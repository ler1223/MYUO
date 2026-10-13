"""Формация и отряд. Позиции отряда на карте здесь нет (см. world.WorldMap)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from .unit import Unit

MIN_GRID, MAX_GRID = 3, 5   # допустимый размер стороны поля
MAX_SQUAD_UNITS = 15


class FormationError(ValueError):
    pass


@dataclass(frozen=True)
class FormationSize:
    """Размер поля отряда и предел числа юнитов. Задаётся в данных (config.json)."""

    rows: int = 3
    cols: int = 3
    max_units: int = 5

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FormationSize":
        size = cls(data.get("rows", 3), data.get("cols", 3), data.get("max_units", 5))
        for name, value in (("rows", size.rows), ("cols", size.cols)):
            if not MIN_GRID <= value <= MAX_GRID:
                raise ValueError(f"formation {name} must be between {MIN_GRID} and {MAX_GRID}")
        if not 1 <= size.max_units <= min(MAX_SQUAD_UNITS, size.rows * size.cols):
            raise ValueError(f"formation max_units must be between 1 and {min(MAX_SQUAD_UNITS, size.rows * size.cols)}")
        return size

    def to_dict(self) -> dict[str, int]:
        return {"rows": self.rows, "cols": self.cols, "max_units": self.max_units}


class Formation:
    # Значения по умолчанию; у конкретной формации размер берётся из FormationSize.
    ROWS = 3       # row 0 = передний ряд
    COLS = 3
    MAX_UNITS = 5

    def __init__(self, size: Optional[FormationSize] = None) -> None:
        size = size or FormationSize(self.ROWS, self.COLS, self.MAX_UNITS)
        self.rows = size.rows
        self.cols = size.cols
        self.max_units = size.max_units
        self._slots: dict[tuple[int, int], Unit] = {}

    def contains(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols

    def place(self, unit: Unit, row: int, col: int) -> None:
        if not self.contains(row, col):
            raise FormationError(f"cell ({row}, {col}) is outside the formation")
        if (row, col) in self._slots:
            raise FormationError(f"cell ({row}, {col}) is occupied")
        if self.position_of(unit.uid) is not None:
            raise FormationError(f"unit {unit.uid} is already in the formation")
        if len(self._slots) >= self.max_units:
            raise FormationError(f"formation is full ({self.max_units} units)")
        self._slots[(row, col)] = unit

    def swap(self, pos_a: tuple[int, int], pos_b: tuple[int, int]) -> None:
        """Меняет содержимое двух клеток; любая из них может быть пустой."""
        for row, col in (pos_a, pos_b):
            if not self.contains(row, col):
                raise FormationError(f"cell ({row}, {col}) is outside the formation")
        unit_a, unit_b = self._slots.pop(pos_a, None), self._slots.pop(pos_b, None)
        if unit_a is not None:
            self._slots[pos_b] = unit_a
        if unit_b is not None:
            self._slots[pos_a] = unit_b

    def remove(self, uid: int) -> Optional[Unit]:
        pos = self.position_of(uid)
        return self._slots.pop(pos) if pos is not None else None

    def position_of(self, uid: int) -> Optional[tuple[int, int]]:
        for pos, unit in self._slots.items():
            if unit.uid == uid:
                return pos
        return None

    def unit_at(self, row: int, col: int) -> Optional[Unit]:
        return self._slots.get((row, col))

    @property
    def units(self) -> list[Unit]:
        """Передний ряд первым, внутри ряда слева направо."""
        return [self._slots[pos] for pos in sorted(self._slots)]

    def __len__(self) -> int:
        return len(self._slots)


@dataclass
class Squad:
    id: str
    name: str
    formation: Formation = field(default_factory=Formation)
    leader_uid: Optional[int] = None
