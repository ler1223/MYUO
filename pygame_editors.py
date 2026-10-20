"""Экраны редакторов для demo_pygame: отряды, тактики, навыки.

Экраны только вызывают операции ядра (game.world, game.editing, Database.update)
над справочником app.db и редактируемой расстановкой app.setup; бой идёт на копии.
Все строки интерфейса проходят через ui.t (перевод, ключ = английский текст).
Все выборы сделаны выпадающими списками с поиском (ui.dropdown / ui.multiselect).
"""
from __future__ import annotations

import copy
from typing import Any, Hashable, Iterable, Mapping, Optional, Protocol, Sequence

import pygame

from game.database import Database
from game.definitions import APPLY_RECIPIENTS, CATEGORIES, PART_DAMAGE, PART_KINDS
from game.editing import (
    condition_params,
    default_apply,
    default_condition,
    default_rule,
    describe_skill,
    new_part,
    new_skill_data,
    param_options,
    set_owners,
    set_passive_tactics,
    set_tactics,
    skill_owners,
)
from game.i18n import Translator
from game.scenario import Scenario
from game.squad import MAX_GRID, MAX_SQUAD_UNITS, MIN_GRID
from game.stats import SCALING_STATS, Stat
from game.tactics import CONDITIONS, SELECTORS, SIDES
from game.tags import TAG_DAMAGE, TAG_SKILL, TAG_UNIT
from game.unit import Unit
from pygame_ui import DIM, HEIGHT, PANEL, RED, TEXT, UI, WIDTH, Option

TOP = 44            # под панелью вкладок
ROW_H = 28
MAX_RULES = 12
ENEMY_TEXT = (240, 170, 170)
EMPTY = ""          # значение варианта «пусто» в выпадающих списках
LIST_W = 190        # ширина списка объектов слева
FORM_X = 222        # левый край формы справа от списка


class EditorHost(Protocol):
    """Что экранам нужно от приложения."""

    db: Database
    setup: Scenario
    message: str
    t: Translator

    def changed(self) -> None: ...
    def data_changed(self) -> None: ...
    def units(self) -> list[Unit]: ...
    def label(self, unit: Unit) -> str: ...
    def next_uid(self) -> int: ...
    def reset_setup(self) -> None: ...


# --- общие помощники --------------------------------------------------------

def apply(app: EditorHost, section: str, key: str, data: Mapping[str, Any]) -> bool:
    """Записывает определение в справочник; ошибку проверки показывает сообщением."""
    try:
        app.db.update(section, key, data)
    except (ValueError, KeyError, TypeError) as error:
        app.message = str(error)
        return False
    app.data_changed()
    return True


def named(ui: UI, definitions: Iterable[Any]) -> list[Option]:
    """Варианты списка из определений: (id, переведённое название)."""
    return [(d.id, ui.t(d.name)) for d in definitions]


def plain(ui: UI, values: Iterable[str]) -> list[Option]:
    """Варианты списка из строковых кодов: (код, перевод кода)."""
    return [(value, ui.t(value)) for value in values]


def tag_options(ui: UI, db: Database, kind: str) -> list[Option]:
    return named(ui, (tag for tag in db.tags.values() if tag.kind == kind))


def entity_list(ui: UI, key: Hashable, entries: Sequence[tuple[str, str]], selected: Optional[str],
                y: int, rows: int, colors: Optional[Mapping[str, Any]] = None) -> Optional[str]:
    """Прокручиваемый список объектов слева. Возвращает id, по которому кликнули."""
    area = pygame.Rect(16, y, LIST_W, rows * 25)
    offset = ui.scroll(key, area, len(entries), rows)
    clicked = None
    for row, (entry_id, label) in enumerate(entries[offset:offset + rows]):
        color = (colors or {}).get(entry_id, TEXT)
        if ui.button(label, pygame.Rect(16, y + row * 25, LIST_W, 22), entry_id == selected, color=color):
            clicked = entry_id
    if len(entries) > rows:
        ui.text(f"{offset + 1}-{offset + rows}/{len(entries)}", 16, y + rows * 25 + 2, DIM, "small")
    return clicked


def param_label(ui: UI, value: Any) -> str:
    return f"{round(value * 100)}%" if isinstance(value, float) else ui.t(str(value))


def condition_widgets(ui: UI, db: Database, key: Hashable, condition: dict[str, Any], x: int, y: int,
                      type_w: int, param_w: int) -> Optional[dict[str, Any]]:
    """Выбор типа условия и его параметров. Возвращает новое условие, если его изменили.

    Ширины заданы в базовом масштабе и умножаются на ui.scale (окно башни крупнее)."""
    k = ui.scale
    type_w, param_w, h, gap = round(type_w * k), round(param_w * k), round(24 * k), round(4 * k)
    result = None
    picked = ui.dropdown((key, "type"), pygame.Rect(x, y, type_w, h), plain(ui, CONDITIONS), condition["type"])
    if picked is not None and picked != condition["type"]:
        result = default_condition(picked, db)
    params = condition_params(condition["type"])
    for i, (param, kind) in enumerate(params.items()):
        width = (param_w - gap * (len(params) - 1)) // len(params)
        rect = pygame.Rect(x + type_w + gap + i * (width + gap), y, width, h)
        choices = [(value, param_label(ui, value)) for value in param_options(kind, db)]
        picked = ui.dropdown((key, param), rect, choices, condition[param])
        if picked is not None and picked != condition[param]:
            result = dict(condition, **{param: picked})
    return result


# Смещения колонок таблицы правил от её левого края (базовый масштаб).
RULE_SELF, RULE_TARGET, RULE_PICK, RULE_SKILL, RULE_MOVE = 24, 216, 408, 506, 680
RULE_COND_W, RULE_PARAM_W = 100, 84


def rule_table(ui: UI, db: Database, key: Hashable, rules: list[dict[str, Any]], skill_ids: Sequence[str],
               x: int, y: int, max_rules: int = MAX_RULES) -> Optional[list[dict[str, Any]]]:
    """Таблица правил тактики с кнопкой добавления. Возвращает новый список правил, если его изменили.

    Размеры в базовом масштабе умножаются на ui.scale."""
    t = ui.t
    s = lambda v: round(v * ui.scale)
    h, row_h = s(24), s(ROW_H)
    for label, offset in (("if self", RULE_SELF), ("if target", RULE_TARGET), ("pick", RULE_PICK),
                          ("skill", RULE_SKILL)):
        ui.text(t(label), x + s(offset), y, DIM, "small")
    y += s(20)
    new_rules: Optional[list[dict[str, Any]]] = None
    def cost(skill_id: str) -> str:
        skill = db.skills[skill_id]
        return f"AP{skill.ap_cost}" + (f" PP{skill.pp_cost}" if skill.pp_cost else "")

    skill_choices = [(s_id, f"{t(db.skills[s_id].name)} {cost(s_id)}") for s_id in skill_ids if s_id in db.skills]
    for i, rule in enumerate(rules):
        ry = y + i * row_h
        ui.text(f"{i + 1}.", x, ry + s(4))
        edited = dict(rule)
        for field, offset in (("self_condition", RULE_SELF), ("condition", RULE_TARGET)):
            condition = condition_widgets(ui, db, (key, i, field), rule[field], x + s(offset), ry,
                                          RULE_COND_W, RULE_PARAM_W)
            if condition is not None:
                edited[field] = condition
        picked = ui.dropdown((key, i, "selector"), pygame.Rect(x + s(RULE_PICK), ry, s(94), h),
                             plain(ui, SELECTORS), rule["selector"])
        if picked is not None:
            edited["selector"] = picked
        # Красным: навык недоступен (сняли с класса или предмета), правило в бою пропускается.
        available = rule["skill"] in skill_ids
        missing = t(db.skills[rule["skill"]].name) if rule["skill"] in db.skills else rule["skill"]
        choices = skill_choices if available else [(rule["skill"], f"! {missing}"), *skill_choices]
        picked = ui.dropdown((key, i, "skill"), pygame.Rect(x + s(RULE_SKILL), ry, s(170), h), choices, rule["skill"],
                             color=TEXT if available else RED)
        if picked is not None:
            edited["skill"] = picked
        if edited != rule:
            new_rules = rules[:i] + [edited] + rules[i + 1:]
        if ui.button("^", pygame.Rect(x + s(RULE_MOVE), ry, s(26), h), enabled=i > 0):
            new_rules = rules[:i - 1] + [rule, rules[i - 1]] + rules[i + 1:]
        if ui.button("v", pygame.Rect(x + s(RULE_MOVE + 30), ry, s(26), h), enabled=i < len(rules) - 1):
            new_rules = rules[:i] + [rules[i + 1], rule] + rules[i + 2:]
        if ui.button("x", pygame.Rect(x + s(RULE_MOVE + 60), ry, s(26), h), color=RED):
            new_rules = rules[:i] + rules[i + 1:]
    can_add = len(rules) < max_rules and bool(skill_choices)
    if ui.button(t("+ Add rule"), pygame.Rect(x + s(24), y + len(rules) * row_h + s(4), s(160), h), enabled=can_add):
        new_rules = rules + [default_rule([s_id for s_id, _ in skill_choices])]
    return new_rules


# --- отряды ----------------------------------------------------------------

class SquadEditor:
    GRID_X, GRID_Y = 16, 104
    GRID_W, GRID_H = 450, 252     # место под поле отряда; клетки делят его поровну
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
        if self._draw_field_size(ui, app):
            self.selected = None
            return
        army, squad = armies[self.army_key]
        formation = squad.formation
        cell_w, cell_h = self.GRID_W // formation.cols, self.GRID_H // formation.rows

        ui.text(t("Formation {n}/{max}  (top row = front, * = leader)", n=len(formation), max=formation.max_units),
                16, TOP + 34)
        for row in range(formation.rows):
            for col in range(formation.cols):
                rect = pygame.Rect(self.GRID_X + col * cell_w, self.GRID_Y + row * cell_h, cell_w - 6, cell_h - 6)
                if ui.button("", rect, self.selected == ("cell", (row, col))):
                    self._click_cell(app, army, squad, (row, col))
                unit = formation.unit_at(row, col)
                if unit is not None:
                    # Чем мельче клетка, тем меньше строк в ней помещается.
                    leader = " *" if squad.leader_uid == unit.uid else ""
                    roomy = rect.height >= 56
                    ui.text(f"{app.label(unit)}{leader}", rect.x + 5, rect.y + 4, font="main" if roomy else "small",
                            width=rect.width - 10)
                    if roomy:
                        ui.text(f"L{unit.state.level}  HP {unit.max_hp}  INIT {unit.stat(Stat.INITIATIVE)}",
                                rect.x + 5, rect.y + 26, DIM, "small", rect.width - 10)
                    elif rect.height >= 36:
                        ui.text(f"L{unit.state.level} HP {unit.max_hp}", rect.x + 5, rect.y + 20, DIM, "small",
                                rect.width - 10)
                    if rect.height >= 74:
                        ui.text(f"ATK {unit.stat(Stat.PHYS_ATK)}/{unit.stat(Stat.MAG_ATK)}  "
                                f"DEF {unit.stat(Stat.PHYS_DEF)}/{unit.stat(Stat.MAG_DEF)}",
                                rect.x + 5, rect.y + 44, DIM, "small", rect.width - 10)

        self._draw_reserve(ui, app, army)
        self._draw_selection(ui, app, army, squad)
        ui.text(t("Click a unit, then a cell to move or swap. Click a reserve unit, then a cell to place it."),
                16, HEIGHT - 44, DIM, "small")

    @staticmethod
    def _draw_field_size(ui: UI, app: EditorHost) -> bool:
        """Размер поля отряда и предел числа юнитов (общие для всех отрядов). True, если изменили."""
        t, size = ui.t, app.db.formation
        values = {"rows": size.rows, "cols": size.cols, "max_units": size.max_units}
        ui.text(t("Field"), 436, TOP + 4, font="small")
        fields = (("rows", "rows", 480, MIN_GRID, MAX_GRID), ("cols", "columns", 566, MIN_GRID, MAX_GRID),
                  ("max_units", "units", 676, 1, MAX_SQUAD_UNITS))
        changed = False
        for field, label, fx, low, high in fields:
            value = ui.number_input(("field", field), pygame.Rect(fx, TOP, 34, 24), values[field], low, high)
            ui.text(t(label), fx + 38, TOP + 5, DIM, "small")
            if value is not None:
                values[field], changed = value, True
        if changed:
            values["max_units"] = min(values["max_units"], values["rows"] * values["cols"])
            try:
                app.db.set_formation(**values)
                app.data_changed()
            except ValueError as error:
                app.message = str(error)
                return False
        return changed

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
        picked = ui.dropdown("recruit", pygame.Rect(x, y + 24, 240, 24),
                             [(EMPTY, t("choose a class...")), *named(ui, app.db.units.values())], EMPTY)
        if picked:
            unit = army.recruit(app.db.create_unit(picked, app.next_uid()))
            self.selected = ("reserve", unit.uid)
            app.changed()

    def _draw_selection(self, ui: UI, app: EditorHost, army, squad) -> None:
        t, db = ui.t, app.db
        y = self.GRID_Y + self.GRID_H + 4
        unit = self._selected_unit(army, squad)
        if unit is None:
            ui.text(t("Nothing selected"), 16, y, DIM)
            return
        in_squad = self.selected[0] == "cell"
        stats = "  ".join(f"{t(s.value)} {unit.stat(s)}" for s in Stat)
        ui.text(f"{app.label(unit)}  L{unit.state.level}  AP {unit.ap.max}  PP {unit.pp.max}   "
                f"{t('tags')}: {', '.join(t(tag) for tag in sorted(unit.tags)) or '-'}", 16, y, width=WIDTH - 32)
        ui.text(stats, 16, y + 22, DIM, "small", WIDTH - 32)
        skills = ", ".join(t(db.skills[s].name) for s in unit.skill_ids if s in db.skills) or "-"
        passives = ", ".join(t(db.passives[p].name) for p in unit.passive_ids if p in db.passives) or "-"
        ui.text(f"{t('skills')}: {skills}   {t('passives')}: {passives}", 16, y + 40, DIM, "small", WIDTH - 32)

        # Снаряжение: по выпадающему списку на каждый слот класса.
        for i, slot in enumerate(unit.definition.slots[:6]):
            sx = 16 + i * 162
            ui.text(t(slot), sx, y + 60, DIM, "small", 154)
            fitting = [item for item in db.items.values() if item.slot == slot]
            current = unit.state.equipment[i] or EMPTY
            picked = ui.dropdown(("equip", unit.uid, i), pygame.Rect(sx, y + 76, 154, 24),
                                 [(EMPTY, "-"), *named(ui, fitting)], current)
            if picked is not None and picked != current:
                if picked == EMPTY:
                    unit.unequip(i)
                else:
                    unit.equip(i, picked)
                unit.state.current_hp = unit.max_hp
                app.changed()

        by = y + 108
        if ui.button(t("To reserve"), pygame.Rect(16, by, 130, 24), enabled=in_squad):
            army.unassign(unit.uid)
            self.selected = ("reserve", unit.uid)
            app.changed()
        if ui.button(t("Make leader"), pygame.Rect(154, by, 150, 24),
                     enabled=in_squad and squad.leader_uid != unit.uid):
            army.set_leader(squad.id, unit.uid)
            app.changed()
        if ui.button(t("Dismiss"), pygame.Rect(312, by, 130, 24), color=RED):
            army.dismiss(unit.uid)
            self.selected = None
            app.changed()


# --- тактики ---------------------------------------------------------------

class TacticsEditor:
    def __init__(self) -> None:
        self.uid: Optional[int] = None

    def draw(self, ui: UI, app: EditorHost) -> None:
        units = app.units()
        if not units:
            ui.text(ui.t("No units."), 16, TOP)
            return
        if self.uid not in {u.uid for u in units}:
            self.uid = units[0].uid
        unit = next(u for u in units if u.uid == self.uid)
        self._draw_rules(ui, app, unit)

        entries = [(str(u.uid), app.label(u) + (" *" if u.has_custom_tactics else "")) for u in units]
        colors = {str(uid): ENEMY_TEXT for uid in app.setup.enemy.units}
        clicked = entity_list(ui, "tactics-units", entries, str(self.uid), TOP, 21, colors)
        if clicked is not None:
            self.uid = int(clicked)

    def _draw_rules(self, ui: UI, app: EditorHost, unit: Unit) -> None:
        t, db, x = ui.t, app.db, FORM_X
        state = t("custom") if unit.has_custom_tactics else t("default")
        ui.text(t("Tactics of {unit} ({state})", unit=app.label(unit), state=state), x, TOP + 2)
        ui.text(t("Rules are checked top to bottom: the first one whose conditions hold,"), x, TOP + 24, DIM, "small")
        ui.text(t("with a valid target and enough AP, is used. Otherwise: Attack, if AP allows."),
                x, TOP + 40, DIM, "small")

        rules = unit.tactics.to_list()
        new_rules = rule_table(ui, db, ("tactics", unit.uid), rules, unit.skill_ids, x, TOP + 64)
        y = TOP + 84 + len(rules) * ROW_H + 4
        if ui.button(t("Reset to default"), pygame.Rect(x + 192, y, 200, 24), enabled=unit.has_custom_tactics):
            unit.reset_tactics()
            app.changed()
            return
        if new_rules is not None:
            try:
                set_tactics(db, unit, new_rules)
                app.changed()
            except (ValueError, KeyError) as error:
                app.message = str(error)

        y += 34
        ui.text(t("Passive tactics: rules apply to the targets that caused the trigger."), x, y, DIM, "small")
        y += 22
        for passive_id in unit.passive_ids:
            passive = db.passives.get(passive_id)
            if passive is None or y > HEIGHT - 140:
                continue
            state = t("custom") if unit.has_passive_tactics(passive_id) else t("default")
            ui.text(t("Passive {name} ({state})", name=t(passive.name), state=state), x, y)
            if ui.button(t("Reset to default"), pygame.Rect(x + 192, y - 2, 200, 22),
                         enabled=unit.has_passive_tactics(passive_id)):
                unit.reset_passive_tactics(passive_id)
                app.changed()
                return
            y += 24
            rules = unit.passive_tactics_of(passive_id).to_list()
            new_rules = rule_table(ui, db, ("passive", unit.uid, passive_id), rules, unit.skill_ids, x, y,
                                   max_rules=4)
            if new_rules is not None:
                try:
                    set_passive_tactics(db, unit, passive_id, new_rules)
                    app.changed()
                except (ValueError, KeyError) as error:
                    app.message = str(error)
            y += 24 + max(1, len(rules)) * ROW_H

        ui.text(t("Available skills"), x, y + 8, DIM, "small")
        y += 8
        for skill_id in unit.skill_ids:
            y += 18
            if y > HEIGHT - 44 or skill_id not in db.skills:
                break
            skill = db.skills[skill_id]
            ui.text(f"{t(skill.name)}: {describe_skill(skill, db, t)}", x, y, DIM, "small", WIDTH - x - 16)


# --- навыки ----------------------------------------------------------------

class SkillEditor:
    PART_ROWS = 3
    APPLY_ROWS = 3

    def __init__(self) -> None:
        self.skill_id: Optional[str] = None

    def draw(self, ui: UI, app: EditorHost) -> None:
        db = app.db
        if self.skill_id not in db.skills:
            self.skill_id = next(iter(db.skills), None)
        if self.skill_id is not None:
            self._draw_form(ui, app, self.skill_id)
        ui.text(ui.t("Skills"), 16, TOP, DIM, "small")
        clicked = entity_list(ui, "skills", named(ui, db.skills.values()), self.skill_id, TOP + 20, 18)
        if clicked is not None:
            self.skill_id = clicked
        if ui.button(ui.t("+ New"), pygame.Rect(16, HEIGHT - 84, 92, 24)):
            self.skill_id = db.create("skills", "New Skill", new_skill_data())
            app.data_changed()
        if ui.button(ui.t("Delete"), pygame.Rect(112, HEIGHT - 84, 94, 24), enabled=self.skill_id is not None,
                     color=RED):
            db.delete("skills", self.skill_id)
            app.data_changed()

    def _draw_form(self, ui: UI, app: EditorHost, skill_id: str) -> None:
        t, db, x = ui.t, app.db, FORM_X
        skill = db.skills[skill_id]
        data = skill.to_dict()
        new = copy.deepcopy(data)
        key = ("skill", skill_id)

        def number(field: str, label: str, fx: int, fy: int, label_w: int, low: int, high: int, width: int = 44) -> None:
            ui.text(t(label), fx, fy + 4, font="small")
            value = ui.number_input((key, field), pygame.Rect(fx + label_w, fy, width, 24), data[field], low, high)
            if value is not None:
                new[field] = value

        def choice(field: str, label: str, fx: int, fy: int, label_w: int, width: int, choices: list[Option]) -> None:
            ui.text(t(label), fx, fy + 4, font="small")
            picked = ui.dropdown((key, field), pygame.Rect(fx + label_w, fy, width, 24), choices, data[field])
            if picked is not None:
                new[field] = picked

        # Строка 1: название и id
        ui.text(t("Name"), x, TOP + 4, font="small")
        name = ui.text_input((key, "name"), pygame.Rect(x + 76, TOP, 230, 24), data["name"])
        if name:
            new["name"] = name
        ui.text(f"id: {skill_id}", x + 320, TOP + 5, DIM, "small")

        # Строка 2: цена в AP и PP, цель, область, удары, точность
        y = TOP + 30
        number("ap_cost", "AP cost", x, y, 60, 0, 9, 40)
        number("pp_cost", "PP cost", x + 108, y, 60, 0, 9, 40)
        choice("targets", "Aimed at", x + 220, y, 62, 90, plain(ui, SIDES))
        choice("area", "Area", x + 382, y, 56, 96, named(ui, db.areas.values()))
        number("hits", "Hits", x + 544, y, 44, 1, 9, 40)
        number("accuracy", "Accuracy %", x + 638, y, 78, 0, 999, 46)

        # Строка 3: теги навыка, восстановление, бонус по тегу
        y = TOP + 60
        ui.text(t("Skill tags"), x, y + 4, font="small")
        tags = ui.multiselect((key, "tags"), pygame.Rect(x + 76, y, 170, 24), tag_options(ui, db, TAG_SKILL), data["tags"])
        if tags is not None:
            new["tags"] = tags
        number("ap_restore", "Gives AP", x + 258, y, 70, 0, 9)
        number("pp_restore", "PP", x + 380, y, 24, 0, 9)
        ui.text(t("Bonus vs"), x + 458, y + 4, font="small")
        bonus_tag, bonus_mult = next(iter(data["bonus_vs"].items()), (EMPTY, 1.5))
        picked = ui.dropdown((key, "bonus_tag"), pygame.Rect(x + 530, y, 130, 24),
                             [(EMPTY, "-"), *tag_options(ui, db, TAG_UNIT)], bonus_tag)
        if picked is not None:
            new["bonus_vs"] = {picked: bonus_mult} if picked else {}
        mult = ui.number_input((key, "bonus_mult"), pygame.Rect(x + 664, y, 50, 24), bonus_mult, 0, 10, integer=False)
        if mult is not None and bonus_tag:
            new["bonus_vs"] = {bonus_tag: mult}

        # Строка 4: кому принадлежит навык
        y = TOP + 90
        for section, label, ox in (("units", "Classes", 0), ("items", "Items", 372)):
            ui.text(t(label), x + ox, y + 4, font="small")
            owners = skill_owners(db, section, skill_id)
            picked = ui.multiselect((key, section), pygame.Rect(x + ox + 76, y, 282, 24),
                                    named(ui, getattr(db, section).values()), owners)
            if picked is not None:
                try:
                    set_owners(db, section, skill_id, picked)
                    app.data_changed()
                except ValueError as error:
                    app.message = str(error)

        self._draw_parts(ui, app, key, data, new, x, TOP + 122)
        self._draw_applies(ui, app, key, data, new, x, TOP + 122 + 46 + self.PART_ROWS * ROW_H + 6)

        y = TOP + 122 + 2 * 46 + (self.PART_ROWS + self.APPLY_ROWS) * ROW_H + 14
        ui.text(describe_skill(skill, db, t), x, y, TEXT, "small", WIDTH - x - 16)
        ui.text(t("A skill belongs to the chosen classes and to whoever wears the chosen items."),
                x, y + 22, DIM, "small")
        ui.text(t("Effects apply after damage or healing; conditions are checked on each unit hit."),
                x, y + 38, DIM, "small")
        if new != data:
            apply(app, "skills", skill_id, new)

    def _draw_parts(self, ui: UI, app: EditorHost, key: Hashable, data: dict, new: dict, x: int, y: int) -> None:
        """Части урона и лечения: вид, категория, сила, два слагаемых скейла, тип урона."""
        t, db = ui.t, app.db
        parts = data["parts"]
        ui.text(t("Damage and healing parts: {n}", n=len(parts)), x, y + 4, font="small")
        if ui.button(t("+ Add part"), pygame.Rect(x + 250, y, 150, 22)):
            new["parts"] = parts + [new_part()]
        cols = (("kind", 22), ("category", 96), ("power", 190), ("scales from", 240), ("and from", 382),
                ("damage type", 524), ("weapon", 648))
        for label, offset in cols:
            ui.text(t(label), x + offset, y + 26, DIM, "small")
        y += 44
        area = pygame.Rect(x, y - 2, WIDTH - x - 16, self.PART_ROWS * ROW_H)
        pygame.draw.rect(ui.screen, PANEL, area)
        offset = ui.scroll((key, "parts"), area, len(parts), self.PART_ROWS)
        stat_choices = plain(ui, (s.value for s in SCALING_STATS))
        for row, index in enumerate(range(offset, min(len(parts), offset + self.PART_ROWS))):
            part = parts[index]
            edited = copy.deepcopy(part)
            ry, pkey = y + row * ROW_H, (key, "part", index)
            ui.text(f"{index + 1}.", x + 4, ry + 4, DIM, "small")
            picked = ui.dropdown((pkey, "kind"), pygame.Rect(x + 22, ry, 70, 24), plain(ui, PART_KINDS), part["kind"])
            if picked is not None:
                edited["kind"] = picked
            picked = ui.dropdown((pkey, "category"), pygame.Rect(x + 96, ry, 90, 24), plain(ui, CATEGORIES),
                                 part["category"])
            if picked is not None:
                edited["category"] = picked
            value = ui.number_input((pkey, "power"), pygame.Rect(x + 190, ry, 46, 24), part["power"], 0, 20, False)
            if value is not None:
                edited["power"] = value
            scaling = [dict(s) for s in part["scaling"]]
            for n, sx in ((0, 240), (1, 382)):
                term = scaling[n] if n < len(scaling) else None
                choices = stat_choices if n == 0 else [(EMPTY, "-"), *stat_choices]
                picked = ui.dropdown((pkey, "stat", n), pygame.Rect(x + sx, ry, 92, 24), choices,
                                     term["stat"] if term else EMPTY)
                if picked is not None:
                    if picked == EMPTY:
                        scaling = scaling[:n] + scaling[n + 1:]
                    elif term is None:
                        scaling.append({"stat": picked, "coef": 1.0})
                    else:
                        term["stat"] = picked
                coef = ui.number_input((pkey, "coef", n), pygame.Rect(x + sx + 96, ry, 42, 24),
                                       term["coef"] if term else 0, 0, 20, False)
                if coef is not None and term is not None:
                    term["coef"] = coef
            edited["scaling"] = scaling
            tags = ui.multiselect((pkey, "tags"), pygame.Rect(x + 524, ry, 120, 24),
                                  tag_options(ui, db, TAG_DAMAGE), part["tags"])
            if tags is not None:
                edited["tags"] = tags
            is_damage = part["kind"] == PART_DAMAGE
            if ui.button(t("yes") if part["weapon_tags"] else t("no"), pygame.Rect(x + 648, ry, 62, 24),
                         part["weapon_tags"], enabled=is_damage):
                edited["weapon_tags"] = not part["weapon_tags"]
            if ui.button("x", pygame.Rect(x + 716, ry, 24, 24), color=RED):
                new["parts"] = parts[:index] + parts[index + 1:]
            elif edited != part:
                new["parts"] = parts[:index] + [edited] + parts[index + 1:]

    def _draw_applies(self, ui: UI, app: EditorHost, key: Hashable, data: dict, new: dict, x: int, y: int) -> None:
        """Накладываемые эффекты: эффект, получатель, условие на цель."""
        t, db = ui.t, app.db
        applies = data["applies"]
        ui.text(t("Effects: {n}", n=len(applies)), x, y + 4, font="small")
        if ui.button(t("+ Add effect"), pygame.Rect(x + 250, y, 150, 22), enabled=bool(db.effects)):
            new["applies"] = applies + [default_apply(db, next(iter(db.effects)))]
        for label, offset in (("effect", 22), ("goes to", 236), ("if target", 330)):
            ui.text(t(label), x + offset, y + 26, DIM, "small")
        y += 44
        area = pygame.Rect(x, y - 2, WIDTH - x - 16, self.APPLY_ROWS * ROW_H)
        pygame.draw.rect(ui.screen, PANEL, area)
        offset = ui.scroll((key, "applies"), area, len(applies), self.APPLY_ROWS)
        effect_choices = [(e.id, f"{t(e.name)} [{', '.join(t(tag) for tag in sorted(e.tags))}]")
                          for e in db.effects.values()]
        for row, index in enumerate(range(offset, min(len(applies), offset + self.APPLY_ROWS))):
            item = applies[index]
            edited = copy.deepcopy(item)
            ry, akey = y + row * ROW_H, (key, "apply", index)
            ui.text(f"{index + 1}.", x + 4, ry + 4, DIM, "small")
            picked = ui.dropdown((akey, "effect"), pygame.Rect(x + 22, ry, 210, 24), effect_choices, item["effect_id"])
            if picked is not None and picked != item["effect_id"]:
                # Получатель подстраивается под знак эффекта: бафф на себя, дебафф на цель.
                edited.update(default_apply(db, picked), condition=item["condition"])
            picked = ui.dropdown((akey, "to"), pygame.Rect(x + 236, ry, 90, 24), plain(ui, APPLY_RECIPIENTS), item["to"])
            if picked is not None:
                edited["to"] = picked
            condition = condition_widgets(ui, db, akey, item["condition"], x + 330, ry, 130, 130)
            if condition is not None:
                edited["condition"] = condition
            if ui.button("x", pygame.Rect(x + 716, ry, 24, 24), color=RED):
                new["applies"] = applies[:index] + applies[index + 1:]
            elif edited != item:
                new["applies"] = applies[:index] + [edited] + applies[index + 1:]
