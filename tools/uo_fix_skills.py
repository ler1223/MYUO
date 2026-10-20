"""Исправление упрощений в навыках UO (data/skills.json) по текстам каталога.

    python -X utf8 tools/uo_fix_skills.py          # отчёт
    python -X utf8 tools/uo_fix_skills.py --write  # записать навыки, эффекты и переводы

Старый перенос (tools/uo_import.py) терял часть условий из описаний: «+N potency v. flying targets», состояния
после «Inflicts», воскрешение, подготовку («charging»), случайные цели, фей, день и ночь. Здесь каждое такое
исправление записано явно, по одному навыку. Инструмент идемпотентный: повторный запуск ничего не меняет.
Требует сначала tools/uo_fill_passives.py --write (общие эффекты uo_faerie и т. п.).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "tools"))

import uo_fill_passives as fp  # noqa: E402

DATA = BASE / "data"
CHARGE_SKILLS = ("arrow_rain", "blizzard", "circle_heal", "glacial_rain", "gravity", "radiant_heal", "trinity_rain",
                 "dragoon_dive")
RANDOM_AILMENTS = ["uo_poison", "uo_burn", "uo_freeze", "uo_stun", "uo_blind", "uo_guard_seal", "uo_passive_seal",
                   "uo_crit_seal"]


def tag(name: str) -> dict:
    return {"type": "has_tag", "tag": name}


def lacks(name: str) -> dict:
    return {"type": "lacks_tag", "tag": name}


def label(name: str) -> dict:
    return {"type": "has_label", "label": name}


def has(effect: str) -> dict:
    return {"type": "has_effect", "effect_id": effect}


def build(kit: fp.Kit, skills: dict) -> list[str]:
    """Правит словарь навыков на месте; возвращает список изменённых id."""
    before = copy.deepcopy(skills)
    fx = kit.stat_fx

    def potency(sid: str, add: float, target: dict | None = None, own: dict | None = None, scale: str = "") -> None:
        entry = {"add": add, "self_condition": own or fp.ALWAYS, "target_condition": target or fp.ALWAYS, "scale": scale}
        if entry not in skills[sid]["potency"]:
            skills[sid]["potency"].append(entry)

    def apply(sid: str, effect_id: str, to: str = "target", condition: dict | None = None) -> None:
        entry = fp.ap(effect_id, to, condition)
        if entry not in skills[sid]["applies"]:
            skills[sid]["applies"].append(entry)

    def extras(sid: str, **kw) -> None:
        skills[sid]["extras"].update(kw)

    def set_(sid: str, **kw) -> None:
        skills[sid].update(kw)

    def power(sid: str, value: float, index: int = 0) -> None:
        skills[sid]["parts"][index]["power"] = value

    # --- числа, расходившиеся с игрой ---
    power("aerial_smite", 1.5)
    extras("aerial_smite", hit_ap=1, hit_full_hp=True)
    set_("innocent_ray", ap_cost=2)
    power("row_smash", 1.2)
    skills["row_smash"]["extras"].pop("ignore_def", None)        # «против бронированных» — ignore_def_vs, а не всегда
    skills["heavy_smash"]["extras"].pop("ignore_def", None)
    set_("sanguine_attack", targets="enemy", parts=[fp.dmg(1.0)])
    extras("sanguine_attack", lifesteal=0.5)
    skills["pursuit_strike"].update(accuracy=100)
    power("pursuit_strike", 0.75)
    power("following_slash_strike", 1.0)
    power("knights_pursuit_strike", 0.75)
    power("weakness_hunter_strike", 1.5)
    extras("triple_counter_strike", random_targets=3)

    # --- воскрешение ---
    doomed = kit.effect("uo_doomed", "Погибнет в конце боя", tags=[], triggers=[
        fp.rx("battle_end", "any", "damage", "owner", amount=100, percent=True)])
    set_("animated_dead", targets="ally", parts=[], ap_restore=1, tags=["magic"])
    extras("animated_dead", revive=True, revive_pct=100)
    apply("animated_dead", doomed, "self")
    extras("reincarnation", revive=True)

    # --- состояния и условная сила ---
    for sid, eid in (("fire_slash", "uo_burn"), ("poison_slash", "uo_poison"), ("icicle_dart", "uo_freeze"),
                     ("inferno", "uo_burn"), ("assassins_nail", "uo_blind"), ("grisly_fire", "uo_burn"),
                     ("grisly_poison", "uo_poison")):
        apply(sid, eid)
    potency("assassins_nail", 0.5, own={"type": "is_night"})
    for sid, add in (("brutal_drive", 1.0), ("brutal_swing", 0.8), ("death_spin", 0.75), ("vicious_torment", 0.75)):
        potency(sid, add, target=label("ailment"))
    extras("vicious_torment", hit_pp=1, hit_label="ailment")
    extras("burning_edge", hit_pp=1, hit_label="burn")
    potency("checkmate", 1.0, target={"type": "hp_below", "value": 0.5001})
    potency("cursed_strike", 0.5, target=label("debuff"))
    extras("cursed_strike", ignore_def_label="debuff", ignore_def_label_share=1.0)
    potency("double_blast", 0.8, target=tag("flying"))
    potency("sonic_blast", 0.8, target=tag("flying"))
    potency("heavens_asunder", 0.3, target=tag("flying"))
    extras("heavens_asunder", hit_pp=2, hit_label="stun")
    potency("skyward_thrust", 0.5, target=tag("flying"))
    potency("dragoon_dive", 0.5, target=lacks("flying"))
    potency("icestorm", 0.5, target=has("uo_burn"))
    potency("grisly_fire", 0.5, target=has("uo_burn"))
    potency("grisly_poison", 0.5, target=has("uo_poison"))
    extras("inferno", hit_pp=1)
    extras("honed_slash", truestrike_buffed=True)
    extras("tempest_drive", desperate=0.5)
    extras("painful_smash", target_hp_damage=0.25)
    extras("natures_wrath", pp_drain=1, drain_vs=["cavalry"])
    set_("dark_mist", pp_restore=2)
    extras("leaping_slash", crit_ap=1)
    apply("leaping_slash", fx("crit_rate+30", stack=True), "self")

    # --- несколько целей ---
    for sid, n in (("dual_shot", 2), ("icicle_arrow", 2), ("magick_missile", 2), ("double_blast", 2), ("photon_arrow", 2),
                   ("skyward_thrust", 3), ("triple_shatter", 3)):
        extras(sid, random_targets=n)
    apply("photon_arrow", fx("phys_def-50%"))
    apply("photon_arrow", "uo_passive_seal", condition={"type": "is_day"})
    skills["photon_arrow"]["applies"] = [a for a in skills["photon_arrow"]["applies"]
                                         if not (a["effect_id"] == "uo_passive_seal" and a["condition"] == fp.ALWAYS)]

    # --- подготовка («charging») ---
    for sid in CHARGE_SKILLS:
        extras(sid, charge=True)
    set_("gravity", parts=[fp.dmg(0.0)])
    skills["gravity"]["parts"][0]["category"] = "pure"
    extras("gravity", target_hp_damage=0.5)
    kit.effect("uo_charging", "Подготовка навыка", flags=["charging", "passive_seal"], tags=[])

    # --- феи ---
    faerie = kit.effect("uo_faerie", "Призванная фея", tags=["faerie"], stack_rule="STACK", max_stacks=5)
    for sid in ("faerie_heal", "sylphic_wind", "boon_of_the_faeries_heal", "rage_of_the_faeries_strike"):
        apply(sid, faerie, "self")
    potency("elemental_roar", 0.3, scale="faeries")
    extras("elemental_roar", dismiss_effect=faerie)
    for sid in ("freezing_thrust", "thunderous_thrust"):
        potency(sid, 0.25, own=has(faerie))
    extras("primus_edge", full_hp_pp=1, full_hp_effect=faerie)

    # --- день и ночь ---
    apply("night_vision", "uo_next_sure", condition={"type": "is_night"})
    skills["night_vision"]["applies"] = [a for a in skills["night_vision"]["applies"]
                                         if not (a["effect_id"] == "uo_next_sure" and a["condition"] == fp.ALWAYS)]
    extras("row_resistance", day_area="all")

    # --- проклятия без урона, дебафф-усилитель, случайное состояние ---
    amp = kit.effect("uo_debuff_amp", "Дебаффы действуют в 1.5 раза сильнее", flags=["debuff_amp"], tags=["debuff"])
    for sid in ("compounding_curse", "defensive_curse", "offensive_curse", "passive_curse", "chaos_unending"):
        set_(sid, parts=[])
    apply("compounding_curse", amp)
    extras("chaos_unending", random_effects=RANDOM_AILMENTS)

    # --- мелочи ---
    glow = kit.effect("uo_glowing_light", "Сияние: точность +30 и защита от слепоты (не снимается)", tags=[],
                      modifiers=[{"stat": "accuracy", "op": "FLAT", "value": 30}], grants_tags=["immune_blind"])
    skills["glowing_light"]["extras"].pop("dispel", None)
    skills["glowing_light"]["applies"] = [fp.ap(glow)]
    conferral = kit.effect("uo_conferral_magic", "Магический урон в атаках союзника (+50 силы)", tags=["buff"],
                           attack_mods=[{"add_tags": [], "power_mult": 1.0, "accuracy_add": 0, "crit_add": 0,
                                         "add_scaling": [{"stat": "mag_atk", "coef": 0.5}], "skill_tag": None}])
    skills["mystic_conferral"]["applies"] = [fp.ap(conferral)]
    potency("limited_heal", 2.0, scale="few_allies")
    return [k for k in skills if skills[k] != before.get(k)]


def main(write: bool) -> int:
    def load(name):
        raw = (DATA / name).read_text(encoding="utf-8")
        return json.loads(raw), (2 if raw.startswith('{\n  "') else 1), raw.endswith("\n")

    skills, is_, ns = load("skills.json")
    effects, ie, ne = load("effects.json")
    ru, ir, nr = load("lang/ru.json")
    kit = fp.Kit(effects)
    changed = build(kit, skills)
    added = {k: v for k, v in kit.new_effects.items() if k not in effects}
    print(f"навыков изменено: {len(changed)}; новых эффектов: {len(added)}")
    for sid in changed:
        print("  ", sid)
    if not write:
        print("\n(без --write ничего не записано)")
        return 0
    effects.update(added)
    for key, value in kit.ru.items():
        ru.setdefault(key, value)
    for name, data, indent, nl in (("skills.json", skills, is_, ns), ("effects.json", effects, ie, ne),
                                   ("lang/ru.json", ru, ir, nr)):
        (DATA / name).write_text(json.dumps(data, ensure_ascii=False, indent=indent) + ("\n" if nl else ""),
                                 encoding="utf-8", newline="")
    print("\nзаписано")
    return 0


if __name__ == "__main__":
    sys.exit(main("--write" in sys.argv))
