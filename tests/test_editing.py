"""Тесты редактирования и расширений ядра: тактики, конструктор навыков, области,
слоты снаряжения, отряды, сохранение расстановки, выбор языка."""
import dataclasses
import json
import random
import string
import tempfile
import unittest
from pathlib import Path

from game.areas import AREAS
from game.battle import BattleSimulation
from game.database import Database
from game.definitions import SkillDefinition
from game.editing import (
    SkillDraft,
    condition_params,
    cycle,
    default_apply,
    default_condition,
    default_rule,
    describe_skill,
    param_options,
    set_tactics,
    skill_users,
    slugify,
)
from game.events import (
    END_DEFEAT,
    END_EXHAUSTED,
    REASON_TEXT,
    BattleEnded,
    DamageDealt,
    EffectApplied,
    EffectExpired,
    Healed,
    PassiveTriggered,
    ResourceGained,
    SkillUsed,
    TurnStarted,
    UnitDied,
    format_event,
)
from game.i18n import DEFAULT_LANG, Translator, available_languages
from game.save import clone_scenario, load_settings, load_setup, save_setup, scenario_from_save, scenario_to_save
from game.scenario import build_demo
from game.squad import Formation, FormationError, Squad
from game.stats import Stat
from game.tactics import CONDITIONS, SELECTORS, TacticsSet
from game.unit import UnitState, place_equipment
from game.world import Army


def squads(db, left, right):
    """Два отряда из списков (definition_id, level, row, col); uid идут подряд с 1."""
    result, uid = [], 1
    for squad_id, roster in (("a", left), ("b", right)):
        squad = Squad(squad_id, squad_id.upper())
        for definition_id, level, row, col in roster:
            squad.formation.place(db.create_unit(definition_id, uid, level), row, col)
            uid += 1
        result.append(squad)
    return result


def duel(db, left_id, right_id, seed=1, left_level=1, right_level=1):
    """Два отряда по одному юниту: uid 1 против uid 2."""
    a, b = squads(db, [(left_id, left_level, 0, 0)], [(right_id, right_level, 0, 0)])
    return BattleSimulation(a, b, db, seed=seed), a.formation.units[0], b.formation.units[0]


def rule(skill, **parts):
    return {"skill": skill, "self_condition": {"type": "always"}, "condition": {"type": "always"},
            "selector": "frontmost", **parts}


def turn_of(sim, uid):
    """Доигрывает до хода юнита и возвращает события этого хода."""
    while not sim.finished:
        events = sim.step()
        if TurnStarted(uid) in events:
            return events[events.index(TurnStarted(uid)):]
    raise AssertionError(f"unit {uid} never had a turn")


def new_skill(db, units=(), items=(), **fields):
    draft = SkillDraft(bind_units=list(units), bind_items=list(items), **fields)
    return draft.save_to(db)


class TacticsEditingTests(unittest.TestCase):
    def setUp(self):
        self.db = Database.load()

    def test_default_tactics_roundtrip(self):
        for definition in self.db.units.values():
            data = json.loads(json.dumps(definition.tactics.to_list()))
            self.assertEqual(TacticsSet.from_list(data).to_list(), data)
        self.assertEqual(self.db.units["cleric"].tactics.to_list()[0], {
            "skill": "heal", "self_condition": {"type": "always"},
            "condition": {"type": "hp_below", "value": 0.6}, "selector": "weakest",
        })

    def test_legacy_side_key_is_ignored(self):
        old = {"side": "self", "condition": {"type": "always"}, "selector": "frontmost", "skill": "attack"}
        self.assertEqual(TacticsSet.from_list([old]).to_list(), [rule("attack")])

    def test_every_registered_condition_has_editor_defaults(self):
        for name in CONDITIONS:
            data = default_condition(name, self.db)
            for param, kind in condition_params(name).items():
                self.assertIn(data[param], param_options(kind, self.db))
            for key in ("condition", "self_condition"):
                item = rule("attack", **{key: data})
                self.assertEqual(TacticsSet.from_list([item]).to_list(), [item])
        self.assertEqual(param_options("flag", self.db), ["stunned"])

    def test_cycle(self):
        names = list(SELECTORS)
        self.assertEqual(cycle(names, names[-1], 1), names[0])
        self.assertEqual(cycle(names, names[0], -1), names[-1])
        self.assertEqual(cycle(names, "missing", 1), names[0])

    def test_skill_decides_the_side_of_the_target(self):
        cleric, knight, goblin = (self.db.create_unit(d, i) for i, d in enumerate(["cleric", "knight", "goblin"], 1))
        knight.take_damage(50)
        tactics = TacticsSet.from_list([rule("heal"), rule("attack")])
        rng = random.Random(0)
        # heal нацелен на союзников: выбирается первый союзник, а не враг.
        self.assertEqual(tactics.choose(cleric, [knight, cleric], [goblin], rng, self.db.skills), ("heal", knight))
        self.assertEqual(self.db.skills["heal"].targets, "ally")
        self.assertEqual(self.db.skills["attack"].targets, "enemy")
        self.assertEqual(TacticsSet.from_list([rule("attack")]).choose(cleric, [cleric], [goblin], rng, self.db.skills),
                         ("attack", goblin))

    def test_self_condition(self):
        sim, knight, orc = duel(self.db, "knight", "orc", right_level=3)
        set_tactics(self.db, knight, [
            rule("power_strike", self_condition={"type": "hp_below", "value": 0.8}),
            rule("attack"),
        ])
        events = sim.run()
        hp, used = knight.max_hp, []
        for e in events:
            if isinstance(e, DamageDealt) and e.target == knight.uid:
                hp = e.hp_left
            elif isinstance(e, SkillUsed) and e.user == knight.uid:
                used.append((e.skill_id, hp < knight.max_hp * 0.8))
        self.assertIn(("attack", False), used)
        self.assertIn(("power_strike", True), used)
        # Здоровый рыцарь мощный удар не использует; раненый бьёт им, пока хватает AP.
        self.assertTrue(all(wounded for skill, wounded in used if skill == "power_strike"), used)

    def test_custom_tactics_change_battle_and_leave_definition_alone(self):
        sim, knight, orc = duel(self.db, "knight", "orc")
        default = knight.definition.tactics
        self.assertFalse(knight.has_custom_tactics)
        set_tactics(self.db, knight, [rule("attack")])
        self.assertTrue(knight.has_custom_tactics)
        used = [e.skill_id for e in sim.run() if isinstance(e, SkillUsed) and e.user == knight.uid]
        self.assertEqual(used, ["attack"] * knight.ap.max)
        self.assertIs(knight.definition.tactics, default)
        self.assertIs(self.db.create_unit("knight", 9).tactics, default)
        knight.reset_tactics()
        self.assertFalse(knight.has_custom_tactics)

    def test_rule_order_matters(self):
        rules = self.db.units["knight"].tactics.to_list()
        used = []
        for order in (rules, rules[::-1]):
            sim, knight, _ = duel(self.db, "knight", "orc")
            set_tactics(self.db, knight, order)
            used.append({e.skill_id for e in sim.run() if isinstance(e, SkillUsed) and e.user == knight.uid})
        self.assertEqual(used, [{"power_strike"}, {"attack"}])

    def test_unit_cannot_use_foreign_skill(self):
        knight = self.db.create_unit("knight", 1)
        with self.assertRaises(ValueError):
            set_tactics(self.db, knight, [rule("fireball")])
        self.assertFalse(knight.has_custom_tactics)


class SkillBindingTests(unittest.TestCase):
    def setUp(self):
        self.db = Database.load()

    def test_bound_to_unit_type(self):
        new_skill(self.db, units=["knight", "orc"], name="Slam")
        knight, archer = self.db.create_unit("knight", 1), self.db.create_unit("archer", 2)
        self.assertIn("slam", self.db.skills_for(knight))
        self.assertNotIn("slam", self.db.skills_for(archer))
        set_tactics(self.db, knight, [rule("slam")])
        with self.assertRaises(ValueError):
            set_tactics(self.db, archer, [rule("slam")])

    def test_bound_to_item(self):
        new_skill(self.db, items=["iron_sword"], name="Blade Dance")
        armed = self.db.create_unit("knight", 1, equipment=["iron_sword"])
        bare = self.db.create_unit("knight", 2)
        self.assertIn("blade_dance", self.db.skills_for(armed))
        self.assertNotIn("blade_dance", self.db.skills_for(bare))
        armed.unequip(0)
        self.assertNotIn("blade_dance", self.db.skills_for(armed))

    def test_unbound_skill_is_available_to_nobody(self):
        new_skill(self.db, name="Orphan")
        for definition_id in self.db.units:
            self.assertNotIn("orphan", self.db.skills_for(self.db.create_unit(definition_id, 1)))

    def test_rule_with_lost_skill_is_skipped_in_battle(self):
        new_skill(self.db, items=["iron_sword"], name="Blade Dance", ap_cost=1)
        a, b = squads(self.db, [("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        knight = a.formation.units[0]
        knight.equip(0, "iron_sword")
        set_tactics(self.db, knight, [rule("blade_dance"), rule("attack")])
        knight.unequip(0)  # меч сняли, правило осталось
        events = BattleSimulation(a, b, self.db, seed=1).run()
        used = {e.skill_id for e in events if isinstance(e, SkillUsed) and e.user == knight.uid}
        self.assertEqual(used, {"attack"})

    def test_rebinding_replaces_binding(self):
        new_skill(self.db, units=["knight"], name="Slam")
        new_skill(self.db, units=["mage"], name="Slam")
        self.assertEqual(self.db.custom_skill_ids, ["slam"])
        self.assertEqual(self.db.skill_bindings["slam"].units, ("mage",))
        with self.assertRaises(ValueError):
            new_skill(self.db, units=["dragon"], name="Slam")
        with self.assertRaises(ValueError):
            new_skill(self.db, items=["excalibur"], name="Slam")


class EquipmentTests(unittest.TestCase):
    def setUp(self):
        self.db = Database.load()

    def test_every_class_has_fixed_slots(self):
        for definition in self.db.units.values():
            self.assertTrue(definition.slots, definition.id)
            unit = self.db.create_unit(definition.id, 1)
            self.assertEqual(unit.state.equipment, [None] * len(definition.slots))
        self.assertEqual(self.db.units["archer"].slots, ("bow", "light_armor", "artifact", "artifact"))
        self.assertEqual(self.db.units["knight"].slots, ("light_sword", "light_shield", "medium_armor", "artifact"))

    def test_items_go_to_matching_slots(self):
        knight = self.db.create_unit("knight", 1, equipment=["shield", "iron_sword"])
        self.assertEqual(knight.state.equipment, ["iron_sword", "shield", None, None])
        self.assertEqual([i.id for i in knight.equipped], ["iron_sword", "shield"])
        with self.assertRaises(ValueError):
            self.db.create_unit("archer", 2, equipment=["iron_sword"])   # у лучника нет слота меча
        with self.assertRaises(ValueError):
            self.db.create_unit("knight", 3, equipment=["shield", "shield"])  # слот щита один
        with self.assertRaises(ValueError):
            self.db.create_unit("knight", 4, equipment=["excalibur"])

    def test_equip_and_unequip(self):
        knight = self.db.create_unit("knight", 1)
        atk = knight.stat(Stat.ATK)
        knight.equip(0, "iron_sword")
        self.assertEqual(knight.stat(Stat.ATK), atk + 5)
        with self.assertRaises(ValueError):
            knight.equip(1, "iron_sword")  # меч в слот щита
        with self.assertRaises(ValueError):
            knight.equip(0, "excalibur")
        self.assertEqual(knight.unequip(0), "iron_sword")
        self.assertEqual(knight.stat(Stat.ATK), atk)

    def test_two_slots_of_one_type(self):
        ring = dataclasses.replace(self.db.items["shield"], id="ring", name="Ring", slot="artifact")
        items = {**self.db.items, "ring": ring}
        self.assertEqual(place_equipment(self.db.units["archer"].slots, items, ["ring", "ring"]),
                         [None, None, "ring", "ring"])
        with self.assertRaises(ValueError):
            place_equipment(self.db.units["archer"].slots, items, ["ring", "ring", "ring"])

    def test_state_with_slots_is_json_serializable(self):
        knight = self.db.create_unit("knight", 1, equipment=["iron_sword"])
        data = json.loads(json.dumps(dataclasses.asdict(knight.state)))
        self.assertEqual(data["equipment"], ["iron_sword", None, None, None])
        clone = self.db.restore_unit(UnitState(**data))
        self.assertEqual(clone.stat(Stat.ATK), knight.stat(Stat.ATK))

    def test_item_grants_active_skill_and_passive(self):
        # Меч даёт носителю активный навык и пассивку; лучнику для теста выдан слот под меч.
        sword = dataclasses.replace(self.db.items["iron_sword"], skills=("fireball",), passives=("avenger",))
        archer_def = dataclasses.replace(self.db.units["archer"], slots=("light_sword",))
        db = Database(self.db.effects, {**self.db.items, "iron_sword": sword}, self.db.skills,
                      self.db.passives, {**self.db.units, "archer": archer_def})
        a, b = squads(db, [("goblin", 1, 0, 0), ("archer", 1, 1, 0)], [("knight", 9, 0, 0)])
        archer = a.formation.units[1]
        self.assertNotIn("fireball", db.skills_for(archer))
        self.assertNotIn("avenger", archer.passive_ids)

        archer.equip(0, "iron_sword")
        self.assertIn("fireball", db.skills_for(archer))
        self.assertIn("avenger", archer.passive_ids)
        set_tactics(db, archer, [rule("fireball")])
        events = BattleSimulation(a, b, db, seed=1).run()
        self.assertIn(SkillUsed(archer.uid, "fireball", 3), events)
        self.assertIn(UnitDied(1), events)  # гоблин гибнет от рыцаря 9 уровня
        self.assertIn(PassiveTriggered(archer.uid, "avenger"), events)

        archer.unequip(0)
        self.assertNotIn("fireball", db.skills_for(archer))
        self.assertNotIn("avenger", archer.passive_ids)


class SkillAreaTests(unittest.TestCase):
    ENEMIES = [("goblin", 1, 0, 0), ("goblin", 1, 0, 1), ("goblin", 1, 1, 0), ("goblin", 1, 2, 1)]  # uid 2..5

    def setUp(self):
        self.db = Database.load()

    def hit_targets(self, area):
        new_skill(self.db, units=["mage"], name="Wave", power=0.1, ap_cost=1, area=area)
        a, b = squads(self.db, [("mage", 5, 0, 0)], self.ENEMIES)  # 5 уровень, чтобы пережить гоблинов
        set_tactics(self.db, a.formation.units[0], [rule("wave")])
        events = turn_of(BattleSimulation(a, b, self.db, seed=1), 1)
        self.assertEqual([e for e in events if isinstance(e, SkillUsed)], [SkillUsed(1, "wave", 2)])
        return [e.target for e in events if isinstance(e, DamageDealt)]

    def test_registered_areas(self):
        self.assertEqual(set(AREAS), {"single", "row", "column", "all"})

    def test_single(self):
        self.assertEqual(self.hit_targets("single"), [2])

    def test_row(self):
        self.assertEqual(self.hit_targets("row"), [2, 3])

    def test_column(self):
        self.assertEqual(self.hit_targets("column"), [2, 4])

    def test_all(self):
        self.assertEqual(self.hit_targets("all"), [2, 3, 4, 5])

    def test_unknown_area_is_rejected(self):
        with self.assertRaises(ValueError):
            SkillDraft(name="Bad", area="cone").build(self.db)
        with self.assertRaises(ValueError):
            SkillDefinition.from_dict("bad", {"area": "cone"})

    def test_area_heal_and_effects_reach_every_ally_in_area(self):
        new_skill(self.db, units=["cleric"], name="Mass Heal", kind="heal", targets="ally", area="all",
                  power=1.0, ap_cost=1, applies=[dict(default_apply(self.db, "war_cry"), to="target")])
        a, b = squads(self.db, [("knight", 1, 0, 0), ("cleric", 1, 1, 0), ("archer", 1, 1, 1)], [("goblin", 1, 0, 0)])
        cleric = a.formation.units[1]
        set_tactics(self.db, cleric, [rule("mass_heal")])
        events = turn_of(BattleSimulation(a, b, self.db, seed=1), cleric.uid)
        self.assertEqual([e.target for e in events if isinstance(e, Healed)], [1, 2, 3])
        self.assertEqual([e.target for e in events if isinstance(e, EffectApplied)], [1, 2, 3])

    def test_area_kill_ends_battle_once(self):
        new_skill(self.db, units=["mage"], name="Meteor", power=5.0, ap_cost=1, area="all")
        a, b = squads(self.db, [("mage", 9, 0, 0)], self.ENEMIES)
        set_tactics(self.db, a.formation.units[0], [rule("meteor")])
        sim = BattleSimulation(a, b, self.db, seed=1)
        events = sim.run()
        self.assertEqual([e for e in events if isinstance(e, UnitDied)], [UnitDied(u) for u in (2, 3, 4, 5)])
        self.assertEqual(events[-1], BattleEnded("a", END_DEFEAT))
        self.assertEqual(sum(isinstance(e, BattleEnded) for e in events), 1)


class SkillBuilderTests(unittest.TestCase):
    def setUp(self):
        self.db = Database.load()

    def test_builtin_skills_keep_working_and_roundtrip(self):
        self.assertEqual([a.effect_id for a in self.db.skills["poison_arrow"].applies], ["poison"])
        for skill in self.db.skills.values():
            self.assertEqual(SkillDefinition.from_dict(skill.id, json.loads(json.dumps(skill.to_dict()))), skill)

    def test_build_skill_with_many_effects(self):
        draft = SkillDraft(name="Toxic Shout!", kind="damage", power=1.5, ap_cost=0, bind_units=["knight"])
        for _ in range(4):  # число эффектов не ограничено
            draft.applies.append(default_apply(self.db, "poison"))
        draft.applies.append(default_apply(self.db, "war_cry"))
        self.assertEqual([a["to"] for a in draft.applies], ["target"] * 4 + ["self"])
        skill = draft.save_to(self.db)
        self.assertEqual((skill.id, len(skill.applies)), ("toxic_shout", 5))
        self.assertIn("War Cry -> self", describe_skill(skill, self.db))

        sim, knight, orc = duel(self.db, "knight", "orc")
        set_tactics(self.db, knight, [rule("toxic_shout")])
        atk_before = knight.stat(Stat.ATK)
        events = turn_of(sim, knight.uid)
        applied = [e for e in events if isinstance(e, EffectApplied)]
        # 4-й яд упирается в max_stacks и только обновляет длительность.
        self.assertEqual([(e.target, e.effect_id, e.stacks) for e in applied],
                         [(orc.uid, "poison", n) for n in (1, 2, 3, 3)] + [(knight.uid, "war_cry", 1)])
        self.assertEqual(orc.effects[0].stacks, 3)
        self.assertEqual(knight.stat(Stat.ATK), round(atk_before * 1.3))
        # Бафф, наложенный в свой ход, в этот же ход не убывает.
        self.assertEqual(next(e for e in knight.effects if e.definition.id == "war_cry").remaining, 3)
        self.assertNotIn(EffectExpired(knight.uid, "war_cry"), events)

    def test_apply_condition(self):
        new_skill(self.db, units=["knight"], name="Finisher", power=1.0, ap_cost=0,
                  applies=[dict(default_apply(self.db, "stun"), condition={"type": "hp_below", "value": 0.5})])
        sim, knight, orc = duel(self.db, "knight", "orc", right_level=3)
        set_tactics(self.db, knight, [rule("finisher")])
        events = sim.run()
        stun = next((e for e in events if isinstance(e, EffectApplied) and e.effect_id == "stun"), None)
        self.assertIsNotNone(stun, "stun was never applied")
        index = events.index(stun)
        hit = events[index - 1]
        self.assertIsInstance(hit, DamageDealt)
        self.assertLess(hit.hp_left, orc.max_hp * 0.5)
        early_hits = [e for e in events[:index - 1] if isinstance(e, DamageDealt) and e.cause == "finisher"]
        self.assertTrue(early_hits)
        self.assertTrue(all(e.hp_left >= orc.max_hp * 0.5 for e in early_hits))

    def test_support_skill_on_self(self):
        draft = SkillDraft(name="Rally", bind_units=["knight"])
        draft.set_kind("support")
        self.assertEqual(draft.targets, "ally")
        draft.targets = "self"
        with self.assertRaises(ValueError):
            draft.build(self.db)  # без эффектов и восстановления бессмысленен
        draft.applies.append(default_apply(self.db, "war_cry"))
        draft.save_to(self.db)
        sim, knight, orc = duel(self.db, "knight", "orc")
        set_tactics(self.db, knight, [rule("rally")])
        events = sim.run()
        rallies = [e for e in events if isinstance(e, SkillUsed) and e.user == knight.uid]
        self.assertEqual(rallies, [SkillUsed(knight.uid, "rally", knight.uid)] * knight.ap.max)
        self.assertFalse(any(isinstance(e, (DamageDealt, Healed)) and e.source == knight.uid for e in events))
        self.assertEqual(events[-1], BattleEnded("b", END_EXHAUSTED))

    def test_ap_and_pp_restore(self):
        new_skill(self.db, units=["knight"], name="Second Wind", kind="support", targets="self",
                  ap_cost=1, ap_restore=2, pp_restore=1)
        sim, knight, goblin = duel(self.db, "knight", "goblin")
        set_tactics(self.db, knight, [rule("second_wind")])
        sim.step()               # гоблин быстрее и ходит первым
        knight.pp.spend(1)       # как будто пассивка уже сработала
        events = turn_of(sim, knight.uid)
        # 4 AP - 1 за навык + 2 восстановлено, но не выше максимума.
        self.assertIn(ResourceGained(1, 1, "AP", 1, 4, "second_wind"), events)
        self.assertIn(ResourceGained(1, 1, "PP", 1, 1, "second_wind"), events)
        self.assertEqual((knight.ap.current, knight.pp.current), (4, 1))
        self.assertIn("+2 AP", describe_skill(self.db.skills["second_wind"], self.db))

    def test_effects_on_killed_target_are_skipped(self):
        new_skill(self.db, units=["knight"], name="Overkill", power=5.0, ap_cost=0,
                  applies=[default_apply(self.db, "poison"), default_apply(self.db, "war_cry")])
        sim, knight, goblin = duel(self.db, "knight", "goblin", left_level=5)
        set_tactics(self.db, knight, [rule("overkill")])
        events = sim.run()
        self.assertIn(UnitDied(goblin.uid), events)
        self.assertFalse(any(isinstance(e, EffectApplied) and e.target == goblin.uid for e in events))
        self.assertIn(EffectApplied(knight.uid, "war_cry", 1, knight.uid), events)
        self.assertEqual(events[-1], BattleEnded("a", END_DEFEAT))

    def test_validation(self):
        with self.assertRaises(ValueError):
            SkillDraft(name="!!!").build(self.db)
        with self.assertRaises(ValueError):
            SkillDraft(name="Big", power=99).build(self.db)
        with self.assertRaises(ValueError):
            SkillDraft(name="Aim", targets="everyone").build(self.db)
        with self.assertRaises(ValueError):
            SkillDraft(name="Bad", applies=[{"effect_id": "nope", "to": "target", "condition": {"type": "always"}}]).build(self.db)
        with self.assertRaises(ValueError):
            SkillDraft(name="Attack").save_to(self.db)  # встроенный id
        self.assertEqual(slugify("  Fire  Ball #2 "), "fire_ball_2")

    def test_update_copy_and_remove_custom_skill(self):
        new_skill(self.db, units=["knight"], name="Jab", power=0.5)
        new_skill(self.db, units=["knight"], name="Jab", power=0.7)
        self.assertEqual(self.db.custom_skill_ids, ["jab"])
        self.assertEqual(self.db.skills["jab"].power, 0.7)
        copy = SkillDraft.from_skill(self.db.skills["jab"], binding=self.db.skill_bindings["jab"])
        self.assertEqual((copy.bind_units, copy.power), (["knight"], 0.7))
        template = SkillDraft.from_skill(self.db.skills["heal"], name="Big Heal")
        self.assertEqual((template.kind, template.targets, template.bind_units), ("heal", "ally", []))

        knight = self.db.create_unit("knight", 1)
        set_tactics(self.db, knight, [rule("jab")])
        self.assertEqual(skill_users("jab", [knight]), [knight])
        knight.reset_tactics()
        self.assertEqual(skill_users("jab", [knight]), [])
        self.db.remove_custom_skill("jab")
        self.assertNotIn("jab", self.db.skills)
        with self.assertRaises(ValueError):
            self.db.remove_custom_skill("attack")


class SquadEditingTests(unittest.TestCase):
    def setUp(self):
        self.db = Database.load()
        self.army = Army("p", "P")
        self.squad = self.army.create_squad("s", "S")
        for uid, (definition_id, row, col) in enumerate([("knight", 0, 0), ("archer", 1, 1), ("mage", 2, 2)], start=1):
            self.army.recruit(self.db.create_unit(definition_id, uid))
            self.army.assign(uid, "s", row, col)

    def test_swap_and_move(self):
        formation = self.squad.formation
        formation.swap((0, 0), (1, 1))
        self.assertEqual((formation.unit_at(0, 0).uid, formation.unit_at(1, 1).uid), (2, 1))
        formation.swap((0, 0), (0, 2))  # перенос в пустую клетку
        self.assertIsNone(formation.unit_at(0, 0))
        self.assertEqual(formation.unit_at(0, 2).uid, 2)
        self.assertEqual(len(formation), 3)
        with self.assertRaises(FormationError):
            formation.swap((0, 0), (3, 0))

    def test_unassign_reserve_leader_dismiss(self):
        self.assertEqual(self.squad.leader_uid, 1)
        self.army.set_leader("s", 3)
        self.assertEqual(self.squad.leader_uid, 3)
        self.army.unassign(3)
        self.assertEqual(self.squad.leader_uid, 1)
        self.assertEqual([u.uid for u in self.army.reserve()], [3])
        with self.assertRaises(ValueError):
            self.army.set_leader("s", 3)
        self.army.dismiss(3)
        self.army.dismiss(1)
        self.assertEqual(list(self.army.units), [2])
        self.assertEqual(self.squad.leader_uid, 2)
        self.army.unassign(2)
        self.assertIsNone(self.squad.leader_uid)

    def test_full_squad_rejects_sixth_unit(self):
        for uid, col in ((4, 1), (5, 2)):
            self.army.recruit(self.db.create_unit("goblin", uid))
            self.army.assign(uid, "s", 0, col)
        self.army.recruit(self.db.create_unit("goblin", 6))
        with self.assertRaises(FormationError):
            self.army.assign(6, "s", 1, 0)
        self.assertEqual(len(self.squad.formation), Formation.MAX_UNITS)
        self.assertEqual([u.uid for u in self.army.reserve()], [6])

    def test_empty_squad_loses_immediately(self):
        sim = BattleSimulation(self.squad, Squad("e", "E"), self.db, seed=1)
        self.assertEqual(sim.run()[-1], BattleEnded("s", END_DEFEAT))


class SetupSaveTests(unittest.TestCase):
    def setUp(self):
        self.db = Database.load()
        self.scenario = build_demo(self.db)
        new_skill(self.db, units=["knight"], items=["shield"], name="Venom Strike", power=1.2, ap_cost=1,
                  area="row", applies=[default_apply(self.db, "poison")])
        knight = self.scenario.player_squad.formation.units[0]
        set_tactics(self.db, knight, [rule("venom_strike"),
                                      rule("attack", self_condition={"type": "hp_below", "value": 0.9})])
        self.scenario.player.recruit(self.db.create_unit("goblin", 50))  # резерв
        self.scenario.player_squad.formation.swap((0, 1), (0, 0))
        self.scenario.player.set_leader("vanguard", 2)

    def test_scenario_roundtrip(self):
        data = json.loads(json.dumps(scenario_to_save(self.scenario)))
        restored = scenario_from_save(self.db, data)
        self.assertEqual(scenario_to_save(restored), scenario_to_save(self.scenario))
        self.assertEqual(restored.player_squad.formation.unit_at(0, 0).uid, 1)
        self.assertEqual(restored.player_squad.leader_uid, 2)
        self.assertEqual([u.uid for u in restored.player.reserve()], [50])
        self.assertTrue(restored.player.units[1].has_custom_tactics)
        self.assertFalse(restored.player.units[2].has_custom_tactics)
        self.assertEqual(restored.player.units[1].state.equipment, ["iron_sword", "shield", None, None])
        self.assertEqual(restored.world.positions, self.scenario.world.positions)

    def test_file_roundtrip_into_fresh_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "setup.json"
            save_setup(path, self.db, self.scenario, {"language": "ru"})
            fresh_db = Database.load()
            restored = load_setup(path, fresh_db)
            self.assertEqual(load_settings(path), {"language": "ru"})
        self.assertEqual(fresh_db.skills["venom_strike"], self.db.skills["venom_strike"])
        self.assertEqual(fresh_db.skill_bindings, self.db.skill_bindings)
        self.assertEqual(scenario_to_save(restored), scenario_to_save(self.scenario))

    def test_legacy_custom_skill_without_binding_goes_to_every_unit_type(self):
        db = Database.load()
        db.load_custom_skills({"old": {"name": "Old", "kind": "heal", "ap_cost": 1}})
        self.assertEqual(db.skill_bindings["old"].units, tuple(db.units))
        self.assertEqual(db.skills["old"].targets, "ally")

    def test_battle_runs_on_clone_and_keeps_setup_intact(self):
        before = scenario_to_save(self.scenario)
        runs = []
        for _ in range(2):
            clone = clone_scenario(self.db, self.scenario)
            sim = BattleSimulation(clone.player_squad, clone.enemy_squad, self.db, seed=4)
            runs.append(sim.run())
        self.assertEqual(runs[0], runs[1])
        self.assertTrue(any(isinstance(e, SkillUsed) and e.skill_id == "venom_strike" for e in runs[0]))
        self.assertEqual(scenario_to_save(self.scenario), before)


class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.db = Database.load()

    def test_english_is_default_and_needs_no_file(self):
        t = Translator()
        self.assertEqual((t.lang, t("Round {n}", n=3), t("{braces} stay")), (DEFAULT_LANG, "Round 3", "{braces} stay"))
        self.assertEqual(Translator.load("en").texts, {})
        self.assertIn("ru", available_languages())
        with self.assertRaises(ValueError):
            Translator.load("xx")

    def test_translation_keeps_placeholders(self):
        fields = lambda text: sorted({name for _, name, _, _ in string.Formatter().parse(text) if name})
        for lang in available_languages()[1:]:
            for english, translated in Translator.load(lang).texts.items():
                self.assertEqual(fields(english), fields(translated), (lang, english))

    def test_battle_log_in_russian(self):
        ru = Translator.load("ru")
        scenario = build_demo(self.db)
        sim = BattleSimulation(scenario.player_squad, scenario.enemy_squad, self.db, seed=1)
        events = sim.run()
        name = lambda uid: f"{ru(sim.units[uid].name)}({uid})"
        english = [format_event(e, lambda uid: sim.units[uid].label) for e in events]
        russian = [format_event(e, name, ru) for e in events]
        self.assertEqual(english[0], "=== Battle: vanguard vs raiders ===")
        for en_line, ru_line in zip(english, russian):
            self.assertNotEqual(en_line, ru_line)
            # Латиницей остаются только HP, AP, PP и множитель стаков "x2".
            self.assertFalse(set(string.ascii_lowercase) & set(ru_line.lower()) - set("hpax"), ru_line)
        self.assertEqual(format_event(UnitDied(1), name, ru), "  Рыцарь(1) погибает")

    def test_every_reason_and_data_name_is_translated(self):
        ru = Translator.load("ru").texts
        names = [d.name for group in (self.db.units, self.db.skills, self.db.effects, self.db.items, self.db.passives)
                 for d in group.values()]
        ids = [*self.db.skills, *self.db.effects, *self.db.passives, *self.db.items]
        slots = {slot for d in self.db.units.values() for slot in d.slots}
        for key in [*REASON_TEXT.values(), *names, *ids, *slots]:
            self.assertIn(key, ru)


if __name__ == "__main__":
    unittest.main()
