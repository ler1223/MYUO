"""Визуальные эффекты боя: частицы со свечением, снаряды, разрезы, молнии, лучи, волны, текст.

Эффекты живут в логических координатах поля (1000x620) и рисуются через камеру
(Camera): она переводит точку поля в пиксели окна с учётом размера окна и зума.
Поэтому при любом разрешении и увеличении эффекты рисуются чётко, а не растягиваются.

Эффект живёт с момента start (мс) в течение duration и рисует себя по доле прошедшего
времени. Свечение рисуется сложением цветов (BLEND_RGB_ADD). О бое модуль ничего не знает.
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

Color = tuple[int, int, int]
Point = tuple[float, float]

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


@dataclass(frozen=True)
class Camera:
    """Логические координаты поля -> пиксели окна.

    scale: пикселей окна на логический пиксель (размер окна x зум);
    origin: логическая точка, которая видна в левом верхнем углу области поля;
    offset: где в окне начинается область поля; clip: область поля в окне.
    """

    scale: float = 1.0
    origin: Point = (0.0, 0.0)
    offset: Point = (0.0, 0.0)
    clip: Optional[pygame.Rect] = None

    def p(self, x: float, y: float) -> tuple[int, int]:
        return (round(self.offset[0] + (x - self.origin[0]) * self.scale),
                round(self.offset[1] + (y - self.origin[1]) * self.scale))

    def s(self, value: float) -> float:
        return value * self.scale


IDENTITY = Camera()


@lru_cache(maxsize=None)
def fx_font(size: int, numbers: bool = False) -> pygame.font.Font:
    """Шрифт эффектов нужного размера в пикселях окна (числа крупным жирным шрифтом)."""
    size = max(8, size)
    return pygame.font.Font(None, size) if numbers else pygame.font.SysFont(FONT_NAMES, size, bold=True)


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
    """Свечение в пикселях окна (pos и radius уже переведены камерой)."""
    if strength <= 0.02 or radius < 2:
        return
    tint = tuple(int(c * min(1.0, strength)) for c in color)
    sprite = glow_sprite(tint, int(radius))
    screen.blit(sprite, sprite.get_rect(center=(int(pos[0]), int(pos[1]))), special_flags=pygame.BLEND_RGB_ADD)


def glow_at(screen: pygame.Surface, cam: Camera, pos: Point, color: Color, radius: float, strength: float = 1.0) -> None:
    """Свечение в логической точке поля."""
    add_glow(screen, cam.p(*pos), color, cam.s(radius), strength)


def lerp(a: Point, b: Point, t: float) -> Point:
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def width(cam: Camera, value: float) -> int:
    return max(1, round(cam.s(value)))


@dataclass
class Effect:
    start: int
    duration: int

    def progress(self, now: int) -> Optional[float]:
        """Доля прошедшего времени 0..1; None, если эффект ещё не начался или уже кончился."""
        if now < self.start or now > self.start + self.duration:
            return None
        return (now - self.start) / max(1, self.duration)

    def draw(self, screen: pygame.Surface, now: int, cam: Camera) -> None: ...


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: int
    born: int
    color: Color
    size: float
    gravity: float = 0.0
    shape: str = "glow"       # glow | spark | flake | star | bubble | shard


@dataclass
class Projectile(Effect):
    """Снаряд от source к target: стрела, огненный шар, осколки льда, тёмная сфера."""

    source: Point = (0, 0)
    target: Point = (0, 0)
    kind: str = "orb"         # orb | arrow | shards
    color: Color = (255, 255, 255)
    arc: float = 0.0          # высота дуги (стрелы летят навесом)
    size: float = 1.0         # размер сферы

    def point(self, t: float) -> Point:
        x, y = lerp(self.source, self.target, t)
        return x, y - math.sin(t * math.pi) * self.arc

    def draw(self, screen: pygame.Surface, now: int, cam: Camera) -> None:
        t = self.progress(now)
        if t is None:
            return
        t = ease_out(t) if self.kind == "orb" else t
        head = self.point(t)
        if self.kind == "arrow":
            tail = self.point(max(0.0, t - 0.08))
            pygame.draw.line(screen, (90, 70, 50), cam.p(*tail), cam.p(*head), width(cam, 3))
            pygame.draw.line(screen, (230, 230, 230), cam.p(*lerp(tail, head, 0.7)), cam.p(*head), width(cam, 3))
            glow_at(screen, cam, head, self.color, 10, 0.7)
            for i in range(1, 6):          # светящийся след
                glow_at(screen, cam, self.point(max(0.0, t - i * 0.03)), self.color, 7 - i, 0.5)
        elif self.kind == "shards":
            for i, offset in enumerate((-10, 0, 10)):
                x, y = self.point(max(0.0, t - i * 0.05))
                pts = [(x + 9, y + offset), (x - 3, y + offset - 4), (x - 7, y + offset), (x - 3, y + offset + 4)]
                pygame.draw.polygon(screen, (220, 240, 255), [cam.p(*pt) for pt in pts])
                glow_at(screen, cam, (x, y + offset), self.color, 12, 0.8)
        else:
            for i in range(8, 0, -1):          # хвост из гаснущих свечений
                glow_at(screen, cam, self.point(max(0.0, t - i * 0.035)), self.color,
                        (6 + 14 * (1 - i / 8)) * self.size, 0.35)
            glow_at(screen, cam, head, self.color, 26 * self.size, 1.0)
            glow_at(screen, cam, head, (255, 255, 230), 10 * self.size, 1.0)


@dataclass
class Slash(Effect):
    """Дуга разреза поперёк цели."""

    center: Point = (0, 0)
    color: Color = (235, 235, 245)
    radius: float = 46
    facing: int = 1           # 1: удар слева направо, -1: справа налево

    def draw(self, screen: pygame.Surface, now: int, cam: Camera) -> None:
        t = self.progress(now)
        if t is None:
            return
        sweep = ease_out(min(1.0, t * 1.6))
        fade = 1 - max(0.0, (t - 0.45) / 0.55)
        cx, cy = self.center
        start, end = -2.3, -2.3 + 2.6 * sweep
        steps = 18
        for i in range(steps):
            a = start + (end - start) * i / steps
            thickness = 1 + 7 * math.sin(math.pi * i / steps)
            x = cx + self.facing * math.cos(a) * self.radius
            y = cy + math.sin(a) * self.radius * 0.8 + self.radius * 0.35
            glow_at(screen, cam, (x, y), self.color, 6 + thickness * 1.6, 0.9 * fade)
            if i % 2 == 0:
                pygame.draw.circle(screen, (255, 255, 255), cam.p(x, y), width(cam, thickness * 0.45 * fade))


@dataclass
class Thrust(Effect):
    """Прямой выпад сквозь цель (колющий удар, промах)."""

    center: Point = (0, 0)
    color: Color = (235, 235, 245)
    facing: int = 1

    def draw(self, screen: pygame.Surface, now: int, cam: Camera) -> None:
        t = self.progress(now)
        if t is None:
            return
        length = 90 * ease_out(min(1.0, t * 2))
        fade = 1 - t
        x0 = self.center[0] - self.facing * 50
        x1 = x0 + self.facing * length
        y = self.center[1]
        for i in range(12):
            glow_at(screen, cam, (x0 + (x1 - x0) * i / 11, y), self.color, 5 + i * 0.8, 0.8 * fade)
        pygame.draw.line(screen, (255, 255, 255), cam.p(x0, y), cam.p(x1, y), width(cam, 3 * fade))


@dataclass
class Ring(Effect):
    """Расходящаяся волна (удар, взрыв, вспышка пассивки)."""

    center: Point = (0, 0)
    color: Color = (255, 255, 255)
    radius_from: float = 10
    radius_to: float = 60
    thickness: int = 4
    squash: float = 0.6       # кольцо «лежит» на земле

    def draw(self, screen: pygame.Surface, now: int, cam: Camera) -> None:
        t = self.progress(now)
        if t is None:
            return
        r = cam.s(self.radius_from + (self.radius_to - self.radius_from) * ease_out(t))
        rect = pygame.Rect(0, 0, int(r * 2), int(r * 2 * self.squash))
        rect.center = cam.p(*self.center)
        fade = 1 - t
        pad = 8
        layer = pygame.Surface(rect.inflate(pad, pad).size)
        inner = pygame.Rect(pad // 2, pad // 2, rect.width, rect.height)
        pygame.draw.ellipse(layer, tuple(int(c * fade) for c in self.color), inner, width(cam, self.thickness * fade + 1))
        screen.blit(layer, rect.inflate(pad, pad).topleft, special_flags=pygame.BLEND_RGB_ADD)


@dataclass
class Bolt(Effect):
    """Молния: ломаная от source к target, мерцает."""

    source: Point = (0, 0)
    target: Point = (0, 0)
    color: Color = (200, 200, 255)
    seed: int = 0

    def draw(self, screen: pygame.Surface, now: int, cam: Camera) -> None:
        t = self.progress(now)
        if t is None:
            return
        rng = random.Random(self.seed + (now - self.start) // 40)   # новая форма каждые 40 мс
        points = [self.source]
        for i in range(1, 9):
            x, y = lerp(self.source, self.target, i / 9)
            points.append((x + rng.uniform(-14, 14), y + rng.uniform(-6, 6)))
        points.append(self.target)
        fade = 1 - t
        for point in points:
            glow_at(screen, cam, point, self.color, 14, 0.6 * fade)
        pygame.draw.lines(screen, (240, 240, 255), False, [cam.p(*pt) for pt in points], width(cam, 4 * fade))


@dataclass
class Beam(Effect):
    """Столб света с неба на цель."""

    center: Point = (0, 0)
    color: Color = (255, 225, 120)
    thickness: int = 34

    def draw(self, screen: pygame.Surface, now: int, cam: Camera) -> None:
        t = self.progress(now)
        if t is None:
            return
        strength = math.sin(t * math.pi)
        x, bottom = cam.p(*self.center)
        top = cam.clip.top if cam.clip else 0
        w = max(2, int(cam.s(self.thickness) * (0.6 + 0.4 * strength)))
        height = max(1, bottom - top)
        layer = pygame.Surface((w, height))
        for i in range(w):
            k = (1 - abs(i - w / 2) / (w / 2)) ** 2 * strength
            pygame.draw.line(layer, tuple(int(c * k) for c in self.color), (i, 0), (i, height))
        screen.blit(layer, (int(x - w / 2), top), special_flags=pygame.BLEND_RGB_ADD)
        add_glow(screen, (x, bottom), self.color, cam.s(40), strength)


@dataclass
class FloatText(Effect):
    """Всплывающий текст: число урона, MISS, CRIT!, название навыка или пассивки."""

    pos: Point = (0, 0)
    text: str = ""
    color: Color = (255, 255, 255)
    size: int = 16            # высота шрифта в логических пикселях
    rise: float = 34
    pop: bool = True          # короткое «вздутие» в начале
    numbers: bool = False     # крупный цифровой шрифт

    def draw(self, screen: pygame.Surface, now: int, cam: Camera) -> None:
        t = self.progress(now)
        if t is None:
            return
        scale = 1 + 0.6 * max(0.0, 1 - t * 6) if self.pop else 1
        font = fx_font(round(cam.s(self.size) * scale), self.numbers)
        img = font.render(self.text, True, self.color)
        outline = font.render(self.text, True, (15, 15, 20))
        alpha = int(255 * min(1.0, (1 - t) * 3))
        img.set_alpha(alpha)
        outline.set_alpha(alpha)
        rect = img.get_rect(center=cam.p(self.pos[0], self.pos[1] - self.rise * ease_out(t)))
        o = width(cam, 2)
        for dx, dy in ((-o, 0), (o, 0), (0, -o), (0, o)):
            screen.blit(outline, rect.move(dx, dy))
        screen.blit(img, rect)


@dataclass
class Flash(Effect):
    """Вспышка всего поля (крит, молния)."""

    color: Color = (255, 255, 255)
    strength: float = 0.5

    def draw(self, screen: pygame.Surface, now: int, cam: Camera) -> None:
        t = self.progress(now)
        if t is None:
            return
        k = self.strength * (1 - t) ** 2
        screen.fill(tuple(int(c * k) for c in self.color), cam.clip, special_flags=pygame.BLEND_RGB_ADD)


@dataclass
class RuneCircle(Effect):
    """Магический круг на земле: два кольца с насечками, медленно вращается, вспыхивает и гаснет."""

    center: Point = (0, 0)
    color: Color = (255, 140, 60)
    radius: float = 40
    squash: float = 0.35

    def draw(self, screen: pygame.Surface, now: int, cam: Camera) -> None:
        t = self.progress(now)
        if t is None:
            return
        strength = min(1.0, t / 0.2) * min(1.0, (1 - t) / 0.3)
        r = cam.s(self.radius) * (0.7 + 0.3 * ease_out(min(1.0, t / 0.3)))
        pad = 12
        layer = pygame.Surface((int(r * 2) + pad * 2, int(r * 2 * self.squash) + pad * 2))
        cx, cy = layer.get_width() / 2, layer.get_height() / 2
        color = tuple(int(c * strength) for c in self.color)
        line = max(1, round(cam.s(2)))
        for k in (1.0, 0.78):
            rect = pygame.Rect(0, 0, int(r * 2 * k), int(r * 2 * k * self.squash))
            rect.center = (int(cx), int(cy))
            pygame.draw.ellipse(layer, color, rect, line)
        spin = (now - self.start) / 900
        for i in range(12):                      # насечки рун между кольцами
            a = spin + i * math.tau / 12
            x0, y0 = cx + math.cos(a) * r * 0.8, cy + math.sin(a) * r * 0.8 * self.squash
            x1, y1 = cx + math.cos(a + 0.12) * r * 0.97, cy + math.sin(a + 0.12) * r * 0.97 * self.squash
            pygame.draw.line(layer, color, (x0, y0), (x1, y1), line)
        for i in range(3):                       # треугольник внутри
            a, b = spin * -1.5 + i * math.tau / 3, spin * -1.5 + (i + 1) * math.tau / 3
            pygame.draw.line(layer, color, (cx + math.cos(a) * r * 0.76, cy + math.sin(a) * r * 0.76 * self.squash),
                             (cx + math.cos(b) * r * 0.76, cy + math.sin(b) * r * 0.76 * self.squash), line)
        x, y = cam.p(*self.center)
        screen.blit(layer, (int(x - cx), int(y - cy)), special_flags=pygame.BLEND_RGB_ADD)
        add_glow(screen, (x, y), self.color, r * 0.9, 0.35 * strength)


@dataclass
class Pillar(Effect):
    """Столб пламени (или света), вырастающий из земли и опадающий."""

    base: Point = (0, 0)
    color: Color = (255, 120, 30)
    height: float = 110
    thickness: float = 26
    seed: int = 0

    def draw(self, screen: pygame.Surface, now: int, cam: Camera) -> None:
        t = self.progress(now)
        if t is None:
            return
        grow = ease_out(min(1.0, t / 0.3)) * min(1.0, (1 - t) / 0.35)
        rng = random.Random(self.seed + (now - self.start) // 50)
        h = cam.s(self.height) * grow * rng.uniform(0.9, 1.05)
        w = max(2, int(cam.s(self.thickness) * (0.6 + 0.4 * grow)))
        if h < 2:
            return
        x, bottom = cam.p(*self.base)
        layer = pygame.transform.smoothscale(pillar_texture(self.color), (w, int(h)))
        screen.blit(layer, (int(x - w / 2), int(bottom - h)), special_flags=pygame.BLEND_RGB_ADD)
        add_glow(screen, (x, bottom), self.color, w * 1.6, grow)


@lru_cache(maxsize=64)
def pillar_texture(color: Color) -> pygame.Surface:
    """Текстура столба 32x128: ярче в середине и у земли, к верху тоньше и темнее."""
    w, h = 32, 128
    surface = pygame.Surface((w, h))
    for j in range(h):
        up = 1 - j / h                            # 0 у верха, 1 у земли
        for i in range(w):
            across = max(0.0, 1 - abs(i - w / 2) / (w / 2 * (0.4 + 0.6 * up))) ** 1.5
            k = across * up ** 0.7
            surface.set_at((i, j), (min(255, int(color[0] * k + 120 * k * up)), min(255, int(color[1] * k + 40 * k * up)),
                                    int(color[2] * k)))
    return surface


@dataclass
class ArrowRain(Effect):
    """Дождь стрел на область: стрелы падают сверху наискосок в случайные точки вокруг center."""

    center: Point = (0, 0)
    color: Color = (255, 240, 200)
    count: int = 12
    spread: float = 50
    facing: int = 1
    seed: int = 0

    def draw(self, screen: pygame.Surface, now: int, cam: Camera) -> None:
        t = self.progress(now)
        if t is None:
            return
        rng = random.Random(self.seed)
        for _ in range(self.count):
            delay = rng.uniform(0, 0.55)
            land = (self.center[0] + rng.uniform(-self.spread, self.spread), self.center[1] + rng.uniform(-12, 12))
            k = (t - delay) / 0.4
            if not 0 <= k <= 1:
                continue
            start = (land[0] - 70 * self.facing, land[1] - 200)
            head = lerp(start, land, k)
            tail = lerp(start, land, max(0.0, k - 0.18))
            pygame.draw.line(screen, (90, 70, 50), cam.p(*tail), cam.p(*head), width(cam, 2))
            pygame.draw.line(screen, (235, 235, 235), cam.p(*lerp(tail, head, 0.75)), cam.p(*head), width(cam, 2))
            glow_at(screen, cam, head, self.color, 6, 0.5)


@dataclass
class Glint(Effect):
    """Блик-звёздочка: прицеливание, готовность, наконечник стрелы."""

    pos: Point = (0, 0)
    color: Color = (255, 250, 220)
    size: float = 22

    def draw(self, screen: pygame.Surface, now: int, cam: Camera) -> None:
        t = self.progress(now)
        if t is None:
            return
        k = math.sin(t * math.pi)
        x, y = cam.p(*self.pos)
        r = cam.s(self.size) * k
        line = max(1, round(cam.s(2) * k))
        pygame.draw.line(screen, (255, 255, 255), (x - r, y), (x + r, y), line)
        pygame.draw.line(screen, (255, 255, 255), (x, y - r * 0.7), (x, y + r * 0.7), line)
        add_glow(screen, (x, y), self.color, r * 0.9, k)


@dataclass
class Dome(Effect):
    """Полупрозрачный купол щита перед защитником."""

    center: Point = (0, 0)
    color: Color = (110, 170, 255)
    radius: float = 50

    def draw(self, screen: pygame.Surface, now: int, cam: Camera) -> None:
        t = self.progress(now)
        if t is None:
            return
        k = min(1.0, t / 0.15) * min(1.0, (1 - t) / 0.4)
        r = cam.s(self.radius) * (0.8 + 0.2 * ease_out(min(1.0, t / 0.2)))
        layer = pygame.Surface((int(r * 2) + 4, int(r * 2) + 4))
        c = (layer.get_width() // 2, layer.get_height() // 2)
        for i in range(6):                        # к краю купол ярче
            rr = r * (1 - i * 0.12)
            pygame.draw.circle(layer, tuple(int(v * k * (0.5 - i * 0.07)) for v in self.color), c, int(rr),
                               max(1, round(cam.s(3))))
        x, y = cam.p(*self.center)
        screen.blit(layer, (int(x - c[0]), int(y - c[1])), special_flags=pygame.BLEND_RGB_ADD)


@dataclass
class FxSystem:
    """Все активные эффекты, частицы и «реакции» карт (тряска, вспышка, выпад)."""

    effects: list[Effect] = field(default_factory=list)
    particles: list[Particle] = field(default_factory=list)
    shakes: list[tuple[int, int, float]] = field(default_factory=list)   # (начало, длительность, сила) экрана
    card_hits: dict[int, int] = field(default_factory=dict)              # uid -> когда по карте попали
    card_lunges: dict[int, tuple[int, Point]] = field(default_factory=dict)  # uid -> (когда, куда)
    rng: random.Random = field(default_factory=lambda: random.Random(7))
    last_draw: int = 0

    def clear(self) -> None:
        self.effects.clear()
        self.particles.clear()
        self.shakes.clear()
        self.card_hits.clear()
        self.card_lunges.clear()

    def add(self, effect: Effect) -> None:
        self.effects.append(effect)

    def shake(self, start: int, duration: int = 260, strength: float = 6) -> None:
        self.shakes.append((start, duration, strength))

    def burst(self, now: int, pos: Point, color: Color, count: int = 18, speed: float = 3.0, life: int = 650,
              size: float = 3.0, gravity: float = 0.05, shape: str = "glow", up: float = 0.0, spread: float = 1.0) -> None:
        """Вспышка частиц из точки во все стороны (up: дополнительный подъём вверх)."""
        for _ in range(count):
            a = self.rng.uniform(0, math.tau)
            v = speed * self.rng.uniform(0.35, 1.0)
            self.particles.append(Particle(
                pos[0] + self.rng.uniform(-6, 6) * spread, pos[1] + self.rng.uniform(-6, 6) * spread,
                math.cos(a) * v, math.sin(a) * v * 0.7 - up, int(life * self.rng.uniform(0.6, 1.0)), now,
                color, size * self.rng.uniform(0.7, 1.3), gravity, shape))

    def rise(self, now: int, rect: pygame.Rect, color: Color, count: int = 14, shape: str = "glow",
             speed: float = 1.2, life: int = 900, size: float = 3.0) -> None:
        """Частицы, поднимающиеся из области (лечение, бафф, яд)."""
        for _ in range(count):
            self.particles.append(Particle(
                self.rng.uniform(rect.left, rect.right), self.rng.uniform(rect.centery, rect.bottom),
                self.rng.uniform(-0.3, 0.3), -speed * self.rng.uniform(0.5, 1.2), int(life * self.rng.uniform(0.6, 1)),
                now + self.rng.randint(0, 200), color, size * self.rng.uniform(0.7, 1.3), 0.0, shape))

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

    def card_offset(self, uid: int, now: int, home: Point) -> tuple[float, float, float]:
        """(dx, dy, яркость вспышки 0..1) для карты: выпад к цели и дрожь от удара."""
        dx = dy = 0.0
        lunge = self.card_lunges.get(uid)
        if lunge is not None:
            start, target = lunge
            t = (now - start) / 380
            if 0 <= t <= 1:
                k = math.sin(t * math.pi) * 0.28           # туда и обратно
                dx, dy = (target[0] - home[0]) * k, (target[1] - home[1]) * k
        flash = 0.0
        hit = self.card_hits.get(uid)
        if hit is not None and 0 <= now - hit <= 260:
            t = (now - hit) / 260
            dx += math.sin(t * 40) * 7 * (1 - t)
            flash = (1 - t) ** 2
        return dx, dy, flash

    def draw(self, screen: pygame.Surface, now: int, cam: Camera = IDENTITY) -> None:
        dt = max(1, min(50, now - self.last_draw)) if self.last_draw else 16
        self.last_draw = now
        self.effects = [e for e in self.effects if now <= e.start + e.duration]
        for effect in self.effects:
            effect.draw(screen, now, cam)
        alive = []
        step = dt / 16
        for p in self.particles:
            age = now - p.born
            if age < 0:
                alive.append(p)
                continue
            if age > p.life:
                continue
            alive.append(p)
            p.vy += p.gravity * step
            p.x += p.vx * step
            p.y += p.vy * step
            self._draw_particle(screen, cam, p, 1 - age / p.life)
        self.particles = alive

    @staticmethod
    def _draw_particle(screen: pygame.Surface, cam: Camera, p: Particle, k: float) -> None:
        x, y = cam.p(p.x, p.y)
        size = cam.s(p.size)
        if p.shape == "spark":
            tail = cam.p(p.x - p.vx * 3, p.y - p.vy * 3)
            pygame.draw.line(screen, p.color, (x, y), tail, max(1, int(size * k)))
            add_glow(screen, (x, y), p.color, size * 3, k * 0.6)
        elif p.shape == "flake":
            r = max(1, int(size * 1.6 * k))
            for a in (0, math.pi / 3, 2 * math.pi / 3):
                ox, oy = math.cos(a) * r, math.sin(a) * r
                pygame.draw.line(screen, (230, 245, 255), (x - ox, y - oy), (x + ox, y + oy), max(1, int(cam.scale)))
            add_glow(screen, (x, y), p.color, size * 3, k * 0.5)
        elif p.shape == "star":
            r = size * 2 * k + cam.s(2)
            pts = [(x + math.cos(a) * (r if i % 2 == 0 else r * 0.45), y + math.sin(a) * (r if i % 2 == 0 else r * 0.45))
                   for i, a in enumerate(i * math.pi / 5 - math.pi / 2 for i in range(10))]
            pygame.draw.polygon(screen, (255, 240, 140), pts)
            add_glow(screen, (x, y), p.color, r * 2.5, k * 0.6)
        elif p.shape == "bubble":
            pygame.draw.circle(screen, p.color, (x, y), max(1, int(size * (1.4 - k * 0.4))), max(1, int(cam.scale)))
        elif p.shape == "shard":
            r = size * 2
            pygame.draw.polygon(screen, (220, 240, 255), [(x, y - r), (x + r * 0.5, y), (x, y + r), (x - r * 0.5, y)])
            add_glow(screen, (x, y), p.color, r * 2, k * 0.7)
        else:
            add_glow(screen, (x, y), p.color, size * 3 * (0.5 + k), k)


# --- оружие ---------------------------------------------------------------

WEAPON_DIR = Path(__file__).resolve().parent / "assets" / "weapons"
WEAPON_KINDS = ("sword", "axe", "spear", "dagger", "bow", "staff", "shield", "fist")
WEAPON_LENGTH = {"sword": 70, "axe": 64, "spear": 96, "dagger": 40, "bow": 70, "staff": 84, "shield": 54, "fist": 30}

_weapon_cache: dict[tuple[str, int], pygame.Surface] = {}


def _draw_weapon(kind: str, length: int) -> pygame.Surface:
    """Оружие кодом, остриём вверх, в поверхности length x length."""
    s = pygame.Surface((length, length), pygame.SRCALPHA)
    c = length / 2
    u = length / 100                                  # единица длины
    wood, steel, edge, gold = (120, 80, 45), (196, 202, 214), (245, 248, 255), (222, 182, 82)
    w = lambda v: max(1, round(v * u))
    if kind in ("sword", "dagger"):
        blade = 0.62 if kind == "sword" else 0.45
        top, guard = length * 0.04, length * (0.04 + blade)
        pygame.draw.polygon(s, steel, [(c, top), (c + w(6), top + w(10)), (c + w(5), guard), (c - w(5), guard), (c - w(6), top + w(10))])
        pygame.draw.line(s, edge, (c, top + w(4)), (c, guard - w(2)), w(2))
        pygame.draw.rect(s, gold, pygame.Rect(c - w(16), guard, w(32), w(5)), border_radius=w(2))
        pygame.draw.rect(s, wood, pygame.Rect(c - w(3), guard + w(5), w(6), w(16)))
        pygame.draw.circle(s, gold, (c, guard + w(24)), w(5))
    elif kind == "axe":
        pygame.draw.line(s, wood, (c, length * 0.12), (c, length * 0.98), w(6))
        pygame.draw.polygon(s, steel, [(c + w(2), length * 0.12), (c + w(30), length * 0.04), (c + w(36), length * 0.24),
                                       (c + w(30), length * 0.44), (c + w(2), length * 0.36)])
        pygame.draw.line(s, edge, (c + w(31), length * 0.06), (c + w(33), length * 0.42), w(3))
    elif kind == "spear":
        pygame.draw.line(s, wood, (c, length * 0.16), (c, length * 0.99), w(4))
        pygame.draw.polygon(s, steel, [(c, length * 0.01), (c + w(7), length * 0.1), (c, length * 0.2), (c - w(7), length * 0.1)])
        pygame.draw.line(s, gold, (c - w(6), length * 0.21), (c + w(6), length * 0.21), w(3))
    elif kind == "bow":
        box = pygame.Rect(c - w(30), length * 0.04, w(44), length * 0.92)
        pygame.draw.arc(s, wood, box, -math.pi / 2, math.pi / 2, w(6))
        pygame.draw.line(s, (230, 230, 220), (box.centerx, box.top + w(3)), (box.centerx, box.bottom - w(3)), w(1))
    elif kind == "staff":
        pygame.draw.line(s, wood, (c, length * 0.14), (c, length * 0.99), w(5))
        pygame.draw.circle(s, (150, 210, 255), (c, length * 0.1), w(9))
        pygame.draw.circle(s, (240, 250, 255), (c - w(2), length * 0.08), w(4))
    elif kind == "shield":
        pts = [(c - w(40), length * 0.08), (c + w(40), length * 0.08), (c + w(36), length * 0.5), (c, length * 0.96),
               (c - w(36), length * 0.5)]
        pygame.draw.polygon(s, (60, 90, 160), pts)
        pygame.draw.polygon(s, steel, pts, w(6))
        pygame.draw.line(s, gold, (c, length * 0.16), (c, length * 0.8), w(6))
        pygame.draw.line(s, gold, (c - w(24), length * 0.36), (c + w(24), length * 0.36), w(6))
    else:   # fist
        pygame.draw.circle(s, (230, 190, 150), (c, c), w(30))
        pygame.draw.circle(s, (150, 110, 80), (c, c), w(30), w(4))
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
            image = pygame.image.load(str(path)).convert_alpha()
            k = length / max(image.get_size())
            _weapon_cache[key] = pygame.transform.smoothscale(image, (max(1, round(image.get_width() * k)),
                                                                      max(1, round(image.get_height() * k))))
        else:
            _weapon_cache[key] = _draw_weapon(kind, length)
    return _weapon_cache[key]


@dataclass
class WeaponStrike(Effect):
    """Оружие атакующего: появляется у него, летит к цели и бьёт.

    Меч, топор, кинжал и кулак — замах и удар дугой; копьё — выпад; лук — натягивается
    у стрелка; посох — поднимается над заклинателем; щит — встаёт перед целью (прикрытие).
    """

    kind: str = "sword"
    source: Point = (0, 0)
    target: Point = (0, 0)
    facing: int = 1           # 1: атакующий слева, бьёт вправо

    def draw(self, screen: pygame.Surface, now: int, cam: Camera) -> None:
        t = self.progress(now)
        if t is None:
            return
        appear = min(1.0, t / 0.15)
        fade = 1 - max(0.0, (t - 0.8) / 0.2)
        alpha = int(255 * min(appear, fade))
        length = cam.s(WEAPON_LENGTH.get(self.kind, 60))
        if self.kind == "bow":
            pos = (self.source[0] + 34 * self.facing, self.source[1] - 6)
            angle = -12 * self.facing
            stretch = 1 - 0.2 * math.sin(min(1.0, t / 0.6) * math.pi)
        elif self.kind == "staff":
            pos = (self.source[0] + 18 * self.facing, self.source[1] - 30 - 20 * ease_out(min(1.0, t / 0.5)))
            angle, stretch = -10 * self.facing, 1.0
            glow_at(screen, cam, (pos[0], pos[1] - WEAPON_LENGTH["staff"] * 0.4), (150, 210, 255), 22, 0.8 * fade)
        elif self.kind == "shield":
            pos = lerp(self.source, self.target, 0.75)
            angle, stretch = 0, 1.0
        else:
            # Полёт к цели, затем удар: дуга (рубящее) или выпад (колющее).
            travel = ease_out(min(1.0, t / 0.6))
            near = (self.target[0] - 40 * self.facing, self.target[1] - 20)
            pos = lerp((self.source[0] + 20 * self.facing, self.source[1] - 30), near, travel)
            pos = (pos[0], pos[1] - math.sin(travel * math.pi) * 30)
            strike = max(0.0, (t - 0.55) / 0.3)
            if self.kind == "spear":
                angle = -90 * self.facing
                pos = (pos[0] + 40 * self.facing * ease_out(min(1.0, strike)), pos[1] + 20)
            else:
                angle = (40 - 160 * ease_out(min(1.0, strike))) * -self.facing   # замах за голову и удар вниз
            stretch = 1.0
        image = weapon_sprite(self.kind, length)
        if self.facing < 0 and self.kind in ("bow",):
            image = pygame.transform.flip(image, True, False)
        if stretch != 1.0:
            image = pygame.transform.smoothscale(image, (max(1, int(image.get_width() * stretch)), image.get_height()))
        rotated = pygame.transform.rotate(image, angle)
        rotated.set_alpha(alpha)
        screen.blit(rotated, rotated.get_rect(center=cam.p(*pos)))
