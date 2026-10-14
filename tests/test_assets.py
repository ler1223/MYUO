"""Проверка файлов вкладки Stage без pygame: спрайты, визуал навыков, сцена."""
import json
import struct
import tempfile
import unittest
from pathlib import Path

from game.database import Database
from engine.scene import DEFAULT_SCENE, SCENES_DIR, SceneConfig, SceneObject, SceneStore

ROOT = Path(__file__).resolve().parent.parent
UNITS_DIR = ROOT / "assets" / "units"
UNITS = json.loads((UNITS_DIR / "units.json").read_text(encoding="utf-8"))
VISUALS = json.loads((ROOT / "assets" / "visuals" / "skills.json").read_text(encoding="utf-8"))
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# Действия шагов визуала: должны совпадать с StageScreen.steps (проверяется в tests/test_ui.py).
STEP_ACTIONS = {"dash", "hop", "lunge", "jump", "rise", "tilt", "knockback", "glow", "projectile", "slash", "thrust",
                "ring", "beam", "bolt", "burst", "sparkle", "flash", "shake", "runes", "pillars", "arrow_rain",
                "glint", "dome", "weapon", "impact", "wrap", "sprite", "sprite_beam"}
FX_DIR = ROOT / "assets" / "fx"
FX = json.loads((FX_DIR / "effects.json").read_text(encoding="utf-8"))
FX_LAYERS = {"front", "back", "wrap", "ground"}
FX_ANIMATIONS = {"sweep", "stretch", "spin", "grow", "pulse"}
WHO = {"self", "target", "targets"}
DELIVERIES = {"melee", "arrow", "magic", "heal", "support"}


def png_size(path: Path) -> tuple[int, int]:
    """Размер PNG из заголовка IHDR."""
    data = path.read_bytes()[:24]
    assert data[:8] == PNG_SIGNATURE, f"{path.name} is not a PNG file"
    return struct.unpack(">II", data[16:24])


class UnitSpriteTests(unittest.TestCase):
    def test_every_sprite_has_a_png_of_its_recorded_height_and_a_sheet(self):
        self.assertTrue(UNITS["sprites"])
        for sprite_id, info in UNITS["sprites"].items():
            width, height = png_size(UNITS_DIR / f"{sprite_id}.png")
            self.assertEqual(height, info["height"], sprite_id)
            self.assertIn(info["sheet"], UNITS["sheets"], sprite_id)
            for value in info.get("anchors", {}).values():
                self.assertTrue(0 < value <= 1, sprite_id)

    def test_fallback_points_to_existing_sprites_and_classes(self):
        fallback = UNITS["fallback"]
        self.assertIn(fallback["default"], UNITS["sprites"])
        for class_id, sprite in fallback["classes"].items():
            self.assertIn(sprite, UNITS["sprites"], class_id)
        for sprite in fallback["tags"].values():
            self.assertIn(sprite, UNITS["sprites"])


class SkillVisualDataTests(unittest.TestCase):
    def entries(self):
        for key, entry in VISUALS.items():
            if key == "_defaults":
                yield from ((f"_defaults/{k}", v) for k, v in entry.items())
            elif not key.startswith("_"):
                yield key, entry

    def test_steps_use_known_actions_and_roles(self):
        for key, entry in self.entries():
            self.assertGreater(entry.get("windup", 380), 0, key)
            for phase in ("cast", "hit"):
                for step in entry.get(phase, []):
                    self.assertIn(step["do"], STEP_ACTIONS, (key, step))
                    self.assertIn(step.get("who", "self"), WHO, (key, step))
                    self.assertGreaterEqual(step.get("at", 0), 0, (key, step))

    def test_sprite_steps_name_existing_effects(self):
        for key, entry in self.entries():
            for step in entry.get("cast", []) + entry.get("hit", []):
                name = step.get("fx") if step["do"] in ("sprite", "sprite_beam") else step.get("sprite")
                if name is not None:
                    self.assertIn(name, FX, (key, step))

    def test_keys_name_real_skills_and_classes(self):
        db = Database.load()                                    # визуал описан для настоящих данных data/
        self.assertEqual(set(VISUALS["_defaults"]), DELIVERIES)
        for key in VISUALS:
            if key.startswith("_"):
                continue
            class_id, _, skill_id = key.rpartition("/")
            self.assertIn(skill_id, db.skills, key)
            if class_id:
                self.assertIn(class_id, db.units, key)


class SpriteEffectFileTests(unittest.TestCase):
    def test_every_effect_has_its_images_and_valid_settings(self):
        self.assertTrue(FX)
        for name, spec in FX.items():
            cols, rows = spec.get("grid", [1, 1])
            self.assertLessEqual(spec.get("frames", 1), cols * rows, name)
            self.assertIn(spec.get("blend"), ("add", "alpha"), name)
            self.assertIn(spec.get("layer", "front"), FX_LAYERS, name)
            if "animate" in spec:
                self.assertIn(spec["animate"], FX_ANIMATIONS, name)
            files = [spec["back"], spec["front"]] if spec.get("layer") == "wrap" else [f"{name}.png"]
            for file in files:
                width, height = png_size(FX_DIR / file)
                self.assertGreaterEqual(min(width // cols, height // rows), 32, (name, file))   # кадры не крошечные


class SceneTests(unittest.TestCase):
    def test_every_saved_scene_loads_and_projection_round_trips(self):
        store = SceneStore(SCENES_DIR)
        self.assertIn(DEFAULT_SCENE, store.ids())
        for scene_id in store.ids():
            scene = store.load(scene_id)
            self.assertEqual(SceneConfig.from_dict(scene.to_dict()), scene, scene_id)   # файл уже в чистом виде
        scene = store.load(DEFAULT_SCENE)
        projection = scene.projection()
        for row in range(3):
            for col in range(3):
                x, z = scene.cell("left", row, col, 3)
                sx, sy, _ = projection.project(x, 0, z)
                back = projection.unproject(sx, sy)
                self.assertAlmostEqual(back[0], x, places=6)
                self.assertAlmostEqual(back[1], z, places=6)
        near = projection.project(*xz(scene.cell("left", 0, 2, 3)))
        far = projection.project(*xz(scene.cell("left", 0, 0, 3)))
        self.assertLess(far[1], near[1])                     # дальняя колонна выше
        self.assertLess(far[2], near[2])                     # и мельче
        right = scene.cell("right", 1, 1, 3)
        self.assertEqual(right[0], -scene.cell("left", 1, 1, 3)[0])   # противник зеркален

    def test_bigger_field_continues_the_lines_and_bad_values_are_clamped(self):
        scene = SceneConfig(rows=[100, 200], columns=[200, 100, 0])
        self.assertEqual(scene.row_distance(3), 400)
        self.assertEqual(scene.column_depth(4, 5), 0)          # ближняя колонна всегда на ближней линии
        self.assertEqual(scene.column_depth(0, 5), 400)        # лишние уходят вглубь с тем же шагом
        bad = SceneConfig.from_dict({"horizon": 900, "ground": 400, "focal": -5, "rows": [], "unknown": 1})
        self.assertLess(bad.horizon, bad.ground)
        self.assertGreaterEqual(bad.focal, 100)
        self.assertTrue(bad.rows)

    def test_store_creates_copies_and_deletes_scenes(self):
        with tempfile.TemporaryDirectory() as folder:
            store = SceneStore(Path(folder))
            first = store.create("Castle Yard")
            self.assertEqual(first, "castle_yard")
            source = store.load(first)
            source.objects.append(SceneObject("tree.png", 10, 300, layer="nowhere"))
            source.clamp()
            self.assertEqual(source.objects[0].layer, "upright")   # неизвестный слой исправлен
            copy = store.create("Castle Yard", source)
            self.assertEqual(copy, "castle_yard_2")                 # id не повторяется
            self.assertEqual(store.load(copy).objects[0].image, "tree.png")
            self.assertEqual(store.names(), {first: "Castle Yard", copy: "Castle Yard"})
            store.delete(first)
            self.assertEqual(store.ids(), [copy])
            self.assertEqual(store.load("missing"), SceneConfig())  # нет файла — сцена по умолчанию


class DemoBattleTests(unittest.TestCase):
    def test_demo_battle_shows_almost_every_skill_and_every_passive(self):
        from game.battle import BattleSimulation
        from game.events import Covered, PassiveTriggered, SkillUsed, UnitDied
        from game.scenario import DEMO_SEED, build_demo_battle
        db = Database.load()                                    # демонстрация собрана под настоящие данные
        scenario = build_demo_battle(db)
        sim = BattleSimulation(scenario.player_squad, scenario.enemy_squad, db, seed=DEMO_SEED)
        skills, passives, covers, deaths = set(), set(), 0, 0
        while not sim.finished:
            for ev in sim.step():
                skills.add(ev.skill_id) if isinstance(ev, SkillUsed) else None
                passives.add(ev.passive_id) if isinstance(ev, PassiveTriggered) else None
                covers += isinstance(ev, Covered)
                deaths += isinstance(ev, UnitDied)
        units = [u for squad in (scenario.player_squad, scenario.enemy_squad) for u in squad.formation.units]
        owned = {s for unit in units for s in unit.definition.skills}      # навыки классов демонстрации
        self.assertGreaterEqual(len(skills & owned), len(owned) - 2, sorted(owned - skills))
        own_passives = {p for unit in units for p in unit.definition.passives}
        self.assertGreaterEqual(len(passives & own_passives), len(own_passives) * 0.8, sorted(own_passives - passives))
        self.assertGreater(covers, 0)
        self.assertGreater(deaths, 0)
        self.assertEqual(db.units["knight"].ap_max, Database.load().units["knight"].ap_max)   # справочник не тронут


def xz(cell):
    return cell[0], 0.0, cell[1]


if __name__ == "__main__":
    unittest.main()
