"""Области действия навыка: кого задевает навык вокруг выбранной цели.

Функция области получает клетку цели и клетку другого юнита той же стороны
((row, col) в формации) и отвечает, задет ли он. Новая область (например,
"around": одна клетка вокруг цели) добавляется строкой в AREAS.
"""
from __future__ import annotations

from typing import Callable

Position = tuple[int, int]

AREA_SINGLE = "single"

AREAS: dict[str, Callable[[Position, Position], bool]] = {
    AREA_SINGLE: lambda target, other: other == target,
    "row": lambda target, other: other[0] == target[0],
    "column": lambda target, other: other[1] == target[1],
    "all": lambda target, other: True,
}
