"""Сценарии: демо (две армии по отряду на соседних клетках), бой тестовых классов визуала
и демонстрационный бой с как можно большим числом разных навыков и пассивок."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional, Sequence

from .database import Database
from .squad import Squad
from .stats import Stat
from .tactics import Always, Frontmost, HpBelow, TacticRule, TacticsSet, Weakest
from .world import Army, WorldMap

MAP_SIZE = (8, 6)


@dataclass
class Scenario:
    player: Army
    enemy: Army
    world: WorldMap
    player_squad: Squad
    enemy_squad: Squad


def full_level(db: Database, class_id: str, level: int) -> int:
    """Уровень не ниже того, с которого у класса открыты все навыки и пассивки: демо показывает всё."""
    return max(level, db.units[class_id].top_unlock)


def pick(db: Database, candidates) -> Optional[str]:
    """Первый класс из кандидатов, который есть в справочнике (классы UO, иначе прежние)."""
    for class_id in (candidates,) if isinstance(candidates, str) else candidates:
        if class_id in db.units:
            return class_id
    return None


def fitting(db: Database, class_id: str, items: Sequence[str]) -> tuple[str, ...]:
    """Предметы из списка, которые есть и влезают в слоты класса (каждый слот — один раз)."""
    free = list(db.definition_for(class_id, db.lineage(class_id)).slots)
    chosen = []
    for item_id in items:
        item = db.items.get(item_id)
        if item is not None and item.slot in free:
            free.remove(item.slot)
            chosen.append(item_id)
    return tuple(chosen)


def _build_army(db: Database, army_id: str, name: str, squad_id: str, squad_name: str, roster, first_uid: int,
                show_all: bool = False):
    """roster: список (класс или кандидаты, level, equipment, row, col). show_all: уровни до full_level.
    Классы, которых нет, пропускаются; неподходящие предметы не надеваются."""
    army = Army(army_id, name)
    squad = army.create_squad(squad_id, squad_name, db.formation)
    roster = [(pick(db, c), level, equipment, row, col) for c, level, equipment, row, col in roster]
    roster = [(c, level, fitting(db, c, equipment), row, col) for c, level, equipment, row, col in roster if c]
    for offset, (definition_id, level, equipment, row, col) in enumerate(roster):
        if show_all:
            level = full_level(db, definition_id, level)
        unit = army.recruit(db.create_unit(definition_id, first_uid + offset, level, equipment))
        army.assign(unit.uid, squad_id, row, col)
    return army, squad


def build_demo(db: Database) -> Scenario:
    player, player_squad = _build_army(
        db, "player", "Player", "vanguard", "Vanguard",
        [
            (("fighter", "knight"), 3, ("iron_sword", "shield"), 0, 1),
            (("hunter", "archer"), 1, ("short_bow",), 1, 0),
            (("wizard", "mage"), 1, ("oak_staff",), 1, 2),
            ("cleric", 1, ("oak_staff",), 2, 1),
        ],
        first_uid=1, show_all=True,
    )
    enemy, enemy_squad = _build_army(
        db, "enemy", "Enemy", "raiders", "Raiders",
        [
            (("gladiator", "orc"), 2, ("war_axe",), 0, 1),
            (("thief", "goblin"), 2, ("rusty_dagger", "iron_sword"), 0, 0),
            (("rider", "knight"), 2, ("lance",), 0, 2),
            (("wizard", "mage"), 2, ("oak_staff",), 1, 1),
        ],
        first_uid=11, show_all=True,
    )
    world = WorldMap(*MAP_SIZE)
    world.place(player_squad.id, 3, 2)
    world.place(enemy_squad.id, 4, 2)
    return Scenario(player, enemy, world, player_squad, enemy_squad)


# Пять тестовых классов визуала (docs/test_classes.md): (класс, предметы, ряд, колонна) у каждой стороны.
# Классы UO со спрайтами тестовых классов (паладин, всадник, охотник, пиромант, клирик), иначе прежние.
SHOWCASE_PLAYER = (
    (("lord", "paladin"), ("iron_sword", "shield"), 0, 1),
    (("rider", "knight"), ("lance",), 0, 2),
    ("hunter", ("short_bow",), 1, 0),
    (("warlock", "pyromancer"), ("oak_staff",), 1, 2),
    ("cleric", ("oak_staff",), 2, 1),
)
SHOWCASE_ENEMY = (
    (("lord", "paladin"), ("iron_sword", "shield"), 0, 0),
    (("rider", "knight"), ("lance",), 0, 2),
    (("warlock", "pyromancer"), ("oak_staff",), 1, 1),
    ("hunter", ("short_bow",), 2, 0),
    ("cleric", ("oak_staff",), 2, 2),
)


def build_showcase(db: Database, level: int = 3) -> Scenario:
    """Бой тестовых классов против них же. Классы и предметы, которых нет в справочнике, пропускаются;
    если не осталось никого, берётся обычное демо."""
    def roster(entries):
        return [(pick(db, cls), level, items, row, col) for cls, items, row, col in entries if pick(db, cls)]

    player_roster, enemy_roster = roster(SHOWCASE_PLAYER), roster(SHOWCASE_ENEMY)
    if not player_roster or not enemy_roster:
        return build_demo(db)
    player, player_squad = _build_army(db, "player", "Player", "vanguard", "Vanguard", player_roster, first_uid=1,
                                       show_all=True)
    enemy, enemy_squad = _build_army(db, "enemy", "Enemy", "raiders", "Raiders", enemy_roster, first_uid=11,
                                     show_all=True)
    world = WorldMap(*MAP_SIZE)
    world.place(player_squad.id, 3, 2)
    world.place(enemy_squad.id, 4, 2)
    return Scenario(player, enemy, world, player_squad, enemy_squad)


# --- демонстрационный бой: как можно больше разных навыков и пассивок ------------

# 18 разных классов UO (иначе прежних): (кандидаты, ряд, колонна).
DEMO_PLAYER = (
    (("lord", "paladin"), 0, 1), (("fighter",), 0, 0), (("rider", "knight"), 0, 2),
    (("hunter",), 1, 0), (("soldier", "spearman"), 1, 1), (("shaman", "stormcaller"), 1, 2),
    (("wizard", "pyromancer"), 2, 0), (("cleric",), 2, 1), (("witch",), 2, 2),
)
DEMO_ENEMY = (
    (("hoplite", "knight"), 0, 1), (("gladiator", "orc"), 0, 0), (("thief", "goblin"), 0, 2),
    (("arbalist", "archer"), 1, 0), (("sellsword", "cryomancer"), 1, 1), (("priestess", "mage"), 1, 2),
    (("radiant_knight", "cleric"), 2, 0), (("dark_knight", "rider"), 2, 1), (("gryphon_knight", "fighter"), 2, 2),
)
DEMO_LEVEL = 5
DEMO_AP = 8                 # запас AP в демонстрации: хватает, чтобы каждый показал все свои навыки
DEMO_HP = 3                 # во столько раз больше HP: юниты живут, пока не покажут навыки
DEMO_PP = 4                 # запас PP: пассивки срабатывают чаще
DEMO_SEED = 25              # на этом сиде 29 навыков (всё, кроме «Шквала» и whirlwind) и все 7 пассивок
DEMO_FRAGILE = ("thief", "goblin")  # эти без запаса HP: их гибель показывает реакции на смерть союзника


@dataclass(frozen=True)
class VarietyTactics(TacticsSet):
    """Тактика демонстрации: сначала навыки, которые юнит ещё не применял, потом как обычно.

    Помнит применённые навыки каждого юнита (used); у каждого боя своя тактика.
    """

    used: dict = field(default_factory=dict, compare=False, hash=False)

    def choose(self, actor, allies, enemies, rng, skills):
        done = self.used.setdefault(actor.uid, set())
        fresh = TacticsSet(tuple(rule for rule in self.rules if rule.skill_id not in done))
        picked = fresh.choose(actor, allies, enemies, rng, skills) or super().choose(actor, allies, enemies, rng, skills)
        if picked is not None:
            done.add(picked[0])
        return picked


def variety_rules(db: Database, class_id: str) -> tuple[TacticRule, ...]:
    """Правило на каждый навык класса: дорогие первыми (пока AP много), лечение — раненым."""
    skills = [db.skills[s] for s in db.units[class_id].skills if s in db.skills]
    rules = []
    for skill in sorted(skills, key=lambda s: -s.ap_cost):
        heals = skill.targets == "ally" and bool(skill.parts)
        rules.append(TacticRule(skill.id, HpBelow(0.9) if heals else Always(),
                                selector=Weakest() if heals else Frontmost()))
    return tuple(rules)


def auto_equipment(db: Database, class_id: str) -> tuple[str, ...]:
    """По предмету на каждый не-артефактный слот класса: первый подходящий из справочника."""
    chosen = []
    for slot in db.units[class_id].slots:
        item = next((i for i, d in db.items.items() if d.slot == slot and i not in chosen), None)
        if item is not None and slot != "artifact":
            chosen.append(item)
    return tuple(chosen)


def build_demo_battle(db: Database, level: int = DEMO_LEVEL) -> Scenario:
    """Бой для демонстрации визуала: все классы, все их пассивки, тактика разнообразия,
    у всех DEMO_AP очков действия, DEMO_PP очков пассивок и в DEMO_HP раз больше здоровья.

    Классы, которых нет в справочнике, пропускаются; если не осталось никого — обычное демо.
    """
    size = db.formation

    def roster(entries):
        """Классы из справочника, на клетках, которые есть на поле, не больше max_units."""
        chosen = [(pick(db, cls), row, col) for cls, row, col in entries]
        placed = [(cls, level, auto_equipment(db, cls), row, col) for cls, row, col in chosen
                  if cls and row < size.rows and col < size.cols]
        return placed[:size.max_units]

    player_roster, enemy_roster = roster(DEMO_PLAYER), roster(DEMO_ENEMY)
    if not player_roster or not enemy_roster:
        return build_demo(db)
    # Юниты строятся по копии справочника, где у классов больше AP; правила и data/ не меняются.
    demo_db = db.copy()
    for class_id, definition in demo_db.units.items():
        hp = 1 if class_id in DEMO_FRAGILE else DEMO_HP
        stats = dict(definition.base_stats)
        stats[Stat.HP] = stats.get(Stat.HP, 1) * hp
        growth = dict(definition.growth)
        growth[Stat.HP] = growth.get(Stat.HP, 0) * hp
        demo_db.units[class_id] = replace(definition, ap_max=max(definition.ap_max, DEMO_AP),
                                           pp_max=max(definition.pp_max, DEMO_PP), base_stats=stats, growth=growth)
    player, player_squad = _build_army(demo_db, "player", "Player", "vanguard", "Vanguard", player_roster, first_uid=1,
                                       show_all=True)
    enemy, enemy_squad = _build_army(demo_db, "enemy", "Enemy", "raiders", "Raiders", enemy_roster, first_uid=11,
                                     show_all=True)
    tactics = VarietyTactics()
    for squad in (player_squad, enemy_squad):
        for unit in squad.formation.units:
            unit.set_tactics(VarietyTactics(variety_rules(db, unit.definition.id), tactics.used))
    world = WorldMap(*MAP_SIZE)
    world.place(player_squad.id, 3, 2)
    world.place(enemy_squad.id, 4, 2)
    return Scenario(player, enemy, world, player_squad, enemy_squad)
