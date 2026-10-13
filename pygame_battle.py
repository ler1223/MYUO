"""Проигрывание боя: расписание событий (BattleView) и основа экрана боя (BattleScreen).

BattleView делает шаги симуляции и даёт каждому событию время показа, чтобы удары, эффекты
и гибель шли друг за другом. BattleScreen превращает наступившие события в общие эффекты
(числа урона и лечения, промах, крит, блок, эффекты, пассивки, раунд, конец боя), рисует
строку состояния и лог и держит камеру. Где стоят юниты (point, facing) и как выглядит
поле (draw_field), решает наследник. Экран только читает бой; в логику не вмешивается.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

import pygame

from engine.camera import Camera, ViewCamera
from engine.fx import ELEMENT_COLORS, Beam, Bolt, Flash, FloatText, FxSystem, Ring, Slash, Thrust
from engine.projection import World
from engine.sprites import SINGLE_MS, FxLibrary, SpriteEffect
from game.battle import BattleSimulation
from game.definitions import PART_HEAL, SkillDefinition
from game.events import (
    AttackMissed,
    BattleEnded,
    Covered,
    DamageDealt,
    EffectApplied,
    EffectExpired,
    Event,
    Healed,
    PassiveTriggered,
    ResourceGained,
    RoundStarted,
    SkillUsed,
    TurnSkipped,
    TurnStarted,
    UnitDied,
    format_event,
)
from game.unit import Unit
from pygame_ui import DIM, GREEN, HEIGHT, PANEL, RED, TEXT, UI, WIDTH, YELLOW, fit

CENTER_X = WIDTH // 2
FIELD_RECT = pygame.Rect(0, 52, WIDTH, 440)   # область поля в логических пикселях окна
LOG_TOP = FIELD_RECT.bottom + 8
LOG_LINES = 5
LOG_LINE_H = 18
SKIP_BACKLOG_MS = 300      # после долгого перерыва старые события не проигрываются пачкой

# --- расписание ------------------------------------------------------------------

SETTLE_MS = 250             # пауза после последнего события шага
TIMELINE_KEEP_MS = 3000     # сколько хранить показанные события (эффектам хватает)
POPUP_MS = 900              # всплывающие числа вкладки Battle
KEEP_LOG = 8
# Сколько длится показ события, прежде чем показывать следующее.
BEAT_MS: dict[type, int] = {
    SkillUsed: 380, DamageDealt: 110, AttackMissed: 110, Healed: 110, Covered: 200,
    EffectApplied: 60, EffectExpired: 40, ResourceGained: 60, PassiveTriggered: 120,
    UnitDied: 250, RoundStarted: 450, TurnSkipped: 200,
}


@dataclass
class Popup:
    uid: int
    text: str
    color: tuple[int, int, int]
    born: int


class BattleView:
    """Состояние показа боя: строится только из событий симуляции.

    beat: своя длительность показа события (замах навыка на вкладке Stage) или None.
    """

    def __init__(self, db: Any, seed: int, scenario_factory: Callable[[], Any],
                 beat: Optional[Callable[[Event], Optional[int]]] = None):
        self.db = db
        self.scenario_factory = scenario_factory
        self.beat = beat
        self.restart(seed)

    def restart(self, seed: int) -> None:
        scenario = self.scenario_factory()
        self.seed = seed
        self.sim = BattleSimulation(scenario.player_squad, scenario.enemy_squad, self.db, seed=seed)
        self.log: list[Event] = []  # последние события; текст строится при отрисовке на текущем языке
        self.popups: list[Popup] = []
        self.current_uid: Optional[int] = None
        self.round = 0
        self.ended: Optional[BattleEnded] = None
        self.timeline: list[tuple[int, Event]] = []   # (когда показать, событие)
        self.busy_until = 0

    def step(self, now: int) -> None:
        self.consume(self.sim.step(), now)

    def schedule(self, events: list[Event], now: int) -> list[int]:
        """Время показа каждого события: замах, удары по очереди, гибель."""
        cursor = max(now, self.busy_until - SETTLE_MS)
        times = []
        for ev in events:
            times.append(cursor)
            own = self.beat(ev) if self.beat is not None else None
            cursor += own if own is not None else BEAT_MS.get(type(ev), 0)
        self.busy_until = cursor + SETTLE_MS
        return times

    def consume(self, events: list[Event], now: int) -> None:
        times = self.schedule(events, now)
        self.timeline.extend(zip(times, events))
        for when, ev in zip(times, events):
            self._consume_one(ev, when)
        self.log = (self.log + events)[-KEEP_LOG:]

    def _consume_one(self, ev: Event, now: int) -> None:
        """Ход, раунд, итог и всплывающие числа вкладки Battle; now — время показа события."""
        if isinstance(ev, RoundStarted):
            self.round = ev.round
        elif isinstance(ev, TurnStarted):
            self.current_uid = ev.unit
        elif isinstance(ev, DamageDealt):
            self.popups.append(Popup(ev.target, f"-{ev.amount}" + ("!" if ev.crit else ""), RED, now))
        elif isinstance(ev, Healed):
            self.popups.append(Popup(ev.target, f"+{ev.amount}" + ("!" if ev.crit else ""), GREEN, now))
        elif isinstance(ev, BattleEnded):
            self.current_uid = None
            self.ended = ev

    def prune(self, now: int) -> None:
        # Всплывающие числа живут POPUP_MS с момента показа (он может быть в будущем).
        self.popups = [p for p in self.popups if now - p.born < POPUP_MS]
        self.timeline = [(when, ev) for when, ev in self.timeline if now - when < TIMELINE_KEEP_MS]


# --- вид навыка ----------------------------------------------------------------

AP_COLOR = (90, 160, 240)
PP_COLOR = (190, 120, 235)
ELEMENTS = ("lightning", "fire", "ice", "light", "dark", "poison")
PHYSICAL = ("slashing", "piercing", "blunt")
DOT_VISUALS = {"burn": "fire", "poison": "poison", "plague": "dark"}   # периодический урон эффектов
EFFECT_LOOKS = {"stun": "stun", "poison": "poison", "plague": "poison", "burn": "fire", "slow": "ice"}
# Вид эффекта -> спрайтовый эффект из assets/fx (если он есть).
EFFECT_SPRITES = {"stun": "stun_stars", "poison": "poison_cloud", "fire": "burning", "ice": "ice_burst",
                  "buff": "buff", "debuff": "debuff"}
# Слот оружия класса -> вид оружия в эффекте атаки.
WEAPON_BY_SLOT = {"light_sword": "sword", "heavy_weapon": "axe", "lance": "spear", "dagger": "dagger",
                  "bow": "bow", "staff": "staff"}

Visual = tuple[str, Optional[str], str]


def weapon_kind(unit: Optional[Unit], delivery: str) -> str:
    """Каким оружием бьёт юнит: надетое оружие, иначе оружейный слот класса, иначе по виду навыка."""
    if unit is not None:
        for item in unit.equipped:
            if item.slot in WEAPON_BY_SLOT:
                return WEAPON_BY_SLOT[item.slot]
        for slot in unit.definition.slots:
            if slot in WEAPON_BY_SLOT:
                return WEAPON_BY_SLOT[slot]
    return {"arrow": "bow", "magic": "staff"}.get(delivery, "fist")


def skill_visual(skill: Optional[SkillDefinition], user: Optional[Unit]) -> Visual:
    """(доставка, стихия, физический тип) навыка: от этого зависит, какой эффект рисовать.

    Доставка: melee (удар), arrow (стрела), magic (заклинание), heal, support.
    """
    if skill is None:
        return "melee", None, "slashing"
    damage_tags: set[str] = set()
    for part in skill.parts:
        damage_tags.update(part.tags)
        if part.weapon_tags and user is not None:
            damage_tags.update(user.weapon_damage_tags)
    if skill.parts and all(part.kind == PART_HEAL for part in skill.parts):
        return "heal", "heal", ""
    if not skill.parts:
        return "support", "buff", ""
    element = next((e for e in ELEMENTS if e in damage_tags), None)
    if element is None and any(a.effect_id in ("poison", "plague") for a in skill.applies):
        element = "poison"
    physical = next((p for p in PHYSICAL if p in damage_tags), "slashing")
    if "ranged" in skill.tags:
        return "arrow", element, physical
    if "magic" in skill.tags or any(part.category == "magical" for part in skill.parts):
        return "magic", element or "arcane", physical
    return "melee", element, physical


# --- экран боя -------------------------------------------------------------------

class BattleScreen:
    """Вкладка боя. is_battle: на ней работают клавиши боя. Наследник задаёт, где стоят юниты."""

    is_battle = True

    def __init__(self) -> None:
        self.fx = FxSystem()
        self.camera_view = ViewCamera(FIELD_RECT)
        self._sim: Any = None
        self._shown_until = 0               # события до этого момента уже показаны
        self._prev_frame = 0
        self.hp: dict[int, int] = {}        # HP, как в уже показанных событиях
        self.dead: set[int] = set()
        self.visuals: dict[int, Visual] = {}   # uid -> вид его последнего навыка
        self.view: Any = None
        self.t: Any = str
        self.native = False                 # поле рисуется отдельно, прямо в окно (draw_field)
        self.dragging = False
        self.sprites: Optional[FxLibrary] = None   # спрайтовые эффекты (assets/fx); None — только кодом

    # --- что задаёт наследник ---

    def layout(self, sim: Any) -> None:
        """Расставить юнитов боя sim."""

    def point(self, uid: int, on: str = "body") -> World:
        """Точка юнита в мире: feet, body, head."""
        return 0.0, 0.0, 0.0

    def facing(self, uid: int) -> int:
        """1 — смотрит вправо (отряд игрока), -1 — влево."""
        return 1

    def reset(self) -> None:
        """Новый бой: забыть всё, что относилось к прошлому."""
        self.fx.clear()
        self.visuals.clear()

    def draw_field(self, target: pygame.Surface, now: int, cam: Camera) -> None:
        """Поле боя в пикселях окна через камеру."""

    def status_note(self) -> str:
        """Добавка к строке состояния (подсказка своих клавиш)."""
        return ""

    # --- события -> эффекты ---

    def update(self, ui: UI, view: Any, now: int) -> None:
        """Состояние на момент now: новый бой, расстановка, эффекты наступивших событий, камера."""
        self.t, self.view = ui.t, view
        sim = view.sim
        if sim is not self._sim or now - self._prev_frame > SKIP_BACKLOG_MS:
            if sim is not self._sim:
                self.reset()
            self._sim = sim
            self._shown_until = now
            self.hp = {uid: unit.hp for uid, unit in sim.units.items()}
            self.dead = {uid for uid, unit in sim.units.items() if not unit.is_alive}
        self._prev_frame = now
        self.layout(sim)
        for when, ev in view.timeline:
            if self._shown_until < when <= now:
                self.spawn(view, ev, when)
        self._shown_until = max(self._shown_until, now)
        self.camera_view.update(now)

    def spawn(self, view: Any, ev: Any, when: int) -> None:
        """Общие эффекты события; наследник добавляет свои движения и визуал навыков."""
        fx, t, db = self.fx, self.t, view.db
        if isinstance(ev, DamageDealt):
            pos = self.point(ev.target)
            fx.hits[ev.target] = when
            self.hp[ev.target] = ev.hp_left
            if self.is_periodic(ev, db):
                look = DOT_VISUALS.get(ev.cause, "dark")
                fx.burst(when, pos, ELEMENT_COLORS[look], 12, 1.4, 600, 3, up=1.2,
                         shape="bubble" if look == "poison" else "glow")
            head = self.point(ev.target, "head")
            size = 1.4 if ev.crit else 1.0
            fx.add(FloatText(when, 1000, head, str(ev.amount), (255, 90, 70) if not ev.crit else (255, 230, 80),
                             int(40 * size), 44, numbers=True))
            if ev.crit:
                self.sprite("crit", when, pos, 1.2)
                fx.add(FloatText(when, 900, (head[0], head[1] + 40, head[2]), t("crit").upper() + "!", (255, 230, 80), 22, 20))
                fx.add(Flash(when, 160, (255, 240, 200), 0.35))
                fx.shake(when, 300, 7)
            if ev.guarded:
                fx.add(Ring(when, 450, pos, ELEMENT_COLORS["guard"], 20, 55, 5))
                fx.add(FloatText(when, 800, self.point(ev.target, "feet"), t("guarded").upper(), ELEMENT_COLORS["guard"], 14, 10))

        elif isinstance(ev, AttackMissed):
            pos = self.point(ev.target)
            f = self.facing(ev.source)
            fx.add(Thrust(when, 260, (pos[0] + 30 * f, pos[1], pos[2]), (160, 160, 170), f))
            fx.add(FloatText(when, 900, self.point(ev.target, "head"), "MISS", (200, 200, 210), 22, 30))

        elif isinstance(ev, Healed):
            self.hp[ev.target] = ev.hp_left
            if ev.amount <= 0:
                return  # лечить было нечего: эффект не нужен
            fx.rise(when, self.point(ev.target, "feet"), 30, 120, ELEMENT_COLORS["heal"], 18,
                    "star" if ev.crit else "glow", 1.4, 900, 3)
            fx.add(FloatText(when, 1000, self.point(ev.target, "head"), f"+{ev.amount}", GREEN, 36, 40, numbers=True))

        elif isinstance(ev, EffectApplied):
            pos, feet = self.point(ev.target), self.point(ev.target, "feet")
            effect = db.effects.get(ev.effect_id)
            look = EFFECT_LOOKS.get(ev.effect_id) or ("buff" if effect and "buff" in effect.tags else "debuff")
            head = self.point(ev.target, "head")
            if self.sprite(EFFECT_SPRITES.get(look, ""), when, (head[0], head[1] + 20, head[2]) if look == "stun" else pos,
                           0.6 if look == "stun" else 1.0, ms=1200):
                pass                                   # спрайт эффекта вместо нарисованного кодом
            elif look == "stun":
                head = self.point(ev.target, "head")
                fx.burst(when, (head[0], head[1] + 14, head[2]), (255, 230, 90), 6, 1.0, 900, 3, gravity=0.0, shape="star")
            elif look == "poison":
                fx.rise(when, feet, 26, 110, ELEMENT_COLORS["poison"], 12, "bubble", 1.0, 900, 4)
            elif look == "fire":
                fx.rise(when, feet, 26, 110, ELEMENT_COLORS["fire"], 14, "glow", 1.6, 700, 3)
            elif look == "ice":
                fx.burst(when, pos, ELEMENT_COLORS["ice"], 10, 1.2, 900, 3, gravity=0.02, shape="flake")
            elif look == "buff":
                fx.rise(when, feet, 30, 120, ELEMENT_COLORS["buff"], 16, "glow", 1.5, 900, 3)
                fx.add(Ring(when, 500, feet, ELEMENT_COLORS["buff"], 15, 55, 3))
            else:
                fx.burst(when, pos, ELEMENT_COLORS["debuff"], 14, 1.6, 700, 3, gravity=0.06)
            name = t(effect.name) if effect else ev.effect_id
            color = ELEMENT_COLORS["buff"] if look == "buff" else (210, 170, 255)
            fx.add(FloatText(when + 120, 900, (pos[0], pos[1] - 26, pos[2]), name, color, 13, 16, False))

        elif isinstance(ev, EffectExpired):
            fx.burst(when, self.point(ev.target), (120, 120, 130), 6, 0.8, 400, 2, gravity=0.0)

        elif isinstance(ev, PassiveTriggered):
            passive = db.passives.get(ev.passive_id)
            fx.add(Ring(when, 600, self.point(ev.unit, "feet"), (255, 210, 110), 30, 80, 4))
            head = self.point(ev.unit, "head")
            fx.add(FloatText(when, 1100, (head[0], head[1] + 30, head[2]), t(passive.name) if passive else ev.passive_id,
                             (255, 214, 120), 14, 14))

        elif isinstance(ev, ResourceGained):
            fx.rise(when, self.point(ev.target, "feet"), 24, 100, AP_COLOR if ev.resource == "AP" else PP_COLOR,
                    10, "glow", 1.2, 700, 3)

        elif isinstance(ev, UnitDied):
            pos = self.point(ev.unit)
            self.dead.add(ev.unit)
            self.sprite("death_smoke", when + 300, pos, 1.2)
            color = (230, 190, 110) if self.facing(ev.unit) > 0 else (230, 120, 90)
            fx.burst(when, pos, color, 40, 4.0, 900, 3, gravity=0.08, spread=4)
            fx.burst(when, pos, (90, 90, 100), 24, 2.0, 1100, 4, gravity=-0.02, spread=5)

        elif isinstance(ev, RoundStarted):
            fx.add(FloatText(when, 900, self.screen_point(CENTER_X, 200), t("Round {n}", n=ev.round).upper(),
                             (255, 236, 170), 56, 0, numbers=True))

        elif isinstance(ev, BattleEnded):
            text = t("{winner} wins", winner=t(ev.winner_id)) if ev.winner_id else t("draw")
            fx.add(FloatText(when, 2500, self.screen_point(CENTER_X, 250), text.upper(), (255, 236, 170), 64, 10, numbers=True))

    def sprite(self, name: str, when: int, pos: World, scale: float = 1.0, facing: int = 1,
               ms: Optional[int] = None) -> bool:
        """Спрайтовый эффект name в точке pos, если он есть в assets/fx; иначе False."""
        library = self.sprites
        if library is None or name not in library:
            return False
        self.fx.add(SpriteEffect(when, library.duration(name, ms or SINGLE_MS), library, name, pos, scale, facing))
        return True

    def screen_point(self, x: float, y: float) -> World:
        """Мировая точка, которая видна в логической точке (x, y) поля (для надписей по центру)."""
        return 0.0, 0.0, 0.0

    @staticmethod
    def is_periodic(ev: DamageDealt, db: Any) -> bool:
        """Урон от эффекта (горение, яд), а не от навыка."""
        return ev.source is None or ev.cause in DOT_VISUALS or ev.cause in db.effects

    def impact(self, when: int, pos: World, visual: Visual, facing: int) -> None:
        """Общий эффект попадания в точке pos по виду навыка и стихии."""
        fx = self.fx
        delivery, element, physical = visual
        color = ELEMENT_COLORS.get(element or "steel", (255, 255, 255))
        if delivery == "melee":
            if physical == "piercing":
                fx.add(Thrust(when, 280, pos, ELEMENT_COLORS["steel"], facing))
            elif physical == "blunt":
                fx.add(Ring(when, 380, pos, (255, 240, 210), 10, 70, 6))
                fx.shake(when, 200, 4)
            else:
                fx.add(Slash(when, 320, pos, ELEMENT_COLORS["steel"], 48, facing))
            fx.burst(when, pos, (255, 230, 180), 14, 4.5, 380, 2, gravity=0.15, shape="spark")
            if element:
                fx.burst(when, pos, color, 20, 3.0, 600, 4, up=1.0)
                fx.add(Ring(when, 400, pos, color, 10, 60, 4))
        elif delivery == "arrow":
            fx.burst(when, pos, (255, 240, 200), 10, 3.5, 350, 2, gravity=0.12, shape="spark")
            if element:
                fx.burst(when, pos, color, 16, 2.5, 600, 4, up=0.8)
        elif element == "lightning":
            fx.add(Bolt(when, 300, pos, color, seed=when, lean=20 * facing))
            fx.add(Flash(when, 140, (180, 180, 255), 0.4))
            fx.burst(when, pos, color, 18, 4.0, 400, 2, gravity=0.0, shape="spark")
        elif element == "light":
            fx.add(Beam(when, 450, pos, color))
            fx.burst(when, pos, color, 16, 2.0, 700, 3, up=1.5)
        elif element == "ice":
            fx.burst(when, pos, color, 16, 3.5, 700, 3, gravity=0.1, shape="shard")
            fx.burst(when, pos, color, 10, 1.5, 900, 3, gravity=0.02, shape="flake")
        elif element == "fire":
            fx.add(Ring(when, 420, pos, color, 15, 75, 6))
            fx.burst(when, pos, color, 30, 4.0, 650, 4, up=1.0)
            fx.burst(when, pos, (255, 220, 120), 14, 2.0, 900, 2, gravity=-0.03)
            fx.shake(when, 220, 5)
        else:
            fx.add(Ring(when, 420, pos, color, 12, 65, 5))
            fx.burst(when, pos, color, 24, 3.5, 650, 4)

    # --- камера ---

    def camera(self, window_scale: float = 1.0, window_offset: tuple[float, float] = (0, 0)) -> Camera:
        return self.camera_view.camera(window_scale, window_offset)

    def handle_event(self, event: pygame.event.Event, pos: tuple[float, float], window_scale: float = 1.0) -> None:
        """Мышь и клавиши поля. pos: курсор в логических пикселях окна."""
        cam = self.camera_view
        if event.type == pygame.MOUSEWHEEL:
            cam.zoom_at(pos, event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3) and FIELD_RECT.collidepoint(pos):
            self.dragging = cam.zoom > 1
        elif event.type == pygame.MOUSEBUTTONUP and event.button in (1, 3):
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            if not cam.manual:
                cam.manual = True
            cam.pan(event.rel[0] / window_scale, event.rel[1] / window_scale)
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_HOME, pygame.K_0):
                cam.reset()
            elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                cam.zoom_at(FIELD_RECT.center, 1)
            elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                cam.zoom_at(FIELD_RECT.center, -1)
            elif event.key == pygame.K_c:
                cam.auto = not cam.auto

    # --- отрисовка ---

    def draw_battle(self, ui: UI, view: Any, autoplay: bool, now: int) -> None:
        """Строка состояния и лог; поле рисуется здесь же только без окна (native False),
        иначе его рисует draw_field прямо в окно после масштабирования интерфейса."""
        screen, t, font = ui.screen, ui.t, ui.fonts["main"]
        self.update(ui, view, now)
        sim = view.sim
        status = t("Round {n}   seed {seed}", n=view.round, seed=view.seed)
        if view.ended:
            winner = view.ended.winner_id
            status += "   " + (t("{winner} wins", winner=t(winner)) if winner else t("draw")).upper()
        if self.camera_view.manual:
            status += f"   x{self.camera_view.zoom:g}"
        status += self.status_note()
        status_img = font.render(status, True, YELLOW if view.ended else TEXT)
        screen.blit(status_img, status_img.get_rect(midtop=(CENTER_X, 31)))
        screen.blit(font.render(f"A: {t(sim.attacker.name)}", True, TEXT), (12, 31))
        title = font.render(f"B: {t(sim.defender.name)}", True, TEXT)
        screen.blit(title, (WIDTH - title.get_width() - 12, 31))
        self._draw_log(ui, view, autoplay)
        if not self.native:
            self.draw_field(screen, now, self.camera())

    def _draw_log(self, ui: UI, view: Any, autoplay: bool) -> None:
        screen, t, small = ui.screen, ui.t, ui.fonts["small"]
        panel = pygame.Rect(8, LOG_TOP, WIDTH - 16, HEIGHT - LOG_TOP - 8)
        pygame.draw.rect(screen, PANEL, panel)
        pygame.draw.rect(screen, DIM, panel, 1)
        auto = t("on") if autoplay else t("off")
        hint = small.render(t("SPACE step   A auto [{auto}]   R restart   wheel zoom, drag to move", auto=auto), True, DIM)
        screen.blit(hint, (panel.right - hint.get_width() - 8, panel.y + 6))
        sim = view.sim
        name = lambda uid: f"{t(sim.units[uid].name)}({uid})"
        lines = [format_event(ev, name, t).strip() for ev in view.log[-LOG_LINES:]]
        lines = lines or [t("Press SPACE to step or A to autoplay.")]
        for i, line in enumerate(lines):
            color = TEXT if i == len(lines) - 1 else DIM
            width = panel.width - 16 - (hint.get_width() + 16 if i == 0 else 0)
            screen.blit(small.render(fit(small, line, width), True, color), (panel.x + 8, panel.y + 6 + i * LOG_LINE_H))
