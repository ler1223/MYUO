"""Задник и земля сцены: рисуются один раз в высоком разрешении и кэшируются.

- Небо: градиент цвета sky или картинка задника (assets/backgrounds). Земля картинки
  задника (строка backdrop_line, % высоты) ставится на дальний край земли сцены.
- Земля: текстура (assets/grounds) кладётся на плоскость земли в перспективе построчно:
  каждой строке экрана соответствует глубина z, по ней — строка текстуры и её масштаб.
  Без текстуры земля однотонная (earth). Вдали земля уходит в дымку цвета неба, у дальнего
  края плавно переходит в задник.
- Лежащие объекты сцены (слой ground) кладутся на землю так же, построчно.

Каждый кадр из готовой картинки вырезается видимая камерой часть и масштабируется в окно;
пока камера стоит, используется уже масштабированный кадр.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import pygame

from .camera import Camera
from .scene import BACKDROP_DIR, GROUND_DIR, PROPS_DIR, SceneConfig

EDGE_FADE = 0.12            # доля глубины земли у дальнего края, где она растворяется в заднике


def _load(folder: Path, name: str, cache: dict) -> Optional[pygame.Surface]:
    key = (folder, name)
    if key not in cache:
        path = folder / name
        cache[key] = pygame.image.load(str(path)) if name and path.is_file() else None
    return cache[key]


def _darken(surface: pygame.Surface, percent: float) -> None:
    if percent > 0:
        shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, int(255 * percent / 100)))
        surface.blit(shade, (0, 0))


class Backdrop:
    """Картинка задника с землёй для сцены; field — область поля в логических пикселях окна."""

    def __init__(self, field: pygame.Rect, props_dir: Optional[Path] = None):
        self.field = pygame.Rect(field)
        self.props_dir = props_dir or PROPS_DIR
        self._images: dict = {}
        self._key: Optional[tuple] = None
        self._surface: Optional[pygame.Surface] = None
        self._frame_key: Optional[tuple] = None
        self._frame: Optional[pygame.Surface] = None

    # --- готовая картинка ---

    def surface(self, scene: SceneConfig, quality: float) -> pygame.Surface:
        quality = round(max(1.0, min(3.0, quality)) * 4) / 4
        key = (scene.version(), quality)
        if key != self._key:
            self._surface = self.render(scene, quality)
            self._key = key
            self._frame_key = None
        return self._surface

    def draw(self, target: pygame.Surface, scene: SceneConfig, cam: Camera, quality: float) -> None:
        """Видимая камерой часть задника в область поля окна."""
        image = self.surface(scene, quality)
        q = image.get_width() / self.field.width
        frame_key = (self._key, cam.scale, cam.origin, cam.offset)
        if frame_key != self._frame_key:
            vw, vh = self.field.width * cam.scale, self.field.height * cam.scale   # всё поле в пикселях окна
            left, top = cam.p(*self.field.topleft)
            visible = pygame.Rect(left, top, round(vw), round(vh)).clip(cam.clip) if cam.clip else pygame.Rect(left, top, round(vw), round(vh))
            if visible.width <= 0 or visible.height <= 0:
                return
            # Та же область в пикселях картинки задника.
            src = pygame.Rect(round((visible.x - left) / cam.scale * q), round((visible.y - top) / cam.scale * q),
                              max(1, round(visible.width / cam.scale * q)), max(1, round(visible.height / cam.scale * q)))
            src = src.clip(image.get_rect())
            part = image.subsurface(src)
            self._frame = part if part.get_size() == visible.size else pygame.transform.smoothscale(part, visible.size)
            self._frame_pos = visible.topleft
            self._frame_key = frame_key
        if self._frame is not None:
            target.blit(self._frame, self._frame_pos)

    # --- построение ---

    def render(self, scene: SceneConfig, quality: float) -> pygame.Surface:
        size = (round(self.field.width * quality), round(self.field.height * quality))
        surface = pygame.Surface(size)
        projection = scene.projection()
        to_px = lambda ly: (ly - self.field.top) * quality          # логическая высота -> строка картинки
        far_y = projection.project(0, 0, scene.ground_depth)[1]
        self._sky(surface, scene, to_px(far_y), quality)
        self._ground(surface, scene, quality)
        for obj in sorted((o for o in scene.objects if o.layer == "ground"), key=lambda o: -o.z):
            self._ground_object(surface, scene, obj, quality)
        return surface

    def _sky(self, surface: pygame.Surface, scene: SceneConfig, far_row: float, quality: float) -> None:
        w, h = surface.get_size()
        sky = tuple(scene.sky)
        for y in range(h):                     # градиент: к дальнему краю земли светлее
            k = min(1.0, max(0.0, y / max(1, far_row)))
            pygame.draw.line(surface, tuple(min(255, int(c * (0.7 + 0.5 * k))) for c in sky), (0, y), (w, y))
        image = _load(BACKDROP_DIR, scene.backdrop, self._images)
        if image is None:
            return
        width = w * scene.backdrop_width / 100
        k = width / image.get_width()
        scaled = pygame.transform.smoothscale(image, (max(1, round(width)), max(1, round(image.get_height() * k))))
        _darken(scaled, scene.backdrop_darken)
        top = far_row - scaled.get_height() * scene.backdrop_line / 100
        left = (w - scaled.get_width()) / 2
        if top > 0:                            # над картинкой — цвет её верхней строки
            row = pygame.transform.smoothscale(scaled.subsurface((0, 0, scaled.get_width(), 1)), (1, 1)).get_at((0, 0))
            surface.fill(row, (0, 0, w, math.ceil(top)))
        surface.blit(scaled, (round(left), round(top)))

    def _rows(self, scene: SceneConfig, quality: float):
        """Строки земли: (строка картинки, глубина z, масштаб k, прозрачность у дальнего края)."""
        projection = scene.projection()
        h = round(self.field.height * quality)
        for row in range(h):
            ly = self.field.top + (row + 0.5) / quality
            z = projection.depth_at(ly)
            if z is None or z > scene.ground_depth or z < -projection.focal * 0.9:
                continue
            edge = min(1.0, (scene.ground_depth - z) / max(1.0, scene.ground_depth * EDGE_FADE))
            yield row, z, projection.scale(z), edge

    def _ground(self, surface: pygame.Surface, scene: SceneConfig, quality: float) -> None:
        w = surface.get_width()
        texture = _load(GROUND_DIR, scene.ground_texture, self._images)
        if texture is not None and pygame.display.get_surface() is not None:
            texture = texture.convert()
        sky, earth = tuple(scene.sky), tuple(scene.earth)
        center_px = (500 - self.field.left) * quality          # мировой x = 0
        line = pygame.Surface((w, 1))
        for row, z, k, edge in self._rows(scene, quality):
            haze = scene.haze / 100 * min(1.0, max(0.0, z) / max(1.0, scene.ground_depth)) ** 1.3
            if texture is None:
                line.fill(earth)
            else:
                tw, th = texture.get_size()
                tex_row = int((z / scene.ground_tile) % 1.0 * th)
                tile_px = scene.ground_tile * k * quality
                strip = texture.subsurface((0, min(th - 1, tex_row), tw, 1))
                if tile_px < 2:
                    line.fill(pygame.transform.smoothscale(strip, (1, 1)).get_at((0, 0)))
                else:
                    scaled = pygame.transform.smoothscale(strip, (max(1, round(tile_px)), 1))
                    x = center_px - math.ceil(center_px / tile_px) * tile_px
                    while x < w:
                        line.blit(scaled, (round(x), 0))
                        x += tile_px
            if haze > 0:
                fog = pygame.Surface((w, 1))
                fog.fill(sky)
                fog.set_alpha(int(255 * min(1.0, haze)))
                line.blit(fog, (0, 0))
            line.set_alpha(int(255 * max(0.0, edge)))
            surface.blit(line, (0, row))
            line.set_alpha(None)
        if scene.ground_darken > 0:
            shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            for row, _, _, edge in self._rows(scene, quality):
                pygame.draw.line(shade, (0, 0, 0, int(255 * scene.ground_darken / 100 * edge)), (0, row), (w, row))
            surface.blit(shade, (0, 0))

    def _ground_object(self, surface: pygame.Surface, scene: SceneConfig, obj, quality: float) -> None:
        """Картинка, лежащая на земле: верх картинки — дальний край, длина вглубь obj.size."""
        image = _load(self.props_dir, obj.image, self._images)
        if image is None:
            return
        if obj.flip:
            image = pygame.transform.flip(image, True, False)
        iw, ih = image.get_size()
        length, width = obj.size, obj.size * iw / ih
        near, far = obj.z - length / 2, obj.z + length / 2
        projection = scene.projection()
        for row, z, k, edge in self._rows(scene, quality):
            if not near <= z <= far:
                continue
            src_row = min(ih - 1, int((far - z) / length * ih))
            px_w = max(1, round(width * k * quality))
            strip = pygame.transform.smoothscale(image.subsurface((0, src_row, iw, 1)), (px_w, 1))
            cx = (projection.project(obj.x, 0, z)[0] - self.field.left) * quality
            surface.blit(strip, (round(cx - px_w / 2), row))
