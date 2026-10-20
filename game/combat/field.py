"""Поле боя: два отряда, ряды и колонки, кого навык может достать и кого выбрать целью.

Правила (справка UO, «Battle Rows», «Default Targeting»):
- ряд 0 — передний, остальные — задние. Пока в переднем ряду кто-то стоит, ближние навыки достают
  только его; дальние (стрелы), магия и пронзающие (по колонке) — любой ряд;
- по умолчанию атака выбирает врага прямо напротив (та же колонка), иначе ближайшего по колонке,
  передний ряд раньше заднего; поровну — случайно. Навыки на союзников — ближайшего в переднем ряду;
- условия тактики с приоритетом (меньше HP и т. п.) меняют порядок: передний ряд первым, в нём от
  дальней колонки к ближней, затем задний так же; из них — лучший по приоритету.
"""
from __future__ import annotations

import random
from typing import Optional, Sequence

from ..areas import AreaDefinition
from ..definitions import SkillDefinition
from ..squad import Squad
from ..tactics import Frontmost
from ..unit import Unit

REACH_TAGS = ("ranged", "magic")           # навыки этих видов достают задний ряд
PIERCE_AREAS = ("column", "pierce")        # пронзающие: колонка задевает оба ряда — тоже достают


class Side:
    """Отряд на поле: index 0 — нападающий (слева), 1 — защищающийся (справа)."""

    def __init__(self, squad: Squad, index: int):
        self.squad = squad
        self.index = index
        self.units: list[Unit] = list(squad.formation.units)

    @property
    def id(self) -> str:
        return self.squad.id

    def pos(self, unit: Unit) -> tuple[int, int]:
        return self.squad.formation.position_of(unit.uid) or (0, 0)

    def alive(self) -> list[Unit]:
        return [u for u in self.units if u.is_alive]

    def front_row(self) -> Optional[int]:
        rows = [self.pos(u)[0] for u in self.alive()]
        return min(rows) if rows else None

    def hp_share(self) -> float:
        """Остаток HP отряда долей (итог боя без разгрома)."""
        total = sum(max(1, u.max_hp) for u in self.units)
        return sum(max(0, u.hp) for u in self.units) / max(1, total)

    def has(self, unit: Unit) -> bool:
        return any(u is unit for u in self.units)


def reaches_back(skill: SkillDefinition) -> bool:
    return any(tag in skill.tags for tag in REACH_TAGS) or skill.area in PIERCE_AREAS


def can_revive(skill: SkillDefinition) -> bool:
    """Навык поднимает павшего союзника (game/definitions.py SkillExtras.revive)."""
    return skill.extras.revive


def reachable(skill: SkillDefinition, actor: Unit, own: Side, other: Side) -> list[Unit]:
    """Кого навык может выбрать целью."""
    if skill.targets == "self":
        return [actor] if actor.is_alive else []
    if skill.targets == "ally":
        if can_revive(skill):                 # воскрешение — только павшие союзники
            return [u for u in own.units if not u.is_alive]
        return own.alive()
    units = other.alive()
    if reaches_back(skill):
        return units
    front = other.front_row()
    return [u for u in units if other.pos(u)[0] == front]


def default_order(actor: Unit, own: Side, side: Side, candidates: Sequence[Unit], rng: random.Random) -> list[Unit]:
    """Порядок по умолчанию: та же колонка, затем ближайшие колонки; передний ряд раньше; поровну —
    случайно."""
    col = own.pos(actor)[1]
    tie = {u.uid: rng.random() for u in candidates}
    return sorted(candidates, key=lambda u: (abs(side.pos(u)[1] - col), side.pos(u)[0], tie[u.uid]))


def priority_order(actor: Unit, own: Side, side: Side, candidates: Sequence[Unit]) -> list[Unit]:
    """Порядок для условий с приоритетом: передний ряд первым, в ряду от дальней колонки к ближней."""
    col = own.pos(actor)[1]
    return sorted(candidates, key=lambda u: (side.pos(u)[0], -abs(side.pos(u)[1] - col)))


def pick_target(rule_selector, actor: Unit, own: Side, side: Side, candidates: Sequence[Unit],
                rng: random.Random) -> Unit:
    """Цель из подходящих: по умолчанию (Frontmost) — как в UO, иначе приоритет тактики."""
    if isinstance(rule_selector, Frontmost):
        return default_order(actor, own, side, candidates, rng)[0]
    ordered = priority_order(actor, own, side, candidates)
    return rule_selector.select(actor, ordered, rng)


def affected(skill: SkillDefinition, area: AreaDefinition, target: Unit, side: Side) -> list[Unit]:
    """Кого задевает навык с опорной целью target: живые в области вокруг неё."""
    anchor = side.pos(target)
    hit = [u for u in side.alive() if area.covers(anchor, side.pos(u))]
    if target in hit:                     # основная цель — первой
        hit.remove(target)
        hit.insert(0, target)
    return hit


def around(owner: Unit, side: Side, area: Optional[AreaDefinition]) -> list[Unit]:
    """Живые свои в области вокруг владельца (None — вся сторона)."""
    if area is None:
        return side.alive()
    anchor = side.pos(owner)
    return [u for u in side.alive() if area.covers(anchor, side.pos(u))]
