"""Карта мира (позиции отрядов) и армия игрока (юниты и отряды)."""
from __future__ import annotations

from typing import Optional

from .squad import Squad
from .unit import Unit


class WorldMap:
    """Единственное место, где хранится положение отрядов."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.positions: dict[str, tuple[int, int]] = {}

    def place(self, squad_id: str, x: int, y: int) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise ValueError(f"cell ({x}, {y}) is outside the map")
        occupant = self.squad_at(x, y)
        if occupant is not None and occupant != squad_id:
            raise ValueError(f"cell ({x}, {y}) is occupied by {occupant}")
        self.positions[squad_id] = (x, y)

    def remove(self, squad_id: str) -> None:
        self.positions.pop(squad_id, None)

    def position_of(self, squad_id: str) -> Optional[tuple[int, int]]:
        return self.positions.get(squad_id)

    def squad_at(self, x: int, y: int) -> Optional[str]:
        for squad_id, pos in self.positions.items():
            if pos == (x, y):
                return squad_id
        return None

    def are_adjacent(self, squad_a: str, squad_b: str) -> bool:
        """Соседние по стороне клетки."""
        a, b = self.positions.get(squad_a), self.positions.get(squad_b)
        if a is None or b is None:
            return False
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


class Army:
    def __init__(self, army_id: str, name: str):
        self.id = army_id
        self.name = name
        self.units: dict[int, Unit] = {}
        self.squads: dict[str, Squad] = {}

    def recruit(self, unit: Unit) -> Unit:
        if unit.uid in self.units:
            raise ValueError(f"unit {unit.uid} is already in the army")
        self.units[unit.uid] = unit
        return unit

    def create_squad(self, squad_id: str, name: str) -> Squad:
        if squad_id in self.squads:
            raise ValueError(f"squad {squad_id} already exists")
        squad = Squad(squad_id, name)
        self.squads[squad_id] = squad
        return squad

    def squad_of(self, uid: int) -> Optional[Squad]:
        for squad in self.squads.values():
            if squad.formation.position_of(uid) is not None:
                return squad
        return None

    def unassign(self, uid: int) -> None:
        """Убирает юнита из отряда в резерв; лидерство переходит к первому оставшемуся."""
        squad = self.squad_of(uid)
        if squad is None:
            return
        squad.formation.remove(uid)
        if squad.leader_uid == uid:
            rest = squad.formation.units
            squad.leader_uid = rest[0].uid if rest else None

    def dismiss(self, uid: int) -> None:
        """Удаляет юнита из армии совсем."""
        self.unassign(uid)
        del self.units[uid]

    def set_leader(self, squad_id: str, uid: int) -> None:
        squad = self.squads[squad_id]
        if squad.formation.position_of(uid) is None:
            raise ValueError(f"unit {uid} is not in squad {squad_id}")
        squad.leader_uid = uid

    def reserve(self) -> list[Unit]:
        """Юниты армии, не стоящие ни в одном отряде."""
        return [u for u in self.units.values() if self.squad_of(u.uid) is None]

    def assign(self, uid: int, squad_id: str, row: int, col: int) -> None:
        """Ставит юнита в клетку отряда. Первый назначенный становится лидером."""
        unit = self.units[uid]
        squad = self.squads[squad_id]
        previous = self.squad_of(uid)
        old_pos = previous.formation.position_of(uid) if previous else None
        if previous is not None:
            previous.formation.remove(uid)
        try:
            squad.formation.place(unit, row, col)
        except ValueError:
            if previous is not None:  # откат, чтобы юнит не выпал из старого отряда
                previous.formation.place(unit, *old_pos)
            raise
        if previous is not None and previous is not squad and previous.leader_uid == uid:
            rest = previous.formation.units
            previous.leader_uid = rest[0].uid if rest else None
        if squad.leader_uid is None:
            squad.leader_uid = uid
