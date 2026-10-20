"""Вкладка Show окна прототипа: бой показом UO (battle.BattleShow) — демонстрация, свои отряды или
стычка из открытого мира.

Клавиши: R — заново (новый seed), T — режим (демо / свои отряды), 1-3 — скорость, P — пауза,
SPACE — доиграть сразу, ENTER — после стычки из мира вернуться в мир.
Нет папки игры или видеокарты — вкладка пишет об этом и ничего не рисует.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

import pygame

from battle import BattleShow
from game.save import clone_scenario
from game.scenario import DEMO_SEED, build_demo_battle
from pygame_ui import DIM, HEIGHT, TEXT, UI, WIDTH, YELLOW

FIELD = pygame.Rect(0, 32, WIDTH, HEIGHT - 32 - 28)     # поле в логических пикселях окна
MODES = ("demo", "setup")
MODE_LABELS = {"demo": "demo battle", "setup": "your squads", "world": "world encounter"}
SPEEDS = (1, 2, 4)
MAX_FRAME_MS = 50


class ShowScreen:
    is_battle = False                  # клавиши боя вкладки Battle сюда не идут: у вкладки свои

    def __init__(self, app: Any):
        self.app = app
        self.mode = MODES[0]
        self.seed = DEMO_SEED
        self.scene: Optional[str] = None
        self.show: Optional[BattleShow] = None
        self.native = False
        self.clock = 0.0
        self.speed = 1
        self.paused = False
        self._last = 0
        self.encounter: Optional[Callable[[], Any]] = None   # бой из мира: фабрика сценария
        self.on_return: Callable[[], None] = lambda: None
        self.error = ""

    # --- бой ---

    def scenario(self):
        if self.mode == "world" and self.encounter is not None:
            return self.encounter()
        if self.mode == "setup":
            return clone_scenario(self.app.db, self.app.setup)
        return build_demo_battle(self.app.db)

    def restart(self, seed: Optional[int] = None) -> None:
        self.seed = self.seed if seed is None else seed
        self.clock, self._last, self.error = 0.0, 0, ""
        try:
            scenario = self.scenario()
            self.show = BattleShow(self.app.db, scenario.player_squad, scenario.enemy_squad, self.seed, self.scene,
                                  time_of_day=scenario.time_of_day)
        except (KeyError, ValueError) as error:          # классы сценария удалили из справочника
            self.show, self.error = None, str(error)

    def start_world(self, encounter: Callable[[], Any], scene: Optional[str], on_return: Callable[[], None],
                    seed: int) -> None:
        self.mode, self.encounter, self.scene, self.on_return = "world", encounter, scene, on_return
        self.restart(seed)

    def outcome(self) -> Optional[bool]:
        """Итог стычки из мира: True — победа нападавших (игрока), None — не доиграна."""
        show = self.show
        if show is None or not show.done(self.clock):
            return None
        return show.battle.winner_id == show.battle.attacker.id

    def leave_world(self) -> None:
        self.mode, self.encounter, self.scene = MODES[0], None, None
        self.restart(DEMO_SEED)

    # --- ввод ---

    def handle_event(self, event: pygame.event.Event, pos, window_scale: float = 1.0) -> None:
        if event.type != pygame.KEYDOWN:
            return
        key = event.key
        if key == pygame.K_r:
            self.restart(self.seed + 1)
        elif key == pygame.K_t and self.mode != "world":
            self.mode = MODES[(MODES.index(self.mode) + 1) % len(MODES)]
            self.restart(DEMO_SEED if self.mode == "demo" else self.seed)
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.speed = SPEEDS[key - pygame.K_1]
        elif key == pygame.K_p:
            self.paused = not self.paused
        elif key == pygame.K_SPACE and self.show is not None:
            self.clock = self.show.skip(self.clock)
        elif key == pygame.K_RETURN and self.mode == "world" and self.outcome() is not None:
            self.on_return()

    # --- кадр ---

    def _tick(self) -> None:
        now = pygame.time.get_ticks()
        dt = now - self._last if self._last else 0
        self._last = now
        if not self.paused:
            self.clock += min(dt, MAX_FRAME_MS) * self.speed
        if self.show is not None:
            self.show.update(self.clock)

    def draw(self, ui: UI, app: Any) -> None:
        if self.show is None and not self.error:
            self.restart()
        self._tick()
        t = ui.t
        if self.show is not None and not self.native:
            self.show.draw(ui.screen, FIELD, self.clock)
        elif self.show is None or not self.show.data.ok:
            ui.text(self.error or t("Battle show needs the game files and a GPU (see engine/uo)."),
                    FIELD.x + 16, FIELD.centery, YELLOW, "main", FIELD.width - 32)
        status = f"{t(MODE_LABELS[self.mode])}   seed {self.seed}"
        if self.show is not None:
            status += f"   {t('Round {n}', n=self.show.round)}"
            battle = self.show.battle
            if self.show.done(self.clock):
                winner = battle.winner_id
                status += "   " + (t("{winner} wins", winner=t(winner)) if winner else t("draw")).upper()
        ui.text(status, 12, HEIGHT - 24, TEXT, "small", WIDTH // 2)
        hint = "R restart  T mode  1-3 speed  P pause  SPACE skip" + ("  ENTER back" if self.mode == "world" else "")
        ui.text(t(hint), WIDTH // 2, HEIGHT - 24, DIM, "small", WIDTH // 2 - 12)

    def camera(self, window_scale: float = 1.0, window_offset: tuple[float, float] = (0, 0)):
        return window_scale, window_offset

    def draw_field(self, target: pygame.Surface, now: int, cam, force: bool = False) -> None:
        """Поле в полном разрешении окна (поверх масштабированного интерфейса)."""
        if self.show is None:
            return
        scale, (ox, oy) = cam
        clip = pygame.Rect(round(ox + FIELD.x * scale), round(oy + FIELD.y * scale),
                           round(FIELD.width * scale), round(FIELD.height * scale))
        self.show.draw(target, clip, self.clock)
