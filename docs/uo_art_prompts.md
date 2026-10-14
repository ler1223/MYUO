# Промпты картинок: классы, навыки и предметы Unicorn Overlord

Собрано `python tools/make_art_prompts.py` из справочника — перегенерируйте после его изменений. Промпты на английском. Запросы скрипт не делает: готовые тексты целиком — в `docs/requests/` (`python tools/build_requests.py`).

Всего запросов: 22 (спрайты классов — 19, экран бойца — 1, значки навыков — 1, иконки предметов — 1).

## Как пользоваться

1. Листы с сеткой 5x2 (1536x1024, прозрачный фон): в начало запроса — блоки **STYLE** и **SHEET** из `docs/ui_prompts.md`, затем ячейки батча. Первой строкой — `Match the art direction of the attached screenshots, but do not copy any text, logo or exact artwork.` и 1-2 скриншота UO.
2. Готовый лист — в `assets/ui/sheets/` под именем батча и нарезка: `python tools/cut_ui_sheet.py <номер> --force` (батчи 11+ ищутся в этом файле).
3. Спрайты классов — листы-линейки (раздел 1): общий промпт листа ниже плюс строки персонажей; лист — в `assets/sprites_src/lineup/` и `python tools/cut_lineup.py ...` (команда у каждого листа). Первый лист задаёт рост и стиль: его Fighter — эталон, готовый `uo_01.png` прикладывается ко всем следующим листам. Свой спрайт сразу заменяет временный похожий (прежние спрайты — `assets/units/old_*`).
4. Как в UO, у навыка и предмета нет своей картинки: значок — на тип навыка (атака, поддержка, лечение, помеха; активный или пассивный), иконка — на вид предмета. Тип навыка выводится из самого навыка (`game/skill_kinds.py`). Если всё же нужен свой значок, достаточно положить `skill/<тип>/<id>.png` или `item/<слот>/<id>.png`.

## 1. Спрайты классов — листы-линейки

Все 60 классов заново, семьями (базовый класс и его повышения рядом): 19 листов. Конница и летуны шире — их на листе меньше; рост выше человека указан в строке. Пол — тот же, что у имён бойцов класса (`female_classes` в `data/names.json`).

## Линейка: первый лист

Приложить по желанию 1-2 скриншота боя UO — только как образец стиля.

```
Draw a horizontal lineup sheet of full-body unit sprites for a high-fantasy tactics RPG, standing
in one row on the same flat ground line, evenly spaced with clear empty space between them, nothing
overlapping or cropped. This sheet sets the scale and style for all later sheets of the same cast.
If screenshots are attached, use them only as a style reference and do not copy any character.

SCALE RULES: everything at exactly the same scale, as if photographed together. A normal adult human
is as tall as the first character, about 40% of the image height. Heights of the others are given in their lines relative to a human (no note = human height; a
weapon, hat or ears may rise above the head). All feet touch the same ground line near the bottom edge;
flying units hover just above it. No character is enlarged or shrunk to fill its slot.

POSE: all face right, side view with a slight three-quarter turn toward the viewer, calm combat-ready
stance, weapons held close to the body. Mounts and wings fully visible, not cut by the image edge.

FROM LEFT TO RIGHT:
<персонажи>

STYLE: hand-painted 2D fantasy character art in the spirit of the battle sprites of Vanillaware's
Unicorn Overlord (do not copy any existing character): rich painterly shading with soft light from the upper
left, clean dark contour lines, deep saturated but never neon colors, detailed cloth folds and metal highlights,
heroic realistic proportions about 7 heads tall, faces and silhouettes readable at small size. Every character
in one consistent style, palette and lighting, like one cast of the same game.

OUTPUT: transparent background PNG, no ground, no shadow, no scenery, no text, no labels.
```

## Линейка: остальные листы

Приложить готовый `assets/sprites_src/lineup/uo_01.png`.

```
Using the attached lineup sheet as the scale and style reference, draw a new horizontal lineup sheet of
full-body unit sprites of the same cast, standing in one row on the same flat ground line, evenly spaced with
clear empty space between them, nothing overlapping or cropped. Far left: the Fighter from the reference
(the first character there), unchanged and at exactly the same size.

SCALE RULES: everything at exactly the same scale, as if photographed together. A normal adult human
is as tall as that Fighter. Heights of the others are given in their lines relative to a human (no note = human height; a
weapon, hat or ears may rise above the head). All feet touch the same ground line near the bottom edge;
flying units hover just above it. No character is enlarged or shrunk to fill its slot.

POSE: all face right, side view with a slight three-quarter turn toward the viewer, calm combat-ready
stance, weapons held close to the body. Mounts and wings fully visible, not cut by the image edge.

FROM LEFT TO RIGHT:
1. The Fighter from the reference (unchanged).
<персонажи>

STYLE: hand-painted 2D fantasy character art in the spirit of the battle sprites of Vanillaware's
Unicorn Overlord (do not copy any existing character): rich painterly shading with soft light from the upper
left, clean dark contour lines, deep saturated but never neon colors, detailed cloth folds and metal highlights,
heroic realistic proportions about 7 heads tall, faces and silhouettes readable at small size. Every character
in one consistent style, palette and lighting, like one cast of the same game.

OUTPUT: transparent background PNG, no ground, no shadow, no scenery, no text, no labels.
```

## Листы линеек

**Лист 1** (`assets/sprites_src/lineup/uo_01.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_01.png fighter vanguard arbalist shieldshooter dreadnought --reference fighter`

```
1. Fighter, male: steel plate armor over blue tabard, sallet helmet, arming sword and kite shield, sturdy defensive stance.
2. Vanguard, male: heavier ornate plate with gold trim and a short blue cape, great kite shield, longsword, veteran bulwark.
3. Arbalist, male: brigandine and padded cap, heavy crossbow (arbalest) held at the hip.
4. Shieldshooter, male: heavy plate, crossbow mounted on a large greatshield, armored marksman.
5. Dreadnought, male: colossal plate armor, enormous tower greatshield and broad sword; about 115% human height.
```

**Лист 2** (`assets/sprites_src/lineup/uo_02.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_02.png _ref cleric bishop crusader valkyria --reference _ref`

```
2. Cleric, female: white and blue priest robes, hood, simple staff with a holy symbol.
3. Bishop, female: ornate white and gold vestments with tall mitre, crosier staff.
4. Crusader, male: white tabard with red cross over plate, sword and two shields (one on the arm, one on the back).
5. Valkyria, female: winged helmet, silver plate with feather motifs, sword and round shield, female warrior.
```

**Лист 3** (`assets/sprites_src/lineup/uo_03.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_03.png _ref dark_knight doom_knight --reference _ref`

```
2. Dark Knight (cavalry), female: black spiked armor on a black horse with red eyes, great axe and dark shield; about 180% human height.
3. Doom Knight (cavalry), female: massive black and crimson armor on an armored nightmare horse, huge axe; about 190% human height.
```

**Лист 4** (`assets/sprites_src/lineup/uo_04.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_04.png _ref elven_archer elven_augur elven_fencer elven_sibyl --reference _ref`

```
2. Elven Archer, male: elf in leaf-green leathers, ornate elven longbow.
3. Elven Augur, female: elf mystic in white and teal robes, ornate spear used as a staff.
4. Elven Fencer, male: elf with long ears, green and white elegant tunic, slender rapier, spellblade.
5. Elven Sibyl, female: elf seer in flowing white robes with gold leaves, crystal-tipped spear-staff.
```

**Лист 5** (`assets/sprites_src/lineup/uo_05.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_05.png _ref feathersword gladiator berserker --reference _ref`

```
2. Feathersword (flying), male: angelic knight with white feathered wings, sword and shield.
3. Gladiator, male: bare muscular torso with leather straps, single shoulder guard, big axe.
4. Berserker, male: wild hair, war paint, fur loincloth and chains, enormous double-bit axe, about 110% human height.
```

**Лист 6** (`assets/sprites_src/lineup/uo_06.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_06.png _ref gryphon_knight gryphon_master --reference _ref`

```
2. Gryphon Knight (flying), female: light armored rider on a brown gryphon with spread wings, axe; about 200% human height.
3. Gryphon Master (flying), female: rider in ornate armor on a white gryphon, big axe; about 220% human height.
```

**Лист 7** (`assets/sprites_src/lineup/uo_07.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_07.png _ref hoplite legionnaire housecarl viking --reference _ref`

```
2. Hoplite, male: full plate, crested great helm, huge tower greatshield and short spear, immovable wall.
3. Legionnaire, male: gilded heavy plate, crimson crest, tower greatshield with emblem, spear.
4. Housecarl, male: Nordic mail and fur mantle, bearded axe, round helmet with nasal, broad build.
5. Viking, male: heavier mail with fur and braided beard, round shield on the back, large bearded axe.
```

**Лист 8** (`assets/sprites_src/lineup/uo_08.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_08.png _ref hunter sniper paladin --reference _ref`

```
2. Hunter, male: green hooded cloak, leather armor, recurve bow and arrow nocked, quiver.
3. Sniper, male: dark green long coat, feathered hat, long elegant bow, cold focused gaze.
4. Paladin (cavalry), female: white and gold plate on a white barded horse, sword and shield; about 180% human height.
```

**Лист 9** (`assets/sprites_src/lineup/uo_09.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_09.png _ref knight great_knight --reference _ref`

```
2. Knight (cavalry), female: knight in blue and silver plate on an armored warhorse, lance and shield; rider and horse together about 180% of human height.
3. Great Knight (cavalry), female: heavy gilded plate on a barded warhorse with caparison, long lance and shield; about 190% human height.
```

**Лист 10** (`assets/sprites_src/lineup/uo_10.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_10.png _ref lord high_lord prince --reference _ref`

```
2. Lord, male: young noble prince in blue and silver armor with short cape, longsword and heater shield with a unicorn crest.
3. High Lord (cavalry), female: noble in gleaming royal armor on a white warhorse, sword and unicorn shield; about 180% human height.
4. Prince, male: regal young prince in a red and gold coat, rapier-like sword, no armor.
```

**Лист 11** (`assets/sprites_src/lineup/uo_11.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_11.png _ref priestess high_priestess sellsword landsknecht --reference _ref`

```
2. Priestess, female: white and gold temple dress, long veil, ornate staff with a crystal.
3. High Priestess, female: majestic white gown with gold halo crown, tall ornate staff.
4. Sellsword, male: mismatched mercenary armor, huge zweihander on the shoulder.
5. Landsknecht, male: slashed puffed doublet and plumed beret, massive zweihander, half-plate.
```

**Лист 12** (`assets/sprites_src/lineup/uo_12.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_12.png _ref radiant_knight sainted_knight --reference _ref`

```
2. Radiant Knight (cavalry), female: white and gold armor on a white horse, sword and holy shield, healer knight; about 180% human height.
3. Sainted Knight (cavalry), female: radiant white plate with halo-like crest on a white barded horse, lance; about 190% human height.
```

**Лист 13** (`assets/sprites_src/lineup/uo_13.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_13.png _ref shaman druid snow_ranger werebear --reference _ref`

```
2. Shaman, female: tribal layered robes with feathers and bones, gnarled wooden staff with charms.
3. Druid, female: green and brown robes with leaves and antler circlet, living-wood staff.
4. Snow Ranger, male: white fur cloak and hood, white longbow, snowy ranger.
5. Werebear, male: huge bear-headed beastman in heavy armor, greatshield and axe; about 125% human height.
```

**Лист 14** (`assets/sprites_src/lineup/uo_14.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_14.png _ref soldier sergeant swordfighter sword_master --reference _ref`

```
2. Soldier, male: padded gambeson and kettle hat, simple spear held upright, light infantry.
3. Sergeant, male: brigandine with rank sash, plumed kettle hat, long spear, commanding pose.
4. Swordfighter, male: light coat over a tunic, katana-like curved sword held low, nimble duelist.
5. Sword Master, male: long flowing coat, two-handed curved sword, calm master's stance.
```

**Лист 15** (`assets/sprites_src/lineup/uo_15.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_15.png _ref thief rogue warrior breaker --reference _ref`

```
2. Thief, male: dark hood and scarf, short cape, light short sword, crouched sneaky stance.
3. Rogue, male: black leather with red sash, two short swords, smirking agile stance.
4. Warrior, male: heavy armor with spiked pauldrons, great maul-axe, armor breaker.
5. Breaker, male: huge spiked plate armor, giant war hammer-axe resting on the shoulder, about 110% human height.
```

**Лист 16** (`assets/sprites_src/lineup/uo_16.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_16.png _ref werefox werelion wereowl --reference _ref`

```
2. Werefox, female: fox-headed beastwoman in light leather, spear, nimble.
3. Werelion, male: lion-headed beastman with a mane, bare chest and gold armor pieces, huge axe; about 115% human height.
4. Wereowl (flying), female: owl-winged beastwoman mage with feathered cloak, staff; wings spread.
```

**Лист 17** (`assets/sprites_src/lineup/uo_17.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_17.png _ref werewolf witch sorceress --reference _ref`

```
2. Werewolf, male: wolf-headed beastman warrior in light armor, curved sword, digitigrade legs.
3. Witch, female: dark purple dress and tattered hooded cloak, crooked staff with a green glowing charm.
4. Sorceress, female: elegant black and gold gown, tall collar, staff topped with a crescent moon.
```

**Лист 18** (`assets/sprites_src/lineup/uo_18.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_18.png _ref wizard warlock --reference _ref`

```
2. Wizard, female: deep blue robe, pointed wide hat, staff with a fire-red orb.
3. Warlock, male: black and violet robes with high collar, staff with a dark crystal, sinister.
```

**Лист 19** (`assets/sprites_src/lineup/uo_19.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_19.png _ref wyvern_knight wyvern_master --reference _ref`

```
2. Wyvern Knight (flying), female: armored rider on a small green wyvern with spread wings, spear; about 200% human height, hovering slightly above ground.
3. Wyvern Master (flying), female: heavy armored rider on a large red wyvern, long spear; about 220% human height.
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

