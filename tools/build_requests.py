"""Готовые тексты запросов для генерации картинок -> docs/requests/ (сами запросы не делаются).

    python tools/build_requests.py            # все запросы из docs/uo_art_prompts.md
    python tools/build_requests.py --old      # плюс старые батчи 1-10 из docs/ui_prompts.md

Каждый файл — полный текст одного запроса, копируется в ChatGPT целиком:
  batch_NN.txt   — лист 5x2: строка про образец + STYLE + SHEET + ячейки батча;
  lineup_NN.txt  — линейка спрайтов классов: общий промпт линейки (первого или следующих листов)
                   со строками персонажей листа.
docs/requests/README.md — оглавление: что приложить, куда сохранить картинку, чем нарезать.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.gen_ui_image import REF_LINE, assemble, block_after, sections  # noqa: E402

UI_PROMPTS = ROOT / "docs" / "ui_prompts.md"
UO_PROMPTS = ROOT / "docs" / "uo_art_prompts.md"
OUT = ROOT / "docs" / "requests"
REFS = "1-2 скриншота меню UO из assets/ref/"
NAME_LINE = ("FILE NAME: give the finished PNG for download exactly this file name: {name} "
             "(this is only the file name - never draw it or any other text in the image).")


def name_line(path: str) -> str:
    return NAME_LINE.format(name=Path(path).name)


def batches(text: str) -> list[tuple[int, str, str]]:
    """(номер, имя листа, заголовок) всех батчей-листов документа."""
    found = []
    for _, title in sections(text):
        match = re.match(r"Батч (\d+) .*`([^`]+\.png)`", title)
        if match:
            found.append((int(match.group(1)), match.group(2), title))
    return found


def batch_request(source: str, ui_text: str, number: int) -> str:
    """Полный запрос батча: STYLE и SHEET берутся из docs/ui_prompts.md."""
    _, block = block_after(source, f"Батч {number} ")
    sheet = next(s for n, s, _t in batches(source) if n == number)
    return f"{REF_LINE}\n\n{assemble(ui_text, block)}\n\n{name_line(sheet)}\n"


def lineup_template(text: str, number: int) -> str:
    """Общий промпт линейки из docs/uo_art_prompts.md: у первого листа свой (он задаёт эталон роста)."""
    return block_after(text, "Линейка: первый лист" if number == 1 else "Линейка: остальные листы")[1]


def lineup_attach(number: int) -> str:
    return ("по желанию 1-2 скриншота боя UO (только стиль)" if number == 1
            else "готовый assets/sprites_src/lineup/uo_01.png — эталон роста и стиля")


def lineups(text: str) -> list[tuple[int, str, str, str]]:
    """(номер, путь листа, команда нарезки, строки персонажей) из раздела 1 docs/uo_art_prompts.md."""
    found = []
    for match in re.finditer(r"\*\*Лист (\d+)\*\* \(`([^`]+)`\): `([^`]+)`\s*```\n(.*?)```", text, re.S):
        found.append((int(match.group(1)), match.group(2), match.group(3), match.group(4).strip()))
    return found


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ui_text = UI_PROMPTS.read_text(encoding="utf-8")
    uo_text = UO_PROMPTS.read_text(encoding="utf-8")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    rows = []

    for number, path, _command, people in lineups(uo_text):
        name = f"lineup_{number:02d}.txt"
        text = lineup_template(uo_text, number).replace("<персонажи>", people).strip()
        (OUT / name).write_text(f"{text}\n\n{name_line(path)}\n", encoding="utf-8")
        rows.append((name, f"Спрайты классов, лист {number}", lineup_attach(number), path,
                     f"python tools/take_image.py lineup {number} --cut"))

    sources = [(uo_text, batches(uo_text))]
    if "--old" in sys.argv:
        sources.insert(0, (ui_text, [b for b in batches(ui_text)]))
    for source, found in sources:
        for number, sheet, title in found:
            name = f"batch_{number:02d}.txt"
            (OUT / name).write_text(batch_request(source, ui_text, number), encoding="utf-8")
            what = re.sub(r"\s*\(`[^`]+`\)$", "", title.split("—", 1)[-1]).strip()
            rows.append((name, f"Батч {number}: {what}", REFS, f"assets/ui/sheets/{sheet}",
                         f"python tools/take_image.py {number} --cut"))

    index = ["# Готовые запросы для генерации картинок", "",
             "Собрано `python tools/build_requests.py` из `docs/uo_art_prompts.md` и `docs/ui_prompts.md` — "
             "перегенерируйте после их изменения. Файл — полный текст одного запроса: "
             "откройте, скопируйте целиком в ChatGPT, приложите образец, сохраните картинку (PNG с прозрачным "
             "фоном, 1536x1024) и выполните команду из последней колонки: она заберёт самую свежую картинку из "
             "«Загрузок» (или файл с нужным именем — его просит последняя строка запроса), положит по пути из "
             "таблицы и нарежет. Без `--cut` — только переложит и покажет команду нарезки.", "",
             f"Всего запросов: {len(rows)}. Линейки — по порядку: `lineup_01.txt` задаёт рост и стиль, его картинка прикладывается ко всем следующим.", "",
             "| Файл | Что | Приложить | Куда ляжет | Забрать и нарезать |", "| --- | --- | --- | --- | --- |"]
    index += [f"| `{n}` | {w} | {a} | `{s}` | `{c}` |" for n, w, a, s, c in rows]
    (OUT / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"{len(rows)} requests -> {OUT}")


if __name__ == "__main__":
    main()
