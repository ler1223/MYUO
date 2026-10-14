"""Промпты картинок для классов, навыков и предметов UO -> docs/uo_art_prompts.md (сами запросы не делаются).

    python tools/make_art_prompts.py

Собирается из справочника data/: спрайты всех классов — листами-линейками (режет tools/cut_lineup.py),
элементы экрана бойца и тактики, значки типов навыков и иконки видов предметов — листами 5x2
(режет tools/cut_ui_sheet.py, номера батчей с 11). Как в UO, своей картинки у навыка и предмета нет:
значок общий на тип навыка (game.skill_kinds), иконка — на вид предмета (слот).
Перегенерируйте после изменения справочника: список листов и файлов меняется вместе с ним.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from game.database import Database  # noqa: E402

OUT = ROOT / "docs" / "uo_art_prompts.md"
FIRST_BATCH = 11
ANCHOR = "fighter"          # первый персонаж первого листа — эталон роста для всех остальных листов
SHEET_WIDTH = 4.0           # сколько «пехотинцев» помещается на лист после эталона
WIDTH = {"cavalry": 1.8, "flying": 2.0}   # ширина всадника и летуна в пехотинцах

FOLLOW = """Follow the reference completely and repeat each picture: the same character with the same face, hair,
body, armor, clothes, colors, weapon, shield, mount or wings, in the same art style. Keep the pose of the
picture, only mirrored if needed so that everyone faces right. Do not change, add or invent anything."""
RULES = """Rules:
- one row on the same ground line, evenly spaced, nothing overlapping or cut off, full body from head to feet;
- one scale for everyone: <HUMAN>; riders, flyers and big beasts are taller - their height is in the line;
- transparent background, no ground, no shadow, no scenery, no text, no numbers."""
FIRST_LINEUP = f"""The attached picture uo_01_ref.png shows numbered characters from Unicorn Overlord.
Draw them as one horizontal lineup of full-body game sprites, in the order of the numbers from left to right.

{FOLLOW}

{RULES.replace("<HUMAN>", "a human is about 40% of the image height")}

Characters:
<персонажи>"""
NEXT_LINEUP = f"""Two pictures are attached: uo_01.png - the first finished lineup, and uo_NN_ref.png - numbered
characters from Unicorn Overlord. Draw a new lineup the same way as uo_01.png: far left the Fighter from
uo_01.png, unchanged and at the same size, then the characters of uo_NN_ref.png in the order of the numbers.

{FOLLOW}

{RULES.replace("<HUMAN>", "a human is as tall as that Fighter")}

Characters:
1. The Fighter from uo_01.png.
<персонажи>"""

# Рост выше человека, % (всадники и летуны — с конём или зверем); остальные — рост человека
HEIGHT = {
    "gladiator": 110, "berserker": 115, "werebear": 125, "werelion": 115,
    "knight": 180, "great_knight": 190, "radiant_knight": 180, "sainted_knight": 190, "dark_knight": 180,
    "doom_knight": 190, "paladin": 180, "high_lord": 180,
    "wyvern_knight": 200, "wyvern_master": 220, "gryphon_knight": 200, "gryphon_master": 220,
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


def look_line(db: Database, class_id: str, number: int) -> str:
    """«Knight - picture 2, rider on a horse, about 180% of a human's height.» — внешность с картинки коллажа."""
    unit = db.units[class_id]
    kind = {"cavalry": ", rider on a horse", "flying": ", flying"}
    kind = next((text for tag, text in kind.items() if tag in unit.tags), "")
    height = f", about {HEIGHT[class_id]}% of a human's height" if class_id in HEIGHT else ""
    return f"{unit.name} - picture {number}{kind}{height}."


def families(db: Database) -> list[list[str]]:
    """Семьи классов: базовый, затем его повышения; первой — семья эталона ANCHOR."""
    seen: set[str] = set()
    result = []

    def walk(class_id: str, family: list[str]) -> None:
        if class_id in seen:
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
           "3. Спрайты классов — листы-линейки (раздел 1): общий промпт листа ниже плюс строки персонажей. Внешность "
           "берётся с коллажа-референса `assets/ref/lineups/uo_NN_ref.png` (арт классов UO в полный рост, собирает "
           "`python tools/uo_class_refs.py`): строка N = персонаж с номером N. Первый лист задаёт рост и стиль: его Fighter — "
           "эталон, готовый `uo_01.png` прикладывается ко всем следующим листам вместе с их коллажем. Лист — в "
           "`assets/sprites_src/lineup/` и `python tools/cut_lineup.py ...` (команда у каждого листа). Свой спрайт "
           "сразу заменяет временный похожий (прежние спрайты — `assets/units/old_*`).",
           "4. Как в UO, у навыка и предмета нет своей картинки: значок — на тип навыка (атака, поддержка, лечение, "
           "помеха; активный или пассивный), иконка — на вид предмета. Тип навыка выводится из самого навыка "
           "(`game/skill_kinds.py`). Если всё же нужен свой значок, достаточно положить `skill/<тип>/<id>.png` "
           "или `item/<слот>/<id>.png`.",
           ""]
    batch = FIRST_BATCH
    totals = {}

    # 1. Спрайты классов
    sheets = lineup_sheets(db)
    count = sum(len(s) for s in sheets)
    out += ["## 1. Спрайты классов — листы-линейки", "",
            f"Все {count} классов заново, семьями (базовый класс и его повышения рядом): {len(sheets)} листов. "
            "Конница и летуны шире — их на листе меньше; рост выше человека указан в строке. Внешность — с "
            "коллажа `assets/ref/lineups/uo_NN_ref.png`: персонаж с тем же номером, что у строки, повторяется "
            "полностью.", "",
            "## Линейка: первый лист", "", "Приложить `assets/ref/lineups/uo_01_ref.png`.",
            "", "```", FIRST_LINEUP, "```", "",
            "## Линейка: остальные листы", "", "Приложить готовый `assets/sprites_src/lineup/uo_01.png` и коллаж "
            "листа `assets/ref/lineups/uo_NN_ref.png`.",
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
        out += [f"{k}. {look_line(db, c, k)}" for k, c in enumerate(group, start=first)]
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
    slots = [s for s in db.slot_types if s not in ITEM_LOOKS]
    print(f"{OUT}: {sum(totals.values())} requests; slots without an icon: {slots}")


if __name__ == "__main__":
    main()
