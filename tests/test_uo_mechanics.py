"""Механики в духе Unicorn Overlord: уровни блока, состояния, защитные заряды, событие «перед навыком»,
условная сила, игнор защиты, кража AP/PP, награда за добивание, проценты HP, снятие по метке."""
import unittest

from game.battle import BattleSimulation
from game.events import AttackMissed, DamageDealt, PassiveTriggered, TurnSkipped
from game.stats import Stat
from tests.helpers import add_skill, duel, only, plain_db, set_stats, turn_of

HIT = {"kind": "damage", "category": "physical", "power": 1.0}


def strike(**extra):
    return {"ap_cost": 1, "targets": "enemy", "tags": ["melee"], "parts": [HIT], **extra}


def effect(db, effect_id, **data):
    db.update("effects", effect_id, {"name": effect_id, "duration": 3, **data})


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()
        data = self.db.to_dict()
        data["config"]["guard"] = {"levels": {"small": 0.25, "medium": 0.5, "heavy": 0.75}, "base": "small",
                                   "tags": {"armored": "heavy"}}
        self.db._apply(data)
        add_skill(self.db, "hit", ["knight", "orc"], **strike())

    def damage_to_defender(self, guard_rate, attacker="orc", defender="orc", extras=None):
        if extras is not None:
            add_skill(self.db, "hit", ["knight", "orc"], **strike(extras=extras))
        set_stats(self.db, defender, guard_rate=guard_rate)
        sim, a, b = duel(self.db, attacker, defender)
        only(self.db, a, "hit")
        events = turn_of(sim, a.uid) if a.stat(Stat.INITIATIVE) >= b.stat(Stat.INITIATIVE) else None
        while events is None or not any(isinstance(e, DamageDealt) and e.target == b.uid for e in events):
            events = turn_of(sim, a.uid)
        return next(e.amount for e in events if isinstance(e, DamageDealt) and e.target == b.uid)

    def test_guard_level_comes_from_tags_and_unguardable_attacks_ignore_it(self):
        plain = self.damage_to_defender(0)
        small = self.damage_to_defender(100)                     # орк без щита: малый блок, -25%
        self.assertEqual(small, round(plain * 0.75))
        heavy = self.damage_to_defender(100, defender="knight")   # бронированный: тяжёлый блок
        self.assertLess(heavy, small)
        through = self.damage_to_defender(100, extras={"unguardable_vs": ["infantry"]})
        self.assertEqual(through, plain)

    def test_forced_guard_from_a_passive_charge(self):
        plain = self.damage_to_defender(0, attacker="knight")
        effect(self.db, "quick_guard", flags=["guard:medium"], charges=1, tags=["buff"])
        self.db.update("passives", "quick", {"name": "quick", "pp_cost": 1, "reaction": {
            "event": "targeted", "whose": "self", "action": "apply_effect", "effect_id": "quick_guard",
            "to": "owner", "attack_tags": ["physical"]}})
        data = self.db.units["orc"].to_dict()
        data["passives"] = ["quick"]
        self.db.update("units", "orc", data)
        sim, a, b = duel(self.db, "knight", "orc")
        only(self.db, a, "hit")
        events = turn_of(sim, a.uid)
        dealt = next(e.amount for e in events if isinstance(e, DamageDealt) and e.target == b.uid)
        self.assertEqual(dealt, round(plain * 0.5))
        self.assertIn(PassiveTriggered(b.uid, "quick"), events)
        self.assertFalse(b.has_effect("quick_guard"))             # заряд потрачен


class AilmentTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()
        add_skill(self.db, "hit", ["knight", "orc"], **strike())

    def test_frozen_unit_skips_cannot_evade_and_thaws_when_hit(self):
        effect(self.db, "freeze", flags=["frozen"], tags=["debuff", "ailment"])
        set_stats(self.db, "orc", evasion=100)
        sim, a, b = duel(self.db, "knight", "orc")
        only(self.db, a, "hit")
        b.add_effect(self.db.effects["freeze"])
        events = turn_of(sim, a.uid)
        self.assertTrue(any(isinstance(e, DamageDealt) and e.target == b.uid for e in events))   # не уклонился
        self.assertFalse(b.has_effect("freeze"))                                                 # оттаял

    def test_blind_attacker_always_misses_and_seals_block_passives(self):
        effect(self.db, "blind", flags=["blind"], duration=1, tags=["debuff", "ailment"])
        add_skill(self.db, "hit", ["knight", "orc"], **strike(extras={"truestrike": True}))
        sim, a, b = duel(self.db, "knight", "orc")
        only(self.db, a, "hit")
        a.add_effect(self.db.effects["blind"])
        events = turn_of(sim, a.uid)
        self.assertIn(AttackMissed(a.uid, b.uid, "hit"), events)                  # даже верный удар
        effect(self.db, "seal", flags=["frozen"])
        sim, a, b = duel(self.db, "knight", "orc")
        a.add_effect(self.db.effects["seal"])
        self.assertTrue(any(isinstance(e, TurnSkipped) for e in turn_of(sim, a.uid)))

    def test_poison_takes_a_percent_of_max_hp(self):
        effect(self.db, "uo_poison", tags=["debuff", "ailment"], triggers=[{
            "event": "turn_start", "whose": "self", "action": "damage", "amount": 30, "percent": True,
            "to": "owner"}])
        sim, a, b = duel(self.db, "knight", "orc")
        b.add_effect(self.db.effects["uo_poison"])
        events = turn_of(sim, b.uid)
        hit = next(e for e in events if isinstance(e, DamageDealt) and e.target == b.uid)
        self.assertEqual(hit.amount, round(b.max_hp * 0.3))


class ChargeTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()
        add_skill(self.db, "hit", ["knight", "orc"], **strike(hits=2))

    def test_evade_and_negate_charges_take_one_hit_each(self):
        effect(self.db, "dodge", flags=["evade:melee"], charges=1)
        sim, a, b = duel(self.db, "knight", "orc")
        only(self.db, a, "hit")
        b.add_effect(self.db.effects["dodge"])
        events = turn_of(sim, a.uid)
        self.assertEqual(sum(1 for e in events if isinstance(e, AttackMissed)), 1)   # второй удар прошёл
        effect(self.db, "wall", flags=["negate:magical"], charges=1)
        sim, a, b = duel(self.db, "knight", "orc")
        only(self.db, a, "hit")
        b.add_effect(self.db.effects["wall"])
        turn_of(sim, a.uid)
        self.assertTrue(b.has_effect("wall"))                                         # физику не ловит

    def test_endure_and_debuff_immunity(self):
        effect(self.db, "endure", flags=["endure"], charges=1)
        effect(self.db, "ward", flags=["immune:debuff"], charges=1)
        effect(self.db, "weak", tags=["debuff"], modifiers=[{"stat": "phys_atk", "op": "PERCENT_ADD", "value": -0.3}])
        set_stats(self.db, "knight", phys_atk=999)
        sim, a, b = duel(self.db, "knight", "orc")
        only(self.db, a, "hit")
        b.add_effect(self.db.effects["endure"])
        turn_of(sim, a.uid)
        self.assertEqual(b.hp, 0)                                          # пережил первый удар, не второй
        sim, a, b = duel(self.db, "knight", "orc")
        b.add_effect(self.db.effects["ward"])
        self.assertIsNone(sim._give_effect(b, "weak", a.uid))
        self.assertIsNotNone(sim._give_effect(b, "weak", a.uid))           # заряд потрачен


class SkillExtrasTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def first_damage(self, **extra):
        add_skill(self.db, "hit", ["knight"], **strike(**extra))
        sim, a, b = duel(self.db, "knight", "orc")
        only(self.db, a, "hit")
        events = turn_of(sim, a.uid)
        return sim, a, b, next(e.amount for e in events if isinstance(e, DamageDealt) and e.target == b.uid)

    def test_potency_bonus_and_defence_ignore(self):
        _, _, b, plain = self.first_damage()
        _, _, _, vs_infantry = self.first_damage(potency=[{"add": 0.5, "target_condition": {
            "type": "has_tag", "tag": "infantry"}}])
        self.assertEqual(vs_infantry, round(plain * 1.5))
        _, _, _, scaled = self.first_damage(potency=[{"add": 1.0, "scale": "target_hp_missing"}])
        self.assertEqual(scaled, plain)                                   # цель цела: прибавки нет
        _, a, b, pierced = self.first_damage(extras={"ignore_def": 1.0})
        self.assertEqual(pierced, a.stat(Stat.PHYS_ATK))

    def test_drain_steal_and_kill_rewards(self):
        sim, a, b, _ = self.first_damage(extras={"ap_drain": 1, "steal": True, "kill_pp": 1})
        self.assertEqual(b.ap.current, b.ap.max - 1)
        self.assertEqual(a.ap.current, a.ap.max)                          # потратил 1, украл 1
        set_stats(self.db, "knight", phys_atk=999)
        sim, a, b, _ = self.first_damage(extras={"kill_pp": 1, "kill_heal": 0.5})
        self.assertFalse(b.is_alive)
        self.assertEqual(a.pp.current, a.pp.max)

    def test_before_skill_event_and_dispel_by_label(self):
        effect(self.db, "focus", tags=["buff"], modifiers=[{"stat": "phys_atk", "op": "PERCENT_ADD", "value": 0.5}])
        self.db.update("passives", "rally", {"name": "rally", "pp_cost": 1, "reaction": {
            "event": "before_skill", "whose": "self", "action": "apply_effect", "effect_id": "focus",
            "to": "owner", "limit": "battle"}})
        data = self.db.units["knight"].to_dict()
        data["passives"] = ["rally"]
        self.db.update("units", "knight", data)
        add_skill(self.db, "hit", ["knight"], **strike(extras={"dispel": ["buff"]}))
        sim, a, b = duel(self.db, "knight", "orc")
        only(self.db, a, "hit")
        b.add_effect(self.db.effects["focus"])
        events = turn_of(sim, a.uid)
        self.assertLess(events.index(PassiveTriggered(a.uid, "rally")),
                        next(i for i, e in enumerate(events) if isinstance(e, DamageDealt)))
        self.assertTrue(a.has_effect("focus"))
        self.assertFalse(b.has_effect("focus"))                           # бафф цели снят ударом

    def test_taunt_draws_single_target_attacks(self):
        effect(self.db, "provoke", flags=["taunt"])
        add_skill(self.db, "hit", ["knight", "orc"], **strike())
        from tests.helpers import squads
        a, b = squads(self.db, [("knight", 1, 0, 0)], [("orc", 1, 0, 0), ("orc", 1, 1, 1)])
        sim = BattleSimulation(a, b, self.db, seed=1)
        knight = a.formation.units[0]
        only(self.db, knight, "hit")
        back = b.formation.units[1]
        back.add_effect(self.db.effects["provoke"])
        events = turn_of(sim, knight.uid)
        self.assertTrue(any(isinstance(e, DamageDealt) and e.target == back.uid for e in events))


if __name__ == "__main__":
    unittest.main()
