"""Опыт и уровни юнитов. Навыки и пассивки класса открываются с уровня (UnitDefinition.skill_levels)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .unit import Unit


@dataclass(frozen=True)
class ExpRules:
    """Сколько опыта даёт бой и сколько нужно на уровень.

    За каждого врага юнит получает per_enemy * factor ** (уровень врага - уровень юнита):
    враг сильнее даёт больше, слабее — меньше. Множитель зажат в [min_share, max_share].
    """

    per_level: int = 100
    per_enemy: float = 30
    factor: float = 1.25
    min_share: float = 0.2
    max_share: float = 3.0
    max_level: int = 50

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExpRules":
        rules = cls(**{key: data[key] for key in cls.__dataclass_fields__ if key in data})
        if rules.per_level < 1 or rules.max_level < 1 or not 0 <= rules.min_share <= rules.max_share:
            raise ValueError("exp rules: per_level and max_level must be positive, min_share <= max_share")
        return rules

    def to_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.__dataclass_fields__}

    def battle_exp(self, level: int, enemy_levels: Iterable[int]) -> int:
        total = 0.0
        for enemy in enemy_levels:
            share = min(self.max_share, max(self.min_share, self.factor ** (enemy - level)))
            total += self.per_enemy * share
        return round(total)


@dataclass
class LevelUp:
    """Итог начисления опыта одному юниту."""

    uid: int
    exp: int                     # сколько опыта получено
    old_level: int
    new_level: int
    skills: list[str] = field(default_factory=list)      # открытые на новых уровнях
    passives: list[str] = field(default_factory=list)

    @property
    def levels(self) -> int:
        return self.new_level - self.old_level


def grant_exp(unit: Unit, amount: int, rules: ExpRules) -> LevelUp:
    """Начисляет опыт; за раз можно получить несколько уровней. На максимальном уровне опыт не копится."""
    state, definition = unit.state, unit.definition
    result = LevelUp(unit.uid, amount, state.level, state.level)
    if state.level >= rules.max_level:
        state.exp = 0
        return result
    state.exp += amount
    while state.exp >= rules.per_level and state.level < rules.max_level:
        state.exp -= rules.per_level
        state.level += 1
    if state.level >= rules.max_level:
        state.exp = 0
    result.new_level = state.level
    old = result.old_level
    result.skills = [s for s in definition.skills_at(state.level) if s not in definition.skills_at(old)]
    result.passives = [p for p in definition.passives_at(state.level) if p not in definition.passives_at(old)]
    return result
