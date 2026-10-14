# Промпты картинок: классы, навыки и предметы Unicorn Overlord

Собрано `python tools/make_art_prompts.py` из справочника — перегенерируйте после его изменений. Промпты на английском. Запросы скрипт не делает: готовые тексты целиком — в `docs/requests/` (`python tools/build_requests.py`).

Всего запросов: 22 (спрайты классов — 19, экран бойца — 1, значки навыков — 1, иконки предметов — 1).

## Как пользоваться

1. Листы с сеткой 5x2 (1536x1024, прозрачный фон): в начало запроса — блоки **STYLE** и **SHEET** из `docs/ui_prompts.md`, затем ячейки батча. Первой строкой — `Match the art direction of the attached screenshots, but do not copy any text, logo or exact artwork.` и 1-2 скриншота UO.
2. Готовый лист — в `assets/ui/sheets/` под именем батча и нарезка: `python tools/cut_ui_sheet.py <номер> --force` (батчи 11+ ищутся в этом файле).
3. Спрайты классов — листы-линейки (раздел 1): общий промпт листа ниже плюс строки персонажей. Внешность берётся с коллажа-референса `assets/ref/lineups/uo_NN_ref.png` (картинки классов с вики UO, собирает `python tools/uo_class_refs.py`): строка N = панель N. Первый лист задаёт рост и стиль: его Fighter — эталон, готовый `uo_01.png` прикладывается ко всем следующим листам вместе с их коллажем. Лист — в `assets/sprites_src/lineup/` и `python tools/cut_lineup.py ...` (команда у каждого листа). Свой спрайт сразу заменяет временный похожий (прежние спрайты — `assets/units/old_*`).
4. Как в UO, у навыка и предмета нет своей картинки: значок — на тип навыка (атака, поддержка, лечение, помеха; активный или пассивный), иконка — на вид предмета. Тип навыка выводится из самого навыка (`game/skill_kinds.py`). Если всё же нужен свой значок, достаточно положить `skill/<тип>/<id>.png` или `item/<слот>/<id>.png`.

## 1. Спрайты классов — листы-линейки

Все 60 классов заново, семьями (базовый класс и его повышения рядом): 19 листов. Конница и летуны шире — их на листе меньше; рост выше человека указан в строке. Внешность — с панели коллажа `assets/ref/lineups/uo_NN_ref.png` с тем же номером, что у строки. Где в справке UO двое (мужчина и женщина), рисуется тот, чей пол у класса в `female_classes` (`data/names.json`).

## Линейка: первый лист

Приложить `assets/ref/lineups/uo_01_ref.png`.

```
Draw a horizontal lineup sheet of full-body unit sprites for a high-fantasy tactics RPG, standing
in one row on the same flat ground line, evenly spaced with clear empty space between them, nothing
overlapping or cropped. This sheet sets the scale and style for all later sheets of the same cast.

REFERENCE: the attached numbered sheet (uo_01_ref.png) is the design reference - official class art of Unicorn
Overlord. Each numbered panel is one class: a large close-up illustration on the left and the same character as
a small full-body map sprite on the right. Line N of the list below = panel N of that sheet.
Reproduce every character faithfully from its panel: gender, face and hair, body build, armor and clothing
shapes, colors and patterns, helmet, cape, weapon, shield, mount or wings. Take the details from the close-up
and the full-body silhouette (legs, boots, mount) from the small sprite. Do not invent new outfits, do not swap
weapons, do not mix designs between panels. If a panel shows two people, draw only the one named in the line.
The line text is only a reminder of names and heights - where it seems to disagree, the panel wins. Ignore the
panel backgrounds and numbers.

SCALE RULES: everything at exactly the same scale, as if photographed together. A normal adult human
is as tall as the first character, about 40% of the image height. Taller units have their height in the line relative to a human (no note = human height; a weapon,
hat or ears may rise above the head). All feet touch the same ground line near the bottom edge; flying units
hover just above it. No character is enlarged or shrunk to fill its slot.

POSE: all face right, full body from head to feet, side view with a slight three-quarter turn toward the
viewer, calm combat-ready stance, weapons held close to the body. Mounts and wings fully visible, not cut by
the image edge.

FROM LEFT TO RIGHT:
<персонажи>

STYLE: the same hand-painted 2D art as the close-ups of the reference: painterly shading with soft
light from the upper left, clean dark contour lines, deep saturated but never neon colors, detailed cloth folds
and metal highlights. Proportions of the close-ups (realistic, about 7 heads tall), NOT the chunky chibi
proportions of the small map sprites. Every character in one consistent style, palette and lighting.

OUTPUT: transparent background PNG, no ground, no shadow, no scenery, no text, no numbers, no labels.
```

## Линейка: остальные листы

Приложить готовый `assets/sprites_src/lineup/uo_01.png` и коллаж листа `assets/ref/lineups/uo_NN_ref.png`.

```
Two images are attached. Draw a new horizontal lineup sheet of full-body unit sprites of the same cast,
standing in one row on the same flat ground line, evenly spaced with clear empty space between them, nothing
overlapping or cropped.

SCALE AND STYLE REFERENCE: the attached lineup sheet uo_01.png (unnumbered, transparent background). Far left
of the new sheet: its first character, the Fighter, unchanged and at exactly the same size. Match its
rendering style exactly.

REFERENCE: the attached numbered sheet (uo_NN_ref.png, with numbers) is the design reference - official class art of Unicorn
Overlord. Each numbered panel is one class: a large close-up illustration on the left and the same character as
a small full-body map sprite on the right. Line N of the list below = panel N of that sheet.
Reproduce every character faithfully from its panel: gender, face and hair, body build, armor and clothing
shapes, colors and patterns, helmet, cape, weapon, shield, mount or wings. Take the details from the close-up
and the full-body silhouette (legs, boots, mount) from the small sprite. Do not invent new outfits, do not swap
weapons, do not mix designs between panels. If a panel shows two people, draw only the one named in the line.
The line text is only a reminder of names and heights - where it seems to disagree, the panel wins. Ignore the
panel backgrounds and numbers.

SCALE RULES: everything at exactly the same scale, as if photographed together. A normal adult human
is as tall as that Fighter. Taller units have their height in the line relative to a human (no note = human height; a weapon,
hat or ears may rise above the head). All feet touch the same ground line near the bottom edge; flying units
hover just above it. No character is enlarged or shrunk to fill its slot.

POSE: all face right, full body from head to feet, side view with a slight three-quarter turn toward the
viewer, calm combat-ready stance, weapons held close to the body. Mounts and wings fully visible, not cut by
the image edge.

FROM LEFT TO RIGHT:
1. The Fighter from uo_01.png (unchanged).
<персонажи>

STYLE: the same hand-painted 2D art as the close-ups of the reference: painterly shading with soft
light from the upper left, clean dark contour lines, deep saturated but never neon colors, detailed cloth folds
and metal highlights. Proportions of the close-ups (realistic, about 7 heads tall), NOT the chunky chibi
proportions of the small map sprites. Every character in one consistent style, palette and lighting.

OUTPUT: transparent background PNG, no ground, no shadow, no scenery, no text, no numbers, no labels.
```

## Листы линеек

**Лист 1** (`assets/sprites_src/lineup/uo_01.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_01.png fighter vanguard arbalist shieldshooter dreadnought --reference fighter`

```
1. Fighter: as in panel 1.
2. Vanguard: as in panel 2.
3. Arbalist: as in panel 3.
4. Shieldshooter: as in panel 4.
5. Dreadnought: as in panel 5.
```

**Лист 2** (`assets/sprites_src/lineup/uo_02.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_02.png _ref cleric bishop crusader valkyria --reference _ref`

```
2. Cleric: as in panel 2.
3. Bishop: as in panel 3.
4. Crusader: as in panel 4.
5. Valkyria: as in panel 5.
```

**Лист 3** (`assets/sprites_src/lineup/uo_03.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_03.png _ref dark_knight doom_knight --reference _ref`

```
2. Dark Knight (cavalry): as in panel 2; about 180% of a human's height.
3. Doom Knight (cavalry): as in panel 3; about 190% of a human's height.
```

**Лист 4** (`assets/sprites_src/lineup/uo_04.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_04.png _ref elven_archer elven_augur elven_fencer elven_sibyl --reference _ref`

```
2. Elven Archer: as in panel 2, the female one of the two.
3. Elven Augur: as in panel 3.
4. Elven Fencer: as in panel 4, the female one of the two.
5. Elven Sibyl: as in panel 5.
```

**Лист 5** (`assets/sprites_src/lineup/uo_05.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_05.png _ref feathersword gladiator berserker --reference _ref`

```
2. Feathersword (flying): as in panel 2.
3. Gladiator: as in panel 3; about 110% of a human's height.
4. Berserker: as in panel 4; about 115% of a human's height.
```

**Лист 6** (`assets/sprites_src/lineup/uo_06.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_06.png _ref gryphon_knight gryphon_master --reference _ref`

```
2. Gryphon Knight (flying): as in panel 2; about 200% of a human's height.
3. Gryphon Master (flying): as in panel 3; about 220% of a human's height.
```

**Лист 7** (`assets/sprites_src/lineup/uo_07.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_07.png _ref hoplite legionnaire housecarl viking --reference _ref`

```
2. Hoplite: as in panel 2.
3. Legionnaire: as in panel 3.
4. Housecarl: as in panel 4.
5. Viking: as in panel 5.
```

**Лист 8** (`assets/sprites_src/lineup/uo_08.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_08.png _ref hunter sniper paladin --reference _ref`

```
2. Hunter: as in panel 2.
3. Sniper: as in panel 3.
4. Paladin (cavalry): as in panel 4; about 180% of a human's height.
```

**Лист 9** (`assets/sprites_src/lineup/uo_09.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_09.png _ref knight great_knight --reference _ref`

```
2. Knight (cavalry): as in panel 2; about 180% of a human's height.
3. Great Knight (cavalry): as in panel 3; about 190% of a human's height.
```

**Лист 10** (`assets/sprites_src/lineup/uo_10.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_10.png _ref lord high_lord prince --reference _ref`

```
2. Lord: as in panel 2.
3. High Lord (cavalry): as in panel 3; about 180% of a human's height.
4. Prince: as in panel 4.
```

**Лист 11** (`assets/sprites_src/lineup/uo_11.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_11.png _ref priestess high_priestess sellsword landsknecht --reference _ref`

```
2. Priestess: as in panel 2.
3. High Priestess: as in panel 3.
4. Sellsword: as in panel 4, the male one of the two.
5. Landsknecht: as in panel 5, the male one of the two.
```

**Лист 12** (`assets/sprites_src/lineup/uo_12.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_12.png _ref radiant_knight sainted_knight --reference _ref`

```
2. Radiant Knight (cavalry): as in panel 2; about 180% of a human's height.
3. Sainted Knight (cavalry): as in panel 3; about 190% of a human's height.
```

**Лист 13** (`assets/sprites_src/lineup/uo_13.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_13.png _ref shaman druid snow_ranger werebear --reference _ref`

```
2. Shaman: as in panel 2.
3. Druid: as in panel 3.
4. Snow Ranger: as in panel 4.
5. Werebear: as in panel 5; about 125% of a human's height.
```

**Лист 14** (`assets/sprites_src/lineup/uo_14.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_14.png _ref soldier sergeant swordfighter sword_master --reference _ref`

```
2. Soldier: as in panel 2, the male one of the two.
3. Sergeant: as in panel 3, the male one of the two.
4. Swordfighter: as in panel 4, the female one of the two.
5. Sword Master: as in panel 5, the female one of the two.
```

**Лист 15** (`assets/sprites_src/lineup/uo_15.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_15.png _ref thief rogue warrior breaker --reference _ref`

```
2. Thief: as in panel 2.
3. Rogue: as in panel 3.
4. Warrior: as in panel 4, the male one of the two.
5. Breaker: as in panel 5, the male one of the two.
```

**Лист 16** (`assets/sprites_src/lineup/uo_16.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_16.png _ref werefox werelion wereowl --reference _ref`

```
2. Werefox: as in panel 2.
3. Werelion: as in panel 3; about 115% of a human's height.
4. Wereowl (flying): as in panel 4.
```

**Лист 17** (`assets/sprites_src/lineup/uo_17.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_17.png _ref werewolf witch sorceress --reference _ref`

```
2. Werewolf: as in panel 2.
3. Witch: as in panel 3.
4. Sorceress: as in panel 4.
```

**Лист 18** (`assets/sprites_src/lineup/uo_18.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_18.png _ref wizard warlock --reference _ref`

```
2. Wizard: as in panel 2.
3. Warlock: as in panel 3.
```

**Лист 19** (`assets/sprites_src/lineup/uo_19.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_19.png _ref wyvern_knight wyvern_master --reference _ref`

```
2. Wyvern Knight (flying): as in panel 2; about 200% of a human's height.
3. Wyvern Master (flying): as in panel 3; about 220% of a human's height.
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

