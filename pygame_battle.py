"""Основа экранов боя: события симуляции -> эффекты по расписанию, зум, строка состояния и лог.

Экран только читает бой; в логику не вмешивается. Где стоит юнит и куда он смотрит,
решает наследник (point, facing, layout, draw_field). Здесь — общие эффекты событий,
одинаковые для любого вида юнитов: числа урона и лечения, промах, крит, блок, эффекты,
пассивки, раунд и конец боя, а также общий удар по стихии (impact).
"""
from __future__ import annotations

from typing import Any, Optional

import pygame

from game.definitions import PART_HEAL, SkillDefinition
from game.events import (
    AttackMissed,
    BattleEnded,
    DamageDealt,
    EffectApplied,
    EffectExpired,
    Healed,
    PassiveTriggered,
    ResourceGained,
    RoundStarted,
    UnitDied,
    format_event,
)
from game.unit import Unit
from pygame_fx import ELEMENT_COLORS, Beam, Bolt, Camera, Flash, FloatText, FxSystem, Ring, Slash, Thrust
from pygame_ui import DIM, GREEN, HEIGHT, PANEL, TEXT, UI, WIDTH, YELLOW, fit

CENTER_X = WIDTH // 2
FIELD_RECT = pygame.Rect(0, 52, WIDTH, 440)   # область поля в логических пикселях окна
FIELD_TOP = FIELD_RECT.top + 12
MAX_ZOOM = 3.0
ZOOM_STEP = 0.25
LOG_TOP = FIELD_RECT.bottom + 8
LOG_LINES = 5
LOG_LINE_H = 18
SKIP_BACKLOG_MS = 300      # после долгого перерыва старые события не проигрываются пачкой

AP_COLOR = (90, 160, 240)
PP_COLOR = (190, 120, 235)
ELEMENTS = ("lightning", "fire", "ice", "light", "dark", "poison")
PHYSICAL = ("slashing", "piercing", "blunt")
DOT_VISUALS = {"burn": "fire", "poison": "poison", "plague": "dark"}   # периодический урон эффектов
EFFECT_LOOKS = {"stun": "stun", "poison": "poison", "plague": "poison", "burn": "fire", "slow": "ice"}
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


class BattleScreen:
    """Вкладка боя. is_battle: на ней работают клавиши боя. Наследник задаёт, где стоят юниты."""

    is_battle = True

    def __init__(self) -> None:
        self.fx = FxSystem()
        self._sim: Any = None
        self._shown_until = 0               # события до этого момента уже показаны
        self._prev_frame = 0
        self.hp: dict[int, int] = {}        # HP, как в уже показанных событиях
        self.dead: set[int] = set()
        self.visuals: dict[int, Visual] = {}   # uid -> вид его последнего навыка
        self.view: Any = None
        self.t: Any = str
        self.native = False                 # поле рисуется отдельно, прямо в окно (draw_field)
        self.zoom = 1.0
        self.origin: tuple[float, float] = FIELD_RECT.topleft
        self.dragging = False

    # --- что задаёт наследник ---

    def layout(self, sim: Any) -> None:
        """Расставить юнитов боя sim."""

    def point(self, uid: int, on: str = "body") -> tuple[float, float]:
        """Точка юнита на поле: feet, body, head."""
        return CENTER_X, FIELD_RECT.centery

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
        """Состояние на момент now: новый бой, расстановка, эффекты наступивших событий."""
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
            size = 1.4 if ev.crit else 1.0
            fx.add(FloatText(when, 1000, (pos[0], pos[1] - 20), str(ev.amount), (255, 90, 70) if not ev.crit else (255, 230, 80),
                             int(40 * size), 44, numbers=True))
            if ev.crit:
                fx.add(FloatText(when, 900, (pos[0], pos[1] - 60), t("crit").upper() + "!", (255, 230, 80), 22, 20))
                fx.add(Flash(when, 160, (255, 240, 200), 0.35))
                fx.shake(when, 300, 7)
            if ev.guarded:
                fx.add(Ring(when, 450, pos, ELEMENT_COLORS["guard"], 20, 55, 5, 1.0))
                fx.add(FloatText(when, 800, (pos[0], pos[1] + 30), t("guarded").upper(), ELEMENT_COLORS["guard"], 14, 10))

        elif isinstance(ev, AttackMissed):
            pos = self.point(ev.target)
            fx.add(Thrust(when, 260, (pos[0] + 30 * self.facing(ev.source), pos[1]), (160, 160, 170), self.facing(ev.source)))
            fx.add(FloatText(when, 900, (pos[0], pos[1] - 30), "MISS", (200, 200, 210), 22, 30))

        elif isinstance(ev, Healed):
            pos = self.point(ev.target)
            self.hp[ev.target] = ev.hp_left
            if ev.amount <= 0:
                return  # лечить было нечего: эффект не нужен
            rect = pygame.Rect(0, 0, 60, 90)
            rect.center = (int(pos[0]), int(pos[1]))
            fx.rise(when, rect, ELEMENT_COLORS["heal"], 18, "star" if ev.crit else "glow", 1.4, 900, 3)
            fx.add(FloatText(when, 1000, (pos[0], pos[1] - 20), f"+{ev.amount}", GREEN, 36, 40, numbers=True))

        elif isinstance(ev, EffectApplied):
            pos = self.point(ev.target)
            effect = db.effects.get(ev.effect_id)
            look = EFFECT_LOOKS.get(ev.effect_id) or ("buff" if effect and "buff" in effect.tags else "debuff")
            rect = pygame.Rect(0, 0, 60, 80)
            rect.center = (int(pos[0]), int(pos[1]))
            if look == "stun":
                head = self.point(ev.target, "head")
                fx.burst(when, (head[0], head[1] - 10), (255, 230, 90), 6, 1.0, 900, 3, gravity=0.0, shape="star")
            elif look == "poison":
                fx.rise(when, rect, ELEMENT_COLORS["poison"], 12, "bubble", 1.0, 900, 4)
            elif look == "fire":
                fx.rise(when, rect, ELEMENT_COLORS["fire"], 14, "glow", 1.6, 700, 3)
            elif look == "ice":
                fx.burst(when, pos, ELEMENT_COLORS["ice"], 10, 1.2, 900, 3, gravity=0.02, shape="flake")
            elif look == "buff":
                fx.rise(when, rect, ELEMENT_COLORS["buff"], 16, "glow", 1.5, 900, 3)
                fx.add(Ring(when, 500, self.point(ev.target, "feet"), ELEMENT_COLORS["buff"], 15, 55, 3, 0.35))
            else:
                fx.burst(when, pos, ELEMENT_COLORS["debuff"], 14, 1.6, 700, 3, gravity=0.06)
            name = t(effect.name) if effect else ev.effect_id
            color = ELEMENT_COLORS["buff"] if look == "buff" else (210, 170, 255)
            fx.add(FloatText(when + 120, 900, (pos[0], pos[1] + 26), name, color, 13, 16, False))

        elif isinstance(ev, EffectExpired):
            fx.burst(when, self.point(ev.target), (120, 120, 130), 6, 0.8, 400, 2, gravity=0.0)

        elif isinstance(ev, PassiveTriggered):
            pos = self.point(ev.unit)
            passive = db.passives.get(ev.passive_id)
            fx.add(Ring(when, 600, self.point(ev.unit, "feet"), (255, 210, 110), 30, 80, 4, 0.35))
            head = self.point(ev.unit, "head")
            fx.add(FloatText(when, 1100, (head[0], head[1] - 30), t(passive.name) if passive else ev.passive_id,
                             (255, 214, 120), 14, 14))

        elif isinstance(ev, ResourceGained):
            rect = pygame.Rect(0, 0, 50, 70)
            pos = self.point(ev.target)
            rect.center = (int(pos[0]), int(pos[1]))
            fx.rise(when, rect, AP_COLOR if ev.resource == "AP" else PP_COLOR, 10, "glow", 1.2, 700, 3)

        elif isinstance(ev, UnitDied):
            pos = self.point(ev.unit)
            self.dead.add(ev.unit)
            color = (230, 190, 110) if self.facing(ev.unit) > 0 else (230, 120, 90)
            fx.burst(when, pos, color, 40, 4.0, 900, 3, gravity=0.08, spread=4)
            fx.burst(when, pos, (90, 90, 100), 24, 2.0, 1100, 4, gravity=-0.02, spread=5)

        elif isinstance(ev, RoundStarted):
            fx.add(FloatText(when, 900, (CENTER_X, 200), t("Round {n}", n=ev.round).upper(), (255, 236, 170),
                             56, 0, numbers=True))

        elif isinstance(ev, BattleEnded):
            text = t("{winner} wins", winner=t(ev.winner_id)) if ev.winner_id else t("draw")
            fx.add(FloatText(when, 2500, (CENTER_X, 250), text.upper(), (255, 236, 170), 64, 10, numbers=True))

    @staticmethod
    def is_periodic(ev: DamageDealt, db: Any) -> bool:
        """Урон от эффекта (горение, яд), а не от навыка."""
        return ev.source is None or ev.cause in DOT_VISUALS or ev.cause in db.effects

    def impact(self, when: int, pos: tuple[float, float], visual: Visual, facing: int) -> None:
        """Общий эффект попадания в точке pos по виду навыка и стихии."""
        fx = self.fx
        delivery, element, physical = visual
        color = ELEMENT_COLORS.get(element or "steel", (255, 255, 255))
        if delivery == "melee":
            if physical == "piercing":
                fx.add(Thrust(when, 280, pos, ELEMENT_COLORS["steel"], facing))
            elif physical == "blunt":
                fx.add(Ring(when, 380, pos, (255, 240, 210), 10, 70, 6, 0.8))
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
            fx.add(Bolt(when, 300, (pos[0] + 20 * facing, FIELD_TOP - 10), pos, color, seed=when))
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

    # --- зум и перетаскивание ---

    def view_size(self) -> tuple[float, float]:
        """Сколько логических пикселей поля видно при текущем зуме."""
        return FIELD_RECT.width / self.zoom, FIELD_RECT.height / self.zoom

    def _clamp(self) -> None:
        vw, vh = self.view_size()
        x = min(max(self.origin[0], FIELD_RECT.left), FIELD_RECT.right - vw)
        y = min(max(self.origin[1], FIELD_RECT.top), FIELD_RECT.bottom - vh)
        self.origin = (x, y)

    def zoom_at(self, pos: tuple[float, float], steps: float) -> None:
        """Зум колесом мыши: точка поля под курсором (pos в логических пикселях окна) остаётся на месте."""
        if not FIELD_RECT.collidepoint(pos):
            return
        fx = self.origin[0] + (pos[0] - FIELD_RECT.left) / self.zoom
        fy = self.origin[1] + (pos[1] - FIELD_RECT.top) / self.zoom
        self.zoom = min(MAX_ZOOM, max(1.0, round((self.zoom + steps * ZOOM_STEP) * 4) / 4))
        self.origin = (fx - (pos[0] - FIELD_RECT.left) / self.zoom, fy - (pos[1] - FIELD_RECT.top) / self.zoom)
        self._clamp()

    def pan(self, dx: float, dy: float) -> None:
        """Сдвиг поля на (dx, dy) логических пикселей окна (мышь тянет поле за собой)."""
        self.origin = (self.origin[0] - dx / self.zoom, self.origin[1] - dy / self.zoom)
        self._clamp()

    def reset_zoom(self) -> None:
        self.zoom, self.origin = 1.0, FIELD_RECT.topleft

    def handle_event(self, event: pygame.event.Event, pos: tuple[float, float], window_scale: float = 1.0) -> None:
        """Мышь и клавиши поля. pos: курсор в логических пикселях окна."""
        if event.type == pygame.MOUSEWHEEL:
            self.zoom_at(pos, event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3) and FIELD_RECT.collidepoint(pos):
            self.dragging = self.zoom > 1
        elif event.type == pygame.MOUSEBUTTONUP and event.button in (1, 3):
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.pan(event.rel[0] / window_scale, event.rel[1] / window_scale)
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_HOME, pygame.K_0):
                self.reset_zoom()
            elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                self.zoom_at(FIELD_RECT.center, 1)
            elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.zoom_at(FIELD_RECT.center, -1)

    def camera(self, window_scale: float = 1.0, window_offset: tuple[float, float] = (0, 0)) -> Camera:
        """Камера поля: размер окна x зум; область поля в окне."""
        clip = pygame.Rect(round(window_offset[0] + FIELD_RECT.left * window_scale),
                           round(window_offset[1] + FIELD_RECT.top * window_scale),
                           round(FIELD_RECT.width * window_scale), round(FIELD_RECT.height * window_scale))
        return Camera(window_scale * self.zoom, self.origin, clip.topleft, clip)

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
        if self.zoom > 1:
            status += f"   x{self.zoom:g}"
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
