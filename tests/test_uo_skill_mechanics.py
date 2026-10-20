"""Механики навыков UO, исправленные на шаге 5: подготовка, случайные цели, феи, день и ночь, снижение урона,
«следующая атака», воскрешение, смертельные удары. Навыки и эффекты берутся из data/."""
import unittest

from game.combat import Battle
from game.combat.record import ACTIVE, SKIP, Act
from game.database import Database
from game.editing import set_owners
from game.events import DamageDealt, EffectApplied, Healed, SkillUsed
from game.stats import Stat
from tests.helpers import plain_db, set_stats, squads
from tests.test_uo_passives import copy_effect, copy_skill, install, use

REAL = Database.load()


def world(*skill_ids, owner="mage", passive=None):
    db = plain_db()
    for unit_id in list(db.units):
        data = db.units[unit_id].to_dict()
        data["passives"] = []
        db.update("units", unit_id, data)
    for effect_id in ("uo_charging", "uo_faerie", "uo_burn", "uo_poison", "uo_stun", "uo_freeze", "uo_blind",
                      "uo_guard_seal", "uo_passive_seal", "uo_crit_seal", "uo_debuff_amp", "uo_reduce_50",
                      "uo_phys_atk_m50pct_mag_atk_m50pct", "uo_doomed", "uo_regen", "uo_next_sure"):
        copy_effect(db, effect_id)
    for skill_id in skill_ids:
        copy_skill(db, skill_id)
        set_owners(db, "units", skill_id, [owner])
    if passive:
        install(db, passive, owner)
    return db


def fight(db, left, right, seed=1, **kw):
    a, b = squads(db, left, right)
    return Battle(a, b, db, seed=seed, **kw), a.formation.units, b.formation.units


def cast(sim, db, user, skill_id, target):
    act = Act(ACTIVE, user.uid, skill_id, target=target.uid)
    sim._resolve(user, db.skills[skill_id], target, act, root=True)
    return act


def damages(act):
    return [e for e in act.events if isinstance(e, DamageDealt)]


class ChargeTests(unittest.TestCase):
    def setUp(self):
        self.db = world("gravity")
        use(self.db, "mage", "gravity")
        set_stats(self.db, "goblin", hp=400, phys_def=0, mag_def=0)
        self.sim, (self.mage,), (self.goblin,) = fight(self.db, [("mage", 1, 0, 0)], [("goblin", 1, 0, 0)])

    def test_charge_waits_for_the_end_of_the_round(self):
        kinds = []
        while not self.sim.finished and len(kinds) < 12:
            self.sim.step()
            kinds.append(self.sim.last_act.kind if self.sim.last_act else None)
            if any(isinstance(e, SkillUsed) and e.skill_id == "gravity" for e in self.sim.events):
                break
        self.assertIn(SKIP, kinds)                                # объявление подготовки — пропуск хода с причиной
        declared = next(a for a in self.sim.acts if a.kind == SKIP and a.reason == "charge")
        self.assertEqual(declared.actor, self.mage.uid)
        used = [e for e in self.sim.events if isinstance(e, SkillUsed) and e.skill_id == "gravity"]
        self.assertEqual(len(used), 1)
        self.assertEqual(self.sim.round, 1)                       # сработало в конце первого круга

    def test_charging_unit_cannot_dodge_or_use_passives(self):
        act = Act(ACTIVE, self.mage.uid, "gravity")
        self.sim._give(self.mage, "uo_charging", self.mage, act)
        self.assertTrue(self.mage.has_flag("charging"))
        self.assertTrue(self.mage.has_flag("passive_seal"))

    def test_gravity_deals_half_of_target_hp(self):
        hp = self.goblin.hp
        act = cast(self.sim, self.db, self.mage, "gravity", self.goblin)
        self.assertAlmostEqual(hp - self.goblin.hp, hp / 2, delta=max(2, hp * 0.05))
        self.assertTrue(damages(act))


class TargetsTests(unittest.TestCase):
    def test_dual_shot_hits_two_different_enemies(self):
        db = world("dual_shot", owner="archer")
        sim, (archer,), (a, b, c) = fight(db, [("archer", 1, 0, 0)],
                                         [("goblin", 1, 0, 0), ("orc", 1, 0, 1), ("rider", 1, 0, 2)])
        for seed in range(1, 6):
            sim, (archer,), enemies = fight(db, [("archer", 1, 0, 0)],
                                            [("goblin", 1, 0, 0), ("orc", 1, 0, 1), ("rider", 1, 0, 2)], seed=seed)
            act = cast(sim, db, archer, "dual_shot", enemies[0])
            targets = {e.target for e in damages(act)} | {s.target for s in act.strikes}
            self.assertEqual(len(targets), 2)

    def test_chaos_unending_gives_every_enemy_an_ailment(self):
        db = world("chaos_unending", owner="mage")
        sim, (mage,), enemies = fight(db, [("mage", 1, 0, 0)], [("goblin", 1, 0, 0), ("orc", 1, 0, 1)])
        cast(sim, db, mage, "chaos_unending", enemies[0])
        for enemy in enemies:
            self.assertTrue(any("ailment" in e.definition.tags for e in enemy.effects))


class FaerieTests(unittest.TestCase):
    def test_faeries_raise_potency_and_are_dismissed(self):
        db = world("faerie_heal", "elemental_roar")
        set_stats(db, "goblin", hp=900, phys_def=0, mag_def=0)
        sim, (mage, knight), (goblin,) = fight(db, [("mage", 1, 0, 0), ("knight", 1, 0, 1)], [("goblin", 1, 0, 0)])
        plain = sum(e.amount for e in damages(cast(sim, db, mage, "elemental_roar", goblin)))
        for _ in range(3):
            cast(sim, db, mage, "faerie_heal", knight)
        self.assertEqual(sum(e.stacks for e in mage.effects if e.definition.id == "uo_faerie"), 3)
        boosted = sum(e.amount for e in damages(cast(sim, db, mage, "elemental_roar", goblin)))
        self.assertGreater(boosted, plain)
        self.assertFalse(mage.has_effect("uo_faerie"))            # феи рассеяны


class DefenceTests(unittest.TestCase):
    def test_reduce_flag_halves_one_hit(self):
        db = world(owner="goblin")
        add = {"kind": "damage", "category": "magical", "power": 1.0, "scaling": [{"stat": "phys_atk", "coef": 1.0}]}
        db.update("skills", "zap", {"name": "zap", "ap_cost": 1, "tags": ["magic"], "parts": [add]})
        set_owners(db, "units", "zap", ["goblin"])
        set_stats(db, "goblin", phys_atk=40)
        set_stats(db, "knight", hp=500, mag_def=0)
        sim, (goblin,), (knight,) = fight(db, [("goblin", 1, 0, 0)], [("knight", 1, 0, 0)])
        full = damages(cast(sim, db, goblin, "zap", knight))[0].amount
        sim._give(knight, "uo_reduce_50", knight, Act(ACTIVE, 1, "x"))
        half = damages(cast(sim, db, goblin, "zap", knight))[0].amount
        again = damages(cast(sim, db, goblin, "zap", knight))[0].amount
        self.assertAlmostEqual(half / full, 0.5, delta=0.1)
        self.assertEqual(again, full)                              # заряд один

    def test_compounding_curse_amplifies_debuffs(self):
        db = world("compounding_curse", owner="mage")
        sim, (mage,), (goblin,) = fight(db, [("mage", 1, 0, 0)], [("goblin", 1, 0, 0)])
        sim._give(goblin, "uo_phys_atk_m50pct_mag_atk_m50pct", mage, Act(ACTIVE, 1, "x"))
        base = goblin.stat(Stat.PHYS_ATK)
        cast(sim, db, mage, "compounding_curse", goblin)
        self.assertLess(goblin.stat(Stat.PHYS_ATK), base)


class NextAttackTests(unittest.TestCase):
    @staticmethod
    def until_used(sim, unit):
        while not sim.finished and not any(isinstance(e, SkillUsed) and e.user == unit.uid for e in sim.events):
            sim.step()

    def test_binding_guard_seals_the_target_on_hit(self):
        db = world(owner="knight", passive="binding_guard")
        copy_effect(db, "uo_next_guard_seal")
        set_stats(db, "goblin", hp=900)
        sim, (knight,), (goblin,) = fight(db, [("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        self.until_used(sim, knight)
        self.assertTrue(any(isinstance(e, EffectApplied) and e.effect_id == "uo_guard_seal" and e.target == goblin.uid
                            for e in sim.events))

    def test_sanguine_arts_heals_by_damage_dealt(self):
        db = world(owner="knight", passive="sanguine_arts")
        copy_effect(db, "uo_next_vampire")
        set_stats(db, "goblin", hp=900, phys_def=0)
        sim, (knight,), (goblin,) = fight(db, [("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        knight.state.current_hp = knight.max_hp // 2
        self.until_used(sim, knight)
        healed = [e for e in sim.events if isinstance(e, Healed) and e.target == knight.uid]
        self.assertTrue(healed)

    def test_discharge_turns_buffs_into_power(self):
        db = world(owner="knight", passive="discharge")
        copy_effect(db, "uo_discharge")
        copy_effect(db, "uo_phys_atk_p30pct")
        sim, (knight,), (goblin,) = fight(db, [("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        for effect_id in ("uo_phys_atk_p30pct", "uo_regen"):
            copy_effect(db, effect_id)
            sim._give(knight, effect_id, knight, Act(ACTIVE, 1, "x"))
        from game.combat.engine import Moment
        sim._react(Moment("before_skill", subject=knight, actor=knight, target=goblin), Act(ACTIVE, 1, "x").before)
        stacks = next(e.stacks for e in knight.effects if e.definition.id == "uo_discharge")
        self.assertEqual(stacks, 2)                                # два бонуса сняты — два стака
        self.assertFalse(knight.has_effect("uo_regen"))


class ReviveTests(unittest.TestCase):
    def test_animated_dead_raises_with_full_hp_and_dooms_the_caster(self):
        db = world("animated_dead", owner="mage")
        sim, (mage, knight), (goblin,) = fight(db, [("mage", 1, 0, 0), ("knight", 1, 0, 1)], [("goblin", 1, 0, 0)])
        knight.state.current_hp = 0
        sim._dead.add(knight.uid)
        cast(sim, db, mage, "animated_dead", knight)
        self.assertEqual(knight.hp, knight.max_hp)
        self.assertTrue(mage.has_effect("uo_doomed"))

    def test_parting_resurrection_revives_a_fallen_ally_at_the_end(self):
        db = world(owner="mage", passive="parting_resurrection")
        set_stats(db, "goblin", hp=1, phys_def=0)
        sim, (mage, knight), (goblin,) = fight(db, [("mage", 1, 0, 0), ("knight", 1, 0, 1)], [("goblin", 1, 0, 0)])
        knight.state.current_hp = 0
        sim._dead.add(knight.uid)
        sim.run()
        self.assertTrue(knight.is_alive)


class RulesTests(unittest.TestCase):
    def test_desperate_attack_never_misses_and_always_crits_when_low(self):
        from game.combat import rules
        db = world("tempest_drive", owner="knight")
        sim, (knight,), (goblin,) = fight(db, [("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        skill = db.skills["tempest_drive"]
        attack = rules.Attack(knight, skill, frozenset(), [])
        self.assertFalse(rules.truestrike(attack))
        knight.state.current_hp = knight.max_hp // 4
        self.assertTrue(rules.truestrike(attack))
        self.assertEqual(rules.crit_chance(attack), 100.0)

    def test_hit_full_hp_gives_ap_only_against_a_healthy_target(self):
        db = world("aerial_smite", owner="knight")
        sim, (knight,), (goblin, orc) = fight(db, [("knight", 1, 0, 0)], [("goblin", 1, 0, 0), ("orc", 1, 0, 1)])
        orc.state.current_hp = 1
        knight.ap.spend(knight.ap.current)
        cast(sim, db, knight, "aerial_smite", goblin)
        self.assertGreaterEqual(knight.ap.current, 1)

    def test_day_extends_row_resistance_to_everyone(self):
        for time_of_day, expected in (("day", 3), ("night", 1)):
            db = world("row_resistance", owner="cleric")
            sim, (cleric, knight, mage), _ = fight(db, [("cleric", 1, 0, 0), ("knight", 1, 1, 0), ("mage", 1, 1, 1)],
                                                    [("goblin", 1, 0, 0)], time_of_day=time_of_day)
            cast(sim, db, cleric, "row_resistance", cleric)
            buffed = [u for u in (cleric, knight, mage) if any(e.definition.id == "uo_mag_def_p50pct" for e in u.effects)]
            self.assertEqual(len(buffed), expected, time_of_day)


if __name__ == "__main__":
    unittest.main()
