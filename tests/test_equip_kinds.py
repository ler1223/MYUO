"""Кто что носит: вид предмета (kind), виды класса (equips) и списки-исключения (classes)."""
import unittest

from game.database import Database
from game.unit import UnitState, wearable
from tests.helpers import plain_db


def kinds_db(item_kind="staff_arcane", equips=None, story=None):
    """Справочник с особым видом посоха: oak_staff — посох мага; mage носит его, если задано equips."""
    data = plain_db().to_dict()
    data["config"]["item_kinds"] = {"staff_arcane": "staff", "rapier": "light_sword"}
    if item_kind:
        data["items"]["oak_staff"]["kind"] = item_kind
    for class_id, kinds in (equips or {}).items():
        data["units"][class_id]["equips"] = list(kinds)
    for class_id in story or ():
        data["units"][class_id]["story"] = True
    return Database(data)


class KindRuleTests(unittest.TestCase):
    def test_main_kind_is_worn_by_every_class_with_the_slot(self):
        db = kinds_db(item_kind=None)
        self.assertEqual(db.items["oak_staff"].equip_kind, "staff")
        self.assertTrue(db.create_unit("cleric", 1).can_equip("oak_staff"))
        self.assertTrue(db.create_unit("mage", 1).can_equip("oak_staff"))
        self.assertFalse(db.create_unit("knight", 1).can_equip("oak_staff"))        # нет слота

    def test_special_kind_needs_the_class_kind(self):
        db = kinds_db(equips={"mage": ["staff_arcane"]})
        self.assertTrue(db.create_unit("mage", 1).can_equip("oak_staff"))
        cleric = db.create_unit("cleric", 1)
        self.assertFalse(cleric.can_equip("oak_staff"))
        with self.assertRaises(ValueError):
            cleric.equip(0, "oak_staff")

    def test_kinds_are_inherited_by_promotion(self):
        db = kinds_db(equips={"mage": ["staff_arcane"]})
        self.assertIn("staff_arcane", db.definition_for("cleric", ["mage"]).kinds)
        self.assertTrue(wearable(db.items["oak_staff"], db.definition_for("cleric", ["mage"])))

    def test_story_class_skips_class_lists_but_not_kinds(self):
        db = kinds_db(story=["cleric"])
        data = db.items["iron_sword"].to_dict()
        data["classes"] = ["knight"]
        db.update("items", "iron_sword", data)
        self.assertFalse(db.create_unit("cleric", 1).can_equip("oak_staff"))        # вид проверяется и у сюжетных
        db.update("units", "orc", {**db.units["orc"].to_dict(), "slots": ["light_sword", "artifact"], "story": True})
        self.assertTrue(db.create_unit("orc", 1).can_equip("iron_sword"))           # список-исключение — нет

    def test_class_list_is_an_extra_restriction(self):
        db = kinds_db(equips={"mage": ["staff_arcane"], "cleric": ["staff_arcane"]})
        data = db.items["oak_staff"].to_dict()
        data["classes"] = ["cleric"]
        db.update("items", "oak_staff", data)
        self.assertTrue(db.create_unit("cleric", 1).can_equip("oak_staff"))
        self.assertFalse(db.create_unit("mage", 1).can_equip("oak_staff"))

    def test_old_equipment_of_a_wrong_kind_goes_back_to_the_inventory(self):
        db = kinds_db()
        state = UnitState(uid=1, definition_id="mage", level=1, current_hp=1, equipment=["oak_staff"])
        unit = db.restore_unit(state)
        self.assertEqual(unit.rejected_equipment, ["oak_staff"])
        self.assertNotIn("oak_staff", unit.state.equipment)

    def test_round_trip_and_validation(self):
        db = kinds_db(equips={"mage": ["staff_arcane"]})
        self.assertEqual(db.items["oak_staff"].to_dict()["kind"], "staff_arcane")
        self.assertEqual(db.units["mage"].to_dict()["equips"], ["staff_arcane"])
        self.assertEqual(Database(db.to_dict()).item_kinds, db.item_kinds)
        self.assertEqual(db.kinds_of_slot("staff"), ["staff", "staff_arcane"])
        data = db.to_dict()
        data["items"]["iron_sword"]["kind"] = "staff_arcane"          # вид чужого слота
        with self.assertRaises(ValueError):
            Database(data)
        data = db.to_dict()
        data["units"]["knight"]["equips"] = ["laser"]
        with self.assertRaises(ValueError):
            Database(data)


class GameDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database.load()

    def can(self, class_id, item_id):
        return wearable(self.db.items[item_id], self.db.definition_for(class_id, self.db.lineage(class_id)))

    def test_staffs_by_kind(self):
        self.assertTrue(self.can("wizard", "thawing_scepter"))       # посох мага
        self.assertFalse(self.can("cleric", "thawing_scepter"))
        self.assertTrue(self.can("cleric", "gleaming_mace"))         # именной посох: Cleric/Bishop
        self.assertFalse(self.can("priestess", "thawing_scepter"))   # сюжетная — тоже по виду

    def test_named_items_and_fixed_slots(self):
        self.assertTrue(self.can("lord", "holy_unicorn_blade"))
        self.assertFalse(self.can("fighter", "holy_unicorn_blade"))
        self.assertIn("light_shield", self.db.units["viking"].slots)
        self.assertIn("light_sword", self.db.units["sainted_knight"].slots)

    def test_class_lists_are_only_exceptions(self):
        listed = [i for i in self.db.items.values() if i.classes]
        self.assertLess(len(listed), 20)


if __name__ == "__main__":
    unittest.main()
