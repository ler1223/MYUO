"""Общие заглушки картинок интерфейса: по одной на группу (все предметы, все навыки, фон и т. д.).

Запуск: python tools/make_ui_placeholders.py [--force]
Пишет в assets/ui/ самые общие ключи (см. pygame_art.py): bg, portrait, item, skill, passive,
stat, icon и icon/gold. Своя картинка кладётся рядом с более точным ключом (item/bow/hero_bow.png,
skill/fireball.png, bg/shop.png ...) и сразу заменяет заглушку. Существующие файлы без --force
не трогаются. Промпты для настоящих картинок — docs/art_prompts.md, раздел «Интерфейс».
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "assets" / "ui"
ICON = 128
LINE = (20, 20, 28)


def canvas(w: int = ICON, h: int = ICON) -> pygame.Surface:
    return pygame.Surface((w, h), pygame.SRCALPHA)


def badge(color, rim) -> pygame.Surface:
    """Круглая подложка иконки."""
    s = canvas()
    pygame.draw.circle(s, rim, (64, 64), 62)
    pygame.draw.circle(s, color, (64, 64), 54)
    return s


def background() -> pygame.Surface:
    """Фон экранов: тёмный вертикальный градиент с редким ромбовым узором."""
    w, h = 960, 640
    s = pygame.Surface((w, h))
    for y in range(h):
        k = y / h
        s.fill((round(22 + 14 * k), round(24 + 10 * k), round(38 + 18 * k)), (0, y, w, 1))
    for y in range(0, h, 80):
        for x in range((y // 80) % 2 * 60, w, 120):
            pygame.draw.polygon(s, (40, 44, 64), [(x, y + 20), (x + 20, y), (x + 40, y + 20), (x + 20, y + 40)], 1)
    return s


def portrait() -> pygame.Surface:
    """Безликий силуэт: голова и плечи."""
    s = canvas()
    s.fill((48, 54, 76, 255))
    pygame.draw.ellipse(s, (120, 126, 150), (14, 80, 100, 90))
    pygame.draw.circle(s, (150, 156, 178), (64, 54), 28)
    return s


def item() -> pygame.Surface:
    """Сундучок: общая заглушка для всех предметов."""
    s = canvas()
    pygame.draw.rect(s, (60, 64, 84), (0, 0, ICON, ICON), border_radius=16)
    body = pygame.Rect(22, 52, 84, 54)
    pygame.draw.rect(s, (150, 100, 55), body, border_radius=6)
    pygame.draw.rect(s, (175, 120, 65), (22, 34, 84, 26), border_top_left_radius=14, border_top_right_radius=14)
    pygame.draw.rect(s, LINE, (22, 34, 84, 72), 3, border_radius=8)
    pygame.draw.line(s, LINE, (22, 60), (106, 60), 3)
    pygame.draw.rect(s, (230, 200, 90), (56, 52, 16, 18), border_radius=3)
    return s


def skill() -> pygame.Surface:
    """Звезда-вспышка на синем: все активные навыки."""
    s = badge((50, 90, 170), (120, 170, 240))
    points = []
    for i in range(16):
        r = 44 if i % 2 == 0 else 18
        a = math.pi * i / 8 - math.pi / 2
        points.append((64 + r * math.cos(a), 64 + r * math.sin(a)))
    pygame.draw.polygon(s, (250, 235, 160), points)
    return s


def passive() -> pygame.Surface:
    """Щит на фиолетовом: все пассивки."""
    s = badge((100, 60, 150), (180, 130, 230))
    shield = [(64, 26), (98, 38), (94, 76), (64, 104), (34, 76), (30, 38)]
    pygame.draw.polygon(s, (225, 210, 245), shield)
    pygame.draw.polygon(s, LINE, shield, 3)
    return s


def stat() -> pygame.Surface:
    """Ромб: все статы (свой цвет стата интерфейс накладывает сам)."""
    s = canvas()
    pygame.draw.polygon(s, (235, 235, 240), [(64, 8), (120, 64), (64, 120), (8, 64)])
    pygame.draw.polygon(s, LINE, [(64, 8), (120, 64), (64, 120), (8, 64)], 4)
    return s


def icon() -> pygame.Surface:
    """Кружок: все значки интерфейса."""
    return badge((70, 76, 100), (160, 166, 190))


def gold() -> pygame.Surface:
    s = canvas()
    for dx, dy in ((-14, 12), (12, 4), (0, -12)):
        pygame.draw.circle(s, (120, 90, 20), (64 + dx, 64 + dy), 36)
        pygame.draw.circle(s, (240, 200, 70), (64 + dx, 64 + dy), 32)
        pygame.draw.circle(s, (200, 160, 40), (64 + dx, 64 + dy), 20, 4)
    return s


IMAGES = {
    "bg": background, "portrait": portrait, "item": item, "skill": skill, "passive": passive,
    "stat": stat, "icon": icon, "icon/gold": gold,
}


def main(argv: list[str]) -> int:
    force = "--force" in argv
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    for name, draw in IMAGES.items():
        path = OUT / f"{name}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not force:
            print(f"{name}: exists, kept")
            continue
        pygame.image.save(draw(), str(path))
        print(f"{name}: written")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
