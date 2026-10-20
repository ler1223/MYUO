"""Фигуры классов вне боя (башня, мир, карточки, портреты) — те же куклы UO, что и в показе боя.

Фигура стоит в стойке боя (часть фазы stance «по кругу»: UPWARD_IDLE или STANCE_2) и рисуется
видеокартой (engine.uo.library.Model.frame) в картинку pygame. Масштаб общий: человек ростом
HUMAN_UNITS единиц игры = заданный рост в пикселях, так что всадники и звери выше людей, как в игре.
Нет папки игры, видеокарты или файла класса — фигуры нет (None), экраны рисуют свою замену.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Optional

import pygame

from .data import TICK_MS, ShowData

HUMAN_UNITS = 360.0          # рост пешего бойца в стойке, единицы игры (медиана классов UO)
FACE_FOLDER = "CharaFace"    # портреты UO: Face_<файл класса>.mbs — фигура по пояс, точка 0,0 у лица
FACE_ANIM = "FACE_UI"
FACE_SIDE = 150.0            # сторона квадрата портрета (голова и плечи), единицы игры
FACE_ABOVE = 0.45            # доля квадрата выше точки 0,0 (лица); по рамке нельзя — шлемы, посохи, маски
FRAME_STEP = 2               # тиков игры на кадр фигуры (30 кадров в секунду хватает экранам)
CACHE_FRAMES = 1500          # кадров в памяти


class Figures:
    def __init__(self, data: Optional[ShowData] = None):
        self.data = data or ShowData()
        self._frames: OrderedDict = OrderedDict()
        self._anims: dict[str, Optional[str]] = {}

    # --- что есть ---

    def stance(self, class_id: str, look: int = 0) -> Optional[str]:
        """Анимация стойки класса (часть «по кругу») или None."""
        key = (class_id, look)
        if key not in self._anims:
            parts = self.data.phase(class_id, "stance")
            loop = [p for p in parts if p.endswith("*")]
            name = (loop or parts or [""])[-1].rstrip("*")
            model = self.data.unit_model(class_id, look) if name else None
            self._anims[key] = name if model is not None and name in model.puppet.anims else None
        return self._anims[key]

    def has(self, class_id: Optional[str], look: int = 0) -> bool:
        return bool(class_id) and self.data.ok and self.stance(class_id, look) is not None

    def box(self, class_id: str, look: int = 0) -> Optional[tuple[float, float, float, float]]:
        """Рамка стойки в единицах игры (ноги — y = 0)."""
        name = self.stance(class_id, look) if self.data.ok else None
        return self.data.unit_model(class_id, look).box(name) if name else None

    def ratio(self, class_id: str, look: int = 0) -> float:
        """Рост фигуры относительно человека (всадник — около 2.5)."""
        box = self.box(class_id, look)
        return (box[3] - box[1]) / HUMAN_UNITS if box else 1.0

    # --- кадры ---

    def pose(self, class_id: str, now_ms: float, height: float, flip: bool = False, look: int = 0
             ) -> Optional[tuple[pygame.Surface, tuple[float, float]]]:
        """(кадр стойки сейчас, точка ног в нём); height — рост человека в пикселях."""
        name = self.stance(class_id, look) if self.data.ok else None
        if name is None:
            return None
        model = self.data.unit_model(class_id, look)
        length = max(1, model.length(name))
        tick = int(now_ms / TICK_MS) % length // FRAME_STEP * FRAME_STEP
        return self._frame((class_id, look), model, name, tick, height / HUMAN_UNITS, flip)

    def still(self, class_id: str, height: float, flip: bool = False, look: int = 0
              ) -> Optional[tuple[pygame.Surface, tuple[float, float]]]:
        """Первый кадр стойки (портреты, неподвижные картинки)."""
        name = self.stance(class_id, look) if self.data.ok else None
        if name is None:
            return None
        return self._frame((class_id, look), self.data.unit_model(class_id, look), name, 0, height / HUMAN_UNITS, flip)

    def fit(self, class_id: str, size: tuple[int, int], look: int = 0) -> float:
        """Рост человека в пикселях, при котором стойка класса вписывается в size."""
        box = self.box(class_id, look)
        if not box:
            return float(size[1])
        w, h = max(1.0, box[2] - box[0]), max(1.0, box[3] - box[1])
        return min(size[0] / w, size[1] / h) * HUMAN_UNITS

    # --- портреты ---

    def face_model(self, class_id: str):
        """Портрет класса из CharaFace (по файлу класса, без номера внешности) или None."""
        if not self.data.ok:
            return None
        info = self.data.classes.get(class_id, {})
        names = [info["face"]] if info.get("face") else []
        file = info.get("file", "")
        names += [f"Face_{file}", f"Face_{file[:-2]}" if file[-2:].isdigit() else ""]
        for name in filter(None, names):
            model = self.data.model(FACE_FOLDER, name)
            if model is not None and FACE_ANIM in model.puppet.anims:
                return model
        return None

    def face(self, class_id: str, size: int, flip: bool = False) -> Optional[pygame.Surface]:
        """Квадратный портрет size x size: голова и плечи с портрета UO."""
        key = ("face", class_id, size, flip)
        found = self._frames.get(key)
        if found is not None:
            return found
        model = self.face_model(class_id)
        box = model.box(FACE_ANIM) if model is not None else None
        if not box:
            return None
        cx, top, side = self.data.classes.get(class_id, {}).get("face_box") or (0.0, -FACE_SIDE * FACE_ABOVE, FACE_SIDE)
        if flip:
            cx = -cx
        crop = (cx - side / 2, top, cx + side / 2, top + side)
        out = model.frame(FACE_ANIM, 0, size / side, flip, box=crop)
        if out is None:
            return None
        rgba = out[0]
        surface = pygame.image.frombytes(rgba.tobytes(), (rgba.shape[1], rgba.shape[0]), "RGBA")
        if surface.get_size() != (size, size):
            square = pygame.Surface((size, size), pygame.SRCALPHA)
            square.blit(surface, ((size - surface.get_width()) // 2, 0))
            surface = square
        self._frames[key] = surface
        return surface

    def _frame(self, class_id: str, model, anim: str, tick: int, scale: float, flip: bool):
        scale = round(scale, 3)
        key = (class_id, anim, tick, scale, flip)
        found = self._frames.get(key)
        if found is not None:
            self._frames.move_to_end(key)
            return found
        tick = model.puppet.canonical_tick(anim, tick, True)
        out = model.frame(anim, tick, scale, flip, loop=True, box=model.box(anim))
        if out is None:
            return None
        rgba, origin = out
        h, w = rgba.shape[:2]
        surface = pygame.image.frombytes(rgba.tobytes(), (w, h), "RGBA")
        found = (surface, (float(origin[0]), float(origin[1])))
        self._frames[key] = found
        while len(self._frames) > CACHE_FRAMES:
            self._frames.popitem(last=False)
        return found
