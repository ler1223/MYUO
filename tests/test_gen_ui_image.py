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


class BuiltRequestTests(unittest.TestCase):
    def test_every_uo_request_is_complete_without_placeholders(self):
        from tools import build_requests as br
        ui_text = br.UI_PROMPTS.read_text(encoding="utf-8")
        uo_text = br.UO_PROMPTS.read_text(encoding="utf-8")
        found = br.batches(uo_text)
        self.assertTrue(found)
        for number, _sheet, _title in found:
            text = br.batch_request(uo_text, ui_text, number)
            self.assertTrue(text.startswith(br.REF_LINE))
            self.assertIn("STYLE:", text)
            self.assertIn("SHEET:", text)
            self.assertNotIn("<STYLE>", text)
            self.assertIn("Cell 1:", text)
        sheets = br.lineups(uo_text)
        self.assertEqual(sum(len(people.splitlines()) for *_x, people in sheets), 60)   # все классы UO
        for number in (1, 2):
            template = br.lineup_template(uo_text, number)
            self.assertIn("<персонажи>", template)
            self.assertIn(f"uo_{number:02d}_ref.png", template)            # внешность — с коллажа
            self.assertIn("Follow the reference completely", template)
            self.assertNotIn("<STYLE>", template)
            self.assertNotIn("menu interface", template)                  # не стиль меню
        self.assertNotIn("uo_01.png", br.lineup_template(uo_text, 1))     # первый лист ни на что не опирается
        self.assertIn("the Fighter from\nuo_01.png", br.lineup_template(uo_text, 2))
        number, _path, command, people = sheets[0]
        self.assertTrue(people.startswith("1. Fighter - picture 1."))     # эталон роста — первым
        self.assertIn("--reference fighter", command)
        self.assertTrue(all("_ref" in c for _n, _p, c, _x in sheets[1:]))
        for *_x, p in sheets:                                              # строка N = персонаж N коллажа
            for line in p.splitlines():
                self.assertIn(f"picture {line.split('.')[0]}", line)
        self.assertIn("uo_05_ref.png", br.lineup_template(uo_text, 5))     # свой коллаж у каждого листа
        from game.database import Database
        from tools import uo_class_refs
        self.assertLessEqual(set(Database.load().units), set(uo_class_refs.SOURCES))   # у каждого класса источник
        found = dict((n, s) for n, s, _t in br.batches(uo_text))
        self.assertEqual(set(found), {11, 12, 13})                        # иконки — по типам, а не поштучно


class TakeImageTests(unittest.TestCase):
    def test_downloaded_picture_goes_under_the_right_name(self):
        import os
        import tempfile
        import time
        from PIL import Image
        from tools import take_image as ti
        path, command = ti.target("batch", 11)
        self.assertEqual((path.name, command[-1]), ("b11_unit.png", "11"))
        path, command = ti.target("lineup", 2)
        self.assertEqual(path.name, "uo_02.png")
        self.assertIn("cut_lineup.py", " ".join(command))
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(folder / "ChatGPT Image 1.webp")
            time.sleep(0.01)
            Image.new("RGBA", (8, 8)).save(folder / "newest.png")
            os.utime(folder / "newest.png", None)
            self.assertEqual(ti.find(folder, "b11_unit.png").name, "newest.png")       # иначе самая свежая
            Image.new("RGBA", (8, 8)).save(folder / "b11_unit.png")
            os.utime(folder / "ChatGPT Image 1.webp", None)
            self.assertEqual(ti.find(folder, "b11_unit.png").name, "b11_unit.png")     # точное имя важнее
            ti.save_png(folder / "ChatGPT Image 1.webp", folder / "out" / "sheet.png")
            with Image.open(folder / "out" / "sheet.png") as image:
                self.assertEqual((image.format, image.mode), ("PNG", "RGBA"))


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
