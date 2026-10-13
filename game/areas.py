"""Области: какие клетки формации задеты относительно опорной клетки.

Область это набор смещений (ряд, колонна) от опорной клетки. Для навыка опорная
клетка это цель, для прикрытия и триггеров эффектов это сам юнит. Смещение по
ряду больше нуля значит «дальше от врага» (ряд 0 передний).

Области не зависят от размера поля: смещения заданы в пределах MAX_SPAN в каждую
сторону, чего хватает на поле до 5x5. Области хранятся в данных и правятся
редактором; BUILTIN_AREAS нужны, только если в папке данных нет своего файла.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

Position = tuple[int, int]

MAX_SPAN = 4               # наибольшее смещение: покрывает поле 5x5 из любой клетки
AREA_SINGLE = "single"     # область по умолчанию: только сама опорная клетка
_SPAN = range(-MAX_SPAN, MAX_SPAN + 1)


@dataclass(frozen=True)
class AreaDefinition:
    id: str
    name: str
    cells: frozenset[Position] = frozenset({(0, 0)})

    @classmethod
    def from_dict(cls, area_id: str, data: Mapping[str, Any]) -> "AreaDefinition":
        cells = frozenset((int(row), int(col)) for row, col in data.get("cells", [[0, 0]]))
        for row, col in cells:
            if abs(row) > MAX_SPAN or abs(col) > MAX_SPAN:
                raise ValueError(f"area {area_id}: offset ({row}, {col}) is beyond {MAX_SPAN}")
        return cls(area_id, data.get("name", area_id), cells)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "cells": [list(cell) for cell in sorted(self.cells)]}

    def covers(self, anchor: Position, other: Position) -> bool:
        """Попадает ли клетка other в область с опорной клеткой anchor."""
        return (other[0] - anchor[0], other[1] - anchor[1]) in self.cells


BUILTIN_AREAS: dict[str, dict[str, Any]] = {
    AREA_SINGLE: {"name": "Single", "cells": [[0, 0]]},
    "row": {"name": "Row", "cells": [[0, col] for col in _SPAN]},
    "column": {"name": "Column", "cells": [[row, 0] for row in _SPAN]},
    "all": {"name": "All", "cells": [[row, col] for row in _SPAN for col in _SPAN]},
}
