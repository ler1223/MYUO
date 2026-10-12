"""Эффекты как данные: определение (статика) и активный экземпляр (состояние)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Collection, Iterator, Mapping, Optional

from .stats import Modifier


class StackRule(str, Enum):
    REFRESH = "REFRESH"  # обновить длительность, стаки не растут
    STACK = "STACK"      # +1 стак (до max_stacks) и обновить длительность
    IGNORE = "IGNORE"    # повторное наложение ничего не делает
    REPLACE = "REPLACE"  # старый экземпляр заменяется новым


@dataclass(frozen=True)
class PeriodicAction:
    """Действие в начале хода носителя. amount умножается на число стаков."""

    kind: str  # "damage" | "heal"
    amount: int


@dataclass(frozen=True)
class EffectDefinition:
    id: str
    name: str
    modifiers: tuple[Modifier, ...] = ()
    flags: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()
    duration: Optional[int] = None  # None = постоянный
    stack_rule: StackRule = StackRule.REFRESH
    max_stacks: int = 1
    periodic: tuple[PeriodicAction, ...] = ()

    @classmethod
    def from_dict(cls, effect_id: str, data: Mapping[str, Any]) -> "EffectDefinition":
        return cls(
            id=effect_id,
            name=data.get("name", effect_id),
            modifiers=tuple(Modifier.from_dict(m) for m in data.get("modifiers", ())),
            flags=frozenset(data.get("flags", ())),
            tags=frozenset(data.get("tags", ())),
            duration=data.get("duration"),
            stack_rule=StackRule(data.get("stack_rule", StackRule.REFRESH.value)),
            max_stacks=data.get("max_stacks", 1),
            periodic=tuple(PeriodicAction(p["kind"], p["amount"]) for p in data.get("periodic", ())),
        )


@dataclass
class ActiveEffect:
    """Экземпляр эффекта на юните. Ссылки на носителя намеренно нет."""

    definition: EffectDefinition
    remaining: Optional[int]
    stacks: int = 1
    source: Optional[int] = None  # uid наложившего

    @classmethod
    def new(cls, definition: EffectDefinition, source: Optional[int] = None) -> "ActiveEffect":
        return cls(definition, definition.duration, 1, source)

    def modifiers(self) -> Iterator[Modifier]:
        """Модификаторы с учётом стаков: каждый стак даёт полный набор."""
        for _ in range(self.stacks):
            yield from self.definition.modifiers

    def to_save(self) -> dict[str, Any]:
        return {
            "effect_id": self.definition.id,
            "remaining": self.remaining,
            "stacks": self.stacks,
            "source": self.source,
        }

    @classmethod
    def from_save(cls, data: Mapping[str, Any], definitions: Mapping[str, EffectDefinition]) -> "ActiveEffect":
        return cls(definitions[data["effect_id"]], data["remaining"], data["stacks"], data["source"])


def apply_effect(
    effects: list[ActiveEffect], definition: EffectDefinition, source: Optional[int] = None
) -> Optional[ActiveEffect]:
    """Накладывает эффект по правилу стакинга. Возвращает None, если наложение проигнорировано."""
    existing = next((e for e in effects if e.definition.id == definition.id), None)
    if existing is None:
        effect = ActiveEffect.new(definition, source)
        effects.append(effect)
        return effect

    rule = definition.stack_rule
    if rule is StackRule.IGNORE:
        return None
    if rule is StackRule.REPLACE:
        effect = ActiveEffect.new(definition, source)
        effects[effects.index(existing)] = effect
        return effect
    if rule is StackRule.STACK:
        existing.stacks = min(definition.max_stacks, existing.stacks + 1)
    existing.remaining = definition.duration
    return existing


def tick_effects(effects: list[ActiveEffect], skip: Collection[ActiveEffect] = ()) -> list[ActiveEffect]:
    """Уменьшает длительность временных эффектов, удаляет и возвращает истёкшие.

    Эффекты из skip (наложенные в этот же ход) не убывают.
    """
    expired: list[ActiveEffect] = []
    for effect in effects:
        if effect.remaining is None or any(effect is fresh for fresh in skip):
            continue
        effect.remaining -= 1
        if effect.remaining <= 0:
            expired.append(effect)
    for effect in expired:
        effects.remove(effect)
    return expired
