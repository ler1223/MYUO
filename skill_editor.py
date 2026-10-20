"""Редактор показа навыков (анимации UO): python skill_editor.py

Один редактор для двух вещей:
- стандартные анимации класса — набор частей тела и их длительности (библиотека «Анимации»);
- анимация навыка — какая стандартная анимация привязана, эффекты на применяющем и на цели,
  траектория снаряда (визуальная кривая) и «дождь» эффектов по стороне противника.

Анимация навыка хранится одна на навык: одинаковый навык у класса и у предмета показывает одно
и то же. Эффекты и траектория — дополнительные слои поверх стандартной анимации.

Слева — классы, затем все доступные классу навыки: его собственные и навыки всех предметов,
которые можно надеть в его слоты. Фильтр — только по тегам атаки (ближний/дальний/магия).
Внизу: параметры анимации навыка, тайминги ударов/подхода/возврата, эффекты, полёт, дождь, теги.

Предпросмотр — сцена боя против манекена с несохранёнными правками; шкала под ней: части цепочки,
удары (красные), подход (синий), возврат (зелёный); клик по шкале — перейти в момент.

Клавиши: пробел — пауза, ←/→ — кадр, 1-4 — скорость, Ctrl+S — сохранить,
Esc — закрыть модальное окно, C — библиотека стандартных анимаций, T — редактор кривой полёта.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional

import pygame

from battle.animation import ANIMATION_TAGS, curve_point, normalize_curve, normalize_skill_animation, to_json

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "data" / "uo_battle.json"
SIZE = (1600, 900)
FPS = 60
TICK = 1000 / 60

BG = (24, 26, 32)
PANEL = (34, 37, 46)
TEXT = (225, 225, 230)
DIM = (140, 145, 160)
HIT = (230, 80, 70)
GO = (90, 140, 240)
BACK = (90, 200, 110)
WARN = (240, 190, 60)
GOOD = (120, 210, 140)
MISSING = (225, 100, 100)

PICKER_BOX = pygame.Rect(300, 60, 1000, 780)
ANIM_BOX = pygame.Rect(70, 20, 1460, 860)
CURVE_BOX = pygame.Rect(190, 80, 1220, 700)

APPROACH = (("auto", "по событиям"), ("none", "нет"), ("dash", "разбег"), ("jump", "прыжок"), ("chain", "в цепочке"))
RETURN = (("auto", "по событиям"), ("back", "бег назад"), ("jump", "прыжок"), ("chain", "в цепочке"))
EVENT_COLORS = {0: HIT, 1: GO, 2: (200, 120, 240), 3: (80, 210, 220)}
EVENT_NAMES = {0: "удар", 1: "движение", 2: "получает удар", 3: "остановка"}
FX_TABS = (("fx", "Эффекты"), ("trajectory", "Полёт"), ("rain", "Дождь"), ("tags", "Теги"))


class Picker:
    def __init__(self, title: str, options: list[str], on_pick: Callable[[str], None], preview=None):
        self.title, self.options, self.on_pick, self.preview = title, options, on_pick, preview
        self.filter = ""
        self.scroll = 0
        self.hover: Optional[str] = None
        self.fresh = True

    def visible(self) -> list[str]:
        f = self.filter.upper()
        return [o for o in self.options if f in o.upper()]


class Editor:
    def __init__(self):
        from battle.data import ShowData
        from game.database import Database
        self.db = Database.load()
        self.data = ShowData()
        if not self.data.ok:
            raise SystemExit("Нет папки игры или видеокарты (moderngl): показ кукол недоступен.")
        self.effect_names = sorted(n for n in self.data.effect_model().puppet.anims if n)
        self.classes = sorted(c for c, v in self.data.classes.items() if v.get("file"))
        self.cls = self.classes[0]
        self.sid: Optional[str] = None
        self.skill_filter = ""
        self.edit: dict = {}
        self.player: Any = None
        self.tick = 0.0
        self.speed = 1.0
        self.paused = False
        self.picker: Optional[Picker] = None
        self.message = ""
        self.dirty = False
        self.preview_cache: dict = {}

        # новые данные: стандартные анимации и анимации навыков
        self.animations: dict[str, dict] = copy.deepcopy(self.data.animations)
        self.skill_animations: dict[str, dict] = copy.deepcopy(self.data.skill_animations)
        self.anim_name: Optional[str] = None
        self.anim_edit: dict = {"class": self.cls, "name": "", "parts": [], "holds": {}}
        self.anim_only_current = True
        self.anim_modal = False
        self.anim_preview = None
        self.anim_preview_key: Any = None
        self.anim_preview_cache: dict = {}

        # визуальный редактор кривой полёта
        self.curve_modal = False
        self.curve_drag: Optional[int] = None
        self.curve_selected: Optional[int] = None
        self.fx_tab = "fx"
        self._sync_data()
        self.select_class(self.cls)

    # --- данные ---

    def _sync_data(self) -> None:
        """Показ читает те же словари, которые правит редактор (без перезагрузки файла)."""
        self.data.animations = self.animations
        self.data.skill_animations = self.skill_animations

    def class_skill_ids(self, cls: str) -> list[str]:
        unit = self.db.units.get(cls)
        return [s if isinstance(s, str) else s["id"] for s in (unit.skills if unit else ())]

    def skills_of(self, cls: str) -> list[str]:
        """Все навыки, доступные классу: свои и всех предметов, которые влезают в его слоты."""
        unit = self.db.units.get(cls)
        ids = list(self.class_skill_ids(cls))
        slots = set(unit.slots if unit else ())
        for item in self.db.items.values():
            if item.slot in slots:
                ids.extend(item.skills)
        ids = [sid for sid in dict.fromkeys(ids) if sid in self.db.skills]
        return ids

    def visible_skills(self) -> list[str]:
        skills = self.skills_of(self.cls)
        if self.skill_filter:
            skills = [sid for sid in skills if self.skill_filter in self.db.skills[sid].tags]
        return skills

    def skill_label(self, sid: str) -> str:
        skill = self.db.skills.get(sid)
        name = skill.name if skill else sid
        if sid not in self.class_skill_ids(self.cls):
            name = "· " + name                 # навык предмета
        return name

    def model(self):
        return self.data.unit_model(self.cls)

    def visible_animations(self) -> list[str]:
        if not self.anim_only_current:
            return sorted(self.animations)
        return sorted(n for n, a in self.animations.items() if (a.get("class") or "") == self.cls)

    def select_class(self, cls: str) -> None:
        self.cls = cls
        skills = self.visible_skills()
        if self.sid not in skills:
            self.select_skill(skills[0] if skills else None)
        # библиотека анимаций: если включён фильтр по классу — выбрать подходящую
        if self.anim_only_current:
            visible = self.visible_animations()
            if self.anim_name not in visible:
                self.select_animation(visible[0] if visible else None)
        if self.anim_edit.get("class") not in (cls, ""):
            self.select_animation(self.anim_name)

    def select_filter(self, tag: str) -> None:
        self.skill_filter = tag
        skills = self.visible_skills()
        if self.sid not in skills:
            self.select_skill(skills[0] if skills else None)

    def select_skill(self, sid: Optional[str]) -> None:
        self.sid = sid
        self.dirty = False
        self.message = ""
        self.tick, self.paused = 0.0, False
        if sid is None:
            self.edit, self.player = {}, None
            return
        spec = self.skill_animations.get(sid, {})
        timing = self.data.skill_timing(self.cls, sid)
        self.edit = {
            "animation": str(spec.get("animation") or ""),
            "tags": list(spec.get("tags") or []),
            "caster_fx": copy.deepcopy(list(spec.get("caster_fx") or [])),
            "target_fx": copy.deepcopy(list(spec.get("target_fx") or [])),
            "trajectory": copy.deepcopy(spec.get("trajectory")),
            "rain": copy.deepcopy(spec.get("rain")),
            "hits": list(timing.get("hits", [])),
            "approach": timing.get("approach", "auto"), "approach_from": timing.get("approach_from", 0.0),
            "approach_to": timing.get("approach_to", 0.0), "ret": timing.get("ret", "auto"),
            "ret_from": timing.get("ret_from", 0.0),
        }
        if self.edit["animation"] and self.edit["animation"] not in self.animations:
            self.message = f"Анимация «{self.edit['animation']}» не найдена в библиотеке"
        self.rebuild(reset=True)

    def timing_dict(self) -> dict:
        e = self.edit
        out: dict = {}
        if e.get("hits"):
            out["hits"] = sorted(float(h) for h in e["hits"])
        if e.get("approach", "auto") != "auto":
            out["approach"] = e["approach"]
            if e["approach"] == "chain":
                out["approach_from"], out["approach_to"] = e["approach_from"], e["approach_to"]
        if e.get("ret", "auto") != "auto":
            out["ret"] = e["ret"]
            if e["ret"] == "chain":
                out["ret_from"] = e["ret_from"]
        return out

    def skill_dict(self) -> dict:
        return {
            "animation": self.edit.get("animation") or "",
            "tags": list(self.edit.get("tags") or []),
            "caster_fx": copy.deepcopy(list(self.edit.get("caster_fx") or [])),
            "target_fx": copy.deepcopy(list(self.edit.get("target_fx") or [])),
            "trajectory": copy.deepcopy(self.edit.get("trajectory")),
            "rain": copy.deepcopy(self.edit.get("rain")),
        }

    def apply_skill(self) -> None:
        if self.sid is None:
            return
        spec = normalize_skill_animation(self.sid, self.skill_dict())
        has = bool(spec["animation"] or spec["tags"] or spec["caster_fx"] or spec["target_fx"]
                   or spec["trajectory"] or spec["rain"])
        if has:
            self.skill_animations[self.sid] = spec
        else:
            self.skill_animations.pop(self.sid, None)
        timing = self.timing_dict()
        cls_data = self.data.classes.setdefault(self.cls, {})
        timings = cls_data.setdefault("timing", {})
        if timing:
            timings[self.sid] = timing
        else:
            timings.pop(self.sid, None)
        self._sync_data()
        self.dirty = True
        self.rebuild(reset=False)

    def rebuild(self, reset: bool = True) -> None:
        from anim_review import SkillPlayer
        if reset:
            self.tick, self.paused = 0.0, False
        self._sync_data()
        try:
            self.player = SkillPlayer(self.db, self.cls, self.sid, data=self.data) if self.sid else None
        except Exception as error:
            self.player = error

    # --- сохранение ---

    def persist(self) -> None:
        try:
            config = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
        except Exception:
            config = {}
        manual = config.setdefault("manual", {})
        # старые композиты уже перенесены в manual.animations
        manual.pop("composites", None)
        packed = to_json(self.animations, self.skill_animations)
        manual["animations"] = packed["animations"]
        manual["skill_animations"] = packed["skill_animations"]
        if self.sid is not None:
            entry = manual.setdefault("classes", {}).setdefault(self.cls, {})
            timings = entry.setdefault("timing", {})
            timing = self.timing_dict()
            if timing:
                timings[self.sid] = timing
            else:
                timings.pop(self.sid, None)
            if not timings:
                entry.pop("timing", None)
            if not entry:
                manual["classes"].pop(self.cls, None)
            if not manual["classes"]:
                manual.pop("classes", None)
        CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=1), encoding="utf-8")

    def save(self) -> None:
        if self.sid is not None:
            self.apply_skill()
        self.persist()
        self.dirty = False
        self.message = f"Сохранено: {self.cls} / {self.sid}" if self.sid else "Сохранено"

    def reset(self) -> None:
        if self.sid is None:
            return
        self.skill_animations.pop(self.sid, None)
        self.data.classes.setdefault(self.cls, {}).setdefault("timing", {}).pop(self.sid, None)
        self._sync_data()
        self.persist()
        self.message = f"Сброшено к старой анимации: {self.cls} / {self.sid}"
        self.select_skill(self.sid)

    # --- привязка анимации ---

    def bind_animation(self, name: Optional[str]) -> None:
        if self.sid is None:
            return
        self.edit["animation"] = name or ""
        self.apply_skill()
        self.message = f"Привязана анимация: {name}" if name else "Анимация отвязана"

    def current_animation(self) -> Optional[dict]:
        name = self.edit.get("animation")
        return self.animations.get(name) if name else None

    def current_parts(self) -> list[str]:
        animation = self.current_animation()
        if animation is not None:
            return list(animation.get("parts") or [])
        return list(self.data.classes.get(self.cls, {}).get("skills", {}).get(self.sid or "", []))

    def current_holds(self) -> dict[int, float]:
        animation = self.current_animation()
        return dict(animation.get("holds") or {}) if animation else {}

    def generic_parts(self) -> list[str]:
        """Чем показ играет навык без своей анимации: обычная атака или каст класса."""
        if self.sid is None:
            return []
        kind = self.data.skill(self.sid, self.cls).get("kind", "melee")
        return self.data.default_chain(self.cls, kind)

    def import_legacy_animation(self) -> None:
        if self.sid is None:
            return
        parts = list(self.data.classes.get(self.cls, {}).get("skills", {}).get(self.sid, []))
        if not parts:
            parts = self.generic_parts()       # своей анимации нет — берём обычную атаку или каст
        if not parts:
            self.message = "У навыка нет ни своей, ни обычной цепочки"
            return
        timing = self.data.classes.get(self.cls, {}).get("timing", {}).get(self.sid, {})
        holds = {int(k): float(v) for k, v in (timing.get("holds") or {}).items()}
        base = f"{self.cls}__{self.sid}"
        name, index = base, 2
        while name in self.animations:
            name = f"{base}_{index}"
            index += 1
        self.animations[name] = {
            "id": name, "class": self.cls, "name": name,
            "parts": parts, "holds": holds, "tags": [],
        }
        self.select_animation(name)
        self.edit["animation"] = name
        self.apply_skill()
        self.anim_modal = True
        self.message = f"Создана стандартная анимация «{name}»"

    def new_animation_for_skill(self) -> None:
        """Новая анимация навыка: пустая, сразу привязана и открыта в библиотеке.

        Так можно собрать анимацию и навыку без старой цепочки — например, навыку
        предмета, у которого в файле игры своей анимации нет.
        """
        self.new_animation()
        if self.anim_name is None:
            return
        self.edit["animation"] = self.anim_name
        self.apply_skill()
        self.anim_modal = True
        self.message = f"Создана анимация «{self.anim_name}» — добавьте части"

    # --- библиотека стандартных анимаций ---

    def select_animation(self, name: Optional[str]) -> None:
        self.anim_name = name if name in self.animations else None
        if self.anim_name is None:
            self.anim_edit = {"class": self.cls, "name": "", "parts": [], "holds": {}}
        else:
            anim = self.animations[self.anim_name]
            self.anim_edit = {
                "class": anim.get("class") or self.cls,
                "name": anim.get("name") or self.anim_name,
                "parts": list(anim.get("parts") or []),
                "holds": dict(anim.get("holds") or {}),
            }
        self.anim_preview = None
        self.anim_preview_key = None

    def open_animation_modal(self) -> None:
        self.anim_modal = True
        visible = self.visible_animations()
        if self.anim_name not in visible:
            bound = self.edit.get("animation") if self.sid else None
            if bound in self.animations:
                self.select_animation(bound)
            elif visible:
                self.select_animation(visible[0])

    def save_animation_state(self) -> None:
        if self.anim_name is None:
            return
        self.animations[self.anim_name] = {
            "id": self.anim_name,
            "class": self.anim_edit.get("class") or self.cls,
            "name": self.anim_edit.get("name") or self.anim_name,
            "parts": list(self.anim_edit["parts"]),
            "holds": dict(self.anim_edit["holds"]),
            "tags": list(self.animations.get(self.anim_name, {}).get("tags") or []),
        }
        self.anim_preview = None
        self.anim_preview_key = None
        self._sync_data()
        if self.sid and self.edit.get("animation") == self.anim_name:
            self.rebuild(reset=False)
        self.dirty = True

    def new_animation(self) -> None:
        index = 1
        while f"anim_{index}" in self.animations:
            index += 1
        name = f"anim_{index}"
        self.animations[name] = {"id": name, "class": self.cls, "name": name,
                                 "parts": [], "holds": {}, "tags": []}
        self.select_animation(name)
        self.anim_edit["name"] = name
        self.save_animation_state()
        self.message = f"Создана анимация «{name}»"

    def duplicate_animation(self) -> None:
        if self.anim_name is None:
            return
        base = f"{self.anim_name}_copy"
        name, index = base, 2
        while name in self.animations:
            name = f"{base}{index}"
            index += 1
        self.animations[name] = copy.deepcopy(self.animations[self.anim_name])
        self.animations[name].update({"id": name, "name": name})
        self.select_animation(name)
        self.save_animation_state()

    def delete_animation(self) -> None:
        if self.anim_name is None:
            return
        name = self.anim_name
        self.animations.pop(name, None)
        for spec in self.skill_animations.values():
            if spec.get("animation") == name:
                spec["animation"] = ""
        if self.edit.get("animation") == name:
            self.edit["animation"] = ""
            self.apply_skill()
        visible = self.visible_animations()
        self.select_animation(visible[0] if visible else None)
        self.dirty = True
        self.message = f"Удалена анимация «{name}»"

    def rename_animation(self, new: str) -> None:
        old = self.anim_name
        new = new.strip()
        if not old or not new or new == old:
            return
        if new in self.animations:
            self.message = f"Анимация «{new}» уже есть"
            return
        self.animations[new] = self.animations.pop(old)
        self.animations[new].update({"id": new, "name": new})
        for spec in self.skill_animations.values():
            if spec.get("animation") == old:
                spec["animation"] = new
        if self.edit.get("animation") == old:
            self.edit["animation"] = new
            self.rebuild(reset=False)
        self.anim_name = new
        self.anim_edit["name"] = new
        self.dirty = True

    def add_anim_part(self, name: str) -> None:
        self.anim_edit["parts"].append(name)
        self.save_animation_state()

    def remove_anim_part(self, index: int) -> None:
        if 0 <= index < len(self.anim_edit["parts"]):
            self.anim_edit["parts"].pop(index)
            self.anim_edit["holds"] = {}
            self.save_animation_state()

    def move_anim_part(self, index: int, delta: int) -> None:
        parts = self.anim_edit["parts"]
        other = index + delta
        if 0 <= index < len(parts) and 0 <= other < len(parts):
            parts[index], parts[other] = parts[other], parts[index]
            self.anim_edit["holds"] = {}
            self.save_animation_state()

    def set_anim_hold(self, index: int, value: Optional[float]) -> None:
        if value is None:
            self.anim_edit["holds"].pop(index, None)
        else:
            self.anim_edit["holds"][index] = max(TICK, float(value))
        self.save_animation_state()

    def anim_model(self):
        return self.data.unit_model(self.anim_edit.get("class") or self.cls)

    def anim_total(self) -> float:
        model = self.anim_model()
        total = 0.0
        for index, name in enumerate(self.anim_edit["parts"]):
            total += self.anim_edit["holds"].get(index, self.data.length_ms(model, name) if model else 0)
        return total

    def anim_player(self):
        key = (self.anim_edit.get("class"), tuple(self.anim_edit["parts"]),
               tuple(sorted(self.anim_edit["holds"].items())))
        if key != self.anim_preview_key:
            self.anim_preview_key = key
            try:
                if not self.anim_edit["parts"]:
                    self.anim_preview = None
                else:
                    from anim_review import PhasePlayer
                    model = self.anim_model()
                    self.anim_preview = PhasePlayer(model, self.anim_edit["parts"], self.anim_edit["holds"])
            except Exception as error:
                self.anim_preview = error
        return self.anim_preview

    # --- эффекты навыка ---

    def native_fx(self, name: str) -> float:
        model = self.data.effect_model()
        return self.data.length_ms(model, name) if model else 0.0

    def add_fx(self, kind: str, name: str) -> None:
        self.edit.setdefault(kind, []).append({"anim": name, "start": 0.0, "end": 0.0})
        self.apply_skill()

    def remove_fx(self, kind: str, index: int) -> None:
        items = self.edit.get(kind, [])
        if 0 <= index < len(items):
            items.pop(index)
            self.apply_skill()

    def set_fx(self, kind: str, index: int, field: str, value: Optional[float]) -> None:
        items = self.edit.get(kind, [])
        if not (0 <= index < len(items)) or value is None:
            return
        item = items[index]
        value = max(0.0, float(value))
        if field == "start":
            item["start"] = value
            if item.get("end") and item["end"] < value:
                item["end"] = value
        else:
            item["end"] = value if value > item.get("start", 0) else 0.0
        self.apply_skill()

    def fx_now(self, kind: str, index: int) -> None:
        items = self.edit.get(kind, [])
        if not (0 <= index < len(items)):
            return
        item = items[index]
        native = self.native_fx(item["anim"])
        if kind == "caster_fx":
            start = round(self.now_in_chain())
        else:
            start = 0.0
        item["start"] = start
        item["end"] = round(start + native)
        self.apply_skill()

    # --- траектория ---

    def default_projectile(self) -> str:
        if self.sid is None:
            return ""
        old = self.data.skill(self.sid, self.cls).get("shot") or {}
        if old.get("anim"):
            return old["anim"]
        shot = self.data.classes.get(self.cls, {}).get("shot") or {}
        return shot.get("anim", "")

    def ensure_trajectory(self) -> dict:
        traj = self.edit.get("trajectory")
        if not isinstance(traj, dict):
            traj = {"anim": self.default_projectile(), "curve": [[0.0, 0.0], [0.5, -0.2], [1.0, 0.0]],
                    "speed": 60.0, "fall": 0.0}
            self.edit["trajectory"] = traj
        return traj

    def toggle_trajectory(self) -> None:
        if self.edit.get("trajectory"):
            self.edit["trajectory"] = None
        else:
            self.ensure_trajectory()
        self.apply_skill()

    def set_traj_anim(self, name: str) -> None:
        self.ensure_trajectory()["anim"] = name
        self.apply_skill()

    def set_traj_speed(self, value: Optional[float]) -> None:
        if value is None:
            return
        self.ensure_trajectory()["speed"] = max(1.0, float(value))
        self.apply_skill()

    def set_curve(self, points: list[list[float]]) -> None:
        self.ensure_trajectory()["curve"] = normalize_curve(points)
        self.apply_skill()

    def preset_curve(self, degrees: Optional[float] = None) -> None:
        if degrees is None:
            points = [[0.0, 0.0], [1.0, 0.0]]
        else:
            import math
            lift = -math.tan(math.radians(degrees)) * 0.25
            points = [[0.0, 0.0], [0.5, lift], [1.0, 0.0]]
        self.set_curve(points)

    # --- дождь ---

    def ensure_rain(self) -> dict:
        rain = self.edit.get("rain")
        if not isinstance(rain, dict):
            rain = {"duration": 1200.0, "entries": []}
            self.edit["rain"] = rain
        return rain

    def toggle_rain(self) -> None:
        if self.edit.get("rain"):
            self.edit["rain"] = None
        else:
            self.ensure_rain()
        self.apply_skill()

    def add_rain_entry(self, name: str) -> None:
        self.ensure_rain().setdefault("entries", []).append({"anim": name, "count": 10})
        self.apply_skill()

    def remove_rain_entry(self, index: int) -> None:
        entries = self.ensure_rain().get("entries", [])
        if 0 <= index < len(entries):
            entries.pop(index)
            self.apply_skill()

    def set_rain_count(self, index: int, value: Optional[float]) -> None:
        entries = self.ensure_rain().get("entries", [])
        if value is not None and 0 <= index < len(entries):
            entries[index]["count"] = max(1, int(value))
            self.apply_skill()

    def set_rain_duration(self, value: Optional[float]) -> None:
        if value is not None:
            self.ensure_rain()["duration"] = max(100.0, float(value))
            self.apply_skill()

    # --- время сцены ---

    def chain_layout(self) -> tuple[float, list[tuple[str, float, float]], list[float], list[float]]:
        player = self.player
        if not hasattr(player, "show") or self.sid is None:
            return 0.0, [], [], []
        director = player.show.director
        info = self.data.skill(self.sid, self.cls)
        timing = self.data.skill_timing(self.cls, self.sid)
        parts, hits, moves = director.chain(1, self.sid, info.get("kind", "melee"), timing)
        start = None
        for clip in player.show.tl.track(1).clips:
            if clip.parts and parts and clip.parts[0].anim == parts[0].anim and clip.start >= player.start:
                start = clip.start
                break
        start = (start if start is not None else player.start) - player.start
        layout, at = [], 0.0
        for part in parts:
            layout.append((part.anim, at, part.ms))
            at += part.ms
        return start, layout, hits, moves

    def chain_events(self) -> list[tuple[float, int, str]]:
        model, out = self.model(), []
        if model is None:
            return out
        _, layout, _, _ = self.chain_layout()
        for name, at, ms in layout:
            for tick, kind in model.puppet.events(name):
                if tick * TICK <= ms:
                    out.append((at + tick * TICK, kind, name))
        return sorted(out)

    def now_in_chain(self) -> float:
        if not hasattr(self.player, "total"):
            return 0.0
        start, *_ = self.chain_layout()
        return max(0.0, (self.tick * TICK) % self.player.total - start)

    # --- кадр ---

    def run(self, max_frames: Optional[int] = None) -> None:
        pygame.init()
        screen = pygame.display.set_mode(SIZE)
        pygame.display.set_caption("Редактор анимаций навыков UO")
        pygame.key.set_repeat(300, 40)
        from pygame_ui import UI, load_fonts
        fonts = load_fonts()
        ui = UI(screen, fonts)
        clock = pygame.time.Clock()
        frames = 0
        while max_frames is None or frames < max_frames:
            frames += 1
            dt = clock.tick(FPS)
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT:
                    return

            filtered = events
            if (self.picker or self.curve_modal) and any(e.type == pygame.KEYDOWN for e in events):
                filtered = [e for e in events if e.type != pygame.KEYDOWN]
            ui.begin(filtered)
            if not ui.captured:
                for e in events:
                    self.key(e)

            if not self.paused:
                self.tick += dt * 60 / 1000 * self.speed
            screen.fill(BG)

            saved_clicks = list(ui.clicks)
            layers = []
            if self.picker:
                layers.append(PICKER_BOX)
            if self.anim_modal:
                layers.append(ANIM_BOX)
            if self.curve_modal:
                layers.append(CURVE_BOX)

            def restrict(region: Optional[pygame.Rect], above: list[pygame.Rect]) -> None:
                if region is None:
                    ui.clicks = []
                else:
                    ui.clicks = [c for c in saved_clicks
                                 if region.collidepoint(c[0])
                                 and not any(a.collidepoint(c[0]) for a in above)]

            ui.clicks = [c for c in saved_clicks
                         if not any(r.collidepoint(c[0]) for r in layers)]
            self.draw_lists(ui, screen)
            self.draw_preview(ui, screen, fonts)
            self.draw_skill_info(ui, screen)
            self.draw_panels(ui, screen, fonts)

            if self.anim_modal:
                restrict(ANIM_BOX, [r for r in (PICKER_BOX,) if self.picker])
                self.draw_animation_modal(ui, screen, fonts)
            if self.curve_modal:
                restrict(CURVE_BOX, [r for r in (PICKER_BOX,) if self.picker])
                self.draw_curve_modal(ui, screen, fonts)
            if self.picker:
                restrict(PICKER_BOX, [])
                self.draw_picker(ui, screen, fonts)

            ui.clicks = saved_clicks
            ui.end()
            pygame.display.flip()
        self.screen = screen

    def key(self, e) -> None:
        if self.picker is not None:
            if e.type == pygame.TEXTINPUT:
                self.picker.filter += e.text
                self.picker.scroll = 0
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.picker = None
                elif e.key == pygame.K_BACKSPACE:
                    self.picker.filter = self.picker.filter[:-1]
            elif e.type == pygame.MOUSEWHEEL:
                self.picker.scroll = max(0, self.picker.scroll - e.y * 3)
            return

        if self.curve_modal:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.curve_modal = False
            return

        if self.anim_modal:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.anim_modal = False
            return

        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_SPACE:
            self.paused = not self.paused
        elif e.key == pygame.K_LEFT:
            self.paused, self.tick = True, max(0.0, self.tick - 1)
        elif e.key == pygame.K_RIGHT:
            self.paused, self.tick = True, self.tick + 1
        elif pygame.K_1 <= e.key <= pygame.K_4:
            self.speed = (0.25, 0.5, 1.0, 2.0)[e.key - pygame.K_1]
        elif e.key == pygame.K_s and e.mod & pygame.KMOD_CTRL:
            self.save()
        elif e.key == pygame.K_c:
            self.open_animation_modal()
        elif e.key == pygame.K_t and self.sid:
            self.ensure_trajectory()
            self.apply_skill()
            self.curve_modal = True

    # --- отрисовка: списки ---

    def draw_lists(self, ui, screen) -> None:
        area = pygame.Rect(8, 8, 200, SIZE[1] - 16)
        pygame.draw.rect(screen, PANEL, area)
        ui.text("Классы", area.x + 6, area.y + 4, DIM, "small")
        row = 22
        visible = (area.height - 32) // row
        off = ui.scroll("classes", area, len(self.classes), visible)
        for i, cls in enumerate(self.classes[off:off + visible]):
            r = pygame.Rect(area.x + 4, area.y + 24 + i * row, area.width - 8, row - 2)
            if ui.button(cls, r, selected=cls == self.cls):
                self.select_class(cls)

        area = pygame.Rect(214, 8, 200, SIZE[1] - 16)
        pygame.draw.rect(screen, PANEL, area)
        ui.text("Навыки класса и предметов", area.x + 6, area.y + 4, DIM, "small")
        filters = (("", "Все"), ("melee", "Бл."), ("ranged", "Дал."), ("magic", "Маг."))
        for i, (tag, label) in enumerate(filters):
            r = pygame.Rect(area.x + 4 + i * 48, area.y + 22, 44, 20)
            if ui.button(label, r, selected=self.skill_filter == tag):
                self.select_filter(tag)
        skills = self.visible_skills()
        list_area = pygame.Rect(area.x + 2, area.y + 48, area.width - 4, area.height - 54)
        row = 24
        visible = list_area.height // row
        off = ui.scroll("skills", list_area, len(skills), visible)
        for i, sid in enumerate(skills[off:off + visible]):
            r = pygame.Rect(list_area.x + 2, list_area.y + i * row, list_area.width - 4, row - 2)
            own = sid in self.class_skill_ids(self.cls)
            if ui.button(self.skill_label(sid), r, selected=sid == self.sid, color=TEXT if own else DIM):
                self.select_skill(sid)
        if not skills:
            ui.text("Нет подходящих навыков", list_area.x + 4, list_area.y + 6, DIM, "small")
        ui.text(f"{len(skills)} шт. · · = предмет", area.x + 6, area.bottom - 18, DIM, "small")

    def preview_rect(self) -> pygame.Rect:
        return pygame.Rect(420, 8, 820, 410)

    # --- отрисовка: предпросмотр ---

    def draw_preview(self, ui, screen, fonts) -> None:
        area = self.preview_rect()
        pygame.draw.rect(screen, (16, 18, 22), area)
        if self.sid is None:
            ui.text("У класса нет навыков.", area.x + 20, area.y + 20)
            return
        if isinstance(self.player, Exception):
            ui.text(f"Ошибка показа: {self.player}", area.x + 20, area.y + 20, HIT, "small", area.width - 40)
        elif self.player is not None:
            self.player.draw(screen, area, self.tick, fonts["small"])
            if self.player.used != self.sid:
                ui.text(f"В сцене применён {self.player.used}: условие навыка не выполнилось.", area.x + 10,
                        area.bottom - 22, WARN, "small")
        bar = pygame.Rect(area.x, area.bottom + 4, area.width, 44)
        pygame.draw.rect(screen, PANEL, bar)
        if not hasattr(self.player, "total"):
            return
        total = self.player.total
        k = bar.width / max(1.0, total)
        start, layout, hits, _moves = self.chain_layout()
        for n, (name, at, ms) in enumerate(layout):
            r = pygame.Rect(bar.x + (start + at) * k, bar.y + 2, max(2, ms * k - 1), 18)
            pygame.draw.rect(screen, (60, 66, 90) if n % 2 else (50, 56, 78), r)
            ui.text(name, r.x + 3, r.y + 2, TEXT, "small", max(10, r.width - 4))
        for at, kind, _ in self.chain_events():
            x = bar.x + (start + at) * k
            pygame.draw.line(screen, EVENT_COLORS.get(kind, DIM), (x, bar.y + 20), (x, bar.y + 34), 2)
        for h in hits:
            x = bar.x + (start + h) * k
            pygame.draw.line(screen, HIT, (x, bar.y), (x, bar.bottom), 3)
        e = self.edit
        if e.get("approach") == "chain":
            pygame.draw.line(screen, GO, (bar.x + (start + e["approach_from"]) * k, bar.bottom - 6),
                             (bar.x + (start + e["approach_to"]) * k, bar.bottom - 6), 4)
        if e.get("ret") == "chain":
            pygame.draw.line(screen, BACK, (bar.x + (start + e["ret_from"]) * k, bar.bottom - 6),
                             (bar.right, bar.bottom - 6), 4)
        play = (self.tick * TICK) % total
        x = bar.x + play * k
        pygame.draw.line(screen, WARN, (x, bar.y - 2), (x, bar.bottom + 2), 2)
        ui.text(f"{play:5.0f} мс хода · {play - start:5.0f} мс цепочки", bar.right - 250, bar.bottom + 2, DIM,
                "small")
        if ui.clicked(bar):
            pos = ui.clicks[0][0]
            self.paused = True
            self.tick = (pos[0] - bar.x) / k / TICK

    # --- характеристики навыка ---

    def _skill_fields(self, skill) -> list[tuple[str, str]]:
        d = getattr(skill, "__dict__", {}) or {}
        order = ("name", "title", "kind", "type", "target", "targets", "power", "dmg", "damage",
                 "mp", "mp_cost", "mana", "cost", "cd", "cooldown", "range", "radius", "duration",
                 "level", "cast", "cast_time", "hits", "desc", "description")
        out, seen = [], set()
        for key in order:
            if key in d:
                value = d[key]
                if value is None or value == "" or value == [] or value == {}:
                    continue
                out.append((key, str(value)))
                seen.add(key)
        for key, value in d.items():
            if key in seen:
                continue
            if isinstance(value, (int, float, str, bool)) and value not in (None, "", 0, False):
                out.append((key, str(value)))
        return out

    def draw_skill_info(self, ui, screen) -> None:
        if self.sid is None:
            return
        area = self.preview_rect()
        box = pygame.Rect(area.x + 8, area.y + 8, 390, 200)
        surf = pygame.Surface(box.size, pygame.SRCALPHA)
        surf.fill((10, 12, 16, 210))
        screen.blit(surf, box.topleft)
        pygame.draw.rect(screen, DIM, box, 1)
        y = box.y + 6
        ui.text(f"Навык: {self.sid}", box.x + 6, y, TEXT, "main", box.width - 12)
        y += 20
        skill = self.db.skills.get(self.sid)
        if skill is None:
            ui.text("нет данных в базе", box.x + 6, y, DIM, "small")
        else:
            for key, value in self._skill_fields(skill):
                if y > box.bottom - 16:
                    break
                ui.text(key, box.x + 6, y, DIM, "small", 100)
                ui.text(value, box.x + 110, y, TEXT, "small", box.width - 116)
                y += 13
        y += 4
        if y < box.bottom - 16:
            anim = self.current_animation()
            parts = self.current_parts()
            tags = ", ".join(self.edit.get("tags") or []) or "—"
            ui.text(f"анимация: {anim.get('name') if anim else 'старая'} · частей {len(parts)}"
                    f" · эффектов {len(self.edit.get('caster_fx') or [])}+{len(self.edit.get('target_fx') or [])}",
                    box.x + 6, y, DIM, "small", box.width - 12)
            y += 13
            ui.text(f"теги: {tags}", box.x + 6, y, DIM, "small", box.width - 12)

    # --- панели ---

    def small_button(self, ui, text, x, y, w=24, selected=False) -> bool:
        return bool(ui.button(text, pygame.Rect(x, y, w, 22), selected=selected))

    def draw_panels(self, ui, screen, fonts) -> None:
        bar_y = self.preview_rect().bottom + 50
        top = self.preview_rect().bottom + 70
        for k, sp in enumerate((0.25, 0.5, 1.0, 2.0)):
            if ui.button(f"×{sp:g}", pygame.Rect(420 + k * 54, bar_y - 2, 50, 20), selected=self.speed == sp):
                self.speed = sp
        if ui.button("пауза" if not self.paused else "дальше", pygame.Rect(640, bar_y - 2, 70, 20)):
            self.paused = not self.paused
        if ui.button("Анимации (C)", pygame.Rect(1060, 8, 150, 30), fill=(60, 60, 110)):
            self.open_animation_modal()
        if ui.button("Сохранить (Ctrl+S)", pygame.Rect(1250, 8, 170, 30), fill=(40, 90, 50)):
            self.save()
        if ui.button("Сбросить к старой", pygame.Rect(1426, 8, 166, 30), fill=(110, 40, 36)):
            self.reset()
        state = "есть несохранённые правки" if self.dirty else ""
        ui.text(self.message or state, 1060, 44, WARN if self.dirty else DIM, "small", 530)
        if self.sid is None:
            ui.text("Выберите навык.", 420, top, DIM)
            return

        # колонка 1 — стандартная анимация
        x, y, w = 420, top, 400
        pygame.draw.rect(screen, PANEL, (x - 4, y - 4, w + 8, SIZE[1] - y - 4))
        ui.text("Стандартная анимация", x, y, TEXT, "main")
        y += 24
        animation = self.current_animation()
        if animation is not None:
            source = animation.get("class") or "—"
            ui.text(f"{animation.get('name') or self.edit['animation']}", x, y, GOOD, "main", w - 6)
            y += 18
            ui.text(f"источник: {source} · частей: {len(animation.get('parts') or [])}"
                    f" · {self.current_total():.0f} мс", x, y, DIM, "small", w - 6)
            y += 20
            model = self.model()
            for i, name in enumerate(animation.get("parts") or []):
                if y > SIZE[1] - 160:
                    ui.text("…", x, y, DIM, "small")
                    break
                native = self.data.length_ms(model, name) if model else 0
                hold = (animation.get("holds") or {}).get(i)
                missing = model is not None and name not in model.puppet.anims
                ui.text(f"{i + 1}. {name}", x, y + 3, HIT if missing else TEXT, "small", 220)
                ui.text(f"{hold if hold is not None else native:.0f} мс", x + 228, y + 3,
                        WARN if hold is not None else DIM, "small")
                y += 22
            if y > SIZE[1] - 160:
                y = SIZE[1] - 160
            if ui.button("Редактировать анимацию", pygame.Rect(x, y + 6, 190, 24), fill=(60, 60, 110)):
                self.open_animation_modal()
            if ui.button("Отвязать", pygame.Rect(x + 196, y + 6, 90, 24)):
                self.bind_animation(None)
            y += 38
        else:
            ui.text("Анимация не привязана.", x, y, WARN, "main")
            y += 20
            old = self.current_parts()
            parts = old or self.generic_parts()
            if parts:
                ui.text("Показывается старая цепочка класса. «Создать» сделает из неё" if old else
                        "Своей анимации у навыка нет: играется обычная атака или каст класса.", x, y,
                        DIM, "small", w - 6)
                y += 16
                ui.text("стандартную анимацию — дальше её можно править в библиотеке.", x, y, DIM, "small", w - 6)
                y += 20
                model = self.model()
                for i, name in enumerate(parts):
                    if y > SIZE[1] - 190:
                        ui.text("…", x, y, DIM, "small")
                        break
                    native = self.data.length_ms(model, name) if model else 0
                    missing = model is not None and name not in model.puppet.anims
                    ui.text(f"{i + 1}. {name}", x, y + 3, HIT if missing else TEXT, "small", 220)
                    ui.text(f"{native:.0f} мс", x + 228, y + 3, DIM, "small")
                    y += 22
                y += 6
                if ui.button("Создать из старой цепочки" if old else "Создать из обычной атаки",
                             pygame.Rect(x, y, 210, 26), fill=(40, 90, 50)):
                    self.import_legacy_animation()
            else:
                ui.text("Ни привязки, ни старой цепочки у навыка нет.", x, y, DIM, "small", w - 6)
                y += 16
                ui.text("Создайте анимацию и соберите её из частей модели.", x, y, DIM, "small", w - 6)
                y += 24
                if ui.button("Создать новую анимацию", pygame.Rect(x, y, 210, 26), fill=(40, 90, 50)):
                    self.new_animation_for_skill()
            if ui.button("Выбрать из библиотеки", pygame.Rect(x + 216, y, 180, 26)):
                names = self.visible_animations()
                if names:
                    self.picker = Picker("Стандартная анимация", names, self.bind_animation, None)
            y += 42
        if ui.button("Библиотека анимаций (C)", pygame.Rect(x, SIZE[1] - 40, 210, 26), fill=(60, 60, 110)):
            self.open_animation_modal()
        ui.text("Новые данные: manual.animations и manual.skill_animations", x + 216, SIZE[1] - 34, DIM, "small", 180)

        # колонка 2 — удары, подход, возврат
        x, y, w = 832, top, 400
        pygame.draw.rect(screen, PANEL, (x - 4, y - 4, w + 8, SIZE[1] - y - 4))
        ui.text("Тайминги сцены", x, y, TEXT, "main")
        y += 26
        ui.text("Удары", x, y, TEXT, "main")
        if ui.button("по событиям игры", pygame.Rect(x + 70, y, 150, 22), selected=not self.edit["hits"]):
            self.edit["hits"] = []
            self.apply_skill()
        if ui.button("+ удар сейчас", pygame.Rect(x + 226, y, 120, 22)):
            self.edit["hits"] = sorted(self.edit["hits"] + [round(self.now_in_chain())])
            self.apply_skill()
        y += 26
        for i, h in enumerate(self.edit["hits"]):
            ui.text(f"{h:.0f} мс", x + 10 + (i % 4) * 96, y + 3, HIT, "small")
            if self.small_button(ui, "x", x + 64 + (i % 4) * 96, y):
                self.edit["hits"].pop(i)
                self.apply_skill()
            if i % 4 == 3:
                y += 24
        y += 32
        ui.text("Подход к цели", x, y, TEXT, "main")
        y += 22
        for k, (key, label) in enumerate(APPROACH):
            if ui.button(label, pygame.Rect(x + k * 80, y, 76, 22), selected=self.edit["approach"] == key):
                self.edit["approach"] = key
                if key == "chain" and not self.edit["approach_to"]:
                    self.edit["approach_to"] = round(self.now_in_chain())
                self.apply_skill()
        y += 26
        if self.edit["approach"] == "chain":
            ui.text(f"с {self.edit['approach_from']:.0f} мс", x, y + 3, GO, "small")
            if ui.button("= сейчас", pygame.Rect(x + 80, y, 70, 22)):
                self.edit["approach_from"] = round(self.now_in_chain())
                self.apply_skill()
            ui.text(f"до {self.edit['approach_to']:.0f} мс", x + 170, y + 3, GO, "small")
            if ui.button("= сейчас", pygame.Rect(x + 250, y, 70, 22)):
                self.edit["approach_to"] = round(self.now_in_chain())
                self.apply_skill()
            y += 26
        y += 8
        ui.text("Возврат на место", x, y, TEXT, "main")
        y += 22
        for k, (key, label) in enumerate(RETURN):
            if ui.button(label, pygame.Rect(x + k * 96, y, 92, 22), selected=self.edit["ret"] == key):
                self.edit["ret"] = key
                if key == "chain" and not self.edit["ret_from"]:
                    self.edit["ret_from"] = round(self.now_in_chain())
                self.apply_skill()
        y += 26
        if self.edit["ret"] == "chain":
            ui.text(f"с {self.edit['ret_from']:.0f} мс до конца цепочки", x, y + 3, BACK, "small")
            if ui.button("= сейчас", pygame.Rect(x + 220, y, 70, 22)):
                self.edit["ret_from"] = round(self.now_in_chain())
                self.apply_skill()
        y += 34
        ui.text("События анимаций (из игры): п.от, п.до — подход, возв — возврат", x, y, TEXT, "main")
        y += 22
        events = self.chain_events()
        for at, kind, part in events[:8]:
            ui.text(f"{at:5.0f} мс {part}", x, y + 3, EVENT_COLORS.get(kind, DIM), "small", 150)
            ui.text(EVENT_NAMES.get(kind, str(kind)), x + 152, y + 3, DIM, "small", 70)
            for k, (label, field) in enumerate((("п.от", "approach_from"), ("п.до", "approach_to"),
                                                ("возв", "ret_from"), ("удар", None))):
                if ui.button(label, pygame.Rect(x + 226 + k * 44, y, 42, 20)):
                    self.take_event(field, round(at))
            y += 22

        # колонка 3 — эффекты, полёт, дождь, теги
        x, y, w = 1244, top - 340, 348
        pygame.draw.rect(screen, PANEL, (x - 4, y - 4, w + 8, SIZE[1] - y - 4))
        for i, (key, label) in enumerate(FX_TABS):
            if ui.button(label, pygame.Rect(x + i * 84, y, 80, 22), selected=self.fx_tab == key):
                self.fx_tab = key
        y += 30
        if self.fx_tab == "fx":
            self.draw_fx_tab(ui, screen, x, y, w)
        elif self.fx_tab == "trajectory":
            self.draw_trajectory_tab(ui, x, y, w)
        elif self.fx_tab == "rain":
            self.draw_rain_tab(ui, x, y, w)
        else:
            self.draw_tags_tab(ui, x, y, w)

    def current_total(self) -> float:
        model = self.model()
        total = 0.0
        for i, name in enumerate(self.current_parts()):
            total += self.current_holds().get(i, self.data.length_ms(model, name) if model else 0)
        return total

    def take_event(self, field: Optional[str], at: int) -> None:
        e = self.edit
        if field is None:
            e["hits"] = sorted(set(e["hits"] + [at]))
        else:
            e[field] = at
            if field == "ret_from":
                e["ret"] = "chain"
            else:
                e["approach"] = "chain"
                if field == "approach_from" and e["approach_to"] <= at:
                    e["approach_to"] = at + 300
        self.apply_skill()

    def draw_fx_tab(self, ui, screen, x, y, w) -> None:
        ui.text("На применяющем (от начала цепочки)", x, y, TEXT, "main", w)
        if ui.button("+ эффект", pygame.Rect(x + w - 78, y - 2, 74, 20)):
            self.picker = Picker("Эффект на применяющем", self.effect_names,
                                 lambda n: self.add_fx("caster_fx", n), ("fx", None))
        y += 24
        y = self.draw_fx_list(ui, screen, "caster_fx", x, y, w)
        y += 8
        ui.text("На цели при попадании (от удара)", x, y, TEXT, "main", w)
        if ui.button("+ эффект", pygame.Rect(x + w - 78, y - 2, 74, 20)):
            self.picker = Picker("Эффект на цели", self.effect_names,
                                 lambda n: self.add_fx("target_fx", n), ("fx", None))
        y += 24
        y = self.draw_fx_list(ui, screen, "target_fx", x, y, w)
        ui.text("0 в конце = показывать родную длину эффекта.", x, y + 8, DIM, "small", w)

    def draw_fx_list(self, ui, screen, kind: str, x: int, y: int, w: int) -> int:
        items = self.edit.get(kind) or []
        area = pygame.Rect(x, y, w, 154)
        row = 25
        visible = area.height // row
        off = ui.scroll(kind, area, len(items), visible)
        if not items:
            ui.text("пусто", x + 4, y + 4, DIM, "small")
        for index, item in enumerate(items[off:off + visible], start=off):
            yy = y + (index - off) * row
            ui.text(item["anim"], x, yy + 3, TEXT, "small", 120)
            value = ui.number_input((kind, index, "start"), pygame.Rect(x + 122, yy, 44, 20),
                                    float(item.get("start", 0)), 0, 100000)
            if value is not None:
                self.set_fx(kind, index, "start", value)
                return y + min(len(items), visible) * row + 2
            value = ui.number_input((kind, index, "end"), pygame.Rect(x + 170, yy, 44, 20),
                                    float(item.get("end", 0)), 0, 100000)
            if value is not None:
                self.set_fx(kind, index, "end", value)
                return y + min(len(items), visible) * row + 2
            if self.small_button(ui, "с", x + 218, yy, 22):
                self.fx_now(kind, index)
                return y + min(len(items), visible) * row + 2
            if self.small_button(ui, "x", x + 244, yy, 22):
                self.remove_fx(kind, index)
                return y + min(len(items), visible) * row + 2
        return y + min(len(items), visible) * row + 2

    def draw_trajectory_tab(self, ui, x, y, w) -> None:
        active = bool(self.edit.get("trajectory"))
        if ui.button("Своя траектория: " + ("вкл" if active else "выкл"),
                     pygame.Rect(x, y, 210, 24), selected=active):
            self.toggle_trajectory()
        y += 32
        if not active:
            ui.text("По умолчанию — прямая или старая дуга снаряда.", x, y, DIM, "small", w)
            return
        traj = self.ensure_trajectory()
        ui.text("Анимация снаряда", x, y, DIM, "small")
        y += 16
        ui.text(traj.get("anim") or "—", x, y + 3, TEXT, "small", 220)
        if ui.button("выбрать", pygame.Rect(x + w - 66, y, 62, 20)):
            self.picker = Picker("Анимация снаряда", self.effect_names, self.set_traj_anim, ("fx", None))
        y += 26
        ui.text("Скорость", x, y + 3, DIM, "small")
        value = ui.number_input(("traj", "speed"), pygame.Rect(x + 66, y, 50, 20),
                                float(traj.get("speed", 60)), 1, 999)
        if value is not None:
            self.set_traj_speed(value)
        ui.text("ед/тик", x + 122, y + 3, DIM, "small")
        y += 30
        curve = traj.get("curve") or []
        ui.text(f"Точек кривой: {len(curve)}", x, y, TEXT, "main")
        y += 24
        if ui.button("Редактор кривой (T)", pygame.Rect(x, y, 180, 26), fill=(60, 60, 110)):
            self.curve_modal = True
        y += 34
        for k, (label, deg) in enumerate((("Прямая", None), ("30°", 30), ("45°", 45), ("60°", 60))):
            if ui.button(label, pygame.Rect(x + k * 80, y, 76, 22), selected=False):
                self.preset_curve(deg)
        ui.text("Кривая задаёт подъём в долях расстояния. Отрицательное — выше линии.", x, y + 30, DIM, "small", w)
        kind = self.data.skill(self.sid, self.cls).get("kind", "melee") if self.sid else "melee"
        if kind not in ("ranged", "magic"):
            ui.text("Обычно используется только дальними и магическими навыками.", x, y + 78, WARN, "small", w)

    def draw_rain_tab(self, ui, x, y, w) -> None:
        active = bool(self.edit.get("rain"))
        if ui.button("Дождь: " + ("вкл" if active else "выкл"), pygame.Rect(x, y, 160, 24), selected=active):
            self.toggle_rain()
        y += 32
        if not active:
            ui.text("Набор эффектов, равномерно падающих по стороне противника.", x, y, DIM, "small", w)
            return
        rain = self.ensure_rain()
        ui.text("Длительность", x, y + 3, DIM, "small")
        value = ui.number_input(("rain", "duration"), pygame.Rect(x + 96, y, 64, 20),
                                float(rain.get("duration", 1200)), 100, 60000)
        if value is not None:
            self.set_rain_duration(value)
        ui.text("мс", x + 166, y + 3, DIM, "small")
        y += 28
        if ui.button("+ эффект", pygame.Rect(x, y, 90, 22)):
            self.picker = Picker("Эффект дождя", self.effect_names, self.add_rain_entry, ("fx", None))
        y += 28
        entries = rain.get("entries") or []
        for index, item in enumerate(entries):
            ui.text(item["anim"], x, y + 3, TEXT, "small", 170)
            value = ui.number_input(("rain", index, "count"), pygame.Rect(x + 174, y, 52, 20),
                                    float(item.get("count", 1)), 1, 999)
            if value is not None:
                self.set_rain_count(index, value)
            if self.small_button(ui, "x", x + 230, y, 22):
                self.remove_rain_entry(index)
                return
            y += 25
        if not entries:
            ui.text("Добавьте эффекты и их количество.", x, y, DIM, "small", w)
        else:
            ui.text(f"всего: {sum(int(e.get('count', 0)) for e in entries)} эффектов", x, y + 4, DIM, "small", w)
        kind = self.data.skill(self.sid, self.cls).get("kind", "melee") if self.sid else "melee"
        if kind not in ("ranged", "magic"):
            ui.text("Обычно используется только дальними и магическими навыками.", x, y + 22, WARN, "small", w)

    def draw_tags_tab(self, ui, x, y, w) -> None:
        ui.text("Теги анимации — подсказки, в бою не участвуют.", x, y, DIM, "small", w)
        y += 22
        options = [(key, f"{key} — {label}") for key, label in sorted(ANIMATION_TAGS.items())]
        chosen = ui.multiselect(("anim_tags", self.sid), pygame.Rect(x, y, w, 24), options,
                                self.edit.get("tags") or [])
        if chosen is not None:
            self.edit["tags"] = list(chosen)
            self.apply_skill()
        y += 34
        tags = self.edit.get("tags") or []
        if tags:
            ui.text(", ".join(tags), x, y, TEXT, "small", w)
        else:
            ui.text("Теги не выбраны.", x, y, DIM, "small")

    # --- пикер ---

    def draw_picker(self, ui, screen, fonts) -> None:
        p = self.picker
        fresh, p.fresh = p.fresh, False
        box = PICKER_BOX
        pygame.draw.rect(screen, (20, 22, 28), box)
        pygame.draw.rect(screen, WARN, box, 2)
        ui.text(f"{p.title}: наберите текст для поиска — «{p.filter}»  (Esc — закрыть)",
                box.x + 10, box.y + 8, TEXT, "main", box.width - 20)
        names = p.visible()
        list_r = pygame.Rect(box.x + 10, box.y + 36, 420, box.height - 46)
        row = 22
        visible = list_r.height // row
        p.scroll = min(p.scroll, max(0, len(names) - visible))
        p.hover = None
        for i, name in enumerate(names[p.scroll:p.scroll + visible]):
            r = pygame.Rect(list_r.x, list_r.y + i * row, list_r.width, row - 2)
            if r.collidepoint(ui.mouse):
                p.hover = name
            if not fresh and ui.button(name, r):
                self.picker = None
                p.on_pick(name)
                return
        ui.text(f"{len(names)} шт.", box.x + 10, box.bottom - 18, DIM, "small")
        view = pygame.Rect(box.x + 440, box.y + 36, box.width - 450, box.height - 46)
        pygame.draw.rect(screen, (40, 44, 52), view)
        if p.hover is None or p.preview is None:
            return
        kind, cls = p.preview
        model = self.data.unit_model(cls) if kind == "unit" else self.data.effect_model()
        key = (kind, cls, p.hover)
        if key not in self.preview_cache:
            from anim_review import PhasePlayer
            self.preview_cache[key] = PhasePlayer(model, [p.hover + ("*" if model.puppet.is_hold(p.hover) else "")])
        self.preview_cache[key].draw(screen, view, self.tick, fonts["small"])

    # --- библиотека стандартных анимаций ---

    def draw_animation_modal(self, ui, screen, fonts) -> None:
        box = ANIM_BOX
        pygame.draw.rect(screen, (20, 22, 28), box)
        pygame.draw.rect(screen, WARN, box, 2)
        ui.text("Стандартные анимации классов — части тела и их длительности",
                box.x + 10, box.y + 8, TEXT, "main", box.width - 200)
        if ui.button("Закрыть (Esc)", pygame.Rect(box.right - 130, box.y + 6, 120, 24)):
            self.anim_modal = False
            return

        list_r = pygame.Rect(box.x + 10, box.y + 40, 280, box.height - 60)
        pygame.draw.rect(screen, PANEL, list_r)
        ui.text("Анимации", list_r.x + 6, list_r.y + 4, DIM, "small")
        if ui.button("только класс" if self.anim_only_current else "все",
                     pygame.Rect(list_r.x + 84, list_r.y + 2, 190, 20),
                     selected=self.anim_only_current):
            self.anim_only_current = not self.anim_only_current
            visible = self.visible_animations()
            if self.anim_name not in visible:
                self.select_animation(visible[0] if visible else None)
        btn_y = list_r.y + 24
        if ui.button("новый", pygame.Rect(list_r.x + 4, btn_y, 84, 22)):
            self.new_animation()
        if self.anim_name and ui.button("дублировать", pygame.Rect(list_r.x + 92, btn_y, 96, 22)):
            self.duplicate_animation()
        if self.anim_name and ui.button("удалить", pygame.Rect(list_r.x + 192, btn_y, 84, 22)):
            self.delete_animation()

        list_inner = pygame.Rect(list_r.x + 4, list_r.y + 52, list_r.width - 8, list_r.height - 60)
        row = 22
        visible = list_inner.height // row
        names = self.visible_animations()
        off = ui.scroll("anim_list", list_inner, len(names), visible)
        for i, name in enumerate(names[off:off + visible]):
            r = pygame.Rect(list_inner.x, list_inner.y + i * row, list_inner.width, row - 2)
            if ui.button(name, r, selected=name == self.anim_name):
                self.select_animation(name)
        if not names:
            ui.text("Анимаций нет. Нажмите «новый».", list_inner.x + 4, list_inner.y + 4, DIM, "small",
                    list_inner.width - 8)

        mid = pygame.Rect(list_r.right + 10, box.y + 40, 620, box.height - 60)
        pygame.draw.rect(screen, PANEL, mid)
        if self.anim_name is None:
            ui.text("Выберите анимацию слева или создайте новую.", mid.x + 12, mid.y + 12, DIM)
            return

        y = mid.y + 8
        ui.text("Имя:", mid.x + 8, y + 3, DIM, "small")
        new_name = ui.text_input(("anim_name", self.anim_name), pygame.Rect(mid.x + 50, y, 260, 22),
                                 self.anim_edit.get("name") or self.anim_name)
        if new_name:
            self.rename_animation(new_name)
        if ui.button("применить к навыку", pygame.Rect(mid.x + 320, y, 180, 22), fill=(40, 90, 50)):
            if self.sid:
                self.edit["animation"] = self.anim_name
                self.apply_skill()
                self.message = f"Привязана анимация «{self.anim_name}»"
        y += 30

        ui.text("Класс-источник:", mid.x + 8, y + 3, DIM, "small")
        options = [(c, c) for c in self.classes]
        picked = ui.dropdown(("anim_class", self.anim_name), pygame.Rect(mid.x + 130, y, 220, 22),
                             options, self.anim_edit.get("class") or self.cls)
        if picked is not None:
            self.anim_edit["class"] = picked
            self.save_animation_state()
        if ui.button("= текущий класс", pygame.Rect(mid.x + 360, y, 150, 22)):
            self.anim_edit["class"] = self.cls
            self.save_animation_state()
        y += 32

        src_model = self.anim_model()
        src_have = set(src_model.puppet.anims) if src_model is not None else set()
        ui.text(f"Части: {len(self.anim_edit['parts'])} · суммарно {self.anim_total():.0f} мс  "
                f"(* = своя длительность)", mid.x + 8, y, DIM, "small")
        y += 20
        bottom_btn_y = mid.bottom - 34
        part_area = pygame.Rect(mid.x + 4, y, mid.width - 8, max(20, bottom_btn_y - y - 6))
        row = 25
        visible = part_area.height // row
        off = ui.scroll("anim_parts", part_area, len(self.anim_edit["parts"]), visible)
        for i, name in enumerate(self.anim_edit["parts"][off:off + visible], start=off):
            yy = y + (i - off) * row
            native = self.data.length_ms(src_model, name) if src_model else 0
            hold = self.anim_edit["holds"].get(i)
            missing = name not in src_have
            ui.text(f"{i + 1}. {name}", mid.x + 8, yy + 3, HIT if missing else TEXT, "small", 250)
            shown = hold if hold is not None else native
            ui.text(f"{shown:.0f} мс" + ("" if hold is None else " *"), mid.x + 264, yy + 3,
                    WARN if hold is not None else DIM, "small")
            if self.small_button(ui, "-", mid.x + 350, yy):
                self.set_anim_hold(i, max(TICK, shown - 50))
            if self.small_button(ui, "+", mid.x + 376, yy):
                self.set_anim_hold(i, shown + 50)
            if self.small_button(ui, "↺", mid.x + 402, yy, 24):
                self.set_anim_hold(i, None)
            if self.small_button(ui, "↑", mid.x + 432, yy) and i > 0:
                self.move_anim_part(i, -1)
            if self.small_button(ui, "↓", mid.x + 458, yy) and i + 1 < len(self.anim_edit["parts"]):
                self.move_anim_part(i, 1)
            if self.small_button(ui, "x", mid.x + 486, yy):
                self.remove_anim_part(i)
                break
        if ui.button("+ часть", pygame.Rect(mid.x + 8, bottom_btn_y, 100, 24)):
            names = sorted(n for n in src_have if n and not n.startswith(("D_", "HG_D_")))
            self.picker = Picker("Анимация модели", names, self.add_anim_part,
                                 ("unit", self.anim_edit.get("class") or self.cls))
        if ui.button("длины по умолчанию", pygame.Rect(mid.x + 116, bottom_btn_y, 170, 24)):
            self.anim_edit["holds"] = {}
            self.save_animation_state()
        if ui.button("создать из старой", pygame.Rect(mid.x + 294, bottom_btn_y, 150, 24)):
            self.import_legacy_animation()
        if ui.button("сохранить в файл", pygame.Rect(mid.x + 452, bottom_btn_y, 160, 24), fill=(40, 90, 50)):
            self.save()

        right = pygame.Rect(mid.right + 10, box.y + 40, box.right - mid.right - 20, box.height - 60)
        pygame.draw.rect(screen, PANEL, right)
        ui.text("Предпросмотр стандартной анимации", right.x + 8, right.y + 6, TEXT, "main", right.width - 16)
        view = pygame.Rect(right.x + 8, right.y + 30, right.width - 16, right.height - 40)
        pygame.draw.rect(screen, (16, 18, 22), view)
        player = self.anim_player()
        if isinstance(player, Exception):
            ui.text(f"Ошибка: {player}", view.x + 8, view.y + 8, HIT, "small", view.width - 16)
        elif player is None:
            ui.text("Нет частей.", view.x + 8, view.y + 8, DIM)
        else:
            try:
                player.draw(screen, view, self.tick, fonts["small"])
            except Exception as error:
                ui.text(f"Ошибка отрисовки: {error}", view.x + 8, view.y + 8, HIT, "small", view.width - 16)

    # --- визуальный редактор кривой ---

    def _curve_rects(self):
        box = CURVE_BOX
        plot = pygame.Rect(box.x + 16, box.y + 58, 820, box.height - 100)
        side = pygame.Rect(plot.right + 16, box.y + 58, box.right - plot.right - 32, box.height - 100)
        return box, plot, side

    @staticmethod
    def _curve_to_screen(u: float, v: float, plot: pygame.Rect) -> tuple[int, int]:
        v_min, v_max = -0.7, 0.15
        return (round(plot.x + u * plot.width),
                round(plot.y + (v - v_min) / (v_max - v_min) * plot.height))

    @staticmethod
    def _screen_to_curve(pos, plot: pygame.Rect) -> tuple[float, float]:
        v_min, v_max = -0.7, 0.15
        u = (pos[0] - plot.x) / max(1, plot.width)
        v = v_min + (pos[1] - plot.y) / max(1, plot.height) * (v_max - v_min)
        return max(0.0, min(1.0, u)), max(v_min, min(v_max, v))

    def draw_curve_modal(self, ui, screen, fonts) -> None:
        traj = self.ensure_trajectory()
        box, plot, side = self._curve_rects()
        pygame.draw.rect(screen, (20, 22, 28), box)
        pygame.draw.rect(screen, WARN, box, 2)
        ui.text("Траектория снаряда — тяните точки мышью. Начало и конец закреплены по высоте.",
                box.x + 10, box.y + 8, TEXT, "main", box.width - 160)
        if ui.button("Готово (Esc)", pygame.Rect(box.right - 130, box.y + 6, 120, 24)):
            self.curve_modal = False
            return

        pygame.draw.rect(screen, (14, 16, 20), plot)
        pygame.draw.rect(screen, DIM, plot, 1)
        for k in range(5):
            u = k / 4
            x, _ = self._curve_to_screen(u, 0, plot)
            pygame.draw.line(screen, (44, 48, 58), (x, plot.y), (x, plot.bottom), 1)
        for v in (-0.6, -0.4, -0.2, 0.0):
            _, y = self._curve_to_screen(0, v, plot)
            pygame.draw.line(screen, (44, 48, 58), (plot.x, y), (plot.right, y), 1)
            ui.text(f"{v:+.1f}", plot.x - 30, y - 7, DIM, "small")
        _, zero_y = self._curve_to_screen(0, 0, plot)
        pygame.draw.line(screen, (90, 96, 110), (plot.x, zero_y), (plot.right, zero_y), 2)
        points = normalize_curve(traj.get("curve"))
        curve = [self._curve_to_screen(*curve_point(points, i / 80), plot) for i in range(81)]
        if len(curve) > 1:
            pygame.draw.lines(screen, GOOD, False, curve, 3)
        for i, (u, v) in enumerate(points):
            p = self._curve_to_screen(u, v, plot)
            color = WARN if self.curve_selected == i else TEXT
            pygame.draw.circle(screen, color, p, 7 if self.curve_selected == i else 5)
        start = self._curve_to_screen(0, 0, plot)
        end = self._curve_to_screen(1, 0, plot)
        pygame.draw.circle(screen, HIT, start, 5)
        pygame.draw.circle(screen, HIT, end, 5)

        # перетаскивание
        pressed = pygame.mouse.get_pressed()[0]
        inside = plot.collidepoint(ui.mouse)
        if pressed and inside:
            if self.curve_drag is None:
                nearest, distance = None, 14
                for i, (u, v) in enumerate(points):
                    if i in (0, len(points) - 1):
                        continue
                    p = self._curve_to_screen(u, v, plot)
                    d = ((p[0] - ui.mouse[0]) ** 2 + (p[1] - ui.mouse[1]) ** 2) ** 0.5
                    if d < distance:
                        nearest, distance = i, d
                self.curve_drag = nearest
            if self.curve_drag is not None:
                u, v = self._screen_to_curve(ui.mouse, plot)
                left = points[self.curve_drag - 1][0] + 0.01
                right = points[self.curve_drag + 1][0] - 0.01
                points[self.curve_drag] = [max(left, min(right, u)), v]
                self.curve_selected = self.curve_drag
                traj["curve"] = points
        if not pressed and self.curve_drag is not None:
            self.curve_drag = None
            self.set_curve(points)

        if ui.clicked(plot) == -1:
            u, v = self._screen_to_curve(ui.clicks[0][0] if ui.clicks else ui.mouse, plot)
            for i, (pu, pv) in enumerate(points):
                p = self._curve_to_screen(pu, pv, plot)
                if ((p[0] - ui.mouse[0]) ** 2 + (p[1] - ui.mouse[1]) ** 2) ** 0.5 < 14 and i not in (0, len(points) - 1):
                    points.pop(i)
                    self.curve_selected = None
                    self.set_curve(points)
                    break

        ui.text("ЛКМ — тянуть, ПКМ по точке — удалить. Подъём: чем выше, тем больше дуга.", plot.x,
                plot.bottom + 10, DIM, "small", plot.width)

        y = side.y
        ui.text("Снаряд", side.x, y, TEXT, "main")
        y += 22
        ui.text(traj.get("anim") or "—", side.x, y + 3, TEXT, "small", side.width - 80)
        if ui.button("выбрать", pygame.Rect(side.right - 70, y, 66, 20)):
            self.picker = Picker("Анимация снаряда", self.effect_names, self.set_traj_anim, ("fx", None))
        y += 30
        ui.text("Скорость, ед/тик", side.x, y + 3, DIM, "small")
        value = ui.number_input(("curve", "speed"), pygame.Rect(side.x + 120, y, 60, 20),
                                float(traj.get("speed", 60)), 1, 999)
        if value is not None:
            self.set_traj_speed(value)
        y += 36
        if ui.button("Добавить точку", pygame.Rect(side.x, y, 140, 24)):
            u, v = (0.5, -0.2)
            if plot.collidepoint(ui.mouse):
                u, v = self._screen_to_curve(ui.mouse, plot)
            points = normalize_curve(traj.get("curve") + [[u, v]])
            self.curve_selected = len(points) - 2
            self.set_curve(points)
        y += 30
        if self.curve_selected is not None and ui.button("Удалить точку", pygame.Rect(side.x, y, 140, 24)):
            points = normalize_curve(traj.get("curve"))
            if 0 < self.curve_selected < len(points) - 1:
                points.pop(self.curve_selected)
                self.curve_selected = None
                self.set_curve(points)
        y += 36
        for k, (label, deg) in enumerate((("Прямая", None), ("30°", 30), ("45°", 45), ("60°", 60))):
            if ui.button(label, pygame.Rect(side.x + k * 80, y, 74, 22)):
                self.preset_curve(deg)
        ui.text("Кривая хранится как точки (доля пути, подъём).", side.x, y + 30, DIM, "small", side.width)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    Editor().run()
