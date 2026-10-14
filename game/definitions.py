"""Неизменяемые определения предметов, навыков и пассивок."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .areas import AREA_SINGLE
from .stats import Modifier, Scale, Stat
from .reactions import DO_APPLY_EFFECT, DO_COVER, LEGACY_EVENTS, ON_TARGETED, Reaction
from .tactics import SIDES, Always, ICondition, condition_from_dict, condition_to_dict
from .tiers import check_tier, rank_of

PART_DAMAGE = "damage"
PART_HEAL = "heal"
PART_KINDS = (PART_DAMAGE, PART_HEAL)

# Категория урона определяет, какая защита цели вычитается.
PHYSICAL = "physical"   # phys_def; может быть заблокирован (guard)
MAGICAL = "magical"     # mag_def
PURE = "pure"           # игнорирует защиту и блок
CATEGORIES = (PHYSICAL, MAGICAL, PURE)

APPLY_TARGET = "target"
APPLY_SELF = "self"
APPLY_RECIPIENTS = (APPLY_TARGET, APPLY_SELF)

SCOPES = ("self", "ally", "enemy", "any")



@dataclass(frozen=True)
class ItemDefinition:
    """Предмет снаряжения. Пока надет, даёт модификаторы, навыки, пассивки и теги."""

    id: str
    name: str
    slot: str                               # тип слота, в который предмет надевается
    modifiers: tuple[Modifier, ...] = ()
    skills: tuple[str, ...] = ()            # активные навыки, доступные носителю
    passives: tuple[str, ...] = ()          # пассивки носителя
    tags: tuple[str, ...] = ()              # теги, которые получает носитель
    damage_tags: tuple[str, ...] = ()       # тип урона оружия (для частей навыков с weapon_tags)
    tier: int = 5                           # тир 0..30 (game/tiers.py): 0..9 — новичок, 10..19 — наёмник, 20..30 — герой
    price: int = 0                          # цена в магазине; продаётся дешевле

    @classmethod
    def from_dict(cls, item_id: str, data: Mapping[str, Any]) -> "ItemDefinition":
        item = cls(
            id=item_id,
            name=data.get("name", item_id),
            slot=data["slot"],
            modifiers=tuple(Modifier.from_dict(m) for m in data.get("modifiers", ())),
            skills=tuple(data.get("skills", ())),
            passives=tuple(data.get("passives", ())),
            tags=tuple(data.get("tags", ())),
            damage_tags=tuple(data.get("damage_tags", ())),
            tier=check_tier(int(data.get("tier", 5)), f"item {item_id}"),
            price=int(data.get("price", 0)),
        )
        if item.price < 0:
            raise ValueError(f"item {item_id}: price must not be negative")
        return item

    @property
    def rank(self) -> int:
        """Ступень на экране: 1 — новичок, 2 — наёмник, 3 — герой."""
        return rank_of(self.tier)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "slot": self.slot,
            "tier": self.tier,
            "price": self.price,
            "modifiers": [m.to_dict() for m in self.modifiers],
            "skills": list(self.skills),
            "passives": list(self.passives),
            "tags": list(self.tags),
            "damage_tags": list(self.damage_tags),
        }


@dataclass(frozen=True)
class SkillPart:
    """Часть навыка: одна порция урона или лечения.

    Значение атаки = сумма (стат применяющего * коэффициент) по scaling.
    Урон = (значение атаки - защита цели) * power; лечение = значение * power.
    """

    kind: str = PART_DAMAGE
    category: str = PHYSICAL
    power: float = 1.0
    scaling: tuple[Scale, ...] = (Scale(Stat.PHYS_ATK),)
    tags: tuple[str, ...] = ()      # тип урона: режущий, огонь и т. д.
    weapon_tags: bool = False       # брать тип урона из надетого оружия (tags = запасной вариант)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SkillPart":
        kind = data.get("kind", PART_DAMAGE)
        if kind not in PART_KINDS:
            raise ValueError(f"unknown skill part kind {kind!r}")
        category = data.get("category", PHYSICAL)
        if category not in CATEGORIES:
            raise ValueError(f"unknown damage category {category!r}")
        default_stat = Stat.MAG_ATK if category == MAGICAL else Stat.PHYS_ATK
        scaling = tuple(Scale.from_dict(s) for s in data["scaling"]) if "scaling" in data else (Scale(default_stat),)
        return cls(kind, category, data.get("power", 1.0), scaling,
                   tuple(data.get("tags", ())), data.get("weapon_tags", False))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "category": self.category,
            "power": self.power,
            "scaling": [s.to_dict() for s in self.scaling],
            "tags": list(self.tags),
            "weapon_tags": self.weapon_tags,
        }


@dataclass(frozen=True)
class SkillApply:
    """Компонент навыка: эффект effect_id получает задетый юнит или сам применяющий.

    Условие проверяется после урона/лечения: для получателя "target" на каждом
    задетом юните, для "self" на основной цели навыка.
    """

    effect_id: str
    to: str = APPLY_TARGET
    condition: ICondition = Always()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SkillApply":
        to = data.get("to", APPLY_TARGET)
        if to not in APPLY_RECIPIENTS:
            raise ValueError(f"unknown effect recipient {to!r}")
        return cls(data["effect_id"], to, condition_from_dict(data.get("condition")))

    def to_dict(self) -> dict[str, Any]:
        return {"effect_id": self.effect_id, "to": self.to, "condition": condition_to_dict(self.condition)}


# Растущая прибавка силы (PotencyBonus.scale): доля 0..1, на которую умножается add.
SCALES = ("self_hp_missing",      # чем меньше HP у применяющего
          "self_hp",              # чем больше HP у применяющего
          "target_hp_missing",    # чем меньше HP у цели
          "target_hp",            # чем больше HP у цели
          "enemies_fallen",       # чем меньше врагов осталось (доля павших)
          "front_row")            # 1, если применяющий в переднем ряду


@dataclass(frozen=True)
class PotencyBonus:
    """Прибавка к силе навыка (как в UO: +50 к силе 100 -> add 0.5 к power каждой части урона).

    Срабатывает, если оба условия выполнены (self — на применяющего, target — на цель удара);
    scale — растущая прибавка: add умножается на долю (см. SCALES)."""

    add: float
    self_condition: ICondition = Always()
    target_condition: ICondition = Always()
    scale: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PotencyBonus":
        scale = data.get("scale", "")
        if scale and scale not in SCALES:
            raise ValueError(f"unknown potency scale {scale!r}")
        return cls(float(data["add"]), condition_from_dict(data.get("self_condition")),
                   condition_from_dict(data.get("target_condition")), scale)

    def to_dict(self) -> dict[str, Any]:
        return {"add": self.add, "self_condition": condition_to_dict(self.self_condition),
                "target_condition": condition_to_dict(self.target_condition), "scale": self.scale}


@dataclass(frozen=True)
class SkillExtras:
    """Особенности навыка в духе UO; всё по умолчанию выключено.

    unguardable / unguardable_vs — блок невозможен (всегда или против целей с одним из тегов);
    ignore_def / ignore_def_vs — доля защиты цели, которая не учитывается (всегда или против тегов);
    truestrike — не промахивается (кроме слепоты); crit_add — прибавка к шансу крита; no_crit;
    hp_cost — доля макс. HP, которую применяющий платит перед навыком (не опускается ниже 1);
    heal_on_hit — доля макс. HP применяющего за попадание; lifesteal — доля нанесённого урона;
    ap_drain / pp_drain — сколько AP/PP теряет каждый задетый; steal — забрать их себе;
    dispel — метки эффектов (buff, debuff), снимаемых с задетых;
    kill_ap / kill_pp / kill_heal / kill_effect — применяющему, если цель погибла."""

    unguardable: bool = False
    unguardable_vs: tuple[str, ...] = ()
    ignore_def: float = 0.0
    ignore_def_vs: tuple[str, ...] = ()
    truestrike: bool = False
    crit_add: int = 0
    no_crit: bool = False
    hp_cost: float = 0.0
    heal_on_hit: float = 0.0
    lifesteal: float = 0.0
    ap_drain: int = 0
    pp_drain: int = 0
    steal: bool = False
    dispel: tuple[str, ...] = ()
    kill_ap: int = 0
    kill_pp: int = 0
    kill_heal: float = 0.0
    kill_effect: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SkillExtras":
        known = cls.__dataclass_fields__
        unknown = set(data) - set(known)
        if unknown:
            raise ValueError(f"unknown skill extras {sorted(unknown)}")
        values = {k: (tuple(v) if isinstance(v, list) else v) for k, v in data.items()}
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        default = SkillExtras()
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.__dict__.items()
                if v != getattr(default, k)}


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    name: str
    ap_cost: int = 1
    pp_cost: int = 0                        # навык может стоить PP вместо AP или вместе с ним
    targets: str = "enemy"                  # кого можно выбрать целью: enemy / ally / self
    area: str = AREA_SINGLE                 # id области вокруг цели (Database.areas)
    hits: int = 1                           # число ударов; попадание, крит и блок бросаются на каждый
    accuracy: int = 100                     # шанс попадания навыка, % (может быть больше 100)
    tags: tuple[str, ...] = ()              # вид навыка: ближний, дальний, магия
    parts: tuple[SkillPart, ...] = ()       # урон и лечение; пусто = навык поддержки
    bonus_vs: tuple[tuple[str, float], ...] = ()  # (тег цели, множитель урона)
    ap_restore: int = 0                     # сколько AP получает каждый задетый юнит
    pp_restore: int = 0                     # сколько PP получает каждый задетый юнит
    applies: tuple[SkillApply, ...] = ()    # накладываемые эффекты, число не ограничено
    # Требования для применения (задел): проверяются до тактик, в интерфейсе пока не редактируются.
    requires_self: ICondition = Always()
    requires_target: ICondition = Always()
    potency: tuple[PotencyBonus, ...] = ()  # условные прибавки к силе (против дебаффнутых, при низком HP...)
    extras: SkillExtras = SkillExtras()     # неблокируемость, игнор защиты, кража AP, бонусы за добивание...

    @classmethod
    def from_dict(cls, skill_id: str, data: Mapping[str, Any]) -> "SkillDefinition":
        targets = data.get("targets", "enemy")
        if targets not in SIDES:
            raise ValueError(f"skill {skill_id}: unknown targets {targets!r}")
        area = data.get("area", AREA_SINGLE)
        hits = data.get("hits", 1)
        if hits < 1:
            raise ValueError(f"skill {skill_id}: hits must be at least 1")
        try:
            parts = tuple(SkillPart.from_dict(p) for p in data.get("parts", ()))
        except ValueError as error:
            raise ValueError(f"skill {skill_id}: {error}") from None
        return cls(
            id=skill_id,
            name=data.get("name", skill_id),
            ap_cost=data.get("ap_cost", 1),
            pp_cost=data.get("pp_cost", 0),
            targets=targets,
            area=area,
            hits=hits,
            accuracy=data.get("accuracy", 100),
            tags=tuple(data.get("tags", ())),
            parts=parts,
            bonus_vs=tuple((tag, mult) for tag, mult in data.get("bonus_vs", {}).items()),
            ap_restore=data.get("ap_restore", 0),
            pp_restore=data.get("pp_restore", 0),
            applies=tuple(SkillApply.from_dict(a) for a in data.get("applies", ())),
            requires_self=condition_from_dict(data.get("requires_self")),
            requires_target=condition_from_dict(data.get("requires_target")),
            potency=tuple(PotencyBonus.from_dict(b) for b in data.get("potency", ())),
            extras=SkillExtras.from_dict(data.get("extras", {})),
        )

    def affordable(self, unit: Any) -> bool:
        """Хватает ли юниту AP и PP на навык."""
        return unit.ap.can_spend(self.ap_cost) and unit.pp.can_spend(self.pp_cost)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ap_cost": self.ap_cost,
            "pp_cost": self.pp_cost,
            "targets": self.targets,
            "area": self.area,
            "hits": self.hits,
            "accuracy": self.accuracy,
            "tags": list(self.tags),
            "parts": [p.to_dict() for p in self.parts],
            "bonus_vs": dict(self.bonus_vs),
            "ap_restore": self.ap_restore,
            "pp_restore": self.pp_restore,
            "applies": [a.to_dict() for a in self.applies],
            "requires_self": condition_to_dict(self.requires_self),
            "requires_target": condition_to_dict(self.requires_target),
            "potency": [b.to_dict() for b in self.potency],
            "extras": self.extras.to_dict(),
        }


@dataclass(frozen=True)
class PassiveDefinition:
    """Пассивка: реакция владельца на событие боя, которая стоит PP.

    Что именно происходит, описывает reaction (см. game.reactions): например,
    «союзника выбрали целью -> принять удар на себя» или «по мне попали ->
    применить навык контратаки к атаковавшему».
    """

    id: str
    name: str
    pp_cost: int
    reaction: Reaction

    @classmethod
    def from_dict(cls, passive_id: str, data: Mapping[str, Any]) -> "PassiveDefinition":
        try:
            reaction = Reaction.from_dict(data["reaction"] if "reaction" in data else _legacy_passive(data))
        except (ValueError, KeyError) as error:
            raise ValueError(f"passive {passive_id}: {error}") from None
        return cls(passive_id, data.get("name", passive_id), data.get("pp_cost", 0), reaction)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "pp_cost": self.pp_cost, "reaction": self.reaction.to_dict()}


def _legacy_passive(data: Mapping[str, Any]) -> dict[str, Any]:
    """Пассивка старого формата: эффект на событие (trigger, scope) или прикрытие (cover_*)."""
    if data.get("action") == "cover":
        return {
            "event": ON_TARGETED, "whose": "ally", "action": DO_COVER, "to": "owner",
            "area": data.get("cover_area", "row"), "cover_many": data.get("cover_many", False),
            "attack_tags": data.get("cover_tags", ()), "skill_areas": data.get("cover_skill_areas", ()),
            "effect_id": data.get("effect_id"),
        }
    event, outcome = LEGACY_EVENTS.get(data["trigger"], (None, None))
    if event is None:
        raise ValueError(f"unknown event {data['trigger']!r}")
    return {"event": event, "outcome": outcome, "whose": data.get("scope", "any"), "action": DO_APPLY_EFFECT,
            "effect_id": data["effect_id"], "to": "owner"}
