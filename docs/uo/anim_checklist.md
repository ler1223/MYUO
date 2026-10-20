# Что проверить глазами в показе боя после переноса навыков

Анимации автоматически не проверить: у кукол нет «правильного» эталона, только файлы игры. Тесты (`tests/test_battle_show.py`)
проверяют расписание без видеокарты; ниже — то, что поменялось и требует взгляда в `python anim_review.py`
(пункты, у которых изменился состав, сами попросят проверки заново) и `python skill_editor.py`.

Покрытие «класс — навык»: `docs/uo/anim_coverage.md` (`python tools/uo_battle/fill_skill_animations.py --write`),
таблица цепочек: `docs/uo/skill_table.md` (`python tools/uo_battle/table.py`).

## 1. Навыки с подготовкой (новая сцена)

Навык тратит ход на подготовку: лента с названием, круг заклинания, поза `charge`; удар — в конце круга обычной сценой.
Если у класса нет фазы `charge`, поза не играется (остаётся лента и круг) — это допустимо, но стоит посмотреть.

| Навык | Что смотреть |
|---|---|
| arrow_rain | подготовка у лучника (hunter, sniper, arbalist…), в конце круга дождь стрел (`ARROWRAIN_OUT`) по всем |
| glacial_rain | то же у snow_ranger, заморозка на целях |
| blizzard | эффект `BLIZZARD` (теперь подобран), заморозка |
| trinity_rain | магический дождь, три удара |
| gravity | эффект `GRAVITY` / `GRAVITY_HIT`, урон — половина HP каждой цели |
| dragoon_dive | прыжок виверны: нет собственной анимации — проверить, что сыграла хоть какая-то атака |
| circle_heal, radiant_heal | лечение всех союзников в конце круга |
| пассивка hastened_charge | в начале боя подготовка пропускается: навык бьёт сразу |

## 2. Эффекты навыков, подобранные заново (`EFFECT_ALIAS` в `tools/uo_battle/build.py`)

blizzard (`BLIZZARD`), resurrection и parting_resurrection (`RESURRECT`), bulwark (`WALL`), magick_wall (`MAGICBARRIER`),
earthshaker (`EARTHSTOMP`), dark_flame (`DARKFLAME_FIRE`), chaos_unending (`CHAOS`), phalanx_shift (`PHALANX`),
strength_shatter_ii / magick_shatter (`POWER_BREAK`), passive_curse / passive_shatter_spear (`PASSIVE`).
Проверить, что эффект правильный по виду и месту (на цели или на применяющем).

## 3. Навыки, у которых сменился вид

- defensive_curse, offensive_curse, compounding_curse, passive_curse, chaos_unending: были «дальнобойными» с уроном, стали
  поддержкой (без урона, состояние на цели): в сцене не должно быть удара и цифр урона.
- sanguine_attack: был «лечением», стал ближним уроном с вампиризмом.
- animated_dead: теперь воскрешение союзника (поддержка), цель — павший.
- resurrection, reincarnation, parting_resurrection_revive: цель — павший; проверить, что кукла встаёт, а не «лечится».

## 4. Свои цепочки навыков предметов, найденные сборщиком

arrow_rain (arbalist, elven_archer, feather_bow, hunter, shieldshooter, sniper, snow_ranger), ground_strike (breaker, warrior),
freezing_thrust (elven_augur, elven_sibyl, eltlinde), true_thrust (hoplite, legionnaire), holy_cradle (feather_rod). Остальным
классам этих навыков играет обычная атака или каст — так и задумано.

## 5. Навыки с несколькими случайными целями

dual_shot, icicle_arrow, magick_missile, double_blast, photon_arrow, skyward_thrust, triple_shatter, triple_counter_strike:
сцена бьёт выбранного врага и ещё одного или двух случайных. Для ближнего боя проверить, что разбег идёт к выбранной цели, а не
к случайной; для дальнего — что снаряды летят ко всем.

## 6. Навыки-ответы пассивок (99 карточек)

`*_strike`, `*_heal`, `*_buff`, `*_curse`, `*_pact`, `*_revive`: играют удар или каст класса, эффекты — родные из `data/uo_battle.json`
(`skills.<id>`). Выборочно посмотреть: counter_strike, wide_counter_strike, banishing_counter_strike, vanitas_strike,
magick_burst_strike, dawn_horn_buff, wolf_pack_buff, tailwind_buff, hastened_heal_heal, relic_heal_heal, lifeshare_gift,
parting_resurrection_revive. Главное — нет «пустой» сцены (кукла стоит, цифры идут) и нет прыжка к неправильной цели.

## 7. Показ времени суток

Время суток (`Scenario.time_of_day`) в картинке пока не отражено: фон боя не меняется. Влияет только на правила (ночные и дневные
пассивки и навыки).
