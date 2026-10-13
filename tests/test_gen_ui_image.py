"""Генератор картинок интерфейса без сети: сборка промптов из docs/ui_prompts.md и запрос к подменённому API."""
import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import gen_ui_image as gen

TEXT = gen.PROMPTS.read_text(encoding="utf-8")


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class PromptTests(unittest.TestCase):
    def test_every_sheet_batch_gets_style_sheet_and_ten_cells(self):
        for number in range(1, 8):
            name, prompt = gen.batch_prompt(TEXT, number)
            self.assertTrue(name.startswith(f"b{number}_") and name.endswith(".png"))
            self.assertIn("Unicorn Overlord", prompt)                      # блок STYLE
            self.assertIn("5 columns and\n2 rows", prompt)                  # блок SHEET
            self.assertNotIn("<STYLE>", prompt)
            self.assertIn("Cell 10:", prompt)

    def test_backgrounds_take_their_motif(self):
        keys = gen.backgrounds(TEXT)
        self.assertIn("bg/prepare", keys)
        self.assertIn("bg/battle_hud", keys)
        prompt = gen.background_prompt(TEXT, "bg/shop")
        self.assertIn("merchant", prompt)
        self.assertNotIn("<MOTIF>", prompt)
        with self.assertRaises(KeyError):
            gen.background_prompt(TEXT, "bg/nowhere")


class RequestTests(unittest.TestCase):
    def fake(self, captured):
        png = b"\x89PNG fake"

        def urlopen(req, timeout=None):
            captured.append(req)
            return FakeResponse(json.dumps({"data": [{"b64_json": base64.b64encode(png).decode()}]}).encode())
        return urlopen

    def test_generation_without_references_and_saving(self):
        captured = []
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}), \
                mock.patch("urllib.request.urlopen", self.fake(captured)):
            out = Path(folder) / "sheet.png"
            self.assertEqual(gen.main(["--batch", "1", "--out", str(out), "--quality", "low"]), 0)
            self.assertEqual(out.read_bytes(), b"\x89PNG fake")
            self.assertIn("Cell 1:", out.with_suffix(".txt").read_text(encoding="utf-8"))   # промпт рядом
            self.assertEqual(gen.main(["--batch", "1", "--out", str(out)]), 1)             # не перезаписывает
        req = captured[0]
        self.assertTrue(req.full_url.endswith("/images/generations"))
        self.assertEqual(req.get_header("Authorization"), "Bearer test-key")
        body = json.loads(req.data)
        self.assertEqual((body["size"], body["quality"], body["background"]), ("1536x1024", "low", "transparent"))

    def test_references_go_to_the_edits_endpoint_as_multipart(self):
        captured = []
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}), \
                mock.patch("urllib.request.urlopen", self.fake(captured)):
            ref = Path(folder) / "uo.png"
            ref.write_bytes(b"reference")
            out = Path(folder) / "bg.png"
            gen.main(["--background", "bg/prepare", "--ref", str(ref), "--out", str(out)])
        req = captured[0]
        self.assertTrue(req.full_url.endswith("/images/edits"))
        self.assertIn("multipart/form-data", req.get_header("Content-type"))
        self.assertIn(b'name="image[]"; filename="uo.png"', req.data)
        self.assertIn(gen.REF_LINE.encode(), req.data)
        self.assertNotIn(b'name="background"', req.data)                   # фон не прозрачный

    def test_missing_key_does_not_send_anything(self):
        captured = []
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict("os.environ", {}, clear=True), \
                mock.patch("urllib.request.urlopen", self.fake(captured)):
            self.assertEqual(gen.main(["--batch", "2", "--out", str(Path(folder) / "x.png")]), 2)
        self.assertEqual(captured, [])


if __name__ == "__main__":
    unittest.main()
