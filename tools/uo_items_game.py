"""Снаряжение UO из файлов игры: добавить предметы, которых нет в данных (вики их не знает).

    python tools/uo_items_game.py --main <образ main (распакованный NSO)> --text <папка Unicorn_US> [--enum <Item.inc>]
                                  [--dry-run]

Откуда что:
- список и порядок предметов — Debug/_UcEnum_Item.inc (снаряжение: WEAPON_START..ACCESSORY_END);
- названия — MsgSheet/UcItemList.fms (английские; i-й предмет перечисления = (i + смещение)-я строка,
  смещение находится по «Bronze Sword»);
- характеристики — таблица предметов в данных исполняемого файла: записи по 46 слов (u32) подряд,
  слово 2 — номер предмета. Раскладка записи (проверена на 487 предметах вики, совпало в >97%):
    [6] вид (18 меч, 19 топор, 20 копьё, 21 лук, 22 посох, 23 щит, 24 большой щит, 25 аксессуар)
    [8] младшие 16 бит / старшие 16 бит: оружие — физ. атака / маг. атака; щит — физ. защита / шанс блока;
        аксессуар — физ. защита / маг. защита
    [10] цена, [11] цена продажи, [12] номер навыка предмета (BT_SKILLID)
    [16..23], [24..31], [32..39] — три слота доп. статов: (номер стата, float значение, …)
- расходники, ключевые предметы и записи без характеристик (пустые/«-»/DUMMY) не переносятся.

Результат — только ДОПОЛНЕНИЕ data/items.json (+ навыки/пассивки/перевод), чужие правки не трогаются;
сведения об извлечённом — docs/uo/items_game.json.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from tools import uo_items, uo_import  # noqa: E402
from tools.uo_extract import auto_map  # noqa: E402

DATA, DOCS = ROOT / "data", ROOT / "docs" / "uo"
KINDS = {18: "sword", 19: "axe", 20: "spear", 21: "bow", 22: "staff", 23: "shield", 24: "greatshield",
         25: "accessory"}
STRIDE, SIGNATURE = 46, [0, 0, 282, 0, 0, 0, 18, 1, 8, 0, 500, 50]     # запись Bronze Sword
BLOCKS = (16, 24, 32)


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower().replace("�", "").replace("’", ""))


def find_table(words: np.ndarray) -> int:
    """Номер слова, с которого начинается запись предмета 282 (Bronze Sword), по сигнатуре."""
    head = np.where(words == 282)[0]
    for p in head:
        start = int(p) - 2
        if start >= 0 and words[start:start + len(SIGNATURE)].tolist() == SIGNATURE \
                and words[start + STRIDE + 2] == 283:
            return start
    raise SystemExit("таблица предметов не найдена: образ другой версии?")


def read_names(sheet: Path) -> list[str]:
    data = sheet.read_bytes()
    start = next(i for i in range(0x20, len(data)) if data[i])
    return [b.decode("utf-8", "replace") for b in data[start:].split(b"\0")]


def stat_names(entries: list[dict], blocks: dict[int, list[tuple[int, float]]]) -> dict[int, tuple[str, str, bool]]:
    """Номер стата -> (название, знак, проценты) по предметам вики, чьи статы известны."""
    votes: dict[int, Counter] = defaultdict(Counter)
    for idx, entry in blocks.items():
        lines = entry["lines"]
        found = entry["blocks"]
        if len(lines) != len(found):
            continue
        for line, (sid, _value) in zip(lines, found):
            m = re.match(r"^(.*?)\s*([+-])\s*(\d+(?:\.\d+)?)\s*(%?)\s*$", line)
            if m:
                votes[sid][(m.group(1).strip(), m.group(2), bool(m.group(4)))] += 1
                continue
            n = re.search(r"\d+(?:\.\d+)?", line)         # «Heal 10% HP when…», «Takes 20% Less Damage»
            if n:
                votes[sid][(line[:n.start()] + "{n}" + line[n.end():], "T", "%" in line[n.end():n.end() + 1])] += 1
            else:                                               # «Poison Immunity»
                votes[sid][(line, "R", False)] += 1
    return {sid: c.most_common(1)[0][0] for sid, c in votes.items()}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", required=True, type=Path)
    ap.add_argument("--text", required=True, type=Path, help="распакованный Unicorn_US.CPK")
    ap.add_argument("--enum", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    image = args.main.read_bytes()
    words = np.frombuffer(image[:len(image) // 4 * 4], "<u4").astype(np.int64)
    table = find_table(words)
    names = read_names(args.text / "MsgSheet" / "UcItemList.fms")
    offset = names.index("Bronze Sword", 100) - 282
    enum_path = args.enum or args.text / "Debug" / "_UcEnum_Item.inc"
    internal = [m.group(1) for line in enum_path.read_text(encoding="utf-8-sig").splitlines()[1:]
                if (m := re.match(r"([A-Z0-9_]+)\s*,", line))]
    start_id, end_id = internal.index("WEAPON_START"), internal.index("ACCESSORY_END")
    skill_names = auto_map.align_names(args.text)          # английское название -> внутреннее имя
    skill_enum = [ln.split(",")[0].strip() for ln in
                  (args.text / "Debug" / "_UcEnum_Skill.inc").read_text(encoding="utf-8-sig").splitlines()[1:]]
    sheet_names = read_names(args.text / "MsgSheet" / "UcSkillList.fms")
    eng_by_norm = {}
    for t in sheet_names:
        t2 = re.sub(r"^\((A|P)\) ", "", t)
        eng_by_norm.setdefault(auto_map.norm(t2), t2)

    eng_by_internal = {v: eng_by_norm[k] for k, v in skill_names.items() if k in eng_by_norm}

    def skill_name(sid: int) -> str | None:
        if not 0 < sid < len(skill_enum):
            return None
        return eng_by_internal.get(re.sub(r"^(ACT|PAS)_", "", skill_enum[sid]))

    wiki = json.loads((DOCS / "items.json").read_text(encoding="utf-8"))
    known = {norm(i["name"]) for i in wiki["items"]}
    wiki_by_name = {norm(i["name"]): i for i in wiki["items"]}

    rows = {}
    for idx in range(start_id + 1, end_id):
        if internal[idx].endswith(("_START", "_END")):
            continue
        name = names[idx + offset].replace("�", "'")
        if name in ("", "-", "DUMMY", "None"):
            continue
        r = words[table + (idx - 282) * STRIDE: table + (idx - 281) * STRIDE]
        if int(r[2]) != idx or int(r[6]) not in KINDS:
            continue
        kind = KINDS[int(r[6])]
        lo, hi = int(r[8]) & 0xFFFF, int(r[8]) >> 16
        entry = {"id": idx, "internal": internal[idx], "name": name, "kind": kind, "phys_atk": 0, "mag_atk": 0,
                 "phys_def": 0, "mag_def": 0, "guard_rate": 0, "price": int(r[10]), "skill_id": int(r[12]),
                 "blocks": [(int(r[k]), struct.unpack("<f", struct.pack("<I", int(r[k + 1])))[0])
                            for k in BLOCKS if int(r[k])]}
        if kind in ("sword", "axe", "spear", "bow"):
            entry["phys_atk"], entry["mag_atk"] = lo, hi
        elif kind == "staff":
            entry["phys_atk"], entry["mag_atk"] = lo, hi
        elif kind in ("shield", "greatshield"):
            entry["phys_def"], entry["guard_rate"] = lo, hi
        else:
            entry["phys_def"], entry["mag_def"] = lo, hi
        rows[idx] = entry

    # номер стата -> текст: учимся на предметах, которые есть и в игре, и в вики
    learn = {i: {"lines": wiki_by_name[norm(e["name"])]["stats"], "blocks": e["blocks"]}
             for i, e in rows.items() if norm(e["name"]) in wiki_by_name and wiki_by_name[norm(e["name"])]["stats"]}
    stats = stat_names(list(learn.values()), learn)
    # иммунитеты идут подряд: 64 яд, 65 ожог, 66 заморозка, 67 оглушение, 68 слепота, 69 смертельный удар,
    # 70 печать защиты, 71 печать пассивок, 72 дебафф; 73 — «Affliction Immunity» (число предметов совпало: 6)
    stats.setdefault(73, ("Affliction Immunity", "R", False))

    def stat_line(sid: int, value: float) -> str | None:
        if sid not in stats:
            return None
        label, sign, percent = stats[sid]
        if sign == "R":
            return label
        if sign == "T":
            number = round(value * 100) if percent else (int(value) if float(value).is_integer() else value)
            return label.replace("{n}", str(number))
        number = round(value * 100) if percent else (int(value) if float(value).is_integer() else value)
        return f"{label} {sign}{number}{'%' if percent else ''}"

    new, skipped, unknown_stats = {}, Counter(), Counter()
    seen = Counter()
    for idx, e in rows.items():
        if norm(e["name"]) in known:
            continue
        lines = []
        for sid, value in e["blocks"]:
            line = stat_line(sid, value)
            if line:
                lines.append(line)
            else:
                unknown_stats[sid] += 1
        sname = skill_name(e["skill_id"]) if e["skill_id"] else None
        has = any(e[k] for k in ("phys_atk", "mag_atk", "phys_def", "mag_def", "guard_rate")) or lines or sname
        if not has:
            skipped["без характеристик"] += 1
            continue
        seen[e["name"]] += 1
        name = e["name"] if seen[e["name"]] == 1 else f"{e['name']} {'I' * seen[e['name']]}"
        new[idx] = {"name": name, "kind": e["kind"], **{k: e[k] for k in
                    ("phys_atk", "mag_atk", "phys_def", "mag_def", "guard_rate")},
                    "skills": [sname] if sname else [], "skill_cost": "", "stats": lines, "price": e["price"],
                    "classes": "", "game_id": idx, "game_internal": e["internal"]}
    print(f"снаряжения в игре: {len(rows)}; статов по номерам выучено: {len(stats)}; "
          f"новых предметов: {len(new)}; пропущено: {dict(skipped)}; неизвестных статов: {dict(unknown_stats)}")
    (DOCS / "items_game.json").write_text(json.dumps(
        {"source": "таблица предметов в данных main + UcItemList.fms", "stat_ids": {str(k): list(v) for k, v in stats.items()},
         "new_items": list(new.values())}, indent=1, ensure_ascii=False), encoding="utf-8")
    if args.dry_run or not new:
        return

    # --- сборка тем же кодом, что при импорте: тиры считаются по всему списку, добавляются только новые ---
    classes_ref = json.loads((DOCS / "classes.json").read_text(encoding="utf-8"))
    grades = {k: v for k, v in json.loads((DATA / "grades.json").read_text(encoding="utf-8")).items()
              if not k.startswith("_")}
    importer = uo_import.Importer(classes_ref, grades)
    importer.classes()
    importer.skills_and_passives()
    combined = {"items": wiki["items"] + list(new.values()), "skills": wiki["skills"]}
    items, passives, skills, ru = uo_items.build(combined, importer, importer.skills, importer.passives)
    cur = {n: json.loads((DATA / f"{n}.json").read_text(encoding="utf-8")) for n in ("items", "skills", "passives")}
    added = Counter()
    for entry in new.values():
        key = uo_items.slug(entry["name"])
        if key in cur["items"] or key not in items:
            continue
        cur["items"][key] = items[key]
        added["items"] += 1
        for sid in items[key]["skills"]:
            if sid not in cur["skills"] and sid in (skills or importer.skills):
                cur["skills"][sid] = (skills or importer.skills)[sid]; added["skills"] += 1
        for pid in items[key]["passives"]:
            if pid not in cur["passives"] and pid in (passives or importer.passives):
                cur["passives"][pid] = (passives or importer.passives)[pid]; added["passives"] += 1
    for n, obj in cur.items():
        (DATA / f"{n}.json").write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lang_path = DATA / "lang" / "ru.json"
    lang = json.loads(lang_path.read_text(encoding="utf-8"))
    for key, value in ru.items():
        lang.setdefault(key, value)
    lang_path.write_text(json.dumps(lang, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("добавлено:", dict(added))


if __name__ == "__main__":
    main()
