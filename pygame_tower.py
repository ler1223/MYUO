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
from game.events import format_event
from game.i18n import Translator, available_languages
from game.tower import (DEFAULT_SAVE_PATH, DRAFT, OVER, PREPARE, REWARD, SHOP, TOWER_RULES_PATH, TowerRules,
                        TowerRun)
from game.unit import Unit
from pygame_art import ArtBank, Portraits
from pygame_battle import FIELD_RECT, SKIP_BACKLOG_MS, BattleView
from pygame_stage import TOWER_MODE, StageScreen, load_visuals
from pygame_tips import STAT_COLORS, class_tip, modifier_text, tier_color, unit_tip
import pygame_tower_style
from pygame_tower_inventory import InventoryFilter
from pygame_tower_prepare import INVENTORY, MAIN, STATUS, UNIT, draw_prepare, go_back
from pygame_tower_style import (ACCENTS, AP_COLOR, BACK, CELL, CELL_EMPTY, DIM, ENEMY, EXP, GOLD, GREEN, H, M,
                                GOLD_LINE, PANEL_DARK, PP_COLOR, SIZE, SIZES, TEXT, TOP_H, W, background, bar, button,
                                Skin, class_entries, framed, item_icon, make_ui, panel, portrait, skill_chip, stat_grid)
from pygame_ui import RED, UI, YELLOW, Window, fit, lighter

FPS = 60
AUTO_STEP_MS = 600
SPEEDS = (1, 2, 4)                       # клавиши 1, 2, 3
NONE_ITEM = "__none__"                   # в списке снаряжения: снять предмет

# --- раскладка: прямоугольники, общие для отрисовки и тестов -------------------------

def draft_card(i: int) -> pygame.Rect:
    return pygame.Rect(M + i * 636, TOP_H + 96, 600, H - TOP_H - 96 - 40)


def take_button(card: pygame.Rect) -> pygame.Rect:
    return pygame.Rect(card.x + 20, card.bottom - 74, card.width - 40, 56)


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
        pygame_tower_style.SKIN = Skin(self.art)   # нарисованные рамки, если они есть в assets/ui/frame
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
        # Подготовка (pygame_tower_prepare): вид, выбранный боец, вкладка и слот его редактора
        self.view = MAIN
        self.back_view = MAIN                  # куда вернуться из редактора бойца
        self.selected: Optional[int] = None
        self.tab = STATUS
        self.slot = 0
        self.drag: Optional[tuple[int, tuple[int, int]]] = None   # (uid, где нажали) — бойца тащат
        self.preview = None
        self.inv = InventoryFilter()           # фильтры и сортировка экрана инвентаря
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
        self.selected, self.view, self.picks, self.confirm_new = None, MAIN, [], False
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


def draw_top(ui: UI, app: TowerApp, accent) -> None:
    t, run = ui.t, app.run
    pygame.draw.rect(ui.screen, PANEL_DARK, (0, 0, W, TOP_H))
    pygame.draw.rect(ui.screen, accent, (0, TOP_H - 6, W, 4))
    pygame.draw.line(ui.screen, GOLD_LINE, (0, TOP_H - 2), (W, TOP_H - 2), 2)
    boss = app.rules.is_boss(run.floor)
    ui.screen.blit(app.art.image("icon/boss" if boss else "icon/floor", (48, 48)), (M, 12))
    ui.text(t("Floor {n}", n=run.floor), M + 60, 14, ENEMY if boss else GOLD, "big")
    if boss:
        ui.text(t("(boss)"), M + 240, 22, ENEMY, "main")
    ui.screen.blit(app.art.image("icon/gold", (44, 44)), (420, 14))
    ui.text(str(run.inventory.gold), 474, 16, GOLD, "big")
    ui.tip(pygame.Rect(420, 10, 200, 56), lambda: [(t("Gold"), GOLD, "main"),
                                                   (t("Earned by winning floors, spent in the shop."), TEXT, "small")])
    ui.text(t("best floor {n}", n=run.best), 660, 24, DIM, "main")
    buttons = pygame.Rect(W - 760, 12, 280, 52), pygame.Rect(W - 466, 12, 300, 52), pygame.Rect(W - 152, 12, 128, 52)
    if button(ui, t("Reload data (F5)"), buttons[0], enabled=not app.in_battle, font="small", icon="icon/settings"):
        if app.reload():
            app.message = t("data reloaded")
    label = t("Sure? Click again") if app.confirm_new else t("New run")
    if button(ui, label, buttons[1], enabled=not app.in_battle, selected=app.confirm_new, font="small"):
        if app.confirm_new or run.phase == OVER:
            app.new_run()
        else:
            app.confirm_new = True
    if button(ui, app.t.lang.upper(), buttons[2]):
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
    return bool(button(ui, t("Take"), take_button(rect), primary=True, font="big"))


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
                EXP, (30, 40, 60), kind="exp")
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
    if button(ui, label, TAKE, primary=True, font="big"):
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
        if button(ui, t("Hire for {n}", n=price), hire_button(card), enabled=run.inventory.gold >= price):
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
        if button(ui, t("Buy {n}", n=price), buy, primary=True, enabled=run.inventory.gold >= price):
            app.act(run.buy, db, i)
    reroll = rules.reroll_price(run.rerolls)
    if button(ui, t("New goods for {n}", n=reroll), REROLL, enabled=run.inventory.gold >= reroll):
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
        if button(ui, f"+{rules.sell_price(db, item_id)}", pygame.Rect(area.right - 130, ry + 16, 130, 44)):
            app.act(run.sell, db, item_id)
    if button(ui, t("Leave the shop"), LEAVE, primary=True, font="big"):
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
    if button(ui, t("New run"), NEW_RUN, primary=True, font="big"):
        app.new_run()


# --- бой ----------------------------------------------------------------------------

def draw_battle(ui: UI, app: TowerApp) -> None:
    """Верхняя полоса, панели отрядов с портретами и журнал; поле рисует draw_field."""
    t, stage, view = ui.t, app.stage, app.stage.battle_view
    stage.update(ui, view, app.clock)
    sim = view.sim
    accent = ACCENTS["battle"]
    hud = pygame.Rect(0, FIELD.bottom, W, H - FIELD.bottom)          # полотно под полем: фон bg/battle_hud
    ui.screen.blit(app.art.image("bg/battle_hud", hud.size, cover=True), hud.topleft)
    pygame.draw.rect(ui.screen, PANEL_DARK, (0, 0, W, TOP_H))
    pygame.draw.rect(ui.screen, accent, (0, TOP_H - 5, W, 5))
    boss = app.rules.is_boss(app.run.floor)
    ui.text(t("Floor {n}", n=app.run.floor) + ("  " + t("(boss)") if boss else ""), M, 16, ENEMY if boss else TEXT,
            "big")
    ui.text(t("Round {n}", n=view.round), 400, 22, GOLD, "main")
    for i, speed in enumerate(SPEEDS):
        if button(ui, f"x{speed}", pygame.Rect(620 + i * 92, 12, 84, 52), selected=app.speed == speed):
            app.speed = speed
    if button(ui, t("Continue") if app.paused else t("Pause"), pygame.Rect(916, 12, 200, 52), selected=app.paused):
        app.paused = not app.paused
    if button(ui, t("Skip"), pygame.Rect(1128, 12, 160, 52), enabled=not sim.finished):
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
        framed(ui, image, pygame.Rect(card.x + 6, card.y + 6, side, side), accent, width=2,
               kind="portrait_enemy" if enemy else "portrait")
        x = card.x + side + 14
        width = card.right - x - 8
        ui.text(t(unit.name), x, card.y + 6, DIM if dead else TEXT, "small", width)
        bar(ui, pygame.Rect(x, card.y + 34, width, 16), hp, unit.max_hp, GREEN if hp * 3 > unit.max_hp else RED,
            kind="enemy" if enemy else "hp",
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
    if button(ui, t("Continue (ENTER)"), CONTINUE, primary=True, font="big"):
        app.finish_battle()


SCREENS: dict[str, Callable[[UI, TowerApp], None]] = {
    DRAFT: draw_draft, PREPARE: draw_prepare, REWARD: draw_reward, SHOP: draw_shop, OVER: draw_over,
}


def draw_frame(ui: UI, app: TowerApp, window: Optional[Window] = None) -> None:
    """Кадр в ui.screen (1920x1280); с окном поле боя рисуется прямо в окно в полном разрешении."""
    ui.t = app.t
    ui.frames = pygame_tower_style.SKIN.draw if pygame_tower_style.SKIN is not None else None
    ui.screen.fill(BACK)
    if app.in_battle:
        draw_battle(ui, app)
        if window is None:
            app.stage.draw_field(ui.screen, app.clock, field_camera(app.stage, None))
        draw_result(ui, app)
    else:
        phase = UNIT if app.view == UNIT and app.run.phase == PREPARE else app.run.phase
        scene = INVENTORY if app.view == INVENTORY and app.run.phase == PREPARE else phase
        background(ui, app, scene)
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
                # назад по экранам подготовки; с главного экрана — выход
                running = app.in_battle or app.run.phase != PREPARE or go_back(app)
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
