"""Защитные навыки UO из data/: стена, стена магии, оплот, тёмная броня, мистический щит, сопротивление ряда,
воскрешение. Навык и его эффекты берутся из data/ и добавляются в замороженную базу тестов."""
import unittest

from game.combat import Battle
from game.combat.record import ACTIVE, Act
from game.database import Database
from game.events import DamageDealt
from game.stats import Stat
from tests.helpers import add_skill, plain_db, set_stats, squads

REAL = Database.load()


def install(db, *skill_ids, owners=()):
    """Переносит навыки из data/ (и всё, на что они ссылаются) в базу теста."""
    from game.editing import set_owners
    for skill_id in skill_ids:
        skill = REAL.skills[skill_id]
        for apply in skill.applies:
            if apply.effect_id not in db.effects:
                db.update("effects", apply.effect_id, REAL.effects[apply.effect_id].to_dict())
        db.update("skills", skill_id, skill.to_dict())
        set_owners(db, "units", skill_id, list(owners))


def setup(left, right):
    db = plain_db()
    install(db, "wall", "magick_wall", "bulwark", "dark_armor", "mystic_shield", "row_resistance", "resurrection",
            owners=["knight", "cleric"])
    add_skill(db, "chop", ["goblin"], ap_cost=1, tags=["melee"],
              parts=[{"kind": "damage", "category": "physical", "power": 1.0,
                      "scaling": [{"stat": "phys_atk", "coef": 1.0}]}])
    add_skill(db, "zap", ["goblin"], ap_cost=1, tags=["magic"],
              parts=[{"kind": "damage", "category": "magical", "power": 1.0,
                      "scaling": [{"stat": "phys_atk", "coef": 1.0}]}])
    set_stats(db, "goblin", phys_atk=60)
    set_stats(db, "knight", hp=500, phys_def=0, mag_def=0, guard_rate=0, evasion=0)
    a, b = squads(db, left, right)
    return db, Battle(a, b, db, seed=1), a, b


def cast(sim, db, user, skill_id, target):
    act = Act(ACTIVE, user.uid, skill_id, target=target.uid)
    sim._resolve(user, db.skills[skill_id], target, act, root=True)
    return [e.amount for e in act.events if isinstance(e, DamageDealt)]


class WallTests(unittest.TestCase):
    def test_wall_negates_exactly_one_physical_hit(self):
        db, sim, a, b = setup([("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        knight, goblin = a.formation.units[0], b.formation.units[0]
        cast(sim, db, knight, "wall", knight)
        self.assertEqual(cast(sim, db, goblin, "chop", knight), [0])
        self.assertGreater(cast(sim, db, goblin, "chop", knight)[0], 0)

    def test_wall_does_not_stop_magic(self):
        db, sim, a, b = setup([("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        knight, goblin = a.formation.units[0], b.formation.units[0]
        cast(sim, db, knight, "wall", knight)
        self.assertGreater(cast(sim, db, goblin, "zap", knight)[0], 0)

    def test_magick_wall_negates_magic(self):
        db, sim, a, b = setup([("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        knight, goblin = a.formation.units[0], b.formation.units[0]
        cast(sim, db, knight, "magick_wall", knight)
        self.assertEqual(cast(sim, db, goblin, "zap", knight), [0])

    def test_dark_armor_negates_two_hits(self):
        db, sim, a, b = setup([("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        knight, goblin = a.formation.units[0], b.formation.units[0]
        cast(sim, db, knight, "dark_armor", knight)
        self.assertEqual([cast(sim, db, goblin, "chop", knight)[0] for _ in range(3)][:2], [0, 0])
        self.assertGreater(cast(sim, db, goblin, "chop", knight)[0], 0)

    def test_bulwark_protects_the_whole_row(self):
        db, sim, a, b = setup([("knight", 1, 0, 0), ("cleric", 1, 0, 1)], [("goblin", 1, 0, 0)])
        knight, cleric = a.formation.units[:2]
        goblin = b.formation.units[0]
        cast(sim, db, knight, "bulwark", knight)
        self.assertEqual(cast(sim, db, goblin, "chop", cleric), [0])
        self.assertEqual(cast(sim, db, goblin, "chop", knight), [0])


class DefenceBuffTests(unittest.TestCase):
    def test_mystic_shield_gives_half_more_mag_def_and_pp(self):
        db, sim, a, b = setup([("knight", 1, 0, 0)], [("goblin", 1, 0, 0)])
        set_stats(db, "knight", mag_def=20)
        knight = a.formation.units[0]
        before = knight.stat(Stat.MAG_DEF)
        knight.pp.spend(knight.pp.current)
        cast(sim, db, knight, "mystic_shield", knight)
        self.assertEqual(knight.stat(Stat.MAG_DEF), round(before * 1.5))
        self.assertEqual(knight.pp.current, min(2, knight.pp_max))      # PP ограничен запасом бойца

    def test_row_resistance_hits_a_row(self):
        self.assertEqual(REAL.skills["row_resistance"].area, "row")
        self.assertEqual([a.effect_id for a in REAL.skills["row_resistance"].applies], ["uo_mag_def_p50pct"])


class ResurrectionTests(unittest.TestCase):
    def test_resurrection_raises_a_fallen_ally_with_one_hp(self):
        db, sim, a, b = setup([("cleric", 1, 0, 0), ("knight", 1, 1, 0)], [("goblin", 1, 0, 0)])
        cleric, knight = a.formation.units[:2]
        knight.state.current_hp = 0
        sim._dead.add(knight.uid)
        cast(sim, db, cleric, "resurrection", knight)
        self.assertEqual(knight.hp, 1)
        self.assertTrue(knight.is_alive)


if __name__ == "__main__":
    unittest.main()
