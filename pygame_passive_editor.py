"""Экран редактора пассивок: эффект на событие и прикрытие союзников."""
from __future__ import annotations

import copy
from typing import Optional

import pygame

from game import events
from game.areas import AREA_SINGLE, AREAS
from game.definitions import CATEGORIES, PASSIVE_ACTIONS, PASSIVE_COVER, PASSIVE_EFFECT, SCOPES
from game.editing import new_passive_data, set_owners, skill_owners
from pygame_data_editors import list_buttons
from pygame_editors import EMPTY, FORM_X, TOP, EditorHost, apply, entity_list, named, plain
from pygame_ui import DIM, UI, WIDTH

LABEL_W = 170
# События, на которые может реагировать пассивка с эффектом.
TRIGGERS = [cls.__name__ for cls in events.Event.__subclasses__()]


class PassiveEditor:
    """Пассивка: что делает, сколько стоит PP, условия срабатывания и кому принадлежит."""

    def __init__(self) -> None:
        self.passive_id: Optional[str] = None

    def draw(self, ui: UI, app: EditorHost) -> None:
        db = app.db
        if self.passive_id not in db.passives:
            self.passive_id = next(iter(db.passives), None)
        if self.passive_id is not None:
            self._draw_form(ui, app, self.passive_id)
        ui.text(ui.t("Passives"), 16, TOP, DIM, "small")
        clicked = entity_list(ui, "passives", named(ui, db.passives.values()), self.passive_id, TOP + 20, 18)
        if clicked is not None:
            self.passive_id = clicked
        new, delete = list_buttons(ui, self.passive_id is not None)
        if new:
            self.passive_id = db.create("passives", "New Passive", new_passive_data(db))
            app.data_changed()
        elif delete:
            db.delete("passives", self.passive_id)
            app.data_changed()

    def _draw_form(self, ui: UI, app: EditorHost, passive_id: str) -> None:
        t, db, x = ui.t, app.db, FORM_X
        data = db.passives[passive_id].to_dict()
        new = copy.deepcopy(data)
        key = ("passive", passive_id)
        fx = x + LABEL_W
        is_cover = data["action"] == PASSIVE_COVER

        def row(n: int) -> int:
            return TOP + n * 30

        ui.text(t("Name"), x, row(0) + 4, font="small")
        name = ui.text_input((key, "name"), pygame.Rect(fx, row(0), 220, 24), data["name"])
        if name:
            new["name"] = name
        ui.text(f"id: {passive_id}", fx + 234, row(0) + 5, DIM, "small")

        ui.text(t("What it does"), x, row(1) + 4, font="small")
        action_choices = [(PASSIVE_EFFECT, t("applies an effect on an event")),
                          (PASSIVE_COVER, t("covers allies: takes the hit instead"))]
        picked = ui.dropdown((key, "action"), pygame.Rect(fx, row(1), 320, 24), action_choices, data["action"])
        if picked is not None and picked != data["action"]:
            new["action"] = picked
            if picked == PASSIVE_EFFECT and not data["effect_id"]:
                new["effect_id"] = next(iter(db.effects), None)
        ui.text(t("PP cost"), fx + 340, row(1) + 4, font="small")
        value = ui.number_input((key, "pp_cost"), pygame.Rect(fx + 410, row(1), 44, 24), data["pp_cost"], 0, 9)
        if value is not None:
            new["pp_cost"] = value

        ui.text(t("Effect on the owner"), x, row(2) + 4, font="small")
        effect_choices = named(ui, db.effects.values())
        if is_cover:
            effect_choices = [(EMPTY, "-"), *effect_choices]  # у прикрытия эффект необязателен
        picked = ui.dropdown((key, "effect"), pygame.Rect(fx, row(2), 320, 24), effect_choices, data["effect_id"] or EMPTY)
        if picked is not None:
            new["effect_id"] = picked or None

        if is_cover:
            self._draw_cover(ui, db, key, data, new, x, fx, row)
            owners_row = 7
        else:
            ui.text(t("On event"), x, row(3) + 4, font="small")
            picked = ui.dropdown((key, "trigger"), pygame.Rect(fx, row(3), 220, 24), plain(ui, TRIGGERS), data["trigger"])
            if picked is not None:
                new["trigger"] = picked
            ui.text(t("Whose event"), fx + 240, row(3) + 4, font="small")
            picked = ui.dropdown((key, "scope"), pygame.Rect(fx + 340, row(3), 114, 24), plain(ui, SCOPES), data["scope"])
            if picked is not None:
                new["scope"] = picked
            ui.text(t("The effect is applied to the owner when the event happens and the owner has enough PP."),
                    x, row(4) + 4, DIM, "small")
            owners_row = 5

        # Кому принадлежит пассивка
        for n, (section, label) in enumerate((("units", "Classes"), ("items", "Items"))):
            ry = row(owners_row + n)
            ui.text(t(label), x, ry + 4, font="small")
            owners = skill_owners(db, section, passive_id, "passives")
            picked = ui.multiselect((key, section), pygame.Rect(fx, ry, 460, 24),
                                    named(ui, getattr(db, section).values()), owners)
            if picked is not None:
                try:
                    set_owners(db, section, passive_id, picked, field="passives")
                    app.data_changed()
                except ValueError as error:
                    app.message = str(error)

        if new != data:
            apply(app, "passives", passive_id, new)

    @staticmethod
    def _draw_cover(ui: UI, db, key, data: dict, new: dict, x: int, fx: int, row) -> None:
        """Настройки прикрытия: зона, сколько союзников, от каких атак и областей навыка."""
        t = ui.t
        ui.text(t("Covers allies in"), x, row(3) + 4, font="small")
        zone_choices = [("row", t("the owner's row")), ("column", t("the owner's column")), ("all", t("the whole squad"))]
        picked = ui.dropdown((key, "cover_area"), pygame.Rect(fx, row(3), 220, 24), zone_choices, data["cover_area"])
        if picked is not None:
            new["cover_area"] = picked
        many_choices = [(False, t("one ally")), (True, t("every ally hit in the zone"))]
        picked = ui.dropdown((key, "cover_many"), pygame.Rect(fx + 230, row(3), 230, 24), many_choices, data["cover_many"])
        if picked is not None:
            new["cover_many"] = picked

        ui.text(t("Against attacks tagged"), x, row(4) + 4, font="small")
        tag_choices = [*plain(ui, CATEGORIES), *named(ui, (tag for tag in db.tags.values() if tag.kind != "unit"))]
        picked = ui.multiselect((key, "cover_tags"), pygame.Rect(fx, row(4), 460, 24), tag_choices, data["cover_tags"])
        if picked is not None:
            new["cover_tags"] = picked
        ui.text(t("- means any attack"), fx + 470, row(4) + 5, DIM, "small")

        ui.text(t("Against skills aimed at"), x, row(5) + 4, font="small")
        picked = ui.multiselect((key, "cover_skill_areas"), pygame.Rect(fx, row(5), 460, 24),
                                plain(ui, AREAS), data["cover_skill_areas"])
        if picked is not None:
            new["cover_skill_areas"] = picked
        ui.text(t("- means any area"), fx + 470, row(5) + 5, DIM, "small")
        ui.text(t("The hit is redirected to the owner, who cannot evade it. The first able protector"),
                x, row(6) + 2, DIM, "small", WIDTH - x - 16)
        ui.text(t("in formation order covers; PP is spent once per enemy skill."), x, row(6) + 16, DIM, "small")


__all__ = ["PassiveEditor", "AREA_SINGLE", "PASSIVE_ACTIONS"]
