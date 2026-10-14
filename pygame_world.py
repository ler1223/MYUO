"""Вкладка World: открытый мир, как в Unicorn Overlord.

Герой (всадник) свободно ездит по карте в реальном времени: WASD или стрелки, Shift — быстрее.
Камера смотрит сверху-сбоку и плавно едет за ним; земля лежит в перспективе (движок 2.5D),
поверх — объекты карты и отряды врага, отсортированные по глубине. E — взаимодействие
(открыть сундук, отдохнуть в городе или форте, осмотреть руины), I — инвентарь и основной
отряд (снаряжение надевается из инвентаря), M — мини-карта.

Логика мира — game.overworld (без pygame); здесь ввод, отрисовка и связь с боем: когда враг
настигает героя, окно запускает бой на вкладке Stage (start_battle), а после него
(finish_battle) применяет итог.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable, Optional

import pygame

from engine.camera import Camera
from engine.fx import add_glow, fx_font
from engine.projection import Projection
from engine.render import GROUND, OVERLAY, UPRIGHT, Part, View, draw_parts
from game.overworld import SAFE_KINDS, Interaction, Overworld, WorldDef, WorldObject
from pygame_stage import ImageBank, SpriteBank, placeholder
from pygame_ui import DIM, GREEN, HEIGHT, PANEL, RED, TEXT, UI, WIDTH, YELLOW

ROOT = Path(__file__).resolve().parent
WORLD_IMAGES = ROOT / "assets" / "world"
GROUND_DIR = ROOT / "assets" / "grounds"

FIELD = pygame.Rect(0, 52, WIDTH, 520)        # поле мира в логических пикселях окна
FOOTER_Y = FIELD.bottom + 6
# Камера: герой стоит на глубине NEAR от камеры; дальше — вверх по экрану.
PROJECTION = Projection(horizon=-500, ground=760, focal=900, center_x=WIDTH / 2)
NEAR = 320
FOLLOW_MS = 160            # чем меньше, тем плотнее камера держится за героем
GROUND_RES = 1.0           # пикселей карты земли на единицу мира
TILE = 180                 # сторона плитки земли, единицы мира
HUMAN = 95                 # рост человека на карте мира (спрайты здесь мельче, чем в бою)
HERO_CLASS = "high_lord"   # чей спрайт у героя на карте (конный лорд)
VOID = (18, 22, 30)        # за краем карты
HAZE = (150, 170, 200)     # дымка вдали
HAZE_TOP = 0.45            # насколько сильна дымка у верхнего края поля
LOCKED_FOG = (12, 16, 26, 165)
ENEMY_BORDER = (200, 70, 60)
MINIMAP_W = 190
MESSAGE_MS = 3500
SAVE_EVERY_MS = 3000
NONE_ITEM = "__none__"     # в списке снаряжения: снять предмет
PANEL_RECT = pygame.Rect(30, 60, WIDTH - 60, HEIGHT - 110)
INV_ROW = 22
SQUAD_ROW = 52


class WorldScreen:
    """Экран мира. start_battle(enemy_id) — окно начинает бой; finish_battle() — забрать итог."""

    is_battle = False

    def __init__(self, world: WorldDef, save_path: Optional[Path] = None, seed: int = 1):
        self.world = world
        self.state = Overworld(world, seed)
        self.save_path = save_path
        if save_path is not None and Path(save_path).exists():
            try:
                self.state.load(save_path)
            except (OSError, ValueError, KeyError, TypeError):
                pass                           # чужое или битое сохранение: новая игра
        self.cam: tuple[float, float] = self.state.hero
        self.bank = SpriteBank()
        self.images = ImageBank(WORLD_IMAGES)
        self.panel = False                     # открыт инвентарь и отряд
        self.minimap = True
        self.native = False
        self.message = ""
        self.message_until = 0
        self.pending: Optional[str] = None     # бой с этим отрядом идёт на вкладке Stage
        self.start_battle: Callable[[str], None] = lambda enemy_id: None
        self.finish_battle: Callable[[], Optional[bool]] = lambda: None   # True победа, False поражение, None — не закончен
        self.on_change: Callable[[], None] = lambda: None                 # снаряжение отряда изменилось
        self.app: Any = None
        self.t: Any = str
        self._last = 0
        self._saved_at = 0
        self._ground_key: Any = None
        self._ground_map: Optional[pygame.Surface] = None
        self._minimap: Optional[pygame.Surface] = None
        self._frame_key: Any = None
        self._frame: Optional[pygame.Surface] = None
        self._haze: Optional[pygame.Surface] = None
        self._enemy_prev: dict[str, tuple[float, float]] = {}
        self._enemy_facing: dict[str, int] = {}

    # --- ввод и шаг ---

    def handle_event(self, event: pygame.event.Event, pos: tuple[float, float], window_scale: float = 1.0) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_i, pygame.K_TAB):
            self.panel = not self.panel
        elif self.panel:
            return
        elif event.key == pygame.K_e:
            self.interact()
        elif event.key == pygame.K_m:
            self.minimap = not self.minimap

    @staticmethod
    def direction_from_keys(pressed: Any) -> tuple[float, float]:
        """W/стрелка вверх — вглубь карты (+z), S — к зрителю, A/D — влево и вправо."""
        dx = (pressed[pygame.K_d] or pressed[pygame.K_RIGHT]) - (pressed[pygame.K_a] or pressed[pygame.K_LEFT])
        dz = (pressed[pygame.K_w] or pressed[pygame.K_UP]) - (pressed[pygame.K_s] or pressed[pygame.K_DOWN])
        return float(dx), float(dz)

    def update(self, now: int, direction: tuple[float, float] = (0.0, 0.0), run: bool = False) -> None:
        """Шаг мира и камеры на момент now."""
        dt = now - self._last if self._last else 16
        self._last = now
        if self.pending is not None:
            return
        for enemy_id, state in self.state.enemies.items():
            prev = self._enemy_prev.get(enemy_id)
            if prev is not None and abs(state.x - prev[0]) > 0.5:
                self._enemy_facing[enemy_id] = 1 if state.x > prev[0] else -1
            self._enemy_prev[enemy_id] = (state.x, state.z)
        met = self.state.step(dt, (0.0, 0.0) if self.panel else direction, run)
        k = 1 - math.exp(-max(0, min(100, dt)) / FOLLOW_MS)
        self.cam = (self.cam[0] + (self.state.hero[0] - self.cam[0]) * k,
                    self.cam[1] + (self.state.hero[1] - self.cam[1]) * k)
        if met is not None:
            self.pending = met
            self.say(self.t("{name} attacks!", name=self.t(self.world.enemy(met).name)), now)
            self.save()
            self.start_battle(met)
        elif direction != (0.0, 0.0) and now - self._saved_at > SAVE_EVERY_MS:
            self._saved_at = now
            self.save()

    def resume(self, now: int) -> None:
        """Вернулись на вкладку после боя: итог в мир."""
        if self.pending is None:
            return
        enemy_id, self.pending = self.pending, None
        outcome = self.finish_battle()
        result = self.state.resolve_battle(enemy_id, bool(outcome))
        name = self.t(self.world.enemy(enemy_id).name)
        if outcome is None:
            self.say(self.t("Retreated from {name}.", name=name), now)
        elif outcome:
            liberated = self.world.region_at((self.world.enemy(enemy_id).x, self.world.enemy(enemy_id).z))
            text = self.t("Victory over {name}!", name=name) + self._loot_text(result)
            if liberated is not None and liberated.id in self.state.liberated and self.world.enemy(enemy_id).boss:
                text += "  " + self.t("{region} is liberated!", region=self.t(liberated.name))
            self.say(text, now)
        else:
            self.say(self.t("Defeated by {name}. Back to safety.", name=name), now)
        self.cam = self.state.hero
        self.save()

    def interact(self) -> Optional[Interaction]:
        obj = self.state.nearest_interactive()
        if obj is None:
            return None
        result = self.state.interact(obj.id)
        now = self._last
        if obj.kind == "chest":
            self.say(self.t("Found:") + self._loot_text(result, lead=" "), now)
        elif result.rested:
            self.say(self.t("Rested at {name}. You will return here after a defeat.", name=self.t(obj.name)), now)
        else:
            self.say(self.t("{name}: nothing to do here yet.", name=self.t(obj.name)), now)
        self.save()
        return result

    def say(self, text: str, now: int) -> None:
        self.message, self.message_until = text, now + MESSAGE_MS

    def save(self) -> None:
        if self.save_path is not None:
            try:
                self.state.save(self.save_path)
            except OSError:
                pass

    # --- названия предметов ---

    def item_name(self, item_id: str) -> str:
        db = self.app.db if self.app is not None else None
        if db is not None and item_id in db.items:
            return self.t(db.items[item_id].name)
        good = self.world.goods.get(item_id)
        return self.t(good.name) if good else item_id

    def _loot_text(self, result: Interaction, lead: str = "  ") -> str:
        parts = [f"{self.item_name(i)} x{n}" for i, n in result.loot]
        if result.gold:
            parts.append(self.t("{n} gold", n=result.gold))
        return lead + ", ".join(parts) if parts else ""

    # --- кадр: интерфейс ---

    def draw(self, ui: UI, app: Any) -> None:
        self.app, self.t = app, ui.t
        now = pygame.time.get_ticks()
        if self.pending is not None:
            self.resume(now)
        pressed = pygame.key.get_pressed()
        run = bool(pressed[pygame.K_LSHIFT] or pressed[pygame.K_RSHIFT])
        self.update(now, (0.0, 0.0) if ui.captured else self.direction_from_keys(pressed), run)
        self.draw_hud(ui, now)
        if self.panel:                        # панель поверх поля: поле рисуется в интерфейс, под неё
            self.draw_field(ui.screen, now, self.camera(), force=True)
            shade = pygame.Surface(FIELD.size, pygame.SRCALPHA)
            shade.fill((0, 0, 0, 150))
            ui.screen.blit(shade, FIELD.topleft)
            self.draw_panel(ui, app)
        elif not self.native:
            self.draw_field(ui.screen, now, self.camera())

    def draw_hud(self, ui: UI, now: int) -> None:
        t, font = ui.t, ui.fonts["main"]
        region = self.state.region_here()
        if region is not None:
            status = t("liberated") if region.id in self.state.liberated else t("enemy territory")
            ui.text(f"{t(region.name)} — {status}", 12, 31, GREEN if region.id in self.state.liberated else RED)
        gold = font.render(t("Gold: {n}", n=self.state.inventory.gold), True, YELLOW)
        ui.screen.blit(gold, (WIDTH - gold.get_width() - 12, 31))
        near = self.state.nearest_interactive()
        if near is not None:
            prompt = {"chest": t("E: open the chest"), "town": t("E: rest in {name}", name=t(near.name)),
                      "fort": t("E: rest in {name}", name=t(near.name))}.get(near.kind, t("E: inspect {name}", name=t(near.name)))
            ui.text(prompt, WIDTH // 2 - 150, 31, YELLOW)
        hint = t("WASD move   Shift run   E interact   I inventory and squad   M map")
        ui.text(hint, 12, FOOTER_Y, DIM, "small")
        if self.message and now < self.message_until:
            ui.text(self.message, 12, FOOTER_Y + 20, TEXT, "small", WIDTH - 24)

    # --- инвентарь и отряд ---

    def main_squad(self) -> Any:
        return self.app.setup.player_squad if self.app is not None else None

    def draw_panel(self, ui: UI, app: Any) -> None:
        t, db, inventory = ui.t, app.db, self.state.inventory
        pygame.draw.rect(ui.screen, PANEL, PANEL_RECT)
        pygame.draw.rect(ui.screen, DIM, PANEL_RECT, 1)
        x, y = PANEL_RECT.x + 12, PANEL_RECT.y + 10
        ui.text(t("Inventory"), x, y, YELLOW)
        ui.text(t("Gold: {n}", n=inventory.gold), x + 180, y, YELLOW)
        rows = sorted(inventory.items.items(), key=lambda item: self.item_name(item[0]).casefold())
        area = pygame.Rect(x, y + 28, 300, PANEL_RECT.bottom - y - 70)
        offset = ui.scroll(("world", "inventory"), area, len(rows), area.height // INV_ROW)
        for i, (item_id, count) in enumerate(rows[offset:offset + area.height // INV_ROW]):
            kind = db.items[item_id].slot if item_id in db.items else \
                (self.world.goods[item_id].kind if item_id in self.world.goods else "")
            ry = area.y + i * INV_ROW
            ui.text(f"{self.item_name(item_id)}", x, ry, TEXT, "small", 190)
            ui.text(f"x{count}", x + 195, ry, TEXT, "small")
            ui.text(t(kind), x + 230, ry, DIM, "small", 80)
        if not rows:
            ui.text(t("empty"), x, area.y, DIM, "small")

        squad = self.main_squad()
        sx = PANEL_RECT.x + 340
        ui.text(t("Main squad: {name}", name=t(squad.name)) if squad else t("No squad"), sx, y, YELLOW)
        if squad is None:
            return
        for i, unit in enumerate(squad.formation.units):
            ry = y + 28 + i * SQUAD_ROW
            leader = " *" if unit.uid == squad.leader_uid else ""
            ui.text(f"{t(unit.name)} L{unit.state.level}{leader}", sx, ry, TEXT, "small", 170)
            ui.text(f"HP {unit.hp}/{unit.max_hp}", sx, ry + 18, GREEN, "small")
            for slot_index, slot in enumerate(unit.definition.slots):
                current = unit.state.equipment[slot_index]
                rect = pygame.Rect(sx + 175 + slot_index * 105, ry + 6, 100, 24)
                fits = [item_id for item_id in inventory.items if item_id in db.items and db.items[item_id].slot == slot]
                options = [(NONE_ITEM, f"— {t(slot)}")] + [(i_, f"{self.item_name(i_)} x{inventory.count(i_)}") for i_ in fits]
                if current is not None:
                    options.append((current, self.item_name(current)))
                picked = ui.dropdown(("world", "slot", unit.uid, slot_index), rect, options,
                                     current if current is not None else NONE_ITEM)
                if picked is not None and picked != (current if current is not None else NONE_ITEM):
                    self.change_equipment(unit, slot_index, picked)

    def change_equipment(self, unit: Any, slot_index: int, item_id: str) -> None:
        """Надеть предмет из инвентаря (NONE_ITEM — снять) на юнита основного отряда."""
        inventory = self.state.inventory
        try:
            if item_id == NONE_ITEM:
                inventory.unequip(unit, slot_index)
            else:
                inventory.equip(unit, slot_index, item_id)
        except ValueError as error:
            self.say(str(error), self._last)
            return
        self.on_change()
        self.save()

    # --- поле ---

    def camera(self, window_scale: float = 1.0, window_offset: tuple[float, float] = (0, 0)) -> Camera:
        clip = pygame.Rect(round(window_offset[0] + FIELD.left * window_scale), round(window_offset[1] + FIELD.top * window_scale),
                           round(FIELD.width * window_scale), round(FIELD.height * window_scale))
        return Camera(window_scale, FIELD.topleft, clip.topleft, clip)

    def rel(self, x: float, z: float, y: float = 0.0) -> tuple[float, float, float]:
        """Точка мира -> точка относительно камеры (для проекции)."""
        return x - self.cam[0], y, z - self.cam[1] + NEAR

    def draw_field(self, target: pygame.Surface, now: int, cam: Camera, force: bool = False) -> None:
        if self.panel and not force:
            return                             # с открытой панелью поле уже в интерфейсе
        previous = target.get_clip()
        target.set_clip(cam.clip)
        ground = self.ground_frame()
        image = ground if ground.get_size() == cam.clip.size else pygame.transform.smoothscale(ground, cam.clip.size)
        target.blit(image, cam.clip.topleft)
        view = View(PROJECTION, cam, now)
        parts: list[Part] = []
        for obj in self.world.objects:
            if self._visible(obj.x, obj.z):
                parts += self._object_parts(obj)
        for enemy_id, state in self.state.enemies.items():
            if self._visible(state.x, state.z):
                parts += self._enemy_parts(enemy_id, state, now)
        parts += self._hero_parts(now)
        draw_parts(target, view, parts)
        if self.minimap:
            self._draw_minimap(target, cam)
        target.set_clip(previous)

    def _visible(self, x: float, z: float) -> bool:
        _, _, rz = self.rel(x, z)
        return -200 < rz < 2000 and abs(x - self.cam[0]) < 1600

    # --- земля ---

    def ground_map(self) -> pygame.Surface:
        """Карта земли сверху (1 пиксель = 1/GROUND_RES единицы): текстуры регионов,
        туман над закрытыми, граница вражеских. Перестраивается, когда меняются регионы."""
        key = (frozenset(self.state.unlocked), frozenset(self.state.liberated))
        if key == self._ground_key and self._ground_map is not None:
            return self._ground_map
        w, d = (round(v * GROUND_RES) for v in self.world.size)
        surface = pygame.Surface((w, d))
        surface.fill(VOID)
        to_px = lambda p: (round(p[0] * GROUND_RES), round(d - p[1] * GROUND_RES))
        for region in self.world.regions:
            points = [to_px(p) for p in region.polygon]
            xs, ys = [p[0] for p in points], [p[1] for p in points]
            box = pygame.Rect(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)
            layer = pygame.Surface(box.size, pygame.SRCALPHA)
            texture = self._texture(region.ground)
            if texture is None:
                layer.fill((70, 100, 60))
            else:
                tw, th = texture.get_size()
                for tx in range(-(box.x % tw), box.width, tw):
                    for ty in range(-(box.y % th), box.height, th):
                        layer.blit(texture, (tx, ty))
            mask = pygame.Surface(box.size, pygame.SRCALPHA)
            pygame.draw.polygon(mask, (255, 255, 255, 255), [(px - box.x, py - box.y) for px, py in points])
            layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            if region.id not in self.state.unlocked:
                fog = pygame.Surface(box.size, pygame.SRCALPHA)
                pygame.draw.polygon(fog, LOCKED_FOG, [(px - box.x, py - box.y) for px, py in points])
                layer.blit(fog, (0, 0))
            surface.blit(layer, box.topleft)
        for region in self.world.regions:      # границы поверх: у вражеских красные
            color = ENEMY_BORDER if region.id in self.state.unlocked and region.id not in self.state.liberated else (40, 40, 40)
            pygame.draw.polygon(surface, color, [to_px(p) for p in region.polygon], 4)
        self._ground_key, self._ground_map, self._minimap, self._frame_key = key, surface, None, None
        return surface

    def _texture(self, name: str) -> Optional[pygame.Surface]:
        path = GROUND_DIR / name
        if not name or not path.is_file():
            return None
        image = pygame.image.load(str(path))
        if pygame.display.get_surface() is not None:
            image = image.convert()
        size = max(4, round(TILE * GROUND_RES))
        return pygame.transform.smoothscale(image, (size, size))

    def ground_frame(self) -> pygame.Surface:
        """Земля в перспективе, видимая с камеры, в логических пикселях поля: каждая строка
        экрана — строка карты земли на своей глубине, растянутая по ширине."""
        ground = self.ground_map()
        key = (round(self.cam[0]), round(self.cam[1]), self._ground_key)
        if key == self._frame_key and self._frame is not None:
            return self._frame
        frame = pygame.Surface(FIELD.size)
        frame.fill(VOID)
        gw, gd = ground.get_size()
        p = PROJECTION
        for row in range(FIELD.height):
            y = FIELD.top + row + 0.5
            k = (y - p.horizon) / (p.ground - p.horizon)
            if k <= 0.02:
                continue
            z = self.cam[1] - NEAR + (p.focal / k - p.focal)
            gy = int(gd - z * GROUND_RES)
            if not 0 <= gy < gd:
                continue
            left_x, right_x = self.cam[0] - p.center_x / k, self.cam[0] + (WIDTH - p.center_x) / k
            sx0, sx1 = max(0, int(left_x * GROUND_RES)), min(gw, int(math.ceil(right_x * GROUND_RES)))
            if sx1 <= sx0:
                continue
            dx0 = round(p.center_x + (sx0 / GROUND_RES - self.cam[0]) * k)
            dx1 = round(p.center_x + (sx1 / GROUND_RES - self.cam[0]) * k)
            if dx1 > dx0:
                frame.blit(pygame.transform.scale(ground.subsurface((sx0, gy, sx1 - sx0, 1)), (dx1 - dx0, 1)), (dx0, row))
        frame.blit(self.haze(), (0, 0))
        self._frame_key, self._frame = key, frame
        return frame

    def haze(self) -> pygame.Surface:
        """Дымка вдали: у верхнего края поля сильнее."""
        if self._haze is None:
            self._haze = pygame.Surface(FIELD.size, pygame.SRCALPHA)
            for row in range(FIELD.height):
                k = (1 - row / FIELD.height) ** 2.2 * HAZE_TOP
                pygame.draw.line(self._haze, (*HAZE, int(255 * k)), (0, row), (FIELD.width, row))
        return self._haze

    # --- спрайты ---

    def _shadow(self, x: float, z: float, width: float) -> Part:
        point = self.rel(x, z)

        def draw(target: pygame.Surface, view: View) -> None:
            px, py, k = view.p(point)
            rect = pygame.Rect(0, 0, max(2, round(width * k)), max(2, round(width * k * 0.3)))
            rect.center = (px, py)
            shade = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.ellipse(shade, (0, 0, 0, 90), shade.get_rect())
            target.blit(shade, rect)
        return Part(GROUND, point[2], draw)

    def _sprite(self, image_name: str, x: float, z: float, height: float, flip: bool = False,
                bank: Optional[ImageBank] = None, lift: float = 0.0) -> Part:
        point = self.rel(x, z, lift)
        bank = bank or self.images

        def draw(target: pygame.Surface, view: View) -> None:
            px, py, k = view.p(point)
            sprite, _ = bank.scaled(image_name, max(4, round(height * k / 2) * 2), flip, placeholder)
            target.blit(sprite, sprite.get_rect(midbottom=(px, py)))
        return Part(UPRIGHT, point[2], draw)

    def _label(self, text: str, x: float, z: float, height: float, color: tuple[int, int, int]) -> Part:
        point = self.rel(x, z, height + 12)

        def draw(target: pygame.Surface, view: View) -> None:
            px, py, k = view.p(point)
            font = fx_font(max(10, round(14 * view.cam.scale)), False)
            img, shade = font.render(text, True, color), font.render(text, True, (10, 10, 14))
            rect = img.get_rect(midbottom=(px, py))
            target.blit(shade, rect.move(1, 1))
            target.blit(img, rect)
        return Part(OVERLAY, 0, draw)

    def _object_parts(self, obj: WorldObject) -> list[Part]:
        image = obj.image or f"{obj.kind}.png"
        if obj.kind == "chest" and obj.id in self.state.opened:
            image = "chest_open.png"
        parts = [self._shadow(obj.x, obj.z, max(obj.radius * 2, obj.size * 0.5)),
                 self._sprite(image, obj.x, obj.z, obj.size)]
        if obj.kind in SAFE_KINDS or obj.kind == "ruins":
            parts.append(self._label(self.t(obj.name), obj.x, obj.z, obj.size, (240, 230, 200)))
        return parts

    def _enemy_parts(self, enemy_id: str, state: Any, now: int) -> list[Part]:
        enemy = self.world.enemy(enemy_id)
        db = self.app.db if self.app is not None else None
        leader = enemy.leader_in(list(db.units)) if db is not None else enemy.leader_class
        tags = db.units[leader].tags if db is not None and leader in db.units else ()
        sprite = self.bank.sprite_for(leader, tags)
        height = HUMAN * self.bank.ratio(sprite)
        bob = 3 * abs(math.sin(now / 140 + hash(enemy_id) % 7)) if state.target is not None or state.chasing else 0
        facing = self._enemy_facing.get(enemy_id, -1)
        parts = [self._shadow(state.x, state.z, HUMAN * 0.6),
                 self._sprite(f"{sprite}.png" if sprite else "", state.x, state.z, height, facing < 0, self.bank, bob)]
        name = self.t(enemy.name) + (" !" if state.chasing else "")
        parts.append(self._label(name, state.x, state.z, height, (255, 120, 100) if state.chasing else (230, 170, 160)))
        return parts

    def _hero_parts(self, now: int) -> list[Part]:
        x, z = self.state.hero
        sprite = self.bank.sprite_for(HERO_CLASS, ("cavalry",))
        height = HUMAN * self.bank.ratio(sprite)
        bob = 2 * math.sin(now / 160)
        parts = [self._shadow(x, z, HUMAN * 0.9), self._sprite(f"{sprite}.png", x, z, height, self.state.facing < 0,
                                                               self.bank, abs(bob))]
        point = self.rel(x, z)

        def ring(target: pygame.Surface, view: View) -> None:   # кольцо героя на земле
            px, py, k = view.p(point)
            add_glow(target, (px, py), (60, 50, 15), 40 * k, 1.0)
        parts.append(Part(GROUND, point[2] - 1, ring))
        return parts

    # --- мини-карта ---

    def _draw_minimap(self, target: pygame.Surface, cam: Camera) -> None:
        ground = self.ground_map()
        w = round(MINIMAP_W * cam.scale)
        h = round(w * ground.get_height() / ground.get_width())
        if self._minimap is None or self._minimap.get_width() != w:
            self._minimap = pygame.transform.smoothscale(ground, (w, h))
        box = pygame.Rect(cam.clip.right - w - round(10 * cam.scale), cam.clip.top + round(10 * cam.scale), w, h)
        target.blit(self._minimap, box)
        pygame.draw.rect(target, (220, 220, 220), box, max(1, round(cam.scale)))
        sx, sz = w / self.world.size[0], h / self.world.size[1]
        to_map = lambda x, z: (box.x + round(x * sx), box.bottom - round(z * sz))
        dot = max(2, round(3 * cam.scale))
        for obj in self.world.objects:
            if obj.kind in SAFE_KINDS:
                pygame.draw.rect(target, (240, 220, 140), pygame.Rect(*to_map(obj.x, obj.z), dot * 2, dot * 2))
        for state in self.state.enemies.values():
            pygame.draw.circle(target, RED, to_map(state.x, state.z), dot)
        pygame.draw.circle(target, (255, 255, 255), to_map(*self.state.hero), dot + 1)

