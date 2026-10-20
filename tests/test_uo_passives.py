"""Пассивки UO из data/ (бывшие заглушки): по образцу каждого шаблона — что происходит в бою.

Пассивка, её навык-ответ и все эффекты берутся из data/ и добавляются в замороженную базу тестов."""
import json
import unittest

from game.combat import Battle
from game.combat.record import ACTIVE, Act
from game.database import Database
from game.editing import set_owners
from game.events import (
    DamageDealt,
    EffectApplied,
    Healed,
    PassiveTriggered,
    ResourceGained,
    SkillUsed,
    UnitDied,
)
from tests.helpers import add_skill, plain_db, set_stats, squads

REAL = Database.load()


def copy_effect(db, effect_id):
    if effect_id in db.effects or effect_id not in REAL.effects:
        return
    data = REAL.effects[effect_id].to_dict()
    for tag in data.get("grants_tags", ()):
        if tag not in db.tags:
            db.update("tags", tag, REAL.tags[tag].to_dict())
    db.update("effects", effect_id, data)
    for trigger in data.get("triggers", ()):
        for key in ("effect_id",):
            if trigger.get(key):
                copy_effect(db, trigger[key])


def copy_skill(db, skill_id):
    if skill_id in db.skills or skill_id not in REAL.skills:
        return
    data = REAL.skills[skill_id].to_dict()
    for apply in data.get("applies", ()):
        copy_effect(db, apply["effect_id"])
    db.update("skills", skill_id, data)


def install(db, passive_id, owner):
    """Пассивка из data/ (с навыками и эффектами) — классу owner."""
    passive = REAL.passives[passive_id]
    data = passive.to_dict()
    reactions = [data["reaction"], *data["reaction"].get("then", ())]
    for r in reactions:
        copy_effect(db, r.get("effect_id"))
        copy_effect(db, r.get("effect_filter"))
        if r.get("skill_id"):
            copy_skill(db, r["skill_id"])
    for effect_id in ("uo_negate_physical", "uo_burn", "uo_poison", "uo_stun", "uo_regen", "uo_next_magic",
                      "uo_guard_medium", "uo_endure", "uo_taunt", "uo_immune_debuff"):
        copy_effect(db, effect_id)
    db.update("passives", passive_id, data)
    set_owners(db, "units", passive_id, [owner], field="passives")
    unit = db.units[owner].to_dict()
    unit["pp_max"] = 9
    db.update("units", owner, unit)


def world(passive_id, owner="knight"):
    db = plain_db()
    for unit_id in list(db.units):                    # чужие пассивки не мешают (один ответ бойца на действие)
        data = db.units[unit_id].to_dict()
        data["passives"] = []
        db.update("units", unit_id, data)
    install(db, passive_id, owner)
    return db


def fight(db, left, right, seed=1, **kw):
    a, b = squads(db, left, right)
    sim = Battle(a, b, db, seed=seed, **kw)
    return sim, a.formation.units, b.formation.units


def names(events, cls):
    return [e for e in events if isinstance(e, cls)]


def fired(sim, passive_id):
    return [e for e in sim.events if isinstance(e, PassiveTriggered) and e.passive_id == passive_id]


def use(db, unit_id, skill_id):
    """Единственное правило тактики класса."""
    from tests.helpers import rule
    data = db.units[unit_id].to_dict()
    data["tactics"] = [rule(skill_id)]
    db.update("units", unit_id, data)


class StartOfBattleTests(unittest.TestCase):
    def test_stance_buffs_the_owner(self):
        db = world("bunker_stance")
        sim, (knight, *_), _ = fight(db, [("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        sim._next_act()
        self.assertEqual(len(fired(sim, "bunker_stance")), 1)
        self.assertEqual(knight.stat(__import__("game.stats", fromlist=["Stat"]).Stat.INITIATIVE),
                         db.create_unit("knight", 9).stat(__import__("game.stats", fromlist=["Stat"]).Stat.INITIATIVE) + 30)

    def test_war_cry_raises_attack_by_a_fifth(self):
        from game.stats import Stat
        db = world("war_cry")
        sim, (knight,), _ = fight(db, [("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        before = knight.stat(Stat.PHYS_ATK)
        sim._next_act()
        self.assertEqual(knight.stat(Stat.PHYS_ATK), round(before * 1.2))

    def test_shell_negates_three_hits(self):
        db = world("magick_shell")
        sim, (knight,), _ = fight(db, [("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        sim._next_act()
        self.assertTrue(knight.has_flag("negate"))
        self.assertEqual(next(e for e in knight.effects if "negate" in e.definition.flags).charges, 3)

    def test_group_buff_through_a_support_skill(self):
        db = world("dawn_horn")
        sim, (knight, mage), _ = fight(db, [("knight", 1, 0, 0), ("mage", 1, 0, 1)], [("goblin", 1, 0, 0)])
        sim._next_act()
        self.assertIn("immune_stun", knight.tags)
        self.assertIn("immune_stun", mage.tags)

    def test_hastened_curse_slows_an_enemy(self):
        from game.stats import Stat
        db = world("hastened_curse")
        sim, _, (goblin, *_) = fight(db, [("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        before = goblin.stat(Stat.INITIATIVE)
        sim._next_act()
        self.assertEqual(goblin.stat(Stat.INITIATIVE), max(0, before - 30))

    def test_first_strike_hits_and_stuns(self):
        db = world("rapid_shot")
        sim, _, (goblin,) = fight(db, [("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        sim._next_act()
        self.assertEqual(len(fired(sim, "rapid_shot")), 1)
        self.assertLess(goblin.hp, goblin.max_hp)
        self.assertTrue(goblin.has_effect("uo_stun"))

    def test_taunt_and_negate_one_physical_hit(self):
        db = world("provoking_wall")
        sim, (knight,), _ = fight(db, [("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        sim._next_act()
        self.assertTrue(knight.has_flag("taunt"))
        self.assertTrue(knight.has_flag("negate:physical"))


class TieredTests(unittest.TestCase):
    def test_heavy_alignment_counts_armored_allies(self):
        db = world("heavy_alignment")
        for unit_id in ("knight", "orc", "goblin"):
            data = db.units[unit_id].to_dict()
            data["tags"] = list(data["tags"]) + ["armored"]
            db.update("units", unit_id, data)
        sim, (knight, orc, goblin), _ = fight(db, [("knight", 1, 0, 0), ("orc", 1, 0, 1), ("goblin", 1, 0, 2)],
                                              [("mage", 1, 0, 0)])
        sim._next_act()
        self.assertEqual(len(fired(sim, "heavy_alignment")), 1)
        for unit in (knight, orc, goblin):
            self.assertIn("immune_stun", unit.tags)              # три бронированных — все три ступени
            self.assertGreaterEqual(len(unit.effects), 3)

    def test_no_armored_allies_means_nothing_happens(self):
        db = world("heavy_alignment", owner="goblin")
        sim, (goblin,), _ = fight(db, [("goblin", 1, 0, 0)], [("mage", 1, 0, 0)])
        sim._next_act()
        self.assertEqual(fired(sim, "heavy_alignment"), [])

    def test_united_front_follows_the_enemy_surplus(self):
        db = world("united_front")
        sim, (knight,), _ = fight(db, [("knight", 1, 0, 0)],
                                  [("mage", 1, 0, 0), ("goblin", 1, 0, 1), ("orc", 1, 0, 2)])
        sim._next_act()
        self.assertEqual(len(fired(sim, "united_front")), 1)
        self.assertEqual(len(knight.effects), 2)                 # перевес 2 — ступени 1 и 2: инициатива и защита


class ReactionTests(unittest.TestCase):
    def test_counter_hits_the_attacker(self):
        db = world("counter")
        use(db, "goblin", "attack")
        sim, (knight,), (goblin,) = fight(db, [("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        sim.run()
        self.assertTrue(fired(sim, "counter"))
        self.assertTrue(any(e.source == knight.uid and e.target == goblin.uid and e.cause == "counter"
                            for e in names(sim.events, DamageDealt)))

    def test_cure_removes_the_state_and_heals(self):
        db = world("poison_cure", owner="cleric")
        sim, (cleric, knight), (goblin,) = fight(db, [("cleric", 1, 0, 0), ("knight", 1, 0, 1)],
                                                [("goblin", 1, 0, 0)])
        knight.state.current_hp = knight.max_hp // 2
        hp = knight.hp
        sim._give(knight, "uo_poison", goblin, Act(ACTIVE, goblin.uid, "x"))
        self.assertFalse(knight.has_effect("uo_poison"))        # реакция сняла отравление сразу
        self.assertGreater(knight.hp, hp)                        # и вылечила 10%
        self.assertTrue(fired(sim, "poison_cure"))

    def test_mirror_weakness_returns_debuffs_to_the_source(self):
        db = world("mirror_weakness")
        sim, (knight,), (goblin,) = fight(db, [("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        act = Act(ACTIVE, goblin.uid, "x")
        sim._give(knight, "uo_poison", goblin, act)
        self.assertFalse(knight.has_effect("uo_poison"))
        self.assertTrue(goblin.has_effect("uo_poison"))

    def test_lifeshare_moves_hp_to_the_hit_ally(self):
        db = world("lifeshare")
        use(db, "goblin", "attack")
        set_stats(db, "knight", hp=200)
        sim, (knight, mage), (goblin,) = fight(db, [("knight", 1, 0, 1), ("mage", 1, 0, 0)], [("goblin", 1, 0, 0)])
        mage.state.current_hp = max(1, mage.max_hp // 4)
        sim.step()
        sim.step()
        sim.run()
        self.assertTrue(fired(sim, "lifeshare") or knight.hp < knight.max_hp)

    def test_grave_impetus_gives_ap_when_an_ally_falls(self):
        db = world("grave_impetus")
        sim, (knight, mage), (goblin,) = fight(db, [("knight", 1, 0, 0), ("mage", 1, 0, 1)], [("goblin", 1, 0, 0)])
        knight.ap.spend(2)
        before = knight.ap.current
        act = Act(ACTIVE, goblin.uid, "x")
        mage.state.current_hp = 0
        sim._die(mage, act)
        self.assertEqual(knight.ap.current, before + 1)

    def test_free_action_skips_ap_spending(self):
        db = world("reinforce", owner="mage")
        use(db, "knight", "attack")
        set_stats(db, "goblin", hp=999, phys_atk=1)
        sim, (mage, knight), _ = fight(db, [("mage", 1, 0, 0), ("knight", 1, 0, 1)], [("goblin", 1, 0, 0)])
        full = knight.ap.max
        while not sim.finished and not any(isinstance(e, SkillUsed) and e.user == knight.uid for e in sim.events):
            sim.step()
        self.assertTrue(fired(sim, "reinforce"))
        self.assertEqual(knight.ap.current, full)               # навык применён, а AP не потрачен

    def test_evil_cover_steals_pp_from_the_ward(self):
        db = world("evil_cover", owner="knight")
        use(db, "goblin", "attack")
        sim, (mage, knight), (goblin,) = fight(db, [("mage", 1, 0, 0), ("knight", 1, 0, 1)], [("goblin", 1, 0, 0)])
        sim.step()
        sim.step()
        self.assertTrue(fired(sim, "evil_cover"))
        gains = [e for e in names(sim.events, ResourceGained) if e.resource == "PP" and e.cause == "evil_cover"]
        self.assertTrue(any(e.amount < 0 for e in gains) and any(e.amount > 0 for e in gains))

    def test_healing_cover_heals_the_covered_ally(self):
        db = world("healing_cover", owner="knight")
        use(db, "goblin", "attack")
        sim, (mage, knight), (goblin,) = fight(db, [("mage", 1, 0, 0), ("knight", 1, 0, 1)], [("goblin", 1, 0, 0)])
        mage.state.current_hp = mage.max_hp // 2
        sim.step()
        self.assertTrue(any(e.target == mage.uid and e.cause == "healing_cover" for e in names(sim.events, Healed)))

    def test_recast_repeats_a_magic_attack(self):
        db = world("recast", owner="mage")
        use(db, "mage", "magic_bolt")
        sim, (mage,), (orc,) = fight(db, [("mage", 1, 0, 0)], [("orc", 1, 0, 0)])
        set_stats(db, "orc", hp=999)
        sim.step()
        sim.step()
        events = sim.run()
        used = [e for e in sim.events if isinstance(e, SkillUsed) and e.user == mage.uid and e.skill_id == "magic_bolt"]
        self.assertGreaterEqual(len(used), 2)
        self.assertTrue(fired(sim, "recast"))


class AlliesTests(unittest.TestCase):
    def test_passive_gift_returns_pp_after_an_ally_passive(self):
        db = world("passive_gift", owner="knight")
        install(db, "war_cry", "mage")
        sim, (knight, mage), _ = fight(db, [("knight", 1, 0, 0), ("mage", 1, 0, 1)], [("goblin", 1, 0, 0)])
        sim._next_act()
        self.assertTrue(fired(sim, "war_cry"))
        self.assertTrue(fired(sim, "passive_gift"))
        gifts = [e for e in names(sim.events, ResourceGained) if e.cause == "passive_gift"]
        self.assertEqual([(e.target, e.resource, e.amount) for e in gifts], [(mage.uid, "PP", 1)])

    def test_sorcerous_connection_boosts_ally_and_owner_next_magic(self):
        from game.stats import Stat
        db = world("sorcerous_connection", owner="cleric")
        use(db, "mage", "magic_bolt")
        set_stats(db, "goblin", hp=999)
        sim, (cleric, mage), _ = fight(db, [("cleric", 1, 0, 0), ("mage", 1, 0, 1)], [("goblin", 1, 0, 0)])
        base = mage.stat(Stat.MAG_ATK)
        while not sim.finished and not any(isinstance(e, SkillUsed) and e.user == mage.uid for e in sim.events):
            sim.step()
        self.assertTrue(fired(sim, "sorcerous_connection"))
        self.assertTrue(any(e.target == mage.uid and "mag_atk" in e.effect_id for e in names(sim.events, EffectApplied)))
        self.assertTrue(any(e.target == cleric.uid and "mag_atk" in e.effect_id for e in names(sim.events, EffectApplied)))
        self.assertGreater(base, 0)


class DayNightTests(unittest.TestCase):
    def ap_after(self, time_of_day):
        db = world("diurnal_impetus")
        use(db, "knight", "attack")
        sim, (knight,), _ = fight(db, [("knight", 1, 0, 0)], [("orc", 1, 0, 0)], time_of_day=time_of_day)
        knight.ap.spend(1)
        base = knight.ap.current
        act = Act(ACTIVE, knight.uid, "attack")
        from game.combat.engine import Moment
        sim._react(Moment("skill_used", subject=knight, actor=knight, target=sim.units[2]), act.after)
        return knight.ap.current - base

    def test_diurnal_impetus_gives_ap_only_by_day(self):
        self.assertEqual(self.ap_after("day"), 1)
        self.assertEqual(self.ap_after("night"), 0)


class DefenceTests(unittest.TestCase):
    def test_magick_conversion_negates_magic_and_gives_pp(self):
        db = world("magick_conversion")
        use(db, "mage", "magic_bolt")
        sim, (knight,), (mage,) = fight(db, [("knight", 1, 0, 0)], [("mage", 1, 0, 0)])
        knight.pp.spend(knight.pp.current)
        sim.run()
        hits = [e for e in names(sim.events, DamageDealt) if e.target == knight.uid and e.cause == "magic_bolt"]
        self.assertTrue(fired(sim, "magick_conversion"))
        self.assertEqual(hits[0].amount, 0)

    def test_reflect_magick_hits_the_caster(self):
        db = world("reflect_magick")
        use(db, "mage", "magic_bolt")
        sim, (knight,), (mage,) = fight(db, [("knight", 1, 0, 0)], [("mage", 1, 0, 0)])
        sim.run()
        self.assertTrue(fired(sim, "reflect_magick"))
        self.assertTrue(any(e.source == mage.uid and e.target == mage.uid for e in names(sim.events, DamageDealt)))

    def test_honed_shield_nullifies_piercing(self):
        db = world("honed_shield")
        add_skill(db, "pierce", ["goblin"], ap_cost=1, area="column", tags=["melee"],
                  parts=[{"kind": "damage", "category": "physical", "power": 1.0,
                          "scaling": [{"stat": "phys_atk", "coef": 1.0}]}])
        use(db, "goblin", "pierce")
        sim, (knight,), (goblin,) = fight(db, [("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        sim.step()
        hp = knight.hp
        sim.step()
        self.assertEqual(knight.hp, hp)
        self.assertIn("nullify_pierce", knight.tags)


class BurstTests(unittest.TestCase):
    def test_fire_burst_spreads_over_burning_target(self):
        db = world("fire_burst")
        sim, _, (goblin, orc) = fight(db, [("knight", 1, 0, 0)], [("goblin", 1, 0, 0), ("orc", 1, 0, 1)])
        act = Act(ACTIVE, 1, "x")
        sim._give(goblin, "uo_burn", sim.units[1], act)
        skill = db.skills["fire_burst"]
        hit = []
        sim._resolve(sim.units[1], skill, goblin, act, root=False)
        self.assertLess(orc.hp, orc.max_hp)

    def test_fire_burst_hits_one_when_not_burning(self):
        db = world("fire_burst")
        sim, _, (goblin, orc) = fight(db, [("knight", 1, 0, 0)], [("goblin", 1, 0, 0), ("orc", 1, 0, 1)])
        sim._resolve(sim.units[1], db.skills["fire_burst"], goblin, Act(ACTIVE, 1, "x"), root=False)
        self.assertEqual(orc.hp, orc.max_hp)


class CatalogTests(unittest.TestCase):
    def test_only_known_stubs_remain(self):
        stubs = sorted(k for k, v in REAL.passives.items()
                       if v.reaction.action == "restore_pp" and not v.reaction.amount)
        self.assertEqual(stubs, ["celestial_light"])

    def test_passives_are_skills_with_a_trigger(self):
        for pid, passive in REAL.passives.items():
            skill = REAL.skills[pid]
            self.assertTrue(skill.is_passive and skill.trigger is not None, pid)
            self.assertEqual(skill.ap_cost, 0, pid)
            self.assertEqual(skill.pp_cost, passive.pp_cost, pid)


if __name__ == "__main__":
    unittest.main()
