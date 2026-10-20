"""Образцы внешности классов UO для генерации спрайтов: арт класса в полный рост и коллажи по листам линеек.

    python tools/uo_class_refs.py              # скачать недостающие и собрать коллажи
    python tools/uo_class_refs.py --force      # скачать все заново

Картинка класса — основной арт персонажа этого класса в полный рост, один человек, без фигурки с карты
(источники в SOURCES: вики Fandom и Miraheze, официальный арт на RPGFan). Где полноростового арта нет,
берётся крупный арт из справки игры (GameHelp) без правой части с фигуркой. Однотонная подложка вокруг
персонажа обрезается. Сохраняется в assets/ref/classes/<id>.png.
Коллаж листа — assets/ref/lineups/uo_NN_ref.png: персонажи листа в ряд одной высоты, над каждым номер его
строки в запросе (docs/requests/lineup_NN.txt). assets/ref в git не попадает.
"""
from __future__ import annotations

import io
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from game.database import Database  # noqa: E402
from tools.make_art_prompts import lineup_sheets  # noqa: E402

OUT = ROOT / "assets" / "ref" / "classes"
SHEETS = ROOT / "assets" / "ref" / "lineups"
HEADERS = {"User-Agent": "Mozilla/5.0 MYUO-research/1.0"}
FANDOM = "https://unicornoverlord.fandom.com/api.php"
MIRAHEZE = "https://unilord.miraheze.org/w/api.php"
RPGFAN = "https://www.rpgfan.com/wp-content/uploads/2024/01/Unicorn-Overlord-Artwork-{}.webp"
GAMEHELP_ART = 0.64         # доля ширины картинки справки, где крупный арт (правее — фигурка с карты)
HEIGHT = 900                # высота персонажа в коллаже
GAP = 40
LABEL = 90                  # полоса с номерами над персонажами

# Класс -> (источник, файл): fandom / miraheze — файл вики, rpgfan — номер и имя арта,
# gamehelp — страница класса на Miraheze (полноростового арта нет), none — арта класса нет
# (именованные боссы: внешность берётся из спрайтов модели игры).
SOURCES = {
    "arbalist": ("fandom", "Unicorn-Overlord-Arbalist.png"),
    "berserker": ("fandom", "Berserker.png"),
    "bishop": ("fandom", "Bishop.png"),
    "black_prince": ("none", "Black Prince"),
    "black_prince_hg": ("none", "Black Prince (HG)"),
    "breaker": ("fandom", "Breaker.png"),
    "cleric": ("fandom", "Sharon.png"),
    "crusader": ("fandom", "Virginia.jpg"),
    "dark_knight": ("gamehelp", "Dark Knight"),
    "dark_marquess_a": ("none", "Dark Marquess (A)"),
    "dark_marquess_l": ("none", "Dark Marquess (L)"),
    "dark_marquess_r": ("none", "Dark Marquess (R)"),
    "dark_marquess_s": ("none", "Dark Marquess (S)"),
    "doom_knight": ("fandom", "Doom Knight png.png"),
    "dreadnought": ("fandom", "Amalia_fullbody.jpg"),
    "druid": ("fandom", "Druid.png"),
    "eltlinde": ("none", "Eltlinde"),
    "elven_archer": ("miraheze", "Galadmir_Portrait.png"),
    "elven_augur": ("rpgfan", "014-Rosalinde"),
    "elven_fencer": ("fandom", "Unicorn-Overlord-Elven_Fencer.webp"),
    "elven_sibyl": ("rpgfan", "012-Eltolinde"),
    "feather_bow": ("none", "Feather Bow"),
    "feather_rod": ("none", "Feather Rod"),
    "feather_shield": ("none", "Feather Shield"),
    "feathersword": ("fandom", "Unicorn-Overlord-Feathersword.png"),
    "fighter": ("fandom", "Fighter.png"),
    "gladiator": ("fandom", "Gladiator.png"),
    "great_knight": ("fandom", "Great Knight.png"),
    "gryphon_knight": ("fandom", "Unicorn-Overlord-Gryphon Knight.png"),
    "gryphon_master": ("fandom", "Gryphon Master.png"),
    "high_lord": ("fandom", "High Lord.png"),
    "high_priestess": ("fandom", "High priestess.png"),
    "hoplite": ("fandom", "Hodrick.png"),
    "housecarl": ("fandom", "Unicorn-Overlord-Housecarl.png"),
    "hunter": ("fandom", "Unicorn-Overlord-Hunter.png"),
    "knight": ("fandom", "Knight.png"),
    "landsknecht": ("fandom", "Landsknecht.png"),
    "legionnaire": ("fandom", "Legionnaire.png"),
    "lord": ("fandom", "Lord.png"),
    "necromancer": ("none", "Necromancer"),
    "paladin": ("fandom", "Paladin.png"),
    "priestess": ("fandom", "Scarlett.png"),
    "prince": ("gamehelp", "Prince"),
    "radiant_knight": ("fandom", "Radiant Knight.png"),
    "rogue": ("fandom", "Rogue.png"),
    "sainted_knight": ("fandom", "Sainted knight.png"),
    "sellsword": ("fandom", "Berenice.png"),
    "sergeant": ("fandom", "Gailey.png"),
    "shaman": ("fandom", "Selvie.png"),
    "shieldshooter": ("fandom", "Shieldshooter.png"),
    "sniper": ("fandom", "Sniper.png"),
    "snow_ranger": ("fandom", "Yunifi.webp"),
    "soldier": ("fandom", "SoldierM.png"),
    "sorceress": ("fandom", "Sorceress.png"),
    "sword_master": ("fandom", "Swordmaster.png"),
    "swordfighter": ("fandom", "Swordfighter.png"),
    "thief": ("fandom", "Travis.png"),
    "unify": ("none", "Unify"),
    "valkyria": ("fandom", "Valkyria.png"),
    "vanguard": ("fandom", "Vanguard.png"),
    "viking": ("fandom", "Viking.png"),
    "warlock": ("fandom", "Warlock.png"),
    "warrior": ("fandom", "Warrior.png"),
    "werebear": ("gamehelp", "Werebear"),
    "werefox": ("fandom", "Dinah.png"),
    "werelion": ("fandom", "Werelion.png"),
    "wereowl": ("fandom", "Ramona.webp"),
    "werewolf": ("fandom", "Unicorn-Overlord-Werewolf.webp"),
    "witch": ("fandom", "Yahna.png"),
    "wizard": ("fandom", "Auch.png"),
    "wyvern_knight": ("fandom", "Wyvern-knight.jpg"),
    "wyvern_master": ("fandom", "Wyvern-master.png"),
}

# Скриншоты с куском интерфейса игры по краю: какую часть оставить (доли ширины и высоты: лево, верх, право, низ)
CROP = {"doom_knight": (0, 0, 0.92, 1), "hoplite": (0, 0, 0.93, 1), "wyvern_master": (0, 0, 0.97, 1)}


def fetch(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60).read()


def wiki_file(api: str, name: str) -> bytes:
    query = urllib.parse.urlencode({"action": "query", "titles": "File:" + name, "prop": "imageinfo",
                                    "iiprop": "url", "format": "json"})
    page = next(iter(json.loads(fetch(f"{api}?{query}"))["query"]["pages"].values()))
    if "imageinfo" not in page:
        raise LookupError(f"no file {name!r}")
    return fetch(page["imageinfo"][0]["url"])


def picture(source: str, name: str, crop: tuple = (0, 0, 1, 1)):
    """Картинка класса (PIL) из источника; у справки — только левая часть с крупным артом."""
    from PIL import Image
    if source == "rpgfan":
        data = fetch(RPGFAN.format(name))
    elif source == "gamehelp":
        data = wiki_file(MIRAHEZE, f"GameHelp {name}.png")
    else:
        data = wiki_file(FANDOM if source == "fandom" else MIRAHEZE, name)
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    if source == "gamehelp":
        image = image.crop((0, 0, round(image.width * GAMEHELP_ART), image.height))
    w, h = image.size
    image = image.crop((round(crop[0] * w), round(crop[1] * h), round(crop[2] * w), round(crop[3] * h)))
    return trim(image)


def trim(image, tolerance: int = 24):
    """Обрезает однотонную подложку (цвет угла) и прозрачные края; картинку со сценой не трогает."""
    from PIL import ImageChops
    box = image.getchannel("A").getbbox() or (0, 0, *image.size)
    image = image.crop(box)
    rgb = image.convert("RGB")
    corner = rgb.getpixel((0, 0))
    if all(abs(a - b) <= tolerance for a, b in zip(corner, rgb.getpixel((rgb.width - 1, rgb.height - 1)))):
        background = rgb.copy()
        background.paste(corner, (0, 0, *rgb.size))
        diff = ImageChops.difference(rgb, background).convert("L").point(lambda v: 255 if v > tolerance else 0)
        inner = diff.getbbox()
        if inner and (inner[2] - inner[0]) * (inner[3] - inner[1]) < 0.95 * rgb.width * rgb.height:
            pad = 8
            image = image.crop((max(0, inner[0] - pad), max(0, inner[1] - pad),
                                min(image.width, inner[2] + pad), min(image.height, inner[3] + pad)))
    return image


def collage(images: list, first: int):
    """Персонажи в ряд одной высоты на светлом фоне, над каждым номер строки запроса."""
    from PIL import Image, ImageDraw, ImageFont
    scaled = [im.resize((round(im.width * HEIGHT / im.height), HEIGHT), Image.LANCZOS) for im in images]
    width = sum(im.width for im in scaled) + GAP * (len(scaled) + 1)
    sheet = Image.new("RGB", (width, HEIGHT + LABEL + GAP * 2), (236, 232, 222))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=LABEL - 20)
    x = GAP
    for n, image in enumerate(scaled, start=first):
        sheet.paste(image, (x, GAP + LABEL), image)
        label = str(n)
        left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
        cx = x + image.width // 2
        plate = (cx - (right - left) // 2 - 18, GAP - 4, cx + (right - left) // 2 + 18, GAP + LABEL - 12)
        draw.rectangle(plate, fill=(20, 24, 40))
        draw.text((cx, (plate[1] + plate[3]) // 2), label, font=font, fill=(250, 245, 230), anchor="mm")
        x += image.width + GAP
    return sheet


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    from PIL import Image
    db = Database.load()
    missing = []
    for class_id in db.units:
        path = OUT / f"{class_id}.png"
        if path.exists() and "--force" not in argv:
            continue
        if class_id not in SOURCES:
            missing.append(class_id)
            print(f"{class_id}: no source in SOURCES")
            continue
        if SOURCES[class_id][0] == "none":
            print(f"{class_id}: без арта класса (именованный босс, спрайт берётся из модели игры)")
            continue
        try:
            image = picture(*SOURCES[class_id], CROP.get(class_id, (0, 0, 1, 1)))
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save(path)
            print(f"{class_id} <- {SOURCES[class_id][1]} {image.size[0]}x{image.size[1]}")
        except (LookupError, OSError) as error:
            missing.append(class_id)
            print(f"{class_id}: {error}")
        time.sleep(0.3)
    SHEETS.mkdir(parents=True, exist_ok=True)
    for n, group in enumerate(lineup_sheets(db), start=1):
        paths = [OUT / f"{c}.png" for c in group]
        if all(p.exists() for p in paths):
            collage([Image.open(p).convert("RGBA") for p in paths], 1 if n == 1 else 2).save(SHEETS / f"uo_{n:02d}_ref.png")
        else:
            print(f"sheet {n}: some pictures are missing, no collage")
    print(f"{len(db.units) - len(missing)} classes -> {OUT.relative_to(ROOT)}, collages -> {SHEETS.relative_to(ROOT)}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
