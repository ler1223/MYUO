"""Дополнительные действия реакции (reaction.then): одна оплата PP, несколько действий подряд."""
import unittest

from game.combat import Battle
from game.events import PassiveTriggered
from game.reactions import Reaction
from tests.helpers import plain_db, squads
from tests.test_reactions import give


class ThenTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def battle(self, left, right):
        a, b = squads(self.db, left, right)
        return Battle(a, b, self.db, seed=1)

    def test_round_trip_keeps_steps(self):
        data = dict(event="battle_start", whose="any", action="restore_ap", amount=1, to="owner",
                    then=[{"action": "heal", "amount": 10, "percent": True, "to": "owner"}])
        reaction = Reaction.from_dict(data)
        self.assertEqual(len(reaction.then), 1)
        self.assertEqual(reaction.then[0].action, "heal")
        self.assertEqual(reaction.to_dict()["then"], [{"action": "heal", "to": "owner", "amount": 10, "percent": True}])
        self.assertEqual(Reaction.from_dict(reaction.to_dict()), reaction)

    def test_cover_cannot_be_a_step(self):
        with self.assertRaises(ValueError):
            Reaction.from_dict(dict(event="targeted", whose="ally", action="cover",
                                    then=[{"action": "cover"}]))

    def test_steps_run_after_main_action_for_one_pp(self):
        give(self.db, ["knight"], pp=1, event="battle_start", whose="any", action="restore_ap", amount=1,
             to="owner", then=[{"action": "heal", "amount": 50, "percent": True, "to": "owner"},
                               {"action": "restore_pp", "amount": 2, "to": "owner"}])
        sim = self.battle([("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        knight = sim.units[1]
        knight.state.current_hp = 10
        ap_before = knight.ap.current
        events = sim.step()
        self.assertEqual(sum(isinstance(e, PassiveTriggered) and e.passive_id == "react" for e in events), 1)      # PP заплачен один раз
        self.assertGreater(knight.hp, 10)                                              # лечение
        self.assertEqual(knight.pp.current, knight.pp_max)                              # потрачен 1, возвращено 2
        self.assertGreaterEqual(knight.ap.current, ap_before)


if __name__ == "__main__":
    unittest.main()
