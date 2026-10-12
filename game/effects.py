"""Эффекты как данные: определение (статика) и активный экземпляр (состояние)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Collection, Iterator, Mapping, Optional

from .stats import Modifier, Scale


class StackRule(str, Enum):
    REFRESH = "REFRESH"  # обновить длительность, стаки не растут
    STACK = "STACK"      # +1 стак (до max_stacks) и обновить длительность
    IGNORE = "IGNORE"    # повторное наложение ничего не делает
    REPLACE = "REPLACE"  # старый экземпляр заменяется новым


# Когда срабатывает триггер эффекта.
WHEN_TURN_START = "turn_start"   # в начале хода носителя
WHEN_EXPIRE = "expire"           # когда у эффекта кончилась длительность или заряды
WHEN_APPLIED = "applied"         # когда эффект наложен (или обновлён)
TRIGGER_WHEN = (WHEN_TURN_START, WHEN_EXPIRE, WHEN_APPLIED)

# Что делает триггер.
TRIGGER_ACTIONS = ("damage", "heal", "apply_effect", "remove_effect", "restore_ap", "restore_pp")

# На кого действует: сам носитель, наложивший эффект, или юниты вокруг носителя.
TARGET_SELF = "self"
TARGET_SOURCE = "source"
TARGET_ALLIES = "allies"        # союзники носителя, кроме него самого
TARGET_ENEMIES = "enemies"
TARGET_EVERYONE = "everyone"    # все, кроме носителя
TRIGGER_TARGETS = (TARGET_SELF, TARGET_SOURCE, TARGET_ALLIES, TARGET_ENEMIES, TARGET_EVERYONE)


@dataclass(frozen=True)
class EffectTrigger:
    """Правило «когда -> что -> кому». Из таких правил собирается поведение эффекта.

    Примеры: яд = в начале хода урон себе; заразный яд = по истечении наложить
    тот же эффект союзникам в соседних клетках.
    """

    when: str
    action: str
    amount: int = 0                   # урон, лечение или AP/PP; для урона и лечения умножается на стаки
    effect_id: Optional[str] = None   # для apply_effect и remove_effect
    to: str = TARGET_SELF
    area: Optional[str] = None        # для allies/enemies/everyone: область вокруг носителя; None = вся сторона

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EffectTrigger":
        trigger = cls(data["when"], data["action"], data.get("amount", 0), data.get("effect_id") or None,
                      data.get("to", TARGET_SELF), data.get("area") or None)
        if trigger.when not in TRIGGER_WHEN:
            raise ValueError(f"unknown trigger moment {trigger.when!r}")
        if trigger.action not in TRIGGER_ACTIONS:
            raise ValueError(f"unknown trigger action {trigger.action!r}")
        if trigger.to not in TRIGGER_TARGETS:
            raise ValueError(f"unknown trigger target {trigger.to!r}")
        if trigger.action in ("apply_effect", "remove_effect") and trigger.effect_id is None:
            raise ValueError(f"trigger action {trigger.action!r} needs an effect")
        return trigger

    def to_dict(self) -> dict[str, Any]:
        return {"when": self.when, "action": self.action, "amount": self.amount, "effect_id": self.effect_id,
                "to": self.to, "area": self.area}


@dataclass(frozen=True)
class AttackMod:
    """Как эффект меняет навыки носителя (например, зачарование оружия)."""

    add_tags: tuple[str, ...] = ()        # теги, добавляемые атаке (тип урона и т. п.)
    power_mult: float = 1.0               # множитель урона и лечения
    add_scaling: tuple[Scale, ...] = ()   # дополнительные слагаемые скейла каждой части
    accuracy_add: int = 0                 # прибавка к шансу попадания, %
    crit_add: int = 0                     # прибавка к шансу крита, %
    skill_tag: Optional[str] = None       # действует только на навыки с этим тегом; None = на все

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AttackMod":
        return cls(
            add_tags=tuple(data.get("add_tags", ())),
            power_mult=data.get("power_mult", 1.0),
            add_scaling=tuple(Scale.from_dict(s) for s in data.get("add_scaling", ())),
            accuracy_add=data.get("accuracy_add", 0),
            crit_add=data.get("crit_add", 0),
            skill_tag=data.get("skill_tag"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "add_tags": list(self.add_tags),
            "power_mult": self.power_mult,
            "add_scaling": [s.to_dict() for s in self.add_scaling],
            "accuracy_add": self.accuracy_add,
            "crit_add": self.crit_add,
            "skill_tag": self.skill_tag,
        }


@dataclass(frozen=True)
class EffectDefinition:
    id: str
    name: str
    modifiers: tuple[Modifier, ...] = ()
    flags: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()           # метки самого эффекта (buff/debuff) для dispel
    grants_tags: tuple[str, ...] = ()            # теги, которые получает носитель
    attack_mods: tuple[AttackMod, ...] = ()      # изменения навыков носителя
    duration: Optional[int] = None               # ходов; None = постоянный
    charges: Optional[int] = None                # на сколько применений навыков хватает attack_mods
    stack_rule: StackRule = StackRule.REFRESH
    max_stacks: int = 1
    triggers: tuple[EffectTrigger, ...] = ()     # поведение: когда -> что -> кому

    @classmethod
    def from_dict(cls, effect_id: str, data: Mapping[str, Any]) -> "EffectDefinition":
        try:
            triggers = [EffectTrigger.from_dict(t) for t in data.get("triggers", ())]
        except ValueError as error:
            raise ValueError(f"effect {effect_id}: {error}") from None
        # Старая запись "periodic" = урон или лечение себе в начале хода.
        triggers += [EffectTrigger(WHEN_TURN_START, p["kind"], p["amount"]) for p in data.get("periodic", ())]
        return cls(
            id=effect_id,
            name=data.get("name", effect_id),
            modifiers=tuple(Modifier.from_dict(m) for m in data.get("modifiers", ())),
            flags=frozenset(data.get("flags", ())),
            tags=frozenset(data.get("tags", ())),
            grants_tags=tuple(data.get("grants_tags", ())),
            attack_mods=tuple(AttackMod.from_dict(m) for m in data.get("attack_mods", ())),
            duration=data.get("duration"),
            charges=data.get("charges"),
            stack_rule=StackRule(data.get("stack_rule", StackRule.REFRESH.value)),
            max_stacks=data.get("max_stacks", 1),
            triggers=tuple(triggers),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "modifiers": [m.to_dict() for m in self.modifiers],
            "flags": sorted(self.flags),
            "tags": sorted(self.tags),
            "grants_tags": list(self.grants_tags),
            "attack_mods": [m.to_dict() for m in self.attack_mods],
            "duration": self.duration,
            "charges": self.charges,
            "stack_rule": self.stack_rule.value,
            "max_stacks": self.max_stacks,
            "triggers": [t.to_dict() for t in self.triggers],
        }


@dataclass
class ActiveEffect:
    """Экземпляр эффекта на юните. Ссылки на носителя намеренно нет."""

    definition: EffectDefinition
    remaining: Optional[int]
    stacks: int = 1
    source: Optional[int] = None    # uid наложившего
    charges: Optional[int] = None   # оставшиеся заряды attack_mods

    @classmethod
    def new(cls, definition: EffectDefinition, source: Optional[int] = None) -> "ActiveEffect":
        return cls(definition, definition.duration, 1, source, definition.charges)

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
            "charges": self.charges,
        }

    @classmethod
    def from_save(cls, data: Mapping[str, Any], definitions: Mapping[str, EffectDefinition]) -> "ActiveEffect":
        return cls(definitions[data["effect_id"]], data["remaining"], data["stacks"], data["source"],
                   data.get("charges"))


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
    existing.charges = definition.charges
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
