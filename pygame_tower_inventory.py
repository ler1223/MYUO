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
from pygame_tower_style import (ACCENTS, BOTTOM_Y, CELL, CONTENT_Y, DIM, GOLD, GOLD_DIM, GREEN, ENEMY, M, TEXT, W,
                                button, item_icon, panel, plate, portrait, preview_stats)
from pygame_ui import UI, lighter

SHOW = ("all", "free", "equipped")
GROUPS = {"all": (), "weapons": ("light_sword", "bow", "staff", "dagger", "heavy_weapon", "lance"),
          "armor": ("light_shield", "light_armor", "medium_armor", "robe"), "artifacts": ("artifact",)}
SORTS = ("tier", "name", "slot", "price")       # плюс любой стат: "stat:<имя>"
ANY = "__any__"

FILTERS = pygame.Rect(M, CONTENT_Y, 400, BOTTOM_Y - CONTENT_Y - 12)
DETAIL = pygame.Rect(W - M - 460, CONTENT_Y, 460, FILTERS.height)
TABLE = pygame.Rect(FILTERS.right + 20, CONTENT_Y, DETAIL.x - FILTERS.right - 40, FILTERS.height)
ROW = 100
TABLE_AREA = pygame.Rect(TABLE.x + 14, TABLE.y + 104, TABLE.width - 28, TABLE.height - 118)


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
        return (not group or item.slot in group) and (not flt.tier or item.tier == flt.tier) \
            and (wearer is None or item.slot in wearer.definition.slots)

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


# --- раскладка кнопок (общая для отрисовки и тестов) ---------------------------------

def show_button(i: int) -> pygame.Rect:
    return pygame.Rect(FILTERS.x + 20 + i * 124, FILTERS.y + 112, 116, 50)


def group_button(i: int) -> pygame.Rect:
    return pygame.Rect(FILTERS.x + 20 + (i % 2) * 182, FILTERS.y + 214 + (i // 2) * 58, 174, 50)


def tier_button(i: int) -> pygame.Rect:
    return pygame.Rect(FILTERS.x + 20 + i * 92, FILTERS.y + 382, 84, 50)


FITS_DROPDOWN = pygame.Rect(FILTERS.x + 20, FILTERS.y + 484, FILTERS.width - 40, 50)
SORT_DROPDOWN = pygame.Rect(FILTERS.x + 20, FILTERS.y + 586, FILTERS.width - 120, 50)
ORDER_BUTTON = pygame.Rect(SORT_DROPDOWN.right + 10, SORT_DROPDOWN.y, 70, 50)
RESET_BUTTON = pygame.Rect(FILTERS.x + 20, FILTERS.bottom - 74, FILTERS.width - 40, 54)


def table_row(i: int) -> pygame.Rect:
    return pygame.Rect(TABLE_AREA.x, TABLE_AREA.y + i * ROW, TABLE_AREA.width, ROW - 8)


def wear_row(i: int) -> pygame.Rect:
    """i-й боец в списке «надеть на» справа."""
    return pygame.Rect(DETAIL.x + 16, DETAIL.y + 560 + i * 92, DETAIL.width - 32, 84)


# --- отрисовка ----------------------------------------------------------------------

def draw_inventory(ui: UI, app: Any, open_unit: Callable[..., None]) -> None:
    flt = app.inv
    draw_filters(ui, app, flt)
    entries = inventory_entries(app, flt)
    draw_table(ui, app, flt, entries, open_unit)
    draw_detail(ui, app, flt)


def label(ui: UI, text: str, y: int) -> None:
    ui.text(text, FILTERS.x + 22, y, GOLD, "main")


def draw_filters(ui: UI, app: Any, flt: InventoryFilter) -> None:
    t = ui.t
    panel(ui, FILTERS, ACCENTS["prepare"], t("Filters"))
    label(ui, t("Show"), FILTERS.y + 76)
    for i, show in enumerate(SHOW):
        if button(ui, t({"all": "all", "free": "free", "equipped": "worn"}[show]), show_button(i),
                  selected=flt.show == show, font="small"):
            flt.show = show
    label(ui, t("Type"), FILTERS.y + 178)
    for i, group in enumerate(GROUPS):
        if button(ui, t({"all": "any type", "weapons": "weapons", "armor": "armor and shields",
                         "artifacts": "artifacts"}[group]), group_button(i), selected=flt.group == group, font="small"):
            flt.group = group
    label(ui, t("Tier"), FILTERS.y + 346)
    for i, tier in enumerate((0, 1, 2, 3)):
        text = t("any") if tier == 0 else ("I", "II", "III")[tier - 1]
        if button(ui, text, tier_button(i), selected=flt.tier == tier, font="small"):
            flt.tier = tier
    label(ui, t("Fits a fighter"), FILTERS.y + 448)
    units = sorted(app.run.army.units.values(), key=lambda u: u.uid)
    options = [(ANY, t("anyone"))] + [(u.uid, f"{t(u.name)} {t('lv {n}', n=u.state.level)}") for u in units]
    picked = ui.dropdown("inventory-fits", FITS_DROPDOWN, options, flt.fits if flt.fits is not None else ANY)
    if picked is not None:
        flt.fits = None if picked == ANY else picked
    label(ui, t("Sort by"), FILTERS.y + 550)
    sorts = [(s, t({"tier": "tier", "name": "name", "slot": "slot", "price": "price"}[s])) for s in SORTS]
    sorts += [(f"stat:{s.value}", t(s.value)) for s in Stat]
    picked = ui.dropdown("inventory-sort", SORT_DROPDOWN, sorts, flt.sort)
    if picked is not None:
        flt.sort = picked
    if button(ui, "v" if flt.descending else "^", ORDER_BUTTON):
        flt.descending = not flt.descending
    ui.tip(ORDER_BUTTON, lambda: [(t("descending") if flt.descending else t("ascending"), TEXT, "small")])
    if button(ui, t("Reset filters"), RESET_BUTTON, font="small"):
        app.inv = InventoryFilter(picked=flt.picked)


def draw_table(ui: UI, app: Any, flt: InventoryFilter, entries: list[Entry], open_unit: Callable[..., None]) -> None:
    t, db, run = ui.t, app.db, app.run
    free = sum(e.count for e in entries if e.owner is None)
    worn = sum(1 for e in entries if e.owner is not None)
    panel(ui, TABLE, ACCENTS["prepare"], t("Inventory"), t("free {a}, worn {b}", a=free, b=worn))
    for x, text in ((0, t("Item")), (TABLE_AREA.width - 520, t("Bonuses")), (TABLE_AREA.width - 230, t("Where"))):
        ui.text(text, TABLE_AREA.x + 14 + x, TABLE.y + 70, GOLD, "small")
    rows = max(1, TABLE_AREA.height // ROW)
    offset = ui.scroll("inventory-table", TABLE_AREA, len(entries), rows)
    sort_stat = Stat(flt.sort[5:]) if flt.sort.startswith("stat:") else None
    for i, entry in enumerate(entries[offset:offset + rows]):
        rect = table_row(i)
        item = db.items[entry.item_id]
        chosen = entry.owner is None and flt.picked == entry.item_id
        plate(ui, rect, (60, 52, 30) if chosen else (lighter(CELL, 14) if ui.hovered(rect) else CELL),
              GOLD if chosen else GOLD_DIM, cut=10)
        on_icon = bool(item_icon(ui, app, entry.item_id, pygame.Rect(rect.x + 8, rect.y + 6, 80, 80), entry.count))
        x = rect.x + 104
        ui.text(t(item.name), x, rect.y + 10, tier_color(item.tier), "main", rect.width - 660)
        ui.text(f"{t(item.slot)} · {item.price}", x, rect.y + 52, DIM, "small", rect.width - 660)
        mods = []
        for mod in item.modifiers:                       # стат сортировки — первым и золотым
            mods.append((modifier_text(t, mod), GOLD if mod.stat is sort_stat else TEXT))
        mods.sort(key=lambda m: m[1] != GOLD)
        mx = rect.right - 520
        for j, (text, color) in enumerate(mods[:3]):
            ui.text(text, mx, rect.y + 8 + j * 28, color, "small", 280)
        wx = rect.right - 230
        if entry.owner is not None and entry.owner in run.army.units:
            owner = run.army.units[entry.owner]
            portrait(ui, app, owner.definition.id, pygame.Rect(wx, rect.y + 8, 76, 76), GREEN)
            ui.text(t(owner.name), wx + 84, rect.y + 16, GREEN, "small", 140)
            ui.text(t("worn"), wx + 84, rect.y + 48, DIM, "tiny")
        else:
            ui.text(t("free") + (f" x{entry.count}" if entry.count > 1 else ""), wx, rect.y + 30, TEXT, "main")
        if ui.clicked(rect) and not on_icon:
            if entry.owner is not None:
                open_unit(app, entry.owner, "inventory", tab="equipment", slot=entry.slot)
            else:
                flt.picked = entry.item_id
    if not entries:
        ui.text(t("nothing matches the filters"), TABLE_AREA.x + 14, TABLE_AREA.y + 20, DIM, "main")


def draw_detail(ui: UI, app: Any, flt: InventoryFilter) -> None:
    """Справа: выбранный свободный предмет и бойцы, на которых его можно надеть."""
    t, db, run = ui.t, app.db, app.run
    body = panel(ui, DETAIL, ACCENTS["prepare"], t("Item"))
    item_id = flt.picked if flt.picked and run.inventory.has(flt.picked) else None
    if item_id is None:
        flt.picked = None
        ui.text(t("Click a free item to put it on someone."), DETAIL.x + 20, body.y + 20, DIM, "small",
                DETAIL.width - 40)
        return
    item = db.items[item_id]
    item_icon(ui, app, item_id, pygame.Rect(DETAIL.x + 20, body.y + 16, 120, 120))
    ui.text(t(item.name), DETAIL.x + 156, body.y + 20, tier_color(item.tier), "big", DETAIL.width - 176)
    y = body.y + 150
    for text, color, font in item_tip(t, db, item_id)[1:12]:
        if text:
            ui.text(text, DETAIL.x + 20, y, color, "small", DETAIL.width - 40)
        y += 26
    wearers = [u for u in sorted(run.army.units.values(), key=lambda u: u.uid) if item.slot in u.definition.slots]
    ui.text(t("Put on:"), DETAIL.x + 20, wear_row(0).y - 40, GOLD, "main")
    for i, unit in enumerate(wearers[:5]):
        rect = wear_row(i)
        plate(ui, rect, lighter(CELL, 14) if ui.hovered(rect) else CELL, GOLD_DIM, cut=8)
        portrait(ui, app, unit.definition.id, pygame.Rect(rect.x + 6, rect.y + 6, 72, 72))
        ui.text(f"{t(unit.name)} {t('lv {n}', n=unit.state.level)}", rect.x + 88, rect.y + 8, TEXT, "small",
                rect.width - 96)
        slots = [k for k, s in enumerate(unit.definition.slots) if s == item.slot]
        slot = ([k for k in slots if unit.state.equipment[k] is None] or slots)[0]   # куда наденется
        current = unit.state.equipment[slot]
        now = t(db.items[current].name) if current in db.items else t("empty")
        ui.text(t("now: {item}", item=now), rect.x + 88, rect.y + 44, DIM, "tiny", rect.width - 230)
        after = preview_stats(app, unit, slot, item_id)
        changes = sorted(((after[s] - unit.stat(s), s) for s in Stat if after[s] != unit.stat(s)),
                         key=lambda c: -abs(c[0]))
        for j, (delta, stat) in enumerate(changes[:2]):                  # два самых заметных изменения
            ui.text(f"{t(stat.value)} {delta:+d}", rect.right - 190, rect.y + 10 + j * 32,
                    GREEN if delta > 0 else ENEMY, "small", 180)
        if ui.clicked(rect):
            app.equip_anywhere(unit, item_id)
            if not run.inventory.has(item_id):
                flt.picked = None
