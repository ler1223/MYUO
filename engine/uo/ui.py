"""Интерфейс из Unicorn Overlord: элементы GUI игры (раскладки-куклы GUI/*.mbs) как рамки uikit.

data/uo_ui.json говорит, какой элемент игры становится какой рамкой (panel, button, tab…).
skin_folder() рисует их видеокартой (engine.uo.gl) в assets/uo_anim/_cache/ui/frame/<вид>.png
и пишет рядом theme.json с параметрами рамок (тело замеряется, как в tools/measure_ui_art.py).
Картинки пересобираются, когда меняется data/uo_ui.json. Нет папки игры или видеокарты — None,
и интерфейс рисуется своими картинками assets/ui.
"""
from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Optional

import numpy as np

from .library import CACHE, ROOT, snap, source

CONFIG = ROOT / "data" / "uo_ui.json"
SKIN = CACHE / "ui"
EDGE = 90           # как в tools/measure_ui_art.py: насколько линия рамки отличается от середины


def fill_insets(rgba: np.ndarray) -> list[int]:
    """Отступы от краёв картинки до тела рамки [слева, сверху, справа, снизу]: от середины к краю,
    пока цвет не отличается от середины заметно (линия рамки)."""
    h, w = rgba.shape[:2]
    cy, cx = h // 2, w // 2
    mid = rgba[max(0, cy - 1):cy + 2, max(0, cx - 1):cx + 2, :3].reshape(-1, 3).mean(0)

    def scan(points) -> int:
        for steps, (y, x) in enumerate(points):
            if rgba[y, x, 3] < 40 or np.abs(rgba[y, x, :3].astype(int) - mid).sum() > EDGE:
                return steps
        return len(points)

    left = cx - scan([(cy, x) for x in range(cx, -1, -1)])
    right = w - 1 - (cx + scan([(cy, x) for x in range(cx, w)]))
    top = cy - scan([(y, cx) for y in range(cy, -1, -1)])
    bottom = h - 1 - (cy + scan([(y, cx) for y in range(cy, h)]))
    return [max(0, left + 1), max(0, top + 1), max(0, right + 1), max(0, bottom + 1)]


def render(file: str, anim: str, tick: Optional[float] = None, scale: float = 1.0) -> Optional[np.ndarray]:
    """Элемент интерфейса игры как RGBA (обрезан по видимому)."""
    model = source().model("GUI", file)
    if model is None or anim not in model.puppet.anims:
        return None
    tick = model.length(anim) // 2 if tick is None else tick
    found = model.frame(anim, tick, scale, False)
    if found is None:
        return None
    rgba = found[0]
    ys, xs = np.nonzero(rgba[..., 3] > 8)
    return rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1] if len(xs) else None


def skin_folder() -> Optional[Path]:
    """Папка скина UO (с theme.json) — собрана или пересобрана при надобности; None — недоступно."""
    if not source().ok or not CONFIG.is_file():
        return None
    theme_path = SKIN / "theme.json"
    if theme_path.is_file() and theme_path.stat().st_mtime >= CONFIG.stat().st_mtime:
        return SKIN
    from PIL import Image
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    (SKIN / "frame").mkdir(parents=True, exist_ok=True)
    frames = {}
    for kind, spec in config.get("frames", {}).items():
        rgba = render(spec.get("file", config.get("file", "Interface")), spec["anim"], spec.get("tick"))
        if rgba is None:
            continue
        if spec.get("tint"):
            rgba = rgba.copy()
            rgba[..., :3] = (rgba[..., :3].astype(np.uint16) * np.array(spec["tint"]) // 255).astype(np.uint8)
        Image.fromarray(rgba).save(SKIN / "frame" / f"{kind}.png")
        frames[kind] = {k: spec[k] for k in ("border", "scale", "middle") if k in spec}
        frames[kind]["fill"] = spec.get("fill") or fill_insets(rgba)
    theme = {"frames": frames, **{k: config[k] for k in ("fonts", "text", "widgets") if k in config}}
    theme_path.write_text(json.dumps(theme, ensure_ascii=False, indent=1), encoding="utf-8")
    return SKIN


# ---- элементы интерфейса во время игры ---------------------------------------------------------

_SPRITES: "OrderedDict[tuple, Optional[tuple]]" = OrderedDict()
SPRITES_MAX = 600


def key_ticks(file: str, anim: str, keys: dict[int, Optional[int]]) -> dict[int, Optional[float]]:
    """Номер трека → номер ключа (None — трек не рисуется) в тики для Puppet.evaluate_tracks."""
    model = source().model("GUI", file)
    if model is None or anim not in model.puppet.anims:
        return {}
    return {t: None if k is None else model.puppet.key_tick(anim, t, k) for t, k in keys.items()}


def digits(value: int, tracks: list[int]) -> dict[int, Optional[int]]:
    """Число цифрами-треками (tracks — от единиц к старшим); лишние старшие треки скрыты.
    В раскладках игры ключ k трека-цифры — цифра k."""
    text = str(max(0, int(value)))[-len(tracks):]
    return {t: int(text[-1 - i]) if i < len(text) else None for i, t in enumerate(tracks)}


def number(value: int, places: int, layers: int = 1, tick: float = 0):
    """Число раскладкой NUM_*: треки 0..places-1 — разряды от единиц (слоёв layers подряд), деталь k кадра — цифра k.
    → (tracks, parts) для sprite(): лишние старшие разряды скрыты."""
    text = str(max(0, int(value)))[-places:]
    tracks, parts = {}, {}
    for layer in range(layers):
        for i in range(places):
            t = layer * places + i
            tracks[t] = tick if i < len(text) else None
            if i < len(text):
                parts[t] = int(text[-1 - i])
    return tracks, parts


def mesh(file: str, anim: str, tick: float = 0, tracks: Optional[dict[int, Optional[float]]] = None,
         default: float = 0, parts: Optional[dict[int, int]] = None):
    """(сетка элемента интерфейса на видеокарте, страницы атласа) — как sprite, но для кадра поля."""
    model = source().model("GUI", file)
    if model is None or anim not in model.puppet.anims:
        return None
    from .gl import GLRenderer
    key = ("ui", id(model), anim, round(tick, 1),
           None if tracks is None else tuple(sorted((t, None if v is None else round(v, 1)) for t, v in tracks.items())),
           default, None if parts is None else tuple(sorted(parts.items())))
    found = GLRenderer.get().mesh(key, model.puppet, lambda: _items(model.puppet, anim, tick, tracks, default, parts))
    return (found, model.pages) if found is not None else None


def _items(puppet, anim: str, tick: float, tracks, default, parts):
    if tracks is None and parts is None:
        return puppet.evaluate(anim, tick)
    a = puppet.anims[anim]
    items = []
    for t in range(a["tcount"]):
        when = tick if tracks is None else tracks.get(t, default)
        item = None if when is None else puppet.track_item(a["tstart"] + t, when)
        if item is not None:
            item.only = (parts or {}).get(t, -1)
            items.append(item)
    return items


def draw(target, file: str, anim: str, point: tuple[float, float], scale: float, tick: float = 0,
         tracks: Optional[dict[int, Optional[float]]] = None, default: float = 0,
         parts: Optional[dict[int, int]] = None, alpha: float = 1.0, flip: bool = False, mul=(1.0, 1.0, 1.0)) -> bool:
    """Элемент интерфейса игры в картинку pygame target так, что его точка 0,0 — в point.
    False — нечего рисовать. (В кадр видеокарты элементы интерфейса рисует battle.hud.)"""
    found = sprite(file, anim, tick, scale, flip, tracks, default, parts)
    if found is None:
        return False
    image, (ox, oy) = found
    if alpha < 0.996 or tuple(mul) != (1.0, 1.0, 1.0):
        import pygame
        image = image.copy()
        image.fill((*(round(255 * m) for m in mul), round(255 * alpha)), special_flags=pygame.BLEND_RGBA_MULT)
    target.blit(image, (round(point[0] - ox), round(point[1] - oy)))
    return True


def fill(target, color, rect) -> None:
    """Залитый прямоугольник в картинку pygame."""
    import pygame
    pygame.draw.rect(target, color, rect)


def sprite(file: str, anim: str, tick: float = 0, scale: float = 1.0, flip: bool = False,
           tracks: Optional[dict[int, Optional[float]]] = None, default: float = 0,
           parts: Optional[dict[int, int]] = None):
    """Элемент интерфейса игры как (pygame.Surface, точка 0,0 раскладки в пикселях) или None.
    tracks — свои тики трекам (номер внутри анимации), остальным default; без tracks — вся анимация в tick.
    parts — трек → какую одну деталь его кадра рисовать (цифры NUM_*). Масштаб — ступенями (snap)."""
    scale = snap(scale)
    key = (file, anim, round(tick, 1), round(scale, 3), flip,
           None if tracks is None else tuple(sorted((t, None if v is None else round(v, 1)) for t, v in tracks.items())),
           default, None if parts is None else tuple(sorted(parts.items())))
    if key in _SPRITES:
        _SPRITES.move_to_end(key)
        return _SPRITES[key]
    found = None
    model = source().model("GUI", file)
    if model is not None and anim in model.puppet.anims:
        import pygame
        from .gl import GLRenderer
        puppet = model.puppet
        items = _items(puppet, anim, tick, tracks, default, parts)
        done = GLRenderer.get().render(puppet, model.pages, items, scale, flip) if items else None
        if done is not None:
            rgba, origin = done
            surface = pygame.image.frombuffer(rgba.tobytes(), (rgba.shape[1], rgba.shape[0]), "RGBA")
            try:
                surface = surface.convert_alpha()
            except pygame.error:     # нет окна
                surface = surface.copy()
            found = surface, (round(origin[0]), round(origin[1]))
    _SPRITES[key] = found
    while len(_SPRITES) > SPRITES_MAX:
        _SPRITES.popitem(last=False)
    return found
