"""Промпты картинок для классов, навыков и предметов UO -> docs/uo_art_prompts.md (сами запросы не делаются).

    python tools/make_art_prompts.py

Собирается из справочника data/: спрайты всех классов — листами-линейками (режет tools/cut_lineup.py),
элементы экрана бойца и тактики, значки типов навыков и иконки видов предметов — листами 5x2
(режет tools/cut_ui_sheet.py, номера батчей с 11). Как в UO, своей картинки у навыка и предмета нет:
значок общий на тип навыка (game.skill_kinds), иконка — на вид предмета (слот).
Перегенерируйте после изменения справочника: список листов и файлов меняется вместе с ним.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from game.database import Database  # noqa: E402

OUT = ROOT / "docs" / "uo_art_prompts.md"
NAMES_JSON = ROOT / "data" / "names.json"
FIRST_BATCH = 11
ANCHOR = "fighter"          # первый персонаж первого листа — эталон роста для всех остальных листов
SHEET_WIDTH = 4.0           # сколько «пехотинцев» помещается на лист после эталона
WIDTH = {"cavalry": 1.8, "flying": 2.0}   # ширина всадника и летуна в пехотинцах

CHARACTER_STYLE = """STYLE: hand-painted 2D fantasy character art in the spirit of the battle sprites of Vanillaware's
Unicorn Overlord (do not copy any existing character): rich painterly shading with soft light from the upper
left, clean dark contour lines, deep saturated but never neon colors, detailed cloth folds and metal highlights,
heroic realistic proportions about 7 heads tall, faces and silhouettes readable at small size. Every character
in one consistent style, palette and lighting, like one cast of the same game."""
LINEUP_RULES = """SCALE RULES: everything at exactly the same scale, as if photographed together. A normal adult human
is <HUMAN>. Heights of the others are given in their lines relative to a human (no note = human height; a
weapon, hat or ears may rise above the head). All feet touch the same ground line near the bottom edge;
flying units hover just above it. No character is enlarged or shrunk to fill its slot.

POSE: all face right, side view with a slight three-quarter turn toward the viewer, calm combat-ready
stance, weapons held close to the body. Mounts and wings fully visible, not cut by the image edge."""
LINEUP_OUTPUT = "OUTPUT: transparent background PNG, no ground, no shadow, no scenery, no text, no labels."
FIRST_LINEUP = f"""Draw a horizontal lineup sheet of full-body unit sprites for a high-fantasy tactics RPG, standing
in one row on the same flat ground line, evenly spaced with clear empty space between them, nothing
overlapping or cropped. This sheet sets the scale and style for all later sheets of the same cast.
If screenshots are attached, use them only as a style reference and do not copy any character.

{LINEUP_RULES.replace("<HUMAN>", "as tall as the first character, about 40% of the image height")}

FROM LEFT TO RIGHT:
<персонажи>

{CHARACTER_STYLE}

{LINEUP_OUTPUT}"""
NEXT_LINEUP = f"""Using the attached lineup sheet as the scale and style reference, draw a new horizontal lineup sheet of
full-body unit sprites of the same cast, standing in one row on the same flat ground line, evenly spaced with
clear empty space between them, nothing overlapping or cropped. Far left: the Fighter from the reference
(the first character there), unchanged and at exactly the same size.

{LINEUP_RULES.replace("<HUMAN>", "as tall as that Fighter")}

FROM LEFT TO RIGHT:
1. The Fighter from the reference (unchanged).
<персонажи>

{CHARACTER_STYLE}

{LINEUP_OUTPUT}"""

# Внешность классов (английский — для генератора): одна строка, рост относительно человека
LOOK = {
    "fighter": "Fighter: steel plate armor over blue tabard, sallet helmet, arming sword and kite shield, sturdy defensive stance",
    "vanguard": "Vanguard: heavier ornate plate with gold trim and a short blue cape, great kite shield, longsword, veteran bulwark",
    "soldier": "Soldier: padded gambeson and kettle hat, simple spear held upright, light infantry",
    "sergeant": "Sergeant: brigandine with rank sash, plumed kettle hat, long spear, commanding pose",
    "housecarl": "Housecarl: Nordic mail and fur mantle, bearded axe, round helmet with nasal, broad build",
    "viking": "Viking: heavier mail with fur and braided beard, round shield on the back, large bearded axe",
    "swordfighter": "Swordfighter: light coat over a tunic, katana-like curved sword held low, nimble duelist",
    "sword_master": "Sword Master: long flowing coat, two-handed curved sword, calm master's stance",
    "sellsword": "Sellsword: mismatched mercenary armor, huge zweihander on the shoulder",
    "landsknecht": "Landsknecht: slashed puffed doublet and plumed beret, massive zweihander, half-plate",
    "hoplite": "Hoplite: full plate, crested great helm, huge tower greatshield and short spear, immovable wall",
    "legionnaire": "Legionnaire: gilded heavy plate, crimson crest, tower greatshield with emblem, spear",
    "gladiator": "Gladiator: bare muscular torso with leather straps, single shoulder guard, big axe",
    "berserker": "Berserker: wild hair, war paint, fur loincloth and chains, enormous double-bit axe, about 110% human height",
    "warrior": "Warrior: heavy armor with spiked pauldrons, great maul-axe, armor breaker",
    "breaker": "Breaker: huge spiked plate armor, giant war hammer-axe resting on the shoulder, about 110% human height",
    "hunter": "Hunter: green hooded cloak, leather armor, recurve bow and arrow nocked, quiver",
    "sniper": "Sniper: dark green long coat, feathered hat, long elegant bow, cold focused gaze",
    "arbalist": "Arbalist: brigandine and padded cap, heavy crossbow (arbalest) held at the hip",
    "shieldshooter": "Shieldshooter: heavy plate, crossbow mounted on a large greatshield, armored marksman",
    "thief": "Thief: dark hood and scarf, short cape, light short sword, crouched sneaky stance",
    "rogue": "Rogue: black leather with red sash, two short swords, smirking agile stance",
    "knight": "Knight (cavalry): knight in blue and silver plate on an armored warhorse, lance and shield; rider and horse together about 180% of human height",
    "great_knight": "Great Knight (cavalry): heavy gilded plate on a barded warhorse with caparison, long lance and shield; about 190% human height",
    "radiant_knight": "Radiant Knight (cavalry): white and gold armor on a white horse, sword and holy shield, healer knight; about 180% human height",
    "sainted_knight": "Sainted Knight (cavalry): radiant white plate with halo-like crest on a white barded horse, lance; about 190% human height",
    "dark_knight": "Dark Knight (cavalry): black spiked armor on a black horse with red eyes, great axe and dark shield; about 180% human height",
    "doom_knight": "Doom Knight (cavalry): massive black and crimson armor on an armored nightmare horse, huge axe; about 190% human height",
    "cleric": "Cleric: white and blue priest robes, hood, simple staff with a holy symbol",
    "bishop": "Bishop: ornate white and gold vestments with tall mitre, crosier staff",
    "wizard": "Wizard: deep blue robe, pointed wide hat, staff with a fire-red orb",
    "warlock": "Warlock: black and violet robes with high collar, staff with a dark crystal, sinister",
    "witch": "Witch: dark purple dress and tattered hooded cloak, crooked staff with a green glowing charm",
    "sorceress": "Sorceress: elegant black and gold gown, tall collar, staff topped with a crescent moon",
    "shaman": "Shaman: tribal layered robes with feathers and bones, gnarled wooden staff with charms",
    "druid": "Druid: green and brown robes with leaves and antler circlet, living-wood staff",
    "wyvern_knight": "Wyvern Knight (flying): armored rider on a small green wyvern with spread wings, spear; about 200% human height, hovering slightly above ground",
    "wyvern_master": "Wyvern Master (flying): heavy armored rider on a large red wyvern, long spear; about 220% human height",
    "gryphon_knight": "Gryphon Knight (flying): light armored rider on a brown gryphon with spread wings, axe; about 200% human height",
    "gryphon_master": "Gryphon Master (flying): rider in ornate armor on a white gryphon, big axe; about 220% human height",
    "lord": "Lord: young noble prince in blue and silver armor with short cape, longsword and heater shield with a unicorn crest",
    "high_lord": "High Lord (cavalry): noble in gleaming royal armor on a white warhorse, sword and unicorn shield; about 180% human height",
    "priestess": "Priestess: white and gold temple dress, long veil, ornate staff with a crystal",
    "high_priestess": "High Priestess: majestic white gown with gold halo crown, tall ornate staff",
    "crusader": "Crusader: white tabard with red cross over plate, sword and two shields (one on the arm, one on the back)",
    "valkyria": "Valkyria: winged helmet, silver plate with feather motifs, sword and round shield, female warrior",
    "paladin": "Paladin (cavalry): white and gold plate on a white barded horse, sword and shield; about 180% human height",
    "prince": "Prince: regal young prince in a red and gold coat, rapier-like sword, no armor",
    "dreadnought": "Dreadnought: colossal plate armor, enormous tower greatshield and broad sword; about 115% human height",
    "snow_ranger": "Snow Ranger: white fur cloak and hood, white longbow, snowy ranger",
    "elven_fencer": "Elven Fencer: elf with long ears, green and white elegant tunic, slender rapier, spellblade",
    "elven_archer": "Elven Archer: elf in leaf-green leathers, ornate elven longbow",
    "elven_augur": "Elven Augur: elf mystic in white and teal robes, ornate spear used as a staff",
    "elven_sibyl": "Elven Sibyl: elf seer in flowing white robes with gold leaves, crystal-tipped spear-staff",
    "werewolf": "Werewolf: wolf-headed beastman warrior in light armor, curved sword, digitigrade legs",
    "werefox": "Werefox: fox-headed beastwoman in light leather, spear, nimble",
    "werebear": "Werebear: huge bear-headed beastman in heavy armor, greatshield and axe; about 125% human height",
    "wereowl": "Wereowl (flying): owl-winged beastwoman mage with feathered cloak, staff; wings spread",
    "werelion": "Werelion: lion-headed beastman with a mane, bare chest and gold armor pieces, huge axe; about 115% human height",
    "feathersword": "Feathersword (flying): angelic knight with white feathered wings, sword and shield",
}
# Значки типов навыков (game.skill_kinds): символ типа; активные и пассивные различаются цветом
SKILL_SYMBOLS = {
    "attack": "two crossed swords",
    "support": "a heater shield with a rising chevron arrow above it",
    "healing": "a cupped pair of hands holding a small glowing leaf-shaped light",
    "sabotage": "a cracked shield with a downward chevron arrow below it",
}
SKILL_FIELDS = {
    "skill": "warm antique gold symbol on a deep crimson round field (#7a1f24)",
    "passive": "pale silver-blue symbol on a deep navy round field (#1b2a55)",
}
# Иконки видов предметов (слоты data/config.json): одна на вид, рамку цвета тира рисует интерфейс
ITEM_LOOKS = {
    "light_sword": "a plain steel one-handed arming sword, blade pointing to the upper right",
    "heavy_weapon": "a heavy two-handed bearded war axe, head at the upper right",
    "lance": "a long cavalry spear with a leaf-shaped steel head, diagonal",
    "bow": "a wooden recurve bow with its string, held diagonally",
    "staff": "a mage's wooden staff topped with a small glowing blue crystal, diagonal",
    "light_shield": "a round-topped heater shield with a simple gold border",
    "greatshield": "a large rectangular tower greatshield with iron rivets",
    "artifact": "a gold ring with a small blue gem",
}


def gender(db: Database) -> dict[str, str]:
    female = set(json.loads(NAMES_JSON.read_text(encoding="utf-8")).get("female_classes", ()))
    return {c: "female" if c in female else "male" for c in db.units}


def look_line(class_id: str, sex: str) -> str:
    """«Knight (cavalry), female: ...»: пол после названия — тот же, что у имён бойцов этого класса."""
    head, rest = LOOK[class_id].split(":", 1)
    return f"{head}, {sex}:{rest}."


def families(db: Database) -> list[list[str]]:
    """Семьи классов: базовый, затем его повышения; первой — семья эталона ANCHOR."""
    seen: set[str] = set()
    result = []

    def walk(class_id: str, family: list[str]) -> None:
        if class_id in seen or class_id not in LOOK:
            return
        seen.add(class_id)
        family.append(class_id)
        for promotion in db.units[class_id].promotions:
            walk(promotion.class_id, family)

    for class_id in [ANCHOR, *(c for c in db.units if not db.parents(c)), *db.units]:
        family: list[str] = []
        walk(class_id, family)
        if family:
            result.append(family)
    return result


def width(db: Database, class_id: str) -> float:
    tags = db.units[class_id].tags
    return max((w for tag, w in WIDTH.items() if tag in tags), default=1.0)


def lineup_sheets(db: Database) -> list[list[str]]:
    """Семьи целиком на первый лист, где хватает места (семья шире листа делится). На первом листе эталон —
    сам первый персонаж, на остальных он ещё и занимает место слева, поэтому первый лист на одного шире."""
    sheets: list[list[str]] = []
    used: list[float] = []

    def room(index: int) -> float:
        return SHEET_WIDTH + (1 if index == 0 else 0) - used[index]

    for family in families(db):
        parts, part, size = [], [], 0.0               # семья, разрезанная по ширине листа
        for class_id in family:
            w = width(db, class_id)
            if part and size + w > SHEET_WIDTH:
                parts.append((part, size))
                part, size = [], 0.0
            part.append(class_id)
            size += w
        parts.append((part, size))
        for part, size in parts:
            index = next((i for i in range(len(sheets)) if room(i) >= size), None)
            if index is None:
                sheets.append([])
                used.append(0.0)
                index = len(sheets) - 1
            sheets[index] += part
            used[index] += size
    return sheets


def cell_table(rows: list[tuple[int, str, str]]) -> list[str]:
    return ["| Ячейка | Файл | Итог |", "| --- | --- | --- |", *(f"| {k} | `{f}` | {s} |" for k, f, s in rows), ""]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    db = Database.load()
    out = ["# Промпты картинок: классы, навыки и предметы Unicorn Overlord",
           "",
           "Собрано `python tools/make_art_prompts.py` из справочника — перегенерируйте после его изменений. "
           "Промпты на английском. Запросы скрипт не делает: готовые тексты целиком — в `docs/requests/` "
           "(`python tools/build_requests.py`).",
           "",
           "## Как пользоваться", "",
           "1. Листы с сеткой 5x2 (1536x1024, прозрачный фон): в начало запроса — блоки **STYLE** и **SHEET** из "
           "`docs/ui_prompts.md`, затем ячейки батча. Первой строкой — `Match the art direction of the attached "
           "screenshots, but do not copy any text, logo or exact artwork.` и 1-2 скриншота UO.",
           "2. Готовый лист — в `assets/ui/sheets/` под именем батча и нарезка: "
           "`python tools/cut_ui_sheet.py <номер> --force` (батчи 11+ ищутся в этом файле).",
           "3. Спрайты классов — листы-линейки (раздел 1): общий промпт листа ниже плюс строки персонажей; лист — в "
           "`assets/sprites_src/lineup/` и `python tools/cut_lineup.py ...` (команда у каждого листа). Первый лист "
           "задаёт рост и стиль: его Fighter — эталон, готовый `uo_01.png` прикладывается ко всем следующим листам. "
           "Свой спрайт сразу заменяет временный похожий (прежние спрайты — `assets/units/old_*`).",
           "4. Как в UO, у навыка и предмета нет своей картинки: значок — на тип навыка (атака, поддержка, лечение, "
           "помеха; активный или пассивный), иконка — на вид предмета. Тип навыка выводится из самого навыка "
           "(`game/skill_kinds.py`). Если всё же нужен свой значок, достаточно положить `skill/<тип>/<id>.png` "
           "или `item/<слот>/<id>.png`.",
           ""]
    batch = FIRST_BATCH
    totals = {}

    # 1. Спрайты классов
    sexes = gender(db)
    sheets = lineup_sheets(db)
    count = sum(len(s) for s in sheets)
    out += ["## 1. Спрайты классов — листы-линейки", "",
            f"Все {count} классов заново, семьями (базовый класс и его повышения рядом): {len(sheets)} листов. "
            "Конница и летуны шире — их на листе меньше; рост выше человека указан в строке. Пол — тот же, что "
            "у имён бойцов класса (`female_classes` в `data/names.json`).", "",
            "## Линейка: первый лист", "", "Приложить по желанию 1-2 скриншота боя UO — только как образец стиля.",
            "", "```", FIRST_LINEUP, "```", "",
            "## Линейка: остальные листы", "", "Приложить готовый `assets/sprites_src/lineup/uo_01.png`.",
            "", "```", NEXT_LINEUP, "```", "",
            "## Листы линеек", ""]
    for n, group in enumerate(sheets, start=1):
        name = f"uo_{n:02d}.png"
        first = 1 if n == 1 else 2
        who = " ".join(group) if n == 1 else "_ref " + " ".join(group)
        reference = ANCHOR if n == 1 else "_ref"
        out += [f"**Лист {n}** (`assets/sprites_src/lineup/{name}`): "
                f"`python tools/cut_lineup.py assets/sprites_src/lineup/{name} {who} --reference {reference}`",
                "", "```"]
        out += [f"{k}. {look_line(c, sexes[c])}" for k, c in enumerate(group, start=first)]
        out += ["```", ""]
    totals["спрайты классов"] = len(sheets)

    # 2. Экран бойца и тактика
    out += [f"## Батч {batch} — экран бойца и тактика (`b{batch}_unit.png`)", "", "```", "<STYLE>", "<SHEET>",
            "Cell 1: FRAME, tactic skill bar for skills paid with AP, 300x70: deep crimson fill (#7a1f24), thin gold "
            "border with small arrow-shaped right end like a banner, border band 20 px.",
            "Cell 2: FRAME, the same tactic skill bar for skills paid with PP: deep blue fill (#1d4f8a).",
            "Cell 3: FRAME, tactic condition bar, 300x70: muted olive-gold fill (#5c5230), thin gold border, small "
            "chevron ends, border band 20 px.",
            "Cell 4: priority number plate, 100x80: slanted parallelogram plate in dark crimson with a gold edge, "
            "empty center for a number.",
            "Cell 5: grade letter frame, 80x80: small square plate with cut corners, dark navy fill, thin gold border.",
            "Cell 6: FRAME, dropdown option list window, 260x300: very dark navy, thin gold border, tiny corner "
            "diamonds, border band 20 px.",
            "Cell 7: small square button icon, 90x90: gold upward triangle on a dark navy square with a gold edge.",
            "Cell 8: the same button icon with a downward triangle.",
            "Cell 9: the same button icon with a thin gold X (remove).",
            "Cell 10: unit pedestal, 300x120: low round stone dais seen from the front at a slight top-down angle, "
            "carved edge with gold inlay, like the formation board of Unicorn Overlord.",
            "```", "",
            *cell_table([(1, "frame/tactic_ap.png", "512x128"), (2, "frame/tactic_pp.png", "512x128"),
                         (3, "frame/tactic_condition.png", "512x128"), (4, "frame/priority.png", "160x128"),
                         (5, "frame/grade.png", "96x96"), (6, "frame/picker.png", "384x448"),
                         (7, "icon/up.png", "96x96"), (8, "icon/down.png", "96x96"), (9, "icon/remove.png", "96x96"),
                         (10, "field/pedestal.png", "512x192")])]
    batch += 1
    totals["экран бойца"] = 1

    # 3. Значки типов навыков
    out += [f"## Батч {batch} — значки типов навыков (`b{batch}_skills.png`)", "",
            "Круглый значок внутри кольца (кольцо рисует интерфейс). Верхний ряд — активные навыки (AP), нижний — "
            "пассивные (PP): тот же символ, другой цвет. Ячейки 5 и 10 пустые.", "",
            "```", "<STYLE>", "<SHEET>"]
    rows = []
    for row, (kind, field) in enumerate(SKILL_FIELDS.items()):
        what = "active skill" if kind == "skill" else "passive skill"
        for k, (skill_type, symbol) in enumerate(SKILL_SYMBOLS.items(), start=1 + row * 5):
            out.append(f"Cell {k}: round {what} type icon \"{skill_type}\", 200x200: {symbol}; {field}. "
                       "A single bold symbol, no ring, no text.")
            rows.append((k, f"{kind}/{skill_type}.png", "256x256"))
    out += ["Cells 5 and 10: leave empty.", "```", "", *cell_table(rows)]
    batch += 1
    totals["значки навыков"] = 1

    # 4. Иконки видов предметов
    out += [f"## Батч {batch} — иконки видов предметов (`b{batch}_items.png`)", "",
            "Одна иконка на вид предмета: лёгкий поворот три четверти, чистый силуэт, без рамки и фона "
            "(рамку цвета тира рисует интерфейс). Ячейки 9 и 10 пустые.", "",
            "```", "<STYLE>", "<SHEET>"]
    rows = []
    for k, (slot, look) in enumerate(ITEM_LOOKS.items(), start=1):
        out.append(f"Cell {k}: inventory icon, 200x200: {look}. Single object, slight three-quarter view, "
                   "no frame, no background.")
        rows.append((k, f"item/{slot}.png", "256x256"))
    out += ["Cells 9 and 10: leave empty.", "```", "", *cell_table(rows)]
    totals["иконки предметов"] = 1

    summary = ", ".join(f"{k} — {v}" for k, v in totals.items())
    out.insert(4, f"Всего запросов: {sum(totals.values())} ({summary}).")
    out.insert(5, "")
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    missing = [c for c in db.units if c not in LOOK]
    slots = [s for s in db.slot_types if s not in ITEM_LOOKS]
    print(f"{OUT}: {sum(totals.values())} requests; classes without a look: {missing}; slots without an icon: {slots}")


if __name__ == "__main__":
    main()
