"""Генерация картинок интерфейса через OpenAI Images API (gpt-image) по промптам из docs/ui_prompts.md.

Промпт собирается из документа: блоки STYLE и SHEET плюс список ячеек батча. Для фонов (батч 8)
берётся шаблон батча и мотив из его таблицы. Можно передать и свой промпт.

Запуск:
  python tools/gen_ui_image.py --list                         что можно сгенерировать
  python tools/gen_ui_image.py --batch 1 --dry-run            показать промпт, ничего не отправлять
  python tools/gen_ui_image.py --batch 1 --ref ref/uo1.png    лист батча 1 по образцу скриншота
  python tools/gen_ui_image.py --background bg/prepare        фон экрана подготовки
  python tools/gen_ui_image.py --prompt "..." --out assets/ui/sheets/test.png

Ключ — переменная окружения OPENAI_API_KEY (в файлы и вывод не попадает). Запрос платный:
промпт и картинки-образцы (--ref) уходят в OpenAI. Без --ref вызывается генерация
(/v1/images/generations), с --ref — правка по образцам (/v1/images/edits).
Готовая картинка пишется в assets/ui/sheets/<имя из заголовка батча> (фоны — в assets/ui/<ключ>.png),
рядом — .txt с промптом. Существующий файл без --force не перезаписывается.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "docs" / "ui_prompts.md"
SHEETS = ROOT / "assets" / "ui" / "sheets"
UI_DIR = ROOT / "assets" / "ui"
API = "https://api.openai.com/v1/images"
DEFAULT_MODEL = "gpt-image-1"
SIZES = ("1024x1024", "1536x1024", "1024x1536", "auto")
QUALITIES = ("low", "medium", "high", "auto")
REF_LINE = "Match the art direction of the attached screenshots, but do not copy any text, logo or exact artwork."
RETRIES = 3
TIMEOUT = 600


# --- промпты из документа ------------------------------------------------------------

def code_blocks(text: str) -> list[tuple[int, str]]:
    """Блоки ``` ... ```: (позиция начала, содержимое)."""
    return [(m.start(), m.group(1).strip()) for m in re.finditer(r"```\n(.*?)```", text, re.S)]


def sections(text: str) -> list[tuple[int, str]]:
    """Заголовки второго уровня: (позиция, текст)."""
    return [(m.start(), m.group(1).strip()) for m in re.finditer(r"^## (.+)$", text, re.M)]


def block_after(text: str, heading_start: str) -> tuple[str, str]:
    """(заголовок, первый блок кода после него) для раздела, чей заголовок начинается с heading_start."""
    heads = sections(text)
    for i, (pos, title) in enumerate(heads):
        if title.startswith(heading_start):
            end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
            for start, block in code_blocks(text):
                if pos < start < end:
                    return title, block
    raise KeyError(f"no prompt block under '## {heading_start}' in {PROMPTS.name}")


def batch_prompt(text: str, number: int) -> tuple[str, str]:
    """(имя файла листа, полный промпт) батча-листа."""
    title, block = block_after(text, f"Батч {number} ")
    found = re.search(r"`([^`]+\.png)`", title)
    if not found:
        raise KeyError(f"batch {number} is not a sheet (no file name in its title)")
    return found.group(1), assemble(text, block)


def assemble(text: str, block: str) -> str:
    """Подставляет общие блоки STYLE и SHEET вместо <STYLE> и <SHEET>."""
    _, style = block_after(text, "STYLE")
    _, sheet = block_after(text, "SHEET")
    return block.replace("<STYLE>", style).replace("<SHEET>", sheet).strip()


def backgrounds(text: str) -> dict[str, str]:
    """Фоны батча 8: ключ (bg/prepare) -> мотив из таблицы."""
    heads = sections(text)
    start = next(pos for pos, title in heads if title.startswith("Батч 8"))
    end = next((pos for pos, _ in heads if pos > start), len(text))
    rows = re.findall(r"^\| `([^`]+)\.png` \| `([^`]+)`", text[start:end], re.M)
    return dict(rows)


def background_prompt(text: str, key: str) -> str:
    motifs = backgrounds(text)
    if key not in motifs:
        raise KeyError(f"unknown background {key!r}; known: {', '.join(motifs)}")
    _, block = block_after(text, "Батч 8")
    return assemble(text, block).replace("<MOTIF>", motifs[key])


def list_targets(text: str) -> list[str]:
    lines = []
    for _, title in sections(text):
        found = re.match(r"Батч (\d+) .*`([^`]+\.png)`", title)
        if found:
            lines.append(f"--batch {found.group(1)}  -> {found.group(2)}  ({title})")
    lines += [f"--background {key}" for key in backgrounds(text)]
    return lines


# --- запрос -------------------------------------------------------------------------

def multipart(fields: dict[str, str], files: list[tuple[str, Path]]) -> tuple[bytes, str]:
    """Тело multipart/form-data: текстовые поля и файлы (name, путь)."""
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for name, path in files:
        kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        head = (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'
                f"Content-Type: {kind}\r\n\r\n").encode()
        parts.append(head + path.read_bytes() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def request(prompt: str, key: str, model: str, size: str, quality: str, transparent: bool,
            refs: list[Path]) -> bytes:
    """Одна картинка PNG. С образцами — /edits (несколько image[]), иначе /generations."""
    fields = {"model": model, "prompt": prompt, "size": size, "quality": quality, "n": "1"}
    if transparent:
        fields["background"] = "transparent"
    if refs:
        body, content_type = multipart(fields, [("image[]", path) for path in refs])
        url = f"{API}/edits"
    else:
        payload = dict(fields, n=1)
        body, content_type, url = json.dumps(payload).encode(), "application/json", f"{API}/generations"
    for attempt in range(1, RETRIES + 1):
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": content_type})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                data = json.loads(response.read())
            return base64.b64decode(data["data"][0]["b64_json"])
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")[:500]
            if error.code in (429, 500, 502, 503) and attempt < RETRIES:
                time.sleep(10 * attempt)
                continue
            raise SystemExit(f"OpenAI error {error.code}: {detail}")
        except urllib.error.URLError as error:
            if attempt < RETRIES:
                time.sleep(5 * attempt)
                continue
            raise SystemExit(f"network error: {error.reason}")
    raise SystemExit("no image returned")


# --- запуск -------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument("--batch", type=int, help="номер батча-листа из docs/ui_prompts.md")
    what.add_argument("--background", help="фон батча 8, например bg/prepare")
    what.add_argument("--prompt", help="свой промпт целиком")
    what.add_argument("--list", action="store_true", help="показать, что можно сгенерировать")
    parser.add_argument("--ref", action="append", default=[], type=Path,
                        help="картинка-образец стиля (скриншот UO); можно несколько")
    parser.add_argument("--out", type=Path, help="куда сохранить (по умолчанию — по батчу или ключу фона)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--size", default="1536x1024", choices=SIZES)
    parser.add_argument("--quality", default="high", choices=QUALITIES)
    parser.add_argument("--extra", default="", help="дописать к промпту (например, правку одной ячейки)")
    parser.add_argument("--force", action="store_true", help="перезаписать существующий файл")
    parser.add_argument("--dry-run", action="store_true", help="только показать промпт")
    args = parser.parse_args(argv)

    text = PROMPTS.read_text(encoding="utf-8")
    if args.list:
        print("\n".join(list_targets(text)))
        return 0
    transparent = True
    if args.batch is not None:
        name, prompt = batch_prompt(text, args.batch)
        out = args.out or SHEETS / name
    elif args.background:
        prompt, transparent = background_prompt(text, args.background), False
        out = args.out or UI_DIR / f"{args.background}.png"
    else:
        prompt = args.prompt
        if args.out is None:
            parser.error("--prompt needs --out")
        out = args.out
    if args.extra:
        prompt += "\n" + args.extra
    if args.ref:
        missing = [str(p) for p in args.ref if not p.is_file()]
        if missing:
            parser.error(f"no such reference image: {', '.join(missing)}")
        prompt = REF_LINE + "\n" + prompt

    print(f"-> {out}  ({args.model}, {args.size}, quality {args.quality}"
          f"{', transparent' if transparent else ''}{f', {len(args.ref)} reference(s)' if args.ref else ''})")
    if args.dry_run:
        print(prompt)
        return 0
    if out.exists() and not args.force:
        print(f"{out} exists; use --force to overwrite", file=sys.stderr)
        return 1
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("set OPENAI_API_KEY first", file=sys.stderr)
        return 2
    image = request(prompt, key, args.model, args.size, args.quality, transparent, args.ref)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(image)
    out.with_suffix(".txt").write_text(prompt + "\n", encoding="utf-8")
    print(f"saved {out} ({len(image) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
