"""Порядок в анимациях навыков: убрать пустые привязки и составить таблицу покрытия.

    python tools/uo_battle/fill_skill_animations.py            # отчёт
    python tools/uo_battle/fill_skill_animations.py --write    # убрать пустые записи, записать docs/uo/anim_coverage.md

Пустая запись `manual.skill_animations.<навык>` (ни анимации, ни эффектов, ни полёта, ни дождя, ни тегов)
показу ничего не даёт: без неё навык играется так же. Редактор показа (skill_editor.py) пишет их при каждом
сохранении, поэтому их накапливается много. Записи с содержимым не трогаются.

Покрытие: для каждого навыка и каждого класса, который его применяет (свой навык или навык предмета в слотах класса),
откуда берётся анимация тела — по порядку, как в battle/director.py (Director.chain):
  привязка — стандартная анимация навыка (manual.animations), собранная на модели этого класса;
  цепочка  — своя цепочка класса из файла игры (classes.<класс>.skills);
  общая    — обычная атака или каст класса.
Навыки-ответы пассивок (*_strike, *_heal, *_buff, *_curse) играют удар класса — это задумано.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from game.database import Database  # noqa: E402

CONFIG = ROOT / "data" / "uo_battle.json"
REPORT = ROOT / "docs" / "uo" / "anim_coverage.md"
RESPONSE_SUFFIXES = ("_strike", "_heal", "_buff", "_curse", "_pact", "_gift", "_revive")


def is_empty(spec: dict) -> bool:
    return not (spec.get("animation") or spec.get("tags") or spec.get("caster_fx") or spec.get("target_fx")
                or spec.get("trajectory") or spec.get("rain"))


def users(db: Database) -> dict[str, set[str]]:
    """навык -> классы, которые его применяют (свои навыки и навыки предметов, влезающих в слоты)."""
    out: dict[str, set[str]] = {}
    for class_id, unit in db.units.items():
        ids = [s if isinstance(s, str) else s["id"] for s in unit.skills]
        for item in db.items.values():
            if item.slot in unit.slots:
                ids.extend(item.skills)
        for skill_id in set(ids):
            out.setdefault(skill_id, set()).add(class_id)
    return out


def coverage(config: dict, db: Database) -> dict[str, dict[str, list[str]]]:
    manual = config.get("manual", {})
    animations, bound = manual.get("animations", {}), manual.get("skill_animations", {})
    result: dict[str, dict[str, list[str]]] = {}
    for skill_id, classes in sorted(users(db).items()):
        if skill_id not in db.skills:
            continue
        sources: dict[str, list[str]] = {"привязка": [], "цепочка": [], "общая": []}
        for class_id in sorted(classes):
            if class_id not in config.get("classes", {}):
                continue
            animation = animations.get((bound.get(skill_id) or {}).get("animation") or "")
            if animation and animation.get("class") == class_id and animation.get("parts"):
                sources["привязка"].append(class_id)
            elif config["classes"][class_id].get("skills", {}).get(skill_id):
                sources["цепочка"].append(class_id)
            else:
                sources["общая"].append(class_id)
        result[skill_id] = sources
    return result


def markdown(config: dict, db: Database, cover: dict) -> str:
    lines = ["# Покрытие анимаций навыков", "",
             "Собрано `python tools/uo_battle/fill_skill_animations.py --write`. Подробности — в докстринге скрипта.", ""]
    totals = {"привязка": 0, "цепочка": 0, "общая": 0}
    for sources in cover.values():
        for key, classes in sources.items():
            totals[key] += len(classes)
    lines += [f"Пар «класс — навык»: привязка {totals['привязка']}, цепочка класса {totals['цепочка']}, "
              f"общая атака или каст {totals['общая']}.", "",
              "## Навыки, у которых хоть у одного класса анимация общая", "",
              "Навыки-ответы пассивок сюда не входят: удар класса для них — задумка.", "",
              "| Навык | Вид | Область | Классов | Примеры |", "|---|---|---|---|---|"]
    for skill_id, sources in cover.items():
        if skill_id.endswith(RESPONSE_SUFFIXES) or not sources["общая"]:
            continue
        skill, info = db.skills[skill_id], config["skills"].get(skill_id, {})
        lines.append(f"| {skill_id} | {info.get('kind', '?')} | {skill.area} | {len(sources['общая'])} | "
                     f"{', '.join(sources['общая'][:4])} |")
    return "\n".join(lines) + "\n"


def main(write: bool) -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    bound = config.get("manual", {}).get("skill_animations", {})
    empty = [k for k, v in bound.items() if is_empty(v)]
    print(f"пустых привязок: {len(empty)} из {len(bound)}")
    db = Database.load()
    if write:
        for key in empty:
            bound.pop(key)
        CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=1), encoding="utf-8")
    cover = coverage(config, db)
    text = markdown(config, db, cover)
    if write:
        REPORT.write_text(text, encoding="utf-8")
        print("записано:", REPORT)
    else:
        print(text.split("\n\n")[1])
        print("(без --write ничего не записано)")
    return 0


if __name__ == "__main__":
    sys.exit(main("--write" in sys.argv))
