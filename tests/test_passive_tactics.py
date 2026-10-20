"""Пассивки в тактике бойца: строки с условиями игры, порядок, выключенные строки, предел n за действие."""
import unittest

from game.combat import Battle as BattleSimulation
from game.editing import set_owners, set_tactics
from game.events import PassiveTriggered, SkillUsed
from tests.helpers import only, plain_db, squads, turn_of
from tests.test_reactions import counter, give


def set_tactics_rows(db, unit, rows) -> None:
    """Строки тактики бойца: активные и пассивные вперемешку (формат с ключами условий игры)."""
    set_tactics(db, unit, rows)


class PassiveRulesTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def battle(self, left, right, seed=1):
        a, b = squads(self.db, left, right)
        sim = BattleSimulation(a, b, self.db, seed=seed)
        return sim, sim.units[1], sim.units[2]

    def fired(self, sim, uid):
        return [e for e in turn_of(sim, uid) if isinstance(e, PassiveTriggered) and e.passive_id == "react"]

    def test_row_conditions_gate_the_passive(self):
        # «Атакован кавалерией»: орк отвечает контратакой только на удар всадника
        give(self.db, ["orc"], **counter())
        for attacker, expected in (("rider", 1), ("knight", 0)):
            db = self.db.copy()
            a, b = squads(db, [(attacker, 1, 0, 0)], [("orc", 1, 0, 0)])
            sim = BattleSimulation(a, b, db, seed=1)
            only(db, sim.units[1], "attack")
            set_tactics_rows(db, sim.units[2], [{"skill": "react", "conditions": ["attacked_by_cavalry"]}])
            self.assertEqual(len(self.fired(sim, 1)), expected, attacker)

    def test_disabled_row_turns_the_passive_off(self):
        give(self.db, ["orc"], **counter())
        sim, knight, orc = self.battle([("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        only(self.db, knight, "attack")
        self.assertEqual(len(self.fired(sim, 1)), 1)                          # без строки — работает с условиями по умолчанию
        sim, knight, orc = self.battle([("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        only(self.db, knight, "attack")
        set_tactics_rows(self.db, orc, [{"skill": "react", "conditions": [], "off": True}])
        self.assertEqual(self.fired(sim, 1), [])

    def test_target_filter_without_candidates_keeps_the_pp(self):
        give(self.db, ["orc"], **counter())
        sim, knight, orc = self.battle([("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        only(self.db, knight, "attack")
        set_tactics_rows(self.db, orc, [{"skill": "react", "conditions": ["flying"]}])    # атаковавший не летает
        self.assertEqual(self.fired(sim, 1), [])
        self.assertEqual(orc.pp.current, orc.pp.max)

    def test_priority_picks_the_target_among_the_group(self):
        # пассивка бьёт по врагам из группы: «наименьшее HP» выбирает слабейшего
        give(self.db, ["goblin"], event="skill_used", whose="ally", action="use_skill", skill_id="attack",
             to="enemies")
        sim, knight, goblin = self.battle([("knight", 1, 0, 0), ("goblin", 1, 0, 1)],
                                          [("orc", 1, 0, 0), ("archer", 1, 0, 1)])
        set_tactics_rows(self.db, goblin, [{"skill": "react", "conditions": ["lowest_hp"]}])
        only(self.db, knight, "attack")
        sim.step()                                   # гоблин быстрее и ходит первым
        sim.units[4].state.current_hp = 20          # слабее орка, но переживёт яд до удара
        events = turn_of(sim, 1)
        self.assertIn(SkillUsed(2, "attack", 4), events)

    def test_rows_of_passives_are_taken_in_tactics_order(self):
        # две пассивки на одно событие: сверху в тактике — раньше (а предел n=1 оставляет только первую)
        self.db.passives_per_action = 1
        give(self.db, ["orc"], passive_id="first", **counter())
        give(self.db, ["orc"], passive_id="second", **counter())
        sim, knight, orc = self.battle([("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        only(self.db, knight, "attack")
        set_tactics_rows(self.db, orc, [{"skill": "second", "conditions": []}, {"skill": "first", "conditions": []}])
        fired = [e.passive_id for e in turn_of(sim, 1) if isinstance(e, PassiveTriggered)]
        self.assertEqual(fired, ["second"])

    def test_battle_start_passive_waits_for_its_condition(self):
        # навык начала боя с условием «летающие враги на поле»
        give(self.db, ["knight"], event="battle_start", whose="self", action="use_skill", skill_id="attack",
             to="enemies")
        for enemy, expected in (("orc", 0), ("rider", 0)):
            sim, knight, orc = self.battle([("knight", 1, 0, 0)], [(enemy, 1, 0, 0)])
            set_tactics_rows(self.db, knight, [{"skill": "react", "conditions": ["flying_enemies_present"]}])
            sim.step()
            self.assertEqual(len([e for e in sim.events if isinstance(e, PassiveTriggered)
                                  and e.passive_id == "react"]), expected, enemy)
        sim, knight, orc = self.battle([("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        set_tactics_rows(self.db, knight, [{"skill": "react", "conditions": ["infantry_enemies_present"]}])
        sim.step()
        self.assertTrue([e for e in sim.events if isinstance(e, PassiveTriggered) and e.passive_id == "react"])

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


if __name__ == "__main__":
    unittest.main()
