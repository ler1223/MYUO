"""Бесконечная башня: бои подряд с усиливающимися врагами.

Забег: выбор трёх бойцов (каждый раз 1 из 3, со стартовым снаряжением) -> подготовка
(расстановка, снаряжение, тактики) -> бой -> при победе опыт, золото и выбор 2 предметов
из 5 -> следующий этаж; после каждого N-го этажа магазин (найм и предметы). Поражение
заканчивает забег. Все числа баланса — в data/tower.json (TowerRules).

Случайность детерминирована: seed забега + этаж + назначение, поэтому после загрузки
сохранения враги этажа и предложения те же.
"""
from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Collection, Mapping, Optional, Sequence, Union

from .database import DEFAULT_DATA_DIR, Database
from .inventory import Inventory
from .progression import ExpRules, LevelUp, grant_exp
from .promotion import promote
from .save import unit_from_save, unit_to_save
from .scenario import MAP_SIZE, Scenario
from .squad import Formation, FormationSize
from .unit import UnitDefinition, class_allowed
from .world import Army, WorldMap

TOWER_RULES_PATH = DEFAULT_DATA_DIR / "tower.json"
NAMES_PATH = DEFAULT_DATA_DIR / "names.json"


def load_names(class_id: str, path: Path = NAMES_PATH) -> list[str]:
    """Личные имена для бойца класса (английские; перевод — в data/lang/<язык>.json, как у остального
    текста). Классам с женской фигурой (female_classes) — женские имена, остальным — мужские."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return list(data["female" if class_id in data.get("female_classes", ()) else "male"])
    except (OSError, ValueError, KeyError):
        return []
DEFAULT_SAVE_PATH = Path(__file__).resolve().parent.parent / "saves" / "tower.json"
SAVE_VERSION = 1
PLAYER_SQUAD = "tower"
ENEMY_SQUAD = "floor"
ENEMY_FIRST_UID = 1000
ARTIFACT = "artifact"
RANGED_SLOTS = ("bow", "staff")     # классы с таким слотом встают во второй ряд

DRAFT, PREPARE, REWARD, SHOP, OVER = "draft", "prepare", "reward", "shop", "over"


def base_classes(db: Database) -> list[str]:
    """Классы, в которые никто не повышается и с тиром ниже 20: из них набор, найм и враги
    (повышенные — повышением; сразу повышенные классы вроде эльфов в набор не попадают)."""
    roots = sorted(c for c in db.units if not db.parents(c) and not db.units[c].story)
    return [c for c in roots if db.units[c].tier < 20] or roots or sorted(c for c in db.units if not db.units[c].story)


def by_floor(table: Sequence[Mapping[str, Any]], floor: int) -> Mapping[str, Any]:
    """Последняя строка таблицы, чей floor не больше этажа (таблица по возрастанию этажей)."""
    found = table[0]
    for row in table:
        if row["floor"] <= floor:
            found = row
    return found


class TowerRules:
    """Правила башни из data/tower.json: ступени отряда, рост врагов, награды, магазин."""

    def __init__(self, data: Mapping[str, Any]):
        self.data = data
        self.exp = ExpRules.from_dict(data.get("exp", {}))
        for name, table in (("squad", data["squad"]), ("enemies.count", data["enemies"]["count"]),
                            ("enemies.gear_tier", data["enemies"]["gear_tier"]),
                            ("reward.tier_weights", data["reward"]["tier_weights"])):
            floors = [row["floor"] for row in table]
            if not floors or floors[0] != 1 or floors != sorted(floors):
                raise ValueError(f"tower {name}: floors must start at 1 and grow")
        if data["reward"]["take"] > data["reward"]["offer"]:
            raise ValueError("tower reward: cannot take more items than offered")
        groups = data.get("draft", {}).get("groups")
        if not groups:
            raise ValueError("tower draft: groups must not be empty")
        for group in groups:
            if not group.get("role"):
                raise ValueError("tower draft: every group needs a role")

    @classmethod
    def load(cls, path: Union[str, Path] = TOWER_RULES_PATH) -> "TowerRules":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    # --- набор отряда ---

    def draft_groups(self) -> list[Mapping[str, Any]]:
        """Группы набора по порядку: в каждой роль (или явные классы); выбор — общий `.choices`."""
        return list(self.data["draft"]["groups"])

    def draft_pool(self, db: Database, group: Mapping[str, Any]) -> list[str]:
        """Классы на выбор в группе: свои (classes) или все базовые классы этой роли (role).

        Повышенные классы в набор не попадают, даже если записаны в группе.
        """
        available = set(base_classes(db))
        listed = [c for c in group.get("classes", ()) if c in available]
        if listed:
            return listed
        return [c for c in base_classes(db) if group["role"] in db.units[c].roles]

    # --- отряд игрока ---

    def squad_size(self, floor: int) -> FormationSize:
        """Поле и число бойцов, которых можно выставить на этаже; ступени наследуют rows/cols."""
        rows, cols, units = 3, 3, 1
        for row in self.data["squad"]:
            if row["floor"] > floor:
                break
            rows, cols, units = row.get("rows", rows), row.get("cols", cols), row.get("units", units)
        return FormationSize.from_dict({"rows": rows, "cols": cols, "max_units": min(units, rows * cols)})

    # --- враги ---

    def is_boss(self, floor: int) -> bool:
        every = self.data["boss"]["every"]
        return every > 0 and floor % every == 0

    def enemy_count(self, floor: int) -> int:
        size = self.squad_size(floor)
        count = by_floor(self.data["enemies"]["count"], floor)["units"]
        if self.is_boss(floor):
            count += self.data["boss"]["extra_units"]
        return max(1, min(count, size.rows * size.cols))

    def enemy_level(self, floor: int) -> int:
        enemies = self.data["enemies"]
        level = int(enemies["level_start"] + (floor - 1) * enemies["level_per_floor"])
        if self.is_boss(floor):
            level += self.data["boss"]["level_bonus"]
        return max(1, min(level, self.exp.max_level))

    def gear_tier(self, floor: int) -> int:
        return by_floor(self.data["enemies"]["gear_tier"], floor)["tier"]

    def artifact_chance(self, floor: int) -> float:
        enemies = self.data["enemies"]
        steps = floor - enemies["artifacts_from"] + 1
        return min(1.0, max(0.0, steps * enemies["artifact_chance_per_floor"]))

    def enemy_classes(self, db: Database) -> dict[str, float]:
        """Пул классов врагов с весами; пусто в данных — все базовые классы поровну (повышенные
        получаются повышением на этаже, enemy_promotion)."""
        listed = {k: v for k, v in self.data["enemies"].get("classes", {}).items()
                  if k in db.units and v > 0 and not db.units[k].story}
        return listed or {class_id: 1.0 for class_id in base_classes(db)}

    def enemy_promotion(self, floor: int) -> float:
        """Шанс, что враг, доросший до повышения, повышен (на каждой ступени отдельно)."""
        table = self.data["enemies"].get("promotion")
        return float(by_floor(table, floor)["chance"]) if table else 0.0

    # --- награды и магазин ---

    def gold(self, floor: int) -> int:
        gold = self.data["gold"]["base"] + self.data["gold"]["per_floor"] * floor
        return gold * (self.data["boss"]["gold_factor"] if self.is_boss(floor) else 1)

    def tier_weights(self, floor: int) -> list[float]:
        """Веса тиров предметов награды и магазина (первый — тир 1). У главаря — как на этажах выше."""
        if self.is_boss(floor):
            floor += self.data["boss"]["reward_floor_bonus"]
        return list(by_floor(self.data["reward"]["tier_weights"], floor)["weights"])

    def shop_after(self, floor: int) -> bool:
        every = self.data["shop"]["every"]
        return every > 0 and floor % every == 0

    def recruit_price(self, level: int) -> int:
        shop = self.data["shop"]
        return shop["recruit_price"] + shop["recruit_price_per_level"] * (level - 1)

    def reroll_price(self, rerolls: int) -> int:
        return self.data["shop"]["reroll"] + self.data["shop"]["reroll_step"] * rerolls

    def sell_price(self, db: Database, item_id: str) -> int:
        return int(db.items[item_id].price * self.data["shop"]["sell_share"])

    def scene(self, floor: int) -> str:
        if self.is_boss(floor) and self.data["boss"].get("scene"):
            return self.data["boss"]["scene"]
        scenes = self.data["scenes"]
        return scenes["list"][(floor - 1) // max(1, scenes["every"]) % len(scenes["list"])]


def preferred_cells(definition: UnitDefinition, size: FormationSize) -> list[tuple[int, int]]:
    """Клетки по убыванию желательности: ближний бой — передний ряд, стрелки и маги — второй."""
    rows = list(range(size.rows))
    if any(slot in RANGED_SLOTS for slot in definition.slots) and size.rows > 1:
        rows = rows[1:] + rows[:1]
    cols = sorted(range(size.cols), key=lambda c: abs(c - (size.cols - 1) / 2))
    return [(row, col) for row in rows for col in cols]


def free_cell(taken: Collection[tuple[int, int]], definition: UnitDefinition,
              size: FormationSize) -> Optional[tuple[int, int]]:
    """Лучшая свободная клетка для класса; None, если поле заполнено."""
    if len(taken) >= size.max_units:
        return None
    return next((cell for cell in preferred_cells(definition, size) if cell not in taken), None)


@dataclass
class BattleReport:
    """Итог боя этажа для экрана наград."""

    floor: int
    won: bool
    boss: bool = False
    gold: int = 0
    level_ups: list[LevelUp] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BattleReport":
        return cls(data["floor"], data["won"], data.get("boss", False), data.get("gold", 0),
                   [LevelUp(**up) for up in data.get("level_ups", ())])


class TowerRun:
    """Состояние забега. Юниты живут в армии игрока: в отряде — выставленные, остальные в запасе."""

    def __init__(self, rules: TowerRules, seed: Optional[int] = None, best: int = 0):
        self.rules = rules
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.best = best              # лучший пройденный этаж за все забеги
        self.floor = 1                # этаж, бой которого следующий
        self.phase = DRAFT
        self.army = Army("player", "Player")
        self.squad = self.army.create_squad(PLAYER_SQUAD, "Tower", rules.squad_size(1))
        self.inventory = Inventory(gold=rules.data["start_gold"])
        self.next_uid = 1
        self.offers: list[str] = []                       # классы на выбор при наборе
        self.reward: list[str] = []                       # предметы награды
        self.recruits: list[Optional[tuple[str, int]]] = []   # (класс, уровень); None — уже нанят
        self.shop_items: list[Optional[str]] = []         # None — уже куплен
        self.rerolls = 0
        self.report: Optional[BattleReport] = None
        self.draft_group = 0                              # какая группа набора сейчас выбирается

    @classmethod
    def new(cls, db: Database, rules: TowerRules, best: int = 0, seed: Optional[int] = None) -> "TowerRun":
        run = cls(rules, seed, best)
        run.offers = run._draft_offers(db)
        return run

    def _rng(self, purpose: str) -> random.Random:
        return random.Random(f"{self.seed}:{self.floor}:{purpose}:{self.rerolls}")

    # --- юниты ---

    @property
    def fielded(self) -> list:
        return self.squad.formation.units

    @property
    def reserve(self) -> list:
        return self.army.reserve()

    def starter_gear(self, db: Database, class_id: str) -> tuple[str, ...]:
        """Стартовое снаряжение: по предмету на каждый слот, кроме артефактов (из starter_gear или самый дешёвый).

        Предмет берётся только если класс может его надеть (game/unit.py class_allowed): иначе
        подбирается самый дешёвый разрешённый предмет того же слота и ступени.
        """
        named = self.rules.data.get("starter_gear", {})
        tier = self.rules.data.get("starter_tier", 1)
        class_ids = tuple(dict.fromkeys((class_id, *db.lineage(class_id))))
        story = db.units[class_id].story
        gear = []
        for slot in db.units[class_id].slots:
            if slot == ARTIFACT:
                continue
            item = named.get(slot)
            if item in db.items and db.items[item].slot == slot and class_allowed(db.items[item], class_ids, story):
                gear.append(item)
                continue
            fitting = [i for i in db.items.values()
                       if i.slot == slot and i.rank == tier and class_allowed(i, class_ids, story)]
            item = min(fitting, key=lambda i: i.price).id if fitting else None
            if item is not None:
                gear.append(item)
        return tuple(gear)

    def _add_unit(self, db: Database, class_id: str, level: int) -> int:
        unit = db.create_unit(class_id, self.next_uid, level, self.starter_gear(db, class_id))
        unit.state.nickname = self._new_name(class_id)
        self.next_uid += 1
        self.army.recruit(unit)
        formation = self.squad.formation
        taken = [formation.position_of(u.uid) for u in formation.units]
        cell = free_cell(taken, unit.definition, self.rules.squad_size(self.floor))
        if cell is not None:
            self.army.assign(unit.uid, PLAYER_SQUAD, *cell)
        return unit.uid

    def _new_name(self, class_id: str) -> str:
        """Личное имя нового бойца: из data/names.json, сначала те, что ещё не заняты в армии."""
        names = load_names(class_id)
        if not names:
            return ""
        taken = {u.state.nickname for u in self.army.units.values()}
        free = [n for n in names if n not in taken] or names
        return self._rng(f"name{self.next_uid}").choice(free)

    # --- набор отряда ---

    def _draft_offers(self, db: Database) -> list[str]:
        groups = self.rules.draft_groups()
        if self.draft_group >= len(groups):
            return []
        rng = self._rng(f"draft{self.draft_group}")
        pool = self.rules.draft_pool(db, groups[self.draft_group])
        choices = min(self.rules.data["draft"]["choices"], len(pool))
        return rng.sample(pool, choices) if choices else []

    def pick(self, db: Database, class_id: str) -> int:
        """Выбор бойца при наборе: группа за группой, после последней — подготовка к первому этажу."""
        if self.phase != DRAFT or class_id not in self.offers:
            raise ValueError(f"class {class_id!r} is not offered")
        uid = self._add_unit(db, class_id, self.rules.data["draft"]["level"])
        self.draft_group += 1
        if self.draft_group >= len(self.rules.draft_groups()):
            self.phase, self.offers = PREPARE, []
        else:
            self.offers = self._draft_offers(db)
        return uid

    # --- расстановка ---

    def place(self, uid: int, row: int, col: int) -> None:
        """Ставит юнита в клетку: стоящий в отряде меняется местами, из запаса — вытесняет занявшего."""
        formation = self.squad.formation
        position = formation.position_of(uid)
        if position is not None:
            formation.swap(position, (row, col))
            return
        occupant = formation.unit_at(row, col)
        if occupant is not None:
            self.army.unassign(occupant.uid)
        self.army.assign(uid, PLAYER_SQUAD, row, col)    # FormationError, если отряд полон

    def bench(self, uid: int) -> None:
        self.army.unassign(uid)

    def field(self, uid: int) -> tuple[int, int]:
        """Из резерва в отряд, на лучшую свободную клетку для класса. ValueError, если отряд полон."""
        formation = self.squad.formation
        if formation.position_of(uid) is not None:
            return formation.position_of(uid)
        taken = [formation.position_of(u.uid) for u in formation.units]
        cell = free_cell(taken, self.army.units[uid].definition, self.rules.squad_size(self.floor))
        if cell is None:
            raise ValueError("the squad is full")
        self.army.assign(uid, PLAYER_SQUAD, *cell)
        return cell

    def _resize(self) -> None:
        """Поле этажа: кто не помещается в новое поле, уходит в запас."""
        size = self.rules.squad_size(self.floor)
        old = self.squad.formation
        if (old.rows, old.cols, old.max_units) == (size.rows, size.cols, size.max_units):
            return
        placed = [(unit, old.position_of(unit.uid)) for unit in old.units]
        self.squad.formation = Formation(size)
        for unit, (row, col) in placed:
            if self.squad.formation.contains(row, col) and len(self.squad.formation) < size.max_units:
                self.squad.formation.place(unit, row, col)
        if self.squad.formation.position_of(self.squad.leader_uid or -1) is None:
            units = self.squad.formation.units
            self.squad.leader_uid = units[0].uid if units else None

    # --- бой ---

    def enemy_roster(self, db: Database) -> list[tuple[str, int, tuple[str, ...], int, int]]:
        """Враги этажа: (класс, уровень, снаряжение, ряд, колонна). У главаря первый — вожак."""
        rules, floor = self.rules, self.floor
        rng = random.Random(f"{self.seed}:{floor}:enemy")
        pool = rules.enemy_classes(db)
        grid = rules.squad_size(floor)
        size = FormationSize(grid.rows, grid.cols, grid.rows * grid.cols)
        level, tier = rules.enemy_level(floor), rules.gear_tier(floor)
        roster, taken = [], []
        for index in range(rules.enemy_count(floor)):
            class_id = rng.choices(list(pool), weights=list(pool.values()))[0]
            unit_level = level + (rules.data["boss"]["leader_level_bonus"] if rules.is_boss(floor) and index == 0 else 0)
            unit_level = min(unit_level, rules.exp.max_level)
            chance = rules.enemy_promotion(floor)
            while True:                                   # повышение по случайному открытому пути
                paths = [p for p in db.units[class_id].promotions
                         if p.level <= unit_level and p.class_id in db.units and not db.units[p.class_id].story]
                if not paths or rng.random() >= chance:
                    break
                class_id = rng.choice(paths).class_id
            definition = db.definition_for(class_id, db.lineage(class_id))
            cell = free_cell(taken, definition, size)
            if cell is None:
                break
            taken.append(cell)
            gear = self._enemy_gear(db, definition, tier, rng)
            roster.append((class_id, unit_level, gear, *cell))
        return roster

    def _enemy_gear(self, db: Database, definition: UnitDefinition, tier: int, rng: random.Random) -> tuple[str, ...]:
        """Тир 0 — враги без снаряжения (лёгкие первые этажи). Берутся только разрешённые классу предметы."""
        gear = []
        if tier < 1:
            return ()
        class_ids = tuple(dict.fromkeys((definition.id, *(a.id for a in definition.ancestors))))
        for slot in definition.slots:
            if slot == ARTIFACT and rng.random() >= self.rules.artifact_chance(self.floor):
                continue
            # Лучший доступный тир, не выше нужного
            for wanted in range(tier, 0, -1):
                fitting = sorted(i.id for i in db.items.values() if i.slot == slot and i.rank == wanted
                                 and class_allowed(i, class_ids, definition.story))
                if fitting:
                    gear.append(rng.choice(fitting))
                    break
        return tuple(gear)

    def battle(self, db: Database) -> Scenario:
        """Бой этажа на копиях бойцов с полным здоровьем; сам забег бой не меняет."""
        if self.phase != PREPARE or not self.fielded:
            raise ValueError("nobody is fielded")
        player = Army("player", "Player")
        squad = player.create_squad(PLAYER_SQUAD, "Tower", self.rules.squad_size(self.floor))
        for unit in self.fielded:
            clone = unit_from_save(db, unit_to_save(unit))
            if clone is None:
                continue
            clone.state.current_hp = clone.max_hp
            player.recruit(clone)
            player.assign(clone.uid, PLAYER_SQUAD, *self.squad.formation.position_of(unit.uid))
        enemy = Army("enemy", "Enemy")
        roster = self.enemy_roster(db)
        size = self.rules.squad_size(self.floor)
        enemy_squad = enemy.create_squad(ENEMY_SQUAD, "Floor", FormationSize(size.rows, size.cols, size.rows * size.cols))
        for offset, (class_id, level, gear, row, col) in enumerate(roster):
            unit = enemy.recruit(db.create_unit(class_id, ENEMY_FIRST_UID + offset, level, gear))
            enemy.assign(unit.uid, ENEMY_SQUAD, row, col)
        world = WorldMap(*MAP_SIZE)
        world.place(squad.id, 3, 2)
        world.place(enemy_squad.id, 4, 2)
        return Scenario(player, enemy, world, squad, enemy_squad)

    def finish(self, db: Database, scenario: Scenario, won: bool) -> BattleReport:
        """Итог боя этажа: при победе опыт всем участникам (и павшим), золото и предметы на выбор."""
        if self.phase != PREPARE:
            raise ValueError("no battle in progress")
        boss = self.rules.is_boss(self.floor)
        report = BattleReport(self.floor, won, boss)
        if not won:
            self.phase = OVER
            self.best = max(self.best, self.floor - 1)
        else:
            enemy_levels = [unit.state.level for unit in scenario.enemy_squad.formation.units]
            for fighter in scenario.player_squad.formation.units:
                unit = self.army.units.get(fighter.uid)
                if unit is None:
                    continue
                exp = self.rules.exp.battle_exp(unit.state.level, enemy_levels)
                report.level_ups.append(grant_exp(unit, exp, self.rules.exp))
            report.gold = self.rules.gold(self.floor)
            self.inventory.add_gold(report.gold)
            self.best = max(self.best, self.floor)
            self.reward = self._offer_items(db, self._rng("reward"), self.rules.data["reward"]["offer"])
            self.phase = REWARD
        for unit in self.army.units.values():
            unit.state.current_hp = unit.max_hp
        self.report = report
        return report

    # --- награда ---

    def _offer_items(self, db: Database, rng: random.Random, count: int) -> list[str]:
        """Предметы на выбор: тир по весам этажа, внутри тира — случайный, без повторов, пока хватает."""
        by_tier: dict[int, list[str]] = {}
        for item in db.items.values():
            by_tier.setdefault(item.rank, []).append(item.id)
        if not by_tier:
            return []
        weights = self.rules.tier_weights(self.floor)
        offer: list[str] = []
        for _ in range(count):
            tier = rng.choices(range(1, len(weights) + 1), weights=weights)[0]
            # Нет предметов такого тира — ближайший имеющийся
            tier = min(by_tier, key=lambda t: (abs(t - tier), t))
            fresh = [i for i in by_tier[tier] if i not in offer] or by_tier[tier]
            offer.append(rng.choice(fresh))
        return offer

    def take(self, db: Database, indices: Sequence[int]) -> None:
        """Забирает выбранные предметы награды (не больше take) и идёт дальше."""
        if self.phase != REWARD:
            raise ValueError("no reward to take")
        chosen = list(dict.fromkeys(indices))
        if len(chosen) > self.rules.data["reward"]["take"] or any(not 0 <= i < len(self.reward) for i in chosen):
            raise ValueError("wrong reward choice")
        for index in chosen:
            self.inventory.add(self.reward[index])
        self.reward = []
        done = self.floor
        self.floor += 1
        self._resize()
        if self.rules.shop_after(done):
            self.phase, self.rerolls = SHOP, 0
            self._stock_shop(db)
        else:
            self.phase = PREPARE

    # --- магазин ---

    def _stock_shop(self, db: Database) -> None:
        """Бойцы на найм (уровень — средний по армии) и предметы по весам тиров этажа."""
        rng = self._rng("shop")
        shop = self.rules.data["shop"]
        level = max(1, sum(u.state.level for u in self.army.units.values()) // max(1, len(self.army.units)))
        pool = base_classes(db)
        fresh = rng.sample(pool, min(shop["recruits"], len(pool))) if pool else []
        self.recruits = [(class_id, level) for class_id in fresh]
        self.shop_items = list(self._offer_items(db, rng, shop["items"]))

    def hire(self, db: Database, index: int) -> int:
        offer = self.recruits[index]
        if self.phase != SHOP or offer is None or offer[0] not in db.units:
            raise ValueError("recruit is not available")
        if not self.inventory.spend_gold(self.rules.recruit_price(offer[1])):
            raise ValueError("not enough gold")
        self.recruits[index] = None
        return self._add_unit(db, *offer)

    def buy(self, db: Database, index: int) -> None:
        item_id = self.shop_items[index]
        if self.phase != SHOP or item_id is None or item_id not in db.items:
            raise ValueError("item is not available")
        if not self.inventory.spend_gold(db.items[item_id].price):
            raise ValueError("not enough gold")
        self.shop_items[index] = None
        self.inventory.add(item_id)

    def sell(self, db: Database, item_id: str) -> int:
        if self.phase != SHOP or item_id not in db.items or not self.inventory.remove(item_id):
            raise ValueError("nothing to sell")
        price = self.rules.sell_price(db, item_id)
        self.inventory.add_gold(price)
        return price

    def reroll(self, db: Database) -> None:
        if self.phase != SHOP or not self.inventory.spend_gold(self.rules.reroll_price(self.rerolls)):
            raise ValueError("not enough gold")
        self.rerolls += 1
        self._stock_shop(db)

    # --- повышение ---

    def promote(self, db: Database, uid: int, class_id: str) -> None:
        """Повысить бойца армии (на подготовке): game/promotion.py."""
        if self.phase != PREPARE or uid not in self.army.units:
            raise ValueError("promotion is only possible while preparing")
        promote(db, self.army.units[uid], class_id)

    def leave_shop(self) -> None:
        if self.phase == SHOP:
            self.phase, self.recruits, self.shop_items = PREPARE, [], []

    # --- сохранение ---

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SAVE_VERSION, "seed": self.seed, "best": self.best, "floor": self.floor,
            "phase": self.phase, "next_uid": self.next_uid, "rerolls": self.rerolls,
            "draft_group": self.draft_group,
            "units": [unit_to_save(u) for u in self.army.units.values()],
            "cells": [[u.uid, *self.squad.formation.position_of(u.uid)] for u in self.fielded],
            "inventory": self.inventory.to_dict(),
            "offers": list(self.offers), "reward": list(self.reward),
            "recruits": [list(r) if r else None for r in self.recruits],
            "shop_items": list(self.shop_items),
            "report": self.report.to_dict() if self.report else None,
        }

    @classmethod
    def from_dict(cls, db: Database, rules: TowerRules, data: Mapping[str, Any]) -> "TowerRun":
        """Юниты исчезнувших классов пропадают; кто не помещается в поле — в запасе."""
        if data.get("version") != SAVE_VERSION:
            raise ValueError(f"unsupported tower save version {data.get('version')!r}")
        run = cls(rules, data["seed"], data.get("best", 0))
        run.floor, run.phase = data["floor"], data["phase"]
        run.next_uid, run.rerolls = data["next_uid"], data.get("rerolls", 0)
        run.squad.formation = Formation(rules.squad_size(run.floor))
        returned: list[str] = []
        for unit_data in data["units"]:
            unit = unit_from_save(db, unit_data)
            if unit is None:
                continue
            run.army.recruit(unit)
            # Снаряжение, которое класс больше не носит (ограничения по классам или слоты),
            # возвращается в инвентарь, а не пропадает (Counter: сколько штук не поместилось).
            saved = [i for i in (unit_data.get("state") or {}).get("equipment", ()) if i]
            now = [i for i in unit.state.equipment if i]
            for item_id, count in (Counter(saved) - Counter(now)).items():
                if item_id in db.items:
                    returned.extend([item_id] * count)
        for uid, row, col in data["cells"]:
            formation = run.squad.formation
            if uid in run.army.units and formation.contains(row, col) and len(formation) < formation.max_units \
                    and formation.unit_at(row, col) is None:
                run.army.assign(uid, PLAYER_SQUAD, row, col)
        run.inventory = Inventory.from_dict(data["inventory"])
        for item_id in returned:
            run.inventory.add(item_id)
        run.offers = [c for c in data.get("offers", ()) if c in db.units]
        run.reward = [i for i in data.get("reward", ()) if i in db.items]
        run.recruits = [tuple(r) if r else None for r in data.get("recruits", ())]
        run.shop_items = list(data.get("shop_items", ()))
        run.report = BattleReport.from_dict(data["report"]) if data.get("report") else None
        # Старые сохранения без draft_group: считаем, что выбрано столько групп, сколько бойцов.
        groups = rules.draft_groups()
        run.draft_group = max(0, min(int(data.get("draft_group", len(run.army.units))), len(groups)))
        if run.phase == DRAFT and not run.offers:
            if run.draft_group < len(groups):
                run.offers = run._draft_offers(db)
            else:
                run.phase = PREPARE
        return run

    def rebuild(self, db: Database, rules: Optional[TowerRules] = None) -> "TowerRun":
        """Тот же забег по заново прочитанным данным (справочник или правила правили в демо)."""
        return TowerRun.from_dict(db, rules or self.rules, self.to_dict())

    def save(self, path: Union[str, Path]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, db: Database, rules: TowerRules, path: Union[str, Path]) -> "TowerRun":
        return cls.from_dict(db, rules, json.loads(Path(path).read_text(encoding="utf-8")))
