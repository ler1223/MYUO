"""Распаковать архив CRIWARE CPK (Unicorn.CPK из romfs игры) в папку.

    python tools/uo_extract/unpack.py <Unicorn.CPK> <папка> ["Chara/*" "Effect/*" …]

Маски — fnmatch по пути внутри архива; без масок распаковывается всё (около 5 ГБ, ~20 минут).
Для анимаций юнитов достаточно "Chara/*" (и "Effect/*" для эффектов). Уже распакованные файлы
нужного размера пропускаются.
"""
from __future__ import annotations

import fnmatch
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from tools.uo_extract.cpk import CPK  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cpk, out, patterns = CPK(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
    started, total = time.time(), 0
    for entry in cpk.files:
        if patterns and not any(fnmatch.fnmatch(entry["path"], p) for p in patterns):
            continue
        dst = out / entry["path"]
        if dst.is_file() and dst.stat().st_size == entry["extract_size"]:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = cpk.read(entry)
        dst.write_bytes(data)
        total += len(data)
        print(f"{entry['path']}  {len(data)}  {time.time() - started:.0f} с", flush=True)
    print(f"готово: {total / 1e6:.0f} МБ за {time.time() - started:.0f} с")


if __name__ == "__main__":
    main()
