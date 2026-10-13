# Картинки для сцены боя: что нужно и промпты

Всё, что нужно для визуализации боя: юниты, спрайтовые эффекты, земля, задники, оружие. Объекты-декорации пока не делаем. Генерация — GPT Image (размеры 1024x1024, 1536x1024, 1024x1536; качество high).

Общий блок стиля для юнитов и эффектов (так выглядит второй лист героев: чистый контур, cel-заливка):

```
STYLE: clean 2D fantasy game art in the manner of modern Japanese tactics RPGs, crisp dark ink
outlines, cel shading with two or three tones, soft highlights, rich but slightly muted colors,
consistent with the attached reference sheet.
```

К каждому промпту юнитов прикладывайте картинкой `assets/sprites_src/lineup/lineup_2.png` — модель держит стиль и рост по образцу.

## 1. Юниты — листы-линейки

Сделано: листы A, B и C нарисованы по этим промптам и нарезаны — свои спрайты есть у всех 15 классов. Промпты ниже — для новых классов и перерисовки: на каждом листе первым стоит паладин с образца — эталон роста, при нарезке его выбрасываем.

Нарезка: `python tools/cut_lineup.py <лист> _ref <id> <id> ... --reference _ref` — паладин-эталон (`_ref`) задаёт рост человека на листе и в файлы не попадает. Например, лист A: `python tools/cut_lineup.py assets/sprites_src/lineup/lineup_a.png _ref knight fighter spearman orc --reference _ref`. Если персонажи стоят почти вплотную — `--gap 1`.

Общая часть промпта листа (1536x1024, прозрачный фон):

```
Using the attached lineup as the scale and style reference, draw a new horizontal lineup sheet of
full-body unit sprites standing in one row on the same flat ground line, evenly spaced, nothing
overlapping or cropped. Far left: the paladin from the reference at exactly the same size.

SCALE RULES: everything at exactly the same scale as the reference, as if photographed together.
A normal human is as tall as the paladin. All feet touch the same ground line near the bottom edge.
No character is enlarged or shrunk to fill its slot.

POSE: all face right, side view with a slight three-quarter turn toward the viewer, calm
combat-ready stance, weapons held close to the body.

FROM LEFT TO RIGHT:
1. The paladin from the reference (unchanged).
<персонажи>

<STYLE>

OUTPUT: transparent background PNG, no ground, no shadow, no scenery, no text, no labels.
```

**Лист A — пехота:**
```
2. Knight (knight): heavy full plate armor in steel and dark blue, closed great helm with a plume,
   longsword and a large heater shield, broader and heavier than the paladin, same height.
3. Fighter (fighter): light leather and chain armor, red scarf, one-handed sword, agile stance,
   no shield, same height as a human.
4. Spearman (spearman): brigandine armor, round helmet, long spear held upright, small buckler on
   the back, same height as a human (the spear rises above the head).
5. Orc (orc): green-skinned muscular orc warrior in crude iron and leather armor, heavy two-handed
   war axe, hunched; about 115% of a human's height and much broader.
```

**Лист B — стрелки и ловкие:**
```
2. Archer (archer): light leather armor, short cape, simple longbow, quiver on the hip, short hair,
   human height, simpler outfit than a hunter.
3. Goblin (goblin): small green goblin skirmisher with big ears, ragged leather, rusty dagger in
   each hand, crouched; only about 65% of a human's height.
4. Mage (mage): blue robes with silver trim, pointed wide-brim hat, oak staff with a blue crystal,
   human height (the hat may rise above).
5. Witch (witch): dark purple and black dress, tattered hooded cloak, crooked staff with a green
   glowing skull charm, pale skin, human height.
```

**Лист C — стихийные маги:**
```
2. Cryomancer (cryomancer): white and icy-blue layered robes with fur collar, staff topped with an
   ice crystal, frost patterns on the cloth, human height.
3. Stormcaller (stormcaller): dark blue and gold robes, storm-grey cape, staff with a forked metal
   head crackling with small sparks, human height.
```

Если масштаб сбился — правка того же листа: `Keep everything exactly the same, only fix the scale: <кого> must be <во сколько раз> the paladin's height.`

## 2. Эффекты — спрайты с анимацией

Состояние: одиночные картинки, оружие, плитки земли и дополнительные элементы — нарисованные (вырезаны из коллажей). Покадровые анимации (`hit_spark`, `fire_burst`, `heal` и др.) пока скриптовые: в коллаже их кадры около 65 пикселей, нужны оригиналы 1024x1024. Задники — миниатюры, нужны оригиналы 1536x1024. **Присылайте отдельные файлы, а не коллажи:** из коллажа картинка достаётся в 4–15 раз меньше. Промпты ниже годятся, чтобы перерисовать их по одному — файл с тем же именем просто заменяет старый, описание в `effects.json` остаётся. Земля и задники из того же набора тоже скриптовые; оружие из него не подключено (прежнее лучше).

### Как лучше делать

Эффект — картинка (или покадровая анимация), которая накладывается на юнита или летит между юнитами. Движок уже умеет ставить её в мир и сортировать по глубине, поэтому эффект лежит перед юнитом, за ним или обвивает его.

**Два вида эффектов** — это главное, иначе генерация будет мучением:
1. **Покадровая анимация (флипбук)** — для «хаотичных» эффектов: огонь, взрыв, дым, искры, вспышка магии, ядовитое облако, вода, электричество. Генератор не умеет рисовать идеально согласованные кадры, но у хаотичных эффектов это и не нужно: глаз видит «живое пламя». Лист — сетка кадров: **1024x1024, 4x4 = 16 кадров по 256x256**, по порядку слева направо, сверху вниз, от зарождения до исчезновения.
2. **Одиночная картинка, которую оживляет движок** — для эффектов с чёткой формой: дуга разреза, росчерк выпада, кольцо, круг рун, столб света, купол щита, стрела, звёзды оглушения. Генератор рисует одну красивую картинку, а движок её раскрывает по дуге, растягивает, вращает, гасит. Так форма не «прыгает» между кадрами.

**Фон.** Светящиеся эффекты (огонь, свет, молния, магия, искры) — **на чистом чёрном фоне**: движок рисует их сложением цветов, чёрное становится прозрачным, края светятся без ореолов. Непрозрачные (дым, пыль, яд, тьма, осколки льда, кровь) — **на прозрачном фоне**.

**Как это подключается** (предлагаемый формат, движок под него допишу, когда появятся картинки):
- файлы `assets/fx/<id>.png`, описание в `assets/fx/effects.json`:
  `"fire_burst": {"grid": [4, 4], "frames": 16, "fps": 24, "size": 160, "blend": "add", "layer": "front", "anchor": "body", "loop": false}`
  - `size` — высота в единицах мира (рост человека 185);
  - `blend` — `add` (чёрный фон) или `alpha` (прозрачный);
  - `layer` — `front` (перед юнитом), `back` (за юнитом), `ground` (лежит на земле в перспективе), `wrap` (два файла `<id>_back.png` и `<id>_front.png` — за и перед юнитом);
  - `orient` — `facing` (отражать по стороне атакующего), `travel` (поворачивать по направлению полёта — снаряды, лучи);
  - для одиночной картинки `"animate": "sweep" | "grow" | "spin" | "pulse" | "stretch"`;
- в визуале навыка шаг `{"do": "sprite", "fx": "fire_burst", "who": "target", "on": "body", "at": 0, "scale": 1.2}`, снаряд — `{"do": "projectile", "sprite": "fireball", ...}`.
- кодовые эффекты остаются запасными: пока картинки нет, рисуется нынешний эффект.

**После генерации:** проверить, что кадры идут по порядку и эффект не обрезан краем кадра; лишний фон у `alpha`-эффектов удалить. Инструмент нарезки сетки с выравниванием кадров по центру яркости и превью-полоской я сделаю вместе с подключением.

### Общая часть промптов эффектов

Флипбук (1024x1024):

```
2D game visual effect sprite sheet: a 4x4 grid of 16 equal square frames (256x256 each), read left
to right, top to bottom, showing one continuous animation from start to finish: <эффект>.
The effect is centered in every frame, fully inside the frame, same scale in all frames, no camera
movement. <ФОН>
<STYLE>
No text, no frame borders, no grid lines, no characters.
```

Одиночная картинка (1024x1024):

```
2D game visual effect, single image: <эффект>. Centered, fully inside the image, crisp shape,
<ФОН>
<STYLE>
No text, no characters.
```

`<ФОН>`: для `add` — `pure black background, the effect glows`; для `alpha` — `transparent background PNG`.

### Список эффектов

Флипбуки:

| Файл | Где | blend, layer | `<эффект>` |
| --- | --- | --- | --- |
| `hit_spark.png` | любое попадание оружием | add, front | `a sharp impact flash with white-yellow sparks bursting outward and fading` |
| `blunt_impact.png` | дробящие удары, удар щитом | add, front | `a heavy impact shockwave star with a dust ring and flying pebbles` |
| `fire_burst.png` | огненный шар, огненная стрела | add, front | `a fiery explosion: bright core, expanding orange flames and embers, dissipating smoke wisps` |
| `fire_pillar.png` | огненная буря | add, wrap | `a tall column of fire erupting from the ground, rising, roaring and dying down` |
| `burning.png` | эффект «горение» (зацикленный) | add, front, loop | `small flames licking upward over a body area, looping seamlessly` |
| `fireball.png` | снаряд огненного шара (зацикленный) | add, front, travel | `a flying fireball with a flickering flame tail pointing left, looping` |
| `ice_burst.png` | ледяной осколок, буран | alpha, front | `ice crystals shattering outward with frost mist and sparkling shards` |
| `blizzard.png` | буран по всему полю | alpha, front | `swirling snow and icy wind gusts sweeping across, looping` |
| `lightning_strike.png` | удар молнии | add, front | `a jagged lightning bolt striking down from the top edge, bright flash, crackling arcs, fading` |
| `chain_arc.png` | цепная молния между целями | add, travel | `a horizontal crackling electric arc stretching from left to right, flickering` |
| `holy_burst.png` | кара | add, front | `a radiant golden holy burst with light rays and floating feathers of light` |
| `heal.png` | лечение | add, wrap | `soft green and gold healing light rising upward with small leaves and sparkles` |
| `buff.png` | баффы, боевой клич, сплочение | add, wrap | `golden aura flames rising around a figure with upward sparkles` |
| `debuff.png` | дебаффы | alpha, front | `a curling purple-black cursed mist with faint runes, sinking downward` |
| `poison_cloud.png` | яд, ядовитая стрела | alpha, front | `a green toxic bubbling gas cloud with popping bubbles, looping` |
| `plague.png` | чума | alpha, front | `dark sickly smoke with tiny flies and greenish glow` |
| `wind_blade.png` | зачарование ветром | alpha, wrap | `swirling pale-green wind ribbons spiraling upward around a figure` |
| `dust_cloud.png` | разгон всадника, приземление | alpha, ground | `a low dust cloud kicked up from the ground, spreading sideways and settling` |
| `death_smoke.png` | гибель | alpha, front | `a puff of grey smoke with fading sparkles, dissipating upward` |
| `arcane_burst.png` | магическая стрела | add, front | `a blue arcane energy pop with small glyph fragments` |
| `magic_orb.png` | снаряд магии (зацикленный) | add, front | `a glowing blue magic orb pulsing with a short swirling tail, looping` |

Одиночные картинки (оживляет движок):

| Файл | Где | blend, анимация | `<эффект>` |
| --- | --- | --- | --- |
| `slash.png` | режущие удары | add, sweep | `a single wide crescent sword slash arc, bright white core fading to blue at the tips, motion streaks` |
| `slash_heavy.png` | топор, сокрушающий удар | add, sweep | `a thick heavy crescent axe slash arc, orange-white core, sparks along the edge` |
| `thrust.png` | колющие, копьё, таран | add, stretch | `a straight horizontal piercing thrust streak, sharp pointed tip on the right, speed lines` |
| `arrow.png` | все стрелы | alpha, travel | `a single wooden arrow with grey fletching, horizontal, tip pointing right` |
| `fire_arrow_trail.png` | огненная стрела | add, travel | `a short horizontal fire trail with embers, thicker on the right` |
| `ice_shard.png` | снаряд ледяного осколка | alpha, travel | `a sharp jagged ice shard projectile, horizontal, point to the right` |
| `rune_circle.png` | круги рун под ногами | add, spin, ground | `a circular magic rune circle seen from above, thin glowing lines, runes around the edge, inner triangle` |
| `ring_wave.png` | ударные волны | add, grow, ground | `a thin glowing circular shockwave ring seen from above, soft edge` |
| `light_pillar.png` | лечение, кара | add, pulse | `a tall vertical pillar of soft light from top to bottom, brighter center, soft edges` |
| `shield_dome.png` | прикрытие, защита | add, pulse, wrap | `a translucent hexagonal energy shield dome, glowing blue edges` |
| `stun_stars.png` | оглушение (крутится над головой) | alpha, spin | `a small ring of five cartoon yellow stars` |
| `glint.png` | прицеливание, блик | add, pulse | `a sharp four-pointed star glint` |
| `crit.png` | критический удар | add, grow | `a bold jagged starburst impact shape, white-yellow` |

Порядок, если делать не всё сразу: `hit_spark`, `slash`, `thrust`, `fire_burst`, `heal`, `rune_circle`, `light_pillar`, `lightning_strike`, `ice_burst`, `poison_cloud`, `buff`, `debuff`, `shield_dome`, `stun_stars` — это закрывает почти все навыки демонстрации.

## Земля и задник: как ложатся в сцену

Земля — плитка, которую движок сам кладёт на плоскость в перспективе и повторяет. Задник — далёкий пейзаж за краем земли: его линия земли ставится на дальний край поля. Поэтому земля рисуется **строго сверху, без перспективы**, а задник — **без переднего плана**.

Блок стиля в конец каждого промпта земли и задника (живописнее, чем у юнитов: фон не должен спорить с фигурами):

```
hand-painted 2D fantasy illustration in the manner of premium Japanese console tactics RPGs,
painterly texture, soft natural light, rich but slightly muted colors, no text, no characters
```

## 3. Земля — плитки текстур

Папка: `assets/grounds/`, PNG 1024x1024, без прозрачности. Выбирается в редакторе сцены (вкладка «Макет», страница «Земля»); там же размер плитки в единицах мира (рост человека 185: плитка 160–250 обычно выглядит естественно).

Требования, без которых будет видно шов или «ковёр»:
- бесшовная по всем четырём краям (seamless, tileable);
- вид строго сверху (orthographic top-down), без перспективы и горизонта;
- ровное освещение без пятна света и виньетки, без теней от предметов;
- без крупных приметных деталей (одинокий камень будет повторяться рядами) — мелкие детали равномерно.

Промпт (перед блоком стиля):

```
seamless tileable ground texture, orthographic top-down view, flat even lighting, no perspective,
no horizon, no vignette, no large unique features, small details evenly distributed, 1024x1024,
<покрытие>
```

| Файл | `<покрытие>` |
| --- | --- |
| `meadow.png` | `short green meadow grass with tiny wildflowers and a few small pebbles` |
| `dirt.png` | `trampled brown dirt with small stones and sparse dry grass tufts` |
| `cobblestone.png` | `old grey cobblestone pavement with moss in the gaps` |
| `flagstone.png` | `large worn castle courtyard flagstones, beige and grey` |
| `sand.png` | `fine desert sand with soft wind ripples and scattered small rocks` |
| `snow.png` | `packed snow with light footprints and a few ice patches` |

Если шов всё же виден: попросите модель «make the texture seamless, fix the edges so it tiles», или проверьте, разложив картинку 2x2.

## 4. Задники

Папка: `assets/backgrounds/`, PNG или JPG, 2560x1080 (21:9) или шире, без прозрачности. Выбирается на странице «Задник»; там же «Линия %» — на какой высоте картинки (в % от верха) её земля встречается с полем боя, и ширина задника.

Требования:
- только дальний план: небо и далёкий пейзаж (холмы, лес, стены замка, горы);
- ровная, почти горизонтальная линия, где дальняя земля уходит к полю, на 70–75% высоты; ниже неё — спокойная земля без деталей (её закроет поле);
- без переднего плана, без персонажей, без крупных объектов у нижнего края;
- взгляд немного сверху, как на поле боя.

Промпт (перед блоком стиля):

```
wide panoramic distant landscape backdrop for a side-view battle scene, camera slightly above,
only far background: sky and <пейзаж>, the distant ground meets a flat even plain at about 72% of
the image height, the bottom quarter is a plain empty field with no details, no foreground objects,
21:9 panorama
```

| Файл | `<пейзаж>` |
| --- | --- |
| `hills.png` | `rolling green hills, small distant forests and a village on the horizon, soft morning clouds` |
| `castle.png` | `tall stone castle walls and towers in the distance, banners, warm afternoon light` |
| `forest.png` | `edge of a dark pine forest and misty mountains behind it` |
| `desert.png` | `distant sand dunes and ancient ruins under a hot hazy sky` |
| `winter.png` | `snowy mountains and frozen pine forest under a pale winter sky` |

Сейчас есть `meadow.png` (бывший фон карт): его линия земли примерно на 70%.

## 5. Оружие в атаках — 8 штук

Папка: `assets/weapons/<вид>.png`, около 256x256, прозрачный фон. Оружие вертикально, остриём или верхом вверх, по центру. Показывается шагом `weapon` визуала навыка; какое оружие, код берёт из надетого предмета, иначе из оружейного слота класса.

| Файл | Слоты | Промпт |
| --- | --- | --- |
| `sword.png` | light_sword | `single straight longsword, vertical, blade pointing up, gold crossguard, leather grip` |
| `axe.png` | heavy_weapon | `single battle axe, vertical, head at the top, wooden haft` |
| `spear.png` | lance | `single long spear, vertical, leaf-shaped steel tip at the top` |
| `dagger.png` | dagger | `single short dagger, vertical, blade pointing up` |
| `bow.png` | bow | `single wooden recurve longbow, vertical, string on the left side` |
| `staff.png` | staff | `single wizard staff, vertical, glowing blue crystal at the top` |
| `shield.png` | прикрытие | `single kite shield, front view, blue field with gold cross` |
| `fist.png` | без оружия | `armoured gauntlet fist, front view` |

Блок стиля в конец каждого промпта оружия:

```
hand-painted 2D fantasy game asset, clean ink linework, soft cel shading, crisp edges, centered,
no text, transparent background
```

## 6. Открытый мир — объекты карты

Папка: `assets/world/<имя>.png`, прозрачный фон, объект стоит на нижнем крае картинки (там земля), вид сбоку-сверху, как юниты. Сейчас там заглушки (`tools/make_world_placeholders.py`); файл с тем же именем заменяет заглушку. Размер в мире задаётся в карте (`size` — высота объекта), поэтому картинки можно рисовать в любом разрешении, лучше 1024 по большей стороне.

Общая часть промпта (1024x1024, прозрачный фон):

```
2D fantasy overworld map object sprite for a tactics RPG, seen from a three-quarter top-down side view,
<объект>, standing on an invisible ground line at the bottom edge, centered, full object visible,
no ground patch, no shadow, no text.
<STYLE>
transparent background PNG
```

| Файл | `<объект>` |
| --- | --- |
| `town.png` | `a small medieval town: half-timbered houses with red roofs around a bell tower, low stone wall` |
| `fort.png` | `a compact stone fort with two square towers, battlements, wooden gate and a blue banner` |
| `ruins.png` | `ancient overgrown temple ruins: broken columns, a fallen arch, moss and ivy` |
| `chest.png` | `a closed wooden treasure chest with iron bands and a gold lock` |
| `chest_open.png` | `the same treasure chest, open and empty` |
| `tree.png` | `a single tall pine tree` |
| `rock.png` | `a large mossy boulder` |

Чтобы объекты совпали по стилю с юнитами, прикладывайте `assets/sprites_src/lineup/lineup_2.png` как образец стиля.

## 7. Интерфейс — иконки, портреты и фоны (окно башни)

Папка: `assets/ui/<ключ>.png`. Ключ идёт от частного к общему, картинка ищется по самому точному ключу, который есть (`pygame_art.py`):

| Ключ | Что это | Если файла нет |
| --- | --- | --- |
| `item/<слот>/<id предмета>` | иконка предмета, например `item/bow/hero_bow.png` | `item/<слот>.png`, затем общая `item.png` |
| `skill/<id>`, `passive/<id>` | значок навыка и пассивки, например `skill/fireball.png` | `skill.png`, `passive.png` |
| `stat/<стат>` | значок стата, например `stat/initiative.png` | `stat.png` (белый ромб, окрашивается цветом стата) |
| `icon/<имя>` | значки интерфейса: `gold`, `floor`, `boss`, `exp`, `level` | `icon.png` |
| `portrait/<класс>` | портрет класса, квадрат | верхняя часть спрайта класса из `assets/units`, затем `portrait.png` |
| `bg/<экран>` | фон экрана: `draft`, `prepare`, `reward`, `shop`, `over`, `tactics` | `bg.png` |

Сейчас в папке только общие заглушки (`tools/make_ui_placeholders.py`). Можно рисовать по одной картинке на слот (`item/bow.png` сразу даст иконку всем лукам) и постепенно уточнять до отдельных предметов. Код менять не нужно.

Общая часть промпта иконки (512x512, прозрачный фон):

```
2D fantasy RPG inventory icon, <предмет>, single object centered, slight three-quarter view,
bold readable silhouette, clean ink outline, soft cel shading, no background, no frame, no text.
<STYLE>
transparent background PNG
```

Цвет тира рисовать не надо: рамку цвета тира рисует интерфейс. Тиры различаются материалом: новичок — дерево, кожа, железо; наёмник — сталь, бронза; герой — серебро, золото, свечение.

| Ключ | `<предмет>` |
| --- | --- |
| `item/light_sword.png` | `a one-handed straight steel sword` |
| `item/light_shield.png` | `a round wooden shield with an iron rim` |
| `item/bow.png` | `a recurve hunting bow` |
| `item/staff.png` | `a wooden mage staff with a glowing crystal` |
| `item/dagger.png` | `a short curved dagger` |
| `item/heavy_weapon.png` | `a heavy two-handed battle axe` |
| `item/lance.png` | `a long cavalry lance with a pennant` |
| `item/light_armor.png` | `a leather jerkin` |
| `item/medium_armor.png` | `a chainmail shirt` |
| `item/robe.png` | `a mage robe with embroidered hem` |
| `item/artifact/*_pendant.png` | `a heart-shaped red gem pendant` |
| `item/artifact/*_brooch.png` | `an ornate brooch with a red stone` |
| `item/artifact/*_ring.png` | `a heavy iron signet ring` |
| `item/artifact/*_rune.png` | `a glowing violet rune stone` |
| `item/artifact/*_amulet.png` | `a blue protective amulet` |
| `item/artifact/*_feather.png` | `a single bright cyan feather` |
| `item/artifact/*_lens.png` | `a brass monocle lens` |
| `item/artifact/*_ribbon.png` | `a flowing green silk ribbon` |
| `item/artifact/*_fang.png` | `a sharp beast fang on a cord` |
| `item/artifact/*_claw.png` | `a curved dragon claw` |
| `item/artifact/*_emblem.png` | `a bronze shield-shaped emblem` |
| `skill.png`, `passive.png` | `a round skill badge with a <символ навыка>` — по одному на навык, символ из названия навыка |
| `icon/floor.png`, `icon/boss.png` | `a stone tower icon`, `a horned skull icon` |

Звёздочка `*` — три файла на артефакт: `novice_`, `mercenary_`, `hero_` (например `item/artifact/hero_feather.png`).

Портреты (`portrait/<класс>.png`, 512x512) нужны, только если вырезка из спрайта не нравится. Голова и плечи, взгляд вправо, тот же стиль, что у листа юнитов. Подправить вырезку без новой картинки можно в `assets/units/units.json`: `"portrait": [центр x, верх, размер]` в долях картинки спрайта.

Фоны экранов (`bg/<экран>.png`, 1920x1280, без прозрачности): тёмные и спокойные, без деталей в центре, потому что поверх лежат панели.

```
dark atmospheric fantasy background for a game menu, <место>, muted colors, soft vignette, low detail
in the middle, no characters, no text
<STYLE>
```

| Ключ | `<место>` |
| --- | --- |
| `bg/draft.png` | `a mercenary guild hall with banners at night` |
| `bg/prepare.png` | `the inside of a stone tower, torches and a war table` |
| `bg/reward.png` | `a treasure room with scattered gold` |
| `bg/shop.png` | `a merchant tent with weapons on racks` |
| `bg/over.png` | `a ruined tower under a red sky` |

## 8. Рамки и окна интерфейса (9-slice)

Папка: `assets/ui/frame/<вид>.png`. Рамка растягивается по девяти частям: четыре угла рисуются как есть, края тянутся только вдоль, середина — во все стороны. Поэтому одна картинка 512x512 подходит для панели любого размера. Пока файла нет, рамка рисуется кодом.

| Файл | Где используется | Размер картинки |
| --- | --- | --- |
| `frame/panel.png` | большие панели (отряд, враги, списки) | 512x512 |
| `frame/header.png` | шапка панели под заголовком | 512x128 |
| `frame/card.png` | карточки и строки списков | 512x256 |
| `frame/slot.png` | ячейки иконок предметов и портретов | 256x256 |
| `frame/button.png`, `button_hover.png`, `button_selected.png`, `button_primary.png`, `button_disabled.png` | кнопки по состояниям | 512x160 |

Как генерировать, чтобы рамку можно было сразу использовать:

1. Каждый элемент — отдельной картинкой. Не макет экрана целиком: из него элементы чисто не вырезать, и в них «запекается» текст.
2. Вид строго спереди, без перспективы. Рамка занимает весь холст от края до края, снаружи прозрачно.
3. Украшения только в четырёх углах. Прямые края между углами — ровные и одинаковые по всей длине, без узоров посередине: середину края будем растягивать.
4. Середина — ровная тёмная заливка без текстуры, градиента и виньетки (тоже растягивается).
5. Толщина рамки одинаковая со всех сторон: в промпте задаётся в пикселях (например, 64). Точно генератор не попадёт; я измерю и запишу в `assets/ui/frames.json` (`{"panel": {"border": 64, "scale": 0.5}}`, `scale` — во сколько раз рисовать край на экране).
6. Сначала сделайте `panel.png`. Остальные элементы просите правкой этой же картинки («the same frame, but …»): так сохраняется стиль.
7. Без текста, иконок и теней, выходящих за рамку.

Общий промпт (подставить `<элемент>` и размер):

```
UI frame element for a fantasy tactics RPG, in the style of Unicorn Overlord menus: dark navy blue panel
with ornate gold trim. <элемент>. Flat front view, no perspective, centered, the frame fills the whole canvas
edge to edge. The border is exactly 64 px thick on every side; decorative ornaments only in the four corners;
the straight edges between the corners are plain and uniform so they can be stretched; the center is a flat,
even dark navy fill with no texture, gradient or vignette. No text, no icons, no drop shadow outside the frame.
Transparent background outside the frame. <размер> PNG.
```

| Файл | `<элемент>` |
| --- | --- |
| `panel.png` | `a large window panel with a double gold border and small filigree corners` |
| `header.png` | `a horizontal title bar: navy band with a thin gold line along the bottom edge, small gold end caps` |
| `card.png` | `a list card with a thin single gold border and small cut corners` |
| `slot.png` | `a square item slot with a thick bevelled gold frame and a dark recessed center` |
| `button.png` | `a wide button with cut corners and a thin gold border` |
| `button_hover.png` | `the same button, slightly brighter fill and a brighter gold border` |
| `button_selected.png` | `the same button, deep amber fill, bright gold border` |
| `button_primary.png` | `the same button, rich gold fill with darker gold border` |
| `button_disabled.png` | `the same button, desaturated grey-blue, dim border` |

Цвет тира у ячеек предметов (серый, синий, оранжевый) интерфейс дорисует сам тонкой линией внутри `slot.png`, поэтому ячейку делайте нейтральной.
