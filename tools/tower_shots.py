"""Снимки экранов окна башни без дисплея — проверить вид интерфейса глазами.

    python tools/tower_shots.py [папка] [--lang ru]

Забег новый, во временном сохранении (настоящее saves/tower.json не трогается); справочник — data/.
Снимки: набор, подготовка (главный, отряд, юниты, редактор бойца по вкладкам, инвентарь),
бой в середине, награда, магазин, конец забега. Мышь можно навести: --mouse x,y (на все снимки); --data папка — другой справочник.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

import pygame_tower as tw  # noqa: E402
import pygame_tower_prepare as pp  # noqa: E402
from game.tower import DRAFT, OVER, SHOP  # noqa: E402

SEED = 7


class Shooter:
    def __init__(self, folder: Path, lang: str, mouse: tuple[int, int] | None, data: str | None = None):
        pygame.init()
        pygame.display.set_mode((64, 64))
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp())
        self.app = tw.TowerApp(self.tmp / "tower.json", data, lang=lang, seed=SEED)
        self.ui = tw.make_ui(pygame.Surface(tw.SIZE))
        self.mouse = mouse

    def frame(self, events=(), mouse=None) -> None:
        self.ui.transform = lambda _pos, m=mouse or self.mouse or (-100, -100): m
        self.ui.begin(list(events))
        tw.draw_frame(self.ui, self.app)

    def click(self, pos) -> None:
        self.frame([pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)])
        self.frame([pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)])

    def shot(self, name: str, mouse=None) -> None:
        self.frame(mouse=mouse)
        self.frame(mouse=mouse)            # второй кадр: наведение и подсказки по прошлому кадру
        path = self.folder / f"{name}.png"
        pygame.image.save(self.ui.screen, str(path))
        print(path)

    def run(self) -> None:
        app = self.app
        self.shot("01_draft")
        while app.run.phase == DRAFT:
            offers = app.run.offers                    # с путями повышения — чтобы снять и их экран
            app.act(app.run.pick, app.db, next((c for c in offers if app.db.units[c].promotions), offers[0]))
        app.view = pp.MAIN
        self.shot("02_prepare")
        app.view = pp.SQUAD
        self.shot("03_squad")
        app.view = pp.UNITS
        self.shot("04_units")
        uid = app.run.fielded[0].uid
        for tab in (pp.STATUS, pp.EQUIPMENT, pp.TACTICS):
            pp.open_unit(app, uid, pp.MAIN, tab)
            self.shot(f"05_unit_{tab}")
        app.tactic_pick = (0, 0)                       # открытый список условий тактики
        self.shot("05_unit_tactics_pick")
        app.tactic_pick = None
        unit = next((u for u in app.run.army.units.values() if u.definition.promotions), None)
        if unit is not None:                           # пути повышения (уровень — чтобы первый был открыт)
            level = unit.state.level
            unit.state.level = max(level, min(p.level for p in unit.definition.promotions))
            pp.open_unit(app, unit.uid, pp.MAIN)
            app.view = pp.PROMOTE
            self.shot("05_unit_promote")
            unit.state.level = level
        app.view = pp.INVENTORY
        self.shot("06_inventory")
        app.view = pp.MAIN
        app.start_battle()
        for _ in range(240):                 # несколько ходов боя с эффектами
            app.tick(50)
            self.frame()
        self.shot("07_battle")
        app.skip()
        app.tick(16)
        self.shot("08_battle_end")
        app.finish_battle()
        self.shot("09_reward")
        app.run.phase = SHOP
        app.run._stock_shop(app.db)
        self.shot("10_shop")
        app.run.phase = OVER
        self.shot("11_over")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", nargs="?", default="shots")
    parser.add_argument("--lang", default="ru")
    parser.add_argument("--mouse", default=None, help="x,y — курсор на всех снимках")
    parser.add_argument("--data", default=None, help="папка справочника вместо data/")
    args = parser.parse_args()
    mouse = tuple(int(v) for v in args.mouse.split(",")) if args.mouse else None
    Shooter(Path(args.folder), args.lang, mouse, args.data).run()


if __name__ == "__main__":
    main()
