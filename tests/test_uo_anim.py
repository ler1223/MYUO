"""Анимации юнитов из Unicorn Overlord: клипы и позы, банк спрайтов, живые эффекты, кукла и её отрисовка.

Файлов игры в репозитории нет: анимации и эффекты подменяются заглушками, кукла — синтетическая.
Отрисовка видеокартой проверяется, только если есть moderngl и OpenGL 3.3.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import numpy as np
import pygame

import pygame_stage
from engine.sprites import FxLibrary
from engine.uo import ui as uo_ui
from engine.uo.gl import GLRenderer
from engine.uo.items import ItemIcons
from engine.uo.library import LiveAnims, bg_role, resolve_chain, state_parts
from engine.uo.puppet import ADD, IDENTITY, MULTIPLY, NORMAL, Canvas, Item, matrix
from engine.uo_anim import Actions, Clip
from pygame_stage import UNITS_DIR, Motion, SpriteBank, StageScreen


def part(ms=400, frames=4, anim="A", cls="fighter"):
    """Часть состояния: frames — тики анимации, ms — их длительность."""
    return {"class": cls, "anim": anim, "from": 0, "frames": frames, "ms": ms, "loop": False}


class ClipTests(unittest.TestCase):
    def test_once_holds_last_frame_and_ends(self):
        clip = Clip(1000, part())
        self.assertEqual(clip.frame(1000), 0)
        self.assertEqual(clip.frame(1250), 2)
        self.assertEqual(clip.frame(5000), 3)
        self.assertEqual(clip.end, 1400)

    def test_loop_and_stretch(self):
        self.assertEqual(Clip(0, part(), "loop").frame(500), 1)           # второй круг
        self.assertIsNone(Clip(0, part(), "loop").end)                     # без duration не кончается
        stretched = Clip(0, part(), "stretch", 100)                       # 400 мс сжаты в 100
        self.assertEqual(stretched.frame(60), 2)
        self.assertEqual(stretched.end, 100)

    def test_actions_pose_idle_between_clips_and_hold(self):
        actions = Actions()
        a, b = part(anim="a"), part(anim="b")
        actions.play(7, [Clip(100, a), Clip(500, b)])
        self.assertIsNone(actions.pose(7, 50))                            # до клипа — стойка
        self.assertEqual(actions.pose(7, 200)[0]["anim"], "a")
        self.assertEqual(actions.pose(7, 600)[0]["anim"], "b")
        self.assertIsNone(actions.pose(7, 950))                           # всё доиграно — стойка
        actions.play(7, [Clip(550, a)])                                   # новое начало заменяет начатое позже
        self.assertEqual(actions.pose(7, 600)[0]["anim"], "a")
        actions.hold(7, Clip(2000, b))
        self.assertEqual(actions.pose(7, 9000), (b, 3))                   # смерть: последний кадр навсегда
        self.assertIsNone(actions.pose(8, 100))


class RingAnims(LiveAnims):
    """LiveAnims без файлов игры: части стойки заданы."""

    def __init__(self, ring):
        self.ring = ring

    def parts(self, cid, state):
        return self.ring if cid == "fighter" and state == "idle" else []


class FakeAnims:
    """Анимации для банка спрайтов: кадр — полоса 10x34, ноги внизу у левого края."""

    def __init__(self):
        self.scaled_calls = []

    def has(self, cid):
        return cid in ("fighter", "knight")

    def parts(self, cid, state):
        return [part(cls=cid)] if self.has(cid) and state in ("idle", "attack") else []

    def ratio(self, cid):
        return 1.8 if cid == "knight" else 1.0

    def height_px(self, cid):
        return 34.0

    def scaled(self, p, index, k, flip):
        self.scaled_calls.append((p["anim"], index, k, flip))
        image = pygame.Surface((round(10 * k), round(34 * k)), pygame.SRCALPHA)
        image.fill((0, 200, 0, 255))
        return image, image.copy(), ((9 if flip else 1) * k, 34 * k)

    def still(self, cid):
        return self.scaled(part(cls=cid), 0, 1.0, False)[0]

    def idle_at(self, cid, ms):
        return (part(cls=cid), (ms // 100) % 4) if self.has(cid) else None


class BankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_idle_is_a_ring_of_parts(self):
        ring = [dict(part(400), anim="UPWARD"), dict(part(200, frames=2), anim="UPWARD_IDLE")]
        anims = RingAnims(ring)
        self.assertEqual(anims.idle_at("fighter", 100), (ring[0], 1))
        self.assertEqual(anims.idle_at("fighter", 450), (ring[1], 0))        # вторая часть после первой
        self.assertEqual(anims.idle_at("fighter", 650), (ring[0], 0))        # и снова первая
        self.assertIsNone(anims.idle_at("wizard", 0))

    def test_bank_prefers_animation_and_gives_still_for_static_places(self):
        anims = FakeAnims()
        bank = SpriteBank(UNITS_DIR, None, anims)
        self.assertEqual(bank.sprite_for("fighter"), "uo:fighter")
        self.assertTrue(bank.animated("uo:fighter"))
        self.assertFalse(bank.animated("old_knight"))
        self.assertNotEqual(bank.sprite_for("wizard"), "uo:wizard")       # нет куклы — обычный спрайт
        self.assertAlmostEqual(bank.ratio("uo:knight"), 1.8)
        self.assertEqual(bank.image("uo:fighter.png").get_size(), (10, 34))   # первый кадр стойки
        sprite, _ = bank.unit_sprite("uo:fighter", 68, False)
        self.assertEqual(sprite.get_height(), 68)
        frame, _, origin = bank.idle_pose("uo:fighter", 250, 68.0, True)     # рост 68 при 34 единицах — масштаб 2
        self.assertEqual(frame.get_size(), (20, 68))
        self.assertEqual(origin, (18, 68))
        self.assertEqual(anims.scaled_calls[-1], ("A", 2, 2.0, True))
        self.assertEqual(bank.parts("uo:fighter", "die"), [])
        self.assertFalse(str(SpriteBank(UNITS_DIR, None, None).sprite_for("fighter")).startswith("uo:"))


class FxLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_extra_effects_do_not_override_own(self):
        own, extra = self.tmp / "own", self.tmp / "extra"
        own.mkdir()
        extra.mkdir()
        (own / "effects.json").write_text(json.dumps({"hit": {"frames": 1, "size": 10}}), encoding="utf-8")
        (extra / "effects.json").write_text(json.dumps({"hit": {"frames": 1, "size": 99},
                                                        "uo_hit": {"frames": 1, "size": 50}}), encoding="utf-8")
        image = pygame.Surface((8, 8), pygame.SRCALPHA)
        image.fill((255, 0, 0, 255))
        pygame.image.save(image, str(extra / "uo_hit.png"))
        fx = FxLibrary(own, (extra,))
        self.assertEqual(fx.spec("hit")["size"], 10)                     # своё важнее
        self.assertIn("uo_hit", fx)
        self.assertEqual(len(fx.frames("uo_hit", "main")), 1)           # картинка из своей папки
        self.assertNotIn("uo_hit", FxLibrary(own))

    def test_live_effects_are_drawn_on_demand(self):
        drawn = []
        live = SimpleNamespace(
            spec=lambda name: {"frames": 30, "fps": 60, "size": 120, "blend": "add"} if name == "uo_fireball" else None,
            aspect=lambda name: 2.0,
            scaled=lambda name, frame, height, flip, angle=0.0: drawn.append((name, frame, height, flip))
            or pygame.Surface((height * 2, height)))
        fx = FxLibrary(self.tmp, live=live)
        self.assertIn("uo_fireball", fx)
        self.assertNotIn("uo_nothing", fx)
        self.assertNotIn("fireball", fx)                                 # живые — только uo_*
        self.assertEqual(fx.duration("uo_fireball"), 500)                # 30 тиков при 60 в секунду
        frames = fx.frames("uo_fireball", "main")
        self.assertEqual(len(frames), 30)
        self.assertEqual(frames[0].get_width() / frames[0].get_height(), 2.0)
        self.assertEqual(fx.scaled("uo_fireball", "main", 7, 40, 80, True).get_size(), (80, 40))
        self.assertEqual(drawn, [("uo_fireball", 7, 40, True)])


class SkillFxTests(unittest.TestCase):
    def test_skill_fx_names_and_motion_only_steps(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "uo_anim.json").write_text(json.dumps({"skill_fx": {
                "fireball": {"cast": ["FIREBALL"], "hit": [{"anim": "FIREBALL_HIT", "from": 3}]}}}), encoding="utf-8")
            old, pygame_stage.UO_ANIM_CONFIG = pygame_stage.UO_ANIM_CONFIG, tmp / "uo_anim.json"
            try:
                fx = pygame_stage.uo_skill_fx()
            finally:
                pygame_stage.UO_ANIM_CONFIG = old
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(fx, {"fireball": {"cast": ["uo_fireball"], "hit": ["uo_fireball_hit"]}})
        stage = StageScreen.__new__(StageScreen)                     # без окна: нужны только эффекты
        stage.skill_fx, stage.sprites = fx, {"uo_fireball": {}}
        steps = [{"do": "dash"}, {"do": "sprite", "fx": "fire_burst"}, {"do": "shake"}, {"do": "ring"}]
        self.assertEqual([s["do"] for s in stage._steps(steps, "fireball")], ["dash", "shake"])   # эффекты — из игры
        self.assertEqual(stage._steps(steps, "heal"), steps)                                       # у других — как было
        stage.sprites = {}
        self.assertEqual(stage._steps(steps, "fireball"), steps)                                   # нет эффектов — как было


class ChoreographyTests(unittest.TestCase):
    def test_melee_parts_follow_dash_phases(self):
        run, strike, back, settle = (part(300, anim=n) for n in ("run", "strike", "back", "settle"))
        dash = Motion(1000, 200, 150, 350, dx=300)
        clips = StageScreen._dash_clips(dash, [run, strike, back, settle])
        self.assertEqual([c.part["anim"] for c in clips], ["run", "strike", "back", "settle"])
        self.assertEqual((clips[0].start, clips[0].end), (1000, 1200))          # бег — пока едет к цели
        self.assertEqual(dash.hold, 300)                                        # стоит, пока доигрывает удар
        self.assertEqual(clips[1].start, 1200)
        self.assertEqual((clips[2].start, clips[2].end), (1500, 1850))          # бег назад — на возврате
        self.assertEqual(clips[3].start, dash.end)

    def test_single_attack_plays_on_arrival(self):
        dash = Motion(0, 200, 400, 300, dx=200)
        clips = StageScreen._dash_clips(dash, [part(300)])
        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].start, 200)
        self.assertEqual(dash.hold, 400)                                        # удар короче — пауза прежняя


class ChoiceTests(unittest.TestCase):
    def test_chain_takes_first_rule_group_in_order(self):
        names = ["IDLE", "ATTACK_A2", "ATTACK_A1", "ATTACK_B1", "ATTACK_1", "SKILL_A1"]
        self.assertEqual(resolve_chain(names, [r"^ATTACK_A\d+$", r"^ATTACK_\d+$"]), ["ATTACK_A1", "ATTACK_A2"])
        self.assertEqual(resolve_chain(names, ["^NOPE$", r"^ATTACK_\d+$"]), ["ATTACK_1"])
        self.assertEqual(resolve_chain(names, ["^DIE$"]), [])

    def test_manual_choice_overrides_rules_and_broken_are_skipped(self):
        config = {"states": {"idle": {"chain": ["^IDLE$"]}, "attack": {"chain": [r"^ATTACK_A\d+$"]}},
                  "broken": {"F": ["ATTACK_A2"]}}
        names = ["IDLE", "STANCE_1", "ATTACK_A1", "ATTACK_A2", "ATTACK_A3", "S02_MAGIC_A"]
        auto = {"file": "F"}
        self.assertEqual(state_parts(auto, config, names, "attack"),
                         [{"anim": "ATTACK_A1"}, {"anim": "ATTACK_A3"}])                         # битая пропущена
        manual = {"file": "F", "states": {"idle": ["STANCE_1", {"anim": "IDLE", "from": 10, "to": 40}, "NOPE"],
                                          "attack": []}, "skills": {"fireball": ["S02_MAGIC_A"]}}
        self.assertEqual(state_parts(manual, config, names, "idle"),
                         [{"anim": "STANCE_1"}, {"anim": "IDLE", "from": 10, "to": 40}])          # чужие имена отброшены
        self.assertEqual(state_parts(manual, config, names, "attack"), [])                      # явно пусто
        self.assertEqual(state_parts(manual, config, names, "skill.fireball"), [{"anim": "S02_MAGIC_A"}])
        self.assertEqual(state_parts(manual, config, names, "skill.heal"), [])

    def test_background_layer_roles(self):
        self.assertEqual(bg_role("kinkei_01", {}), "front")
        self.assertEqual(bg_role("kyaratemae00", {}), "front")
        self.assertEqual(bg_role("effect_01", {}), "hidden")
        self.assertEqual(bg_role("sora_01", {}), "back")
        self.assertEqual(bg_role("kinkei_01", {"kinkei_01": "back"}), "back")             # задано в конфиге


def square_puppet(mask_frame: bool = False, layers=None):
    """Кукла из одной или двух деталей-квадратов 10x10 (первая — маска 4x4 в углу); layers — номера
    слоёв деталей (поле a .mbs): маска обрезает детали только своей тысячи."""
    fan = lambda x0, y0, s: np.array([[x0 + s / 2, y0 + s / 2], [x0, y0], [x0 + s, y0], [x0 + s, y0 + s],
                                      [x0, y0 + s], [x0, y0]], float)
    n = 2 if mask_frame else 1
    xy = np.stack([fan(0, 0, 4), fan(0, 0, 10)] if mask_frame else [fan(0, 0, 10)])
    return SimpleNamespace(
        item_polys=lambda it: (np.arange(n), xy * (-1 if it.key_flags & 1 else 1, 1)),
        visible=np.ones(n, bool), shown=lambda it, parts: np.ones(len(parts), bool),
        f_flags=np.array([0x100 if mask_frame else 0]),
        p_b=np.array([3, 1] if mask_frame else [1]), p_mode=np.zeros(n, int), p_page=np.zeros(n, int),
        uv=np.full((1, 6, 2), 0.5), p_uv=np.zeros(n, int), colors=None,
        bbox=lambda items: (0.0, 0.0, 10.0, 10.0),
        **({"m": SimpleNamespace(parts={"a": np.array(layers)})} if layers is not None else {}))


@unittest.skipIf(GLRenderer.get() is None, "нет moderngl или OpenGL 3.3")
class GLTests(unittest.TestCase):
    def setUp(self):
        self.gl = GLRenderer.get()
        self.tex = self.gl.texture(np.full((4, 4, 4), (255, 64, 0, 255), np.uint8))

    def test_square_is_drawn_with_origin_and_flip(self):
        item = Item(0, dict(IDENTITY))
        rgba, origin = self.gl.render(square_puppet(), [self.tex], [item], 2.0)
        self.assertEqual(rgba.shape, (24, 24, 4))                    # 10 единиц x2 + поля по 2
        self.assertEqual(origin, (2.0, 2.0))
        self.assertEqual(tuple(rgba[12, 12]), (255, 64, 0, 255))
        self.assertEqual(rgba[0, 0, 3], 0)
        flipped, origin = self.gl.render(square_puppet(), [self.tex], [item], 2.0, flip=True)
        self.assertEqual(origin, (22.0, 2.0))                        # отражён: точка 0,0 у правого края
        self.assertEqual(tuple(flipped[12, 12]), (255, 64, 0, 255))

    def test_mask_frame_clips_rest_of_frame(self):
        rgba, _ = self.gl.render(square_puppet(mask_frame=True), [self.tex], [Item(0, dict(IDENTITY))], 2.0)
        self.assertEqual(rgba[2 + 3, 2 + 3, 3], 255)                 # внутри маски 4x4 — видно
        self.assertEqual(rgba[2 + 15, 2 + 15, 3], 0)                 # вне маски — обрезано
        other = square_puppet(mask_frame=True, layers=[7150, 4431])    # деталь другого слоя (кадр 84 волшебника)
        rgba, _ = self.gl.render(other, [self.tex], [Item(0, dict(IDENTITY))], 2.0)
        self.assertEqual(rgba[2 + 15, 2 + 15, 3], 255)               # маска её не обрезает


class PuppetTests(unittest.TestCase):
    def test_matrix_rotates_and_scales(self):
        t = dict(tx=5.0, ty=-2.0, rx=0.0, ry=0.0, rz=np.pi / 2, sx=2.0, sy=1.0)
        a, b, c, d, e, f = matrix(t)
        self.assertAlmostEqual(a * 1 + c * 0 + e, 5.0)                          # (1, 0) -> (0, 2) + сдвиг
        self.assertAlmostEqual(b * 1 + d * 0 + f, 0.0)

    def test_canvas_blend_modes_and_mask(self):
        tex = np.zeros((4, 4, 4), np.uint8)
        tex[...] = (255, 128, 0, 255)
        white = np.ones((3, 4), np.float32)
        tri = np.array([[0, 0], [8, 0], [0, 8]], float)
        uv = np.array([[0.5, 0.5]] * 3)
        canvas = Canvas(8, 8)
        canvas.triangle(tri, uv, white, tex, NORMAL)
        self.assertTrue(np.allclose(canvas.rgba[1, 1], (1.0, 128 / 255, 0, 1.0), atol=0.01))
        self.assertEqual(canvas.rgba[7, 7, 3], 0)                                # вне треугольника пусто
        canvas.triangle(tri, uv, white, tex, MULTIPLY)                           # умножение на себя
        self.assertAlmostEqual(float(canvas.rgba[1, 1, 1]), (128 / 255) ** 2, places=2)
        canvas.triangle(tri, uv, white, tex, ADD)
        self.assertAlmostEqual(float(canvas.rgba[1, 1, 0]), 1.0)                 # сложение до предела
        masked = Canvas(8, 8)
        masked.triangle(np.array([[0, 0], [2, 0], [0, 2]], float), uv, white, tex, NORMAL, mask_write=True)
        self.assertEqual(masked.rgba[0, 0, 3], 0)                                # маска не рисуется
        masked.triangle(tri, uv, white, tex, NORMAL, mask_test=True)
        self.assertGreater(masked.rgba[0, 0, 3], 0.9)                            # внутри маски — да
        self.assertEqual(masked.rgba[4, 1, 3], 0)                                # вне маски — нет


class InterfaceTests(unittest.TestCase):
    """Интерфейс UO: числа раскладками, подписи всплывающих, иконки предметов по правилам."""

    def test_digits_hide_leading_places(self):
        self.assertEqual(uo_ui.digits(157, [5, 6, 7]), {5: 7, 6: 5, 7: 1})
        self.assertEqual(uo_ui.digits(7, [5, 6, 7]), {5: 7, 6: None, 7: None})

    def test_number_selects_part_per_digit_in_both_layers(self):
        tracks, parts = uo_ui.number(42, 4, 2, 10)
        self.assertEqual(tracks, {0: 10, 1: 10, 2: None, 3: None, 4: 10, 5: 10, 6: None, 7: None})
        self.assertEqual(parts, {0: 2, 1: 4, 4: 2, 5: 4})

    def test_popup_layouts(self):
        self.assertEqual(pygame_stage.uo_popup_anims("damage", False, False), ["NUM_DAMAGE"])
        self.assertEqual(pygame_stage.uo_popup_anims("damage", True, False), ["NUM_CRITICAL_DAMAGE", "STR_CRITICAL_DAMAGE"])
        self.assertEqual(pygame_stage.uo_popup_anims("damage", True, True), ["NUM_GUARD", "STR_CRITICAL_GUARD"])
        self.assertEqual(pygame_stage.uo_popup_anims("heal", False, False), ["NUM_HEAL"])
        self.assertEqual(pygame_stage.uo_popup_anims("miss", False, False), ["STR_MISS"])

    def test_item_icons_by_kind_tier_and_keywords(self):
        item = lambda i, slot, tier, name="", skills=(): SimpleNamespace(id=i, slot=slot, tier=tier, price=tier,
                                                                          name=name, skills=skills, passives=())
        items = {"a": item("a", "light_sword", 0), "b": item("b", "light_sword", 5), "c": item("c", "light_sword", 9),
                 "d": item("d", "light_sword", 3, skills=("x",)), "e": item("e", "artifact", 1, "Silver Bangle"),
                 "f": item("f", "artifact", 1, "Odd Thing")}
        icons = ItemIcons(items)
        icons._names = ["SWORD_N00_A", "SWORD_N01_A", "SWORD_N02_A", "SWORD_S00_A", "BANGLE_2", "TALISMAN"]
        import re
        icons._rules = ({"c": "SWORD_N00_A"}, [(re.compile("bangle", re.I), "BANGLE_2")])
        self.assertEqual(icons.icon("a"), "SWORD_N00_A")       # обычные — по тиру внутри вида
        self.assertEqual(icons.icon("b"), "SWORD_N01_A")
        self.assertEqual(icons.icon("c"), "SWORD_N00_A")       # вручную важнее правил
        self.assertEqual(icons.icon("d"), "SWORD_S00_A")       # с навыком — особые
        self.assertEqual(icons.icon("e"), "BANGLE_2")          # аксессуар по слову
        self.assertEqual(icons.icon("f"), "TALISMAN")          # без подходящего слова


class ChunkTests(unittest.TestCase):
    def test_step_is_cut_before_each_next_skill(self):
        from game.events import DamageDealt, SkillUsed, TurnStarted
        from pygame_battle import BattleView
        turn, a, b = TurnStarted(1), SkillUsed(1, "x", 2), SkillUsed(2, "counter", 1)
        hit = DamageDealt(1, 2, 5, 10, "x")
        chunks = BattleView._chunks([turn, a, hit, b, hit])
        self.assertEqual(chunks, [[turn, a, hit], [b, hit]])     # контратака — отдельным куском


if __name__ == "__main__":
    unittest.main()
