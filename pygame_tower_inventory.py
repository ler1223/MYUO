"""Инвентарь забега на подготовке к этажу: все предметы — свободные и надетые, фильтры и сортировка.

Слева фильтры (что показывать, группа слотов, тир, кому подходит) и сортировка (тир, название,
слот, цена или любой стат) с направлением. В середине таблица предметов: свободные со счётчиком,
надетые — по одному, с портретом владельца. Клик по надетому открывает редактор владельца на
этом слоте; по свободному — справа описание и список бойцов, на кого его можно надеть.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

import pygame

from game.stats import ModOp, Stat
from pygame_tips import item_tip, modifier_text, tier_color
from pygame_tower_style import BODY, DIM, ENEMY, GAP, GOLD, GREEN, TEXT, button, item_icon, panel, portrait, preview_stats
from uikit import Gui
from uikit import widgets as w
from uikit.layout import cols, cut_left, cut_top, inset, place, rows

SHOW = ("all", "free", "equipped")
GROUPS = {"all": (), "weapons": ("light_sword", "bow", "staff", "dagger", "heavy_weapon", "lance"),
          "armor": ("light_shield", "light_armor", "medium_armor", "robe"), "artifacts": ("artifact",)}
SORTS = ("tier", "name", "slot", "price")       # плюс любой стат: "stat:<имя>"
ANY = "__any__"

# --- раскладка (общая для отрисовки и тестов) -----------------------------------------

FILTERS, TABLE, DETAIL = cols(BODY, [470, 1.0, 440], GAP)
PAD = (38, 92, 38, 36)                          # содержимое панели с заголовком (uikit.widgets.panel)
FILTER_AREA = inset(FILTERS, *PAD)
TABLE_HEAD = pygame.Rect(TABLE.x + PAD[0], TABLE.y + PAD[1], TABLE.width - 2 * PAD[0], 34)
TABLE_AREA = pygame.Rect(TABLE_HEAD.x, TABLE_HEAD.bottom + 8, TABLE_HEAD.width,
                         TABLE.bottom - PAD[3] - TABLE_HEAD.bottom - 8)
DETAIL_AREA = inset(DETAIL, *PAD)
ROW = 104
CONTROL_H = 56
BLOCK_LINES = (1, 2, 1, 1, 1)                   # строк кнопок в блоках: показ, тип, тир, кому, сортировка


def filter_block(i: int) -> tuple[pygame.Rect, pygame.Rect]:
    """i-й блок фильтров: (подпись, кнопки под ней)."""
    y = FILTER_AREA.y
    for k in range(i):
        y += 40 + BLOCK_LINES[k] * (CONTROL_H + 8) + 14
    title = pygame.Rect(FILTER_AREA.x, y, FILTER_AREA.width, 34)
    return title, pygame.Rect(FILTER_AREA.x, title.bottom + 6, FILTER_AREA.width,
                              BLOCK_LINES[i] * (CONTROL_H + 8) - 8)


def show_button(i: int) -> pygame.Rect:
    return cols(filter_block(0)[1], [0.85, 1.35, 1.0], 8)[i]       # «свободные» длиннее остальных


def group_button(i: int) -> pygame.Rect:
    top, bottom = rows(filter_block(1)[1], [CONTROL_H, CONTROL_H], 8)
    return cols(top if i < 2 else bottom, [1.0, 1.0], 8)[i % 2]


def tier_button(i: int) -> pygame.Rect:
    return cols(filter_block(2)[1], [1.7, 1.0, 1.0, 1.0], 8)[i]    # «любой» и три тира


FITS_DROPDOWN = filter_block(3)[1]
SORT_DROPDOWN, ORDER_BUTTON = cols(filter_block(4)[1], [1.0, 72], 8)
RESET_BUTTON = place(FILTER_AREA, (FILTER_AREA.width, 64), "bottom")
WEAR_TOP = DETAIL_AREA.y + 500


def table_columns(row: pygame.Rect) -> list[pygame.Rect]:
    """Колонки таблицы: иконка, предмет, бонусы, где."""
    return cols(row, [84, 1.0, 220, 210], 14)


def table_row(i: int) -> pygame.Rect:
    return pygame.Rect(TABLE_AREA.x, TABLE_AREA.y + i * ROW, TABLE_AREA.width, ROW - 8)


def wear_row(i: int) -> pygame.Rect:
    """i-й боец в списке «надеть на» справа."""
    return pygame.Rect(DETAIL_AREA.x, WEAR_TOP + 56 + i * 96, DETAIL_AREA.width, 88)


@dataclass
class InventoryFilter:
    show: str = "all"                 # all / free / equipped
    group: str = "all"                # группа слотов (GROUPS)
    tier: int = 0                     # 0 — любой
    fits: Optional[int] = None        # uid бойца: только то, что он может надеть
    sort: str = "tier"                # SORTS или "stat:<стат>"
    descending: bool = True
    picked: Optional[str] = None      # выбранный свободный предмет (панель справа)


@dataclass(frozen=True)
class Entry:
    """Строка инвентаря: свободные предметы одного вида (count) или один надетый (owner, slot)."""

    item_id: str
    count: int = 1
    owner: Optional[int] = None
    slot: Optional[int] = None


def stat_bonus(item, stat: Stat) -> float:
    """Прибавка предмета к стату (простые прибавки; доли — в процентах для сравнения)."""
    total = 0.0
    for mod in item.modifiers:
        if mod.stat is stat:
            total += mod.value if mod.op is ModOp.FLAT else mod.value * 100
    return total


def inventory_entries(app: Any, flt: InventoryFilter) -> list[Entry]:
    """Свободные и надетые предметы забега после фильтров, в порядке сортировки."""
    db, run = app.db, app.run
    entries: list[Entry] = []
    if flt.show != "equipped":
        entries += [Entry(i, n) for i, n in run.inventory.items.items() if n > 0 and i in db.items]
    if flt.show != "free":
        for unit in run.army.units.values():
            entries += [Entry(i, 1, unit.uid, k) for k, i in enumerate(unit.state.equipment) if i in db.items]
    group = GROUPS.get(flt.group, ())
    wearer = run.army.units.get(flt.fits) if flt.fits is not None else None

    def keep(entry: Entry) -> bool:
        item = db.items[entry.item_id]
        return (not group or item.slot in group) and (not flt.tier or item.rank == flt.tier) \
            and (wearer is None or wearer.can_equip(entry.item_id))

    entries = [e for e in entries if keep(e)]
    slots = list(db.slot_types)
    t = app.t
    if flt.sort.startswith("stat:"):
        stat = Stat(flt.sort[5:])
        key = lambda e: (stat_bonus(db.items[e.item_id], stat), db.items[e.item_id].tier)
    elif flt.sort == "name":
        key = lambda e: t(db.items[e.item_id].name).casefold()
    elif flt.sort == "slot":
        key = lambda e: (slots.index(db.items[e.item_id].slot) if db.items[e.item_id].slot in slots else 99,
                         -db.items[e.item_id].tier)
    elif flt.sort == "price":
        key = lambda e: db.items[e.item_id].price
    else:
        key = lambda e: (db.items[e.item_id].tier, db.items[e.item_id].price)
    entries.sort(key=lambda e: (key(e), e.owner is not None, e.item_id))
    if flt.descending:
        entries.reverse()
    return entries


# --- отрисовка ----------------------------------------------------------------------

def draw_inventory(ui: Gui, app: Any, open_unit: Callable[..., None]) -> None:
    flt = app.inv
    draw_filters(ui, app, flt)
    entries = inventory_entries(app, flt)
    draw_table(ui, app, flt, entries, open_unit)
    draw_detail(ui, app, flt)


def draw_filters(ui: Gui, app: Any, flt: InventoryFilter) -> None:
    t = ui.t
    panel(ui, FILTERS, t("Filters"))
    for i, title in enumerate((t("Show"), t("Type"), t("Tier"), t("Fits a fighter"), t("Sort by"))):
        ui.label(title, filter_block(i)[0], "label")
    for i, show in enumerate(SHOW):
        if button(ui, t({"all": "all", "free": "free", "equipped": "worn"}[show]), show_button(i),
                  selected=flt.show == show, style="small"):
            flt.show = show
    for i, group in enumerate(GROUPS):
        if button(ui, t({"all": "any type", "weapons": "weapons", "armor": "armor and shields",
                         "artifacts": "artifacts"}[group]), group_button(i), selected=flt.group == group,
                  style="small"):
            flt.group = group
    for i, tier in enumerate((0, 1, 2, 3)):
        text = t("any") if tier == 0 else ("I", "II", "III")[tier - 1]
        if button(ui, text, tier_button(i), selected=flt.tier == tier, style="small"):
            flt.tier = tier
    units = sorted(app.run.army.units.values(), key=lambda u: u.uid)
    options = [(ANY, t("anyone"))] + [(u.uid, f"{t(u.nickname)} {t('lv {n}', n=u.state.level)}") for u in units]
    picked = ui.dropdown("inventory-fits", FITS_DROPDOWN, options, flt.fits if flt.fits is not None else ANY)
    if picked is not None:
        flt.fits = None if picked == ANY else picked
    sorts = [(s, t({"tier": "tier", "name": "name", "slot": "slot", "price": "price"}[s])) for s in SORTS]
    sorts += [(f"stat:{s.value}", t(s.value)) for s in Stat]
    picked = ui.dropdown("inventory-sort", SORT_DROPDOWN, sorts, flt.sort)
    if picked is not None:
        flt.sort = picked
    if button(ui, "↓" if flt.descending else "↑", ORDER_BUTTON, style="small"):
        flt.descending = not flt.descending
    ui.tip(ORDER_BUTTON, lambda: [(t("descending") if flt.descending else t("ascending"), TEXT, "small")])
    if button(ui, t("Reset filters"), RESET_BUTTON, style="small"):
        app.inv = InventoryFilter(picked=flt.picked)


def draw_table(ui: Gui, app: Any, flt: InventoryFilter, entries: list[Entry], open_unit: Callable[..., None]) -> None:
    t, db, run = ui.t, app.db, app.run
    free = sum(e.count for e in entries if e.owner is None)
    worn = sum(1 for e in entries if e.owner is not None)
    panel(ui, TABLE, t("Inventory"), t("free {a}, worn {b}", a=free, b=worn))
    for rect, text in zip(table_columns(inset(TABLE_HEAD, 14, 0))[1:], (t("Item"), t("Bonuses"), t("Where"))):
        ui.label(text, rect, "label")
    lines = max(1, TABLE_AREA.height // ROW)
    offset = ui.scroll("inventory-table", TABLE_AREA, len(entries), lines)
    sort_stat = Stat(flt.sort[5:]) if flt.sort.startswith("stat:") else None
    for i, entry in enumerate(entries[offset:offset + lines]):
        rect = table_row(i)
        item = db.items[entry.item_id]
        chosen = entry.owner is None and flt.picked == entry.item_id
        body, clicked = w.selectable(ui, rect, "row", selected=chosen)
        icon_r, name_c, mods_c, where_c = table_columns(inset(body, 6, 2))
        on_icon = bool(item_icon(ui, app, entry.item_id, place(icon_r, (84, 84), "center"), entry.count))
        name_r, slot_r = rows(name_c, [1.0, 1.0])
        ui.label(t(item.name), name_r, "body", color=tier_color(item.rank))
        ui.label(f"{t(item.slot)} · {item.price}", slot_r, "small", color=DIM)
        mods = [(modifier_text(t, mod), GOLD if mod.stat is sort_stat else TEXT) for mod in item.modifiers]
        mods.sort(key=lambda m: m[1] != GOLD)                 # стат сортировки — первым и золотым
        for line, (text, color) in zip(rows(mods_c, [1.0] * 3), mods[:3]):
            ui.label(text, line, "small", color=color)
        if entry.owner is not None and entry.owner in run.army.units:
            owner = run.army.units[entry.owner]
            face, info = cut_left(where_c, 76, 10)
            portrait(ui, app, owner.definition.id, place(face, (76, 76), "center"))
            who, state = rows(info, [1.0, 1.0])
            ui.label(t(owner.nickname), who, "small", color=GREEN)
            ui.label(t("worn"), state, "tiny", color=DIM)
        else:
            ui.label(t("free") + (f" ×{entry.count}" if entry.count > 1 else ""), where_c, "body")
        if clicked and not on_icon:
            if entry.owner is not None:
                open_unit(app, entry.owner, "inventory", tab="equipment", slot=entry.slot)
            else:
                flt.picked = entry.item_id
    if not entries:
        ui.label(t("nothing matches the filters"), pygame.Rect(TABLE_AREA.x, TABLE_AREA.y, TABLE_AREA.width, 44),
                 "body", color=DIM)


def draw_detail(ui: Gui, app: Any, flt: InventoryFilter) -> None:
    """Справа: выбранный свободный предмет и бойцы, на которых его можно надеть."""
    t, db, run = ui.t, app.db, app.run
    panel(ui, DETAIL, t("Item"))
    item_id = flt.picked if flt.picked and run.inventory.has(flt.picked) else None
    if item_id is None:
        flt.picked = None
        ui.paragraph(t("Click a free item to put it on someone."), DETAIL_AREA, color=DIM)
        return
    item = db.items[item_id]
    head, rest = cut_top(DETAIL_AREA, 120, 16)
    icon_r, name_r = cut_left(head, 120, 16)
    item_icon(ui, app, item_id, icon_r)
    ui.paragraph(t(item.name), name_r, ui.ts("heading", color=tier_color(item.rank)), max_lines=2)
    y = rest.y
    for text, color, _font in item_tip(t, db, item_id)[1:12]:
        if text and y < WEAR_TOP - 30:
            ui.label(text, pygame.Rect(rest.x, y, rest.width, 30), "small", color=color)
        y += 30 if text else 10
    wearers = [u for u in sorted(run.army.units.values(), key=lambda u: u.uid) if u.can_equip(item_id)]
    w.section(ui, pygame.Rect(DETAIL_AREA.x, WEAR_TOP, DETAIL_AREA.width, 44), t("Put on:"))
    for i, unit in enumerate(wearers):
        rect = wear_row(i)
        if rect.bottom > DETAIL_AREA.bottom:
            break
        body, clicked = w.selectable(ui, rect, "row")
        face, info = cut_left(inset(body, 4, 2), 76, 12)
        portrait(ui, app, unit.definition.id, place(face, (76, 76), "center"))
        text_c, delta_c = cols(info, [1.0, 140], 8)
        who, now_r = rows(text_c, [1.0, 1.0])
        ui.label(f"{t(unit.nickname)} {t('lv {n}', n=unit.state.level)}", who, "small")
        slots = [k for k, s in enumerate(unit.definition.slots) if s == item.slot]
        slot = ([k for k in slots if unit.state.equipment[k] is None] or slots)[0]   # куда наденется
        current = unit.state.equipment[slot]
        now = t(db.items[current].name) if current in db.items else t("empty")
        ui.label(t("now: {item}", item=now), now_r, "tiny", color=DIM)
        after = preview_stats(app, unit, slot, item_id)
        changes = sorted(((after[s] - unit.stat(s), s) for s in Stat if after[s] != unit.stat(s)),
                         key=lambda c: -abs(c[0]))
        for line, (delta, stat) in zip(rows(delta_c, [1.0, 1.0]), changes[:2]):   # два самых заметных
            ui.label(f"{t(stat.value)} {delta:+d}", line, "tiny", align="right", color=GREEN if delta > 0 else ENEMY)
        if clicked:
            app.equip_anywhere(unit, item_id)
            if not run.inventory.has(item_id):
                flt.picked = None
