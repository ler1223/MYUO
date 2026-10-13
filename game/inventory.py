"""Инвентарь армии: золото и стопки предметов по id.

Инвентарь не знает, что за предметы в нём лежат: снаряжение из справочника (data/items.json)
или товары мира (материалы, расходники — каталог goods карты мира). Проверку id делает тот,
кто кладёт предмет. Поэтому новые источники (места сбора, магазины, награды) просто
вызывают add/remove, а надевание снаряжения — equip/unequip.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from .unit import Unit


@dataclass
class Inventory:
    gold: int = 0
    items: dict[str, int] = field(default_factory=dict)   # id -> сколько

    def count(self, item_id: str) -> int:
        return self.items.get(item_id, 0)

    def has(self, item_id: str, count: int = 1) -> bool:
        return self.count(item_id) >= count

    def add(self, item_id: str, count: int = 1) -> None:
        if count < 0:
            raise ValueError("count must not be negative")
        if count:
            self.items[item_id] = self.count(item_id) + count

    def remove(self, item_id: str, count: int = 1) -> bool:
        """Забирает count штук; если столько нет, ничего не меняет и возвращает False."""
        if count < 0 or not self.has(item_id, count):
            return False
        left = self.count(item_id) - count
        if left:
            self.items[item_id] = left
        else:
            self.items.pop(item_id, None)
        return True

    def add_gold(self, amount: int) -> None:
        self.gold = max(0, self.gold + amount)

    def spend_gold(self, amount: int) -> bool:
        if amount < 0 or self.gold < amount:
            return False
        self.gold -= amount
        return True

    # --- снаряжение юнитов ---

    def equip(self, unit: Unit, slot_index: int, item_id: str) -> None:
        """Надевает предмет из инвентаря в слот юнита; снятый предмет возвращается в инвентарь."""
        if not self.has(item_id):
            raise ValueError(f"no {item_id!r} in the inventory")
        previous = unit.state.equipment[slot_index]
        unit.equip(slot_index, item_id)          # проверяет, что предмет подходит слоту
        self.remove(item_id)
        if previous is not None:
            self.add(previous)

    def unequip(self, unit: Unit, slot_index: int) -> Optional[str]:
        """Снимает предмет со слота юнита в инвентарь."""
        item_id = unit.unequip(slot_index)
        if item_id is not None:
            self.add(item_id)
        return item_id

    # --- сохранение ---

    def to_dict(self) -> dict[str, Any]:
        return {"gold": self.gold, "items": dict(sorted(self.items.items()))}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Inventory":
        items = {str(k): int(v) for k, v in dict(data.get("items", {})).items() if int(v) > 0}
        return cls(max(0, int(data.get("gold", 0))), items)
