"""Юнит: определение класса (статика), состояние (сохраняется) и рантайм-объект."""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Collection, Iterator, Mapping, Optional, Sequence

from .definitions import ItemDefinition
from .effects import ActiveEffect, EffectDefinition, apply_effect, tick_effects
from .resource import Resource
from .stats import STAT_DEFAULTS, Modifier, Stat, compute_stat
from .tactics import TacticsSet

# Правила ресурсов. Максимумы AP/PP задаются в данных класса (ap_max, pp_max).
# AP и PP не восстанавливаются сами: только навыками (ap_restore / pp_restore).
AP_START: Optional[int] = None  # None = полный запас в начале боя
AP_PER_TURN = 0
DEFAULT_AP_MAX = 4
DEFAULT_PP_MAX = 1


def _stat_map(data: Mapping[str, float]) -> Mapping[Stat, float]:
    return MappingProxyType({Stat(k): v for k, v in data.items()})


def parse_learned(entries: Sequence[Any]) -> tuple[tuple[str, ...], Mapping[str, int]]:
    """Список навыков (или пассивок) класса: id или {"id": ..., "level": ...}.

    Возвращает все id по порядку и уровни открытия тех, что открываются выше первого уровня.
    """
    ids, levels = [], {}
    for entry in entries:
        if isinstance(entry, str):
            ids.append(entry)
            continue
        level = int(entry.get("level", 1))
        if level < 1:
            raise ValueError(f"unlock level of {entry['id']!r} must be at least 1")
        ids.append(entry["id"])
        if level > 1:
            levels[entry["id"]] = level
    return tuple(ids), MappingProxyType(levels)


def learned_to_list(ids: Sequence[str], levels: Mapping[str, int]) -> list[Any]:
    """Обратно в формат данных: открытые с первого уровня — просто id."""
    return [{"id": i, "level": levels[i]} if levels.get(i, 1) > 1 else i for i in ids]


def place_equipment(
    slots: Sequence[str], items: Mapping[str, ItemDefinition], item_ids: Sequence[Optional[str]],
    strict: bool = True,
) -> list[Optional[str]]:
    """Раскладывает предметы по слотам класса: результат выровнен по slots, None = пусто.

    Принимает и уже выровненный список, и простой перечень предметов
    (каждый попадает в первый свободный слот своего типа). При strict=False
    неизвестные и не поместившиеся предметы молча отбрасываются: так загружаются
    сохранения после правки классов и предметов.
    """
    ids = list(item_ids)
    for item_id in ids:
        if item_id is not None and item_id not in items and strict:
            raise ValueError(f"unknown item {item_id!r}")
    ids = [i if i in items else None for i in ids]
    if len(ids) == len(slots) and all(i is None or items[i].slot == s for i, s in zip(ids, slots)):
        return ids
    placed: list[Optional[str]] = [None] * len(slots)
    for item_id in ids:
        if item_id is None:
            continue
        slot = items[item_id].slot
        free = next((k for k, s in enumerate(slots) if s == slot and placed[k] is None), None)
        if free is not None:
            placed[free] = item_id
        elif strict:
            raise ValueError(f"no free {slot!r} slot for item {item_id!r}")
    return placed


@dataclass(frozen=True)
class UnitDefinition:
    """Класс юнита."""

    id: str
    name: str
    base_stats: Mapping[Stat, float]
    growth: Mapping[Stat, float]        # прибавка за каждый уровень выше первого
    skills: tuple[str, ...] = ()
    passives: tuple[str, ...] = ()
    tactics: TacticsSet = TacticsSet()
    slots: tuple[str, ...] = ()         # типы слотов снаряжения
    tags: tuple[str, ...] = ()          # особенности класса: пехота, конница и т. д.
    ap_max: int = DEFAULT_AP_MAX
    pp_max: int = DEFAULT_PP_MAX
    # Уровень класса, с которого открывается навык или пассивка; кого здесь нет — с первого.
    skill_levels: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))
    passive_levels: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))

    @classmethod
    def from_dict(cls, unit_id: str, data: Mapping[str, Any]) -> "UnitDefinition":
        skills, skill_levels = parse_learned(data.get("skills", ()))
        passives, passive_levels = parse_learned(data.get("passives", ()))
        return cls(
            id=unit_id,
            name=data.get("name", unit_id),
            base_stats=_stat_map(data["stats"]),
            growth=_stat_map(data.get("growth", {})),
            skills=skills,
            passives=passives,
            tactics=TacticsSet.from_list(data.get("tactics", ())),
            slots=tuple(data.get("slots", ())),
            tags=tuple(data.get("tags", ())),
            ap_max=data.get("ap_max", DEFAULT_AP_MAX),
            pp_max=data.get("pp_max", DEFAULT_PP_MAX),
            skill_levels=skill_levels,
            passive_levels=passive_levels,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "stats": {stat.value: value for stat, value in self.base_stats.items()},
            "growth": {stat.value: value for stat, value in self.growth.items()},
            "ap_max": self.ap_max,
            "pp_max": self.pp_max,
            "tags": list(self.tags),
            "slots": list(self.slots),
            "skills": learned_to_list(self.skills, self.skill_levels),
            "passives": learned_to_list(self.passives, self.passive_levels),
            "tactics": self.tactics.to_list(),
        }

    def skills_at(self, level: int) -> tuple[str, ...]:
        """Навыки класса, открытые к этому уровню."""
        return tuple(s for s in self.skills if self.skill_levels.get(s, 1) <= level)

    def passives_at(self, level: int) -> tuple[str, ...]:
        return tuple(p for p in self.passives if self.passive_levels.get(p, 1) <= level)

    @property
    def top_unlock(self) -> int:
        """Уровень, к которому открыто всё, что есть у класса."""
        return max((*self.skill_levels.values(), *self.passive_levels.values()), default=1)


@dataclass
class UnitState:
    """Всё, что сохраняется про юнита. Итоговых статов здесь нет.

    equipment выровнен по слотам определения: id предмета или None.
    """

    uid: int
    definition_id: str
    level: int
    current_hp: int
    equipment: list[Optional[str]] = field(default_factory=list)
    exp: int = 0          # опыт к следующему уровню


class Unit:
    """Рантайм-юнит: определение + состояние + AP/PP + активные эффекты."""

    def __init__(self, definition: UnitDefinition, state: UnitState, items: Mapping[str, ItemDefinition],
                 strict: bool = True):
        self.definition = definition
        self.state = state
        self._items = items  # справочник предметов для разрешения state.equipment
        state.equipment = place_equipment(definition.slots, items, state.equipment, strict)
        self.ap = self._full_ap()
        self.pp = Resource(definition.pp_max, definition.pp_max)
        self.effects: list[ActiveEffect] = []
        self.tactics: TacticsSet = definition.tactics  # может быть заменён редактором

    # --- идентичность ---

    @property
    def uid(self) -> int:
        return self.state.uid

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def label(self) -> str:
        return f"{self.name}({self.uid})"

    # --- снаряжение ---

    @property
    def equipped(self) -> list[ItemDefinition]:
        return [self._items[item_id] for item_id in self.state.equipment if item_id is not None]

    def equip(self, slot_index: int, item_id: str) -> None:
        slot = self.definition.slots[slot_index]
        if item_id not in self._items:
            raise ValueError(f"unknown item {item_id!r}")
        if self._items[item_id].slot != slot:
            raise ValueError(f"item {item_id!r} does not fit slot {slot!r}")
        self.state.equipment[slot_index] = item_id

    def unequip(self, slot_index: int) -> Optional[str]:
        item_id = self.state.equipment[slot_index]
        self.state.equipment[slot_index] = None
        return item_id

    @property
    def skill_ids(self) -> tuple[str, ...]:
        """Доступные навыки: класса (открытые к уровню юнита) и надетых предметов."""
        ids = self.definition.skills_at(self.state.level) + tuple(s for item in self.equipped for s in item.skills)
        return tuple(dict.fromkeys(ids))

    @property
    def passive_ids(self) -> tuple[str, ...]:
        """Пассивки класса (открытые к уровню юнита) и надетых предметов."""
        ids = self.definition.passives_at(self.state.level) + tuple(p for item in self.equipped for p in item.passives)
        return tuple(dict.fromkeys(ids))

    @property
    def tags(self) -> frozenset[str]:
        """Теги юнита: класса, надетых предметов и активных эффектов."""
        tags = set(self.definition.tags)
        for item in self.equipped:
            tags.update(item.tags)
        for effect in self.effects:
            tags.update(effect.definition.grants_tags)
        return frozenset(tags)

    @property
    def weapon_damage_tags(self) -> tuple[str, ...]:
        """Тип урона надетого оружия; пусто, если оружия с типом нет."""
        return tuple(dict.fromkeys(tag for item in self.equipped for tag in item.damage_tags))

    # --- статы ---

    def _modifiers(self) -> Iterator[Modifier]:
        for item in self.equipped:
            yield from item.modifiers
        for effect in self.effects:
            yield from effect.modifiers()

    def stat(self, stat: Stat) -> int:
        """Считает стат заново из всех источников; результат нигде не хранится."""
        base = self.definition.base_stats.get(stat, STAT_DEFAULTS.get(stat, 0))
        base += self.definition.growth.get(stat, 0) * (self.state.level - 1)
        return compute_stat(base, (m for m in self._modifiers() if m.stat is stat))

    @property
    def max_hp(self) -> int:
        return self.stat(Stat.HP)

    @property
    def hp(self) -> int:
        return min(self.state.current_hp, self.max_hp)

    @property
    def is_alive(self) -> bool:
        return self.state.current_hp > 0

    def take_damage(self, amount: int) -> int:
        """Возвращает фактически снятое HP."""
        before = self.hp
        self.state.current_hp = max(0, before - max(0, amount))
        return before - self.state.current_hp

    def heal(self, amount: int) -> int:
        """Возвращает фактически восстановленное HP. Мёртвых не лечит."""
        if not self.is_alive:
            return 0
        before = self.hp
        self.state.current_hp = min(self.max_hp, before + max(0, amount))
        return self.state.current_hp - before

    # --- тактики ---

    @property
    def has_custom_tactics(self) -> bool:
        return self.tactics is not self.definition.tactics

    def set_tactics(self, tactics: TacticsSet) -> None:
        self.tactics = tactics

    def reset_tactics(self) -> None:
        self.tactics = self.definition.tactics

    # --- ресурсы ---

    def _full_ap(self) -> Resource:
        ap_max = self.definition.ap_max
        return Resource(ap_max, ap_max if AP_START is None else AP_START)

    def start_battle(self) -> None:
        self.ap = self._full_ap()
        self.pp = Resource(self.definition.pp_max, self.definition.pp_max)

    # --- эффекты ---

    def add_effect(self, definition: EffectDefinition, source: Optional[int] = None) -> Optional[ActiveEffect]:
        return apply_effect(self.effects, definition, source)

    def has_effect(self, effect_id: str) -> bool:
        return any(e.definition.id == effect_id for e in self.effects)

    def has_flag(self, flag: str) -> bool:
        return any(flag in e.definition.flags for e in self.effects)

    def dispel(self, tag: str) -> list[ActiveEffect]:
        """Снимает все эффекты с меткой и возвращает их."""
        removed = [e for e in self.effects if tag in e.definition.tags]
        self.effects = [e for e in self.effects if tag not in e.definition.tags]
        return removed

    def tick(self, skip: Collection[ActiveEffect] = ()) -> list[ActiveEffect]:
        """Конец хода носителя: возвращает истёкшие эффекты. skip не убывают."""
        return tick_effects(self.effects, skip)

    def save_effects(self) -> list[dict[str, Any]]:
        return [e.to_save() for e in self.effects]

    def load_effects(self, saved: Sequence[Mapping[str, Any]], definitions: Mapping[str, EffectDefinition]) -> None:
        self.effects = [ActiveEffect.from_save(d, definitions) for d in saved if d["effect_id"] in definitions]

    def __repr__(self) -> str:
        return f"<Unit {self.label} L{self.state.level} HP {self.hp}/{self.max_hp}>"
