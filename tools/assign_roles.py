"""Роли классов: башня делит классы на группы (воин, лучник, маг, поддержка, танк, целитель).

Набор ролей по классам живёт в data/units.json (поле "roles"; ролей у класса может быть
несколько); скрипт проставляет его по таблице соответствия (можно править руками).
Запуск без --write только показывает таблицу; с --write записывает data/units.json.

    python tools/assign_roles.py [--write]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from game.database import DEFAULT_DATA_DIR
from game.roles import ARCHER, HEALER, MAGE, SUPPORT, TANK, WARRIOR

# Классы каждой роли; класс может быть сразу в нескольких ролях (рыцарь — танк и поддержка,
# святой рыцарь — целитель и поддержка, шаман — маг и целитель).
ROLE_CLASSES = {
    WARRIOR: (
        "warrior", "gladiator", "housecarl", "sellsword", "swordfighter", "dark_knight",
        "doom_knight", "berserker", "breaker", "viking", "landsknecht", "sword_master",
        "dreadnought", "werelion", "werewolf", "feathersword", "elven_fencer",
    ),
    ARCHER: (
        "arbalist", "hunter", "gryphon_knight", "wyvern_knight",
        "shieldshooter", "sniper", "gryphon_master", "wyvern_master", "elven_archer",
    ),
    MAGE: ("wizard", "witch", "shaman", "sorceress", "warlock", "druid", "wereowl"),
    SUPPORT: ("thief", "knight", "radiant_knight", "rogue", "werefox"),
    TANK: (
        "fighter", "hoplite", "soldier", "knight",
        "vanguard", "legionnaire", "great_knight", "sergeant", "werebear",
    ),
    HEALER: ("cleric", "radiant_knight", "shaman", "bishop", "sainted_knight", "paladin"),
}

# Класс → роли в порядке групп башни.
CLASS_ROLES: dict[str, list[str]] = {}
for _role, _classes in ROLE_CLASSES.items():
    for _class_id in _classes:
        CLASS_ROLES.setdefault(_class_id, []).append(_role)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="записать data/units.json")
    args = parser.parse_args()

    path = Path(DEFAULT_DATA_DIR) / "units.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [c for c in data if not data[c].get("story") and c not in CLASS_ROLES]
    if missing:
        raise SystemExit(f"нет роли для классов: {sorted(missing)}")
    for class_id, roles in CLASS_ROLES.items():
        if class_id not in data:
            raise SystemExit(f"нет класса {class_id!r} в units.json")
        data[class_id]["roles"] = roles
        data[class_id].pop("role", None)
    # Старый формат (одна роль строкой) переводим в список у всех классов, включая сюжетные.
    for class_data in data.values():
        if "role" in class_data:
            old = class_data.pop("role")
            if old and "roles" not in class_data:
                class_data["roles"] = [old]
    for role, classes in ROLE_CLASSES.items():
        print(f"{role:8s} {len(classes):2d}  {' '.join(classes)}")
    several = {c: r for c, r in CLASS_ROLES.items() if len(r) > 1}
    if several:
        print("несколько ролей: " + ", ".join(f"{c} ({', '.join(r)})" for c, r in sorted(several.items())))
    if args.write:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"записано: {path}")


if __name__ == "__main__":
    main()
