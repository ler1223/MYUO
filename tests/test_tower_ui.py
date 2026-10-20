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

from game.database import Database
from game.tower import DRAFT, OVER, PREPARE, REWARD, SHOP
from tests.helpers import FIXTURE_DIR, tower_rules_data

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
        self.rules_path = Path(self.tmp) / "tower.json.rules"    # правила с группами под фикстуру
        self.rules_path.write_text(json.dumps(tower_rules_data()), encoding="utf-8")
        pygame.display.set_mode(tw.SIZE)
        self.ui = tw.make_ui(pygame.Surface(tw.SIZE))
        self.app = self.open_app()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def open_app(self):
        return tw.TowerApp(self.save_path, self.data_dir, rules_path=self.rules_path, seed=SEED)

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
        self.app.handle_key(pygame.K_RETURN)
        self.assertFalse(self.app.in_battle)

    def test_draft_by_clicks_and_the_run_is_saved(self):
        self.frame()
        self.draft()
        run = self.app.run
        self.assertEqual((run.phase, len(run.army.units)), (PREPARE, 6))
        saved = json.loads(self.save_path.read_text(encoding="utf-8"))
        self.assertEqual(len(saved["units"]), 6)
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

    def test_tactics_table_in_the_style_of_uo(self):
        import pygame_tower_unit as pu
        rule = {"skill": "x", "condition": {"type": "always"}, "self_condition": {"type": "always"},
                "selector": "frontmost"}
        both = pu.set_column(pu.set_column(rule, 0, pu.TARGET, {"type": "hp_below", "value": 0.5}), 1,
                             pu.PRIORITY, "weakest")
        self.assertEqual(pu.rule_items(both), [(pu.TARGET, {"type": "hp_below", "value": 0.5}),
                                               (pu.PRIORITY, "weakest")])
        swapped = pu.set_column(both, 0, pu.SELF, {"type": "has_label", "label": "buff"})   # замена в колонке 1
        self.assertEqual(swapped["condition"], {"type": "always"})
        self.assertEqual(pu.rule_items(pu.set_column(both, 1, None, None)), [(pu.TARGET, both["condition"])])
        self.draft()
        app = self.app
        unit = app.run.fielded[0]
        pp.open_unit(app, unit.uid, pp.MAIN, pp.TACTICS)
        self.frame()
        rules_before = len(unit.tactics.to_list())
        cell = pu.tactic_columns(pu.tactic_row(0))[2]
        self.click(*cell.center)                                   # «Условие 1» первого правила
        self.assertEqual(app.tactic_pick, (0, 0))
        options = [(None, None)] + [(g, v) for g, v, *_ in pu.condition_options(app.db)]
        index = next(i for i, (g, v) in enumerate(options) if v == {"type": "hp_below", "value": 0.5} and g == pu.TARGET)
        box_y = cell.bottom + 6 if cell.bottom + 6 + min(len(options) * 50 + 24, pu.CONTENT_BODY.height - 40) \
            <= pu.CONTENT_BODY.bottom else None
        if box_y is not None and index < 15:
            self.click(cell.x - 60 + 40, box_y + 12 + index * 50 + 20)
            self.assertEqual(unit.tactics.to_list()[0]["condition"], {"type": "hp_below", "value": 0.5})
            self.assertIsNone(app.tactic_pick)
        self.click(*cell.center)
        self.assertTrue(pp.go_back(app))                            # Esc закрывает список, а не редактор
        self.assertEqual((app.tactic_pick, app.view), (None, pp.UNIT))
        self.frame()                                                # кадр без списка (как после Esc в игре)
        self.click(*pu.tactic_columns(pu.tactic_row(rules_before))[1].center)   # «+ Добавить тактику»
        self.assertEqual(len(unit.tactics.to_list()), rules_before + 1)

    def test_passive_tactics_switch_in_the_tower_table(self):
        import pygame_tower_unit as pu
        self.draft()
        app = self.app
        unit = next(u for u in pp.ordered_units(app) if u.passive_ids)
        pp.open_unit(app, unit.uid, pp.MAIN, pp.TACTICS)
        self.frame()
        pid = next(p for p in unit.passive_ids if p in app.db.passives)
        switch = pygame.Rect(pu.CONTENT_BODY.x, pu.RESET_TACTICS.bottom + 14 + 24 + 6, pu.CONTENT_BODY.width, 48)
        self.click(switch.x + 312 + 150, switch.centery)          # вторая плашка — первая пассивка
        self.assertEqual(app.tactic_passive, pid)
        self.frame()
        self.click(*pu.tactic_columns(pu.tactic_row(0))[1].center)   # «+ Добавить тактику» пассивки
        self.assertTrue(unit.has_passive_tactics(pid))
        self.assertEqual(unit.passive_tactics_of(pid).to_list()[0]["skill"], unit.skill_ids[0])
        self.click(*pu.RESET_TACTICS.center)                      # сброс пассивки к данным
        self.assertFalse(unit.has_passive_tactics(pid))
        self.assertTrue(pp.go_back(app))                          # Esc — назад к тактикам юнита
        self.assertIsNone(app.tactic_passive)

    def test_promotion_by_clicks(self):
        path = self.data_dir / "units.json"
        units = json.loads(path.read_text(encoding="utf-8"))
        for class_id, data in units.items():
            if class_id != "orc":
                data["promotions"] = [{"class": "orc", "level": 2}]
        path.write_text(json.dumps(units), encoding="utf-8")
        self.app = self.open_app()
        self.draft()
        app = self.app
        unit = app.run.fielded[0]
        skills = set(unit.definition.skills)
        pp.open_unit(app, unit.uid, pp.MAIN)
        self.frame()
        self.click(*pp.PROMOTE_BUTTON.center)                 # уровень мал: экран путей открывается,
        self.assertEqual(app.view, pp.PROMOTE)
        self.click(*pp.promote_button(pp.promote_card(0, 1)).center)
        self.assertEqual(unit.definition.id, unit.state.definition_id)   # но повысить нельзя
        self.assertNotEqual(unit.definition.id, "orc")
        unit.state.level = 2
        self.frame()
        self.click(*pp.promote_button(pp.promote_card(0, 1)).center)
        promoted = app.run.army.units[unit.uid]
        self.assertEqual((promoted.definition.id, app.view), ("orc", pp.UNIT))
        self.assertTrue(skills <= set(promoted.definition.skills))
        saved = json.loads(self.save_path.read_text(encoding="utf-8"))
        self.assertIn(["orc"], [[u["state"]["definition_id"]] for u in saved["units"]])

    def test_shop_by_clicks(self):
        rules = tower_rules_data(shop={"every": 1})            # магазин после каждого этажа
        rules_path = Path(self.tmp) / "tower_rules.json"
        rules_path.write_text(json.dumps(rules), encoding="utf-8")
        self.app = tw.TowerApp(self.save_path, self.data_dir, rules_path, seed=SEED)
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
        (self.tmp / "ui" / "item" / "bow.png").unlink(missing_ok=True)       # своей картинки слота ещё нет
        self.art = type(self.art)(self.tmp / "ui")
        self.assertEqual(self.art.find("item/bow/hero_bow")[0], "item")
        self.assertEqual(self.art.find("icon/gold")[0], "icon/gold")
        self.assertEqual(self.art.find("icon/nothing_drawn_yet")[0], "icon")
        self.assertEqual(self.art.image("skill/fireball", (40, 30)).get_size(), (30, 30))   # вписана целиком
        own = pygame.Surface((10, 10))
        (self.tmp / "ui" / "item" / "bow").mkdir(parents=True, exist_ok=True)
        pygame.image.save(own, str(self.tmp / "ui" / "item" / "bow.png"))
        fresh = type(self.art)(self.tmp / "ui")
        self.assertEqual(fresh.find("item/bow/hero_bow")[0], "item/bow")                  # своя картинка слота

    def test_temporary_sprites_replace_old_stand_ins_but_not_own_sprites(self):
        from pygame_stage import UNITS_DIR, SpriteBank
        folder = self.tmp / "ref"
        folder.mkdir()
        image = pygame.Surface((30, 100), pygame.SRCALPHA)
        image.fill((255, 0, 0, 255), (0, 0, 10, 100))                       # красная полоса слева
        for class_id in ("fighter", "knight"):
            pygame.image.save(image, str(folder / f"{class_id}.png"))
        (folder / "units.json").write_text(json.dumps({"sprites": {
            "fighter": {"height": 100, "ratio": 1.0, "flip": True},
            "knight": {"height": 100, "ratio": 1.8}}}), encoding="utf-8")
        bank = SpriteBank(UNITS_DIR, folder)
        self.assertEqual(bank.sprite_for("fighter"), "ref:fighter")          # вместо old_knight
        self.assertAlmostEqual(bank.ratio("ref:knight"), 1.8)                # всадник выше человека
        flipped = bank.image("ref:fighter.png")
        self.assertEqual(flipped.get_at((29, 50))[:3], (255, 0, 0))           # отражён: полоса справа
        self.assertFalse(str(SpriteBank(UNITS_DIR, None).sprite_for("fighter")).startswith("ref:"))  # без папки
        own = SpriteBank(UNITS_DIR, folder)
        own.sprites.clear()
        own.config["sprites"]["fighter"] = {"sheet": "x", "height": 1}
        own._add_temporary(json.loads((folder / "units.json").read_text(encoding="utf-8")))
        self.assertEqual(own.sprite_for("fighter"), "fighter")               # свой спрайт важнее

    def test_skill_icon_is_shared_by_its_kind(self):
        from game.database import Database
        from pygame_art import passive_key, skill_key
        db = Database.load()
        shutil.rmtree(self.tmp / "ui" / "skill", ignore_errors=True)            # значков типов ещё нет
        self.art = type(self.art)(self.tmp / "ui")
        self.assertEqual(skill_key(db, "attack"), "skill/attack/attack")
        self.assertEqual(self.art.find(skill_key(db, "attack"))[0], "skill")              # пока общая заглушка
        (self.tmp / "ui" / "skill").mkdir(parents=True, exist_ok=True)
        pygame.image.save(pygame.Surface((10, 10)), str(self.tmp / "ui" / "skill" / "attack.png"))
        fresh = type(self.art)(self.tmp / "ui")
        self.assertEqual(fresh.find(skill_key(db, "attack"))[0], "skill/attack")          # значок типа
        self.assertTrue(passive_key(db, next(iter(db.passives))).startswith("passive/"))

    def test_sheet_is_cut_by_cells_without_the_halo(self):
        from tools import cut_ui_sheet as cutter
        sheet = pygame.Surface((1536, 1024), pygame.SRCALPHA)
        sheet.fill((0, 0, 0, 0))
        sheet.fill((255, 200, 50, 6), (60, 60, 300, 300))                   # ореол — почти прозрачный
        sheet.fill((200, 160, 60, 255), (100, 100, 200, 120))               # элемент ячейки 1
        sheet.fill((20, 30, 90, 255), (700, 650, 80, 80))                   # ячейка 8, два куска
        sheet.fill((20, 30, 90, 255), (800, 650, 20, 80))
        parts = cutter.cut(sheet)
        self.assertEqual(set(parts), {1, 8})
        self.assertLessEqual(parts[1].get_width(), 200 + 8)                 # ореол обрезан
        self.assertGreaterEqual(parts[8].get_width(), 120)                  # куски одной ячейки вместе
        self.assertEqual(parts[1].get_at((0, 0)).a, 0)
        files = cutter.batch_files(cutter.PROMPTS.read_text(encoding="utf-8"))
        self.assertEqual(files[1][1][1], "frame/panel")
        self.assertEqual(len(files[6][1]), 10)

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
        lines = [text for text, *_ in item_tip(t, db, "dove_plume", price=380)]
        self.assertIn("initiative +10", lines)
        self.assertIn("Price: 380", lines)
        bash = [text for text, *_ in skill_tip(t, db, "shield_bash", unlock=15, level=3)]
        self.assertIn("Unlocks at level 15", bash)
        self.assertTrue(any(text.startswith("AP ") for text in bash))


if __name__ == "__main__":
    unittest.main()
