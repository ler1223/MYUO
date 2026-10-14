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


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1] if len(sys.argv) > 1 else "parse"
    folder = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "docs" / "uo" / "wiki"
    {"fetch": fetch, "parse": parse}[mode](folder)


if __name__ == "__main__":
    main()
