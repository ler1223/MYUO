"""Собрать полный каталог предметов и навыков Unicorn Overlord.

    python tools/uo_catalog.py [--main <main.bin>] [--text <Unicorn_US>] [--refresh]

Пишет только в docs/uo/catalog/:
  items.json          — все предметы: игра + вики + текущая реализация MYUO;
  skills.json         — все активные/пассивные навыки: игра + вики + предметы;
  README.md           — источники, схема, покрытие, конфликты;
  source/            — сырые выгрузки (main.bin, UcItemList.fms, Cargo, wikitext).

Игра — основной источник ID/чисел, Miraheze — основной источник классов,
добычи и текстовых описаний. Спорные места не разрешаются молча: они попадают
в поле conflicts соответствующего предмета/навыка.
"""
from __future__ import annotations

import argparse
import collections
import difflib
import json
import re
import struct
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from tools import uo_items  # noqa: E402
from tools.uo_extract import auto_map  # noqa: E402

DATA = ROOT / "data"
UNITS = json.loads((DATA / "units.json").read_text(encoding="utf-8"))
CLASS_NAME = {key: value.get("name", key) for key, value in UNITS.items()}
DOCS = ROOT / "docs" / "uo"
OUT = DOCS / "catalog"
SOURCE = OUT / "source"
WIKI_RAW = SOURCE / "wiki"
WIKI_PAGES = WIKI_RAW / "pages"

WIKI_API = "https://unilord.miraheze.org/w/api.php"
WIKI_BASE = "https://unilord.miraheze.org/wiki/"
UA = "Mozilla/5.0 (MYUO catalog collector; contact: local)"

ITEM_STRIDE = 46
ITEM_SIGNATURE = [0, 0, 282, 0, 0, 0, 18, 1, 8, 0, 500, 50]
ITEM_BLOCKS = (16, 24, 32)
ITEM_KINDS = {18: "sword", 19: "axe", 20: "spear", 21: "bow", 22: "staff",
              23: "shield", 24: "greatshield", 25: "accessory"}
SLOT = dict(uo_items.SLOTS)
SLOT["consumable"] = "consumable"
SLOT["material"] = "material"

SKILL_STRIDE = 76
SKILL_SIGNATURE = [0, 1025, 0, 171, 21, 65536, 0, 1, 0, 1123024896]
PCT_TYPES = {43, 224, 136, 229, 137, 130, 129, 110, 49, 225}
RAW_TYPES = {120, 84, 83, 114, 166, 123, 206, 220, 214, 105}

KIND_ORDER = ["sword", "axe", "spear", "bow", "staff", "shield", "greatshield",
              "accessory", "consumable", "material"]

# --- имена классов -----------------------------------------------------------------

CLASS_ALIASES = {
    "Lord": "lord", "High Lord": "high_lord", "Paladin": "paladin",
    "Fighter": "fighter", "Vanguard": "vanguard",
    "Swordfighter": "swordfighter", "Swordmaster": "sword_master",
    "Sellsword": "sellsword", "Landsknecht": "landsknecht",
    "Thief": "thief", "Rogue": "rogue",
    "Radiant Knight": "radiant_knight", "Sainted Knight": "sainted_knight",
    "Elven Fencer": "elven_fencer", "Werewolf": "werewolf",
    "Feathersword": "feathersword", "Feathershield": "feather_shield",
    "Crusader": "crusader", "Valkyria": "valkyria", "Prince": "prince",
    "Dreadnought": "dreadnought", "Dark Marquess (Sword)": "dark_marquess_s",
    "Housecarl": "housecarl", "Viking": "viking",
    "Gladiator": "gladiator", "Berserker": "berserker", "Werelion": "werelion",
    "Warrior": "warrior", "Breaker": "breaker",
    "Dark Knight": "dark_knight", "Doom Knight": "doom_knight",
    "Gryphon Knight": "gryphon_knight", "Gryphon Master": "gryphon_master",
    "Werebear": "werebear", "Dark Marquess (Axe)": "dark_marquess_a",
    "Soldier": "soldier", "Sergeant": "sergeant",
    "Hoplite": "hoplite", "Legionnaire": "legionnaire",
    "Knight": "knight", "Great Knight": "great_knight",
    "Wyvern Knight": "wyvern_knight", "Wyvern Master": "wyvern_master",
    "Elven Sibyl": "elven_sibyl", "Elven Augur": "elven_augur",
    "Werefox": "werefox", "Dark Marquess (Spear)": "dark_marquess_l",
    "Hunter": "hunter", "Sniper": "sniper",
    "Arbalist": "arbalist", "Shieldshooter": "shieldshooter",
    "Elven Archer": "elven_archer", "Featherbow": "feather_bow",
    "Snow Ranger": "snow_ranger",
    "Witch": "witch", "Sorceress": "sorceress",
    "Wizard": "wizard", "Warlock": "warlock",
    "Shaman": "shaman", "Druid": "druid",
    "Cleric": "cleric", "Bishop": "bishop",
    "Priestess": "priestess", "High Priestess": "high_priestess",
    "Wereowl": "wereowl", "Featherstaff": "feather_rod",
    "Dark Marquess (Staff)": "dark_marquess_r",
    "Alain": "alain",  # отдельного класса нет; см. classes_rule
}

STAFF_CLASSES = ["wizard", "warlock", "witch", "sorceress", "dark_marquess_r",
                 "cleric", "bishop", "wereowl", "feather_rod", "priestess", "high_priestess",
                 "shaman", "druid"]
ARCANE_CLASSES = ["wizard", "warlock", "witch", "sorceress", "dark_marquess_r"]
DIVINE_CLASSES = ["cleric", "bishop", "wereowl", "feather_rod", "priestess", "high_priestess"]
SHAMAN_CLASSES = ["shaman", "druid"]

BASE_CLASSES = {
    "sword": ["lord", "high_lord", "paladin", "fighter", "vanguard", "swordfighter", "sword_master",
              "sellsword", "landsknecht", "thief", "rogue", "radiant_knight", "sainted_knight",
              "elven_fencer", "werewolf", "feathersword", "feather_shield", "crusader", "valkyria",
              "prince", "dreadnought", "dark_marquess_s"],
    "axe": ["housecarl", "viking", "gladiator", "berserker", "werelion", "warrior", "breaker",
            "dark_knight", "doom_knight", "gryphon_knight", "gryphon_master", "werebear",
            "dark_marquess_a"],
    "spear": ["soldier", "sergeant", "hoplite", "legionnaire", "knight", "great_knight",
              "wyvern_knight", "wyvern_master", "elven_sibyl", "elven_augur", "werefox",
              "dark_marquess_l"],
    "bow": ["hunter", "sniper", "arbalist", "shieldshooter", "elven_archer", "feather_bow",
            "snow_ranger"],
    "staff": STAFF_CLASSES,
    "shield": ["lord", "high_lord", "paladin", "fighter", "vanguard", "viking", "landsknecht",
               "knight", "great_knight", "radiant_knight", "sainted_knight", "dark_knight",
               "doom_knight", "feathersword", "crusader", "valkyria"],
    "greatshield": ["hoplite", "legionnaire", "shieldshooter", "werebear", "feather_shield",
                    "dreadnought", "dark_marquess_a", "dark_marquess_r", "dark_marquess_l",
                    "dark_marquess_s"],
}

STAFF_GROUPS = {
    5: ("all_staff", STAFF_CLASSES),
    7: ("arcane", ARCANE_CLASSES),
    8: ("divine", DIVINE_CLASSES),
    26: ("gleaming_mace", ["cleric", "bishop"]),
    27: ("shaman", SHAMAN_CLASSES),
}

SUBTYPE_RULES = {
    "sword": {34: ("rapier", ["swordfighter", "sword_master"]),
              23: ("holy_unicorn_blade", ["lord", "high_lord"])},
    "axe": {6: ("hammer", ["werebear", "warrior", "breaker"]),
            33: ("dark_knight_cleaver", None)},
    "spear": {25: ("flame_javelin", ["soldier", "sergeant"]),
              32: ("dragoons_warspear", ["wyvern_knight", "wyvern_master"])},
    "bow": {31: ("crossbow", ["arbalist", "shieldshooter"])},
    "shield": {12: ("chivalric", None)},
}

# Restrictions for accessories from the GameFAQs Item Tables (Equip Limits column).
# Only items with an explicit, documented limit are listed here.
ACCESSORY_RULES = {
    "mages_gloves": ("explicit", ["wizard", "warlock", "witch", "sorceress", "elven_fencer",
                                  "priestess", "high_priestess", "elven_augur", "dark_marquess_r"],
                     "GameFAQs Item Tables: Mage's Gloves — Wizard, Warlock, Witch, Sorceress, Elven Fencer, Priestess, High Priestess, Elven Augur, Staff Dark Marquess"),
    "masters_gauntlets": ("non_caster", None,
                          "GameFAQs Item Tables: Master's Gauntlets — All non-caster classes"),
    "guardian_gloves": ("non_caster", None,
                        "GameFAQs Item Tables: Guardian Gloves — All non-caster classes"),
    "wyvern_reins": ("explicit", ["wyvern_knight", "wyvern_master", "gryphon_knight", "gryphon_master"],
                     "GameFAQs Item Tables: Wyvern Reins — Wyvern Knight, Wyvern Master, Gryphon Knight, Gryphon Master"),
    "heavenwyvern_reins": ("explicit", ["wyvern_knight", "wyvern_master", "gryphon_knight", "gryphon_master"],
                           "GameFAQs Item Tables: Heavenwyvern Reins — Wyvern Knight, Wyvern Master, Gryphon Knight, Gryphon Master"),
    "coursers_reins": ("cavalry", None,
                       "GameFAQs Item Tables: Courser's Reigns — Cavalry classes"),
    "heavensteed_reins": ("cavalry", None,
                          "GameFAQs Item Tables: Heavensteed Reins — Cavalry classes"),
    "wyvern_claw": ("flying", None,
                    "GameFAQs Item Tables: Wyvern Claw — Flying units"),
    "shawl_of_repose": ("explicit", ["wyvern_knight", "wyvern_master", "gryphon_knight", "gryphon_master",
                                     "wereowl", "feathersword", "feather_bow", "feather_rod", "feather_shield"],
                        "GameFAQs Item Tables: Shawl of Repose — Wyvern/Gryphon/Wereowl/Feather classes"),
    "counter_belt": ("melee", None,
                     "GameFAQs Item Tables: Counter Belt — All melee classes"),
}

CAVALRY_CLASSES = ["dark_knight", "doom_knight", "great_knight", "high_lord", "knight", "paladin",
                   "radiant_knight", "sainted_knight", "dark_marquess_l"]
FLYING_CLASSES = ["wyvern_knight", "wyvern_master", "gryphon_knight", "gryphon_master", "wereowl",
                  "feathersword", "feather_bow", "feather_rod", "feather_shield"]


def norm_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    text = text.replace("\ufffd", "").replace("\u2019", "'").replace("\u2018", "'")
    # Притяжательное 's не должно менять имя: Notos's Sword == Notos Sword.
    text = re.sub(r"'s\b", "", text, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def slug(name: str) -> str:
    return uo_items.slug(name.replace("\u2019", "'"))


def clean_wiki(text: str) -> str:
    text = text.strip()
    # В таблицах Miraheze первая ячейка иногда несёт style="... | значение".
    text = re.sub(r'^(?:style|class|colspan|rowspan|align|width|data-sort-value|id)\s*=\s*[^|]*\|\s*',
                  "", text, flags=re.I | re.S)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"<ref[^>]*/>", "", text)
    text = re.sub(r"\[\[File:[^\]]*\]\]", "", text, flags=re.I)
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]*)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = text.replace("[[]]", "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def split_substats(text: str) -> list[str]:
    text = clean_wiki(text)
    parts = []
    for line in re.split(r"[\n;]+", text):
        line = line.strip(" *\u2022")
        if line and line not in ("-", "—"):
            parts.append(line)
    return parts


def parse_int(value: str):
    if value is None:
        return None
    value = clean_wiki(str(value)).replace(",", "").replace("G", "").strip()
    if not value or value in ("-", "—", "N/A", "n/a", "?"):
        return None
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def wiki_api(params: dict):
    url = WIKI_API + "?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": "2"})
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def cargo_query(table: str, fields: str) -> list[dict]:
    rows, offset = [], 0
    while True:
        data = wiki_api({"action": "cargoquery", "tables": table, "fields": fields,
                         "limit": "500", "offset": str(offset)})
        batch = [row["title"] for row in data.get("cargoquery", [])]
        rows += batch
        if len(batch) < 500:
            break
        offset += 500
    return rows


WIKI_PAGES_LIST = ["Swords", "Axes", "Spears", "Bows", "Staves", "GreatShields", "Shields",
                   "Accessories", "Consumables", "Materials", "Items", "Classes"]


def fetch_wiki(refresh: bool = False) -> None:
    WIKI_RAW.mkdir(parents=True, exist_ok=True)
    WIKI_PAGES.mkdir(parents=True, exist_ok=True)
    if refresh:
        for page in WIKI_PAGES_LIST:
            data = wiki_api({"action": "parse", "page": page, "prop": "wikitext"})
            text = data.get("parse", {}).get("wikitext", "")
            (WIKI_RAW / f"{page}.wikitext").write_text(text, encoding="utf-8")
            print("wiki:", page, len(text))
        items = cargo_query("Items", "Id,Sort,Name,Icon,PhysickalAttack,MagickalAttack,PhysickalDefense,"
                                    "MagickalDefense,GuardRate,Skill,Slot1,Slot2,Slot3,Description,Cost,Sell")
        skills = cargo_query("Skills", "Category,Cost,Name,Type,ClassSkill,EquipSkill,LearnedAt,"
                                     "PhysickalPotency,MagickalPotency,HitCount,HitRate,Pattern,Ranged,"
                                     "Limited,Unguardable,Uncoverable,Charge,Activation,Description")
        (SOURCE / "miraheze_items.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        (SOURCE / "miraheze_skills.json").write_text(json.dumps(skills, ensure_ascii=False, indent=1), encoding="utf-8")
        print("cargo: items", len(items), "skills", len(skills))


def load_cached_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


# --- игровые данные -----------------------------------------------------------------

def read_names(path: Path) -> list[str]:
    data = path.read_bytes()
    start = next(i for i in range(0x20, len(data)) if data[i])
    return [b.decode("utf-8", "replace") for b in data[start:].split(b"\0")]


def find_item_table(words: np.ndarray) -> int:
    for position in np.where(words == 282)[0]:
        start = int(position) - 2
        if start >= 0 and words[start:start + len(ITEM_SIGNATURE)].tolist() == ITEM_SIGNATURE \
                and words[start + ITEM_STRIDE + 2] == 283:
            return start
    raise SystemExit("таблица предметов не найдена: образ другой версии?")


def find_skill_table(words: np.ndarray) -> int:
    for position in np.where(words == 171)[0]:
        start = int(position) - 3
        if start >= 0 and words[start:start + len(SKILL_SIGNATURE)].tolist() == SKILL_SIGNATURE \
                and words[start + SKILL_STRIDE + 3] == 172:
            return start
    raise SystemExit("таблица навыков не найдена: образ другой версии?")


def read_enum(path: Path) -> list[str]:
    return [m.group(1) for line in path.read_text(encoding="utf-8-sig").splitlines()[1:]
            if (m := re.match(r"([A-Z0-9_]+)\s*,", line))]


def skill_names_map(text: Path) -> tuple[dict[str, str], dict[str, str], list[str]]:
    names = auto_map.align_names(text)
    sheet = read_names(text / "MsgSheet" / "UcSkillList.fms")
    english = {}
    for text_name in sheet:
        text_name = re.sub(r"^\((A|P)\) ", "", text_name).replace("\ufffd", "'")
        english.setdefault(auto_map.norm(text_name), text_name)
    by_internal = {internal: english[key] for key, internal in names.items() if key in english}
    return names, by_internal, sheet


def extract_game_items(main: Path, text: Path) -> list[dict]:
    image = main.read_bytes()
    words = np.frombuffer(image[:len(image) // 4 * 4], "<u4").astype(np.int64)
    table = find_item_table(words)
    names = read_names(text / "MsgSheet" / "UcItemList.fms")
    offset = names.index("Bronze Sword", 100) - 282
    enum = read_enum(text / "Debug" / "_UcEnum_Item.inc")
    start, end = enum.index("WEAPON_START"), enum.index("ACCESSORY_END")
    _, skill_map, _ = skill_names_map(text)
    skill_enum = read_enum(text / "Debug" / "_UcEnum_Skill.inc")

    def skill_name(sid: int):
        if not 0 < sid < len(skill_enum):
            return None
        return skill_map.get(re.sub(r"^(ACT|PAS)_", "", skill_enum[sid]))

    stat_ids = load_cached_json(DOCS / "items_game.json", {}).get("stat_ids", {})
    stat_ids = {int(k): tuple(v) for k, v in stat_ids.items()}

    def stat_line(sid: int, value: float):
        if sid not in stat_ids:
            return None
        label, sign, percent = stat_ids[sid]
        if sign == "R":
            return label
        number = round(value * 100) if percent else (int(value) if float(value).is_integer() else value)
        if sign == "T":
            return label.replace("{n}", str(number))
        return f"{label} {sign}{number}{'%' if percent else ''}"

    rows = []
    for idx in range(start + 1, end):
        if enum[idx].endswith(("_START", "_END")):
            continue
        name = names[idx + offset].replace("\ufffd", "'")
        record = words[table + (idx - 282) * ITEM_STRIDE: table + (idx - 281) * ITEM_STRIDE]
        if int(record[2]) != idx or int(record[6]) not in ITEM_KINDS:
            continue
        kind = ITEM_KINDS[int(record[6])]
        low, high = int(record[8]) & 0xFFFF, int(record[8]) >> 16
        item_skill = skill_name(int(record[12])) if int(record[12]) else None
        if item_skill and not re.search(r"[A-Za-z]", item_skill):
            item_skill = None
        entry = {
            "game_id": idx, "internal": enum[idx], "name": name, "kind": kind,
            "subtype_word": int(record[7]),
            "phys_atk": 0, "mag_atk": 0, "phys_def": 0, "mag_def": 0, "guard_rate": 0,
            "price": int(record[10]), "sell": int(record[11]), "skill_id": int(record[12]),
            "skill_name": item_skill,
            "substats": [],
            "blocks": [],
        }
        if kind in ("sword", "axe", "spear", "bow", "staff"):
            entry["phys_atk"], entry["mag_atk"] = low, high
        elif kind in ("shield", "greatshield"):
            entry["phys_def"], entry["guard_rate"] = low, high
        else:
            entry["phys_def"], entry["mag_def"] = low, high
        for block in ITEM_BLOCKS:
            sid, raw = int(record[block]), int(record[block + 1])
            value = struct.unpack("<f", struct.pack("<I", raw))[0]
            if sid:
                line = stat_line(sid, value)
                entry["blocks"].append({"id": sid, "value": value, "line": line})
                if line:
                    entry["substats"].append(line)
        entry["debug"] = ("DEBUG" in entry["internal"] or entry["name"].startswith(("HP +", "STR +",
                                                                                       "Physical Attack +",
                                                                                       "Magical Attack +",
                                                                                       "Critical Damage +")))
        entry["dummy"] = entry["name"] in ("-", "DUMMY", "None", "") or "EXPAND" in entry["internal"]
        entry["has_stats"] = bool(entry["phys_atk"] or entry["mag_atk"] or entry["phys_def"]
                                  or entry["mag_def"] or entry["guard_rate"] or entry["substats"]
                                  or entry["skill_name"])
        rows.append(entry)
    return rows


def f32(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", int(value)))[0]


def clean_skill_text(text: str) -> str:
    text = re.sub(r"#c\(\d+\)(.*?)#/c", r"\1", text, flags=re.S)
    text = re.sub(r"#\(5[67]\)\s*(AP|PP)", r"\1", text)
    text = re.sub(r"#\(\d+\)", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


NEGATIVE_VERB = re.compile(r"Inflicts", re.I)
SIGNED_VERBS = re.compile(r"Inflicts|Grants|Restores?|Recover|Sacrifice|Ignores|Reduce|Remove", re.I)


SENTENCE_END = re.compile(r"(?<!Phys)(?<!Mag)\.\s|\)\n")


def fill_skill_text(text: str, record) -> tuple[str, bool]:
    """Подставляет числа записи навыка вместо «%s».

    Игра хранит величины без знака: «Inflicts Initiative %s» — это штраф (−30), «Grants … %s» — прибавка.
    Поэтому у значений после глагола «Inflicts» ставится минус. Одинаковые блоки (вид и значение), которые
    игра повторяет для усиленного варианта («вдвое для летающих»), считаются одним числом.
    """
    slots = text.count("%s")
    if not slots:
        return text, True
    blocks = []
    for offset in (17, 26, 35):
        kind, value = int(record[offset]), f32(record[offset + 1])
        if kind and value and abs(value) < 100000:
            blocks.append((kind, value))
    if len(blocks) != slots and len(set(blocks)) == slots:
        blocks = list(dict.fromkeys(blocks))
    if len(blocks) != slots:
        return text, False
    iterator = iter(blocks)

    def put(match) -> str:
        kind, value = next(iterator)
        sentence = SENTENCE_END.split(text[:match.start()])[-1]       # глагол той же фразы
        verbs = SIGNED_VERBS.findall(sentence)
        if verbs and NEGATIVE_VERB.fullmatch(verbs[-1]):
            value = -abs(value)
        percent = kind in PCT_TYPES or (kind not in RAW_TYPES and 0 < abs(value) <= 1.5 and value != int(value))
        return f"{round(value * 100)}%" if percent else f"{value:+g}".replace("+-", "-")

    return re.sub(r"%s", put, text).replace("%%", "%"), True


def extract_game_skills(main: Path, text: Path) -> list[dict]:
    image = main.read_bytes()
    words = np.frombuffer(image[:len(image) // 4 * 4], "<u4").astype(np.int64)
    base = find_skill_table(words)

    def record(sid: int):
        return words[base + (sid - 171) * SKILL_STRIDE: base + (sid - 170) * SKILL_STRIDE]

    names, inner_to_english, sheet = skill_names_map(text)
    enum = read_enum(text / "Debug" / "_UcEnum_Skill.inc")
    index = {re.sub(r"^(ACT|PAS)_", "", value): i for i, value in enumerate(enum[:471])}

    wiki = json.loads((DOCS / "classes.json").read_text(encoding="utf-8"))["skills"]
    normalize = lambda value: re.sub(r"#\(\d+\)|#c\(\d+\)|%s|[^a-z]", "", value.lower())  # noqa: E731
    votes = {"active": collections.Counter(), "p1": collections.Counter()}
    for name, skill in wiki.items():
        key = auto_map.norm(name)
        if key not in names or names[key] not in index:
            continue
        sid = index[names[key]]
        lines = skill["text"].split("\n")
        first = normalize(lines[0])
        if skill["category"] == "active" and len(normalize(skill["text"])) >= 40:
            for position in range(900, 1500):
                if normalize(sheet[position]) == normalize(skill["text"]):
                    votes["active"][position - sid] += 1
        if skill["category"] == "passive" and len(first) >= 20:
            for position in range(1400, len(sheet)):
                if normalize(sheet[position].split("\n")[0]) == first:
                    votes["p1"][position - sid] += 1
    off_active = votes["active"].most_common(1)[0][0] if votes["active"] else 957
    off_passive = votes["p1"].most_common(1)[0][0] if votes["p1"] else 1428

    # Вторую строку пассивки ищем по уже собранному skills_game.json.
    previous = load_cached_json(DOCS / "skills_game.json", {})
    second_votes = collections.Counter()
    for key, skill in previous.items():
        if skill.get("category") != "passive":
            continue
        lines = skill.get("text", "").split("\n")
        if len(lines) < 2:
            continue
        sid = skill.get("game_id")
        if not isinstance(sid, int) or not 0 <= sid < 471:
            continue
        second = normalize(lines[1])
        if len(second) < 20:
            continue
        for position in range(off_passive + 400, len(sheet)):
            if normalize(sheet[position]) == second:
                second_votes[position - sid] += 1
    off_effect = second_votes.most_common(1)[0][0] if second_votes else None

    rows = []
    for sid, internal in enumerate(enum[:471]):
        match = re.match(r"^(ACT|PAS)_(.+)$", internal)
        if not match or internal.endswith(("_START", "_END")) or internal.startswith("ACT_ASSIST"):
            continue
        name = inner_to_english.get(match.group(2))
        if not name or not re.search(r"[A-Za-z]{3}", name):
            continue
        record_data = record(sid)
        if int(record_data[3]) != sid:
            continue
        active = match.group(1) == "ACT"
        phys, mag = f32(record_data[9]), f32(record_data[10])
        if active:
            game_text = clean_skill_text(sheet[off_active + sid])
        else:
            # условие срабатывания — 1428 + номер, действие — 957 + номер (как у описаний активных навыков)
            parts = [sheet[off_passive + sid], sheet[off_active + sid]]
            game_text = clean_skill_text("\n".join(part for part in parts if part))
        if re.fullmatch(r"[?\s]*", game_text):
            continue
        game_text, filled = fill_skill_text(game_text, record_data)
        rows.append({
            "key": slug(name), "name": name, "game_id": sid, "internal": internal,
            "category": "active" if active else "passive",
            "type": "Attack" if phys or mag else "Support",
            "ap": (int(record_data[5]) >> 16) if active else 0,
            "pp": int(record_data[6]),
            "phys": round(phys) or None, "mag": round(mag) or None,
            "hits": (int(record_data[11]) & 0xFFFF) or None,
            "accuracy": (int(record_data[11]) >> 16) or None,
            "traits": ["Ranged"] if int(record_data[1]) & 1 else [],
            "game_text": game_text, "numbers_filled": filled,
        })
    return rows


# --- вики ---------------------------------------------------------------------------

def parse_tables(text: str) -> list[list[list[str]]]:
    """Вернуть таблицы как списки строк; ячейки уже очищены, <br> стал \n."""
    tables = []
    for block in re.findall(r"\{\|.*?\n\|\}", text, re.S):
        rows = []
        for chunk in re.split(r"\n\|-", block)[1:]:
            chunk = chunk.strip()
            if not chunk or chunk.startswith("|}"):
                continue
            if chunk.startswith("|"):
                chunk = chunk[1:]
            chunk = chunk.replace("\n|", "||")
            cells = [clean_wiki(cell) for cell in chunk.split("||")]
            if len([cell for cell in cells if cell]) >= 2:
                rows.append(cells)
        tables.append(rows)
    return tables


BASE_CLASS_TEXT: dict[str, str] = {}
BASE_CLASS_UNKNOWN: dict[str, list[str]] = {}


def parse_equippable(text: str) -> list[str]:
    match = re.search(r"==\s*Equippable By\s*==(.*?)(?:\n==|\Z)", text, re.S | re.I)
    if not match:
        return []
    names = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line.startswith("*"):
            continue
        line = clean_wiki(line[1:])
        names.append(line)
    return names


def map_class_names(names: list[str]) -> tuple[list[str], list[str]]:
    """Превратить строки вики ('Lord/High Lord') в id классов."""
    mapped: list[str] = []
    unknown: list[str] = []
    for raw in names:
        raw = raw.strip()
        if not raw:
            continue
        if raw in CLASS_ALIASES:
            mapped.append(CLASS_ALIASES[raw])
            continue
        parts = [part.strip() for part in re.split(r"\s*/\s*", raw) if part.strip()]
        if len(parts) > 1:
            for part in parts:
                if part in CLASS_ALIASES:
                    mapped.append(CLASS_ALIASES[part])
                else:
                    unknown.append(part)
        else:
            unknown.append(raw)
    return sorted(set(mapped)), unknown


def extract_wiki_items() -> list[dict]:
    rows = []
    base_text = {}

    def add(kind, name, **fields):
        name = clean_wiki(name)
        if not name or name in ("-", "—"):
            return
        entry = {"kind": kind, "name": name, "page": fields.pop("page", ""), "stats": [],
                 "skill": "", "price": None, "sell": None, "acquisition": "", "classes_text": "",
                 "icon": "", "wiki_id": None, "description": "", "group": ""}
        entry.update(fields)
        rows.append(entry)

    # Оружие
    for page, kind in (("Swords", "sword"), ("Axes", "axe"), ("Spears", "spear"),
                       ("Bows", "bow"), ("Staves", "staff")):
        path = WIKI_RAW / f"{page}.wikitext"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        raw_classes = parse_equippable(text)
        base_text[kind], BASE_CLASS_UNKNOWN[kind] = map_class_names(raw_classes)
        BASE_CLASS_TEXT[kind] = " / ".join(raw_classes)
        for table in parse_tables(text):
            for row in table:
                # 0 icon, 1 name, 2 atk, 3 second stat/classes, 4 skill, 5 substats, 6 price, 7 obtain
                if len(row) < 8 or not row[1]:
                    continue
                if kind == "staff":
                    add(kind, row[1], page=page, icon=row[0], mag_atk=parse_int(row[2]),
                        classes_text=row[3], skill=row[4], stats=split_substats(row[5]),
                        price=parse_int(row[6]), acquisition=row[7])
                else:
                    add(kind, row[1], page=page, icon=row[0], phys_atk=parse_int(row[2]),
                        mag_atk=parse_int(row[3]), skill=row[4], stats=split_substats(row[5]),
                        price=parse_int(row[6]), acquisition=row[7])

    # Большие щиты
    path = WIKI_RAW / "GreatShields.wikitext"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        raw_classes = parse_equippable(text)
        base_text["greatshield"], BASE_CLASS_UNKNOWN["greatshield"] = map_class_names(raw_classes)
        BASE_CLASS_TEXT["greatshield"] = " / ".join(raw_classes)
        for table in parse_tables(text):
            for row in table:
                if len(row) < 9 or not row[2]:
                    continue
                stats = [value for value in row[6:9] if value and value not in ("-", "—")]
                add("greatshield", row[2], page="GreatShields", icon=row[1], wiki_id=parse_int(row[0]),
                    phys_def=parse_int(row[3]), guard_rate=parse_int(row[4]), skill=row[5],
                    stats=stats)

    # Аксессуары
    path = WIKI_RAW / "Accessories.wikitext"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        for table in parse_tables(text):
            for row in table:
                if len(row) < 9 or not row[1]:
                    continue
                stats = [value for value in row[5:8] if value and value not in ("-", "—")]
                add("accessory", row[1], page="Accessories", icon=row[0], wiki_id=parse_int(row[8]),
                    phys_def=parse_int(row[2]), mag_def=parse_int(row[3]), skill=row[4], stats=stats)

    # Щиты из Cargo (страница Shields — только шаблон)
    cargo = load_cached_json(SOURCE / "miraheze_items.json", [])
    for row in cargo:
        if row.get("Sort") == "Shield":
            stats = [value for value in (row.get("Slot1"), row.get("Slot2"), row.get("Slot3"))
                     if value and value not in ("-", "—")]
            add("shield", row.get("Name", ""), page="Shields", icon=row.get("Icon", ""),
                wiki_id=parse_int(row.get("Id")), phys_def=parse_int(row.get("PhysickalDefense")),
                guard_rate=parse_int(row.get("GuardRate")), skill=row.get("Skill", ""),
                stats=stats, price=parse_int(row.get("Cost")), sell=parse_int(row.get("Sell")),
                description=row.get("Description", ""))

    # Остальные записи Cargo, которых нет в таблицах (например, одиночные предметы)
    known = {(norm_name(row["name"]), row["kind"]) for row in rows}
    for row in cargo:
        sort = row.get("Sort", "")
        kind = {"Sword": "sword", "Axe": "axe", "Spear": "spear", "Bow": "bow", "Staff": "staff",
                "Shield": "shield", "Greatshield": "greatshield", "Accessory": "accessory",
                "Consumables": "consumable", "Material": "material"}.get(sort)
        if not kind or (norm_name(row.get("Name", "")), kind) in known:
            continue
        stats = [value for value in (row.get("Slot1"), row.get("Slot2"), row.get("Slot3"))
                 if value and value not in ("-", "—")]
        add(kind, row.get("Name", ""), page="Cargo", icon=row.get("Icon", ""),
            wiki_id=parse_int(row.get("Id")), skill=row.get("Skill", ""), stats=stats,
            price=parse_int(row.get("Cost")), sell=parse_int(row.get("Sell")),
            description=row.get("Description", ""))

    # Расходники
    path = WIKI_RAW / "Consumables.wikitext"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        groups = {}
        last_heading = ""
        for line in text.splitlines():
            if match := re.match(r"==\s*([^=]+?)\s*==", line):
                last_heading = match.group(1).strip()
            for name in re.findall(r"name\d+\s*=\s*([^\n|]+)", line):
                groups[clean_wiki(name)] = last_heading
        for table in parse_tables(text):
            for row in table:
                if len(row) < 4 or not row[1]:
                    continue
                unobtainable = row[0].rstrip().endswith("*")
                add("consumable", row[1], page="Consumables", icon=row[0].rstrip("* ").strip(),
                    description=row[2], wiki_id=parse_int(row[3]), group=groups.get(clean_wiki(row[1]), ""),
                    unobtainable=unobtainable)

    # Страница Shields — только шаблон, поэтому категорийный список берём из
    # проверенного набора классов; для остальных видов он нужен как страховка.
    for kind, ids in BASE_CLASSES.items():
        if not base_text.get(kind):
            base_text[kind] = list(ids)
            BASE_CLASS_TEXT.setdefault(kind, " / ".join(CLASS_NAME.get(class_id, class_id) for class_id in ids))

    # Материалы (шаблоны ItemList)
    path = WIKI_RAW / "Materials.wikitext"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        last_heading = ""
        for match in re.finditer(r"(?:===\s*([^=]+?)\s*===)|(\{\{ItemList.*?\}\})", text, re.S):
            if match.group(1):
                last_heading = match.group(1).strip()
                continue
            body = match.group(2)
            names = dict(re.findall(r"(name\d+)\s*=\s*([^\n|]+)", body))
            images = dict(re.findall(r"(image\d+)\s*=\s*([^\n|]+)", body))
            for key, name in names.items():
                add("material", name, page="Materials", icon=images.get(key, "").strip(),
                    group=last_heading)
        # В Detailed List есть описания и ID, которых нет в шаблонах ItemList.
        details = {}
        for table in parse_tables(text):
            for row in table:
                if len(row) >= 4 and row[1] and row[2]:
                    details[norm_name(row[1])] = (clean_wiki(row[2]), parse_int(row[3]))
        for row in rows:
            if row["kind"] not in ("material", "consumable"):
                continue
            detail = details.get(norm_name(row["name"]))
            if detail:
                description, wiki_id = detail
                if not row.get("description"):
                    row["description"] = description
                if row["wiki_id"] is None:
                    row["wiki_id"] = wiki_id

    # Один и тот же предмет может прийти из Cargo и из таблицы (или из двух
    # региональных ItemList). Склеиваем по виду+нормализованному имени.
    deduped: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["kind"], norm_name(row["name"]))
        current = deduped.get(key)
        if current is None:
            deduped[key] = row
            continue
        # Предпочитаем строку из тематической таблицы, а не Cargo.
        if current.get("page") == "Cargo" and row.get("page") != "Cargo":
            base, other = row, current
        else:
            base, other = current, row
        for field in ("icon", "wiki_id", "skill", "price", "sell", "acquisition",
                      "description", "classes_text", "group"):
            if base.get(field) in (None, "", [], 0) and other.get(field) not in (None, "", [], 0):
                base[field] = other[field]
        if not base.get("stats") and other.get("stats"):
            base["stats"] = other["stats"]
        for field in ("acquisition", "description"):
            if base.get(field) and other.get(field) and base[field] != other[field]:
                base[field] = base[field] + "\n" + other[field]
        deduped[key] = base
    rows = list(deduped.values())

    return rows, base_text


def enrich_with_pages(rows: list[dict]) -> None:
    """Добавить Acquisition/EquippableBy/цену из одиночных страниц предметов."""
    for row in rows:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", row["name"]).strip("_")
        path = WIKI_PAGES / f"{safe}.wikitext"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        params = {}
        if match := re.search(r"\{\{\s*Item InfoBox\s*(.*?)\n\}\}", text, re.S | re.I):
            for line in match.group(1).splitlines():
                line = line.strip()
                if line.startswith("|") and "=" in line:
                    key, value = line[1:].split("=", 1)
                    params[key.strip()] = value.strip()
        if params.get("Cost") and row.get("price") is None:
            row["price"] = parse_int(params["Cost"])
        if params.get("Buy") and row.get("price") is None:
            row["price"] = parse_int(params["Buy"])
        if params.get("Sell") and row.get("sell") is None:
            row["sell"] = parse_int(params["Sell"])
        if params.get("EquippableBy"):
            row["classes_text"] = clean_wiki(params["EquippableBy"])
        if match := re.search(r"==\s*Acquisition\s*==(.*?)(?:\n==|\Z)", text, re.S | re.I):
            row["acquisition"] = clean_wiki(match.group(1))
        if row.get("acquisition") in ("*", "-", "—"):
            row["acquisition"] = ""
        if params.get("Description") and not row.get("description"):
            row["description"] = clean_wiki(params["Description"])
        # Одиночные страницы щитов/аксессуаров хранят числа и слоты в параметрах
        # Item InfoBox, а не в таблице Cargo.
        for param, field in (("PhysickalAttack", "phys_atk"), ("MagickalAttack", "mag_atk"),
                             ("PhysickalDefense", "phys_def"), ("MagickalDefense", "mag_def"),
                             ("GuardRate", "guard_rate")):
            if params.get(param) and row.get(field) is None:
                row[field] = parse_int(params[param])
        if params.get("Skill") and not row.get("skill"):
            row["skill"] = clean_wiki(params["Skill"])
        if params.get("Id") and not row.get("wiki_id"):
            row["wiki_id"] = parse_int(params["Id"])
        if params.get("Icon") and not row.get("icon"):
            row["icon"] = clean_wiki(params["Icon"])
        stats = row.get("stats") or []
        for index in (1, 2, 3):
            value = params.get(f"Slot{index}")
            if value:
                value = clean_wiki(value)
                if value and value not in stats:
                    stats.append(value)
        row["stats"] = stats


# --- слияние -----------------------------------------------------------------------

ALIAS_PAIRS = [
    # (имя на Miraheze, имя в файлах игры)
    ("Baroque Staff", "Baroque Rod"), ("Carnat Staff", "Carnat Rod"),
    ("Vorpal Staff", "Vorpal Rod"), ("Meteorite Staff", "Meteorite Rod"),
    ("Kingspear Elhal", "Kingslance Elhal"),
    ("Sacral Sword", "Sainted Sword"), ("Sacral Axe", "Sainted Axe"),
    ("Sacral Spear", "Sainted Spear"), ("Sacral Staff", "Sainted Rod"),
    ("Sacral Bow", "Sainted Bow"), ("Sacral Broach", "Sainted Broach"),
    ("Apeliotes's Bow", "Apeliotes"), ("Boreas's Axe", "Boreas"),
    ("Euros's Staff", "Euros"), ("Helleborus Axe", "Helleborus"),
    ("Lupinus Staff", "Lupine"), ("Notos's Sword", "Notus"),
    ("Orchis Spear", "Orchis"), ("Quince Bow", "Quince"),
    ("Rosularis Sword", "Rosularis"), ("Skiron's Greatshield", "Skiron Greatshield"),
    ("Zephyros's Spear", "Zephyros"), ("Mercenay's Shield", "Mercenary's Shield"),
    ("Watchman's Bockler", "Watchman's Buckler"),
    ("Zenoiran Knight Bow", "Zenoiran Knight's Bow"),
    ("Zenoiran Knight Spear", "Zenoiran Knight's Spear"),
    ("Zenoiran Knight Axe", "Zenoiran Knight's Axe"),
    ("Zenoiran Knight Staff", "Zenoiran Knight's Staff"),
    ("Zenoiran Knight Shield", "Zenoiran Knight's Shield"),
    ("Zenoiran Knight Greatshield", "Zenoiran Knight's Greatshield"),
    ("Recruit's ShortAxe", "Recruit's Handaxe"),
    ("Aid Cover", "Healing Cover"),
    # Совпадают по ID предмета и характеристикам: вики использует имена персонажей,
    # игра — имена ветров.
    ("Kaikai's Shield", "Caecius"),
    ("Lips's Ring", "Libonotus Wind Ring"),
    ("Demonic Pact", "Daemonic Pact"),
    ("Slyphic Barrier", "Sylphic Barrier"),
]

ALIASES_BIDIR: dict[str, str] = {}
for _wiki_name, _game_name in ALIAS_PAIRS:
    _w, _g = norm_name(_wiki_name), norm_name(_game_name)
    ALIASES_BIDIR[_w] = _g
    ALIASES_BIDIR[_g] = _w


def alias_key(name: str) -> str:
    return norm_name(name)


def find_wiki_match(game: dict, wiki_rows: list[dict], used: set[int]) -> tuple[dict | None, str, float, int | None]:
    key = norm_name(game["name"])
    candidates = [(i, row) for i, row in enumerate(wiki_rows)
                  if i not in used and row["kind"] == game["kind"]]
    exact = [(i, row) for i, row in candidates if norm_name(row["name"]) == key]
    if exact:
        return exact[0][1], "exact", 1.0, exact[0][0]
    target = ALIASES_BIDIR.get(key)
    if target:
        alias = [(i, row) for i, row in candidates if norm_name(row["name"]) == norm_name(target)]
        if alias:
            return alias[0][1], "alias", 1.0, alias[0][0]
    # мягкое совпадение (только для не-отладочных записей)
    if not game.get("debug") and not game.get("dummy"):
        scored = [(difflib.SequenceMatcher(None, key, norm_name(row["name"])).ratio(), i, row)
                  for i, row in candidates]
        if scored:
            score, index, row = max(scored, key=lambda value: value[0])
            if score >= 0.88:
                return row, "fuzzy", round(score, 3), index
    return None, "none", 0.0, None


def item_classes(game: dict | None, wiki: dict | None, base_classes: dict[str, list[str]]) -> dict:
    kind = (game or wiki)["kind"]
    subtype = kind
    game_sub = game.get("subtype_word") if game else None
    if kind == "staff":
        subtype = {5: "staff", 7: "staff_arcane", 8: "staff_divine",
                   26: "staff_gleaming", 27: "staff_shaman"}.get(game_sub, "staff")
    elif kind == "accessory":
        # word7 у аксессуаров — категория (перчатки, кольцо и т.п.), а не
        # подтип оружия; для каталога достаточно accessory.
        subtype = "accessory"
    elif game_sub is not None and game_sub != {"sword": 1, "axe": 3, "spear": 2, "bow": 4,
                                               "shield": 9, "greatshield": 10,
                                               "accessory": 0}.get(kind):
        subtype = SUBTYPE_RULES.get(kind, {}).get(game_sub, (f"subtype_{game_sub}", None))[0]

    notes = []
    source = ""
    rule = "unrestricted"
    allowed: list[str] = []
    wiki_text = (wiki or {}).get("classes_text", "").strip()
    text = wiki_text if kind == "staff" else (wiki_text or BASE_CLASS_TEXT.get(kind, ""))

    if kind == "staff":
        if game_sub == 26:
            rule, allowed = "gleaming_mace", ["cleric", "bishop"]
            source = "game:word7=26; gamefaqs"
            notes.append("Miraheze перечисляет всех лекарей; game word7=26 и GameFAQs — Cleric/Bishop.")
            if not text:
                text = "Cleric / Bishop (game word7=26)"
        elif text and text.lower() != "all":
            names = [part.strip() for part in re.split(r"[,/\n]+", text) if part.strip()]
            mapped, unknown = map_class_names(names)
            if mapped:
                allowed = mapped
                if set(mapped) == set(STAFF_CLASSES):
                    rule = "all_staff"
                elif set(mapped) == set(ARCANE_CLASSES):
                    rule = "arcane"
                elif set(mapped) == set(DIVINE_CLASSES):
                    rule = "divine"
                elif set(mapped) == set(SHAMAN_CLASSES):
                    rule = "shaman"
                else:
                    rule = "staff_explicit"
                source = "miraheze:Staves; game:word7"
            if unknown:
                notes.append("неизвестные классы в вики: " + ", ".join(unknown))
        elif game_sub in STAFF_GROUPS:
            rule, allowed = STAFF_GROUPS[game_sub]
            allowed = list(allowed)
            source = "game:word7"
            text = " / ".join(CLASS_NAME.get(class_id, class_id) for class_id in allowed) + f" (game word7={game_sub})"
        else:
            rule, allowed, source = "all_staff", list(STAFF_CLASSES), "miraheze:Staves"
            text = "All staff users"

    elif subtype in ("rapier", "flame_javelin", "dragoons_warspear", "hammer", "crossbow"):
        allowed = sorted(set(base_classes.get(kind, [])) & set(
            SUBTYPE_RULES[kind][game_sub][1] or []))
        rule, source = subtype, "game:word7 + gamefaqs"
    elif subtype == "holy_unicorn_blade":
        allowed, rule, source = ["lord", "high_lord"], "alain_only", "gamefaqs:Item Tables"
        text = "Alain (Lord / High Lord)"
        notes.append("Алана нет среди классов data/units.json; ограничение записано как Lord/High Lord.")
    elif subtype == "dark_knight_cleaver":
        allowed, rule, source = list(base_classes.get(kind, [])), "base", "miraheze:Axes"
        notes.append("word7=33; GameFAQs показывает Dark Knight Cleaver+ у Crusader/Valkyria — ограничения по классу нет.")
    elif subtype == "chivalric":
        allowed, rule, source = list(base_classes.get(kind, [])), "base", "miraheze:Shields"
        notes.append("word7=12; GameFAQs показывает Chivalric Shield+ у Crusader/Valkyria — ограничения по классу нет.")
    else:
        allowed, rule, source = list(base_classes.get(kind, [])), "base", f"miraheze:{kind}"

    if kind == "accessory":
        key = slug((game or wiki)["name"])
        if key in ACCESSORY_RULES:
            rule, allowed, source = ACCESSORY_RULES[key]
            text = source
            if rule == "non_caster":
                allowed = sorted(k for k, value in UNITS.items() if "caster" not in value.get("tags", []))
            elif rule == "cavalry":
                allowed = list(CAVALRY_CLASSES)
            elif rule == "flying":
                allowed = list(FLYING_CLASSES)
            elif rule == "melee":
                melee_slots = {"light_sword", "heavy_weapon", "lance"}
                allowed = sorted(k for k, value in UNITS.items() if melee_slots & set(value.get("slots", [])))
        else:
            allowed, rule, source = [], "unrestricted", "no documented limit"
            text = "No documented limit"
    elif kind in ("consumable", "material"):
        allowed, rule, source = [], "unrestricted", "not equipment"

    return {"allowed": allowed, "rule": rule, "source": source, "text": text,
            "subtype": subtype, "notes": notes}


def merge_items(game_rows: list[dict], wiki_rows: list[dict], base_classes: dict[str, list[str]]) -> list[dict]:
    wiki_used: set[int] = set()
    catalog = []
    for game in sorted(game_rows, key=lambda row: row["game_id"]):
        wiki, match_type, score, wiki_index = find_wiki_match(game, wiki_rows, wiki_used)
        if wiki is not None and wiki_index is not None:
            wiki_used.add(wiki_index)
        classes = item_classes(game, wiki, base_classes)
        name = game["name"]
        kind = game["kind"]
        canonical_stats = {
            "phys_atk": game["phys_atk"] or (wiki or {}).get("phys_atk") or 0,
            "mag_atk": game["mag_atk"] or (wiki or {}).get("mag_atk") or 0,
            "phys_def": game["phys_def"] or (wiki or {}).get("phys_def") or 0,
            "mag_def": game["mag_def"] or (wiki or {}).get("mag_def") or 0,
            "guard_rate": game["guard_rate"] or (wiki or {}).get("guard_rate") or 0,
        }
        price = (wiki or {}).get("price")
        if price is None:
            price = game["price"]
        sell = (wiki or {}).get("sell")
        if sell is None:
            sell = game["sell"]
        conflicts = []
        if wiki:
            for stat in ("phys_atk", "mag_atk", "phys_def", "mag_def", "guard_rate"):
                wiki_value = wiki.get(stat)
                if wiki_value not in (None, 0) and game.get(stat) not in (None, 0) and wiki_value != game[stat]:
                    conflicts.append(f"{stat}: игра {game[stat]}, вики {wiki_value}")
            if wiki.get("skill") and game.get("skill_name") and \
                    norm_name(wiki["skill"]) != norm_name(game["skill_name"]):
                conflicts.append(f"навык: игра {game['skill_name']}, вики {wiki['skill']}")
            if wiki.get("classes_text") and classes["rule"] == "gleaming_mace":
                conflicts.append("Gleaming Mace: вики — все лекари, game word7/GameFAQs — Cleric/Bishop")
        skill = game.get("skill_name") or (wiki or {}).get("skill") or None
        if skill and not re.search(r"[A-Za-z]", skill):
            skill = None
        entry = {
            "catalog_id": f"game:{game['internal']}",
            "id": slug(name),
            "name": name,
            "kind": kind,
            "slot": SLOT.get(kind, kind),
            "subtype": classes["subtype"] or kind,
            "stats": canonical_stats,
            "game_stats": {key: game[key] for key in ("phys_atk", "mag_atk", "phys_def", "mag_def", "guard_rate")},
            "wiki_stats": {key: (wiki or {}).get(key) for key in ("phys_atk", "mag_atk", "phys_def", "mag_def", "guard_rate")},
            "price": price, "sell": sell,
            "substats": game["substats"] or (wiki or {}).get("stats", []),
            "skill": skill,
            "skill_id": None,
            "classes": classes,
            "acquisition": (wiki or {}).get("acquisition") or "",
            "description": (wiki or {}).get("description") or "",
            "icon": (wiki or {}).get("icon") or "",
            "group": (wiki or {}).get("group") or "",
            "unobtainable": bool((wiki or {}).get("unobtainable")),
            "wiki_id": (wiki or {}).get("wiki_id"),
            "match": {"type": match_type, "score": score},
            "game": {
                "id": game["game_id"], "internal": game["internal"],
                "subtype_word": game.get("subtype_word"), "price": game["price"],
                "sell": game["sell"], "skill_id": game["skill_id"], "skill_name": game.get("skill_name"),
                "debug": game["debug"], "dummy": game["dummy"], "has_stats": game["has_stats"],
                "blocks": game["blocks"],
            },
            "wiki": {
                "page": (wiki or {}).get("page"), "name": (wiki or {}).get("name"),
                "url": WIKI_BASE + (wiki or {}).get("page", "").replace(" ", "_") if wiki else None,
                "price": (wiki or {}).get("price"), "sell": (wiki or {}).get("sell"),
                "skill": (wiki or {}).get("skill"), "classes_text": (wiki or {}).get("classes_text"),
                "acquisition": (wiki or {}).get("acquisition"), "icon": (wiki or {}).get("icon"),
                "description": (wiki or {}).get("description"), "wiki_id": (wiki or {}).get("wiki_id"),
            },
            "sources": ["game:main.bin"] + (["miraheze:" + wiki["page"]] if wiki and wiki.get("page") else []),
            "conflicts": conflicts,
        }
        catalog.append(entry)

    # Вики-предметы без игровой записи
    for index, wiki in enumerate(wiki_rows):
        if index in wiki_used:
            continue
        classes = item_classes(None, wiki, base_classes)
        wiki_skill = wiki.get("skill") or None
        if wiki_skill and not re.search(r"[A-Za-z]", wiki_skill):
            wiki_skill = None
        entry = {
            "catalog_id": f"wiki:{wiki['kind']}:{slug(wiki['name'])}",
            "id": slug(wiki["name"]),
            "name": wiki["name"], "kind": wiki["kind"], "slot": SLOT.get(wiki["kind"], wiki["kind"]),
            "subtype": classes["subtype"] or wiki["kind"],
            "stats": {key: wiki.get(key) or 0 for key in ("phys_atk", "mag_atk", "phys_def", "mag_def", "guard_rate")},
            "game_stats": {key: 0 for key in ("phys_atk", "mag_atk", "phys_def", "mag_def", "guard_rate")},
            "wiki_stats": {key: wiki.get(key) for key in ("phys_atk", "mag_atk", "phys_def", "mag_def", "guard_rate")},
            "price": wiki.get("price"), "sell": wiki.get("sell"), "substats": wiki.get("stats", []),
            "skill": wiki_skill, "skill_id": None, "classes": classes,
            "acquisition": wiki.get("acquisition") or "", "description": wiki.get("description") or "",
            "icon": wiki.get("icon") or "", "group": wiki.get("group") or "",
            "unobtainable": bool(wiki.get("unobtainable")), "wiki_id": wiki.get("wiki_id"),
            "match": {"type": "wiki_only", "score": 1.0},
            "game": None,
            "wiki": {"page": wiki.get("page"), "name": wiki["name"],
                     "url": WIKI_BASE + (wiki.get("page") or "").replace(" ", "_"),
                     "price": wiki.get("price"), "sell": wiki.get("sell"), "skill": wiki.get("skill"),
                     "classes_text": wiki.get("classes_text"), "acquisition": wiki.get("acquisition"),
                     "icon": wiki.get("icon"), "description": wiki.get("description"),
                     "wiki_id": wiki.get("wiki_id")},
            "sources": ["miraheze:" + (wiki.get("page") or "")],
            "conflicts": [],
        }
        catalog.append(entry)
    return catalog


# --- навыки ------------------------------------------------------------------------

def choose_skill_text(game_text: str, wiki_text: str) -> tuple[str, str]:
    """Выбрать более полный текст, но не прятать противоречие в числах.

    Игровой текст часто содержит только условие срабатывания, а вики добавляет
    эффект. Если же вики меняет знак AP/PP или процента, доверяем игре и
    возвращаем конфликт.
    """
    game_text = (game_text or "").strip()
    wiki_text = (wiki_text or "").strip()
    if not wiki_text:
        return game_text, ""
    if not game_text:
        return wiki_text, ""
    pattern = re.compile(r"[+-]\d+\s*(?:AP|PP)|[+-]\d+\s*%", re.I)
    game_tokens = {re.sub(r"\s+", " ", token.upper()) for token in pattern.findall(game_text)}
    wiki_tokens = {re.sub(r"\s+", " ", token.upper()) for token in pattern.findall(wiki_text)}
    for token in game_tokens:
        if token[0] not in "+-":
            continue
        opposite = ("-" if token[0] == "+" else "+") + token[1:]
        if opposite in wiki_tokens and token not in wiki_tokens:
            return game_text, f"текст: игра «{game_text}», вики «{wiki_text}»"
    return wiki_text, ""


def build_skills(game_skills: list[dict], class_skills: dict, item_entries: list[dict],
                 cargo_skills: list[dict]) -> list[dict]:
    by_key: dict[str, dict] = {}
    # 1. Игровые навыки
    for game in game_skills:
        key = game["key"]
        entry = by_key.setdefault(key, {
            "id": key, "name": game["name"], "aliases": [], "category": game["category"],
            "type": game["type"], "ap": game["ap"], "pp": game["pp"], "learned_at": None,
            "phys": game["phys"], "mag": game["mag"], "hits": game["hits"],
            "accuracy": game["accuracy"], "traits": list(game["traits"]),
            "text": game["game_text"], "game_text": game["game_text"], "wiki_text": "",
            "classes": [], "items": [], "game": {"id": game["game_id"], "internal": game["internal"],
                                                  "numbers_filled": game["numbers_filled"]},
            "wiki": None, "sources": ["game:main.bin"], "conflicts": [],
        })
        entry.setdefault("game_variants", []).append({
            "id": game["game_id"], "internal": game["internal"], "category": game["category"],
            "text": game["game_text"], "ap": game["ap"], "pp": game["pp"],
        })

    # 2. Классовые навыки вики
    for name, skill in class_skills.items():
        if not name or name.startswith("|") or "pdmg number" in name.lower():
            continue
        key = slug(name)
        target = by_key.get(key)
        if target is None:
            # сначала явный алиас (Demonic Pact -> Daemonic Pact, Slyphic -> Sylphic)
            alias = ALIASES_BIDIR.get(norm_name(name))
            if alias:
                target = next((candidate for candidate in by_key.values()
                               if norm_name(candidate["name"]) == alias), None)
        if target is None:
            # затем лучшее мягкое совпадение, а не первое попавшееся
            best, best_score = None, 0.0
            for candidate in by_key.values():
                score = difflib.SequenceMatcher(None, key, candidate["id"]).ratio()
                if score > best_score:
                    best, best_score = candidate, score
            if best is not None and best_score >= 0.9:
                target = best
        if target is not None and slug(name) != target["id"] and name not in target["aliases"]:
            target["aliases"].append(name)
        if target is None:
            target = {"id": key, "name": name, "aliases": [], "category": skill["category"],
                      "type": skill["type"], "ap": skill["ap"], "pp": skill["pp"], "learned_at": None,
                      "phys": skill["phys"], "mag": skill["mag"], "hits": skill["hits"],
                      "accuracy": skill["accuracy"], "traits": list(skill.get("traits", [])),
                      "text": skill["text"], "game_text": "", "wiki_text": skill["text"],
                      "classes": [], "items": [], "game": None, "wiki": None,
                      "sources": ["miraheze/classes"], "conflicts": []}
            by_key[key] = target
        target["wiki_text"] = skill["text"]
        target["text"], text_conflict = choose_skill_text(target.get("game_text", ""), skill["text"])
        if text_conflict and text_conflict not in target["conflicts"]:
            target["conflicts"].append(text_conflict)
        target["classes"] = list(skill.get("classes", []))
        target["wiki"] = {key: skill.get(key) for key in ("category", "type", "ap", "pp", "phys", "mag",
                                                          "hits", "accuracy", "traits", "classes")}
        if "miraheze/classes" not in target["sources"]:
            target["sources"].append("miraheze/classes")

    # 3. Cargo Skills (доп. поля pattern/ranged/...)
    cargo_by_name = {norm_name(row.get("Name", "")): row for row in cargo_skills}
    for entry in by_key.values():
        row = cargo_by_name.get(norm_name(entry["name"]))
        if row:
            entry["cargo"] = {key: row.get(key) for key in row}
            for source in ("miraheze:Skills",):
                if source not in entry["sources"]:
                    entry["sources"].append(source)

    # 4. Связь с предметами
    item_links: dict[str, list[str]] = collections.defaultdict(list)
    for item in item_entries:
        skill_name = item.get("skill")
        if not skill_name or not re.search(r"[A-Za-z]", skill_name):
            continue
        key = slug(skill_name)
        if key not in by_key:
            # ищем по нормализованному имени
            key = next((candidate for candidate in by_key if norm_name(by_key[candidate]["name"]) == norm_name(skill_name)), key)
        if key not in by_key:
            by_key[key] = {"id": key, "name": skill_name, "aliases": [], "category": "unknown",
                           "type": "", "ap": None, "pp": None, "learned_at": None, "phys": None,
                           "mag": None, "hits": None, "accuracy": None, "traits": [], "text": "",
                           "game_text": "", "wiki_text": "", "classes": [], "items": [],
                           "game": None, "wiki": None, "sources": ["item"], "conflicts": []}
        by_key[key]["items"].append(item["catalog_id"])
        item_links[item["catalog_id"]].append(key)
    for item in item_entries:
        if item["catalog_id"] in item_links:
            item["skill_id"] = item_links[item["catalog_id"]]

    # 5. Текущая реализация
    data_skills = json.loads((DATA / "skills.json").read_text(encoding="utf-8"))
    data_passives = json.loads((DATA / "passives.json").read_text(encoding="utf-8"))
    for entry in by_key.values():
        key = entry["id"]
        if key in data_skills:
            value = data_skills[key]
            parts = len(value.get("parts", []))
            has_effect = bool(parts or value.get("applies") or value.get("ap_restore")
                              or value.get("pp_restore") or value.get("extras")
                              or value.get("bonus_vs") or value.get("potency"))
            known_stub = key in {"wall", "magick_wall", "resurrection"} and not has_effect
            entry["implementation"] = {
                "present": True, "kind": "skill", "id": key,
                "stub": known_stub, "parts": parts, "has_effect": has_effect,
                "status": "stub" if known_stub else ("implemented" if has_effect else "present_no_effects"),
                "ap_cost": value.get("ap_cost"), "pp_cost": value.get("pp_cost"),
            }
        elif key in data_passives:
            value = data_passives[key]
            entry["implementation"] = {"present": True, "kind": "passive", "id": key,
                                       "stub": False, "parts": 0, "has_effect": True,
                                       "status": "implemented"}
        else:
            entry["implementation"] = {"present": False, "kind": None, "id": None, "stub": False,
                                       "parts": 0, "has_effect": False, "status": "missing"}
    result = sorted(by_key.values(), key=lambda entry: ({"active": 0, "passive": 1}.get(entry["category"], 2),
                                                       entry["name"].lower()))
    # В игровых строках проценты экранированы как %% (иногда %%%). В справочнике
    # нужен обычный текст, иначе 100%% выглядит как ошибка.
    for entry in result:
        for field in ("text", "game_text", "wiki_text"):
            if entry.get(field):
                entry[field] = re.sub(r"%{2,}", "%", entry[field])
        for variant in entry.get("game_variants", []):
            if variant.get("text"):
                variant["text"] = re.sub(r"%{2,}", "%", variant["text"])
        entry["conflicts"] = [re.sub(r"%{2,}", "%", conflict) for conflict in entry.get("conflicts", [])]
    return result


# --- запись ------------------------------------------------------------------------

def implementation_key(item: dict, data_items: dict, used: set[str]) -> str | None:
    """Найти текущий предмет MYUO с учётом алиасов, апострофов и суффикса II/III."""
    base_id = item["id"].split("__")[0]
    suffix = item["id"].split("__", 1)[1] if "__" in item["id"] else ""
    candidates: list[str] = []
    if suffix:
        numeral = {"2": "ii", "3": "iii", "4": "iv"}.get(suffix, suffix)
        candidates += [f"{base_id}_{numeral}", f"{base_id}{numeral}", f"{base_id}_{suffix}"]
    candidates += [base_id, slug(item["name"])]
    names = {norm_name(item["name"]), norm_name(base_id.replace("_", " "))}
    for wiki_name, game_name in ALIAS_PAIRS:
        if norm_name(item["name"]) in (norm_name(wiki_name), norm_name(game_name)):
            candidates += [slug(wiki_name), slug(game_name)]
            names |= {norm_name(wiki_name), norm_name(game_name)}
    for candidate in candidates:
        if candidate and candidate in data_items and candidate not in used:
            return candidate
    for key, value in data_items.items():
        if key in used:
            continue
        if norm_name(value.get("name", "")) in names:
            return key
    return None


def enrich_catalog_items(items: list[dict], skills: list[dict]) -> None:
    """Добавить переносимые поля и статус текущей реализации MYUO."""
    data_items = json.loads((DATA / "items.json").read_text(encoding="utf-8"))
    skill_by_id = {skill["id"]: skill for skill in skills}
    used_current: set[str] = set()
    for item in items:
        for field in ("acquisition", "description"):
            if item.get(field):
                item[field] = re.sub(r"%{2,}", "%", item[field])
        item["conflicts"] = [re.sub(r"%{2,}", "%", conflict) for conflict in item.get("conflicts", [])]
    equipment = [item for item in items if item["kind"] in SLOT and item["kind"] not in ("consumable", "material")]
    for item in equipment:
        notes: list[str] = []
        sub_mods, bonus, tags, heals = uo_items.substats({"stats": item.get("substats", [])}, notes)
        mods = uo_items.modifiers(item["stats"]) + sub_mods
        guard_efficiency = None
        for line in item.get("substats", []):
            match = re.search(r"Guard Efficiency\s*([+-]?\d+)\s*%", line, re.I)
            if match:
                guard_efficiency = int(match.group(1))
                break
        if item["kind"] == "shield":
            tags = ["shield"] + tags
        elif item["kind"] == "greatshield":
            tags = ["greatshield"] + tags
        price = round(item["price"] / 40) if item.get("price") else None
        item_skills, item_passives = [], []
        for sid in item.get("skill_id") or []:
            implementation = (skill_by_id.get(sid) or {}).get("implementation") or {}
            if implementation.get("kind") == "passive":
                item_passives.append(sid)
            else:
                item_skills.append(sid)
        item["suggested"] = {
            "slot": item["slot"],
            "modifiers": mods,
            "skills": item_skills,
            "passives": item_passives,
            "item_passives": [{"id": f"uo_item_heal_{percent}", "amount": int(percent)}
                              for percent in heals],
            "tags": tags,
            "ap_bonus": bonus.get("ap_bonus", 0),
            "pp_bonus": bonus.get("pp_bonus", 0),
            "guard_efficiency": guard_efficiency,
            "traits": bonus.get("traits", {}),
            "price": price,
            "notes": notes,
        }
        base_id = item["id"].split("__")[0]
        current_key = implementation_key(item, data_items, used_current)
        if current_key:
            used_current.add(current_key)
            current = data_items[current_key]
            item["implementation"] = {
                "present": True, "base_present": True, "id": current_key, "slot": current.get("slot"),
                "tier": current.get("tier"), "price": current.get("price"),
                "modifiers": current.get("modifiers", []), "skills": current.get("skills", []),
                "passives": current.get("passives", []), "tags": current.get("tags", []),
            }
        elif base_id in data_items:
            item["implementation"] = {
                "present": False, "base_present": True, "id": base_id,
                "note": "в MYUO есть только базовый вариант; эта запись не перенесена",
            }
        else:
            item["implementation"] = {"present": False, "base_present": False}

    # Тир — место по силе внутри вида, как в tools/uo_items.py.
    # Отладочные и пустые записи не должны сдвигать тиры реальных предметов.
    rankable = [item for item in equipment
                if not (item.get("game") or {}).get("debug")
                and not (item.get("game") or {}).get("dummy")]
    for kind in ("sword", "axe", "spear", "bow", "staff", "shield", "greatshield", "accessory"):
        group = [item for item in rankable if item["kind"] == kind]
        ranked = []
        for item in group:
            entry = {**item["stats"], "skills": item.get("skill_id") or []}
            ranked.append((uo_items.strength(entry, item["suggested"]["modifiers"], item["suggested"]), item))
        ranked.sort(key=lambda pair: pair[0])
        for index, (_power, item) in enumerate(ranked):
            tier = round(30 * index / max(1, len(ranked) - 1))
            item["suggested"]["tier"] = tier
            if not item["suggested"]["price"]:
                item["suggested"]["price"] = 20 + tier * 12
    for item in equipment:
        if "tier" not in item["suggested"]:
            item["suggested"]["tier"] = 0
            if not item["suggested"]["price"]:
                item["suggested"]["price"] = 20


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--main", type=Path, default=Path(r"F:\MYUO2\main.bin"))
    parser.add_argument("--text", type=Path, default=Path(r"F:\MYUO2\unpacked_us"))
    parser.add_argument("--refresh", action="store_true", help="перекачать вики-страницы и Cargo")
    parser.add_argument("--reuse-game", action="store_true",
                        help="не перечитывать main.bin, взять source/game_*.json")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    SOURCE.mkdir(parents=True, exist_ok=True)
    fetch_wiki(args.refresh)

    if args.reuse_game and (SOURCE / "game_items.json").exists() and (SOURCE / "game_skills.json").exists():
        game_items = load_cached_json(SOURCE / "game_items.json", [])
        game_skills = load_cached_json(SOURCE / "game_skills.json", [])
    else:
        game_items = extract_game_items(args.main, args.text)
        game_skills = extract_game_skills(args.main, args.text)
        write_json(SOURCE / "game_items.json", game_items)
        write_json(SOURCE / "game_skills.json", game_skills)
    print("игра: предметов", len(game_items), "навыков", len(game_skills))

    wiki_items, base_classes = extract_wiki_items()
    enrich_with_pages(wiki_items)
    write_json(SOURCE / "wiki_items_parsed.json", wiki_items)
    print("вики: предметов", len(wiki_items))

    class_skills = json.loads((DOCS / "classes.json").read_text(encoding="utf-8"))["skills"]
    cargo_skills = load_cached_json(SOURCE / "miraheze_skills.json", [])
    cargo_items = load_cached_json(SOURCE / "miraheze_items.json", [])

    items = merge_items(game_items, wiki_items, base_classes)
    skills = build_skills(game_skills, class_skills, items, cargo_skills)

    # Уникальные id: при совпадении добавляем суффикс
    seen = collections.Counter()
    for item in items:
        if not item["id"]:
            internal = (item.get("game") or {}).get("internal", "")
            item["id"] = "debug_" + (slug(internal) or "item")
        base = item["id"]
        seen[base] += 1
        if seen[base] > 1:
            item["id"] = f"{base}__{seen[base]}"
            item["variant_of"] = base
    def item_sort_key(item: dict):
        game = item.get("game") or {}
        junk = 1 if game.get("debug") or game.get("dummy") else 0
        return (KIND_ORDER.index(item["kind"]) if item["kind"] in KIND_ORDER else 99,
                junk, item["name"].lower(), game.get("id", 10**9))

    items.sort(key=item_sort_key)

    # Связь предметов и навыков: id навыка теперь окончательный
    skill_by_id = {skill["id"]: skill for skill in skills}
    for item in items:
        item["skill_id"] = [sid for sid in (item.get("skill_id") or []) if sid in skill_by_id]

    enrich_catalog_items(items, skills)

    write_json(OUT / "items.json", {"schema": 1, "generated": date.today().isoformat(),
                                     "sources": source_manifest(), "counts": item_counts(items), "items": items})
    write_json(OUT / "skills.json", {"schema": 1, "generated": date.today().isoformat(),
                                      "sources": source_manifest(), "counts": skill_counts(skills), "skills": skills})
    write_readme(items, skills, game_items, wiki_items)
    print("готово:", OUT / "items.json", OUT / "skills.json", OUT / "README.md")


def source_manifest() -> list[dict]:
    return [
        {"id": "game", "name": "Файлы игры", "confidence": "primary",
         "detail": "main.bin (таблицы предметов и навыков), UcItemList.fms, UcSkillList.fms, "
                   "_UcEnum_Item.inc, _UcEnum_Skill.inc"},
        {"id": "miraheze", "name": "Unicorn Overlord Wiki (Miraheze)", "confidence": "primary",
         "url": "https://unilord.miraheze.org", "detail": "таблицы Swords/Axes/Spears/Bows/Staves/"
                                                          "Shields/GreatShields/Accessories/Consumables/Materials, Cargo Items/Skills"},
        {"id": "gamefaqs", "name": "GameFAQs Item Tables (Merqurial)", "confidence": "secondary",
         "url": "https://gamefaqs.gamespot.com/switch/426397-unicorn-overlord/faqs/81216/item-tables",
         "detail": "колонка Equip Limits; страница закрыта Cloudflare, использованы доступные фрагменты"},
        {"id": "data", "name": "Текущая реализация MYUO", "confidence": "implementation",
         "detail": "data/items.json, data/skills.json, data/passives.json, data/units.json"},
    ]


def item_counts(items: list[dict]) -> dict:
    return {
        "total": len(items),
        "by_kind": dict(collections.Counter(item["kind"] for item in items)),
        "game": sum(1 for item in items if item.get("game")),
        "wiki_only": sum(1 for item in items if not item.get("game")),
        "wiki_only_equipment": sum(1 for item in items
                                   if not item.get("game") and item["kind"] not in ("consumable", "material")),
        "game_only": sum(1 for item in items if item.get("game") and item["match"]["type"] == "none"),
        "game_only_real": sum(1 for item in items
                              if item.get("game") and item["match"]["type"] == "none"
                              and not item["game"].get("debug") and not item["game"].get("dummy")),
        "with_classes": sum(1 for item in items
                            if item["classes"]["allowed"] and item["classes"]["rule"] != "unrestricted"),
        "debug": sum(1 for item in items if (item.get("game") or {}).get("debug")),
        "dummy": sum(1 for item in items if (item.get("game") or {}).get("dummy")),
    }


def skill_counts(skills: list[dict]) -> dict:
    return {
        "total": len(skills),
        "active": sum(1 for skill in skills if skill["category"] == "active"),
        "passive": sum(1 for skill in skills if skill["category"] == "passive"),
        "game": sum(1 for skill in skills if skill.get("game")),
        "wiki_only": sum(1 for skill in skills if not skill.get("game")),
        "implemented": sum(1 for skill in skills if skill["implementation"]["status"] == "implemented"),
        "present": sum(1 for skill in skills if skill["implementation"]["present"]),
        "stubs": sum(1 for skill in skills if skill["implementation"]["stub"]),
        "no_effects": sum(1 for skill in skills if skill["implementation"]["status"] == "present_no_effects"),
        "missing": sum(1 for skill in skills if not skill["implementation"]["present"]),
    }


def write_readme(items: list[dict], skills: list[dict], game_items: list[dict], wiki_items: list[dict]) -> None:
    counts = item_counts(items)
    scounts = skill_counts(skills)
    equipment = [item for item in items if item["kind"] in SLOT
                 and item["kind"] not in ("consumable", "material")]
    blank_acquisition = sum(1 for item in equipment if not item.get("acquisition"))
    blank_description = sum(1 for item in equipment if not item.get("description"))
    description_note = (f"Описаний нет ни у одной из {len(equipment)} единиц снаряжения."
                        if blank_description == len(equipment)
                        else f"Описаний нет у {blank_description} из {len(equipment)} единиц снаряжения.")
    unparsed_notes = sum(len((item.get("suggested") or {}).get("notes", [])) for item in equipment)
    staff = [item for item in items if item["kind"] == "staff" and item["classes"]["rule"] not in ("all_staff", "unrestricted")]
    conflicts = [(item["name"], conflict) for item in items for conflict in item["conflicts"]]
    text = f"""# Каталог Unicorn Overlord: предметы и навыки

Собрано {date.today().isoformat()}. Это справочник для переноса в MYUO, а не готовый `data/*.json`.

## Файлы

- `items.json` — {counts['total']} записей: {counts['game']} с игровой записью, {counts['wiki_only']} только с вики
  (из них {counts['wiki_only_equipment']} единиц снаряжения, остальное расходники/материалы),
  {counts['game_only']} только из игры (из них {counts['game_only_real']} реальных, остальные отладочные/пустые).
- `skills.json` — {scounts['total']} навыков: {scounts['active']} активных, {scounts['passive']} пассивных;
  {scounts['present']} уже есть в MYUO ({scounts['implemented']} с эффектами, {scounts['stubs']} заглушки,
  {scounts['no_effects']} без разобранных эффектов).
- `source/` — сырые выгрузки: `game_items.json`, `game_skills.json`, `wiki_items_parsed.json`,
  `miraheze_items.json`, `miraheze_skills.json`, `wiki/*.wikitext`, `wiki/pages/*.wikitext`.

## Источники и доверие

1. **Файлы игры** — primary: ID, внутренние имена, числа, цена, word7 (подтип), word12 (навык).
2. **Miraheze** — primary: классы посоха, добыча, тексты, таблицы щитов/аксессуаров/расходников.
3. **GameFAQs Item Tables** — secondary: колонка `Equip Limits` для аксессуаров и особого оружия.
4. **Fandom / docs/uo/classes.json** — secondary: классовые навыки, уровни, описания.
5. **data/** — текущая реализация MYUO; поле `implementation` показывает, что уже перенесено.

Источники не смешаны молча: расхождения лежат в `conflicts`, а спорные ограничения — в
`classes.notes`. Если источник не найден, `classes.rule = "unrestricted"` и
`classes.source = "no documented limit"` — это не значит, что ограничения нет.

## Схема предмета

```json
{{
  "catalog_id": "game:SWORD_01",
  "id": "bronze_sword",
  "name": "Bronze Sword",
  "kind": "sword",
  "slot": "light_sword",
  "subtype": "sword",
  "stats": {{"phys_atk": 8, "mag_atk": 0, "phys_def": 0, "mag_def": 0, "guard_rate": 0}},
  "game_stats": {{"phys_atk": 8, "mag_atk": 0, "phys_def": 0, "mag_def": 0, "guard_rate": 0}},
  "wiki_stats": {{"phys_atk": 8, "mag_atk": null, "phys_def": null, "mag_def": null, "guard_rate": null}},
  "price": 500,
  "sell": 50,
  "substats": [],
  "skill": null,
  "skill_id": [],
  "classes": {{
    "allowed": ["lord", "high_lord", "paladin", "..."],
    "rule": "base",
    "source": "miraheze:Swords",
    "text": "Lord/High Lord / Paladin / ...",
    "subtype": "sword",
    "notes": []
  }},
  "acquisition": "All mercenaries and recruits early on start with this weapon.",
  "description": "",
  "match": {{"type": "exact", "score": 1.0}},
  "game": {{"id": 282, "internal": "SWORD_01", "subtype_word": 1, "debug": false, "dummy": false}},
  "wiki": {{"page": "Swords", "name": "Bronze Sword"}},
  "sources": ["game:main.bin", "miraheze:Swords"],
  "conflicts": [],
  "suggested": {{
    "slot": "light_sword",
    "modifiers": [{{"stat": "phys_atk", "op": "FLAT", "value": 8}}],
    "skills": [], "passives": [], "item_passives": [],
    "tags": [], "ap_bonus": 0, "pp_bonus": 0, "guard_efficiency": null,
    "price": 12, "tier": 2, "notes": []
  }},
  "implementation": {{"present": true, "base_present": true, "id": "bronze_sword", "tier": 0, "price": 20}}
}}
```

`stats` — канонические числа: значения игры имеют приоритет, вики заполняет пробелы;
`game_stats` и `wiki_stats` сохранены отдельно. `classes.allowed` — id классов из
`data/units.json`; пустой список при `unrestricted` означает «ограничение не задокументировано».
Для посохов `rule`: `all_staff`, `arcane`, `divine`, `shaman`, `gleaming_mace`, `staff_explicit`.
Для оружия: `base`, `hammer`, `crossbow`, `rapier`, `flame_javelin`, `dragoons_warspear`, `alain_only`.
Для аксессуаров: `explicit`, `non_caster`, `cavalry`, `flying`, `melee`, `unrestricted`.

`suggested` — черновик для импорта: модификаторы, слот, навыки/пассивки, теги, цена и тир.
Цена и тир рассчитаны по силе внутри вида, это предложение, а не числа из игры; отладочные
и пустые записи в расчёте тира не участвуют.
`implementation` — что уже есть в `data/items.json` (по slug); `present: false` — ещё не перенесено.
`base_present: true` при `present: false` означает, что в MYUO есть только базовый вариант,
а этот дубликат (суффикс `__2`, `__3`) ещё не добавлен.
`match.type`: `exact`/`alias`/`fuzzy` — связь с вики, `wiki_only` — только вики (расходники/материалы),
`none` — только игра.

## Схема навыка

```json
{{
  "id": "power_bolt",
  "name": "Power Bolt",
  "category": "active",
  "type": "Attack",
  "ap": 1,
  "pp": 0,
  "phys": 120,
  "hits": 1,
  "accuracy": 100,
  "classes": ["Arbalist 1", "Shieldshooter 1"],
  "items": ["game:BOW_01"],
  "text": "Attack a single enemy.",
  "game_text": "Attack a single enemy.",
  "game": {{"id": 171, "internal": "ACT_POWER_BOLT"}},
  "game_variants": [{{"id": 171, "internal": "ACT_POWER_BOLT", "category": "active"}}],
  "implementation": {{
    "present": true, "kind": "skill", "id": "power_bolt",
    "stub": false, "parts": 1, "has_effect": true, "status": "implemented"
  }}
}}
```

## Что важно при переносе

- **Посохи.** `word7`: 5 — все посохи, 7 — аркана, 8 — божественные, 26 — Gleaming Mace,
  27 — шаманские. Вики-таблица даёт те же группы, но для Gleaming Mace расходится:
  вики — все лекари, game word7/GameFAQs — Cleric/Bishop. В `conflicts` это отмечено.
- **Молоты.** `word7=6`: {", ".join(sorted({item['name'] for item in items if item['subtype'] == 'hammer'}))}.
  Разрешены Werebear/Warrior/Breaker.
- **Арбалеты.** `word7=31`: Gallian Crossbow, Woodpecker; Arbalist/Shieldshooter.
- **Рапиры.** `word7=34`: Stingray, Moonlight Rapier; Swordfighter/Sword Master.
- **Особые копья.** Flame Javelin — Soldier/Sergeant; Dragoon's Warspear — Wyvern Knight/Master.
- **Holy Unicorn Blade** — Lord/High Lord (Алана нет в `data/units.json`, поэтому записаны эти классы).
- **Аксессуары.** Явно задокументированы Mage's Gloves, Master's Gauntlets, Guardian Gloves,
  Wyvern/Heavenwyvern/Courser's/Heavensteed Reins, Wyvern Claw, Shawl of Repose, Counter Belt.
  Остальные оставлены `unrestricted`; это не приговор, а отсутствие источника.
- **Отладка.** `game.debug`/`game.dummy` — записи вида `HP +50`, `WEAPON_EXPAND_*`, `-`.
  Их не надо переносить в игру.
- **Дубликаты.** Одинаковые имена (`Cursed Blade of the Abyss` и т.п.) сохранены как отдельные
  записи; `id` получает суффикс `__2`, `__3`, `variant_of` указывает на базовый.
- **Навыки.** 439 игровых записей; после склейки active/passive-вариантов — 437 карточек.
  Все 205 классовых навыков из `docs/uo/classes.json` привязаны к карточкам (в том числе через
  алиасы `Aid Cover`→`Healing Cover`, `Demonic Pact`→`Daemonic Pact`, `Slyphic Barrier`→`Sylphic Barrier`).
  Числа из игры, тексты из вики, где есть. `implementation.status`: `implemented` — есть эффекты;
  `stub` — известные пустые wall/magick_wall/resurrection; `present_no_effects` — запись есть,
  но эффекты ещё не разобраны; `missing` — записи нет. Два игровых навыка имеют
  active/passive-варианты (Animated Dead, Dark Armor) — они сохранены в `game_variants`.
- **Valor/leader skills** в этот файл не включены: в игровом enum они не имеют отдельных
  ACT/PAS-записей с английскими именами. Это отдельный слой.

## Как переносить

1. Берите только записи без `game.debug`/`game.dummy`; отладочные `-`, `HP +50`,
   `WEAPON_EXPAND_*` в игру не переносятся.
2. Для снаряжения основой служит `suggested`: `slot`, `modifiers`, `skills`, `passives`,
   `item_passives`, `tags`, `ap_bonus`, `pp_bonus`, `guard_efficiency`, `price`, `tier`.
   `suggested.notes` — строки субстатов, которые не разобрались автоматически.
   `guard_efficiency` вынесен отдельно, потому что в текущем `data/items.json` такого стата нет.
   `item_passives` — сгенерированные пассивки «лечение при активном навыке»; их нужно создать
   при импорте, если в проекте ещё нет соответствующих `uo_item_heal_*`.
3. `classes.allowed` переносите в `ItemDefinition.classes`. При проверке учитывайте
   и текущий класс, и историю повышений: `[definition.id, *state.history]`.
   Дополнительно сверяйте `slot` предмета со слотами класса: если слота нет, предмет
   недоступен даже при совпадении класса.
4. Сначала сверяйтесь с `implementation`: если `present: true`, в `data/items.json` уже есть
   предмет с этим `id`; сравните `implementation.modifiers`/`tier`/`price` с `suggested`.
5. Для навыков `implementation` показывает, есть ли уже запись в `data/skills.json` или
   `data/passives.json`; `status: "missing"` — надо добавлять, `stub` — реализация неполная.
6. `game_variants` сохраняет оба игровых варианта (active/passive), даже если карточка одна.

## Известные пробелы

- Добыча заполнена не у всех: без `acquisition` осталось {blank_acquisition} шт. снаряжения.
  {description_note} Miraheze хранит описания только для расходников/материалов и
  части отдельных страниц, а не для снаряжения.
- Часть игровых предметов без характеристик (67 записей: 19 реальных и 48 отладочных/пустых);
  они включены с `has_stats: false`, чтобы список был полным.
- `wiki_only`-снаряжения нет: Kaikai's Shield и Lips's Ring оказались алиасами Caecius и
  Libonotus Wind Ring (совпали игровые ID 705/849 и характеристики). Все 139 `wiki_only` —
  расходники и материалы.
- Локализационные пары (Sacral→Sainted, Staff→Rod, Apeliotes→Apeliotes's Bow и т.п.)
  сматчены через `ALIAS_PAIRS` и помечены `match.type = "alias"`.
- {unparsed_notes} строк субстатов не разобраны и лежат в `suggested.notes`; числа в игровых
  описаниях иногда остаются `%s`, если число подстановок не совпало (`game.numbers_filled = false`).

## Проверка

```powershell
python tools/uo_catalog.py --main F:\\MYUO2\\main.bin --text F:\\MYUO2\\unpacked_us
python -X utf8 -c "import json; d=json.load(open('docs/uo/catalog/items.json',encoding='utf-8')); print(d['counts'])"
```

Конфликты:

```powershell
python -X utf8 -c "import json; d=json.load(open('docs/uo/catalog/items.json',encoding='utf-8')); [print(i['name'], c) for i in d['items'] for c in i['conflicts']]"
```
"""
    (OUT / "README.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
