"""Тесты боевых формул: урон, скейлы, попадание, крит, блок, теги и модификаторы атак."""
import unittest

from game.battle import GUARD_REDUCTION, BattleSimulation
from game.events import AttackMissed, DamageDealt, EffectApplied, EffectExpired, Healed, SkillUsed, TurnSkipped
from game.stats import Stat
from game.tags import TagRule, rule_multipliers
from tests.helpers import DB, add_skill, duel, only, plain_db, set_stats, squads, turn_of

OUTCOMES = (DamageDealt, Healed, AttackMissed)


def part(category="physical", power=1.0, tags=(), weapon=False, scaling=None, kind="damage"):
    data = {"kind": kind, "category": category, "power": power, "tags": list(tags), "weapon_tags": weapon}
    if scaling:
        data["scaling"] = [{"stat": stat, "coef": coef} for stat, coef in scaling]
    return data


def equip(db, unit, item_id):
    unit.equip(unit.definition.slots.index(db.items[item_id].slot), item_id)


def strike(db, attacker, target, skill, seed=1, gear=(), target_gear=()):
    """Первый ход attacker (uid 1) единственным навыком skill по target (uid 2)."""
    sim, a, b = duel(db, attacker, target, seed)
    for item_id in gear:
        equip(db, a, item_id)
    for item_id in target_gear:
        equip(db, b, item_id)
    only(db, a, skill)
    events = turn_of(sim, 1)
    return [e for e in events if isinstance(e, OUTCOMES)], events, sim


def amounts(outcomes):
    return [e.amount for e in outcomes if isinstance(e, DamageDealt)]


class DamageFormulaTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def test_physical_is_attack_minus_defense_times_power(self):
        # рыцарь: phys_atk 22; орк: phys_def 8
        self.assertEqual(amounts(strike(self.db, "knight", "orc", "attack")[0]), [14])
        self.assertEqual(amounts(strike(self.db, "knight", "orc", "power_strike")[0]), [21])

    def test_magical_uses_magic_stats(self):
        # маг: mag_atk 24; орк: mag_def 3
        self.assertEqual(amounts(strike(self.db, "mage", "orc", "magic_bolt")[0]), [21])
        self.assertEqual(amounts(strike(self.db, "mage", "orc", "fireball")[0]), [32])  # 21 * 1.5 = 31.5

    def test_pure_ignores_defense(self):
        add_skill(self.db, "smite", ["knight"], parts=[part("pure")])
        self.assertEqual(amounts(strike(self.db, "knight", "orc", "smite")[0]), [22])

    def test_minimum_damage_is_one(self):
        sim, weak, tank = duel(self.db, "knight", "knight", right_level=9)
        self.assertGreater(tank.stat(Stat.PHYS_DEF), weak.stat(Stat.PHYS_ATK))
        only(self.db, weak, "attack")
        self.assertEqual(amounts(e for e in turn_of(sim, 1) if isinstance(e, DamageDealt)), [1])

    def test_scaling_from_several_stats(self):
        # (100% phys_atk 22 + 20% max HP 60 - phys_def 8) * 1.5
        add_skill(self.db, "body_slam", ["knight"],
                  parts=[part(power=1.5, scaling=[("phys_atk", 1.0), ("hp", 0.2)])])
        self.assertEqual(amounts(strike(self.db, "knight", "orc", "body_slam")[0]), [39])
        # скейл от защиты: 200% phys_def 14 (12 и +20% от пассивки iron_will) - 8
        add_skill(self.db, "shield_slam", ["knight"], parts=[part(scaling=[("phys_def", 2.0)])])
        self.assertEqual(amounts(strike(self.db, "knight", "orc", "shield_slam")[0]), [20])

    def test_mixed_skill_deals_each_part_separately(self):
        add_skill(self.db, "spellblade", ["knight"], parts=[part(), part("magical")])
        # физика 22 - 8, магия mag_atk 4 - mag_def 3
        self.assertEqual(amounts(strike(self.db, "knight", "orc", "spellblade")[0]), [14, 1])

    def test_heal_scales_from_any_stat(self):
        add_skill(self.db, "bandage", ["knight"], targets="self",
                  parts=[part(kind="heal", scaling=[("phys_atk", 0.5), ("hp", 0.1)])])
        sim, knight, _ = duel(self.db, "knight", "goblin")
        knight.take_damage(40)
        only(self.db, knight, "bandage")
        healed = [e for e in turn_of(sim, 1) if isinstance(e, Healed)]
        self.assertEqual([e.amount for e in healed], [17])  # 22 * 0.5 + 60 * 0.1


class AccuracyTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def test_zero_accuracy_always_misses_and_applies_nothing(self):
        add_skill(self.db, "wild_swing", ["knight"], accuracy=0, parts=[part()],
                  applies=[{"effect_id": "poison", "to": "target"}, {"effect_id": "war_cry", "to": "self"}])
        for seed in range(10):
            outcomes, events, _ = strike(self.db, "knight", "orc", "wild_swing", seed)
            self.assertEqual(outcomes, [AttackMissed(1, 2, "wild_swing")])
            self.assertFalse(any(isinstance(e, EffectApplied) for e in events))

    def test_evasion_is_subtracted_and_high_accuracy_beats_it(self):
        set_stats(self.db, "orc", evasion=100)
        add_skill(self.db, "sure_shot", ["knight"], accuracy=200, parts=[part()])
        for seed in range(10):
            self.assertIsInstance(strike(self.db, "knight", "orc", "attack", seed)[0][0], AttackMissed)
            self.assertEqual(amounts(strike(self.db, "knight", "orc", "sure_shot", seed)[0]), [14])

    def test_accuracy_stat_multiplies_skill_accuracy(self):
        set_stats(self.db, "knight", accuracy=50)
        hits = sum(not isinstance(strike(self.db, "knight", "orc", "attack", seed)[0][0], AttackMissed)
                   for seed in range(200))
        self.assertTrue(60 <= hits <= 140, hits)  # около половины

    def test_heal_ignores_evasion_but_can_miss(self):
        set_stats(self.db, "knight", evasion=100)
        add_skill(self.db, "shaky_heal", ["cleric"], targets="ally", accuracy=0, parts=[part("magical", kind="heal")])
        for skill, expected in (("heal", Healed), ("shaky_heal", AttackMissed)):
            a, b = squads(self.db, [("knight", 1, 0, 0), ("cleric", 1, 1, 0)], [("goblin", 1, 0, 0)])
            knight, cleric = a.formation.units
            knight.take_damage(40)
            only(self.db, cleric, skill)
            outcomes = [e for e in turn_of(BattleSimulation(a, b, self.db, seed=1), cleric.uid)
                        if isinstance(e, OUTCOMES)]
            self.assertEqual([type(e) for e in outcomes], [expected], skill)


class CritAndGuardTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def test_crit_multiplies_by_crit_damage(self):
        set_stats(self.db, "knight", crit_rate=100)
        outcomes = strike(self.db, "knight", "orc", "attack")[0]
        self.assertEqual([(e.amount, e.crit) for e in outcomes], [(21, True)])  # 14 * 1.5
        set_stats(self.db, "knight", crit_damage=200)
        self.assertEqual(amounts(strike(self.db, "knight", "orc", "attack")[0]), [28])

    def test_heal_can_crit(self):
        set_stats(self.db, "cleric", crit_rate=100)
        a, b = squads(self.db, [("knight", 1, 0, 0), ("cleric", 1, 1, 0)], [("goblin", 1, 0, 0)])
        knight, cleric = a.formation.units
        knight.take_damage(50)
        only(self.db, cleric, "heal")
        healed = [e for e in turn_of(BattleSimulation(a, b, self.db, seed=1), cleric.uid) if isinstance(e, Healed)]
        self.assertEqual([(e.amount, e.crit) for e in healed], [(29, True)])  # 16 * 1.2 * 1.5 = 28.8

    def test_guard_halves_physical_damage(self):
        set_stats(self.db, "orc", guard_rate=100)
        outcomes = strike(self.db, "knight", "orc", "attack", gear=["iron_sword"])[0]
        self.assertEqual(GUARD_REDUCTION, 0.5)
        self.assertEqual([(e.amount, e.guarded) for e in outcomes], [(10, True)])  # (27 - 8) * 0.5 = 9.5

    def test_blunt_cannot_be_guarded(self):
        set_stats(self.db, "orc", guard_rate=100)
        self.assertTrue(self.db.tags["blunt"].unblockable)
        outcomes = strike(self.db, "knight", "orc", "attack")[0]  # без оружия атака дробящая
        self.assertEqual([(e.amount, e.guarded) for e in outcomes], [(14, False)])

    def test_magic_and_pure_cannot_be_guarded(self):
        set_stats(self.db, "orc", guard_rate=100)
        add_skill(self.db, "smite", ["knight"], parts=[part("pure")])
        self.assertEqual([(e.amount, e.guarded) for e in strike(self.db, "mage", "orc", "magic_bolt")[0]], [(21, False)])
        self.assertEqual([(e.amount, e.guarded) for e in strike(self.db, "knight", "orc", "smite")[0]], [(22, False)])

    def test_guard_cuts_only_the_physical_part_of_a_mixed_skill(self):
        set_stats(self.db, "orc", guard_rate=100)
        add_skill(self.db, "spellblade", ["knight"], parts=[part(tags=["slashing"]), part("magical", power=5)])
        outcomes = strike(self.db, "knight", "orc", "spellblade")[0]
        self.assertEqual([(e.amount, e.guarded) for e in outcomes], [(7, True), (5, False)])

    def test_mixed_blunt_and_slashing_is_unblockable(self):
        set_stats(self.db, "orc", guard_rate=100)
        add_skill(self.db, "mace_sword", ["knight"], parts=[part(tags=["slashing"]), part(tags=["blunt"])])
        outcomes = strike(self.db, "knight", "orc", "mace_sword")[0]
        self.assertEqual([(e.amount, e.guarded) for e in outcomes], [(14, False), (14, False)])


class MultiHitTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def test_each_hit_deals_damage_and_effects_apply_once(self):
        add_skill(self.db, "triple", ["knight"], hits=3, parts=[part(power=0.5)],
                  applies=[{"effect_id": "poison", "to": "target"}])
        outcomes, events, _ = strike(self.db, "knight", "orc", "triple")
        self.assertEqual(amounts(outcomes), [7, 7, 7])
        self.assertEqual(sum(isinstance(e, SkillUsed) for e in events), 1)
        self.assertEqual(sum(isinstance(e, EffectApplied) for e in events), 1)

    def test_hit_and_crit_are_rolled_per_hit(self):
        set_stats(self.db, "knight", crit_rate=50, accuracy=50)
        add_skill(self.db, "barrage", ["knight"], hits=4, parts=[part(power=0.5)])
        patterns = set()
        for seed in range(40):
            outcomes = strike(self.db, "knight", "orc", "barrage", seed)[0]
            self.assertEqual(len(outcomes), 4)
            patterns.add(tuple("miss" if isinstance(e, AttackMissed) else "crit" if e.crit else "hit" for e in outcomes))
        self.assertTrue(any(len(set(p)) > 1 for p in patterns))  # внутри одного применения исходы разные
        self.assertGreater(len(patterns), 10)

    def test_demo_flurry_hits_twice(self):
        self.assertEqual(self.db.skills["flurry"].hits, 2)
        self.assertEqual(amounts(strike(self.db, "goblin", "orc", "flurry")[0]), [5, 5])  # (16 - 8) * 0.6 = 4.8


class TagRuleTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def test_rule_matching(self):
        rules = [TagRule(attack=("melee",), attack_not=("flying",), target=("flying",), hit=0.5),
                 TagRule(attack=("cavalry",), target=("infantry",), damage=1.5),
                 TagRule(attack=("fire",), target=("infantry",), damage=2.0)]
        self.assertEqual(rule_multipliers(rules, {"melee", "cavalry"}, {"infantry"}), (1.5, 1.0))
        self.assertEqual(rule_multipliers(rules, {"melee"}, {"flying"}), (1.0, 0.5))
        self.assertEqual(rule_multipliers(rules, {"melee", "flying"}, {"flying"}), (1.0, 1.0))
        self.assertEqual(rule_multipliers(rules, {"cavalry", "fire"}, {"infantry"}), (3.0, 1.0))  # перемножаются

    def test_cavalry_deals_more_to_infantry(self):
        # всадник: phys_atk 21; гоблин (пехота): phys_def 3; всадник (конница): phys_def 8
        self.assertEqual(amounts(strike(self.db, "rider", "goblin", "attack")[0]), [27])  # 18 * 1.5
        self.assertEqual(amounts(strike(self.db, "rider", "rider", "attack")[0]), [13])

    def test_skill_bonus_against_tag(self):
        self.assertEqual(dict(self.db.skills["lance_charge"].bonus_vs), {"cavalry": 1.5})
        self.assertEqual(amounts(strike(self.db, "rider", "rider", "lance_charge")[0]), [25])  # 13 * 1.3 * 1.5
        self.assertEqual(amounts(strike(self.db, "rider", "orc", "lance_charge")[0]), [25])    # 13 * 1.3 * 1.5 (пехота)

    def test_resistance_is_a_tag_given_by_an_item(self):
        # маг: mag_atk 24; рыцарь: mag_def 5, амулет даёт +2 и тег fire_resistant
        self.assertEqual(amounts(strike(self.db, "mage", "knight", "fireball")[0]), [28])  # 19 * 1.5 = 28.5
        outcomes, _, sim = strike(self.db, "mage", "knight", "fireball", target_gear=["fire_charm"])
        self.assertIn("fire_resistant", sim.units[2].tags)
        self.assertEqual(amounts(outcomes), [13])  # 17 * 1.5 * 0.5 = 12.75
        self.assertEqual(amounts(strike(self.db, "mage", "knight", "magic_bolt", target_gear=["fire_charm"])[0]), [17])

    def test_melee_from_the_ground_is_less_accurate_against_flying(self):
        data = self.db.units["goblin"].to_dict()
        self.db.update("units", "bat", dict(data, name="Bat", tags=["flying"]))
        rules = [r.to_dict() for r in self.db.rules]
        self.assertIn({"attack": ["melee"], "attack_not": ["flying"], "target": ["flying"], "damage": 1.0, "hit": 0.5}, rules)
        hits = sum(not isinstance(strike(self.db, "knight", "bat", "attack", seed)[0][0], AttackMissed)
                   for seed in range(200))
        self.assertTrue(60 <= hits <= 140, hits)
        for seed in range(20):  # летающий по летающему и стрелок по летающему бьют без штрафа
            self.assertIsInstance(strike(self.db, "bat", "bat", "attack", seed)[0][0], DamageDealt)
            self.assertEqual(amounts(strike(self.db, "archer", "bat", "shot", seed)[0]), [26])  # 17 * 1.5 = 25.5

    def test_weapon_sets_the_damage_type(self):
        self.db.set_rules([{"attack": ["slashing"], "target": ["infantry"], "damage": 2.0}])
        self.assertEqual(amounts(strike(self.db, "knight", "orc", "attack")[0]), [14])                       # дробящий
        self.assertEqual(amounts(strike(self.db, "knight", "orc", "attack", gear=["iron_sword"])[0]), [38])  # режущий
        # stun_bash всегда дробящий: оружие его тип не меняет
        add_skill(self.db, "bash", ["knight"], parts=[part(tags=["blunt"])])
        self.assertEqual(amounts(strike(self.db, "knight", "orc", "bash", gear=["iron_sword"])[0]), [19])

    def test_category_can_be_used_in_rules(self):
        self.db.set_rules([{"attack": ["magical"], "target": ["armored"], "damage": 2.0}])
        self.assertEqual(amounts(strike(self.db, "mage", "knight", "magic_bolt")[0]), [38])
        self.assertEqual(amounts(strike(self.db, "mage", "orc", "magic_bolt")[0]), [21])


class AttackModTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def enchanted_strikes(self, effect_id, count):
        sim, knight, orc = duel(self.db, "knight", "orc", right_level=5)
        knight.add_effect(self.db.effects[effect_id])
        only(self.db, knight, "attack")
        events = sim.run()
        hits = [e.amount for e in events if isinstance(e, DamageDealt) and e.source == 1]
        return hits[:count], events, knight

    def test_effect_adds_damage_tag_and_power(self):
        self.db.set_rules([{"attack": ["slashing"], "target": ["infantry"], "damage": 2.0}])
        plain = amounts(strike(self.db, "knight", "orc", "attack")[0])
        self.assertEqual(plain, [14])
        # wind_blade: атаки получают тег «режущий» и x1.2 -> 14 * 1.2 * 2 = 33.6
        outcomes_sim, knight, orc = duel(self.db, "knight", "orc")
        knight.add_effect(self.db.effects["wind_blade"])
        only(self.db, knight, "attack")
        self.assertEqual(amounts(e for e in turn_of(outcomes_sim, 1) if isinstance(e, DamageDealt)), [34])

    def test_effect_adds_scaling_accuracy_and_crit(self):
        self.db.update("effects", "focus", {"name": "Focus", "attack_mods": [
            {"add_scaling": [{"stat": "mag_atk", "coef": 2.0}], "accuracy_add": 100, "crit_add": 100}]})
        set_stats(self.db, "orc", evasion=100)
        sim, knight, orc = duel(self.db, "knight", "orc")
        knight.add_effect(self.db.effects["focus"])
        only(self.db, knight, "attack")
        outcomes = [e for e in turn_of(sim, 1) if isinstance(e, OUTCOMES)]
        self.assertEqual([(e.amount, e.crit) for e in outcomes], [(33, True)])  # (22 + 4 * 2 - 8) * 1.5

    def test_charges_are_spent_per_skill_use(self):
        self.db.update("effects", "oil", {"name": "Oil", "charges": 2, "attack_mods": [{"power_mult": 2.0}]})
        hits, events, knight = self.enchanted_strikes("oil", 4)
        # рыцарь 1 ур.: 22 - (8 + 4 * 1) = 10 по орку 5 уровня
        self.assertEqual(hits, [20, 20, 10, 10])
        self.assertEqual(sum(e == EffectExpired(1, "oil") for e in events), 1)
        self.assertFalse(knight.has_effect("oil"))

    def test_skill_tag_filter(self):
        self.db.update("effects", "sharp_eye", {"name": "Sharp Eye", "attack_mods": [
            {"power_mult": 2.0, "skill_tag": "ranged"}]})
        hits, _, _ = self.enchanted_strikes("sharp_eye", 1)
        self.assertEqual(hits, [10])  # attack ближний, модификатор не действует

    def test_effect_can_grant_a_unit_tag(self):
        self.db.update("effects", "mounted", {"name": "Mounted", "grants_tags": ["cavalry"]})
        sim, knight, goblin = duel(self.db, "knight", "goblin")
        knight.add_effect(self.db.effects["mounted"])
        self.assertIn("cavalry", knight.tags)
        only(self.db, knight, "attack")
        self.assertEqual(amounts(e for e in turn_of(sim, 1) if isinstance(e, DamageDealt)), [28])  # 19 * 1.5 -> HP 28


class SkillRequirementTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def test_requires_target(self):
        add_skill(self.db, "execute", ["knight"], parts=[part(power=2)],
                  requires_target={"type": "has_effect", "effect_id": "poison"})
        for poisoned, expected in ((False, "attack"), (True, "execute")):  # без яда: запасная атака
            sim, knight, orc = duel(self.db, "knight", "orc")
            only(self.db, knight, "execute")
            if poisoned:
                orc.add_effect(self.db.effects["poison"])
            self.assertIn(SkillUsed(1, expected, 2), turn_of(sim, 1))

    def test_requires_self(self):
        add_skill(self.db, "rage", [], parts=[part(power=2)],
                  requires_self={"type": "hp_below", "value": 0.5})
        data = self.db.units["knight"].to_dict()
        self.db.update("units", "berserk", dict(data, skills=["rage"], tactics=[]))
        for wounded, expected in ((False, TurnSkipped(1, "no_action")), (True, SkillUsed(1, "rage", 2))):
            sim, berserk, orc = duel(self.db, "berserk", "orc")
            only(self.db, berserk, "rage")
            if wounded:
                berserk.take_damage(berserk.hp - 10)
            self.assertIn(expected, turn_of(sim, 1))


class PpCostTests(unittest.TestCase):
    """Навык может стоить PP вместо AP или вместе с ним."""

    def setUp(self):
        self.db = plain_db()

    def test_skill_spends_pp_and_ap(self):
        add_skill(self.db, "guard_break", ["knight"], ap_cost=1, pp_cost=1, parts=[part(power=2)])
        sim, knight, tank = duel(self.db, "knight", "knight", right_level=5)  # противник без оглушения
        only(self.db, knight, "guard_break")
        events = turn_of(sim, 1)
        self.assertIn(SkillUsed(1, "guard_break", 2), events)
        self.assertEqual((knight.ap.current, knight.pp.current), (3, 0))
        # PP кончились: навык больше недоступен, срабатывает запасная атака за AP.
        self.assertIn(SkillUsed(1, "attack", 2), turn_of(sim, 1))
        self.assertEqual((knight.ap.current, knight.pp.current), (2, 0))

    def test_pp_only_skill_and_exhaustion(self):
        # У юнита единственный навык за 1 PP и ни одного за AP: бой кончается, когда PP потрачены.
        add_skill(self.db, "spark", [], ap_cost=0, pp_cost=1, parts=[part("magical")])
        data = self.db.units["mage"].to_dict()
        self.db.update("units", "sparker", dict(data, skills=["spark"], pp_max=2, tactics=[
            {"skill": "spark", "condition": {"type": "always"}, "selector": "frontmost"}]))
        sim, a, b = duel(self.db, "sparker", "sparker")
        events = sim.run()
        used = [e for e in events if isinstance(e, SkillUsed)]
        self.assertEqual(len(used), 4)                         # по 2 PP у каждого
        self.assertEqual((a.pp.current, b.pp.current, a.ap.current), (0, 0, a.ap.max))
        self.assertEqual(events[-1].reason, "exhausted")

    def test_pp_cost_roundtrip_and_description(self):
        add_skill(self.db, "spark", [], ap_cost=0, pp_cost=2, parts=[part("magical")])
        skill = self.db.skills["spark"]
        self.assertEqual(skill.to_dict()["pp_cost"], 2)
        self.assertEqual(self.db.copy().skills["spark"], skill)
        from game.editing import describe_skill
        self.assertTrue(describe_skill(skill, self.db).startswith("AP 0 PP 2 ->"))
        self.assertEqual(self.db.skills["attack"].pp_cost, 0)  # в старых данных поля нет: цена 0


class DataSanityTests(unittest.TestCase):
    def test_real_data_directory_loads(self):
        """Папка data/ с правками песочницы должна загружаться и проходить проверку ссылок."""
        from game.database import Database
        live = Database.load()
        self.assertTrue(live.units and live.skills)

    def test_every_class_attack_has_a_damage_type(self):
        for definition in DB.units.values():
            self.assertTrue(definition.tags, definition.id)
        for skill in DB.skills.values():
            for skill_part in skill.parts:
                if skill_part.kind == "damage" and skill_part.category == "physical":
                    self.assertTrue(skill_part.tags, skill.id)


if __name__ == "__main__":
    unittest.main()
