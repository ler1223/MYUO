"""Открытый мир: карта с регионами, объектами и бродячими отрядами врага, герой и прогресс.

Без pygame. Координаты мира: x — вправо, z — вглубь (вверх по карте), в тех же единицах,
что и сцена боя (рост человека около 185).

- WorldDef — карта из data/world/<id>.json: регионы (многоугольники), объекты (город, форт,
  руины, сундук, декор), отряды врага с составом и добычей, каталог товаров (goods).
- Overworld — состояние игры на карте: где герой, какие регионы освобождены и открыты,
  какие сундуки открыты, какие отряды разбиты, инвентарь. Шаг step() двигает героя и врагов
  и сообщает о столкновении с врагом (это бой); resolve_battle() применяет итог боя.

Регион открыт (unlocked) — по нему можно ходить. Освобождён (liberated) — враг в нём разбит:
это даёт победа над отрядом-главарём региона (boss), и тогда открываются регионы из unlocks.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Optional, Sequence

from .inventory import Inventory

if TYPE_CHECKING:
    from .database import Database
    from .scenario import Scenario

ROOT = Path(__file__).resolve().parent.parent
WORLD_DIR = ROOT / "data" / "world"
DEFAULT_WORLD = "test"
SAVE_VERSION = 1

HERO_SPEED = 360            # единиц в секунду
RUN_FACTOR = 1.7            # с зажатым Shift
HERO_RADIUS = 30
INTERACT_RADIUS = 110
CONTACT_RADIUS = 70         # враг так близко — бой
GRACE_MS = 2500             # после боя враги не нападают столько времени
WANDER_PAUSE_MS = (900, 2600)
OBJECT_KINDS = ("town", "fort", "ruins", "chest", "decor")
SAFE_KINDS = ("town", "fort")    # здесь герой отдыхает; после поражения возвращается сюда
GOOD_KINDS = ("material", "consumable", "valuable")

Point = tuple[float, float]


def point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    """Чётно-нечётное правило."""
    x, z = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, zi = polygon[i]
        xj, zj = polygon[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi) + xi:
            inside = not inside
        j = i
    return inside


# --- описание карты ------------------------------------------------------------

@dataclass(frozen=True)
class Good:
    """Товар мира: не снаряжение (материал, расходник, ценность)."""

    id: str
    name: str
    kind: str = "material"


@dataclass(frozen=True)
class Region:
    id: str
    name: str
    polygon: tuple[Point, ...]
    ground: str = ""                         # текстура земли из assets/grounds
    open: bool = False                       # открыт с начала игры
    liberated: bool = False                  # уже наш с начала игры
    unlocks: tuple[str, ...] = ()            # что открывается после освобождения
    scene: str = ""                          # сцена боя для стычек здесь (assets/scenes); пусто — сцена карты

    def contains(self, point: Point) -> bool:
        return point_in_polygon(point, self.polygon)


@dataclass(frozen=True)
class WorldObject:
    id: str
    kind: str
    name: str
    x: float
    z: float
    image: str = ""                          # assets/world/<image>; пусто — <kind>.png
    size: float = 200                        # высота спрайта в единицах мира
    radius: float = 0                        # непроходимый круг (0 — проходимо)
    loot: tuple[tuple[str, int], ...] = ()   # сундук: (id предмета, сколько)
    gold: int = 0

    @property
    def interactive(self) -> bool:
        return self.kind != "decor"


@dataclass(frozen=True)
class EnemySquadDef:
    id: str
    name: str
    x: float
    z: float
    roster: tuple[tuple[str, int, int, int], ...]   # (класс, уровень, ряд, колонна); класс: "a|b" — кандидаты
    boss: bool = False                       # разбит — регион освобождён
    roam: float = 260                        # бродит в таком радиусе от дома
    aggro: float = 420                       # замечает героя на таком расстоянии
    leash: float = 900                       # дальше от дома не преследует
    speed: float = 230
    loot: tuple[tuple[str, int], ...] = ()
    gold: int = 0

    @property
    def leader_class(self) -> str:
        return self.roster[0][0].split("|")[0] if self.roster else ""

    def leader_in(self, classes: Sequence[str]) -> str:
        """Класс вожака, который есть в справочнике (первый подходящий кандидат)."""
        return next((c for c in self.roster[0][0].split("|") if c in classes), self.leader_class) if self.roster else ""


@dataclass(frozen=True)
class WorldDef:
    id: str
    name: str
    size: tuple[float, float]                # ширина (x) и глубина (z)
    start: Point
    regions: tuple[Region, ...]
    objects: tuple[WorldObject, ...]
    enemies: tuple[EnemySquadDef, ...]
    goods: Mapping[str, Good] = field(default_factory=dict)
    scene: str = ""                          # сцена боя для стычек (assets/scenes)

    @classmethod
    def load(cls, world_id: str = DEFAULT_WORLD, folder: Path = WORLD_DIR) -> "WorldDef":
        data = json.loads((Path(folder) / f"{world_id}.json").read_text(encoding="utf-8"))
        return cls.from_dict(world_id, data)

    @classmethod
    def from_dict(cls, world_id: str, data: Mapping[str, Any]) -> "WorldDef":
        pairs = lambda items: tuple((str(i), int(n)) for i, n in items)
        regions = tuple(Region(r["id"], r["name"], tuple((float(x), float(z)) for x, z in r["polygon"]),
                               r.get("ground", ""), bool(r.get("open")), bool(r.get("liberated")),
                               tuple(r.get("unlocks", ())), r.get("scene", "")) for r in data["regions"])
        objects = tuple(WorldObject(o["id"], o["kind"], o.get("name", ""), float(o["x"]), float(o["z"]),
                                    o.get("image", ""), float(o.get("size", 200)), float(o.get("radius", 0)),
                                    pairs(o.get("loot", ())), int(o.get("gold", 0))) for o in data.get("objects", ()))
        enemies = tuple(EnemySquadDef(e["id"], e["name"], float(e["x"]), float(e["z"]),
                                      tuple(("|".join(c) if isinstance(c, list) else str(c), int(lv), int(r), int(col))
                                            for c, lv, r, col in e["roster"]),
                                      bool(e.get("boss")), float(e.get("roam", 260)), float(e.get("aggro", 420)),
                                      float(e.get("leash", 900)), float(e.get("speed", 230)),
                                      pairs(e.get("loot", ())), int(e.get("gold", 0))) for e in data.get("enemies", ()))
        goods = {k: Good(k, g["name"], g.get("kind", "material")) for k, g in data.get("goods", {}).items()}
        world = cls(world_id, data.get("name", world_id), (float(data["size"][0]), float(data["size"][1])),
                    (float(data["start"][0]), float(data["start"][1])), regions, objects, enemies, goods,
                    data.get("scene", ""))
        world.check()
        return world

    def check(self) -> None:
        """Ошибки описания: повторяющиеся id, неизвестные виды и ссылки."""
        ids = [r.id for r in self.regions]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate region ids")
        for region in self.regions:
            if len(region.polygon) < 3:
                raise ValueError(f"region {region.id}: polygon needs at least 3 points")
            for other in region.unlocks:
                if other not in ids:
                    raise ValueError(f"region {region.id} unlocks unknown region {other!r}")
        things = [o.id for o in self.objects] + [e.id for e in self.enemies]
        if len(set(things)) != len(things):
            raise ValueError("duplicate object or enemy ids")
        for obj in self.objects:
            if obj.kind not in OBJECT_KINDS:
                raise ValueError(f"object {obj.id}: unknown kind {obj.kind!r}")
        for good in self.goods.values():
            if good.kind not in GOOD_KINDS:
                raise ValueError(f"good {good.id}: unknown kind {good.kind!r}")
        if self.region_at(self.start) is None:
            raise ValueError("the start point is outside every region")

    def unknown_references(self, classes: Sequence[str], items: Sequence[str]) -> list[str]:
        """Классы и предметы, которых нет в справочнике (и в каталоге товаров)."""
        known_items = set(items) | set(self.goods)
        problems = []
        for enemy in self.enemies:
            problems += [f"{enemy.id}: class {c!r}" for c, *_ in enemy.roster
                         if not any(x in classes for x in c.split("|"))]
            problems += [f"{enemy.id}: item {i!r}" for i, _ in enemy.loot if i not in known_items]
        for obj in self.objects:
            problems += [f"{obj.id}: item {i!r}" for i, _ in obj.loot if i not in known_items]
        return problems

    def battle_scene(self, point: Point) -> str:
        """Сцена боя для стычки в этой точке: сцена региона, иначе сцена карты."""
        region = self.region_at(point)
        return (region.scene if region is not None else "") or self.scene

    def region_at(self, point: Point) -> Optional[Region]:
        return next((r for r in self.regions if r.contains(point)), None)

    def region(self, region_id: str) -> Region:
        return next(r for r in self.regions if r.id == region_id)

    def obj(self, object_id: str) -> WorldObject:
        return next(o for o in self.objects if o.id == object_id)

    def enemy(self, enemy_id: str) -> EnemySquadDef:
        return next(e for e in self.enemies if e.id == enemy_id)


# --- состояние игры ------------------------------------------------------------

@dataclass
class EnemyState:
    """Где отряд врага сейчас и куда идёт (в сохранение не попадает: после загрузки — дома)."""

    x: float
    z: float
    target: Optional[Point] = None
    wait_until: int = 0
    chasing: bool = False


@dataclass
class Interaction:
    """Что произошло при взаимодействии с объектом (для показа игроку)."""

    object_id: str
    kind: str
    loot: tuple[tuple[str, int], ...] = ()
    gold: int = 0
    rested: bool = False


class Overworld:
    def __init__(self, world: WorldDef, seed: int = 1):
        self.world = world
        self.rng = random.Random(seed)
        self.hero: Point = world.start
        self.facing = 1                      # 1 — вправо, -1 — влево
        self.unlocked: set[str] = {r.id for r in world.regions if r.open or r.liberated}
        self.liberated: set[str] = {r.id for r in world.regions if r.liberated}
        self.opened: set[str] = set()        # открытые сундуки
        self.defeated: set[str] = set()      # разбитые отряды врага
        self.inventory = Inventory()
        self.safe_point: Point = world.start  # последний город или форт
        self.grace_until = 0
        self.clock = 0                       # мс игрового времени
        self.enemies: dict[str, EnemyState] = {}
        self.reset_enemies()

    def reset_enemies(self) -> None:
        self.enemies = {e.id: EnemyState(e.x, e.z) for e in self.world.enemies if e.id not in self.defeated}

    # --- где можно ходить ---

    def walkable(self, point: Point) -> bool:
        x, z = point
        w, d = self.world.size
        if not (HERO_RADIUS <= x <= w - HERO_RADIUS and HERO_RADIUS <= z <= d - HERO_RADIUS):
            return False
        region = self.world.region_at(point)
        if region is None or region.id not in self.unlocked:
            return False
        return all(math.dist(point, (o.x, o.z)) >= o.radius + HERO_RADIUS for o in self.world.objects if o.radius > 0)

    def region_here(self) -> Optional[Region]:
        return self.world.region_at(self.hero)

    # --- шаг ---

    def step(self, dt_ms: int, direction: Point = (0.0, 0.0), run: bool = False) -> Optional[str]:
        """Двигает героя (direction — направление ввода, длина не важна) и врагов.

        Возвращает id отряда врага, который настиг героя (начинается бой), или None.
        """
        dt_ms = max(0, min(100, dt_ms))
        self.clock += dt_ms
        self._move_hero(dt_ms, direction, run)
        for enemy_id, state in self.enemies.items():
            self._move_enemy(self.world.enemy(enemy_id), state, dt_ms)
        if self.clock < self.grace_until:
            return None
        for enemy_id, state in self.enemies.items():
            if math.dist(self.hero, (state.x, state.z)) <= CONTACT_RADIUS:
                return enemy_id
        return None

    def _move_hero(self, dt_ms: int, direction: Point, run: bool) -> None:
        length = math.hypot(*direction)
        if length < 1e-6:
            return
        step = HERO_SPEED * (RUN_FACTOR if run else 1.0) * dt_ms / 1000
        dx, dz = direction[0] / length * step, direction[1] / length * step
        if dx:
            self.facing = 1 if dx > 0 else -1
        x, z = self.hero
        # Скольжение вдоль препятствий: сначала целиком, потом по каждой оси отдельно.
        for candidate in ((x + dx, z + dz), (x + dx, z), (x, z + dz)):
            if self.walkable(candidate):
                self.hero = candidate
                return

    def _move_enemy(self, enemy: EnemySquadDef, state: EnemyState, dt_ms: int) -> None:
        home = (enemy.x, enemy.z)
        home_region = self.world.region_at(home)
        awake = home_region is not None and home_region.id in self.unlocked   # в закрытых регионах враги не нападают
        sees = (awake and self.clock >= self.grace_until and math.dist(self.hero, (state.x, state.z)) <= enemy.aggro
                and math.dist(self.hero, home) <= enemy.leash)
        state.chasing = sees
        if sees:
            goal = self.hero
        else:
            if state.target is None or math.dist((state.x, state.z), state.target) < 8:
                if state.target is not None:
                    state.wait_until = self.clock + self.rng.randint(*WANDER_PAUSE_MS)
                a, r = self.rng.uniform(0, math.tau), enemy.roam * math.sqrt(self.rng.uniform(0, 1))
                state.target = (enemy.x + math.cos(a) * r, enemy.z + math.sin(a) * r)
            if self.clock < state.wait_until:
                return
            goal = state.target
        speed = enemy.speed * (1.3 if sees else 0.55)
        dist = math.dist((state.x, state.z), goal)
        if dist < 1e-6:
            return
        step = min(dist, speed * dt_ms / 1000)
        nx = state.x + (goal[0] - state.x) / dist * step
        nz = state.z + (goal[1] - state.z) / dist * step
        region = self.world.region_at((nx, nz))
        if region is not None and region.id in self.unlocked or not sees:
            state.x, state.z = nx, nz
        else:
            state.target = None              # в закрытый регион за героем не идёт

    # --- объекты ---

    def nearest_interactive(self) -> Optional[WorldObject]:
        """Объект в пределах досягаемости, с которым можно что-то сделать."""
        near = [(math.dist(self.hero, (o.x, o.z)) - o.radius, o) for o in self.world.objects
                if o.interactive and not (o.kind == "chest" and o.id in self.opened)]
        near = [(d, o) for d, o in near if d <= INTERACT_RADIUS]
        return min(near, key=lambda item: item[0])[1] if near else None

    def interact(self, object_id: str) -> Interaction:
        obj = self.world.obj(object_id)
        if obj.kind == "chest":
            if obj.id in self.opened:
                return Interaction(obj.id, obj.kind)
            self.opened.add(obj.id)
            self._take(obj.loot, obj.gold)
            return Interaction(obj.id, obj.kind, obj.loot, obj.gold)
        if obj.kind in SAFE_KINDS:
            self.safe_point = (obj.x, obj.z - (obj.radius + HERO_RADIUS + 20))
            return Interaction(obj.id, obj.kind, rested=True)
        return Interaction(obj.id, obj.kind)

    def _take(self, loot: Sequence[tuple[str, int]], gold: int) -> None:
        for item_id, count in loot:
            self.inventory.add(item_id, count)
        self.inventory.add_gold(gold)

    # --- бой ---

    def resolve_battle(self, enemy_id: str, won: bool) -> Interaction:
        """Итог боя с отрядом enemy_id: победа — добыча и, у главаря, освобождение региона;
        поражение — герой у последнего города, враг дома. После боя враги дают передышку."""
        enemy = self.world.enemy(enemy_id)
        self.grace_until = self.clock + GRACE_MS
        if not won:
            self.hero = self.safe_point
            self.enemies[enemy_id] = EnemyState(enemy.x, enemy.z)
            return Interaction(enemy_id, "defeat")
        self.defeated.add(enemy_id)
        self.enemies.pop(enemy_id, None)
        self._take(enemy.loot, enemy.gold)
        if enemy.boss:
            region = self.world.region_at((enemy.x, enemy.z))
            if region is not None:
                self.liberate(region.id)
        return Interaction(enemy_id, "victory", enemy.loot, enemy.gold)

    def liberate(self, region_id: str) -> None:
        self.liberated.add(region_id)
        self.unlocked.add(region_id)
        self.unlocked.update(self.world.region(region_id).unlocks)

    # --- сохранение ---

    def to_dict(self) -> dict[str, Any]:
        return {"version": SAVE_VERSION, "world": self.world.id, "hero": list(self.hero),
                "safe_point": list(self.safe_point), "unlocked": sorted(self.unlocked),
                "liberated": sorted(self.liberated), "opened": sorted(self.opened),
                "defeated": sorted(self.defeated), "inventory": self.inventory.to_dict()}

    def load_dict(self, data: Mapping[str, Any]) -> None:
        """Прогресс из сохранения; чужая версия или другая карта — ValueError."""
        if data.get("version") != SAVE_VERSION or data.get("world") != self.world.id:
            raise ValueError("the world save does not match this map")
        known_regions = {r.id for r in self.world.regions}
        self.unlocked = {r for r in data.get("unlocked", ()) if r in known_regions} | self.unlocked
        self.liberated = {r for r in data.get("liberated", ()) if r in known_regions} | self.liberated
        self.opened = set(data.get("opened", ()))
        self.defeated = set(data.get("defeated", ()))
        self.inventory = Inventory.from_dict(data.get("inventory", {}))
        hero = tuple(data.get("hero", self.world.start))
        self.hero = hero if self.walkable(hero) else self.world.start
        safe = tuple(data.get("safe_point", self.world.start))
        self.safe_point = safe if self.walkable(safe) else self.world.start
        self.reset_enemies()

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def load(self, path: Path) -> None:
        self.load_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# --- бой со встреченным отрядом -------------------------------------------------

ENEMY_FIRST_UID = 1000          # uid юнитов врага: не пересекаются с армией игрока


def encounter_scenario(db: "Database", setup: "Scenario", enemy: EnemySquadDef) -> "Scenario":
    """Бой: копия основного отряда игрока (из расстановки) против отряда врага с карты.

    Расстановка не меняется: бой идёт на копии, после боя здоровье юнитов прежнее, как в UO.
    Классы, которых нет в справочнике, и не помещающиеся в поле клетки пропускаются.
    """
    from .save import clone_scenario
    from .scenario import Scenario, _build_army, auto_equipment, pick

    player = clone_scenario(db, setup)
    size = db.formation
    chosen = [(pick(db, cls.split("|")), level, row, col) for cls, level, row, col in enemy.roster]
    roster = [(cls, level, auto_equipment(db, cls), row, col) for cls, level, row, col in chosen
              if cls and row < size.rows and col < size.cols][:size.max_units]
    if not roster:
        raise ValueError(f"enemy squad {enemy.id} has no units this database knows")
    army, squad = _build_army(db, "enemy", enemy.name, enemy.id, enemy.name, roster, first_uid=ENEMY_FIRST_UID)
    return Scenario(player.player, army, player.world, player.player_squad, squad)
