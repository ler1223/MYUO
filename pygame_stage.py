"""Вкладка Stage: бой статичными спрайтами юнитов, как в Unicorn Overlord.

Юниты не анимируются покадрово: живость дают движения спрайта (рывок с послеобразами,
прыжок, отскок, наклон, отбрасывание, подъём в воздух, свечение) и эффекты. Что делает
каждый навык, задаётся данными в assets/visuals/skills.json: шаги в момент применения
(cast) и на каждое попадание (hit). Навыки без описания берут общий визуал по виду.

Юниты стоят в трёхмерной сцене (pygame_scene.SceneConfig): клетка формации -> мировая
точка -> экран с перспективой. Спрайты: assets/units/<id>.png, нарезанные
tools/cut_lineup.py с одного листа, поэтому их размеры согласованы.
"""
from __future__ import annotations

import json
import math
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import pygame

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
from game.scenario import build_showcase
from game.unit import Unit
from pygame_battle import FIELD_RECT, FIELD_TOP, BattleScreen, skill_visual, weapon_kind
from pygame_fx import (
    ELEMENT_COLORS,
    ArrowRain,
    Beam,
    Bolt,
    Camera,
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
    add_glow,
    ease_out,
    fx_font,
)
from pygame_scene import BACKGROUND_DIR, SceneConfig
from pygame_ui import GREEN, RED

ROOT = Path(__file__).resolve().parent
UNITS_DIR = ROOT / "assets" / "units"
VISUALS_PATH = ROOT / "assets" / "visuals" / "skills.json"

FOCUS_MS = 700             # сколько после удара участники атаки остаются в фокусе
SEE_THROUGH = 70           # непрозрачность юнита, закрывающего участника атаки (из 255)
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


# --- движения спрайтов --------------------------------------------------------

@dataclass
class Motion:
    """Сдвиг спрайта: туда (go мс), держится (hold), обратно (back).

    dx, dy: смещение в логических пикселях; lift: высота дуги прыжка; angle: наклон в градусах.
    trail: рисовать послеобразы, пока спрайт движется.
    """

    start: int
    go: int
    hold: int
    back: int
    dx: float = 0.0
    dy: float = 0.0
    lift: float = 0.0
    angle: float = 0.0
    trail: bool = False

    @property
    def end(self) -> int:
        return self.start + self.go + self.hold + self.back

    def at(self, now: int) -> Optional[tuple[float, float, float, float]]:
        """(dx, dy, высота над землёй, угол) в момент now; None вне движения."""
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
        return self.dx * k, self.dy * k, self.lift * math.sin(math.pi * t / max(1, total)), self.angle * k

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


# --- спрайты ------------------------------------------------------------------

class SpriteBank:
    """Спрайты классов, их рост относительно человека и опорные точки (assets/units/units.json)."""

    def __init__(self, folder: Path = UNITS_DIR):
        self.folder = folder
        path = folder / "units.json"
        self.config: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self._images: dict[Optional[str], Optional[pygame.Surface]] = {}
        self._scaled: OrderedDict = OrderedDict()

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

    def image(self, sprite_id: Optional[str]) -> pygame.Surface:
        if sprite_id not in self._images:
            path = self.folder / f"{sprite_id}.png"
            image = None
            if sprite_id and path.exists():
                image = pygame.image.load(str(path))
                if pygame.display.get_surface() is not None:
                    image = image.convert_alpha()
            self._images[sprite_id] = image
        return self._images[sprite_id] or self._placeholder()

    def _placeholder(self) -> pygame.Surface:
        """Силуэт для класса без картинки: голова и плащ."""
        if self._images.get("") is None:
            s = pygame.Surface((60, 150), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (150, 150, 165), (10, 30, 40, 120))
            pygame.draw.circle(s, (190, 180, 170), (30, 20), 16)
            self._images[""] = s
        return self._images[""]

    def scaled(self, sprite_id: Optional[str], px_height: int, flip: bool) -> tuple[pygame.Surface, pygame.Surface]:
        """(спрайт, белый силуэт) нужной высоты в пикселях окна; повёрнут к противнику."""
        key = (sprite_id, px_height, flip)
        if key in self._scaled:
            self._scaled.move_to_end(key)
            return self._scaled[key]
        image = self.image(sprite_id)
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


def load_visuals(path: Path = VISUALS_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@dataclass
class Place:
    """Где стоит юнит: мировая точка, ноги на экране, масштаб глубины, сторона, спрайт и его рост."""

    world: tuple[float, float]       # (x, z) в сцене
    feet: tuple[float, float]        # логические пиксели поля
    scale: float
    side: str
    sprite: Optional[str]
    height: float                    # высота спрайта, логические пиксели
    human: float                     # рост человека на этой глубине
    head: Optional[float] = None     # свои опорные точки спрайта, доли высоты
    body: Optional[float] = None
    flying: bool = False

    @property
    def facing(self) -> int:
        return 1 if self.side == "left" else -1

    @property
    def tall(self) -> bool:
        return self.height > self.human * TALL

    def anchor(self, on: str) -> tuple[float, float]:
        x, y = self.feet
        if on == "feet":
            return x, y
        if on == "sky":
            return x, FIELD_TOP - 20
        if on == "head":
            return x, y - (self.height * self.head if self.head else self.human * 0.9)
        return x, y - (self.height * self.body if self.body else self.human * 0.5)


Context = dict[str, Any]


class StageScreen(BattleScreen):
    """Вкладка боя спрайтами. Свой бой: тестовые отряды (или расстановка игрока, клавиша T)."""

    def __init__(self, scene: Optional[SceneConfig] = None):
        super().__init__()
        self.scene = scene or SceneConfig.load()
        self.bank = SpriteBank()
        self.skill_visuals = load_visuals()
        self.battle_view: Any = None        # свой BattleView; его создаёт окно
        self.use_test = True                # тестовые отряды пяти классов, иначе расстановка игрока
        self.stage: dict[int, Place] = {}
        self.motions: dict[int, list[Motion]] = {}
        self.tints: dict[int, list[Tint]] = {}
        self.deaths: dict[int, int] = {}
        self.focus: tuple[frozenset, int, int] = (frozenset(), 0, 0)   # участники атаки, с, по
        self.alpha: dict[int, float] = {}   # текущая непрозрачность спрайта
        self._last_draw = 0
        self._background: tuple[Any, Optional[pygame.Surface]] = (None, None)
        self._background_images: dict[str, Optional[pygame.Surface]] = {}
        # Шаги визуала навыков: имя -> обработчик (шаг, момент, юнит, контекст).
        self.steps: dict[str, Callable[[dict, int, int, Context], None]] = {
            "dash": self._dash, "hop": self._hop, "lunge": self._hop, "jump": self._jump, "rise": self._rise,
            "tilt": self._tilt, "knockback": self._knockback, "glow": self._glow,
            "projectile": self._projectile, "slash": self._slash, "thrust": self._thrust, "ring": self._ring,
            "beam": self._beam, "bolt": self._bolt, "burst": self._burst, "sparkle": self._sparkle,
            "flash": self._flash, "shake": self._shake, "runes": self._runes, "pillars": self._pillars,
            "arrow_rain": self._arrow_rain, "glint": self._glint, "dome": self._dome, "weapon": self._weapon,
            "impact": self._impact,
        }

    # --- бой этой вкладки ---

    def scenario(self, db: Any, setup: Any) -> Any:
        return build_showcase(db) if self.use_test else clone_scenario(db, setup)

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
        return "   " + self.t("test squads (T)" if self.use_test else "your squads (T)")

    def handle_event(self, event: pygame.event.Event, pos: tuple[float, float], window_scale: float = 1.0) -> None:
        super().handle_event(event, pos, window_scale)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_t and self.battle_view is not None:
            self.use_test = not self.use_test
            self.battle_view.restart(self.battle_view.seed)

    # --- раскладка ---

    def place_for(self, unit: Unit, side: str, row: int, col: int, cols: int) -> Place:
        """Юнит в клетке формации -> место на поле по сцене."""
        scene = self.scene
        x, z = scene.cell(side, row, col, cols)
        sx, sy, k = scene.project(x, z)
        sprite = self.bank.sprite_id(unit)
        human = scene.human_height * k
        return Place((x, z), (sx, sy), k, side, sprite, human * self.bank.ratio(sprite), human,
                     self.bank.anchor(sprite, "head"), self.bank.anchor(sprite, "body"), FLYING_TAG in unit.tags)

    def layout(self, sim: Any) -> None:
        self.stage = {}
        for squad, side in ((sim.attacker, "left"), (sim.defender, "right")):
            formation = squad.formation
            for unit in formation.units:
                row, col = formation.position_of(unit.uid)
                self.stage[unit.uid] = self.place_for(unit, side, row, col, formation.cols)

    def point(self, uid: int, on: str = "body") -> tuple[float, float]:
        place = self.stage.get(uid)
        return place.anchor(on) if place else super().point(uid, on)

    def facing(self, uid: int) -> int:
        place = self.stage.get(uid)
        return place.facing if place else 1

    def reset(self) -> None:
        super().reset()
        self.motions.clear()
        self.tints.clear()
        self.deaths.clear()
        self.alpha.clear()
        self.focus = (frozenset(), 0, 0)

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
                head = stage[ev.user].anchor("head")
                self.fx.add(FloatText(when, 900, (head[0], head[1] - 14), self.t(skill.name) if skill else ev.skill_id,
                                      (255, 236, 170), 14, 18, False))
            spec = self.spec(unit, ev.skill_id)
            context = self._context(ev.user, ev.target, self._targets_of(view, ev))
            windup = int(spec.get("windup", DEFAULT_WINDUP))
            self.focus = (frozenset([ev.user, *context["targets"]]), when, when + windup + FOCUS_MS)
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

    def _context(self, source: int, target: int, targets: list[int]) -> Context:
        visual = self.visuals.get(source, ("melee", None, "slashing"))
        return {"self": source, "source": source, "target": target, "targets": targets,
                "element": visual[1], "visual": visual}

    def _cover(self, ev: Covered, when: int) -> None:
        """Прикрытие: защитник прыжком встаёт перед союзником, перед ним купол щита."""
        stage = self.stage
        if ev.protector not in stage or ev.target not in stage:
            return
        guard, ward = stage[ev.protector], stage[ev.target]
        f = ward.facing
        members, start, end = self.focus
        self.focus = (members | {ev.protector, ev.target}, min(start, when) if members else when, max(end, when + 1050))
        dx = ward.feet[0] + f * 40 * ward.scale - guard.feet[0]
        dy = ward.feet[1] + 4 - guard.feet[1]
        self._move(ev.protector, Motion(when, 200, 500, 350, dx=dx, dy=dy, lift=24, trail=True))
        front = (ward.feet[0] + f * 60 * ward.scale, ward.anchor("body")[1])
        self.fx.add(Dome(when + 150, 700, front, ELEMENT_COLORS["guard"], 56 * ward.scale))
        self.fx.add(FloatText(when, 900, (front[0], front[1] - 70), self.t("cover").upper(), ELEMENT_COLORS["guard"], 20, 20))

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

    # --- шаги: движения ---

    def _move(self, uid: int, motion: Motion) -> None:
        self.motions.setdefault(uid, []).append(motion)

    def _color(self, step: dict, context: Context, default: Any = "steel") -> tuple[int, int, int]:
        color = step.get("color", default)
        if color == "$element":
            color = context.get("element") or "steel"
        if isinstance(color, str):
            return ELEMENT_COLORS.get(color, (255, 255, 255))
        return tuple(color)

    def _ms(self, step: dict, default: int = 400) -> int:
        return int(step.get("ms", default))

    def _dash(self, step: dict, at: int, uid: int, context: Context) -> None:
        """К цели, остановка в gap перед ней со стороны противника (gap < 0 — насквозь)."""
        place, target = self.stage[uid], self.stage.get(context["target"], self.stage[uid])
        if uid == context["target"]:
            return
        gap = step.get("gap", 64) * target.scale
        dx = target.feet[0] + target.facing * gap - place.feet[0]
        dy = target.feet[1] - place.feet[1]
        self._move(uid, Motion(at, self._ms(step), int(step.get("hold", 150)), int(step.get("back", 350)),
                               dx=dx, dy=dy, trail=step.get("trail", False)))

    def _hop(self, step: dict, at: int, uid: int, context: Context) -> None:
        """hop — шаг назад и обратно, lunge — вперёд."""
        place, ms = self.stage[uid], self._ms(step)
        sign = -1 if step.get("do") == "hop" else 1
        go = int(ms * 0.4)
        self._move(uid, Motion(at, go, int(step.get("hold", ms * 0.2)), ms - go,
                               dx=sign * place.facing * step.get("dist", 14) * place.scale))

    def _jump(self, step: dict, at: int, uid: int, context: Context) -> None:
        ms = self._ms(step)
        self._move(uid, Motion(at, ms // 2, 0, ms - ms // 2, lift=step.get("height", 24) * self.stage[uid].scale))

    def _rise(self, step: dict, at: int, uid: int, context: Context) -> None:
        """Подъём в воздух, зависание и спуск."""
        ms = self._ms(step)
        go, hold = int(ms * 0.3), int(ms * 0.4)
        self._move(uid, Motion(at, go, hold, ms - go - hold, dy=-step.get("height", 16) * self.stage[uid].scale))

    def _tilt(self, step: dict, at: int, uid: int, context: Context) -> None:
        ms = self._ms(step)
        go = hold = int(ms * 0.3)
        self._move(uid, Motion(at, go, hold, ms - go - hold, angle=step.get("angle", -8) * self.stage[uid].facing))

    def _knockback(self, step: dict, at: int, uid: int, context: Context) -> None:
        """Отброс назад, к своему краю поля."""
        place = self.stage[uid]
        self._move(uid, Motion(at, 90, 70, 320, dx=-place.facing * step.get("dist", 14) * place.scale))

    def _glow(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.tints.setdefault(uid, []).append(Tint(at, self._ms(step), self._color(step, context)))

    # --- шаги: эффекты ---

    def _pos(self, step: dict, uid: int) -> tuple[float, float]:
        return self.stage[uid].anchor(step.get("on", "body"))

    def _source(self, uid: int, context: Context) -> Place:
        return self.stage.get(context["source"], self.stage[uid])

    def _projectile(self, step: dict, at: int, uid: int, context: Context) -> None:
        source = self._source(uid, context)
        target = self.stage.get(context["target"], self.stage[uid])
        start = source.anchor("body")
        start = (start[0] + 22 * source.facing * source.scale, start[1] - 6)
        end = (start[0] + 50 * source.facing, FIELD_TOP - 30) if step.get("to") == "sky" else target.anchor("body")
        size = 0.6 if step.get("small") else 1.7 if step.get("big") else 1.0
        self.fx.add(Projectile(at, self._ms(step), start, end, step.get("kind", "orb"), self._color(step, context),
                               step.get("arc", 0) * source.scale, size))

    def _slash(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.fx.add(Slash(at, self._ms(step, 320), self._pos(step, uid), self._color(step, context),
                          step.get("radius", 48) * self.stage[uid].scale, self._source(uid, context).facing))

    def _thrust(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.fx.add(Thrust(at, self._ms(step, 280), self._pos(step, uid), self._color(step, context),
                           self._source(uid, context).facing))

    def _ring(self, step: dict, at: int, uid: int, context: Context) -> None:
        k = self.stage[uid].scale
        self.fx.add(Ring(at, self._ms(step), self._pos(step, uid), self._color(step, context), step.get("from", 10) * k,
                         step.get("to", 60) * k, int(step.get("thickness", 4)), 0.35 if step.get("on") == "feet" else 0.6))

    def _beam(self, step: dict, at: int, uid: int, context: Context) -> None:
        place = self.stage[uid]
        self.fx.add(Beam(at, self._ms(step), place.anchor("feet"), self._color(step, context),
                         int(step.get("thickness", 34) * place.scale)))

    def _bolt(self, step: dict, at: int, uid: int, context: Context) -> None:
        pos = self._pos(step, uid)
        self.fx.add(Bolt(at, self._ms(step, 300), (pos[0] + 20 * self._source(uid, context).facing, FIELD_TOP - 10), pos,
                         self._color(step, context), seed=at))

    def _burst(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.fx.burst(at, self._pos(step, uid), self._color(step, context), int(step.get("count", 18)),
                      step.get("speed", 3.0), int(step.get("life", 650)), step.get("size", 3.0),
                      step.get("gravity", 0.05), step.get("shape", "glow"), step.get("up", 0.0))

    def _sparkle(self, step: dict, at: int, uid: int, context: Context) -> None:
        """Искры поднимаются от тела."""
        place = self.stage[uid]
        rect = pygame.Rect(0, 0, int(place.human * 0.35), int(place.human))
        rect.midbottom = (int(place.feet[0]), int(place.feet[1]))
        self.fx.rise(at, rect, self._color(step, context), int(step.get("count", 16)), step.get("shape", "glow"), 1.5, 900, 3)

    def _flash(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.fx.add(Flash(at, self._ms(step), self._color(step, context), step.get("power", 0.3)))

    def _shake(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.fx.shake(at, self._ms(step), step.get("power", 5))

    def _runes(self, step: dict, at: int, uid: int, context: Context) -> None:
        place = self.stage[uid]
        self.fx.add(RuneCircle(at, self._ms(step), place.anchor("feet"), self._color(step, context),
                               step.get("radius", 40) * place.scale))

    def _pillars(self, step: dict, at: int, uid: int, context: Context) -> None:
        """Столбы вокруг цели: в центре и по сторонам."""
        place = self.stage[uid]
        count, k = int(step.get("count", 3)), place.scale
        radius = step.get("radius", 26) * k
        x, y = place.feet
        for i in range(count):
            a = (i - (count - 1) / 2) * 1.2
            base = (x + math.sin(a) * radius * 1.4, y + math.cos(a) * radius * 0.25 - (0 if i == count // 2 else 6))
            self.fx.add(Pillar(at + abs(i - count // 2) * 70, self._ms(step), base, self._color(step, context),
                               step.get("height", 120) * k, step.get("thickness", 28) * k, seed=at + i))

    def _arrow_rain(self, step: dict, at: int, uid: int, context: Context) -> None:
        place = self.stage[uid]
        self.fx.add(ArrowRain(at, self._ms(step), place.anchor("feet"), self._color(step, context, [255, 240, 200]),
                              int(step.get("count", 10)), 34 * place.scale, self._source(uid, context).facing, seed=at + uid))

    def _glint(self, step: dict, at: int, uid: int, context: Context) -> None:
        place, pos = self.stage[uid], self._pos(step, uid)
        self.fx.add(Glint(at, self._ms(step), (pos[0] + 16 * place.facing * place.scale, pos[1]),
                          self._color(step, context, [255, 250, 220]), step.get("size", 22) * place.scale))

    def _dome(self, step: dict, at: int, uid: int, context: Context) -> None:
        self.fx.add(Dome(at, self._ms(step), self._pos(step, uid), self._color(step, context, "guard"),
                         step.get("radius", 50) * self.stage[uid].scale))

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

    # --- отрисовка ---

    def offset(self, uid: int, now: int) -> tuple[float, float, float, float]:
        """Сумма движений юнита: (dx, dy, высота над землёй, угол); летающие ещё и парят."""
        dx = dy = lift = angle = 0.0
        for motion in self.motions.get(uid, ()):
            value = motion.at(now)
            if value is not None:
                dx, dy, lift, angle = dx + value[0], dy + value[1], lift + value[2], angle + value[3]
        place = self.stage.get(uid)
        if place is not None and place.flying and uid not in self.dead:
            lift += (self.scene.fly_height + 5 * math.sin(now / 320 + uid)) * place.scale
        return dx, dy, lift, angle

    def draw_field(self, target: pygame.Surface, now: int, cam: Camera) -> None:
        view = self.view
        if view is None:
            return
        for uid in list(self.motions):      # закончившиеся движения больше не нужны
            self.motions[uid] = [m for m in self.motions[uid] if m.end >= now]
        for uid in list(self.tints):
            self.tints[uid] = [t for t in self.tints[uid] if t.start + t.duration >= now]
        previous_clip = target.get_clip()
        target.set_clip(cam.clip)
        shake = self.fx.screen_offset(now)
        cam = Camera(cam.scale, (cam.origin[0] - shake[0], cam.origin[1] - shake[1]), cam.offset, cam.clip)
        self.draw_background(target, cam)
        units = view.sim.units
        visible = [uid for uid in self.stage if self.death_progress(uid, now) < 1]
        for uid in visible:
            self._draw_ground(target, uid, now, cam)
        # Дальние раньше ближних; кто сейчас в движении — поверх стоящих на той же линии.
        order = sorted(visible, key=lambda uid: (self.stage[uid].feet[1] + self.offset(uid, now)[1]
                                                 + (30 if self.motions.get(uid) else 0)))
        self._update_alpha(order, now, cam)
        for uid in order:
            self._draw_unit(target, units[uid], now, cam)
        for uid in order:
            self._draw_plate(target, units[uid], cam)
        self.fx.draw(target, now, cam)
        target.set_clip(previous_clip)

    def draw_background(self, target: pygame.Surface, cam: Camera) -> None:
        """Фон сцены: картинка из assets/backgrounds (заполняет поле, движется с зумом) или градиент."""
        scene = self.scene
        size = (max(1, round(cam.s(FIELD_RECT.width))), max(1, round(cam.s(FIELD_RECT.height))))
        key = (size, scene.background, scene.darken, tuple(scene.sky), tuple(scene.earth))
        if self._background[0] != key:
            self._background = (key, self._render_background(size))
        target.blit(self._background[1], cam.p(*FIELD_RECT.topleft))

    def _render_background(self, size: tuple[int, int]) -> pygame.Surface:
        scene = self.scene
        bg = pygame.Surface(size)
        image = self._background_image(scene.background)
        if image is not None:
            k = max(size[0] / image.get_width(), size[1] / image.get_height())
            scaled = pygame.transform.smoothscale(image, (int(image.get_width() * k) + 1, int(image.get_height() * k) + 1))
            bg.blit(scaled, (0, 0), pygame.Rect((scaled.get_width() - size[0]) // 2, (scaled.get_height() - size[1]) // 2, *size))
        else:
            for y in range(size[1]):
                k = y / size[1]
                color = tuple(int(a + (b - a) * k) for a, b in zip(scene.sky, scene.earth))
                pygame.draw.line(bg, color, (0, y), (size[0], y))
        if scene.darken > 0:
            shade = pygame.Surface(size, pygame.SRCALPHA)
            shade.fill((0, 0, 0, int(255 * scene.darken / 100)))
            bg.blit(shade, (0, 0))
        return bg

    def _background_image(self, name: str) -> Optional[pygame.Surface]:
        if name not in self._background_images:
            path = BACKGROUND_DIR / name
            self._background_images[name] = pygame.image.load(str(path)) if name and path.is_file() else None
        return self._background_images[name]

    def death_progress(self, uid: int, now: int) -> float:
        """0 жив, 0..1 падает и тает, 1 исчез."""
        if uid not in self.dead:
            return 0.0
        died = self.deaths.get(uid)
        return 1.0 if died is None else min(1.0, max(0.0, (now - died) / DEATH_MS))

    def _draw_ground(self, target: pygame.Surface, uid: int, now: int, cam: Camera) -> None:
        """Тень под ногами и цветное кольцо стороны; у ходящего юнита кольцо жёлтое."""
        place = self.stage[uid]
        dx, dy, lift, _ = self.offset(uid, now)
        fade = 1 - self.death_progress(uid, now)
        width = place.human * (0.75 if place.tall else 0.45)
        x, y = cam.p(place.feet[0] + dx, place.feet[1] + max(0.0, dy) + 2)
        shrink = 1 - min(0.5, lift / (place.human * 0.5))
        rect = pygame.Rect(0, 0, max(2, round(cam.s(width) * shrink)), max(2, round(cam.s(width * 0.22) * shrink)))
        rect.center = (x, y)
        shadow = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, int(110 * fade)), shadow.get_rect())
        target.blit(shadow, rect)
        if fade < 1:
            return
        color = CURRENT_RING if uid == self.view.current_uid else SIDE_RING[place.side]
        ring = pygame.Surface(rect.inflate(8, 6).size)
        pygame.draw.ellipse(ring, color, ring.get_rect(), max(1, round(cam.s(1.5))))
        target.blit(ring, rect.inflate(8, 6), special_flags=pygame.BLEND_RGB_ADD)

    def _sprite_at(self, place: Place, cam: Camera, now: int, uid: int) -> tuple[pygame.Surface, pygame.Surface]:
        breath = 1 + 0.012 * math.sin(now / 650 + uid * 1.7)      # еле заметное дыхание
        px_height = max(4, round(cam.s(place.height) * breath / 2) * 2)
        return self.bank.scaled(place.sprite, px_height, place.side == "right")

    def sprite_rect(self, uid: int, now: int, cam: Camera) -> pygame.Rect:
        place = self.stage[uid]
        sprite, _ = self._sprite_at(place, cam, now, uid)
        dx, dy, lift, _ = self.offset(uid, now)
        return sprite.get_rect(midbottom=cam.p(place.feet[0] + dx, place.feet[1] + dy - lift))

    def _update_alpha(self, order: list[int], now: int, cam: Camera) -> None:
        """Во время атаки юниты, нарисованные поверх атакующего или цели и закрывающие их, становятся прозрачными."""
        members, start, end = self.focus
        active = {uid for uid in order if uid in members} if start <= now <= end else set()
        rects = {uid: self.sprite_rect(uid, now, cam) for uid in order}
        step = min(1.0, max(0, now - self._last_draw) / FADE_MS) if self._last_draw else 1.0
        self._last_draw = now
        drawn: list[int] = []               # активные юниты, уже нарисованные (под текущим)
        for uid in order:
            rect = rects[uid]
            core = rect.inflate(-rect.width // 4, -rect.height // 8)
            covers = uid not in members and any(core.colliderect(rects[a]) for a in drawn)
            goal = SEE_THROUGH if covers else 255
            current = self.alpha.get(uid, 255)
            self.alpha[uid] = current + (goal - current) * step
            if uid in active:
                drawn.append(uid)

    def _draw_unit(self, target: pygame.Surface, unit: Unit, now: int, cam: Camera) -> None:
        uid, place = unit.uid, self.stage[unit.uid]
        sprite, white = self._sprite_at(place, cam, now, uid)
        dx, dy, lift, angle = self.offset(uid, now)
        shake_dx, flash = self.fx.hit_reaction(uid, now)
        dying = self.death_progress(uid, now)
        alpha = self.alpha.get(uid, 255) * (1 - dying)
        if dying > 0:   # падает назад и тает
            angle += 70 * ease_out(dying) * place.facing
        # Послеобразы рывка: тот же спрайт в недавних точках пути, всё прозрачнее.
        if any(m.trail and m.moving(now) for m in self.motions.get(uid, ())):
            ghost = sprite.copy()
            ghost.fill((70, 90, 140), special_flags=pygame.BLEND_RGB_ADD)
            for i in range(TRAIL_GHOSTS, 0, -1):
                gdx, gdy, glift, _ = self.offset(uid, now - i * TRAIL_STEP_MS)
                ghost.set_alpha(int(120 * (1 - i / (TRAIL_GHOSTS + 1)) * alpha / 255))
                target.blit(ghost, ghost.get_rect(midbottom=cam.p(place.feet[0] + gdx, place.feet[1] + gdy - glift)))
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
        rect = image.get_rect(midbottom=cam.p(place.feet[0] + dx + shake_dx, place.feet[1] + dy - lift))
        if angle:   # поворот вокруг ног: сдвиг, чтобы ноги остались на месте
            rect.centerx += round(math.sin(math.radians(angle)) * -sprite.get_height() * 0.3)
        target.blit(image, rect)
        if flash > 0 and not angle:
            white = white.copy()
            white.set_alpha(int(200 * flash * alpha / 255))
            target.blit(white, rect)

    def _draw_plate(self, target: pygame.Surface, unit: Unit, cam: Camera) -> None:
        """Под ногами: полоса HP, числа HP, AP и PP, ниже активные эффекты."""
        uid, place = unit.uid, self.stage[unit.uid]
        if uid in self.dead:
            return
        hp, max_hp = self.hp.get(uid, unit.hp), max(1, unit.max_hp)
        w = place.human * 0.3
        bar = pygame.Rect(cam.p(place.feet[0] - w / 2, place.feet[1] + 8), (max(4, round(cam.s(w))), max(2, round(cam.s(5)))))
        pygame.draw.rect(target, (30, 20, 22), bar.inflate(2, 2))
        fill = bar.copy()
        fill.width = round(bar.width * max(0, hp) / max_hp)
        pygame.draw.rect(target, GREEN if hp * 3 > max_hp else RED, fill)
        font = fx_font(round(cam.s(11)), True)
        text = f"{hp}   AP {unit.ap.current}  PP {unit.pp.current}"
        img, shade = font.render(text, True, (235, 235, 240)), font.render(text, True, (10, 10, 14))
        pos = img.get_rect(midtop=(bar.centerx, bar.bottom + max(1, round(cam.s(1)))))
        target.blit(shade, pos.move(1, 1))
        target.blit(img, pos)
        if unit.effects:
            names = ", ".join(self.t(e.definition.name) for e in unit.effects)
            line = fx_font(round(cam.s(10)), False).render(names, True, (220, 190, 255))
            target.blit(line, line.get_rect(midtop=(bar.centerx, pos.bottom)))
        if uid == self.view.current_uid:
            add_glow(target, cam.p(*place.anchor("head")), (60, 50, 15), cam.s(30), 1.0)
