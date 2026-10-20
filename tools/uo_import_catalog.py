"""Перенос каталога Unicorn Overlord (docs/uo/catalog/items.json) в data/items.json.

Что делает:
- ограничения по классам: `classes` предмета = `classes.allowed` записи каталога
  (пустой список — без ограничений). Локализационные дубли (Sacral Sword и Sainted Sword —
  один игровой предмет) получают тот же список, что и канонический;
- навыки и пассивки, которые дают предметы (игровой файл, поле word12): недостающие ссылки
  добавляются. Пассивки-заглушки (реакция restore_pp без числа — ничего не делает и тратит PP)
  не привязываются: см. отчёт;
- характеристики: там, где игра и вики расходятся, берётся число из игры (приоритет игрового файла);
- недостающие предметы: дубликаты имён из игры добавляются суффиксами _ii/_iii.

Запуск: python -X utf8 tools/uo_import_catalog.py [--write]
Без --write печатает отчёт и ничего не меняет.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CATALOG_PATH = BASE / "docs" / "uo" / "catalog" / "items.json"
ITEMS_PATH = BASE / "data" / "items.json"
TOOLS = BASE / "tools"
sys.path.insert(0, str(TOOLS))
import uo_catalog as uc  # noqa: E402

# Вики-имя -> id дубля в data/items.json. Это те же игровые предметы под старыми (вики) именами.
ALIAS_DUPS = {
    "Rosularis Sword": "rosularis_sword", "Sacral Sword": "sacral_sword", "Notos's Sword": "notoss_sword",
    "Recruit's ShortAxe": "recruits_shortaxe", "Helleborus Axe": "helleborus_axe", "Sacral Axe": "sacral_axe",
    "Boreas's Axe": "boreass_axe", "Zenoiran Knight Spear": "zenoiran_knight_spear", "Orchis Spear": "orchis_spear",
    "Sacral Spear": "sacral_spear", "Kingspear Elhal": "kingspear_elhal", "Zephyros's Spear": "zephyross_spear",
    "Zenoiran Knight Bow": "zenoiran_knight_bow", "Quince Bow": "quince_bow", "Sacral Bow": "sacral_bow",
    "Apeliotes's Bow": "apeliotess_bow", "Baroque Staff": "baroque_staff", "Carnat Staff": "carnat_staff",
    "Vorpal Staff": "vorpal_staff", "Meteorite Staff": "meteorite_staff", "Lupinus Staff": "lupinus_staff",
    "Sacral Staff": "sacral_staff", "Euros's Staff": "euross_staff",
    "Skiron's Greatshield": "skirons_greatshield", "Ervélda's Talisman": "erveldas_talisman",
    "Sacral Broach": "sacral_broach", "Lips's Ring": "lipss_ring", "Watchman's Bockler": "watchmans_bockler",
    "Mercenay's Shield": "mercenays_shield", "Kaikai's Shield": "kaikais_shield",
}

# Предметы, которые в каталоге описаны как отдельные записи с тем же именем (дубликаты имён в игре).
# id каталога -> id в data (суффикс _ii/_iii по правилам проекта).
NEW_ITEMS = {
    "twinned_bough__2": "twinned_bough_ii",
    "greatshield_of_the_abyss__2": "greatshield_of_the_abyss_ii",
    "ring_of_the_unicorn__2": "ring_of_the_unicorn_ii",
    "ring_of_the_unicorn__3": "ring_of_the_unicorn_iii",
}

# Расхождения, которые намеренно не переносим.
SKIP_MODIFIERS = {"ring_of_the_maiden", "warding_staff"}   # каталог сдвинул дубликаты колец; у посоха
                                                 # «Guard Rate -25%» из вики-таблицы каталог не разобрал
SKIP_BONUSES = {"ring_of_the_maiden"}           # та же сдвинутая запись: PP +1 у неё верный


def is_stub_passive(passives: dict, pid: str) -> bool:
    """Пассивка-заглушка: реакция restore_pp без числа — ничего не делает, но тратит PP."""
    reaction = passives[pid]["reaction"]
    return reaction["action"] == "restore_pp" and not reaction.get("amount")


def main(write: bool) -> int:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["items"]
    items = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
    passives = json.loads((BASE / "data" / "passives.json").read_text(encoding="utf-8"))
    cat_by_id = {i["id"]: i for i in catalog}
    cat_by_name = {uc.norm_name(i["name"]): i for i in catalog}

    # --- маппинг каталог -> data ---
    cat_to_data: dict[str, str] = {}
    for i in catalog:
        im = i.get("implementation") or {}
        if im.get("present") and im.get("id") in items:
            cat_to_data[i["id"]] = im["id"]
    dup_of: dict[str, str] = {}
    for wiki_name, data_id in ALIAS_DUPS.items():
        game_name = uc.ALIASES_BIDIR.get(uc.norm_name(wiki_name))
        c = cat_by_name.get(uc.norm_name(game_name)) if game_name else None
        if c and data_id in items:
            dup_of[data_id] = c["id"]
            cat_to_data.setdefault(c["id"], data_id)

    report = {"classes": 0, "skills": [], "passives": [], "skipped_passives": [], "modifiers": [],
              "tags": [], "bonuses": [], "new_items": [], "duplicates": len(dup_of)}
    applied = 0

    for cid, did in cat_to_data.items():
        c = cat_by_id[cid]
        sug = c.get("suggested") or {}
        allowed = (c.get("classes") or {}).get("allowed") or []
        entry = items[did]
        changed = False

        # ограничения по классам
        if allowed and entry.get("classes") != allowed:
            entry["classes"] = list(allowed)
            changed = True
            report["classes"] += 1

        # навыки
        want_skills = list(sug.get("skills") or [])
        if set(want_skills) != set(entry.get("skills") or []):
            entry["skills"] = want_skills
            changed = True
            report["skills"].append((did, want_skills))

        # пассивки: добавляем недостающие с реальной реализацией (заглушки не привязываем)
        want_passives = [p for p in (sug.get("passives") or []) + [x["id"] for x in (sug.get("item_passives") or [])]
                         if p in passives]
        skipped = [p for p in want_passives if is_stub_passive(passives, p)]
        want_passives = [p for p in want_passives if p not in skipped]
        if skipped:
            report["skipped_passives"].append((did, skipped))
        merged = list(dict.fromkeys(list(entry.get("passives") or []) + want_passives))
        if set(merged) != set(entry.get("passives") or []):
            entry["passives"] = merged
            changed = True
            report["passives"].append((did, want_passives))

        # характеристики (приоритет игрового файла)
        if did not in SKIP_MODIFIERS:
            want_mods = sug.get("modifiers") or []
            if want_mods != entry.get("modifiers"):
                entry["modifiers"] = want_mods
                changed = True
                report["modifiers"].append(did)

        # теги
        want_tags = list(sug.get("tags") or [])
        if set(want_tags) != set(entry.get("tags") or []):
            entry["tags"] = want_tags
            changed = True
            report["tags"].append((did, want_tags))

        # бонусы AP/PP
        for field, key in (("ap_bonus", "ap_bonus"), ("pp_bonus", "pp_bonus")):
            if did in SKIP_BONUSES:
                continue
            if sug.get(field) != entry.get(key, 0):
                entry[key] = sug.get(field) or 0
                changed = True
                report["bonuses"].append((did, field, entry[key]))

        if changed:
            applied += 1

    # --- локализационные дубли: тот же список классов, что у канонического предмета ---
    for did, cid in dup_of.items():
        allowed = (cat_by_id[cid].get("classes") or {}).get("allowed") or []
        if allowed and items[did].get("classes") != allowed:
            items[did]["classes"] = list(allowed)
            report["classes"] += 1
            applied += 1

    # --- недостающие предметы (дубликаты имён из игры) ---
    for cid, did in NEW_ITEMS.items():
        if did in items:
            continue
        c = cat_by_id.get(cid)
        if c is None:
            continue
        sug = c.get("suggested") or {}
        allowed = (c.get("classes") or {}).get("allowed") or []
        base_cat = cat_by_id.get(cid.rsplit("__", 1)[0])
        base_data = cat_to_data.get(base_cat["id"]) if base_cat else None
        name = (items[base_data]["name"] if base_data in items else c["name"])
        items[did] = {
            "name": f"{name} II" if did.endswith("_ii") else f"{name} III",
            "slot": sug.get("slot"),
            "tier": sug.get("tier", 1),
            "price": sug.get("price", 0),
            **({"classes": list(allowed)} if allowed else {}),
            **({"ap_bonus": sug["ap_bonus"]} if sug.get("ap_bonus") else {}),
            **({"pp_bonus": sug["pp_bonus"]} if sug.get("pp_bonus") else {}),
            "modifiers": sug.get("modifiers") or [],
            "skills": list(sug.get("skills") or []),
            "passives": [p for p in (sug.get("passives") or []) + [x["id"] for x in (sug.get("item_passives") or [])]
                         if p in passives and not is_stub_passive(passives, p)],
            "tags": list(sug.get("tags") or []),
            "damage_tags": [],
        }
        report["new_items"].append((did, items[did]["name"]))

    print("=== отчёт переноса ===")
    print("сопоставлено каталог->data:", len(cat_to_data), "| локализационных дублей:", report["duplicates"])
    print("предметов изменено:", applied)
    print("  ограничения по классам:", report["classes"])
    print("  навыки:", len(report["skills"]))
    for did, s in report["skills"]:
        print("      %-28s %s" % (did, s))
    print("  пассивки:", len(report["passives"]))
    for did, p in report["passives"]:
        print("      %-28s %s" % (did, p))
    print("  пассивки-заглушки (не привязаны):", len(report["skipped_passives"]))
    for did, p in report["skipped_passives"]:
        print("      %-28s %s" % (did, p))
    print("  характеристики:", len(report["modifiers"]))
    print("     ", report["modifiers"])
    print("  теги:", len(report["tags"]))
    for did, t in report["tags"]:
        print("      %-28s %s" % (did, t))
    print("  бонусы AP/PP:", len(report["bonuses"]))
    for did, f, v in report["bonuses"]:
        print("      %-28s %s=%s" % (did, f, v))
    print("  новые предметы:", report["new_items"])
    print("  всего предметов в data:", len(items))

    if write:
        ITEMS_PATH.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("\nзаписано:", ITEMS_PATH)
    else:
        print("\n(без --write ничего не записано)")
    return 0


if __name__ == "__main__":
    sys.exit(main("--write" in sys.argv))
