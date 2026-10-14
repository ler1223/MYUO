"""Нарезка листа-линейки персонажей на отдельные спрайты с общим масштабом.

Запуск: python tools/cut_lineup.py assets/sprites_src/lineup/lineup_2.png paladin hunter pyromancer cleric rider
        [--reference <id>] [--gap <пустых столбцов между персонажами, по умолчанию 2>]
        [--alpha <порог непрозрачности 0-255, по умолчанию 24; выше — если по листу рассыпан шум>]

Лист: персонажи стоят в ряд слева направо на одной линии земли, фон прозрачный.
Персонажи разделяются пустыми столбцами; если они касаются друг друга (оружие заходит на
соседа), силуэты разделяются по «перешейкам» (нужны numpy и scipy). Каждый сохраняется в assets/units/<id>.png
обрезанным по своим границам, без изменения размера: поэтому всадник остаётся выше
пехотинца ровно во столько раз, во сколько на листе. В assets/units/units.json
записывается рост человека на листе (по первому персонажу, если не задан --reference):
сцена масштабирует все спрайты одним коэффициентом от него. Персонаж с id, начинающимся
с «_» (например, паладин-эталон на новом листе), не сохраняется: он только мера роста.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "units"
ALPHA = 24              # пиксель с меньшей непрозрачностью считается фоном (--alpha N)
MIN_WIDTH = 40          # более узкие куски (соринки) не считаются персонажами
MIN_GAP = 2             # столько пустых столбцов подряд разделяют персонажей (--gap N)


def column_runs(sheet: pygame.Surface, min_gap: int = MIN_GAP, alpha: int = ALPHA) -> list[tuple[int, int]]:
    """Полосы непустых столбцов [начало, конец) слева направо."""
    w, h = sheet.get_size()
    mask = pygame.mask.from_surface(sheet, alpha)
    filled = [any(mask.get_at((x, y)) for y in range(0, h, 2)) for x in range(w)]
    runs, start, gap = [], None, 0
    for x, full in enumerate(filled + [False] * min_gap):
        if full:
            if start is None:
                start = x
            gap = 0
        elif start is not None:
            gap += 1
            if gap >= min_gap:
                runs.append((start, x - gap + 1))
                start, gap = None, 0
    return [run for run in runs if run[1] - run[0] >= MIN_WIDTH]


def crop(sheet: pygame.Surface, left: int, right: int, alpha: int = ALPHA) -> tuple[pygame.Surface, pygame.Rect]:
    """Персонаж в полосе столбцов: обрезка по непрозрачным пикселям; слабый шум прозрачности убирается."""
    part = sheet.subsurface(pygame.Rect(left, 0, right - left, sheet.get_height()))
    rect = pygame.mask.from_surface(part, alpha).get_bounding_rects()
    box = rect[0].unionall(rect[1:]) if rect else part.get_rect()
    image = part.subsurface(box).copy()
    # Пиксели прозрачнее порога (шум вокруг фигур) становятся полностью прозрачными:
    # маска умножает прозрачность на 1 внутри фигуры и на 0 вне её.
    keep = pygame.mask.from_surface(image, alpha).to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(255, 255, 255, 0))
    image.blit(keep, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return image, box.move(left, 0)


def split_touching(sheet: pygame.Surface, count: int, alpha: int) -> Optional[list[tuple[pygame.Surface, pygame.Rect]]]:
    """Персонажи, которые касаются друг друга (оружие заходит на соседа): силуэты сжимаются,
    пока не распадутся на count крупных частей, потом каждый пиксель отдаётся ближайшей части.
    Нужны numpy и scipy; без них — None."""
    try:
        import numpy as np
        from scipy import ndimage
    except ImportError:
        return None
    opaque = pygame.surfarray.array_alpha(sheet).T >= max(alpha, 128)   # [y, x]
    for radius in range(1, 40):
        core = ndimage.binary_erosion(opaque, iterations=radius)
        labels, found = ndimage.label(core)
        if found < count:
            continue
        sizes = ndimage.sum(core, labels, range(1, found + 1))
        big = [i + 1 for i in np.argsort(sizes)[::-1][:count] if sizes[i] >= sizes.max() * 0.15]
        if len(big) != count:
            continue
        # Слева направо; каждому непрозрачному пикселю — ближайшая крупная часть.
        big.sort(key=lambda label: ndimage.center_of_mass(core, labels, label)[1])
        seeds = np.zeros_like(labels)
        for index, label in enumerate(big, 1):
            seeds[labels == label] = index
        visible = pygame.surfarray.array_alpha(sheet).T >= alpha
        # Части растут только по силуэту (лента на копье уходит к хозяину копья, а не к соседу,
        # чья голова ближе по прямой); оторванные кусочки — ближайшей части.
        owner = seeds.copy()
        while True:
            grown = ndimage.grey_dilation(owner, size=3)
            fill = visible & (owner == 0) & (grown > 0)
            if not fill.any():
                break
            owner[fill] = grown[fill]
        if (visible & (owner == 0)).any():
            _, (iy, ix) = ndimage.distance_transform_edt(owner == 0, return_indices=True)
            owner = owner[iy, ix]
        result = []
        for index in range(1, count + 1):
            mine = visible & (owner == index)
            ys, xs = np.nonzero(mine)
            box = pygame.Rect(int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))
            image = sheet.subsurface(box).copy()
            keep = pygame.Surface(box.size, pygame.SRCALPHA)
            keep_alpha = pygame.surfarray.pixels_alpha(keep)
            keep_alpha[:] = (mine[box.top:box.bottom, box.left:box.right].T * 255).astype(np.uint8)
            del keep_alpha
            keep_rgb = pygame.surfarray.pixels3d(keep)
            keep_rgb[:] = 255
            del keep_rgb
            image.blit(keep, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            result.append((image, box))
        print(f"split touching characters (shrink radius {radius})")
        return result
    return None


def main(argv: list[str]) -> int:
    reference, min_gap, alpha = None, MIN_GAP, ALPHA
    if "--alpha" in argv:
        i = argv.index("--alpha")
        alpha = int(argv[i + 1])
        del argv[i:i + 2]
    if "--reference" in argv:
        i = argv.index("--reference")
        reference = argv[i + 1]
        del argv[i:i + 2]
    if "--gap" in argv:
        i = argv.index("--gap")
        min_gap = int(argv[i + 1])
        del argv[i:i + 2]
    if len(argv) < 2:
        print(__doc__)
        return 1
    sheet_path, ids = Path(argv[0]), argv[1:]
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    sheet = pygame.image.load(str(sheet_path)).convert_alpha()
    runs = column_runs(sheet, min_gap, alpha)
    if len(runs) == len(ids):
        pieces = [crop(sheet, left, right, alpha) for left, right in runs]
    else:
        pieces = split_touching(sheet, len(ids), alpha)
        if pieces is None:
            print(f"found {len(runs)} characters on the sheet, but {len(ids)} ids given: {runs}")
            return 1
    OUT.mkdir(parents=True, exist_ok=True)
    config_path = OUT / "units.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    sprites = config.setdefault("sprites", {})
    reference = reference or ids[0]
    human = None
    for unit_id, (image, box) in zip(ids, pieces):
        if unit_id == reference:
            human = box.height
        if unit_id.startswith("_"):            # эталон роста с образца: только мера, файл не нужен
            print(f"{unit_id}: {'reference' if unit_id == reference else 'skipped'} ({box.height}px), not saved")
            continue
        pygame.image.save(image, str(OUT / f"{unit_id}.png"))
        # Рост на листе: от низа (линия земли) до верха; масштаб общий для всего листа.
        # Остальные ключи спрайта (опорные точки anchors) сохраняются.
        sprites.setdefault(unit_id, {}).update({"sheet": sheet_path.name, "height": box.height, "ground": box.bottom})
        config.get("fallback", {}).get("classes", {}).pop(unit_id, None)   # свой спрайт вместо временного похожего
        print(f"{unit_id}: {box.width}x{box.height} at {box.topleft}")
    sheets = config.setdefault("sheets", {})
    if human:
        # Рост человека в пикселях этого листа: одинаков для всех листов, нарисованных по эталону.
        sheets[sheet_path.name] = {"human_height": human}
    used = {info.get("sheet") for info in sprites.values()}
    for name in [name for name in sheets if name not in used]:   # листы, с которых больше ничего не взято
        del sheets[name]
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
