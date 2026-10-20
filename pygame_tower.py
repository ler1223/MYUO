"""Окно бесконечной башни (pygame-ce). Запуск: python tower.py

Отдельная программа, не вкладка демо: свой забег (saves/tower.json), общий справочник data/.
Перед каждым боем и по F5 справочник, правила башни (data/tower.json) и визуал навыков
перечитываются с диска, поэтому правки, сделанные в открытом рядом окне демо, сразу в игре.

Интерфейс рисуется в логическом размере 1920x1280 и масштабируется под окно; строится на движке
uikit (тема assets/ui/theme.json). Экран зависит от фазы забега: набор бойцов, подготовка
(pygame_tower_prepare), бой этажа на сцене (2.5D) с панелями отрядов, награда, магазин, конец забега.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional, Union

import pygame

from game import roles
from game.database import Database
from game.i18n import Translator, available_languages
from game.tower import (DEFAULT_SAVE_PATH, DRAFT, OVER, PREPARE, REWARD, SHOP, TOWER_RULES_PATH, TowerRules,
                        TowerRun)
from game.unit import Unit
from pygame_art import ArtBank, Portraits
from battle import BattleShow
from battle.data import ENABLED as UO_ANIM_ENABLED
from battle.figures import Figures
from pygame_tips import STAT_COLORS, class_tip, modifier_text, tier_color, unit_tip
from pygame_tower_inventory import InventoryFilter
from pygame_tower_prepare import EQUIPMENT, INVENTORY, MAIN, PROMOTE, UNIT, draw_prepare, go_back
from pygame_tower_style import (BACK, DIM, ENEMY, FULL_BODY, GAP, GOLD, H, M, SIZE, SIZES, TEXT, TOP_H, W,
                                background, bar, button, class_entries, full_figure, item_icon, level_badge,
                                make_ui, panel, portrait, shade, skill_chip, stat_rows, unit_name)
from pygame_ui import Window
from uikit import Gui
from uikit import widgets as w
from uikit.layout import cols, cut_left, cut_top, grid, inset, place, row_of, rows

FPS = 60
AUTO_STEP_MS = 600
MAX_FRAME_MS = 50                        # больше за кадр время боя не идёт
SPEEDS = (1, 2, 4)                       # клавиши 1, 2, 3
NONE_ITEM = "__none__"                   # в списке снаряжения: снять предмет
RESULT = 4                               # слой итога боя: над полем и панелями, забирает мышь

# --- раскладка: прямоугольники, общие для отрисовки и тестов -------------------------

TOP = pygame.Rect(0, 0, W, TOP_H)
TOP_ROW = inset(TOP, M, 12, M, 14)
DRAFT_TITLE, DRAFT_AREA = cut_top(FULL_BODY, 64, 16)
DRAFT_CARDS = cols(DRAFT_AREA, [1.0, 1.0, 1.0], GAP)
PANEL_PAD = (38, 92, 38, 36)


def draft_card(i: int) -> pygame.Rect:
    return DRAFT_CARDS[i]


def take_button(card: pygame.Rect) -> pygame.Rect:
    return place(inset(card, 40, 0, 40, 38), (card.width - 80, 76), "bottom")


REWARD_LEFT, REWARD_RIGHT = cols(FULL_BODY, [860, 1.0], GAP)
REWARD_AREA = inset(REWARD_RIGHT, *PANEL_PAD)
TAKE = place(REWARD_AREA, (REWARD_AREA.width, 78), "bottom")
RECRUITS, GOODS, SELL = cols(FULL_BODY, [600, 720, 1.0], GAP)
RECRUIT_AREA, GOODS_AREA, SELL_AREA = (inset(r, *PANEL_PAD) for r in (RECRUITS, GOODS, SELL))
LEAVE = place(SELL_AREA, (SELL_AREA.width, 78), "bottom")
REROLL = place(GOODS_AREA, (GOODS_AREA.width, 70), "bottom")
OVER_PANEL = place(FULL_BODY, (1200, 860), "center")
NEW_RUN = place(inset(OVER_PANEL, 0, 0, 0, 50), (420, 84), "bottom")
# Бой, как в UO: поле на весь экран, поверх — плашки бойцов и небольшие кнопки сверху.
# Логическое поле сцены — поле демо (FIELD_RECT), продолженное вверх (небо) до пропорций экрана.
FIELD = pygame.Rect(0, 0, W, H)
BANNER = place(FIELD, (W, 420), "center")                       # итог боя: надпись UO и кнопка под ней
CONTINUE = place(inset(BANNER, 0, 0, 0, 30), (440, 84), "bottom")
BATTLE_BAR = pygame.Rect(0, 0, W, TOP_H)                         # кнопки боя поверх поля
FLOOR_PLATE, ROUND_LABEL = row_of(TOP_ROW, [400, 240], 18, "left")
*SPEED_BUTTONS, PAUSE, SKIP = row_of(TOP_ROW, [96, 96, 96, 190, 210], 10, "right")
UO_RESULT_FILE = "Interface"                                     # GUI/Interface.mbs: RESULT_WIN_* / RESULT_LOSE_*
MESSAGE = pygame.Rect(0, H - 70, W, 60)                          # строка сообщения внизу экрана


def reward_card(i: int) -> pygame.Rect:
    return pygame.Rect(REWARD_AREA.x, REWARD_AREA.y + i * 190, REWARD_AREA.width, 176)


def recruit_card(i: int, count: int = 3) -> pygame.Rect:
    """i-я карточка найма из count: делят высоту панели поровну."""
    return rows(RECRUIT_AREA, [1.0] * max(count, i + 1), 14)[i]


def hire_button(card: pygame.Rect) -> pygame.Rect:
    return pygame.Rect(card.x + 236, card.bottom - 84, card.width - 256, 66)


def goods_card(i: int, count: int = 5) -> pygame.Rect:
    """i-я карточка товара из count: делят место над кнопкой нового товара поровну."""
    area = pygame.Rect(GOODS_AREA.x, GOODS_AREA.y, GOODS_AREA.width, REROLL.y - GOODS_AREA.y - 14)
    return rows(area, [1.0] * max(count, i + 1), 10)[i]


def window_field(window: Optional[Window]) -> pygame.Rect:
    """Поле боя в пикселях окна (без окна — логические пиксели)."""
    if window is None:
        return pygame.Rect(FIELD)
    k, (ox, oy) = window.scale, window.offset
    return pygame.Rect(round(ox + FIELD.x * k), round(oy + FIELD.y * k), round(FIELD.width * k), round(FIELD.height * k))


class TowerApp:
    """Забег, справочник, картинки, сцена боя и состояние экранов."""

    def __init__(self, save_path: Union[str, Path, None] = DEFAULT_SAVE_PATH, data_dir: Union[str, Path, None] = None,
                 rules_path: Union[str, Path] = TOWER_RULES_PATH,
                 lang: Optional[str] = None, seed: Optional[int] = None):
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
        self._item_icons: Any = None       # иконки предметов из UO (engine.uo.items), если есть игра
        if UO_ANIM_ENABLED:
            self.art.providers.append(self._uo_art)
        self.figures = Figures()           # фигуры и портреты классов на экранах башни (куклы UO)
        self.portraits = Portraits(self.art, self.figures)
        self.show: Optional[BattleShow] = None   # бой этажа: правила game.combat, показ battle/
        self.result_at: Optional[int] = None   # когда показан итог боя (время боя) — для анимации надписи
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
        self.tab = EQUIPMENT
        self.tactic_pick = None                # открытый список в таблице тактики: (правило, колонка)
        self.tactic_passive = None             # чьи тактики в таблице: None — юнита, иначе id пассивки
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

    def _uo_art(self, key: str) -> Optional[pygame.Surface]:
        """Картинка из Unicorn Overlord для ключа ArtBank: иконка предмета item/<слот>/<id>."""
        parts = key.split("/")
        if len(parts) != 3 or parts[0] != "item" or parts[2] not in self.db.items:
            return None
        if self._item_icons is None:
            from engine.uo.items import ItemIcons
            self._item_icons = ItemIcons(self.db.items)
        rgba = self._item_icons.image(parts[2])
        if rgba is None:
            return None
        image = pygame.image.frombuffer(rgba.tobytes(), (rgba.shape[1], rgba.shape[0]), "RGBA")
        return image.convert_alpha() if pygame.display.get_surface() is not None else image.copy()

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
        self._item_icons = None
        self.art.forget()
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

    def set_look(self, unit: Any, look: int) -> None:
        """Модель бойца из моделей его класса (пол, внешность); сохраняется в забеге."""
        unit.state.look = int(look)
        self.save()

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
        seed = self.run.seed + self.run.floor * 7919
        self.clock = 0
        self.show = BattleShow(self.db, self.scenario.player_squad, self.scenario.enemy_squad, seed=seed,
                               scene=self.rules.scene(self.run.floor), time_of_day=self.scenario.time_of_day)
        self.in_battle, self.paused, self.message = True, False, ""

    def tick(self, dt: int) -> None:
        """Время боя: идёт быстрее при ускорении, стоит на паузе; показ берёт у боя следующие акты сам,
        когда доиграна сцена прошлого."""
        if not self.in_battle or self.show is None:
            return
        if not self.paused:
            self.clock += min(dt, MAX_FRAME_MS) * self.speed     # долгий кадр не перескакивает через сцены
        self.show.update(self.clock)

    def battle_over(self) -> bool:
        """Бой кончился и доигран: итог и «Дальше» — только после последней сцены."""
        return self.show is not None and self.show.done(self.clock)

    def skip(self) -> None:
        """Доиграть бой сразу: сцены пропускаются, плашки и павшие — как в итоге."""
        if self.show is not None and not self.show.battle.finished:
            self.clock = self.show.skip(self.clock)

    def finish_battle(self) -> None:
        """Enter после боя: итог в забег, дальше награда или конец."""
        if not self.in_battle or not self.battle_over():
            return
        battle = self.show.battle
        won = battle.winner_id == battle.attacker.id
        self.run.finish(self.db, self.scenario, won)
        self.in_battle, self.scenario, self.picks, self.show = False, None, [], None
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
        elif key == pygame.K_s:
            self.skip()
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.finish_battle()

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
            self.message = self.t("{unit} cannot wear this", unit=self.t(unit.nickname))
            return
        empty = [i for i in slots if unit.state.equipment[i] is None]
        self.change_equipment(unit, (empty or slots)[0], item_id)


# --- верхняя полоса ------------------------------------------------------------------

def top_strip(ui: Gui) -> None:
    shade(ui, TOP, 200)
    w.divider(ui, 0, W, TOP.bottom - 2)


def draw_top(ui: Gui, app: TowerApp) -> None:
    t, run = ui.t, app.run
    top_strip(ui)
    boss = app.rules.is_boss(run.floor)
    floor_icon, floor_r, gold_icon, gold_r, best_r = row_of(TOP_ROW, [52, 300, 48, 160, 320], 12, "left")
    ui.screen.blit(app.art.image("icon/boss" if boss else "icon/floor", (52, 52)), floor_icon.topleft)
    ui.label(t("Floor {n}", n=run.floor) + ("  " + t("(boss)") if boss else ""), floor_r, "title",
             color=ENEMY if boss else GOLD)
    ui.screen.blit(app.art.image("icon/gold", (48, 48)), gold_icon.move(0, 4).topleft)
    ui.label(str(run.inventory.gold), gold_r, "title")
    ui.tip(gold_icon.union(gold_r), lambda: [(t("Gold"), GOLD, "main"),
                                             (t("Earned by winning floors, spent in the shop."), TEXT, "small")])
    ui.label(t("best floor {n}", n=run.best), best_r, "body", color=DIM)
    reload_r, new_r, lang_r = row_of(TOP_ROW, [320, 300, 110], 12, "right")
    if button(ui, t("Reload data (F5)"), reload_r, enabled=not app.in_battle, style="small",
              icon_key="icon/settings", app=app):
        if app.reload():
            app.message = t("data reloaded")
    label = t("Sure? Click again") if app.confirm_new else t("New run")
    if button(ui, label, new_r, enabled=not app.in_battle, selected=app.confirm_new, style="small"):
        if app.confirm_new or run.phase == OVER:
            app.new_run()
        else:
            app.confirm_new = True
    if button(ui, app.t.lang.upper(), lang_r, style="small"):
        app.next_language()


# --- набор -------------------------------------------------------------------------

def draw_draft(ui: Gui, app: TowerApp) -> None:
    t, run = ui.t, app.run
    groups = app.rules.draft_groups()
    group = groups[min(run.draft_group, len(groups) - 1)]
    total = len(groups)
    ui.label(t("Choose a fighter {n}/{total}: {role}", n=len(run.army.units) + 1, total=total,
               role=t(roles.TITLES.get(group["role"], group["role"]))), DRAFT_TITLE, "title")
    taken = list(run.army.units.values())
    faces = row_of(DRAFT_TITLE, [64] * len(taken), 10, "right")
    for rect, unit in zip(faces, taken):                     # уже взятые — портреты справа от заголовка
        portrait(ui, app, unit.definition.id, place(rect, (64, 64), "center"))
        ui.tip(rect, lambda u=unit: unit_tip(t, app.db, u))
    for i, class_id in enumerate(list(run.offers)):
        if draw_class_card(ui, app, class_id, draft_card(i)):
            app.act(run.pick, app.db, class_id)


def draw_class_card(ui: Gui, app: TowerApp, class_id: str, rect: pygame.Rect) -> bool:
    """Карточка класса при наборе: фигура, статы, снаряжение, навыки. True — взяли."""
    t, db, run = ui.t, app.db, app.run
    level = app.rules.data["draft"]["level"]
    unit = db.create_unit(class_id, 0, level, run.starter_gear(db, class_id))
    body = panel(ui, rect, t(unit.name), t("lv {n}", n=level))
    body.height = take_button(rect).y - body.y - 14
    art_r, rest = cut_top(body, 340, 12)
    shade(ui, art_r, 120)
    full_figure(ui, app, class_id, (art_r.width - 20, art_r.height - 16), (art_r.centerx, art_r.bottom - 8))
    tags = ", ".join(t(db.tags[tag].name) for tag in unit.definition.tags if tag in db.tags)
    ui.label(tags, inset(pygame.Rect(art_r.x, art_r.y, art_r.width, 40), 12, 0), "small", color=DIM)
    stats_r, rest = cut_top(rest, 6 * 34, 10)
    stat_rows(ui, app, unit, stats_r, 2, style="small", grades=True)
    gear_title, rest = cut_top(rest, 32, 4)
    ui.label(t("Equipment"), gear_title, "label")
    gear_r, rest = cut_top(rest, 76, 10)
    for i, item_id in enumerate(i for i in unit.state.equipment if i is not None):
        item_icon(ui, app, item_id, pygame.Rect(gear_r.x + i * 84, gear_r.y, 76, 76))
    skills_title, rest = cut_top(rest, 32, 4)
    ui.label(t("Skills and passives"), skills_title, "label")
    entries = class_entries(unit)
    for chip, (kind, entry_id, unlock) in zip(grid(rest, len(entries), 2, 44, 12, 8), entries):
        if chip.bottom > rest.bottom:
            break
        skill_chip(ui, app, kind, entry_id, chip, unlock, level)
    return bool(button(ui, t("Take"), take_button(rect), primary=True, style="tab"))


# --- награда ------------------------------------------------------------------------

def item_card(ui: Gui, app: TowerApp, item_id: str, rect: pygame.Rect, selected: bool = False,
              price: Optional[int] = None, action: Optional[pygame.Rect] = None) -> int:
    """Крупная карточка предмета: иконка, название цвета тира, слот и тир, бонусы.
    action — место под кнопку на карточке (текст его не занимает). Возвращает клик по карточке."""
    t, db = ui.t, app.db
    item = db.items.get(item_id)
    body, clicked = w.selectable(ui, rect, "card", selected=selected)
    icon_r, text_r = cut_left(inset(body, 10, 8), body.height - 16, 18)
    on_icon = item_icon(ui, app, item_id, icon_r, price=price)
    if item is None:
        return clicked
    if action is not None:
        text_r.width = action.x - text_r.x - 12
    name_r, kind_r, mods_r = rows(text_r, [40, 30, 1.0], 2)
    ui.label(t(item.name), name_r, "heading", color=tier_color(item.rank))
    tier_name = t(("novice", "mercenary", "hero")[item.rank - 1])
    ui.label(f"{t(item.slot)} · {tier_name}", kind_r, "small", color=DIM)
    for cell, mod in zip(grid(mods_r, len(item.modifiers), 1 if action else 2, 30, 12, 2), item.modifiers):
        ui.label(modifier_text(t, mod), cell, "small", color=STAT_COLORS.get(mod.stat, TEXT))
    if selected:                                  # галочка: в шрифте её может не быть, рисуется линиями
        a, b, c = (body.right - 46, body.y + 26), (body.right - 34, body.y + 40), (body.right - 12, body.y + 10)
        pygame.draw.lines(ui.screen, GOLD, False, (a, b, c), 6)
    return 0 if on_icon else clicked


def draw_reward(ui: Gui, app: TowerApp) -> None:
    t, run, db = ui.t, app.run, app.db
    report = run.report
    floor = report.floor if report else run.floor
    body = panel(ui, REWARD_LEFT, t("Floor {n} cleared!", n=floor))
    if report:
        gold_r, rest = cut_top(body, 56, 12)
        icon_r, text_r = cut_left(gold_r, 52, 12)
        ui.screen.blit(app.art.image("icon/gold", (52, 52)), icon_r.topleft)
        ui.label(t("+{n} gold", n=report.gold), text_r, "title")
        for up in report.level_ups:
            unit = run.army.units.get(up.uid)
            height = 150 + (54 if up.skills or up.passives else 0)
            if unit is None or rest.height < height:
                continue
            row, rest = cut_top(rest, height, 12)
            row_body = w.frame(ui, "card", row)
            face, info = cut_left(inset(row_body, 10, 8), 100, 16)
            portrait(ui, app, unit.definition.id, place(face, (100, 100), "top"))
            name_r, exp_r, level_r, news_r = rows(info, [40, 26, 40, 1.0], 4)
            ui.label(unit_name(t, unit), name_r, "body")
            ui.label(f"+{up.exp} {t('exp')}", name_r, "small", align="right", color=(120, 200, 255))
            bar(ui, exp_r, unit.state.exp, app.rules.exp.per_level, "exp")
            if up.levels:
                ui.label(t("Level up! {a} -> {b}", a=up.old_level, b=up.new_level), level_r, "heading")
            else:
                level_badge(ui, level_r, unit.state.level)
            news = [("skill", s) for s in up.skills] + [("passive", p) for p in up.passives]
            for chip, (kind, entry_id) in zip(cols(news_r, [1.0] * 3, 10), news[:3]):
                skill_chip(ui, app, kind, entry_id, chip)
    take = app.rules.data["reward"]["take"]
    panel(ui, REWARD_RIGHT, t("Choose up to {n} items", n=take), f"{len(app.picks)}/{take}")
    for i, item_id in enumerate(run.reward):
        if item_card(ui, app, item_id, reward_card(i), i in app.picks):
            if i in app.picks:
                app.picks.remove(i)
            elif len(app.picks) < take:
                app.picks.append(i)
    label = t("Take ({n}/{take}) and go on", n=len(app.picks), take=take)
    if button(ui, label, TAKE, primary=True, style="tab"):
        app.act(run.take, db, list(app.picks))
        app.picks = []


# --- магазин ------------------------------------------------------------------------

def draw_shop(ui: Gui, app: TowerApp) -> None:
    t, run, db, rules = ui.t, app.run, app.db, app.rules
    panel(ui, RECRUITS, t("Recruits"))
    for i, offer in enumerate(run.recruits):
        card = recruit_card(i, len(run.recruits))
        body = w.frame(ui, "card", card)
        if offer is None or offer[0] not in db.units:
            ui.label(t("hired"), inset(body, 20), "heading", color=DIM, align="center")
            continue
        class_id, level = offer
        definition = db.units[class_id]
        art_r, info = cut_left(inset(body, 10, 10), 210, 16)
        shade(ui, art_r, 120)
        full_figure(ui, app, class_id, (art_r.width - 12, art_r.height - 12), (art_r.centerx, art_r.bottom - 6))
        ui.tip(art_r, lambda c=class_id, lv=level: class_tip(t, db, c, lv))
        name_r, level_r, skills_r = rows(pygame.Rect(info.x, info.y, info.width, hire_button(card).y - info.y - 10),
                                         [44, 36, 1.0], 4)
        ui.label(t(definition.name), name_r, "heading", color=TEXT)
        level_badge(ui, level_r, level)
        entries = [e for e in class_entries(definition) if e[2] <= level]
        chips = max(0, min(3, (skills_r.height + 6) // 50))
        for chip, (kind, entry_id, unlock) in zip(rows(skills_r, [44] * chips, 6), entries[:chips]):
            skill_chip(ui, app, kind, entry_id, chip, unlock, level)
        price = rules.recruit_price(level)
        if button(ui, t("Hire for {n}", n=price), hire_button(card), enabled=run.inventory.gold >= price):
            app.act(run.hire, db, i)

    panel(ui, GOODS, t("Goods"))
    for i, item_id in enumerate(run.shop_items):
        card = goods_card(i, len(run.shop_items))
        if item_id is None:
            body = w.frame(ui, "card", card)
            ui.label(t("sold"), body, "heading", color=DIM, align="center")
            continue
        price = db.items[item_id].price if item_id in db.items else 0
        buy = place(inset(card, 0, 0, 18, 20), (200, 64), "bottomright")
        item_card(ui, app, item_id, card, price=price, action=buy)
        if button(ui, t("Buy {n}", n=price), buy, enabled=run.inventory.gold >= price):
            app.act(run.buy, db, i)
    reroll = rules.reroll_price(run.rerolls)
    if button(ui, t("New goods for {n}", n=reroll), REROLL, enabled=run.inventory.gold >= reroll):
        app.act(run.reroll, db)

    panel(ui, SELL, t("Sell"))
    items = [(i, n) for i, n in sorted(run.inventory.items.items()) if n > 0 and i in db.items]
    area = pygame.Rect(SELL_AREA.x, SELL_AREA.y, SELL_AREA.width, LEAVE.y - SELL_AREA.y - 16)
    lines = max(1, area.height // 92)
    offset = ui.scroll("tower-sell", area, len(items), lines)
    if not items:
        ui.label(t("nothing to sell"), pygame.Rect(area.x, area.y, area.width, 40), "body", color=DIM)
    for row, (item_id, count) in enumerate(items[offset:offset + lines]):
        line = pygame.Rect(area.x, area.y + row * 92, area.width, 84)
        icon_r, name_r, sell_r = cols(line, [84, 1.0, 120], 12)
        item_icon(ui, app, item_id, icon_r, count)
        ui.label(t(db.items[item_id].name), name_r, "small", color=tier_color(db.items[item_id].rank))
        if button(ui, f"+{rules.sell_price(db, item_id)}", place(sell_r, (120, 60), "center"), style="small"):
            app.act(run.sell, db, item_id)
    if button(ui, t("Leave the shop"), LEAVE, primary=True, style="tab"):
        app.act(run.leave_shop)


# --- конец забега -------------------------------------------------------------------

def draw_over(ui: Gui, app: TowerApp) -> None:
    t, run = ui.t, app.run
    body = panel(ui, OVER_PANEL, t("Defeat on floor {n}", n=run.floor))
    head, rest = cut_top(body, 60, 24)
    ui.label(t("Floors cleared: {n}   best: {best}", n=run.floor - 1, best=run.best), head, "title", color=TEXT)
    units = list(run.army.units.values())[:12]
    for cell, unit in zip(grid(rest, len(units), 6, 230, 16, 16), units):
        face, name_r = rows(cell, [1.0, 36], 4)
        portrait(ui, app, unit.definition.id, place(face, (face.width, face.width), "top"), dim=True)
        ui.label(f"{unit_name(t, unit)} {unit.state.level}", name_r, "small", align="center", color=DIM)
    if button(ui, t("New run"), NEW_RUN, primary=True, style="tab"):
        app.new_run()


# --- бой ----------------------------------------------------------------------------

def draw_battle(ui: Gui, app: TowerApp) -> None:
    """Поверх поля, как в UO: этаж и раунд слева сверху, скорость, пауза и пропуск справа.
    Остальное — на самом поле: плашки под бойцами, цифры урона, названия навыков."""
    t, show = ui.t, app.show
    boss = app.rules.is_boss(app.run.floor)
    plate = w.frame(ui, "header", FLOOR_PLATE)
    ui.label(t("Floor {n}", n=app.run.floor) + ("  " + t("(boss)") if boss else ""), plate, "heading",
             align="center", color=ENEMY if boss else GOLD)
    ui.label(t("Round {n}", n=max(1, show.round)), ROUND_LABEL, ui.ts("heading").but(outline=ui.colors["shadow"]), color=TEXT)
    for rect, speed, key in zip(SPEED_BUTTONS, SPEEDS, "123"):
        if button(ui, f"×{speed}", rect, selected=app.speed == speed, style="small"):
            app.speed = speed
    if button(ui, t("Continue") if app.paused else t("Pause"), PAUSE, selected=app.paused, style="small"):
        app.paused = not app.paused
    ui.tip(PAUSE, lambda: [(t("SPACE pause   1/2/3 speed   S skip   ENTER after the battle"), TEXT, "small")])
    if button(ui, t("Skip"), SKIP, enabled=not show.battle.finished, style="small"):
        app.skip()


def draw_result(ui: Gui, app: TowerApp) -> None:
    """Итог боя поверх поля: надпись UO WIN/LOSE (появление, затем покой) и кнопка «Дальше»
    (слой RESULT забирает мышь). Без игры — своя рамка с надписью."""
    if not app.battle_over():
        app.result_at = None
        return
    t = ui.t
    battle = app.show.battle
    won = battle.winner_id == battle.attacker.id
    if app.result_at is None:
        app.result_at = app.clock
    ui.block(BANNER, RESULT)

    def draw() -> None:
        if not uo_result(ui, app, won):
            body = w.frame(ui, "dialog", place(BANNER, (900, 300), "center"))
            head, _ = cut_top(inset(body, 20, 10), 110)
            ui.label(t("Victory!") if won else t("Defeat"), head, "huge", align="center", color=GOLD if won else ENEMY)
    ui.later(RESULT, draw)
    ui.later(RESULT, lambda: button(ui, t("Continue (ENTER)"), CONTINUE, primary=True, style="tab", layer=RESULT)
             and app.finish_battle())


def uo_result(ui: Gui, app: TowerApp, won: bool) -> bool:
    """Надпись итога из интерфейса UO по центру поля; False — нет игры."""
    if not UO_ANIM_ENABLED:
        return False
    from engine.uo import ui as uo_ui
    name = "RESULT_WIN" if won else "RESULT_LOSE"
    model = uo_ui.source().model("GUI", UO_RESULT_FILE)
    if model is None or f"{name}_OPEN" not in model.puppet.anims:
        return False
    tick = (app.clock - (app.result_at if app.result_at is not None else app.clock)) * 60 / 1000
    opening = model.length(f"{name}_OPEN")
    if tick < opening:
        anim, tick = f"{name}_OPEN", int(tick)
    else:
        anim = f"{name}_IDLE"
        tick = int(tick - opening) % max(1, model.length(anim))
    found = uo_ui.sprite(UO_RESULT_FILE, anim, tick, W / 1920)
    if found is not None:
        image, (ox, oy) = found
        ui.screen.blit(image, (BANNER.centerx - ox, BANNER.centery - 50 - oy))
    return True


SCREENS: dict[str, Callable[[Gui, TowerApp], None]] = {
    DRAFT: draw_draft, PREPARE: draw_prepare, REWARD: draw_reward, SHOP: draw_shop, OVER: draw_over,
}


def draw_frame(ui: Gui, app: TowerApp, window: Optional[Window] = None) -> None:
    """Кадр в ui.screen (1920x1280); с окном поле боя рисуется прямо в окно в полном разрешении."""
    ui.t = app.t
    if app.in_battle:
        ui.screen.fill((0, 0, 0, 0))            # в окне OpenGL поле рисуется в окно, интерфейс — поверх него
        if window is None or not window.gl:
            ui.screen.fill(BACK)
            app.show.draw(ui.screen, pygame.Rect(FIELD), app.clock)
        draw_battle(ui, app)
        draw_result(ui, app)
    else:
        ui.screen.fill(BACK)
        phase = UNIT if app.view in (UNIT, PROMOTE) and app.run.phase == PREPARE else app.run.phase
        scene = INVENTORY if app.view == INVENTORY and app.run.phase == PREPARE else phase
        background(ui, app, scene)
        draw_top(ui, app)
        SCREENS[app.run.phase](ui, app)
    if app.message:
        style = ui.ts("body", color="gold")
        width = min(W - 80, ui.width(app.message, style) + 60)
        box = place(MESSAGE, (width, 56), "center")
        ui.later(3, lambda: (w.frame(ui, "tooltip", box), ui.label(app.message, inset(box, 30, 0), style,
                                                                   align="center")))
    ui.end()
    if window is not None and window.gl:      # окно OpenGL: поле видеокартой в окно, интерфейс текстурой поверх
        window.clear()
        if app.in_battle:
            canvas = app.show.render(window.size, window_field(window), app.clock)
            if canvas is not None:
                canvas.present(window.size)
        window.present(window.canvas.get_rect())
    elif window is not None:
        window.present()


def main(max_frames: Optional[int] = None, save_path: Union[str, Path, None] = DEFAULT_SAVE_PATH,
         data_dir: Union[str, Path, None] = None, lang: Optional[str] = None) -> None:
    """max_frames нужен только для проверки запуска без окна (SDL_VIDEODRIVER=dummy)."""
    pygame.init()
    pygame.display.set_caption("Squad auto-battle — Tower")
    fitting = Window.presets(SIZES)
    # окно (и контекст OpenGL) — до забега: куклы и текстуры сразу грузятся в контекст окна
    window = Window(fitting[-1], SIZE, SIZES, alpha=True, gl=True)
    app = TowerApp(save_path, data_dir, lang=lang)
    if app.resolution in fitting and app.resolution != window.size:
        window.resize(app.resolution)
    app.resolution = window.size
    ui = make_ui(window.canvas)
    ui.transform = window.to_logical
    clock = pygame.time.Clock()
    frames, running = 0, True
    while running:
        dt = clock.tick(FPS)
        events = [window.logical_event(e) for e in pygame.event.get()]
        ui.begin(events)
        for event in events:
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                window.resize(event.size, resized=True)
                app.resolution = window.size
            elif event.type != pygame.KEYDOWN or ui.captured:
                continue
            elif event.key == pygame.K_ESCAPE:
                # назад по экранам подготовки; с главного экрана — выход
                running = app.in_battle or app.run.phase != PREPARE or go_back(app)
            elif event.key == pygame.K_F12:
                window.next_size()
                app.resolution = window.size
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
