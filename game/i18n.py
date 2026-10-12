"""Выбор языка. Ключом служит английский текст, поэтому английскому файл не нужен.

Новый язык = файл data/lang/<код>.json вида {"английский текст": "перевод"}.
Непереведённые строки остаются английскими.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Optional, Union

DEFAULT_LANG = "en"
LANG_DIR = Path(__file__).resolve().parent.parent / "data" / "lang"


class Translator:
    def __init__(self, lang: str = DEFAULT_LANG, texts: Optional[Mapping[str, str]] = None):
        self.lang = lang
        self.texts = dict(texts or {})

    @classmethod
    def load(cls, lang: str, directory: Union[str, Path] = LANG_DIR) -> "Translator":
        if lang == DEFAULT_LANG:
            return cls()
        path = Path(directory) / f"{lang}.json"
        if not path.exists():
            raise ValueError(f"unknown language {lang!r}")
        return cls(lang, json.loads(path.read_text(encoding="utf-8")))

    def __call__(self, text: str, **params: Any) -> str:
        """Перевод строки; params подставляются в {плейсхолдеры}."""
        template = self.texts.get(text, text)
        return template.format(**params) if params else template


def available_languages(directory: Union[str, Path] = LANG_DIR) -> list[str]:
    return [DEFAULT_LANG] + sorted(p.stem for p in Path(directory).glob("*.json"))
