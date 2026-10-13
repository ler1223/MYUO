# Картинки для сцены боя: что нужно и промпты

Спрайты героев генерируются листом-линейкой: промпт и правила масштаба в `docs/test_classes.md`. Здесь земля, задники и оружие. Объекты (декорации) пока не делаем.

Как это ложится в сцену: земля — плитка, которую движок сам кладёт на плоскость в перспективе и повторяет. Задник — далёкий пейзаж за краем земли: его линия земли ставится на дальний край поля. Поэтому земля рисуется **строго сверху, без перспективы**, а задник — **без переднего плана**.

Общий блок стиля в конец каждого промпта земли и задника (тот же, что у героев):

```
hand-painted 2D fantasy illustration in the manner of premium Japanese console tactics RPGs,
painterly texture, soft natural light, rich but slightly muted colors, no text, no characters
```

## Земля — плитки текстур

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

## Задники

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

## Оружие в атаках — 8 штук

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
