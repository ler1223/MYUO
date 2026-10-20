"""Кто что носит: виды предметов и виды классов из каталога UO (docs/uo/catalog/items.json).

    python -X utf8 tools/uo_equip_kinds.py [--write]

Как в игре (подтип word7 у предмета и список подтипов у класса):
- у предмета ``kind`` — вид; основной вид слота (обычный меч, топор, копьё, лук, посох, щит) не пишется;
- у класса ``equips`` — особые виды сверх основных видов своих слотов: молоты, арбалеты, рапиры, посохи магов
  (``staff_arcane``), лекарей (``staff_divine``), шаманов (``staff_shaman``);
- ``config.json: item_kinds`` — особые виды и их слоты;
- ``classes`` у предмета остаётся только для исключений: именное оружие (Ален, драгуны, Flame Javelin,
  Gleaming Mace) и аксессуары с задокументированным ограничением. Списки, которые повторяют правило вида
  (``base``, ``all_staff``, молоты, арбалеты...), убираются.

Заодно правятся слоты классов, противоречащие спискам «Equippable By» (см. SLOT_FIXES).
В конце сверка: для каждого обычного (не сюжетного) класса и предмета новое правило даёт то же, что каталог.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

# правило каталога -> особый вид предмета
KIND_OF_RULE = {"hammer": "hammer", "crossbow": "crossbow", "rapier": "rapier",
                "arcane": "staff_arcane", "divine": "staff_divine", "shaman": "staff_shaman"}
ITEM_KINDS = {"hammer": "heavy_weapon", "crossbow": "bow", "rapier": "light_sword",
              "staff_arcane": "staff", "staff_divine": "staff", "staff_shaman": "staff"}
# правила, которые целиком описываются видом: список классов у предмета не нужен
BY_KIND = {"base", "all_staff", "unrestricted", *KIND_OF_RULE}

# Слоты классов, расходящиеся со списками каталога (Miraheze «Equippable By»):
#   Sainted Knight (повышение Radiant Knight) — меч и щит, не копьё;
#   Viking и Landsknecht носят щит (списки щитов), один слот аксессуара становится щитом.
SLOT_FIXES = {
    "sainted_knight": ("lance", "light_sword"),
    "viking": ("artifact", "light_shield"),
    "landsknecht": ("artifact", "light_shield"),
}


def load(path: Path):
    raw = path.read_text(encoding="utf-8")
    return raw, json.loads(raw)


def dump(path: Path, raw: str, data) -> None:
    indent = 2 if raw.startswith('{\n  "') else 1
    path.write_text(json.dumps(data, ensure_ascii=False, indent=indent) + ("\n" if raw.endswith("\n") else ""),
                    encoding="utf-8", newline="")


def main(write: bool) -> int:
    catalog = json.loads((BASE / "docs" / "uo" / "catalog" / "items.json").read_text(encoding="utf-8"))["items"]
    items_raw, items = load(BASE / "data" / "items.json")
    units_raw, units = load(BASE / "data" / "units.json")
    config_raw, config = load(BASE / "data" / "config.json")
    by_id = {c["id"]: c for c in catalog}

    # --- слоты классов ---
    for class_id, (old, new) in SLOT_FIXES.items():
        slots = units[class_id]["slots"]
        if new in slots:
            continue
        index = slots.index(old) if old != "artifact" else len(slots) - 1 - slots[::-1].index(old)
        slots[index] = new
        if new == "light_shield":                       # щит сразу за оружием, как у остальных классов
            slots.insert(1, slots.pop(index))
        print(f"слоты {class_id}: {old} -> {new}: {slots}")

    # --- правило каждого предмета игры: из каталога, а для дублей-синонимов — по совпадению списка ---
    rule_sets: dict[tuple[str, frozenset], str] = {}
    for c in catalog:
        if c["slot"] and c["classes"]["rule"] != "unrestricted":
            rule_sets.setdefault((c["slot"], frozenset(c["classes"]["allowed"])), c["classes"]["rule"])
    rules: dict[str, str] = {}
    unknown = []
    for item_id, item in items.items():
        if item_id in by_id:
            rules[item_id] = by_id[item_id]["classes"]["rule"]
        elif not item.get("classes"):
            rules[item_id] = "unrestricted"
        elif (item["slot"], frozenset(item["classes"])) in rule_sets:
            rules[item_id] = rule_sets[(item["slot"], frozenset(item["classes"]))]
        else:
            rules[item_id] = "explicit"
            unknown.append(item_id)
    if unknown:
        print("без записи каталога, список оставлен как исключение:", unknown)

    # --- виды классов: кому каталог разрешает предметы особого вида ---
    equips: dict[str, set[str]] = defaultdict(set)
    for c in catalog:
        kind = KIND_OF_RULE.get(c["classes"]["rule"])
        if kind:
            for class_id in c["classes"]["allowed"]:
                if ITEM_KINDS[kind] in units[class_id]["slots"]:
                    equips[class_id].add(kind)
                else:
                    print(f"  {class_id}: в списке {kind}, но нет слота {ITEM_KINDS[kind]}")
    order = list(ITEM_KINDS)
    for class_id, unit in units.items():
        listed = sorted(equips.get(class_id, ()), key=order.index)
        if listed:
            unit["equips"] = listed
        else:
            unit.pop("equips", None)

    # --- предметы: вид и исключения ---
    dropped = kept = 0
    for item_id, item in items.items():
        rule = rules[item_id]
        kind = KIND_OF_RULE.get(rule)
        if kind:
            item["kind"] = kind
        else:
            item.pop("kind", None)
        if rule in BY_KIND:
            if item.pop("classes", None):
                dropped += 1
        elif item.get("classes"):
            kept += 1
    config["item_kinds"] = ITEM_KINDS

    # --- сверка с каталогом ---
    from game.database import Database
    from game.unit import wearable
    db = Database({**{"config": config, "items": items, "units": units},
                   **{k: json.loads((BASE / "data" / f"{k}.json").read_text(encoding="utf-8"))
                      for k in ("skills", "effects", "tags", "areas") if (BASE / "data" / f"{k}.json").exists()}})
    mismatch = []
    for item_id, item in db.items.items():
        c = by_id.get(item_id)
        if c is None or c["classes"]["rule"] == "unrestricted":
            continue
        allowed = set(c["classes"]["allowed"])
        for class_id, unit in db.units.items():
            if unit.story or item.slot not in unit.slots:
                continue
            new = wearable(item, unit)
            if new != (class_id in allowed):
                mismatch.append((item_id, class_id, new))
    print(f"списков классов убрано: {dropped}; исключений осталось: {kept}")
    print("виды классов:", {k: sorted(v) for k, v in sorted(equips.items())})
    print(f"расхождений с каталогом у обычных классов: {len(mismatch)}")
    for row in mismatch[:20]:
        print("  ", row)
    if write:
        dump(BASE / "data" / "items.json", items_raw, items)
        dump(BASE / "data" / "units.json", units_raw, units)
        dump(BASE / "data" / "config.json", config_raw, config)
        print("записано")
    else:
        print("(без --write ничего не записано)")
    return 0


if __name__ == "__main__":
    sys.exit(main("--write" in sys.argv))
