"""Оценка построения: сила бойца и отряда числом (формула) — для интерфейса, подбора и баланса.

Формула (веса — data/rating.json):
  стойкость  = HP * (1 + средняя защита / defence_ref) * (1 + уклонение / 100) * (1 + блок / guard_ref)
  натиск     = AP и PP за бой тратятся на навыки с лучшей ценностью за очко; ценность применения =
               сумма частей навыка: урон (атака - enemy_defence, не меньше min_damage_share атаки) * сила,
               лечение — атака * сила * heal; * удары * цели (клетки области, не больше targets_cap)
               * точность * средний множитель крита; навык без урона и лечения — support за эффект
  скорость   = 1 + инициатива / speed_ref
  сила бойца = scale * sqrt(стойкость * натиск * скорость) + passive * открытые пассивки
Отряд: стойкость каждого бойца умножается на вес его ряда (rows: передний принимает удары), затем
сила = scale * sqrt(сумма стойкостей * сумма натисков * средняя скорость) + пассивки. Поэтому танк
впереди даёт больше, чем маг впереди. Проверка формулы боями — tools/rate_builds.py.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from .database import DEFAULT_DATA_DIR, Database
from .definitions import SkillDefinition
from .stats import Stat
from .unit import Unit

RATING_PATH = DEFAULT_DATA_DIR / "rating.json"
DEFAULTS = {"scale": 1.0, "defence_ref": 20, "guard_ref": 200, "enemy_defence": 8, "min_damage_share": 0.2,
            "targets_cap": 3, "heal": 0.8, "support": 6, "speed_ref": 40, "passive": 4, "rows": [1.3, 0.9, 0.7]}


def load_weights(path: Path = RATING_PATH) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {**DEFAULTS, **{k: v for k, v in data.items() if not k.startswith("_")}}


@dataclass(frozen=True)
class Rating:
    """Сила и её составляющие (чтобы объяснить число в подсказке)."""

    power: int
    defence: float
    offence: float
    speed: float
    passives: int


def defence(unit: Unit, w: Mapping[str, Any]) -> float:
    s = unit.stat
    armour = (s(Stat.PHYS_DEF) + s(Stat.MAG_DEF)) / 2
    return s(Stat.HP) * (1 + armour / w["defence_ref"]) * (1 + max(0, s(Stat.EVASION)) / 100) \
        * (1 + max(0, s(Stat.GUARD_RATE)) / w["guard_ref"])


def skill_value(unit: Unit, skill: SkillDefinition, db: Database, w: Mapping[str, Any]) -> float:
    """Ценность одного применения навыка."""
    s = unit.stat
    crit = 1 + max(0, min(100, s(Stat.CRIT_RATE))) / 100 * max(0, s(Stat.CRIT_DAMAGE) / 100 - 1)
    area = db.areas.get(skill.area)
    targets = min(len(area.cells) if area else 1, w["targets_cap"])
    hit = max(0.0, min(1.5, skill.accuracy / 100 * s(Stat.ACCURACY) / 100))
    value = 0.0
    for part in skill.parts:
        attack = sum(s(scale.stat) * scale.coef for scale in part.scaling)
        if part.kind == "heal":
            value += attack * part.power * w["heal"]
        else:
            value += max(attack - w["enemy_defence"], attack * w["min_damage_share"]) * part.power * crit * hit
    value *= skill.hits * targets
    if not skill.parts:
        value = w["support"] * max(1, len(skill.applies))
    return value


def offence(unit: Unit, db: Database, w: Mapping[str, Any]) -> float:
    """Натиск за бой: запас AP и PP тратится на навыки с лучшей ценностью за очко."""
    skills = [db.skills[i] for i in unit.skill_ids if i in db.skills]
    total = 0.0
    for pool, cost in ((unit.ap_max, "ap_cost"), (unit.pp_max, "pp_cost")):
        usable = [(skill_value(unit, sk, db, w), getattr(sk, cost)) for sk in skills if getattr(sk, cost) > 0]
        left = pool
        for value, price in sorted(usable, key=lambda v: -v[0] / v[1]):
            uses = left // price
            total += uses * value
            left -= uses * price
    return total


def rate_unit(unit: Unit, db: Database, w: Optional[Mapping[str, Any]] = None) -> Rating:
    w = w or load_weights()
    d, o = defence(unit, w), offence(unit, db, w)
    speed = 1 + max(0, unit.stat(Stat.INITIATIVE)) / w["speed_ref"]
    passives = len(unit.passive_ids)
    power = w["scale"] * math.sqrt(max(0.0, d * o * speed)) + w["passive"] * passives
    return Rating(round(power), d, o, speed, passives)


def rate_squad(units: Sequence[tuple[Unit, int]], db: Database, w: Optional[Mapping[str, Any]] = None) -> Rating:
    """units: (боец, ряд). Стойкость взвешивается по ряду: передний ряд принимает удары."""
    w = w or load_weights()
    if not units:
        return Rating(0, 0.0, 0.0, 1.0, 0)
    rows = list(w["rows"])
    total_d = total_o = total_s = 0.0
    passives = 0
    for unit, row in units:
        total_d += defence(unit, w) * rows[min(row, len(rows) - 1)]
        total_o += offence(unit, db, w)
        total_s += 1 + max(0, unit.stat(Stat.INITIATIVE)) / w["speed_ref"]
        passives += len(unit.passive_ids)
    speed = total_s / len(units)
    power = w["scale"] * math.sqrt(max(0.0, total_d * total_o * speed)) + w["passive"] * passives
    return Rating(round(power), total_d, total_o, speed, passives)


def rate_formation(formation: Any, db: Database, w: Optional[Mapping[str, Any]] = None) -> Rating:
    """Сила отряда по его строю (squad.Formation)."""
    return rate_squad([(u, formation.position_of(u.uid)[0]) for u in formation.units], db, w)


# --- проверка боями ------------------------------------------------------------------

Roster = Sequence[tuple[str, int, Sequence[str], int, int]]   # (класс, уровень, снаряжение, ряд, колонна)


def build_squad(db: Database, roster: Roster, side: str, first_uid: int, size: Any = None):
    """Отряд из списка бойцов (без забега): классы создаются сразу со своей историей повышений."""
    from .squad import FormationSize
    from .world import Army
    army = Army(side, side)
    rows = max([r for _, _, _, r, _ in roster] + [db.formation.rows - 1]) + 1
    cols = max([c for _, _, _, _, c in roster] + [db.formation.cols - 1]) + 1
    squad = army.create_squad(side, side, size or FormationSize(rows, cols, rows * cols))
    for offset, (class_id, level, gear, row, col) in enumerate(roster):
        unit = army.recruit(db.create_unit(class_id, first_uid + offset, level, gear))
        army.assign(unit.uid, side, row, col)
    return squad


def simulate(db: Database, first: Roster, second: Roster, runs: int = 20, seed: int = 0) -> float:
    """Доля побед first над second; стороны по очереди нападают (у нападающего преимущество в ничьих)."""
    from .battle import BattleSimulation
    wins = 0.0
    for i in range(runs):
        a = build_squad(db, first, "first", 1)
        b = build_squad(db, second, "second", 500)
        attacker, defender = (a, b) if i % 2 == 0 else (b, a)
        sim = BattleSimulation(attacker, defender, db, seed=seed * 7919 + i)
        sim.run()
        if sim.winner_id == "first":
            wins += 1
        elif sim.winner_id is None:
            wins += 0.5
    return wins / runs


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Ранговая корреляция: 1 — формула упорядочивает так же, как бои; 0 — никак."""
    def ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2
            i = j + 1
        return out
    n = len(xs)
    if n < 2:
        return 0.0
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    var = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return cov / var if var else 0.0
