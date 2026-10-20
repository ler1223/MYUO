"""Показ боя Unicorn Overlord: правила game.combat, сцены по актам, фон, бойцы, эффекты и интерфейс UO.

Разбор оригинала — docs/uo/battle.md; данные из файлов игры — data/uo_battle.json (tools/uo_battle/build.py).
"""
from .show import BattleShow

__all__ = ["BattleShow"]
