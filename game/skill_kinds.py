"""Тип навыка, как в UO: атака, поддержка, лечение или помеха.

Своей картинки у навыка нет — значок общий на тип (skill/<тип>, passive/<тип>). Тип не хранится
в данных, а выводится из самого навыка, поэтому он есть и у навыков, созданных в редакторе.
"""
from __future__ import annotations

from typing import Any

from .definitions import PART_DAMAGE, PART_HEAL, PART_HEAL_PCT
from .reactions import (DO_APPLY_EFFECT, DO_DAMAGE, DO_DISPEL, DO_HEAL, DO_REMOVE_EFFECT, DO_USE_SKILL, TO_ACTOR,
                        TO_ENEMIES, TO_SOURCE)

ATTACK = "attack"
SUPPORT = "support"
HEALING = "healing"
SABOTAGE = "sabotage"
KINDS = (ATTACK, SUPPORT, HEALING, SABOTAGE)
HARMFUL = {"debuff", "ailment"}             # метки эффектов, которые вешают врагу


def skill_kind(db: Any, skill_id: str) -> str:
    """Урон — атака; иначе лечение; иначе эффекты: на врага — помеха, на своих — поддержка."""
    skill = db.skills.get(skill_id)
    if skill is None:
        return SUPPORT
    parts = {part.kind for part in skill.parts}
    if PART_DAMAGE in parts:
        return ATTACK
    if parts & {PART_HEAL, PART_HEAL_PCT}:
        return HEALING
    return SABOTAGE if skill.targets == "enemy" else SUPPORT


def passive_kind(db: Any, passive_id: str) -> str:
    """По действию реакции: навык — его тип, урон — атака, лечение — лечение, вредный эффект врагу — помеха."""
    passive = db.passives.get(passive_id)
    if passive is None:
        return SUPPORT
    reaction = passive.reaction
    if reaction.action == DO_USE_SKILL:
        return skill_kind(db, reaction.skill_id)
    if reaction.action == DO_DAMAGE:
        return ATTACK
    if reaction.action == DO_HEAL:
        return HEALING
    if reaction.action in (DO_APPLY_EFFECT, DO_REMOVE_EFFECT):
        effect = db.effects.get(reaction.effect_id)
        harmful = effect is not None and bool(effect.tags & HARMFUL)
        return SABOTAGE if harmful == (reaction.action == DO_APPLY_EFFECT) else SUPPORT
    if reaction.action == DO_DISPEL and reaction.to in (TO_ACTOR, TO_SOURCE, TO_ENEMIES):
        return SABOTAGE
    return SUPPORT
