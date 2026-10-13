"""Нарезка листа-линейки персонажей на отдельные спрайты с общим масштабом.

Запуск: python tools/cut_lineup.py assets/sprites_src/lineup/lineup_2.png paladin hunter pyromancer cleric rider
        [--reference <id>] [--gap <пустых столбцов между персонажами, по умолчанию 2>]

Лист: персонажи стоят в ряд слева направо на одной линии земли, фон прозрачный.
Персонажи разделяются пустыми столбцами. Каждый сохраняется в assets/units/<id>.png
обрезанным по своим границам, без изменения размера: поэтому всадник остаётся выше
пехотинца ровно во столько раз, во сколько на листе. В assets/units/units.json
записывается рост человека на листе (по первому персонажу, если не задан --reference):
арена масштабирует все спрайты одним коэффициентом от него.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "units"
ALPHA = 24              # пиксель с меньшей непрозрачностью считается фоном
MIN_WIDTH = 40          # более узкие куски (соринки) не считаются персонажами
MIN_GAP = 2             # столько пустых столбцов подряд разделяют персонажей (--gap N)


def column_runs(sheet: pygame.Surface, min_gap: int = MIN_GAP) -> list[tuple[int, int]]:
    """Полосы непустых столбцов [начало, конец) слева направо."""
    w, h = sheet.get_size()
    mask = pygame.mask.from_surface(sheet, ALPHA)
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


def crop(sheet: pygame.Surface, left: int, right: int) -> tuple[pygame.Surface, pygame.Rect]:
    """Персонаж в полосе столбцов: обрезка по непрозрачным пикселям."""
    part = sheet.subsurface(pygame.Rect(left, 0, right - left, sheet.get_height()))
    rect = pygame.mask.from_surface(part, ALPHA).get_bounding_rects()
    box = rect[0].unionall(rect[1:]) if rect else part.get_rect()
    return part.subsurface(box).copy(), box.move(left, 0)


def main(argv: list[str]) -> int:
    reference, min_gap = None, MIN_GAP
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
    runs = column_runs(sheet, min_gap)
    if len(runs) != len(ids):
        print(f"found {len(runs)} characters on the sheet, but {len(ids)} ids given: {runs}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    config_path = OUT / "units.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    sprites = config.setdefault("sprites", {})
    reference = reference or ids[0]
    human = None
    for unit_id, (left, right) in zip(ids, runs):
        image, box = crop(sheet, left, right)
        pygame.image.save(image, str(OUT / f"{unit_id}.png"))
        # Рост на листе: от низа (линия земли) до верха; масштаб общий для всего листа.
        # Остальные ключи спрайта (опорные точки anchors) сохраняются.
        sprites.setdefault(unit_id, {}).update({"sheet": sheet_path.name, "height": box.height, "ground": box.bottom})
        if unit_id == reference:
            human = box.height
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
