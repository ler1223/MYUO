"""Временные спрайты классов из референсов: персонаж вырезается из assets/ref/classes и идёт в игру.

    python tools/ref_sprites.py              # вырезать недостающие
    python tools/ref_sprites.py --force      # заново все
    python tools/ref_sprites.py knight lord  # только эти

Фон убирает rembg (модель MODEL, при первом запуске скачивается), затем остаётся самый большой
кусок фигуры с ближними к нему частями (оружие), края обрезаются. Кто на арте смотрит влево (FACE_LEFT),
получает flip в units.json — игра отражает его при загрузке; рост и разворот обновляются запуском без
перенарезки (уже вырезанные пропускаются). Результат — assets/ref/sprites/<id>.png и units.json с ростом:
рост спрайта в ростах человека — из HEIGHT tools/make_art_prompts.py (конница, летуны, крупные звери).
SpriteBank (pygame_stage.py) берёт эти спрайты вместо временных старых old_*, но не вместо своих
нарезанных с линеек. Папка assets/ref в git не попадает: чтобы убрать временные спрайты, удалите
assets/ref/sprites.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.make_art_prompts import HEIGHT  # noqa: E402

SOURCE = ROOT / "assets" / "ref" / "classes"
OUT = ROOT / "assets" / "ref" / "sprites"
MAX_HEIGHT = 640            # высота готового спрайта, px
ALPHA = 40                  # непрозрачность, с которой пиксель считается фигурой
KEEP = 0.04                 # куски меньше этой доли самого большого — мусор фона
MODEL = "birefnet-general"     # лучше прочих режет персонажей со скриншотов боя (без пола и полупрозрачности)
SKIP = {"dark_knight", "werebear", "prince"}   # в референсе только крупный план, не фигура целиком
# Кто на арте смотрит влево (в бою UO отряд игрока справа): игра отражает их при загрузке (flip в units.json)
FACE_LEFT = {"arbalist", "berserker", "breaker", "cleric", "druid", "elven_archer", "elven_augur", "elven_sibyl",
             "feathersword", "fighter", "great_knight", "high_lord", "high_priestess", "knight", "landsknecht",
             "lord", "paladin", "priestess", "radiant_knight", "sainted_knight", "sergeant", "shaman", "sniper",
             "snow_ranger", "soldier", "sorceress", "swordfighter", "thief", "werelion", "witch", "wyvern_master"}


def cut(image, session):
    """Фигура без фона: альфа от rembg, мелкие куски фона убраны, края обрезаны."""
    import numpy
    from rembg import remove
    from scipy import ndimage
    from PIL import Image
    out = remove(image.convert("RGB"), session=session)
    rgba = numpy.array(out)
    mask = rgba[..., 3] > ALPHA
    labels, count = ndimage.label(mask)
    if count:
        sizes = ndimage.sum(mask, labels, range(1, count + 1))
        keep = [i + 1 for i, s in enumerate(sizes) if s >= sizes.max() * KEEP]
        rgba[..., 3] = numpy.where(numpy.isin(labels, keep), rgba[..., 3], 0)
    result = Image.fromarray(rgba)
    box = result.getchannel("A").point(lambda v: 255 if v > ALPHA else 0).getbbox()
    return result.crop(box) if box else result


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    from PIL import Image
    wanted = [a for a in argv if not a.startswith("--")]
    session = None
    OUT.mkdir(parents=True, exist_ok=True)
    index_path = OUT / "units.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    sprites = index.setdefault("sprites", {})
    for path in sorted(SOURCE.glob("*.png")):
        class_id = path.stem
        if class_id in SKIP or (wanted and class_id not in wanted):
            continue
        target = OUT / f"{class_id}.png"
        if target.exists() and "--force" not in argv and not wanted and class_id in sprites:
            continue
        if session is None:
            from rembg import new_session
            session = new_session(MODEL)
        sprite = cut(Image.open(path), session)
        if sprite.height > MAX_HEIGHT:
            sprite = sprite.resize((round(sprite.width * MAX_HEIGHT / sprite.height), MAX_HEIGHT), Image.LANCZOS)
        sprite.save(target)
        sprites[class_id] = {"height": sprite.height}
        print(f"{class_id}: {sprite.width}x{sprite.height}")
    for class_id, info in sprites.items():                  # рост и разворот можно менять без перенарезки
        info["ratio"] = HEIGHT.get(class_id, 100) / 100
        info["flip"] = class_id in FACE_LEFT
    index["_comment"] = ("Временные спрайты из референсов (tools/ref_sprites.py): height — высота картинки, "
                         "ratio — рост в ростах человека, flip — отразить (на арте смотрит влево). Удалите папку, чтобы вернуть старые спрайты.")
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(sprites)} sprites -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
