"""Навыки предметов UO: докачать недостающие страницы вики, разобрать и подключить к предметам.

    python tools/uo_items_refresh.py [--dry-run]

Зачем: tools/uo_wiki.py забирает страницы навыков предметов, но у многих навыков вики даёт не шаблон
{{Skill InfoBox}}, а одну строку («Sanguine Attack - 100 Phys, 1 Hit, ... [1 AP]»), и такие навыки
терялись — предмет оставался без способности. Здесь разбираются оба вида, а результат добавляется
в данные ТОЛЬКО ДОПОЛНЯЯ (чужие правки data/*.json не трогаются): новые навыки/пассивки/эффекты,
у предметов — списки skills/passives.

Навыки без страницы в вики (их ~75: «Quick Barrier», «Spiked Blow»…) в игре есть, а чисел для них
в доступных данных нет. Они пишутся в docs/uo/item_skills_missing.json, а предмет получает
приближённый навык (если задан --approx) или остаётся без него.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from tools import uo_items, uo_import, uo_wiki  # noqa: E402

DATA = ROOT / "data"
DOCS = ROOT / "docs" / "uo"
PAGES = DOCS / "wiki" / "skills"
MISSING = DOCS / "item_skills_missing.json"


def oneline(name: str, text: str) -> dict | None:
    """«Name - 100 Phys, 1 Hit, Inflicts Burn [1 AP]» -> запись справочника навыка."""
    body = text.strip().split(" - ", 1)[-1] if " - " in text.strip()[:80] else text.strip()
    cost = re.search(r"\[(\d+)\s*(AP|PP)\]", body)
    phys = re.search(r"(\d+)\s*Phys", body)
    mag = re.search(r"(\d+)\s*Mag", body)
    hits = re.search(r"(\d+)\s*(?:True\s+)?Hits?\b", body)
    if not (cost or phys or mag):
        return None
    ap = int(cost.group(1)) if cost and cost.group(2) == "AP" else 0
    pp = int(cost.group(1)) if cost and cost.group(2) == "PP" else 0
    attack = bool(phys or mag)
    traits = [t for t, rx in (("Ranged", r"\bRanged\b"), ("Limited", r"\bLIMITED\b")) if re.search(rx, body)]
    clean = re.sub(r"\[\d+\s*(AP|PP)\]", "", body).strip(" .,")
    return {"name": name, "level": 1, "type": "Attack" if attack else "Support",
            "category": "active" if attack or ap else "passive", "ap": ap, "pp": pp or (0 if ap or attack else 1),
            "phys": int(phys.group(1)) if phys else None, "mag": int(mag.group(1)) if mag else None,
            "hits": int(hits.group(1)) if hits else (1 if attack else None), "accuracy": 100 if attack else None,
            "traits": traits, "text": clean}


def page_entry(name: str, text: str) -> dict | None:
    if text.lstrip().startswith("{{Skill InfoBox"):
        entry = uo_wiki.infobox(text)
        return {"name": name, "level": 1, "type": "", **entry} if entry["text"] else None
    return oneline(name, text)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    dry = "--dry-run" in sys.argv
    ref = json.loads((DOCS / "items.json").read_text(encoding="utf-8"))
    classes_ref = json.loads((DOCS / "classes.json").read_text(encoding="utf-8"))
    wanted = sorted({s for i in ref["items"] for s in i["skills"]} - set(ref["skills"]) - set(classes_ref["skills"]))
    PAGES.mkdir(parents=True, exist_ok=True)
    missing = {}
    for name in wanted:
        path = PAGES / f"{name}.wiki"
        if not path.exists():
            try:
                path.write_text(uo_wiki.get(name), encoding="utf-8")
            except (KeyError, OSError, ValueError):
                path.write_text("", encoding="utf-8")        # страницы нет — не спрашивать снова
            time.sleep(0.2)
        entry = page_entry(name, path.read_text(encoding="utf-8")) if path.read_text(encoding="utf-8") else None
        if entry:
            ref["skills"][name] = entry
        else:
            missing[name] = [i["name"] for i in ref["items"] if name in i["skills"]]
    print(f"навыков предметов без записи: {len(wanted)}; найдено в вики: {len(wanted) - len(missing)}; "
          f"без страницы: {len(missing)}")
    MISSING.write_text(json.dumps(missing, indent=1, ensure_ascii=False), encoding="utf-8")
    if dry:
        return
    (DOCS / "items.json").write_text(json.dumps(ref, indent=1, ensure_ascii=False), encoding="utf-8")

    # --- сборка предметов тем же кодом, что при полном импорте, но без перезаписи данных ---
    grades = {k: v for k, v in json.loads((DATA / "grades.json").read_text(encoding="utf-8")).items()
              if not k.startswith("_")}
    importer = uo_import.Importer(classes_ref, grades)
    importer.classes()
    importer.skills_and_passives()
    items, passives, skills, ru = uo_items.build(ref, importer, importer.skills, importer.passives)

    def load(name):
        return json.loads((DATA / name).read_text(encoding="utf-8"))

    def save(name, obj):
        (DATA / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    cur_items, cur_skills, cur_pas = load("items.json"), load("skills.json"), load("passives.json")
    cur_eff = load("effects.json")
    added = {"skills": 0, "passives": 0, "effects": 0, "items": 0}
    for key, value in skills.items():
        if key not in cur_skills:
            cur_skills[key] = value; added["skills"] += 1
    for key, value in passives.items():
        if key not in cur_pas:
            cur_pas[key] = value; added["passives"] += 1
    for key, value in importer.effects.items():
        if key not in cur_eff and any(key in json.dumps(v) for v in list(skills.values()) + list(passives.values())):
            cur_eff[key] = value; added["effects"] += 1
    for key, value in items.items():
        old = cur_items.get(key)
        if old is None:
            continue
        for field in ("skills", "passives"):
            if value[field] and value[field] != old.get(field):
                old[field] = value[field]; added["items"] += 1
    save("items.json", cur_items); save("skills.json", cur_skills); save("passives.json", cur_pas)
    save("effects.json", cur_eff)
    lang_path = DATA / "lang" / "ru.json"
    lang = json.loads(lang_path.read_text(encoding="utf-8"))
    for key, value in ru.items():
        lang.setdefault(key, value)
    lang_path.write_text(json.dumps(lang, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("добавлено:", added)


if __name__ == "__main__":
    main()
