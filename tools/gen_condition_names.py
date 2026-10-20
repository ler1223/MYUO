"""Названия условий тактики для интерфейса: data/conditions.json (английские, из игры) и русские в data/lang/ru.json.

    python -X utf8 tools/gen_condition_names.py [--write]

Английские названия — короткие строки меню тактики игры (``short`` из docs/uo/catalog/factors.json, его собирает
``tools/uo_skill_records.py``), названия групп — из ``UcFactorList.fms`` (610–622). Русские строятся по семействам
условий; ключ перевода — английское название (так устроен весь ``data/lang/ru.json``).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
GROUP_EN = {"formation": "Formation & Situation", "combatant_type": "Combatant Type", "hp": "HP", "ap_pp": "AP & PP",
            "status": "Combatant Status", "attack_type": "Attack Type", "unit_size": "Unit Size",
            "own_condition": "Own Condition", "own_hp": "Own HP", "own_ap_pp": "Own AP & PP",
            "enemies_present": "Enemies Present", "high_stats": "High Stats", "low_stats": "Low Stats",
            "custom": "Custom conditions"}
GROUP_RU = {"formation": "Строй и обстановка", "combatant_type": "Тип бойца", "hp": "HP цели", "ap_pp": "AP и PP цели",
            "status": "Состояние цели", "attack_type": "Тип атаки", "unit_size": "Размер отряда",
            "own_condition": "Я сам", "own_hp": "Своё HP", "own_ap_pp": "Своё AP и PP", "enemies_present": "Враги на поле",
            "high_stats": "Наибольший стат", "low_stats": "Наименьший стат", "custom": "Свои условия"}
TYPES = {"infantry": "пехота", "cavalry": "конница", "flying": "летуны", "armored": "бронированные", "scout": "разведчики",
         "archer": "лучники", "caster": "заклинатели", "elven": "эльфы", "bestral": "звери", "angel": "ангелы"}
STATS = {"max hp": "макс. HP", "max ap": "макс. AP", "max pp": "макс. PP", "patk": "физ. атака", "matk": "маг. атака",
         "pdef": "физ. защита", "mdef": "маг. защита", "init": "инициатива", "acc": "точность", "eva": "уклонение",
         "crit": "шанс крита", "grd": "шанс блока"}
STATUS = {"afflicted": "С состоянием", "poisoned": "Отравлена", "burning": "Горит", "frozen": "Заморожена",
          "stunned": "Оглушена", "blinded": "Ослеплена", "passive sealed": "Печать пассивок",
          "guard sealed": "Печать блока", "buffed": "С баффом", "debuffed": "С дебаффом"}
NOT_STATUS = {"afflicted": "Без состояния", "buffed": "Без баффа", "debuffed": "Без дебаффа", "poison": "Не отравлена",
              "burn": "Не горит", "frozen": "Не заморожена", "stun": "Не оглушена", "darkness": "Не ослеплена",
              "passive seal": "Без печати пассивок", "guard seal": "Без печати блока"}
FIXED = {
    "None": "Нет", "Prioritize the front row": "Приоритет: передний ряд", "Prioritize the back row": "Приоритет: задний ряд",
    "In the front row": "В переднем ряду", "In the back row": "В заднем ряду",
    "Lined up in front and back row": "В колонне из двух рядов", "Row with the most combatants": "Ряд, где больше всего бойцов",
    "Row with the least combatants": "Ряд, где меньше всего бойцов", "Rows with 2+ enemies (allies)": "Ряд с 2+ бойцами",
    "Rows with 3+ enemies (allies)": "Ряд с 3+ бойцами", "Daytime only": "Только днём", "Nighttime only": "Только ночью",
    "Most HP": "Больше всего HP", "Least HP": "Меньше всего HP", "Highest % HP": "Наибольшая доля HP",
    "Lowest % HP": "Наименьшая доля HP", "With less than 100% HP": "С неполным HP", "With 100% or more HP": "С полным HP",
    "Prioritize Buffed": "Приоритет: с баффом", "Prioritize Debuffed": "Приоритет: с дебаффом",
    "When physickally attacked": "Когда бьют физически", "When magickally attacked": "Когда бьют магией",
    "When the row is attacked": "Когда атакован ряд", "When the column is attacked": "Когда атакована колонна",
    "When all allies are attacked": "Когда атакованы все союзники", "Most AP": "Больше всего AP", "Least AP": "Меньше всего AP",
    "Most PP": "Больше всего PP", "Least PP": "Меньше всего PP", "User": "Только сам", "Other combatants": "Только другие",
    "User is buffed": "Я с баффом", "User is debuffed": "Я с дебаффом", "Own HP is less than 100%": "Своё HP неполное",
    "Own HP is 100% or more": "Своё HP полное", "1st action": "Первое действие", "2nd action": "Второе действие",
    "3rd action": "Третье действие", "4th action": "Четвёртое действие", "5th action": "Пятое действие", "???": "Служебное",
}


def russian(en: str) -> str:
    if en in FIXED:
        return FIXED[en]
    low = en.lower()
    if m := re.fullmatch(r"prioritize (\w+) combatants", low):
        return f"Приоритет: {TYPES[m.group(1)]}"
    if low in TYPES:
        return TYPES[low].capitalize()
    if m := re.fullmatch(r"(with|own hp is|avg\. enemy \(ally\) hp) (\d+)% or (less|more)( hp)?", low):
        prefix = {"with": "С HP", "own hp is": "Своё HP", "avg. enemy (ally) hp": "Среднее HP целей"}[m.group(1)]
        return f"{prefix} {'не выше' if m.group(3) == 'less' else 'не ниже'} {m.group(2)}%"
    if m := re.fullmatch(r"avg\. enemy \(ally\) hp less than 100%", low):
        return "Среднее HP целей неполное"
    if m := re.fullmatch(r"avg\. enemy \(ally\) hp 100% or more", low):
        return "Среднее HP целей полное"
    if low in STATUS:
        return STATUS[low]
    if m := re.fullmatch(r"not (afflicted|buffed|debuffed)", low):
        return NOT_STATUS[m.group(1)]
    if m := re.fullmatch(r"not afflicted with (poison|burn|frozen|stun|darkness|passive seal|guard seal)", low):
        return NOT_STATUS[m.group(1)]
    if m := re.fullmatch(r"when attacked by an? (\w+) combatant", low):
        return f"Когда бьёт: {TYPES[m.group(1)]}"
    if m := re.fullmatch(r"with (\d) or (more|fewer) (enemies|allies)", low):
        noun = "Врагов" if m.group(3) == "enemies" else "Союзников"
        return f"{noun} {'не меньше' if m.group(2) == 'more' else 'не больше'} {m.group(1)}"
    if m := re.fullmatch(r"(own )?(ap|pp) is (\d)( or (less|more))?", low):
        own = "Своё" if m.group(1) else ""
        what = m.group(2).upper()
        subject = f"{own} {what}" if own else f"{what} цели"
        if not m.group(4):
            return f"{subject} равно {m.group(3)}"
        return f"{subject} {'не больше' if m.group(5) == 'less' else 'не меньше'} {m.group(3)}"
    if m := re.fullmatch(r"(\w+) enemies present", low):
        return f"Есть враги: {TYPES[m.group(1)]}"
    if m := re.fullmatch(r"no (\w+) enemies", low):
        return f"Нет врагов: {TYPES[m.group(1)]}"
    if m := re.fullmatch(r"(highest|lowest) (.+)", low):
        return f"{'Наибольш' if m.group(1) == 'highest' else 'Наименьш'}{'ий' if m.group(2) in ('max hp', 'max ap', 'max pp', 'init', 'acc', 'eva', 'crit', 'grd') else 'ая'} {STATS[m.group(2)]}".replace("Наибольшийя", "Наибольший")
    raise KeyError(en)


def main(write: bool) -> int:
    factors = json.loads((BASE / "docs" / "uo" / "catalog" / "factors.json").read_text(encoding="utf-8"))["factors"]
    conditions = {}
    for factor in factors:
        if factor["key"] == "none" or factor["kind"] == "none":
            continue
        conditions[factor["key"]] = {"id": factor["id"], "kind": factor["kind"], "group": factor["group"],
                                     "name": factor["short"]}
    data = {"groups": GROUP_EN, "conditions": conditions}
    ru_path = BASE / "data" / "lang" / "ru.json"
    raw = ru_path.read_text(encoding="utf-8")
    ru = json.loads(raw)
    added = {}
    for item in conditions.values():
        name = item["name"]
        if name not in ru:
            added[name] = russian(name)
    for key, name in GROUP_EN.items():
        if name not in ru:
            added[name] = GROUP_RU[key]
    clash = {k: (ru[k], v) for k, v in added.items() if k in ru}
    print(f"условий: {len(conditions)}; новых переводов: {len(added)}")
    for k in list(added)[:12]:
        print("  ", k, "->", added[k])
    if write:
        (BASE / "data" / "conditions.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                                                       encoding="utf-8", newline="")
        ru.update(added)
        indent = 2 if raw.startswith('{\n  "') else 1
        ru_path.write_text(json.dumps(ru, ensure_ascii=False, indent=indent) + ("\n" if raw.endswith("\n") else ""),
                           encoding="utf-8", newline="")
        print("записано")
    return 0


if __name__ == "__main__":
    sys.exit(main("--write" in sys.argv))
