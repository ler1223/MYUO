"""Симуляция боя двух отрядов. Графики не знает, наружу отдаёт только события."""
from __future__ import annotations

import random
from typing import Optional

from .areas import AREAS
from .database import Database
from .definitions import APPLY_SELF, APPLY_TARGET, SKILL_DAMAGE, SKILL_HEAL, PassiveDefinition, SkillDefinition
from .effects import ActiveEffect
from .events import (
    END_DEFEAT,
    END_EXHAUSTED,
    END_ROUND_LIMIT,
    END_WIPEOUT,
    SKIP_NO_ACTION,
    SKIP_STUNNED,
    BattleEnded,
    BattleStarted,
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
from .unit import AP_PER_TURN, Unit

DEFAULT_MAX_ROUNDS = 30
FALLBACK_SKILL_ID = "attack"
STUNNED_FLAG = "stunned"
DAMAGE_SPREAD = (0.9, 1.1)


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
        # разрешение ничьих по SPD и порядок срабатывания пассивок.
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
        self._check_end()
        self._check_exhausted()

    def _next_unit(self) -> Optional[Unit]:
        while not self.finished:
            while self._queue:
                unit = self._queue.pop(0)
                if unit.is_alive:
                    return unit
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
            # sorted устойчив: при равном SPD сохраняется исходный порядок.
            self._queue = sorted(self._alive(), key=lambda u: -u.stat(Stat.SPD))
        return None

    def _take_turn(self, unit: Unit) -> None:
        self._acting, self._fresh = unit, []
        self._emit(TurnStarted(unit.uid))
        self._apply_periodic(unit)
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
            if self.finished:
                return
        # Эффект, полученный в свой же ход, начинает убывать со следующего хода.
        for effect in unit.tick(skip=self._fresh):
            self._emit(EffectExpired(unit.uid, effect.definition.id))

    def _apply_periodic(self, unit: Unit) -> None:
        for effect in list(unit.effects):
            for action in effect.definition.periodic:
                amount = action.amount * effect.stacks
                if action.kind == "damage":
                    dealt = unit.take_damage(amount)
                    self._emit(DamageDealt(effect.source, unit.uid, dealt, unit.hp, effect.definition.id))
                    if not unit.is_alive:
                        self._emit(UnitDied(unit.uid))
                        self._check_end()
                        return
                elif action.kind == "heal":
                    healed = unit.heal(amount)
                    self._emit(Healed(effect.source, unit.uid, healed, unit.hp, effect.definition.id))

    def _act(self, unit: Unit) -> bool:
        """Выполняет действие по тактикам. False, если юнит ничего не смог сделать."""
        allies = self._alive(self._side[unit.uid])
        enemies = [u for u in self._alive() if self._side[u.uid] != self._side[unit.uid]]
        skills = {skill_id: self.db.skills[skill_id] for skill_id in self.db.skills_for(unit)}
        choice = unit.tactics.choose(unit, allies, enemies, self.rng, skills)
        if choice is None:
            # Ни одно правило не подошло: обычная атака по первому врагу, если на неё есть AP.
            fallback = skills.get(FALLBACK_SKILL_ID)
            if fallback is None or not enemies or not unit.ap.can_spend(fallback.ap_cost):
                return False
            choice = (FALLBACK_SKILL_ID, enemies[0])
        skill_id, target = choice
        skill = skills[skill_id]
        unit.ap.spend(skill.ap_cost)
        self._emit(SkillUsed(unit.uid, skill.id, target.uid))
        self._resolve_skill(unit, skill, target)
        return True

    def _affected(self, skill: SkillDefinition, target: Unit) -> list[Unit]:
        """Живые юниты стороны цели, попавшие в область навыка, в порядке формации."""
        in_area = AREAS[skill.area]
        target_pos = self._pos[target.uid]
        return [u for u in self._alive(self._side[target.uid]) if in_area(target_pos, self._pos[u.uid])]

    def _resolve_skill(self, user: Unit, skill: SkillDefinition, target: Unit) -> None:
        affected = self._affected(skill, target)
        for unit in affected:
            self._hit(user, skill, unit)
            for apply in skill.applies:
                if apply.to == APPLY_TARGET and unit.is_alive and apply.condition.check(user, unit):
                    self._apply_skill_effect(user, unit, apply.effect_id)
        for apply in skill.applies:
            if apply.to == APPLY_SELF and user.is_alive and apply.condition.check(user, target):
                self._apply_skill_effect(user, user, apply.effect_id)
        dead = [unit for unit in affected if not unit.is_alive]
        for unit in dead:
            self._emit(UnitDied(unit.uid))
        if dead:
            self._check_end()

    def _hit(self, user: Unit, skill: SkillDefinition, unit: Unit) -> None:
        """Урон или лечение одного задетого юнита и восстановление его AP/PP."""
        atk = user.stat(Stat.ATK)
        if skill.kind == SKILL_HEAL:
            healed = unit.heal(round(atk * skill.power))
            self._emit(Healed(user.uid, unit.uid, healed, unit.hp, skill.id))
        elif skill.kind == SKILL_DAMAGE:
            roll = self.rng.uniform(*DAMAGE_SPREAD)
            damage = max(1, round(atk * skill.power * roll - unit.stat(Stat.DEF) / 2))
            dealt = unit.take_damage(damage)
            self._emit(DamageDealt(user.uid, unit.uid, dealt, unit.hp, skill.id))
        if unit.is_alive:
            self._restore(user, unit, "AP", unit.ap, skill.ap_restore, skill.id)
            self._restore(user, unit, "PP", unit.pp, skill.pp_restore, skill.id)

    def _restore(self, user: Unit, unit: Unit, name: str, resource: Resource, amount: int, cause: str) -> None:
        if amount <= 0:
            return
        before = resource.current
        resource.gain(amount)
        if resource.current > before:  # полный запас: восстанавливать нечего
            self._emit(ResourceGained(user.uid, unit.uid, name, resource.current - before, resource.current, cause))

    def _apply_skill_effect(self, user: Unit, recipient: Unit, effect_id: str) -> None:
        effect = self._add_effect(recipient, effect_id, user.uid)
        if effect is not None:
            self._emit(EffectApplied(recipient.uid, effect_id, effect.stacks, user.uid))

    def _add_effect(self, recipient: Unit, effect_id: str, source: Optional[int]) -> Optional[ActiveEffect]:
        effect = recipient.add_effect(self.db.effects[effect_id], source)
        if effect is not None and recipient is self._acting:
            self._fresh.append(effect)
        return effect

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
        """Заканчивает бой, если ни у одного живого юнита нет AP даже на самый дешёвый навык."""
        if self.finished:
            return
        for unit in self._alive():
            if any(unit.ap.can_spend(self.db.skills[s].ap_cost) for s in self.db.skills_for(unit)):
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
        self.events.append(BattleEnded(winner_id, reason))

    # --- события и пассивки ---

    def _emit(self, event: Event, from_passive: bool = False) -> None:
        self.events.append(event)
        # События, порождённые пассивками, сами пассивки не запускают:
        # это исключает бесконечные цепочки при pp_cost 0.
        if not from_passive:
            self._dispatch_passives(event)

    def _dispatch_passives(self, event: Event) -> None:
        trigger = type(event).__name__
        for owner in self._alive():
            for passive_id in owner.passive_ids:
                passive = self.db.passives[passive_id]
                if passive.trigger != trigger or not self._scope_matches(passive, owner, event):
                    continue
                if not owner.pp.can_spend(passive.pp_cost):
                    continue
                effect = self._add_effect(owner, passive.effect_id, owner.uid)
                if effect is None:
                    continue  # эффект проигнорирован (IGNORE), PP не тратим
                owner.pp.spend(passive.pp_cost)
                self._emit(PassiveTriggered(owner.uid, passive.id), from_passive=True)
                self._emit(EffectApplied(owner.uid, passive.effect_id, effect.stacks, owner.uid), from_passive=True)

    def _scope_matches(self, passive: PassiveDefinition, owner: Unit, event: Event) -> bool:
        if passive.scope == "any":
            return True
        subject = event.subject()
        if subject is None:
            return False
        if passive.scope == "self":
            return subject == owner.uid
        same_side = self._side[subject] == self._side[owner.uid]
        if passive.scope == "ally":
            return same_side and subject != owner.uid
        return not same_side  # enemy

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
