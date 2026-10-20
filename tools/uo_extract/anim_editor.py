"""Редактор выбора анимаций юнитов из Unicorn Overlord (локальная страница в браузере).

    python tools/uo_extract/anim_editor.py --src <папка распакованного Unicorn.CPK> [--port 8766]

Вкладки: «Персонажи», «Эффекты навыков», «Фоны».

Для каждого класса проекта: файл персонажа (Chara/*.mbs и др.), вариант внешности и какие
анимации файла идут в состояния (стойка, атака, каст, попадание, уклонение, защита, смерть,
победа) — цепочкой частей, у части можно обрезать тики. Анимации можно пометить битыми: правила
их не выберут. Выбор сохраняется в data/uo_anim.json; игра рисует кукол сама (engine.uo.library)
и перечитывает файл, когда он меняется, — пересобирать ничего не нужно.

Куклы рисуются в браузере тем же способом, что и при сборке (tools/uo_extract/editor/*.js);
.mbs берутся из папки игры, текстуры .ftx переводятся в PNG при первом запросе и кэшируются
в assets/uo_anim/_cache (в git не хранится).
"""
from __future__ import annotations

import argparse
import http.server
import json
import re
import struct
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from engine.uo import ftx  # noqa: E402
from engine.uo.library import remember_game_folder  # noqa: E402

PAGE_DIR = Path(__file__).resolve().parent / "editor"
CONFIG = ROOT / "data" / "uo_anim.json"
UNITS = ROOT / "data" / "units.json"
CACHE = ROOT / "assets" / "uo_anim" / "_cache"
FOLDERS = ("Chara", "CharaNpc", "CharaOp", "CharaFace", "Effect", "BattleBG")
SCENES = ROOT / "assets" / "scenes"
SAFE = re.compile(r"^[A-Za-z0-9_]+$")


class Handler(http.server.SimpleHTTPRequestHandler):
    src: Path

    def log_message(self, *args):
        pass

    def _send(self, body: bytes, kind: str = "application/json", code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, code: int = 200) -> None:
        self._send(json.dumps(data, ensure_ascii=False).encode("utf-8"), code=code)

    def do_GET(self):
        url = urlparse(self.path)
        path, query = unquote(url.path), parse_qs(url.query)
        if path == "/api/config":
            return self._send(CONFIG.read_bytes())
        if path == "/api/units":
            data = json.loads(UNITS.read_text(encoding="utf-8"))
            units = data.get("units", data)
            ids = lambda lst: [x if isinstance(x, str) else x["id"] for x in lst]
            return self._json({uid: {"name": u.get("name", uid), "tags": u.get("tags", []), "skills": ids(u.get("skills", [])),
                                     "passives": ids(u.get("passives", []))} for uid, u in units.items()})
        if path == "/api/files":
            return self._json({f: sorted(p.stem for p in (self.src / f).glob("*.mbs")) for f in FOLDERS})
        if path == "/api/scenes":
            return self._json({p.stem: json.loads(p.read_text(encoding="utf-8")).get("name", p.stem)
                               for p in sorted(SCENES.glob("*.json"))})
        if path == "/api/skills":
            skills = json.loads((ROOT / "data" / "skills.json").read_text(encoding="utf-8"))
            skills = skills.get("skills", skills)
            return self._json({sid: {"name": s.get("name", sid), "tags": s.get("tags", [])} for sid, s in skills.items()})
        if path == "/api/skins":
            folder, file = query.get("folder", [""])[0], query.get("file", [""])[0]
            if folder not in FOLDERS or not SAFE.match(file):
                return self._json({"error": "bad request"}, 400)
            names = sorted(p.stem for p in (self.src / folder).glob("*.ftx"))
            own = [n for n in names if n == file or re.fullmatch(re.escape(file) + r"\d\d", n)]
            pages = {n: struct.unpack_from("<I", (self.src / folder / f"{n}.ftx").read_bytes()[:16], 12)[0]
                     for n in own or names[:1]}
            return self._json({"skins": own or names[:1], "all": names, "pages": pages})
        m = re.fullmatch(r"/game/(\w+)/(\w+)\.mbs", path)
        if m and m.group(1) in FOLDERS:
            file = self.src / m.group(1) / f"{m.group(2)}.mbs"
            return self._send(file.read_bytes(), "application/octet-stream") if file.is_file() else self._send(b"", code=404)
        m = re.fullmatch(r"/tex/(\w+)/(\w+)\.(\d+)\.png", path)
        if m and m.group(1) in FOLDERS:
            png = self._texture(m.group(1), m.group(2), int(m.group(3)))
            return self._send(png.read_bytes(), "image/png") if png else self._send(b"", code=404)
        if path == "/":
            path = "/index.html"
        file = (PAGE_DIR / path.lstrip("/")).resolve()
        if PAGE_DIR in file.parents and file.is_file():
            kind = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                    ".css": "text/css; charset=utf-8"}.get(file.suffix, "application/octet-stream")
            return self._send(file.read_bytes(), kind)
        self._send(b"not found", "text/plain", 404)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.path == "/api/config":
            try:
                data = json.loads(body)
                assert isinstance(data.get("classes"), dict) and isinstance(data.get("states"), dict)
            except (ValueError, AssertionError):
                return self._json({"error": "неверный конфиг"}, 400)
            CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return self._json({"ok": True})
        self._send(b"not found", "text/plain", 404)

    def _texture(self, folder: str, name: str, page: int) -> Path | None:
        out = CACHE / folder / f"{name}.{page}.png"
        if not out.is_file():
            src = self.src / folder / f"{name}.ftx"
            if not src.is_file():
                return None
            data = src.read_bytes()
            _, texs = ftx.parse(data)
            out.parent.mkdir(parents=True, exist_ok=True)
            for i, tex in enumerate(texs):
                ftx.decode(data, tex).save(CACHE / folder / f"{name}.{i}.png", compress_level=1)
        return out if out.is_file() else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="папка распакованного Unicorn.CPK (с подпапкой Chara)")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    src = Path(args.src).resolve()
    if not (src / "Chara").is_dir():
        sys.exit(f"нет папки {src / 'Chara'}")
    remember_game_folder(src)                       # игра будет брать куклы из этой же папки
    handler = type("EditorHandler", (Handler,), {"src": src})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    url = f"http://localhost:{args.port}/"
    print(f"Редактор анимаций: {url}  (Ctrl+C — выход)")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
