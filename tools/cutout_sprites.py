"""Сборка анимаций из листа частей персонажа (cut-out анимация).

Запуск: python tools/cutout_sprites.py knight

Читает assets/sprites_src/<класс>/sheet.png и rig.json, пишет в assets/sprites/<класс>/:
полоски кадров <анимация>.png, sprite.json (размер кадра для арены) и preview.png.

rig.json:
- parts: {имя: {"box": [x, y, w, h] на листе, "pivot": [x, y] на листе}} — pivot это сустав,
  вокруг которого часть вращается;
- bones: [{"name", "part" (или null), "parent" (или null), "attach": [dx, dy] — где сустав
  стоит относительно сустава родителя, в пикселях листа, "z": порядок рисования,
  "shade": затемнение для дальних конечностей, "part_scale": [sx, sy]}];
- scale: во сколько раз уменьшить лист; frame: [w, h] кадра; root: [x, y] — где в кадре таз;
- animations: {имя: [{кость: угол в градусах, "root": [dx, dy]}, ...]} — кадры позы;
  угол 0 = часть висит как на листе, плюс = против часовой стрелки.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "sprites_src"
OUT = ROOT / "assets" / "sprites"
SUPERSAMPLE = 3          # рисуем крупнее и уменьшаем: края частей сглаживаются
BG_THRESHOLD = 22        # насколько цвет пикселя может отличаться от фона листа


def cut_part(sheet: pygame.Surface, box: list[int], bg: pygame.Color) -> pygame.Surface:
    """Вырезает часть из рамки: фон, связанный с краем рамки, становится прозрачным.

    Светлые места внутри части (блики на металле), похожие на фон, не вырезаются.
    """
    rect = pygame.Rect(box)
    part = sheet.subsurface(rect).convert_alpha()
    background = pygame.mask.from_threshold(part, bg, (BG_THRESHOLD,) * 3 + (255,))
    width, height = rect.size
    outside = pygame.mask.Mask((width, height))
    for region in background.connected_components():
        bounds = region.get_bounding_rects()
        if any(r.left == 0 or r.top == 0 or r.right == width or r.bottom == height for r in bounds):
            outside.draw(region, (0, 0))
    for y in range(height):
        for x in range(width):
            if outside.get_at((x, y)):
                part.set_at((x, y), (0, 0, 0, 0))
    return part


def rotate_vector(x: float, y: float, degrees: float) -> tuple[float, float]:
    """Поворот против часовой стрелки на экране (ось y вниз), как pygame.transform.rotate."""
    a = math.radians(degrees)
    return x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)


class Rig:
    def __init__(self, folder: Path):
        self.spec = json.loads((folder / "rig.json").read_text(encoding="utf-8"))
        sheet = pygame.image.load(str(folder / "sheet.png")).convert_alpha()
        bg = sheet.get_at((4, 4))
        self.scale = self.spec["scale"] * SUPERSAMPLE
        self.parts: dict[str, tuple[pygame.Surface, tuple[float, float]]] = {}
        for name, data in self.spec["parts"].items():
            image = cut_part(sheet, data["box"], bg)
            x, y, _, _ = data["box"]
            pivot = (data["pivot"][0] - x, data["pivot"][1] - y)
            self.parts[name] = (image, pivot)
        self.bones = {bone["name"]: bone for bone in self.spec["bones"]}
        self._cache: dict[tuple, pygame.Surface] = {}

    def _part_image(self, bone: dict) -> tuple[pygame.Surface, tuple[float, float]]:
        """Часть кости, уменьшенная до размера кадра (и затемнённая для дальних конечностей)."""
        key = (bone["name"],)
        image, (px, py) = self.parts[bone["part"]]
        sx, sy = bone.get("part_scale", (1, 1))
        if key not in self._cache:
            size = (max(1, round(image.get_width() * self.scale * sx)), max(1, round(image.get_height() * self.scale * sy)))
            scaled = pygame.transform.smoothscale(image, size)
            if bone.get("shade"):
                scaled.fill(tuple(bone["shade"]) + (255,), special_flags=pygame.BLEND_RGBA_MULT)
            if bone.get("flip"):
                scaled = pygame.transform.flip(scaled, True, False)
            self._cache[key] = scaled
        width = image.get_width()
        if bone.get("flip"):
            px = width - px
        return self._cache[key], (px * self.scale * sx, py * self.scale * sy)

    def render(self, pose: dict) -> pygame.Surface:
        fw, fh = self.spec["frame"]
        canvas = pygame.Surface((fw * SUPERSAMPLE, fh * SUPERSAMPLE), pygame.SRCALPHA)
        rx, ry = self.spec["root"]
        dx, dy = pose.get("root", (0, 0))
        world: dict[str, tuple[float, float, float]] = {}   # кость -> (x, y, угол)

        def place(name: str) -> tuple[float, float, float]:
            if name not in world:
                bone = self.bones[name]
                angle = pose.get(name, bone.get("angle", 0))
                if bone.get("parent") is None:
                    world[name] = ((rx + dx) * SUPERSAMPLE, (ry + dy) * SUPERSAMPLE, angle)
                else:
                    px, py, pangle = place(bone["parent"])
                    ax, ay = bone.get("attach", (0, 0))
                    ox, oy = rotate_vector(ax * self.scale, ay * self.scale, pangle)
                    world[name] = (px + ox, py + oy, pangle + angle)
            return world[name]

        for name in self.bones:
            place(name)
        for bone in sorted(self.bones.values(), key=lambda b: b.get("z", 0)):
            if not bone.get("part"):
                continue
            image, (pvx, pvy) = self._part_image(bone)
            x, y, angle = world[bone["name"]]
            rotated = pygame.transform.rotate(image, angle)
            # Центр части относительно сустава, повёрнутый вместе с частью.
            cx, cy = rotate_vector(image.get_width() / 2 - pvx, image.get_height() / 2 - pvy, angle)
            canvas.blit(rotated, rotated.get_rect(center=(round(x + cx), round(y + cy))))
            for effect in pose.get("glow", []):
                if effect["bone"] == bone["name"]:
                    gx, gy = rotate_vector(*[v * self.scale for v in effect["at"]], angle)
                    glow(canvas, x + gx, y + gy, effect.get("radius", 10) * SUPERSAMPLE)
        return pygame.transform.smoothscale(canvas, (fw, fh))


def glow(canvas: pygame.Surface, x: float, y: float, radius: float) -> None:
    """Свечение каста: несколько полупрозрачных кругов."""
    for step, alpha in ((1.0, 50), (0.65, 90), (0.35, 200)):
        r = max(1, round(radius * step))
        spot = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(spot, (170, 220, 255, alpha), (r, r), r)
        canvas.blit(spot, (round(x) - r, round(y) - r))


def build(class_id: str) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    rig = Rig(SRC / class_id)
    out = OUT / class_id
    out.mkdir(parents=True, exist_ok=True)
    fw, fh = rig.spec["frame"]
    rows = []
    for name, poses in rig.spec["animations"].items():
        strip = pygame.Surface((fw * len(poses), fh), pygame.SRCALPHA)
        for i, pose in enumerate(poses):
            strip.blit(rig.render(pose), (i * fw, 0))
        pygame.image.save(strip, str(out / f"{name}.png"))
        rows.append(strip)
    meta = {"frame_width": fw, "frame_height": fh, "anchor_x": rig.spec["root"][0], "scale": 1,
            "ground": fh - rig.spec["ground_y"]}
    (out / "sprite.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    # Превью: все анимации строками, крупно, на сером фоне.
    zoom = 2
    preview = pygame.Surface((max(r.get_width() for r in rows) * zoom, fh * zoom * len(rows)))
    preview.fill((70, 74, 84))
    for i, strip in enumerate(rows):
        preview.blit(pygame.transform.scale_by(strip, zoom), (0, i * fh * zoom))
    pygame.image.save(preview, str(SRC / class_id / "preview.png"))
    print(f"{class_id}: {', '.join(rig.spec['animations'])} -> {out}")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "knight")
