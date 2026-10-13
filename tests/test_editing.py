"""Тесты редактирования: тактики, правка справочника (классы, предметы, навыки, теги),
снаряжение, области навыков, отряды, сохранение расстановки, выбор языка."""
import dataclasses
import json
import random
import string
import tempfile
import unittest
from pathlib import Path

from game.battle import BattleSimulation
from game.database import Database
from game.definitions import SkillDefinition
from game.editing import (
    condition_params,
    default_apply,
    default_condition,
    default_rule,
    describe_skill,
    new_item_data,
    new_rule_data,
    new_skill_data,
    new_tag_data,
    new_unit_data,
    param_options,
    set_owners,
    set_tactics,
    skill_owners,
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
    UnitDied,
    format_event,
)
from game.i18n import DEFAULT_LANG, Translator, available_languages
from game.save import SAVE_VERSION, clone_scenario, load_settings, load_setup, save_setup, scenario_from_save, scenario_to_save
from game.scenario import build_demo
from game.squad import Formation, FormationError, Squad
from game.stats import Stat
from game.tactics import CONDITIONS, TacticsSet
from game.unit import UnitState, place_equipment
from game.world import Army
from tests.helpers import DB, add_skill, duel, only, plain_db, rule, squads, turn_of
from tests.test_combat import part


class TacticsEditingTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def test_default_tactics_roundtrip(self):
        for definition in self.db.units.values():
            data = json.loads(json.dumps(definition.tactics.to_list()))
            self.assertEqual(TacticsSet.from_list(data).to_list(), data)
        self.assertEqual(self.db.units["cleric"].tactics.to_list()[0], {
            "skill": "heal", "self_condition": {"type": "always"},
            "condition": {"type": "hp_below", "value": 0.6}, "selector": "weakest",
        })

    def test_every_registered_condition_has_editor_defaults(self):
        for name in CONDITIONS:
            data = default_condition(name, self.db)
            for param, kind in condition_params(name).items():
                self.assertIn(data[param], param_options(kind, self.db))
            for key in ("condition", "self_condition"):
                item = rule("attack", **{key: data})
                self.assertEqual(TacticsSet.from_list([item]).to_list(), [item])
        self.assertEqual(param_options("flag", self.db), ["stunned"])
        self.assertIn("cavalry", param_options("tag", self.db))
        self.assertNotIn("slashing", param_options("tag", self.db))  # только теги юнитов

    def test_skill_decides_the_side_of_the_target(self):
        cleric, knight, goblin = (self.db.create_unit(d, i) for i, d in enumerate(["cleric", "knight", "goblin"], 1))
        knight.take_damage(50)
        rng = random.Random(0)
        tactics = TacticsSet.from_list([rule("heal"), rule("magic_bolt")])
        self.assertEqual(tactics.choose(cleric, [knight, cleric], [goblin], rng, self.db.skills), ("heal", knight))
        self.assertEqual((self.db.skills["heal"].targets, self.db.skills["attack"].targets), ("ally", "enemy"))

    def test_self_condition(self):
        sim, knight, orc = duel(self.db, "knight", "orc", right_level=3)
        set_tactics(self.db, knight, [
            rule("power_strike", self_condition={"type": "hp_below", "value": 0.8}),
            rule("attack"),
        ])
        hp, used = knight.max_hp, []
        for e in sim.run():
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
        only(self.db, knight, "attack")
        self.assertTrue(knight.has_custom_tactics)
        used = [e.skill_id for e in sim.run() if isinstance(e, SkillUsed) and e.user == knight.uid]
        self.assertTrue(used)
        self.assertEqual(set(used), {"attack"})
        self.assertIs(knight.definition.tactics, default)
        self.assertIs(self.db.create_unit("knight", 9).tactics, default)
        knight.reset_tactics()
        self.assertFalse(knight.has_custom_tactics)

    def test_rule_with_unavailable_skill_is_skipped(self):
        sim, knight, orc = duel(self.db, "knight", "orc")
        set_tactics(self.db, knight, [rule("fireball"), rule("attack")])  # fireball не навык рыцаря
        used = {e.skill_id for e in sim.run() if isinstance(e, SkillUsed) and e.user == knight.uid}
        self.assertEqual(used, {"attack"})
        with self.assertRaises(ValueError):
            set_tactics(self.db, knight, [rule("no_such_skill")])

    def test_default_rule_and_skill_users(self):
        knight = self.db.create_unit("knight", 1)
        self.assertEqual(default_rule(knight.skill_ids), rule("attack"))
        self.assertEqual(skill_users("power_strike", [knight]), [knight])
        only(self.db, knight, "attack")
        self.assertEqual(skill_users("power_strike", [knight]), [])


class DatabaseEditingTests(unittest.TestCase):
    def setUp(self):
        self.db = DB.copy()

    def test_data_is_split_into_files_and_roundtrips(self):
        self.assertEqual(sorted(p.stem for p in Path(DB.directory).glob("*.json")),
                         ["config", "effects", "items", "passives", "skills", "tags", "units"])
        with tempfile.TemporaryDirectory() as tmp:
            self.db.save(tmp)
            reloaded = Database.load(tmp)
        self.assertEqual(reloaded.to_dict(), DB.to_dict())
        self.assertEqual(reloaded.skills, DB.skills)
        self.assertEqual(reloaded.rules, DB.rules)

    def test_edit_class_stats_slots_tags(self):
        data = self.db.units["archer"].to_dict()
        data["stats"]["phys_atk"] = 99
        data["growth"]["evasion"] = 2
        data["slots"] = ["bow", "artifact"]
        data["tags"] = ["cavalry", "archer"]
        data["ap_max"] = 6
        self.db.update("units", "archer", data)
        archer = self.db.create_unit("archer", 1, level=3, equipment=["short_bow"])
        self.assertEqual((archer.stat(Stat.PHYS_ATK), archer.stat(Stat.EVASION), archer.ap.max), (107, 19, 6))
        self.assertEqual((archer.state.equipment, archer.tags), (["short_bow", None], {"cavalry", "archer"}))
        self.assertEqual(DB.units["archer"].base_stats[Stat.PHYS_ATK], 20)  # исходный справочник не тронут

    def test_create_and_delete_class(self):
        unit_id = self.db.create("units", "Dark Knight", new_unit_data(self.db))
        self.assertEqual(unit_id, "dark_knight")
        self.assertEqual(self.db.create("units", "Dark Knight", new_unit_data(self.db)), "dark_knight_2")
        unit = self.db.create_unit(unit_id, 1)
        self.assertEqual((unit.name, unit.skill_ids, unit.stat(Stat.CRIT_DAMAGE)), ("Dark Knight", ("attack",), 150))
        self.db.delete("units", "dark_knight_2")
        self.assertNotIn("dark_knight_2", self.db.units)

    def test_create_edit_delete_item(self):
        item_id = self.db.create("items", "Flame Sword", new_item_data(self.db))
        data = self.db.items[item_id].to_dict()
        data.update(slot="light_sword", damage_tags=["fire"], tags=["fire_resistant"], skills=["fireball"],
                    passives=["avenger"], modifiers=[{"stat": "phys_atk", "op": "FLAT", "value": 9},
                                                     {"stat": "crit_rate", "op": "FLAT", "value": 20}])
        self.db.update("items", item_id, data)
        knight = self.db.create_unit("knight", 1, equipment=[item_id])
        self.assertEqual((knight.stat(Stat.PHYS_ATK), knight.stat(Stat.CRIT_RATE)), (31, 25))
        self.assertEqual(knight.weapon_damage_tags, ("fire",))
        self.assertIn("fire_resistant", knight.tags)
        self.assertIn("fireball", knight.skill_ids)
        self.assertIn("avenger", knight.passive_ids)
        self.db.delete("items", item_id)
        self.assertNotIn(item_id, self.db.items)

    def test_create_skill_and_assign_owners(self):
        skill_id = self.db.create("skills", "Whirlwind", new_skill_data())
        data = self.db.skills[skill_id].to_dict()
        data.update(area="row", tags=["melee"], hits=2)
        self.db.update("skills", skill_id, data)
        set_owners(self.db, "units", skill_id, ["knight", "orc"])
        set_owners(self.db, "items", skill_id, ["war_axe"])
        self.assertEqual(skill_owners(self.db, "units", skill_id), ["knight", "orc"])
        self.assertEqual(skill_owners(self.db, "items", skill_id), ["war_axe"])
        self.assertIn(skill_id, self.db.create_unit("knight", 1).skill_ids)
        self.assertNotIn(skill_id, self.db.create_unit("goblin", 2).skill_ids)
        self.assertIn(skill_id, self.db.create_unit("goblin", 3, equipment=["rusty_dagger"]).skill_ids
                      + self.db.create_unit("orc", 4, equipment=["war_axe"]).skill_ids)
        set_owners(self.db, "units", skill_id, ["orc"])
        self.assertEqual(skill_owners(self.db, "units", skill_id), ["orc"])
        self.assertIn("x2", describe_skill(self.db.skills[skill_id], self.db))

    def test_delete_skill_cleans_every_reference(self):
        self.db.delete("skills", "power_strike")
        for definition in self.db.units.values():
            self.assertNotIn("power_strike", definition.skills)
            self.assertNotIn("power_strike", [r.skill_id for r in definition.tactics.rules])
        self.assertEqual([r.skill_id for r in self.db.units["knight"].tactics.rules], ["attack"])
        scenario = build_demo(self.db)  # демо по-прежнему собирается и играется
        BattleSimulation(scenario.player_squad, scenario.enemy_squad, self.db, seed=1).run()

    def test_delete_tag_cleans_every_reference(self):
        self.db.delete("tags", "cavalry")
        self.assertEqual(self.db.units["rider"].tags, ())
        self.assertEqual(self.db.skills["lance_charge"].bonus_vs, ())
        self.assertFalse(any("cavalry" in r.tags() for r in self.db.rules))
        self.assertEqual(len(self.db.rules), len(DB.rules) - 1)
        self.db.delete("tags", "slashing")
        self.assertEqual(self.db.items["iron_sword"].damage_tags, ())
        self.assertEqual(self.db.effects["wind_blade"].attack_mods[0].add_tags, ())

    def test_tags_and_rules_editing(self):
        tag_id = self.db.create("tags", "Undead", new_tag_data())
        self.assertEqual((self.db.tags[tag_id].kind, self.db.tags[tag_id].unblockable), ("unit", False))
        rules = [r.to_dict() for r in self.db.rules] + [dict(new_rule_data(), attack=["light"], target=[tag_id], damage=2.0)]
        self.db.set_rules(rules)
        self.assertEqual(self.db.rules[-1].damage, 2.0)
        with self.assertRaises(ValueError):
            self.db.set_rules([{"attack": ["no_such_tag"]}])
        self.assertEqual(len(self.db.rules), len(rules))  # неудачная правка ничего не меняет

    def test_invalid_edit_is_rejected_and_changes_nothing(self):
        before = self.db.to_dict()
        bad = [
            ("units", "knight", dict(before["units"]["knight"], skills=["no_such_skill"])),
            ("units", "knight", dict(before["units"]["knight"], slots=["no_such_slot"])),
            ("units", "knight", dict(before["units"]["knight"], tags=["no_such_tag"])),
            ("items", "shield", dict(before["items"]["shield"], slot="no_such_slot")),
            ("skills", "attack", dict(before["skills"]["attack"], area="cone")),
            ("skills", "attack", dict(before["skills"]["attack"], hits=0)),
            ("skills", "attack", dict(before["skills"]["attack"], applies=[{"effect_id": "nope"}])),
            ("tags", "melee", {"name": "Melee", "kind": "weird"}),
        ]
        for section, key, value in bad:
            with self.assertRaises((ValueError, KeyError), msg=(section, value)):
                self.db.update(section, key, value)
            self.assertEqual(self.db.to_dict(), before)

    def test_existing_units_follow_class_edit_after_rebuild(self):
        scenario = build_demo(self.db)
        data = self.db.units["knight"].to_dict()
        data["stats"]["hp"] = 200
        data["slots"] = ["light_sword"]  # слота щита больше нет
        self.db.update("units", "knight", data)
        rebuilt = clone_scenario(self.db, scenario)
        knight = rebuilt.player.units[1]
        self.assertEqual(knight.max_hp, 216)
        self.assertEqual(knight.state.equipment, ["iron_sword"])  # щит снят: слот пропал

    def test_slugify(self):
        self.assertEqual(slugify("  Fire  Ball #2 "), "fire_ball_2")


class EquipmentTests(unittest.TestCase):
    def setUp(self):
        self.db = DB.copy()

    def test_every_class_has_slots_from_the_fixed_list(self):
        for definition in self.db.units.values():
            self.assertTrue(definition.slots, definition.id)
            self.assertLessEqual(set(definition.slots), set(self.db.slot_types))
            unit = self.db.create_unit(definition.id, 1)
            self.assertEqual(unit.state.equipment, [None] * len(definition.slots))
        self.assertEqual(self.db.units["archer"].slots, ("bow", "light_armor", "artifact", "artifact"))
        self.assertEqual(self.db.units["knight"].slots, ("light_sword", "light_shield", "medium_armor", "artifact"))

    def test_every_weapon_slot_has_a_starter_item_with_damage_type(self):
        weapon_slots = {"light_sword", "bow", "staff", "dagger", "heavy_weapon", "lance"}
        typed = {item.slot for item in self.db.items.values() if item.damage_tags}
        self.assertEqual(typed, weapon_slots)

    def test_items_go_to_matching_slots(self):
        knight = self.db.create_unit("knight", 1, equipment=["shield", "iron_sword"])
        self.assertEqual(knight.state.equipment, ["iron_sword", "shield", None, None])
        with self.assertRaises(ValueError):
            self.db.create_unit("archer", 2, equipment=["iron_sword"])   # у лучника нет слота меча
        with self.assertRaises(ValueError):
            self.db.create_unit("knight", 3, equipment=["shield", "shield"])  # слот щита один
        with self.assertRaises(ValueError):
            self.db.create_unit("knight", 4, equipment=["excalibur"])

    def test_equip_and_unequip(self):
        knight = self.db.create_unit("knight", 1)
        atk = knight.stat(Stat.PHYS_ATK)
        knight.equip(0, "iron_sword")
        self.assertEqual((knight.stat(Stat.PHYS_ATK), knight.weapon_damage_tags), (atk + 5, ("slashing",)))
        with self.assertRaises(ValueError):
            knight.equip(1, "iron_sword")  # меч в слот щита
        with self.assertRaises(ValueError):
            knight.equip(0, "excalibur")
        self.assertEqual(knight.unequip(0), "iron_sword")
        self.assertEqual((knight.stat(Stat.PHYS_ATK), knight.weapon_damage_tags), (atk, ()))

    def test_two_slots_of_one_type_and_lenient_placing(self):
        slots = self.db.units["archer"].slots
        self.assertEqual(place_equipment(slots, self.db.items, ["fire_charm", "fire_charm"]),
                         [None, None, "fire_charm", "fire_charm"])
        with self.assertRaises(ValueError):
            place_equipment(slots, self.db.items, ["fire_charm"] * 3)
        self.assertEqual(place_equipment(slots, self.db.items, ["fire_charm"] * 3 + ["gone", "iron_sword"], strict=False),
                         [None, None, "fire_charm", "fire_charm"])

    def test_state_with_slots_is_json_serializable(self):
        knight = self.db.create_unit("knight", 1, equipment=["iron_sword"])
        data = json.loads(json.dumps(dataclasses.asdict(knight.state)))
        self.assertEqual(data["equipment"], ["iron_sword", None, None, None])
        clone = self.db.restore_unit(UnitState(**data))
        self.assertEqual(clone.stat(Stat.PHYS_ATK), knight.stat(Stat.PHYS_ATK))

    def test_item_grants_active_skill_and_passive_in_battle(self):
        db = plain_db()
        data = db.items["short_bow"].to_dict()
        db.update("items", "short_bow", dict(data, skills=["fireball"], passives=["avenger"]))
        a, b = squads(db, [("goblin", 1, 0, 0), ("archer", 1, 1, 0)], [("knight", 9, 0, 0)])
        archer = a.formation.units[1]
        self.assertNotIn("fireball", archer.skill_ids)
        archer.equip(0, "short_bow")
        self.assertIn("avenger", archer.passive_ids)
        only(db, archer, "fireball")
        events = BattleSimulation(a, b, db, seed=1).run()
        self.assertIn(SkillUsed(archer.uid, "fireball", 3), events)
        self.assertIn(UnitDied(1), events)  # гоблин гибнет от рыцаря 9 уровня
        self.assertIn(PassiveTriggered(archer.uid, "avenger"), events)
        archer.unequip(0)
        self.assertNotIn("fireball", archer.skill_ids)
        self.assertNotIn("avenger", archer.passive_ids)


class SkillAreaTests(unittest.TestCase):
    ENEMIES = [("goblin", 1, 0, 0), ("goblin", 1, 0, 1), ("goblin", 1, 1, 0), ("goblin", 1, 2, 1)]  # uid 2..5

    def setUp(self):
        self.db = plain_db()

    def hit_targets(self, area):
        add_skill(self.db, "wave", ["mage"], area=area, parts=[part("magical", power=0.1)])
        a, b = squads(self.db, [("mage", 9, 0, 0)], self.ENEMIES)  # 9 уровень, чтобы пережить гоблинов
        only(self.db, a.formation.units[0], "wave")
        events = turn_of(BattleSimulation(a, b, self.db, seed=1), 1)
        self.assertEqual([e for e in events if isinstance(e, SkillUsed)], [SkillUsed(1, "wave", 2)])
        return [e.target for e in events if isinstance(e, DamageDealt)]

    def test_registered_areas(self):
        self.assertEqual(set(DB.areas), {"single", "row", "column", "all"})

    def test_single(self):
        self.assertEqual(self.hit_targets("single"), [2])

    def test_row(self):
        self.assertEqual(self.hit_targets("row"), [2, 3])

    def test_column(self):
        self.assertEqual(self.hit_targets("column"), [2, 4])

    def test_all(self):
        self.assertEqual(self.hit_targets("all"), [2, 3, 4, 5])

    def test_area_heal_and_effects_reach_every_ally_in_area(self):
        add_skill(self.db, "mass_heal", ["cleric"], targets="ally", area="all",
                  parts=[part("magical", kind="heal")], applies=[{"effect_id": "war_cry", "to": "target"}])
        a, b = squads(self.db, [("knight", 1, 0, 0), ("cleric", 1, 1, 0), ("archer", 1, 1, 1)], [("goblin", 1, 0, 0)])
        cleric = a.formation.units[1]
        only(self.db, cleric, "mass_heal")
        events = turn_of(BattleSimulation(a, b, self.db, seed=1), cleric.uid)
        self.assertEqual([e.target for e in events if isinstance(e, Healed)], [1, 2, 3])
        self.assertEqual([e.target for e in events if isinstance(e, EffectApplied)], [1, 2, 3])

    def test_area_kill_ends_battle_once(self):
        add_skill(self.db, "meteor", ["mage"], area="all", parts=[part("magical", power=5)])
        a, b = squads(self.db, [("mage", 9, 0, 0)], self.ENEMIES)
        only(self.db, a.formation.units[0], "meteor")
        events = BattleSimulation(a, b, self.db, seed=1).run()
        self.assertEqual([e for e in events if isinstance(e, UnitDied)], [UnitDied(u) for u in (2, 3, 4, 5)])
        self.assertEqual(events[-1], BattleEnded("a", END_DEFEAT))
        self.assertEqual(sum(isinstance(e, BattleEnded) for e in events), 1)


class SkillEffectTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def test_builtin_skills_roundtrip(self):
        self.assertEqual([a.effect_id for a in self.db.skills["poison_arrow"].applies], ["poison"])
        for skill in self.db.skills.values():
            self.assertEqual(SkillDefinition.from_dict(skill.id, json.loads(json.dumps(skill.to_dict()))), skill)

    def test_skill_with_many_effects(self):
        applies = [default_apply(self.db, "poison")] * 4 + [default_apply(self.db, "war_cry")]
        self.assertEqual([a["to"] for a in applies], ["target"] * 4 + ["self"])
        add_skill(self.db, "toxic_shout", ["knight"], ap_cost=0, parts=[part(power=0.5)], applies=applies)
        self.assertIn("War Cry -> self", describe_skill(self.db.skills["toxic_shout"], self.db))

        sim, knight, orc = duel(self.db, "knight", "orc")
        only(self.db, knight, "toxic_shout")
        atk_before = knight.stat(Stat.PHYS_ATK)
        events = turn_of(sim, knight.uid)
        applied = [e for e in events if isinstance(e, EffectApplied)]
        # 4-й яд упирается в max_stacks и только обновляет длительность.
        self.assertEqual([(e.target, e.effect_id, e.stacks) for e in applied],
                         [(orc.uid, "poison", n) for n in (1, 2, 3, 3)] + [(knight.uid, "war_cry", 1)])
        self.assertEqual(knight.stat(Stat.PHYS_ATK), round(atk_before * 1.3))
        # Бафф, наложенный в свой ход, в этот же ход не убывает.
        self.assertEqual(next(e for e in knight.effects if e.definition.id == "war_cry").remaining, 3)
        self.assertNotIn(EffectExpired(knight.uid, "war_cry"), events)

    def test_apply_condition(self):
        add_skill(self.db, "finisher", ["knight"], ap_cost=0, parts=[part()],
                  applies=[dict(default_apply(self.db, "stun"), condition={"type": "hp_below", "value": 0.5})])
        sim, knight, orc = duel(self.db, "knight", "orc", right_level=3)
        only(self.db, knight, "finisher")
        events = sim.run()
        stun = next((e for e in events if isinstance(e, EffectApplied) and e.effect_id == "stun"), None)
        self.assertIsNotNone(stun, "stun was never applied")
        index = events.index(stun)
        self.assertLess(events[index - 1].hp_left, orc.max_hp * 0.5)
        early_hits = [e for e in events[:index - 1] if isinstance(e, DamageDealt) and e.cause == "finisher"]
        self.assertTrue(early_hits)
        self.assertTrue(all(e.hp_left >= orc.max_hp * 0.5 for e in early_hits))

    def test_support_skill_on_self(self):
        add_skill(self.db, "rally", ["knight"], targets="self", applies=[default_apply(self.db, "war_cry")])
        sim, knight, orc = duel(self.db, "knight", "orc")
        only(self.db, knight, "rally")
        events = sim.run()
        rallies = [e for e in events if isinstance(e, SkillUsed) and e.user == knight.uid]
        self.assertTrue(rallies)
        self.assertEqual(set(rallies), {SkillUsed(knight.uid, "rally", knight.uid)})
        self.assertFalse(any(isinstance(e, (DamageDealt, Healed)) and e.source == knight.uid for e in events))
        self.assertEqual(events[-1], BattleEnded("b", END_EXHAUSTED))

    def test_ap_and_pp_restore(self):
        add_skill(self.db, "second_wind", ["knight"], targets="self", ap_cost=1, ap_restore=2, pp_restore=1)
        sim, knight, goblin = duel(self.db, "knight", "goblin")
        only(self.db, knight, "second_wind")
        sim.step()               # гоблин быстрее и ходит первым
        knight.pp.spend(1)       # как будто пассивка уже сработала
        events = turn_of(sim, knight.uid)
        # 4 AP - 1 за навык + 2 восстановлено, но не выше максимума.
        self.assertIn(ResourceGained(1, 1, "AP", 1, 4, "second_wind"), events)
        self.assertIn(ResourceGained(1, 1, "PP", 1, 1, "second_wind"), events)
        self.assertEqual((knight.ap.current, knight.pp.current), (4, 1))
        self.assertIn("+2 AP", describe_skill(self.db.skills["second_wind"], self.db))

    def test_effects_on_killed_target_are_skipped(self):
        add_skill(self.db, "overkill", ["knight"], ap_cost=0, parts=[part(power=5)],
                  applies=[default_apply(self.db, "poison"), default_apply(self.db, "war_cry")])
        sim, knight, goblin = duel(self.db, "knight", "goblin", left_level=5)
        only(self.db, knight, "overkill")
        events = sim.run()
        self.assertIn(UnitDied(goblin.uid), events)
        self.assertFalse(any(isinstance(e, EffectApplied) and e.target == goblin.uid for e in events))
        self.assertIn(EffectApplied(knight.uid, "war_cry", 1, knight.uid), events)
        self.assertEqual(events[-1], BattleEnded("a", END_DEFEAT))


class SquadEditingTests(unittest.TestCase):
    def setUp(self):
        self.db = DB
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
        self.db = DB.copy()
        self.scenario = build_demo(self.db)
        knight = self.scenario.player_squad.formation.units[0]
        set_tactics(self.db, knight, [rule("power_strike", self_condition={"type": "hp_below", "value": 0.9}),
                                      rule("attack")])
        self.scenario.player.recruit(self.db.create_unit("goblin", 50, equipment=["rusty_dagger"]))  # резерв
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

    def test_file_roundtrip_with_settings_and_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "setup.json"
            save_setup(path, self.db, self.scenario, {"language": "ru"})
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(set(saved), {"version", "settings", "scenario"})  # данных игры в сохранении нет
            self.assertEqual(load_settings(path), {"language": "ru"})
            self.assertEqual(scenario_to_save(load_setup(path, self.db)), scenario_to_save(self.scenario))
            saved["version"] = SAVE_VERSION - 1
            path.write_text(json.dumps(saved), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_setup(path, self.db)

    def test_setup_survives_deleted_class_item_and_skill(self):
        data = scenario_to_save(self.scenario)
        self.db.delete("units", "archer")
        self.db.delete("items", "iron_sword")
        self.db.delete("skills", "power_strike")
        restored = scenario_from_save(self.db, data)
        self.assertNotIn(2, restored.player.units)                      # лучник исчез вместе с классом
        self.assertEqual(restored.player_squad.leader_uid, 1)           # лидерство перешло к оставшемуся
        knight = restored.player.units[1]
        self.assertEqual(knight.state.equipment, [None, "shield", None, None])
        self.assertEqual([r.skill_id for r in knight.tactics.rules], ["attack"])
        sim = BattleSimulation(restored.player_squad, restored.enemy_squad, self.db, seed=1)
        self.assertIsInstance(sim.run()[-1], BattleEnded)

    def test_battle_runs_on_clone_and_keeps_setup_intact(self):
        before = scenario_to_save(self.scenario)
        runs = []
        for _ in range(2):
            clone = clone_scenario(self.db, self.scenario)
            runs.append(BattleSimulation(clone.player_squad, clone.enemy_squad, self.db, seed=4).run())
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(scenario_to_save(self.scenario), before)


class LanguageTests(unittest.TestCase):
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
        for seed in range(1, 6):
            scenario = build_demo(DB)
            sim = BattleSimulation(scenario.player_squad, scenario.enemy_squad, DB, seed=seed)
            events = sim.run()
            name = lambda uid: f"{ru(sim.units[uid].name)}({uid})"
            english = [format_event(e, lambda uid: sim.units[uid].label) for e in events]
            russian = [format_event(e, name, ru) for e in events]
            self.assertEqual(english[0], "=== Battle: vanguard vs raiders ===")
            for en_line, ru_line in zip(english, russian):
                self.assertNotEqual(en_line, ru_line)
                # Латиницей остаются только HP, AP, PP и множитель стаков "x2".
                self.assertFalse(set(string.ascii_lowercase) & set(ru_line.lower()) - set("hpax"), ru_line)

    def test_every_reason_and_data_name_is_translated(self):
        ru = Translator.load("ru").texts
        groups = (DB.units, DB.skills, DB.effects, DB.items, DB.passives, DB.tags)
        names = [d.name for group in groups for d in group.values()]
        ids = [key for group in groups[1:] for key in group]
        stats = [s.value for s in Stat]
        for key in [*REASON_TEXT.values(), *names, *ids, *DB.slot_types, *stats, "crit", "guarded", "physical",
                    "magical", "pure"]:
            self.assertIn(key, ru)


if __name__ == "__main__":
    unittest.main()
