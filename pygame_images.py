"""Картинки из папки с кэшем масштабированных копий и силуэт-заглушка (мир, редкие экраны)."""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Callable, Optional

import pygame

SPRITE_CACHE = 300


class ImageBank:
    """Картинки папки и их масштабированные копии (с белым силуэтом для вспышки), с кэшем."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self._images: dict[str, Optional[pygame.Surface]] = {}
        self._scaled: OrderedDict = OrderedDict()

    def image(self, name: str) -> Optional[pygame.Surface]:
        if name not in self._images:
            path = self.folder / name
            image = None
            if name and path.is_file():
                image = pygame.image.load(str(path))
                if pygame.display.get_surface() is not None:
                    image = image.convert_alpha()
            self._images[name] = image
        return self._images[name]

    def scaled(self, name: str, px_height: int, flip: bool, fallback: Callable[[], pygame.Surface]):
        """(картинка, белый силуэт) нужной высоты в пикселях окна."""
        key = (name, px_height, flip)
        if key in self._scaled:
            self._scaled.move_to_end(key)
            return self._scaled[key]
        image = self.image(name) or fallback()
        k = px_height / image.get_height()
        sprite = pygame.transform.smoothscale(image, (max(1, round(image.get_width() * k)), max(1, px_height)))
        if flip:
            sprite = pygame.transform.flip(sprite, True, False)
        white = sprite.copy()
        white.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
        self._scaled[key] = (sprite, white)
        if len(self._scaled) > SPRITE_CACHE:
            self._scaled.popitem(last=False)
        return sprite, white


def placeholder() -> pygame.Surface:
    """Силуэт для картинки, которой нет: голова и плащ."""
    s = pygame.Surface((60, 150), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (150, 150, 165), (10, 30, 40, 120))
    pygame.draw.circle(s, (190, 180, 170), (30, 20), 16)
    return s
