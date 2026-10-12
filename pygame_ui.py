"""Общие цвета, шрифты и минимальный набор виджетов для окон pygame.

Виджеты немедленного режима: рисуются и опрашиваются одним вызовом в каждом кадре.
Виджеты с состоянием (поле ввода, выпадающий список) различаются по ключу key:
любое хешируемое значение, уникальное для виджета и редактируемого объекта.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Hashable, Optional, Sequence

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
POPUP_BG = (30, 33, 42)

POPUP_ROW_H = 22
POPUP_ROWS = 10
POPUP_MIN_W = 200
POPUP_MAX_W = 380

Option = tuple[Any, str]  # (значение, подпись)


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


def format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


@dataclass
class Popup:
    """Открытый выпадающий список."""

    key: Hashable
    anchor: pygame.Rect
    options: list[Option]
    multi: bool = False
    chosen: list[Any] = field(default_factory=list)  # для множественного выбора
    search: str = ""
    scroll: int = 0

    def filtered(self) -> list[Option]:
        needle = self.search.casefold()
        return [o for o in self.options if needle in o[1].casefold()]


class UI:
    def __init__(self, screen: pygame.Surface, fonts: dict[str, pygame.font.Font], t: Translator | None = None):
        self.screen = screen
        self.fonts = fonts
        self.t = t or Translator()  # перевод строк интерфейса; виджеты получают уже готовый текст
        self.clicks: list[tuple[tuple[int, int], int]] = []
        self.wheel = 0
        self.mouse = (0, 0)
        self.captured = False  # клавиатура занята полем ввода или списком: горячие клавиши не работают
        # поле ввода
        self.focus: Optional[Hashable] = None
        self.buffer = ""
        self._committed: Optional[tuple[Hashable, str]] = None
        # выпадающий список
        self.popup: Optional[Popup] = None
        self._popup_clicks: list[tuple[tuple[int, int], int]] = []
        self.popup_box: Optional[pygame.Rect] = None  # где список нарисован в последний раз
        self._picked: Optional[tuple[Hashable, Any]] = None       # доставляется виджету в этом кадре
        self._picked_next: Optional[tuple[Hashable, Any]] = None  # выбрано в конце прошлого кадра
        self.scrolls: dict[Hashable, int] = {}

    # --- кадр ---

    def begin(self, events: list[pygame.event.Event]) -> None:
        """Вызывается раз в кадр до отрисовки."""
        self.captured = self.focus is not None or self.popup is not None
        self._committed = None
        self._picked, self._picked_next = self._picked_next, None
        self.clicks = [(e.pos, e.button) for e in events if e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3)]
        self.wheel = sum(e.y for e in events if e.type == pygame.MOUSEWHEEL)
        self.mouse = pygame.mouse.get_pos()
        keys = [e for e in events if e.type == pygame.KEYDOWN]

        if self.popup is not None:
            # Список модальный: клики и колесо достаются только ему.
            self._popup_clicks, self.clicks = self.clicks, []
            self.popup.scroll = max(0, self.popup.scroll - self.wheel)
            self.wheel = 0
            for e in keys:
                self._popup_key(e)
        elif self.focus is not None:
            for e in keys:
                self._input_key(e)
            if self.clicks and self.focus is not None:
                self._commit()  # клик мимо поля завершает ввод

    def end(self) -> None:
        """Вызывается после отрисовки кадра: рисует открытый список поверх всего."""
        if self.popup is not None:
            self._draw_popup(self.popup)
        self._popup_clicks = []

    def _commit(self) -> None:
        self._committed = (self.focus, self.buffer)
        self.focus = None

    def _input_key(self, event: pygame.event.Event) -> None:
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
            self._commit()
        elif event.key == pygame.K_ESCAPE:
            self.focus = None
        elif event.key == pygame.K_BACKSPACE:
            self.buffer = self.buffer[:-1]
        elif event.unicode and event.unicode.isprintable():
            self.buffer += event.unicode

    def _popup_key(self, event: pygame.event.Event) -> None:
        popup = self.popup
        if event.key == pygame.K_ESCAPE:
            self.popup = None
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            found = popup.filtered()
            if found and not popup.multi:
                self._picked_next = (popup.key, found[0][0])
            self.popup = None
        elif event.key == pygame.K_BACKSPACE:
            popup.search, popup.scroll = popup.search[:-1], 0
        elif event.unicode and event.unicode.isprintable():
            popup.search, popup.scroll = popup.search + event.unicode, 0

    # --- простые виджеты ---

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
            fill = BUTTON_HOVER if rect.collidepoint(self.mouse) and self.popup is None else BUTTON
        pygame.draw.rect(self.screen, fill, rect)
        pygame.draw.rect(self.screen, YELLOW if selected else DIM, rect, 1)
        if text:
            f = self.fonts[font]
            img = f.render(fit(f, text, rect.width - 8), True, color if enabled else DIM)
            self.screen.blit(img, img.get_rect(center=rect.center))
        return self.clicked(rect) if enabled else 0

    def scroll(self, key: Hashable, area: pygame.Rect, total: int, visible: int) -> int:
        """Смещение прокрутки списка: колесо работает, пока курсор над area."""
        offset = self.scrolls.get(key, 0)
        if area.collidepoint(self.mouse):
            offset -= self.wheel
        offset = max(0, min(offset, total - visible))
        self.scrolls[key] = offset
        return offset

    # --- поля ввода ---

    def text_input(self, key: Hashable, rect: pygame.Rect, value: str, max_len: int = 24,
                   font: str = "small") -> Optional[str]:
        """Поле ввода текста. Возвращает новый текст после Enter, Tab или клика мимо, иначе None."""
        focused = self.focus == key
        if focused:
            self.buffer = self.buffer[:max_len]
        pygame.draw.rect(self.screen, SLOT, rect)
        pygame.draw.rect(self.screen, YELLOW if focused else DIM, rect, 1)
        f = self.fonts[font]
        shown = (self.buffer + "_") if focused else value
        img = f.render(fit(f, shown, rect.width - 8), True, TEXT)
        self.screen.blit(img, (rect.x + 5, rect.y + (rect.height - img.get_height()) // 2))
        if self.clicked(rect) and not focused:
            self.focus, self.buffer = key, value
        if self._committed is not None and self._committed[0] == key:
            text, self._committed = self._committed[1].strip(), None
            return text if text != value else None
        return None

    def number_input(self, key: Hashable, rect: pygame.Rect, value: float, low: float = 0, high: float = 9999,
                     integer: bool = True) -> Optional[float]:
        """Поле ввода числа. Нечисловой ввод отбрасывается, значение обрезается до [low, high]."""
        text = self.text_input(key, rect, format_number(value), max_len=7)
        if text is None:
            return None
        try:
            number = float(text.replace(",", "."))
        except ValueError:
            return None
        number = max(low, min(high, round(number) if integer else round(number, 2)))
        return (int(number) if integer else number) if number != value else None

    # --- выпадающие списки ---

    def dropdown(self, key: Hashable, rect: pygame.Rect, options: Sequence[Option], current: Any,
                 color=TEXT) -> Any:
        """Выбор одного значения из списка с поиском. Возвращает выбранное значение или None.

        Чтобы предложить «пусто», добавьте вариант со своим значением-маркером (не None).
        """
        label = next((text for value, text in options if value == current), str(current))
        if self.button(label, rect, selected=self._is_open(key), color=color):
            self.popup = Popup(key, rect, list(options))
        return self._take_pick(key)

    def multiselect(self, key: Hashable, rect: pygame.Rect, options: Sequence[Option],
                    chosen: Sequence[Any]) -> Optional[list[Any]]:
        """Выбор нескольких значений. Возвращает новый список после каждого переключения, иначе None."""
        labels = [text for value, text in options if value in chosen]
        if self.button(", ".join(labels) or "-", rect, selected=self._is_open(key)):
            self.popup = Popup(key, rect, list(options), multi=True, chosen=list(chosen))
        return self._take_pick(key)

    def _is_open(self, key: Hashable) -> bool:
        return self.popup is not None and self.popup.key == key

    def _take_pick(self, key: Hashable) -> Any:
        if self._picked is not None and self._picked[0] == key:
            value, self._picked = self._picked[1], None
            return value
        return None

    def _draw_popup(self, popup: Popup) -> None:
        font = self.fonts["small"]
        found = popup.filtered()
        longest = max((font.size(text)[0] for _, text in popup.options), default=0)
        width = max(POPUP_MIN_W, min(POPUP_MAX_W, max(popup.anchor.width, longest + 44)))
        rows = min(POPUP_ROWS, max(1, len(found)))
        height = 26 + rows * POPUP_ROW_H + 4
        x = min(popup.anchor.x, WIDTH - width - 4)
        y = popup.anchor.bottom + 2
        if y + height > HEIGHT - 4:
            y = max(4, popup.anchor.y - height - 2)
        box = pygame.Rect(x, y, width, height)
        self.popup_box = box
        pygame.draw.rect(self.screen, POPUP_BG, box)
        pygame.draw.rect(self.screen, YELLOW, box, 1)

        prompt = self.t("search") + ": " + popup.search + "_"
        self.screen.blit(font.render(fit(font, prompt, width - 12), True, YELLOW), (x + 6, y + 5))
        popup.scroll = max(0, min(popup.scroll, len(found) - rows))
        if not found:
            self.screen.blit(font.render(self.t("nothing found"), True, DIM), (x + 6, y + 30))

        picked = None
        for row, (value, text) in enumerate(found[popup.scroll:popup.scroll + rows]):
            rect = pygame.Rect(x + 2, y + 26 + row * POPUP_ROW_H, width - 4, POPUP_ROW_H)
            marked = popup.multi and value in popup.chosen
            if rect.collidepoint(self.mouse):
                pygame.draw.rect(self.screen, BUTTON_HOVER, rect)
            prefix = ("[x] " if marked else "[ ] ") if popup.multi else ""
            img = font.render(fit(font, prefix + text, rect.width - 10), True, YELLOW if marked else TEXT)
            self.screen.blit(img, (rect.x + 5, rect.y + 3))
            if any(rect.collidepoint(pos) for pos, _ in self._popup_clicks):
                picked = (value,)
        if len(found) > rows:
            more = font.render(f"{popup.scroll + 1}-{popup.scroll + rows}/{len(found)}", True, DIM)
            self.screen.blit(more, (box.right - more.get_width() - 6, y + 5))

        if picked is not None:
            value = picked[0]
            if popup.multi:
                if value in popup.chosen:
                    popup.chosen.remove(value)
                else:
                    popup.chosen.append(value)
                order = [v for v, _ in popup.options]
                self._picked_next = (popup.key, sorted(popup.chosen, key=order.index))
            else:
                self._picked_next = (popup.key, value)
                self.popup = None
        elif self._popup_clicks and not any(box.collidepoint(pos) for pos, _ in self._popup_clicks):
            self.popup = None  # клик мимо списка закрывает его
