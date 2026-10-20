"""Первичное сопоставление: заполнить data/uo_anim.json явным выбором анимаций, эффектов и фонов.

    python tools/uo_extract/auto_map.py --src <папка распакованного Unicorn.CPK> [--text <папка>] [--force]

--text — распакованный Unicorn_US.CPK (по умолчанию <src>/../unpacked_us): английские названия навыков
игры (MsgSheet/UcSkillList.fms) и их внутренние имена (Debug/_UcEnum_Skill.inc). Навыки проекта названы
по-английски, а эффекты и подписанные анимации в файлах игры — по внутренним именам (Icebolt — ICE_SHOT).

Без --force уже заданное (вручную в редакторе) не трогается — дописывается только недостающее.

Что заполняется:
- classes.<класс>.states — состояния персонажа:
  idle — кольцо UPWARD, UPWARD_IDLE, UPWARD_END по кругу (у кого их нет — STANCE_1..3),
  attack — первый неподписанный слот навыка класса (S## с ATTACK*/MAGIC*; подписанные слоты вроде
  S01_ARROW_RAIN — это свои навыки), skill — запасной каст,
  hit (KNOCKBACK), avoid (AVOID), guard (GUARD), cover (COVER_A1, COVER_A2), die, victory.
  Анимации D_* и FACE_* — разговорные, IDLE — стойка в разговоре: в бою они не берутся.
- classes.<класс>.skills.<навык> — анимация навыка класса: группа S## файла (слоты навыков
  класса в игре). Сначала по имени (FIRST_AID, ARROW_RAIN, BT_HEAL…), потом по роду навыка
  (магия — MAGIC*, лечение — *HEAL*, остальное — ATTACK*) по порядку слотов.
- skill_fx.<навык> — эффекты из Effect/Battle_Effect.mbs: группа с именем навыка (Fireball —
  FIREBALL_*, Heavy Smash — HEAVYSMASH); cast — на применившем, hit — на цели.
- backgrounds.<фон> — фоны боя BattleBG/BGBt*: use, сцена проекта (scene) по названию, линия пола.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from engine.uo.library import remember_game_folder  # noqa: E402
from engine.uo.mbs import MBS  # noqa: E402

CONFIG = ROOT / "data" / "uo_anim.json"
TALK = re.compile(r"^(D_|FACE_|EP_|HG_D_)")
SCENES = [   # фон по названию -> сцена проекта (assets/scenes)
    (re.compile(r"Snow|Ice", re.I), "winter"),
    (re.compile(r"Desert|Oasis|Wasteland|Sand", re.I), "desert"),
    (re.compile(r"Forest|Thorn|Elf|Wood|Albion|Wetland", re.I), "forest"),
    (re.compile(r"Cave|Underground|Graveyard|DarkElf|Limestone|Mist|Nightsky", re.I), "lava"),
    (re.compile(r"Capital|Castle|Fort|Cathedral|Sanct|Town|Colosseum|Citadel|Square|Ruins", re.I), "castle"),
]


def norm(text: str) -> str:
    return re.sub(r"[^A-Z]", "", text.upper().replace("MAGICK", "MAGIC"))


def groups(names: list[str]) -> dict[str, list[str]]:
    """S## -> анимации группы по порядку (полные имена с префиксом)."""
    out: dict[str, list[str]] = {}
    for n in names:
        m = re.match(r"^(S\d\d)_", n)
        if m:
            out.setdefault(m.group(1), []).append(n)
    return out


def group_label(anims: list[str]) -> str:
    """Имя группы без префикса и номеров частей: S16_FIRST_AID_1 -> FIRST_AID."""
    base = re.sub(r"^S\d\d_", "", anims[0])
    return re.sub(r"(_\d+|_[A-Z]?\d+|_IDLE\d*|_END\d*|_TO_IDLE)+$", "", base)


def first(names, *options):
    for o in options:
        if o in names:
            return [o]
    return []


def class_states(names: list[str], g: dict[str, list[str]]) -> dict[str, list[str]]:
    usable = [n for n in names if not TALK.match(n)]
    ring = [n for n in ("UPWARD", "UPWARD_IDLE", "UPWARD_END") if n in usable]
    if "UPWARD_IDLE" not in ring:
        ring = [n for n in ("STANCE_1", "STANCE_2", "STANCE_3") if n in usable] or first(usable, "GUARD_IDLE_1")
    plain = [k for k in sorted(g) if k < "S16" and re.match(r"^(ATTACK|MAGIC)", group_label(g[k]))]
    states = {
        "idle": ring,
        "attack": g.get(plain[0]) if plain else first(usable, "ATTACK", "ATTACK_1", "ATTACK_A1"),
        "hit": first(usable, "KNOCKBACK"),
        "avoid": first(usable, "AVOID"),
        "guard": first(usable, "GUARD"),
        "cover": [n for n in ("COVER_A1", "COVER_A2") if n in usable],
        "die": first(usable, "DIE") or [n for n in ("DIE_BLOW_1", "DIE_BLOW_2") if n in usable] or first(usable, "DOWN"),
        "victory": first(usable, "VICTORY_1"),
    }
    actives = [k for k in sorted(g) if "S02" <= k < "S16"]
    cast = next((k for k in actives if re.search(r"MAGIC|SKILL|HEAL", g[k][0])), actives[0] if actives else None)
    states["skill"] = g.get(cast, []) if cast else []
    return states


def skill_kind(skill: dict) -> str:
    parts = skill.get("parts", [])
    if parts and all(p.get("kind") == "heal" for p in parts):
        return "heal"
    tags = set(skill.get("tags", []))
    if "magic" in tags or any(p.get("category") == "magical" for p in parts):
        return "magic"
    if "ranged" in tags:
        return "ranged"
    return "melee"


# слоты без имени навыка (ATTACK_B, MAGIC_A, …) — по роду навыка; подписанные (ARROW_RAIN, BT_HEAL) — только по имени
KIND_GROUP = {"heal": r"^(BT_)?HEAL|RESURRECT", "magic": r"^(MAGIC|SKILL)", "ranged": r"^ATTACK", "melee": r"^ATTACK"}


def align_names(text: Path) -> dict[str, str]:
    """Английское название навыка игры -> внутреннее имя (без ACT_/PAS_). Тексты (A)/(P) в UcSkillList
    идут в порядке перечисления; списки выравниваются по похожести имён (переводы бывают вольные)."""
    sheet, enum = text / "MsgSheet" / "UcSkillList.fms", text / "Debug" / "_UcEnum_Skill.inc"
    if not sheet.is_file() or not enum.is_file():
        return {}
    data = sheet.read_bytes()
    start = next(i for i in range(0x20, len(data)) if data[i])
    eng = [re.sub(r"^\((A|P)\) ", "", t) for t in (b.decode("utf-8", "replace") for b in data[start:].split(b"\0"))
           if re.match(r"^\((A|P)\) ", t)]
    internal = [ln.split(",")[0].strip() for ln in enum.read_text(encoding="utf-8-sig").splitlines()[1:]]
    internal = [e for e in internal if re.match(r"^(ACT|PAS)_", e) and not e.endswith(("_START", "_END"))
                and not e.startswith("ACT_ASSIST")]
    a = [norm(re.sub(r"^(ACT|PAS)_", "", x)) for x in internal]
    b = [norm(x) for x in eng]
    gap, band = -0.6, 8
    score = {(0, 0): 0.0}
    back = {}
    for i in range(len(a) + 1):
        for j in range(max(0, i - band), min(len(b), i + band) + 1):
            if i == j == 0:
                continue
            options = []
            if i and j and (i - 1, j - 1) in score:
                options.append((score[(i - 1, j - 1)] + difflib.SequenceMatcher(None, a[i - 1], b[j - 1]).ratio(), 0))
            if i and (i - 1, j) in score:
                options.append((score[(i - 1, j)] + gap, 1))
            if j and (i, j - 1) in score:
                options.append((score[(i, j - 1)] + gap, 2))
            if options:
                score[(i, j)], back[(i, j)] = max(options)
    i, j, out = len(a), len(b), {}
    while (i, j) in back:
        step = back[(i, j)]
        if step == 0:
            out[norm(eng[j - 1])] = re.sub(r"^(ACT|PAS)_", "", internal[i - 1])
            i, j = i - 1, j - 1
        elif step == 1:
            i -= 1
        else:
            j -= 1
    return out


def skill_keys(sid: str, all_skills: dict, names: dict[str, str]) -> list[str]:
    """Ключи для поиска анимаций и эффектов навыка: английское и внутреннее имя, без знаков."""
    eng = norm(all_skills.get(sid, {}).get("name", sid))
    keys = [eng, norm(sid)]
    if eng in names:
        keys.append(norm(names[eng]))
    return keys


def class_skills(skill_ids: list[str], all_skills: dict, g: dict[str, list[str]], passives: list[str],
                 names: dict[str, str]) -> dict:
    """Навык -> анимации группы S##: по имени, потом по роду навыка по порядку слотов."""
    out, used = {}, set()
    labels = {k: norm(group_label(v)) for k, v in g.items()}
    for sid in skill_ids:                                 # по имени навыка или его пассивки
        owner = next((p for p in passives if sid.startswith(p + "_")), None)
        keys = skill_keys(sid, all_skills, names) + (skill_keys(owner, {}, names) if owner else [])
        keys += [k[2:] for k in keys if k.startswith("BT")]
        hit = next((k for k, lab in labels.items() if lab in keys and k not in used), None)
        if hit:
            out[sid] = g[hit]
            used.add(hit)
    slots = [k for k in sorted(g) if "S02" <= k < "S16"]
    for sid in skill_ids:                                 # остальные — по роду, по порядку слотов
        if sid in out:
            continue
        kind = skill_kind(all_skills.get(sid, {}))
        free = [k for k in slots if k not in used and re.search(KIND_GROUP[kind], group_label(g[k]))]
        if free:
            out[sid] = g[free[0]]
            used.add(free[0])
    return out


def effect_groups(names: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for n in names:
        base = re.sub(r"(_\d+|_HIT|_EFFECT|_OUT|_IN|_BUFFER)+$", "", n)
        out.setdefault(norm(base), []).append(n)
    return out


GENERIC_HITS = [   # (слова в названии навыка, эффект попадания) — по стихии и по виду удара
    (r"FIRE|FLAME|BURN|BLAZE|INFERN|VOLCAN", "HIT_A_FIRE"),
    (r"ICE|ICIC|FROST|FREEZ|BLIZZ|SNOW", "HIT_A_ICE"),
    (r"TOXIC|VENOM|POISON|PLAGUE", "HIT_A_POIZON"),
    (r"SMASH|HAMMER|CRUSH|BASH|SMITE|BLOW|SWING|KICK|STOMP", "HITMARK_00A"),
    (r"THRUST|STAB|LANCE|SPEAR|IMPAL|PIERC|STING|PENETRAT|JAVELIN", "HIT_C"),
]


def generic_hit(skill: dict) -> str:
    name = norm(skill.get("name", ""))
    found = next((fx for rx, fx in GENERIC_HITS if re.search(rx, name)), None)
    kind = skill_kind(skill)
    if kind == "heal":
        return "HEAL_HIT_01"
    if found:
        return found
    return {"magic": "HIT_A_MAGIC", "ranged": "HIT_C"}.get(kind, "HIT_A")


def skill_fx(all_skills: dict, fx_names: list[str], names: dict[str, str]) -> dict:
    g = effect_groups(fx_names)
    out = {}
    for sid in all_skills:
        anims = next((g[k] for k in skill_keys(sid, all_skills, names) if k in g), None)
        if not anims:                                     # своего эффекта у навыка в игре нет — общий удар
            out[sid] = {"cast": [], "hit": [generic_hit(all_skills.get(sid, {}))], "generic": True}
            continue
        hits = [a for a in anims if re.search(r"HIT|_OUT$", a)]
        rest = [a for a in anims if a not in hits]
        if not hits and len(rest) > 1:                    # FIREBALL_1, _2, _3: последняя — попадание
            hits, rest = rest[-1:], rest[:-1]
        out[sid] = {"cast": rest, "hit": hits}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True)
    ap.add_argument("--text", default=None, help="распакованный Unicorn_US.CPK (английские названия навыков)")
    ap.add_argument("--force", action="store_true", help="перезаписать и то, что задано вручную")
    args = ap.parse_args()
    src = Path(args.src)
    remember_game_folder(src)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    units = json.loads((ROOT / "data" / "units.json").read_text(encoding="utf-8"))
    units = units.get("units", units)
    all_skills = json.loads((ROOT / "data" / "skills.json").read_text(encoding="utf-8"))
    all_skills = all_skills.get("skills", all_skills)
    ids = lambda lst: [x if isinstance(x, str) else x["id"] for x in lst]
    eng_names = align_names(Path(args.text) if args.text else src.parent / "unpacked_us")
    print(f"английских названий навыков игры: {len(eng_names)}")

    order = ("idle", "attack", "skill", "hit", "avoid", "guard", "cover", "die", "victory")
    config["states"] = {k: config["states"].get(k, {"chain": []}) for k in order}
    config["states"]["idle"].update(loop=True, chain=["^UPWARD$", "^UPWARD_IDLE$", "^UPWARD_END$"])
    config["states"]["cover"]["chain"] = ["^COVER_A\\d$"]
    stats = {"classes": 0, "skills": 0, "fx": 0, "bg": 0}
    for cid, spec in config["classes"].items():
        folder = spec.get("folder", "Chara")
        names = [a["name"] for a in MBS((src / folder / f"{spec['file']}.mbs").read_bytes()).anims if a["name"]]
        g = groups(names)
        states = spec.setdefault("states", {})
        for state, parts in class_states(names, g).items():
            if args.force or state not in states:
                states[state] = parts
        unit = units.get(cid, {})
        skill_ids = ids(unit.get("skills", [])) + [s for s in all_skills
                                                    if any(s.startswith(p + "_") for p in ids(unit.get("passives", [])))]
        mapped = class_skills(skill_ids, all_skills, g, ids(unit.get("passives", [])), eng_names)
        skills = spec.setdefault("skills", {})
        for sid, parts in mapped.items():
            if args.force or sid not in skills:
                skills[sid] = parts
        stats["classes"] += 1
        stats["skills"] += len(mapped)
    fx_names = [a["name"] for a in MBS((src / "Effect" / "Battle_Effect.mbs").read_bytes()).anims if a["name"]]
    fx = config.setdefault("skill_fx", {})
    for sid, entry in skill_fx(all_skills, fx_names, eng_names).items():
        if args.force or sid not in fx:
            fx[sid] = entry
            stats["fx"] += 1
    bgs = config.setdefault("backgrounds", {})
    for path in sorted((src / "BattleBG").glob("BGBt*.mbs")):
        if path.stem not in bgs or args.force:
            scene = next((s for rx, s in SCENES if rx.search(path.stem)), "default")
            bgs[path.stem] = {"use": True, "scene": scene, "floor": 420}
            stats["bg"] += 1
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"классов {stats['classes']}, навыков с анимацией {stats['skills']}, эффектов навыков {stats['fx']}, фонов {stats['bg']}")


if __name__ == "__main__":
    main()
