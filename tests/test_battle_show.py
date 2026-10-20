"""Тесты показа боя без файлов игры: полёт снаряда, расписание снарядов режиссёра, разбор настроек DbReg."""
import json
import struct
import tempfile
import unittest
from pathlib import Path

from battle.data import TICK_MS, ShowData
from battle.director import Director
from battle.timeline import Shot, Timeline
from engine.uo.drg import parse
from game.combat import Battle
from game.combat.record import ACTIVE
from tests.helpers import add_skill, duel, only, plain_db
from tests.test_combat import part


class ShotTests(unittest.TestCase):
    def test_straight_shot_goes_from_a_to_b_and_faces_its_way(self):
        shot = Shot(100, "BOW_SHOT", (0, 0), (600, 0), 300, 1.0)
        self.assertEqual(shot.at(100)[:2], (0, 0))
        self.assertEqual(shot.at(400)[:2], (600, 0))
        x, y, angle, flip = shot.at(250)
        self.assertEqual((x, y, round(angle), flip), (300, 0, 0, False))
        back = Shot(0, "BOW_SHOT", (600, 0), (0, 0), 300, 1.0)
        self.assertTrue(back.at(150)[3])                                    # летит влево — отражён
        self.assertEqual(round(back.at(150)[2]), 0)

    def test_lobbed_shot_arcs_above_the_line_and_lands_on_target(self):
        shot = Shot(0, "SPEAR", (0, 0), (600, 0), 30 * TICK_MS, 1.0, fall=0.8, tick_ms=TICK_MS)
        x, y, angle, _ = shot.at(shot.ms / 2)
        self.assertLess(y, -50)                                             # y вниз: дуга выше прямой
        self.assertAlmostEqual(angle, 0, delta=1)                           # в верхней точке — горизонтально
        self.assertGreater(shot.at(shot.ms * 0.1)[2], 10)                   # вылет — вверх
        end = shot.at(shot.ms)
        self.assertAlmostEqual(end[0], 600)
        self.assertAlmostEqual(end[1], 0, places=6)


class VolleyTests(unittest.TestCase):
    def test_hits_land_when_their_projectiles_arrive(self):
        db = plain_db()
        add_skill(db, "volley", ["knight"], hits=2, accuracy=1000, tags=["ranged"], parts=[part(power=0.1)])
        tmp = Path(tempfile.mkdtemp()) / "uo_battle.json"
        balls = [[0.0, 0.0, 0.0], [50.0, -30.0, 12.0]]
        tmp.write_text(json.dumps({"skills": {"volley": {"kind": "ranged", "cast": [], "hit": ["HIT_C"],
                                                         "shot": {"anim": "FIREBALL", "speed": 40, "volley": balls}}}}),
                       encoding="utf-8")
        sim, knight, orc = duel(db, "knight", "orc")
        only(db, knight, "volley")
        battle = Battle(sim.attacker, sim.defender, db, seed=1)
        timeline = Timeline()
        director = Director(ShowData(tmp), battle, timeline)
        while True:
            battle.step()
            act = battle.last_act
            if act.kind == ACTIVE and act.actor == knight.uid:
                break
        director.act(act, 0)
        shots = timeline.shots
        self.assertEqual(len(shots), 2)
        self.assertAlmostEqual(shots[1].start - shots[0].start, 12 * TICK_MS)   # задержка второго шара
        arrivals = sorted(s.start + s.ms for s in shots)
        times = [p.time for p in timeline.track(orc.uid).plates if p.time > 0]
        self.assertEqual([round(t) for t in times[:2]], [round(t) for t in arrivals])   # удар — когда долетел


class DbRegTests(unittest.TestCase):
    def test_groups_and_records(self):
        group_at, table = 40, 40 + 144
        data = bytearray(table + 2 * 208)
        struct.pack_into("<4s6I", data, 0, b"DRG\0", 96, 2, 0, group_at, 0, table)
        entry = struct.pack("<4I", 2, 0, 1, 0) + b"C:/Soft/DbReg/Battle/Shot.txt".ljust(64, b"\0") + \
            b"BTSHOT".ljust(24, b"\0") + b"".ljust(40, b"\0")
        data[group_at:group_at + 144] = entry
        for i, (kind, value, name) in enumerate(((1, 40.0, b"FIREBALL_SPEED"), (0, 6.0, b"FIREBALL_COUNT"))):
            at = table + i * 208
            struct.pack_into("<If", data, at, kind, value)
            data[at + 16:at + 16 + len(name)] = name
            note = "ファイアーボール".encode() if i == 0 else b""
            data[at + 80:at + 80 + len(note)] = note
        groups, params = parse(bytes(data))
        self.assertEqual([(g.name, g.first, g.count) for g in groups], [("BTSHOT", 0, 2)])
        self.assertEqual([(p.group, p.name, p.value, p.is_float) for p in params],
                         [("BTSHOT", "FIREBALL_SPEED", 40.0, True), ("BTSHOT", "FIREBALL_COUNT", 6.0, False)])
        self.assertEqual(params[0].note, "ファイアーボール")


def fake_puppet(keys, length, loop_start=-1):
    """Кукла из одного трека: keys — (кадр, трансформация, длительность, флаги[, цель прыжка])."""
    import numpy as np
    from engine.uo.puppet import Puppet
    p = Puppet.__new__(Puppet)
    p.keys = np.array([(f, tr, d, fl, k[0] if k else 0) for f, tr, d, fl, *k in keys],
                      dtype=[("frame", "<u4"), ("tr", "<u2"), ("dur", "<u2"), ("flags", "<u4"), ("f2", "<u4")])
    p.tracks = np.array([(0, len(keys), length, loop_start, -1, 0)],
                        dtype=[("kstart", "<u2"), ("kcount", "<u2"), ("length", "<u4"), ("i0", "<i4"),
                               ("i1", "<i4"), ("flags", "<u4")])
    p.transforms = [dict(tx=float(x), ty=0.0, rx=0.0, ry=0.0, rz=0.0, sx=1.0, sy=1.0, rgba=(1, 1, 1, 1)) for x in (0, 100, 200)]
    p.track_times = [np.concatenate([[0], np.cumsum([max(1, k[2]) for k in keys])])]
    p.timelines = [p._timeline(0)]
    p.anims = {"A": {"tstart": 0, "tcount": 1}}
    return p


class TrackTimeTests(unittest.TestCase):
    """Время трека .mbs: длина — поле length, i0 — тик начала цикла, 0x400 — переход трансформации,
    0x4 — прыжок на ключ (морфинг вершин к цели прыжка), 0x800 — метка последнего ключа."""

    def test_length_cuts_keys_and_loop_starts_at_tick(self):
        p = fake_puppet([(1, 0, 10, 0x20), (2, 1, 10, 0x20), (3, 2, 10, 0x820)], length=25, loop_start=10)
        self.assertEqual(p.anim_length("A"), 25)                         # не 30: ключи после length обрезаны
        self.assertEqual(p.track_item(0, 24).frame, 3)
        self.assertEqual(p.track_item(0, 25).frame, 2)                   # цикл с тика 10, а не с ключа 10
        self.assertEqual(p.track_item(0, 31).frame, 2)
        once = fake_puppet([(1, 0, 10, 0x20), (2, 1, 10, 0x820)], length=20)
        self.assertEqual(once.track_item(0, 99).frame, 2)               # без цикла — держит последний кадр

    def test_jump_key_skips_keys_and_closes_the_loop(self):
        """0x4 — прыжок: ключи между прыжком и целью не показываются, цикл — с цели прыжка."""
        p = fake_puppet([(1, 0, 10, 0x20), (2, 1, 10, 0x24, 3), (3, 2, 10, 0x20),
                         (4, 0, 10, 0x20), (5, 1, 10, 0x24, 3)], length=40)
        self.assertEqual([int(k) for k in p.timelines[0].order], [0, 1, 3, 4])
        self.assertEqual(p.timelines[0].loop, 20)                       # цикл — с ключа 3 (тик 20)
        self.assertEqual(p.track_item(0, 25).frame, 4)                  # после прыжка идёт цель, а не ключ 2
        self.assertEqual(p.track_item(0, 45).frame, 4)                  # цикл с цели прыжка

    def test_flags_choose_what_is_interpolated(self):
        p = fake_puppet([(1, 0, 10, 0x420), (2, 2, 10, 0x820)], length=20)
        self.assertAlmostEqual(p.track_item(0, 5).tr["tx"], 100)        # 0x400: трансформация к следующему ключу
        self.assertEqual(p.track_item(0, 5).morph_frame, -1)
        p = fake_puppet([(1, 0, 10, 0x24, 1), (2, 0, 10, 0x820)], length=20)
        item = p.track_item(0, 5)
        self.assertEqual((item.morph_frame, item.morph), (2, 0.5))      # 0x4: вершины к кадру цели прыжка
        p = fake_puppet([(1, 0, 10, 0x20), (2, 1, 10, 0x820)], length=20, loop_start=0)
        self.assertEqual(p.track_item(0, 15).morph_frame, -1)           # 0x800 — только конец трека


if __name__ == "__main__":
    unittest.main()
