# Готовые запросы для генерации картинок

Собрано `python tools/build_requests.py` из `docs/uo_art_prompts.md` и `docs/ui_prompts.md` — перегенерируйте после их изменения. Файл — полный текст одного запроса: откройте, скопируйте целиком в ChatGPT, приложите образец, сохраните картинку (PNG с прозрачным фоном, 1536x1024) и выполните команду из последней колонки: она заберёт самую свежую картинку из «Загрузок» (или файл с нужным именем — его просит последняя строка запроса), положит по пути из таблицы и нарежет. Без `--cut` — только переложит и покажет команду нарезки.

Всего запросов: 22. Линейки — по порядку: `lineup_01.txt` задаёт рост и стиль, его картинка прикладывается ко всем следующим.

| Файл | Что | Приложить | Куда ляжет | Забрать и нарезать |
| --- | --- | --- | --- | --- |
| `lineup_01.txt` | Спрайты классов, лист 1 | assets/ref/lineups/uo_01_ref.png | `assets/sprites_src/lineup/uo_01.png` | `python tools/take_image.py lineup 1 --cut` |
| `lineup_02.txt` | Спрайты классов, лист 2 | assets/ref/lineups/uo_02_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_02.png` | `python tools/take_image.py lineup 2 --cut` |
| `lineup_03.txt` | Спрайты классов, лист 3 | assets/ref/lineups/uo_03_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_03.png` | `python tools/take_image.py lineup 3 --cut` |
| `lineup_04.txt` | Спрайты классов, лист 4 | assets/ref/lineups/uo_04_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_04.png` | `python tools/take_image.py lineup 4 --cut` |
| `lineup_05.txt` | Спрайты классов, лист 5 | assets/ref/lineups/uo_05_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_05.png` | `python tools/take_image.py lineup 5 --cut` |
| `lineup_06.txt` | Спрайты классов, лист 6 | assets/ref/lineups/uo_06_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_06.png` | `python tools/take_image.py lineup 6 --cut` |
| `lineup_07.txt` | Спрайты классов, лист 7 | assets/ref/lineups/uo_07_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_07.png` | `python tools/take_image.py lineup 7 --cut` |
| `lineup_08.txt` | Спрайты классов, лист 8 | assets/ref/lineups/uo_08_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_08.png` | `python tools/take_image.py lineup 8 --cut` |
| `lineup_09.txt` | Спрайты классов, лист 9 | assets/ref/lineups/uo_09_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_09.png` | `python tools/take_image.py lineup 9 --cut` |
| `lineup_10.txt` | Спрайты классов, лист 10 | assets/ref/lineups/uo_10_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_10.png` | `python tools/take_image.py lineup 10 --cut` |
| `lineup_11.txt` | Спрайты классов, лист 11 | assets/ref/lineups/uo_11_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_11.png` | `python tools/take_image.py lineup 11 --cut` |
| `lineup_12.txt` | Спрайты классов, лист 12 | assets/ref/lineups/uo_12_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_12.png` | `python tools/take_image.py lineup 12 --cut` |
| `lineup_13.txt` | Спрайты классов, лист 13 | assets/ref/lineups/uo_13_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_13.png` | `python tools/take_image.py lineup 13 --cut` |
| `lineup_14.txt` | Спрайты классов, лист 14 | assets/ref/lineups/uo_14_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_14.png` | `python tools/take_image.py lineup 14 --cut` |
| `lineup_15.txt` | Спрайты классов, лист 15 | assets/ref/lineups/uo_15_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_15.png` | `python tools/take_image.py lineup 15 --cut` |
| `lineup_16.txt` | Спрайты классов, лист 16 | assets/ref/lineups/uo_16_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_16.png` | `python tools/take_image.py lineup 16 --cut` |
| `lineup_17.txt` | Спрайты классов, лист 17 | assets/ref/lineups/uo_17_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_17.png` | `python tools/take_image.py lineup 17 --cut` |
| `lineup_18.txt` | Спрайты классов, лист 18 | assets/ref/lineups/uo_18_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_18.png` | `python tools/take_image.py lineup 18 --cut` |
| `lineup_19.txt` | Спрайты классов, лист 19 | assets/ref/lineups/uo_19_ref.png и готовый assets/sprites_src/lineup/uo_01.png (эталон роста) | `assets/sprites_src/lineup/uo_19.png` | `python tools/take_image.py lineup 19 --cut` |
| `batch_11.txt` | Батч 11: экран бойца и тактика | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b11_unit.png` | `python tools/take_image.py 11 --cut` |
| `batch_12.txt` | Батч 12: значки типов навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b12_skills.png` | `python tools/take_image.py 12 --cut` |
| `batch_13.txt` | Батч 13: иконки видов предметов | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b13_items.png` | `python tools/take_image.py 13 --cut` |
