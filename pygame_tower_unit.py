"""Редактор бойца на подготовке в духе «Unit Details» Unicorn Overlord.

Слева: табличка (портрет, имя, уровень, до следующего, класс, тир, сила), фигура, особенности,
кнопки «В отряд/резерв» и «Повышение». Справа вкладки:
  Снаряжение — слоты длинными плашками, статы в две колонки с буквой оценки (S..F) и ромбиками AP/PP,
               снизу подходящие предметы инвентаря (при наведении — стрелки разницы статов);
  Навыки     — активные и пассивные с ценой, уровнем открытия и описанием;
  Тактика    — таблица как в UO: приоритет, навык (красный — за AP, синий — за PP), «Условие 1»,
               «Условие 2»; клик по ячейке открывает список вариантов поверх (слой PICK).
Условия в двух колонках — из трёх групп: «цель: …» (условие на цель), «я: …» (условие на себя),
«приоритет: …» (выбор цели); две из одной группы в одном правиле не выбираются.
"""
from __future__ import annotations

from typing import Any, Optional

import pygame

from game import promotion
from game.editing import describe_condition, describe_reaction, describe_skill, set_passive_tactics, set_tactics
from game.rating import rate_unit
from game.unit import Unit
from pygame_tips import modifier_text, tier_color
from pygame_tower_style import (BODY, DIM, GAP, GOLD, TEXT, bar, button, class_entries, class_line, crown, diamonds,
                                full_figure, item_icon, level_badge, portrait, preview_stats, skill_chip,
                                stat_rows, unit_name)
from uikit import Gui
from uikit import widgets as w
from uikit.layout import cols, cut_left, cut_top, grid, inset, place, row_of, rows

STATUS, EQUIPMENT, TACTICS = "status", "equipment", "tactics"     # STATUS — вкладка «Навыки»
NONE_ITEM = "__none__"
PICK = 6                                  # слой списка вариантов тактики: над всем, забирает мышь
TACTIC_ROWS = 8                           # строк в таблице тактики (правила + «Добавить тактику»)
TARGET, SELF, PRIORITY = "target", "self", "priority"
AP_TINT, PP_TINT = (170, 52, 40), (40, 104, 170)

# --- раскладка ------------------------------------------------------------------------

ART, EDITOR = cut_left(BODY, 700, GAP)
PLATE = pygame.Rect(ART.x, ART.y, ART.width, 176)
STAGE = pygame.Rect(ART.x, PLATE.bottom + 14, ART.width, ART.bottom - PLATE.bottom - 14 - 92)
FIELD_TOGGLE, PROMOTE_BUTTON = cols(pygame.Rect(ART.x + 10, ART.bottom - 80, ART.width - 20, 76), [1.0, 1.0], 12)
TAB_ROW = pygame.Rect(EDITOR.x + 30, EDITOR.y + 30, EDITOR.width - 60, 72)
TAB_ORDER = (EQUIPMENT, STATUS, TACTICS)
TABS = dict(zip(TAB_ORDER, row_of(TAB_ROW, [330, 330, 330], 10, "left")))
CONTENT = pygame.Rect(EDITOR.x, TAB_ROW.bottom, EDITOR.width, EDITOR.bottom - TAB_ROW.bottom)
CONTENT_BODY = inset(CONTENT, 44, 34, 44, 34)
PROMOTE_AREA = inset(EDITOR, 38, 92, 38, 36)
# снаряжение: сверху слоты и статы, снизу инвентарь
GEAR_TOP, GEAR_BOTTOM = rows(CONTENT_BODY, [520, 1.0], 24)
SLOTS_AREA, STATS_AREA = cols(GEAR_TOP, [1.0, 1.0], 40)
SLOT_ROW = 88
# тактика
TACTIC_HEAD = pygame.Rect(CONTENT_BODY.x, CONTENT_BODY.y, CONTENT_BODY.width, 40)
TACTIC_ROW = 66


def tactic_columns(row: pygame.Rect) -> list[pygame.Rect]:
    """Колонки строки тактики: приоритет, навык, условие 1, условие 2, кнопки."""
    return cols(row, [130, 1.3, 1.0, 1.0, 156], 12)


def tactic_row(i: int) -> pygame.Rect:
    return pygame.Rect(CONTENT_BODY.x, TACTIC_HEAD.bottom + 10 + i * (TACTIC_ROW + 8), CONTENT_BODY.width, TACTIC_ROW)


RESET_TACTICS = pygame.Rect(CONTENT_BODY.x, tactic_row(TACTIC_ROWS).y + 6, 420, 64)


def slot_row(i: int) -> pygame.Rect:
    return pygame.Rect(SLOTS_AREA.x, SLOTS_AREA.y + 54 + i * SLOT_ROW, SLOTS_AREA.width, SLOT_ROW - 8)


# --- общее с другими видами подготовки ---------------------------------------------------

def place_text(app: Any, unit: Unit) -> str:
    t = app.t
    formation = app.run.squad.formation
    position = formation.position_of(unit.uid)
    if position is None:
        return t("reserve")
    row, col = position
    names = {0: t("front row"), formation.rows - 1: t("back row")}
    return f"{names.get(row, t('middle row'))}, {t('place {n}', n=col + 1)}"


def leader_kind(app: Any, unit: Unit) -> str:
    """Рамка портрета: у лидера отряда — с короной."""
    return "leader" if app.run.squad.leader_uid == unit.uid else "normal"


def power_tip(ui: Gui, rect: pygame.Rect, rating: Any) -> None:
    """Подсказка: из чего сложилась сила."""
    t = ui.t
    ui.tip(rect, lambda: [(t("Power {n}", n=rating.power), GOLD, "main"),
                          (t("toughness {n}", n=round(rating.defence)), TEXT, "small"),
                          (t("damage per battle {n}", n=round(rating.offence)), TEXT, "small"),
                          (t("speed x{n}", n=f"{rating.speed:.2f}"), TEXT, "small"),
                          (t("passives {n}", n=rating.passives), TEXT, "small"), ("", TEXT, "small"),
                          (t("Formula estimate (data/rating.json); a fighter in the front row adds more toughness."),
                           DIM, "small")])


# --- слева: табличка, фигура, кнопки ----------------------------------------------------

def draw_unit_art(ui: Gui, app: Any, unit: Unit) -> None:
    t, run, db = ui.t, app.run, app.db
    body = w.frame(ui, "card", PLATE)
    face, info = cut_left(inset(body, 10, 8), body.height - 16, 18)
    portrait(ui, app, unit.definition.id, place(face, (face.height, face.height), "center"), leader_kind(app, unit))
    name_r, level_r, class_r = rows(info, [52, 40, 1.0], 2)
    ui.label(unit_name(t, unit), name_r, "title")
    right = level_badge(ui, pygame.Rect(level_r.x, level_r.y, 120, level_r.height), unit.state.level)
    need = app.rules.exp.per_level
    exp_r = pygame.Rect(right + 20, level_r.y, level_r.right - right - 20, level_r.height)
    label, track = cols(exp_r, [190, 1.0], 10)
    ui.label(t("to next {n}", n=max(0, need - unit.state.exp)), label, "small", color=(120, 200, 255))
    bar(ui, place(track, (track.width, 20), "center"), unit.state.exp, need, "exp")
    tier = unit.definition.tier
    ui.label(f"{class_line(t, unit)} · {t('tier {n}', n=tier)}", class_r, "body", color=DIM)
    rating = rate_unit(unit, db)
    power_r = ui.label(t("Power {n}", n=rating.power), class_r, "body", align="right", color=GOLD)
    power_tip(ui, power_r.inflate(12, 16), rating)
    if run.squad.leader_uid == unit.uid:
        crown(ui, app, (PLATE.right - 34, PLATE.y + 8), 40)

    stage_body = w.frame(ui, "panel", STAGE)
    glow = pygame.Surface(stage_body.size, pygame.SRCALPHA)
    for r in range(240, 0, -20):
        pygame.draw.circle(glow, (70, 90, 150, 9), (glow.get_width() // 2, glow.get_height() // 2), r * 1.3)
    ui.screen.blit(glow, stage_body.topleft)
    traits_r, figure_r = cut_top(inset(stage_body, 14, 8), 36, 6)
    tags = [t(db.tags[tag].name) for tag in unit.definition.tags if tag in db.tags]
    ui.label(" · ".join(tags), traits_r, "small", color=DIM, align="center")
    where_r, figure_r = cut_top(figure_r, 30, 4)
    ui.label(place_text(app, unit), where_r, "small", align="center", color=GOLD if
             run.squad.formation.position_of(unit.uid) else DIM)
    pedestal = place(figure_r, (figure_r.width * 2 // 3, 46), "bottom", (0, -10))
    art = ui.skin.images.get("field/pedestal")
    if art is not None:                           # постамент картинкой (ширина как у овала, высота по картинке)
        scaled = pygame.transform.smoothscale(art, (pedestal.width, round(art.get_height() * pedestal.width / art.get_width())))
        ui.screen.blit(scaled, scaled.get_rect(midtop=(pedestal.centerx, pedestal.y)))
    else:
        pygame.draw.ellipse(ui.screen, (10, 14, 28), pedestal)
        pygame.draw.ellipse(ui.screen, (150, 124, 72), pedestal, 2)
    full_figure(ui, app, unit.definition.id, (figure_r.width - 40, figure_r.height - 40),
                (pedestal.centerx, pedestal.centery + 6), look=unit.state.look)
    looks = app.figures.data.looks(unit.definition.id)
    if len(looks) > 1:                            # модель бойца: варианты класса из игры (пол, внешность)
        row = pygame.Rect(0, 0, 230, 34)
        row.midtop = (pedestal.centerx, pedestal.bottom + 4)
        left, label_r, right = pygame.Rect(row.x, row.y, 40, row.h), row.inflate(-88, 0), \
            pygame.Rect(row.right - 40, row.y, 40, row.h)
        index = unit.state.look % len(looks)
        if button(ui, "<", left, style="small"):
            app.set_look(unit, (index - 1) % len(looks))
        if button(ui, ">", right, style="small"):
            app.set_look(unit, (index + 1) % len(looks))
        ui.label(t("Model {n}/{m}", n=index + 1, m=len(looks)), label_r, "small", align="center", color=DIM)

    fielded = run.squad.formation.position_of(unit.uid) is not None
    if button(ui, t("To reserve") if fielded else t("To the squad"), FIELD_TOGGLE):
        app.act(run.bench if fielded else run.field, unit.uid)
    paths = [p for p in unit.definition.promotions if p.class_id in db.units]
    if not paths:
        ui.label(t("final class"), PROMOTE_BUTTON, "small", align="center", color=DIM)
    elif app.view != "promote":
        ready = bool(promotion.available(unit, db))
        label = t("Promotion!") if ready else t("Promotion at lv {n}", n=min(p.level for p in paths))
        if button(ui, label, PROMOTE_BUTTON, primary=ready, style=None if ready else "small"):
            app.view = "promote"


# --- вкладки -----------------------------------------------------------------------------

def draw_editor(ui: Gui, app: Any, unit: Unit) -> None:
    """Вкладки и содержимое справа (табличка и фигура слева — draw_unit_art)."""
    t = ui.t
    draw_unit_art(ui, app, unit)
    labels = {EQUIPMENT: "Equipment", STATUS: "Skills", TACTICS: "Tactics"}
    icons = {EQUIPMENT: "icon/inventory", STATUS: "icon/units", TACTICS: "icon/tactics"}
    for tab, rect in TABS.items():
        if button(ui, t(labels[tab]), rect, tab=True, selected=app.tab == tab, icon_key=icons[tab], app=app):
            app.tab = tab
            app.tactic_pick = None
    w.frame(ui, "panel", CONTENT)
    {EQUIPMENT: draw_equipment, STATUS: draw_skills, TACTICS: draw_tactics}.get(app.tab, draw_equipment)(ui, app, unit)


# --- снаряжение --------------------------------------------------------------------------

def draw_equipment(ui: Gui, app: Any, unit: Unit) -> None:
    t, db, inventory = ui.t, app.db, app.run.inventory
    w.section(ui, SLOTS_AREA, t("Equipment"))
    slots = unit.definition.slots
    app.slot = min(app.slot, max(0, len(slots) - 1))
    for index, slot in enumerate(slots):
        rect = slot_row(index)
        if rect.bottom > SLOTS_AREA.bottom:
            break
        body, clicked = w.selectable(ui, rect, "row", selected=index == app.slot)
        icon_r, text_r = cut_left(inset(body, 6, 2), body.height - 4, 14)
        current = unit.state.equipment[index]
        name_r, kind_r = rows(text_r, [1.0, 26])
        if current is not None and current in db.items:
            item = db.items[current]
            item_icon(ui, app, current, place(icon_r, (icon_r.height, icon_r.height), "center"))
            ui.label(t(item.name), name_r, "body", color=tier_color(item.rank))
            ui.label(f"{t(slot)} · " + ", ".join(modifier_text(t, m) for m in item.modifiers[:2]), kind_r, "tiny",
                     color=DIM)
        else:
            w.family_frame(ui, "slot", place(icon_r, (icon_r.height, icon_r.height), "center"), "empty")
            ui.label(f"({t(slot)})", name_r, "body", color=DIM)
        if clicked:
            app.slot = index

    head = w.section(ui, STATS_AREA, t("Parameters"))
    gems, stats_r = cut_top(head, 36, 8)
    ap_r, pp_r = cols(gems, [1.0, 1.0], 20)
    ui.label("AP", ap_r, "heading", color=(120, 170, 250))
    diamonds(ui, app, ap_r.x + 48, ap_r.centery, unit.ap_max, "ap", size=22)
    ui.label("PP", pp_r, "heading", color=(200, 140, 240))
    diamonds(ui, app, pp_r.x + 48, pp_r.centery, unit.pp_max, "pp", size=22)

    hovered: Optional[str] = None
    area = w.section(ui, GEAR_BOTTOM, t("Inventory: {slot}", slot=t(slots[app.slot])) if slots else t("Inventory"))
    if slots:
        slot = slots[app.slot]
        fits = [i for i, n in sorted(inventory.items.items(), key=lambda kv: -db.items[kv[0]].tier
                                     if kv[0] in db.items else 0)
                if n > 0 and i in db.items and db.items[i].slot == slot and unit.can_equip(i)]
        options = ([NONE_ITEM] if unit.state.equipment[app.slot] is not None else []) + fits
        lines = max(1, (area.height + 8) // 92)
        offset = ui.scroll(("tower-fits", unit.uid, app.slot), area, (len(options) + 1) // 2, lines) * 2
        for cell, item_id in zip(grid(area, min(len(options) - offset, lines * 2), 2, 84, 16, 8), options[offset:]):
            hover = ui.hovered(cell)
            body, clicked = w.selectable(ui, cell, "row")
            if item_id == NONE_ITEM:
                ui.label(t("Take off"), inset(body, 20, 0), "body", color=DIM)
            else:
                item = db.items[item_id]
                icon_r, text_r = cut_left(inset(body, 4, 2), body.height - 4, 12)
                item_icon(ui, app, item_id, place(icon_r, (icon_r.height, icon_r.height), "center"),
                          inventory.count(item_id))
                name_r, mods_r = rows(text_r, [1.0, 1.0])
                ui.label(t(item.name), name_r, "small", color=tier_color(item.rank))
                ui.label(", ".join(modifier_text(t, m) for m in item.modifiers[:3]), mods_r, "tiny", color=DIM)
            if hover:
                hovered = item_id
            if clicked:
                app.change_equipment(unit, app.slot, item_id)
        if not options:
            ui.label(t("no fitting items in the inventory"), pygame.Rect(area.x, area.y, area.width, 40), "small",
                     color=DIM)
    preview = preview_stats(app, unit, app.slot, None if hovered == NONE_ITEM else hovered) \
        if hovered is not None else None
    stat_rows(ui, app, unit, stats_r, 2, preview, style="small", grades=True)


# --- навыки ------------------------------------------------------------------------------

def skill_lines(unit: Unit) -> tuple[list, list]:
    """(активные, пассивные): (вид, id, уровень открытия) класса и снаряжения."""
    entries = class_entries(unit)
    items = [("skill", s, 1) for item in unit.equipped for s in item.skills] + \
            [("passive", p, 1) for item in unit.equipped for p in item.passives]
    skills = [e for e in entries if e[0] == "skill"] + [e for e in items if e[0] == "skill"]
    passives = [e for e in entries if e[0] == "passive"] + [e for e in items if e[0] == "passive"]
    return skills, passives


def skill_list(ui: Gui, app: Any, unit: Unit, entries: list, area: pygame.Rect) -> pygame.Rect:
    """Навыки строками с описанием под каждой. Возвращает остаток области."""
    db, t = app.db, ui.t
    for kind, entry_id, unlock in entries:
        if area.height < 92:
            break
        row, area = cut_top(area, 92, 10)
        chip, note = rows(row, [50, 1.0], 2)
        skill_chip(ui, app, kind, entry_id, chip, unlock, unit.state.level, costs=True)
        if kind == "skill" and entry_id in db.skills:
            parts = describe_skill(db.skills[entry_id], db, t).split(" | ")
            line = ", ".join(parts[1:]) or parts[0]
        elif entry_id in db.passives:
            line = describe_reaction(db.passives[entry_id].reaction, db, t)
        else:
            line = ""
        ui.label(line, inset(note, 56, 0, 8, 0), "tiny", color=DIM)
    return area


def draw_skills(ui: Gui, app: Any, unit: Unit) -> None:
    t = ui.t
    skills, passives = skill_lines(unit)
    left, right = cols(CONTENT_BODY, [1.0, 1.0], 40)
    skill_list(ui, app, unit, skills, w.section(ui, left, t("Active skills"), f"{len(skills)}"))
    skill_list(ui, app, unit, passives, w.section(ui, right, t("Passive skills"), f"{len(passives)}"))


# --- тактика -----------------------------------------------------------------------------

def condition_options(db: Any) -> list[tuple[str, Any, str, dict]]:
    """Варианты условий: (группа, значение, шаблон подписи, параметры подписи)."""
    out: list[tuple[str, Any, str, dict]] = []
    for value in (0.25, 0.5, 0.75):
        out.append((TARGET, {"type": "hp_below", "value": value}, "Target HP below {n}%", {"n": round(value * 100)}))
    out.append((TARGET, {"type": "hp_above", "value": 1.0}, "Target at full HP", {}))
    for tag in ("infantry", "cavalry", "flying", "armored", "archer", "caster", "scout", "elf", "bestral"):
        if tag in db.tags:
            out.append((TARGET, {"type": "has_tag", "tag": tag}, "Target: {tag}", {"tag": db.tags[tag].name}))
    if "armored" in db.tags:
        out.append((TARGET, {"type": "lacks_tag", "tag": "armored"}, "Target: not armored", {}))
    out.append((TARGET, {"type": "has_label", "label": "debuff"}, "Target is debuffed", {}))
    out.append((TARGET, {"type": "has_label", "label": "buff"}, "Target is buffed", {}))
    for effect_id, word in (("uo_poison", "poisoned"), ("uo_burn", "burning"), ("uo_freeze", "frozen"),
                            ("uo_stun", "stunned")):
        if effect_id in db.effects:
            out.append((TARGET, {"type": "has_effect", "effect_id": effect_id}, f"Target is {word}", {}))
            out.append((TARGET, {"type": "lacks_effect", "effect_id": effect_id}, f"Target is not {word}", {}))
    for value in (0.25, 0.5, 0.75):
        out.append((SELF, {"type": "hp_below", "value": value}, "My HP below {n}%", {"n": round(value * 100)}))
    out.append((SELF, {"type": "hp_above", "value": 1.0}, "My HP is full", {}))
    out.append((SELF, {"type": "has_label", "label": "buff"}, "I am buffed", {}))
    out.append((SELF, {"type": "has_label", "label": "debuff"}, "I am debuffed", {}))
    for selector, label in (("weakest", "Prioritize lowest HP"), ("strongest", "Prioritize strongest"),
                            ("backmost", "Prioritize back row"), ("random", "Random target"),
                            ("frontmost", "Prioritize front row")):
        out.append((PRIORITY, selector, label, {}))
    return out


GROUP_KEYS = {TARGET: "condition", SELF: "self_condition", PRIORITY: "selector"}
DEFAULTS = {TARGET: {"type": "always"}, SELF: {"type": "always"}, PRIORITY: "frontmost"}


def rule_items(rule: dict) -> list[tuple[str, Any]]:
    """Заполненные условия правила по порядку колонок: (группа, значение); не больше двух."""
    items = [(group, rule.get(key, DEFAULTS[group])) for group, key in GROUP_KEYS.items()]
    return [(group, value) for group, value in items if value != DEFAULTS[group]][:2]


def set_column(rule: dict, column: int, group: Optional[str], value: Any) -> dict:
    """Правило, в колонке column которого теперь (group, value); group None — очистить колонку."""
    rule = dict(rule)
    items = rule_items(rule)
    if column < len(items):
        old_group = items[column][0]
        rule[GROUP_KEYS[old_group]] = DEFAULTS[old_group]
    if group is not None:
        rule[GROUP_KEYS[group]] = value
    return rule


def option_label(ui: Gui, db: Any, group: str, value: Any) -> str:
    t = ui.t
    for g, v, template, params in condition_options(db):
        if g == group and v == value:
            return t(template, **{k: t(p) if isinstance(p, str) else p for k, p in params.items()})
    if group == PRIORITY:
        return t(value)
    prefix = t("Target:") if group == TARGET else t("Me:")
    return f"{prefix} {describe_condition(value, t)}"


def tinted_pill(ui: Gui, rect: pygame.Rect, tint, hover: bool, kind: str = "condition") -> pygame.Rect:
    """Плашка строки тактики: картинка frame/tactic_<kind> (ap, pp, condition), если нарисована,
    иначе рамка строки с цветной заливкой тела (навык: красный — AP, синий — PP)."""
    if ui.skin.has(f"tactic_{kind}"):
        body = w.frame(ui, f"tactic_{kind}", rect)
        if hover:
            glow = pygame.Surface(body.size, pygame.SRCALPHA)
            glow.fill((255, 240, 200, 30))
            ui.screen.blit(glow, body.topleft)
        return body
    body = w.family_frame(ui, "row", rect, "hover" if hover else "normal")
    if tint is not None:
        fill = pygame.Surface(body.size, pygame.SRCALPHA)
        fill.fill((*tint, 150 if hover else 120))
        ui.screen.blit(fill, body.topleft)
    return body


def icon_button(ui: Gui, rect: pygame.Rect, kind: str, enabled: bool = True) -> bool:
    """Маленькая кнопка со значком, нарисованным линиями (вверх, вниз, убрать): не зависит от шрифта."""
    hover = enabled and ui.hovered(rect)
    box = place(rect, (min(rect.width, rect.height), min(rect.width, rect.height)), "center")
    pygame.draw.rect(ui.screen, (36, 48, 84) if hover else (16, 22, 42), box, border_radius=6)
    color = GOLD if hover else ((200, 170, 110) if enabled else (80, 80, 96))
    pygame.draw.rect(ui.screen, color, box, 2, border_radius=6)
    c, r = box.center, box.width // 4
    image = ui.skin.images.get(f"icon/{kind}")
    if image is not None:                         # нарисованный значок вместо линий
        side = box.width - 10
        icon = pygame.transform.smoothscale(image, (side, side))
        if not enabled:
            icon.set_alpha(90)
        ui.screen.blit(icon, icon.get_rect(center=c))
    elif kind == "up":
        pygame.draw.polygon(ui.screen, color, [(c[0] - r, c[1] + r // 2), (c[0] + r, c[1] + r // 2), (c[0], c[1] - r)])
    elif kind == "down":
        pygame.draw.polygon(ui.screen, color, [(c[0] - r, c[1] - r // 2), (c[0] + r, c[1] - r // 2), (c[0], c[1] + r)])
    else:
        pygame.draw.line(ui.screen, color, (c[0] - r, c[1] - r), (c[0] + r, c[1] + r), 3)
        pygame.draw.line(ui.screen, color, (c[0] - r, c[1] + r), (c[0] + r, c[1] - r), 3)
    return enabled and bool(ui.clicked(rect))


def draw_tactics(ui: Gui, app: Any, unit: Unit) -> None:
    t, db = ui.t, app.db
    selected = getattr(app, "tactic_passive", None)      # None — тактики юнита, иначе id пассивки
    if selected is not None and selected not in unit.passive_ids:
        selected = None
        app.tactic_passive = None
    if selected is None:
        rules_ = [dict(r) for r in unit.tactics.to_list()]
    else:
        rules_ = [dict(r) for r in unit.passive_tactics_of(selected).to_list()]
    head = tactic_columns(TACTIC_HEAD)
    for rect, text in zip(head, (t("Priority"), t("Skill"), t("Condition 1"), t("Condition 2"))):
        ui.label(text, rect, "label", align="center")
    w.divider(ui, TACTIC_HEAD.x, TACTIC_HEAD.right, TACTIC_HEAD.bottom + 2)
    changed: Optional[list] = None
    pick = getattr(app, "tactic_pick", None)
    for i in range(TACTIC_ROWS):
        row = tactic_row(i)
        number_r, skill_r, first_r, second_r, actions_r = tactic_columns(row)
        if i >= len(rules_):
            if i == len(rules_) and unit.skill_ids:
                add = inset(pygame.Rect(skill_r.x, row.y, second_r.right - skill_r.x, row.height), 0, 8)
                hover = ui.hovered(add, 0)
                ui.label("+ " + t("Add a tactic"), add, "body", align="left", color=TEXT if hover else DIM)
                if ui.clicked(add):
                    changed = rules_ + [{"skill": unit.skill_ids[0], "condition": DEFAULTS[TARGET],
                                         "self_condition": DEFAULTS[SELF], "selector": DEFAULTS[PRIORITY]}]
            continue
        rule = rules_[i]
        badge = place(number_r, (64, 56), "center")
        if not ui.skin.draw(ui.screen, "priority", badge):
            pygame.draw.polygon(ui.screen, (90, 40, 30), [(badge.x + 10, badge.y), (badge.right, badge.y),
                                                          (badge.right - 10, badge.bottom), (badge.x, badge.bottom)])
        ui.label(str(i + 1), badge, ui.ts("level", size=34), align="center")
        skill = db.skills.get(rule["skill"])
        tint = PP_TINT if skill is not None and skill.pp_cost and not skill.ap_cost else AP_TINT
        kind = "pp" if tint == PP_TINT else "ap"
        body = tinted_pill(ui, skill_r, tint, ui.hovered(skill_r) or pick == (i, "skill"), kind)
        cost = (skill.pp_cost if kind == "pp" else skill.ap_cost) if skill is not None else 0
        right = diamonds(ui, app, body.x + 8, body.centery, cost, kind, size=18)
        ui.label(t(skill.name) if skill else rule["skill"], pygame.Rect(right + 8, body.y, body.right - right - 12,
                                                                         body.height), "body", align="center")
        if skill is not None:
            ui.tip(skill_r, lambda s=skill: [(t(s.name), GOLD, "main"),
                                             (describe_skill(s, db, t).replace(" | ", "\n"), TEXT, "small")])
        if ui.clicked(skill_r):
            app.tactic_pick = (i, "skill")
        items = rule_items(rule)
        for column, cell in enumerate((first_r, second_r)):
            body = tinted_pill(ui, cell, None, ui.hovered(cell) or pick == (i, column))
            if column < len(items):
                ui.label(option_label(ui, db, *items[column]), inset(body, 8, 0), "small", align="center")
            else:
                ui.label("—", body, "body", align="center", color=DIM)
            if ui.clicked(cell):
                app.tactic_pick = (i, column)
        up, down, remove = cols(inset(actions_r, 0, 10), [1.0, 1.0, 1.0], 8)
        if icon_button(ui, up, "up", enabled=i > 0):
            changed = rules_[:]
            changed[i - 1], changed[i] = changed[i], changed[i - 1]
        if icon_button(ui, down, "down", enabled=i < len(rules_) - 1):
            changed = rules_[:]
            changed[i + 1], changed[i] = changed[i], changed[i + 1]
        if icon_button(ui, remove, "remove"):
            changed = rules_[:i] + rules_[i + 1:]
    reset = RESET_TACTICS
    custom = unit.has_custom_tactics if selected is None else unit.has_passive_tactics(selected)
    if button(ui, t("Reset to default"), reset, enabled=custom):
        if selected is None:
            unit.reset_tactics()
        else:
            unit.reset_passive_tactics(selected)
        app.tactic_pick = None
        app.save()
    note = pygame.Rect(reset.right + 30, reset.y, CONTENT_BODY.right - reset.right - 30, reset.height)
    if selected is None:
        note_text = t("Rules are checked top to bottom: the first one whose conditions hold, with a target and "
                      "enough AP, is used.")
    else:
        note_text = t("Passive rules pick a skill for the targets that caused the trigger; without rules the "
                      "passive works as written in its data.")
    ui.paragraph(note_text, note, color=DIM, max_lines=3)
    # Пассивки настраиваются в той же таблице: переключатель юнит <-> пассивка.
    hint = pygame.Rect(CONTENT_BODY.x, reset.bottom + 14, CONTENT_BODY.width, 24)
    ui.label(t("Whose tactics to edit (passives apply to the targets that caused the trigger):"),
             hint, "small", color=DIM)
    switch = pygame.Rect(CONTENT_BODY.x, hint.bottom + 6, CONTENT_BODY.width, 48)
    ids = [None] + [pid for pid in unit.passive_ids if pid in db.passives]
    for pid, rect in zip(ids, row_of(switch, [300] * len(ids), 12, "left")):
        name = t("Main tactics") if pid is None else t(db.passives[pid].name)
        if pid is not None and unit.has_passive_tactics(pid):
            name += " *"
        if button(ui, name, rect, selected=selected == pid, style="small"):
            app.tactic_passive = pid
            app.tactic_pick = None
    if pick is not None and pick[0] < len(rules_):
        picked = draw_picker(ui, app, unit, rules_, pick)
        if picked is not None:
            changed = picked
    if changed is not None:
        try:
            if selected is None:
                set_tactics(db, unit, changed)
            else:
                set_passive_tactics(db, unit, selected, changed)
            app.save()
        except (ValueError, KeyError) as error:
            app.message = str(error)


def draw_picker(ui: Gui, app: Any, unit: Unit, rules_: list, pick: tuple) -> Optional[list]:
    """Список вариантов поверх таблицы (слой PICK): навыки или условия. Клик обрабатывается сразу,
    рисуется список в конце кадра поверх всего. Возвращает новые правила или None."""
    t, db = ui.t, app.db
    index, column = pick
    rule = rules_[index]
    anchor = tactic_columns(tactic_row(index))[1 if column == "skill" else 2 + column]
    if column == "skill":
        options = [("skill", skill_id) for skill_id in unit.skill_ids if skill_id in db.skills]
    else:
        other = {g for k, (g, _v) in enumerate(rule_items(rule)) if k != column}
        options = [(None, None)] + [(g, v) for g, v, _tmpl, _p in condition_options(db) if g not in other]
    row_h = 50
    width = 430
    height = min(len(options) * row_h + 24, CONTENT_BODY.height - 20)
    box = pygame.Rect(anchor.x - 60, anchor.bottom + 6, width, height)
    if box.bottom > CONTENT_BODY.bottom:          # вниз не влезает — сбоку от ячейки, не закрывая её
        box.y = CONTENT_BODY.y
        box.right = anchor.x - 8
        if box.x < CONTENT_BODY.x - 20:
            box.x = anchor.right + 8
    box.clamp_ip(CONTENT_BODY.inflate(40, 40))
    ui.block(box, PICK)
    visible = max(1, (box.height - 24) // row_h)
    offset = ui.scroll(("tactic-pick", unit.uid, index, column), box, len(options), visible)
    shown = [(pygame.Rect(box.x + 12, box.y + 12 + k * row_h, box.width - 24, row_h - 6), group, value)
             for k, (group, value) in enumerate(options[offset:offset + visible])]
    result = None
    for row, group, value in shown:
        if any(row.collidepoint(pos) for pos, _ in ui.clicks):
            new_rule = dict(rule, skill=value) if group == "skill" else set_column(rule, column, group, value)
            result = rules_[:index] + [new_rule] + rules_[index + 1:]
            app.tactic_pick = None
    if ui.clicks and not any(box.collidepoint(p) or anchor.collidepoint(p) for p, _ in ui.clicks)             and app.tactic_pick == pick:
        app.tactic_pick = None                               # клик мимо списка закрывает его
    colors = {TARGET: (240, 180, 160), SELF: (160, 220, 170), PRIORITY: (170, 200, 250)}

    def draw() -> None:
        w.frame(ui, "picker" if ui.skin.has("picker") else "inset", box.inflate(16, 16))
        for row, group, value in shown:
            if row.collidepoint(ui.mouse):
                fill = pygame.Surface(row.size, pygame.SRCALPHA)
                fill.fill((244, 208, 112, 40))
                ui.screen.blit(fill, row.topleft)
            if group == "skill":
                skill = db.skills[value]
                kind = "pp" if skill.pp_cost and not skill.ap_cost else "ap"
                right = diamonds(ui, app, row.x + 6, row.centery, skill.pp_cost if kind == "pp" else skill.ap_cost,
                                 kind, size=18)
                ui.label(t(skill.name), pygame.Rect(right + 10, row.y, row.right - right - 10, row.height), "body",
                         color=GOLD if value == rule["skill"] else TEXT)
            elif group is None:
                ui.label("— " + t("No condition"), inset(row, 10, 0), "body", color=DIM)
            else:
                ui.label(option_label(ui, db, group, value), inset(row, 10, 0), "body", color=colors[group])

    ui.later(PICK, draw)
    return result
