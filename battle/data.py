"""Что показ боя берёт из Unicorn Overlord: data/uo_battle.json (tools/uo_battle/build.py) и сами куклы.

Куклы читаются engine.uo.library.source() (файлы игры, текстуры на видеокарте), их кадры —
сетками engine.uo.gl. Здесь — какой файл у класса, какие анимации у фаз боя и навыков, какие
эффекты у навыков, какой фон у сцены; длительности анимаций в мс.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from engine.uo.gl import GLRenderer
from engine.uo.library import source

from .animation import from_manual, normalize_skill_animation

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "data" / "uo_battle.json"
TICK_MS = 1000 / 60                  # анимации UO — 60 тиков в секунду
EFFECT_FILE = ("Effect", "Battle_Effect")
UI_FILES = {"hud": ("GUI", "Interface_Battle_00"), "ui": ("GUI", "Interface")}
ENABLED = os.environ.get("MYUO_UO_ANIM", "1") != "0"
# Замены анимаций, которых у модели нет: у женских моделей смерть — DIE_BLOW_1 + DIE_BLOW_2,
# у мужских — DIE (в uo_battle.json цепочка die записана по основной модели класса).
ANIM_ALIASES = {
    "DIE": ("DIE_BLOW_1", "DIE_BLOW_2"),
    "DIE_BLOW_1": ("DIE",),
    "DIE_BLOW_2": ("DIE",),
}


class ShowData:
    """Справочник показа: классы, навыки, сцены; модели кукол по требованию."""

    def __init__(self, path: Path = CONFIG):
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        manual = data.get("manual", {})
        self.classes: dict[str, dict] = {**data.get("classes", {})}
        for cid, over in manual.get("classes", {}).items():
            base = self.classes.get(cid, {})
            merged = {**base, **over}
            for key in ("skills", "phases", "timing", "skill_fx"):    # правка одного навыка не стирает остальные
                if isinstance(over.get(key), dict):
                    merged[key] = {**base.get(key, {}), **over[key]}
            self.classes[cid] = merged
        self.skills: dict[str, dict] = {**data.get("skills", {})}
        for sid, over in manual.get("skills", {}).items():
            self.skills[sid] = {**self.skills.get(sid, {}), **over}
        self.scenes: dict[str, str] = {**data.get("scenes", {}), **manual.get("scenes", {})}
        self.timing: dict[str, float] = {**data.get("timing", {}), **manual.get("timing", {})}
        # Новые анимации: стандартные анимации классов и анимации навыков (data/uo_battle.json,
        # раздел manual). Старые цепочки classes.<класс>.skills остаются запасным вариантом.
        self.animations, self.skill_animations = from_manual(manual)

    @property
    def ok(self) -> bool:
        """Есть папка игры и видеокарта: показ можно рисовать."""
        return ENABLED and source().ok and GLRenderer.get() is not None

    # --- модели ---

    def model(self, folder: str, file: str, variant: int = 0):
        return source().model(folder, file, variant) if self.ok else None

    def looks(self, class_id: str) -> list[dict]:
        """Модели класса (файл и вариант внешности); первая — его основная.
        `looks_extra` в manual добавляет именованных персонажей, не переписывая сборку."""
        info = self.classes.get(class_id, {})
        base = info.get("looks") or ([{"file": info["file"], "variant": 0}] if info.get("file") else [])
        return base + list(info.get("looks_extra") or ())

    def unit_model(self, class_id: str, look: int = 0):
        info = self.classes.get(class_id)
        looks = self.looks(class_id)
        if not info or not looks:
            return None
        chosen = looks[look % len(looks)]
        return self.model(info.get("folder", "Chara"), chosen["file"], int(chosen.get("variant", 0)))

    def effect_model(self):
        return self.model(*EFFECT_FILE)

    def ui_model(self, which: str = "hud"):
        return self.model(*UI_FILES[which])

    # --- анимации ---

    @staticmethod
    def length_ms(model, anim: str) -> float:
        if model is None or anim not in model.puppet.anims:
            return 0.0
        return model.length(anim) * TICK_MS

    @staticmethod
    def anim_names(model, name: str) -> list[str]:
        """Части цепочки → анимации модели: сама анимация, а если её нет — замена по ANIM_ALIASES
        (DIE у женской модели — это DIE_BLOW_1 + DIE_BLOW_2, у мужской вместо них — DIE)."""
        if model is None:
            return [name]
        anims = model.puppet.anims
        if name in anims:
            return [name]
        return [a for a in ANIM_ALIASES.get(name, ()) if a in anims]

    def lead_in_ms(self, model, anim: str) -> float:
        """Сколько анимация в начале ничего не показывает (все треки прозрачны или пусты), мс:
        у цифр урона UO ~18 тиков — число проявляется позже, чем запущено."""
        if model is None or anim not in model.puppet.anims:
            return 0.0
        key = (id(model), anim)
        cache = self.__dict__.setdefault("_lead_in", {})
        if key not in cache:
            puppet = model.puppet
            a = puppet.anims[anim]
            first = 0
            for tick in range(0, max(1, puppet.anim_length(anim))):
                items = [puppet.track_item(t, tick) for t in range(a["tstart"], a["tstart"] + a["tcount"])]
                if any(it is not None and it.tr["rgba"][3] > 0.05 for it in items):
                    first = tick
                    break
            cache[key] = first * TICK_MS
        return cache[key]

    def phase(self, class_id: str, name: str) -> list[str]:
        """Части фазы («*» в конце — по кругу); пусто, если у класса такой нет."""
        return list(self.classes.get(class_id, {}).get("phases", {}).get(name, []))

    def skill_chain(self, class_id: str, skill_id: str) -> list[str]:
        """Части тела: из привязанной стандартной анимации, иначе старая цепочка класса."""
        animation = self.animation(skill_id)
        if animation is not None and animation.get("parts"):
            return list(animation["parts"])
        return list(self.classes.get(class_id, {}).get("skills", {}).get(skill_id, []))

    def animation(self, skill_id: str) -> Optional[dict[str, Any]]:
        """Стандартная анимация, привязанная к навыку (None — навык ещё на старой анимации)."""
        spec = self.skill_animations.get(skill_id)
        if not spec or not spec.get("animation"):
            return None
        return self.animations.get(spec["animation"])

    def animation_holds(self, skill_id: str) -> dict[int, float]:
        animation = self.animation(skill_id)
        return dict(animation.get("holds", {})) if animation is not None else {}

    def skill_animation(self, skill_id: str) -> Optional[dict[str, Any]]:
        """Описание анимации навыка (эффекты, траектория, дождь, теги) или None."""
        return self.skill_animations.get(skill_id)

    def animation_tags(self, skill_id: str) -> list[str]:
        spec = self.skill_animations.get(skill_id)
        return list(spec.get("tags", ())) if spec else []

    def skill(self, skill_id: str, class_id: Optional[str] = None) -> dict[str, Any]:
        """Эффекты навыка; у класса может быть своя правка (редактор навыков: classes.<класс>.skill_fx)."""
        base = self.skills.get(skill_id, {"kind": "melee", "cast": [], "hit": ["HIT_A"]})
        own = self.classes.get(class_id or "", {}).get("skill_fx", {}).get(skill_id)
        return {**base, **own} if own else base

    def skill_timing(self, class_id: str, skill_id: str) -> dict[str, Any]:
        """Ручные моменты навыка класса (редактор навыков: classes.<класс>.timing): hits — удары, мс от начала
        цепочки; holds — длительность частей {номер: мс}; approach / ret — подход и возврат (auto, none, dash,
        jump, chain, back) с approach_from / approach_to / ret_from, мс."""
        return dict(self.classes.get(class_id, {}).get("timing", {}).get(skill_id, {}))

    def ticks(self, key: str, default: float) -> float:
        """Тайминг боя UO (timing) в мс; нет в данных — default тиков."""
        return self.timing.get(key, default) * TICK_MS

    def scene(self, scene_id: Optional[str]) -> Optional[str]:
        return self.scenes.get(scene_id or "default") or self.scenes.get("default")
