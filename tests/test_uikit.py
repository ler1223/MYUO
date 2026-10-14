"""Движок интерфейса uikit: шрифт с кириллицей, текст по центру, раскладка, рамки по телу,
полосы из кусков, слои и перекрытие мыши, замеры картинок; личные имена бойцов башни."""
import json
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

from game.tower import DRAFT, TowerRun, load_names
from tests.helpers import DB
from tests.test_tower import rules

ROOT = Path(__file__).resolve().parent.parent
RUSSIAN = "абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"

if pygame is not None:
    from uikit import layout, load_gui
    from uikit import widgets as w
    from uikit.skin import Images, Skin, nine_slice
    from uikit.text import TextStyle


def setUpModule():
    if pygame is not None:
        pygame.init()
        pygame.display.set_mode((64, 64))


@unittest.skipIf(pygame is None, "pygame-ce is not installed")
class TextTests(unittest.TestCase):
    def setUp(self):
        self.screen = pygame.Surface((800, 400))
        self.gui = load_gui(self.screen)

    def test_bundled_font_has_every_russian_letter(self):
        theme = json.loads((ROOT / "assets" / "ui" / "theme.json").read_text(encoding="utf-8"))
        for face, path in theme["fonts"].items():
            self.assertTrue((ROOT / "assets" / path).is_file(), path)
            font = self.gui.texts.fonts.get(face, 24)
            metrics = font.metrics(RUSSIAN + "…×↑↓")
            self.assertTrue(all(m is not None for m in metrics), face)       # у каждой буквы есть глиф

    def test_text_sits_in_the_middle_of_its_box_by_capital_height(self):
        style = self.gui.ts("body")
        for height in (40, 60, 90):
            box = pygame.Rect(10, 10, 400, height)
            self.screen.fill((0, 0, 0))
            caps = self.gui.texts.draw(self.screen, "НАЗАД", style.but(shadow=None), box, "center")
            self.assertLessEqual(abs(caps.centery - box.centery), 1)
            self.assertLessEqual(abs(caps.centerx - box.centerx), 1)
            lit = [y for y in range(box.top, box.bottom) if any(self.screen.get_at((x, y))[0] > 128
                                                              for x in range(caps.left, caps.right))]
            self.assertLessEqual(abs((lit[0] + lit[-1]) / 2 - box.centery), 2)  # нарисованные буквы — по центру

    def test_long_text_is_cut_with_an_ellipsis_and_wrapped_by_words(self):
        texts, style = self.gui.texts, self.gui.ts("body")
        cut = texts.fit("Наносит урон всем врагам в ряду", style, 150)
        self.assertTrue(cut.endswith("…"))
        self.assertLessEqual(texts.width(cut, style), 150)
        lines = texts.wrap("Наносит урон всем врагам в ряду и поджигает их", style, 220)
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(texts.width(line, style) <= 220 for line in lines))

    def test_outline_and_shadow_do_not_move_the_letters(self):
        plain = TextStyle(size=30, shadow=None)
        rich = TextStyle(size=30, shadow=(0, 0, 0), outline=(0, 0, 0))
        box = pygame.Rect(0, 0, 300, 60)
        self.assertEqual(self.gui.texts.draw(self.screen, "Щит", plain, box, "center"),
                         self.gui.texts.draw(self.screen, "Щит", rich, box, "center"))


@unittest.skipIf(pygame is None, "pygame-ce is not installed")
class LayoutTests(unittest.TestCase):
    def test_columns_share_the_rest_by_weights_and_fill_the_box(self):
        box = pygame.Rect(10, 0, 1000, 50)
        parts = layout.cols(box, [200, 1.0, 2.0], 10)
        self.assertEqual(parts[0].width, 200)
        self.assertEqual(parts[2].width, 2 * parts[1].width + (parts[2].width - 2 * parts[1].width))
        self.assertEqual(parts[-1].right, box.right)
        self.assertEqual(parts[1].x, parts[0].right + 10)

    def test_grid_place_and_centered_row(self):
        cells = layout.grid(pygame.Rect(0, 0, 310, 500), 5, 3, 40, 10, 6)
        self.assertEqual((cells[3].x, cells[3].y, cells[3].width), (0, 46, 96))
        self.assertEqual(layout.place(pygame.Rect(0, 0, 100, 100), (20, 10), "bottomright").bottomright, (100, 100))
        row = layout.row_of(pygame.Rect(0, 0, 100, 10), [20, 20], 10)
        self.assertEqual((row[0].x, row[1].right), (25, 75))
        self.assertEqual(layout.inset(pygame.Rect(0, 0, 100, 100), 10, 20), pygame.Rect(10, 20, 80, 60))


@unittest.skipIf(pygame is None, "pygame-ce is not installed")
class SkinTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "frame").mkdir()
        (self.tmp / "bar").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def save(self, key, surface):
        pygame.image.save(surface, str(self.tmp / f"{key}.png"))

    def test_corners_stay_middle_stretches_and_edge_motif_is_kept(self):
        frame = pygame.Surface((96, 96), pygame.SRCALPHA)
        frame.fill((200, 0, 0, 255))
        frame.fill((0, 0, 200, 255), (32, 32, 32, 32))
        out = nine_slice(frame, (300, 200), 32, 1.0)
        self.assertEqual(out.get_at((5, 5))[:3], (200, 0, 0))
        self.assertEqual(out.get_at((150, 100))[:3], (0, 0, 200))
        motif = pygame.Surface((100, 100), pygame.SRCALPHA)
        motif.fill((0, 0, 200, 255))
        motif.fill((200, 0, 0, 255), (40, 0, 20, 10))
        red = lambda s: sum(1 for x in range(300) if s.get_at((x, 2))[:3] == (200, 0, 0))
        self.assertGreater(red(nine_slice(motif, (300, 100), 20, 1.0)), 40)
        self.assertEqual(red(nine_slice(motif, (300, 100), 20, 1.0, (20, 0))), 20)

    def test_border_per_axis_keeps_side_ornaments_of_a_low_wide_frame(self):
        frame = pygame.Surface((120, 40), pygame.SRCALPHA)
        frame.fill((0, 0, 200, 255))
        frame.fill((200, 0, 0, 255), (0, 0, 30, 40))                 # широкое украшение слева во всю высоту
        out = nine_slice(frame, (400, 80), (30, 8), 1.0)
        self.assertEqual(out.get_at((25, 40))[:3], (200, 0, 0))      # не сжато в полоску
        self.assertEqual(out.get_at((200, 40))[:3], (0, 0, 200))

    def test_states_of_different_size_are_aligned_by_their_body(self):
        normal = pygame.Surface((100, 40), pygame.SRCALPHA)
        normal.fill((0, 0, 0, 255))
        normal.fill((0, 0, 200, 255), (10, 10, 80, 20))               # тело 10 px от краёв
        active = pygame.Surface((100, 100), pygame.SRCALPHA)
        active.fill((0, 0, 0, 255))
        active.fill((0, 200, 0, 255), (10, 40, 80, 50))               # украшение сверху: тело ниже
        self.save("frame/tab", normal)
        self.save("frame/tab_active", active)
        frames = {"tab": {"border": 12, "scale": 1, "fill": [10, 10, 10, 10]},
                  "tab_active": {"border": 12, "scale": 1, "fill": [10, 40, 10, 10]}}
        skin = Skin(Images(self.tmp), frames, {})
        rect = pygame.Rect(50, 100, 300, 60)
        body = skin.body("tab", rect)
        screen = pygame.Surface((400, 300))
        skin.draw(screen, "tab_active", rect, body)
        self.assertEqual(screen.get_at(body.center)[:3], (0, 200, 0))
        self.assertEqual(screen.get_at((body.x - 1, body.y + 5))[:3], (0, 0, 0))   # линия рамки на месте
        self.assertGreater(screen.get_at((body.x + 1, body.y + 1))[1], 150)        # тело с первого пикселя
        self.assertEqual(skin.around("tab_active", body).top, body.top - 40)        # украшение — наружу

    def test_bar_is_assembled_from_an_end_and_a_body_at_any_length(self):
        end = pygame.Surface((20, 20), pygame.SRCALPHA)
        end.fill((200, 160, 60, 255))                                 # золотой конец
        end.fill((0, 200, 0, 255), (12, 5, 8, 10))                    # начало заливки
        body = pygame.Surface((4, 20), pygame.SRCALPHA)
        body.fill((200, 160, 60, 255))
        body.fill((0, 200, 0, 255), (0, 5, 4, 10))
        self.save("bar/hp_end", end)
        self.save("bar/hp_body", body)
        skin = Skin(Images(self.tmp), {}, {"hp": {"inner": [12, 5, 15]}})
        for width in (60, 300):
            screen = pygame.Surface((400, 40))
            rect = pygame.Rect(10, 10, width, 20)
            self.assertTrue(skin.draw_bar(screen, "hp", rect, 0.5))
            self.assertEqual(screen.get_at((12, 20))[:3], (200, 160, 60))           # левый конец целиком
            self.assertEqual(screen.get_at((rect.right - 3, 20))[:3], (200, 160, 60))  # правый конец — зеркало
            inner = skin.bar_inner("hp", rect)
            self.assertEqual(screen.get_at((inner.x + 2, inner.centery))[:3], (0, 200, 0))
            self.assertLess(screen.get_at((inner.right - 3, inner.centery))[1], 100)   # пустая часть темнее
        self.assertFalse(skin.draw_bar(pygame.Surface((10, 10)), "exp", pygame.Rect(0, 0, 50, 10), 1))


@unittest.skipIf(pygame is None, "pygame-ce is not installed")
class GuiTests(unittest.TestCase):
    def setUp(self):
        self.screen = pygame.Surface((400, 300))
        self.gui = load_gui(self.screen)

    def test_later_layers_are_drawn_over_and_block_the_mouse_below(self):
        gui = self.gui
        gui.begin([])
        order = []
        gui.later(2, lambda: order.append("top"))
        gui.later(1, lambda: order.append("plates"))
        order.append("now")
        gui.block(pygame.Rect(0, 0, 100, 100), 2)
        gui.end()
        self.assertEqual(order, ["now", "plates", "top"])
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(50, 50), button=1)
        gui.begin([click])
        gui.mouse = (50, 50)
        self.assertFalse(gui.hovered(pygame.Rect(0, 0, 200, 200)))           # под окном слоя 2
        self.assertEqual(gui.clicked(pygame.Rect(0, 0, 200, 200)), 0)
        self.assertEqual(gui.clicked(pygame.Rect(0, 0, 200, 200), layer=2), 1)
        gui.end()

    def test_button_label_stays_put_between_states(self):
        """Наведение и выбор не двигают подпись вкладки: тело общее, текст по нему."""
        gui = self.gui
        rect = pygame.Rect(40, 60, 300, 72)
        boxes = []
        for selected, mouse in ((False, (-5, -5)), (False, rect.center), (True, (-5, -5))):
            gui.begin([])
            gui.mouse = mouse
            body = w.family_frame(gui, "tab", rect, w.state_of(gui.hovered(rect), selected))
            boxes.append(body)
        self.assertEqual(boxes[0], boxes[1])
        self.assertEqual(boxes[0], boxes[2])


@unittest.skipIf(pygame is None, "pygame-ce is not installed")
class MeasureToolTests(unittest.TestCase):
    def test_body_of_a_frame_and_the_parts_of_a_bar(self):
        from tools import measure_ui_art as measure
        frame = pygame.Surface((120, 60), pygame.SRCALPHA)
        frame.fill((220, 180, 90, 255))
        frame.fill((20, 30, 70, 255), (14, 9, 90, 40))
        self.assertEqual(measure.fill_insets(frame), [14, 9, 16, 11])
        bar = pygame.Surface((200, 30), pygame.SRCALPHA)
        bar.fill((0, 0, 0, 0))
        bar.fill((220, 180, 90, 255), (0, 0, 24, 30))                 # ромб на конце выше полосы
        bar.fill((220, 180, 90, 255), (176, 0, 24, 30))
        bar.fill((220, 180, 90, 255), (24, 8, 152, 14))
        bar.fill((30, 180, 60, 255), (24, 11, 152, 8))                # заливка
        end, body, inner = measure.bar_parts(bar)
        self.assertGreaterEqual(end.get_width(), 24)
        self.assertEqual(body.get_height(), 30)
        self.assertEqual(inner[1:], [11, 19])


class NameTests(unittest.TestCase):
    def test_fighters_get_different_names_matching_the_figure(self):
        run = TowerRun.new(DB, rules(), seed=7)
        while run.phase == DRAFT:
            run.pick(DB, run.offers[0])
        names = [u.state.nickname for u in run.army.units.values()]
        self.assertTrue(all(names))
        self.assertEqual(len(set(names)), len(names))
        female = json.loads((ROOT / "data" / "names.json").read_text(encoding="utf-8"))["female_classes"]
        for unit in run.army.units.values():
            self.assertIn(unit.state.nickname, load_names(unit.definition.id))
            self.assertEqual(unit.state.nickname in load_names(female[0]), unit.definition.id in female)
        self.assertEqual(run.rebuild(DB).army.units[next(iter(run.army.units))].state.nickname, names[0])

    def test_every_name_has_a_russian_translation(self):
        data = json.loads((ROOT / "data" / "names.json").read_text(encoding="utf-8"))
        ru = json.loads((ROOT / "data" / "lang" / "ru.json").read_text(encoding="utf-8"))
        for name in data["male"] + data["female"]:
            self.assertIn(name, ru)


if __name__ == "__main__":
    unittest.main()
