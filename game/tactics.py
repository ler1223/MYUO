"""Тактики как данные: правило = навык + условие на себя + условие на цель + выбор цели.

Сторону цели (враг, союзник, сам юнит) задаёт навык, а не правило: лечение и
баффы нацелены на союзников, атаки на врагов.

Новое условие или селектор добавляется классом и записью в реестр
CONDITIONS / SELECTORS, существующий код при этом не меняется.
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass, is_dataclass
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Mapping, Optional, Protocol, Sequence

from .stats import Stat

if TYPE_CHECKING:
    from .definitions import SkillDefinition
    from .unit import Unit

SIDES = ("enemy", "ally", "self")


class ICondition(Protocol):
    """Проверка юнита: кандидата в цели или самого действующего.

    Необязательный атрибут класса PARAMS = {имя_параметра: вид} описывает
    параметры для редактора; виды: "fraction", "flag", "effect".
    """

    def check(self, actor: "Unit", candidate: "Unit") -> bool: ...


class ITargetSelector(Protocol):
    """Выбор одной цели из непустого списка (порядок: передний ряд первым)."""

    def select(self, actor: "Unit", candidates: Sequence["Unit"], rng: random.Random) -> "Unit": ...


# --- условия ---------------------------------------------------------------

@dataclass(frozen=True)
class Always:
    def check(self, actor: "Unit", candidate: "Unit") -> bool:
        return True


@dataclass(frozen=True)
class HpBelow:
    PARAMS: ClassVar[dict[str, str]] = {"value": "fraction"}
    value: float  # доля от max_hp, 0..1

    def check(self, actor: "Unit", candidate: "Unit") -> bool:
        return candidate.hp < candidate.max_hp * self.value


@dataclass(frozen=True)
class HasFlag:
    PARAMS: ClassVar[dict[str, str]] = {"flag": "flag"}
    flag: str

    def check(self, actor: "Unit", candidate: "Unit") -> bool:
        return candidate.has_flag(self.flag)


@dataclass(frozen=True)
class LacksEffect:
    PARAMS: ClassVar[dict[str, str]] = {"effect_id": "effect"}
    effect_id: str

    def check(self, actor: "Unit", candidate: "Unit") -> bool:
        return not candidate.has_effect(self.effect_id)


# --- селекторы -------------------------------------------------------------

class Weakest:
    """Наименьшая доля HP."""

    def select(self, actor: "Unit", candidates: Sequence["Unit"], rng: random.Random) -> "Unit":
        return min(candidates, key=lambda u: u.hp / max(1, u.max_hp))


class Strongest:
    """Наибольший ATK."""

    def select(self, actor: "Unit", candidates: Sequence["Unit"], rng: random.Random) -> "Unit":
        return max(candidates, key=lambda u: u.stat(Stat.ATK))


class Frontmost:
    def select(self, actor: "Unit", candidates: Sequence["Unit"], rng: random.Random) -> "Unit":
        return candidates[0]


class Backmost:
    def select(self, actor: "Unit", candidates: Sequence["Unit"], rng: random.Random) -> "Unit":
        return candidates[-1]


class Random:
    def select(self, actor: "Unit", candidates: Sequence["Unit"], rng: random.Random) -> "Unit":
        return rng.choice(list(candidates))


# Реестры: имя из JSON -> фабрика. Параметры условия передаются именованными аргументами.
CONDITIONS: dict[str, Callable[..., ICondition]] = {
    "always": Always,
    "hp_below": HpBelow,
    "has_flag": HasFlag,
    "lacks_effect": LacksEffect,
}

SELECTORS: dict[str, Callable[[], ITargetSelector]] = {
    "weakest": Weakest,
    "strongest": Strongest,
    "frontmost": Frontmost,
    "backmost": Backmost,
    "random": Random,
}


def _registry_name(registry: Mapping[str, Any], obj: Any) -> str:
    for name, factory in registry.items():
        if factory is type(obj):
            return name
    raise ValueError(f"{type(obj).__name__} is not registered")


def condition_from_dict(data: Optional[Mapping[str, Any]]) -> ICondition:
    """Формат: {"type": имя из CONDITIONS, ...параметры}. None = always."""
    params = dict(data or {"type": "always"})
    return CONDITIONS[params.pop("type")](**params)


def condition_to_dict(condition: ICondition) -> dict[str, Any]:
    params = asdict(condition) if is_dataclass(condition) else dict(vars(condition))
    return {"type": _registry_name(CONDITIONS, condition), **params}


@dataclass(frozen=True)
class TacticRule:
    skill_id: str
    condition: ICondition = Always()        # условие на цель
    self_condition: ICondition = Always()   # условие на самого юнита
    selector: ITargetSelector = Frontmost()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TacticRule":
        """Формат: {"skill", "condition": {...}, "self_condition": {...}, "selector"}.

        Ключ "side" из старых данных игнорируется: сторону задаёт навык.
        """
        return cls(
            skill_id=data["skill"],
            condition=condition_from_dict(data.get("condition")),
            self_condition=condition_from_dict(data.get("self_condition")),
            selector=SELECTORS[data.get("selector", "frontmost")](),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill_id,
            "self_condition": condition_to_dict(self.self_condition),
            "condition": condition_to_dict(self.condition),
            "selector": _registry_name(SELECTORS, self.selector),
        }


@dataclass(frozen=True)
class TacticsSet:
    rules: tuple[TacticRule, ...] = ()

    @classmethod
    def from_list(cls, data: Sequence[Mapping[str, Any]]) -> "TacticsSet":
        return cls(tuple(TacticRule.from_dict(r) for r in data))

    def to_list(self) -> list[dict[str, Any]]:
        return [rule.to_dict() for rule in self.rules]

    def choose(
        self,
        actor: "Unit",
        allies: Sequence["Unit"],
        enemies: Sequence["Unit"],
        rng: random.Random,
        skills: Mapping[str, "SkillDefinition"],
    ) -> Optional[tuple[str, "Unit"]]:
        """Первое правило, которое можно выполнить.

        Правило пропускается, если навыка нет в skills (юниту он недоступен),
        не хватает AP, не выполнено условие на себя или не нашлось цели.
        allies включает самого actor; оба списка содержат только живых
        в порядке формации.
        """
        pools = {"enemy": enemies, "ally": allies, "self": [actor]}
        for rule in self.rules:
            skill = skills.get(rule.skill_id)
            if skill is None or not actor.ap.can_spend(skill.ap_cost):
                continue
            if not rule.self_condition.check(actor, actor):
                continue
            candidates = [u for u in pools[skill.targets] if rule.condition.check(actor, u)]
            if candidates:
                return rule.skill_id, rule.selector.select(actor, candidates, rng)
        return None
