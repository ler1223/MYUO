"""Тесты реакций: события, фильтры, действие «применить навык», порядок, лимиты, фаза «до»."""
import unittest

from game.battle import BattleSimulation
from game.database import Database
from game.editing import describe_reaction, new_passive_data, reaction_defaults, set_owners
from game.events import (
    AttackMissed,
    DamageDealt,
    EffectApplied,
    Healed,
    PassiveTriggered,
    ResourceGained,
    RoundStarted,
    SkillUsed,
    UnitDied,
)
from game.reactions import Reaction
from tests.helpers import add_skill, only, plain_db, squads, turn_of
from tests.test_combat import part


def give(db: Database, owners, passive_id="react", pp=1, pp_max=9, **reaction) -> None:
    """Пассивка с одной реакцией для классов owners; запас PP классов поднимается до pp_max."""
    db.update("passives", passive_id, {"name": passive_id, "pp_cost": pp, "reaction": reaction})
    set_owners(db, "units", passive_id, list(owners), field="passives")
    for unit_id in owners:
        data = db.units[unit_id].to_dict()
        db.update("units", unit_id, dict(data, pp_max=pp_max))


def counter(**extra):
    """Контратака: по владельцу попали -> обычная атака по атаковавшему."""
    return dict(event="attacked", whose="self", outcome="landed", action="use_skill", skill_id="attack",
                to="actor", **extra)


def triggered(events, passive_id="react"):
    return [e.unit for e in events if isinstance(e, PassiveTriggered) and e.passive_id == passive_id]


class UseSkillTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def battle(self, left, right, seed=1):
        a, b = squads(self.db, left, right)
        return BattleSimulation(a, b, self.db, seed=seed)

    def test_counterattack_costs_pp_not_ap_and_is_not_countered(self):
        give(self.db, ["orc", "knight"], **counter())
        sim = self.battle([("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        knight, orc = sim.units[1], sim.units[2]
        only(self.db, knight, "attack")
        events = turn_of(sim, 1)
        i = events.index(SkillUsed(1, "attack", 2))
        self.assertEqual(events[i + 2:i + 4], [PassiveTriggered(2, "react"), SkillUsed(2, "attack", 1)])
        self.assertEqual(triggered(events), [2])          # на контратаку рыцарь не отвечает: цепочки нет
        self.assertEqual((orc.ap.current, orc.pp.current), (orc.ap.max, orc.pp.max - 1))
        self.assertTrue(any(isinstance(e, DamageDealt) and e.target == 1 for e in events[i:]))

    def test_reaction_on_miss(self):
        add_skill(self.db, "whiff", ["knight"], accuracy=0, parts=[part()])
        give(self.db, ["orc"], **dict(counter(), outcome="missed"))
        sim = self.battle([("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        only(self.db, sim.units[1], "whiff")
        events = turn_of(sim, 1)
        self.assertIn(AttackMissed(1, 2, "whiff"), events)
        self.assertEqual(triggered(events), [2])

    def test_every_hit_of_a_multi_hit_skill_is_an_event_and_limits_work(self):
        add_skill(self.db, "double", ["knight"], hits=2, parts=[part(power=0.3)])
        for limit, expected in (("none", 2), ("round", 1)):
            give(self.db, ["orc"], **counter(limit=limit))
            sim = self.battle([("knight", 9, 0, 0)], [("orc", 9, 0, 0)])
            only(self.db, sim.units[1], "double")
            self.assertEqual(len(triggered(turn_of(sim, 1))), expected, limit)

    def test_limit_per_battle(self):
        give(self.db, ["orc"], **counter(limit="battle"))
        sim = self.battle([("knight", 9, 0, 0)], [("orc", 9, 0, 0)])
        only(self.db, sim.units[1], "attack")
        self.assertEqual(len(triggered(sim.run())), 1)

    def test_follow_up_on_the_target_of_an_allys_skill(self):
        give(self.db, ["goblin"], event="skill_used", whose="ally", action="use_skill", skill_id="attack", to="target")
        sim = self.battle([("knight", 1, 0, 0), ("goblin", 1, 0, 1)], [("orc", 1, 0, 0)])
        knight, goblin = sim.units[1], sim.units[2]
        only(self.db, knight, "attack")
        only(self.db, goblin, "attack")
        sim.step()                                   # гоблин быстрее и ходит первым
        ap_before = goblin.ap.current
        events = turn_of(sim, 1)
        i = events.index(SkillUsed(1, "attack", 3))
        self.assertIn(SkillUsed(2, "attack", 3), events[i + 1:])
        self.assertEqual(goblin.ap.current, ap_before)   # навык-реакция не тратит AP

    def test_skill_requirements_are_checked(self):
        add_skill(self.db, "finisher", [], parts=[part(power=3)], requires_target={"type": "has_effect", "effect_id": "poison"})
        give(self.db, ["orc"], **dict(counter(), skill_id="finisher"))
        sim = self.battle([("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        only(self.db, sim.units[1], "attack")
        self.assertEqual(triggered(turn_of(sim, 1)), [])   # цель не отравлена: навык неприменим, PP целы
        self.assertEqual(sim.units[2].pp.current, sim.units[2].pp.max)

    def test_stunned_owner_does_not_react(self):
        give(self.db, ["orc"], **counter())
        sim = self.battle([("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        only(self.db, sim.units[1], "attack")
        sim.units[2].add_effect(self.db.effects["stun"])
        self.assertEqual(triggered(turn_of(sim, 1)), [])


class EventTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def battle(self, left, right, seed=1):
        a, b = squads(self.db, left, right)
        return BattleSimulation(a, b, self.db, seed=seed)

    def test_hp_below_fires_once_per_crossing_and_rearms_after_healing(self):
        give(self.db, ["orc"], event="hp_below", whose="self", threshold=0.5, action="apply_effect",
             effect_id="war_cry", to="owner")
        sim = self.battle([("knight", 9, 0, 0)], [("orc", 1, 0, 0)])
        knight, orc = sim.units[1], sim.units[2]
        only(self.db, knight, "attack")
        only(self.db, orc, "attack")
        fired, healed = [], False
        while not sim.finished:
            events = sim.step()
            fired += triggered(events)
            if fired and not healed and orc.is_alive:
                orc.state.current_hp = orc.max_hp   # вылечили выше порога: реакция снова взведена
                healed = True
        self.assertEqual(fired, [2, 2])

    def test_reactions_go_in_initiative_order(self):
        give(self.db, ["goblin", "cleric"], event="attacked", whose="ally", action="apply_effect",
             effect_id="war_cry", to="owner")
        # Клирик раньше гоблина по формации, но у гоблина выше инициатива (8 против 6).
        sim = self.battle([("orc", 1, 0, 0)], [("knight", 1, 0, 0), ("cleric", 1, 0, 1), ("goblin", 1, 1, 0)])
        only(self.db, sim.units[1], "attack")
        self.assertEqual(triggered(turn_of(sim, 1)), [4, 3])

    def test_before_phase_one_reaction_per_side(self):
        give(self.db, ["goblin", "cleric"], event="targeted", whose="ally", action="use_skill", skill_id="attack",
             to="actor")
        sim = self.battle([("orc", 1, 0, 0)], [("knight", 1, 0, 0), ("cleric", 1, 0, 1), ("goblin", 1, 1, 0)])
        only(self.db, sim.units[1], "attack")
        events = turn_of(sim, 1)
        self.assertEqual(triggered(events), [4])             # первым по инициативе успевает гоблин, и только он
        strike = events.index(SkillUsed(4, "attack", 1))
        hit = next(i for i, e in enumerate(events) if isinstance(e, DamageDealt) and e.source == 1)
        self.assertLess(strike, hit)                          # удар на опережение до атаки орка

    def test_crit_outcome_and_whose_enemy(self):
        data = self.db.units["knight"].to_dict()
        data["stats"]["crit_rate"] = 100
        self.db.update("units", "knight", data)
        give(self.db, ["knight"], event="attacked", whose="enemy", outcome="crit", action="apply_effect",
             effect_id="war_cry", to="owner")
        sim = self.battle([("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        only(self.db, sim.units[1], "attack")
        events = turn_of(sim, 1)
        self.assertEqual(triggered(events), [1])
        self.assertIn(EffectApplied(1, "war_cry", 1, 1), events)

    def test_effect_with_thorns(self):
        self.db.update("effects", "thorns", {"name": "Thorns", "triggers": [
            {"event": "attacked", "whose": "self", "outcome": "landed", "action": "damage", "amount": 5, "to": "actor"}]})
        sim = self.battle([("orc", 1, 0, 0)], [("knight", 1, 0, 0)])
        sim.units[2].add_effect(self.db.effects["thorns"], source=2)
        only(self.db, sim.units[1], "attack")
        events = turn_of(sim, 1)
        self.assertTrue(any(isinstance(e, DamageDealt) and e.target == 1 and e.cause == "thorns" and e.amount == 5
                            for e in events))

    def test_explodes_on_death(self):
        add_skill(self.db, "nuke", ["knight"], parts=[part(power=5)])
        self.db.update("effects", "volatile", {"name": "Volatile", "triggers": [
            {"event": "died", "whose": "self", "action": "damage", "amount": 7, "to": "enemies"}]})
        sim = self.battle([("knight", 9, 0, 0)], [("orc", 1, 0, 0), ("goblin", 1, 0, 1)])
        sim.units[2].add_effect(self.db.effects["volatile"], source=2)
        only(self.db, sim.units[1], "nuke")
        events = turn_of(sim, 1)
        death = events.index(UnitDied(2))
        self.assertTrue(any(isinstance(e, DamageDealt) and e.target == 1 and e.cause == "volatile"
                            for e in events[death:]))

    def test_round_end_and_round_start(self):
        self.db.update("effects", "second_wind", {"name": "Second Wind", "triggers": [
            {"event": "round_end", "action": "restore_ap", "amount": 1, "to": "owner"},
            {"event": "round_start", "action": "heal", "amount": 3, "to": "owner"}]})
        sim = self.battle([("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        knight = sim.units[1]
        knight.add_effect(self.db.effects["second_wind"], source=1)
        knight.take_damage(10)
        events = sim.run()
        second = events.index(RoundStarted(2))
        self.assertIsInstance(events[second - 1], ResourceGained)   # конец первого раунда
        self.assertEqual(events[second + 1], Healed(1, 1, 3, events[second + 1].hp_left, "second_wind"))

    def test_turn_end(self):
        self.db.update("effects", "afterglow", {"name": "Afterglow", "triggers": [
            {"event": "turn_end", "whose": "self", "action": "heal", "amount": 2, "to": "owner"}]})
        sim = self.battle([("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        knight = sim.units[1]
        knight.add_effect(self.db.effects["afterglow"], source=1)
        knight.take_damage(10)
        events = turn_of(sim, 1)
        self.assertEqual((type(events[-1]), events[-1].amount), (Healed, 2))

    def test_effect_applied_filter_and_cleanse(self):
        # Иммунитет: на владельца наложили яд -> снять яд.
        give(self.db, ["orc"], pp=0, event="effect_applied", whose="self", effect_filter="poison",
             action="remove_effect", effect_id="poison", to="owner")
        add_skill(self.db, "venom", ["knight"], parts=[part(power=0.1)], applies=[{"effect_id": "poison"}])
        sim = self.battle([("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        only(self.db, sim.units[1], "venom")
        turn_of(sim, 1)
        self.assertFalse(sim.units[2].has_effect("poison"))


class DataTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def test_roundtrip_and_validation(self):
        give(self.db, ["orc"], **counter(limit="round", area="row", attack_tags=["melee"]))
        passive = self.db.passives["react"]
        self.assertEqual(self.db.copy().passives["react"], passive)
        bad = [
            dict(counter(), event="sometime"),
            dict(counter(), skill_id=None),
            dict(counter(), skill_id="no_such_skill"),
            dict(counter(), action="cover"),         # прикрытие только в фазе «до»
            dict(counter(), area="cone"),
            dict(counter(), attack_tags=["no_such_tag"]),
            dict(counter(), limit="sometimes"),
        ]
        for reaction in bad:
            with self.assertRaises(ValueError, msg=reaction):
                self.db.update("passives", "bad", {"name": "bad", "reaction": reaction})
            self.assertNotIn("bad", self.db.passives)

    def test_deleting_the_skill_removes_the_passive(self):
        add_skill(self.db, "riposte", [], parts=[part()])
        give(self.db, ["orc"], **dict(counter(), skill_id="riposte"))
        self.db.delete("skills", "riposte")
        self.assertNotIn("react", self.db.passives)
        self.assertNotIn("react", self.db.units["orc"].passives)

    def test_defaults_and_description(self):
        data = new_passive_data(self.db)
        reaction = Reaction.from_dict(data["reaction"])
        self.assertEqual((reaction.action, reaction.skill_id, reaction.to), ("use_skill", "attack", "actor"))
        self.assertEqual(describe_reaction(reaction, self.db), "attacked (self), landed -> use_skill Attack -> actor")
        cover = reaction_defaults(self.db, data["reaction"], "action", "cover")
        self.assertEqual((cover["event"], cover["whose"]), ("targeted", "ally"))
        Reaction.from_dict(cover)
        back = reaction_defaults(self.db, cover, "event", "died")
        self.assertEqual(back["action"], "apply_effect")
        Reaction.from_dict(back)


if __name__ == "__main__":
    unittest.main()
