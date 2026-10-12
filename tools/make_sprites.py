"""Генерация базовых спрайтов юнитов в assets/sprites/.

Запуск: python tools/make_sprites.py
Спрайты рисуются примитивами на холсте 32x32 и сохраняются в PNG: по одному
кадру на класс, юнит смотрит вправо. Файл называется как id класса; default.png
используется для классов без собственного спрайта. Готовые PNG можно
перерисовать вручную в любом редакторе: игра читает только файлы.
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

SIZE = 32
OUT = Path(__file__).resolve().parent.parent / "assets" / "sprites"

SKIN = (236, 188, 150)
DARK = (30, 28, 34)
STEEL = (165, 174, 190)
STEEL_DARK = (110, 118, 135)
WOOD = (130, 88, 48)
LEATHER = (104, 72, 44)
GOLD = (236, 196, 72)
WHITE = (236, 236, 228)


def canvas() -> pygame.Surface:
    return pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)


def rect(s, color, x, y, w, h) -> None:
    pygame.draw.rect(s, color, pygame.Rect(x, y, w, h))


def outline(s: pygame.Surface) -> pygame.Surface:
    """Тёмная обводка в один пиксель вокруг непрозрачных пикселей."""
    result = canvas()
    mask = pygame.mask.from_surface(s)
    shadow = mask.to_surface(setcolor=DARK, unsetcolor=(0, 0, 0, 0))
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        result.blit(shadow, (dx, dy))
    result.blit(s, (0, 0))
    return result


def humanoid(s, body, pants, boots=LEATHER, skin=SKIN, robe=False, top=6) -> None:
    """Общая фигура: голова, торс, руки, ноги. top = верх головы (ниже = меньше ростом)."""
    if robe:
        rect(s, body, 10, top + 8, 12, 30 - top - 9)      # роба до пят
        rect(s, boots, 11, 29, 4, 2)
        rect(s, boots, 17, 29, 4, 2)
    else:
        rect(s, pants, 12, top + 18, 3, 29 - top - 18)    # ноги
        rect(s, pants, 17, top + 18, 3, 29 - top - 18)
        rect(s, boots, 11, 29, 5, 2)
        rect(s, boots, 16, 29, 5, 2)
        rect(s, body, 11, top + 8, 10, 10)                # торс
    rect(s, body, 9, top + 9, 2, 7)                       # дальняя рука
    rect(s, body, 21, top + 9, 2, 7)                      # ближняя рука
    rect(s, skin, 9, top + 15, 2, 2)
    rect(s, skin, 21, top + 15, 2, 2)
    rect(s, skin, 12, top, 8, 8)                          # голова
    rect(s, DARK, 17, top + 3, 1, 2)                      # глаз (смотрит вправо)


def knight() -> pygame.Surface:
    s = canvas()
    humanoid(s, STEEL, STEEL_DARK, STEEL_DARK)
    rect(s, STEEL, 12, 5, 8, 5)                           # шлем
    rect(s, STEEL_DARK, 12, 10, 8, 1)
    rect(s, DARK, 15, 9, 5, 1)                            # прорезь забрала
    rect(s, (200, 60, 60), 15, 2, 2, 3)                   # плюмаж
    rect(s, (70, 110, 200), 5, 14, 6, 10)                 # щит
    rect(s, GOLD, 7, 17, 2, 4)
    rect(s, WHITE, 24, 5, 2, 12)                          # клинок
    rect(s, GOLD, 23, 17, 4, 1)                           # гарда
    rect(s, WOOD, 24, 18, 2, 2)
    return outline(s)


def archer() -> pygame.Surface:
    s = canvas()
    green = (72, 140, 80)
    humanoid(s, green, (96, 80, 56))
    rect(s, green, 11, 5, 10, 3)                          # капюшон
    rect(s, green, 11, 5, 2, 8)
    rect(s, LEATHER, 7, 11, 2, 9)                         # колчан
    rect(s, WHITE, 7, 9, 2, 2)
    pygame.draw.arc(s, WOOD, pygame.Rect(20, 7, 9, 18), -1.45, 1.45, 2)   # лук
    pygame.draw.line(s, WHITE, (25, 8), (25, 23))                          # тетива
    return outline(s)


def cleric() -> pygame.Surface:
    s = canvas()
    humanoid(s, WHITE, WHITE, robe=True)
    rect(s, GOLD, 10, 20, 12, 1)                          # пояс
    rect(s, GOLD, 15, 14, 2, 15)                          # кайма
    rect(s, (150, 104, 60), 12, 5, 8, 2)                  # волосы
    rect(s, (150, 104, 60), 12, 5, 2, 5)
    rect(s, WOOD, 25, 7, 1, 23)                           # посох
    rect(s, GOLD, 23, 5, 5, 1)                            # крест
    rect(s, GOLD, 25, 3, 1, 5)
    return outline(s)


def mage() -> pygame.Surface:
    s = canvas()
    purple = (124, 84, 190)
    humanoid(s, purple, purple, robe=True, top=8)
    pygame.draw.polygon(s, purple, [(10, 9), (22, 9), (17, 0)])   # колпак
    rect(s, (92, 60, 150), 9, 9, 14, 2)                            # поля
    rect(s, GOLD, 10, 21, 12, 1)
    rect(s, WOOD, 25, 8, 1, 22)                                    # посох
    pygame.draw.circle(s, (110, 200, 250), (25, 6), 3)             # сфера
    rect(s, WHITE, 24, 5, 1, 1)
    return outline(s)


def goblin() -> pygame.Surface:
    s = canvas()
    skin = (112, 170, 84)
    humanoid(s, (120, 88, 56), (88, 66, 44), skin=skin, top=12)
    rect(s, skin, 11, 11, 10, 9)                                   # большая голова
    pygame.draw.polygon(s, skin, [(11, 13), (7, 11), (11, 16)])    # уши
    pygame.draw.polygon(s, skin, [(21, 13), (25, 11), (21, 16)])
    rect(s, DARK, 17, 14, 2, 2)
    rect(s, WHITE, 16, 18, 1, 1)                                   # клык
    rect(s, STEEL, 23, 20, 1, 6)                                   # кинжал
    rect(s, WOOD, 22, 26, 3, 1)
    return outline(s)


def orc() -> pygame.Surface:
    s = canvas()
    skin = (86, 132, 78)
    humanoid(s, skin, (84, 60, 40), skin=skin, top=5)
    rect(s, skin, 9, 13, 14, 11)                                   # широкий торс
    rect(s, LEATHER, 9, 21, 14, 2)                                 # пояс
    pygame.draw.line(s, LEATHER, (10, 13), (21, 21), 2)            # перевязь
    rect(s, skin, 11, 4, 10, 9)                                    # голова
    rect(s, DARK, 17, 7, 2, 2)
    rect(s, DARK, 12, 4, 9, 2)                                     # волосы
    rect(s, WHITE, 14, 12, 1, 2)                                   # клыки
    rect(s, WHITE, 19, 12, 1, 2)
    rect(s, WOOD, 26, 5, 1, 24)                                    # топорище
    pygame.draw.polygon(s, STEEL, [(27, 5), (31, 7), (31, 14), (27, 12)])   # лезвие
    return outline(s)


def rider() -> pygame.Surface:
    s = canvas()
    horse = (150, 100, 60)
    horse_dark = (112, 72, 42)
    pygame.draw.ellipse(s, horse, pygame.Rect(4, 17, 21, 9))       # корпус
    for x in (6, 10, 18, 22):
        rect(s, horse_dark, x, 24, 2, 7)                           # ноги
    pygame.draw.polygon(s, horse, [(21, 19), (26, 10), (31, 12), (30, 15), (27, 16), (25, 22)])   # шея и голова
    rect(s, DARK, 28, 12, 1, 1)
    pygame.draw.line(s, horse_dark, (4, 19), (1, 25), 2)           # хвост
    pygame.draw.line(s, horse_dark, (23, 12), (21, 18), 2)         # грива
    blue = (70, 110, 200)
    rect(s, blue, 12, 9, 7, 9)                                     # всадник
    rect(s, (60, 60, 90), 12, 17, 3, 6)                            # нога
    rect(s, SKIN, 13, 3, 6, 6)
    rect(s, STEEL, 13, 2, 6, 3)                                    # шлем
    rect(s, DARK, 17, 6, 1, 1)
    pygame.draw.line(s, WOOD, (8, 16), (30, 5), 1)                 # копьё
    pygame.draw.polygon(s, STEEL, [(29, 4), (31, 3), (31, 6)])
    return outline(s)


def default() -> pygame.Surface:
    """Заглушка для классов без собственного спрайта."""
    s = canvas()
    grey = (150, 152, 160)
    humanoid(s, grey, (110, 112, 120), (90, 90, 96), skin=(200, 200, 204))
    return outline(s)


SPRITES = {
    "knight": knight,
    "archer": archer,
    "cleric": cleric,
    "mage": mage,
    "goblin": goblin,
    "orc": orc,
    "rider": rider,
    "default": default,
}


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    OUT.mkdir(parents=True, exist_ok=True)
    for name, draw in SPRITES.items():
        pygame.image.save(draw(), str(OUT / f"{name}.png"))
    print(f"{len(SPRITES)} sprites written to {OUT}")


if __name__ == "__main__":
    main()
