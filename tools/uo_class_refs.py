"""Образцы внешности классов UO для генерации спрайтов: картинки с вики и коллажи по листам линеек.

    python tools/uo_class_refs.py              # скачать недостающие и собрать коллажи
    python tools/uo_class_refs.py --force      # скачать все заново

Картинка класса — игровая иллюстрация GameHelp <Класс>.png со страницы класса на unilord.miraheze.org,
сохраняется в assets/ref/classes/<id>.png. Коллаж листа — assets/ref/lineups/uo_NN_ref.png: картинки классов
листа сеткой, на каждой номер её строки в запросе (docs/requests/lineup_NN.txt). assets/ref в git не попадает.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from game.database import Database  # noqa: E402
from tools.make_art_prompts import lineup_sheets  # noqa: E402
from tools.uo_import import slug  # noqa: E402
from tools.uo_wiki import get  # noqa: E402

CLASSES_JSON = ROOT / "docs" / "uo" / "classes.json"
OUT = ROOT / "assets" / "ref" / "classes"
SHEETS = ROOT / "assets" / "ref" / "lineups"
FILE_API = ("https://unilord.miraheze.org/w/api.php?action=query&titles={title}&prop=imageinfo&iiprop=url"
            "&format=json")
HEADERS = {"User-Agent": "MYUO-research/1.0"}
CELL = (704, 392)           # размер картинки справки UO
COLUMNS = 2
LABEL = 64                  # высота цифры номера
GAP = 16


def class_pages() -> dict[str, str]:
    """id класса -> страница вики."""
    return {slug(c["name"]): c["name"] for c in json.loads(CLASSES_JSON.read_text(encoding="utf-8"))["classes"]}


def picture_of(page: str) -> str:
    """Имя файла иллюстрации класса: GameHelp <...>, иначе первая картинка страницы, кроме значков."""
    text = get(page)
    files = re.findall(r"\[\[File:\s*([^\]|]+)", text)
    own = [f for f in files if f.strip().lower().startswith("gamehelp")]
    rest = [f for f in files if not re.search(r"icon|gem|letter|asscon", f, re.I)]
    if not own + rest:
        raise LookupError(f"{page}: no picture on the page")
    return (own + rest)[0].strip()


def download(file_name: str, path: Path) -> None:
    url = FILE_API.format(title=urllib.parse.quote("File:" + file_name))
    info = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30).read())
    page = next(iter(info["query"]["pages"].values()))
    source = page["imageinfo"][0]["url"]
    data = urllib.request.urlopen(urllib.request.Request(source, headers=HEADERS), timeout=60).read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def collage(images: list, first: int):
    """Картинки сеткой по COLUMNS, в углу каждой — номер строки запроса.

    Картинка справки UO: слева крупный арт класса, справа его фигурка на карте целиком — нужны обе."""
    import pygame
    columns = min(COLUMNS, len(images))
    rows = -(-len(images) // columns)
    sheet = pygame.Surface((columns * CELL[0] + (columns + 1) * GAP, rows * CELL[1] + (rows + 1) * GAP))
    sheet.fill((236, 232, 222))
    font = pygame.font.Font(None, LABEL)
    for i, image in enumerate(images):
        x = GAP + (i % columns) * (CELL[0] + GAP)
        y = GAP + (i // columns) * (CELL[1] + GAP)
        sheet.blit(pygame.transform.smoothscale(image, CELL), (x, y))
        label = font.render(str(first + i), True, (250, 245, 230))
        plate = pygame.Rect(x, y, label.get_width() + 24, label.get_height() + 10)
        pygame.draw.rect(sheet, (20, 24, 40), plate)
        sheet.blit(label, label.get_rect(center=plate.center))
    return sheet


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    import pygame
    pygame.init()
    pygame.display.set_mode((1, 1))
    db = Database.load()
    pages = class_pages()
    missing = []
    for class_id in db.units:
        path = OUT / f"{class_id}.png"
        if path.exists() and "--force" not in argv:
            continue
        try:
            download(picture_of(pages[class_id]), path)
            print(f"{class_id} <- {pages[class_id]}")
        except (KeyError, LookupError, OSError) as error:
            missing.append(class_id)
            print(f"{class_id}: {error}")
        time.sleep(0.3)
    SHEETS.mkdir(parents=True, exist_ok=True)
    for n, group in enumerate(lineup_sheets(db), start=1):
        images = [pygame.image.load(str(OUT / f"{c}.png")).convert_alpha() for c in group if (OUT / f"{c}.png").exists()]
        if len(images) == len(group):
            pygame.image.save(collage(images, 1 if n == 1 else 2), str(SHEETS / f"uo_{n:02d}_ref.png"))
        else:
            print(f"sheet {n}: some pictures are missing, no collage")
    print(f"{len(db.units) - len(missing)} classes -> {OUT.relative_to(ROOT)}, collages -> {SHEETS.relative_to(ROOT)}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
