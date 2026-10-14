"""Раскладка: чистые функции над pygame.Rect. Экраны собирают свои области из них.

Размеры в split/rows/cols: int — пиксели, float — доля оставшегося места (веса: 1.0, 2.0 ...).
"""
from __future__ import annotations

from typing import Sequence, Union

import pygame

Size = Union[int, float]
ANCHORS = {"topleft": (0, 0), "top": (0.5, 0), "topright": (1, 0), "left": (0, 0.5), "center": (0.5, 0.5),
           "right": (1, 0.5), "bottomleft": (0, 1), "bottom": (0.5, 1), "bottomright": (1, 1)}


def inset(rect: pygame.Rect, left: int, top: int | None = None, right: int | None = None,
          bottom: int | None = None) -> pygame.Rect:
    """Прямоугольник с отступами внутрь (как padding: один, два или четыре числа)."""
    top = left if top is None else top
    right = left if right is None else right
    bottom = top if bottom is None else bottom
    return pygame.Rect(rect.x + left, rect.y + top, max(0, rect.width - left - right),
                       max(0, rect.height - top - bottom))


def _lengths(total: int, sizes: Sequence[Size], gap: int) -> list[int]:
    fixed = sum(s for s in sizes if isinstance(s, int))
    weights = sum(s for s in sizes if isinstance(s, float))
    free = max(0, total - fixed - gap * (len(sizes) - 1))
    lengths = [s if isinstance(s, int) else int(free * s / weights) for s in sizes]
    flexible = [i for i, s in enumerate(sizes) if isinstance(s, float)]
    if flexible:                                  # остаток от округления — последней доле
        lengths[flexible[-1]] += free - sum(lengths[i] for i in flexible)
    return lengths


def split(rect: pygame.Rect, sizes: Sequence[Size], gap: int = 0, axis: str = "x") -> list[pygame.Rect]:
    out, pos = [], rect.x if axis == "x" else rect.y
    for length in _lengths(rect.width if axis == "x" else rect.height, sizes, gap):
        out.append(pygame.Rect(pos, rect.y, length, rect.height) if axis == "x"
                   else pygame.Rect(rect.x, pos, rect.width, length))
        pos += length + gap
    return out


def cols(rect: pygame.Rect, sizes: Sequence[Size], gap: int = 0) -> list[pygame.Rect]:
    return split(rect, sizes, gap, "x")


def rows(rect: pygame.Rect, sizes: Sequence[Size], gap: int = 0) -> list[pygame.Rect]:
    return split(rect, sizes, gap, "y")


def cut_top(rect: pygame.Rect, height: int, gap: int = 0) -> tuple[pygame.Rect, pygame.Rect]:
    """(полоса сверху, остаток под ней)."""
    top, rest = rows(rect, [height, 1.0], gap)
    return top, rest


def cut_bottom(rect: pygame.Rect, height: int, gap: int = 0) -> tuple[pygame.Rect, pygame.Rect]:
    """(остаток над полосой, полоса снизу)."""
    rest, bottom = rows(rect, [1.0, height], gap)
    return rest, bottom


def cut_left(rect: pygame.Rect, width: int, gap: int = 0) -> tuple[pygame.Rect, pygame.Rect]:
    left, rest = cols(rect, [width, 1.0], gap)
    return left, rest


def cut_right(rect: pygame.Rect, width: int, gap: int = 0) -> tuple[pygame.Rect, pygame.Rect]:
    rest, right = cols(rect, [1.0, width], gap)
    return rest, right


def grid(rect: pygame.Rect, count: int, columns: int, cell_h: int | None = None, gap: int = 0,
         gap_y: int | None = None) -> list[pygame.Rect]:
    """count ячеек слева направо, сверху вниз; ширина — поровну, высота — cell_h или поровну."""
    gap_y = gap if gap_y is None else gap_y
    lines = max(1, (count + columns - 1) // columns)
    width = (rect.width - gap * (columns - 1)) // columns
    height = cell_h if cell_h is not None else (rect.height - gap_y * (lines - 1)) // lines
    return [pygame.Rect(rect.x + (i % columns) * (width + gap), rect.y + (i // columns) * (height + gap_y), width, height)
            for i in range(count)]


def place(rect: pygame.Rect, size: tuple[int, int], anchor: str = "center", offset: tuple[int, int] = (0, 0)) -> pygame.Rect:
    """Прямоугольник размера size, привязанный к точке anchor внутри rect."""
    ax, ay = ANCHORS[anchor]
    return pygame.Rect(round(rect.x + (rect.width - size[0]) * ax) + offset[0],
                       round(rect.y + (rect.height - size[1]) * ay) + offset[1], *size)


def row_of(rect: pygame.Rect, widths: Sequence[int], gap: int = 0, align: str = "center") -> list[pygame.Rect]:
    """Ряд элементов заданной ширины во всю высоту rect, выровненный как группа (left, center, right)."""
    total = sum(widths) + gap * (len(widths) - 1)
    x = rect.x if align == "left" else (rect.right - total if align == "right" else rect.centerx - total // 2)
    out = []
    for w in widths:
        out.append(pygame.Rect(x, rect.y, w, rect.height))
        x += w + gap
    return out


def square(rect: pygame.Rect, anchor: str = "center") -> pygame.Rect:
    side = min(rect.width, rect.height)
    return place(rect, (side, side), anchor)
