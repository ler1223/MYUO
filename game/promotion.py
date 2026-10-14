"""Повышение класса: боец на нужном уровне становится другим классом и сохраняет всё прежнее.

Класс перечисляет пути в данных: "promotions": [{"class": "paladin", "level": 10}, ...]. Путей может
быть несколько, и в один класс можно прийти разными путями. Поэтому наследование считается не по
дереву классов, а по истории самого бойца (UnitState.history — классы до повышений, по порядку):

  навыки и пассивки — все, что были у прежних классов, плюс свои (уровень открытия — меньший);
  особенности (теги) — все;
  слоты — каждого типа столько, сколько было больше всего у одного из классов (надетое не слетает);
  AP и PP — наибольшие;
  статы — у каждого стата на уровне бойца наибольшее значение среди классов истории и нового
          (UnitDefinition.base_stat), поэтому повышение никогда не ослабляет;
  уровень и опыт сохраняются; тактика по умолчанию — нового класса, своя тактика бойца остаётся.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping, Optional, Sequence

from .unit import Promotion, Unit, UnitDefinition

if TYPE_CHECKING:
    from .database import Database


def _union(lists: Sequence[Sequence[str]]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for items in lists:
        for item in items:
            seen.setdefault(item, None)
    return tuple(seen)


def _levels(chain: Sequence[UnitDefinition], ids: Sequence[str], attr: str, owned: str) -> Mapping[str, int]:
    """Уровень открытия: наименьший среди классов, у которых навык есть."""
    levels = {}
    for entry in ids:
        level = min(getattr(d, attr).get(entry, 1) for d in chain if entry in getattr(d, owned))
        if level > 1:
            levels[entry] = level
    return MappingProxyType(levels)


def _slots(chain: Sequence[UnitDefinition]) -> tuple[str, ...]:
    """Слоты нового класса и недостающие слоты прежних (каждого типа — наибольшее число)."""
    slots = list(chain[-1].slots)
    have = Counter(slots)
    for definition in reversed(chain[:-1]):
        for slot, count in Counter(definition.slots).items():
            for _ in range(count - have[slot]):
                slots.append(slot)
            have[slot] = max(have[slot], count)
    return tuple(slots)


def merged_definition(chain: Sequence[UnitDefinition]) -> UnitDefinition:
    """Класс бойца с историей: chain — от первого класса к текущему."""
    current = chain[-1]
    if len(chain) == 1:
        return current
    order = [*chain[:-1], current]                     # унаследованное — первым, своё — после
    skills = _union([d.skills for d in order])
    passives = _union([d.passives for d in order])
    return replace(
        current,
        skills=skills, skill_levels=_levels(order, skills, "skill_levels", "skills"),
        passives=passives, passive_levels=_levels(order, passives, "passive_levels", "passives"),
        tags=_union([d.tags for d in order]),
        slots=_slots(order),
        ap_max=max(d.ap_max for d in order),
        pp_max=max(d.pp_max for d in order),
        ancestors=tuple(chain[:-1]),
    )


def available(unit: Unit, db: Optional["Database"] = None) -> list[Promotion]:
    """Пути повышения, открытые бойцу на его уровне (и существующие в справочнике, если он дан)."""
    return [p for p in unit.definition.promotions
            if p.level <= unit.state.level and (db is None or p.class_id in db.units)]


def promote(db: "Database", unit: Unit, class_id: str) -> None:
    """Повысить бойца в class_id (путь должен быть открыт). Боец меняется на месте: тот же объект
    остаётся в армии и строю; HP — полное, AP и PP — полные."""
    if class_id not in {p.class_id for p in available(unit, db)}:
        raise ValueError(f"{unit.definition.id} cannot be promoted to {class_id!r} at level {unit.state.level}")
    history = [*unit.state.history, unit.definition.id]
    unit.reclass(db.definition_for(class_id, history))
    unit.state.history = history
    unit.state.definition_id = class_id
    unit.state.current_hp = unit.max_hp
