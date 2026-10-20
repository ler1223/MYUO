"""Слои кадра и сортировка по глубине.

Всё на поле отдаёт рендереру части (Part): слой, глубину и функцию рисования.
1. GROUND — лежит на земле (тени, круги, волны); всегда под стоящими.
2. UPRIGHT — стоит или летит (спрайты, объекты, столбы, снаряды, частицы).
3. OVERLAY — надписи и вспышки поверх всего.
В слоях земли и стоящих дальнее рисуется раньше ближнего (алгоритм художника). Эффект,
обвивающий юнита, отдаёт две части: заднюю (глубже юнита) и переднюю (ближе).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

import pygame

from .camera import Camera
from .projection import Projection, World

GROUND, UPRIGHT, OVERLAY = 0, 1, 2
BEHIND = 0.5                # насколько задняя половина эффекта глубже его центра
IN_FRONT = -0.5


class View:
    """Мир -> пиксели окна в этом кадре: перспектива сцены и камера."""

    def __init__(self, projection: Projection, cam: Camera, now: int):
        self.projection = projection
        self.cam = cam
        self.now = now

    def p(self, point: World) -> tuple[int, int, float]:
        """(x, y, z) мира -> (x, y) пикселей окна и сколько пикселей окна в единице мира там."""
        lx, ly, k = self.projection.project(*point)
        px, py = self.cam.p(lx, ly)
        return px, py, k * self.cam.scale

    def xy(self, point: World) -> tuple[int, int]:
        lx, ly, _ = self.projection.project(*point)
        return self.cam.p(lx, ly)


@dataclass
class Part:
    layer: int
    depth: float
    draw: Callable[[pygame.Surface, View], None]
    order: int = 0              # при равной глубине: меньше — раньше
    gl: Optional[Callable[[Any, View], None]] = None     # то же в кадр видеокарты (engine.uo.frame.GLFrame)


def _order(parts: list[Part]) -> list[Part]:
    return sorted(parts, key=lambda p: (p.layer, -p.depth if p.layer != OVERLAY else 0, p.order))


def draw_parts(target: pygame.Surface, view: View, parts: list[Part]) -> None:
    """Рисует части по слоям; в слоях земли и стоящих — от дальних к ближним."""
    for part in _order(parts):
        part.draw(target, view)


def draw_parts_gl(frame: Any, view: View, parts: list[Part]) -> None:
    """То же в кадр видеокарты: у части есть gl — рисует она; нет — рисуется pygame на прозрачный
    слой кадра (frame.legacy). Слой накладывается в конце каждого слоя частей (земля, стоящие,
    надписи): внутри слоя нарисованное pygame оказывается поверх кукол — зато слой выгружается
    не чаще трёх раз за кадр."""
    layer = None
    for part in _order(parts):
        if part.layer != layer:
            frame.flush()
            layer = part.layer
        if part.gl is not None:
            part.gl(frame, view)
        else:
            part.draw(frame.legacy, view)
    frame.flush()
