"""Именованные персонажи как юниты: слоты снаряжения и навыки, которые реально играют.

Для каждого именованного класса (data/uo_battle.json → manual.classes) добавляет запись в
data/units.json: статы, рост и пассивки берутся у класса-образца, слоты — его же, а навыки
выбираются только те, чья анимация целиком есть в модели именованного (иначе в бою
показывались бы обрывки). Все они — сюжетные (story), в найм башни не попадают.

Запуск из корня проекта: python tools/uo_battle/named_units.py
Повторный запуск обновляет записи, ручные правки в этих 12 юнитах перезаписываются.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# именованный класс: (подпись, класс-образец, тир, навыки)
NAMED = {
    "black_prince": ("Black Prince", "lord", 20, ["lightning_blade", "killing_chain"]),
    "black_prince_hg": ("Black Prince (HG)", "lord", 30, ["warding_slash", "thunderous_strike"]),
    "dark_marquess_a": ("Dark Marquess (A)", "crusader", 25, ["iron_crusher", "spiral_sword"]),
    "dark_marquess_l": ("Dark Marquess (L)", "dark_knight", 25, ["vengeful_axe", "omega_shatter"]),
    "dark_marquess_r": ("Dark Marquess (R)", "sorceress", 25, ["icebolt", "ice_coffin"]),
    "dark_marquess_s": ("Dark Marquess (S)", "viking", 25, ["smash", "rolling_axe"]),
    "eltlinde": ("Eltlinde", "elven_sibyl", 25, ["primus_edge", "faerie_heal"]),
    "feather_bow": ("Feather Bow", "sniper", 25, ["sonic_shaft", "toxic_bolt"]),
    "feather_rod": ("Feather Rod", "warlock", 25, ["innocent_ray", "magick_missile"]),
    "feather_shield": ("Feather Shield", "radiant_knight", 25, ["shield_bash", "defender"]),
    "necromancer": ("Necromancer", "warlock", 25, ["innocent_ray"]),
    "unify": ("Unify", "arbalist", 30, ["power_bolt", "mystic_arrow"]),
}


def learned(skills: list[str]) -> list:
    """Первый навык с первого уровня, остальные — с 10-го (как у сюжетных юнитов)."""
    out = []
    for i, sid in enumerate(skills):
        out.append(sid if i == 0 else {"id": sid, "level": 10})
    return out


def tactics(skills: list[str]) -> list[dict]:
    return [{"skill": sid,
             "self_condition": {"type": "always"},
             "condition": {"type": "always"},
             "selector": "frontmost"} for sid in skills]


def main() -> None:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    from battle.data import ShowData
    from game.database import Database

    show = ShowData()
    db = Database.load()
    path = ROOT / "data" / "units.json"
    units = json.loads(path.read_text(encoding="utf-8"))

    for class_id, (name, base_id, tier, skills) in NAMED.items():
        base = units[base_id]
        model = show.unit_model(class_id, 0)
        anims = model.puppet.anims if model is not None else {}
        for sid in skills:
            anim = show.animation(sid)
            parts = list(anim["parts"]) if anim and anim.get("parts") else list(
                show.classes.get(base_id, {}).get("skills", {}).get(sid, []))
            missing = [p for p in parts if p not in anims]
            if not parts or missing:
                raise SystemExit(f"{class_id}: навык {sid} не сыграет на модели, части {missing}")
        unit = {
            "name": name,
            "stats": copy.deepcopy(base["stats"]),
            "growth": copy.deepcopy(base["growth"]),
            "ap_max": base.get("ap_max", 3),
            "pp_max": base.get("pp_max", 3),
            "tags": list(base.get("tags", ())),
            "slots": list(base.get("slots", ())),
            "skills": learned(skills),
            "passives": copy.deepcopy(base.get("passives", [])),
            "tactics": tactics(skills),
            "tier": tier,
            "story": True,
        }
        if base.get("roles"):
            unit["roles"] = list(base["roles"])
        units[class_id] = unit
        print(f"{class_id:18} <- {base_id:14} слоты {unit['slots']}  навыки {skills}")

    path.write_text(json.dumps(units, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nвсего юнитов: {len(units)}")


if __name__ == "__main__":
    main()
