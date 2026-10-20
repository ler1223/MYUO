"""События боя. Симуляция только порождает их, визуализация только читает."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Optional

# Причины окончания боя (BattleEnded.reason) и пропуска хода (TurnSkipped.reason).
END_DEFEAT = "defeat"            # один отряд уничтожен
END_WIPEOUT = "wipeout"          # уничтожены оба
END_EXHAUSTED = "exhausted"      # никто больше не может действовать, решает остаток HP
END_ROUND_LIMIT = "round_limit"  # лимит раундов, ничья
SKIP_STUNNED = "stunned"
SKIP_NO_ACTION = "no_action"
SKIP_CHARGE = "charge"          # ход ушёл на подготовку навыка (extras.charge)

REASON_TEXT = {
    END_DEFEAT: "enemy squad defeated",
    END_WIPEOUT: "both squads defeated",
    END_EXHAUSTED: "no actions left, decided by remaining HP",
    END_ROUND_LIMIT: "round limit",
    SKIP_STUNNED: "stunned",
    SKIP_NO_ACTION: "no action available",
    SKIP_CHARGE: "charging a skill",
}


@dataclass(frozen=True)
class Event:
    # Имя поля с uid юнита, «чьё» это событие (для scope пассивок). None = ничьё.
    SUBJECT: ClassVar[Optional[str]] = None

    def subject(self) -> Optional[int]:
        return getattr(self, self.SUBJECT) if self.SUBJECT else None


@dataclass(frozen=True)
class BattleStarted(Event):
    attacker_id: str
    defender_id: str


@dataclass(frozen=True)
class RoundStarted(Event):
    round: int


@dataclass(frozen=True)
class TurnStarted(Event):
    SUBJECT: ClassVar[Optional[str]] = "unit"
    unit: int


@dataclass(frozen=True)
class TurnSkipped(Event):
    SUBJECT: ClassVar[Optional[str]] = "unit"
    unit: int
    reason: str


@dataclass(frozen=True)
class SkillUsed(Event):
    SUBJECT: ClassVar[Optional[str]] = "user"
    user: int
    skill_id: str
    target: int  # основная цель; навык по области задевает и других


@dataclass(frozen=True)
class AttackMissed(Event):
    """Удар навыка не попал по цели."""

    SUBJECT: ClassVar[Optional[str]] = "target"
    source: int
    target: int
    cause: str


@dataclass(frozen=True)
class DamageDealt(Event):
    SUBJECT: ClassVar[Optional[str]] = "target"
    source: Optional[int]
    target: int
    amount: int
    hp_left: int
    cause: str  # id навыка или эффекта
    crit: bool = False
    guarded: bool = False  # часть урона заблокирована


@dataclass(frozen=True)
class Healed(Event):
    SUBJECT: ClassVar[Optional[str]] = "target"
    source: Optional[int]
    target: int
    amount: int
    hp_left: int
    cause: str
    crit: bool = False


@dataclass(frozen=True)
class ResourceGained(Event):
    """Навык восстановил AP или PP."""

    SUBJECT: ClassVar[Optional[str]] = "target"
    source: Optional[int]
    target: int
    resource: str  # "AP" | "PP"
    amount: int
    current: int
    cause: str


@dataclass(frozen=True)
class EffectApplied(Event):
    SUBJECT: ClassVar[Optional[str]] = "target"
    target: int
    effect_id: str
    stacks: int
    source: Optional[int]


@dataclass(frozen=True)
class EffectExpired(Event):
    SUBJECT: ClassVar[Optional[str]] = "target"
    target: int
    effect_id: str


@dataclass(frozen=True)
class PassiveTriggered(Event):
    SUBJECT: ClassVar[Optional[str]] = "unit"
    unit: int
    passive_id: str


@dataclass(frozen=True)
class Covered(Event):
    """Защитник принял на себя удар, нацеленный на союзника."""

    SUBJECT: ClassVar[Optional[str]] = "target"
    protector: int
    target: int   # кого прикрыли
    cause: str    # id навыка врага


@dataclass(frozen=True)
class UnitDied(Event):
    SUBJECT: ClassVar[Optional[str]] = "unit"
    unit: int


@dataclass(frozen=True)
class BattleEnded(Event):
    winner_id: Optional[str]  # None = ничья
    reason: str


def _plain(text: str, **params: Any) -> str:
    return text.format(**params) if params else text


def format_event(ev: Event, name_fn: Callable[[int], str], tr: Optional[Callable[..., str]] = None) -> str:
    """Текст события для лога.

    name_fn превращает uid в подпись юнита. tr (например, i18n.Translator)
    переводит шаблоны и названия; без него текст английский, а навыки и
    эффекты подписаны своими id.
    """
    t = tr or _plain
    match ev:
        case BattleStarted():
            return t("=== Battle: {a} vs {b} ===", a=t(ev.attacker_id), b=t(ev.defender_id))
        case RoundStarted():
            return t("--- Round {n} ---", n=ev.round)
        case TurnStarted():
            return t("{unit} turn", unit=name_fn(ev.unit))
        case TurnSkipped():
            return t("  {unit} skips the turn ({reason})", unit=name_fn(ev.unit), reason=t(REASON_TEXT[ev.reason]))
        case SkillUsed():
            return t("  {user} uses {skill} on {target}",
                     user=name_fn(ev.user), skill=t(ev.skill_id), target=name_fn(ev.target))
        case AttackMissed():
            return t("  {source} misses {target} with {cause}",
                     source=name_fn(ev.source), target=name_fn(ev.target), cause=t(ev.cause))
        case DamageDealt():
            notes = "".join(f", {t(word)}" for word, on in (("crit", ev.crit), ("guarded", ev.guarded)) if on)
            return t("  {target} takes {amount} damage from {cause} (HP {hp})",
                     target=name_fn(ev.target), amount=ev.amount, cause=t(ev.cause) + notes, hp=ev.hp_left)
        case Healed():
            notes = f", {t('crit')}" if ev.crit else ""
            return t("  {target} is healed for {amount} by {cause} (HP {hp})",
                     target=name_fn(ev.target), amount=ev.amount, cause=t(ev.cause) + notes, hp=ev.hp_left)
        case ResourceGained() if ev.amount < 0:
            return t("  {target} loses {amount} {resource} from {cause} ({resource} {current})",
                     target=name_fn(ev.target), amount=-ev.amount, resource=ev.resource,
                     cause=t(ev.cause), current=ev.current)
        case ResourceGained():
            return t("  {target} gains {amount} {resource} from {cause} ({resource} {current})",
                     target=name_fn(ev.target), amount=ev.amount, resource=ev.resource,
                     cause=t(ev.cause), current=ev.current)
        case EffectApplied():
            stacks = f" x{ev.stacks}" if ev.stacks > 1 else ""
            return t("  {target} gains {effect}", target=name_fn(ev.target), effect=t(ev.effect_id) + stacks)
        case EffectExpired():
            return t("  {target} loses {effect}", target=name_fn(ev.target), effect=t(ev.effect_id))
        case PassiveTriggered():
            return t("  {unit} triggers passive {passive}", unit=name_fn(ev.unit), passive=t(ev.passive_id))
        case Covered():
            return t("  {protector} covers {target} from {cause}",
                     protector=name_fn(ev.protector), target=name_fn(ev.target), cause=t(ev.cause))
        case UnitDied():
            return t("  {unit} dies", unit=name_fn(ev.unit))
        case BattleEnded():
            reason = t(REASON_TEXT[ev.reason])
            if ev.winner_id is None:
                return t("=== Battle ended: draw ({reason}) ===", reason=reason)
            return t("=== Battle ended: {winner} wins ({reason}) ===", winner=t(ev.winner_id), reason=reason)
    return repr(ev)
