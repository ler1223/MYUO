"""Бой двух отрядов по правилам Unicorn Overlord (docs/uo/battle.md).

Ход боя (справка UO, «Flow of Battle»):
- круг: каждый живой боец с AP действует один раз, по убыванию инициативы (поровну — случайно);
  следующий круг — снова все, у кого остались AP; бой кончается, когда за круг никто не смог
  действовать или одна сторона пала;
- действие — активный навык по тактике (game.tactics), стоит AP; цель и кого достать — game.combat.field;
- пассивки (game.reactions) срабатывают на моменты боя и стоят PP: в начале боя, до удара (прикрыть,
  блок, уклонение), после удара (контратака), после атаки (преследование), в конце боя. На одно
  действие каждый боец отвечает не больше чем одной пассивкой; отвечают по убыванию инициативы;
  пассивки отвечают только на активные навыки (на ответы не отвечают), защищают — от любых;
- перед активным навыком: яд и ожог (урон), восстановление (лечение) — эффекты с реакцией на
  turn_start; заморожен — пропускает, пока по нему не попадут; оглушён — пропускает один ход;
- итог: одна сторона пала — побеждает другая; иначе проигрывает та, у кого меньше остаток HP (в долях).

Наружу: step() — события следующего акта (game.events, для журнала), last_act / acts — запись по
действиям (game.combat.record) для показа боя.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from ..database import Database
from ..definitions import (APPLY_SELF, APPLY_TARGET, PART_DAMAGE, PART_HEAL, PART_HEAL_PCT, PassiveDefinition,
                           SkillDefinition)
from ..effects import ActiveEffect, AttackMod, StackRule
from ..events import (
    END_DEFEAT,
    END_EXHAUSTED,
    END_ROUND_LIMIT,
    END_WIPEOUT,
    SKIP_NO_ACTION,
    SKIP_STUNNED,
    AttackMissed,
    BattleEnded,
    BattleStarted,
    Covered,
    DamageDealt,
    EffectApplied,
    EffectExpired,
    Event,
    Healed,
    PassiveTriggered,
    ResourceGained,
    RoundStarted,
    SkillUsed,
    TurnSkipped,
    TurnStarted,
    UnitDied,
)
from ..reactions import (
    ATTACK_EVENTS,
    DO_APPLY_EFFECT,
    DO_COVER,
    DO_DAMAGE,
    DO_DISPEL,
    DO_HEAL,
    DO_REMOVE_EFFECT,
    DO_RESTORE_AP,
    DO_RESTORE_PP,
    DO_USE_SKILL,
    EFFECT_EVENTS,
    EVENTS_WITHOUT_SUBJECT,
    LIMIT_BATTLE,
    LIMIT_ROUND,
    ON_ATTACKED,
    ON_BATTLE_END,
    ON_BATTLE_START,
    ON_BEFORE_SKILL,
    ON_DIED,
    ON_EFFECT_APPLIED,
    ON_EFFECT_EXPIRED,
    ON_HEALED,
    ON_HP_BELOW,
    ON_ROUND_END,
    ON_ROUND_START,
    ON_SKILL_USED,
    ON_TARGETED,
    ON_TURN_END,
    ON_TURN_START,
    OUTCOME_ANY,
    OUTCOME_CRIT,
    OUTCOME_GUARDED,
    OUTCOME_LANDED,
    OUTCOME_MISSED,
    THIS_EFFECT,
    TO_ACTOR,
    TO_ALLIES,
    TO_ENEMIES,
    TO_EVERYONE,
    TO_OWNER,
    TO_SOURCE,
    TO_SUBJECT,
    TO_TARGET,
    Reaction,
)
from ..squad import Squad
from ..stats import Stat
from ..tactics import Always, Frontmost
from ..unit import Unit
from . import rules
from .field import Side, affected, default_order, pick_target, reachable
from .record import (
    ACTIVE,
    AFFLICTION,
    END,
    EVADE,
    HIT,
    MISS,
    NEGATE,
    PASSIVE,
    ROUND,
    SKIP,
    START,
    Act,
    Change,
    Strike,
)

MAX_ROUNDS = 30                 # предохранитель: столько кругов — и бой кончается по остатку HP
FALLBACK_SKILL = "attack"       # запасной навык, когда ни одно правило тактики не подошло
MAX_DEPTH = 4                   # реакции на реакции — не глубже (эффекты, вызывающие друг друга по кругу)
SKIP_FROZEN = "frozen"
NO_PASSIVES = ("passive_seal", "frozen", "stunned")   # с этим пассивки не срабатывают


@dataclass
class Moment:
    """Момент боя, на который могут ответить пассивки."""

    event: str
    subject: Optional[Unit] = None      # с кем случилось
    actor: Optional[Unit] = None        # кто вызвал
    target: Optional[Unit] = None       # основная цель навыка
    skill: Optional[SkillDefinition] = None
    attack_tags: frozenset[str] = frozenset()
    outcome: str = OUTCOME_ANY          # для attacked: landed / missed / crit / guarded
    outcomes: frozenset[str] = frozenset()
    hp_before: int = -1                 # для hp_below: HP до удара (срабатывает при пересечении порога)
    effect: Optional[ActiveEffect] = None    # для effect_applied / effect_expired


@dataclass
class _Action:
    """Действие, к которому относятся ответы: каждый боец отвечает на него не больше одного раза.
    covering — кто уже прикрывает в этом действии всех подходящих (cover_many): прикрывает и следующих.
    passives_fired — сколько пассивок сработало за действие (предел — database.passives_per_action)."""

    responded: set[int] = field(default_factory=set)
    covering: set[int] = field(default_factory=set)
    one_each: bool = True               # False — вне хода (начало и конец боя, круга): ответов сколько угодно
    before: set[tuple[int, str]] = field(default_factory=set)   # (сторона, действие) уже ответившие до удара
    fresh: list[ActiveEffect] = field(default_factory=list)     # наложено в этот ход — в его конце не убывает
    passives_fired: int = 0             # пассивки, сработавшие за это действие
    passive_limit: int = 2              # предел пассивок за действие (-1 — без предела)


class Battle:
    """Бой attacker (слева) против defender (справа). Отряды и юниты меняются по ходу боя (HP)."""

    def __init__(self, attacker: Squad, defender: Squad, db: Database, seed: Optional[int] = None,
                 first_strike: Optional[str] = None, max_rounds: int = MAX_ROUNDS,
                 passives_per_action: Optional[int] = None):
        self.db = db
        self.rng = random.Random(seed)
        self.attacker, self.defender = attacker, defender
        self.sides = (Side(attacker, 0), Side(defender, 1))
        self.units: dict[int, Unit] = {u.uid: u for side in self.sides for u in side.units}
        self.first_strike = first_strike      # id отряда с первым ударом (действует раньше всех)
        self.max_rounds = max_rounds
        # Предел пассивок за одно активное действие; None — как в data/config.json (обычно 2).
        # -1 снимает предел (демонстрация анимаций: assets-тест).
        self.passives_per_action = db.passives_per_action if passives_per_action is None else passives_per_action
        self.events: list[Event] = []
        self.acts: list[Act] = []
        self.last_act: Optional[Act] = None
        self.round = 0
        self.finished = False
        self.winner_id: Optional[str] = None
        self.end_reason = ""
        self._started = False
        self._order: list[Unit] = []
        self._acted = False
        self._uses: dict[tuple[int, str], int] = {}          # (боец, пассивка) -> сколько раз за бой
        self._step_events: list[Event] = []
        self._pending_end: Optional[str] = None
        self._action = _Action(one_each=False)   # действие, к которому относятся ответы сейчас
        self._depth = 0
        self._dead: set[int] = set()
        self._round_ended = True
        self._unblockable = frozenset(t for t, d in db.tags.items() if d.unblockable)

    # --- снаружи ---

    def side_of(self, unit: Unit) -> Side:
        return self.sides[0] if self.sides[0].has(unit) else self.sides[1]

    def other(self, side: Side) -> Side:
        return self.sides[1 - side.index]

    def step(self) -> list[Event]:
        """Следующий акт боя; его события по порядку (пусто — бой уже кончился)."""
        self._step_events = []
        act = self._next_act()
        while act is not None:                     # начало боя и круга — одним шагом со следующим ходом
            self.acts.append(act)
            self.last_act = act
            if act.kind not in (START, ROUND) or self.finished:
                break
            act = self._next_act()
        return list(self._step_events)

    def run(self) -> list[Event]:
        """Доиграть бой до конца; все события."""
        while not self.finished:
            self.step()
        return self.events

    # --- круги и ходы ---

    def _next_act(self) -> Optional[Act]:
        if self.finished:
            return None
        if not self._started:
            return self._start()
        if self._pending_end:
            return self._end(self._pending_end)
        while True:
            if not self._order:
                if not self._round_ended:          # конец круга: реакции на него — своим актом
                    self._round_ended = True
                    act = self._round_act(ON_ROUND_END)
                    self._check_wipe()
                    if act.after:
                        return act
                    if self._pending_end:
                        return self._end(self._pending_end)
                if self.round and not self._acted:
                    return self._end(END_EXHAUSTED)
                if self.round >= self.max_rounds:
                    return self._end(END_ROUND_LIMIT)
                self._begin_round()
                if not self._order:
                    return self._end(END_EXHAUSTED)
                act = self._round_act(ON_ROUND_START)
                self._check_wipe()
                if act.after:
                    return act
            unit = self._order.pop(0)
            if not unit.is_alive or unit.ap.current <= 0:
                continue
            act = self._turn(unit)
            self._check_wipe()
            return act

    def _start(self) -> Act:
        self._started = True
        for unit in self.units.values():       # эффекты, наложенные до боя, остаются; спадают в конце
            unit.start_battle()
        act = Act(START)
        self._emit(act, BattleStarted(self.attacker.id, self.defender.id))
        self._action = _Action(one_each=False)
        self._react(Moment(ON_BATTLE_START), act.after)
        self._check_wipe()
        return act

    def _round_act(self, event: str) -> Act:
        act = Act(ROUND, reason=event, round=self.round)
        self._action = _Action(one_each=False)
        self._react(Moment(event), act.after)
        return act

    def _begin_round(self) -> None:
        self._round_ended = False
        self.round += 1
        self._acted = False
        units = [u for side in self.sides for u in side.alive() if u.ap.current > 0]
        tie = {u.uid: self.rng.random() for u in units}
        first = lambda u: 0 if self.first_strike and self.side_of(u).id == self.first_strike else 1
        self._order = sorted(units, key=lambda u: (first(u), -u.stat(Stat.INITIATIVE), tie[u.uid]))
        self._emit(None, RoundStarted(self.round))

    def _turn(self, unit: Unit) -> Act:
        self._action = _Action(passive_limit=self.passives_per_action)
        self._emit(None, TurnStarted(unit.uid))
        if unit.has_flag("frozen"):
            return self._skip(unit, SKIP_FROZEN)
        if unit.has_flag("stunned"):
            act = self._skip(unit, SKIP_STUNNED)
            self._remove_flagged(unit, "stunned", act)     # «до следующего хода»: этот ход и был им
            return act
        choice = self._choose(unit)
        if choice is None:
            return self._skip(unit, SKIP_NO_ACTION)
        skill, target = choice
        act = Act(ACTIVE, unit.uid, skill.id, target=target.uid, ap_cost=skill.ap_cost, pp_cost=skill.pp_cost,
                  hits=skill.hits, round=self.round)
        # перед активным навыком: яд, ожог, восстановление (реакции эффектов на начало хода) и ответы
        self._react(Moment(ON_TURN_START, subject=unit), act.before)
        if not unit.is_alive or self._pending_end:
            act.kind, act.reason = SKIP, "died"
            return act
        self._react(Moment(ON_BEFORE_SKILL, subject=unit, actor=unit, target=target, skill=skill), act.before)
        if not unit.is_alive:
            return act
        if not target.is_alive:              # цель пала до удара (ответ пассивкой): цель заново
            choice = self._choose(unit)
            if choice is None:
                return act
            skill, target = choice
            act.skill_id, act.target = skill.id, target.uid
        unit.ap.spend(skill.ap_cost)
        unit.pp.spend(min(skill.pp_cost, unit.pp.current))
        self._acted = True
        self._resolve(unit, skill, target, act, root=True)
        if unit.is_alive:
            self._tick(unit, act)
        return act

    def _skip(self, unit: Unit, reason: str) -> Act:
        act = Act(SKIP, unit.uid, reason=reason, round=self.round)
        self._emit(act, TurnSkipped(unit.uid, SKIP_STUNNED if reason == SKIP_FROZEN else reason))
        self._react(Moment(ON_TURN_END, subject=unit), act.after)
        return act

    def _choose(self, unit: Unit) -> Optional[tuple[SkillDefinition, Unit]]:
        """Первое правило тактики, которое можно выполнить (навык есть, хватает AP/PP, условия,
        есть цель); цель — по правилам UO (field)."""
        own = self.side_of(unit)
        other = self.other(own)
        available = set(unit.skill_ids)
        rules_ = [(r.skill_id, r.condition, r.self_condition, r.selector) for r in unit.tactics.ordered(unit)]
        # ни одно правило не подошло — обычная атака (навык attack), если она у бойца есть
        fallback = [(FALLBACK_SKILL, Always(), Always(), Frontmost())] if FALLBACK_SKILL in unit.skill_ids else []
        for skill_id, condition, self_condition, selector in rules_ + fallback:
            skill = self.db.skills.get(skill_id)
            if skill is None or skill.id not in available or not skill.affordable(unit):
                continue
            if not (skill.requires_self.check(unit, unit) and self_condition.check(unit, unit)):
                continue
            side = own if skill.targets in ("ally", "self") else other
            pool = reachable(skill, unit, own, other)
            if skill.targets == "enemy" and skill.area in ("", "single"):
                pool = [u for u in other.alive() if u.has_flag("taunt")] or pool
            candidates = [u for u in pool if skill.requires_target.check(unit, u) and condition.check(unit, u)]
            if candidates:
                unit.tactics.chosen(unit, skill.id)
                return skill, pick_target(selector, unit, own, side, candidates, self.rng)
        return None

    # --- навык ---

    def _resolve(self, user: Unit, skill: SkillDefinition, target: Unit, act: Act, root: bool) -> None:
        """Применение навыка: ответы до удара, удары, эффекты, гибели, ответы после (только у хода)."""
        self._emit(act, SkillUsed(user.uid, skill.id, target.uid))
        tside = self.side_of(target)
        area = self.db.areas.get(skill.area) or self.db.areas.get("single")
        hit_list = [user] if skill.targets == "self" else affected(skill, area, target, tside)
        tags, mods = self._attack(user, skill)
        attack = rules.Attack(user, skill, tags, [m for _, m in mods])
        hostile = skill.targets == "enemy"
        if skill.extras.hp_cost:
            self._lose_hp(user, max(0, min(user.hp - 1, round(user.max_hp * skill.extras.hp_cost))), user, skill.id, act)
        # до удара: прикрыть, блок, уклонение (у врагов цели и у неё самой)
        covers: dict[int, Unit] = {}
        if hostile:
            for unit in list(hit_list):
                moment = Moment(ON_TARGETED, subject=unit, actor=user, target=target, skill=skill, attack_tags=tags)
                protector = self._cover(moment, act, hit_list)
                if protector is not None:
                    covers[protector.uid] = unit
                    act.covers.append((protector.uid, unit.uid))
                    self._emit(act, Covered(protector.uid, unit.uid, skill.id))
                    hit_list[hit_list.index(unit)] = protector
            hit_list = list(dict.fromkeys(hit_list))
            for unit in list(hit_list):           # блок, уклонение, усиления — у тех, по кому придётся удар
                self._react(Moment(ON_TARGETED, subject=unit, actor=user, target=target, skill=skill,
                                   attack_tags=tags), act.before)
        act.targets = [u.uid for u in hit_list]
        # удары
        landed: dict[int, set[str]] = {}
        killed: list[Unit] = []
        blind = hostile and user.has_flag("blind")
        has_damage = any(p.kind == PART_DAMAGE for p in skill.parts)
        has_heal = any(p.kind in (PART_HEAL, PART_HEAL_PCT) for p in skill.parts)
        for index in range(skill.hits):
            for unit in hit_list:
                if not unit.is_alive:
                    continue
                attack.potency = self._potency(user, skill, unit)
                strike = Strike(unit.uid, index, covered=covers[unit.uid].uid if unit.uid in covers else None,
                                max_hp=unit.max_hp)
                if hostile and has_damage:
                    self._strike(attack, unit, strike, act, blind)
                    outcome = landed.setdefault(unit.uid, set())
                    if strike.outcome == HIT:
                        outcome.add(OUTCOME_LANDED)
                        if strike.crit:
                            outcome.add(OUTCOME_CRIT)
                        if strike.guard:
                            outcome.add(OUTCOME_GUARDED)
                    else:
                        outcome.add(OUTCOME_MISSED)
                elif has_heal and not rules.roll(self.rng, rules.hit_chance(attack, unit, (), ignore_evasion=True)):
                    strike.outcome = MISS                 # лечение не уклоняется, но навык с низкой точностью мажет
                    self._emit(act, AttackMissed(user.uid, unit.uid, skill.id))
                    landed.setdefault(unit.uid, set()).add(OUTCOME_MISSED)
                elif has_heal:
                    crit = rules.roll(self.rng, rules.crit_chance(attack))
                    amount = rules.healing(attack, unit, crit)
                    strike.crit = crit
                    strike.heal = self._heal(unit, amount, user, skill.id, act, crit, change=False)
                    landed.setdefault(unit.uid, set()).add(OUTCOME_LANDED)
                else:
                    landed.setdefault(unit.uid, set()).add(OUTCOME_LANDED)
                strike.hp = unit.hp
                if not unit.is_alive and unit not in killed:
                    strike.died = True
                    killed.append(unit)
                act.strikes.append(strike)
        if blind:
            self._remove_flagged(user, "blind", act)
        self._spend_charges(user, mods, act)
        # после ударов: эффекты, AP/PP, снятие, добивание
        hit_units = [u for u in hit_list if OUTCOME_LANDED in landed.get(u.uid, set())]
        self._after_hit(user, skill, target, hit_units, killed, act)
        for unit in killed:
            self._die(unit, act)
        if not root:
            return
        # ответы после: на удар по себе и союзникам, на применение навыка
        for unit in hit_list:
            outcomes = landed.get(unit.uid, set())
            if not hostile or not unit.is_alive or not outcomes:
                continue
            outcome = OUTCOME_LANDED if OUTCOME_LANDED in outcomes else OUTCOME_MISSED
            self._react(Moment(ON_ATTACKED, subject=unit, actor=user, target=target, skill=skill, attack_tags=tags,
                               outcome=outcome, outcomes=frozenset(outcomes)), act.after)
        if user.is_alive:
            self._react(Moment(ON_SKILL_USED, subject=user, actor=user, target=target, skill=skill,
                               attack_tags=tags), act.after)

    def _attack(self, user: Unit, skill: SkillDefinition) -> tuple[frozenset[str], list[tuple[ActiveEffect, AttackMod]]]:
        """Теги атаки (навык, тип урона частей и оружия, сам атакующий, поправки) и поправки эффектов."""
        mods = [(e, m) for e in user.effects for m in e.definition.attack_mods
                if (m.skill_tag is None or m.skill_tag in skill.tags) and (e.charges is None or e.charges > 0)]
        tags = set(skill.tags) | set(user.tags)
        for part in skill.parts:
            if part.kind == PART_DAMAGE:
                tags.add(part.category)          # physical / magical / pure — тоже тег атаки
            if part.weapon_tags and user.weapon_damage_tags:
                tags.update(user.weapon_damage_tags)     # тип урона — от оружия, а не запасной из навыка
            else:
                tags.update(part.tags)
        for _, mod in mods:
            tags.update(mod.add_tags)
        return frozenset(tags), mods

    def _potency(self, user: Unit, skill: SkillDefinition, target: Unit) -> float:
        """Условная прибавка к силе (UO: «+50 potency if …»)."""
        add = 0.0
        for bonus in skill.potency:
            if not (bonus.self_condition.check(user, user) and bonus.target_condition.check(user, target)):
                continue
            share = 1.0
            if bonus.scale == "self_hp_missing":
                share = 1 - user.hp / max(1, user.max_hp)
            elif bonus.scale == "self_hp":
                share = user.hp / max(1, user.max_hp)
            elif bonus.scale == "target_hp_missing":
                share = 1 - target.hp / max(1, target.max_hp)
            elif bonus.scale == "target_hp":
                share = target.hp / max(1, target.max_hp)
            elif bonus.scale == "enemies_fallen":
                enemies = self.other(self.side_of(user)).units
                share = sum(not u.is_alive for u in enemies) / max(1, len(enemies))
            elif bonus.scale == "front_row":
                share = 1.0 if self.side_of(user).pos(user)[0] == 0 else 0.0
            add += bonus.add * share
        return add

    def _strike(self, attack: rules.Attack, unit: Unit, strike: Strike, act: Act, blind: bool) -> None:
        """Удар по врагу: промах, уклонение, попадание с критом и блоком; урон, разморозка."""
        user, skill = attack.user, attack.skill
        truestrike = skill.extras.truestrike
        covered = strike.covered is not None       # защитник принимает удар — не уклоняется
        evade = None if truestrike or covered else self._tag_flag(unit, "evade", attack.tags)
        if blind:
            strike.outcome = MISS
        elif evade:
            strike.outcome = EVADE
            self._remove_flagged(unit, evade, act)
        elif not rules.roll(self.rng, rules.hit_chance(attack, unit, self.db.rules, ignore_evasion=covered)):
            strike.outcome = MISS
        if strike.outcome != HIT:
            strike.hp = unit.hp
            self._emit(act, AttackMissed(user.uid, unit.uid, skill.id))
            return
        strike.crit = rules.roll(self.rng, rules.crit_chance(attack))
        forced = next((f.split(":", 1)[1] for e in unit.effects for f in e.definition.flags
                       if f.startswith("guard:")), None)
        guard_cut = 0.0
        if rules.can_guard(attack, unit, self._unblockable) and \
                (forced or rules.roll(self.rng, unit.stat(Stat.GUARD_RATE))):
            strike.guard = rules.guard_level(unit, self.db.guard, forced)
            guard_cut = self.db.guard.reduction(strike.guard)
            if forced:
                self._remove_flagged(unit, f"guard:{forced}", act)
        negate = self._tag_flag(unit, "negate", attack.tags)
        amount = 0 if negate else rules.damage(attack, unit, self.db.rules, strike.crit, guard_cut)
        if negate:
            strike.outcome = NEGATE
            self._remove_flagged(unit, negate, act)
        if amount >= unit.hp and unit.has_flag("endure"):
            amount = max(0, unit.hp - 1)
            self._remove_flagged(unit, "endure", act)
        strike.damage = unit.take_damage(amount)
        if unit.has_flag("frozen"):
            strike.thawed = True
            self._remove_flagged(unit, "frozen", act)
        self._emit(act, DamageDealt(user.uid, unit.uid, strike.damage, unit.hp, skill.id, strike.crit,
                                    strike.guard is not None))
        extras = skill.extras
        if extras.heal_on_hit and user.is_alive:
            self._heal(user, round(user.max_hp * extras.heal_on_hit), user, skill.id, act)
        if extras.lifesteal and strike.damage and user.is_alive:
            self._heal(user, round(strike.damage * extras.lifesteal), user, skill.id, act)
        if extras.hit_ap:
            self._resource(user, "AP", extras.hit_ap, user, skill.id, act)
        if extras.hit_pp:
            self._resource(user, "PP", extras.hit_pp, user, skill.id, act)
        self._hp_below(unit, strike.damage, act)

    @staticmethod
    def _tag_flag(unit: Unit, base: str, tags: frozenset[str]) -> Optional[str]:
        """Флаг base (на всё) или base:<тег атаки> у цели — какой сработает."""
        if unit.has_flag(base):
            return base
        return next((f"{base}:{t}" for t in sorted(tags) if unit.has_flag(f"{base}:{t}")), None)

    def _after_hit(self, user: Unit, skill: SkillDefinition, target: Unit, hit_units: list[Unit],
                   killed: list[Unit], act: Act) -> None:
        extras = skill.extras
        for apply in skill.applies:
            if apply.to == APPLY_TARGET:
                for unit in hit_units:
                    if unit.is_alive and apply.condition.check(user, unit):
                        self._give(unit, apply.effect_id, user, act)
            elif apply.to == APPLY_SELF and user.is_alive and apply.condition.check(user, target) and                     (hit_units or not any(p.kind == PART_DAMAGE for p in skill.parts)):
                self._give(user, apply.effect_id, user, act)     # все удары мимо — себе тоже ничего
        for unit in hit_units:
            if not unit.is_alive:
                continue
            if skill.ap_restore:
                self._resource(unit, "AP", skill.ap_restore, user, skill.id, act)
            if skill.pp_restore:
                self._resource(unit, "PP", skill.pp_restore, user, skill.id, act)
            for label in extras.dispel:
                self._dispel(unit, label, act)
            for name, amount in (("AP", extras.ap_drain), ("PP", extras.pp_drain)):
                if amount:
                    taken = self._resource(unit, name, -amount, user, skill.id, act)
                    if extras.steal and taken and user.is_alive:
                        self._resource(user, name, taken, user, skill.id, act)
        if killed and user.is_alive:
            if extras.kill_ap:
                self._resource(user, "AP", extras.kill_ap, user, skill.id, act)
            if extras.kill_pp:
                self._resource(user, "PP", extras.kill_pp, user, skill.id, act)
            if extras.kill_heal:
                self._heal(user, round(user.max_hp * extras.kill_heal), user, skill.id, act)
            if extras.kill_effect:
                self._give(user, extras.kill_effect, user, act)

    def _spend_charges(self, user: Unit, mods: list[tuple[ActiveEffect, AttackMod]], act: Act) -> None:
        for effect in {id(e): e for e, _ in mods}.values():
            if effect.charges is not None:
                effect.charges -= 1
                if effect.charges <= 0 and effect in user.effects:
                    self._expire(user, effect, act)

    # --- конец хода ---

    def _tick(self, unit: Unit, act: Act) -> None:
        """Конец своего хода: у временных эффектов убывает длительность, реакции на конец хода."""
        for effect in unit.tick(skip=self._action.fresh):
            unit.effects.append(effect)          # снимается через _expire: с реакциями на истечение
            self._expire(unit, effect, act)
        self._react(Moment(ON_TURN_END, subject=unit), act.after)

    # --- прикрытие ---

    def _cover(self, moment: Moment, act: Act, hit_list: list[Unit]) -> Optional[Unit]:
        """Прикрытие цели moment.subject: первый по инициативе, кто может, принимает удар на себя.
        Кто сам под ударом, прикрывает, только если прикрывает всех (cover_many)."""
        ward = moment.subject
        action = self._action
        for owner in self._owners():
            if owner is ward or not self._can_respond(owner):
                continue
            if self._passive_cap_reached():
                return None
            for passive_id in owner.passive_ids:
                passive = self.db.passives.get(passive_id)
                if passive is None or passive.reaction.action != DO_COVER:
                    continue
                reaction = passive.reaction
                key = ("p", owner.uid, passive_id)
                if owner.uid in action.covering and reaction.cover_many:
                    if self._matches(owner, passive, reaction, moment, key, counted=False):
                        return owner
                    continue
                if owner.uid in action.responded:
                    continue
                if not self._matches(owner, passive, reaction, moment, key):
                    continue
                action.responded.add(owner.uid)
                if action.one_each:
                    action.passives_fired += 1
                self._uses[key] = self.round
                owner.pp.spend(passive.pp_cost)
                sub = Act(PASSIVE, owner.uid, passive_id, reason=moment.event, pp_cost=passive.pp_cost,
                          round=self.round, targets=[ward.uid])
                self._emit(sub, PassiveTriggered(owner.uid, passive_id))
                if reaction.effect_id:
                    self._give(owner, reaction.effect_id, owner, sub)
                if reaction.cover_many:
                    action.covering.add(owner.uid)
                act.before.append(sub)
                return owner
        return None

    # --- реакции: пассивки и поведение эффектов ---

    def _react(self, moment: Moment, into: list[Act]) -> None:
        """Все, кто отвечает на момент, по убыванию инициативы: пассивки (стоят PP; в моменты хода —
        не больше одного ответа бойца на действие) и реакции эффектов (бесплатно). Ответы — актами в into."""
        if self._depth >= MAX_DEPTH or self.finished:
            return
        self._depth += 1
        try:
            for owner, origin, reaction, key in self._reactors(moment):
                if self.finished:
                    break
                if reaction.action == DO_COVER:
                    continue
                passive = isinstance(origin, PassiveDefinition)
                if passive and (not self._can_respond(owner) or
                                self._action.one_each and owner.uid in self._action.responded):
                    continue
                if passive and self._passive_cap_reached():
                    continue                              # за действие срабатывает не больше n пассивок
                kind = (self.side_of(owner).id, reaction.action)
                guards_other = passive and moment.event == ON_TARGETED and owner is not moment.subject
                if guards_other and kind in self._action.before:
                    continue                          # за союзника до удара отвечает один с каждой стороны
                if not self._matches(owner, origin, reaction, moment, key):
                    continue
                sub = self._perform(owner, origin, reaction, moment, key)
                if sub is not None:
                    into.append(sub)
                    if guards_other:
                        self._action.before.add(kind)
        finally:
            self._depth -= 1

    def _reactors(self, moment: Moment) -> list:
        """(владелец, пассивка или эффект, реакция, ключ лимита) — в порядке ответа."""
        owners = self._owners()
        subject = moment.subject
        if moment.event == ON_DIED and subject is not None and subject not in owners:
            owners.append(subject)                  # погибший отвечает на собственную гибель
        out = []
        for owner in owners:
            for passive_id in owner.passive_ids:
                passive = self.db.passives.get(passive_id)
                if passive is not None and passive.reaction.event == moment.event:
                    out.append((owner, passive, passive.reaction, ("p", owner.uid, passive_id)))
            effects = list(owner.effects)
            if moment.effect is not None and owner is subject and not any(e is moment.effect for e in effects):
                effects.append(moment.effect)       # истёкший эффект отвечает на своё истечение
            for effect in effects:
                for index, reaction in enumerate(effect.definition.triggers):
                    if reaction.event == moment.event:
                        out.append((owner, effect, reaction, ("e", owner.uid, effect.definition.id, index)))
        return out

    def _owners(self) -> list[Unit]:
        owners = [u for side in self.sides for u in side.alive()]
        owners.sort(key=lambda u: -u.stat(Stat.INITIATIVE))
        return owners

    def _can_respond(self, owner: Unit) -> bool:
        return owner.is_alive and not any(owner.has_flag(f) for f in NO_PASSIVES)

    def _passive_cap_reached(self) -> bool:
        """Предел пассивок за активное действие (database.passives_per_action; -1 — без предела)."""
        limit = self._action.passive_limit
        return self._action.one_each and limit >= 0 and self._action.passives_fired >= limit

    def _matches(self, owner: Unit, origin, reaction: Reaction, moment: Moment, key: tuple,
                 counted: bool = True) -> bool:
        subject = moment.subject
        if not owner.is_alive and not (moment.event == ON_DIED and subject is owner and reaction.whose == "self"):
            return False
        if counted and isinstance(origin, PassiveDefinition) and not owner.pp.can_spend(origin.pp_cost):
            return False
        if counted and reaction.limit == LIMIT_BATTLE and key in self._uses:
            return False
        if counted and reaction.limit == LIMIT_ROUND and self._uses.get(key) == self.round:
            return False
        if moment.event not in EVENTS_WITHOUT_SUBJECT:
            if subject is None:
                return False
            same = self.side_of(owner) is self.side_of(subject)
            whose = reaction.whose
            if whose == "self" and subject is not owner or whose == "ally" and (not same or subject is owner) \
                    or whose == "enemy" and same:
                return False
            if not reaction.subject_condition.check(owner, subject):
                return False
            if reaction.area:
                area = self.db.areas.get(reaction.area)
                side = self.side_of(owner)
                if area is not None and (not same or not area.covers(side.pos(owner), side.pos(subject))):
                    return False
        if not reaction.self_condition.check(owner, owner):
            return False
        if moment.event in ATTACK_EVENTS:
            if reaction.attack_tags and not any(t in moment.attack_tags for t in reaction.attack_tags):
                return False
            if reaction.skill_areas and (moment.skill is None or moment.skill.area not in reaction.skill_areas):
                return False
        if moment.event == ON_ATTACKED and reaction.outcome != OUTCOME_ANY and reaction.outcome not in moment.outcomes:
            return False
        if moment.event in EFFECT_EVENTS and moment.effect is not None:
            if reaction.effect_filter == THIS_EFFECT and origin is not moment.effect:
                return False
            if reaction.effect_filter not in (None, THIS_EFFECT) and moment.effect.definition.id != reaction.effect_filter:
                return False
            if reaction.effect_label and reaction.effect_label not in moment.effect.definition.tags:
                return False
        if moment.event == ON_HP_BELOW and subject is not None:
            line = subject.max_hp * reaction.threshold
            if not (subject.is_alive and moment.hp_before >= line > subject.hp):
                return False
        return True

    def _recipients(self, owner: Unit, origin, reaction: Reaction, moment: Moment) -> list[Unit]:
        to = reaction.to
        source = self.units.get(origin.source) if isinstance(origin, ActiveEffect) and origin.source else owner
        role = {TO_OWNER: owner, TO_SUBJECT: moment.subject, TO_ACTOR: moment.actor, TO_TARGET: moment.target,
                TO_SOURCE: source}
        if to in role:
            unit = role[to]
            return [unit] if unit is not None and unit.is_alive else []
        own = self.side_of(owner)
        area = self.db.areas.get(reaction.to_area) if reaction.to_area else None
        if to == TO_ALLIES:
            units = [u for u in own.alive() if u is not owner]
        elif to == TO_ENEMIES:
            units = self.other(own).alive()
        elif to == TO_EVERYONE:
            units = [u for side in self.sides for u in side.alive() if u is not owner]
        else:
            return []
        if area is not None:                       # область вокруг владельца (на своей стороне — по его клетке)
            anchor = own.pos(owner)
            units = [u for u in units if area.covers(anchor, self.side_of(u).pos(u))]
        return units

    def _trigger_targets(self, owner: Unit, moment: Moment) -> list[Unit]:
        """Цели, из-за которых сработала пассивка: кто вызвал событие и с кем оно случилось.

        Порядок — «виновник» первым (актёр, цель навыка, источник эффекта, пострадавший),
        поэтому селектор «передний» у правила пассивки выбирает того, кто её вызвал.
        """
        source = self.units.get(moment.effect.source) if moment.effect is not None and moment.effect.source else None
        units: list[Unit] = []
        for unit in (moment.actor, moment.target, source, moment.subject, owner):
            if unit is None or not unit.is_alive or any(unit is other for other in units):
                continue
            units.append(unit)
        return units

    def _passive_plan(self, owner: Unit, passive_id: str, moment: Moment) -> Optional[tuple[SkillDefinition, Unit]]:
        """Правило тактики, привязанное к пассивке: навык и цель из вызвавших срабатывание.

        Правила проверяются сверху вниз; пусто — у пассивки нет своих правил, работает реакция из данных.
        """
        tactics = owner.passive_tactics.get(passive_id)
        if tactics is None or not tactics.rules:
            return None
        own, other = self.side_of(owner), self.other(self.side_of(owner))
        targets = self._trigger_targets(owner, moment)
        for rule in tactics.ordered(owner):
            skill = self.db.skills.get(rule.skill_id)
            if skill is None or skill.id not in owner.skill_ids:
                continue
            if not (skill.requires_self.check(owner, owner) and rule.self_condition.check(owner, owner)):
                continue
            side = own if skill.targets in ("ally", "self") else other
            pool = [owner] if skill.targets == "self" else [u for u in targets if side.has(u)]
            candidates = [u for u in pool if u.is_alive and skill.requires_target.check(owner, u)
                          and rule.condition.check(owner, u)]
            if candidates:
                return skill, rule.selector.select(owner, candidates, self.rng)
        return None

    def _perform(self, owner: Unit, origin, reaction: Reaction, moment: Moment, key: tuple) -> Optional[Act]:
        """Ответ: кому, оплата (PP пассивки), действие. Делать нечего — ничего не тратится, None."""
        passive = isinstance(origin, PassiveDefinition)
        skill = None
        plan = self._passive_plan(owner, origin.id, moment) if passive else None
        if plan is not None:                          # правила пассивки: навык по цели, вызвавшей срабатывание
            skill, chosen = plan
            action, targets = DO_USE_SKILL, [chosen]
        else:
            action = reaction.action
            targets = self._recipients(owner, origin, reaction, moment)
            if action == DO_USE_SKILL:
                skill = self.db.skills.get(reaction.skill_id or "")
                target = self._skill_target(owner, skill, reaction, moment, targets) if skill and owner.is_alive else None
                targets = [target] if target is not None and skill.requires_self.check(owner, owner) \
                    and skill.requires_target.check(owner, target) else []
            elif action == DO_APPLY_EFFECT:
                targets = [t for t in targets if self._would_apply(t, reaction.effect_id)]
            elif action == DO_REMOVE_EFFECT:
                targets = [t for t in targets if t.has_effect(reaction.effect_id or "")]
            elif action == DO_DISPEL:
                targets = [t for t in targets if any(reaction.label in e.definition.tags for e in t.effects)]
        if not targets:
            return None
        self._uses[key] = self.round
        if passive:
            if self._action.one_each:
                self._action.responded.add(owner.uid)
                self._action.passives_fired += 1
            owner.pp.spend(origin.pp_cost)
            sub = Act(PASSIVE, owner.uid, origin.id, reason=moment.event, pp_cost=origin.pp_cost, round=self.round)
            self._emit(sub, PassiveTriggered(owner.uid, origin.id))
            cause, source, stacks = origin.id, owner, 1
        else:
            sub = Act(AFFLICTION, owner.uid, origin.definition.id, target=owner.uid, reason=moment.event,
                      round=self.round)
            cause, source, stacks = origin.definition.id, self.units.get(origin.source) if origin.source else None, origin.stacks
        sub.targets = [t.uid for t in targets]
        for target in targets:
            if self.finished:
                break
            if not target.is_alive and action != DO_USE_SKILL:
                continue
            if action == DO_USE_SKILL:
                sub.skill_used, sub.target, sub.hits = skill.id, target.uid, skill.hits
                self._resolve(owner, skill, target, sub, root=False)
            elif action == DO_APPLY_EFFECT:
                self._give(target, reaction.effect_id, source, sub)
            elif action == DO_REMOVE_EFFECT:
                for effect in [e for e in target.effects if e.definition.id == reaction.effect_id]:
                    self._expire(target, effect, sub, "expire")
            elif action == DO_DISPEL:
                self._dispel(target, reaction.label or "", sub)
            elif action == DO_DAMAGE:
                amount = max(1, round(target.max_hp * reaction.amount / 100)) if reaction.percent \
                    else reaction.amount * stacks
                if reaction.percent:
                    amount *= stacks
                self._lose_hp(target, amount, source, cause, sub)
                if not target.is_alive:
                    self._die(target, sub)
                    self._check_wipe()
            elif action == DO_HEAL:
                amount = round(target.max_hp * reaction.amount / 100) if reaction.percent else reaction.amount * stacks
                self._heal(target, amount, source, cause, sub)
            elif action in (DO_RESTORE_AP, DO_RESTORE_PP):
                self._resource(target, "AP" if action == DO_RESTORE_AP else "PP", reaction.amount, source,
                               cause, sub)
        return sub

    def _skill_target(self, owner: Unit, skill: SkillDefinition, reaction: Reaction, moment: Moment,
                      targets: list[Unit]) -> Optional[Unit]:
        """Цель навыка-ответа: роль из момента или первая из группы; иначе ближайший подходящий (UO)."""
        own = self.side_of(owner)
        other = self.other(own)
        if skill.targets == "self":
            return owner
        wanted = own if skill.targets == "ally" else other
        for unit in targets:
            if unit.is_alive and wanted.has(unit):
                return unit
        if reaction.to in (TO_ALLIES, TO_ENEMIES, TO_EVERYONE) or not targets:
            pool = reachable(skill, owner, own, other)
            return default_order(owner, own, wanted, pool, self.rng)[0] if pool else None
        return None

    def _would_apply(self, unit: Unit, effect_id: Optional[str]) -> bool:
        definition = self.db.effects.get(effect_id or "")
        if definition is None or not unit.is_alive:
            return False
        if "debuff" in definition.tags and unit.has_flag("immune:debuff"):
            return False
        existing = next((e for e in unit.effects if e.definition.id == definition.id), None)
        return not (existing is not None and definition.stack_rule == StackRule.IGNORE)

    # --- изменения бойцов ---

    def _give(self, unit: Unit, effect_id: Optional[str], source: Optional[Unit], act: Act) -> Optional[ActiveEffect]:
        definition = self.db.effects.get(effect_id or "")
        if definition is not None and unit.is_alive and "debuff" in definition.tags and unit.has_flag("immune:debuff"):
            self._remove_flagged(unit, "immune:debuff", act)      # ослабление отражено, заряд потрачен
            return None
        if not self._would_apply(unit, effect_id):
            return None
        effect = unit.add_effect(definition, source.uid if source else None)
        if effect is None:
            return None
        self._action.fresh.append(effect)
        act.changes.append(Change(unit.uid, "effect", effect_id=definition.id, stacks=effect.stacks))
        self._emit(act, EffectApplied(unit.uid, definition.id, effect.stacks, source.uid if source else None))
        self._react(Moment(ON_EFFECT_APPLIED, subject=unit, actor=source, effect=effect), act.after)
        return effect

    def _expire(self, unit: Unit, effect: ActiveEffect, act: Act, kind: str = "expire") -> None:
        """Эффект снят (истёк, израсходован, снят навыком): событие и реакции на его истечение."""
        if effect in unit.effects:
            unit.effects.remove(effect)
        act.changes.append(Change(unit.uid, kind, effect_id=effect.definition.id))
        self._emit(act, EffectExpired(unit.uid, effect.definition.id))
        self._react(Moment(ON_EFFECT_EXPIRED, subject=unit, effect=effect), act.after)

    def _remove_flagged(self, unit: Unit, flag: str, act: Act) -> None:
        """Снять эффекты с флагом (заряды: разморозка, конец оглушения, израсходованный блок)."""
        for effect in [e for e in unit.effects if flag in e.definition.flags]:
            if effect.charges is not None and effect.charges > 1:
                effect.charges -= 1
                continue
            self._expire(unit, effect, act)

    def _dispel(self, unit: Unit, label: str, act: Act) -> None:
        for effect in [e for e in unit.effects if label in e.definition.tags]:
            self._expire(unit, effect, act, "dispel")

    def _resource(self, unit: Unit, name: str, amount: int, source: Optional[Unit], cause: str, act: Act) -> int:
        """AP/PP: +amount (не выше запаса) или −amount; возвращает, сколько на самом деле изменилось."""
        resource = unit.ap if name == "AP" else unit.pp
        before = resource.current
        if amount >= 0:
            resource.gain(amount)
        else:
            resource.current = max(0, before + amount)
        delta = resource.current - before
        if delta:
            act.changes.append(Change(unit.uid, name.lower(), delta, current=resource.current))
            self._emit(act, ResourceGained(source.uid if source else None, unit.uid, name, delta, resource.current, cause))
        return abs(delta)

    def _heal(self, unit: Unit, amount: int, source: Optional[Unit], cause: str, act: Act, crit: bool = False,
              change: bool = True) -> int:
        healed = unit.heal(max(0, amount))
        if change:
            act.changes.append(Change(unit.uid, "heal", healed, current=unit.hp))
        self._emit(act, Healed(source.uid if source else None, unit.uid, healed, unit.hp, cause, crit))
        if healed:
            self._react(Moment(ON_HEALED, subject=unit, actor=source), act.after)
        return healed

    def _lose_hp(self, unit: Unit, amount: int, source: Optional[Unit], cause: str, act: Act) -> None:
        lost = unit.take_damage(max(0, amount))
        act.changes.append(Change(unit.uid, "damage", lost, current=unit.hp))
        self._emit(act, DamageDealt(source.uid if source else None, unit.uid, lost, unit.hp, cause))
        self._hp_below(unit, lost, act)

    def _hp_below(self, unit: Unit, lost: int, act: Act) -> None:
        if lost and unit.is_alive:
            self._react(Moment(ON_HP_BELOW, subject=unit, hp_before=unit.hp + lost), act.after)

    def _die(self, unit: Unit, act: Act) -> None:
        if unit.uid in self._dead:
            return
        self._dead.add(unit.uid)
        act.deaths.append(unit.uid)
        self._emit(act, UnitDied(unit.uid))
        self._react(Moment(ON_DIED, subject=unit), act.after)
        unit.effects = []

    # --- конец ---

    def _check_wipe(self) -> None:
        if self._pending_end or self.finished:
            return
        left, right = (bool(side.alive()) for side in self.sides)
        if not (left and right):
            self._pending_end = END_DEFEAT if left or right else END_WIPEOUT

    def _end(self, reason: str) -> Act:
        """Пассивки конца боя (кто жив), итог, событие конца. Усиления и ослабления спадают."""
        self._pending_end = None
        act = Act(END, reason=reason, round=self.round)
        if reason != END_WIPEOUT:                  # пассивки «в конце боя»
            self._action = _Action(one_each=False)
            self._react(Moment(ON_BATTLE_END), act.after)
        left, right = self.sides
        if not left.alive() and not right.alive():
            winner = None
        elif not right.alive():
            winner = left.id
        elif not left.alive():
            winner = right.id
        elif reason == END_ROUND_LIMIT:
            winner = None                          # предохранитель сработал — ничья
        else:
            a, b = left.hp_share(), right.hp_share()
            winner = left.id if a > b else right.id if b > a else None
        self.finished = True
        self.winner_id = winner
        self.end_reason = reason
        act.winner = winner
        self._emit(act, BattleEnded(winner, reason))
        return act

    def _emit(self, act: Optional[Act], event: Event) -> None:
        self.events.append(event)
        self._step_events.append(event)
        if act is not None:
            act.events.append(event)
