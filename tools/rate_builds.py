"""Проверка формулы силы (game/rating.py) боями.

    python tools/rate_builds.py classes [--level 10] [--rank 1] [--runs 10]
        каждый класс — отряд из трёх одинаковых бойцов (стартовое снаряжение ступени rank, ряды как
        в башне) — бьётся со всеми остальными; таблица: сила по формуле и доля побед, внизу ранговая
        корреляция (1 — формула упорядочивает классы так же, как бои)
    python tools/rate_builds.py save [saves/tower.json] [--runs 40]
        отряд забега против врагов текущего этажа: сила обеих сторон и доля побед

Веса формулы — data/rating.json; поправили — запустите снова.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from game import rating  # noqa: E402
from game.database import Database  # noqa: E402
from game.squad import FormationSize  # noqa: E402
from game.tower import DEFAULT_SAVE_PATH, TowerRules, TowerRun, preferred_cells  # noqa: E402


def starter(db: Database, class_id: str, rank: int) -> tuple[str, ...]:
    """Самый дешёвый предмет нужной ступени на каждый слот, кроме артефактов."""
    gear = []
    for slot in db.definition_for(class_id, db.lineage(class_id)).slots:
        fitting = [i for i in db.items.values() if i.slot == slot and i.rank == rank and slot != "artifact"]
        if fitting:
            gear.append(min(fitting, key=lambda i: (i.price, i.id)).id)
    return tuple(gear)


def trio(db: Database, class_id: str, level: int, rank: int) -> list:
    size = FormationSize(3, 3, 9)
    definition = db.definition_for(class_id, db.lineage(class_id))
    cells = preferred_cells(definition, size)[:3]
    level = max(level, db.promotion_level(class_id))
    return [(class_id, level, starter(db, class_id, rank), row, col) for row, col in cells]


def classes(args) -> None:
    db = Database.load()
    weights = rating.load_weights()
    ids = sorted(db.units)
    squads = {c: trio(db, c, args.level, args.rank) for c in ids}
    powers = {c: rating.rate_squad([(db.create_unit(cid, 1, lv, gear), row)
                                    for cid, lv, gear, row, _col in squads[c]], db, weights).power for c in ids}
    wins = {c: 0.0 for c in ids}
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            share = rating.simulate(db, squads[a], squads[b], args.runs, seed=i)
            wins[a] += share
            wins[b] += 1 - share
    games = len(ids) - 1
    print(f"{'класс':14}{'тир':>5}{'сила':>8}{'победы':>9}")
    for c in sorted(ids, key=lambda c: -wins[c]):
        print(f"{c:14}{db.units[c].tier:>5}{powers[c]:>8}{wins[c] / games:>9.0%}")
    corr = rating.spearman([powers[c] for c in ids], [wins[c] for c in ids])
    print(f"\nранговая корреляция силы и побед: {corr:+.2f}")


def save(args) -> None:
    db = Database.load()
    rules = TowerRules.load()
    run = TowerRun.from_dict(db, rules, json.loads(Path(args.path).read_text(encoding="utf-8")))
    ours = [(u.definition.id, u.state.level, [i for i in u.state.equipment if i], *run.squad.formation.position_of(u.uid))
            for u in run.fielded]
    theirs = [(c, lv, gear, row, col) for c, lv, gear, row, col in run.enemy_roster(db)]
    us = rating.rate_formation(run.squad.formation, db)
    them = rating.rate_squad([(db.create_unit(c, 1, lv, g), row) for c, lv, g, row, _col in theirs], db)
    share = rating.simulate(db, ours, theirs, args.runs)
    print(f"этаж {run.floor}: наш отряд {us.power}, враги {them.power}, победы {share:.0%} из {args.runs}")
    print("  (история повышений бойцов в симуляции берётся по первому пути к классу)")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")       # консоль Windows: русские подписи таблицы
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    one = sub.add_parser("classes")
    one.add_argument("--level", type=int, default=10)
    one.add_argument("--rank", type=int, default=1)
    one.add_argument("--runs", type=int, default=10)
    two = sub.add_parser("save")
    two.add_argument("path", nargs="?", default=str(DEFAULT_SAVE_PATH))
    two.add_argument("--runs", type=int, default=40)
    args = parser.parse_args()
    {"classes": classes, "save": save}[args.mode](args)


if __name__ == "__main__":
    main()
