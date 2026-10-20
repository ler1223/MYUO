"""Навыки и пассивки UO из файлов игры: добавить те, которых нет в данных (вики их не знает).

    python tools/uo_skills_game.py --main <образ main> --text <папка Unicorn_US> [--dry-run]

Откуда что:
- список навыков — Debug/_UcEnum_Skill.inc (BT_SKILLID: ACT_* активные, PAS_* пассивки), английские
  названия — MsgSheet/UcSkillList.fms (сопоставление — auto_map.align_names);
- числа — таблица навыков в данных исполняемого файла: записи по 76 слов (u32), слово 3 — номер навыка.
  Раскладка (проверена на 200 навыках вики, hits и accuracy совпали в >99%):
    [1] флаги (бит 0x1 — дальнобойный), [5] старшие 16 бит — стоимость AP, [6] — стоимость PP,
    [9] float физ. мощь, [10] float маг. мощь, [11] младшие 16 бит — число ударов, старшие — точность;
- описание — тот же UcSkillList.fms: активные — строка (957 + номер), пассивки — строка условия
  (1428 + номер) и строка действия (смещение определяется по навыкам вики). Числа в строках игры
  заменены подстановками «%s» — они лежат в бинарных таблицах, которые не разобраны, поэтому эффекты,
  зависящие от числа («Ignores %s Defense»), сохраняют только то, что видно из текста: это
  приближение, оно помечено в docs/uo/skills_game.json.

Результат — ДОПОЛНЕНИЕ data/skills.json, data/passives.json, data/lang/ru.json; чужие правки не трогаются.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from tools import uo_items, uo_import  # noqa: E402
from tools.uo_extract import auto_map  # noqa: E402

DATA, DOCS = ROOT / "data", ROOT / "docs" / "uo"
STRIDE = 76
SIGNATURE = [0, 1025, 0, 171, 21, 65536, 0, 1, 0, 1123024896]      # Power Bolt


def f32(x: int) -> float:
    return struct.unpack("<f", struct.pack("<I", int(x)))[0]


def clean(text: str) -> str:
    text = re.sub(r"#c\(\d+\)(.*?)#/c", r"\1", text, flags=re.S)
    text = re.sub(r"#\(5[67]\)\s*(AP|PP)", r"\1", text)
    text = re.sub(r"#\(\d+\)", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


PCT_TYPES = {43, 224, 136, 229, 137, 130, 129}     # выучено по навыкам вики: значение — доля (0.15 -> 15%)
RAW_TYPES = {120, 84, 83, 114, 166, 123, 206, 220, 214, 105}   # значение — число как есть (потенция, AP/PP)


def fill(text: str, record) -> tuple[str, bool]:
    """Подставить числа из блоков эффектов записи (слова 17/26/35: тип, float значение) вместо «%s».
    Подстановка только когда число подстановок равно числу ненулевых блоков — иначе текст не трогается."""
    slots = text.count("%s")
    if not slots:
        return text, True
    values = []
    for off in (17, 26, 35):
        t, v = int(record[off]), f32(record[off + 1])
        if t and v and abs(v) < 100000:
            pct = t in PCT_TYPES or (t not in RAW_TYPES and 0 < abs(v) <= 1.5 and v != int(v))
            values.append(f"{round(v * 100)}%" if pct else f"{v:+g}".replace("+-", "-"))
    if len(values) != slots:
        return text, False
    it = iter(values)
    return re.sub(r"%s", lambda m: next(it), text), True


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", required=True, type=Path)
    ap.add_argument("--text", required=True, type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="заменить ранее добавленные из игры навыки")
    args = ap.parse_args()

    image = args.main.read_bytes()
    words = np.frombuffer(image[:len(image) // 4 * 4], "<u4").astype(np.int64)
    base = None
    for p in np.where(words == 171)[0]:
        s = int(p) - 3
        if s >= 0 and words[s:s + len(SIGNATURE)].tolist() == SIGNATURE and words[s + STRIDE + 3] == 172:
            base = s
            break
    if base is None:
        raise SystemExit("таблица навыков не найдена: образ другой версии?")

    def record(sid: int) -> np.ndarray:
        return words[base + (sid - 171) * STRIDE: base + (sid - 170) * STRIDE]

    sheet = args.text / "MsgSheet" / "UcSkillList.fms"
    data = sheet.read_bytes()
    start = next(i for i in range(0x20, len(data)) if data[i])
    P = [b.decode("utf-8", "replace") for b in data[start:].split(b"\0")]
    names = auto_map.align_names(args.text)                          # norm(eng) -> внутреннее имя
    enum = [ln.split(",")[0].strip() for ln in (args.text / "Debug" / "_UcEnum_Skill.inc")
            .read_text(encoding="utf-8-sig").splitlines()[1:]]
    index = {re.sub(r"^(ACT|PAS)_", "", e): i for i, e in enumerate(enum[:471])}
    eng = {}
    for t in P:
        t2 = re.sub(r"^\((A|P)\) ", "", t).replace("�", "'")
        eng.setdefault(auto_map.norm(t2), t2)
    inner_to_eng = {v: eng[k] for k, v in names.items() if k in eng}

    # --- смещения строк описаний по навыкам вики ---
    wiki = json.loads((DOCS / "classes.json").read_text(encoding="utf-8"))["skills"]
    norm = lambda t: re.sub(r"#\(\d+\)|#c\(\d+\)|%s|[^a-z]", "", t.lower())      # noqa: E731
    votes = {"active": collections.Counter(), "p1": collections.Counter(), "p2": collections.Counter()}
    for n, s in wiki.items():
        k = auto_map.norm(n)
        if k not in names or names[k] not in index:
            continue
        sid, lines = index[names[k]], s["text"].split("\n")
        key = norm(lines[0])
        if s["category"] == "active" and len(norm(s["text"])) >= 40:
            for j in range(900, 1500):
                if norm(P[j]) == norm(s["text"]):
                    votes["active"][j - sid] += 1
        if s["category"] == "passive" and len(key) >= 20:
            for j in range(1400, len(P)):
                if norm(P[j].split("\n")[0]) == key:
                    votes["p1"][j - sid] += 1
    off_a = votes["active"].most_common(1)[0][0]
    off_p = votes["p1"].most_common(1)[0][0]
    p2 = collections.Counter()
    for n, s in wiki.items():
        k = auto_map.norm(n)
        if k in names and names[k] in index and s["category"] == "passive" and len(s["text"].split("\n")) > 1:
            second = norm(s["text"].split("\n")[1])
            if len(second) < 20:
                continue
            for j in range(off_p + 400, len(P)):
                if norm(P[j]) == second:
                    p2[j - index[names[k]]] += 1
    off_e = p2.most_common(1)[0][0] if p2 else None
    print(f"смещения описаний: активные {off_a}, пассивки {off_p}, действие {off_e}")

    sk = json.loads((DATA / "skills.json").read_text(encoding="utf-8"))
    ps = json.loads((DATA / "passives.json").read_text(encoding="utf-8"))
    previous = DOCS / "skills_game.json"
    if args.refresh and previous.exists():          # пересобрать ранее добавленные из игры
        for key, old in json.loads(previous.read_text(encoding="utf-8")).items():
            (sk if old["category"] == "active" else ps).pop(key, None)
    entries = {}
    for sid, e in enumerate(enum[:471]):
        m = re.match(r"^(ACT|PAS)_(.+)$", e)
        if not m or e.endswith(("_START", "_END")) or e.startswith("ACT_ASSIST"):
            continue
        name = inner_to_eng.get(m.group(2))
        if not name or not re.search(r"[A-Za-z]{3}", name):
            continue
        key = uo_items.slug(name)
        if key in sk or key in ps or key in entries:
            continue
        r = record(sid)
        if int(r[3]) != sid:
            continue
        active = m.group(1) == "ACT"
        phys, mag = f32(r[9]), f32(r[10])
        text = clean(P[off_a + sid]) if active else clean("\n".join(
            x for x in (P[off_p + sid], P[off_e + sid] if off_e else "") if x))
        if re.fullmatch(r"[?\s]*", text):
            continue
        text, filled = fill(text, r)
        entries[key] = {"name": name, "level": 1, "type": "Attack" if phys or mag else "Support",
                        "category": "active" if active else "passive", "ap": (int(r[5]) >> 16) if active else 0,
                        "pp": int(r[6]), "phys": round(phys) or None, "mag": round(mag) or None,
                        "hits": (int(r[11]) & 0xFFFF) or None, "accuracy": (int(r[11]) >> 16) or None,
                        "traits": ["Ranged"] if int(r[1]) & 1 else [], "text": text, "game_id": sid, "numbers_filled": filled,
                        "game_internal": e}
    print(f"навыков игры, которых нет в данных: {len(entries)} "
          f"(активных {sum(1 for v in entries.values() if v['category'] == 'active')})")
    (DOCS / "skills_game.json").write_text(json.dumps(entries, indent=1, ensure_ascii=False), encoding="utf-8")
    if args.dry_run:
        return

    classes_ref = json.loads((DOCS / "classes.json").read_text(encoding="utf-8"))
    grades = {k: v for k, v in json.loads((DATA / "grades.json").read_text(encoding="utf-8")).items()
              if not k.startswith("_")}
    importer = uo_import.Importer(classes_ref, grades)
    importer.classes()
    importer.skills_and_passives()
    added = collections.Counter()
    for key, entry in entries.items():
        try:
            if entry["category"] == "active":
                sk[key] = importer.active(key, dict(entry))
                added["skills"] += 1
            else:
                ps[key] = {"name": entry["name"], "pp_cost": entry["pp"] or 1,
                           "reaction": importer.passive(key, dict(entry))}
                added["passives"] += 1
        except Exception as error:                      # одиночный неразобранный навык не должен валить импорт
            print("пропущен", key, type(error).__name__, error)
            added["failed"] += 1
    # побочные навыки/эффекты, на которые ссылаются разобранные пассивки (heal_… и т.п.)
    ef_path = DATA / "effects.json"
    effects = json.loads(ef_path.read_text(encoding="utf-8"))
    for key, value in importer.skills.items():
        if key not in sk and key not in entries:
            sk[key] = value; added["side_skills"] += 1
    for key, value in importer.effects.items():
        if key not in effects:
            effects[key] = value; added["effects"] += 1
    ef_path.write_text(json.dumps(effects, indent=2, ensure_ascii=False) + chr(10), encoding="utf-8")
    (DATA / "skills.json").write_text(json.dumps(sk, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (DATA / "passives.json").write_text(json.dumps(ps, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lang_path = DATA / "lang" / "ru.json"
    lang = json.loads(lang_path.read_text(encoding="utf-8"))
    for key, value in importer.ru.items():
        lang.setdefault(key, value)
    lang_path.write_text(json.dumps(lang, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # --- навыки предметов, ждавшие этих данных ---
    items = json.loads((DATA / "items.json").read_text(encoding="utf-8"))
    ref = json.loads((DOCS / "items.json").read_text(encoding="utf-8"))["items"]
    game = json.loads((DOCS / "items_game.json").read_text(encoding="utf-8"))["new_items"]
    for entry in ref + game:
        item = items.get(uo_items.slug(entry["name"]))
        if not item:
            continue
        for sname in entry.get("skills", []):
            k = uo_items.slug(sname)
            if k in sk and k not in item["skills"]:
                item["skills"].append(k); added["item_skill_links"] += 1
            elif k in ps and k not in item["passives"]:
                item["passives"].append(k); added["item_passive_links"] += 1
    (DATA / "items.json").write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("добавлено:", dict(added))


if __name__ == "__main__":
    main()
