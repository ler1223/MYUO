"""Расписание показа: что в какой момент делает каждый боец и что появляется на экране.

Время — мс от начала боя. Режиссёр (battle.director) кладёт сюда сцены актов, показ (battle.show)
спрашивает состояние на момент now. Всё по времени, ничего не «доигрывается» само: можно
перемотать, пропустить, повторить.

- Clip — анимация бойца: части по очереди (у последней можно «по кругу»); после конца — then:
  stance (боевая стойка по кругу) или hold (последний кадр).
- Move — перемещение бойца из точки в точку за время (с дугой — прыжок).
- Fx — эффект Battle_Effect в точке (или на бойце), Shot — снаряд (летит из точки в точку),
  Popup — цифры и надписи над бойцом,
  Banner — лента с названием навыка, Plate — что показывает плашка бойца с этого момента,
  Fade — исчезновение (гибель), Focus — куда смотрит камера.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from typing import Optional

from .stage import Spot


@dataclass
class Part:
    anim: str
    ms: float                  # длительность части (растянутая или своя)
    native: float              # своя длительность анимации
    loop: bool = False


@dataclass
class Clip:
    start: float
    parts: list[Part]
    then: str = "stance"       # stance | hold

    @property
    def end(self) -> float:
        return self.start + sum(p.ms for p in self.parts if not p.loop) if not self.parts or not self.parts[-1].loop \
            else math.inf

    def at(self, t: float) -> Optional[tuple[str, float]]:
        """(анимация, мс внутри неё) в момент t или None — клип кончился."""
        local = t - self.start
        for part in self.parts:
            if part.loop:                      # по кругу: циклы у треков свои (i0), время не заворачивается
                return part.anim, local
            if local < part.ms:
                return part.anim, local * part.native / max(1.0, part.ms)
            local -= part.ms
        return None


@dataclass
class Move:
    start: float
    ms: float
    a: Spot
    b: Spot
    arc: float = 0.0           # высота дуги (прыжок)
    ease: str = "linear"       # linear | out

    def at(self, t: float) -> tuple[float, float, float]:
        k = min(1.0, max(0.0, (t - self.start) / max(1.0, self.ms)))
        if self.ease == "out":
            k = 1 - (1 - k) ** 2
        x = self.a.x + (self.b.x - self.a.x) * k
        y = self.a.y + (self.b.y - self.a.y) * k - self.arc * math.sin(math.pi * k)
        s = self.a.scale + (self.b.scale - self.a.scale) * k
        return x, y, s


@dataclass
class Fx:
    start: float
    anim: str
    x: float
    y: float
    scale: float
    flip: bool
    ms: float
    front: bool = True         # поверх бойцов (иначе — за ними, у земли)
    uid: Optional[int] = None  # привязан к бойцу: x, y — смещение от его ног


@dataclass
class Shot:
    """Снаряд Battle_Effect: анимация по кругу летит из a в b за ms (нарисована летящей вправо).
    fall — навесной: ускорение падения в единицах за тик² (UO: *_PARABOLASHOT_FALLSPEED)."""

    start: float
    anim: str
    a: tuple[float, float]
    b: tuple[float, float]
    ms: float
    scale: float
    fall: float = 0.0
    tick_ms: float = 1000 / 60
    path: tuple[tuple[float, float], ...] = ()   # точки (доля пути, подъём долей расстояния)

    def at(self, t: float) -> tuple[float, float, float, bool]:
        """(x, y, угол в градусах против часовой, отражён) в момент t."""
        T = max(1.0, self.ms)
        u = min(T, max(0.0, t - self.start))
        dx, dy = self.b[0] - self.a[0], self.b[1] - self.a[1]
        if self.path:
            from .animation import curve_point
            dist = math.hypot(dx, dy)
            k = u / T
            along, lift = curve_point(self.path, k)
            x = self.a[0] + dx * along
            y = self.a[1] + dy * along + lift * dist
            e = 0.004
            a0, l0 = curve_point(self.path, max(0.0, k - e))
            a1, l1 = curve_point(self.path, min(1.0, k + e))
            vx = dx * (a1 - a0)
            vy = dy * (a1 - a0) + (l1 - l0) * dist
            flip = vx < 0
            angle = math.degrees(math.atan2(vy, -vx) if flip else math.atan2(-vy, vx))
            return x, y, angle, flip
        g = self.fall / (self.tick_ms * self.tick_ms)
        vy0 = (dy - g * T * T / 2) / T
        x = self.a[0] + dx * u / T
        y = self.a[1] + vy0 * u + g * u * u / 2
        vx, vy = dx / T, vy0 + g * u
        flip = vx < 0
        angle = math.degrees(math.atan2(vy, -vx) if flip else math.atan2(-vy, vx))
        return x, y, angle, flip


@dataclass
class Popup:
    start: float
    uid: int
    anims: list[str]           # раскладки Interface: NUM_* (число) и STR_* (надпись)
    value: Optional[int]
    ms: float


@dataclass
class Banner:
    start: float
    end: float
    text: str
    side: int                  # 0 — слева (нападающие), 1 — справа
    passive: bool


@dataclass
class Plate:
    time: float
    hp: int
    max_hp: int
    ap: int
    pp: int
    alive: bool = True


@dataclass
class Focus:
    start: float
    ms: float
    box: Optional[tuple[float, float, float, float]]    # None — обзор


@dataclass
class Track:
    """Всё о бойце по времени."""

    clips: list[Clip] = field(default_factory=list)
    moves: list[Move] = field(default_factory=list)
    plates: list[Plate] = field(default_factory=list)
    fade: Optional[tuple[float, float]] = None      # (начало, длительность) исчезновения

    def clip_at(self, t: float) -> Optional[Clip]:
        starts = [c.start for c in self.clips]
        i = bisect.bisect_right(starts, t) - 1
        return self.clips[i] if i >= 0 else None

    def move_at(self, t: float) -> Optional[Move]:
        current = None
        for move in self.moves:
            if move.start <= t:
                current = move
        return current

    def plate_at(self, t: float) -> Optional[Plate]:
        current = None
        for plate in self.plates:
            if plate.time <= t:
                current = plate
        return current

    def alpha(self, t: float) -> float:
        if self.fade is None or t < self.fade[0]:
            return 1.0
        return max(0.0, 1 - (t - self.fade[0]) / max(1.0, self.fade[1]))

    def add_clip(self, clip: Clip) -> None:
        self.clips = [c for c in self.clips if c.start < clip.start] + [clip]


class Timeline:
    def __init__(self):
        self.tracks: dict[int, Track] = {}
        self.fx: list[Fx] = []
        self.shots: list[Shot] = []
        self.popups: list[Popup] = []
        self.banners: list[Banner] = []
        self.focus: list[Focus] = []
        self.end = 0.0             # когда доиграет всё запланированное

    def track(self, uid: int) -> Track:
        return self.tracks.setdefault(uid, Track())

    def prune(self, t: float, keep: float = 5000) -> None:
        """Убрать давно кончившееся (эффекты, надписи)."""
        self.fx = [f for f in self.fx if f.start + f.ms > t - keep]
        self.shots = [s for s in self.shots if s.start + s.ms > t - keep]
        self.popups = [p for p in self.popups if p.start + p.ms > t - keep]
        self.banners = [b for b in self.banners if b.end > t - keep]
