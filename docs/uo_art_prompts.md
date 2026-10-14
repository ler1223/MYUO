# Промпты картинок: классы, навыки и предметы Unicorn Overlord

Собрано `python tools/make_art_prompts.py` из справочника — перегенерируйте после его изменений. Промпты на английском. Запросы скрипт не делает: отправляйте вручную в ChatGPT или через `tools/gen_ui_image.py` по вашей команде.

Всего запросов: 93 (спрайты классов — 15, экран бойца — 1, значки навыков — 22, иконки предметов — 55).

## Как пользоваться

1. Листы с сеткой 5x2 (1536x1024, прозрачный фон): в начало запроса — блоки **STYLE** и **SHEET** из `docs/ui_prompts.md`, затем ячейки батча. Первой строкой — `Match the art direction of the attached screenshots, but do not copy any text, logo or exact artwork.` и 1-2 скриншота UO.
2. Готовый лист — в `assets/ui/sheets/` под именем батча и нарезка: `python tools/cut_ui_sheet.py <номер> --force` (батчи 11+ ищутся в этом файле).
3. Спрайты классов — листы-линейки (раздел 1): общий промпт листа из `docs/art_prompts.md`, раздел 1, плюс строки персонажей; лист — в `assets/sprites_src/lineup/` и `python tools/cut_lineup.py ...` (команда у каждого листа). Свой спрайт сразу заменяет временный похожий.
4. Иконки и значки без своего файла берут общую заглушку, поэтому рисовать можно в любом порядке.

## 1. Спрайты классов — листы-линейки

60 классов, по 4 на лист после эталона-паладина: 15 запросов. Конница и летуны выше человека — рост указан в строке.

**Лист 1** (`assets/sprites_src/lineup/uo_01.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_01.png _ref arbalist berserker bishop breaker --reference _ref`

```
2. Arbalist: brigandine and padded cap, heavy crossbow (arbalest) held at the hip.
3. Berserker: wild hair, war paint, fur loincloth and chains, enormous double-bit axe, about 110% human height.
4. Bishop: ornate white and gold vestments with tall mitre, crosier staff.
5. Breaker: huge spiked plate armor, giant war hammer-axe resting on the shoulder, about 110% human height.
```

**Лист 2** (`assets/sprites_src/lineup/uo_02.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_02.png _ref cleric crusader dark_knight doom_knight --reference _ref`

```
2. Cleric: white and blue priest robes, hood, simple staff with a holy symbol.
3. Crusader: white tabard with red cross over plate, sword and two shields (one on the arm, one on the back).
4. Dark Knight (cavalry): black spiked armor on a black horse with red eyes, great axe and dark shield; about 180% human height.
5. Doom Knight (cavalry): massive black and crimson armor on an armored nightmare horse, huge axe; about 190% human height.
```

**Лист 3** (`assets/sprites_src/lineup/uo_03.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_03.png _ref dreadnought druid elven_archer elven_augur --reference _ref`

```
2. Dreadnought: colossal plate armor, enormous tower greatshield and broad sword; about 115% human height.
3. Druid: green and brown robes with leaves and antler circlet, living-wood staff.
4. Elven Archer: elf in leaf-green leathers, ornate elven longbow.
5. Elven Augur: elf mystic in white and teal robes, ornate spear used as a staff.
```

**Лист 4** (`assets/sprites_src/lineup/uo_04.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_04.png _ref elven_fencer elven_sibyl feathersword fighter --reference _ref`

```
2. Elven Fencer: elf with long ears, green and white elegant tunic, slender rapier, spellblade.
3. Elven Sibyl: elf seer in flowing white robes with gold leaves, crystal-tipped spear-staff.
4. Feathersword (flying): angelic knight with white feathered wings, sword and shield.
5. Fighter: steel plate armor over blue tabard, sallet helmet, arming sword and kite shield, sturdy defensive stance.
```

**Лист 5** (`assets/sprites_src/lineup/uo_05.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_05.png _ref gladiator great_knight gryphon_knight gryphon_master --reference _ref`

```
2. Gladiator: bare muscular torso with leather straps, single shoulder guard, big axe.
3. Great Knight (cavalry): heavy gilded plate on a barded warhorse with caparison, long lance and shield; about 190% human height.
4. Gryphon Knight (flying): light armored rider on a brown gryphon with spread wings, axe; about 200% human height.
5. Gryphon Master (flying): rider in ornate armor on a white gryphon, big axe; about 220% human height.
```

**Лист 6** (`assets/sprites_src/lineup/uo_06.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_06.png _ref high_lord high_priestess hoplite housecarl --reference _ref`

```
2. High Lord (cavalry): noble in gleaming royal armor on a white warhorse, sword and unicorn shield; about 180% human height.
3. High Priestess: majestic white gown with gold halo crown, tall ornate staff.
4. Hoplite: full plate, crested great helm, huge tower greatshield and short spear, immovable wall.
5. Housecarl: Nordic mail and fur mantle, bearded axe, round helmet with nasal, broad build.
```

**Лист 7** (`assets/sprites_src/lineup/uo_07.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_07.png _ref hunter knight landsknecht legionnaire --reference _ref`

```
2. Hunter: green hooded cloak, leather armor, recurve bow and arrow nocked, quiver.
3. Knight (cavalry): knight in blue and silver plate on an armored warhorse, lance and shield; rider and horse together about 180% of human height.
4. Landsknecht: slashed puffed doublet and plumed beret, massive zweihander, half-plate.
5. Legionnaire: gilded heavy plate, crimson crest, tower greatshield with emblem, spear.
```

**Лист 8** (`assets/sprites_src/lineup/uo_08.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_08.png _ref lord paladin priestess prince --reference _ref`

```
2. Lord: young noble prince in blue and silver armor with short cape, longsword and heater shield with a unicorn crest.
3. Paladin (cavalry): white and gold plate on a white barded horse, sword and shield; about 180% human height.
4. Priestess: white and gold temple dress, long veil, ornate staff with a crystal.
5. Prince: regal young prince in a red and gold coat, rapier-like sword, no armor.
```

**Лист 9** (`assets/sprites_src/lineup/uo_09.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_09.png _ref radiant_knight rogue sainted_knight sellsword --reference _ref`

```
2. Radiant Knight (cavalry): white and gold armor on a white horse, sword and holy shield, healer knight; about 180% human height.
3. Rogue: black leather with red sash, two short swords, smirking agile stance.
4. Sainted Knight (cavalry): radiant white plate with halo-like crest on a white barded horse, lance; about 190% human height.
5. Sellsword: mismatched mercenary armor, huge zweihander on the shoulder.
```

**Лист 10** (`assets/sprites_src/lineup/uo_10.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_10.png _ref sergeant shaman shieldshooter sniper --reference _ref`

```
2. Sergeant: brigandine with rank sash, plumed kettle hat, long spear, commanding pose.
3. Shaman: tribal layered robes with feathers and bones, gnarled wooden staff with charms.
4. Shieldshooter: heavy plate, crossbow mounted on a large greatshield, armored marksman.
5. Sniper: dark green long coat, feathered hat, long elegant bow, cold focused gaze.
```

**Лист 11** (`assets/sprites_src/lineup/uo_11.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_11.png _ref snow_ranger soldier sorceress sword_master --reference _ref`

```
2. Snow Ranger: white fur cloak and hood, white longbow, snowy ranger.
3. Soldier: padded gambeson and kettle hat, simple spear held upright, light infantry.
4. Sorceress: elegant black and gold gown, tall collar, staff topped with a crescent moon.
5. Sword Master: long flowing coat, two-handed curved sword, calm master's stance.
```

**Лист 12** (`assets/sprites_src/lineup/uo_12.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_12.png _ref swordfighter thief valkyria vanguard --reference _ref`

```
2. Swordfighter: light coat over a tunic, katana-like curved sword held low, nimble duelist.
3. Thief: dark hood and scarf, short cape, light short sword, crouched sneaky stance.
4. Valkyria: winged helmet, silver plate with feather motifs, sword and round shield, female warrior.
5. Vanguard: heavier ornate plate with gold trim and a short blue cape, great kite shield, longsword, veteran bulwark.
```

**Лист 13** (`assets/sprites_src/lineup/uo_13.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_13.png _ref viking warlock warrior werebear --reference _ref`

```
2. Viking: heavier mail with fur and braided beard, round shield on the back, large bearded axe.
3. Warlock: black and violet robes with high collar, staff with a dark crystal, sinister.
4. Warrior: heavy armor with spiked pauldrons, great maul-axe, armor breaker.
5. Werebear: huge bear-headed beastman in heavy armor, greatshield and axe; about 125% human height.
```

**Лист 14** (`assets/sprites_src/lineup/uo_14.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_14.png _ref werefox werelion wereowl werewolf --reference _ref`

```
2. Werefox: fox-headed beastwoman in light leather, spear, nimble.
3. Werelion: lion-headed beastman with a mane, bare chest and gold armor pieces, huge axe; about 115% human height.
4. Wereowl (flying): owl-winged beastwoman mage with feathered cloak, staff; wings spread.
5. Werewolf: wolf-headed beastman warrior in light armor, curved sword, digitigrade legs.
```

**Лист 15** (`assets/sprites_src/lineup/uo_15.png`): `python tools/cut_lineup.py assets/sprites_src/lineup/uo_15.png _ref witch wizard wyvern_knight wyvern_master --reference _ref`

```
2. Witch: dark purple dress and tattered hooded cloak, crooked staff with a green glowing charm.
3. Wizard: deep blue robe, pointed wide hat, staff with a fire-red orb.
4. Wyvern Knight (flying): armored rider on a small green wyvern with spread wings, spear; about 200% human height, hovering slightly above ground.
5. Wyvern Master (flying): heavy armored rider on a large red wyvern, long spear; about 220% human height.
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

## 3. Значки навыков и пассивок

213 значков, 22 листов. Ячейка: круглый значок 200x200 внутри кольца (кольцо рисует интерфейс — рисовать только сам символ на тёмном круге). Красноватые тона — физические, синие и фиолетовые — магия, золотые — лечение и защита.

## Батч 12 — значки навыков (`b12_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round active skill icon, 200x200, "Active Steal": Attack a single enemy. Steal 1 of the enemy's AP. (Does not apply if they guard the first hit.). A single bold symbol on a dark round field, no ring, no text.
Cell 2: round active skill icon, 200x200, "Aerial Smite": Attack a row of enemies. Cavalry targets cannot guard against this attack. Grants the user -1 AP if a target is at 100% HP. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round active skill icon, 200x200, "Assaulting Blow": Attack a single enemy. Grants the user +1 AP if the target is defeated. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round active skill icon, 200x200, "Assaulting Lance": Attacks a single enemy. Grants the user +1AP if the target is defeated. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round active skill icon, 200x200, "Attack": a fitting emblem. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round active skill icon, 200x200, "Aurora Veil": Grants HP regeneration to a row of allies. Grants targets +50 Mag. Defense. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round active skill icon, 200x200, "Banishing Stab": Attack a single enemy. Remove all of the target's buff. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round active skill icon, 200x200, "Bastard's Cross": Attack a single enemy. Potency increases based on the target's HP. (Maximum increases: +60.). A single bold symbol on a dark round field, no ring, no text.
Cell 9: round active skill icon, 200x200, "Bear Crush": Attack a single enemy. Inflicts Stun. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round active skill icon, 200x200, "Brandish": Attack a single enemy. Ignores 50% of the target's Defense. Grants the user +1 PP if the attack hits. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `skill/active_steal.png` | 256x256 |
| 2 | `skill/aerial_smite.png` | 256x256 |
| 3 | `skill/assaulting_blow.png` | 256x256 |
| 4 | `skill/assaulting_lance.png` | 256x256 |
| 5 | `skill/attack.png` | 256x256 |
| 6 | `skill/aurora_veil.png` | 256x256 |
| 7 | `skill/banishing_stab.png` | 256x256 |
| 8 | `skill/bastards_cross.png` | 256x256 |
| 9 | `skill/bear_crush.png` | 256x256 |
| 10 | `skill/brandish.png` | 256x256 |

## Батч 13 — значки навыков (`b13_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round active skill icon, 200x200, "Cavalry Slayer": Attack a single enemy. Inflicts AP -1, PP -1, and Guard Seal if the target is cavalry. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round active skill icon, 200x200, "Compounding Curse": Make debuffs 1.5x more effective for a row of enemies. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round active skill icon, 200x200, "Curing Call": Restore minor HP to a row of allies. Removes all of target's debuff. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round active skill icon, 200x200, "Dark Flame": Consumes 30% of own HP to attack a row of enemies. +50 potency v. debuffed targets. Inflitcts Burn. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round active skill icon, 200x200, "Decimate": Attack a single enemy. Potency increases the fewer enemies there are. (Maximum increase: +100.). A single bold symbol on a dark round field, no ring, no text.
Cell 6: round active skill icon, 200x200, "Defender": Attacks a single enemy. Grants the user 50% Phys. Defense. Grants the user +1 PP if this attacks hits. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round active skill icon, 200x200, "Defensive Curse": Inflicts Phys. Attack -50%, Mag. Attack -50%, and Guard Seal on a row of enemies. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round active skill icon, 200x200, "Defensive Order": Grants all allies +20% Defense. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round active skill icon, 200x200, "Divine Cross": Attacks a single enemy and remove all buffs. Grants the user +1 PP if the target is defeated. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round active skill icon, 200x200, "Diving Thrust": Attack a single enemy. Cavalry targets cannot guard against this attack. +50 potency v. cavalry targets. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `skill/cavalry_slayer.png` | 256x256 |
| 2 | `skill/compounding_curse.png` | 256x256 |
| 3 | `skill/curing_call.png` | 256x256 |
| 4 | `skill/dark_flame.png` | 256x256 |
| 5 | `skill/decimate.png` | 256x256 |
| 6 | `skill/defender.png` | 256x256 |
| 7 | `skill/defensive_curse.png` | 256x256 |
| 8 | `skill/defensive_order.png` | 256x256 |
| 9 | `skill/divine_cross.png` | 256x256 |
| 10 | `skill/diving_thrust.png` | 256x256 |

## Батч 14 — значки навыков (`b14_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round active skill icon, 200x200, "Dual Shot": Attack two enemies. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round active skill icon, 200x200, "Earthshaker": Attack all enemies. Damage increases the less HP the user has. {Maximum increase: +75.). A single bold symbol on a dark round field, no ring, no text.
Cell 3: round active skill icon, 200x200, "Elemental Roar": Attak all enemies. Potency increases with faerie count (+30 per faerie). This dismisses all summoned faeries. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round active skill icon, 200x200, "Fatal Dive": Attack a column of enemies with a piercing strike. Deals damage equal to 50% of the user's HP. (This attack cannot be a critcal.). A single bold symbol on a dark round field, no ring, no text.
Cell 5: round active skill icon, 200x200, "Finishing Stab": Attack a single enemy. Grants the user +50% Phys. Attack if the target is defeated. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round active skill icon, 200x200, "Fire Breath": Attack a row of enemies. Inflicts Burn. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round active skill icon, 200x200, "Fireball": Attack a single enemy with magick. Inflicts Burn. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round active skill icon, 200x200, "Glacial Rain": Attack all enemies. Inflicts Freeze. (User cannot evade or use passive skills while charging.). A single bold symbol on a dark round field, no ring, no text.
Cell 9: round active skill icon, 200x200, "Grand Smash": Attack all enemies. +50 potency if the user is at 100% HP. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round active skill icon, 200x200, "Greatshield": Grants the user +50% Phys. Defense and +2 PP. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `skill/dual_shot.png` | 256x256 |
| 2 | `skill/earthshaker.png` | 256x256 |
| 3 | `skill/elemental_roar.png` | 256x256 |
| 4 | `skill/fatal_dive.png` | 256x256 |
| 5 | `skill/finishing_stab.png` | 256x256 |
| 6 | `skill/fire_breath.png` | 256x256 |
| 7 | `skill/fireball.png` | 256x256 |
| 8 | `skill/glacial_rain.png` | 256x256 |
| 9 | `skill/grand_smash.png` | 256x256 |
| 10 | `skill/greatshield.png` | 256x256 |

## Батч 15 — значки навыков (`b15_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round active skill icon, 200x200, "Hache": Attack a single enemy. Grants the user +1PP PP if this attacks hits. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round active skill icon, 200x200, "Heal": Restore moderate HP to an ally. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round active skill icon, 200x200, "Heavy Bolt": Attack a single enemy. +100 potency if the user is in the front row. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round active skill icon, 200x200, "Heavy Slash": Attack a single enemy. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round active skill icon, 200x200, "Heavy Smash": Attack a single enemy. Ignores 100% Defense v. armored targets. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round active skill icon, 200x200, "High Swing": Attack a row of enemies. Cavalry targets cannot guard against this attack. +50 potency v. cavalry targets. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round active skill icon, 200x200, "Holy Light": Attack a single enemy with magick. Removes all of target's buffs. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round active skill icon, 200x200, "Honed Slash": Attack a single enemy. Becomes a truestrike if the user if buffed. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round active skill icon, 200x200, "Honed Spear": Attack a column of enemies with a piercing strike. +50 potency if the user if buffed. Cavalry targets cannot guard against this attack. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round active skill icon, 200x200, "Ice Coffin": Attack a row enemies with magick. Inflicts Freeze. +50 potency v. frozen targets. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `skill/hache.png` | 256x256 |
| 2 | `skill/heal.png` | 256x256 |
| 3 | `skill/heavy_bolt.png` | 256x256 |
| 4 | `skill/heavy_slash.png` | 256x256 |
| 5 | `skill/heavy_smash.png` | 256x256 |
| 6 | `skill/high_swing.png` | 256x256 |
| 7 | `skill/holy_light.png` | 256x256 |
| 8 | `skill/honed_slash.png` | 256x256 |
| 9 | `skill/honed_spear.png` | 256x256 |
| 10 | `skill/ice_coffin.png` | 256x256 |

## Батч 16 — значки навыков (`b16_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round active skill icon, 200x200, "Icebolt": Attack a single enemy with magick. Inflicts Freeze. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round active skill icon, 200x200, "Icicle Arrow": Attack two enemies. Inflicts Freeze. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round active skill icon, 200x200, "Impale": Attacks a single enemy. Grants the user +1PPPP if the target is defeated. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round active skill icon, 200x200, "Innocent Ray": Attack a row of enemies with magick. Removes all of target's buffs. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round active skill icon, 200x200, "Iron Crusher": Attack a single enemy. Ignores 50% Defense v. armored targets. +50 potency v. armored targets. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round active skill icon, 200x200, "Javelin": Attack a single enemy. Grants +50 potency v. flying targets. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round active skill icon, 200x200, "Keen Edge": Attack a single enemy with a critical strike. (Critical rate+50%.). A single bold symbol on a dark round field, no ring, no text.
Cell 8: round active skill icon, 200x200, "Killing Chain": Attack a single enemy. Grants the user +1AP if the target is defeated. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round active skill icon, 200x200, "Lean Edge": Attack a single enemy. Recover 25% HP if the attack hits. Recover 25% HP if the target is defeated. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round active skill icon, 200x200, "Lightning Blade": Attack a single enemy. Inflicts Stun. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `skill/icebolt.png` | 256x256 |
| 2 | `skill/icicle_arrow.png` | 256x256 |
| 3 | `skill/impale.png` | 256x256 |
| 4 | `skill/innocent_ray.png` | 256x256 |
| 5 | `skill/iron_crusher.png` | 256x256 |
| 6 | `skill/javelin.png` | 256x256 |
| 7 | `skill/keen_edge.png` | 256x256 |
| 8 | `skill/killing_chain.png` | 256x256 |
| 9 | `skill/lean_edge.png` | 256x256 |
| 10 | `skill/lightning_blade.png` | 256x256 |

## Батч 17 — значки навыков (`b17_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round active skill icon, 200x200, "Long Thrust": Attack a column of enemies with a piercing strike. Cavalry targets cannot guard against this attack. Grants +50 potency v. cavalry targets. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round active skill icon, 200x200, "Magick Missile": Attack two enemies with magick. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round active skill icon, 200x200, "Magick Wall": Grants the user a buff that negates one magick attack or one affliction. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round active skill icon, 200x200, "Meteor Slash": Attacks a single enemy with a critical flurry. (Critical rate +30%.). A single bold symbol on a dark round field, no ring, no text.
Cell 5: round active skill icon, 200x200, "Mirage Stab": Attack a row of enemies. Grants the user the ability to evade one attack. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round active skill icon, 200x200, "Mounting Charge": Restore 30% HP to the user. Grants the user +30% Phys. Attack. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round active skill icon, 200x200, "Mystic Arrow": Attack a single enemy. Deals additional magick attack of 100 potenecy to armored targets. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round active skill icon, 200x200, "Nature’s Wrath": Attack a column of enemies with piercing magic. Inflicts -1PP PP to cavalry targets. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round active skill icon, 200x200, "Night Vision": Grants a row of allies +50 Accuracy. At night, makes the targets' next attack a truestrike. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round active skill icon, 200x200, "Offensive Curse": Inflicts Phys. Attack -50% and Mag. Attack -50% on a row of enemies. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `skill/long_thrust.png` | 256x256 |
| 2 | `skill/magick_missile.png` | 256x256 |
| 3 | `skill/magick_wall.png` | 256x256 |
| 4 | `skill/meteor_slash.png` | 256x256 |
| 5 | `skill/mirage_stab.png` | 256x256 |
| 6 | `skill/mounting_charge.png` | 256x256 |
| 7 | `skill/mystic_arrow.png` | 256x256 |
| 8 | `skill/natures_wrath.png` | 256x256 |
| 9 | `skill/night_vision.png` | 256x256 |
| 10 | `skill/offensive_curse.png` | 256x256 |

## Батч 18 — значки навыков (`b18_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round active skill icon, 200x200, "Offensive Order": Grants all allies +20% Attack. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round active skill icon, 200x200, "Omega Shatter": Attack a single enemy. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round active skill icon, 200x200, "Passive Curse": Inflicts PP -1 and Initiative -10 on a row of enemies. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round active skill icon, 200x200, "Passive Hold": Attack a single enemy. Inflicts Passive Seal. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round active skill icon, 200x200, "Passive Steal": Attacks a single enemy. Steal all of the enemy's PP. (Does not apply if they guard the first hit.). A single bold symbol on a dark round field, no ring, no text.
Cell 6: round active skill icon, 200x200, "Penetrate": Attacks a column of enemies with a piercing strike. Inflicts Phys. Defense -30%. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round active skill icon, 200x200, "Piercing Lance": Attack a single enemy. Inflicts Guard Seal. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round active skill icon, 200x200, "Pile Thrust": Attacks a single target with multiple hits. Grants the user +1AP if the target is defeated. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round active skill icon, 200x200, "Power Bolt": Attack a single enemy. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round active skill icon, 200x200, "Primus Edge": Attack a single enemy. If the user is at 100% HP, grants the user +1 PP and +1 summoned faeries. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `skill/offensive_order.png` | 256x256 |
| 2 | `skill/omega_shatter.png` | 256x256 |
| 3 | `skill/passive_curse.png` | 256x256 |
| 4 | `skill/passive_hold.png` | 256x256 |
| 5 | `skill/passive_steal.png` | 256x256 |
| 6 | `skill/penetrate.png` | 256x256 |
| 7 | `skill/piercing_lance.png` | 256x256 |
| 8 | `skill/pile_thrust.png` | 256x256 |
| 9 | `skill/power_bolt.png` | 256x256 |
| 10 | `skill/primus_edge.png` | 256x256 |

## Батч 19 — значки навыков (`b19_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round active skill icon, 200x200, "Rolling Axe": Attack a row of enemies with multiple hits. Inflicts Phys. Defense -15%. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round active skill icon, 200x200, "Round Swing": Attack a row of enemies. Damage increases the more HP the user has. {Maximum increase: +50.). A single bold symbol on a dark round field, no ring, no text.
Cell 3: round active skill icon, 200x200, "Row Protection": Grants allies in the user's row +50% Phys. Defense. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round active skill icon, 200x200, "Row Shot": Attack a row of enemies. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round active skill icon, 200x200, "Row Smash": Attack a row of enemies. Ignores 100% Defense v. armored targets. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round active skill icon, 200x200, "Saint's Blade": Attack a single enemy. +25 potency if the user is at 100% HP. Grants the user +1PP PP if this attacks hits. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round active skill icon, 200x200, "Shadowbite": Attack a row of enemies. Inflicts Blindness. Inflicts Initiative -20 and Evasion -20. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round active skill icon, 200x200, "Shield Bash": Attacks a single enemy. Inflicts Stun. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round active skill icon, 200x200, "Shield Smite": Attack a single enemy. Inflicts Defense -20%. Grants the user +20% Defense. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round active skill icon, 200x200, "Single Shot": Attack a single enemy. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `skill/rolling_axe.png` | 256x256 |
| 2 | `skill/round_swing.png` | 256x256 |
| 3 | `skill/row_protection.png` | 256x256 |
| 4 | `skill/row_shot.png` | 256x256 |
| 5 | `skill/row_smash.png` | 256x256 |
| 6 | `skill/saints_blade.png` | 256x256 |
| 7 | `skill/shadowbite.png` | 256x256 |
| 8 | `skill/shield_bash.png` | 256x256 |
| 9 | `skill/shield_smite.png` | 256x256 |
| 10 | `skill/single_shot.png` | 256x256 |

## Батч 20 — значки навыков (`b20_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round active skill icon, 200x200, "Slice": Attacks a single enemy. Grants the user +1 PP if the target is defeated. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round active skill icon, 200x200, "Smash": Attack a single enemy. Inflicts Phys. Defense -20%. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round active skill icon, 200x200, "Sonic Shaft": Attack a single enemy. Deals 100% of target's Initiative in additional damage. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round active skill icon, 200x200, "Spinning Edge": Attack a row of enemies. Ignores 50% of the target's Defense. Grants the user +1 PP if a target is defeated. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round active skill icon, 200x200, "Spiral Sword": Attack a single enemy. Inflicts Evasion -20. Grants the user +20 Evasion. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round active skill icon, 200x200, "Sting": Attacks a single enemy. +50 potency if the user is below 50% HP. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round active skill icon, 200x200, "Sylphic Wind": Attack a row of enemies with magick. +20 potency v. flying targets. Grants the user +1 summoned faeries. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round active skill icon, 200x200, "Tempest Drive": Attack a column of enemies with a piercing strike. Cavalry targets cannot guard against this attack. Becomes a truestrike and critical if user is belo. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round active skill icon, 200x200, "Toxic Bolt": Attack a single enemy. Inflicts Poison. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round active skill icon, 200x200, "Toxic Throw": Attack a single enemy. Inflicts Poison. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `skill/slice.png` | 256x256 |
| 2 | `skill/smash.png` | 256x256 |
| 3 | `skill/sonic_shaft.png` | 256x256 |
| 4 | `skill/spinning_edge.png` | 256x256 |
| 5 | `skill/spiral_sword.png` | 256x256 |
| 6 | `skill/sting.png` | 256x256 |
| 7 | `skill/sylphic_wind.png` | 256x256 |
| 8 | `skill/tempest_drive.png` | 256x256 |
| 9 | `skill/toxic_bolt.png` | 256x256 |
| 10 | `skill/toxic_throw.png` | 256x256 |

## Батч 21 — значки навыков (`b21_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round active skill icon, 200x200, "Vengeful Axe": Attacks a single enemy. Damage increases the less HP the user has. (Maximum increase: +100.). A single bold symbol on a dark round field, no ring, no text.
Cell 2: round active skill icon, 200x200, "Venom Axe": Attack a single enemy. Inflicts Poison. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round active skill icon, 200x200, "Venom Thrust": Attack a column of enemies with a piercing strike. Inflicts Poison and debuffs target HP recovery by -50%. +50 potency v. poisoned targets. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round active skill icon, 200x200, "Vertical Edge": Attack a single enemy. Becomes a truestrike, ignores 50% defense, and +50 potency v. flying targets. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round active skill icon, 200x200, "Volcano": Attack a column of enemies with piercing magick. Inflicts Burn. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round active skill icon, 200x200, "Wall": Grants the user a buff that negates one physickal attack. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round active skill icon, 200x200, "Warding Slash": Attacks a single enemy. Grants the user +20% Phys. Defense. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round active skill icon, 200x200, "Wide Breaker": Attack a row of enemies. Inflicts Phys. Defense -30% . +50 potency v. debuffed targets. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round active skill icon, 200x200, "Wide Smash": Attack a row of enemies. +50 potency if the user is at 100% HP. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round active skill icon, 200x200, "Wild Fang": Attack a row of enemies. Potency increases the less HP a target has. (Maximum increase: +50.). A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `skill/vengeful_axe.png` | 256x256 |
| 2 | `skill/venom_axe.png` | 256x256 |
| 3 | `skill/venom_thrust.png` | 256x256 |
| 4 | `skill/vertical_edge.png` | 256x256 |
| 5 | `skill/volcano.png` | 256x256 |
| 6 | `skill/wall.png` | 256x256 |
| 7 | `skill/warding_slash.png` | 256x256 |
| 8 | `skill/wide_breaker.png` | 256x256 |
| 9 | `skill/wide_smash.png` | 256x256 |
| 10 | `skill/wild_fang.png` | 256x256 |

## Батч 22 — значки навыков (`b22_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round active skill icon, 200x200, "Wild Rush": Attack a column of enemies with a piercing strike. Inflitcts Stun. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round active skill icon, 200x200, "Wind Arrow": Attack a single enemy. Inflicts Evasion -50. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round passive skill icon, 200x200, "Accelerate": Activates after an enemy attacks with an active skill. Grants the user +20 Initiative and +20 Accuracy. (Effect stacks.). A single bold symbol on a dark round field, no ring, no text.
Cell 4: round passive skill icon, 200x200, "Active Gift": Activates after an ally uses an active skill. Grants an ally +1 AP. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round passive skill icon, 200x200, "Aerial Guard": Activates before being hit by a physickal attack. Block an enemy attack with a medium guard. Becomes a heavy guard and grants the user +1 PP if the en. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round passive skill icon, 200x200, "Aerial Snipe": Activates after an ally is hit by an attack. Counterattack a single enemy. +100 potency v. flying targets. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round passive skill icon, 200x200, "Aid Cover": Activates before an ally is attacked. Cover an ally with a medium guard. Restores 25% HP to that ally. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round passive skill icon, 200x200, "Arrow Cover": Activates before an ally is hit by a ranged phys. attack. Cover an ally and nullify all damage. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round passive skill icon, 200x200, "Berserk": Activates before attacking with an active skill. Consume all PP to grant the user +1 AP. The user will survive one lethal blow. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round passive skill icon, 200x200, "Bestral Guard": Activates before being hit by a physickal attack. Block an enemy attack with a medium guard. Becomes a heavy guard and grants the user +1 PP if the en. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `skill/wild_rush.png` | 256x256 |
| 2 | `skill/wind_arrow.png` | 256x256 |
| 3 | `passive/accelerate.png` | 256x256 |
| 4 | `passive/active_gift.png` | 256x256 |
| 5 | `passive/aerial_guard.png` | 256x256 |
| 6 | `passive/aerial_snipe.png` | 256x256 |
| 7 | `passive/aid_cover.png` | 256x256 |
| 8 | `passive/arrow_cover.png` | 256x256 |
| 9 | `passive/berserk.png` | 256x256 |
| 10 | `passive/bestral_guard.png` | 256x256 |

## Батч 23 — значки навыков (`b23_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round passive skill icon, 200x200, "Bestral Howl": Activates before attacking with an active skill. Grants allies in the user's row +15% Phys. Attack. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round passive skill icon, 200x200, "Binding Guard": Activates before attacking with an active skill. User's next attack will inflict Guard Seal. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round passive skill icon, 200x200, "Boon of the Faeries": Activates at the start of a battle. Restore moderate HP to a row of allies. Grants a buff that negates a single debuff. Grants the user +1 summoned fa. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round passive skill icon, 200x200, "Bulk Up": Activates after being hit by an attack. Recover 40% HP. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round passive skill icon, 200x200, "Bull Force": Activates after using an active skill. Grants the user +1AP AP, +20% Phys. Attack, and +20 Initiative. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round passive skill icon, 200x200, "Cavalier Call": Activates before attacking with an active skill. Grants cavalry allies in the user's row +20% Attack. (Effect stacks). A single bold symbol on a dark round field, no ring, no text.
Cell 7: round passive skill icon, 200x200, "Cavalry Guard": Activates before being hit by a physickal attack. Block an enemy attack with a medium guard. Becomes a heavy guard and grants the user +1 PP if the en. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round passive skill icon, 200x200, "Charged Impetus": Activates after using an active skill. Grants the user +1APAP and +50% Critical damage. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round passive skill icon, 200x200, "Circle Barrier": Activates before an ally is attacked. Reduce damage taken by all allies by 25% for one attack. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round passive skill icon, 200x200, "Concentrate": Activates after using an active skill. Grants the user +1 AP and +40 Accuracy. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `passive/bestral_howl.png` | 256x256 |
| 2 | `passive/binding_guard.png` | 256x256 |
| 3 | `passive/boon_of_the_faeries.png` | 256x256 |
| 4 | `passive/bulk_up.png` | 256x256 |
| 5 | `passive/bull_force.png` | 256x256 |
| 6 | `passive/cavalier_call.png` | 256x256 |
| 7 | `passive/cavalry_guard.png` | 256x256 |
| 8 | `passive/charged_impetus.png` | 256x256 |
| 9 | `passive/circle_barrier.png` | 256x256 |
| 10 | `passive/concentrate.png` | 256x256 |

## Батч 24 — значки навыков (`b24_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round passive skill icon, 200x200, "Curing Heal": Activates after an ally is hit by an attack. Restore minor HP to an ally. Remove all of their debuffs. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round passive skill icon, 200x200, "Cursed Swamp": Activates at the start of a battle. Inflicts Initiative -10 and Evasion -30 on all enemies. Inflicts PP -1 to cavalry targets. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round passive skill icon, 200x200, "Deflect": Activates before being hit by a melee attack. Negate melee damage for a single hit. Grants the user +20 Evasion. (Effect stacks.). A single bold symbol on a dark round field, no ring, no text.
Cell 4: round passive skill icon, 200x200, "Demonic Pact": Activates after using an active skill. Sacrifice 25% HP to grant user +1 AP. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round passive skill icon, 200x200, "Discharge": Activates before attacking with an active skill. Consume all of the user's buffs and increases attack power for one attack. (Number of consumed buffs. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round passive skill icon, 200x200, "Diurnal Guard": Activates before being hit by a physickal attack. Block an enemy attack with a medium guard. Grants the user +1 PP during the day. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round passive skill icon, 200x200, "Divine Blessing": Activates at the start of a battle. Grants all allies HP regeneration and +10% Defense. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round passive skill icon, 200x200, "Dragon's Roar": Activates at the start of a battle. Inflicts Initiative -20 on all enemies. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round passive skill icon, 200x200, "Eagle Eye": Activates before attacking with an active skill. Makes the user's next attack a truestrike. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round passive skill icon, 200x200, "Eagle's Eye": Activates before attacking with an active skill. Makes the user's next attack a truestrike. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `passive/curing_heal.png` | 256x256 |
| 2 | `passive/cursed_swamp.png` | 256x256 |
| 3 | `passive/deflect.png` | 256x256 |
| 4 | `passive/demonic_pact.png` | 256x256 |
| 5 | `passive/discharge.png` | 256x256 |
| 6 | `passive/diurnal_guard.png` | 256x256 |
| 7 | `passive/divine_blessing.png` | 256x256 |
| 8 | `passive/dragons_roar.png` | 256x256 |
| 9 | `passive/eagle_eye.png` | 256x256 |
| 10 | `passive/eagles_eye.png` | 256x256 |

## Батч 25 — значки навыков (`b25_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round passive skill icon, 200x200, "Elemental Impetus": Activates after using an active skill. Grants the user +1 AP +1 summoned faeries. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round passive skill icon, 200x200, "Enduring Guard": Activates before being hit by a physickal attack. Block an enemy attack with a heavy guard. Grants the user a buff to endure one lethal blow. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round passive skill icon, 200x200, "Enrage": Activates after an ally is hit by an attack. Grants the user +20% Attack and +20% Accuracy. (Effect stacks.). A single bold symbol on a dark round field, no ring, no text.
Cell 4: round passive skill icon, 200x200, "Evade": Activates before being attacked. Evade a single hit. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round passive skill icon, 200x200, "Evasive Impetus": Activates after evading an attack. Grants the user +1 AP. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round passive skill icon, 200x200, "Feathering": Activates before attacking with an active skill. Grants allies in the user's row +15 Initiative. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round passive skill icon, 200x200, "First Aid": Activates at the end of a battle. Restore 25% HP to an ally. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round passive skill icon, 200x200, "Focus Sight": Activates before an ally attacks (Active). Make an ally's next attack a truestrike. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round passive skill icon, 200x200, "Following Slash": Activates after an ally is hit by an attack. Counterattack a single enemy. Grants the user +1PP PP if the attack hits. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round passive skill icon, 200x200, "Frenzied Strike": Activates after an ally is hit by an attack. Counterattack a single enemy. Inflicts Phys. Defense -15%. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `passive/elemental_impetus.png` | 256x256 |
| 2 | `passive/enduring_guard.png` | 256x256 |
| 3 | `passive/enrage.png` | 256x256 |
| 4 | `passive/evade.png` | 256x256 |
| 5 | `passive/evasive_impetus.png` | 256x256 |
| 6 | `passive/feathering.png` | 256x256 |
| 7 | `passive/first_aid.png` | 256x256 |
| 8 | `passive/focus_sight.png` | 256x256 |
| 9 | `passive/following_slash.png` | 256x256 |
| 10 | `passive/frenzied_strike.png` | 256x256 |

## Батч 26 — значки навыков (`b26_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round passive skill icon, 200x200, "Ground Counter": Activates after an enemy attacks with an active skill. Counterattack a single enemy. +100 potency v. cavalry targets. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round passive skill icon, 200x200, "Gryphon Glide": Activates before being hit by a ranged attack. Evades a single hit of a ranged attack. Grants the user +1 AP. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round passive skill icon, 200x200, "Guard Order": Activates before an ally is attacked. Grants a row of allies +100% Guard Rate for one attack. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round passive skill icon, 200x200, "Guardian": Activates after being hit by a physickal attack. Grants the user +20% Phys. Defense and +20% Guard Rate. (Effect stacks.). A single bold symbol on a dark round field, no ring, no text.
Cell 5: round passive skill icon, 200x200, "Hastened Cover": Activates before an ally is attacked. Cover an ally with a medium guard. Grants that ally max Initiative for their next action. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round passive skill icon, 200x200, "Hastened Strike": Activates at the start of a battle. Attack a single enemy with a first strike. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round passive skill icon, 200x200, "Hawk Eye": Activates before attacking with an active skill. Makes the user's next attack a truestrike and guaranteed critical. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round passive skill icon, 200x200, "Heavy Counter": Activates after an enemy attacks with an active skill. Counterattack a single enemy. Ignores 100% Defense v. armored targets. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round passive skill icon, 200x200, "Heavy Cover": Activates before an ally is attacked. Cover an ally with a heavy guard. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round passive skill icon, 200x200, "Heavy Guard": Activates before being hit by a physickal attack. Block an emeny attack with a heavy guard. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `passive/ground_counter.png` | 256x256 |
| 2 | `passive/gryphon_glide.png` | 256x256 |
| 3 | `passive/guard_order.png` | 256x256 |
| 4 | `passive/guardian.png` | 256x256 |
| 5 | `passive/hastened_cover.png` | 256x256 |
| 6 | `passive/hastened_strike.png` | 256x256 |
| 7 | `passive/hawk_eye.png` | 256x256 |
| 8 | `passive/heavy_counter.png` | 256x256 |
| 9 | `passive/heavy_cover.png` | 256x256 |
| 10 | `passive/heavy_guard.png` | 256x256 |

## Батч 27 — значки навыков (`b27_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round passive skill icon, 200x200, "Holy Barrier": Activates before an ally is attacked. Reduce damage taken by an ally by 50% for one attack. Also prevents them from being afflicted. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round passive skill icon, 200x200, "Holy Guard": Activates before being hit by a physickal attack. Block an enemy attack with a medium guard. Prevents debuffs. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round passive skill icon, 200x200, "Iron Veil": Activates at the start of a battle. Grants +50% Guard Rate and +30% Phys. Defense to all allies. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round passive skill icon, 200x200, "Iron Will": a fitting emblem. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round passive skill icon, 200x200, "Keen Call": Activates before an ally attacks (Active). Grants 100% Critical Rate for an ally's next attack. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round passive skill icon, 200x200, "Killing Pursuit": Activates after an ally attacks (Active). Follow-up attack a single enemy. Grants the user +1 AP if the target is defeated. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round passive skill icon, 200x200, "Knight's Pursuit": Activates after a calavry-based ally attacks (Active). Follow-up attack a column of enemies with a piercing strike. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round passive skill icon, 200x200, "Life Blow": Activates at the end of a battle. Attack a single enemy. Deals damage equal to 80% of the user's HP. (This attack cannot be a critical). A single bold symbol on a dark round field, no ring, no text.
Cell 9: round passive skill icon, 200x200, "Lifesaver": Activates before being attacked. Heal self for minor HP recovery. Grants user a buff to endure one lethal blow. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round passive skill icon, 200x200, "Lifeshare": Activates after an ally is hit by an attack. Share HP with an ally. (50% of the user's HP). A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `passive/holy_barrier.png` | 256x256 |
| 2 | `passive/holy_guard.png` | 256x256 |
| 3 | `passive/iron_veil.png` | 256x256 |
| 4 | `passive/iron_will.png` | 256x256 |
| 5 | `passive/keen_call.png` | 256x256 |
| 6 | `passive/killing_pursuit.png` | 256x256 |
| 7 | `passive/knights_pursuit.png` | 256x256 |
| 8 | `passive/life_blow.png` | 256x256 |
| 9 | `passive/lifesaver.png` | 256x256 |
| 10 | `passive/lifeshare.png` | 256x256 |

## Батч 28 — значки навыков (`b28_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round passive skill icon, 200x200, "Luminous Cover": Activates before an ally is attacked. Cover an ally with a medium guard. Grants that ally +20% Defense. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round passive skill icon, 200x200, "Magick Barrier": Activates before an ally is hit by a magick attack. Negate the next magick damage dealt to an ally. Also negates afflictions. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round passive skill icon, 200x200, "Magick Conferral": Activates before an ally's physickal attack (Active). Add magick damage to an ally's next attack. (50 potency.). A single bold symbol on a dark round field, no ring, no text.
Cell 4: round passive skill icon, 200x200, "Magick Counter": Activates after an enemy attacks with an active skill. Counterattack a single enemy with magick. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round passive skill icon, 200x200, "Magick Pursuit": Activates after ally uses a magick attack (Active). Follow-up attack a single enemy with magick. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round passive skill icon, 200x200, "Maiden's Hammer": Activates after an enemy attacks with an active skill. Counterattack a single enemy. Potency increases the less HP the user has. (Maximum increase:+10. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round passive skill icon, 200x200, "Medical Aid": Activates at the end of a battle. Restore 15% HP to a row of allies. Healing doubles if target's HP is 50% or less. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round passive skill icon, 200x200, "Noble Guard": Activates before being hit by a physickal attack. Block an ememy attack with a medium guard. Grants the user +20% Defense. Grants the user +1 PP if th. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round passive skill icon, 200x200, "Nocturnal Evade": Activates before being attacked. Evade a single hit. Grants the user +1 PP at night. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round passive skill icon, 200x200, "Nocturnal Guard": Activates before being hit by a physickal attack. Block an enemy attack with a medium guard. Grants the user +1 PP at night. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `passive/luminous_cover.png` | 256x256 |
| 2 | `passive/magick_barrier.png` | 256x256 |
| 3 | `passive/magick_conferral.png` | 256x256 |
| 4 | `passive/magick_counter.png` | 256x256 |
| 5 | `passive/magick_pursuit.png` | 256x256 |
| 6 | `passive/maidens_hammer.png` | 256x256 |
| 7 | `passive/medical_aid.png` | 256x256 |
| 8 | `passive/noble_guard.png` | 256x256 |
| 9 | `passive/nocturnal_evade.png` | 256x256 |
| 10 | `passive/nocturnal_guard.png` | 256x256 |

## Батч 29 — значки навыков (`b29_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round passive skill icon, 200x200, "Nocturnal Rest": Activates after attacking. Recover 30% HP. Recovered HP doubles at night. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round passive skill icon, 200x200, "Nocturnal Strike": Activates at the start of a battle. Attack an enemy with a first strike. Grants the user +1 PP at night. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round passive skill icon, 200x200, "Parry": Activates before being hit by a melee attack. Negate melee damage for a single hit. Grants the user +1APAP. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round passive skill icon, 200x200, "Parting Blow": Activates at the end pf a battle. Attacks a single enemy. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round passive skill icon, 200x200, "Parting Resurrection": Activates at the end of battle. Revive one ally, restorting them to 1 HP. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round passive skill icon, 200x200, "Passive Miracle": Activates after receiving an ally's passive skill. Restore minor HP and grant +1 PP to an ally. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round passive skill icon, 200x200, "Provoke": Activates at the start of a battle. Force a row of enemies to focus attacks on the user. Grants the user +50% Guard Rate. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round passive skill icon, 200x200, "Pure Field": Activates at the start of a battle. Grants all allies a buff that negates a single debuff. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round passive skill icon, 200x200, "Pursuit": Activates after an ally attacks (Active). Follow-up attack a single enemy. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round passive skill icon, 200x200, "Quick Cast": Activates at the start of a battle. Grants the user max Initiative for their next action and -50 Critical Rate. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `passive/nocturnal_rest.png` | 256x256 |
| 2 | `passive/nocturnal_strike.png` | 256x256 |
| 3 | `passive/parry.png` | 256x256 |
| 4 | `passive/parting_blow.png` | 256x256 |
| 5 | `passive/parting_resurrection.png` | 256x256 |
| 6 | `passive/passive_miracle.png` | 256x256 |
| 7 | `passive/provoke.png` | 256x256 |
| 8 | `passive/pure_field.png` | 256x256 |
| 9 | `passive/pursuit.png` | 256x256 |
| 10 | `passive/quick_cast.png` | 256x256 |

## Батч 30 — значки навыков (`b30_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round passive skill icon, 200x200, "Quick Cover": Activates before an ally is attacked. Cover an ally with a medium guard. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round passive skill icon, 200x200, "Quick Cure": Activates after an ally is debuffed. Remove all debuffs from an ally. Grants the target immunity to one debuff. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round passive skill icon, 200x200, "Quick Curse": Activates before an enemy uses an attack skill. Inflicts Attack -20% for a single enemy's next attack. Inflicts Critcal Seal. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round passive skill icon, 200x200, "Quick Dispel": Activates after an enemy is buffed. Remove all buffs from a single enemy. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round passive skill icon, 200x200, "Quick Guard": Activates before being hit by a physickal attack. Block an enemy attack with a medium guard. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round passive skill icon, 200x200, "Quick Heal": Activates after an ally is hit by an attack. Restore minor HP to an ally. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round passive skill icon, 200x200, "Quick Reload": Activates after attacking. Follow-up attacks a single enemy. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round passive skill icon, 200x200, "Radiant Cover": Activates before an ally is attacked. Cover an ally with a medium guard. Makes that ally's next attack a truestrike. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round passive skill icon, 200x200, "Rage of the Faeries": Activates at the start of a battle. Attack a row of enemies with a magick first strike. Inflicts Stun, grants the user +1 summoned faeries. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round passive skill icon, 200x200, "Rapid Order": Activates at the start of a battle. Grants all allies +20 Initiative. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `passive/quick_cover.png` | 256x256 |
| 2 | `passive/quick_cure.png` | 256x256 |
| 3 | `passive/quick_curse.png` | 256x256 |
| 4 | `passive/quick_dispel.png` | 256x256 |
| 5 | `passive/quick_guard.png` | 256x256 |
| 6 | `passive/quick_heal.png` | 256x256 |
| 7 | `passive/quick_reload.png` | 256x256 |
| 8 | `passive/radiant_cover.png` | 256x256 |
| 9 | `passive/rage_of_the_faeries.png` | 256x256 |
| 10 | `passive/rapid_order.png` | 256x256 |

## Батч 31 — значки навыков (`b31_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round passive skill icon, 200x200, "Refresh": Activates after an ally is debuffed. Remove all debuffs from a row of allies. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round passive skill icon, 200x200, "Remove Weakness": Activates after the user is debuffed. Removes the user’s debuffs. Grants user a buff to evade one attack. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round passive skill icon, 200x200, "Restore": Activates after an ally uses a passive skill. Grants an ally +1 PP. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round passive skill icon, 200x200, "Row Barrier": Activates before an ally is hit by a magick attack. Negate the next magick damage dealt to a row of allies. Also negates afflictions. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round passive skill icon, 200x200, "Row Cover": Activates before an ally is attacked. Cover a row of allies with a medium guard. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round passive skill icon, 200x200, "Royal Guard": Activates before being hit by a physickal attack. Block an enemy attack with a medium guard. User recovers 25% HP. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round passive skill icon, 200x200, "Saint's Barrier": Activates before an ally is attacked. Reduce damage taken by an ally by 50% for one attack. Also prevents them from being ddebuffed. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round passive skill icon, 200x200, "Sanguine Arts": Activates before attacking with an active skill. User will reover HP equal to +50% of damage dealt on next attack. A single bold symbol on a dark round field, no ring, no text.
Cell 9: round passive skill icon, 200x200, "Selfless Heal": Activates after being healed. Restore minor HP to all allies. Remove all debuffs. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round passive skill icon, 200x200, "Shadow Pursuit": Activates after an ally attacks (Active). Follow-up attack a single enemy. Inflicts Blindness. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `passive/refresh.png` | 256x256 |
| 2 | `passive/remove_weakness.png` | 256x256 |
| 3 | `passive/restore.png` | 256x256 |
| 4 | `passive/row_barrier.png` | 256x256 |
| 5 | `passive/row_cover.png` | 256x256 |
| 6 | `passive/royal_guard.png` | 256x256 |
| 7 | `passive/saints_barrier.png` | 256x256 |
| 8 | `passive/sanguine_arts.png` | 256x256 |
| 9 | `passive/selfless_heal.png` | 256x256 |
| 10 | `passive/shadow_pursuit.png` | 256x256 |

## Батч 32 — значки навыков (`b32_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round passive skill icon, 200x200, "Slyphic Barrier": Activates before an ally is hit by a ranged phys. attack. Allow an ally to evade one attack. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round passive skill icon, 200x200, "Sneaking Edge": Activates at the start of a battle. Attack a single enemy with a first strike. Inflicts Guard Seal and Passive Seal. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round passive skill icon, 200x200, "Sniping Order": Activates before an ally attacks (Active). Make a row of allies' next attack a truestrike. A single bold symbol on a dark round field, no ring, no text.
Cell 4: round passive skill icon, 200x200, "Snow-white Strike": Activates after an ally attacks (Active). Follow-up attack a single enemy. Inflicts Freeze. +100 potency v. forzen targets. A single bold symbol on a dark round field, no ring, no text.
Cell 5: round passive skill icon, 200x200, "Triple Counter": Activates after an enemy attacks with an active skill. Counterattack three enemies. A single bold symbol on a dark round field, no ring, no text.
Cell 6: round passive skill icon, 200x200, "Undying Will": Activates before attacking with an active skill. Attack potency increases as HP decreases.(Maximum increase:+100) Grants the ablility to survive one l. A single bold symbol on a dark round field, no ring, no text.
Cell 7: round passive skill icon, 200x200, "Vengeance": Activates after being attacked. Grants the user +20% Attack and +20% Defense. (Effect stacks.) Grants the user +1 PP if the user is at 50% HP or less. A single bold symbol on a dark round field, no ring, no text.
Cell 8: round passive skill icon, 200x200, "Vengeful Guard": Activates before being hit by a physickal attack. Blocks an enemy attack with a medium guard. Grants the user +20% Phys. Attack. (Effect stacks.). A single bold symbol on a dark round field, no ring, no text.
Cell 9: round passive skill icon, 200x200, "War Horn": Activates at the start of a battle. Make all allies attack skills unguardable. A single bold symbol on a dark round field, no ring, no text.
Cell 10: round passive skill icon, 200x200, "Weakness Hunter": Activates after an enemy is debuffed. Attack a single enemy. Ignores 50% of the target's Defense. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `passive/slyphic_barrier.png` | 256x256 |
| 2 | `passive/sneaking_edge.png` | 256x256 |
| 3 | `passive/sniping_order.png` | 256x256 |
| 4 | `passive/snow_white_strike.png` | 256x256 |
| 5 | `passive/triple_counter.png` | 256x256 |
| 6 | `passive/undying_will.png` | 256x256 |
| 7 | `passive/vengeance.png` | 256x256 |
| 8 | `passive/vengeful_guard.png` | 256x256 |
| 9 | `passive/war_horn.png` | 256x256 |
| 10 | `passive/weakness_hunter.png` | 256x256 |

## Батч 33 — значки навыков (`b33_skills.png`)

```
<STYLE>
<SHEET>
Cell 1: round passive skill icon, 200x200, "Wide Counter": Activates after an enemy attacks with an active skill. Counterattack a row of enemies. A single bold symbol on a dark round field, no ring, no text.
Cell 2: round passive skill icon, 200x200, "Wild Kick": Activates after an enemy guards against an ally's attack. Attack a single enemy. Inflicts Stun and Guard Seal. A single bold symbol on a dark round field, no ring, no text.
Cell 3: round passive skill icon, 200x200, "Wing Rest": Activates at the end of a battle. Recover 25% HP. Recovered HP doubles if afflicted. A single bold symbol on a dark round field, no ring, no text.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `passive/wide_counter.png` | 256x256 |
| 2 | `passive/wild_kick.png` | 256x256 |
| 3 | `passive/wing_rest.png` | 256x256 |

## 4. Иконки предметов

Ячейка: иконка предмета 200x200, лёгкий поворот три четверти, чистый силуэт, без рамки и фона (рамку цвета тира рисует интерфейс). Материал серии указан в строке.

## Батч 34 — иконки: sword (`b34_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, sword "Bronze Sword": dull bronze. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, sword "Iron Sword": plain grey iron. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, sword "Recruit's Shortsword": plain simple iron, recruit issue. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, sword "Baroque Sword": ornate baroque gilded. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, sword "Viperfang". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, sword "Hallowed Blade". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, sword "Searing Rapier": red-hot glowing. Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, sword "Templar's Sword": holy white enamel with a gold cross. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, sword "Black-Iron Sword": blackened iron. Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, sword "Carnat Sword": red-lacquered steel. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/light_sword/bronze_sword.png` | 256x256 |
| 2 | `item/light_sword/iron_sword.png` | 256x256 |
| 3 | `item/light_sword/recruits_shortsword.png` | 256x256 |
| 4 | `item/light_sword/baroque_sword.png` | 256x256 |
| 5 | `item/light_sword/viperfang.png` | 256x256 |
| 6 | `item/light_sword/hallowed_blade.png` | 256x256 |
| 7 | `item/light_sword/searing_rapier.png` | 256x256 |
| 8 | `item/light_sword/templars_sword.png` | 256x256 |
| 9 | `item/light_sword/black_iron_sword.png` | 256x256 |
| 10 | `item/light_sword/carnat_sword.png` | 256x256 |

## Батч 35 — иконки: sword (`b35_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, sword "Crimson Épée": crimson. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, sword "Sanguine Blade": blood-red crimson metal. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, sword "Barbarian's Might". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, sword "Rose Knight Sword": rose and thorn motifs. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, sword "Royal Saber": royal blue and gold. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, sword "Steel Sword": polished steel. Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, sword "Pursuant's Blade". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, sword "Bandit Longsword". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, sword "Dancer's Delight". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, sword "Greatsword". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/light_sword/crimson_epee.png` | 256x256 |
| 2 | `item/light_sword/sanguine_blade.png` | 256x256 |
| 3 | `item/light_sword/barbarians_might.png` | 256x256 |
| 4 | `item/light_sword/rose_knight_sword.png` | 256x256 |
| 5 | `item/light_sword/royal_saber.png` | 256x256 |
| 6 | `item/light_sword/steel_sword.png` | 256x256 |
| 7 | `item/light_sword/pursuants_blade.png` | 256x256 |
| 8 | `item/light_sword/bandit_longsword.png` | 256x256 |
| 9 | `item/light_sword/dancers_delight.png` | 256x256 |
| 10 | `item/light_sword/greatsword.png` | 256x256 |

## Батч 36 — иконки: sword (`b36_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, sword "Moonlight Rapier": silver-blue moonlit. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, sword "Sacral Sword": sacred white and gold with a halo motif. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, sword "Scorpion's Sting". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, sword "Sylph's Bane". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, sword "Thorn Blade": dark thorny wood and iron. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, sword "Stingray". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, sword "Zenoiran Sword": imperial black and gold ornamented. Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, sword "Flamberge". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, sword "Heavenswing Sword". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, sword "Hunter's Claymore". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/light_sword/moonlight_rapier.png` | 256x256 |
| 2 | `item/light_sword/sacral_sword.png` | 256x256 |
| 3 | `item/light_sword/scorpions_sting.png` | 256x256 |
| 4 | `item/light_sword/sylphs_bane.png` | 256x256 |
| 5 | `item/light_sword/thorn_blade.png` | 256x256 |
| 6 | `item/light_sword/stingray.png` | 256x256 |
| 7 | `item/light_sword/zenoiran_sword.png` | 256x256 |
| 8 | `item/light_sword/flamberge.png` | 256x256 |
| 9 | `item/light_sword/heavenswing_sword.png` | 256x256 |
| 10 | `item/light_sword/hunters_claymore.png` | 256x256 |

## Батч 37 — иконки: sword (`b37_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, sword "Spellsteel Sword": bluish runed steel faintly glowing. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, sword "Vorpal Sword": razor-keen silver steel. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, sword "Wyvern Razor". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, sword "Dragonbone Blade": ivory dragon bone with scales. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, sword "Phantom Knight's Sword": ghostly translucent violet metal. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, sword "Cutthroat's Boon". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, sword "Greatwood Sword": pale carved wood with leaf motifs and a green gem. Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, sword "Runic Sword": carved runes. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, sword "Carnelian Blade": inlaid with red carnelian stones. Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, sword "Rosularis Sword". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/light_sword/spellsteel_sword.png` | 256x256 |
| 2 | `item/light_sword/vorpal_sword.png` | 256x256 |
| 3 | `item/light_sword/wyvern_razor.png` | 256x256 |
| 4 | `item/light_sword/dragonbone_blade.png` | 256x256 |
| 5 | `item/light_sword/phantom_knights_sword.png` | 256x256 |
| 6 | `item/light_sword/cutthroats_boon.png` | 256x256 |
| 7 | `item/light_sword/greatwood_sword.png` | 256x256 |
| 8 | `item/light_sword/runic_sword.png` | 256x256 |
| 9 | `item/light_sword/carnelian_blade.png` | 256x256 |
| 10 | `item/light_sword/rosularis_sword.png` | 256x256 |

## Батч 38 — иконки: sword (`b38_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, sword "Hailstorm Edge". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, sword "Galecutter". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, sword "Icefall Blade": frosty pale-blue steel with icicles. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, sword "Meteorite Sword": dark meteoric iron with starry flecks. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, sword "Wingcrest Blade": white steel with a feather crest. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, sword "Zenoiran Knight's Sword": imperial black and gold ornamented. Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, sword "Holy Unicorn Blade": white and gold holy. Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, sword "Notos's Sword". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, sword "Kingsblade Cornix": kingly legendary. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/light_sword/hailstorm_edge.png` | 256x256 |
| 2 | `item/light_sword/galecutter.png` | 256x256 |
| 3 | `item/light_sword/icefall_blade.png` | 256x256 |
| 4 | `item/light_sword/meteorite_sword.png` | 256x256 |
| 5 | `item/light_sword/wingcrest_blade.png` | 256x256 |
| 6 | `item/light_sword/zenoiran_knights_sword.png` | 256x256 |
| 7 | `item/light_sword/holy_unicorn_blade.png` | 256x256 |
| 8 | `item/light_sword/notoss_sword.png` | 256x256 |
| 9 | `item/light_sword/kingsblade_cornix.png` | 256x256 |

## Батч 39 — иконки: axe or hammer (`b39_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, axe or hammer "Bronze Axe": dull bronze. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, axe or hammer "Mason's Hammer". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, axe or hammer "Recruit's ShortAxe": plain simple iron, recruit issue. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, axe or hammer "Iron Axe": plain grey iron. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, axe or hammer "Barbarian's Axe". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, axe or hammer "Baroque Axe": ornate baroque gilded. Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, axe or hammer "Crushing Axe". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, axe or hammer "Hoarfrost Axe": icy white frost. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, axe or hammer "Spiked Hammer". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, axe or hammer "Templar's Axe": holy white enamel with a gold cross. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/heavy_weapon/bronze_axe.png` | 256x256 |
| 2 | `item/heavy_weapon/masons_hammer.png` | 256x256 |
| 3 | `item/heavy_weapon/recruits_shortaxe.png` | 256x256 |
| 4 | `item/heavy_weapon/iron_axe.png` | 256x256 |
| 5 | `item/heavy_weapon/barbarians_axe.png` | 256x256 |
| 6 | `item/heavy_weapon/baroque_axe.png` | 256x256 |
| 7 | `item/heavy_weapon/crushing_axe.png` | 256x256 |
| 8 | `item/heavy_weapon/hoarfrost_axe.png` | 256x256 |
| 9 | `item/heavy_weapon/spiked_hammer.png` | 256x256 |
| 10 | `item/heavy_weapon/templars_axe.png` | 256x256 |

## Батч 40 — иконки: axe or hammer (`b40_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, axe or hammer "Black-Iron Axe": blackened iron. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, axe or hammer "Carnat Axe": red-lacquered steel. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, axe or hammer "Headsman's Axe". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, axe or hammer "Sanguine Axe": blood-red crimson metal. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, axe or hammer "Rose Knight Axe": rose and thorn motifs. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, axe or hammer "Bandit's Handaxe". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, axe or hammer "Warhammer". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, axe or hammer "Rose Knight Hammer": rose and thorn motifs. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, axe or hammer "Morningstar". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, axe or hammer "Steel Axe": polished steel. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/heavy_weapon/black_iron_axe.png` | 256x256 |
| 2 | `item/heavy_weapon/carnat_axe.png` | 256x256 |
| 3 | `item/heavy_weapon/headsmans_axe.png` | 256x256 |
| 4 | `item/heavy_weapon/sanguine_axe.png` | 256x256 |
| 5 | `item/heavy_weapon/rose_knight_axe.png` | 256x256 |
| 6 | `item/heavy_weapon/bandits_handaxe.png` | 256x256 |
| 7 | `item/heavy_weapon/warhammer.png` | 256x256 |
| 8 | `item/heavy_weapon/rose_knight_hammer.png` | 256x256 |
| 9 | `item/heavy_weapon/morningstar.png` | 256x256 |
| 10 | `item/heavy_weapon/steel_axe.png` | 256x256 |

## Батч 41 — иконки: axe or hammer (`b41_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, axe or hammer "Silvermoon Axe". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, axe or hammer "Banishing Hammer". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, axe or hammer "Frozen Battleaxe". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, axe or hammer "Sacral Axe": sacred white and gold with a halo motif. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, axe or hammer "Thorn Axe": dark thorny wood and iron. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, axe or hammer "Zenoiran Axe": imperial black and gold ornamented. Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, axe or hammer "Hunter's Halberd". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, axe or hammer "Eliminator". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, axe or hammer "Spellsteel Axe": bluish runed steel faintly glowing. Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, axe or hammer "Vorpal Axe": razor-keen silver steel. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/heavy_weapon/silvermoon_axe.png` | 256x256 |
| 2 | `item/heavy_weapon/banishing_hammer.png` | 256x256 |
| 3 | `item/heavy_weapon/frozen_battleaxe.png` | 256x256 |
| 4 | `item/heavy_weapon/sacral_axe.png` | 256x256 |
| 5 | `item/heavy_weapon/thorn_axe.png` | 256x256 |
| 6 | `item/heavy_weapon/zenoiran_axe.png` | 256x256 |
| 7 | `item/heavy_weapon/hunters_halberd.png` | 256x256 |
| 8 | `item/heavy_weapon/eliminator.png` | 256x256 |
| 9 | `item/heavy_weapon/spellsteel_axe.png` | 256x256 |
| 10 | `item/heavy_weapon/vorpal_axe.png` | 256x256 |

## Батч 42 — иконки: axe or hammer (`b42_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, axe or hammer "Dragonbone Axe": ivory dragon bone with scales. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, axe or hammer "Phantom Knight's Axe": ghostly translucent violet metal. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, axe or hammer "Greatwood Axe": pale carved wood with leaf motifs and a green gem. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, axe or hammer "Dark Knight Cleaver". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, axe or hammer "Labrys". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, axe or hammer "Carnelian Axe": inlaid with red carnelian stones. Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, axe or hammer "Golden Ram Axe": golden. Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, axe or hammer "Helleborus Axe". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, axe or hammer "Giant's Greataxe". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, axe or hammer "Icefall Axe": frosty pale-blue steel with icicles. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/heavy_weapon/dragonbone_axe.png` | 256x256 |
| 2 | `item/heavy_weapon/phantom_knights_axe.png` | 256x256 |
| 3 | `item/heavy_weapon/greatwood_axe.png` | 256x256 |
| 4 | `item/heavy_weapon/dark_knight_cleaver.png` | 256x256 |
| 5 | `item/heavy_weapon/labrys.png` | 256x256 |
| 6 | `item/heavy_weapon/carnelian_axe.png` | 256x256 |
| 7 | `item/heavy_weapon/golden_ram_axe.png` | 256x256 |
| 8 | `item/heavy_weapon/helleborus_axe.png` | 256x256 |
| 9 | `item/heavy_weapon/giants_greataxe.png` | 256x256 |
| 10 | `item/heavy_weapon/icefall_axe.png` | 256x256 |

## Батч 43 — иконки: axe or hammer (`b43_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, axe or hammer "Juggernaut". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, axe or hammer "Knot of Ruin". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, axe or hammer "Meteorite Axe": dark meteoric iron with starry flecks. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, axe or hammer "Wingcrest Axe": white steel with a feather crest. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, axe or hammer "Boreas's Axe". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, axe or hammer "Zenoiran Knight Axe": imperial black and gold ornamented. Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, axe or hammer "Kingsaxe Drakenash". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/heavy_weapon/juggernaut.png` | 256x256 |
| 2 | `item/heavy_weapon/knot_of_ruin.png` | 256x256 |
| 3 | `item/heavy_weapon/meteorite_axe.png` | 256x256 |
| 4 | `item/heavy_weapon/wingcrest_axe.png` | 256x256 |
| 5 | `item/heavy_weapon/boreass_axe.png` | 256x256 |
| 6 | `item/heavy_weapon/zenoiran_knight_axe.png` | 256x256 |
| 7 | `item/heavy_weapon/kingsaxe_drakenash.png` | 256x256 |

## Батч 44 — иконки: spear (`b44_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, spear "Bronze Spear": dull bronze. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, spear "Iron Spear": plain grey iron. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, spear "Recruit's ShortSpear": plain simple iron, recruit issue. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, spear "Baroque Spear": ornate baroque gilded. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, spear "Surging Shortspear". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, spear "Templar's Spear": holy white enamel with a gold cross. Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, spear "Black-Iron Spear": blackened iron. Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, spear "Bloody Spear". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, spear "Carnat Spear": red-lacquered steel. Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, spear "Valkyrie's Partisan". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/lance/bronze_spear.png` | 256x256 |
| 2 | `item/lance/iron_spear.png` | 256x256 |
| 3 | `item/lance/recruits_shortspear.png` | 256x256 |
| 4 | `item/lance/baroque_spear.png` | 256x256 |
| 5 | `item/lance/surging_shortspear.png` | 256x256 |
| 6 | `item/lance/templars_spear.png` | 256x256 |
| 7 | `item/lance/black_iron_spear.png` | 256x256 |
| 8 | `item/lance/bloody_spear.png` | 256x256 |
| 9 | `item/lance/carnat_spear.png` | 256x256 |
| 10 | `item/lance/valkyries_partisan.png` | 256x256 |

## Батч 45 — иконки: spear (`b45_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, spear "Corroded Spear". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, spear "Flame Javelin": flame-wreathed. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, spear "Unwavering Spear". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, spear "Steel Spear": polished steel. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, spear "Canyon Lance". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, spear "Watchman's Longspear". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, spear "Sacral Spear": sacred white and gold with a halo motif. Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, spear "Thorn Spear": dark thorny wood and iron. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, spear "Zenoiran Spear": imperial black and gold ornamented. Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, spear "Glaive". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/lance/corroded_spear.png` | 256x256 |
| 2 | `item/lance/flame_javelin.png` | 256x256 |
| 3 | `item/lance/unwavering_spear.png` | 256x256 |
| 4 | `item/lance/steel_spear.png` | 256x256 |
| 5 | `item/lance/canyon_lance.png` | 256x256 |
| 6 | `item/lance/watchmans_longspear.png` | 256x256 |
| 7 | `item/lance/sacral_spear.png` | 256x256 |
| 8 | `item/lance/thorn_spear.png` | 256x256 |
| 9 | `item/lance/zenoiran_spear.png` | 256x256 |
| 10 | `item/lance/glaive.png` | 256x256 |

## Батч 46 — иконки: spear (`b46_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, spear "Crimson Sarissa": crimson. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, spear "Spellsteel Spear": bluish runed steel faintly glowing. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, spear "Vorpal Spear": razor-keen silver steel. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, spear "Dragonbone Spear": ivory dragon bone with scales. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, spear "Phantom Knight's Spear": ghostly translucent violet metal. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, spear "Adept's Shortspear". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, spear "General's Pike". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, spear "Greatwood Spear": pale carved wood with leaf motifs and a green gem. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, spear "Runic Spear": carved runes. Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, spear "Elfeater". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/lance/crimson_sarissa.png` | 256x256 |
| 2 | `item/lance/spellsteel_spear.png` | 256x256 |
| 3 | `item/lance/vorpal_spear.png` | 256x256 |
| 4 | `item/lance/dragonbone_spear.png` | 256x256 |
| 5 | `item/lance/phantom_knights_spear.png` | 256x256 |
| 6 | `item/lance/adepts_shortspear.png` | 256x256 |
| 7 | `item/lance/generals_pike.png` | 256x256 |
| 8 | `item/lance/greatwood_spear.png` | 256x256 |
| 9 | `item/lance/runic_spear.png` | 256x256 |
| 10 | `item/lance/elfeater.png` | 256x256 |

## Батч 47 — иконки: spear (`b47_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, spear "Helix Spear". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, spear "Carnelian Spear": inlaid with red carnelian stones. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, spear "Orchis Spear". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, spear "Silver Trident": silver. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, spear "Dragoon's Warspear". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, spear "Storm of Hail". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, spear "Nameless Guard's Spear". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, spear "Testarossa". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, spear "Icefall Spear": frosty pale-blue steel with icicles. Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, spear "Meteorite Lance": dark meteoric iron with starry flecks. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/lance/helix_spear.png` | 256x256 |
| 2 | `item/lance/carnelian_spear.png` | 256x256 |
| 3 | `item/lance/orchis_spear.png` | 256x256 |
| 4 | `item/lance/silver_trident.png` | 256x256 |
| 5 | `item/lance/dragoons_warspear.png` | 256x256 |
| 6 | `item/lance/storm_of_hail.png` | 256x256 |
| 7 | `item/lance/nameless_guards_spear.png` | 256x256 |
| 8 | `item/lance/testarossa.png` | 256x256 |
| 9 | `item/lance/icefall_spear.png` | 256x256 |
| 10 | `item/lance/meteorite_lance.png` | 256x256 |

## Батч 48 — иконки: spear (`b48_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, spear "Twinned Bough". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, spear "Wingcrest Spear": white steel with a feather crest. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, spear "Zenoiran Knight Spear": imperial black and gold ornamented. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, spear "Zephyros's Spear". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, spear "Kingspear Elhal". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/lance/twinned_bough.png` | 256x256 |
| 2 | `item/lance/wingcrest_spear.png` | 256x256 |
| 3 | `item/lance/zenoiran_knight_spear.png` | 256x256 |
| 4 | `item/lance/zephyross_spear.png` | 256x256 |
| 5 | `item/lance/kingspear_elhal.png` | 256x256 |

## Батч 49 — иконки: bow (`b49_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, bow "Bronze Bow": dull bronze. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, bow "Flame Bow": flame-wreathed. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, bow "Recruit's ShortBow": plain simple iron, recruit issue. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, bow "Iron Bow": plain grey iron. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, bow "Salamander Greatbow". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, bow "Starless Bow". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, bow "Baroque Bow": ornate baroque gilded. Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, bow "Viper Bow": green serpent motifs. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, bow "Pheasant Bow". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, bow "Piercing Bow". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/bow/bronze_bow.png` | 256x256 |
| 2 | `item/bow/flame_bow.png` | 256x256 |
| 3 | `item/bow/recruits_shortbow.png` | 256x256 |
| 4 | `item/bow/iron_bow.png` | 256x256 |
| 5 | `item/bow/salamander_greatbow.png` | 256x256 |
| 6 | `item/bow/starless_bow.png` | 256x256 |
| 7 | `item/bow/baroque_bow.png` | 256x256 |
| 8 | `item/bow/viper_bow.png` | 256x256 |
| 9 | `item/bow/pheasant_bow.png` | 256x256 |
| 10 | `item/bow/piercing_bow.png` | 256x256 |

## Батч 50 — иконки: bow (`b50_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, bow "Thundering Bow": crackling with lightning. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, bow "Black-Iron Bow": blackened iron. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, bow "Templar's Bow": holy white enamel with a gold cross. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, bow "Bow of Swiftness". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, bow "Carnat Bow": red-lacquered steel. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, bow "Sanguine Bow": blood-red crimson metal. Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, bow "Spellseal Bow". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, bow "Steel Bow": polished steel. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, bow "Silvermoon Bow". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, bow "Watchman's LongBow". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/bow/thundering_bow.png` | 256x256 |
| 2 | `item/bow/black_iron_bow.png` | 256x256 |
| 3 | `item/bow/templars_bow.png` | 256x256 |
| 4 | `item/bow/bow_of_swiftness.png` | 256x256 |
| 5 | `item/bow/carnat_bow.png` | 256x256 |
| 6 | `item/bow/sanguine_bow.png` | 256x256 |
| 7 | `item/bow/spellseal_bow.png` | 256x256 |
| 8 | `item/bow/steel_bow.png` | 256x256 |
| 9 | `item/bow/silvermoon_bow.png` | 256x256 |
| 10 | `item/bow/watchmans_longbow.png` | 256x256 |

## Батч 51 — иконки: bow (`b51_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, bow "Sacral Bow": sacred white and gold with a halo motif. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, bow "Thorn Bow": dark thorny wood and iron. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, bow "Zenoiran Bow": imperial black and gold ornamented. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, bow "Spellsteel Bow": bluish runed steel faintly glowing. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, bow "Vorpal Bow": razor-keen silver steel. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, bow "Phantom Knight's Bow": ghostly translucent violet metal. Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, bow "Crane Bow". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, bow "Dragonbone Bow": ivory dragon bone with scales. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, bow "General's Longbow". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, bow "Greatwood Bow": pale carved wood with leaf motifs and a green gem. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/bow/sacral_bow.png` | 256x256 |
| 2 | `item/bow/thorn_bow.png` | 256x256 |
| 3 | `item/bow/zenoiran_bow.png` | 256x256 |
| 4 | `item/bow/spellsteel_bow.png` | 256x256 |
| 5 | `item/bow/vorpal_bow.png` | 256x256 |
| 6 | `item/bow/phantom_knights_bow.png` | 256x256 |
| 7 | `item/bow/crane_bow.png` | 256x256 |
| 8 | `item/bow/dragonbone_bow.png` | 256x256 |
| 9 | `item/bow/generals_longbow.png` | 256x256 |
| 10 | `item/bow/greatwood_bow.png` | 256x256 |

## Батч 52 — иконки: bow (`b52_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, bow "Desert Bow". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, bow "Carnelian Bow": inlaid with red carnelian stones. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, bow "Interrogator's Bow". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, bow "Greatwood Spiritbow": pale carved wood with leaf motifs and a green gem. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, bow "Quince Bow". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, bow "Trapper's Warbow". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, bow "Icefall Bow": frosty pale-blue steel with icicles. Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, bow "Nameless Guard's Bow". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, bow "Piercing Strongbow". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, bow "Thundering Strongbow": crackling with lightning. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/bow/desert_bow.png` | 256x256 |
| 2 | `item/bow/carnelian_bow.png` | 256x256 |
| 3 | `item/bow/interrogators_bow.png` | 256x256 |
| 4 | `item/bow/greatwood_spiritbow.png` | 256x256 |
| 5 | `item/bow/quince_bow.png` | 256x256 |
| 6 | `item/bow/trappers_warbow.png` | 256x256 |
| 7 | `item/bow/icefall_bow.png` | 256x256 |
| 8 | `item/bow/nameless_guards_bow.png` | 256x256 |
| 9 | `item/bow/piercing_strongbow.png` | 256x256 |
| 10 | `item/bow/thundering_strongbow.png` | 256x256 |

## Батч 53 — иконки: bow (`b53_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, bow "Frostbloom Bow". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, bow "Meteorite Bow": dark meteoric iron with starry flecks. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, bow "Wingcrest Bow": white steel with a feather crest. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, bow "Woodpecker". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, bow "Zenoiran Knight Bow": imperial black and gold ornamented. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, bow "The Inquisitor". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, bow "Alminster". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, bow "Gallian Crossbow". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, bow "Apeliotes's Bow". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, bow "Infamous Bow". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/bow/frostbloom_bow.png` | 256x256 |
| 2 | `item/bow/meteorite_bow.png` | 256x256 |
| 3 | `item/bow/wingcrest_bow.png` | 256x256 |
| 4 | `item/bow/woodpecker.png` | 256x256 |
| 5 | `item/bow/zenoiran_knight_bow.png` | 256x256 |
| 6 | `item/bow/the_inquisitor.png` | 256x256 |
| 7 | `item/bow/alminster.png` | 256x256 |
| 8 | `item/bow/gallian_crossbow.png` | 256x256 |
| 9 | `item/bow/apeliotess_bow.png` | 256x256 |
| 10 | `item/bow/infamous_bow.png` | 256x256 |

## Батч 54 — иконки: bow (`b54_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, bow "Kingsbow Bastorik". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/bow/kingsbow_bastorik.png` | 256x256 |

## Батч 55 — иконки: mage staff (`b55_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, mage staff "Shaman's Bonestaff". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, mage staff "Bronze Staff": dull bronze. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, mage staff "Recruit's Staff": plain simple iron, recruit issue. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, mage staff "Baroque Staff": ornate baroque gilded. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, mage staff "Iron Staff": plain grey iron. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, mage staff "Chiropteran Staff". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, mage staff "Chlorotic". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, mage staff "Defender's Mace". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, mage staff "Lifeblood Staff". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, mage staff "Liberator's Staff". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/staff/shamans_bonestaff.png` | 256x256 |
| 2 | `item/staff/bronze_staff.png` | 256x256 |
| 3 | `item/staff/recruits_staff.png` | 256x256 |
| 4 | `item/staff/baroque_staff.png` | 256x256 |
| 5 | `item/staff/iron_staff.png` | 256x256 |
| 6 | `item/staff/chiropteran_staff.png` | 256x256 |
| 7 | `item/staff/chlorotic.png` | 256x256 |
| 8 | `item/staff/defenders_mace.png` | 256x256 |
| 9 | `item/staff/lifeblood_staff.png` | 256x256 |
| 10 | `item/staff/liberators_staff.png` | 256x256 |

## Батч 56 — иконки: mage staff (`b56_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, mage staff "Thawing Scepter". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, mage staff "Mother Laelia's Staff". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, mage staff "Spellsteel Staff": bluish runed steel faintly glowing. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, mage staff "Pestilent Staff". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, mage staff "Quartz Rod". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, mage staff "Black-Iron Staff": blackened iron. Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, mage staff "Hallowed Mace". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, mage staff "Carnat Staff": red-lacquered steel. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, mage staff "Dustbound Staff". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, mage staff "Flame-Hex Staff". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/staff/thawing_scepter.png` | 256x256 |
| 2 | `item/staff/mother_laelias_staff.png` | 256x256 |
| 3 | `item/staff/spellsteel_staff.png` | 256x256 |
| 4 | `item/staff/pestilent_staff.png` | 256x256 |
| 5 | `item/staff/quartz_rod.png` | 256x256 |
| 6 | `item/staff/black_iron_staff.png` | 256x256 |
| 7 | `item/staff/hallowed_mace.png` | 256x256 |
| 8 | `item/staff/carnat_staff.png` | 256x256 |
| 9 | `item/staff/dustbound_staff.png` | 256x256 |
| 10 | `item/staff/flame_hex_staff.png` | 256x256 |

## Батч 57 — иконки: mage staff (`b57_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, mage staff "Poison-Hex Staff". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, mage staff "Speed-Hex Staff". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, mage staff "Staff of Succor". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, mage staff "Greatwood Staff": pale carved wood with leaf motifs and a green gem. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, mage staff "Templar's Staff": holy white enamel with a gold cross. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, mage staff "Bloodmoon Rod". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, mage staff "Red-Bark Staff". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, mage staff "Gleaming Mace". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, mage staff "Steel Staff": polished steel. Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, mage staff "Telluric Staff". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/staff/poison_hex_staff.png` | 256x256 |
| 2 | `item/staff/speed_hex_staff.png` | 256x256 |
| 3 | `item/staff/staff_of_succor.png` | 256x256 |
| 4 | `item/staff/greatwood_staff.png` | 256x256 |
| 5 | `item/staff/templars_staff.png` | 256x256 |
| 6 | `item/staff/bloodmoon_rod.png` | 256x256 |
| 7 | `item/staff/red_bark_staff.png` | 256x256 |
| 8 | `item/staff/gleaming_mace.png` | 256x256 |
| 9 | `item/staff/steel_staff.png` | 256x256 |
| 10 | `item/staff/telluric_staff.png` | 256x256 |

## Батч 58 — иконки: mage staff (`b58_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, mage staff "Cardinal's Mace". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, mage staff "Grand Magus Staff". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, mage staff "Libera". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, mage staff "Precious Rod". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, mage staff "Ein Seeker". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, mage staff "Purifier". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, mage staff "Sacral Staff": sacred white and gold with a halo motif. Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, mage staff "Thorn Staff": dark thorny wood and iron. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, mage staff "Icestorm Staff". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, mage staff "Zenoiran Staff": imperial black and gold ornamented. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/staff/cardinals_mace.png` | 256x256 |
| 2 | `item/staff/grand_magus_staff.png` | 256x256 |
| 3 | `item/staff/libera.png` | 256x256 |
| 4 | `item/staff/precious_rod.png` | 256x256 |
| 5 | `item/staff/ein_seeker.png` | 256x256 |
| 6 | `item/staff/purifier.png` | 256x256 |
| 7 | `item/staff/sacral_staff.png` | 256x256 |
| 8 | `item/staff/thorn_staff.png` | 256x256 |
| 9 | `item/staff/icestorm_staff.png` | 256x256 |
| 10 | `item/staff/zenoiran_staff.png` | 256x256 |

## Батч 59 — иконки: mage staff (`b59_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, mage staff "Phosphorescent Staff". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, mage staff "Ringed Staff". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, mage staff "Phantom Knight's Staff": ghostly translucent violet metal. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, mage staff "Vorpal Staff": razor-keen silver steel. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, mage staff "Dragonbone Staff": ivory dragon bone with scales. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, mage staff "Millenium Scepter". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, mage staff "Cleric's Cane". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, mage staff "Lyrical Wand". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, mage staff "Carnelian Staff": inlaid with red carnelian stones. Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, mage staff "Lupinus Staff". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/staff/phosphorescent_staff.png` | 256x256 |
| 2 | `item/staff/ringed_staff.png` | 256x256 |
| 3 | `item/staff/phantom_knights_staff.png` | 256x256 |
| 4 | `item/staff/vorpal_staff.png` | 256x256 |
| 5 | `item/staff/dragonbone_staff.png` | 256x256 |
| 6 | `item/staff/millenium_scepter.png` | 256x256 |
| 7 | `item/staff/clerics_cane.png` | 256x256 |
| 8 | `item/staff/lyrical_wand.png` | 256x256 |
| 9 | `item/staff/carnelian_staff.png` | 256x256 |
| 10 | `item/staff/lupinus_staff.png` | 256x256 |

## Батч 60 — иконки: mage staff (`b60_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, mage staff "Icefall Staff": frosty pale-blue steel with icicles. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, mage staff "Wind Scepter". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, mage staff "Meteorite Staff": dark meteoric iron with starry flecks. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, mage staff "Wingcrest Staff": white steel with a feather crest. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, mage staff "Papal Crosier". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, mage staff "Zenoiran Knight's Staff": imperial black and gold ornamented. Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, mage staff "Euros's Staff". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, mage staff "Kingstaff Albiore". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, mage staff "Warding Staff". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/staff/icefall_staff.png` | 256x256 |
| 2 | `item/staff/wind_scepter.png` | 256x256 |
| 3 | `item/staff/meteorite_staff.png` | 256x256 |
| 4 | `item/staff/wingcrest_staff.png` | 256x256 |
| 5 | `item/staff/papal_crosier.png` | 256x256 |
| 6 | `item/staff/zenoiran_knights_staff.png` | 256x256 |
| 7 | `item/staff/euross_staff.png` | 256x256 |
| 8 | `item/staff/kingstaff_albiore.png` | 256x256 |
| 9 | `item/staff/warding_staff.png` | 256x256 |

## Батч 61 — иконки: shield (`b61_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, shield "Obsidian Shield": black obsidian. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, shield "Battler's Shield". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, shield "Bronze Shield": dull bronze. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, shield "Parrying Shield". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, shield "Recruit's Shield": plain simple iron, recruit issue. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, shield "Blessed Roundshield". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, shield "Watchman's Bockler". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, shield "Arrowshield". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, shield "Greatwood Shield": pale carved wood with leaf motifs and a green gem. Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, shield "Hoarfrost Shield": icy white frost. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/light_shield/obsidian_shield.png` | 256x256 |
| 2 | `item/light_shield/battlers_shield.png` | 256x256 |
| 3 | `item/light_shield/bronze_shield.png` | 256x256 |
| 4 | `item/light_shield/parrying_shield.png` | 256x256 |
| 5 | `item/light_shield/recruits_shield.png` | 256x256 |
| 6 | `item/light_shield/blessed_roundshield.png` | 256x256 |
| 7 | `item/light_shield/watchmans_bockler.png` | 256x256 |
| 8 | `item/light_shield/arrowshield.png` | 256x256 |
| 9 | `item/light_shield/greatwood_shield.png` | 256x256 |
| 10 | `item/light_shield/hoarfrost_shield.png` | 256x256 |

## Батч 62 — иконки: shield (`b62_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, shield "Iron Shield": plain grey iron. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, shield "Searing Shield": red-hot glowing. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, shield "Templar's Shield": holy white enamel with a gold cross. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, shield "Baroque Shield": ornate baroque gilded. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, shield "Viper Shield": green serpent motifs. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, shield "Guard's Shield". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, shield "Zenoiran Shield": imperial black and gold ornamented. Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, shield "Chivalric Shield". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, shield "Luminous Shield": softly glowing pale gold. Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, shield "Twin Dragon Shield". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/light_shield/iron_shield.png` | 256x256 |
| 2 | `item/light_shield/searing_shield.png` | 256x256 |
| 3 | `item/light_shield/templars_shield.png` | 256x256 |
| 4 | `item/light_shield/baroque_shield.png` | 256x256 |
| 5 | `item/light_shield/viper_shield.png` | 256x256 |
| 6 | `item/light_shield/guards_shield.png` | 256x256 |
| 7 | `item/light_shield/zenoiran_shield.png` | 256x256 |
| 8 | `item/light_shield/chivalric_shield.png` | 256x256 |
| 9 | `item/light_shield/luminous_shield.png` | 256x256 |
| 10 | `item/light_shield/twin_dragon_shield.png` | 256x256 |

## Батч 63 — иконки: shield (`b63_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, shield "Carnat Shield": red-lacquered steel. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, shield "Unfettered Shield". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, shield "Angel Hunter's Buckler". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, shield "Cavalry Hunter's Buckler". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, shield "Ironclad Buckler". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, shield "Manalith Buckler". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, shield "Squire's Shield". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, shield "Black-Iron Shield": blackened iron. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, shield "Steel Shield": polished steel. Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, shield "Golden Ram Shield": golden. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/light_shield/carnat_shield.png` | 256x256 |
| 2 | `item/light_shield/unfettered_shield.png` | 256x256 |
| 3 | `item/light_shield/angel_hunters_buckler.png` | 256x256 |
| 4 | `item/light_shield/cavalry_hunters_buckler.png` | 256x256 |
| 5 | `item/light_shield/ironclad_buckler.png` | 256x256 |
| 6 | `item/light_shield/manalith_buckler.png` | 256x256 |
| 7 | `item/light_shield/squires_shield.png` | 256x256 |
| 8 | `item/light_shield/black_iron_shield.png` | 256x256 |
| 9 | `item/light_shield/steel_shield.png` | 256x256 |
| 10 | `item/light_shield/golden_ram_shield.png` | 256x256 |

## Батч 64 — иконки: shield (`b64_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, shield "White Rider's Shield": white enamel. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, shield "Beast Hunter's Buckler". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, shield "Hunter's Buckler". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, shield "Moonlight Shield": silver-blue moonlit. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, shield "Mercenay's Shield". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, shield "Nameless Guard's Shield". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, shield "Azure Crest Shield". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, shield "Holy Unicorn Shield": white and gold holy. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, shield "Thorn Shield": dark thorny wood and iron. Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, shield "White Knight's Shield": white enamel. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/light_shield/white_riders_shield.png` | 256x256 |
| 2 | `item/light_shield/beast_hunters_buckler.png` | 256x256 |
| 3 | `item/light_shield/hunters_buckler.png` | 256x256 |
| 4 | `item/light_shield/moonlight_shield.png` | 256x256 |
| 5 | `item/light_shield/mercenays_shield.png` | 256x256 |
| 6 | `item/light_shield/nameless_guards_shield.png` | 256x256 |
| 7 | `item/light_shield/azure_crest_shield.png` | 256x256 |
| 8 | `item/light_shield/holy_unicorn_shield.png` | 256x256 |
| 9 | `item/light_shield/thorn_shield.png` | 256x256 |
| 10 | `item/light_shield/white_knights_shield.png` | 256x256 |

## Батч 65 — иконки: shield (`b65_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, shield "Unyielding Shield". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, shield "Spellsteel Shield": bluish runed steel faintly glowing. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, shield "Vorpal Shield": razor-keen silver steel. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, shield "Heavenswing Shield". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, shield "Holy Knight's Shield": white and gold holy. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, shield "Scarlet Crest Shield". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, shield "Blue Rose Shield": blue, rose and thorn motifs. Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, shield "Dragonbone Shield": ivory dragon bone with scales. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, shield "Phantom Knight's Shield": ghostly translucent violet metal. Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, shield "Zenoiran Knight's Shield": imperial black and gold ornamented. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/light_shield/unyielding_shield.png` | 256x256 |
| 2 | `item/light_shield/spellsteel_shield.png` | 256x256 |
| 3 | `item/light_shield/vorpal_shield.png` | 256x256 |
| 4 | `item/light_shield/heavenswing_shield.png` | 256x256 |
| 5 | `item/light_shield/holy_knights_shield.png` | 256x256 |
| 6 | `item/light_shield/scarlet_crest_shield.png` | 256x256 |
| 7 | `item/light_shield/blue_rose_shield.png` | 256x256 |
| 8 | `item/light_shield/dragonbone_shield.png` | 256x256 |
| 9 | `item/light_shield/phantom_knights_shield.png` | 256x256 |
| 10 | `item/light_shield/zenoiran_knights_shield.png` | 256x256 |

## Батч 66 — иконки: shield (`b66_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, shield "Icefall Shield": frosty pale-blue steel with icicles. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, shield "Kaikai's Shield". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, shield "Wingcrest Shield": white steel with a feather crest. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/light_shield/icefall_shield.png` | 256x256 |
| 2 | `item/light_shield/kaikais_shield.png` | 256x256 |
| 3 | `item/light_shield/wingcrest_shield.png` | 256x256 |

## Батч 67 — иконки: large tower greatshield (`b67_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, large tower greatshield "Heaven's Mirror Greatshield". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, large tower greatshield "Bronze Greatshield": dull bronze. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, large tower greatshield "Conveyable Greatshield". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, large tower greatshield "Recruit's Greatshield": plain simple iron, recruit issue. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, large tower greatshield "Baroque Greatshield": ornate baroque gilded. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, large tower greatshield "Hoarfrost Greatshield": icy white frost. Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, large tower greatshield "Horsekiller Greatshield". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, large tower greatshield "Iron Greatshield": plain grey iron. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, large tower greatshield "Ironclad Towershield". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, large tower greatshield "Searing Greatshield": red-hot glowing. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/greatshield/heavens_mirror_greatshield.png` | 256x256 |
| 2 | `item/greatshield/bronze_greatshield.png` | 256x256 |
| 3 | `item/greatshield/conveyable_greatshield.png` | 256x256 |
| 4 | `item/greatshield/recruits_greatshield.png` | 256x256 |
| 5 | `item/greatshield/baroque_greatshield.png` | 256x256 |
| 6 | `item/greatshield/hoarfrost_greatshield.png` | 256x256 |
| 7 | `item/greatshield/horsekiller_greatshield.png` | 256x256 |
| 8 | `item/greatshield/iron_greatshield.png` | 256x256 |
| 9 | `item/greatshield/ironclad_towershield.png` | 256x256 |
| 10 | `item/greatshield/searing_greatshield.png` | 256x256 |

## Батч 68 — иконки: large tower greatshield (`b68_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, large tower greatshield "Squire's Greatshield". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, large tower greatshield "Templar's Greatshield": holy white enamel with a gold cross. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, large tower greatshield "Viper Greatshield": green serpent motifs. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, large tower greatshield "Wingclipper Greatshield". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, large tower greatshield "Black-Iron Greatshield": blackened iron. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, large tower greatshield "Zenoiran Greatshield": imperial black and gold ornamented. Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, large tower greatshield "White Knight's Greatshield": white enamel. Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, large tower greatshield "Beastslayer Greatshield". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, large tower greatshield "Carnat Greatshield": red-lacquered steel. Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, large tower greatshield "Greatwood Greatshield": pale carved wood with leaf motifs and a green gem. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/greatshield/squires_greatshield.png` | 256x256 |
| 2 | `item/greatshield/templars_greatshield.png` | 256x256 |
| 3 | `item/greatshield/viper_greatshield.png` | 256x256 |
| 4 | `item/greatshield/wingclipper_greatshield.png` | 256x256 |
| 5 | `item/greatshield/black_iron_greatshield.png` | 256x256 |
| 6 | `item/greatshield/zenoiran_greatshield.png` | 256x256 |
| 7 | `item/greatshield/white_knights_greatshield.png` | 256x256 |
| 8 | `item/greatshield/beastslayer_greatshield.png` | 256x256 |
| 9 | `item/greatshield/carnat_greatshield.png` | 256x256 |
| 10 | `item/greatshield/greatwood_greatshield.png` | 256x256 |

## Батч 69 — иконки: large tower greatshield (`b69_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, large tower greatshield "Blacksilver Pavise". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, large tower greatshield "Bulwark Towershield". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, large tower greatshield "Luminous Greatshield": softly glowing pale gold. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, large tower greatshield "Moonlight Greatshield": silver-blue moonlit. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, large tower greatshield "Panoplied Greatshield". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, large tower greatshield "Steel Greatshield": polished steel. Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, large tower greatshield "Azure Crest Greatshield". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, large tower greatshield "Unyielding Greatshield". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, large tower greatshield "Citadel Guard's Greatshield". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, large tower greatshield "Thorn Greatshield": dark thorny wood and iron. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/greatshield/blacksilver_pavise.png` | 256x256 |
| 2 | `item/greatshield/bulwark_towershield.png` | 256x256 |
| 3 | `item/greatshield/luminous_greatshield.png` | 256x256 |
| 4 | `item/greatshield/moonlight_greatshield.png` | 256x256 |
| 5 | `item/greatshield/panoplied_greatshield.png` | 256x256 |
| 6 | `item/greatshield/steel_greatshield.png` | 256x256 |
| 7 | `item/greatshield/azure_crest_greatshield.png` | 256x256 |
| 8 | `item/greatshield/unyielding_greatshield.png` | 256x256 |
| 9 | `item/greatshield/citadel_guards_greatshield.png` | 256x256 |
| 10 | `item/greatshield/thorn_greatshield.png` | 256x256 |

## Батч 70 — иконки: large tower greatshield (`b70_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, large tower greatshield "Mirage Greatshield". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, large tower greatshield "Champion's Towershield". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, large tower greatshield "Spellsteel Greatshield": bluish runed steel faintly glowing. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, large tower greatshield "Drakestone Iceshield". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, large tower greatshield "Dragonbone Greatshield": ivory dragon bone with scales. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, large tower greatshield "Gran Baris". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, large tower greatshield "Vorpal Greatshield": razor-keen silver steel. Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, large tower greatshield "Zenoiran Knight's Greatshield": imperial black and gold ornamented. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, large tower greatshield "Greatshield Of The Abyss". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, large tower greatshield "Skiron's Greatshield". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/greatshield/mirage_greatshield.png` | 256x256 |
| 2 | `item/greatshield/champions_towershield.png` | 256x256 |
| 3 | `item/greatshield/spellsteel_greatshield.png` | 256x256 |
| 4 | `item/greatshield/drakestone_iceshield.png` | 256x256 |
| 5 | `item/greatshield/dragonbone_greatshield.png` | 256x256 |
| 6 | `item/greatshield/gran_baris.png` | 256x256 |
| 7 | `item/greatshield/vorpal_greatshield.png` | 256x256 |
| 8 | `item/greatshield/zenoiran_knights_greatshield.png` | 256x256 |
| 9 | `item/greatshield/greatshield_of_the_abyss.png` | 256x256 |
| 10 | `item/greatshield/skirons_greatshield.png` | 256x256 |

## Батч 71 — иконки: large tower greatshield (`b71_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, large tower greatshield "Phantom Knight's Greatshield": ghostly translucent violet metal. Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, large tower greatshield "Hero's Greatshield". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, large tower greatshield "Icefall Greatshield": frosty pale-blue steel with icicles. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, large tower greatshield "Wingcrest Greatshield": white steel with a feather crest. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/greatshield/phantom_knights_greatshield.png` | 256x256 |
| 2 | `item/greatshield/heros_greatshield.png` | 256x256 |
| 3 | `item/greatshield/icefall_greatshield.png` | 256x256 |
| 4 | `item/greatshield/wingcrest_greatshield.png` | 256x256 |

## Батч 72 — иконки: accessory (`b72_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Ancient Crown". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Battleline Standard". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Celestial Talisman". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Chloe's Charm". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "Cleric's Bracelet". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, accessory "Dancer's Bracelet". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, accessory "Dream Crown". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, accessory "Elite Standard". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, accessory "Familiar's Choker". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, accessory "First Aid Kit". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/ancient_crown.png` | 256x256 |
| 2 | `item/artifact/battleline_standard.png` | 256x256 |
| 3 | `item/artifact/celestial_talisman.png` | 256x256 |
| 4 | `item/artifact/chloes_charm.png` | 256x256 |
| 5 | `item/artifact/clerics_bracelet.png` | 256x256 |
| 6 | `item/artifact/dancers_bracelet.png` | 256x256 |
| 7 | `item/artifact/dream_crown.png` | 256x256 |
| 8 | `item/artifact/elite_standard.png` | 256x256 |
| 9 | `item/artifact/familiars_choker.png` | 256x256 |
| 10 | `item/artifact/first_aid_kit.png` | 256x256 |

## Батч 73 — иконки: accessory (`b73_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Gambler's Coin". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Glory Sash". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Gold Goblet": gold. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Golden Egg": golden. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "Gust Bracelet". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, accessory "Lapis Bell". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, accessory "Large Aid Kit". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, accessory "Liberator's Bracelet". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, accessory "Lips's Ring". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, accessory "Magia Heart". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/gamblers_coin.png` | 256x256 |
| 2 | `item/artifact/glory_sash.png` | 256x256 |
| 3 | `item/artifact/gold_goblet.png` | 256x256 |
| 4 | `item/artifact/golden_egg.png` | 256x256 |
| 5 | `item/artifact/gust_bracelet.png` | 256x256 |
| 6 | `item/artifact/lapis_bell.png` | 256x256 |
| 7 | `item/artifact/large_aid_kit.png` | 256x256 |
| 8 | `item/artifact/liberators_bracelet.png` | 256x256 |
| 9 | `item/artifact/lipss_ring.png` | 256x256 |
| 10 | `item/artifact/magia_heart.png` | 256x256 |

## Батч 74 — иконки: accessory (`b74_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Magia Soul". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Medical Kit". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Outlaw's Bracelet". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Pursuant's Bracelet". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "Ring Of The Unicorn". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, accessory "Rookie Egg". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, accessory "Sage Owl's Shawl". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, accessory "Silver Goblet": silver. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, accessory "Squall Bracelet". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, accessory "Tailwind Cape". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/magia_soul.png` | 256x256 |
| 2 | `item/artifact/medical_kit.png` | 256x256 |
| 3 | `item/artifact/outlaws_bracelet.png` | 256x256 |
| 4 | `item/artifact/pursuants_bracelet.png` | 256x256 |
| 5 | `item/artifact/ring_of_the_unicorn.png` | 256x256 |
| 6 | `item/artifact/rookie_egg.png` | 256x256 |
| 7 | `item/artifact/sage_owls_shawl.png` | 256x256 |
| 8 | `item/artifact/silver_goblet.png` | 256x256 |
| 9 | `item/artifact/squall_bracelet.png` | 256x256 |
| 10 | `item/artifact/tailwind_cape.png` | 256x256 |

## Батч 75 — иконки: accessory (`b75_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Talisman Of The Abyss". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Thief's Bell". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Truestrike Star". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Verdant Ribbon". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "White Ribbon": white enamel. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, accessory "Wind Faerie's Bell". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, accessory "Acrobat's Shoes". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, accessory "Aurora Ring". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, accessory "Wingline Standard". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, accessory "Wolf Fang Bracelet". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/talisman_of_the_abyss.png` | 256x256 |
| 2 | `item/artifact/thiefs_bell.png` | 256x256 |
| 3 | `item/artifact/truestrike_star.png` | 256x256 |
| 4 | `item/artifact/verdant_ribbon.png` | 256x256 |
| 5 | `item/artifact/white_ribbon.png` | 256x256 |
| 6 | `item/artifact/wind_faeries_bell.png` | 256x256 |
| 7 | `item/artifact/acrobats_shoes.png` | 256x256 |
| 8 | `item/artifact/aurora_ring.png` | 256x256 |
| 9 | `item/artifact/wingline_standard.png` | 256x256 |
| 10 | `item/artifact/wolf_fang_bracelet.png` | 256x256 |

## Батч 76 — иконки: accessory (`b76_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Wyvern Claw". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Awakening Amulet". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Bloodmoon Earrings". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Clearsight Amulet". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "Counter Belt". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, accessory "Defensive Ring". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, accessory "Defrosting Amulet". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, accessory "Detoxifying Amulet". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, accessory "Earrings Of Pursuit". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, accessory "Gravekeeper Boots". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/wyvern_claw.png` | 256x256 |
| 2 | `item/artifact/awakening_amulet.png` | 256x256 |
| 3 | `item/artifact/bloodmoon_earrings.png` | 256x256 |
| 4 | `item/artifact/clearsight_amulet.png` | 256x256 |
| 5 | `item/artifact/counter_belt.png` | 256x256 |
| 6 | `item/artifact/defensive_ring.png` | 256x256 |
| 7 | `item/artifact/defrosting_amulet.png` | 256x256 |
| 8 | `item/artifact/detoxifying_amulet.png` | 256x256 |
| 9 | `item/artifact/earrings_of_pursuit.png` | 256x256 |
| 10 | `item/artifact/gravekeeper_boots.png` | 256x256 |

## Батч 77 — иконки: accessory (`b77_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Gravekeeper Lantern". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Liberator's Belt". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Mage's Gloves". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Necromancer's Lantern". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "Parrying Amulet". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, accessory "Quenching Amulet". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, accessory "Retaliation Earrings". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, accessory "Self-Aid Kit". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, accessory "Dancer's Anklet". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, accessory "Shawl Of Repose". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/gravekeeper_lantern.png` | 256x256 |
| 2 | `item/artifact/liberators_belt.png` | 256x256 |
| 3 | `item/artifact/mages_gloves.png` | 256x256 |
| 4 | `item/artifact/necromancers_lantern.png` | 256x256 |
| 5 | `item/artifact/parrying_amulet.png` | 256x256 |
| 6 | `item/artifact/quenching_amulet.png` | 256x256 |
| 7 | `item/artifact/retaliation_earrings.png` | 256x256 |
| 8 | `item/artifact/self_aid_kit.png` | 256x256 |
| 9 | `item/artifact/dancers_anklet.png` | 256x256 |
| 10 | `item/artifact/shawl_of_repose.png` | 256x256 |

## Батч 78 — иконки: accessory (`b78_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Skillful Amulet". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Spirit's Necklace". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Watchman's Lantern". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Badger Gauntlets". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "Barbed Ribbon". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, accessory "Bloodbrand Tome". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, accessory "Citadel Guard's Sabatons". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, accessory "Phoenix's Plume". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, accessory "Soothing Plume". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, accessory "Cooling Bandana". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/skillful_amulet.png` | 256x256 |
| 2 | `item/artifact/spirits_necklace.png` | 256x256 |
| 3 | `item/artifact/watchmans_lantern.png` | 256x256 |
| 4 | `item/artifact/badger_gauntlets.png` | 256x256 |
| 5 | `item/artifact/barbed_ribbon.png` | 256x256 |
| 6 | `item/artifact/bloodbrand_tome.png` | 256x256 |
| 7 | `item/artifact/citadel_guards_sabatons.png` | 256x256 |
| 8 | `item/artifact/phoenixs_plume.png` | 256x256 |
| 9 | `item/artifact/soothing_plume.png` | 256x256 |
| 10 | `item/artifact/cooling_bandana.png` | 256x256 |

## Батч 79 — иконки: accessory (`b79_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Crude Tasset". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Dawn Robes". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Defender's Ring". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Dirty Gambler's Coin". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "Druid's Robes". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, accessory "Dusk Robes". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, accessory "Flamebrand Tome". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, accessory "Fluffy Cape". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, accessory "Frostbrand Tome". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, accessory "Guardian Gloves". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/crude_tasset.png` | 256x256 |
| 2 | `item/artifact/dawn_robes.png` | 256x256 |
| 3 | `item/artifact/defenders_ring.png` | 256x256 |
| 4 | `item/artifact/dirty_gamblers_coin.png` | 256x256 |
| 5 | `item/artifact/druids_robes.png` | 256x256 |
| 6 | `item/artifact/dusk_robes.png` | 256x256 |
| 7 | `item/artifact/flamebrand_tome.png` | 256x256 |
| 8 | `item/artifact/fluffy_cape.png` | 256x256 |
| 9 | `item/artifact/frostbrand_tome.png` | 256x256 |
| 10 | `item/artifact/guardian_gloves.png` | 256x256 |

## Батч 80 — иконки: accessory (`b80_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Illusory Cloak". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Leaf Broach". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Miser's Bracelet". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Monk's Mitre". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "Rose Broach": rose and thorn motifs. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, accessory "Charm Of Warding". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, accessory "Thief's Mantle". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, accessory "Thunderbrand Tome". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, accessory "Twilight Cloak". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, accessory "Wolfpack Gauntlets". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/illusory_cloak.png` | 256x256 |
| 2 | `item/artifact/leaf_broach.png` | 256x256 |
| 3 | `item/artifact/misers_bracelet.png` | 256x256 |
| 4 | `item/artifact/monks_mitre.png` | 256x256 |
| 5 | `item/artifact/rose_broach.png` | 256x256 |
| 6 | `item/artifact/charm_of_warding.png` | 256x256 |
| 7 | `item/artifact/thiefs_mantle.png` | 256x256 |
| 8 | `item/artifact/thunderbrand_tome.png` | 256x256 |
| 9 | `item/artifact/twilight_cloak.png` | 256x256 |
| 10 | `item/artifact/wolfpack_gauntlets.png` | 256x256 |

## Батч 81 — иконки: accessory (`b81_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Wooly Mittens". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Courser's Reins". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Defensive Gauntlets". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Sorcerer's Gauntlets". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "Vengeful Caligae". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, accessory "Wyvern Reins". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, accessory "Brown Beret". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, accessory "Dove Plume". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, accessory "Iron Shackles": plain grey iron. Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, accessory "Lamplight Ring". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/wooly_mittens.png` | 256x256 |
| 2 | `item/artifact/coursers_reins.png` | 256x256 |
| 3 | `item/artifact/defensive_gauntlets.png` | 256x256 |
| 4 | `item/artifact/sorcerers_gauntlets.png` | 256x256 |
| 5 | `item/artifact/vengeful_caligae.png` | 256x256 |
| 6 | `item/artifact/wyvern_reins.png` | 256x256 |
| 7 | `item/artifact/brown_beret.png` | 256x256 |
| 8 | `item/artifact/dove_plume.png` | 256x256 |
| 9 | `item/artifact/iron_shackles.png` | 256x256 |
| 10 | `item/artifact/lamplight_ring.png` | 256x256 |

## Батч 82 — иконки: accessory (`b82_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Leather Hood". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Vitality Talisman". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Bronze Bangle": dull bronze. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Bronze Circlet": dull bronze. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "Holy Broach": white and gold holy. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, accessory "Master's Gauntlets". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, accessory "Watchman's Horn". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, accessory "Black Cat-Ear Hood". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, accessory "Green Beret". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, accessory "Old Witch's Ring". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/leather_hood.png` | 256x256 |
| 2 | `item/artifact/vitality_talisman.png` | 256x256 |
| 3 | `item/artifact/bronze_bangle.png` | 256x256 |
| 4 | `item/artifact/bronze_circlet.png` | 256x256 |
| 5 | `item/artifact/holy_broach.png` | 256x256 |
| 6 | `item/artifact/masters_gauntlets.png` | 256x256 |
| 7 | `item/artifact/watchmans_horn.png` | 256x256 |
| 8 | `item/artifact/black_cat_ear_hood.png` | 256x256 |
| 9 | `item/artifact/green_beret.png` | 256x256 |
| 10 | `item/artifact/old_witchs_ring.png` | 256x256 |

## Батч 83 — иконки: accessory (`b83_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Power Belt". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Silk Hood". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Sniper's Lens". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Armored Gauntlets". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "Lapis Pendant". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, accessory "Prisoner's Shackles". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, accessory "Raven Plume". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, accessory "White Cat-Ear Hood": white enamel. Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, accessory "Crown Of The Abyss". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, accessory "Elite Beret". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/power_belt.png` | 256x256 |
| 2 | `item/artifact/silk_hood.png` | 256x256 |
| 3 | `item/artifact/snipers_lens.png` | 256x256 |
| 4 | `item/artifact/armored_gauntlets.png` | 256x256 |
| 5 | `item/artifact/lapis_pendant.png` | 256x256 |
| 6 | `item/artifact/prisoners_shackles.png` | 256x256 |
| 7 | `item/artifact/raven_plume.png` | 256x256 |
| 8 | `item/artifact/white_cat_ear_hood.png` | 256x256 |
| 9 | `item/artifact/crown_of_the_abyss.png` | 256x256 |
| 10 | `item/artifact/elite_beret.png` | 256x256 |

## Батч 84 — иконки: accessory (`b84_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Gauntlets Of The Abyss". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Holy Unicorn Signet": white and gold holy. Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Sacral Broach": sacred white and gold with a halo motif. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Silver Circlet": silver. Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "Archbishop's Mitre". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, accessory "Daemon's Shackles". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, accessory "Lifeblood Talisman". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, accessory "Sage's Hood". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, accessory "Undead Ring". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, accessory "Blue Spectacles": blue. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/gauntlets_of_the_abyss.png` | 256x256 |
| 2 | `item/artifact/holy_unicorn_signet.png` | 256x256 |
| 3 | `item/artifact/sacral_broach.png` | 256x256 |
| 4 | `item/artifact/silver_circlet.png` | 256x256 |
| 5 | `item/artifact/archbishops_mitre.png` | 256x256 |
| 6 | `item/artifact/daemons_shackles.png` | 256x256 |
| 7 | `item/artifact/lifeblood_talisman.png` | 256x256 |
| 8 | `item/artifact/sages_hood.png` | 256x256 |
| 9 | `item/artifact/undead_ring.png` | 256x256 |
| 10 | `item/artifact/blue_spectacles.png` | 256x256 |

## Батч 85 — иконки: accessory (`b85_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Gauntlets". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Mercenary's Eyepatch". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Silken Scarf". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Sniper's Amber Lens". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "Carnelian Pendant": inlaid with red carnelian stones. Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, accessory "Cleric's Medallion". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, accessory "Gold Circlet": gold. Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, accessory "Knight's Medallion". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, accessory "Scarlett's Ribbon". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, accessory "Silver Bangle": silver. Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/gauntlets.png` | 256x256 |
| 2 | `item/artifact/mercenarys_eyepatch.png` | 256x256 |
| 3 | `item/artifact/silken_scarf.png` | 256x256 |
| 4 | `item/artifact/snipers_amber_lens.png` | 256x256 |
| 5 | `item/artifact/carnelian_pendant.png` | 256x256 |
| 6 | `item/artifact/clerics_medallion.png` | 256x256 |
| 7 | `item/artifact/gold_circlet.png` | 256x256 |
| 8 | `item/artifact/knights_medallion.png` | 256x256 |
| 9 | `item/artifact/scarletts_ribbon.png` | 256x256 |
| 10 | `item/artifact/silver_bangle.png` | 256x256 |

## Батч 86 — иконки: accessory (`b86_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Angel Plume". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Glacial Ring". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Mistletoe Charm". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Sorcerer's Medallion". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "Warrior's Medallion". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, accessory "Charm Of Land & Sea". Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, accessory "Charm Of Sun & Moon". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, accessory "Heavensteed Reins". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, accessory "Salamander Ring". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, accessory "Sapphire Pendant". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/angel_plume.png` | 256x256 |
| 2 | `item/artifact/glacial_ring.png` | 256x256 |
| 3 | `item/artifact/mistletoe_charm.png` | 256x256 |
| 4 | `item/artifact/sorcerers_medallion.png` | 256x256 |
| 5 | `item/artifact/warriors_medallion.png` | 256x256 |
| 6 | `item/artifact/charm_of_land_sea.png` | 256x256 |
| 7 | `item/artifact/charm_of_sun_moon.png` | 256x256 |
| 8 | `item/artifact/heavensteed_reins.png` | 256x256 |
| 9 | `item/artifact/salamander_ring.png` | 256x256 |
| 10 | `item/artifact/sapphire_pendant.png` | 256x256 |

## Батч 87 — иконки: accessory (`b87_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Thunderclap Ring". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Cloth Gauntlets". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Gold Bangle": gold. Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Heavenwyvern Reins". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "Mirrored Spectacles". Single object, slight three-quarter view, no frame.
Cell 6: inventory icon, 200x200, accessory "Royal Scarf": royal blue and gold. Single object, slight three-quarter view, no frame.
Cell 7: inventory icon, 200x200, accessory "Amethyst Pendant". Single object, slight three-quarter view, no frame.
Cell 8: inventory icon, 200x200, accessory "Ervélda's Talisman". Single object, slight three-quarter view, no frame.
Cell 9: inventory icon, 200x200, accessory "Hero's Medallion". Single object, slight three-quarter view, no frame.
Cell 10: inventory icon, 200x200, accessory "Lucky Coin". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/thunderclap_ring.png` | 256x256 |
| 2 | `item/artifact/cloth_gauntlets.png` | 256x256 |
| 3 | `item/artifact/gold_bangle.png` | 256x256 |
| 4 | `item/artifact/heavenwyvern_reins.png` | 256x256 |
| 5 | `item/artifact/mirrored_spectacles.png` | 256x256 |
| 6 | `item/artifact/royal_scarf.png` | 256x256 |
| 7 | `item/artifact/amethyst_pendant.png` | 256x256 |
| 8 | `item/artifact/erveldas_talisman.png` | 256x256 |
| 9 | `item/artifact/heros_medallion.png` | 256x256 |
| 10 | `item/artifact/lucky_coin.png` | 256x256 |

## Батч 88 — иконки: accessory (`b88_items.png`)

```
<STYLE>
<SHEET>
Cell 1: inventory icon, 200x200, accessory "Ruby Pendant". Single object, slight three-quarter view, no frame.
Cell 2: inventory icon, 200x200, accessory "Veteran's Eyepatch". Single object, slight three-quarter view, no frame.
Cell 3: inventory icon, 200x200, accessory "Bloodstained Ribbon". Single object, slight three-quarter view, no frame.
Cell 4: inventory icon, 200x200, accessory "Lionheart". Single object, slight three-quarter view, no frame.
Cell 5: inventory icon, 200x200, accessory "Onyx Pendant". Single object, slight three-quarter view, no frame.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `item/artifact/ruby_pendant.png` | 256x256 |
| 2 | `item/artifact/veterans_eyepatch.png` | 256x256 |
| 3 | `item/artifact/bloodstained_ribbon.png` | 256x256 |
| 4 | `item/artifact/lionheart.png` | 256x256 |
| 5 | `item/artifact/onyx_pendant.png` | 256x256 |

