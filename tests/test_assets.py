"""Проверка набора спрайтов (без pygame: только наличие и формат файлов)."""
import struct
import unittest
from pathlib import Path

from tests.helpers import DB

SPRITE_DIR = Path(__file__).resolve().parent.parent / "assets" / "sprites"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_size(path: Path) -> tuple[int, int]:
    """Размер PNG из заголовка IHDR."""
    data = path.read_bytes()[:24]
    assert data[:8] == PNG_SIGNATURE, f"{path.name} is not a PNG file"
    return struct.unpack(">II", data[16:24])


class SpriteAssetTests(unittest.TestCase):
    def test_every_class_has_a_sprite_and_there_is_a_fallback(self):
        for name in (*DB.units, "default"):
            self.assertTrue((SPRITE_DIR / f"{name}.png").exists(), name)

    def test_sprites_are_32x32_png(self):
        for path in SPRITE_DIR.glob("*.png"):
            self.assertEqual(png_size(path), (32, 32), path.name)


if __name__ == "__main__":
    unittest.main()
