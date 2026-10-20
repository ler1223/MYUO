"""Реализация пассивок-заглушек UO (data/passives.json: реакция restore_pp без числа).

    python -X utf8 tools/uo_fill_passives.py          # отчёт: что будет сделано
    python -X utf8 tools/uo_fill_passives.py --write  # записать пассивки, навыки-ответы, эффекты и переводы
    python -X utf8 tools/uo_fill_passives.py --write --redo   # пересобрать и уже сделанные пассивки таблицы

Для каждой пассивки в таблице TABLE явно записано, как она устроена: реакция (событие, чьё, действие, кому,
дополнительные шаги `then`), навык-ответ и эффекты. Тексты берутся из docs/uo/catalog/skills.json (строка условия
и строка действия из UcSkillList.fms), числа силы навыков-ответов (phys / mag / hits / accuracy) — оттуда же.
Трогаются только пассивки, которые всё ещё заглушки; ручные правки остальных не теряются.
Навыки-ответы называются <пассивка>_strike / _heal / _buff / _curse и имеют то же имя, что пассивка:
по имени tools/uo_battle/build.py находит внутреннее имя навыка и его эффекты в файлах игры.
УСТАРЕЛО после переноса пассивок в навыки: таблица применена, инструмент работает только со старым passives.json.
Пассивки, которые движок ещё не умеет, перечислены в DEFERRED и остаются заглушками.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from game.reactions import Reaction  # noqa: E402

DATA = BASE / "data"
CATALOG = BASE / "docs" / "uo" / "catalog" / "skills.json"
ALWAYS = {"type": "always"}
POINT_STATS = ("crit_rate", "guard_rate", "evasion", "accuracy", "crit_damage")   # «%» в UO — пункты, не доля
ALIASES = {"atk": ["phys_atk", "mag_atk"], "def": ["phys_def", "mag_def"]}
STAT_RU = {"phys_def": "физ. защита", "phys_atk": "физ. атака", "mag_def": "маг. защита", "mag_atk": "маг. атака",
           "crit_rate": "шанс крита", "crit_damage": "урон крита", "guard_rate": "шанс блока",
           "initiative": "инициатива", "evasion": "уклонение", "accuracy": "точность"}

# Пассивки, для которых в движке пока нет нужной механики (остаются заглушками, причина — в отчёте).
DEFERRED = {
    "celestial_light": "в игре это сюжетная заглушка («Unleash its true power…»), действие неизвестно",
}


TABLE_IDS: list[str] = []


class Kit:
    """Собирает новые эффекты, навыки и переводы; уже существующие id не трогает."""

    def __init__(self, effects: dict):
        self.effects = effects
        self.new_effects: dict[str, dict] = {}
        self.new_skills: dict[str, dict] = {}
        self.ru: dict[str, str] = {}

    # --- эффекты ---

    def effect(self, eid: str, ru: str, **fields) -> str:
        if eid in self.effects or eid in self.new_effects:
            return eid
        data = {"name": f"UO {eid[3:]}", "modifiers": [], "flags": [], "tags": ["buff"], "grants_tags": [],
                "attack_mods": [], "duration": None, "charges": None, "stack_rule": "REFRESH", "max_stacks": 1,
                "triggers": []}
        data.update(fields)
        self.new_effects[eid] = data
        self.ru[data["name"]] = ru
        return eid

    def stat_fx(self, *specs: str, stack: bool = False, duration: int | None = None, nxt: bool = False,
                grants: tuple[str, ...] = ()) -> str:
        """Бафф или дебафф статов: «phys_atk+20%», «initiative-10», «atk-20%». nxt — на одну следующую атаку."""
        mods, ids, label = [], [], []
        for spec in specs:
            m = re.fullmatch(r"(\w+?)([+-])(\d+(?:\.\d+)?)(%?)", spec)
            if m is None:
                raise ValueError(spec)
            stats = ALIASES.get(m.group(1), [m.group(1)])
            value = float(m.group(3)) * (1 if m.group(2) == "+" else -1)
            value = int(value) if value == int(value) else value
            percent = bool(m.group(4)) and not all(s in POINT_STATS for s in stats)
            for stat in stats:
                mods.append({"stat": stat, "op": "PERCENT_ADD" if percent else "FLAT",
                             "value": round(value / 100, 3) if percent else value})
            ids.append(f"{'_'.join(stats)}_{'m' if value < 0 else 'p'}{abs(value):g}{'pct' if percent else ''}")
            label.append(f"{' и '.join(STAT_RU[s] for s in stats)} {value:+g}{'%' if m.group(4) else ''}")
        eid = "uo_" + ("next_" if nxt else "") + "_".join(ids) + ("_stack" if stack else "") \
            + (f"_t{duration}" if duration else "")
        bad = all(m["value"] < 0 for m in mods)
        fields = {"modifiers": mods, "tags": ["debuff" if bad else "buff"],
                  "stack_rule": "STACK" if stack else "REFRESH", "max_stacks": 5 if stack else 1,
                  "duration": duration, "grants_tags": list(grants)}
        if nxt:      # заряд тратится на атаке; пустая поправка нужна, чтобы движок считал заряд
            fields.update(charges=1, attack_mods=[{"add_tags": [], "power_mult": 1.0, "add_scaling": [],
                                                   "accuracy_add": 0, "crit_add": 0, "skill_tag": None}])
        ru = ", ".join(label) + (" (следующая атака)" if nxt else "") + (" (до конца хода)" if duration else "")
        return self.effect(eid, ru, **fields)

    # --- навыки ---

    def skill(self, sid: str, name: str, **kw) -> str:
        self.new_skills[sid] = make_skill(name, **kw)
        return sid


def make_skill(name: str, targets: str = "enemy", area: str = "single", hits: int = 1, accuracy: int = 100,
               tags: tuple = ("melee",), parts: tuple = (), applies: tuple = (), extras: dict | None = None,
               potency: tuple = (), ap_restore: int = 0, pp_restore: int = 0) -> dict:
    return {"name": name, "ap_cost": 1, "pp_cost": 0, "targets": targets, "area": area, "hits": hits,
            "accuracy": accuracy, "tags": list(tags), "parts": list(parts), "bonus_vs": {},
            "ap_restore": ap_restore, "pp_restore": pp_restore, "applies": list(applies),
            "requires_self": ALWAYS, "requires_target": ALWAYS, "potency": list(potency), "extras": extras or {}}


def dmg(power: float, magic: bool = False) -> dict:
    return {"kind": "damage", "category": "magical" if magic else "physical", "power": power,
            "scaling": [{"stat": "mag_atk" if magic else "phys_atk", "coef": 1.0}], "tags": [], "weapon_tags": False}


def heal(power: float) -> dict:
    return {"kind": "heal", "category": "magical", "power": power,
            "scaling": [{"stat": "mag_atk", "coef": 1.0}], "tags": [], "weapon_tags": False}


def ap(effect_id: str, to: str = "target", condition: dict | None = None) -> dict:
    return {"effect_id": effect_id, "to": to, "condition": condition or ALWAYS}


def tag(name: str) -> dict:
    return {"type": "has_tag", "tag": name}


def rx(event: str, whose: str, action: str, to: str, **kw) -> dict:
    return {"event": event, "whose": whose, "action": action, "to": to, **kw}


def step(action: str, to: str = "owner", **kw) -> dict:
    return {"action": action, "to": to, **kw}



# Короткие записи триггеров.
def battle_start(action, to, **kw): return rx("battle_start", "self", action, to, **kw)
def battle_end(action, to, **kw): return rx("battle_end", "self", action, to, **kw)
def after_skill(action, to, **kw): return rx("skill_used", "self", action, to, **kw)
def before_skill(action, to, **kw): return rx("before_skill", "self", action, to, **kw)
def before_ally_attack(action, to, **kw): return rx("before_skill", "ally", action, to, **kw)
def after_ally_attack(action, to, **kw): return rx("skill_used", "ally", action, to, **kw)
def after_enemy_attack(action, to, **kw): return rx("skill_used", "enemy", action, to, **kw)
def ally_hit(action, to, **kw): return rx("attacked", "ally", action, to, outcome="landed", **kw)
def ally_attacked(action, to, **kw): return rx("attacked", "ally", action, to, **kw)
def ally_targeted(action, to, **kw): return rx("targeted", "ally", action, to, **kw)
def self_targeted(action, to="owner", **kw): return rx("targeted", "self", action, to, **kw)
def self_attacked(action, to="owner", **kw): return rx("attacked", "self", action, to, **kw)
def ally_debuffed(action, to, **kw): return rx("effect_applied", "ally", action, to, effect_label="debuff", **kw)
def self_debuffed(action, to="owner", **kw): return rx("effect_applied", "self", action, to, effect_label="debuff", **kw)


def build(kit: Kit, cat: dict) -> dict[str, tuple[dict, str | None]]:
    """id пассивки -> (реакция, примечание). Новые навыки и эффекты складываются в kit."""
    fx, sk = kit.stat_fx, kit.skill
    use = lambda sid, to: dict(action="use_skill", skill_id=sid, to=to)   # noqa: E731
    N = {}

    def put(pid: str, reaction: dict, note: str = "") -> None:
        N[pid] = (reaction, note)

    def num(pid: str, key: str, default: float) -> float:
        value = cat[pid][key]
        return value / 100 if value else default

    # ---- начало боя: баффы себе и союзникам ----
    stun_guard = kit.effect("uo_immune_stun_guard_rate_p20", "Иммунитет к оглушению, шанс блока +20",
                            modifiers=[{"stat": "guard_rate", "op": "FLAT", "value": 20}], grants_tags=["immune_stun"])
    sid = sk("dawn_horn_buff", "Dawn Horn", targets="ally", area="all", applies=[ap(stun_guard)])
    put("dawn_horn", battle_start(**use(sid, "owner")))

    pierce = kit.effect("uo_guard_rate_p100_nullify_pierce", "Шанс блока +100, пронзающие удары не наносят урона",
                        modifiers=[{"stat": "guard_rate", "op": "FLAT", "value": 100}], grants_tags=["nullify_pierce"])
    sid = sk("honed_shield_buff", "Honed Shield", targets="ally", applies=[ap(pierce)])
    put("honed_shield", battle_start(**use(sid, "allies")))

    put("bunker_stance", battle_start("apply_effect", "owner",
                                      effect_id=fx("initiative+30", "phys_def+40%", "guard_rate+40")))
    put("impetus_stance", battle_start("apply_effect", "owner", effect_id=fx("atk+50%"),
                                       then=[step("restore_ap", amount=1)]))
    put("war_cry", battle_start("apply_effect", "owner", effect_id=fx("phys_atk+20%")))
    put("magick_shell", battle_start("apply_effect", "owner", effect_id="uo_negate_3"))
    put("darkness_armor", battle_start("apply_effect", "owner", effect_id="uo_negate_6"))

    sid = sk("quick_action_buff", "Quick Action", targets="ally", applies=[ap(fx("initiative+15", duration=1))])
    put("quick_action", battle_start(**use(sid, "allies")), "союзник выбирается порядком целей UO")
    for pid, name in (("hastened_action", "Hastened Action"), ("hastened_cast", "Hastened Cast")):
        sid = sk(f"{pid}_buff", name, targets="ally", applies=[ap(fx("initiative+1000", duration=1))])
        put(pid, battle_start(**use(sid, "allies")), "«максимум инициативы» — +1000 до конца хода")

    put("provoking_wall", battle_start("apply_effect", "owner", effect_id="uo_taunt",
                                       then=[step("apply_effect", effect_id="uo_negate_physical")]))
    evade2 = kit.effect("uo_evade_2", "Уклонение от двух ударов", flags=["evade"], charges=2)
    put("scornful_dead", battle_start("apply_effect", "owner", effect_id="uo_taunt",
                                      then=[step("apply_effect", effect_id=evade2)]))
    sid = sk("hastened_curse_curse", "Hastened Curse", applies=[ap(fx("initiative-30"))], tags=("magic",))
    put("hastened_curse", battle_start(**use(sid, "enemies")))
    sid = sk("eye_of_the_warrior_princess_curse", "Eye of the Warrior Princess", area="all",
             applies=[ap(fx("atk-20%", "initiative-10"))])
    put("eye_of_the_warrior_princess", battle_start(**use(sid, "enemies")))
    sid = sk("ominous_wall_buff", "Ominous Wall", targets="ally", area="all", applies=[ap("uo_negate_one")])
    put("ominous_wall", battle_start(**use(sid, "owner")))

    stun_free = kit.effect("uo_immune_stun", "Иммунитет к оглушению", grants_tags=["immune_stun"])
    row = dict(to_area="row")
    put("heavy_alignment", battle_start("tiered", "owner", label="ally:armored", then=[
        step("apply_effect", "side", effect_id=fx("guard_rate+20"), **row),
        step("apply_effect", "side", effect_id=stun_free, **row),
        step("apply_effect", "side", effect_id=fx("def+20%"), **row)]),
        "ряд владельца; считаются бронированные союзники отряда")
    put("aerial_alignment", battle_start("tiered", "owner", label="ally:flying", then=[
        step("apply_effect", "side", effect_id=fx("crit_rate+20"), **row),
        step("apply_effect", "side", effect_id=fx("accuracy+20"), **row),
        step("apply_effect", "side", effect_id=fx("atk+20%"), **row)]),
        "ряд владельца; считаются летающие союзники отряда")
    put("united_front", battle_start("tiered", "owner", label="surplus", then=[
        step("apply_effect", "side", effect_id=fx("initiative+30")),
        step("apply_effect", "side", effect_id=fx("def+50%")),
        step("apply_effect", "side", effect_id="uo_negate_5")]),
        "ступень = на сколько врагов больше, чем союзников")
    sid = sk("wolf_pack_buff", "Wolf Pack", targets="ally", area="all",
             applies=[ap(fx("phys_atk+20%")), ap(fx("crit_rate+50"), condition=tag("bestral"))])
    put("wolf_pack", battle_start(**use(sid, "owner")))
    sid = sk("bears_den_buff", "Bear's Den", targets="ally", area="all",
             applies=[ap(fx("phys_def+20%")), ap(fx("guard_rate+50"), condition=tag("bestral"))])
    put("bears_den", battle_start(**use(sid, "owner")))
    put("reheal", battle_start("apply_effect", "side", effect_id="uo_regen", **row))
    sid = sk("hastened_heal_heal", "Hastened Heal", targets="ally", area="all", tags=("magic",), parts=[heal(0.5)],
             applies=[ap("uo_regen", condition={"type": "is_day"})])
    put("hastened_heal", battle_start(**use(sid, "owner")), "регенерация только днём")

    # ---- начало боя: удары первыми ----
    sid = sk("rapid_shot_strike", "Rapid Shot", tags=("ranged",), parts=[dmg(num("rapid_shot", "phys", 1.0))],
             applies=[ap("uo_stun")])
    put("rapid_shot", battle_start(**use(sid, "enemies")))
    sid = sk("hastened_shatter_strike", "Hastened Shatter", tags=("ranged",),
             parts=[dmg(num("hastened_shatter", "phys", 1.5))], applies=[ap(fx("phys_def-50%"))])
    put("hastened_shatter", battle_start(**use(sid, "enemies")))
    sid = sk("provoking_strike_strike", "Provoking Strike", parts=[dmg(num("provoking_strike", "phys", 0.5))],
             applies=[ap("uo_taunt", "self")])
    put("provoking_strike", battle_start(**use(sid, "enemies")))
    sid = sk("ground_punisher_strike", "Ground Punisher", tags=("ranged",), area="all",
             parts=[dmg(num("ground_punisher", "phys", 0.5))], extras={"ap_drain": 1, "pp_drain": 1})
    put("ground_punisher", battle_start(**use(sid, "enemies")))

    # ---- конец боя ----
    sid = sk("fire_burst_strike", "Fire Burst", tags=("magic",), parts=[dmg(num("fire_burst", "mag", 1.0), True)],
             extras={"spread_effect": "uo_burn"})
    put("fire_burst", battle_end(**use(sid, "enemies")))
    sid = sk("poison_burst_strike", "Poison Burst", tags=("magic",), parts=[dmg(num("poison_burst", "mag", 1.0), True)],
             extras={"spread_effect": "uo_poison"})
    put("poison_burst", battle_end(**use(sid, "enemies")))
    sid = sk("judgment_strike", "Judgment", area="all", tags=("ranged",), parts=[dmg(num("judgment", "phys", 1.0))],
             extras={"ignore_def": 0.5, "lifesteal": 1.0})
    put("judgment", battle_end(**use(sid, "enemies")))
    put("party_aid", battle_end("heal", "side", amount=25, percent=True))

    # ---- после своего навыка ----
    sid = sk("daemonic_pact_pact", "Daemonic Pact", targets="self", ap_restore=1, extras={"hp_cost": 0.25},
             tags=("magic",))
    put("daemonic_pact", after_skill(**use(sid, "owner")))
    put("diurnal_impetus", after_skill("apply_effect", "owner", effect_id=fx("mag_atk+20%"), then=[
        step("restore_ap", amount=1, self_condition={"type": "is_day"})]))
    put("nocturnal_impetus", after_skill("apply_effect", "owner", effect_id=fx("mag_atk+20%"), then=[
        step("restore_ap", amount=1, self_condition={"type": "is_night"})]))
    put("blade_dance", after_skill("apply_effect", "owner", effect_id=fx("crit_rate+20", "crit_damage+20", stack=True)))
    sid = sk("tailwind_buff", "Tailwind", targets="ally", area="row", applies=[
        ap(fx("initiative+10", stack=True)), ap(fx("initiative+10", stack=True), condition=tag("flying"))])
    put("tailwind", after_skill(**use(sid, "owner")), "летающим вдвое: второй такой же стак")
    put("recast", after_skill("repeat_skill", "owner", attack_tags=["magical"]))
    put("grave_impetus", rx("died", "ally", "restore_ap", "owner", amount=1))
    put("inner_balance", before_skill("dispel", "owner", label="debuff",
                                      then=[step("apply_effect", effect_id="uo_next_sure_crit")]))
    put("aerial_wing", before_skill("apply_effect", "owner", effect_id="uo_next_sure", then=[
        step("apply_effect", effect_id=fx("atk+20%", nxt=True), self_condition={"type": "hp_above", "value": 1.0})]))

    # ---- на действия союзников ----
    put("passive_gift", rx("passive_used", "ally", "restore_pp", "subject", amount=1))
    put("quick_impetus", after_ally_attack("restore_ap", "subject", amount=2),
        "«сходить ещё раз» заменено двумя AP союзнику")
    free = kit.effect("uo_free_action", "Действие без траты AP", flags=["free_action"], charges=1)
    put("reinforce", before_ally_attack("apply_effect", "subject", effect_id=free))

    # ---- контратаки ----
    sid = sk("counter_strike", "Counter", parts=[dmg(num("counter", "phys", 1.5))])
    put("counter", after_enemy_attack(**use(sid, "actor")))
    sid = sk("vanitas_strike", "Vanitas", tags=("magic",), parts=[dmg(num("vanitas", "mag", 0.5), True)],
             applies=[ap("uo_blind"), ap("uo_poison")])
    put("vanitas", ally_hit(**use(sid, "actor")))
    sid = sk("banishing_counter_strike", "Banishing Counter", tags=("ranged",),
             parts=[dmg(num("banishing_counter", "phys", 1.5))], extras={"dispel": ["buff"]})
    put("banishing_counter", after_enemy_attack(**use(sid, "actor")))
    sid = sk("phantom_counter_strike", "Phantom Counter", parts=[dmg(num("phantom_counter", "phys", 1.0))],
             applies=[ap("uo_burn")], extras={"dispel": ["buff"]})
    put("phantom_counter", after_enemy_attack(**use(sid, "actor")))
    sid = sk("vanquish_strike", "Vanquish", area="row", tags=("ranged",), parts=[dmg(num("vanquish", "phys", 1.0))],
             extras={"ap_drain": 2})
    put("vanquish", after_enemy_attack(**use(sid, "actor")), "AP −2 получают все задетые, а не только ослабленные")
    sid = sk("magick_burst_strike", "Magick Burst", area="all", tags=("magic",),
             parts=[dmg(num("magick_burst", "mag", 1.0), True)], applies=[ap(fx("initiative-10"))])
    put("magick_burst", after_enemy_attack(**use(sid, "actor")))
    sid = sk("phantom_kick_strike", "Phantom Kick", area="row", tags=("ranged",),
             parts=[dmg(num("phantom_kick", "phys", 0.5))], applies=[ap("uo_stun"), ap("uo_passive_seal")])
    put("phantom_kick", after_enemy_attack(**use(sid, "actor")))
    sid = sk("poison_touch_curse", "Poison Touch", tags=("magic",), applies=[ap("uo_poison"), ap(fx("atk-20%"))])
    put("poison_touch", ally_hit(**use(sid, "actor")))
    sid = sk("venom_touch_curse", "Venom Touch", area="row", tags=("magic",),
             applies=[ap("uo_poison"), ap(fx("atk-25%"))])
    put("venom_touch", after_enemy_attack(**use(sid, "actor")))

    # ---- смена строя: ответ на атаку по союзнику ----
    for pid, name, kind in (("phalanx_shift", "Phalanx Shift", "cavalry"), ("aerial_shift", "Aerial Shift", "flying")):
        sid = sk(f"{pid}_buff", name, targets="ally", area="row", applies=[
            ap(fx("atk+20%"), condition=tag(kind)), ap(fx("crit_rate+40"), condition=tag(kind))])
        put(pid, ally_attacked(**use(sid, "subject")), "ряд атакованного союзника")

    # ---- ответ на ослабление ----
    put("self_care", self_debuffed("dispel", "owner", label="debuff"))
    put("cursed_impetus", self_debuffed("restore_ap", "owner", amount=1))
    put("abyssal_miasma", self_debuffed("dispel", "owner", label="debuff",
                                        then=[step("apply_effect", effect_id="uo_negate_one")]))
    put("mirror_weakness", self_debuffed("reflect_debuffs", "actor"))
    for pid, eid in (("poison_cure", "uo_poison"), ("fire_cure", "uo_burn"), ("freeze_cure", "uo_freeze"),
                     ("stun_cure", "uo_stun"), ("blind_cure", "uo_blind"), ("guard_cure", "uo_guard_seal"),
                     ("passive_cure", "uo_passive_seal")):
        r = rx("effect_applied", "ally", "remove_effect", "subject", effect_filter=eid, effect_id=eid,
               then=[step("heal", "subject", amount=10, percent=True)])
        put(pid, r)
    put("sacred_cure", ally_debuffed("dispel", "side", label="debuff", to_area="row",
                                     then=[step("apply_effect", "side", effect_id="uo_immune_debuff", to_area="row")]))
    sid = sk("relic_heal_heal", "Relic Heal", targets="ally", tags=("magic",), parts=[heal(num("relic_heal", "mag", 1.0))],
             applies=[ap("uo_regen")])
    put("relic_heal", ally_hit(**use(sid, "subject")))

    # ---- преследования ----
    sid = sk("aerial_pursuit_strike", "Aerial Pursuit", parts=[dmg(num("aerial_pursuit", "phys", 1.0))])
    put("aerial_pursuit", after_ally_attack(**use(sid, "target"), subject_condition=tag("flying")))
    sid = sk("banishing_pursuit_strike", "Banishing Pursuit", tags=("ranged",),
             parts=[dmg(num("banishing_pursuit", "phys", 0.75))], extras={"dispel": ["buff"]})
    put("banishing_pursuit", after_ally_attack(**use(sid, "target")))
    sid = sk("wide_pursuit_strike", "Wide Pursuit", area="row", parts=[dmg(num("wide_pursuit", "phys", 0.75))])
    put("wide_pursuit", after_ally_attack(**use(sid, "target")))
    sid = sk("shattering_pursuit_strike", "Shattering Pursuit", area="column",
             parts=[dmg(num("shattering_pursuit", "phys", 0.75))], applies=[ap(fx("phys_def-25%"))])
    put("shattering_pursuit", after_ally_attack(**use(sid, "target")))
    sid = sk("sanguine_pursuit_strike", "Sanguine Pursuit", tags=("ranged",),
             parts=[dmg(num("sanguine_pursuit", "phys", 1.0))],
             extras={"lifesteal": 0.5, "hit_pp": 1, "hit_label": "ailment"})
    put("sanguine_pursuit", after_ally_attack(**use(sid, "target")))
    sid = sk("guard_hunter_strike", "Guard Hunter", tags=("magic",), parts=[dmg(num("guard_hunter", "mag", 1.0), True)],
             extras={"ignore_def": 0.3})
    put("guard_hunter", rx("attacked", "enemy", "use_skill", "subject", outcome="guarded", skill_id=sid))

    # ---- до атаки врага ----
    reflect = kit.effect("uo_reflect_magic", "Отражение магии", flags=["reflect:magical"], charges=1)
    put("reflect_magick", rx("before_skill", "enemy", "apply_effect", "actor", attack_tags=["magical"],
                             effect_id=reflect))
    put("cursed_gaol", rx("before_skill", "enemy", "apply_effect", "actor", effect_id=fx("atk-50%"),
                          then=[step("apply_effect", "actor", effect_id="uo_crit_seal")]))
    sid = sk("shining_light_curse", "Shining Light", area="row", tags=("magic",), applies=[ap("uo_blind")])
    put("shining_light", rx("before_skill", "enemy", "use_skill", "actor", skill_id=sid))

    # ---- до атаки союзника: лечение, баффы ----
    sid = sk("preemptive_heal_heal", "Preemptive Heal", targets="ally", tags=("magic",),
             parts=[heal(num("preemptive_heal", "mag", 1.0))])
    put("preemptive_heal", ally_targeted(**use(sid, "subject")))
    sid = sk("holy_breath_heal", "Holy Breath", targets="ally", tags=("magic",),
             parts=[heal(num("holy_breath", "mag", 0.5))],
             extras={"dispel": ["ailment"], "hit_pp": 1, "hit_label": "ailment"})
    put("holy_breath", before_ally_attack(**use(sid, "subject")))
    put("sorcerous_connection", before_ally_attack("apply_effect", "subject", attack_tags=["magical"],
                                                   effect_id=fx("mag_atk+50%", nxt=True),
                                                   then=[step("apply_effect", effect_id=fx("mag_atk+50%", nxt=True))]))
    put("powerful_call", before_ally_attack("apply_effect", "subject", effect_id=fx("phys_atk+30%", nxt=True)))
    insp = fx("atk+30%", "crit_damage+50", "accuracy+50", nxt=True)
    put("inspiration", before_ally_attack("apply_effect", "subject", effect_id=insp))
    put("wide_inspiration", before_ally_attack("apply_effect", "side", effect_id=insp, to_area="row"),
        "ряд владельца")
    for pid, status in (("flame_conferral", "burn"), ("ice_conferral", "freeze"),
                        ("thunderous_conferral", "stun"), ("dark_conferral", "blind")):
        nxt = kit.effect(f"uo_next_magic_{status}", f"Магия и состояние в следующей атаке ({status})",
                         charges=1, attack_mods=[{"add_tags": [], "power_mult": 1.0, "accuracy_add": 0, "crit_add": 0,
                                                  "add_scaling": [{"stat": "mag_atk", "coef": 0.5}],
                                                  "skill_tag": None, "on_hit": [f"uo_{status}"]}])
        put(pid, before_ally_attack("apply_effect", "subject", attack_tags=["physical"], effect_id=nxt))
    vamp = kit.effect("uo_next_vampire", "Вампиризм следующей атаки (50%)", charges=1,
                      attack_mods=[{"add_tags": [], "power_mult": 1.0, "add_scaling": [], "accuracy_add": 0,
                                    "crit_add": 0, "skill_tag": None, "lifesteal": 0.5}])
    put("sanguine_conferral", before_ally_attack("apply_effect", "subject", attack_tags=["physical"],
                                                 effect_id="uo_next_magic",
                                                 then=[step("apply_effect", "subject", effect_id=vamp)]),
        "лечится владелец пассивки — источник эффекта")

    # ---- до атаки по союзнику ----
    put("sylphic_barrier", ally_targeted("apply_effect", "subject", attack_tags=["ranged"], effect_id="uo_evade_one"))
    put("grant_evade", ally_targeted("apply_effect", "subject", effect_id="uo_evade_one"))
    r25 = kit.effect("uo_reduce_25", "Урон −25% от одной атаки", flags=["reduce:25"], charges=1)
    r50 = kit.effect("uo_reduce_50", "Урон −50% от одной атаки", flags=["reduce:50"], charges=1)
    put("quick_barrier", ally_targeted("apply_effect", "subject", effect_id=r50))
    put("protection", ally_targeted("apply_effect", "side", effect_id=r50, to_area="row"), "ряд владельца")
    put("circle_barrier", ally_targeted("apply_effect", "side", effect_id=r25, limit="round"))
    for pid in ("holy_barrier", "saints_barrier"):
        put(pid, ally_targeted("apply_effect", "subject", effect_id=r50, limit="round",
                               then=[step("apply_effect", "subject", effect_id="uo_immune_debuff")]))
    put("mighty_shield", ally_targeted("apply_effect", "subject", effect_id="uo_negate_one"))
    put("enduring_cover", ally_targeted("cover", "owner", effect_id="uo_guard_heavy",
                                        then=[step("apply_effect", effect_id="uo_endure")]))
    put("healing_cover", ally_targeted("cover", "owner", effect_id="uo_guard_medium",
                                       then=[step("heal", "subject", amount=25, percent=True)]))
    put("advance_cover", ally_targeted("cover", "owner", effect_id="uo_guard_medium",
                                       then=[step("restore_ap", amount=1)]))
    put("evil_cover", ally_targeted("cover", "owner", effect_id="uo_guard_medium",
                                    then=[step("restore_pp", "subject", amount=-1), step("restore_pp", amount=1)]))
    put("sacrifice", ally_targeted("cover", "owner", then=[step("restore_pp", amount=2)]))

    # ---- до атаки по себе / после неё ----
    put("toughness", self_targeted("apply_effect", effect_id="uo_endure"))
    put("painbringer", self_targeted("apply_effect", effect_id=fx("atk+20%", "initiative+10", stack=True),
                                     then=[step("restore_ap", amount=1)]))
    put("nimble_fighter", self_attacked(outcome="missed", action="apply_effect",
                                        effect_id=fx("phys_atk+20%", "crit_damage+30", stack=True)))
    put("guarding_fighter", self_attacked(outcome="guarded", action="apply_effect",
                                          effect_id=fx("phys_atk+20%", "crit_damage+30", stack=True)))
    put("vengeful_impetus", self_attacked(action="restore_ap", amount=1))
    put("guarding_impetus", self_attacked(outcome="guarded", action="restore_ap", amount=1))
    put("undead_wall", self_targeted("apply_effect", attack_tags=["physical"], effect_id="uo_negate_physical",
                                     then=[step("apply_effect", effect_id=fx("initiative+20"))]))
    put("invincible", self_targeted("apply_effect", effect_id="uo_negate_one"))
    put("phantom_step", self_targeted("apply_effect", effect_id="uo_evade_one"))
    put("dynamic_glide", self_targeted("apply_effect", effect_id="uo_evade_one",
                                       then=[step("apply_effect", effect_id=fx("phys_atk+20%"))]))
    put("dark_step", self_targeted("apply_effect", effect_id="uo_evade_one",
                                   then=[step("apply_effect", effect_id=fx("evasion+25"))]))
    put("magick_conversion", self_targeted("apply_effect", attack_tags=["magical"], effect_id="uo_negate_magic",
                                           then=[step("restore_pp", amount=2)]))
    sid = sk("lifeshare_gift", "Lifeshare", targets="ally", tags=("magic",), extras={"give_hp": 0.5})
    put("lifeshare", ally_hit(**use(sid, "subject")))

    # ---- исправленные упрощения (шаг 5); навыки pursuit_strike и triple_counter_strike правит uo_fix_skills.py ----
    instant = kit.effect("uo_instant_charge", "Следующая подготовка пропускается", flags=["instant_charge"], charges=1)
    put("hastened_charge", battle_start("apply_effect", "owner", effect_id=instant))
    seal = kit.effect("uo_next_guard_seal", "Следующая атака накладывает печать блока", charges=1,
                      attack_mods=[{"add_tags": [], "power_mult": 1.0, "add_scaling": [], "accuracy_add": 0,
                                    "crit_add": 0, "skill_tag": None, "on_hit": ["uo_guard_seal"]}])
    put("binding_guard", before_skill("apply_effect", "owner", effect_id=seal))
    put("sanguine_arts", before_skill("apply_effect", "owner", effect_id=vamp))
    put("deflect", self_targeted("apply_effect", attack_tags=["melee"], effect_id="uo_negate_melee",
                                 then=[step("apply_effect", effect_id=fx("evasion+20", stack=True))]))
    discharge = kit.effect("uo_discharge", "Сила следующей атаки +25% за каждый снятый бафф", charges=1,
                           stack_rule="STACK", max_stacks=8, tags=[],
                           attack_mods=[{"add_tags": [], "power_mult": 1.0, "add_scaling": [], "accuracy_add": 0,
                                         "crit_add": 0, "skill_tag": None, "power_per_stack": 0.25}])
    put("discharge", before_skill("consume_buffs", "owner", effect_id=discharge))
    undying = kit.effect("uo_undying_will", "Сила следующей атаки растёт с потерей HP (до +100)", charges=1, tags=[],
                         attack_mods=[{"add_tags": [], "power_mult": 1.0, "add_scaling": [], "accuracy_add": 0,
                                       "crit_add": 0, "skill_tag": None, "power_by_missing_hp": 1.0}])
    put("undying_will", before_skill("apply_effect", "owner", effect_id=undying,
                                     then=[step("apply_effect", effect_id="uo_endure")]))
    put("berserk", before_skill("restore_pp", "owner", amount=-99,
                                then=[step("restore_ap", amount=1), step("apply_effect", effect_id="uo_endure")]))
    put("quick_cast", battle_start("apply_effect", "owner",
                                   effect_id=fx("initiative+1000", "crit_rate-50", duration=1)),
        "«максимум инициативы» — +1000 до конца хода")
    qc = kit.effect("uo_next_atk_m20pct_crit_seal", "Атака −20% и печать крита на одну атаку", flags=["crit_seal"],
                    charges=1, tags=["debuff"],
                    modifiers=[{"stat": "phys_atk", "op": "PERCENT_ADD", "value": -0.2},
                               {"stat": "mag_atk", "op": "PERCENT_ADD", "value": -0.2}],
                    attack_mods=[{"add_tags": [], "power_mult": 1.0, "add_scaling": [], "accuracy_add": 0,
                                  "crit_add": 0, "skill_tag": None}])
    put("quick_curse", rx("before_skill", "enemy", "apply_effect", "actor", limit="round", effect_id=qc))
    pct = lambda power: {"kind": "heal_pct", "category": "magical", "power": power, "scaling": [],   # noqa: E731
                         "tags": [], "weapon_tags": False}
    sid = sk("first_aid_heal", "First Aid", targets="ally", tags=("magic",), parts=[pct(0.25)])
    put("first_aid", battle_end(**use(sid, "owner")), "союзник выбирается порядком целей UO")
    sid = sk("medical_aid_heal", "Medical Aid", targets="ally", area="row", tags=("magic",), parts=[pct(0.15)],
             potency=[{"add": 0.15, "self_condition": ALWAYS, "scale": "",
                       "target_condition": {"type": "hp_below", "value": 0.5001}}])
    put("medical_aid", battle_end(**use(sid, "owner")), "ряд владельца; вдвое при HP цели 50% и ниже")
    put("wing_rest", battle_end("heal", "owner", amount=25, percent=True, then=[
        step("heal", amount=25, percent=True, self_condition={"type": "has_label", "label": "ailment"})]))
    put("nocturnal_rest", after_skill("heal", "owner", amount=30, percent=True, then=[
        step("heal", amount=30, percent=True, self_condition={"type": "is_night"})]))
    put("nocturnal_evade", self_targeted("apply_effect", effect_id="uo_evade_one", then=[
        step("restore_pp", amount=1, self_condition={"type": "is_night"})]))
    put("diurnal_guard", self_targeted("apply_effect", attack_tags=["physical"], effect_id="uo_guard_medium", then=[
        step("restore_pp", amount=1, self_condition={"type": "is_day"})]))
    sid = sk("nocturnal_strike_strike", "Nocturnal Strike", parts=[dmg(num("nocturnal_strike", "phys", 1.5))])
    put("nocturnal_strike", battle_start(**use(sid, "enemies"), then=[
        step("restore_pp", amount=1, self_condition={"type": "is_night"})]))
    sid = sk("parting_resurrection_revive", "Parting Resurrection", targets="ally", tags=("magic",),
             extras={"revive": True})
    put("parting_resurrection", battle_end(**use(sid, "owner")))
    sid = sk("passive_miracle_heal", "Passive Miracle", targets="ally", tags=("magic",), pp_restore=1,
             parts=[heal(num("passive_miracle", "mag", 0.5))])
    put("passive_miracle", rx("passive_used", "ally", "use_skill", "subject", skill_id=sid))
    put("restore", rx("passive_used", "ally", "restore_pp", "subject", amount=1))
    put("quick_cure", ally_debuffed("dispel", "subject", label="debuff", then=[
        step("apply_effect", "subject", effect_id="uo_immune_debuff")]))
    kit.effect("uo_faerie", "Призванная фея", tags=["faerie"], stack_rule="STACK", max_stacks=5)
    put("elemental_impetus", after_skill("restore_ap", "owner", amount=1, then=[
        step("apply_effect", effect_id="uo_faerie")]))
    # ---- классовые пассивки с неточной реализацией старого импорта ----
    put("bulk_up", self_attacked(outcome="landed", action="heal", amount=40, percent=True))
    sid = sk("lifesaver_heal", "Lifesaver", targets="self", tags=("magic",), parts=[heal(num("lifesaver", "mag", 0.5))])
    put("lifesaver", self_targeted(**use(sid, "owner"), then=[step("apply_effect", effect_id="uo_endure")]))
    put("royal_guard", self_targeted("apply_effect", attack_tags=["physical"], effect_id="uo_guard_medium", then=[
        step("heal", amount=10, percent=True)]), "сколько HP возвращает Royal Guard, в тексте игры не указано (%s) — взято 10%")
    sid = sk("healing_pursuit_heal", "Healing Pursuit", targets="ally", tags=("magic",),
             parts=[heal(num("healing_pursuit", "mag", 0.5))])
    put("healing_pursuit", rx("healed", "ally", "use_skill", "subject", skill_id=sid),
        "лечение выше максимума HP (до 150%) не поддерживается")
    sid = sk("healing_hunter_strike", "Healing Hunter", extras={"ignore_def": 0.3},
             parts=[dmg(num("healing_hunter", "phys", 1.0))])
    put("healing_hunter", rx("skill_used", "enemy", "use_skill", "actor", attack_tags=["healing"], skill_id=sid))
    heavy = lambda tag_name, extra: put(f"{tag_name}_guard", self_targeted(   # noqa: E731
        "apply_effect", attack_tags=["physical"], effect_id="uo_guard_medium", then=[
            step("apply_effect", effect_id="uo_guard_heavy", actor_condition=tag(tag_name)),
            step("restore_pp", amount=1, actor_condition=tag(tag_name))]), extra)
    heavy("aerial", "против летающих — тяжёлый блок и +1 PP (число в игре не указано)")
    heavy("bestral", "против зверей — тяжёлый блок и +1 PP (число в игре не указано)")
    heavy("cavalry", "против кавалерии — тяжёлый блок и +1 PP (число в игре не указано)")
    put("nocturnal_guard", self_targeted("apply_effect", attack_tags=["physical"], effect_id="uo_guard_medium", then=[
        step("restore_pp", amount=1, self_condition={"type": "is_night"})]),
        "число PP в игре не указано (%s) — взято 1")
    N["demonic_pact"] = N["daemonic_pact"]          # то же умение под старым написанием имени
    return N


def main(write: bool, redo: bool = False) -> int:
    if not (DATA / "passives.json").exists():
        print("data/passives.json больше нет: пассивки — навыки kind: passive в data/skills.json "
              "(docs/uo/ABILITIES_DESIGN.md). Таблица TABLE осталась как описание и применена к данным.")
        return 1
    def load(name):
        raw = (DATA / name).read_text(encoding="utf-8")
        return json.loads(raw), (2 if raw.startswith('{\n  "') else 1), raw.endswith("\n")

    def save(name, data, indent, newline):
        (DATA / name).write_text(json.dumps(data, ensure_ascii=False, indent=indent) + ("\n" if newline else ""),
                                 encoding="utf-8", newline="")

    passives, ip, np_ = load("passives.json")
    skills, is_, ns = load("skills.json")
    effects, ie, ne = load("effects.json")
    ru, ir, nr = load("lang/ru.json")
    catalog = {x["id"]: x for x in json.loads(CATALOG.read_text(encoding="utf-8"))["skills"]}
    kit = Kit(effects)
    table = build(kit, catalog)
    TABLE_IDS.extend(table)
    stubs = [k for k, v in passives.items()
             if v["reaction"]["action"] == "restore_pp" and not v["reaction"].get("amount")]
    if redo:                                # пересобрать и уже сделанные пассивки этой таблицы (после правки таблицы)
        stubs = stubs + [k for k in TABLE_IDS if k not in stubs and k in passives]

    done, left, skipped = [], [], []
    for pid in stubs:
        if pid in DEFERRED:
            left.append((pid, DEFERRED[pid]))
            continue
        if pid not in table:
            left.append((pid, "нет в таблице"))
            continue
        reaction, note = table[pid]
        try:
            normal = Reaction.from_dict(reaction).to_dict()
        except Exception as error:                      # ошибка в таблице — сразу видно, какая пассивка
            raise SystemExit(f"{pid}: {error}")
        passives[pid]["reaction"] = normal
        done.append((pid, note))
    extra = [p for p in table if p not in stubs]

    used_skills = {r["skill_id"] for pid, _ in done for r in [passives[pid]["reaction"]] if r.get("skill_id")}
    added_skills = {k: v for k, v in kit.new_skills.items() if k in used_skills and (redo or k not in skills)}
    added_effects = {k: v for k, v in kit.new_effects.items() if k not in effects}
    print(f"заглушек было: {len(stubs)}; реализовано: {len(done)}; осталось: {len(left)}")
    print(f"новых навыков-ответов: {len(added_skills)}; новых эффектов: {len(added_effects)}")
    for pid, why in left:
        print(f"  осталась заглушкой: {pid} — {why}")
    if extra:
        print("  в таблице, но уже не заглушки (пропущены):", ", ".join(extra))
    for pid, note in done:
        if note:
            print(f"  примечание {pid}: {note}")
    if not write:
        print("\n(без --write ничего не записано)")
        return 0
    skills.update(added_skills)
    effects.update(added_effects)
    for key, value in kit.ru.items():
        if key not in ru:
            ru[key] = value
    save("passives.json", passives, ip, np_)
    save("skills.json", skills, is_, ns)
    save("effects.json", effects, ie, ne)
    save("lang/ru.json", ru, ir, nr)
    print("\nзаписано")
    return 0


if __name__ == "__main__":
    sys.exit(main("--write" in sys.argv, "--redo" in sys.argv))
