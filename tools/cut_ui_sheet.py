"""Нарезка листов интерфейса (assets/ui/sheets/bN_*.png, сетка 5x2) на отдельные картинки assets/ui/<ключ>.png.

Запуск: python tools/cut_ui_sheet.py [номер батча ...] [--force] [--doc docs/uo_art_prompts.md] [--by-order] [--clean] [--solid N] [--gap N]
        python tools/cut_ui_sheet.py --sheet <лист.png> --keys <ключ1>,<ключ2>,... [--force]
Куда класть каждую ячейку, берётся из таблицы батча в docs/ui_prompts.md (колонки «Ячейка» и «Файл»);
батчи 11 и дальше (иконки предметов и навыков, тактика) — в docs/uo_art_prompts.md: без --doc ищутся в обоих.
Элемент — непрозрачные куски листа; кусок относится к ячейке по своему центру, куски одной ячейки
(ободок и символ значка, стрелки метки) собираются вместе. Полупрозрачный ореол вокруг (alpha
меньше HALO) убирается, картинка обрезается по содержимому и сохраняется в своём разрешении:
рамки потом растягиваются по девяти частям (pygame_tower_style.Skin), значки масштабируются.
Существующие файлы без --force не перезаписываются.

Генератор не всегда держит сетку: элементы стоят неравномерно, и середина одного попадает в соседнюю
ячейку. --by-order нумерует элементы по порядку слева направо в каждом из двух рядов (ячейки 1-5 и 6-10),
пропуская пустые места в конце ряда; куски одного элемента (близкие друг к другу) собираются вместе.
--clean сначала убирает фон моделью rembg (birefnet-general, `pip install "rembg[cpu]"`): для листов, где
генератор нарисовал плотный ореол или тёмную подложку, которые склеивают соседние элементы.
--sheet и --keys режут лист без таблицы: ключи по порядку ячеек (пустой ключ — ячейка пропускается),
нумерация по порядку.
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
OPTIONS_WITH_VALUE = ("--doc", "--solid", "--gap", "--sheet", "--keys")
GAP = 24             # --by-order: куски ближе этого (px) — один элемент (--gap N)


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


def cut_by_order(sheet: pygame.Surface, gap: int = GAP, solid: int = SOLID) -> dict[int, pygame.Surface]:
    """Ячейка -> элемент, номер по порядку слева направо в ряду: верхний ряд 1.., нижний 6..
    solid — с какой непрозрачности пиксель считается элементом (выше — если ореол плотный)."""
    alpha = pygame.surfarray.array_alpha(sheet)
    width, height = sheet.get_size()
    solid_mask = alpha > solid
    # Элемент — куски ближе gap пикселей друг к другу (не по рамкам: диагональные копьё и лук рядом)
    grouped, _count = ndimage.label(ndimage.binary_dilation(solid_mask, iterations=max(1, gap // 2)))
    labels = numpy.where(solid_mask, grouped, 0)
    boxes = []
    for index, box in enumerate(ndimage.find_objects(labels), start=1):
        if box is not None and int((labels[box] == index).sum()) >= MIN_PIECE:
            boxes.append([box[0].start, box[1].start, box[0].stop, box[1].stop, [index]])
    rows: dict[int, list] = {0: [], 1: []}
    for box in boxes:
        rows[int((box[1] + box[3]) / 2 * ROWS // height)].append(box)
    numbered = {}
    for row, items in rows.items():
        for k, box in enumerate(sorted(items, key=lambda b: b[0])[:COLS]):
            numbered[row * COLS + k + 1] = box[4]
    keep = numpy.zeros_like(labels)
    for cell, indices in numbered.items():
        keep[numpy.isin(labels, indices)] = cell
    return _parts(sheet, keep)


def clean(sheet: pygame.Surface) -> pygame.Surface:
    """Лист без фона и ореола: элементы выделяет rembg, лист сперва кладётся на чёрное."""
    from PIL import Image
    from rembg import new_session, remove
    raw = pygame.image.tobytes(sheet, "RGBA")
    image = Image.frombytes("RGBA", sheet.get_size(), raw)
    ground = Image.new("RGBA", image.size, (0, 0, 0, 255))
    ground.alpha_composite(image)
    out = remove(ground.convert("RGB"), session=new_session("birefnet-general")).convert("RGBA")
    return pygame.image.frombytes(out.tobytes(), out.size, "RGBA").convert_alpha()


def _parts(sheet: pygame.Surface, cells: numpy.ndarray) -> dict[int, pygame.Surface]:
    """Вырезка элементов по карте ячеек (0 — фон) с мягким краем, без ореола."""
    rgba = pygame.surfarray.pixels3d(sheet).copy()
    alpha = pygame.surfarray.array_alpha(sheet)
    width, height = sheet.get_size()
    result = {}
    for cell in sorted(int(c) for c in numpy.unique(cells) if c):
        near = ndimage.binary_dilation(cells == cell, iterations=3) & (alpha >= HALO)
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


def save_parts(parts: dict[int, pygame.Surface], cells: dict[int, str], force: bool) -> None:
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


def main(argv: list[str]) -> int:
    force = "--force" in argv
    by_order = "--by-order" in argv
    solid = int(argv[argv.index("--solid") + 1]) if "--solid" in argv else SOLID
    gap = int(argv[argv.index("--gap") + 1]) if "--gap" in argv else GAP
    prepare = clean if "--clean" in argv else (lambda image: image)
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    if "--sheet" in argv:
        sheet = prepare(pygame.image.load(argv[argv.index("--sheet") + 1]).convert_alpha())
        keys = argv[argv.index("--keys") + 1].split(",")
        cells = {n: key for n, key in enumerate(keys, start=1) if key}
        save_parts(cut_by_order(sheet, gap, solid), cells, force)
        return 0
    values = {i + 1 for i, a in enumerate(argv) if a in OPTIONS_WITH_VALUE}   # значения опций — не номера батчей
    wanted = {int(a) for i, a in enumerate(argv) if a.isdigit() and i not in values}
    docs = [Path(argv[argv.index("--doc") + 1])] if "--doc" in argv else [PROMPTS, PROMPTS.with_name("uo_art_prompts.md")]
    batches = {}
    for doc in docs:
        if doc.is_file():
            batches.update(batch_files(doc.read_text(encoding="utf-8")))
    for number, (sheet_name, cells) in sorted(batches.items()):
        if wanted and number not in wanted:
            continue
        path = SHEETS / sheet_name
        if not path.is_file():
            print(f"batch {number}: no {path.name}, skipped")
            continue
        image = prepare(pygame.image.load(str(path)).convert_alpha())
        parts = cut_by_order(image, gap, solid) if by_order else cut(image)
        save_parts(parts, cells, force)
        extra = sorted(set(parts) - set(cells))
        if extra:
            print(f"batch {number}: pieces in cells {extra} have no file in the table")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
