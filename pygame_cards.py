"""Карты юнитов: арт класса в рамке стиля, повёрнутые к противнику.

Раскладка карты (как у карточных игр):
- слева вверху самоцвет с уровнем, справа вверху эмблема стиля рамки;
- арт класса; под ним лента с названием класса и строка тегов;
- поле с активными эффектами;
- внизу AP (синий самоцвет слева), PP (фиолетовый справа) и полоса HP с числами.

Стиль рамки выбирается по тегам класса (assets/cards/frames.json). Любую часть можно
заменить картинкой: assets/cards/<класс>.png — арт, assets/cards/frames/<стиль>.png —
рамка поверх арта (окно арта в ней прозрачное). Без картинок всё рисуется кодом.

Поворот к противнику — «псевдо-3D»: карта сжата по ширине, ближний к нам край выше,
дальний ниже. Повёрнутые карты кэшируются и перерисовываются, только когда меняется
что-то на карте (HP, AP, PP, эффекты).
"""
from __future__ import annotations

import json
import math
from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

import pygame

from pygame_ui import FONT_NAMES

ROOT = Path(__file__).resolve().parent
CARD_DIR = ROOT / "assets" / "cards"
SPRITE_DIR = ROOT / "assets" / "sprites"
TILT_DEGREES = 24           # насколько карта повёрнута к противнику
PERSPECTIVE = 0.22          # насколько дальний край карты ниже ближнего
CACHE_LIMIT = 400           # сколько повёрнутых карт держать в памяти
BASE_HEIGHT = 140           # размеры частей карты заданы для карты этой высоты

# Раскладка нарисованной кодом рамки в долях карты: прямоугольники [лево, верх, право, низ],
# самоцветы и эмблема [центр x, центр y, радиус в долях ширины]. Для картинок рамок
# раскладка задаётся в frames.json (image_layout).
CODE_LAYOUT = {
    "art": [0.07, 0.05, 0.93, 0.62], "banner": [0.02, 0.56, 0.98, 0.67], "text": [0.09, 0.68, 0.91, 0.85],
    "hp": [0.25, 0.87, 0.75, 0.94], "level": [0.149, 0.107, 0.129], "emblem": [0.861, 0.1, 0.099],
    "ap": [0.149, 0.893, 0.119], "pp": [0.851, 0.893, 0.119],
}

CARD_BACK = (24, 26, 36)
TEXT_LIGHT = (246, 240, 222)
AP_GEM = (70, 140, 250)
PP_GEM = (180, 100, 240)
HP_FULL = (90, 210, 110)
HP_LOW = (230, 80, 70)
HP_BACK = (50, 26, 30)


@lru_cache(maxsize=None)
def card_font(size: int, bold: bool = True) -> pygame.font.Font:
    return pygame.font.SysFont(FONT_NAMES, max(6, size), bold=bold)


@dataclass(frozen=True)
class FrameStyle:
    name: str
    light: tuple[int, int, int]
    dark: tuple[int, int, int]
    gem: tuple[int, int, int]
    emblem: str


@dataclass(frozen=True)
class CardFace:
    """Всё, что видно на карте. По этому ключу карты кэшируются."""

    class_id: str
    title: str                  # название класса (переведённое)
    subtitle: str               # теги класса строкой
    level: int
    style: str
    ap: int
    ap_max: int
    pp: int
    pp_max: int
    hp: int
    max_hp: int
    effects: tuple[str, ...] = ()
    dead: bool = False


def load_frames_config(card_dir: Path = CARD_DIR) -> dict:
    path = Path(card_dir) / "frames.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_styles(card_dir: Path = CARD_DIR) -> tuple[dict[str, FrameStyle], list[str], str, dict[str, tuple]]:
    data = load_frames_config(card_dir)
    styles = {name: FrameStyle(name, tuple(s["light"]), tuple(s["dark"]), tuple(s["gem"]), s.get("emblem", "sword"))
              for name, s in data.get("styles", {}).items()}
    if not styles:
        styles = {"infantry": FrameStyle("infantry", (200, 204, 214), (62, 66, 78), (210, 214, 226), "sword")}
    sides = {side: tuple(color) for side, color in data.get("sides", {}).items()}
    return styles, list(data.get("order", styles)), data.get("default", next(iter(styles))), sides


def _fallback_art(class_id: str) -> Optional[pygame.Surface]:
    """Первый кадр стойки из спрайтов класса (или заглушки default), без прозрачных полей."""
    meta_path = SPRITE_DIR / "sprites.json"
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    for name in (class_id, "default"):
        path = SPRITE_DIR / name / "idle.png"
        if not path.exists():
            continue
        own = SPRITE_DIR / name / "sprite.json"
        if own.exists():
            meta = {**meta, **json.loads(own.read_text(encoding="utf-8"))}
        sheet = pygame.image.load(str(path)).convert_alpha()
        frame = sheet.subsurface(pygame.Rect(0, 0, meta["frame_width"], meta["frame_height"])).copy()
        return frame.subsurface(frame.get_bounding_rect()).copy()
    return None


def shade(color: tuple[int, int, int], k: float) -> tuple[int, int, int]:
    """Светлее (k > 1) или темнее (k < 1)."""
    return tuple(max(0, min(255, int(c * k))) for c in color)


def draw_text(surface: pygame.Surface, text: str, size: int, color, center: tuple[int, int],
              max_width: Optional[int] = None, outline: bool = True, bold: bool = True) -> None:
    font = card_font(size, bold)
    img = font.render(text, True, color)
    if max_width and img.get_width() > max_width:
        img = pygame.transform.smoothscale(img, (max_width, img.get_height()))
    rect = img.get_rect(center=center)
    if outline:
        dark = font.render(text, True, (10, 10, 14))
        if max_width and dark.get_width() > max_width:
            dark = pygame.transform.smoothscale(dark, (max_width, dark.get_height()))
        o = max(1, size // 12)
        for dx, dy in ((-o, 0), (o, 0), (0, -o), (0, o)):
            surface.blit(dark, rect.move(dx, dy))
    surface.blit(img, rect)


def draw_gem(surface: pygame.Surface, center: tuple[int, int], radius: int, color, text: str,
             border, diamond: bool = False, dim: bool = False) -> None:
    """Самоцвет с числом: круглый (AP, PP) или ромб (уровень)."""
    cx, cy = center
    base = shade(color, 0.45 if dim else 1.0)
    if diamond:
        pts = [(cx, cy - radius), (cx + radius, cy), (cx, cy + radius), (cx - radius, cy)]
        pygame.draw.polygon(surface, shade(border, 0.5), [(x + (1 if x > cx else -1 if x < cx else 0), y) for x, y in pts])
        pygame.draw.polygon(surface, base, pts)
        inner = [(cx, cy - radius * 0.6), (cx + radius * 0.6, cy), (cx, cy + radius * 0.6), (cx - radius * 0.6, cy)]
        pygame.draw.polygon(surface, shade(base, 1.35), inner)
        pygame.draw.polygon(surface, border, pts, max(1, radius // 7))
    else:
        pygame.draw.circle(surface, shade(border, 0.5), center, radius + max(1, radius // 7))
        for r in range(radius, 0, -1):                 # объём: светлее к центру
            k = 0.7 + 0.6 * (1 - r / radius)
            pygame.draw.circle(surface, shade(base, k), (cx - (radius - r) // 4, cy - (radius - r) // 4), r)
        pygame.draw.circle(surface, border, center, radius, max(1, radius // 7))
    draw_text(surface, text, int(radius * 1.25), TEXT_LIGHT if not dim else (170, 170, 170), center)


def draw_emblem(surface: pygame.Surface, center: tuple[int, int], radius: int, style: FrameStyle) -> None:
    """Эмблема стиля в круге: меч, щит, конь, звезда, лук, крыло."""
    cx, cy = center
    pygame.draw.circle(surface, shade(style.dark, 0.8), center, radius)
    pygame.draw.circle(surface, style.light, center, radius, max(1, radius // 6))
    r = radius * 0.62
    c = style.light
    w = max(1, int(radius / 6))
    if style.emblem == "shield":
        pts = [(cx - r * 0.8, cy - r * 0.7), (cx + r * 0.8, cy - r * 0.7), (cx + r * 0.7, cy + r * 0.1), (cx, cy + r),
               (cx - r * 0.7, cy + r * 0.1)]
        pygame.draw.polygon(surface, c, pts)
        pygame.draw.line(surface, shade(style.dark, 0.8), (cx, cy - r * 0.55), (cx, cy + r * 0.7), w)
    elif style.emblem == "horse":
        pts = [(cx - r * 0.2, cy - r), (cx + r * 0.6, cy - r * 0.35), (cx + r * 0.75, cy), (cx + r * 0.2, cy - r * 0.05),
               (cx + r * 0.1, cy + r), (cx - r * 0.6, cy + r), (cx - r * 0.45, cy - r * 0.3)]
        pygame.draw.polygon(surface, c, pts)
    elif style.emblem == "star":
        pts = [(cx + math.cos(a) * (r if i % 2 == 0 else r * 0.42), cy + math.sin(a) * (r if i % 2 == 0 else r * 0.42))
               for i, a in enumerate(i * math.pi / 5 - math.pi / 2 for i in range(10))]
        pygame.draw.polygon(surface, c, pts)
    elif style.emblem == "bow":
        box = pygame.Rect(0, 0, int(r * 1.4), int(r * 2))
        box.center = (int(cx - r * 0.15), cy)
        pygame.draw.arc(surface, c, box, -math.pi / 2, math.pi / 2, w + 1)
        pygame.draw.line(surface, c, (box.centerx, box.top + 1), (box.centerx, box.bottom - 1), w)
        pygame.draw.line(surface, c, (cx - r * 0.8, cy), (cx + r * 0.6, cy), w)
    elif style.emblem == "wing":
        for i in range(4):
            a = -0.9 + i * 0.45
            tip = (cx + math.cos(a) * r, cy + math.sin(a) * r)
            pygame.draw.line(surface, c, (cx - r * 0.6, cy + r * 0.4), tip, w + 1)
    else:   # sword
        pygame.draw.line(surface, c, (cx - r * 0.7, cy + r * 0.7), (cx + r * 0.7, cy - r * 0.7), w + 1)
        pygame.draw.line(surface, c, (cx - r * 0.55, cy + r * 0.05), (cx - r * 0.05, cy + r * 0.55), w + 1)


def draw_wings(target: pygame.Surface, rect: pygame.Rect, phase: float, color: tuple[int, int, int],
               image: Optional[pygame.Surface] = None) -> None:
    """Машущие крылья за картой. image: правое крыло (корень слева внизу), левое — его отражение."""
    flap = math.sin(phase)
    if image is not None:
        size = int(rect.width * 0.95)
        wing = pygame.transform.smoothscale(image, (size, int(size * image.get_height() / image.get_width())))
        for side in (-1, 1):
            sprite = wing if side > 0 else pygame.transform.flip(wing, True, False)
            sprite = pygame.transform.rotate(sprite, flap * 14 * side)
            root = (rect.centerx + side * rect.width * 0.25, rect.top + rect.height * 0.32)
            box = sprite.get_rect(bottomleft=root) if side > 0 else sprite.get_rect(bottomright=root)
            target.blit(sprite, box)
        return
    length = rect.width * 0.9
    for side in (-1, 1):
        root = (rect.centerx + side * rect.width * 0.3, rect.top + rect.height * 0.3)
        for i in range(6):
            a = math.radians(-70 + i * 17 + flap * 18 * (1 - i / 8))     # верхние перья машут сильнее
            size = length * (1 - i * 0.11)
            tip = (root[0] + side * math.cos(a) * size, root[1] + math.sin(a) * size)
            mid = ((root[0] + tip[0]) / 2, (root[1] + tip[1]) / 2)
            nx, ny = -(tip[1] - root[1]), tip[0] - root[0]
            norm = math.hypot(nx, ny) or 1
            spread = size * 0.13
            pts = [root, (mid[0] + nx / norm * spread, mid[1] + ny / norm * spread), tip,
                   (mid[0] - nx / norm * spread * 0.5, mid[1] - ny / norm * spread * 0.5)]
            pygame.draw.polygon(target, shade(color, 0.75 + i * 0.05), pts)
            pygame.draw.polygon(target, shade(color, 0.45), pts, 1)


class CardArt:
    """Готовые изображения карт: плоские и повёрнутые."""

    def __init__(self, card_dir: Path = CARD_DIR):
        self.card_dir = Path(card_dir)
        self.styles, self.order, self.default_style, self.side_colors = load_styles(self.card_dir)
        self.image_layout = {**CODE_LAYOUT, **load_frames_config(self.card_dir).get("image_layout", {})}
        self._images: dict[str, Optional[pygame.Surface]] = {}
        self._cards: "OrderedDict[tuple, pygame.Surface]" = OrderedDict()
        self._masks: dict[int, pygame.Surface] = {}

    # --- картинки ---

    def _image(self, relative: str) -> Optional[pygame.Surface]:
        if relative not in self._images:
            path = self.card_dir / relative
            self._images[relative] = pygame.image.load(str(path)).convert_alpha() if path.exists() else None
        return self._images[relative]

    def has_art(self, class_id: str) -> bool:
        return (self.card_dir / f"{class_id}.png").exists()

    def art(self, class_id: str) -> Optional[pygame.Surface]:
        return self._image(f"{class_id}.png")

    def wing_image(self) -> Optional[pygame.Surface]:
        return self._image("wings.png")

    def background(self) -> Optional[pygame.Surface]:
        """Фон поля боя: assets/cards/background.png, если есть."""
        return self._image("background.png")

    def style_for(self, tags: Iterable[str]) -> str:
        tags = set(tags)
        return next((name for name in self.order if name in tags and name in self.styles), self.default_style)

    # --- плоская карта ---

    def flat(self, face: CardFace, size: tuple[int, int]) -> pygame.Surface:
        w, h = size
        f = h / BASE_HEIGHT
        px = lambda value: max(1, round(value * f))
        style = self.styles.get(face.style) or self.styles[self.default_style]
        frame_image = self._image(f"frames/{style.name}.png")
        layout = self.image_layout if frame_image is not None else CODE_LAYOUT
        box_of = lambda name: pygame.Rect(round(layout[name][0] * w), round(layout[name][1] * h),
                                          round((layout[name][2] - layout[name][0]) * w),
                                          round((layout[name][3] - layout[name][1]) * h))
        spot = lambda name: ((round(layout[name][0] * w), round(layout[name][1] * h)), max(2, round(layout[name][2] * w)))
        card = pygame.Surface((w, h), pygame.SRCALPHA)

        if frame_image is None:   # основа и рамка с фаской
            outer = card.get_rect()
            pygame.draw.rect(card, shade(style.dark, 0.7), outer, border_radius=px(9))
            pygame.draw.rect(card, style.light, outer, px(3), border_radius=px(9))
            pygame.draw.rect(card, shade(style.dark, 1.3), outer.inflate(-px(6), -px(6)), px(2), border_radius=px(7))

        # Арт (под картинкой рамки он шире окна: края закрывает рамка)
        window = box_of("art")
        pygame.draw.rect(card, CARD_BACK, window)
        self._draw_art(card, face.class_id, window, f)
        if frame_image is not None:
            card.blit(pygame.transform.smoothscale(frame_image, (w, h)), (0, 0))
        else:
            for i in range(px(18)):                      # затемнение низа арта под ленту
                line = pygame.Surface((window.width, 1), pygame.SRCALPHA)
                line.fill((0, 0, 0, int(150 * i / px(18))))
                card.blit(line, (window.left, window.bottom - px(18) + i))
            pygame.draw.rect(card, style.light, window, px(1))

        # Лента с названием класса
        banner = box_of("banner")
        if frame_image is None:
            notch = px(6)
            mid = banner.centery
            ribbon = [banner.topleft, banner.topright, (banner.right - notch, mid), banner.bottomright,
                      banner.bottomleft, (banner.left + notch, mid)]
            pygame.draw.polygon(card, shade(style.dark, 0.9), ribbon)
            pygame.draw.polygon(card, style.light, ribbon, px(1))
        draw_text(card, face.title.upper(), px(10), TEXT_LIGHT, banner.center, banner.width - px(16))

        # Поле: теги класса и активные эффекты
        box = box_of("text")
        if frame_image is None:
            pygame.draw.rect(card, (18, 20, 28), box, border_radius=px(3))
            pygame.draw.rect(card, shade(style.light, 0.6), box, px(1), border_radius=px(3))
        # Две строки по высоте поля: теги сверху, эффекты снизу (без эффектов теги по центру).
        line = max(6, min(px(7), int(box.height * 0.42)))
        tags_y = box.top + box.height * (0.3 if face.effects else 0.5)
        draw_text(card, face.subtitle, line, shade(style.light, 1.1), (box.centerx, round(tags_y)),
                  box.width - px(6), outline=False, bold=False)
        if face.effects:
            draw_text(card, ", ".join(face.effects), line, (250, 214, 110), (box.centerx, round(box.top + box.height * 0.74)),
                      box.width - px(6), outline=False)

        # HP: полоса с числами
        bar = box_of("hp")
        pygame.draw.rect(card, HP_BACK, bar, border_radius=px(3))
        fill = bar.copy()
        fill.width = round(bar.width * max(0, face.hp) / max(1, face.max_hp))
        pygame.draw.rect(card, HP_FULL if face.hp * 3 > face.max_hp else HP_LOW, fill, border_radius=px(3))
        pygame.draw.rect(card, style.light, bar, px(1), border_radius=px(3))
        draw_text(card, f"{max(0, face.hp)}/{face.max_hp}", max(px(8), int(bar.height * 0.9)), TEXT_LIGHT, bar.center)

        # Самоцветы и эмблема
        center, radius = spot("ap")
        self._gem(card, "ap", center, radius, AP_GEM, str(face.ap), style, dim=face.ap == 0)
        center, radius = spot("pp")
        self._gem(card, "pp", center, radius, PP_GEM, str(face.pp), style, dim=face.pp == 0)
        center, radius = spot("level")
        self._gem(card, f"level_{style.name}", center, radius, style.gem, str(face.level), style, diamond=True)
        center, radius = spot("emblem")
        emblem = self._image(f"emblems/{style.emblem}.png")
        if emblem is not None:
            sprite = pygame.transform.smoothscale(emblem, (radius * 2, radius * 2))
            card.blit(sprite, sprite.get_rect(center=center))
        else:
            draw_emblem(card, center, radius, style)
        return card

    def _gem(self, card: pygame.Surface, name: str, center: tuple[int, int], radius: int, color, text: str,
             style: FrameStyle, diamond: bool = False, dim: bool = False) -> None:
        """Самоцвет: картинка gems/<name>.png (у уровня — gems/level_<стиль>.png или gems/level.png), иначе кодом."""
        image = self._image(f"gems/{name}.png") or (self._image("gems/level.png") if name.startswith("level") else None)
        if image is None:
            draw_gem(card, center, radius, color, text, style.light, diamond=diamond, dim=dim)
            return
        size = radius * 2 + 2
        sprite = pygame.transform.smoothscale(image, (size, size))
        if dim:
            sprite = pygame.transform.grayscale(sprite)
        card.blit(sprite, sprite.get_rect(center=center))
        draw_text(card, text, int(radius * 1.25), TEXT_LIGHT if not dim else (170, 170, 170), center)

    def _draw_art(self, card: pygame.Surface, class_id: str, window: pygame.Rect, f: float) -> None:
        art = self.art(class_id)
        if art is not None:
            # Арт заполняет окно целиком, лишнее обрезается (по центру и сверху).
            k = max(window.width / art.get_width(), window.height / art.get_height())
            scaled = pygame.transform.smoothscale(art, (math.ceil(art.get_width() * k), math.ceil(art.get_height() * k)))
            card.blit(scaled, window.topleft, pygame.Rect((scaled.get_width() - window.width) // 2, 0, *window.size))
            return
        for i in range(window.height):                   # заглушка: тёмный градиент и спрайт класса
            k = i / window.height
            pygame.draw.line(card, (int(40 + 30 * k), int(44 + 26 * k), int(62 + 10 * k)),
                             (window.left, window.top + i), (window.right - 1, window.top + i))
        sprite = _fallback_art(class_id)
        if sprite is not None:
            k = min(window.width * 0.85 / sprite.get_width(), window.height * 0.82 / sprite.get_height())
            sprite = pygame.transform.scale(sprite, (max(1, int(sprite.get_width() * k)), max(1, int(sprite.get_height() * k))))
            card.blit(sprite, sprite.get_rect(midbottom=(window.centerx, window.bottom - max(1, round(4 * f)))))

    # --- повёрнутая карта ---

    def tilted(self, face: CardFace, side: str, size: tuple[int, int]) -> pygame.Surface:
        """Карта, повёрнутая к противнику. Левая сторона смотрит вправо, правая влево."""
        key = (face, side, size)
        card = self._cards.get(key)
        if card is None:
            flat = self.flat(face, size)
            if face.dead:
                flat = pygame.transform.grayscale(flat)
                flat.fill((120, 120, 120, 150), special_flags=pygame.BLEND_RGBA_MULT)
            card = tilt(flat, TILT_DEGREES, facing_right=side == "left")
            self._cards[key] = card
            if len(self._cards) > CACHE_LIMIT:
                old = self._cards.popitem(last=False)[1]
                self._masks.pop(id(old), None)
        else:
            self._cards.move_to_end(key)
        return card

    def silhouette(self, card: pygame.Surface) -> pygame.Surface:
        """Белый силуэт карты для вспышки при попадании."""
        key = id(card)
        if key not in self._masks:
            mask = pygame.mask.from_surface(card)
            self._masks[key] = mask.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
        return self._masks[key]


def tilt(card: pygame.Surface, degrees: float, facing_right: bool) -> pygame.Surface:
    """Поворот карты вокруг вертикальной оси: столбцы пикселей сжимаются к дальнему краю."""
    w, h = card.get_size()
    out_w = max(1, round(w * math.cos(math.radians(degrees))))
    out = pygame.Surface((out_w, h), pygame.SRCALPHA)
    for x in range(out_w):
        t = x / max(1, out_w - 1)               # 0 у левого края, 1 у правого
        far = t if facing_right else 1 - t      # 1 у дальнего края
        k = 1 - PERSPECTIVE * far * math.sin(math.radians(degrees)) * 2
        column_h = max(1, round(h * k))
        src_x = min(w - 1, int(x * w / out_w))
        column = card.subsurface(pygame.Rect(src_x, 0, 1, h))
        out.blit(pygame.transform.smoothscale(column, (1, column_h)), (x, (h - column_h) // 2))
    return out
