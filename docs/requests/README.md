# Готовые запросы для генерации картинок

Собрано `python tools/build_requests.py` из `docs/uo_art_prompts.md`, `docs/ui_prompts.md` и `docs/art_prompts.md` — перегенерируйте после их изменения. Файл — полный текст одного запроса: откройте, скопируйте целиком в ChatGPT, приложите образец, сохраните картинку (PNG с прозрачным фоном, 1536x1024) и выполните команду из последней колонки: она заберёт самую свежую картинку из «Загрузок» (или файл с нужным именем — его просит последняя строка запроса), положит по пути из таблицы и нарежет. Без `--cut` — только переложит и покажет команду нарезки.

Всего запросов: 93. Начать лучше с `batch_11.txt` (экран бойца) и первых линеек.

| Файл | Что | Приложить | Куда ляжет | Забрать и нарезать |
| --- | --- | --- | --- | --- |
| `lineup_01.txt` | Спрайты классов, лист 1 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_01.png` | `python tools/take_image.py lineup 1 --cut` |
| `lineup_02.txt` | Спрайты классов, лист 2 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_02.png` | `python tools/take_image.py lineup 2 --cut` |
| `lineup_03.txt` | Спрайты классов, лист 3 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_03.png` | `python tools/take_image.py lineup 3 --cut` |
| `lineup_04.txt` | Спрайты классов, лист 4 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_04.png` | `python tools/take_image.py lineup 4 --cut` |
| `lineup_05.txt` | Спрайты классов, лист 5 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_05.png` | `python tools/take_image.py lineup 5 --cut` |
| `lineup_06.txt` | Спрайты классов, лист 6 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_06.png` | `python tools/take_image.py lineup 6 --cut` |
| `lineup_07.txt` | Спрайты классов, лист 7 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_07.png` | `python tools/take_image.py lineup 7 --cut` |
| `lineup_08.txt` | Спрайты классов, лист 8 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_08.png` | `python tools/take_image.py lineup 8 --cut` |
| `lineup_09.txt` | Спрайты классов, лист 9 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_09.png` | `python tools/take_image.py lineup 9 --cut` |
| `lineup_10.txt` | Спрайты классов, лист 10 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_10.png` | `python tools/take_image.py lineup 10 --cut` |
| `lineup_11.txt` | Спрайты классов, лист 11 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_11.png` | `python tools/take_image.py lineup 11 --cut` |
| `lineup_12.txt` | Спрайты классов, лист 12 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_12.png` | `python tools/take_image.py lineup 12 --cut` |
| `lineup_13.txt` | Спрайты классов, лист 13 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_13.png` | `python tools/take_image.py lineup 13 --cut` |
| `lineup_14.txt` | Спрайты классов, лист 14 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_14.png` | `python tools/take_image.py lineup 14 --cut` |
| `lineup_15.txt` | Спрайты классов, лист 15 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_15.png` | `python tools/take_image.py lineup 15 --cut` |
| `batch_11.txt` | Батч 11: экран бойца и тактика | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b11_unit.png` | `python tools/take_image.py 11 --cut` |
| `batch_12.txt` | Батч 12: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b12_skills.png` | `python tools/take_image.py 12 --cut` |
| `batch_13.txt` | Батч 13: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b13_skills.png` | `python tools/take_image.py 13 --cut` |
| `batch_14.txt` | Батч 14: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b14_skills.png` | `python tools/take_image.py 14 --cut` |
| `batch_15.txt` | Батч 15: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b15_skills.png` | `python tools/take_image.py 15 --cut` |
| `batch_16.txt` | Батч 16: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b16_skills.png` | `python tools/take_image.py 16 --cut` |
| `batch_17.txt` | Батч 17: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b17_skills.png` | `python tools/take_image.py 17 --cut` |
| `batch_18.txt` | Батч 18: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b18_skills.png` | `python tools/take_image.py 18 --cut` |
| `batch_19.txt` | Батч 19: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b19_skills.png` | `python tools/take_image.py 19 --cut` |
| `batch_20.txt` | Батч 20: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b20_skills.png` | `python tools/take_image.py 20 --cut` |
| `batch_21.txt` | Батч 21: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b21_skills.png` | `python tools/take_image.py 21 --cut` |
| `batch_22.txt` | Батч 22: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b22_skills.png` | `python tools/take_image.py 22 --cut` |
| `batch_23.txt` | Батч 23: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b23_skills.png` | `python tools/take_image.py 23 --cut` |
| `batch_24.txt` | Батч 24: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b24_skills.png` | `python tools/take_image.py 24 --cut` |
| `batch_25.txt` | Батч 25: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b25_skills.png` | `python tools/take_image.py 25 --cut` |
| `batch_26.txt` | Батч 26: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b26_skills.png` | `python tools/take_image.py 26 --cut` |
| `batch_27.txt` | Батч 27: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b27_skills.png` | `python tools/take_image.py 27 --cut` |
| `batch_28.txt` | Батч 28: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b28_skills.png` | `python tools/take_image.py 28 --cut` |
| `batch_29.txt` | Батч 29: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b29_skills.png` | `python tools/take_image.py 29 --cut` |
| `batch_30.txt` | Батч 30: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b30_skills.png` | `python tools/take_image.py 30 --cut` |
| `batch_31.txt` | Батч 31: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b31_skills.png` | `python tools/take_image.py 31 --cut` |
| `batch_32.txt` | Батч 32: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b32_skills.png` | `python tools/take_image.py 32 --cut` |
| `batch_33.txt` | Батч 33: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b33_skills.png` | `python tools/take_image.py 33 --cut` |
| `batch_34.txt` | Батч 34: иконки: sword | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b34_items.png` | `python tools/take_image.py 34 --cut` |
| `batch_35.txt` | Батч 35: иконки: sword | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b35_items.png` | `python tools/take_image.py 35 --cut` |
| `batch_36.txt` | Батч 36: иконки: sword | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b36_items.png` | `python tools/take_image.py 36 --cut` |
| `batch_37.txt` | Батч 37: иконки: sword | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b37_items.png` | `python tools/take_image.py 37 --cut` |
| `batch_38.txt` | Батч 38: иконки: sword | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b38_items.png` | `python tools/take_image.py 38 --cut` |
| `batch_39.txt` | Батч 39: иконки: axe or hammer | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b39_items.png` | `python tools/take_image.py 39 --cut` |
| `batch_40.txt` | Батч 40: иконки: axe or hammer | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b40_items.png` | `python tools/take_image.py 40 --cut` |
| `batch_41.txt` | Батч 41: иконки: axe or hammer | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b41_items.png` | `python tools/take_image.py 41 --cut` |
| `batch_42.txt` | Батч 42: иконки: axe or hammer | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b42_items.png` | `python tools/take_image.py 42 --cut` |
| `batch_43.txt` | Батч 43: иконки: axe or hammer | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b43_items.png` | `python tools/take_image.py 43 --cut` |
| `batch_44.txt` | Батч 44: иконки: spear | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b44_items.png` | `python tools/take_image.py 44 --cut` |
| `batch_45.txt` | Батч 45: иконки: spear | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b45_items.png` | `python tools/take_image.py 45 --cut` |
| `batch_46.txt` | Батч 46: иконки: spear | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b46_items.png` | `python tools/take_image.py 46 --cut` |
| `batch_47.txt` | Батч 47: иконки: spear | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b47_items.png` | `python tools/take_image.py 47 --cut` |
| `batch_48.txt` | Батч 48: иконки: spear | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b48_items.png` | `python tools/take_image.py 48 --cut` |
| `batch_49.txt` | Батч 49: иконки: bow | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b49_items.png` | `python tools/take_image.py 49 --cut` |
| `batch_50.txt` | Батч 50: иконки: bow | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b50_items.png` | `python tools/take_image.py 50 --cut` |
| `batch_51.txt` | Батч 51: иконки: bow | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b51_items.png` | `python tools/take_image.py 51 --cut` |
| `batch_52.txt` | Батч 52: иконки: bow | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b52_items.png` | `python tools/take_image.py 52 --cut` |
| `batch_53.txt` | Батч 53: иконки: bow | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b53_items.png` | `python tools/take_image.py 53 --cut` |
| `batch_54.txt` | Батч 54: иконки: bow | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b54_items.png` | `python tools/take_image.py 54 --cut` |
| `batch_55.txt` | Батч 55: иконки: mage staff | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b55_items.png` | `python tools/take_image.py 55 --cut` |
| `batch_56.txt` | Батч 56: иконки: mage staff | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b56_items.png` | `python tools/take_image.py 56 --cut` |
| `batch_57.txt` | Батч 57: иконки: mage staff | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b57_items.png` | `python tools/take_image.py 57 --cut` |
| `batch_58.txt` | Батч 58: иконки: mage staff | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b58_items.png` | `python tools/take_image.py 58 --cut` |
| `batch_59.txt` | Батч 59: иконки: mage staff | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b59_items.png` | `python tools/take_image.py 59 --cut` |
| `batch_60.txt` | Батч 60: иконки: mage staff | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b60_items.png` | `python tools/take_image.py 60 --cut` |
| `batch_61.txt` | Батч 61: иконки: shield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b61_items.png` | `python tools/take_image.py 61 --cut` |
| `batch_62.txt` | Батч 62: иконки: shield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b62_items.png` | `python tools/take_image.py 62 --cut` |
| `batch_63.txt` | Батч 63: иконки: shield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b63_items.png` | `python tools/take_image.py 63 --cut` |
| `batch_64.txt` | Батч 64: иконки: shield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b64_items.png` | `python tools/take_image.py 64 --cut` |
| `batch_65.txt` | Батч 65: иконки: shield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b65_items.png` | `python tools/take_image.py 65 --cut` |
| `batch_66.txt` | Батч 66: иконки: shield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b66_items.png` | `python tools/take_image.py 66 --cut` |
| `batch_67.txt` | Батч 67: иконки: large tower greatshield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b67_items.png` | `python tools/take_image.py 67 --cut` |
| `batch_68.txt` | Батч 68: иконки: large tower greatshield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b68_items.png` | `python tools/take_image.py 68 --cut` |
| `batch_69.txt` | Батч 69: иконки: large tower greatshield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b69_items.png` | `python tools/take_image.py 69 --cut` |
| `batch_70.txt` | Батч 70: иконки: large tower greatshield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b70_items.png` | `python tools/take_image.py 70 --cut` |
| `batch_71.txt` | Батч 71: иконки: large tower greatshield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b71_items.png` | `python tools/take_image.py 71 --cut` |
| `batch_72.txt` | Батч 72: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b72_items.png` | `python tools/take_image.py 72 --cut` |
| `batch_73.txt` | Батч 73: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b73_items.png` | `python tools/take_image.py 73 --cut` |
| `batch_74.txt` | Батч 74: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b74_items.png` | `python tools/take_image.py 74 --cut` |
| `batch_75.txt` | Батч 75: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b75_items.png` | `python tools/take_image.py 75 --cut` |
| `batch_76.txt` | Батч 76: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b76_items.png` | `python tools/take_image.py 76 --cut` |
| `batch_77.txt` | Батч 77: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b77_items.png` | `python tools/take_image.py 77 --cut` |
| `batch_78.txt` | Батч 78: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b78_items.png` | `python tools/take_image.py 78 --cut` |
| `batch_79.txt` | Батч 79: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b79_items.png` | `python tools/take_image.py 79 --cut` |
| `batch_80.txt` | Батч 80: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b80_items.png` | `python tools/take_image.py 80 --cut` |
| `batch_81.txt` | Батч 81: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b81_items.png` | `python tools/take_image.py 81 --cut` |
| `batch_82.txt` | Батч 82: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b82_items.png` | `python tools/take_image.py 82 --cut` |
| `batch_83.txt` | Батч 83: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b83_items.png` | `python tools/take_image.py 83 --cut` |
| `batch_84.txt` | Батч 84: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b84_items.png` | `python tools/take_image.py 84 --cut` |
| `batch_85.txt` | Батч 85: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b85_items.png` | `python tools/take_image.py 85 --cut` |
| `batch_86.txt` | Батч 86: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b86_items.png` | `python tools/take_image.py 86 --cut` |
| `batch_87.txt` | Батч 87: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b87_items.png` | `python tools/take_image.py 87 --cut` |
| `batch_88.txt` | Батч 88: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b88_items.png` | `python tools/take_image.py 88 --cut` |
