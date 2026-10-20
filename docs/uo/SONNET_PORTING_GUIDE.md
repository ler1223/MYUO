# Перенос каталога UO в игру: пошаговая инструкция для Sonnet 5.5

> **Статус (2026-10-20): шаги 0–7 выполнены.** Итоги: `FEATURES.md` (разделы «Снаряжение», «Навыки», «Эффекты», «Реакции», «Показ боя»),
> приближения — `docs/uo/import_report.md`, что проверить глазами — `docs/uo/anim_checklist.md`. Ниже сохранён исходный план; где код
> и план разошлись (например, особые свойства предметов сделаны полем `traits`, а не новыми статами), верно то, что в коде.

Составлено 2026-10-20. Задача — перенести в MYUO все навыки и предметы из
`docs/uo/catalog/` и реализовать способности, которые сейчас заглушки или приближения,
а потом дать им анимации в показе боя.

Работай по шагам по порядку. После каждого шага прогоняй тесты и делай отдельный коммит.
Если факт из этой инструкции не сходится с кодом, верь коду: проверь, исправь и отметь
расхождение в отчёте шага.

---

## 0. Где работать и правила проекта

**Репозиторий:** `C:\opencode\MYUO`, ветка `visualization` (remote `origin` = github.com/ler1223/MYUO).
Каталог `docs/uo/catalog/` и начатый перенос есть **только здесь**, в коммиты они ещё не попали.
`F:\MYUO2\MYUO` — вторая копия на `origin/visualization` без этой работы. Не работай в ней, пока
не запушишь шаг 0.

**Файлы игры** (только читать):
- `F:\MYUO2\main.bin` (то же самое лежит в `C:\opencode\main.bin`): исполняемый файл с таблицами навыков и предметов;
- `F:\MYUO2\unpacked_us` (или `C:\opencode\unpacked_us`): тексты, `MsgSheet/*.fms`, `Debug/_UcEnum_*.inc`;
- `F:\MYUO2\unpacked`: распакованный `Unicorn.CPK` с куклами и эффектами для показа боя.
  Путь записан в `assets/uo_anim/local.json`.

**Правила кода, как сейчас в проекте:**
- комментарии, docstring и документация на русском, сообщения коммитов на английском (смотри `git log`);
- данные лежат в `data/*.json`, ядро боя — в `game/` (без графики), показ — в `battle/`, инструменты — в `tools/`;
- после каждого изменения возможностей обновляй `FEATURES.md` (раздел и «Не реализовано и ограничения»);
- тесты: `python -m unittest discover -s tests -t .` (или `python -m pytest -q`). Сейчас 406 зелёных.
  Тесты показа выключают кукол через `MYUO_UO_ANIM=0`, видеокарта для них не нужна;
- `Database.load()` проверяет ссылки: неизвестный эффект, навык, тег или класс в данных — это ошибка загрузки.
  После каждой правки данных выполни `python -X utf8 -c "from game.database import Database; Database.load()"`;
- инструменты переноса пиши идемпотентными, с режимом «без `--write` только отчёт»
  (как `tools/uo_import_catalog.py`). Ручные правки данных не должны теряться при повторном запуске;
- не переноси отладочные и пустые записи каталога (`game.debug`, `game.dummy`: `-`, `HP +50`, `WEAPON_EXPAND_*`).

**Ключевые файлы:**

| Что | Где |
|---|---|
| Каталог предметов / навыков (схема — в README) | `docs/uo/catalog/items.json`, `skills.json`, `README.md` |
| Сборщик каталога | `tools/uo_catalog.py` |
| Перенос каталога предметов в `data/items.json` | `tools/uo_import_catalog.py` |
| Полные тексты пассивок-заглушек (сделано для этой задачи) | `docs/uo/catalog/stub_passives.json` |
| Старый перенос классов и навыков, отчёт о приближениях | `tools/uo_import.py`, `docs/uo/import_report.md` |
| Навыки, пассивки, эффекты, предметы, классы | `data/skills.json`, `passives.json`, `effects.json`, `items.json`, `units.json` |
| Определения навыка, предмета, `SkillExtras` | `game/definitions.py` |
| Реакции: события `ON_*` и действия `DO_*` | `game/reactions.py` |
| Бой | `game/combat/engine.py`, `field.py`, `rules.py` |
| Показ боя и анимации навыков | `battle/`, `data/uo_battle.json`, `skill_editor.py`, `anim_review.py` |

---

## Шаг 0. Зафиксировать начатую работу

В рабочем дереве `C:\opencode\MYUO` лежат незакоммиченные изменения:
- `docs/uo/catalog/` — сам каталог; `tools/uo_catalog.py` — его сборщик; `tools/uo_import_catalog.py` — перенос в данные;
- `data/items.json` — импорт уже выполнен (`--write`): ограничения по классам (418 предметов), навыки и пассивки предметов,
  модификаторы из игры, AP/PP-бонусы, предметы `twinned_bough_ii`, `greatshield_of_the_abyss_ii`,
  `ring_of_the_unicorn_ii`, `ring_of_the_unicorn_iii`;
- `game/unit.py` (`class_allowed`, `Unit.can_equip`, фильтр снаряжения по классу и истории повышений),
  `game/definitions.py` (`ItemDefinition.classes`, `SkillExtras.revive`/`revive_pct`),
  `game/combat/engine.py` (`Battle._revive`), `game/combat/field.py` (целью воскрешения становится павший союзник),
  `game/tower.py`, `game/scenario.py` (снаряжение врагов и стартовое снаряжение с учётом классов; при загрузке сохранения
  неподходящие предметы возвращаются в инвентарь), правки UI в `pygame_*`.

Что сделать:
1. `git status`, `git diff --stat`. Убедись, что список совпадает с описанным выше.
2. Прогони тесты. Должно быть 406 passed.
3. Проверь, что тестов на новое нет: `class_allowed`, возврат предметов в инвентарь, `_revive`. Если их нет,
   добавь (`tests/test_core.py` / `tests/test_tower.py` / `tests/test_combat_uo.py` — посмотри, как там устроены хелперы
   в `tests/helpers.py`).
4. Добавь в `FEATURES.md` (раздел «Снаряжение») ограничения по классам и описание каталога.
5. Сделай два коммита: `UO catalog: items and skills reference from game files and wikis` (docs и tools) и
   `Items: class restrictions from the UO catalog, revive extras` (data и game). Запушь `origin visualization`
   **только если пользователь попросит**.

---

## Шаг 1. Починить тексты пассивок в каталоге

**Проблема.** У 108 пассивок предметов в каталоге есть только строка условия
(«Activates after an enemy attacks with an active skill.»), а строки действия нет. Поэтому
`tools/uo_skills_game.py` создал их заглушками: реакция `restore_pp` с `amount: 0`, то есть пассивка
ничего не делает и всё равно тратит PP. Всего таких заглушек в `data/passives.json` — 111.

**Найдено.** Строка действия пассивки лежит в `UcSkillList.fms` по индексу **`957 + game_id`**: смещение то же,
что у описаний активных навыков. Это проверено на 64 из 70 пассивок с известной второй строкой. Строка условия
лежит по индексу `1428 + game_id`. Числа вместо `%s` берутся из блоков записи навыка: слова 17, 26 и 35 записи
(вид, float-значение), их подставляет `fill_skill_text`. Готовый результат для всех 111 заглушек лежит в
`docs/uo/catalog/stub_passives.json` (`trigger`, `effect`, `effect_blocks`, `items`).

Что сделать:
1. В `tools/uo_catalog.py`, функция `extract_game_skills`, для пассивок брать вторую строку как
   `sheet[957 + sid]`. Нынешний подбор `off_effect` голосованием по `skills_game.json` оставь только
   как проверку.
2. Исправь знак и проценты при подстановке чисел. Сейчас они местами неверные (видно в `stub_passives.json`):
   - «Inflicts Initiative +30» / «Inflicts Attack 20%» / «Inflicts AP +1». Дебаффы должны быть отрицательными:
     `-30`, `-20%`, `AP -1`. Скорее всего, знак хранится в виде блока: сравни `effect_blocks` с вики-текстами
     классовых навыков с похожей формулировкой;
   - «Grants an ally +1 Guard Rate» (`honed_shield`) — должно быть в процентах;
   - «Recover HP equal to +1 of damage dealt» (`judgment`) — это 100%;
   - `tailwind` — число не подставилось (`numbers_filled: false`).
   Значения видов (`kind`) для процентов и абсолютных чисел — это `PCT_TYPES` / `RAW_TYPES` в `uo_catalog.py`, дополни их.
3. Пересобери каталог: `python tools/uo_catalog.py --main F:\MYUO2\main.bin --text F:\MYUO2\unpacked_us`.
   Проверь, что `counts` не поменялись (437 навыков, 777 предметов) и что у всех 219 пассивок в `text` по меньшей мере две строки.
   Исключение — `celestial_light`: его текст — заглушка самой игры («Unleash its true power…»), не трогай его.
4. Обнови `stub_passives.json` тем же кодом (или удали его, если каталог теперь даёт то же самое) и пересобери отчёт.
5. Коммит: `UO catalog: passive effect lines and signed numbers from the skill table`.

---

## Шаг 2. Предметы: всё, что ещё не перенесено

Состояние после шага 0: 569 настоящих единиц снаряжения в каталоге, 588 записей в `data/items.json`.
16 записей каталога отсутствуют: `nameless_*`, `obsidian_*`, `veterans_*`, `astral_pike`, `magebane_bow`,
`feathered_crest_greatshield`. У всех них `has_stats: false`, это неиспользуемые записи игры, **не переноси их**.

### 2.1 Сверка
Запусти `python -X utf8 tools/uo_import_catalog.py` без `--write`. В отчёте должно быть «предметов изменено: 0».
Если там не ноль, разберись, откуда взялась разница, прежде чем писать.

### 2.2 Субстаты, которые не переносятся (`suggested.notes`, 59 строк)

| Строка | Сколько | Как сделать |
|---|---|---|
| `HP -15`, `HP -30` | 8 | Это обычный модификатор `{"stat": "hp", "op": "FLAT", "value": -15}`. Парсер `split_substats`/`suggested` его пропустил — исправь сам парсер, а не данные вручную |
| `Deathblow Immunity` | 14 | Новый флаг или тег носителя: смертельные удары (`Deathblow`/«Execution»: extras навыка вида «убить с шансом / при HP ниже …») на него не действуют. Сначала найди, как сейчас реализованы `execution`, `extinction`, `lethal_venom` |
| `Take N% Less Damage` | 6 | Новый стат `damage_taken` (PERCENT, по умолчанию 0), применяется в `rules` после защиты. Добавь в `game/stats.py` и в формулу урона |
| `HP Recovery +N%` | 7 | Новый стат `heal_received` — множитель входящего лечения в `Battle._heal` |
| `Follow-up Skills Deal +N Damage` / `Have +N Potency` | 5 | Бонус к силе навыков, применённых реакцией с тегом преследования (`pursuit`). Нужен тег навыка-ответа (`_strike` у преследований) и стат или эффект с `attack_mods` и `skill_tag` |
| `Counterattack Skills have/Deal +N` | 2 (+ `retaliation_earrings`, `parrying_shield`) | То же для контратак (тег `counter`) |
| `Drain Skill Efficiency +30%` | 2 | Множитель к `SkillExtras.lifesteal` / `heal_on_hit` у носителя |
| `User Earns +N% EXP`, `User's Unit Earns +N% Gold` | 15 | Вне боя: башня (`game/tower.py`, опыт и награда этажа). Сделай статы `exp_gain` / `gold_gain`, бой их не трогает |

Правило: каждый новый стат добавляй в `Stat`, в редактор предметов (`pygame_item_editors.py`), в
`data/lang/ru.json` (подпись) и в тест.

### 2.3 Блок щитом (`suggested.guard_efficiency`, 100 предметов)
В UO у щита есть сила блока (малый, средний и большой блок срезают разную долю урона). В `data/items.json` такого
стата нет. Сделай стат `guard_efficiency` (доля урона, которую срезает блок) и используй его в `rules` при исходе
«блок». Сейчас размер блока берётся из эффектов `uo_guard_small` / `uo_guard_medium` / `uo_guard_heavy`: посмотри,
как они устроены, и сделай так, чтобы стат щита задавал значение по умолчанию, а эффект его перекрывал.

### 2.4 Пассивки «лечение при активном навыке»
`uo_item_heal_10/15/20` уже есть в `data/passives.json` и привязаны к предметам. Проверь только, что у всех 14
предметов из `suggested.item_passives` они действительно стоят.

### 2.5 Расходники и материалы (98 + 41, `kind: consumable/material`)
В проекте нет расходников (`FEATURES.md`: «Расходники (зелья) … не сделаны»). Это отдельная большая задача.
**Не делай её в рамках этого плана**: только допиши в `FEATURES.md`, что каталог для них готов.

Коммиты: по одному на каждую механику (`Stats: damage taken and healing received from UO items`, …) и последний —
`Items: remaining UO substats from the catalog`.

---

## Шаг 3. Семь активных навыков-заглушек

У этих навыков пустые `parts`, `applies` и `extras`, в бою они ничего не делают:

| id | Текст UO | Как сделать (существующие эффекты из `data/effects.json`) |
|---|---|---|
| `wall` | Grants the user a buff that negates one physickal attack. | `applies: [{effect: uo_negate_melee или новый uo_negate_phys, to: self}]`. Проверь, что «physickal» — это не только ближний бой (луки тоже физические) |
| `magick_wall` | …negates one magick attack or one affliction. | `uo_negate_magic` + новый заряд «снять одно состояние» (или `uo_immune_debuff` с `charges: 1`) |
| `bulwark` | Grants a row of allies a buff that negates one physickal attack. | как `wall`, но `targets: ally`, `area: row` |
| `dark_armor` | Completely negate attacks up to two hits. | `uo_negate_one` с `charges: 2` (новый эффект `uo_negate_two`). Внимание: у навыка есть active- и passive-варианты (`game_variants`) |
| `mystic_shield` | Grants the user 50% Mag. Defense and +2 PP. | новый эффект `uo_mag_def_p50pct` (`PERCENT_ADD` 50; внимание: существующий `uo_mag_def_p50` — это FLAT +50, проверь, кто на него ссылается и не ошибка ли это тоже) + `pp_restore: 2` по себе |
| `row_resistance` | Grants allies in the user's row 50% Mag. Defense. Extends to all allies during the day. | Ряд — `uo_mag_def_p50pct`. «Днём — все» требует дня и ночи (шаг 5.2). До шага 5 сделай только ряд и отметь это в `FEATURES.md` |
| `resurrection` | Revive one ally, restoring them to 1 HP. | `extras: {revive: true, revive_pct: 0}`, `targets: ally`. Механика уже есть (шаг 0) |

Для каждого добавь тест в `tests/test_combat_uo.py`: навык меняет исход боя (удар обнулён, союзник поднят и так далее).
Коммит: `UO skills: wall, magick wall, bulwark, dark armor, mystic shield, row resistance, resurrection`.

---

## Шаг 4. 111 пассивок-заглушек

Источник — `docs/uo/catalog/stub_passives.json` (после шага 1 — каталог). Напиши инструмент
`tools/uo_fill_passives.py`: явная таблица `id -> реакция` на Python, без угадывания по регулярным выражениям.
Инструмент переписывает только записи, которые всё ещё заглушки (`restore_pp` с `amount: 0`), и печатает отчёт.
Навыки-ответы называй `<id>_strike` / `<id>_heal`, а поле `name` давай **тем же английским именем, что у пассивки**:
по имени `tools/uo_battle/build.py` найдёт внутреннее имя и эффекты навыка в файлах игры.

Формат реакции смотри в `data/passives.json` и в разделе «Реакции» файла `FEATURES.md`. Готовые шаблоны, которые
уже работают (бери за образец ближайший по смыслу):

| Шаблон | Событие, чьё, действие | Образцы |
|---|---|---|
| бафф себе перед ударом по себе | `targeted`, self, `apply_effect` | `heavy_guard`, `quick_guard`, `parry` |
| прикрытие | `targeted`, ally, `cover` | `heavy_cover`, `arrow_cover`, `luminous_cover` |
| бафф союзнику перед его атакой | `before_skill`, ally, `apply_effect` | `keen_call`, `magick_conferral`, `sniping_order` |
| бафф или навык в начале боя | `battle_start`, self, `apply_effect` / `use_skill` | `pure_field`, `quick_cast`, `sneaking_edge`, `hastened_strike` |
| контратака | `skill_used`, enemy, `use_skill` | `wide_counter`, `heavy_counter`, `magick_counter` |
| преследование | `skill_used`, ally, `use_skill` | `pursuit`, `knights_pursuit`, `shadow_pursuit` |
| ответ на удар по союзнику | `attacked`, ally, `use_skill` | `quick_heal`, `following_slash` |
| конец боя | `battle_end`, self, `use_skill` / `heal` | `parting_blow`, `medical_aid` |
| снять дебафф | `effect_applied`, ally, `dispel` | `refresh`, `quick_cure` |
| AP после навыка | `skill_used`, self, `restore_ap` | `elemental_impetus` |

### 4.1 Группы заглушек и что для них нужно

**A. Сразу на готовых механиках** (только данные и навыки-ответы):
- начало боя, баффы и дебаффы: `dawn_horn`, `bunker_stance`, `impetus_stance`, `war_cry`, `magick_shell`, `darkness_armor`,
  `quick_action`, `hastened_curse`, `eye_of_the_warrior_princess`, `ominous_wall`, `reheal`, `provoking_wall`, `scornful_dead`;
- начало боя, первый удар: `rapid_shot`, `hastened_shatter`, `provoking_strike`, `ground_punisher`;
- конец боя: `fire_burst`, `poison_burst`, `judgment`, `party_aid`;
- контратаки: `counter`, `banishing_counter`, `phantom_counter`, `vanquish`, `magick_burst`, `phantom_kick`, `venom_touch`, `vanitas`, `poison_touch`;
- преследования: `aerial_pursuit` (только летающий союзник — условие на subject по тегу `flying`), `banishing_pursuit`,
  `wide_pursuit`, `shattering_pursuit`, `sanguine_pursuit`; `guard_hunter` (событие `attacked` с исходом «блок» по врагу);
- после своего навыка: `daemonic_pact` (урон себе 25% + 1 AP: нужны два действия, см. B), `grave_impetus` (`died`, ally),
  `blade_dance`, `tailwind`; после удара по себе или блока: `vengeful_impetus`, `guarding_impetus`, `nimble_fighter`, `guarding_fighter`;
- перед ударом по себе: `invincible`, `phantom_step`, `dark_step`, `dynamic_glide`, `undead_wall`, `magick_conversion`,
  `toughness` (`uo_endure`), `painbringer`;
- перед ударом по союзнику: `grant_evade`, `sylphic_barrier`, `mighty_shield`, `preemptive_heal`, `quick_barrier`, `protection`;
- перед атакой союзника: `powerful_call`, `inspiration`, `wide_inspiration`, `sorcerous_connection`, `holy_breath`, конверсии
  `flame_/ice_/thunderous_/sanguine_/dark_conferral` (бафф с `attack_mods`: магическая часть +50 силы и состояние, `charges: 1`);
- перед вражеской атакой: `cursed_gaol`, `shining_light`;
- лечение состояний: `poison_cure`, `fire_cure`, `freeze_cure`, `stun_cure`, `blind_cure`, `guard_cure`, `passive_cure`
  (`effect_applied` с фильтром по конкретному эффекту, снять его и вылечить 10%: тоже два действия), `self_care`, `sacred_cure`;
- после пассивки или навыка союзника: `passive_gift`.

**B. Нужна одна общая доработка — несколько действий у пассивки.** Сейчас у пассивки ровно одна реакция
(`FEATURES.md`, «Не реализовано»). Почти у трети заглушек два действия: «прикрыть + вылечить», «снять дебафф +
вылечить», «урон себе + AP», «уклонение + бафф». Сделай в `game/reactions.py` необязательное поле реакции
`then: [ {action, skill_id/effect_id/amount/percent, to, …}, … ]`: дополнительные действия с теми же ролями,
которые выполняются после главного; PP тратится один раз. Поддержи его в загрузке, сохранении, редакторе
пассивок (`pygame_editors.py`, раздел F8: можно показывать списком строк, как поведение эффекта) и в тестах.
Это откроет: `healing_cover`, `advance_cover`, `evil_cover`, `enduring_cover`, `sacrifice`, все `*_cure`, `daemonic_pact`,
`abyssal_miasma`, `dynamic_glide`, `dark_step`, `undead_wall`, `magick_conversion`, `relic_heal`, `holy_breath`.

**C. Нужны новые механики движка** (каждая — отдельный коммит с тестом):

| Механика | Пассивки | Где делать |
|---|---|---|
| «Следующее действие с инициативой +N / максимальной» | `quick_action`, `hastened_action`, `hastened_cast` | эффект с `charges: 1` на инициативу; проверь, как `quick_cast` сейчас приближён (+100 на весь бой) и замени на заряд |
| «Союзник действует ещё раз» / «действие без траты AP» | `quick_impetus`, `reinforce` | очередь ходов в `game/combat/engine.py` |
| Повторить заклинание | `recast` | `skill_used`, self, фильтр `magic`: применить тот же навык (новое действие `repeat_skill`) |
| Отразить магию | `reflect_magick` | `targeted`, фаза «до»: удар уходит в атакующего, его пассивки «до/после» не срабатывают |
| Передать дебаффы | `mirror_weakness` | снять дебаффы с себя и наложить их на цель (новое действие) |
| Поделиться HP | `lifeshare` | лечение союзника за счёт HP владельца (50% его HP) |
| Мгновенный заряд | `hastened_charge` | зависит от зарядных навыков (шаг 5.3) |
| Баффы по числу целей | `heavy_alignment`, `aerial_alignment`, `united_front` | условие «сколько юнитов с тегом / разница численности»: новое условие в `game/tactics.py`, его же используют реакции |
| Бонус по тегу союзника | `wolf_pack`, `bears_den`, `phalanx_shift`, `aerial_shift`, `tailwind` («вдвое для летающих») | `then` + условие на получателя по тегу (`bestral`, `cavalry`, `flying`) |
| День и ночь | `diurnal_impetus`, `nocturnal_impetus`, `hastened_heal` | шаг 5.2 |

**D. Не переносить:** `celestial_light` — текст игры — заглушка, в игре этот навык сюжетный. Оставь как есть и
отметь в отчёте.

Порядок: сначала A (данные), потом B (`then`) и данные под него, потом C по одной механике. После каждой
подгруппы — `Database.load()`, тесты, коммит `UO passives: <группа>`. В `tests/test_combat_uo.py` добавь хотя
бы по одному бою на каждый шаблон: пассивка сработала, PP потрачен, эффект виден.

---

## Шаг 5. Приближения у уже «реализованных» навыков

`implementation.status: implemented` в каталоге значит только «эффекты есть». Список упрощений при старом
переносе — в `docs/uo/import_report.md` (верх файла). Основные группы:

1. **Конец боя.** Событие `battle_end` уже есть (`game/reactions.py`, `ON_BATTLE_END`). `first_aid`, `life_blow`,
   `medical_aid`, `parting_blow`, `wing_rest` всё ещё могут быть на «конец раунда, раз за бой»: проверь и переведи на
   `battle_end`. `parting_resurrection` — на настоящее воскрешение (`extras.revive`).
2. **День и ночь.** `night_vision`, `nocturnal_strike`, `nocturnal_evade`, `nocturnal_rest`, `diurnal_guard`,
   `photon_arrow`, `row_resistance`, `diurnal_impetus`, `nocturnal_impetus`, `hastened_heal`. Нужно состояние боя
   «день/ночь» (`Battle.time_of_day`, задаётся сценарием, башня — по номеру этажа или случайно), условие
   `time_of_day` в `game/tactics.py` для реакций и навыков (`requires_self`) и подпись в показе. В `game/scenario.py`
   уже есть упоминание `night`: начни с него.
3. **Зарядные навыки** («charge»: действие в конце раунда): `glacial_rain`, `arrow_rain`, `blizzard`, `trinity_rain`,
   `circle_heal`, `radiant_heal`, `gravity`, `dragoon_dive`. В UO навык тратит ход на подготовку и срабатывает в
   конце раунда. Нужен эффект-заряд и действие на `round_end`. В показе нужна лента подготовки (часть `TAME`/`*_CHARGE`
   есть в `skill_effect_by_name.json` и в файлах классов).
4. **Феи** (`elemental_roar`, `faerie_heal`, `primus_edge`, `sylphic_wind`, `rage_of_the_faeries`,
   `boon_of_the_faeries`, `freezing_thrust`, `thunderous_thrust`, `elemental_impetus`). Нужен счётчик фей у юнита
   (стакающийся эффект `uo_faerie`, предел из текста UO), сила навыка от числа стаков (`potency` по стакам эффекта)
   и «рассеять всех фей». Это крупная механика, делай её последней.
5. **Случайные цели** (`dual_shot`, `icicle_arrow`, `magick_missile`, `triple_counter`, `chaos_unending`): удары
   по случайным врагам. Нужна область `random_N` (каждый удар выбирает цель заново).
6. **Прочее из отчёта**: `deflect` (взят только первый эффект; с `then` можно взять все), `quick_curse` (несколько
   состояний), `sanguine_arts` (вампиризм следующей атаки — эффект с `attack_mods`, а не лечение), `discharge`
   (сила от снятых баффов), `selfless_heal` (лечение группы), `passive_miracle` и `restore` (нужно событие
   «союзник применил пассивку»: добавь `ON_PASSIVE_USED`; оно же нужно для `passive_gift`), `lifeshare`,
   `compounding_curse` / `defensive_curse` / `offensive_curse` / `passive_curse` / `pursuit` (сила взята 100:
   возьми числа из каталога, поля `phys` / `mag`).
7. **Скейлы от цели** (`bastards_cross`, `checkmate`, `gravity`, `painful_smash`, `medical_aid`: «от HP цели»,
   «от недостающего HP») — тоже в списке «Не реализовано» в `FEATURES.md`. Добавь в часть навыка `scaling` статы
   `target_hp`, `target_missing_hp`, `self_missing_hp`.

Сверяй каждое число с каталогом: `phys`, `mag`, `hits`, `accuracy`, `ap`, `pp` там из игры. Быстрая проверка —
скрипт, который сравнивает `data/skills.json` с `docs/uo/catalog/skills.json` по этим полям и печатает расхождения.
Добавь его в `tools/` и держи расхождения на нуле. Исключения допустимы, но каждое нужно объяснить в отчёте.

После шага 5 перепиши `docs/uo/import_report.md`: в нём должны остаться только настоящие оставшиеся упрощения.

---

## Шаг 6. Анимации новых и изменённых навыков

### 6.1 Как устроена новая система

Данные лежат в `data/uo_battle.json` → `manual` (сборщик `tools/uo_battle/build.py` этот раздел не трогает):
- `manual.animations.<id>` — **стандартная анимация класса**: `{"class", "name", "parts": [части тела из .mbs класса],
  "holds": {"<номер части>": мс}, "tags"}`. Части — имена анимаций в файле куклы класса (`ATTACK_A1`, `MAGIC_A`,
  `S03_MEGA_SLASH_1`…). `*` в конце имени части значит «повторять по кругу»;
- `manual.skill_animations.<skill_id>` — **анимация навыка**, одна на навык для всех классов и предметов:
  `animation` (id стандартной анимации), `caster_fx` / `target_fx` (эффекты `Effect/Battle_Effect.mbs`:
  `{"anim", "start", "end"}`, время в мс; у `target_fx` время отсчитывается от удара; `end: 0` — родная длина эффекта),
  `trajectory` (кривая полёта снаряда: `curve` — точки `[доля пути, подъём]`, отрицательный подъём — вверх; `speed`, `fall`),
  `rain` (дождь эффектов по стороне противника: `duration`, `entries: [{anim, count}]`), `tags` (только подсказки);
- `manual.classes.<класс>.timing.<skill_id>` — удары, подход и возврат: `hits`, `approach` / `ret`
  (`auto | none | dash | jump | chain | back`), `approach_from/to`, `ret_from`;
- старое (запасное): `classes.<класс>.skills.<skill_id>` — цепочка частей, которую нашёл сборщик или
  `tools/uo_battle/item_animations.py`; `skills.<skill_id>` — вид (`melee | ranged | magic | heal | support`),
  `cast`, `hit`, `shot` из игры.

Логика и проверка формата — `battle/animation.py` (`normalize_*`, `from_manual`, `to_json`).

**Какую цепочку играет показ** (`battle/director.py`, `Director.chain`):
1. `skill_animations[sid].animation` → `animations[...].parts`, если хотя бы одна часть есть в модели класса;
2. иначе `classes[cls].skills[sid]` (своя цепочка класса из файла игры);
3. иначе `default_chain(cls, kind)`: обычная атака или каст класса, в крайнем случае — стойка.

Отсюда главный подвох: **анимация навыка одна на все классы, а части берутся из модели конкретного
класса**. Навык предмета, привязанный к анимации лучника, у мага сыграет обычный каст (пункт 3 списка выше). Это
нормально и задумано, но не привязывай общие навыки (`attack`, навыки предметов) к анимации одного класса,
если эти части есть не у всех. Для таких навыков оставляй `animation: ""` и задавай только `caster_fx` / `target_fx` / `trajectory` / `rain`.

**Редактор** — `python skill_editor.py` (пользователь работает в нём мышью):
- слева класс и все его навыки: свои и навыки предметов, которые влезают в его слоты (навыки предметов отмечены «·»);
- «Создать из обычной атаки» → `import_legacy_animation`: стандартная анимация `<класс>__<навык>` из нынешней цепочки,
  сразу привязана к навыку; «Создать новую анимацию» → `new_animation_for_skill`: пустая `anim_N`, привязана и открыта в библиотеке;
- «Библиотека анимаций (C)»: части (добавить, переставить, убрать), длительность части ±50 мс, переименование, копия, удаление
  (удаление отвязывает анимацию от навыков);
- вкладки «Эффекты», «Полёт» (T: редактор кривой с готовыми углами), «Дождь», «Теги»; кнопки «п.от», «п.до», «возв»,
  «удар» берут момент из событий анимаций (`model.puppet.events`: 0 — удар, 1 — движение, 2 — получает удар, 3 — остановка);
- Ctrl+S пишет `manual.animations`, `manual.skill_animations` и `manual.classes.<класс>.timing`.
Проверка руками — `python anim_review.py`: пользователь ставит «верно / неверно» в `data/anim_review.json`.

### 6.2 Что сделать

1. После шагов 3–5 запусти `python tools/uo_battle/build.py`, чтобы новые навыки (`*_strike`, `*_heal`)
   получили вид и эффекты игры в `skills.<id>`. Сборщик находит внутреннее имя по английскому имени навыка, поэтому
   у навыка-ответа должно быть то же `name`, что у пассивки. Проверь, что у всех навыков из `data/skills.json` есть
   запись в `uo_battle.json` → `skills`.
2. Запусти `python tools/uo_battle/item_animations.py` (сначала без `--write`): он найдёт в файлах классов
   свои цепочки навыков предметов (`S##_<НАВЫК>_*`). Затем запусти с `--write`.
3. Пересобери таблицу покрытия: `python tools/uo_battle/table.py` → `docs/uo/skill_table.md`. Сделай к ней
   сводку: у каких навыков источник «общая» (обычная атака или каст), хотя навык не обычный удар
   (область `row` / `column` / `all`, дождь, лечение группы, баффы).
4. Для навыков-ответов пассивок (`*_strike`, `*_heal`, сейчас у 72 навыков нет `skill_animations`) **не создавай
   стандартных анимаций**: показ играет удар класса, этого достаточно. Задай им только `target_fx` из `skills.<id>.hit`,
   если сборщик нашёл свой эффект пассивки (`PAS_*`).
5. Для 77 пустых `skill_animations` (`animation: ""` и без эффектов, в основном навыки предметов) проверь, что
   после пункта 2 у них появилась своя цепочка класса. Пустые записи, которые ничего не дают, удали: показ без них
   работает так же.
6. Навыки с областью «ряд», «все» и дождём (`arrow_rain`, `blizzard`, `icestorm`, `firestorm`, `earthquake`,
   `trinity_rain`…): если в `skills.<id>` нет своего эффекта на поле, задай `rain` (эффекты попадания, `count` ≈ 6–12,
   `duration` ≈ 1000–1500 мс). Для навесных выстрелов задай `trajectory` с подъёмом (готовые углы — в
   `Editor.preset_curve`).
7. Записывай программно и только через `battle.animation.to_json` (тот же формат, что у редактора), сохраняя
   ручные правки: ключи, которые уже есть в `manual.animations` / `manual.skill_animations`, не перезаписывай.
   Сделай это инструментом `tools/uo_battle/fill_skill_animations.py` с `--write`.
8. Тесты: `tests/test_skill_preview.py`, `tests/test_item_animations.py`, `tests/test_battle_show.py`,
   `tests/test_animations.py`. Добавь проверку: каждый навык из `data/skills.json` строится в `Director.chain`
   без исключения для каждого класса, у которого он есть (свой или предметный). Это можно проверить без видеокарты
   только по данным: части привязанной анимации существуют в списке анимаций модели — смотри, как это делают
   существующие тесты.
9. **Глазами ты анимацию не проверишь.** В конце шага составь для пользователя список «что проверить в
   `anim_review.py` / `skill_editor.py`»: класс, навык, что именно поменялось.

Коммит: `Battle show: animations for the new UO skills and passive responses`.

---

## Шаг 7. Завершение

1. `FEATURES.md`: разделы «Навыки», «Эффекты», «Реакции», «Снаряжение», «Показ боя» и «Не реализовано и
   ограничения». Дату «Актуально на» обнови.
2. `docs/uo/catalog/README.md`: обнови «Известные пробелы» (тексты пассивок починены, субстаты перенесены).
3. Пересобери каталог (шаг 1, п. 3): у `implementation.status` не должно остаться `stub` и `present_no_effects`.
   Если что-то осталось, объясни причину в README.
4. Полный прогон тестов. Итоговый отчёт пользователю:
   - что перенесено (числа до и после);
   - какие механики добавлены;
   - что осталось приближением и почему;
   - список для ручной проверки анимаций.

---

## Приложение A. Быстрые команды

```powershell
cd C:\opencode\MYUO
python -m unittest discover -s tests -t .
python -X utf8 -c "from game.database import Database; Database.load(); print('ok')"
python tools/uo_catalog.py --main F:\MYUO2\main.bin --text F:\MYUO2\unpacked_us
python -X utf8 tools/uo_import_catalog.py            # отчёт; --write — записать
python tools/uo_battle/build.py                      # data/uo_battle.json (manual не трогает)
python tools/uo_battle/item_animations.py            # --write
python tools/uo_battle/table.py                      # docs/uo/skill_table.md
python skill_editor.py                               # редактор анимаций (нужны moderngl и папка игры)
python anim_review.py                                # ручная проверка анимаций
```

Заглушки пассивок, которые ещё остались:

```powershell
python -X utf8 -c "import json; p=json.load(open('data/passives.json',encoding='utf-8')); print([k for k,v in p.items() if v['reaction']['action']=='restore_pp' and not v['reaction'].get('amount')])"
```

## Приложение B. Подводные камни

- `Database.load()` падает на неизвестных ключах `extras` (`SkillExtras.from_dict`). Новое поле сначала добавь в
  dataclass, потом в данные.
- Реакция-навык не вызывает реакций на атаку (контратака на контратаку невозможна), а цепочка реакций обрывается
  на шестом звене. Не пытайся обойти это в данных.
- «Limited» в UO значит «раз за раунд» (`limit: "round"`; ещё есть `"none"` и `"battle"`, см. `LIMITS` в `game/reactions.py`).
- У пассивки фаза «до» (`targeted`, `before_skill`) срабатывает не больше одной на каждую сторону.
  Защитные пассивки соревнуются: порядок — по инициативе владельца.
- Сюжетные классы (`story: true`) не ограничены по снаряжению (`class_allowed`).
- Локализационные дубли предметов (Sacral/Sainted и т.п., `ALIAS_DUPS` в `uo_import_catalog.py`) — один игровой
  предмет под двумя именами. Меняешь один — поменяй и второй.
- `skill_editor.py` пишет `data/uo_battle.json` целиком (`indent=1`). Если пользователь мог что-то сохранить
  в редакторе, перечитай файл перед программной записью и не держи его копию в памяти между шагами.
- В `F:\MYUO2\MYUO` лежит `stash@{0}` со старыми черновиками от 2026-10-15. Все они уже есть в коммитах ветки,
  не применяй его.
