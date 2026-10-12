"""Общая форма реакции «когда -> если -> что -> кому» для редакторов пассивок и эффектов."""
from __future__ import annotations

from typing import Any, Hashable, Optional

import pygame

from game.database import Database
from game.definitions import CATEGORIES
from game.editing import FRACTIONS, describe_reaction, reaction_defaults
from game.reactions import (
    AMOUNT_ACTIONS,
    ATTACK_EVENTS,
    DO_COVER,
    DO_USE_SKILL,
    EFFECT_ACTIONS,
    EFFECT_EVENTS,
    EVENTS,
    EVENTS_WITHOUT_SUBJECT,
    GROUPS,
    LIMITS,
    ON_ATTACKED,
    ON_HP_BELOW,
    ON_TARGETED,
    OUTCOMES,
    ROLES,
    TARGETS,
    THIS_EFFECT,
    WHOSE,
    Reaction,
)
from pygame_editors import EMPTY, condition_widgets, named, plain
from pygame_ui import DIM, TEXT, UI, WIDTH

LABEL_W = 110
ROW = 30
FORM_ROWS = 7   # сколько строк занимает форма


def reaction_form(ui: UI, db: Database, key: Hashable, data: dict[str, Any], x: int, y: int,
                  for_effect: bool) -> Optional[dict[str, Any]]:
    """Рисует форму реакции. Возвращает изменённую реакцию (формат JSON) или None.

    for_effect: форма в редакторе эффекта (есть фильтр «этот эффект» и роль «наложивший»).
    """
    t = ui.t
    new = dict(data)
    fx = x + LABEL_W
    width = WIDTH - fx - 16

    def change(field: str, value: Any) -> None:
        nonlocal new
        new = reaction_defaults(db, new, field, value)

    def label(text: str, row: int) -> int:
        ry = y + row * ROW
        ui.text(t(text), x, ry + 4, font="small")
        return ry

    # 1. Когда
    ry = label("When", 0)
    picked = ui.dropdown((key, "event"), pygame.Rect(fx, ry, 190, 24), plain(ui, EVENTS), data["event"])
    if picked is not None:
        change("event", picked)
    has_subject = data["event"] not in EVENTS_WITHOUT_SUBJECT
    if has_subject:
        ui.text(t("whose"), fx + 200, ry + 4, DIM, "small")
        picked = ui.dropdown((key, "whose"), pygame.Rect(fx + 250, ry, 100, 24), plain(ui, WHOSE), data["whose"])
        if picked is not None:
            change("whose", picked)
    ui.text(t("how often"), fx + 362, ry + 4, DIM, "small")
    limits = [(value, t("no limit") if value == "none" else t(value)) for value in LIMITS]
    picked = ui.dropdown((key, "limit"), pygame.Rect(fx + 446, ry, 140, 24), limits, data["limit"])
    if picked is not None:
        change("limit", picked)

    # 2. Условия на владельца и на того, с кем случилось событие
    ry = label("If owner", 1)
    condition = condition_widgets(ui, db, (key, "self"), data["self_condition"], fx, ry, 120, 110)
    if condition is not None:
        change("self_condition", condition)
    if has_subject:
        ui.text(t("if subject"), fx + 246, ry + 4, DIM, "small")
        condition = condition_widgets(ui, db, (key, "subject"), data["subject_condition"], fx + 330, ry, 120, 110)
        if condition is not None:
            change("subject_condition", condition)

    # 3. Фильтры, зависящие от события
    ry = label("Filters", 2)
    fx2 = fx
    if has_subject:
        ui.text(t("in area"), fx2, ry + 4, DIM, "small")
        areas = [(EMPTY, t("anywhere")), *named(ui, db.areas.values())]
        picked = ui.dropdown((key, "area"), pygame.Rect(fx2 + 60, ry, 110, 24), areas, data["area"] or EMPTY)
        if picked is not None:
            change("area", picked or None)
        fx2 += 180
    event = data["event"]
    if event in ATTACK_EVENTS:
        tags = [*plain(ui, CATEGORIES), *named(ui, (tag for tag in db.tags.values() if tag.kind != "unit"))]
        ui.text(t("tags"), fx2, ry + 4, DIM, "small")
        picked = ui.multiselect((key, "attack_tags"), pygame.Rect(fx2 + 40, ry, 120, 24), tags, data["attack_tags"])
        if picked is not None:
            change("attack_tags", picked)
        ui.text(t("skill area"), fx2 + 168, ry + 4, DIM, "small")
        picked = ui.multiselect((key, "skill_areas"), pygame.Rect(fx2 + 250, ry, 100, 24),
                                named(ui, db.areas.values()), data["skill_areas"])
        if picked is not None:
            change("skill_areas", picked)
        if event == ON_ATTACKED:
            picked = ui.dropdown((key, "outcome"), pygame.Rect(fx2 + 356, ry, 90, 24), plain(ui, OUTCOMES), data["outcome"])
            if picked is not None:
                change("outcome", picked)
    elif event in EFFECT_EVENTS:
        choices = [(EMPTY, t("any effect"))]
        if for_effect:
            choices.append((THIS_EFFECT, t("this effect")))
        choices += named(ui, db.effects.values())
        ui.text(t("effect"), fx2, ry + 4, DIM, "small")
        picked = ui.dropdown((key, "effect_filter"), pygame.Rect(fx2 + 56, ry, 180, 24), choices,
                             data["effect_filter"] or EMPTY)
        if picked is not None:
            change("effect_filter", picked or None)
    elif event == ON_HP_BELOW:
        ui.text(t("below"), fx2, ry + 4, DIM, "small")
        choices = [(value, f"{round(value * 100)}%") for value in FRACTIONS]
        picked = ui.dropdown((key, "threshold"), pygame.Rect(fx2 + 56, ry, 80, 24), choices, data["threshold"])
        if picked is not None:
            change("threshold", picked)

    # 4. Что сделать
    ry = label("Do", 3)
    actions = [a for a in plain(ui, ("use_skill", "apply_effect", "remove_effect", "damage", "heal",
                                       "restore_ap", "restore_pp"))]
    if event == ON_TARGETED:
        actions.append((DO_COVER, t(DO_COVER)))
    picked = ui.dropdown((key, "action"), pygame.Rect(fx, ry, 170, 24), actions, data["action"])
    if picked is not None:
        change("action", picked)
    action = data["action"]
    if action == DO_USE_SKILL:
        skills = [(s.id, f"{t(s.name)}") for s in db.skills.values()]
        picked = ui.dropdown((key, "skill"), pygame.Rect(fx + 180, ry, 220, 24), skills, data["skill_id"])
        if picked is not None:
            change("skill_id", picked)
    elif action in EFFECT_ACTIONS or action == DO_COVER:
        effects = named(ui, db.effects.values())
        if action == DO_COVER:
            effects = [(EMPTY, t("no effect")), *effects]   # у прикрытия эффект на защитника необязателен
        picked = ui.dropdown((key, "effect_id"), pygame.Rect(fx + 180, ry, 220, 24), effects, data["effect_id"] or EMPTY)
        if picked is not None:
            change("effect_id", picked or None)
        if action == DO_COVER:
            many = [(False, t("one ally")), (True, t("every ally hit"))]
            picked = ui.dropdown((key, "cover_many"), pygame.Rect(fx + 410, ry, 170, 24), many, data["cover_many"])
            if picked is not None:
                change("cover_many", picked)
    elif action in AMOUNT_ACTIONS:
        value = ui.number_input((key, "amount"), pygame.Rect(fx + 180, ry, 56, 24), data["amount"], 0, 999)
        if value is not None:
            change("amount", value)
        if for_effect and action in ("damage", "heal"):
            ui.text(t("x stacks"), fx + 244, ry + 4, DIM, "small")

    # 5. Кому
    ry = label("To whom", 4)
    if action == DO_COVER:
        ui.text(t("the hit goes to the owner, who cannot evade it"), fx, ry + 4, DIM, "small")
    else:
        roles = ROLES if action == DO_USE_SKILL else TARGETS
        roles = [r for r in roles if for_effect or r != "source"]
        picked = ui.dropdown((key, "to"), pygame.Rect(fx, ry, 170, 24), plain(ui, roles), data["to"])
        if picked is not None:
            change("to", picked)
        if data["to"] in GROUPS:
            areas = [(EMPTY, t("whole side")), *named(ui, db.areas.values())]
            picked = ui.dropdown((key, "to_area"), pygame.Rect(fx + 180, ry, 150, 24), areas, data["to_area"] or EMPTY)
            if picked is not None:
                change("to_area", picked or None)

    # 6. Итог одной строкой
    try:
        summary, color = describe_reaction(Reaction.from_dict(new), db, t), TEXT
    except (ValueError, KeyError) as error:
        summary, color = str(error), DIM
    ui.text(summary, x, y + 5 * ROW + 6, color, "small", width + LABEL_W)
    ui.text(t("owner = who has it; subject = to whom it happened; actor = who caused it; target = the skill's target"),
            x, y + 6 * ROW, DIM, "small", width + LABEL_W)
    return new if new != data else None
