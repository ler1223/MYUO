"""Камеры: Camera переводит логические пиксели поля в пиксели окна; ViewCamera — обзор поля.

ViewCamera — двумерная камера поверх перспективы сцены, как в Unicorn Overlord: в обзоре
видно всё поле, при атаке камера плавно наезжает на атакующего и цели (focus) и
возвращается. Игрок может сам приблизить колесом и перетащить поле; тогда камера держит
его выбор, пока он не вернёт обзор (Home).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import pygame

Point = tuple[float, float]

MAX_ZOOM = 3.0
ZOOM_STEP = 0.25
FOCUS_ZOOM = 1.45          # самый сильный наезд на действие
FOCUS_MIN_ZOOM = 1.15      # самый слабый: даже если участники далеко, камера чуть приближается к центру действия
FOCUS_MARGIN = 0.18        # запас вокруг участников, доля видимой области
EASE_MS = 220              # чем меньше, тем резче камера догоняет цель


@dataclass(frozen=True)
class Camera:
    """Логические пиксели поля -> пиксели окна.

    scale: пикселей окна на логический пиксель (размер окна x зум);
    origin: логическая точка, которая видна в левом верхнем углу области поля;
    offset: где в окне начинается область поля; clip: область поля в окне.
    """

    scale: float = 1.0
    origin: Point = (0.0, 0.0)
    offset: Point = (0.0, 0.0)
    clip: Optional[pygame.Rect] = None

    def p(self, x: float, y: float) -> tuple[int, int]:
        return (round(self.offset[0] + (x - self.origin[0]) * self.scale),
                round(self.offset[1] + (y - self.origin[1]) * self.scale))

    def s(self, value: float) -> float:
        return value * self.scale

    def shifted(self, dx: float, dy: float) -> "Camera":
        """Та же камера, сдвинутая на (dx, dy) логических пикселей (дрожь поля)."""
        return Camera(self.scale, (self.origin[0] - dx, self.origin[1] - dy), self.offset, self.clip)


IDENTITY = Camera()


class ViewCamera:
    """Обзор поля field (логические пиксели): зум, перемещение, наезд на действие."""

    def __init__(self, field: pygame.Rect):
        self.field = pygame.Rect(field)
        self.zoom = 1.0
        self.origin: Point = self.field.topleft
        self.goal: tuple[float, Point] = (1.0, self.field.topleft)
        self.manual = False                 # игрок сам выбрал зум: наезды не мешают
        self.auto = True                    # наезжать на действие
        self.focus_until = 0
        self._last = 0

    # --- видимая область ---

    def view_size(self, zoom: Optional[float] = None) -> tuple[float, float]:
        zoom = zoom or self.zoom
        return self.field.width / zoom, self.field.height / zoom

    def _clamped(self, zoom: float, origin: Point) -> Point:
        vw, vh = self.view_size(zoom)
        return (min(max(origin[0], self.field.left), self.field.right - vw),
                min(max(origin[1], self.field.top), self.field.bottom - vh))

    def camera(self, window_scale: float = 1.0, window_offset: Point = (0, 0)) -> Camera:
        clip = pygame.Rect(round(window_offset[0] + self.field.left * window_scale),
                           round(window_offset[1] + self.field.top * window_scale),
                           round(self.field.width * window_scale), round(self.field.height * window_scale))
        return Camera(window_scale * self.zoom, self.origin, clip.topleft, clip)

    # --- наезд ---

    def focus(self, box: pygame.Rect, until: int) -> None:
        """Плавно показать область box (логические пиксели) до момента until."""
        if self.manual or not self.auto:
            return
        margin = 1 + FOCUS_MARGIN * 2
        zoom = min(FOCUS_ZOOM, self.field.width / max(1, box.width * margin), self.field.height / max(1, box.height * margin))
        zoom = max(FOCUS_MIN_ZOOM, zoom)
        vw, vh = self.view_size(zoom)
        self.goal = (zoom, self._clamped(zoom, (box.centerx - vw / 2, box.centery - vh / 2)))
        self.focus_until = until

    def update(self, now: int) -> None:
        """Шаг к цели; после конца наезда цель — обзор."""
        if not self.manual and now > self.focus_until:
            self.goal = (1.0, self.field.topleft)
        if self.manual:
            self._last = now
            return
        dt = max(0, min(100, now - self._last)) if self._last else 1000
        self._last = now
        k = 1 - math.exp(-dt / EASE_MS)
        zoom, origin = self.goal
        self.zoom += (zoom - self.zoom) * k
        self.origin = (self.origin[0] + (origin[0] - self.origin[0]) * k, self.origin[1] + (origin[1] - self.origin[1]) * k)
        if abs(self.zoom - zoom) < 0.002:
            self.zoom, self.origin = zoom, origin

    def settle(self) -> None:
        """Сразу встать в цель (без плавного перехода)."""
        self.zoom, self.origin = self.goal

    # --- управление игроком ---

    def zoom_at(self, pos: Point, steps: float) -> None:
        """Зум колесом: точка поля под курсором (логические пиксели) остаётся на месте."""
        if not self.field.collidepoint(pos):
            return
        fx = self.origin[0] + (pos[0] - self.field.left) / self.zoom
        fy = self.origin[1] + (pos[1] - self.field.top) / self.zoom
        self.zoom = min(MAX_ZOOM, max(1.0, round((self.zoom + steps * ZOOM_STEP) * 4) / 4))
        self.origin = self._clamped(self.zoom, (fx - (pos[0] - self.field.left) / self.zoom,
                                                fy - (pos[1] - self.field.top) / self.zoom))
        self.manual = self.zoom > 1
        self.goal = (self.zoom, self.origin)

    def pan(self, dx: float, dy: float) -> None:
        """Сдвиг на (dx, dy) логических пикселей окна (мышь тянет поле за собой)."""
        self.origin = self._clamped(self.zoom, (self.origin[0] - dx / self.zoom, self.origin[1] - dy / self.zoom))
        self.goal = (self.zoom, self.origin)

    def reset(self) -> None:
        """Обзор всего поля; наезды снова работают."""
        self.zoom, self.origin, self.manual = 1.0, self.field.topleft, False
        self.goal = (1.0, self.origin)
        self.focus_until = 0
