"""Экраны редакторов справочника: классы юнитов.

Каждая правка сразу записывается в app.db через Database.update (он же её проверяет);
на диск справочник сохраняется при переходе на вкладку боя.
"""
from __future__ import annotations

import copy
from typing import Optional

import pygame

from game.editing import new_unit_data, stat_default
from game.stats import Stat
from game.tags import TAG_UNIT
from pygame_editors import EMPTY, FORM_X, TOP, EditorHost, apply, entity_list, named, plain, rule_table, tag_options
from pygame_ui import DIM, HEIGHT, RED, UI

CLASS_RULES = 6     # сколько правил тактики по умолчанию помещается в редакторе класса
MAX_SLOTS = 6


def list_buttons(ui: UI, can_delete: bool) -> tuple[bool, bool]:
    """Кнопки под списком объектов: (нажато «новый», нажато «удалить»)."""
    new = bool(ui.button(ui.t("+ New"), pygame.Rect(16, HEIGHT - 84, 92, 24)))
    delete = bool(ui.button(ui.t("Delete"), pygame.Rect(112, HEIGHT - 84, 94, 24), enabled=can_delete, color=RED))
    return new, delete


class ClassEditor:
    """Класс юнита: статы и рост, AP/PP, теги, слоты, навыки, пассивки, тактики по умолчанию."""

    def __init__(self) -> None:
        self.unit_id: Optional[str] = None

    def draw(self, ui: UI, app: EditorHost) -> None:
        db = app.db
        if self.unit_id not in db.units:
            self.unit_id = next(iter(db.units), None)
        if self.unit_id is not None:
            self._draw_form(ui, app, self.unit_id)
        ui.text(ui.t("Classes"), 16, TOP, DIM, "small")
        clicked = entity_list(ui, "classes", named(ui, db.units.values()), self.unit_id, TOP + 20, 18)
        if clicked is not None:
            self.unit_id = clicked
        new, delete = list_buttons(ui, self.unit_id is not None)
        if new:
            self.unit_id = db.create("units", "New Class", new_unit_data(db))
            app.data_changed()
        elif delete:
            db.delete("units", self.unit_id)  # юниты этого класса исчезнут из отрядов
            app.data_changed()

    def _draw_form(self, ui: UI, app: EditorHost, unit_id: str) -> None:
        t, db, x = ui.t, app.db, FORM_X
        definition = db.units[unit_id]
        data = definition.to_dict()
        new = copy.deepcopy(data)
        key = ("class", unit_id)

        # Название и ресурсы
        ui.text(t("Name"), x, TOP + 4, font="small")
        name = ui.text_input((key, "name"), pygame.Rect(x + 76, TOP, 200, 24), data["name"])
        if name:
            new["name"] = name
        ui.text(f"id: {unit_id}", x + 290, TOP + 5, DIM, "small")
        for field, label, fx in (("ap_max", "AP max", 480), ("pp_max", "PP max", 610)):
            ui.text(t(label), x + fx, TOP + 4, font="small")
            value = ui.number_input((key, field), pygame.Rect(x + fx + 64, TOP, 44, 24), data[field], 0, 9)
            if value is not None:
                new[field] = value

        # Статы: база и прирост за уровень
        y = TOP + 34
        for label, offset in (("stat", 0), ("base", 116), ("per level", 178)):
            ui.text(t(label), x + offset, y, DIM, "small")
        for row, stat in enumerate(Stat):
            ry = y + 18 + row * 24
            ui.text(t(stat.value), x, ry + 3, font="small", width=112)
            base = data["stats"].get(stat.value, stat_default(stat))
            value = ui.number_input((key, "base", stat.value), pygame.Rect(x + 116, ry, 56, 22), base, 0, 9999)
            if value is not None:
                new["stats"][stat.value] = value
            growth = data["growth"].get(stat.value, 0)
            value = ui.number_input((key, "growth", stat.value), pygame.Rect(x + 178, ry, 56, 22), growth, 0, 999,
                                    integer=False)
            if value is not None:
                new["growth"][stat.value] = value
                if value == 0:
                    del new["growth"][stat.value]

        # Теги, навыки, пассивки
        rx = x + 262
        lists = (
            ("tags", "Tags", tag_options(ui, db, TAG_UNIT)),
            ("skills", "Skills", named(ui, db.skills.values())),
            ("passives", "Passives", named(ui, db.passives.values())),
        )
        for row, (field, label, choices) in enumerate(lists):
            ry = y + row * 30
            ui.text(t(label), rx, ry + 4, font="small")
            picked = ui.multiselect((key, field), pygame.Rect(rx + 80, ry, 420, 24), choices, data[field])
            if picked is not None:
                new[field] = picked

        # Слоты снаряжения: тип каждого слота выбирается из фиксированного списка
        sy = y + 96
        slots = data["slots"]
        ui.text(t("Equipment slots: {n}", n=len(slots)), rx, sy + 4, font="small")
        slot_choices = plain(ui, db.slot_types)
        picked = ui.dropdown((key, "add-slot"), pygame.Rect(rx + 200, sy, 160, 24),
                             [(EMPTY, t("+ add slot...")), *slot_choices], EMPTY)
        if picked and len(slots) < MAX_SLOTS:
            new["slots"] = slots + [picked]
        for i, slot in enumerate(slots[:MAX_SLOTS]):
            rect = pygame.Rect(rx + (i % 3) * 168, sy + 30 + (i // 3) * 28, 160, 24)
            picked = ui.dropdown((key, "slot", i), rect, [(EMPTY, t("(remove slot)")), *slot_choices], slot)
            if picked is not None and picked != slot:
                new["slots"] = slots[:i] + ([picked] if picked else []) + slots[i + 1:]

        # Тактики по умолчанию: их получают новые юниты класса
        ty = y + 18 + len(Stat) * 24 + 8
        ui.text(t("Default tactics (given to new units of the class)"), x, ty, font="small")
        rules = data["tactics"]
        skill_ids = [s for s in data["skills"] if s in db.skills]
        new_rules = rule_table(ui, db, (key, "tactics"), rules, skill_ids, x, ty + 20, CLASS_RULES)
        if new_rules is not None:
            new["tactics"] = new_rules

        if new != data:
            # Навык убрали у класса: правила по умолчанию с ним тоже убираются.
            new["tactics"] = [r for r in new["tactics"] if r["skill"] in new["skills"]]
            apply(app, "units", unit_id, new)
