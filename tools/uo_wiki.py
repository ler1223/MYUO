"""Справочник классов Unicorn Overlord из вики (unilord.miraheze.org) — образец для своих данных.

    python tools/uo_wiki.py fetch [папка]      # скачать разметку страниц классов (MediaWiki API)
    python tools/uo_wiki.py parse [папка]      # разобрать в docs/uo/classes.json и docs/uo/classes.md

Из страницы класса берутся: тип (оружие, щит, пехота/конница/летун, броня, маг...), особенность,
оценки статов (S..F), повышение и его цена в почёте, навыки (категория, стоимость, уровень,
физ./маг. сила, число ударов, точность, описание, признаки вроде Ranged/Limited). Навыки
собираются ещё и общим списком: один и тот же навык бывает у нескольких классов.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "uo"
API = "https://unilord.miraheze.org/w/api.php?action=parse&page={page}&prop=wikitext&format=json&redirects=1"
SKIP = ("Dark Marquess",)                 # вражеские варианты без своих страниц
GRADES = "SABCDEF"
STATS = {"HP": "hp", "PATK": "phys_atk", "PDEF": "phys_def", "MATK": "mag_atk", "MDEF": "mag_def",
         "ACC": "accuracy", "EVA": "evasion", "CRI": "crit_rate", "GUD": "guard_rate", "INI": "initiative"}


def get(page: str) -> str:
    request = urllib.request.Request(API.format(page=urllib.parse.quote(page)),
                                     headers={"User-Agent": "MYUO-research/1.0"})
    return json.loads(urllib.request.urlopen(request, timeout=30).read())["parse"]["wikitext"]["*"]


def fetch(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    index = get("Classes")
    pages = sorted(set(re.findall(r"\[\[([^\]|#:]+)(?:\|[^\]]*)?\]\]", index)))
    for page in pages:
        if page.startswith(SKIP):
            continue
        (folder / f"{page}.wiki").write_text(get(page), encoding="utf-8")
        time.sleep(0.3)
    (folder / "Classes.wiki").write_text(index, encoding="utf-8")
    print(f"{len(pages)} pages -> {folder}")


def clean(text: str) -> str:
    """Разметка вики -> простой текст (цветные числа, картинки AP/PP, переносы)."""
    text = re.sub(r"\[\[File:AP Gem[^\]]*\]\]", "AP", text)
    text = re.sub(r"\[\[File:PP Gem[^\]]*\]\]", "PP", text)
    text = re.sub(r"\[\[File:[^\]]*\]\]", "", text)
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"'''?", "", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def field(block: str, name: str) -> str:
    match = re.search(rf"\|\s*{re.escape(name)}\s*=\s*(.*?)(?=\n\s*\||\n\}}\}}|$)", block, re.S)
    return match.group(1).strip() if match else ""


def number(text: str):
    match = re.search(r"-?\d+", text or "")
    return int(match.group()) if match else None


def boxes(text: str, kind: str) -> list[str]:
    """Тела шаблонов {{<kind> Skill Box ...}} (без вложенных шаблонов)."""
    return re.findall(r"\{\{" + kind + r" Skill Box(.*?)\n\}\}", text, re.S)


def parse_class(name: str, text: str) -> dict:
    ctype = clean(field(text, "CType"))
    details = clean(text.split("{{LeaderClass Details")[0].split("== Character Details ==")[-1])
    promote = re.search(r"promote into \[\[([^\]|]+)", text)
    honors = re.search(r"costs '''(\d+)'''", text)
    grades = {}
    for key, stat in STATS.items():
        letter = re.search(rf"\|\s*{key} IMAGE\s*=\s*\[\[File:Letter (\w)", text)
        grades[stat] = letter.group(1) if letter else None
    overview = {}
    for row in re.findall(r"^\|\s*(Active|Passive) Skill\s*\|\|\s*(.*?)\s*\|\|\s*(.*?)\s*\|\|\s*(.*?)\s*\|\|\s*(.*?)\s*$",
                          text, re.M):
        category, cost, skill, kind, level = row
        overview[clean(skill)] = {"category": category.lower(), "cost": cost, "type": kind,
                                  "level": number(level) or 1}
    skills = []
    for kind in ("Active", "Passive"):
        for block in boxes(text, kind):
            skill_name = clean(field(block, "skill name"))
            info = overview.get(skill_name, {})
            cost = info.get("cost", "")
            skills.append({
                "name": skill_name, "category": kind.lower(), "type": info.get("type", ""),
                "level": info.get("level", 1),
                "ap": number(cost) if "AP" in cost else 0, "pp": number(cost) if "PP" in cost else 0,
                "phys": number(field(block, "pdmg number")), "mag": number(field(block, "mdmg number")),
                "hits": number(field(block, "target number")), "accuracy": number(field(block, "number %")),
                "text": clean(field(block, "skill description")),
                "traits": [t for t in re.findall(r"[A-Za-z][A-Za-z .]+", field(block, "trait")) if t.strip() != "none"],
            })
    return {
        "name": name, "type": ctype, "trait": clean(field(text, "CTrait")), "about": details,
        "leader": clean(field(text, "Lskill name")), "move": clean(field(text, "Move type")),
        "stamina": clean(field(text, "Sta Number")), "promotes_to": promote.group(1) if promote else None,
        "honors": int(honors.group(1)) if honors else None, "grades": grades, "skills": skills,
    }


def group_of(name: str, index: str) -> str:
    """Раздел страницы «Classes», в котором класс перечислен."""
    section = "other"
    for line in index.split("\n"):
        heading = re.match(r"=+\s*(.*?)\s*=+", line)
        if heading:
            section = clean(heading.group(1))
        elif f"[[{name}" in line:
            return section
    return section


def parse(folder: Path) -> None:
    index = (folder / "Classes.wiki").read_text(encoding="utf-8") if (folder / "Classes.wiki").exists() else ""
    classes = []
    for path in sorted(folder.glob("*.wiki")):
        if path.stem == "Classes" or path.stem.startswith(SKIP):
            continue
        entry = parse_class(path.stem, path.read_text(encoding="utf-8"))
        entry["group"] = group_of(path.stem, index)
        classes.append(entry)
    promoted_from = {c["promotes_to"]: c["name"] for c in classes if c["promotes_to"]}
    for entry in classes:
        entry["promoted_from"] = promoted_from.get(entry["name"])
    skills: dict[str, dict] = {}
    for entry in classes:
        for skill in entry["skills"]:
            known = skills.setdefault(skill["name"], {**{k: v for k, v in skill.items() if k != "level"}, "classes": []})
            known["classes"].append(f"{entry['name']} {skill['level']}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "classes.json").write_text(json.dumps({"classes": classes, "skills": skills}, indent=1, ensure_ascii=False),
                                      encoding="utf-8")
    (OUT / "classes.md").write_text(markdown(classes, skills), encoding="utf-8")
    print(f"{len(classes)} classes, {len(skills)} skills -> {OUT}")


def markdown(classes: list[dict], skills: dict) -> str:
    out = ["# Классы Unicorn Overlord (справочник)", "",
           "Собрано `python tools/uo_wiki.py` из unilord.miraheze.org. Образец для своих данных; оценки статов —",
           "буквы S (лучше всех) .. F. Сила навыков — как в UO (100 = обычный удар), «удары» — число ударов.", ""]
    for entry in classes:
        grades = ", ".join(f"{k} {v}" for k, v in entry["grades"].items())
        up = f" → {entry['promotes_to']} ({entry['honors']} почёта)" if entry["promotes_to"] else ""
        down = f" (повышение из {entry['promoted_from']})" if entry["promoted_from"] else ""
        out += [f"## {entry['name']}{up}{down}", "", f"Тип: {entry['type']}. Особенность: {entry['trait']}. "
                f"Раздел: {entry['group']}.", "", f"Статы: {grades}", "",
                "| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for s in entry["skills"]:
            cost = f"{s['ap']} AP" if s["ap"] else f"{s['pp']} PP"
            text = s["text"].replace("\n", "; ") + (f" [{', '.join(s['traits'])}]" if s["traits"] else "")
            out.append(f"| {s['name']} | {s['category']} | {cost} | {s['level']} | {s['phys'] or ''} | {s['mag'] or ''} | "
                       f"{s['hits'] or ''} | {s['accuracy'] or ''} | {text} |")
        out.append("")
    return "\n".join(out) + "\n"


# --- снаряжение ------------------------------------------------------------------------

ITEM_PAGES = {"Swords": "sword", "Axes": "axe", "Spears": "spear", "Bows": "bow", "Staves": "staff",
              "GreatShields": "greatshield", "Accessories": "accessory"}
CARGO = ("https://unilord.miraheze.org/w/api.php?action=cargoquery&tables=Items&format=json&limit=500"
         "&fields=Id,Sort,Name,PhysickalAttack,MagickalAttack,PhysickalDefense,MagickalDefense,GuardRate,Skill,"
         "Slot1,Slot2,Slot3,Cost&where=Sort%3D%27Shield%27")


def fetch_items(folder: Path) -> None:
    """Страницы списков снаряжения, щиты из таблицы Cargo, страницы навыков предметов."""
    folder.mkdir(parents=True, exist_ok=True)
    for page in ITEM_PAGES:
        (folder / f"{page}.wiki").write_text(get(page), encoding="utf-8")
        time.sleep(0.3)
    request = urllib.request.Request(CARGO, headers={"User-Agent": "MYUO-research/1.0"})
    rows = [r["title"] for r in json.loads(urllib.request.urlopen(request, timeout=60).read())["cargoquery"]]
    (folder / "shields.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    known = set(json.loads((OUT / "classes.json").read_text(encoding="utf-8"))["skills"]) if (OUT / "classes.json").exists() else set()
    skills = sorted({s for item in parse_items(folder) for s in item["skills"] if s not in known})
    (folder / "skills").mkdir(exist_ok=True)
    for skill in skills:
        try:
            (folder / "skills" / f"{skill}.wiki").write_text(get(skill), encoding="utf-8")
        except (KeyError, OSError) as error:
            print(f"skill page {skill!r}: {error}")
        time.sleep(0.3)
    print(f"{len(ITEM_PAGES)} pages, {len(rows)} shields, {len(skills)} item skills -> {folder}")


def cells(row: str) -> list[str]:
    """Ячейки строки таблицы вики: разделители «||» и «|» в начале строки, кроме внутри [[...]] и {{...}}."""
    out, current, depth, i = [], "", 0, 0
    text = row.strip()
    if text.startswith("|"):
        text = text[1:]
    while i < len(text):
        two = text[i:i + 2]
        if two in ("[[", "{{"):
            depth += 1
            current += two
            i += 2
            continue
        if two in ("]]", "}}"):
            depth = max(0, depth - 1)
            current += two
            i += 2
            continue
        if depth == 0 and (two == "||" or (text[i] == "\n" and text[i + 1:i + 2] == "|")):
            out.append(current)
            current = ""
            i += 2
            continue
        current += text[i]
        i += 1
    out.append(current)
    result = []
    for cell in out:
        if cell.strip().startswith(("style=", "class=")):   # атрибуты ячейки до первого «|» вне [[...]]
            depth, cut = 0, None
            for k in range(len(cell)):
                if cell[k:k + 2] == "[[":
                    depth += 1
                elif cell[k:k + 2] == "]]":
                    depth -= 1
                elif cell[k] == "|" and depth == 0:
                    cut = k
                    break
            cell = cell[cut + 1:] if cut is not None else ""
        result.append(cell.strip())
    return result


def item_skills(text: str) -> list[str]:
    return [m for m in re.findall(r"\[\[([^\]|:]+)(?:\|[^\]]*)?\]\]", text) if not m.startswith("File")]


def stat_lines(*parts: str) -> list[str]:
    lines = []
    for part in parts:
        lines += [line for line in clean(part).split("\n") if line and line != "-"]
    return lines


def parse_items(folder: Path) -> list[dict]:
    items: list[dict] = []
    for page, kind in ITEM_PAGES.items():
        path = folder / f"{page}.wiki"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        table = text[text.index("{|"):] if "{|" in text else ""
        head = table.split("\n|-", 2)[1] if table.count("\n|-") > 1 else ""
        columns = []                       # шапка бывает в одну строку (!a!!b) и в несколько (!a\n!b)
        for line in head.split("\n"):
            if line.startswith("!"):
                columns += [c.strip().split("|")[-1].strip() for c in line.lstrip("!").split("!!")]
        for row in table.split("\n|-")[1:]:
            values = cells(row.split("\n|}")[0])
            if len(values) < 3:
                continue
            data = dict(zip(columns, values))
            name = clean(data.get("Name", ""))
            if not name:
                continue
            number = lambda key: int(re.search(r"-?\d+", data.get(key, "")).group()) if re.search(r"-?\d+", data.get(key, "")) else 0
            items.append({
                "name": name, "kind": kind, "phys_atk": number("P.Atk"), "mag_atk": number("M.Atk"),
                "phys_def": number("P.Def"), "mag_def": number("M.Def"), "guard_rate": number("Guard Rate"),
                "skills": item_skills(data.get("Skill", "")),
                "skill_cost": "PP" if "PP_Gem" in data.get("Skill", "") else ("AP" if "AP_Gem" in data.get("Skill", "") else ""),
                "stats": stat_lines(data.get("Substats", ""), data.get("Stat 1", ""), data.get("Stat 2", ""),
                                    data.get("Stat 3", "")),
                "price": number("Price"), "classes": clean(data.get("Classes", "")),
            })
    shields = folder / "shields.json"
    if shields.exists():
        for row in json.loads(shields.read_text(encoding="utf-8")):
            num = lambda v: int(v) if str(v).lstrip("-").isdigit() else 0
            items.append({"name": row["Name"], "kind": "shield", "phys_atk": 0, "mag_atk": 0,
                          "phys_def": num(row["PhysickalDefense"]), "mag_def": num(row["MagickalDefense"]),
                          "guard_rate": num(row["GuardRate"]), "skills": item_skills(f"[[{row['Skill']}]]") if row["Skill"] else [],
                          "skill_cost": "", "stats": [s for s in (row["Slot1"], row["Slot2"], row["Slot3"]) if s],
                          "price": num(row.get("Cost", "")), "classes": ""})
    return items


def infobox(text: str) -> dict:
    """Шаблон {{Skill InfoBox |Category=... |Description=...}} страницы навыка."""
    fields = dict(re.findall(r"\|\s*(\w+)\s*=\s*([^\n|]*)", text))
    num = lambda key: int(re.search(r"\d+", fields.get(key, "")).group()) if re.search(r"\d+", fields.get(key, "")) else None
    description = clean(fields.get("Description", ""))
    activation = clean(fields.get("Activation", ""))
    return {"category": "passive" if "Passive" in fields.get("Category", "") else "active",
            "ap": num("Cost") if "Active" in fields.get("Category", "") else 0,
            "pp": num("Cost") if "Passive" in fields.get("Category", "") else 0,
            "phys": num("PhysickalPotency") or None, "mag": num("MagickalPotency") or None,
            "hits": num("HitCount") or None, "accuracy": num("HitRate") or None,
            "traits": ["Ranged"] if fields.get("Ranged", "").strip() == "yes" else [],
            "text": "\n".join(x for x in (activation, description) if x)}


def parse_item_data(folder: Path) -> None:
    items = parse_items(folder)
    skills = {}
    for path in sorted((folder / "skills").glob("*.wiki")) if (folder / "skills").exists() else []:
        entry = infobox(path.read_text(encoding="utf-8"))
        if entry["text"]:
            skills[path.stem] = {"name": path.stem, "level": 1, "type": "", **entry}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "items.json").write_text(json.dumps({"items": items, "skills": skills}, indent=1, ensure_ascii=False),
                                    encoding="utf-8")
    print(f"{len(items)} items, {len(skills)} item skills -> {OUT / 'items.json'}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1] if len(sys.argv) > 1 else "parse"
    folder = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "docs" / "uo" / "wiki"
    {"fetch": fetch, "parse": parse, "items": lambda f: (fetch_items(f), parse_item_data(f)),
     "parse-items": parse_item_data}[mode](folder)


if __name__ == "__main__":
    main()
