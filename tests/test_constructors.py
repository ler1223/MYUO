"""Тесты основы конструкторов: области как данные, размер формации, триггеры эффектов."""
import unittest

from game.areas import AREA_SINGLE, MAX_SPAN, AreaDefinition
from game.battle import BattleSimulation
from game.effects import EffectDefinition
from game.events import BattleEnded, DamageDealt, EffectApplied, EffectExpired, Healed, ResourceGained, UnitDied
from game.save import scenario_from_save, scenario_to_save
from game.scenario import build_demo
from game.squad import Formation, FormationError, FormationSize
from game.world import Army
from tests.helpers import DB, add_skill, only, plain_db, squads, turn_of
from tests.test_combat import part

ADJACENT = {"name": "Adjacent", "cells": [[0, -1], [0, 1], [-1, 0], [1, 0]]}


def add_effect(db, effect_id, **data):
    db.update("effects", effect_id, {"name": effect_id, **data})


def trigger(when, action, **rest):
    return {"when": when, "action": action, **rest}


class AreaTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def test_builtin_areas_when_data_has_no_file(self):
        self.assertEqual(set(DB.areas), {"single", "row", "column", "all"})
        self.assertEqual(DB.areas["single"].cells, {(0, 0)})
        self.assertEqual(len(DB.areas["row"].cells), 2 * MAX_SPAN + 1)
        self.assertEqual(len(DB.areas["all"].cells), (2 * MAX_SPAN + 1) ** 2)

    def test_area_is_offsets_from_the_anchor(self):
        area = AreaDefinition.from_dict("pierce", {"cells": [[0, 0], [1, 0]]})   # цель и клетка за ней
        self.assertTrue(area.covers((0, 1), (0, 1)))
        self.assertTrue(area.covers((0, 1), (1, 1)))
        self.assertFalse(area.covers((0, 1), (2, 1)))
        self.assertFalse(area.covers((1, 1), (0, 1)))                           # перед целью не задевает
        self.assertEqual(AreaDefinition.from_dict("pierce", area.to_dict()), area)
        with self.assertRaises(ValueError):
            AreaDefinition.from_dict("far", {"cells": [[0, MAX_SPAN + 1]]})

    def test_custom_area_in_a_skill(self):
        self.db.update("areas", "pierce", {"name": "Pierce", "cells": [[0, 0], [1, 0]]})
        self.db.update("areas", "cross", {"name": "Cross", "cells": [[0, 0], *ADJACENT["cells"]]})
        enemies = [("goblin", 1, 0, 0), ("goblin", 1, 0, 1), ("goblin", 1, 1, 0), ("goblin", 1, 1, 1), ("goblin", 1, 2, 0)]
        for area, expected in (("pierce", [2, 4]), ("cross", [2, 3, 4]), ("single", [2])):
            add_skill(self.db, "probe", ["knight"], area=area, parts=[part(power=0.1)])
            a, b = squads(self.db, [("knight", 9, 0, 0)], enemies)   # 9 уровень: пережить пятерых гоблинов
            only(self.db, a.formation.units[0], "probe")
            events = turn_of(BattleSimulation(a, b, self.db, seed=1), 1)
            self.assertEqual([e.target for e in events if isinstance(e, DamageDealt)], expected, area)

    def test_unknown_area_is_rejected(self):
        before = self.db.to_dict()
        for section, key, value in (
            ("skills", "attack", dict(before["skills"]["attack"], area="cone")),
            ("passives", "p", {"name": "p", "action": "cover", "cover_area": "cone"}),
            ("effects", "poison", dict(before["effects"]["poison"], triggers=[trigger("expire", "damage", to="allies", area="cone")])),
        ):
            with self.assertRaises(ValueError, msg=section):
                self.db.update(section, key, value)
        self.assertEqual(self.db.to_dict(), before)

    def test_delete_area_falls_back_to_single(self):
        self.db.update("areas", "cross", ADJACENT)
        add_skill(self.db, "probe", [], area="cross", parts=[part()])
        self.db.update("passives", "wall", {"name": "wall", "action": "cover", "cover_area": "cross",
                                            "cover_skill_areas": ["cross", "row"]})
        add_effect(self.db, "aura", triggers=[trigger("turn_start", "heal", amount=1, to="allies", area="cross")])
        self.db.delete("areas", "cross")
        self.assertEqual(self.db.skills["probe"].area, AREA_SINGLE)
        wall = self.db.passives["wall"].reaction
        self.assertEqual((wall.area, wall.skill_areas), (None, ("row",)))   # без области: любой союзник
        self.assertIsNone(self.db.effects["aura"].triggers[0].to_area)
        with self.assertRaises(ValueError):
            self.db.delete("areas", AREA_SINGLE)


class FormationSizeTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def test_default_and_limits(self):
        self.assertEqual(self.db.formation, FormationSize(3, 3, 5))
        self.assertEqual(self.db.to_dict()["config"]["formation"], {"rows": 3, "cols": 3, "max_units": 5})
        for rows, cols, units in ((2, 3, 5), (6, 3, 5), (3, 6, 5), (3, 3, 0), (3, 3, 10), (5, 5, 16)):
            with self.assertRaises(ValueError, msg=(rows, cols, units)):
                self.db.set_formation(rows, cols, units)
        self.assertEqual(self.db.formation, FormationSize(3, 3, 5))
        self.db.set_formation(5, 5, 15)
        self.assertEqual(self.db.copy().formation, FormationSize(5, 5, 15))

    def test_formation_respects_its_size(self):
        formation = Formation(FormationSize(4, 5, 12))
        for uid in range(12):
            formation.place(self.db.create_unit("goblin", uid), uid // 5, uid % 5)
        with self.assertRaises(FormationError):
            formation.place(self.db.create_unit("goblin", 99), 3, 4)   # тринадцатый
        formation.remove(0)
        with self.assertRaises(FormationError):
            formation.place(self.db.create_unit("goblin", 99), 4, 0)   # ряд за пределами поля
        formation.swap((0, 1), (3, 4))
        self.assertEqual(formation.unit_at(3, 4).uid, 1)
        self.assertEqual(len(Formation()._slots), 0)
        self.assertEqual((Formation().rows, Formation().cols, Formation().max_units), (3, 3, 5))

    def test_big_battle_on_a_5x5_field(self):
        self.db.set_formation(5, 5, 15)
        armies = []
        for side, first in (("a", 1), ("b", 101)):
            army = Army(side, side)
            squad = army.create_squad(side, side, self.db.formation)
            for n in range(15):
                unit = army.recruit(self.db.create_unit(("knight", "archer", "mage", "goblin", "orc")[n % 5], first + n))
                army.assign(unit.uid, side, n // 5, n % 5)
            armies.append(squad)
        self.assertEqual(len(armies[0].formation), 15)
        sim = BattleSimulation(armies[0], armies[1], self.db, seed=3)
        events = sim.run()
        self.assertIsInstance(events[-1], BattleEnded)
        self.assertEqual(len(sim.units), 30)

    def test_row_area_reaches_across_a_wide_field(self):
        self.db.set_formation(3, 5, 10)
        add_skill(self.db, "sweep", ["knight"], area="row", parts=[part(power=0.1)])
        left = Army("a", "a")
        right = Army("b", "b")
        a = left.create_squad("a", "a", self.db.formation)
        b = right.create_squad("b", "b", self.db.formation)
        mage = left.recruit(self.db.create_unit("knight", 1, level=9))
        left.assign(1, "a", 0, 0)
        for col in range(5):
            right.recruit(self.db.create_unit("goblin", 10 + col))
            right.assign(10 + col, "b", 0, col)
        only(self.db, mage, "sweep")
        events = turn_of(BattleSimulation(a, b, self.db, seed=1), 1)
        self.assertEqual([e.target for e in events if isinstance(e, DamageDealt)], [10, 11, 12, 13, 14])

    def test_shrinking_the_field_moves_extra_units_to_the_reserve(self):
        self.db.set_formation(5, 5, 8)
        scenario = build_demo(self.db)
        army, squad = scenario.player, scenario.player_squad
        for n, cell in enumerate([(4, 4), (3, 0), (0, 4)]):
            unit = army.recruit(self.db.create_unit("goblin", 60 + n))
            army.assign(unit.uid, squad.id, *cell)
        self.assertEqual(len(squad.formation), 7)
        saved = scenario_to_save(scenario)
        self.db.set_formation(3, 3, 5)
        restored = scenario_from_save(self.db, saved)
        formation = restored.player_squad.formation
        self.assertEqual((formation.rows, formation.cols, len(formation)), (3, 3, 4))
        self.assertEqual(sorted(u.uid for u in restored.player.reserve()), [60, 61, 62])
        self.assertEqual(len(restored.player.units), 7)   # никто не потерялся


class EffectTriggerTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def duel(self, effect_id, on="b"):
        """Рыцарь (uid 1) против орка (uid 2); эффект заранее висит на одном из них."""
        a, b = squads(self.db, [("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        knight, orc = a.formation.units[0], b.formation.units[0]
        carrier, source = (orc, knight) if on == "b" else (knight, orc)
        carrier.add_effect(self.db.effects[effect_id], source=source.uid)
        return BattleSimulation(a, b, self.db, seed=1), knight, orc

    def test_old_periodic_data_becomes_a_turn_start_trigger(self):
        old = EffectDefinition.from_dict("poison", {"name": "Poison", "periodic": [{"kind": "damage", "amount": 4}]})
        reaction = old.triggers[0]
        self.assertEqual((reaction.event, reaction.whose, reaction.action, reaction.amount, reaction.to),
                         ("turn_start", "self", "damage", 4, "owner"))
        self.assertEqual(DB.effects["poison"].triggers, old.triggers)
        self.assertNotIn("periodic", old.to_dict())

    def test_turn_start_damage_and_heal(self):
        add_effect(self.db, "burn", duration=2, triggers=[trigger("turn_start", "damage", amount=5)])
        sim, knight, orc = self.duel("burn")
        events = turn_of(sim, 2)
        self.assertEqual((events[1].amount, events[1].cause, events[1].target), (5, "burn", 2))
        add_effect(self.db, "regen", duration=2, triggers=[trigger("turn_start", "heal", amount=7)])
        sim, knight, orc = self.duel("regen")
        orc.take_damage(20)
        healed = turn_of(sim, 2)[1]
        self.assertEqual((type(healed), healed.amount, healed.cause), (Healed, 7, "regen"))

    def test_amount_scales_with_stacks(self):
        sim, knight, orc = self.duel("poison")
        orc.add_effect(self.db.effects["poison"], source=1)
        orc.add_effect(self.db.effects["poison"], source=1)
        self.assertEqual(turn_of(sim, 2)[1].amount, 12)

    def test_effect_jumps_to_neighbours_when_it_expires(self):
        # Заразная хворь: 1 ход, по истечении перекидывается на союзников в соседних клетках.
        self.db.update("areas", "adjacent", ADJACENT)
        add_effect(self.db, "plague", duration=1, tags=["debuff"], triggers=[
            trigger("turn_start", "damage", amount=3),
            trigger("expire", "apply_effect", effect_id="plague", to="allies", area="adjacent"),
        ])
        a, b = squads(self.db, [("knight", 1, 0, 0)],
                      [("goblin", 1, 0, 0), ("goblin", 1, 0, 1), ("goblin", 1, 0, 2), ("goblin", 1, 2, 2)])
        left, middle, right, far = b.formation.units
        middle.add_effect(self.db.effects["plague"], source=1)
        sim = BattleSimulation(a, b, self.db, seed=1)
        events = turn_of(sim, middle.uid)
        self.assertIn(DamageDealt(1, middle.uid, 3, middle.max_hp - 3, "plague"), events)
        expired = events.index(EffectExpired(middle.uid, "plague"))
        self.assertEqual(events[expired + 1:], [EffectApplied(left.uid, "plague", 1, 1), EffectApplied(right.uid, "plague", 1, 1)])
        self.assertFalse(middle.has_effect("plague"))
        self.assertFalse(far.has_effect("plague"))                  # не сосед
        # На ходу правого соседа хворь возвращается к среднему: зараза гуляет по отряду.
        back = turn_of(sim, right.uid)
        self.assertIn(EffectApplied(middle.uid, "plague", 1, 1), back)

    def test_applied_trigger_and_remove_effect(self):
        add_effect(self.db, "antidote", duration=1, triggers=[
            trigger("applied", "remove_effect", effect_id="poison"),
            trigger("applied", "heal", amount=10),
        ])
        add_skill(self.db, "cure", ["knight"], targets="self", applies=[{"effect_id": "antidote", "to": "self"}])
        sim, knight, orc = self.duel("poison", on="a")
        knight.take_damage(30)
        only(self.db, knight, "cure")
        events = turn_of(sim, 1)
        applied = events.index(EffectApplied(1, "antidote", 1, 1))
        self.assertEqual(events[applied + 1], EffectExpired(1, "poison"))
        self.assertIsInstance(events[applied + 2], Healed)
        self.assertFalse(knight.has_effect("poison"))

    def test_trigger_can_target_the_source(self):
        add_effect(self.db, "leech", duration=2, triggers=[
            trigger("turn_start", "damage", amount=6),
            trigger("turn_start", "heal", amount=6, to="source"),
            trigger("turn_start", "restore_ap", amount=1, to="source"),
        ])
        sim, knight, orc = self.duel("leech")
        knight.take_damage(20)
        sim.step()                                    # рыцарь ходит первым и тратит AP
        events = turn_of(sim, 2)
        self.assertIn(DamageDealt(1, 2, 6, orc.max_hp - 6 - (orc.max_hp - orc.hp - 6), "leech"), events)
        self.assertTrue(any(isinstance(e, Healed) and e.target == 1 and e.amount == 6 for e in events))
        self.assertTrue(any(isinstance(e, ResourceGained) and e.target == 1 and e.resource == "AP" for e in events))

    def test_trigger_on_enemies_and_everyone(self):
        add_effect(self.db, "thorns", duration=3, triggers=[trigger("turn_start", "damage", amount=2, to="enemies")])
        add_effect(self.db, "nova", duration=3, triggers=[trigger("turn_start", "damage", amount=2, to="everyone")])
        for effect_id, expected in (("thorns", [1]), ("nova", [1, 3])):
            a, b = squads(self.db, [("knight", 1, 0, 0)], [("orc", 1, 0, 0), ("goblin", 1, 0, 1)])
            b.formation.units[0].add_effect(self.db.effects[effect_id], source=1)
            events = turn_of(BattleSimulation(a, b, self.db, seed=1), 2)
            hit = [e.target for e in events if isinstance(e, DamageDealt) and e.cause == effect_id]
            self.assertEqual(hit, expected, effect_id)

    def test_trigger_damage_can_kill_and_end_the_battle(self):
        add_effect(self.db, "doom", duration=3, triggers=[trigger("turn_start", "damage", amount=999)])
        sim, knight, orc = self.duel("doom")
        events = sim.run()
        self.assertIn(UnitDied(2), events)
        self.assertEqual(events[-1], BattleEnded("a", "defeat"))
        self.assertEqual(sum(isinstance(e, BattleEnded) for e in events), 1)

    def test_chains_of_effects_stop(self):
        add_effect(self.db, "pong", duration=2)
        add_effect(self.db, "ping", duration=2, triggers=[trigger("applied", "apply_effect", effect_id="pong")])
        add_effect(self.db, "pong", duration=2, triggers=[trigger("applied", "apply_effect", effect_id="ping")])
        add_skill(self.db, "serve", ["knight"], parts=[part(power=0.1)], applies=[{"effect_id": "ping", "to": "target"}])
        a, b = squads(self.db, [("knight", 1, 0, 0)], [("orc", 1, 0, 0)])
        only(self.db, a.formation.units[0], "serve")
        events = turn_of(BattleSimulation(a, b, self.db, seed=1), 1)
        applied = [e for e in events if isinstance(e, EffectApplied) and e.effect_id in ("ping", "pong")]
        self.assertTrue(2 <= len(applied) <= 10, len(applied))      # цепочка обрывается, а не висит вечно

    def test_expire_fires_when_charges_run_out(self):
        add_effect(self.db, "last_gasp", charges=1, attack_mods=[{"power_mult": 2.0}],
                   triggers=[trigger("expire", "heal", amount=5)])
        sim, knight, orc = self.duel("last_gasp", on="a")
        knight.take_damage(20)
        only(self.db, knight, "attack")
        events = turn_of(sim, 1)
        expired = events.index(EffectExpired(1, "last_gasp"))
        self.assertEqual(events[expired + 1], Healed(2, 1, 5, knight.hp, "last_gasp"))

    def test_validation(self):
        for bad in (trigger("sometimes", "damage"), trigger("expire", "explode"), trigger("expire", "damage", to="moon"),
                    trigger("expire", "apply_effect"), trigger("expire", "apply_effect", effect_id="nope")):
            with self.assertRaises(ValueError, msg=bad):
                add_effect(self.db, "bad", triggers=[bad])
            self.assertNotIn("bad", self.db.effects)

    def test_delete_effect_cleans_every_reference(self):
        add_effect(self.db, "spread", triggers=[trigger("expire", "apply_effect", effect_id="war_cry", to="allies")])
        self.db.update("passives", "wall", {"name": "wall", "action": "cover", "effect_id": "war_cry"})
        add_skill(self.db, "shout", ["knight"], targets="self", applies=[{"effect_id": "war_cry", "to": "self"}])
        self.db.delete("effects", "war_cry")
        self.assertEqual(self.db.skills["shout"].applies, ())
        self.assertEqual(self.db.effects["spread"].triggers, ())
        self.assertIsNone(self.db.passives["wall"].reaction.effect_id)  # прикрытие остаётся без эффекта
        self.assertNotIn("avenger", self.db.passives)              # пассивка-эффект без эффекта удалена
        self.assertNotIn("avenger", self.db.units["knight"].passives)
        scenario = build_demo(self.db)
        BattleSimulation(scenario.player_squad, scenario.enemy_squad, self.db, seed=1).run()


if __name__ == "__main__":
    unittest.main()
