"""Окно башни без дисплея: набор кликами, подготовка, бой на сцене, награда, магазин, F5.

Работает на временной копии tests/data и временном сохранении; правила — data/tower.json.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
try:
    import pygame
except ImportError:
    pygame = None

from engine.scene import SCENES_DIR
from game.database import Database
from game.tower import DRAFT, OVER, PREPARE, REWARD, SHOP, TOWER_RULES_PATH
from tests.helpers import FIXTURE_DIR

if pygame is not None:
    import pygame_tower as tw
    from pygame_ui import HEIGHT, UI, WIDTH, load_fonts

ROOT = Path(__file__).resolve().parent.parent
SEED = 7                     # забеги в тестах одинаковые
TAKE_Y =tw.TOP + 44 + (620 - tw.TOP - 110) - 36 + 14 if pygame is not None else 0


def setUpModule():
    if pygame is not None:
        pygame.init()


@unittest.skipIf(pygame is None, "pygame-ce is not installed")
class TowerWindowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data_dir = Path(self.tmp) / "data"
        shutil.copytree(FIXTURE_DIR, self.data_dir)
        self.save_path = Path(self.tmp) / "tower.json"
        self.scenes_dir = Path(self.tmp) / "scenes"
        shutil.copytree(SCENES_DIR, self.scenes_dir)
        self.ui = UI(pygame.display.set_mode((WIDTH, HEIGHT)), load_fonts())
        self.app = self.open_app()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def open_app(self):
        return tw.TowerApp(self.save_path, self.data_dir, scenes_dir=self.scenes_dir, seed=SEED)

    def frame(self, events=()):
        self.ui.begin(list(events))
        tw.draw_frame(self.ui, self.app)

    def click(self, x, y, button=1):
        self.frame([pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x, y), button=button)])
        self.frame()

    def draft(self):
        """Набор кликами по «Взять» на первой карточке."""
        while self.app.run.phase == DRAFT:
            self.click(16 + tw.CARD_W // 2, TAKE_Y)

    def fight(self):
        """Кнопка боя, бой до конца, Enter — итог в забег."""
        self.click(100, HEIGHT - 66)
        self.assertTrue(self.app.in_battle)
        self.app.skip()
        self.app.tick(16)
        self.frame()
        self.app.stage.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN), (0, 0))
        self.assertFalse(self.app.in_battle)

    def test_draft_by_clicks_and_the_run_is_saved(self):
        self.frame()
        self.draft()
        run = self.app.run
        self.assertEqual((run.phase, len(run.army.units)), (PREPARE, 3))
        saved = json.loads(self.save_path.read_text(encoding="utf-8"))
        self.assertEqual(len(saved["units"]), 3)
        self.assertEqual(self.open_app().run.to_dict()["units"], run.to_dict()["units"])   # забег продолжается

    def test_floor_battle_reward_and_next_floor(self):
        self.draft()
        self.frame()
        self.fight()
        run = self.app.run
        self.assertEqual(run.phase, REWARD)                   # на этом seed первый этаж выигран
        self.frame()
        for i in (0, 1, 2):                                   # третий не отмечается: можно взять два
            self.click(tw.SIDE_X + 100, tw.TOP + 32 + i * 66 + 30)
        self.assertEqual(self.app.picks, [0, 1])
        taken = [run.reward[0], run.reward[1]]
        self.click(tw.SIDE_X + 100, HEIGHT - 54)
        self.assertEqual(self.app.run.floor, 2)
        for item in taken:
            self.assertTrue(self.app.run.inventory.has(item))

    def test_defeat_screen_starts_a_new_run_and_keeps_the_record(self):
        self.draft()
        run = self.app.run
        run.best = 4
        run.finish(self.app.db, run.battle(self.app.db), won=False)
        self.assertEqual(run.phase, OVER)
        self.frame()
        self.click(100, HEIGHT - 63)                          # «Новый забег»
        self.assertEqual((self.app.run.phase, self.app.run.best), (DRAFT, 4))

    def test_prepare_equipment_reserve_and_tactics(self):
        self.draft()
        self.frame()
        run, app = self.app.run, self.app
        unit = run.fielded[0]
        app.selected = unit.uid
        slot = next(i for i, item in enumerate(unit.state.equipment) if item is not None)
        item = unit.state.equipment[slot]
        app.change_equipment(unit, slot, tw.NONE_ITEM)
        self.assertTrue(run.inventory.has(item))
        app.change_equipment(unit, slot, item)
        self.assertEqual(unit.state.equipment[slot], item)
        self.frame()
        self.click(tw.SIDE_X + 50, tw.TOP + 4 + 24 + 10)      # «В резерв»
        self.assertIn(unit, run.reserve)
        cell = tw.cell_rect(app, 2, 2)
        self.click(*cell.center)                              # из резерва в пустую клетку
        self.assertEqual(run.squad.formation.position_of(unit.uid), (2, 2))
        self.click(tw.SIDE_X + 116 + 50, tw.TOP + 4 + 24 + 10)   # «Тактика»
        self.assertTrue(app.tactics)
        self.frame()
        self.click(80, HEIGHT - 56)                           # «Назад»
        self.assertFalse(app.tactics)

    def test_shop_by_clicks(self):
        rules = json.loads(TOWER_RULES_PATH.read_text(encoding="utf-8"))
        rules["shop"]["every"] = 1                             # магазин после каждого этажа
        rules_path = Path(self.tmp) / "tower_rules.json"
        rules_path.write_text(json.dumps(rules), encoding="utf-8")
        self.app = tw.TowerApp(self.save_path, self.data_dir, rules_path, scenes_dir=self.scenes_dir, seed=SEED)
        self.draft()
        self.app.run.inventory.add_gold(1000)
        self.frame()
        self.fight()
        self.app.run.take(self.app.db, [])
        self.assertEqual(self.app.run.phase, SHOP)
        self.frame()
        units = len(self.app.run.army.units)
        self.click(16 + 85, tw.TOP + 58 + 92 - 20)            # «Нанять» у первого
        self.assertEqual(len(self.app.run.army.units), units + 1)
        self.click(252 + 100, HEIGHT - 54)                    # «Выйти из магазина»
        self.assertEqual(self.app.run.phase, PREPARE)

    def test_f5_picks_up_data_edited_elsewhere(self):
        self.draft()
        unit = self.app.run.fielded[0]
        other = Database.load(self.data_dir)                  # «окно демо» правит класс
        data = other.units[unit.definition.id].to_dict()
        data["stats"]["hp"] = 999
        other.update("units", unit.definition.id, data)
        other.save()
        self.app.handle_key(pygame.K_F5)
        reloaded = self.app.run.army.units[unit.uid]
        self.assertEqual(reloaded.definition.base_stats[next(s for s in reloaded.definition.base_stats
                                                             if s.value == "hp")], 999)

    def test_main_loop_starts_without_a_display(self):
        """Отдельным процессом: main() закрывает pygame, а шрифты сцены кэшируются на модуль."""
        code = ("import pygame_tower as tw; "
                f"tw.main(max_frames=3, save_path={str(self.save_path)!r}, data_dir={str(self.data_dir)!r})")
        env = dict(os.environ, SDL_VIDEODRIVER="dummy", PYGAME_HIDE_SUPPORT_PROMPT="1")
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True,
                                timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.save_path.exists())


if __name__ == "__main__":
    unittest.main()
