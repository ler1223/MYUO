"""Формулы UO (справка игры: «Damage», «Accuracy and Evasion», «Critical Hits», «Guarding»).

    Физический урон = (Phys. ATK − Phys. DEF) × (физическая сила / 100)
    Магический урон = (Mag. ATK − Mag. DEF) × (магическая сила / 100)
    Урон = физический + магический, затем — блок, крит, особенности классов, усиления.
    Попадание = (Accuracy − Evasion) × точность навыка, затем — особенности классов и усиления.

В данных навык — части (SkillPart): у каждой своя категория (physical — защита Phys. DEF и блок,
magical — Mag. DEF, pure — без защиты), сила power (1.0 = 100) и значение атаки scaling
(сумма статов применяющего × коэффициент). Блок снимает долю только физической части.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Optional

from ..definitions import MAGICAL, PART_DAMAGE, PART_HEAL, PART_HEAL_PCT, PHYSICAL, SkillDefinition, SkillPart
from ..effects import AttackMod
from ..stats import Stat
from ..tags import TagRule, rule_multipliers
from ..unit import Unit

MIN_DAMAGE = 1            # попавший удар с уроном снимает хотя бы столько


@dataclass
class Attack:
    """Всё, что нужно удару: кто, каким навыком, с какими поправками."""

    user: Unit
    skill: SkillDefinition
    tags: frozenset[str]                  # теги атаки: навыка, оружия, атакующего, поправок
    mods: list[AttackMod]                 # поправки эффектов применяющего (зачарование, «следующий удар»)
    potency: float = 0.0                  # прибавка к силе каждой части урона (условная сила навыка)

    @property
    def power_mult(self) -> float:
        k = 1.0
        for mod in self.mods:
            k *= mod.power_mult
        return k


def attack_value(user: Unit, part: SkillPart, mods: Iterable[AttackMod]) -> float:
    value = sum(user.stat(s.stat) * s.coef for s in part.scaling)
    for mod in mods:
        value += sum(user.stat(s.stat) * s.coef for s in mod.add_scaling)
    return value


def hit_chance(attack: Attack, target: Unit, rules: Iterable[TagRule], ignore_evasion: bool = False) -> float:
    """Шанс попадания 0..100 (может быть больше 100 — тогда попадает всегда)."""
    if attack.skill.extras.truestrike:
        return 1000.0
    evasion = 0 if ignore_evasion or target.has_flag("frozen") else target.stat(Stat.EVASION)
    chance = (attack.user.stat(Stat.ACCURACY) - evasion) * attack.skill.accuracy / 100
    chance *= rule_multipliers(rules, attack.tags, target.tags)[1]
    return chance + sum(m.accuracy_add for m in attack.mods)


def crit_chance(attack: Attack) -> float:
    if attack.skill.extras.no_crit or attack.user.has_flag("crit_seal"):
        return 0.0
    return (attack.user.stat(Stat.CRIT_RATE) + attack.skill.extras.crit_add
            + sum(m.crit_add for m in attack.mods))


def can_guard(attack: Attack, target: Unit, unblockable_tags: frozenset[str] = frozenset()) -> bool:
    """Может ли цель блокировать удар: нет печати блока, не заморожена, не оглушена, навык не
    неблокируемый (всегда или против её тегов) и в нём есть физическая часть."""
    skill = attack.skill
    if skill.extras.unguardable or any(tag in target.tags for tag in skill.extras.unguardable_vs):
        return False
    if attack.user.has_flag("unguardable"):
        return False
    if any(target.has_flag(f) for f in ("guard_seal", "frozen", "stunned")):
        return False
    if unblockable_tags and any(tag in unblockable_tags for tag in attack.tags):
        return False                         # тип урона, который не блокируется (дробящий и т. п.)
    return any(p.kind == PART_DAMAGE and p.category == PHYSICAL for p in skill.parts)


def damage(attack: Attack, target: Unit, rules: Iterable[TagRule], crit: bool,
           guard_cut: float) -> int:
    """Урон одного удара по цели: части по формуле UO, блок — по физической части, крит, особенности."""
    skill, user = attack.skill, attack.user
    ignore = skill.extras.ignore_def
    if any(tag in target.tags for tag in skill.extras.ignore_def_vs):
        ignore = 1.0
    physical = magical = 0.0
    for part in skill.parts:
        if part.kind != PART_DAMAGE:
            continue
        atk = attack_value(user, part, attack.mods)
        if part.category == PHYSICAL:
            defense = target.stat(Stat.PHYS_DEF)
        elif part.category == MAGICAL:
            defense = target.stat(Stat.MAG_DEF)
        else:
            defense = 0
        value = max(0.0, atk - defense * (1 - ignore)) * (part.power + attack.potency)
        if part.category == PHYSICAL:
            physical += value
        else:
            magical += value
    total = physical * (1 - guard_cut) + magical
    total *= attack.power_mult
    total *= rule_multipliers(rules, attack.tags, target.tags)[0]
    for tag, mult in skill.bonus_vs:
        if tag in target.tags:
            total *= mult
    if crit:
        total *= user.stat(Stat.CRIT_DAMAGE) / 100
    total *= max(0.0, 1 - target.trait("damage_reduction") / 100)       # «получает N% меньше урона»
    return max(MIN_DAMAGE, round(total)) if any(p.kind == PART_DAMAGE for p in skill.parts) else 0


def healing(attack: Attack, target: Unit, crit: bool) -> int:
    """Лечение частями навыка (по значению атаки или долей макс. HP цели)."""
    total = 0.0
    for part in attack.skill.parts:
        if part.kind == PART_HEAL:
            total += attack_value(attack.user, part, attack.mods) * (part.power + attack.potency)
        elif part.kind == PART_HEAL_PCT:
            total += target.max_hp * part.power
    total *= attack.power_mult
    if crit:
        total *= attack.user.stat(Stat.CRIT_DAMAGE) / 100
    return round(total)


def roll(rng: random.Random, chance: float) -> bool:
    """Бросок шанса в процентах."""
    return chance >= 100 or (chance > 0 and rng.random() * 100 < chance)


def guard_level(target: Unit, guard, forced: Optional[str]) -> str:
    """Сила блока: навыка блока (forced), иначе по щиту цели."""
    return forced or guard.level_of(target.tags)
