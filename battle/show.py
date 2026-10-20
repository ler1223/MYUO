"""Показ боя UO: бой по правилам (game.combat) проигрывается сценами (battle.director) на фоне UO.

    show = BattleShow(db, attacker, defender, seed, scene_id)
    show.update(now)           # каждый кадр: время показа в мс (ускорение и пауза — у вызывающего)
    show.render(size, clip, now) -> Canvas   # кадр видеокарты: present() в окно или read_into(картинка)
    show.done(now)             # бой кончился и доигран; итог — show.battle.winner_id
    show.skip(now)             # доиграть бой сразу, показать итог

Бой идёт по актам: следующий акт берётся у боя, когда доиграна сцена предыдущего, — анимации
не начинаются поверх друг друга, итог показывается после последней.
"""
from __future__ import annotations

from typing import Optional

import pygame

from game.combat import Battle

from .data import TICK_MS, ShowData
from .director import Director
from .hud import Hud
from .render import Camera, Canvas
from .timeline import Timeline

FRONT_LAYERS = ("kinkei", "temae", "maekusa", "kyaratemae", "front")   # слои фона перед бойцами
HEAD = 300.0                   # высота головы над ногами (единицы куклы) — для цифр


class BattleShow:
    def __init__(self, db, attacker, defender, seed: Optional[int] = None, scene: Optional[str] = None,
                 data: Optional[ShowData] = None, first_strike: Optional[str] = None):
        self.data = data or ShowData()
        self.battle = Battle(attacker, defender, db, seed=seed, first_strike=first_strike)
        self.tl = Timeline()
        self.scene_files = self.data.scene(scene) or []
        self.director = Director(self.data, self.battle, self.tl, self._bottom())
        self.hud = Hud(self.data)
        self.ready = 0.0               # когда доиграет запланированное
        self.canvas: Optional[Canvas] = None
        self.round = 0
        self._seen = 0                 # сколько актов боя уже отдано режиссёру

    def _bottom(self) -> Optional[float]:
        """Нижний край сцены фона (последний файл — сама сцена, перед ним — небо)."""
        model = self.data.model("BattleBG", self.scene_files[-1]) if self.scene_files else None
        if model is None:
            return None
        return max(a["bbox"][3] for a in model.puppet.anims.values())

    # --- ход ---

    def update(self, now: float) -> None:
        """Брать у боя следующие акты, пока их сцены начинаются не позже now."""
        while not self.battle.finished and self.ready <= now:
            self.battle.step()
            fresh = self.battle.acts[self._seen:]
            self._seen = len(self.battle.acts)
            if not fresh:
                break
            for act in fresh:
                self.round = max(self.round, act.round)
                self.ready = self.director.act(act, max(now, self.ready))
        self.tl.prune(now)

    def done(self, now: float) -> bool:
        return self.battle.finished and now >= self.ready

    def skip(self, now: float) -> float:
        """Доиграть бой без сцен: плашки и павшие — как в итоге; возвращает новое «сейчас»."""
        self.battle.run()
        self.round = self.battle.round
        t = max(now, self.ready)
        for uid, unit in self.battle.units.items():
            self.director.plate(uid, t, hp=unit.hp, alive=unit.is_alive, ap=unit.ap.current, pp=unit.pp.current)
            if not unit.is_alive and self.tl.track(uid).fade is None:
                self.tl.track(uid).fade = (t, 1)
            self.director.go_home(uid, t)
        self.ready = t + 400
        return self.ready

    # --- кадр ---

    def camera(self, clip: pygame.Rect, now: float) -> Camera:
        base = self.director.stage.view(clip.width / max(1, clip.height))
        box = base
        start, goal, k = base, base, 1.0
        for focus in self.tl.focus:
            if focus.start > now:
                break
            start = box
            goal = self._fit(focus.box, base) if focus.box else base
            k = min(1.0, (now - focus.start) / max(1.0, focus.ms))
            k = 1 - (1 - k) ** 2
            box = tuple(a + (b - a) * k for a, b in zip(start, goal))
        return Camera(box, clip)

    @staticmethod
    def _fit(box, base):
        """Наезд: рамка участников в пропорциях обзора, не меньше 70 % обзора, внутри обзора."""
        bw, bh = base[2] - base[0], base[3] - base[1]
        aspect = bw / bh
        w = max(box[2] - box[0], (box[3] - box[1]) * aspect, bw * 0.72)
        h = w / aspect
        cx = (box[0] + box[2]) / 2
        bottom = min(base[3], box[3] + 40)
        x0 = min(max(cx - w / 2, base[0]), base[2] - w)
        y0 = max(base[1], bottom - h)
        return x0, y0, x0 + w, y0 + h

    def render(self, size: tuple[int, int], clip: pygame.Rect, now: float) -> Optional[Canvas]:
        if not self.data.ok:
            return None
        if self.canvas is None:
            from engine.uo.gl import GLRenderer
            self.canvas = Canvas(GLRenderer.get())
        canvas = self.canvas
        canvas.begin(size, clip)
        cam = self.camera(canvas.clip, now)
        self._background(canvas, cam, now, front=False)
        self._fx(canvas, cam, now, front=False)
        actors = self._actors(now)
        for uid, x, y, s, anim, ms, flip, alpha in sorted(actors, key=lambda a: a[2]):
            self._actor(canvas, cam, uid, x, y, s, anim, ms, flip, alpha)
        self._fx(canvas, cam, now, front=True)
        self._background(canvas, cam, now, front=True)
        self._hud(canvas, cam, actors, now)
        return canvas

    def draw(self, target: pygame.Surface, clip: pygame.Rect, now: float) -> bool:
        """Кадр в картинку pygame (одно чтение с видеокарты); False — показ недоступен."""
        canvas = self.render(target.get_size(), clip, now)
        if canvas is None:
            return False
        canvas.read_into(target, clip)
        return True

    # --- части кадра ---

    def _background(self, canvas: Canvas, cam: Camera, now: float, front: bool) -> None:
        from engine.uo.gl import GLRenderer
        gl = GLRenderer.get()
        point = cam.p(0, 0)
        for file in self.scene_files:
            model = self.data.model("BattleBG", file)
            if model is None:
                continue
            puppet = model.puppet
            for anim in puppet.anims:
                if anim.lower().startswith(FRONT_LAYERS) != front:
                    continue
                length = max(1, model.length(anim))
                tick = int(now / TICK_MS) % length if length > 1 else 0
                mesh = gl.mesh(("bg", id(model), anim, tick), puppet, lambda a=anim, t=tick: puppet.evaluate(a, t, True))
                canvas.puppet(mesh, model.pages, cam.k, False, point)

    def _actors(self, now: float) -> list:
        out = []
        for uid, home in self.director.home.items():
            track = self.tl.track(uid)
            alpha = track.alpha(now)
            if alpha <= 0:
                continue
            move = track.move_at(now)
            if move is not None:
                x, y, s = move.at(now)
            else:
                x, y, s = home.x, home.y, home.scale
            clip = track.clip_at(now)
            anim, ms = None, 0.0
            if clip is not None:
                found = clip.at(now)
                if found is None:
                    if clip.then == "hold":
                        last = [p for p in clip.parts if not p.loop][-1]
                        anim, ms = last.anim, last.native - 1
                    else:
                        found = self._stance(uid, now - clip.end)
                if found is not None:
                    anim, ms = found
            else:
                anim, ms = self._stance(uid, now + uid * 731) or (None, 0)
            out.append((uid, x, y, s, anim, ms, home.facing < 0, alpha))
        return out

    def _stance(self, uid: int, ms: float):
        parts = self.director.phase(uid, "stance")
        if not parts:
            return None
        total = sum(p.native for p in parts)
        local = ms % max(1.0, total) if parts[-1].loop is False else ms
        for part in parts:
            if part.loop:                      # циклы у треков свои: вступление стойки не повторяется
                return part.anim, local
            if local < part.native:
                return part.anim, local
            local -= part.native
        return parts[-1].anim, parts[-1].native - 1

    def _actor(self, canvas: Canvas, cam: Camera, uid: int, x: float, y: float, s: float, anim, ms: float,
               flip: bool, alpha: float) -> None:
        model = self.director.model(uid)
        if model is None or anim is None or anim not in model.puppet.anims:
            return
        from engine.uo.gl import GLRenderer
        raw = int(ms / TICK_MS)
        loop = raw >= model.length(anim)             # за концом бывает только часть «по кругу»
        tick = model.puppet.canonical_tick(anim, raw, loop)
        mesh = GLRenderer.get().mesh(("unit", id(model), anim, tick, loop), model.puppet,
                                     lambda: model.puppet.evaluate(anim, tick, loop))
        canvas.puppet(mesh, model.pages, s * cam.k, flip, cam.p(x, y), alpha)

    def _fx(self, canvas: Canvas, cam: Camera, now: float, front: bool) -> None:
        model = self.director.fx_model
        if model is None:
            return
        from engine.uo.gl import GLRenderer
        gl = GLRenderer.get()
        for fx in self.tl.fx:
            if fx.front != front or not fx.start <= now < fx.start + fx.ms:
                continue
            tick = min(int((now - fx.start) / TICK_MS), max(0, model.length(fx.anim) - 1))
            mesh = gl.mesh(("fx", id(model), fx.anim, tick), model.puppet, lambda f=fx, t=tick: model.puppet.evaluate(f.anim, t))
            x, y, scale = fx.x, fx.y, fx.scale
            if fx.uid is not None:                   # эффект привязан к бойцу: следует за его движением
                home = self.director.home.get(fx.uid)
                if home is None:
                    continue
                move = self.tl.track(fx.uid).move_at(now)
                if move is not None:
                    bx, by, bs = move.at(now)
                else:
                    bx, by, bs = home.x, home.y, home.scale
                x, y, scale = bx + fx.x * bs, by + fx.y * bs, fx.scale * bs
            canvas.puppet(mesh, model.pages, scale * cam.k, fx.flip, cam.p(x, y))
        if not front:
            return
        for shot in self.tl.shots:                   # снаряды — поверх бойцов
            if not shot.start <= now < shot.start + shot.ms or shot.anim not in model.puppet.anims:
                continue
            x, y, angle, flip = shot.at(now)
            tick = int((now - shot.start) / TICK_MS)        # циклы у треков свои (UO: i0 трека)
            mesh = gl.mesh(("fx", id(model), shot.anim, tick), model.puppet,
                           lambda s=shot, t=tick: model.puppet.evaluate(s.anim, t))
            canvas.puppet(mesh, model.pages, shot.scale * cam.k, flip, cam.p(x, y), angle=angle)

    def _hud(self, canvas: Canvas, cam: Camera, actors: list, now: float) -> None:
        where = {a[0]: a for a in actors}
        battle = self.battle
        for uid, home in self.director.home.items():
            track = self.tl.track(uid)
            plate = track.plate_at(now)
            if plate is None or uid not in where:
                continue
            unit = battle.units[uid]
            enemy = battle.side_of(unit).index == 1
            _, x, y, s, *_ = where[uid]
            self.hud.plate(canvas, cam, x, y, s, plate, unit.state.level, enemy, unit.ap.max, unit.pp.max, now)
        for popup in self.tl.popups:
            if not popup.start <= now < popup.start + popup.ms:
                continue
            spot = where.get(popup.uid)
            x, y, s = (spot[1], spot[2], spot[3]) if spot else (self.director.home[popup.uid].x,
                                                                 self.director.home[popup.uid].y, 1.0)
            self.hud.popup(canvas, cam, x, y - HEAD * s, s, popup, now)
        for banner in self.tl.banners:
            if banner.start <= now < banner.end:
                self.hud.banner(canvas, banner, now)
