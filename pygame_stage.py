"""Вкладка Stage: бой статичными спрайтами юнитов в сцене 2.5D, как в Unicorn Overlord.

Юниты стоят в трёхмерной сцене (engine.scene) и не анимируются покадрово: живость дают
движения в мире (рывок с послеобразами, прыжок, отскок, наклон, отбрасывание, подъём,
свечение) и трёхмерные эффекты (engine.fx). Рывок вглубь уменьшает спрайт, к зрителю —
увеличивает. Камера наезжает на атакующего и цели (engine.camera).

Что делает каждый навык, задаётся данными в assets/visuals/skills.json: шаги в момент
применения (cast) и на каждое попадание (hit). Навыки без описания берут общий визуал по виду.
Спрайты: assets/units/<id>.png, нарезанные tools/cut_lineup.py с одного листа.
"""
from __future__ import annotations

import json
import math
from collections import OrderedDict
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
)
from engine.projection import World
from engine.render import GROUND, OVERLAY, UPRIGHT, Part, View, draw_parts
from engine.scene import PROPS_DIR, SceneConfig, SceneObject
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
from pygame_battle import FIELD_RECT, BattleScreen, skill_visual, weapon_kind
from pygame_ui import GREEN, RED

ROOT = Path(__file__).resolve().parent
UNITS_DIR = ROOT / "assets" / "units"
VISUALS_PATH = ROOT / "assets" / "visuals" / "skills.json"

FOCUS_MS = 700             # сколько после удара участники атаки остаются в фокусе
SEE_THROUGH = 70           # непрозрачность того, кто закрывает участника атаки (из 255)
FADE_MS = 120              # скорость перехода прозрачности
DEFAULT_WINDUP = 380
DEATH_MS = 800
TRAIL_GHOSTS = 4           # послеобразов при рывке
TRAIL_STEP_MS = 28
SPRITE_CACHE = 300
FLYING_TAG = "flying"
TALL = 1.3                 # спрайт выше человека в столько раз — «большой» (всадник): тень шире
SIDE_RING = {"left": (60, 110, 220), "right": (220, 70, 60)}
CURRENT_RING = (230, 200, 80)
# Бои вкладки: демонстрация всех навыков и пассивок, пять тестовых классов, расстановка игрока.
MODES = ("demo", "showcase", "setup")
MODE_LABELS = {"demo": "demo battle (T)", "showcase": "test squads (T)", "setup": "your squads (T)"}


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


# --- картинки -----------------------------------------------------------------

class ImageBank:
    """Картинки папки и их масштабированные копии (с белым силуэтом для вспышки), с кэшем."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self._images: dict[str, Optional[pygame.Surface]] = {}
        self._scaled: OrderedDict = OrderedDict()

    def image(self, name: str) -> Optional[pygame.Surface]:
        if name not in self._images:
            path = self.folder / name
            image = None
            if name and path.is_file():
                image = pygame.image.load(str(path))
                if pygame.display.get_surface() is not None:
                    image = image.convert_alpha()
            self._images[name] = image
        return self._images[name]

    def scaled(self, name: str, px_height: int, flip: bool, fallback: Callable[[], pygame.Surface]):
        """(картинка, белый силуэт) нужной высоты в пикселях окна."""
        key = (name, px_height, flip)
        if key in self._scaled:
            self._scaled.move_to_end(key)
            return self._scaled[key]
        image = self.image(name) or fallback()
        k = px_height / image.get_height()
        sprite = pygame.transform.smoothscale(image, (max(1, round(image.get_width() * k)), max(1, px_height)))
        if flip:
            sprite = pygame.transform.flip(sprite, True, False)
        white = sprite.copy()
        white.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
        self._scaled[key] = (sprite, white)
        if len(self._scaled) > SPRITE_CACHE:
            self._scaled.popitem(last=False)
        return sprite, white


def placeholder() -> pygame.Surface:
    """Силуэт для картинки, которой нет: голова и плащ."""
    s = pygame.Surface((60, 150), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (150, 150, 165), (10, 30, 40, 120))
    pygame.draw.circle(s, (190, 180, 170), (30, 20), 16)
    return s


class SpriteBank(ImageBank):
    """Спрайты классов, их рост относительно человека и опорные точки (assets/units/units.json)."""

    def __init__(self, folder: Path = UNITS_DIR):
        super().__init__(folder)
        path = self.folder / "units.json"
        self.config: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    @property
    def sprites(self) -> dict[str, dict[str, Any]]:
        return self.config.get("sprites", {})

    def sprite_id(self, unit: Unit) -> Optional[str]:
        """Какой спрайт у юнита: свой, по классу из fallback, по тегу, по умолчанию."""
        sprites = self.sprites
        class_id = unit.definition.id
        if class_id in sprites:
            return class_id
        fallback = self.config.get("fallback", {})
        if fallback.get("classes", {}).get(class_id) in sprites:
            return fallback["classes"][class_id]
        for tag, sprite in fallback.get("tags", {}).items():
            if tag in unit.tags and sprite in sprites:
                return sprite
        default = fallback.get("default")
        return default if default in sprites else None

    def ratio(self, sprite_id: Optional[str]) -> float:
        """Высота спрайта в ростах человека (у всадника с копьём около 1.8)."""
        info = self.sprites.get(sprite_id or "")
        if not info:
            return 1.0
        human = self.config.get("sheets", {}).get(info.get("sheet"), {}).get("human_height") or info["height"]
        return info["height"] / human

    def anchor(self, sprite_id: Optional[str], on: str) -> Optional[float]:
        """Своя опорная точка спрайта (head, body) в долях его высоты от ног, если задана."""
        return self.sprites.get(sprite_id or "", {}).get("anchors", {}).get(on)

    def unit_sprite(self, sprite_id: Optional[str], px_height: int, flip: bool):
        return self.scaled(f"{sprite_id}.png" if sprite_id else "", px_height, flip, placeholder)


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

    @property
    def facing(self) -> int:
        return 1 if self.side == "left" else -1

    @property
    def tall(self) -> bool:
        return self.height > self.human * TALL

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


class StageScreen(BattleScreen):
    """Вкладка боя спрайтами. Свой бой: демонстрация, тестовые отряды или расстановка игрока (клавиша T)."""

    def __init__(self, scene: Optional[SceneConfig] = None, props_dir: Optional[Path] = None):
        super().__init__()
        self.scene = scene or SceneConfig()
        self.bank = SpriteBank()
        self.props = ImageBank(props_dir or PROPS_DIR)
        self.backdrop = Backdrop(FIELD_RECT, props_dir)
        self.skill_visuals = load_visuals()
        self.battle_view: Any = None        # свой BattleView; его создаёт окно
        self.mode = MODES[0]                # какой бой показывает вкладка (клавиша T)
        self.stage: dict[int, Place] = {}
        self.motions: dict[int, list[Motion]] = {}
        self.tints: dict[int, list[Tint]] = {}
        self.deaths: dict[int, int] = {}
        self.focus: tuple[frozenset, int, int] = (frozenset(), 0, 0)   # участники атаки, с, по
        self.alpha: dict[Any, float] = {}   # непрозрачность юнита (uid) или объекта (("prop", i))
        self._last_draw = 0
        # Шаги визуала навыков: имя -> обработчик (шаг, момент, юнит, контекст).
        self.steps: dict[str, Callable[[dict, int, int, Context], None]] = {
            "dash": self._dash, "hop": self._hop, "lunge": self._hop, "jump": self._jump, "rise": self._rise,
            "tilt": self._tilt, "knockback": self._knockback, "glow": self._glow,
            "projectile": self._projectile, "slash": self._slash, "thrust": self._thrust, "ring": self._ring,
            "wrap": self._wrap, "beam": self._beam, "bolt": self._bolt, "burst": self._burst, "sparkle": self._sparkle,
            "flash": self._flash, "shake": self._shake, "runes": self._runes, "pillars": self._pillars,
            "arrow_rain": self._arrow_rain, "glint": self._glint, "dome": self._dome, "weapon": self._weapon,
            "impact": self._impact,
        }

    # --- бой этой вкладки ---

    def scenario(self, db: Any, setup: Any) -> Any:
        if self.mode == "demo":
            return build_demo_battle(db)
        return build_showcase(db) if self.mode == "showcase" else clone_scenario(db, setup)

    def next_mode(self) -> None:
        """Следующий бой: демонстрация -> тестовые отряды -> ваша расстановка."""
        self.mode = MODES[(MODES.index(self.mode) + 1) % len(MODES)]
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

    def handle_event(self, event: pygame.event.Event, pos: tuple[float, float], window_scale: float = 1.0) -> None:
        super().handle_event(event, pos, window_scale)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_t:
            self.next_mode()

    # --- раскладка ---

    def place_for(self, unit: Unit, side: str, row: int, col: int, cols: int) -> Place:
        """Юнит в клетке формации -> место в мире по сцене."""
        scene = self.scene
        x, z = scene.cell(side, row, col, cols)
        sprite = self.bank.sprite_id(unit)
        human = scene.human_height
        return Place(x, z, side, sprite, human * self.bank.ratio(sprite), human, self.bank.anchor(sprite, "head"),
                     self.bank.anchor(sprite, "body"), scene.fly_height if FLYING_TAG in unit.tags else 0.0)

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
                self.fx.add(FloatText(when, 900, stage[ev.user].anchor("head"), self.t(skill.name) if skill else ev.skill_id,
                                      (255, 236, 170), 14, 18, False))
            spec = self.spec(unit, ev.skill_id)
            context = self._context(ev.user, ev.target, self._targets_of(view, ev))
            until = when + int(spec.get("windup", DEFAULT_WINDUP)) + FOCUS_MS
            self.focus = (frozenset([ev.user, *context["targets"]]), when, until)
            self._focus_camera(self.focus[0], until)
            self.run(spec.get("cast", []), when, context, "self")
        elif isinstance(ev, DamageDealt) and not self.is_periodic(ev, view.db):
            self.run(self.spec(units.get(ev.source), ev.cause).get("hit", []), when,
                     self._context(ev.source, ev.target, [ev.target]), "target")
        elif isinstance(ev, Healed) and ev.source is not None and ev.amount > 0:
            self.run(self.spec(units.get(ev.source), ev.cause).get("hit", []), when,
                     self._context(ev.source, ev.target, [ev.target]), "target")
        elif isinstance(ev, AttackMissed) and ev.target in stage:   # уклонение: короткий отскок назад
            self._move(ev.target, Motion(when, 90, 80, 260, dx=-stage[ev.target].facing * 22, lift=10))
        elif isinstance(ev, Covered):
            self._cover(ev, when)
        elif isinstance(ev, UnitDied):
            self.deaths[ev.unit] = when

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
        self.fx.add(Dome(when + 150, 700, (front_x, 0.0, ward.z - 4), ELEMENT_COLORS["guard"], ward.human * 0.45))
        self.fx.add(FloatText(when, 900, ward.anchor("head"), self.t("cover").upper(), ELEMENT_COLORS["guard"], 20, 20))

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

    def _impact(self, step: dict, at: int, uid: int, context: Context) -> None:
        """Общий эффект удара по виду навыка и стихии."""
        self.impact(at, self._pos(step, uid), context["visual"], self._source(uid, context).facing)

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
        """0 жив, 0..1 падает и тает, 1 исчез."""
        if uid not in self.dead:
            return 0.0
        died = self.deaths.get(uid)
        return 1.0 if died is None else min(1.0, max(0.0, (now - died) / DEATH_MS))

    # --- отрисовка ---

    def set_scene(self, scene: SceneConfig) -> None:
        """Другая сцена: расстановка пересчитается в следующем кадре."""
        self.scene = scene

    def draw_field(self, target: pygame.Surface, now: int, cam: Camera) -> None:
        previous_clip = target.get_clip()
        target.set_clip(cam.clip)
        cam = cam.shifted(*self.fx.screen_offset(now))
        quality = cam.scale / max(1.0, self.camera_view.zoom) * FOCUS_ZOOM
        self.backdrop.draw(target, self.scene, cam, quality)
        view = View(self.scene.projection(), cam, now)
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
        draw_parts(target, view, parts)
        target.set_clip(previous_clip)

    def prop_parts(self, view: View) -> list[Part]:
        """Стоящие объекты сцены (лежащие нарисованы в заднике)."""
        parts = []
        for i, obj in enumerate(self.scene.objects):
            if obj.layer == "upright":
                parts.append(Part(UPRIGHT, obj.z, lambda s, v, i=i, obj=obj: self._draw_prop(s, v, i, obj)))
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

    def _sprite(self, uid: int, view: View, now: int, feet: World):
        place = self.stage[uid]
        k = view.p(feet)[2]
        breath = 1 + 0.012 * math.sin(now / 650 + uid * 1.7)      # еле заметное дыхание
        px_height = max(4, round(place.height * k * breath / 2) * 2)
        return self.bank.unit_sprite(place.sprite, px_height, place.side == "right")

    def unit_rect(self, uid: int, view: View) -> pygame.Rect:
        feet, _ = self.world_at(uid, view.now)
        sprite, _ = self._sprite(uid, view, view.now, feet)
        return sprite.get_rect(midbottom=view.xy(feet))

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
        parts = [Part(GROUND, feet[2], lambda s, v: self._draw_ground(s, v, uid, feet)),
                 Part(UPRIGHT, feet[2], lambda s, v: self._draw_unit(s, v, uid, feet, angle))]
        if uid not in self.dead:
            parts.append(Part(OVERLAY, 0, lambda s, v: self._draw_plate(s, v, unit), 1))
        return parts

    def _draw_ground(self, target: pygame.Surface, view: View, uid: int, feet: World) -> None:
        """Тень под ногами (остаётся на земле при прыжке) и кольцо стороны; у ходящего кольцо жёлтое."""
        place = self.stage[uid]
        x, y, k = view.p((feet[0], 0.0, feet[2]))
        fade = 1 - self.death_progress(uid, view.now)
        shrink = 1 - min(0.5, feet[1] / (place.human * 0.5))
        width = place.human * (0.75 if place.tall else 0.45) * k * shrink
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
        sprite, white = self._sprite(uid, view, now, feet)
        shake, flash = self.fx.hit_reaction(uid, now)
        dying = self.death_progress(uid, now)
        alpha = self.alpha.get(uid, 255) * (1 - dying)
        if dying > 0:   # падает назад и тает
            angle += 70 * ease_out(dying) * place.facing
        # Послеобразы рывка: тот же спрайт в недавних точках пути, всё прозрачнее.
        if any(m.trail and m.moving(now) for m in self.motions.get(uid, ())):
            ghost = sprite.copy()
            ghost.fill((70, 90, 140), special_flags=pygame.BLEND_RGB_ADD)
            for i in range(TRAIL_GHOSTS, 0, -1):
                past, _ = self.world_at(uid, now - i * TRAIL_STEP_MS)
                ghost.set_alpha(int(120 * (1 - i / (TRAIL_GHOSTS + 1)) * alpha / 255))
                target.blit(ghost, ghost.get_rect(midbottom=view.xy(past)))
        image = sprite
        tint = [(t.color, t.strength(now)) for t in self.tints.get(uid, ()) if t.strength(now) > 0.02]
        if tint:
            image = sprite.copy()
            for color, k in tint:
                image.fill(tuple(int(c * k * 0.55) for c in color), special_flags=pygame.BLEND_RGB_ADD)
        if alpha < 254:
            image = image.copy() if image is sprite else image
            image.set_alpha(int(alpha))
        if angle:
            image = pygame.transform.rotate(image, angle)
        rect = image.get_rect(midbottom=view.xy((feet[0] + shake, feet[1], feet[2])))
        if angle:   # поворот вокруг ног: сдвиг, чтобы ноги остались на месте
            rect.centerx += round(math.sin(math.radians(angle)) * -sprite.get_height() * 0.3)
        target.blit(image, rect)
        if flash > 0 and not angle:
            white = white.copy()
            white.set_alpha(int(200 * flash * alpha / 255))
            target.blit(white, rect)

    def _draw_plate(self, target: pygame.Surface, view: View, unit: Unit) -> None:
        """Под ногами: полоса HP, числа HP, AP и PP, ниже активные эффекты."""
        uid, place = unit.uid, self.stage[unit.uid]
        x, y, k = view.p((place.x, 0.0, place.z))
        hp, max_hp = self.hp.get(uid, unit.hp), max(1, unit.max_hp)
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
