"""Перечисления игры из Debug/*.inc (Unicorn Overlord): разделы «ИМЯID:число», дальше строки
«ИМЯ , // описание» (описание по-японски). Код игры обращается к эффектам, баффам, навыкам по этим
номерам; описания говорят, чем запись служит (например, у эффектов: 発動 — выпуск, 弾 — снаряд,
軌跡 — след снаряда, 予兆 — предвестник на цели, HIT — попадание).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

HEADER = re.compile(r"^﻿?([A-Z_]+)ID:(\d+)\s*$")
ENTRY = re.compile(r"^([A-Za-z0-9_]+)\s*,\s*(?://\s*(.*))?$")


@dataclass(frozen=True)
class Entry:
    section: str
    index: int
    name: str
    note: str


def parse(text: str) -> dict[str, list[Entry]]:
    """Разделы файла: имя раздела (EFFECT, BUFF, …) -> записи по порядку (номер = место в разделе)."""
    sections: dict[str, list[Entry]] = {}
    current = None
    for line in text.splitlines():
        line = line.strip()
        head = HEADER.match(line)
        if head:
            current = sections.setdefault(head.group(1), [])
            continue
        entry = ENTRY.match(line)
        if entry and current is not None:
            current.append(Entry(next(k for k, v in sections.items() if v is current), len(current),
                                 entry.group(1), (entry.group(2) or "").strip()))
    return sections


def load(path: Path) -> dict[str, list[Entry]]:
    return parse(Path(path).read_text(encoding="utf-8", errors="replace"))


# Роль эффекта по описанию в EFFECTID
ROLES = (("hit", ("HIT", "ヒット")), ("out", ("発動", "発射")), ("trail", ("軌跡",)), ("buffer", ("予兆",)),
         ("shot", ("弾",)))


def effect_role(entry: Entry) -> str:
    """out | shot | trail | buffer | hit | main — чем служит эффект в навыке."""
    note = entry.note.split("：", 1)[1] if "：" in entry.note else ""
    for role, words in ROLES:
        if any(w in note for w in words) or (role == "hit" and entry.name.endswith("_HIT")):
            return role
    return "main"
