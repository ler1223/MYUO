# Готовые запросы для генерации картинок

Собрано `python tools/build_requests.py` из `docs/uo_art_prompts.md`, `docs/ui_prompts.md` и `docs/art_prompts.md` — перегенерируйте после их изменения. Файл — полный текст одного запроса: откройте, скопируйте целиком в ChatGPT, приложите образец, сохраните картинку (PNG с прозрачным фоном, 1536x1024) по пути из таблицы и нарежьте командой.

Всего запросов: 93. Начать лучше с `batch_11.txt` (экран бойца) и первых линеек.

| Файл | Что | Приложить | Сохранить как | Нарезать |
| --- | --- | --- | --- | --- |
| `lineup_01.txt` | Спрайты классов, лист 1 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_01.png` | `python tools/cut_lineup.py assets/sprites_src/lineup/uo_01.png _ref arbalist berserker bishop breaker --reference _ref` |
| `lineup_02.txt` | Спрайты классов, лист 2 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_02.png` | `python tools/cut_lineup.py assets/sprites_src/lineup/uo_02.png _ref cleric crusader dark_knight doom_knight --reference _ref` |
| `lineup_03.txt` | Спрайты классов, лист 3 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_03.png` | `python tools/cut_lineup.py assets/sprites_src/lineup/uo_03.png _ref dreadnought druid elven_archer elven_augur --reference _ref` |
| `lineup_04.txt` | Спрайты классов, лист 4 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_04.png` | `python tools/cut_lineup.py assets/sprites_src/lineup/uo_04.png _ref elven_fencer elven_sibyl feathersword fighter --reference _ref` |
| `lineup_05.txt` | Спрайты классов, лист 5 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_05.png` | `python tools/cut_lineup.py assets/sprites_src/lineup/uo_05.png _ref gladiator great_knight gryphon_knight gryphon_master --reference _ref` |
| `lineup_06.txt` | Спрайты классов, лист 6 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_06.png` | `python tools/cut_lineup.py assets/sprites_src/lineup/uo_06.png _ref high_lord high_priestess hoplite housecarl --reference _ref` |
| `lineup_07.txt` | Спрайты классов, лист 7 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_07.png` | `python tools/cut_lineup.py assets/sprites_src/lineup/uo_07.png _ref hunter knight landsknecht legionnaire --reference _ref` |
| `lineup_08.txt` | Спрайты классов, лист 8 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_08.png` | `python tools/cut_lineup.py assets/sprites_src/lineup/uo_08.png _ref lord paladin priestess prince --reference _ref` |
| `lineup_09.txt` | Спрайты классов, лист 9 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_09.png` | `python tools/cut_lineup.py assets/sprites_src/lineup/uo_09.png _ref radiant_knight rogue sainted_knight sellsword --reference _ref` |
| `lineup_10.txt` | Спрайты классов, лист 10 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_10.png` | `python tools/cut_lineup.py assets/sprites_src/lineup/uo_10.png _ref sergeant shaman shieldshooter sniper --reference _ref` |
| `lineup_11.txt` | Спрайты классов, лист 11 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_11.png` | `python tools/cut_lineup.py assets/sprites_src/lineup/uo_11.png _ref snow_ranger soldier sorceress sword_master --reference _ref` |
| `lineup_12.txt` | Спрайты классов, лист 12 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_12.png` | `python tools/cut_lineup.py assets/sprites_src/lineup/uo_12.png _ref swordfighter thief valkyria vanguard --reference _ref` |
| `lineup_13.txt` | Спрайты классов, лист 13 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_13.png` | `python tools/cut_lineup.py assets/sprites_src/lineup/uo_13.png _ref viking warlock warrior werebear --reference _ref` |
| `lineup_14.txt` | Спрайты классов, лист 14 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_14.png` | `python tools/cut_lineup.py assets/sprites_src/lineup/uo_14.png _ref werefox werelion wereowl werewolf --reference _ref` |
| `lineup_15.txt` | Спрайты классов, лист 15 | старая линейка с паладином (assets/sprites_src/lineup/lineup_a.png) — образец масштаба | `assets/sprites_src/lineup/uo_15.png` | `python tools/cut_lineup.py assets/sprites_src/lineup/uo_15.png _ref witch wizard wyvern_knight wyvern_master --reference _ref` |
| `batch_11.txt` | Батч 11: экран бойца и тактика | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b11_unit.png` | `python tools/cut_ui_sheet.py 11` |
| `batch_12.txt` | Батч 12: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b12_skills.png` | `python tools/cut_ui_sheet.py 12` |
| `batch_13.txt` | Батч 13: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b13_skills.png` | `python tools/cut_ui_sheet.py 13` |
| `batch_14.txt` | Батч 14: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b14_skills.png` | `python tools/cut_ui_sheet.py 14` |
| `batch_15.txt` | Батч 15: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b15_skills.png` | `python tools/cut_ui_sheet.py 15` |
| `batch_16.txt` | Батч 16: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b16_skills.png` | `python tools/cut_ui_sheet.py 16` |
| `batch_17.txt` | Батч 17: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b17_skills.png` | `python tools/cut_ui_sheet.py 17` |
| `batch_18.txt` | Батч 18: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b18_skills.png` | `python tools/cut_ui_sheet.py 18` |
| `batch_19.txt` | Батч 19: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b19_skills.png` | `python tools/cut_ui_sheet.py 19` |
| `batch_20.txt` | Батч 20: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b20_skills.png` | `python tools/cut_ui_sheet.py 20` |
| `batch_21.txt` | Батч 21: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b21_skills.png` | `python tools/cut_ui_sheet.py 21` |
| `batch_22.txt` | Батч 22: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b22_skills.png` | `python tools/cut_ui_sheet.py 22` |
| `batch_23.txt` | Батч 23: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b23_skills.png` | `python tools/cut_ui_sheet.py 23` |
| `batch_24.txt` | Батч 24: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b24_skills.png` | `python tools/cut_ui_sheet.py 24` |
| `batch_25.txt` | Батч 25: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b25_skills.png` | `python tools/cut_ui_sheet.py 25` |
| `batch_26.txt` | Батч 26: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b26_skills.png` | `python tools/cut_ui_sheet.py 26` |
| `batch_27.txt` | Батч 27: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b27_skills.png` | `python tools/cut_ui_sheet.py 27` |
| `batch_28.txt` | Батч 28: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b28_skills.png` | `python tools/cut_ui_sheet.py 28` |
| `batch_29.txt` | Батч 29: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b29_skills.png` | `python tools/cut_ui_sheet.py 29` |
| `batch_30.txt` | Батч 30: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b30_skills.png` | `python tools/cut_ui_sheet.py 30` |
| `batch_31.txt` | Батч 31: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b31_skills.png` | `python tools/cut_ui_sheet.py 31` |
| `batch_32.txt` | Батч 32: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b32_skills.png` | `python tools/cut_ui_sheet.py 32` |
| `batch_33.txt` | Батч 33: значки навыков | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b33_skills.png` | `python tools/cut_ui_sheet.py 33` |
| `batch_34.txt` | Батч 34: иконки: sword | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b34_items.png` | `python tools/cut_ui_sheet.py 34` |
| `batch_35.txt` | Батч 35: иконки: sword | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b35_items.png` | `python tools/cut_ui_sheet.py 35` |
| `batch_36.txt` | Батч 36: иконки: sword | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b36_items.png` | `python tools/cut_ui_sheet.py 36` |
| `batch_37.txt` | Батч 37: иконки: sword | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b37_items.png` | `python tools/cut_ui_sheet.py 37` |
| `batch_38.txt` | Батч 38: иконки: sword | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b38_items.png` | `python tools/cut_ui_sheet.py 38` |
| `batch_39.txt` | Батч 39: иконки: axe or hammer | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b39_items.png` | `python tools/cut_ui_sheet.py 39` |
| `batch_40.txt` | Батч 40: иконки: axe or hammer | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b40_items.png` | `python tools/cut_ui_sheet.py 40` |
| `batch_41.txt` | Батч 41: иконки: axe or hammer | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b41_items.png` | `python tools/cut_ui_sheet.py 41` |
| `batch_42.txt` | Батч 42: иконки: axe or hammer | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b42_items.png` | `python tools/cut_ui_sheet.py 42` |
| `batch_43.txt` | Батч 43: иконки: axe or hammer | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b43_items.png` | `python tools/cut_ui_sheet.py 43` |
| `batch_44.txt` | Батч 44: иконки: spear | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b44_items.png` | `python tools/cut_ui_sheet.py 44` |
| `batch_45.txt` | Батч 45: иконки: spear | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b45_items.png` | `python tools/cut_ui_sheet.py 45` |
| `batch_46.txt` | Батч 46: иконки: spear | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b46_items.png` | `python tools/cut_ui_sheet.py 46` |
| `batch_47.txt` | Батч 47: иконки: spear | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b47_items.png` | `python tools/cut_ui_sheet.py 47` |
| `batch_48.txt` | Батч 48: иконки: spear | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b48_items.png` | `python tools/cut_ui_sheet.py 48` |
| `batch_49.txt` | Батч 49: иконки: bow | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b49_items.png` | `python tools/cut_ui_sheet.py 49` |
| `batch_50.txt` | Батч 50: иконки: bow | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b50_items.png` | `python tools/cut_ui_sheet.py 50` |
| `batch_51.txt` | Батч 51: иконки: bow | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b51_items.png` | `python tools/cut_ui_sheet.py 51` |
| `batch_52.txt` | Батч 52: иконки: bow | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b52_items.png` | `python tools/cut_ui_sheet.py 52` |
| `batch_53.txt` | Батч 53: иконки: bow | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b53_items.png` | `python tools/cut_ui_sheet.py 53` |
| `batch_54.txt` | Батч 54: иконки: bow | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b54_items.png` | `python tools/cut_ui_sheet.py 54` |
| `batch_55.txt` | Батч 55: иконки: mage staff | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b55_items.png` | `python tools/cut_ui_sheet.py 55` |
| `batch_56.txt` | Батч 56: иконки: mage staff | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b56_items.png` | `python tools/cut_ui_sheet.py 56` |
| `batch_57.txt` | Батч 57: иконки: mage staff | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b57_items.png` | `python tools/cut_ui_sheet.py 57` |
| `batch_58.txt` | Батч 58: иконки: mage staff | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b58_items.png` | `python tools/cut_ui_sheet.py 58` |
| `batch_59.txt` | Батч 59: иконки: mage staff | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b59_items.png` | `python tools/cut_ui_sheet.py 59` |
| `batch_60.txt` | Батч 60: иконки: mage staff | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b60_items.png` | `python tools/cut_ui_sheet.py 60` |
| `batch_61.txt` | Батч 61: иконки: shield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b61_items.png` | `python tools/cut_ui_sheet.py 61` |
| `batch_62.txt` | Батч 62: иконки: shield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b62_items.png` | `python tools/cut_ui_sheet.py 62` |
| `batch_63.txt` | Батч 63: иконки: shield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b63_items.png` | `python tools/cut_ui_sheet.py 63` |
| `batch_64.txt` | Батч 64: иконки: shield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b64_items.png` | `python tools/cut_ui_sheet.py 64` |
| `batch_65.txt` | Батч 65: иконки: shield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b65_items.png` | `python tools/cut_ui_sheet.py 65` |
| `batch_66.txt` | Батч 66: иконки: shield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b66_items.png` | `python tools/cut_ui_sheet.py 66` |
| `batch_67.txt` | Батч 67: иконки: large tower greatshield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b67_items.png` | `python tools/cut_ui_sheet.py 67` |
| `batch_68.txt` | Батч 68: иконки: large tower greatshield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b68_items.png` | `python tools/cut_ui_sheet.py 68` |
| `batch_69.txt` | Батч 69: иконки: large tower greatshield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b69_items.png` | `python tools/cut_ui_sheet.py 69` |
| `batch_70.txt` | Батч 70: иконки: large tower greatshield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b70_items.png` | `python tools/cut_ui_sheet.py 70` |
| `batch_71.txt` | Батч 71: иконки: large tower greatshield | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b71_items.png` | `python tools/cut_ui_sheet.py 71` |
| `batch_72.txt` | Батч 72: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b72_items.png` | `python tools/cut_ui_sheet.py 72` |
| `batch_73.txt` | Батч 73: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b73_items.png` | `python tools/cut_ui_sheet.py 73` |
| `batch_74.txt` | Батч 74: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b74_items.png` | `python tools/cut_ui_sheet.py 74` |
| `batch_75.txt` | Батч 75: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b75_items.png` | `python tools/cut_ui_sheet.py 75` |
| `batch_76.txt` | Батч 76: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b76_items.png` | `python tools/cut_ui_sheet.py 76` |
| `batch_77.txt` | Батч 77: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b77_items.png` | `python tools/cut_ui_sheet.py 77` |
| `batch_78.txt` | Батч 78: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b78_items.png` | `python tools/cut_ui_sheet.py 78` |
| `batch_79.txt` | Батч 79: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b79_items.png` | `python tools/cut_ui_sheet.py 79` |
| `batch_80.txt` | Батч 80: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b80_items.png` | `python tools/cut_ui_sheet.py 80` |
| `batch_81.txt` | Батч 81: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b81_items.png` | `python tools/cut_ui_sheet.py 81` |
| `batch_82.txt` | Батч 82: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b82_items.png` | `python tools/cut_ui_sheet.py 82` |
| `batch_83.txt` | Батч 83: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b83_items.png` | `python tools/cut_ui_sheet.py 83` |
| `batch_84.txt` | Батч 84: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b84_items.png` | `python tools/cut_ui_sheet.py 84` |
| `batch_85.txt` | Батч 85: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b85_items.png` | `python tools/cut_ui_sheet.py 85` |
| `batch_86.txt` | Батч 86: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b86_items.png` | `python tools/cut_ui_sheet.py 86` |
| `batch_87.txt` | Батч 87: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b87_items.png` | `python tools/cut_ui_sheet.py 87` |
| `batch_88.txt` | Батч 88: иконки: accessory | 1-2 скриншота меню UO из assets/ref/ | `assets/ui/sheets/b88_items.png` | `python tools/cut_ui_sheet.py 88` |
