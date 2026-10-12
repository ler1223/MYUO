"""Экран боя со спрайтами юнитов (вкладка Arena).

Показывает тот же бой, что и вкладка Battle: читает состояние BattleView, которое
строится только из событий симуляции. Когда юнит применяет навык, проигрывается
одна из его анимаций; какая именно, решает вид навыка (см. animation_for).

Спрайты лежат в assets/sprites/<id класса>/<анимация>.png: горизонтальные полоски
кадров. Размер кадра и скорость записаны в assets/sprites/sprites.json
(см. tools/make_sprites.py).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import pygame

from game.definitions import SkillDefinition
from game.events import format_event
from game.squad import Formation, Squad
from game.unit import Unit
from pygame_ui import BG, DIM, GREEN, HEIGHT, PANEL, RED, TEXT, UI, WIDTH, YELLOW, fit

SPRITE_DIR = Path(__file__).resolve().parent / "assets" / "sprites"
DEFAULT_SPRITE = "default"
SPRITE_SCALE = 2           # кадр 80x64 рисуется как 160x128
DEAD_ALPHA = 120
IDLE = "idle"
DEFAULT_META = {"frame_width": 80, "frame_height": 64, "anchor_x": 30, "frame_ms": 110, "idle_ms": 450}
GROUND_MARGIN = 4          # сколько пикселей кадра остаётся под ногами юнита
BODY_HEIGHT = 100          # высота фигуры на экране: над ней рисуются подписи

# Вид навыка (его тег) -> анимация. Навык без этих тегов считается ближней атакой.
SKILL_ANIMATIONS = (("ranged", "ranged"), ("magic", "cast"), ("melee", "melee"))
FALLBACK_ANIMATION = "melee"

# Раскладка поля
CENTER_X = WIDTH // 2
HORIZON_Y = 150
FIELD_BOTTOM = 498
FRONT_OFFSET = 70          # расстояние переднего ряда от центра
ROW_STEP = 118             # шаг между рядами формации (по горизонтали)
COL_STEP = 146             # шаг между колоннами: фигура 100 + подписи над ней 46
COL_SKEW = 14              # сдвиг колонн для ощущения глубины
FIRST_FEET_Y = 198
BAR_W = 64
PIP = 6
LOG_TOP = FIELD_BOTTOM + 8
LOG_LINES = 5
LOG_LINE_H = 18

SKY = (38, 44, 62)
GROUND = (52, 70, 56)
GROUND_LINE = (62, 84, 66)
SHADOW = (34, 46, 38)
HP_BACK = (70, 40, 40)
AP_COLOR = (90, 160, 240)
PP_COLOR = (190, 120, 235)
DEAD_TEXT = (120, 120, 125)


def animation_for(skill: Optional[SkillDefinition]) -> str:
    """Какую анимацию проигрывать для навыка: по его тегам."""
    if skill is not None:
        for tag, animation in SKILL_ANIMATIONS:
            if tag in skill.tags:
                return animation
    return FALLBACK_ANIMATION


class SpriteBank:
    """Загружает и кэширует кадры анимаций классов; для неизвестного класса отдаёт заглушку."""

    def __init__(self, directory: Path = SPRITE_DIR, scale: int = SPRITE_SCALE):
        self.directory = Path(directory)
        self.scale = scale
        meta_path = self.directory / "sprites.json"
        self.meta = dict(DEFAULT_META)
        if meta_path.exists():
            self.meta.update(json.loads(meta_path.read_text(encoding="utf-8")))
        self._frames: dict[tuple[str, str], list[pygame.Surface]] = {}
        self._variants: dict[tuple[str, str, int, bool, bool], pygame.Surface] = {}

    @property
    def frame_ms(self) -> int:
        return self.meta["frame_ms"]

    @property
    def idle_ms(self) -> int:
        return self.meta["idle_ms"]

    def has_own_sprites(self, class_id: str) -> bool:
        return (self.directory / class_id / f"{IDLE}.png").exists()

    def frames(self, class_id: str, animation: str = IDLE) -> list[pygame.Surface]:
        """Кадры анимации. Нет анимации: стойка; нет класса: заглушка default."""
        key = (class_id, animation)
        if key not in self._frames:
            self._frames[key] = self._load(class_id, animation)
        return self._frames[key]

    def _load(self, class_id: str, animation: str) -> list[pygame.Surface]:
        path = self.directory / class_id / f"{animation}.png"
        if not path.exists():
            if animation != IDLE:
                return self.frames(class_id, IDLE)
            if class_id != DEFAULT_SPRITE:
                return self.frames(DEFAULT_SPRITE, IDLE)
            # Нет даже заглушки (папку спрайтов удалили): серый прямоугольник.
            blank = pygame.Surface((self.meta["frame_width"] * self.scale, self.meta["frame_height"] * self.scale),
                                   pygame.SRCALPHA)
            pygame.draw.rect(blank, (150, 152, 160), pygame.Rect(self.anchor(False) - 20, 30, 40, 90))
            return [blank]
        sheet = pygame.image.load(str(path)).convert_alpha()
        width, height = self.meta["frame_width"], self.meta["frame_height"]
        frames = []
        for i in range(max(1, sheet.get_width() // width)):
            frame = sheet.subsurface(pygame.Rect(i * width, 0, width, height))
            frames.append(pygame.transform.scale(frame, (width * self.scale, height * self.scale)))
        return frames

    def anchor(self, flipped: bool) -> int:
        """Где в кадре на экране стоят ноги юнита (по горизонтали)."""
        x = self.meta["anchor_x"] if not flipped else self.meta["frame_width"] - self.meta["anchor_x"]
        return x * self.scale

    def get(self, class_id: str, animation: str = IDLE, index: int = 0, flipped: bool = False,
            dead: bool = False) -> pygame.Surface:
        """Кадр. flipped: смотрит влево. dead: серый, полупрозрачный, лежит на боку."""
        frames = self.frames(class_id, animation)
        index %= len(frames)
        key = (class_id, animation, index, flipped, dead)
        if key not in self._variants:
            image = frames[index]
            if flipped:
                image = pygame.transform.flip(image, True, False)
            if dead:
                image = pygame.transform.rotate(pygame.transform.grayscale(image), 90 if flipped else -90)
                image.set_alpha(DEAD_ALPHA)
            self._variants[key] = image
        return self._variants[key]


def feet_position(side: str, row: int, col: int) -> tuple[int, int]:
    """Точка под ногами юнита. Передний ряд ближе к центру, колонны идут сверху вниз."""
    offset = FRONT_OFFSET + row * ROW_STEP + col * COL_SKEW
    x = CENTER_X - offset if side == "left" else CENTER_X + offset
    return x, FIRST_FEET_Y + col * COL_STEP


class ArenaScreen:
    """Вкладка боя со спрайтами. is_battle: на ней работают клавиши боя."""

    is_battle = True

    def __init__(self, bank: Optional[SpriteBank] = None):
        self.bank = bank or SpriteBank()

    def current_frame(self, view: Any, unit: Unit, now: int) -> tuple[str, int]:
        """(анимация, номер кадра) юнита в момент now.

        Пока идёт анимация последнего применённого навыка, показывается она; иначе стойка.
        """
        action = view.actions.get(unit.uid)
        if action is not None:
            skill_id, started = action
            animation = animation_for(view.db.skills.get(skill_id))
            index = (now - started) // self.bank.frame_ms
            if 0 <= index < len(self.bank.frames(unit.definition.id, animation)):
                return animation, index
        idle = self.bank.frames(unit.definition.id, IDLE)
        return IDLE, (now // self.bank.idle_ms + unit.uid) % len(idle)  # uid сдвигает фазу, чтобы не дышали хором

    def draw_battle(self, ui: UI, view: Any, autoplay: bool, now: int, popup_ms: int, popup_rise: int) -> None:
        screen, t = ui.screen, ui.t
        font, small, big = ui.fonts["main"], ui.fonts["small"], ui.fonts["big"]
        sim = view.sim

        # Фон: небо, земля и линии рядов
        pygame.draw.rect(screen, SKY, pygame.Rect(0, 52, WIDTH, HORIZON_Y - 52))
        pygame.draw.rect(screen, GROUND, pygame.Rect(0, HORIZON_Y, WIDTH, FIELD_BOTTOM - HORIZON_Y))
        for col in range(Formation.COLS):
            y = FIRST_FEET_Y + col * COL_STEP + 6
            pygame.draw.line(screen, GROUND_LINE, (0, y), (WIDTH, y))

        status = t("Round {n}   seed {seed}", n=view.round, seed=view.seed)
        if view.ended:
            winner = view.ended.winner_id
            result = t("{winner} wins", winner=t(winner)) if winner else t("draw")
            status += f"   {result.upper()}"
        status_img = font.render(status, True, YELLOW if view.ended else TEXT)
        screen.blit(status_img, status_img.get_rect(midtop=(CENTER_X, 31)))
        screen.blit(font.render(f"A: {t(sim.attacker.name)}", True, TEXT), (12, 31))
        title = font.render(f"B: {t(sim.defender.name)}", True, TEXT)
        screen.blit(title, (WIDTH - title.get_width() - 12, 31))

        # Юниты рисуются сверху вниз, чтобы ближние перекрывали дальних.
        placed: list[tuple[int, int, str, Unit]] = []
        for squad, side in ((sim.attacker, "left"), (sim.defender, "right")):
            placed.extend(self._placements(squad, side))
        anchors: dict[int, tuple[int, int]] = {}
        for x, y, side, unit in sorted(placed, key=lambda p: p[1]):
            anchors[unit.uid] = self._draw_unit(ui, view, unit, x, y, side, now)

        # Всплывающие числа урона и лечения
        shown: dict[int, int] = {}
        for popup in view.popups:
            anchor = anchors.get(popup.uid)
            if anchor is None:
                continue
            index = shown.get(popup.uid, 0)
            shown[popup.uid] = index + 1
            progress = (now - popup.born) / popup_ms
            img = big.render(popup.text, True, popup.color)
            pos = (anchor[0] - img.get_width() // 2 + index * 44, anchor[1] - round(popup_rise * progress))
            outline = big.render(popup.text, True, BG)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                screen.blit(outline, (pos[0] + dx, pos[1] + dy))
            screen.blit(img, pos)

        # Лог
        panel = pygame.Rect(8, LOG_TOP, WIDTH - 16, HEIGHT - LOG_TOP - 8)
        pygame.draw.rect(screen, PANEL, panel)
        pygame.draw.rect(screen, DIM, panel, 1)
        auto = t("on") if autoplay else t("off")
        hint = small.render(t("SPACE step   A auto [{auto}]   R restart   ESC quit", auto=auto), True, DIM)
        screen.blit(hint, (panel.right - hint.get_width() - 8, panel.y + 6))
        name = lambda uid: f"{t(sim.units[uid].name)}({uid})"
        lines = [format_event(ev, name, t).strip() for ev in view.log[-LOG_LINES:]]
        lines = lines or [t("Press SPACE to step or A to autoplay.")]
        for i, line in enumerate(lines):
            color = TEXT if i == len(lines) - 1 else DIM
            width = panel.width - 16 - (hint.get_width() + 16 if i == 0 else 0)
            screen.blit(small.render(fit(small, line, width), True, color), (panel.x + 8, panel.y + 6 + i * LOG_LINE_H))

    @staticmethod
    def _placements(squad: Squad, side: str) -> list[tuple[int, int, str, Unit]]:
        result = []
        for row in range(Formation.ROWS):
            for col in range(Formation.COLS):
                unit = squad.formation.unit_at(row, col)
                if unit is not None:
                    result.append((*feet_position(side, row, col), side, unit))
        return result

    def _draw_unit(self, ui: UI, view: Any, unit: Unit, x: int, y: int, side: str, now: int) -> tuple[int, int]:
        """Рисует юнита с ногами в точке (x, y). Возвращает точку над головой для всплывающих чисел.

        Над спрайтом снизу вверх: квадратики AP/PP, полоса HP, имя, строка эффектов.
        """
        screen, t, small = ui.screen, ui.t, ui.fonts["small"]
        alive = unit.is_alive
        flipped = side == "right"
        is_current = unit.uid == view.current_uid

        shadow = pygame.Rect(0, 0, 70, 16)
        shadow.center = (x, y + 2)
        pygame.draw.ellipse(screen, SHADOW, shadow)
        if is_current:
            pygame.draw.ellipse(screen, YELLOW, shadow.inflate(12, 6), 2)

        if alive:
            animation, index = self.current_frame(view, unit, now)
            sprite = self.bank.get(unit.definition.id, animation, index, flipped)
            feet_in_frame = sprite.get_height() - GROUND_MARGIN * self.bank.scale
            screen.blit(sprite, (x - self.bank.anchor(flipped), y + 4 - feet_in_frame))
        else:
            sprite = self.bank.get(unit.definition.id, IDLE, 0, flipped, dead=True)
            screen.blit(sprite, sprite.get_rect(center=(x, y - 26)))

        name_y = y - BODY_HEIGHT - 37
        label = small.render(fit(small, f"{t(unit.name)}({unit.uid})", 110), True, TEXT if alive else DEAD_TEXT)
        screen.blit(label, label.get_rect(midtop=(x, name_y)))
        if not alive:
            return x, name_y

        bar = pygame.Rect(x - BAR_W // 2, name_y + 16, BAR_W, 7)
        pygame.draw.rect(screen, HP_BACK, bar)
        max_hp = max(1, unit.max_hp)
        fill = bar.copy()
        fill.width = round(bar.width * unit.hp / max_hp)
        pygame.draw.rect(screen, GREEN if unit.hp * 3 > max_hp else RED, fill)
        pygame.draw.rect(screen, DIM, bar, 1)

        # AP и PP одной строкой маленьких квадратиков
        pips = [(AP_COLOR, i < unit.ap.current) for i in range(unit.ap.max)]
        pips += [(PP_COLOR, i < unit.pp.current) for i in range(unit.pp.max)]
        px = x - (len(pips) * (PIP + 2) + 4) // 2
        for i, (color, filled) in enumerate(pips):
            rect = pygame.Rect(px + i * (PIP + 2) + (4 if i >= unit.ap.max else 0), bar.bottom + 3, PIP, PIP)
            if filled:
                pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, color, rect, 1)

        top = name_y
        effects = [t(e.definition.name) + (f" x{e.stacks}" if e.stacks > 1 else "") for e in unit.effects]
        if effects:
            top = name_y - 14
            line = small.render(fit(small, ", ".join(effects), 116), True, YELLOW)
            screen.blit(line, line.get_rect(midtop=(x, top)))
        return x, top
