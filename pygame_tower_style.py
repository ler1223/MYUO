"""Оформление окна башни в духе Unicorn Overlord: тёмно-синие панели со скошенными углами,
золотая окантовка, шрифт с засечками; общие элементы экранов (панели, иконки, портреты,
фигуры, значки навыков со стоимостью, сетка статов).

Логический размер интерфейса 1920x1280; окно масштабирует его целиком.
"""
from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Optional

import pygame

from game.stats import Stat
from game.tower import DRAFT, OVER, PREPARE, REWARD, SHOP
from game.unit import Unit
from pygame_art import item_key, passive_key, skill_key, stat_key
from pygame_tips import (PASSIVE_COLOR, SKILL_COLOR, STAT_COLORS, item_tip, passive_tip, skill_tip, stat_tip,
                         tier_color)
from pygame_ui import FONT_NAMES, RED, UI, lighter

# Логический размер интерфейса башни и размеры окна для F12 (те, что не влезают в экран, пропускаются)
SIZE = W, H = 1920, 1280
SCALE = 1.92                             # во сколько раз крупнее базового интерфейса 1000x620
SIZES = ((1200, 800), (1440, 960), (1620, 1080), (1920, 1280), (2400, 1600))
TOP_H = 76                               # верхняя полоса
M = 24                                   # поля
CONTENT_Y = TOP_H + 16                   # верх содержимого экранов
BOTTOM_Y = H - 100                       # нижняя полоса с кнопками экрана
SERIF = ["georgia", "cambria", "constantia", "palatinolinotype", "bookantiqua", "timesnewroman", *FONT_NAMES]

# Палитра: ночная синева и золото
BACK = (8, 12, 26)
PANEL = (18, 28, 56)
PANEL_DARK = (10, 16, 34)
CELL = (26, 38, 72)
CELL_EMPTY = (16, 24, 48)
GOLD_LINE = (190, 158, 92)               # окантовка
GOLD_DIM = (120, 100, 62)
GOLD = (244, 208, 112)                   # заголовки, золото, выбор
TEXT = (238, 232, 216)                   # слоновая кость
DIM = (150, 156, 176)
GREEN = (110, 210, 120)
EXP = (110, 200, 255)
HP_BACK = (64, 30, 36)
AP_COLOR = (90, 160, 240)
PP_COLOR = (190, 120, 235)
ENEMY = (228, 96, 84)
ALLY = (110, 160, 240)
# Цвет экрана: шапки панелей и полоса под верхней строкой
ACCENTS = {DRAFT: (30, 88, 104), PREPARE: (34, 58, 116), REWARD: (118, 88, 34), SHOP: (32, 92, 62),
           OVER: (116, 36, 40), "battle": (66, 46, 108), "tactics": (50, 58, 108), "unit": (46, 50, 96)}
PRIMARY = (150, 110, 40)                 # главная кнопка экрана (бой, взять, выйти)
DANGER = (130, 44, 44)
# Кнопки и списки (UI.style)
STYLE = dict(button=(24, 34, 66), hover=(38, 54, 98), selected=(96, 76, 34), disabled=(16, 20, 36),
             border=GOLD_DIM, accent=GOLD, radius=2)
CUT = 14                                 # скос углов панелей


def tower_fonts() -> dict[str, pygame.font.Font]:
    return {
        "tiny": pygame.font.SysFont(SERIF, 17),
        "small": pygame.font.SysFont(SERIF, 21),
        "main": pygame.font.SysFont(SERIF, 26),
        "big": pygame.font.SysFont(SERIF, 34, bold=True),
        "title": pygame.font.SysFont(SERIF, 48, bold=True),
    }


def make_ui(canvas: pygame.Surface) -> UI:
    ui = UI(canvas, tower_fonts())
    ui.scale = SCALE
    ui.style = dict(STYLE)
    return ui


# --- рамки -------------------------------------------------------------------------

def cut_corners(rect: pygame.Rect, cut: int = CUT) -> list[tuple[int, int]]:
    r = rect
    return [(r.x + cut, r.y), (r.right - cut, r.y), (r.right, r.y + cut), (r.right, r.bottom - cut),
            (r.right - cut, r.bottom), (r.x + cut, r.bottom), (r.x, r.bottom - cut), (r.x, r.y + cut)]


class Skin:
    """Нарисованные рамки: assets/ui/frame/<вид>.png растягиваются по девяти частям (углы не тянутся).

    Виды: panel, header, button, button_hover, button_primary, button_selected, button_disabled, card, slot.
    Ширина нетянущегося края в пикселях картинки — assets/ui/frames.json: {"panel": {"border": 48,
    "scale": 0.5}} (scale — во сколько раз рисовать край на экране; по умолчанию border 32, scale 0.5).
    Нет картинки — плашка рисуется кодом (скошенные углы и золотая окантовка).
    """

    def __init__(self, art: Any):
        self.art = art
        path = art.folder / "frames.json"
        self.config: dict = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        self._cache: dict = {}

    def draw(self, screen: pygame.Surface, kind: str, rect: pygame.Rect) -> bool:
        key = f"frame/{kind}"
        if rect.width < 4 or rect.height < 4 or not self.art.has_own(key):
            return False
        cache = (kind, rect.size)
        if cache not in self._cache:
            config = self.config.get(kind, {})
            self._cache[cache] = nine_slice(self.art.find(key)[1], rect.size, int(config.get("border", 32)),
                                            float(config.get("scale", 0.5)))
            if len(self._cache) > 400:
                self._cache.pop(next(iter(self._cache)))
        screen.blit(self._cache[cache], rect.topleft)
        return True


def nine_slice(image: pygame.Surface, size: tuple[int, int], border: int, scale: float = 0.5) -> pygame.Surface:
    """Картинка рамки в размер size: углы как есть (с масштабом scale), края тянутся вдоль, середина — во все стороны."""
    w, h = image.get_size()
    b = max(1, min(border, w // 2 - 1, h // 2 - 1))
    t = max(1, min(round(b * scale), size[0] // 2, size[1] // 2))
    out = pygame.Surface(size, pygame.SRCALPHA)
    xs, ys = (0, b, w - b, w), (0, b, h - b, h)
    txs, tys = (0, t, size[0] - t, size[0]), (0, t, size[1] - t, size[1])
    for i in range(3):
        for j in range(3):
            src = pygame.Rect(xs[i], ys[j], xs[i + 1] - xs[i], ys[j + 1] - ys[j])
            dst = pygame.Rect(txs[i], tys[j], txs[i + 1] - txs[i], tys[j + 1] - tys[j])
            if src.width > 0 and src.height > 0 and dst.width > 0 and dst.height > 0:
                out.blit(pygame.transform.smoothscale(image.subsurface(src), dst.size), dst.topleft)
    return out


SKIN: Optional[Skin] = None       # задаёт окно башни (TowerApp); без него всё рисуется кодом


def plate(ui: UI, rect: pygame.Rect, fill=PANEL, border=GOLD_LINE, cut: int = CUT, width: int = 2,
          kind: str = "card") -> None:
    """Плашка: нарисованная рамка вида kind, если она есть, иначе скошенные углы и двойная золотая окантовка."""
    if SKIN is not None and SKIN.draw(ui.screen, kind, rect):
        return
    pygame.draw.polygon(ui.screen, fill, cut_corners(rect, cut))
    pygame.draw.polygon(ui.screen, border, cut_corners(rect, cut), width)
    if rect.width > 3 * cut and rect.height > 3 * cut:
        inner = rect.inflate(-10, -10)
        pygame.draw.polygon(ui.screen, lighter(border, -70), cut_corners(inner, max(2, cut - 4)), 1)


def panel(ui: UI, rect: pygame.Rect, accent, title: str = "", right: str = "") -> pygame.Rect:
    """Панель с цветной шапкой и золотым заголовком. Возвращает область под шапкой."""
    plate(ui, rect, PANEL, kind="panel")
    if not title:
        return rect.inflate(-12, -12)
    head = pygame.Rect(rect.x + 6, rect.y + 6, rect.width - 12, 52)
    if SKIN is None or not SKIN.draw(ui.screen, "header", head):
        band = pygame.Surface(head.size)
        for x in range(head.width):                 # шапка — градиент цвета экрана к синеве
            k = x / head.width
            band.fill(tuple(round(a * (1 - k) + b * k) for a, b in zip(accent, PANEL)), (x, 0, 1, head.height))
        ui.screen.blit(band, head.topleft)
    pygame.draw.line(ui.screen, GOLD_LINE, (head.x + 8, head.bottom), (head.right - 8, head.bottom), 2)
    ui.text(title, head.x + 18, head.y + 8, GOLD, "big", head.width - 36)
    if right:
        img = ui.fonts["main"].render(right, True, TEXT)
        ui.screen.blit(img, (head.right - img.get_width() - 18, head.y + 12))
    return pygame.Rect(rect.x, head.bottom + 2, rect.width, rect.bottom - head.bottom - 2)


def button(ui: UI, text: str, rect: pygame.Rect, primary: bool = False, enabled: bool = True,
           selected: bool = False, font: str = "main") -> int:
    """Кнопка в стиле UO: скошенные углы, золотая рамка, главная — золотая."""
    hover = enabled and ui.hovered(rect)
    if not enabled:
        fill, border, color, kind = STYLE["disabled"], GOLD_DIM, DIM, "button_disabled"
    elif primary:
        fill, border, color, kind = (lighter(PRIMARY, 24) if hover else PRIMARY), GOLD, TEXT, "button_primary"
    elif selected:
        fill, border, color, kind = STYLE["selected"], GOLD, GOLD, "button_selected"
    else:
        fill, border, color = (STYLE["hover"] if hover else STYLE["button"]), (GOLD if hover else GOLD_LINE), TEXT
        kind = "button_hover" if hover and SKIN is not None and SKIN.art.has_own("frame/button_hover") else "button"
    plate(ui, rect, fill, border, cut=min(12, rect.height // 3), kind=kind)
    img = ui.fonts[font].render(text, True, color)
    if img.get_width() > rect.width - 16:
        img = pygame.transform.smoothscale(img, (rect.width - 16, img.get_height()))
    ui.screen.blit(img, img.get_rect(center=rect.center))
    return ui.clicked(rect) if enabled else 0


def bar(ui: UI, rect: pygame.Rect, value: float, maximum: float, color, back=HP_BACK, label: str = "") -> None:
    pygame.draw.rect(ui.screen, back, rect)
    share = 0 if maximum <= 0 else max(0.0, min(1.0, value / maximum))
    if share > 0:
        pygame.draw.rect(ui.screen, color, (rect.x, rect.y, max(2, round(rect.width * share)), rect.height))
        pygame.draw.rect(ui.screen, lighter(color, 50), (rect.x, rect.y, max(2, round(rect.width * share)), 2))
    pygame.draw.rect(ui.screen, GOLD_DIM, rect, 1)
    if label:
        img = ui.fonts["tiny"].render(label, True, TEXT)
        ui.screen.blit(img, img.get_rect(center=rect.center))


def framed(ui: UI, image: pygame.Surface, rect: pygame.Rect, border=GOLD_LINE, back=PANEL_DARK, width: int = 2) -> None:
    """Картинка в рамке-ячейке. С нарисованной рамкой slot цвет (тир, сторона) — тонкой линией внутри."""
    plate(ui, rect, back, border, cut=min(10, rect.width // 6), width=width, kind="slot")
    ui.screen.blit(image, image.get_rect(center=rect.center))
    if SKIN is not None and SKIN.art.has_own("frame/slot") and border != GOLD_LINE:
        pygame.draw.rect(ui.screen, border, rect.inflate(-8, -8), 2)


def portrait(ui: UI, app: Any, class_id: str, rect: pygame.Rect, border=GOLD_LINE, flip: bool = False) -> None:
    image = app.portraits.portrait(class_id, min(rect.width, rect.height) - 8, flip)
    framed(ui, image, rect, border)


def figure(ui: UI, app: Any, class_id: str, feet: tuple[int, int], height: int, flip: bool = False,
           alpha: int = 255) -> pygame.Rect:
    """Фигура класса в полный рост, стоящая ногами в точке feet. Возвращает её прямоугольник."""
    bank = app.stage.bank
    sprite_id = bank.sprite_for(class_id)
    sprite, _ = bank.unit_sprite(sprite_id, max(8, round(height * bank.ratio(sprite_id))), flip)
    if alpha < 255:
        sprite = sprite.copy()
        sprite.set_alpha(alpha)
    rect = sprite.get_rect(midbottom=feet)
    ui.screen.blit(sprite, rect)
    return rect


def crown(ui: UI, app: Any, center: tuple[int, int], size: int = 30) -> None:
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


def item_icon(ui: UI, app: Any, item_id: str, rect: pygame.Rect, count: int = 0,
              price: Optional[int] = None) -> int:
    """Иконка предмета в рамке цвета тира, с числом и подсказкой. Возвращает клик (+1/-1/0)."""
    item = app.db.items.get(item_id)
    border = tier_color(item.tier) if item else RED
    key = item_key(item) if item else "item"
    image = app.art.image(key, (rect.width - 14, rect.height - 14))
    framed(ui, image, rect, lighter(border, 40) if ui.hovered(rect) else border)
    if count > 1:
        img = ui.fonts["small"].render(f"x{count}", True, TEXT)
        back = pygame.Rect(rect.right - img.get_width() - 10, rect.bottom - img.get_height() - 4,
                           img.get_width() + 8, img.get_height())
        pygame.draw.rect(ui.screen, (0, 0, 0), back)
        ui.screen.blit(img, (back.x + 4, back.y))
    ui.tip(rect, lambda: item_tip(ui.t, app.db, item_id, price))
    return ui.clicked(rect)


def diamonds(ui: UI, x: int, y: int, count: int, color, size: int = 14) -> int:
    """Ромбики стоимости (AP синие, PP фиолетовые), как в UO. Возвращает правый край."""
    for i in range(count):
        cx = x + i * (size + 3) + size // 2
        points = [(cx, y), (cx + size // 2, y + size // 2), (cx, y + size), (cx - size // 2, y + size // 2)]
        pygame.draw.polygon(ui.screen, color, points)
        pygame.draw.polygon(ui.screen, lighter(color, 70), points, 1)
    return x + count * (size + 3)


def skill_chip(ui: UI, app: Any, kind: str, entry_id: str, rect: pygame.Rect, unlock: int = 1,
               level: Optional[int] = None, costs: bool = False) -> None:
    """Навык или пассивка: значок, название, стоимость, замок до уровня открытия; подсказка с описанием."""
    db, t = app.db, ui.t
    section = db.skills if kind == "skill" else db.passives
    locked = level is not None and unlock > level
    color = SKILL_COLOR if kind == "skill" else PASSIVE_COLOR
    pygame.draw.rect(ui.screen, lighter(CELL, 14) if ui.hovered(rect) else CELL, rect)
    pygame.draw.line(ui.screen, color if not locked else DIM, rect.topleft, rect.bottomleft, 3)
    side = rect.height - 6
    key = skill_key(entry_id) if kind == "skill" else passive_key(entry_id)
    icon = app.art.image(key, (side, side))
    if locked:
        icon = icon.copy()
        icon.fill((90, 90, 90, 255), special_flags=pygame.BLEND_RGBA_MULT)
    ui.screen.blit(icon, (rect.x + 6, rect.y + 3))
    name = t(section[entry_id].name) if entry_id in section else entry_id
    room = rect.width - side - 22
    right = rect.right - 10
    if locked:                                    # уровень открытия — значок справа, имя не обрезает его
        lock = ui.fonts["tiny"].render(t("lv {n}", n=unlock), True, TEXT)
        badge = pygame.Rect(right - lock.get_width() - 10, rect.centery - 11, lock.get_width() + 10, 22)
        pygame.draw.rect(ui.screen, (90, 50, 50), badge)
        ui.screen.blit(lock, (badge.x + 5, badge.y + 2))
        room -= badge.width + 8
    elif costs and entry_id in section:
        entry = section[entry_id]
        ap, pp = (entry.ap_cost, entry.pp_cost) if kind == "skill" else (0, entry.pp_cost)
        width = (ap + pp) * 17
        x = right - width
        x = diamonds(ui, x, rect.centery - 7, ap, AP_COLOR)
        diamonds(ui, x, rect.centery - 7, pp, PP_COLOR)
        room -= width + 8
    ui.text(name, rect.x + side + 16, rect.y + (rect.height - ui.fonts["small"].get_height()) // 2,
            DIM if locked else color, "small", room)
    tip = (lambda: skill_tip(t, db, entry_id, unlock, level)) if kind == "skill" \
        else (lambda: passive_tip(t, db, entry_id, unlock, level))
    ui.tip(rect, tip)


def class_entries(unit_or_definition) -> list[tuple[str, str, int]]:
    """(вид, id, уровень открытия) навыков и пассивок класса по порядку."""
    definition = getattr(unit_or_definition, "definition", unit_or_definition)
    return [("skill", s, definition.skill_levels.get(s, 1)) for s in definition.skills] + \
           [("passive", p, definition.passive_levels.get(p, 1)) for p in definition.passives]


def stat_grid(ui: UI, app: Any, unit: Unit, x: int, y: int, cols: int, col_w: int, row_h: int = 30,
              preview: Optional[dict] = None) -> int:
    """Статы со значками своего цвета и подсказками; preview — статы «если надеть»: стрелки разницы."""
    stats = list(Stat)
    rows = (len(stats) + cols - 1) // cols
    for i, stat in enumerate(stats):
        cx, cy = x + (i // rows) * col_w, y + (i % rows) * row_h
        color = STAT_COLORS[stat]
        icon = app.tinted(stat_key(stat), row_h - 10, color)
        ui.screen.blit(icon, (cx, cy + 5))
        ui.text(ui.t(stat.value), cx + row_h, cy + 3, DIM, "small", col_w - row_h - 120)
        value = unit.stat(stat)
        shown = value
        right = cx + col_w - 16
        if preview is not None and preview.get(stat, value) != value:
            shown = preview[stat]
            delta = shown - value
            arrow_color = GREEN if delta > 0 else ENEMY
            img = ui.fonts["small"].render(f"{delta:+d}", True, arrow_color)
            ui.screen.blit(img, (right - img.get_width(), cy + 4))
            right -= img.get_width() + 22
            ax, ay = right + 10, cy + row_h // 2
            tri = [(ax - 7, ay + 5), (ax + 7, ay + 5), (ax, ay - 6)] if delta > 0 else \
                  [(ax - 7, ay - 5), (ax + 7, ay - 5), (ax, ay + 6)]
            pygame.draw.polygon(ui.screen, arrow_color, tri)
            color = arrow_color
        img = ui.fonts["main"].render(str(shown), True, color)
        ui.screen.blit(img, (right - img.get_width() - 4, cy + 1))
        ui.tip(pygame.Rect(cx, cy, col_w - 10, row_h), lambda s=stat, v=value: stat_tip(ui.t, s, v))
    return y + rows * row_h


def background(ui: UI, app: Any, screen_name: str) -> None:
    ui.screen.blit(app.art.image(f"bg/{screen_name}", SIZE, cover=True), (0, 0))


def preview_stats(app: Any, unit: Unit, slot: int, item_id: Optional[str]) -> dict:
    """Статы, если в слот slot надеть item_id (None — снять): копия юнита, сам юнит не меняется."""
    state = replace(unit.state, equipment=list(unit.state.equipment))
    state.equipment[slot] = item_id
    ghost = Unit(unit.definition, state, app.db.items, strict=False)
    return {stat: ghost.stat(stat) for stat in Stat}
