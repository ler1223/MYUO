"""Иконки предметов из Unicorn Overlord (GUI/ItemIcon.mbs: 291 иконка-анимация).

Таблицы «предмет -> иконка» в архиве игры нет (она в исполняемом файле), поэтому иконка выбирается
правилами, а data/uo_ui.json ("item_icons") их уточняет:
- "items": {id предмета: иконка} — вручную, важнее всего;
- "keywords": [[регулярное выражение по английскому названию, иконка], ...] — первое совпадение
  (аксессуары: Bangle -> BANGLE_*, Hood -> HOOD_*, Ring -> RING_* ...);
- оружие и щиты — по виду (меч SWORD_, копьё SPEAR_, ...): обычные (без навыков и пассивок) берут
  иконки N00.. по тиру внутри вида, особые — S00.. по тиру.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

import numpy as np

from .library import source
from .ui import CONFIG

FILE = "ItemIcon"
KINDS = {"light_sword": "SWORD", "lance": "SPEAR", "bow": "BOW", "heavy_weapon": "AXE", "staff": "STAFF",
         "light_shield": "SHIELD", "greatshield": "L_SHIELD"}
ACCESSORY = "TALISMAN"                   # аксессуар без подходящего слова
ICON_SCALE = 1.5                         # родной размер — около 72 пикселей; крупнее, чтобы не мылить при увеличении


class ItemIcons:
    """Иконка UO для предмета справочника: имя анимации и картинка RGBA (numpy) родного размера."""

    def __init__(self, items: dict[str, Any]):
        self.items = items
        self._names: Optional[list[str]] = None
        self._rules: Optional[tuple[dict, list]] = None
        self._chosen: dict[str, Optional[str]] = {}
        self._images: dict[str, Optional[np.ndarray]] = {}

    @property
    def names(self) -> list[str]:
        if self._names is None:
            model = source().model("GUI", FILE)
            self._names = list(model.puppet.anims) if model is not None else []
        return self._names

    def rules(self) -> tuple[dict, list]:
        if self._rules is None:
            config = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.is_file() else {}
            spec = config.get("item_icons", {})
            self._rules = (spec.get("items", {}),
                           [(re.compile(rx, re.I), icon) for rx, icon in spec.get("keywords", [])])
        return self._rules

    def icon(self, item_id: str) -> Optional[str]:
        """Имя анимации-иконки для предмета; None — нет игры или предмета."""
        if item_id not in self._chosen:
            self._chosen[item_id] = self._choose(item_id)
        return self._chosen[item_id]

    def _choose(self, item_id: str) -> Optional[str]:
        item = self.items.get(item_id)
        names = set(self.names)
        if item is None or not names:
            return None
        manual, keywords = self.rules()
        if manual.get(item_id) in names:
            return manual[item_id]
        kind = KINDS.get(item.slot)
        if kind is None:
            for rx, icon in keywords:
                if icon in names and rx.search(item.name):
                    return icon
            return ACCESSORY if ACCESSORY in names else None
        special = bool(item.skills or item.passives)
        group = "S" if special else "N"
        icons = sorted(n for n in names if re.fullmatch(rf"{kind}_{group}\d\d_A", n))
        if not icons:
            return None
        same = sorted((i for i in self.items.values() if i.slot == item.slot and bool(i.skills or i.passives) == special),
                      key=lambda i: (i.tier, i.price, i.id))
        place = next(k for k, i in enumerate(same) if i.id == item_id)
        return icons[min(len(icons) - 1, place * len(icons) // max(1, len(same)))]

    def image(self, item_id: str) -> Optional[np.ndarray]:
        """Иконка предмета RGBA (обрезана по видимому)."""
        name = self.icon(item_id)
        if name is None:
            return None
        if name not in self._images:
            from .ui import render
            self._images[name] = render(FILE, name, 0, ICON_SCALE)
        return self._images[name]
