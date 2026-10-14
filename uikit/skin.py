"""Нарисованные рамки и полосы.

Рамка (assets/ui/frame/<вид>.png, параметры — theme.json -> frames.<вид>):
  border — сколько пикселей картинки от края не тянется (углы): число или [по x, по y]; scale — во сколько раз
  рисовать картинку на экране; middle — ширина узора посередине краёв (тоже не тянется);
  fill — отступы от краёв картинки до тела (внутренней области), замеряет tools/measure_ui_art.py.

Тело — главное: прямоугольник виджета на экране — это его тело плюс отступы fill обычного
состояния. Любое другое состояние (наведение, выбор) рисуется так, чтобы ЕГО тело совпало с тем же
телом: украшения торчат наружу, а содержимое и линии рамки остаются на месте.

Полоса (assets/ui/bar/<вид>_end.png и _body.png, theme.json -> bars.<вид>.inner [x0, y0, y1]):
собирается на месте из конца, растянутого тела и зеркального конца, масштаб — по высоте, так что
концы не искажаются при любой длине. Пустая часть — та же полоса с затемнённой заливкой.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import pygame

CACHE_SIZE = 500
EMPTY_TINT = (52, 52, 64)            # заливка полосы в пустой части: умножение цвета


class Images:
    """Картинки по ключу «папка/имя» (без .png) из папки темы; нет файла — None."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self._cache: dict[str, Optional[pygame.Surface]] = {}

    def get(self, key: str) -> Optional[pygame.Surface]:
        if key not in self._cache:
            path = self.folder / f"{key}.png"
            image = None
            if path.is_file():
                image = pygame.image.load(str(path))
                image = image.convert_alpha() if pygame.display.get_surface() is not None else image
            self._cache[key] = image
        return self._cache[key]


def _cuts(length: int, target: int, border: int, middle: int, scale: float) -> tuple[list[int], list[int]]:
    """Точки разреза по одной оси: (в картинке, на экране)."""
    b = max(1, min(border, length // 2 - 1))
    t = max(1, min(round(b * scale), target // 2))
    m = max(0, min(middle, length - 2 * b - 2))
    tm = min(round(m * scale), max(0, target - 2 * t - 2)) if m else 0
    if not m or not tm:
        return [0, b, length - b, length], [0, t, target - t, target]
    src_mid, dst_mid = (length - m) // 2, (target - tm) // 2
    return ([0, b, src_mid, src_mid + m, length - b, length],
            [0, t, dst_mid, dst_mid + tm, target - t, target])


def nine_slice(image: pygame.Surface, size: tuple[int, int], border: Union[int, tuple[int, int]], scale: float = 0.5,
               middle: tuple[int, int] = (0, 0)) -> pygame.Surface:
    """Картинка рамки в размер size: углы с масштабом scale, края тянутся вдоль, середина — во все стороны;
    узор middle посередине краёв не тянется. border — одно число или (по x, по y): у низкой широкой
    рамки боковые украшения шире, чем толщина верхнего и нижнего края."""
    w, h = image.get_size()
    bx, by = (border, border) if isinstance(border, int) else border
    xs, txs = _cuts(w, size[0], bx, middle[0], scale)
    ys, tys = _cuts(h, size[1], by, middle[1], scale)
    out = pygame.Surface(size, pygame.SRCALPHA)
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            src = pygame.Rect(xs[i], ys[j], xs[i + 1] - xs[i], ys[j + 1] - ys[j])
            dst = pygame.Rect(txs[i], tys[j], txs[i + 1] - txs[i], tys[j + 1] - tys[j])
            if src.width > 0 and src.height > 0 and dst.width > 0 and dst.height > 0:
                out.blit(pygame.transform.smoothscale(image.subsurface(src), dst.size), dst.topleft)
    return out


class Skin:
    def __init__(self, images: Images, frames: dict, bars: dict):
        self.images = images
        self.frames = frames
        self.bars = bars
        self._cache: dict = {}

    def _remember(self, key, make):
        if key not in self._cache:
            self._cache[key] = make()
            if len(self._cache) > CACHE_SIZE:
                self._cache.pop(next(iter(self._cache)))
        return self._cache[key]

    # --- рамки ---

    def has(self, kind: str) -> bool:
        return self.images.get(f"frame/{kind}") is not None

    def insets(self, kind: str) -> tuple[int, int, int, int]:
        """Отступы от прямоугольника рамки до её тела на экране (слева, сверху, справа, снизу)."""
        spec = self.frames.get(kind, {})
        scale = float(spec.get("scale", 0.5))
        fill = spec.get("fill", [0, 0, 0, 0]) if self.has(kind) else [0, 0, 0, 0]
        return tuple(round(v * scale) for v in fill)

    def body(self, kind: str, rect: pygame.Rect) -> pygame.Rect:
        """Тело рамки kind, нарисованной в rect."""
        left, top, right, bottom = self.insets(kind)
        return pygame.Rect(rect.x + left, rect.y + top, max(0, rect.width - left - right),
                           max(0, rect.height - top - bottom))

    def around(self, kind: str, body: pygame.Rect) -> pygame.Rect:
        """Прямоугольник рамки kind, тело которой — body."""
        left, top, right, bottom = self.insets(kind)
        return pygame.Rect(body.x - left, body.y - top, body.width + left + right, body.height + top + bottom)

    def draw(self, screen: pygame.Surface, kind: str, rect: pygame.Rect, body: Optional[pygame.Rect] = None) -> bool:
        """Рамка kind в rect; с body — так, чтобы тело рамки совпало с body. False — картинки нет."""
        image = self.images.get(f"frame/{kind}")
        if image is None:
            return False
        if body is not None:
            rect = self.around(kind, body)
        if rect.width < 4 or rect.height < 4:
            return True
        spec = self.frames.get(kind, {})
        scale = float(spec.get("scale", 0.5))
        fill = spec.get("fill", [0, 0, 0, 0])
        border = spec.get("border", 32)
        bx, by = (border, border) if isinstance(border, int) else border
        border = (max(int(bx), fill[0] + 1, fill[2] + 1), max(int(by), fill[1] + 1, fill[3] + 1))  # тело внутри углов
        middle = spec.get("middle", [0, 0])
        surface = self._remember(("frame", kind, rect.size), lambda: nine_slice(
            image, rect.size, border, scale, (int(middle[0]), int(middle[1]))))
        screen.blit(surface, rect.topleft)
        return True

    # --- полосы ---

    def has_bar(self, kind: str) -> bool:
        return self.images.get(f"bar/{kind}_end") is not None and self.images.get(f"bar/{kind}_body") is not None

    def bar_inner(self, kind: str, rect: pygame.Rect) -> pygame.Rect:
        """Область заливки полосы kind, собранной в rect (для подписи поверх)."""
        end = self.images.get(f"bar/{kind}_end")
        if end is None:
            return rect
        x0, y0, y1 = self.bars.get(kind, {}).get("inner", [0, 0, end.get_height()])
        k = rect.height / end.get_height()
        ends = self._end_width(end, rect)
        ix = round(x0 * ends / end.get_width())
        return pygame.Rect(rect.x + ix, rect.y + round(y0 * k), rect.width - 2 * ix, max(1, round((y1 - y0) * k)))

    def _end_width(self, end: pygame.Surface, rect: pygame.Rect) -> int:
        width = round(end.get_width() * rect.height / end.get_height())
        return max(1, min(width, rect.width // 2 - 1))

    def _bar_surfaces(self, kind: str, size: tuple[int, int]) -> tuple[pygame.Surface, pygame.Surface]:
        def make():
            end, body = self.images.get(f"bar/{kind}_end"), self.images.get(f"bar/{kind}_body")
            w, h = size
            ends = self._end_width(end, pygame.Rect(0, 0, w, h))
            full = pygame.Surface(size, pygame.SRCALPHA)
            left = pygame.transform.smoothscale(end, (ends, h))
            middle = max(1, w - 2 * ends)
            full.blit(pygame.transform.smoothscale(body, (middle, h)), (ends, 0))
            full.blit(left, (0, 0))
            full.blit(pygame.transform.flip(left, True, False), (w - ends, 0))
            empty = full.copy()
            inner = self.bar_inner(kind, pygame.Rect(0, 0, w, h))
            dark = pygame.Surface(inner.size, pygame.SRCALPHA)
            dark.fill((*EMPTY_TINT, 255))
            empty.blit(dark, inner.topleft, special_flags=pygame.BLEND_RGBA_MULT)
            return full, empty
        return self._remember(("bar", kind, size), make)

    def draw_bar(self, screen: pygame.Surface, kind: str, rect: pygame.Rect, share: float) -> bool:
        """Полоса kind в rect, заполненная на долю share (0..1). False — картинок нет."""
        if not self.has_bar(kind) or rect.width < 8 or rect.height < 3:
            return False
        full, empty = self._bar_surfaces(kind, rect.size)
        screen.blit(empty, rect.topleft)
        inner = self.bar_inner(kind, pygame.Rect(0, 0, *rect.size))
        width = round(inner.width * max(0.0, min(1.0, share)))
        if width > 0:
            area = pygame.Rect(0, 0, inner.x + width, rect.height)      # левый конец и заливка до доли
            screen.blit(full, rect.topleft, area)
        return True
