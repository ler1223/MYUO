"""Спрайтовые эффекты: картинки и покадровые анимации (флипбуки) в мире 2.5D.

Описание — assets/fx/effects.json, картинки — assets/fx/<id>.png (или <id>_back.png и
<id>_front.png для обвивающих). Поля описания:
- grid [колонки, строки] и frames — сетка кадров (обход слева направо, сверху вниз), fps, loop;
- size — высота в единицах мира (рост человека 185);
- blend — add (чёрный фон, свечение сложением цветов) или alpha (прозрачный фон; если у
  картинки нет прозрачности, прозрачным становится цвет её левого верхнего угла);
- layer — front (перед юнитом), back (за ним), wrap (back и front файлы), ground (лежит на земле);
- animate — для одиночной картинки: sweep (раскрывается дугой), stretch (вытягивается),
  spin (вращается), grow (растёт и гаснет), pulse (пульсирует);
- orient — travel: поворачивается по направлению полёта.
Картинки смотрят вправо; эффект юнита противника отражается.
"""
from __future__ import annotations

import json
import math
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pygame

from .fx import Effect, ease_out
from .projection import World
from .render import BEHIND, GROUND, IN_FRONT, UPRIGHT, Part, View

FX_DIR = Path(__file__).resolve().parent.parent / "assets" / "fx"
CACHE = 600
SINGLE_MS = 500             # сколько живёт одиночная картинка без своего ms


class FxLibrary:
    """Описания и кадры спрайтовых эффектов папки."""

    def __init__(self, folder: Path = FX_DIR):
        self.folder = Path(folder)
        path = self.folder / "effects.json"
        self.specs: dict[str, dict[str, Any]] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self._frames: dict[str, list[pygame.Surface]] = {}
        self._scaled: OrderedDict = OrderedDict()

    def __contains__(self, name: str) -> bool:
        return name in self.specs

    def spec(self, name: str) -> dict[str, Any]:
        return self.specs.get(name, {})

    def files(self, name: str) -> dict[str, str]:
        """Часть эффекта -> файл: main, или back и front у обвивающих."""
        spec = self.spec(name)
        if spec.get("layer") == "wrap" and "back" in spec and "front" in spec:
            return {"back": spec["back"], "front": spec["front"]}
        return {"main": f"{name}.png"}

    def duration(self, name: str, default: int = SINGLE_MS) -> int:
        spec = self.spec(name)
        if spec.get("frames", 1) > 1 and not spec.get("loop"):
            return int(1000 * spec["frames"] / max(1, spec.get("fps", 24)))
        return default

    def frames(self, name: str, part: str) -> list[pygame.Surface]:
        key = f"{name}/{part}"
        if key not in self._frames:
            self._frames[key] = self._load(name, self.files(name).get(part, ""))
        return self._frames[key]

    def _load(self, name: str, file: str) -> list[pygame.Surface]:
        path = self.folder / file
        if not file or not path.is_file():
            return []
        spec = self.spec(name)
        image = pygame.image.load(str(path))
        has_display = pygame.display.get_surface() is not None
        if spec.get("blend") == "add":
            image = image.convert() if has_display else image
        else:
            if not image.get_flags() & pygame.SRCALPHA:       # фон без прозрачности: цвет угла — прозрачный
                image.set_colorkey(image.get_at((0, 0))[:3])
            image = image.convert_alpha() if has_display else image
        cols, rows = spec.get("grid", [1, 1])
        count = spec.get("frames", cols * rows)
        # Границы кадров — по долям размера: лист любого размера (1024, 1254...) режется ровно.
        iw, ih = image.get_size()
        xs = [round(c * iw / cols) for c in range(cols + 1)]
        ys = [round(r * ih / rows) for r in range(rows + 1)]
        frames = [image.subsurface(pygame.Rect(xs[i % cols], ys[i // cols], xs[i % cols + 1] - xs[i % cols],
                                               ys[i // cols + 1] - ys[i // cols])) for i in range(count)]
        return [trim(frame) for frame in frames] if spec.get("frames", 1) == 1 else frames

    def scaled(self, name: str, part: str, frame: int, height: int, width: Optional[int] = None,
               flip: bool = False, angle: float = 0.0) -> Optional[pygame.Surface]:
        """Кадр нужного размера в пикселях окна (повёрнутый, отражённый), с кэшем."""
        frames = self.frames(name, part)
        if not frames:
            return None
        source = frames[frame % len(frames)]
        width = width or max(1, round(source.get_width() * height / source.get_height()))
        key = (name, part, frame % len(frames), height, width, flip, round(angle / 3) * 3)
        if key in self._scaled:
            self._scaled.move_to_end(key)
            return self._scaled[key]
        image = pygame.transform.smoothscale(source, (max(1, width), max(1, height)))
        if flip:
            image = pygame.transform.flip(image, True, False)
        if key[-1]:
            image = pygame.transform.rotate(image, key[-1])
        self._scaled[key] = image
        if len(self._scaled) > CACHE:
            self._scaled.popitem(last=False)
        return image


def trim(image: pygame.Surface) -> pygame.Surface:
    """Одиночная картинка без пустых полей: по непрозрачным (или не чёрным) пикселям."""
    if image.get_flags() & pygame.SRCALPHA or image.get_colorkey() is not None:
        box = image.get_bounding_rect()
    else:
        mask = pygame.mask.from_threshold(image, (0, 0, 0), (12, 12, 12, 255))
        mask.invert()
        rects = mask.get_bounding_rects()
        box = rects[0].unionall(rects[1:]) if rects else image.get_rect()
    return image.subsurface(box) if box.width and box.height else image


def blit_effect(target: pygame.Surface, image: pygame.Surface, center: tuple[int, int], additive: bool,
                strength: float) -> None:
    """Картинка эффекта с силой strength (0..1): сложением цветов или с прозрачностью."""
    if strength <= 0.02:
        return
    rect = image.get_rect(center=center)
    if additive:
        if strength < 0.98:
            image = image.copy()
            level = int(255 * strength)
            image.fill((level, level, level), special_flags=pygame.BLEND_RGB_MULT)
        target.blit(image, rect, special_flags=pygame.BLEND_RGB_ADD)
    else:
        if strength < 0.98:
            image = image.copy()
            image.set_alpha(int(255 * strength))
        target.blit(image, rect)


@dataclass
class SpriteEffect(Effect):
    """Спрайтовый эффект в точке мира pos (центр картинки; лежащий — центр на земле)."""

    library: Optional[FxLibrary] = None
    name: str = ""
    pos: World = (0, 0, 0)
    scale: float = 1.0
    facing: int = 1

    def parts(self, now: int) -> list[Part]:
        t = self.progress(now)
        if t is None or self.library is None or self.name not in self.library:
            return []
        spec = self.library.spec(self.name)
        z = self.pos[2]
        layer = spec.get("layer", "front")
        if layer == "wrap":
            return [Part(UPRIGHT, z + BEHIND, lambda s, v: self._draw(s, v, now, t, "back")),
                    Part(UPRIGHT, z + IN_FRONT, lambda s, v: self._draw(s, v, now, t, "front"))]
        if layer == "ground":
            return [Part(GROUND, z, lambda s, v: self._draw(s, v, now, t, "main", ground=True))]
        depth = z + BEHIND if layer == "back" else z - 2
        return [Part(UPRIGHT, depth, lambda s, v: self._draw(s, v, now, t, "main"))]

    def _frame(self, now: int) -> int:
        spec = self.library.spec(self.name)
        return int((now - self.start) * spec.get("fps", 24) / 1000)

    def _draw(self, target: pygame.Surface, view: View, now: int, t: float, part: str, ground: bool = False) -> None:
        library, spec = self.library, self.library.spec(self.name)
        x, y, k = view.p(self.pos)
        height = spec.get("size", 160) * self.scale * k
        frames = spec.get("frames", 1)
        frame = self._frame(now)
        if frames > 1 and not spec.get("loop"):
            frame = min(frames - 1, frame)
        animate = spec.get("animate") if frames == 1 else None
        strength = 1.0 if frames > 1 and not spec.get("loop") else min(1.0, t / 0.12) * min(1.0, (1 - t) / 0.25)
        scale_x, angle = 1.0, 0.0
        if animate == "sweep":
            scale_x = 0.35 + 0.65 * ease_out(min(1.0, t * 1.8))
            strength = 1 - max(0.0, (t - 0.45) / 0.55)
        elif animate == "stretch":
            scale_x = 0.15 + 0.85 * ease_out(min(1.0, t * 2.2))
            strength = 1 - max(0.0, (t - 0.5) / 0.5)
        elif animate == "grow":
            height *= 0.4 + 0.9 * ease_out(t)
            strength = (1 - t) ** 1.2
        elif animate == "pulse":
            height *= 0.92 + 0.08 * math.sin(t * math.pi * 4)
            strength = math.sin(math.pi * t)
        elif animate == "spin":
            angle = -(now - self.start) * 0.36 * self.facing
        source = library.frames(self.name, part)
        if not source:
            return
        aspect = source[0].get_width() / source[0].get_height()
        px_h = max(2, round(height))
        px_w = max(2, round(height * aspect * scale_x))
        if ground:   # лежит на земле: сжат по высоте так же, как земля на этой глубине
            r = spec.get("size", 160) * self.scale / 2
            near = view.xy((self.pos[0], 0, self.pos[2] - r))[1]
            far = view.xy((self.pos[0], 0, self.pos[2] + r))[1]
            px_w = max(2, round(height * aspect * scale_x))
            px_h = max(2, abs(near - far))
            y = (near + far) // 2
        image = library.scaled(self.name, part, frame, px_h, px_w, self.facing < 0, angle)
        if image is not None:
            blit_effect(target, image, (x, y), spec.get("blend") == "add", strength)


@dataclass
class SpriteProjectile(Effect):
    """Снаряд-картинка от source к target по дуге; повёрнут по направлению полёта."""

    library: Optional[FxLibrary] = None
    name: str = ""
    source: World = (0, 0, 0)
    target: World = (0, 0, 0)
    arc: float = 0.0
    scale: float = 1.0

    def point(self, t: float) -> World:
        x, y, z = (a + (b - a) * t for a, b in zip(self.source, self.target))
        return x, y + math.sin(t * math.pi) * self.arc, z

    def parts(self, now: int) -> list[Part]:
        t = self.progress(now)
        if t is None or self.library is None or self.name not in self.library:
            return []
        return [Part(UPRIGHT, self.point(t)[2] - 1, lambda s, v: self._draw(s, v, now, t))]

    def _draw(self, target: pygame.Surface, view: View, now: int, t: float) -> None:
        spec = self.library.spec(self.name)
        head, k = view.p(self.point(t))[:2], view.p(self.point(t))[2]
        ahead = view.xy(self.point(min(1.0, t + 0.03)))
        dx, dy = ahead[0] - head[0], ahead[1] - head[1]
        left = dx < 0
        angle = math.degrees(math.atan2(-dy, -dx if left else dx)) * (-1 if left else 1)
        frame = int((now - self.start) * spec.get("fps", 18) / 1000)
        image = self.library.scaled(self.name, "main", frame, max(2, round(spec.get("size", 160) * self.scale * k)),
                                    flip=left, angle=angle)
        if image is not None:
            blit_effect(target, image, head, spec.get("blend") == "add", 1.0)


@dataclass
class SpriteBeam(Effect):
    """Картинка, растянутая между двумя точками (цепная молния): мерцает кадрами."""

    library: Optional[FxLibrary] = None
    name: str = ""
    source: World = (0, 0, 0)
    target: World = (0, 0, 0)
    thickness: float = 60

    def parts(self, now: int) -> list[Part]:
        t = self.progress(now)
        if t is None or self.library is None or self.name not in self.library:
            return []
        return [Part(UPRIGHT, min(self.source[2], self.target[2]) - 2, lambda s, v: self._draw(s, v, now, t))]

    def _draw(self, target: pygame.Surface, view: View, now: int, t: float) -> None:
        spec = self.library.spec(self.name)
        a, b = view.xy(self.source), view.xy(self.target)
        k = view.p(self.target)[2]
        length = max(2, round(math.hypot(b[0] - a[0], b[1] - a[1])))
        angle = math.degrees(math.atan2(-(b[1] - a[1]), b[0] - a[0]))
        frame = int((now - self.start) * spec.get("fps", 18) / 1000)
        image = self.library.scaled(self.name, "main", frame, max(2, round(self.thickness * k)), length, angle=angle)
        if image is not None:
            strength = min(1.0, t / 0.1) * min(1.0, (1 - t) / 0.3)
            blit_effect(target, image, ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2), spec.get("blend") == "add", strength)
