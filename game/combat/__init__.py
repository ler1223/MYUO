"""Правила боя Unicorn Overlord (docs/uo/battle.md): поле, формулы, ход боя и его запись по действиям."""
from .engine import MAX_ROUNDS, Battle
from .record import Act, Change, Strike

__all__ = ["Battle", "Act", "Change", "Strike", "MAX_ROUNDS"]
