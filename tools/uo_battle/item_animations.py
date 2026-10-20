"""Настоящие анимации навыков предметов из файлов игры.

У навыка класса в файле персонажа есть своя цепочка (S##_<НАВЫК>_1..N), и
tools/uo_battle/build.py находит её по внутреннему имени навыка. Навыки предметов
сборщик не смотрел: в manual.skill_animations у них лежала заглушка — обычная
атака или каст класса. Этот инструмент:

- находит у каждого класса в его модели слоты навыков предметов, которые он может
  надеть (стрелы дождём, пронзание, удар по земле, святая колыбель…);
- пишет их настоящие цепочки в manual.classes.<класс>.skills (ручная правка не
  теряется при пересборке);
- убирает у этих навыков заглушку привязки (animation = ""), чтобы играла своя
  анимация класса, а эффекты, полёт и дождь навыка остались;
- где в файлах своей анимации нет — ничего не трогает: остаётся обычная атака или
  каст класса, как и было.

Запуск: python tools/uo_battle/item_animations.py [--write] [--src <папка игры>]
Без --write только печатает, что будет сделано.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.uo.mbs import MBS  # noqa: E402

CONFIG = ROOT / "data" / "uo_battle.json"
LOCAL = ROOT / "assets" / "uo_anim" / "local.json"
# То же, что в build.py: у дождя стрел в файлах встречается и GRACIAL_RAIN.
SLOT_ALIAS = {"GRACIALRAIN": "ARROWRAIN"}


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def slot_chains(names) -> dict[str, list[str]]:
    """Слоты S## файла персонажа: имя без номера -> анимации по порядку файла."""
    groups: dict[str, list[str]] = {}
    for name in names:
        m = re.match(r"^S\d\d_(.+)$", name)
        if m:
            base = re.sub(r"_?\d+$", "", m.group(1))
            groups.setdefault(base, []).append(name)
    return groups


def skill_chain(groups: dict[str, list[str]], code: str) -> list[str]:
    """Части навыка: все слоты, в имени которых стоит внутреннее имя навыка (как build.py).

    Пусто — у навыка в этом файле своей анимации нет.
    """
    code = norm(SLOT_ALIAS.get(code.upper(), code))
    if not code:
        return []
    return [name for base, names in groups.items() if code in norm(base) for name in names]


def merged_classes(config: dict) -> dict[str, dict]:
    """classes + manual.classes: правка вручную важнее собранного (как в battle.data)."""
    manual = config.get("manual") or {}
    classes = dict(config.get("classes") or {})
    for cid, over in (manual.get("classes") or {}).items():
        classes[cid] = {**classes.get(cid, {}), **over}
    return classes


def find(class_id: str, file: str, unit: dict, items, skills, game, src: Path) -> list[tuple[str, list[str]]]:
    """Навыки предметов класса, у которых в его модели есть настоящая цепочка."""
    path = src / "Chara" / f"{file}.mbs"
    if not path.is_file():
        return []
    groups = slot_chains(a["name"] for a in MBS(path.read_bytes()).anims)
    own = {s if isinstance(s, str) else s["id"] for s in unit.get("skills") or ()}
    slots = set(unit.get("slots") or ())
    ids = {s for item in items if item.get("slot") in slots for s in item.get("skills") or ()}
    out = []
    for sid in sorted(ids - own):
        if sid not in skills:
            continue
        internal = (game.get(sid) or {}).get("game_internal") or ""
        code = re.sub(r"^(ACT|PAS)_", "", internal)
        parts = skill_chain(groups, code)
        if parts:
            out.append((sid, parts))
    return out


def is_placeholder(classes: dict[str, dict], animations: dict[str, dict], bind: dict) -> bool:
    """Привязка-заглушка: цепочка совпадает с одной из фаз класса-источника.

    migrate_animations привязывал навыку предмета обычную атаку, каст или стойку класса
    (S01_ATTACK_A1…, SKILL_A1…, IDLE…), чтобы навык хоть что-то играл.
    """
    animation = animations.get((bind or {}).get("animation") or "") or {}
    parts = tuple(str(p) for p in animation.get("parts") or ())
    phases = {tuple(str(p).rstrip("*") for p in v)
              for v in (classes.get(animation.get("class") or "", {}).get("phases") or {}).values()}
    return bool(parts) and parts in phases


def plan(config: dict, src: Path) -> list[dict]:
    """Что изменить: по записи на пару класс + навык предмета с настоящей анимацией."""
    units = json.loads((ROOT / "data" / "units.json").read_text(encoding="utf-8"))
    items = list(json.loads((ROOT / "data" / "items.json").read_text(encoding="utf-8")).values())
    skills = json.loads((ROOT / "data" / "skills.json").read_text(encoding="utf-8"))
    game = json.loads((ROOT / "docs" / "uo" / "skills_game.json").read_text(encoding="utf-8"))
    manual = config.setdefault("manual", {})
    manual_classes = manual.setdefault("classes", {})
    binds = manual.get("skill_animations") or {}
    animations = manual.get("animations") or {}
    classes = merged_classes(config)
    changes = []
    for class_id, info in sorted(classes.items()):
        unit = units.get(class_id)
        if unit is None or not info.get("file"):
            continue
        for sid, parts in find(class_id, info["file"], unit, items, skills, game, src):
            entry = manual_classes.setdefault(class_id, {})
            old = (entry.get("skills") or {}).get(sid)
            bind = binds.get(sid) or {}
            bound = bind.get("animation") or ""
            bound_parts = list((animations.get(bound) or {}).get("parts") or ())
            changes.append({
                "class": class_id,
                "skill": sid,
                "parts": parts,
                "was": list(old or ()),
                "bound": bound,
                "bound_parts": bound_parts,
                "clear_bind": bool(bound) and bound_parts != parts,
            })
    # Заглушки: навыку предмета при миграции досталась цепочка фазы класса (атака, каст или
    # стойка) — в показе это чужая атака или «ничего». Такие привязки снимаем: у класса
    # играется его обычная атака или каст, а если выше нашлась своя анимация — она.
    known = {change["skill"] for change in changes}
    item_skills = sorted({s for item in items for s in item.get("skills") or () if s in skills})
    for sid in item_skills:
        bind = dict(binds.get(sid) or {})
        bound = bind.get("animation") or ""
        if not bound or sid in known:
            continue
        if not is_placeholder(classes, animations, bind):
            continue                                 # настоящая анимация — не трогаем
        parts = list((animations.get(bound) or {}).get("parts") or ())
        changes.append({"class": "", "skill": sid, "parts": [], "was": [], "bound": bound,
                        "bound_parts": parts, "clear_bind": True, "placeholder": True})
    return changes


def apply(config: dict, changes: list[dict]) -> None:
    manual = config.setdefault("manual", {})
    manual_classes = manual.setdefault("classes", {})
    binds = manual.setdefault("skill_animations", {})
    for change in changes:
        if change["parts"]:
            entry = manual_classes.setdefault(change["class"], {})
            entry.setdefault("skills", {})[change["skill"]] = change["parts"]
        if change["clear_bind"]:
            spec = dict(binds.get(change["skill"]) or {})
            spec["animation"] = ""
            binds[change["skill"]] = spec


def main() -> None:
    local = json.loads(LOCAL.read_text(encoding="utf-8")) if LOCAL.is_file() else {}
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default=local.get("src", "F:/MYUO2/unpacked"))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    changes = plan(config, Path(args.src))
    for change in changes:
        where = change["class"] or "—"
        note = "заглушка снята" if change["clear_bind"] else "привязки нет"
        parts = " ".join(change["parts"]) or f"было: {change['bound']} ({' '.join(change['bound_parts'])})"
        print(f"{where:14} {change['skill']:20} {note:14} {parts}")
    own = sum(1 for change in changes if change["parts"])
    print(f"навыков предметов со своей анимацией: {own}, снято заглушек: "
          f"{sum(1 for change in changes if change['clear_bind'])}")
    if not args.write:
        print("без --write ничего не записано")
        return
    apply(config, changes)
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"записано: {CONFIG}")


if __name__ == "__main__":
    main()
