"""Вкладка Scene: редактор сцены боя — сетка расположения юнитов в трёхмерном пространстве и фон.

Сверху поле так же, как на вкладке Stage (тот же бой, те же спрайты), поверх — сетка:
линии колонн (глубина) и рядов (расстояние от центра) на земле и ручки клеток отряда
игрока. Ручку можно тянуть мышью: вверх-вниз меняется глубина колонны, влево-вправо —
расстояние ряда; отряд противника зеркален. Снизу — числа сцены, фон и затемнение.
Каждая правка сразу записывается в assets/stage/scene.json.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pygame

from pygame_battle import FIELD_RECT
from pygame_fx import Camera
from pygame_scene import LIMITS, MAX_LINES, SCENE_PATH, SceneConfig, background_files
from pygame_stage import StageScreen
from pygame_ui import DIM, TEXT, UI, WIDTH, YELLOW

FORM_TOP = FIELD_RECT.bottom + 8
ROW_H = 28
LABEL_W = 78
FIELD_W = 64
HANDLE_R = 7               # радиус ручки клетки, логические пиксели
GRAB_R = 16                # насколько близко к ручке надо нажать
GRID_COLOR = (120, 200, 255)
HORIZON_COLOR = (255, 200, 120)

# (ключ, подпись, целое ли) — простые числа сцены в первой строке формы
NUMBERS = (("horizon", "Horizon", True), ("ground", "Ground", True), ("focal", "Focal", True),
           ("human_height", "Height", True), ("slant", "Slant", True), ("fly_height", "Fly", True))


class SceneEditor:
    """Редактор сцены. Поле рисует Stage; редактор добавляет сетку и ручки и правит scene."""

    def __init__(self, stage: StageScreen, path: Optional[Path] = SCENE_PATH):
        self.stage = stage
        self.scene: SceneConfig = stage.scene
        self.path = path                    # None: не записывать на диск
        self.drag: Optional[tuple[int, int]] = None   # (ряд, колонна) перетаскиваемой ручки
        self.native = False

    # --- изменение сцены ---

    def changed(self) -> None:
        self.scene.clamp()
        if self.path is not None:
            self.scene.save(self.path)

    def formation_size(self) -> tuple[int, int]:
        view = self.stage.battle_view
        size = view.sim.attacker.formation if view is not None else None
        return (size.rows, size.cols) if size is not None else (len(self.scene.rows), len(self.scene.columns))

    def handles(self) -> dict[tuple[int, int], tuple[float, float]]:
        """Ручки клеток отряда игрока: (ряд, колонна) -> точка на поле."""
        rows, cols = self.formation_size()
        result = {}
        for row in range(rows):
            for col in range(cols):
                x, z = self.scene.cell("left", row, col, cols)
                sx, sy, _ = self.scene.project(x, z)
                result[(row, col)] = (sx, sy)
        return result

    def drag_to(self, cell: tuple[int, int], pos: tuple[float, float]) -> None:
        """Ручка клетки в точку pos: глубина её колонны и расстояние её ряда меняются.

        Линии за последней заданной (продолжение шага) не двигаются.
        """
        scene = self.scene
        ground = scene.unproject(*pos)
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

    def handle_event(self, event: pygame.event.Event, pos: tuple[float, float], window_scale: float = 1.0) -> None:
        """Перетаскивание ручек мышью. pos: курсор в логических пикселях окна."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and FIELD_RECT.collidepoint(pos):
            near = [(abs(hx - pos[0]) + abs(hy - pos[1]), cell) for cell, (hx, hy) in self.handles().items()]
            near = [item for item in near if item[0] <= GRAB_R * 1.5]
            self.drag = min(near)[1] if near else None
        elif event.type == pygame.MOUSEMOTION and self.drag is not None:
            self.drag_to(self.drag, pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.drag is not None:
            self.drag = None
            self.changed()

    # --- форма ---

    def draw(self, ui: UI, app: Any) -> None:
        t, scene = ui.t, self.scene
        stage = self.stage
        if stage.battle_view is not None:
            stage.update(ui, stage.battle_view, pygame.time.get_ticks())
        y = FORM_TOP
        changed = False
        for i, (key, label, integer) in enumerate(NUMBERS):
            x = 8 + i * (LABEL_W + FIELD_W + 22)
            ui.text(t(label), x, y + 5, DIM, "small")
            low, high = LIMITS[key]
            value = ui.number_input(("scene", key), pygame.Rect(x + LABEL_W, y, FIELD_W, 24), getattr(scene, key), low, high, integer)
            if value is not None:
                setattr(scene, key, float(value))
                changed = True

        y += ROW_H
        x = 8
        for name, label, limits in (("rows", "Rows", "row"), ("columns", "Columns", "column")):
            values: list[float] = getattr(scene, name)
            ui.text(t(label), x, y + 5, DIM, "small")
            x += LABEL_W
            for i, current in enumerate(values):
                low, high = LIMITS[limits]
                value = ui.number_input(("scene", name, i), pygame.Rect(x, y, 52, 24), current, low, high)
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
            x += 72

        y += ROW_H
        ui.text(t("Background"), 8, y + 5, DIM, "small")
        options = [("", t("none"))] + [(name, name) for name in background_files()]
        picked = ui.dropdown(("scene", "background"), pygame.Rect(8 + LABEL_W, y, 200, 24), options, scene.background)
        if picked is not None and picked != scene.background:
            scene.background = picked
            changed = True
        ui.text(t("Darken %"), 300, y + 5, DIM, "small")
        darken = ui.number_input(("scene", "darken"), pygame.Rect(300 + LABEL_W, y, FIELD_W, 24), scene.darken, 0, 100)
        if darken is not None:
            scene.darken = float(darken)
            changed = True
        if ui.button(t("Reset"), pygame.Rect(460, y, 80, 24)):
            fresh = SceneConfig()
            for key, value in fresh.to_dict().items():
                setattr(scene, key, value)
            changed = True
        ui.text(t("Drag cell handles: up/down — depth, sideways — row."),
                552, y + 5, DIM, "small", WIDTH - 560)
        if changed:
            self.changed()
        if not self.native:
            self.draw_field(ui.screen, pygame.time.get_ticks(), self.camera())

    # --- поле с сеткой ---

    def camera(self, window_scale: float = 1.0, window_offset: tuple[float, float] = (0, 0)) -> Camera:
        clip = pygame.Rect(round(window_offset[0] + FIELD_RECT.left * window_scale),
                           round(window_offset[1] + FIELD_RECT.top * window_scale),
                           round(FIELD_RECT.width * window_scale), round(FIELD_RECT.height * window_scale))
        return Camera(window_scale, FIELD_RECT.topleft, clip.topleft, clip)

    def draw_field(self, target: pygame.Surface, now: int, cam: Camera) -> None:
        if self.stage.view is not None:
            self.stage.draw_field(target, now, cam)
        else:
            self.stage.draw_background(target, cam)
        previous = target.get_clip()
        target.set_clip(cam.clip)
        scene = self.scene
        _, horizon, _ = scene.project(0, 1e9)
        if FIELD_RECT.top <= horizon <= FIELD_RECT.bottom:
            pygame.draw.line(target, HORIZON_COLOR, cam.p(FIELD_RECT.left, horizon), cam.p(FIELD_RECT.right, horizon), 1)
        rows, cols = self.formation_size()
        line = max(1, round(cam.s(1.5)))
        for side in ("left", "right"):
            cells = {(r, c): scene.project(*scene.cell(side, r, c, cols))[:2] for r in range(rows) for c in range(cols)}
            for r in range(rows):                    # линия ряда уходит в глубину
                pygame.draw.lines(target, GRID_COLOR, False, [cam.p(*cells[(r, c)]) for c in range(cols)], line)
            for c in range(cols):                    # линия колонны поперёк поля
                pygame.draw.lines(target, GRID_COLOR, False, [cam.p(*cells[(r, c)]) for r in range(rows)], line)
        for cell, pos in self.handles().items():
            color = YELLOW if cell == self.drag else TEXT
            pygame.draw.circle(target, color, cam.p(*pos), max(2, round(cam.s(HANDLE_R))), line)
        target.set_clip(previous)
