"""Экран редактора пассивок: цена PP, реакция на событие и владельцы."""
from __future__ import annotations

from typing import Optional

import pygame

from game.editing import new_passive_data, set_owners, skill_owners
from pygame_data_editors import list_buttons
from pygame_editors import FORM_X, TOP, EditorHost, apply, entity_list, named
from pygame_reaction import FORM_ROWS, LABEL_W, ROW, reaction_form
from pygame_ui import DIM, UI


class PassiveEditor:
    """Пассивка это реакция владельца на событие боя, которая стоит PP."""

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
        new = dict(data)
        key = ("passive", passive_id)
        fx = x + LABEL_W

        ui.text(t("Name"), x, TOP + 4, font="small")
        name = ui.text_input((key, "name"), pygame.Rect(fx, TOP, 220, 24), data["name"])
        if name:
            new["name"] = name
        ui.text(t("PP cost"), fx + 236, TOP + 4, font="small")
        value = ui.number_input((key, "pp_cost"), pygame.Rect(fx + 300, TOP, 44, 24), data["pp_cost"], 0, 9)
        if value is not None:
            new["pp_cost"] = value
        ui.text(f"id: {passive_id}", fx + 360, TOP + 5, DIM, "small")

        reaction = reaction_form(ui, db, (key, "reaction"), data["reaction"], x, TOP + 36, for_effect=False)
        if reaction is not None:
            new["reaction"] = reaction

        y = TOP + 36 + FORM_ROWS * ROW + 10
        ui.text(t("Reactions of the same moment go by initiative; in the 'targeted' phase only one per side."),
                x, y, DIM, "small")
        ui.text(t("A skill used as a reaction costs only this PP and does not trigger attack reactions."),
                x, y + 16, DIM, "small")
        for n, (section, label) in enumerate((("units", "Classes"), ("items", "Items"))):
            ry = y + 44 + n * 30
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
