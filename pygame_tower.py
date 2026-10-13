"""Окно бесконечной башни (pygame-ce). Запуск: python tower.py

Отдельная программа, не вкладка демо: свой забег (saves/tower.json), общий справочник data/.
Перед каждым боем и по F5 справочник, правила башни (data/tower.json) и визуал навыков
перечитываются с диска, поэтому правки, сделанные в открытом рядом окне демо, сразу в игре.

Интерфейс рисуется в логическом размере 1920x1280 и масштабируется под окно. Экран зависит
от фазы забега: набор бойцов, подготовка (расстановка, снаряжение, тактики), бой этажа на сцене
(2.5D) с панелями отрядов, награда, магазин, конец забега. Картинки — pygame_art (заглушки
с цепочкой замены), подсказки при наведении — pygame_tips.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional, Union

import pygame

from engine.camera import Camera
from engine.scene import SCENES_DIR, SceneStore
from game.database import Database
from game.editing import set_tactics
from game.events import format_event
from game.i18n import Translator, available_languages
from game.stats import Stat
from game.tower import (DEFAULT_SAVE_PATH, DRAFT, OVER, PREPARE, REWARD, SHOP, TOWER_RULES_PATH, TowerRules,
                        TowerRun)
from game.unit import Unit
from pygame_art import ArtBank, Portraits, item_key, passive_key, skill_key, stat_key
from pygame_battle import FIELD_RECT, SKIP_BACKLOG_MS, BattleView
from pygame_editors import ROW_H, rule_table
from pygame_stage import TOWER_MODE, StageScreen, load_visuals
from pygame_tips import (PASSIVE_COLOR, SKILL_COLOR, STAT_COLORS, class_tip, item_tip, modifier_text, passive_tip,
                         skill_tip, stat_tip, tier_color, unit_tip)
from pygame_ui import DIM, FONT_NAMES, GREEN, RED, TEXT, UI, YELLOW, Window, fit, lighter

FPS = 60
AUTO_STEP_MS = 600
SPEEDS = (1, 2, 4)                       # клавиши 1, 2, 3
NONE_ITEM = "__none__"                   # в списке снаряжения: снять предмет

# Логический размер интерфейса башни и размеры окна для F12 (те, что не влезают в экран, пропускаются)
SIZE = W, H = 1920, 1280
SCALE = 1.92                             # во сколько раз крупнее базового интерфейса 1000x620
SIZES = ((1200, 800), (1440, 960), (1620, 1080), (1920, 1280), (2400, 1600))
TOP_H = 76                               # верхняя полоса
M = 24                                   # поля

# Палитра
BACK = (16, 18, 28)
PANEL = (30, 34, 50)
PANEL_DARK = (22, 25, 38)
CELL = (40, 46, 66)
CELL_EMPTY = (34, 38, 54)
GOLD = (240, 200, 70)
EXP = (110, 200, 255)
HP_BACK = (70, 36, 40)
AP_COLOR = (90, 160, 240)
PP_COLOR = (190, 120, 235)
ENEMY = (225, 90, 80)
# Цвет экрана: шапки панелей, главная кнопка, полоса под верхней строкой
ACCENTS = {DRAFT: (40, 140, 150), PREPARE: (60, 110, 190), REWARD: (190, 140, 45), SHOP: (55, 145, 85),
           OVER: (170, 60, 60), "battle": (125, 80, 175), "tactics": (90, 100, 170)}
PRIMARY = (176, 128, 36)                 # главная кнопка экрана (бой, взять, выйти)
DANGER = (150, 50, 50)


def tower_fonts() -> dict[str, pygame.font.Font]:
    return {
        "tiny": pygame.font.SysFont(FONT_NAMES, 16),
        "small": pygame.font.SysFont(FONT_NAMES, 20),
        "main": pygame.font.SysFont(FONT_NAMES, 25),
        "big": pygame.font.SysFont(FONT_NAMES, 34, bold=True),
        "title": pygame.font.SysFont(FONT_NAMES, 46, bold=True),
    }


# --- раскладка: прямоугольники, общие для отрисовки и тестов -------------------------

def draft_card(i: int) -> pygame.Rect:
    return pygame.Rect(M + i * 636, TOP_H + 96, 600, H - TOP_H - 96 - 40)


def take_button(card: pygame.Rect) -> pygame.Rect:
    return pygame.Rect(card.x + 20, card.bottom - 74, card.width - 40, 56)


LEFT = pygame.Rect(M, TOP_H + 16, 1000, H - TOP_H - 16 - M)           # подготовка: отряд
RIGHT = pygame.Rect(LEFT.right + M, TOP_H + 16, W - LEFT.right - 2 * M, LEFT.height)   # выбранный юнит
GRID = pygame.Rect(LEFT.x + 24, LEFT.y + 70, LEFT.width - 48, 600)
FIGHT = pygame.Rect(LEFT.right - 264, LEFT.bottom - 104, 240, 84)
BENCH = pygame.Rect(RIGHT.x + 260, RIGHT.y + 168, 200, 46)
TACTICS = pygame.Rect(RIGHT.x + 474, RIGHT.y + 168, 200, 46)
BACK_BUTTON = pygame.Rect(M + 24, H - M - 80, 240, 56)
REWARD_LEFT = pygame.Rect(M, TOP_H + 16, 860, H - TOP_H - 16 - M)
REWARD_RIGHT = pygame.Rect(REWARD_LEFT.right + M, TOP_H + 16, W - REWARD_LEFT.right - 2 * M, REWARD_LEFT.height)
TAKE = pygame.Rect(REWARD_RIGHT.x + 24, REWARD_RIGHT.bottom - 84, 760, 64)
RECRUITS = pygame.Rect(M, TOP_H + 16, 600, H - TOP_H - 16 - M)
GOODS = pygame.Rect(RECRUITS.right + M, TOP_H + 16, 700, RECRUITS.height)
SELL = pygame.Rect(GOODS.right + M, TOP_H + 16, W - GOODS.right - 2 * M, RECRUITS.height)
LEAVE = pygame.Rect(SELL.x + 24, SELL.bottom - 84, SELL.width - 48, 64)
REROLL = pygame.Rect(GOODS.x + 24, GOODS.bottom - 84, 340, 64)
OVER_PANEL = pygame.Rect(W // 2 - 600, TOP_H + 120, 1200, 860)
NEW_RUN = pygame.Rect(OVER_PANEL.centerx - 180, OVER_PANEL.bottom - 110, 360, 72)
# Бой: поле во всю ширину, снизу отряды и журнал
FIELD = pygame.Rect(0, TOP_H, W, round(FIELD_RECT.height * W / FIELD_RECT.width))
HUD_Y = FIELD.bottom + 10
PLAYER_HUD = pygame.Rect(12, HUD_Y, 700, H - HUD_Y - 12)
ENEMY_HUD = pygame.Rect(W - 712, HUD_Y, 700, H - HUD_Y - 12)
LOG = pygame.Rect(PLAYER_HUD.right + 12, HUD_Y, ENEMY_HUD.x - PLAYER_HUD.right - 24, H - HUD_Y - 12)
CONTINUE = pygame.Rect(W // 2 - 200, FIELD.centery + 50, 400, 70)


def reward_card(i: int) -> pygame.Rect:
    return pygame.Rect(REWARD_RIGHT.x + 24, REWARD_RIGHT.y + 80 + i * 186, REWARD_RIGHT.width - 48, 172)


def recruit_card(i: int) -> pygame.Rect:
    return pygame.Rect(RECRUITS.x + 20, RECRUITS.y + 70 + i * 356, RECRUITS.width - 40, 340)


def hire_button(card: pygame.Rect) -> pygame.Rect:
    return pygame.Rect(card.x + 230, card.bottom - 70, card.width - 250, 54)


def goods_card(i: int) -> pygame.Rect:
    return pygame.Rect(GOODS.x + 20, GOODS.y + 70 + i * 190, GOODS.width - 40, 176)


def field_scale() -> float:
    """Во сколько раз поле боя на экране башни крупнее логического поля сцены."""
    return FIELD.width / FIELD_RECT.width


def field_camera(stage: StageScreen, window: Optional[Window]) -> Camera:
    """Камера сцены, вписывающая её поле в прямоугольник FIELD (с окном — в пиксели окна)."""
    k = field_scale()
    scale, offset = (window.scale, window.offset) if window is not None else (1.0, (0.0, 0.0))
    ws = scale * k
    return stage.camera(ws, (offset[0] + FIELD.x * scale - FIELD_RECT.x * ws,
                             offset[1] + FIELD.y * scale - FIELD_RECT.y * ws))


def to_field(pos: tuple[float, float]) -> tuple[float, float]:
    """Точка экрана башни -> точка логического поля сцены."""
    k = field_scale()
    return (pos[0] - FIELD.x) / k + FIELD_RECT.x, (pos[1] - FIELD.y) / k + FIELD_RECT.y


class TowerApp:
    """Забег, справочник, картинки, сцена боя и состояние экранов."""

    def __init__(self, save_path: Union[str, Path, None] = DEFAULT_SAVE_PATH, data_dir: Union[str, Path, None] = None,
                 rules_path: Union[str, Path] = TOWER_RULES_PATH, scenes_dir: Optional[Path] = SCENES_DIR,
                 props_dir: Optional[Path] = None, lang: Optional[str] = None, seed: Optional[int] = None):
        """seed: случайность новых забегов (тесты); None — каждый забег свой."""
        self.seed = seed
        self.save_path = Path(save_path) if save_path else None
        self.data_dir, self.rules_path = data_dir, rules_path
        self.db = Database.load(data_dir)
        self.rules = TowerRules.load(rules_path)
        self.t = Translator()
        self.resolution: tuple[int, int] = SIZES[0]
        self.message = ""
        self.run = self._load(lang)
        self.art = ArtBank()
        self.store = SceneStore(scenes_dir or SCENES_DIR)
        self.stage = StageScreen(None, props_dir)
        self.portraits = Portraits(self.art, self.stage.bank)
        self.stage.mode = TOWER_MODE
        self.stage.on_return = self.finish_battle
        self.scenario: Any = None          # бой этажа, который идёт сейчас
        self.in_battle = False
        self.paused = False
        self.speed = 1
        self.clock = 0                     # время боя: идёт быстрее при ускорении, стоит на паузе
        self.last_step = 0
        self.selected: Optional[int] = None    # выбранный юнит на подготовке
        self.tactics = False                   # подготовка: показана таблица тактики выбранного
        self.picks: list[int] = []             # отмеченные предметы награды
        self.confirm_new = False               # «Новый забег» нажат один раз
        self._enemies: Any = None              # (этаж, справочник, враги этажа)
        self._tinted: dict[tuple, pygame.Surface] = {}

    # --- сохранение ---

    def _load(self, lang: Optional[str]) -> TowerRun:
        run, settings = None, {}
        if self.save_path and self.save_path.exists():
            try:
                data = json.loads(self.save_path.read_text(encoding="utf-8"))
                settings = data.get("settings", {})
                run = TowerRun.from_dict(self.db, self.rules, data)
            except (OSError, ValueError, KeyError, TypeError) as error:
                self.message = f"save ignored ({error})"
        lang = lang or settings.get("language")
        if lang in available_languages():
            self.t = Translator.load(lang)
        if settings.get("resolution"):
            self.resolution = tuple(settings["resolution"])
        return run or TowerRun.new(self.db, self.rules, seed=self.seed)

    def save(self) -> None:
        if not self.save_path:
            return
        data = self.run.to_dict()
        data["settings"] = {"language": self.t.lang, "resolution": list(self.resolution)}
        try:
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            self.save_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as error:
            self.message = f"{self.t('cannot save')}: {error}"

    def reload(self) -> bool:
        """Перечитать справочник, правила башни и визуал навыков; забег пересобирается по ним."""
        try:
            db = Database.load(self.data_dir)
            rules = TowerRules.load(self.rules_path)
            run = self.run.rebuild(db, rules)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.message = self.t("data not reloaded: {error}", error=error)
            return False
        self.db, self.rules, self.run = db, rules, run
        self.stage.skill_visuals = load_visuals()
        self._enemies = None
        return True

    def act(self, action: Any, *args: Any) -> Any:
        """Действие забега; ошибку (не хватает золота, поле полно) показывает сообщением."""
        try:
            result = action(*args)
        except ValueError as error:
            self.message = self.t(str(error))
            return None
        self.message = ""
        self.save()
        return result

    def new_run(self) -> None:
        self.run = TowerRun.new(self.db, self.rules, best=self.run.best, seed=self.seed)
        self.selected, self.tactics, self.picks, self.confirm_new = None, False, [], False
        self.message = ""
        self.save()

    def next_language(self) -> None:
        languages = available_languages()
        self.t = Translator.load(languages[(languages.index(self.t.lang) + 1) % len(languages)])
        self.save()

    def enemies(self) -> list:
        """Враги текущего этажа (для показа на подготовке); считаются раз на этаж."""
        key = (self.run.floor, id(self.db), self.run.seed)
        if self._enemies is None or self._enemies[0] != key:
            self._enemies = (key, self.run.enemy_roster(self.db))
        return self._enemies[1]

    def tinted(self, key: str, size: int, color) -> pygame.Surface:
        """Иконка, окрашенная в цвет (значки статов: одна заглушка на все, цвет у каждого свой)."""
        cache = (key, size, tuple(color))
        if cache not in self._tinted:
            image = self.art.image(key, (size, size)).copy()
            if not self.art.has_own(key):
                image.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
            self._tinted[cache] = image
        return self._tinted[cache]

    # --- бой ---

    def start_battle(self) -> None:
        self.reload()
        try:
            self.scenario = self.run.battle(self.db)
        except ValueError as error:
            self.message = self.t(str(error))
            return
        scene_id = self.rules.scene(self.run.floor)
        if scene_id in self.store.ids():
            self.stage.set_scene(self.store.load(scene_id))
        seed = self.run.seed + self.run.floor * 7919
        self.stage.battle_view = BattleView(self.db, seed, lambda: self.scenario, self.stage.windup)
        self.in_battle, self.paused, self.message = True, False, ""
        self.last_step = self.clock

    def tick(self, dt: int) -> None:
        """Время боя и автоматические ходы: следующий ход, когда эффекты прошлого доиграли."""
        if not self.in_battle:
            return
        view = self.stage.battle_view
        if not self.paused:
            self.clock += dt * self.speed
            ready = self.clock - self.last_step >= AUTO_STEP_MS and self.clock >= view.busy_until
            if not view.sim.finished and ready:
                view.step(self.clock)
                self.last_step = self.clock
        view.prune(self.clock)

    def skip(self) -> None:
        """Доиграть бой сразу: сцена перескакивает к итогу без анимаций."""
        view = self.stage.battle_view
        mark = len(view.sim.events)
        view.sim.run()
        view.consume(view.sim.events[mark:], self.clock)
        self.clock = view.busy_until + SKIP_BACKLOG_MS + 1
        self.last_step = self.clock

    def finish_battle(self) -> None:
        """Enter после боя: итог в забег, дальше награда или конец."""
        view = self.stage.battle_view
        if not self.in_battle or view is None or not view.sim.finished:
            return
        won = view.sim.winner_id == view.sim.attacker.id
        self.run.finish(self.db, self.scenario, won)
        self.in_battle, self.scenario, self.picks = False, None, []
        self.save()

    def handle_key(self, key: int) -> None:
        if key == pygame.K_F5:
            if not self.in_battle and self.reload():
                self.message = self.t("data reloaded")
        elif not self.in_battle:
            return
        elif key == pygame.K_SPACE:
            self.paused = not self.paused
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.speed = SPEEDS[key - pygame.K_1]
        elif key == pygame.K_s and not self.stage.battle_view.sim.finished:
            self.skip()

    def handle_battle_event(self, event: pygame.event.Event, pos: tuple[float, float], window_scale: float) -> None:
        """Мышь и клавиши поля сцены: координаты экрана башни переводятся в координаты поля."""
        if hasattr(event, "pos"):
            data = dict(event.dict, pos=to_field(event.pos))
            event = pygame.event.Event(event.type, data)
        self.stage.handle_event(event, to_field(pos), window_scale * field_scale())

    # --- снаряжение ---

    def change_equipment(self, unit: Unit, slot_index: int, item_id: str) -> None:
        inventory = self.run.inventory
        if item_id == NONE_ITEM:
            self.act(inventory.unequip, unit, slot_index)
        else:
            self.act(inventory.equip, unit, slot_index, item_id)

    def equip_anywhere(self, unit: Unit, item_id: str) -> None:
        """Клик по предмету инвентаря: в первый подходящий слот (пустой, иначе первый занятый)."""
        item = self.db.items.get(item_id)
        slots = [i for i, slot in enumerate(unit.definition.slots) if item is not None and slot == item.slot]
        if not slots:
            self.message = self.t("{unit} cannot wear this", unit=self.t(unit.name))
            return
        empty = [i for i in slots if unit.state.equipment[i] is None]
        self.change_equipment(unit, (empty or slots)[0], item_id)


# --- общие элементы -------------------------------------------------------------------

def panel(ui: UI, rect: pygame.Rect, accent, title: str = "", right: str = "") -> pygame.Rect:
    """Панель с цветной шапкой. Возвращает область под шапкой."""
    pygame.draw.rect(ui.screen, PANEL, rect, border_radius=10)
    head = pygame.Rect(rect.x, rect.y, rect.width, 54 if title else 8)
    pygame.draw.rect(ui.screen, accent, head, border_top_left_radius=10, border_top_right_radius=10)
    pygame.draw.rect(ui.screen, lighter(accent, -40), (head.x, head.bottom - 4, head.width, 4))
    pygame.draw.rect(ui.screen, lighter(accent, 30), rect, 2, border_radius=10)
    if title:
        ui.text(title, rect.x + 20, rect.y + 10, TEXT, "big", rect.width - 40)
    if right:
        img = ui.fonts["main"].render(right, True, TEXT)
        ui.screen.blit(img, (rect.right - img.get_width() - 20, rect.y + 14))
    return pygame.Rect(rect.x, head.bottom, rect.width, rect.bottom - head.bottom)


def bar(ui: UI, rect: pygame.Rect, value: float, maximum: float, color, back=HP_BACK, label: str = "") -> None:
    pygame.draw.rect(ui.screen, back, rect, border_radius=rect.height // 2)
    share = 0 if maximum <= 0 else max(0.0, min(1.0, value / maximum))
    if share > 0:
        pygame.draw.rect(ui.screen, color, (rect.x, rect.y, max(rect.height, round(rect.width * share)), rect.height),
                         border_radius=rect.height // 2)
    pygame.draw.rect(ui.screen, (0, 0, 0), rect, 1, border_radius=rect.height // 2)
    if label:
        font = ui.fonts["tiny"]
        img = font.render(label, True, TEXT)
        ui.screen.blit(img, img.get_rect(center=rect.center))


def framed(ui: UI, image: pygame.Surface, rect: pygame.Rect, border, back=PANEL_DARK, width: int = 3) -> None:
    pygame.draw.rect(ui.screen, back, rect, border_radius=8)
    ui.screen.blit(image, image.get_rect(center=rect.center))
    pygame.draw.rect(ui.screen, border, rect, width, border_radius=8)


def portrait(ui: UI, app: TowerApp, class_id: str, rect: pygame.Rect, border=DIM, flip: bool = False) -> None:
    image = app.portraits.portrait(class_id, min(rect.width, rect.height) - 6, flip)
    framed(ui, image, rect, border)


def item_icon(ui: UI, app: TowerApp, item_id: str, rect: pygame.Rect, count: int = 0,
              price: Optional[int] = None) -> int:
    """Иконка предмета в рамке цвета тира, с числом и подсказкой. Возвращает клик (+1/-1/0)."""
    item = app.db.items.get(item_id)
    border = tier_color(item.tier) if item else RED
    key = item_key(item) if item else "item"
    image = app.art.image(key, (rect.width - 12, rect.height - 12))
    hover = ui.hovered(rect)
    framed(ui, image, rect, lighter(border, 40) if hover else border)
    if count > 1:
        font = ui.fonts["small"]
        img = font.render(f"x{count}", True, TEXT)
        back = pygame.Rect(rect.right - img.get_width() - 10, rect.bottom - img.get_height() - 4,
                           img.get_width() + 8, img.get_height())
        pygame.draw.rect(ui.screen, (0, 0, 0), back, border_radius=4)
        ui.screen.blit(img, (back.x + 4, back.y))
    ui.tip(rect, lambda: item_tip(ui.t, app.db, item_id, price))
    return ui.clicked(rect)


def skill_chip(ui: UI, app: TowerApp, kind: str, entry_id: str, rect: pygame.Rect, unlock: int = 1,
               level: Optional[int] = None) -> None:
    """Навык или пассивка: значок, название, замок до уровня открытия; подсказка с описанием."""
    db, t = app.db, ui.t
    section = db.skills if kind == "skill" else db.passives
    locked = level is not None and unlock > level
    color = SKILL_COLOR if kind == "skill" else PASSIVE_COLOR
    pygame.draw.rect(ui.screen, CELL if not ui.hovered(rect) else lighter(CELL, 18), rect, border_radius=6)
    side = rect.height - 6
    key = skill_key(entry_id) if kind == "skill" else passive_key(entry_id)
    icon = app.art.image(key, (side, side))
    if locked:
        icon = icon.copy()
        icon.fill((90, 90, 90, 255), special_flags=pygame.BLEND_RGBA_MULT)
    ui.screen.blit(icon, (rect.x + 3, rect.y + 3))
    name = t(section[entry_id].name) if entry_id in section else entry_id
    room = rect.width - side - 18
    if locked:                                    # уровень открытия — значок справа, имя не обрезает его
        lock = ui.fonts["tiny"].render(t("lv {n}", n=unlock), True, TEXT)
        badge = pygame.Rect(rect.right - lock.get_width() - 14, rect.centery - 11, lock.get_width() + 10, 22)
        pygame.draw.rect(ui.screen, (80, 60, 60), badge, border_radius=5)
        ui.screen.blit(lock, (badge.x + 5, badge.y + 2))
        room -= badge.width + 6
    ui.text(name, rect.x + side + 12, rect.y + (rect.height - ui.fonts["small"].get_height()) // 2,
            DIM if locked else color, "small", room)
    tip = (lambda: skill_tip(t, db, entry_id, unlock, level)) if kind == "skill" \
        else (lambda: passive_tip(t, db, entry_id, unlock, level))
    ui.tip(rect, tip)


def class_entries(unit_or_definition, level: Optional[int] = None) -> list[tuple[str, str, int]]:
    """(вид, id, уровень открытия) навыков и пассивок класса по порядку."""
    definition = getattr(unit_or_definition, "definition", unit_or_definition)
    return [("skill", s, definition.skill_levels.get(s, 1)) for s in definition.skills] + \
           [("passive", p, definition.passive_levels.get(p, 1)) for p in definition.passives]


def stat_grid(ui: UI, app: TowerApp, unit: Unit, x: int, y: int, cols: int, col_w: int, row_h: int = 30) -> int:
    """Статы со значками своего цвета и подсказками. Возвращает низ сетки."""
    stats = list(Stat)
    rows = (len(stats) + cols - 1) // cols
    for i, stat in enumerate(stats):
        cx, cy = x + (i // rows) * col_w, y + (i % rows) * row_h
        color = STAT_COLORS[stat]
        icon = app.tinted(stat_key(stat), row_h - 8, color)
        ui.screen.blit(icon, (cx, cy + 4))
        ui.text(ui.t(stat.value), cx + row_h, cy + 3, DIM, "small", col_w - row_h - 70)
        value = unit.stat(stat)
        img = ui.fonts["main"].render(str(value), True, color)
        ui.screen.blit(img, (cx + col_w - img.get_width() - 16, cy + 1))
        ui.tip(pygame.Rect(cx, cy, col_w - 10, row_h), lambda s=stat, v=value: stat_tip(ui.t, s, v))
    return y + rows * row_h


def background(ui: UI, app: TowerApp, screen_name: str) -> None:
    ui.screen.blit(app.art.image(f"bg/{screen_name}", SIZE, cover=True), (0, 0))


def draw_top(ui: UI, app: TowerApp, accent) -> None:
    t, run = ui.t, app.run
    pygame.draw.rect(ui.screen, PANEL_DARK, (0, 0, W, TOP_H))
    pygame.draw.rect(ui.screen, accent, (0, TOP_H - 5, W, 5))
    boss = app.rules.is_boss(run.floor)
    ui.screen.blit(app.art.image("icon/boss" if boss else "icon/floor", (48, 48)), (M, 12))
    ui.text(t("Floor {n}", n=run.floor), M + 60, 14, ENEMY if boss else TEXT, "big")
    if boss:
        ui.text(t("(boss)"), M + 230, 22, ENEMY, "main")
    ui.screen.blit(app.art.image("icon/gold", (44, 44)), (420, 14))
    ui.text(str(run.inventory.gold), 474, 16, GOLD, "big")
    ui.tip(pygame.Rect(420, 10, 200, 56), lambda: [(t("Gold"), GOLD, "main"),
                                                   (t("Earned by winning floors, spent in the shop."), TEXT, "small")])
    ui.text(t("best floor {n}", n=run.best), 660, 24, DIM, "main")
    buttons = pygame.Rect(W - 760, 14, 280, 48), pygame.Rect(W - 466, 14, 300, 48), pygame.Rect(W - 152, 14, 128, 48)
    if ui.button(t("Reload data (F5)"), buttons[0], enabled=not app.in_battle):
        if app.reload():
            app.message = t("data reloaded")
    label = t("Sure? Click again") if app.confirm_new else t("New run")
    if ui.button(label, buttons[1], enabled=not app.in_battle, fill=DANGER if app.confirm_new else None):
        if app.confirm_new or run.phase == OVER:
            app.new_run()
        else:
            app.confirm_new = True
    if ui.button(app.t.lang.upper(), buttons[2], font="main"):
        app.next_language()


# --- набор -------------------------------------------------------------------------

def draw_draft(ui: UI, app: TowerApp) -> None:
    t, run = ui.t, app.run
    accent = ACCENTS[DRAFT]
    total = app.rules.data["draft"]["picks"]
    ui.text(t("Choose a fighter {n}/{total}", n=len(run.army.units) + 1, total=total), M, TOP_H + 20, TEXT, "title")
    taken = [u.definition.id for u in run.army.units.values()]
    for i, class_id in enumerate(taken):                      # уже взятые — портреты справа от заголовка
        portrait(ui, app, class_id, pygame.Rect(W - M - (len(taken) - i) * 84, TOP_H + 12, 76, 76), accent)
    for i, class_id in enumerate(list(run.offers)):
        if draw_class_card(ui, app, class_id, draft_card(i), accent):
            app.act(run.pick, app.db, class_id)


def draw_class_card(ui: UI, app: TowerApp, class_id: str, rect: pygame.Rect, accent) -> bool:
    """Карточка класса при наборе: фигура, статы, снаряжение, навыки. True — взяли."""
    t, db, run = ui.t, app.db, app.run
    level = app.rules.data["draft"]["level"]
    unit = db.create_unit(class_id, 0, level, run.starter_gear(db, class_id))
    body = panel(ui, rect, accent, t(unit.name), t("lv {n}", n=level))
    x, y = rect.x + 20, body.y + 14
    art = pygame.Rect(x, y, rect.width - 40, 400)
    pygame.draw.rect(ui.screen, PANEL_DARK, art, border_radius=8)
    figure = app.portraits.full(class_id, (art.width - 20, art.height - 16))
    ui.screen.blit(figure, figure.get_rect(midbottom=(art.centerx, art.bottom - 8)))
    tags = ", ".join(t(db.tags[tag].name) for tag in unit.definition.tags if tag in db.tags)
    ui.text(tags, x + 12, art.y + 10, DIM, "small", art.width - 24)
    y = stat_grid(ui, app, unit, x, art.bottom + 12, 2, (rect.width - 40) // 2, 28) + 10
    ui.text(t("Equipment"), x, y, DIM, "small")
    for i, item_id in enumerate(i for i in unit.state.equipment if i is not None):
        item_icon(ui, app, item_id, pygame.Rect(x + i * 78, y + 26, 70, 70))
    y += 108
    ui.text(t("Skills and passives"), x, y, DIM, "small")
    entries = class_entries(unit)
    for i, (kind, entry_id, unlock) in enumerate(entries[:10]):
        chip = pygame.Rect(x + (i % 2) * ((rect.width - 40) // 2), y + 26 + (i // 2) * 42, (rect.width - 40) // 2 - 8, 38)
        if chip.bottom > rect.bottom - 84:
            break
        skill_chip(ui, app, kind, entry_id, chip, unlock, level)
    return bool(ui.button(t("Take"), take_button(rect), font="big", color=TEXT, fill=PRIMARY))


# --- подготовка ---------------------------------------------------------------------

def cell_rect(app: TowerApp, row: int, col: int) -> pygame.Rect:
    """Передний ряд справа (ближе к врагу), колонны формации — по вертикали."""
    formation = app.run.squad.formation
    cell_w, cell_h = GRID.width // formation.rows, GRID.height // formation.cols
    x = GRID.x + (formation.rows - 1 - row) * cell_w
    return pygame.Rect(x + 5, GRID.y + col * cell_h + 5, cell_w - 10, cell_h - 10)


def reserve_rect(i: int) -> pygame.Rect:
    return pygame.Rect(GRID.x + (i % 4) * 238, GRID.bottom + 86 + (i // 4) * 104, 228, 96)


def unit_card(ui: UI, app: TowerApp, unit: Unit, rect: pygame.Rect, selected: bool) -> None:
    """Боец в клетке поля: портрет, имя, уровень, HP и опыт."""
    t = ui.t
    fill = lighter(CELL, 22) if selected else CELL
    pygame.draw.rect(ui.screen, fill, rect, border_radius=10)
    pygame.draw.rect(ui.screen, YELLOW if selected else lighter(ACCENTS[PREPARE], 10), rect,
                     4 if selected else 2, border_radius=10)
    side = min(rect.height - 16, 150)
    portrait(ui, app, unit.definition.id, pygame.Rect(rect.x + 8, rect.y + 8, side, side),
             YELLOW if selected else DIM)
    x = rect.x + side + 20
    width = rect.right - x - 12
    ui.text(t(unit.name), x, rect.y + 12, TEXT, "main", width)
    ui.text(t("lv {n}", n=unit.state.level), x, rect.y + 44, GOLD, "small")
    bar(ui, pygame.Rect(x, rect.y + 76, width, 18), unit.hp, unit.max_hp, GREEN, label=f"HP {unit.max_hp}")
    need = app.rules.exp.per_level
    bar(ui, pygame.Rect(x, rect.y + 102, width, 10), unit.state.exp, need, EXP, (30, 40, 60))
    ui.tip(rect, lambda: unit_tip(t, app.db, unit))


def draw_prepare(ui: UI, app: TowerApp) -> None:
    t, run, db = ui.t, app.run, app.db
    units = {u.uid: u for u in run.army.units.values()}
    if app.selected not in units:
        app.selected = run.fielded[0].uid if run.fielded else next(iter(units), None)
    if app.tactics and app.selected is not None:
        draw_tactics(ui, app, units[app.selected])
        return
    accent = ACCENTS[PREPARE]
    formation = run.squad.formation
    shop_in = next((k for k in range(1, 1000) if app.rules.shop_after(run.floor + k - 1)), None) \
        if app.rules.data["shop"]["every"] > 0 else None
    note = t("shop after {n} more floor(s)", n=shop_in) if shop_in else ""
    panel(ui, LEFT, accent, t("Squad: {n}/{max}", n=len(formation), max=formation.max_units), note)
    ui.text(t("front") + "  >>", GRID.right - 140, GRID.y - 14, lighter(accent, 60), "small")
    for row in range(formation.rows):
        for col in range(formation.cols):
            rect = cell_rect(app, row, col)
            unit = formation.unit_at(row, col)
            if unit is None:
                pygame.draw.rect(ui.screen, CELL_EMPTY, rect, border_radius=10)
                pygame.draw.rect(ui.screen, (60, 66, 90), rect, 2, border_radius=10)
            else:
                unit_card(ui, app, unit, rect, unit.uid == app.selected)
            click = ui.clicked(rect)
            if not click:
                continue
            selected = app.selected
            if unit is None:
                if selected is not None:
                    app.act(run.place, selected, row, col)           # в пустую клетку
            elif selected is None or selected == unit.uid:
                app.selected = unit.uid
            elif formation.position_of(selected) is None or click < 0:
                app.act(run.place, selected, row, col)               # из резерва — на его место; правый клик — обмен
            else:
                app.selected = unit.uid
    ui.text(t("click: select, move to an empty cell; right click: swap"), GRID.x, GRID.bottom + 12, DIM, "small")

    ui.text(t("Reserve (click a unit, then a cell)"), GRID.x, GRID.bottom + 52, TEXT, "main")
    for i, unit in enumerate(run.reserve[:8]):
        rect = reserve_rect(i)
        chosen = unit.uid == app.selected
        pygame.draw.rect(ui.screen, lighter(CELL, 22) if chosen else CELL, rect, border_radius=8)
        pygame.draw.rect(ui.screen, YELLOW if chosen else DIM, rect, 3 if chosen else 1, border_radius=8)
        portrait(ui, app, unit.definition.id, pygame.Rect(rect.x + 6, rect.y + 6, 84, 84))
        ui.text(t(unit.name), rect.x + 98, rect.y + 16, TEXT, "small", rect.width - 104)
        ui.text(t("lv {n}", n=unit.state.level), rect.x + 98, rect.y + 50, GOLD, "small")
        ui.tip(rect, lambda u=unit: unit_tip(t, db, u))
        if ui.clicked(rect):
            app.selected = unit.uid
    if len(run.reserve) > 8:
        ui.text(f"+{len(run.reserve) - 8}", GRID.right - 60, GRID.bottom + 52, DIM, "main")

    # Враги этажа
    ey = LEFT.bottom - 128
    boss = app.rules.is_boss(run.floor)
    ui.text(t("Enemies of floor {n}", n=run.floor) + ("  " + t("(boss)") if boss else ""), GRID.x, ey,
            ENEMY, "main")
    for i, (class_id, level, *_rest) in enumerate(app.enemies()):
        rect = pygame.Rect(GRID.x + i * 80, ey + 36, 72, 72)
        if class_id not in db.units:
            continue
        portrait(ui, app, class_id, rect, ENEMY if (boss and i == 0) else (120, 60, 60), flip=True)
        tag = ui.fonts["tiny"].render(str(level), True, TEXT)
        back = pygame.Rect(rect.right - tag.get_width() - 10, rect.bottom - 22, tag.get_width() + 8, 20)
        pygame.draw.rect(ui.screen, (90, 30, 30), back, border_radius=4)
        ui.screen.blit(tag, (back.x + 4, back.y + 1))
        ui.tip(rect, lambda c=class_id, lv=level: class_tip(t, db, c, lv))
    if ui.button(t("Fight!"), FIGHT, enabled=bool(run.fielded), font="title", color=TEXT, fill=PRIMARY):
        app.start_battle()

    if app.selected is not None:
        draw_unit_panel(ui, app, units[app.selected])


def draw_unit_panel(ui: UI, app: TowerApp, unit: Unit) -> None:
    """Выбранный юнит: портрет, опыт, статы, снаряжение, навыки и инвентарь."""
    t, db, run = ui.t, app.db, app.run
    accent = ACCENTS[PREPARE]
    body = panel(ui, RIGHT, lighter(accent, -20), t(unit.name), t("lv {n}", n=unit.state.level))
    x, y = RIGHT.x + 24, body.y + 16
    portrait(ui, app, unit.definition.id, pygame.Rect(x, y, 210, 210), GOLD)
    tx = x + 236
    tags = ", ".join(t(db.tags[tag].name) for tag in unit.definition.tags if tag in db.tags)
    ui.text(tags, tx, y + 4, DIM, "small", RIGHT.right - tx - 24)
    need = app.rules.exp.per_level
    ui.text(t("exp {n}/{need}", n=unit.state.exp, need=need), tx, y + 36, EXP, "small")
    bar(ui, pygame.Rect(tx, y + 64, RIGHT.right - tx - 24, 16), unit.state.exp, need, EXP, (30, 40, 60))
    fielded = run.squad.formation.position_of(unit.uid) is not None
    if ui.button(t("To reserve") if fielded else t("In reserve"), BENCH, enabled=fielded):
        app.act(run.bench, unit.uid)
    if ui.button(t("Tactics"), TACTICS, fill=ACCENTS["tactics"]):
        app.tactics = True
    y = stat_grid(ui, app, unit, x, y + 226, 2, (RIGHT.width - 48) // 2) + 12

    # Снаряжение: иконка надетого (подсказка) и список подходящего из инвентаря
    ui.text(t("Equipment"), x, y, TEXT, "main")
    y += 34
    inventory = run.inventory
    half = (RIGHT.width - 48) // 2
    for slot_index, slot in enumerate(unit.definition.slots):
        sx, sy = x + (slot_index % 2) * half, y + (slot_index // 2) * 82
        current = unit.state.equipment[slot_index]
        icon = pygame.Rect(sx, sy, 72, 72)
        if current is not None:
            item_icon(ui, app, current, icon)
        else:
            pygame.draw.rect(ui.screen, CELL_EMPTY, icon, border_radius=8)
            pygame.draw.rect(ui.screen, (60, 66, 90), icon, 2, border_radius=8)
        fits = [i for i, n in inventory.items.items() if n > 0 and i in db.items and db.items[i].slot == slot]
        options = [(NONE_ITEM, f"- {t(slot)}")] + [(i, f"{t(db.items[i].name)} x{inventory.count(i)}") for i in fits]
        if current is not None:
            options.append((current, t(db.items[current].name)))
        color = tier_color(db.items[current].tier) if current in db.items else DIM
        picked = ui.dropdown(("tower-slot", unit.uid, slot_index), pygame.Rect(sx + 82, sy + 14, half - 100, 44),
                             options, current if current is not None else NONE_ITEM, color)
        if picked is not None and picked != (current if current is not None else NONE_ITEM):
            app.change_equipment(unit, slot_index, picked)
    y += ((len(unit.definition.slots) + 1) // 2) * 82 + 6

    ui.text(t("Skills and passives"), x, y, TEXT, "main")
    entries = class_entries(unit) + [("skill", s, 1) for item in unit.equipped for s in item.skills] \
        + [("passive", p, 1) for item in unit.equipped for p in item.passives]
    for i, (kind, entry_id, unlock) in enumerate(entries[:10]):
        skill_chip(ui, app, kind, entry_id, pygame.Rect(x + (i % 2) * half, y + 34 + (i // 2) * 44, half - 10, 40),
                   unlock, unit.state.level)
    y += 34 + ((min(len(entries), 10) + 1) // 2) * 44 + 8

    ui.text(t("Inventory: click an item to put it on"), x, y, TEXT, "main")
    items = [(i, n) for i, n in sorted(inventory.items.items()) if n > 0 and i in db.items]
    per_row = (RIGHT.width - 48) // 80
    rows = max(1, (RIGHT.bottom - 16 - (y + 34)) // 80)
    for i, (item_id, count) in enumerate(items[:per_row * rows]):
        rect = pygame.Rect(x + (i % per_row) * 80, y + 34 + (i // per_row) * 80, 72, 72)
        if item_icon(ui, app, item_id, rect, count):
            app.equip_anywhere(unit, item_id)


def draw_tactics(ui: UI, app: TowerApp, unit: Unit) -> None:
    t, db = ui.t, app.db
    accent = ACCENTS["tactics"]
    area = pygame.Rect(M, TOP_H + 16, W - 2 * M, H - TOP_H - 16 - M)
    panel(ui, area, accent, t("Tactics of {unit}", unit=f"{t(unit.name)} {t('lv {n}', n=unit.state.level)}"))
    portrait(ui, app, unit.definition.id, pygame.Rect(area.right - 190, area.y + 70, 160, 160), GOLD)
    x = area.x + 24
    ui.text(t("Rules are checked top to bottom: the first one whose conditions hold,"), x, area.y + 72, DIM, "small")
    ui.text(t("with a valid target and enough AP, is used. Otherwise: Attack, if AP allows."), x, area.y + 98,
            DIM, "small")
    rules = unit.tactics.to_list()
    new_rules = rule_table(ui, db, ("tower-tactics", unit.uid), rules, unit.skill_ids, x, area.y + 140)
    y = area.y + 140 + round(20 * ui.scale) + (len(rules) + 1) * round(ROW_H * ui.scale) + 20
    if ui.button(t("Reset to default"), pygame.Rect(x, y, 360, 48), enabled=unit.has_custom_tactics):
        unit.reset_tactics()
        app.save()
    elif new_rules is not None:
        try:
            set_tactics(db, unit, new_rules)
            app.save()
        except (ValueError, KeyError) as error:
            app.message = str(error)
    ui.text(t("Available skills"), x, y + 70, TEXT, "main")
    for i, skill_id in enumerate(unit.skill_ids[:8]):
        skill_chip(ui, app, "skill", skill_id, pygame.Rect(x + (i % 4) * 440, y + 106 + (i // 4) * 48, 430, 42))
    if ui.button(t("Back"), BACK_BUTTON, font="main"):
        app.tactics = False


# --- награда ------------------------------------------------------------------------

def item_card(ui: UI, app: TowerApp, item_id: str, rect: pygame.Rect, selected: bool = False,
              price: Optional[int] = None) -> int:
    """Крупная карточка предмета: иконка, название цвета тира, статы, кому подходит."""
    t, db = ui.t, app.db
    item = db.items.get(item_id)
    pygame.draw.rect(ui.screen, lighter(CELL, 20) if selected else CELL, rect, border_radius=10)
    border = YELLOW if selected else (tier_color(item.tier) if item else RED)
    pygame.draw.rect(ui.screen, border, rect, 4 if selected else 2, border_radius=10)
    side = rect.height - 24
    item_icon(ui, app, item_id, pygame.Rect(rect.x + 12, rect.y + 12, side, side), price=price)
    if item is None:
        return ui.clicked(rect)
    x, width = rect.x + side + 30, rect.width - side - 44
    ui.text(t(item.name), x, rect.y + 12, tier_color(item.tier), "big", width)
    ui.text(f"{t(item.slot)} · {t(('novice', 'mercenary', 'hero')[min(item.tier, 3) - 1])}", x, rect.y + 54, DIM,
            "small", width)
    lines = [m for m in item.modifiers]
    for i, mod in enumerate(lines[:3]):
        color = STAT_COLORS.get(mod.stat, TEXT)
        ui.text(modifier_text(t, mod), x + (i % 2) * (width // 2), rect.y + 84 + (i // 2) * 28, color, "main",
                width // 2)
    if selected:                                  # галочка: в шрифте её может не быть, рисуется линиями
        a, b, c = (rect.right - 50, rect.y + 30), (rect.right - 38, rect.y + 44), (rect.right - 16, rect.y + 14)
        pygame.draw.lines(ui.screen, YELLOW, False, (a, b, c), 6)
    return ui.clicked(rect)


def draw_reward(ui: UI, app: TowerApp) -> None:
    t, run, db = ui.t, app.run, app.db
    report = run.report
    floor = report.floor if report else run.floor
    accent = ACCENTS[REWARD]
    body = panel(ui, REWARD_LEFT, accent, t("Floor {n} cleared!", n=floor))
    x, y = REWARD_LEFT.x + 24, body.y + 18
    if report:
        ui.screen.blit(app.art.image("icon/gold", (44, 44)), (x, y))
        ui.text(t("+{n} gold", n=report.gold), x + 56, y + 4, GOLD, "big")
        y += 70
        for up in report.level_ups:
            unit = run.army.units.get(up.uid)
            if unit is None or y > REWARD_LEFT.bottom - 120:
                continue
            row = pygame.Rect(x, y, REWARD_LEFT.width - 48, 112 + (44 if up.skills or up.passives else 0))
            pygame.draw.rect(ui.screen, CELL, row, border_radius=10)
            portrait(ui, app, unit.definition.id, pygame.Rect(row.x + 8, row.y + 8, 96, 96), GOLD if up.levels else DIM)
            ux = row.x + 120
            ui.text(t(unit.name), ux, row.y + 10, TEXT, "main")
            ui.text(f"+{up.exp} {t('exp')}", ux + 300, row.y + 12, EXP, "small")
            bar(ui, pygame.Rect(ux, row.y + 50, row.right - ux - 20, 14), unit.state.exp, app.rules.exp.per_level,
                EXP, (30, 40, 60))
            if up.levels:
                ui.text(t("Level up! {a} -> {b}", a=up.old_level, b=up.new_level), ux, row.y + 74, GOLD, "main")
            news = [("skill", s) for s in up.skills] + [("passive", p) for p in up.passives]
            for i, (kind, entry_id) in enumerate(news[:3]):
                skill_chip(ui, app, kind, entry_id, pygame.Rect(ux + i * 230, row.y + 108, 222, 40))
            y = row.bottom + 12
    take = app.rules.data["reward"]["take"]
    body = panel(ui, REWARD_RIGHT, accent, t("Choose up to {n} items", n=take), f"{len(app.picks)}/{take}")
    for i, item_id in enumerate(run.reward):
        if item_card(ui, app, item_id, reward_card(i), i in app.picks):
            if i in app.picks:
                app.picks.remove(i)
            elif len(app.picks) < take:
                app.picks.append(i)
    label = t("Take ({n}/{take}) and go on", n=len(app.picks), take=take)
    if ui.button(label, TAKE, font="big", color=TEXT, fill=PRIMARY):
        app.act(run.take, db, list(app.picks))
        app.picks = []


# --- магазин ------------------------------------------------------------------------

def draw_shop(ui: UI, app: TowerApp) -> None:
    t, run, db, rules = ui.t, app.run, app.db, app.rules
    accent = ACCENTS[SHOP]
    panel(ui, RECRUITS, accent, t("Recruits"))
    for i, offer in enumerate(run.recruits):
        card = recruit_card(i)
        pygame.draw.rect(ui.screen, CELL, card, border_radius=10)
        if offer is None or offer[0] not in db.units:
            ui.text(t("hired"), card.x + 20, card.y + 20, DIM, "big")
            continue
        class_id, level = offer
        definition = db.units[class_id]
        art = pygame.Rect(card.x + 10, card.y + 10, 200, card.height - 20)
        pygame.draw.rect(ui.screen, PANEL_DARK, art, border_radius=8)
        figure = app.portraits.full(class_id, (art.width - 12, art.height - 12))
        ui.screen.blit(figure, figure.get_rect(midbottom=(art.centerx, art.bottom - 6)))
        ui.tip(art, lambda c=class_id, lv=level: class_tip(t, db, c, lv))
        x = card.x + 230
        ui.text(t(definition.name), x, card.y + 14, TEXT, "big", card.right - x - 12)
        ui.text(t("lv {n}", n=level), x, card.y + 58, GOLD, "main")
        entries = [e for e in class_entries(definition) if e[2] <= level]
        for j, (kind, entry_id, unlock) in enumerate(entries[:4]):
            skill_chip(ui, app, kind, entry_id, pygame.Rect(x, card.y + 96 + j * 42, card.right - x - 16, 38),
                       unlock, level)
        price = rules.recruit_price(level)
        if ui.button(t("Hire for {n}", n=price), hire_button(card), enabled=run.inventory.gold >= price,
                     font="main", fill=accent):
            app.act(run.hire, db, i)

    panel(ui, GOODS, accent, t("Goods"))
    for i, item_id in enumerate(run.shop_items):
        card = goods_card(i)
        if item_id is None:
            pygame.draw.rect(ui.screen, CELL_EMPTY, card, border_radius=10)
            ui.text(t("sold"), card.x + 20, card.y + 20, DIM, "big")
            continue
        price = db.items[item_id].price if item_id in db.items else 0
        item_card(ui, app, item_id, card, price=price)
        buy = pygame.Rect(card.right - 190, card.bottom - 62, 170, 48)
        if ui.button(t("Buy {n}", n=price), buy, enabled=run.inventory.gold >= price, font="main", fill=PRIMARY):
            app.act(run.buy, db, i)
    reroll = rules.reroll_price(run.rerolls)
    if ui.button(t("New goods for {n}", n=reroll), REROLL, enabled=run.inventory.gold >= reroll, font="main"):
        app.act(run.reroll, db)

    body = panel(ui, SELL, lighter(accent, -30), t("Sell"))
    items = [(i, n) for i, n in sorted(run.inventory.items.items()) if n > 0 and i in db.items]
    area = pygame.Rect(SELL.x + 20, body.y + 14, SELL.width - 40, LEAVE.y - body.y - 30)
    rows = area.height // 86
    offset = ui.scroll("tower-sell", area, len(items), rows)
    for row, (item_id, count) in enumerate(items[offset:offset + rows]):
        ry = area.y + row * 86
        item_icon(ui, app, item_id, pygame.Rect(area.x, ry, 76, 76), count)
        ui.text(t(db.items[item_id].name), area.x + 90, ry + 8, tier_color(db.items[item_id].tier), "small",
                area.width - 230)
        if ui.button(f"+{rules.sell_price(db, item_id)}", pygame.Rect(area.right - 130, ry + 16, 130, 44), font="main"):
            app.act(run.sell, db, item_id)
    if ui.button(t("Leave the shop"), LEAVE, font="big", color=TEXT, fill=PRIMARY):
        app.act(run.leave_shop)


# --- конец забега -------------------------------------------------------------------

def draw_over(ui: UI, app: TowerApp) -> None:
    t, run = ui.t, app.run
    body = panel(ui, OVER_PANEL, ACCENTS[OVER], t("Defeat on floor {n}", n=run.floor))
    x, y = OVER_PANEL.x + 40, body.y + 30
    ui.text(t("Floors cleared: {n}   best: {best}", n=run.floor - 1, best=run.best), x, y, TEXT, "big")
    for i, unit in enumerate(list(run.army.units.values())[:12]):
        rect = pygame.Rect(x + (i % 6) * 186, y + 80 + (i // 6) * 230, 170, 170)
        portrait(ui, app, unit.definition.id, rect, DIM)
        ui.text(f"{t(unit.name)} {unit.state.level}", rect.x, rect.bottom + 8, DIM, "small", rect.width)
    if ui.button(t("New run"), NEW_RUN, font="big", color=TEXT, fill=PRIMARY):
        app.new_run()


# --- бой ----------------------------------------------------------------------------

def draw_battle(ui: UI, app: TowerApp) -> None:
    """Верхняя полоса, панели отрядов с портретами и журнал; поле рисует draw_field."""
    t, stage, view = ui.t, app.stage, app.stage.battle_view
    stage.update(ui, view, app.clock)
    sim = view.sim
    accent = ACCENTS["battle"]
    pygame.draw.rect(ui.screen, PANEL_DARK, (0, 0, W, TOP_H))
    pygame.draw.rect(ui.screen, accent, (0, TOP_H - 5, W, 5))
    boss = app.rules.is_boss(app.run.floor)
    ui.text(t("Floor {n}", n=app.run.floor) + ("  " + t("(boss)") if boss else ""), M, 16, ENEMY if boss else TEXT,
            "big")
    ui.text(t("Round {n}", n=view.round), 400, 22, GOLD, "main")
    for i, speed in enumerate(SPEEDS):
        if ui.button(f"x{speed}", pygame.Rect(620 + i * 92, 14, 84, 48), selected=app.speed == speed, font="main"):
            app.speed = speed
    if ui.button(t("Continue") if app.paused else t("Pause"), pygame.Rect(916, 14, 200, 48), font="main",
                 fill=(70, 110, 70) if app.paused else None):
        app.paused = not app.paused
    if ui.button(t("Skip"), pygame.Rect(1128, 14, 160, 48), enabled=not sim.finished, font="main"):
        app.skip()
    ui.text(t("SPACE pause   1/2/3 speed   S skip   wheel zoom"), 1310, 26, DIM, "small")

    squad_hud(ui, app, sim.attacker, PLAYER_HUD, (60, 110, 190), t("Your squad"), False)
    squad_hud(ui, app, sim.defender, ENEMY_HUD, (170, 60, 60), t("Enemies"), True)
    body = panel(ui, LOG, (70, 74, 100), t("Battle log"))
    name = lambda uid: f"{t(sim.units[uid].name)}({uid})"
    lines = [format_event(ev, name, t).strip() for ev in view.log[-9:]]
    for i, line in enumerate(lines):
        ui.text(fit(ui.fonts["tiny"], line, LOG.width - 32), LOG.x + 16, body.y + 10 + i * 24,
                TEXT if i == len(lines) - 1 else DIM, "tiny")


def squad_hud(ui: UI, app: TowerApp, squad, rect: pygame.Rect, accent, title: str, enemy: bool) -> None:
    """Отряд в бою: портрет, HP (как уже показано на сцене), AP и PP каждого."""
    t, stage, view = ui.t, app.stage, app.stage.battle_view
    body = panel(ui, rect, accent, title)
    units = squad.formation.units
    cols = 3
    w, h = (rect.width - 32) // cols, min(110, (body.height - 20) // max(1, (len(units) + cols - 1) // cols))
    for i, unit in enumerate(units):
        card = pygame.Rect(rect.x + 12 + (i % cols) * (w + 4), body.y + 8 + (i // cols) * (h + 4), w, h)
        hp = stage.hp.get(unit.uid, unit.hp)
        dead = unit.uid in stage.dead or hp <= 0
        current = view.current_uid == unit.uid
        pygame.draw.rect(ui.screen, (40, 30, 34) if dead else CELL, card, border_radius=8)
        pygame.draw.rect(ui.screen, YELLOW if current else lighter(accent, 20), card, 3 if current else 1,
                         border_radius=8)
        side = h - 12
        image = app.portraits.portrait(unit.definition.id, side - 4, enemy)
        if dead:
            image = image.copy()
            image.fill((90, 80, 80, 255), special_flags=pygame.BLEND_RGBA_MULT)
        framed(ui, image, pygame.Rect(card.x + 6, card.y + 6, side, side), accent, width=2)
        x = card.x + side + 14
        width = card.right - x - 8
        ui.text(t(unit.name), x, card.y + 6, DIM if dead else TEXT, "small", width)
        bar(ui, pygame.Rect(x, card.y + 34, width, 16), hp, unit.max_hp, GREEN if hp * 3 > unit.max_hp else RED,
            label=f"{max(0, hp)}/{unit.max_hp}")
        pips(ui, x, card.y + 58, unit.ap.current, unit.ap.max, AP_COLOR)
        pips(ui, x, card.y + 76, unit.pp.current, unit.pp.max, PP_COLOR)
        ui.tip(card, lambda u=unit: unit_tip(t, app.db, u))


def pips(ui: UI, x: int, y: int, current: int, maximum: int, color) -> None:
    for i in range(min(maximum, 10)):
        rect = pygame.Rect(x + i * 15, y, 12, 12)
        if i < current:
            pygame.draw.rect(ui.screen, color, rect, border_radius=3)
        pygame.draw.rect(ui.screen, color, rect, 1, border_radius=3)


def draw_result(ui: UI, app: TowerApp) -> None:
    """Итог боя поверх поля: победа или поражение и кнопка «Дальше»."""
    view = app.stage.battle_view
    if not view.sim.finished or view.ended is None:
        return
    t = ui.t
    won = view.sim.winner_id == view.sim.attacker.id
    banner = pygame.Rect(W // 2 - 420, FIELD.centery - 120, 840, 280)
    shade = pygame.Surface(banner.size, pygame.SRCALPHA)
    shade.fill((10, 12, 20, 210))
    ui.screen.blit(shade, banner.topleft)
    color = GOLD if won else ENEMY
    pygame.draw.rect(ui.screen, color, banner, 4, border_radius=12)
    img = ui.fonts["title"].render(t("Victory!") if won else t("Defeat"), True, color)
    ui.screen.blit(img, img.get_rect(center=(banner.centerx, banner.y + 70)))
    if ui.button(t("Continue (ENTER)"), CONTINUE, font="big", color=TEXT, fill=PRIMARY):
        app.finish_battle()


SCREENS: dict[str, Callable[[UI, TowerApp], None]] = {
    DRAFT: draw_draft, PREPARE: draw_prepare, REWARD: draw_reward, SHOP: draw_shop, OVER: draw_over,
}


def draw_frame(ui: UI, app: TowerApp, window: Optional[Window] = None) -> None:
    """Кадр в ui.screen (1920x1280); с окном поле боя рисуется прямо в окно в полном разрешении."""
    ui.t = app.t
    ui.screen.fill(BACK)
    if app.in_battle:
        draw_battle(ui, app)
        if window is None:
            app.stage.draw_field(ui.screen, app.clock, field_camera(app.stage, None))
        draw_result(ui, app)
    else:
        phase = "tactics" if app.tactics and app.run.phase == PREPARE else app.run.phase
        background(ui, app, phase)
        draw_top(ui, app, ACCENTS[phase])
        SCREENS[app.run.phase](ui, app)
    if app.message:
        img = ui.fonts["main"].render(fit(ui.fonts["main"], app.message, W - 80), True, YELLOW)
        back = pygame.Rect(W // 2 - img.get_width() // 2 - 16, H - 52, img.get_width() + 32, 40)
        pygame.draw.rect(ui.screen, PANEL_DARK, back, border_radius=8)
        ui.screen.blit(img, (back.x + 16, back.y + 6))
    ui.end()
    if window is not None:
        window.present()
        if app.in_battle:
            app.stage.draw_field(window.surface, app.clock, field_camera(app.stage, window))
            # подсказки, итог боя и открытый список — поверх поля
            for area in (banner_area(app), ui.popup_box if ui.popup is not None else ui.tip_box):
                if area is not None:
                    window.present(area)


def banner_area(app: TowerApp) -> Optional[pygame.Rect]:
    view = app.stage.battle_view
    if view is None or not view.sim.finished:
        return None
    return pygame.Rect(W // 2 - 420, FIELD.centery - 120, 840, 280)


def make_ui(window_canvas: pygame.Surface) -> UI:
    ui = UI(window_canvas, tower_fonts())
    ui.scale = SCALE
    return ui


def main(max_frames: Optional[int] = None, save_path: Union[str, Path, None] = DEFAULT_SAVE_PATH,
         data_dir: Union[str, Path, None] = None, lang: Optional[str] = None) -> None:
    """max_frames нужен только для проверки запуска без окна (SDL_VIDEODRIVER=dummy)."""
    pygame.init()
    pygame.display.set_caption("Squad auto-battle — Tower")
    pygame.display.set_mode(SIZES[0])
    app = TowerApp(save_path, data_dir, lang=lang)
    fitting = Window.presets(SIZES)
    size = app.resolution if app.resolution in fitting else fitting[-1]
    window = Window(size, SIZE, SIZES)
    app.resolution = window.surface.get_size()
    ui = make_ui(window.canvas)
    ui.transform = window.to_logical
    clock = pygame.time.Clock()
    frames, running = 0, True
    while running:
        dt = clock.tick(FPS)
        events = [window.logical_event(e) for e in pygame.event.get()]
        ui.begin(events)
        for event in events:
            if app.in_battle and not ui.captured:
                mouse = event.pos if hasattr(event, "pos") else ui.mouse
                if FIELD.collidepoint(mouse) or event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONUP:
                    app.handle_battle_event(event, mouse, window.scale)
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                window.resize(event.size)
                app.resolution = window.surface.get_size()
            elif event.type != pygame.KEYDOWN or ui.captured:
                continue
            elif event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_F12:
                window.next_size()
                app.resolution = window.surface.get_size()
            else:
                app.handle_key(event.key)
        app.tick(dt)
        draw_frame(ui, app, window)
        pygame.display.flip()
        frames += 1
        if max_frames is not None and frames >= max_frames:
            running = False
    app.save()
    pygame.quit()


if __name__ == "__main__":
    main(lang=sys.argv[1] if len(sys.argv) > 1 else None)
