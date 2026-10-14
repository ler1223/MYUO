"""Gui — UI из pygame_ui с темой, стилями текста, нарисованными рамками и слоями.

Слои. Всё, что рисуется сразу, лежит на слое 0 в порядке вызовов. later(слой, функция) откладывает
рисование до конца кадра: слои рисуются по возрастанию (плашки над фигурами, перетаскиваемое
поверх всего), после них подсказка и открытый список (pygame_ui.UI.end).

Перекрытие мыши. block(rect, слой) объявляет, что в этом кадре область занята слоем; в следующем
кадре наведение и клики виджетов нижних слоев в этой области не срабатывают (окно поверх поля
боя, итог боя). Виджет сообщает свой слой параметром layer (по умолчанию 0).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

import pygame

from pygame_ui import UI
from uikit.skin import Images, Skin
from uikit.text import Fonts, Text, TextStyle

ROOT = Path(__file__).resolve().parent.parent
THEME_PATH = ROOT / "assets" / "ui" / "theme.json"


class Gui(UI):
    def __init__(self, screen: pygame.Surface, theme: dict, folder: Path, assets: Path):
        self.theme = theme
        self.colors = {name: tuple(value) for name, value in theme.get("colors", {}).items()}
        fonts = Fonts({face: assets / path for face, path in theme.get("fonts", {}).items()})
        self.texts = Text(fonts)
        self.styles: dict[str, TextStyle] = {name: self._style(spec) for name, spec in theme.get("text", {}).items()}
        legacy = {key: self.texts.font(self.styles[name]) for key, name in theme.get("legacy", {}).items()
                  if name in self.styles}
        super().__init__(screen, legacy)
        self.skin = Skin(Images(folder), theme.get("frames", {}), theme.get("bars", {}))
        self.widgets: dict[str, dict] = theme.get("widgets", {})
        self.frames = lambda target, kind, rect: self.skin.draw(target, kind, rect)
        self._layers: dict[int, list[Callable[[], None]]] = {}
        self._blocks: list[tuple[pygame.Rect, int]] = []
        self._blocked: list[tuple[pygame.Rect, int]] = []        # прошлый кадр — по нему решается наведение

    def _color(self, value: Any):
        if value is None or isinstance(value, bool):
            return None
        return self.colors[value] if isinstance(value, str) else tuple(value)

    def _style(self, spec: dict) -> TextStyle:
        base = TextStyle()
        return TextStyle(face=spec.get("face", base.face), size=int(spec.get("size", base.size)),
                         color=self._color(spec.get("color", "text")) or base.color,
                         shadow=self._color(spec.get("shadow", "shadow")) if spec.get("shadow", True) else None,
                         outline=self._color(spec.get("outline")))

    # --- текст ---

    def ts(self, name: str, **changes) -> TextStyle:
        """Стиль темы по имени; changes — поправки (color может быть именем цвета темы)."""
        style = self.styles[name]
        if isinstance(changes.get("color"), str):
            changes["color"] = self.colors[changes["color"]]
        return style.but(**changes) if changes else style

    def label(self, text: str, rect: pygame.Rect, style: Any = "body", align: str = "left", valign: str = "center",
              color: Any = None) -> pygame.Rect:
        """Строка в прямоугольнике (обрезается с «…»). style — имя стиля темы или TextStyle."""
        style = self.ts(style) if isinstance(style, str) else style
        if color is not None:
            style = style.but(color=self.colors[color] if isinstance(color, str) else tuple(color))
        return self.texts.draw(self.screen, text, style, rect, align, valign)

    def paragraph(self, text: str, rect: pygame.Rect, style: Any = "paragraph", color: Any = None,
                  max_lines: Optional[int] = None) -> int:
        style = self.ts(style) if isinstance(style, str) else style
        if color is not None:
            style = style.but(color=self.colors[color] if isinstance(color, str) else tuple(color))
        return self.texts.paragraph(self.screen, text, style, rect, max_lines)

    def width(self, text: str, style: Any = "body") -> int:
        return self.texts.width(text, self.ts(style) if isinstance(style, str) else style)

    # --- слои и мышь ---

    def later(self, layer: int, draw: Callable[[], None]) -> None:
        self._layers.setdefault(layer, []).append(draw)

    def block(self, rect: pygame.Rect, layer: int) -> None:
        self._blocks.append((pygame.Rect(rect), layer))

    def begin(self, events: list[pygame.event.Event]) -> None:
        self._blocked, self._blocks = self._blocks, []
        self._layers = {}
        super().begin(events)

    def covered(self, pos: tuple[int, int], layer: int = 0) -> bool:
        return any(layer < above and rect.collidepoint(pos) for rect, above in self._blocked)

    def hovered(self, rect: pygame.Rect, layer: int = 0) -> bool:
        return super().hovered(rect) and not self.covered(self.mouse, layer)

    def clicked(self, rect: pygame.Rect, layer: int = 0) -> int:
        for pos, button in self.clicks:
            if rect.collidepoint(pos) and not self.covered(pos, layer):
                return 1 if button == 1 else -1
        return 0

    def end(self) -> None:
        for layer in sorted(self._layers):
            for draw in self._layers[layer]:
                draw()
        self._layers = {}
        super().end()


def load_gui(screen: pygame.Surface, theme_path: Path = THEME_PATH) -> Gui:
    theme = json.loads(Path(theme_path).read_text(encoding="utf-8"))
    folder = Path(theme_path).parent
    return Gui(screen, theme, folder, folder.parent)
