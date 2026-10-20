"""Вкладка Stage: бой статичными спрайтами юнитов в сцене 2.5D, как в Unicorn Overlord.

Юниты стоят в трёхмерной сцене (engine.scene); живость дают движения в мире (рывок с
послеобразами, прыжок, отскок, наклон, отбрасывание, подъём, свечение) и трёхмерные эффекты
(engine.fx). Рывок вглубь уменьшает спрайт, к зрителю — увеличивает. Камера наезжает на
атакующего и цели (engine.camera).

Классы с листами анимаций из Unicorn Overlord (engine.uo_anim, assets/uo_anim) ещё и играют их:
стойка по кругу, при рывке к цели — бег, удар по прибытии, бег назад; на месте — атака или каст;
попадание, уклонение, прикрытие и смерть — свои анимации (_animate_*).

Что делает каждый навык, задаётся данными в assets/visuals/skills.json: шаги в момент
применения (cast) и на каждое попадание (hit). Навыки без описания берут общий визуал по виду.
Спрайты: assets/units/<id>.png, нарезанные tools/cut_lineup.py с одного листа.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import pygame

from engine.backdrop import Backdrop
from engine.camera import FOCUS_ZOOM, Camera
from engine.fx import (
    ELEMENT_COLORS,
    SKY_HEIGHT,
    ArrowRain,
    Beam,
    Bolt,
    Dome,
    Effect,
    Flash,
    FloatText,
    Glint,
    Pillar,
    Projectile,
    Ring,
    RuneCircle,
    Slash,
    Thrust,
    WeaponStrike,
    WrapRing,
    add_glow,
    ease_out,
    fx_font,
    glow_sprite,
)
from engine.projection import World
from engine.render import GROUND, OVERLAY, UPRIGHT, Part, View, draw_parts, draw_parts_gl
from engine.scene import PROPS_DIR, SceneConfig, SceneObject
from engine.sprites import FxLibrary, SpriteBeam, SpriteEffect, SpriteProjectile
from engine.uo import ui as uo_ui
from engine.uo.frame import GLFrame
from engine.uo.gl import GLRenderer
from engine.uo.library import LiveAnims, LiveFx
from engine.uo_anim import Actions, Clip
from game.events import (
    AttackMissed,
    Covered,
    DamageDealt,
    Event,
    Healed,
    RoundStarted,
    SkillUsed,
    TurnSkipped,
    TurnStarted,
    UnitDied,
)
from game.save import clone_scenario
from game.scenario import DEMO_SEED, build_demo_battle, build_showcase
from game.unit import Unit
from pygame_battle import BattleScreen, skill_visual, weapon_kind
from pygame_images import ImageBank, placeholder  # noqa: F401
from pygame_ui import GREEN, RED

ROOT = Path(__file__).resolve().parent
UNITS_DIR = ROOT / "assets" / "units"
TEMP_SPRITES_DIR = ROOT / "assets" / "ref" / "sprites"   # временные спрайты из референсов (tools/ref_sprites.py)
TEMP_PREFIX = "ref:"
UO_PREFIX = "uo:"           # анимированный юнит из Unicorn Overlord (engine.uo.library)
# Куклы из Unicorn Overlord включены, если есть папка игры и видеокарта; MYUO_UO_ANIM=0 выключает (так делают тесты).
UO_ANIM_ENABLED = os.environ.get("MYUO_UO_ANIM", "1") != "0"
# Поле боя рисует видеокарта целиком (engine.uo.frame), если куклы включены; MYUO_GL_FIELD=0 — по-старому pygame.
GL_FIELD = UO_ANIM_ENABLED and os.environ.get("MYUO_GL_FIELD", "1") != "0"
VISUALS_PATH = ROOT / "assets" / "visuals" / "skills.json"
UO_ANIM_CONFIG = ROOT / "data" / "uo_anim.json"

FOCUS_MS = 700             # сколько после удара участники атаки остаются в фокусе
SEE_THROUGH = 70           # непрозрачность того, кто закрывает участника атаки (из 255)
FADE_MS = 120              # скорость перехода прозрачности
DEFAULT_WINDUP = 380
DEATH_MS = 800
TRAIL_GHOSTS = 4           # послеобразов при рывке
TRAIL_STEP_MS = 28
FLYING_TAG = "flying"
TALL = 1.3                 # спрайт выше человека в столько раз — «большой» (всадник): тень шире
# Анимации юнитов (engine.uo_anim): сколько удар может задержать возврат после рывка, сколько
# держится середина каста, на сколько можно ускорить начало каста, сдвиг стойки соседей.
STRIKE_HOLD_MAX = 1200
CAST_LOOP_MS = 300
CAST_SPEEDUP = 2.0
IDLE_DESYNC_MS = 731
# Навык с эффектами из Unicorn Overlord (data/uo_anim.json, skill_fx): из шагов его визуала остаются только
# движения, эффекты — из игры (каст на применившем, попадание на цели).
UO_MOTION_STEPS = {"dash", "hop", "lunge", "jump", "rise", "tilt", "knockback", "shake"}
SKILL_PART_MAX_MS = 1500           # длинная часть анимации навыка (удержание каста) сжимается до этого
SIDE_RING = {"left": (60, 110, 220), "right": (220, 70, 60)}
CURRENT_RING = (230, 200, 80)
# Бои вкладки: демонстрация всех навыков и пассивок, пять тестовых классов, расстановка игрока.
MODES = ("demo", "showcase", "setup")
MODE_LABELS = {"demo": "demo battle (T)", "showcase": "test squads (T)", "setup": "your squads (T)",
               "world": "world battle (ENTER — back)", "tower": "tower floor (ENTER when over)"}
# Чужие бои: сцена показывает бой, который дал хозяин (encounter), и по Enter после боя зовёт on_return.
# В круг клавиши T они не входят.
WORLD_MODE = "world"       # стычка в открытом мире
TOWER_MODE = "tower"       # этаж башни (окно tower.py)
EXTERNAL_MODES = (WORLD_MODE, TOWER_MODE)


# --- движения спрайтов --------------------------------------------------------

@dataclass
class Motion:
    """Сдвиг юнита в мире: туда (go мс), держится (hold), обратно (back).

    dx, dz: сдвиг по полю и вглубь; dy: подъём (держится); lift: высота дуги прыжка;
    angle: наклон в градусах. trail: рисовать послеобразы, пока юнит движется.
    """

    start: int
    go: int
    hold: int
    back: int
    dx: float = 0.0
    dz: float = 0.0
    dy: float = 0.0
    lift: float = 0.0
    angle: float = 0.0
    trail: bool = False

    @property
    def end(self) -> int:
        return self.start + self.go + self.hold + self.back

    def at(self, now: int) -> Optional[tuple[float, float, float, float]]:
        """(dx, высота, dz, угол) в момент now; None вне движения."""
        t = now - self.start
        total = self.go + self.hold + self.back
        if t < 0 or t > total:
            return None
        if t < self.go:
            k = ease_out(t / max(1, self.go))
        elif t < self.go + self.hold:
            k = 1.0
        else:
            u = (t - self.go - self.hold) / max(1, self.back)
            k = 1 - u * u * (3 - 2 * u)
        return self.dx * k, self.dy * k + self.lift * math.sin(math.pi * t / max(1, total)), self.dz * k, self.angle * k

    def moving(self, now: int) -> bool:
        t = now - self.start
        return 0 <= t < self.go or self.go + self.hold < t <= self.go + self.hold + self.back


@dataclass
class Tint:
    """Свечение спрайта цветом: нарастает и гаснет."""

    start: int
    duration: int
    color: tuple[int, int, int]

    def strength(self, now: int) -> float:
        t = (now - self.start) / max(1, self.duration)
        return math.sin(math.pi * t) if 0 <= t <= 1 else 0.0


def uo_skill_fx() -> dict[str, dict[str, list[str]]]:
    """Навык -> эффекты из Unicorn Overlord: {"cast": [имя в FxLibrary], "hit": [...]} (data/uo_anim.json).
    Имя эффекта — uo_<анимация Battle_Effect>, как его собирает tools/uo_extract/build_anims.py."""
    if not UO_ANIM_CONFIG.is_file():
        return {}
    name = lambda e: "uo_" + (e if isinstance(e, str) else e["anim"]).lower()
    fx = json.loads(UO_ANIM_CONFIG.read_text(encoding="utf-8")).get("skill_fx", {})
    return {sid: {k: [name(e) for e in v.get(k, [])] for k in ("cast", "hit")} for sid, v in fx.items()}


# --- картинки -----------------------------------------------------------------

class SpriteBank(ImageBank):
    """Спрайты классов, их рост относительно человека и опорные точки (assets/units/units.json).

    Временные спрайты из референсов (папка temporary, tools/ref_sprites.py) встают вместо временных
    похожих старых (fallback.classes), но не вместо своих спрайтов класса из assets/units.
    Анимированные юниты из Unicorn Overlord (anims — engine.uo.library.LiveAnims или то же по
    интерфейсу) важнее всех: их id — «uo:<класс>», картинка для неподвижных мест — первый кадр стойки."""

    def __init__(self, folder: Path = UNITS_DIR, temporary: Optional[Path] = TEMP_SPRITES_DIR,
                 anims: Any = "live"):
        super().__init__(folder)
        path = self.folder / "units.json"
        self.config: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.temporary = Path(temporary) if temporary else None
        if self.temporary and (self.temporary / "units.json").is_file():
            self._add_temporary(json.loads((self.temporary / "units.json").read_text(encoding="utf-8")))
        self.anims = (LiveAnims() if UO_ANIM_ENABLED else None) if anims == "live" else anims

    def _add_temporary(self, index: dict[str, Any]) -> None:
        sprites = self.config.setdefault("sprites", {})
        sheets = self.config.setdefault("sheets", {})
        classes = self.config.setdefault("fallback", {}).setdefault("classes", {})
        for class_id, info in index.get("sprites", {}).items():
            if class_id in sprites or not (self.temporary / f"{class_id}.png").is_file():
                continue                                     # свой спрайт класса важнее временного
            sprite_id = TEMP_PREFIX + class_id
            sheets[sprite_id] = {"human_height": info["height"] / max(0.1, info.get("ratio", 1.0))}
            sprites[sprite_id] = {"sheet": sprite_id, "height": info["height"], "flip": bool(info.get("flip"))}
            classes[class_id] = sprite_id

    def image(self, name: str) -> Optional[pygame.Surface]:
        if name.startswith(UO_PREFIX) and name not in self._images:
            self._images[name] = self.anims.still(name[len(UO_PREFIX):-len(".png")]) if self.anims else None
        if self.temporary and name.startswith(TEMP_PREFIX) and name not in self._images:
            path = self.temporary / name[len(TEMP_PREFIX):]
            image = pygame.image.load(str(path)) if path.is_file() else None
            if image is not None and pygame.display.get_surface() is not None:
                image = image.convert_alpha()
            if image is not None and self.sprites.get(name[:-len(".png")], {}).get("flip"):
                image = pygame.transform.flip(image, True, False)      # на арте смотрит влево
            self._images[name] = image
        return super().image(name)

    @property
    def sprites(self) -> dict[str, dict[str, Any]]:
        return self.config.get("sprites", {})

    def sprite_id(self, unit: Unit) -> Optional[str]:
        """Какой спрайт у юнита: свой, по классу из fallback, по тегу, по умолчанию."""
        return self.sprite_for(unit.definition.id, unit.tags)

    def sprite_for(self, class_id: str, tags: Any = ()) -> Optional[str]:
        """Спрайт класса (и его тегов), когда юнита ещё нет — например, отряд врага на карте мира.
        Порядок: анимация из Unicorn Overlord, явное соответствие класса (fallback.classes), свой спрайт
        с тем же id, по тегу, по умолчанию."""
        if self.anims is not None and self.anims.has(class_id):
            return UO_PREFIX + class_id
        sprites = self.sprites
        fallback = self.config.get("fallback", {})
        if fallback.get("classes", {}).get(class_id) in sprites:
            return fallback["classes"][class_id]
        if class_id in sprites:
            return class_id
        for tag, sprite in fallback.get("tags", {}).items():
            if tag in tags and sprite in sprites:
                return sprite
        default = fallback.get("default")
        return default if default in sprites else None

    def ratio(self, sprite_id: Optional[str]) -> float:
        """Высота спрайта в ростах человека (у всадника с копьём около 1.8)."""
        if self.animated(sprite_id):
            return self.anims.ratio(sprite_id[len(UO_PREFIX):])
        info = self.sprites.get(sprite_id or "")
        if not info:
            return 1.0
        human = self.config.get("sheets", {}).get(info.get("sheet"), {}).get("human_height") or info["height"]
        return info["height"] / human

    def anchor(self, sprite_id: Optional[str], on: str) -> Optional[float]:
        """Своя опорная точка спрайта (head, body) в долях его высоты от ног, если задана."""
        return self.sprites.get(sprite_id or "", {}).get("anchors", {}).get(on)

    def aspect(self, sprite_id: Optional[str]) -> float:
        """Ширина картинки к высоте."""
        image = self.image(f"{sprite_id}.png" if sprite_id else "") or placeholder()
        return image.get_width() / image.get_height()

    def unit_sprite(self, sprite_id: Optional[str], px_height: int, flip: bool):
        return self.scaled(f"{sprite_id}.png" if sprite_id else "", px_height, flip, placeholder)

    # --- анимированные юниты (engine.uo_anim) ---

    def animated(self, sprite_id: Optional[str]) -> bool:
        return bool(sprite_id) and sprite_id.startswith(UO_PREFIX) and self.anims is not None \
            and self.anims.has(sprite_id[len(UO_PREFIX):])

    def parts(self, sprite_id: str, state: str) -> list[dict]:
        """Части состояния анимированного юнита (пусто, если такого состояния у класса нет)."""
        return self.anims.parts(sprite_id[len(UO_PREFIX):], state) if self.animated(sprite_id) else []

    def pose(self, sprite_id: str, part: dict, index: int, px_height: float, flip: bool):
        """(кадр, белый силуэт, точка ног в кадре) анимированного юнита: px_height — рост в стойке
        в пикселях окна."""
        class_id = sprite_id[len(UO_PREFIX):]
        k = px_height / max(1.0, self.anims.height_px(class_id))
        return self.anims.scaled(part, index, k, flip)

    def idle_pose(self, sprite_id: str, now: int, px_height: float, flip: bool):
        """Кадр стойки в момент now (мс): части стойки идут по кругу."""
        found = self.anims.idle_at(sprite_id[len(UO_PREFIX):], now)
        return self.pose(sprite_id, *found, px_height, flip) if found else None


def load_visuals(path: Path = VISUALS_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@dataclass
class Place:
    """Где стоит юнит: мировая точка на земле, сторона, спрайт и его рост в единицах мира."""

    x: float
    z: float
    side: str
    sprite: Optional[str]
    height: float                    # высота спрайта
    human: float                     # рост человека
    head: Optional[float] = None     # свои опорные точки спрайта, доли высоты
    body: Optional[float] = None
    hover: float = 0.0               # высота парения летающих
    width: float = 0.0               # ширина спрайта (по картинке)

    @property
    def facing(self) -> int:
        return 1 if self.side == "left" else -1

    @property
    def tall(self) -> bool:
        return self.height > self.human * TALL

    @property
    def shadow(self) -> float:
        """Ширина тени: по ширине спрайта, в разумных пределах."""
        return min(self.human * 0.85, max(self.human * 0.35, (self.width or self.human * 0.6) * 0.55))

    def anchor(self, on: str) -> World:
        if on == "feet":
            return self.x, 0.0, self.z
        if on == "sky":
            return self.x, SKY_HEIGHT, self.z
        if on == "head":
            y = self.height * self.head if self.head else self.human * 0.9
        else:
            y = self.height * self.body if self.body else self.human * 0.5
        return self.x, y + self.hover, self.z


Context = dict[str, Any]


def put(target: Any, image: pygame.Surface, pos: tuple[float, float], alpha: float = 1.0,
        additive: bool = False) -> None:
    """Картинка pygame в картинку pygame или в кадр видеокарты (GLFrame), левый верхний угол в pos."""
    if isinstance(target, GLFrame):
        target.blit(image, pos, alpha, additive)
        return
    if alpha < 0.996:
        image = image.copy()
        image.set_alpha(int(255 * alpha))
    target.blit(image, (round(pos[0]), round(pos[1])), special_flags=pygame.BLEND_RGB_ADD if additive else 0)


def glow(target: Any, pos: tuple[float, float], color, radius: float, strength: float = 1.0) -> None:
    """Свечение (как engine.fx.add_glow) и в кадр видеокарты."""
    if not isinstance(target, GLFrame):
        add_glow(target, pos, color, radius, strength)
        return
    if strength <= 0.02 or radius < 2:
        return
    sprite = glow_sprite(tuple(color), int(radius) // 2 * 2 or 2)
    w, h = sprite.get_size()
    target.image(sprite, (pos[0] - w / 2, pos[1] - h / 2, w, h), alpha=min(1.0, strength), additive=True)


_GROUND_ART: dict[str, pygame.Surface] = {}


def ground_art(kind: str) -> pygame.Surface:
    """Белые заготовки для кадра видеокарты: shadow — залитый эллипс, ring — его контур."""
    if kind not in _GROUND_ART:
        surface = pygame.Surface((256, 64), pygame.SRCALPHA)
        if kind == "shadow":
            pygame.draw.ellipse(surface, (255, 255, 255, 255), surface.get_rect())
        else:
            pygame.draw.ellipse(surface, (255, 255, 255, 255), surface.get_rect(), 5)
        _GROUND_ART[kind] = surface
    return _GROUND_ART[kind]


UO_POPUP_FILE = "Interface"
UO_POPUP_SIZE = 0.42       # цифры UO (высота 76 при 1080p) к масштабу сцены
UO_DIGIT_STEP = 64         # шаг разрядов в NUM_*
UO_WORD_RISE = 70          # подпись (Critical, Guard, Miss) над числом, единицы раскладки


def uo_popup_anims(kind: str, crit: bool, guarded: bool) -> list[str]:
    """Какие раскладки UO показать: число и подпись (крит, защита, промах)."""
    if kind == "miss":
        return ["STR_MISS"]
    if kind == "heal":
        return ["NUM_CRITICAL_HEAL", "STR_CRITICAL_HEAL"] if crit else ["NUM_HEAL"]
    if guarded:
        return ["NUM_GUARD", "STR_CRITICAL_GUARD" if crit else "STR_GUARD"]
    return ["NUM_CRITICAL_DAMAGE", "STR_CRITICAL_DAMAGE"] if crit else ["NUM_DAMAGE"]


@dataclass
class UoPopup(Effect):
    """Всплывающая раскладка интерфейса UO над точкой мира: число урона/лечения (value) или подпись."""

    pos: World = (0, 0, 0)
    anim: str = ""
    value: Optional[int] = None

    def parts(self, now: int) -> list[Part]:
        if self.progress(now) is None:
            return []
        return [Part(OVERLAY, 0, lambda s, v: self.draw(s, v, now), 2, gl=lambda f, v: self.draw(f, v, now))]

    def draw(self, target: Any, view: View, now: int) -> None:
        """В картинку pygame или в кадр видеокарты."""
        tick = int((now - self.start) * 60 / 1000)
        scale = view.cam.s(UO_POPUP_SIZE)
        if not isinstance(target, GLFrame):
            scale = uo_ui.snap(scale)
        tracks = parts = None
        shift = 0.0
        if self.value is not None:
            tracks, parts = uo_ui.number(self.value, 4, 2, tick)
            shift = (len(str(max(0, self.value))[-4:]) - 1) * UO_DIGIT_STEP * scale / 2   # число по центру
        x, y = view.xy(self.pos)
        rise = UO_WORD_RISE * scale if self.value is None and not self.anim.startswith("STR_MISS") else 0
        uo_ui.draw(target, UO_POPUP_FILE, self.anim, (x + shift, y - rise), scale, tick, tracks=tracks, parts=parts)


UO_BANNER_FILE = "Interface_Battle_00"
UO_SKILL_BANNER = "A_SKILL_1"        # красная лента навыка: _ON (появление), сама лента, _OFF (уход)
UO_PASSIVE_BANNER = "S_SKILL"        # синяя — пассивное умение
UO_BANNER_MS = 1500
UO_BANNER_SCALE = 0.42               # к ширине поля 1920
UO_BANNER_FONT = Path(__file__).resolve().parent / "assets" / "fonts" / "LinLibertine_RB.ttf"
_banner_fonts: dict[int, pygame.font.Font] = {}


def banner_font(size: int) -> pygame.font.Font:
    if size not in _banner_fonts:
        _banner_fonts[size] = (pygame.font.Font(str(UO_BANNER_FONT), size) if UO_BANNER_FONT.is_file()
                               else pygame.font.SysFont(None, size, bold=True))
    return _banner_fonts[size]


@dataclass
class UoBanner(Effect):
    """Лента UO с названием навыка вверху поля; side -1 — левая половина (наши), 1 — правая (враги)."""

    text: str = ""
    anim: str = UO_SKILL_BANNER
    side: int = -1

    def draw(self, target: pygame.Surface, clip: pygame.Rect, now: int) -> None:
        model = uo_ui.source().model("GUI", UO_BANNER_FILE)
        if model is None or self.anim not in model.puppet.anims:
            return
        tick = (now - self.start) * 60 / 1000
        opening, closing = model.length(f"{self.anim}_ON"), model.length(f"{self.anim}_OFF")
        left = (self.start + self.duration - now) * 60 / 1000
        if tick < opening:
            anim, tick, shown = f"{self.anim}_ON", tick, tick / max(1, opening)
        elif left < closing:
            anim, tick, shown = f"{self.anim}_OFF", closing - left, left / max(1, closing)
        else:
            anim, tick, shown = self.anim, 0, 1.0
        scale = clip.width / 1920 * UO_BANNER_SCALE
        x = clip.x + clip.width * (0.5 + 0.24 * self.side)
        y = clip.y + clip.height * 0.17
        if not uo_ui.draw(target, UO_BANNER_FILE, anim, (x, y), scale, int(tick)):
            return
        if shown > 0.35:
            size = max(10, round(54 * scale * 1.6))
            text, shadow = self._text(size)
            alpha = min(1.0, (shown - 0.35) / 0.4)
            rect = text.get_rect(center=(round(x), round(y)))
            put(target, shadow, rect.move(2, 2).topleft, alpha)
            put(target, text, rect.topleft, alpha)

    def _text(self, size: int) -> tuple[pygame.Surface, pygame.Surface]:
        """Надпись и её тень (одни и те же картинки, пока лента видна: в кадре видеокарты — одна текстура)."""
        cached = getattr(self, "_texts", None)
        if cached is None or cached[0] != size:
            font = banner_font(size)
            cached = (size, font.render(self.text, True, (255, 246, 226)), font.render(self.text, True, (30, 16, 8)))
            self._texts = cached
        return cached[1], cached[2]


class StageScreen(BattleScreen):
    """Вкладка боя спрайтами. Свой бой: демонстрация, тестовые отряды или расстановка игрока (клавиша T)."""

    def __init__(self, scene: Optional[SceneConfig] = None, props_dir: Optional[Path] = None,
                 field: Optional[pygame.Rect] = None):
        """field — область поля в логических пикселях сцены (по умолчанию FIELD_RECT демо)."""
        super().__init__(field)
        self.scene = scene or SceneConfig()
        self.bank = SpriteBank()
        self.props = ImageBank(props_dir or PROPS_DIR)
        self.backdrop = Backdrop(self.field, props_dir)
        self.skill_visuals = load_visuals()
        self.sprites = FxLibrary(live=LiveFx() if UO_ANIM_ENABLED else None)
        self.skill_fx = uo_skill_fx() if UO_ANIM_ENABLED else {}   # навык -> эффекты из Unicorn Overlord
        self.battle_view: Any = None        # свой BattleView; его создаёт окно
        self.mode = MODES[0]                # какой бой показывает вкладка (клавиша T)
        self.encounter: Optional[Callable[[], Any]] = None   # чужой бой (EXTERNAL_MODES): мир, башня
        self.on_return: Callable[[], None] = lambda: None     # Enter после чужого боя
        # своя плашка под ногами (окно башни): (экран, юнит, HP на сцене, точка ног x y, масштаб) -> None
        self.plate_drawer: Optional[Callable[[pygame.Surface, Unit, int, tuple[int, int], float], None]] = None
        self.stage: dict[int, Place] = {}
        self.motions: dict[int, list[Motion]] = {}
        self.tints: dict[int, list[Tint]] = {}
        self.deaths: dict[int, int] = {}
        self.actions = Actions()            # кадры анимированных юнитов (engine.uo_anim)
        self.focus: tuple[frozenset, int, int] = (frozenset(), 0, 0)   # участники атаки, с, по
        self.alpha: dict[Any, float] = {}   # непрозрачность юнита (uid) или объекта (("prop", i))
        self.banners: list[UoBanner] = []   # ленты с названиями навыков (UO) вверху экрана
        self.fx_until = 0                   # когда доиграют эффекты навыков, которые уже запущены
        self._frame: Optional[GLFrame] = None   # кадр видеокарты (GL_FIELD)
        self._last_draw = 0
        # Шаги визуала навыков: имя -> обработчик (шаг, момент, юнит, контекст).
        self.steps: dict[str, Callable[[dict, int, int, Context], None]] = {
            "dash": self._dash, "hop": self._hop, "lunge": self._hop, "jump": self._jump, "rise": self._rise,
            "tilt": self._tilt, "knockback": self._knockback, "glow": self._glow,
            "projectile": self._projectile, "slash": self._slash, "thrust": self._thrust, "ring": self._ring,
            "wrap": self._wrap, "beam": self._beam, "bolt": self._bolt, "burst": self._burst, "sparkle": self._sparkle,
            "flash": self._flash, "shake": self._shake, "runes": self._runes, "pillars": self._pillars,
            "arrow_rain": self._arrow_rain, "glint": self._glint, "dome": self._dome, "weapon": self._weapon,
            "impact": self._impact, "sprite": self._sprite_step, "sprite_beam": self._sprite_beam,
        }

    # --- бой этой вкладки ---

    def scenario(self, db: Any, setup: Any) -> Any:
        if self.mode in EXTERNAL_MODES and self.encounter is not None:
            return self.encounter()
        if self.mode == "demo":
            return build_demo_battle(db)
        return build_showcase(db) if self.mode == "showcase" else clone_scenario(db, setup)

    def next_mode(self) -> None:
        """Следующий бой: демонстрация -> тестовые отряды -> ваша расстановка."""
        self.mode = MODES[(MODES.index(self.mode) + 1) % len(MODES)] if self.mode in MODES else MODES[0]
        if self.battle_view is not None:
            self.battle_view.restart(DEMO_SEED if self.mode == "demo" else self.battle_view.seed)

    def windup(self, ev: Event) -> Optional[int]:
        """Сколько длится замах навыка: BattleView ставит удар после него."""
        if not isinstance(ev, SkillUsed) or self.battle_view is None:
            return None
        unit = self.battle_view.sim.units.get(ev.user)
        return int(self.spec(unit, ev.skill_id).get("windup", DEFAULT_WINDUP))

    def spec(self, unit: Optional[Unit], skill_id: str) -> dict[str, Any]:
        """Визуал навыка: для класса, для навыка, иначе общий по виду доставки."""
        visuals = self.skill_visuals
        if unit is not None and f"{unit.definition.id}/{skill_id}" in visuals:
            return visuals[f"{unit.definition.id}/{skill_id}"]
        if skill_id in visuals:
            return visuals[skill_id]
        db = self.battle_view.db if self.battle_view is not None else None
        skill = db.skills.get(skill_id) if db is not None else None
        return visuals.get("_defaults", {}).get(skill_visual(skill, unit)[0], {})

    def status_note(self) -> str:
        note = "   " + self.t(MODE_LABELS[self.mode])
        return note + "   " + self.t("camera (C): {state}", state=self.t("on") if self.camera_view.auto else self.t("off"))

    def log_hint(self, autoplay: bool) -> str:
        if self.mode == TOWER_MODE:
            return self.t("SPACE pause   1/2/3 speed   S skip   ENTER after the battle   wheel zoom")
        return super().log_hint(autoplay)

    def handle_event(self, event: pygame.event.Event, pos: tuple[float, float], window_scale: float = 1.0) -> None:
        super().handle_event(event, pos, window_scale)
        if event.type != pygame.KEYDOWN:
            return
        if self.mode in EXTERNAL_MODES:      # чужой бой: только вернуться, когда он закончен
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.battle_view is not None \
                    and self.battle_view.done:
                self.on_return()
        elif event.key == pygame.K_t:
            self.next_mode()

    # --- раскладка ---

    def place_for(self, unit: Unit, side: str, row: int, col: int, cols: int) -> Place:
        """Юнит в клетке формации -> место в мире по сцене."""
        scene = self.scene
        x, z = scene.cell(side, row, col, cols)
        sprite = self.bank.sprite_id(unit)
        human = scene.human_height
        height = human * self.bank.ratio(sprite)
        return Place(x, z, side, sprite, height, human, self.bank.anchor(sprite, "head"),
                     self.bank.anchor(sprite, "body"), scene.fly_height if FLYING_TAG in unit.tags else 0.0,
                     height * self.bank.aspect(sprite))

    def layout(self, sim: Any) -> None:
        self.stage = {}
        for squad, side in ((sim.attacker, "left"), (sim.defender, "right")):
            formation = squad.formation
            for unit in formation.units:
                row, col = formation.position_of(unit.uid)
                self.stage[unit.uid] = self.place_for(unit, side, row, col, formation.cols)

    def point(self, uid: int, on: str = "body") -> World:
        place = self.stage.get(uid)
        return place.anchor(on) if place else super().point(uid, on)

    def facing(self, uid: int) -> int:
        place = self.stage.get(uid)
        return place.facing if place else 1

    def screen_point(self, x: float, y: float) -> World:
        ground = self.scene.projection().unproject(x, y)
        return (ground[0], 0.0, ground[1]) if ground else (0.0, 0.0, 0.0)

    def reset(self) -> None:
        super().reset()
        self.motions.clear()
        self.tints.clear()
        self.deaths.clear()
        self.actions.clear()
        self.alpha.clear()
        self.focus = (frozenset(), 0, 0)
        self.camera_view.focus_until = 0

    # --- события -> движения и эффекты ---

    def spawn(self, view: Any, ev: Any, when: int) -> None:
        super().spawn(view, ev, when)
        units, stage = view.sim.units, self.stage
        if isinstance(ev, SkillUsed):
            unit = units.get(ev.user)
            skill = view.db.skills.get(ev.skill_id)
            visual = skill_visual(skill, unit)
            self.visuals[ev.user] = visual
            if ev.user in stage:
                self.announce(when, ev.user, self.t(skill.name) if skill else ev.skill_id)
            spec = self.spec(unit, ev.skill_id)
            context = self._context(ev.user, ev.target, self._targets_of(view, ev))
            windup = int(spec.get("windup", DEFAULT_WINDUP))
            until = when + windup + FOCUS_MS
            self.focus = (frozenset([ev.user, *context["targets"]]), when, until)
            self._focus_camera(self.focus[0], until)
            self.run(self._steps(spec.get("cast", []), ev.skill_id), when, context, "self")
            self._animate_skill(ev.user, when, windup, visual[0], ev.skill_id)
            self._uo_skill_fx(ev.skill_id, "cast", when, ev.user)
        elif isinstance(ev, DamageDealt) and not self.is_periodic(ev, view.db):
            self.run(self._steps(self.spec(units.get(ev.source), ev.cause).get("hit", []), ev.cause), when,
                     self._context(ev.source, ev.target, [ev.target]), "target")
            self._uo_skill_fx(ev.cause, "hit", when, ev.target)
            if ev.target != ev.source:
                self._animate(ev.target, "hit", when)
        elif isinstance(ev, Healed) and ev.source is not None and ev.amount > 0:
            self.run(self._steps(self.spec(units.get(ev.source), ev.cause).get("hit", []), ev.cause), when,
                     self._context(ev.source, ev.target, [ev.target]), "target")
            self._uo_skill_fx(ev.cause, "hit", when, ev.target)
        elif isinstance(ev, AttackMissed) and ev.target in stage:   # уклонение: короткий отскок назад
            self._move(ev.target, Motion(when, 90, 80, 260, dx=-stage[ev.target].facing * 22, lift=10))
            self._animate(ev.target, "avoid", when)
        elif isinstance(ev, Covered):
            self._cover(ev, when)
            self._animate(ev.protector, "cover" if self._parts(ev.protector, "cover") else "guard", when + 200)
        elif isinstance(ev, UnitDied):
            self.deaths[ev.unit] = when + self._animate(ev.unit, "die", when, hold=True)
            if ev.unit in stage:
                self._uo_effect("uo_death", when, stage[ev.unit].anchor("body"), stage[ev.unit].facing)

    def announce(self, when: int, uid: int, text: str, passive: bool = False) -> None:
        """Название навыка лентой UO вверху экрана на стороне бойца (навык — красная A_SKILL,
        пассивное умение — синяя S_SKILL); новая лента той же стороны сменяет прежнюю. Без игры — как у родителя."""
        if not (UO_ANIM_ENABLED and uo_ui.source().ok) or uid not in self.stage:
            super().announce(when, uid, text, passive)
            return
        side = -1 if self.stage[uid].facing > 0 else 1        # смотрит вправо — наш, лента слева
        self.banners = [b for b in self.banners if b.side != side or b.start + b.duration < when] + [
            UoBanner(when, UO_BANNER_MS, text, UO_PASSIVE_BANNER if passive else UO_SKILL_BANNER, side)]

    def popup(self, when: int, uid: int, kind: str, amount: int = 0, crit: bool = False, guarded: bool = False) -> None:
        """Цифры и подписи UO (NUM_*, STR_* из GUI/Interface.mbs); без игры — как у родителя."""
        anims = uo_popup_anims(kind, crit, guarded) if UO_ANIM_ENABLED and uo_ui.source().ok else None
        model = uo_ui.source().model("GUI", UO_POPUP_FILE) if anims else None
        if model is None or uid not in self.stage:
            super().popup(when, uid, kind, amount, crit, guarded)
            return
        head = self.stage[uid].anchor("head")
        for anim in anims:
            if anim in model.puppet.anims:
                ms = int(model.length(anim) * 1000 / 60)
                self.fx.add(UoPopup(when, ms, head, anim, amount if anim.startswith("NUM_") else None))

    def _focus_camera(self, members, until: int) -> None:
        """Камера наезжает на участников: прямоугольник их ног и голов на экране."""
        projection = self.scene.projection()
        points = []
        for uid in members:
            place = self.stage.get(uid)
            if place is None:
                continue
            for y in (0.0, place.height + place.hover):
                lx, ly, _ = projection.project(place.x, y, place.z)
                points.append((lx, ly))
        if points:
            xs, ys = [p[0] for p in points], [p[1] for p in points]
            box = pygame.Rect(min(xs), min(ys), max(1, max(xs) - min(xs)), max(1, max(ys) - min(ys)))
            self.camera_view.focus(box.inflate(80, 40), until)

    def _context(self, source: int, target: int, targets: list[int]) -> Context:
        visual = self.visuals.get(source, ("melee", None, "slashing"))
        return {"self": source, "source": source, "target": target, "targets": targets,
                "element": visual[1], "visual": visual}

    def _cover(self, ev: Covered, when: int) -> None:
        """Прикрытие: защитник прыжком встаёт перед союзником, вокруг них купол щита."""
        stage = self.stage
        if ev.protector not in stage or ev.target not in stage:
            return
        guard, ward = stage[ev.protector], stage[ev.target]
        members, start, end = self.focus
        self.focus = (members | {ev.protector, ev.target}, min(start, when) if members else when, max(end, when + 1050))
        front_x = ward.x + ward.facing * 40
        self._move(ev.protector, Motion(when, 200, 500, 350, dx=front_x - guard.x, dz=ward.z - 4 - guard.z, lift=24, trail=True))
        if not self.sprite("shield_dome", when + 150, (front_x, ward.human * 0.45, ward.z - 4), 1.3, ward.facing, 800):
            self.fx.add(Dome(when + 150, 700, (front_x, 0.0, ward.z - 4), ELEMENT_COLORS["guard"], ward.human * 0.45))
        self.fx.add(FloatText(when, 900, ward.anchor("head"), self.t("cover").upper(), ELEMENT_COLORS["guard"], 20, 20))
        self._uo_effect("uo_guard", when + 200, (front_x, ward.human * 0.45, ward.z - 4), ward.facing)

    @staticmethod
    def _targets_of(view: Any, ev: SkillUsed) -> list[int]:
        """Кого задел навык: следующие события того же применения уже стоят в расписании."""
        timeline = view.timeline
        index = next((i for i, (_, e) in enumerate(timeline) if e is ev), None)
        targets: list[int] = []
        if index is not None:
            for _, e in timeline[index + 1:]:
                if isinstance(e, (SkillUsed, TurnStarted, TurnSkipped, RoundStarted)):
                    break
                if isinstance(e, (DamageDealt, Healed, AttackMissed)) and e.source == ev.user \
                        and e.cause == ev.skill_id and e.target not in targets:
                    targets.append(e.target)
        return targets or [ev.target]

    def run(self, steps: list[dict], base: int, context: Context, default_who: str) -> None:
        """Шаги визуала навыка: каждому юниту из who в момент base + at."""
        for step in steps:
            handler = self.steps.get(step.get("do", ""))
            if handler is None:
                continue
            who = step.get("who", default_who)
            uids = context["targets"] if who == "targets" else [context.get(who)]
            for uid in uids:
                if uid in self.stage:
                    handler(step, base + int(step.get("at", 0)), uid, context)

    # --- анимации юнитов (engine.uo_anim) ---

    def _parts(self, uid: int, state: str) -> list[dict]:
        place = self.stage.get(uid)
        return self.bank.parts(place.sprite, state) if place is not None else []

    def _animate(self, uid: int, state: str, when: int, hold: bool = False) -> int:
        """Сыграть состояние целиком (части подряд); hold — потом держать последний кадр.
        Возвращает длительность в мс (0, если у юнита нет такой анимации)."""
        parts = self._parts(uid, state)
        if not parts or uid in self.deaths:
            return 0
        clips, at = [], when
        for part in parts:
            clips.append(Clip(at, part))
            at += int(part["ms"])
        if hold:
            self.actions.play(uid, clips[:-1])
            self.actions.hold(uid, clips[-1])
        else:
            self.actions.play(uid, clips)
        return at - when

    def _animate_skill(self, uid: int, when: int, windup: int, delivery: str, skill_id: str = "") -> None:
        """Навык: своя анимация навыка класса, иначе атака или каст. С рывком к цели — бег, удар по
        прибытии, бег назад; на месте — части подряд (слишком длинные сжимаются)."""
        own, attack, cast = self._parts(uid, f"skill.{skill_id}"), self._parts(uid, "attack"), self._parts(uid, "skill")
        dash = max((m for m in self.motions.get(uid, ()) if m.start >= when and abs(m.dx) > 30),
                   key=lambda m: abs(m.dx), default=None)
        if own:
            if dash is not None:
                self.actions.play(uid, self._dash_clips(dash, own))
            else:
                clips, at = [], when
                for part in own:
                    ms = min(SKILL_PART_MAX_MS, int(part["ms"]))
                    clips.append(Clip(at, part, "stretch", ms))
                    at += ms
                self.actions.play(uid, clips)
            return
        if not attack and not cast:
            return
        magic = delivery in ("magic", "heal", "support")
        if dash is not None and attack:
            self.actions.play(uid, self._dash_clips(dash, attack))
        elif magic and cast:
            first = int(cast[0]["ms"])
            clips = [Clip(when, cast[0], "stretch", max(windup, round(first / CAST_SPEEDUP)))]
            at = clips[0].end
            if len(cast) > 1:
                clips.append(Clip(at, cast[1], "loop", CAST_LOOP_MS))
                at += CAST_LOOP_MS
            clips += [Clip(at, part) for part in cast[2:3]]
            self.actions.play(uid, clips)
        else:
            parts = attack or cast
            at, clips = when, []
            for part in parts[1:] if len(parts) >= 4 else parts:    # бег к цели на месте не нужен
                clips.append(Clip(at, part))
                at += int(part["ms"])
            self.actions.play(uid, clips[:3])

    @staticmethod
    def _dash_clips(dash: Motion, attack: list[dict]) -> list[Clip]:
        """Части атаки на фазы рывка: бег (go), удар (hold, удлиняется под удар), бег назад (back)."""
        run, strike, back, settle = (attack + [None] * 4)[:4] if len(attack) >= 3 else (
            (attack[0], attack[1], None, None) if len(attack) == 2 else (None, attack[0], None, None))
        clips = []
        if run is not None:
            clips.append(Clip(dash.start, run, "stretch", max(1, dash.go)))
        strike_ms = min(STRIKE_HOLD_MAX, int(strike["ms"]))
        dash.hold = max(dash.hold, strike_ms)                # возвращаться, когда удар доигран
        clips.append(Clip(dash.start + dash.go, strike, "stretch", strike_ms))
        if back is not None:
            clips.append(Clip(dash.start + dash.go + dash.hold, back, "stretch", max(1, dash.back)))
        if settle is not None:
            clips.append(Clip(dash.end, settle))
        return clips

    # --- шаги: движения (единицы мира) ---

    def _move(self, uid: int, motion: Motion) -> None:
        self.motions.setdefault(uid, []).append(motion)

    def _color(self, step: dict, context: Context, default: Any = "steel") -> tuple[int, int, int]:
        color = step.get("color", default)
        if color == "$element":
            color = context.get("element") or "steel"
        if isinstance(color, str):
            return ELEMENT_COLORS.get(color, (255, 255, 255))
        return tuple(color)

    @staticmethod
    def _ms(step: dict, default: int = 400) -> int:
        return int(step.get("ms", default))

    def _dash(self, step: dict, at: int, uid: int, context: Context) -> None:
        """К цели, остановка в gap перед ней со стороны противника (gap < 0 — насквозь)."""
        place, target = self.stage[uid], self.stage.get(context["target"], self.stage[uid])
        if uid == context["target"]:
            return
        front_x = target.x + target.facing * step.get("gap", 64)
        self._move(uid, Motion(at, self._ms(step), int(step.get("hold", 150)), int(step.get("back", 350)),
                               dx=front_x - place.x, dz=target.z - place.z, trail=step.get("trail", False)))

    def _hop(self, step: dict, at: int, uid: int, context: Context) -> None:
        """hop — шаг назад и обратно, lunge — вперёд."""
        place, ms = self.stage[uid], self._ms(step)
        sign = -1 if step.get("do") == "hop" else 1
        go = int(ms * 0.4)
        self._move(uid, Motion(at, go, int(step.get("hold", ms * 0.2)), ms - go, dx=sign * place.facing * step.get("dist", 14)))

    def _jump(self, step: dict, at: int, uid: int, context: Context) -> None:
        ms = self._ms(step)
        self._move(uid, Motion(at, ms // 2, 0, ms - ms // 2, lift=step.get("height", 24)))

    def _rise(self, step: dict, at: int, uid: int, context: Context) -> None:
        """Подъём в воздух, зависание и спуск."""
        ms = self._ms(step)
        go, hold = int(ms * 0.3), int(ms * 0.4)
        self._move(uid, Motion(at, go, hold, ms - go - hold, dy=step.get("height", 16)))

    def _tilt(self, step: dict, at: int, uid: int, context: Context) -> None:
        ms = self._ms(step)
        go = hold = int(ms * 0.3)
        self._move(uid, Motion(at, go, hold, ms - go - hold, angle=step.get("angle", -8) * self.stage[uid].facing))

    def _knockback(self, step: dict, at: int, uid: int, context: Context) -> None:
        """Отброс назад, к своему краю поля."""
        self._move(uid, Motion(at, 90, 70, 320, dx=-self.stage[uid].facing * step.get("dist", 14)))

    def _glow(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.tints.setdefault(uid, []).append(Tint(at, self._ms(step), self._color(step, context)))

    # --- шаги: эффекты (единицы мира) ---

    def _pos(self, step: dict, uid: int) -> World:
        return self.stage[uid].anchor(step.get("on", "body"))

    def _source(self, uid: int, context: Context) -> Place:
        return self.stage.get(context["source"], self.stage[uid])

    def _projectile(self, step: dict, at: int, uid: int, context: Context) -> None:
        source = self._source(uid, context)
        target = self.stage.get(context["target"], self.stage[uid])
        sx, sy, sz = source.anchor("body")
        start = (sx + 22 * source.facing, sy + 6, sz)
        end = (start[0] + 50 * source.facing, SKY_HEIGHT * 0.5, sz) if step.get("to") == "sky" else target.anchor("body")
        size = 0.6 if step.get("small") else 1.7 if step.get("big") else 1.0
        if step.get("sprite") in self.sprites:      # снаряд-картинка из assets/fx
            self.fx.add(SpriteProjectile(at, self._ms(step), self.sprites, step["sprite"], start, end,
                                         step.get("arc", 0), step.get("scale", 0.5)))
            return
        self.fx.add(Projectile(at, self._ms(step), start, end, step.get("kind", "orb"), self._color(step, context),
                               step.get("arc", 0), size))

    def _slash(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.fx.add(Slash(at, self._ms(step, 320), self._pos(step, uid), self._color(step, context),
                          step.get("radius", 48), self._source(uid, context).facing))

    def _thrust(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.fx.add(Thrust(at, self._ms(step, 280), self._pos(step, uid), self._color(step, context),
                           self._source(uid, context).facing))

    def _ring(self, step: dict, at: int, uid: int, context: Context) -> None:
        """На земле (on: feet) — под юнитом; на высоте — обвивает юнита."""
        self.fx.add(Ring(at, self._ms(step), self._pos(step, uid), self._color(step, context), step.get("from", 10),
                         step.get("to", 60), step.get("thickness", 4)))

    def _wrap(self, step: dict, at: int, uid: int, context: Context) -> None:
        """Кольца поднимаются вокруг юнита, обвивая его спереди и сзади."""
        place = self.stage[uid]
        self.fx.add(WrapRing(at, self._ms(step, 800), place.anchor("feet"), self._color(step, context, "heal"),
                             step.get("radius", place.human * 0.25), step.get("height", place.height * 0.9),
                             int(step.get("rings", 3))))

    def _beam(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.fx.add(Beam(at, self._ms(step), self.stage[uid].anchor("feet"), self._color(step, context),
                         step.get("thickness", 34)))

    def _bolt(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.fx.add(Bolt(at, self._ms(step, 300), self._pos(step, uid), self._color(step, context), seed=at,
                         lean=20 * self._source(uid, context).facing))

    def _burst(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.fx.burst(at, self._pos(step, uid), self._color(step, context), int(step.get("count", 18)),
                      step.get("speed", 3.0), int(step.get("life", 650)), step.get("size", 3.0),
                      step.get("gravity", 0.05), step.get("shape", "glow"), step.get("up", 0.0))

    def _sparkle(self, step: dict, at: int, uid: int, context: Context) -> None:
        """Искры поднимаются вокруг юнита."""
        place = self.stage[uid]
        self.fx.rise(at, place.anchor("feet"), place.human * 0.2, place.height, self._color(step, context),
                     int(step.get("count", 16)), step.get("shape", "glow"), 1.5, 900, 3)

    def _flash(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.fx.add(Flash(at, self._ms(step), self._color(step, context), step.get("power", 0.3)))

    def _shake(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.fx.shake(at, self._ms(step), step.get("power", 5))

    def _runes(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.fx.add(RuneCircle(at, self._ms(step), self.stage[uid].anchor("feet"), self._color(step, context),
                               step.get("radius", 40)))

    def _pillars(self, step: dict, at: int, uid: int, context: Context) -> None:
        """Столбы по кругу вокруг цели: дальние за ней, ближние перед ней."""
        place = self.stage[uid]
        count = int(step.get("count", 3))
        radius = step.get("radius", 26) * 1.6
        for i in range(count):
            a = 0.4 + i * math.tau / count
            base = (place.x + math.cos(a) * radius, 0.0, place.z + math.sin(a) * radius * 0.8)
            self.fx.add(Pillar(at + i * 70, self._ms(step), base, self._color(step, context),
                               step.get("height", 120), step.get("thickness", 28), seed=at + i))

    def _arrow_rain(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.fx.add(ArrowRain(at, self._ms(step), self.stage[uid].anchor("feet"), self._color(step, context, [255, 240, 200]),
                              int(step.get("count", 10)), 34, self._source(uid, context).facing, seed=at + uid))

    def _glint(self, step: dict, at: int, uid: int, context: Context) -> None:
        place = self.stage[uid]
        x, y, z = self._pos(step, uid)
        self.fx.add(Glint(at, self._ms(step), (x + 16 * place.facing, y, z), self._color(step, context, [255, 250, 220]),
                          step.get("size", 22)))

    def _dome(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.fx.add(Dome(at, self._ms(step), self.stage[uid].anchor("feet"), self._color(step, context, "guard"),
                         step.get("radius", 50)))

    def _weapon(self, step: dict, at: int, uid: int, context: Context) -> None:
        """Оружие юнита (по предмету или слоту класса) появляется и бьёт цель."""
        source = self._source(uid, context)
        target = self.stage.get(context["target"], source)
        units = self.view.sim.units if self.view is not None else {}
        kind = step.get("kind") or weapon_kind(units.get(context["source"]), context["visual"][0])
        self.fx.add(WeaponStrike(at, self._ms(step, 600), kind, source.anchor("body"), target.anchor("body"), source.facing))

    def _sprite_step(self, step: dict, at: int, uid: int, context: Context) -> None:
        """Спрайтовый эффект из assets/fx на юните: тело, голова или ноги (лежащие — на земле)."""
        name = step.get("fx", "")
        if name not in self.sprites:
            return
        place = self.stage[uid]
        x, y, z = self._pos(step, uid)
        if self.sprites.spec(name).get("layer") == "ground" or self.sprites.spec(name).get("uo_anim")                 and self.sprites.spec(name).get("anchor") == "feet":
            y = 0.0
        ms = self.sprites.duration(name, self._ms(step, 500))
        self.fx.add(SpriteEffect(at, ms, self.sprites, name, (x + step.get("dx", 0) * place.facing, y + step.get("dy", 0), z),
                                 step.get("scale", 1.0), self._source(uid, context).facing))

    def _sprite_beam(self, step: dict, at: int, uid: int, context: Context) -> None:
        """Картинка, растянутая от источника до юнита (цепная молния)."""
        name = step.get("fx", "")
        if name in self.sprites:
            self.fx.add(SpriteBeam(at, self._ms(step, 400), self.sprites, name, self._source(uid, context).anchor("body"),
                                   self.stage[uid].anchor("body"), step.get("thickness", 60)))

    def _impact(self, step: dict, at: int, uid: int, context: Context) -> None:
        """Общий эффект удара по виду навыка и стихии."""
        self.impact(at, self._pos(step, uid), context["visual"], self._source(uid, context).facing)

    def _uo_fx(self, skill_id: str) -> Optional[dict[str, list[str]]]:
        """Эффекты навыка из Unicorn Overlord, если хоть один собран (иначе визуал проекта)."""
        fx = self.skill_fx.get(skill_id)
        if fx and any(name in self.sprites for name in fx["cast"] + fx["hit"]):
            return fx
        return None

    def _steps(self, steps: list[dict], skill_id: str) -> list[dict]:
        """Шаги визуала навыка: у навыка с эффектами из игры остаются только движения."""
        return [s for s in steps if s.get("do") in UO_MOTION_STEPS] if self._uo_fx(skill_id) else steps

    def _uo_skill_fx(self, skill_id: str, kind: str, when: int, uid: int) -> None:
        """Эффекты навыка (cast — на применившем, hit — на цели) друг за другом."""
        fx = self._uo_fx(skill_id)
        if not fx or uid not in self.stage:
            return
        place = self.stage[uid]
        for name in fx[kind]:
            if self._uo_effect(name, when, place.anchor("body"), place.facing):
                when += self.sprites.duration(name)

    def _uo_effect(self, name: str, when: int, pos: World, facing: int) -> bool:
        """Эффект из assets/uo_anim/fx в точке pos (лежащий на земле — у ног); False, если его нет."""
        if name not in self.sprites:
            return False
        if self.sprites.spec(name).get("anchor") == "feet":
            pos = (pos[0], 0.0, pos[2])
        self.fx.add(SpriteEffect(when, self.sprites.duration(name), self.sprites, name, pos, 1.0, facing))
        self.fx_until = max(self.fx_until, when + self.sprites.duration(name))
        return True

    def preload(self, class_ids) -> None:
        """Заранее загрузить куклы бойцов, эффектов и интерфейса UO: иначе первая загрузка (до секунды)
        случается посреди боя и картинка встаёт."""
        if not (UO_ANIM_ENABLED and uo_ui.source().ok):
            return
        src = uo_ui.source()
        for cid in set(class_ids):
            if self.bank.animated(self.bank.sprite_for(cid) or ""):
                src.class_model(cid)
        if self.sprites is not None and self.sprites.live is not None:
            self.sprites.live.model()
        for file in (UO_POPUP_FILE, UO_BANNER_FILE):
            src.model("GUI", file)

    def busy_until(self) -> int:
        """Когда доиграет всё запущенное на сцене: анимации бойцов, движения, эффекты навыков.
        Следующий ход и итог боя ждут этого момента, чтобы ничего не начиналось поверх."""
        until = self.fx_until
        for clips in self.actions.clips.values():
            for clip in clips:
                end = clip.end
                if end is not None:
                    until = max(until, end)
        for motions in self.motions.values():
            for motion in motions:
                until = max(until, motion.end)
        return until

    # --- положение в кадре ---

    def offset(self, uid: int, now: int) -> tuple[float, float, float, float]:
        """Сумма движений юнита: (dx, высота, dz, угол); летающие ещё и парят."""
        dx = dy = dz = angle = 0.0
        for motion in self.motions.get(uid, ()):
            value = motion.at(now)
            if value is not None:
                dx, dy, dz, angle = dx + value[0], dy + value[1], dz + value[2], angle + value[3]
        place = self.stage.get(uid)
        if place is not None and place.hover and uid not in self.dead:
            dy += place.hover + 5 * math.sin(now / 320 + uid)
        return dx, dy, dz, angle

    def world_at(self, uid: int, now: int) -> tuple[World, float]:
        """(точка ног юнита в мире с учётом движений, угол наклона)."""
        place = self.stage[uid]
        dx, dy, dz, angle = self.offset(uid, now)
        return (place.x + dx, dy, place.z + dz), angle

    def death_progress(self, uid: int, now: int) -> float:
        """0 жив, 0..1 падает и тает, 1 исчез (анимированный сначала доигрывает смерть)."""
        if uid not in self.dead:
            return 0.0
        died = self.deaths.get(uid)
        return 1.0 if died is None else min(1.0, max(0.0, (now - died) / DEATH_MS))

    # --- отрисовка ---

    def set_scene(self, scene: SceneConfig) -> None:
        """Другая сцена: расстановка пересчитается в следующем кадре."""
        self.scene = scene

    def gl_frame(self) -> Optional[GLFrame]:
        """Кадр видеокарты для поля или None (выключено, нет видеокарты)."""
        if not GL_FIELD:
            return None
        if self._frame is None:
            gl = GLRenderer.get()
            if gl is None:
                return None
            self._frame = GLFrame(gl)
        return self._frame

    def render_gl(self, size: tuple[int, int], now: int, cam: Camera) -> Optional[GLFrame]:
        """Поле в кадр видеокарты размера size (пиксели окна; поле — в cam.clip). Без вывода:
        окно OpenGL кладёт его на экран (GLFrame.present), остальные читают в картинку (draw_field)."""
        frame = self.gl_frame()
        if frame is None:
            return None
        frame.begin(size, cam.clip)
        cam = cam.shifted(*self.fx.screen_offset(now))
        quality = cam.scale / max(1.0, self.camera_view.zoom) * FOCUS_ZOOM
        self.backdrop.draw_gl(frame, self.scene, cam, quality)
        view = View(self.scene.projection(), cam, now)
        draw_parts_gl(frame, view, self._field_parts(view, now))
        for banner in self._live_banners(now):
            banner.draw(frame, cam.clip or pygame.Rect(0, 0, *size), now)
        frame.end()
        return frame

    def _field_parts(self, view: View, now: int) -> list[Part]:
        parts = self.prop_parts(view)
        if self.view is not None:
            for uid in list(self.motions):      # закончившиеся движения больше не нужны
                self.motions[uid] = [m for m in self.motions[uid] if m.end >= now]
            for uid in list(self.tints):
                self.tints[uid] = [t for t in self.tints[uid] if t.start + t.duration >= now]
            units = self.view.sim.units
            visible = [uid for uid in self.stage if self.death_progress(uid, now) < 1]
            self._update_alpha(visible, view)
            for uid in visible:
                parts.extend(self.unit_parts(units[uid], view))
            parts.extend(self.fx.parts(now))
        return parts

    def _live_banners(self, now: int) -> list[UoBanner]:
        self.banners = [b for b in self.banners if b.start + b.duration >= now]
        return [b for b in self.banners if b.start <= now]

    def draw_field(self, target: pygame.Surface, now: int, cam: Camera) -> None:
        if self.gl_frame() is not None:          # видеокартой, одно чтение кадра в картинку
            frame = self.render_gl(target.get_size(), now, cam)
            frame.read_into(target, cam.clip)
            return
        previous_clip = target.get_clip()
        target.set_clip(cam.clip)
        cam = cam.shifted(*self.fx.screen_offset(now))
        quality = cam.scale / max(1.0, self.camera_view.zoom) * FOCUS_ZOOM
        self.backdrop.draw(target, self.scene, cam, quality)
        view = View(self.scene.projection(), cam, now)
        draw_parts(target, view, self._field_parts(view, now))
        for banner in self._live_banners(now):
            banner.draw(target, cam.clip or target.get_rect(), now)
        target.set_clip(previous_clip)

    def prop_parts(self, view: View) -> list[Part]:
        """Стоящие объекты сцены (лежащие нарисованы в заднике)."""
        parts = []
        for i, obj in enumerate(self.scene.objects):
            if obj.layer == "upright":
                parts.append(Part(UPRIGHT, obj.z, lambda s, v, i=i, obj=obj: self._draw_prop(s, v, i, obj),
                                  gl=lambda f, v, i=i, obj=obj: self._draw_prop_gl(f, v, i, obj)))
        return parts

    def prop_rect(self, obj: SceneObject, view: View) -> Optional[pygame.Rect]:
        x, y, k = view.p((obj.x, obj.y, obj.z))
        image = self.props.image(obj.image)
        if image is None:
            return None
        h = max(2, round(obj.size * k))
        w = max(1, round(h * image.get_width() / image.get_height()))
        return pygame.Rect(x - w // 2, y - h, w, h)

    def _draw_prop(self, target: pygame.Surface, view: View, index: int, obj: SceneObject) -> None:
        k = view.p((obj.x, obj.y, obj.z))[2]
        if self.props.image(obj.image) is None:
            return
        sprite, _ = self.props.scaled(obj.image, max(2, round(obj.size * k / 2) * 2), obj.flip, placeholder)
        alpha = self.alpha.get(("prop", index), 255)
        if alpha < 254:
            sprite = sprite.copy()
            sprite.set_alpha(int(alpha))
        target.blit(sprite, sprite.get_rect(midbottom=view.xy((obj.x, obj.y, obj.z))))

    def _draw_prop_gl(self, frame: GLFrame, view: View, index: int, obj: SceneObject) -> None:
        image = self.props.image(obj.image)
        rect = self.prop_rect(obj, view)
        if image is None or rect is None:
            return
        tex = frame.keyed_texture(("prop", id(self.props), obj.image), lambda: image, mipmaps=True)
        frame.image(None, tuple(rect), alpha=self.alpha.get(("prop", index), 255) / 255, texture=tex, flip=obj.flip)

    def _sprite(self, uid: int, view: View, now: int, feet: World):
        """(картинка, белый силуэт, точка ног в картинке) юнита в момент now."""
        place = self.stage[uid]
        k = view.p(feet)[2]
        flip = place.side == "right"
        if self.bank.animated(place.sprite):
            pose = self.actions.pose(uid, now)
            frame = self.bank.pose(place.sprite, *pose, place.height * k, flip) if pose else \
                self.bank.idle_pose(place.sprite, now + uid * IDLE_DESYNC_MS, place.height * k, flip)
            if frame is not None:
                return frame
        breath = 1 + 0.012 * math.sin(now / 650 + uid * 1.7)      # еле заметное дыхание
        px_height = max(4, round(place.height * k * breath / 2) * 2)
        sprite, white = self.bank.unit_sprite(place.sprite, px_height, flip)
        return sprite, white, (sprite.get_width() / 2, sprite.get_height())

    @staticmethod
    def _placed(sprite: pygame.Surface, origin: tuple[float, float], point: tuple[float, float]) -> pygame.Rect:
        """Прямоугольник картинки, у которой точка origin стоит в point."""
        return sprite.get_rect(topleft=(round(point[0] - origin[0]), round(point[1] - origin[1])))

    def unit_rect(self, uid: int, view: View) -> pygame.Rect:
        feet, _ = self.world_at(uid, view.now)
        place = self.stage[uid]
        if self.gl_frame() is not None and self.bank.animated(place.sprite):    # по сетке куклы, без картинки
            cid = place.sprite[len(UO_PREFIX):]
            anims = self.bank.anims
            pose = self.actions.pose(uid, view.now) or anims.idle_at(cid, view.now + uid * IDLE_DESYNC_MS)
            found = anims.mesh(*pose) if pose else None
            if found is not None:
                scale = place.height * view.p(feet)[2] / max(1.0, anims.height_px(cid))
                ox, oy, w, h = found[0].frame_box(scale, place.side == "right")
                x, y = view.xy(feet)
                return pygame.Rect(round(x - ox), round(y - oy), w, h)
        sprite, _, origin = self._sprite(uid, view, view.now, feet)
        return self._placed(sprite, origin, view.xy(feet))

    def _update_alpha(self, visible: list[int], view: View) -> None:
        """Во время атаки всё, что стоит ближе атакующего или цели и закрывает их, становится прозрачным."""
        now = view.now
        members, start, end = self.focus
        active = [uid for uid in visible if uid in members] if start <= now <= end else []
        targets = [(self.world_at(uid, now)[0][2], self.unit_rect(uid, view)) for uid in active]
        step = min(1.0, max(0, now - self._last_draw) / FADE_MS) if self._last_draw else 1.0
        self._last_draw = now
        things: list[tuple[Any, float, Optional[pygame.Rect]]] = [
            (uid, self.world_at(uid, now)[0][2], self.unit_rect(uid, view)) for uid in visible if uid not in members]
        things += [(("prop", i), obj.z, self.prop_rect(obj, view)) for i, obj in enumerate(self.scene.objects)
                   if obj.layer == "upright"]
        for key, z, rect in things:
            covers = rect is not None and any(
                z < tz and rect.inflate(-rect.width // 4, -rect.height // 8).colliderect(trect) for tz, trect in targets)
            goal = SEE_THROUGH if covers else 255
            current = self.alpha.get(key, 255)
            self.alpha[key] = current + (goal - current) * step
        for uid in active:
            self.alpha[uid] = 255

    def unit_parts(self, unit: Unit, view: View) -> list[Part]:
        """Тень (земля), спрайт с послеобразами (стоящие) и плашка HP (надписи)."""
        uid = unit.uid
        feet, angle = self.world_at(uid, view.now)
        parts = [Part(GROUND, feet[2], lambda s, v: self._draw_ground(s, v, uid, feet),
                      gl=lambda f, v: self._draw_ground_gl(f, v, uid, feet)),
                 Part(UPRIGHT, feet[2], lambda s, v: self._draw_unit(s, v, uid, feet, angle),
                      gl=lambda f, v: self._draw_unit_gl(f, v, uid, feet, angle))]
        if uid not in self.dead:
            parts.append(Part(OVERLAY, 0, lambda s, v: self._draw_plate(s, v, unit), 1,
                              gl=lambda f, v: self._draw_plate(f, v, unit)))
        return parts

    def _draw_ground_gl(self, frame: GLFrame, view: View, uid: int, feet: World) -> None:
        """Тень и кольцо стороны — белыми заготовками, окрашенными видеокартой."""
        place = self.stage[uid]
        x, y, k = view.p((feet[0], 0.0, feet[2]))
        fade = 1 - self.death_progress(uid, view.now)
        shrink = 1 - min(0.5, feet[1] / (place.human * 0.5))
        width = place.shadow * k * shrink
        w, h = max(2.0, width), max(2.0, width * 0.22)
        frame.image(ground_art("shadow"), (x - w / 2, y - h / 2, w, h), alpha=110 / 255 * fade, mul=(0, 0, 0))
        if fade < 1:
            return
        color = CURRENT_RING if self.view is not None and uid == self.view.current_uid else SIDE_RING[place.side]
        rw, rh = w + 8, h + 6
        frame.image(ground_art("ring"), (x - rw / 2, y - rh / 2, rw, rh), additive=True,
                    mul=tuple(c / 255 for c in color))

    def _draw_unit_gl(self, frame: GLFrame, view: View, uid: int, feet: World, angle: float) -> None:
        """Юнит видеокартой: кукла UO рисуется сразу нужного размера (без кэша картинок), у спрайтов —
        их картинка; прозрачность, свечение, вспышка, поворот и послеобразы — при наложении."""
        place, now = self.stage[uid], view.now
        animated = self.bank.animated(place.sprite)
        shake, flash = self.fx.hit_reaction(uid, now)
        dying = self.death_progress(uid, now)
        alpha = self.alpha.get(uid, 255) * (1 - dying) / 255
        if dying > 0 and not animated:   # падает назад и тает (анимированный падает сам)
            angle += 70 * ease_out(dying) * place.facing
        point = view.xy((feet[0] + shake, feet[1], feet[2]))
        add = [0.0, 0.0, 0.0]
        for t in self.tints.get(uid, ()):
            k = t.strength(now)
            if k > 0.02:
                add = [a + c * k * 0.55 / 255 for a, c in zip(add, t.color)]
        ghosts = ()
        if any(m.trail and m.moving(now) for m in self.motions.get(uid, ())):
            ghosts = tuple((view.xy(self.world_at(uid, now - i * TRAIL_STEP_MS)[0]),
                            0.47 * (1 - i / (TRAIL_GHOSTS + 1)) * alpha) for i in range(TRAIL_GHOSTS, 0, -1))
        flip = place.side == "right"
        k = view.p(feet)[2]
        flash = 0.78 * flash if not angle else 0.0
        if animated:
            cid = place.sprite[len(UO_PREFIX):]
            anims = self.bank.anims
            pose = self.actions.pose(uid, now) or anims.idle_at(cid, now + uid * IDLE_DESYNC_MS)
            found = anims.mesh(*pose) if pose else None
            if found is not None:
                scale = place.height * k / max(1.0, anims.height_px(cid))
                frame.puppet(found[0], found[1], scale, flip, point, alpha, tuple(add), flash, angle, ghosts=ghosts)
                return
        breath = 1 + 0.012 * math.sin(now / 650 + uid * 1.7)      # еле заметное дыхание
        px_height = max(4, round(place.height * k * breath / 2) * 2)
        sprite, _ = self.bank.unit_sprite(place.sprite, px_height, flip)
        w, h = sprite.get_size()
        for (gx, gy), ghost_alpha in ghosts:
            frame.image(sprite, (gx - w / 2, gy - h, w, h), alpha=ghost_alpha, add=(70 / 255, 90 / 255, 140 / 255))
        frame.image(sprite, (point[0] - w / 2, point[1] - h, w, h), alpha=alpha, add=tuple(add), flash=flash,
                    angle=angle, pivot=point)

    def _draw_ground(self, target: pygame.Surface, view: View, uid: int, feet: World) -> None:
        """Тень под ногами (остаётся на земле при прыжке) и кольцо стороны; у ходящего кольцо жёлтое."""
        place = self.stage[uid]
        x, y, k = view.p((feet[0], 0.0, feet[2]))
        fade = 1 - self.death_progress(uid, view.now)
        shrink = 1 - min(0.5, feet[1] / (place.human * 0.5))
        width = place.shadow * k * shrink
        rect = pygame.Rect(0, 0, max(2, round(width)), max(2, round(width * 0.22)))
        rect.center = (x, y)
        shadow = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, int(110 * fade)), shadow.get_rect())
        target.blit(shadow, rect)
        if fade < 1:
            return
        color = CURRENT_RING if self.view is not None and uid == self.view.current_uid else SIDE_RING[place.side]
        ring = pygame.Surface(rect.inflate(8, 6).size)
        pygame.draw.ellipse(ring, color, ring.get_rect(), max(1, round(1.5 * k)))
        target.blit(ring, rect.inflate(8, 6), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_unit(self, target: pygame.Surface, view: View, uid: int, feet: World, angle: float) -> None:
        place, now = self.stage[uid], view.now
        sprite, white, origin = self._sprite(uid, view, now, feet)
        animated = self.bank.animated(place.sprite)
        shake, flash = self.fx.hit_reaction(uid, now)
        dying = self.death_progress(uid, now)
        alpha = self.alpha.get(uid, 255) * (1 - dying)
        if dying > 0 and not animated:   # падает назад и тает (анимированный падает сам)
            angle += 70 * ease_out(dying) * place.facing
        # Послеобразы рывка: тот же спрайт в недавних точках пути, всё прозрачнее.
        if any(m.trail and m.moving(now) for m in self.motions.get(uid, ())):
            ghost = sprite.copy()
            ghost.fill((70, 90, 140), special_flags=pygame.BLEND_RGB_ADD)
            for i in range(TRAIL_GHOSTS, 0, -1):
                past, _ = self.world_at(uid, now - i * TRAIL_STEP_MS)
                ghost.set_alpha(int(120 * (1 - i / (TRAIL_GHOSTS + 1)) * alpha / 255))
                target.blit(ghost, self._placed(ghost, origin, view.xy(past)))
        image = sprite
        tint = [(t.color, t.strength(now)) for t in self.tints.get(uid, ()) if t.strength(now) > 0.02]
        if tint:
            image = sprite.copy()
            for color, k in tint:
                image.fill(tuple(int(c * k * 0.55) for c in color), special_flags=pygame.BLEND_RGB_ADD)
        if alpha < 254:
            image = image.copy() if image is sprite else image
            image.set_alpha(int(alpha))
        point = view.xy((feet[0] + shake, feet[1], feet[2]))
        rect = self._placed(image, origin, point)
        if angle:   # поворот вокруг ног: ноги остаются на месте
            w, h = image.get_size()
            image = pygame.transform.rotate(image, angle)
            a = math.radians(angle)
            vx, vy = origin[0] - w / 2, origin[1] - h / 2
            rx, ry = vx * math.cos(a) + vy * math.sin(a), -vx * math.sin(a) + vy * math.cos(a)
            rect = image.get_rect(center=(round(point[0] - rx), round(point[1] - ry)))
        target.blit(image, rect)
        if flash > 0 and not angle:
            white = (white if white is not None else image).copy()     # у кукол UO силуэт делается здесь
            white.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
            white.set_alpha(int(200 * flash * alpha / 255))
            target.blit(white, rect)

    def _draw_plate(self, target: pygame.Surface, view: View, unit: Unit) -> None:
        """Под ногами: полоса HP, числа HP, AP и PP, ниже активные эффекты."""
        uid, place = unit.uid, self.stage[unit.uid]
        x, y, k = view.p((place.x, 0.0, place.z))
        hp, max_hp = self.hp.get(uid, unit.hp), max(1, unit.max_hp)
        if self.plate_drawer is not None:
            self.plate_drawer(target, unit, hp, (x, y), k)
            if self.view is not None and uid == self.view.current_uid:
                glow(target, view.xy(place.anchor("head")), (60, 50, 15), 30 * k, 1.0)
            return
        if isinstance(target, GLFrame):          # своя плашка рисуется pygame — на слой кадра
            target = target.legacy
        w = max(4, round(place.human * 0.3 * k))
        bar = pygame.Rect(x - w // 2, y + round(8 * k), w, max(2, round(5 * k)))
        pygame.draw.rect(target, (30, 20, 22), bar.inflate(2, 2))
        fill = bar.copy()
        fill.width = round(bar.width * max(0, hp) / max_hp)
        pygame.draw.rect(target, GREEN if hp * 3 > max_hp else RED, fill)
        font = fx_font(round(11 * k), True)
        text = f"{hp}   AP {unit.ap.current}  PP {unit.pp.current}"
        img, shade = font.render(text, True, (235, 235, 240)), font.render(text, True, (10, 10, 14))
        pos = img.get_rect(midtop=(bar.centerx, bar.bottom + max(1, round(k))))
        target.blit(shade, pos.move(1, 1))
        target.blit(img, pos)
        if unit.effects:
            names = ", ".join(self.t(e.definition.name) for e in unit.effects)
            line = fx_font(round(10 * k), False).render(names, True, (220, 190, 255))
            target.blit(line, line.get_rect(midtop=(bar.centerx, pos.bottom)))
        if self.view is not None and uid == self.view.current_uid:
            add_glow(target, view.xy(place.anchor("head")), (60, 50, 15), 30 * k, 1.0)
