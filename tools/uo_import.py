"""Классы, навыки и пассивки Unicorn Overlord -> справочник data/ (по docs/uo/classes.json).

    python tools/uo_import.py            # заменить классы на классы UO, добавить их навыки, пассивки, эффекты
    python tools/uo_import.py --dry-run  # только отчёт docs/uo/import_report.md, данные не трогаются
    python tools/uo_import.py regrade    # пересчитать статы классов по data/grades.json (оценки в классах)

Что делается:
  классы    — 60 классов UO (три пернатых без данных в вики пропущены): статы по оценкам S..F
              (data/grades.json), теги (пехота, конница, летун, броня, лучник, маг, щит...), слоты (оружие,
              щит, аксессуары), навыки с уровнями открытия, повышения (базовый -> повышенный, ур. PROMOTE_LEVEL),
              тир (базовые 10, уникальные 15, повышенные 20, повышения уникальных 25);
  навыки    — сила UO (100 = power 1.0), удары, точность, область (одиночная, ряд, колонна, все), теги
              (ближний, дальний, магия), состояния и баффы, условная сила, неблокируемость, игнор защиты,
              кража AP/PP, награды за попадание и добивание;
  пассивки  — триггер UO -> событие реакции с фильтрами, действие: навык-ответ (контратака, преследование,
              первый удар), блок, прикрытие, бафф, лечение, AP/PP, снятие дебаффов;
  эффекты   — общая библиотека (состояния UO, баффы и дебаффы статов, защитные заряды) и эффекты навыков.
Чего в движке нет (ночь и день, феи, воскрешение, конец боя, …) — приближения, список в отчёте.
Старые классы удаляются, неиспользуемые старые навыки, пассивки и эффекты — тоже.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from game.database import Database  # noqa: E402
from tools.uo_names import CLASSES as CLASS_RU, SKILLS as SKILL_RU, TAGS as TAG_RU  # noqa: E402

REFERENCE = ROOT / "docs" / "uo" / "classes.json"
REPORT = ROOT / "docs" / "uo" / "import_report.md"
GRADES = ROOT / "data" / "grades.json"
LANG = ROOT / "data" / "lang" / "ru.json"
SPRITES_JSON = ROOT / "assets" / "units" / "units.json"
NAMES_JSON = ROOT / "data" / "names.json"
SKIP = {"Featherbow", "Feathershield", "Featherstaff"}
UNIQUE_BASE = {"Lord", "Priestess", "Crusader"}
PROMOTE_LEVEL = 10
WEAPONS = {"Sword": "light_sword", "Axe": "heavy_weapon", "Spear": "lance", "Bow": "bow", "Staff": "staff"}
SHIELD_SLOT, ACCESSORY = "light_shield", "artifact"
TYPE_TAGS = {"Infantry": "infantry", "Cavalry": "cavalry", "Flying": "flying", "Armor": "armored",
             "Archer": "archer", "Caster": "caster", "Shield": "shield", "Greatshield": "greatshield",
             "Scout": "scout", "Elf": "elf", "Bestral": "bestral", "Angel": "angel"}
FEMALE_SPRITES = {"cleric", "mage", "cryomancer", "stormcaller", "witch", "rider"}
STATS = ["hp", "phys_atk", "phys_def", "mag_atk", "mag_def", "accuracy", "evasion", "crit_rate", "guard_rate",
         "initiative"]
# Спрайт для класса UO (своих спрайтов у новых классов нет)
SPRITE = {
    "fighter": "knight", "vanguard": "knight", "lord": "paladin", "high_lord": "rider", "prince": "fighter",
    "crusader": "paladin", "valkyria": "paladin", "feathersword": "paladin", "dreadnought": "knight",
    "swordfighter": "fighter", "sword_master": "fighter", "sellsword": "fighter", "landsknecht": "fighter",
    "thief": "fighter", "rogue": "fighter", "werewolf": "fighter", "elven_fencer": "fighter",
    "soldier": "spearman", "sergeant": "spearman", "hoplite": "spearman", "legionnaire": "spearman",
    "werefox": "spearman", "housecarl": "fighter", "viking": "fighter", "gladiator": "orc", "berserker": "orc",
    "warrior": "knight", "breaker": "knight", "werelion": "orc", "werebear": "orc",
    "knight": "rider", "great_knight": "rider", "radiant_knight": "rider", "sainted_knight": "rider",
    "dark_knight": "rider", "doom_knight": "rider", "paladin": "rider", "gryphon_knight": "rider",
    "gryphon_master": "rider", "wyvern_knight": "rider", "wyvern_master": "rider",
    "hunter": "hunter", "sniper": "hunter", "arbalist": "archer", "shieldshooter": "archer",
    "elven_archer": "archer", "snow_ranger": "hunter",
    "cleric": "cleric", "bishop": "cleric", "priestess": "cleric", "high_priestess": "cleric",
    "wizard": "mage", "warlock": "pyromancer", "witch": "witch", "sorceress": "witch", "wereowl": "witch",
    "shaman": "stormcaller", "druid": "cryomancer", "elven_augur": "stormcaller", "elven_sibyl": "cryomancer",
}

AILMENTS = {   # название в UO -> (id, флаги, длительность ходов, реакции, русское название)
    "Burn": ("burn", [], None, [{"event": "turn_start", "whose": "self", "action": "damage", "amount": 20,
                                 "to": "owner"}], "Ожог"),
    "Poison": ("poison", [], None, [{"event": "turn_start", "whose": "self", "action": "damage", "amount": 30,
                                     "percent": True, "to": "owner"}], "Яд"),
    "Freeze": ("freeze", ["frozen"], 2, [], "Заморозка"),
    "Stun": ("stun", ["stunned"], 1, [], "Оглушение"),
    "Blindness": ("blind", ["blind"], 1, [], "Слепота"),
    "Guard Seal": ("guard_seal", ["guard_seal"], None, [], "Печать блока"),
    "Passive Seal": ("passive_seal", ["passive_seal"], None, [], "Печать пассивок"),
    "Critical Seal": ("crit_seal", ["crit_seal"], None, [], "Печать крита"),
}
STAT_WORDS = [  # слово UO -> статы (длинные первыми)
    ("Phys. Defense", ["phys_def"]), ("Phys. Attack", ["phys_atk"]), ("Mag. Defense", ["mag_def"]),
    ("Mag. Attack", ["mag_atk"]), ("Critical Rate", ["crit_rate"]), ("Critical damage", ["crit_damage"]),
    ("Guard Rate", ["guard_rate"]), ("Initiative", ["initiative"]), ("Evasion", ["evasion"]),
    ("Accuracy", ["accuracy"]), ("Defense", ["phys_def", "mag_def"]), ("Attack", ["phys_atk", "mag_atk"]),
]
STAT_RU = {"phys_def": "физ. защита", "phys_atk": "физ. атака", "mag_def": "маг. защита", "mag_atk": "маг. атака",
           "crit_rate": "шанс крита", "crit_damage": "урон крита", "guard_rate": "шанс блока",
           "initiative": "инициатива", "evasion": "уклонение", "accuracy": "точность"}
CHARGES = {   # защитные заряды: id -> (флаги, русское название)
    "guard_small": (["guard:small"], "Малый блок"), "guard_medium": (["guard:medium"], "Средний блок"),
    "guard_heavy": (["guard:heavy"], "Тяжёлый блок"), "evade_one": (["evade"], "Уклонение от удара"),
    "evade_ranged": (["evade:ranged"], "Уклонение от выстрела"), "negate_one": (["negate"], "Неуязвимость к удару"),
    "negate_melee": (["negate:melee"], "Защита от ближнего удара"),
    "negate_magic": (["negate:magical"], "Защита от магии"), "endure": (["endure"], "Стойкость"),
    "immune_debuff": (["immune:debuff"], "Защита от дебаффа"), "immune_ailment": (["immune:ailment"], "Защита от состояния"),
    "taunt": (["taunt"], "Провокация"), "unguardable": (["unguardable"], "Неотразимость"),
}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower().replace("’", "").replace("'", "")).strip("_")


class Importer:
    def __init__(self, reference: dict, grades: dict):
        self.ref = reference
        self.grades = grades
        self.skills: dict[str, dict] = {}
        self.passives: dict[str, dict] = {}
        self.effects: dict[str, dict] = {}
        self.ru: dict[str, str] = {}
        self.notes: dict[str, list[str]] = {}

    def note(self, skill: str, text: str) -> None:
        self.notes.setdefault(skill, []).append(text)

    # --- эффекты --------------------------------------------------------------------

    def ailment(self, name: str) -> str:
        effect_id, flags, duration, triggers, ru = AILMENTS[name]
        effect_id = "uo_" + effect_id
        self.effects[effect_id] = {"name": f"UO {name}", "flags": flags, "tags": ["debuff", "ailment"],
                                   "duration": duration, "triggers": triggers,
                                   "stack_rule": "STACK" if name == "Burn" else "REFRESH",
                                   "max_stacks": 3 if name == "Burn" else 1}
        self.ru[f"UO {name}"] = ru
        return effect_id

    def charge(self, kind: str) -> str:
        flags, ru = CHARGES[kind]
        effect_id = "uo_" + kind
        self.effects[effect_id] = {"name": f"UO {kind}", "flags": flags, "tags": ["buff"],
                                   "charges": 1 if kind not in ("taunt", "unguardable") else None,
                                   "duration": 2 if kind in ("taunt", "unguardable") else None}
        self.ru[f"UO {kind}"] = ru
        return effect_id

    def stat_effect(self, changes: list[tuple[list[str], float, bool]], stacks: bool, name_hint: str) -> str:
        """Бафф или дебафф статов на весь бой: changes — (статы, значение, проценты?)."""
        modifiers, parts = [], []
        for stats, value, percent in changes:
            for stat in stats:
                modifiers.append({"stat": stat, "op": "PERCENT_ADD" if percent else "FLAT",
                                  "value": round(value / 100, 3) if percent else value})
            label = " и ".join(STAT_RU[s] for s in stats)
            parts.append(f"{label} {value:+g}{'%' if percent else ''}")
        bad = all(value < 0 for _, value, _ in changes)
        effect_id = "uo_" + slug("_".join(f"{'_'.join(s)}_{'m' if v < 0 else 'p'}{abs(v):g}{'pct' if p else ''}"
                                          for s, v, p in changes)) + ("_stack" if stacks else "")
        name = f"UO {effect_id[3:]}"
        self.effects[effect_id] = {"name": name, "modifiers": modifiers, "tags": ["debuff" if bad else "buff"],
                                   "duration": None, "stack_rule": "STACK" if stacks else "REFRESH",
                                   "max_stacks": 5 if stacks else 1}
        self.ru[name] = ", ".join(parts)
        return effect_id

    # --- разбор текста -----------------------------------------------------------------

    @staticmethod
    def stat_changes(text: str) -> list[tuple[list[str], float, bool]]:
        """«+20% Phys. Defense and +10 Accuracy», «Initiative -20» -> [(статы, значение, проценты?)]."""
        words = "|".join(re.escape(word) for word, _ in STAT_WORDS)
        found = []
        for match in re.finditer(rf"([+-]\d+)(%?)\s*({words})|({words})\s*([+-]\d+)(%?)", text, re.I):
            if match.group(1):
                value, percent, word = int(match.group(1)), bool(match.group(2)), match.group(3)
            else:
                word, value, percent = match.group(4), int(match.group(5)), bool(match.group(6))
            stats = next(v for k, v in STAT_WORDS if k.lower() == word.lower())
            found.append((stats, value, percent))
        return found

    @staticmethod
    def area(text: str) -> str:
        lower = text.lower()
        if "all enemies" in lower or "all allies" in lower:
            return "all"
        if "column" in lower:
            return "column"
        if "row of" in lower or "a row" in lower or "row enemies" in lower:
            return "row"
        return "single"

    def inflicted(self, key: str, text: str) -> tuple[list[dict], dict]:
        """«Inflicts X» -> (наложения на цель, особенности навыка)."""
        applies, extras = [], {}
        for line in text.split("\n"):
            low = line.lower()
            if not low.startswith(("inflicts", "inflitcts")):
                continue
            for name in AILMENTS:
                if name.lower() in low or (name == "Critical Seal" and "critcal seal" in low):
                    cond = {"type": "has_tag", "tag": "cavalry"} if "cavalry" in low else {"type": "always"}
                    applies.append({"effect_id": self.ailment(name), "to": "target", "condition": cond})
            if re.search(r"\bAP\b[^,.]*-(\d)", line):
                extras["ap_drain"] = int(re.search(r"\bAP\b[^,.]*-(\d)", line).group(1))
            if re.search(r"\bPP\b[^,.]*-(\d)", line):
                extras["pp_drain"] = int(re.search(r"\bPP\b[^,.]*-(\d)", line).group(1))
            changes = [c for c in self.stat_changes(line) if c[1] < 0]
            if changes:
                applies.append({"effect_id": self.stat_effect(changes, False, key), "to": "target"})
        return applies, extras

    def potency_and_extras(self, key: str, text: str) -> tuple[list[dict], dict]:
        potency, extras = [], {}
        for line in text.replace("{", "(").split("\n"):
            low = line.lower()
            bonus = re.search(r"\+(\d+) potency v\. (\w+) targets", line)
            if bonus:
                tag = {"cavalry": "cavalry", "flying": "flying", "armored": "armored", "infantry": "infantry"}.get(
                    bonus.group(2))
                if tag:
                    potency.append({"add": int(bonus.group(1)) / 100,
                                    "target_condition": {"type": "has_tag", "tag": tag}})
                elif bonus.group(2) == "debuffed":
                    potency.append({"add": int(bonus.group(1)) / 100,
                                    "target_condition": {"type": "has_label", "label": "debuff"}})
                elif bonus.group(2) in ("frozen", "forzen", "poisoned"):
                    effect = self.ailment("Freeze" if "fro" in bonus.group(2) or "for" in bonus.group(2) else "Poison")
                    potency.append({"add": int(bonus.group(1)) / 100,
                                    "target_condition": {"type": "has_effect", "effect_id": effect}})
            maximum = re.search(r"[Mm]aximum increases?: ?\+?(\d+)", text)
            top = int(maximum.group(1)) / 100 if maximum else 0.5
            if "less hp the user has" in low or "as hp decreases" in low:
                potency.append({"add": top, "scale": "self_hp_missing"})
            if "more hp the user has" in low:
                potency.append({"add": top, "scale": "self_hp"})
            if "less hp a target has" in low:
                potency.append({"add": top, "scale": "target_hp_missing"})
            if "based on the target's hp" in low:
                potency.append({"add": top, "scale": "target_hp"})
            if "fewer enemies" in low:
                potency.append({"add": top, "scale": "enemies_fallen"})
            front = re.search(r"\+(\d+) potency if the user is in the front row", line)
            if front:
                potency.append({"add": int(front.group(1)) / 100, "scale": "front_row"})
            buffed = re.search(r"\+(\d+) potency if the user (?:is|if) buffed", line)
            if buffed:
                potency.append({"add": int(buffed.group(1)) / 100,
                                "self_condition": {"type": "has_label", "label": "buff"}})
            hp_cond = re.search(r"\+(\d+) potency if the user is (at|below) (\d+)% HP", line)
            if hp_cond:
                kind = "hp_above" if hp_cond.group(2) == "at" else "hp_below"
                value = int(hp_cond.group(3)) / 100 if kind == "hp_below" else min(1.0, int(hp_cond.group(3)) / 100)
                potency.append({"add": int(hp_cond.group(1)) / 100, "self_condition": {"type": kind, "value": value}})
            if "cavalry targets cannot guard" in low:
                extras["unguardable_vs"] = ["cavalry"]
            ignore = re.search(r"[Ii]gnores (\d+)% (?:of the target's )?[Dd]efense( v\. armored)?", line)
            if ignore:
                extras["ignore_def"] = int(ignore.group(1)) / 100
                if ignore.group(2):
                    extras["ignore_def_vs"] = ["armored"]
            if "truestrike" in low and "if" not in low and "next" not in low:
                extras["truestrike"] = True
            if "cannot be a crit" in low:
                extras["no_crit"] = True
            crit = re.search(r"[Cc]ritical rate ?\+(\d+)", line)
            if crit:
                extras["crit_add"] = int(crit.group(1))
            if "remove" in low and "buff" in low and "debuff" not in low:
                extras["dispel"] = ["buff"]
            heal_hit = re.search(r"[Rr]ecover (\d+)% HP if the attack hits", line)
            if heal_hit:
                extras["heal_on_hit"] = int(heal_hit.group(1)) / 100
            heal_kill = re.search(r"[Rr]ecover (\d+)% HP if the target is defeated", line)
            if heal_kill:
                extras["kill_heal"] = int(heal_kill.group(1)) / 100
            steal = re.search(r"HP equal to (\d+)% of damage", line)
            if steal:
                extras["lifesteal"] = int(steal.group(1)) / 100
            cost = re.search(r"(?:Consumes|Sacrifice) (\d+)% (?:of own )?HP", line)
            if cost:
                extras["hp_cost"] = int(cost.group(1)) / 100
            gain = re.search(r"Grants the user \+(\d)\s*(AP|PP)", line)
            if gain and ("defeated" in low):
                extras["kill_ap" if gain.group(2) == "AP" else "kill_pp"] = int(gain.group(1))
            elif gain and ("hits" in low):
                extras["hit_ap" if gain.group(2) == "AP" else "hit_pp"] = int(gain.group(1))
            take = re.search(r"Steal (\d+|all of the enemy's) ?(?:of the enemy's )?(AP|PP)", line)
            if "steal" in low and ("ap" in low or "pp" in low):
                amount = 1
                number = re.search(r"Steal (\d+)", line)
                if number:
                    amount = int(number.group(1))
                elif "all" in low:
                    amount = 9
                extras["ap_drain" if " ap" in low.replace("pp", "") and "PP" not in line else "pp_drain"] = amount
                extras["steal"] = True
            if "night" in low or "day" in low:
                self.note(key, f"ночь/день не переносятся: «{line}»")
            if "faerie" in low:
                self.note(key, f"феи заменены приближением: «{line}»")
            del take
        return potency, extras

    @staticmethod
    def tags_of(entry: dict, text: str) -> list[str]:
        magic = bool(entry.get("mag")) or "magick" in text.lower() or "magic" in text.lower()
        ranged = "Ranged" in entry.get("traits", ())
        tags = ["magic"] if magic and not entry.get("phys") else (["ranged"] if ranged else ["melee"])
        if magic and entry.get("phys"):
            tags.append("magic")
        return tags

    # --- активные навыки ---------------------------------------------------------------

    def parts(self, entry: dict, heal: bool) -> list[dict]:
        parts = []
        if heal:
            percent = re.search(r"(?:Restore|Recover) (\d+)% HP", entry["text"])
            if percent:
                return [{"kind": "heal_pct", "category": "magical", "power": int(percent.group(1)) / 100}]
            power = (entry.get("mag") or 50) / 100
            return [{"kind": "heal", "category": "magical", "power": power,
                     "scaling": [{"stat": "mag_atk", "coef": 1.0}]}]
        if entry.get("phys"):
            parts.append({"kind": "damage", "category": "physical", "power": entry["phys"] / 100,
                          "scaling": [{"stat": "phys_atk", "coef": 1.0}]})
        if entry.get("mag"):
            parts.append({"kind": "damage", "category": "magical", "power": entry["mag"] / 100,
                          "scaling": [{"stat": "mag_atk", "coef": 1.0}]})
        hp = re.search(r"damage equal to (\d+)% of the user's HP", entry["text"])
        if hp:
            parts.append({"kind": "damage", "category": "pure", "power": 1.0,
                          "scaling": [{"stat": "hp", "coef": int(hp.group(1)) / 100}]})
        return parts

    @staticmethod
    def sentences(text: str) -> list[str]:
        """Строки описания; строка без точки в конце продолжается следующей."""
        out, current = [], ""
        for line in text.split("\n"):
            current = f"{current} {line}".strip()
            if current.endswith((".", ")")):
                out.append(current)
                current = ""
        if current:
            out.append(current)
        return out

    def next_attack(self, kind: str, ru: str, mods: dict) -> str:
        """Заряд на следующую атаку (верный удар, крит, добавка магии, мощь)."""
        effect_id = "uo_next_" + kind
        self.effects[effect_id] = {"name": f"UO next {kind}", "tags": ["buff"], "charges": 1, "attack_mods": [mods]}
        self.ru[f"UO next {kind}"] = ru
        return effect_id

    def support_effects(self, key: str, text: str) -> list[tuple[str, str]]:
        """Баффы и заряды из текста: [(эффект, кому: target/self)]."""
        result = []
        for line in self.sentences(text):
            low = line.lower()
            who = "self" if "the user" in low or "user's" in low and "allies" not in low else "target"
            changes = [c for c in self.stat_changes(line) if c[1] > 0]
            if low.startswith(("grants", "grant")) and changes:
                result.append((self.stat_effect(changes, "stack" in text.lower(), key), who))
            elif "evade" in low and ("one" in low or "single" in low):
                result.append((self.charge("evade_ranged" if "ranged" in low else "evade_one"), who))
            elif "negate" in low and "magick" in low and "damage" in low:
                result.append((self.charge("negate_magic"), who))
            elif "negate" in low and "melee" in low:
                result.append((self.charge("negate_melee"), who))
            elif "reduce damage taken" in low:
                level = "medium" if "50%" in line else "small"
                result.append((self.charge(f"guard_{level}"), who))
                self.note(key, "«урезать урон одной атаки» — принудительный блок (только физический урон)")
            elif "truestrike" in low and "next attack" in low:
                crit = "critical" in low
                mods = {"accuracy_add": 1000, "crit_add": 100 if crit else 0}
                result.append((self.next_attack("sure_crit" if crit else "sure",
                                                "Верный удар и крит" if crit else "Верный удар", mods), who))
            elif "critical rate for" in low and "next attack" in low:
                result.append((self.next_attack("crit", "Верный крит", {"crit_add": 100}), who))
            elif "add magick damage" in low:
                result.append((self.next_attack("magic", "Магия в атаке", {
                    "add_scaling": [{"stat": "mag_atk", "coef": 0.5}]}), who))
            elif "increases attack power for one attack" in low:
                result.append((self.next_attack("power", "Мощная атака", {"power_mult": 1.5}), who))
                self.note(key, "мощь от поглощённых баффов — фиксированные +50%")
            elif "max initiative" in low:
                result.append((self.stat_effect([(["initiative"], 100, False)], False, key), "self"))
                self.note(key, "«макс. инициатива на ход» — +100 инициативы на весь бой")
            elif "immunity to damage" in low or ("nullify" in low and "damage" in low):
                result.append((self.charge("negate_one"), who))
            elif "lethal blow" in low:
                result.append((self.charge("endure"), who))
            elif "negates a single debuff" in low or "immunity to one debuff" in low:
                result.append((self.charge("immune_debuff"), who))
            elif "focus attacks on the user" in low:
                result.append((self.charge("taunt"), "self"))
            elif "unguardable" in low:
                result.append((self.charge("unguardable"), "target"))
            elif "regeneration" in low:
                self.effects["uo_regen"] = {"name": "UO regen", "tags": ["buff"], "duration": 3, "triggers": [
                    {"event": "turn_start", "whose": "self", "action": "heal", "amount": 15, "percent": True,
                     "to": "owner"}]}
                self.ru["UO regen"] = "Регенерация"
                result.append(("uo_regen", who))
        return result

    def active(self, key: str, entry: dict) -> dict:
        text = entry["text"]
        low = text.lower()
        heal = ("restore" in low or "heal" in low or "recover" in low) and "attack" not in low.split("\n")[0]
        effects = self.support_effects(key, text)
        targets = "enemy"
        if heal or (not entry.get("phys") and not entry.get("mag") and "enem" not in low.split("\n")[0]):
            targets = "ally" if "all" in low or "ally" in low or "allies" in low or heal else "self"
        parts = self.parts(entry, heal) if (entry.get("phys") or entry.get("mag") or heal or "HP" in text) else []
        if targets == "enemy" and not parts:
            parts = [{"kind": "damage", "category": "physical", "power": 1.0,
                      "scaling": [{"stat": "phys_atk", "coef": 1.0}]}]
            self.note(key, "сила не указана в вики — взята 100")
        applies, extras_inflict = self.inflicted(key, text)
        potency, extras = self.potency_and_extras(key, text)
        extras.update(extras_inflict)
        for effect_id, who in effects:
            applies.append({"effect_id": effect_id, "to": "self" if who == "self" and targets == "enemy" else "target"})
        if "removes all" in low and "debuff" in low or "remove all debuffs" in low:
            extras.setdefault("dispel", []).append("debuff")
        if "two enemies" in low or "three enemies" in low:
            self.note(key, "две-три случайные цели заменены одиночной целью с теми же ударами")
        if "charg" in low:
            self.note(key, "заряд (действие в конце раунда) не переносится: обычный удар")
        if "revive" in low:
            self.note(key, "воскрешения в движке нет: лечение")
        skill = {"name": entry["name"], "ap_cost": entry["ap"] or 1, "pp_cost": entry["pp"] if not entry["ap"] else 0,
                 "targets": targets, "area": self.area(text.split("\n")[0]), "hits": entry.get("hits") or 1,
                 "accuracy": entry.get("accuracy") or 100, "tags": self.tags_of(entry, text), "parts": parts,
                 "applies": applies, "potency": potency, "extras": extras}
        return skill

    # --- пассивки ------------------------------------------------------------------------

    TRIGGERS = [  # (начало строки «Activates ...» -> поля реакции)
        ("at the start of a battle", {"event": "battle_start"}),
        ("before attacking with an active skill", {"event": "before_skill", "whose": "self"}),
        ("before an ally is attacked", {"event": "targeted", "whose": "ally"}),
        ("after an enemy attacks with an active skill", {"event": "skill_used", "whose": "enemy"}),
        ("after an ally is hit by an attack", {"event": "attacked", "whose": "ally", "outcome": "landed"}),
        ("before being hit by a physickal attack", {"event": "targeted", "whose": "self", "attack_tags": ["physical"]}),
        ("after using an active skill", {"event": "skill_used", "whose": "self"}),
        ("at the end", {"event": "round_end", "limit": "battle"}),
        ("after an ally attacks", {"event": "skill_used", "whose": "ally"}),
        ("before being attacked", {"event": "targeted", "whose": "self"}),
        ("before an ally attacks", {"event": "before_skill", "whose": "ally"}),
        ("after attacking", {"event": "skill_used", "whose": "self"}),
        ("after an ally is debuffed", {"event": "effect_applied", "whose": "ally", "effect_label": "debuff"}),
        ("before an ally is hit by a ranged phys", {"event": "targeted", "whose": "ally",
                                                   "attack_tags": ["ranged"]}),
        ("before an ally is hit by a magick attack", {"event": "targeted", "whose": "ally", "attack_tags": ["magical"]}),
        ("before being hit by a melee attack", {"event": "targeted", "whose": "self", "attack_tags": ["melee"]}),
        ("after being hit by an attack", {"event": "attacked", "whose": "self", "outcome": "landed"}),
        ("after being attacked", {"event": "attacked", "whose": "self"}),
        ("after an enemy guards against an ally", {"event": "attacked", "whose": "enemy", "outcome": "guarded"}),
        ("before an enemy uses an attack skill", {"event": "before_skill", "whose": "enemy"}),
        ("after being healed", {"event": "healed", "whose": "self"}),
        ("after the user is debuffed", {"event": "effect_applied", "whose": "self", "effect_label": "debuff"}),
        ("after evading an attack", {"event": "attacked", "whose": "self", "outcome": "missed"}),
        ("after a calavry-based ally attacks", {"event": "skill_used", "whose": "ally",
                                               "subject_condition": {"type": "has_tag", "tag": "cavalry"}}),
        ("before being hit by a ranged attack", {"event": "targeted", "whose": "self", "attack_tags": ["ranged"]}),
        ("after receiving an ally's passive skill", {"event": "skill_used", "whose": "ally"}),
        ("after being hit by a physickal attack", {"event": "attacked", "whose": "self", "outcome": "landed",
                                                   "attack_tags": ["physical"]}),
        ("after an ally uses an active skill", {"event": "skill_used", "whose": "ally"}),
        ("before an ally's physickal attack", {"event": "before_skill", "whose": "ally", "attack_tags": ["physical"]}),
        ("after ally uses a magick attack", {"event": "skill_used", "whose": "ally", "attack_tags": ["magical"]}),
        ("after an enemy is debuffed", {"event": "effect_applied", "whose": "enemy", "effect_label": "debuff"}),
        ("after an ally uses a passive skill", {"event": "skill_used", "whose": "ally"}),
        ("after an enemy is buffed", {"event": "effect_applied", "whose": "enemy", "effect_label": "buff"}),
    ]

    def trigger(self, key: str, text: str) -> dict:
        first = text.split("\n")[0].lower()
        for start, fields in self.TRIGGERS:
            if start in first:
                if "passive skill" in start:
                    self.note(key, "события «пассивка союзника» нет: реагирует на навык союзника")
                if start == "at the end":
                    self.note(key, "конца боя нет: срабатывает в конце раунда, раз за бой")
                return dict(fields)
        self.note(key, f"триггер не распознан: «{text.splitlines()[0]}» — начало боя")
        return {"event": "battle_start"}

    def passive(self, key: str, entry: dict) -> dict:
        text = entry["text"]
        body = "\n".join(text.split("\n")[1:]) or text
        low = body.lower()
        reaction = self.trigger(key, text)
        reaction.setdefault("whose", "self")
        if "Limited" in entry.get("traits", ()):
            reaction["limit"] = "round"
        attack = ("attack a" in low or "strike" in low or "counterattack" in low or "follow-up" in low
                  or "attacks a" in low) and "next attack" not in low
        heal = ("restore" in low or "heal" in low) and not attack
        if attack:
            helper = dict(self.active(key, dict(entry, text=body, ap=1, pp=0)), name=entry["name"])
            helper_id = f"{key}_strike"
            self.skills[helper_id] = helper
            self.ru.setdefault(entry["name"], SKILL_RU.get(entry["name"], entry["name"]))
            reaction.update(action="use_skill", skill_id=helper_id)
            if "counter" in low:
                reaction["to"] = "actor"
            elif "follow-up" in low or "pursuit" in low:
                reaction["to"] = "target"
            elif reaction["event"] in ("battle_start", "before_skill") and reaction.get("whose") != "enemy":
                reaction["to"] = "enemies"
            else:
                reaction["to"] = "actor" if reaction["event"] in ("targeted", "attacked", "before_skill") else "enemies"
            return reaction
        if "cover" in low:
            reaction = {"event": "targeted", "whose": "ally", "action": "cover", "to": "owner",
                        "attack_tags": reaction.get("attack_tags", []), "limit": reaction.get("limit", "none"),
                        "cover_many": "row of allies" in low}
            level = "heavy" if "heavy guard" in low else ("medium" if "medium guard" in low else None)
            if level:
                reaction["effect_id"] = self.charge(f"guard_{level}")
            elif "nullify" in low:
                reaction["effect_id"] = self.charge("negate_one")
            return reaction
        guard = re.search(r"(minor|small|medium|heavy) guard", low)
        if guard and "block" in low:
            level = {"minor": "small"}.get(guard.group(1), guard.group(1))
            reaction.update(action="apply_effect", effect_id=self.charge(f"guard_{level}"), to="owner")
            return reaction
        to = "owner"
        if "an ally" in low or "that ally" in low or "the target" in low:
            to = "subject" if reaction.get("whose") in ("ally", "enemy") else "owner"
        group = None
        if "allies in the user's row" in low or "row of allies" in low or "a row" in low:
            group = ("allies", "row")
        elif "all allies" in low:
            group = ("allies", None)
        elif "all enemies" in low or "row of enemies" in low:
            group = ("enemies", None)
        if heal:
            percent = re.search(r"(?:Restore|Recover) (\d+)% HP", body)
            if percent:
                reaction.update(action="heal", amount=int(percent.group(1)), percent=True, to=to)
            else:
                helper_id = f"{key}_heal"
                self.skills[helper_id] = dict(self.active(key, dict(entry, text=body, ap=1, pp=0)),
                                              name=entry["name"], targets="ally")
                reaction.update(action="use_skill", skill_id=helper_id, to=to)
            if group:
                reaction.update(to=group[0], to_area=group[1])
                if reaction["action"] == "use_skill":
                    self.note(key, "лечение группы — одним навыком по первому союзнику")
            return reaction
        if "remove all buffs" in low:
            reaction.update(action="dispel", label="buff",
                            to="actor" if reaction.get("whose") not in ("self", None) else "enemies")
            return reaction
        if "revive" in low:
            reaction.update(action="apply_effect", effect_id=self.charge("endure"), to="allies")
            self.note(key, "воскрешения нет: союзники получают «пережить смертельный удар»")
            return reaction
        if "of damage dealt on next attack" in low:
            reaction.update(action="heal", amount=25, percent=True, to="owner")
            self.note(key, "вампиризм следующей атаки — сразу лечение 25% HP")
            return reaction
        if "sacrifice" in low and "ap" in low:
            reaction.update(action="restore_ap", amount=1, to="owner")
            self.note(key, "плата HP за AP не переносится: просто +1 AP")
            return reaction
        if "inflict guard seal" in low:
            reaction.update(action="apply_effect", effect_id=self.ailment("Guard Seal"), to="actor")
            self.note(key, "«следующая атака накладывает печать блока» — печать сразу атаковавшему")
            return reaction
        if "remove" in low and "debuff" in low:
            reaction.update(action="dispel", label="debuff", to=group[0] if group else to)
            if group and group[1]:
                reaction["to_area"] = group[1]
            return reaction
        resource = re.search(r"Grants (?:the user|an ally|that ally) \+(\d)\s*(AP|PP)", body)
        effects = self.support_effects(key, body)
        inflict, _ = self.inflicted(key, body)
        if resource and not effects:
            reaction.update(action="restore_ap" if resource.group(2) == "AP" else "restore_pp",
                            amount=int(resource.group(1)), to=to)
            return reaction
        if inflict:
            reaction.update(action="apply_effect", effect_id=inflict[0]["effect_id"],
                            to=group[0] if group and group[0] == "enemies" else "actor")
            if len(inflict) > 1:
                self.note(key, "наложено только первое из нескольких состояний")
            return reaction
        if effects:
            effect_id, who = effects[0]
            reaction.update(action="apply_effect", effect_id=effect_id,
                            to=group[0] if group else ("owner" if who == "self" else to))
            if group and group[1]:
                reaction["to_area"] = group[1]
            if len(effects) > 1:
                self.note(key, "из нескольких эффектов взят первый")
            return reaction
        self.note(key, f"действие не распознано: «{body}» — пассивка без эффекта (+1 PP себе)")
        reaction.update(action="restore_pp", amount=0, to="owner")
        return reaction

    # --- классы ------------------------------------------------------------------------

    def stats(self, grades: dict[str, str]) -> tuple[dict, dict]:
        base, growth = {}, {}
        for stat in STATS:
            value, per = self.grades[stat][grades.get(stat) or "C"]
            base[stat], growth[stat] = value, per
        base["crit_damage"] = self.grades.get("crit_damage", 150)
        return base, {k: v for k, v in growth.items() if v}

    def classes(self) -> dict[str, dict]:
        out = {}
        for entry in self.ref["classes"]:
            if entry["name"] in SKIP or not entry["skills"]:
                continue
            class_id = slug(entry["name"])
            words = entry["type"].replace("ScoutBestral", "Scout Bestral").split()
            weapon = next((WEAPONS[w] for w in words if w in WEAPONS), "light_sword")
            shields = sum(1 for w in words if w in ("Shield", "Greatshield"))
            promoted = entry["group"].startswith("Promoted")
            accessories = (1 if shields else 2) + (1 if promoted else 0)
            tags = list(dict.fromkeys(TYPE_TAGS[w] for w in words if w in TYPE_TAGS))
            base, growth = self.stats(entry["grades"])
            kind = "promoted" if promoted else "base"
            skills, passives = [], []
            for skill in entry["skills"]:
                if not skill["name"] or "|" in skill["name"]:
                    continue                       # страница вики без имени навыка
                key = slug(skill["name"])
                learned = key if skill["level"] <= 1 else {"id": key, "level": skill["level"]}
                (skills if skill["category"] == "active" else passives).append(learned)
            unique = entry["name"] in UNIQUE_BASE or entry.get("promoted_from") in UNIQUE_BASE
            tier = (25 if promoted else 15) if unique else (20 if promoted else 10)
            out[class_id] = {
                "name": entry["name"], "stats": base, "growth": growth,
                "ap_max": self.grades["ap"][kind], "pp_max": self.grades["pp"][kind],
                "tags": tags, "slots": [weapon] + [SHIELD_SLOT] * shields + [ACCESSORY] * accessories,
                "skills": skills, "passives": passives, "tactics": [], "tier": tier,
                "promotions": [{"class": slug(entry["promotes_to"]), "level": PROMOTE_LEVEL}]
                if entry.get("promotes_to") else [],
                "grades": {k: v for k, v in entry["grades"].items() if v},
            }
            self.ru[entry["name"]] = CLASS_RU.get(entry["name"], entry["name"])
        for data in out.values():                  # повышение только в существующий класс
            data["promotions"] = [p for p in data["promotions"] if p["class"] in out]
        return out

    def skills_and_passives(self) -> None:
        for name, entry in self.ref["skills"].items():
            if not entry["name"] or "|" in entry["name"]:
                continue
            key = slug(name)
            self.ru[name] = SKILL_RU.get(name, name)
            if entry["category"] == "active":
                self.skills[key] = self.active(key, entry)
            else:
                self.passives[key] = {"name": name, "pp_cost": entry["pp"] or 1, "reaction": self.passive(key, entry)}

    def tactics(self, data: dict) -> None:
        """Тактика по умолчанию: лечение раненых, баффы, затем атаки — от поздних навыков к ранним."""
        for class_data in data.values():
            rules, ids = [], [s if isinstance(s, str) else s["id"] for s in class_data["skills"]]
            for skill_id in reversed(ids):
                skill = self.skills.get(skill_id)
                if skill is None:
                    continue
                if skill["parts"] and skill["parts"][0]["kind"] in ("heal", "heal_pct"):
                    rules.insert(0, {"skill": skill_id, "condition": {"type": "hp_below", "value": 0.7},
                                     "selector": "weakest"})
                elif skill["targets"] != "enemy":
                    rules.insert(0, {"skill": skill_id})
                else:
                    rules.append({"skill": skill_id})
            class_data["tactics"] = rules


VISUALS_JSON = ROOT / "assets" / "visuals" / "skills.json"
# Нарисованный визуал старых навыков -> похожие навыки UO (остальные берут общий визуал по виду доставки)
VISUAL_MAP = {
    "power_strike": ["heavy_slash", "smash", "heavy_smash"], "crushing_blow": ["grand_smash", "wide_smash"],
    "stun_bash": ["shield_smite"], "flurry": ["spinning_edge", "hastened_strike"],
    "venom_strike": ["venom_thrust", "venom_axe", "toxic_throw"], "cleave": ["round_swing", "row_smash"],
    "smite": ["saints_blade", "divine_cross"], "group_heal": ["row_heal", "sacred_heal"],
    "shot": ["single_shot", "power_bolt", "aerial_snipe"], "poison_arrow": ["toxic_bolt"], "volley": ["row_shot"],
    "piercing_shot": ["sonic_shaft"], "magic_bolt": ["magick_missile"], "firestorm": ["volcano"],
    "ice_shard": ["icebolt"], "blizzard": ["glacial_rain"], "lance_charge": ["assaulting_lance", "piercing_lance"],
}


def remap_visuals(db: Database) -> None:
    """Ключи визуала навыков: старые навыки -> похожие навыки UO; ключи несуществующих — прочь."""
    visuals = json.loads(VISUALS_JSON.read_text(encoding="utf-8"))
    out = {}
    for key, spec in visuals.items():
        class_id, _, skill_id = key.rpartition("/")
        if key.startswith("_") or (skill_id in db.skills and (not class_id or class_id in db.units)):
            out[key] = spec
            continue
        for new in VISUAL_MAP.get(skill_id, []) if not class_id else []:
            if new in db.skills and new not in visuals:
                out[new] = spec
    VISUALS_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def regrade(db: Database, grades: dict) -> None:
    importer = Importer({}, grades)
    for class_id, definition in list(db.units.items()):
        if not definition.grades:
            continue
        data = definition.to_dict()
        data["stats"], data["growth"] = importer.stats(dict(definition.grades))
        db.update("units", class_id, data)
    db.save()
    print(f"stats recomputed for {sum(1 for d in db.units.values() if d.grades)} classes")


def apply(importer: Importer, classes: dict) -> Database:
    db = Database.load()
    data = db.to_dict()
    config = data["config"]
    config["guard"] = {"levels": {"small": 0.25, "medium": 0.5, "heavy": 0.75}, "base": "small",
                       "tags": {"shield": "medium", "greatshield": "heavy"}}
    rules = [r for r in config["tag_rules"] if not (r["attack"] == ["cavalry"] and r["target"] == ["infantry"])
             and not (r["attack"] == ["archer"] and r["target"] == ["flying"])
             and not (r["attack"] == ["flying"] and r["target"] == ["cavalry"])]
    rules += [{"attack": ["cavalry"], "attack_not": [], "target": ["infantry"], "damage": 2.0, "hit": 1.0},
              {"attack": ["archer"], "attack_not": [], "target": ["flying"], "damage": 2.0, "hit": 1.0},
              {"attack": ["flying"], "attack_not": [], "target": ["cavalry"], "damage": 2.0, "hit": 1.0}]
    config["tag_rules"] = rules
    for tag, ru in TAG_RU.items():
        data["tags"].setdefault(tag, {"name": tag.capitalize(), "kind": "unit"})
        importer.ru.setdefault(tag.capitalize(), ru)
    data["effects"].update(importer.effects)
    data["skills"].update(importer.skills)
    data["passives"].update(importer.passives)
    data["units"] = classes
    db._apply(data)
    # Старое, на что больше ничего не ссылается, — прочь (предметы и эффекты свои ссылки сохраняют)
    for section in ("passives", "skills", "effects"):
        for key in list(getattr(db, section)):
            if key in getattr(importer, section) or referenced(db, section, key):
                continue
            db.delete(section, key)
    return db


def referenced(db: Database, section: str, key: str) -> bool:
    text = json.dumps({s: v for s, v in db.to_dict().items() if s != section}, ensure_ascii=False)
    own = json.dumps(db.to_dict()[section], ensure_ascii=False)
    pattern = re.compile(rf'"{re.escape(key)}"')
    return bool(pattern.search(text)) or len(pattern.findall(own)) > 1


def write_report(importer: Importer, classes: dict) -> None:
    lines = ["# Перенос классов UO: отчёт", "",
             f"Классов: {len(classes)}, навыков: {len(importer.skills)}, пассивок: {len(importer.passives)}, "
             f"эффектов: {len(importer.effects)}. Ниже — где пришлось приблизить (`python tools/uo_import.py`).", ""]
    for key in sorted(importer.notes):
        lines.append(f"- **{key}**: " + "; ".join(importer.notes[key]))
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    grades = {k: v for k, v in json.loads(GRADES.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    if "regrade" in sys.argv:
        regrade(Database.load(), grades)
        return
    importer = Importer(json.loads(REFERENCE.read_text(encoding="utf-8")), grades)
    classes = importer.classes()
    importer.skills_and_passives()
    importer.tactics(classes)
    write_report(importer, classes)
    if "--dry-run" in sys.argv:
        print(f"report -> {REPORT}")
        return
    db = apply(importer, classes)
    db.save()
    remap_visuals(db)
    lang = json.loads(LANG.read_text(encoding="utf-8"))
    lang.update(importer.ru)
    LANG.write_text(json.dumps(lang, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    sprites = json.loads(SPRITES_JSON.read_text(encoding="utf-8"))
    sprites["fallback"]["classes"] = {c: SPRITE.get(c, "knight") for c in classes}
    SPRITES_JSON.write_text(json.dumps(sprites, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    names = json.loads(NAMES_JSON.read_text(encoding="utf-8"))
    names["female_classes"] = sorted(c for c in classes if SPRITE.get(c) in FEMALE_SPRITES)
    NAMES_JSON.write_text(json.dumps(names, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(classes)} classes, {len(db.skills)} skills, {len(db.passives)} passives, {len(db.effects)} effects")


if __name__ == "__main__":
    main()
