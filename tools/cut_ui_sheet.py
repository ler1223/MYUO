"""Нарезка листов интерфейса (assets/ui/sheets/bN_*.png, сетка 5x2) на отдельные картинки assets/ui/<ключ>.png.

Запуск: python tools/cut_ui_sheet.py [номер батча ...] [--force]
Куда класть каждую ячейку, берётся из таблицы батча в docs/ui_prompts.md (колонки «Ячейка» и «Файл»).
Элемент — непрозрачные куски листа; кусок относится к ячейке по своему центру, куски одной ячейки
(ободок и символ значка, стрелки метки) собираются вместе. Полупрозрачный ореол вокруг (alpha
меньше HALO) убирается, картинка обрезается по содержимому и сохраняется в своём разрешении:
рамки потом растягиваются по девяти частям (pygame_tower_style.Skin), значки масштабируются.
Существующие файлы без --force не перезаписываются.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import numpy  # noqa: E402
import pygame  # noqa: E402
from scipy import ndimage  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "docs" / "ui_prompts.md"
SHEETS = ROOT / "assets" / "ui" / "sheets"
UI_DIR = ROOT / "assets" / "ui"
COLS, ROWS = 5, 2
SOLID = 128          # кусок элемента: alpha выше этого
HALO = 24            # ореол: alpha ниже этого становится полностью прозрачным
MIN_PIECE = 40       # куски меньше (в пикселях) — пыль генератора
PAD = 2


def batch_files(text: str) -> dict[int, tuple[str, dict[int, str]]]:
    """Номер батча -> (имя листа, ячейка -> ключ файла без .png)."""
    result = {}
    heads = [(m.start(), m.group(1)) for m in re.finditer(r"^## (.+)$", text, re.M)]
    for i, (pos, title) in enumerate(heads):
        found = re.match(r"Батч (\d+) .*`([^`]+\.png)`", title)
        if not found:
            continue
        end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
        cells = {int(n): f[:-4] for n, f in re.findall(r"^\| (\d+) \| `([^`]+\.png)`", text[pos:end], re.M)}
        result[int(found.group(1))] = (found.group(2), cells)
    return result


def cut(sheet: pygame.Surface) -> dict[int, pygame.Surface]:
    """Ячейка (1..10) -> вырезанный элемент с прозрачным фоном."""
    rgba = pygame.surfarray.pixels3d(sheet).copy()
    alpha = pygame.surfarray.array_alpha(sheet)
    width, height = sheet.get_size()
    labels, count = ndimage.label(alpha > SOLID)
    pieces: dict[int, list[int]] = {}
    for index, box in enumerate(ndimage.find_objects(labels), start=1):
        if box is None:
            continue
        size = int((labels[box] == index).sum())
        if size < MIN_PIECE:
            continue
        cx = (box[0].start + box[0].stop) / 2
        cy = (box[1].start + box[1].stop) / 2
        cell = int(cy * ROWS // height) * COLS + int(cx * COLS // width) + 1
        pieces.setdefault(cell, []).append(index)
    result = {}
    for cell, indices in pieces.items():
        mask = numpy.isin(labels, indices)
        # Вокруг кусков берём и их мягкий край, но не ореол
        near = ndimage.binary_dilation(mask, iterations=3) & (alpha >= HALO)
        xs, ys = numpy.nonzero(near)
        x0, x1 = max(0, xs.min() - PAD), min(width, xs.max() + 1 + PAD)
        y0, y1 = max(0, ys.min() - PAD), min(height, ys.max() + 1 + PAD)
        part = pygame.Surface((x1 - x0, y1 - y0), pygame.SRCALPHA)
        pygame.surfarray.blit_array(part, rgba[x0:x1, y0:y1])
        part_alpha = pygame.surfarray.pixels_alpha(part)
        part_alpha[:] = numpy.where(near[x0:x1, y0:y1], alpha[x0:x1, y0:y1], 0)
        del part_alpha
        result[cell] = part
    return result


def main(argv: list[str]) -> int:
    force = "--force" in argv
    wanted = {int(a) for a in argv if a.isdigit()}
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    batches = batch_files(PROMPTS.read_text(encoding="utf-8"))
    for number, (sheet_name, cells) in sorted(batches.items()):
        if wanted and number not in wanted:
            continue
        path = SHEETS / sheet_name
        if not path.is_file():
            print(f"batch {number}: no {path.name}, skipped")
            continue
        parts = cut(pygame.image.load(str(path)).convert_alpha())
        for cell, key in sorted(cells.items()):
            out = UI_DIR / f"{key}.png"
            if cell not in parts:
                print(f"  {key}: cell {cell} is empty on the sheet")
                continue
            if out.exists() and not force:
                print(f"  {key}: exists, kept")
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(parts[cell], str(out))
            print(f"  {key}: {parts[cell].get_width()}x{parts[cell].get_height()}")
        extra = sorted(set(parts) - set(cells))
        if extra:
            print(f"batch {number}: pieces in cells {extra} have no file in the table")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
