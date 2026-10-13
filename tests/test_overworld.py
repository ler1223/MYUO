"""Открытый мир без графики: инвентарь, движение героя, регионы, сундуки, враги, итог боя, сохранение."""
import json
import tempfile
import unittest
from pathlib import Path

from game.database import Database
from game.inventory import Inventory
from game.overworld import (
    CONTACT_RADIUS,
    GRACE_MS,
    DEFAULT_WORLD,
    WORLD_DIR,
    Overworld,
    WorldDef,
    encounter_scenario,
)
from game.scenario import build_demo
from tests.helpers import DB


def small_world(**extra) -> WorldDef:
    """Два региона: открытый «home» слева и закрытый «wild» справа, с главарём."""
    data = {
        "name": "Small", "size": [2000, 1000], "start": [200, 500],
        "goods": {"herb": {"name": "Herb", "kind": "material"}},
        "regions": [
            {"id": "home", "name": "Home", "open": True, "liberated": True,
             "polygon": [[0, 0], [1000, 0], [1000, 1000], [0, 1000]]},
            {"id": "camp", "name": "Camp", "open": True, "unlocks": ["wild"],
             "polygon": [[1000, 0], [1500, 0], [1500, 1000], [1000, 1000]]},
            {"id": "wild", "name": "Wild", "polygon": [[1500, 0], [2000, 0], [2000, 1000], [1500, 1000]]},
        ],
        "objects": [
            {"id": "town", "kind": "town", "name": "Town", "x": 500, "z": 800, "radius": 60},
            {"id": "chest", "kind": "chest", "name": "Chest", "x": 300, "z": 500, "loot": [["herb", 2]], "gold": 30},
            {"id": "rock", "kind": "decor", "name": "", "x": 600, "z": 500, "radius": 50},
        ],
        "enemies": [
            {"id": "boss", "name": "Boss", "x": 1300, "z": 500, "boss": True, "roam": 50, "aggro": 300,
             "roster": [["goblin", 2, 0, 1]], "loot": [["herb", 1]], "gold": 100},
        ],
    }
    data.update(extra)
    return WorldDef.from_dict("small", data)


class InventoryTests(unittest.TestCase):
    def test_stacks_gold_and_equipment(self):
        inv = Inventory()
        inv.add("herb", 3)
        self.assertTrue(inv.remove("herb", 2))
        self.assertFalse(inv.remove("herb", 5))               # не хватает — ничего не меняется
        self.assertEqual(inv.count("herb"), 1)
        inv.add_gold(50)
        self.assertFalse(inv.spend_gold(80))
        self.assertTrue(inv.spend_gold(30))
        db = DB.copy()
        knight = db.create_unit("knight", 1, 1, ["iron_sword"])
        sword_slot = db.units["knight"].slots.index("light_sword")
        with self.assertRaises(ValueError):
            inv.equip(knight, sword_slot, "iron_sword")          # в инвентаре меча нет
        self.assertEqual(inv.unequip(knight, sword_slot), "iron_sword")
        self.assertIsNone(knight.state.equipment[sword_slot])
        inv.equip(knight, sword_slot, "iron_sword")
        self.assertEqual((knight.state.equipment[sword_slot], inv.count("iron_sword")), ("iron_sword", 0))
        inv.add("short_bow")
        with self.assertRaises(ValueError):
            inv.equip(knight, sword_slot, "short_bow")           # лук в слот меча не лезет
        self.assertEqual(inv.count("short_bow"), 1)
        self.assertEqual(Inventory.from_dict(inv.to_dict()), inv)


class OverworldTests(unittest.TestCase):
    def test_hero_walks_slides_and_is_stopped_by_locked_regions_and_objects(self):
        world = Overworld(small_world())
        world.step(1000, (1, 0))
        self.assertGreater(world.hero[0], 200)
        world.hero = (1480, 500)
        world.step(1000, (1, 0))                               # «wild» закрыт
        self.assertLess(world.hero[0], 1500)
        world.hero = (500, 500)
        world.step(1000, (1, 0))                               # камень не пройти
        self.assertLess(world.hero[0], 600 - 50)
        world.hero = (500, 500)
        world.step(100, (1, 1))                                # по диагонали — скользит вдоль камня
        self.assertGreater(world.hero[1], 500)

    def test_chest_gives_loot_once_and_town_becomes_the_safe_point(self):
        world = Overworld(small_world())
        world.hero = (330, 500)
        self.assertEqual(world.nearest_interactive().id, "chest")
        result = world.interact("chest")
        self.assertEqual((result.loot, result.gold), ((("herb", 2),), 30))
        self.assertEqual(world.inventory.count("herb"), 2)
        self.assertIsNone(world.nearest_interactive())         # открытый сундук больше не предлагается
        world.interact("chest")
        self.assertEqual(world.inventory.count("herb"), 2)
        self.assertTrue(world.interact("town").rested)
        self.assertTrue(world.walkable(world.safe_point))

    def test_enemy_chases_the_hero_and_defeat_returns_hero_to_safety(self):
        world = Overworld(small_world())
        world.hero = (1050, 500)
        met = None
        for _ in range(100):
            met = world.step(50) or met
            if met:
                break
        self.assertEqual(met, "boss")                           # враг заметил, догнал — бой
        result = world.resolve_battle("boss", won=False)
        self.assertEqual(result.kind, "defeat")
        self.assertEqual(world.hero, world.safe_point)
        self.assertIn("boss", world.enemies)
        world.hero = (1300, 500)                                # передышка после боя
        self.assertIsNone(world.step(10))
        for _ in range(GRACE_MS // 100 + 1):                  # шаг не длиннее 100 мс
            world.step(100)
        world.hero = (world.enemies["boss"].x, world.enemies["boss"].z + CONTACT_RADIUS / 2)
        self.assertEqual(world.step(10), "boss")

    def test_beating_the_boss_liberates_the_region_and_unlocks_the_next(self):
        world = Overworld(small_world())
        self.assertNotIn("wild", world.unlocked)
        result = world.resolve_battle("boss", won=True)
        self.assertEqual(result.kind, "victory")
        self.assertIn("camp", world.liberated)
        self.assertIn("wild", world.unlocked)
        self.assertNotIn("boss", world.enemies)
        self.assertEqual((world.inventory.count("herb"), world.inventory.gold), (1, 100))
        world.hero = (1480, 500)
        world.step(1000, (1, 0))
        self.assertGreater(world.hero[0], 1500)                 # теперь можно в «wild»

    def test_save_and_load_round_trip(self):
        world = Overworld(small_world())
        world.interact("chest")
        world.resolve_battle("boss", won=True)
        world.hero = (1700, 300)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "world.json"
            world.save(path)
            again = Overworld(small_world())
            again.load(path)
            self.assertEqual((again.hero, again.unlocked, again.opened, again.defeated, again.inventory),
                             (world.hero, world.unlocked, world.opened, world.defeated, world.inventory))
            data = json.loads(path.read_text(encoding="utf-8"))
            data["world"] = "other"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                Overworld(small_world()).load(path)               # сохранение другой карты

    def test_bad_descriptions_are_rejected(self):
        with self.assertRaises(ValueError):
            small_world(start=[1800, 500], regions=[{"id": "a", "name": "A", "polygon": [[0, 0], [10, 0], [0, 10]]}])
        with self.assertRaises(ValueError):
            small_world(objects=[{"id": "x", "kind": "castle", "name": "X", "x": 1, "z": 1}])


class TestMapTests(unittest.TestCase):
    def test_test_map_matches_the_real_data_and_its_regions_chain(self):
        db = Database.load()
        world = WorldDef.load(DEFAULT_WORLD, WORLD_DIR)
        self.assertEqual(world.unknown_references(list(db.units), list(db.items)), [])
        state = Overworld(world)
        self.assertTrue(state.walkable(world.start))
        for obj in world.objects:                                # объекты внутри регионов карты
            self.assertIsNotNone(world.region_at((obj.x, obj.z)), obj.id)
        bosses = [e for e in world.enemies if e.boss]
        self.assertTrue(bosses)
        for boss in bosses:
            state.resolve_battle(boss.id, won=True)
        self.assertEqual(state.unlocked, {r.id for r in world.regions})   # победы открывают всю карту

    def test_encounter_puts_the_main_squad_against_the_enemy_squad(self):
        db = Database.load()
        world = WorldDef.load(DEFAULT_WORLD, WORLD_DIR)
        setup = build_demo(db)
        scenario = encounter_scenario(db, setup, world.enemy("patrol"))
        self.assertEqual(scenario.player_squad.id, setup.player_squad.id)
        self.assertEqual(len(scenario.enemy_squad.formation), 3)
        self.assertTrue(set(scenario.player.units).isdisjoint(scenario.enemy.units))   # uid не пересекаются
        self.assertIsNot(scenario.player_squad, setup.player_squad)                   # бой идёт на копии


if __name__ == "__main__":
    unittest.main()
