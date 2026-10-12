"""Окно прототипа (pygame-ce): бой и редакторы. Только прямоугольники и текст.

Запуск: python demo_pygame.py [seed]
Вкладки: F1 бой, F2 отряды, F3 тактики, F4 конструктор навыков. Язык переключается
кнопкой справа сверху.
Экран боя делает sim.step() и рисует полученные события; в логику боя не вмешивается.
Редакторы меняют расстановку (app.setup), бой каждый раз идёт на её копии.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Union

import pygame

from game.battle import BattleSimulation
from game.database import Database
from game.events import BattleEnded, DamageDealt, Event, Healed, RoundStarted, TurnStarted, format_event
from game.i18n import Translator, available_languages
from game.save import DEFAULT_SETUP_PATH, clone_scenario, load_settings, load_setup, save_setup
from game.scenario import Scenario, build_demo
from game.squad import Formation, Squad
from game.unit import Unit
from pygame_editors import SkillEditor, SquadEditor, TacticsEditor
from pygame_ui import BG, DIM, GREEN, HEIGHT, PANEL, RED, SLOT, TEXT, UI, WIDTH, YELLOW, fit, load_fonts

FPS = 60
AUTO_STEP_MS = 600
POPUP_MS = 900
POPUP_RISE = 34
LOG_LINES = 8

TABS = ("Battle", "Squads", "Tactics", "Skills")
TAB_BATTLE, TAB_SQUADS, TAB_TACTICS, TAB_SKILLS = range(4)
TAB_KEYS = {pygame.K_F1: TAB_BATTLE, pygame.K_F2: TAB_SQUADS, pygame.K_F3: TAB_TACTICS, pygame.K_F4: TAB_SKILLS}
TAB_W = 112
LANG_RECT = pygame.Rect(8 + len(TABS) * (TAB_W + 4) + 8, 4, 44, 24)

# Раскладка поля боя
CENTER_X = WIDTH // 2
CENTER_GAP = 18
GRID_TOP = 52
CELL_W, CELL_H = 155, 122
CARD_W, CARD_H = 145, 112
LOG_TOP = GRID_TOP + CELL_H * Formation.COLS + 12
LOG_LINE_H = 18
PIP = 10

HP_BACK = (70, 40, 40)
AP_COLOR = (90, 160, 240)
PP_COLOR = (190, 120, 235)
DEAD_FILL = (58, 58, 62)
DEAD_TEXT = (120, 120, 125)
SIDE_FILL = {"left": (44, 62, 92), "right": (96, 52, 52)}


@dataclass
class Popup:
    uid: int
    text: str
    color: tuple[int, int, int]
    born: int


class BattleView:
    """Состояние отображения боя: строится только из событий симуляции."""

    def __init__(self, db: Database, seed: int, scenario_factory: Callable[[], Scenario]):
        self.db = db
        self.scenario_factory = scenario_factory
        self.restart(seed)

    def restart(self, seed: int) -> None:
        scenario = self.scenario_factory()
        self.seed = seed
        self.sim = BattleSimulation(scenario.player_squad, scenario.enemy_squad, self.db, seed=seed)
        self.log: list[Event] = []  # последние события; текст строится при отрисовке на текущем языке
        self.popups: list[Popup] = []
        self.current_uid: Optional[int] = None
        self.round = 0
        self.ended: Optional[BattleEnded] = None

    def step(self, now: int) -> None:
        self.consume(self.sim.step(), now)

    def consume(self, events: list[Event], now: int) -> None:
        for ev in events:
            if isinstance(ev, RoundStarted):
                self.round = ev.round
            elif isinstance(ev, TurnStarted):
                self.current_uid = ev.unit
            elif isinstance(ev, DamageDealt):
                self.popups.append(Popup(ev.target, f"-{ev.amount}", RED, now))
            elif isinstance(ev, Healed):
                self.popups.append(Popup(ev.target, f"+{ev.amount}", GREEN, now))
            elif isinstance(ev, BattleEnded):
                self.current_uid = None
                self.ended = ev
        self.log = (self.log + events)[-LOG_LINES:]

    def prune(self, now: int) -> None:
        self.popups = [p for p in self.popups if now - p.born < POPUP_MS]


class App:
    """Редактируемая расстановка, бой на её копии, текущая вкладка и язык."""

    def __init__(self, db: Database, seed: int, save_path: Union[str, Path, None], lang: Optional[str] = None):
        self.db = db
        self.save_path = Path(save_path) if save_path else None
        self.message = ""
        self.dirty = False
        self.tab = TAB_BATTLE
        self.t = Translator()
        self.setup = self._load_setup(lang)
        self.view = BattleView(db, seed, lambda: clone_scenario(self.db, self.setup))
        self.squads = SquadEditor()
        self.tactics = TacticsEditor()
        self.skills = SkillEditor()

    def _load_setup(self, lang: Optional[str]) -> Scenario:
        scenario = None
        if self.save_path and self.save_path.exists():
            try:
                scenario = load_setup(self.save_path, self.db)
                lang = lang or load_settings(self.save_path).get("language")
            except (OSError, ValueError, KeyError, TypeError) as error:  # JSONDecodeError = ValueError
                self.message = f"save ignored ({error}); demo setup loaded"
        if lang in available_languages():
            self.t = Translator.load(lang)
        if scenario is not None:
            self.message = self.t("loaded {file}", file=self.save_path.name)
        return scenario or build_demo(self.db)

    # --- интерфейс для редакторов ---

    def changed(self) -> None:
        self.dirty = True
        self.message = ""

    def units(self) -> list[Unit]:
        return list(self.setup.player.units.values()) + list(self.setup.enemy.units.values())

    def label(self, unit: Unit) -> str:
        return f"{self.t(unit.name)}({unit.uid})"

    def next_uid(self) -> int:
        return max((u.uid for u in self.units()), default=0) + 1

    def reset_setup(self) -> None:
        """Демо-отряды и тактики по умолчанию; свои навыки остаются."""
        self.setup = build_demo(self.db)
        self.changed()
        self.message = self.t("demo squads and default tactics restored")

    # --- язык, вкладки, сохранение ---

    def next_language(self) -> None:
        languages = available_languages()
        self.t = Translator.load(languages[(languages.index(self.t.lang) + 1) % len(languages)])
        self._save()

    def _save(self) -> bool:
        if not self.save_path:
            return False
        try:
            save_setup(self.save_path, self.db, self.setup, {"language": self.t.lang})
            return True
        except OSError as error:
            self.message = f"{self.t('cannot save')}: {error}"
            return False

    def commit(self) -> None:
        """Сохраняет правки и перезапускает бой с тем же seed."""
        if not self.dirty:
            return
        self.dirty = False
        self.view.restart(self.view.seed)
        if self._save():
            self.message = self.t("saved to {file}, battle restarted", file=self.save_path.name)

    def switch(self, tab: int) -> None:
        if tab != self.tab:
            self.tab = tab
            self.skills.focus = False
            self.commit()


def cell_rect(side: str, row: int, col: int) -> pygame.Rect:
    """Передний ряд (row 0) ближе к центру, колонки формации идут по вертикали."""
    if side == "left":
        x = CENTER_X - CENTER_GAP - (row + 1) * CELL_W
    else:
        x = CENTER_X + CENTER_GAP + row * CELL_W
    y = GRID_TOP + col * CELL_H
    return pygame.Rect(x + (CELL_W - CARD_W) // 2, y + (CELL_H - CARD_H) // 2, CARD_W, CARD_H)


def draw_pips(screen, font, label: str, current: int, maximum: int, color, x: int, y: int, text_color) -> None:
    screen.blit(font.render(label, True, text_color), (x, y - 2))
    for i in range(maximum):
        rect = pygame.Rect(x + 26 + i * (PIP + 3), y, PIP, PIP)
        if i < current:
            pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, color, rect, 1)


def draw_unit(ui: UI, unit: Unit, rect: pygame.Rect, side: str, is_current: bool) -> None:
    screen, t = ui.screen, ui.t
    font, small = ui.fonts["main"], ui.fonts["small"]
    alive = unit.is_alive
    text_color = TEXT if alive else DEAD_TEXT
    pygame.draw.rect(screen, SIDE_FILL[side] if alive else DEAD_FILL, rect)
    pygame.draw.rect(screen, YELLOW if is_current else DIM, rect, 3 if is_current else 1)

    x, y = rect.x + 6, rect.y + 4
    title = fit(font, f"{t(unit.name)}({unit.uid}) L{unit.state.level}", CARD_W - 12)
    screen.blit(font.render(title, True, text_color), (x, y))

    bar = pygame.Rect(x, y + 22, CARD_W - 12, 14)
    pygame.draw.rect(screen, HP_BACK if alive else DEAD_FILL, bar)
    max_hp = max(1, unit.max_hp)
    fill = bar.copy()
    fill.width = round(bar.width * unit.hp / max_hp)
    pygame.draw.rect(screen, GREEN if unit.hp * 3 > max_hp else RED, fill)
    pygame.draw.rect(screen, DIM, bar, 1)
    hp_text = small.render(f"{unit.hp}/{unit.max_hp}", True, TEXT if alive else DEAD_TEXT)
    screen.blit(hp_text, hp_text.get_rect(center=bar.center))

    ap_color = AP_COLOR if alive else DEAD_TEXT
    pp_color = PP_COLOR if alive else DEAD_TEXT
    draw_pips(screen, small, "AP", unit.ap.current, unit.ap.max, ap_color, x, y + 44, text_color)
    draw_pips(screen, small, "PP", unit.pp.current, unit.pp.max, pp_color, x, y + 60, text_color)

    if alive:
        names = [t(e.definition.name) + (f" x{e.stacks}" if e.stacks > 1 else "") for e in unit.effects]
    else:
        names = [t("dead")]
    line = fit(small, ", ".join(names), CARD_W - 12)
    screen.blit(small.render(line, True, YELLOW if alive else DEAD_TEXT), (x, y + 78))


def draw_squad(ui: UI, squad: Squad, side: str, current_uid: Optional[int]) -> dict[int, pygame.Rect]:
    rects: dict[int, pygame.Rect] = {}
    for row in range(Formation.ROWS):
        for col in range(Formation.COLS):
            rect = cell_rect(side, row, col)
            unit = squad.formation.unit_at(row, col)
            if unit is None:
                pygame.draw.rect(ui.screen, SLOT, rect, 1)
                continue
            draw_unit(ui, unit, rect, side, unit.uid == current_uid)
            rects[unit.uid] = rect
    return rects


def draw_battle(ui: UI, view: BattleView, autoplay: bool, now: int) -> None:
    screen, t = ui.screen, ui.t
    font, small, big = ui.fonts["main"], ui.fonts["small"], ui.fonts["big"]
    sim = view.sim

    status = t("Round {n}   seed {seed}", n=view.round, seed=view.seed)
    if view.ended:
        winner = view.ended.winner_id
        result = t("{winner} wins", winner=t(winner)) if winner else t("draw")
        status += f"   {result.upper()}"
    status_img = font.render(status, True, YELLOW if view.ended else TEXT)
    screen.blit(status_img, (WIDTH - status_img.get_width() - 12, 8))

    screen.blit(font.render(f"A: {t(sim.attacker.name)}", True, TEXT), (12, 31))
    title = font.render(f"B: {t(sim.defender.name)}", True, TEXT)
    screen.blit(title, (WIDTH - title.get_width() - 12, 31))
    auto = t("on") if autoplay else t("off")
    hint = small.render(t("SPACE step   A auto [{auto}]   R restart   ESC quit", auto=auto), True, DIM)
    screen.blit(hint, hint.get_rect(midtop=(CENTER_X, 33)))

    rects = draw_squad(ui, sim.attacker, "left", view.current_uid)
    rects.update(draw_squad(ui, sim.defender, "right", view.current_uid))

    # Всплывающие числа: несколько чисел над одним юнитом разносим по горизонтали.
    shown: dict[int, int] = {}
    for popup in view.popups:
        rect = rects.get(popup.uid)
        if rect is None:
            continue
        index = shown.get(popup.uid, 0)
        shown[popup.uid] = index + 1
        progress = (now - popup.born) / POPUP_MS
        img = big.render(popup.text, True, popup.color)
        pos = (rect.x + 40 + index * 50, rect.y - 4 - round(POPUP_RISE * progress))
        outline = big.render(popup.text, True, BG)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            screen.blit(outline, (pos[0] + dx, pos[1] + dy))
        screen.blit(img, pos)

    panel = pygame.Rect(8, LOG_TOP, WIDTH - 16, HEIGHT - LOG_TOP - 8)
    pygame.draw.rect(screen, PANEL, panel)
    pygame.draw.rect(screen, DIM, panel, 1)
    name = lambda uid: f"{t(sim.units[uid].name)}({uid})"
    lines = [format_event(ev, name, t).strip() for ev in view.log] or [t("Press SPACE to step or A to autoplay.")]
    for i, line in enumerate(lines):
        color = TEXT if i == len(lines) - 1 else DIM
        screen.blit(small.render(fit(small, line, panel.width - 16), True, color),
                    (panel.x + 8, panel.y + 6 + i * LOG_LINE_H))


def draw_frame(ui: UI, app: App, autoplay: bool, now: int) -> None:
    ui.t = app.t
    t = ui.t
    ui.screen.fill(BG)
    target = None
    for i, name in enumerate(TABS):
        if ui.button(f"F{i + 1} {t(name)}", pygame.Rect(8 + i * (TAB_W + 4), 4, TAB_W, 24), selected=i == app.tab):
            target = i
    switch_language = ui.button(app.t.lang.upper(), LANG_RECT)

    if app.tab == TAB_BATTLE:
        draw_battle(ui, app.view, autoplay, now)
    else:
        editor = {TAB_SQUADS: app.squads, TAB_TACTICS: app.tactics, TAB_SKILLS: app.skills}[app.tab]
        editor.draw(ui, app)
        note = app.message or (t("unsaved changes: open the Battle tab to apply and save") if app.dirty else "")
        ui.text(note, 16, HEIGHT - 26, YELLOW, "small", WIDTH - 32)

    if switch_language:
        app.next_language()
    if target is not None:
        app.switch(target)


def main(seed: int = 1, autoplay: bool = False, max_frames: Optional[int] = None,
         save_path: Union[str, Path, None] = DEFAULT_SETUP_PATH, lang: Optional[str] = None) -> None:
    """max_frames нужен только для проверки запуска без окна (SDL_VIDEODRIVER=dummy).

    save_path=None отключает загрузку и сохранение расстановки.
    lang=None берёт язык из сохранения (или английский).
    """
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Squad auto-battle prototype")
    ui = UI(screen, load_fonts())
    clock = pygame.time.Clock()
    app = App(Database.load(), seed, save_path, lang)
    view = app.view
    last_step = 0
    frames = 0
    running = True

    while running:
        now = pygame.time.get_ticks()
        events = pygame.event.get()
        ui.begin(events)
        for event in events:
            if event.type == pygame.QUIT:
                running = False
            elif event.type != pygame.KEYDOWN:
                continue
            elif event.key == pygame.K_ESCAPE:
                running = False
            elif event.key in TAB_KEYS:
                app.switch(TAB_KEYS[event.key])
            elif app.tab == TAB_SKILLS:
                app.skills.key(event)
            elif app.tab != TAB_BATTLE:
                continue
            elif event.key == pygame.K_SPACE:
                view.step(now)
                last_step = now
            elif event.key == pygame.K_a:
                autoplay = not autoplay
                last_step = now - AUTO_STEP_MS
            elif event.key == pygame.K_r:
                view.restart(view.seed + 1)

        if app.tab == TAB_BATTLE and autoplay and not view.sim.finished and now - last_step >= AUTO_STEP_MS:
            view.step(now)
            last_step = now

        view.prune(now)
        draw_frame(ui, app, autoplay, now)
        pygame.display.flip()
        clock.tick(FPS)
        frames += 1
        if max_frames is not None and frames >= max_frames:
            running = False

    app.commit()  # сохранить несохранённые правки при выходе
    pygame.quit()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
