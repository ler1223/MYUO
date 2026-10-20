"""Куклы и эффекты Unicorn Overlord прямо из файлов игры, нарисованные видеокартой (engine.uo.gl).

Откуда берутся данные:
- папка распакованного Unicorn.CPK — MYUO_UO_SRC или assets/uo_anim/local.json {"src": "..."}
  (его пишут инструменты tools/uo_extract, когда их запускают с --src);
- что играть — data/uo_anim.json (правит редактор tools/uo_extract/anim_editor.py); файл
  перечитывается, когда меняется, поэтому правки из редактора видны без перезапуска.

LiveAnims — анимации классов: части состояний (стойка, атака, навыки…), кадр части в момент
tick нужного масштаба. LiveFx — эффекты навыков (uo_<анимация Battle_Effect>) в том же виде,
что эффекты assets/fx (engine.sprites.FxLibrary), только кадры рисуются на лету.

Нет папки игры, moderngl или видеокарты — has() ложно, и всё рисуется как раньше.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Optional

import numpy as np

from . import ftx
from .gl import GLRenderer
from .puppet import ADD, Puppet

SNAP_STEPS = 16             # масштабы кадров — ступенями 1/16 октавы (~4%): пока камера наезжает,
                            # соседние кадры берутся из кэша, а не рисуются заново каждый кадр


FRAME_STEP = 2              # кадры бойцов через тик (30 в секунду): вдвое меньше рисования и памяти


def snap(k: float) -> float:
    """Ближайшая ступень масштаба."""
    return 2 ** (round(math.log2(max(k, 1e-3)) * SNAP_STEPS) / SNAP_STEPS) if k > 0 else k

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG = ROOT / "data" / "uo_anim.json"
LOCAL = ROOT / "assets" / "uo_anim" / "local.json"
CACHE = ROOT / "assets" / "uo_anim" / "_cache"
TICKS = 60
WORLD_HUMAN = 185           # рост человека в единицах мира сцены (size эффектов, как в assets/fx/effects.json)
TALK = re.compile(r"^(D_|FACE_|EP_|HG_D_)")
IDLE = "idle"


# --- выбор анимаций (общий для игры, сборщиков и редактора) ---------------------------

def natural(name: str) -> tuple:
    m = re.match(r"^(.*?)(\d*)$", name)
    return m.group(1), int(m.group(2) or 0)


def resolve_chain(names: list[str], patterns: list[str]) -> list[str]:
    """Первое правило с совпадениями; из совпадений — группа первого имени (без цифр в конце) по порядку."""
    for pat in patterns:
        hits = sorted((n for n in names if re.match(pat, n)), key=natural)
        if hits:
            base = natural(hits[0])[0]
            return [n for n in hits if natural(n)[0] == base]
    return []


def speed_segments(start: int, end: int, zones) -> list[tuple[float, float, float]]:
    """Отрезки анимации [a, b) со скоростью: зоны части (speed: [{from, to, rate}], rate > 1 — быстрее,
    < 1 — медленнее) поверх обрезки [start, end); промежутки между зонами — скорость 1. Зоны не
    должны пересекаться: при пересечении побеждает та, что раньше в списке."""
    marks = {float(start), float(end)}
    clean = []
    for z in zones or ():
        a, b = max(float(z.get("from") or 0), start), min(float(z.get("to") or end), end)
        rate = float(z.get("rate") or 1)
        if b > a and rate > 0:
            clean.append((a, b, rate))
            marks.update((a, b))
    out = []
    points = sorted(marks)
    for a, b in zip(points, points[1:]):
        rate = next((r for za, zb, r in clean if za <= a and b <= zb), 1.0)
        out.append((a, b, rate))
    return out


def timeline_ticks(start: int, end: int, zones) -> float:
    """Сколько тиков времени занимает часть [start, end) с зонами скорости."""
    return sum((b - a) / rate for a, b, rate in speed_segments(start, end, zones))


def anim_tick(part: dict, index: int) -> int:
    """Тик анимации в момент index (тики времени от начала части) с учётом зон скорости."""
    zones = part.get("speed")
    if not zones:
        return part["from"] + index
    left = float(index)
    end = part.get("to", part["from"] + part["frames"])
    for a, b, rate in speed_segments(part["from"], end, zones):
        span = (b - a) / rate
        if left < span:
            return int(a + left * rate)
        left -= span
    return int(end) - 1


def state_parts(spec: dict, config: dict, names: list[str], state: str) -> list[dict]:
    """Части состояния класса: [{anim, from, to}] — выбранные вручную или по правилам конфига.
    Вручную заданный пустой список — у класса нет этого состояния. Состояние skill.<навык> —
    анимация навыка класса (classes.<класс>.skills)."""
    if state.startswith("skill."):
        manual = spec.get("skills", {}).get(state[len("skill."):], [])
    else:
        manual = spec.get("states", {}).get(state)
    if manual is not None:
        parts = [{"anim": e} if isinstance(e, str) else dict(e) for e in manual]
        return [p for p in parts if p.get("anim") in names]
    broken = set(config.get("broken", {}).get(spec["file"], []))
    rule = config["states"].get(state, {})
    return [{"anim": n} for n in resolve_chain([n for n in names if n not in broken], rule.get("chain", []))]


BG_FRONT = re.compile(r"^(kinkei|maekusa|zenkei)|temae", re.IGNORECASE)   # передний план фона: поверх юнитов
BG_HIDDEN = re.compile(r"^effect", re.IGNORECASE)                       # вспышки сцены в фоне не рисуются


def bg_role(anim: str, layers: dict) -> str:
    """Роль слоя фона боя: back, front или hidden — задана в конфиге (backgrounds.<фон>.layers) или по имени."""
    return layers.get(anim) or ("hidden" if BG_HIDDEN.search(anim) else "front" if BG_FRONT.search(anim) else "back")


# --- источник: папка игры, конфиг, модели ---------------------------------------------

def game_folder() -> Optional[Path]:
    src = os.environ.get("MYUO_UO_SRC")
    if not src and LOCAL.is_file():
        try:
            src = json.loads(LOCAL.read_text(encoding="utf-8")).get("src")
        except ValueError:
            src = None
    return Path(src) if src and Path(src).is_dir() else None


def remember_game_folder(src: Path) -> None:
    """Запомнить папку игры для самой игры (её зовут инструменты, запущенные с --src)."""
    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    LOCAL.write_text(json.dumps({"src": str(Path(src).resolve())}, ensure_ascii=False), encoding="utf-8")


def texture_pages(src: Path, folder: str, name: str) -> list[np.ndarray]:
    """Страницы текстуры <name>.ftx как RGBA; распакованные кэшируются в assets/uo_anim/_cache (PNG)."""
    from PIL import Image
    out, i = [], 0
    while (CACHE / folder / f"{name}.{i}.png").is_file():
        out.append(np.asarray(Image.open(CACHE / folder / f"{name}.{i}.png").convert("RGBA")))
        i += 1
    if out:
        return out
    path = src / folder / f"{name}.ftx"
    if not path.is_file():
        return []
    data = path.read_bytes()
    _, texs = ftx.parse(data)
    (CACHE / folder).mkdir(parents=True, exist_ok=True)
    for i, tex in enumerate(texs):
        image = ftx.decode(data, tex)
        image.save(CACHE / folder / f"{name}.{i}.png", compress_level=1)
        out.append(np.asarray(image.convert("RGBA")))
    return out


class Model:
    """Кукла файла игры с текстурами на видеокарте."""

    def __init__(self, src: Path, folder: str, file: str, variant: int, skin: Optional[str] = None):
        self.puppet = Puppet((src / folder / f"{file}.mbs").read_bytes(), variant)
        gl = GLRenderer.get()
        skin = skin or next((n for n in (f"{file}00", file) if (src / folder / f"{n}.ftx").is_file()), file)
        self.pages = [gl.texture(p) for p in texture_pages(src, folder, skin)]
        self.names = list(self.puppet.anims)
        self._boxes: dict = {}

    def length(self, anim: str) -> int:
        return self.puppet.anim_length(anim) if anim in self.puppet.anims else 0

    def items(self, anim: str, tick: float, loop: bool = False):
        return self.puppet.evaluate(anim, tick, loop)

    def frame(self, anim: str, tick: float, scale: float, flip: bool, loop: bool = False, box=None,
              premultiplied: bool = False):
        """(RGBA [h, w, 4], точка 0,0 персонажа в пикселях) или None."""
        return GLRenderer.get().render(self.puppet, self.pages, self.items(anim, tick, loop), scale, flip, box,
                                       premultiplied=premultiplied)

    def box(self, anim: str, start: float = 0, end: Optional[float] = None, step: float = 4):
        """Рамка анимации (единицы игры) по кадрам с шагом step тиков."""
        key = (anim, start, end)
        if key not in self._boxes:
            end = self.length(anim) if end is None else end
            boxes = [b for b in (self.puppet.bbox(self.items(anim, t)) for t in np.arange(start, max(start + 1, end), step))
                     if b]
            self._boxes[key] = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes),
                                max(b[3] for b in boxes)) if boxes else None
        return self._boxes[key]


class Source:
    """Папка игры + data/uo_anim.json (перечитывается, когда файл меняется) + модели."""

    def __init__(self, src: Optional[Path] = None, config: Path = CONFIG):
        self.src = Path(src) if src else game_folder()
        self.config_path = config
        self.config: dict[str, Any] = {}
        self.version = 0
        self._mtime = None
        self._checked = 0.0
        self._models: dict = {}
        self.refresh(force=True)

    @property
    def ok(self) -> bool:
        return self.src is not None and GLRenderer.get() is not None and bool(self.config)

    def refresh(self, force: bool = False) -> bool:
        """Перечитать конфиг, если он изменился (не чаще раза в секунду). True — перечитан."""
        now = time.monotonic()
        if not force and now - self._checked < 1.0:
            return False
        self._checked = now
        try:
            mtime = self.config_path.stat().st_mtime
        except OSError:
            return False
        if mtime == self._mtime:
            return False
        try:
            self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except ValueError:          # файл как раз пишут — прочитаем в следующий раз
            return False
        self._mtime = mtime
        self.version += 1
        self._models = {k: m for k, m in self._models.items() if k[3] == self._variant_of(k)}
        return True

    def _variant_of(self, key) -> int:
        folder, file, _, variant, cid = key
        return int(self.config.get("classes", {}).get(cid, {}).get("variant", 0)) if cid else variant

    def model(self, folder: str, file: str, variant: int = 0, cid: str = "") -> Optional[Model]:
        key = (folder, file, None, variant, cid)
        if key not in self._models:
            try:
                self._models[key] = Model(self.src, folder, file, variant) if self.ok and \
                    (self.src / folder / f"{file}.mbs").is_file() else None
            except Exception:       # битый файл не должен ронять игру
                self._models[key] = None
        return self._models[key]

    def class_model(self, cid: str) -> Optional[Model]:
        spec = self.config.get("classes", {}).get(cid)
        if not spec:
            return None
        return self.model(spec.get("folder", "Chara"), spec["file"], int(spec.get("variant", 0)), cid)


_SOURCE: Optional[Source] = None


def source() -> Source:
    global _SOURCE
    if _SOURCE is None:
        _SOURCE = Source()
    return _SOURCE


# --- анимации классов ----------------------------------------------------------------

class LiveAnims:
    """Части состояний классов и их кадры (интерфейс как у прежних листов engine.uo_anim)."""

    SCALED_MB = 300

    def __init__(self, src: Optional[Source] = None):
        self.source = src or source()
        self._parts: dict = {}
        self._heights: dict = {}
        self._scaled: OrderedDict = OrderedDict()
        self._bytes = 0
        self._stills: dict = {}
        self._version = -1

    def _sync(self) -> None:
        self.source.refresh()
        if self._version != self.source.version:
            self._version = self.source.version
            self._parts.clear()
            self._heights.clear()
            self._stills.clear()
            self._scaled.clear()
            self._bytes = 0

    @property
    def classes(self) -> dict:
        return self.source.config.get("classes", {})

    def has(self, cid: str) -> bool:
        return self.source.ok and bool(self.parts(cid, IDLE))

    def parts(self, cid: str, state: str) -> list[dict]:
        """Части состояния: {class, anim, from, frames (тики), ms, loop}."""
        self._sync()
        key = (cid, state)
        if key not in self._parts:
            spec, model = self.classes.get(cid), self.source.class_model(cid) if self.source.ok else None
            out = []
            if spec and model:
                for p in state_parts(spec, self.source.config, model.names, state):
                    start = int(p.get("from") or 0)
                    end = min(model.length(p["anim"]), int(p.get("to") or 10 ** 9))
                    zones = [z for z in (p.get("speed") or []) if isinstance(z, dict)]
                    ticks = max(1, round(timeline_ticks(start, end, zones))) if end > start else 1
                    out.append({"class": cid, "anim": p["anim"], "from": start, "to": max(end, start + 1),
                                "frames": ticks, "ms": round(ticks * 1000 / TICKS), "loop": state == IDLE,
                                **({"speed": zones} if zones else {})})
            self._parts[key] = out
        return self._parts[key]

    def height(self, cid: str) -> float:
        """Рост класса в стойке (единицы игры): верх фигуры в первом кадре стойки."""
        self._sync()
        if cid not in self._heights:
            parts, model = self.parts(cid, IDLE), self.source.class_model(cid)
            box = model.puppet.bbox(model.items(parts[0]["anim"], parts[0]["from"])) if parts and model else None
            self._heights[cid] = -box[1] if box and box[1] < 0 else 300.0
        return self._heights[cid]

    def ratio(self, cid: str) -> float:
        human = self.source.config.get("human")
        return self.height(cid) / (self.height(human) if human in self.classes else 300.0)

    def height_px(self, cid: str) -> float:
        """Рост в стойке в «пикселях» масштаба 1 (единицы игры)."""
        return self.height(cid)

    def scaled(self, part: dict, index: int, k: float, flip: bool):
        """(кадр, None вместо белого силуэта, точка ног в кадре) части в тике index при масштабе k."""
        import pygame
        self._sync()
        k = snap(k)
        index -= index % FRAME_STEP
        key = (part["class"], part["anim"], anim_tick(part, index), k, flip)
        if key in self._scaled:
            self._scaled.move_to_end(key)
            return self._scaled[key]
        model = self.source.class_model(part["class"])
        found = model.frame(part["anim"], anim_tick(part, index), k, flip, part.get("loop", False)) if model else None
        if found is None:
            sprite, origin = pygame.Surface((1, 1), pygame.SRCALPHA), (0, 0)
        else:
            rgba, origin = found
            sprite = pygame.image.frombuffer(rgba.tobytes(), (rgba.shape[1], rgba.shape[0]), "RGBA")
            if pygame.display.get_surface() is not None:
                sprite = sprite.convert_alpha()
            else:
                sprite = sprite.copy()
        result = (sprite, None, origin)            # белый силуэт (вспышка удара) сцена делает сама, когда нужен
        self._scaled[key] = result
        self._bytes += sprite.get_width() * sprite.get_height() * 4
        while self._bytes > self.SCALED_MB * 2 ** 20 and len(self._scaled) > 1:
            _, (old, _, _) = self._scaled.popitem(last=False)
            self._bytes -= old.get_width() * old.get_height() * 4
        return result

    def mesh(self, part: dict, index: int):
        """(сетка кадра на видеокарте, страницы атласа) части в тике index — для кадра поля
        (engine.uo.frame); масштаб — рост в пикселях / height_px. None — нет кадра."""
        self._sync()
        model = self.source.class_model(part["class"])
        if model is None:
            return None
        tick = anim_tick(part, index)
        loop = part.get("loop", False)
        mesh = GLRenderer.get().mesh(("unit", id(model), part["anim"], tick, loop), model.puppet,
                                     lambda: model.items(part["anim"], tick, loop))
        return (mesh, model.pages) if mesh is not None else None

    def still(self, cid: str):
        """Первый кадр стойки (портреты, карточки, карта мира)."""
        self._sync()
        if cid not in self._stills:
            part = self.idle_part(cid)
            self._stills[cid] = self.scaled(part, 0, 1.0, False)[0] if part else None
        return self._stills[cid]

    def idle_part(self, cid: str) -> Optional[dict]:
        parts = self.parts(cid, IDLE)
        return parts[0] if parts else None

    def idle_at(self, cid: str, ms: int) -> Optional[tuple[dict, int]]:
        """(часть, тик) стойки в момент ms: части стойки идут друг за другом по кругу."""
        parts = self.parts(cid, IDLE)
        total = sum(max(1, int(p["ms"])) for p in parts)
        if not total:
            return None
        t = ms % total
        for part in parts:
            ms_part = max(1, int(part["ms"]))
            if t < ms_part:
                return part, min(int(part["frames"]) - 1, int(t * int(part["frames"]) / ms_part))
            t -= ms_part
        return parts[-1], int(parts[-1]["frames"]) - 1


# --- эффекты навыков -----------------------------------------------------------------

class LiveFx:
    """Эффекты uo_<анимация Battle_Effect> для engine.sprites.FxLibrary: описание и кадры на лету."""

    SCALED_MB = 150

    def __init__(self, src: Optional[Source] = None):
        self.source = src or source()
        self._specs: dict = {}
        self._scaled: OrderedDict = OrderedDict()
        self._bytes = 0

    def model(self) -> Optional[Model]:
        return self.source.model("Effect", self.source.config.get("effects_file", "Battle_Effect")) \
            if self.source.ok else None

    def anim_of(self, name: str) -> Optional[str]:
        """Имя анимации эффекта: из раздела effects конфига или uo_<анимация> навыков."""
        rule = self.source.config.get("effects", {}).get(name)
        if rule:
            return rule["anim"]
        model = self.model()
        if model is None or not name.startswith("uo_"):
            return None
        wanted = name[3:].upper()
        return wanted if wanted in model.puppet.anims else None

    def spec(self, name: str) -> Optional[dict]:
        self.source.refresh()
        if name not in self._specs:
            anim, model = self.anim_of(name), self.model()
            spec = None
            if anim and model:
                box = model.box(anim)
                if box:
                    rx, ry = max(abs(box[0]), abs(box[2])), max(abs(box[1]), abs(box[3]))
                    items = [it for t in range(0, max(1, model.length(anim)), 4) for it in model.items(anim, t)]
                    modes = [int(model.puppet.p_mode[p]) for it in items for p in model.puppet.item_polys(it)[0]]
                    human = LiveAnims(self.source).height(self.source.config.get("human", "")) or 300.0
                    rule = self.source.config.get("effects", {}).get(name, {})
                    spec = {"frames": max(1, model.length(anim)), "fps": TICKS, "loop": False,
                            "size": round(2 * ry * WORLD_HUMAN / human, 1), "box": (-rx, -ry, rx, ry),
                            "blend": "add" if sum(m == ADD for m in modes) * 2 >= max(1, len(modes)) else "alpha",
                            "layer": rule.get("layer", "front"), "anchor": rule.get("anchor", "body"), "anim": anim}
            self._specs[name] = spec
        return self._specs[name]

    def scaled(self, name: str, frame: int, height: int, flip: bool, angle: float = 0.0):
        """Кадр эффекта высотой height пикселей окна (ширина — по пропорциям эффекта)."""
        import pygame
        spec = self.spec(name)
        if spec is None:
            return None
        height = max(1, round(snap(height)))
        frame -= frame % FRAME_STEP
        key = (name, frame, height, flip, round(angle / 3) * 3)
        if key in self._scaled:
            self._scaled.move_to_end(key)
            return self._scaled[key]
        box = spec["box"]
        k = height / max(1.0, box[3] - box[1])
        found = self.model().frame(spec["anim"], frame, k, flip, box=box, premultiplied=spec["blend"] == "add")
        if found is None:
            return None
        rgba, _ = found
        if spec["blend"] == "add":      # на чёрном: цвет складывается с картинкой
            image = pygame.image.frombuffer(np.ascontiguousarray(rgba[..., :3]).tobytes(), (rgba.shape[1], rgba.shape[0]), "RGB").copy()
        else:
            image = pygame.image.frombuffer(rgba.tobytes(), (rgba.shape[1], rgba.shape[0]), "RGBA").copy()
        if key[-1]:
            image = pygame.transform.rotate(image, key[-1])
        self._scaled[key] = image
        self._bytes += image.get_width() * image.get_height() * 4
        while self._bytes > self.SCALED_MB * 2 ** 20 and len(self._scaled) > 1:
            _, old = self._scaled.popitem(last=False)
            self._bytes -= old.get_width() * old.get_height() * 4
        return image

    def mesh(self, name: str, frame: int):
        """(сетка кадра эффекта, страницы, описание) — для кадра поля; точка 0,0 — центр эффекта."""
        spec, model = self.spec(name), self.model()
        if spec is None or model is None:
            return None
        frame = max(0, min(int(frame), spec["frames"] - 1))
        mesh = GLRenderer.get().mesh(("fx", id(model), spec["anim"], frame), model.puppet,
                                     lambda: model.items(spec["anim"], frame))
        return (mesh, model.pages, spec) if mesh is not None else None

    def aspect(self, name: str) -> float:
        box = self.spec(name)["box"]
        return (box[2] - box[0]) / max(1.0, box[3] - box[1])


def duration_ms(spec: dict) -> int:
    return int(math.ceil(spec["frames"] * 1000 / spec.get("fps", TICKS)))
