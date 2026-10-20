"""Настройки игры из DbReg/DbRegDb.drg (Unicorn Overlord): именованные числа, которыми код игры
настраивает бой, камеру, эффекты, интерфейс.

Файл: заголовок ("DRG", 96, число записей, 0, смещение таблицы групп, 0, смещение таблицы записей, …),
группы по 144 байта (число записей, первая запись, номер, 0, путь исходного .txt — 64, имя группы — 24,
описание — 40), записи по 208 байт: вид (0 — целое, 1 — дробное), значение float32, 8 байт пусто,
имя (64, ASCII), описание (128, UTF-8, японский; часто только у первой записи блока).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

GROUP_SIZE = 144
RECORD_SIZE = 208


@dataclass(frozen=True)
class Param:
    group: str
    name: str
    value: float
    is_float: bool
    note: str


@dataclass(frozen=True)
class Group:
    name: str
    source: str                    # исходный файл настроек у разработчиков (…/Battle/Effect.txt)
    note: str
    first: int
    count: int


def _text(raw: bytes, encoding: str = "utf-8") -> str:
    return raw.split(b"\0", 1)[0].decode(encoding, "replace")


def parse(data: bytes) -> tuple[list[Group], list[Param]]:
    if data[:4] != b"DRG\0":
        raise ValueError("not a DRG file")
    _, _, count, _, group_at, _, table = struct.unpack_from("<4s6I", data, 0)
    groups = []
    at = group_at
    while at + GROUP_SIZE <= table:
        entry = data[at:at + GROUP_SIZE]
        if not entry[16:].startswith(b"C:/"):
            break
        n, first, _, _ = struct.unpack_from("<4I", entry, 0)
        groups.append(Group(_text(entry[80:104]), _text(entry[16:80]), _text(entry[104:144]), first, n))
        at += GROUP_SIZE
    owner = {}
    for group in groups:
        for i in range(group.first, group.first + group.count):
            owner[i] = group.name
    params = []
    for i in range(count):
        at = table + i * RECORD_SIZE
        if at + RECORD_SIZE > len(data):
            break
        kind, value = struct.unpack_from("<If", data, at)
        name = _text(data[at + 16:at + 80], "ascii")
        if name:
            params.append(Param(owner.get(i, ""), name, value, kind == 1, _text(data[at + 80:at + RECORD_SIZE])))
    return groups, params


class DbReg:
    """Настройки по группам: reg["BTEFFECT"]["FIREBALL_SPEED"].value."""

    def __init__(self, path: Path):
        self.groups, self.params = parse(Path(path).read_bytes())
        self._by_group: dict[str, dict[str, Param]] = {}
        for p in self.params:
            self._by_group.setdefault(p.group, {}).setdefault(p.name, p)

    def __getitem__(self, group: str) -> dict[str, Param]:
        return self._by_group.get(group, {})

    def value(self, group: str, name: str, default: float = 0.0) -> float:
        p = self[group].get(name)
        return p.value if p is not None else default

    def find(self, prefix: str) -> Iterator[Param]:
        return (p for p in self.params if p.name.startswith(prefix))
