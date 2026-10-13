"""Сохранение и загрузка расстановки: армии, отряды, тактики юнитов, настройки.

UnitState остаётся неизменным; изменённые тактики и эффекты лежат рядом с ним.
Классы, предметы и навыки здесь не хранятся: они живут в data/ (см. Database).
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
SAVE_VERSION = 2  # меняется при несовместимых изменениях формата; чужие версии не читаются


def unit_to_save(unit: Unit) -> dict[str, Any]:
    return {
        "state": asdict(unit.state),
        "effects": unit.save_effects(),
        # None = тактики по умолчанию из определения
        "tactics": unit.tactics.to_list() if unit.has_custom_tactics else None,
    }


def unit_from_save(db: Database, data: Mapping[str, Any]) -> Optional[Unit]:
    """None, если класса юнита больше нет. Правила с удалёнными навыками отбрасываются."""
    state = UnitState(**data["state"])
    if state.definition_id not in db.units:
        return None
    unit = db.restore_unit(state, data.get("effects", ()))
    if data.get("tactics") is not None:
        unit.set_tactics(TacticsSet.from_list([r for r in data["tactics"] if r["skill"] in db.skills]))
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
        unit = unit_from_save(db, unit_data)
        if unit is not None:
            army.recruit(unit)
    for squad_data in data["squads"]:
        squad = army.create_squad(squad_data["id"], squad_data["name"], db.formation)
        for uid, row, col in squad_data["cells"]:
            # Поле могли уменьшить: кто не поместился, остаётся в резерве.
            fits = squad.formation.contains(row, col) and len(squad.formation) < squad.formation.max_units
            if uid in army.units and fits:
                army.assign(uid, squad.id, row, col)
        if squad.formation.position_of(squad_data["leader_uid"] or -1) is not None:
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
    """Независимая копия с определениями, заново взятыми из db.

    Бой портит копию, а не редактируемую расстановку. После правки классов
    или предметов так же обновляется сама расстановка.
    """
    return scenario_from_save(db, scenario_to_save(scenario))


def save_setup(path: Union[str, Path], db: Database, scenario: Scenario,
               settings: Optional[Mapping[str, Any]] = None) -> None:
    """settings: настройки приложения, не относящиеся к игре (например, язык)."""
    data = {"version": SAVE_VERSION, "settings": dict(settings or {}), "scenario": scenario_to_save(scenario)}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _read(path: Union[str, Path]) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") != SAVE_VERSION:
        raise ValueError(f"unsupported save version {data.get('version')!r}")
    return data


def load_settings(path: Union[str, Path]) -> dict[str, Any]:
    return _read(path).get("settings", {})


def load_setup(path: Union[str, Path], db: Database) -> Scenario:
    return scenario_from_save(db, _read(path)["scenario"])
