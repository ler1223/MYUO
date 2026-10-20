"""Новая система анимаций: разбор данных, кривые полёта, привязка навыка и режиссёр.

Файлы игры не нужны: модели подменяются заглушками, анимации — временными JSON.
"""
import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from battle.animation import (curve_length, curve_point, from_manual, normalize_animation,
                             normalize_curve, normalize_fx_list, normalize_rain,
                             normalize_skill_animation, normalize_trajectory, to_json)
from battle.data import TICK_MS, ShowData
from battle.director import Director
from battle.timeline import Shot, Timeline
from game.combat import Battle
from game.combat.record import ACTIVE
from tests.helpers import add_skill, duel, only, plain_db
from tests.test_combat import part


def write_show(data: dict) -> Path:
    path = Path(tempfile.mkdtemp()) / "uo_battle.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


class ParseTests(unittest.TestCase):
    def test_animation_normalizes_parts_holds_and_tags(self):
        anim = normalize_animation("a", {"class": "knight", "parts": ["IDLE", " ", "ATTACK"],
                                        "holds": {"0": 300, "-1": 500, "x": 100}, "tags": ["melee", "melee"]})
        self.assertEqual(anim["parts"], ["IDLE", "ATTACK"])
        self.assertEqual(anim["holds"], {0: 300.0})
        self.assertEqual(anim["tags"], ["melee"])
        self.assertEqual(anim["class"], "knight")

    def test_effect_intervals_are_sanitized(self):
        out = normalize_fx_list([{"anim": "HIT", "start": 100, "end": 300}, {"anim": ""}, "bad",
                                 {"anim": "A", "start": -5, "end": 1}])
        self.assertEqual(out, [{"anim": "HIT", "start": 100.0, "end": 300.0},
                               {"anim": "A", "start": 0.0, "end": 1.0}])

    def test_curve_gets_endpoints_and_is_sorted(self):
        curve = normalize_curve([[0.8, -0.4], [0.5, -0.2]])
        self.assertEqual(curve[0], [0.0, 0.0])
        self.assertEqual(curve[-1], [1.0, 0.0])
        self.assertEqual([p[0] for p in curve], sorted(p[0] for p in curve))

    def test_trajectory_without_curve_or_anim_is_not_stored(self):
        self.assertIsNone(normalize_trajectory({"curve": [[0, 0], [1, 0]], "anim": ""}))
        traj = normalize_trajectory({"curve": [[0, 0], [0.5, -0.2], [1, 0]], "speed": 0, "anim": "ARROW"})
        self.assertEqual(traj["speed"], 1.0)
        self.assertEqual(traj["anim"], "ARROW")

    def test_rain_requires_entries_and_counts(self):
        self.assertIsNone(normalize_rain({"entries": [{"anim": "A", "count": 0}]}))
        rain = normalize_rain({"duration": 1, "entries": [{"anim": "A", "count": 3}, {"anim": "", "count": 2}]})
        self.assertEqual(rain["duration"], 100.0)
        self.assertEqual(rain["entries"], [{"anim": "A", "count": 3}])

    def test_manual_reads_old_composites_and_round_trips(self):
        anims, skills = from_manual({"composites": {"old": {"parts": ["A"], "source_kind": "unit",
                                                            "source_name": "knight", "holds": {"0": 100}}},
                                     "skill_animations": {"fireball": {"animation": "old", "tags": ["magic"]}}})
        self.assertEqual(anims["old"]["class"], "knight")
        self.assertEqual(skills["fireball"]["animation"], "old")
        packed = to_json(anims, skills)
        self.assertEqual(packed["animations"]["old"]["holds"], {"0": 100})
        self.assertEqual(packed["skill_animations"]["fireball"]["tags"], ["magic"])


class CurveTests(unittest.TestCase):
    def test_straight_curve_is_the_line(self):
        points = [[0.0, 0.0], [1.0, 0.0]]
        for k in (0.0, 0.25, 0.5, 1.0):
            self.assertAlmostEqual(curve_point(points, k)[1], 0.0)

    def test_arc_goes_above_the_line(self):
        points = [[0.0, 0.0], [0.5, -0.3], [1.0, 0.0]]
        self.assertLess(curve_point(points, 0.5)[1], -0.25)
        self.assertAlmostEqual(curve_point(points, 0.0)[1], 0.0)
        self.assertAlmostEqual(curve_point(points, 1.0)[1], 0.0)

    def test_curve_length_is_longer_than_straight(self):
        points = [[0.0, 0.0], [0.5, -0.4], [1.0, 0.0]]
        self.assertGreater(curve_length((0, 0), (600, 0), points), 600)

    def test_shot_path_uses_curve_and_stays_on_target(self):
        path = ((0.0, 0.0), (0.5, -0.3), (1.0, 0.0))
        shot = Shot(0, "ARROW", (0, 0), (600, 0), 300, 1.0, path=path)
        mid = shot.at(150)
        self.assertLess(mid[1], -100)                    # дуга выше прямой (y экрана вниз)
        end = shot.at(300)
        self.assertAlmostEqual(end[0], 600)
        self.assertAlmostEqual(end[1], 0)
        self.assertFalse(end[3])


class BindingTests(unittest.TestCase):
    def make_data(self) -> ShowData:
        path = write_show({
            "classes": {"knight": {"file": "Knight", "phases": {"attack": ["ATTACK_1"]},
                                   "skills": {"old_slash": ["OLD_1"]}}},
            "manual": {
                "animations": {"knight_slash": {"class": "knight", "name": "knight_slash",
                                                "parts": ["ATTACK_A", "ATTACK_B"], "holds": {"0": 250},
                                                "tags": ["melee"]}},
                "skill_animations": {"fireball": {
                    "animation": "knight_slash", "tags": ["magic"],
                    "caster_fx": [{"anim": "CAST", "start": 50, "end": 300}],
                    "target_fx": [{"anim": "HIT", "start": 0, "end": 120}],
                    "trajectory": {"anim": "FIREBALL", "curve": [[0, 0], [0.5, -0.3], [1, 0]], "speed": 80},
                    "rain": {"duration": 1500, "entries": [{"anim": "ICE", "count": 5}]},
                }},
            },
        })
        return ShowData(path)

    def test_skill_takes_parts_and_holds_from_its_animation(self):
        data = self.make_data()
        self.assertEqual(data.skill_chain("knight", "fireball"), ["ATTACK_A", "ATTACK_B"])
        self.assertEqual(data.animation_holds("fireball"), {0: 250.0})
        self.assertEqual(data.animation_tags("fireball"), ["magic"])

    def test_unbound_skill_falls_back_to_old_class_chain(self):
        data = self.make_data()
        self.assertEqual(data.skill_chain("knight", "old_slash"), ["OLD_1"])
        self.assertIsNone(data.animation("old_slash"))

    def test_skill_animation_keeps_effects_trajectory_and_rain(self):
        data = self.make_data()
        spec = data.skill_animation("fireball")
        self.assertEqual(spec["caster_fx"], [{"anim": "CAST", "start": 50.0, "end": 300.0}])
        self.assertEqual(spec["target_fx"], [{"anim": "HIT", "start": 0.0, "end": 120.0}])
        self.assertEqual(spec["trajectory"]["speed"], 80.0)
        self.assertEqual(spec["rain"]["entries"], [{"anim": "ICE", "count": 5}])


class DirectorAnimationTests(unittest.TestCase):
    def fake_model(self, names: dict):
        """Модель эффекта: puppet.anims + length, достаточные для планирования эффектов."""
        puppet = SimpleNamespace(anims={n: {} for n in names}, evaluate=lambda *a, **k: None)
        return SimpleNamespace(puppet=puppet, length=lambda name: names.get(name, 10))

    def make_battle(self):
        db = plain_db()
        add_skill(db, "arrow", ["knight"], hits=1, accuracy=1000, tags=["ranged"], parts=[part(power=0.1)])
        return db

    def test_director_uses_custom_trajectory(self):
        db = self.make_battle()
        path = write_show({
            "classes": {"knight": {"file": "Knight", "phases": {"attack": ["ATTACK_1"]}}},
            "skills": {"arrow": {"kind": "ranged", "cast": [], "hit": ["HIT_A"],
                                 "shot": {"anim": "ARROW", "speed": 10}}},
            "manual": {"skill_animations": {"arrow": {
                "animation": "", "tags": [],
                "trajectory": {"anim": "ARROW", "curve": [[0, 0], [0.5, -0.3], [1, 0]], "speed": 60},
            }}},
        })
        sim, knight, orc = duel(db, "knight", "orc")
        only(db, knight, "arrow")
        battle = Battle(sim.attacker, sim.defender, db, seed=1)
        timeline = Timeline()
        director = Director(ShowData(path), battle, timeline)
        while True:
            battle.step()
            act = battle.last_act
            if act.kind == ACTIVE and act.actor == knight.uid:
                break
        director.act(act, 0)
        self.assertEqual(len(timeline.shots), 1)
        shot = timeline.shots[0]
        self.assertEqual([list(p) for p in shot.path], [[0.0, 0.0], [0.5, -0.3], [1.0, 0.0]])
        # Скорость 60 вместо 10: тот же путь режиссёр проходит быстрее, чем старым снарядом.
        straight = math.hypot(600, 0)
        self.assertLess(shot.ms, straight / 10 * TICK_MS)

    def test_director_schedules_bound_caster_and_target_effects(self):
        db = self.make_battle()
        path = write_show({
            "classes": {"knight": {"file": "Knight", "phases": {"attack": ["ATTACK_1"]}}},
            "skills": {"arrow": {"kind": "ranged", "cast": [], "hit": ["HIT_A"],
                                 "shot": {"anim": "ARROW", "speed": 40}}},
            "manual": {"skill_animations": {"arrow": {
                "animation": "", "tags": [],
                "caster_fx": [{"anim": "CAST", "start": 0, "end": 100}],
                "target_fx": [{"anim": "HIT_X", "start": 0, "end": 50}],
            }}},
        })
        sim, knight, orc = duel(db, "knight", "orc")
        only(db, knight, "arrow")
        battle = Battle(sim.attacker, sim.defender, db, seed=1)
        timeline = Timeline()
        director = Director(ShowData(path), battle, timeline)
        director.fx_model = self.fake_model({"CAST": 10, "HIT_X": 10, "HIT_A": 10})
        while True:
            battle.step()
            act = battle.last_act
            if act.kind == ACTIVE and act.actor == knight.uid:
                break
        director.act(act, 0)
        names = [fx.anim for fx in timeline.fx]
        self.assertIn("CAST", names)
        self.assertIn("HIT_X", names)
        self.assertNotIn("HIT_A", names)                 # свои эффекты на цели заменяют стандартную вспышку
        self.assertTrue(all(fx.uid is not None for fx in timeline.fx if fx.anim in ("CAST", "HIT_X")))

    def test_rain_schedules_all_effects_within_duration(self):
        db = self.make_battle()
        path = write_show({
            "classes": {"knight": {"file": "Knight", "phases": {"attack": ["ATTACK_1"]}}},
            "skills": {"arrow": {"kind": "ranged", "cast": [], "hit": ["HIT_A"],
                                 "shot": {"anim": "ARROW", "speed": 40}}},
            "manual": {"skill_animations": {"arrow": {
                "animation": "", "tags": [],
                "rain": {"duration": 1200, "entries": [{"anim": "ICE", "count": 4},
                                                       {"anim": "FIRE", "count": 2}]},
            }}},
        })
        sim, knight, orc = duel(db, "knight", "orc")
        only(db, knight, "arrow")
        battle = Battle(sim.attacker, sim.defender, db, seed=1)
        timeline = Timeline()
        director = Director(ShowData(path), battle, timeline)
        while True:
            battle.step()
            act = battle.last_act
            if act.kind == ACTIVE and act.actor == knight.uid:
                break
        director.act(act, 0)
        rain_shots = [s for s in timeline.shots if s.anim in ("ICE", "FIRE")]
        self.assertEqual(len(rain_shots), 6)
        span = max(s.start for s in rain_shots) - min(s.start for s in rain_shots)
        self.assertLess(span, 1200)


if __name__ == "__main__":
    unittest.main()
