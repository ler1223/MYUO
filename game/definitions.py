"""Неизменяемые определения предметов, навыков и пассивок."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .areas import AREA_SINGLE, AREAS
from .stats import Modifier
from .tactics import SIDES, Always, ICondition, condition_from_dict, condition_to_dict

SKILL_DAMAGE = "damage"
SKILL_HEAL = "heal"
SKILL_SUPPORT = "support"  # без урона и лечения, только эффекты и восстановление AP/PP
SKILL_KINDS = (SKILL_DAMAGE, SKILL_HEAL, SKILL_SUPPORT)

# На кого навык нацелен, если в данных не указано иначе.
DEFAULT_TARGETS = {SKILL_DAMAGE: "enemy", SKILL_HEAL: "ally", SKILL_SUPPORT: "ally"}

APPLY_TARGET = "target"
APPLY_SELF = "self"
APPLY_RECIPIENTS = (APPLY_TARGET, APPLY_SELF)

SCOPES = ("self", "ally", "enemy", "any")


@dataclass(frozen=True)
class ItemDefinition:
    """Предмет снаряжения. Пока экипирован, даёт модификаторы, навыки и пассивки."""

    id: str
    name: str
    slot: str                               # тип слота, в который предмет надевается
    modifiers: tuple[Modifier, ...] = ()
    skills: tuple[str, ...] = ()            # активные навыки, доступные носителю
    passives: tuple[str, ...] = ()          # пассивки носителя

    @classmethod
    def from_dict(cls, item_id: str, data: Mapping[str, Any]) -> "ItemDefinition":
        return cls(
            id=item_id,
            name=data.get("name", item_id),
            slot=data["slot"],
            modifiers=tuple(Modifier.from_dict(m) for m in data.get("modifiers", ())),
            skills=tuple(data.get("skills", ())),
            passives=tuple(data.get("passives", ())),
        )


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
    ap_cost: int = 0
    power: float = 1.0
    kind: str = SKILL_DAMAGE                # "damage" | "heal" | "support"
    targets: str = "enemy"                  # кого можно выбрать целью: enemy / ally / self
    area: str = AREA_SINGLE                 # кого задевает вокруг цели, см. areas.AREAS
    ap_restore: int = 0                     # сколько AP получает каждый задетый юнит
    pp_restore: int = 0                     # сколько PP получает каждый задетый юнит
    applies: tuple[SkillApply, ...] = ()    # накладываемые эффекты, число не ограничено

    @classmethod
    def from_dict(cls, skill_id: str, data: Mapping[str, Any]) -> "SkillDefinition":
        """Эффекты задаются списком "applies"; "effect_id" = короткая запись одного эффекта на цель."""
        kind = data.get("kind", SKILL_DAMAGE)
        if kind not in SKILL_KINDS:
            raise ValueError(f"skill {skill_id}: unknown kind {kind!r}")
        targets = data.get("targets", DEFAULT_TARGETS[kind])
        if targets not in SIDES:
            raise ValueError(f"skill {skill_id}: unknown targets {targets!r}")
        area = data.get("area", AREA_SINGLE)
        if area not in AREAS:
            raise ValueError(f"skill {skill_id}: unknown area {area!r}")
        applies = [SkillApply.from_dict(a) for a in data.get("applies", ())]
        if data.get("effect_id") is not None:
            applies.insert(0, SkillApply(data["effect_id"]))
        return cls(
            id=skill_id,
            name=data.get("name", skill_id),
            ap_cost=data.get("ap_cost", 0),
            power=data.get("power", 1.0),
            kind=kind,
            targets=targets,
            area=area,
            ap_restore=data.get("ap_restore", 0),
            pp_restore=data.get("pp_restore", 0),
            applies=tuple(applies),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ap_cost": self.ap_cost,
            "power": self.power,
            "kind": self.kind,
            "targets": self.targets,
            "area": self.area,
            "ap_restore": self.ap_restore,
            "pp_restore": self.pp_restore,
            "applies": [a.to_dict() for a in self.applies],
        }


@dataclass(frozen=True)
class SkillBinding:
    """Кому доступен навык из конструктора: типам юнитов и носителям предметов."""

    units: tuple[str, ...] = ()
    items: tuple[str, ...] = ()


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
