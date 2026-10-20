"""Строки тактики с условиями игры: формат записи и выбор навыка и цели в бою."""
import unittest

from game.combat import Battle
from game.combat.record import ACTIVE
from game.editing import set_tactics, tactic_rows
from game.save import unit_from_save, unit_to_save
from game.tactics import TacticRule, TacticsSet
from tests.helpers import add_skill, plain_db, set_stats, squads


def row(skill, *conditions):
    return {"skill": skill, "conditions": list(conditions)}


def first_skill(sim, uid):
    """Навык и цель первого хода бойца."""
    while not sim.finished:
        sim.step()
        act = sim.last_act
        if act is not None and act.kind == ACTIVE and act.actor == uid:
            return act.skill_id, act.target
    return None


class FormatTests(unittest.TestCase):
    def test_new_format_round_trips(self):
        data = [row("heal", "target_hp_is_lt_50_pct", "lowest_pct_hp"), row("attack"),
                row("attack", {"type": "has_effect", "effect_id": "uo_burn", "on": "target"}, "daytime")]
        rules = TacticsSet.from_list(data)
        self.assertEqual(rules.to_list()[0], data[0])
        self.assertEqual(TacticsSet.from_list(rules.to_list()).to_list(), rules.to_list())

    def test_old_format_is_read_and_written_in_the_new_form(self):
        old = {"skill": "attack", "self_condition": {"type": "hp_below", "value": 0.7},
               "condition": {"type": "has_tag", "tag": "flying"}, "selector": "strongest"}
        written = TacticRule.from_dict(old).to_dict()
        self.assertEqual(written["skill"], "attack")
        self.assertIn("conditions", written)
        self.assertEqual(TacticRule.from_dict(written).to_dict(), written)
        weakest = dict(old, selector="weakest", condition={"type": "always"})
        rule = TacticRule.from_dict(weakest)
        self.assertTrue(any(c.key == "lowest_pct_hp" for c in rule.conditions))      # слабейший — это условие игры

    def test_rule_with_game_conditions_is_written_in_the_new_format(self):
        data = row("attack", "flying", "lowest_pct_hp")
        self.assertEqual(TacticRule.from_dict(data).to_dict(), data)

    def test_unknown_condition_key_is_an_error(self):
        with self.assertRaises(ValueError):
            TacticRule.from_dict(row("attack", "no_such_key"))


class BattleChoiceTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()
        for unit_id in ("knight", "mage", "cleric", "goblin"):
            data = self.db.units[unit_id].to_dict()
            data["passives"] = []
            self.db.update("units", unit_id, data)
        set_stats(self.db, "goblin", hp=900, phys_atk=1)

    def start(self, tactics, left=(("cleric", 1, 0, 0), ("knight", 1, 0, 1), ("mage", 1, 1, 0)),
              right=(("goblin", 1, 0, 0),), **kw):
        a, b = squads(self.db, list(left), list(right))
        sim = Battle(a, b, self.db, seed=1, **kw)
        healer = sim.units[1]
        set_tactics(self.db, healer, tactics)
        return sim, healer

    def test_heal_waits_for_a_wounded_ally(self):
        sim, healer = self.start([row("heal", "target_hp_is_lt_50_pct"), row("magic_bolt")])
        self.assertEqual(first_skill(sim, healer.uid)[0], "magic_bolt")
        sim, healer = self.start([row("heal", "target_hp_is_lt_50_pct"), row("magic_bolt")])
        sim.units[3].state.current_hp = 1
        skill, target = first_skill(sim, healer.uid)
        self.assertEqual((skill, target), ("heal", 3))

    def test_priority_picks_the_weakest_ally(self):
        sim, healer = self.start([row("heal", "lowest_hp")])
        sim.units[2].state.current_hp = 20
        sim.units[3].state.current_hp = 5
        self.assertEqual(first_skill(sim, healer.uid), ("heal", 3))

    def test_target_only_without_candidates_falls_to_the_next_rule(self):
        sim, healer = self.start([row("magic_bolt", "flying"), row("magic_bolt", "infantry")])
        self.assertEqual(first_skill(sim, healer.uid), ("magic_bolt", 4))

    def test_activates_only_gates_the_whole_rule(self):
        for time_of_day, expected in (("night", "magic_bolt"), ("day", "heal")):
            sim, healer = self.start([row("heal", "daytime"), row("magic_bolt")], time_of_day=time_of_day)
            sim.units[3].state.current_hp = 1
            self.assertEqual(first_skill(sim, healer.uid)[0], expected, time_of_day)

    def test_first_action_rule_is_used_once(self):
        add_skill(self.db, "opening", ["cleric"], ap_cost=1, tags=["melee"],
                  parts=[{"kind": "damage", "category": "physical", "power": 0.1,
                          "scaling": [{"stat": "phys_atk", "coef": 1.0}]}])
        sim, healer = self.start([row("opening", "first_action"), row("magic_bolt")])
        used = []
        while not sim.finished and len(used) < 3:
            sim.step()
            act = sim.last_act
            if act is not None and act.kind == ACTIVE and act.actor == healer.uid:
                used.append(act.skill_id)
        self.assertEqual(used[:2], ["opening", "magic_bolt"])


if __name__ == "__main__":
    unittest.main()


class UnifiedListTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def test_passives_without_a_row_follow_the_active_rows(self):
        unit = self.db.create_unit("knight", 1)
        passive = next(p for p in unit.passive_ids if p in self.db.skills)
        rows = tactic_rows(self.db, unit)
        self.assertEqual(rows[-1 - [r["skill"] for r in reversed(rows)].index(passive)]["skill"], passive)
        self.assertEqual(len([r for r in rows if r["skill"] == passive]), 1)

    def test_old_save_with_passive_tactics_becomes_a_row(self):
        unit = self.db.create_unit("knight", 1)
        passive = next(p for p in unit.passive_ids if p in self.db.skills)
        data = unit_to_save(unit)
        self.assertNotIn("passive_tactics", data)
        data["passive_tactics"] = {passive: [{"skill": "attack", "self_condition": {"type": "always"},
                                              "condition": {"type": "always"}, "selector": "frontmost"}]}
        restored = unit_from_save(self.db, data)
        self.assertIn(passive, [r.skill_id for r in restored.tactics.rules])
