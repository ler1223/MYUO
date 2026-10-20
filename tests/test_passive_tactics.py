"""Тактики пассивок: правила применяются к целям, вызвавшим срабатывание, предел n за действие."""
import unittest

from game.combat import Battle as BattleSimulation
from game.editing import set_owners, set_passive_tactics
from game.events import PassiveTriggered, SkillUsed
from game.save import unit_from_save, unit_to_save
from game.tactics import TacticsSet
from tests.helpers import add_skill, only, plain_db, rule, squads, turn_of
from tests.test_combat import part
from tests.test_reactions import counter, give


def react_with_rules(db, unit, passive_id: str, skill_id: str, **conditions) -> None:
    """Привязывает к пассивке юнита правило тактики: навык по вызвавшей цели."""
    set_passive_tactics(db, unit, passive_id, [rule(skill_id, **conditions)])


class PassiveRulesTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def battle(self, left, right, seed=1):
        a, b = squads(self.db, left, right)
        sim = BattleSimulation(a, b, self.db, seed=seed)
        return sim, sim.units[1], sim.units[2]

    def test_rule_of_passive_uses_its_skill_on_the_cause(self):
        add_skill(self.db, "riposte", ["orc"], parts=[part(power=0.6)])
        give(self.db, ["orc"], **counter())
        sim, knight, orc = self.battle([("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        react_with_rules(self.db, orc, "react", "riposte")
        only(self.db, knight, "attack")
        events = turn_of(sim, 1)
        i = events.index(SkillUsed(1, "attack", 2))
        # правило выбрало riposte вместо стандартной атаки из реакции, цель — атаковавший
        self.assertEqual(events[i + 2:i + 4], [PassiveTriggered(2, "react"), SkillUsed(2, "riposte", 1)])

    def test_rule_falls_back_to_reaction_when_conditions_do_not_hold(self):
        add_skill(self.db, "riposte", ["orc"], parts=[part(power=0.6)],
                  requires_target={"type": "has_effect", "effect_id": "poison"})
        give(self.db, ["orc"], **counter())
        sim, knight, orc = self.battle([("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        react_with_rules(self.db, orc, "react", "riposte")
        only(self.db, knight, "attack")
        events = turn_of(sim, 1)
        i = events.index(SkillUsed(1, "attack", 2))
        # цель не отравлена: правило не подошло, сработала стандартная реакция (attack по атаковавшему)
        self.assertEqual(events[i + 2:i + 4], [PassiveTriggered(2, "react"), SkillUsed(2, "attack", 1)])

    def test_rule_takes_targets_of_the_trigger_not_the_whole_side(self):
        # Союзник применил навык по врагу: правило пассивки бьёт по цели навыка, а не по всем врагам.
        add_skill(self.db, "follow", ["goblin"], parts=[part(power=0.6)])
        give(self.db, ["goblin"], event="skill_used", whose="ally", action="use_skill", skill_id="attack",
             to="target")
        sim, knight, goblin = self.battle([("knight", 1, 0, 0), ("goblin", 1, 0, 1)], [("orc", 1, 0, 0), ("archer", 1, 0, 1)])
        react_with_rules(self.db, goblin, "react", "follow")
        only(self.db, knight, "attack")
        sim.step()                                   # гоблин быстрее и ходит первым
        events = turn_of(sim, 1)
        i = events.index(SkillUsed(1, "attack", 3))
        self.assertIn(SkillUsed(2, "follow", 3), events[i + 1:])   # цель — тот, по кому ударил союзник
        self.assertNotIn(SkillUsed(2, "follow", 4), events)
        self.assertEqual(goblin.pp.current, goblin.pp_max - 1)     # пассивка платит PP, а не AP

    def test_limit_of_passives_per_one_active_action(self):
        set_owners(self.db, "units", "avenger", [])   # убираем классовую пассивку, чтобы не мешала счёту
        give(self.db, ["orc"], passive_id="one", pp=1, event="attacked", whose="any",
             action="restore_pp", amount=0, to="owner")
        a, b = squads(self.db, [("knight", 50, 0, 0)],
                      [("orc", 50, 0, 0), ("orc", 50, 0, 1), ("orc", 50, 1, 0)])
        sim = BattleSimulation(a, b, self.db, seed=1)
        only(self.db, sim.units[1], "attack")
        fired = [e for e in turn_of(sim, 1) if isinstance(e, PassiveTriggered)]
        self.assertEqual(len(fired), 2)              # за одно действие — не больше n=2 пассивок

    def test_config_raises_the_limit(self):
        db = plain_db()
        db.passives_per_action = 3
        set_owners(db, "units", "avenger", [])
        give(db, ["orc"], passive_id="one", pp=1, event="attacked", whose="any",
             action="restore_pp", amount=0, to="owner")
        a, b = squads(db, [("knight", 50, 0, 0)],
                      [("orc", 50, 0, 0), ("orc", 50, 0, 1), ("orc", 50, 1, 0)])
        sim = BattleSimulation(a, b, db, seed=1)
        only(db, sim.units[1], "attack")
        fired = [e for e in turn_of(sim, 1) if isinstance(e, PassiveTriggered)]
        self.assertEqual(len(fired), 3)

    def test_passive_tactics_survive_save_and_load(self):
        add_skill(self.db, "riposte", ["orc"], parts=[part(power=0.6)])
        give(self.db, ["orc"], **counter())
        sim, knight, orc = self.battle([("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        react_with_rules(self.db, orc, "react", "riposte", condition={"type": "hp_below", "value": 0.7},
                         self_condition={"type": "hp_above", "value": 0.1}, selector="weakest")
        data = unit_to_save(orc)
        self.assertEqual(data["passive_tactics"]["react"][0]["skill"], "riposte")
        restored = unit_from_save(self.db, data)
        rules = restored.passive_tactics_of("react").to_list()
        self.assertEqual(rules[0]["condition"], {"type": "hp_below", "value": 0.7})
        self.assertEqual(rules[0]["selector"], "weakest")
        self.assertTrue(restored.has_passive_tactics("react"))

    def test_removed_skill_drops_the_rule_on_load(self):
        give(self.db, ["orc"], **counter())
        add_skill(self.db, "temp_skill", [], parts=[part()])
        orc = self.db.create_unit("orc", 2, 1)
        set_passive_tactics(self.db, orc, "react", [rule("temp_skill")])
        data = unit_to_save(orc)
        self.db.delete("skills", "temp_skill")
        restored = unit_from_save(self.db, data)
        self.assertEqual(restored.passive_tactics, {})


if __name__ == "__main__":
    unittest.main()
