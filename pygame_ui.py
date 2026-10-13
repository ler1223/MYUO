"""Общие цвета, шрифты и минимальный набор виджетов для окон pygame.

Виджеты немедленного режима: рисуются и опрашиваются одним вызовом в каждом кадре.
Виджеты с состоянием (поле ввода, выпадающий список) различаются по ключу key:
любое хешируемое значение, уникальное для виджета и редактируемого объекта.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Hashable, Optional, Sequence

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

TIP_BG = (16, 18, 26)
TIP_BORDER = (200, 170, 90)
TIP_W = 330           # ширина подсказки при базовом масштабе

Option = tuple[Any, str]  # (значение, подпись)
TipLine = tuple[str, Any, str]  # строка подсказки: (текст, цвет, шрифт); пустой текст — отступ


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


def wrap(font: pygame.font.Font, text: str, width: int) -> list[str]:
    """Разбивает текст на строки не шире width пикселей (по словам; длинное слово обрезается)."""
    lines, line = [], ""
    for word in text.split(" "):
        candidate = f"{line} {word}" if line else word
        if font.size(candidate)[0] <= width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return [fit(font, part, width) for part in lines]


def lighter(color, amount: int):
    """Цвет светлее на amount (отрицательное — темнее)."""
    return tuple(max(0, min(255, c + amount)) for c in color[:3])


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
        """Варианты, содержащие поисковую строку: сначала точное совпадение, затем начало названия."""
        needle = self.search.casefold()
        found = [o for o in self.options if needle in o[1].casefold()]
        if not needle:
            return found
        rank = lambda o: (o[1].casefold() != needle, not o[1].casefold().startswith(needle))
        return sorted(found, key=rank)


class UI:
    def __init__(self, screen: pygame.Surface, fonts: dict[str, pygame.font.Font], t: Translator | None = None):
        self.screen = screen
        self.fonts = fonts
        self.t = t or Translator()  # перевод строк интерфейса; виджеты получают уже готовый текст
        self.clicks: list[tuple[tuple[int, int], int]] = []
        self.wheel = 0
        self.mouse = (0, 0)
        self.transform = lambda pos: pos   # окно -> логические координаты (окно может быть больше)
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
        self.scale = 1.0     # во сколько раз интерфейс крупнее базового 1000x620 (размеры списков, подсказок)
        self.releases: list[tuple[tuple[int, int], int]] = []
        # оформление кнопок и списков; окно башни задаёт своё (тёмно-синее с золотом)
        # нарисованные рамки: frames(экран, вид, прямоугольник) -> True, если рамка нарисована картинкой
        self.frames: Optional[Callable[[pygame.Surface, str, pygame.Rect], bool]] = None
        self.style = dict(button=BUTTON, hover=BUTTON_HOVER, selected=BUTTON_SELECTED, disabled=BUTTON_DISABLED,
                          border=DIM, accent=YELLOW, radius=3)
        # подсказка под курсором: строки (текст, цвет, шрифт) и картинка; рисуется поверх всего в end()
        self._tip: Optional[tuple[list[TipLine], Optional[pygame.Surface]]] = None
        self.tip_box: Optional[pygame.Rect] = None    # где подсказка нарисована в этом кадре

    # --- кадр ---

    def begin(self, events: list[pygame.event.Event]) -> None:
        """Вызывается раз в кадр до отрисовки."""
        self.captured = self.focus is not None or self.popup is not None
        self._committed = None
        self._tip, self.tip_box = None, None
        self._picked, self._picked_next = self._picked_next, None
        self.clicks = [(e.pos, e.button) for e in events if e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3)]
        # отпускания кнопки мыши: конец перетаскивания (окно само решает, что куда перетащили)
        self.releases = [(e.pos, e.button) for e in events if e.type == pygame.MOUSEBUTTONUP and e.button in (1, 3)]
        self.wheel = sum(e.y for e in events if e.type == pygame.MOUSEWHEEL)
        self.mouse = self.transform(pygame.mouse.get_pos())
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
        """Вызывается после отрисовки кадра: рисует подсказку и открытый список поверх всего."""
        if self.popup is not None:
            self._draw_popup(self.popup)
        elif self._tip is not None:
            self._draw_tip(*self._tip)
        self._popup_clicks = []

    # --- подсказки ---

    def hovered(self, rect: pygame.Rect) -> bool:
        return self.popup is None and rect.collidepoint(self.mouse)

    def tip(self, rect: pygame.Rect, lines: Callable[[], list[TipLine]],
            image: Optional[Callable[[], Optional[pygame.Surface]]] = None) -> bool:
        """Подсказка, пока курсор над rect. lines и image вызываются только при наведении."""
        if not self.hovered(rect):
            return False
        self._tip = (lines(), image() if image else None)
        return True

    def _draw_tip(self, lines: list[TipLine], image: Optional[pygame.Surface]) -> None:
        k = self.scale
        pad, max_w = round(10 * k), round(TIP_W * k)
        rows: list[tuple[pygame.Surface, int]] = []     # (строка, отступ сверху)
        for text, color, font_name in lines:
            font = self.fonts.get(font_name, self.fonts["small"])
            if not text:
                rows.append((pygame.Surface((1, max(2, font.get_height() // 3)), pygame.SRCALPHA), 0))
                continue
            for part in wrap(font, text, max_w - 2 * pad - (image.get_width() + pad if image else 0)):
                rows.append((font.render(part, True, color), 0))
        text_w = max((img.get_width() for img, _ in rows), default=0)
        text_h = sum(img.get_height() + 2 for img, _ in rows)
        img_w = image.get_width() + pad if image else 0
        width = text_w + img_w + 2 * pad
        height = max(text_h, image.get_height() if image else 0) + 2 * pad
        screen_w, screen_h = self.screen.get_size()
        x, y = self.mouse[0] + round(18 * k), self.mouse[1] + round(18 * k)
        if x + width > screen_w - 4:
            x = max(4, self.mouse[0] - width - round(12 * k))
        if y + height > screen_h - 4:
            y = max(4, screen_h - height - 4)
        box = pygame.Rect(x, y, width, height)
        self.tip_box = box
        if self.frames is None or not self.frames(self.screen, "tooltip", box):
            shade = pygame.Surface(box.size, pygame.SRCALPHA)
            shade.fill((*TIP_BG, 240))
            self.screen.blit(shade, box.topleft)
            pygame.draw.rect(self.screen, TIP_BORDER, box, max(1, round(k)))
        if image is not None:
            self.screen.blit(image, (x + pad, y + pad))
        cy = y + pad
        for img, _ in rows:
            self.screen.blit(img, (x + pad + img_w, cy))
            cy += img.get_height() + 2

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
               font: str = "small", color=TEXT, fill=None) -> int:
        """Кнопка. Возвращает +1/-1 (левый/правый клик) или 0. fill — свой цвет кнопки."""
        hover = rect.collidepoint(self.mouse) and self.popup is None
        style = self.style
        if not enabled:
            back = style["disabled"]
        elif selected:
            back = style["selected"]
        elif fill is not None:
            back = lighter(fill, 28) if hover else fill
        else:
            back = style["hover"] if hover else style["button"]
        radius = round(style["radius"] * self.scale)
        pygame.draw.rect(self.screen, back, rect, border_radius=radius)
        border = style["accent"] if selected or (hover and enabled) else             (lighter(fill, 60) if fill is not None and enabled else style["border"])
        pygame.draw.rect(self.screen, border, rect, max(1, round(self.scale)), border_radius=radius)
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
        k = self.scale
        row_h = max(POPUP_ROW_H, font.get_height() + 6)
        head = row_h + 4
        screen_w, screen_h = self.screen.get_size()
        longest = max((font.size(text)[0] for _, text in popup.options), default=0)
        width = max(round(POPUP_MIN_W * k), min(round(POPUP_MAX_W * k), max(popup.anchor.width, longest + 44)))
        rows = min(POPUP_ROWS, max(1, len(found)))
        height = head + rows * row_h + 4
        x = min(popup.anchor.x, screen_w - width - 4)
        y = popup.anchor.bottom + 2
        if y + height > screen_h - 4:
            y = max(4, popup.anchor.y - height - 2)
        box = pygame.Rect(x, y, width, height)
        self.popup_box = box
        if self.frames is None or not self.frames(self.screen, "inset", box):
            pygame.draw.rect(self.screen, POPUP_BG, box)
            pygame.draw.rect(self.screen, YELLOW, box, 1)

        prompt = self.t("search") + ": " + popup.search + "_"
        self.screen.blit(font.render(fit(font, prompt, width - 12), True, YELLOW), (x + 6, y + 5))
        popup.scroll = max(0, min(popup.scroll, len(found) - rows))
        if not found:
            self.screen.blit(font.render(self.t("nothing found"), True, DIM), (x + 6, y + head + 4))

        picked = None
        for row, (value, text) in enumerate(found[popup.scroll:popup.scroll + rows]):
            rect = pygame.Rect(x + 2, y + head + row * row_h, width - 4, row_h)
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


RESOLUTIONS = ((1000, 620), (1280, 794), (1440, 893), (1600, 992), (1920, 1190), (2560, 1587))


class Window:
    """Окно любого размера: интерфейс рисуется в логическом размере (logical, по умолчанию
    WIDTH x HEIGHT) и масштабируется с сохранением пропорций; поле боя рисуется прямо в окно, чётко.

    sizes: размеры окна, которые перебирает F12 (берутся только помещающиеся на экран).
    """

    def __init__(self, size: tuple[int, int], logical: tuple[int, int] = (WIDTH, HEIGHT),
                 sizes: Sequence[tuple[int, int]] = RESOLUTIONS):
        self.logical = logical
        self.sizes = tuple(sizes)
        self.canvas = pygame.Surface(logical)
        self.resize(size)

    def resize(self, size: tuple[int, int]) -> None:
        self.surface = pygame.display.set_mode(size, pygame.RESIZABLE)
        w, h = self.surface.get_size()
        lw, lh = self.logical
        self.scale = min(w / lw, h / lh)
        self.offset = ((w - lw * self.scale) / 2, (h - lh * self.scale) / 2)

    def to_logical(self, pos: tuple[int, int]) -> tuple[int, int]:
        return (int((pos[0] - self.offset[0]) / self.scale), int((pos[1] - self.offset[1]) / self.scale))

    def logical_event(self, event: pygame.event.Event) -> pygame.event.Event:
        """Событие мыши с координатами в логических пикселях интерфейса."""
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            data = dict(event.dict, pos=self.to_logical(event.pos))
            return pygame.event.Event(event.type, data)
        return event

    def present(self, area: Optional[pygame.Rect] = None) -> None:
        """Интерфейс в окно: масштаб с сохранением пропорций, по краям чёрные поля.

        area: только эта часть интерфейса (логические пиксели) — например, открытый список поверх поля.
        """
        if area is None:
            self.surface.fill((0, 0, 0))
            area = self.canvas.get_rect()
        area = area.clip(self.canvas.get_rect())
        size = (round(area.width * self.scale), round(area.height * self.scale))
        part = self.canvas.subsurface(area)
        image = part if size == part.get_size() else pygame.transform.smoothscale(part, size)
        self.surface.blit(image, (round(self.offset[0] + area.x * self.scale), round(self.offset[1] + area.y * self.scale)))

    def next_size(self) -> None:
        """Следующий размер окна из помещающихся на экран (F12)."""
        presets = Window.presets(self.sizes)
        current = self.surface.get_size()
        bigger = [r for r in presets if r[0] > current[0]]
        self.resize(bigger[0] if bigger else presets[0])

    @staticmethod
    def presets(sizes: Sequence[tuple[int, int]] = RESOLUTIONS) -> list[tuple[int, int]]:
        """Размеры окна, которые помещаются на экран."""
        desktop = pygame.display.get_desktop_sizes()[0] if pygame.display.get_init() else (10 ** 5, 10 ** 5)
        fitting = [r for r in sizes if r[0] <= desktop[0] and r[1] <= desktop[1] - 60]
        return fitting or [sizes[0]]
