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
    параметры для редактора; виды: "fraction", "flag", "effect", "tag".
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
class HpAbove:
    PARAMS: ClassVar[dict[str, str]] = {"value": "fraction"}
    value: float  # доля от max_hp, 0..1

    def check(self, actor: "Unit", candidate: "Unit") -> bool:
        return candidate.hp >= candidate.max_hp * self.value


@dataclass(frozen=True)
class IsDay:
    """Сейчас день (Battle.time_of_day; у юнита вне боя — день)."""

    def check(self, actor: "Unit", candidate: "Unit") -> bool:
        return candidate.time_of_day == "day"


@dataclass(frozen=True)
class IsNight:
    def check(self, actor: "Unit", candidate: "Unit") -> bool:
        return candidate.time_of_day == "night"


@dataclass(frozen=True)
class HasLabel:
    """Есть эффект с меткой (buff, debuff, ailment)."""
    PARAMS: ClassVar[dict[str, str]] = {"label": "label"}
    label: str

    def check(self, actor: "Unit", candidate: "Unit") -> bool:
        return any(self.label in e.definition.tags for e in candidate.effects)


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


@dataclass(frozen=True)
class HasEffect:
    PARAMS: ClassVar[dict[str, str]] = {"effect_id": "effect"}
    effect_id: str

    def check(self, actor: "Unit", candidate: "Unit") -> bool:
        return candidate.has_effect(self.effect_id)


@dataclass(frozen=True)
class HasTag:
    PARAMS: ClassVar[dict[str, str]] = {"tag": "tag"}
    tag: str

    def check(self, actor: "Unit", candidate: "Unit") -> bool:
        return self.tag in candidate.tags


@dataclass(frozen=True)
class LacksTag:
    PARAMS: ClassVar[dict[str, str]] = {"tag": "tag"}
    tag: str

    def check(self, actor: "Unit", candidate: "Unit") -> bool:
        return self.tag not in candidate.tags


# --- селекторы -------------------------------------------------------------

class Weakest:
    """Наименьшая доля HP."""

    def select(self, actor: "Unit", candidates: Sequence["Unit"], rng: random.Random) -> "Unit":
        return min(candidates, key=lambda u: u.hp / max(1, u.max_hp))


class Strongest:
    """Наибольшая атака (большая из физической и магической)."""

    def select(self, actor: "Unit", candidates: Sequence["Unit"], rng: random.Random) -> "Unit":
        return max(candidates, key=lambda u: max(u.stat(Stat.PHYS_ATK), u.stat(Stat.MAG_ATK)))


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
    "hp_above": HpAbove,
    "is_day": IsDay,
    "is_night": IsNight,
    "has_label": HasLabel,
    "has_flag": HasFlag,
    "lacks_effect": LacksEffect,
    "has_effect": HasEffect,
    "has_tag": HasTag,
    "lacks_tag": LacksTag,
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


# До переключения редакторов на новый вид (docs/uo/ABILITIES_DESIGN.md, шаг 6) правило пишется старым видом
# {"skill", "condition", "self_condition", "selector"}, если оно им точно выражается; иначе — новым
# {"skill", "conditions": [...]}. Читаются оба.
WRITE_LEGACY_WHEN_POSSIBLE = True


@dataclass(frozen=True)
class TacticRule:
    """Строка тактики: навык и до двух условий (game/conditions.py); порядок строк — приоритет."""

    skill_id: str
    conditions: tuple = ()

    @classmethod
    def of(cls, skill_id: str, condition: ICondition = Always(), self_condition: ICondition = Always(),
           selector: ITargetSelector = Frontmost()) -> "TacticRule":
        """Правило из старых частей: условие на цель, условие на себя, выбор цели."""
        from .conditions import conditions_from_legacy
        return cls(skill_id, conditions_from_legacy({
            "condition": condition_to_dict(condition), "self_condition": condition_to_dict(self_condition),
            "selector": _registry_name(SELECTORS, selector)}))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TacticRule":
        from .conditions import condition_from_data, conditions_from_legacy
        if "conditions" in data:
            return cls(data["skill"], tuple(condition_from_data(c) for c in data["conditions"]))
        return cls(data["skill"], conditions_from_legacy(data))

    def to_dict(self) -> dict[str, Any]:
        from .conditions import conditions_to_legacy
        legacy = conditions_to_legacy(self.conditions) if WRITE_LEGACY_WHEN_POSSIBLE else None
        if legacy is not None:
            return {"skill": self.skill_id, **legacy}
        return {"skill": self.skill_id, "conditions": [c.to_data() for c in self.conditions]}

    # старые части правила (для кода, ещё не знающего новый вид): первое подходящее условие каждого рода
    @property
    def condition(self) -> ICondition:
        from .conditions import LegacyCondition
        return next((c.inner for c in self.conditions if isinstance(c, LegacyCondition) and c.on == "target"), Always())

    @property
    def self_condition(self) -> ICondition:
        from .conditions import LegacyCondition
        return next((c.inner for c in self.conditions if isinstance(c, LegacyCondition) and c.on == "self"), Always())

    @property
    def selector(self) -> ITargetSelector:
        from .conditions import SELECTOR_FACTORS, LegacySelector
        for c in self.conditions:
            if isinstance(c, LegacySelector):
                return SELECTORS[c.name]()
            for name, key in SELECTOR_FACTORS.items():
                if c.key == key:
                    return SELECTORS[name]()
        return Frontmost()


@dataclass(frozen=True)
class TacticsSet:
    rules: tuple[TacticRule, ...] = ()

    @classmethod
    def from_list(cls, data: Sequence[Mapping[str, Any]]) -> "TacticsSet":
        return cls(tuple(TacticRule.from_dict(r) for r in data))

    def to_list(self) -> list[dict[str, Any]]:
        return [rule.to_dict() for rule in self.rules]

    def ordered(self, actor: "Unit") -> Sequence[TacticRule]:
        """Правила в порядке проверки (наследники могут переставлять)."""
        return self.rules

    def chosen(self, actor: "Unit", skill_id: str) -> None:
        """Бой выбрал навык по этой тактике (наследникам — запомнить)."""

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
        не хватает AP или PP, не выполнено условие на себя (правила или самого навыка)
        или не нашлось цели.
        allies включает самого actor; оба списка содержат только живых
        в порядке формации.
        """
        pools = {"enemy": enemies, "ally": allies, "self": [actor]}
        for rule in self.rules:
            skill = skills.get(rule.skill_id)
            if skill is None or not skill.affordable(actor):
                continue
            if not (skill.requires_self.check(actor, actor) and rule.self_condition.check(actor, actor)):
                continue
            candidates = [
                u for u in pools[skill.targets]
                if skill.requires_target.check(actor, u) and rule.condition.check(actor, u)
            ]
            if candidates:
                return rule.skill_id, rule.selector.select(actor, candidates, rng)
        return None
