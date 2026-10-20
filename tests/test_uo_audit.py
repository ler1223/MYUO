"""Данные UO против каталога и надёжность: числа навыков сходятся с игрой, каждый навык и каждая пассивка
проигрываются в бою без ошибок."""
import os
import sys
import unittest
from pathlib import Path

from game.combat import Battle
from game.database import Database
from game.editing import set_owners
from game.events import PassiveTriggered, SkillUsed
from game.squad import Squad

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import uo_audit_skills  # noqa: E402

REAL = Database.load()
OTHERS = (("knight", 0, 1), ("cleric", 1, 0), ("gryphon_knight", 1, 1))
FOES = (("fighter", 0, 0), ("shaman", 0, 1), ("hunter", 1, 0), ("rogue", 1, 1))


def squads(db, owner, extra=OTHERS):
    out, uid = [], 1
    for sid, roster in (("a", ((owner, 0, 0), *extra)), ("b", FOES)):
        squad = Squad(sid, sid.upper())
        for class_id, row, col in roster:
            squad.formation.place(db.create_unit(class_id, uid, 5), row, col)
            uid += 1
        out.append(squad)
    return out


def isolated(db):
    """Бойцы без своих пассивок и с большим запасом PP: проверяется только испытуемый навык."""
    for unit_id in ("lord", "knight", "cleric", "gryphon_knight", "fighter", "shaman", "hunter", "rogue"):
        data = db.units[unit_id].to_dict()
        data["passives"] = []
        data["pp_max"] = 9
        data["ap_max"] = 3
        db.update("units", unit_id, data)


class AuditTests(unittest.TestCase):
    def test_skill_numbers_match_the_game(self):
        self.assertEqual(uo_audit_skills.audit(), [])


class EverythingRunsTests(unittest.TestCase):
    def test_every_active_skill_runs_in_battle(self):
        failures = []
        db = REAL.copy()
        isolated(db)
        base = db.units["lord"].to_dict()
        for skill_id in REAL.skills:
            data = dict(base)
            data["tactics"] = [{"skill": skill_id, "self_condition": {"type": "always"},
                                "condition": {"type": "always"}, "selector": "frontmost"}]
            data["skills"] = [*base["skills"], skill_id]
            db.update("units", "lord", data)
            for seed in (1, 2):
                try:
                    a, b = squads(db, "lord")
                    sim = Battle(a, b, db, seed=seed, time_of_day="night" if seed == 1 else "day")
                    sim.run()
                except Exception as error:                       # noqa: BLE001
                    failures.append((skill_id, seed, f"{type(error).__name__}: {error}"))
                    break
        self.assertEqual(failures, [])

    def test_every_passive_runs_in_battle(self):
        failures = []
        db = REAL.copy()
        isolated(db)
        for passive_id in REAL.passives:
            set_owners(db, "units", passive_id, ["lord"], field="passives")
            for seed in (1, 2, 3):
                try:
                    a, b = squads(db, "lord")
                    Battle(a, b, db, seed=seed, time_of_day="night" if seed % 2 else "day").run()
                except Exception as error:                       # noqa: BLE001
                    failures.append((passive_id, seed, f"{type(error).__name__}: {error}"))
                    break
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
