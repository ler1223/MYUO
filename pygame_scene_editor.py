"""Вкладка Scene: редактор сцен боя 2.5D.

Сверху — то же поле, что на вкладке Stage (тот же бой, те же спрайты) в выбранной сцене,
поверх — подсказки текущей страницы. Снизу — страницы:
- Сцены: выбор сцены для Stage, название, новая, копия, удалить;
- Сетка: перспектива, рост, ряды и колонны формаций; кружки клеток тянутся мышью
  (вверх-вниз — глубина колонны, вбок — расстояние ряда);
- Земля: текстура в перспективе, размер плитки, глубина, дымка, цвета;
- Задник: картинка за дальним краем земли, где у неё линия земли, ширина, затемнение;
- Объекты: декорации из assets/props — добавить, выбрать кликом, тащить по земле, поднять,
  размер, отражение, слой (стоит / лежит на земле), удалить.
Каждая правка сразу записывается в assets/scenes/<id>.json.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable, Optional

import pygame

from engine.camera import Camera, ViewCamera
from engine.render import View
from engine.scene import (
    LAYERS,
    LIMITS,
    MAX_LINES,
    PROPS_DIR,
    SceneConfig,
    SceneObject,
    SceneStore,
    backdrop_files,
    ground_files,
    prop_files,
)
from pygame_battle import FIELD_RECT
from pygame_stage import StageScreen
from pygame_ui import DIM, TEXT, UI, WIDTH, YELLOW

FORM_TOP = FIELD_RECT.bottom + 8
ROW_H = 27
PAGE_W = 80
FORM_X = 8 + PAGE_W + 10
LABEL_W = 64
FIELD_W = 54
HANDLE_R = 7               # радиус ручки клетки, логические пиксели
GRAB_R = 16                # насколько близко к ручке надо нажать
GRID_COLOR = (120, 200, 255)
HORIZON_COLOR = (255, 200, 120)
PAGES = ("Scenes", "Grid", "Ground", "Backdrop", "Objects")
SIZE_LIMITS = (5, 2000)


class SceneEditor:
    """Редактор сцен. Поле рисует Stage; редактор добавляет сетку, выбор объектов и правит сцену."""

    def __init__(self, stage: StageScreen, store: SceneStore, scene_id: str,
                 on_select: Callable[[str], None] = lambda _: None, props_dir: Optional[Path] = None,
                 persist: bool = True):
        self.stage = stage
        self.store = store
        self.scene_id = scene_id
        self.on_select = on_select          # окно запоминает выбранную сцену в настройках
        self.props_dir = props_dir or PROPS_DIR
        self.persist = persist              # False: не записывать на диск
        self.page = "Grid"
        self.drag: Optional[tuple[int, int]] = None   # (ряд, колонна) перетаскиваемой ручки
        self.selected: Optional[int] = None           # выбранный объект
        self.moving: Optional[tuple[float, float]] = None   # объект тащится: сдвиг от курсора до него (x, z)
        self.new_image = ""                 # картинка для кнопки «Добавить»
        self.native = False
        self.camera_view = ViewCamera(FIELD_RECT)       # редактор показывает всё поле, без наездов

    @property
    def scene(self) -> SceneConfig:
        return self.stage.scene

    # --- изменение сцены ---

    def changed(self) -> None:
        self.scene.clamp()
        if self.persist:
            self.store.save(self.scene_id, self.scene)

    def select_scene(self, scene_id: str) -> None:
        self.scene_id = scene_id
        self.stage.set_scene(self.store.load(scene_id))
        self.selected = None
        self.on_select(scene_id)

    def formation_size(self) -> tuple[int, int]:
        view = self.stage.battle_view
        size = view.sim.attacker.formation if view is not None else None
        return (size.rows, size.cols) if size is not None else (len(self.scene.rows), len(self.scene.columns))

    def handles(self) -> dict[tuple[int, int], tuple[float, float]]:
        """Ручки клеток отряда игрока: (ряд, колонна) -> точка на поле (логические пиксели)."""
        rows, cols = self.formation_size()
        projection = self.scene.projection()
        result = {}
        for row in range(rows):
            for col in range(cols):
                x, z = self.scene.cell("left", row, col, cols)
                sx, sy, _ = projection.project(x, 0, z)
                result[(row, col)] = (sx, sy)
        return result

    def drag_to(self, cell: tuple[int, int], pos: tuple[float, float]) -> None:
        """Ручка клетки в точку pos: глубина её колонны и расстояние её ряда меняются.
        Линии за последней заданной (продолжение шага) не двигаются."""
        scene = self.scene
        ground = scene.projection().unproject(*pos)
        if ground is None:
            return
        x, z = ground
        row, col = cell
        _, cols = self.formation_size()
        index = len(scene.columns) - 1 - (cols - 1 - col)       # колонны считаются от ближней
        if 0 <= index < len(scene.columns):
            scene.columns[index] = round(max(0.0, z))
        if row < len(scene.rows):
            scene.rows[row] = round(max(0.0, -x + scene.slant * scene.column_depth(col, cols) / 100))
        scene.clamp()

    def object_at(self, pos: tuple[float, float]) -> Optional[int]:
        """Объект под точкой поля: ближние раньше дальних."""
        projection = self.scene.projection()
        view = View(projection, Camera(1.0, FIELD_RECT.topleft, FIELD_RECT.topleft), 0)
        ground = projection.unproject(*pos)
        found = []
        for i, obj in enumerate(self.scene.objects):
            if obj.layer == "upright":
                rect = self.stage.prop_rect(obj, view)
                hit = rect is not None and rect.collidepoint(pos)
            else:
                hit = ground is not None and abs(ground[0] - obj.x) <= obj.size / 2 and abs(ground[1] - obj.z) <= obj.size / 2
            if hit:
                found.append((obj.z, i))
        return min(found)[1] if found else None

    def handle_event(self, event: pygame.event.Event, pos: tuple[float, float], window_scale: float = 1.0) -> None:
        """Мышь на поле: ручки сетки (страница Сетка) и объекты (страница Объекты)."""
        down = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and FIELD_RECT.collidepoint(pos)
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.drag is not None or self.moving is not None:
                self.changed()
            self.drag, self.moving = None, None
        elif self.page == "Grid":
            if down:
                near = [(abs(hx - pos[0]) + abs(hy - pos[1]), cell) for cell, (hx, hy) in self.handles().items()]
                near = [item for item in near if item[0] <= GRAB_R * 1.5]
                self.drag = min(near)[1] if near else None
            elif event.type == pygame.MOUSEMOTION and self.drag is not None:
                self.drag_to(self.drag, pos)
        elif self.page == "Objects":
            ground = self.scene.projection().unproject(*pos)
            if down:
                self.selected = self.object_at(pos)
                if self.selected is not None and ground is not None:
                    obj = self.scene.objects[self.selected]
                    self.moving = (obj.x - ground[0], obj.z - ground[1])
            elif event.type == pygame.MOUSEMOTION and self.moving is not None and ground is not None:
                obj = self.scene.objects[self.selected]
                obj.x, obj.z = round(ground[0] + self.moving[0]), round(ground[1] + self.moving[1])
                obj.clamp()

    # --- форма ---

    def draw(self, ui: UI, app: Any) -> None:
        stage = self.stage
        if stage.battle_view is not None:
            stage.update(ui, stage.battle_view, pygame.time.get_ticks())
        t = ui.t
        for i, page in enumerate(PAGES):
            if ui.button(t(page), pygame.Rect(8, FORM_TOP + i * 22, PAGE_W, 20), selected=page == self.page):
                self.page = page
        pages = {"Scenes": self._scenes, "Grid": self._grid, "Ground": self._ground, "Backdrop": self._backdrop,
                 "Objects": self._objects}
        if pages[self.page](ui):
            self.changed()
        if not self.native:
            self.draw_field(ui.screen, pygame.time.get_ticks(), self.camera())

    def _row(self, line: int) -> int:
        return FORM_TOP + line * ROW_H

    def _number(self, ui: UI, label: str, x: int, y: int, value: float, limits: tuple[float, float],
                key: Any) -> Optional[float]:
        ui.text(ui.t(label), x, y + 5, DIM, "small")
        return ui.number_input(("scene", key), pygame.Rect(x + LABEL_W, y, FIELD_W, 24), value, *limits)

    def _fields(self, ui: UI, line: int, names: list[tuple[str, str]]) -> bool:
        """Строка числовых полей сцены (подпись, имя поля)."""
        changed, x = False, FORM_X
        for label, name in names:
            value = self._number(ui, label, x, self._row(line), getattr(self.scene, name), LIMITS[name], name)
            if value is not None:
                setattr(self.scene, name, float(value))
                changed = True
            x += LABEL_W + FIELD_W + 12
        return changed

    def _scenes(self, ui: UI) -> bool:
        t, store = ui.t, self.store
        names = store.names()
        names.setdefault(self.scene_id, self.scene.name)       # выбранной сцены может ещё не быть на диске
        ui.text(t("Active"), FORM_X, self._row(0) + 5, DIM, "small")
        picked = ui.dropdown(("scene", "pick"), pygame.Rect(FORM_X + LABEL_W, self._row(0), 220, 24),
                             sorted(names.items(), key=lambda item: item[1].casefold()), self.scene_id)
        if picked is not None and picked != self.scene_id:
            self.select_scene(picked)
            return False
        ui.text(t("Name"), FORM_X + LABEL_W + 240, self._row(0) + 5, DIM, "small")
        name = ui.text_input(("scene", "name", self.scene_id), pygame.Rect(FORM_X + LABEL_W * 2 + 240, self._row(0), 220, 24),
                             self.scene.name)
        if ui.button(t("New"), pygame.Rect(FORM_X, self._row(1), 90, 24)):
            self.select_scene(store.create(t("New scene")))
        if ui.button(t("Copy"), pygame.Rect(FORM_X + 100, self._row(1), 90, 24)):
            self.select_scene(store.create(f"{self.scene.name} 2", self.scene))
        if ui.button(t("Delete"), pygame.Rect(FORM_X + 200, self._row(1), 90, 24), enabled=len(names) > 1):
            store.delete(self.scene_id)
            self.select_scene(next(i for i in sorted(names) if i != self.scene_id))
        ui.text(t("The chosen scene is used on the Stage tab. id: {id}", id=self.scene_id), FORM_X, self._row(2) + 5,
                DIM, "small", WIDTH - FORM_X - 8)
        if name:
            self.scene.name = name
            return True
        return False

    def _grid(self, ui: UI) -> bool:
        scene, t = self.scene, ui.t
        changed = self._fields(ui, 0, [("Horizon", "horizon"), ("Ground", "ground"), ("Focal", "focal"),
                                       ("Height", "human_height"), ("Slant", "slant"), ("Fly", "fly_height")])
        for line, (name, label, limits) in enumerate((("rows", "Rows", "row"), ("columns", "Columns", "column")), 1):
            values: list[float] = getattr(scene, name)
            y, x = self._row(line), FORM_X
            ui.text(t(label), x, y + 5, DIM, "small")
            x += LABEL_W
            for i, current in enumerate(values):
                value = ui.number_input(("scene", name, i), pygame.Rect(x, y, 52, 24), current, *LIMITS[limits])
                if value is not None:
                    values[i] = float(value)
                    changed = True
                x += 56
            if ui.button("+", pygame.Rect(x, y, 24, 24), enabled=len(values) < MAX_LINES):
                values.append(scene.line(values, len(values)))
                changed = True
            if ui.button("-", pygame.Rect(x + 28, y, 24, 24), enabled=len(values) > 1):
                values.pop()
                changed = True
        ui.text(t("Drag cell handles: up/down — depth, sideways — row."), FORM_X, self._row(3) + 5, DIM, "small")
        if ui.button(t("Reset"), pygame.Rect(WIDTH - 98, self._row(3), 90, 22)):
            fresh = SceneConfig()
            for key in ("horizon", "ground", "focal", "human_height", "rows", "columns", "slant", "fly_height"):
                setattr(scene, key, getattr(fresh, key))
            changed = True
        return changed

    def _image_choice(self, ui: UI, label: str, line: int, files: list[str], current: str, key: str) -> Optional[str]:
        ui.text(ui.t(label), FORM_X, self._row(line) + 5, DIM, "small")
        options = [("", ui.t("none"))] + [(name, name) for name in files]
        picked = ui.dropdown(("scene", key), pygame.Rect(FORM_X + LABEL_W, self._row(line), 180, 24), options, current)
        return picked if picked is not None and picked != current else None

    def _color(self, ui: UI, label: str, line: int, x: int, name: str) -> bool:
        ui.text(ui.t(label), x, self._row(line) + 5, DIM, "small")
        color: list[int] = getattr(self.scene, name)
        changed = False
        for i in range(3):
            value = ui.number_input(("scene", name, i), pygame.Rect(x + LABEL_W + i * 46, self._row(line), 42, 24), color[i], 0, 255)
            if value is not None:
                color[i] = int(value)
                changed = True
        pygame.draw.rect(ui.screen, tuple(color), pygame.Rect(x + LABEL_W + 140, self._row(line) + 2, 20, 20))
        return changed

    def _ground(self, ui: UI) -> bool:
        scene = self.scene
        changed = False
        picked = self._image_choice(ui, "Texture", 0, ground_files(), scene.ground_texture, "ground_texture")
        if picked is not None:
            scene.ground_texture, changed = picked, True
        changed |= self._fields(ui, 1, [("Tile", "ground_tile"), ("Depth", "ground_depth"), ("Darken %", "ground_darken"),
                                        ("Haze %", "haze")])
        changed |= self._color(ui, "Earth", 2, FORM_X, "earth")
        changed |= self._color(ui, "Sky", 2, FORM_X + 300, "sky")
        ui.text(ui.t("Textures: assets/grounds, seamless top-down tiles."), FORM_X, self._row(3) + 5, DIM, "small")
        return changed

    def _backdrop(self, ui: UI) -> bool:
        scene = self.scene
        changed = False
        picked = self._image_choice(ui, "Image", 0, backdrop_files(), scene.backdrop, "backdrop")
        if picked is not None:
            scene.backdrop, changed = picked, True
        changed |= self._fields(ui, 1, [("Line %", "backdrop_line"), ("Width %", "backdrop_width"),
                                        ("Darken %", "backdrop_darken")])
        ui.text(ui.t("The image's ground line (Line %, from the top) sits on the far edge of the ground."),
                FORM_X, self._row(2) + 5, DIM, "small", WIDTH - FORM_X - 8)
        return changed

    def _objects(self, ui: UI) -> bool:
        t, scene = ui.t, self.scene
        files = prop_files(self.props_dir)
        changed = False
        ui.text(t("Image"), FORM_X, self._row(0) + 5, DIM, "small")
        if files:
            if self.new_image not in files:
                self.new_image = files[0]
            picked = ui.dropdown(("scene", "prop"), pygame.Rect(FORM_X + LABEL_W, self._row(0), 180, 24),
                                 [(name, name) for name in files], self.new_image)
            self.new_image = picked or self.new_image
            if ui.button(t("Add"), pygame.Rect(FORM_X + LABEL_W + 190, self._row(0), 80, 24)):
                z = scene.columns[0] + 120 if scene.columns else 300      # за дальней колонной
                scene.objects.append(SceneObject(self.new_image, 0.0, z))
                self.selected = len(scene.objects) - 1
                changed = True
        else:
            ui.text(t("No images in assets/props yet."), FORM_X + LABEL_W, self._row(0) + 5, DIM, "small")
        if self.selected is not None and self.selected >= len(scene.objects):
            self.selected = None
        if self.selected is None:
            ui.text(t("Click an object on the field to select it, drag to move it."), FORM_X, self._row(1) + 5, DIM, "small")
            return changed
        obj = scene.objects[self.selected]
        ui.text(f"{self.selected + 1}/{len(scene.objects)}  {obj.image}", FORM_X + LABEL_W + 280, self._row(0) + 5, TEXT, "small")
        x = FORM_X
        for label, name, limits in (("X", "x", LIMITS["object_x"]), ("Z", "z", LIMITS["object_z"]),
                                    ("Lift", "y", LIMITS["object_y"]), ("Size", "size", SIZE_LIMITS)):
            value = self._number(ui, label, x, self._row(1), getattr(obj, name), limits, ("object", self.selected, name))
            if value is not None:
                setattr(obj, name, float(value))
                changed = True
            x += LABEL_W + FIELD_W + 12
        y = self._row(2)
        if ui.button(t("Flip"), pygame.Rect(FORM_X, y, 80, 24), selected=obj.flip):
            obj.flip, changed = not obj.flip, True
        if ui.button(t("Lies on the ground") if obj.layer == "ground" else t("Stands"), pygame.Rect(FORM_X + 90, y, 150, 24)):
            obj.layer, changed = LAYERS[(LAYERS.index(obj.layer) + 1) % len(LAYERS)], True
        if ui.button("<", pygame.Rect(FORM_X + 250, y, 30, 24)):
            self.selected = (self.selected - 1) % len(scene.objects)
        if ui.button(">", pygame.Rect(FORM_X + 284, y, 30, 24)):
            self.selected = (self.selected + 1) % len(scene.objects)
        if ui.button(t("Delete"), pygame.Rect(FORM_X + 324, y, 90, 24)):
            del scene.objects[self.selected]
            self.selected = None
            changed = True
        return changed

    # --- поле с подсказками ---

    def camera(self, window_scale: float = 1.0, window_offset: tuple[float, float] = (0, 0)) -> Camera:
        return self.camera_view.camera(window_scale, window_offset)

    def draw_field(self, target: pygame.Surface, now: int, cam: Camera) -> None:
        stage_camera, self.stage.camera_view = self.stage.camera_view, self.camera_view   # без наездов
        try:
            self.stage.draw_field(target, now, cam)
        finally:
            self.stage.camera_view = stage_camera
        previous = target.get_clip()
        target.set_clip(cam.clip)
        projection = self.scene.projection()
        line = max(1, round(cam.s(1.5)))
        if self.page == "Grid":
            if FIELD_RECT.top <= projection.horizon <= FIELD_RECT.bottom:
                pygame.draw.line(target, HORIZON_COLOR, cam.p(FIELD_RECT.left, projection.horizon),
                                 cam.p(FIELD_RECT.right, projection.horizon), 1)
            rows, cols = self.formation_size()
            for side in ("left", "right"):
                cells = {}
                for r in range(rows):
                    for c in range(cols):
                        x, z = self.scene.cell(side, r, c, cols)
                        cells[(r, c)] = projection.project(x, 0, z)[:2]
                for r in range(rows):                # линия ряда уходит в глубину
                    pygame.draw.lines(target, GRID_COLOR, False, [cam.p(*cells[(r, c)]) for c in range(cols)], line)
                for c in range(cols):                # линия колонны поперёк поля
                    pygame.draw.lines(target, GRID_COLOR, False, [cam.p(*cells[(r, c)]) for r in range(rows)], line)
            for cell, pos in self.handles().items():
                color = YELLOW if cell == self.drag else TEXT
                pygame.draw.circle(target, color, cam.p(*pos), max(2, round(cam.s(HANDLE_R))), line)
        elif self.page == "Objects" and self.selected is not None and self.selected < len(self.scene.objects):
            obj = self.scene.objects[self.selected]
            ring = [projection.project(obj.x + math.cos(a) * 30, 0, obj.z + math.sin(a) * 30)[:2]
                    for a in (i * math.tau / 24 for i in range(25))]
            pygame.draw.lines(target, YELLOW, False, [cam.p(*p) for p in ring], line)
            base, top = projection.project(obj.x, 0, obj.z), projection.project(obj.x, obj.y, obj.z)
            pygame.draw.line(target, YELLOW, cam.p(*base[:2]), cam.p(*top[:2]), line)
        target.set_clip(previous)
