"""Неизменяемые определения предметов, навыков и пассивок."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .areas import AREA_SINGLE, AREAS
from .stats import Modifier, Scale, Stat
from .tactics import SIDES, Always, ICondition, condition_from_dict, condition_to_dict

PART_DAMAGE = "damage"
PART_HEAL = "heal"
PART_KINDS = (PART_DAMAGE, PART_HEAL)

# Категория урона определяет, какая защита цели вычитается.
PHYSICAL = "physical"   # phys_def; может быть заблокирован (guard)
MAGICAL = "magical"     # mag_def
PURE = "pure"           # игнорирует защиту и блок
CATEGORIES = (PHYSICAL, MAGICAL, PURE)

APPLY_TARGET = "target"
APPLY_SELF = "self"
APPLY_RECIPIENTS = (APPLY_TARGET, APPLY_SELF)

SCOPES = ("self", "ally", "enemy", "any")


@dataclass(frozen=True)
class ItemDefinition:
    """Предмет снаряжения. Пока надет, даёт модификаторы, навыки, пассивки и теги."""

    id: str
    name: str
    slot: str                               # тип слота, в который предмет надевается
    modifiers: tuple[Modifier, ...] = ()
    skills: tuple[str, ...] = ()            # активные навыки, доступные носителю
    passives: tuple[str, ...] = ()          # пассивки носителя
    tags: tuple[str, ...] = ()              # теги, которые получает носитель
    damage_tags: tuple[str, ...] = ()       # тип урона оружия (для частей навыков с weapon_tags)

    @classmethod
    def from_dict(cls, item_id: str, data: Mapping[str, Any]) -> "ItemDefinition":
        return cls(
            id=item_id,
            name=data.get("name", item_id),
            slot=data["slot"],
            modifiers=tuple(Modifier.from_dict(m) for m in data.get("modifiers", ())),
            skills=tuple(data.get("skills", ())),
            passives=tuple(data.get("passives", ())),
            tags=tuple(data.get("tags", ())),
            damage_tags=tuple(data.get("damage_tags", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "slot": self.slot,
            "modifiers": [m.to_dict() for m in self.modifiers],
            "skills": list(self.skills),
            "passives": list(self.passives),
            "tags": list(self.tags),
            "damage_tags": list(self.damage_tags),
        }


@dataclass(frozen=True)
class SkillPart:
    """Часть навыка: одна порция урона или лечения.

    Значение атаки = сумма (стат применяющего * коэффициент) по scaling.
    Урон = (значение атаки - защита цели) * power; лечение = значение * power.
    """

    kind: str = PART_DAMAGE
    category: str = PHYSICAL
    power: float = 1.0
    scaling: tuple[Scale, ...] = (Scale(Stat.PHYS_ATK),)
    tags: tuple[str, ...] = ()      # тип урона: режущий, огонь и т. д.
    weapon_tags: bool = False       # брать тип урона из надетого оружия (tags = запасной вариант)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SkillPart":
        kind = data.get("kind", PART_DAMAGE)
        if kind not in PART_KINDS:
            raise ValueError(f"unknown skill part kind {kind!r}")
        category = data.get("category", PHYSICAL)
        if category not in CATEGORIES:
            raise ValueError(f"unknown damage category {category!r}")
        default_stat = Stat.MAG_ATK if category == MAGICAL else Stat.PHYS_ATK
        scaling = tuple(Scale.from_dict(s) for s in data["scaling"]) if "scaling" in data else (Scale(default_stat),)
        return cls(kind, category, data.get("power", 1.0), scaling,
                   tuple(data.get("tags", ())), data.get("weapon_tags", False))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "category": self.category,
            "power": self.power,
            "scaling": [s.to_dict() for s in self.scaling],
            "tags": list(self.tags),
            "weapon_tags": self.weapon_tags,
        }


@dataclass(frozen=True)
class SkillApply:
    """Компонент навыка: эффект effect_id получает задетый юнит или сам применяющий.

    Условие проверяется после урона/лечения: для получателя "target" на каждом
    задетом юните, для "self" на основной цели навыка.
    """

    effect_id: str
    to: str = APPLY_TARGET
    condition: ICondition = Always()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SkillApply":
        to = data.get("to", APPLY_TARGET)
        if to not in APPLY_RECIPIENTS:
            raise ValueError(f"unknown effect recipient {to!r}")
        return cls(data["effect_id"], to, condition_from_dict(data.get("condition")))

    def to_dict(self) -> dict[str, Any]:
        return {"effect_id": self.effect_id, "to": self.to, "condition": condition_to_dict(self.condition)}


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    name: str
    ap_cost: int = 1
    targets: str = "enemy"                  # кого можно выбрать целью: enemy / ally / self
    area: str = AREA_SINGLE                 # кого задевает вокруг цели, см. areas.AREAS
    hits: int = 1                           # число ударов; попадание, крит и блок бросаются на каждый
    accuracy: int = 100                     # шанс попадания навыка, % (может быть больше 100)
    tags: tuple[str, ...] = ()              # вид навыка: ближний, дальний, магия
    parts: tuple[SkillPart, ...] = ()       # урон и лечение; пусто = навык поддержки
    bonus_vs: tuple[tuple[str, float], ...] = ()  # (тег цели, множитель урона)
    ap_restore: int = 0                     # сколько AP получает каждый задетый юнит
    pp_restore: int = 0                     # сколько PP получает каждый задетый юнит
    applies: tuple[SkillApply, ...] = ()    # накладываемые эффекты, число не ограничено
    # Требования для применения (задел): проверяются до тактик, в интерфейсе пока не редактируются.
    requires_self: ICondition = Always()
    requires_target: ICondition = Always()

    @classmethod
    def from_dict(cls, skill_id: str, data: Mapping[str, Any]) -> "SkillDefinition":
        targets = data.get("targets", "enemy")
        if targets not in SIDES:
            raise ValueError(f"skill {skill_id}: unknown targets {targets!r}")
        area = data.get("area", AREA_SINGLE)
        if area not in AREAS:
            raise ValueError(f"skill {skill_id}: unknown area {area!r}")
        hits = data.get("hits", 1)
        if hits < 1:
            raise ValueError(f"skill {skill_id}: hits must be at least 1")
        try:
            parts = tuple(SkillPart.from_dict(p) for p in data.get("parts", ()))
        except ValueError as error:
            raise ValueError(f"skill {skill_id}: {error}") from None
        return cls(
            id=skill_id,
            name=data.get("name", skill_id),
            ap_cost=data.get("ap_cost", 1),
            targets=targets,
            area=area,
            hits=hits,
            accuracy=data.get("accuracy", 100),
            tags=tuple(data.get("tags", ())),
            parts=parts,
            bonus_vs=tuple((tag, mult) for tag, mult in data.get("bonus_vs", {}).items()),
            ap_restore=data.get("ap_restore", 0),
            pp_restore=data.get("pp_restore", 0),
            applies=tuple(SkillApply.from_dict(a) for a in data.get("applies", ())),
            requires_self=condition_from_dict(data.get("requires_self")),
            requires_target=condition_from_dict(data.get("requires_target")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ap_cost": self.ap_cost,
            "targets": self.targets,
            "area": self.area,
            "hits": self.hits,
            "accuracy": self.accuracy,
            "tags": list(self.tags),
            "parts": [p.to_dict() for p in self.parts],
            "bonus_vs": dict(self.bonus_vs),
            "ap_restore": self.ap_restore,
            "pp_restore": self.pp_restore,
            "applies": [a.to_dict() for a in self.applies],
            "requires_self": condition_to_dict(self.requires_self),
            "requires_target": condition_to_dict(self.requires_target),
        }


@dataclass(frozen=True)
class PassiveDefinition:
    """Реакция на событие: при срабатывании эффект effect_id накладывается на владельца."""

    id: str
    name: str
    trigger: str   # имя класса события, например "UnitDied"
    scope: str     # чьё событие: self / ally / enemy / any
    pp_cost: int
    effect_id: str

    @classmethod
    def from_dict(cls, passive_id: str, data: Mapping[str, Any]) -> "PassiveDefinition":
        scope = data.get("scope", "any")
        if scope not in SCOPES:
            raise ValueError(f"passive {passive_id}: unknown scope {scope!r}")
        return cls(
            id=passive_id,
            name=data.get("name", passive_id),
            trigger=data["trigger"],
            scope=scope,
            pp_cost=data.get("pp_cost", 0),
            effect_id=data["effect_id"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "trigger": self.trigger, "scope": self.scope,
                "pp_cost": self.pp_cost, "effect_id": self.effect_id}
