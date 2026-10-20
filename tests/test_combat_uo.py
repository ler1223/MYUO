"""Правила боя UO (game/combat): ход по инициативе и кругам, ряды и цели, формула урона, блок,
прикрытие, одна пассивка на действие, состояния, итог по остатку HP. Справка игры — docs/uo/battle.md."""
import unittest

from game.combat import Battle
from game.combat.record import ACTIVE, END, MISS, PASSIVE, SKIP, START
from game.events import DamageDealt, TurnStarted
from tests.helpers import add_skill, plain_db, rule, set_stats, squads


def battle(db, left, right, seed=1):
    a, b = squads(db, left, right)
    return Battle(a, b, db, seed=seed)


def acts(b, kind=None):
    return [a for a in b.acts if kind is None or a.kind == kind]


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()
        add_skill(self.db, "poke", ["knight", "archer"], ap_cost=1, tags=["melee"],
                  parts=[{"kind": "damage", "power": 0.1}])
        for unit in ("knight", "archer"):
            data = self.db.units[unit].to_dict()
            data.update(ap_max=2, passives=[], tactics=[rule("poke")])
            self.db.update("units", unit, data)

    def test_initiative_order_and_rounds_until_ap_runs_out(self):
        set_stats(self.db, "archer", initiative=20)
        set_stats(self.db, "knight", initiative=5, hp=500)
        b = battle(self.db, [("knight", 1, 0, 0)], [("archer", 1, 0, 0)])
        b.run()
        order = [a.actor for a in acts(b, ACTIVE)]
        self.assertEqual(order, [2, 1, 2, 1])          # быстрый первым; по 2 AP — два круга
        self.assertEqual(b.round, 3)                     # третий круг: действовать некому — конец
        self.assertEqual(acts(b)[0].kind, START)
        self.assertEqual(acts(b)[-1].kind, END)

    def test_result_by_remaining_hp_share(self):
        set_stats(self.db, "knight", hp=500, phys_atk=40)
        set_stats(self.db, "archer", hp=500, phys_atk=10)
        b = battle(self.db, [("knight", 1, 0, 0)], [("archer", 1, 0, 0)])
        b.run()
        self.assertEqual(b.winner_id, "a")                # у правых осталось меньше HP — они проиграли
        self.assertEqual(b.end_reason, "exhausted")


class RowTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()
        add_skill(self.db, "swing", ["knight"], tags=["melee"], parts=[{"kind": "damage", "power": 0.1}])
        add_skill(self.db, "arrow", ["archer"], tags=["ranged"], parts=[{"kind": "damage", "power": 0.1}])
        for unit, skill in (("knight", "swing"), ("archer", "arrow")):
            data = self.db.units[unit].to_dict()
            data.update(passives=[], tactics=[rule(skill, selector="weakest")])
            self.db.update("units", unit, data)
        set_stats(self.db, "cleric", hp=5, initiative=0)
        set_stats(self.db, "mage", hp=500, initiative=0)

    def test_melee_reaches_back_row_only_when_front_row_is_empty(self):
        for attacker, expected in (("knight", 2), ("archer", 3)):
            b = battle(self.db, [(attacker, 1, 0, 1)], [("mage", 1, 0, 1), ("cleric", 1, 1, 1)])
            b.units[3].state.current_hp = 1               # раненый клерик сзади — лучшая цель по приоритету
            b.step()
            self.assertEqual(b.last_act.target, expected)  # ближнему он недоступен, стрела достаёт

    def test_default_target_is_the_enemy_in_front_then_the_closest_column(self):
        data = self.db.units["knight"].to_dict()
        data.update(tactics=[rule("swing")])
        self.db.update("units", "knight", data)
        b = battle(self.db, [("knight", 1, 0, 2)], [("mage", 1, 0, 0), ("mage", 1, 0, 2)])
        b.step()
        self.assertEqual(b.last_act.target, 3)           # прямо напротив (колонка 2)
        b = battle(self.db, [("knight", 1, 0, 2)], [("mage", 1, 0, 0), ("mage", 1, 0, 1)])
        b.step()
        self.assertEqual(b.last_act.target, 3)           # напротив пусто — ближайшая колонка


class DamageTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()
        set_stats(self.db, "knight", phys_atk=50, mag_atk=30, initiative=99)
        set_stats(self.db, "mage", hp=999, phys_def=10, mag_def=5, initiative=0)
        for unit in ("knight", "mage"):
            data = self.db.units[unit].to_dict()
            data.update(passives=[])
            self.db.update("units", unit, data)

    def strike(self, **skill):
        add_skill(self.db, "test", ["knight"], **skill)
        data = self.db.units["knight"].to_dict()
        data.update(tactics=[rule("test")])
        self.db.update("units", "knight", data)
        b = battle(self.db, [("knight", 1, 0, 0)], [("mage", 1, 0, 0)])
        b.step()
        return b.last_act

    def test_physical_plus_magical_by_the_formula(self):
        act = self.strike(parts=[{"kind": "damage", "category": "physical", "power": 1.5},
                                 {"kind": "damage", "category": "magical", "power": 0.5,
                                  "scaling": [{"stat": "mag_atk"}]}])
        # (50 − 10) × 1.5 + (30 − 5) × 0.5 = 60 + 12.5
        self.assertEqual(act.strikes[0].damage, 72)

    def test_guard_cuts_only_the_physical_part(self):
        set_stats(self.db, "mage", guard_rate=100)
        act = self.strike(parts=[{"kind": "damage", "category": "physical", "power": 1.0},
                                 {"kind": "damage", "category": "magical", "power": 1.0,
                                  "scaling": [{"stat": "mag_atk"}]}])
        self.assertEqual(act.strikes[0].guard, "medium")
        self.assertEqual(act.strikes[0].damage, round(40 * 0.5 + 25))

    def test_every_hit_of_a_multi_hit_skill_is_separate(self):
        act = self.strike(hits=3, parts=[{"kind": "damage", "power": 0.5}])
        self.assertEqual([s.hit_index for s in act.strikes], [0, 1, 2])
        self.assertEqual(sum(1 for e in act.events if isinstance(e, DamageDealt)), 3)

    def test_truestrike_ignores_evasion(self):
        set_stats(self.db, "mage", evasion=500)
        act = self.strike(parts=[{"kind": "damage", "power": 0.5}])
        self.assertEqual(act.strikes[0].outcome, MISS)
        act = self.strike(parts=[{"kind": "damage", "power": 0.5}], extras={"truestrike": True})
        self.assertGreater(act.strikes[0].damage, 0)


class PassiveTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()
        add_skill(self.db, "swing", ["knight"], tags=["melee"], parts=[{"kind": "damage", "power": 0.5}])
        add_skill(self.db, "riposte", [], tags=["melee"], parts=[{"kind": "damage", "power": 0.2}])
        self.db.update("passives", "cover", {"name": "Cover", "pp_cost": 1, "reaction": {
            "event": "targeted", "whose": "ally", "action": "cover", "to": "owner"}})
        self.db.update("passives", "counter", {"name": "Counter", "pp_cost": 1, "reaction": {
            "event": "attacked", "whose": "self", "action": "use_skill", "skill_id": "riposte", "to": "actor"}})
        data = self.db.units["knight"].to_dict()
        data.update(passives=[], tactics=[rule("swing")], ap_max=1)
        self.db.update("units", "knight", data)
        set_stats(self.db, "knight", initiative=99, hp=500)
        for unit, passives in (("mage", ["counter"]), ("cleric", ["cover", "counter"])):
            data = self.db.units[unit].to_dict()
            data.update(passives=passives, tactics=[], ap_max=0)
            self.db.update("units", unit, data)
            set_stats(self.db, unit, hp=500)

    def test_cover_takes_the_blow_and_the_coverer_cannot_answer_again(self):
        b = battle(self.db, [("knight", 1, 0, 0)], [("mage", 1, 0, 0), ("cleric", 1, 0, 1)])
        b.step()
        act = b.last_act
        self.assertEqual(act.kind, ACTIVE)
        self.assertEqual(act.covers, [(3, 2)])            # клерик прикрыл мага
        self.assertEqual([s.target for s in act.strikes], [3])
        answered = [a.actor for a in act.after if a.kind == PASSIVE]
        self.assertNotIn(3, answered)                     # одна пассивка на действие: прикрыл — не контратакует
        self.assertNotIn(2, answered)                     # по магу не попали — ему не на что отвечать

    def test_counter_hits_the_attacker_and_does_not_chain(self):
        b = battle(self.db, [("knight", 1, 0, 0)], [("mage", 1, 0, 0)])
        b.step()
        counters = [a for a in b.last_act.after if a.kind == PASSIVE]
        self.assertEqual(len(counters), 1)
        self.assertEqual(counters[0].skill_used, "riposte")
        self.assertEqual(counters[0].target, 1)
        self.assertFalse(counters[0].after)               # на ответ не отвечают


class AfflictionTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()
        add_skill(self.db, "swing", ["knight", "mage"], tags=["melee"], parts=[{"kind": "damage", "power": 0.1}])
        for unit in ("knight", "mage"):
            data = self.db.units[unit].to_dict()
            data.update(passives=[], tactics=[rule("swing")], ap_max=2)
            self.db.update("units", unit, data)
            set_stats(self.db, unit, hp=500)
        set_stats(self.db, "knight", initiative=99)
        self.db.update("effects", "frost", {"name": "Frost", "flags": ["frozen"], "tags": ["debuff"]})

    def test_frozen_skips_until_hit_and_a_hit_thaws(self):
        b = battle(self.db, [("knight", 1, 0, 0)], [("mage", 1, 0, 0)])
        b.units[2].add_effect(self.db.effects["frost"])     # наложено до боя — остаётся
        b.step()                                          # рыцарь бьёт — мага размораживает
        self.assertTrue(b.last_act.strikes[0].thawed)
        b.step()
        self.assertEqual(b.last_act.kind, ACTIVE)         # маг уже действует

    def test_poison_hurts_before_the_active_skill(self):
        b = battle(self.db, [("knight", 1, 0, 0)], [("mage", 1, 0, 0)])
        b.units[1].add_effect(self.db.effects["poison"])     # наложено до боя — остаётся
        b.step()
        act = b.last_act
        self.assertEqual(act.kind, ACTIVE)
        self.assertTrue(act.before and act.before[0].kind == "affliction")
        self.assertLess(b.units[1].hp, 500)

    def test_stun_skips_one_turn(self):
        b = battle(self.db, [("knight", 1, 0, 0)], [("mage", 1, 0, 0)])
        b.units[1].add_effect(self.db.effects["stun"])     # наложено до боя — остаётся
        b.step()
        self.assertEqual(b.last_act.kind, SKIP)
        self.assertFalse(b.units[1].has_flag("stunned"))
        self.assertTrue(any(isinstance(e, TurnStarted) for e in b.events))


if __name__ == "__main__":
    unittest.main()
