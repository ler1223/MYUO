"""Где стоят бойцы и куда смотрит камера (координаты сцены фона UO: x вправо, y вниз, 0,0 — центр фона).

Как в бою UO: нападающий отряд слева лицом вправо, защищающийся справа; передний ряд ближе к центру,
задние — дальше от него; колонки уходят в глубину: колонка 0 — дальняя (выше и мельче на экране),
последняя — ближняя. Бойцы стоят на земле фона, в полосе floor (дальний край, ближний край).
Камера по умолчанию показывает оба отряда целиком.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

FLOOR = (300.0, 520.0)       # полоса земли фона: y дальней и ближней колонки (допущение по фонам UO)
FRONT_X = 250.0              # передний ряд: расстояние от центра
ROW_STEP = 240.0             # между рядами
LANE_SKEW = 40.0             # ближняя колонка чуть дальше от центра: колонки идут по диагонали
FAR_SCALE = 0.82             # во сколько раз мельче боец в дальней колонке
VIEW_HEIGHT = 1000.0         # высота кадра в единицах сцены при обзоре
VIEW_BELOW = 90.0           # сколько земли видно под ближней колонкой
APPROACH = 175.0             # ближний бой: на таком расстоянии перед целью останавливается атакующий
OFFSCREEN = 1000.0           # выход на поле: откуда вбегают (дальше от центра своего края)


def floor_for(bottom: Optional[float]) -> tuple[float, float]:
    """Полоса земли для фона с нижним краем bottom: ближняя колонка — чуть выше края."""
    if bottom is None:
        return FLOOR
    near = min(FLOOR[1], bottom - VIEW_BELOW - 10)
    return near - (FLOOR[1] - FLOOR[0]), near


@dataclass(frozen=True)
class Spot:
    """Место бойца: точка ног, масштаб глубины, куда смотрит (1 — вправо)."""

    x: float
    y: float
    scale: float
    facing: int

    def ahead(self, distance: float) -> "Spot":
        """Точка перед этим местом (со стороны, куда он смотрит) на distance (с поправкой на глубину)."""
        return Spot(self.x + self.facing * distance * self.scale, self.y + 2, self.scale, self.facing)


class Stage:
    """Раскладка поля для отрядов rows × cols (ряд 0 — передний)."""

    def __init__(self, rows: int = 2, cols: int = 3, floor: tuple[float, float] = FLOOR,
                 bottom: Optional[float] = None):
        """bottom — нижний край картинки фона: ниже него кадр не опускается."""
        self.rows, self.cols = max(1, rows), max(1, cols)
        self.floor = floor
        self.bottom = bottom

    def depth(self, col: int) -> float:
        """0 — дальняя колонка, 1 — ближняя."""
        return col / max(1, self.cols - 1)

    def spot(self, side: int, row: int, col: int) -> Spot:
        """Место клетки (side 0 — слева, 1 — справа)."""
        d = self.depth(col)
        far, near = self.floor
        y = far + (near - far) * d
        scale = FAR_SCALE + (1 - FAR_SCALE) * d
        x = (FRONT_X + row * ROW_STEP + (d - 0.5) * 2 * LANE_SKEW) * scale
        sign = -1 if side == 0 else 1
        return Spot(sign * x, y, scale, 1 if side == 0 else -1)

    def scale_at(self, y: float) -> float:
        far, near = self.floor
        d = min(1.2, max(-0.2, (y - far) / max(1.0, near - far)))
        return FAR_SCALE + (1 - FAR_SCALE) * d

    def view(self, aspect: float) -> tuple[float, float, float, float]:
        """Кадр обзора (x0, y0, x1, y1) в единицах сцены для окна с пропорцией aspect (ширина/высота)."""
        bottom = self.floor[1] + VIEW_BELOW
        if self.bottom is not None:
            bottom = min(bottom, self.bottom - 8)
        height = VIEW_HEIGHT
        width = height * aspect
        reach = FRONT_X + (self.rows - 1) * ROW_STEP + LANE_SKEW + 200
        if width < 2 * reach:          # все ряды должны влезть: кадр шире — и выше
            width = 2 * reach
            height = width / aspect
        return -width / 2, bottom - height, width / 2, bottom
