# Картинки для сцены боя: что нужно и промпты

Спрайты героев генерируются листом-линейкой — промпт и правила масштаба в `docs/test_classes.md`. Здесь остальное. Картинки рам, самоцветов и эмблем карт больше не нужны: бой картами убран (его картинки лежат в git под тегом `cards-arena`).

## Фон сцены

Папка: `assets/backgrounds/`, PNG или JPG, 1920x1080 или больше, без прозрачности. Фон выбирается в редакторе сцены (вкладка Scene) и заполняет поле с обрезкой по краям. Юниты стоят в нижних двух третях поля, по центру между отрядами нужно спокойное место для эффектов. Сейчас есть `meadow.png`.

```
wide side-view fantasy battlefield, ground plane seen slightly from above, grassy plain or castle courtyard,
distant hills or walls in the upper third, calm empty middle and foreground, painterly style, muted colours,
no characters, no text, 16:9
```

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
