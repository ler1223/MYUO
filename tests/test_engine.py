"""Тесты движка 2.5D: проекция, слои и глубина, трёхмерные эффекты, земля и задник.

Без pygame-ce тесты пропускаются (кроме проекции).
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
try:
    import pygame
except ImportError:
    pygame = None

from engine.projection import Projection
from engine.scene import SceneConfig, SceneObject

if pygame is not None:
    from engine import backdrop as backdrop_module
    from engine.backdrop import Backdrop
    from engine.camera import Camera, ViewCamera
    from engine.fx import Beam, Burst, FxSystem, Pillar, Ring, WrapRing
    from engine.render import GROUND, OVERLAY, UPRIGHT, Part, View, draw_parts
    from engine.sprites import FxLibrary, SpriteBeam, SpriteEffect, SpriteProjectile

FIELD = (0, 52, 1000, 440)


class ProjectionTests(unittest.TestCase):
    def test_depth_shrinks_and_ground_rises_toward_horizon(self):
        p = Projection(horizon=-360, ground=452, focal=1200)
        near, far = p.project(100, 0, 0), p.project(100, 0, 600)
        self.assertEqual(near, (600, 452, 1.0))
        self.assertLess(far[1], near[1])
        self.assertLess(far[2], 1.0)
        self.assertLess(abs(far[0] - 500), abs(near[0] - 500))   # вдали ближе к центру
        lifted = p.project(100, 50, 600)
        self.assertAlmostEqual(far[1] - lifted[1], 50 * far[2])   # высота тоже уменьшается с глубиной
        self.assertIsNone(p.unproject(500, -400))                 # выше горизонта земли нет


@unittest.skipIf(pygame is None, "pygame-ce is not installed")
class LayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((10, 10))

    def setUp(self):
        self.view = View(Projection(), Camera(1.0, (0, 52), (0, 52), pygame.Rect(FIELD)), 0)

    def test_ground_first_then_upright_far_to_near_then_overlay(self):
        order = []
        mark = lambda name: (lambda s, v: order.append(name))
        parts = [Part(OVERLAY, 0, mark("text")), Part(UPRIGHT, 10, mark("near unit")),
                 Part(GROUND, 10, mark("near shadow")), Part(UPRIGHT, 300, mark("far unit")),
                 Part(GROUND, 300, mark("far shadow"))]
        draw_parts(pygame.Surface((1000, 620)), self.view, parts)
        self.assertEqual(order, ["far shadow", "near shadow", "far unit", "near unit", "text"])

    def test_effects_around_a_unit_split_into_back_and_front(self):
        unit_z = 200
        ground_ring = Ring(0, 400, (0, 0, unit_z), (255, 255, 255))
        self.assertEqual([p.layer for p in ground_ring.parts(100)], [GROUND])     # на земле — под юнитом
        for effect in (Ring(0, 400, (0, 80, unit_z), (255, 255, 255)), WrapRing(0, 400, (0, 0, unit_z)),
                       Beam(0, 400, (0, 0, unit_z))):
            depths = sorted(p.depth for p in effect.parts(100))
            self.assertLess(depths[0], unit_z)        # передняя половина перед юнитом
            self.assertGreater(depths[1], unit_z)     # задняя за ним
        pillar = Pillar(0, 400, (0, 0, unit_z + 30))
        self.assertGreater(pillar.parts(100)[0].depth, unit_z)   # столб за юнитом закрыт им

    def test_particles_fly_in_depth_and_sort_around_their_center(self):
        fx = FxSystem()
        fx.burst(0, (0, 100, 200), (255, 200, 100), count=40, speed=4)
        burst = fx.effects[0]
        self.assertIsInstance(burst, Burst)
        depths = {round(p.at(200)[0][2]) for p in burst.particles}
        self.assertGreater(len(depths), 10)                      # разлетаются и вглубь, и к зрителю
        parts = burst.parts(200)
        self.assertEqual(sorted(p.depth for p in parts), [199.5, 200.5])
        draw_parts(pygame.Surface((1000, 620)), self.view, fx.parts(200))
        self.assertEqual(fx.parts(5000), [])                      # отжившие убираются

    def test_view_camera_eases_to_focus_and_back(self):
        cam = ViewCamera(pygame.Rect(FIELD))
        cam.focus(pygame.Rect(400, 250, 200, 150), until=1000)
        cam.update(10)
        self.assertGreater(cam.zoom, 1.0)
        self.assertLess(cam.zoom, cam.goal[0])                    # плавно, а не рывком
        for now in range(10, 1000, 16):
            cam.update(now)
        self.assertAlmostEqual(cam.zoom, cam.goal[0], places=2)
        for now in range(1001, 3000, 16):
            cam.update(now)
        self.assertEqual((cam.zoom, cam.origin), (1.0, (0, 52)))


@unittest.skipIf(pygame is None, "pygame-ce is not installed")
class SpriteEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((10, 10))
        cls.library = FxLibrary()

    def setUp(self):
        self.view = View(Projection(), Camera(1.0, (0, 52), (0, 52), pygame.Rect(FIELD)), 0)

    def test_flipbook_frames_and_duration(self):
        frames = self.library.frames("fire_burst", "main")
        self.assertEqual(len(frames), 16)
        self.assertEqual(frames[0].get_size(), (256, 256))
        self.assertEqual(self.library.duration("fire_burst"), 1000 * 16 // 24)
        self.assertEqual(self.library.duration("burning", 700), 700)        # зацикленный — сколько попросили

    def test_layers_wrap_ground_and_front(self):
        z = 200
        wrap = SpriteEffect(0, 500, self.library, "heal", (0, 90, z)).parts(100)
        self.assertEqual(sorted(p.depth for p in wrap), [z - 0.5, z + 0.5])   # за юнитом и перед ним
        ground = SpriteEffect(0, 500, self.library, "rune_circle", (0, 0, z)).parts(100)
        self.assertEqual([p.layer for p in ground], [GROUND])
        front = SpriteEffect(0, 500, self.library, "hit_spark", (0, 90, z)).parts(100)
        self.assertLess(front[0].depth, z)
        surface = pygame.Surface((1000, 620))
        draw_parts(surface, self.view, wrap + ground + front)
        self.assertGreater(surface.get_bounding_rect().width, 0)              # что-то нарисовано

    def test_opaque_background_of_alpha_effects_becomes_transparent(self):
        stars = self.library.frames("stun_stars", "main")[0]                  # у картинки жёлтый фон без прозрачности
        self.assertEqual(stars.get_at((0, 0)).a, 0)
        self.assertLess(stars.get_width(), 1024)                              # одиночная картинка обрезана по рисунку

    def test_projectile_turns_along_its_flight_and_beam_stretches(self):
        arrow = SpriteProjectile(0, 300, self.library, "arrow", (-300, 90, 0), (300, 90, 0), 40, 0.45)
        beam = SpriteBeam(0, 300, self.library, "chain_arc", (-300, 90, 0), (300, 90, 200))
        surface = pygame.Surface((1000, 620))
        draw_parts(surface, self.view, arrow.parts(150) + beam.parts(150))
        self.assertGreater(surface.get_bounding_rect().width, 100)


@unittest.skipIf(pygame is None, "pygame-ce is not installed")
class BackdropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((10, 10))

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.saved_dir = backdrop_module.GROUND_DIR
        backdrop_module.GROUND_DIR = self.tmp
        checker = pygame.Surface((32, 32))
        checker.fill((200, 40, 40))
        checker.fill((40, 40, 200), (0, 0, 16, 32))
        pygame.image.save(checker, str(self.tmp / "checker.png"))
        rug = pygame.Surface((20, 40))
        rug.fill((250, 250, 0))
        pygame.image.save(rug, str(self.tmp / "rug.png"))

    def tearDown(self):
        backdrop_module.GROUND_DIR = self.saved_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ground_texture_lies_in_perspective_and_is_cached(self):
        scene = SceneConfig(ground_texture="checker.png", ground_tile=100, haze=0)
        backdrop = Backdrop(pygame.Rect(FIELD), self.tmp)
        image = backdrop.surface(scene, 1.0)
        self.assertIs(backdrop.surface(scene, 1.0), image)        # без правок — та же картинка
        near_row, far_row = 452 - 52 - 2, 330 - 52

        def stripes(row):   # сколько раз синяя половина плитки сменяется красной вдоль строки
            blue = [image.get_at((x, row)).b > image.get_at((x, row)).r for x in range(0, 1000)]
            return sum(1 for a, b in zip(blue, blue[1:]) if a != b)
        self.assertGreater(stripes(far_row), stripes(near_row))   # вдали плитки мельче, полос больше
        scene.ground_tile = 200
        self.assertIsNot(backdrop.surface(scene, 1.0), image)     # правка — перерисовка

    def test_ground_object_is_drawn_on_the_ground(self):
        scene = SceneConfig(objects=[SceneObject("rug.png", 0, 100, layer="ground", size=80)], haze=0)
        image = Backdrop(pygame.Rect(FIELD), self.tmp).surface(scene, 1.0)
        _, y, _ = scene.projection().project(0, 0, 100)
        self.assertEqual(image.get_at((500, round(y) - 52))[:3], (250, 250, 0))
        _, far_y, _ = scene.projection().project(0, 0, 600)
        self.assertNotEqual(image.get_at((500, round(far_y) - 52))[:3], (250, 250, 0))


if __name__ == "__main__":
    unittest.main()
