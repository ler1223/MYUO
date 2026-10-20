"""Однократная миграция старых цепочек навыков в стандартные анимации.

Читает data/uo_battle.json, создаёт manual.animations (по одной на уникальную цепочку
класса) и manual.skill_animations (привязка навыка к анимации). Старые поля
manual.classes.<класс>.skills / timing / skill_fx не удаляются: показ использует новую
привязку, а старые значения остаются запасным вариантом.

Запуск: python tools/migrate_animations.py [--write]
Без --write только печатает, что будет сделано.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "data" / "uo_battle.json"
sys.path.insert(0, str(ROOT))


def migrate(config: dict) -> tuple[dict, dict]:
    manual = config.setdefault("manual", {})
    animations = dict(manual.get("animations") or {})
    skills = dict(manual.get("skill_animations") or {})
    # Старые композиты — такие же стандартные анимации, только с source_kind/source_name.
    for name, comp in (manual.get("composites") or {}).items():
        if not isinstance(comp, dict) or name in animations:
            continue
        if (comp.get("source_kind") or "unit") != "unit":
            continue
        animations[name] = {
            "class": comp.get("source_name") or comp.get("class") or "",
            "name": name,
            "parts": list(comp.get("parts") or []),
            "holds": {str(k): v for k, v in (comp.get("holds") or {}).items()},
            "tags": list(comp.get("tags") or []),
        }

    classes = config.get("classes") or {}
    manual_classes = (manual.get("classes") or {})
    # Уникальные цепочки внутри класса переиспользуются, чтобы не плодить копии.
    by_parts: dict[tuple[str, tuple[str, ...], tuple[tuple[int, float], ...]], str] = {}
    for name, anim in animations.items():
        key = (str(anim.get("class") or ""), tuple(anim.get("parts") or ()),
               tuple(sorted((int(k), float(v)) for k, v in (anim.get("holds") or {}).items())))
        by_parts.setdefault(key, name)

    for class_id, info in classes.items():
        chains = info.get("skills") or {}
        for skill_id, parts in chains.items():
            if skill_id in skills or not parts:
                continue
            timing = ((manual_classes.get(class_id) or {}).get("timing") or {}).get(skill_id) or {}
            holds = {int(k): float(v) for k, v in (timing.get("holds") or {}).items()}
            key = (class_id, tuple(str(p) for p in parts), tuple(sorted(holds.items())))
            name = by_parts.get(key)
            if name is None:
                name = f"{class_id}__{skill_id}"
                suffix = 2
                while name in animations:
                    name = f"{class_id}__{skill_id}_{suffix}"
                    suffix += 1
                animations[name] = {
                    "class": class_id,
                    "name": name,
                    "parts": [str(p) for p in parts],
                    "holds": {str(k): v for k, v in sorted(holds.items())},
                    "tags": [],
                }
                by_parts[key] = name
            skills[skill_id] = {
                "animation": name,
                "tags": [],
                "caster_fx": [],
                "target_fx": [],
                "trajectory": None,
                "rain": None,
            }

    manual["animations"] = {n: animations[n] for n in sorted(animations)}
    manual["skill_animations"] = {s: skills[s] for s in sorted(skills)}
    return animations, skills


def bind_item_skills(config: dict, animations: dict, skills: dict,
                     by_parts: dict) -> None:
    """Навыки предметов без своей цепочки получают стандартную анимацию класса, который
    может носить этот предмет: тип навыка выбирает фазу (атака/каст), как запасной вариант игры."""
    from game.database import Database
    db = Database.load()
    classes = config.get("classes") or {}
    manual_classes = (config.get("manual", {}).get("classes") or {})
    for item in db.items.values():
        for skill_id in item.skills:
            if skill_id in skills or skill_id not in db.skills:
                continue
            class_id = next((c for c in classes
                             if item.slot in (getattr(db.units.get(c), "slots", ()) or ())), None)
            if class_id is None:
                continue
            tags = set(db.skills[skill_id].tags)
            order = ("charge", "attack", "release", "stance") if "magic" in tags else \
                ("attack", "charge", "release", "stance")
            parts: list[str] = []
            for phase in order:
                parts = [p.rstrip("*") for p in (classes[class_id].get("phases", {}).get(phase) or [])
                         if str(p).strip()]
                if parts:
                    break
            if not parts:
                continue
            holds: dict[int, float] = {}
            timing = ((manual_classes.get(class_id) or {}).get("timing") or {}).get(skill_id) or {}
            holds = {int(k): float(v) for k, v in (timing.get("holds") or {}).items()}
            key = (class_id, tuple(parts), tuple(sorted(holds.items())))
            name = by_parts.get(key)
            if name is None:
                name = f"{class_id}__{skill_id}"
                suffix = 2
                while name in animations:
                    name = f"{class_id}__{skill_id}_{suffix}"
                    suffix += 1
                animations[name] = {
                    "class": class_id,
                    "name": name,
                    "parts": list(parts),
                    "holds": {str(k): v for k, v in sorted(holds.items())},
                    "tags": [],
                }
                by_parts[key] = name
            skills[skill_id] = {
                "animation": name,
                "tags": [],
                "caster_fx": [],
                "target_fx": [],
                "trajectory": None,
                "rain": None,
            }


def main(argv: list[str]) -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    animations, skills = migrate(config)
    manual = config.setdefault("manual", {})
    classes = config.get("classes") or {}
    by_parts: dict[tuple[str, tuple[str, ...], tuple[tuple[int, float], ...]], str] = {}
    for name, anim in animations.items():
        key = (str(anim.get("class") or ""), tuple(anim.get("parts") or ()),
               tuple(sorted((int(k), float(v)) for k, v in (anim.get("holds") or {}).items())))
        by_parts.setdefault(key, name)
    bind_item_skills(config, animations, skills, by_parts)
    manual["animations"] = {n: animations[n] for n in sorted(animations)}
    manual["skill_animations"] = {s: skills[s] for s in sorted(skills)}
    print(f"стандартных анимаций: {len(animations)}, привязанных навыков: {len(skills)}")
    if "--write" in argv:
        backup = CONFIG.with_suffix(CONFIG.suffix + ".bak")
        if CONFIG.exists() and not backup.exists():
            backup.write_text(CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
        CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"записано: {CONFIG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
