"""Подготовка к этажу в духе Unicorn Overlord.

Виды (app.view):
  main   — слева наш отряд, справа враги этажа в их построении; бойцы стоят фигурами на клетках
  squad  — справа вместо врагов все бойцы армии; расстановка перетаскиванием (на клетку — поставить
           или поменяться, с поля в список — в резерв)
  units  — полный список бойцов: уровень, опыт, HP, место в отряде, снаряжение
  unit   — редактор бойца: большая фигура, вкладки «Статус», «Снаряжение», «Тактика»
Клик по бойцу (без перетаскивания) где угодно открывает его редактор.

Раскладка — прямоугольники ниже, собранные функциями uikit.layout; отрисовка и тесты берут их отсюда.
Слои: 0 — панели и фигуры, 1 — плашки бойцов над всеми фигурами, 5 — перетаскиваемый боец.
"""
from __future__ import annotations

import math
from typing import Any, Optional

import pygame

from dataclasses import replace

from game import promotion
from game.stats import Stat  # noqa: F401  (pp.Stat в тестах)
from game.rating import rate_formation, rate_squad, rate_unit
from game.unit import Unit
from pygame_tips import unit_tip
from pygame_tower_inventory import draw_inventory
from pygame_tower_unit import (ART, CONTENT, EDITOR, EQUIPMENT, FIELD_TOGGLE, NONE_ITEM, PROMOTE_AREA,  # noqa: F401
                               PROMOTE_BUTTON, STATUS, TABS, TACTICS, draw_editor, draw_unit_art, leader_kind,
                               place_text, power_tip)
from pygame_tower_style import (BODY, BOTTOM_H, BOTTOM_Y, DIM, ENEMY, GAP, GOLD, GREEN, M, TEXT, W, bar, button,  # noqa
                                class_line, figure, full_figure, item_icon, level_badge, nameplate, panel, portrait,
                                preview_stats, shade, skill_chip, unit_name)
from uikit import Gui
from uikit import widgets as w
from uikit.layout import cols, cut_left, cut_top, grid, inset, place, row_of, rows

MAIN, SQUAD, UNITS, UNIT, INVENTORY, PROMOTE = "main", "squad", "units", "unit", "inventory", "promote"
SNAP = 1.6                          # прилипание: до скольких «радиусов клетки» от курсора
DRAG_MIN = 12                       # дальше стольких пикселей от нажатия — уже перетаскивание
PLATES, DRAG = 1, 5                 # слои: плашки над фигурами, перетаскиваемый боец над всем

# --- раскладка ------------------------------------------------------------------------

PANEL_PAD = (38, 92, 38, 36)        # от края панели с заголовком до содержимого (uikit.widgets.panel)
HALF_L, HALF_R = cols(BODY, [1.0, 1.0], GAP)
BOTTOM = pygame.Rect(0, BOTTOM_Y, W, BOTTOM_H)
BOTTOM_ROW = inset(BOTTOM, M, 16, M, 14)
SQUAD_BUTTON, UNITS_BUTTON, INVENTORY_BUTTON = row_of(BOTTOM_ROW, [300, 300, 300], 16, "left")
FIGHT = place(BOTTOM_ROW, (420, BOTTOM_ROW.height), "right")
BACK, PREV, NEXT = row_of(BOTTOM_ROW, [260, 250, 250], 16, "left")
COUNTER = pygame.Rect(NEXT.right + 24, BOTTOM_ROW.y, 200, BOTTOM_ROW.height)
def promote_card(i: int, count: int) -> pygame.Rect:
    """i-я карточка пути повышения из count."""
    return cols(PROMOTE_AREA, [1.0] * max(1, count), 20)[i]


def promote_button(card: pygame.Rect) -> pygame.Rect:
    return place(inset(card, 24, 0, 24, 22), (card.width - 48, 72), "bottom")
# списки
ROSTER_AREA = inset(HALF_R, *PANEL_PAD)
ROSTER_COLS, ROSTER_CARD_H = 2, 128
LIST = BODY
LIST_HEAD = pygame.Rect(LIST.x + PANEL_PAD[0], LIST.y + PANEL_PAD[1], LIST.width - 2 * PANEL_PAD[0], 34)
LIST_AREA = pygame.Rect(LIST_HEAD.x, LIST_HEAD.bottom + 10, LIST_HEAD.width,
                        LIST.bottom - PANEL_PAD[3] - LIST_HEAD.bottom - 10)
LIST_ROW = 116


def list_columns(row: pygame.Rect) -> list[pygame.Rect]:
    """Колонки строки списка юнитов: портрет, имя, уровень, HP, место, снаряжение."""
    return cols(row, [96, 1.0, 190, 250, 300, 430], 20)


def roster_card(i: int) -> pygame.Rect:
    """i-я видимая карточка армии в виде «Отряд»."""
    return grid(ROSTER_AREA, i + 1, ROSTER_COLS, ROSTER_CARD_H, 14, 12)[i]


def unit_row(i: int) -> pygame.Rect:
    """i-я видимая строка списка юнитов."""
    return pygame.Rect(LIST_AREA.x, LIST_AREA.y + i * LIST_ROW, LIST_AREA.width, LIST_ROW - 10)


def unit_point(app: Any, uid: int) -> tuple[int, int]:
    """Точка на фигуре бойца, стоящего в отряде (для мыши и тестов)."""
    formation = app.run.squad.formation
    area = field_area(HALF_L)
    x, y, scale = spots(area, formation.rows, formation.cols, False)[formation.position_of(uid)]
    return round(x), round(y - unit_height(area, formation.cols) * scale * 0.4)


def cell_point(app: Any, row: int, col: int) -> tuple[int, int]:
    """Середина клетки земли нашего поля."""
    formation = app.run.squad.formation
    x, y, _scale = spots(field_area(HALF_L), formation.rows, formation.cols, False)[(row, col)]
    return round(x), round(y)


# --- поле отряда в перспективе ------------------------------------------------------

def field_area(half: pygame.Rect) -> pygame.Rect:
    return inset(half, 30, 96, 30, 70)


def spots(area: pygame.Rect, rows_: int, cols_: int, mirror: bool) -> dict[tuple[int, int], tuple[float, float, float]]:
    """Клетка (ряд, колонна) -> (x, y ног, масштаб). Колонны уходят вглубь (дальняя сверху и мельче),
    передний ряд (0) ближе к середине экрана: у нас справа, у врага (mirror) слева."""
    top = area.height * 0.30
    depth = (area.height - top - 40) / max(1, cols_ - 1)
    dx = area.width * 0.84 / rows_
    result = {}
    for col in range(cols_):
        k = col / max(1, cols_ - 1)
        scale = 0.78 + 0.22 * k
        y = area.y + top + col * depth
        for row in range(rows_):
            lateral = (row + 0.5) * dx + (k - 0.5) * dx * 0.22
            x = area.right - area.width * 0.08 - lateral if not mirror else area.x + area.width * 0.08 + lateral
            result[(row, col)] = (x, y, scale)
    return result


def tile_rect(spot: tuple[float, float, float], dx: float) -> pygame.Rect:
    x, y, scale = spot
    width = dx * 0.86 * scale
    return pygame.Rect(round(x - width / 2), round(y - width * 0.17), round(width), round(width * 0.34))


def unit_height(area: pygame.Rect, cols_: int) -> float:
    return (area.height * 0.70 - 40) / max(1, cols_ - 1) * 0.86 if cols_ > 1 else area.height * 0.4


def draw_field(ui: Gui, app: Any, half: pygame.Rect, entries: list[dict], rows_: int, cols_: int, mirror: bool,
               hot: Optional[tuple[int, int]] = None) -> list[tuple[pygame.Rect, tuple[int, int], Optional[int]]]:
    """Клетки и стоящие на них фигуры. entries: dict(uid, class_id, name, level, hp, max_hp, row, col, leader, boss).
    Возвращает цели для мыши: (прямоугольник, клетка, uid или None), ближние позже."""
    area = field_area(half)
    places = spots(area, rows_, cols_, mirror)
    dx = area.width * 0.84 / rows_
    height = unit_height(area, cols_)
    by_cell = {(e["row"], e["col"]): e for e in entries}
    dragging_uid = app.drag[0] if app.drag else None
    targets = []
    side = "enemy" if mirror else "ally"
    for col in range(cols_):                                 # дальние колонны первыми
        for row in range(rows_):
            tile = tile_rect(places[(row, col)], dx)
            lit = hot == (row, col)
            image = app.art.image(f"field/tile_{side}_hot" if lit else f"field/tile_{side}", tile.size) \
                if app.art.has_own(f"field/tile_{side}") else None
            if image is not None:
                ui.screen.blit(pygame.transform.smoothscale(image, tile.size), tile.topleft)
            else:
                pygame.draw.ellipse(ui.screen, (70, 30, 36) if mirror else (24, 40, 84), tile)
                pygame.draw.ellipse(ui.screen, GOLD if lit else (150, 124, 72), tile, 3 if lit else 2)
            targets.append((tile, (row, col), None))
    plate_k = min(1.0, dx * 0.96 / 260)
    for col in range(cols_):
        for row in range(rows_):
            entry = by_cell.get((row, col))
            if entry is None:
                continue
            x, y, scale = places[(row, col)]
            alpha = 90 if entry.get("uid") is not None and entry.get("uid") == dragging_uid else 255
            rect = figure(ui, app, entry["class_id"], (round(x), round(y + 4)), round(height * scale), mirror, alpha,
                          entry.get("look", 0))
            targets.append((rect, (row, col), entry.get("uid")))
            if entry.get("tip"):
                ui.tip(rect, entry["tip"])
            # плашка — над всеми фигурами (задние ряды не прячутся за передними), серединой под ногами
            ui.later(PLATES, lambda e=entry, x=x, y=y, s=scale: nameplate(
                ui, app, (round(x), round(y + 10 * s)), e["name"], e["level"], e["hp"], e["max_hp"], mirror,
                bool(e.get("leader")), bool(e.get("boss")), plate_k * (0.86 + 0.14 * s)))
    return targets


def squad_entries(app: Any) -> list[dict]:
    run, t = app.run, app.t
    formation = run.squad.formation
    return [dict(uid=u.uid, class_id=u.definition.id, look=u.state.look, name=unit_name(t, u), level=u.state.level, hp=u.hp,
                 max_hp=u.max_hp, row=formation.position_of(u.uid)[0], col=formation.position_of(u.uid)[1],
                 leader=run.squad.leader_uid == u.uid, tip=lambda u=u: unit_tip(app.t, app.db, u))
            for u in formation.units]


def enemy_entries(app: Any) -> list[dict]:
    boss = app.rules.is_boss(app.run.floor)
    entries = []
    for i, (class_id, level, gear, row, col) in enumerate(app.enemies()):
        if class_id not in app.db.units:
            continue
        unit = app.db.create_unit(class_id, 0, level, gear)
        entries.append(dict(uid=None, class_id=class_id, name=app.t(unit.name), level=level, hp=unit.max_hp,
                            max_hp=unit.max_hp, row=row, col=col, boss=boss and i == 0,
                            tip=lambda u=unit: unit_tip(app.t, app.db, u)))
    return entries


# --- главный экран и расстановка -------------------------------------------------------

def draw_prepare(ui: Gui, app: Any) -> None:
    units = {u.uid: u for u in app.run.army.units.values()}
    if app.selected not in units:
        app.selected = next(iter(units), None)
    if app.view == UNIT and app.selected is not None:
        draw_unit(ui, app, units[app.selected])
        return
    if app.view == PROMOTE and app.selected is not None:
        draw_promotion(ui, app, units[app.selected])
        return
    if app.view == UNITS:
        draw_units(ui, app)
    elif app.view == INVENTORY:
        draw_inventory(ui, app, open_unit)
    else:
        draw_formation(ui, app)
    draw_bottom(ui, app)


def bottom_strip(ui: Gui) -> None:
    shade(ui, BOTTOM, 200)
    w.divider(ui, 0, W, BOTTOM.y)


def draw_bottom(ui: Gui, app: Any) -> None:
    bottom_strip(ui)
    t = ui.t
    if button(ui, t("Squad"), SQUAD_BUTTON, selected=app.view == SQUAD, icon_key="icon/squad_tab", app=app):
        app.view = MAIN if app.view == SQUAD else SQUAD
    if button(ui, t("Units"), UNITS_BUTTON, selected=app.view == UNITS, icon_key="icon/units", app=app):
        app.view = MAIN if app.view == UNITS else UNITS
    if button(ui, t("Inventory"), INVENTORY_BUTTON, selected=app.view == INVENTORY, icon_key="icon/inventory", app=app):
        app.view = MAIN if app.view == INVENTORY else INVENTORY
    formation = app.run.squad.formation
    note = pygame.Rect(INVENTORY_BUTTON.right + 30, BOTTOM_ROW.y, FIGHT.x - INVENTORY_BUTTON.right - 60,
                       BOTTOM_ROW.height)
    ui.label(t("Fielded {n}/{max}", n=len(formation), max=formation.max_units), note, "heading")
    if button(ui, t("Fight!"), FIGHT, primary=True, enabled=bool(app.run.fielded), style="tab"):
        app.start_battle()


def draw_formation(ui: Gui, app: Any) -> None:
    t, run = ui.t, app.run
    formation = run.squad.formation
    shop_in = next((k for k in range(1, 1000) if app.rules.shop_after(run.floor + k - 1)), None) \
        if app.rules.data["shop"]["every"] > 0 else None
    ours = rate_formation(formation, app.db)
    panel(ui, HALF_L, t("Your squad"), f"{t('Power {n}', n=ours.power)}   {len(formation)}/{formation.max_units}")
    power_tip(ui, pygame.Rect(HALF_L.right - 380, HALF_L.y + 20, 360, 70), ours)
    targets = draw_field(ui, app, HALF_L, squad_entries(app), formation.rows, formation.cols, False,
                         hot=snap_cell(app, ui.mouse) if dragging(ui, app) else None)
    if shop_in:
        ui.label(t("shop after {n} more floor(s)", n=shop_in),
                 pygame.Rect(HALF_L.x + PANEL_PAD[0], HALF_L.bottom - 70, HALF_L.width - 80, 32), "label")
    roster_targets: list[tuple[pygame.Rect, Optional[int]]] = []
    if app.view == SQUAD:
        roster_targets = draw_roster(ui, app)
    else:
        boss = app.rules.is_boss(run.floor)
        title = t("Enemies of floor {n}", n=run.floor) + ("  " + t("(boss)") if boss else "")
        theirs = enemy_rating(app)
        panel(ui, HALF_R, title, f"{t('Power {n}', n=theirs.power)}   {t('{n} units', n=len(app.enemies()))}")
        power_tip(ui, pygame.Rect(HALF_R.right - 380, HALF_R.y + 20, 360, 70), theirs)
        grid_size = app.rules.squad_size(run.floor)
        draw_field(ui, app, HALF_R, enemy_entries(app), grid_size.rows, grid_size.cols, True)
    handle_drag(ui, app, targets, roster_targets)


def draw_roster(ui: Gui, app: Any) -> list[tuple[pygame.Rect, Optional[int]]]:
    """Все бойцы армии справа: карточки, которые перетаскиваются на поле."""
    t, run = ui.t, app.run
    panel(ui, HALF_R, t("Army"), t("drag a fighter onto the field"))
    formation = run.squad.formation
    targets = [(HALF_R, None)]                          # отпустить над списком — убрать в резерв
    units = ordered_units(app)
    lines = max(1, (ROSTER_AREA.height + 12) // (ROSTER_CARD_H + 12))
    offset = ui.scroll("tower-roster", ROSTER_AREA, (len(units) + ROSTER_COLS - 1) // ROSTER_COLS, lines) * ROSTER_COLS
    for i, unit in enumerate(units[offset:offset + lines * ROSTER_COLS]):
        card = roster_card(i)
        fielded = formation.position_of(unit.uid) is not None
        held = app.drag is not None and app.drag[0] == unit.uid
        body, _ = w.selectable(ui, card, "card", selected=fielded)
        face, info = cut_left(body, body.height, 14)
        portrait(ui, app, unit.definition.id, face, leader_kind(app, unit), dim=held)
        name_r, class_r, exp_r = rows(info, [1.0, 1.0, 22], 2)
        ui.label(unit_name(t, unit), name_r, "body", color=DIM if held else TEXT)
        right = level_badge(ui, class_r, unit.state.level)
        ui.label(class_line(t, unit), pygame.Rect(right + 14, class_r.y, info.right - right - 14, class_r.height),
                 "small", color=DIM)
        bar(ui, exp_r.inflate(0, -2), unit.state.exp, app.rules.exp.per_level, "exp")
        if fielded:
            ui.label(t("in squad"), name_r, "tiny", align="right", color=GOLD)
        if promotion.available(unit, app.db):
            ui.label("↑", class_r, "heading", align="right", color=GOLD)
            ui.tip(class_r, lambda: [(t("Promotion!"), GOLD, "main")])
        ui.tip(card, lambda u=unit: unit_tip(t, app.db, u))
        targets.append((card, unit.uid))
    return targets


def dragging(ui: Gui, app: Any) -> bool:
    """Бойца уже тащат (кнопка нажата на бойце, и курсор ушёл дальше DRAG_MIN)."""
    return app.drag is not None and math.dist(ui.mouse, app.drag[1]) >= DRAG_MIN


def snap_cell(app: Any, feet: tuple[float, float]) -> Optional[tuple[int, int]]:
    """Клетка нашего поля, к которой прилипают ноги перетаскиваемого бойца: ближайшая к курсору
    (расстояние меряется в размерах клетки, по глубине клетки ближе друг к другу), если она не дальше SNAP."""
    formation = app.run.squad.formation
    area = field_area(HALF_L)
    dx = area.width * 0.84 / formation.rows
    best, best_d = None, SNAP
    for cell, (x, y, scale) in spots(area, formation.rows, formation.cols, False).items():
        d = math.hypot((feet[0] - x) / (dx * 0.5 * scale), (feet[1] - y) / (dx * 0.3 * scale))
        if d < best_d:
            best, best_d = cell, d
    return best


def handle_drag(ui: Gui, app: Any, field: list, roster: list) -> None:
    """Нажатие на бойца начинает перетаскивание; отпускание — поставить, поменять, убрать в резерв.
    Бойца держат за ноги: клетка выбирается по точке курсора и прилипает к ближайшей.
    Отпустили там же, где нажали, — это клик: открыть редактор бойца."""
    run = app.run
    for pos, key in ui.clicks:
        if key != 1:
            continue
        uid = next((u for rect, _cell, u in reversed(field) if u is not None and rect.collidepoint(pos)), None)
        if uid is None:
            uid = next((u for rect, u in reversed(roster) if u is not None and rect.collidepoint(pos)), None)
        if uid is not None:
            app.drag = (uid, pos)
    for pos, key in ui.releases:
        if key != 1 or app.drag is None:
            continue
        uid, start = app.drag
        app.drag = None
        if math.dist(pos, start) < DRAG_MIN:
            open_unit(app, uid, app.view)
            continue
        cell = snap_cell(app, pos)
        if cell is not None:
            app.act(run.place, uid, *cell)
        elif any(rect.collidepoint(pos) for rect, _u in roster):
            if run.squad.formation.position_of(uid) is not None:
                app.act(run.bench, uid)
    if dragging(ui, app):
        unit = run.army.units.get(app.drag[0])
        if unit is None:
            return
        formation = run.squad.formation
        area = field_area(HALF_L)
        height = unit_height(area, formation.cols)
        cell = snap_cell(app, ui.mouse)
        if cell is not None:                         # тень на клетке, куда он встанет
            x, y, scale = spots(area, formation.rows, formation.cols, False)[cell]
            ui.later(DRAG, lambda: figure(ui, app, unit.definition.id, (round(x), round(y + 4)),
                                          round(height * scale), alpha=150, look=unit.state.look))
        else:                                        # в руке: ноги в точке курсора
            mouse = ui.mouse
            ui.later(DRAG, lambda: figure(ui, app, unit.definition.id, mouse, round(height * 0.9), alpha=210,
                                          look=unit.state.look))


def open_unit(app: Any, uid: int, back: str, tab: Optional[str] = None, slot: int = 0) -> None:
    """Редактор бойца; back — куда вернёт «Назад», tab и slot — открыть сразу нужную вкладку и слот."""
    app.selected, app.back_view, app.view = uid, back if back != UNIT else MAIN, UNIT
    app.slot, app.preview = slot or 0, None
    if tab is not None:
        app.tab = tab


def ordered_units(app: Any) -> list[Unit]:
    """Сначала стоящие в отряде (передний ряд первым), затем резерв."""
    formation = app.run.squad.formation
    units = list(app.run.army.units.values())
    return sorted(units, key=lambda u: (formation.position_of(u.uid) is None,
                                        formation.position_of(u.uid) or (0, 0), u.uid))


# --- список юнитов ---------------------------------------------------------------------

def draw_units(ui: Gui, app: Any) -> None:
    t, db = ui.t, app.db
    units = ordered_units(app)
    panel(ui, LIST, t("Units"), t("{n} in the army", n=len(units)))
    heads = list_columns(inset(LIST_HEAD, 22, 0))
    for rect, text in zip(heads[1:], (t("Fighter"), t("Level"), t("HP"), t("Place"), t("Equipment"))):
        ui.label(text, rect, "label")
    lines = max(1, LIST_AREA.height // LIST_ROW)
    offset = ui.scroll("tower-units", LIST_AREA, len(units), lines)
    for i, unit in enumerate(units[offset:offset + lines]):
        rect = unit_row(i)
        fielded = app.run.squad.formation.position_of(unit.uid) is not None
        body, clicked = w.selectable(ui, rect, "row")
        face, info, level, hp, where, gear = list_columns(inset(body, 10, 4))
        portrait(ui, app, unit.definition.id, place(face, (face.width, face.width), "center"), leader_kind(app, unit))
        name_r, class_r = rows(info, [1.0, 1.0])
        ui.label(unit_name(t, unit), name_r, "body")
        if promotion.available(unit, db):
            ui.label("↑ " + t("Promotion!"), name_r, "small", align="right", color=GOLD)
        tags = ", ".join(t(db.tags[tag].name) for tag in unit.definition.tags if tag in db.tags)
        ui.label(f"{class_line(t, unit)} · {tags}" if tags else class_line(t, unit), class_r, "small", color=DIM)
        badge, exp_r = rows(level, [1.0, 20], 4)
        level_badge(ui, badge, unit.state.level)
        bar(ui, exp_r, unit.state.exp, app.rules.exp.per_level, "exp")
        bar(ui, place(hp, (hp.width, 30), "center"), unit.hp, unit.max_hp, "hp", f"{unit.hp}/{unit.max_hp}")
        ui.label(place_text(app, unit), where, "small", color=GOLD if fielded else DIM)
        on_icon = False
        side = min(gear.height, 84)
        for j, item_id in enumerate(i for i in unit.state.equipment if i is not None):
            cell = pygame.Rect(gear.x + j * (side + 6), gear.centery - side // 2, side, side)
            if cell.right > gear.right:
                break
            on_icon = bool(item_icon(ui, app, item_id, cell)) or on_icon
        if clicked and not on_icon:                   # клик по иконке — только подсказка
            open_unit(app, unit.uid, UNITS)


# --- редактор бойца -----------------------------------------------------------------

def draw_unit(ui: Gui, app: Any, unit: Unit) -> None:
    t = ui.t
    draw_editor(ui, app, unit)

    bottom_strip(ui)
    if button(ui, t("Back"), BACK):
        app.view = app.back_view
    order = [u.uid for u in ordered_units(app)]
    index = order.index(unit.uid)
    if button(ui, "‹ " + t("Previous"), PREV, enabled=len(order) > 1):
        open_unit(app, order[index - 1], app.back_view)
    if button(ui, t("Next") + " ›", NEXT, enabled=len(order) > 1):
        open_unit(app, order[(index + 1) % len(order)], app.back_view)
    ui.label(f"{index + 1} / {len(order)}", COUNTER, "heading", color=DIM)


# --- повышение -----------------------------------------------------------------------

def draw_promotion(ui: Gui, app: Any, unit: Unit) -> None:
    """Пути повышения бойца карточками: класс, с какого уровня, что добавится, как изменятся статы и сила."""
    t, db = ui.t, app.db
    draw_unit_art(ui, app, unit)
    paths = [p for p in unit.definition.promotions if p.class_id in db.units]
    panel(ui, EDITOR, t("Promotion: {name}", name=unit_name(t, unit)), t("everything learned stays"))
    if not paths:
        ui.label(t("final class"), PROMOTE_AREA, "heading", align="center", color=DIM)
    for i, path in enumerate(paths):
        promotion_card(ui, app, unit, path, promote_card(i, len(paths)))
    bottom_strip(ui)
    if button(ui, t("Back"), BACK):
        app.view = UNIT


def promoted_ghost(app: Any, unit: Unit, class_id: str) -> Unit:
    """Копия бойца, будто он уже повышен (сам боец не меняется)."""
    target = app.db.definition_for(class_id, [*unit.state.history, unit.definition.id])
    state = replace(unit.state, equipment=list(unit.state.equipment), history=list(unit.state.history))
    return Unit(target, state, app.db.items, strict=False)


def promotion_card(ui: Gui, app: Any, unit: Unit, path: Any, card: pygame.Rect) -> None:
    t, db = ui.t, app.db
    ghost = promoted_ghost(app, unit, path.class_id)
    target = ghost.definition
    body = inset(w.frame(ui, "card", card), 16, 12)
    head, rest = cut_top(body, 44, 6)
    ui.label(t(target.name), head, "heading", color=TEXT)
    ui.label(t("tier {n}", n=target.tier), head, "small", align="right", color=DIM)
    art_r, rest = cut_top(rest, min(250, rest.height // 3), 8)
    shade(ui, art_r, 110)
    full_figure(ui, app, path.class_id, (art_r.width - 16, art_r.height - 12), (art_r.centerx, art_r.bottom - 6))
    power_r, rest = cut_top(rest, 34, 6)
    ui.label(t("Power {a} → {b}", a=rate_unit(unit, db).power, b=rate_unit(ghost, db).power), power_r, "body",
             color=GOLD)
    new = [("skill", s, target.skill_levels.get(s, 1)) for s in target.skills if s not in unit.definition.skills]
    new += [("passive", p, target.passive_levels.get(p, 1)) for p in target.passives
            if p not in unit.definition.passives]
    title_r, rest = cut_top(rest, 30, 4)
    ui.label(t("New:"), title_r, "label")
    for kind, entry_id, unlock in new:
        if rest.height < 44 + 110:
            break
        chip, rest = cut_top(rest, 42, 6)
        skill_chip(ui, app, kind, entry_id, chip, unlock, unit.state.level)
    added = list(target.slots)
    for slot in unit.definition.slots:
        if slot in added:
            added.remove(slot)
    extras = [t(x) for x in added] + [t(db.tags[x].name) for x in target.tags
                                      if x not in unit.definition.tags and x in db.tags]
    if extras or not new:
        line, rest = cut_top(rest, 30, 4)
        ui.label(", ".join(extras) if extras else t("nothing new, only stats"), line, "small",
                 color=TEXT if extras else DIM)
    gains = [(ghost.stat(s) - unit.stat(s), s) for s in Stat if ghost.stat(s) != unit.stat(s)]
    stats_r = pygame.Rect(rest.x, rest.y + 6, rest.width, promote_button(card).y - rest.y - 16)
    for cell, (delta, stat) in zip(grid(stats_r, len(gains), 2, 30, 14, 2), gains):
        if cell.bottom > stats_r.bottom:
            break
        ui.label(f"{t(stat.value)} {delta:+d}", cell, "small", color=GREEN if delta > 0 else ENEMY)
    ready = unit.state.level >= path.level
    if button(ui, t("Promote") if ready else t("from lv {n}", n=path.level), promote_button(card), primary=ready,
              enabled=ready, style="tab"):
        app.act(app.run.promote, db, unit.uid, path.class_id)
        app.view = UNIT


def enemy_rating(app: Any):
    """Сила врагов этажа (как на поле подготовки)."""
    db = app.db
    units = [(db.create_unit(c, 0, level, gear), row) for c, level, gear, row, _col in app.enemies() if c in db.units]
    return rate_squad(units, db)


def go_back(app: Any) -> bool:
    """Esc на подготовке: закрыть список тактики; из редактора — туда, откуда пришли, из списков — на главный."""
    if getattr(app, "tactic_pick", None) is not None:
        app.tactic_pick = None
        return True
    if app.view == PROMOTE:
        app.view = UNIT
        return True
    if app.view == UNIT:
        app.view = app.back_view
        return True
    if app.view != MAIN:
        app.view = MAIN
        return True
    return False
