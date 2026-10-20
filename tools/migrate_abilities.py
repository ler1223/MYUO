"""Перенос пассивок в навыки: data/passives.json -> data/skills.json (docs/uo/ABILITIES_DESIGN.md, шаг 3).

    python -X utf8 tools/migrate_abilities.py [--data data] [--write]

Без --write только отчёт. С --write:
- каждая пассивка становится навыком ``kind: passive`` (game/abilities.py: skill_from_passive): условие срабатывания —
  ``trigger``, тело навыка-ответа ``<пассивка>_*`` вливается в саму пассивку, остальные действия остаются ``steps``;
- навыки-ответы, влившиеся в пассивки, удаляются; passives.json удаляется;
- ключи привязок анимаций в data/uo_battle.json (``manual.skill_animations``, ``manual.classes.*.skills|timing``) с id
  навыка-ответа переименовываются в id пассивки; раздел ``skills`` этого файла надо пересобрать
  ``python tools/uo_battle/build.py``.
Отчёт сверяет роль цели и событие каждой пассивки с записью навыка в игре (docs/uo/catalog/skill_records.json).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from game.abilities import merge_passives  # noqa: E402

EVENT_ALIASES = {"before_skill|skill_used": ("before_skill", "skill_used")}


def load(path: Path):
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw), (2 if raw.startswith('{\n  "') else 1), raw.endswith("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=BASE / "data")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    directory = args.data
    passives_path = directory / "passives.json"
    if not passives_path.exists():
        print("passives.json нет — переносить нечего")
        return 0
    passives, _, _ = load(passives_path)
    skills, indent, newline = load(directory / "skills.json")
    data = {"skills": skills}
    for name in ("units", "items"):
        data[name] = load(directory / f"{name}.json")[0]
    before = set(skills)
    clashes = sorted(set(passives) & before)
    if clashes:
        print("ВНИМАНИЕ: id пассивок совпадают с id навыков (навык будет затёрт):", clashes)
    merge_passives(data, passives)
    new = data["skills"]
    absorbed = sorted(before - set(new))
    print(f"пассивок: {len(passives)}; навыков было {len(before)}, стало {len(new)}; влито навыков-ответов: {len(absorbed)}")
    print("с телом:", sum(1 for s in new.values() if s.get("body")), "| прикрытий:",
          sum(1 for s in new.values() if s.get("response") == "cover" and s.get("kind") == "passive"),
          "| только шаги:", sum(1 for s in new.values() if s.get("kind") == "passive" and not s.get("body")
                                 and s.get("response") != "cover"))

    records_path = BASE / "docs" / "uo" / "catalog" / "skill_records.json"
    if records_path.exists():
        records = json.loads(records_path.read_text(encoding="utf-8"))["skills"]
        mismatches = []
        for pid, skill in new.items():
            record = records.get(pid)
            if skill.get("kind") != "passive" or record is None or "trigger" not in record:
                continue
            want = record["trigger"].get("event")
            wanted = EVENT_ALIASES.get(want, (want,))
            if want and skill["trigger"]["event"] not in wanted:
                mismatches.append((pid, "событие", skill["trigger"]["event"], want))
            phase = record["trigger"].get("phase")
            if record["target"] == "attacker" and skill.get("target") not in ("attacker", None):
                mismatches.append((pid, "цель", skill.get("target"), "attacker"))
        print(f"расхождений с записями игры: {len(mismatches)}")
        for line in mismatches[:40]:
            print("  ", *line)

    if not args.write:
        print("\n(без --write ничего не записано)")
        return 0
    (directory / "skills.json").write_text(json.dumps(new, ensure_ascii=False, indent=indent) + ("\n" if newline else ""),
                                           encoding="utf-8", newline="")
    passives_path.unlink()
    config_path = directory / "uo_battle.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        manual = config.get("manual", {})
        owner = {}
        for gone in absorbed:
            host = next((pid for pid in passives if gone.startswith(pid + "_")), None)
            if host:
                owner[gone] = host
        for key in [k for k in list(manual.get("skill_animations", {})) if k in owner]:
            manual["skill_animations"].setdefault(owner[key], manual["skill_animations"][key])
            del manual["skill_animations"][key]
        for cls in manual.get("classes", {}).values():
            for field in ("skills", "timing", "skill_fx"):
                for key in [k for k in list(cls.get(field, {})) if k in owner]:
                    cls[field].setdefault(owner[key], cls[field][key])
                    del cls[field][key]
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nзаписано:", directory / "skills.json", "(passives.json удалён)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
