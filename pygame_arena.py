"""Вкладка Arena: бой картами юнитов. Главное на экране — эффекты атак.

Карты стоят по формации и повёрнуты к противнику. События боя показываются по
расписанию BattleView.timeline: замах и полёт снаряда, попадания, эффекты, гибель.
Экран только читает бой; в логику не вмешивается.
"""
from __future__ import annotations

from typing import Any, Optional

import pygame

from game.definitions import PART_HEAL, SkillDefinition
from game.events import (
    AttackMissed,
    BattleEnded,
    Covered,
    DamageDealt,
    EffectApplied,
    EffectExpired,
    Healed,
    PassiveTriggered,
    ResourceGained,
    RoundStarted,
    SkillUsed,
    UnitDied,
    format_event,
)
from game.unit import Unit
from pygame_cards import CardArt
from pygame_fx import (
    ELEMENT_COLORS,
    Beam,
    Camera,
    Bolt,
    Flash,
    FloatText,
    FxSystem,
    Projectile,
    Ring,
    Slash,
    Thrust,
    add_glow,
    fx_font,
)
from pygame_ui import DIM, GREEN, HEIGHT, PANEL, RED, TEXT, UI, WIDTH, YELLOW, fit

CENTER_X = WIDTH // 2
FIELD_RECT = pygame.Rect(0, 52, WIDTH, 440)   # область поля в логических пикселях окна
FIELD_TOP = 64
MAX_ZOOM = 3.0
ZOOM_STEP = 0.25
FIELD_BOTTOM = 492
CENTER_GAP = 46            # полоса между отрядами
MAX_CARD_H = 150
CARD_RATIO = 0.72          # ширина карты к высоте (до поворота)
TRAVEL_MS = 380            # полёт снаряда и выпад: столько же, сколько BEAT_MS["SkillUsed"]
LOG_TOP = FIELD_BOTTOM + 8
LOG_LINES = 5
LOG_LINE_H = 18
SKIP_BACKLOG_MS = 300      # после долгого перерыва старые события не проигрываются пачкой

HP_BACK = (60, 30, 34)
AP_COLOR = (90, 160, 240)
PP_COLOR = (190, 120, 235)
DEAD_TEXT = (120, 120, 125)
ELEMENTS = ("lightning", "fire", "ice", "light", "dark", "poison")
PHYSICAL = ("slashing", "piercing", "blunt")
DOT_VISUALS = {"burn": "fire", "poison": "poison", "plague": "dark"}   # периодический урон эффектов
EFFECT_LOOKS = {"stun": "stun", "poison": "poison", "plague": "poison", "burn": "fire", "slow": "ice"}


def skill_visual(skill: Optional[SkillDefinition], user: Optional[Unit]) -> tuple[str, Optional[str], str]:
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


class ArenaScreen:
    """Вкладка боя картами. is_battle: на ней работают клавиши боя."""

    is_battle = True

    def __init__(self, art: Optional[CardArt] = None):
        self.art = art or CardArt()
        self.fx = FxSystem()
        self._sim: Any = None
        self._shown_until = 0               # события до этого момента уже показаны
        self._prev_frame = 0
        self._hp: dict[int, int] = {}       # HP на картах: меняется в момент показа удара
        self._dead: set[int] = set()
        self._visuals: dict[int, tuple[str, Optional[str], str]] = {}   # uid -> вид его последнего навыка
        self._background: Optional[pygame.Surface] = None
        self._view: Any = None
        self._t: Any = str
        self.places: dict = {}
        self.native = False                 # поле рисуется отдельно, прямо в окно (draw_field)
        self.zoom = 1.0
        self.origin: tuple[float, float] = FIELD_RECT.topleft
        self.dragging = False

    # --- раскладка ---

    def layout(self, sim: Any) -> dict[int, tuple[tuple[int, int], tuple[int, int], str]]:
        """uid -> (центр карты, размер карты до поворота, сторона)."""
        result = {}
        for squad, side in ((sim.attacker, "left"), (sim.defender, "right")):
            formation = squad.formation
            rows, cols = formation.rows, formation.cols
            col_step = (FIELD_BOTTOM - FIELD_TOP) / cols
            card_h = int(min(MAX_CARD_H, col_step * 0.8))
            card_w = int(card_h * CARD_RATIO)
            row_step = min(card_w * 1.15, (CENTER_X - CENTER_GAP - 20) / rows)
            for unit in formation.units:
                row, col = formation.position_of(unit.uid)
                offset = CENTER_GAP + card_w * 0.45 + row * row_step + col * 8   # колонны чуть уходят вглубь
                x = CENTER_X - offset if side == "left" else CENTER_X + offset
                y = FIELD_TOP + col_step * (col + 0.5)
                result[unit.uid] = ((int(x), int(y)), (card_w, card_h), side)
        return result

    # --- события -> эффекты ---

    def _sync(self, view: Any, now: int) -> None:
        sim = view.sim
        if sim is not self._sim or now - self._prev_frame > SKIP_BACKLOG_MS:
            if sim is not self._sim:
                self.fx.clear()
                self._visuals.clear()
            self._sim = sim
            self._shown_until = now
            self._hp = {uid: unit.hp for uid, unit in sim.units.items()}
            self._dead = {uid for uid, unit in sim.units.items() if not unit.is_alive}
        self._prev_frame = now

    def _play(self, ui: UI, view: Any, places: dict, now: int) -> None:
        for when, ev in view.timeline:
            if self._shown_until < when <= now:
                self._spawn(ui, view, ev, when, places)
        self._shown_until = max(self._shown_until, now)

    def _spawn(self, ui: UI, view: Any, ev: Any, when: int, places: dict) -> None:
        fx, t, units, db = self.fx, ui.t, view.sim.units, view.db
        center = lambda uid: places[uid][0] if uid in places else (CENTER_X, 260)
        top = lambda uid: (center(uid)[0], center(uid)[1] - places[uid][1][1] // 2 if uid in places else 200)
        facing = lambda uid: 1 if uid in places and places[uid][2] == "left" else -1

        if isinstance(ev, SkillUsed):
            skill = db.skills.get(ev.skill_id)
            visual = skill_visual(skill, units.get(ev.user))
            self._visuals[ev.user] = visual
            delivery, element, _ = visual
            source, target = center(ev.user), center(ev.target)
            color = ELEMENT_COLORS.get(element or "steel", (255, 255, 255))
            name = t(skill.name) if skill else ev.skill_id
            fx.add(FloatText(when, 900, (top(ev.user)[0], top(ev.user)[1] - 8), name, (255, 236, 170), 14, 18, False))
            if delivery in ("melee", "arrow", "magic") and ev.target != ev.user:
                fx.card_lunges[ev.user] = (when, target)
            if delivery == "arrow":
                fx.add(Projectile(when, TRAVEL_MS, source, target, "arrow", color, arc=40))
            elif delivery == "magic" and element not in ("lightning", "light"):
                fx.add(Projectile(when, TRAVEL_MS, source, target, "shards" if element == "ice" else "orb", color))
                fx.burst(when, source, color, 10, 1.5, 400, 3)
            elif delivery in ("magic", "heal", "support"):
                fx.add(Ring(when, 420, source, color, 10, 60, 3, 0.5))      # каст: волна вокруг заклинателя
                fx.burst(when, source, color, 12, 1.2, 500, 3, up=1.0)

        elif isinstance(ev, DamageDealt):
            pos = center(ev.target)
            fx.card_hits[ev.target] = when
            self._hp[ev.target] = ev.hp_left
            if ev.cause in DOT_VISUALS or ev.cause in db.effects:
                look = DOT_VISUALS.get(ev.cause, "dark")
                fx.burst(when, pos, ELEMENT_COLORS[look], 12, 1.4, 600, 3, up=1.2,
                         shape="bubble" if look == "poison" else "glow")
            else:
                self._impact(when, pos, self._visuals.get(ev.source, ("melee", None, "slashing")), facing(ev.source))
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
            pos = center(ev.target)
            fx.add(Thrust(when, 260, (pos[0] + 30 * facing(ev.source), pos[1]), (160, 160, 170), facing(ev.source)))
            fx.add(FloatText(when, 900, (pos[0], pos[1] - 30), "MISS", (200, 200, 210), 22, 30))

        elif isinstance(ev, Healed):
            pos = center(ev.target)
            self._hp[ev.target] = ev.hp_left
            if ev.amount <= 0:
                return  # лечить было нечего: эффект не нужен
            rect = pygame.Rect(0, 0, 60, 90)
            rect.center = pos
            fx.rise(when, rect, ELEMENT_COLORS["heal"], 18, "star" if ev.crit else "glow", 1.4, 900, 3)
            fx.add(Ring(when, 500, (pos[0], pos[1] + 40), ELEMENT_COLORS["heal"], 15, 50, 3))
            fx.add(FloatText(when, 1000, (pos[0], pos[1] - 20), f"+{ev.amount}", GREEN, 36, 40, numbers=True))

        elif isinstance(ev, EffectApplied):
            pos = center(ev.target)
            effect = db.effects.get(ev.effect_id)
            look = EFFECT_LOOKS.get(ev.effect_id) or ("buff" if effect and "buff" in effect.tags else "debuff")
            rect = pygame.Rect(0, 0, 60, 80)
            rect.center = pos
            if look == "stun":
                fx.burst(when, (pos[0], pos[1] - 50), (255, 230, 90), 6, 1.0, 900, 3, gravity=0.0, shape="star")
            elif look == "poison":
                fx.rise(when, rect, ELEMENT_COLORS["poison"], 12, "bubble", 1.0, 900, 4)
            elif look == "fire":
                fx.rise(when, rect, ELEMENT_COLORS["fire"], 14, "glow", 1.6, 700, 3)
            elif look == "ice":
                fx.burst(when, pos, ELEMENT_COLORS["ice"], 10, 1.2, 900, 3, gravity=0.02, shape="flake")
            elif look == "buff":
                fx.rise(when, rect, ELEMENT_COLORS["buff"], 16, "glow", 1.5, 900, 3)
                fx.add(Ring(when, 500, (pos[0], pos[1] + 40), ELEMENT_COLORS["buff"], 15, 55, 3))
            else:
                fx.burst(when, pos, ELEMENT_COLORS["debuff"], 14, 1.6, 700, 3, gravity=0.06)
            name = t(effect.name) if effect else ev.effect_id
            color = ELEMENT_COLORS["buff"] if look == "buff" else (210, 170, 255)
            fx.add(FloatText(when + 120, 900, (pos[0], pos[1] + 26), name, color, 13, 16, False))

        elif isinstance(ev, EffectExpired):
            fx.burst(when, center(ev.target), (120, 120, 130), 6, 0.8, 400, 2, gravity=0.0)

        elif isinstance(ev, Covered):
            protector, covered = center(ev.protector), center(ev.target)
            fx.card_lunges[ev.protector] = (when, covered)
            for pos in (protector, covered):
                fx.add(Ring(when, 500, pos, ELEMENT_COLORS["guard"], 20, 60, 5, 1.0))
            fx.add(FloatText(when, 900, (protector[0], protector[1] - 50), t("cover").upper(), ELEMENT_COLORS["guard"], 22, 20))

        elif isinstance(ev, PassiveTriggered):
            pos = center(ev.unit)
            passive = db.passives.get(ev.passive_id)
            fx.add(Ring(when, 600, pos, (255, 210, 110), 30, 80, 4, 0.9))
            fx.add(FloatText(when, 1100, (pos[0], pos[1] - 70), t(passive.name) if passive else ev.passive_id,
                             (255, 214, 120), 14, 14))

        elif isinstance(ev, ResourceGained):
            rect = pygame.Rect(0, 0, 50, 70)
            rect.center = center(ev.target)
            fx.rise(when, rect, AP_COLOR if ev.resource == "AP" else PP_COLOR, 10, "glow", 1.2, 700, 3)

        elif isinstance(ev, UnitDied):
            pos = center(ev.unit)
            self._dead.add(ev.unit)
            side = places[ev.unit][2] if ev.unit in places else "left"
            color = (230, 190, 110) if side == "left" else (230, 120, 90)
            fx.burst(when, pos, color, 40, 4.0, 900, 3, gravity=0.08, spread=4)
            fx.burst(when, pos, (90, 90, 100), 24, 2.0, 1100, 4, gravity=-0.02, spread=5)

        elif isinstance(ev, RoundStarted):
            fx.add(FloatText(when, 900, (CENTER_X, 200), t("Round {n}", n=ev.round).upper(), (255, 236, 170),
                             56, 0, numbers=True))

        elif isinstance(ev, BattleEnded):
            text = t("{winner} wins", winner=t(ev.winner_id)) if ev.winner_id else t("draw")
            fx.add(FloatText(when, 2500, (CENTER_X, 250), text.upper(), (255, 236, 170), 64, 10, numbers=True))

    def _impact(self, when: int, pos: tuple[int, int], visual: tuple[str, Optional[str], str], facing: int) -> None:
        """Эффект попадания по цели в точке pos."""
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
        """Мышь и клавиши арены. pos: курсор в логических пикселях окна."""
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

    def draw_battle(self, ui: UI, view: Any, autoplay: bool, now: int, popup_ms: int, popup_rise: int) -> None:
        """Логическая часть: события -> эффекты, строка состояния и лог.

        Поле рисуется здесь же только без окна высокого разрешения (native False);
        иначе его рисует draw_field прямо в окно после масштабирования интерфейса.
        """
        screen, t, font = ui.screen, ui.t, ui.fonts["main"]
        sim = view.sim
        self._t = t
        self._sync(view, now)
        self.places = self.layout(sim)
        self._play(ui, view, self.places, now)
        self._view = view

        status = t("Round {n}   seed {seed}", n=view.round, seed=view.seed)
        if view.ended:
            winner = view.ended.winner_id
            status += "   " + (t("{winner} wins", winner=t(winner)) if winner else t("draw")).upper()
        if self.zoom > 1:
            status += f"   x{self.zoom:g}"
        status_img = font.render(status, True, YELLOW if view.ended else TEXT)
        screen.blit(status_img, status_img.get_rect(midtop=(CENTER_X, 31)))
        screen.blit(font.render(f"A: {t(sim.attacker.name)}", True, TEXT), (12, 31))
        title = font.render(f"B: {t(sim.defender.name)}", True, TEXT)
        screen.blit(title, (WIDTH - title.get_width() - 12, 31))
        self._draw_log(ui, view, autoplay)
        if not self.native:
            self.draw_field(screen, now, self.camera())

    def draw_field(self, target: pygame.Surface, now: int, cam: Camera) -> None:
        """Поле боя: фон, карты и эффекты, в пикселях окна через камеру."""
        view = self._view
        if view is None:
            return
        previous_clip = target.get_clip()
        target.set_clip(cam.clip)
        shake = self.fx.screen_offset(now)
        cam = Camera(cam.scale, (cam.origin[0] - shake[0], cam.origin[1] - shake[1]), cam.offset, cam.clip)
        self._draw_background(target, cam)
        places = self.places
        order = sorted(places, key=lambda uid: (uid == view.current_uid, places[uid][0][1]))
        for uid in order:
            self._draw_card(target, view, view.sim.units[uid], places[uid], now, cam)
        self.fx.draw(target, now, cam)
        target.set_clip(previous_clip)

    def _draw_background(self, target: pygame.Surface, cam: Camera) -> None:
        clip = cam.clip
        key = clip.size
        if self._background is None or self._background.get_size() != key:
            bg = pygame.Surface(key)
            for y in range(key[1]):
                k = y / key[1]
                pygame.draw.line(bg, (int(26 + 22 * k), int(30 + 24 * k), int(44 + 10 * k)), (0, y), (key[0], y))
            self._background = bg
        target.blit(self._background, clip.topleft)
        # Тёплая полоса между отрядами двигается вместе с полем при зуме.
        x, _ = cam.p(CENTER_X, 0)
        band = pygame.Surface((max(2, int(cam.s(120))), clip.height))
        for i in range(band.get_width()):
            k = (1 - abs(i - band.get_width() / 2) / (band.get_width() / 2)) ** 2
            pygame.draw.line(band, (int(16 * k), int(14 * k), int(9 * k)), (i, 0), (i, clip.height))
        target.blit(band, (x - band.get_width() // 2, clip.top), special_flags=pygame.BLEND_RGB_ADD)

    def _card_font(self, size: float) -> pygame.font.Font:
        return fx_font(max(8, round(size)))

    def _draw_card(self, target: pygame.Surface, view: Any, unit: Unit, place: tuple, now: int, cam: Camera) -> None:
        t = self._t
        (cx, cy), size, side = place
        dead = unit.uid in self._dead
        dx, dy, flash = self.fx.card_offset(unit.uid, now, (cx, cy))
        current = unit.uid == view.current_uid and not dead
        lift = -8 if current else 0
        # Размер карты в пикселях окна; масштаб округлён, чтобы кэш повёрнутых карт не разрастался.
        k = round(cam.scale * 8) / 8
        px_size = (max(8, round(size[0] * k)), max(10, round(size[1] * k)))
        font = self._card_font(11 * k)
        card = self.art.tilted(unit.definition.id, t(unit.name), unit.state.level, side, px_size, font, dead)
        rect = card.get_rect(center=cam.p(cx + dx, cy + dy + lift))
        if current:
            add_glow(target, rect.center, (120, 100, 40), max(rect.size) * 0.8, 1.0)
        target.blit(card, rect)
        if flash > 0:
            white = self.art.silhouette(card).copy()
            white.set_alpha(int(220 * flash))
            target.blit(white, rect)
        if dead:
            return

        # HP, AP, PP — плоско под картой, чтобы читались.
        bar = pygame.Rect(0, 0, round(cam.s(size[0] - 6)), max(2, round(cam.s(6))))
        bar.midtop = (rect.centerx, rect.bottom + round(cam.s(3)))
        pygame.draw.rect(target, HP_BACK, bar)
        hp, max_hp = self._hp.get(unit.uid, unit.hp), max(1, unit.max_hp)
        fill = bar.copy()
        fill.width = round(bar.width * max(0, hp) / max_hp)
        pygame.draw.rect(target, GREEN if hp * 3 > max_hp else RED, fill)
        pips = [(AP_COLOR, i < unit.ap.current) for i in range(unit.ap.max)]
        pips += [(PP_COLOR, i < unit.pp.current) for i in range(unit.pp.max)]
        step, pip = cam.s(8), max(2, round(cam.s(6)))
        px = rect.centerx - len(pips) * step / 2
        for i, (color, filled) in enumerate(pips):
            box = pygame.Rect(round(px + i * step), bar.bottom + round(cam.s(3)), pip, pip)
            pygame.draw.rect(target, color, box, 0 if filled else 1)
        names = [t(e.definition.name) for e in unit.effects]
        if names:
            small = self._card_font(12 * cam.scale)
            line = small.render(fit(small, ", ".join(names), round(cam.s(size[0] + 30))), True, YELLOW)
            target.blit(line, line.get_rect(midbottom=(rect.centerx, rect.top - round(cam.s(2)))))

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
