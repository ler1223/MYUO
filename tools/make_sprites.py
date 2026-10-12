"""Генерация спрайтов юнитов с простой анимацией в assets/sprites/.

Запуск: python tools/make_sprites.py

Каждый класс рисуется из простых фигур по общему «скелету»: корпус, голова, руки
и оружие в передней руке, которое поворачивается вместе с рукой. Поза задаётся
числами (сдвиг корпуса, углы руки и оружия), анимация это список поз.

На выходе для каждого класса папка assets/sprites/<id класса>/ с полосками кадров:
idle.png (стойка), melee.png (ближняя атака), ranged.png (дальняя атака),
cast.png (заклинание). Кадр 80x64, юнит смотрит вправо. Папка default
используется для классов без собственных спрайтов. Размеры и скорость
записаны в assets/sprites/sprites.json. Любую полоску можно перерисовать
вручную: игра читает только файлы.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Optional

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

FRAME_W, FRAME_H = 80, 64
ANCHOR_X = 30            # где в кадре стоят ноги юнита
GROUND = 60
OUT = Path(__file__).resolve().parent.parent / "assets" / "sprites"
META = {"frame_width": FRAME_W, "frame_height": FRAME_H, "anchor_x": ANCHOR_X,
        "frame_ms": 110, "idle_ms": 450, "animations": ["idle", "melee", "ranged", "cast"]}

SKIN = (236, 188, 150)
DARK = (30, 28, 34)
STEEL = (170, 178, 194)
STEEL_DARK = (112, 120, 138)
WOOD = (134, 92, 50)
LEATHER = (104, 72, 44)
GOLD = (236, 196, 72)
WHITE = (238, 238, 230)
GLOW = (140, 214, 255)

Surface = pygame.Surface
Point = tuple[float, float]


@dataclass(frozen=True)
class Look:
    """Внешность класса."""

    body: tuple[int, int, int]
    pants: tuple[int, int, int] = LEATHER
    boots: tuple[int, int, int] = LEATHER
    skin: tuple[int, int, int] = SKIN
    weapon: str = "none"       # sword, dagger, axe, staff, lance, bow, none
    orb: tuple[int, int, int] = GLOW   # навершие посоха
    shield: bool = False
    robe: bool = False
    bulk: int = 0              # насколько корпус шире обычного
    short: int = 0             # насколько юнит ниже обычного
    mount: bool = False        # верхом на лошади
    head: Optional[Callable[[Surface, int, int], None]] = None  # головной убор: (холст, x, y головы)


@dataclass(frozen=True)
class Pose:
    """Поза. Углы в градусах: 0 вправо (вперёд), 90 вниз, -90 вверх."""

    dx: int = 0                # сдвиг корпуса вперёд
    dy: int = 0                # сдвиг вверх-вниз (дыхание)
    arm: float = 70            # передняя рука
    weapon: float = -80        # оружие относительно горизонтали
    pull: int = 0              # натяжение тетивы
    shot: Optional[int] = None  # расстояние снаряда от руки; None = снаряда нет
    glow: int = 0              # радиус свечения заклинания


def vec(angle: float, length: float = 1.0) -> Point:
    rad = math.radians(angle)
    return math.cos(rad) * length, math.sin(rad) * length


def add(p: Point, q: Point) -> Point:
    return p[0] + q[0], p[1] + q[1]


def rect(s: Surface, color, x, y, w, h) -> None:
    pygame.draw.rect(s, color, pygame.Rect(round(x), round(y), w, h))


def line(s: Surface, color, a: Point, b: Point, width: int = 1) -> None:
    pygame.draw.line(s, color, (round(a[0]), round(a[1])), (round(b[0]), round(b[1])), width)


def outline(s: Surface) -> Surface:
    """Тёмная обводка в один пиксель вокруг непрозрачных пикселей."""
    result = Surface(s.get_size(), pygame.SRCALPHA)
    shadow = pygame.mask.from_surface(s).to_surface(setcolor=DARK, unsetcolor=(0, 0, 0, 0))
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        result.blit(shadow, (dx, dy))
    result.blit(s, (0, 0))
    return result


# --- оружие ----------------------------------------------------------------

def draw_weapon(s: Surface, look: Look, hand: Point, pose: Pose) -> Point:
    """Рисует оружие в руке. Возвращает точку, откуда вылетают снаряды и где светится заклинание."""
    w = pose.weapon
    forward, side = vec(w), vec(w + 90)
    tip = hand
    kind = look.weapon
    if kind in ("sword", "dagger"):
        length = 20 if kind == "sword" else 9
        tip = add(hand, vec(w, length))
        line(s, WHITE, add(hand, vec(w, 2)), tip, 3)
        guard = add(hand, vec(w, 3))
        line(s, GOLD, add(guard, (side[0] * 4, side[1] * 4)), add(guard, (-side[0] * 4, -side[1] * 4)), 2)
    elif kind == "axe":
        tip = add(hand, vec(w, 20))
        line(s, WOOD, add(hand, vec(w, -6)), tip, 2)
        base = add(hand, vec(w, 13))
        blade = [tip, add(tip, (side[0] * 8, side[1] * 8)), add(base, (side[0] * 9, side[1] * 9)), base]
        pygame.draw.polygon(s, STEEL, [(round(x), round(y)) for x, y in blade])
    elif kind == "staff":
        tip = add(hand, vec(w, 18))
        line(s, WOOD, add(hand, vec(w, -12)), tip, 2)
        pygame.draw.circle(s, look.orb, (round(tip[0]), round(tip[1])), 4)
        rect(s, WHITE, tip[0] - 2, tip[1] - 2, 1, 1)
    elif kind == "lance":
        tip = add(hand, vec(w, 24))
        line(s, WOOD, add(hand, vec(w, -10)), tip, 2)
        head = [add(tip, vec(w, 6)), add(tip, (side[0] * 3, side[1] * 3)), add(tip, (-side[0] * 3, -side[1] * 3))]
        pygame.draw.polygon(s, STEEL, [(round(x), round(y)) for x, y in head])
        tip = head[0]
    elif kind == "bow":
        points = []
        for step in (-1, -0.5, 0, 0.5, 1):   # дуга: концы у руки, середина выгнута вперёд
            bend = 6 * (1 - step * step)
            points.append((hand[0] + side[0] * 12 * step + forward[0] * bend,
                           hand[1] + side[1] * 12 * step + forward[1] * bend))
        pygame.draw.lines(s, WOOD, False, [(round(x), round(y)) for x, y in points], 2)
        nock = add(hand, vec(w, -pose.pull))
        line(s, WHITE, points[0], nock)
        line(s, WHITE, nock, points[-1])
        if pose.pull:
            line(s, WOOD, nock, add(nock, vec(w, 15)))
            rect(s, STEEL, nock[0] + forward[0] * 15, nock[1] + forward[1] * 15 - 1, 2, 2)
        tip = add(hand, vec(w, 6))
    return tip


# --- фигура ----------------------------------------------------------------

def draw_horse(s: Surface, x: int) -> None:
    horse, dark = (150, 100, 60), (112, 72, 42)
    pygame.draw.ellipse(s, horse, pygame.Rect(x - 20, 38, 42, 16))
    for leg in (-16, -8, 8, 15):
        rect(s, dark, x + leg, 50, 4, GROUND - 50)
    neck = [(x + 14, 42), (x + 24, 24), (x + 34, 28), (x + 32, 34), (x + 26, 36), (x + 22, 48)]
    pygame.draw.polygon(s, horse, neck)
    rect(s, DARK, x + 28, 28, 2, 2)
    line(s, dark, (x - 19, 42), (x - 26, 54), 3)     # хвост
    line(s, dark, (x + 18, 28), (x + 13, 42), 3)     # грива


def draw_unit(look: Look, pose: Pose, shot_kind: str = "rock") -> Surface:
    s = Surface((FRAME_W, FRAME_H), pygame.SRCALPHA)
    cx = ANCHOR_X + pose.dx
    half = 6 + look.bulk
    if look.mount:
        draw_horse(s, cx)
        hip_y, torso_h = 42, 14
        rect(s, look.pants, cx - 1, hip_y - 2, 5, 12)                  # нога всадника
    else:
        leg = 12 - look.short
        hip_y, torso_h = GROUND - leg, 16 - look.short
        if look.robe:
            rect(s, look.body, cx - half - 1, hip_y - 2, half * 2 + 2, leg)
            rect(s, look.boots, cx - 5, GROUND - 3, 4, 3)
            rect(s, look.boots, cx + 1, GROUND - 3, 4, 3)
        else:
            rect(s, look.pants, cx - 5, hip_y, 4, leg - 2)
            rect(s, look.pants, cx + 1, hip_y, 4, leg - 2)
            rect(s, look.boots, cx - 6, GROUND - 3, 6, 3)
            rect(s, look.boots, cx, GROUND - 3, 6, 3)
    top = hip_y - torso_h + pose.dy
    shoulder_y = top + 3

    # дальняя рука и щит
    back = (cx - half + 1, shoulder_y)
    back_hand = add(back, vec(105, 10))
    line(s, look.body, back, back_hand, 4)
    if look.shield:
        rect(s, (70, 110, 200), back_hand[0] - 7, back_hand[1] - 9, 10, 15)
        rect(s, GOLD, back_hand[0] - 4, back_hand[1] - 4, 4, 5)
    else:
        rect(s, look.skin, back_hand[0] - 2, back_hand[1] - 1, 4, 4)

    rect(s, look.body, cx - half, top, half * 2, torso_h)              # торс
    if look.robe:
        rect(s, GOLD, cx - half, top + torso_h - 4, half * 2, 2)       # пояс

    head_x, head_y = cx - 6, top - 12
    rect(s, look.skin, head_x, head_y, 12, 12)
    rect(s, DARK, head_x + 8, head_y + 5, 2, 3)                        # глаз
    if look.head:
        look.head(s, head_x, head_y)

    # передняя рука с оружием
    shoulder = (cx + half - 2, shoulder_y)
    hand = add(shoulder, vec(pose.arm, 11))
    tip = draw_weapon(s, look, hand, pose)
    line(s, look.body, shoulder, hand, 4)
    rect(s, look.skin, hand[0] - 2, hand[1] - 2, 4, 4)

    source = tip if look.weapon in ("staff", "bow") else hand
    if pose.glow:
        halo = Surface((FRAME_W, FRAME_H), pygame.SRCALPHA)
        pygame.draw.circle(halo, (*GLOW, 120), (round(source[0]), round(source[1])), pose.glow + 3)
        s.blit(halo, (0, 0))
        pygame.draw.circle(s, WHITE, (round(source[0]), round(source[1])), max(1, pose.glow // 2))
    if pose.shot is not None:
        px, py = source[0] + pose.shot, source[1]
        if shot_kind == "arrow":
            line(s, WOOD, (px - 10, py), (px, py))
            rect(s, STEEL, px, py - 1, 3, 3)
        elif shot_kind == "orb":
            pygame.draw.circle(s, GLOW, (round(px), round(py)), 4)
            pygame.draw.circle(s, WHITE, (round(px), round(py)), 2)
        else:
            pygame.draw.circle(s, STEEL_DARK, (round(px), round(py)), 3)
    return outline(s)


# --- анимации --------------------------------------------------------------

def rest(look: Look) -> Pose:
    """Стойка: как юнит держит оружие, когда ничего не делает."""
    return {
        "bow": Pose(arm=40, weapon=0),
        "lance": Pose(arm=75, weapon=-62),
        "staff": Pose(arm=55, weapon=-88),
    }.get(look.weapon, Pose())


def animations(look: Look) -> dict[str, tuple[list[Pose], str]]:
    """Название анимации -> (позы по кадрам, вид снаряда)."""
    base = rest(look)
    idle = [base, replace(base, dy=1)]

    if look.weapon == "lance":       # выпад копьём
        melee = [Pose(dx=-3, arm=160, weapon=0), Pose(dx=2, arm=60, weapon=0),
                 Pose(dx=9, arm=5, weapon=0), Pose(dx=3, arm=70, weapon=-30)]
    else:                            # замах и удар сверху вниз
        melee = [Pose(dx=-2, arm=-110, weapon=-125), Pose(dx=2, arm=-45, weapon=-50),
                 Pose(dx=8, arm=20, weapon=28), Pose(dx=3, arm=50, weapon=-30)]

    if look.weapon == "bow":         # поднять лук, натянуть, отпустить
        ranged = [Pose(arm=0, weapon=0), Pose(arm=0, weapon=0, pull=5), Pose(arm=0, weapon=0, pull=9),
                  Pose(dx=-1, arm=0, weapon=0, shot=14)]
        ranged_shot = "arrow"
    else:                            # бросок
        ranged = [Pose(dx=-2, arm=-130, weapon=-150), Pose(arm=-70, weapon=-90),
                  Pose(dx=4, arm=5, weapon=-20, shot=8), Pose(dx=2, arm=50, weapon=-40, shot=22)]
        ranged_shot = "rock"

    up = -88 if look.weapon in ("staff", "bow") else -80
    cast = [Pose(arm=-50, weapon=up, glow=2), Pose(arm=-75, weapon=up, glow=5),
            Pose(dy=-1, arm=-85, weapon=up, glow=8), Pose(arm=-20, weapon=up + 40, shot=12)]
    return {"idle": (idle, "rock"), "melee": (melee, "rock"), "ranged": (ranged, ranged_shot), "cast": (cast, "orb")}


def strip(look: Look, poses: list[Pose], shot_kind: str) -> Surface:
    sheet = Surface((FRAME_W * len(poses), FRAME_H), pygame.SRCALPHA)
    for i, pose in enumerate(poses):
        sheet.blit(draw_unit(look, pose, shot_kind), (i * FRAME_W, 0))
    return sheet


# --- головные уборы ---------------------------------------------------------

def helmet(s: Surface, x: int, y: int) -> None:
    rect(s, STEEL, x, y - 1, 12, 8)
    rect(s, STEEL, x, y + 7, 4, 5)
    rect(s, DARK, x + 5, y + 5, 7, 2)
    rect(s, (200, 60, 60), x + 4, y - 6, 3, 5)


def hood(s: Surface, x: int, y: int) -> None:
    green = (72, 140, 80)
    rect(s, green, x - 1, y - 2, 14, 5)
    rect(s, green, x - 1, y - 2, 4, 14)


def hair(s: Surface, x: int, y: int) -> None:
    brown = (150, 104, 60)
    rect(s, brown, x, y - 1, 12, 4)
    rect(s, brown, x, y, 3, 9)


def wizard_hat(s: Surface, x: int, y: int) -> None:
    pygame.draw.polygon(s, (124, 84, 190), [(x - 3, y + 2), (x + 15, y + 2), (x + 7, y - 13)])
    rect(s, (92, 60, 150), x - 4, y + 1, 20, 3)


def goblin_head(s: Surface, x: int, y: int) -> None:
    skin = (112, 170, 84)
    pygame.draw.polygon(s, skin, [(x, y + 3), (x - 7, y), (x, y + 8)])
    pygame.draw.polygon(s, skin, [(x + 12, y + 3), (x + 19, y), (x + 12, y + 8)])
    rect(s, WHITE, x + 7, y + 10, 2, 2)


def orc_head(s: Surface, x: int, y: int) -> None:
    rect(s, DARK, x, y - 1, 12, 3)
    rect(s, WHITE, x + 3, y + 10, 2, 3)
    rect(s, WHITE, x + 9, y + 10, 2, 3)


def cap(s: Surface, x: int, y: int) -> None:
    rect(s, STEEL, x, y - 1, 12, 5)


LOOKS = {
    "knight": Look(body=STEEL, pants=STEEL_DARK, boots=STEEL_DARK, weapon="sword", shield=True, head=helmet),
    "archer": Look(body=(72, 140, 80), pants=(96, 80, 56), weapon="bow", head=hood),
    "cleric": Look(body=WHITE, weapon="staff", orb=GOLD, robe=True, head=hair),
    "mage": Look(body=(124, 84, 190), weapon="staff", robe=True, head=wizard_hat),
    "goblin": Look(body=(120, 88, 56), pants=(88, 66, 44), skin=(112, 170, 84), weapon="dagger", short=4,
                   head=goblin_head),
    "orc": Look(body=(86, 132, 78), pants=(84, 60, 40), skin=(86, 132, 78), weapon="axe", bulk=2, head=orc_head),
    "rider": Look(body=(70, 110, 200), pants=(60, 60, 90), weapon="lance", mount=True, head=cap),
    "default": Look(body=(150, 152, 160), pants=(110, 112, 120), boots=(90, 90, 96), skin=(200, 200, 204)),
}


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    for name, look in LOOKS.items():
        folder = OUT / name
        folder.mkdir(parents=True, exist_ok=True)
        for animation, (poses, shot_kind) in animations(look).items():
            pygame.image.save(strip(look, poses, shot_kind), str(folder / f"{animation}.png"))
    (OUT / "sprites.json").write_text(json.dumps(META, indent=2) + "\n", encoding="utf-8")
    print(f"{len(LOOKS)} classes x {len(META['animations'])} animations written to {OUT}")


if __name__ == "__main__":
    main()
