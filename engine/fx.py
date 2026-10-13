"""Трёхмерные эффекты боя: частицы, снаряды, разрезы, кольца, столбы, лучи, купола, текст.

Эффект живёт в мире (x, y, z) с момента start в течение duration и отдаёт рендереру части
(render.Part) со слоем и глубиной. Поэтому эффект правильно перекрывается юнитами:
- кольца и круги рун лежат на земле в перспективе (слой земли, под юнитами);
- столб пламени за юнитом скрыт им, перед юнитом — закрывает его;
- обвивающие эффекты (кольцо на высоте, купол, облако частиц) делятся на заднюю половину
  (за юнитом) и переднюю (перед ним);
- надписи и вспышка экрана — поверх всего.
Свечение рисуется сложением цветов (BLEND_RGB_ADD). О бое модуль ничего не знает.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pygame

from pygame_ui import FONT_NAMES

from .projection import World
from .render import BEHIND, GROUND, IN_FRONT, OVERLAY, UPRIGHT, Part, View

Color = tuple[int, int, int]

ELEMENT_COLORS: dict[str, Color] = {
    "fire": (255, 120, 30),
    "ice": (120, 200, 255),
    "lightning": (200, 200, 255),
    "light": (255, 225, 120),
    "dark": (170, 70, 230),
    "poison": (110, 220, 60),
    "arcane": (110, 150, 255),
    "steel": (235, 235, 245),
    "heal": (120, 255, 150),
    "buff": (255, 210, 90),
    "debuff": (190, 80, 230),
    "guard": (110, 170, 255),
}
SKY_HEIGHT = 900            # «небо» для лучей и молний, единицы мира над землёй
HIT_MS = 260                # сколько длится реакция юнита на попадание
FRAME_MS = 16               # скорости частиц заданы в единицах мира за кадр 60 FPS


# --- общие помощники ----------------------------------------------------------

@lru_cache(maxsize=None)
def fx_font(size: int, numbers: bool = False) -> pygame.font.Font:
    """Шрифт эффектов нужного размера в пикселях окна (числа крупным жирным шрифтом)."""
    size = max(8, size)
    return pygame.font.Font(None, size) if numbers else pygame.font.SysFont(FONT_NAMES, size, bold=True)


GLOW_LEVELS = 16            # ступеней яркости свечения: гаснущие свечения берут картинки из кэша
_glow_cache: dict[tuple[Color, int], pygame.Surface] = {}


def glow_sprite(color: Color, radius: int) -> pygame.Surface:
    """Круглое свечение: яркий центр, мягко гаснущие края. Рисуется с BLEND_RGB_ADD."""
    radius = max(2, int(radius))
    key = (color, radius)
    if key not in _glow_cache:
        if len(_glow_cache) > 4000:
            _glow_cache.clear()
        surface = pygame.Surface((radius * 2, radius * 2))
        step = max(1, radius // 40)            # у больших свечений кольца пореже
        for r in range(radius, 0, -step):
            k = (1 - r / radius) ** 1.8
            pygame.draw.circle(surface, tuple(min(255, int(c * k)) for c in color), (radius, radius), r)
        _glow_cache[key] = surface
    return _glow_cache[key]


def add_glow(screen: pygame.Surface, pos: tuple[float, float], color: Color, radius: float, strength: float = 1.0) -> None:
    """Свечение в пикселях окна."""
    if strength <= 0.02 or radius < 2:
        return
    k = round(min(1.0, strength) * GLOW_LEVELS) / GLOW_LEVELS
    sprite = glow_sprite(tuple(int(c * k) for c in color), int(radius) // 2 * 2 or 2)
    screen.blit(sprite, sprite.get_rect(center=(int(pos[0]), int(pos[1]))), special_flags=pygame.BLEND_RGB_ADD)


def add_lines(screen: pygame.Surface, points: list[tuple[int, int]], color: Color, width: int, closed: bool = False) -> None:
    """Светящаяся ломаная (сложением цветов) в пикселях окна."""
    if len(points) < 2:
        return
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    pad = width + 2
    box = pygame.Rect(min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + pad * 2 + 1, max(ys) - min(ys) + pad * 2 + 1)
    clip = screen.get_clip()
    box = box.clip(clip) if clip else box
    if box.width <= 0 or box.height <= 0:
        return
    layer = pygame.Surface(box.size)
    pygame.draw.lines(layer, color, closed, [(x - box.x, y - box.y) for x, y in points], max(1, width))
    screen.blit(layer, box.topleft, special_flags=pygame.BLEND_RGB_ADD)


def lerp(a, b, t: float):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def scaled_color(color: Color, k: float) -> Color:
    return tuple(max(0, min(255, int(c * k))) for c in color)


def circle_points(center: World, radius: float, y: float, start: float, end: float, steps: int = 24) -> list[World]:
    """Точки окружности на высоте y вокруг center в плоскости земли (углы в радианах;
    0..pi — дальняя половина, pi..2pi — ближняя)."""
    return [(center[0] + math.cos(a) * radius, y, center[2] + math.sin(a) * radius)
            for a in (start + (end - start) * i / steps for i in range(steps + 1))]


# --- эффекты ------------------------------------------------------------------

@dataclass
class Effect:
    start: int
    duration: int

    def progress(self, now: int) -> Optional[float]:
        """Доля прошедшего времени 0..1; None, если эффект ещё не начался или уже кончился."""
        if now < self.start or now > self.start + self.duration:
            return None
        return (now - self.start) / max(1, self.duration)

    def parts(self, now: int) -> list[Part]:
        """Части для рендерера; по умолчанию одна стоящая часть на глубине depth()."""
        t = self.progress(now)
        if t is None:
            return []
        return [Part(UPRIGHT, self.depth(t), lambda s, v, t=t: self.draw(s, v, t))]

    def depth(self, t: float) -> float:
        return 0.0

    def draw(self, screen: pygame.Surface, view: View, t: float) -> None: ...


@dataclass
class Particle:
    pos: World
    vel: World                 # единиц мира за кадр 60 FPS
    born: int
    life: int
    color: Color
    size: float
    gravity: float = 0.0       # единиц мира за кадр^2, вниз
    shape: str = "glow"        # glow | spark | flake | star | bubble | shard

    def at(self, now: int) -> Optional[tuple[World, float]]:
        """(позиция, доля оставшейся жизни) в момент now; None, если частицы нет."""
        age = now - self.born
        if age < 0 or age > self.life:
            return None
        f = age / FRAME_MS
        x = self.pos[0] + self.vel[0] * f
        y = max(0.0, self.pos[1] + self.vel[1] * f - 0.5 * self.gravity * f * f)
        z = self.pos[2] + self.vel[2] * f
        return (x, y, z), 1 - age / self.life


@dataclass
class Burst(Effect):
    """Облако частиц вокруг center: дальние частицы рисуются за юнитом, ближние — перед ним."""

    center: World = (0, 0, 0)
    particles: list[Particle] = field(default_factory=list)

    def parts(self, now: int) -> list[Part]:
        if now < self.start or now > self.start + self.duration:
            return []
        back, front = [], []
        for p in self.particles:
            state = p.at(now)
            if state is not None:
                (back if state[0][2] >= self.center[2] else front).append((p, state))
        z = self.center[2]
        return [Part(UPRIGHT, z + BEHIND, lambda s, v: self._draw(s, v, back), 1),
                Part(UPRIGHT, z + IN_FRONT, lambda s, v: self._draw(s, v, front), 1)]

    @staticmethod
    def _draw(screen: pygame.Surface, view: View, items) -> None:
        for p, (pos, k) in items:
            x, y, scale = view.p(pos)
            size = p.size * scale
            if p.shape == "spark":
                tail = view.xy((pos[0] - p.vel[0] * 3, pos[1] - p.vel[1] * 3, pos[2] - p.vel[2] * 3))
                pygame.draw.line(screen, p.color, (x, y), tail, max(1, int(size * k)))
                add_glow(screen, (x, y), p.color, size * 3, k * 0.6)
            elif p.shape == "flake":
                r = max(1, int(size * 1.6 * k))
                for a in (0, math.pi / 3, 2 * math.pi / 3):
                    ox, oy = math.cos(a) * r, math.sin(a) * r
                    pygame.draw.line(screen, (230, 245, 255), (x - ox, y - oy), (x + ox, y + oy), max(1, int(scale)))
                add_glow(screen, (x, y), p.color, size * 3, k * 0.5)
            elif p.shape == "star":
                r = size * 2 * k + 2 * scale
                pts = [(x + math.cos(a) * (r if i % 2 == 0 else r * 0.45), y + math.sin(a) * (r if i % 2 == 0 else r * 0.45))
                       for i, a in enumerate(i * math.pi / 5 - math.pi / 2 for i in range(10))]
                pygame.draw.polygon(screen, (255, 240, 140), pts)
                add_glow(screen, (x, y), p.color, r * 2.5, k * 0.6)
            elif p.shape == "bubble":
                pygame.draw.circle(screen, p.color, (x, y), max(1, int(size * (1.4 - k * 0.4))), max(1, int(scale)))
            elif p.shape == "shard":
                r = size * 2
                pygame.draw.polygon(screen, (220, 240, 255), [(x, y - r), (x + r * 0.5, y), (x, y + r), (x - r * 0.5, y)])
                add_glow(screen, (x, y), p.color, r * 2, k * 0.7)
            else:
                add_glow(screen, (x, y), p.color, size * 3 * (0.5 + k), k)


@dataclass
class Projectile(Effect):
    """Снаряд от source к target: стрела, огненный шар, осколки льда."""

    source: World = (0, 0, 0)
    target: World = (0, 0, 0)
    kind: str = "orb"         # orb | arrow | shards
    color: Color = (255, 255, 255)
    arc: float = 0.0          # высота дуги, единицы мира
    size: float = 1.0

    def point(self, t: float) -> World:
        x, y, z = lerp(self.source, self.target, t)
        return x, y + math.sin(t * math.pi) * self.arc, z

    def depth(self, t: float) -> float:
        return self.point(t)[2] - 1

    def draw(self, screen: pygame.Surface, view: View, t: float) -> None:
        t = ease_out(t) if self.kind == "orb" else t
        head = self.point(t)
        hx, hy, k = view.p(head)
        if self.kind == "arrow":
            tail = view.xy(self.point(max(0.0, t - 0.08)))
            mid = (tail[0] + (hx - tail[0]) * 0.7, tail[1] + (hy - tail[1]) * 0.7)
            w = max(1, round(3 * k))
            pygame.draw.line(screen, (90, 70, 50), tail, (hx, hy), w)
            pygame.draw.line(screen, (230, 230, 230), mid, (hx, hy), w)
            add_glow(screen, (hx, hy), self.color, 10 * k, 0.7)
            for i in range(1, 6):          # светящийся след
                add_glow(screen, view.xy(self.point(max(0.0, t - i * 0.03))), self.color, (7 - i) * k, 0.5)
        elif self.kind == "shards":
            for i, offset in enumerate((-10, 0, 10)):
                x, y, z = self.point(max(0.0, t - i * 0.05))
                px, py, kk = view.p((x, y + offset, z))
                pts = [(px + 9 * kk, py), (px - 3 * kk, py - 4 * kk), (px - 7 * kk, py), (px - 3 * kk, py + 4 * kk)]
                pygame.draw.polygon(screen, (220, 240, 255), pts)
                add_glow(screen, (px, py), self.color, 12 * kk, 0.8)
        else:
            for i in range(8, 0, -1):          # хвост из гаснущих свечений
                add_glow(screen, view.xy(self.point(max(0.0, t - i * 0.035))), self.color,
                         (6 + 14 * (1 - i / 8)) * self.size * k, 0.35)
            add_glow(screen, (hx, hy), self.color, 26 * self.size * k, 1.0)
            add_glow(screen, (hx, hy), (255, 255, 230), 10 * self.size * k, 1.0)


@dataclass
class Slash(Effect):
    """Дуга разреза поперёк цели, чуть перед ней."""

    center: World = (0, 0, 0)
    color: Color = (235, 235, 245)
    radius: float = 46
    facing: int = 1           # 1: удар слева направо

    def depth(self, t: float) -> float:
        return self.center[2] - 2

    def draw(self, screen: pygame.Surface, view: View, t: float) -> None:
        sweep = ease_out(min(1.0, t * 1.6))
        fade = 1 - max(0.0, (t - 0.45) / 0.55)
        cx, cy, k = view.p(self.center)
        r = self.radius * k
        start, end = -2.3, -2.3 + 2.6 * sweep
        steps = 18
        for i in range(steps):
            a = start + (end - start) * i / steps
            thickness = 1 + 7 * math.sin(math.pi * i / steps)
            x = cx + self.facing * math.cos(a) * r
            y = cy + math.sin(a) * r * 0.8 + r * 0.35
            add_glow(screen, (x, y), self.color, (6 + thickness * 1.6) * k, 0.9 * fade)
            if i % 2 == 0:
                pygame.draw.circle(screen, (255, 255, 255), (x, y), max(1, round(thickness * 0.45 * fade * k)))


@dataclass
class Thrust(Effect):
    """Прямой выпад сквозь цель (колющий удар, промах)."""

    center: World = (0, 0, 0)
    color: Color = (235, 235, 245)
    facing: int = 1

    def depth(self, t: float) -> float:
        return self.center[2] - 2

    def draw(self, screen: pygame.Surface, view: View, t: float) -> None:
        length = 90 * ease_out(min(1.0, t * 2))
        fade = 1 - t
        x0 = self.center[0] - self.facing * 50
        a = view.xy((x0, self.center[1], self.center[2]))
        b, k = view.p((x0 + self.facing * length, self.center[1], self.center[2]))[:2], view.p(self.center)[2]
        for i in range(12):
            add_glow(screen, lerp(a, b, i / 11), self.color, (5 + i * 0.8) * k, 0.8 * fade)
        pygame.draw.line(screen, (255, 255, 255), a, b, max(1, round(3 * fade * k)))


@dataclass
class Ring(Effect):
    """Расходящаяся волна. На земле (y = 0) лежит под юнитами; на высоте обвивает юнита:
    дальняя половина за ним, ближняя перед ним."""

    center: World = (0, 0, 0)
    color: Color = (255, 255, 255)
    radius_from: float = 10
    radius_to: float = 60
    thickness: float = 4

    def parts(self, now: int) -> list[Part]:
        t = self.progress(now)
        if t is None:
            return []
        z = self.center[2]
        if self.center[1] <= 0:
            return [Part(GROUND, z, lambda s, v: self._draw(s, v, t, 0, math.tau))]
        return [Part(UPRIGHT, z + BEHIND, lambda s, v: self._draw(s, v, t, 0, math.pi)),
                Part(UPRIGHT, z + IN_FRONT, lambda s, v: self._draw(s, v, t, math.pi, math.tau))]

    def _draw(self, screen: pygame.Surface, view: View, t: float, a0: float, a1: float) -> None:
        r = self.radius_from + (self.radius_to - self.radius_from) * ease_out(t)
        points = [view.xy(p) for p in circle_points(self.center, r, self.center[1], a0, a1, 32)]
        k = view.p(self.center)[2]
        add_lines(screen, points, scaled_color(self.color, 1 - t), round(self.thickness * (1 - t) * k + 1), a1 - a0 >= math.tau)


@dataclass
class WrapRing(Effect):
    """Кольца, поднимающиеся вокруг юнита (лечение, бафф): обвивают его спереди и сзади."""

    center: World = (0, 0, 0)
    color: Color = (120, 255, 150)
    radius: float = 40
    height: float = 160
    rings: int = 3

    def parts(self, now: int) -> list[Part]:
        t = self.progress(now)
        if t is None:
            return []
        z = self.center[2]
        return [Part(UPRIGHT, z + BEHIND, lambda s, v: self._draw(s, v, t, 0, math.pi)),
                Part(UPRIGHT, z + IN_FRONT, lambda s, v: self._draw(s, v, t, math.pi, math.tau))]

    def _draw(self, screen: pygame.Surface, view: View, t: float, a0: float, a1: float) -> None:
        k = view.p(self.center)[2]
        for i in range(self.rings):
            u = t * 1.4 - i * 0.2             # кольца поднимаются одно за другим
            if not 0 <= u <= 1:
                continue
            y = self.center[1] + self.height * ease_out(u)
            strength = math.sin(math.pi * u)
            points = [view.xy(p) for p in circle_points(self.center, self.radius * (1 - 0.3 * u), y, a0, a1, 24)]
            add_lines(screen, points, scaled_color(self.color, strength), max(1, round(3 * k)))


@dataclass
class RuneCircle(Effect):
    """Магический круг на земле в перспективе: два кольца, насечки и треугольник, вращается."""

    center: World = (0, 0, 0)
    color: Color = (255, 140, 60)
    radius: float = 40

    def parts(self, now: int) -> list[Part]:
        t = self.progress(now)
        if t is None:
            return []
        return [Part(GROUND, self.center[2], lambda s, v: self._draw(s, v, t, now))]

    def _draw(self, screen: pygame.Surface, view: View, t: float, now: int) -> None:
        strength = min(1.0, t / 0.2) * min(1.0, (1 - t) / 0.3)
        color = scaled_color(self.color, strength)
        r = self.radius * (0.7 + 0.3 * ease_out(min(1.0, t / 0.3)))
        c = (self.center[0], 0.0, self.center[2])
        k = view.p(c)[2]
        w = max(1, round(2 * k))
        for f in (1.0, 0.78):
            add_lines(screen, [view.xy(p) for p in circle_points(c, r * f, 0, 0, math.tau, 40)], color, w, True)
        spin = (now - self.start) / 900
        for i in range(12):                   # насечки рун между кольцами
            a = spin + i * math.tau / 12
            p0 = (c[0] + math.cos(a) * r * 0.8, 0, c[2] + math.sin(a) * r * 0.8)
            p1 = (c[0] + math.cos(a + 0.12) * r * 0.97, 0, c[2] + math.sin(a + 0.12) * r * 0.97)
            add_lines(screen, [view.xy(p0), view.xy(p1)], color, w)
        tri = [(c[0] + math.cos(-spin * 1.5 + i * math.tau / 3) * r * 0.76, 0,
                c[2] + math.sin(-spin * 1.5 + i * math.tau / 3) * r * 0.76) for i in range(3)]
        add_lines(screen, [view.xy(p) for p in tri], color, w, True)
        add_glow(screen, view.xy(c), self.color, r * 0.9 * k, 0.35 * strength)


@dataclass
class Pillar(Effect):
    """Столб пламени (или света), вырастающий из земли в точке base."""

    base: World = (0, 0, 0)
    color: Color = (255, 120, 30)
    height: float = 110
    thickness: float = 26
    seed: int = 0

    def depth(self, t: float) -> float:
        return self.base[2]

    def draw(self, screen: pygame.Surface, view: View, t: float) -> None:
        grow = ease_out(min(1.0, t / 0.3)) * min(1.0, (1 - t) / 0.35)
        rng = random.Random(self.seed + int(t * self.duration) // 50)
        x, bottom, k = view.p(self.base)
        h = self.height * k * grow * rng.uniform(0.9, 1.05)
        w = max(2, int(self.thickness * k * (0.6 + 0.4 * grow)))
        if h < 2:
            return
        layer = pygame.transform.smoothscale(pillar_texture(self.color), (w, int(h)))
        screen.blit(layer, (int(x - w / 2), int(bottom - h)), special_flags=pygame.BLEND_RGB_ADD)
        add_glow(screen, (x, bottom), self.color, w * 1.6, grow)


@lru_cache(maxsize=64)
def pillar_texture(color: Color) -> pygame.Surface:
    """Текстура столба 32x128: ярче в середине и у земли, к верху тоньше и темнее."""
    w, h = 32, 128
    surface = pygame.Surface((w, h))
    for j in range(h):
        up = 1 - j / h                        # 0 у верха, 1 у земли
        for i in range(w):
            across = max(0.0, 1 - abs(i - w / 2) / (w / 2 * (0.4 + 0.6 * up))) ** 1.5
            k = across * up ** 0.7
            surface.set_at((i, j), (min(255, int(color[0] * k + 120 * k * up)), min(255, int(color[1] * k + 40 * k * up)),
                                    int(color[2] * k)))
    return surface


@dataclass
class Beam(Effect):
    """Столб света с неба на юнита: юнит стоит внутри — за ним яркая часть, перед ним прозрачная."""

    center: World = (0, 0, 0)
    color: Color = (255, 225, 120)
    thickness: float = 34

    def parts(self, now: int) -> list[Part]:
        t = self.progress(now)
        if t is None:
            return []
        z = self.center[2]
        return [Part(UPRIGHT, z + BEHIND, lambda s, v: self._draw(s, v, t, 1.0)),
                Part(UPRIGHT, z + IN_FRONT, lambda s, v: self._draw(s, v, t, 0.35))]

    def _draw(self, screen: pygame.Surface, view: View, t: float, power: float) -> None:
        strength = math.sin(t * math.pi) * power
        x, bottom, k = view.p((self.center[0], 0, self.center[2]))
        top = view.xy((self.center[0], SKY_HEIGHT, self.center[2]))[1]
        if view.cam.clip is not None:
            top = max(top, view.cam.clip.top)
        w = max(2, int(self.thickness * k * (0.6 + 0.4 * math.sin(t * math.pi))))
        height = max(1, bottom - top)
        layer = pygame.Surface((w, height))
        for i in range(w):
            c = (1 - abs(i - w / 2) / (w / 2)) ** 2 * strength
            pygame.draw.line(layer, scaled_color(self.color, c), (i, 0), (i, height))
        screen.blit(layer, (int(x - w / 2), top), special_flags=pygame.BLEND_RGB_ADD)
        add_glow(screen, (x, bottom), self.color, 40 * k, strength)


@dataclass
class Bolt(Effect):
    """Молния с неба в target, мерцает."""

    target: World = (0, 0, 0)
    color: Color = (200, 200, 255)
    seed: int = 0
    lean: float = 20          # верх молнии сдвинут вбок

    def depth(self, t: float) -> float:
        return self.target[2] - 1

    def draw(self, screen: pygame.Surface, view: View, t: float) -> None:
        rng = random.Random(self.seed + int(t * self.duration) // 40)   # новая форма каждые 40 мс
        source = (self.target[0] + self.lean, self.target[1] + SKY_HEIGHT * 0.6, self.target[2])
        k = view.p(self.target)[2]
        points = [view.xy(source)]
        for i in range(1, 9):
            x, y, z = lerp(source, self.target, i / 9)
            points.append(view.xy((x + rng.uniform(-14, 14), y + rng.uniform(-6, 6), z)))
        points.append(view.xy(self.target))
        fade = 1 - t
        for point in points:
            add_glow(screen, point, self.color, 14 * k, 0.6 * fade)
        pygame.draw.lines(screen, (240, 240, 255), False, points, max(1, round(4 * fade * k)))


@dataclass
class Glint(Effect):
    """Блик-звёздочка: прицеливание, готовность, наконечник."""

    pos: World = (0, 0, 0)
    color: Color = (255, 250, 220)
    size: float = 22

    def depth(self, t: float) -> float:
        return self.pos[2] - 3

    def draw(self, screen: pygame.Surface, view: View, t: float) -> None:
        strength = math.sin(t * math.pi)
        x, y, k = view.p(self.pos)
        r = self.size * k * strength
        w = max(1, round(2 * k * strength))
        pygame.draw.line(screen, (255, 255, 255), (x - r, y), (x + r, y), w)
        pygame.draw.line(screen, (255, 255, 255), (x, y - r * 0.7), (x, y + r * 0.7), w)
        add_glow(screen, (x, y), self.color, r * 0.9, strength)


@dataclass
class Dome(Effect):
    """Купол щита вокруг center: дальняя половина за юнитом, ближняя перед ним."""

    center: World = (0, 0, 0)
    color: Color = (110, 170, 255)
    radius: float = 50

    def parts(self, now: int) -> list[Part]:
        t = self.progress(now)
        if t is None:
            return []
        z = self.center[2]
        return [Part(UPRIGHT, z + BEHIND, lambda s, v: self._draw(s, v, t, 0, math.pi)),
                Part(UPRIGHT, z + IN_FRONT, lambda s, v: self._draw(s, v, t, math.pi, math.tau))]

    def _draw(self, screen: pygame.Surface, view: View, t: float, a0: float, a1: float) -> None:
        strength = min(1.0, t / 0.15) * min(1.0, (1 - t) / 0.4)
        r = self.radius * (0.8 + 0.2 * ease_out(min(1.0, t / 0.2)))
        k = view.p(self.center)[2]
        for i in range(5):                    # широты купола: кольца всё выше и уже
            lat = i / 5 * math.pi / 2
            ring = [view.xy(p) for p in circle_points(self.center, r * math.cos(lat), self.center[1] + r * math.sin(lat), a0, a1, 20)]
            add_lines(screen, ring, scaled_color(self.color, strength * (0.6 - i * 0.08)), max(1, round(3 * k)))
        for j in range(6):                    # меридианы своей половины
            a = a0 + (a1 - a0) * (j + 0.5) / 6
            arc = [view.xy((self.center[0] + math.cos(a) * r * math.cos(b), self.center[1] + r * math.sin(b),
                            self.center[2] + math.sin(a) * r * math.cos(b))) for b in (i * math.pi / 2 / 8 for i in range(9))]
            add_lines(screen, arc, scaled_color(self.color, strength * 0.35), max(1, round(2 * k)))


@dataclass
class ArrowRain(Effect):
    """Дождь стрел: стрелы падают сверху наискосок вокруг center, дальние за целью, ближние перед ней."""

    center: World = (0, 0, 0)
    color: Color = (255, 240, 200)
    count: int = 12
    spread: float = 50
    facing: int = 1
    seed: int = 0

    def _arrows(self) -> list[tuple[float, World]]:
        rng = random.Random(self.seed)
        return [(rng.uniform(0, 0.55), (self.center[0] + rng.uniform(-self.spread, self.spread), 0.0,
                                        self.center[2] + rng.uniform(-self.spread * 0.6, self.spread * 0.6)))
                for _ in range(self.count)]

    def parts(self, now: int) -> list[Part]:
        t = self.progress(now)
        if t is None:
            return []
        arrows = self._arrows()
        back = [a for a in arrows if a[1][2] >= self.center[2]]
        front = [a for a in arrows if a[1][2] < self.center[2]]
        z = self.center[2]
        return [Part(UPRIGHT, z + BEHIND, lambda s, v: self._draw(s, v, t, back)),
                Part(UPRIGHT, z + IN_FRONT, lambda s, v: self._draw(s, v, t, front))]

    def _draw(self, screen: pygame.Surface, view: View, t: float, arrows) -> None:
        for delay, land in arrows:
            k = (t - delay) / 0.4
            if not 0 <= k <= 1:
                continue
            start = (land[0] - 70 * self.facing, 220.0, land[2])
            head, tail = view.xy(lerp(start, land, k)), view.xy(lerp(start, land, max(0.0, k - 0.18)))
            scale = view.p(land)[2]
            w = max(1, round(2 * scale))
            pygame.draw.line(screen, (90, 70, 50), tail, head, w)
            pygame.draw.line(screen, (235, 235, 235), lerp(tail, head, 0.75), head, w)
            add_glow(screen, head, self.color, 6 * scale, 0.5)


@dataclass
class FloatText(Effect):
    """Всплывающий текст над точкой мира: число урона, MISS, CRIT!, название навыка."""

    pos: World = (0, 0, 0)
    text: str = ""
    color: Color = (255, 255, 255)
    size: int = 16            # высота шрифта в логических пикселях
    rise: float = 34
    pop: bool = True          # короткое «вздутие» в начале
    numbers: bool = False     # крупный цифровой шрифт

    def parts(self, now: int) -> list[Part]:
        t = self.progress(now)
        if t is None:
            return []
        return [Part(OVERLAY, 0, lambda s, v: self.draw(s, v, t), 2)]

    def draw(self, screen: pygame.Surface, view: View, t: float) -> None:
        scale = 1 + 0.6 * max(0.0, 1 - t * 6) if self.pop else 1
        font = fx_font(round(view.cam.s(self.size) * scale), self.numbers)
        img = font.render(self.text, True, self.color)
        outline = font.render(self.text, True, (15, 15, 20))
        alpha = int(255 * min(1.0, (1 - t) * 3))
        img.set_alpha(alpha)
        outline.set_alpha(alpha)
        x, y = view.xy(self.pos)
        rect = img.get_rect(center=(x, y - view.cam.s(self.rise * ease_out(t))))
        o = max(1, round(view.cam.s(2)))
        for dx, dy in ((-o, 0), (o, 0), (0, -o), (0, o)):
            screen.blit(outline, rect.move(dx, dy))
        screen.blit(img, rect)


@dataclass
class Flash(Effect):
    """Вспышка всего поля (крит, взрыв)."""

    color: Color = (255, 255, 255)
    strength: float = 0.5

    def parts(self, now: int) -> list[Part]:
        t = self.progress(now)
        if t is None:
            return []
        return [Part(OVERLAY, 0, lambda s, v: self.draw(s, v, t), 0)]

    def draw(self, screen: pygame.Surface, view: View, t: float) -> None:
        screen.fill(scaled_color(self.color, self.strength * (1 - t) ** 2), view.cam.clip, special_flags=pygame.BLEND_RGB_ADD)


# --- оружие -------------------------------------------------------------------

WEAPON_DIR = Path(__file__).resolve().parent.parent / "assets" / "weapons"
WEAPON_KINDS = ("sword", "axe", "spear", "dagger", "bow", "staff", "shield", "fist")
WEAPON_LENGTH = {"sword": 70, "axe": 64, "spear": 96, "dagger": 40, "bow": 70, "staff": 84, "shield": 54, "fist": 30}
_weapon_cache: dict[tuple[str, int], pygame.Surface] = {}


def _draw_weapon(kind: str, length: int) -> pygame.Surface:
    """Оружие кодом, остриём вверх, в поверхности length x length."""
    s = pygame.Surface((length, length), pygame.SRCALPHA)
    c = length / 2
    u = length / 100
    wood, steel, edge, gold = (120, 80, 45), (196, 202, 214), (245, 248, 255), (222, 182, 82)
    w = lambda v: max(1, round(v * u))
    if kind in ("sword", "dagger"):
        blade = 0.62 if kind == "sword" else 0.45
        top, guard = length * 0.04, length * (0.04 + blade)
        pygame.draw.polygon(s, steel, [(c, top), (c + w(6), top + w(10)), (c + w(5), guard), (c - w(5), guard), (c - w(6), top + w(10))])
        pygame.draw.line(s, edge, (c, top + w(4)), (c, guard - w(2)), w(2))
        pygame.draw.rect(s, gold, pygame.Rect(c - w(16), guard, w(32), w(5)), border_radius=w(2))
        pygame.draw.rect(s, wood, pygame.Rect(c - w(3), guard + w(5), w(6), w(16)))
    elif kind == "axe":
        pygame.draw.line(s, wood, (c, length * 0.12), (c, length * 0.98), w(6))
        pygame.draw.polygon(s, steel, [(c + w(2), length * 0.12), (c + w(30), length * 0.04), (c + w(36), length * 0.24),
                                       (c + w(30), length * 0.44), (c + w(2), length * 0.36)])
    elif kind == "spear":
        pygame.draw.line(s, wood, (c, length * 0.16), (c, length * 0.99), w(4))
        pygame.draw.polygon(s, steel, [(c, length * 0.01), (c + w(7), length * 0.1), (c, length * 0.2), (c - w(7), length * 0.1)])
    elif kind == "bow":
        box = pygame.Rect(c - w(30), length * 0.04, w(44), length * 0.92)
        pygame.draw.arc(s, wood, box, -math.pi / 2, math.pi / 2, w(6))
        pygame.draw.line(s, (230, 230, 220), (box.centerx, box.top + w(3)), (box.centerx, box.bottom - w(3)), w(1))
    elif kind == "staff":
        pygame.draw.line(s, wood, (c, length * 0.14), (c, length * 0.99), w(5))
        pygame.draw.circle(s, (150, 210, 255), (c, length * 0.1), w(9))
    elif kind == "shield":
        pts = [(c - w(40), length * 0.08), (c + w(40), length * 0.08), (c + w(36), length * 0.5), (c, length * 0.96),
               (c - w(36), length * 0.5)]
        pygame.draw.polygon(s, (60, 90, 160), pts)
        pygame.draw.polygon(s, steel, pts, w(6))
    else:   # fist
        pygame.draw.circle(s, (230, 190, 150), (c, c), w(30))
    return s


def weapon_sprite(kind: str, length: int) -> pygame.Surface:
    """Оружие остриём вверх: картинка assets/weapons/<вид>.png, иначе нарисованное кодом."""
    length = max(8, int(length))
    key = (kind, length)
    if key not in _weapon_cache:
        if len(_weapon_cache) > 300:
            _weapon_cache.clear()
        path = WEAPON_DIR / f"{kind}.png"
        if path.exists():
            image = pygame.image.load(str(path))
            k = length / max(image.get_size())
            _weapon_cache[key] = pygame.transform.smoothscale(image, (max(1, round(image.get_width() * k)),
                                                                      max(1, round(image.get_height() * k))))
        else:
            _weapon_cache[key] = _draw_weapon(kind, length)
    return _weapon_cache[key]


@dataclass
class WeaponStrike(Effect):
    """Оружие атакующего: появляется у него, летит к цели и бьёт; лук натягивается у стрелка,
    посох поднимается над заклинателем, щит встаёт перед целью."""

    kind: str = "sword"
    source: World = (0, 0, 0)
    target: World = (0, 0, 0)
    facing: int = 1

    def _place(self, t: float) -> tuple[World, float, float]:
        """(точка, угол, растяжение по ширине)."""
        if self.kind == "bow":
            return (self.source[0] + 34 * self.facing, self.source[1] + 6, self.source[2]), -12 * self.facing, \
                1 - 0.2 * math.sin(min(1.0, t / 0.6) * math.pi)
        if self.kind == "staff":
            return (self.source[0] + 18 * self.facing, self.source[1] + 30 + 20 * ease_out(min(1.0, t / 0.5)),
                    self.source[2]), -10 * self.facing, 1.0
        if self.kind == "shield":
            return lerp(self.source, self.target, 0.75), 0, 1.0
        travel = ease_out(min(1.0, t / 0.6))
        near = (self.target[0] - 40 * self.facing, self.target[1] + 20, self.target[2])
        x, y, z = lerp((self.source[0] + 20 * self.facing, self.source[1] + 30, self.source[2]), near, travel)
        y += math.sin(travel * math.pi) * 30
        strike = ease_out(min(1.0, max(0.0, (t - 0.55) / 0.3)))
        if self.kind == "spear":
            return (x + 40 * self.facing * strike, y - 20, z), -90 * self.facing, 1.0
        return (x, y, z), (40 - 160 * strike) * -self.facing, 1.0

    def depth(self, t: float) -> float:
        return self._place(t)[0][2] - 2

    def draw(self, screen: pygame.Surface, view: View, t: float) -> None:
        alpha = int(255 * min(min(1.0, t / 0.15), 1 - max(0.0, (t - 0.8) / 0.2)))
        pos, angle, stretch = self._place(t)
        x, y, k = view.p(pos)
        image = weapon_sprite(self.kind, WEAPON_LENGTH.get(self.kind, 60) * k)
        if self.facing < 0 and self.kind == "bow":
            image = pygame.transform.flip(image, True, False)
        if stretch != 1.0:
            image = pygame.transform.smoothscale(image, (max(1, int(image.get_width() * stretch)), image.get_height()))
        rotated = pygame.transform.rotate(image, angle)
        rotated.set_alpha(alpha)
        screen.blit(rotated, rotated.get_rect(center=(x, y)))


# --- система эффектов -----------------------------------------------------------

@dataclass
class FxSystem:
    """Все активные эффекты, дрожь поля и реакция юнитов на попадание (дрожь и вспышка)."""

    effects: list[Effect] = field(default_factory=list)
    shakes: list[tuple[int, int, float]] = field(default_factory=list)   # (начало, длительность, сила)
    hits: dict[int, int] = field(default_factory=dict)                   # uid -> когда по юниту попали
    rng: random.Random = field(default_factory=lambda: random.Random(7))

    def clear(self) -> None:
        self.effects.clear()
        self.shakes.clear()
        self.hits.clear()

    def add(self, effect: Effect) -> None:
        self.effects.append(effect)

    def shake(self, start: int, duration: int = 260, strength: float = 6) -> None:
        self.shakes.append((start, duration, strength))

    def burst(self, now: int, pos: World, color: Color, count: int = 18, speed: float = 3.0, life: int = 650,
              size: float = 3.0, gravity: float = 0.05, shape: str = "glow", up: float = 0.0, spread: float = 1.0) -> None:
        """Вспышка частиц из точки во все стороны, в том числе вглубь и к зрителю (up: подъём)."""
        rng, particles = self.rng, []
        for _ in range(count):
            a = rng.uniform(0, math.tau)
            v = speed * rng.uniform(0.35, 1.0)
            start = (pos[0] + rng.uniform(-6, 6) * spread, pos[1] + rng.uniform(-6, 6) * spread, pos[2] + rng.uniform(-4, 4) * spread)
            vel = (math.cos(a) * v, rng.uniform(-0.7, 0.7) * v + up, math.sin(a) * v * 0.7)
            particles.append(Particle(start, vel, now, int(life * rng.uniform(0.6, 1.0)), color,
                                      size * rng.uniform(0.7, 1.3), gravity, shape))
        self.add(Burst(now, life, pos, particles))

    def rise(self, now: int, base: World, radius: float, height: float, color: Color, count: int = 14,
             shape: str = "glow", speed: float = 1.2, life: int = 900, size: float = 3.0) -> None:
        """Частицы, поднимающиеся вокруг юнита (лечение, бафф, яд): цилиндр радиуса radius."""
        rng, particles = self.rng, []
        for _ in range(count):
            a, r = rng.uniform(0, math.tau), radius * math.sqrt(rng.uniform(0, 1))
            start = (base[0] + math.cos(a) * r, rng.uniform(0, height * 0.5), base[2] + math.sin(a) * r)
            vel = (rng.uniform(-0.3, 0.3), speed * rng.uniform(0.5, 1.2), 0.0)
            particles.append(Particle(start, vel, now + rng.randint(0, 200), int(life * rng.uniform(0.6, 1)), color,
                                      size * rng.uniform(0.7, 1.3), 0.0, shape))
        self.add(Burst(now, life + 200, base, particles))

    def parts(self, now: int) -> list[Part]:
        self.effects = [e for e in self.effects if now <= e.start + e.duration]
        result: list[Part] = []
        for effect in self.effects:
            result.extend(effect.parts(now))
        return result

    def screen_offset(self, now: int) -> tuple[float, float]:
        """Дрожь поля в логических пикселях."""
        dx = dy = 0.0
        for start, duration, strength in self.shakes:
            if start <= now <= start + duration:
                k = strength * (1 - (now - start) / duration)
                dx += self.rng.uniform(-k, k)
                dy += self.rng.uniform(-k, k) * 0.6
        self.shakes = [s for s in self.shakes if now <= s[0] + s[1]]
        return dx, dy

    def hit_reaction(self, uid: int, now: int) -> tuple[float, float]:
        """(сдвиг по x в единицах мира, яркость белой вспышки 0..1) юнита, по которому только что попали."""
        hit = self.hits.get(uid)
        if hit is None or not 0 <= now - hit <= HIT_MS:
            return 0.0, 0.0
        t = (now - hit) / HIT_MS
        return math.sin(t * 40) * 7 * (1 - t), (1 - t) ** 2
