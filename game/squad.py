"""Формация 3x3 и отряд. Позиции отряда на карте здесь нет (см. world.WorldMap)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .unit import Unit


class FormationError(ValueError):
    pass


class Formation:
    ROWS = 3       # row 0 = передний ряд
    COLS = 3
    MAX_UNITS = 5

    def __init__(self) -> None:
        self._slots: dict[tuple[int, int], Unit] = {}

    def place(self, unit: Unit, row: int, col: int) -> None:
        if not (0 <= row < self.ROWS and 0 <= col < self.COLS):
            raise FormationError(f"cell ({row}, {col}) is outside the formation")
        if (row, col) in self._slots:
            raise FormationError(f"cell ({row}, {col}) is occupied")
        if self.position_of(unit.uid) is not None:
            raise FormationError(f"unit {unit.uid} is already in the formation")
        if len(self._slots) >= self.MAX_UNITS:
            raise FormationError(f"formation is full ({self.MAX_UNITS} units)")
        self._slots[(row, col)] = unit

    def swap(self, pos_a: tuple[int, int], pos_b: tuple[int, int]) -> None:
        """Меняет содержимое двух клеток; любая из них может быть пустой."""
        for row, col in (pos_a, pos_b):
            if not (0 <= row < self.ROWS and 0 <= col < self.COLS):
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
