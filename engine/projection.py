"""Перспектива сцены: мировая точка -> логические пиксели окна и обратно.

На глубине z всё уменьшается в focal / (focal + z) раз; земля на этой глубине видна на
высоте экрана между линией земли ground (z = 0) и горизонтом horizon. Модуль без pygame.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

World = tuple[float, float, float]     # (x, y, z)


@dataclass(frozen=True)
class Projection:
    horizon: float = -360
    ground: float = 452
    focal: float = 1200
    center_x: float = 500

    def scale(self, z: float) -> float:
        """Сколько логических пикселей в единице мира на глубине z."""
        return self.focal / max(1.0, self.focal + z)

    def project(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        """(x, y, z) мира -> (x, y) логических пикселей и масштаб на этой глубине."""
        k = self.scale(z)
        return self.center_x + x * k, self.horizon + (self.ground - self.horizon) * k - y * k, k

    def depth_at(self, sy: float) -> Optional[float]:
        """Глубина земли, видной на высоте экрана sy; выше горизонта — None."""
        k = (sy - self.horizon) / max(1e-6, self.ground - self.horizon)
        if k <= 0.02:
            return None
        return self.focal / k - self.focal

    def unproject(self, sx: float, sy: float) -> Optional[tuple[float, float]]:
        """Точка на земле под экранной точкой -> мировые (x, z); выше горизонта — None."""
        z = self.depth_at(sy)
        if z is None:
            return None
        return (sx - self.center_x) / self.scale(z), z
