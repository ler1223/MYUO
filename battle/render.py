"""Кадр показа боя на видеокарте: фон, бойцы, эффекты, интерфейс UO — в один буфер.

Куклы (персонажи, эффекты, фоны, элементы интерфейса) рисуются сетками engine.uo.gl прямо в буфер
кадра; через рабочий буфер — только то, что накладывается с прозрачностью или вспышкой.
Картинки pygame (надписи) — текстурами. Готовый кадр — в окно OpenGL (present) или одним
чтением в картинку pygame (read_into).

Координаты: Camera переводит единицы сцены в пиксели кадра (y вниз). Строка y буфера —
строка y картинки (как в engine.uo.gl), в окно кадр выводится перевёрнутым.

ScreenOverlay — интерфейс (холст pygame) поверх окна OpenGL (pygame_ui.Window с gl=True).
"""
from __future__ import annotations

import math
from collections import OrderedDict
from typing import Optional

import pygame

from engine.uo.gl import GLRenderer, Mesh, moderngl

Point = tuple[float, float]


def corners(x: float, y: float, w: float, h: float, pivot: Optional[Point] = None, angle: float = 0.0):
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    if not angle:
        return pts
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    px, py = pivot or (x + w / 2, y + h / 2)
    return [(px + (qx - px) * ca + (qy - py) * sa, py - (qx - px) * sa + (qy - py) * ca) for qx, qy in pts]


class Camera:
    """Видимая часть сцены box (x0, y0, x1, y1) в прямоугольнике clip кадра."""

    def __init__(self, box: tuple[float, float, float, float], clip: pygame.Rect):
        self.box = box
        self.clip = pygame.Rect(clip)
        self.k = self.clip.height / max(1.0, box[3] - box[1])

    def p(self, x: float, y: float) -> Point:
        return self.clip.x + (x - self.box[0]) * self.k, self.clip.y + (y - self.box[1]) * self.k


class Canvas:
    def __init__(self, gl: GLRenderer):
        self.gl = gl
        self.ctx = gl.ctx
        self.size = (0, 0)
        self.color = self.fbo = None
        self.clip = pygame.Rect(0, 0, 0, 0)
        self._textures: OrderedDict = OrderedDict()

    def begin(self, size: tuple[int, int], clip: Optional[pygame.Rect] = None) -> None:
        w, h = max(1, size[0]), max(1, size[1])
        if (w, h) != self.size:
            for obj in (self.fbo, self.color):
                if obj is not None:
                    obj.release()
            self.color = self.ctx.texture((w, h), 4)
            self.color.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self.fbo = self.ctx.framebuffer(color_attachments=[self.color])
            self.size = (w, h)
        self.clip = pygame.Rect(clip or (0, 0, w, h)).clip(pygame.Rect(0, 0, w, h))
        self.fbo.scissor = None
        self.fbo.use()
        self.ctx.viewport = (0, 0, w, h)
        self.fbo.clear(0, 0, 0, 1)
        self.fbo.scissor = tuple(self.clip)

    def _target(self) -> None:
        self.fbo.use()
        self.ctx.viewport = (0, 0, *self.size)

    # --- куклы ---

    def puppet(self, mesh: Optional[Mesh], pages: list, scale: float, flip: bool, point: Point,
               alpha: float = 1.0, flash: float = 0.0, mul=(1.0, 1.0, 1.0), additive: bool = False,
               angle: float = 0.0) -> None:
        """Сетка куклы: её точка 0,0 — в point (пиксели кадра); angle — поворот вокруг неё (градусы)."""
        if mesh is None or alpha <= 0.004:
            return
        if alpha >= 0.996 and not flash and tuple(mul) == (1.0, 1.0, 1.0) and not additive and abs(angle) < 0.5:
            self.gl.draw_mesh(mesh, pages, self.fbo, self.size, scale, flip, point[0], point[1])
            return
        placed = self.gl.draw_to_temp(mesh, pages, scale, flip)
        if placed is None:
            return
        ox, oy, w, h = placed
        self._target()
        tw, th = self.gl.temp_size
        self.gl.quad(self.gl.temp, corners(point[0] - ox, point[1] - oy, w, h, point, angle), (0, 0, w / tw, h / th),
                     self.size, alpha=alpha, flash=flash, mul=mul, additive=additive)

    # --- картинки ---

    def texture(self, surface: pygame.Surface):
        key = id(surface)
        found = self._textures.get(key)
        if found is not None and found[0] is surface:
            self._textures.move_to_end(key)
            return found[1]
        tex = self.ctx.texture(surface.get_size(), 4, pygame.image.tobytes(surface, "RGBA"))
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self._textures[key] = (surface, tex)
        while len(self._textures) > 300:
            _, (_, old) = self._textures.popitem(last=False)
            old.release()
        return tex

    def image(self, surface: pygame.Surface, pos: Point, alpha: float = 1.0) -> None:
        if alpha <= 0.004:
            return
        tex = self.texture(surface)
        self._target()
        w, h = surface.get_size()
        self.gl.quad(tex, corners(pos[0], pos[1], w, h), (0, 0, 1, 1), self.size, kind=1, alpha=alpha)

    def rect(self, color, rect, alpha: float = 1.0) -> None:
        if not hasattr(self, "_white"):
            surface = pygame.Surface((4, 4), pygame.SRCALPHA)
            surface.fill((255, 255, 255, 255))
            self._white = surface
        tex = self.texture(self._white)
        self._target()
        x, y, w, h = rect
        self.gl.quad(tex, corners(x, y, w, h), (0, 0, 1, 1), self.size, kind=1, alpha=alpha,
                     mul=tuple(c / 255 for c in color[:3]))

    # --- вывод ---

    def read_into(self, target: pygame.Surface, area: Optional[pygame.Rect] = None) -> None:
        area = pygame.Rect(area or self.clip).clip(pygame.Rect(0, 0, *self.size))
        if area.width <= 0 or area.height <= 0:
            return
        data = self.fbo.read(viewport=tuple(area), components=3, alignment=1)
        target.blit(pygame.image.frombuffer(data, area.size, "RGB"), area.topleft)

    def present(self, window_size: tuple[int, int], area: Optional[pygame.Rect] = None) -> None:
        """В окно OpenGL на то же место (ctx.screen)."""
        area = pygame.Rect(area or self.clip)
        w, h = self.size
        self.ctx.screen.use()
        self.ctx.viewport = (0, 0, *window_size)
        self.ctx.disable(moderngl.BLEND)
        self.gl.quad(self.color, corners(area.x, area.y, area.width, area.height),
                     (area.x / w, area.y / h, area.right / w, area.bottom / h), window_size, screen=True)


class ScreenOverlay:
    """Интерфейс (холст pygame) поверх окна OpenGL: загружается текстурой каждый кадр."""

    def __init__(self, gl: GLRenderer):
        self.gl = gl
        self.tex = None

    def draw(self, canvas: pygame.Surface, window_size: tuple[int, int], rect, area: Optional[pygame.Rect] = None) -> None:
        """Холст (или его часть area) в прямоугольник rect окна (x, y, w, h в пикселях окна)."""
        ctx = self.gl.ctx
        size = canvas.get_size()
        if self.tex is None or self.tex.size != size:
            if self.tex is not None:
                self.tex.release()
            self.tex = ctx.texture(size, 4)
            self.tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
            if canvas.get_masks()[:3] == (0xFF0000, 0xFF00, 0xFF) and canvas.get_pitch() == size[0] * 4:
                self.tex.swizzle = "BGRA"            # байты картинки — B, G, R, A: пишутся без перекладки
        area = area or canvas.get_rect()
        if area.width <= 0 or area.height <= 0:
            return
        if self.tex.swizzle == "BGRA":
            self.tex.write(canvas.get_buffer())
        else:
            self.tex.write(pygame.image.tobytes(canvas, "RGBA"))
        self.tex.build_mipmaps()
        x, y, w, h = rect
        kx, ky = w / size[0], h / size[1]
        dst = (x + area.x * kx, y + area.y * ky, area.width * kx, area.height * ky)
        ctx.screen.use()
        ctx.viewport = (0, 0, *window_size)
        self.gl.quad(self.tex, corners(*dst),
                     (area.x / size[0], area.y / size[1], area.right / size[0], area.bottom / size[1]),
                     window_size, kind=1, screen=True)
