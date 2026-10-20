"""Условия тактики Unicorn Overlord (game/conditions.py): состав, виды, поведение по группам."""
import json
import unittest
from pathlib import Path

from game.combat import Battle
from game.conditions import (
    ACTIVATES_ONLY,
    FACTORS,
    PRIORITIZE,
    TARGET_ONLY,
    Context,
    LegacyCondition,
    check_conditions,
    condition_from_data,
)
from game.combat.engine import Moment
from game.combat.record import Act
from tests.helpers import plain_db, squads

ROOT = Path(__file__).resolve().parent.parent
GAME = json.loads((ROOT / "docs" / "uo" / "catalog" / "factors.json").read_text(encoding="utf-8"))["factors"]


def world(left, right, **kw):
    db = plain_db()
    a, b = squads(db, left, right)
    sim = Battle(a, b, db, seed=1, **kw)
    return db, sim, a.formation.units, b.formation.units


def ctx(sim, owner, **kw):
    return Context(sim, owner, **kw)


class RegistryTests(unittest.TestCase):
    def test_every_game_condition_is_registered_with_its_kind_and_group(self):
        by_key = {f["key"]: f for f in GAME}
        self.assertEqual(set(by_key), set(FACTORS))
        for key, factor in FACTORS.items():
            self.assertEqual(factor.id, by_key[key]["id"], key)
            if by_key[key]["kind"] != "none":
                self.assertEqual(factor.kind, by_key[key]["kind"], key)
                self.assertEqual(factor.group, by_key[key]["group"], key)

    def test_two_conditions_of_one_group_are_refused(self):
        a, b, c = (condition_from_data(k) for k in ("lowest_hp", "target_hp_is_lt_50_pct", "flying"))
        check_conditions([a, c])
        check_conditions([b, c])
        with self.assertRaises(ValueError):
            check_conditions([a, b])                     # обе группы hp
        with self.assertRaises(ValueError):
            check_conditions([a, b, c])                  # больше двух

    def test_unknown_key_and_custom_conditions(self):
        with self.assertRaises(ValueError):
            condition_from_data("no_such_condition")
        custom = condition_from_data({"type": "has_effect", "effect_id": "uo_burn", "on": "target"})
        self.assertIsInstance(custom, LegacyCondition)
        self.assertEqual(condition_from_data(custom.to_data()).to_data(), custom.to_data())
        self.assertEqual(condition_from_data("flying").to_data(), "flying")


class TargetTests(unittest.TestCase):
    def test_hp_thresholds_are_inclusive_like_the_game(self):
        _, sim, (knight, mage), _ = world([("knight", 1, 0, 0), ("mage", 1, 0, 1)], [("goblin", 1, 0, 0)])
        c = ctx(sim, knight)
        mage.state.current_hp = mage.max_hp // 2
        self.assertTrue(FACTORS["target_hp_is_lt_50_pct"].accepts(c, mage))
        self.assertFalse(FACTORS["target_hp_is_lt_25_pct"].accepts(c, mage))
        self.assertTrue(FACTORS["target_hp_is_lt_100_pct"].accepts(c, mage))
        self.assertFalse(FACTORS["target_hp_is_lt_100_pct"].accepts(c, knight))
        self.assertTrue(FACTORS["target_hp_is_gt_100_pct"].accepts(c, knight))

    def test_status_and_type_filters(self):
        db, sim, (knight, mage), (goblin,) = world([("knight", 1, 0, 0), ("mage", 1, 0, 1)], [("goblin", 1, 0, 0)])
        for effect_id in ("uo_poison", "uo_phys_atk_p30pct"):
            if effect_id not in db.effects:
                from tests.test_uo_passives import copy_effect
                copy_effect(db, effect_id)
        c = ctx(sim, knight)
        sim._give(mage, "uo_poison", goblin, Act("active", goblin.uid, "x"))
        self.assertTrue(FACTORS["poisoned"].accepts(c, mage))
        self.assertFalse(FACTORS["not_poisoned"].accepts(c, mage))
        self.assertTrue(FACTORS["afflicted"].accepts(c, mage))
        self.assertTrue(FACTORS["debuffed"].accepts(c, mage))
        self.assertFalse(FACTORS["buffed"].accepts(c, mage))
        self.assertTrue(FACTORS["armored"].accepts(c, knight))          # у фикстуры knight — armored
        self.assertTrue(FACTORS["caster"].accepts(c, mage))
        self.assertTrue(FACTORS["user"].accepts(c, knight))
        self.assertTrue(FACTORS["other_combatants"].accepts(c, mage))

    def test_formation_filters_and_ranks(self):
        _, sim, _, _ = world([("knight", 1, 0, 0), ("mage", 1, 1, 0), ("archer", 1, 0, 1)], [("goblin", 1, 0, 0)])
        front, back, other = sim.units[1], sim.units[2], sim.units[3]          # uid идут по порядку записи
        c = ctx(sim, front)
        self.assertTrue(FACTORS["front_row"].accepts(c, front))
        self.assertTrue(FACTORS["back_row"].accepts(c, back))
        self.assertTrue(FACTORS["full_column"].accepts(c, front))        # колонка 0: передний и задний
        self.assertFalse(FACTORS["full_column"].accepts(c, other))
        self.assertTrue(FACTORS["row_with_2_plus_combatants"].accepts(c, front))
        self.assertFalse(FACTORS["row_with_2_plus_combatants"].accepts(c, back))
        self.assertLess(FACTORS["prioritize_front_row"].rank(c, front), FACTORS["prioritize_front_row"].rank(c, back))
        self.assertLess(FACTORS["row_with_most_combatants"].rank(c, front), FACTORS["row_with_most_combatants"].rank(c, back))

    def test_priorities_order_targets(self):
        _, sim, (knight, mage), _ = world([("knight", 1, 0, 0), ("mage", 1, 0, 1)], [("goblin", 1, 0, 0)])
        c = ctx(sim, knight)
        mage.state.current_hp = 1
        low = min((knight, mage), key=lambda u: FACTORS["lowest_hp"].rank(c, u))
        self.assertIs(low, mage)
        self.assertIs(max((knight, mage), key=lambda u: FACTORS["highest_phys_def"].rank(c, u) * -1), knight)
        self.assertLess(FACTORS["prioritize_armored"].rank(c, knight), FACTORS["prioritize_armored"].rank(c, mage))

    def test_ap_and_pp_filters(self):
        _, sim, (knight, mage), _ = world([("knight", 1, 0, 0), ("mage", 1, 0, 1)], [("goblin", 1, 0, 0)])
        c = ctx(sim, knight)
        mage.ap.spend(mage.ap.current)
        self.assertTrue(FACTORS["0_ap"].accepts(c, mage))
        self.assertFalse(FACTORS["1_or_more_ap"].accepts(c, mage))
        self.assertTrue(FACTORS["1_or_more_ap"].accepts(c, knight))


class GateTests(unittest.TestCase):
    def test_day_night_and_unit_size(self):
        _, sim, (knight, mage), (goblin, orc, rider) = world([("knight", 1, 0, 0), ("mage", 1, 0, 1)],
                                                             [("goblin", 1, 0, 0), ("orc", 1, 0, 1), ("rider", 1, 1, 0)],
                                                             time_of_day="night")
        c = ctx(sim, knight)
        self.assertTrue(FACTORS["nighttime"].gate(c))
        self.assertFalse(FACTORS["daytime"].gate(c))
        self.assertTrue(FACTORS["3_or_more_enemies"].gate(c))
        self.assertFalse(FACTORS["4_or_more_enemies"].gate(c))
        self.assertTrue(FACTORS["2_or_more_allies"].gate(c))
        self.assertTrue(FACTORS["2_or_fewer_allies"].gate(c))
        self.assertFalse(FACTORS["1_or_fewer_allies"].gate(c))
        self.assertTrue(FACTORS["cavalry_enemies_present"].gate(c))
        self.assertTrue(FACTORS["no_flying_enemies"].gate(c))
        self.assertFalse(FACTORS["no_cavalry_enemies"].gate(c))

    def test_own_state(self):
        _, sim, (knight, mage), _ = world([("knight", 1, 0, 0), ("mage", 1, 0, 1)], [("goblin", 1, 0, 0)])
        c = ctx(sim, knight, action_index=2)
        self.assertTrue(FACTORS["own_hp_is_gt_100_pct"].gate(c))
        knight.state.current_hp = knight.max_hp // 4
        self.assertTrue(FACTORS["own_hp_is_lt_25_pct"].gate(c))
        self.assertTrue(FACTORS["own_hp_is_lt_100_pct"].gate(c))
        self.assertTrue(FACTORS["second_action"].gate(c))
        self.assertFalse(FACTORS["first_action"].gate(c))
        self.assertTrue(FACTORS["own_ap_is_1_or_more"].gate(c))
        self.assertFalse(FACTORS["user_is_buffed"].gate(c))

    def test_average_hp_of_candidates(self):
        _, sim, (knight, mage), _ = world([("knight", 1, 0, 0), ("mage", 1, 0, 1)], [("goblin", 1, 0, 0)])
        mage.state.current_hp = mage.max_hp // 2
        c = ctx(sim, knight, candidates=[knight, mage])
        self.assertTrue(FACTORS["average_hp_is_lt_100_pct"].gate(c))
        self.assertTrue(FACTORS["average_hp_is_gt_50_pct"].gate(c))
        self.assertFalse(FACTORS["average_hp_is_lt_50_pct"].gate(c))
        self.assertFalse(FACTORS["average_hp_is_lt_25_pct"].gate(ctx(sim, knight)))     # целей нет

    def test_attack_conditions_read_the_moment(self):
        db, sim, (knight, mage), (goblin,) = world([("knight", 1, 0, 0), ("mage", 1, 0, 1)], [("rider", 1, 0, 0)])
        rider = sim.units[3]
        moment = Moment("targeted", subject=knight, actor=rider, skill=db.skills["attack"],
                        attack_tags=frozenset({"physical", "melee"}))
        c = ctx(sim, knight, moment=moment)
        self.assertTrue(FACTORS["physickally_attacked"].gate(c))
        self.assertFalse(FACTORS["magickally_attacked"].gate(c))
        self.assertTrue(FACTORS["attacked_by_cavalry"].gate(c))
        self.assertFalse(FACTORS["attacked_by_flying"].gate(c))
        self.assertFalse(FACTORS["row_is_attacked"].gate(c))
        self.assertFalse(FACTORS["physickally_attacked"].gate(ctx(sim, knight)))          # у активных — всегда ложь


if __name__ == "__main__":
    unittest.main()
