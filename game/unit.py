"""Юнит: определение класса (статика), состояние (сохраняется) и рантайм-объект."""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Collection, Iterator, Mapping, Optional, Sequence

from .definitions import ItemDefinition
from .effects import ActiveEffect, EffectDefinition, apply_effect, tick_effects
from .resource import Resource
from .roles import normalize as normalize_roles
from .stats import STAT_DEFAULTS, Modifier, ModOp, Stat, compute_stat
from .tactics import TacticsSet
from .tiers import check_tier

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


def class_allowed(item: ItemDefinition, class_ids: Sequence[str], story: bool = False) -> bool:
    """Предмет разрешён классу: пустой список — без ограничений, иначе совпадение хотя бы с одним классом.

    Классы бойца — текущий и история повышений (game/promotion.py): то, чем он был до этого.
    Сюжетные классы (story: true) не ограничены: их снаряжение задаётся сюжетом, а вики-списки
    «Equippable By» их не покрывают.
    """
    if story:
        return True
    if not item.classes:
        return True
    return any(c in item.classes for c in class_ids)


def class_ids_of(definition: UnitDefinition) -> tuple[str, ...]:
    """Классы, которые носит определение класса: сам класс и его предки (game/promotion.py)."""
    return tuple(dict.fromkeys((definition.id, *(a.id for a in definition.ancestors))))


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
    tier: int = 10                      # тир класса 0..30 (game/tiers.py): базовые 10, повышенные 20, 30
    promotions: tuple["Promotion", ...] = ()   # в кого класс повышается и с какого уровня
    # Классы, которыми боец был до этого (game/promotion.py): их статы на уровне бойца — нижняя граница.
    ancestors: tuple["UnitDefinition", ...] = ()
    grades: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))   # оценки UO (S..F), справочно
    story: bool = False                 # личный класс сюжетного героя UO (принцессы, принц, Ален): не для найма
    # Роли (game/roles.py): воин, лучник, маг, поддержка, танк, целитель; их может быть несколько.
    roles: tuple[str, ...] = ()

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
            tier=check_tier(int(data.get("tier", 10)), f"unit {unit_id}"),
            promotions=tuple(Promotion.from_dict(p) for p in data.get("promotions", ())),
            grades=MappingProxyType(dict(data.get("grades", {}))),
            story=bool(data.get("story", False)),
            roles=normalize_roles(data.get("roles") or data.get("role", ())),
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
            "tier": self.tier,
            "promotions": [p.to_dict() for p in self.promotions],
            **({"grades": dict(self.grades)} if self.grades else {}),
            **({"story": True} if self.story else {}),
            **({"roles": list(self.roles)} if self.roles else {}),
        }

    def base_stat(self, stat: Stat, level: int) -> float:
        """Стат класса на уровне без снаряжения; у повышенного бойца — не ниже, чем у прежних классов."""
        own = self.base_stats.get(stat, STAT_DEFAULTS.get(stat, 0)) + self.growth.get(stat, 0) * (level - 1)
        return max([own] + [a.base_stat(stat, level) for a in self.ancestors])

    def skills_at(self, level: int) -> tuple[str, ...]:
        """Навыки класса, открытые к этому уровню."""
        return tuple(s for s in self.skills if self.skill_levels.get(s, 1) <= level)

    def passives_at(self, level: int) -> tuple[str, ...]:
        return tuple(p for p in self.passives if self.passive_levels.get(p, 1) <= level)

    @property
    def top_unlock(self) -> int:
        """Уровень, к которому открыто всё, что есть у класса."""
        return max((*self.skill_levels.values(), *self.passive_levels.values()), default=1)


@dataclass(frozen=True)
class Promotion:
    """Путь повышения: в класс class_id, когда боец достиг уровня level."""

    class_id: str
    level: int

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Promotion":
        promotion = cls(data["class"], int(data.get("level", 1)))
        if promotion.level < 1:
            raise ValueError(f"promotion level to {promotion.class_id!r} must be at least 1")
        return promotion

    def to_dict(self) -> dict[str, Any]:
        return {"class": self.class_id, "level": self.level}


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
    nickname: str = ""    # личное имя бойца (башня); пусто — зовётся по классу
    history: list[str] = field(default_factory=list)   # классы до повышений, по порядку (game/promotion.py)
    look: int = 0         # модель из списка моделей класса (data/uo_battle.json, classes.<класс>.looks)


class Unit:
    """Рантайм-юнит: определение + состояние + AP/PP + активные эффекты."""

    def __init__(self, definition: UnitDefinition, state: UnitState, items: Mapping[str, ItemDefinition],
                 strict: bool = True):
        self.definition = definition
        self.state = state
        self._items = items  # справочник предметов для разрешения state.equipment
        kept, rejected = self._filter_by_class(state.equipment)
        self.rejected_equipment = rejected      # что не подошло классу (возвращается в инвентарь башни)
        if rejected and strict:
            raise ValueError(f"items {sorted(rejected)} are not allowed for class {definition.id!r}")
        state.equipment = place_equipment(definition.slots, items, kept, strict)
        self.ap = self._full_ap()
        self.pp = Resource(self.pp_max, self.pp_max)
        self.effects: list[ActiveEffect] = []
        self.time_of_day = "day"                # время суток боя (game/combat/engine.py: Battle.time_of_day)
        self.tactics: TacticsSet = definition.tactics  # может быть заменён редактором

    def _filter_by_class(self, item_ids: Sequence[Optional[str]]) -> tuple[list[Optional[str]], list[str]]:
        """Делит снаряжение на подходящее классу и отброшенное (class_allowed, game/unit.py)."""
        if self.definition.story:                 # сюжетные классы не ограничены списками снаряжения
            return list(item_ids), []
        class_ids = tuple(dict.fromkeys((self.definition.id, *self.state.history)))
        kept: list[Optional[str]] = []
        rejected: list[str] = []
        for item_id in item_ids:
            if item_id is None:
                kept.append(item_id)
                continue
            item = self._items.get(item_id)
            if item is not None and not class_allowed(item, class_ids):
                rejected.append(item_id)
                continue
            kept.append(item_id)
        return kept, rejected

    def _allowed(self, item: Optional[ItemDefinition]) -> bool:
        """Предмет разрешён бойцу: сюжетные классы — любой, остальные — по списку классов."""
        if item is None:
            return False
        if self.definition.story:
            return True
        return class_allowed(item, self.class_ids)

    # --- идентичность ---

    @property
    def uid(self) -> int:
        return self.state.uid

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def nickname(self) -> str:
        """Личное имя, если есть, иначе название класса (для интерфейса; в журнале боя — name)."""
        return self.state.nickname or self.definition.name

    @property
    def label(self) -> str:
        return f"{self.name}({self.uid})"

    # --- снаряжение ---

    @property
    def equipped(self) -> list[ItemDefinition]:
        return [self._items[item_id] for item_id in self.state.equipment if item_id is not None]

    @property
    def class_ids(self) -> tuple[str, ...]:
        """Классы бойца: текущий и история повышений — по ним проверяется снаряжение."""
        return tuple(dict.fromkeys((self.definition.id, *self.state.history)))

    def can_equip(self, item_id: str) -> bool:
        """Может ли боец надеть предмет: существует, слот подходит, класс разрешён."""
        item = self._items.get(item_id)
        if item is None:
            return False
        if item.slot not in self.definition.slots:
            return False
        return self._allowed(item)

    def equip(self, slot_index: int, item_id: str) -> None:
        slot = self.definition.slots[slot_index]
        item = self._items.get(item_id)
        if item is None:
            raise ValueError(f"unknown item {item_id!r}")
        if item.slot != slot:
            raise ValueError(f"item {item_id!r} does not fit slot {slot!r}")
        if not self._allowed(item):
            raise ValueError(f"item {item_id!r} is not allowed for class {self.definition.id!r}")
        self.state.equipment[slot_index] = item_id

    def reclass(self, definition: UnitDefinition) -> None:
        """Новый класс (повышение, game/promotion.py): снаряжение перекладывается по новым слотам,
        своя тактика остаётся, тактика по умолчанию — нового класса; AP и PP полные."""
        custom = self.has_custom_tactics
        kept, rejected = self._filter_by_class(self.state.equipment)
        self.rejected_equipment = rejected
        self.definition = definition
        self.state.equipment = place_equipment(definition.slots, self._items, kept, strict=False)
        if not custom:
            self.tactics = definition.tactics
        self.ap = self._full_ap()
        self.pp = Resource(self.pp_max, self.pp_max)

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
        amp = 1.5 if self.has_flag("debuff_amp") else 1.0        # Compounding Curse: дебаффы действуют в 1.5 раза сильнее
        for effect in self.effects:
            if amp != 1.0 and "debuff" in effect.definition.tags:
                for m in effect.modifiers():
                    yield m if m.op is ModOp.PERCENT_MULT else Modifier(m.stat, m.op, m.value * amp)
            else:
                yield from effect.modifiers()

    def trait(self, name: str) -> float:
        """Сумма особого свойства предметов (ITEM_TRAITS в game/definitions.py)."""
        return sum(item.trait(name) for item in self.equipped)

    def stat(self, stat: Stat) -> int:
        """Считает стат заново из всех источников; результат нигде не хранится."""
        base = self.definition.base_stat(stat, self.state.level)
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

    @property
    def ap_max(self) -> int:
        """Запас AP: класса плюс прибавки надетых предметов (кулоны UO)."""
        return max(0, self.definition.ap_max + sum(i.ap_bonus for i in self.equipped))

    @property
    def pp_max(self) -> int:
        return max(0, self.definition.pp_max + sum(i.pp_bonus for i in self.equipped))

    def _full_ap(self) -> Resource:
        ap_max = self.ap_max
        return Resource(ap_max, ap_max if AP_START is None else AP_START)

    def start_battle(self) -> None:
        self.ap = self._full_ap()
        self.pp = Resource(self.pp_max, self.pp_max)

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
