"""Виджеты немедленного режима: рисуются и опрашиваются одним вызовом в кадре.

Семейство виджета (theme.json -> widgets.<семейство>) — какие рамки у его состояний:
{"normal": "button", "hover": "button_hover", "selected": "button_selected", "disabled": ...,
 "text": стиль подписи, "colors": {состояние: цвет подписи}}.
Прямоугольник виджета — рамка ОБЫЧНОГО состояния; её тело — область содержимого. Остальные
состояния рисуются по тому же телу (Skin.draw(body=...)), поэтому при наведении и выборе
не сдвигаются ни линии рамки, ни подпись, ни значок.
"""
from __future__ import annotations

from typing import Any, Optional

import pygame

from uikit.gui import Gui
from uikit.layout import inset

FALLBACK_FILL = (20, 30, 58)
FALLBACK_LINE = (190, 158, 92)


def plate(gui: Gui, rect: pygame.Rect, fill=FALLBACK_FILL, line=FALLBACK_LINE) -> None:
    """Плашка кодом, когда картинки рамки нет."""
    pygame.draw.rect(gui.screen, fill, rect, border_radius=6)
    pygame.draw.rect(gui.screen, line, rect, 2, border_radius=6)


def frame(gui: Gui, kind: str, rect: pygame.Rect, body: Optional[pygame.Rect] = None) -> pygame.Rect:
    """Рамка kind в rect (или вокруг тела body). Возвращает тело — область содержимого."""
    if not gui.skin.draw(gui.screen, kind, rect, body):
        plate(gui, rect if body is None else body)
        return inset(rect if body is None else body, 6)
    return body if body is not None else gui.skin.body(kind, rect)


def state_of(hover: bool, selected: bool = False, enabled: bool = True) -> str:
    return "disabled" if not enabled else ("selected" if selected else ("hover" if hover else "normal"))


def family_frame(gui: Gui, family: str, rect: pygame.Rect, state: str) -> pygame.Rect:
    """Рамка семейства в состоянии state, выровненная по телу обычного состояния. Возвращает тело."""
    kinds = gui.widgets.get(family, {})
    base = kinds.get("normal", family)
    body = gui.skin.body(base, rect) if gui.skin.has(base) else inset(rect, 6)
    kind = kinds.get(state) or base
    if not gui.skin.draw(gui.screen, kind, rect, body):
        plate(gui, rect, FALLBACK_FILL if state != "selected" else (90, 70, 30))
    return body


def content(gui: Gui, family: str, rect: pygame.Rect) -> pygame.Rect:
    """Тело виджета семейства в rect (не рисуя)."""
    base = gui.widgets.get(family, {}).get("normal", family)
    return gui.skin.body(base, rect) if gui.skin.has(base) else inset(rect, 6)


def icon_label(gui: Gui, body: pygame.Rect, text: str, style, icon: Optional[pygame.Surface] = None,
               align: str = "center", gap: int = 10) -> None:
    """Значок и подпись одной группой, выровненной в body; подпись обрезается, значок остаётся."""
    style = gui.ts(style) if isinstance(style, str) else style
    icon_w = icon.get_width() + gap if icon is not None else 0
    style = gui.texts.shrink(text, style, body.width - icon_w)
    text = gui.texts.fit(text, style, body.width - icon_w)
    width = icon_w + gui.texts.width(text, style)
    x = body.x if align == "left" else (body.right - width if align == "right" else body.centerx - width // 2)
    if icon is not None:
        gui.screen.blit(icon, icon.get_rect(midleft=(x, body.centery)))
    gui.texts.draw(gui.screen, text, style, pygame.Rect(x + icon_w, body.y, width - icon_w + 2, body.height),
                   "left", "center", fit=False)


def button(gui: Gui, rect: pygame.Rect, text: str, icon: Optional[pygame.Surface] = None, family: str = "button",
           selected: bool = False, enabled: bool = True, style: Optional[str] = None, layer: int = 0) -> int:
    """Кнопка семейства family (button, primary, tab). Возвращает +1/-1 (левый/правый клик) или 0."""
    spec = gui.widgets.get(family, {})
    hover = enabled and gui.hovered(rect, layer)
    state = state_of(hover, selected, enabled)
    body = family_frame(gui, family, rect, state)
    color = spec.get("colors", {}).get(state, "text")
    text_style = gui.ts(style or spec.get("text", "button"), color=color)
    if spec.get("shadow") is False:
        text_style = text_style.but(shadow=None)
    if icon is not None and not enabled:
        icon = icon.copy()
        icon.set_alpha(110)
    icon_label(gui, body, text, text_style, icon)
    return gui.clicked(rect, layer) if enabled else 0


def selectable(gui: Gui, rect: pygame.Rect, family: str = "row", selected: bool = False, layer: int = 0) -> tuple[pygame.Rect, int]:
    """Строка или карточка, которую можно выбрать: (тело, клик)."""
    hover = gui.hovered(rect, layer)
    body = family_frame(gui, family, rect, state_of(hover, selected))
    return body, gui.clicked(rect, layer)


def panel(gui: Gui, rect: pygame.Rect, title: str = "", right: str = "", kind: str = "panel",
          pad: int = 18) -> pygame.Rect:
    """Панель: рамка, заголовок слева, пометка справа, линия под ними. Возвращает область под линией."""
    body = inset(frame(gui, kind, rect), pad, pad // 2 if title else pad, pad, pad)
    if not title:
        return body
    head = pygame.Rect(body.x, body.y, body.width, 48)
    right_w = gui.width(right, "label") + 12 if right else 0
    gui.label(title, pygame.Rect(head.x + 4, head.y, head.width - right_w - 8, head.height), "heading")
    if right:
        gui.label(right, head, "label", align="right")
    divider(gui, head.x, head.right, head.bottom + 2)
    return pygame.Rect(body.x, head.bottom + 12, body.width, body.bottom - head.bottom - 12)


def divider(gui: Gui, x0: int, x1: int, y: int) -> None:
    """Тонкая золотая линия с затуханием к концам, как под заголовками UO."""
    width = max(1, x1 - x0)
    line = pygame.Surface((width, 2), pygame.SRCALPHA)
    gold = gui.colors.get("gold_dim", FALLBACK_LINE)
    for x in range(width):
        fade = min(1.0, x / 40, (width - x) / 40)
        line.set_at((x, 0), (*gold, round(230 * fade)))
        line.set_at((x, 1), (0, 0, 0, round(120 * fade)))
    gui.screen.blit(line, (x0, y))


def section(gui: Gui, rect: pygame.Rect, title: str, right: str = "") -> pygame.Rect:
    """Подзаголовок с линией в верху rect. Возвращает область под ним."""
    head = pygame.Rect(rect.x, rect.y, rect.width, 40)
    gui.label(title, head, "heading")
    if right:
        gui.label(right, head, "label", align="right")
    divider(gui, rect.x, rect.right, head.bottom + 2)
    return pygame.Rect(rect.x, head.bottom + 12, rect.width, max(0, rect.bottom - head.bottom - 12))


def bar(gui: Gui, rect: pygame.Rect, value: float, maximum: float, kind: str = "hp", text: str = "",
        style: str = "bar", align: str = "center") -> pygame.Rect:
    """Полоса из конца и тела, собранная по размеру. Возвращает область заливки (подпись — в ней)."""
    share = 0.0 if maximum <= 0 else max(0.0, min(1.0, value / maximum))
    if gui.skin.draw_bar(gui.screen, kind, rect, share):
        inner = gui.skin.bar_inner(kind, rect)
    else:
        inner = rect
        pygame.draw.rect(gui.screen, (30, 20, 26), rect)
        pygame.draw.rect(gui.screen, {"exp": (110, 200, 255), "enemy": (220, 80, 70)}.get(kind, (110, 210, 120)),
                         (rect.x, rect.y, round(rect.width * share), rect.height))
        pygame.draw.rect(gui.screen, FALLBACK_LINE, rect, 1)
    if text:
        gui.label(text, inset(inner, 6, -6, 6, -6), style, align=align)
    return inner


def picture(gui: Gui, image: pygame.Surface, rect: pygame.Rect, family: str = "slot", state: str = "normal",
            line: Optional[tuple] = None, layer: int = 0) -> pygame.Rect:
    """Картинка в ячейке-рамке: картинка вписывается в тело рамки (по центру, с сохранением пропорций).
    line — цветная линия по краю тела (тир предмета)."""
    body = family_frame(gui, family, rect, state)
    w, h = image.get_size()
    k = min(body.width / max(1, w), body.height / max(1, h))
    if abs(k - 1) > 0.01:
        image = pygame.transform.smoothscale(image, (max(1, round(w * k)), max(1, round(h * k))))
    place = image.get_rect(center=body.center)
    clip = gui.screen.get_clip()
    gui.screen.set_clip(body.clip(clip) if clip else body)
    gui.screen.blit(image, place)
    gui.screen.set_clip(clip)
    if line is not None:
        pygame.draw.rect(gui.screen, line, body, 2)
    return body


def diamonds(gui: Gui, x: int, cy: int, count: int, total: int, image: Optional[pygame.Surface],
             empty: Optional[pygame.Surface] = None, color=(110, 170, 250), size: int = 20, gap: int = 2) -> int:
    """Ромбики (AP, PP): count полных из total. Возвращает правый край."""
    for i in range(total):
        rect = pygame.Rect(x + i * (size + gap), cy - size // 2, size, size)
        full = i < count
        picture_ = image if full else (empty or image)
        if picture_ is not None:
            if not full and empty is None:
                picture_ = picture_.copy()
                picture_.set_alpha(70)
            gui.screen.blit(picture_, rect)
        else:
            points = [(rect.centerx, rect.y), (rect.right, rect.centery), (rect.centerx, rect.bottom),
                      (rect.x, rect.centery)]
            if full:
                pygame.draw.polygon(gui.screen, color, points)
            pygame.draw.polygon(gui.screen, color, points, 1)
    return x + total * (size + gap)
