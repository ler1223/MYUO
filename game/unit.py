"""Юнит: определение (статика), состояние (сохраняется) и рантайм-объект."""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Collection, Iterator, Mapping, Optional, Sequence

from .definitions import ItemDefinition
from .effects import ActiveEffect, EffectDefinition, apply_effect, tick_effects
from .resource import Resource
from .stats import Modifier, Stat, compute_stat
from .tactics import TacticsSet

# Правила ресурсов. Максимумы AP/PP задаются в JSON юнита (ap_max, pp_max).
# AP и PP не восстанавливаются сами: только навыками (ap_restore / pp_restore).
AP_START: Optional[int] = None  # None = полный запас в начале боя
AP_PER_TURN = 0
DEFAULT_AP_MAX = 4
DEFAULT_PP_MAX = 1


def _stat_map(data: Mapping[str, float]) -> Mapping[Stat, float]:
    return MappingProxyType({Stat(k): v for k, v in data.items()})


def place_equipment(
    slots: Sequence[str], items: Mapping[str, ItemDefinition], item_ids: Sequence[Optional[str]]
) -> list[Optional[str]]:
    """Раскладывает предметы по слотам класса: результат выровнен по slots, None = пусто.

    Принимает и уже выровненный список, и простой перечень предметов
    (каждый попадает в первый свободный слот своего типа).
    """
    ids = list(item_ids)
    for item_id in ids:
        if item_id is not None and item_id not in items:
            raise ValueError(f"unknown item {item_id!r}")
    if len(ids) == len(slots) and all(i is None or items[i].slot == s for i, s in zip(ids, slots)):
        return ids
    placed: list[Optional[str]] = [None] * len(slots)
    for item_id in ids:
        if item_id is None:
            continue
        slot = items[item_id].slot
        free = next((k for k, s in enumerate(slots) if s == slot and placed[k] is None), None)
        if free is None:
            raise ValueError(f"no free {slot!r} slot for item {item_id!r}")
        placed[free] = item_id
    return placed


@dataclass(frozen=True)
class UnitDefinition:
    id: str
    name: str
    base_stats: Mapping[Stat, float]
    growth: Mapping[Stat, float]        # прибавка за каждый уровень выше первого
    skills: tuple[str, ...] = ()
    passives: tuple[str, ...] = ()
    tactics: TacticsSet = TacticsSet()
    slots: tuple[str, ...] = ()         # типы слотов снаряжения, жёстко заданы классом
    ap_max: int = DEFAULT_AP_MAX
    pp_max: int = DEFAULT_PP_MAX

    @classmethod
    def from_dict(cls, unit_id: str, data: Mapping[str, Any]) -> "UnitDefinition":
        return cls(
            id=unit_id,
            name=data.get("name", unit_id),
            base_stats=_stat_map(data["stats"]),
            growth=_stat_map(data.get("growth", {})),
            skills=tuple(data.get("skills", ())),
            passives=tuple(data.get("passives", ())),
            tactics=TacticsSet.from_list(data.get("tactics", ())),
            slots=tuple(data.get("slots", ())),
            ap_max=data.get("ap_max", DEFAULT_AP_MAX),
            pp_max=data.get("pp_max", DEFAULT_PP_MAX),
        )


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


class Unit:
    """Рантайм-юнит: определение + состояние + AP/PP + активные эффекты."""

    def __init__(self, definition: UnitDefinition, state: UnitState, items: Mapping[str, ItemDefinition]):
        self.definition = definition
        self.state = state
        self._items = items  # справочник предметов для разрешения state.equipment
        state.equipment = place_equipment(definition.slots, items, state.equipment)
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
        """Навыки класса и надетых предметов."""
        ids = self.definition.skills + tuple(s for item in self.equipped for s in item.skills)
        return tuple(dict.fromkeys(ids))

    @property
    def passive_ids(self) -> tuple[str, ...]:
        """Пассивки класса и надетых предметов."""
        ids = self.definition.passives + tuple(p for item in self.equipped for p in item.passives)
        return tuple(dict.fromkeys(ids))

    # --- статы ---

    def _modifiers(self) -> Iterator[Modifier]:
        for item in self.equipped:
            yield from item.modifiers
        for effect in self.effects:
            yield from effect.modifiers()

    def stat(self, stat: Stat) -> int:
        """Считает стат заново из всех источников; результат нигде не хранится."""
        base = self.definition.base_stats.get(stat, 0) + self.definition.growth.get(stat, 0) * (self.state.level - 1)
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
        """Снимает все эффекты с тегом и возвращает их."""
        removed = [e for e in self.effects if tag in e.definition.tags]
        self.effects = [e for e in self.effects if tag not in e.definition.tags]
        return removed

    def tick(self, skip: Collection[ActiveEffect] = ()) -> list[ActiveEffect]:
        """Конец хода носителя: возвращает истёкшие эффекты. skip не убывают."""
        return tick_effects(self.effects, skip)

    def save_effects(self) -> list[dict[str, Any]]:
        return [e.to_save() for e in self.effects]

    def load_effects(self, saved: Sequence[Mapping[str, Any]], definitions: Mapping[str, EffectDefinition]) -> None:
        self.effects = [ActiveEffect.from_save(d, definitions) for d in saved]

    def __repr__(self) -> str:
        return f"<Unit {self.label} L{self.state.level} HP {self.hp}/{self.max_hp}>"
