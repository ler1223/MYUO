"""Особые свойства предметов UO (ITEM_TRAITS): сила блока, урон, лечение, смертельный удар."""
import unittest

from game.combat import Battle
from game.combat.record import ACTIVE, Act
from game.definitions import ItemDefinition
from game.events import DamageDealt
from tests.helpers import add_skill, plain_db, set_stats, squads


def with_charm(db, **traits):
    """Амулет fire_charm получает особые свойства и теги (tags — отдельным ключом)."""
    data = db.items["fire_charm"].to_dict()
    tags = traits.pop("tags", [])
    data["traits"] = traits
    data["tags"] = list(data["tags"]) + tags
    db.update("items", "fire_charm", data)


def fight(db, left, right, equipment=((), ())):
    a, b = squads(db, [(left, 1, 0, 0)], [(right, 1, 0, 0)])
    for squad, items in zip((a, b), equipment):
        unit = squad.formation.units[0]
        for item in items:
            unit.equip(unit.definition.slots.index("artifact"), item)
    return Battle(a, b, db, seed=1), a.formation.units[0], b.formation.units[0]


class TraitDataTests(unittest.TestCase):
    def test_round_trip_and_sum(self):
        item = ItemDefinition.from_dict("x", {"name": "x", "slot": "artifact", "traits": {"heal_received": 30}})
        self.assertEqual(item.trait("heal_received"), 30)
        self.assertEqual(item.trait("exp_gain"), 0)
        self.assertEqual(item.to_dict()["traits"], {"heal_received": 30})

    def test_unknown_trait_is_an_error(self):
        with self.assertRaises(ValueError):
            ItemDefinition.from_dict("x", {"name": "x", "slot": "artifact", "traits": {"luck": 1}})

    def test_unit_sums_traits_of_equipped_items(self):
        db = plain_db()
        with_charm(db, exp_gain=20)
        knight = db.create_unit("knight", 1, equipment=["fire_charm"])
        self.assertEqual(knight.trait("exp_gain"), 20)
        self.assertEqual(db.create_unit("knight", 2).trait("exp_gain"), 0)


class DamageTraitTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()
        add_skill(self.db, "chop", ["goblin"], ap_cost=1, tags=["melee"],
                  parts=[{"kind": "damage", "category": "physical", "power": 1.0,
                          "scaling": [{"stat": "phys_atk", "coef": 1.0}]}])
        set_stats(self.db, "goblin", phys_atk=60)
        set_stats(self.db, "knight", hp=500, phys_def=0, guard_rate=100, evasion=0)

    def damage(self, **traits):
        with_charm(self.db, **traits)
        sim, goblin, knight = fight(self.db, "goblin", "knight", equipment=((), ("fire_charm",) if traits else ()))
        act = Act(ACTIVE, goblin.uid, "chop", target=knight.uid)
        sim._resolve(goblin, self.db.skills["chop"], knight, act, root=True)
        return next(e.amount for e in act.events if isinstance(e, DamageDealt))

    def test_damage_reduction_lowers_damage(self):
        plain = self.damage()
        self.assertAlmostEqual(self.damage(damage_reduction=50) / plain, 0.5, delta=0.05)

    def test_guard_efficiency_raises_block(self):
        base = self.damage()                       # блок без щита: малый, 25%
        self.assertLess(self.damage(guard_efficiency=50), base)


class HealTraitTests(unittest.TestCase):
    def test_heal_received_scales_healing(self):
        db = plain_db()
        with_charm(db, heal_received=50)
        sim, goblin, knight = fight(db, "goblin", "knight", equipment=((), ("fire_charm",)))
        knight.state.current_hp = 10
        act = Act(ACTIVE, goblin.uid, "x")
        self.assertEqual(sim._heal(knight, 20, goblin, "x", act), 30)


class DeathblowTests(unittest.TestCase):
    def setUp(self):
        self.db = plain_db()
        add_skill(self.db, "finish", ["goblin"], ap_cost=1, tags=["melee"], extras={"deathblow_hp": 0.5},
                  parts=[{"kind": "damage", "category": "physical", "power": 0.1,
                          "scaling": [{"stat": "phys_atk", "coef": 1.0}]}])
        self.db.update("tags", "immune_deathblow", {"name": "Immune to deathblow", "kind": "unit"})
        set_stats(self.db, "knight", hp=100, phys_def=0, guard_rate=0, evasion=0)

    def strike(self, equipment=()):
        sim, goblin, knight = fight(self.db, "goblin", "knight", equipment=((), equipment))
        knight.state.current_hp = 40                       # уже ниже половины
        act = Act(ACTIVE, goblin.uid, "finish", target=knight.uid)
        sim._resolve(goblin, self.db.skills["finish"], knight, act, root=True)
        return knight

    def test_deathblow_kills_a_weakened_target(self):
        self.assertFalse(self.strike().is_alive)

    def test_immunity_tag_survives_it(self):
        with_charm(self.db, tags=["immune_deathblow"])
        self.assertTrue(self.strike(("fire_charm",)).is_alive)


if __name__ == "__main__":
    unittest.main()
