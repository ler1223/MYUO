"""Собрать data/uo_battle.json — что показ боя (battle/) берёт из файлов Unicorn Overlord.

    python tools/uo_battle/build.py [--src <распакованный Unicorn.CPK>] [--text <распакованный Unicorn_US.CPK>]

По умолчанию папки — F:/MYUO2/unpacked и <src>/../unpacked_us (или из assets/uo_anim/local.json).
Уже заданное вручную в разделах "manual" не трогается.

Что собирается:
- classes.<класс>: файл персонажа (Chara/<имя>.mbs): английское название класса (UcClassList) ->
  внутреннее имя (_UcEnum_Class: LORD, WHITE_KNIGHT, ..._HG — повышенный) -> файл с тем же именем и
  полом (data/names.json, female_classes); анимации боя по фазам (docs/uo/battle.md):
  stance (стойка по кругу), dash/stop (разбег, торможение), back/home (бег назад, разворот),
  jump/land, hit, guard, avoid, cover, die, down, victory; цепочки ударов (ATTACK_A1..A4,
  MAGIC_A..MAGIC_A_END, S##_<НАВЫК>_*) и какой навык класса какую играет.
- skills.<навык>: внутреннее имя (UcSkillList выровнен с _UcEnum_Skill), вид (ближний, дальний, магия,
  лечение, поддержка), эффекты из Effect/Battle_Effect.mbs: cast — на применившем, out — вылет снаряда,
  shot — сам снаряд (летит к цели: anim, speed — единиц за тик, volley — [dx, dy, задержка в тиках]
  каждого снаряда залпа, fall — ускорение падения у навесных), trail — след снаряда (軌跡, エフェクト),
  buffer — предвестник на цели перед главным эффектом (予兆, *_BUFFER), hit — на цели. Роли эффектов —
  по перечислению игры EFFECTID (Debug/_UcEnum_Buff.inc, engine.uo.enums). Скорости и залпы —
  из настроек игры DbReg/DbRegDb.drg (группа BTSHOT, engine.uo.drg).
- classes.<класс>.shot: снаряд оружия класса (стрела, болт, нож, копьё, томагавк) для дальних
  навыков без своего снаряда.
- timing: тайминги боя из настроек игры (тики, 60 в секунду): разбег к цели, возврат, гибель,
  когда начинает следующий, остановка удара (hitstop) на крите и блоке.
- scenes.<сцена башни>: фон боя BattleBG/BGBt*.mbs.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.uo.drg import DbReg  # noqa: E402
from engine.uo.puppet import Puppet  # noqa: E402

OUT = ROOT / "data" / "uo_battle.json"
LOCAL = ROOT / "assets" / "uo_anim" / "local.json"
# Своих файлов у этих классов нет: персонаж с этим классом в игре (принцессы, принцы, особые).
UNIQUE = {"ALBION_PRINCESS": "Scarlet_F", "CORNIA_PRINCESS": "Virginia_F", "ELHEIM_PRINCESS_W": "Eltlinde_F00",
          "ELHEIM_PRINCESS_B": "Eltlinde_F10", "BASTORIAS_PRINCESS": "Ranger_F", "PRINCE": "Prince_M",
          "DARK_PRINCE": "BlackPrince_M", "NECROMANCER": "Necromancer_M", "DREADNOUGHT": "Armoria_HG_F"}
# В файлах игры нет своей модели (только текст справки): временно играет модель похожего класса; настоящую
# выбирают в редакторе показа навыков (manual.classes.<класс>.file), помечено "stand_in"
STAND_IN = {"PALADIN": "WhiteKnight_HG_M", "WERELION": "WereWolf_M"}
SCENES = {   # сцена башни -> слои фона: небо (*_b), сама сцена; персонажи стоят на её земле
    "default": ["BGBtPlain_b", "BGBtPlain_a"], "forest": ["BGBtElfPlain_b", "BGBtElfPlain_a"],
    "winter": ["BGBtSnowRuins_b", "BGBtSnowRuins_a"], "desert": ["BGBtDesertPlain_b", "BGBtDesertPlain_a"],
    "lava": ["BGBtPlain_A_b", "BGBtWasteland_a"], "castle": ["BGBtCapital_D_b", "BGBtCapital_D_a"]}
# Общие эффекты попадания по виду удара и стихии (docs/uo/battle.md, «Эффекты»)
GENERIC_HIT = {"melee": "HIT_A", "ranged": "HIT_C", "magic": "HIT_A_MAGIC", "fire": "HIT_A_FIRE",
               "ice": "HIT_A_ICE", "poison": "HIT_A_POIZON", "heal": "HEAL_HIT_01", "support": "STATUS_UP_A"}
ELEMENT_TAGS = ("fire", "ice", "poison")
# Снаряды Battle_Effect: анимация на месте (след позади, летит вправо), двигает её код игры
SHOT_NAME = re.compile(r"(SHOT|SPEAR|MISSILE|FIREBALL|TOMAHAWK|ROLLAXE|DARTS|SONICSHAFT|AIRTHRUST_\d+|CHASE_MAGIC)"
                       r"(_BLIND|_POISON|_FIRE|_HG)?$")
NOT_SHOT = ("SHOT_EFFECT", "SHOT_EFFECT_FIRE", "LINESHOT_OUT", "MULTISHOT_OUT")
# Снаряд оружия класса (по файлу персонажа) и его скорость в BTSHOT; навесные — с FALLSPEED
CLASS_SHOTS = {"Hunter": ("BOW_SHOT", "HUNTER_SHOT"), "ElfArcher": ("BOW_SHOT", "ELFARCHER_PARABOLASHOT"),
               "Ranger": ("CROSSBOW_SHOT", "RANGER_POWSHOT"), "Thief": ("KNIFE_SHOT", "THIEF_SHOT"),
               "Soldier": ("SPEAR", "SOLDIER_PARABOLASHOT"), "Huscarl": ("TOMAHAWK", "HUSCARL_PARABOLASHOT")}
# Тайминги боя: ключ timing -> имя настройки (ищется во всех группах боя BT*)
TIMING = {"move_attack": "MOVETIME_ATTACK", "return_front": "MOVETIME_RETURN_FF", "return_back": "MOVETIME_RETURN_RR",
          "die_wait": "DIE_WAIT_TIME", "die_fade": "DIE_FADE_TIME", "next_start": "NEXT_PLAYSTART_RETURN_RATE",
          "hitstop_crit": "ADD_HITSTOP_TIME_CRITICAL", "hitstop_guard": "ADD_HITSTOP_TIME_GUARD",
          "attack_range": "ATTACK_RANGE_BASE", "zoom_attack": "ZOOM_ATTACK", "zoom_all": "ZOOM_ATTACK_ALL",
          "zoom_skill": "ZOOM_SKILL_START"}
SHOT_GROUPS = ("BTSHOT", "BTACTION")       # где искать <ИМЯ>_SPEED (THIEF_SHOT_SPEED — в BTACTION)
# Внутреннее имя навыка -> имя его эффектов, когда они не совпадают (по японскому названию в _UcEnum_Skill)
# Навык -> имя его слота анимаций класса, когда они не совпадают (Ледяной дождь — дождь стрел)
SLOT_ALIAS = {"GRACIALRAIN": "ARROWRAIN"}
# Дождь стрел (EFFECTID ARROWRAIN_OUT 発動, ARROWRAIN_HIT_01/02; BTSHOT ARROWRAIN_*): выстрел вверх, стрелы
# падают на цели. У навыков-дождей без своих эффектов (GRACIAL_RAIN_EFFECT/HIT в файле эффектов нет) — те же
RAIN_FX = {"out": "ARROWRAIN_OUT", "hit": ["ARROWRAIN_HIT_01", "ARROWRAIN_HIT_02"]}
RAIN_PARAMS = {"speed": "ARROWRAIN_SPEED", "start_x": "ARROWRAIN_START_POS_X", "interval_x": "ARROWRAIN_INTERVAL_X",
               "interval": "ARROWRAIN_INTERVAL_TIME", "rand_from": "ARROWRAIN_TIME_RAND_START",
               "rand_to": "ARROWRAIN_TIME_RAND_END"}
EFFECT_ALIAS = {"MAGIC_A_WATER_0": "ICESHOT",     # アイスショット — Icebolt
                "TOXIC_THROW": "KNIFE_SHOT_POISON", "BLIND_THROW": "KNIFE_SHOT_BLIND"}   # EFFECTID TOXIC_THROW, BLIND_THROW
# След выстрела стрелой и болтом (EFFECTID SHOT_ARROW_EFFECT 矢：エフェクト)
ARROW_TRAIL = {"BOW_SHOT": "SHOT_EFFECT", "CROSSBOW_SHOT": "SHOT_EFFECT", "BOW_SHOT_FIRE": "SHOT_EFFECT_FIRE",
               "CROSSBOW_SHOT_FIRE": "SHOT_EFFECT_FIRE"}


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def sheet(path: Path) -> list[str]:
    data = path.read_bytes()
    start = next(i for i in range(0x20, len(data)) if data[i])
    return [b.decode("utf-8", "replace") for b in data[start:].split(b"\0")]


def enum(path: Path) -> list[str]:
    return [line.split(",")[0].strip() for line in path.read_text(encoding="utf-8-sig").splitlines()[1:]
            if "," in line]


def align(names: list[str], internal: list[str]) -> dict[str, str]:
    """Английские названия -> внутренние имена: два списка в одном порядке, но с лишними и
    вольными переводами; выравнивание по похожести (динамическое программирование)."""
    a, b = [norm(n) for n in names], [norm(i) for i in internal]
    gap = -0.55
    n, m = len(a), len(b)
    score = [[0.0] * (m + 1) for _ in range(n + 1)]
    back = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        score[i][0], back[i][0] = i * gap, 1
    for j in range(1, m + 1):
        score[0][j], back[0][j] = j * gap, 2
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sim = difflib.SequenceMatcher(None, a[i - 1], b[j - 1]).ratio()
            options = ((score[i - 1][j - 1] + sim, 0), (score[i - 1][j] + gap, 1), (score[i][j - 1] + gap, 2))
            score[i][j], back[i][j] = max(options)
    i, j, pairs = n, m, {}
    while i and j:
        step = back[i][j]
        if step == 0:
            pairs[names[i - 1]] = internal[j - 1]
            i, j = i - 1, j - 1
        elif step == 1:
            i -= 1
        else:
            j -= 1
    return pairs


# --- классы -------------------------------------------------------------------

def class_files(text: Path, chara: Path, units: dict, female: set) -> dict[str, dict]:
    english = [t for t in sheet(text / "MsgSheet" / "UcClassList.fms")][:80]
    internal = enum(text / "Debug" / "_UcEnum_Class.inc")
    internal = internal[:internal.index("CLASSTYPE_END")] if "CLASSTYPE_END" in internal else internal
    by_name = {}
    for name, code in zip(english, internal):
        by_name.setdefault(norm(name), code)
    files = {norm(p.stem): p.stem for p in chara.glob("*.mbs")}
    out = {}
    for class_id, unit in units.items():
        code = by_name.get(norm(unit["name"]))
        if code is None:
            continue
        promoted = code.endswith("_HG")
        base = code[:-3] if promoted else code
        gender = "F" if class_id in female else "M"
        if base in UNIQUE:
            stem = UNIQUE[base]
        elif base in STAND_IN:
            out[class_id] = {"code": code, "file": STAND_IN[base], "stand_in": True}
            continue
        else:
            stem = None
            for g in (gender, "M" if gender == "F" else "F"):
                for hg in ((True, False) if promoted else (False,)):
                    key = norm(base) + ("hg" if hg else "") + g.lower()
                    if key in files:
                        stem = files[key]
                        break
                if stem:
                    break
        if stem and (chara / f"{stem}.mbs").is_file():
            out[class_id] = {"code": code, "file": stem}
    return out


# Не части цепочки: показ в энциклопедии классов, подготовка, эффект класса, варианты «вперёд/назад»
SKIP_PART = re.compile(r"(_CLASSPEDIA|_PREACTION|_START|_EFFECT|_EX\d*|\d_[FB](_ATK)?)$")
MIN_PART = 3                 # тиков: короче — заглушка (у бойца ATTACK_C1..E по 1 тику)


def key_of(name: str) -> str:
    """База цепочки: ATTACK_B2 -> ATTACK_B, MAGIC_A_IDLE -> MAGIC_A, ATTACK_1 -> ATTACK."""
    m = re.match(r"^(ATTACK|MAGIC|SKILL)(?:_([A-Z])(?=\d|_|$))?", name)
    return (m.group(1) + (f"_{m.group(2)}" if m.group(2) else "")) if m else re.sub(r"_?\d+$", "", name)


def normalize_chain(names: list[str], lengths: dict[str, int], prefix: str = "") -> list[str]:
    """Части одной цепочки по порядку файла, без лишнего:
    - служебные анимации и заглушки (SKIP_PART, короче MIN_PART тиков);
    - слитная версия (ATTACK_A), если есть разбитая на части (ATTACK_A1..A4): разбитая нужна, чтобы
      между частями шло перемещение;
    - X_TO_IDLE — окончание «удар и сразу в стойку»: заменяет X и всё, что шло после него (A2, A_END)."""
    stem = lambda n: n[len(prefix):] if prefix and n.startswith(prefix) else n
    parts = [n for n in names if not SKIP_PART.search(n) and lengths.get(n, 0) >= MIN_PART]
    stems = [stem(n) for n in parts]
    base = key_of(stems[0]) if stems else ""
    # слитная версия — сама база группы (ATTACK_A), когда есть её части с номерами (ATTACK_A1)
    parts = [n for n, st in zip(parts, stems)
             if not (st == base and any(re.fullmatch(re.escape(base) + r"\d+", o) for o in stems))]
    # окончание после одного выстрела (X_END), когда есть окончание после второго (X_END2)
    parts = [n for n in parts if not (n.endswith("_END") and n + "2" in parts)]
    for n in list(parts):
        if n.endswith("_TO_IDLE"):
            plain = n[:-len("_TO_IDLE")]
            if plain in parts:
                cut = parts.index(plain)
                parts = parts[:cut] + [n]
            else:
                parts = parts[:parts.index(n) + 1]
            break
    return parts


def chains(anims: list[str], lengths: dict[str, int] | None = None) -> dict[str, list[str]]:
    """Цепочки ударов файла: ATTACK_A1..A4 -> ATTACK_A, MAGIC_A, MAGIC_A_IDLE, MAGIC_A_2.. -> MAGIC_A,
    S03_ATTACK_C1.. -> S03; по порядку в файле, без лишних частей (normalize_chain)."""
    out: dict[str, list[str]] = {}
    for name in anims:
        slot = re.match(r"^(S\d\d)_", name)
        if slot:
            key = slot.group(1)
        else:
            # буква цепочки — одна буква перед цифрой, «_» или концом имени (ATTACK_B2, MAGIC_A_IDLE, ATTACK_C);
            # ATTACK_IDLE, ATTACK_END, ATTACK_1 — цепочка без буквы
            m = re.match(r"^(ATTACK|MAGIC|SKILL)(?:_([A-Z])(?=\d|_|$))?", name)
            if not m:
                continue
            key = m.group(1) + (f"_{m.group(2)}" if m.group(2) else "")
        out.setdefault(key, []).append(name)
    if lengths is None:
        return out
    cleaned = {}
    for key, names in out.items():
        parts = normalize_chain(names, lengths, f"{key}_" if re.match(r"^S\d\d$", key) else "")
        if parts:
            cleaned[key] = parts
    return cleaned


def phases(p: Puppet) -> dict[str, list[str]]:
    """Анимации боя по фазам; «*» в конце — часть идёт по кругу, пока фаза не сменится."""
    has = set(p.anims)
    pick = lambda *names: [n for n in names if n.rstrip("*") in has]
    out = {
        # ожидание в бою — IDLE по кругу (у FACE_BATTLE, мимики боя, та же длина). STANCE_1..3 — поза приказа
        # или навыка (длины совпадают с ORDER_1..3 и SKILL_A1..3); UPWARD_IDLE похожа, но это не стойка боя
        "stance": pick("IDLE*"),
        "dash": pick("DASH_1"), "stop": pick("DASH_2"),
        "back": pick("BACK_1"), "home": pick("BACK_2"),
        "jump": pick("JUMP_1"), "land": pick("JUMP_2"),
        "hit": pick("KNOCKBACK"), "guard": pick("GUARD"), "avoid": pick("AVOID"),
        "cover": pick("COVER_A1", "COVER_A2"),
        "die": pick("DIE_BLOW_1", "DIE_BLOW_2") if "DIE_BLOW_1" in has else pick("DIE"),
        "down": pick("DOWN", "DOWN_IDLE*"),
        "victory": pick("VICTORY_1", "VICTORY_2*"),
        "charge": pick("SKILL_A1", "SKILL_A2*"), "release": pick("SKILL_A3"),
    }
    return {k: v for k, v in out.items() if v}


def skill_kind(skill: dict) -> str:
    parts = skill.get("parts", [])
    if parts and all(pt["kind"] != "damage" for pt in parts):
        return "heal"
    if not parts:
        return "support"
    tags = skill.get("tags", [])
    if "magic" in tags:
        return "magic"
    return "ranged" if "ranged" in tags else "melee"


def class_skills(p: Puppet, unit: dict, skills: dict, internal: dict[str, str]) -> dict[str, list[str]]:
    """Какой цепочкой файла играть каждый активный навык класса."""
    found = chains(list(p.anims), {n: p.anim_length(n) for n in p.anims})
    slots = {k: v for k, v in found.items() if re.match(r"^S\d\d$", k)}
    plain = {k: v for k, v in found.items() if not re.match(r"^S\d\d$", k) and k != "SKILL"}
    magic = [k for k in plain if k.startswith("MAGIC")]
    attack = [k for k in plain if k.startswith("ATTACK")]
    used: dict[str, int] = {"magic": 0, "attack": 0}
    out = {}
    ids = [s if isinstance(s, str) else s["id"] for s in unit.get("skills", [])]
    for sid in ids:
        skill = skills.get(sid)
        if skill is None:
            continue
        code = norm(internal.get(skill["name"], ""))
        code = norm(SLOT_ALIAS.get(code.upper(), code))
        # именной слот: анимации слотов, в имени которых стоит навык (дождь лежит в двух слотах:
        # S05_ARROW_RAIN_1/2 и S06_ARROW_RAIN_3), по порядку файла
        named = [n for v in slots.values() for n in v if code and code in norm(re.sub(r"_?\d+$", "", n[4:]))]
        if named:
            out[sid] = named
            continue
        kind = skill_kind(skill)
        pool, key = (magic, "magic") if kind in ("magic", "heal", "support") and magic else (attack or magic, "attack")
        if not pool:
            continue
        out[sid] = plain[pool[used[key] % len(pool)]]
        used[key] += 1
    return out


# --- эффекты -------------------------------------------------------------------

def effect_groups(effect: Puppet) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for name in effect.anims:
        key = re.sub(r"(_[A-Z]?\d+[A-Z]?|_HIT|_OUT|_EFFECT|_BUFFER|_LOOP.*|_END.*|_B|_C|_S)+$", "", name)
        groups.setdefault(norm(key), []).append(name)
    return groups


def is_shot(name: str) -> bool:
    return bool(SHOT_NAME.search(name)) and name not in NOT_SHOT


def param(reg: DbReg, key: str) -> float | None:
    for group in SHOT_GROUPS:
        found = reg[group].get(key)
        if found is not None:
            return found.value
    return None


def shot_info(reg: DbReg, anim: str, key: str | None = None) -> dict:
    """Снаряд: скорость (единиц за тик), залп (смещение от руки и задержка каждого), падение."""
    base = key or norm(anim).upper()
    keys = [base] if key else [k[:-len("_SPEED")] for g in SHOT_GROUPS for k in reg[g] if k.endswith("_SPEED")
                               and norm(k[:-len("_SPEED")]) in (norm(anim), norm(re.sub(r"_\d+$", "", anim)))]
    prefix = keys[0] if keys else None
    speed = param(reg, f"{prefix}_SPEED") if prefix else None
    out = {"anim": anim}
    if speed:
        out["speed"] = speed                 # нет своей — у показа скорость оружия класса или DEFAULT_SPEED
    fall = param(reg, f"{prefix}_FALLSPEED") if prefix else None
    if fall:
        out["fall"] = fall
    volley = []
    while prefix and param(reg, f"{prefix}_{len(volley)}_OFFSET_X") is not None:
        i = len(volley)
        volley.append([param(reg, f"{prefix}_{i}_OFFSET_X"), param(reg, f"{prefix}_{i}_OFFSET_Y") or 0.0,
                       param(reg, f"{prefix}_{i}_WAITTIME") or 0.0])
    if volley:
        out["volley"] = volley
    return out


def skill_effects(skill: dict, code: str, effect: Puppet, groups: dict[str, list[str]], reg: DbReg) -> dict:
    kind = skill_kind(skill)
    names = (groups.get(norm(code)) or groups.get(norm(EFFECT_ALIAS.get(code, "")), [])) if code else []
    shots = [n for n in names if is_shot(n)]
    out = [n for n in names if n.endswith("_OUT")]
    buffer = [n for n in names if n.endswith("_BUFFER")]
    trail = [n for n in names if n.endswith("_EFFECT") and "HIT" not in n]
    cast = [n for n in names if "HIT" not in n and not n.endswith("_OUT") and n not in shots + buffer + trail]
    hit = [n for n in names if "HIT" in n]
    if not hit:
        element = next((t for p in skill.get("parts", []) for t in p.get("tags", []) if t in ELEMENT_TAGS), None)
        generic = GENERIC_HIT.get(element) if element and kind != "heal" else GENERIC_HIT.get(kind)
        if generic in effect.anims:
            hit = [generic]
    info = {"kind": kind, "internal": code, "cast": cast[:2], "hit": hit[:2]}
    if out:
        info["out"] = out[0]
    if shots:
        info["shot"] = shot_info(reg, shots[0])
        if trail:
            info["shot"]["trail"] = trail[0]
    if buffer:
        info["buffer"] = buffer
    if code.endswith("RAIN"):                    # дождь стрел: выстрел вверх, стрелы падают на цели
        rain = {k: param(reg, v) for k, v in RAIN_PARAMS.items()}
        info["rain"] = {**RAIN_FX, **{k: v for k, v in rain.items() if v is not None}}
        info["hit"] = RAIN_FX["hit"]
    return info


def class_looks(chara: Path, own: str, code: str) -> list[dict]:
    """Модели класса: его файл и файл того же класса другого пола (Soldier_M <-> Soldier_F), в каждом —
    все варианты внешности (первая группа вариантов деталей: головы, причёски)."""
    files = [own]
    m = re.match(r"^(.*)_([MF])$", own)
    if m and code.split("_HG")[0] not in UNIQUE:
        other = f"{m.group(1)}_{'F' if m.group(2) == 'M' else 'M'}"
        if (chara / f"{other}.mbs").is_file():
            files.append(other)
    looks = []
    for file in files:
        count = len(Puppet((chara / f"{file}.mbs").read_bytes(), 0).variant_combos())
        looks += [{"file": file, "variant": i} for i in range(count)]
    return looks


def battle_timing(reg: DbReg) -> dict[str, float]:
    found = {p.name: p.value for p in reversed(reg.params) if p.group.startswith("BT")}
    return {key: round(found[name], 4) for key, name in TIMING.items() if name in found}


def class_shot(file: str, reg: DbReg, effect: Puppet) -> dict | None:
    base = re.sub(r"(_HG)?_[MF]\d*$", "", file)
    found = CLASS_SHOTS.get(base)
    if found is None or found[0] not in effect.anims:
        return None
    anim = found[0] + ("_HG" if "_HG_" in file and found[0] + "_HG" in effect.anims else "")
    info = shot_info(reg, anim, found[1])
    info.setdefault("speed", param(reg, "DEFAULT_SPEED") or 60.0)
    if ARROW_TRAIL.get(anim) in effect.anims:
        info["trail"] = ARROW_TRAIL[anim]
    return info


def main() -> None:
    local = json.loads(LOCAL.read_text(encoding="utf-8")) if LOCAL.is_file() else {}
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default=local.get("src", "F:/MYUO2/unpacked"))
    parser.add_argument("--text")
    args = parser.parse_args()
    src = Path(args.src)
    text = Path(args.text) if args.text else src.parent / "unpacked_us"
    units = json.loads((ROOT / "data" / "units.json").read_text(encoding="utf-8"))
    skills = json.loads((ROOT / "data" / "skills.json").read_text(encoding="utf-8"))
    female = set(json.loads((ROOT / "data" / "names.json").read_text(encoding="utf-8")).get("female_classes", []))
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else {}
    manual = old.get("manual", {"classes": {}, "skills": {}, "scenes": {}})

    english = [re.sub(r"^\((A|P)\) ", "", t) for t in sheet(text / "MsgSheet" / "UcSkillList.fms")
               if re.match(r"^\((A|P)\) ", t)]
    internal = [e for e in enum(text / "Debug" / "_UcEnum_Skill.inc") if re.match(r"^(ACT|PAS)_", e)
                and not e.startswith("ACT_ASSIST") and not e.endswith(("_START", "_END", "_SKILL_P"))]
    pairs = {k: re.sub(r"^(ACT|PAS)_", "", v) for k, v in align(english, internal).items()}

    files = class_files(text, src / "Chara", units, female)
    classes = {}
    for class_id, info in sorted(files.items()):
        p = Puppet((src / "Chara" / f"{info['file']}.mbs").read_bytes(), 0)
        classes[class_id] = {"code": info["code"], "file": info["file"], **({"stand_in": True} if info.get("stand_in") else {}),
                             "phases": phases(p),
                             "skills": class_skills(p, units[class_id], skills, pairs),
                             "looks": class_looks(src / "Chara", info["file"], info["code"])}
    effect = Puppet((src / "Effect" / "Battle_Effect.mbs").read_bytes(), 0)
    reg = DbReg(src / "DbReg" / "DbRegDb.drg")
    for class_id, info in classes.items():
        shot = class_shot(info["file"], reg, effect)
        if shot:
            info["shot"] = shot
    groups = effect_groups(effect)
    skill_out = {sid: skill_effects(s, pairs.get(s["name"], ""), effect, groups, reg)
                 for sid, s in sorted(skills.items())}
    scenes = {k: [f for f in v if (src / "BattleBG" / f"{f}.mbs").is_file()] for k, v in SCENES.items()}
    data = {
        "_comment": "Показ боя UO (battle/): собирает tools/uo_battle/build.py из файлов игры; правки — в manual "
                    "(те же разделы: classes, skills, scenes), они важнее собранного.",
        "classes": classes, "skills": skill_out, "scenes": scenes,
        "timing": battle_timing(reg), "manual": manual,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    missing = sorted(set(units) - set(classes))
    print(f"classes {len(classes)}/{len(units)} (без файла: {', '.join(missing)}), skills {len(skill_out)}, "
          f"с эффектами навыка: {sum(bool(v['cast']) for v in skill_out.values())}, "
          f"со своим снарядом: {sum('shot' in v for v in skill_out.values())}, "
          f"классов со снарядом оружия: {sum('shot' in v for v in classes.values())}")


if __name__ == "__main__":
    main()
