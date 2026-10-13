"""Подготовка к этажу в духе Unicorn Overlord.

Виды (app.view):
  main   — слева наш отряд, справа враги этажа в их построении; бойцы стоят фигурами на клетках
  squad  — справа вместо врагов все бойцы армии; расстановка перетаскиванием (на клетку — поставить
           или поменяться, с поля в список — в резерв)
  units  — полный список бойцов: уровень, опыт, HP, место в отряде, снаряжение
  unit   — редактор бойца: большая фигура, вкладки «Статус», «Снаряжение», «Тактика»
Клик по бойцу (без перетаскивания) где угодно открывает его редактор.
"""
from __future__ import annotations

import math
from typing import Any, Optional

import pygame

from game.editing import describe_reaction, describe_skill, set_tactics
from game.stats import Stat
from game.unit import Unit
from pygame_tower_inventory import draw_inventory
from pygame_editors import ROW_H, rule_table
from pygame_tips import modifier_text, tier_color, unit_tip
from pygame_tower_style import (ACCENTS, BOTTOM_Y, CONTENT_Y, CELL, CELL_EMPTY, DIM, ENEMY, EXP, GOLD, GOLD_DIM, GOLD_LINE, GREEN, H,
                                M, PANEL_DARK, TEXT, W, bar, preview_stats, button, class_entries, crown, figure,
                                item_icon, panel, plate, portrait, skill_chip, stat_grid)
from pygame_ui import UI, lighter

MAIN, SQUAD, UNITS, UNIT, INVENTORY = "main", "squad", "units", "unit", "inventory"
STATUS, EQUIPMENT, TACTICS = "status", "equipment", "tactics"
NONE_ITEM = "__none__"
SNAP = 1.6                          # прилипание: до скольких «радиусов клетки» от курсора
DRAG_MIN = 12                       # дальше стольких пикселей от нажатия — уже перетаскивание

# Раскладка
HALF_L = pygame.Rect(M, CONTENT_Y, W // 2 - M - 12, BOTTOM_Y - CONTENT_Y - 12)
HALF_R = pygame.Rect(W // 2 + 12, CONTENT_Y, W // 2 - M - 12, HALF_L.height)
SQUAD_BUTTON = pygame.Rect(M, BOTTOM_Y + 14, 280, 70)
UNITS_BUTTON = pygame.Rect(M + 300, BOTTOM_Y + 14, 280, 70)
INVENTORY_BUTTON = pygame.Rect(M + 600, BOTTOM_Y + 14, 280, 70)
FIGHT = pygame.Rect(W - M - 380, BOTTOM_Y + 10, 380, 78)
BACK = pygame.Rect(M, BOTTOM_Y + 14, 260, 70)
PREV = pygame.Rect(M + 280, BOTTOM_Y + 14, 220, 70)
NEXT = pygame.Rect(M + 520, BOTTOM_Y + 14, 220, 70)
ART = pygame.Rect(M, CONTENT_Y, 640, BOTTOM_Y - CONTENT_Y - 12)
FIELD_TOGGLE = pygame.Rect(ART.x + 40, ART.bottom - 92, ART.width - 80, 64)
TAB_X = ART.right + 24
TABS = {STATUS: pygame.Rect(TAB_X, CONTENT_Y, 300, 62), EQUIPMENT: pygame.Rect(TAB_X + 312, CONTENT_Y, 300, 62),
        TACTICS: pygame.Rect(TAB_X + 624, CONTENT_Y, 300, 62)}
CONTENT = pygame.Rect(TAB_X, CONTENT_Y + 74, W - TAB_X - M, BOTTOM_Y - CONTENT_Y - 86)
LIST = pygame.Rect(M, CONTENT_Y, W - 2 * M, BOTTOM_Y - CONTENT_Y - 12)
LIST_ROW = 112
SLOT_ROW = 118
TABLE_W = 780                       # ширина таблицы тактики при базовом масштабе (RULE_MOVE + кнопки)
PANEL_HEAD = 62                     # высота шапки панели (pygame_tower_style.panel)
ROSTER_AREA = pygame.Rect(HALF_R.x + 16, HALF_R.y + PANEL_HEAD + 12, HALF_R.width - 32, HALF_R.height - PANEL_HEAD - 24)
ROSTER_COLS, ROSTER_CARD = 3, ((HALF_R.width - 56) // 3, 132)
LIST_AREA = pygame.Rect(LIST.x + 16, LIST.y + PANEL_HEAD + 40, LIST.width - 32, LIST.height - PANEL_HEAD - 52)


def roster_card(i: int) -> pygame.Rect:
    """i-я видимая карточка армии в виде «Отряд»."""
    w, h = ROSTER_CARD
    return pygame.Rect(ROSTER_AREA.x + (i % ROSTER_COLS) * (w + 12), ROSTER_AREA.y + (i // ROSTER_COLS) * (h + 10), w, h)


def unit_row(i: int) -> pygame.Rect:
    """i-я видимая строка списка юнитов."""
    return pygame.Rect(LIST_AREA.x, LIST_AREA.y + i * LIST_ROW, LIST_AREA.width, LIST_ROW - 8)


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
    return pygame.Rect(half.x + 20, half.y + 70, half.width - 40, half.height - 90)


def spots(area: pygame.Rect, rows: int, cols: int, mirror: bool) -> dict[tuple[int, int], tuple[float, float, float]]:
    """Клетка (ряд, колонна) -> (x, y ног, масштаб). Колонны уходят вглубь (дальняя сверху и мельче),
    передний ряд (0) ближе к середине экрана: у нас справа, у врага (mirror) слева."""
    top = area.height * 0.34
    depth = (area.height - top - 70) / max(1, cols - 1)
    dx = area.width * 0.84 / rows
    result = {}
    for col in range(cols):
        k = col / max(1, cols - 1)
        scale = 0.78 + 0.22 * k
        y = area.y + top + col * depth
        for row in range(rows):
            lateral = (row + 0.5) * dx + (k - 0.5) * dx * 0.22
            x = area.right - area.width * 0.08 - lateral if not mirror else area.x + area.width * 0.08 + lateral
            result[(row, col)] = (x, y, scale)
    return result


def tile_rect(spot: tuple[float, float, float], dx: float) -> pygame.Rect:
    x, y, scale = spot
    w = dx * 0.86 * scale
    return pygame.Rect(round(x - w / 2), round(y - w * 0.17), round(w), round(w * 0.34))


def unit_height(area: pygame.Rect, cols: int) -> float:
    return (area.height * 0.66 - 70) / max(1, cols - 1) * 0.86 if cols > 1 else area.height * 0.4


def draw_field(ui: UI, app: Any, half: pygame.Rect, entries: list[dict], rows: int, cols: int, mirror: bool,
               hot: Optional[tuple[int, int]] = None) -> list[tuple[pygame.Rect, tuple[int, int], Optional[int]]]:
    """Клетки и стоящие на них фигуры. entries: dict(uid, class_id, level, hp, max_hp, row, col, leader, boss).
    Возвращает цели для мыши: (прямоугольник, клетка, uid или None), ближние позже."""
    area = field_area(half)
    places = spots(area, rows, cols, mirror)
    dx = area.width * 0.84 / rows
    height = unit_height(area, cols)
    by_cell = {(e["row"], e["col"]): e for e in entries}
    dragging = app.drag[0] if app.drag else None
    targets = []
    side_fill, side_line = ((70, 30, 36), (150, 70, 60)) if mirror else ((24, 40, 84), GOLD_DIM)
    for col in range(cols):                                 # дальние колонны первыми
        for row in range(rows):
            spot = places[(row, col)]
            tile = tile_rect(spot, dx)
            lit = hot == (row, col)
            fill = lighter(side_fill, 40 if lit else (12 if row == 0 else 0))
            pygame.draw.ellipse(ui.screen, fill, tile)
            pygame.draw.ellipse(ui.screen, GOLD if lit else side_line, tile, 4 if lit else 2)
            targets.append((tile, (row, col), None))
    plates = []
    for col in range(cols):
        for row in range(rows):
            entry = by_cell.get((row, col))
            if entry is None:
                continue
            x, y, scale = places[(row, col)]
            alpha = 90 if entry.get("uid") is not None and entry.get("uid") == dragging else 255
            rect = figure(ui, app, entry["class_id"], (round(x), round(y + 4)), round(height * scale), mirror, alpha)
            plates.append((entry, rect, x, y, scale))
            targets.append((rect, (row, col), entry.get("uid")))
            if entry.get("tip"):
                ui.tip(rect, entry["tip"])
    # Плашки и короны поверх всех фигур, чтобы задние ряды не терялись за передними
    for entry, rect, x, y, scale in plates:
        plate_w = round(dx * 0.7)
        label = pygame.Rect(round(x - plate_w / 2), round(y + dx * 0.15 * scale + 2), plate_w, 44)
        pygame.draw.rect(ui.screen, PANEL_DARK, label)
        pygame.draw.rect(ui.screen, ENEMY if mirror else GOLD_DIM, label, 1)
        name = f"{ui.t(app.db.units[entry['class_id']].name)}  {entry['level']}"
        ui.text(name, label.x + 6, label.y + 2, ENEMY if entry.get("boss") else TEXT, "tiny", label.width - 12)
        bar(ui, pygame.Rect(label.x + 6, label.y + 28, label.width - 12, 10), entry["hp"], entry["max_hp"],
            GREEN if not mirror else ENEMY)
        if entry.get("leader") or entry.get("boss"):                # корона на плашке своего бойца
            crown(ui, app, (label.right - 4, label.y - 2), 30)
    return targets


def squad_entries(app: Any) -> list[dict]:
    run = app.run
    formation = run.squad.formation
    return [dict(uid=u.uid, class_id=u.definition.id, level=u.state.level, hp=u.hp, max_hp=u.max_hp,
                 row=formation.position_of(u.uid)[0], col=formation.position_of(u.uid)[1],
                 leader=run.squad.leader_uid == u.uid, tip=lambda u=u: unit_tip(app.t, app.db, u))
            for u in formation.units]


def enemy_entries(app: Any) -> list[dict]:
    boss = app.rules.is_boss(app.run.floor)
    entries = []
    for i, (class_id, level, gear, row, col) in enumerate(app.enemies()):
        if class_id not in app.db.units:
            continue
        unit = app.db.create_unit(class_id, 0, level, gear)
        entries.append(dict(uid=None, class_id=class_id, level=level, hp=unit.max_hp, max_hp=unit.max_hp, row=row,
                            col=col, boss=boss and i == 0, tip=lambda u=unit: unit_tip(app.t, app.db, u)))
    return entries


# --- главный экран и расстановка -------------------------------------------------------

def draw_prepare(ui: UI, app: Any) -> None:
    units = {u.uid: u for u in app.run.army.units.values()}
    if app.selected not in units:
        app.selected = next(iter(units), None)
    if app.view == UNIT and app.selected is not None:
        draw_unit(ui, app, units[app.selected])
        return
    if app.view == UNITS:
        draw_units(ui, app)
    elif app.view == INVENTORY:
        draw_inventory(ui, app, open_unit)
    else:
        draw_formation(ui, app)
    draw_bottom(ui, app)


def draw_bottom(ui: UI, app: Any) -> None:
    pygame.draw.rect(ui.screen, PANEL_DARK, (0, BOTTOM_Y, W, H - BOTTOM_Y))
    pygame.draw.line(ui.screen, GOLD_LINE, (0, BOTTOM_Y), (W, BOTTOM_Y), 2)
    t = ui.t
    if button(ui, t("Squad"), SQUAD_BUTTON, selected=app.view == SQUAD):
        app.view = MAIN if app.view == SQUAD else SQUAD
    if button(ui, t("Units"), UNITS_BUTTON, selected=app.view == UNITS):
        app.view = MAIN if app.view == UNITS else UNITS
    if button(ui, t("Inventory"), INVENTORY_BUTTON, selected=app.view == INVENTORY):
        app.view = MAIN if app.view == INVENTORY else INVENTORY
    formation = app.run.squad.formation
    note = t("Fielded {n}/{max}", n=len(formation), max=formation.max_units)
    ui.text(note, INVENTORY_BUTTON.right + 40, BOTTOM_Y + 34, GOLD, "main")
    if button(ui, t("Fight!"), FIGHT, primary=True, enabled=bool(app.run.fielded), font="title"):
        app.start_battle()


def draw_formation(ui: UI, app: Any) -> None:
    t, run = ui.t, app.run
    formation = run.squad.formation
    shop_in = next((k for k in range(1, 1000) if app.rules.shop_after(run.floor + k - 1)), None) \
        if app.rules.data["shop"]["every"] > 0 else None
    panel(ui, HALF_L, ACCENTS["prepare"], t("Your squad"), f"{len(formation)}/{formation.max_units}")
    targets = draw_field(ui, app, HALF_L, squad_entries(app), formation.rows, formation.cols, False,
                         hot=snap_cell(app, ui.mouse) if dragging(ui, app) else None)
    if shop_in:
        ui.text(t("shop after {n} more floor(s)", n=shop_in), HALF_L.x + 24, HALF_L.bottom - 40, DIM, "small")
    roster_targets: list[tuple[pygame.Rect, Optional[int]]] = []
    if app.view == SQUAD:
        roster_targets = draw_roster(ui, app)
    else:
        boss = app.rules.is_boss(run.floor)
        title = t("Enemies of floor {n}", n=run.floor) + ("  " + t("(boss)") if boss else "")
        panel(ui, HALF_R, ACCENTS["over"], title, t("{n} units", n=len(app.enemies())))
        grid = app.rules.squad_size(run.floor)
        draw_field(ui, app, HALF_R, enemy_entries(app), grid.rows, grid.cols, True)
    handle_drag(ui, app, targets, roster_targets)


def draw_roster(ui: UI, app: Any) -> list[tuple[pygame.Rect, Optional[int]]]:
    """Все бойцы армии справа: карточки, которые перетаскиваются на поле."""
    t, run = ui.t, app.run
    panel(ui, HALF_R, ACCENTS["prepare"], t("Army"), t("drag a fighter onto the field"))
    formation = run.squad.formation
    targets = [(HALF_R, None)]                          # отпустить над списком — убрать в резерв
    units = ordered_units(app)
    area = ROSTER_AREA
    rows = max(1, area.height // (ROSTER_CARD[1] + 10))
    offset = ui.scroll("tower-roster", area, (len(units) + ROSTER_COLS - 1) // ROSTER_COLS, rows) * ROSTER_COLS
    for i, unit in enumerate(units[offset:offset + rows * ROSTER_COLS]):
        card = roster_card(i)
        fielded = formation.position_of(unit.uid) is not None
        dragging = app.drag is not None and app.drag[0] == unit.uid
        plate(ui, card, lighter(CELL, 16) if ui.hovered(card) else CELL, GOLD if fielded else GOLD_DIM, cut=10)
        portrait(ui, app, unit.definition.id, pygame.Rect(card.x + 10, card.y + 10, 110, 110),
                 GOLD if fielded else GOLD_DIM)
        x = card.x + 132
        ui.text(t(unit.name), x, card.y + 12, DIM if dragging else TEXT, "small", card.right - x - 10)
        ui.text(t("lv {n}", n=unit.state.level), x, card.y + 44, GOLD, "small")
        bar(ui, pygame.Rect(x, card.y + 76, card.right - x - 14, 8), unit.state.exp, app.rules.exp.per_level, EXP,
            (30, 40, 60))
        ui.text(t("in squad") if fielded else t("reserve"), x, card.y + 94, GOLD if fielded else DIM, "tiny")
        if run.squad.leader_uid == unit.uid:
            crown(ui, app, (card.right - 26, card.y + 26), 28)
        ui.tip(card, lambda u=unit: unit_tip(t, app.db, u))
        targets.append((card, unit.uid))
    return targets


def dragging(ui: UI, app: Any) -> bool:
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


def handle_drag(ui: UI, app: Any, field: list, roster: list) -> None:
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
            figure(ui, app, unit.definition.id, (round(x), round(y + 4)), round(height * scale), alpha=150)
        else:                                        # в руке: ноги в точке курсора
            figure(ui, app, unit.definition.id, ui.mouse, round(height * 0.9), alpha=210)


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


def place_text(app: Any, unit: Unit) -> str:
    t = app.t
    formation = app.run.squad.formation
    position = formation.position_of(unit.uid)
    if position is None:
        return t("reserve")
    row, col = position
    names = {0: t("front row"), formation.rows - 1: t("back row")}
    return f"{names.get(row, t('middle row'))}, {t('place {n}', n=col + 1)}"


# --- список юнитов ---------------------------------------------------------------------

def draw_units(ui: UI, app: Any) -> None:
    t, db = ui.t, app.db
    units = ordered_units(app)
    body = panel(ui, LIST, ACCENTS["prepare"], t("Units"), t("{n} in the army", n=len(units)))
    columns = ((0, t("Fighter")), (560, t("Level")), (760, t("HP")), (960, t("Place")), (1330, t("Equipment")))
    for x, label in columns:
        ui.text(label, LIST.x + 30 + x, body.y + 8, GOLD, "small")
    area = LIST_AREA
    rows = max(1, area.height // LIST_ROW)
    offset = ui.scroll("tower-units", area, len(units), rows)
    for i, unit in enumerate(units[offset:offset + rows]):
        rect = unit_row(i)
        fielded = app.run.squad.formation.position_of(unit.uid) is not None
        plate(ui, rect, lighter(CELL, 16) if ui.hovered(rect) else CELL, GOLD if fielded else GOLD_DIM, cut=10)
        portrait(ui, app, unit.definition.id, pygame.Rect(rect.x + 10, rect.y + 6, 92, 92))
        x = rect.x + 14
        ui.text(t(unit.name), x + 104, rect.y + 16, TEXT, "main", 400)
        tags = ", ".join(t(db.tags[tag].name) for tag in unit.definition.tags if tag in db.tags)
        ui.text(tags, x + 104, rect.y + 56, DIM, "tiny", 420)
        if app.run.squad.leader_uid == unit.uid:
            crown(ui, app, (rect.x + 94, rect.y + 16), 26)
        ui.text(str(unit.state.level), x + 560, rect.y + 20, GOLD, "big")
        bar(ui, pygame.Rect(x + 560, rect.y + 70, 160, 10), unit.state.exp, app.rules.exp.per_level, EXP, (30, 40, 60))
        bar(ui, pygame.Rect(x + 760, rect.y + 38, 160, 22), unit.hp, unit.max_hp, GREEN, label=f"{unit.max_hp}")
        ui.text(place_text(app, unit), x + 960, rect.y + 34, GOLD if fielded else DIM, "small", 350)
        on_icon = False
        for j, item_id in enumerate(i for i in unit.state.equipment if i is not None):
            on_icon = bool(item_icon(ui, app, item_id, pygame.Rect(x + 1330 + j * 84, rect.y + 10, 78, 78))) or on_icon
        if ui.clicked(rect) and not on_icon:                   # клик по иконке — только подсказка
            open_unit(app, unit.uid, UNITS)


# --- редактор бойца -----------------------------------------------------------------

def draw_unit(ui: UI, app: Any, unit: Unit) -> None:
    t, run = ui.t, app.run
    # Слева большая фигура и имя на плашке
    plate(ui, ART, PANEL_DARK, GOLD_LINE)
    glow = pygame.Surface((ART.width - 24, ART.height - 24), pygame.SRCALPHA)
    for r in range(260, 0, -20):
        pygame.draw.circle(glow, (60, 80, 140, 10), (glow.get_width() // 2, glow.get_height() // 2 - 60), r * 1.4)
    ui.screen.blit(glow, (ART.x + 12, ART.y + 12))
    figure(ui, app, unit.definition.id, (ART.centerx, ART.bottom - 300), 640)
    name_plate = pygame.Rect(ART.x + 24, ART.bottom - 290, ART.width - 48, 186)
    plate(ui, name_plate, (16, 24, 50), GOLD_LINE, cut=12)
    ui.text(t(unit.name), name_plate.x + 24, name_plate.y + 14, GOLD, "title", name_plate.width - 160)
    level = ui.fonts["big"].render(t("lv {n}", n=unit.state.level), True, TEXT)
    ui.screen.blit(level, (name_plate.right - level.get_width() - 24, name_plate.y + 24))
    need = app.rules.exp.per_level
    ui.text(t("exp {n}/{need}", n=unit.state.exp, need=need), name_plate.x + 24, name_plate.y + 84, EXP, "small")
    bar(ui, pygame.Rect(name_plate.x + 24, name_plate.y + 116, name_plate.width - 48, 12), unit.state.exp, need, EXP,
        (30, 40, 60))
    ui.text(place_text(app, unit), name_plate.x + 24, name_plate.y + 144, DIM, "small", name_plate.width - 48)
    if run.squad.leader_uid == unit.uid:
        crown(ui, app, (name_plate.right - 40, name_plate.y - 24), 40)
    fielded = run.squad.formation.position_of(unit.uid) is not None
    if button(ui, t("To reserve") if fielded else t("To the squad"), FIELD_TOGGLE):
        app.act(run.bench if fielded else run.field, unit.uid)

    for tab, rect in TABS.items():
        if button(ui, t({STATUS: "Status", EQUIPMENT: "Equipment", TACTICS: "Tactics"}[tab]), rect,
                  selected=app.tab == tab, font="big"):
            app.tab = tab
    plate(ui, CONTENT, (18, 28, 56), GOLD_LINE)
    {STATUS: draw_status, EQUIPMENT: draw_equipment, TACTICS: draw_tactics}[app.tab](ui, app, unit)

    pygame.draw.rect(ui.screen, PANEL_DARK, (0, BOTTOM_Y, W, H - BOTTOM_Y))
    pygame.draw.line(ui.screen, GOLD_LINE, (0, BOTTOM_Y), (W, BOTTOM_Y), 2)
    if button(ui, t("Back"), BACK):
        app.view = app.back_view
    order = [u.uid for u in ordered_units(app)]
    index = order.index(unit.uid)
    if button(ui, "‹ " + t("Previous"), PREV, enabled=len(order) > 1):
        open_unit(app, order[index - 1], app.back_view)
    if button(ui, t("Next") + " ›", NEXT, enabled=len(order) > 1):
        open_unit(app, order[(index + 1) % len(order)], app.back_view)
    ui.text(f"{index + 1} / {len(order)}", NEXT.right + 30, BOTTOM_Y + 36, DIM, "main")


def section_title(ui: UI, text: str, x: int, y: int, width: int) -> int:
    ui.text(text, x, y, GOLD, "main")
    pygame.draw.line(ui.screen, GOLD_DIM, (x, y + 34), (x + width, y + 34), 1)
    return y + 44


def draw_status(ui: UI, app: Any, unit: Unit) -> None:
    t, db = ui.t, app.db
    x, y = CONTENT.x + 30, CONTENT.y + 24
    left_w = 560
    y = section_title(ui, t("Parameters"), x, y, left_w)
    bar(ui, pygame.Rect(x, y, left_w, 26), unit.hp, unit.max_hp, GREEN, label=f"HP {unit.hp}/{unit.max_hp}")
    y = stat_grid(ui, app, unit, x, y + 40, 1, left_w, 38)
    y = section_title(ui, t("Traits"), x, y + 16, left_w)
    for i, tag in enumerate(tag for tag in unit.definition.tags if tag in db.tags):
        chip = pygame.Rect(x + (i % 3) * 186, y + (i // 3) * 44, 178, 38)
        plate(ui, chip, CELL, GOLD_DIM, cut=8)
        ui.text(t(db.tags[tag].name), chip.x + 12, chip.y + 7, TEXT, "small", chip.width - 20)

    sx = x + left_w + 60
    width = CONTENT.right - sx - 30
    entries = class_entries(unit)
    items = [("skill", s) for item in unit.equipped for s in item.skills] + \
            [("passive", p) for item in unit.equipped for p in item.passives]
    sy = section_title(ui, t("Active skills"), sx, CONTENT.y + 24, width)
    for kind, entry_id, unlock in [e for e in entries if e[0] == "skill"] + [(k, i, 1) for k, i in items if k == "skill"]:
        skill_row(ui, app, unit, kind, entry_id, unlock, pygame.Rect(sx, sy, width, 70))
        sy += 78
    sy = section_title(ui, t("Passive skills"), sx, sy + 12, width)
    for kind, entry_id, unlock in [e for e in entries if e[0] == "passive"] + \
            [(k, i, 1) for k, i in items if k == "passive"]:
        skill_row(ui, app, unit, kind, entry_id, unlock, pygame.Rect(sx, sy, width, 70))
        sy += 78


def skill_row(ui: UI, app: Any, unit: Unit, kind: str, entry_id: str, unlock: int, rect: pygame.Rect) -> None:
    """Строка навыка: значок, название, стоимость ромбиками и короткое описание под ним."""
    if rect.bottom > CONTENT.bottom - 10:
        return
    skill_chip(ui, app, kind, entry_id, pygame.Rect(rect.x, rect.y, rect.width, 40), unlock, unit.state.level,
               costs=True)
    db, t = app.db, ui.t
    if kind == "skill" and entry_id in db.skills:
        text = describe_skill(db.skills[entry_id], db, t).split(" | ")
        line = ", ".join(text[1:]) or text[0]
    elif entry_id in db.passives:
        line = describe_reaction(db.passives[entry_id].reaction, db, t)
    else:
        line = ""
    ui.text(line, rect.x + 50, rect.y + 44, DIM, "tiny", rect.width - 60)


def draw_equipment(ui: UI, app: Any, unit: Unit) -> None:
    t, db, inventory = ui.t, app.db, app.run.inventory
    x, y = CONTENT.x + 30, CONTENT.y + 24
    width = 640
    y = section_title(ui, t("Equipment"), x, y, width)
    slots = unit.definition.slots
    app.slot = min(app.slot, max(0, len(slots) - 1))
    for index, slot in enumerate(slots):
        row = pygame.Rect(x, y + index * SLOT_ROW, width, SLOT_ROW - 10)
        chosen = index == app.slot
        plate(ui, row, (60, 52, 30) if chosen else (lighter(CELL, 14) if ui.hovered(row) else CELL),
              GOLD if chosen else GOLD_DIM, cut=10)
        current = unit.state.equipment[index]
        icon = pygame.Rect(row.x + 10, row.y + 10, 88, 88)
        ui.text(t(slot), row.x + 112, row.y + 8, GOLD if chosen else DIM, "tiny")
        if current is not None:
            item_icon(ui, app, current, icon)
            ui.text(t(db.items[current].name), row.x + 112, row.y + 34, tier_color(db.items[current].tier), "main",
                    row.width - 124)
            mods = ", ".join(modifier_text(t, m) for m in db.items[current].modifiers)
            ui.text(mods, row.x + 112, row.y + 72, TEXT, "tiny", row.width - 124)
        else:
            plate(ui, icon, CELL_EMPTY, GOLD_DIM, cut=8)
            ui.text(t("empty"), row.x + 112, row.y + 40, DIM, "main")
        if ui.clicked(row):
            app.slot = index

    # Справа: статы с разницей и подходящие предметы из инвентаря
    rx = x + width + 50
    rwidth = CONTENT.right - rx - 30
    ry = section_title(ui, t("Parameters"), rx, CONTENT.y + 24, rwidth)
    preview = None
    hovered: Optional[str] = None
    candidates_y = ry + len(Stat) * 30 + 24
    if slots:
        slot = slots[app.slot]
        fits = [i for i, n in sorted(inventory.items.items()) if n > 0 and i in db.items and db.items[i].slot == slot]
        cy = section_title(ui, t("Inventory: {slot}", slot=t(slot)), rx, candidates_y, rwidth)
        current = unit.state.equipment[app.slot]
        options = ([NONE_ITEM] if current is not None else []) + fits
        area = pygame.Rect(rx, cy, rwidth, CONTENT.bottom - cy - 20)
        rows = max(1, area.height // 92)
        offset = ui.scroll(("tower-fits", unit.uid, app.slot), area, len(options), rows)
        for i, item_id in enumerate(options[offset:offset + rows]):
            row = pygame.Rect(rx, cy + i * 92, rwidth, 84)
            hover = ui.hovered(row)
            plate(ui, row, lighter(CELL, 16) if hover else CELL, GOLD if hover else GOLD_DIM, cut=8)
            if item_id == NONE_ITEM:
                ui.text(t("Take off"), row.x + 20, row.y + 24, DIM, "main")
            else:
                item_icon(ui, app, item_id, pygame.Rect(row.x + 6, row.y + 6, 72, 72), inventory.count(item_id))
                ui.text(t(db.items[item_id].name), row.x + 92, row.y + 8, tier_color(db.items[item_id].tier), "main",
                        row.width - 100)
                mods = ", ".join(modifier_text(t, m) for m in db.items[item_id].modifiers)
                ui.text(mods, row.x + 92, row.y + 46, TEXT, "tiny", row.width - 100)
            if hover:
                hovered = item_id
            if ui.clicked(row):
                app.change_equipment(unit, app.slot, item_id)
        if not options:
            ui.text(t("no fitting items in the inventory"), rx, cy + 10, DIM, "small")
        if hovered is not None:
            preview = preview_stats(app, unit, app.slot, None if hovered == NONE_ITEM else hovered)
    stat_grid(ui, app, unit, rx, ry, 1, rwidth, 30, preview)


def draw_tactics(ui: UI, app: Any, unit: Unit) -> None:
    t, db = ui.t, app.db
    x, y = CONTENT.x + 30, CONTENT.y + 24
    ui.text(t("Rules are checked top to bottom: the first one whose conditions hold,"), x, y, DIM, "small")
    ui.text(t("with a valid target and enough AP, is used. Otherwise: Attack, if AP allows."), x, y + 28, DIM, "small")
    rules = unit.tactics.to_list()
    # Таблица рассчитана на базовые 1000 px: масштаб такой, чтобы она поместилась во вкладку
    scale, ui.scale = ui.scale, min(ui.scale, (CONTENT.width - 60) / TABLE_W)
    try:
        new_rules = rule_table(ui, db, ("tower-tactics", unit.uid), rules, unit.skill_ids, x, y + 70)
        by = y + 70 + round(20 * ui.scale) + (len(rules) + 1) * round(ROW_H * ui.scale) + 20
    finally:
        ui.scale = scale
    if button(ui, t("Reset to default"), pygame.Rect(x, by, 380, 56), enabled=unit.has_custom_tactics):
        unit.reset_tactics()
        app.save()
    elif new_rules is not None:
        try:
            set_tactics(db, unit, new_rules)
            app.save()
        except (ValueError, KeyError) as error:
            app.message = str(error)
    sy = section_title(ui, t("Available skills"), x, by + 80, CONTENT.width - 60)
    for i, skill_id in enumerate(unit.skill_ids[:8]):
        skill_chip(ui, app, "skill", skill_id, pygame.Rect(x + (i % 3) * 400, sy + (i // 3) * 50, 390, 42),
                   costs=True)


def go_back(app: Any) -> bool:
    """Esc на подготовке: из редактора — туда, откуда пришли, из списков — на главный экран."""
    if app.view == UNIT:
        app.view = app.back_view
        return True
    if app.view != MAIN:
        app.view = MAIN
        return True
    return False
