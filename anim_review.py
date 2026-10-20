"""Проверка анимаций UO вручную: python anim_review.py

Слева — классы (сколько неверных, сколько не проверено), посередине — пункты класса, справа — показ.
Пункт — одна вещь на проверку: фаза боя (стойка, разбег, возврат, попадание, блок, гибель, победа…),
проигрывается куклой на месте по кругу, или навык класса — настоящая сцена боя против манекена
(подход, удар, снаряды, эффекты, возврат). У каждого пункта написано, что проверить и из каких анимаций
он собран.

Отметки — «Верно» / «Неверно» и комментарий, в чём проблема. Всё пишется в data/anim_review.json
(его читает разработчик). Если состав пункта поменялся (другие анимации, эффекты или правка в
data/anim_review_notes.json), пункт помечается «изменено — проверь снова», прежний комментарий виден.

Клавиши: пробел — пауза, R — сначала, ←/→ — кадр назад/вперёд (на паузе), 1-4 — скорость
(×0.25, ×0.5, ×1, ×2), ↑/↓ — пункт, F1 — верно, F2 — неверно, F3 — снять отметку. Клик по полю
комментария — ввод (Enter — сохранить, Shift+Enter — новая строка, Esc — выйти из поля).
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Optional

import pygame

ROOT = Path(__file__).resolve().parent
REVIEW = ROOT / "data" / "anim_review.json"
NOTES = ROOT / "data" / "anim_review_notes.json"
SIZE = (1600, 900)
FPS = 60
SPEEDS = (0.25, 0.5, 1.0, 2.0)
LOOP_MS = 4000               # часть «по кругу» в фазе: столько показывать, потом фаза сначала

BG = (24, 26, 32)
PANEL = (34, 37, 46)
TEXT = (225, 225, 230)
DIM = (140, 145, 160)
GOOD = (90, 200, 110)
BAD = (230, 80, 70)
CHANGED = (240, 190, 60)
SELECT = (60, 66, 90)

PHASES = (
    ("stance", "Боевая стойка", "Стоит в боевой стойке своего класса; цикл без скачков и мигания; летун парит."),
    ("dash", "Разбег", "Бег к цели (DASH_1): поза бега, без рывков."),
    ("stop", "Торможение", "Остановка у цели (DASH_2) — переход в стойку."),
    ("back", "Бег назад", "Бег на своё место (BACK_1)."),
    ("home", "Разворот на месте", "Разворот лицом к врагу на своём месте (BACK_2)."),
    ("jump", "Прыжок", "Прыжок (прикрытие союзника, у летунов — взлёт)."),
    ("land", "Приземление", "Приземление после прыжка."),
    ("cover", "Прикрытие", "Прыжок к союзнику и стойка со щитом."),
    ("hit", "Попадание по нему", "Реакция на удар (KNOCKBACK)."),
    ("guard", "Блок", "Блок удара."),
    ("avoid", "Уклонение", "Уклонение от удара."),
    ("die", "Гибель", "Гибель — заканчивается лёжа (последний кадр держится)."),
    ("down", "Лежит", "Лежит после гибели по кругу."),
    ("victory", "Победа", "Победная поза."),
    ("charge", "Заряд", "Заряд навыка по кругу."),
    ("release", "Выпуск заряда", "Выпуск заряженного навыка."),
)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


class Item:
    def __init__(self, item_id: str, cls: str, kind: str, title: str, check: str, parts: list[str],
                 extra: dict, rev: int, note: str):
        self.id, self.cls, self.kind, self.title, self.check = item_id, cls, kind, title, check
        self.parts, self.extra, self.note = parts, extra, note
        self.signature = json.dumps({"parts": parts, "extra": extra, "rev": rev}, sort_keys=True, ensure_ascii=False)


def build_items(data, db) -> dict[str, list[Item]]:
    """Пункты по классам: фазы, что есть у класса, и его навыки."""
    notes = load_json(NOTES, {})
    out: dict[str, list[Item]] = {}
    for cls in sorted(data.classes):
        info = data.classes[cls]
        if not info.get("file"):
            continue
        items = []

        def note_of(item_id):
            n = notes.get(item_id) or notes.get(f"{cls}/*") or {}
            return int(n.get("rev", 0)), n.get("note", "")
        for key, title, check in PHASES:
            parts = data.phase(cls, key)
            if parts:
                rev, note = note_of(f"{cls}/{key}")
                items.append(Item(f"{cls}/{key}", cls, "phase", title, check, parts, {}, rev, note))
        unit = db.units.get(cls)
        skills = [s if isinstance(s, str) else s["id"] for s in (unit.skills if unit else [])]
        for sid in skills:
            skill = db.skills.get(sid)
            if skill is None:
                continue
            chain = data.skill_chain(cls, sid)
            fx = data.skill(sid)
            weapon = info.get("shot") if fx.get("kind") == "ranged" and not fx.get("shot") else None
            rev, note = note_of(f"{cls}/skill/{sid}")
            check = ("Навык целиком: подход к цели (если нужен), замах, момент удара совпадает с попаданием и "
                     "цифрой, снаряд вылетает из рук и долетает до цели, эффекты на своих местах, возврат.")
            items.append(Item(f"{cls}/skill/{sid}", cls, "skill", f"Навык: {skill.name}", check,
                              chain, {"effects": fx, "weapon_shot": weapon}, rev, note))
        # сырые слоты UO (S01.., S15.., S20 CHASE…): какому навыку какой — в данных игры не записано
        for slot, names in slot_groups(info["file"]).items():
            item_id = f"{cls}/slot/{slot}"
            rev, note = note_of(item_id)
            items.append(Item(item_id, cls, "phase", f"Слот UO {slot}: {names[0][4:]}",
                              "Сырой слот анимаций из файла игры. Напиши в комментарии, какой это навык и как "
                              "он должен выглядеть (или что слот не нужен).", names, {"slot": slot}, rev, note))
        out[cls] = items
    return out


def slot_groups(file: str) -> dict[str, list[str]]:
    """Слоты S## файла персонажа: части по порядку файла."""
    import re
    from engine.uo.library import source
    from engine.uo.mbs import MBS
    path = source().src / "Chara" / f"{file}.mbs"
    groups: dict[str, list[str]] = {}
    for a in MBS(path.read_bytes()).anims:
        m = re.match(r"^(S\d\d)_", a["name"])
        if m:
            groups.setdefault(m.group(1), []).append(a["name"])
    return groups


class PhasePlayer:
    """Фаза на месте: части по порядку, часть «по кругу» — LOOP_MS, потом сначала.

    holds — необязательные длительности частей в мс по номеру (как в стандартной анимации)."""

    def __init__(self, model, parts: list[str], holds: Optional[dict[int, float]] = None):
        self.model = model
        self.parts = []
        holds = holds or {}
        box = None
        for index, name in enumerate(parts):
            anim = name.rstrip("*")
            if anim not in model.puppet.anims:
                continue
            loop = name.endswith("*")
            length = max(1, model.length(anim))
            if index in holds:
                length = max(1, round(float(holds[index]) / (1000 / 60)))
            self.parts.append((anim, length, loop))
            b = model.box(anim)
            if b:
                box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
        self.box = box or (-200, -400, 200, 20)
        self.total = sum(LOOP_MS / (1000 / 60) if loop else length for _, length, loop in self.parts) or 1
        self.cache: dict = {}

    def at(self, tick: float) -> tuple[str, int, bool]:
        tick = tick % self.total
        for anim, length, loop in self.parts:
            span = LOOP_MS / (1000 / 60) if loop else length
            if tick < span:
                return anim, int(tick), loop
            tick -= span
        anim, length, loop = self.parts[-1]
        return anim, length - 1, loop

    def draw(self, surface: pygame.Surface, rect: pygame.Rect, tick: float, font) -> None:
        if not self.parts:
            return
        anim, local, loop = self.at(tick)
        b = self.box
        k = min(rect.width * 0.8 / max(1, b[2] - b[0]), rect.height * 0.8 / max(1, b[3] - b[1]))
        puppet = self.model.puppet
        t = puppet.canonical_tick(anim, local, loop)
        key = (anim, t, loop, round(k, 4))
        if key not in self.cache:
            found = self.model.frame(anim, t, k, False, loop=loop, box=b)
            self.cache[key] = None if found is None else (
                pygame.image.frombytes(found[0].tobytes(), (found[0].shape[1], found[0].shape[0]), "RGBA"), found[1])
            if len(self.cache) > 900:
                self.cache.pop(next(iter(self.cache)))
        found = self.cache[key]
        feet = (rect.centerx, rect.y + rect.height * 0.85)
        pygame.draw.line(surface, (70, 80, 70), (rect.x + 20, feet[1]), (rect.right - 20, feet[1]), 2)
        if found is not None:
            image, (ox, oy) = found
            surface.blit(image, (round(feet[0] - ox), round(feet[1] - oy)))
        # полоса частей
        x = rect.x + 10
        y = rect.bottom - 26
        tick_mod = tick % self.total
        for name, length, part_loop in self.parts:
            span = LOOP_MS / (1000 / 60) if part_loop else length
            w = max(30, int((rect.width - 20) * span / self.total))
            active = name == anim
            pygame.draw.rect(surface, SELECT if active else PANEL, (x, y, w - 2, 20))
            label = f"{name}{' ∞' if part_loop else ''} ({length})"
            surface.blit(font.render(label, True, TEXT if active else DIM), (x + 4, y + 3))
            x += w
        surface.blit(font.render(f"{anim}  тик {local}  (по кругу)" if loop else f"{anim}  тик {local}", True, CHANGED),
                     (rect.x + 10, rect.y + 8))
        del tick_mod


def pick_dummy(db, conditions, fallback: str = "fighter") -> str:
    """Класс манекена, у которого есть (или нет) теги из условий цели."""
    from game.tactics import HasTag, LacksTag
    wanted = [c for c in conditions if isinstance(c, (HasTag, LacksTag))]
    if not wanted:
        return fallback
    order = sorted(db.units, key=lambda c: (c != fallback, db.units[c].story, c))
    for cid in order:
        tags = set(db.units[cid].tags)
        if all((c.tag in tags) == isinstance(c, HasTag) for c in wanted):
            return cid
    return fallback


def satisfy(db, unit, condition) -> bool:
    """Подгоняет юнита под условие навыка: HP, эффекты, теги. True — условие выполнено."""
    from game import tactics
    if condition is None or isinstance(condition, tactics.Always):
        return True
    if isinstance(condition, tactics.HpBelow):
        limit = unit.max_hp * max(0.0, condition.value)
        unit.state.current_hp = max(1, min(unit.max_hp, math.ceil(limit) - 1))
    elif isinstance(condition, tactics.HpAbove):
        unit.state.current_hp = unit.max_hp
    elif isinstance(condition, tactics.HasEffect):
        effect = db.effects.get(condition.effect_id)
        if effect is not None:
            unit.add_effect(effect)
    elif isinstance(condition, tactics.LacksEffect):
        unit.effects = [e for e in unit.effects if e.definition.id != condition.effect_id]
    elif isinstance(condition, tactics.HasLabel):
        effect = next((e for e in db.effects.values() if condition.label in e.tags), None)
        if effect is not None:
            unit.add_effect(effect)
    elif isinstance(condition, tactics.HasFlag):
        effect = next((e for e in db.effects.values() if condition.flag in e.flags), None)
        if effect is not None:
            unit.add_effect(effect)
    elif isinstance(condition, tactics.HasTag) and condition.tag not in unit.tags:
        effect = next((e for e in db.effects.values() if condition.tag in e.grants_tags), None)
        if effect is not None:
            unit.add_effect(effect)
    return condition.check(unit, unit)


def item_for_skill(db, cls: str, sid: str):
    """Предмет, который даёт классу этот навык: навык предмета иначе юниту незнаком."""
    unit = db.units.get(cls)
    slots = set(unit.slots if unit else ())
    for item_id, item in db.items.items():
        if sid in item.skills and item.slot in slots:
            return item_id
    return None


class SkillPlayer:
    """Навык сценой боя: класс против манекена; показ с начала его хода до конца.

    Условия навыка (requires_self / requires_target и условия накладываемых эффектов)
    сцена выполняет сама: манекен берётся с нужными тегами, HP и эффекты подгоняются,
    чтобы в показе играл именно выбранный навык, а не запасной."""

    def __init__(self, db, cls: str, sid: str, data=None):
        from battle import BattleShow
        from game.editing import set_tactics
        from game.squad import Formation, Squad
        skill = db.skills[sid]
        ally = skill.targets in ("ally", "self")
        applied = [a.condition for a in skill.applies]
        dummy_cls = pick_dummy(db, [skill.requires_target, *applied])
        # навык предмета: без надетого предмета класса юнит его не знает и сцена его не играет
        definition = db.units.get(cls)
        own = set(definition.skills_at(50)) if definition else set()
        gear = {}
        if sid not in own:
            item_id = item_for_skill(db, cls, sid)
            if item_id is not None:
                gear[1] = [item_id]

        def squad(name, cells):
            f = Formation()
            made = []
            for uid, c, row, col, tactic, level in cells:
                unit = db.create_unit(c, uid, level=level, equipment=gear.get(uid, ()))
                set_tactics(db, unit, tactic)
                f.place(unit, row, col)
                made.append(unit)
            return Squad(name, name, f), made
        mine = [(1, cls, 0, 1, [{"skill": sid}], 50)]     # 50: открыты все навыки класса
        if ally:
            mine.append((2, "fighter", 0, 0, [], 50))
        left, mine_units = squad("left", mine)
        right, right_units = squad("right", [(11, dummy_cls, 0, 1, [], 60)])
        for s in (left, right):
            for u in s.formation.units:
                u.pp.current = 0                # без пассивок: только сам навык
        me, dummy = mine_units[0], right_units[0]
        mate = mine_units[1] if ally else None
        target = me if skill.targets == "self" else (mate if mate is not None else dummy)
        if mate is not None:
            mate.take_damage(mate.max_hp // 2)      # чтобы лечение и «цель ранена» было видно
        satisfy(db, me, skill.requires_self)
        satisfy(db, target, skill.requires_target)
        for condition in applied:
            satisfy(db, target, condition)
        self.show = BattleShow(db, left, right, seed=7, scene="default", data=data)
        director = self.show.director
        spans = []
        orig = director.act

        def act(a, at):
            end = orig(a, at)
            spans.append((a.kind, a.actor, a.skill_id, at, end))
            return end
        director.act = act
        t = 0.0
        while t < 120000 and not any(k == "active" and u == 1 for k, u, *_ in spans):
            self.show.update(t)
            t += 100
        found = next(((s, at, end) for k, u, s, at, end in spans if k == "active" and u == 1), None)
        director.act = orig
        if found is None:
            self.used, self.start, self.end = None, 0.0, 3000.0
        else:
            self.used, self.start, self.end = found[0], found[1] - 300, found[2] + 600
        self.total = max(1.0, self.end - self.start)

    def draw(self, surface: pygame.Surface, rect: pygame.Rect, tick: float, font) -> None:
        ms = self.start + (tick * 1000 / 60) % self.total
        self.show.update(ms)
        self.show.draw(surface, rect, ms)
        surface.blit(font.render(f"{(ms - self.start) / 1000:5.2f} с из {self.total / 1000:.2f}", True, CHANGED),
                     (rect.x + 10, rect.y + 8))


class App:
    def __init__(self):
        from battle.data import ShowData
        from game.database import Database
        self.db = Database.load()
        self.data = ShowData()
        if not self.data.ok:
            raise SystemExit("Нет папки игры или видеокарты (moderngl): показ кукол недоступен.")
        self.items = build_items(self.data, self.db)
        self.classes = list(self.items)
        self.review = load_json(REVIEW, {"items": {}})
        self.cls = self.classes[0]
        self.index = 0
        self.filter = "all"
        self.player: Any = None
        self.tick = 0.0
        self.speed = 1.0
        self.paused = False
        self.typing = False
        self.comment = ""
        self.class_scroll = self.item_scroll = 0
        self.open_item()

    # --- данные ---

    def state(self, item: Item) -> str:
        entry = self.review["items"].get(item.id)
        if not entry or not entry.get("status"):
            return "new"
        if entry.get("signature") != item.signature:
            return "changed"
        return entry["status"]

    def mark(self, status: Optional[str]) -> None:
        item = self.current()
        if item is None:
            return
        if status is None:
            self.review["items"].pop(item.id, None)
        else:
            self.review["items"][item.id] = {
                "status": status, "comment": self.comment.strip(), "signature": item.signature,
                "what": {"title": item.title, "parts": item.parts, **item.extra},
                "used_skill": getattr(self.player, "used", None),
                "checked": time.strftime("%Y-%m-%d %H:%M")}
        REVIEW.write_text(json.dumps(self.review, ensure_ascii=False, indent=1), encoding="utf-8")

    def visible_items(self) -> list[Item]:
        items = self.items[self.cls]
        if self.filter == "all":
            return items
        return [i for i in items if self.state(i) == self.filter or (self.filter == "todo" and self.state(i) in ("new", "changed"))]

    def current(self) -> Optional[Item]:
        items = self.visible_items()
        return items[self.index] if 0 <= self.index < len(items) else None

    def open_item(self) -> None:
        item = self.current()
        self.tick, self.paused, self.typing = 0.0, False, False
        entry = self.review["items"].get(item.id, {}) if item else {}
        self.comment = entry.get("comment", "")
        self.player = None
        if item is None:
            return
        try:
            if item.kind == "phase":
                self.player = PhasePlayer(self.data.unit_model(item.cls), item.parts)
            else:
                self.player = SkillPlayer(self.db, item.cls, item.id.rsplit("/", 1)[1])
        except Exception as error:          # пункт с ошибкой — показать причину, не падать
            self.player = error

    def counts(self, cls: str) -> tuple[int, int, int]:
        states = [self.state(i) for i in self.items[cls]]
        return states.count("bad"), sum(s in ("new", "changed") for s in states), len(states)

    # --- кадр ---

    def run(self, max_frames: Optional[int] = None) -> None:
        """max_frames — для проверки без окна (SDL_VIDEODRIVER=dummy)."""
        pygame.init()
        screen = pygame.display.set_mode(SIZE)
        pygame.display.set_caption("Проверка анимаций UO")
        pygame.key.set_repeat(300, 40)
        from pygame_ui import UI, load_fonts
        fonts = load_fonts()
        ui = UI(screen, fonts)
        small = fonts["small"]
        clock = pygame.time.Clock()
        frames = 0
        while max_frames is None or frames < max_frames:
            frames += 1
            dt = clock.tick(FPS)
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT:
                    return
                self.key(e)
            if not self.paused:
                self.tick += dt * 60 / 1000 * self.speed
            ui.begin([] if self.typing else events)
            screen.fill(BG)
            self.draw_classes(ui, screen, small)
            self.draw_items(ui, screen, small)
            self.draw_preview(ui, screen, fonts)
            ui.end()
            pygame.display.flip()
        self.screen = screen

    def key(self, e) -> None:
        if self.typing:
            if e.type == pygame.TEXTINPUT:
                self.comment += e.text
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.typing = False
                elif e.key == pygame.K_BACKSPACE:
                    self.comment = self.comment[:-1]
                elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if e.mod & pygame.KMOD_SHIFT:
                        self.comment += "\n"
                    else:
                        self.typing = False
                        status = (self.review["items"].get(self.current().id, {}).get("status") or "bad")
                        self.mark(status)
            return
        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_SPACE:
            self.paused = not self.paused
        elif e.key == pygame.K_r:
            self.tick = 0.0
        elif e.key == pygame.K_LEFT:
            self.paused, self.tick = True, max(0.0, self.tick - 1)
        elif e.key == pygame.K_RIGHT:
            self.paused, self.tick = True, self.tick + 1
        elif pygame.K_1 <= e.key <= pygame.K_4:
            self.speed = SPEEDS[e.key - pygame.K_1]
        elif e.key in (pygame.K_UP, pygame.K_DOWN):
            n = len(self.visible_items())
            if n:
                self.index = (self.index + (1 if e.key == pygame.K_DOWN else -1)) % n
                self.open_item()
        elif e.key == pygame.K_F1:
            self.mark("ok")
        elif e.key == pygame.K_F2:
            self.mark("bad")
        elif e.key == pygame.K_F3:
            self.mark(None)

    def draw_classes(self, ui, screen, font) -> None:
        area = pygame.Rect(8, 8, 250, SIZE[1] - 16)
        pygame.draw.rect(screen, PANEL, area)
        row = 24
        visible = (area.height - 10) // row
        offset = ui.scroll("classes", area, len(self.classes), visible)
        for i, cls in enumerate(self.classes[offset:offset + visible]):
            rect = pygame.Rect(area.x + 4, area.y + 5 + i * row, area.width - 8, row - 2)
            bad, todo, total = self.counts(cls)
            color = BAD if bad else (TEXT if todo else GOOD)
            if ui.button("", rect, selected=cls == self.cls):
                self.cls, self.index = cls, 0
                self.open_item()
            ui.text(cls, rect.x + 6, rect.y + 4, color, "small", 150)
            ui.text(f"x{bad} ?{todo}/{total}", rect.right - 80, rect.y + 4, DIM, "small")

    def draw_items(self, ui, screen, font) -> None:
        area = pygame.Rect(266, 8, 330, SIZE[1] - 16)
        pygame.draw.rect(screen, PANEL, area)
        for k, (key, label) in enumerate((("all", "все"), ("todo", "проверить"), ("bad", "неверно"), ("ok", "верно"))):
            if ui.button(label, pygame.Rect(area.x + 4 + k * 81, area.y + 4, 78, 22), selected=self.filter == key):
                self.filter, self.index = key, 0
                self.open_item()
        items = self.visible_items()
        row = 26
        top = area.y + 32
        visible = (area.bottom - top) // row
        offset = ui.scroll("items", area, len(items), visible)
        marks = {"ok": ("+", GOOD), "bad": ("X", BAD), "changed": ("!", CHANGED), "new": ("·", DIM)}
        for i, item in enumerate(items[offset:offset + visible]):
            rect = pygame.Rect(area.x + 4, top + i * row, area.width - 8, row - 2)
            if ui.button("", rect, selected=offset + i == self.index):
                self.index = offset + i
                self.open_item()
            sign, color = marks[self.state(item)]
            ui.text(sign, rect.x + 6, rect.y + 4, color, "main")
            ui.text(item.title, rect.x + 26, rect.y + 5, TEXT, "small", rect.width - 30)

    def draw_preview(self, ui, screen, fonts) -> None:
        area = pygame.Rect(604, 8, SIZE[0] - 612, 540)
        pygame.draw.rect(screen, (16, 18, 22), area)
        item = self.current()
        if item is None:
            ui.text("Нет пунктов.", area.x + 20, area.y + 20)
            return
        if isinstance(self.player, Exception):
            ui.text(f"Ошибка показа: {self.player}", area.x + 20, area.y + 20, BAD, "small", area.width - 40)
        elif self.player is not None:
            self.player.draw(screen, area, self.tick, fonts["small"])
        y = area.bottom + 8
        x = area.x
        state = self.state(item)
        names = {"ok": ("верно", GOOD), "bad": ("неверно", BAD), "changed": ("изменено — проверь снова", CHANGED),
                 "new": ("не проверено", DIM)}
        label, color = names[state]
        ui.text(f"{item.cls}: {item.title}", x, y, TEXT, "big")
        ui.text(label, x + 620, y + 4, color, "main")
        y += 30
        for line in wrap_text(fonts["small"], "Проверить: " + item.check, area.width):
            ui.text(line, x, y, TEXT, "small")
            y += 17
        ui.text("Анимации: " + " → ".join(item.parts or ["(нет — по виду навыка)"]), x, y, DIM, "small", area.width)
        y += 17
        fx = item.extra.get("effects")
        if fx:
            shot = fx.get("shot") or item.extra.get("weapon_shot")
            text = (f"Эффекты: выпуск {fx.get('out') or '—'}, снаряд {shot.get('anim') if shot else '—'}, "
                    f"на цели {', '.join(fx.get('cast') or []) or '—'}, попадание {', '.join(fx.get('hit') or []) or '—'}")
            ui.text(text, x, y, DIM, "small", area.width)
            y += 17
            used = getattr(self.player, "used", None)
            sid = item.id.rsplit("/", 1)[1]
            if used and used != sid:
                ui.text(f"Внимание: в сцене применён {used} — условие навыка не выполнилось.", x, y, CHANGED, "small")
                y += 17
        if item.note:
            ui.text("Что менялось: " + item.note, x, y, CHANGED, "small", area.width)
            y += 17
        # управление
        y += 6
        for k, (label, speed) in enumerate((("×0.25", 0.25), ("×0.5", 0.5), ("×1", 1.0), ("×2", 2.0))):
            if ui.button(label, pygame.Rect(x + k * 64, y, 60, 26), selected=self.speed == speed):
                self.speed = speed
        if ui.button("пауза" if not self.paused else "дальше", pygame.Rect(x + 270, y, 80, 26)):
            self.paused = not self.paused
        if ui.button("сначала", pygame.Rect(x + 356, y, 80, 26)):
            self.tick = 0.0
        if ui.button("Верно (F1)", pygame.Rect(x + 520, y, 120, 26), fill=(40, 90, 50)):
            self.mark("ok")
        if ui.button("Неверно (F2)", pygame.Rect(x + 646, y, 120, 26), fill=(110, 40, 36)):
            self.mark("bad")
        if ui.button("Снять (F3)", pygame.Rect(x + 772, y, 110, 26)):
            self.mark(None)
        y += 34
        box = pygame.Rect(x, y, area.width, SIZE[1] - y - 10)
        pygame.draw.rect(screen, (44, 48, 60) if self.typing else PANEL, box)
        pygame.draw.rect(screen, CHANGED if self.typing else DIM, box, 1)
        if ui.clicked(box):
            self.typing = True
            pygame.key.start_text_input()
        text = self.comment or ("" if self.typing else "Комментарий: что не так (клик, чтобы писать; Enter — сохранить)")
        lines = []
        for para in text.split("\n"):
            lines += wrap_text(fonts["main"], para, box.width - 16)
        for i, line in enumerate(lines[-((box.height - 10) // 19):]):
            ui.text(line + ("|" if self.typing and i == len(lines) - 1 else ""), box.x + 8, box.y + 6 + i * 19,
                    TEXT if self.comment else DIM, "main")


def wrap_text(font, text: str, width: int) -> list[str]:
    from pygame_ui import wrap
    return wrap(font, text, width) if text else [""]


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    App().run()
