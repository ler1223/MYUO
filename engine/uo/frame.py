"""Кадр поля боя на видеокарте: всё поле собирается в одном буфере и выводится в окно без чтения
обратно (окно в режиме OPENGL) или читается один раз за кадр в картинку pygame (инструменты, тесты,
окна без OpenGL).

Что умеет кадр:
- puppet — кадр куклы (сетка engine.uo.gl.Mesh): рисуется в рабочий буфер и накладывается с
  прозрачностью, свечением цветом, вспышкой белым, поворотом вокруг ног, послеобразами;
- image — картинка pygame (задник, объекты сцены, спрайты без кукол, текст, заготовки теней);
- legacy — прозрачная картинка pygame размером с кадр для эффектов, нарисованных кодом
  (engine.fx): что на неё нарисовано, накладывается при следующем рисовании видеокартой (flush).
  Сложение цветом (BLEND_RGB_ADD) на прозрачном фоне тоже видно: яркость становится непрозрачностью.
Координаты — пиксели кадра (y вниз), как у камеры сцены.
"""
from __future__ import annotations

import math
from collections import OrderedDict
from typing import Any, Optional

import pygame

from .gl import GLRenderer, Mesh, moderngl

TEXTURES = 600                     # картинок pygame на видеокарте (самые давние выгружаются)
Point = tuple[float, float]


def _corners(x: float, y: float, w: float, h: float, pivot: Point, angle: float) -> list[Point]:
    """Углы прямоугольника (лв, пв, пн, лн), повёрнутого на angle градусов (против часовой, как
    pygame.transform.rotate) вокруг pivot."""
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    if not angle:
        return pts
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    px, py = pivot
    return [(px + (qx - px) * ca + (qy - py) * sa, py - (qx - px) * sa + (qy - py) * ca) for qx, qy in pts]


class GLFrame:
    """Буфер кадра поля и инструменты рисования в него."""

    def __init__(self, gl: GLRenderer):
        self.gl = gl
        self.ctx = gl.ctx
        self.size = (0, 0)
        self.color = self.fbo = None
        self.clip = pygame.Rect(0, 0, 0, 0)
        self._legacy: Optional[pygame.Surface] = None
        self._legacy_tex = None
        self._dirty = False
        self._textures: OrderedDict[int, tuple[pygame.Surface, Any]] = OrderedDict()
        self._keyed: OrderedDict[Any, Any] = OrderedDict()

    # --- кадр ---

    def begin(self, size: tuple[int, int], clip: Optional[pygame.Rect] = None) -> None:
        """Новый кадр размера size; рисуется только внутри clip (область поля)."""
        w, h = max(1, size[0]), max(1, size[1])
        if (w, h) != self.size:
            for obj in (self.fbo, self.color, self._legacy_tex):
                if obj is not None:
                    obj.release()
            self.color = self.ctx.texture((w, h), 4)
            self.color.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self.fbo = self.ctx.framebuffer(color_attachments=[self.color])
            self._legacy = pygame.Surface((w, h), pygame.SRCALPHA)
            self._legacy_tex = self.ctx.texture((w, h), 4)
            self.size = (w, h)
        self.clip = pygame.Rect(clip) if clip is not None else pygame.Rect(0, 0, w, h)
        self.clip = self.clip.clip(pygame.Rect(0, 0, w, h))
        self.fbo.scissor = None
        self.fbo.use()
        self.ctx.viewport = (0, 0, w, h)
        self.fbo.clear(0, 0, 0, 1)
        self.fbo.scissor = tuple(self.clip)       # рисуется только поле (у буфера moderngl — своё)
        self._dirty = False

    def _target(self) -> None:
        self.fbo.use()
        self.ctx.viewport = (0, 0, *self.size)

    def end(self) -> None:
        self.flush()

    # --- кукла ---

    def puppet(self, mesh: Optional[Mesh], pages: list, scale: float, flip: bool, point: Point,
               alpha: float = 1.0, add=(0.0, 0.0, 0.0), flash: float = 0.0, angle: float = 0.0,
               additive: bool = False, ghosts: tuple = (), box=None, mul=(1.0, 1.0, 1.0)) -> None:
        """Кадр куклы: её точка 0,0 (ноги) — в point. ghosts — послеобразы ((точка, прозрачность), ...)
        под ним; additive — эффект со сложением цвета."""
        if mesh is None or alpha <= 0.004:
            return
        placed = self.gl.draw_to_temp(mesh, pages, scale, flip, box=box)
        if placed is None:
            return
        ox, oy, w, h = placed
        self._target()
        tw, th = self.gl.temp_size
        uv = (0.0, 0.0, w / tw, h / th)
        for (gx, gy), ghost_alpha in ghosts:
            self.gl.quad(self.gl.temp, _corners(gx - ox, gy - oy, w, h, (gx, gy), 0), uv, self.size,
                         alpha=ghost_alpha, add=(70 / 255, 90 / 255, 140 / 255))
        x, y = point
        self.gl.quad(self.gl.temp, _corners(x - ox, y - oy, w, h, (x, y), angle), uv, self.size, alpha=alpha,
                     add=add, flash=flash, additive=additive, mul=mul)

    # --- картинки pygame ---

    def texture_of(self, surface: pygame.Surface, mipmaps: bool = False):
        """Текстура картинки (по самой картинке: та же картинка — та же текстура)."""
        key = id(surface)
        found = self._textures.get(key)
        if found is not None and found[0] is surface:
            self._textures.move_to_end(key)
            return found[1]
        tex = self._upload(surface, mipmaps)
        self._textures[key] = (surface, tex)
        while len(self._textures) > TEXTURES:
            _, (_, old) = self._textures.popitem(last=False)
            old.release()
        return tex

    def keyed_texture(self, key: Any, make, mipmaps: bool = False):
        """Текстура по своему ключу: make() даёт картинку, если её ещё нет."""
        if key in self._keyed:
            self._keyed.move_to_end(key)
            return self._keyed[key]
        surface = make()
        tex = self._upload(surface, mipmaps) if surface is not None else None
        self._keyed[key] = tex
        while len(self._keyed) > 64:
            _, old = self._keyed.popitem(last=False)
            if old is not None:
                old.release()
        return tex

    def _upload(self, surface: pygame.Surface, mipmaps: bool):
        data = pygame.image.tobytes(surface, "RGBA")
        tex = self.ctx.texture(surface.get_size(), 4, data)
        if mipmaps:
            tex.build_mipmaps()
            tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        else:
            tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        tex.repeat_x = tex.repeat_y = False
        return tex

    def image(self, surface: Optional[pygame.Surface], rect, alpha: float = 1.0, additive: bool = False,
              mul=(1.0, 1.0, 1.0), add=(0.0, 0.0, 0.0), flash: float = 0.0, angle: float = 0.0,
              pivot: Optional[Point] = None, src: Optional[pygame.Rect] = None, texture=None,
              flip: bool = False) -> None:
        """Картинка (или готовая texture) в прямоугольник rect кадра; src — её часть."""
        if (surface is None and texture is None) or alpha <= 0.004:
            return
        tex = texture or self.texture_of(surface)
        tw, th = tex.size
        x, y, w, h = rect
        s = src or pygame.Rect(0, 0, tw, th)
        u0, u1 = s.x / tw, s.right / tw
        if flip:
            u0, u1 = u1, u0
        self._target()
        self.gl.quad(tex, _corners(x, y, w, h, pivot or (x + w / 2, y + h / 2), angle),
                     (u0, s.y / th, u1, s.bottom / th), self.size, kind=1, alpha=alpha, mul=mul, add=add,
                     flash=flash, additive=additive)

    def blit(self, surface: Optional[pygame.Surface], pos: Point, alpha: float = 1.0, additive: bool = False) -> None:
        """Картинка без масштаба, левый верхний угол в pos."""
        if surface is not None:
            self.image(surface, (pos[0], pos[1], *surface.get_size()), alpha, additive)

    def rect(self, color, rect, alpha: float = 1.0) -> None:
        """Залитый прямоугольник."""
        self.image(None, rect, alpha, texture=self._white(), mul=tuple(c / 255 for c in color[:3]))

    def _white(self):
        return self.keyed_texture(("white",), lambda: _filled((4, 4), (255, 255, 255, 255)))

    # --- слой pygame ---

    @property
    def legacy(self) -> pygame.Surface:
        """Прозрачная картинка размером с кадр для рисования pygame; наложится при flush."""
        self._dirty = True
        return self._legacy

    def flush(self) -> None:
        """Нарисованное на слое pygame — в кадр (вся область поля: искать нарисованное дороже)."""
        if not self._dirty:
            return
        self._dirty = False
        surface = self._legacy
        box = self.clip
        if box.width <= 0 or box.height <= 0:
            return
        data = pygame.image.tobytes(surface.subsurface(box), "RGBA")
        self._legacy_tex.write(data, viewport=(box.x, box.y, box.width, box.height))
        self._target()
        w, h = self.size
        self.gl.quad(self._legacy_tex, _corners(box.x, box.y, box.width, box.height, (0, 0), 0),
                     (box.x / w, box.y / h, box.right / w, box.bottom / h), self.size, kind=2)
        surface.fill((0, 0, 0, 0), box)

    # --- вывод ---

    def read_into(self, target: pygame.Surface, area: Optional[pygame.Rect] = None) -> None:
        """Область кадра (по умолчанию clip) — в картинку pygame на то же место."""
        self.flush()
        area = (area or self.clip).clip(pygame.Rect(0, 0, *self.size))
        if area.width <= 0 or area.height <= 0:
            return
        data = self.fbo.read(viewport=tuple(area), components=3, alignment=1)
        target.blit(pygame.image.frombuffer(data, area.size, "RGB"), area.topleft)

    def present(self, window_size: tuple[int, int], area: Optional[pygame.Rect] = None) -> None:
        """Кадр в окно OpenGL (уже привязанный ctx.screen): область area — на то же место окна."""
        self.flush()
        area = area or self.clip
        w, h = self.size
        self.ctx.screen.use()
        self.ctx.viewport = (0, 0, *window_size)
        self.ctx.disable(moderngl.BLEND)
        self.gl.quad(self.color, _corners(area.x, area.y, area.width, area.height, (0, 0), 0),
                     (area.x / w, area.y / h, area.right / w, area.bottom / h), window_size, screen=True)


def _filled(size, color) -> pygame.Surface:
    s = pygame.Surface(size, pygame.SRCALPHA)
    s.fill(color)
    return s


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
        self.gl.quad(self.tex, _corners(*dst, (0, 0), 0),
                     (area.x / size[0], area.y / size[1], area.right / size[0], area.bottom / size[1]),
                     window_size, kind=1, screen=True)
