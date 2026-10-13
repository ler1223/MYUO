"""Проверка набора спрайтов (без pygame: только наличие и формат файлов)."""
import json
import struct
import unittest
from pathlib import Path

from tests.helpers import DB

SPRITE_DIR = Path(__file__).resolve().parent.parent / "assets" / "sprites"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
META = json.loads((SPRITE_DIR / "sprites.json").read_text(encoding="utf-8"))


def png_size(path: Path) -> tuple[int, int]:
    """Размер PNG из заголовка IHDR."""
    data = path.read_bytes()[:24]
    assert data[:8] == PNG_SIGNATURE, f"{path.name} is not a PNG file"
    return struct.unpack(">II", data[16:24])


class SpriteAssetTests(unittest.TestCase):
    def test_meta(self):
        self.assertEqual(META["animations"], ["idle", "melee", "ranged", "cast"])
        self.assertGreater(META["frame_ms"], 0)
        self.assertLess(META["anchor_x"], META["frame_width"])

    def test_every_class_has_every_animation_and_there_is_a_fallback(self):
        for name in (*DB.units, "default"):
            for animation in META["animations"]:
                self.assertTrue((SPRITE_DIR / name / f"{animation}.png").exists(), (name, animation))

    def test_strips_are_made_of_whole_frames(self):
        strips = list(SPRITE_DIR.glob("*/*.png"))
        self.assertTrue(strips)
        for path in strips:
            meta = dict(META)
            own = path.parent / "sprite.json"   # у класса может быть свой размер кадра
            if own.exists():
                meta.update(json.loads(own.read_text(encoding="utf-8")))
            width, height = png_size(path)
            self.assertEqual(height, meta["frame_height"], path)
            self.assertEqual(width % meta["frame_width"], 0, path)
            frames = width // meta["frame_width"]
            self.assertGreaterEqual(frames, 2 if path.stem == "idle" else 3, path)  # анимация, а не один кадр


if __name__ == "__main__":
    unittest.main()
