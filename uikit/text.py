"""Текст: шрифты из файлов, стили, рендер с тенью и обводкой, выравнивание в прямоугольнике.

Вертикально текст ставится по высоте заглавных букв (у Fira — «Н»), а не по высоте картинки строки:
в картинке есть место под выносные элементы (у, р, д), из-за него текст по «центру картинки»
сидит выше середины рамки. Высоту заглавных шрифт сообщает сам (metrics).
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

import pygame

ELLIPSIS = "…"
SHRINK = 0.72                  # до какой доли размера ужимается не влезающая строка
MIN_SIZE = 12
FALLBACK = ["segoeui", "arial", "dejavusans"]
CACHE_SIZE = 1200
Color = tuple[int, int, int]


@dataclass(frozen=True)
class TextStyle:
    face: str = "medium"                 # ключ шрифта темы: regular, medium, semibold, italic
    size: int = 24
    color: Color = (238, 232, 216)
    shadow: Optional[Color] = (6, 6, 12)  # тень вниз на size/14 px; None — без тени
    outline: Optional[Color] = None      # обводка (числа поверх картинок)

    def but(self, **changes) -> "TextStyle":
        return replace(self, **changes)

    def scaled(self, k: float) -> "TextStyle":
        return replace(self, size=max(6, round(self.size * k)))


class Fonts:
    """Шрифты по (начертание, размер); нет файла — системный."""

    def __init__(self, files: dict[str, Path]):
        self.files = files
        self._cache: dict[tuple[str, int], pygame.font.Font] = {}

    def get(self, face: str, size: int) -> pygame.font.Font:
        key = (face, size)
        if key not in self._cache:
            path = self.files.get(face)
            if path is not None and Path(path).is_file():
                self._cache[key] = pygame.font.Font(str(path), size)
            else:
                self._cache[key] = pygame.font.SysFont(FALLBACK, size, bold=face != "regular",
                                                       italic=face == "italic")
        return self._cache[key]


class Text:
    def __init__(self, fonts: Fonts):
        self.fonts = fonts
        self._cache: OrderedDict = OrderedDict()
        self._caps: dict[tuple[str, int], int] = {}

    def font(self, style: TextStyle) -> pygame.font.Font:
        return self.fonts.get(style.face, style.size)

    def width(self, text: str, style: TextStyle) -> int:
        return self.font(style).size(text)[0]

    def cap_height(self, style: TextStyle) -> int:
        """Высота заглавных над базовой линией."""
        key = (style.face, style.size)
        if key not in self._caps:
            metrics = self.font(style).metrics("Н")
            self._caps[key] = metrics[0][3] if metrics and metrics[0] else round(style.size * 0.7)
        return self._caps[key]

    def line_height(self, style: TextStyle) -> int:
        return round(self.font(style).get_linesize() * 1.02)

    def render(self, text: str, style: TextStyle) -> tuple[pygame.Surface, int]:
        """(картинка, поле): поле — сколько пикселей тень и обводка добавили слева и сверху."""
        key = (text, style)
        hit = self._cache.get(key)
        if hit is not None:
            self._cache.move_to_end(key)
            return hit
        font = self.font(style)
        main = font.render(text, True, style.color)
        ring = max(1, round(style.size / 22)) if style.outline else 0
        drop = max(1, round(style.size / 14)) if style.shadow else 0
        pad = ring
        out = pygame.Surface((main.get_width() + 2 * ring + drop, main.get_height() + 2 * ring + drop), pygame.SRCALPHA)
        if style.shadow:
            shade = font.render(text, True, style.shadow)
            shade.set_alpha(170)
            out.blit(shade, (pad + drop, pad + drop))
        if style.outline:
            edge = font.render(text, True, style.outline)
            for dx in range(-ring, ring + 1):
                for dy in range(-ring, ring + 1):
                    if dx or dy:
                        out.blit(edge, (pad + dx, pad + dy))
        out.blit(main, (pad, pad))
        self._cache[key] = (out, pad)
        if len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return out, pad

    def shrink(self, text: str, style: TextStyle, width: int) -> TextStyle:
        """Как в UO: длинная подпись сначала ужимается (до SHRINK размера), и только потом режется «…»."""
        if width <= 0 or self.width(text, style) <= width:
            return style
        low = max(MIN_SIZE, round(style.size * SHRINK))
        for size in range(style.size - 1, low - 1, -1):
            smaller = style.but(size=size)
            if self.width(text, smaller) <= width:
                return smaller
        return style.but(size=low) if low < style.size else style

    def fit(self, text: str, style: TextStyle, width: int) -> str:
        """Текст, обрезанный с «…», чтобы влез в width."""
        font = self.font(style)
        if width <= 0:
            return ""
        if font.size(text)[0] <= width:
            return text
        low, high = 0, len(text)
        while low < high:                       # самая длинная голова, которая влезает с «…»
            mid = (low + high + 1) // 2
            if font.size(text[:mid].rstrip() + ELLIPSIS)[0] <= width:
                low = mid
            else:
                high = mid - 1
        return text[:low].rstrip() + ELLIPSIS if low else ""

    def wrap(self, text: str, style: TextStyle, width: int) -> list[str]:
        """Строки не шире width по словам; слово длиннее строки обрезается с «…»."""
        font = self.font(style)
        lines: list[str] = []
        for paragraph in text.split("\n"):
            line = ""
            for word in paragraph.split(" "):
                candidate = f"{line} {word}" if line else word
                if font.size(candidate)[0] <= width or not line:
                    line = candidate
                else:
                    lines.append(line)
                    line = word
            lines.append(line)
        return [self.fit(line, style, width) for line in lines]

    def draw(self, screen: pygame.Surface, text: str, style: TextStyle, rect: pygame.Rect, align: str = "left",
             valign: str = "center", fit: bool = True) -> pygame.Rect:
        """Строка в прямоугольнике. align: left, center, right; valign: top (заглавные от верха),
        center (заглавные посередине), bottom (базовая линия по низу). Возвращает рамку заглавных."""
        if fit:
            style = self.shrink(text, style, rect.width)
            text = self.fit(text, style, rect.width)
        if not text:
            return pygame.Rect(rect.x, rect.y, 0, 0)
        font = self.font(style)
        width = font.size(text)[0]
        cap, ascent = self.cap_height(style), font.get_ascent()
        if align == "center":
            x = rect.centerx - width // 2
        elif align == "right":
            x = rect.right - width
        else:
            x = rect.x
        if valign == "top":
            baseline = rect.y + cap
        elif valign == "bottom":
            baseline = rect.bottom
        else:
            baseline = rect.centery + cap // 2
        image, pad = self.render(text, style)
        screen.blit(image, (x - pad, baseline - ascent - pad))
        return pygame.Rect(x, baseline - cap, width, cap)

    def paragraph(self, screen: pygame.Surface, text: str, style: TextStyle, rect: pygame.Rect,
                  max_lines: Optional[int] = None) -> int:
        """Абзац с переносом сверху вниз. Возвращает y под последней строкой."""
        lines = self.wrap(text, style, rect.width)
        if max_lines is not None and len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = self.fit(lines[-1] + ELLIPSIS, style, rect.width)
        step = self.line_height(style)
        y = rect.y
        for line in lines:
            self.draw(screen, line, style, pygame.Rect(rect.x, y, rect.width, step), valign="center")
            y += step
        return y
