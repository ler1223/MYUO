"""Бой по шагам для вкладки Battle окна прототипа: правила game.combat, карточки и лог событий.

Шаг — один ход (step боя); события шага попадают в лог, урон и лечение — всплывающими числами.
Экран только читает бой; в логику не вмешивается.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from game.combat import Battle
from game.events import BattleEnded, DamageDealt, Event, Healed, RoundStarted, TurnStarted
from pygame_ui import GREEN, RED

POPUP_MS = 900              # всплывающие числа живут столько
KEEP_LOG = 8
STEP_MS = 450               # после шага следующий не раньше (автоигра)


@dataclass
class Popup:
    uid: int
    text: str
    color: tuple[int, int, int]
    born: int


class BattleLog:
    """Бой копии расстановки (scenario_factory) с seed; лог, числа, текущий боец, итог."""

    def __init__(self, db: Any, seed: int, scenario_factory: Callable[[], Any]):
        self.db = db
        self.scenario_factory = scenario_factory
        self.restart(seed)

    def restart(self, seed: int) -> None:
        scenario = self.scenario_factory()
        self.seed = seed
        self.sim = Battle(scenario.player_squad, scenario.enemy_squad, self.db, seed=seed)
        self.log: list[Event] = []
        self.popups: list[Popup] = []
        self.current_uid: Optional[int] = None
        self.round = 0
        self.ended: Optional[BattleEnded] = None
        self.busy_until = 0

    @property
    def done(self) -> bool:
        return self.sim.finished

    def step(self, now: int) -> None:
        if not self.sim.finished:
            self.consume(self.sim.step(), now)

    def flush(self, now: int) -> None:
        mark = len(self.sim.events)
        self.sim.run()
        self.consume(self.sim.events[mark:], now)

    def consume(self, events: list[Event], now: int) -> None:
        for ev in events:
            if isinstance(ev, RoundStarted):
                self.round = ev.round
            elif isinstance(ev, TurnStarted):
                self.current_uid = ev.unit
            elif isinstance(ev, DamageDealt):
                self.popups.append(Popup(ev.target, f"-{ev.amount}" + ("!" if ev.crit else ""), RED, now))
            elif isinstance(ev, Healed):
                self.popups.append(Popup(ev.target, f"+{ev.amount}" + ("!" if ev.crit else ""), GREEN, now))
            elif isinstance(ev, BattleEnded):
                self.current_uid = None
                self.ended = ev
        self.log = (self.log + events)[-KEEP_LOG:]
        self.busy_until = now + STEP_MS

    def prune(self, now: int) -> None:
        self.popups = [p for p in self.popups if now - p.born < POPUP_MS]
