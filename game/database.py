"""Справочник всех определений, загружаемый из одного JSON."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

from . import events
from .definitions import ItemDefinition, PassiveDefinition, SkillBinding, SkillDefinition
from .effects import EffectDefinition
from .unit import Unit, UnitDefinition, UnitState

DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "game_data.json"


class Database:
    def __init__(
        self,
        effects: Mapping[str, EffectDefinition],
        items: Mapping[str, ItemDefinition],
        skills: Mapping[str, SkillDefinition],
        passives: Mapping[str, PassiveDefinition],
        units: Mapping[str, UnitDefinition],
    ):
        self.effects = dict(effects)
        self.items = dict(items)
        self.skills = dict(skills)
        self.passives = dict(passives)
        self.units = dict(units)
        # Навыки из конструктора: id -> кому доступен. Порядок вставки сохраняется.
        self.skill_bindings: dict[str, SkillBinding] = {}
        self._validate()

    @classmethod
    def load(cls, path: Union[str, Path, None] = None) -> "Database":
        with open(path or DEFAULT_DATA_PATH, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Database":
        return cls(
            effects={k: EffectDefinition.from_dict(k, v) for k, v in data.get("effects", {}).items()},
            items={k: ItemDefinition.from_dict(k, v) for k, v in data.get("items", {}).items()},
            skills={k: SkillDefinition.from_dict(k, v) for k, v in data.get("skills", {}).items()},
            passives={k: PassiveDefinition.from_dict(k, v) for k, v in data.get("passives", {}).items()},
            units={k: UnitDefinition.from_dict(k, v) for k, v in data.get("units", {}).items()},
        )

    def _validate(self) -> None:
        """Проверяет ссылки между определениями, чтобы опечатка в JSON падала при загрузке."""
        def require(known: Mapping[str, Any], ref: Optional[str], where: str) -> None:
            if ref is not None and ref not in known:
                raise ValueError(f"{where}: unknown id {ref!r}")

        for skill in self.skills.values():
            for apply in skill.applies:
                require(self.effects, apply.effect_id, f"skill {skill.id}")
        for passive in self.passives.values():
            require(self.effects, passive.effect_id, f"passive {passive.id}")
            if not hasattr(events, passive.trigger):
                raise ValueError(f"passive {passive.id}: unknown event {passive.trigger!r}")
        for item in self.items.values():
            for skill_id in item.skills:
                require(self.skills, skill_id, f"item {item.id}")
            for passive_id in item.passives:
                require(self.passives, passive_id, f"item {item.id}")
        for unit in self.units.values():
            for skill_id in unit.skills:
                require(self.skills, skill_id, f"unit {unit.id}")
            for passive_id in unit.passives:
                require(self.passives, passive_id, f"unit {unit.id}")
            for rule in unit.tactics.rules:
                if rule.skill_id not in unit.skills:
                    raise ValueError(f"unit {unit.id}: tactic uses skill {rule.skill_id!r} the unit does not have")

    # --- навыки из конструктора ---

    @property
    def custom_skill_ids(self) -> list[str]:
        return list(self.skill_bindings)

    def skills_for(self, unit: Unit) -> tuple[str, ...]:
        """Навыки, доступные юниту: класса, надетых предметов и привязанные из конструктора."""
        own = unit.skill_ids
        worn = {item.id for item in unit.equipped}
        bound = tuple(
            skill_id
            for skill_id, binding in self.skill_bindings.items()
            if skill_id not in own and (unit.definition.id in binding.units or worn.intersection(binding.items))
        )
        return own + bound

    def add_custom_skill(self, skill: SkillDefinition, units: Sequence[str] = (), items: Sequence[str] = ()) -> None:
        """Добавляет или заменяет навык из конструктора и его привязку.

        Встроенные навыки заменить нельзя.
        """
        if not skill.id:
            raise ValueError("skill id is empty")
        if skill.id in self.skills and skill.id not in self.skill_bindings:
            raise ValueError(f"{skill.id!r} is a built-in skill")
        for apply in skill.applies:
            if apply.effect_id not in self.effects:
                raise ValueError(f"skill {skill.id}: unknown effect {apply.effect_id!r}")
        for unit_id in units:
            if unit_id not in self.units:
                raise ValueError(f"skill {skill.id}: unknown unit type {unit_id!r}")
        for item_id in items:
            if item_id not in self.items:
                raise ValueError(f"skill {skill.id}: unknown item {item_id!r}")
        self.skills[skill.id] = skill
        self.skill_bindings[skill.id] = SkillBinding(tuple(units), tuple(items))

    def remove_custom_skill(self, skill_id: str) -> None:
        if skill_id not in self.skill_bindings:
            raise ValueError(f"{skill_id!r} is not a custom skill")
        del self.skill_bindings[skill_id]
        del self.skills[skill_id]

    def save_custom_skills(self) -> dict[str, Any]:
        return {
            skill_id: dict(self.skills[skill_id].to_dict(), bind_units=list(binding.units), bind_items=list(binding.items))
            for skill_id, binding in self.skill_bindings.items()
        }

    def load_custom_skills(self, data: Mapping[str, Any]) -> None:
        for skill_id, saved in data.items():
            saved = dict(saved)
            # Старые сохранения без привязки: навык был доступен всем типам юнитов.
            legacy = "bind_units" not in saved and "bind_items" not in saved
            units = list(self.units) if legacy else saved.pop("bind_units", [])
            items = saved.pop("bind_items", [])
            self.add_custom_skill(SkillDefinition.from_dict(skill_id, saved), units, items)

    # --- юниты ---

    def create_unit(self, definition_id: str, uid: int, level: int = 1, equipment: Sequence[Optional[str]] = ()) -> Unit:
        """Новый юнит с полным HP. Предметы раскладываются по подходящим слотам класса."""
        state = UnitState(uid=uid, definition_id=definition_id, level=level, current_hp=0, equipment=list(equipment))
        unit = Unit(self.units[definition_id], state, self.items)
        state.current_hp = unit.max_hp
        return unit

    def restore_unit(self, state: UnitState, saved_effects: Sequence[Mapping[str, Any]] = ()) -> Unit:
        """Восстанавливает юнита из сохранённого состояния и списка эффектов."""
        unit = Unit(self.units[state.definition_id], state, self.items)
        unit.load_effects(saved_effects, self.effects)
        return unit
