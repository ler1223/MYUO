"""Окно прототипа (pygame-ce): бой и редакторы. Только прямоугольники и текст.

Запуск: python demo_pygame.py [seed]
Вкладки переключаются клавишами F1, F2, ... или кликом; язык кнопкой справа от вкладок.
Бой показывают две вкладки: Battle (карточки) и Arena (спрайты юнитов).
Экран боя делает sim.step() и рисует полученные события; в логику боя не вмешивается.
Редакторы меняют справочник (app.db, папка data/) и расстановку (app.setup);
бой каждый раз идёт на копии расстановки.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Union

import pygame

from game.battle import BattleSimulation
from game.database import Database
from game.events import BattleEnded, DamageDealt, Event, Healed, RoundStarted, SkillUsed, TurnStarted, format_event
from game.i18n import Translator, available_languages
from game.save import DEFAULT_SETUP_PATH, clone_scenario, load_settings, load_setup, save_setup
from game.scenario import Scenario, build_demo
from game.squad import Formation, Squad
from game.unit import Unit
from pygame_arena import ArenaScreen
from pygame_data_editors import ClassEditor
from pygame_effect_editor import AreaEditor, EffectEditor
from pygame_editors import SkillEditor, SquadEditor, TacticsEditor
from pygame_item_editors import ItemEditor, TagEditor
from pygame_passive_editor import PassiveEditor
from pygame_ui import BG, DIM, GREEN, HEIGHT, PANEL, RED, SLOT, TEXT, UI, WIDTH, YELLOW, fit, load_fonts

FPS = 60
AUTO_STEP_MS = 600
POPUP_MS = 900
SETTLE_MS = 250             # пауза после последнего события шага
TIMELINE_KEEP_MS = 3000     # сколько хранить показанные события (эффектам хватает)
# Сколько длится показ события, прежде чем показывать следующее (по имени класса события).
BEAT_MS = {
    "SkillUsed": 380, "DamageDealt": 110, "AttackMissed": 110, "Healed": 110, "Covered": 200,
    "EffectApplied": 60, "EffectExpired": 40, "ResourceGained": 60, "PassiveTriggered": 120,
    "UnitDied": 250, "RoundStarted": 450, "TurnSkipped": 200,
}
POPUP_RISE = 34
LOG_LINES = 8

TAB_BATTLE = 0
LANG_W = 44          # кнопка языка справа от вкладок
FIRST_TAB_KEY = pygame.K_F1

# Раскладка поля боя
CENTER_X = WIDTH // 2
CENTER_GAP = 18
GRID_TOP = 52
SIDE_W, SIDE_H = 465, 366     # место под поле одного отряда; клетки делят его поровну
LOG_TOP = GRID_TOP + SIDE_H + 12
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
        self.actions: dict[int, tuple[str, int]] = {}  # uid -> (id последнего навыка, когда применён): для анимации
        self.current_uid: Optional[int] = None
        self.round = 0
        self.ended: Optional[BattleEnded] = None
        # Расписание проигрывания: шаг боя мгновенный, а события показываются по очереди.
        self.timeline: list[tuple[int, Event]] = []
        self.busy_until = 0

    def step(self, now: int) -> None:
        self.consume(self.sim.step(), now)

    def schedule(self, events: list[Event], now: int) -> list[int]:
        """Время показа каждого события: замах, полёт снаряда, удары по очереди, гибель."""
        cursor = max(now, self.busy_until - SETTLE_MS)
        times = []
        for ev in events:
            times.append(cursor)
            cursor += BEAT_MS.get(type(ev).__name__, 0)
        self.busy_until = cursor + SETTLE_MS
        return times

    def consume(self, events: list[Event], now: int) -> None:
        times = self.schedule(events, now)
        self.timeline.extend(zip(times, events))
        for when, ev in zip(times, events):
            self._consume_one(ev, when)
        self.log = (self.log + events)[-LOG_LINES:]

    def _consume_one(self, ev: Event, now: int) -> None:
        """Состояние для вкладки с карточками; now это время показа события."""
        if isinstance(ev, RoundStarted):
            self.round = ev.round
        elif isinstance(ev, TurnStarted):
            self.current_uid = ev.unit
        elif isinstance(ev, SkillUsed):
            self.actions[ev.user] = (ev.skill_id, now)
        elif isinstance(ev, DamageDealt):
            self.popups.append(Popup(ev.target, f"-{ev.amount}" + ("!" if ev.crit else ""), RED, now))
        elif isinstance(ev, Healed):
            self.popups.append(Popup(ev.target, f"+{ev.amount}" + ("!" if ev.crit else ""), GREEN, now))
        elif isinstance(ev, BattleEnded):
            self.current_uid = None
            self.ended = ev

    def prune(self, now: int) -> None:
        # Всплывающие числа живут POPUP_MS с момента показа (он может быть в будущем).
        self.popups = [p for p in self.popups if now - p.born < POPUP_MS]
        self.timeline = [(when, ev) for when, ev in self.timeline if now - when < TIMELINE_KEEP_MS]


class App:
    """Справочник, редактируемая расстановка, бой на её копии, вкладки и язык."""

    def __init__(self, db: Database, seed: int, save_path: Union[str, Path, None], lang: Optional[str] = None):
        self.db = db
        self.save_path = Path(save_path) if save_path else None
        self.message = ""
        self.dirty = False        # есть несохранённые правки расстановки или данных
        self.data_dirty = False   # менялся справочник: его надо записать в data/
        self.tab = TAB_BATTLE
        self.t = Translator()
        self.resolution: tuple[int, int] = (WIDTH, HEIGHT)   # размер окна; сохраняется вместе с языком
        self.setup = self._load_setup(lang)
        self.view = BattleView(db, seed, lambda: clone_scenario(self.db, self.setup))
        # (название вкладки, экран); у вкладки боя с карточками экрана нет
        self.tabs: list[tuple[str, Any]] = [
            ("Battle", None),
            ("Squads", SquadEditor()),
            ("Tactics", TacticsEditor()),
            ("Skills", SkillEditor()),
            ("Classes", ClassEditor()),
            ("Items", ItemEditor()),
            ("Tags", TagEditor()),
            ("Passives", PassiveEditor()),
            ("Effects", EffectEditor()),
            ("Areas", AreaEditor()),
            ("Arena", ArenaScreen()),
        ]

    def _load_setup(self, lang: Optional[str]) -> Scenario:
        scenario = None
        if self.save_path and self.save_path.exists():
            try:
                scenario = load_setup(self.save_path, self.db)
                settings = load_settings(self.save_path)
                lang = lang or settings.get("language")
                if settings.get("resolution"):
                    self.resolution = tuple(settings["resolution"])
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

    def data_changed(self) -> None:
        """Справочник изменился: юниты расстановки пересобираются по новым определениям."""
        self.setup = clone_scenario(self.db, self.setup)
        for unit in self.units():
            unit.state.current_hp = unit.max_hp
        self.data_dirty = True
        self.changed()

    def units(self) -> list[Unit]:
        return list(self.setup.player.units.values()) + list(self.setup.enemy.units.values())

    def label(self, unit: Unit) -> str:
        return f"{self.t(unit.name)}({unit.uid})"

    def next_uid(self) -> int:
        return max((u.uid for u in self.units()), default=0) + 1

    def reset_setup(self) -> None:
        """Демо-отряды и тактики по умолчанию; справочник не трогается."""
        try:
            self.setup = build_demo(self.db)
        except (KeyError, ValueError) as error:  # демо-классы или предметы могли удалить
            self.message = f"{self.t('cannot build the demo squads')}: {error}"
            return
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
            if self.data_dirty:
                self.db.save()
                self.data_dirty = False
            save_setup(self.save_path, self.db, self.setup, {"language": self.t.lang, "resolution": list(self.resolution)})
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
            self.message = self.t("saved, battle restarted")

    def on_battle_tab(self) -> bool:
        """Открыта ли вкладка, показывающая бой (карточки или спрайты)."""
        screen = self.tabs[self.tab][1]
        return screen is None or getattr(screen, "is_battle", False)

    def switch(self, tab: int) -> None:
        if tab != self.tab and 0 <= tab < len(self.tabs):
            self.tab = tab
            self.commit()


RESOLUTIONS = ((1000, 620), (1280, 794), (1440, 893), (1600, 992), (1920, 1190), (2560, 1587))


class Window:
    """Окно любого размера: интерфейс рисуется в логическом размере WIDTH x HEIGHT и
    масштабируется с сохранением пропорций; поле арены рисуется прямо в окно, чётко."""

    def __init__(self, size: tuple[int, int]):
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.resize(size)

    def resize(self, size: tuple[int, int]) -> None:
        self.surface = pygame.display.set_mode(size, pygame.RESIZABLE)
        w, h = self.surface.get_size()
        self.scale = min(w / WIDTH, h / HEIGHT)
        self.offset = ((w - WIDTH * self.scale) / 2, (h - HEIGHT * self.scale) / 2)

    def to_logical(self, pos: tuple[int, int]) -> tuple[int, int]:
        return (int((pos[0] - self.offset[0]) / self.scale), int((pos[1] - self.offset[1]) / self.scale))

    def logical_event(self, event: pygame.event.Event) -> pygame.event.Event:
        """Событие мыши с координатами в логических пикселях интерфейса."""
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            data = dict(event.dict, pos=self.to_logical(event.pos))
            return pygame.event.Event(event.type, data)
        return event

    def present(self) -> None:
        """Интерфейс в окно: масштаб с сохранением пропорций, по краям чёрные поля."""
        self.surface.fill((0, 0, 0))
        size = (round(WIDTH * self.scale), round(HEIGHT * self.scale))
        image = self.canvas if size == self.canvas.get_size() else pygame.transform.smoothscale(self.canvas, size)
        self.surface.blit(image, (round(self.offset[0]), round(self.offset[1])))

    @staticmethod
    def presets() -> list[tuple[int, int]]:
        """Размеры окна, которые помещаются на экран."""
        desktop = pygame.display.get_desktop_sizes()[0] if pygame.display.get_init() else (10 ** 5, 10 ** 5)
        fitting = [r for r in RESOLUTIONS if r[0] <= desktop[0] and r[1] <= desktop[1] - 60]
        return fitting or [RESOLUTIONS[0]]


def cell_rect(formation: Formation, side: str, row: int, col: int) -> pygame.Rect:
    """Передний ряд (row 0) ближе к центру, колонки формации идут по вертикали."""
    cell_w, cell_h = SIDE_W // formation.rows, SIDE_H // formation.cols
    if side == "left":
        x = CENTER_X - CENTER_GAP - (row + 1) * cell_w
    else:
        x = CENTER_X + CENTER_GAP + row * cell_w
    return pygame.Rect(x + 5, GRID_TOP + col * cell_h + 5, cell_w - 10, cell_h - 10)


def draw_pips(screen, font, label: str, current: int, maximum: int, color, x: int, y: int, text_color) -> None:
    screen.blit(font.render(label, True, text_color), (x, y - 2))
    for i in range(maximum):
        rect = pygame.Rect(x + 26 + i * (PIP + 3), y, PIP, PIP)
        if i < current:
            pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, color, rect, 1)


def draw_unit(ui: UI, unit: Unit, rect: pygame.Rect, side: str, is_current: bool) -> None:
    """Карточка юнита. На большом поле карточки мельче, и нижние строки в них не рисуются."""
    screen, t = ui.screen, ui.t
    small = ui.fonts["small"]
    font = ui.fonts["main"] if rect.width >= 130 else small
    alive = unit.is_alive
    text_color = TEXT if alive else DEAD_TEXT
    pygame.draw.rect(screen, SIDE_FILL[side] if alive else DEAD_FILL, rect)
    pygame.draw.rect(screen, YELLOW if is_current else DIM, rect, 3 if is_current else 1)

    inner = rect.width - 12
    x, y = rect.x + 6, rect.y + 4
    title = fit(font, f"{t(unit.name)}({unit.uid}) L{unit.state.level}", inner)
    screen.blit(font.render(title, True, text_color), (x, y))

    bar = pygame.Rect(x, y + 22, inner, 14)
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
    if rect.height >= 62:
        draw_pips(screen, small, "AP", unit.ap.current, unit.ap.max, ap_color, x, y + 44, text_color)
    if rect.height >= 80:
        draw_pips(screen, small, "PP", unit.pp.current, unit.pp.max, pp_color, x, y + 60, text_color)
    if rect.height >= 98:
        if alive:
            names = [t(e.definition.name) + (f" x{e.stacks}" if e.stacks > 1 else "") for e in unit.effects]
        else:
            names = [t("dead")]
        line = fit(small, ", ".join(names), inner)
        screen.blit(small.render(line, True, YELLOW if alive else DEAD_TEXT), (x, y + 78))


def draw_squad(ui: UI, squad: Squad, side: str, current_uid: Optional[int]) -> dict[int, pygame.Rect]:
    rects: dict[int, pygame.Rect] = {}
    formation = squad.formation
    for row in range(formation.rows):
        for col in range(formation.cols):
            rect = cell_rect(formation, side, row, col)
            unit = formation.unit_at(row, col)
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
    screen.blit(status_img, status_img.get_rect(midtop=(CENTER_X, 31)))

    screen.blit(font.render(f"A: {t(sim.attacker.name)}", True, TEXT), (12, 31))
    title = font.render(f"B: {t(sim.defender.name)}", True, TEXT)
    screen.blit(title, (WIDTH - title.get_width() - 12, 31))

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
        pos = (rect.x + min(40, rect.width // 4) + index * 50, rect.y - 4 - round(POPUP_RISE * progress))
        outline = big.render(popup.text, True, BG)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            screen.blit(outline, (pos[0] + dx, pos[1] + dy))
        screen.blit(img, pos)

    panel = pygame.Rect(8, LOG_TOP, WIDTH - 16, HEIGHT - LOG_TOP - 8)
    pygame.draw.rect(screen, PANEL, panel)
    pygame.draw.rect(screen, DIM, panel, 1)
    auto = t("on") if autoplay else t("off")
    hint = small.render(t("SPACE step   A auto [{auto}]   R restart   ESC quit", auto=auto), True, DIM)
    screen.blit(hint, (panel.right - hint.get_width() - 8, panel.y + 6))
    name = lambda uid: f"{t(sim.units[uid].name)}({uid})"
    lines = [format_event(ev, name, t).strip() for ev in view.log] or [t("Press SPACE to step or A to autoplay.")]
    for i, line in enumerate(lines):
        color = TEXT if i == len(lines) - 1 else DIM
        width = panel.width - 16 - (hint.get_width() + 16 if i == 0 else 0)
        screen.blit(small.render(fit(small, line, width), True, color), (panel.x + 8, panel.y + 6 + i * LOG_LINE_H))


def language_rect(app: App) -> pygame.Rect:
    return pygame.Rect(WIDTH - LANG_W - 8, 4, LANG_W, 24)


def tab_width(app: App) -> int:
    """Вкладки делят ширину окна поровну, оставляя место кнопке языка."""
    return (WIDTH - 16 - LANG_W - 8) // len(app.tabs) - 4


def draw_frame(ui: UI, app: App, autoplay: bool, now: int, window: Optional[Window] = None) -> None:
    """Кадр интерфейса в ui.screen. С окном (window) он масштабируется в окно, а поле арены
    рисуется поверх прямо в окно в полном разрешении."""
    ui.t = app.t
    t = ui.t
    ui.screen.fill(BG)
    target = None
    for i, (name, _) in enumerate(app.tabs):
        width = tab_width(app)
        if ui.button(f"F{i + 1} {t(name)}", pygame.Rect(8 + i * (width + 4), 4, width, 24), selected=i == app.tab):
            target = i
    switch_language = ui.button(app.t.lang.upper(), language_rect(app))

    editor = app.tabs[app.tab][1]
    if editor is None:
        draw_battle(ui, app.view, autoplay, now)
    elif app.on_battle_tab():
        editor.native = window is not None
        editor.draw_battle(ui, app.view, autoplay, now, POPUP_MS, POPUP_RISE)
    else:
        editor.draw(ui, app)
        note = app.message or (t("unsaved changes: open the Battle or Arena tab to apply and save") if app.dirty else "")
        ui.text(note, 16, HEIGHT - 26, YELLOW, "small", WIDTH - 32)
    ui.end()
    if window is not None:
        window.present()
        if app.on_battle_tab() and hasattr(editor, "draw_field"):
            editor.draw_field(window.surface, now, editor.camera(window.scale, window.offset))

    if switch_language:
        app.next_language()
    if target is not None:
        app.switch(target)


def main(seed: int = 1, autoplay: bool = False, max_frames: Optional[int] = None,
         save_path: Union[str, Path, None] = DEFAULT_SETUP_PATH, lang: Optional[str] = None,
         data_dir: Union[str, Path, None] = None) -> None:
    """max_frames нужен только для проверки запуска без окна (SDL_VIDEODRIVER=dummy).

    save_path=None отключает загрузку и сохранение (в том числе запись справочника).
    lang=None берёт язык из сохранения (или английский). data_dir: папка данных вместо data/.
    """
    pygame.init()
    pygame.display.set_caption("Squad auto-battle prototype")
    pygame.display.set_mode((WIDTH, HEIGHT))
    app = App(Database.load(data_dir), seed, save_path, lang)
    window = Window(app.resolution)
    ui = UI(window.canvas, load_fonts())
    ui.transform = window.to_logical
    clock = pygame.time.Clock()
    view = app.view
    last_step = 0
    frames = 0
    running = True

    while running:
        now = pygame.time.get_ticks()
        events = [window.logical_event(e) for e in pygame.event.get()]
        ui.begin(events)
        arena = app.tabs[app.tab][1] if app.on_battle_tab() else None
        for event in events:
            if arena is not None and hasattr(arena, "handle_event") and not ui.captured:
                mouse = event.pos if hasattr(event, "pos") else ui.mouse
                arena.handle_event(event, mouse, window.scale)
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                window.resize(event.size)
                app.resolution = window.surface.get_size()
            elif event.type != pygame.KEYDOWN or ui.captured:
                continue  # пока открыт список или идёт ввод, клавиши достаются им
            elif event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_F12:                    # следующий размер окна
                presets = Window.presets()
                current = window.surface.get_size()
                bigger = [r for r in presets if r[0] > current[0]]
                window.resize(bigger[0] if bigger else presets[0])
                app.resolution = window.surface.get_size()
            elif 0 <= event.key - FIRST_TAB_KEY < len(app.tabs):
                app.switch(event.key - FIRST_TAB_KEY)
            elif not app.on_battle_tab():
                continue
            elif event.key == pygame.K_SPACE:
                view.step(now)
                last_step = now
            elif event.key == pygame.K_a:
                autoplay = not autoplay
                last_step = now - AUTO_STEP_MS
            elif event.key == pygame.K_r:
                view.restart(view.seed + 1)

        ready = now - last_step >= AUTO_STEP_MS and now >= view.busy_until   # эффекты прошлого шага доиграли
        if app.on_battle_tab() and autoplay and not view.sim.finished and ready:
            view.step(now)
            last_step = now

        view.prune(now)
        draw_frame(ui, app, autoplay, now, window)
        pygame.display.flip()
        clock.tick(FPS)
        frames += 1
        if max_frames is not None and frames >= max_frames:
            running = False

    app.commit()  # сохранить несохранённые правки при выходе
    pygame.quit()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
