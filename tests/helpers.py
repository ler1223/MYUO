"""Общие заготовки для тестов."""
import copy
import json
from pathlib import Path

from game.combat import Battle as BattleSimulation
from game.database import Database
from game.editing import set_owners
from game.events import TurnStarted
from game.squad import Squad
from game.tower import TOWER_RULES_PATH

# Тесты работают на собственной замороженной копии данных (tests/data): папка data/ это
# песочница, которую правят редакторы, и её содержимое тестам не указ.
FIXTURE_DIR = Path(__file__).resolve().parent / "data"
DB = Database.load(FIXTURE_DIR)  # только для чтения; тесты, меняющие данные, берут DB.copy()

# Группы набора под семь классов фикстуры (data/tower.json ссылается на классы игры,
# которых в tests/data нет): у каждой группы свой пул из трёх классов.
DRAFT_GROUPS = (
    {"role": "warrior", "classes": ["goblin", "orc", "knight"]},
    {"role": "archer", "classes": ["archer", "rider", "goblin"]},
    {"role": "mage", "classes": ["mage", "cleric", "rider"]},
    {"role": "support", "classes": ["cleric", "goblin", "knight"]},
    {"role": "tank", "classes": ["knight", "orc", "goblin"]},
    {"role": "healer", "classes": ["cleric", "mage", "archer"]},
)


def tower_rules_data(**changes) -> dict:
    """data/tower.json с группами набора под фикстуру и правками верхнего уровня."""
    data = json.loads(TOWER_RULES_PATH.read_text(encoding="utf-8"))
    data["draft"] = dict(data["draft"], groups=copy.deepcopy(list(DRAFT_GROUPS)))
    for key, value in changes.items():
        data[key] = dict(data[key], **value) if isinstance(data.get(key), dict) else value
    return data


def plain_db() -> Database:
    """Копия данных без случайности в бою: точность 100, уклонение, крит и блок 0."""
    db = DB.copy()
    for unit_id, definition in list(db.units.items()):
        data = definition.to_dict()
        data["stats"].update(accuracy=100, evasion=0, crit_rate=0, guard_rate=0)
        db.update("units", unit_id, data)
    return db


def set_stats(db: Database, unit_id: str, **stats) -> None:
    data = db.units[unit_id].to_dict()
    data["stats"].update(stats)
    db.update("units", unit_id, data)


def add_skill(db: Database, skill_id: str, owners=(), **data) -> None:
    """Добавляет навык и выдаёт его классам owners."""
    db.update("skills", skill_id, {"name": skill_id, **data})
    set_owners(db, "units", skill_id, list(owners))


def rule(skill, **parts):
    return {"skill": skill, "self_condition": {"type": "always"}, "condition": {"type": "always"},
            "selector": "frontmost", **parts}


def squads(db, left, right):
    """Два отряда из списков (definition_id, level, row, col); uid идут подряд с 1."""
    result, uid = [], 1
    for squad_id, roster in (("a", left), ("b", right)):
        squad = Squad(squad_id, squad_id.upper())
        for definition_id, level, row, col in roster:
            squad.formation.place(db.create_unit(definition_id, uid, level), row, col)
            uid += 1
        result.append(squad)
    return result


def duel(db, left_id, right_id, seed=1, left_level=1, right_level=1):
    """Два отряда по одному юниту: uid 1 против uid 2."""
    a, b = squads(db, [(left_id, left_level, 0, 0)], [(right_id, right_level, 0, 0)])
    return BattleSimulation(a, b, db, seed=seed), a.formation.units[0], b.formation.units[0]


def turn_of(sim, uid):
    """Доигрывает до хода юнита и возвращает события этого хода."""
    while not sim.finished:
        events = sim.step()
        if TurnStarted(uid) in events:
            return events[events.index(TurnStarted(uid)):]
    raise AssertionError(f"unit {uid} never had a turn")


def only(db, unit, skill_id):
    """Оставляет юниту единственное правило: применять skill_id по первому подходящему."""
    from game.editing import set_tactics
    set_tactics(db, unit, [rule(skill_id)])
