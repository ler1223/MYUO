"""Сцена боя: трёхмерное пространство, в котором стоят двумерные спрайты.

Мир: x — поперёк поля (0 в центре, отряд игрока слева, x < 0), z — глубина (0 — ближняя
линия, дальше от зрителя больше), высота — вверх. Камера смотрит сверху-сбоку, перспектива
простая: на глубине z всё уменьшается в focal / (focal + z) раз, земля на этой глубине видна
на высоте экрана между линией земли (z = 0) и горизонтом.

Сетка расположения: у каждого ряда формации своё расстояние от центра (rows), у каждой
колонны — своя глубина (columns). slant сдвигает дальние колонны к центру: отряд стоит
по диагонали. Всё это и фон редактируются на вкладке Scene и хранятся в assets/stage/scene.json.
Модуль не зависит от pygame.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent
SCENE_PATH = ROOT / "assets" / "stage" / "scene.json"
BACKGROUND_DIR = ROOT / "assets" / "backgrounds"
BACKGROUND_TYPES = (".png", ".jpg", ".jpeg")
FIELD_CENTER_X = 500          # центр поля в логических пикселях окна

# Пределы значений: и для редактора, и для проверки файла.
LIMITS: dict[str, tuple[float, float]] = {
    "horizon": (-3000, 400),
    "ground": (100, 600),
    "focal": (100, 20000),
    "human_height": (40, 400),
    "slant": (-200, 200),
    "fly_height": (0, 200),
    "darken": (0, 100),
    "row": (0, 1000),
    "column": (0, 3000),
}
MAX_LINES = 5                 # самое большое поле 5x5


@dataclass
class SceneConfig:
    horizon: float = -360       # экранная высота горизонта (может быть выше окна)
    ground: float = 452         # экранная высота ближней линии земли (z = 0)
    focal: float = 1200         # чем меньше, тем сильнее перспектива
    human_height: float = 185   # рост человека на ближней линии, логические пиксели
    rows: list[float] = field(default_factory=lambda: [150.0, 245.0, 340.0])     # от центра, передний ряд первым
    columns: list[float] = field(default_factory=lambda: [260.0, 130.0, 0.0])    # глубина колонны 0, 1, 2 ...
    slant: float = 15           # сдвиг к центру на каждые 100 глубины
    fly_height: float = 40      # высота парения летающих
    background: str = ""        # файл в assets/backgrounds; пусто — градиент
    darken: float = 0           # затемнение фона, %
    sky: list[int] = field(default_factory=lambda: [22, 24, 32])        # градиент без картинки: верх
    earth: list[int] = field(default_factory=lambda: [42, 44, 46])      # и низ

    # --- файл ---

    @classmethod
    def load(cls, path: Path = SCENE_PATH) -> "SceneConfig":
        if not path.exists():
            return cls()
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneConfig":
        """Неизвестные ключи пропускаются, значения обрезаются до пределов."""
        known = {f.name for f in fields(cls)}
        scene = cls(**{k: v for k, v in data.items() if k in known})
        scene.clamp()
        return scene

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path = SCENE_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def clamp(self) -> None:
        for name in ("horizon", "ground", "focal", "human_height", "slant", "fly_height", "darken"):
            low, high = LIMITS[name]
            setattr(self, name, float(min(high, max(low, getattr(self, name)))))
        self.horizon = min(self.horizon, self.ground - 20)        # горизонт всегда выше земли
        self.rows = [float(min(LIMITS["row"][1], max(LIMITS["row"][0], v))) for v in self.rows[:MAX_LINES]] or [110.0]
        self.columns = [float(min(LIMITS["column"][1], max(LIMITS["column"][0], v)))
                        for v in self.columns[:MAX_LINES]] or [0.0]

    # --- сетка ---

    @staticmethod
    def line(values: list[float], index: int) -> float:
        """Значение линии; за последней линией шаг продолжается."""
        if index < len(values):
            return values[index]
        step = values[-1] - values[-2] if len(values) > 1 else 100.0
        return values[-1] + step * (index - len(values) + 1)

    def row_distance(self, row: int) -> float:
        return self.line(self.rows, row)

    def column_depth(self, col: int, cols: int) -> float:
        """Глубина колонны формации; у поля шире, чем задано линий, колонны продолжаются вглубь.

        Колонны считаются от ближней: последняя колонна формации стоит на последней линии.
        """
        from_near = cols - 1 - col
        near_first = list(reversed(self.columns))
        return self.line(near_first, from_near)

    def cell(self, side: str, row: int, col: int, cols: int) -> tuple[float, float]:
        """Мировые (x, z) клетки формации; side: left — отряд игрока, right — противник."""
        z = self.column_depth(col, cols)
        distance = self.row_distance(row) - self.slant * z / 100
        return (-distance if side == "left" else distance), z

    # --- проекция ---

    def scale(self, z: float) -> float:
        return self.focal / max(1.0, self.focal + z)

    def project(self, x: float, z: float, height: float = 0.0) -> tuple[float, float, float]:
        """Мировая точка -> (x, y) в логических пикселях поля и масштаб на этой глубине."""
        k = self.scale(z)
        return FIELD_CENTER_X + x * k, self.horizon + (self.ground - self.horizon) * k - height * k, k

    def unproject(self, sx: float, sy: float) -> Optional[tuple[float, float]]:
        """Точка на земле под экранной точкой -> мировые (x, z); выше горизонта — None."""
        k = (sy - self.horizon) / max(1e-6, self.ground - self.horizon)
        if k <= 0.02:
            return None
        return (sx - FIELD_CENTER_X) / k, self.focal / k - self.focal


def background_files() -> list[str]:
    """Картинки фона из assets/backgrounds."""
    if not BACKGROUND_DIR.exists():
        return []
    return sorted(p.name for p in BACKGROUND_DIR.iterdir() if p.suffix.lower() in BACKGROUND_TYPES)
