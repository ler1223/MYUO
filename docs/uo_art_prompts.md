# Промпты картинок: классы, навыки и предметы Unicorn Overlord

Собрано `python tools/make_art_prompts.py` из справочника — перегенерируйте после его изменений. Промпты на английском. Запросы скрипт не делает: готовые тексты целиком — в `docs/requests/` (`python tools/build_requests.py`).

Всего запросов: 22 (спрайты классов — 19, экран бойца — 1, значки навыков — 1, иконки предметов — 1).

## Как пользоваться

1. Листы с сеткой 5x2 (1536x1024, прозрачный фон): в начало запроса — блоки **STYLE** и **SHEET** из `docs/ui_prompts.md`, затем ячейки батча. Первой строкой — `Match the art direction of the attached screenshots, but do not copy any text, logo or exact artwork.` и 1-2 скриншота UO.
2. Готовый лист — в `assets/ui/sheets/` под именем батча и нарезка: `python tools/cut_ui_sheet.py <номер> --force` (батчи 11+ ищутся в этом файле).
3. Спрайты классов — листы-линейки (раздел 1): общий промпт листа ниже плюс строки персонажей. Внешность берётся с коллажа-референса `assets/ref/lineups/uo_NN_ref.png` (арт классов UO в полный рост, собирает `python tools/uo_class_refs.py`): строка N = персонаж с номером N. Первый лист задаёт рост и стиль: его Fighter — эталон, готовый `uo_01.png` прикладывается ко всем следующим листам вместе с их коллажем. Лист — в `assets/sprites_src/lineup/` и `python tools/cut_lineup.py ...` (команда у каждого листа). Свой спрайт сразу заменяет временный похожий (прежние спрайты — `assets/units/old_*`).
4. Как в UO, у навыка и предмета нет своей картинки: значок — на тип навыка (атака, поддержка, лечение, помеха; активный или пассивный), иконка — на вид предмета. Тип навыка выводится из самого навыка (`game/skill_kinds.py`). Если всё же нужен свой значок, достаточно положить `skill/<тип>/<id>.png` или `item/<слот>/<id>.png`.

## 1. Спрайты классов — листы-линейки

Все 60 классов заново, семьями (базовый класс и его повышения рядом): 19 листов. Конница и летуны шире — их на листе меньше; рост выше человека указан в строке. Внешность — с коллажа `assets/ref/lineups/uo_NN_ref.png`: персонаж с тем же номером, что у строки, повторяется полностью.

## Линейка: первый лист

Приложить `assets/ref/lineups/uo_01_ref.png`.

```
The attached picture uo_01_ref.png shows numbered characters from Unicorn Overlord.
Draw them as one horizontal lineup of full-body game sprites, in the order of the numbers from left to right.

Follow the reference completely and repeat each picture: the same character with the same face, hair,
body, armor, clothes, colors, weapon, shield, mount or wings, in the same art style. Keep the pose of the
picture, only mirrored if needed so that everyone faces right. Do not change, add or invent anything.

Rules:
- one row on the same ground line, evenly spaced, nothing overlapping or cut off, full body from head to feet;
- one scale for everyone: a human is about 40% of the image height; riders, flyers and big beasts are taller - their height is in the line;
- transparent background, no ground, no shadow, no scenery, no text, no numbers.

Characters:
<персонажи>
```

## Линейка: остальные листы

Приложить готовый `assets/sprites_src/lineup/uo_01.png` и коллаж листа `assets/ref/lineups/uo_NN_ref.png`.

```
Two pictures are attached: uo_01.png - the first finished lineup, and uo_NN_ref.png - numbered
characters from Unicorn Overlord. Draw a new lineup the same way as uo_01.png: far left the Fighter from
uo_01.png, unchanged and at the same size, then the characters of uo_NN_ref.png in the order of the numbers.

Follow the reference completely and repeat each picture: the same character with the same face, hair,
body, armor, clothes, colors, weapon, shield, mount or wings, in the same art style. Keep the pose of the
picture, only mirrored if needed so that everyone faces right. Do not change, add or invent anything.

Rules:
- one row on the same ground line, evenly spaced, nothing overlapping or cut off, full body from head to feet;
- one scale for everyone: a human is as tall as that Fighter; riders, flyers and big beasts are taller - their height is in the line;
- transparent background, no ground, no shadow, no scenery, no text, no numbers.

Characters:
1. The Fighter from uo_01.png.
<персонажи>
```

## Листы линеек

**Лист 1** (`assets/sprites_src/lineup/uo_01.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_01.png fighter vanguard arbalist shieldshooter dreadnought --reference fighter`

```
1. Fighter - picture 1.
2. Vanguard - picture 2.
3. Arbalist - picture 3.
4. Shieldshooter - picture 4.
5. Dreadnought - picture 5.
```

**Лист 2** (`assets/sprites_src/lineup/uo_02.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_02.png _ref cleric bishop crusader valkyria --reference _ref`

```
2. Cleric - picture 2.
3. Bishop - picture 3.
4. Crusader - picture 4.
5. Valkyria - picture 5.
```

**Лист 3** (`assets/sprites_src/lineup/uo_03.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_03.png _ref dark_knight doom_knight --reference _ref`

```
2. Dark Knight - picture 2, rider on a horse, about 180% of a human's height.
3. Doom Knight - picture 3, rider on a horse, about 190% of a human's height.
```

**Лист 4** (`assets/sprites_src/lineup/uo_04.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_04.png _ref elven_archer elven_augur elven_fencer elven_sibyl --reference _ref`

```
2. Elven Archer - picture 2.
3. Elven Augur - picture 3.
4. Elven Fencer - picture 4.
5. Elven Sibyl - picture 5.
```

**Лист 5** (`assets/sprites_src/lineup/uo_05.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_05.png _ref feathersword gladiator berserker --reference _ref`

```
2. Feathersword - picture 2, flying.
3. Gladiator - picture 3, about 110% of a human's height.
4. Berserker - picture 4, about 115% of a human's height.
```

**Лист 6** (`assets/sprites_src/lineup/uo_06.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_06.png _ref gryphon_knight gryphon_master --reference _ref`

```
2. Gryphon Knight - picture 2, flying, about 200% of a human's height.
3. Gryphon Master - picture 3, flying, about 220% of a human's height.
```

**Лист 7** (`assets/sprites_src/lineup/uo_07.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_07.png _ref hoplite legionnaire housecarl viking --reference _ref`

```
2. Hoplite - picture 2.
3. Legionnaire - picture 3.
4. Housecarl - picture 4.
5. Viking - picture 5.
```

**Лист 8** (`assets/sprites_src/lineup/uo_08.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_08.png _ref hunter sniper paladin --reference _ref`

```
2. Hunter - picture 2.
3. Sniper - picture 3.
4. Paladin - picture 4, rider on a horse, about 180% of a human's height.
```

**Лист 9** (`assets/sprites_src/lineup/uo_09.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_09.png _ref knight great_knight --reference _ref`

```
2. Knight - picture 2, rider on a horse, about 180% of a human's height.
3. Great Knight - picture 3, rider on a horse, about 190% of a human's height.
```

**Лист 10** (`assets/sprites_src/lineup/uo_10.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_10.png _ref lord high_lord prince --reference _ref`

```
2. Lord - picture 2.
3. High Lord - picture 3, rider on a horse, about 180% of a human's height.
4. Prince - picture 4.
```

**Лист 11** (`assets/sprites_src/lineup/uo_11.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_11.png _ref priestess high_priestess sellsword landsknecht --reference _ref`

```
2. Priestess - picture 2.
3. High Priestess - picture 3.
4. Sellsword - picture 4.
5. Landsknecht - picture 5.
```

**Лист 12** (`assets/sprites_src/lineup/uo_12.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_12.png _ref radiant_knight sainted_knight --reference _ref`

```
2. Radiant Knight - picture 2, rider on a horse, about 180% of a human's height.
3. Sainted Knight - picture 3, rider on a horse, about 190% of a human's height.
```

**Лист 13** (`assets/sprites_src/lineup/uo_13.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_13.png _ref shaman druid snow_ranger werebear --reference _ref`

```
2. Shaman - picture 2.
3. Druid - picture 3.
4. Snow Ranger - picture 4.
5. Werebear - picture 5, about 125% of a human's height.
```

**Лист 14** (`assets/sprites_src/lineup/uo_14.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_14.png _ref soldier sergeant swordfighter sword_master --reference _ref`

```
2. Soldier - picture 2.
3. Sergeant - picture 3.
4. Swordfighter - picture 4.
5. Sword Master - picture 5.
```

**Лист 15** (`assets/sprites_src/lineup/uo_15.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_15.png _ref thief rogue warrior breaker --reference _ref`

```
2. Thief - picture 2.
3. Rogue - picture 3.
4. Warrior - picture 4.
5. Breaker - picture 5.
```

**Лист 16** (`assets/sprites_src/lineup/uo_16.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_16.png _ref werefox werelion wereowl --reference _ref`

```
2. Werefox - picture 2.
3. Werelion - picture 3, about 115% of a human's height.
4. Wereowl - picture 4, flying.
```

**Лист 17** (`assets/sprites_src/lineup/uo_17.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_17.png _ref werewolf witch sorceress --reference _ref`

```
2. Werewolf - picture 2.
3. Witch - picture 3.
4. Sorceress - picture 4.
```

**Лист 18** (`assets/sprites_src/lineup/uo_18.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_18.png _ref wizard warlock --reference _ref`

```
2. Wizard - picture 2.
3. Warlock - picture 3.
```

**Лист 19** (`assets/sprites_src/lineup/uo_19.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_19.png _ref wyvern_knight wyvern_master --reference _ref`

```
2. Wyvern Knight - picture 2, flying, about 200% of a human's height.
3. Wyvern Master - picture 3, flying, about 220% of a human's height.
```

## Батч 11 — экран бойца и тактика (`b11_unit.png`)

```
<STYLE>
<SHEET>
Cell 1: FRAME, tactic skill bar for skills paid with AP, 300x70: deep crimson fill (#7a1f24), thin gold border with small arrow-shaped right end like a banner, border band 20 px.
Cell 2: FRAME, the same tactic skill bar for skills paid with PP: deep blue fill (#1d4f8a).
Cell 3: FRAME, tactic condition bar, 300x70: muted olive-gold fill (#5c5230), thin gold border, small chevron ends, border band 20 px.
Cell 4: priority number plate, 100x80: slanted parallelogram plate in dark crimson with a gold edge, empty center for a number.
Cell 5: grade letter frame, 80x80: small square plate with cut corners, dark navy fill, thin gold border.
Cell 6: FRAME, dropdown option list window, 260x300: very dark navy, thin gold border, tiny corner diamonds, border band 20 px.
Cell 7: small square button icon, 90x90: gold upward triangle on a dark navy square with a gold edge.
Cell 8: the same button icon with a downward triangle.
Cell 9: the same button icon with a thin gold X (remove).
Cell 10: unit pedestal, 300x120: low round stone dais seen from the front at a slight top-down angle, carved edge with gold inlay, like the formation board of Unicorn Overlord.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `frame/tactic_ap.png` | 512x128 |
| 2 | `frame/tactic_pp.png` | 512x128 |
| 3 | `frame/tactic_condition.png` | 512x128 |
| 4 | `frame/priority.png` | 160x128 |
| 5 | `frame/grade.png` | 96x96 |
| 6 | `frame/picker.png` | 384x448 |
| 7 | `icon/up.png` | 96x96 |
| 8 | `icon/down.png` | 96x96 |
| 9 | `icon/remove.png` | 96x96 |
| 10 | `field/pedestal.png` | 512x192 |

## Батч 12 — значки типов навыков (`b12_skills.png`)

Круглый значок внутри кольца (кольцо рисует интерфейс). Верхний ряд — активные навыки (AP), нижний — пассивные (PP): тот же символ, другой цвет. Ячейки 5 и 10 пустые.

```
<STYLE>
<SHEET>
Cell 1: round active skill type icon "attack", 200x200: two crossed swords; warm antique gold symbol on a deep crimson round field (#7a1f24). A single bold symbol, no ring, no text.
Cell 2: round active skill type icon "support", 200x200: a heater shield with a rising chevron arrow above it; warm antique gold symbol on a deep crimson round field (#7a1f24). A single bold symbol, no ring, no text.
Cell 3: round active skill type icon "healing", 200x200: a cupped pair of hands holding a small glowing leaf-shaped light; warm antique gold symbol on a deep crimson round field (#7a1f24). A single bold symbol, no ring, no text.
Cell 4: round active skill type icon "sabotage", 200x200: a cracked shield with a downward chevron arrow below it; warm antique gold symbol on a deep crimson round field (#7a1f24). A single bold symbol, no ring, no text.
Cell 6: round passive skill type icon "attack", 200x200: two crossed swords; pale silver-blue symbol on a deep navy round field (#1b2a55). A single bold symbol, no ring, no text.
Cell 7: round passive skill type icon "support", 200x200: a heater shield with a rising chevron arrow above it; pale silver-blue symbol on a deep navy round field (#1b2a55). A single bold symbol, no ring, no text.
Cell 8: round passive skill type icon "healing", 200x200: a cupped pair of hands holding a small glowing leaf-shaped light; pale silver-blue symbol on a deep navy round field (#1b2a55). A single bold symbol, no ring, no text.
Cell 9: round passive skill type icon "sabotage", 200x200: a cracked shield with a downward chevron arrow below it; pale silver-blue symbol on a deep navy round field (#1b2a55). A single bold symbol, no ring, no text.
Cells 5 and 10: leave empty.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `skill/attack.png` | 256x256 |
| 2 | `skill/support.png` | 256x256 |
| 3 | `skill/healing.png` | 256x256 |
| 4 | `skill/sabotage.png` | 256x256 |
| 6 | `passive/attack.png` | 256x256 |
| 7 | `passive/support.png` | 256x256 |
| 8 | `passive/healing.png` | 256x256 |
| 9 | `passive/sabotage.png` | 256x256 |

## Батч 13 — иконки видов предметов (`b13_items.png`)

Одна иконка на вид предмета: лёгкий поворот три четверти, чистый силуэт, без рамки и фона (рамку цвета тира рисует интерфейс). Ячейки 9 и 10 пустые.

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200: a plain steel one-handed arming sword, blade pointing to the upper right. Single object, slight three-quarter view, no frame, no background.
Cell 2: inventory icon, 200x200: a heavy two-handed bearded war axe, head at the upper right. Single object, slight three-quarter view, no frame, no background.
Cell 3: inventory icon, 200x200: a long cavalry spear with a leaf-shaped steel head, diagonal. Single object, slight three-quarter view, no frame, no background.
Cell 4: inventory icon, 200x200: a wooden recurve bow with its string, held diagonally. Single object, slight three-quarter view, no frame, no background.
Cell 5: inventory icon, 200x200: a mage's wooden staff topped with a small glowing blue crystal, diagonal. Single object, slight three-quarter view, no frame, no background.
Cell 6: inventory icon, 200x200: a round-topped heater shield with a simple gold border. Single object, slight three-quarter view, no frame, no background.
Cell 7: inventory icon, 200x200: a large rectangular tower greatshield with iron rivets. Single object, slight three-quarter view, no frame, no background.
Cell 8: inventory icon, 200x200: a gold ring with a small blue gem. Single object, slight three-quarter view, no frame, no background.
Cells 9 and 10: leave empty.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/light_sword.png` | 256x256 |
| 2 | `item/heavy_weapon.png` | 256x256 |
| 3 | `item/lance.png` | 256x256 |
| 4 | `item/bow.png` | 256x256 |
| 5 | `item/staff.png` | 256x256 |
| 6 | `item/light_shield.png` | 256x256 |
| 7 | `item/greatshield.png` | 256x256 |
| 8 | `item/artifact.png` | 256x256 |

