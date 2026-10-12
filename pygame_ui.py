"""Общие цвета, шрифты и минимальный набор виджетов для окон pygame."""
from __future__ import annotations

import pygame

from game.i18n import Translator

WIDTH, HEIGHT = 1000, 620
FONT_NAMES = ["consolas", "dejavusansmono", "liberationmono", "couriernew", "arial"]

BG = (24, 26, 32)
PANEL = (34, 37, 46)
SLOT = (40, 43, 53)
TEXT = (225, 228, 235)
DIM = (140, 145, 158)
YELLOW = (250, 210, 60)
RED = (225, 80, 80)
GREEN = (90, 200, 110)
BUTTON = (52, 57, 72)
BUTTON_HOVER = (68, 75, 96)
BUTTON_SELECTED = (60, 96, 150)
BUTTON_DISABLED = (38, 40, 48)


def load_fonts() -> dict[str, pygame.font.Font]:
    return {
        "main": pygame.font.SysFont(FONT_NAMES, 16),
        "small": pygame.font.SysFont(FONT_NAMES, 13),
        "big": pygame.font.SysFont(FONT_NAMES, 22, bold=True),
    }


def fit(font: pygame.font.Font, text: str, width: int) -> str:
    """Обрезает текст, чтобы он поместился в width пикселей."""
    if font.size(text)[0] <= width:
        return text
    while text and font.size(text + "~")[0] > width:
        text = text[:-1]
    return text + "~"


class UI:
    """Виджеты немедленного режима: рисуются и опрашиваются в одном вызове."""

    def __init__(self, screen: pygame.Surface, fonts: dict[str, pygame.font.Font], t: Translator | None = None):
        self.screen = screen
        self.fonts = fonts
        self.t = t or Translator()  # перевод строк интерфейса; виджеты получают уже готовый текст
        self.clicks: list[tuple[tuple[int, int], int]] = []
        self.wheel = 0
        self.mouse = (0, 0)

    def begin(self, events: list[pygame.event.Event]) -> None:
        """Вызывается раз в кадр до отрисовки."""
        self.clicks = [(e.pos, e.button) for e in events if e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3)]
        self.wheel = sum(e.y for e in events if e.type == pygame.MOUSEWHEEL)
        self.mouse = pygame.mouse.get_pos()

    def text(self, text: str, x: int, y: int, color=TEXT, font: str = "main", width: int | None = None) -> None:
        f = self.fonts[font]
        self.screen.blit(f.render(fit(f, text, width) if width else text, True, color), (x, y))

    def clicked(self, rect: pygame.Rect) -> int:
        """+1 левый клик по области, -1 правый, 0 нет клика."""
        for pos, button in self.clicks:
            if rect.collidepoint(pos):
                return 1 if button == 1 else -1
        return 0

    def button(self, text: str, rect: pygame.Rect, selected: bool = False, enabled: bool = True,
               font: str = "small", color=TEXT) -> int:
        """Кнопка. Возвращает +1/-1 (левый/правый клик) или 0."""
        if not enabled:
            fill = BUTTON_DISABLED
        elif selected:
            fill = BUTTON_SELECTED
        else:
            fill = BUTTON_HOVER if rect.collidepoint(self.mouse) else BUTTON
        pygame.draw.rect(self.screen, fill, rect)
        pygame.draw.rect(self.screen, YELLOW if selected else DIM, rect, 1)
        if text:
            f = self.fonts[font]
            img = f.render(fit(f, text, rect.width - 8), True, color if enabled else DIM)
            self.screen.blit(img, img.get_rect(center=rect.center))
        return self.clicked(rect) if enabled else 0
