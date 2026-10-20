"""Запись боя по действиям: что показ боя (battle/) проигрывает сценой за сценой.

Бой — последовательность актов (Act). Акт — одно действие целиком: ход бойца с активным навыком,
срабатывание пассивки, урон от яда перед ходом, пропуск хода, начало и конец боя. Внутри акта —
всё, что случилось из-за него, по порядку: пассивки до удара (before), удары (strikes),
наложенные эффекты, перемены AP/PP, гибели и пассивки после удара (after) — тоже акты.
Плоские события (game.events) для журнала и совместимости собираются параллельно.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..events import Event

# Виды актов
START = "start"            # начало боя (пассивки начала — в after)
ACTIVE = "active"          # ход: активный навык
PASSIVE = "passive"        # пассивка (в before/after другого акта или в начале/конце боя)
AFFLICTION = "affliction"  # яд, ожог, восстановление перед ходом
SKIP = "skip"              # ход пропущен (заморожен, оглушён, нечем действовать)
ROUND = "round"            # начало или конец круга: только ответы на него (в after)
END = "end"                # конец боя (пассивки конца — в after)

# Исход удара
HIT, MISS, EVADE, NEGATE = "hit", "miss", "evade", "negate"


@dataclass
class Strike:
    """Один удар навыка по одному бойцу (у многоударного — каждый удар отдельно)."""

    target: int
    hit_index: int                  # номер удара навыка (0..hits-1)
    outcome: str = HIT              # hit, miss (промах), evade (уклонение навыком), negate (урон снят)
    crit: bool = False
    guard: Optional[str] = None     # small / medium / heavy — урон частично снят блоком
    damage: int = 0
    heal: int = 0
    hp: int = 0                     # HP цели после удара
    max_hp: int = 0
    died: bool = False
    thawed: bool = False            # удар разморозил цель
    covered: Optional[int] = None   # удар принят вместо этого бойца (прикрытие)


@dataclass
class Change:
    """Изменение на бойце, не связанное с уроном удара: эффект, AP/PP, лечение, снятие."""

    target: int
    kind: str                       # effect, expire, ap, pp, heal, damage, dispel
    value: int = 0                  # на сколько (AP/PP, лечение, урон)
    effect_id: str = ""
    stacks: int = 1
    current: int = 0                # итог (AP/PP, HP)


@dataclass
class Act:
    kind: str
    actor: Optional[int] = None     # кто действует (у START/END — None)
    skill_id: str = ""              # навык (ACTIVE) или пассивка (PASSIVE)
    skill_used: str = ""            # PASSIVE: навык, который пассивка применила (контратака и т. п.)
    target: Optional[int] = None    # основная цель
    targets: list[int] = field(default_factory=list)       # все задетые (после прикрытия)
    reason: str = ""                # SKIP: почему; PASSIVE: на что сработала (событие); END: итог
    ap_cost: int = 0
    pp_cost: int = 0
    hits: int = 1
    covers: list[tuple[int, int]] = field(default_factory=list)   # (защитник, прикрытый)
    strikes: list[Strike] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)
    deaths: list[int] = field(default_factory=list)
    before: list["Act"] = field(default_factory=list)
    after: list["Act"] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    winner: Optional[str] = None    # END: id победившего отряда (None — ничья)
    round: int = 0                  # круг боя, в котором был акт

    def walk(self):
        """Сам акт и все вложенные — в порядке, в котором они случились."""
        for act in self.before:
            yield from act.walk()
        yield self
        for act in self.after:
            yield from act.walk()
