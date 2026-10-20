"""Как устроены навыки в Unicorn Overlord: расшифровка записи навыка и условий тактики из файлов игры.

    python -X utf8 tools/uo_skill_records.py [--main F:\\MYUO2\\main.bin] [--text F:\\MYUO2\\unpacked_us]

Пишет:
- docs/uo/catalog/factors.json — все условия тактики игры (MsgSheet/UcFactorList.fms): номер, короткое и полное имя,
  описание, группа экрана тактики и вид: prioritize (порядок целей), target_only (фильтр целей: нет подходящих —
  навык не срабатывает), activates_only (условие на обстановку, себя или атаку).
- docs/uo/catalog/skill_records.json — расшифрованные поля записи каждого навыка каталога (таблица в main.bin,
  76 слов u32 на навык; см. tools/uo_skills_game.py про найденную раньше раскладку).

Какие слова что значат, проверено сопоставлением с текстами всех 437 навыков (чистота — доля навыков, у которых
значение однозначно задаётся свойством):
  41 — вид: 1 активный, 2 пассивный (100%);
   7 — тип: 1 атака, 2 помеха, 3 лечение, 4 поддержка (совпадает со значками игры);
  12 — кому: у активных 1 враг, 6 союзник, 7 сам; у пассивок 1 враг (обычный выбор цели), 2 атаковавший
       (контратака), 3 цель союзника (преследование), 4 действующий союзник (усиление его атаки), 5 атакованный
       или ослабленный союзник (прикрытие, лечение состояний), 6 союзник, 7 сам (98%);
  13 — область: 1 одна цель, 2 две, 3 три, 5 все, 6 ряд, 7 колонна (95%; расхождения — ошибки старого импорта);
   8 — особый ответ: 1 воскрешение, 2 добавка к атаке союзника, 3 преследование, 4 контратака, 5 отражение, 6 прикрытие;
  43 — фаза срабатывания пассивки: 1 начало боя, 2 до чужого действия, 3 до удара по себе, 4 после своей защиты,
       5 после действия, 6 конец боя (100%);
  44 — событие срабатывания пассивки (40 значений на 47 текстов условий, 100%), таблица TRIGGER_EVENTS ниже;
  45, 46, 47 — условия тактики по умолчанию (номера UcFactorList): «Prioritize Bestral» у Beastslayer, «Cavalry» у
       Cavalry Slayer, «Lowest HP» + «Flying Enemies Present» у пассивки Aerial Shift — то есть пассивки стоят в тактике
       с теми же условиями, что активные;
  66 — подготовка (charge): не 0 только у навыков «charging» (97%);
   1 — флаги, бит 0 — дальнобойный (Ranged).
Слова 14, 42, 48, 49, 75 различают группы навыков, но смысл не установлен: они выгружаются как unknown.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "tools"))
import uo_catalog as uc  # noqa: E402

OUT = BASE / "docs" / "uo" / "catalog"

KIND = {1: "active", 2: "passive"}
TYPE = {1: "attack", 2: "debuff", 3: "heal", 4: "support"}
TARGET_ACTIVE = {1: "enemy", 6: "ally", 7: "self"}
TARGET_PASSIVE = {1: "enemy", 2: "attacker", 3: "ally_target", 4: "acting_ally", 5: "affected_ally", 6: "ally",
                  7: "self"}
AREA = {1: "single", 2: "two", 3: "three", 5: "all", 6: "row", 7: "column"}
RESPONSE = {1: "revive", 2: "imbue", 3: "pursuit", 4: "counter", 5: "reflect", 6: "cover"}
PHASE = {1: "battle_start", 2: "before_other", 3: "before_hit", 4: "after_defence", 5: "after", 6: "battle_end"}
# событие (слово 44) -> (событие MYUO, чьё, фильтр). Фаза 1 и 6 — событие 0.
TRIGGER_EVENTS = {
    15: ("skill_used", "self", None), 16: ("skill_used", "ally", None), 17: ("passive_used", "ally", None),
    20: ("skill_used", "self", "attack"), 21: ("skill_used", "self", "magical"), 22: ("before_skill", "self", None),
    28: ("before_skill|skill_used", "ally", "attack"), 29: ("before_skill", "ally", "physical"),
    30: ("before_skill|skill_used", "ally", "magical"), 31: ("skill_used", "ally", "cavalry"),
    32: ("skill_used", "ally", "flying"), 33: ("healed", "self", None), 34: ("passive_used", "ally", "on_owner"),
    39: ("targeted", "self", None), 40: ("targeted", "self", "melee"), 41: ("targeted", "self", "ranged"),
    42: ("targeted", "self", "physical"), 43: ("targeted", "self", "magical"), 44: ("attacked", "self", "missed"),
    45: ("attacked", "self", "guarded"), 46: ("attacked", "self", None), 47: ("attacked", "self", "physical"),
    49: ("skill_used", "enemy", None), 50: ("targeted", "ally", None), 51: ("targeted", "ally", "unknown"),
    53: ("targeted", "ally", "magical"), 54: ("targeted", "ally", "ranged physical"), 55: ("attacked", "ally", None),
    56: ("attacked", "ally", "landed"), 57: ("healed", "ally", None), 58: ("died", "ally", None),
    59: ("before_skill", "enemy", "attack"), 63: ("before_skill", "enemy", "magical"),
    64: ("skill_used", "enemy", "healing"), 65: ("attacked", "enemy", "guarded"),
    67: ("effect_applied", "self", "debuff"), 69: ("effect_applied", "ally", "debuff"),
    70: ("effect_applied", "enemy", "buff"), 71: ("effect_applied", "enemy", "debuff"),
}
# группы экрана тактики (UcFactorList 610..622) и диапазоны номеров условий
GROUPS = [((1, 11), "formation"), ((12, 31), "hp"), ((32, 53), "status"), ((54, 73), "combatant_type"),
          ((74, 88), "attack_type"), ((89, 104), "unit_size"), ((105, 112), "own_hp"), ((113, 132), "ap_pp"),
          ((133, 148), "own_ap_pp"), ((149, 157), "own_condition"), ((158, 177), "enemies_present"),
          ((178, 189), "high_stats"), ((190, 201), "low_stats")]


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"#c\(\d+\)|#/c|#\(\d+\)", "", text or "").replace("%%", "%")).strip()


# опечатки и служебные записи игры (имя расходится с описанием): № 95 «2 or Fewer» — «three or fewer enemies»,
# № 107 «Own HP is >75%» — «75% or less HP»
KEY_FIXES = {95: "3_or_fewer_enemies", 107: "own_hp_is_lt_75_pct", 202: "story_only"}


def factor_key(fid: int, name: str, group: str) -> str:
    """Стабильный ключ условия для данных тактик: «Target HP is <25%» -> target_hp_lt_25."""
    if not fid:
        return "none"
    if fid in KEY_FIXES:
        return KEY_FIXES[fid]
    text = name.lower().replace("<", " lt ").replace(">", " gt ").replace("%", " pct").replace("+", " plus")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def factors(sheet: list[str]) -> list[dict]:
    out = []
    for fid in range(0, 203):            # 202 — «???»: служебное условие сюжетных навыков
        desc = clean(sheet[fid + 406]) if fid else ""
        kind = ("prioritize" if desc.startswith("Prioritize") else "target_only" if desc.startswith("Target only")
                else "activates_only" if desc.startswith("Activates") else "none")
        group = next((g for (lo, hi), g in GROUPS if lo <= fid <= hi), "none")
        out.append({"id": fid, "key": factor_key(fid, clean(sheet[fid]), group), "name": clean(sheet[fid]),
                    "short": clean(sheet[fid + 203]),
                    "description": desc.split(" The skill")[0], "group": group, "kind": kind})
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--main", type=Path, default=Path(r"F:\MYUO2\main.bin"))
    parser.add_argument("--text", type=Path, default=Path(r"F:\MYUO2\unpacked_us"))
    args = parser.parse_args()
    sheet = uc.read_names(args.text / "MsgSheet" / "UcFactorList.fms")
    table = factors(sheet)
    seen: dict[str, int] = {}
    for factor in table:                         # одинаковые имена в игре (два «2 or Fewer Enemies») — с номером
        if factor["key"] in seen:
            raise SystemExit(f"повтор ключа условия {factor['key']}: {seen[factor['key']]} и {factor['id']}")
        seen[factor["key"]] = factor["id"]
    names = {f["id"]: f["name"] for f in table}
    keys = {f["id"]: f["key"] for f in table}

    image = args.main.read_bytes()
    words = np.frombuffer(image[:len(image) // 4 * 4], "<u4").astype(np.int64)
    base = uc.find_skill_table(words)
    catalog = json.loads((OUT / "skills.json").read_text(encoding="utf-8"))["skills"]
    records = {}
    for entry in catalog:
        if not entry.get("game"):
            continue
        sid = entry["game"]["id"]
        r = [int(v) for v in words[base + (sid - 171) * uc.SKILL_STRIDE: base + (sid - 170) * uc.SKILL_STRIDE]]
        kind = KIND.get(r[41], r[41])
        record = {
            "game_id": sid, "internal": entry["game"]["internal"], "kind": kind, "type": TYPE.get(r[7], r[7]),
            "target": (TARGET_PASSIVE if kind == "passive" else TARGET_ACTIVE).get(r[12], r[12]),
            "area": AREA.get(r[13], r[13]), "response": RESPONSE.get(r[8]), "ranged": bool(r[1] & 1),
            "charge": bool(r[66]),
            "default_conditions": [{"id": r[k], "key": keys.get(r[k], "?"), "name": names.get(r[k], "?")}
                                   for k in (45, 46, 47) if r[k]],
            "unknown": {str(k): r[k] for k in (14, 42, 48, 49, 75)},
        }
        if kind == "passive":
            event = TRIGGER_EVENTS.get(r[44]) if r[44] else (PHASE[r[43]], "self", None)
            record["trigger"] = {"phase": PHASE.get(r[43], r[43]), "event_id": r[44],
                                 "text": entry["text"].split("\n")[0],
                                 **({"event": event[0], "whose": event[1], "filter": event[2]} if event else {})}
        records[entry["id"]] = record
    (OUT / "factors.json").write_text(json.dumps({"source": "MsgSheet/UcFactorList.fms", "factors": table},
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "skill_records.json").write_text(json.dumps({"source": "main.bin skill table, см. docstring "
                                                        "tools/uo_skill_records.py", "skills": records},
                                                       ensure_ascii=False, indent=1), encoding="utf-8")
    with_defaults = sum(1 for r in records.values() if r["default_conditions"])
    print(f"условий тактики: {len(table)}; навыков: {len(records)}; с условиями по умолчанию: {with_defaults}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
