"""Тесты окна без дисплея: синтетические клики, ввод текста и выбор в списках по всем вкладкам.

Окно рисуется в фиктивный видеодрайвер SDL. Каждый тест работает на временной копии
tests/data и временном файле сохранения, настоящая папка data/ не трогается.
Без установленного pygame-ce тесты пропускаются.
"""
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
except ImportError:  # окно необязательно: ядро проверяется и без него
    pygame = None

from game.database import Database
from game.events import DamageDealt, EffectApplied, EffectExpired, PassiveTriggered
from game.stats import Stat
from game.tactics import condition_to_dict
from engine.scene import SCENES_DIR
from tests.helpers import FIXTURE_DIR

if pygame is not None:
    import demo_pygame as d
    from engine.camera import MAX_ZOOM, Camera
    from engine.render import View
    from pygame_battle import FIELD_RECT
    from pygame_scene_editor import FORM_TOP, FORM_X, LABEL_W, ROW_H
    from game.scenario import DEMO_AP, DEMO_SEED
    from pygame_stage import Motion
    from pygame_world import NONE_ITEM
    from pygame_ui import UI, load_fonts

X, TOP = 222, 44                      # левый край формы и верх под вкладками
FX = X + 110                          # поля формы реакции
NEW = (16 + 46, 620 - 84 + 12)        # «+ Новый» под списком объектов
DELETE = (112 + 47, 620 - 84 + 12)
RECRUIT = (500 + 120, 104 + 5 * 28 + 10 + 24 + 12)
SELECTED_EQUIP_Y = 104 + 3 * 84 + 4 + 76 + 12


def setUpModule():
    if pygame is not None:
        pygame.init()


@unittest.skipIf(pygame is None, "pygame-ce is not installed")
class WindowTestCase(unittest.TestCase):
    """Приложение на копии данных и помощники для кликов, ввода и выпадающих списков."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data_dir = Path(self.tmp) / "data"
        shutil.copytree(FIXTURE_DIR, self.data_dir)
        self.save_path = Path(self.tmp) / "setup.json"
        self.scenes_dir = Path(self.tmp) / "scenes"
        shutil.copytree(SCENES_DIR, self.scenes_dir)
        self.props_dir = Path(self.tmp) / "props"
        self.props_dir.mkdir()
        post = pygame.Surface((20, 60), pygame.SRCALPHA)       # декорация для страницы объектов
        post.fill((150, 110, 70))
        pygame.image.save(post, str(self.props_dir / "post.png"))
        self.ui = UI(pygame.display.set_mode((d.WIDTH, d.HEIGHT)), load_fonts())
        self.app = self.open_app()
        self.db = self.app.db

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def open_app(self, lang=None):
        return d.App(Database.load(self.data_dir), 1, self.save_path, lang, self.scenes_dir, self.props_dir)

    def tab(self, name):
        index = [n for n, _ in self.app.tabs].index(name)
        self.app.switch(index)
        self.frame()
        return self.app.tabs[index][1]

    def frame(self, events=()):
        self.ui.begin(list(events))
        d.draw_frame(self.ui, self.app, False, 0)

    def click(self, x, y, button=1):
        self.frame([pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x, y), button=button)])
        self.frame()

    def key(self, k, text=""):
        self.frame([pygame.event.Event(pygame.KEYDOWN, key=k, unicode=text)])

    def typing(self, text):
        for ch in text:
            self.key(ord(ch.lower()) if ch.isascii() else 0, ch)

    def enter(self):
        self.key(pygame.K_RETURN)
        self.frame()
        self.frame()

    def write(self, x, y, text):
        """Кликнуть в поле ввода, стереть содержимое, набрать text и подтвердить."""
        self.click(x, y)
        self.assertIsNotNone(self.ui.focus, f"no input field at {(x, y)}")
        for _ in range(30):
            self.key(pygame.K_BACKSPACE)
        self.typing(text)
        self.enter()

    def pick(self, x, y, search):
        """Открыть выпадающий список, набрать поиск и взять первый найденный вариант."""
        self.click(x, y)
        self.assertIsNotNone(self.ui.popup, f"no dropdown at {(x, y)}")
        self.typing(search)
        found = self.ui.popup.filtered()
        self.assertTrue(found, f"nothing found for {search!r}")
        self.enter()
        return found[0][0]

    def toggle(self, x, y, search):
        """Список с отметками: открыть, найти, отметить первую строку, закрыть."""
        self.click(x, y)
        self.assertTrue(self.ui.popup is not None and self.ui.popup.multi, f"no multiselect at {(x, y)}")
        self.typing(search)
        self.assertTrue(self.ui.popup.filtered(), f"nothing found for {search!r}")
        self.frame()
        box = self.ui.popup_box
        self.click(box.x + 20, box.y + 26 + 11)
        self.key(pygame.K_ESCAPE)
        self.frame()

    def play(self, seed=None):
        """Перейти на вкладку боя (правки применяются и сохраняются) и доиграть бой."""
        self.tab("Battle")
        view = self.app.view
        if seed is not None:
            view.restart(seed)
        while not view.sim.finished:
            view.step(0)
        return view.sim.events


class SkillTacticsSquadTests(WindowTestCase):
    def test_skill_builder_tactics_equipment_and_save(self):
        db = self.db
        editor = self.tab("Skills")
        self.click(*NEW)
        sid = editor.skill_id
        self.write(X + 176, TOP + 12, "Sweep")
        self.write(X + 80, TOP + 42, "2")                         # цена AP
        self.write(X + 188, TOP + 42, "1")                        # цена PP
        self.assertEqual(self.pick(X + 486, TOP + 42, "row"), "row")
        self.write(X + 608, TOP + 42, "2")                        # удары
        self.write(X + 739, TOP + 42, "150")                      # точность
        self.toggle(X + 156, TOP + 72, "melee")
        self.assertEqual(self.pick(X + 590, TOP + 72, "infantry"), "infantry")
        self.write(X + 689, TOP + 72, "1.25")
        self.toggle(X + 216, TOP + 102, "knight")
        skill = db.skills[sid]
        self.assertEqual((skill.name, skill.ap_cost, skill.pp_cost, skill.area, skill.hits, skill.accuracy),
                         ("Sweep", 2, 1, "row", 2, 150))
        self.assertEqual((skill.tags, dict(skill.bonus_vs)), (("melee",), {"infantry": 1.25}))
        self.assertIn(sid, db.units["knight"].skills)

        py = TOP + 178                                            # первая часть урона
        self.write(X + 210, py, "0.7")
        self.assertEqual(self.pick(X + 428, py, "hp"), "hp")
        self.write(X + 498, py, "0.1")
        self.toggle(X + 584, py, "slashing")
        self.click(X + 678, py)                                   # тип урона от оружия
        part = db.skills[sid].parts[0]
        self.assertEqual([(s.stat.value, s.coef) for s in part.scaling], [("phys_atk", 1.0), ("hp", 0.1)])
        self.assertEqual((part.power, part.tags, part.weapon_tags), (0.7, ("slashing",), True))
        self.click(X + 325, TOP + 133)                            # + часть
        self.assertEqual(self.pick(X + 141, py + 28, "magical"), "magical")

        ay0 = TOP + 122 + 46 + 3 * 28 + 6
        self.click(X + 325, ay0 + 11)                             # + эффект
        ay = ay0 + 56
        self.assertEqual(self.pick(X + 122, ay, "stun"), "stun")
        self.assertEqual(self.pick(X + 395, ay, "hp_below"), "hp_below")
        self.assertEqual(self.pick(X + 524, ay, "30"), 0.3)
        self.assertEqual(db.skills[sid].applies[0].to_dict(),
                         {"effect_id": "stun", "to": "target", "condition": {"type": "hp_below", "value": 0.3}})

        self.tab("Tactics")
        ty = TOP + 96
        self.assertEqual(self.pick(X + 596, ty, "sweep"), sid)
        self.assertEqual(self.pick(X + 74, ty, "hp_below"), "hp_below")
        self.assertEqual(self.pick(X + 168, ty, "70"), 0.7)
        self.assertEqual(self.pick(X + 453, ty, "weakest"), "weakest")
        knight = self.app.setup.player.units[1]
        self.assertEqual(knight.tactics.to_list()[0], {"skill": sid, "self_condition": {"type": "hp_below", "value": 0.7},
                                                       "condition": {"type": "always"}, "selector": "weakest"})
        self.click(X + 104, ty + 2 * 28 + 4)                      # + правило
        self.assertEqual(len(knight.tactics.rules), 3)
        self.click(X + 753, ty + 2 * 28)                          # удалить третье
        self.assertEqual(len(knight.tactics.rules), 2)

        self.tab("Squads")
        self.click(16 + 220, 104 + 38)                            # рыцарь в клетке (0, 1)
        self.pick(16 + 77, SELECTED_EQUIP_Y, "-")                 # снять меч
        self.assertIsNone(self.app.setup.player.units[1].state.equipment[0])
        self.pick(16 + 77, SELECTED_EQUIP_Y, "iron")
        self.pick(16 + 3 * 162 + 77, SELECTED_EQUIP_Y, "fire")    # артефакт даёт тег
        knight = self.app.setup.player.units[1]
        self.assertEqual(knight.state.equipment, ["iron_sword", "shield", None, "fire_charm"])
        self.assertIn("fire_resistant", knight.tags)
        self.assertEqual(self.pick(*RECRUIT, "rider"), "rider")
        self.assertEqual([u.name for u in self.app.setup.player.reserve()], ["Rider"])

        self.play()
        self.assertFalse(self.app.dirty or self.app.data_dirty)
        reopened = self.open_app()
        self.assertEqual(reopened.db.skills[sid], db.skills[sid])
        self.assertEqual(reopened.setup.player.units[1].state.equipment, ["iron_sword", "shield", None, "fire_charm"])
        self.assertEqual([r.skill_id for r in reopened.setup.player.units[1].tactics.rules], [sid, "attack"])


class ClassEditorTests(WindowTestCase):
    def test_edit_create_and_delete_class(self):
        db = self.db
        editor = self.tab("Classes")
        stat_row = lambda stat: TOP + 63 + list(Stat).index(stat) * 24
        self.write(X + 144, stat_row(Stat.HP), "100")
        self.write(X + 206, stat_row(Stat.EVASION), "1.5")        # рост за уровень
        self.write(X + 566, TOP + 12, "5")                        # макс. AP
        knight = db.units["knight"]
        self.assertEqual((knight.base_stats[Stat.HP], knight.growth[Stat.EVASION], knight.ap_max), (100, 1.5, 5))
        live = self.app.setup.player.units[1]                     # юнит расстановки сразу пересобран
        self.assertEqual((live.max_hp, live.ap.max), (116, 5))

        rx, row_y = X + 262, (lambda n: TOP + 46 + n * 30)
        self.toggle(rx + 280, row_y(0), "cavalry")
        self.toggle(rx + 280, row_y(0), "infantry")               # снять пехоту
        self.assertEqual(db.units["knight"].tags, ("cavalry", "armored"))
        sy = TOP + 130
        self.assertEqual(self.pick(rx + 280, sy + 12, "lance"), "lance")
        self.assertEqual(self.pick(rx + 248, sy + 42, "remove"), "")   # убрать слот щита
        self.assertEqual(db.units["knight"].slots, ("light_sword", "medium_armor", "artifact", "lance"))
        self.assertEqual(self.app.setup.player.units[1].state.equipment, ["iron_sword", None, None, None])

        self.toggle(rx + 280, row_y(1), "fireball")
        ty = TOP + 34 + 18 + 11 * 24 + 8 + 40 + 12
        self.assertEqual(self.pick(X + 586, ty, "fireball"), "fireball")
        self.toggle(rx + 280, row_y(1), "fireball")               # навык убран: правило с ним тоже
        self.assertEqual([r.skill_id for r in db.units["knight"].tactics.rules], ["attack"])

        self.click(*NEW)
        new_id = editor.unit_id
        self.write(X + 176, TOP + 12, "Gryphon")
        self.toggle(rx + 280, row_y(0), "flying")
        self.assertEqual((db.units[new_id].name, db.units[new_id].tags), ("Gryphon", ("flying",)))
        self.tab("Squads")
        self.assertEqual(self.pick(*RECRUIT, "gryphon"), new_id)
        self.click(16 + 70, 104 + 38)                             # в клетку (0, 0)
        self.assertEqual(self.app.setup.player_squad.formation.unit_at(0, 0).definition.id, new_id)
        self.play()

        editor = self.tab("Classes")
        editor.unit_id = new_id
        self.frame()
        self.click(*DELETE)
        self.assertNotIn(new_id, db.units)
        self.assertIsNone(self.app.setup.player_squad.formation.unit_at(0, 0))
        self.play()
        reloaded = Database.load(self.data_dir)
        self.assertEqual(reloaded.units["knight"].slots, ("light_sword", "medium_armor", "artifact", "lance"))
        self.assertNotIn(new_id, reloaded.units)


class ItemAndTagEditorTests(WindowTestCase):
    def test_items_tags_rules_and_language(self):
        db = self.db
        tags = self.tab("Tags")
        self.click(*NEW)
        tag_id = tags.tag_id
        self.write(X + 166, TOP + 12, "Undead")
        n_rules = len(db.rules)
        self.click(X + 280, TOP + 67)                             # + правило
        row = TOP + 56 + 84 + n_rules * 28 + 12
        self.toggle(X + 112, row, "light")
        self.toggle(X + 472, row, "undead")
        self.write(X + 592, row, "2")
        self.assertEqual(db.rules[-1].to_dict(), {"attack": ["light"], "attack_not": [], "target": [tag_id],
                                                  "damage": 2.0, "hit": 1.0})
        tags.tag_id = "piercing"
        self.frame()
        self.click(X + 630, TOP + 12)                             # «мимо блока»
        self.assertTrue(db.tags["piercing"].unblockable)

        items = self.tab("Items")
        self.click(*NEW)
        item_id = items.item_id
        self.write(X + 210, TOP + 12, "Sun Blade")
        self.assertEqual(self.pick(X + 210, TOP + 42, "light_sword"), "light_sword")
        ly = lambda n: TOP + 72 + n * 30
        for n, search in enumerate(("flying", "light", "fireball", "avenger")):
            self.toggle(X + 310, ly(n), search)
        my0 = TOP + 188
        self.click(X + 340, my0 + 11)                             # + модификатор
        self.write(X + 434, my0 + 56, "12")
        item = db.items[item_id]
        self.assertEqual((item.slot, item.tags, item.damage_tags, item.skills, item.passives),
                         ("light_sword", ("flying",), ("light",), ("fireball",), ("avenger",)))
        self.assertEqual([m.to_dict() for m in item.modifiers], [{"stat": "phys_atk", "op": "FLAT", "value": 12}])

        self.tab("Squads")
        self.click(16 + 220, 104 + 38)
        self.assertEqual(self.pick(16 + 77, SELECTED_EQUIP_Y, "sun"), item_id)
        knight = self.app.setup.player.units[1]
        self.assertEqual((knight.stat(Stat.PHYS_ATK), knight.weapon_damage_tags), (38, ("light",)))

        # Орк становится нежитью: удар светлым клинком по нему удваивается правилом тега.
        orc = db.units["orc"].to_dict()
        db.update("units", "orc", dict(orc, tags=orc["tags"] + [tag_id]))
        self.app.data_changed()
        amounts = []
        for seed in range(1, 13):
            amounts += [e.amount for e in self.play(seed) if isinstance(e, DamageDealt)
                        and e.source == 1 and e.target == 11 and e.cause == "power_strike" and not e.crit]
        self.assertTrue(any(a > 44 for a in amounts), amounts)   # без правила не больше (38 - 9) * 1.5

        items = self.tab("Items")
        items.item_id = item_id
        self.frame()
        self.click(*DELETE)
        self.assertIsNone(self.app.setup.player.units[1].state.equipment[0])
        tags = self.tab("Tags")
        tags.tag_id = tag_id
        self.frame()
        self.click(*DELETE)
        self.assertEqual((tag_id in db.units["orc"].tags, len(db.rules)), (False, n_rules))
        self.play()
        self.assertEqual(Database.load(self.data_dir).to_dict(), db.to_dict())

        self.click(*d.language_rect(self.app).center)             # все вкладки рисуются и на русском
        self.assertEqual(self.app.t.lang, "ru")
        for name, _ in self.app.tabs:
            self.tab(name)


class AreaEffectFieldTests(WindowTestCase):
    def test_areas_effect_behaviour_and_field_size(self):
        db = self.db
        areas = self.tab("Areas")
        self.click(*NEW)
        aid = areas.area_id
        self.write(X + 176, TOP + 12, "Cross")
        cell = lambda row, col: (X + 60 + (col + 4) * 28 + 13, TOP + 86 + (row + 4) * 28 + 13)
        for offset in ((0, -1), (0, 1), (-1, 0), (1, 0), (0, 0)):   # крест, затем убрать центр
            self.click(*cell(*offset))
        self.assertEqual(db.areas[aid].cells, {(0, -1), (0, 1), (-1, 0), (1, 0)})

        effects = self.tab("Effects")
        self.click(*NEW)
        eid = effects.effect_id
        self.write(X + 176, TOP + 12, "Plague")
        self.write(X + 96, TOP + 42, "1")                          # 1 ход
        add_rule = (X + 405, TOP + 92 + 44 + 3 * 28 + 6 + 11)
        row = lambda n: TOP + 52 + n * 30
        back = (d.WIDTH - 76, TOP + 12)
        self.click(*add_rule)                                     # 1: в начале хода урон 3 себе
        self.write(FX + 208, row(3), "3")
        self.click(*back)
        self.click(*add_rule)                                     # 2: по истечении перекинуться на соседей
        self.assertEqual(self.pick(FX + 95, row(0), "effect_expired"), "effect_expired")
        self.assertEqual(self.pick(FX + 326, row(2), "this effect"), "@this")
        self.assertEqual(self.pick(FX + 85, row(3), "apply_effect"), "apply_effect")
        self.assertEqual(self.pick(FX + 290, row(3), "plague"), eid)
        self.assertEqual(self.pick(FX + 85, row(4), "allies"), "allies")
        self.assertEqual(self.pick(FX + 255, row(4), "cross"), aid)
        self.click(*back)
        got = [(t.event, t.action, t.amount, t.effect_id, t.effect_filter, t.to, t.to_area)
               for t in db.effects[eid].triggers]
        self.assertEqual(got, [("turn_start", "damage", 3, None, None, "owner", None),
                               ("effect_expired", "apply_effect", 1, eid, "@this", "allies", aid)])

        skill = db.skills["poison_arrow"].to_dict()
        db.update("skills", "poison_arrow", dict(skill, applies=[{"effect_id": eid, "to": "target"}]))
        self.app.data_changed()
        jumps = 0
        for seed in range(1, 15):
            events = self.play(seed)
            for i, e in enumerate(events):
                if isinstance(e, EffectExpired) and e.effect_id == eid:
                    jumps += sum(isinstance(n, EffectApplied) and n.effect_id == eid for n in events[i + 1:i + 4])
        self.assertGreater(jumps, 0)

        self.tab("Squads")                                        # поле 5x5 на 12 юнитов
        for x, value in ((497, "5"), (583, "5"), (693, "12")):
            self.write(x, TOP + 12, value)
        self.assertEqual(db.formation.to_dict(), {"rows": 5, "cols": 5, "max_units": 12})
        grid = lambda r, c: (16 + c * 90 + 40, 104 + r * 50 + 22)
        for n, pos in enumerate([(4, 4), (3, 0), (2, 2), (4, 0), (0, 4), (3, 3), (1, 4), (4, 2), (1, 1)]):
            self.pick(*RECRUIT, ("goblin", "orc", "rider", "mage")[n % 4])
            self.click(*grid(*pos))
        self.assertEqual(len(self.app.setup.player_squad.formation), 12)   # тринадцатый не поместился
        self.assertIn("full", self.app.message)
        self.play()
        self.tab("Squads")                                        # обратно 3x3: лишние в резерве
        self.write(497, TOP + 12, "3")
        self.write(583, TOP + 12, "3")
        formation = self.app.setup.player_squad.formation
        self.assertEqual((formation.rows, formation.cols, len(self.app.setup.player.units)), (3, 3, 13))
        self.assertEqual(len(self.app.setup.player.reserve()), 13 - len(formation))


class ReactionEditorTests(WindowTestCase):
    def test_passive_reaction_form_and_effect_thorns(self):
        db = self.db
        passives = self.tab("Passives")
        self.click(*NEW)
        pid = passives.passive_id
        row = lambda n: TOP + 48 + n * 30
        r = db.passives[pid].reaction
        self.assertEqual((r.event, r.action, r.skill_id, r.to), ("attacked", "use_skill", "attack", "actor"))
        self.write(FX + 100, TOP + 12, "Riposte")
        self.assertEqual(self.pick(FX + 516, row(0), "round"), "round")
        self.assertEqual(self.pick(FX + 60, row(1), "hp_below"), "hp_below")
        self.assertEqual(self.pick(FX + 179, row(1), "90"), 0.9)
        self.toggle(FX + 280, row(2), "melee")
        self.toggle(FX + 140, TOP + 312, "orc")                  # владелец: орк
        r = db.passives[pid].reaction
        self.assertEqual((r.limit, r.attack_tags, condition_to_dict(r.self_condition)),
                         ("round", ("melee",), {"type": "hp_below", "value": 0.9}))
        self.assertIn(pid, db.units["orc"].passives)

        self.click(FX + 85, row(3))                               # на «удар по юниту» прикрытия нет
        self.assertTrue(all(value != "cover" for value, _ in self.ui.popup.options))
        self.key(pygame.K_ESCAPE)
        self.assertEqual(self.pick(FX + 95, row(0), "targeted"), "targeted")
        self.assertEqual(self.pick(FX + 85, row(3), "cover"), "cover")
        r = db.passives[pid].reaction
        self.assertEqual((r.event, r.whose, r.action), ("targeted", "ally", "cover"))
        self.assertEqual(self.pick(FX + 95, row(0), "attacked"), "attacked")
        self.assertEqual(db.passives[pid].reaction.action, "apply_effect")    # прикрытие сменилось
        self.assertEqual(self.pick(FX + 85, row(3), "use_skill"), "use_skill")
        self.assertEqual(self.pick(FX + 85, row(4), "actor"), "actor")

        effects = self.tab("Effects")
        self.click(*NEW)
        eid = effects.effect_id
        self.click(X + 405, TOP + 92 + 44 + 3 * 28 + 6 + 11)      # + правило: форма открывается сразу
        self.assertEqual(effects.editing, 0)
        erow = lambda n: TOP + 52 + n * 30
        self.assertEqual(self.pick(FX + 95, erow(0), "attacked"), "attacked")
        self.assertEqual(self.pick(FX + 85, erow(3), "damage"), "damage")
        self.write(FX + 208, erow(3), "6")
        self.assertEqual(self.pick(FX + 85, erow(4), "actor"), "actor")
        self.click(d.WIDTH - 76, TOP + 12)                        # < Назад
        self.assertIsNone(effects.editing)
        t = db.effects[eid].triggers[0]
        self.assertEqual((t.event, t.whose, t.action, t.amount, t.to), ("attacked", "self", "damage", 6, "actor"))

        for seed in range(1, 8):                                  # шипы на рыцаре, орк контратакует
            self.tab("Battle")
            self.app.view.restart(seed)
            self.app.view.sim.units[1].add_effect(db.effects[eid], source=1)
            events = self.play()
            if any(isinstance(e, PassiveTriggered) and e.passive_id == pid for e in events) and \
                    any(isinstance(e, DamageDealt) and e.cause == eid for e in events):
                break
        else:
            self.fail("no riposte or thorns in 7 battles")


class SkillVisualTests(WindowTestCase):
    def test_skill_visuals(self):
        from pygame_battle import skill_visual
        db = Database.load(self.data_dir)
        knight = db.create_unit("knight", 1, equipment=["iron_sword"])
        archer = db.create_unit("archer", 2)
        self.assertEqual(skill_visual(db.skills["attack"], knight), ("melee", None, "slashing"))   # тип от меча
        self.assertEqual(skill_visual(db.skills["poison_arrow"], archer), ("arrow", "poison", "piercing"))
        self.assertEqual(skill_visual(db.skills["fireball"], None), ("magic", "fire", "slashing"))
        self.assertEqual(skill_visual(db.skills["magic_bolt"], None)[:2], ("magic", "arcane"))
        self.assertEqual(skill_visual(db.skills["heal"], None)[0], "heal")
        self.assertEqual(skill_visual(db.skills["enchant_wind"], None)[0], "support")

    def test_weapon_kinds(self):
        from pygame_battle import weapon_kind
        db = Database.load(self.data_dir)
        self.assertEqual(weapon_kind(db.create_unit("knight", 1, equipment=["iron_sword"]), "melee"), "sword")
        self.assertEqual(weapon_kind(db.create_unit("orc", 2), "melee"), "axe")            # слот класса без предмета
        self.assertEqual(weapon_kind(db.create_unit("rider", 3), "melee"), "spear")
        self.assertEqual(weapon_kind(db.create_unit("archer", 4), "arrow"), "bow")
        self.assertEqual(weapon_kind(None, "magic"), "staff")


class StageTests(WindowTestCase):
    def play(self, stage, view):
        """Весь бой кадр за кадром; какие эффекты появлялись и у кого были движения."""
        now, spawned, moved = 1000, set(), set()
        while not view.sim.finished:
            view.consume(view.sim.step(), now)
            while now < view.busy_until:
                self.ui.begin([])
                d.draw_frame(self.ui, self.app, False, now)
                spawned.update(type(e).__name__ for e in stage.fx.effects)
                moved.update(uid for uid, motions in stage.motions.items() if motions)
                now += 40
        return spawned, moved

    def test_demo_battle_is_the_default_and_t_cycles_the_battles(self):
        stage = self.tab("Stage")
        view = stage.battle_view
        self.assertEqual((stage.mode, view.seed), ("demo", DEMO_SEED))
        classes = {unit.definition.id for unit in view.sim.units.values()}
        self.assertEqual(classes, set(self.db.units))          # демонстрация: все классы справочника
        self.assertEqual(max(u.ap.max for u in view.sim.units.values()), DEMO_AP)
        spawned, _ = self.play(stage, view)
        self.assertTrue({"SpriteEffect", "SpriteProjectile"} <= spawned, spawned)   # спрайтовые удары и снаряды
        for mode in ("showcase", "setup", "demo"):
            stage.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_t), (0, 0))
            self.assertEqual(stage.mode, mode)

    def test_stage_plays_test_squads_with_skill_visuals(self):
        stage = self.tab("Stage")
        stage.next_mode()                                      # тестовые отряды пяти классов
        view = self.app.battle_view()
        self.assertIs(view, stage.battle_view)
        self.assertIsNot(view, self.app.view)                 # у вкладки свой бой
        classes = {unit.definition.id for unit in view.sim.units.values()}
        self.assertEqual(classes, {"rider", "cleric"})        # в тестовых данных есть только эти из пяти
        spawned, moved = self.play(stage, view)
        self.assertTrue({"FloatText", "SpriteEffect"} <= spawned, spawned)   # таран, лечение — спрайтами
        self.assertTrue(moved)                                # рывки, отскоки, отбрасывание
        self.assertEqual(stage.deaths.keys(), {uid for uid, u in view.sim.units.items() if not u.is_alive})

    def test_step_actions_match_the_data_check(self):
        from tests.test_assets import STEP_ACTIONS
        self.assertEqual(set(self.tab("Stage").steps), STEP_ACTIONS)

    def test_windup_comes_from_visuals_and_targets_from_timeline(self):
        from game.events import DamageDealt, SkillUsed
        stage = self.tab("Stage")
        stage.next_mode()
        view = stage.battle_view
        # визуал в assets описан для навыков UO; навыкам тестовых данных — свой
        stage.skill_visuals["lance_charge"] = {"windup": 420, "cast": [], "hit": []}
        stage.skill_visuals["rider/attack"] = {"windup": 300, "cast": [], "hit": []}
        rider = next(u for u in view.sim.units.values() if u.definition.id == "rider")
        self.assertEqual(stage.windup(SkillUsed(rider.uid, "lance_charge", 11)),
                         stage.skill_visuals["lance_charge"]["windup"])
        self.assertEqual(stage.spec(rider, "attack"), stage.skill_visuals["rider/attack"])     # свой визуал класса
        self.assertEqual(stage.spec(rider, "unknown_skill"), stage.skill_visuals["_defaults"]["melee"])
        used = SkillUsed(rider.uid, "attack", 11)
        view.timeline = [(0, used), (400, DamageDealt(rider.uid, 11, 5, 10, "attack")),
                         (500, DamageDealt(rider.uid, 12, 5, 10, "attack")), (600, SkillUsed(11, "attack", 1))]
        self.assertEqual(stage._targets_of(view, used), [11, 12])

    def test_your_squads_use_fallback_sprites(self):
        stage = self.tab("Stage")
        stage.next_mode()
        stage.next_mode()
        self.frame()                                          # расстановка обновляется при отрисовке
        view = stage.battle_view
        self.assertEqual(stage.mode, "setup")
        self.assertIn("knight", {u.definition.id for u in view.sim.units.values()})
        knight = next(u for u in view.sim.units.values() if u.definition.id == "knight")
        classes = stage.bank.config["fallback"]["classes"]
        classes["knight"] = "rider"
        self.assertEqual(stage.bank.sprite_id(knight), "rider")               # явное соответствие класса — первым
        del classes["knight"]
        self.assertEqual(stage.bank.sprite_id(knight), "knight")              # иначе свой спрайт
        del stage.bank.config["sprites"]["knight"]                            # без него — по тегу или по умолчанию
        self.assertEqual(stage.bank.sprite_id(knight), "paladin")
        rider = next(u for u in view.sim.units.values() if u.definition.id == "rider")
        self.assertEqual(stage.stage[rider.uid].sprite, "rider")
        self.assertTrue(stage.stage[rider.uid].tall)
        self.assertGreater(stage.bank.ratio("rider"), stage.bank.ratio("paladin") * 1.4)   # всадник выше пехоты
        self.play(stage, view)


    def test_units_covering_the_attack_become_transparent(self):
        stage = self.tab("Stage")
        self.frame()                                           # демонстрация: юнитов много, они перекрываются
        view = View(stage.scene.projection(), Camera(1.0, FIELD_RECT.topleft, FIELD_RECT.topleft, FIELD_RECT), 500)
        far_first = sorted(stage.stage, key=lambda uid: -stage.stage[uid].z)
        rects = {uid: stage.unit_rect(uid, view) for uid in far_first}
        # Дальний юнит и ближний, который его заметно перекрывает.
        back, front = next((a, b) for i, a in enumerate(far_first) for b in far_first[i + 1:]
                           if stage.stage[b].z < stage.stage[a].z
                           and rects[b].inflate(-rects[b].width // 4, -rects[b].height // 8).colliderect(rects[a]))
        stage.focus = (frozenset([back]), 0, 1000)
        stage._last_draw = 0
        stage._update_alpha(far_first, view)
        self.assertLess(stage.alpha[front], 255)               # закрывающий стал прозрачным
        self.assertEqual(stage.alpha[back], 255)               # участник атаки — нет
        stage._update_alpha(far_first, View(view.projection, view.cam, 5000))   # атака кончилась
        self.assertEqual(stage.alpha[front], 255)

    def test_camera_moves_in_on_the_attack_and_back(self):
        from game.events import SkillUsed
        stage = self.tab("Stage")
        view = stage.battle_view
        rider = next(u for u in view.sim.units.values() if u.definition.id == "rider")
        target = next(u.uid for u in view.sim.units.values() if stage.facing(u.uid) != stage.facing(rider.uid))
        used = SkillUsed(rider.uid, "attack", target)
        view.timeline = [(1000, used)]
        stage.spawn(view, used, 1000)
        self.assertGreater(stage.camera_view.goal[0], 1.0)     # наезд на атакующего и цель
        stage.camera_view.settle()
        self.assertGreater(stage.camera_view.zoom, 1.0)
        stage.camera_view.update(stage.camera_view.focus_until + 1)
        self.assertEqual(stage.camera_view.goal[0], 1.0)       # после удара — снова обзор
        stage.camera_view.auto = False
        stage.spawn(view, used, 9000)
        self.assertEqual(stage.camera_view.goal[0], 1.0)       # наезды выключены (клавиша C)

    def test_motions_happen_in_the_world(self):
        stage = self.tab("Stage")
        uid = next(iter(stage.stage))
        place = stage.stage[uid]
        stage._move(uid, Motion(0, 100, 100, 100, dz=200))     # рывок вглубь
        feet, _ = stage.world_at(uid, 150)
        self.assertEqual(feet[2], place.z + 200)
        view = View(stage.scene.projection(), Camera(), 150)
        self.assertLess(view.p(feet)[2], view.p((place.x, 0, place.z))[2])   # вдали спрайт мельче


class SceneEditorTests(WindowTestCase):
    def saved(self, editor):
        return json.loads((self.scenes_dir / f"{editor.scene_id}.json").read_text(encoding="utf-8"))

    def page(self, name):
        from pygame_scene_editor import PAGES
        self.click(20, form_y(0) + PAGES.index(name) * 22 + 8)

    def test_dragging_a_cell_moves_its_column_and_row_and_saves(self):
        editor = self.tab("Scene")
        scene = editor.scene
        before_col, before_row = list(scene.columns), list(scene.rows)
        handle = editor.handles()[(1, 0)]                      # средний ряд, дальняя колонна
        down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=handle)
        editor.handle_event(down, handle)
        self.assertEqual(editor.drag, (1, 0))
        target = (handle[0] - 30, handle[1] - 20)              # дальше от центра и глубже
        editor.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=target, rel=(-30, -20), buttons=(1, 0, 0)), target)
        editor.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=target), target)
        self.assertGreater(scene.columns[0], before_col[0])
        self.assertGreater(scene.rows[1], before_row[1])
        self.assertEqual(scene.columns[1:], before_col[1:])    # остальные линии на месте
        moved = editor.handles()[(1, 0)]
        self.assertAlmostEqual(moved[0], target[0], delta=2)   # ручка пришла под курсор
        self.assertAlmostEqual(moved[1], target[1], delta=2)
        self.assertEqual(self.saved(editor)["columns"], scene.columns)
        self.assertIs(self.tab("Stage").scene, scene)          # общая со Stage

    def test_grid_ground_and_backdrop_pages(self):
        editor = self.tab("Scene")
        scene = editor.scene
        self.write(FORM_X + LABEL_W + 5, form_y(0) + 5, "-500")   # «Горизонт»
        self.assertEqual(scene.horizon, -500)
        lines = len(scene.rows)
        self.click(FORM_X + LABEL_W + lines * 56 + 5, form_y(1) + 5)   # + ряд
        self.assertEqual(len(scene.rows), lines + 1)
        self.assertEqual(scene.rows[-1] - scene.rows[-2], scene.rows[-2] - scene.rows[-3])   # шаг продолжен
        self.page("Backdrop")
        self.pick(FORM_X + LABEL_W + 5, form_y(0) + 5, "meadow")
        self.assertEqual(scene.backdrop, "meadow.png")
        self.page("Ground")
        self.write(FORM_X + LABEL_W + 5, form_y(1) + 5, "300")   # «Плитка»
        self.assertEqual(scene.ground_tile, 300)
        self.assertEqual(self.saved(editor)["backdrop"], "meadow.png")

    def test_scenes_page_creates_switches_renames_and_deletes(self):
        editor = self.tab("Scene")
        first = editor.scene_id
        self.page("Scenes")
        self.click(FORM_X + 5, form_y(1) + 5)                  # «Новая»
        created = editor.scene_id
        self.assertNotEqual(created, first)
        self.assertIn(created, editor.store.ids())
        self.assertEqual(self.app.scene_id, created)           # окно запомнило выбор
        self.assertIs(self.tab("Stage").scene, editor.scene)
        self.tab("Scene")
        self.write(FORM_X + LABEL_W * 2 + 245, form_y(0) + 5, "Castle")   # название
        self.assertEqual(self.saved(editor)["name"], "Castle")
        self.click(FORM_X + 205, form_y(1) + 5)                # «Удалить»
        self.assertNotIn(created, editor.store.ids())
        self.assertIn(editor.scene_id, editor.store.ids())     # выбрана одна из оставшихся
        self.assertIn(first, editor.store.ids())

    def test_objects_are_added_selected_dragged_and_sorted_by_depth(self):
        editor = self.tab("Scene")
        scene = editor.scene
        self.page("Objects")
        self.click(FORM_X + LABEL_W + 195, form_y(0) + 5)      # «Добавить»
        self.assertEqual(len(scene.objects), 1)
        obj = scene.objects[0]
        self.assertEqual(obj.image, "post.png")
        editor.selected = None
        view = View(scene.projection(), Camera(1.0, FIELD_RECT.topleft, FIELD_RECT.topleft), 0)
        grab = editor.stage.prop_rect(obj, view).center
        editor.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=grab), grab)
        self.assertEqual(editor.selected, 0)                   # выбран кликом
        z_before = obj.z
        to = (grab[0] + 60, grab[1] + 30)                      # правее и ближе
        editor.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=to, rel=(60, 30), buttons=(1, 0, 0)), to)
        editor.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=to), to)
        self.assertGreater(obj.x, 0)
        self.assertLess(obj.z, z_before)
        self.assertEqual(self.saved(editor)["objects"][0]["x"], obj.x)
        self.assertEqual([p.depth for p in editor.stage.prop_parts(view)], [obj.z])   # сортируется по глубине
        self.click(FORM_X + 95, form_y(2) + 5)                 # стоит -> лежит на земле
        self.assertEqual(obj.layer, "ground")
        self.assertEqual(editor.stage.prop_parts(view), [])    # лежащие рисуются в заднике
        self.click(FORM_X + 329, form_y(2) + 5)                # «Удалить»
        self.assertEqual(scene.objects, [])


def form_y(line):
    return FORM_TOP + line * ROW_H


class WorldTests(WindowTestCase):
    def test_hero_moves_camera_follows_and_chest_is_opened(self):
        world = self.tab("World")
        start = world.state.hero
        for now in range(1000, 2000, 16):
            world.update(now, (1.0, 0.0))
        self.assertGreater(world.state.hero[0], start[0] + 200)
        self.assertLess(abs(world.cam[0] - world.state.hero[0]), 60)     # камера догнала героя
        world.state.hero = (260, 1040)                                   # у сундука на лугу
        self.frame()
        world.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e), (0, 0))
        self.assertIn("chest_meadow", world.state.opened)
        self.assertEqual(world.state.inventory.count("herb"), 3)
        self.assertTrue((Path(self.tmp) / "world.json").exists())        # прогресс сохранён

    def test_panel_equips_items_from_the_inventory_on_the_main_squad(self):
        world = self.tab("World")
        world.state.inventory.add("iron_sword")
        world.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_i), (0, 0))
        self.assertTrue(world.panel)
        squad = self.app.setup.player_squad
        knight = next(u for u in squad.formation.units if "light_sword" in u.definition.slots)
        slot = knight.definition.slots.index("light_sword")
        was = knight.state.equipment[slot]
        world.change_equipment(knight, slot, NONE_ITEM)
        self.assertIsNone(knight.state.equipment[slot])
        self.assertEqual(world.state.inventory.count("iron_sword"), 1 + (was == "iron_sword"))
        world.change_equipment(knight, slot, "iron_sword")
        self.assertEqual(knight.state.equipment[slot], "iron_sword")
        self.assertTrue(self.app.dirty)                                  # расстановка сохранится
        self.frame()                                                     # панель рисуется

    def test_enemy_contact_starts_a_stage_battle_and_the_result_returns(self):
        world = self.tab("World")
        enemy = world.world.enemy("scouts")
        world.state.hero = (enemy.x - 40, enemy.z)
        world.state.enemies["scouts"].x, world.state.enemies["scouts"].z = enemy.x, enemy.z
        world.update(5000, (0.0, 0.0))
        self.assertEqual(world.pending, "scouts")
        self.assertEqual(self.app.tabs[self.app.tab][0], "Stage")        # бой на вкладке Stage
        stage = self.app.stage
        self.assertEqual(stage.mode, "world")
        view = stage.battle_view
        self.assertEqual({u.definition.id for u in view.sim.defender.formation.units}, {"goblin"})
        while not view.sim.finished:
            view.step(0)
        won = view.sim.winner_id == view.sim.attacker.id
        stage.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN), (0, 0))
        self.assertEqual(self.app.tabs[self.app.tab][0], "World")
        self.frame()
        self.assertIsNone(world.pending)
        self.assertEqual("scouts" in world.state.defeated, won)
        self.assertNotEqual(stage.mode, "world")                          # Stage вернулась к своему бою


class ZoomAndWindowTests(WindowTestCase):
    def test_zoom_keeps_point_under_cursor_pan_and_reset(self):
        stage = self.tab("Stage")
        cam = stage.camera_view
        under = lambda pos: (cam.origin[0] + (pos[0] - FIELD_RECT.left) / cam.zoom,
                             cam.origin[1] + (pos[1] - FIELD_RECT.top) / cam.zoom)
        cursor = (300, 250)
        before = under(cursor)
        cam.zoom_at(cursor, 4)                                 # x2
        self.assertEqual(cam.zoom, 2.0)
        self.assertTrue(cam.manual)                            # игрок выбрал зум: наезды не мешают
        self.assertAlmostEqual(under(cursor)[0], before[0])    # точка под курсором не уехала
        self.assertAlmostEqual(under(cursor)[1], before[1])
        cam.pan(-10_000, -10_000)                              # дальше края поля не утащить
        vw, vh = cam.view_size()
        self.assertEqual(cam.origin, (FIELD_RECT.right - vw, FIELD_RECT.bottom - vh))
        cam.zoom_at(cursor, 100)
        self.assertEqual(cam.zoom, MAX_ZOOM)
        cam.zoom_at((500, 600), 1)                             # колесо над логом поле не трогает
        self.assertEqual(cam.zoom, MAX_ZOOM)
        stage.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_HOME, unicode=""), (0, 0))
        self.assertEqual((cam.zoom, cam.origin, cam.manual), (1.0, FIELD_RECT.topleft, False))

    def test_large_window_maps_mouse_and_draws_the_field(self):
        window = d.Window((1600, 992))
        self.assertAlmostEqual(window.scale, 1.6)
        self.assertEqual(window.to_logical((800, 496)), (500, 310))
        click = window.logical_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(160, 160), button=1))
        self.assertEqual(click.pos, (100, 100))
        self.ui = UI(window.canvas, load_fonts())
        self.ui.transform = window.to_logical
        stage = self.tab("Stage")
        stage.camera_view.zoom_at((300, 250), 4)
        self.app.battle_view().consume(self.app.battle_view().sim.step(), 1000)
        self.ui.begin([])
        d.draw_frame(self.ui, self.app, False, 1300, window)
        self.assertTrue(stage.native)
        self.assertAlmostEqual(stage.camera(window.scale, window.offset).scale, 3.2)   # окно 1.6 x зум 2
        self.assertEqual(window.surface.get_size(), (1600, 992))
        self.tab("Scene")                                      # редактор тоже рисует поле в окно
        self.ui.begin([])
        d.draw_frame(self.ui, self.app, False, 1400, window)


if __name__ == "__main__":
    unittest.main()
