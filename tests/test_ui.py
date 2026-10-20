"""Тесты окна без дисплея: синтетические клики, ввод текста и выбор в списках по всем вкладкам.

Окно рисуется в фиктивный видеодрайвер SDL. Каждый тест работает на временной копии
tests/data и временном файле сохранения, настоящая папка data/ не трогается.
Без установленного pygame-ce тесты пропускаются.
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
except ImportError:  # окно необязательно: ядро проверяется и без него
    pygame = None

from game.database import Database
from game.events import DamageDealt, EffectApplied, EffectExpired, PassiveTriggered
from game.stats import Stat
from game.tactics import condition_to_dict
from tests.helpers import FIXTURE_DIR

if pygame is not None:
    import demo_pygame as d
    from game.scenario import DEMO_SEED
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
        self.ui = UI(pygame.display.set_mode((d.WIDTH, d.HEIGHT)), load_fonts())
        self.app = self.open_app()
        self.db = self.app.db

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def open_app(self, lang=None):
        return d.App(Database.load(self.data_dir), 1, self.save_path, lang)

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

        # тактики пассивок: своя таблица правил у каждой пассивки юнита
        pid = knight.passive_ids[0]
        py_head = TOP + 84 + 2 * 28 + 4 + 34 + 22                 # заголовок первой пассивки
        add_rule = (X + 24 + 80, py_head + 24 + 20 + 4 + 12)      # «+ правило» её таблицы
        self.click(*add_rule)
        self.assertTrue(knight.has_passive_tactics(pid))
        self.assertEqual(knight.passive_tactics_of(pid).to_list()[0]["skill"], "attack")
        self.click(X + 192 + 100, py_head - 2 + 11)               # сброс пассивки к данным
        self.assertFalse(knight.has_passive_tactics(pid))
        self.click(*add_rule)
        self.assertTrue(knight.has_passive_tactics(pid))

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
        restored = reopened.setup.player.units[1]
        self.assertTrue(restored.has_passive_tactics(pid))        # тактики пассивок пережили сохранение
        self.assertEqual(restored.passive_tactics_of(pid).to_list()[0]["skill"], "attack")


class ClassEditorTests(WindowTestCase):
    def test_edit_create_and_delete_class(self):
        db = self.db
        editor = self.tab("Classes")
        stat_row = lambda stat: TOP + 63 + list(Stat).index(stat) * 24
        self.write(X + 144, stat_row(Stat.HP), "100")
        self.write(X + 206, stat_row(Stat.EVASION), "1.5")        # рост за уровень
        self.write(X + 616, TOP + 12, "5")                        # макс. AP
        self.toggle(X + 444, TOP + 12, "tank")                    # роли класса (башня)
        self.toggle(X + 444, TOP + 12, "support")
        knight = db.units["knight"]
        self.assertEqual((knight.base_stats[Stat.HP], knight.growth[Stat.EVASION], knight.ap_max), (100, 1.5, 5))
        self.assertEqual(set(knight.roles), {"tank", "support"})
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
        self.assertEqual(set(reloaded.units["knight"].roles), {"tank", "support"})
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

        # по правилам UO рыцарь бьёт того, кто перед ним, — орка: пусть орк отвечает на удары по себе
        db.update("passives", pid, dict(db.passives[pid].to_dict(), reaction=dict(
            db.passives[pid].reaction.to_dict(), whose="self")))
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


class ShowTabTests(WindowTestCase):
    def test_demo_battle_by_default_modes_restart_and_skip(self):
        show = self.tab("Show")
        self.assertEqual((show.mode, show.seed), ("demo", DEMO_SEED))
        if show.show is None:
            self.skipTest(show.error or "no battle show")
        press = lambda key: show.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key), (0, 0))
        press(pygame.K_t)
        self.assertEqual(show.mode, "setup")
        press(pygame.K_t)
        self.assertEqual(show.mode, "demo")
        press(pygame.K_r)
        self.assertEqual(show.seed, DEMO_SEED + 1)
        press(pygame.K_SPACE)                                  # доиграть сразу
        self.assertTrue(show.show.battle.finished)
        self.assertTrue(show.show.done(show.clock + 1000))
        self.frame()


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

    def test_enemy_contact_starts_a_show_battle_and_the_result_returns(self):
        world = self.tab("World")
        enemy = world.world.enemy("scouts")
        world.state.hero = (enemy.x - 40, enemy.z)
        world.state.enemies["scouts"].x, world.state.enemies["scouts"].z = enemy.x, enemy.z
        world.update(5000, (0.0, 0.0))
        self.assertEqual(world.pending, "scouts")
        self.assertEqual(self.app.tabs[self.app.tab][0], "Show")         # бой на вкладке Show
        show = self.app.show
        self.assertEqual(show.mode, "world")
        battle = show.show.battle
        self.assertEqual({u.definition.id for u in battle.defender.formation.units}, {"goblin"})
        show.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE), (0, 0))   # доиграть
        show.clock += 5000
        won = battle.winner_id == battle.attacker.id
        show.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN), (0, 0))
        self.assertEqual(self.app.tabs[self.app.tab][0], "World")
        self.frame()
        self.assertIsNone(world.pending)
        self.assertEqual("scouts" in world.state.defeated, won)
        self.assertNotEqual(show.mode, "world")                           # Show вернулась к своему бою


class WindowTests(WindowTestCase):
    def test_large_window_maps_mouse_and_draws_the_field(self):
        window = d.Window((1600, 992))
        self.assertAlmostEqual(window.scale, 1.6)
        self.assertEqual(window.to_logical((800, 496)), (500, 310))
        click = window.logical_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(160, 160), button=1))
        self.assertEqual(click.pos, (100, 100))
        self.ui = UI(window.canvas, load_fonts())
        self.ui.transform = window.to_logical
        show = self.tab("Show")
        self.ui.begin([])
        d.draw_frame(self.ui, self.app, False, 1300, window)
        self.assertTrue(show.native)
        self.assertEqual(show.camera(window.scale, window.offset)[0], window.scale)
        self.assertEqual(window.surface.get_size(), (1600, 992))


if __name__ == "__main__":
    unittest.main()
