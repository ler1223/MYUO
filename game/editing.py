"""Операции редакторов без графики: правка тактик и конструктор навыков.

Всё собирается только из уже зарегистрированных компонентов: условий
(CONDITIONS), селекторов (SELECTORS), областей (AREAS), эффектов и навыков
из Database.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

from .areas import AREA_SINGLE, AREAS
from .database import Database
from .definitions import (
    APPLY_SELF,
    APPLY_TARGET,
    DEFAULT_TARGETS,
    SKILL_DAMAGE,
    SKILL_KINDS,
    SKILL_SUPPORT,
    SkillBinding,
    SkillDefinition,
)
from .tactics import CONDITIONS, SIDES, TacticsSet
from .unit import Unit

FRACTIONS = tuple(round(0.1 * i, 1) for i in range(1, 11))
DEFAULT_FRACTION = 0.5
POWER_STEP = 0.1
POWER_MAX = 5.0
AP_COST_MAX = 6
RESTORE_MAX = 6
BUFF_TAG = "buff"


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
    raise ValueError(f"unknown condition parameter kind {kind!r}")


def default_condition(name: str, db: Database) -> dict[str, Any]:
    """Условие в формате JSON с параметрами по умолчанию."""
    data: dict[str, Any] = {"type": name}
    for param, kind in condition_params(name).items():
        data[param] = DEFAULT_FRACTION if kind == "fraction" else param_options(kind, db)[0]
    return data


def _same(text: str, **params: Any) -> str:
    return text


def describe_condition(data: Mapping[str, Any], t: Optional[Callable[..., str]] = None) -> str:
    """Текст условия; t переводит названия (тип условия, эффект, флаг)."""
    t = t or _same
    params = " ".join(t(v) if isinstance(v, str) else str(v) for k, v in data.items() if k != "type")
    return f"{t(data['type'])} {params}".strip()


def cycle(options: Sequence[Any], current: Any, delta: int) -> Any:
    """Следующее/предыдущее значение по кругу."""
    if current not in options:
        return options[0]
    return options[(list(options).index(current) + delta) % len(options)]


# --- тактики ---------------------------------------------------------------

def default_rule(db: Database, unit: Unit) -> dict[str, Any]:
    return {
        "skill": db.skills_for(unit)[0],
        "self_condition": {"type": "always"},
        "condition": {"type": "always"},
        "selector": "frontmost",
    }


def set_tactics(db: Database, unit: Unit, rules: Sequence[Mapping[str, Any]]) -> None:
    """Заменяет тактики юнита правилами в формате JSON, проверяя доступность навыков."""
    allowed = db.skills_for(unit)
    for rule in rules:
        if rule["skill"] not in allowed:
            raise ValueError(f"{unit.label} cannot use skill {rule['skill']!r}")
    unit.set_tactics(TacticsSet.from_list(rules))


def skill_users(skill_id: str, units: Iterable[Unit]) -> list[Unit]:
    """Юниты, в тактиках которых используется навык."""
    return [u for u in units if any(rule.skill_id == skill_id for rule in u.tactics.rules)]


# --- конструктор навыков ---------------------------------------------------

def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def default_apply(db: Database, effect_id: str) -> dict[str, Any]:
    """Положительный эффект по умолчанию идёт на себя, остальные на цель."""
    to = APPLY_SELF if BUFF_TAG in db.effects[effect_id].tags else APPLY_TARGET
    return {"effect_id": effect_id, "to": to, "condition": {"type": "always"}}


@dataclass
class SkillDraft:
    """Черновик навыка. applies хранится в формате JSON и не ограничен по длине.

    bind_units и bind_items задают, кому навык будет доступен: типам юнитов
    и носителям предметов.
    """

    name: str = "New Skill"
    kind: str = SKILL_DAMAGE
    power: float = 1.0
    ap_cost: int = 1
    targets: str = DEFAULT_TARGETS[SKILL_DAMAGE]
    area: str = AREA_SINGLE
    ap_restore: int = 0
    pp_restore: int = 0
    applies: list[dict[str, Any]] = field(default_factory=list)
    bind_units: list[str] = field(default_factory=list)
    bind_items: list[str] = field(default_factory=list)

    @property
    def skill_id(self) -> str:
        return slugify(self.name)

    @classmethod
    def from_skill(cls, skill: SkillDefinition, name: Optional[str] = None,
                   binding: Optional[SkillBinding] = None) -> "SkillDraft":
        data = skill.to_dict()
        binding = binding or SkillBinding()
        return cls(
            name=name or skill.name, kind=skill.kind, power=skill.power, ap_cost=skill.ap_cost,
            targets=skill.targets, area=skill.area, ap_restore=skill.ap_restore, pp_restore=skill.pp_restore,
            applies=data["applies"], bind_units=list(binding.units), bind_items=list(binding.items),
        )

    def set_kind(self, kind: str) -> None:
        """Смена типа подставляет привычную для него сторону цели."""
        self.kind = kind
        self.targets = DEFAULT_TARGETS[kind]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name.strip(),
            "kind": self.kind,
            "power": round(self.power, 2),
            "ap_cost": self.ap_cost,
            "targets": self.targets,
            "area": self.area,
            "ap_restore": self.ap_restore,
            "pp_restore": self.pp_restore,
            "applies": [dict(a, condition=dict(a["condition"])) for a in self.applies],
        }

    def build(self, db: Database) -> SkillDefinition:
        """Проверяет черновик и собирает определение навыка (в базу не добавляет)."""
        if not self.skill_id:
            raise ValueError("skill name must contain letters or digits")
        if self.kind not in SKILL_KINDS:
            raise ValueError(f"unknown skill kind {self.kind!r}")
        if self.targets not in SIDES:
            raise ValueError(f"unknown targets {self.targets!r}")
        if self.area not in AREAS:
            raise ValueError(f"unknown area {self.area!r}")
        if not 0 <= self.power <= POWER_MAX:
            raise ValueError(f"power must be between 0 and {POWER_MAX}")
        if not 0 <= self.ap_cost <= AP_COST_MAX:
            raise ValueError(f"AP cost must be between 0 and {AP_COST_MAX}")
        if not (0 <= self.ap_restore <= RESTORE_MAX and 0 <= self.pp_restore <= RESTORE_MAX):
            raise ValueError(f"AP and PP restore must be between 0 and {RESTORE_MAX}")
        if self.kind == SKILL_SUPPORT and not (self.applies or self.ap_restore or self.pp_restore):
            raise ValueError("a support skill needs an effect or AP/PP restore")
        for apply in self.applies:
            if apply["effect_id"] not in db.effects:
                raise ValueError(f"unknown effect {apply['effect_id']!r}")
        return SkillDefinition.from_dict(self.skill_id, self.to_dict())

    def save_to(self, db: Database) -> SkillDefinition:
        """Собирает навык и регистрирует его в базе вместе с привязкой."""
        skill = self.build(db)
        db.add_custom_skill(skill, self.bind_units, self.bind_items)
        return skill


def describe_skill(skill: SkillDefinition, db: Database, t: Optional[Callable[..., str]] = None) -> str:
    """Короткое описание навыка для интерфейса; t переводит названия."""
    t = t or _same
    action = t(skill.kind) if skill.kind == SKILL_SUPPORT else f"{t(skill.kind)} x{skill.power:g}"
    aim = t(skill.targets) if skill.area == AREA_SINGLE else f"{t(skill.targets)}, {t(skill.area)}"
    parts = [f"AP {skill.ap_cost}", f"{action} -> {aim}"]
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
