"""Уровни, опыт, навыки по уровню и бесконечная башня без графики."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from game.battle import BattleSimulation
from game.database import Database
from game.editing import set_owners
from game.progression import ExpRules, grant_exp
from game.tower import DRAFT, OVER, PREPARE, REWARD, SHOP, TOWER_RULES_PATH, TowerRules, TowerRun, by_floor
from game.world import Army
from tests.helpers import DB

RULES_DATA = json.loads(TOWER_RULES_PATH.read_text(encoding="utf-8"))


def rules(**changes) -> TowerRules:
    """Правила башни из data/tower.json с правками верхнего уровня (раздел целиком или его поля)."""
    data = copy.deepcopy(RULES_DATA)
    for key, value in changes.items():
        data[key] = dict(data[key], **value) if isinstance(data.get(key), dict) else value
    return TowerRules(data)


def learning_db() -> Database:
    """Рыцарь учит power_strike на 5 уровне, avenger — на 3."""
    db = DB.copy()
    data = db.units["knight"].to_dict()
    data["skills"] = ["attack", {"id": "power_strike", "level": 5}]
    data["passives"] = ["iron_will", {"id": "avenger", "level": 3}]
    db.update("units", "knight", data)
    return db


def drafted(db: Database, tower_rules: TowerRules = None) -> TowerRun:
    """Забег после набора: каждый раз берётся первый из предложенных."""
    run = TowerRun.new(db, tower_rules or rules(), seed=7)
    while run.phase == DRAFT:
        run.pick(db, run.offers[0])
    return run


class LevelUnlockTests(unittest.TestCase):
    def test_skills_and_passives_open_with_class_level(self):
        db = learning_db()
        definition = db.units["knight"]
        self.assertEqual(definition.skill_levels, {"power_strike": 5})
        self.assertEqual(definition.top_unlock, 5)
        low, high = db.create_unit("knight", 1, 1), db.create_unit("knight", 2, 5)
        self.assertEqual((low.skill_ids, low.passive_ids), (("attack",), ("iron_will",)))
        self.assertEqual((high.skill_ids, high.passive_ids), (("attack", "power_strike"), ("iron_will", "avenger")))
        self.assertEqual(definition.to_dict()["skills"], ["attack", {"id": "power_strike", "level": 5}])
        with self.assertRaises(ValueError):
            data = definition.to_dict()
            data["skills"] = [{"id": "attack", "level": 0}]
            db.update("units", "knight", data)

    def test_locked_skill_is_never_used_in_battle(self):
        db = learning_db()
        army = Army("a", "A")
        squad = army.create_squad("s", "S", db.formation)
        army.recruit(db.create_unit("knight", 1, 1))
        army.assign(1, "s", 0, 0)
        foes = Army("b", "B")
        enemy = foes.create_squad("e", "E", db.formation)
        foes.recruit(db.create_unit("orc", 2, 1))
        foes.assign(2, "e", 0, 0)
        sim = BattleSimulation(squad, enemy, db, seed=1)
        used = {getattr(ev, "skill_id", None) for ev in sim.run() if type(ev).__name__ == "SkillUsed" and ev.user == 1}
        self.assertNotIn("power_strike", used)

    def test_deleting_and_reassigning_keeps_working_with_levels(self):
        db = learning_db()
        db.delete("skills", "power_strike")
        self.assertNotIn("power_strike", db.units["knight"].skills)
        db = learning_db()
        set_owners(db, "units", "power_strike", [])
        self.assertNotIn("power_strike", db.units["knight"].skills)


class ExpTests(unittest.TestCase):
    def test_exp_depends_on_level_difference(self):
        rules = ExpRules(per_enemy=30, factor=2, min_share=0.25, max_share=4)
        self.assertEqual(rules.battle_exp(5, [5, 5]), 60)
        self.assertEqual(rules.battle_exp(5, [6]), 60)              # враг на уровень выше — вдвое
        self.assertEqual(rules.battle_exp(5, [10]), 120)            # но не больше max_share
        self.assertEqual(rules.battle_exp(10, [1]), 8)              # и не меньше min_share

    def test_several_levels_at_once_report_new_skills(self):
        db = learning_db()
        knight = db.create_unit("knight", 1, 1)
        up = grant_exp(knight, 450, ExpRules(per_level=100))
        self.assertEqual((up.old_level, up.new_level, knight.state.exp), (1, 5, 50))
        self.assertEqual((up.skills, up.passives), (["power_strike"], ["avenger"]))
        up = grant_exp(knight, 10_000, ExpRules(per_level=100, max_level=7))
        self.assertEqual((knight.state.level, knight.state.exp, up.levels), (7, 0, 2))


class TowerRulesTests(unittest.TestCase):
    def test_floor_tables(self):
        r = rules(squad=[{"floor": 1, "units": 2, "rows": 3, "cols": 3}, {"floor": 4, "units": 4, "cols": 4}],
                  boss={"every": 5, "extra_units": 1, "level_bonus": 3})
        self.assertEqual(r.squad_size(3).to_dict(), {"rows": 3, "cols": 3, "max_units": 2})
        self.assertEqual(r.squad_size(9).to_dict(), {"rows": 3, "cols": 4, "max_units": 4})   # rows наследуется
        self.assertTrue(r.is_boss(5))
        self.assertEqual(r.enemy_count(5), by_floor(RULES_DATA["enemies"]["count"], 5)["units"] + 1)
        self.assertEqual(r.enemy_level(5) - int(1 + 4 * RULES_DATA["enemies"]["level_per_floor"]), 3)
        bonus = 5 + RULES_DATA["boss"]["reward_floor_bonus"]          # награда главаря — как на этажах выше
        self.assertEqual(r.tier_weights(5), list(by_floor(RULES_DATA["reward"]["tier_weights"], bonus)["weights"]))
        self.assertEqual(r.scene(5), RULES_DATA["boss"]["scene"])
        with self.assertRaises(ValueError):
            rules(squad=[{"floor": 2, "units": 3}])                  # таблица должна начинаться с 1 этажа


class TowerRunTests(unittest.TestCase):
    def test_draft_gives_three_equipped_units_in_sensible_rows(self):
        run = drafted(DB)
        self.assertEqual((run.phase, len(run.army.units), len(run.fielded)), (PREPARE, 3, 3))
        for unit in run.army.units.values():
            self.assertTrue(unit.equipped)                           # стартовое снаряжение надето
            self.assertNotIn("artifact", [i.slot for i in unit.equipped])
            row = run.squad.formation.position_of(unit.uid)[0]
            ranged = any(s in ("bow", "staff") for s in unit.definition.slots)
            self.assertEqual(row, 1 if ranged else 0)
        with self.assertRaises(ValueError):
            run.pick(DB, "knight")                                   # набор закончен

    def test_battle_win_gives_exp_gold_and_two_of_five_items(self):
        db = DB.copy()
        run = drafted(db)
        scenario = run.battle(db)
        self.assertEqual(len(scenario.enemy_squad.formation), run.rules.enemy_count(1))
        scenario.player_squad.formation.units[0].take_damage(5)      # бой идёт на копиях
        self.assertTrue(all(u.hp == u.max_hp for u in run.army.units.values()))
        report = run.finish(db, scenario, won=True)
        self.assertEqual(run.phase, REWARD)
        self.assertEqual(len(report.level_ups), 3)
        self.assertTrue(all(up.exp > 0 for up in report.level_ups))
        self.assertEqual(run.inventory.gold, RULES_DATA["start_gold"] + run.rules.gold(1))
        self.assertEqual(len(run.reward), 5)
        with self.assertRaises(ValueError):
            run.take(db, [0, 1, 2])
        first, second = run.reward[0], run.reward[1]
        run.take(db, [0, 1])
        self.assertTrue(run.inventory.has(first) and run.inventory.has(second))
        self.assertEqual((run.floor, run.phase), (2, PREPARE))
        self.assertEqual(run.best, 1)

    def test_defeat_ends_the_run(self):
        run = drafted(DB)
        run.finish(DB, run.battle(DB), won=False)
        self.assertEqual((run.phase, run.best), (OVER, 0))
        with self.assertRaises(ValueError):
            run.battle(DB)

    def test_squad_grows_and_reserve_can_be_fielded(self):
        r = rules(squad=[{"floor": 1, "units": 2, "rows": 3, "cols": 3}, {"floor": 2, "units": 3}])
        run = drafted(DB, r)
        self.assertEqual((len(run.fielded), len(run.reserve)), (2, 1))
        benched = run.reserve[0]
        with self.assertRaises(ValueError):
            run.place(benched.uid, 2, 2)                              # поле полно
        with self.assertRaises(ValueError):
            run.field(benched.uid)                                    # «В отряд», а мест нет
        run.finish(DB, run.battle(DB), won=True)
        run.take(DB, [])
        self.assertEqual(run.squad.formation.max_units, 3)
        cell = run.field(benched.uid)                                 # на лучшую свободную клетку
        self.assertEqual(run.squad.formation.position_of(benched.uid), cell)
        run.bench(benched.uid)
        run.place(benched.uid, 2, 2)
        self.assertEqual(len(run.fielded), 3)
        occupant = run.fielded[0]
        run.place(benched.uid, *run.squad.formation.position_of(occupant.uid))   # поменяться местами
        self.assertEqual(run.squad.formation.position_of(benched.uid), (0, run.squad.formation.position_of(benched.uid)[1]))

    def test_shop_hire_buy_sell_and_reroll(self):
        db = DB.copy()
        run = drafted(db, rules(shop={"every": 1}, start_gold=1000))
        run.finish(db, run.battle(db), won=True)
        run.take(db, [0])
        self.assertEqual(run.phase, SHOP)
        self.assertEqual((len(run.recruits), len(run.shop_items)), (3, 5))
        gold = run.inventory.gold
        uid = run.hire(db, 0)
        self.assertIn(uid, run.army.units)
        self.assertLess(run.inventory.gold, gold)
        with self.assertRaises(ValueError):
            run.hire(db, 0)                                          # уже нанят
        item = run.shop_items[1]
        run.buy(db, 1)
        self.assertTrue(run.inventory.has(item))
        gold = run.inventory.gold
        run.sell(db, item)
        self.assertEqual(run.inventory.gold, gold + run.rules.sell_price(db, item))
        before = list(run.shop_items)
        run.reroll(db)
        self.assertEqual(run.rerolls, 1)
        self.assertEqual(len(run.shop_items), 5)
        self.assertTrue(all(i is not None for i in run.shop_items))
        self.assertNotEqual(before, run.shop_items)
        run.leave_shop()
        self.assertEqual(run.phase, PREPARE)

    def test_enemies_of_a_floor_are_stable_and_bosses_lead(self):
        run = drafted(DB, rules(boss={"every": 1, "leader_level_bonus": 4}))
        self.assertEqual(run.enemy_roster(DB), run.enemy_roster(DB))
        roster = run.enemy_roster(DB)
        self.assertEqual(roster[0][1], max(level for _, level, *_ in roster))
        self.assertGreater(roster[0][1], roster[-1][1])

    def test_save_load_and_rebuild(self):
        db = DB.copy()
        run = drafted(db)
        run.finish(db, run.battle(db), won=True)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tower.json"
            run.save(path)
            again = TowerRun.load(db, run.rules, path)
        self.assertEqual(again.to_dict(), run.to_dict())
        db.delete("units", run.fielded[0].definition.id)            # класс удалили в демо
        rebuilt = run.rebuild(db)
        self.assertLess(len(rebuilt.army.units), len(run.army.units))


class RealDataTests(unittest.TestCase):
    def test_tower_rules_and_items_fit_the_real_data(self):
        db = Database.load()
        tower = TowerRules.load()
        for slot, item in tower.data["starter_gear"].items():
            self.assertEqual(db.items[item].slot, slot)
        self.assertEqual({item.rank for item in db.items.values()}, {1, 2, 3})       # тир 0..30, ступени I-III
        self.assertTrue(all(0 <= item.tier <= 30 for item in db.items.values()))
        for stat_items in ("feather", "brooch"):
            self.assertEqual([db.items[f"{t}_{stat_items}"].rank for t in ("novice", "mercenary", "hero")], [1, 2, 3])

    def test_a_few_real_floors(self):
        db = Database.load()
        run = drafted(db, TowerRules.load())
        for _ in range(3):
            if run.phase == SHOP:
                run.leave_shop()
            scenario = run.battle(db)
            sim = BattleSimulation(scenario.player_squad, scenario.enemy_squad, db, seed=run.floor)
            sim.run()
            run.finish(db, scenario, sim.winner_id == scenario.player_squad.id)
            if run.phase == OVER:
                break
            run.take(db, [0, 1])
        self.assertGreaterEqual(run.best, 1)


if __name__ == "__main__":
    unittest.main()
