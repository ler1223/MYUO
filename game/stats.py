"""Статы и модификаторы: единый механизм для экипировки, баффов и пассивок."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping


class Stat(str, Enum):
    HP = "hp"
    PHYS_ATK = "phys_atk"
    PHYS_DEF = "phys_def"
    MAG_ATK = "mag_atk"
    MAG_DEF = "mag_def"
    INITIATIVE = "initiative"    # порядок ходов
    ACCURACY = "accuracy"        # %, множитель шанса попадания навыка
    EVASION = "evasion"          # %, вычитается из шанса попадания по юниту
    CRIT_RATE = "crit_rate"      # %, шанс крита
    CRIT_DAMAGE = "crit_damage"  # %, множитель крита (150 = x1.5)
    GUARD_RATE = "guard_rate"    # %, шанс блока физического урона


# Значения для статов, не указанных в данных класса.
STAT_DEFAULTS = {Stat.ACCURACY: 100, Stat.CRIT_DAMAGE: 150}

# Статы, от которых могут скейлиться навыки.
SCALING_STATS = (Stat.HP, Stat.PHYS_ATK, Stat.MAG_ATK, Stat.PHYS_DEF, Stat.MAG_DEF)


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

    def to_dict(self) -> dict[str, Any]:
        return {"stat": self.stat.value, "op": self.op.value, "value": self.value}


@dataclass(frozen=True)
class Scale:
    """Слагаемое скейла навыка: стат применяющего, умноженный на коэффициент."""

    stat: Stat
    coef: float = 1.0

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Scale":
        return cls(Stat(data["stat"]), data.get("coef", 1.0))

    def to_dict(self) -> dict[str, Any]:
        return {"stat": self.stat.value, "coef": self.coef}


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
