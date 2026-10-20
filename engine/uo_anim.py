"""Анимации юнитов из Unicorn Overlord: что играет юнит в момент времени.

Кадры рисует видеокарта прямо из файлов игры (engine.uo.library.LiveAnims): у класса есть
состояния (idle, attack, skill, hit, avoid, guard, cover, die, victory) и анимации навыков
(skill.<навык>), состояние — цепочка частей (у атаки ближнего боя: бег к цели, удар, бег назад,
возврат в стойку). Часть — анимация игры с тика from длиной frames тиков (60 в секунду).

Clip — часть, которую юнит играет с момента start: once (один раз, потом последний кадр),
loop (по кругу) или stretch (растянуть или сжать на duration мс). Actions — клипы юнитов по uid:
pose(uid, now) отвечает, какой тик какой части показывать; без клипа — стойка по кругу.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

Part = dict                 # часть состояния: class, anim, from, frames (тики), ms, loop


@dataclass
class Clip:
    start: int
    part: Part
    mode: str = "once"              # once, loop, stretch
    duration: Optional[int] = None  # для stretch и для ограничения loop; None — естественная длина

    @property
    def end(self) -> Optional[int]:
        """Когда клип кончился; None у бесконечного loop."""
        if self.duration is not None:
            return self.start + self.duration
        return None if self.mode == "loop" else self.start + int(self.part["ms"])

    def frame(self, now: int) -> int:
        n = int(self.part["frames"])
        t = max(0, now - self.start)
        if self.mode == "stretch" and self.duration:
            return min(n - 1, int(t / self.duration * n))
        i = int(t * n / max(1, int(self.part["ms"])))
        return i % n if self.mode == "loop" else min(n - 1, i)


@dataclass
class Actions:
    """Клипы юнитов: последовательность на юнита; последний начавшийся клип и есть поза."""

    clips: dict[int, list[Clip]] = field(default_factory=dict)
    holds: dict[int, Clip] = field(default_factory=dict)     # после конца держать последний кадр (смерть)

    def clear(self) -> None:
        self.clips.clear()
        self.holds.clear()

    def play(self, uid: int, clips: list[Clip]) -> None:
        """Новая последовательность заменяет то, что ещё не началось к её началу."""
        if not clips:
            return
        start = clips[0].start
        kept = [c for c in self.clips.get(uid, []) if c.start < start]
        self.clips[uid] = kept + sorted(clips, key=lambda c: c.start)
        self.holds.pop(uid, None)

    def hold(self, uid: int, clip: Clip) -> None:
        self.play(uid, [clip])
        self.holds[uid] = clip

    def pose(self, uid: int, now: int) -> Optional[tuple[Part, int]]:
        """(часть, номер кадра) или None — показывать стойку."""
        clips = self.clips.get(uid)
        hold = self.holds.get(uid)
        if hold is not None and now >= hold.start:
            return hold.part, hold.frame(now)
        if not clips:
            return None
        current = None
        for clip in clips:
            if clip.start <= now:
                current = clip
        if current is None:
            return None
        end = current.end
        if end is not None and now >= end:
            return None
        return current.part, current.frame(now)

    def busy_until(self, uid: int) -> int:
        ends = [c.end for c in self.clips.get(uid, []) if c.end is not None]
        return max(ends) if ends else 0
