"""Справочник всех определений игры.

Данные лежат в папке data/ по одному JSON на раздел (классы, предметы, навыки,
эффекты, пассивки, теги) плюс config.json (типы слотов и правила тегов).
Редакторы меняют справочник через update/create/delete и сохраняют его save().
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

from .areas import AREA_SINGLE, BUILTIN_AREAS, AreaDefinition
from .abilities import merge_passives, referenced_skills, skill_from_passive
from .definitions import CATEGORIES, ItemDefinition, PassiveDefinition, SkillDefinition
from .effects import EffectDefinition
from .squad import FormationSize
from .tags import TagDefinition, TagRule
from .promotion import merged_definition
from .unit import Unit, UnitDefinition, UnitState

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class GuardRules:
    """Блок, как в UO: уровень блока — какую долю физического урона он снимает.

    base — уровень блока без щита; tags — тег носителя (от щита) -> уровень; принудительный блок
    (эффект с флагом guard_small / guard_medium / guard_heavy) берёт уровень из флага.
    Без раздела "guard" в config.json — прежнее правило: любой блок снимает половину."""

    levels: Mapping[str, float] = field(default_factory=lambda: {"small": 0.25, "medium": 0.5, "heavy": 0.75})
    base: str = "medium"
    tags: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GuardRules":
        rules = cls(**{k: v for k, v in data.items() if k in ("levels", "base", "tags")})
        for level in (rules.base, *rules.tags.values()):
            if level not in rules.levels:
                raise ValueError(f"unknown guard level {level!r}")
        return rules

    def to_dict(self) -> dict[str, Any]:
        return {"levels": dict(self.levels), "base": self.base, "tags": dict(self.tags)}

    def reduction(self, level: str) -> float:
        return float(self.levels.get(level, 0.5))

    def level_of(self, tags: Any) -> str:
        """Лучший уровень блока по тегам носителя (щит, большой щит)."""
        best = self.base
        for tag, level in self.tags.items():
            if tag in tags and self.reduction(level) > self.reduction(best):
                best = level
        return best
CONFIG = "config"

# Раздел -> класс определения. Порядок = порядок разбора (сначала то, на что ссылаются).
SECTIONS = {
    "areas": AreaDefinition,
    "tags": TagDefinition,
    "effects": EffectDefinition,
    "skills": SkillDefinition,          # и активные, и пассивки (kind: passive)
    "items": ItemDefinition,
    "units": UnitDefinition,
}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


class Database:
    def __init__(self, data: Mapping[str, Any], directory: Union[str, Path, None] = None):
        self.directory = Path(directory) if directory else None
        self.areas: dict[str, AreaDefinition] = {}
        self.tags: dict[str, TagDefinition] = {}
        self.effects: dict[str, EffectDefinition] = {}
        self.passives: dict[str, PassiveDefinition] = {}
        self.skills: dict[str, SkillDefinition] = {}
        self.items: dict[str, ItemDefinition] = {}
        self.units: dict[str, UnitDefinition] = {}
        self.slot_types: tuple[str, ...] = ()
        self.formation = FormationSize()
        self.rules: list[TagRule] = []
        self.passives_per_action = 2      # сколько пассивок срабатывает за одно активное действие
        self._apply(data)

    # --- загрузка и сохранение ---

    @classmethod
    def load(cls, directory: Union[str, Path, None] = None) -> "Database":
        directory = Path(directory or DEFAULT_DATA_DIR)
        data = {}
        for name in (*SECTIONS, CONFIG):
            path = directory / f"{name}.json"
            if name == "areas" and not path.exists():
                continue  # старая папка данных без областей: возьмутся встроенные
            data[name] = json.loads(path.read_text(encoding="utf-8"))
        legacy = directory / "passives.json"
        if legacy.exists():                    # старая папка данных: пассивки лежали отдельно
            data["passives"] = json.loads(legacy.read_text(encoding="utf-8"))
        return cls(data, directory)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            section: {key: value.to_dict() for key, value in getattr(self, section).items()}
            for section in SECTIONS
        }
        data[CONFIG] = {"formation": self.formation.to_dict(), "slot_types": list(self.slot_types),
                        "tag_rules": [r.to_dict() for r in self.rules], "guard": self.guard.to_dict(),
                        "combat": {"passives_per_action": self.passives_per_action}}
        return data

    def save(self, directory: Union[str, Path, None] = None) -> None:
        directory = Path(directory or self.directory or DEFAULT_DATA_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        for name, content in self.to_dict().items():
            text = json.dumps(content, indent=2, ensure_ascii=False)
            (directory / f"{name}.json").write_text(text + "\n", encoding="utf-8")

    def copy(self) -> "Database":
        return Database(self.to_dict(), self.directory)

    def _apply(self, data: Mapping[str, Any]) -> None:
        """Разбирает и проверяет данные целиком; при ошибке справочник не меняется.

        Словари разделов обновляются на месте: юниты держат ссылку на self.items.
        """
        source = dict(data)
        source.setdefault("areas", BUILTIN_AREAS)
        legacy = source.pop("passives", None)
        if legacy:                             # пассивки старого вида (раздел passives) становятся навыками
            merge_passives(source, legacy)
        parsed = {
            section: {key: cls.from_dict(key, value) for key, value in source.get(section, {}).items()}
            for section, cls in SECTIONS.items()
        }
        parsed["passives"] = {}
        for skill in parsed["skills"].values():
            if skill.is_passive:
                try:
                    parsed["passives"][skill.id] = skill.passive_view()
                except ValueError as error:
                    raise ValueError(str(error)) from None
        config = data.get(CONFIG, {})
        slot_types = tuple(config.get("slot_types", ()))
        rules = [TagRule.from_dict(r) for r in config.get("tag_rules", ())]
        formation = FormationSize.from_dict(config.get("formation", {}))
        guard = GuardRules.from_dict(config.get("guard", {}))
        self._validate(parsed, slot_types, rules)
        for section, values in parsed.items():
            target = getattr(self, section)
            target.clear()
            target.update(values)
        self.slot_types = slot_types
        self.rules = rules
        self.formation = formation
        self.guard = guard
        self.passives_per_action = max(0, int(config.get("combat", {}).get("passives_per_action", 2)))
        self._merged: dict[tuple[str, ...], UnitDefinition] = {}

    @staticmethod
    def _validate(parsed: Mapping[str, Mapping[str, Any]], slot_types: Sequence[str], rules: Sequence[TagRule]) -> None:
        """Проверяет ссылки между определениями, чтобы опечатка в данных падала сразу."""
        tags, effects, passives = parsed["tags"], parsed["effects"], parsed["passives"]
        skills, items, areas = parsed["skills"], parsed["items"], parsed["areas"]
        actives = {k: v for k, v in skills.items() if not v.is_passive}
        if AREA_SINGLE not in areas:
            raise ValueError(f"area {AREA_SINGLE!r} is required")

        def require(known: Any, refs: Any, where: str) -> None:
            for ref in refs:
                if ref not in known:
                    raise ValueError(f"{where}: unknown id {ref!r}")

        for effect in effects.values():
            require(tags, effect.grants_tags, f"effect {effect.id}")
            for mod in effect.attack_mods:
                require(tags, mod.add_tags, f"effect {effect.id}")
        known = {"skills": skills, "effects": effects, "areas": areas, "attack_tags": {*tags, *CATEGORIES, "healing"}}
        reactions = [(f"effect {e.id}", r) for e in effects.values() for r in e.triggers]
        reactions += [(f"passive {p.id}", p.reaction) for p in passives.values()]
        for where, reaction in reactions:
            for section, refs in reaction.references().items():
                require(known[section], refs, where)
        for skill in skills.values():
            where = f"skill {skill.id}"
            require(effects, [a.effect_id for a in skill.applies], where)
            require(areas, [skill.area], where)
            require(tags, skill.tags, where)
            require(tags, [tag for tag, _ in skill.bonus_vs], where)
            for part in skill.parts:
                require(tags, part.tags, where)
        for item in items.values():
            where = f"item {item.id}"
            require(slot_types, [item.slot], where)
            require(actives, item.skills, where)
            require(passives, item.passives, where)
            require(tags, item.tags + item.damage_tags, where)
            require(parsed["units"], item.classes, where)
        for unit in parsed["units"].values():
            where = f"unit {unit.id}"
            require(slot_types, unit.slots, where)
            require(actives, unit.skills, where)
            require(passives, unit.passives, where)
            require(tags, unit.tags, where)
            require(skills, [rule.skill_id for rule in unit.tactics.rules], f"{where} tactics")
        for rule in rules:
            require({*tags, *CATEGORIES}, rule.tags(), "tag rule")
        units = parsed["units"]
        for unit in units.values():
            require(units, [p.class_id for p in unit.promotions], f"unit {unit.id} promotions")

        def climb(class_id: str, path: tuple[str, ...]) -> None:      # повышения не ходят по кругу
            if class_id in path:
                raise ValueError(f"promotion cycle: {' -> '.join(path + (class_id,))}")
            for promotion in units[class_id].promotions:
                climb(promotion.class_id, path + (class_id,))

        for class_id in units:
            climb(class_id, ())

    # --- правка (редакторы) ---

    def update(self, section: str, key: str, value: Mapping[str, Any]) -> None:
        """Заменяет или добавляет определение, заданное в формате JSON."""
        data = self.to_dict()
        if section == "passives":              # редакторы пассивок отдают старый вид; хранится навык-пассивка
            skill, gone = skill_from_passive(key, value, data["skills"], referenced_skills(data, {}))
            data["skills"][key] = skill
            if gone:
                data["skills"].pop(gone, None)
        else:
            data[section][key] = dict(value)
        self._apply(data)

    def create(self, section: str, name: str, value: Mapping[str, Any]) -> str:
        """Добавляет определение под новым id, полученным из названия. Возвращает id."""
        base = slugify(name) or section.rstrip("s")
        key, n = base, 2
        while key in getattr(self, section):
            key, n = f"{base}_{n}", n + 1
        self.update(section, key, dict(value, name=name))
        return key

    def delete(self, section: str, key: str) -> None:
        """Удаляет определение и вычищает все ссылки на него."""
        if section == "areas" and key == AREA_SINGLE:
            raise ValueError(f"area {AREA_SINGLE!r} cannot be deleted")
        data = self.to_dict()
        passive = section == "passives" or (section == "skills" and key in self.skills and self.skills[key].is_passive)
        if section == "passives":
            section = "skills"
        del data[section][key]
        if passive:                            # пассивку убирают и у классов, предметов и из тактик
            for owner in (*data["units"].values(), *data["items"].values()):
                owner["passives"] = [p for p in owner["passives"] if _entry_id(p) != key]
            for unit in data["units"].values():
                unit["tactics"] = [r for r in unit["tactics"] if r["skill"] != key]

        def drop(container: dict[str, Any], *fields: str) -> None:
            for field in fields:
                if field in container:
                    container[field] = [x for x in container[field] if _entry_id(x) != key]

        _clean_reactions(data, section, key)
        if section == "skills":
            for unit in data["units"].values():
                drop(unit, "skills")
                unit["tactics"] = [r for r in unit["tactics"] if r["skill"] != key]
            for item in data["items"].values():
                drop(item, "skills")
        elif section == "units":
            for unit in data["units"].values():
                unit["promotions"] = [p for p in unit.get("promotions", ()) if p["class"] != key]
            for item in data["items"].values():
                drop(item, "classes")
        elif section == "areas":
            for skill in data["skills"].values():
                if skill["area"] == key:
                    skill["area"] = AREA_SINGLE
        elif section == "effects":
            for skill in data["skills"].values():
                skill["applies"] = [a for a in skill["applies"] if a["effect_id"] != key]
        elif section == "tags":
            for unit in data["units"].values():
                drop(unit, "tags")
            for item in data["items"].values():
                drop(item, "tags", "damage_tags")
            for skill in data["skills"].values():
                drop(skill, "tags")
                skill["bonus_vs"].pop(key, None)
                for part in skill["parts"]:
                    drop(part, "tags")
            for effect in data["effects"].values():
                drop(effect, "grants_tags")
                for mod in effect["attack_mods"]:
                    drop(mod, "add_tags")
            config = data[CONFIG]
            config["tag_rules"] = [
                r for r in config["tag_rules"] if key not in (*r["attack"], *r["attack_not"], *r["target"])
            ]
        self._apply(data)

    def set_formation(self, rows: int, cols: int, max_units: int) -> None:
        """Меняет размер поля отряда и предел числа юнитов."""
        data = self.to_dict()
        data[CONFIG]["formation"] = {"rows": rows, "cols": cols, "max_units": max_units}
        self._apply(data)

    def set_rules(self, rules: Sequence[Mapping[str, Any]]) -> None:
        data = self.to_dict()
        data[CONFIG]["tag_rules"] = [dict(r) for r in rules]
        self._apply(data)

    # --- юниты ---

    # --- классы и повышения ---

    def definition_for(self, definition_id: str, history: Sequence[str] = ()) -> UnitDefinition:
        """Класс бойца с учётом истории повышений (game/promotion.py); исчезнувшие классы истории пропускаются."""
        chain = tuple(c for c in history if c in self.units and c != definition_id) + (definition_id,)
        if chain not in self._merged:
            self._merged[chain] = merged_definition([self.units[c] for c in chain])
        return self._merged[chain]

    def parents(self, class_id: str) -> list[str]:
        """Классы, которые повышаются в class_id."""
        return [u.id for u in self.units.values() if any(p.class_id == class_id for p in u.promotions)]

    def lineage(self, class_id: str) -> list[str]:
        """Путь к классу от базового (первый найденный): история для бойца, созданного сразу этим классом."""
        path, current = [], class_id
        while True:
            parents = [p for p in self.parents(current) if p not in path and p != class_id]
            if not parents:
                return list(reversed(path))
            current = parents[0]
            path.append(current)

    def promotion_level(self, class_id: str) -> int:
        """Наименьший уровень, на котором до класса можно дойти повышениями от базового."""
        level, chain = 1, self.lineage(class_id) + [class_id]
        for before, after in zip(chain, chain[1:]):
            level = max(level, next(p.level for p in self.units[before].promotions if p.class_id == after))
        return level

    def create_unit(self, definition_id: str, uid: int, level: int = 1, equipment: Sequence[Optional[str]] = (),
                    history: Optional[Sequence[str]] = None) -> Unit:
        """Новый юнит с полным HP. Предметы раскладываются по подходящим слотам класса.
        history — классы до повышений; None — путь от базового класса (lineage)."""
        history = self.lineage(definition_id) if history is None else list(history)
        state = UnitState(uid=uid, definition_id=definition_id, level=level, current_hp=0, equipment=list(equipment),
                          history=history)
        unit = Unit(self.definition_for(definition_id, history), state, self.items)
        state.current_hp = unit.max_hp
        return unit

    def restore_unit(self, state: UnitState, saved_effects: Sequence[Mapping[str, Any]] = ()) -> Unit:
        """Восстанавливает юнита из сохранённого состояния и списка эффектов.

        Снаряжение, которого больше нет или которое не подходит к слотам класса, снимается.
        """
        state.history = [c for c in state.history if c in self.units]
        unit = Unit(self.definition_for(state.definition_id, state.history), state, self.items, strict=False)
        unit.load_effects(saved_effects, self.effects)
        return unit


def _entry_id(entry: Any) -> Any:
    """id элемента списка: строка или {"id": ...} (навык класса, открываемый с уровня)."""
    return entry.get("id") if isinstance(entry, dict) else entry


def _clean_reactions(data: dict[str, Any], section: str, key: str) -> None:
    """Убирает ссылки на удалённое определение из реакций эффектов и из пассивок-навыков (данные в формате JSON).

    Действие, которому без него нечего делать (навык, эффект или фильтр по эффекту), удаляется; пассивка, у которой
    не осталось ни тела, ни прикрытия, ни действий, удаляется вместе со ссылками на неё.
    Удалённая область или тег просто перестают фильтровать.
    """
    def fix(reaction: dict[str, Any]) -> bool:
        """Правит реакцию эффекта на месте; False, если её надо удалить."""
        if section == "skills" and reaction["skill_id"] == key:
            return False
        if section == "effects":
            if reaction["effect_filter"] == key:
                return False
            if reaction["effect_id"] == key:
                if reaction["action"] != "cover":
                    return False
                reaction["effect_id"] = None  # у прикрытия эффект необязателен
        if section == "areas":
            for field in ("area", "to_area"):
                if reaction[field] == key:
                    reaction[field] = None
            reaction["skill_areas"] = [a for a in reaction["skill_areas"] if a != key]
        if section == "tags":
            reaction["attack_tags"] = [t for t in reaction["attack_tags"] if t != key]
        return True

    def step_ok(step: dict[str, Any]) -> bool:
        if section == "skills" and step.get("skill_id") == key:
            return False
        if section == "effects" and step.get("effect_id") == key:
            return False
        if section == "areas" and step.get("to_area") == key:
            step.pop("to_area")
        return True

    def passive_ok(skill: dict[str, Any]) -> bool:
        trigger = skill["trigger"]
        if section == "effects" and trigger.get("effect_filter") == key:
            return False
        if section == "areas":
            if trigger.get("area") == key:
                trigger.pop("area")
            if trigger.get("skill_areas"):
                trigger["skill_areas"] = [a for a in trigger["skill_areas"] if a != key]
            if skill.get("target_area") == key:
                skill.pop("target_area")
        if section == "tags" and trigger.get("attack_tags"):
            trigger["attack_tags"] = [t for t in trigger["attack_tags"] if t != key]
        cover = skill.get("cover")
        if cover and section == "effects" and cover.get("effect_id") == key:
            cover.pop("effect_id")
        if skill.get("steps"):
            skill["steps"] = [s for s in skill["steps"] if step_ok(s)]
        return bool(skill.get("body") or skill.get("cover") is not None or skill.get("steps"))

    for effect in data["effects"].values():
        effect["triggers"] = [r for r in effect["triggers"] if fix(r)]
    gone = [skill_id for skill_id, skill in data["skills"].items()
            if skill.get("kind") == "passive" and not passive_ok(skill)]
    for skill_id in gone:
        del data["skills"][skill_id]
        for owner in (*data["units"].values(), *data["items"].values()):
            owner["passives"] = [p for p in owner["passives"] if _entry_id(p) != skill_id]
        for unit in data["units"].values():
            unit["tactics"] = [r for r in unit["tactics"] if r["skill"] != skill_id]
