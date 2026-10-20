"""Оформление окна башни в духе Unicorn Overlord поверх движка интерфейса uikit.

Здесь — то, что знает про игру: палитра, кнопки и панели башни, иконки предметов с тиром,
портреты и фигуры классов, навыки со стоимостью, сетка статов, плашки бойцов на поле.
Рамки, полосы, текст и раскладка — uikit (тема assets/ui/theme.json).

Логический размер интерфейса 1920x1280; окно масштабирует его целиком.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Optional

import pygame

from game.stats import Stat
from game.tower import DRAFT, OVER, PREPARE, REWARD, SHOP
from game.unit import Unit
from pygame_art import item_key, passive_key, skill_key, stat_key
from pygame_tips import (PASSIVE_COLOR, SKILL_COLOR, STAT_COLORS, item_tip, passive_tip, skill_tip, stat_tip,
                         tier_color)
from uikit import Gui, load_gui
from uikit import widgets as w
from uikit.layout import cols, inset, place

# Логический размер интерфейса башни и размеры окна для F12 (те, что не влезают в экран, пропускаются)
SIZE = W, H = 1920, 1280
SCALE = 1.92                             # во сколько раз крупнее базового интерфейса 1000x620 (таблица тактики)
SIZES = ((1200, 800), (1440, 960), (1620, 1080), (1920, 1280), (2400, 1600))
TOP_H = 84                               # верхняя полоса
M = 28                                   # поля экрана
GAP = 24                                 # между панелями
BOTTOM_H = 108                           # нижняя полоса с кнопками экрана
CONTENT_Y = TOP_H + 14                   # верх содержимого экранов
BOTTOM_Y = H - BOTTOM_H                  # верх нижней полосы
SCREEN = pygame.Rect(0, 0, W, H)
BODY = pygame.Rect(M, CONTENT_Y, W - 2 * M, BOTTOM_Y - CONTENT_Y - 10)      # между полосами
FULL_BODY = pygame.Rect(M, CONTENT_Y, W - 2 * M, H - CONTENT_Y - M)         # экраны без нижней полосы

# Палитра: ночная синева и золото (цвета подсказок и чисел; рамки — картинки темы)
BACK = (8, 12, 26)
PANEL_DARK = (10, 16, 34)
GOLD_LINE = (190, 158, 92)
GOLD_DIM = (150, 124, 72)
GOLD = (244, 208, 112)
TEXT = (238, 232, 216)
DIM = (160, 164, 182)
GREEN = (120, 214, 128)
EXP = (120, 200, 255)
AP_COLOR = (90, 160, 240)
PP_COLOR = (190, 120, 235)
ENEMY = (232, 98, 86)
ACCENTS = {DRAFT: (30, 88, 104), PREPARE: (34, 58, 116), REWARD: (118, 88, 34), SHOP: (32, 92, 62),
           OVER: (116, 36, 40), "battle": (66, 46, 108), "unit": (46, 50, 96)}
# Кнопки и выпадающие списки старого UI (таблица тактики) — в цветах башни
STYLE = dict(button=(24, 34, 66), hover=(38, 54, 98), selected=(96, 76, 34), disabled=(16, 20, 36),
             border=GOLD_DIM, accent=GOLD, radius=2)


def make_ui(canvas: pygame.Surface) -> Gui:
    ui = load_gui(canvas)
    ui.scale = SCALE
    ui.style = dict(STYLE)
    return ui


# --- картинки ------------------------------------------------------------------------

def icon(app: Any, key: Optional[str], side: int) -> Optional[pygame.Surface]:
    """Значок по ключу ArtBank (своя картинка или заглушка) квадратом side."""
    return app.art.image(key, (side, side)) if key else None


def own_icon(app: Any, key: str, side: int) -> Optional[pygame.Surface]:
    """Значок, только если для него нарисована своя картинка (не заглушка)."""
    return app.art.image(key, (side, side)) if app.art.has_own(key) else None


def background(ui: Gui, app: Any, screen_name: str) -> None:
    ui.screen.blit(app.art.image(f"bg/{screen_name}", SIZE, cover=True), (0, 0))


def shade(ui: Gui, rect: pygame.Rect, alpha: int = 170, color=(4, 6, 14)) -> None:
    """Полупрозрачная тёмная подложка (полосы экрана, текст поверх картинок)."""
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    layer.fill((*color, alpha))
    ui.screen.blit(layer, rect.topleft)


# --- кнопки и панели башни -----------------------------------------------------------

def button(ui: Gui, text: str, rect: pygame.Rect, primary: bool = False, enabled: bool = True,
           selected: bool = False, icon_key: Optional[str] = None, tab: bool = False, style: Optional[str] = None,
           layer: int = 0, app: Any = None) -> int:
    """Кнопка башни: обычная, главная (primary, золотая) или вкладка (tab). icon_key — значок слева
    (нужен app). Возвращает +1/-1 (левый/правый клик) или 0."""
    family = "tab" if tab else ("primary" if primary else "button")
    image = None
    if icon_key and app is not None:
        body = w.content(ui, family, rect)
        image = own_icon(app, icon_key, max(8, round(body.height * 0.82)))
    return w.button(ui, rect, text, image, family, selected=selected, enabled=enabled, style=style, layer=layer)


def panel(ui: Gui, rect: pygame.Rect, title: str = "", right: str = "") -> pygame.Rect:
    """Панель с заголовком; возвращает область содержимого."""
    return w.panel(ui, rect, title, right)


def bar(ui: Gui, rect: pygame.Rect, value: float, maximum: float, kind: str = "hp", text: str = "") -> pygame.Rect:
    return w.bar(ui, rect, value, maximum, kind, text)


def portrait(ui: Gui, app: Any, class_id: str, rect: pygame.Rect, kind: str = "normal", flip: bool = False,
             dim: bool = False) -> pygame.Rect:
    """Портрет класса в рамке: kind normal, leader (корона) или enemy (красная)."""
    body = w.content(ui, "portrait", rect)
    image = app.portraits.portrait(class_id, max(8, min(body.width, body.height)), flip)
    if dim:
        image = image.copy()
        image.fill((90, 84, 84, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return w.picture(ui, image, rect, "portrait", kind)


def figure(ui: Gui, app: Any, class_id: str, feet: tuple[int, int], height: int, flip: bool = False,
           alpha: int = 255, look: int = 0) -> pygame.Rect:
    """Фигура класса в полный рост, стоящая ногами в точке feet (height — рост человека в пикселях).
    Кукла UO стоит в стойке по кругу (battle.figures); без неё — картинка app.portraits.full.
    Возвращает прямоугольник фигуры."""
    pose = app.figures.pose(class_id, pygame.time.get_ticks(), max(8, height), flip, look)
    if pose is not None:
        sprite, origin = pose
        rect = sprite.get_rect(topleft=(round(feet[0] - origin[0]), round(feet[1] - origin[1])))
    else:
        sprite = app.portraits.full(class_id, (max(8, round(height * 0.6)), max(8, round(height))), flip)
        rect = sprite.get_rect(midbottom=feet)
    if alpha < 255:
        sprite = sprite.copy()
        sprite.set_alpha(alpha)
    ui.screen.blit(sprite, rect)
    return rect


def full_figure(ui: Gui, app: Any, class_id: str, size: tuple[int, int], feet: tuple[int, int],
                flip: bool = False, look: int = 0) -> pygame.Rect:
    """Фигура класса, вписанная в size и стоящая ногами в точке feet (карточки найма, экран бойца).
    Кукла UO стоит в стойке по кругу, иначе — картинка app.portraits.full."""
    figures = app.figures
    if figures.has(class_id, look):
        pose = figures.pose(class_id, pygame.time.get_ticks(), figures.fit(class_id, size, look), flip, look)
        if pose is not None:
            sprite, origin = pose
            rect = sprite.get_rect(topleft=(round(feet[0] - origin[0]), round(feet[1] - origin[1])))
            ui.screen.blit(sprite, rect)
            return rect
    image = app.portraits.full(class_id, size, flip)
    rect = image.get_rect(midbottom=feet)
    ui.screen.blit(image, rect)
    return rect


def crown(ui: Gui, app: Any, center: tuple[int, int], size: int = 30) -> None:
    """Корона лидера: своя картинка icon/leader или нарисованная."""
    if app.art.has_own("icon/leader"):
        image = app.art.image("icon/leader", (size, size))
        ui.screen.blit(image, image.get_rect(center=center))
        return
    x, y, s = center[0] - size // 2, center[1] - size // 3, size
    points = [(x, y + s * 0.7), (x, y), (x + s * 0.25, y + s * 0.35), (x + s * 0.5, y - s * 0.1),
              (x + s * 0.75, y + s * 0.35), (x + s, y), (x + s, y + s * 0.7)]
    pygame.draw.polygon(ui.screen, GOLD, points)
    pygame.draw.polygon(ui.screen, (90, 60, 20), points, 2)


def unit_name(t: Any, unit: Unit) -> str:
    """Имя бойца для интерфейса: личное, если есть, иначе класс."""
    return t(unit.nickname)


def class_line(t: Any, unit: Unit) -> str:
    return t(unit.definition.name)


def level_badge(ui: Gui, rect: pygame.Rect, level: int, align: str = "left") -> int:
    """«Ур. 7»: подпись мелко, число курсивом, как в UO. Возвращает правый край."""
    prefix = ui.t("Lv.")
    pw = ui.width(prefix, "label") + 6
    nw = ui.width(str(level), "level")
    x = rect.x if align == "left" else (rect.right - pw - nw if align == "right" else rect.centerx - (pw + nw) // 2)
    ui.label(prefix, pygame.Rect(x, rect.y, pw, rect.height), "label")
    ui.label(str(level), pygame.Rect(x + pw, rect.y, nw + 4, rect.height), "level")
    return x + pw + nw


# --- предметы и навыки ---------------------------------------------------------------

def item_icon(ui: Gui, app: Any, item_id: str, rect: pygame.Rect, count: int = 0,
              price: Optional[int] = None, layer: int = 0) -> int:
    """Иконка предмета в ячейке; линия цвета тира, значок тира, число; подсказка. Возвращает клик."""
    item = app.db.items.get(item_id)
    body = w.content(ui, "slot", rect)
    image = app.art.image(item_key(item) if item else "item", body.size)
    hover = ui.hovered(rect, layer)
    body = w.picture(ui, image, rect, "slot", "hover" if hover else "normal",
                     line=tier_color(item.rank) if item else (200, 60, 60), layer=layer)
    mark = own_icon(app, f"icon/tier{item.rank}", max(12, body.width // 3)) if item else None
    if mark is not None:
        ui.screen.blit(mark, (body.x - 2, body.y - 2))
    if count > 1:
        ui.label(f"×{count}", inset(body, 2), ui.ts("number", size=max(14, body.height // 3), outline=(6, 6, 12)),
                 align="right", valign="bottom")
    ui.tip(rect, lambda: item_tip(ui.t, app.db, item_id, price))
    return ui.clicked(rect, layer)


def diamonds(ui: Gui, app: Any, x: int, cy: int, count: int, kind: str, total: Optional[int] = None,
             size: int = 20) -> int:
    """Ромбики стоимости или запаса: kind ap (синие) или pp (фиолетовые). Возвращает правый край."""
    image = own_icon(app, f"icon/{kind}", size)
    color = AP_COLOR if kind == "ap" else PP_COLOR
    return w.diamonds(ui, x, cy, count, count if total is None else total, image, color=color, size=size)


def skill_chip(ui: Gui, app: Any, kind: str, entry_id: str, rect: pygame.Rect, unlock: int = 1,
               level: Optional[int] = None, costs: bool = False, layer: int = 0) -> None:
    """Навык или пассивка одной строкой: значок в кольце, название, стоимость ромбиками или замок
    с уровнем открытия; подсказка с описанием."""
    db, t = app.db, ui.t
    section = db.skills if kind == "skill" else db.passives
    locked = level is not None and unlock > level
    color = SKILL_COLOR if kind == "skill" else PASSIVE_COLOR
    body, _ = w.selectable(ui, rect, "row", layer=layer)
    ring = place(rect, (rect.height + 8, rect.height + 8), "left", (-6, 0))
    inner = ui.skin.body("skill", ring) if ui.skin.has("skill") else inset(ring, 4)
    image = app.art.image(skill_key(db, entry_id) if kind == "skill" else passive_key(db, entry_id), inner.size)
    if locked:
        image = image.copy()
        image.fill((90, 90, 90, 255), special_flags=pygame.BLEND_RGBA_MULT)
    w.frame(ui, "skill", ring)                    # кольцо с непрозрачной серединой — снизу, значок поверх
    ui.screen.blit(image, image.get_rect(center=inner.center))
    text_area = pygame.Rect(ring.right + 8, body.y, body.right - ring.right - 14, body.height)
    if locked:
        tag = t("lv {n}", n=unlock)
        tag_w = ui.width(tag, "small") + 34
        lock = own_icon(app, "icon/lock", 22)
        tag_rect = pygame.Rect(text_area.right - tag_w, body.y, tag_w, body.height)
        if lock is not None:
            ui.screen.blit(lock, lock.get_rect(midleft=(tag_rect.x, tag_rect.centery)))
        ui.label(tag, tag_rect, "small", align="right", color="red")
        text_area.width -= tag_w + 8
    elif costs and entry_id in section:
        entry = section[entry_id]
        ap, pp = (entry.ap_cost, entry.pp_cost) if kind == "skill" else (0, entry.pp_cost)
        width = (ap + pp) * 20
        x = text_area.right - width
        x = diamonds(ui, app, x, body.centery, ap, "ap", size=18)
        diamonds(ui, app, x, body.centery, pp, "pp", size=18)
        text_area.width -= width + 8
    name = t(section[entry_id].name) if entry_id in section else entry_id
    ui.label(name, text_area, "small", color=DIM if locked else color)
    tip = (lambda: skill_tip(t, db, entry_id, unlock, level)) if kind == "skill" \
        else (lambda: passive_tip(t, db, entry_id, unlock, level))
    ui.tip(rect, tip)


def class_entries(unit_or_definition) -> list[tuple[str, str, int]]:
    """(вид, id, уровень открытия) навыков и пассивок класса по порядку."""
    definition = getattr(unit_or_definition, "definition", unit_or_definition)
    return [("skill", s, definition.skill_levels.get(s, 1)) for s in definition.skills] + \
           [("passive", p, definition.passive_levels.get(p, 1)) for p in definition.passives]


GRADE_COLORS = {"S": (250, 214, 96), "A": (240, 128, 92), "B": (120, 210, 120), "C": (110, 180, 240),
                "D": (170, 170, 200), "E": (140, 140, 150), "F": (110, 100, 100)}


def grade_badge(ui: Gui, rect: pygame.Rect, letter: str) -> None:
    """Буква оценки стата (S..F, как в UO): насколько хорошо стат растёт у класса."""
    color = GRADE_COLORS.get(letter, DIM)
    side = min(rect.height - 6, rect.width - 2, 32)
    box = place(rect, (side, side), "center")
    if not ui.skin.draw(ui.screen, "grade", box):          # рамка оценки картинкой, если нарисована
        pygame.draw.rect(ui.screen, (8, 12, 24), box, border_radius=5)
        pygame.draw.rect(ui.screen, color, box, 2, border_radius=5)
    ui.label(letter, box, ui.ts("number", size=max(12, box.height - 8), color=color, outline=(4, 4, 10)), align="center")


def stat_rows(ui: Gui, app: Any, unit: Unit, rect: pygame.Rect, columns: int = 1, preview: Optional[dict] = None,
              stats: Optional[list[Stat]] = None, style: str = "body", grades: bool = False) -> int:
    """Статы строками в духе UO: значок своего цвета, название, значение справа, тонкая линия под
    строкой; preview — статы «если надеть»: новое значение и разница; grades — буква оценки стата класса
    (S..F) у правого края. Возвращает низ."""
    stats = list(Stat) if stats is None else stats
    lines = (len(stats) + columns - 1) // columns
    row_h = rect.height // max(1, lines)
    for i, (cell, stat) in enumerate(zip(_cells(rect, len(stats), columns, row_h), stats)):
        color = STAT_COLORS[stat]
        side = min(row_h - 6, 30)
        ui.screen.blit(app.tinted(stat_key(stat), side, color), (cell.x, cell.centery - side // 2))
        value = unit.stat(stat)
        shown, right = value, cell.right - 4
        letter = unit.definition.grades.get(stat.value) if grades else None
        if grades:
            if letter:
                grade_badge(ui, pygame.Rect(cell.right - 34, cell.y, 34, cell.height), letter)
            right -= 42
            cell = pygame.Rect(cell.x, cell.y, cell.width - 42, cell.height)
        if preview is not None and preview.get(stat, value) != value:
            shown = preview[stat]
            delta = shown - value
            tone = GREEN if delta > 0 else ENEMY
            box = ui.label(f"{delta:+d}", pygame.Rect(cell.right - 70, cell.y, 66, cell.height), "small",
                           align="right", color=tone)
            right = box.x - 26
            ax, ay = right + 13, cell.centery
            tri = [(ax - 7, ay + 5), (ax + 7, ay + 5), (ax, ay - 6)] if delta > 0 else \
                  [(ax - 7, ay - 5), (ax + 7, ay - 5), (ax, ay + 6)]
            pygame.draw.polygon(ui.screen, tone, tri)
            color = tone
        number = ui.label(str(shown), pygame.Rect(cell.x, cell.y, right - cell.x, cell.height), "number",
                          align="right", color=color)
        ui.label(ui.t(stat.value), pygame.Rect(cell.x + side + 10, cell.y, number.x - cell.x - side - 20, cell.height),
                 style)
        w.divider(ui, cell.x + side + 6, cell.right, cell.bottom - 3)
        ui.tip(cell.inflate(42 if grades else 0, 0).move(21 if grades else 0, 0),
               lambda s=stat, v=value, g=letter: stat_tip(ui.t, s, v) + ([(ui.t("Growth grade {g}", g=g),
                                                                            GRADE_COLORS.get(g, DIM), "small")] if g else []))
    return rect.y + lines * row_h


def _cells(rect: pygame.Rect, count: int, columns: int, row_h: int) -> list[pygame.Rect]:
    """Ячейки по колонкам: сначала вниз, потом вправо (как в UO)."""
    lines = (count + columns - 1) // columns
    columns_rects = cols(rect, [1.0] * columns, 28)
    return [pygame.Rect(columns_rects[i // lines].x, rect.y + (i % lines) * row_h, columns_rects[i // lines].width,
                        row_h) for i in range(count)]


def preview_stats(app: Any, unit: Unit, slot: int, item_id: Optional[str]) -> dict:
    """Статы, если в слот slot надеть item_id (None — снять): копия юнита, сам юнит не меняется."""
    state = replace(unit.state, equipment=list(unit.state.equipment))
    state.equipment[slot] = item_id
    ghost = Unit(unit.definition, state, app.db.items, strict=False)
    return {stat: ghost.stat(stat) for stat in Stat}


# --- бойцы на поле -------------------------------------------------------------------

NAMEPLATE = (260, 104)                   # плашка бойца на поле подготовки (при масштабе 1)


def nameplate(ui: Gui, app: Any, center_top: tuple[int, int], name: str, level: int, hp: int, max_hp: int,
              enemy: bool = False, leader: bool = False, boss: bool = False, k: float = 1.0) -> pygame.Rect:
    """Плашка бойца: имя по центру, ниже уровень и полоса HP. Ставится серединой верха в center_top."""
    size = (round(NAMEPLATE[0] * k), round(NAMEPLATE[1] * k))
    rect = pygame.Rect(0, 0, *size)
    rect.midtop = center_top
    body = w.family_frame(ui, "nameplate", rect, "enemy" if enemy else "normal")
    top, bottom = inset(body, 4, 0).copy(), inset(body, 2, 0).copy()
    top.height = body.height // 2
    bottom.y, bottom.height = body.y + body.height // 2, body.height - body.height // 2
    ui.label(name, top, ui.ts("name", size=round(24 * k)), align="center",
             color=ENEMY if boss else (GOLD if leader else TEXT))
    level_rect = pygame.Rect(bottom.x, bottom.y, round(56 * k), bottom.height)
    ui.label(str(level), level_rect, ui.ts("level", size=round(24 * k)), align="center")
    bar_rect = pygame.Rect(level_rect.right, bottom.centery - round(9 * k), bottom.right - level_rect.right - 2,
                           round(18 * k))
    w.bar(ui, bar_rect, hp, max_hp, "enemy" if enemy else "hp")
    if leader or boss:
        crown(ui, app, (rect.centerx, rect.y + 2), round(30 * k))
    return rect
