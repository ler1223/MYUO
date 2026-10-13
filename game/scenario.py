"""Демо-сценарий: две армии по одному отряду на соседних клетках карты."""
from __future__ import annotations

from dataclasses import dataclass

from .database import Database
from .squad import Squad
from .world import Army, WorldMap

MAP_SIZE = (8, 6)


@dataclass
class Scenario:
    player: Army
    enemy: Army
    world: WorldMap
    player_squad: Squad
    enemy_squad: Squad


def _build_army(db: Database, army_id: str, name: str, squad_id: str, squad_name: str, roster, first_uid: int):
    """roster: список (definition_id, level, equipment, row, col)."""
    army = Army(army_id, name)
    squad = army.create_squad(squad_id, squad_name, db.formation)
    for offset, (definition_id, level, equipment, row, col) in enumerate(roster):
        unit = army.recruit(db.create_unit(definition_id, first_uid + offset, level, equipment))
        army.assign(unit.uid, squad_id, row, col)
    return army, squad


def build_demo(db: Database) -> Scenario:
    player, player_squad = _build_army(
        db, "player", "Player", "vanguard", "Vanguard",
        [
            ("knight", 3, ("iron_sword", "shield"), 0, 1),
            ("archer", 1, ("short_bow",), 1, 0),
            ("mage", 1, ("oak_staff",), 1, 2),
            ("cleric", 1, ("oak_staff",), 2, 1),
        ],
        first_uid=1,
    )
    enemy, enemy_squad = _build_army(
        db, "enemy", "Enemy", "raiders", "Raiders",
        [
            ("orc", 2, ("war_axe",), 0, 1),
            ("goblin", 2, ("rusty_dagger",), 0, 0),
            ("rider", 2, ("lance",), 0, 2),
            ("mage", 2, ("oak_staff",), 1, 1),
        ],
        first_uid=11,
    )
    world = WorldMap(*MAP_SIZE)
    world.place(player_squad.id, 3, 2)
    world.place(enemy_squad.id, 4, 2)
    return Scenario(player, enemy, world, player_squad, enemy_squad)
