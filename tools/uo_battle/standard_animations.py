"""Стандартные анимации классов, у которых их нет.

Собирает в manual.animations (data/uo_battle.json) небольшой набор на каждый класс без библиотеки:
несколько видов атак, применение навыка и заклинания — из анимаций модели класса:

- attack_1..3 — семейства ATTACK, ATTACK_A/B/C: либо длинная цепочка (ATTACK_B, ATTACK_B_IDLE,
  ATTACK_B_2, ATTACK_B_IDLE2, ATTACK_B_END), либо нумерованные части (ATTACK_1..4, ATTACK_A_1..) ;
- skill_1 — SKILL_A1..3, иначе SKILL/SKILL_IDLE/SKILL_END, иначе ORDER_1..3;
- magic_1..2 — MAGIC_A/MAGIC_B (длинная цепочка с IDLE или нумерованные части).

Запуск из корня проекта:
    python tools/uo_battle/standard_animations.py            # добавить недостающие
    python tools/uo_battle/standard_animations.py --reset    # пересобрать созданные этим скриптом
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

MADE = re.compile(r"__(attack_\d|skill_\d|magic_\d)$")


def numbered(anims: dict, prefix: str) -> list[str]:
    """Нумерованные части семейства по порядку: PREFIX1 | PREFIX_1 (и вариант с _TO_IDLE)."""
    parts = []
    for n in range(1, 10):
        for cand in (f"{prefix}{n}", f"{prefix}_{n}"):
            if cand in anims:
                parts.append(cand)
                break
        else:
            for cand in (f"{prefix}{n}_TO_IDLE", f"{prefix}_{n}_TO_IDLE"):
                if cand in anims:
                    parts.append(cand)
                    break
    return parts


def family(anims: dict, prefix: str) -> list[str]:
    """Части одного семейства: длинная цепочка с IDLE или номера по порядку плюс концовка."""
    chain = [name for name in (prefix, f"{prefix}_IDLE", f"{prefix}_2", f"{prefix}_IDLE2",
                               f"{prefix}_END", f"{prefix}_END2") if name in anims]
    nums = numbered(anims, prefix)
    first = (f"{prefix}1", f"{prefix}_1")
    if len(nums) >= 2 or (len(nums) == 1 and nums[0] in first):
        parts = nums
        for end in (f"{prefix}_END", f"{prefix}_END_TO_IDLE", f"{prefix}_TO_IDLE"):
            if end in anims and end not in parts:
                parts.append(end)
                break
        return parts
    return chain


def magic_family(anims: dict, letter: str) -> list[str]:
    """Заклинание: цепочка MAGIC_A, MAGIC_A_IDLE, MAGIC_A_2, MAGIC_A_2_IDLE, MAGIC_A_END."""
    prefix = f"MAGIC_{letter}"
    if prefix in anims:
        seq = [prefix, f"{prefix}_IDLE", f"{prefix}_2", f"{prefix}_IDLE2", f"{prefix}_2_IDLE",
               f"{prefix}_END"]
        return [name for name in seq if name in anims]
    parts = numbered(anims, prefix)
    if parts and f"{prefix}_END" in anims:
        parts.append(f"{prefix}_END")
    return parts


def skill_parts(anims: dict) -> list[str]:
    """Применение навыка: SKILL_A1..3, иначе SKILL/SKILL_IDLE/SKILL_END, иначе ORDER_1..3."""
    for cand in (["SKILL_A1", "SKILL_A2", "SKILL_A3"], ["SKILL_A"],
                 ["SKILL_B1", "SKILL_B2", "SKILL_B3"], ["SKILL_B"],
                 ["SKILL", "SKILL_IDLE", "SKILL_END"],
                 ["ORDER_1", "ORDER_2", "ORDER_3"], ["ORDER"]):
        parts = [name for name in cand if name in anims]
        if parts and (len(parts) >= 2 or len(cand) == 1):
            return parts
    return []


def standard_set(anims: dict) -> dict[str, list[str]]:
    """Набор стандартных анимаций класса по именам анимаций его модели."""
    letters = [family(anims, f"ATTACK_{letter}") for letter in "ABCDE"]
    plain = family(anims, "ATTACK")
    strong = [p for p in letters if len(p) >= 2]
    weak = [p for p in letters if len(p) == 1]
    attacks = (([plain] if plain else []) + strong + (weak if len(strong) < 2 else []))
    out: dict[str, list[str]] = {}
    for i, parts in enumerate(attacks[:3], start=1):
        out[f"attack_{i}"] = parts
    skill = skill_parts(anims)
    if skill:
        out["skill_1"] = skill
    magic = [p for p in (magic_family(anims, letter) for letter in "ABCDE") if p][:2]
    for i, parts in enumerate(magic, start=1):
        out[f"magic_{i}"] = parts
    return out


def main() -> None:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    from battle.data import ShowData

    path = ROOT / "data" / "uo_battle.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    show = ShowData()
    animations = data.setdefault("manual", {}).setdefault("animations", {})

    if "--reset" in sys.argv:
        for key in [k for k in animations if MADE.search(k)]:
            animations.pop(key)

    have = {a.get("class") for a in animations.values()}
    made = 0
    for class_id in sorted(show.classes):
        if class_id in have:
            continue
        model = show.unit_model(class_id, 0)
        if model is None:
            print(f"{class_id}: нет модели, пропуск")
            continue
        for name, parts in standard_set(model.puppet.anims).items():
            key = f"{class_id}__{name}"
            animations[key] = {"class": class_id, "name": key, "parts": parts, "holds": {}, "tags": []}
            made += 1
            print(f"{key:34} {parts}")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nсоздано анимаций: {made}, всего в библиотеке: {len(animations)}")


if __name__ == "__main__":
    main()
