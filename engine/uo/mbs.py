"""Vanillaware FMBS (Unicorn Overlord, Switch) sprite/animation parser.

Section layout (offset table at 0xB0, 12 x u64):
  s0  colors     6 x RGBA8 per entry (24 B)            count u32 @0x54
  s1  uv polys   6 x (u,v) f32, triangle fan (48 B)     count u32 @0x58
  s2  xy polys   6 x (x,y) f32, triangle fan (48 B)     count u32 @0x5C
  s3  boxes      80 B                                   count u32 @0x60
  s4  parts      20 B: u32 ?, u8 tex?, u8, u16, u32 flags, u32 color<<16|uv, u32 xy
                                                        count u32 @0x50
  s5  8 B                                               count u16 @0x64
  s6  frames     28 B: f32 bbox[4], u32 part_start, u32 part_count<<16|?, u32 flags
                                                        count u16 @0x6A
  s7  transforms 36 B: f32 tx,ty,?,?,?,rot,sx,sy, u32 rgba
                                                        count u16 @0x66
  s8  keys       32 B: u32 frame, u16 transform, u16 duration, u32 flags, ...
                                                        count u16 @0x68
  s9  anims      48 B: f32 bbox[4], char name[24], u16 track_start, u8 track_count, u8 flags
                                                        count u16 @0x6C
  s10 tracks     24 B: u16 key_start, u16 key_count, u32 length, ...
                                                        count u16 @0x6E
  s11 events     20 B: u32 tick, u32 key, u32 0, u32 type, u32 0     count u16 @0x72
                 трек ссылается на события полем flags: младшие 16 бит — первая запись, следующий
                 байт — сколько записей. type: 0 — момент действия (удар, выпуск снаряда), 1 — начало
                 движения (разбег, прыжок, взлёт), 2 — получение удара, 3 — приземление, остановка.
"""
import struct
import sys
import numpy as np


class MBS:
    def __init__(self, data: bytes):
        if data[:4] != b"FMBS":
            raise ValueError("not FMBS")
        self.d = d = data
        self.name = d[0x80:0xB0].split(b"\0")[0].decode("ascii", "replace")
        offs = [struct.unpack_from("<Q", d, 0xB0 + 8 * i)[0] for i in range(12)]
        n_parts, n_col, n_uv, n_xy, n_box = struct.unpack_from("<5I", d, 0x50)
        n5, n7, n8, n6, n9, n10, _n_unk, n11 = struct.unpack_from("<8H", d, 0x64)
        self.offs = offs
        self.counts = dict(parts=n_parts, colors=n_col, uv=n_uv, xy=n_xy, boxes=n_box, s5=n5,
                           transforms=n7, keys=n8, frames=n6, anims=n9, tracks=n10, s11=n11)

        def arr(i, n, dtype):
            dt = np.dtype(dtype)
            return np.frombuffer(d, dtype=dt, count=n, offset=offs[i]) if n else np.zeros(0, dt)

        self.colors = np.frombuffer(d, "u1", n_col * 24, offs[0]).reshape(-1, 6, 4)
        self.uv = np.frombuffer(d, "<f4", n_uv * 12, offs[1]).reshape(-1, 6, 2)
        self.xy = np.frombuffer(d, "<f4", n_xy * 12, offs[2]).reshape(-1, 6, 2)
        self.parts = arr(4, n_parts, [("a", "<u4"), ("tex", "u1"), ("b", "u1"), ("c", "<u2"),
                                      ("flags", "<u4"), ("uvcol", "<u4"), ("xy", "<u4")])
        self.frames = arr(6, n6, [("bbox", "<f4", 4), ("pstart", "<u4"), ("pinfo", "<u4"), ("flags", "<u4")])
        self.transforms = arr(7, n7, [("tx", "<f4"), ("ty", "<f4"), ("u0", "<f4"), ("u1", "<f4"),
                                      ("u2", "<f4"), ("rot", "<f4"), ("sx", "<f4"), ("sy", "<f4"),
                                      ("rgba", "u1", 4)])
        self.keys = arr(8, n8, [("frame", "<u4"), ("tr", "<u2"), ("dur", "<u2"), ("flags", "<u4"),
                                ("f2", "<u4"), ("f3", "<u4"), ("f4", "<u4"), ("f5", "<u4"), ("f6", "<u4")])
        self.anims = []
        for i in range(n9):
            o = offs[9] + i * 48
            bbox = struct.unpack_from("<4f", d, o)
            name = d[o + 16:o + 40].split(b"\0")[0].decode("ascii", "replace")
            ts, tc, af = struct.unpack_from("<HBB", d, o + 40)
            self.anims.append({"name": name, "bbox": bbox, "tstart": ts, "tcount": tc, "aflags": af})
        self.tracks = arr(10, n10, [("kstart", "<u2"), ("kcount", "<u2"), ("length", "<u4"),
                                    ("i0", "<i4"), ("i1", "<i4"), ("flags", "<u4"), ("layer", "<u4")])
        self.events = arr(11, n11, [("tick", "<u4"), ("key", "<u4"), ("u0", "<u4"), ("type", "<u4"), ("u1", "<u4")])

    def track_events(self, ti):
        """События трека ti: [(тик, тип)]."""
        fl = int(self.tracks[ti]["flags"])
        first, count = fl & 0xFFFF, (fl >> 16) & 0xFF
        return [(int(e["tick"]), int(e["type"])) for e in self.events[first:first + count]] if count else []

    def frame_parts(self, fi):
        f = self.frames[fi]
        n = int(f["pinfo"]) >> 16
        s = int(f["pstart"])
        return self.parts[s:s + n]


if __name__ == "__main__":
    m = MBS(open(sys.argv[1], "rb").read())
    print(m.name, m.counts)
    for a in m.anims[:20]:
        print(a)
