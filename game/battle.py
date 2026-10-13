"""Симуляция боя двух отрядов. Графики не знает, наружу отдаёт только события."""
from __future__ import annotations

import random
from dataclasses import dataclass, replace
from typing import Optional, Union

from .database import Database
from .definitions import (
    APPLY_SELF,
    APPLY_TARGET,
    MAGICAL,
    PART_DAMAGE,
    PART_HEAL,
    PHYSICAL,
    PassiveDefinition,
    SkillDefinition,
    SkillPart,
)
from .effects import ActiveEffect, AttackMod, StackRule
from .events import (
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
from .resource import Resource
from .squad import Squad
from .stats import Stat
from .reactions import (
    ATTACK_EVENTS,
    DO_APPLY_EFFECT,
    DO_COVER,
    DO_DAMAGE,
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
    ON_BATTLE_START,
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
    TO_OWNER,
    TO_SOURCE,
    TO_SUBJECT,
    TO_TARGET,
    Reaction,
)
from .tags import rule_multipliers
from .unit import AP_PER_TURN, Unit

DEFAULT_MAX_ROUNDS = 30
FALLBACK_SKILL_ID = "attack"
STUNNED_FLAG = "stunned"
MAX_TRIGGER_DEPTH = 6     # предел цепочки «реакция вызвала событие, на которое снова реагируют...»
GUARD_REDUCTION = 0.5  # какая доля физического урона остаётся после блока

Origin = Union[PassiveDefinition, ActiveEffect]  # чья реакция: пассивки (стоит PP) или эффекта (бесплатно)


@dataclass
class Moment:
    """Случившееся в бою событие, на которое могут сработать реакции."""

    event: str
    subject: Optional[Unit] = None      # с кем случилось
    actor: Optional[Unit] = None        # кто вызвал
    skill: Optional[SkillDefinition] = None
    attack_tags: frozenset[str] = frozenset()
    outcomes: frozenset[str] = frozenset()   # для attacked: landed / crit / guarded или missed
    effect: Optional[ActiveEffect] = None
    hp_before: int = 0                   # для hp_below
    depth: int = 0                       # длина цепочки реакций, которая к нему привела
    target: Optional[Unit] = None       # основная цель навыка


class BattleSimulation:
    """Бой идёт, пока хоть один юнит может действовать.

    AP и PP сами не восстанавливаются, поэтому бой может закончиться при живых
    отрядах: тогда побеждает отряд с большей долей оставшегося HP.
    """

    def __init__(
        self,
        attacker: Squad,
        defender: Squad,
        db: Database,
        seed: Optional[int] = None,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
    ):
        self.attacker = attacker
        self.defender = defender
        self.db = db
        self.rng = random.Random(seed)
        self.max_rounds = max_rounds

        self.events: list[Event] = []
        self.round = 0
        self.finished = False
        self.winner_id: Optional[str] = None

        # Порядок «атакующий, затем защитник, внутри по формации» задаёт
        # разрешение ничьих по инициативе и порядок срабатывания пассивок.
        self._squads = (attacker, defender)
        self.units: dict[int, Unit] = {}
        self._side: dict[int, str] = {}
        self._pos: dict[int, tuple[int, int]] = {}
        for squad in self._squads:
            for unit in squad.formation.units:
                self.units[unit.uid] = unit
                self._side[unit.uid] = squad.id
                self._pos[unit.uid] = squad.formation.position_of(unit.uid)
        self._queue: list[Unit] = []
        self._started = False
        self._round_active = False  # был ли в раунде хоть один навык или оглушение
        self._acting: Optional[Unit] = None
        self._fresh: list[ActiveEffect] = []  # эффекты, полученные ходящим юнитом в этот ход
        # Реакции: моменты ждут в очереди, пока навык не разрешится до конца.
        self._pending: list[Moment] = []
        self._busy = 0                 # сколько навыков сейчас разрешается
        self._processing = False       # идёт разбор очереди моментов
        self._depth = 0                # глубина момента, реакции на который сейчас выполняются
        self._reaction_skills = 0      # навыки, применённые реакцией, не вызывают реакций на атаку
        self._used: dict[tuple, int] = {}  # ключ реакции -> раунд, в котором она сработала последней

    # --- публичный интерфейс ---

    def step(self) -> list[Event]:
        """Один ход одного юнита. Возвращает события, появившиеся за этот шаг."""
        mark = len(self.events)
        if not self.finished:
            if not self._started:
                self._start()
            unit = self._next_unit()
            if unit is not None:
                self._take_turn(unit)
                self._check_exhausted()
        return self.events[mark:]

    def run(self) -> list[Event]:
        while not self.finished:
            self.step()
        return self.events

    # --- ход боя ---

    def _start(self) -> None:
        self._started = True
        for unit in self.units.values():
            unit.start_battle()
        self._emit(BattleStarted(self.attacker.id, self.defender.id))
        self._raise(Moment(ON_BATTLE_START))
        self._check_end()
        self._check_exhausted()

    def _next_unit(self) -> Optional[Unit]:
        while not self.finished:
            while self._queue:
                unit = self._queue.pop(0)
                if unit.is_alive:
                    return unit
            if self.round > 0:
                self._raise(Moment(ON_ROUND_END))
                if self.finished:
                    break
            if self.round > 0 and not self._round_active:
                # AP есть, но условия тактик не дали никому действовать целый раунд.
                self._finish_by_hp(END_EXHAUSTED)
                break
            if self.round >= self.max_rounds:
                self._finish(None, END_ROUND_LIMIT)
                break
            self.round += 1
            self._round_active = False
            self._emit(RoundStarted(self.round))
            self._raise(Moment(ON_ROUND_START))
            # sorted устойчив: при равной инициативе сохраняется исходный порядок.
            self._queue = sorted(self._alive(), key=lambda u: -u.stat(Stat.INITIATIVE))
        return None

    def _take_turn(self, unit: Unit) -> None:
        self._acting, self._fresh = unit, []
        self._emit(TurnStarted(unit.uid))
        self._raise(Moment(ON_TURN_START, unit, unit))
        if self.finished or not unit.is_alive:
            return
        if unit.has_flag(STUNNED_FLAG):
            self._round_active = True  # оглушение пройдёт, бой ещё не выдохся
            self._emit(TurnSkipped(unit.uid, SKIP_STUNNED))
        else:
            unit.ap.gain(AP_PER_TURN)
            if self._act(unit):
                self._round_active = True
            else:
                self._emit(TurnSkipped(unit.uid, SKIP_NO_ACTION))
            if self.finished or not unit.is_alive:
                return
        # Эффект, полученный в свой же ход, начинает убывать со следующего хода.
        for effect in unit.tick(skip=self._fresh):
            self._expire(unit, effect)
        if not self.finished and unit.is_alive:
            self._raise(Moment(ON_TURN_END, unit, unit))

    def _expire(self, unit: Unit, effect: ActiveEffect) -> None:
        self._emit(EffectExpired(unit.uid, effect.definition.id))
        self._raise(Moment(ON_EFFECT_EXPIRED, unit, self.units.get(effect.source), effect=effect))

    def _act(self, unit: Unit) -> bool:
        """Выполняет действие по тактикам. False, если юнит ничего не смог сделать."""
        allies = self._alive(self._side[unit.uid])
        enemies = [u for u in self._alive() if self._side[u.uid] != self._side[unit.uid]]
        skills = {skill_id: self.db.skills[skill_id] for skill_id in unit.skill_ids if skill_id in self.db.skills}
        choice = unit.tactics.choose(unit, allies, enemies, self.rng, skills)
        if choice is None:
            # Ни одно правило не подошло: обычная атака по первому врагу, если на неё есть AP.
            fallback = skills.get(FALLBACK_SKILL_ID)
            if fallback is None or not enemies or not fallback.affordable(unit):
                return False
            choice = (FALLBACK_SKILL_ID, enemies[0])
        skill_id, target = choice
        skill = skills[skill_id]
        unit.ap.spend(skill.ap_cost)
        unit.pp.spend(skill.pp_cost)
        self._emit(SkillUsed(unit.uid, skill.id, target.uid))
        self._resolve_skill(unit, skill, target)
        if not self.finished:
            self._raise(Moment(ON_SKILL_USED, unit, unit, skill, target=target))
        return True

    def _affected(self, skill: SkillDefinition, target: Unit) -> list[Unit]:
        """Живые юниты стороны цели, попавшие в область навыка, в порядке формации."""
        area = self.db.areas[skill.area]
        target_pos = self._pos[target.uid]
        return [u for u in self._alive(self._side[target.uid]) if area.covers(target_pos, self._pos[u.uid])]

    def _resolve_skill(self, user: Unit, skill: SkillDefinition, target: Unit) -> None:
        """Разрешает навык целиком; реакции на всё случившееся выполняются после него."""
        self._busy += 1
        try:
            self._resolve(user, skill, target)
        finally:
            self._busy -= 1
        self._flush()

    def _resolve(self, user: Unit, skill: SkillDefinition, target: Unit) -> None:
        affected = self._affected(skill, target)
        used = self._attack_mods(user, skill)
        mods = [mod for _, mod in used]
        attack_tags = self._attack_tags(user, skill, mods)
        affected, protector = self._before_attack(user, skill, target, affected, attack_tags)
        reacts = not self._reaction_skills and any(part.kind == PART_DAMAGE for part in skill.parts)
        landed: list[Unit] = []  # по кому попал хотя бы один удар
        for _ in range(skill.hits):
            for unit in affected:
                if not unit.is_alive:
                    continue
                outcome = self._hit(user, skill, unit, mods, unit is protector)
                if outcome is not None and unit not in landed:
                    landed.append(unit)
                if reacts:
                    outcomes = outcome or frozenset({OUTCOME_MISSED})
                    self._raise(Moment(ON_ATTACKED, unit, user, skill, attack_tags, outcomes, target=target))
        for unit in landed:
            if not unit.is_alive:
                continue
            self._restore(user.uid, unit, "AP", unit.ap, skill.ap_restore, skill.id)
            self._restore(user.uid, unit, "PP", unit.pp, skill.pp_restore, skill.id)
            for apply in skill.applies:
                if apply.to == APPLY_TARGET and apply.condition.check(user, unit):
                    self._give_effect(unit, apply.effect_id, user.uid)
        if landed:
            for apply in skill.applies:
                if apply.to == APPLY_SELF and user.is_alive and apply.condition.check(user, target):
                    self._give_effect(user, apply.effect_id, user.uid)
        self._spend_charges(user, [effect for effect, _ in used])
        dead = [unit for unit in affected if not unit.is_alive]
        for unit in dead:
            self._die(unit, user)
        if dead:
            self._check_end()

    def _attack_tags(self, user: Unit, skill: SkillDefinition, mods: list[AttackMod]) -> frozenset[str]:
        """Все теги атаки: вид навыка, категории и типы урона частей, добавленные эффектами."""
        tags = {*skill.tags, *(part.category for part in skill.parts)}
        for part in skill.parts:
            tags.update(self._part_tags(user, part))
        for mod in mods:
            tags.update(mod.add_tags)
        return frozenset(tags)

    def _before_attack(self, user: Unit, skill: SkillDefinition, target: Unit, affected: list[Unit],
                       attack_tags: frozenset[str]) -> tuple[list[Unit], Optional[Unit]]:
        """Фаза «до»: реакции на выбор целей, не больше одной на каждую сторону.

        Прикрытие перенаправляет удары по союзникам на владельца: удары по всем
        прикрытым сливаются в один удар по нему. Возвращает (задетые, защитник или None).
        """
        if self._reaction_skills or not affected:
            return affected, None
        moment = Moment(ON_TARGETED, affected[0], user, skill, attack_tags, target=target)
        reacted: set[str] = set()
        protector: Optional[Unit] = None
        for owner, origin, reaction, key in self._reactors(moment):
            side = self._side[owner.uid]
            if self.finished or side in reacted:
                continue
            subjects = [u for u in affected if self._matches(owner, origin, reaction, moment, u)]
            if not subjects:
                continue
            if reaction.action == DO_COVER:
                if protector is not None or self._side[user.uid] == side or not owner.is_alive:
                    continue  # свои навыки не перехватываются
                if not self._can_pay(owner, origin, reaction, key):
                    continue
                covered = subjects if reaction.cover_many else subjects[:1]
                self._pay(owner, origin, key)
                for unit in covered:
                    self._emit(Covered(owner.uid, unit.uid, skill.id))
                if reaction.effect_id is not None:
                    self._give_effect(owner, reaction.effect_id, owner.uid)
                result: list[Unit] = []
                for unit in affected:
                    replacement = owner if unit in covered else unit
                    if replacement not in result:
                        result.append(replacement)
                affected, protector = result, owner
            elif not self._perform(owner, origin, reaction, replace(moment, subject=subjects[0]), key):
                continue
            reacted.add(side)
        return [u for u in affected if u.is_alive], protector

    def _attack_mods(self, user: Unit, skill: SkillDefinition) -> list[tuple[ActiveEffect, AttackMod]]:
        """Изменения навыка от эффектов применяющего (зачарования и т. п.)."""
        if not skill.parts:
            return []
        return [
            (effect, mod)
            for effect in user.effects
            for mod in effect.definition.attack_mods
            if mod.skill_tag is None or mod.skill_tag in skill.tags
        ]

    def _spend_charges(self, user: Unit, used: list[ActiveEffect]) -> None:
        """Эффекты с зарядами расходуют один заряд за применённый навык."""
        spent: list[ActiveEffect] = []
        for effect in used:
            if effect.charges is None or any(effect is done for done in spent):
                continue
            spent.append(effect)
            effect.charges -= 1
            if effect.charges <= 0 and any(effect is active for active in user.effects):
                user.effects = [active for active in user.effects if active is not effect]
                self._expire(user, effect)

    def _part_tags(self, user: Unit, part: SkillPart) -> set[str]:
        """Теги части урона: категория плюс тип урона (оружия, если часть его использует)."""
        weapon = user.weapon_damage_tags if part.weapon_tags else ()
        return {part.category, *(weapon or part.tags)}

    def _hit(self, user: Unit, skill: SkillDefinition, unit: Unit, mods: list[AttackMod],
             unevadable: bool = False) -> Optional[frozenset[str]]:
        """Один удар по одному юниту: попадание, крит, блок, затем все части навыка.

        unevadable: уклонение цели не учитывается (защитник, принявший удар на себя).
        Возвращает исходы удара (landed, crit, guarded) или None при промахе.
        """
        hostile = self._side[unit.uid] != self._side[user.uid]
        common = {*skill.tags, *user.tags}
        for mod in mods:
            common.update(mod.add_tags)
        part_tags = [common | self._part_tags(user, part) for part in skill.parts]
        target_tags = unit.tags
        all_tags = set(common).union(*part_tags)

        # Попадание: шанс навыка * точность, правила тегов, минус уклонение врага.
        chance = skill.accuracy * user.stat(Stat.ACCURACY) / 100
        chance *= rule_multipliers(self.db.rules, all_tags, target_tags)[1]
        chance += sum(mod.accuracy_add for mod in mods)
        if hostile and not unevadable:
            chance -= unit.stat(Stat.EVASION)
        if self.rng.random() * 100 >= chance:
            self._emit(AttackMissed(user.uid, unit.uid, skill.id))
            return None

        crit_chance = user.stat(Stat.CRIT_RATE) + sum(mod.crit_add for mod in mods)
        crit = bool(skill.parts) and self.rng.random() * 100 < crit_chance
        crit_mult = user.stat(Stat.CRIT_DAMAGE) / 100 if crit else 1.0
        guarded = hostile and self._roll_guard(skill, unit, part_tags)
        power_mult = 1.0
        for mod in mods:
            power_mult *= mod.power_mult
        extra = [scale for mod in mods for scale in mod.add_scaling]
        bonus = 1.0
        for tag, mult in skill.bonus_vs:
            if tag in target_tags:
                bonus *= mult

        for part, tags in zip(skill.parts, part_tags):
            if not unit.is_alive:
                break
            value = sum(user.stat(scale.stat) * scale.coef for scale in (*part.scaling, *extra))
            if part.kind == PART_HEAL:
                self._heal(unit, round(value * part.power * power_mult * crit_mult), user.uid, skill.id, crit)
                continue
            defense = {PHYSICAL: Stat.PHYS_DEF, MAGICAL: Stat.MAG_DEF}.get(part.category)
            damage = (value - (unit.stat(defense) if defense else 0)) * part.power * power_mult
            damage *= rule_multipliers(self.db.rules, tags, target_tags)[0] * bonus * crit_mult
            blocked = guarded and part.category == PHYSICAL
            if blocked:
                damage *= GUARD_REDUCTION
            self._deal(unit, max(1, round(damage)), user.uid, skill.id, crit, blocked)
        outcome = {OUTCOME_LANDED}
        if crit:
            outcome.add(OUTCOME_CRIT)
        if guarded:
            outcome.add(OUTCOME_GUARDED)
        return frozenset(outcome)

    def _roll_guard(self, skill: SkillDefinition, unit: Unit, part_tags: list[set[str]]) -> bool:
        """Блок возможен, если в навыке есть физический урон и нет неблокируемого типа."""
        physical = [tags for part, tags in zip(skill.parts, part_tags)
                    if part.kind != PART_HEAL and part.category == PHYSICAL]
        if not physical:
            return False
        if any(tag in self.db.tags and self.db.tags[tag].unblockable for tags in physical for tag in tags):
            return False
        return self.rng.random() * 100 < unit.stat(Stat.GUARD_RATE)

    def _restore(self, source: Optional[int], unit: Unit, name: str, resource: Resource, amount: int,
                 cause: str) -> None:
        if amount <= 0:
            return
        before = resource.current
        resource.gain(amount)
        if resource.current > before:  # полный запас: восстанавливать нечего
            self._emit(ResourceGained(source, unit.uid, name, resource.current - before, resource.current, cause))

    def _would_apply(self, recipient: Unit, effect_id: str) -> bool:
        """Изменит ли наложение что-нибудь (эффект с правилом IGNORE второй раз не накладывается)."""
        definition = self.db.effects[effect_id]
        return not (definition.stack_rule is StackRule.IGNORE and recipient.has_effect(effect_id))

    def _give_effect(self, recipient: Unit, effect_id: str, source: Optional[int]) -> Optional[ActiveEffect]:
        """Накладывает эффект и сообщает об этом."""
        effect = recipient.add_effect(self.db.effects[effect_id], source)
        if effect is None:
            return None
        if recipient is self._acting:
            self._fresh.append(effect)
        self._emit(EffectApplied(recipient.uid, effect_id, effect.stacks, source))
        self._raise(Moment(ON_EFFECT_APPLIED, recipient, self.units.get(source), effect=effect))
        return effect

    def _deal(self, unit: Unit, amount: int, source: Optional[int], cause: str,
              crit: bool = False, guarded: bool = False) -> int:
        """Снимает HP и сообщает об этом. Гибель обрабатывает вызывающий."""
        before = unit.hp
        dealt = unit.take_damage(amount)
        self._emit(DamageDealt(source, unit.uid, dealt, unit.hp, cause, crit, guarded))
        if dealt:
            self._raise(Moment(ON_HP_BELOW, unit, self.units.get(source), hp_before=before))
        return dealt

    def _heal(self, unit: Unit, amount: int, source: Optional[int], cause: str, crit: bool = False) -> None:
        healed = unit.heal(amount)
        self._emit(Healed(source, unit.uid, healed, unit.hp, cause, crit))
        if healed:
            self._raise(Moment(ON_HEALED, unit, self.units.get(source)))

    def _die(self, unit: Unit, killer: Optional[Unit]) -> None:
        self._emit(UnitDied(unit.uid))
        self._raise(Moment(ON_DIED, unit, killer))

    # --- окончание боя ---

    def _check_end(self) -> None:
        if self.finished:
            return
        attacker_alive = bool(self._alive(self.attacker.id))
        defender_alive = bool(self._alive(self.defender.id))
        if attacker_alive and defender_alive:
            return
        if attacker_alive:
            self._finish(self.attacker.id, END_DEFEAT)
        elif defender_alive:
            self._finish(self.defender.id, END_DEFEAT)
        else:
            self._finish(None, END_WIPEOUT)

    def _check_exhausted(self) -> None:
        """Заканчивает бой, если ни одному живому юниту не хватает AP и PP ни на один его навык."""
        if self.finished:
            return
        for unit in self._alive():
            if any(self.db.skills[s].affordable(unit) for s in unit.skill_ids if s in self.db.skills):
                return
        self._finish_by_hp(END_EXHAUSTED)

    def _hp_share(self, squad: Squad) -> float:
        """Доля оставшегося HP отряда; погибшие считаются нулём."""
        units = squad.formation.units
        total = sum(u.max_hp for u in units)
        return sum(u.hp for u in units) / total if total else 0.0

    def _finish_by_hp(self, reason: str) -> None:
        attacker, defender = self._hp_share(self.attacker), self._hp_share(self.defender)
        if attacker > defender:
            self._finish(self.attacker.id, reason)
        elif defender > attacker:
            self._finish(self.defender.id, reason)
        else:
            self._finish(None, reason)

    def _finish(self, winner_id: Optional[str], reason: str) -> None:
        self.finished = True
        self.winner_id = winner_id
        self._queue.clear()
        self._pending.clear()
        self.events.append(BattleEnded(winner_id, reason))

    # --- события и реакции ---

    def _emit(self, event: Event) -> None:
        self.events.append(event)

    def _raise(self, moment: Moment) -> None:
        """Ставит момент в очередь реакций; очередь разбирается, когда навык разрешён до конца."""
        moment.depth = self._depth + 1 if self._processing else 0
        self._pending.append(moment)
        self._flush()

    def _flush(self) -> None:
        if self._busy or self._processing:
            return
        self._processing = True
        try:
            while self._pending and not self.finished:
                moment = self._pending.pop(0)
                if moment.depth > MAX_TRIGGER_DEPTH:
                    continue  # обрываем цепочку: реакции вызывают друг друга по кругу
                self._depth = moment.depth
                self._react(moment)
        finally:
            self._processing = False
            self._depth = 0
            if self.finished:
                self._pending.clear()

    def _react(self, moment: Moment) -> None:
        """Фаза «после»: срабатывают все подходящие реакции, у кого хватает PP."""
        for owner, origin, reaction, key in self._reactors(moment):
            if self.finished:
                return
            if self._matches(owner, origin, reaction, moment):
                self._perform(owner, origin, reaction, moment, key)

    def _reactors(self, moment: Moment) -> list[tuple[Unit, Origin, Reaction, tuple]]:
        """Все реакции, которые могут ответить на момент, в порядке срабатывания.

        Порядок: по убыванию инициативы владельца, при равенстве по формации;
        у владельца сначала пассивки, затем эффекты. Погибший отвечает только
        на собственную гибель.
        """
        owners = sorted(self._alive(), key=lambda u: -u.stat(Stat.INITIATIVE))
        subject = moment.subject
        if moment.event == ON_DIED and subject is not None and subject not in owners:
            owners.append(subject)
        result: list[tuple[Unit, Origin, Reaction, tuple]] = []
        for owner in owners:
            for passive_id in owner.passive_ids:
                passive = self.db.passives.get(passive_id)
                if passive is not None and passive.reaction.event == moment.event:
                    result.append((owner, passive, passive.reaction, ("p", owner.uid, passive_id)))
            effects = list(owner.effects)
            if moment.effect is not None and owner is subject and not any(e is moment.effect for e in effects):
                effects.append(moment.effect)  # истёкший эффект ещё отвечает на собственное истечение
            for effect in effects:
                for index, reaction in enumerate(effect.definition.triggers):
                    if reaction.event == moment.event:
                        result.append((owner, effect, reaction, ("e", owner.uid, effect.definition.id, index)))
        return result

    def _matches(self, owner: Unit, origin: Origin, reaction: Reaction, moment: Moment,
                 subject: Optional[Unit] = None) -> bool:
        """Подходит ли момент под событие и фильтры реакции (subject: замена moment.subject)."""
        subject = subject or moment.subject
        if not owner.is_alive and not (moment.event == ON_DIED and subject is owner and reaction.whose == "self"):
            return False
        if moment.event not in EVENTS_WITHOUT_SUBJECT:
            if subject is None or not self._whose(owner, subject, reaction.whose):
                return False
            if reaction.area and not self.db.areas[reaction.area].covers(self._pos[owner.uid], self._pos[subject.uid]):
                return False
            if not reaction.subject_condition.check(owner, subject):
                return False
        if not reaction.self_condition.check(owner, owner):
            return False
        if moment.event in ATTACK_EVENTS:
            if reaction.attack_tags and not moment.attack_tags.intersection(reaction.attack_tags):
                return False
            if reaction.skill_areas and moment.skill.area not in reaction.skill_areas:
                return False
        if moment.event == ON_ATTACKED and reaction.outcome != OUTCOME_ANY and reaction.outcome not in moment.outcomes:
            return False
        if moment.event in EFFECT_EVENTS and reaction.effect_filter:
            if reaction.effect_filter == THIS_EFFECT:
                if origin is not moment.effect:
                    return False
            elif moment.effect.definition.id != reaction.effect_filter:
                return False
        if moment.event == ON_HP_BELOW:
            line = subject.max_hp * reaction.threshold
            if not (subject.is_alive and moment.hp_before >= line > subject.hp):
                return False  # срабатывает только при пересечении порога сверху вниз
        return True

    def _whose(self, owner: Unit, subject: Unit, whose: str) -> bool:
        if whose == "any":
            return True
        if whose == "self":
            return subject is owner
        same_side = self._side[subject.uid] == self._side[owner.uid]
        if whose == "ally":
            return same_side and subject is not owner
        return not same_side  # enemy

    def _can_pay(self, owner: Unit, origin: Origin, reaction: Reaction, key: tuple) -> bool:
        if reaction.limit == LIMIT_ROUND and self._used.get(key) == self.round:
            return False
        if reaction.limit == LIMIT_BATTLE and key in self._used:
            return False
        if isinstance(origin, PassiveDefinition):
            # Пассивки стоят PP; оглушённый пассивками не пользуется.
            return not owner.has_flag(STUNNED_FLAG) and owner.pp.can_spend(origin.pp_cost)
        return True

    def _pay(self, owner: Unit, origin: Origin, key: tuple) -> None:
        self._used[key] = self.round
        if isinstance(origin, PassiveDefinition):
            owner.pp.spend(origin.pp_cost)
            self._emit(PassiveTriggered(owner.uid, origin.id))

    def _reaction_targets(self, owner: Unit, origin: Origin, reaction: Reaction, moment: Moment) -> list[Unit]:
        to = reaction.to
        if to == TO_OWNER:
            units = [owner]
        elif to == TO_SUBJECT:
            units = [moment.subject]
        elif to == TO_ACTOR:
            units = [moment.actor]
        elif to == TO_TARGET:
            units = [moment.target]
        elif to == TO_SOURCE:
            units = [self.units.get(origin.source) if isinstance(origin, ActiveEffect) else owner]
        else:
            own = self._side[owner.uid]
            units = [u for u in self._alive() if u is not owner]
            if to == TO_ALLIES:
                units = [u for u in units if self._side[u.uid] == own]
            elif to == TO_ENEMIES:
                units = [u for u in units if self._side[u.uid] != own]
            if reaction.to_area is not None:
                area = self.db.areas[reaction.to_area]
                units = [u for u in units if area.covers(self._pos[owner.uid], self._pos[u.uid])]
        return [u for u in units if u is not None and u.is_alive]

    def _perform(self, owner: Unit, origin: Origin, reaction: Reaction, moment: Moment, key: tuple) -> bool:
        """Выполняет действие реакции. False, если делать нечего: тогда PP не тратятся."""
        if reaction.action == DO_COVER:
            return False  # прикрытие работает только в фазе «до»
        targets = self._reaction_targets(owner, origin, reaction, moment)
        if reaction.action == DO_USE_SKILL:
            skill = self.db.skills.get(reaction.skill_id)
            targets = [t for t in targets[:1] if skill is not None and owner.is_alive
                       and skill.requires_self.check(owner, owner) and skill.requires_target.check(owner, t)]
        elif reaction.action == DO_APPLY_EFFECT:
            targets = [t for t in targets if self._would_apply(t, reaction.effect_id)]
        elif reaction.action == DO_REMOVE_EFFECT:
            targets = [t for t in targets if t.has_effect(reaction.effect_id)]
        if not targets or not self._can_pay(owner, origin, reaction, key):
            return False
        self._pay(owner, origin, key)

        is_effect = isinstance(origin, ActiveEffect)
        cause = origin.definition.id if is_effect else origin.id
        source = origin.source if is_effect else owner.uid
        amount = reaction.amount * (origin.stacks if is_effect else 1)  # урон и лечение эффекта растут со стаками
        for target in targets:
            if self.finished:
                break
            if not target.is_alive:
                continue
            if reaction.action == DO_USE_SKILL:
                # Навык-реакция стоит только PP пассивки и не вызывает реакций на атаку.
                self._emit(SkillUsed(owner.uid, reaction.skill_id, target.uid))
                self._reaction_skills += 1
                try:
                    self._resolve_skill(owner, self.db.skills[reaction.skill_id], target)
                finally:
                    self._reaction_skills -= 1
            elif reaction.action == DO_APPLY_EFFECT:
                self._give_effect(target, reaction.effect_id, source)
            elif reaction.action == DO_REMOVE_EFFECT:
                for active in [e for e in target.effects if e.definition.id == reaction.effect_id]:
                    target.effects = [e for e in target.effects if e is not active]
                    self._expire(target, active)
            elif reaction.action == DO_DAMAGE:
                self._deal(target, amount, source, cause)
                if not target.is_alive:
                    self._die(target, self.units.get(source))
                    self._check_end()
            elif reaction.action == DO_HEAL:
                self._heal(target, amount, source, cause)
            elif reaction.action == DO_RESTORE_AP:
                self._restore(source, target, "AP", target.ap, reaction.amount, cause)
            elif reaction.action == DO_RESTORE_PP:
                self._restore(source, target, "PP", target.pp, reaction.amount, cause)
        return True

    # --- вспомогательное ---

    def _alive(self, squad_id: Optional[str] = None) -> list[Unit]:
        """Живые юниты в порядке формации; без аргумента обеих сторон."""
        return [
            unit
            for squad in self._squads
            if squad_id is None or squad.id == squad_id
            for unit in squad.formation.units
            if unit.is_alive
        ]
