"""Экраны редакторов справочника: эффекты и области."""
from __future__ import annotations

import copy
from typing import Optional

import pygame

from game.areas import AREA_SINGLE, MAX_SPAN
from game.editing import new_area_data, new_effect_data
from game.effects import TRIGGER_ACTIONS, TRIGGER_TARGETS, TRIGGER_WHEN, StackRule
from game.stats import ModOp, Stat
from game.tags import TAG_DAMAGE, TAG_SKILL, TAG_UNIT
from pygame_data_editors import list_buttons
from pygame_editors import EMPTY, FORM_X, ROW_H, TOP, EditorHost, apply, entity_list, named, plain, tag_options
from pygame_ui import DIM, PANEL, RED, SLOT, TEXT, UI, WIDTH, YELLOW

EFFECT_LABELS = ("buff", "debuff", "passive")   # метки самого эффекта: по ним работает снятие эффектов
ENGINE_FLAGS = ("stunned",)                     # флаги, которые понимает бой
MODIFIER_ROWS = 3
TRIGGER_ROWS = 4
OP_LABELS = {ModOp.FLAT: "+ value", ModOp.PERCENT_ADD: "+ share (0.2 = +20%)", ModOp.PERCENT_MULT: "x multiplier"}
AREA_TARGETS = ("allies", "enemies", "everyone")  # цели триггера, для которых имеет смысл область
EFFECT_ACTIONS = ("apply_effect", "remove_effect")


class EffectEditor:
    """Эффект: длительность и стаки, модификаторы статов, теги, поведение по триггерам, изменение атак."""

    def __init__(self) -> None:
        self.effect_id: Optional[str] = None

    def draw(self, ui: UI, app: EditorHost) -> None:
        db = app.db
        if self.effect_id not in db.effects:
            self.effect_id = next(iter(db.effects), None)
        if self.effect_id is not None:
            self._draw_form(ui, app, self.effect_id)
        ui.text(ui.t("Effects"), 16, TOP, DIM, "small")
        clicked = entity_list(ui, "effects", named(ui, db.effects.values()), self.effect_id, TOP + 20, 18)
        if clicked is not None:
            self.effect_id = clicked
        new, delete = list_buttons(ui, self.effect_id is not None)
        if new:
            self.effect_id = db.create("effects", "New Effect", new_effect_data())
            app.data_changed()
        elif delete:
            db.delete("effects", self.effect_id)  # эффект уходит из навыков, триггеров и пассивок
            app.data_changed()

    def _draw_form(self, ui: UI, app: EditorHost, effect_id: str) -> None:
        t, db, x = ui.t, app.db, FORM_X
        data = db.effects[effect_id].to_dict()
        new = copy.deepcopy(data)
        key = ("effect", effect_id)

        ui.text(t("Name"), x, TOP + 4, font="small")
        name = ui.text_input((key, "name"), pygame.Rect(x + 76, TOP, 220, 24), data["name"])
        if name:
            new["name"] = name
        ui.text(f"id: {effect_id}", x + 310, TOP + 5, DIM, "small")

        # Длительность, заряды, стаки. 0 в полях длительности и зарядов значит «нет ограничения».
        y = TOP + 30
        for field, label, fx, label_w in (("duration", "Turns", 0, 76), ("charges", "Charges", 132, 62)):
            ui.text(t(label), x + fx, y + 4, font="small")
            value = ui.number_input((key, field), pygame.Rect(x + fx + label_w, y, 44, 24), data[field] or 0, 0, 99)
            if value is not None:
                new[field] = value or None
        ui.text(t("Reapplying"), x + 256, y + 4, font="small")
        picked = ui.dropdown((key, "stack_rule"), pygame.Rect(x + 346, y, 110, 24),
                             plain(ui, (r.value for r in StackRule)), data["stack_rule"])
        if picked is not None:
            new["stack_rule"] = picked
        ui.text(t("Max stacks"), x + 470, y + 4, font="small")
        value = ui.number_input((key, "max_stacks"), pygame.Rect(x + 560, y, 44, 24), data["max_stacks"], 1, 99)
        if value is not None:
            new["max_stacks"] = value
        ui.text(t("0 turns = permanent"), x + 616, y + 5, DIM, "small")

        # Метки, флаги, теги носителю
        y = TOP + 60
        flags = sorted({*ENGINE_FLAGS, *(f for e in db.effects.values() for f in e.flags)})
        lists = (("tags", "Labels", plain(ui, EFFECT_LABELS), 0, 76, 150),
                 ("flags", "Flags", plain(ui, flags), 240, 50, 150),
                 ("grants_tags", "Gives tags", tag_options(ui, db, TAG_UNIT), 454, 84, 220))
        for field, label, choices, fx, label_w, width in lists:
            ui.text(t(label), x + fx, y + 4, font="small")
            picked = ui.multiselect((key, field), pygame.Rect(x + fx + label_w, y, width, 24), choices, data[field])
            if picked is not None:
                new[field] = picked

        self._draw_modifiers(ui, key, data, new, x, TOP + 92)
        self._draw_triggers(ui, db, key, data, new, x, TOP + 92 + 44 + MODIFIER_ROWS * ROW_H + 6)
        self._draw_attack_mod(ui, db, key, data, new, x, TOP + 92 + 2 * 44 + (MODIFIER_ROWS + TRIGGER_ROWS) * ROW_H + 14)
        if new != data:
            apply(app, "effects", effect_id, new)

    def _draw_modifiers(self, ui: UI, key, data: dict, new: dict, x: int, y: int) -> None:
        t = ui.t
        modifiers = data["modifiers"]
        ui.text(t("Stat modifiers: {n}", n=len(modifiers)), x, y + 4, font="small")
        if ui.button(t("+ Add modifier"), pygame.Rect(x + 250, y, 190, 22)):
            new["modifiers"] = modifiers + [{"stat": Stat.PHYS_ATK.value, "op": ModOp.PERCENT_ADD.value, "value": 0.2}]
        for label, offset in (("stat", 22), ("operation", 190), ("value", 404)):
            ui.text(t(label), x + offset, y + 26, DIM, "small")
        y += 44
        area = pygame.Rect(x, y - 2, WIDTH - x - 16, MODIFIER_ROWS * ROW_H)
        pygame.draw.rect(ui.screen, PANEL, area)
        offset = ui.scroll((key, "modifiers"), area, len(modifiers), MODIFIER_ROWS)
        stat_choices = plain(ui, (s.value for s in Stat))
        op_choices = [(op.value, t(label)) for op, label in OP_LABELS.items()]
        for row, index in enumerate(range(offset, min(len(modifiers), offset + MODIFIER_ROWS))):
            mod = modifiers[index]
            edited = dict(mod)
            ry, mkey = y + row * ROW_H, (key, "mod", index)
            ui.text(f"{index + 1}.", x + 4, ry + 4, DIM, "small")
            picked = ui.dropdown((mkey, "stat"), pygame.Rect(x + 22, ry, 164, 24), stat_choices, mod["stat"])
            if picked is not None:
                edited["stat"] = picked
            picked = ui.dropdown((mkey, "op"), pygame.Rect(x + 190, ry, 210, 24), op_choices, mod["op"])
            if picked is not None:
                edited["op"] = picked
            value = ui.number_input((mkey, "value"), pygame.Rect(x + 404, ry, 64, 24), mod["value"], -9999, 9999, False)
            if value is not None:
                edited["value"] = value
            if ui.button("x", pygame.Rect(x + 474, ry, 24, 24), color=RED):
                new["modifiers"] = modifiers[:index] + modifiers[index + 1:]
            elif edited != mod:
                new["modifiers"] = modifiers[:index] + [edited] + modifiers[index + 1:]

    def _draw_triggers(self, ui: UI, db, key, data: dict, new: dict, x: int, y: int) -> None:
        """Поведение эффекта: строки «когда -> что -> сколько / какой эффект -> кому -> в какой области»."""
        t = ui.t
        triggers = data["triggers"]
        ui.text(t("Behaviour (when -> what -> to whom): {n}", n=len(triggers)), x, y + 4, font="small")
        if ui.button(t("+ Add trigger"), pygame.Rect(x + 320, y, 170, 22)):
            new["triggers"] = triggers + [{"when": "turn_start", "action": "damage", "amount": 1, "effect_id": None,
                                           "to": "self", "area": None}]
        cols = (("when", 22), ("what", 126), ("amount", 250), ("effect", 298), ("to whom", 432), ("area", 532))
        for label, offset in cols:
            ui.text(t(label), x + offset, y + 26, DIM, "small")
        y += 44
        area = pygame.Rect(x, y - 2, WIDTH - x - 16, TRIGGER_ROWS * ROW_H)
        pygame.draw.rect(ui.screen, PANEL, area)
        offset = ui.scroll((key, "triggers"), area, len(triggers), TRIGGER_ROWS)
        effect_choices = named(ui, db.effects.values())
        area_choices = [(EMPTY, t("whole side")), *named(ui, db.areas.values())]
        for row, index in enumerate(range(offset, min(len(triggers), offset + TRIGGER_ROWS))):
            trigger = triggers[index]
            edited = dict(trigger)
            ry, tkey = y + row * ROW_H, (key, "trigger", index)
            ui.text(f"{index + 1}.", x + 4, ry + 4, DIM, "small")
            picked = ui.dropdown((tkey, "when"), pygame.Rect(x + 22, ry, 100, 24), plain(ui, TRIGGER_WHEN), trigger["when"])
            if picked is not None:
                edited["when"] = picked
            picked = ui.dropdown((tkey, "action"), pygame.Rect(x + 126, ry, 120, 24), plain(ui, TRIGGER_ACTIONS),
                                 trigger["action"])
            if picked is not None and picked != trigger["action"]:
                edited["action"] = picked
                needs_effect = picked in EFFECT_ACTIONS
                edited["effect_id"] = (trigger["effect_id"] or next(iter(db.effects))) if needs_effect else None
            uses_effect = trigger["action"] in EFFECT_ACTIONS
            if uses_effect:
                picked = ui.dropdown((tkey, "effect"), pygame.Rect(x + 298, ry, 130, 24), effect_choices, trigger["effect_id"])
                if picked is not None:
                    edited["effect_id"] = picked
            else:
                value = ui.number_input((tkey, "amount"), pygame.Rect(x + 250, ry, 44, 24), trigger["amount"], 0, 999)
                if value is not None:
                    edited["amount"] = value
            picked = ui.dropdown((tkey, "to"), pygame.Rect(x + 432, ry, 96, 24), plain(ui, TRIGGER_TARGETS), trigger["to"])
            if picked is not None:
                edited["to"] = picked
                if picked not in AREA_TARGETS:
                    edited["area"] = None
            if trigger["to"] in AREA_TARGETS:
                picked = ui.dropdown((tkey, "area"), pygame.Rect(x + 532, ry, 150, 24), area_choices, trigger["area"] or EMPTY)
                if picked is not None:
                    edited["area"] = picked or None
            if ui.button("x", pygame.Rect(x + 716, ry, 24, 24), color=RED):
                new["triggers"] = triggers[:index] + triggers[index + 1:]
            elif edited != trigger:
                new["triggers"] = triggers[:index] + [edited] + triggers[index + 1:]

    @staticmethod
    def _draw_attack_mod(ui: UI, db, key, data: dict, new: dict, x: int, y: int) -> None:
        """Как эффект меняет навыки носителя (редактируется первое изменение; остальные задаются в файле)."""
        t = ui.t
        mods = data["attack_mods"]
        ui.text(t("Changes the carrier's attacks"), x, y + 4, font="small")
        if ui.button(t("yes") if mods else t("no"), pygame.Rect(x + 250, y, 60, 22), bool(mods)):
            new["attack_mods"] = [] if mods else [{"add_tags": [], "power_mult": 1.0, "add_scaling": [],
                                                   "accuracy_add": 0, "crit_add": 0, "skill_tag": None}]
        if not mods:
            return
        mod = mods[0]
        edited = copy.deepcopy(mod)
        y += 28
        ui.text(t("adds tags"), x, y + 4, DIM, "small")
        tags = ui.multiselect((key, "am", "tags"), pygame.Rect(x + 76, y, 150, 24), tag_options(ui, db, TAG_DAMAGE), mod["add_tags"])
        if tags is not None:
            edited["add_tags"] = tags
        fields = (("power_mult", "power x", 236, 62, 0, 20, False), ("accuracy_add", "accuracy +", 356, 80, -200, 200, True),
                  ("crit_add", "crit +", 490, 50, -100, 100, True))
        for field, label, fx, label_w, low, high, integer in fields:
            ui.text(t(label), x + fx, y + 4, DIM, "small")
            value = ui.number_input((key, "am", field), pygame.Rect(x + fx + label_w, y, 44, 24), mod[field], low, high, integer)
            if value is not None:
                edited[field] = value
        ui.text(t("only skills"), x + 596, y + 4, DIM, "small")
        picked = ui.dropdown((key, "am", "skill_tag"), pygame.Rect(x + 672, y, 90, 24),
                             [(EMPTY, t("any")), *tag_options(ui, db, TAG_SKILL)], mod["skill_tag"] or EMPTY)
        if picked is not None:
            edited["skill_tag"] = picked or None
        if edited != mod:
            new["attack_mods"] = [edited, *mods[1:]]


class AreaEditor:
    """Область: клетки вокруг опорной (цели навыка или самого юнита), которые она задевает."""

    CELL = 28
    GRID_Y = TOP + 86

    def __init__(self) -> None:
        self.area_id: Optional[str] = None

    def draw(self, ui: UI, app: EditorHost) -> None:
        db = app.db
        if self.area_id not in db.areas:
            self.area_id = next(iter(db.areas), None)
        if self.area_id is not None:
            self._draw_form(ui, app, self.area_id)
        ui.text(ui.t("Areas"), 16, TOP, DIM, "small")
        clicked = entity_list(ui, "areas", named(ui, db.areas.values()), self.area_id, TOP + 20, 18)
        if clicked is not None:
            self.area_id = clicked
        new, delete = list_buttons(ui, self.area_id not in (None, AREA_SINGLE))
        if new:
            self.area_id = db.create("areas", "New Area", new_area_data())
            app.data_changed()
        elif delete:
            db.delete("areas", self.area_id)  # навыки с этой областью станут бить по одной цели
            app.data_changed()

    def _draw_form(self, ui: UI, app: EditorHost, area_id: str) -> None:
        t, db, x = ui.t, app.db, FORM_X
        data = db.areas[area_id].to_dict()
        cells = {tuple(cell) for cell in data["cells"]}
        new_cells = set(cells)
        key = ("area", area_id)
        span = range(-MAX_SPAN, MAX_SPAN + 1)

        ui.text(t("Name"), x, TOP + 4, font="small")
        name = ui.text_input((key, "name"), pygame.Rect(x + 76, TOP, 220, 24), data["name"])
        ui.text(f"id: {area_id}", x + 310, TOP + 5, DIM, "small")

        # Быстрое заполнение
        fills = (("Clear", set()), ("Target only", {(0, 0)}), ("Whole row", {(0, c) for c in span}),
                 ("Whole column", {(r, 0) for r in span}), ("Everything", {(r, c) for r in span for c in span}))
        for i, (label, preset) in enumerate(fills):
            if ui.button(t(label), pygame.Rect(x + i * 136, TOP + 32, 130, 22)):
                new_cells = set(preset)

        gx, gy, size = x + 60, self.GRID_Y, self.CELL
        ui.text(t("towards the enemy"), gx, gy - 20, DIM, "small")
        ui.text(t("away from the enemy"), gx, gy + len(span) * size + 4, DIM, "small")
        for r, row in enumerate(span):
            ui.text(f"{row:+d}" if row else "0", x + 22, gy + r * size + 6, DIM, "small")
            for c, col in enumerate(span):
                rect = pygame.Rect(gx + c * size, gy + r * size, size - 2, size - 2)
                marked = (row, col) in cells
                pygame.draw.rect(ui.screen, (190, 90, 70) if marked else SLOT, rect)
                if (row, col) == (0, 0):
                    pygame.draw.rect(ui.screen, YELLOW, rect, 2)   # опорная клетка
                if ui.clicked(rect):
                    new_cells.symmetric_difference_update({(row, col)})

        ix = gx + len(span) * size + 30
        lines = [
            t("Click a cell to mark it."),
            t("The yellow cell is the anchor: the target of a skill,"),
            t("or the unit itself for covers and effect triggers."),
            t("Up is closer to the enemy; left and right are columns."),
            t("Marks beyond the field edge are ignored,"),
            t("so one area works on any field up to 5x5."),
            t("Cells marked: {n}", n=len(cells)),
        ]
        users = [t(s.name) for s in db.skills.values() if s.area == area_id]
        lines.append(t("Used by skills: {names}", names=", ".join(users) or "-"))
        for i, line in enumerate(lines):
            ui.text(line, ix, gy + i * 18, TEXT if i >= 6 else DIM, "small", WIDTH - ix - 12)

        if name or new_cells != cells:
            apply(app, "areas", area_id, {"name": name or data["name"], "cells": [list(c) for c in sorted(new_cells)]})
