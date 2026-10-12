"""Теги и правила их взаимодействия.

Особенности классов, типы урона и сопротивления работают через один механизм:
атака несёт набор тегов (теги навыка, типа урона, оружия, эффектов и самого
атакующего), цель несёт свои теги (класс, снаряжение, эффекты), а таблица
правил решает, как совпадение тегов меняет урон и точность.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import AbstractSet, Any, Iterable, Mapping

TAG_UNIT = "unit"      # тег юнита: пехота, конница, огнестойкий
TAG_DAMAGE = "damage"  # тип урона: режущий, огонь
TAG_SKILL = "skill"    # вид навыка: ближний, дальний, магия
TAG_KINDS = (TAG_UNIT, TAG_DAMAGE, TAG_SKILL)


@dataclass(frozen=True)
class TagDefinition:
    id: str
    name: str
    kind: str = TAG_UNIT
    unblockable: bool = False  # для типов урона: блок (guard) не срабатывает

    @classmethod
    def from_dict(cls, tag_id: str, data: Mapping[str, Any]) -> "TagDefinition":
        kind = data.get("kind", TAG_UNIT)
        if kind not in TAG_KINDS:
            raise ValueError(f"tag {tag_id}: unknown kind {kind!r}")
        return cls(tag_id, data.get("name", tag_id), kind, data.get("unblockable", False))

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "unblockable": self.unblockable}


@dataclass(frozen=True)
class TagRule:
    """Если у атаки есть все теги attack и нет ни одного из attack_not,
    а у цели есть все теги target, урон и точность умножаются."""

    attack: tuple[str, ...] = ()
    attack_not: tuple[str, ...] = ()
    target: tuple[str, ...] = ()
    damage: float = 1.0
    hit: float = 1.0

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TagRule":
        return cls(
            attack=tuple(data.get("attack", ())),
            attack_not=tuple(data.get("attack_not", ())),
            target=tuple(data.get("target", ())),
            damage=data.get("damage", 1.0),
            hit=data.get("hit", 1.0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"attack": list(self.attack), "attack_not": list(self.attack_not), "target": list(self.target),
                "damage": self.damage, "hit": self.hit}

    def tags(self) -> tuple[str, ...]:
        return self.attack + self.attack_not + self.target

    def matches(self, attack_tags: AbstractSet[str], target_tags: AbstractSet[str]) -> bool:
        return (
            all(tag in attack_tags for tag in self.attack)
            and not any(tag in attack_tags for tag in self.attack_not)
            and all(tag in target_tags for tag in self.target)
        )


def rule_multipliers(
    rules: Iterable[TagRule], attack_tags: AbstractSet[str], target_tags: AbstractSet[str]
) -> tuple[float, float]:
    """(множитель урона, множитель точности): совпавшие правила перемножаются."""
    damage, hit = 1.0, 1.0
    for rule in rules:
        if rule.matches(attack_tags, target_tags):
            damage *= rule.damage
            hit *= rule.hit
    return damage, hit
