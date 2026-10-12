"""Операции редакторов без графики.

Редакторы работают с определениями в формате JSON (словари): берут
definition.to_dict(), меняют и отдают в Database.update(), который всё проверяет.
Здесь собраны заготовки новых объектов, варианты для выпадающих списков и описания.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

from .areas import AREA_SINGLE
from .database import Database, slugify
from .definitions import APPLY_SELF, APPLY_TARGET, MAGICAL, PART_DAMAGE, PHYSICAL, SkillDefinition
from .stats import STAT_DEFAULTS, Stat
from .tactics import CONDITIONS, TacticsSet
from .tags import TAG_UNIT
from .unit import DEFAULT_AP_MAX, DEFAULT_PP_MAX, Unit

__all__ = ["slugify"]  # реэкспорт для редакторов

FRACTIONS = tuple(round(0.1 * i, 1) for i in range(1, 11))
DEFAULT_FRACTION = 0.5
BUFF_TAG = "buff"

NEW_UNIT_STATS = {
    Stat.HP: 40, Stat.PHYS_ATK: 12, Stat.PHYS_DEF: 5, Stat.MAG_ATK: 12, Stat.MAG_DEF: 5, Stat.INITIATIVE: 5,
    Stat.ACCURACY: 100, Stat.EVASION: 5, Stat.CRIT_RATE: 5, Stat.CRIT_DAMAGE: 150, Stat.GUARD_RATE: 0,
}


# --- параметры условий -----------------------------------------------------

def condition_params(name: str) -> dict[str, str]:
    """{имя параметра: вид} для условия из реестра."""
    return dict(getattr(CONDITIONS[name], "PARAMS", {}))


def param_options(kind: str, db: Database) -> list[Any]:
    """Допустимые значения параметра условия по его виду."""
    if kind == "fraction":
        return list(FRACTIONS)
    if kind == "flag":
        return sorted({flag for effect in db.effects.values() for flag in effect.flags})
    if kind == "effect":
        return list(db.effects)
    if kind == "tag":
        return [tag.id for tag in db.tags.values() if tag.kind == TAG_UNIT]
    raise ValueError(f"unknown condition parameter kind {kind!r}")


def default_condition(name: str, db: Database) -> dict[str, Any]:
    """Условие в формате JSON с параметрами по умолчанию."""
    data: dict[str, Any] = {"type": name}
    for param, kind in condition_params(name).items():
        options = param_options(kind, db)
        data[param] = DEFAULT_FRACTION if kind == "fraction" else (options[0] if options else "")
    return data


def _same(text: str, **params: Any) -> str:
    return text


def describe_condition(data: Mapping[str, Any], t: Optional[Callable[..., str]] = None) -> str:
    """Текст условия; t переводит названия (тип условия, эффект, флаг, тег)."""
    t = t or _same
    params = " ".join(t(v) if isinstance(v, str) else str(v) for k, v in data.items() if k != "type")
    return f"{t(data['type'])} {params}".strip()


# --- тактики ---------------------------------------------------------------

def default_rule(skill_ids: Sequence[str]) -> dict[str, Any]:
    return {
        "skill": skill_ids[0],
        "self_condition": {"type": "always"},
        "condition": {"type": "always"},
        "selector": "frontmost",
    }


def set_tactics(db: Database, unit: Unit, rules: Sequence[Mapping[str, Any]]) -> None:
    """Заменяет тактики юнита правилами в формате JSON.

    Навык правила должен существовать; недоступный юниту навык в бою просто пропускается.
    """
    for rule in rules:
        if rule["skill"] not in db.skills:
            raise ValueError(f"unknown skill {rule['skill']!r}")
    unit.set_tactics(TacticsSet.from_list(rules))


def skill_users(skill_id: str, units: Iterable[Unit]) -> list[Unit]:
    """Юниты, в тактиках которых используется навык."""
    return [u for u in units if any(rule.skill_id == skill_id for rule in u.tactics.rules)]


# --- заготовки новых объектов ----------------------------------------------

def new_part(category: str = PHYSICAL) -> dict[str, Any]:
    stat = Stat.MAG_ATK if category == MAGICAL else Stat.PHYS_ATK
    return {"kind": PART_DAMAGE, "category": category, "power": 1.0,
            "scaling": [{"stat": stat.value, "coef": 1.0}], "tags": [], "weapon_tags": False}


def new_skill_data() -> dict[str, Any]:
    return {"ap_cost": 1, "pp_cost": 0, "targets": "enemy", "area": AREA_SINGLE, "hits": 1, "accuracy": 100, "parts": [new_part()]}


def new_unit_data(db: Database) -> dict[str, Any]:
    return {
        "stats": {stat.value: value for stat, value in NEW_UNIT_STATS.items()},
        "growth": {},
        "ap_max": DEFAULT_AP_MAX,
        "pp_max": DEFAULT_PP_MAX,
        "skills": ["attack"] if "attack" in db.skills else [],
    }


def new_item_data(db: Database) -> dict[str, Any]:
    return {"slot": db.slot_types[0]}


def new_effect_data() -> dict[str, Any]:
    return {"duration": 3, "tags": ["debuff"]}


def new_area_data() -> dict[str, Any]:
    return {"cells": [[0, 0]]}


def new_tag_data() -> dict[str, Any]:
    return {"kind": TAG_UNIT}


def new_rule_data() -> dict[str, Any]:
    return {"attack": [], "attack_not": [], "target": [], "damage": 1.0, "hit": 1.0}


def default_apply(db: Database, effect_id: str) -> dict[str, Any]:
    """Положительный эффект по умолчанию идёт на себя, остальные на цель."""
    to = APPLY_SELF if BUFF_TAG in db.effects[effect_id].tags else APPLY_TARGET
    return {"effect_id": effect_id, "to": to, "condition": {"type": "always"}}


def stat_default(stat: Stat) -> float:
    return STAT_DEFAULTS.get(stat, 0)


def set_owners(db: Database, section: str, skill_id: str, owner_ids: Sequence[str], field: str = "skills") -> None:
    """Делает навык доступным ровно перечисленным классам (section="units") или предметам ("items").

    field="passives" делает то же для пассивки.
    """
    for owner in list(getattr(db, section).values()):
        has, wanted = skill_id in getattr(owner, field), owner.id in owner_ids
        if has == wanted:
            continue
        data = owner.to_dict()
        data[field] = [s for s in data[field] if s != skill_id] + ([skill_id] if wanted else [])
        db.update(section, owner.id, data)


def skill_owners(db: Database, section: str, skill_id: str, field: str = "skills") -> list[str]:
    return [owner.id for owner in getattr(db, section).values() if skill_id in getattr(owner, field)]


def new_passive_data(db: Database) -> dict[str, Any]:
    return {"action": "effect", "trigger": "BattleStarted", "scope": "any", "pp_cost": 1,
            "effect_id": next(iter(db.effects), None)}


# --- описания --------------------------------------------------------------

def describe_skill(skill: SkillDefinition, db: Database, t: Optional[Callable[..., str]] = None) -> str:
    """Короткое описание навыка для интерфейса; t переводит названия."""
    t = t or _same
    aim = t(skill.targets) if skill.area == AREA_SINGLE else f"{t(skill.targets)}, {t(skill.area)}"
    cost = f"AP {skill.ap_cost}" + (f" PP {skill.pp_cost}" if skill.pp_cost else "")
    head = f"{cost} -> {aim}"
    if skill.hits > 1:
        head += f" x{skill.hits}"
    if skill.accuracy != 100:
        head += f" ({skill.accuracy}%)"
    parts = [head]
    for part in skill.parts:
        scaling = " + ".join(f"{round(s.coef * 100)}% {t(s.stat.value)}" for s in part.scaling)
        text = f"{t(part.kind)} x{part.power:g}: {scaling}"
        if part.kind == PART_DAMAGE:
            kinds = [t(part.category), *(t(tag) for tag in part.tags)]
            if part.weapon_tags:
                kinds.append(t("weapon"))
            text += f" [{', '.join(kinds)}]"
        parts.append(text)
    for tag, mult in skill.bonus_vs:
        parts.append(f"x{mult:g} {t('vs')} {t(tag)}")
    if skill.ap_restore:
        parts.append(f"+{skill.ap_restore} AP")
    if skill.pp_restore:
        parts.append(f"+{skill.pp_restore} PP")
    for apply in skill.applies:
        text = f"{t(db.effects[apply.effect_id].name)} -> {t(apply.to)}"
        condition = apply.to_dict()["condition"]
        if condition["type"] != "always":
            text += f" {t('if')} {describe_condition(condition, t)}"
        parts.append(text)
    return " | ".join(parts)
