"""Реакции: «когда произошло событие -> если выполнены фильтры -> сделать действие -> кому».

Реакция это общий кирпич для пассивок (тратят PP) и для поведения эффектов
(срабатывают бесплатно, пока эффект висит на носителе). Главное действие —
«применить навык»: так к событию привязывается любая способность (контратака,
добивание, лечение в ответ, удар на опережение).

Роли в событии:
- owner   — владелец реакции (носитель пассивки или эффекта);
- subject — с кем событие случилось (кого атаковали, кто погиб, на ком эффект);
- actor   — кто его вызвал (атаковавший, убийца, наложивший эффект, лекарь);
- source  — для эффектов: кто наложил эффект; для пассивок совпадает с owner;
- target  — для событий навыка (targeted, attacked, skill_used): основная цель навыка.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from .tactics import Always, ICondition, condition_from_dict, condition_to_dict

# --- события ---------------------------------------------------------------

ON_BATTLE_START = "battle_start"
ON_ROUND_START = "round_start"
ON_ROUND_END = "round_end"
ON_TURN_START = "turn_start"
ON_TURN_END = "turn_end"
ON_TARGETED = "targeted"            # фаза «до»: навык выбрал цели, удар ещё не нанесён
ON_ATTACKED = "attacked"            # после каждого удара навыка с уроном (попал, промах, крит, блок)
ON_HP_BELOW = "hp_below"            # HP опустилось ниже порога (срабатывает при пересечении)
ON_HEALED = "healed"
ON_DIED = "died"
ON_EFFECT_APPLIED = "effect_applied"
ON_EFFECT_EXPIRED = "effect_expired"  # кончилась длительность или заряды, или эффект сняли
ON_SKILL_USED = "skill_used"
ON_BEFORE_SKILL = "before_skill"    # фаза «до»: юнит вот-вот применит активный навык (subject = он сам)
EVENTS = (ON_BATTLE_START, ON_ROUND_START, ON_ROUND_END, ON_TURN_START, ON_TURN_END, ON_TARGETED, ON_ATTACKED,
          ON_HP_BELOW, ON_HEALED, ON_DIED, ON_EFFECT_APPLIED, ON_EFFECT_EXPIRED, ON_SKILL_USED, ON_BEFORE_SKILL)
EVENTS_WITHOUT_SUBJECT = (ON_BATTLE_START, ON_ROUND_START, ON_ROUND_END)
ATTACK_EVENTS = (ON_TARGETED, ON_ATTACKED, ON_BEFORE_SKILL, ON_SKILL_USED)   # фильтры по тегам атаки и области
EFFECT_EVENTS = (ON_EFFECT_APPLIED, ON_EFFECT_EXPIRED)

# Чьё событие: относительно владельца реакции.
WHOSE = ("self", "ally", "enemy", "any")          # ally = союзник, но не сам владелец

# Исход удара для события attacked.
OUTCOME_ANY = "any"
OUTCOME_LANDED = "landed"
OUTCOME_MISSED = "missed"
OUTCOME_CRIT = "crit"
OUTCOME_GUARDED = "guarded"
OUTCOMES = (OUTCOME_ANY, OUTCOME_LANDED, OUTCOME_MISSED, OUTCOME_CRIT, OUTCOME_GUARDED)

THIS_EFFECT = "@this"   # фильтр эффекта «этот самый эффект» (для поведения эффекта)

# --- действия --------------------------------------------------------------

DO_USE_SKILL = "use_skill"
DO_APPLY_EFFECT = "apply_effect"
DO_REMOVE_EFFECT = "remove_effect"
DO_DAMAGE = "damage"
DO_HEAL = "heal"
DO_RESTORE_AP = "restore_ap"
DO_RESTORE_PP = "restore_pp"
DO_COVER = "cover"      # только для targeted: удар по союзникам переходит на владельца
DO_DISPEL = "dispel"    # снять все эффекты с меткой label (buff, debuff, ailment)
ACTIONS = (DO_USE_SKILL, DO_APPLY_EFFECT, DO_REMOVE_EFFECT, DO_DAMAGE, DO_HEAL, DO_RESTORE_AP, DO_RESTORE_PP,
           DO_COVER, DO_DISPEL)
AMOUNT_ACTIONS = (DO_DAMAGE, DO_HEAL, DO_RESTORE_AP, DO_RESTORE_PP)
EFFECT_ACTIONS = (DO_APPLY_EFFECT, DO_REMOVE_EFFECT)

# Кому: роль из события или группа вокруг владельца.
TO_OWNER = "owner"
TO_SUBJECT = "subject"
TO_ACTOR = "actor"
TO_SOURCE = "source"
TO_TARGET = "target"        # основная цель навыка из события
TO_ALLIES = "allies"        # союзники владельца, кроме него самого
TO_ENEMIES = "enemies"
TO_EVERYONE = "everyone"    # все, кроме владельца
ROLES = (TO_OWNER, TO_SUBJECT, TO_ACTOR, TO_TARGET, TO_SOURCE)
GROUPS = (TO_ALLIES, TO_ENEMIES, TO_EVERYONE)
TARGETS = ROLES + GROUPS

# Как часто может срабатывать (кроме цены в PP).
LIMIT_NONE = "none"
LIMIT_ROUND = "round"
LIMIT_BATTLE = "battle"
LIMITS = (LIMIT_NONE, LIMIT_ROUND, LIMIT_BATTLE)

# Названия событий старых пассивок (имя класса события боя) -> событие и исход.
LEGACY_EVENTS = {
    "BattleStarted": (ON_BATTLE_START, OUTCOME_ANY),
    "RoundStarted": (ON_ROUND_START, OUTCOME_ANY),
    "TurnStarted": (ON_TURN_START, OUTCOME_ANY),
    "SkillUsed": (ON_SKILL_USED, OUTCOME_ANY),
    "DamageDealt": (ON_ATTACKED, OUTCOME_LANDED),
    "AttackMissed": (ON_ATTACKED, OUTCOME_MISSED),
    "Healed": (ON_HEALED, OUTCOME_ANY),
    "EffectApplied": (ON_EFFECT_APPLIED, OUTCOME_ANY),
    "EffectExpired": (ON_EFFECT_EXPIRED, OUTCOME_ANY),
    "UnitDied": (ON_DIED, OUTCOME_ANY),
}
LEGACY_EFFECT_WHEN = {"turn_start": ON_TURN_START, "expire": ON_EFFECT_EXPIRED, "applied": ON_EFFECT_APPLIED}
LEGACY_TARGETS = {"self": TO_OWNER, "source": TO_SOURCE}


def _check(value: str, allowed: tuple[str, ...], what: str) -> str:
    if value not in allowed:
        raise ValueError(f"unknown {what} {value!r}")
    return value


@dataclass(frozen=True)
class Reaction:
    """Одно правило реакции. Поля фильтров, не относящиеся к событию, игнорируются."""

    event: str
    action: str
    whose: str = "self"
    # фильтры
    self_condition: ICondition = Always()       # на владельца
    subject_condition: ICondition = Always()    # на того, с кем случилось событие
    area: Optional[str] = None                  # subject должен быть в этой области вокруг владельца
    attack_tags: tuple[str, ...] = ()           # атака с любым из тегов; пусто = любая
    skill_areas: tuple[str, ...] = ()           # навык с одной из этих областей; пусто = любой
    outcome: str = OUTCOME_ANY                  # для attacked
    effect_filter: Optional[str] = None         # для событий эффектов: какой эффект; None = любой
    effect_label: Optional[str] = None          # для событий эффектов: эффект с этой меткой (buff, debuff)
    threshold: float = 0.5                      # для hp_below: доля от максимального HP
    limit: str = LIMIT_NONE
    # действие
    skill_id: Optional[str] = None
    effect_id: Optional[str] = None             # у прикрытия необязателен: накладывается на владельца
    amount: int = 0
    percent: bool = False                       # урон и лечение: amount — процент от макс. HP получателя
    label: Optional[str] = None                 # для dispel: какая метка снимается
    to: str = TO_SUBJECT
    to_area: Optional[str] = None               # для групп: область вокруг владельца; None = вся сторона
    cover_many: bool = False                    # прикрытие: всех подходящих союзников, а не одного

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Reaction":
        reaction = cls(
            event=_check(data["event"], EVENTS, "event"),
            action=_check(data["action"], ACTIONS, "action"),
            whose=_check(data.get("whose", "self"), WHOSE, "whose"),
            self_condition=condition_from_dict(data.get("self_condition")),
            subject_condition=condition_from_dict(data.get("subject_condition")),
            area=data.get("area") or None,
            attack_tags=tuple(data.get("attack_tags", ())),
            skill_areas=tuple(data.get("skill_areas", ())),
            outcome=_check(data.get("outcome", OUTCOME_ANY), OUTCOMES, "outcome"),
            effect_filter=data.get("effect_filter") or None,
            effect_label=data.get("effect_label") or None,
            threshold=data.get("threshold", 0.5),
            limit=_check(data.get("limit", LIMIT_NONE), LIMITS, "limit"),
            skill_id=data.get("skill_id") or None,
            effect_id=data.get("effect_id") or None,
            amount=data.get("amount", 0),
            percent=data.get("percent", False),
            label=data.get("label") or None,
            to=_check(data.get("to", TO_SUBJECT), TARGETS, "target"),
            to_area=data.get("to_area") or None,
            cover_many=data.get("cover_many", False),
        )
        if reaction.action == DO_USE_SKILL:
            if reaction.skill_id is None:
                raise ValueError("action use_skill needs a skill")
            if reaction.to not in ROLES:
                raise ValueError("a skill is used on one unit: owner, subject, actor, target or source")
        if reaction.action in EFFECT_ACTIONS and reaction.effect_id is None:
            raise ValueError(f"action {reaction.action!r} needs an effect")
        if reaction.action == DO_DISPEL and reaction.label is None:
            raise ValueError("action dispel needs a label")
        if reaction.action == DO_COVER and reaction.event != ON_TARGETED:
            raise ValueError("cover works only on the 'targeted' event")
        return reaction

    @classmethod
    def from_legacy_effect_trigger(cls, data: Mapping[str, Any]) -> "Reaction":
        """Старое правило эффекта {when, action, amount, effect_id, to, area}."""
        event = LEGACY_EFFECT_WHEN.get(data["when"])
        if event is None:
            raise ValueError(f"unknown trigger moment {data['when']!r}")
        own = event in EFFECT_EVENTS
        to = data.get("to", "self")
        return cls.from_dict({
            "event": event, "whose": "self", "effect_filter": THIS_EFFECT if own else None,
            "action": data["action"], "amount": data.get("amount", 0), "effect_id": data.get("effect_id"),
            "to": LEGACY_TARGETS.get(to, to), "to_area": data.get("area"),
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "whose": self.whose,
            "self_condition": condition_to_dict(self.self_condition),
            "subject_condition": condition_to_dict(self.subject_condition),
            "area": self.area,
            "attack_tags": list(self.attack_tags),
            "skill_areas": list(self.skill_areas),
            "outcome": self.outcome,
            "effect_filter": self.effect_filter,
            "effect_label": self.effect_label,
            "threshold": self.threshold,
            "limit": self.limit,
            "action": self.action,
            "skill_id": self.skill_id,
            "effect_id": self.effect_id,
            "amount": self.amount,
            "percent": self.percent,
            "label": self.label,
            "to": self.to,
            "to_area": self.to_area,
            "cover_many": self.cover_many,
        }

    def references(self) -> dict[str, list[str]]:
        """Ссылки на другие определения, для проверки справочника: {раздел: [id]}."""
        effects = [e for e in (self.effect_id, self.effect_filter) if e and e != THIS_EFFECT]
        return {
            "skills": [self.skill_id] if self.skill_id else [],
            "effects": effects,
            "areas": [a for a in (self.area, self.to_area, *self.skill_areas) if a],
            "attack_tags": list(self.attack_tags),
        }


def new_reaction_data() -> dict[str, Any]:
    """Заготовка для редакторов."""
    return Reaction(event=ON_TURN_START, action=DO_DAMAGE, amount=1, to=TO_OWNER).to_dict()
