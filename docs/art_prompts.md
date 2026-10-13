# Картинки для карт: что нужно и промпты

## Что уже подключено (набор fantasy_arena_assets)

| Что | Состояние |
| --- | --- |
| рамки 6 стилей | подключены; это перекрашенные копии одной стальной рамки — стоит перегенерировать по своим промптам, чтобы у стилей был свой орнамент |
| самоцветы AP, PP, уровня для armored, archer, caster, cavalry, flying | подключены; у armored, cavalry и эмблемы лука вычищены обрезки соседних картинок |
| `gems/level.png` и `gems/level_infantry.png` | нет: присланный `level.png` повреждён в центре; у пехоты пока самоцвет, нарисованный кодом |
| эмблемы 6, крыло, фон поля, оружие 8 | подключены |

Раскладка присланных рамок отличается от таблицы в разделе 1 (окно арта 0.19–0.81 по ширине и 0.11–0.58 по высоте, гнёзда крупнее и сдвинуты внутрь). Где на картинке рамки код пишет текст и ставит самоцветы, задаётся в `assets/cards/frames.json`, раздел `image_layout`: если новые рамки будут другой геометрии, достаточно поправить там доли.

Всё ниже уже нарисовано кодом как временная замена. Любой пункт заменяется картинкой: положите PNG в указанную папку, и арена подхватит его при следующем запуске окна. Арт персонажей (героев) сюда не входит.

## Общие требования

- Формат PNG с прозрачным фоном (кроме фона поля).
- Размеры указаны рекомендуемые: картинки масштабируются, но лучше держать пропорции.
- Генерировать серией в одной сессии и одной моделью, с одним и тем же блоком стиля, чтобы все детали подходили друг к другу.
- Если модель не умеет прозрачный фон, просите ровный однотонный фон и удаляйте его потом (например, rembg или «Удалить фон» в редакторе).

Блок стиля — дописывать в конец каждого промпта:

```
fantasy collectible card game UI asset, hand-painted, ornate but clean, polished metal and enamel,
soft rim light, high detail, crisp edges, centered, front view, no text, no letters, no numbers,
no characters, transparent background
```

## 1. Рамки карт — 6 штук

Папка: `assets/cards/frames/<стиль>.png`, размер 720x1000 (пропорция 0.72).

Рамка рисуется поверх арта, поэтому окно арта должно быть прозрачным. Поверх рамки код пишет название, теги, эффекты, HP и ставит самоцветы, поэтому соблюдайте раскладку (доли высоты карты):

| Область | Где |
| --- | --- |
| окно арта (прозрачное) | от 5% до 62% высоты, по 5% от боковых краёв |
| лента для названия | 56–67% высоты, во всю ширину, однотонная середина без рисунка |
| поле для текста | 68–85% высоты, тёмная пластина |
| гнездо самоцвета уровня | левый верхний угол, круг около 18% ширины |
| гнездо эмблемы | правый верхний угол, круг около 16% ширины |
| гнёзда AP и PP | левый и правый нижние углы, круги около 18% ширины |
| полоса HP | 87–93% высоты, по центру, половина ширины |

| Файл | Тег класса | Промпт (перед блоком стиля) |
| --- | --- | --- |
| `infantry.png` | пехота | `vertical card frame, brushed steel and dark iron, riveted plates, simple sword motifs in the corners, empty transparent window in the upper part, plain ribbon banner across the middle, dark text panel below, round empty sockets in the four corners` |
| `armored.png` | бронированный | `vertical card frame, heavy gold and bronze plate armour style, shield crests in the corners, thick bevelled border, empty transparent window in the upper part, plain ribbon banner across the middle, dark text panel below, round empty sockets in the four corners` |
| `cavalry.png` | конница | `vertical card frame, warm leather and brass, horseshoe and laurel ornaments, empty transparent window in the upper part, plain ribbon banner across the middle, dark text panel below, round empty sockets in the four corners` |
| `archer.png` | стрелок | `vertical card frame, carved dark wood with green enamel and leaves, arrow fletching ornaments, empty transparent window in the upper part, plain ribbon banner across the middle, dark text panel below, round empty sockets in the four corners` |
| `caster.png` | заклинатель | `vertical card frame, deep violet enamel and silver filigree, glowing rune engravings, star ornaments, empty transparent window in the upper part, plain ribbon banner across the middle, dark text panel below, round empty sockets in the four corners` |
| `flying.png` | летающий | `vertical card frame, pale sky blue enamel and white silver, feather ornaments along the sides, light airy design, empty transparent window in the upper part, plain ribbon banner across the middle, dark text panel below, round empty sockets in the four corners` |

Какой тег даёт какую рамку, задано в `assets/cards/frames.json` (порядок проверки: летающий, конница, бронированный, заклинатель, стрелок, пехота). Там же цвета рамок, нарисованных кодом.

## 2. Самоцветы — 3 штуки (+ по желанию 6)

Папка: `assets/cards/gems/`, размер 128x128. Число на самоцвете пишет код, поэтому центр должен быть ровным и не слишком светлым.

| Файл | Что | Промпт |
| --- | --- | --- |
| `ap.png` | AP | `round faceted sapphire gem in a gold bezel setting, deep blue, smooth center` |
| `pp.png` | PP | `round faceted amethyst gem in a gold bezel setting, deep purple, smooth center` |
| `level.png` | уровень | `diamond-shaped faceted gem in a silver setting, neutral grey crystal, smooth center` |
| `level_<стиль>.png` | уровень для рамки стиля (необязательно) | тот же промпт с цветом рамки: `golden` для armored, `green` для archer и т. д. |

## 3. Эмблемы стилей — 6 штук

Папка: `assets/cards/emblems/`, размер 128x128, круглый медальон.

| Файл | Промпт |
| --- | --- |
| `sword.png` | `round heraldic medallion with a crossed sword emblem, steel` |
| `shield.png` | `round heraldic medallion with a kite shield emblem, gold` |
| `horse.png` | `round heraldic medallion with a horse head emblem, brass` |
| `bow.png` | `round heraldic medallion with a longbow and arrow emblem, green and wood` |
| `star.png` | `round heraldic medallion with an arcane star emblem, violet and silver` |
| `wing.png` | `round heraldic medallion with a single feathered wing emblem, white and pale blue` |

## 4. Крылья летающих — 1 штука

Файл: `assets/cards/wings.png`, около 512x400. Нужно одно правое крыло; левое получается отражением. Корень крыла — в левом нижнем углу картинки, крыло раскрыто вверх и вправо.

```
single large feathered angel wing, spread open upward and to the right, wing root at the bottom left corner,
white feathers with pale blue tips, soft glow
```

## 5. Оружие в атаках — 8 штук

Папка: `assets/weapons/<вид>.png`, около 256x256. Оружие вертикально, остриём или верхом вверх, по центру. Какое оружие показывать, код берёт из надетого предмета, иначе из оружейного слота класса.

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

## 6. Фон поля боя — 1 штука

Файл: `assets/cards/background.png`, 1920x1080 или больше, без прозрачности. Карты стоят слева и справа, по центру должно оставаться спокойное место для эффектов.

```
wide side-view fantasy battlefield, grassy plain with distant hills and soft morning light, empty foreground,
calm middle area, painterly style, muted colours, no characters, no text, 16:9
```

## 7. Арт классов (герои) — делаете вы

Файл: `assets/cards/<id класса>.png`, портрет 3:4, например 720x960. Картинка заполняет окно арта с обрезкой по краям, поэтому персонажа лучше держать по центру и не прижимать к краям. Id классов: knight, archer, cleric, mage, goblin, orc, rider, fighter, spearman, hunter, pyromancer, cryomancer, stormcaller, paladin, witch.
