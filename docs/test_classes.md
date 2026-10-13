# Вариант «статичные спрайты»: 5 тестовых классов

Идея: юниты стоят на поле, как в Unicorn Overlord, — каждый одним статичным рисунком в полный рост, без покадровой анимации. Живость дают движение спрайтов (рывок, прыжок, отскок, отбрасывание, покачивание) и эффекты. У каждой способности свой визуал.

Классы и навыки уже есть в данных, новые не нужны.

## Классы

| Класс | Роль | Почему именно он | Навыки и пассивки для визуала |
| --- | --- | --- | --- |
| Паладин (`paladin`) | танк, защитник | ближний бой, удар щитом с оглушением, магия света, лечение ряда, прикрытие союзника | attack, shield_bash, smite, group_heal; shield_cover |
| Охотник (`hunter`) | стрелок | пять разных выстрелов: обычный, огненный, ядовитый, залп по ряду, выстрел насквозь; реакция «поддержка огнём» | shot, fire_arrow, poison_arrow, volley, piercing_shot; assist |
| Пиромант (`pyromancer`) | маг по области | снаряд, огненный шар с поджогом, огненная буря вокруг цели | magic_bolt, fireball, firestorm |
| Клирик (`cleric`) | лекарь | лечение одного, экстренное лечение как реакция на чужой урон | magic_bolt, heal; emergency_heal |
| Всадник (`rider`) | конница | таран через поле — самое заметное движение | attack, lance_charge |

Если нужен летающий юнит, его стоит добавить шестым: новый класс (например, наездник на грифоне с тегом `flying`).

## Сцена

- Два отряда сбоку, лицом друг к другу, передний ряд ближе к центру.
- Колонны формации идут в глубину: дальняя колонна выше и мельче, ближняя ниже и крупнее; ближние перекрывают дальних.
- Спрайт стоит ногами на земле, под ним тень. Противник — отражённый спрайт.
- В покое спрайт еле заметно «дышит» (сжатие на 1–2% по высоте) со сдвигом фазы, чтобы отряд не дышал хором.
- Над юнитом компактная плашка: HP, AP и PP числами, значки эффектов.

## Движения (общий набор для всех навыков)

| Движение | Что происходит |
| --- | --- |
| рывок к цели | быстрый подлёт к цели со шлейфом полупрозрачных копий, остановка перед ней |
| возврат | обратно на своё место, медленнее |
| прыжок | подъём по дуге и падение (тень остаётся на земле) |
| отскок назад | короткий шаг назад перед выстрелом |
| выпад | короткий толчок вперёд на месте |
| наклон | поворот спрайта на 5–10° вперёд в момент удара |
| отбрасывание | цель отлетает назад от удара и возвращается |
| дрожь | цель трясётся при попадании, при крите — всё поле |
| вспышка | спрайт на миг становится белым (попадание) или цветным (бафф, лечение) |
| падение | погибший заваливается назад и тает |
| парение | для летающих: покачивание над тенью |

## Визуал каждой способности

### Паладин

| Способность | Визуал |
| --- | --- |
| attack | рывок к цели, одна широкая дуга разреза, искры, возврат |
| shield_bash | рывок со щитом вперёд, удар корпусом: ударная волна, цель отбрасывается, над ней кружатся звёзды оглушения |
| smite | паладин поднимает меч, над целью раскрывается золотой круг, столб света с неба, золотые искры |
| group_heal | паладин на месте, под союзниками ряда загораются круги света, зелёно-золотые искры поднимаются |
| shield_cover (пассивка) | паладин прыжком встаёт перед союзником, полупрозрачный щит-купол, удар разбивается о него искрами |

### Охотник

| Способность | Визуал |
| --- | --- |
| shot | отскок назад, стрела навесом со следом |
| fire_arrow | стрела вспыхивает в полёте, огненный след, вспышка и угли при попадании |
| poison_arrow | зелёный след, при попадании облако яда с пузырями |
| volley | прыжок назад, охотник стреляет вверх, на весь ряд цели падает дождь стрел |
| piercing_shot | охотник замирает, блик на наконечнике, стрела проходит прямой линией насквозь через двух врагов |
| assist (пассивка) | короткий блик над охотником и быстрый выстрел по той же цели |

### Пиромант

| Способность | Визуал |
| --- | --- |
| magic_bolt | лёгкий выпад, маленькая синяя сфера |
| fireball | пиромант чуть поднимается в воздух, под ним огненный круг рун, большой огненный шар дугой, взрыв, цель отброшена и подожжена |
| firestorm | руны вспыхивают под целью, вокруг неё вырастают столбы пламени, всё поле подсвечено оранжевым |

### Клирик

| Способность | Визуал |
| --- | --- |
| magic_bolt | выпад, маленькая белая сфера |
| heal | клирик поднимает посох, на союзника падает мягкий столб света, поднимаются зелёные искры, союзник вспыхивает зелёным |
| emergency_heal (пассивка) | быстрый рывок к союзнику, золотой нимб над ним, быстрая вспышка лечения, возврат |

### Всадник

| Способность | Визуал |
| --- | --- |
| attack | короткий рывок, укол копьём, возврат |
| lance_charge | всадник отъезжает назад, затем таранит через поле со шлейфом пыли и копиями, удар: цель отброшена, искры и волна, всадник проскакивает чуть дальше и возвращается |

## Как устроено (сделано)

- **Спрайты:** `assets/units/<id класса>.png` — один рисунок на класс, нарезаны `tools/cut_lineup.py` с листа `assets/sprites_src/lineup/lineup_2.png`.
- **Визуал способностей задаётся данными:** `assets/visuals/skills.json` — для навыка шаги «когда → кто (сам, цель, все задетые) → что (движение или эффект)». Навыки без своего описания получают общий визуал по виду. Подробности — в `FEATURES.md`, раздел «Вкладка Stage».
- **Новый экран:** вкладка Stage рядом с карточной ареной (открывается кликом), со своим боем тестовых отрядов. Ветка `sprite-animation`.
- Пока не сделано из задуманного выше: звёзды оглушения при ударе щитом идут общим эффектом оглушения; «поддержка огнём» и «экстренное лечение» показываются общим визуалом пассивки и своего навыка.

## Спрайты: что сгенерировать

Главное правило для одинакового масштаба: **все пять персонажей генерируются на одном листе, в один ряд, на одной линии земли**. Если генерировать по одному, модель каждый раз растягивает персонажа на всю картинку, и пехотинец выходит размером с всадника. С листа я сам вырежу каждого в `assets/units/<id класса>.png`, сохранив их размеры друг относительно друга.

Настройки GPT Image: размер 1536x1024, качество high, прозрачный фон (в API: `background="transparent"`, `output_format="png"`; в ChatGPT — фраза про прозрачный PNG в конце промпта). Название игры в промпт не вставляю: стиль описан признаками, так результат стабильнее.

```
A single horizontal character lineup sheet for a 2D side-view fantasy tactics game: five unit sprites
standing in one row on the same flat ground line, evenly spaced with clear empty space between them,
nothing overlapping, nothing cropped.

SCALE RULES (very important):
- Everything is drawn at exactly the same scale, as if photographed together.
- Every human character is the same height: about 52% of the image height, head to feet.
- All feet touch the same horizontal ground line near the bottom edge of the image.
- The mounted lancer is taller only because of the horse: the horse's back is at the height of
  a standing human's hip-to-chest, the rider sits on top. Do not shrink the horse to fit.
- No character is enlarged or shrunk to fill its slot.

POSE: all characters face right, side view with a slight three-quarter turn toward the viewer,
calm combat-ready standing pose, full body visible, weapons held close to the body.

FROM LEFT TO RIGHT:
1. Paladin: polished silver plate armor with gold trim, white tabard, large kite shield on the
   left arm, longsword in the right hand, short hair, determined expression.
2. Hunter: green hooded leather armor and a short cape, longbow in the left hand, quiver on the
   back, light boots, alert stance.
3. Pyromancer: crimson and black robes with gold embroidery, long sleeves, wooden staff topped
   with a glowing ember crystal.
4. Cleric: young healer in white and pale blue robes with a gold sash, ornate staff with a small
   sun emblem, gentle expression.
5. Mounted lancer: knight in a blue surcoat over chainmail riding a brown warhorse, long lance held
   upright, the whole horse in side view facing right.

STYLE: hand-painted 2D fantasy illustration in the manner of premium Japanese console tactics RPGs,
delicate ink linework, soft painterly cel shading, rich but slightly muted colors, ornate detailed
armor and flowing cloth, elegant slightly elongated proportions (head about 1/7 of body height),
warm rim light, crisp clean silhouettes.

OUTPUT: transparent background PNG, no ground, no shadow, no scenery, no text, no labels, no frame.
```

Если масштаб всё равно сбился, лучше исправлять правкой этого же листа, чем генерировать заново:

```
Keep everything exactly the same, only fix the scale: make the horse and rider smaller so that the
rider's head is at about 75% of the image height, and keep all humans the same height.
```

Новые классы потом рисуются на новом листе, но **с паладином из первого листа как эталоном** (приложить первый лист картинкой):

```
Using the attached lineup as the scale and style reference, draw a new lineup sheet with the
paladin from the reference on the far left at exactly the same size, followed by: <новые персонажи>.
Same ground line, same scale rules, same style, transparent background.
```

Паладина с нового листа я выброшу: он нужен только для того, чтобы новые персонажи совпали по росту со старыми.
