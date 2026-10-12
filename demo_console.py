"""Консольное демо: карта -> столкновение -> бой -> итог.

Запуск: python demo_console.py [seed] [--saved] [--lang ru]
--saved берёт расстановку, сохранённую редакторами (saves/setup.json), вместо демо.
--lang выбирает язык вывода (en по умолчанию, остальные из data/lang/).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from game.battle import BattleSimulation
from game.database import Database
from game.events import format_event
from game.i18n import DEFAULT_LANG, Translator, available_languages
from game.save import DEFAULT_SETUP_PATH, load_setup
from game.scenario import Scenario, build_demo
from game.squad import Formation, Squad
from game.stats import Stat
from game.unit import Unit
from game.world import WorldMap

CELL_WIDTH = 14
STAT_SHORT = {
    Stat.HP: "HP", Stat.PHYS_ATK: "PATK", Stat.PHYS_DEF: "PDEF", Stat.MAG_ATK: "MATK", Stat.MAG_DEF: "MDEF",
    Stat.INITIATIVE: "INIT", Stat.ACCURACY: "ACC", Stat.EVASION: "EVA", Stat.CRIT_RATE: "CRIT",
    Stat.CRIT_DAMAGE: "CDMG", Stat.GUARD_RATE: "GRD",
}


def label(unit: Unit, t: Translator) -> str:
    return f"{t(unit.name)}({unit.uid})"


def render_map(world: WorldMap, marks: dict[str, str]) -> str:
    lines = []
    for y in range(world.height):
        row = []
        for x in range(world.width):
            squad_id = world.squad_at(x, y)
            row.append(marks.get(squad_id, ".") if squad_id else ".")
        lines.append(" ".join(row))
    return "\n".join(lines)


def render_formation(squad: Squad, t: Translator) -> str:
    """Сетка 3x3, верхняя строка = передний ряд. Под ней статы и слоты снаряжения."""
    lines = [t("{squad} (leader uid {uid})", squad=t(squad.name), uid=squad.leader_uid)]
    front = t("front")
    for row in range(Formation.ROWS):
        cells = []
        for col in range(Formation.COLS):
            unit = squad.formation.unit_at(row, col)
            cells.append((label(unit, t) if unit else ".").center(CELL_WIDTH))
        tag = front if row == 0 else " " * len(front)
        lines.append(f"  {tag} |" + "|".join(cells) + "|")
    for unit in squad.formation.units:
        stats = " ".join(f"{STAT_SHORT[s]} {unit.stat(s)}" for s in Stat)
        slots = ", ".join(
            f"{t(slot)}: {t(item_id) if item_id else '-'}"
            for slot, item_id in zip(unit.definition.slots, unit.state.equipment)
        )
        tags = ", ".join(t(tag) for tag in sorted(unit.tags)) or "-"
        lines.append(f"    {label(unit, t):<14} L{unit.state.level}  AP {unit.ap.max} PP {unit.pp.max}  {t('tags')}: {tags}")
        lines.append(f"      {stats}")
        lines.append(f"      {t('slots')}: {slots}")
    return "\n".join(lines)


def print_summary(sim: BattleSimulation, t: Translator) -> None:
    print("\n" + t("Survivors:"))
    for squad in (sim.attacker, sim.defender):
        alive = [u for u in squad.formation.units if u.is_alive]
        names = ", ".join(f"{label(u, t)} HP {u.hp}/{u.max_hp}" for u in alive) or t("none")
        print(f"  {t(squad.name)}: {names}")


def print_save_example(scenario: Scenario, t: Translator) -> None:
    """Сохраняется только UnitState и компактный список эффектов."""
    units = scenario.player_squad.formation.units
    unit = next((u for u in units if u.is_alive), units[0])
    save = {"state": asdict(unit.state), "effects": unit.save_effects()}
    print("\n" + t("Save example for {unit}:", unit=label(unit, t)))
    print(json.dumps(save, indent=2))


def main(seed: int = 1, saved: bool = False, lang: str = DEFAULT_LANG) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # кириллица при выводе в файл или конвейер
    t = Translator.load(lang)
    db = Database.load()
    scenario = load_setup(DEFAULT_SETUP_PATH, db) if saved else build_demo(db)
    attacker, defender = scenario.player_squad, scenario.enemy_squad

    print(t("World map {w}x{h} (A = {a}, B = {b}):", w=scenario.world.width, h=scenario.world.height,
            a=t(attacker.name), b=t(defender.name)))
    print(render_map(scenario.world, {attacker.id: "A", defender.id: "B"}))
    print()
    print(render_formation(attacker, t))
    print()
    print(render_formation(defender, t))

    if not scenario.world.are_adjacent(attacker.id, defender.id):
        print("\n" + t("Squads are not adjacent, no battle."))
        return
    print("\n" + t("{a} at {pa} clashes with {b} at {pb} (seed {seed})", a=t(attacker.name),
                   pa=scenario.world.position_of(attacker.id), b=t(defender.name),
                   pb=scenario.world.position_of(defender.id), seed=seed) + "\n")

    sim = BattleSimulation(attacker, defender, db, seed=seed)
    for event in sim.run():
        print(format_event(event, lambda uid: label(sim.units[uid], t), t))

    print_summary(sim, t)
    print_save_example(scenario, t)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Squad auto-battle console demo")
    parser.add_argument("seed", nargs="?", type=int, default=1)
    parser.add_argument("--saved", action="store_true", help="use the setup saved by the editors")
    parser.add_argument("--lang", default=DEFAULT_LANG, choices=available_languages())
    args = parser.parse_args()
    main(args.seed, args.saved, args.lang)
