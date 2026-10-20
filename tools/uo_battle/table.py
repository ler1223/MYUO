"""Таблица «навык -> анимации -> события»: python tools/uo_battle/table.py  (пишет docs/uo/skill_table.md).

По каждому навыку каждого несюжетного класса: откуда привязка (слот UO по имени навыка / общая анимация
атаки или магии, подобранная по виду навыка / ручная правка из редактора), части цепочки с длительностью и
события анимаций из файла игры: 0 — удар/выпуск, 1 — начало движения, 2 — получение удара, 3 — остановка.
Время событий — мс от начала самой части; в редакторе они показаны на шкале и берутся кнопками.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

TYPES = {0: "удар", 1: "движ.", 2: "получ.", 3: "стоп"}
TICK = 1000 / 60


def main() -> None:
    from battle.data import ShowData
    from game.database import Database
    db, data = Database.load(), ShowData()
    manual = json.loads((ROOT / "data" / "uo_battle.json").read_text(encoding="utf-8")).get("manual", {})
    rows = ["# Таблица навыков и анимаций UO", "", "Собрано `tools/uo_battle/table.py`. Источник: слот UO — анимации "
            "`S##_<навык>` файла класса; общая — `ATTACK_*` / `MAGIC_*`, подобранная по виду навыка (в данных игры "
            "связи «навык -> слот» нет); ручная — правка из `skill_editor.py`. События: удар / движ. / получ. / стоп, "
            "в мс от начала части.", ""]
    for cls in sorted(data.classes):
        unit = db.units.get(cls)
        if unit is None or unit.story:
            continue
        info = data.classes[cls]
        model = data.unit_model(cls)
        title = f"## {cls} — {info['file']}" + (" (модель временная: в игре её нет)" if info.get("stand_in") else "")
        rows += [title, "", "| Навык | Источник | Часть | мс | События |", "|---|---|---|---|---|"]
        for entry in unit.skills:
            sid = entry if isinstance(entry, str) else entry["id"]
            chain = info.get("skills", {}).get(sid, [])
            own = manual.get("classes", {}).get(cls, {}).get("skills", {}).get(sid)
            source = "ручная" if own else ("слот UO" if chain and chain[0].startswith("S") and chain[0][1:3].isdigit()
                                           else "общая")
            for i, name in enumerate(chain):
                events = ", ".join(f"{TYPES.get(t, t)} {tick * TICK:.0f}" for tick, t in model.puppet.events(name))
                rows.append(f"| {sid if i == 0 else ''} | {source if i == 0 else ''} | {name} | "
                            f"{data.length_ms(model, name):.0f} | {events or '—'} |")
            if not chain:
                rows.append(f"| {sid} | нет | — | — | — |")
        rows.append("")
    out = ROOT / "docs" / "uo" / "skill_table.md"
    out.write_text("\n".join(rows), encoding="utf-8")
    print("записано", out)


if __name__ == "__main__":
    main()
