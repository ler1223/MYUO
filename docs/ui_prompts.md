# Промпты интерфейса башни (стиль Unicorn Overlord)

Полный набор картинок интерфейса: рамки, кнопки, ячейки, полосы, клетки поля, значки и фоны. Промпты на английском: генератор понимает его точнее.

## Как пользоваться

1. Один запрос — один лист с 10 элементами. ChatGPT за ответ выдаёт одну картинку: 1024x1024, 1536x1024 или 1024x1536. Поэтому 10 элементов идут на одном листе 1536x1024 в сетке 5 колонок x 2 ряда. Я режу лист по ячейкам и привожу каждый элемент к нужному размеру (колонка «Итог»).
2. К каждому запросу прикладывайте 1–2 скриншота меню Unicorn Overlord и пишите первой строкой `Match the art direction of the attached screenshots, but do not copy any text, logo or exact artwork.` Без примера генератор скатывается в «мобильный» стиль: толстые блестящие рамки, камни, свечение.
3. В начало каждого запроса вставляйте блок STYLE и блок SHEET, затем список ячеек батча.
4. Если элемент вышел плохо, перегенерируйте только его: «Redo cell 7 only, keep everything else identical».
5. Готовые листы кладите в `assets/ui/sheets/` с именем батча (`b1_panels.png` и т. д.). Я нарежу и подключу. Картинки, которых пока нет в коде (подсказка, вкладки, клетки поля, плашки), подключу при нарезке.

Фоны (батч 8) — каждый отдельным запросом в размере 1536x1024, без сетки.

Запросы можно отправлять скриптом `tools/gen_ui_image.py`: он собирает промпт из этого файла и обращается к OpenAI Images API (gpt-image). Нужна переменная окружения `OPENAI_API_KEY`; запросы платные, промпт и образцы уходят в OpenAI.

```
python tools/gen_ui_image.py --list                                 что можно сгенерировать
python tools/gen_ui_image.py --batch 1 --dry-run                    показать промпт без запроса
python tools/gen_ui_image.py --batch 1 --ref ref/uo_menu.png        лист батча по образцу скриншота
python tools/gen_ui_image.py --batch 1 --force --extra "Redo cell 7 only, keep everything else identical."
python tools/gen_ui_image.py --background bg/prepare                фон экрана
```

Лист сохраняется в `assets/ui/sheets/`, фон — в `assets/ui/bg/`, рядом `.txt` с отправленным промптом. Готовый файл без `--force` не перезаписывается. Параметры: `--quality low|medium|high`, `--size`, `--model` (по умолчанию `gpt-image-1`).

## STYLE — общий блок стиля

```
STYLE: menu interface art for a high-fantasy tactics RPG, in the spirit of the menus of Vanillaware's
Unicorn Overlord. Refined, heraldic and calm, like an illuminated manuscript bound in midnight-blue cloth.
Surfaces: deep midnight navy and ink blue (#0d1530 to #1b2a55) with a very subtle woven-cloth / vellum grain,
never glossy. Ornament: antique matte gold leaf (#c9a45c, shadows #7a5f2e), drawn as thin double hairlines
(2-3 px) with restrained filigree; fleur-de-lis, acanthus scroll tips and small diamond studs only at corners
and centers of edges. Secondary accents: ivory (#efe6cf) and deep crimson (#7a1f24), used sparingly.
Hand-painted 2D look with crisp clean edges. Flat front view, no perspective, no 3D bevel, no plastic shine,
no chrome, no neon glow, no lens flare, no gemstones unless asked, no sci-fi or mobile-game chunky frames.
Elegant restraint: thin lines, generous calm empty space, nothing cluttered.
```

## SHEET — общий блок раскладки листа

```
SHEET: one image, 1536x1024, fully transparent background. Divide it into an invisible grid of 5 columns and
2 rows; each cell is about 300x500 px. Draw exactly one element per cell, centered in its cell, with at least
30 px of empty transparent space around it; elements never touch or overlap. Cells are numbered left to right,
top to bottom: 1-5 on the top row, 6-10 on the bottom row. Draw only what is listed, no labels, no numbers,
no text, no letters, no icons unless the cell asks for one, no drop shadow outside the element.
For every FRAME element: decoration only in the four corners (and optionally a small motif at the middle of
each edge); the straight parts of the edges between them are plain and uniform; the inner area is a flat even
fill with no texture, gradient or vignette - these parts will be stretched to any size.
```

Почему так: рамки растягиваются по девяти частям. Углы рисуются как есть, края тянутся вдоль, середина — во все стороны. Узор посреди края или градиент в центре при растяжении «поплывут».

---

## Батч 1 — окна и панели (`b1_panels.png`)

```
<STYLE>
<SHEET>
Cell 1: FRAME, large window panel, 280x280: navy fill, double thin gold border (outer line 3 px, inner line
1 px, 8 px apart), small filigree corners with a fleur-de-lis, border band 40 px.
Cell 2: FRAME, small inset panel, 220x220: slightly darker navy fill, single thin gold line, tiny diamond
studs in the corners, border band 24 px.
Cell 3: FRAME, title header bar, 280x80: navy band darker at the bottom, thin gold line along the bottom
edge, small gold scroll caps at the left and right ends, border band 28 px on the ends.
Cell 4: title banner, 280x110: ivory ribbon banner with folded ends and a fine gold edge, empty center for text.
Cell 5: FRAME, tooltip box, 240x160: very dark navy, 90 % opaque, hairline gold border with tiny corner ticks,
border band 16 px.
Cell 6: FRAME, modal dialog window, 280x280: like cell 1 but with a crimson inner hairline and a small gold
crest motif in the middle of the top edge, border band 48 px.
Cell 7: FRAME, list card, 280x110: navy fill, thin gold border with cut (chamfered) corners, border band 20 px.
Cell 8: FRAME, the same list card in the selected state: warm amber-tinted navy fill, brighter gold border,
thin ivory inner line.
Cell 9: FRAME, wide table row, 280x70: barely lighter navy fill, only a thin gold line on the top and bottom
edges, small diamond at both ends, border band 16 px.
Cell 10: the same table row in the hover state: slightly brighter fill, gold lines a little brighter.
```

| Ячейка | Файл | Итог | Край (9-slice) |
| --- | --- | --- | --- |
| 1 | `frame/panel.png` | 512x512 | 72 |
| 2 | `frame/inset.png` | 384x384 | 44 |
| 3 | `frame/header.png` | 512x128 | 48 (по бокам) |
| 4 | `frame/banner.png` | 768x192 | 96 (по бокам) |
| 5 | `frame/tooltip.png` | 384x256 | 28 |
| 6 | `frame/dialog.png` | 512x512 | 88 |
| 7 | `frame/card.png` | 512x192 | 36 |
| 8 | `frame/card_selected.png` | 512x192 | 36 |
| 9 | `frame/row.png` | 512x128 | 28 |
| 10 | `frame/row_hover.png` | 512x128 | 28 |

## Батч 2 — кнопки и вкладки (`b2_buttons.png`)

```
<STYLE>
<SHEET>
All buttons are 280x90 FRAMES with chamfered corners and a border band of 24 px, empty center (text is added
by the game).
Cell 1: normal button: navy fill, thin gold border, tiny diamond at the middle of the left and right edges.
Cell 2: hover: the same, fill one step lighter, gold border brighter.
Cell 3: pressed/selected: deep amber-brown fill, bright gold border, thin ivory inner line.
Cell 4: disabled: desaturated grey-blue fill, dim brownish border, no ornaments.
Cell 5: primary action button: rich matte gold fill with a darker gold border and an engraved inner line,
like a gilded plaque.
Cell 6: primary hover: the same gilded plaque, slightly brighter.
Cell 7: tab, inactive, 260x80: navy tab with a rounded top edge and gold line, open bottom edge.
Cell 8: tab, active: the same tab joined to the panel below, amber-navy fill, bright gold top line, small
fleur-de-lis at the top center.
Cell 9: round icon button, 140x140: navy disk with a double gold ring, empty center.
Cell 10: small square close button, 100x100: navy square with gold border and a thin gold X.
```

| Ячейка | Файл | Итог | Край |
| --- | --- | --- | --- |
| 1 | `frame/button.png` | 512x160 | 40 |
| 2 | `frame/button_hover.png` | 512x160 | 40 |
| 3 | `frame/button_selected.png` | 512x160 | 40 |
| 4 | `frame/button_disabled.png` | 512x160 | 40 |
| 5 | `frame/button_primary.png` | 512x160 | 40 |
| 6 | `frame/button_primary_hover.png` | 512x160 | 40 |
| 7 | `frame/tab.png` | 480x144 | 40 |
| 8 | `frame/tab_active.png` | 480x144 | 40 |
| 9 | `icon/round_button.png` | 128x128 | — |
| 10 | `icon/close.png` | 96x96 | — |

## Батч 3 — ячейки и рамки портретов (`b3_slots.png`)

```
<STYLE>
<SHEET>
Cell 1: FRAME, item slot, 200x200: square, dark recessed navy center, bevel-free thin double gold frame,
small cut corners, border band 28 px. Neutral: no colour accents (the game tints it by item tier).
Cell 2: the same item slot in the hover state: gold slightly brighter, faint ivory inner line.
Cell 3: the same item slot, empty: center a little darker, a faint engraved outline of a generic chest in the
middle.
Cell 4: FRAME, portrait frame, 220x220: square, thin gold double line, small fleur-de-lis on the top edge
center, border band 26 px.
Cell 5: portrait frame for the squad leader: the same frame with a small gold crown on the top edge center.
Cell 6: portrait frame for enemies: the same frame in dark crimson and blackened gold.
Cell 7: round skill frame, 160x160: gold ring with four tiny studs, empty dark center.
Cell 8: tier mark I, 80x80: small pewter-grey shield-shaped gem setting, one engraved line.
Cell 9: tier mark II, 80x80: the same setting in blue steel with two lines.
Cell 10: tier mark III, 80x80: the same setting in warm orange gold with three lines.
```

| Ячейка | Файл | Итог | Край |
| --- | --- | --- | --- |
| 1 | `frame/slot.png` | 256x256 | 36 |
| 2 | `frame/slot_hover.png` | 256x256 | 36 |
| 3 | `frame/slot_empty.png` | 256x256 | 36 |
| 4 | `frame/portrait.png` | 256x256 | 32 |
| 5 | `frame/portrait_leader.png` | 256x256 | 32 |
| 6 | `frame/portrait_enemy.png` | 256x256 | 32 |
| 7 | `frame/skill.png` | 160x160 | — |
| 8 | `icon/tier1.png` | 64x64 | — |
| 9 | `icon/tier2.png` | 64x64 | — |
| 10 | `icon/tier3.png` | 64x64 | — |

## Батч 4 — полосы, ромбики, мелкие украшения (`b4_parts.png`)

```
<STYLE>
<SHEET>
Cell 1: FRAME, horizontal gauge frame, 280x50: thin gold capsule outline with small end caps, empty dark
interior, border band 18 px on the ends.
Cell 2: gauge fill for health, 280x30: flat muted emerald green, a slightly lighter line along the top edge.
Cell 3: gauge fill for experience, 280x30: flat muted sky blue with the same top line.
Cell 4: gauge fill for enemy health, 280x30: flat muted crimson with the same top line.
Cell 5: AP pip, 70x70: small upright diamond of polished sapphire blue in a thin gold setting.
Cell 6: PP pip, 70x70: the same diamond in amethyst violet.
Cell 7: horizontal divider, 280x40: thin gold line fading out at both ends with a small fleur-de-lis in the
center.
Cell 8: corner ornament, 140x140: one gold filigree corner piece (top-left orientation), acanthus scroll.
Cell 9: leader crown, 110x110: small elegant gold crown with three points, ivory pearls.
Cell 10: lock, 90x90: small antique gold padlock.
```

| Ячейка | Файл | Итог | Край |
| --- | --- | --- | --- |
| 1 | `frame/gauge.png` | 512x64 | 24 (по бокам) |
| 2 | `bar/hp.png` | 512x32 | — (тянется) |
| 3 | `bar/exp.png` | 512x32 | — |
| 4 | `bar/enemy.png` | 512x32 | — |
| 5 | `icon/ap.png` | 48x48 | — |
| 6 | `icon/pp.png` | 48x48 | — |
| 7 | `ornament/divider.png` | 768x48 | — |
| 8 | `ornament/corner.png` | 128x128 | — |
| 9 | `icon/leader.png` | 96x96 | — |
| 10 | `icon/lock.png` | 64x64 | — |

## Батч 5 — поле отряда (`b5_field.png`)

Клетки поля видны сверху-сбоку, как сцена боя: эллипс сплюснут примерно в 3 раза.

```
<STYLE>
<SHEET>
Cells 1-5 and 7 are ground markers seen from a low three-quarter angle: a flattened ellipse, width three times
the height, about 280x95, drawn flat on the ground, slightly transparent.
Cell 1: ally tile: navy disc with a thin gold rim and a faint inner ring.
Cell 2: ally tile, highlighted: brighter navy, bright gold rim, soft inner gold haze (no glow outside).
Cell 3: enemy tile: dark crimson disc with a blackened-gold rim.
Cell 4: enemy tile, highlighted: brighter crimson, bright rim.
Cell 5: empty/locked tile: grey-blue disc with a dashed thin rim.
Cell 6: FRAME, unit name plate, 260x70: small dark navy plate, thin gold line top and bottom, tiny end caps,
border band 16 px.
Cell 7: drop marker: the ally tile with four small gold chevrons pointing inward around it.
Cell 8: the name plate for enemies: dark crimson plate with blackened-gold lines.
Cell 9: boss emblem, 120x120: small crimson heraldic shield with a gold horned skull.
Cell 10: squad banner, 120x160: small hanging navy pennant with a gold fleur-de-lis.
```

| Ячейка | Файл | Итог | Край |
| --- | --- | --- | --- |
| 1 | `field/tile_ally.png` | 384x128 | — |
| 2 | `field/tile_ally_hot.png` | 384x128 | — |
| 3 | `field/tile_enemy.png` | 384x128 | — |
| 4 | `field/tile_enemy_hot.png` | 384x128 | — |
| 5 | `field/tile_empty.png` | 384x128 | — |
| 6 | `frame/nameplate.png` | 320x80 | 20 |
| 7 | `field/tile_drop.png` | 384x160 | — |
| 8 | `frame/nameplate_enemy.png` | 320x80 | 20 |
| 9 | `icon/boss.png` | 96x96 | — |
| 10 | `icon/squad.png` | 96x128 | — |

## Батч 6 — значки статов (`b6_stats.png`)

Все значки одного вида: силуэт 120x120 в тонком круглом золотом ободке, внутри однотонная заливка своего цвета. Цвета совпадают с цветами статов в интерфейсе.

```
<STYLE>
<SHEET>
Every cell: one stat icon, 120x120: a simple symbol inside a thin round gold rim, symbol filled with its own
flat colour, readable at 24 px, no background inside the rim.
Cell 1: health - a heart, muted green (#64d278).
Cell 2: physical attack - a crossed sword and axe, orange (#f08c46).
Cell 3: physical defense - a heater shield, steel grey (#aab4c8).
Cell 4: magic attack - a star-tipped wand with sparks, violet (#be78fa).
Cell 5: magic defense - a shield with a rune, blue (#6ea0f5).
Cell 6: initiative - a winged boot, cyan (#5ad7e1).
Cell 7: accuracy - a target with an arrow, yellow (#ebd75f).
Cell 8: evasion - a feather swept sideways, teal (#6ee1af).
Cell 9: critical rate - a cracked gem with a spark, red (#f05f5f).
Cell 10: critical damage - a sword with a burst at the tip, rose (#e1788c).
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `stat/hp.png` | 96x96 |
| 2 | `stat/phys_atk.png` | 96x96 |
| 3 | `stat/phys_def.png` | 96x96 |
| 4 | `stat/mag_atk.png` | 96x96 |
| 5 | `stat/mag_def.png` | 96x96 |
| 6 | `stat/initiative.png` | 96x96 |
| 7 | `stat/accuracy.png` | 96x96 |
| 8 | `stat/evasion.png` | 96x96 |
| 9 | `stat/crit_rate.png` | 96x96 |
| 10 | `stat/crit_damage.png` | 96x96 |

## Батч 7 — значки интерфейса (`b7_icons.png`)

```
<STYLE>
<SHEET>
Every cell: one icon, 120x120, same family as before: simple symbol, thin gold outline, flat colours, readable
at 32 px, transparent around it.
Cell 1: guard rate - a raised round shield, tan (#cdb991).
Cell 2: gold - three stacked gold coins.
Cell 3: experience - a small open book with a gold star.
Cell 4: floor - a stone tower with a banner.
Cell 5: shop - a merchant's coin pouch with a ribbon.
Cell 6: inventory - a leather satchel with gold buckles.
Cell 7: squad - three small helmets side by side.
Cell 8: units - a scroll list with a quill.
Cell 9: tactics - a chess knight on a small plinth.
Cell 10: settings - a gold cog with a fleur-de-lis.
```

| Ячейка | Файл | Итог |
| --- | --- | --- |
| 1 | `stat/guard_rate.png` | 96x96 |
| 2 | `icon/gold.png` | 96x96 |
| 3 | `icon/exp.png` | 96x96 |
| 4 | `icon/floor.png` | 96x96 |
| 5 | `icon/shop.png` | 96x96 |
| 6 | `icon/inventory.png` | 96x96 |
| 7 | `icon/squad_tab.png` | 96x96 |
| 8 | `icon/units.png` | 96x96 |
| 9 | `icon/tactics.png` | 96x96 |
| 10 | `icon/settings.png` | 96x96 |

## Батч 8 — фоны экранов (каждый отдельным запросом, 1536x1024)

Фон лежит под панелями, поэтому он тёмный и спокойный. Детали — по краям, середина пустая. Я растяну его до 1920x1280 (пропорции те же, 3:2).

```
<STYLE>
Background painting for a game menu screen, 1536x1024, landscape, no transparency. <MOTIF>. Dark, low
contrast, painterly, muted colours under a deep navy veil; detail only near the edges and corners, the
central two thirds are calm and nearly empty so that interface panels can sit on top. No characters in focus,
no text, no logos, no UI elements.
```

| Файл | `<MOTIF>` |
| --- | --- |
| `bg/prepare.png` | `the war room of a castle at night: a large map table seen from a distance, banners on stone walls, candlelight` |
| `bg/unit.png` | `an armory alcove: racks of swords and shields fading into darkness, a tall arched window with moonlight` |
| `bg/draft.png` | `a mercenary guild hall: long wooden tables, hanging guild banners, warm lanterns far away` |
| `bg/reward.png` | `a treasure vault: scattered gold coins and chests catching faint golden light at the bottom edge` |
| `bg/shop.png` | `a travelling merchant's tent interior: hanging cloth, crates, weapons on racks at the sides` |
| `bg/over.png` | `a ruined tower top under a dark crimson sky, broken banners, drifting embers` |
| `bg/inventory.png` | `a quartermaster's storeroom: shelves of bundles and potions, wooden chests, a lantern` |
| `bg/battle_hud.png` | `a long dark navy cloth with a faint gold embroidered border along the top edge` (полоса под полем боя) |

## Батч 9–10 — иконки предметов

Предметы — уже по разделу 7 в `docs/art_prompts.md`. В том же формате листа:
- **Батч 9:** 10 видов снаряжения по одной иконке на слот (`item/<слот>.png`): меч, щит, лук, посох, кинжал, топор, копьё, куртка, кольчуга, мантия.
- **Батч 10:** 10 артефактов (`item/artifact/hero_<вид>.png`).

Промпт ячейки: `Cell N: inventory icon, 200x200, <предмет>, centered, slight three-quarter view, clean silhouette, no frame, no background`.

---

## Что нужно от вас

1. Скриншоты меню Unicorn Overlord, которые нравятся больше всего: расстановка отряда, экран юнита со статами и снаряжением, магазин, всплывающая подсказка. По ним я уточню палитру и толщину линий в промптах, а также перерисую запасной стиль, который рисуется кодом, пока картинок нет.
2. Готовые листы в `assets/ui/sheets/`: я нарежу, выставлю края 9-slice и подключу.
