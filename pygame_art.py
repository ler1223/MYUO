"""Картинки интерфейса: иконки, фоны и портреты с цепочкой заглушек.

Картинка ищется по ключу в assets/ui/<ключ>.png. Ключ идёт от частного к общему через «/»:
для «item/light_sword/novice_sword» пробуются novice_sword, затем item/light_sword.png,
затем item.png. Самые общие ключи — это заглушки (tools/make_ui_placeholders.py), поэтому
картинка есть всегда; чтобы у предмета, навыка или экрана появилась своя картинка, достаточно
положить файл с более точным ключом — код менять не нужно.

Ключи (см. функции ниже и FEATURES.md):
  bg/<экран>                 фон экрана: bg/draft, bg/prepare, bg/battle, bg/reward, bg/shop, bg/over
  item/<слот>/<id>           предмет                -> item/<слот> -> item
  skill/<id>, passive/<id>   навык и пассивка       -> skill, passive
  stat/<стат>                иконка стата           -> stat
  icon/<имя>                 значки интерфейса      -> icon  (gold, exp, floor, boss, level)
  portrait/<класс>           портрет класса         -> верх спрайта класса (assets/units) -> portrait
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Optional

import pygame

from pygame_stage import SpriteBank

UI_DIR = Path(__file__).resolve().parent / "assets" / "ui"
CACHE = 600
PORTRAIT_SHARE = 0.36      # верхняя доля фигуры, которая идёт в портрет (голова и плечи)


def item_key(item) -> str:
    return f"item/{item.slot}/{item.id}"


def skill_key(skill_id: str) -> str:
    return f"skill/{skill_id}"


def passive_key(passive_id: str) -> str:
    return f"passive/{passive_id}"


def stat_key(stat) -> str:
    return f"stat/{getattr(stat, 'value', stat)}"


class ArtBank:
    """Картинки assets/ui по ключам с откатом к более общему ключу и кэшем масштабированных копий."""

    def __init__(self, folder: Path = UI_DIR):
        self.folder = Path(folder)
        self._files: dict[str, Optional[pygame.Surface]] = {}
        self._sized: OrderedDict = OrderedDict()

    def _load(self, key: str) -> Optional[pygame.Surface]:
        if key not in self._files:
            path = self.folder / f"{key}.png"
            image = None
            if path.is_file():
                image = pygame.image.load(str(path))
                if pygame.display.get_surface() is not None:
                    image = image.convert_alpha()
            self._files[key] = image
        return self._files[key]

    def has_own(self, key: str) -> bool:
        """Есть ли картинка именно с этим ключом (не заглушка)."""
        return self._load(key) is not None

    def find(self, key: str) -> tuple[str, pygame.Surface]:
        """Самая точная картинка по ключу: (найденный ключ, картинка)."""
        parts = key.split("/")
        while parts:
            found = self._load("/".join(parts))
            if found is not None:
                return "/".join(parts), found
            parts.pop()
        return "", _missing()

    def image(self, key: str, size: tuple[int, int], cover: bool = False) -> pygame.Surface:
        """Картинка в размер: вписанная целиком (по умолчанию) или заполняющая (cover, лишнее обрезается)."""
        found, source = self.find(key)
        cache_key = (found, size, cover)
        if cache_key in self._sized:
            self._sized.move_to_end(cache_key)
            return self._sized[cache_key]
        result = fit_image(source, size, cover)
        self._sized[cache_key] = result
        if len(self._sized) > CACHE:
            self._sized.popitem(last=False)
        return result


def fit_image(source: pygame.Surface, size: tuple[int, int], cover: bool = False) -> pygame.Surface:
    w, h = source.get_size()
    k = (max if cover else min)(size[0] / w, size[1] / h)
    scaled = pygame.transform.smoothscale(source, (max(1, round(w * k)), max(1, round(h * k))))
    if not cover:
        return scaled
    out = pygame.Surface(size, pygame.SRCALPHA)
    out.blit(scaled, ((size[0] - scaled.get_width()) // 2, (size[1] - scaled.get_height()) // 2))
    return out


def _missing() -> pygame.Surface:
    """Если нет даже общей заглушки (папку assets/ui удалили): серый квадрат."""
    surface = pygame.Surface((64, 64), pygame.SRCALPHA)
    surface.fill((70, 74, 90, 255))
    pygame.draw.rect(surface, (130, 135, 150), surface.get_rect(), 2)
    return surface


class Portraits:
    """Портреты классов: своя картинка portrait/<класс>, иначе верхняя часть спрайта, иначе заглушка.

    Вырезка из спрайта: голова находится по верхним непрозрачным строкам, берётся квадрат
    высотой PORTRAIT_SHARE роста фигуры. В assets/units/units.json у спрайта можно задать
    "portrait": [центр x, верх, размер] в долях картинки, если вырезка выходит неудачной.
    """

    def __init__(self, art: ArtBank, sprites: Optional[SpriteBank] = None):
        self.art = art
        self.sprites = sprites or SpriteBank()
        self._crops: dict[str, Optional[pygame.Surface]] = {}
        self._sized: OrderedDict = OrderedDict()

    def full(self, class_id: str, size: tuple[int, int], flip: bool = False) -> pygame.Surface:
        """Фигура целиком (карточки найма и набора)."""
        key = ("full", class_id, size, flip)
        if key not in self._sized:
            sprite_id = self.sprites.sprite_for(class_id)
            image = self.sprites.image(f"{sprite_id}.png") if sprite_id else None
            if image is None:
                image = self.art.find(f"portrait/{class_id}")[1]
            else:
                image = image.subsurface(image.get_bounding_rect())
            self._remember(key, _flip(fit_image(image, size), flip))
        return self._get(key)

    def portrait(self, class_id: str, size: int, flip: bool = False) -> pygame.Surface:
        """Квадратный портрет size x size."""
        key = ("portrait", class_id, size, flip)
        if key not in self._sized:
            if self.art.has_own(f"portrait/{class_id}"):
                image = self.art.image(f"portrait/{class_id}", (size, size), cover=True)
            else:
                crop = self._crop(class_id)
                image = fit_image(crop, (size, size), cover=True) if crop is not None \
                    else self.art.image("portrait", (size, size), cover=True)
            self._remember(key, _flip(image, flip))
        return self._get(key)

    def _crop(self, class_id: str) -> Optional[pygame.Surface]:
        if class_id in self._crops:
            return self._crops[class_id]
        crop = None
        sprite_id = self.sprites.sprite_for(class_id)
        image = self.sprites.image(f"{sprite_id}.png") if sprite_id else None
        if image is not None:
            iw, ih = image.get_size()
            own = self.sprites.sprites.get(sprite_id, {}).get("portrait")
            if own:
                cx, top, side = own[0] * iw, own[1] * ih, own[2] * ih
            else:
                cx, top, side = _head_box(image)
            rect = pygame.Rect(round(cx - side / 2), round(top), round(side), round(side)).clip(image.get_rect())
            if rect.width > 4 and rect.height > 4:
                crop = image.subsurface(rect).copy()
        self._crops[class_id] = crop
        return crop

    def _remember(self, key, image: pygame.Surface) -> None:
        self._sized[key] = image
        if len(self._sized) > CACHE:
            self._sized.popitem(last=False)

    def _get(self, key) -> pygame.Surface:
        self._sized.move_to_end(key)
        return self._sized[key]


HEAD_MIN_WIDTH = 0.16      # голова шире древка: строка фигуры шире этой доли — уже голова, а не оружие


def _head_box(image: pygame.Surface) -> tuple[float, float, float]:
    """(центр x, верх, сторона) квадрата с головой и плечами.

    Верх фигуры часто — наконечник копья или навершие посоха, поэтому голова ищется как первая
    строка, где непрозрачная часть шире HEAD_MIN_WIDTH ширины фигуры; центр — середина
    непрозрачных пикселей в полосе головы.
    """
    box = image.get_bounding_rect()
    try:
        import numpy  # есть вместе с pygame-ce в обычной установке; без него — грубая вырезка
        alpha = pygame.surfarray.array_alpha(image)[box.left:box.right, box.top:box.bottom] > 60
    except (ImportError, ValueError):
        return box.centerx, box.top, box.height * PORTRAIT_SHARE
    # Середина туловища: на этой высоте оружие тонкое, а тело широкое
    torso = alpha[:, round(box.height * 0.22):round(box.height * 0.42)].sum(axis=1)
    center = float((numpy.arange(len(torso)) * torso).sum() / torso.sum()) if torso.sum() else box.width / 2
    # Верх головы: первая строка, где есть фигура рядом с серединой туловища (навершие посоха сбоку)
    half = max(2, round(box.width * HEAD_MIN_WIDTH / 2))
    near = alpha[max(0, round(center) - half):round(center) + half, :].any(axis=0)
    rows = numpy.nonzero(near)[0]
    head = int(rows[0]) if len(rows) else 0
    side = (box.height - head) * PORTRAIT_SHARE
    # Голова чуть смещена от середины туловища: уточняем по полосе головы рядом с ней
    band = alpha[max(0, round(center - side / 2)):round(center + side / 2), head:head + round(side * 0.35)]
    columns = band.sum(axis=1)
    if columns.sum():
        center = max(0, round(center - side / 2)) + float((numpy.arange(len(columns)) * columns).sum() / columns.sum())
    return box.left + center, box.top + head - side * 0.06, side


def _flip(image: pygame.Surface, flip: bool) -> pygame.Surface:
    return pygame.transform.flip(image, True, False) if flip else image
