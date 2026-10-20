"""Показ навыка в редакторе: сцена сама выполняет условия навыка.

Условия (requires_self / requires_target, условия накладываемых эффектов) подгоняются
под юнита до боя: HP, эффекты, класс манекена с нужными тегами.
"""
import unittest

from anim_review import pick_dummy, satisfy
from game.tactics import Always, HasEffect, HasTag, HpAbove, HpBelow, LacksEffect, LacksTag
from tests.helpers import plain_db


class SatisfyTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def unit(self, cid="knight"):
        return self.db.create_unit(cid, 1, level=10)

    def test_always_ok(self):
        self.assertTrue(satisfy(self.db, self.unit(), Always()))

    def test_hp_below_wounds_under_limit(self):
        unit = self.unit()
        self.assertFalse(HpBelow(0.5).check(unit, unit))
        self.assertTrue(satisfy(self.db, unit, HpBelow(0.5)))
        self.assertLess(unit.hp, unit.max_hp * 0.5)
        self.assertGreater(unit.hp, 0)

    def test_hp_above_heals(self):
        unit = self.unit()
        unit.take_damage(unit.hp - 1)
        self.assertTrue(satisfy(self.db, unit, HpAbove(0.9)))
        self.assertGreaterEqual(unit.hp, unit.max_hp * 0.9)

    def test_has_effect_is_applied(self):
        unit = self.unit()
        self.assertTrue(satisfy(self.db, unit, HasEffect("poison")))
        self.assertTrue(unit.has_effect("poison"))

    def test_lacks_effect_removes_it(self):
        unit = self.unit()
        unit.add_effect(self.db.effects["poison"])
        self.assertTrue(satisfy(self.db, unit, LacksEffect("poison")))
        self.assertFalse(unit.has_effect("poison"))

    def test_impossible_condition_stays_false(self):
        unit = self.unit()
        self.assertFalse(satisfy(self.db, unit, HpBelow(0.0)))   # ниже нуля HP не бывает


class DummyTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def test_picks_class_with_required_tag(self):
        cid = pick_dummy(self.db, [HasTag("cavalry")])
        self.assertIn("cavalry", self.db.units[cid].tags)

    def test_picks_class_without_forbidden_tag(self):
        cid = pick_dummy(self.db, [LacksTag("cavalry")])
        self.assertNotIn("cavalry", self.db.units[cid].tags)

    def test_default_without_tag_conditions(self):
        self.assertEqual(pick_dummy(self.db, [Always(), HasEffect("poison")]), "fighter")

    def test_falls_back_when_no_class_fits(self):
        self.assertEqual(pick_dummy(self.db, [HasTag("no-such-tag")]), "fighter")


if __name__ == "__main__":
    unittest.main()
