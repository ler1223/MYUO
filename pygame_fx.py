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
                glow_at(screen, cam, self.point(max(0.0, t - i * 0.035)), self.color, 6 + 14 * (1 - i / 8), 0.35)
            glow_at(screen, cam, head, self.color, 26, 1.0)
            glow_at(screen, cam, head, (255, 255, 230), 10, 1.0)


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
