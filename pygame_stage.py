"""Вкладка Stage: бой статичными спрайтами юнитов, как в Unicorn Overlord.

Юниты не анимируются покадрово: живость дают движения спрайта (рывок с послеобразами,
прыжок, отскок, наклон, отбрасывание, подъём в воздух, свечение) и эффекты. Что делает
каждый навык, задаётся данными в assets/visuals/skills.json: шаги в момент применения
(cast) и на каждое попадание (hit). Навыки без описания берут общий визуал по виду.

Спрайты: assets/units/<id класса>.png, нарезанные tools/cut_lineup.py с одного листа,
поэтому их размеры согласованы; общий масштаб берётся из роста человека на листе.
Экран только читает бой; в логику не вмешивается. Зум, перетаскивание, лог и строка
состояния — как на вкладке Arena (наследуются).
"""
from __future__ import annotations

import json
import math
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

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
from pygame_arena import FIELD_TOP, ArenaScreen, skill_visual
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
    add_glow,
    ease_out,
    fx_font,
)
from pygame_ui import GREEN, RED, UI

ROOT = Path(__file__).resolve().parent
UNITS_DIR = ROOT / "assets" / "units"
VISUALS_PATH = ROOT / "assets" / "visuals" / "skills.json"

HUMAN_H = 112              # рост человека в ближней колонне, логические пиксели
FAR_SCALE = 0.78           # масштаб дальней колонны относительно ближней
GROUND_FAR, GROUND_NEAR = 228, 446   # линия земли дальней и ближней колонны
ROW_GAP = 92               # передний ряд от центра поля
ROW_STEP = 136             # шаг между рядами
DEFAULT_WINDUP = 380
DEATH_MS = 800
TRAIL_GHOSTS = 4           # послеобразов при рывке
SPRITE_CACHE = 300
DOT_CAUSES = ("burn", "poison", "plague")
SIDE_RING = {"left": (60, 110, 220), "right": (220, 70, 60)}


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
    start: int
    duration: int
    color: tuple[int, int, int]

    def strength(self, now: int) -> float:
        t = (now - self.start) / max(1, self.duration)
        return math.sin(math.pi * t) if 0 <= t <= 1 else 0.0


# --- спрайты ------------------------------------------------------------------

class SpriteBank:
    """Спрайты классов и их общий масштаб; классам без картинки — запасной спрайт."""

    def __init__(self, folder: Path = UNITS_DIR):
        self.folder = folder
        path = folder / "units.json"
        self.config: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self._images: dict[str, Optional[pygame.Surface]] = {}
        self._scaled: OrderedDict = OrderedDict()

    def sprite_id(self, unit: Unit) -> Optional[str]:
        """Какой спрайт у юнита: свой, по классу из fallback, по тегу, по умолчанию."""
        sprites = self.config.get("sprites", {})
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

    def height(self, sprite_id: Optional[str]) -> float:
        """Рост спрайта в логических пикселях (ближняя колонна)."""
        info = self.config.get("sprites", {}).get(sprite_id or "")
        if not info:
            return HUMAN_H
        human = self.config.get("sheets", {}).get(info.get("sheet"), {}).get("human_height") or info["height"]
        return HUMAN_H * info["height"] / human

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
        if None not in self._images or self._images[None] is None:
            s = pygame.Surface((60, 150), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (150, 150, 165), (10, 30, 40, 120))
            pygame.draw.circle(s, (190, 180, 170), (30, 20), 16)
            self._images[None] = s
        return self._images[None]

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
    """Где стоит юнит: ноги, масштаб глубины, сторона, спрайт и его рост (логические пиксели)."""

    feet: tuple[float, float]
    scale: float
    side: str
    sprite: Optional[str]
    height: float

    @property
    def facing(self) -> int:
        return 1 if self.side == "left" else -1

    def anchor(self, on: str) -> tuple[float, float]:
        x, y = self.feet
        human = HUMAN_H * self.scale
        if on == "feet":
            return x, y
        if on == "head":
            return x, y - human * 0.9
        if on == "sky":
            return x, FIELD_TOP - 20
        return x, y - human * 0.5


class StageScreen(ArenaScreen):
    """Вкладка боя спрайтами. Свой бой: тестовые отряды (или расстановка игрока, клавиша T)."""

    def __init__(self):
        super().__init__()
        self.bank = SpriteBank()
        self.visuals = load_visuals()
        self.battle_view: Any = None        # свой BattleView; его создаёт окно
        self.use_test = True                # тестовые отряды пяти классов, иначе расстановка игрока
        self.stage: dict[int, Place] = {}
        self.motions: dict[int, list[Motion]] = {}
        self.tints: dict[int, list[Tint]] = {}
        self.deaths: dict[int, int] = {}
        self._hit_source: Optional[int] = None

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
        if unit is not None and f"{unit.definition.id}/{skill_id}" in self.visuals:
            return self.visuals[f"{unit.definition.id}/{skill_id}"]
        if skill_id in self.visuals:
            return self.visuals[skill_id]
        db = self.battle_view.db if self.battle_view is not None else None
        skill = db.skills.get(skill_id) if db is not None else None
        delivery = skill_visual(skill, unit)[0]
        return self.visuals.get("_defaults", {}).get(delivery, {})

    def status_note(self) -> str:
        return "   " + self._t("test squads (T)" if self.use_test else "your squads (T)")

    def handle_event(self, event: pygame.event.Event, pos: tuple[float, float], window_scale: float = 1.0) -> None:
        super().handle_event(event, pos, window_scale)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_t and self.battle_view is not None:
            self.use_test = not self.use_test
            self.battle_view.restart(self.battle_view.seed)

    # --- раскладка ---

    def layout(self, sim: Any) -> dict:
        """Колонны формации уходят в глубину (дальняя выше и мельче), ряды — от центра к краю."""
        result = {}
        self.stage = {}
        for squad, side in ((sim.attacker, "left"), (sim.defender, "right")):
            formation = squad.formation
            cols = formation.cols
            for unit in formation.units:
                row, col = formation.position_of(unit.uid)
                depth = col / (cols - 1) if cols > 1 else 1.0          # 0 дальняя, 1 ближняя
                scale = FAR_SCALE + (1 - FAR_SCALE) * depth
                offset = (ROW_GAP + row * ROW_STEP) * (0.8 + 0.2 * depth)
                x = 500 - offset if side == "left" else 500 + offset
                y = GROUND_FAR + (GROUND_NEAR - GROUND_FAR) * depth
                sprite = self.bank.sprite_id(unit)
                height = self.bank.height(sprite) * scale
                place = Place((x, y), scale, side, sprite, height)
                self.stage[unit.uid] = place
                # Для общих эффектов Arena: центр тела и «рост» для подписи над головой.
                body = place.anchor("body")
                result[unit.uid] = ((int(body[0]), int(body[1])), (int(HUMAN_H * scale * 0.6), int(HUMAN_H * scale)), side)
        return result

    def _sync(self, view: Any, now: int) -> None:
        if view.sim is not self._sim:
            self.motions.clear()
            self.tints.clear()
            self.deaths.clear()
        super()._sync(view, now)

    # --- события -> движения и эффекты ---

    def _spawn(self, ui: UI, view: Any, ev: Any, when: int, places: dict) -> None:
        units, db, stage = view.sim.units, view.db, self.stage
        if isinstance(ev, SkillUsed):
            unit = units.get(ev.user)
            skill = db.skills.get(ev.skill_id)
            visual = skill_visual(skill, unit)
            self._visuals[ev.user] = visual
            if ev.user in stage:
                head = stage[ev.user].anchor("head")
                self.fx.add(FloatText(when, 900, (head[0], head[1] - 14), ui.t(skill.name) if skill else ev.skill_id,
                                      (255, 236, 170), 14, 18, False))
            context = {"self": ev.user, "target": ev.target, "targets": self._targets_of(view, ev),
                       "source": ev.user, "element": visual[1], "visual": visual}
            self._run(self.spec(unit, ev.skill_id).get("cast", []), when, context, "self")
        elif isinstance(ev, DamageDealt):
            self._hit_source = ev.source if ev.cause not in DOT_CAUSES and ev.cause not in db.effects else None
            self._hit_event = ev
            super()._spawn(ui, view, ev, when, places)
            self._hit_source = None
        elif isinstance(ev, Healed):
            super()._spawn(ui, view, ev, when, places)
            if ev.source is not None and ev.amount > 0:
                unit = units.get(ev.source)
                self._run(self.spec(unit, ev.cause).get("hit", []), when, self._hit_context(ev.source, ev.target), "target")
        elif isinstance(ev, AttackMissed):
            super()._spawn(ui, view, ev, when, places)
            if ev.target in stage:   # уклонение: короткий отскок назад
                f = stage[ev.target].facing
                self._move(ev.target, Motion(when, 90, 80, 260, dx=-f * 22, lift=10))
        elif isinstance(ev, Covered):
            self._cover(ui, ev, when)
        elif isinstance(ev, UnitDied):
            super()._spawn(ui, view, ev, when, places)
            self.deaths[ev.unit] = when
        else:
            super()._spawn(ui, view, ev, when, places)

    def _impact(self, when: int, pos: tuple[int, int], visual: tuple, facing: int) -> None:
        """Попадание навыка: шаги hit из визуала навыка (общий удар — только по шагу impact)."""
        source, ev = self._hit_source, getattr(self, "_hit_event", None)
        if source is None or ev is None or self.battle_view is None:
            super()._impact(when, pos, visual, facing)
            return
        unit = self.battle_view.sim.units.get(source)
        self._run(self.spec(unit, ev.cause).get("hit", []), when, self._hit_context(source, ev.target), "target")

    def _hit_context(self, source: int, target: int) -> dict[str, Any]:
        visual = self._visuals.get(source, ("melee", None, "slashing"))
        return {"self": source, "target": target, "targets": [target], "source": source,
                "element": visual[1], "visual": visual}

    def _cover(self, ui: UI, ev: Covered, when: int) -> None:
        """Прикрытие: защитник прыжком встаёт перед союзником, перед ним купол щита."""
        stage = self.stage
        if ev.protector not in stage or ev.target not in stage:
            return
        guard, ward = stage[ev.protector], stage[ev.target]
        f = ward.facing
        dx = ward.feet[0] + f * 40 - guard.feet[0]
        dy = ward.feet[1] + 4 - guard.feet[1]
        self._move(ev.protector, Motion(when, 200, 500, 350, dx=dx, dy=dy, lift=24, trail=True))
        front = (ward.feet[0] + f * 60, ward.anchor("body")[1])
        self.fx.add(Dome(when + 150, 700, front, ELEMENT_COLORS["guard"], 56 * ward.scale))
        self.fx.add(FloatText(when, 900, (front[0], front[1] - 70), ui.t("cover").upper(), ELEMENT_COLORS["guard"], 20, 20))

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

    def _move(self, uid: int, motion: Motion) -> None:
        self.motions.setdefault(uid, []).append(motion)

    def _color(self, step: dict, context: dict) -> tuple[int, int, int]:
        color = step.get("color", "steel")
        if color == "$element":
            color = context.get("element") or "steel"
        if isinstance(color, str):
            return ELEMENT_COLORS.get(color, (255, 255, 255))
        return tuple(color)

    def _run(self, steps: list[dict], base: int, context: dict, default_who: str) -> None:
        for step in steps:
            who = step.get("who", default_who)
            uids = context["targets"] if who == "targets" else [context.get(who)]
            for uid in uids:
                if uid in self.stage:
                    self._step(step, base + int(step.get("at", 0)), uid, context)

    def _step(self, step: dict, at: int, uid: int, context: dict) -> None:
        """Один шаг визуала для юнита uid в момент at."""
        fx, stage = self.fx, self.stage
        place = stage[uid]
        source = stage.get(context["source"], place)
        target = stage.get(context["target"], place)
        do = step.get("do")
        ms = int(step.get("ms", 400))
        color = self._color(step, context)
        pos = place.anchor(step.get("on", "body"))
        f = place.facing
        k = place.scale

        if do == "dash":                      # к цели, остановка в gap перед ней (gap < 0 — насквозь)
            gap = step.get("gap", 64) * target.scale
            dx = target.feet[0] + target.facing * gap - place.feet[0]   # перед целью, со стороны противника
            if uid == context["target"]:
                dx = 0
            dy = target.feet[1] - place.feet[1]
            self._move(uid, Motion(at, ms, int(step.get("hold", 150)), int(step.get("back", 350)), dx=dx, dy=dy,
                                   trail=step.get("trail", False)))
        elif do in ("hop", "lunge"):          # шаг назад или вперёд и обратно
            sign = -1 if do == "hop" else 1
            go = int(ms * 0.4)
            self._move(uid, Motion(at, go, int(step.get("hold", ms * 0.2)), ms - go, dx=sign * f * step.get("dist", 14) * k))
        elif do == "jump":
            self._move(uid, Motion(at, ms // 2, 0, ms - ms // 2, lift=step.get("height", 24) * k))
        elif do == "rise":                    # подъём в воздух и спуск
            go = int(ms * 0.3)
            self._move(uid, Motion(at, go, int(ms * 0.4), ms - go - int(ms * 0.4), dy=-step.get("height", 16) * k))
        elif do == "tilt":
            go = int(ms * 0.3)
            self._move(uid, Motion(at, go, int(ms * 0.3), ms - go - int(ms * 0.3), angle=step.get("angle", -8) * f))
        elif do == "knockback":               # отброс назад, к своему краю поля
            self._move(uid, Motion(at, 90, 70, 320, dx=-f * step.get("dist", 14) * k))
        elif do == "glow":
            self.tints.setdefault(uid, []).append(Tint(at, ms, color))
        elif do == "projectile":
            start = source.anchor("body")
            start = (start[0] + 22 * source.facing, start[1] - 6)
            end = (start[0] + 50 * source.facing, FIELD_TOP - 30) if step.get("to") == "sky" else target.anchor("body")
            size = 0.6 if step.get("small") else 1.7 if step.get("big") else 1.0
            fx.add(Projectile(at, ms, start, end, step.get("kind", "orb"), color, step.get("arc", 0) * k, size))
        elif do == "slash":
            fx.add(Slash(at, ms if "ms" in step else 320, pos, self._color({"color": step.get("color", "steel")}, context),
                         step.get("radius", 48) * k, source.facing))
        elif do == "thrust":
            fx.add(Thrust(at, ms if "ms" in step else 280, pos, color, source.facing))
        elif do == "ring":
            fx.add(Ring(at, ms, pos, color, step.get("from", 10) * k, step.get("to", 60) * k, int(step.get("thickness", 4)),
                        0.35 if step.get("on") == "feet" else 0.6))
        elif do == "beam":
            fx.add(Beam(at, ms, place.anchor("feet"), color, int(step.get("thickness", 34) * k)))
        elif do == "bolt":
            fx.add(Bolt(at, ms, (pos[0] + 20 * source.facing, FIELD_TOP - 10), pos, color, seed=at))
        elif do == "burst":
            fx.burst(at, pos, color, int(step.get("count", 18)), step.get("speed", 3.0), int(step.get("life", 650)),
                     step.get("size", 3.0), step.get("gravity", 0.05), step.get("shape", "glow"), step.get("up", 0.0))
        elif do == "sparkle":                 # искры поднимаются от тела
            rect = pygame.Rect(0, 0, int(60 * k), int(HUMAN_H * k))
            rect.midbottom = (int(place.feet[0]), int(place.feet[1]))
            fx.rise(at, rect, color, int(step.get("count", 16)), step.get("shape", "glow"), 1.5, 900, 3)
        elif do == "flash":
            fx.add(Flash(at, ms, color, step.get("power", 0.3)))
        elif do == "shake":
            fx.shake(at, ms, step.get("power", 5))
        elif do == "runes":
            fx.add(RuneCircle(at, ms, place.anchor("feet"), color, step.get("radius", 40) * k))
        elif do == "pillars":                 # столбы вокруг цели: в центре и по сторонам
            count = int(step.get("count", 3))
            radius = step.get("radius", 26) * k
            x, y = place.feet
            for i in range(count):
                a = (i - (count - 1) / 2) * 1.2
                base = (x + math.sin(a) * radius * 1.4, y + math.cos(a) * radius * 0.25 - (0 if i == count // 2 else 6))
                fx.add(Pillar(at + abs(i - count // 2) * 70, ms, base, color, step.get("height", 120) * k,
                              step.get("thickness", 28) * k, seed=at + i))
        elif do == "arrow_rain":
            fx.add(ArrowRain(at, ms, place.anchor("feet"), color if "color" in step else (255, 240, 200),
                             int(step.get("count", 10)), 34 * k, source.facing, seed=at + uid))
        elif do == "glint":
            fx.add(Glint(at, ms, (pos[0] + 16 * f, pos[1]), color if "color" in step else (255, 250, 220),
                         step.get("size", 22) * k))
        elif do == "dome":
            fx.add(Dome(at, ms, pos, color, step.get("radius", 50) * k))
        elif do == "impact":                  # общий эффект удара по виду навыка и стихии
            ArenaScreen._impact(self, at, (int(pos[0]), int(pos[1])), context["visual"], source.facing)

    # --- отрисовка ---

    def _offset(self, uid: int, now: int) -> tuple[float, float, float, float]:
        dx = dy = lift = angle = 0.0
        for motion in self.motions.get(uid, ()):
            value = motion.at(now)
            if value is not None:
                dx, dy, lift, angle = dx + value[0], dy + value[1], lift + value[2], angle + value[3]
        return dx, dy, lift, angle

    def draw_field(self, target: pygame.Surface, now: int, cam: Camera) -> None:
        view = self._view
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
        self._draw_background(target, cam)
        units = view.sim.units
        visible = [uid for uid in self.stage if self._death_progress(uid, now) < 1]
        for uid in visible:
            self._draw_ground(target, uid, view, now, cam)
        # Дальние раньше ближних; кто сейчас в движении — поверх стоящих на той же линии.
        order = sorted(visible, key=lambda uid: (self.stage[uid].feet[1] + self._offset(uid, now)[1]
                                                 + (30 if self.motions.get(uid) else 0)))
        for uid in order:
            self._draw_unit(target, units[uid], now, cam)
        for uid in order:
            self._draw_plate(target, units[uid], now, cam)
        self.fx.draw(target, now, cam)
        target.set_clip(previous_clip)

    def _death_progress(self, uid: int, now: int) -> float:
        """0 жив, 0..1 падает и тает, 1 исчез."""
        if uid not in self._dead:
            return 0.0
        died = self.deaths.get(uid)
        return 1.0 if died is None else min(1.0, max(0.0, (now - died) / DEATH_MS))

    def _draw_ground(self, target: pygame.Surface, uid: int, view: Any, now: int, cam: Camera) -> None:
        """Тень под ногами и цветное кольцо стороны; у ходящего юнита кольцо жёлтое."""
        place = self.stage[uid]
        dx, dy, lift, _ = self._offset(uid, now)
        fade = 1 - self._death_progress(uid, now)
        width = HUMAN_H * place.scale * (0.9 if place.height > HUMAN_H * place.scale * 1.3 else 0.5)
        x, y = cam.p(place.feet[0] + dx, place.feet[1] + max(0.0, dy) + 2)
        shrink = 1 - min(0.5, lift / 80)
        rect = pygame.Rect(0, 0, max(2, round(cam.s(width) * shrink)), max(2, round(cam.s(width * 0.22) * shrink)))
        rect.center = (x, y)
        shadow = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, int(110 * fade)), shadow.get_rect())
        target.blit(shadow, rect)
        if fade < 1:
            return
        color = (230, 200, 80) if uid == view.current_uid else SIDE_RING[place.side]
        ring = pygame.Surface(rect.inflate(8, 6).size)
        pygame.draw.ellipse(ring, color, ring.get_rect(), max(1, round(cam.s(1.5))))
        target.blit(ring, rect.inflate(8, 6), special_flags=pygame.BLEND_RGB_ADD)

    def _sprite_at(self, place: Place, cam: Camera, now: int, uid: int) -> tuple[pygame.Surface, pygame.Surface]:
        breath = 1 + 0.012 * math.sin(now / 650 + uid * 1.7)      # еле заметное дыхание
        px_height = max(4, round(cam.s(place.height) * breath / 2) * 2)
        return self.bank.scaled(place.sprite, px_height, place.side == "right")

    def _draw_unit(self, target: pygame.Surface, unit: Unit, now: int, cam: Camera) -> None:
        uid, place = unit.uid, self.stage[unit.uid]
        sprite, white = self._sprite_at(place, cam, now, uid)
        dx, dy, lift, angle = self._offset(uid, now)
        shake_dx, _, flash = self.fx.card_offset(uid, now, place.feet)
        dying = self._death_progress(uid, now)
        if dying > 0:   # падает назад и тает
            angle += 70 * ease_out(dying) * place.facing
        # Послеобразы рывка: тот же спрайт в недавних точках пути, всё прозрачнее.
        if any(m.trail and m.moving(now) for m in self.motions.get(uid, ())):
            for i in range(TRAIL_GHOSTS, 0, -1):
                gdx, gdy, glift, _ = self._offset(uid, now - i * 28)
                ghost = sprite.copy()
                ghost.fill((70, 90, 140), special_flags=pygame.BLEND_RGB_ADD)
                ghost.set_alpha(int(120 * (1 - i / (TRAIL_GHOSTS + 1))))
                target.blit(ghost, ghost.get_rect(midbottom=cam.p(place.feet[0] + gdx, place.feet[1] + gdy - glift)))
        feet = cam.p(place.feet[0] + dx + shake_dx, place.feet[1] + dy - lift)
        image = sprite
        tint = [(t.color, t.strength(now)) for t in self.tints.get(uid, ()) if t.strength(now) > 0.02]
        if tint:
            image = sprite.copy()
            for color, k in tint:
                image.fill(tuple(int(c * k * 0.55) for c in color), special_flags=pygame.BLEND_RGB_ADD)
        if dying > 0:
            image = image.copy() if image is sprite else image
            image.set_alpha(int(255 * (1 - dying)))
        if angle:
            image = pygame.transform.rotate(image, angle)
        rect = image.get_rect(midbottom=feet)
        if angle:   # поворот вокруг ног: сдвиг, чтобы ноги остались на месте
            rect.centerx += round(math.sin(math.radians(angle)) * -sprite.get_height() * 0.3)
        target.blit(image, rect)
        if flash > 0 and not angle:
            white = white.copy()
            white.set_alpha(int(200 * flash))
            target.blit(white, rect)

    def _draw_plate(self, target: pygame.Surface, unit: Unit, now: int, cam: Camera) -> None:
        """Под ногами: полоса HP, числа HP, AP и PP."""
        uid, place = unit.uid, self.stage[unit.uid]
        if uid in self._dead:
            return
        hp, max_hp = self._hp.get(uid, unit.hp), max(1, unit.max_hp)
        w = 54 * place.scale
        x, y = place.feet[0] - w / 2, place.feet[1] + 8
        bar = pygame.Rect(cam.p(x, y), (max(4, round(cam.s(w))), max(2, round(cam.s(5)))))
        pygame.draw.rect(target, (30, 20, 22), bar.inflate(2, 2))
        fill = bar.copy()
        fill.width = round(bar.width * max(0, hp) / max_hp)
        pygame.draw.rect(target, GREEN if hp * 3 > max_hp else RED, fill)
        font = fx_font(round(cam.s(11)), True)
        text = f"{hp}   AP {unit.ap.current}  PP {unit.pp.current}"
        img = font.render(text, True, (235, 235, 240))
        shade = font.render(text, True, (10, 10, 14))
        pos = img.get_rect(midtop=(bar.centerx, bar.bottom + max(1, round(cam.s(1)))))
        target.blit(shade, pos.move(1, 1))
        target.blit(img, pos)
        if unit.effects:
            names = ", ".join(self._t(e.definition.name) for e in unit.effects)
            small = fx_font(round(cam.s(10)), False)
            line = small.render(names, True, (220, 190, 255))
            target.blit(line, line.get_rect(midtop=(bar.centerx, pos.bottom)))
        if uid == self._view.current_uid:
            add_glow(target, cam.p(*place.anchor("head")), (60, 50, 15), cam.s(30), 1.0)
