# Каталог Unicorn Overlord: предметы и навыки

Собрано 2026-10-20. Это справочник для переноса в MYUO, а не готовый `data/*.json`.

## Файлы

- `items.json` — 777 записей: 638 с игровой записью, 139 только с вики
  (из них 0 единиц снаряжения, остальное расходники/материалы),
  124 только из игры (из них 55 реальных, остальные отладочные/пустые).
- `skills.json` — 437 навыков: 218 активных, 219 пассивных;
  437 уже есть в MYUO (435 с эффектами, 2 заглушки,
  0 без разобранных эффектов).
- `source/` — сырые выгрузки: `game_items.json`, `game_skills.json`, `wiki_items_parsed.json`,
  `miraheze_items.json`, `miraheze_skills.json`, `wiki/*.wikitext`, `wiki/pages/*.wikitext`.

## Источники и доверие

1. **Файлы игры** — primary: ID, внутренние имена, числа, цена, word7 (подтип), word12 (навык).
2. **Miraheze** — primary: классы посоха, добыча, тексты, таблицы щитов/аксессуаров/расходников.
3. **GameFAQs Item Tables** — secondary: колонка `Equip Limits` для аксессуаров и особого оружия.
4. **Fandom / docs/uo/classes.json** — secondary: классовые навыки, уровни, описания.
5. **data/** — текущая реализация MYUO; поле `implementation` показывает, что уже перенесено.

Источники не смешаны молча: расхождения лежат в `conflicts`, а спорные ограничения — в
`classes.notes`. Если источник не найден, `classes.rule = "unrestricted"` и
`classes.source = "no documented limit"` — это не значит, что ограничения нет.

## Схема предмета

```json
{
  "catalog_id": "game:SWORD_01",
  "id": "bronze_sword",
  "name": "Bronze Sword",
  "kind": "sword",
  "slot": "light_sword",
  "subtype": "sword",
  "stats": {"phys_atk": 8, "mag_atk": 0, "phys_def": 0, "mag_def": 0, "guard_rate": 0},
  "game_stats": {"phys_atk": 8, "mag_atk": 0, "phys_def": 0, "mag_def": 0, "guard_rate": 0},
  "wiki_stats": {"phys_atk": 8, "mag_atk": null, "phys_def": null, "mag_def": null, "guard_rate": null},
  "price": 500,
  "sell": 50,
  "substats": [],
  "skill": null,
  "skill_id": [],
  "classes": {
    "allowed": ["lord", "high_lord", "paladin", "..."],
    "rule": "base",
    "source": "miraheze:Swords",
    "text": "Lord/High Lord / Paladin / ...",
    "subtype": "sword",
    "notes": []
  },
  "acquisition": "All mercenaries and recruits early on start with this weapon.",
  "description": "",
  "match": {"type": "exact", "score": 1.0},
  "game": {"id": 282, "internal": "SWORD_01", "subtype_word": 1, "debug": false, "dummy": false},
  "wiki": {"page": "Swords", "name": "Bronze Sword"},
  "sources": ["game:main.bin", "miraheze:Swords"],
  "conflicts": [],
  "suggested": {
    "slot": "light_sword",
    "modifiers": [{"stat": "phys_atk", "op": "FLAT", "value": 8}],
    "skills": [], "passives": [], "item_passives": [],
    "tags": [], "ap_bonus": 0, "pp_bonus": 0, "guard_efficiency": null,
    "price": 12, "tier": 2, "notes": []
  },
  "implementation": {"present": true, "base_present": true, "id": "bronze_sword", "tier": 0, "price": 20}
}
```

`stats` — канонические числа: значения игры имеют приоритет, вики заполняет пробелы;
`game_stats` и `wiki_stats` сохранены отдельно. `classes.allowed` — id классов из
`data/units.json`; пустой список при `unrestricted` означает «ограничение не задокументировано».
Для посохов `rule`: `all_staff`, `arcane`, `divine`, `shaman`, `gleaming_mace`, `staff_explicit`.
Для оружия: `base`, `hammer`, `crossbow`, `rapier`, `flame_javelin`, `dragoons_warspear`, `alain_only`.
Для аксессуаров: `explicit`, `non_caster`, `cavalry`, `flying`, `melee`, `unrestricted`.

`suggested` — черновик для импорта: модификаторы, слот, навыки/пассивки, теги, цена и тир.
Цена и тир рассчитаны по силе внутри вида, это предложение, а не числа из игры; отладочные
и пустые записи в расчёте тира не участвуют.
`implementation` — что уже есть в `data/items.json` (по slug); `present: false` — ещё не перенесено.
`base_present: true` при `present: false` означает, что в MYUO есть только базовый вариант,
а этот дубликат (суффикс `__2`, `__3`) ещё не добавлен.
`match.type`: `exact`/`alias`/`fuzzy` — связь с вики, `wiki_only` — только вики (расходники/материалы),
`none` — только игра.

## Схема навыка

```json
{
  "id": "power_bolt",
  "name": "Power Bolt",
  "category": "active",
  "type": "Attack",
  "ap": 1,
  "pp": 0,
  "phys": 120,
  "hits": 1,
  "accuracy": 100,
  "classes": ["Arbalist 1", "Shieldshooter 1"],
  "items": ["game:BOW_01"],
  "text": "Attack a single enemy.",
  "game_text": "Attack a single enemy.",
  "game": {"id": 171, "internal": "ACT_POWER_BOLT"},
  "game_variants": [{"id": 171, "internal": "ACT_POWER_BOLT", "category": "active"}],
  "implementation": {
    "present": true, "kind": "skill", "id": "power_bolt",
    "stub": false, "parts": 1, "has_effect": true, "status": "implemented"
  }
}
```

## Что важно при переносе

- **Посохи.** `word7`: 5 — все посохи, 7 — аркана, 8 — божественные, 26 — Gleaming Mace,
  27 — шаманские. Вики-таблица даёт те же группы, но для Gleaming Mace расходится:
  вики — все лекари, game word7/GameFAQs — Cleric/Bishop. В `conflicts` это отмечено.
- **Молоты.** `word7=6`: Banishing Hammer, Juggernaut, Mason's Hammer, Morningstar, Rose Knight Hammer, Spiked Hammer, Warhammer.
  Разрешены Werebear/Warrior/Breaker.
- **Арбалеты.** `word7=31`: Gallian Crossbow, Woodpecker; Arbalist/Shieldshooter.
- **Рапиры.** `word7=34`: Stingray, Moonlight Rapier; Swordfighter/Sword Master.
- **Особые копья.** Flame Javelin — Soldier/Sergeant; Dragoon's Warspear — Wyvern Knight/Master.
- **Holy Unicorn Blade** — Lord/High Lord (Алана нет в `data/units.json`, поэтому записаны эти классы).
- **Аксессуары.** Явно задокументированы Mage's Gloves, Master's Gauntlets, Guardian Gloves,
  Wyvern/Heavenwyvern/Courser's/Heavensteed Reins, Wyvern Claw, Shawl of Repose, Counter Belt.
  Остальные оставлены `unrestricted`; это не приговор, а отсутствие источника.
- **Отладка.** `game.debug`/`game.dummy` — записи вида `HP +50`, `WEAPON_EXPAND_*`, `-`.
  Их не надо переносить в игру.
- **Дубликаты.** Одинаковые имена (`Cursed Blade of the Abyss` и т.п.) сохранены как отдельные
  записи; `id` получает суффикс `__2`, `__3`, `variant_of` указывает на базовый.
- **Навыки.** 439 игровых записей; после склейки active/passive-вариантов — 437 карточек.
  Все 205 классовых навыков из `docs/uo/classes.json` привязаны к карточкам (в том числе через
  алиасы `Aid Cover`→`Healing Cover`, `Demonic Pact`→`Daemonic Pact`, `Slyphic Barrier`→`Sylphic Barrier`).
  Числа из игры, тексты из вики, где есть. `implementation.status`: `implemented` — есть эффекты;
  `stub` — известные пустые wall/magick_wall/resurrection; `present_no_effects` — запись есть,
  но эффекты ещё не разобраны; `missing` — записи нет. Два игровых навыка имеют
  active/passive-варианты (Animated Dead, Dark Armor) — они сохранены в `game_variants`.
- **Valor/leader skills** в этот файл не включены: в игровом enum они не имеют отдельных
  ACT/PAS-записей с английскими именами. Это отдельный слой.

## Как переносить

1. Берите только записи без `game.debug`/`game.dummy`; отладочные `-`, `HP +50`,
   `WEAPON_EXPAND_*` в игру не переносятся.
2. Для снаряжения основой служит `suggested`: `slot`, `modifiers`, `skills`, `passives`,
   `item_passives`, `tags`, `ap_bonus`, `pp_bonus`, `guard_efficiency`, `price`, `tier`.
   `suggested.notes` — строки субстатов, которые не разобрались автоматически.
   `guard_efficiency` вынесен отдельно, потому что в текущем `data/items.json` такого стата нет.
   `item_passives` — сгенерированные пассивки «лечение при активном навыке»; их нужно создать
   при импорте, если в проекте ещё нет соответствующих `uo_item_heal_*`.
3. `classes.allowed` переносите в `ItemDefinition.classes`. При проверке учитывайте
   и текущий класс, и историю повышений: `[definition.id, *state.history]`.
   Дополнительно сверяйте `slot` предмета со слотами класса: если слота нет, предмет
   недоступен даже при совпадении класса.
4. Сначала сверяйтесь с `implementation`: если `present: true`, в `data/items.json` уже есть
   предмет с этим `id`; сравните `implementation.modifiers`/`tier`/`price` с `suggested`.
5. Для навыков `implementation` показывает, есть ли уже запись в `data/skills.json` или
   `data/passives.json`; `status: "missing"` — надо добавлять, `stub` — реализация неполная.
6. `game_variants` сохраняет оба игровых варианта (active/passive), даже если карточка одна.

## Известные пробелы

- Добыча заполнена не у всех: без `acquisition` осталось 382 шт. снаряжения.
  Описаний нет ни у одной из 638 единиц снаряжения. Miraheze хранит описания только для расходников/материалов и
  части отдельных страниц, а не для снаряжения.
- Часть игровых предметов без характеристик (67 записей: 19 реальных и 48 отладочных/пустых);
  они включены с `has_stats: false`, чтобы список был полным.
- `wiki_only`-снаряжения нет: Kaikai's Shield и Lips's Ring оказались алиасами Caecius и
  Libonotus Wind Ring (совпали игровые ID 705/849 и характеристики). Все 139 `wiki_only` —
  расходники и материалы.
- Локализационные пары (Sacral→Sainted, Staff→Rod, Apeliotes→Apeliotes's Bow и т.п.)
  сматчены через `ALIAS_PAIRS` и помечены `match.type = "alias"`.
- 0 строк субстатов не разобраны и лежат в `suggested.notes`; числа в игровых
  описаниях иногда остаются `%s`, если число подстановок не совпало (`game.numbers_filled = false`).

## Проверка

```powershell
python tools/uo_catalog.py --main F:\MYUO2\main.bin --text F:\MYUO2\unpacked_us
python -X utf8 -c "import json; d=json.load(open('docs/uo/catalog/items.json',encoding='utf-8')); print(d['counts'])"
```

Конфликты:

```powershell
python -X utf8 -c "import json; d=json.load(open('docs/uo/catalog/items.json',encoding='utf-8')); [print(i['name'], c) for i in d['items'] for c in i['conflicts']]"
```
