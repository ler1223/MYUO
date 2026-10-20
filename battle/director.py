"""Режиссёр: акт боя (game.combat.record) -> сцена в расписании (battle.timeline).

Сцена хода (docs/uo/battle.md, «Как устроен показ»):
1. яд/ожог перед ходом — цифра и вздрагивание;
2. красная лента с названием навыка на стороне бойца, вспышка применения, камера на участников;
3. пассивки до удара: прикрывающий перепрыгивает к союзнику (COVER), блок, усиления — синяя лента;
4. ближний бой: разбег DASH_1 до цели, торможение DASH_2; дальний и магия — на месте;
5. цепочка удара (ATTACK_*, MAGIC_*, S##_*); момент выпуска — начало удара после замаха.
   Снаряд (стрела, болт, огненный шар; навыка или оружия класса) вылетает в момент выпуска (X_OUT),
   летит к цели со скоростью из настроек игры (залп — каждый со своим смещением и задержкой), удар —
   когда долетел (X_HIT). Без снаряда: след оружия — у атакующего, столп и вспышка — на целях,
   эффект на всё поле — по центру целей; попадание — в момент выпуска.
   в момент каждого удара: эффект попадания, реакция цели (KNOCKBACK, GUARD, AVOID), цифра,
   плашка; гибель — DIE / DIE_BLOW, эффект DIED, растворение;
6. пассивки после удара (контратака, преследование) — своими сценами, по очереди;
7. возврат: BACK_1 бегом на своё место, BACK_2 — разворот; боевая стойка.
Длительности — из самих анимаций и таймингов игры (data.timing: разбег 25 тиков, возврат 25/34,
гибель 20 + 30); нет анимации — разумная пауза. Следующий акт начинается, когда ходивший прошёл
половину пути домой (UO: NEXT_PLAYSTART_RETURN_RATE), — Director.act возвращает этот момент.
"""
from __future__ import annotations

import math
from typing import Callable, Optional

from game.combat.record import ACTIVE, AFFLICTION, END, EVADE, MISS, NEGATE, PASSIVE, ROUND, SKIP, START, Act, Strike

from .animation import curve_length
from .data import TICK_MS, ShowData
from .stage import APPROACH, OFFSCREEN, Spot, Stage, floor_for
from .timeline import Banner, Clip, Focus, Fx, Move, Part, Plate, Popup, Shot, Timeline

RUN_SPEED = 1.9              # бег: единиц сцены в мс
IDLE_HOLD = 260              # сколько держится часть-«удержание» цепочки (прицел, каст)
BANNER_LEAD = 380            # лента с названием успевает показаться до движения
PASSIVE_SCENE = 750          # пассивка без своего навыка (усиление, лечение): столько длится её сцена
HIT_SPACING = 140            # многоударный навык: между ударами
POPUP_MAX = 1700             # цифры висят не дольше
SETTLE = 250                 # пауза после сцены
FOCUS_MS = 450               # наезд камеры
CAST_LIFT = 140              # эффект навыка на применившем — на высоте груди
SHOT_LIFT = 190              # снаряд вылетает на высоте руки
SHOT_AHEAD = 60              # и чуть впереди бойца
HIT_LIFT = 150               # попадает в грудь цели
SHOT_STOP = 40               # не долетая до её середины
WIDE_FX = 3000.0             # эффект шире этого (единиц) — на всё поле: по центру целей
TRAIL_EVERY = 8              # след снаряда (EFFECTID 軌跡, エフェクト): в точке вылета и дальше через столько тиков
MAGIC_KINDS = ("magic", "heal", "support")


def walks_up(kind: str, approach: str = "auto") -> bool:
    """Сближается ли боец с целью перед ударом.

    По умолчанию — только ближний бой: дальние навыки и магия играются с места (стрела летит
    сама, каст идёт у себя). Для них сближение задаётся явно: «разбег», «прыжок» или «в цепочке».
    """
    if approach != "auto":
        return approach in ("dash", "jump", "chain")
    return kind == "melee"


GENERIC = {"skill_on": "SKILL_ON_01", "passive_on": "PAS_PARTICLE_A", "active_on": "ACT_PARTICLE_A",
           "buff": "STATUS_UP_A", "debuff": "STATUS_DOWN_A", "heal": "HEAL_HIT_01", "died": "DIED_01",
           "guard": "PROTECTION_A", "dash": "DASH_EF_END_A1", "land": "LAND_EF_A1", "chant": "CHANTING_COMMON_A"}


def popup_anims(kind: str, crit: bool, guard: bool) -> list[str]:
    """Раскладки Interface для цифры и подписи (как в UO)."""
    if kind == "miss":
        return ["STR_MISS"]
    if kind == "heal":
        return ["NUM_CRITICAL_HEAL", "STR_CRITICAL_HEAL"] if crit else ["NUM_HEAL"]
    if guard:
        return ["NUM_GUARD", "STR_CRITICAL_GUARD" if crit else "STR_GUARD"]
    return ["NUM_CRITICAL_DAMAGE", "STR_CRITICAL_DAMAGE"] if crit else ["NUM_DAMAGE"]


class Director:
    def __init__(self, data: ShowData, battle, timeline: Timeline, bottom: Optional[float] = None):
        """bottom — нижний край картинки фона (земля и кадр — выше него)."""
        self.data = data
        self.battle = battle
        self.tl = timeline
        sides = battle.sides
        rows = max(s.squad.formation.rows for s in sides)
        cols = max(s.squad.formation.cols for s in sides)
        self.stage = Stage(rows, cols, floor_for(bottom), bottom)
        self.home: dict[int, Spot] = {}
        self.side: dict[int, int] = {}
        self.cls: dict[int, str] = {}
        self.look: dict[int, int] = {}       # модель бойца из списка моделей класса (UnitState.look)
        self.shown: dict[int, Plate] = {}
        for side in sides:
            for unit in side.units:
                row, col = side.pos(unit)
                self.home[unit.uid] = self.stage.spot(side.index, row, col)
                self.side[unit.uid] = side.index
                self.cls[unit.uid] = unit.definition.id
                self.look[unit.uid] = getattr(unit.state, "look", 0)
                self.shown[unit.uid] = Plate(0, unit.hp, unit.max_hp, unit.ap.max, unit.pp.max, unit.is_alive)
        self.where: dict[int, Spot] = dict(self.home)    # где боец будет к концу запланированного
        self.ui = data.ui_model("ui")
        self.fx_model = data.effect_model()

    # --- анимации ---

    def model(self, uid: int):
        return self.data.unit_model(self.cls[uid], self.look.get(uid, 0))

    def parts(self, uid: int, names: list[str], stretch: Optional[float] = None) -> list[Part]:
        """Части по именам («*» — по кругу). stretch — растянуть первую часть до стольких мс.
        Анимации, которой у модели нет, подбирается замена (DIE ↔ DIE_BLOW_1/2)."""
        model = self.model(uid)
        out = []
        for name in names:
            loop = name.endswith("*")
            for anim in self.data.anim_names(model, name.rstrip("*")):
                native = self.data.length_ms(model, anim)
                if native <= 0:
                    continue
                if out and out[-1].anim == anim and anim != name.rstrip("*"):
                    continue                       # замена повторила предыдущую часть (DIE_BLOW_1/2 → DIE)
                ms = native
                if not out and stretch is not None and not loop:
                    ms = stretch
                out.append(Part(anim, ms, native, loop))
        return out

    def phase(self, uid: int, name: str, stretch: Optional[float] = None) -> list[Part]:
        return self.parts(uid, self.data.phase(self.cls[uid], name), stretch)

    def play(self, uid: int, at: float, parts: list[Part], then: str = "stance") -> float:
        """Клип с момента at; возвращает его конец (у клипа без конечных частей — at)."""
        if not parts:
            return at
        self.tl.track(uid).add_clip(Clip(at, parts, then))
        return at + sum(p.ms for p in parts if not p.loop)

    def stance(self, uid: int, at: float) -> None:
        parts = self.phase(uid, "stance")
        if parts:
            self.tl.track(uid).add_clip(Clip(at, parts, "stance"))

    def move(self, uid: int, at: float, to: Spot, speed: float = RUN_SPEED, arc: float = 0.0,
             ms: Optional[float] = None, ease: str = "linear") -> float:
        start = self.where[uid]
        dist = abs(to.x - start.x) + abs(to.y - start.y)
        ms = ms if ms is not None else max(180.0, dist / speed)
        self.tl.track(uid).moves.append(Move(at, ms, start, to, arc, ease))
        self.where[uid] = to
        return at + ms

    def chain(self, uid: int, skill_id: str, kind: str, timing: Optional[dict] = None
              ) -> tuple[list[Part], list[float], list[float]]:
        """Цепочка удара навыка: части, моменты действия и моменты начала движения (мс от начала цепочки).

        Моменты — из событий анимаций (секция s11 .mbs): тип 0 — удар или выпуск (у мага — тик 0 части
        *_2_IDLE, то есть конец каста; у лучника — начало ATTACK_END; у вора два удара — два события),
        тип 1 — начало движения (взлёт грифона, прыжок вора). Событий нет — момент по форме цепочки."""
        animation = self.data.animation(skill_id)
        using_animation = bool(animation and animation.get("parts"))
        names = list(animation["parts"]) if using_animation else \
            self.data.skill_chain(self.cls[uid], skill_id)
        if not names:
            names = self.data.default_chain(self.cls[uid], kind)
            using_animation = False
        model = self.model(uid)
        # Привязанная анимация могла быть собрана на другой модели: если ни одна её часть
        # не найдена у этого класса, показываем обычную атаку/каст класса.
        if model is not None and names and not any(n.rstrip("*") in model.puppet.anims for n in names):
            names = self.data.default_chain(self.cls[uid], kind)
            using_animation = False
        parts, hits, moves = [], [], []
        at = 0.0
        holds = dict((animation or {}).get("holds", {})) if using_animation else {}
        holds.update({int(k): float(v) for k, v in (timing or {}).get("holds", {}).items()})
        for name in names:
            if name.endswith("_EFFECT"):             # эффект класса (у виверны), а не поза тела
                continue
            for anim in self.data.anim_names(model, name):
                native = self.data.length_ms(model, anim)
                if native <= 0:
                    continue
                if parts and parts[-1].anim == anim and anim != name:
                    continue                         # замена повторила предыдущую часть
                hold = "IDLE" in anim or model.puppet.is_hold(anim)     # удержание (прицел, каст): недолго
                ms = min(native, IDLE_HOLD) if hold else native
                if len(parts) in holds:                 # длительность части задана в редакторе
                    ms = max(TICK_MS, holds[len(parts)])
                    hold = hold or ms != native
                parts.append(Part(anim, ms, ms if hold else native))
                k = ms / native
                for tick, kind_ in model.puppet.events(anim):
                    when = at + min(tick * TICK_MS * k, ms)
                    (hits if kind_ == 0 else moves if kind_ == 1 else []).append(when)
                at += ms
        if not parts:
            return [], [300.0], []
        if (timing or {}).get("hits"):              # удары заданы в редакторе
            hits = [float(h) for h in timing["hits"]]
        if not hits:
            # без событий: после первого удержания — в начале следующей части; без удержаний — во второй
            idle = next((i for i, p in enumerate(parts) if "IDLE" in p.anim), None)
            k = idle + 1 if idle is not None and idle + 1 < len(parts) else (1 if len(parts) > 1 else 0)
            hits = [sum(p.ms for p in parts[:k]) + parts[k].ms * (0.35 if k else 0.5)]
        return parts, sorted(hits), sorted(moves)

    # --- плашки ---

    def plate(self, uid: int, at: float, **change) -> None:
        shown = self.shown[uid]
        new = Plate(at, change.get("hp", shown.hp), shown.max_hp, change.get("ap", shown.ap), change.get("pp", shown.pp),
                    change.get("alive", shown.alive))
        self.shown[uid] = new
        self.tl.track(uid).plates.append(new)

    # --- эффекты и надписи ---

    def fx(self, name: str, at: float, spot: Spot, front: bool = True, flip: Optional[bool] = None,
           lift: float = 0.0, ms: Optional[float] = None, uid: Optional[int] = None) -> float:
        """Эффект Battle_Effect у точки (lift — выше ног); возвращает его длительность.
        ms — показывать столько мс (интервал из редактора), иначе родная длина анимации.
        uid — эффект привязан к бойцу (следует за ним во время движения)."""
        if not name or self.fx_model is None or name not in self.fx_model.puppet.anims:
            return 0.0
        native = self.data.length_ms(self.fx_model, name)
        shown = native if ms is None else max(1.0, ms)
        if uid is not None:
            self.tl.fx.append(Fx(at, name, 0.0, -lift, 1.0,
                                 spot.facing < 0 if flip is None else flip, shown, front, uid))
        else:
            self.tl.fx.append(Fx(at, name, spot.x, spot.y - lift * spot.scale, spot.scale,
                                 spot.facing < 0 if flip is None else flip, shown, front))
        return shown

    def caster_fx(self, uid: int, spec: Optional[dict], at: float) -> None:
        """Эффекты на применившем: интервалы от начала цепочки тела."""
        for item in (spec or {}).get("caster_fx", ()):
            start = at + float(item.get("start", 0.0))
            end = float(item.get("end", 0.0))
            self.fx(item["anim"], start, self.where.get(uid, self.home[uid]), lift=CAST_LIFT, uid=uid,
                    ms=(end - float(item.get("start", 0.0))) if end > 0 else None)

    def target_fx(self, uid: int, at: float, spec: Optional[dict]) -> None:
        """Эффекты на цели в момент попадания: start/end — смещения от удара."""
        for item in (spec or {}).get("target_fx", ()):
            start = float(item.get("start", 0.0))
            end = float(item.get("end", 0.0))
            self.fx(item["anim"], at + start, self.where.get(uid, self.home[uid]), lift=HIT_LIFT, uid=uid,
                    ms=(end - start) if end > start else None)

    def has_target_fx(self, spec: Optional[dict]) -> bool:
        return bool(spec and spec.get("target_fx"))

    def popup(self, uid: int, at: float, kind: str, value: Optional[int] = None, crit: bool = False,
              guard: bool = False) -> None:
        anims = [a for a in popup_anims(kind, crit, guard) if self.ui is not None and a in self.ui.puppet.anims]
        if anims:
            # у цифр UO прозрачное вступление: запускаем раньше, чтобы число проявилось в момент удара
            lead = min(self.data.lead_in_ms(self.ui, a) for a in anims)
            ms = min(POPUP_MAX, max(self.data.length_ms(self.ui, a) for a in anims))
            self.tl.popups.append(Popup(at - lead, uid, anims, value, ms))

    def banner(self, uid: int, at: float, end: float, text: str, passive: bool) -> None:
        self.tl.banners.append(Banner(at, end, text, self.side[uid], passive))

    def name(self, act: Act) -> str:
        db = self.battle.db
        if act.kind == PASSIVE:
            passive = db.passives.get(act.skill_id)
            return passive.name if passive else act.skill_id
        skill = db.skills.get(act.skill_id)
        return skill.name if skill else act.skill_id

    # --- сцены ---

    def intro(self, at: float) -> float:
        """Выход на поле: отряды вбегают со своих краёв, тормозят, встают в стойку."""
        end = at
        for uid, home in self.home.items():
            if not self.shown[uid].alive:
                continue
            sign = -1 if self.side[uid] == 0 else 1
            start = Spot(home.x + sign * OFFSCREEN, home.y, home.scale, home.facing)
            self.where[uid] = start
            self.tl.track(uid).moves.append(Move(at - 1, 1, start, start))
            arrive = self.move(uid, at, home, ms=900, ease="out")
            dash = self.phase(uid, "dash", stretch=900)
            t = self.play(uid, at, dash + self.phase(uid, "stop"))
            self.stance(uid, max(t, arrive))
            self.plate(uid, at)
            end = max(end, t, arrive)
        return end + SETTLE

    def act(self, act: Act, at: float) -> float:
        """Сцена акта с момента at; возвращает её конец."""
        if act.kind == START:
            t = self.intro(at)
            return self.passives(act.after, t)
        if act.kind == END:
            t = self.passives(act.after, at)
            return self.ending(act, t)
        if act.kind == SKIP:
            return self.passives(act.after, at + 350)
        if act.kind == ROUND:
            return self.passives(act.after, at)
        if act.kind == ACTIVE:
            return self.active(act, at)
        if act.kind == AFFLICTION:
            return self.affliction(act, at)
        return self.passives([act], at)

    def affliction(self, act: Act, at: float) -> float:
        uid = act.actor
        for change in act.changes:
            if change.kind == "damage":
                self.popup(uid, at, "damage", change.value)
                self.play(uid, at, self.phase(uid, "hit"))
                self.plate(uid, at, hp=change.current)
            elif change.kind == "heal":
                if change.value:
                    self.popup(uid, at, "heal", change.value)
                self.fx(GENERIC["heal"], at, self.where[uid])
                self.plate(uid, at, hp=change.current)
        t = at + 650
        for dead in act.deaths:
            t = max(t, self.death(dead, at + 300))
        return t

    def active(self, act: Act, at: float) -> float:
        uid = act.actor
        t = at
        for sub in act.before:                      # яд, ожог — до ленты
            if sub.kind == AFFLICTION:
                t = self.affliction(sub, t)
        if not self.battle.units[uid].is_alive and uid in act.deaths:
            return t
        info = self.data.skill(act.skill_id, self.cls.get(uid))
        kind = info.get("kind", "melee")
        banner_from = t
        self.focus(t, [uid] + act.targets)
        self.fx(GENERIC["skill_on"], t, self.where[uid])
        shown = self.shown[uid]
        self.plate(uid, t, ap=max(0, shown.ap - act.ap_cost), pp=max(0, shown.pp - act.pp_cost))
        t += BANNER_LEAD
        covers = {ward: protector for protector, ward in act.covers}
        for sub in act.before:                      # прикрытие, блок, усиления — до удара
            if sub.kind == PASSIVE:
                t = self.passive_before(sub, t, covers)
        t = self.perform(uid, act, info, kind, t)
        for sub in act.after:
            t = self.passive_scene(sub, t)
        leave = t
        home = self.go_home(uid, t, jump=self.data.skill_timing(self.cls[uid], act.skill_id).get("ret") == "jump")
        t = leave + (home - leave) * self.data.timing.get("next_start", 0.5) if home > leave else t + SETTLE
        for protector in covers.values():
            t = max(t, self.go_home(protector, leave - 200, jump=True))
        end = t
        self.banner(uid, banner_from, end - 100, self.name(act), passive=False)
        self.unfocus(end - 150)
        return end

    def perform(self, uid: int, act: Act, info: dict, kind: str, t: float) -> float:
        """Сближение (ближний бой), цепочка удара, удары по целям; возвращает конец удара."""
        target = act.target if act.target is not None else (act.targets[0] if act.targets else uid)
        hostile = target in self.side and self.side[target] != self.side[uid]
        skill_id = act.skill_used or act.skill_id
        timing = self.data.skill_timing(self.cls[uid], skill_id)
        spec = self.data.skill_animation(skill_id)
        parts, hits, moves = self.chain(uid, skill_id, kind, timing)
        approach, ret = timing.get("approach", "auto"), timing.get("ret", "auto")
        trajectory = (spec or {}).get("trajectory") if kind in ("ranged", "magic") else None
        own_shot = bool(trajectory) or bool(info.get("shot")) or (
            self.data.classes.get(self.cls[uid], {}).get("shot") if kind == "ranged" else None)
        # Перемещение — по событиям цепочки (тип 1 — начало движения): у разбитой на части цепочки
        # (ATTACK_A1..A4, рыцарь ATTACK_1..4) или у класса без разбега (летуны) путь к цели идёт внутри
        # неё; одиночная анимация (ATTACK_1 бойца) играется у цели, к которой ведут разбег DASH_1/DASH_2.
        before = [m for m in moves if m < hits[0]]
        after = [m for m in moves if m > hits[-1]]
        in_chain = (hostile and not own_shot and bool(before)
                    and (len(parts) > 1 or not self.phase(uid, "dash")))
        if not walks_up(kind, approach):             # дальние и магия — с места, без сближения
            in_chain = False
        if approach != "auto":                       # подход задан в редакторе
            in_chain = approach == "chain" and hostile
            if approach == "chain":
                before = [float(timing.get("approach_from", 0.0)), float(timing.get("approach_to", hits[0]))]
        if approach == "jump" and hostile:           # прыжок к цели (JUMP_1 / JUMP_2)
            goal = self.where[target].ahead(APPROACH)
            goal = Spot(goal.x, goal.y, goal.scale, self.home[uid].facing)
            arrive = self.move(uid, t, goal, arc=90, ms=420)
            self.play(uid, t, self.phase(uid, "jump", stretch=420) + self.phase(uid, "land"), then="hold")
            t = arrive
        elif approach == "none":
            pass
        elif in_chain or (hostile and (kind == "melee" or approach == "dash")):
            goal = self.where[target].ahead(APPROACH)
            goal = Spot(goal.x, goal.y, goal.scale, self.home[uid].facing)
            if in_chain:
                leave = before[0]
                arrive = before[-1] if len(before) > 1 and before[-1] - before[0] > 120 else hits[0]
                if approach == "chain":
                    arrive = before[1]
                # тело само уходит вперёд внутри анимации (выпад копьём у рыцаря): стать дальше на этот выпад
                lunge = self.lunge(uid, parts, arrive, hits[0])
                if lunge > 0:
                    goal = self.where[target].ahead(APPROACH + lunge)
                    goal = Spot(goal.x, goal.y, goal.scale, self.home[uid].facing)
                self.move(uid, t + leave, goal, ms=max(120.0, arrive - leave), ease="out")
            else:
                arrive = self.move(uid, t, goal, ms=self.data.ticks("move_attack", 25))
                self.play(uid, t, self.phase(uid, "dash", stretch=arrive - t), then="hold")
                t = arrive
                self.fx(GENERIC["dash"], t, goal, front=False)
                t = self.play(uid, t, self.phase(uid, "stop"), then="hold")
        elif kind in MAGIC_KINDS:
            self.fx(GENERIC["chant"], t, self.where[uid], front=False)        # круг заклинания — у ног
        end = self.play(uid, t, parts, then="hold") if parts else t + 300
        caster_fx = bool((spec or {}).get("caster_fx"))
        if caster_fx:
            self.caster_fx(uid, spec, t)
        if ret == "chain":                           # возврат внутри цепочки с заданного момента
            after = [float(timing.get("ret_from", hits[-1] + 1))]
        if ret == "chain" or (ret == "auto" and in_chain and after and len(parts) > 1):
            # возврат — тоже внутри цепочки: с начала движения после удара до последней части (успокоение)
            total = sum(p.ms for p in parts)
            last_start = total - parts[-1].ms
            stop = last_start if after[0] < last_start else total
            self.move(uid, t + after[0], self.home[uid], ms=max(120.0, stop - after[0]), ease="out")
        release = t + hits[0]
        custom_hit = self.has_target_fx(spec)
        hit_fx = "" if custom_hit else (info.get("hit") or ["HIT_A"])[0]
        heal = kind == "heal"
        rain = (spec or {}).get("rain") if kind in ("ranged", "magic") else None
        if rain and hostile and act.targets:             # новый «дождь»: набор эффектов по стороне противника
            arrivals = self.rain_fx(uid, act, rain, release)
            last = self.strikes(act, release, lambda strike: arrivals(strike), hit_fx, heal, stop=False,
                                target_fx=(spec or {}).get("target_fx"))
            return max(end, release + float(rain.get("duration", 0.0)) + 450, last + 450)
        rain = info.get("rain")
        if rain and hostile and act.targets:            # старый дождь стрел: выстрел вверх, стрелы падают на цели
            arrivals = self.rain(uid, act, rain, release)

            def when_rain(strike: Strike) -> float:
                times = arrivals.get(strike.target) or [release]
                k = strike.hit_index
                return times[min(k, len(times) - 1)] + max(0, k - len(times) + 1) * HIT_SPACING
            last = self.strikes(act, release, when_rain, hit_fx, heal, stop=False,
                                target_fx=(spec or {}).get("target_fx"))
            return max(end, last + 450)
        shot = info.get("shot")
        if shot is None and kind == "ranged":
            shot = self.data.classes.get(self.cls[uid], {}).get("shot")
        if (trajectory or shot) and hostile and act.targets:
            trajectory = trajectory or None
            if shot is None:
                shot = {"anim": (trajectory or {}).get("anim") or
                                (self.data.classes.get(self.cls[uid], {}).get("shot") or {}).get("anim", ""),
                        "speed": (trajectory or {}).get("speed", 60.0)}
            if not shot.get("speed"):                  # своей скорости нет — как у оружия класса
                weapon = self.data.classes.get(self.cls[uid], {}).get("shot") or {}
                shot = {**shot, "speed": weapon.get("speed") or 60.0}
            if shot.get("anim") or trajectory:
                arrivals = self.volley(uid, act, info, shot, release, trajectory=trajectory,
                                       out_fx="" if caster_fx else None,
                                       hit_fx="" if custom_hit else None)

                def when(strike: Strike) -> float:
                    times = arrivals.get(strike.target) or [release]
                    k = strike.hit_index
                    return times[min(k, len(times) - 1)] + max(0, k - len(times) + 1) * HIT_SPACING
                last = self.strikes(act, release, when, hit_fx, heal, stop=False,
                                    target_fx=(spec or {}).get("target_fx"))
                return max(end, last + 450)
        if not custom_hit and not caster_fx and info.get("out"):   # выпуск заклинания — у применившего
            self.fx(info["out"], release, self.where[uid], lift=CAST_LIFT)
        later = self.buffer_fx(uid, act, info, release) - release   # предвестник на целях, потом главный
        if not custom_hit:
            self.cast_fx(uid, act, info, kind, release + later)

        def when(strike: Strike) -> float:          # k-й удар навыка — k-е событие удара цепочки
            k = strike.hit_index
            return t + later + (hits[k] if k < len(hits) else hits[-1] + (k - len(hits) + 1) * HIT_SPACING)
        last = self.strikes(act, release + later, when, hit_fx, heal,
                            target_fx=(spec or {}).get("target_fx"))
        return max(end, last + 450)

    def lunge(self, uid: int, parts: list[Part], since: float, until: float) -> float:
        """На сколько тело уходит вперёд внутри анимаций цепочки между моментами since и until (мс от её
        начала): сдвиг центра рамки тела куклы, единицы сцены."""
        model = self.model(uid)
        if model is None or until <= since:
            return 0.0

        def center(ms: float) -> Optional[float]:
            at = 0.0
            for part in parts:
                if ms < at + part.ms or part is parts[-1]:
                    tick = min(int((ms - at) * part.native / max(1.0, part.ms) / TICK_MS),
                               max(0, model.length(part.anim) - 1))
                    box = model.puppet.bbox(model.puppet.evaluate(part.anim, tick))
                    return None if box is None else (box[0] + box[2]) / 2
                at += part.ms
            return None
        a, b = center(since), center(until)
        return 0.0 if a is None or b is None else max(0.0, b - a)

    def rain(self, uid: int, act: Act, rain: dict, release: float) -> dict[int, list[float]]:
        """Дождь стрел (UO: ARROWRAIN_OUT, BTSHOT ARROWRAIN_*): выпуск вверх у стрелка, потом на каждую цель
        падают стрелы — рядом друг с другом (шаг interval_x), раз в interval тиков со случайной задержкой
        rand_from..rand_to, сверху и со стороны стрелка (start_x), со скоростью speed; удар о землю —
        ARROWRAIN_HIT_01/02. Возвращает, когда долетает каждая стрела по целям."""
        src = self.where[uid]
        facing = self.home[uid].facing
        out_ms = self.fx(rain.get("out", ""), release, src, lift=CAST_LIFT)
        fall = release + out_ms * 0.5
        arrow = (self.data.classes.get(self.cls[uid], {}).get("shot") or {}).get("anim", "BOW_SHOT")
        speed = max(1.0, float(rain.get("speed") or 80.0))
        start_x, step = float(rain.get("start_x") or 500.0), float(rain.get("interval_x") or 100.0)
        every = float(rain.get("interval") or 10.0)
        lo, hi = float(rain.get("rand_from") or 0.0), float(rain.get("rand_to") or 80.0)
        hits = list(rain.get("hit") or [])
        count = max(3, act.hits)
        arrivals: dict[int, list[float]] = {}
        for tid in dict.fromkeys(act.targets):
            if tid not in self.where:
                continue
            dst = self.where[tid]
            for i in range(count):
                jitter = lo + (hash((uid, tid, i, self.battle.round)) % 1000) / 1000 * (hi - lo)
                start = fall + (every * i + jitter) * TICK_MS
                bx = dst.x + (i - (count - 1) / 2) * step * 0.5 * dst.scale
                by = dst.y - 30 * dst.scale
                ax, ay = bx - facing * start_x * dst.scale, by - 900 * dst.scale
                ms = max(60.0, math.hypot(bx - ax, by - ay) / speed * TICK_MS)
                self.tl.shots.append(Shot(start, arrow, (ax, ay), (bx, by), ms, dst.scale, 0.0, TICK_MS))
                if hits:
                    self.fx(hits[i % len(hits)], start + ms, Spot(bx, by, dst.scale, facing), flip=facing < 0)
                arrivals.setdefault(tid, []).append(start + ms)
        return {tid: sorted(times) for tid, times in arrivals.items()}

    def volley(self, uid: int, act: Act, info: dict, shot: dict, launch: float,
               trajectory: Optional[dict] = None, out_fx: Optional[str] = None,
               hit_fx: Optional[str] = None) -> dict[int, list[float]]:
        """Снаряды к целям (главной — весь залп, остальным — по одному); когда долетает каждый.

        trajectory — необязательная кривая из редактора: anim, curve, speed, fall. Если она есть,
        снаряд летит по ней; иначе — по прямой/навесной дуге, как раньше."""
        src = self.where[uid]
        facing = self.home[uid].facing
        speed = max(1.0, float((trajectory or {}).get("speed") or shot.get("speed") or 60.0))
        fall = float((trajectory or {}).get("fall") or shot.get("fall") or 0.0)
        path = tuple((trajectory or {}).get("curve") or ())
        if trajectory and trajectory.get("anim"):
            shot = {**shot, "anim": trajectory["anim"]}
        balls = shot.get("volley") or [[0.0, 0.0, 0.0]]
        if out_fx is None:
            out_fx = info.get("out")
        if hit_fx is None:
            hit_fx = (info.get("hit") or [""])[0]
        arrivals: dict[int, list[float]] = {}
        for n, tid in enumerate(dict.fromkeys(act.targets)):
            if tid not in self.where:
                continue
            dst = self.where[tid]
            bx, by = dst.x - facing * SHOT_STOP * dst.scale, dst.y - HIT_LIFT * dst.scale
            for dx, dy, wait in (balls if n == 0 else balls[:1]):
                start = launch + wait * TICK_MS
                ax = src.x + facing * (SHOT_AHEAD + dx) * src.scale
                ay = src.y + (dy - SHOT_LIFT) * src.scale
                span = abs(bx - ax) if fall and not path else math.hypot(bx - ax, by - ay)
                if path:
                    span = curve_length((ax, ay), (bx, by), path)
                ms = max(60.0, span / speed * TICK_MS)
                flight = Shot(start, shot["anim"], (ax, ay), (bx, by), ms, src.scale, fall, TICK_MS, path=path)
                self.tl.shots.append(flight)
                if shot.get("trail"):
                    t = 0.0
                    while t < ms:
                        x, y, _, flip = flight.at(start + t)
                        self.fx(shot["trail"], start + t, Spot(x, y, src.scale, facing), flip=flip)
                        t += TRAIL_EVERY * TICK_MS
                if out_fx and not (trajectory and trajectory.get("anim") == out_fx):
                    self.fx(out_fx, start, Spot(ax, ay, src.scale, facing), flip=facing < 0)
                if hit_fx:
                    self.fx(hit_fx, start + ms, Spot(bx, by, dst.scale, facing), flip=facing < 0)
                arrivals.setdefault(tid, []).append(start + ms)
        return {tid: sorted(times) for tid, times in arrivals.items()}

    def rain_fx(self, uid: int, act: Act, rain: dict, release: float):
        """Дождь эффектов: count экземпляров каждого эффекта равномерно по стороне противника
        и по времени duration. Возвращает функцию «когда падает k-й удар по цели»."""
        facing = self.home[uid].facing
        own_side = self.side[uid]
        spots = [self.where[x] for x in self.where if x in self.side and self.side[x] != own_side]
        spots = [s for s in spots if s is not None]
        if not spots:
            spots = [self.where[x] for x in act.targets if x in self.where]
        if not spots:
            spots = [self.where[uid]]
        xs = [s.x for s in spots]
        lo, hi = min(xs) - 140 * spots[0].scale, max(xs) + 140 * spots[0].scale
        if hi - lo < 180:
            lo, hi = lo - 90, hi + 90
        base_y = sum(s.y for s in spots) / len(spots)
        scale = sum(s.scale for s in spots) / len(spots)
        entries = list(rain.get("entries", ()))
        # Круговая очередь: типы эффектов чередуются, а не идут блоками.
        queue: list[str] = []
        left = [int(item.get("count", 0)) for item in entries]
        while any(n > 0 for n in left):
            for i, item in enumerate(entries):
                if left[i] > 0:
                    queue.append(str(item.get("anim")))
                    left[i] -= 1
        if not queue:
            return lambda strike: release
        duration = max(100.0, float(rain.get("duration", 1200.0)))
        fall_ms = max(180.0, min(420.0, duration / max(1, len(queue)) * 3))
        times: list[float] = []
        for i, anim in enumerate(queue):
            at = release + duration * (i + 0.5) / len(queue)
            x = lo + (hi - lo) * (i + 0.5) / len(queue)
            # немного вразнобой по высоте, чтобы дождь не выглядел строем
            jitter = ((i * 37) % 11 - 5) * 7 * scale
            start = (x - facing * 90 * scale, base_y - 760 * scale + jitter)
            path = ((0.0, 0.0), (0.55, -0.06), (1.0, 0.0))
            flight = Shot(at, anim, start, (x, base_y - 10 * scale), fall_ms, scale,
                          tick_ms=TICK_MS, path=path)
            self.tl.shots.append(flight)
            times.append(at + fall_ms)
        times.sort()

        def when(strike: Strike) -> float:
            k = min(strike.hit_index, len(times) - 1)
            return times[k]
        return when


    def buffer_fx(self, uid: int, act: Act, info: dict, at: float) -> float:
        """Предвестники (UO: *_BUFFER, 予兆) — на целях, широкие — по центру; возвращает, когда они
        отыграли (с этого момента главный эффект и попадание)."""
        names = [n for n in info.get("buffer", []) if self.fx_model is not None and n in self.fx_model.puppet.anims]
        if not names:
            return at
        facing = self.home[uid].facing
        targets = [x for x in dict.fromkeys(act.targets) if x in self.where] or [uid]
        end = at
        for name in names:
            box = self.fx_model.box(name)
            if box and box[2] - box[0] > WIDE_FX:
                spots = [self.where[x] for x in targets]
                n = len(spots)
                spots = [Spot(sum(s.x for s in spots) / n, sum(s.y for s in spots) / n,
                              sum(s.scale for s in spots) / n, facing)]
            else:
                spots = [self.where[x] for x in targets]
            for spot in spots:
                end = max(end, at + self.fx(name, at, spot, flip=facing < 0))
        return end

    def cast_fx(self, uid: int, act: Act, info: dict, kind: str, at: float) -> None:
        """Свои эффекты навыка без снаряда: на всё поле — по центру целей; ближний и дальний удар —
        у атакующего (след оружия, рывок); заклинание — на каждой цели (столп, вспышка)."""
        model = self.fx_model
        facing = self.home[uid].facing
        targets = [x for x in dict.fromkeys(act.targets) if x in self.where] or [uid]
        for name in info.get("cast", []):
            box = model.box(name) if model is not None and name in model.puppet.anims else None
            if box is None:
                continue
            if box[2] - box[0] > WIDE_FX:
                spots = [self.where[x] for x in targets]
                n = len(spots)
                self.fx(name, at, Spot(sum(s.x for s in spots) / n, sum(s.y for s in spots) / n,
                                       sum(s.scale for s in spots) / n, facing), flip=facing < 0)
            elif kind not in MAGIC_KINDS or targets == [uid]:
                self.fx(name, at, self.where[uid], flip=facing < 0)
            else:
                for x in targets:
                    self.fx(name, at, self.where[x], flip=facing < 0)

    def strikes(self, act: Act, first: float, when: Callable[[Strike], float], hit_fx: str, heal: bool,
                stop: bool = True, target_fx: Optional[list[dict]] = None) -> float:
        """Удары по целям в их моменты; эффекты, AP/PP и гибель без удара — после. Возвращает последний.
        stop — крит и блок задерживают следующие удары (UO: hitstop; у снарядов моменты заданы полётом).
        target_fx — эффекты на цели, отсчитываемые от каждого попадания."""
        last = first
        delay = 0.0
        for strike in act.strikes:
            at = when(strike) + delay
            last = max(last, at)
            self.strike(act, strike, at, hit_fx, heal)
            if target_fx and strike.target in self.where and strike.outcome not in (MISS, EVADE):
                self.target_fx(strike.target, at, {"target_fx": target_fx})
            if stop and strike.crit:
                delay += self.data.ticks("hitstop_crit", 15)
            elif stop and strike.guard:
                delay += self.data.ticks("hitstop_guard", 10)
        for change in act.changes:                  # эффекты, AP/PP — после ударов
            self.change(change, last + 120)
        for dead in act.deaths:
            if dead not in [s.target for s in act.strikes if s.died]:
                self.death(dead, last + 200)
        return last

    def strike(self, act: Act, strike: Strike, at: float, hit_fx: str, heal: bool = False) -> None:
        uid = strike.target
        spot = self.where[uid]
        if heal or strike.heal:
            self.fx(GENERIC["heal"], at, spot)
            if strike.heal:
                self.popup(uid, at, "heal", strike.heal, strike.crit)
            self.plate(uid, at, hp=strike.hp)
            return
        if strike.outcome in (MISS, EVADE):
            self.play(uid, at, self.phase(uid, "avoid"))
            self.popup(uid, at, "miss")
            return
        self.fx(hit_fx, at, spot, lift=120)
        if strike.guard:
            self.fx(GENERIC["guard"], at, spot, lift=110)
            self.play(uid, at, self.phase(uid, "guard"))
        elif strike.outcome == NEGATE:
            self.fx(GENERIC["guard"], at, spot, lift=110)
        else:
            self.play(uid, at, self.phase(uid, "hit"))
        self.popup(uid, at, "damage", strike.damage, strike.crit, strike.guard is not None)
        self.plate(uid, at, hp=strike.hp)
        if strike.died:
            self.death(uid, at + 120)

    def change(self, change, at: float) -> None:
        uid = change.target
        if uid not in self.where:
            return
        if change.kind == "effect":
            definition = self.battle.db.effects.get(change.effect_id)
            bad = definition is not None and "debuff" in definition.tags
            self.fx(GENERIC["debuff" if bad else "buff"], at, self.where[uid])
        elif change.kind in ("ap", "pp"):
            self.plate(uid, at, **{change.kind: change.current})
        elif change.kind == "heal":
            self.fx(GENERIC["heal"], at, self.where[uid])
            if change.value:
                self.popup(uid, at, "heal", change.value)
            self.plate(uid, at, hp=change.current)
        elif change.kind == "damage":
            self.popup(uid, at, "damage", change.value)
            self.plate(uid, at, hp=change.current)

    def death(self, uid: int, at: float) -> float:
        if not self.shown[uid].alive:
            return at
        end = self.play(uid, at, self.phase(uid, "die") or self.phase(uid, "hit"), then="hold")
        fade_at = end + self.data.ticks("die_wait", 20)
        fade = self.data.ticks("die_fade", 30)
        self.fx(GENERIC["died"], fade_at - 100, self.where[uid])
        self.tl.track(uid).fade = (fade_at, fade)
        self.plate(uid, at, alive=False, hp=0)
        return fade_at + fade

    def passives(self, acts: list[Act], at: float) -> float:
        t = at
        for act in acts:
            t = self.passive_scene(act, t)
        return t

    def passive_before(self, act: Act, t: float, covers: dict[int, int]) -> float:
        """Пассивка до удара: прикрытие — прыжок к союзнику; остальное — короткая сцена."""
        uid = act.actor
        ward = next((w for w, p in covers.items() if p == uid), None)
        if ward is None:
            return self.passive_scene(act, t)
        self.banner(uid, t, t + 1300, self.name(act), passive=True)
        self.fx(GENERIC["passive_on"], t, self.where[uid])
        spot = self.where[ward].ahead(70)
        spot = Spot(spot.x, spot.y + 4, spot.scale, self.home[uid].facing)
        arrive = self.move(uid, t, spot, arc=90, ms=420)
        jump = self.phase(uid, "cover") or self.phase(uid, "jump", stretch=420) + self.phase(uid, "land")
        self.play(uid, t, jump, then="hold")
        self.fx(GENERIC["land"], arrive, spot, front=False)
        self.fx(GENERIC["guard"], arrive, spot, lift=110)
        for change in act.changes:
            self.change(change, arrive)
        return arrive + 120

    def passive_scene(self, act: Act, t: float) -> float:
        """Пассивка своей сценой: синяя лента, аура; навык-ответ — как ход, иначе — эффекты на целях."""
        uid = act.actor
        if uid is None or uid not in self.where:
            return t
        start = t
        self.fx(GENERIC["passive_on"], t, self.where[uid])
        shown = self.shown[uid]
        self.plate(uid, t, pp=max(0, shown.pp - act.pp_cost))
        if act.skill_used:
            info = self.data.skill(act.skill_used, self.cls.get(uid))
            t = self.perform(uid, act, info, info.get("kind", "melee"), t + 300)
            t = self.go_home(uid, t, jump=self.data.skill_timing(self.cls[uid], act.skill_used).get("ret") == "jump")
        else:
            for strike in act.strikes:
                self.strike(act, strike, t + 300, "HIT_A")
            for change in act.changes:
                self.change(change, t + 300)
            for dead in act.deaths:
                self.death(dead, t + 400)
            t += PASSIVE_SCENE
        self.banner(uid, start, t, self.name(act), passive=True)
        return t + 100

    def go_home(self, uid: int, t: float, jump: bool = False) -> float:
        """На своё место: бегом (BACK_1) или прыжком, разворот (BACK_2), стойка."""
        home = self.home[uid]
        here = self.where[uid]
        if not self.shown[uid].alive:
            return t
        if abs(here.x - home.x) < 2 and abs(here.y - home.y) < 2:
            self.stance(uid, t)
            return t
        if jump:
            arrive = self.move(uid, t, home, arc=80, ms=420)
            self.play(uid, t, self.phase(uid, "jump", stretch=420) + self.phase(uid, "land"))
            self.stance(uid, arrive + 200)
            return arrive
        front = self.battle.side_of(self.battle.units[uid]).pos(self.battle.units[uid])[0] == 0
        ms = self.data.ticks("return_front" if front else "return_back", 25 if front else 34)
        arrive = self.move(uid, t, home, ms=ms)
        self.play(uid, t, self.phase(uid, "back", stretch=arrive - t) + self.phase(uid, "home"))
        return arrive

    def ending(self, act: Act, t: float) -> float:
        """Конец боя: победители радуются."""
        winners = [uid for uid in self.home if self.shown[uid].alive and act.winner is not None and
                   self.battle.side_of(self.battle.units[uid]).id == act.winner]
        end = t
        for uid in winners:
            end = max(end, self.play(uid, t, self.phase(uid, "victory"), then="hold"))
        self.unfocus(t)
        return t + 600

    # --- камера ---

    def focus(self, at: float, uids: list[int]) -> None:
        spots = [self.where[u] for u in uids if u in self.where]
        if not spots:
            return
        xs, ys = [s.x for s in spots], [s.y for s in spots]
        box = (min(xs) - 260, min(ys) - 520, max(xs) + 260, max(ys) + 140)
        self.tl.focus.append(Focus(at, FOCUS_MS, box))

    def unfocus(self, at: float) -> None:
        self.tl.focus.append(Focus(at, FOCUS_MS, None))
