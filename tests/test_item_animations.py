"""Навыки предметов: свои анимации из файлов игры и старые привязки-заглушки.

Своя анимация навыка лежит в файле персонажа слотом S##_<ВНУТРЕННЕЕ ИМЯ>_1..N
(как у навыков класса в build.py). Навыки предметов сборщик раньше не смотрел, и им
доставалась заглушка — обычная атака, каст или стойка класса.
"""
import unittest

from tools.uo_battle.item_animations import is_placeholder, skill_chain, slot_chains


class SlotChainTests(unittest.TestCase):
    def test_groups_slots_by_skill_name(self):
        groups = slot_chains(["S01_ATTACK_A1", "S01_ATTACK_A2", "S02_ARROW_RAIN_1", "IDLE"])
        self.assertEqual(groups["ATTACK_A"], ["S01_ATTACK_A1", "S01_ATTACK_A2"])
        self.assertEqual(groups["ARROW_RAIN"], ["S02_ARROW_RAIN_1"])

    def test_skill_takes_all_slots_with_its_name(self):
        groups = slot_chains(["S05_ARROW_RAIN_1", "S05_ARROW_RAIN_2", "S06_ARROW_RAIN_3"])
        self.assertEqual(skill_chain(groups, "ARROW_RAIN"),
                         ["S05_ARROW_RAIN_1", "S05_ARROW_RAIN_2", "S06_ARROW_RAIN_3"])

    def test_without_own_animation_is_empty(self):
        groups = slot_chains(["S01_ATTACK_A1", "IDLE"])
        self.assertEqual(skill_chain(groups, "FIRE_SLASH"), [])

    def test_names_are_compared_without_underscores_and_case(self):
        groups = slot_chains(["S03_FREEZE_THRUST_1"])
        self.assertEqual(skill_chain(groups, "FREEZE_THRUST"), ["S03_FREEZE_THRUST_1"])


class PlaceholderTests(unittest.TestCase):
    def setUp(self):
        self.classes = {"lord": {"phases": {"stance": ["IDLE*"], "attack": ["ATTACK_A1", "ATTACK_A2*"]}}}
        self.animations = {
            "lord__fire_slash": {"class": "lord", "parts": ["ATTACK_A1", "ATTACK_A2"]},
            "lord__true_thrust": {"class": "lord", "parts": ["S03_TRUE_THRUST_1"]},
        }

    def test_class_phase_chain_is_placeholder(self):
        self.assertTrue(is_placeholder(self.classes, self.animations, {"animation": "lord__fire_slash"}))

    def test_own_slot_chain_is_not_placeholder(self):
        self.assertFalse(is_placeholder(self.classes, self.animations, {"animation": "lord__true_thrust"}))

    def test_missing_or_empty_binding_is_not_placeholder(self):
        self.assertFalse(is_placeholder(self.classes, self.animations, {}))
        self.assertFalse(is_placeholder(self.classes, self.animations, {"animation": ""}))


if __name__ == "__main__":
    unittest.main()
