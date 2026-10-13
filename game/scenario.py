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


# Пять тестовых классов визуала (docs/test_classes.md): (класс, предметы, ряд, колонна) у каждой стороны.
SHOWCASE_PLAYER = (
    ("paladin", ("iron_sword", "shield"), 0, 1),
    ("rider", ("lance",), 0, 2),
    ("hunter", ("short_bow",), 1, 0),
    ("pyromancer", ("oak_staff",), 1, 2),
    ("cleric", ("oak_staff",), 2, 1),
)
SHOWCASE_ENEMY = (
    ("paladin", ("iron_sword", "shield"), 0, 0),
    ("rider", ("lance",), 0, 2),
    ("pyromancer", ("oak_staff",), 1, 1),
    ("hunter", ("short_bow",), 2, 0),
    ("cleric", ("oak_staff",), 2, 2),
)


def build_showcase(db: Database, level: int = 3) -> Scenario:
    """Бой тестовых классов против них же. Классы и предметы, которых нет в справочнике, пропускаются;
    если не осталось никого, берётся обычное демо."""
    def roster(entries):
        return [(cls, level, tuple(i for i in items if i in db.items), row, col)
                for cls, items, row, col in entries if cls in db.units]

    player_roster, enemy_roster = roster(SHOWCASE_PLAYER), roster(SHOWCASE_ENEMY)
    if not player_roster or not enemy_roster:
        return build_demo(db)
    player, player_squad = _build_army(db, "player", "Player", "vanguard", "Vanguard", player_roster, first_uid=1)
    enemy, enemy_squad = _build_army(db, "enemy", "Enemy", "raiders", "Raiders", enemy_roster, first_uid=11)
    world = WorldMap(*MAP_SIZE)
    world.place(player_squad.id, 3, 2)
    world.place(enemy_squad.id, 4, 2)
    return Scenario(player, enemy, world, player_squad, enemy_squad)
