"""Интерфейс боя UO поверх сцены: плашки бойцов, цифры урона, ленты с названиями навыков.

Раскладки — куклы GUI/Interface_Battle_00 и GUI/Interface; у раскладок треки — разряды цифр, у
кадра цифры деталь k — цифра k (Item.only). Тики — 60 в секунду.
- плашка BATTLE_MINI_HP_GAUGE: трек 1 — щит уровня, 2 — уровень одной цифрой, 3–4 — две цифры,
  5–7 — HP (единицы, десятки, сотни), 8 — «/», 9–11 — макс. HP; заливку полосы игра рисует кодом —
  здесь своя (BAR); MINI_HP_GAUGE_MARKER: треки 0–3 — камни PP, 4–7 — AP;
- цифры NUM_*: треки 0–3 — разряды (шаг 64), 4–7 — их второй слой; надписи STR_* — целиком;
- ленты A_SKILL_1 (навык) и S_SKILL (пассивка): _ON — появление, сама лента, _OFF — уход.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pygame

from engine.uo.gl import GLRenderer

from .data import TICK_MS, ShowData
from .render import Camera, Canvas
from .timeline import Banner, Plate, Popup

GAUGE = "BATTLE_MINI_HP_GAUGE"
MARKER = "MINI_HP_GAUGE_MARKER"
BAR = (-65.3, -3.2, 63.4, 3.2)        # полоса HP в раскладке плашки
DIGIT_STEP = 64
PLATE_SCALE = 0.62                    # плашка к масштабу сцены (единицы раскладки ≈ пиксели при 1080p)
POPUP_SCALE = 0.45
WORD_RISE = 185                       # подпись над числом: низ слова (+41) выше верха цифр (-138)
BANNER_SCALE = 0.42
FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "LinLibertine_RB.ttf"


def ticks(ms: float) -> int:
    return int(ms / TICK_MS)


class Hud:
    def __init__(self, data: ShowData):
        self.data = data
        self.hud = data.ui_model("hud")
        self.ui = data.ui_model("ui")
        self.gl = GLRenderer.get()
        self._fonts: dict[int, pygame.font.Font] = {}
        self._texts: dict = {}

    # --- куклы интерфейса ---

    def _mesh(self, model, anim: str, tick: float, tracks: Optional[dict] = None, parts: Optional[dict] = None):
        puppet = model.puppet
        a = puppet.anims[anim]

        def items():
            out = []
            for t in range(a["tcount"]):
                when = tick if tracks is None else tracks.get(t, None)
                item = None if when is None else puppet.track_item(a["tstart"] + t, when)
                if item is not None:
                    item.only = (parts or {}).get(t, -1)
                    out.append(item)
            return out

        key = ("hud", id(model), anim, round(tick, 1),
               None if tracks is None else tuple(sorted(tracks.items())),
               None if parts is None else tuple(sorted(parts.items())))
        return self.gl.mesh(key, puppet, items)

    def _draw(self, canvas: Canvas, model, anim: str, point, scale: float, tick: float = 0, tracks=None, parts=None,
              alpha: float = 1.0, mul=(1.0, 1.0, 1.0)) -> bool:
        if model is None or anim not in model.puppet.anims:
            return False
        canvas.puppet(self._mesh(model, anim, tick, tracks, parts), model.pages, scale, False, point, alpha, mul=mul)
        return True

    def _key_tick(self, model, anim: str, track: int, key: int) -> float:
        return model.puppet.key_tick(anim, track, key)

    # --- плашка бойца ---

    def plate(self, canvas: Canvas, cam: Camera, x: float, y: float, scale: float, plate: Plate, level: int,
              enemy: bool, ap_max: int, pp_max: int, now: float) -> None:
        model = self.hud
        if model is None or not plate.alive:
            return
        s = PLATE_SCALE * scale * cam.k * 1.6
        px, py = cam.p(x, y)
        x0, y0 = px + 14 * s, py + 16 * s
        keys: dict[int, Optional[int]] = {0: 0, 1: 0, 8: 0}
        if level < 10:
            keys.update({2: level, 3: None, 4: None})
        else:
            keys.update({2: None, 3: level % 10, 4: level // 10 % 10})
        hp = str(max(0, plate.hp))[-3:]
        for i, t in enumerate((5, 6, 7)):
            keys[t] = int(hp[-1 - i]) if i < len(hp) else None
        mx = str(plate.max_hp)[-3:]
        slots = [9, 10, 11][3 - len(mx):]          # макс. HP сразу за «/»
        for t in (9, 10, 11):
            keys[t] = None
        for i, t in enumerate(slots):
            keys[t] = int(mx[-1 - i])
        tracks = {t: None if k is None else self._key_tick(model, GAUGE, t, k) for t, k in keys.items()}
        self._draw(canvas, model, GAUGE, (x0, y0), s, tracks=tracks)
        bx0, by0, bx1, by1 = BAR
        share = max(0.0, min(1.0, plate.hp / max(1, plate.max_hp)))
        if share > 0:
            w = (bx1 - bx0) * s * share
            h = (by1 - by0) * s
            base, light = ((200, 60, 50), (255, 140, 110)) if enemy else ((70, 170, 60), (170, 240, 120))
            canvas.rect(base, (x0 + bx0 * s, y0 + by0 * s, w, h))
            canvas.rect(light, (x0 + bx0 * s, y0 + by0 * s, w, max(1.0, h / 3)))
        tick = ticks(now) % 156
        lit, dark = {}, {}
        for i in range(4):
            pp = 3 - i
            if pp < min(4, pp_max):
                (lit if pp < plate.pp else dark)[i] = tick
            if i < min(4, ap_max):
                (lit if i < plate.ap else dark)[4 + i] = tick
        for group, spent in ((lit, False), (dark, True)):
            if group:
                self._draw(canvas, model, MARKER, (x0, y0 + 10 * s), s, tracks=group,
                           alpha=0.35 if spent else 1.0, mul=(0.35, 0.35, 0.35) if spent else (1.0, 1.0, 1.0))

    # --- цифры ---

    def popup(self, canvas: Canvas, cam: Camera, x: float, y: float, scale: float, popup: Popup, now: float) -> None:
        model = self.ui
        if model is None:
            return
        tick = ticks(now - popup.start)
        s = POPUP_SCALE * scale * cam.k * 1.6
        px, py = cam.p(x, y)
        for anim in popup.anims:
            if anim.startswith("NUM_") and popup.value is not None:
                text = str(max(0, popup.value))[-4:]
                tracks, parts = {}, {}
                for layer in range(2):
                    for i in range(4):
                        t = layer * 4 + i
                        tracks[t] = tick if i < len(text) else None
                        if i < len(text):
                            parts[t] = int(text[-1 - i])
                shift = (len(text) - 1) * DIGIT_STEP * s / 2
                self._draw(canvas, model, anim, (px + shift, py), s, tick, tracks, parts)
            else:
                rise = 0 if anim.startswith("STR_MISS") else WORD_RISE * s
                self._draw(canvas, model, anim, (px, py - rise), s, tick)

    # --- ленты ---

    def banner(self, canvas: Canvas, banner: Banner, now: float) -> None:
        model = self.hud
        name = "S_SKILL" if banner.passive else "A_SKILL_1"
        if model is None or name not in model.puppet.anims:
            return
        clip = canvas.clip
        opening = model.length(f"{name}_ON") * TICK_MS
        closing = model.length(f"{name}_OFF") * TICK_MS
        if now < banner.start + opening:
            anim, tick, shown = f"{name}_ON", ticks(now - banner.start), (now - banner.start) / max(1, opening)
        elif now > banner.end - closing:
            left = banner.end - now
            anim, tick, shown = f"{name}_OFF", ticks(closing - left), left / max(1, closing)
        else:
            anim, tick, shown = name, 0, 1.0
        scale = clip.width / 1920 * BANNER_SCALE
        x = clip.x + clip.width * (0.5 + 0.24 * (-1 if banner.side == 0 else 1))
        y = clip.y + clip.height * 0.17
        self._draw(canvas, model, anim, (x, y), scale, tick)
        if shown > 0.35:
            size = max(10, round(54 * scale * 1.6))
            text, shadow = self.text(banner.text, size)
            alpha = min(1.0, (shown - 0.35) / 0.4)
            w, h = text.get_size()
            canvas.image(shadow, (x - w / 2 + 2, y - h / 2 + 2), alpha)
            canvas.image(text, (x - w / 2, y - h / 2), alpha)

    def text(self, text: str, size: int) -> tuple[pygame.Surface, pygame.Surface]:
        key = (text, size)
        if key not in self._texts:
            if size not in self._fonts:
                self._fonts[size] = pygame.font.Font(str(FONT), size) if FONT.is_file() else pygame.font.SysFont(None, size)
            font = self._fonts[size]
            if len(self._texts) > 100:
                self._texts.clear()
            self._texts[key] = (font.render(text, True, (255, 246, 226)), font.render(text, True, (30, 16, 8)))
        return self._texts[key]
