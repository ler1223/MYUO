"""Ограничения предметов по классам (game/unit.py class_allowed) и воскрешение (extras.revive)."""
import unittest

from game.combat import Battle
from game.combat.field import reachable
from game.combat.record import ACTIVE, Act
from game.unit import class_allowed
from tests.helpers import DB, add_skill, plain_db, squads


def restricted_db(classes=("knight",)):
    db = plain_db()
    data = db.items["iron_sword"].to_dict()
    data["classes"] = list(classes)
    db.update("items", "iron_sword", data)
    return db


class ClassAllowedTests(unittest.TestCase):
    def test_empty_list_means_everyone(self):
        self.assertTrue(class_allowed(DB.items["iron_sword"], ("goblin",)))

    def test_current_class_or_history_matches(self):
        item = restricted_db().items["iron_sword"]
        self.assertTrue(class_allowed(item, ("knight",)))
        self.assertTrue(class_allowed(item, ("mage", "knight")))      # история повышений
        self.assertFalse(class_allowed(item, ("mage",)))

    def test_story_class_is_unrestricted(self):
        self.assertTrue(class_allowed(restricted_db().items["iron_sword"], ("mage",), story=True))


class UnitEquipTests(unittest.TestCase):
    def setUp(self):
        self.db = restricted_db()

    def test_equip_checks_class(self):
        knight = self.db.create_unit("knight", 1)
        knight.equip(0, "iron_sword")
        self.assertTrue(knight.can_equip("iron_sword"))
        self.assertEqual(knight.state.equipment[0], "iron_sword")
        data = self.db.items["iron_sword"].to_dict()
        data["classes"] = ["mage"]
        self.db.update("items", "iron_sword", data)
        with self.assertRaises(ValueError):
            self.db.create_unit("knight", 2).equip(0, "iron_sword")

    def test_strict_create_rejects_wrong_class(self):
        unit = self.db.create_unit("knight", 1, equipment=["iron_sword"])
        self.assertEqual(unit.rejected_equipment, [])
        # класс не подходит: create_unit в строгом режиме отказывает
        with self.assertRaises(ValueError):
            self.db.create_unit("goblin", 2, equipment=["iron_sword"], history=["goblin"])

    def test_reclass_keeps_items_of_previous_classes(self):
        unit = self.db.create_unit("knight", 1, equipment=["iron_sword"])
        unit.reclass(self.db.definition_for("knight", ["knight"]))
        self.assertIn("iron_sword", unit.state.equipment)


class ReviveTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()
        add_skill(self.db, "rise", ["cleric"], ap_cost=1, targets="ally",
                  extras={"revive": True, "revive_pct": 50})
        add_skill(self.db, "rise_min", ["cleric"], ap_cost=1, targets="ally", extras={"revive": True})
        left, right = squads(self.db, [("cleric", 1, 0, 0), ("knight", 1, 1, 0)], [("goblin", 1, 0, 0)])
        self.battle = Battle(left, right, self.db, seed=1)
        self.cleric, self.knight = self.battle.side_of(left.formation.units[0]).units[:2]
        self.knight.state.current_hp = 0
        self.battle._dead.add(self.knight.uid)

    def test_only_fallen_allies_are_targets(self):
        own = self.battle.side_of(self.cleric)
        targets = reachable(self.db.skills["rise"], self.cleric, own, self.battle.other(own))
        self.assertEqual([u.uid for u in targets], [self.knight.uid])

    def test_revive_restores_share_of_max_hp(self):
        act = Act(ACTIVE, self.cleric.uid, "rise", target=self.knight.uid)
        self.battle._resolve(self.cleric, self.db.skills["rise"], self.knight, act, root=True)
        self.assertTrue(self.knight.is_alive)
        self.assertEqual(self.knight.hp, round(self.knight.max_hp * 0.5))
        self.assertNotIn(self.knight.uid, self.battle._dead)      # павший снова может погибнуть

    def test_revive_without_percent_gives_one_hp(self):
        act = Act(ACTIVE, self.cleric.uid, "rise_min", target=self.knight.uid)
        self.battle._resolve(self.cleric, self.db.skills["rise_min"], self.knight, act, root=True)
        self.assertEqual(self.knight.hp, 1)


if __name__ == "__main__":
    unittest.main()
