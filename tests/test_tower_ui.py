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
    import pygame_tower_prepare as pp
    import pygame_tower_inventory as inv

ROOT = Path(__file__).resolve().parent.parent
SEED = 7                     # забеги в тестах одинаковые


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
        pygame.display.set_mode(tw.SIZE)
        self.ui = tw.make_ui(pygame.Surface(tw.SIZE))
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

    def drag(self, start, end):
        """Нажать в start, отпустить в end (start == end — клик)."""
        self.frame([pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=start, button=1)])
        self.frame([pygame.event.Event(pygame.MOUSEBUTTONUP, pos=end, button=1)])
        self.frame()

    def draft(self):
        """Набор кликами по «Взять» на первой карточке."""
        while self.app.run.phase == DRAFT:
            self.click(*tw.take_button(tw.draft_card(0)).center)

    def fight(self):
        """Кнопка боя, бой до конца, Enter — итог в забег."""
        self.click(*pp.FIGHT.center)
        self.assertTrue(self.app.in_battle)
        self.app.skip()
        self.app.tick(16)
        self.frame()
        self.app.handle_battle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN), (0, 0), 1.0)
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
            card = tw.reward_card(i)
            self.click(card.right - 30, card.centery)        # мимо иконки (у неё своя подсказка)
        self.assertEqual(self.app.picks, [0, 1])
        taken = [run.reward[0], run.reward[1]]
        self.click(*tw.TAKE.center)
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
        self.click(*tw.NEW_RUN.center)                       # «Новый забег»
        self.assertEqual((self.app.run.phase, self.app.run.best), (DRAFT, 4))

    def test_formation_by_dragging_fighters(self):
        self.draft()
        self.frame()
        run, app = self.app.run, self.app
        unit = run.fielded[0]
        empty = next((r, c) for r in range(3) for c in range(3) if run.squad.formation.unit_at(r, c) is None)
        self.drag(pp.unit_point(app, unit.uid), pp.cell_point(app, *empty))      # на пустую клетку
        self.assertEqual(run.squad.formation.position_of(unit.uid), empty)
        other = next(u for u in run.fielded if u is not unit)
        where = run.squad.formation.position_of(other.uid)
        self.drag(pp.unit_point(app, unit.uid), pp.cell_point(app, *where))     # ногами на бойца — обмен
        self.assertEqual(run.squad.formation.position_of(unit.uid), where)
        self.click(*pp.SQUAD_BUTTON.center)                                     # справа — армия
        self.assertEqual(app.view, pp.SQUAD)
        self.drag(pp.unit_point(app, unit.uid), pp.roster_card(5).center)       # с поля в список — резерв
        self.assertIn(unit, run.reserve)
        index = pp.ordered_units(app).index(unit)
        self.drag(pp.roster_card(index).center, pp.cell_point(app, *empty))     # из списка на поле
        self.assertEqual(run.squad.formation.position_of(unit.uid), empty)
        self.click(*pp.SQUAD_BUTTON.center)
        self.assertEqual(app.view, pp.MAIN)                                     # снова враги справа

    def test_dragged_fighter_snaps_to_the_nearest_cell_by_the_feet(self):
        self.draft()
        self.frame()
        run, app = self.app.run, self.app
        unit = run.fielded[0]
        empty = next((r, c) for r in range(3) for c in range(3) if run.squad.formation.unit_at(r, c) is None)
        x, y = pp.cell_point(app, *empty)
        self.drag(pp.unit_point(app, unit.uid), (x + 30, y - 18))           # рядом с клеткой — прилипает
        self.assertEqual(run.squad.formation.position_of(unit.uid), empty)
        self.drag(pp.unit_point(app, unit.uid), (pp.HALF_R.centerx, pp.HALF_R.y + 100))   # далеко — не двигается
        self.assertEqual(run.squad.formation.position_of(unit.uid), empty)

    def test_inventory_filters_sorting_and_putting_items_on(self):
        self.draft()
        run, app = self.app.run, self.app
        for item_id in ("iron_sword", "war_axe", "fire_charm", "short_bow"):
            run.inventory.add(item_id)
        self.frame()
        self.click(*pp.INVENTORY_BUTTON.center)
        self.assertEqual(app.view, pp.INVENTORY)
        entries = inv.inventory_entries(app, app.inv)
        worn = sum(1 for u in run.army.units.values() for i in u.state.equipment if i is not None)
        self.assertEqual(sum(1 for e in entries if e.owner is not None), worn)
        self.click(*inv.show_button(1).center)                              # только свободные
        self.assertTrue(all(e.owner is None for e in inv.inventory_entries(app, app.inv)))
        self.click(*inv.group_button(1).center)                             # только оружие
        weapons = inv.inventory_entries(app, app.inv)
        self.assertTrue(weapons and all(app.db.items[e.item_id].slot in inv.GROUPS["weapons"] for e in weapons))
        app.inv.sort = "stat:phys_atk"
        bonuses = [inv.stat_bonus(app.db.items[e.item_id], pp.Stat.PHYS_ATK)
                   for e in inv.inventory_entries(app, app.inv)]
        self.assertEqual(bonuses, sorted(bonuses, reverse=True))
        app.inv.descending = False
        self.assertEqual(inv.inventory_entries(app, app.inv)[0].item_id,
                         sorted(weapons, key=lambda e: inv.stat_bonus(app.db.items[e.item_id], pp.Stat.PHYS_ATK))[0].item_id)
        archer = next((u for u in run.army.units.values() if "bow" in u.definition.slots), None)
        if archer is not None:
            app.inv.fits = archer.uid                                         # только то, что он наденет
            self.assertTrue(all(app.db.items[e.item_id].slot in archer.definition.slots
                                for e in inv.inventory_entries(app, app.inv)))
        self.click(*inv.RESET_BUTTON.center)
        self.assertEqual((app.inv.show, app.inv.group, app.inv.fits), ("all", "all", None))
        self.frame()
        first = inv.inventory_entries(app, app.inv)
        free_row = next(i for i, e in enumerate(first) if e.owner is None)
        item_id = first[free_row].item_id
        row = inv.table_row(free_row)
        self.click(row.right - 40, row.centery)                            # выбрать свободный
        self.assertEqual(app.inv.picked, item_id)
        count = run.inventory.count(item_id)
        wearers = [u for u in sorted(run.army.units.values(), key=lambda u: u.uid)
                   if app.db.items[item_id].slot in u.definition.slots]
        if wearers:
            self.click(*inv.wear_row(0).center)                               # надеть на первого
            self.assertIn(item_id, wearers[0].state.equipment)
            self.assertLessEqual(run.inventory.count(item_id), count)
        app.inv.show = "equipped"
        self.frame()
        worn_entry = inv.inventory_entries(app, app.inv)[0]
        row = inv.table_row(0)
        self.click(row.right - 40, row.centery)                            # надетый — редактор владельца
        self.assertEqual((app.view, app.selected, app.tab, app.slot, app.back_view),
                         (pp.UNIT, worn_entry.owner, pp.EQUIPMENT, worn_entry.slot, pp.INVENTORY))

    def test_units_list_and_fighter_editor(self):
        self.draft()
        run, app = self.app.run, self.app
        self.frame()
        unit = run.fielded[0]
        self.drag(pp.unit_point(app, unit.uid), pp.unit_point(app, unit.uid))   # клик — редактор
        self.assertEqual((app.view, app.selected), (pp.UNIT, unit.uid))
        self.click(*pp.NEXT.center)
        self.assertNotEqual(app.selected, unit.uid)
        self.click(*pp.PREV.center)
        self.assertEqual(app.selected, unit.uid)
        self.click(*pp.TABS[pp.EQUIPMENT].center)
        self.assertEqual(app.tab, pp.EQUIPMENT)
        slot = next(i for i, item in enumerate(unit.state.equipment) if item is not None)
        item = unit.state.equipment[slot]
        before = pp.preview_stats(app, unit, slot, item)
        bare = pp.preview_stats(app, unit, slot, None)                         # «если снять»
        self.assertTrue(any(bare[s] < before[s] for s in before))
        self.assertEqual(unit.state.equipment[slot], item)                     # сам боец не изменился
        app.change_equipment(unit, slot, pp.NONE_ITEM)
        self.assertTrue(run.inventory.has(item))
        app.change_equipment(unit, slot, item)
        self.frame()
        self.click(*pp.TABS[pp.TACTICS].center)
        self.frame()
        self.click(*pp.FIELD_TOGGLE.center)                                     # «В резерв»
        self.assertIn(unit, run.reserve)
        self.click(*pp.FIELD_TOGGLE.center)                                     # «В отряд»
        self.assertIn(unit, run.fielded)
        self.click(*pp.BACK.center)
        self.assertEqual(app.view, pp.MAIN)
        self.click(*pp.UNITS_BUTTON.center)
        self.assertEqual(app.view, pp.UNITS)
        self.click(*pp.unit_row(1).midleft)                                     # строка списка — редактор
        self.assertEqual((app.view, app.back_view), (pp.UNIT, pp.UNITS))
        self.assertEqual(app.selected, pp.ordered_units(app)[1].uid)
        self.assertTrue(pp.go_back(app))                                        # Esc — обратно в список
        self.assertEqual(app.view, pp.UNITS)

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
        self.click(*tw.hire_button(tw.recruit_card(0)).center)   # «Нанять» у первого
        self.assertEqual(len(self.app.run.army.units), units + 1)
        self.click(*tw.LEAVE.center)                         # «Выйти из магазина»
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


@unittest.skipIf(pygame is None, "pygame-ce is not installed")
class ArtAndTipTests(unittest.TestCase):
    def setUp(self):
        pygame.display.set_mode((64, 64))
        from pygame_art import UI_DIR, ArtBank, Portraits
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(UI_DIR, self.tmp / "ui")
        self.art = ArtBank(self.tmp / "ui")
        self.portraits = Portraits(self.art)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_keys_fall_back_to_the_general_placeholder_until_an_own_image_appears(self):
        self.assertEqual(self.art.find("item/bow/hero_bow")[0], "item")
        self.assertEqual(self.art.find("icon/gold")[0], "icon/gold")
        self.assertEqual(self.art.find("icon/boss")[0], "icon")
        self.assertEqual(self.art.image("skill/fireball", (40, 30)).get_size(), (30, 30))   # вписана целиком
        own = pygame.Surface((10, 10))
        (self.tmp / "ui" / "item" / "bow").mkdir(parents=True)
        pygame.image.save(own, str(self.tmp / "ui" / "item" / "bow.png"))
        fresh = type(self.art)(self.tmp / "ui")
        self.assertEqual(fresh.find("item/bow/hero_bow")[0], "item/bow")                  # своя картинка слота

    def test_drawn_frames_replace_the_coded_plates(self):
        import pygame_tower_style as style
        frame = pygame.Surface((96, 96), pygame.SRCALPHA)
        frame.fill((200, 0, 0, 255))
        frame.fill((0, 0, 200, 255), (32, 32, 32, 32))                     # середина другого цвета
        (self.tmp / "ui" / "frame").mkdir()
        pygame.image.save(frame, str(self.tmp / "ui" / "frame" / "panel.png"))
        (self.tmp / "ui" / "frames.json").write_text('{"panel": {"border": 32, "scale": 1}}', encoding="utf-8")
        stretched = style.nine_slice(frame, (300, 200), 32, 1.0)
        self.assertEqual(stretched.get_size(), (300, 200))
        self.assertEqual(stretched.get_at((5, 5))[:3], (200, 0, 0))         # угол как был
        self.assertEqual(stretched.get_at((150, 100))[:3], (0, 0, 200))     # середина растянута
        skin = style.Skin(type(self.art)(self.tmp / "ui"))
        screen = pygame.Surface((400, 300))
        self.assertTrue(skin.draw(screen, "panel", pygame.Rect(10, 10, 300, 200)))
        self.assertFalse(skin.draw(screen, "button", pygame.Rect(10, 10, 100, 40)))   # нет картинки — кодом
        self.assertEqual(screen.get_at((15, 15))[:3], (200, 0, 0))

    def test_every_class_gets_a_portrait_and_a_figure(self):
        db = Database.load()
        for class_id in db.units:
            self.assertEqual(self.portraits.portrait(class_id, 96).get_size(), (96, 96), class_id)
            figure = self.portraits.full(class_id, (200, 300))
            self.assertLessEqual(figure.get_width(), 200)
            self.assertLessEqual(figure.get_height(), 300)
        self.assertEqual(self.portraits.portrait("no_such_class", 50).get_size(), (50, 50))   # заглушка

    def test_tooltip_appears_only_under_the_cursor(self):
        ui = tw.make_ui(pygame.Surface(tw.SIZE))
        ui.begin([])
        ui.mouse = (100, 100)
        self.assertFalse(ui.tip(pygame.Rect(500, 500, 50, 50), lambda: [("x", (255, 255, 255), "main")]))
        self.assertTrue(ui.tip(pygame.Rect(80, 80, 50, 50), lambda: [("Title", (255, 255, 255), "main")] +
                               [("a long line of help text " * 3, (200, 200, 200), "small")]))
        ui.end()
        self.assertIsNotNone(ui.tip_box)
        self.assertTrue(pygame.Rect(0, 0, *tw.SIZE).contains(ui.tip_box))                  # не вылезает за экран

    def test_tips_describe_items_skills_and_unlock_levels(self):
        from pygame_tips import item_tip, skill_tip
        db = Database.load()
        t = lambda text, **kw: text.format(**kw) if kw else text
        lines = [text for text, *_ in item_tip(t, db, "hero_feather", price=380)]
        self.assertIn("initiative +5", lines)
        self.assertIn("Price: 380", lines)
        volley = [text for text, *_ in skill_tip(t, db, "volley", unlock=12, level=3)]
        self.assertIn("Unlocks at level 12", volley)
        self.assertTrue(any(text.startswith("AP ") for text in volley))


if __name__ == "__main__":
    unittest.main()
