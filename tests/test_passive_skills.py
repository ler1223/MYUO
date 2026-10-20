"""Пассивка как навык (docs/uo/ABILITIES_DESIGN.md, шаг 3): данные, перевод старого вида, правка, удаление."""
import copy
import unittest

from game.database import Database
from game.definitions import SkillDefinition
from tests.helpers import DB, plain_db

COUNTER = {"name": "Counter", "pp_cost": 1, "reaction": {
    "event": "skill_used", "whose": "enemy", "action": "use_skill", "skill_id": "counter_strike", "to": "actor"}}
CHEER = {"name": "Cheer", "pp_cost": 1, "reaction": {
    "event": "battle_start", "whose": "self", "action": "restore_ap", "amount": 1, "to": "owner",
    "then": [{"action": "heal", "amount": 10, "percent": True, "to": "owner"}]}}


def with_passives():
    db = plain_db()
    db.update("skills", "counter_strike", {"name": "Counter", "ap_cost": 1, "tags": ["melee"], "parts": [
        {"kind": "damage", "category": "physical", "power": 1.5, "scaling": [{"stat": "phys_atk", "coef": 1.0}]}]})
    db.update("passives", "counter", COUNTER)
    db.update("passives", "cheer", CHEER)
    return db


class PassiveSkillTests(unittest.TestCase):
    def test_old_description_becomes_a_skill_and_the_response_skill_is_absorbed(self):
        db = with_passives()
        counter = db.skills["counter"]
        self.assertTrue(counter.is_passive and counter.body)
        self.assertEqual((counter.ap_cost, counter.pp_cost, counter.targets), (0, 1, "enemy"))
        self.assertEqual(counter.trigger.event, "skill_used")
        self.assertEqual((counter.target, counter.response), ("attacker", "counter"))
        self.assertNotIn("counter_strike", db.skills)                       # влит в пассивку
        self.assertEqual(counter.parts[0].power, 1.5)

    def test_view_gives_the_reaction_the_engine_runs(self):
        db = with_passives()
        reaction = db.passives["counter"].reaction
        self.assertEqual((reaction.action, reaction.skill_id, reaction.to), ("use_skill", "counter", "actor"))
        cheer = db.passives["cheer"].reaction
        self.assertEqual((cheer.action, cheer.amount, cheer.to), ("restore_ap", 1, "owner"))
        self.assertEqual([(s.action, s.amount, s.percent) for s in cheer.then], [("heal", 10, True)])

    def test_steps_passive_round_trips_through_the_database(self):
        db = with_passives()
        again = Database(copy.deepcopy(db.to_dict()))
        self.assertEqual(again.skills["cheer"], db.skills["cheer"])
        self.assertEqual(again.skills["counter"], db.skills["counter"])
        self.assertNotIn("passives", db.to_dict())
        self.assertEqual(SkillDefinition.from_dict("cheer", db.skills["cheer"].to_dict()), db.skills["cheer"])

    def test_old_data_with_a_passives_section_is_still_read(self):
        data = copy.deepcopy(plain_db().to_dict())
        data["passives"] = {"cheer": CHEER}
        db = Database(data)
        self.assertTrue(db.skills["cheer"].is_passive)
        self.assertIn("cheer", db.passives)

    def test_resaving_a_passive_in_the_old_editor_keeps_its_body(self):
        db = with_passives()
        view = db.passives["counter"].to_dict()
        view["pp_cost"] = 2
        db.update("passives", "counter", view)
        self.assertTrue(db.skills["counter"].body)
        self.assertEqual(db.skills["counter"].pp_cost, 2)
        self.assertEqual(db.skills["counter"].parts[0].power, 1.5)

    def test_active_skill_cannot_have_a_trigger_and_passive_needs_one(self):
        data = DB.skills["attack"].to_dict()
        with self.assertRaises(ValueError):
            SkillDefinition.from_dict("x", dict(data, trigger={"event": "attacked"}))
        with self.assertRaises(ValueError):
            SkillDefinition.from_dict("x", dict(data, kind="passive"))

    def test_deleting_a_passive_removes_it_from_owners_and_tactics(self):
        db = with_passives()
        from game.editing import set_owners
        set_owners(db, "units", "cheer", ["knight"], field="passives")
        self.assertIn("cheer", db.units["knight"].passives)
        db.delete("passives", "cheer")
        self.assertNotIn("cheer", db.skills)
        self.assertNotIn("cheer", db.units["knight"].passives)

    def test_deleting_an_effect_drops_steps_that_use_it(self):
        db = with_passives()
        db.update("effects", "fx", {"name": "fx"})
        db.update("passives", "buff", {"name": "Buff", "pp_cost": 1, "reaction": {
            "event": "battle_start", "action": "apply_effect", "effect_id": "fx", "to": "owner"}})
        self.assertIn("buff", db.skills)
        db.delete("effects", "fx")
        self.assertNotIn("buff", db.skills)                                 # делать нечего — пассивка исчезла


if __name__ == "__main__":
    unittest.main()
