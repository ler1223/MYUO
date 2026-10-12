"""Справочник всех определений игры.

Данные лежат в папке data/ по одному JSON на раздел (классы, предметы, навыки,
эффекты, пассивки, теги) плюс config.json (типы слотов и правила тегов).
Редакторы меняют справочник через update/create/delete и сохраняют его save().
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

from . import events
from .definitions import CATEGORIES, ItemDefinition, PassiveDefinition, SkillDefinition
from .effects import EffectDefinition
from .tags import TagDefinition, TagRule
from .unit import Unit, UnitDefinition, UnitState

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CONFIG = "config"

# Раздел -> класс определения. Порядок = порядок разбора (сначала то, на что ссылаются).
SECTIONS = {
    "tags": TagDefinition,
    "effects": EffectDefinition,
    "passives": PassiveDefinition,
    "skills": SkillDefinition,
    "items": ItemDefinition,
    "units": UnitDefinition,
}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


class Database:
    def __init__(self, data: Mapping[str, Any], directory: Union[str, Path, None] = None):
        self.directory = Path(directory) if directory else None
        self.tags: dict[str, TagDefinition] = {}
        self.effects: dict[str, EffectDefinition] = {}
        self.passives: dict[str, PassiveDefinition] = {}
        self.skills: dict[str, SkillDefinition] = {}
        self.items: dict[str, ItemDefinition] = {}
        self.units: dict[str, UnitDefinition] = {}
        self.slot_types: tuple[str, ...] = ()
        self.rules: list[TagRule] = []
        self._apply(data)

    # --- загрузка и сохранение ---

    @classmethod
    def load(cls, directory: Union[str, Path, None] = None) -> "Database":
        directory = Path(directory or DEFAULT_DATA_DIR)
        data = {}
        for name in (*SECTIONS, CONFIG):
            data[name] = json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
        return cls(data, directory)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            section: {key: value.to_dict() for key, value in getattr(self, section).items()}
            for section in SECTIONS
        }
        data[CONFIG] = {"slot_types": list(self.slot_types), "tag_rules": [r.to_dict() for r in self.rules]}
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
        parsed = {
            section: {key: cls.from_dict(key, value) for key, value in data.get(section, {}).items()}
            for section, cls in SECTIONS.items()
        }
        config = data.get(CONFIG, {})
        slot_types = tuple(config.get("slot_types", ()))
        rules = [TagRule.from_dict(r) for r in config.get("tag_rules", ())]
        self._validate(parsed, slot_types, rules)
        for section, values in parsed.items():
            target = getattr(self, section)
            target.clear()
            target.update(values)
        self.slot_types = slot_types
        self.rules = rules

    @staticmethod
    def _validate(parsed: Mapping[str, Mapping[str, Any]], slot_types: Sequence[str], rules: Sequence[TagRule]) -> None:
        """Проверяет ссылки между определениями, чтобы опечатка в данных падала сразу."""
        tags, effects, passives = parsed["tags"], parsed["effects"], parsed["passives"]
        skills, items = parsed["skills"], parsed["items"]

        def require(known: Any, refs: Any, where: str) -> None:
            for ref in refs:
                if ref not in known:
                    raise ValueError(f"{where}: unknown id {ref!r}")

        for effect in effects.values():
            require(tags, effect.grants_tags, f"effect {effect.id}")
            for mod in effect.attack_mods:
                require(tags, mod.add_tags, f"effect {effect.id}")
        for passive in passives.values():
            require(effects, [passive.effect_id], f"passive {passive.id}")
            if not hasattr(events, passive.trigger):
                raise ValueError(f"passive {passive.id}: unknown event {passive.trigger!r}")
        for skill in skills.values():
            where = f"skill {skill.id}"
            require(effects, [a.effect_id for a in skill.applies], where)
            require(tags, skill.tags, where)
            require(tags, [tag for tag, _ in skill.bonus_vs], where)
            for part in skill.parts:
                require(tags, part.tags, where)
        for item in items.values():
            where = f"item {item.id}"
            require(slot_types, [item.slot], where)
            require(skills, item.skills, where)
            require(passives, item.passives, where)
            require(tags, item.tags + item.damage_tags, where)
        for unit in parsed["units"].values():
            where = f"unit {unit.id}"
            require(slot_types, unit.slots, where)
            require(skills, unit.skills, where)
            require(passives, unit.passives, where)
            require(tags, unit.tags, where)
            require(skills, [rule.skill_id for rule in unit.tactics.rules], f"{where} tactics")
        for rule in rules:
            require({*tags, *CATEGORIES}, rule.tags(), "tag rule")

    # --- правка (редакторы) ---

    def update(self, section: str, key: str, value: Mapping[str, Any]) -> None:
        """Заменяет или добавляет определение, заданное в формате JSON."""
        data = self.to_dict()
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
        data = self.to_dict()
        del data[section][key]

        def drop(container: dict[str, Any], *fields: str) -> None:
            for field in fields:
                if field in container:
                    container[field] = [x for x in container[field] if x != key]

        if section == "skills":
            for unit in data["units"].values():
                drop(unit, "skills")
                unit["tactics"] = [r for r in unit["tactics"] if r["skill"] != key]
            for item in data["items"].values():
                drop(item, "skills")
        elif section == "passives":
            for owner in (*data["units"].values(), *data["items"].values()):
                drop(owner, "passives")
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

    def set_rules(self, rules: Sequence[Mapping[str, Any]]) -> None:
        data = self.to_dict()
        data[CONFIG]["tag_rules"] = [dict(r) for r in rules]
        self._apply(data)

    # --- юниты ---

    def create_unit(self, definition_id: str, uid: int, level: int = 1, equipment: Sequence[Optional[str]] = ()) -> Unit:
        """Новый юнит с полным HP. Предметы раскладываются по подходящим слотам класса."""
        state = UnitState(uid=uid, definition_id=definition_id, level=level, current_hp=0, equipment=list(equipment))
        unit = Unit(self.units[definition_id], state, self.items)
        state.current_hp = unit.max_hp
        return unit

    def restore_unit(self, state: UnitState, saved_effects: Sequence[Mapping[str, Any]] = ()) -> Unit:
        """Восстанавливает юнита из сохранённого состояния и списка эффектов.

        Снаряжение, которого больше нет или которое не подходит к слотам класса, снимается.
        """
        unit = Unit(self.units[state.definition_id], state, self.items, strict=False)
        unit.load_effects(saved_effects, self.effects)
        return unit
