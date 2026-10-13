"""Карты юнитов: арт класса в рамке, повёрнутые к противнику.

Арт берётся из assets/cards/<id класса>.png (любой размер, лучше портретный 3:4).
Если файла нет, рисуется заглушка: стоячий спрайт класса на тёмном фоне.
Поворот к противнику — это «псевдо-3D»: карта сжата по ширине, ближний к нам
край выше, дальний ниже. Повёрнутые карты кэшируются: рисуются один раз.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

import pygame

ROOT = Path(__file__).resolve().parent
CARD_DIR = ROOT / "assets" / "cards"
SPRITE_DIR = ROOT / "assets" / "sprites"
TILT_DEGREES = 24           # насколько карта повёрнута к противнику
PERSPECTIVE = 0.22          # насколько дальний край карты ниже ближнего

SIDE_FRAMES = {"left": ((214, 178, 96), (92, 70, 34)), "right": ((196, 104, 82), (84, 38, 34))}
CARD_BACK = (28, 30, 40)


def _fallback_art(class_id: str) -> Optional[pygame.Surface]:
    """Первый кадр стойки из спрайтов класса (или заглушки default), без прозрачных полей."""
    meta = json.loads((SPRITE_DIR / "sprites.json").read_text(encoding="utf-8"))
    for name in (class_id, "default"):
        path = SPRITE_DIR / name / "idle.png"
        if not path.exists():
            continue
        own = SPRITE_DIR / name / "sprite.json"
        if own.exists():
            meta = {**meta, **json.loads(own.read_text(encoding="utf-8"))}
        sheet = pygame.image.load(str(path)).convert_alpha()
        frame = sheet.subsurface(pygame.Rect(0, 0, meta["frame_width"], meta["frame_height"])).copy()
        return frame.subsurface(frame.get_bounding_rect()).copy()
    return None


class CardArt:
    """Готовые изображения карт: плоские и повёрнутые, живые и погибшие."""

    def __init__(self, card_dir: Path = CARD_DIR):
        self.card_dir = Path(card_dir)
        self._art: dict[str, Optional[pygame.Surface]] = {}
        self._cards: dict[tuple, pygame.Surface] = {}
        self._masks: dict[tuple, pygame.Surface] = {}

    def has_art(self, class_id: str) -> bool:
        return (self.card_dir / f"{class_id}.png").exists()

    def art(self, class_id: str) -> Optional[pygame.Surface]:
        if class_id not in self._art:
            path = self.card_dir / f"{class_id}.png"
            self._art[class_id] = pygame.image.load(str(path)).convert_alpha() if path.exists() else None
        return self._art[class_id]

    def flat(self, class_id: str, name: str, level: int, side: str, size: tuple[int, int],
             font: pygame.font.Font) -> pygame.Surface:
        """Карта без поворота: рамка цвета стороны, арт, плашка с именем, уровень."""
        w, h = size
        light, dark = SIDE_FRAMES[side]
        card = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(card, dark, card.get_rect(), border_radius=7)
        pygame.draw.rect(card, light, card.get_rect(), 2, border_radius=7)
        window = pygame.Rect(5, 5, w - 10, h - 10)
        pygame.draw.rect(card, CARD_BACK, window)
        art = self.art(class_id)
        if art is not None:
            # Арт заполняет окно целиком, лишнее обрезается (по центру и сверху).
            k = max(window.width / art.get_width(), window.height / art.get_height())
            scaled = pygame.transform.smoothscale(art, (math.ceil(art.get_width() * k), math.ceil(art.get_height() * k)))
            card.blit(scaled, window.topleft, pygame.Rect((scaled.get_width() - window.width) // 2, 0, *window.size))
        else:
            for i in range(window.height):           # заглушка: тёмный градиент и спрайт класса
                k = i / window.height
                pygame.draw.line(card, (int(40 + 30 * k), int(44 + 26 * k), int(62 + 10 * k)),
                                 (window.left, window.top + i), (window.right - 1, window.top + i))
            sprite = _fallback_art(class_id)
            if sprite is not None:
                k = min(window.width * 0.9 / sprite.get_width(), window.height * 0.78 / sprite.get_height())
                sprite = pygame.transform.scale(sprite, (max(1, int(sprite.get_width() * k)), max(1, int(sprite.get_height() * k))))
                card.blit(sprite, sprite.get_rect(midbottom=(window.centerx, window.bottom - 16)))
        pygame.draw.rect(card, light, window, 1)
        plate = pygame.Rect(window.left, window.bottom - 18, window.width, 18)
        shade = pygame.Surface(plate.size, pygame.SRCALPHA)
        shade.fill((10, 10, 16, 190))
        card.blit(shade, plate)
        label = font.render(name, True, (240, 236, 220))
        if label.get_width() > plate.width - 6:
            label = pygame.transform.smoothscale(label, (plate.width - 6, label.get_height()))
        card.blit(label, label.get_rect(center=plate.center))
        badge = pygame.Rect(window.left + 3, window.top + 3, 22, 16)
        pygame.draw.rect(card, dark, badge, border_radius=4)
        pygame.draw.rect(card, light, badge, 1, border_radius=4)
        lvl = font.render(str(level), True, (250, 240, 200))
        card.blit(lvl, lvl.get_rect(center=badge.center))
        return card

    def tilted(self, class_id: str, name: str, level: int, side: str, size: tuple[int, int],
               font: pygame.font.Font, dead: bool = False) -> pygame.Surface:
        """Карта, повёрнутая к противнику. Левая сторона смотрит вправо, правая влево."""
        key = (class_id, name, level, side, size, dead)
        if key not in self._cards:
            card = self.flat(class_id, name, level, side, size, font)
            if dead:
                card = pygame.transform.grayscale(card)
                card.fill((120, 120, 120, 150), special_flags=pygame.BLEND_RGBA_MULT)
            self._cards[key] = tilt(card, TILT_DEGREES, facing_right=side == "left")
        return self._cards[key]

    def silhouette(self, card: pygame.Surface) -> pygame.Surface:
        """Белый силуэт карты для вспышки при попадании."""
        key = id(card)
        if key not in self._masks:
            mask = pygame.mask.from_surface(card)
            self._masks[key] = mask.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
        return self._masks[key]


def tilt(card: pygame.Surface, degrees: float, facing_right: bool) -> pygame.Surface:
    """Поворот карты вокруг вертикальной оси: столбцы пикселей сжимаются к дальнему краю."""
    w, h = card.get_size()
    out_w = max(1, round(w * math.cos(math.radians(degrees))))
    out = pygame.Surface((out_w, h), pygame.SRCALPHA)
    for x in range(out_w):
        t = x / max(1, out_w - 1)               # 0 у левого края, 1 у правого
        far = t if facing_right else 1 - t      # 1 у дальнего края
        k = 1 - PERSPECTIVE * far * math.sin(math.radians(degrees)) * 2
        column_h = max(1, round(h * k))
        src_x = min(w - 1, int(x * w / out_w))
        column = card.subsurface(pygame.Rect(src_x, 0, 1, h))
        out.blit(pygame.transform.smoothscale(column, (1, column_h)), (x, (h - column_h) // 2))
    return out
