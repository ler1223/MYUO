"""Забрать скачанную из ChatGPT картинку под правильным именем и (по желанию) сразу нарезать.

    python tools/take_image.py 13              # батч 13 -> assets/ui/sheets/b13_skills.png
    python tools/take_image.py lineup 2        # линейка 2 -> assets/sprites_src/lineup/uo_02.png
    python tools/take_image.py 13 --cut        # и сразу нарезать
    python tools/take_image.py 13 --from D:/pics

Где ищется: папка «Загрузки» (или --from). Сначала файл с нужным именем (ChatGPT иногда называет его
так, как просит последняя строка запроса), иначе самая свежая картинка (png, webp, jpg) — какой файл
взят, скрипт пишет. Картинка переводится в PNG с прозрачностью и переносится (из «Загрузок» убирается).
Готовый файл на месте без --force не перезаписывается.
"""
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.build_requests import UO_PROMPTS, batches, lineups  # noqa: E402

PICTURES = (".png", ".webp", ".jpg", ".jpeg")


def target(kind: str, number: int) -> tuple[Path, list[str]]:
    """(куда положить, команда нарезки) для батча или линейки."""
    text = UO_PROMPTS.read_text(encoding="utf-8")
    if kind == "lineup":
        for n, path, command, _people in lineups(text):
            if n == number:
                return ROOT / path, shlex.split(command)
        raise SystemExit(f"no lineup {number} in {UO_PROMPTS.name}")
    for n, sheet, _title in batches(text):
        if n == number:
            return ROOT / "assets" / "ui" / "sheets" / sheet, ["python", "tools/cut_ui_sheet.py", str(number)]
    old = (ROOT / "docs" / "ui_prompts.md").read_text(encoding="utf-8")
    for n, sheet, _title in batches(old):
        if n == number:
            return ROOT / "assets" / "ui" / "sheets" / sheet, ["python", "tools/cut_ui_sheet.py", str(number)]
    raise SystemExit(f"no batch {number}")


def find(folder: Path, name: str) -> Path:
    exact = folder / name
    if exact.is_file():
        return exact
    pictures = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in PICTURES]
    if not pictures:
        raise SystemExit(f"no pictures in {folder}")
    return max(pictures, key=lambda p: p.stat().st_mtime)


def save_png(source: Path, destination: Path) -> None:
    from PIL import Image
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image.convert("RGBA").save(destination)


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("what", nargs="+", help="номер батча или «lineup N»")
    parser.add_argument("--from", dest="folder", default=str(Path.home() / "Downloads"))
    parser.add_argument("--cut", action="store_true", help="сразу нарезать")
    parser.add_argument("--force", action="store_true", help="перезаписать готовый файл")
    args = parser.parse_args(argv)
    kind, number = ("lineup", int(args.what[1])) if args.what[0] == "lineup" else ("batch", int(args.what[0]))
    destination, command = target(kind, number)
    if destination.exists() and not args.force:
        print(f"{destination.relative_to(ROOT)} already exists (use --force)")
        return 1
    source = find(Path(args.folder), destination.name)
    save_png(source, destination)
    source.unlink()
    print(f"{source.name} -> {destination.relative_to(ROOT)}")
    if args.cut:
        if "--force" not in command and kind == "batch":
            command += ["--force", "--by-order"]          # генератор не всегда держит сетку 5x2
        command[0] = sys.executable if command[0] == "python" else command[0]
        return subprocess.call(command, cwd=ROOT)
    print("cut: " + " ".join(command))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
