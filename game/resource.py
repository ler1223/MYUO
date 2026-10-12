"""Общий класс ресурса для AP и PP."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Resource:
    max: int
    current: int

    def __post_init__(self) -> None:
        self.current = min(max(self.current, 0), self.max)

    def can_spend(self, amount: int) -> bool:
        return self.current >= amount

    def spend(self, amount: int) -> None:
        if not self.can_spend(amount):
            raise ValueError(f"not enough resource: {self.current} < {amount}")
        self.current -= amount

    def gain(self, amount: int) -> None:
        self.current = min(self.max, self.current + amount)

    def refill(self) -> None:
        self.current = self.max
