"""Экраны редакторов для demo_pygame: отряды, тактики, конструктор навыков.

Экраны только вызывают операции ядра (game.world, game.editing) над
редактируемой расстановкой app.setup; бой идёт на её копии.
Все строки интерфейса проходят через ui.t (перевод, ключ = английский текст).
"""
from __future__ import annotations

from typing import Any, Optional, Protocol

import pygame

from game.areas import AREAS
from game.database import Database
from game.definitions import APPLY_RECIPIENTS, SKILL_KINDS, SKILL_SUPPORT
from game.editing import (
    AP_COST_MAX,
    POWER_MAX,
    POWER_STEP,
    RESTORE_MAX,
    SkillDraft,
    condition_params,
    cycle,
    default_apply,
    default_condition,
    default_rule,
    describe_skill,
    param_options,
    set_tactics,
    skill_users,
)
from game.scenario import Scenario
from game.squad import Formation
from game.stats import Stat
from game.i18n import Translator
from game.tactics import CONDITIONS, SELECTORS, SIDES, TacticsSet
from game.unit import Unit
from pygame_ui import DIM, GREEN, HEIGHT, PANEL, RED, SLOT, TEXT, UI, WIDTH, YELLOW

TOP = 44            # под панелью вкладок
ROW_H = 28
MAX_RULES = 12
NAME_MAX = 24
ENEMY_TEXT = (240, 170, 170)
HINT_CYCLE = "Left click: next value, right click: previous."


class EditorHost(Protocol):
    """Что экранам нужно от приложения."""

    db: Database
    setup: Scenario
    message: str
    t: Translator

    def changed(self) -> None: ...
    def units(self) -> list[Unit]: ...
    def label(self, unit: Unit) -> str: ...
    def next_uid(self) -> int: ...
    def reset_setup(self) -> None: ...


def condition_buttons(ui: UI, db: Database, condition: dict[str, Any], x: int, y: int,
                      type_w: int, param_w: int) -> Optional[dict[str, Any]]:
    """Кнопка типа условия и кнопки его параметров. Возвращает новое условие, если его изменили."""
    t = ui.t
    result = None
    delta = ui.button(t(condition["type"]), pygame.Rect(x, y, type_w, 24))
    if delta:
        result = default_condition(cycle(list(CONDITIONS), condition["type"], delta), db)
    params = condition_params(condition["type"])
    for i, (param, kind) in enumerate(params.items()):
        width = (param_w - 4 * (len(params) - 1)) // len(params)
        rect = pygame.Rect(x + type_w + 4 + i * (width + 4), y, width, 24)
        value = condition[param]
        delta = ui.button(t(value) if isinstance(value, str) else str(value), rect)
        if delta:
            result = dict(condition, **{param: cycle(param_options(kind, db), value, delta)})
    return result


def stepper(ui: UI, label: str, value: int, low: int, high: int, x: int, y: int, label_w: int) -> int:
    """Подпись, кнопки -/+ и число между ними. Возвращает новое значение."""
    ui.text(label, x, y + 4)
    x += label_w
    if ui.button("-", pygame.Rect(x, y, 22, 24)):
        value = max(low, value - 1)
    ui.text(str(value), x + 30, y + 4)
    if ui.button("+", pygame.Rect(x + 46, y, 22, 24)):
        value = min(high, value + 1)
    return value


# --- отряды ----------------------------------------------------------------

class SquadEditor:
    CELL_W, CELL_H = 150, 84
    GRID_X, GRID_Y = 16, 104
    SIDE_X = 500

    def __init__(self) -> None:
        self.army_key = "player"
        self.selected: Optional[tuple[str, Any]] = None  # ("cell", (row, col)) | ("reserve", uid)

    def draw(self, ui: UI, app: EditorHost) -> None:
        t = ui.t
        scenario = app.setup
        armies = {"player": (scenario.player, scenario.player_squad), "enemy": (scenario.enemy, scenario.enemy_squad)}
        for i, (key, (army, squad)) in enumerate(armies.items()):
            text = f"{t(army.name)}: {t(squad.name)}"
            if ui.button(text, pygame.Rect(16 + i * 208, TOP, 200, 24), key == self.army_key):
                self.army_key, self.selected = key, None
        if ui.button(t("Reset to demo"), pygame.Rect(WIDTH - 176, TOP, 160, 24)):
            app.reset_setup()
            self.selected = None
            return
        army, squad = armies[self.army_key]
        formation = squad.formation

        ui.text(t("Formation {n}/{max}  (top row = front, * = leader)", n=len(formation), max=Formation.MAX_UNITS),
                16, TOP + 34)
        for row in range(Formation.ROWS):
            for col in range(Formation.COLS):
                rect = pygame.Rect(self.GRID_X + col * self.CELL_W, self.GRID_Y + row * self.CELL_H,
                                   self.CELL_W - 8, self.CELL_H - 8)
                if ui.button("", rect, self.selected == ("cell", (row, col))):
                    self._click_cell(app, army, squad, (row, col))
                unit = formation.unit_at(row, col)
                if unit is not None:
                    leader = " *" if squad.leader_uid == unit.uid else ""
                    ui.text(f"{app.label(unit)}{leader}", rect.x + 6, rect.y + 5, width=rect.width - 12)
                    ui.text(f"L{unit.state.level}  HP {unit.max_hp}  SPD {unit.stat(Stat.SPD)}",
                            rect.x + 6, rect.y + 28, DIM, "small", rect.width - 12)
                    ui.text(f"ATK {unit.stat(Stat.ATK)}  DEF {unit.stat(Stat.DEF)}",
                            rect.x + 6, rect.y + 46, DIM, "small", rect.width - 12)

        self._draw_reserve(ui, app, army)
        self._draw_selection(ui, app, army, squad)
        ui.text(t("Click a unit, then a cell to move or swap. Click a reserve unit, then a cell to place it."),
                16, HEIGHT - 52, DIM, "small")

    def _selected_unit(self, army, squad) -> Optional[Unit]:
        if self.selected is None:
            return None
        kind, value = self.selected
        return squad.formation.unit_at(*value) if kind == "cell" else army.units.get(value)

    def _click_cell(self, app: EditorHost, army, squad, pos: tuple[int, int]) -> None:
        formation = squad.formation
        occupant = formation.unit_at(*pos)
        try:
            if self.selected is None:
                if occupant is not None:
                    self.selected = ("cell", pos)
                return
            kind, value = self.selected
            self.selected = None
            if kind == "cell":
                if value != pos:
                    formation.swap(value, pos)
                    app.changed()
            else:
                if occupant is not None:
                    army.unassign(occupant.uid)
                army.assign(value, squad.id, *pos)
                app.changed()
        except ValueError as error:
            app.message = str(error)

    def _draw_reserve(self, ui: UI, app: EditorHost, army) -> None:
        t, x = ui.t, self.SIDE_X
        ui.text(t("Reserve (not in the squad)"), x, TOP + 34)
        reserve = army.reserve()
        if not reserve:
            ui.text(t("empty"), x, self.GRID_Y + 2, DIM, "small")
        for i, unit in enumerate(reserve[:15]):
            rect = pygame.Rect(x + (i % 3) * 160, self.GRID_Y + (i // 3) * 28, 152, 24)
            if ui.button(f"{app.label(unit)} L{unit.state.level}", rect, self.selected == ("reserve", unit.uid)):
                self.selected = ("reserve", unit.uid)
        y = self.GRID_Y + 5 * 28 + 10
        ui.text(t("Recruit a level 1 unit into the reserve"), x, y)
        for i, definition in enumerate(app.db.units.values()):
            rect = pygame.Rect(x + (i % 3) * 160, y + 24 + (i // 3) * 28, 152, 24)
            if ui.button(f"+ {t(definition.name)}", rect):
                unit = army.recruit(app.db.create_unit(definition.id, app.next_uid()))
                self.selected = ("reserve", unit.uid)
                app.changed()

    def _draw_selection(self, ui: UI, app: EditorHost, army, squad) -> None:
        t = ui.t
        y = self.GRID_Y + Formation.ROWS * self.CELL_H + 8
        unit = self._selected_unit(army, squad)
        if unit is None:
            ui.text(t("Nothing selected"), 16, y, DIM)
            return
        in_squad = self.selected[0] == "cell"
        names = lambda ids: ", ".join(t(app.db.skills[i].name if i in app.db.skills else i) for i in ids) or "-"
        ui.text(f"{app.label(unit)}  L{unit.state.level}  HP {unit.max_hp}  ATK {unit.stat(Stat.ATK)}  "
                f"DEF {unit.stat(Stat.DEF)}  SPD {unit.stat(Stat.SPD)}  AP {unit.ap.max}  PP {unit.pp.max}", 16, y)
        ui.text(f"{t('skills')}: {names(app.db.skills_for(unit))}   "
                f"{t('passives')}: {', '.join(t(p) for p in unit.passive_ids) or '-'}",
                16, y + 22, DIM, "small", WIDTH - 32)
        # Слоты заданы классом; предметы пока только показываются.
        slots = "   ".join(f"{t(slot)}: {t(item_id) if item_id else '-'}"
                           for slot, item_id in zip(unit.definition.slots, unit.state.equipment))
        ui.text(f"{t('slots')}: {slots}", 16, y + 40, DIM, "small", WIDTH - 32)
        if ui.button(t("To reserve"), pygame.Rect(16, y + 62, 130, 24), enabled=in_squad):
            army.unassign(unit.uid)
            self.selected = ("reserve", unit.uid)
            app.changed()
        if ui.button(t("Make leader"), pygame.Rect(154, y + 62, 150, 24),
                     enabled=in_squad and squad.leader_uid != unit.uid):
            army.set_leader(squad.id, unit.uid)
            app.changed()
        if ui.button(t("Dismiss"), pygame.Rect(312, y + 62, 130, 24), color=RED):
            army.dismiss(unit.uid)
            self.selected = None
            app.changed()


# --- тактики ---------------------------------------------------------------

class TacticsEditor:
    LIST_W = 150
    X = 176
    # Смещения колонок от X: условие на себя, условие на цель, выбор цели, навык, кнопки.
    COL_SELF, COL_TARGET, COL_PICK, COL_SKILL, COL_UP = 24, 212, 400, 494, 678
    COND_W, PARAM_W = 96, 84

    def __init__(self) -> None:
        self.uid: Optional[int] = None

    def draw(self, ui: UI, app: EditorHost) -> None:
        units = app.units()
        if not units:
            ui.text(ui.t("No units."), 16, TOP)
            return
        if self.uid not in {u.uid for u in units}:
            self.uid = units[0].uid
        enemy_uids = app.setup.enemy.units
        for i, unit in enumerate(units[:22]):
            mark = " *" if unit.has_custom_tactics else ""
            color = ENEMY_TEXT if unit.uid in enemy_uids else TEXT
            rect = pygame.Rect(16, TOP + i * 25, self.LIST_W, 22)
            if ui.button(app.label(unit) + mark, rect, unit.uid == self.uid, color=color):
                self.uid = unit.uid
        unit = next(u for u in units if u.uid == self.uid)
        self._draw_rules(ui, app, unit)

    def _draw_rules(self, ui: UI, app: EditorHost, unit: Unit) -> None:
        t, db, x = ui.t, app.db, self.X
        state = t("custom") if unit.has_custom_tactics else t("default")
        ui.text(t("Tactics of {unit} ({state})", unit=app.label(unit), state=state), x, TOP + 2)
        ui.text(t(HINT_CYCLE) + " " + t("Rules are checked top to bottom: the first one whose"),
                x, TOP + 24, DIM, "small")
        ui.text(t("conditions hold, with a valid target and enough AP, is used. Otherwise: Attack, if AP allows."),
                x, TOP + 40, DIM, "small")
        y0 = TOP + 84
        for label, offset in (("if self", self.COL_SELF), ("if target", self.COL_TARGET),
                              ("pick", self.COL_PICK), ("skill", self.COL_SKILL)):
            ui.text(t(label), x + offset, y0 - 20, DIM, "small")

        rules = unit.tactics.to_list()
        skills = list(db.skills_for(unit))
        new_rules: Optional[list[dict[str, Any]]] = None
        for i, rule in enumerate(rules):
            y = y0 + i * ROW_H
            ui.text(f"{i + 1}.", x, y + 4)
            edited = dict(rule)
            for key, offset in (("self_condition", self.COL_SELF), ("condition", self.COL_TARGET)):
                condition = condition_buttons(ui, db, rule[key], x + offset, y, self.COND_W, self.PARAM_W)
                if condition is not None:
                    edited[key] = condition
            delta = ui.button(t(rule["selector"]), pygame.Rect(x + self.COL_PICK, y, 90, 24))
            if delta:
                edited["selector"] = cycle(list(SELECTORS), rule["selector"], delta)
            skill = db.skills.get(rule["skill"])
            available = skill is not None and rule["skill"] in skills
            text = f"{t(skill.name)} AP{skill.ap_cost}" if skill else rule["skill"]
            # Красным: навык больше недоступен юниту (сняли привязку или предмет), правило пропускается.
            delta = ui.button(text, pygame.Rect(x + self.COL_SKILL, y, 180, 24), color=TEXT if available else RED)
            if delta:
                edited["skill"] = cycle(skills, rule["skill"], delta)
            if edited != rule:
                new_rules = rules[:i] + [edited] + rules[i + 1:]
            if ui.button("^", pygame.Rect(x + self.COL_UP, y, 32, 24), enabled=i > 0):
                new_rules = rules[:i - 1] + [rule, rules[i - 1]] + rules[i + 1:]
            if ui.button("v", pygame.Rect(x + self.COL_UP + 36, y, 32, 24), enabled=i < len(rules) - 1):
                new_rules = rules[:i] + [rules[i + 1], rule] + rules[i + 2:]
            if ui.button("x", pygame.Rect(x + self.COL_UP + 72, y, 26, 24), color=RED):
                new_rules = rules[:i] + rules[i + 1:]

        y = y0 + len(rules) * ROW_H + 6
        if ui.button(t("+ Add rule"), pygame.Rect(x + 24, y, 150, 24), enabled=len(rules) < MAX_RULES):
            new_rules = rules + [default_rule(db, unit)]
        if ui.button(t("Reset to default"), pygame.Rect(x + 182, y, 190, 24), enabled=unit.has_custom_tactics):
            unit.reset_tactics()
            app.changed()
            return
        if new_rules is not None:
            try:
                # Старое правило с уже недоступным навыком остаётся как есть (в бою оно
                # пропускается); проверяются только новые и изменённые правила.
                stale = [r for r in new_rules if r in rules and r["skill"] not in skills]
                set_tactics(db, unit, [r for r in new_rules if r not in stale])
                unit.set_tactics(TacticsSet.from_list(new_rules))
                app.changed()
            except (ValueError, KeyError) as error:
                app.message = str(error)

        y += 40
        ui.text(t("Available skills"), x, y, DIM, "small")
        for skill_id in skills:
            y += 18
            if y > HEIGHT - 44:
                break
            skill = db.skills[skill_id]
            ui.text(f"{t(skill.name)}: {describe_skill(skill, db, t)}", x, y, DIM, "small", WIDTH - x - 16)


# --- конструктор навыков ---------------------------------------------------

class SkillEditor:
    LIST_W = 200
    X = 240
    VISIBLE = 6  # строк эффектов на экране; остальные прокручиваются колесом

    def __init__(self) -> None:
        self.draft = SkillDraft()
        self.focus = False
        self.scroll = 0

    def key(self, event: pygame.event.Event) -> bool:
        """Ввод названия. Возвращает True, если клавиша поглощена полем ввода."""
        if not self.focus:
            return False
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
            self.focus = False
        elif event.key == pygame.K_BACKSPACE:
            self.draft.name = self.draft.name[:-1]
        elif event.unicode and event.unicode.isprintable() and len(self.draft.name) < NAME_MAX:
            self.draft.name += event.unicode
        return True

    def draw(self, ui: UI, app: EditorHost) -> None:
        self._draw_list(ui, app.db)
        self._draw_form(ui, app)

    def _draw_list(self, ui: UI, db: Database) -> None:
        t = ui.t
        ui.text(t("Skills (click to copy)"), 16, TOP, DIM, "small")
        for i, skill in enumerate(list(db.skills.values())[:20]):
            custom = skill.id in db.skill_bindings
            rect = pygame.Rect(16, TOP + 20 + i * 25, self.LIST_W, 22)
            text = t(skill.name) + (" *" if custom else "")
            if ui.button(text, rect, custom and skill.id == self.draft.skill_id):
                # Встроенный навык открывается как шаблон под новым именем.
                name = None if custom else f"{skill.name} II"
                self.draft = SkillDraft.from_skill(skill, name, db.skill_bindings.get(skill.id))
                self.scroll, self.focus = 0, False
        ui.text(t("* = made in the builder"), 16, HEIGHT - 52, DIM, "small")

    def _draw_form(self, ui: UI, app: EditorHost) -> None:
        t, db, draft, x = ui.t, app.db, self.draft, self.X
        skill_id = draft.skill_id
        is_custom = skill_id in db.skill_bindings
        is_builtin = skill_id in db.skills and not is_custom

        # Название и id
        ui.text(t("Name"), x, TOP + 4)
        name_rect = pygame.Rect(x + 90, TOP, 250, 26)
        pygame.draw.rect(ui.screen, SLOT, name_rect)
        pygame.draw.rect(ui.screen, YELLOW if self.focus else DIM, name_rect, 1)
        ui.text(draft.name + ("_" if self.focus else ""), name_rect.x + 6, name_rect.y + 4)
        if ui.clicks:
            self.focus = bool(ui.clicked(name_rect))
        status, color = (t("built-in id, pick another name"), RED) if is_builtin else \
            (t("updates existing skill"), YELLOW) if is_custom else (t("new skill"), GREEN)
        ui.text(f"id: {skill_id or '?'}  ({status})", x + 350, TOP + 6, color, "small", WIDTH - x - 366)

        # Тип, сила, цена
        y = TOP + 32
        ui.text(t("Kind"), x, y + 4)
        delta = ui.button(t(draft.kind), pygame.Rect(x + 90, y, 120, 24))
        if delta:
            draft.set_kind(cycle(SKILL_KINDS, draft.kind, delta))
        has_power = draft.kind != SKILL_SUPPORT
        ui.text(t("Power"), x + 226, y + 4, TEXT if has_power else DIM)
        if ui.button("-", pygame.Rect(x + 304, y, 22, 24), enabled=has_power):
            draft.power = max(0.0, round(draft.power - POWER_STEP, 2))
        ui.text(f"x{draft.power:.1f}", x + 330, y + 4, TEXT if has_power else DIM)
        if ui.button("+", pygame.Rect(x + 372, y, 22, 24), enabled=has_power):
            draft.power = min(POWER_MAX, round(draft.power + POWER_STEP, 2))
        draft.ap_cost = stepper(ui, t("AP cost"), draft.ap_cost, 0, AP_COST_MAX, x + 410, y, 96)

        # Направленность: на кого нацелен и какую область задевает; восстановление ресурсов
        y = TOP + 62
        ui.text(t("Aimed at"), x, y + 4)
        delta = ui.button(t(draft.targets), pygame.Rect(x + 90, y, 120, 24))
        if delta:
            draft.targets = cycle(SIDES, draft.targets, delta)
        ui.text(t("Area"), x + 226, y + 4)
        delta = ui.button(t(draft.area), pygame.Rect(x + 304, y, 90, 24))
        if delta:
            draft.area = cycle(list(AREAS), draft.area, delta)
        draft.ap_restore = stepper(ui, t("Gives AP"), draft.ap_restore, 0, RESTORE_MAX, x + 410, y, 96)
        draft.pp_restore = stepper(ui, t("PP"), draft.pp_restore, 0, RESTORE_MAX, x + 590, y, 30)

        # Привязка: каким классам и каким предметам принадлежит навык
        y = TOP + 92
        ui.text(t("Classes"), x, y + 4)
        self._toggles(ui, [(d.id, t(d.name)) for d in db.units.values()], draft.bind_units, x + 90, y, 84)
        y = TOP + 120
        ui.text(t("Items"), x, y + 4)
        self._toggles(ui, [(i.id, t(i.name)) for i in db.items.values()], draft.bind_items, x + 90, y, 130)
        if not (draft.bind_units or draft.bind_items):
            ui.text(t("not bound: nobody can use it"), x + 370, y + 6, RED, "small")

        # Эффекты
        y = TOP + 150
        ui.text(t("Effects: {n}", n=len(draft.applies)), x, y + 4)
        if ui.button(t("+ Add effect"), pygame.Rect(x + 130, y, 150, 24)):
            draft.applies.append(default_apply(db, next(iter(db.effects))))
            self.scroll = max(0, len(draft.applies) - self.VISIBLE)
        ui.text(t(HINT_CYCLE), x + 296, y + 6, DIM, "small")
        y += 30
        for label, offset in (("effect", 28), ("goes to", 222), ("if target", 300)):
            ui.text(t(label), x + offset, y, DIM, "small")
        y += 18
        self._draw_applies(ui, db, x, y)

        y += self.VISIBLE * ROW_H + 4
        if len(draft.applies) > self.VISIBLE:
            ui.text(t("rows {a}-{b} of {n}, mouse wheel scrolls", a=self.scroll + 1,
                      b=self.scroll + self.VISIBLE, n=len(draft.applies)), x + 28, y, DIM, "small")
        y += 20
        try:
            summary, color = describe_skill(draft.build(db), db, t), TEXT
        except ValueError as error:
            summary, color = f"{t('cannot save')}: {error}", RED
        ui.text(summary, x, y, color, "small", WIDTH - x - 16)

        y += 24
        if ui.button(t("Save skill"), pygame.Rect(x, y, 150, 26), enabled=not is_builtin):
            self._save(app)
        if ui.button(t("New"), pygame.Rect(x + 158, y, 90, 26)):
            self.draft, self.scroll = SkillDraft(), 0
        if ui.button(t("Delete"), pygame.Rect(x + 256, y, 110, 26), enabled=is_custom, color=RED):
            self._delete(app, skill_id)
        ui.text(t("A skill belongs to the chosen classes and to whoever wears the chosen items."),
                x, y + 34, DIM, "small")
        ui.text(t("Effects apply after damage or healing; conditions are checked on each unit hit."),
                x, y + 50, DIM, "small")

    @staticmethod
    def _toggles(ui: UI, options: list[tuple[str, str]], chosen: list[str], x: int, y: int, width: int) -> None:
        """Ряд кнопок-переключателей: id добавляется в chosen или убирается из него."""
        for i, (option_id, text) in enumerate(options):
            if ui.button(text, pygame.Rect(x + i * (width + 4), y, width, 24), option_id in chosen):
                if option_id in chosen:
                    chosen.remove(option_id)
                else:
                    chosen.append(option_id)

    def _draw_applies(self, ui: UI, db: Database, x: int, y: int) -> None:
        t = ui.t
        applies = self.draft.applies
        self.scroll = max(0, min(self.scroll - ui.wheel, len(applies) - self.VISIBLE))
        pygame.draw.rect(ui.screen, PANEL, pygame.Rect(x, y - 2, WIDTH - x - 16, self.VISIBLE * ROW_H + 2))
        effect_ids = list(db.effects)
        remove: Optional[int] = None
        for row, index in enumerate(range(self.scroll, min(len(applies), self.scroll + self.VISIBLE))):
            apply = applies[index]
            ry = y + row * ROW_H
            ui.text(f"{index + 1}.", x + 4, ry + 4, DIM, "small")
            effect = db.effects[apply["effect_id"]]
            tags = ", ".join(t(tag) for tag in sorted(effect.tags))
            delta = ui.button(f"{t(effect.name)} [{tags}]", pygame.Rect(x + 28, ry, 190, 24))
            if delta:
                # Получатель подстраивается под знак эффекта: бафф на себя, дебафф на цель.
                apply.update(default_apply(db, cycle(effect_ids, apply["effect_id"], delta)), condition=apply["condition"])
            delta = ui.button(t(apply["to"]), pygame.Rect(x + 222, ry, 74, 24))
            if delta:
                apply["to"] = cycle(APPLY_RECIPIENTS, apply["to"], delta)
            condition = condition_buttons(ui, db, apply["condition"], x + 300, ry, 120, 130)
            if condition is not None:
                apply["condition"] = condition
            if ui.button("x", pygame.Rect(x + 558, ry, 28, 24), color=RED):
                remove = index
        if remove is not None:
            del applies[remove]

    def _save(self, app: EditorHost) -> None:
        try:
            skill = self.draft.save_to(app.db)
        except ValueError as error:
            app.message = f"{app.t('cannot save')}: {error}"
            return
        app.changed()
        app.message = app.t("saved skill {id}", id=skill.id)

    def _delete(self, app: EditorHost, skill_id: str) -> None:
        users = skill_users(skill_id, app.units())
        if users:
            app.message = app.t("cannot delete: used in tactics of {units}", units=", ".join(app.label(u) for u in users))
            return
        app.db.remove_custom_skill(skill_id)
        app.changed()
        app.message = app.t("deleted skill {id}", id=skill_id)
