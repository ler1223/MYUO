"""Сцены боя и их хранилище. Модуль без pygame.

Сцена: перспектива (horizon, ground, focal), сетка формаций (rows, columns, slant), рост
человека, земля (текстура в перспективе), задник (картинка за дальним краем земли),
дымка и объекты-декорации. Сцен сколько угодно: assets/scenes/<id>.json, создаются и
правятся на вкладке Scene.

Сетка: у каждого ряда формации своё расстояние от центра (rows), у каждой колонны —
своя глубина (columns, колонна 0 — дальняя, верхняя на экране). slant сдвигает дальние
колонны к центру: отряд стоит по диагонали. Отряд противника зеркален.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Optional

from .projection import Projection

ROOT = Path(__file__).resolve().parent.parent
SCENES_DIR = ROOT / "assets" / "scenes"
BACKDROP_DIR = ROOT / "assets" / "backgrounds"
GROUND_DIR = ROOT / "assets" / "grounds"
PROPS_DIR = ROOT / "assets" / "props"
IMAGE_TYPES = (".png", ".jpg", ".jpeg")
DEFAULT_SCENE = "default"
FIELD_CENTER_X = 500          # центр поля в логических пикселях окна
MAX_LINES = 5                 # самое большое поле 5x5
LAYERS = ("upright", "ground")   # объект стоит (спрайт) или лежит на земле

# Пределы чисел: и для редактора, и для проверки файла.
LIMITS: dict[str, tuple[float, float]] = {
    "horizon": (-3000, 400),
    "ground": (100, 600),
    "focal": (100, 20000),
    "human_height": (40, 400),
    "slant": (-200, 200),
    "fly_height": (0, 200),
    "ground_tile": (10, 2000),
    "ground_depth": (100, 20000),
    "backdrop_line": (0, 100),
    "backdrop_width": (50, 400),
    "backdrop_darken": (0, 100),
    "ground_darken": (0, 100),
    "haze": (0, 100),
    "row": (0, 1000),
    "column": (0, 3000),
    "object_x": (-3000, 3000),
    "object_y": (-500, 2000),
    "object_z": (-500, 20000),
}


@dataclass
class SceneObject:
    """Декорация: картинка из assets/props в точке мира (x, y, z).

    size — высота стоящего объекта или длина лежащего (вглубь) в единицах мира; другая
    сторона — по пропорциям картинки. Лежащий объект рисуется на земле в перспективе.
    """

    image: str
    x: float = 0.0
    z: float = 0.0
    y: float = 0.0                 # подъём над землёй
    size: float = 120.0            # высота (стоящий) или длина (лежащий) в единицах мира
    flip: bool = False
    layer: str = "upright"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneObject":
        known = {f.name for f in fields(cls)}
        obj = cls(**{k: v for k, v in data.items() if k in known})
        obj.clamp()
        return obj

    def clamp(self) -> None:
        self.x = float(min(LIMITS["object_x"][1], max(LIMITS["object_x"][0], self.x)))
        self.y = float(min(LIMITS["object_y"][1], max(LIMITS["object_y"][0], self.y)))
        self.z = float(min(LIMITS["object_z"][1], max(LIMITS["object_z"][0], self.z)))
        self.size = float(min(2000, max(5, self.size)))
        self.flip = bool(self.flip)
        if self.layer not in LAYERS:
            self.layer = LAYERS[0]


@dataclass
class SceneConfig:
    name: str = "Default"
    horizon: float = -360        # экранная высота горизонта (может быть выше окна)
    ground: float = 452          # экранная высота ближней линии земли (z = 0)
    focal: float = 1200          # чем меньше, тем сильнее перспектива
    human_height: float = 185    # рост человека, единицы мира
    rows: list[float] = field(default_factory=lambda: [150.0, 245.0, 340.0])   # от центра, передний ряд первым
    columns: list[float] = field(default_factory=lambda: [260.0, 130.0, 0.0])  # глубина колонны 0, 1, 2 ...
    slant: float = 15            # сдвиг к центру на каждые 100 глубины
    fly_height: float = 40       # высота парения летающих
    ground_texture: str = ""     # assets/grounds; пусто — однотонная земля earth
    ground_tile: float = 160     # сторона плитки текстуры в единицах мира
    ground_depth: float = 700    # как далеко тянется земля; дальше виден задник
    ground_darken: float = 0
    backdrop: str = ""           # assets/backgrounds; пусто — градиент неба sky
    backdrop_line: float = 85    # где у картинки задника земля, % высоты от верха
    backdrop_width: float = 100  # ширина задника, % ширины поля
    backdrop_darken: float = 0
    haze: float = 35             # дымка вдали, % (цвет sky)
    sky: list[int] = field(default_factory=lambda: [22, 24, 32])
    earth: list[int] = field(default_factory=lambda: [44, 46, 48])
    objects: list[SceneObject] = field(default_factory=list)

    # --- файл ---

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneConfig":
        """Неизвестные ключи пропускаются, значения обрезаются до пределов."""
        known = {f.name for f in fields(cls)}
        values = {k: v for k, v in data.items() if k in known}
        values["objects"] = [SceneObject.from_dict(o) for o in values.get("objects", []) if isinstance(o, dict) and o.get("image")]
        scene = cls(**values)
        scene.clamp()
        return scene

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def copy(self) -> "SceneConfig":
        return SceneConfig.from_dict(json.loads(json.dumps(self.to_dict())))

    def clamp(self) -> None:
        for f in fields(self):
            if f.name in LIMITS:
                low, high = LIMITS[f.name]
                setattr(self, f.name, float(min(high, max(low, getattr(self, f.name)))))
        self.horizon = min(self.horizon, self.ground - 20)        # горизонт всегда выше земли
        self.rows = [float(min(LIMITS["row"][1], max(LIMITS["row"][0], v))) for v in self.rows[:MAX_LINES]] or [150.0]
        self.columns = [float(min(LIMITS["column"][1], max(LIMITS["column"][0], v)))
                        for v in self.columns[:MAX_LINES]] or [0.0]
        self.sky = [int(min(255, max(0, c))) for c in (list(self.sky) + [0, 0, 0])[:3]]
        self.earth = [int(min(255, max(0, c))) for c in (list(self.earth) + [0, 0, 0])[:3]]
        for obj in self.objects:
            obj.clamp()

    def version(self) -> str:
        """Слепок всего, от чего зависит задник с землёй: меняется — задник перерисовывается."""
        data = self.to_dict()
        data["objects"] = [o for o in data["objects"] if o["layer"] == "ground"]
        for key in ("name", "human_height", "rows", "columns", "slant", "fly_height"):
            data.pop(key)
        return json.dumps(data, sort_keys=True)

    # --- проекция и сетка ---

    def projection(self) -> Projection:
        return Projection(self.horizon, self.ground, self.focal, FIELD_CENTER_X)

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
        """Глубина колонны формации; ближняя колонна всегда на последней линии,
        лишние колонны большого поля уходят вглубь с тем же шагом."""
        near_first = list(reversed(self.columns))
        return self.line(near_first, cols - 1 - col)

    def cell(self, side: str, row: int, col: int, cols: int) -> tuple[float, float]:
        """Мировые (x, z) клетки формации; side: left — отряд игрока, right — противник."""
        z = self.column_depth(col, cols)
        distance = self.row_distance(row) - self.slant * z / 100
        return (-distance if side == "left" else distance), z


def _images(folder: Path) -> list[str]:
    if not folder.exists():
        return []
    return sorted(p.name for p in folder.iterdir() if p.suffix.lower() in IMAGE_TYPES)


def backdrop_files() -> list[str]:
    return _images(BACKDROP_DIR)


def ground_files() -> list[str]:
    return _images(GROUND_DIR)


def prop_files(folder: Optional[Path] = None) -> list[str]:
    return _images(folder or PROPS_DIR)


class SceneStore:
    """Сцены в папке: <id>.json. id — имя файла, его не меняют; название сцены — поле name."""

    def __init__(self, folder: Path = SCENES_DIR):
        self.folder = Path(folder)

    def ids(self) -> list[str]:
        if not self.folder.exists():
            return []
        return sorted(p.stem for p in self.folder.glob("*.json"))

    def path(self, scene_id: str) -> Path:
        return self.folder / f"{scene_id}.json"

    def load(self, scene_id: str) -> SceneConfig:
        """Сцена по id; если файла нет — сцена по умолчанию."""
        path = self.path(scene_id)
        if not path.exists():
            return SceneConfig()
        return SceneConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, scene_id: str, scene: SceneConfig) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path(scene_id).write_text(json.dumps(scene.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def new_id(self, name: str) -> str:
        """Свободный id из названия: латиница, цифры, подчёркивания."""
        base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "scene"
        scene_id, n = base, 2
        while self.path(scene_id).exists():
            scene_id, n = f"{base}_{n}", n + 1
        return scene_id

    def create(self, name: str, source: Optional[SceneConfig] = None) -> str:
        """Новая сцена (копия source или по умолчанию); возвращает её id."""
        scene = source.copy() if source is not None else SceneConfig()
        scene.name = name
        scene_id = self.new_id(name)
        self.save(scene_id, scene)
        return scene_id

    def delete(self, scene_id: str) -> None:
        path = self.path(scene_id)
        if path.exists():
            path.unlink()

    def names(self) -> dict[str, str]:
        """id -> название, для списка в редакторе."""
        result = {}
        for scene_id in self.ids():
            try:
                result[scene_id] = json.loads(self.path(scene_id).read_text(encoding="utf-8")).get("name") or scene_id
            except (OSError, ValueError):
                result[scene_id] = scene_id
        return result
