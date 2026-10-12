"""Общие заготовки для тестов."""
from game.battle import BattleSimulation
from game.database import Database
from game.editing import set_owners
from game.events import TurnStarted
from game.squad import Squad

DB = Database.load()  # только для чтения; тесты, меняющие данные, берут DB.copy()


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
