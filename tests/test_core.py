"""Тесты ядра и симуляции боя. Запуск: python -m unittest discover -s tests -t ."""
import dataclasses
import json
import random
import unittest

from game.battle import BattleSimulation
from game.database import Database
from game.effects import ActiveEffect, EffectDefinition, StackRule, apply_effect, tick_effects
from game.events import (
    END_DEFEAT,
    END_EXHAUSTED,
    END_ROUND_LIMIT,
    SKIP_NO_ACTION,
    BattleEnded,
    BattleStarted,
    EffectExpired,
    PassiveTriggered,
    SkillUsed,
    TurnSkipped,
    TurnStarted,
    UnitDied,
    format_event,
)
from game.resource import Resource
from game.scenario import build_demo
from game.squad import Formation, FormationError, Squad
from game.stats import Modifier, ModOp, Stat, compute_stat
from game.tactics import CONDITIONS, SELECTORS, TacticsSet
from game.unit import UnitState
from game.world import Army, WorldMap

DB = Database.load()
ALL_STATS = list(Stat)


def make_squad(squad_id, roster, first_uid=1):
    """roster: список (definition_id, level, row, col)."""
    squad = Squad(squad_id, squad_id)
    for i, (definition_id, level, row, col) in enumerate(roster):
        squad.formation.place(DB.create_unit(definition_id, first_uid + i, level), row, col)
    return squad


def demo_sim(seed, **kwargs):
    scenario = build_demo(DB)
    return BattleSimulation(scenario.player_squad, scenario.enemy_squad, DB, seed=seed, **kwargs)


class StatsTests(unittest.TestCase):
    def test_modifier_order(self):
        mods = [
            Modifier(Stat.ATK, ModOp.PERCENT_MULT, 2.0),
            Modifier(Stat.ATK, ModOp.PERCENT_ADD, 0.5),
            Modifier(Stat.ATK, ModOp.FLAT, 5),
            Modifier(Stat.ATK, ModOp.PERCENT_ADD, 0.5),
            Modifier(Stat.ATK, ModOp.PERCENT_MULT, 1.5),
        ]
        # (10 + 5) * (1 + 0.5 + 0.5) * (2.0 * 1.5)
        self.assertEqual(compute_stat(10, mods), 90)
        self.assertEqual(compute_stat(10, reversed(mods)), 90)

    def test_rounding_and_floor(self):
        self.assertEqual(compute_stat(10, [Modifier(Stat.DEF, ModOp.PERCENT_ADD, 0.26)]), 13)
        self.assertEqual(compute_stat(3, [Modifier(Stat.SPD, ModOp.FLAT, -10)]), 0)

    def test_stats_return_after_effect_removed(self):
        unit = DB.create_unit("knight", 1)
        before = {s: unit.stat(s) for s in ALL_STATS}
        unit.add_effect(DB.effects["war_cry"])
        unit.add_effect(DB.effects["iron_will"])
        self.assertEqual(unit.stat(Stat.ATK), round(before[Stat.ATK] * 1.3))
        self.assertEqual(unit.stat(Stat.DEF), round(before[Stat.DEF] * 1.2))
        unit.dispel("buff")
        unit.dispel("passive")
        self.assertEqual(unit.effects, [])
        self.assertEqual({s: unit.stat(s) for s in ALL_STATS}, before)

    def test_equipment_and_level_growth(self):
        base = DB.create_unit("knight", 1)
        self.assertEqual((base.stat(Stat.HP), base.stat(Stat.ATK), base.stat(Stat.DEF), base.stat(Stat.SPD)), (60, 14, 10, 5))
        leveled = DB.create_unit("knight", 2, level=3)
        self.assertEqual((leveled.stat(Stat.HP), leveled.stat(Stat.ATK), leveled.stat(Stat.DEF)), (76, 18, 14))
        geared = DB.create_unit("knight", 3, level=3, equipment=["iron_sword", "shield"])
        self.assertEqual((geared.stat(Stat.ATK), geared.stat(Stat.DEF), geared.stat(Stat.SPD)), (23, 18, 4))
        self.assertEqual(geared.hp, geared.max_hp)
        self.assertEqual(geared.unequip(0), "iron_sword")
        self.assertEqual(geared.stat(Stat.ATK), 18)

    def test_definitions_are_frozen(self):
        for definition in (DB.units["knight"], DB.effects["poison"], DB.skills["attack"],
                           DB.passives["avenger"], DB.items["shield"]):
            with self.assertRaises(dataclasses.FrozenInstanceError):
                definition.name = "x"
        with self.assertRaises(TypeError):
            DB.units["knight"].base_stats[Stat.ATK] = 99


class ResourceTests(unittest.TestCase):
    def test_spend_and_gain(self):
        ap = Resource(4, 1)
        self.assertTrue(ap.can_spend(1))
        self.assertFalse(ap.can_spend(2))
        with self.assertRaises(ValueError):
            ap.spend(2)
        ap.gain(10)
        self.assertEqual(ap.current, 4)
        ap.spend(3)
        self.assertEqual(ap.current, 1)

    def test_unit_resources(self):
        unit = DB.create_unit("knight", 1)
        self.assertEqual(unit.ap.current, unit.definition.ap_max)  # полный запас, сам не растёт
        self.assertEqual(unit.pp.current, unit.definition.pp_max)
        self.assertIs(type(unit.ap), type(unit.pp))


class EffectTests(unittest.TestCase):
    def definition(self, rule, max_stacks=1):
        return EffectDefinition(
            id="e", name="E", duration=3, stack_rule=rule, max_stacks=max_stacks,
            modifiers=(Modifier(Stat.ATK, ModOp.FLAT, 2),),
        )

    def test_refresh(self):
        effects = []
        definition = self.definition(StackRule.REFRESH)
        first = apply_effect(effects, definition, source=1)
        tick_effects(effects)
        again = apply_effect(effects, definition, source=2)
        self.assertIs(again, first)
        self.assertEqual((len(effects), first.remaining, first.stacks, first.source), (1, 3, 1, 1))

    def test_stack(self):
        effects = []
        definition = self.definition(StackRule.STACK, max_stacks=3)
        for _ in range(5):
            effect = apply_effect(effects, definition)
        self.assertEqual((len(effects), effect.stacks), (1, 3))
        tick_effects(effects)
        apply_effect(effects, definition)
        self.assertEqual(effect.remaining, 3)
        self.assertEqual(sum(m.value for m in effect.modifiers()), 6)

    def test_ignore(self):
        effects = []
        definition = self.definition(StackRule.IGNORE)
        first = apply_effect(effects, definition, source=1)
        tick_effects(effects)
        self.assertIsNone(apply_effect(effects, definition, source=2))
        self.assertEqual((len(effects), first.remaining, first.source), (1, 2, 1))

    def test_replace(self):
        effects = []
        definition = self.definition(StackRule.REPLACE)
        first = apply_effect(effects, definition, source=1)
        tick_effects(effects)
        second = apply_effect(effects, definition, source=2)
        self.assertIsNot(second, first)
        self.assertEqual(effects, [second])
        self.assertEqual((second.remaining, second.source), (3, 2))

    def test_poison_stacks_on_unit(self):
        unit = DB.create_unit("orc", 1)
        for _ in range(5):
            unit.add_effect(DB.effects["poison"])
        self.assertEqual(unit.effects[0].stacks, 3)

    def test_tick_removes_expired_keeps_permanent(self):
        unit = DB.create_unit("knight", 1)
        unit.add_effect(DB.effects["stun"])       # 1 ход
        unit.add_effect(DB.effects["war_cry"])    # 3 хода
        unit.add_effect(DB.effects["iron_will"])  # постоянный
        self.assertTrue(unit.has_flag("stunned"))
        expired = unit.tick()
        self.assertEqual([e.definition.id for e in expired], ["stun"])
        self.assertFalse(unit.has_flag("stunned"))
        unit.tick()
        self.assertTrue(unit.has_effect("war_cry"))
        unit.tick()
        self.assertFalse(unit.has_effect("war_cry"))
        for _ in range(20):
            unit.tick()
        self.assertEqual([e.definition.id for e in unit.effects], ["iron_will"])

    def test_dispel_by_tag(self):
        unit = DB.create_unit("knight", 1)
        unit.add_effect(DB.effects["poison"])
        unit.add_effect(DB.effects["stun"])
        unit.add_effect(DB.effects["war_cry"])
        removed = unit.dispel("debuff")
        self.assertEqual({e.definition.id for e in removed}, {"poison", "stun"})
        self.assertEqual([e.definition.id for e in unit.effects], ["war_cry"])

    def test_effect_save_and_load(self):
        unit = DB.create_unit("orc", 1)
        unit.add_effect(DB.effects["poison"], source=7)
        unit.add_effect(DB.effects["poison"], source=7)
        unit.add_effect(DB.effects["iron_will"])
        unit.tick()
        saved = json.loads(json.dumps(unit.save_effects()))
        self.assertEqual(saved[0], {"effect_id": "poison", "remaining": 2, "stacks": 2, "source": 7})
        self.assertEqual(set(saved[0]), {"effect_id", "remaining", "stacks", "source"})

        restored = ActiveEffect.from_save(saved[0], DB.effects)
        self.assertEqual(restored, unit.effects[0])
        self.assertIs(restored.definition, DB.effects["poison"])
        self.assertFalse(hasattr(restored, "unit"))

    def test_unit_state_json_roundtrip(self):
        unit = DB.create_unit("knight", 5, level=3, equipment=["iron_sword", "shield"])
        unit.take_damage(10)
        unit.add_effect(DB.effects["war_cry"])
        self.assertEqual({f.name for f in dataclasses.fields(UnitState)},
                         {"uid", "definition_id", "level", "current_hp", "equipment"})
        payload = json.dumps({"state": dataclasses.asdict(unit.state), "effects": unit.save_effects()})

        data = json.loads(payload)
        clone = DB.restore_unit(UnitState(**data["state"]), data["effects"])
        self.assertEqual(clone.state, unit.state)
        self.assertEqual(clone.hp, unit.hp)
        self.assertEqual({s: clone.stat(s) for s in ALL_STATS}, {s: unit.stat(s) for s in ALL_STATS})


class TacticsTests(unittest.TestCase):
    def test_registries(self):
        self.assertLessEqual({"always", "hp_below", "has_flag", "lacks_effect"}, set(CONDITIONS))
        self.assertLessEqual({"weakest", "strongest", "frontmost", "backmost", "random"}, set(SELECTORS))

    def test_cleric_heals_wounded_ally_else_attacks(self):
        cleric = DB.create_unit("cleric", 1)
        knight = DB.create_unit("knight", 2)
        enemy = DB.create_unit("goblin", 3)
        rng = random.Random(0)
        tactics = cleric.definition.tactics
        self.assertEqual(tactics.choose(cleric, [knight, cleric], [enemy], rng, DB.skills), ("attack", enemy))
        knight.take_damage(40)
        self.assertEqual(tactics.choose(cleric, [knight, cleric], [enemy], rng, DB.skills), ("heal", knight))
        cleric.ap.spend(3)  # остался 1 AP: правило лечения пропускается
        self.assertEqual(tactics.choose(cleric, [knight, cleric], [enemy], rng, DB.skills), ("attack", enemy))

    def test_archer_poisons_unpoisoned_then_hits_backmost(self):
        archer = DB.create_unit("archer", 1)
        goblin = DB.create_unit("goblin", 2)
        orc = DB.create_unit("orc", 3)
        mage = DB.create_unit("mage", 4)
        enemies = [goblin, orc, mage]
        rng = random.Random(0)
        tactics = archer.definition.tactics
        self.assertEqual(tactics.choose(archer, [archer], enemies, rng, DB.skills), ("poison_arrow", orc))
        for enemy in enemies:
            enemy.add_effect(DB.effects["poison"])
        self.assertEqual(tactics.choose(archer, [archer], enemies, rng, DB.skills), ("attack", mage))

    def test_new_condition_via_registry(self):
        class IsDefinition:
            def __init__(self, definition_id):
                self.definition_id = definition_id

            def check(self, actor, candidate):
                return candidate.definition.id == self.definition_id

        CONDITIONS["is_definition"] = IsDefinition
        try:
            tactics = TacticsSet.from_list([
                {"side": "enemy", "condition": {"type": "is_definition", "definition_id": "mage"},
                 "selector": "frontmost", "skill": "attack"},
            ])
            actor, goblin, mage = (DB.create_unit(d, i) for i, d in enumerate(["knight", "goblin", "mage"]))
            self.assertEqual(tactics.choose(actor, [actor], [goblin, mage], random.Random(0), DB.skills), ("attack", mage))
            self.assertIsNone(tactics.choose(actor, [actor], [goblin], random.Random(0), DB.skills))
        finally:
            del CONDITIONS["is_definition"]


class SquadAndWorldTests(unittest.TestCase):
    def test_formation_limits(self):
        formation = Formation()
        cells = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1)]
        for uid, (row, col) in enumerate(cells):
            formation.place(DB.create_unit("goblin", uid), row, col)
        self.assertEqual(len(formation), Formation.MAX_UNITS)
        with self.assertRaises(FormationError):
            formation.place(DB.create_unit("goblin", 99), 2, 2)  # шестой юнит

        formation = Formation()
        formation.place(DB.create_unit("goblin", 1), 0, 0)
        with self.assertRaises(FormationError):
            formation.place(DB.create_unit("goblin", 2), 0, 0)  # занято
        with self.assertRaises(FormationError):
            formation.place(DB.create_unit("goblin", 3), 3, 0)  # вне сетки
        with self.assertRaises(FormationError):
            formation.place(DB.create_unit("goblin", 1), 1, 1)  # уже в формации

    def test_formation_order_front_row_first(self):
        formation = Formation()
        for uid, (row, col) in enumerate([(2, 0), (0, 2), (1, 1), (0, 0)]):
            formation.place(DB.create_unit("goblin", uid), row, col)
        self.assertEqual([formation.position_of(u.uid) for u in formation.units], [(0, 0), (0, 2), (1, 1), (2, 0)])

    def test_squad_has_no_position_worldmap_does(self):
        self.assertEqual({f.name for f in dataclasses.fields(Squad)}, {"id", "name", "formation", "leader_uid"})
        world = WorldMap(8, 6)
        world.place("a", 3, 2)
        world.place("b", 4, 2)
        self.assertEqual(world.positions, {"a": (3, 2), "b": (4, 2)})
        self.assertTrue(world.are_adjacent("a", "b"))
        world.place("b", 6, 2)
        self.assertFalse(world.are_adjacent("a", "b"))
        self.assertEqual(world.squad_at(6, 2), "b")
        with self.assertRaises(ValueError):
            world.place("b", 3, 2)
        with self.assertRaises(ValueError):
            world.place("b", 8, 0)

    def test_army(self):
        army = Army("p", "P")
        unit = army.recruit(DB.create_unit("knight", 1))
        other = army.recruit(DB.create_unit("archer", 2))
        first = army.create_squad("s1", "First")
        second = army.create_squad("s2", "Second")
        army.assign(unit.uid, "s1", 0, 0)
        army.assign(other.uid, "s1", 1, 0)
        self.assertEqual(first.leader_uid, unit.uid)
        army.assign(unit.uid, "s2", 0, 1)
        self.assertEqual([u.uid for u in first.formation.units], [other.uid])
        self.assertEqual((first.leader_uid, second.leader_uid), (other.uid, unit.uid))
        with self.assertRaises(ValueError):
            army.recruit(unit)

    def test_demo_scenario(self):
        scenario = build_demo(DB)
        self.assertEqual([u.definition.id for u in scenario.player_squad.formation.units],
                         ["knight", "archer", "mage", "cleric"])
        self.assertEqual(sorted(u.definition.id for u in scenario.enemy_squad.formation.units),
                         ["goblin", "goblin", "mage", "orc"])
        self.assertTrue(scenario.world.are_adjacent(scenario.player_squad.id, scenario.enemy_squad.id))
        self.assertEqual((scenario.world.width, scenario.world.height), (8, 6))


class BattleTests(unittest.TestCase):
    SEEDS = range(1, 21)

    def test_battle_finishes_with_single_result(self):
        for seed in self.SEEDS:
            sim = demo_sim(seed)
            events = sim.run()
            self.assertTrue(sim.finished)
            self.assertIsInstance(events[0], BattleStarted)
            ended = [e for e in events if isinstance(e, BattleEnded)]
            self.assertEqual(len(ended), 1, seed)
            self.assertIs(events[-1], ended[0])
            self.assertEqual(sim.step(), [])

            alive = {s.id: [u for u in s.formation.units if u.is_alive] for s in (sim.attacker, sim.defender)}
            winner = ended[0].winner_id
            self.assertEqual(winner, sim.winner_id)
            self.assertIn(winner, (None, *alive))
            survivors = [sid for sid, units in alive.items() if units]
            if ended[0].reason == END_DEFEAT:
                self.assertEqual(survivors, [winner], seed)
            else:
                # Бой выдохся при живых отрядах: побеждает большая доля оставшегося HP.
                self.assertEqual(ended[0].reason, END_EXHAUSTED)
                self.assertEqual(len(survivors), 2, seed)
                share = {sq.id: sum(u.hp for u in sq.formation.units) / sum(u.max_hp for u in sq.formation.units)
                         for sq in (sim.attacker, sim.defender)}
                self.assertEqual(winner, max(share, key=share.get), seed)

    def test_round_limit_gives_draw(self):
        sim = demo_sim(1, max_rounds=1)
        events = sim.run()
        self.assertIsNone(sim.winner_id)
        self.assertEqual(events[-1], BattleEnded(None, END_ROUND_LIMIT))

    def test_same_seed_same_events(self):
        self.assertEqual(demo_sim(42).run(), demo_sim(42).run())

    def test_step_matches_run(self):
        stepped = demo_sim(7)
        collected = []
        while not stepped.finished:
            new = stepped.step()
            self.assertEqual(sum(isinstance(e, TurnStarted) for e in new) <= 1, True)
            collected.extend(new)
        self.assertEqual(collected, demo_sim(7).run())

    def test_different_seeds_differ(self):
        self.assertNotEqual(demo_sim(1).run(), demo_sim(2).run())

    def test_turn_order_by_speed(self):
        sim = demo_sim(3)
        order = [e.unit for e in sim.step() + sim.step() + sim.step() if isinstance(e, TurnStarted)]
        speeds = [sim.units[uid].stat(Stat.SPD) for uid in order]
        self.assertEqual(speeds, sorted(speeds, reverse=True))
        self.assertEqual(speeds[0], max(u.stat(Stat.SPD) for u in sim.units.values()))

    def test_permanent_passive_applied_at_start(self):
        sim = demo_sim(1)
        knight = sim.attacker.formation.units[0]
        def_before = knight.stat(Stat.DEF)
        events = sim.step()
        self.assertIsInstance(events[0], BattleStarted)
        self.assertEqual(events[1], PassiveTriggered(knight.uid, "iron_will"))
        self.assertTrue(knight.has_effect("iron_will"))
        self.assertEqual(knight.stat(Stat.DEF), round(def_before * 1.2))
        self.assertEqual(knight.pp.current, knight.pp.max)
        sim.run()
        if knight.is_alive:
            self.assertTrue(knight.has_effect("iron_will"))  # постоянный эффект не истекает

    def test_avenger_limited_by_pp(self):
        # Рыцари бьют передний ряд: три гоблина гибнут раньше орка,
        # но PP орка хватает только на одно срабатывание.
        weak = make_squad("weak", [("goblin", 1, 0, 0), ("goblin", 1, 0, 1), ("goblin", 1, 0, 2), ("orc", 1, 1, 1)])
        strong = make_squad("strong", [("knight", 8, 0, 0), ("knight", 8, 0, 1)], first_uid=10)
        orc = weak.formation.units[-1]
        sim = BattleSimulation(weak, strong, DB, seed=5)
        events = sim.run()

        goblin_uids = {u.uid for u in weak.formation.units[:3]}
        orc_death = next((i for i, e in enumerate(events) if e == UnitDied(orc.uid)), len(events))
        goblin_deaths = [i for i, e in enumerate(events) if isinstance(e, UnitDied) and e.unit in goblin_uids]
        self.assertGreaterEqual(sum(i < orc_death for i in goblin_deaths), 2)

        triggers = [e for e in events if e == PassiveTriggered(orc.uid, "avenger")]
        self.assertEqual(len(triggers), orc.definition.pp_max)
        self.assertEqual(orc.pp.current, 0)

    def test_avenger_never_exceeds_pp_in_demo(self):
        for seed in self.SEEDS:
            sim = demo_sim(seed)
            counts = {}
            for e in sim.run():
                if isinstance(e, PassiveTriggered) and e.passive_id == "avenger":
                    counts[e.unit] = counts.get(e.unit, 0) + 1
            for uid, count in counts.items():
                self.assertLessEqual(count, sim.units[uid].definition.pp_max)

    def test_stunned_unit_skips_turn(self):
        sim = demo_sim(1)
        victim = sim.defender.formation.units[0]
        victim.add_effect(DB.effects["stun"])
        while True:
            events = sim.step()
            if TurnStarted(victim.uid) in events:
                break
        self.assertIn(TurnSkipped(victim.uid, "stunned"), events)
        self.assertNotIn(TurnSkipped(victim.uid, SKIP_NO_ACTION), events)
        self.assertFalse(any(isinstance(e, SkillUsed) and e.user == victim.uid for e in events))
        self.assertIn(EffectExpired(victim.uid, "stun"), events)
        self.assertEqual(victim.ap.current, victim.ap.max)  # AP не потрачен
        self.assertFalse(victim.has_flag("stunned"))

    def test_hp_always_in_range(self):
        for seed in self.SEEDS:
            sim = demo_sim(seed)
            while not sim.finished:
                sim.step()
                for unit in sim.units.values():
                    self.assertGreaterEqual(unit.state.current_hp, 0)
                    self.assertLessEqual(unit.state.current_hp, unit.max_hp)
                    self.assertLessEqual(unit.ap.current, unit.ap.max)
                    self.assertGreaterEqual(unit.pp.current, 0)

    def test_fallback_attack_when_no_rule_matches(self):
        # Юнит без единого правила тактик.
        definition = dataclasses.replace(DB.units["goblin"], id="dummy", name="Dummy", tactics=TacticsSet())
        db = Database(DB.effects, DB.items, DB.skills, DB.passives, {**DB.units, "dummy": definition})
        a, b = Squad("a", "A"), Squad("b", "B")
        a.formation.place(db.create_unit("dummy", 1), 0, 0)
        b.formation.place(db.create_unit("dummy", 2), 1, 1)
        b.formation.place(db.create_unit("dummy", 3), 0, 2)
        sim = BattleSimulation(a, b, db, seed=1)
        used = [e for e in sim.run() if isinstance(e, SkillUsed) and e.user == 1]
        self.assertTrue(used)
        self.assertTrue(all(e.skill_id == "attack" for e in used))
        self.assertEqual(used[0].target, 3)  # первый враг = передний ряд

    def test_ap_never_regenerates_and_battle_ends_by_exhaustion(self):
        a = make_squad("a", [("knight", 5, 0, 0)])
        b = make_squad("b", [("knight", 5, 0, 0)], first_uid=2)
        sim = BattleSimulation(a, b, DB, seed=1)
        events = sim.run()
        self.assertEqual(events[-1].reason, END_EXHAUSTED)
        self.assertLess(sim.round, sim.max_rounds)
        for unit in sim.units.values():
            self.assertTrue(unit.is_alive)
            self.assertEqual(unit.ap.current, 0)
            spent = sum(DB.skills[e.skill_id].ap_cost for e in events if isinstance(e, SkillUsed) and e.user == unit.uid)
            self.assertEqual(spent, unit.ap.max)
        # Равные отряды: побеждает тот, у кого осталась большая доля HP.
        left, right = sim.units[1], sim.units[2]
        expected = "a" if left.hp > right.hp else "b" if right.hp > left.hp else None
        self.assertEqual(sim.winner_id, expected)

    def test_idle_round_ends_battle(self):
        # У юнитов есть AP, но единственное правило никогда не выполняется, а запасной атаки нет.
        idle = dataclasses.replace(
            DB.units["cleric"], id="idle", skills=("heal",),
            tactics=TacticsSet.from_list([{"skill": "heal", "condition": {"type": "hp_below", "value": 0.1}}]),
        )
        db = Database(DB.effects, DB.items, DB.skills, DB.passives, {**DB.units, "idle": idle})
        a, b = Squad("a", "A"), Squad("b", "B")
        a.formation.place(db.create_unit("idle", 1), 0, 0)
        b.formation.place(db.create_unit("idle", 2), 0, 0)
        sim = BattleSimulation(a, b, db, seed=1)
        events = sim.run()
        self.assertEqual((sim.round, events[-1]), (1, BattleEnded(None, END_EXHAUSTED)))
        self.assertEqual([e for e in events if isinstance(e, TurnSkipped)],
                         [TurnSkipped(1, SKIP_NO_ACTION), TurnSkipped(2, SKIP_NO_ACTION)])

    def test_format_event_covers_all_events(self):
        sim = demo_sim(1)
        for event in sim.run():
            text = format_event(event, lambda uid: sim.units[uid].label)
            self.assertTrue(text.strip())
            self.assertNotIn("(uid", text)
        self.assertEqual(format_event(UnitDied(1), lambda uid: sim.units[uid].label), "  Knight(1) dies")


if __name__ == "__main__":
    unittest.main()
