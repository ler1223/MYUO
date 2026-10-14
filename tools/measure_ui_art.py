"""Замеры нарисованных рамок и полос для движка интерфейса (uikit) — запускать после замены картинок.

    python tools/measure_ui_art.py            # обновить assets/ui/theme.json и нарезать полосы
    python tools/measure_ui_art.py --dry-run  # только показать замеры

Рамки (assets/ui/frame/<вид>.png): «тело» — внутренняя область рамки. От середины картинки идём
к каждому краю, пока цвет не отличается от середины заметно (линия рамки). Отступы до тела
пишутся в theme.json -> frames.<вид>.fill [слева, сверху, справа, снизу] в пикселях картинки.
По ним все состояния виджета (обычное, наведение, выбор) выравниваются по одному телу, даже если
картинки разного размера или с украшениями сверху (у активной вкладки — лилия).

Полосы (assets/ui/bar/<вид>.png): картинка режется на конец (левый край с ромбом; правый —
его зеркало) и тело (узкий кусок середины). Пишутся bar/<вид>_end.png и bar/<вид>_body.png,
а в theme.json -> bars.<вид>: inner — где внутри конца начинается заливка (x) и её строки (y0, y1).
Полоса любой длины собирается на месте: конец + растянутое тело + зеркальный конец.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = ROOT / "assets" / "ui"
THEME = UI_DIR / "theme.json"
EDGE = 90             # насколько цвет (сумма разниц каналов) отличается от середины на линии рамки
BODY_W = 8            # ширина куска тела полосы


def _diff(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def _mean(image: pygame.Surface, x: int, y: int, r: int = 1):
    """Средний цвет квадрата (2r+1) — шум текстуры не принимается за линию."""
    w, h = image.get_size()
    pixels = [image.get_at((min(w - 1, max(0, x + dx)), min(h - 1, max(0, y + dy))))
              for dx in range(-r, r + 1) for dy in range(-r, r + 1)]
    return tuple(sum(p[i] for p in pixels) // len(pixels) for i in range(4))


def fill_insets(image: pygame.Surface) -> list[int]:
    """[слева, сверху, справа, снизу]: от краёв картинки до тела рамки."""
    w, h = image.get_size()
    cx, cy = w // 2, h // 2
    center = _mean(image, cx, cy, 3)

    def walk(dx: int, dy: int) -> int:
        x, y, steps = cx, cy, 0
        while 0 < x < w - 1 and 0 < y < h - 1:
            p = _mean(image, x, y)
            if p[3] < 200 or _diff(p, center) > EDGE:
                return steps
            x, y, steps = x + dx, y + dy, steps + 1
        return steps

    left, right, up, down = walk(-1, 0), walk(1, 0), walk(0, -1), walk(0, 1)
    # усреднение 3x3 замечает линию на пиксель раньше: первый «другой» пиксель — уже первый пиксель тела
    return [cx - left, cy - up, w - (cx + right) - 1, h - (cy + down) - 1]


def bar_parts(image: pygame.Surface) -> tuple[pygame.Surface, pygame.Surface, list[int]]:
    """(конец, тело, [x начала заливки в конце, y0, y1])."""
    w, h = image.get_size()
    mid = w // 2
    column = [image.get_at((mid, y)) for y in range(h)]

    def same(x: int) -> bool:                    # форма столбца (прозрачность) как у середины
        return all(abs(image.get_at((x, y)).a - column[y].a) < 60 for y in range(h))

    end = next((x for x in range(w // 3) if all(same(x + k) for k in range(6))), w // 6)
    end = min(end + 4, w // 3)
    # строки заливки: от середины вверх и вниз, пока цвет похож на середину
    center = _mean(image, mid, h // 2, 1)
    y0 = h // 2
    while y0 > 0 and _diff(image.get_at((mid, y0 - 1)), center) < 150 and image.get_at((mid, y0 - 1)).a > 200:
        y0 -= 1
    y1 = h // 2
    while y1 < h - 1 and _diff(image.get_at((mid, y1 + 1)), center) < 150 and image.get_at((mid, y1 + 1)).a > 200:
        y1 += 1
    # x начала заливки: на средней строке от конца влево, пока цвет похож на заливку
    x0 = end
    while x0 > 0 and _diff(image.get_at((x0 - 1, h // 2)), center) < 150:
        x0 -= 1
    end_piece = image.subsurface((0, 0, end, h)).copy()
    body = image.subsurface((mid - BODY_W // 2, 0, BODY_W, h)).copy()
    return end_piece, body, [x0, y0, y1 + 1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    pygame.init()
    pygame.display.set_mode((8, 8))
    theme = json.loads(THEME.read_text(encoding="utf-8")) if THEME.is_file() else {}
    frames = theme.setdefault("frames", {})
    for path in sorted((UI_DIR / "frame").glob("*.png")):
        image = pygame.image.load(str(path)).convert_alpha()
        entry = frames.setdefault(path.stem, {})
        if entry.get("manual"):              # замер не удался (градиент, значок в середине) — задано руками
            print(f"frame/{path.stem:22} {image.get_size()}  fill {entry.get('fill')} (manual)")
            continue
        entry["fill"] = fill_insets(image)
        print(f"frame/{path.stem:22} {image.get_size()}  fill {entry['fill']}")
    bars = theme.setdefault("bars", {})
    for path in sorted((UI_DIR / "bar").glob("*.png")):
        if path.stem.endswith(("_end", "_body")):
            continue
        image = pygame.image.load(str(path)).convert_alpha()
        end, body, inner = bar_parts(image)
        print(f"bar/{path.stem:24} {image.get_size()}  end {end.get_width()}  inner {inner}")
        bars.setdefault(path.stem, {})["inner"] = inner
        if not args.dry_run:
            pygame.image.save(end, str(path.with_name(f"{path.stem}_end.png")))
            pygame.image.save(body, str(path.with_name(f"{path.stem}_body.png")))
    if not args.dry_run:
        THEME.write_text(json.dumps(theme, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(THEME)


if __name__ == "__main__":
    sys.exit(main())
