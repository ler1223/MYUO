"""Тип навыка для значка (атака, поддержка, лечение, помеха) выводится из самого навыка и сходится с UO."""
import json
import unittest
from pathlib import Path

from game.database import Database
from game.skill_kinds import KINDS, passive_kind, skill_kind

ROOT = Path(__file__).resolve().parent.parent
WIKI = {"Attack": "attack", "Support": "support", "Healing": "healing", "Sabotage": "sabotage"}


class SkillKindTests(unittest.TestCase):
    def setUp(self):
        self.db = Database.load()

    def test_kinds_agree_with_the_uo_wiki(self):
        reference = json.loads((ROOT / "docs" / "uo" / "classes.json").read_text(encoding="utf-8"))["skills"]
        same = total = 0
        for section, kind_of in ((self.db.skills, skill_kind), (self.db.passives, passive_kind)):
            for key, definition in section.items():
                if section is self.db.skills and definition.is_passive:
                    continue                      # пассивки считаются во втором проходе (по действию реакции)
                wiki = WIKI.get(reference.get(definition.name, {}).get("type"))
                if wiki:
                    total += 1
                    same += kind_of(self.db, key) == wiki
        self.assertGreater(total, 150)
        self.assertGreaterEqual(same / total, 0.9)

    def test_every_skill_and_passive_gets_a_kind(self):
        for key in self.db.skills:
            self.assertIn(skill_kind(self.db, key), KINDS, key)
        for key in self.db.passives:
            self.assertIn(passive_kind(self.db, key), KINDS, key)
        self.assertEqual(skill_kind(self.db, "no_such_skill"), "support")


if __name__ == "__main__":
    unittest.main()
