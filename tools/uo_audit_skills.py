"""Сверка data/skills.json и data/passives.json с каталогом UO (docs/uo/catalog/skills.json): числа из игры.

    python -X utf8 tools/uo_audit_skills.py

Сравнивает у каждой карточки каталога: цену AP и PP, число ударов, точность, силу физической и магической частей.
Известные и обоснованные расхождения перечислены в EXCEPTIONS (с причиной); всё остальное считается ошибкой данных
и печатается списком. Код возврата 1, если есть неучтённые расхождения (его проверяет tests/test_uo_audit.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CATALOG = BASE / "docs" / "uo" / "catalog" / "skills.json"

# id навыка -> {поле: причина}. Поля: ap, pp, hits, accuracy, phys, mag.
EXCEPTIONS: dict[str, dict[str, str]] = {
    "animated_dead": {"mag": "воскрешение с полным HP (revive_pct); мощность в записи игры — это лечение"},
}


def parts_power(skill: dict, category: str) -> float | None:
    powers = [p["power"] for p in skill["parts"] if p["kind"] in ("damage", "heal") and p["category"] == category]
    return round(sum(powers) * 100) if powers else None


def audit() -> list[str]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["skills"]
    skills = json.loads((BASE / "data" / "skills.json").read_text(encoding="utf-8"))
    passives = json.loads((BASE / "data" / "passives.json").read_text(encoding="utf-8"))
    problems = []
    for entry in catalog:
        sid = entry["implementation"].get("id")
        if not sid:
            problems.append(f"{entry['id']}: нет в данных")
            continue
        if entry["category"] == "passive":
            if sid in passives and passives[sid]["pp_cost"] != (entry["pp"] or 0) and sid not in EXCEPTIONS:
                problems.append(f"{sid}: PP пассивки {passives[sid]['pp_cost']}, в игре {entry['pp']}")
            reaction = (passives.get(sid) or {}).get("reaction") or {}
            helper = skills.get(reaction.get("skill_id") or "")
            if helper is not None and reaction["skill_id"].startswith(sid + "_"):   # навык-ответ пассивки
                for field, want in (("hits", entry["hits"] or 1), ("accuracy", entry["accuracy"] or 100)):
                    if helper[field] != want and field not in EXCEPTIONS.get(sid, {}):
                        problems.append(f"{reaction['skill_id']}: {field} = {helper[field]}, в игре {want}")
                if entry["phys"] and parts_power(helper, "physical") != entry["phys"]:
                    problems.append(f"{reaction['skill_id']}: phys = {parts_power(helper, 'physical')}, в игре {entry['phys']}")
                if entry["mag"] and parts_power(helper, "magical") != entry["mag"]:
                    problems.append(f"{reaction['skill_id']}: mag = {parts_power(helper, 'magical')}, в игре {entry['mag']}")
            continue
        data = skills.get(sid)
        if data is None:
            continue
        checks = {
            "ap": (data["ap_cost"], entry["ap"]),
            "pp": (data["pp_cost"], entry["pp"] or 0),
            "hits": (data["hits"], entry["hits"] or 1),
            "accuracy": (data["accuracy"], entry["accuracy"] or 100),
        }
        # мощность: физическая часть и магическая (лечение считается магической частью)
        if entry["phys"]:
            checks["phys"] = (parts_power(data, "physical"), entry["phys"])
        if entry["mag"]:
            checks["mag"] = (parts_power(data, "magical"), entry["mag"])
        for field, (have, want) in checks.items():
            if have != want and field not in EXCEPTIONS.get(sid, {}):
                problems.append(f"{sid}: {field} = {have}, в игре {want}")
    return problems


def main() -> int:
    problems = audit()
    for line in problems:
        print(line)
    print(f"расхождений: {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
