"""Окно бесконечной башни (pygame-ce). Запуск: python tower.py

Отдельная программа, не вкладка демо: свой забег (saves/tower.json), общий справочник data/.
Перед каждым боем и по F5 справочник, правила башни (data/tower.json) и визуал навыков
перечитываются с диска, поэтому правки, сделанные в открытом рядом окне демо, сразу в игре.

Экран зависит от фазы забега: набор бойцов, подготовка (расстановка, снаряжение, тактики),
бой этажа на сцене (2.5D), награда, магазин, конец забега.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional, Union

import pygame

from engine.scene import SCENES_DIR, SceneStore
from game.database import Database
from game.editing import set_tactics
from game.i18n import Translator, available_languages
from game.stats import ModOp, Stat
from game.tower import (DEFAULT_SAVE_PATH, DRAFT, OVER, PREPARE, REWARD, SHOP, TOWER_RULES_PATH, TowerRules,
                        TowerRun)
from game.unit import Unit
from pygame_battle import SKIP_BACKLOG_MS, BattleView
from pygame_editors import ROW_H, rule_table
from pygame_stage import TOWER_MODE, StageScreen, load_visuals
from pygame_ui import (BG, DIM, GREEN, HEIGHT, PANEL, RED, SLOT, TEXT, UI, WIDTH, YELLOW, Window, fit,
                       load_fonts)

FPS = 60
AUTO_STEP_MS = 600
SPEEDS = (1, 2, 4)                       # клавиши 1, 2, 3
TOP = 36                                 # под верхней строкой
NONE_ITEM = "__none__"                   # в списке снаряжения: снять предмет
TIER_COLORS = {1: (200, 200, 200), 2: (110, 170, 255), 3: (255, 170, 60)}
TIER_MARKS = {1: "I", 2: "II", 3: "III"}
SIDE_FILL = (44, 62, 92)
SELECTED_FILL = (70, 96, 140)

# Подготовка: поле отряда слева, юнит справа
GRID_X, GRID_Y, GRID_W, GRID_H = 16, TOP + 40, 450, 252
RESERVE_Y = GRID_Y + GRID_H + 30
SIDE_X = 492
CARD_W = 310


def tier_color(tier: int) -> tuple[int, int, int]:
    return TIER_COLORS.get(tier, YELLOW)


def item_title(t: Any, db: Database, item_id: str) -> str:
    item = db.items.get(item_id)
    return f"{t(item.name)} [{TIER_MARKS.get(item.tier, item.tier)}]" if item else item_id


def item_stats(t: Any, db: Database, item_id: str) -> str:
    """Модификаторы предмета одной строкой: «Физ. атака +5, Блок +10»."""
    item = db.items.get(item_id)
    if item is None:
        return ""
    parts = []
    for mod in item.modifiers:
        if mod.op is ModOp.FLAT:
            value = f"{mod.value:+g}"
        elif mod.op is ModOp.PERCENT_ADD:
            value = f"{mod.value * 100:+g}%"
        else:
            value = f"x{mod.value:g}"
        parts.append(f"{t(mod.stat.value)} {value}")
    parts += [t(db.skills[s].name) for s in item.skills if s in db.skills]
    parts += [t(db.passives[p].name) for p in item.passives if p in db.passives]
    return ", ".join(parts)


class TowerApp:
    """Забег, справочник, сцена боя и состояние экранов."""

    def __init__(self, save_path: Union[str, Path, None] = DEFAULT_SAVE_PATH, data_dir: Union[str, Path, None] = None,
                 rules_path: Union[str, Path] = TOWER_RULES_PATH, scenes_dir: Optional[Path] = SCENES_DIR,
                 props_dir: Optional[Path] = None, lang: Optional[str] = None, seed: Optional[int] = None):
        """seed: случайность новых забегов (тесты); None — каждый забег свой."""
        self.seed = seed
        self.save_path = Path(save_path) if save_path else None
        self.data_dir, self.rules_path = data_dir, rules_path
        self.db = Database.load(data_dir)
        self.rules = TowerRules.load(rules_path)
        self.t = Translator()
        self.resolution: tuple[int, int] = (WIDTH, HEIGHT)
        self.message = ""
        self.run = self._load(lang)
        self.store = SceneStore(scenes_dir or SCENES_DIR)
        self.stage = StageScreen(None, props_dir)
        self.stage.mode = TOWER_MODE
        self.stage.on_return = self.finish_battle
        self.scenario: Any = None          # бой этажа, который идёт сейчас
        self.in_battle = False
        self.paused = False
        self.speed = 1
        self.clock = 0                     # время боя: идёт быстрее при ускорении, стоит на паузе
        self.last_step = 0
        self.selected: Optional[int] = None    # выбранный юнит на подготовке
        self.tactics = False                   # подготовка: показана таблица тактики выбранного
        self.picks: list[int] = []             # отмеченные предметы награды
        self.confirm_new = False               # «Новый забег» нажат один раз
        self._enemies: Any = None              # (этаж, справочник, враги этажа)

    # --- сохранение ---

    def _load(self, lang: Optional[str]) -> TowerRun:
        run, settings = None, {}
        if self.save_path and self.save_path.exists():
            try:
                data = json.loads(self.save_path.read_text(encoding="utf-8"))
                settings = data.get("settings", {})
                run = TowerRun.from_dict(self.db, self.rules, data)
            except (OSError, ValueError, KeyError, TypeError) as error:
                self.message = f"save ignored ({error})"
        lang = lang or settings.get("language")
        if lang in available_languages():
            self.t = Translator.load(lang)
        if settings.get("resolution"):
            self.resolution = tuple(settings["resolution"])
        return run or TowerRun.new(self.db, self.rules, seed=self.seed)

    def save(self) -> None:
        if not self.save_path:
            return
        data = self.run.to_dict()
        data["settings"] = {"language": self.t.lang, "resolution": list(self.resolution)}
        try:
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            self.save_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as error:
            self.message = f"{self.t('cannot save')}: {error}"

    def reload(self) -> bool:
        """Перечитать справочник, правила башни и визуал навыков; забег пересобирается по ним."""
        try:
            db = Database.load(self.data_dir)
            rules = TowerRules.load(self.rules_path)
            run = self.run.rebuild(db, rules)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.message = self.t("data not reloaded: {error}", error=error)
            return False
        self.db, self.rules, self.run = db, rules, run
        self.stage.skill_visuals = load_visuals()
        self._enemies = None
        return True

    def act(self, action: Any, *args: Any) -> Any:
        """Действие забега; ошибку (не хватает золота, поле полно) показывает сообщением."""
        try:
            result = action(*args)
        except ValueError as error:
            self.message = self.t(str(error))
            return None
        self.message = ""
        self.save()
        return result

    def new_run(self) -> None:
        self.run = TowerRun.new(self.db, self.rules, best=self.run.best, seed=self.seed)
        self.selected, self.tactics, self.picks, self.confirm_new = None, False, [], False
        self.message = ""
        self.save()

    def next_language(self) -> None:
        languages = available_languages()
        self.t = Translator.load(languages[(languages.index(self.t.lang) + 1) % len(languages)])
        self.save()

    def enemies(self) -> list:
        """Враги текущего этажа (для показа на подготовке); считаются раз на этаж."""
        key = (self.run.floor, id(self.db), self.run.seed)
        if self._enemies is None or self._enemies[0] != key:
            self._enemies = (key, self.run.enemy_roster(self.db))
        return self._enemies[1]

    # --- бой ---

    def start_battle(self) -> None:
        self.reload()
        try:
            self.scenario = self.run.battle(self.db)
        except ValueError as error:
            self.message = self.t(str(error))
            return
        scene_id = self.rules.scene(self.run.floor)
        if scene_id in self.store.ids():
            self.stage.set_scene(self.store.load(scene_id))
        seed = self.run.seed + self.run.floor * 7919
        self.stage.battle_view = BattleView(self.db, seed, lambda: self.scenario, self.stage.windup)
        self.in_battle, self.paused, self.message = True, False, ""
        self.last_step = self.clock

    def tick(self, dt: int) -> None:
        """Время боя и автоматические ходы: следующий ход, когда эффекты прошлого доиграли."""
        if not self.in_battle:
            return
        view = self.stage.battle_view
        if not self.paused:
            self.clock += dt * self.speed
            ready = self.clock - self.last_step >= AUTO_STEP_MS and self.clock >= view.busy_until
            if not view.sim.finished and ready:
                view.step(self.clock)
                self.last_step = self.clock
        view.prune(self.clock)

    def skip(self) -> None:
        """Доиграть бой сразу: сцена перескакивает к итогу без анимаций."""
        view = self.stage.battle_view
        mark = len(view.sim.events)
        view.sim.run()
        view.consume(view.sim.events[mark:], self.clock)
        self.clock = view.busy_until + SKIP_BACKLOG_MS + 1
        self.last_step = self.clock

    def finish_battle(self) -> None:
        """Enter после боя: итог в забег, дальше награда или конец."""
        view = self.stage.battle_view
        if not self.in_battle or view is None or not view.sim.finished:
            return
        won = view.sim.winner_id == view.sim.attacker.id
        self.run.finish(self.db, self.scenario, won)
        self.in_battle, self.scenario, self.picks = False, None, []
        self.save()

    def handle_key(self, key: int) -> None:
        if key == pygame.K_F5:
            if not self.in_battle and self.reload():
                self.message = self.t("data reloaded")
        elif not self.in_battle:
            return
        elif key == pygame.K_SPACE:
            self.paused = not self.paused
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.speed = SPEEDS[key - pygame.K_1]
        elif key == pygame.K_s and not self.stage.battle_view.sim.finished:
            self.skip()

    # --- снаряжение ---

    def change_equipment(self, unit: Unit, slot_index: int, item_id: str) -> None:
        inventory = self.run.inventory
        if item_id == NONE_ITEM:
            self.act(inventory.unequip, unit, slot_index)
        else:
            self.act(inventory.equip, unit, slot_index, item_id)


# --- отрисовка -----------------------------------------------------------------

def draw_top(ui: UI, app: TowerApp) -> None:
    t, run = ui.t, app.run
    title = t("Tower — floor {n}", n=run.floor)
    if app.rules.is_boss(run.floor):
        title += "  " + t("(boss)")
    ui.text(title, 12, 8, YELLOW if app.rules.is_boss(run.floor) else TEXT)
    ui.text(t("gold {n}", n=run.inventory.gold), 300, 8, YELLOW)
    ui.text(t("best floor {n}", n=run.best), 420, 8, DIM)
    if ui.button(t("Reload data (F5)"), pygame.Rect(WIDTH - 404, 4, 150, 24), enabled=not app.in_battle):
        if app.reload():
            app.message = t("data reloaded")
    label = t("Sure? Click again") if app.confirm_new else t("New run")
    if ui.button(label, pygame.Rect(WIDTH - 246, 4, 180, 24), enabled=not app.in_battle,
                 color=RED if app.confirm_new else TEXT):
        if app.confirm_new or app.run.phase == OVER:
            app.new_run()
        else:
            app.confirm_new = True
    if ui.button(app.t.lang.upper(), pygame.Rect(WIDTH - 58, 4, 50, 24)):
        app.next_language()


def unit_lines(t: Any, db: Database, unit: Unit) -> list[tuple[str, Any]]:
    """Навыки и пассивки класса с уровнем открытия: закрытые тусклые."""
    definition, level = unit.definition, unit.state.level
    lines = []
    for ids, levels, section, mark in ((definition.skills, definition.skill_levels, db.skills, ""),
                                       (definition.passives, definition.passive_levels, db.passives, "* ")):
        for entry in ids:
            need = levels.get(entry, 1)
            name = t(section[entry].name) if entry in section else entry
            if need <= level:
                lines.append((mark + name, TEXT))
            else:
                lines.append((mark + name + "  " + t("lv {n}", n=need), DIM))
    return lines


def draw_stats(ui: UI, unit: Unit, x: int, y: int, columns: int = 2, width: int = 240) -> int:
    t = ui.t
    stats = list(Stat)
    rows = (len(stats) + columns - 1) // columns
    for i, stat in enumerate(stats):
        cx, cy = x + (i // rows) * width, y + (i % rows) * 17
        ui.text(t(stat.value), cx, cy, DIM, "small", width - 56)
        ui.text(str(unit.stat(stat)), cx + width - 52, cy, TEXT, "small")
    return y + rows * 17


def draw_class_card(ui: UI, app: TowerApp, class_id: str, rect: pygame.Rect) -> bool:
    """Карточка класса при наборе. True — взяли."""
    t, db, run = ui.t, app.db, app.run
    level = app.rules.data["draft"]["level"]
    unit = db.create_unit(class_id, 0, level, run.starter_gear(db, class_id))
    pygame.draw.rect(ui.screen, PANEL, rect)
    pygame.draw.rect(ui.screen, DIM, rect, 1)
    x, y = rect.x + 10, rect.y + 8
    ui.text(t(unit.name), x, y, YELLOW, "big")
    tags = ", ".join(t(db.tags[tag].name) for tag in unit.definition.tags if tag in db.tags)
    ui.text(f"{t('lv {n}', n=level)}   {tags}", x, y + 30, DIM, "small", rect.width - 20)
    y = draw_stats(ui, unit, x, y + 52, 2, (rect.width - 20) // 2) + 6
    ui.text(t("Equipment"), x, y, DIM, "small")
    for item_id in unit.state.equipment:
        if item_id is not None:
            y += 16
            ui.text(item_title(t, db, item_id), x + 8, y, tier_color(db.items[item_id].tier), "small", rect.width - 30)
    y += 22
    ui.text(t("Skills (* passive)"), x, y, DIM, "small")
    for text, color in unit_lines(t, db, unit):
        y += 16
        if y > rect.bottom - 56:
            break
        ui.text(text, x + 8, y, color, "small", rect.width - 30)
    return bool(ui.button(t("Take"), pygame.Rect(rect.x + 10, rect.bottom - 36, rect.width - 20, 28)))


def draw_draft(ui: UI, app: TowerApp) -> None:
    t, run = ui.t, app.run
    total = app.rules.data["draft"]["picks"]
    ui.text(t("Choose a fighter {n}/{total}", n=len(run.army.units) + 1, total=total), 16, TOP + 6, TEXT, "big")
    for i, class_id in enumerate(list(run.offers)):
        rect = pygame.Rect(16 + i * (CARD_W + 16), TOP + 44, CARD_W, HEIGHT - TOP - 110)
        if draw_class_card(ui, app, class_id, rect):
            app.act(run.pick, app.db, class_id)
    taken = ", ".join(f"{t(u.name)}" for u in run.army.units.values())
    ui.text(t("Taken: {list}", list=taken or "-"), 16, HEIGHT - 56, DIM)


def cell_rect(app: TowerApp, row: int, col: int) -> pygame.Rect:
    """Передний ряд справа (ближе к врагу), колонны формации — по вертикали."""
    formation = app.run.squad.formation
    cell_w, cell_h = GRID_W // formation.rows, GRID_H // formation.cols
    x = GRID_X + (formation.rows - 1 - row) * cell_w
    return pygame.Rect(x + 3, GRID_Y + col * cell_h + 3, cell_w - 6, cell_h - 6)


def draw_unit_cell(ui: UI, unit: Unit, rect: pygame.Rect, selected: bool) -> None:
    t = ui.t
    pygame.draw.rect(ui.screen, SELECTED_FILL if selected else SIDE_FILL, rect)
    pygame.draw.rect(ui.screen, YELLOW if selected else DIM, rect, 2 if selected else 1)
    ui.text(t(unit.name), rect.x + 6, rect.y + 5, TEXT, "small", rect.width - 12)
    ui.text(t("lv {n}", n=unit.state.level), rect.x + 6, rect.y + 22, DIM, "small")
    ui.text(f"HP {unit.max_hp}", rect.x + 6, rect.y + 39, DIM, "small")


def draw_prepare(ui: UI, app: TowerApp) -> None:
    t, run, db = ui.t, app.run, app.db
    units = {u.uid: u for u in run.army.units.values()}
    if app.selected not in units:
        app.selected = run.fielded[0].uid if run.fielded else next(iter(units), None)
    if app.tactics and app.selected is not None:
        draw_tactics(ui, app, units[app.selected])
        return
    formation = run.squad.formation
    ui.text(t("Fielded {n}/{max}", n=len(formation), max=formation.max_units), GRID_X, TOP + 6)
    ui.text(t("front"), GRID_X + GRID_W - 60, TOP + 6, DIM, "small")
    shop_in = next(k for k in range(1, 1000) if app.rules.shop_after(run.floor + k - 1)) \
        if app.rules.data["shop"]["every"] > 0 else None
    if shop_in is not None:
        ui.text(t("shop after {n} more floor(s)", n=shop_in), GRID_X + 150, TOP + 6, DIM, "small")
    for row in range(formation.rows):
        for col in range(formation.cols):
            rect = cell_rect(app, row, col)
            unit = formation.unit_at(row, col)
            if unit is None:
                pygame.draw.rect(ui.screen, SLOT, rect)
                pygame.draw.rect(ui.screen, DIM, rect, 1)
            else:
                draw_unit_cell(ui, unit, rect, unit.uid == app.selected)
            click = ui.clicked(rect)
            if not click:
                continue
            selected = app.selected
            if unit is None:
                if selected is not None:
                    app.act(run.place, selected, row, col)           # в пустую клетку
            elif selected is None or selected == unit.uid:
                app.selected = unit.uid
            elif formation.position_of(selected) is None or click < 0:
                app.act(run.place, selected, row, col)               # из запаса — на его место; правый клик — обмен
            else:
                app.selected = unit.uid

    ui.text(t("click: select, move to an empty cell; right click: swap"), GRID_X, GRID_Y + GRID_H + 2, DIM, "small")
    ui.text(t("Reserve (click a unit, then a cell)"), GRID_X, RESERVE_Y - 8, DIM, "small")
    for i, unit in enumerate(run.reserve):
        rect = pygame.Rect(GRID_X + (i % 3) * 152, RESERVE_Y + (i // 3) * 28, 146, 24)
        label = f"{t(unit.name)} {t('lv {n}', n=unit.state.level)}"
        if ui.button(label, rect, selected=unit.uid == app.selected):
            app.selected = unit.uid

    # Враги этажа
    ey = HEIGHT - 128
    ui.text(t("Enemies of floor {n}", n=run.floor), GRID_X, ey, DIM, "small")
    enemies = app.enemies()
    text = ", ".join(f"{t(db.units[c].name)} {lv}" for c, lv, *_ in enemies if c in db.units)
    ui.text(text, GRID_X, ey + 18, RED if app.rules.is_boss(run.floor) else TEXT, "small", SIDE_X - GRID_X - 16)
    if ui.button(t("Fight! (floor {n})", n=run.floor), pygame.Rect(GRID_X, HEIGHT - 82, 220, 34),
                 enabled=bool(run.fielded), font="main", color=YELLOW):
        app.start_battle()

    if app.selected is not None:
        draw_unit_panel(ui, app, units[app.selected])


def draw_unit_panel(ui: UI, app: TowerApp, unit: Unit) -> None:
    """Выбранный юнит: уровень и опыт, статы, снаряжение из инвентаря, навыки, инвентарь."""
    t, db, run = ui.t, app.db, app.run
    x, y = SIDE_X, TOP + 4
    panel = pygame.Rect(x - 8, TOP, WIDTH - x, HEIGHT - TOP - 30)
    pygame.draw.rect(ui.screen, PANEL, panel)
    ui.text(f"{t(unit.name)}  {t('lv {n}', n=unit.state.level)}", x, y, YELLOW)
    need = app.rules.exp.per_level
    ui.text(t("exp {n}/{need}", n=unit.state.exp, need=need), x + 220, y + 2, DIM, "small")
    bar = pygame.Rect(x + 330, y + 4, 150, 10)
    pygame.draw.rect(ui.screen, SLOT, bar)
    pygame.draw.rect(ui.screen, GREEN, (bar.x, bar.y, round(bar.width * min(1, unit.state.exp / need)), bar.height))
    fielded = run.squad.formation.position_of(unit.uid) is not None
    if ui.button(t("To reserve") if fielded else t("In reserve"), pygame.Rect(x, y + 24, 110, 22), enabled=fielded):
        app.act(run.bench, unit.uid)
    if ui.button(t("Tactics"), pygame.Rect(x + 116, y + 24, 110, 22)):
        app.tactics = True
    y = draw_stats(ui, unit, x, y + 54, 2, 240) + 8

    # Снаряжение: подходящие предметы из инвентаря
    inventory = run.inventory
    for slot_index, slot in enumerate(unit.definition.slots):
        rect = pygame.Rect(x + (slot_index % 2) * 244, y + (slot_index // 2) * 28, 238, 24)
        current = unit.state.equipment[slot_index]
        fits = [i for i, n in inventory.items.items() if n > 0 and i in db.items and db.items[i].slot == slot]
        options = [(NONE_ITEM, f"- {t(slot)}")] + [(i, f"{item_title(t, db, i)} x{inventory.count(i)}") for i in fits]
        if current is not None:
            options.append((current, item_title(t, db, current)))
        color = tier_color(db.items[current].tier) if current in db.items else DIM
        picked = ui.dropdown(("tower-slot", unit.uid, slot_index), rect, options,
                             current if current is not None else NONE_ITEM, color)
        if picked is not None and picked != (current if current is not None else NONE_ITEM):
            app.change_equipment(unit, slot_index, picked)
    y += ((len(unit.definition.slots) + 1) // 2) * 28 + 6

    ui.text(t("Skills (* passive)"), x, y, DIM, "small")
    lines = unit_lines(t, db, unit) + [(f"+ {t(db.skills[s].name)}", GREEN) for item in unit.equipped
                                       for s in item.skills if s in db.skills]
    for i, (text, color) in enumerate(lines[:12]):
        ui.text(text, x + (i % 2) * 244, y + 18 + (i // 2) * 16, color, "small", 236)
    y += 18 + ((min(len(lines), 12) + 1) // 2) * 16 + 8

    ui.text(t("Inventory"), x, y, DIM, "small")
    items = [(i, n) for i, n in sorted(inventory.items.items()) if n > 0 and i in db.items]
    rows = max(1, (HEIGHT - 40 - y - 18) // 16)
    for i, (item_id, count) in enumerate(items[:rows * 2]):
        text = f"{item_title(t, db, item_id)} x{count}"
        ui.text(text, x + (i % 2) * 244, y + 18 + (i // 2) * 16, tier_color(db.items[item_id].tier), "small", 236)


def draw_tactics(ui: UI, app: TowerApp, unit: Unit) -> None:
    t, db = ui.t, app.db
    x = 16
    ui.text(t("Tactics of {unit}", unit=f"{t(unit.name)} {t('lv {n}', n=unit.state.level)}"), x, TOP + 6, YELLOW)
    ui.text(t("Rules are checked top to bottom: the first one whose conditions hold,"), x, TOP + 28, DIM, "small")
    ui.text(t("with a valid target and enough AP, is used. Otherwise: Attack, if AP allows."), x, TOP + 44, DIM, "small")
    rules = unit.tactics.to_list()
    new_rules = rule_table(ui, db, ("tower-tactics", unit.uid), rules, unit.skill_ids, x, TOP + 68)
    y = TOP + 88 + len(rules) * ROW_H + 4
    if ui.button(t("Reset to default"), pygame.Rect(x + 192, y, 200, 24), enabled=unit.has_custom_tactics):
        unit.reset_tactics()
        app.save()
    elif new_rules is not None:
        try:
            set_tactics(db, unit, new_rules)
            app.save()
        except (ValueError, KeyError) as error:
            app.message = str(error)
    if ui.button(t("Back"), pygame.Rect(x, HEIGHT - 70, 160, 28)):
        app.tactics = False


def draw_item_row(ui: UI, app: TowerApp, item_id: str, rect: pygame.Rect, selected: bool = False) -> None:
    t, db = ui.t, app.db
    item = db.items.get(item_id)
    pygame.draw.rect(ui.screen, SELECTED_FILL if selected else PANEL, rect)
    pygame.draw.rect(ui.screen, YELLOW if selected else DIM, rect, 2 if selected else 1)
    if item is None:
        ui.text(item_id, rect.x + 8, rect.y + 6, DIM, "small")
        return
    ui.text(item_title(t, db, item_id), rect.x + 8, rect.y + 5, tier_color(item.tier), "main", rect.width - 16)
    wearers = [t(u.name) for u in db.units.values() if item.slot in u.slots]
    ui.text(f"{t(item.slot)}: {item_stats(t, db, item_id)}", rect.x + 8, rect.y + 25, TEXT, "small", rect.width - 16)
    who = t("any class") if len(wearers) == len(db.units) else ", ".join(wearers)
    ui.text(who, rect.x + 8, rect.y + 41, DIM, "small", rect.width - 16)


def draw_reward(ui: UI, app: TowerApp) -> None:
    t, run, db = ui.t, app.run, app.db
    report = run.report
    floor = report.floor if report else run.floor
    ui.text(t("Floor {n} cleared!", n=floor), 16, TOP + 6, GREEN, "big")
    if report:
        ui.text(t("+{n} gold", n=report.gold), 16, TOP + 40, YELLOW)
        y = TOP + 70
        for up in report.level_ups:
            unit = run.army.units.get(up.uid)
            if unit is None:
                continue
            text = f"{t(unit.name)}: +{up.exp} {t('exp')}"
            if up.levels:
                text += "   " + t("level {a} -> {b}", a=up.old_level, b=up.new_level)
            ui.text(text, 16, y, YELLOW if up.levels else TEXT, "small", 440)
            y += 18
            for new in [t(db.skills[s].name) for s in up.skills if s in db.skills] + \
                       [t(db.passives[p].name) for p in up.passives if p in db.passives]:
                ui.text(t("new: {name}", name=new), 32, y, GREEN, "small", 420)
                y += 16
            y += 4
    take = app.rules.data["reward"]["take"]
    ui.text(t("Choose up to {n} items", n=take), SIDE_X, TOP + 6)
    for i, item_id in enumerate(run.reward):
        rect = pygame.Rect(SIDE_X, TOP + 32 + i * 66, WIDTH - SIDE_X - 16, 60)
        draw_item_row(ui, app, item_id, rect, i in app.picks)
        if ui.clicked(rect):
            if i in app.picks:
                app.picks.remove(i)
            elif len(app.picks) < take:
                app.picks.append(i)
    label = t("Take ({n}/{take}) and go on", n=len(app.picks), take=take)
    if ui.button(label, pygame.Rect(SIDE_X, HEIGHT - 70, 300, 32), font="main", color=YELLOW):
        app.act(run.take, db, list(app.picks))
        app.picks = []


def draw_shop(ui: UI, app: TowerApp) -> None:
    t, run, db, rules = ui.t, app.run, app.db, app.rules
    ui.text(t("Shop"), 16, TOP + 6, YELLOW, "big")
    ui.text(t("Recruits"), 16, TOP + 40, DIM, "small")
    for i, offer in enumerate(run.recruits):
        rect = pygame.Rect(16, TOP + 58 + i * 100, 300, 92)
        pygame.draw.rect(ui.screen, PANEL, rect)
        pygame.draw.rect(ui.screen, DIM, rect, 1)
        if offer is None or offer[0] not in db.units:
            ui.text(t("hired"), rect.x + 10, rect.y + 8, DIM)
            continue
        class_id, level = offer
        definition = db.units[class_id]
        ui.text(f"{t(definition.name)}  {t('lv {n}', n=level)}", rect.x + 10, rect.y + 6, TEXT)
        names = [t(db.skills[s].name) for s in definition.skills_at(level) if s in db.skills]
        ui.text(", ".join(names), rect.x + 10, rect.y + 28, DIM, "small", rect.width - 20)
        price = rules.recruit_price(level)
        if ui.button(t("Hire for {n}", n=price), pygame.Rect(rect.x + 10, rect.bottom - 32, 160, 24),
                     enabled=run.inventory.gold >= price):
            app.act(run.hire, db, i)

    ui.text(t("Goods"), 332, TOP + 40, DIM, "small")
    for i, item_id in enumerate(run.shop_items):
        rect = pygame.Rect(332, TOP + 58 + i * 66, 360, 60)
        if item_id is None:
            pygame.draw.rect(ui.screen, PANEL, rect)
            ui.text(t("sold"), rect.x + 8, rect.y + 8, DIM)
            continue
        draw_item_row(ui, app, item_id, rect)
        price = db.items[item_id].price if item_id in db.items else 0
        if ui.button(t("Buy {n}", n=price), pygame.Rect(rect.right - 92, rect.y + 4, 86, 22),
                     enabled=run.inventory.gold >= price):
            app.act(run.buy, db, i)

    ui.text(t("Sell"), 708, TOP + 40, DIM, "small")
    items = [(i, n) for i, n in sorted(run.inventory.items.items()) if n > 0 and i in db.items]
    area = pygame.Rect(708, TOP + 58, WIDTH - 724, HEIGHT - TOP - 150)
    rows = area.height // 26
    offset = ui.scroll("tower-sell", area, len(items), rows)
    for row, (item_id, count) in enumerate(items[offset:offset + rows]):
        ry = area.y + row * 26
        ui.text(f"{item_title(t, db, item_id)} x{count}", area.x, ry + 4, tier_color(db.items[item_id].tier),
                "small", area.width - 76)
        if ui.button(f"+{rules.sell_price(db, item_id)}", pygame.Rect(area.right - 70, ry, 70, 22)):
            app.act(run.sell, db, item_id)

    price = rules.reroll_price(run.rerolls)
    if ui.button(t("New goods for {n}", n=price), pygame.Rect(16, HEIGHT - 70, 220, 32),
                 enabled=run.inventory.gold >= price):
        app.act(run.reroll, db)
    if ui.button(t("Leave the shop"), pygame.Rect(252, HEIGHT - 70, 220, 32), font="main", color=YELLOW):
        app.act(run.leave_shop)


def draw_over(ui: UI, app: TowerApp) -> None:
    t, run = ui.t, app.run
    ui.text(t("Defeat on floor {n}", n=run.floor), 16, TOP + 40, RED, "big")
    ui.text(t("Floors cleared: {n}   best: {best}", n=run.floor - 1, best=run.best), 16, TOP + 80)
    for i, unit in enumerate(run.army.units.values()):
        ui.text(f"{t(unit.name)}  {t('lv {n}', n=unit.state.level)}", 16, TOP + 120 + i * 20, DIM, "small")
    if ui.button(t("New run"), pygame.Rect(16, HEIGHT - 80, 220, 34), font="main", color=YELLOW):
        app.new_run()


SCREENS = {DRAFT: draw_draft, PREPARE: draw_prepare, REWARD: draw_reward, SHOP: draw_shop, OVER: draw_over}


def draw_frame(ui: UI, app: TowerApp, window: Optional[Window] = None) -> None:
    """Кадр в ui.screen; с окном (window) поле боя рисуется прямо в окно в полном разрешении."""
    ui.t = app.t
    ui.screen.fill(BG)
    if app.in_battle:
        stage = app.stage
        stage.native = window is not None
        stage.draw_battle(ui, stage.battle_view, not app.paused, app.clock)
        state = t_battle(ui, app)
        ui.text(state, 12, 8, YELLOW if app.paused else TEXT)
    else:
        draw_top(ui, app)
        SCREENS[app.run.phase](ui, app)
    if app.message:
        ui.text(fit(ui.fonts["small"], app.message, WIDTH - 32), 16, HEIGHT - 22, YELLOW, "small")
    ui.end()
    if window is not None:
        window.present()
        if app.in_battle:
            app.stage.draw_field(window.surface, app.clock, app.stage.camera(window.scale, window.offset))
            if ui.popup is not None and ui.popup_box is not None:
                window.present(ui.popup_box)


def t_battle(ui: UI, app: TowerApp) -> str:
    t = ui.t
    state = t("paused") if app.paused else f"x{app.speed}"
    boss = "  " + t("(boss)") if app.rules.is_boss(app.run.floor) else ""
    return t("Floor {n}", n=app.run.floor) + boss + f"   {state}"


def main(max_frames: Optional[int] = None, save_path: Union[str, Path, None] = DEFAULT_SAVE_PATH,
         data_dir: Union[str, Path, None] = None, lang: Optional[str] = None) -> None:
    """max_frames нужен только для проверки запуска без окна (SDL_VIDEODRIVER=dummy)."""
    pygame.init()
    pygame.display.set_caption("Squad auto-battle — Tower")
    pygame.display.set_mode((WIDTH, HEIGHT))
    app = TowerApp(save_path, data_dir, lang=lang)
    window = Window(app.resolution)
    ui = UI(window.canvas, load_fonts())
    ui.transform = window.to_logical
    clock = pygame.time.Clock()
    frames, running = 0, True
    while running:
        dt = clock.tick(FPS)
        events = [window.logical_event(e) for e in pygame.event.get()]
        ui.begin(events)
        for event in events:
            if app.in_battle and not ui.captured:
                mouse = event.pos if hasattr(event, "pos") else ui.mouse
                app.stage.handle_event(event, mouse, window.scale)
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                window.resize(event.size)
                app.resolution = window.surface.get_size()
            elif event.type != pygame.KEYDOWN or ui.captured:
                continue
            elif event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_F12:
                window.next_size()
                app.resolution = window.surface.get_size()
            else:
                app.handle_key(event.key)
        app.tick(dt)
        draw_frame(ui, app, window)
        pygame.display.flip()
        frames += 1
        if max_frames is not None and frames >= max_frames:
            running = False
    app.save()
    pygame.quit()


if __name__ == "__main__":
    main(lang=sys.argv[1] if len(sys.argv) > 1 else None)
