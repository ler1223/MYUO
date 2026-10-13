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
from game.unit import learned_to_list
from pygame_editors import EMPTY, FORM_X, TOP, EditorHost, apply, entity_list, named, plain, rule_table, tag_options
from pygame_ui import DIM, HEIGHT, RED, TEXT, UI

CLASS_RULES = 6     # сколько правил тактики по умолчанию помещается в редакторе класса
MAX_SLOTS = 6
UNLOCK_CELLS = 9    # сколько уровней открытия помещается под слотами (три ряда по три)


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

        # Теги, навыки, пассивки. Навыки и пассивки хранят уровень открытия: {"id", "level"}.
        rx = x + 262
        levels = {field: {i: definition_levels.get(i, 1) for i in ids}
                  for field, ids, definition_levels in (("skills", definition.skills, definition.skill_levels),
                                                        ("passives", definition.passives, definition.passive_levels))}
        lists = (
            ("tags", "Tags", tag_options(ui, db, TAG_UNIT)),
            ("skills", "Skills", named(ui, db.skills.values())),
            ("passives", "Passives", named(ui, db.passives.values())),
        )
        for row, (field, label, choices) in enumerate(lists):
            ry = y + row * 30
            ui.text(t(label), rx, ry + 4, font="small")
            current = list(levels[field]) if field in levels else data[field]
            picked = ui.multiselect((key, field), pygame.Rect(rx + 80, ry, 420, 24), choices, current)
            if picked is not None:
                new[field] = picked if field not in levels else learned(picked, levels[field])

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

        # С какого уровня класса открывается навык или пассивка
        uy = sy + 30 + 2 * 28 + 6
        ui.text(t("Unlocks at level"), rx, uy, DIM, "small")
        entries = [("skills", i, db.skills) for i in levels["skills"]] + [("passives", i, db.passives)
                                                                          for i in levels["passives"]]
        for n, (field, entry_id, section) in enumerate(entries[:UNLOCK_CELLS]):
            ex, ey = rx + (n % 3) * 168, uy + 18 + (n // 3) * 26
            name = t(section[entry_id].name) if entry_id in section else entry_id
            ui.text(name, ex, ey + 3, DIM if field == "passives" else TEXT, "small", 112)
            value = ui.number_input((key, "unlock", field, entry_id), pygame.Rect(ex + 116, ey, 44, 22),
                                    levels[field][entry_id], 1, 99)
            if value is not None:
                new[field] = learned(list(levels[field]), dict(levels[field], **{entry_id: value}))

        # Тактики по умолчанию: их получают новые юниты класса
        ty = y + 18 + len(Stat) * 24 + 8
        ui.text(t("Default tactics (given to new units of the class)"), x, ty, font="small")
        rules = data["tactics"]
        skill_ids = [s for s in definition.skills if s in db.skills]
        new_rules = rule_table(ui, db, (key, "tactics"), rules, skill_ids, x, ty + 20, CLASS_RULES)
        if new_rules is not None:
            new["tactics"] = new_rules

        if new != data:
            # Навык убрали у класса: правила по умолчанию с ним тоже убираются.
            skills = {s if isinstance(s, str) else s["id"] for s in new["skills"]}
            new["tactics"] = [r for r in new["tactics"] if r["skill"] in skills]
            apply(app, "units", unit_id, new)


def learned(ids: list[str], levels: dict[str, int]) -> list:
    """Список навыков класса в формате данных: уровень пишется, только если он выше первого."""
    return learned_to_list(ids, {i: levels.get(i, 1) for i in ids})
