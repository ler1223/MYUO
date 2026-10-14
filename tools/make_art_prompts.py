"""Промпты картинок для классов, навыков и предметов UO -> docs/uo_art_prompts.md (сами запросы не делаются).

    python tools/make_art_prompts.py

Собирается из справочника data/ и docs/uo/: спрайты классов — листами-линейками (эталон паладин + 4
класса, режет tools/cut_lineup.py), элементы экрана бойца и тактики, значки навыков и пассивок,
иконки предметов — листами 5x2 по 10 (режет tools/cut_ui_sheet.py, номера батчей с 11).
Перегенерируйте после изменения справочника: список листов и файлов меняется вместе с ним.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from game.database import Database  # noqa: E402

OUT = ROOT / "docs" / "uo_art_prompts.md"
CLASSES_JSON = ROOT / "docs" / "uo" / "classes.json"
ITEMS_JSON = ROOT / "docs" / "uo" / "items.json"
FIRST_BATCH = 11
PER_LINEUP = 4

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
MATERIALS = {   # слово названия -> подсказка материала для иконки
    "Bronze": "dull bronze", "Recruit's": "plain simple iron, recruit issue", "Baroque": "ornate baroque gilded",
    "Iron": "plain grey iron", "Templar's": "holy white enamel with a gold cross", "Black-Iron": "blackened iron",
    "Greatwood": "pale carved wood with leaf motifs and a green gem", "Carnat": "red-lacquered steel",
    "Steel": "polished steel", "Spellsteel": "bluish runed steel faintly glowing", "Vorpal": "razor-keen silver steel",
    "Sanguine": "blood-red crimson metal", "Dragonbone": "ivory dragon bone with scales", "Thorn": "dark thorny wood and iron",
    "Icefall": "frosty pale-blue steel with icicles", "Wingcrest": "white steel with a feather crest",
    "Carnelian": "inlaid with red carnelian stones", "Phantom": "ghostly translucent violet metal",
    "Zenoiran": "imperial black and gold ornamented", "Meteorite": "dark meteoric iron with starry flecks",
    "Sacral": "sacred white and gold with a halo motif", "Holy": "white and gold holy", "Golden": "golden",
    "Gold": "gold", "Silver": "silver", "Hoarfrost": "icy white frost", "Searing": "red-hot glowing",
    "Viper": "green serpent motifs", "Luminous": "softly glowing pale gold", "Moonlight": "silver-blue moonlit",
    "Obsidian": "black obsidian", "Flame": "flame-wreathed", "Thundering": "crackling with lightning",
    "Rose": "rose and thorn motifs", "Royal": "royal blue and gold", "Runic": "carved runes",
    "Crimson": "crimson", "White": "white enamel", "Blue": "blue", "Kingsblade": "kingly legendary",
}
KIND_NOUN = {"light_sword": "sword", "heavy_weapon": "axe or hammer", "lance": "spear", "bow": "bow",
             "staff": "mage staff", "light_shield": "shield", "greatshield": "large tower greatshield",
             "artifact": "accessory"}


def chunks(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def item_hint(name: str) -> str:
    hints = [MATERIALS[w] for w in name.replace("'s", "'s").split() if w in MATERIALS]
    return ", ".join(dict.fromkeys(hints))


def skill_text(reference: dict, name: str) -> str:
    entry = reference.get(name)
    if not entry:
        return ""
    text = re.sub(r"\s+", " ", entry["text"].replace("\n", " ")).strip()
    text = re.sub(r"\b(AP|PP) ?\1\b", r"\1", text)           # «AP AP» из картинки и подписи в вики
    return text[:150].rstrip(" .")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    db = Database.load()
    classes_ref = json.loads(CLASSES_JSON.read_text(encoding="utf-8"))["skills"]
    items_ref = json.loads(ITEMS_JSON.read_text(encoding="utf-8"))
    skills_ref = {**classes_ref, **items_ref.get("skills", {})}
    out = ["# Промпты картинок: классы, навыки и предметы Unicorn Overlord",
           "",
           "Собрано `python tools/make_art_prompts.py` из справочника — перегенерируйте после его изменений. "
           "Промпты на английском. Запросы скрипт не делает: отправляйте вручную в ChatGPT или через "
           "`tools/gen_ui_image.py` по вашей команде.",
           "",
           "## Как пользоваться", "",
           "1. Листы с сеткой 5x2 (1536x1024, прозрачный фон): в начало запроса — блоки **STYLE** и **SHEET** из "
           "`docs/ui_prompts.md`, затем ячейки батча. Первой строкой — `Match the art direction of the attached "
           "screenshots, but do not copy any text, logo or exact artwork.` и 1-2 скриншота UO.",
           "2. Готовый лист — в `assets/ui/sheets/` под именем батча и нарезка: "
           "`python tools/cut_ui_sheet.py <номер> --force` (батчи 11+ ищутся в этом файле).",
           "3. Спрайты классов — листы-линейки (раздел 1): общий промпт листа из `docs/art_prompts.md`, раздел 1, "
           "плюс строки персонажей; лист — в `assets/sprites_src/lineup/` и `python tools/cut_lineup.py ...` "
           "(команда у каждого листа). Свой спрайт сразу заменяет временный похожий.",
           "4. Иконки и значки без своего файла берут общую заглушку, поэтому рисовать можно в любом порядке.",
           ""]
    batch = FIRST_BATCH
    totals = {}

    # 1. Спрайты классов
    ids = [c for c in db.units if c in LOOK]
    sheets = chunks(ids, PER_LINEUP)
    out += ["## 1. Спрайты классов — листы-линейки", "",
            f"{len(ids)} классов, по {PER_LINEUP} на лист после эталона-паладина: {len(sheets)} запросов. "
            "Конница и летуны выше человека — рост указан в строке.", ""]
    for n, group in enumerate(sheets, start=1):
        name = f"uo_{n:02d}.png"
        out += [f"**Лист {n}** (`assets/sprites_src/lineup/{name}`): "
                f"`python tools/cut_lineup.py assets/sprites_src/lineup/{name} _ref {' '.join(group)} --reference _ref`",
                "", "```"]
        out += [f"{k}. {LOOK[c]}." for k, c in enumerate(group, start=2)]
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
            "| Ячейка | Файл | Итог |", "| --- | --- | --- |",
            "| 1 | `frame/tactic_ap.png` | 512x128 |", "| 2 | `frame/tactic_pp.png` | 512x128 |",
            "| 3 | `frame/tactic_condition.png` | 512x128 |", "| 4 | `frame/priority.png` | 160x128 |",
            "| 5 | `frame/grade.png` | 96x96 |", "| 6 | `frame/picker.png` | 384x448 |",
            "| 7 | `icon/up.png` | 96x96 |", "| 8 | `icon/down.png` | 96x96 |", "| 9 | `icon/remove.png` | 96x96 |",
            "| 10 | `field/pedestal.png` | 512x192 |", ""]
    batch += 1
    totals["экран бойца"] = 1

    # 3. Значки навыков и пассивок
    entries = [("skill", k, d) for k, d in sorted(db.skills.items()) if not k.endswith(("_strike", "_heal"))] + \
              [("passive", k, d) for k, d in sorted(db.passives.items()) if not k.startswith("uo_item_heal")]
    sheets = chunks(entries, 10)
    out += ["## 3. Значки навыков и пассивок", "",
            f"{len(entries)} значков, {len(sheets)} листов. Ячейка: круглый значок 200x200 внутри кольца "
            "(кольцо рисует интерфейс — рисовать только сам символ на тёмном круге). Красноватые тона — физические, "
            "синие и фиолетовые — магия, золотые — лечение и защита.", ""]
    for group in sheets:
        out += [f"## Батч {batch} — значки навыков (`b{batch}_skills.png`)", "", "```", "<STYLE>", "<SHEET>"]
        rows = []
        for k, (kind, key, definition) in enumerate(group, start=1):
            what = "active skill" if kind == "skill" else "passive skill"
            hint = skill_text(skills_ref, definition.name)
            out.append(f"Cell {k}: round {what} icon, 200x200, \"{definition.name}\": {hint or 'a fitting emblem'}. "
                       "A single bold symbol on a dark round field, no ring, no text.")
            rows.append(f"| {k} | `{kind}/{key}.png` | 256x256 |")
        out += ["```", "", "| Ячейка | Файл | Итог |", "| --- | --- | --- |", *rows, ""]
        batch += 1
    totals["значки навыков"] = len(sheets)

    # 4. Иконки предметов по видам
    out += ["## 4. Иконки предметов", "",
            "Ячейка: иконка предмета 200x200, лёгкий поворот три четверти, чистый силуэт, без рамки и фона "
            "(рамку цвета тира рисует интерфейс). Материал серии указан в строке.", ""]
    count = 0
    for slot in ("light_sword", "heavy_weapon", "lance", "bow", "staff", "light_shield", "greatshield", "artifact"):
        items = sorted((d.tier, k, d) for k, d in db.items.items() if d.slot == slot)
        for group in chunks(items, 10):
            out += [f"## Батч {batch} — иконки: {KIND_NOUN[slot]} (`b{batch}_items.png`)", "", "```", "<STYLE>", "<SHEET>"]
            rows = []
            for k, (_tier, key, definition) in enumerate(group, start=1):
                hint = item_hint(definition.name)
                out.append(f"Cell {k}: inventory icon, 200x200, {KIND_NOUN[slot]} \"{definition.name}\""
                           f"{': ' + hint if hint else ''}. Single object, slight three-quarter view, no frame.")
                rows.append(f"| {k} | `item/{slot}/{key}.png` | 256x256 |")
            out += ["```", "", "| Ячейка | Файл | Итог |", "| --- | --- | --- |", *rows, ""]
            batch += 1
            count += 1
    totals["иконки предметов"] = count
    summary = ", ".join(f"{k} — {v}" for k, v in totals.items())
    out.insert(4, f"Всего запросов: {sum(totals.values())} ({summary}).")
    out.insert(5, "")
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    missing = [c for c in db.units if c not in LOOK]
    print(f"{OUT}: {sum(totals.values())} requests; classes without a look: {missing}")


if __name__ == "__main__":
    main()
