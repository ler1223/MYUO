"""Сохранение и загрузка расстановки: армии, отряды, тактики юнитов, свои навыки.

UnitState остаётся неизменным; изменённые тактики и эффекты лежат рядом с ним.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Optional, Union

from .database import Database
from .scenario import Scenario
from .tactics import TacticsSet
from .unit import Unit, UnitState
from .world import Army, WorldMap

DEFAULT_SETUP_PATH = Path(__file__).resolve().parent.parent / "saves" / "setup.json"


def unit_to_save(unit: Unit) -> dict[str, Any]:
    return {
        "state": asdict(unit.state),
        "effects": unit.save_effects(),
        # None = тактики по умолчанию из определения
        "tactics": unit.tactics.to_list() if unit.has_custom_tactics else None,
    }


def unit_from_save(db: Database, data: Mapping[str, Any]) -> Unit:
    unit = db.restore_unit(UnitState(**data["state"]), data.get("effects", ()))
    if data.get("tactics") is not None:
        unit.set_tactics(TacticsSet.from_list(data["tactics"]))
        for rule in unit.tactics.rules:
            if rule.skill_id not in db.skills:
                raise ValueError(f"{unit.label}: unknown skill {rule.skill_id!r} in saved tactics")
    return unit


def army_to_save(army: Army) -> dict[str, Any]:
    return {
        "id": army.id,
        "name": army.name,
        "units": [unit_to_save(u) for u in army.units.values()],
        "squads": [
            {
                "id": squad.id,
                "name": squad.name,
                "leader_uid": squad.leader_uid,
                "cells": [[u.uid, *squad.formation.position_of(u.uid)] for u in squad.formation.units],
            }
            for squad in army.squads.values()
        ],
    }


def army_from_save(db: Database, data: Mapping[str, Any]) -> Army:
    army = Army(data["id"], data["name"])
    for unit_data in data["units"]:
        army.recruit(unit_from_save(db, unit_data))
    for squad_data in data["squads"]:
        squad = army.create_squad(squad_data["id"], squad_data["name"])
        for uid, row, col in squad_data["cells"]:
            army.assign(uid, squad.id, row, col)
        squad.leader_uid = squad_data["leader_uid"]
    return army


def scenario_to_save(scenario: Scenario) -> dict[str, Any]:
    world = scenario.world
    return {
        "player": army_to_save(scenario.player),
        "enemy": army_to_save(scenario.enemy),
        "player_squad": scenario.player_squad.id,
        "enemy_squad": scenario.enemy_squad.id,
        "world": {
            "width": world.width,
            "height": world.height,
            "positions": {squad_id: list(pos) for squad_id, pos in world.positions.items()},
        },
    }


def scenario_from_save(db: Database, data: Mapping[str, Any]) -> Scenario:
    player = army_from_save(db, data["player"])
    enemy = army_from_save(db, data["enemy"])
    world = WorldMap(data["world"]["width"], data["world"]["height"])
    for squad_id, (x, y) in data["world"]["positions"].items():
        world.place(squad_id, x, y)
    return Scenario(player, enemy, world, player.squads[data["player_squad"]], enemy.squads[data["enemy_squad"]])


def clone_scenario(db: Database, scenario: Scenario) -> Scenario:
    """Независимая копия: бой портит копию, а не редактируемую расстановку."""
    return scenario_from_save(db, scenario_to_save(scenario))


def save_setup(path: Union[str, Path], db: Database, scenario: Scenario,
               settings: Optional[Mapping[str, Any]] = None) -> None:
    """settings: настройки приложения, не относящиеся к игре (например, язык)."""
    data = {
        "settings": dict(settings or {}),
        "custom_skills": db.save_custom_skills(),
        "scenario": scenario_to_save(scenario),
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_settings(path: Union[str, Path]) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8")).get("settings", {})


def load_setup(path: Union[str, Path], db: Database) -> Scenario:
    """Сначала регистрирует сохранённые навыки в db, затем восстанавливает сценарий."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    db.load_custom_skills(data.get("custom_skills", {}))
    return scenario_from_save(db, data["scenario"])
