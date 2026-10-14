"""Тексты всплывающих подсказок: предмет, навык, пассивка, эффект, стат, класс и юнит.

Каждая функция возвращает строки (текст, цвет, шрифт) для UI.tip; пустой текст — отступ.
Описания собираются из данных (как в редакторах), поэтому новый навык или предмет
объясняется сам, без отдельного текста.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from game.database import Database
from game.editing import describe_reaction, describe_skill
from game.stats import ModOp, Stat
from game.unit import Unit
from pygame_ui import DIM, GREEN, RED, TEXT, YELLOW

TipLines = list[tuple[str, Any, str]]

TIER_COLORS = {1: (205, 205, 210), 2: (110, 170, 255), 3: (255, 170, 60)}
TIER_NAMES = {1: "novice", 2: "mercenary", 3: "hero"}
SKILL_COLOR = (120, 190, 255)
PASSIVE_COLOR = (200, 150, 255)
EFFECT_COLOR = (240, 200, 120)
# Цвет каждого стата: значки, подписи и полосы в интерфейсе.
STAT_COLORS = {
    Stat.HP: (100, 210, 120), Stat.PHYS_ATK: (240, 140, 70), Stat.PHYS_DEF: (170, 180, 200),
    Stat.MAG_ATK: (190, 120, 250), Stat.MAG_DEF: (110, 160, 245), Stat.INITIATIVE: (90, 215, 225),
    Stat.ACCURACY: (235, 215, 95), Stat.EVASION: (110, 225, 175), Stat.CRIT_RATE: (240, 95, 95),
    Stat.CRIT_DAMAGE: (225, 120, 140), Stat.GUARD_RATE: (205, 185, 145),
}
# Что делает стат (строка перевода).
STAT_HELP = {
    Stat.HP: "Health. At 0 the unit falls.",
    Stat.PHYS_ATK: "Power of physical skills.",
    Stat.PHYS_DEF: "Lowers physical damage taken.",
    Stat.MAG_ATK: "Power of magic skills and healing.",
    Stat.MAG_DEF: "Lowers magic damage taken.",
    Stat.INITIATIVE: "Who acts first in a round.",
    Stat.ACCURACY: "Chance to hit: skill accuracy x accuracy / 100 - target evasion.",
    Stat.EVASION: "Lowers the enemy's chance to hit.",
    Stat.CRIT_RATE: "Chance of a critical hit, %.",
    Stat.CRIT_DAMAGE: "Damage of a critical hit, % of normal.",
    Stat.GUARD_RATE: "Chance to block half of a physical hit (not blunt).",
}


def tier_color(tier: int):
    return TIER_COLORS.get(tier, YELLOW)


def modifier_text(t: Callable[..., str], mod) -> str:
    if mod.op is ModOp.FLAT:
        value = f"{mod.value:+g}"
    elif mod.op is ModOp.PERCENT_ADD:
        value = f"{mod.value * 100:+g}%"
    else:
        value = f"x{mod.value:g}"
    return f"{t(mod.stat.value)} {value}"


def effect_lines(t: Callable[..., str], db: Database, effect_id: str, indent: str = "  ") -> TipLines:
    """Эффект: длительность, изменения статов, особенности и поведение."""
    effect = db.effects.get(effect_id)
    if effect is None:
        return []
    head = t(effect.name)
    if effect.duration:
        head += " — " + t("{n} turns", n=effect.duration)
    lines = [(indent + head, EFFECT_COLOR, "small")]
    details = [modifier_text(t, m) for m in effect.modifiers]
    details += [t(flag) for flag in sorted(effect.flags)]
    details += [t(tag) for tag in effect.grants_tags]
    if details:
        lines.append((indent + "  " + ", ".join(details), TEXT, "small"))
    for reaction in effect.triggers:
        lines.append((indent + "  " + describe_reaction(reaction, db, t), DIM, "small"))
    return lines


def skill_tip(t: Callable[..., str], db: Database, skill_id: str, unlock: int = 1,
              level: Optional[int] = None) -> TipLines:
    skill = db.skills.get(skill_id)
    if skill is None:
        return [(skill_id, RED, "main")]
    lines: TipLines = [(t(skill.name), SKILL_COLOR, "main"), (t("Active skill"), DIM, "small")]
    parts = describe_skill(skill, db, t).split(" | ")
    lines += [(part, TEXT, "small") for part in parts]
    if skill.applies:
        lines.append(("", TEXT, "small"))
        lines.append((t("Effects:"), DIM, "small"))
        for apply in skill.applies:
            lines += effect_lines(t, db, apply.effect_id)
    lines += _unlock_lines(t, unlock, level)
    return lines


def passive_tip(t: Callable[..., str], db: Database, passive_id: str, unlock: int = 1,
                level: Optional[int] = None) -> TipLines:
    passive = db.passives.get(passive_id)
    if passive is None:
        return [(passive_id, RED, "main")]
    lines: TipLines = [(t(passive.name), PASSIVE_COLOR, "main"),
                       (t("Passive, costs {n} PP", n=passive.pp_cost), DIM, "small"),
                       (describe_reaction(passive.reaction, db, t), TEXT, "small")]
    if passive.reaction.effect_id in db.effects:
        lines += effect_lines(t, db, passive.reaction.effect_id)
    lines += _unlock_lines(t, unlock, level)
    return lines


def _unlock_lines(t: Callable[..., str], unlock: int, level: Optional[int]) -> TipLines:
    if unlock <= 1:
        return []
    locked = level is not None and level < unlock
    return [("", TEXT, "small"), (t("Unlocks at level {n}", n=unlock), RED if locked else GREEN, "small")]


def item_tip(t: Callable[..., str], db: Database, item_id: str, price: Optional[int] = None) -> TipLines:
    item = db.items.get(item_id)
    if item is None:
        return [(item_id, RED, "main")]
    lines: TipLines = [(t(item.name), tier_color(item.rank), "main"),
                       (f"{t(item.slot)} · {t(TIER_NAMES.get(item.rank, "tier"))} ({item.tier})", DIM, "small")]
    lines += [(modifier_text(t, m), TEXT, "small") for m in item.modifiers]
    if item.damage_tags:
        lines.append((t("Damage type: {list}", list=", ".join(t(d) for d in item.damage_tags)), TEXT, "small"))
    if item.tags:
        lines.append((t("Gives: {list}", list=", ".join(t(db.tags[x].name) if x in db.tags else x
                                                         for x in item.tags)), TEXT, "small"))
    for skill_id in item.skills:
        lines.append(("", TEXT, "small"))
        lines += skill_tip(t, db, skill_id)
    for passive_id in item.passives:
        lines.append(("", TEXT, "small"))
        lines += passive_tip(t, db, passive_id)
    wearers = [t(u.name) for u in db.units.values() if item.slot in u.slots]
    lines.append(("", TEXT, "small"))
    who = t("any class") if len(wearers) == len(db.units) else ", ".join(wearers) or "-"
    lines.append((t("Fits: {list}", list=who), DIM, "small"))
    if price is not None:
        lines.append((t("Price: {n}", n=price), YELLOW, "small"))
    return lines


def stat_tip(t: Callable[..., str], stat: Stat, value: Optional[int] = None) -> TipLines:
    title = t(stat.value) + (f": {value}" if value is not None else "")
    return [(title, STAT_COLORS.get(stat, TEXT), "main"), (t(STAT_HELP[stat]), TEXT, "small")]


def class_tip(t: Callable[..., str], db: Database, class_id: str, level: int) -> TipLines:
    """Класс (враг этажа, боец на найм): статы на уровне, теги и открытые навыки."""
    definition = db.units.get(class_id)
    if definition is None:
        return [(class_id, RED, "main")]
    unit = db.create_unit(class_id, 0, level)
    return unit_tip(t, db, unit)


def unit_tip(t: Callable[..., str], db: Database, unit: Unit) -> TipLines:
    definition = unit.definition
    tags = ", ".join(t(db.tags[x].name) for x in definition.tags if x in db.tags)
    lines: TipLines = [(f"{t(unit.name)} — {t('lv {n}', n=unit.state.level)}", YELLOW, "main")]
    if tags:
        lines.append((tags, DIM, "small"))
    stats = [f"{t(s.value)} {unit.stat(s)}" for s in (Stat.HP, Stat.PHYS_ATK, Stat.PHYS_DEF, Stat.MAG_ATK,
                                                      Stat.MAG_DEF, Stat.INITIATIVE)]
    lines.append((", ".join(stats), TEXT, "small"))
    skills = [t(db.skills[s].name) for s in unit.skill_ids if s in db.skills]
    passives = [t(db.passives[p].name) for p in unit.passive_ids if p in db.passives]
    if skills:
        lines.append((t("Skills: {list}", list=", ".join(skills)), SKILL_COLOR, "small"))
    if passives:
        lines.append((t("Passives: {list}", list=", ".join(passives)), PASSIVE_COLOR, "small"))
    gear = [t(db.items[i].name) for i in unit.state.equipment if i in db.items]
    if gear:
        lines.append((t("Gear: {list}", list=", ".join(gear)), DIM, "small"))
    return lines
