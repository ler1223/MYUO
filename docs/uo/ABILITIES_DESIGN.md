# Навыки как в Unicorn Overlord: одна сущность для активных и пассивных

Задача для исполнителя (Sonnet 5.5). Составлено 2026-10-20 по файлам игры и нынешнему коду
`C:\opencode\MYUO` (ветка `visualization`, коммит `b3de8a9` и следующий за ним с этим документом).

**Цель.** Пассивка становится обычным навыком: у неё такое же тело (удар, лечение, наложение эффекта), как у активного,
плюс условие срабатывания. Пассивки стоят в той же тактике, что активные, с теми же условиями, и условия проверяются
**перед** срабатыванием. Навыки начала и конца боя — те же пассивки с фазой `battle_start` / `battle_end`.

Работай по шагам из раздела 5, каждый шаг — тесты и отдельный коммит (сообщения на английском, комментарии и
документация на русском, как во всём проекте). Пушить — только по просьбе пользователя.

---

## 1. Как это устроено в оригинале

Источники (всё уже выгружено, перепроверять не надо):
- `docs/uo/catalog/skill_records.json` — расшифрованные поля записи каждого навыка игры (`python -X utf8 tools/uo_skill_records.py`);
- `docs/uo/catalog/factors.json` — все условия тактики игры (201 настоящее + «None» и служебное «???») (`MsgSheet/UcFactorList.fms`) с ключами, группами и видами;
- справка игры (`MsgSheet/UcHelpList.fms`, строки 540–548, 702–722), цитаты ниже.

### 1.1 Тактика
> The tactics you set determine **when** a character will use **what skill**, and **who they will target**.
> Each skill can be assigned up to two **conditions**. In such cases, **both conditions** must be met for the skill to be used.
> On a character's turn, they'll use the highest skill on their **Priority List** with conditions that have been met.

- Тактика — один упорядоченный список строк «навык + условие 1 + условие 2». В игре в нём стоят и активные, и пассивные
  навыки (экран тактики: «+ Add a Tactic», «Condition 1», «Condition 2», шаблоны тактик по классам).
- **Доказательство из данных:** у записи навыка в main.bin слова 45–47 — условия тактики по умолчанию (номера UcFactorList).
  Они есть у 99 активных и **у 90 пассивок**: Aerial Shift — «Lowest HP» + «Flying Enemies Present», Pure Field — «Lowest HP»,
  Parting Resurrection — «Highest HP». То есть условия тактики у пассивки решают и *сработать ли*, и *по кому*.
- Порядок строк — приоритет. Для активного навыка: в свой ход берётся первая сверху строка, у которой выполнены условия и есть цель.
  Для пассивки (вывод из той же модели, в справке прямо не сказано — отметь это в FEATURES): при наступлении её события
  проверяются строки пассивок бойца сверху вниз, срабатывает первая подходящая.
- Убранный из тактики навык не используется (в игре так и есть: тактика решает, что применять).

### 1.2 Условия (UcFactorList) — три вида
Вид виден по описанию условия в игре (поле `kind` в `factors.json`):

| Вид | Описание в игре | Что делает | Сколько в игре |
|---|---|---|---|
| `prioritize` | «Prioritize …» / «The skill will override default targeting rules» | порядок целей (кого выбрать первым) | 48 |
| `target_only` | «Target only …» / «The skill will not activate if there are no applicable targets» | фильтр целей; нет подходящих — навык не срабатывает | 61 |
| `activates_only` | «Activates only when …» / «The skill will not activate otherwise» | условие на обстановку, на себя, на атаку | 92 |

Группы экрана (поле `group`, порядок UcFactorList 610–622): `formation` (ряды, день/ночь), `combatant_type`, `hp`, `ap_pp`,
`status` (бафф, дебафф, состояния), `attack_type` (физ./маг., атакован ряд/колонна/все, атакован конницей… — **это условия
пассивок**), `unit_size` (число врагов/союзников), `own_condition` (сам/другие, на мне бафф, N-е действие), `own_hp`,
`own_ap_pp`, `enemies_present`, `high_stats`, `low_stats`. Нынешнее правило редактора «две из одной группы не выбираются»
совпадает с игрой — сохрани его, сравнивая `group`.

Выбор цели без условий (справка 718–722): ближайший в переднем ряду, атака — враг прямо напротив, иначе ближайший; при
равенстве — случайно. Условие `target_only` не меняет этот порядок, а сужает круг; `prioritize` меняет порядок («передний ряд
от дальнего к ближнему, затем задний»). Это уже реализовано в `game/combat/field.py`: `default_order` (без условий), `priority_order` (порядок для условий-приоритетов) и `pick_target` — используй их, а `prioritize`-условие пусть только задаёт ключ сортировки поверх `priority_order`.

### 1.3 Запись навыка (main.bin, 76 слов) — что значат поля
| Слово | Смысл | Значения | В новом формате |
|---|---|---|---|
| 41 | вид | 1 активный, 2 пассивный | `kind` |
| 7 | тип (значок) | 1 атака, 2 помеха, 3 лечение, 4 поддержка | `type` |
| 12 | кому | активные: 1 враг, 6 союзник, 7 сам. Пассивки: 1 враг (обычный выбор), 2 атаковавший, 3 цель союзника, 4 действующий союзник, 5 атакованный/ослабленный союзник, 6 союзник, 7 сам | `target` |
| 13 | область | 1 одна, 2 две, 3 три, 5 все, 6 ряд, 7 колонна | `area` (`two`/`three` заменяют `extras.random_targets`) |
| 8 | особый ответ | 1 воскрешение, 2 добавка к атаке союзника, 3 преследование, 4 контратака, 5 отражение, 6 прикрытие | `response` |
| 43 | фаза пассивки | 1 начало боя, 2 до чужого действия, 3 до удара по себе, 4 после своей защиты, 5 после, 6 конец боя | `trigger.phase` |
| 44 | событие пассивки | 40 значений, таблица `TRIGGER_EVENTS` в `tools/uo_skill_records.py` | `trigger.event` / `whose` / фильтры |
| 45–47 | условия тактики по умолчанию | номера UcFactorList | `default_tactic` (ключи) |
| 66 | подготовка | ≠ 0 у «charging» | `extras.charge` |
| 1 | флаги | бит 0 — дальнобойный | `tags` (`ranged`) |
| 5, 6, 9, 10, 11 | AP, PP, физ./маг. сила, удары и точность | — | уже перенесены |
| 14, 42, 48, 49, 75 | не расшифрованы | 2–4 значения | не использовать |

Фазы пассивок в игре: начало боя 42, до чужого действия 56, до удара по себе 26, после своей защиты 7, после действия 78,
конец боя 10 (всего 219).

### 1.4 Правила срабатывания, которые уже есть и остаются
Из нынешнего движка (`game/combat/engine.py`, FEATURES «Правила срабатывания»): пассивка стоит PP; на одно действие боец
отвечает не больше чем одной пассивкой; общий предел пассивок на действие (`config.passives_per_action`); в фазе «до» —
не больше одной на сторону; ответы идут по инициативе; навык-ответ не вызывает ответов на атаку (нет контратаки на
контратаку); цепочка обрывается на шестом звене; оглушённый, замороженный и с печатью пассивок не отвечает.
Эти правила **не меняй**, меняется только *как выбирается* пассивка и *что она делает*.

---

## 2. Что сейчас в коде (от чего уходим)

- `data/passives.json` (226 пассивок): `{"name", "pp_cost", "reaction": {event, whose, фильтры, action, skill_id|effect_id|…, to, then}}`.
  Действия: `use_skill` 81 (тело — отдельный навык `<id>_strike/_heal/_buff/_curse/_pact/_gift/_revive` в `data/skills.json`,
  99 штук), `apply_effect` 92, `cover` 13, `dispel` 8, `restore_ap` 8, `heal` 7, `remove_effect` 7, `restore_pp` 4,
  `tiered` 3, `consume_buffs`, `repeat_skill`, `reflect_debuffs` по 1.
- `game/definitions.py`: `PassiveDefinition(id, name, pp_cost, reaction)`; `SkillDefinition` — только активные.
- Классы и предметы: отдельные списки `skills` и `passives` (`data/units.json` 180 пассивок у классов, `data/items.json` 164 ссылки).
- Тактика: `game/tactics.py` `TacticRule(skill_id, condition, self_condition, selector)` — только активные. У пассивок —
  костыль `Unit.passive_tactics: dict[passive_id, TacticsSet]` («Тактики пассивок» в FEATURES): правило выбирает навык-ответ
  и цель *после* того, как пассивка уже сработала по своей реакции. Это и надо заменить.
- Условия — `ICondition.check(actor, candidate)` (`game/tactics.py`): без доступа к бою, поэтому «2+ врагов», «атакован
  конницей», «первое действие», «средний HP целей» сейчас выразить нельзя.
- Движок: пассивки — `_reactors` / `_matches` / `_perform` / `_passive_plan` / `_cover` в `game/combat/engine.py`.
  Поведение эффектов (яд, регенерация, `triggers` в `data/effects.json`) идёт тем же путём — **оно остаётся реакциями**,
  это не навыки.
- Инструменты, которые пишут пассивки: `tools/uo_fill_passives.py`, `tools/uo_fix_skills.py`, `tools/uo_import_catalog.py`,
  `tools/uo_audit_skills.py` (проверяет `<пассивка>_*` навыки-ответы).

---

## 3. Целевая структура

Пример данных — `docs/uo/abilities_example.json` (10 навыков, переведённых руками, и тактика бойца).

### 3.1 Навык (`data/skills.json`, одна запись на навык)
Все нынешние поля `SkillDefinition` остаются (`name, ap_cost, pp_cost, hits, accuracy, tags, parts, bonus_vs, ap_restore,
pp_restore, applies, requires_self, requires_target, potency, extras`). Добавляются:

| Поле | Тип | По умолчанию | Смысл |
|---|---|---|---|
| `kind` | `active` \| `passive` | `active` | вид (слово 41) |
| `type` | `attack` \| `debuff` \| `heal` \| `support` | выводится как сейчас `game/skill_kinds.py` | значок, ИИ, подсказки (слово 7) |
| `target` | `enemy` \| `ally` \| `self` \| `attacker` \| `ally_target` \| `acting_ally` \| `affected_ally` | из `targets` | кому (слово 12); заменяет `targets` (старое поле читать, писать новое) |
| `area` | + `two`, `three` | `single` | «две / три цели»: выбранная + случайные; вместо `extras.random_targets` |
| `trigger` | объект или `null` | `null` у активных, обязателен у пассивок | когда срабатывает (3.2) |
| `response` | `counter` \| `pursuit` \| `cover` \| `imbue` \| `reflect` \| `revive` \| `null` | `null` | особый ответ (слово 8): `cover` — прикрытие (3.3); `counter`/`pursuit` — для `traits` предметов (`counter_potency`, `followup_potency`) вместо нынешнего угадывания `_kind_of_response` |
| `cover` | `{"guard": small\|medium\|heavy\|null, "many": bool}` | — | только при `response: cover` |
| `limit` | `none` \| `round` \| `battle` | `none` | «Limited» и т. п. (из реакции) |
| `steps` | список шагов в формате нынешних `then` | `[]` | редкие действия, которых нет в теле навыка: `tiered`, `repeat_skill`, `reflect_debuffs`, `consume_buffs`, `restore_pp` с отрицательным числом |
| `default_tactic` | до двух ключей условий | `[]` | условия по умолчанию (слова 45–47) для тактики класса |

`kind: passive` ⇒ `ap_cost = 0`, `trigger` обязателен. `kind: active` ⇒ `trigger` нет. Проверка — в `from_dict`.

### 3.2 Условие срабатывания (`trigger`)
Это нынешние поля фильтра `Reaction` без действия — вынеси их в отдельный dataclass `Trigger` в `game/reactions.py`
(или новый `game/triggers.py`) и используй и в навыках, и внутри `Reaction` (эффекты):
`phase` (для показа и документации), `event`, `whose`, `area`, `attack_tags`, `skill_areas`, `outcome`, `effect_filter`,
`effect_label`, `threshold`, `subject_condition`, `actor_condition`. Таблица соответствия слова 44 событиям —
`TRIGGER_EVENTS` в `tools/uo_skill_records.py`, она же — проверка миграции (раздел 4).

### 3.3 Цель пассивки (`target`) — из момента события
| `target` | Кто | Откуда в `Moment` |
|---|---|---|
| `attacker` | кто атаковал / вызвал | `moment.actor` |
| `ally_target` | основная цель действия союзника | `moment.target` |
| `acting_ally` | союзник, который действует | `moment.subject` (событие `before_skill` / `skill_used`) |
| `affected_ally` | атакованный, ослабленный, вылеченный союзник | `moment.subject` |
| `self` | владелец | — |
| `enemy`, `ally` | любой по обычному выбору UO с условиями тактики | `default_order` + условия |

Область (`area`) раскрывается вокруг выбранной цели, как у активных (`affected`). Прикрытие: цель — `affected_ally`,
владелец принимает удар (нынешний `_cover`), `cover.guard` — уровень блока, тело навыка (если есть) применяется к
прикрытому (Healing Cover лечит прикрытого), `applies` с `to: self` — к защитнику (Enduring Cover).

### 3.4 Тактика (`units.json` → `tactics`, сохранения, редакторы)
```json
{"skill": "counter", "conditions": ["attacked_by_cavalry"]}
```
- `conditions` — до двух ключей из `factors.json`; две из одной `group` нельзя.
- Старый формат правила (`condition` / `self_condition` / `selector`) читать и переводить: `selector` → `prioritize`
  (`weakest` → `lowest_pct_hp`, `strongest` → `highest_phys_atk`… — таблица в шаге 2), `condition` → `target_only`,
  `self_condition` → `activates_only`. Условия, которых в игре нет (`has_effect: uo_burn` и т. п.), остаются «своими»
  условиями: `{"type": "has_effect", "effect_id": ...}` в списке `conditions` рядом с ключами игры.
- Один список на бойца: активные и пассивные. `Unit.passive_tactics` удаляется (сохранения переводятся: правила пассивки
  становятся строкой этой пассивки в общем списке, лишнее — отбрасывается с записью в журнал загрузки).
- Тактика по умолчанию класса: навыки класса и надетых предметов в порядке «как у класса», у каждого `default_tactic`.
  Сейчас у классов в `tactics` только активные — сгенерируй тактики по умолчанию инструментом (шаг 3).
- Навыки предметов: при надевании предмета его навыки, которых нет в тактике, добавляются в конец (с `default_tactic`);
  при снятии — убираются. Свою тактику бойца это правило меняет только добавлением/удалением строк.

### 3.5 Как бой выбирает пассивку
На каждый `Moment` (те же точки, что сейчас вызывают `_react`):
1. Владельцы — живые бойцы по убыванию инициативы (как сейчас).
2. Пропустить, если боец не может отвечать (печать, оглушение, заморозка, подготовка) или уже ответил на это действие, или
   достигнут предел пассивок действия.
3. Строки тактики бойца сверху вниз, только `kind: passive`, у которых `trigger` совпал с моментом (нынешний `_matches`
   по полям `Trigger`), `limit` не исчерпан, хватает PP.
4. `activates_only`-условия строки — по контексту (3.6). Не выполнены — следующая строка.
5. Кандидаты в цели — по `target` из момента (3.3) или обычный круг целей для `enemy`/`ally`; `target_only`-условия
   фильтруют; пусто — следующая строка («The skill will not activate if there are no applicable targets»).
6. `prioritize`-условия выбирают цель (иначе `default_order`).
7. Сработала: PP списан, акт `PASSIVE` (как сейчас — показ не меняется), тело навыка — через `_resolve(..., root=False)`,
   `steps` — через нынешний `_run_steps`. Дальше — следующий владелец.
Фаза «до» (`targeted`, `before_skill`): прикрытие (`response: cover`) решается в `_cover` по тем же шагам 3–6.
Начало и конец боя — тот же путь с `Moment(ON_BATTLE_START)` / `Moment(ON_BATTLE_END)`.

### 3.6 Контекст условий
Нынешнее `ICondition.check(actor, candidate)` не видит бой. Сделай контекст и передавай его во все проверки тактики:
```python
@dataclass(frozen=True)
class Context:
    battle: "Battle"            # стороны, раунд, время суток
    owner: "Unit"               # чья тактика
    moment: Optional[Moment]    # для пассивок: событие (атаковавший, теги атаки, область…)
    candidates: Sequence[Unit]  # круг целей навыка (для «среднего HP целей»)
    action_index: int           # какое по счёту действие владельца в бою («First Action»)
```
Условие игры реализуется классом с методом нужного вида: `gate(ctx) -> bool` (activates_only), `accepts(ctx, unit) -> bool`
(target_only), `key(ctx, unit) -> float` (prioritize, меньше — раньше). Старые `ICondition` оборачиваются адаптером, чтобы
`requires_self`/`requires_target`, `potency`, `applies.condition` работали как прежде.

---

## 4. Миграция данных (инструмент `tools/migrate_abilities.py`, `--write`)
Каждая пассивка `P` из `data/passives.json` → навык `P` в `data/skills.json`:
- `kind: passive`, `pp_cost`, `limit`, `trigger` из полей реакции;
- `use_skill` на `P_*`: тело = навык-ответ (`parts`, `applies`, `extras`, `hits`, `accuracy`, `tags`, `area`, `potency`),
  `target` — из `to` реакции (`actor` → `attacker`, `target` → `ally_target`, `subject` → `acting_ally` или `affected_ally`
  по событию, `owner` → `self` или `ally` по `targets` навыка-ответа, `enemies` → `enemy`); навык-ответ удаляется;
- `apply_effect` / `heal` / `restore_ap` / `restore_pp` / `dispel` / `remove_effect`: тело из одного наложения / части
  `heal_pct` / `ap_restore` / `pp_restore` / `extras.dispel` / новое `extras.remove_effects`; `to` → `target` + `area`
  (`allies`/`side` + `to_area: row` → `ally` + `area: row`; `enemies` → `enemy` + `area: all` и т. п.);
- `cover` → `response: cover`, `cover.guard` из эффекта (`uo_guard_heavy` → `heavy`, `uo_negate_one` → `null` + наложение);
- `then` → тело, если выразимо, иначе `steps`; `tiered` / `repeat_skill` / `reflect_debuffs` / `consume_buffs` → `steps`;
- `default_tactic` и `response` — из `docs/uo/catalog/skill_records.json` (сверка `target` и `trigger.event` с полями игры —
  расхождения печатать отчётом, не исправлять молча).
Ссылки: `units.json` и `items.json` — пассивки переносятся из `passives` в `skills` (уровень открытия сохраняется).
`tests/data/passives.json` (фикстура тестов) — тем же инструментом с флагом `--data tests/data`.
Затем `data/passives.json` удаляется, `Database` читает его только если он есть (старые песочницы), переводя на лету.
Показ: `python tools/uo_battle/build.py` (навыки-ответы исчезли, пассивки получили записи), `manual.skill_animations` с
ключами `P_*` переименовать в `P`.

---

## 5. Шаги

### Шаг 0. Подготовка
1. Прочитай этот файл, `docs/uo/abilities_example.json`, разделы «Навыки», «Реакции», «Тактики» в `FEATURES.md`,
   `game/reactions.py`, `game/tactics.py`, в `game/combat/engine.py` — `_choose`, `_react`, `_reactors`, `_matches`,
   `_perform`, `_step_plan`, `_run_steps`, `_cover`, `_passive_plan`.
2. `python -m pytest -q` — должно быть 485 passed. Запомни время (около 1–2 мин).

### Шаг 1. Условия тактики игры (`game/conditions.py`)
1. `Context` (3.6) и реестр условий из `docs/uo/catalog/factors.json`: на каждый `key` — объект вида `prioritize` /
   `target_only` / `activates_only`. Реализуй все 201 (большинство — параметризованные семейства: ряд, тип бойца, HP-порог,
   AP/PP-порог, состояние, число врагов/союзников, наличие типа врага, стат). «Attacked by X», «Physickally Attacked»,
   «Row/Column/All Allies are Attacked» берут данные из `ctx.moment` (у активных — всегда ложь). «N-е действие» —
   `ctx.action_index` (заведи счётчик действий бойца в `Battle`). Day/Night — `battle.time_of_day`.
2. Типы бойцов игры ↔ теги MYUO: Infantry `infantry`, Cavalry `cavalry`, Flying `flying`, Armored `armored`, Scout `scout`,
   Archer `archer`, Caster `caster`, Elven `elf`, Bestral `bestral`, Angel `angel` (все есть в `data/tags.json`).
3. Адаптер старых `ICondition` в `target_only`/`activates_only`; старые селекторы → `prioritize`:
   `weakest` → `lowest_pct_hp`, `strongest` → `highest_phys_atk` (сейчас «большая из атак» — сделай своё условие
   `strongest`, если нужно сохранить поведение), `frontmost` → нет условия (обычный выбор), `backmost` → `prioritize_back_row`,
   `random` → своё условие `random`.
4. Тесты `tests/test_conditions.py`: по одному на каждую группу, плюс «две из одной группы нельзя», плюс все ключи
   `factors.json` (кроме `none`/`story_only`) зарегистрированы.
Коммит: `Tactics: UO tactic conditions with battle context`.

### Шаг 2. Новое правило тактики
1. `TacticRule(skill_id, conditions: tuple[Condition, ...])` (≤ 2), `from_dict` читает и старый формат (3.4), `to_dict`
   пишет новый.
2. `TacticsSet.choose` (активные) — через `Context`: `activates_only` → кандидаты → `target_only` → `prioritize` → цель.
   Поведение старых тактик в тестах должно сохраниться (прогони `tests/test_core.py`, `test_combat*.py`).
3. `game/combat/engine.py:_choose` — тем же кодом.
Коммит: `Tactics: rules with up to two UO conditions, old format still read`.

### Шаг 3. Навык с триггером
1. `Trigger` (3.2); `SkillDefinition`: поля из 3.1, проверки; `Reaction` использует `Trigger` для фильтров (эффекты).
2. `tools/migrate_abilities.py` (раздел 4) — сначала отчёт без `--write`, просмотри расхождения со словами 12/44 игры.
   Запусти на `data/` и `tests/data/`.
3. `Database`: раздел `passives` больше не нужен; `units[...].skills` и `items[...].skills` содержат и пассивки;
   свойства `Unit.passive_ids` / `skill_ids` разделяют по `kind`.
4. Тактики по умолчанию классов: инструмент добавляет пассивки классов в `tactics` (после активных, в порядке
   изучения) с `default_tactic`. Предметы — правило 3.4.
Коммит: `Skills: passives are skills with a trigger; data migrated`.

### Шаг 4. Бой
1. Пассивки выбираются по 3.5: новый метод `_passive_candidates(owner, moment)` вместо ветки пассивок в `_reactors`;
   `_matches` проверяет `Trigger`; `_perform` для навыка: `_resolve` тела + `steps`. Ветка эффектов (`ActiveEffect`)
   остаётся как есть.
2. `_cover` — по навыкам с `response: cover`.
3. `_passive_plan` и `Unit.passive_tactics` — удалить; `game/save.py` переводит старые `passive_tactics`.
4. `_kind_of_response` → `skill.response` (`counter`/`pursuit`) для `traits` предметов.
5. Тесты: все нынешние тесты пассивок (`test_reactions.py`, `test_cover.py`, `test_uo_passives.py`, `test_uo_audit.py`,
   `test_passive_tactics.py` — его переписать под общий список) зелёные; новые: пассивка не срабатывает, если её строка
   убрана из тактики; срабатывает верхняя из двух подходящих; `activates_only` («Attacked by Cavalry») блокирует;
   `target_only` без кандидатов блокирует и не тратит PP; `prioritize` выбирает цель Pursuit/First Aid; навык начала
   боя с условием «Flying Enemies Present».
Коммит: `Combat: passives chosen by tactics with conditions checked before firing`.

### Шаг 5. Инструменты и показ
1. `tools/uo_fill_passives.py`, `tools/uo_fix_skills.py`, `tools/uo_import_catalog.py`, `tools/uo_audit_skills.py` —
   на новый формат (навыки-ответы исчезли: аудит сверяет пассивку напрямую с каталогом; заглушка = пассивка без тела и шагов).
2. `python tools/uo_battle/build.py`; `manual.skill_animations` / `classes.timing` с ключами навыков-ответов — переименовать;
   `battle/director.py` (`name`, `passive_scene`) — навык вместо реакции. `tests/test_battle_show.py` зелёный.
3. Каталог: `python -X utf8 tools/uo_catalog.py --reuse-game` (поле `implementation` — по новому формату).
Коммит: `Tools and battle show on the unified skill format`.

### Шаг 6. Интерфейс
1. Редактор тактик (F3, `pygame_editors.py`) и вкладка «Тактика» бойца башни (`pygame_tower_unit.py`): один список,
   активные (красная плашка AP) и пассивные (синяя PP) вперемешку; условия выбираются из групп `factors.json` (по-русски —
   добавь переводы ключей в `data/lang/ru.json`, имена групп — тоже), две из одной группы нельзя; плашки «Тактики пассивок»
   убрать.
2. Редактор навыков (F4) — вид, триггер (форма из нынешнего редактора пассивок F8), цель, ответ, лимит; редактор пассивок
   F8 становится частью F4 (вкладку убрать или оставить как фильтр «только пассивные»).
3. Подсказки (`pygame_tips.py`) и описание навыка (`game/editing.py: describe_skill`) — с триггером.
4. `tests/test_ui.py`, `tests/test_tower_ui.py` зелёные.
Коммит: `UI: one tactics list for active and passive skills`.

### Шаг 7. Документация
`FEATURES.md`: «Навыки» (вид, триггер, цель, ответ), «Тактики» (условия игры, три вида, группы, контекст), «Реакции»
(остались для эффектов), убрать «Тактики пассивок»; «Не реализовано» — что из условий не сделано. Отчёт пользователю:
что сломалось бы в старых сохранениях и как переводится, какие пассивки разошлись со словами 12/44 игры, что проверить руками
в редакторе тактик.

---

## 6. Подводные камни
- Не путай «условие срабатывания» (`trigger`, из данных навыка) и «условия тактики» (из строки тактики бойца): первое
  говорит, *на что* навык может ответить, второе — *хочет ли* боец отвечать именно так. Условия тактики не должны менять
  `trigger`.
- `requires_self` / `requires_target` у навыка остаются — это свойство навыка («только по отравленной»), а не тактики.
- Предел «одна пассивка на бойца за действие» проверяется **до** перебора строк (иначе боец потратит PP на вторую).
- PP списывается только когда цель найдена и навык реально применяется (как сейчас: «делать нечего — PP не тратится»).
- Навыки начала боя: в `_start` все бойцы по инициативе, у каждого — первая подходящая строка (предел «одна на действие»
  к началу боя относится так же: `_Action(one_each=False)` в `_start` — проверь, что одна пассивка на бойца, это правило игры
  для фазы начала боя тоже).
- Демо-тест `tests/test_assets.py` (доля сработавших пассивок в демо) может просесть: тактики по умолчанию теперь фильтруют;
  смотри на причину, а не снижай порог вслепую.
- `tools/uo_import.py` пишет старый формат — пометь его устаревшим, не запускай.
- Сохранения башни (`saves/`) и фикстура тестов `tests/data` — обе миграции обязательны.
- Числа силы/ударов/точности пассивок сверяй с каталогом (`tools/uo_audit_skills.py`) после миграции — расхождений должно
  остаться 0.

## 7. Отступления от плана, принятые при реализации (шаг 3)

- `targets` (сторона: enemy / ally / self) остаётся как есть; поле `target` у пассивки — роль из события или группа
  (`attacker`, `ally_target`, `acting_ally`, `affected_ally`, `self`, `source`, `enemies`, `allies`, `side`, `everyone`) плюс
  `target_area`. Так перевод без потерь: прежнее `to` реакции восстанавливается однозначно.
- У классов и предметов остаются два списка, `skills` (активные) и `passives` (навыки с `kind: passive`); `Database.passives` —
  производный вид (`SkillDefinition.passive_view()`), по нему работает движок. Раздел `passives` в данных больше не хранится; старый
  файл `passives.json` и вызовы `update("passives", ...)` из редакторов переводятся на лету (`game/abilities.py`).
- Тело навыка (`body: true`) получили только пассивки, чьим действием был «применить навык-ответ» (78 из 226). Остальные действия
  (наложить эффект, дать AP, вылечить долей HP, ступени, повтор навыка…) лежат в `steps` в формате прежних шагов реакции;
  прикрытие — `response: cover` + `cover`.
- `tools/migrate_abilities.py` выполнен на `data/` и `tests/data/` (passives.json удалён); навык `artenie_strike` (в игре пассивка)
  переведён из активных в пассивки `tools/uo_fix_skills.py`.
