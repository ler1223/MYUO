"""Заглушки спрайтов объектов открытого мира: простые картинки, пока нет нарисованных.

Запуск: python tools/make_world_placeholders.py [--force]
Пишет в assets/world/: town, fort, ruins, chest, chest_open, tree, rock (PNG с прозрачностью,
нижний край картинки — земля). Существующие файлы не трогает без --force, чтобы не затереть
настоящие картинки. Промпты для настоящих — docs/art_prompts.md, раздел «Открытый мир».
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "assets" / "world"
LINE = (40, 30, 30)


def canvas(w: int, h: int) -> pygame.Surface:
    return pygame.Surface((w, h), pygame.SRCALPHA)


def outlined(s: pygame.Surface, color, shape: str, *args) -> None:
    getattr(pygame.draw, shape)(s, color, *args)
    getattr(pygame.draw, shape)(s, LINE, *args, 3)


def town() -> pygame.Surface:
    s = canvas(300, 240)
    for x, w, h, roof in ((20, 90, 90, (170, 70, 60)), (110, 100, 120, (150, 60, 55)), (205, 80, 80, (180, 90, 60))):
        base = 238
        outlined(s, (225, 210, 180), "rect", pygame.Rect(x, base - h, w, h))
        outlined(s, roof, "polygon", [(x - 8, base - h), (x + w // 2, base - h - 55), (x + w + 8, base - h)])
        outlined(s, (90, 60, 40), "rect", pygame.Rect(x + w // 2 - 12, base - 40, 24, 40))
    return s


def fort() -> pygame.Surface:
    s = canvas(280, 260)
    outlined(s, (150, 150, 160), "rect", pygame.Rect(30, 110, 220, 148))
    for x in (10, 210):
        outlined(s, (135, 135, 150), "rect", pygame.Rect(x, 50, 60, 208))
        for i in range(3):
            outlined(s, (135, 135, 150), "rect", pygame.Rect(x + i * 22, 32, 16, 20))
    for i in range(8):
        outlined(s, (150, 150, 160), "rect", pygame.Rect(40 + i * 26, 96, 16, 16))
    outlined(s, (70, 50, 40), "rect", pygame.Rect(115, 180, 50, 78))
    pygame.draw.line(s, LINE, (140, 50), (140, 96), 3)
    outlined(s, (60, 90, 170), "polygon", [(140, 50), (180, 62), (140, 74)])
    return s


def ruins() -> pygame.Surface:
    s = canvas(240, 220)
    for x, h in ((20, 170), (90, 120), (160, 190)):
        outlined(s, (175, 170, 150), "rect", pygame.Rect(x, 218 - h, 45, h))
    outlined(s, (175, 170, 150), "rect", pygame.Rect(10, 40, 110, 22))
    for x, y in ((120, 200), (200, 205), (70, 205)):
        outlined(s, (150, 145, 130), "ellipse", pygame.Rect(x, y, 34, 16))
    return s


def chest(open_: bool) -> pygame.Surface:
    s = canvas(90, 80)
    outlined(s, (150, 95, 45), "rect", pygame.Rect(5, 35, 80, 43))
    if open_:
        outlined(s, (120, 75, 35), "polygon", [(5, 35), (85, 35), (75, 5), (15, 5)])
        pygame.draw.rect(s, (40, 25, 15), pygame.Rect(9, 36, 72, 8))
    else:
        outlined(s, (170, 110, 55), "rect", pygame.Rect(5, 15, 80, 24), )
        outlined(s, (230, 190, 70), "rect", pygame.Rect(38, 30, 14, 16))
    return s


def tree() -> pygame.Surface:
    s = canvas(200, 300)
    outlined(s, (110, 75, 45), "rect", pygame.Rect(88, 200, 24, 98))
    for y, w in ((20, 80), (70, 130), (130, 180)):
        outlined(s, (50, 110, 60), "polygon", [(100, y), (100 - w // 2, y + 90), (100 + w // 2, y + 90)])
    return s


def rock() -> pygame.Surface:
    s = canvas(160, 100)
    outlined(s, (130, 130, 135), "polygon", [(10, 98), (30, 40), (70, 10), (120, 25), (150, 98)])
    pygame.draw.line(s, (100, 100, 105), (70, 10), (80, 98), 3)
    return s


IMAGES = {"town": town, "fort": fort, "ruins": ruins, "chest": lambda: chest(False),
          "chest_open": lambda: chest(True), "tree": tree, "rock": rock}


def main(argv: list[str]) -> int:
    force = "--force" in argv
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    OUT.mkdir(parents=True, exist_ok=True)
    for name, draw in IMAGES.items():
        path = OUT / f"{name}.png"
        if path.exists() and not force:
            print(f"{name}: exists, kept")
            continue
        pygame.image.save(draw(), str(path))
        print(f"{name}: written")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
