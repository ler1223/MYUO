"""Тесты пассивок-прикрытий: защитник принимает на себя удар, нацеленный на союзника."""
import unittest

from game.combat import Battle as BattleSimulation
from game.definitions import PassiveDefinition
from game.editing import new_passive_data, set_owners, skill_owners
from game.events import AttackMissed, Covered, DamageDealt, EffectApplied, Healed, PassiveTriggered, SkillUsed
from tests.helpers import DB, add_skill, only, plain_db, set_stats, squads, turn_of
from tests.test_combat import part


def add_cover(db, owners=("knight",), **data):
    """Пассивка-прикрытие "cover" для классов owners."""
    db.update("passives", "cover", {"name": "Cover", "action": "cover", "pp_cost": 1, **data})
    set_owners(db, "units", "cover", list(owners), field="passives")


def fight(db, attacker, defenders, skill="attack", seed=1, level=1):
    """Юнит attacker (uid 1) бьёт навыком skill; защищается отряд defenders (uid с 2).

    Возвращает (события хода атакующего, симуляция).
    """
    a, b = squads(db, [(attacker, level, 0, 0)], defenders)
    only(db, a.formation.units[0], skill)
    sim = BattleSimulation(a, b, db, seed=seed)
    return turn_of(sim, 1), sim


def hits(events):
    """Урон от навыков; яд, которым защитники успели отравить атакующего, не считается."""
    return [e for e in events if isinstance(e, DamageDealt) and e.cause != "poison"]


def damaged(events):
    return [e.target for e in hits(events)]


# лучник в переднем ряду (первая цель), рыцарь рядом в том же ряду
ROW = [("archer", 1, 0, 0), ("knight", 1, 0, 1)]
COLUMN = [("archer", 1, 0, 0), ("knight", 1, 1, 0)]
FAR = [("archer", 1, 0, 0), ("knight", 1, 2, 2)]


class CoverTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()

    def test_hit_is_redirected_to_the_protector(self):
        add_cover(self.db, cover_area="row")
        events, sim = fight(self.db, "orc", ROW)
        archer, knight = sim.units[2], sim.units[3]
        self.assertIn(SkillUsed(1, "attack", 2), events)             # целью был лучник
        index = events.index(PassiveTriggered(3, "cover"))
        self.assertEqual(events[index + 1], Covered(3, 2, "attack"))
        self.assertEqual(damaged(events), [3])                       # урон получил только рыцарь
        self.assertEqual(archer.hp, archer.max_hp)
        self.assertLess(knight.hp, knight.max_hp)
        self.assertEqual(knight.pp.current, 0)
        # урон считается по защите рыцаря: 26 - 14 (12 и +20% от iron_will) = 12
        self.assertEqual([e.amount for e in hits(events)], [12])

    def test_zone_is_relative_to_the_protector(self):
        cases = [("row", ROW, True), ("row", COLUMN, False), ("row", FAR, False),
                 ("column", COLUMN, True), ("column", ROW, False), ("column", FAR, False),
                 ("all", ROW, True), ("all", COLUMN, True), ("all", FAR, True)]
        for area, formation, covers in cases:
            db = plain_db()
            add_cover(db, cover_area=area)
            events, _ = fight(db, "orc", formation)
            self.assertEqual(damaged(events), [3] if covers else [2], (area, formation))

    def test_protector_cannot_evade_a_redirected_hit(self):
        set_stats(self.db, "knight", evasion=100)
        add_cover(self.db)
        for seed in range(10):
            events, _ = fight(self.db, "orc", ROW, seed=seed)
            self.assertEqual(damaged(events), [3], seed)
        # сам по себе такой рыцарь от удара уклоняется
        events, _ = fight(self.db, "orc", [("knight", 1, 0, 0)])
        self.assertIsInstance(next(e for e in events if isinstance(e, (DamageDealt, AttackMissed))), AttackMissed)

    def test_attack_can_still_miss_by_its_own_accuracy(self):
        add_cover(self.db)
        add_skill(self.db, "wild", ["orc"], accuracy=0, parts=[part()])
        events, sim = fight(self.db, "orc", ROW, "wild")
        self.assertIn(AttackMissed(1, 3, "wild"), events)
        self.assertEqual(sim.units[3].pp.current, 0)  # PP потрачены: прикрытие сработало

    def test_tag_filter(self):
        cases = [(["physical"], "orc", "attack", True), (["physical"], "mage", "magic_bolt", False),
                 (["magical"], "mage", "magic_bolt", True), ([], "mage", "magic_bolt", True),
                 (["ranged"], "archer", "shot", True), (["ranged"], "orc", "attack", False),
                 (["melee", "magic"], "mage", "fireball", True)]
        for tags, attacker, skill, covers in cases:
            db = plain_db()
            add_cover(db, cover_tags=tags)
            events, _ = fight(db, attacker, ROW, skill)
            self.assertEqual(damaged(events), [3] if covers else [2], (tags, skill))

    def test_skill_area_filter(self):
        for areas, covers in ((["single"], False), (["row", "all"], True), ([], True)):
            db = plain_db()
            add_cover(db, cover_skill_areas=areas, cover_many=True)
            add_skill(db, "cleave", ["orc"], area="row", parts=[part()])
            events, _ = fight(db, "orc", ROW, "cleave")
            self.assertEqual(damaged(events), [3] if covers else [2, 3], areas)

    def test_cover_one_or_all_allies_hit_by_an_area_attack(self):
        row = [("archer", 1, 0, 0), ("mage", 1, 0, 1), ("knight", 1, 0, 2)]
        add_skill(self.db, "cleave", ["orc"], area="row", parts=[part()])
        add_cover(self.db, cover_many=False)
        events, _ = fight(self.db, "orc", row, "cleave")
        self.assertEqual([e for e in events if isinstance(e, Covered)], [Covered(4, 2, "cleave")])
        self.assertEqual(damaged(events), [4, 3])          # рыцарь за лучника (и за себя, одним ударом), маг сам

        add_cover(self.db, cover_many=True)
        events, _ = fight(self.db, "orc", row, "cleave")
        self.assertEqual([e for e in events if isinstance(e, Covered)], [Covered(4, 2, "cleave"), Covered(4, 3, "cleave")])
        self.assertEqual(damaged(events), [4])             # вся атака слилась в один удар по рыцарю

    def test_cover_everyone_from_anywhere(self):
        squad = [("archer", 1, 0, 0), ("mage", 1, 1, 1), ("cleric", 1, 2, 2), ("knight", 1, 2, 0)]
        add_skill(self.db, "storm", ["orc"], area="all", parts=[part(power=0.1)])
        add_cover(self.db, cover_area="all", cover_many=True)
        events, _ = fight(self.db, "orc", squad, "storm", level=9)  # 9 уровень: пережить четверых до своего хода
        self.assertEqual(sum(isinstance(e, Covered) for e in events), 3)
        self.assertEqual(damaged(events), [5])

    def test_multi_hit_skill_spends_pp_once(self):
        add_cover(self.db)
        add_skill(self.db, "triple", ["orc"], hits=3, parts=[part(power=0.5)])
        events, sim = fight(self.db, "orc", ROW, "triple")
        self.assertEqual(damaged(events), [3, 3, 3])
        self.assertEqual(sum(isinstance(e, PassiveTriggered) and e.passive_id == "cover" for e in events), 1)
        self.assertEqual(sim.units[3].pp.current, 0)

    def test_no_pp_no_cover(self):
        add_cover(self.db)
        events, sim = fight(self.db, "orc", ROW, level=9)
        self.assertEqual(damaged(events), [3])
        self.assertEqual(damaged(turn_of(sim, 1)), [2])    # второй удар: PP рыцаря кончились

    def test_first_protector_in_formation_order_covers(self):
        add_cover(self.db)
        events, sim = fight(self.db, "orc", [("archer", 1, 0, 0), ("knight", 1, 0, 1), ("knight", 1, 0, 2)], level=9)
        self.assertEqual(damaged(events), [3])
        self.assertEqual((sim.units[3].pp.current, sim.units[4].pp.current), (0, 1))
        self.assertEqual(damaged(turn_of(sim, 1)), [4])    # затем очередь второго рыцаря

    def test_stunned_protector_does_not_cover(self):
        add_cover(self.db)
        a, b = squads(self.db, [("orc", 1, 0, 0)], ROW)
        only(self.db, a.formation.units[0], "attack")
        b.formation.units[1].add_effect(self.db.effects["stun"])
        # орк ходит последним, оглушение к тому моменту уже спало бы: оглушаем прямо перед его ходом
        sim = BattleSimulation(a, b, self.db, seed=1)
        sim.step(); sim.step()                              # лучник и рыцарь (рыцарь пропускает ход, стан спадает)
        sim.units[3].add_effect(self.db.effects["stun"])
        self.assertEqual(damaged(sim.step()), [2])

    def test_effects_of_the_attack_land_on_the_protector(self):
        add_cover(self.db)
        events, sim = fight(self.db, "archer", ROW, "poison_arrow")
        self.assertIn(EffectApplied(3, "poison", 1, 1), events)
        self.assertFalse(sim.units[2].has_effect("poison"))

    def test_cover_can_also_apply_an_effect_to_the_protector(self):
        add_cover(self.db, effect_id="war_cry")
        events, _ = fight(self.db, "orc", ROW)
        applied = events.index(EffectApplied(3, "war_cry", 1, 3))
        hit = events.index(hits(events)[0])
        self.assertLess(applied, hit)                       # эффект накладывается до удара

    def test_friendly_skills_are_not_intercepted(self):
        add_cover(self.db, cover_area="all")
        a, b = squads(self.db, [("archer", 1, 0, 0), ("knight", 1, 0, 1), ("cleric", 1, 1, 0)], [("goblin", 1, 2, 2)])
        archer, knight, cleric = a.formation.units
        archer.take_damage(20)
        only(self.db, cleric, "heal")
        events = turn_of(BattleSimulation(a, b, self.db, seed=1), cleric.uid)
        self.assertEqual([e.target for e in events if isinstance(e, Healed)], [archer.uid])
        self.assertFalse(any(isinstance(e, Covered) for e in events))

    def test_protector_attacked_directly_spends_nothing(self):
        add_cover(self.db)
        events, sim = fight(self.db, "orc", [("knight", 1, 0, 0), ("archer", 1, 0, 1)])
        self.assertEqual(damaged(events), [2])
        self.assertEqual(sim.units[2].pp.current, 1)
        self.assertFalse(any(isinstance(e, Covered) for e in events))


class PassiveDataTests(unittest.TestCase):
    def test_roundtrip_and_defaults(self):
        db = DB.copy()
        add_cover(db, cover_area="column", cover_many=True, cover_tags=["physical", "melee"], cover_skill_areas=["single"])
        passive = db.passives["cover"]
        self.assertEqual(PassiveDefinition.from_dict("cover", passive.to_dict()), passive)
        self.assertEqual(db.copy().passives["cover"], passive)
        self.assertIsNone(passive.reaction.effect_id)
        self.assertEqual((passive.reaction.event, passive.reaction.action, passive.reaction.area,
                          passive.reaction.cover_many), ("targeted", "cover", "column", True))
        old = db.passives["avenger"]                        # пассивки старого формата читаются как реакции
        self.assertEqual((old.reaction.event, old.reaction.whose, old.reaction.action, old.reaction.effect_id),
                         ("died", "ally", "apply_effect", "war_cry"))

    def test_validation(self):
        db = DB.copy()
        bad = [
            {"name": "x", "action": "effect", "trigger": "UnitDied"},                 # эффект обязателен
            {"name": "x", "action": "cover", "cover_area": "cone"},
            {"name": "x", "action": "cover", "cover_skill_areas": ["cone"]},
            {"name": "x", "action": "cover", "cover_tags": ["no_such_tag"]},
            {"name": "x", "action": "cover", "effect_id": "no_such_effect"},
            {"name": "x", "action": "dance"},
        ]
        for data in bad:
            with self.assertRaises(ValueError, msg=data):
                db.update("passives", "x", data)
            self.assertNotIn("x", db.passives)

    def test_create_assign_and_delete(self):
        db = DB.copy()
        passive_id = db.create("passives", "Bulwark", new_passive_data(db))
        self.assertEqual(db.passives[passive_id].reaction.action, "use_skill")  # по умолчанию контратака
        set_owners(db, "units", passive_id, ["orc"], field="passives")
        set_owners(db, "items", passive_id, ["shield"], field="passives")
        self.assertEqual(skill_owners(db, "units", passive_id, "passives"), ["orc"])
        self.assertIn(passive_id, db.create_unit("knight", 1, equipment=["shield"]).passive_ids)
        db.delete("passives", passive_id)
        self.assertNotIn(passive_id, db.units["orc"].passives)
        self.assertNotIn(passive_id, db.items["shield"].passives)

    def test_deleting_a_tag_cleans_cover_filters(self):
        db = DB.copy()
        add_cover(db, cover_tags=["melee", "physical"])
        db.delete("tags", "melee")
        self.assertEqual(db.passives["cover"].reaction.attack_tags, ("physical",))


if __name__ == "__main__":
    unittest.main()
