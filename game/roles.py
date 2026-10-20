"""Роли классов (башня): воин, лучник, маг, поддержка, танк, целитель.

Роли — свойство класса (data/units.json, поле "roles": их может быть несколько);
из ролей собираются группы стартового набора. Какие группы и сколько вариантов
в каждой — в data/tower.json (раздел draft), а не в редакторах.
"""
from __future__ import annotations

from typing import Any

WARRIOR = "warrior"
ARCHER = "archer"
MAGE = "mage"
SUPPORT = "support"
TANK = "tank"
HEALER = "healer"

ROLES = (WARRIOR, ARCHER, MAGE, SUPPORT, TANK, HEALER)

# Названия ролей для интерфейса (ключи перевода в data/lang).
TITLES = {
    WARRIOR: "Warrior",
    ARCHER: "Archer",
    MAGE: "Mage",
    SUPPORT: "Support",
    TANK: "Tank",
    HEALER: "Healer",
}


def normalize(value: Any) -> tuple[str, ...]:
    """Роли класса из данных: список (новый формат), строка (старый) или ничего.

    Порядок и повторы сохраняются; неизвестные роли не отбрасываются, чтобы
    правка данных в редакторе ничего не теряла.
    """
    if not value:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set, frozenset)):
        return ()
    return tuple(dict.fromkeys(str(role) for role in value if role))
