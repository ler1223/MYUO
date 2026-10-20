"""Условия тактики Unicorn Overlord (UcFactorList.fms) с контекстом боя.

В игре у каждой строки тактики до двух условий, и выполнены должны быть оба. Условия бывают трёх видов
(docs/uo/ABILITIES_DESIGN.md, раздел 1.2):

- ``prioritize``     — порядок целей: ``rank(ctx, unit)`` (меньше — раньше);
- ``target_only``    — фильтр целей: ``accepts(ctx, unit)``; подходящих нет — навык не срабатывает;
- ``activates_only`` — условие на обстановку, себя или атаку: ``gate(ctx)``.

Ключи (``key``) стабильны и записываются в данные тактик; их список сверяется с ``docs/uo/catalog/factors.json``
(тест ``tests/test_conditions.py``). Свои условия проекта (``has_effect`` и т. п. из ``game/tactics.py``) работают
рядом через ``LegacyCondition`` и пишутся в данные словарём ``{"type": ..., "on": "self" | "target"}``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional, Sequence

from .stats import Stat
from .tactics import CONDITIONS as LEGACY_CONDITIONS
from .tactics import SELECTORS as LEGACY_SELECTORS
from .tactics import Always, condition_from_dict, condition_to_dict

if TYPE_CHECKING:
    from .unit import Unit

PRIORITIZE, TARGET_ONLY, ACTIVATES_ONLY = "prioritize", "target_only", "activates_only"


@dataclass
class Context:
    """Что видят условия. ``battle`` — game.combat.Battle (стороны, время суток); ``owner`` — чья тактика;
    ``moment`` — событие для пассивок (атаковавший, теги и область атаки); ``candidates`` — круг целей навыка
    (для «среднего HP целей»); ``action_index`` — какое по счёту действие владельца в бою (с 1)."""

    battle: Any
    owner: "Unit"
    moment: Any = None
    candidates: Sequence["Unit"] = ()
    action_index: int = 1


class Condition:
    """Общий вид условия: по умолчанию ничего не ограничивает."""

    key = "none"
    kind = ACTIVATES_ONLY
    group = "none"

    def gate(self, ctx: Context) -> bool:
        return True

    def accepts(self, ctx: Context, unit: "Unit") -> bool:
        return True

    def rank(self, ctx: Context, unit: "Unit") -> float:
        return 0.0

    def to_data(self) -> Any:
        return self.key


@dataclass(frozen=True)
class Factor(Condition):
    """Условие игры: одна функция нужного вида."""

    id: int = 0
    key: str = "none"
    kind: str = ACTIVATES_ONLY
    group: str = "none"
    name: str = ""
    fn: Optional[Callable] = field(default=None, compare=False, repr=False)

    def gate(self, ctx: Context) -> bool:
        return True if self.kind != ACTIVATES_ONLY or self.fn is None else bool(self.fn(ctx))

    def accepts(self, ctx: Context, unit: "Unit") -> bool:
        return True if self.kind != TARGET_ONLY or self.fn is None else bool(self.fn(ctx, unit))

    def rank(self, ctx: Context, unit: "Unit") -> float:
        return 0.0 if self.kind != PRIORITIZE or self.fn is None else float(self.fn(ctx, unit))


@dataclass(frozen=True)
class LegacyCondition(Condition):
    """Свои условия проекта (game/tactics.py ICondition), проверяются на владельце или на цели."""

    inner: Any = None
    on: str = "target"
    group: str = "custom"

    @property
    def key(self) -> str:  # type: ignore[override]
        return "custom:" + str(condition_to_dict(self.inner)["type"])

    @property
    def kind(self) -> str:  # type: ignore[override]
        return TARGET_ONLY if self.on == "target" else ACTIVATES_ONLY

    def gate(self, ctx: Context) -> bool:
        return self.on == "target" or self.inner.check(ctx.owner, ctx.owner)

    def accepts(self, ctx: Context, unit: "Unit") -> bool:
        return self.on != "target" or self.inner.check(ctx.owner, unit)

    def to_data(self) -> Any:
        return {**condition_to_dict(self.inner), "on": self.on}


@dataclass(frozen=True)
class LegacySelector(Condition):
    """Старый выбор цели (strongest, backmost, random) как условие-приоритет. Если он единственный приоритет правила,
    выбор идёт его собственным ``select`` — порядок бросков случайности и результат остаются прежними."""

    name: str = "frontmost"
    kind: str = PRIORITIZE
    group: str = "custom"

    @property
    def key(self) -> str:  # type: ignore[override]
        return "custom:" + self.name

    def select(self, owner: "Unit", ordered: Sequence["Unit"], rng) -> "Unit":
        return LEGACY_SELECTORS[self.name]().select(owner, ordered, rng)

    def rank(self, ctx: Context, unit: "Unit") -> float:
        if self.name == "strongest":
            return -max(unit.stat(Stat.PHYS_ATK), unit.stat(Stat.MAG_ATK))
        if self.name == "random":
            return ctx.battle.rng.random()
        return 0.0

    def to_data(self) -> Any:
        return {"type": "selector", "name": self.name}


# --- помощники ---------------------------------------------------------------------------------------------

TYPES = (("infantry", "infantry"), ("cavalry", "cavalry"), ("flying", "flying"), ("armored", "armored"),
         ("scout", "scout"), ("archer", "archer"), ("caster", "caster"), ("elven", "elf"), ("bestral", "bestral"),
         ("angel", "angel"))
STATUS_TAGS = (("poisoned", "poison"), ("burning", "burn"), ("frozen", "freeze"), ("stunned", "stun"),
               ("blinded", "blind"), ("passive_sealed", "passive_seal"), ("guard_sealed", "guard_seal"))
STATS = (("max_hp", Stat.HP), ("max_ap", None), ("max_pp", None), ("phys_atk", Stat.PHYS_ATK), ("mag_atk", Stat.MAG_ATK),
         ("phys_def", Stat.PHYS_DEF), ("mag_def", Stat.MAG_DEF), ("initiative", Stat.INITIATIVE),
         ("accuracy", Stat.ACCURACY), ("evasion", Stat.EVASION), ("critical_rate", Stat.CRIT_RATE),
         ("guard_rate", Stat.GUARD_RATE))


def has_label(unit: "Unit", label: str) -> bool:
    return any(label in e.definition.tags for e in unit.effects)


def hp_share(unit: "Unit") -> float:
    return unit.hp / max(1, unit.max_hp)


def hp_cmp(unit: "Unit", percent: int, op: str) -> bool:
    """«lt N%» — HP не выше N% максимума («25% or less»), «gt N%» — не ниже («25% or more»);
    lt 100 — строго меньше максимума, gt 100 — полное HP."""
    value = unit.hp * 100
    if op == "lt":
        return value < unit.max_hp * 100 if percent == 100 else value <= unit.max_hp * percent
    return value >= unit.max_hp * percent


def side_of(ctx: Context, unit: "Unit"):
    return ctx.battle.side_of(unit)


def row_of(ctx: Context, unit: "Unit") -> int:
    return side_of(ctx, unit).pos(unit)[0]


def row_count(ctx: Context, unit: "Unit") -> int:
    side = side_of(ctx, unit)
    return sum(1 for u in side.alive() if side.pos(u)[0] == side.pos(unit)[0])


def column_full(ctx: Context, unit: "Unit") -> bool:
    side = side_of(ctx, unit)
    col = side.pos(unit)[1]
    return len({side.pos(u)[0] for u in side.alive() if side.pos(u)[1] == col}) >= 2


def enemies(ctx: Context) -> list:
    return ctx.battle.other(ctx.battle.side_of(ctx.owner)).alive()


def allies(ctx: Context) -> list:
    return ctx.battle.side_of(ctx.owner).alive()


def moment_tags(ctx: Context) -> frozenset:
    return frozenset(getattr(ctx.moment, "attack_tags", ()) or ())


def attacker_has(ctx: Context, tag: str) -> bool:
    actor = getattr(ctx.moment, "actor", None)
    return actor is not None and tag in actor.tags


def attack_area(ctx: Context) -> str:
    skill = getattr(ctx.moment, "skill", None)
    return skill.area if skill is not None else ""


def stat_value(unit: "Unit", name: str, stat: Optional[Stat]) -> int:
    if name == "max_ap":
        return unit.ap.max
    if name == "max_pp":
        return unit.pp.max
    return unit.stat(stat)


def build() -> dict[str, Factor]:
    """Все условия игры по номерам UcFactorList (203 записи; 0 и 202 — служебные)."""
    out: dict[str, Factor] = {}

    def add(fid: int, key: str, kind: str, group: str, fn: Optional[Callable]) -> None:
        out[key] = Factor(fid, key, kind, group, key.replace("_", " "), fn)

    add(0, "none", ACTIVATES_ONLY, "none", None)
    add(1, "prioritize_front_row", PRIORITIZE, "formation", lambda c, u: row_of(c, u))
    add(2, "prioritize_back_row", PRIORITIZE, "formation", lambda c, u: -row_of(c, u))
    add(3, "front_row", TARGET_ONLY, "formation", lambda c, u: row_of(c, u) == 0)
    add(4, "back_row", TARGET_ONLY, "formation", lambda c, u: row_of(c, u) > 0)
    add(5, "full_column", TARGET_ONLY, "formation", column_full)
    add(6, "row_with_most_combatants", PRIORITIZE, "formation", lambda c, u: -row_count(c, u))
    add(7, "row_with_least_combatants", PRIORITIZE, "formation", lambda c, u: row_count(c, u))
    add(8, "row_with_2_plus_combatants", TARGET_ONLY, "formation", lambda c, u: row_count(c, u) >= 2)
    add(9, "row_with_3_plus_combatants", TARGET_ONLY, "formation", lambda c, u: row_count(c, u) >= 3)
    add(10, "daytime", ACTIVATES_ONLY, "formation", lambda c: c.battle.time_of_day == "day")
    add(11, "nighttime", ACTIVATES_ONLY, "formation", lambda c: c.battle.time_of_day == "night")
    add(12, "highest_hp", PRIORITIZE, "hp", lambda c, u: -u.hp)
    add(13, "lowest_hp", PRIORITIZE, "hp", lambda c, u: u.hp)
    add(14, "highest_pct_hp", PRIORITIZE, "hp", lambda c, u: -hp_share(u))
    add(15, "lowest_pct_hp", PRIORITIZE, "hp", lambda c, u: hp_share(u))
    thresholds = ((25, "lt"), (50, "lt"), (75, "lt"), (25, "gt"), (50, "gt"), (75, "gt"), (100, "gt"), (100, "lt"))
    for i, (percent, op) in enumerate(thresholds):
        add(16 + i, f"target_hp_is_{op}_{percent}_pct", TARGET_ONLY, "hp",
            lambda c, u, p=percent, o=op: hp_cmp(u, p, o))
        add(24 + i, f"average_hp_is_{op}_{percent}_pct", ACTIVATES_ONLY, "hp",
            lambda c, p=percent, o=op: bool(c.candidates) and (
                (sum(hp_share(u) for u in c.candidates) / len(c.candidates) * 100 < 100) if (p, o) == (100, "lt")
                else (sum(hp_share(u) for u in c.candidates) / len(c.candidates) * 100 <= p) if o == "lt"
                else (sum(hp_share(u) for u in c.candidates) / len(c.candidates) * 100 >= p)))
    add(32, "prioritize_buffed", PRIORITIZE, "status", lambda c, u: 0 if has_label(u, "buff") else 1)
    add(33, "prioritize_debuffed", PRIORITIZE, "status", lambda c, u: 0 if has_label(u, "debuff") else 1)
    add(34, "buffed", TARGET_ONLY, "status", lambda c, u: has_label(u, "buff"))
    add(35, "debuffed", TARGET_ONLY, "status", lambda c, u: has_label(u, "debuff"))
    add(36, "afflicted", TARGET_ONLY, "status", lambda c, u: has_label(u, "ailment"))
    for i, (name, tag) in enumerate(STATUS_TAGS):
        add(37 + i, name, TARGET_ONLY, "status", lambda c, u, t=tag: has_label(u, t))
    add(44, "not_buffed", TARGET_ONLY, "status", lambda c, u: not has_label(u, "buff"))
    add(45, "not_debuffed", TARGET_ONLY, "status", lambda c, u: not has_label(u, "debuff"))
    add(46, "not_afflicted", TARGET_ONLY, "status", lambda c, u: not has_label(u, "ailment"))
    for i, (name, tag) in enumerate(STATUS_TAGS):
        add(47 + i, "not_" + name, TARGET_ONLY, "status", lambda c, u, t=tag: not has_label(u, t))
    for i, (name, tag) in enumerate(TYPES):
        add(54 + i, "prioritize_" + name, PRIORITIZE, "combatant_type", lambda c, u, t=tag: 0 if t in u.tags else 1)
        add(64 + i, name, TARGET_ONLY, "combatant_type", lambda c, u, t=tag: t in u.tags)
    add(74, "physickally_attacked", ACTIVATES_ONLY, "attack_type", lambda c: "physical" in moment_tags(c))
    add(75, "magickally_attacked", ACTIVATES_ONLY, "attack_type", lambda c: "magical" in moment_tags(c))
    add(76, "row_is_attacked", ACTIVATES_ONLY, "attack_type", lambda c: attack_area(c) == "row")
    add(77, "column_is_attacked", ACTIVATES_ONLY, "attack_type", lambda c: attack_area(c) in ("column", "pierce"))
    add(78, "all_allies_are_attacked", ACTIVATES_ONLY, "attack_type", lambda c: attack_area(c) == "all")
    for i, (name, tag) in enumerate(TYPES):
        add(79 + i, "attacked_by_" + name, ACTIVATES_ONLY, "attack_type", lambda c, t=tag: attacker_has(c, t))
    for i, n in enumerate((2, 3, 4, 5)):
        add(89 + i, f"{n}_or_more_enemies", ACTIVATES_ONLY, "unit_size", lambda c, n=n: len(enemies(c)) >= n)
        add(97 + i, f"{n}_or_more_allies", ACTIVATES_ONLY, "unit_size", lambda c, n=n: len(allies(c)) >= n)
    for i, n in enumerate((1, 2, 3, 4)):
        add(93 + i, f"{n}_or_fewer_enemies", ACTIVATES_ONLY, "unit_size", lambda c, n=n: len(enemies(c)) <= n)
        add(101 + i, f"{n}_or_fewer_allies", ACTIVATES_ONLY, "unit_size", lambda c, n=n: len(allies(c)) <= n)
    for i, (percent, op) in enumerate(thresholds):
        add(105 + i, f"own_hp_is_{op}_{percent}_pct", ACTIVATES_ONLY, "own_hp",
            lambda c, p=percent, o=op: hp_cmp(c.owner, p, o))
    # AP и PP: 113.. цели (приоритет, затем пороги), 133.. сам боец
    for base, res, name in ((113, "ap", "ap"), (123, "pp", "pp")):
        add(base, f"most_{name}", PRIORITIZE, "ap_pp", lambda c, u, r=res: -getattr(u, r).current)
        add(base + 1, f"least_{name}", PRIORITIZE, "ap_pp", lambda c, u, r=res: getattr(u, r).current)
        add(base + 2, f"0_{name}", TARGET_ONLY, "ap_pp", lambda c, u, r=res: getattr(u, r).current == 0)
        for i, n in enumerate((1, 2, 3)):
            add(base + 3 + i, f"{n}_or_less_{name}", TARGET_ONLY, "ap_pp",
                lambda c, u, r=res, n=n: getattr(u, r).current <= n)
        for i, n in enumerate((1, 2, 3, 4)):
            add(base + 6 + i, f"{n}_or_more_{name}", TARGET_ONLY, "ap_pp",
                lambda c, u, r=res, n=n: getattr(u, r).current >= n)
    for base, res, name in ((133, "ap", "ap"), (141, "pp", "pp")):
        add(base, f"own_{name}_is_0", ACTIVATES_ONLY, "own_ap_pp", lambda c, r=res: getattr(c.owner, r).current == 0)
        for i, n in enumerate((1, 2, 3)):
            add(base + 1 + i, f"own_{name}_is_{n}_or_less", ACTIVATES_ONLY, "own_ap_pp",
                lambda c, r=res, n=n: getattr(c.owner, r).current <= n)
        for i, n in enumerate((1, 2, 3, 4)):
            add(base + 4 + i, f"own_{name}_is_{n}_or_more", ACTIVATES_ONLY, "own_ap_pp",
                lambda c, r=res, n=n: getattr(c.owner, r).current >= n)
    add(149, "user", TARGET_ONLY, "own_condition", lambda c, u: u is c.owner)
    add(150, "other_combatants", TARGET_ONLY, "own_condition", lambda c, u: u is not c.owner)
    add(151, "user_is_buffed", ACTIVATES_ONLY, "own_condition", lambda c: has_label(c.owner, "buff"))
    add(152, "user_is_debuffed", ACTIVATES_ONLY, "own_condition", lambda c: has_label(c.owner, "debuff"))
    for i, name in enumerate(("first", "second", "third", "fourth", "fifth")):
        add(153 + i, f"{name}_action", ACTIVATES_ONLY, "own_condition", lambda c, n=i + 1: c.action_index == n)
    for i, (name, tag) in enumerate(TYPES):
        add(158 + i, f"{name}_enemies_present", ACTIVATES_ONLY, "enemies_present",
            lambda c, t=tag: any(t in u.tags for u in enemies(c)))
        add(168 + i, f"no_{name}_enemies", ACTIVATES_ONLY, "enemies_present",
            lambda c, t=tag: not any(t in u.tags for u in enemies(c)))
    for i, (name, stat) in enumerate(STATS):
        add(178 + i, f"highest_{name}", PRIORITIZE, "high_stats", lambda c, u, n=name, s=stat: -stat_value(u, n, s))
        add(190 + i, f"lowest_{name}", PRIORITIZE, "low_stats", lambda c, u, n=name, s=stat: stat_value(u, n, s))
    add(202, "story_only", ACTIVATES_ONLY, "none", lambda c: False)
    return out


FACTORS: dict[str, Factor] = build()
BY_ID: dict[int, Factor] = {f.id: f for f in FACTORS.values()}
GROUPS = tuple(dict.fromkeys(f.group for f in FACTORS.values() if f.group != "none"))
# Русские ключи для редактора живут в data/lang/ru.json: «cond:<ключ>» и «cond_group:<группа>».


def condition_from_data(data: Any) -> Condition:
    """Строка-ключ игры или словарь своего условия ({"type": ..., "on": "self" | "target"})."""
    if isinstance(data, Condition):
        return data
    if isinstance(data, str):
        if data not in FACTORS:
            raise ValueError(f"unknown tactic condition {data!r}")
        return FACTORS[data]
    if isinstance(data, Mapping) and data.get("type") == "selector":
        if data.get("name") not in LEGACY_SELECTORS:
            raise ValueError(f"unknown selector {data.get('name')!r}")
        return LegacySelector(data["name"])
    if isinstance(data, Mapping):
        params = dict(data)
        on = params.pop("on", "target")
        if on not in ("self", "target"):
            raise ValueError(f"condition 'on' must be self or target, got {on!r}")
        if params.get("type") not in LEGACY_CONDITIONS:
            raise ValueError(f"unknown condition type {params.get('type')!r}")
        return LegacyCondition(condition_from_dict(params), on)
    raise ValueError(f"bad tactic condition {data!r}")


def check_conditions(conditions: Sequence[Condition]) -> None:
    """Не больше двух условий, и две из одной группы игры не выбираются."""
    if len(conditions) > 2:
        raise ValueError("a tactic has at most two conditions")
    groups = [c.group for c in conditions if c.group not in ("none", "custom")]
    if len(groups) != len(set(groups)):
        raise ValueError("two conditions of one group cannot be combined")


def plain_conditions(conditions: Sequence[Condition]) -> bool:
    """Нет ни одного условия, меняющего порядок или круг целей и обстановку."""
    return not any(isinstance(c, Factor) and c.key != "none" or isinstance(c, LegacyCondition) for c in conditions)


# --- старый вид правила ({"condition", "self_condition", "selector"}) <-> условия ---------------------------------

SELECTOR_FACTORS = {"weakest": "lowest_pct_hp"}        # то же правило в терминах игры


def conditions_from_legacy(data: Mapping[str, Any]) -> tuple[Condition, ...]:
    """Старое правило тактики -> условия: на цель, на себя, затем порядок целей. «Всегда» и «передний» опускаются."""
    out: list[Condition] = []
    for key, on in (("self_condition", "self"), ("condition", "target")):
        raw = data.get(key)
        if raw and raw.get("type", "always") != "always":
            out.append(LegacyCondition(condition_from_dict(raw), on))
    name = data.get("selector", "frontmost")
    if name not in LEGACY_SELECTORS:
        raise KeyError(name)
    if name in SELECTOR_FACTORS:
        out.append(FACTORS[SELECTOR_FACTORS[name]])
    elif name != "frontmost":
        out.append(LegacySelector(name))
    return tuple(out)


def conditions_to_legacy(conditions: Sequence[Condition]) -> Optional[dict[str, Any]]:
    """Условия -> старый вид, если он их выражает точно (по одному условию на цель, на себя и порядку); иначе None."""
    target = own = None
    selector = "frontmost"
    inverse = {v: k for k, v in SELECTOR_FACTORS.items()}
    for cond in conditions:
        if isinstance(cond, LegacyCondition) and cond.on == "target" and target is None:
            target = cond.inner
        elif isinstance(cond, LegacyCondition) and cond.on == "self" and own is None:
            own = cond.inner
        elif isinstance(cond, LegacySelector) and selector == "frontmost":
            selector = cond.name
        elif isinstance(cond, Factor) and cond.key in inverse and selector == "frontmost":
            selector = inverse[cond.key]
        else:
            return None
    return {"self_condition": condition_to_dict(own or Always()), "condition": condition_to_dict(target or Always()),
            "selector": selector}


def choose_target(conditions: Sequence[Condition], ctx: Context, pool: Sequence["Unit"], pick_default, pick_ordered):
    """Цель по условиям строки тактики или None («навык не срабатывает»).

    ``pool`` — круг целей навыка (уже с requires_target). Порядок: фильтры ``target_only`` -> круг кандидатов
    (его видят условия обстановки, например «средний HP целей») -> ``activates_only`` -> порядок.
    ``pick_default(cands)`` — выбор по умолчанию (как у навыков без условий); ``pick_ordered(cands)`` — кандидаты
    в порядке «передний ряд первым» для условий-приоритетов."""
    cands = [u for u in pool if all(c.accepts(ctx, u) for c in conditions)]
    if not cands:
        return None
    ctx.candidates = cands
    if not all(c.gate(ctx) for c in conditions):
        return None
    ranks = [c for c in conditions if c.kind == PRIORITIZE]
    if not ranks:
        return pick_default(cands)
    ordered = pick_ordered(cands)
    if len(ranks) == 1 and isinstance(ranks[0], LegacySelector):
        return ranks[0].select(ctx.owner, ordered, ctx.battle.rng)
    return min(ordered, key=lambda u: tuple(c.rank(ctx, u) for c in ranks))
