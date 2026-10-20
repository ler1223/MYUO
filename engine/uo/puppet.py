"""Кукла Vanillaware: вычисление анимации .mbs и программная отрисовка кадра в RGBA (numpy).

Кадр куклы — набор деталей: многоугольник из 6 вершин (веер вокруг центра) в координатах
персонажа (ноги в 0, y вниз), его UV на странице атласа и цвета вершин. Анимация — треки
(слои), трек — ключи «кадр + трансформация + длительность в тиках (60 в секунду)».

Что учитывается при отрисовке (так же, как во вьюере viewer/render.js):
- смешивание: младший байт поля c детали (0 обычное, 1 сложение, 2 умножение);
- отражение: бит 0 флагов ключа — по горизонтали, бит 1 — по вертикали (до трансформации);
- маски: в кадре с флагом 0x100 детали с b & 2 пишут маску и не рисуются; группа масок обрезает
  следующие за ней детали той же тысячи номеров слоя (поле a детали: маски 9300, 9291 -> подол 9360,
  9351…), детали другой тысячи рисуются целиком (engine.uo.gl, MASK_RULE);
- варианты внешности: биты флагов детали по группам (VARIANT_GROUPS), деталь видна, если в её
  группе нет битов или есть бит выбранного варианта;
- порядок ключей: трек идёт по ключам набора начиная с ключа st (поле по смещению 0x13: у большинства
  треков 0 — с первого, у части 1 — первый ключ служебный); ключ с флагом 0x4 — прыжок: после него
  игра идёт на ключ st + loop (поле loop ключа), поэтому часть ключей списка не показывается вовсе
  (вступление и «хвост» цикла); когда проход приходит на уже пройденный ключ, цикл замыкается;
  0x800 — метка последнего ключа трека: после неё проход кончается. Проверено по данным: поле sum
  трека равно сумме длительностей такого прохода (99% треков), i0 — сумме до точки замыкания (100%);
- интерполяция трансформаций (флаг ключа 0x400) и вершин между кадрами (0x4) — к следующему ключу
  прохода, на стыке цикла — к ключу начала цикла;
- ключ с флагом 0x40 — пауза: трек в это время ничего не рисует; 0x8 (почти всегда на последнем ключе) —
  после конца трека его больше не рисовать (без флага трек держит последний кадр): иначе застревают следы
  взмаха, вспышки, второй посох волшебника;
- время трека: его длина — поле length (ключи после неё обрезаются), i0 >= 0 — тик начала цикла: трек
  крутит отрезок [i0, length) сам, у каждого трека свой цикл (огонь шара мерцает, пока шар летит);
  i1 — тик конца разового трека. Длина анимации — наибольшая длина её треков.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .mbs import MBS

TICKS = 60
VARIANT_GROUPS = (0xFF, 0xC00, 0x3000, 0xC000, 0x30000, 0xFE000000)
MOUTH_GROUP = 0x30000      # рот: бит 16 — говорит, бит 17 — закрыт
IDENTITY = dict(tx=0.0, ty=0.0, rx=0.0, ry=0.0, rz=0.0, sx=1.0, sy=1.0, rgba=(1.0, 1.0, 1.0, 1.0))
NORMAL, ADD, MULTIPLY = 0, 1, 2


@dataclass
class Item:
    """Что рисует один трек в момент времени: кадр, трансформация, морф к следующему кадру."""
    frame: int
    tr: dict
    key_flags: int = 0
    morph_frame: int = -1
    morph: float = 0.0
    only: int = -1            # одна деталь кадра (номер внутри кадра): в цифрах интерфейса деталь k — цифра k


@dataclass
class Timeline:
    """Порядок показа ключей трека: проход по списку с прыжками (флаг ключа 0x4) до замыкания цикла."""
    order: np.ndarray         # номера ключей трека в порядке показа
    times: np.ndarray         # начало каждого ключа в тиках (длина — на один больше order)
    length: int               # сумма длительностей прохода
    loop: int                 # тик начала цикла (-1 — цикла нет)


class Puppet:
    """Данные одного .mbs в удобном виде + выбор варианта внешности."""

    # Переходы к следующему ключу, поле f3 ключа (битовое; разобрано по всем анимациям всех классов):
    #   младший байт (1, 2) — плавный переход трансформации: стоит у пар «тот же кадр, другой transform»;
    #   второй байт (0x100, 0x200) — перетекание кадра в следующий (морф вершин): у пар «другой кадр с тем же
    #   числом деталей» — так дышат и покачиваются стойки (у Sword Master кадры 2222 → 2220 → 2221 по 64 тика).
    # Без них стойки стоят по секунде и дёргаются рывком. Флаги ключа 0x400 / 0x4 включают то же самое.
    tween_f3 = True
    TWEEN_TR = 0xFF
    TWEEN_MORPH = 0xFF00

    def __init__(self, data: bytes, variant: int = 0):
        m = self.m = MBS(data)
        p = m.parts
        self.p_xy = p["xy"].astype(np.int64)
        self.p_uv = (p["uvcol"] & 0xFFFF).astype(np.int64)
        self.p_col = (p["uvcol"] >> 16).astype(np.int64)
        self.p_page = (p["c"] >> 8).astype(np.int64)
        self.p_mode = (p["c"] & 0xFF).astype(np.int64)
        self.p_b = p["b"].astype(np.int64)
        self.p_flags = p["flags"].astype(np.int64)
        self.f_start = m.frames["pstart"].astype(np.int64)
        self.f_count = (m.frames["pinfo"] >> 16).astype(np.int64)
        self.f_flags = m.frames["flags"].astype(np.int64)
        self.xy = m.xy.astype(np.float64)
        self.uv = m.uv.astype(np.float64)
        self.colors = m.colors.astype(np.float64) / 255.0 if len(m.colors) else None
        tr = m.transforms
        self.transforms = [dict(tx=float(t["tx"]), ty=float(t["ty"]), rx=float(t["u1"]), ry=float(t["u2"]),
                                rz=float(t["rot"]), sx=float(t["sx"]), sy=float(t["sy"]),
                                rgba=tuple(float(c) / 255 for c in t["rgba"])) for t in tr]
        self.keys = m.keys
        self.tracks = m.tracks
        self.anims = {a["name"]: a for a in m.anims if a["name"]}
        # длительности треков
        self.track_times: list[np.ndarray] = []
        for t in self.tracks:
            durs = np.maximum(1, self.keys["dur"][int(t["kstart"]):int(t["kstart"]) + int(t["kcount"])].astype(np.int64))
            self.track_times.append(np.concatenate([[0], np.cumsum(durs)]))
        self.timelines = [self._timeline(ti) for ti in range(len(self.tracks))]
        self.set_variant(variant)

    def _timeline(self, ti: int) -> Timeline:
        """Проход по ключам трека: с ключа st, прыжки (0x4) на ключ st + loop, конец по 0x800 или
        по возврату на пройденный ключ (там же точка цикла)."""
        t = self.tracks[ti]
        n = int(t["kcount"])
        if n <= 0:
            return Timeline(np.zeros(0, np.int64), np.zeros(1, np.int64), 0, -1)
        ks = int(t["kstart"])
        st = (int(t["flags"]) >> 24) & 0xFF
        first = st if st < n else 0
        dur = np.maximum(1, self.keys["dur"][ks:ks + n].astype(np.int64))
        flags = self.keys["flags"][ks:ks + n].astype(np.int64)
        jumps = self.keys["f2"][ks:ks + n].astype(np.int64) & 0xFFFF
        seen: dict[int, int] = {}
        order: list[int] = []
        loop = -1
        i = first
        while 0 <= i < n and len(order) < n:
            if i in seen:
                loop = seen[i]
                break
            seen[i] = len(order)
            order.append(i)
            if flags[i] & 0x4:
                i = first + int(jumps[i])
            elif flags[i] & 0x800:
                break
            else:
                i += 1
        keys = np.array(order, np.int64)
        times = np.concatenate([[0], np.cumsum(dur[keys])]) if len(keys) else np.zeros(1, np.int64)
        return Timeline(keys, times, int(times[-1]), int(times[loop]) if loop >= 0 else -1)

    # --- варианты внешности ---

    def variant_bits(self) -> list[list[int]]:
        """Для каждой группы — биты, которые встречаются в файле."""
        used = int(np.bitwise_or.reduce(self.p_flags)) if len(self.p_flags) else 0
        return [[b for b in range(32) if (g >> b) & 1 and (used >> b) & 1] for g in VARIANT_GROUPS]

    HELMET_GROUPS = (2, 3)       # индексы VARIANT_GROUPS: тип и вариант головного убора

    def variant_combos(self) -> list[dict[int, int]]:
        """Все модели файла: внешность (группа 0) x головной убор (группы 3-4). Бит убора с наибольшим
        номером — убор надет (шляпа ведьмы, шлем), поэтому он идёт первым; младший — голова без убора."""
        import itertools
        bits = self.variant_bits()
        axes = [[(0, b) for b in bits[0]] or [(0, None)]]
        for gi in self.HELMET_GROUPS:
            axes.append([(gi, b) for b in sorted(bits[gi], reverse=True)] or [(gi, None)])
        return [{gi: b for gi, b in combo if b is not None} for combo in itertools.product(*axes)]

    def set_variant(self, variant: int = 0, talk: bool = False) -> None:
        """variant — номер модели из variant_combos (0 — первая: первая внешность, убор надет). Остальные
        группы — первый бит. Группа рта (MOUTH_GROUP, биты 16/17): бит 16 — рот говорит (открывается в такт),
        17 — закрыт; в бою (talk=False) — закрытый, а где его нет (32 файла из 78), детали «говорящего» рта
        скрыты."""
        combos = self.variant_combos()
        chosen = combos[variant % len(combos)]
        active = []
        for gi, bits in enumerate(self.variant_bits()):
            if gi in chosen:
                active.append(1 << chosen[gi])
            elif not bits:
                active.append(0)
            elif VARIANT_GROUPS[gi] == MOUTH_GROUP and not talk:
                active.append(1 << 17 if 17 in bits else 0)
            else:
                active.append(1 << bits[0])
        visible = np.ones(len(self.p_flags), bool)
        for g, a in zip(VARIANT_GROUPS, active):
            bits = self.p_flags & g
            visible &= (bits == 0) | ((bits & a) != 0)
        self.visible = visible

    # --- время ---

    def track_length(self, ti: int) -> int:
        """Длина трека в тиках: поле length (ключи после неё обрезаются), без него — длина прохода."""
        total = self.timelines[ti].length
        own = int(self.tracks[ti]["length"])
        return min(own, total) if own > 0 else total

    def events(self, name: str) -> list[tuple[int, int]]:
        """События анимации (тик, тип) по всем трекам, по времени: 0 — удар или выпуск, 1 — начало
        движения, 2 — получение удара, 3 — приземление (секция s11 .mbs)."""
        a = self.anims[name]
        out = {ev for t in range(a["tstart"], a["tstart"] + a["tcount"]) for ev in self.m.track_events(t)}
        return sorted(out)

    def canonical_tick(self, name: str, tick: int, loop: bool = False) -> int:
        """Тот же кадр, что в tick, но с ограниченным номером (ключ кэша сеток): после конца анимации
        цикличные треки (i0) крутят каждый свой период — тик сводится к длине + остаток по их общему
        периоду; разовые треки к этому времени уже держат последний кадр."""
        length = self.anim_length(name)
        if tick < length:
            return max(0, int(tick))
        a = self.anims[name]
        period = 1
        for t in range(a["tstart"], a["tstart"] + a["tcount"]):
            start, own = int(self.tracks[t]["i0"]), self.track_length(t)
            if not 0 <= start < own and loop and own > 1:
                start = 0                    # анимация по кругу: трек без своего цикла — с начала
            if 0 <= start < own:
                period = math.lcm(period, own - start)
                if period > 7200:            # нет общего периода в разумных пределах — две минуты
                    return int(tick) % (length + 7200)
        return length + (int(tick) - length) % period

    def is_hold(self, name: str) -> bool:
        """Анимация-удержание: её главный трек целиком по кругу (i0 = 0, длина трека = длина анимации) —
        прицел, удержание каста, лук вверх у дождя стрел (ARROW_RAIN_2)."""
        a = self.anims[name]
        length = self.anim_length(name)
        return any(int(self.tracks[t]["i0"]) == 0 and self.track_length(t) == length and int(self.tracks[t]["kcount"]) > 1
                   for t in range(a["tstart"], a["tstart"] + a["tcount"]))

    def anim_length(self, name: str) -> int:
        a = self.anims[name]
        return max([self.track_length(t) for t in range(a["tstart"], a["tstart"] + a["tcount"])] or [1])

    def evaluate(self, name: str, tick: float, loop: bool = False) -> list[Item]:
        a = self.anims[name]
        out = []
        for ti in range(a["tstart"], a["tstart"] + a["tcount"]):
            item = self.track_item(ti, tick, loop)
            if item is not None:
                out.append(item)
        return out

    def track_item(self, ti: int, tick: float, loop: bool = False) -> Optional[Item]:
        """Что рисует трек ti (номер во всём файле) в момент tick; None — ничего."""
        t = self.tracks[ti]
        if not int(t["kcount"]):
            return None
        tl = self.timelines[ti]
        order, times = tl.order, tl.times
        if not len(order):
            return None
        length = self.track_length(ti)
        start = tl.loop if tl.loop >= 0 else int(t["i0"])
        if not 0 <= start < length:
            start = 0 if loop else -1          # анимация по кругу: трек без своего цикла — с начала
        tt, hold = max(0.0, float(tick)), False
        if tt >= length:
            if start >= 0:
                tt = start + (tt - start) % max(1, length - start)
            else:
                tt, hold = float(length), True
        if hold:
            pos = len(order) - 1               # трек кончился: держим последний ключ прохода
        else:
            pos = int(np.searchsorted(times, tt, side="right") - 1)
            pos = min(max(pos, 0), len(order) - 1)
        key = self.keys[int(t["kstart"]) + int(order[pos])]
        flags = int(key["flags"])
        if flags & 0x40:                      # ключ-пауза: трек ничего не рисует
            return None
        if hold and flags & 0x8:              # трек кончился и не держит последний кадр (след, вспышка)
            return None
        tr = self.transforms[int(key["tr"])] if int(key["tr"]) < len(self.transforms) else IDENTITY
        item = Item(int(key["frame"]), tr, flags)
        if hold:
            return item
        frac = (tt - times[pos]) / max(1, int(key["dur"]))
        f3 = int(key["f3"]) if self.tween_f3 and "f3" in (key.dtype.names or ()) else 0
        lerp_tr_on = bool(flags & 0x400) or bool(f3 & self.TWEEN_TR)
        morph_on = bool(flags & 0x4) or bool(f3 & self.TWEEN_MORPH)
        if not (lerp_tr_on or morph_on):
            return item
        # цель перехода: следующий ключ прохода; на стыке цикла — ключ начала цикла
        if pos + 1 < len(order):
            npos = pos + 1
        elif start >= 0:
            npos = int(np.searchsorted(times, start, side="right") - 1)
        else:
            return item
        nxt = self.keys[int(t["kstart"]) + int(order[npos])]
        if lerp_tr_on:
            tr2 = self.transforms[int(nxt["tr"])] if int(nxt["tr"]) < len(self.transforms) else IDENTITY
            item.tr = lerp_tr(tr, tr2, frac)
        if morph_on:
            item.morph_frame, item.morph = int(nxt["frame"]), frac
        return item

    def evaluate_tracks(self, name: str, ticks: dict[int, Optional[float]], default: float = 0,
                        loop: bool = False) -> list[Item]:
        """Как evaluate, но у треков свои тики: ticks[номер трека] — тик (None — трек не рисовать),
        остальные — default. Так интерфейс игры показывает цифры (ключ трека = цифра) и состояния."""
        a = self.anims[name]
        out = []
        for i in range(a["tcount"]):
            tick = ticks.get(i, default)
            if tick is not None:
                item = self.track_item(a["tstart"] + i, tick, loop)
                if item is not None:
                    out.append(item)
        return out

    def key_tick(self, name: str, track: int, key: int) -> float:
        """Тик, в который трек track анимации name показывает свой ключ key (середина ключа).
        Ключ, пропущенный прыжком, — по его месту в списке (так его видно в редакторе)."""
        a = self.anims[name]
        ti = a["tstart"] + track
        tl = self.timelines[ti]
        hits = np.nonzero(tl.order == key)[0]
        if len(hits):
            pos = int(hits[0])
            return float(tl.times[pos]) + min(0.5, float(tl.times[pos + 1] - tl.times[pos]) / 2)
        times = self.track_times[ti]
        key = max(0, min(len(times) - 2, key))
        return float(times[key]) + min(0.5, (times[key + 1] - times[key]) / 2)

    # --- геометрия ---

    def item_polys(self, it: Item):
        """Детали кадра трека после трансформации: (индексы деталей, вершины [n,6,2])."""
        f = it.frame
        if f >= len(self.f_count) or not self.f_count[f]:
            return np.zeros(0, np.int64), np.zeros((0, 6, 2))
        s, n = self.f_start[f], self.f_count[f]
        parts = np.arange(s, s + n)
        if 0 <= it.only < n:
            parts = parts[it.only:it.only + 1]
        xy = self.xy[self.p_xy[parts]]
        mf = it.morph_frame
        if mf >= 0 and mf != f and mf < len(self.f_count) and self.f_count[mf] == n:
            xy2 = self.xy[self.p_xy[np.arange(self.f_start[mf], self.f_start[mf] + n)]]
            if 0 <= it.only < n:
                xy2 = xy2[it.only:it.only + 1]
            xy = xy + (xy2 - xy) * it.morph
        if it.key_flags & 3:
            xy = xy * (-1.0 if it.key_flags & 1 else 1.0, -1.0 if it.key_flags & 2 else 1.0)
        a, b, c, d, e, g = matrix(it.tr)
        out = np.empty_like(xy)
        out[..., 0] = a * xy[..., 0] + c * xy[..., 1] + e
        out[..., 1] = b * xy[..., 0] + d * xy[..., 1] + g
        return parts, out

    def is_mask(self, frame: int, part: int) -> bool:
        return bool(self.f_flags[frame] & 0x100) and bool(self.p_b[part] & 2)

    def shown(self, it: Item, parts: np.ndarray) -> np.ndarray:
        """Какие детали трека видны: по варианту внешности, а выбранная деталь (Item.only) — всегда."""
        return np.ones(len(parts), bool) if it.only >= 0 else self.visible[parts]

    def bbox(self, items: list[Item]) -> Optional[tuple[float, float, float, float]]:
        """Рамка видимых деталей (без масок) в координатах персонажа."""
        boxes = []
        for it in items:
            parts, xy = self.item_polys(it)
            if not len(parts):
                continue
            keep = self.shown(it, parts).copy()
            if self.f_flags[it.frame] & 0x100:
                keep &= (self.p_b[parts] & 2) == 0
            if keep.any():
                pts = xy[keep].reshape(-1, 2)
                boxes.append((pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()))
        if not boxes:
            return None
        b = np.array(boxes)
        return float(b[:, 0].min()), float(b[:, 1].min()), float(b[:, 2].max()), float(b[:, 3].max())


def matrix(t: dict) -> tuple[float, ...]:
    """Аффинная матрица (a, b, c, d, e, f): x' = a x + c y + e, y' = b x + d y + f.
    Поворот R = Rx Ry Rz, ортографическая проекция (берутся строки x и y)."""
    cx, sx, cy, sy = math.cos(t["rx"]), math.sin(t["rx"]), math.cos(t["ry"]), math.sin(t["ry"])
    cz, sz = math.cos(t["rz"]), math.sin(t["rz"])
    r00, r01 = cy * cz, -cy * sz
    r10, r11 = sx * sy * cz + cx * sz, -sx * sy * sz + cx * cz
    return r00 * t["sx"], r10 * t["sx"], r01 * t["sy"], r11 * t["sy"], t["tx"], t["ty"]


def lerp_tr(a: dict, b: dict, f: float) -> dict:
    out = {k: a[k] + (b[k] - a[k]) * f for k in ("tx", "ty", "rx", "ry", "rz", "sx", "sy")}
    out["rgba"] = tuple(x + (y - x) * f for x, y in zip(a["rgba"], b["rgba"]))
    return out


# --- растеризация ------------------------------------------------------------------

class Canvas:
    """Холст с premultiplied RGBA (float32) и маской; сюда рисуются треугольники с текстурой."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.rgba = np.zeros((h, w, 4), np.float32)
        self.stencil = np.zeros((h, w), bool)

    def triangle(self, pts: np.ndarray, uvs: np.ndarray, cols: np.ndarray, tex: np.ndarray, mode: int,
                 mask_write: bool = False, mask_test: bool = False) -> None:
        """pts [3,2] в пикселях холста, uvs [3,2] в 0..1, cols [3,4] (rgba 0..1), tex [H,W,4] premultiplied."""
        x0 = max(int(math.floor(pts[:, 0].min())), 0)
        x1 = min(int(math.ceil(pts[:, 0].max())), self.w - 1)
        y0 = max(int(math.floor(pts[:, 1].min())), 0)
        y1 = min(int(math.ceil(pts[:, 1].max())), self.h - 1)
        if x1 < x0 or y1 < y0:
            return
        (ax, ay), (bx, by), (cx, cy) = pts
        area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        if abs(area) < 1e-9:
            return
        px = np.arange(x0, x1 + 1, dtype=np.float32) + 0.5
        py = np.arange(y0, y1 + 1, dtype=np.float32)[:, None] + 0.5
        w0 = ((bx - px) * (cy - py) - (by - py) * (cx - px)) / area
        w1 = ((cx - px) * (ay - py) - (cy - py) * (ax - px)) / area
        w2 = 1.0 - w0 - w1
        eps = -1e-4
        inside = (w0 >= eps) & (w1 >= eps) & (w2 >= eps)
        if mask_test:
            inside &= self.stencil[y0:y1 + 1, x0:x1 + 1]
        if not inside.any():
            return
        w0, w1, w2 = w0[inside], w1[inside], w2[inside]
        u = w0 * uvs[0, 0] + w1 * uvs[1, 0] + w2 * uvs[2, 0]
        v = w0 * uvs[0, 1] + w1 * uvs[1, 1] + w2 * uvs[2, 1]
        texel = sample(tex, u, v)
        col = w0[:, None] * cols[0] + w1[:, None] * cols[1] + w2[:, None] * cols[2]
        src = np.empty_like(texel)
        src[:, :3] = texel[:, :3] * col[:, :3] * col[:, 3:4]
        src[:, 3] = texel[:, 3] * col[:, 3]
        ys, xs = np.nonzero(inside)
        ys += y0
        xs += x0
        if mask_write:
            self.stencil[ys, xs] |= src[:, 3] > 0.1
            return
        dst = self.rgba[ys, xs]
        if mode == ADD:
            out = np.minimum(dst + src, 1.0)
        elif mode == MULTIPLY:
            out = dst.copy()
            out[:, :3] = src[:, :3] * dst[:, :3] + dst[:, :3] * (1 - src[:, 3:4])
        else:
            out = src + dst * (1 - src[:, 3:4])
        self.rgba[ys, xs] = out

    def to_image(self, downsample: int = 1) -> np.ndarray:
        """uint8 RGBA (не premultiplied), с усреднением блоков downsample x downsample."""
        img = self.rgba
        if downsample > 1:
            h, w = img.shape[0] // downsample, img.shape[1] // downsample
            img = img[:h * downsample, :w * downsample].reshape(h, downsample, w, downsample, 4).mean((1, 3))
        a = img[..., 3:4]
        rgb = np.where(a > 1e-6, img[..., :3] / np.maximum(a, 1e-6), 0)
        out = np.concatenate([rgb, a], -1)
        return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


def sample(tex: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Билинейная выборка из premultiplied текстуры [H,W,4] uint8 -> float32 [n,4] в 0..1."""
    h, w = tex.shape[:2]
    x = np.clip(u * w - 0.5, 0, w - 1)
    y = np.clip(v * h - 0.5, 0, h - 1)
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    x1 = np.minimum(x0 + 1, w - 1)
    y1 = np.minimum(y0 + 1, h - 1)
    fx = (x - x0)[:, None].astype(np.float32)
    fy = (y - y0)[:, None].astype(np.float32)
    t00, t01, t10, t11 = tex[y0, x0], tex[y0, x1], tex[y1, x0], tex[y1, x1]
    top = t00 * (1 - fx) + t01 * fx
    bottom = t10 * (1 - fx) + t11 * fx
    return (top * (1 - fy) + bottom * fy) / 255.0


def premultiply(rgba: np.ndarray) -> np.ndarray:
    """uint8 RGBA -> premultiplied uint8 (для выборки без ореолов на краях)."""
    a = rgba[..., 3:4].astype(np.uint16)
    out = rgba.copy()
    out[..., :3] = (rgba[..., :3].astype(np.uint16) * a // 255).astype(np.uint8)
    return out


def draw(puppet: Puppet, items: list[Item], pages: list[np.ndarray], canvas: Canvas, scale: float,
         ox: float, oy: float) -> None:
    """Нарисовать треки на холсте: точка (0, 0) персонажа попадает в (ox, oy), масштаб scale."""
    for it in items:
        parts, xy = puppet.item_polys(it)
        if not len(parts):
            continue
        frame = it.frame
        mask_frame = bool(puppet.f_flags[frame] & 0x100)
        if mask_frame:
            canvas.stencil[:] = False
        clip = None
        tr_rgba = np.array(it.tr["rgba"], np.float32)
        for j, part in enumerate(parts):
            if not puppet.visible[part]:
                continue
            is_mask = mask_frame and bool(puppet.p_b[part] & 2)
            if clip is None:
                clip = is_mask
            page = int(puppet.p_page[part])
            if page >= len(pages):
                continue
            mode = int(puppet.p_mode[part])
            mode = MULTIPLY if mode == 2 else ADD if mode == 1 else NORMAL
            pts = xy[j] * scale + (ox, oy)
            uv = puppet.uv[puppet.p_uv[part]]
            if puppet.colors is not None:
                cols = puppet.colors[puppet.p_col[part]].astype(np.float32) * tr_rgba
            else:
                cols = np.tile(tr_rgba, (6, 1))
            for k in range(1, 5):
                idx = [0, k, k + 1]
                canvas.triangle(pts[idx], uv[idx], cols[idx], pages[page], mode,
                                mask_write=is_mask, mask_test=bool(clip) and not is_mask)
