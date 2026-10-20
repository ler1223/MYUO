"""Пассивка как навык: перевод старого описания пассивки (``{"name", "pp_cost", "reaction"}``) в навык с триггером.

Формат навыка-пассивки — docs/uo/ABILITIES_DESIGN.md. Здесь только перевод данных (в формате JSON): им пользуются
``Database`` (читает старые данные и вызовы ``update("passives", ...)`` из редакторов) и ``tools/migrate_abilities.py``.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from .definitions import PassiveDefinition
from .reactions import (DO_COVER, DO_USE_SKILL, LIMIT_NONE, ON_BEFORE_SKILL, ON_SKILL_USED, Reaction, Trigger)

# поля тела навыка, которые переходят из навыка-ответа в пассивку
BODY_FIELDS = ("targets", "area", "hits", "accuracy", "tags", "parts", "bonus_vs", "ap_restore", "pp_restore",
               "applies", "requires_self", "requires_target", "potency", "extras")
GUARD_EFFECTS = {"uo_guard_small": "small", "uo_guard_medium": "medium", "uo_guard_heavy": "heavy"}
ROLE_OF_TO = {"actor": "attacker", "target": "ally_target", "owner": "self"}


def referenced_skills(data: Mapping[str, Any], passives: Mapping[str, Any]) -> set[str]:
    """Навыки, на которые ссылаются классы, предметы, тактики и пассивки (их нельзя растворить в теле пассивки)."""
    used: set[str] = set()
    for owner in (*data.get("units", {}).values(), *data.get("items", {}).values()):
        for entry in owner.get("skills", ()):
            used.add(entry.get("id") if isinstance(entry, dict) else entry)
        for rule in owner.get("tactics", ()):
            used.add(rule["skill"])
    for skill in data.get("skills", {}).values():
        for step in skill.get("steps", ()):                 # шаги пассивок-навыков
            if step.get("skill_id"):
                used.add(step["skill_id"])
    counts: dict[str, int] = {}
    for passive in passives.values():                    # на один навык-ответ ссылается одна пассивка — свою он не считает
        reaction = passive.get("reaction") or {}
        for ref in (reaction.get("skill_id"), *(s.get("skill_id") for s in reaction.get("then", ()))):
            if ref:
                counts[ref] = counts.get(ref, 0) + 1
    used.update(ref for ref, count in counts.items() if count > 1)
    return used


def skill_from_passive(passive_id: str, passive_data: Mapping[str, Any], skills: Mapping[str, Any],
                       referenced: set[str], pool: Optional[Mapping[str, Any]] = None
                       ) -> tuple[dict[str, Any], Optional[str]]:
    """Навык-пассивка по старому описанию. Второй результат — id навыка-ответа, чьё тело влилось в пассивку
    (его надо удалить), или None."""
    passive = PassiveDefinition.from_dict(passive_id, passive_data)
    r = passive.reaction
    out: dict[str, Any] = {"name": passive.name, "kind": "passive", "ap_cost": 0, "pp_cost": passive.pp_cost}
    trigger = Trigger(r.event, r.whose, "", r.self_condition, r.subject_condition, r.actor_condition, r.area,
                      r.attack_tags, r.skill_areas, r.outcome, r.effect_filter, r.effect_label, r.threshold)
    out["trigger"] = trigger.to_dict()
    if r.limit != LIMIT_NONE:
        out["limit"] = r.limit
    then = [step.step_dict() for step in r.then]
    absorbed = None
    response = (pool or skills).get(r.skill_id) if r.action == DO_USE_SKILL else None
    own = (pool or skills).get(passive_id)
    if (r.action == DO_USE_SKILL and r.skill_id == passive_id and own is not None
            and own.get("kind") == "passive" and own.get("body")):
        # редактор пассивок получил реакцию «применить навык» от самой пассивки (её вид из passive_view): тело то же
        for field in BODY_FIELDS:
            if field in own:
                out[field] = own[field]
        out["body"] = True
        out["target"] = _role(r, trigger)
        if r.to_area:
            out["target_area"] = r.to_area
        for field in ("response", "default_tactic"):
            if own.get(field):
                out[field] = own[field]
        if then:
            out["steps"] = then
        return out, None
    if r.action == DO_COVER:
        out["response"] = "cover"
        guard = GUARD_EFFECTS.get(r.effect_id or "")
        out["cover"] = {k: v for k, v in (("guard", guard), ("effect_id", None if guard else r.effect_id),
                                          ("many", r.cover_many or None)) if v}
        if then:
            out["steps"] = then
    elif (response is not None and r.skill_id.startswith(passive_id + "_") and r.skill_id not in referenced
          and "kind" not in response):
        for field in BODY_FIELDS:
            if field in response:
                out[field] = response[field]
        out["body"] = True
        out["target"] = _role(r, trigger)
        if r.to_area:
            out["target_area"] = r.to_area
        if r.to == "actor" and r.event in ("skill_used", "attacked") and r.whose != "self":
            out["response"] = "counter"
        elif r.to == "target" and r.event == ON_SKILL_USED and r.whose == "ally":
            out["response"] = "pursuit"
        if then:
            out["steps"] = then
        absorbed = r.skill_id
    else:
        main = Reaction(event=r.event, action=r.action, skill_id=r.skill_id, effect_id=r.effect_id, amount=r.amount,
                        percent=r.percent, label=r.label, to=r.to, to_area=r.to_area, then=r.then).step_dict()
        out["steps"] = [main]
    return out, absorbed


def _role(reaction: Reaction, trigger: Trigger) -> str:
    """Роль цели пассивки по старому полю ``to``."""
    if reaction.to == "subject":
        acting = trigger.whose == "ally" and trigger.event in (ON_BEFORE_SKILL, ON_SKILL_USED)
        return "acting_ally" if acting else "affected_ally"
    return ROLE_OF_TO.get(reaction.to, reaction.to)


def merge_passives(source: dict[str, Any], passives: Mapping[str, Any]) -> None:
    """Переводит старый раздел passives в навыки внутри словаря данных source (на месте)."""
    skills = dict(source.get("skills", {}))
    referenced = referenced_skills(source, passives)
    original = dict(skills)
    absorbed = []
    for passive_id, data in passives.items():
        skills[passive_id], gone = skill_from_passive(passive_id, data, skills, referenced, original)
        if gone and gone != passive_id:
            absorbed.append(gone)
    for gone in absorbed:
        skills.pop(gone, None)
    source["skills"] = skills
