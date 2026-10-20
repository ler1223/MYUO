"""Описание анимации навыка: стандартная анимация класса, эффекты и полёт снаряда.

Данные лежат в data/uo_battle.json -> manual.animations и manual.skill_animations.
Здесь только разбор и проверка: редактор и показ боя работают с обычными словарями.

Стандартная анимация (animations.<id>) — это только куски тела класса и их длительности:
    {"class": "arbalist", "parts": ["ATTACK_1", "ATTACK_2"], "holds": {"0": 320}}

Анимация навыка (skill_animations.<skill_id>) добавляет к стандартной анимации то, что
относится к самому навыку:
    animation   — id стандартной анимации;
    tags        — подсказки для человека (в бою не участвуют);
    caster_fx   — эффекты на применяющем: [{"anim": ..., "start": мс, "end": мс}];
    target_fx   — эффекты на цели в момент попадания: смещения start/end от удара;
    trajectory  — необязательная кривая полёта снаряда;
    rain        — необязательный «дождь» эффектов по стороне противника.

У старой анимации (classes.<класс>.skills / skill_fx) нет этих полей — показ умеет
пользоваться ими, пока навык ещё не привязан к новой анимации.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

# Теги анимации — только подсказки в редакторе. Новые можно добавлять в редакторе;
# в боевых правилах они не используются.
ANIMATION_TAGS: dict[str, str] = {
    "melee": "ближний бой",
    "ranged": "дальний бой",
    "magic": "магия",
    "slash": "рубящий",
    "thrust": "колющий",
    "blunt": "дробящий",
    "bow": "лук",
    "crossbow": "арбалет",
    "gun": "огнестрел",
    "fire": "огонь",
    "ice": "лёд",
    "lightning": "молния",
    "holy": "свет",
    "dark": "тьма",
    "wind": "ветер",
    "earth": "земля",
    "poison": "яд",
    "lob": "навесная дуга",
    "rain": "дождь",
    "beam": "луч",
    "wave": "волна",
    "projectile": "снаряд",
    "dash": "рывок",
    "jump": "прыжок",
    "cast": "каст",
    "aoe": "по площади",
    "multi": "много ударов",
    "heal": "лечение",
    "buff": "усиление",
    "debuff": "ослабление",
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parts(raw: Any) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(item) for item in raw if str(item).strip()]


def _holds(raw: Any) -> dict[int, float]:
    if not isinstance(raw, Mapping):
        return {}
    out: dict[int, float] = {}
    for key, value in raw.items():
        try:
            index = int(key)
        except (TypeError, ValueError):
            continue
        ms = _number(value, -1)
        if index >= 0 and ms > 0:
            out[index] = ms
    return dict(sorted(out.items()))


def _strings(raw: Any) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    return list(dict.fromkeys(str(item) for item in raw if str(item).strip()))


def normalize_animation(animation_id: str, raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Стандартная анимация класса: части, их длительности и источник-класс."""
    raw = raw or {}
    return {
        "id": str(animation_id),
        "class": str(raw.get("class") or raw.get("source_name") or raw.get("source_class") or ""),
        "name": str(raw.get("name") or animation_id),
        "parts": _parts(raw.get("parts")),
        "holds": _holds(raw.get("holds")),
        "tags": _strings(raw.get("tags")),
    }


def normalize_fx(raw: Any) -> dict[str, Any] | None:
    """Эффект на применяющем/цели: анимация Battle_Effect и временной интервал."""
    if not isinstance(raw, Mapping):
        return None
    anim = str(raw.get("anim") or "").strip()
    if not anim:
        return None
    start = max(0.0, _number(raw.get("start"), 0.0))
    end = max(0.0, _number(raw.get("end"), 0.0))
    if end and end < start:
        end = start
    return {"anim": anim, "start": start, "end": end}


def normalize_fx_list(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, (list, tuple)):
        return []
    out = [normalize_fx(item) for item in raw]
    return [item for item in out if item is not None]


def normalize_curve(raw: Any) -> list[list[float]]:
    """Кривая полёта: точки [доля пути 0..1, подъём долей расстояния].

    Подъём отрицательный — вверх (ось Y экрана направлена вниз). Концы кривой
    всегда есть: начало (0, 0) и конец (1, 0), если их не задали.
    """
    points: list[list[float]] = []
    if isinstance(raw, (list, tuple)):
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                points.append([min(1.0, max(0.0, _number(item[0]))), _number(item[1])])
    points.sort(key=lambda p: p[0])
    if not points:
        return [[0.0, 0.0], [1.0, 0.0]]
    if points[0][0] > 0:
        points.insert(0, [0.0, 0.0])
    else:
        points[0][0] = 0.0
    if points[-1][0] < 1:
        points.append([1.0, 0.0])
    else:
        points[-1][0] = 1.0
    # Совпадающие x оставляем: это может быть вертикальный участок, но для полёта
    # снаряда полезнее уникальные точки. Последнюю из совпадающих сохраняем.
    compact: list[list[float]] = []
    for point in points:
        if compact and abs(point[0] - compact[-1][0]) < 1e-6:
            compact[-1] = point
        else:
            compact.append(point)
    return compact


def normalize_trajectory(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    curve = normalize_curve(raw.get("curve"))
    anim = str(raw.get("anim") or "").strip()
    speed = max(1.0, _number(raw.get("speed"), 60.0))
    fall = max(0.0, _number(raw.get("fall"), 0.0))
    if len(curve) <= 2 and not anim and fall <= 0:
        return None
    return {"anim": anim, "curve": curve, "speed": speed, "fall": fall}


def normalize_rain(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    entries: list[dict[str, Any]] = []
    for item in raw.get("entries", ()):
        if not isinstance(item, Mapping):
            continue
        anim = str(item.get("anim") or "").strip()
        count = int(_number(item.get("count"), 0))
        if anim and count > 0:
            entries.append({"anim": anim, "count": count})
    if not entries:
        return None
    duration = max(100.0, _number(raw.get("duration"), 1200.0))
    return {"duration": duration, "entries": entries}


def normalize_skill_animation(skill_id: str, raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Анимация навыка: ссылка на стандартную анимацию, эффекты, полёт, дождь, теги."""
    raw = raw or {}
    return {
        "skill": str(skill_id),
        "animation": str(raw.get("animation") or raw.get("anim") or ""),
        "tags": _strings(raw.get("tags")),
        "caster_fx": normalize_fx_list(raw.get("caster_fx")),
        "target_fx": normalize_fx_list(raw.get("target_fx")),
        "trajectory": normalize_trajectory(raw.get("trajectory")),
        "rain": normalize_rain(raw.get("rain")),
    }


def curve_point(points: Sequence[Sequence[float]], k: float) -> tuple[float, float]:
    """Точка кривой (доля пути, подъём) в доле k; плавная интерполяция по точкам."""
    pts = [(float(x), float(y)) for x, y in points] if points else [(0.0, 0.0), (1.0, 0.0)]
    if len(pts) == 1:
        return pts[0]
    k = min(1.0, max(0.0, float(k)))
    if k <= pts[0][0]:
        return pts[0]
    if k >= pts[-1][0]:
        return pts[-1]
    index = 0
    while index + 1 < len(pts) and k > pts[index + 1][0]:
        index += 1
    if index + 1 >= len(pts):
        return pts[-1]
    x0, y0 = pts[index]
    x1, y1 = pts[index + 1]
    if x1 - x0 < 1e-9:
        return x1, y1

    def slope(i: int) -> float:
        if i <= 0:
            return (pts[1][1] - pts[0][1]) / max(1e-9, pts[1][0] - pts[0][0])
        if i >= len(pts) - 1:
            return (pts[-1][1] - pts[-2][1]) / max(1e-9, pts[-1][0] - pts[-2][0])
        return (pts[i + 1][1] - pts[i - 1][1]) / max(1e-9, pts[i + 1][0] - pts[i - 1][0])

    h = x1 - x0
    t = (k - x0) / h
    m0, m1 = slope(index) * h, slope(index + 1) * h
    # Кубический Эрмит: плавный полёт без углов в заданных точках.
    h00 = 2 * t ** 3 - 3 * t ** 2 + 1
    h10 = t ** 3 - 2 * t ** 2 + t
    h01 = -2 * t ** 3 + 3 * t ** 2
    h11 = t ** 3 - t ** 2
    return k, h00 * y0 + h10 * m0 + h01 * y1 + h11 * m1


def curve_length(a: tuple[float, float], b: tuple[float, float], points: Sequence[Sequence[float]],
                 samples: int = 48) -> float:
    """Длина кривой в единицах сцены (для скорости полёта)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    dist = (dx * dx + dy * dy) ** 0.5
    total = 0.0
    prev = None
    for i in range(samples + 1):
        u, lift = curve_point(points, i / samples)
        point = (a[0] + dx * u, a[1] + dy * u + lift * dist)
        if prev is not None:
            total += ((point[0] - prev[0]) ** 2 + (point[1] - prev[1]) ** 2) ** 0.5
        prev = point
    return total


def from_manual(manual: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Разбор manual: (стандартные анимации, анимации навыков)."""
    animations = {
        str(key): normalize_animation(str(key), value)
        for key, value in (manual.get("animations") or {}).items()
        if isinstance(value, Mapping)
    }
    skills = {
        str(key): normalize_skill_animation(str(key), value)
        for key, value in (manual.get("skill_animations") or {}).items()
        if isinstance(value, Mapping)
    }
    # Старые композиты (manual.composites) были стандартными анимациями с источником.
    for key, value in (manual.get("composites") or {}).items():
        if not isinstance(value, Mapping) or key in animations:
            continue
        if (value.get("source_kind") or "unit") == "unit":
            animations[str(key)] = normalize_animation(str(key), {
                "class": value.get("source_name") or value.get("class") or "",
                "parts": value.get("parts") or [],
                "holds": value.get("holds") or {},
                "tags": value.get("tags") or [],
            })
    return animations, skills


def to_json(animations: Mapping[str, Mapping[str, Any]],
            skills: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Обратно в JSON-поля manual (ключи holds — строки, как в файле)."""
    return {
        "animations": {
            name: {
                "class": anim.get("class", ""),
                "name": anim.get("name", name),
                "parts": list(anim.get("parts", ())),
                "holds": {str(k): v for k, v in sorted((anim.get("holds") or {}).items())},
                "tags": list(anim.get("tags", ())),
            }
            for name, anim in sorted(animations.items())
        },
        "skill_animations": {
            skill_id: {
                "animation": spec.get("animation", ""),
                "tags": list(spec.get("tags", ())),
                "caster_fx": list(spec.get("caster_fx", ())),
                "target_fx": list(spec.get("target_fx", ())),
                "trajectory": spec.get("trajectory"),
                "rain": spec.get("rain"),
            }
            for skill_id, spec in sorted(skills.items())
        },
    }


def fx_end(start: float, end: float, native: float) -> float:
    """Длительность показа эффекта: заданный интервал, иначе родная длина анимации."""
    if end > start:
        return max(1.0, end - start)
    return max(1.0, native)
