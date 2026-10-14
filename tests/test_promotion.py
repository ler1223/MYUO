"""Повышение классов, тиры 0..30 и оценка построения (формула и бои)."""
import copy
import unittest

from game import promotion, rating
from game.database import Database
from game.save import unit_from_save, unit_to_save
from game.stats import Stat
from game.tactics import TacticsSet
from game.tiers import rank_of
from game.tower import DRAFT, TowerRun, base_classes
from tests.helpers import DB
from tests.test_tower import rules


def tree_db() -> Database:
    """Гоблин повышается в орка (ур. 5) или в лучника (ур. 3); орк — в наездника (ур. 9)."""
    db = DB.copy()
    for class_id, tier, paths in (("goblin", 10, [{"class": "orc", "level": 5}, {"class": "archer", "level": 3}]),
                                  ("orc", 20, [{"class": "rider", "level": 9}]), ("rider", 30, [])):
        data = db.units[class_id].to_dict()
        data["tier"], data["promotions"] = tier, paths
        db.update("units", class_id, data)
    return db


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.db = tree_db()

    def test_promoted_unit_keeps_everything_of_its_predecessor(self):
        db = self.db
        goblin = db.create_unit("goblin", 1, 6, ["rusty_dagger"])
        before = {s: goblin.stat(s) for s in Stat}
        promotion.promote(db, goblin, "orc")
        unit = goblin                                        # тот же объект: армия и строй его не теряют
        self.assertEqual((unit.definition.id, unit.state.level, unit.state.history), ("orc", 6, ["goblin"]))
        self.assertIn("flurry", unit.definition.skills)       # навык гоблина остался
        self.assertIn("stun_bash", unit.definition.skills)    # и навыки орка есть
        self.assertIn("dagger", unit.definition.slots)        # слот кинжала остался, кинжал надет
        self.assertIn("rusty_dagger", unit.state.equipment)
        self.assertIn("heavy_weapon", unit.definition.slots)
        orc = db.create_unit("orc", 2, 6, history=[])
        for stat in Stat:                                    # статы: не ниже ни того, ни другого класса
            base = unit.definition.base_stat(stat, 6)
            self.assertGreaterEqual(base, db.units["goblin"].base_stat(stat, 6))
            self.assertGreaterEqual(base, orc.definition.base_stat(stat, 6))
        self.assertGreaterEqual(unit.stat(Stat.INITIATIVE), before[Stat.INITIATIVE])
        self.assertEqual(unit.hp, unit.max_hp)

    def test_level_and_path_are_checked_and_chains_go_on(self):
        db = self.db
        goblin = db.create_unit("goblin", 1, 4)
        self.assertEqual([p.class_id for p in promotion.available(goblin, db)], ["archer"])   # орк — с 5-го
        with self.assertRaises(ValueError):
            promotion.promote(db, goblin, "orc")
        with self.assertRaises(ValueError):
            promotion.promote(db, goblin, "knight")                   # нет такого пути
        goblin.state.level = 9
        promotion.promote(db, goblin, "orc")
        promotion.promote(db, goblin, "rider")
        self.assertEqual(goblin.state.history, ["goblin", "orc"])
        self.assertTrue({"flurry", "stun_bash", "lance_charge"} <= set(goblin.definition.skills))
        self.assertEqual(goblin.definition.tier, 30)
        self.assertEqual(promotion.available(goblin, db), [])

    def test_custom_tactics_survive_and_history_is_saved(self):
        db = self.db
        unit = db.create_unit("goblin", 1, 5)
        unit.set_tactics(TacticsSet.from_list([{"skill": "flurry"}]))
        promotion.promote(db, unit, "orc")
        self.assertEqual(unit.tactics.to_list()[0]["skill"], "flurry")
        again = unit_from_save(db, copy.deepcopy(unit_to_save(unit)))
        self.assertEqual(again.state.history, ["goblin"])
        self.assertIn("flurry", again.definition.skills)
        self.assertEqual(again.max_hp, unit.max_hp)

    def test_class_created_directly_gets_the_path_from_a_base_class(self):
        db = self.db
        self.assertEqual(db.lineage("rider"), ["goblin", "orc"])
        self.assertEqual(db.promotion_level("rider"), 9)
        rider = db.create_unit("rider", 1, 9)
        self.assertIn("flurry", rider.definition.skills)
        self.assertEqual(db.parents("orc"), ["goblin"])

    def test_tree_errors_and_deleting_a_class(self):
        db = self.db
        data = db.units["rider"].to_dict()
        data["promotions"] = [{"class": "goblin", "level": 12}]
        with self.assertRaisesRegex(ValueError, "cycle"):
            db.update("units", "rider", data)
        data["promotions"] = [{"class": "dragon", "level": 12}]
        with self.assertRaises(ValueError):
            db.update("units", "rider", data)
        db.delete("units", "orc")
        self.assertEqual([p.class_id for p in db.units["goblin"].promotions], ["archer"])


class TierTests(unittest.TestCase):
    def test_tiers_are_numbers_shown_as_three_ranks(self):
        self.assertEqual([rank_of(t) for t in (0, 9, 10, 19, 20, 30)], [1, 1, 2, 2, 3, 3])
        db = DB.copy()
        data = db.items[next(iter(db.items))].to_dict()
        data["tier"] = 31
        with self.assertRaises(ValueError):
            db.update("items", next(iter(db.items)), data)
        data["tier"] = 14
        db.update("items", next(iter(db.items)), data)
        self.assertEqual(db.items[next(iter(db.items))].rank, 2)


class TowerPromotionTests(unittest.TestCase):
    def test_draft_offers_only_base_classes_and_the_run_promotes(self):
        db = tree_db()
        self.assertNotIn("orc", base_classes(db))
        run = TowerRun.new(db, rules(), seed=7)
        while run.phase == DRAFT:
            self.assertFalse(set(run.offers) & {"orc", "rider", "archer"})
            run.pick(db, run.offers[0])
        unit = run.fielded[0]
        if unit.definition.promotions:
            unit.state.level = 9
            path = unit.definition.promotions[0].class_id
            run.promote(db, unit.uid, path)
            self.assertEqual(run.army.units[unit.uid].definition.id, path)
            again = TowerRun.from_dict(db, run.rules, copy.deepcopy(run.to_dict()))
            self.assertEqual(again.army.units[unit.uid].state.history, unit.state.history)
        run.phase = "reward"
        with self.assertRaises(ValueError):
            run.promote(db, unit.uid, "orc")

    def test_enemies_grow_into_promoted_classes_on_high_floors(self):
        db = tree_db()
        data = copy.deepcopy(rules().data)
        data["enemies"]["classes"] = {"goblin": 1}
        data["enemies"]["promotion"] = [{"floor": 1, "chance": 1.0}]
        run = TowerRun.new(db, type(rules())(data), seed=3)
        run.floor = 20                                         # уровень врагов выше 9: до наездника
        roster = run.enemy_roster(db)
        self.assertTrue(all(lv >= 9 for _c, lv, *_ in roster))
        self.assertTrue({c for c, *_ in roster} <= {"rider", "archer"})          # гоблинов не осталось
        self.assertTrue(all(c != "orc" for c, *_ in roster))                    # орк дорос до наездника
        run.floor = 1
        self.assertTrue({c for c, *_ in run.enemy_roster(db)} <= {"goblin", "archer"})


class RatingTests(unittest.TestCase):
    def test_power_grows_with_level_and_gear(self):
        low, high = DB.create_unit("knight", 1, 1), DB.create_unit("knight", 2, 10)
        self.assertGreater(rating.rate_unit(high, DB).power, rating.rate_unit(low, DB).power)
        armed = DB.create_unit("knight", 3, 1, ["iron_sword", "shield"])
        self.assertGreater(rating.rate_unit(armed, DB).power, rating.rate_unit(low, DB).power)

    def test_the_tank_belongs_in_the_front_row(self):
        knight, mage = DB.create_unit("knight", 1, 5), DB.create_unit("mage", 2, 5)
        good = rating.rate_squad([(knight, 0), (mage, 1)], DB).power
        bad = rating.rate_squad([(knight, 1), (mage, 0)], DB).power
        self.assertGreater(good, bad)

    def test_simulation_measures_win_share(self):
        strong = [("knight", 10, (), 0, c) for c in range(3)]
        weak = [("goblin", 1, (), 0, 1)]
        self.assertGreaterEqual(rating.simulate(DB, strong, weak, runs=4), 0.75)
        self.assertLessEqual(rating.simulate(DB, weak, strong, runs=4), 0.25)
        self.assertAlmostEqual(rating.spearman([1, 2, 3], [10, 20, 30]), 1.0)
        self.assertAlmostEqual(rating.spearman([1, 2, 3], [30, 20, 10]), -1.0)


if __name__ == "__main__":
    unittest.main()
