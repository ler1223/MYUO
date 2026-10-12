"""Статы и модификаторы: единый механизм для экипировки, баффов и пассивок."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping


class Stat(str, Enum):
    HP = "hp"
    ATK = "atk"
    DEF = "def"
    SPD = "spd"


class ModOp(str, Enum):
    FLAT = "FLAT"                  # прибавка к базе
    PERCENT_ADD = "PERCENT_ADD"    # проценты складываются между собой
    PERCENT_MULT = "PERCENT_MULT"  # множители перемножаются


@dataclass(frozen=True)
class Modifier:
    stat: Stat
    op: ModOp
    value: float

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Modifier":
        return cls(Stat(data["stat"]), ModOp(data["op"]), data["value"])


def compute_stat(base: float, modifiers: Iterable[Modifier]) -> int:
    """(база + сумма FLAT) * (1 + сумма PERCENT_ADD) * произведение PERCENT_MULT.

    Модификаторы должны быть уже отфильтрованы по нужному стату.
    """
    flat = 0.0
    percent_add = 0.0
    percent_mult = 1.0
    for mod in modifiers:
        if mod.op is ModOp.FLAT:
            flat += mod.value
        elif mod.op is ModOp.PERCENT_ADD:
            percent_add += mod.value
        else:
            percent_mult *= mod.value
    return max(0, round((base + flat) * (1 + percent_add) * percent_mult))
