"""Условия тактики по умолчанию навыков из записей игры (слова 45–47): ``default_tactic`` в data/skills.json.

    python -X utf8 tools/uo_default_tactics.py [--write]

Берёт ``default_conditions`` из docs/uo/catalog/skill_records.json (python tools/uo_skill_records.py) и записывает ключи
условий (game/conditions.py) в навык. Условия, которых нет в движке (служебные), и лишние сверх двух пропускаются.
У пассивки без своей строки в тактике бойца работают именно эти условия; у активного навыка они нужны для тактики
класса по умолчанию (``tools/uo_default_tactics.py`` её не пересобирает).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from game.conditions import FACTORS, check_conditions  # noqa: E402


def main(write: bool) -> int:
    path = BASE / "data" / "skills.json"
    raw = path.read_text(encoding="utf-8")
    skills = json.loads(raw)
    records = json.loads((BASE / "docs" / "uo" / "catalog" / "skill_records.json").read_text(encoding="utf-8"))["skills"]
    changed = skipped = 0
    for skill_id, record in records.items():
        skill = skills.get(skill_id)
        if skill is None:
            continue
        keys = [c["key"] for c in record["default_conditions"] if c["key"] in FACTORS and c["key"] != "story_only"][:2]
        try:
            check_conditions([FACTORS[k] for k in keys])
        except ValueError:                       # две условия одной группы: оставляем первое
            keys = keys[:1]
            skipped += 1
        if skill.get("default_tactic", []) != keys:
            changed += 1
            if keys:
                skill["default_tactic"] = keys
            else:
                skill.pop("default_tactic", None)
    print(f"навыков с изменённым default_tactic: {changed}; пар из одной группы урезано: {skipped}")
    if write:
        indent = 2 if raw.startswith('{\n  "') else 1
        path.write_text(json.dumps(skills, ensure_ascii=False, indent=indent) + ("\n" if raw.endswith("\n") else ""),
                        encoding="utf-8", newline="")
        print("записано")
    else:
        print("(без --write ничего не записано)")
    return 0


if __name__ == "__main__":
    sys.exit(main("--write" in sys.argv))
