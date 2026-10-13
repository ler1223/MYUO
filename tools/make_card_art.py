"""Арт карты из листа частей: персонаж в стойке, собранный крупно по rig.json.

Запуск: python tools/make_card_art.py knight
Пишет assets/cards/<класс>.png. Для классов с готовым артом этот шаг не нужен:
достаточно положить картинку в assets/cards/<класс>.png.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cutout_sprites import SRC, Rig, pygame  # noqa: E402

CARDS = Path(__file__).resolve().parent.parent / "assets" / "cards"
ART_SCALE = 0.32        # крупнее, чем для кадров анимации
FRAME = (420, 560)
PORTRAIT_HEIGHT = 0.72   # какая часть фигуры (сверху) попадает на карту


def build(class_id: str) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    rig = Rig(SRC / class_id)
    rig.spec = dict(rig.spec, frame=list(FRAME), root=[FRAME[0] * 0.45, FRAME[1] * 0.42])
    rig.scale = ART_SCALE * 3      # Rig рисует с тройным запасом и уменьшает
    rig._cache.clear()
    image = rig.render(rig.spec["animations"]["idle"][0])
    # Портрет: от макушки до колен, по центру фигуры (по тазу), а не по мечу.
    body = image.get_bounding_rect()
    height = int(body.height * PORTRAIT_HEIGHT)
    width = int(height * 0.72)
    crop = pygame.Rect(int(rig.spec["root"][0] - width / 2), body.top - 6, width, height + 6)
    image = image.subsurface(crop.clip(image.get_rect())).copy()
    CARDS.mkdir(parents=True, exist_ok=True)
    pygame.image.save(image, str(CARDS / f"{class_id}.png"))
    print(f"{class_id}: card art {image.get_size()} -> {CARDS / (class_id + '.png')}")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "knight")
