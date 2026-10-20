# Таблица навыков и анимаций UO

Собрано `tools/uo_battle/table.py`. Источник: слот UO — анимации `S##_<навык>` файла класса; общая — `ATTACK_*` / `MAGIC_*`, подобранная по виду навыка (в данных игры связи «навык -> слот» нет); ручная — правка из `skill_editor.py`. События: удар / движ. / получ. / стоп, в мс от начала части.

## arbalist — Ranger_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| power_bolt | общая | ATTACK_1 | 600 | — |
|  |  | ATTACK_2 | 2000 | — |
|  |  | ATTACK_END | 983 | удар 0 |
| toxic_bolt | общая | ATTACK_B1 | 600 | — |
|  |  | ATTACK_B2 | 2000 | — |
|  |  | ATTACK_B3 | 933 | удар 0 |

## berserker — Gladiator_HG_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| wide_smash | общая | ATTACK_A1 | 567 | движ. 233 |
|  |  | ATTACK_A2 | 733 | удар 0 |
|  |  | ATTACK_A3 | 367 | движ. 50 |
|  |  | ATTACK_A4 | 117 | — |
| mounting_charge | общая | ATTACK_B1 | 500 | — |
|  |  | ATTACK_B2 | 367 | движ. 33 |
|  |  | ATTACK_B3 | 733 | удар 0 |
|  |  | ATTACK_B4 | 367 | движ. 50 |
|  |  | ATTACK_B5 | 117 | — |
| grand_smash | общая | ATTACK_C1 | 567 | движ. 100 |
|  |  | ATTACK_C2 | 1733 | движ. 983, удар 1067 |
|  |  | ATTACK_C3 | 483 | движ. 167 |
|  |  | ATTACK_C4 | 117 | — |

## bishop — Cleric_HG_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| heal | слот UO | S02_BT_HEAL_A1 | 1300 | — |
|  |  | S02_BT_HEAL_A2 | 900 | — |
|  |  | S02_BT_HEAL_A3 | 1100 | — |
|  |  | S02_BT_HEAL_A4 | 600 | удар 0 |
|  |  | S02_BT_HEAL_A5 | 183 | — |
|  |  | S19_QUICK_HEAL_1 | 3283 | удар 717 |
|  |  | S19_QUICK_HEAL_2 | 6800 | — |
|  |  | S19_QUICK_HEAL_3 | 217 | — |
| sacred_heal | общая | MAGIC_A | 1300 | — |
|  |  | MAGIC_A_IDLE | 900 | — |
|  |  | MAGIC_A_2 | 1100 | — |
|  |  | MAGIC_A_IDLE2 | 600 | удар 0 |
|  |  | MAGIC_A_END | 183 | — |

## breaker — Warrior_HG_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| heavy_smash | общая | ATTACK_1 | 1217 | движ. 817 |
|  |  | ATTACK_2 | 1017 | удар 67 |
|  |  | ATTACK_3 | 950 | движ. 117 |
|  |  | ATTACK_4 | 700 | — |
| assaulting_blow | общая | ATTACK_B1 | 950 | движ. 50 |
|  |  | ATTACK_B2 | 2417 | удар 1383 |
|  |  | ATTACK_B3 | 1017 | движ. 100 |
|  |  | ATTACK_B4 | 700 | — |
| row_smash | общая | ATTACK_C | 1833 | удар 883 |

## cleric — Cleric_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| heal | слот UO | S02_BT_HEAL_A1 | 1300 | — |
|  |  | S02_BT_HEAL_A2 | 900 | — |
|  |  | S02_BT_HEAL_A3 | 1100 | — |
|  |  | S02_BT_HEAL_A4 | 600 | удар 0 |
|  |  | S02_BT_HEAL_A5 | 183 | — |
|  |  | S19_QUICK_HEAL_1 | 3283 | удар 717 |
|  |  | S19_QUICK_HEAL_2 | 6800 | — |
|  |  | S19_QUICK_HEAL_3 | 217 | — |

## dark_knight — BlackKnight_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| vengeful_axe | общая | ATTACK_A1 | 583 | движ. 50 |
|  |  | ATTACK_A2 | 2117 | движ. 1233, удар 1467 |
|  |  | ATTACK_A3 | 783 | движ. 0 |
|  |  | ATTACK_A4 | 617 | — |
| venom_axe | общая | ATTACK_B1 | 633 | движ. 100 |
|  |  | ATTACK_B2 | 2383 | удар 667, движ. 1183 |
|  |  | ATTACK_B3 | 600 | движ. 0 |
|  |  | ATTACK_B4 | 617 | — |

## doom_knight — BlackKnight_HG_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| vengeful_axe | общая | ATTACK_A1 | 983 | движ. 333 |
|  |  | ATTACK_A2 | 2350 | движ. 1233, удар 1450 |
|  |  | ATTACK_A3 | 817 | движ. 0 |
|  |  | ATTACK_A4 | 900 | — |
| venom_axe | общая | ATTACK_B1 | 983 | движ. 333 |
|  |  | ATTACK_B2 | 2383 | удар 667, движ. 1183 |
|  |  | ATTACK_B3 | 667 | движ. 0 |
|  |  | ATTACK_B4 | 900 | — |
| dark_flame | общая | ATTACK_A1 | 983 | движ. 333 |
|  |  | ATTACK_A2 | 2350 | движ. 1233, удар 1450 |
|  |  | ATTACK_A3 | 817 | движ. 0 |
|  |  | ATTACK_A4 | 900 | — |

## dreadnought — Armoria_HG_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| heavy_slash | слот UO | S03_MEGA_SLASH_1 | 600 | движ. 267 |
|  |  | S03_MEGA_SLASH_2 | 1000 | удар 67 |
| penetrate | слот UO | S01_PENETRATE_1 | 800 | движ. 150 |
|  |  | S01_PENETRATE_2 | 1167 | движ. 0, удар 183 |
| omega_shatter | общая | ATTACK_A1 | 800 | движ. 150 |
|  |  | ATTACK_A2 | 1167 | движ. 0, удар 183 |

## druid — Shaman_HG_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| passive_curse | слот UO | S04_PASSIVE_CURSE_1 | 1200 | — |
|  |  | S04_PASSIVE_CURSE_2 | 850 | — |
|  |  | S04_PASSIVE_CURSE_3 | 1300 | удар 200 |
|  |  | S04_PASSIVE_CURSE_4 | 1100 | удар 0 |
|  |  | S04_PASSIVE_CURSE_5 | 583 | — |
| offensive_curse | общая | ATTACK | 2450 | удар 950, движ. 1050 |
| defensive_curse | общая | ATTACK | 2450 | удар 950, движ. 1050 |
| compounding_curse | общая | ATTACK | 2450 | удар 950, движ. 1050 |

## elven_archer — ElfArcher_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| wind_arrow | общая | MAGIC_A | 733 | — |
|  |  | MAGIC_A_IDLE | 533 | — |
|  |  | MAGIC_A_2 | 7717 | удар 367 |
|  |  | MAGIC_A_IDLE2 | 7350 | удар 0 |
|  |  | MAGIC_A_END | 550 | — |
| icicle_arrow | общая | MAGIC_B | 2467 | — |
|  |  | MAGIC_B_IDLE | 2617 | — |
|  |  | MAGIC_B_2 | 1450 | удар 167 |
|  |  | MAGIC_B_IDLE2 | 2617 | удар 0 |
|  |  | MAGIC_B_END | 367 | — |

## elven_fencer — ElfFencer_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| lightning_blade | общая | ATTACK | 1333 | удар 467, движ. 483 |
| natures_wrath | общая | ATTACK_B | 2067 | движ. 1217 |
|  |  | ATTACK_B_END | 1117 | удар 0 |
| mirage_stab | общая | ATTACK | 1333 | удар 467, движ. 483 |

## feathersword — FeatherSword_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| spiral_sword | общая | ATTACK_A1 | 600 | движ. 67 |
|  |  | ATTACK_A2 | 1067 | удар 500 |
|  |  | ATTACK_A3 | 583 | движ. 0 |
|  |  | ATTACK_A4 | 1633 | — |
| shield_smite | общая | ATTACK_C1 | 600 | движ. 67 |
|  |  | ATTACK_C2 | 1033 | удар 567 |
|  |  | ATTACK_C3 | 667 | движ. 83 |
|  |  | ATTACK_C4 | 1633 | — |
| honed_slash | общая | ATTACK_E1 | 600 | движ. 67 |
|  |  | ATTACK_E2 | 1833 | удар 200, удар 433, удар 1300 |
|  |  | ATTACK_E3 | 667 | движ. 83 |
|  |  | ATTACK_E4 | 1633 | — |

## fighter — Fighter_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| warding_slash | общая | ATTACK_1 | 1267 | удар 500 |
| shield_bash | общая | ATTACK_B | 1367 | удар 383 |

## gladiator — Gladiator_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| wide_smash | общая | ATTACK_A1 | 567 | движ. 233 |
|  |  | ATTACK_A2 | 733 | удар 0 |
|  |  | ATTACK_A3 | 317 | движ. 0 |
|  |  | ATTACK_A4 | 117 | — |

## great_knight — Knight_HG_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| assaulting_lance | общая | ATTACK_1 | 633 | движ. 50 |
|  |  | ATTACK_2 | 2867 | движ. 1233, удар 1450 |
|  |  | ATTACK_3 | 783 | движ. 0 |
|  |  | ATTACK_4 | 867 | — |
| wild_rush | общая | ATTACK_B2_1 | 1983 | удар 1317 |
|  |  | ATTACK_B2_2 | 1900 | удар 1233 |
| pile_thrust | общая | ATTACK_C1 | 933 | движ. 750 |
|  |  | ATTACK_C2 | 533 | движ. 0 |

## gryphon_knight — GriffonKnight_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| high_swing | общая | ATTACK_A1 | 2333 | движ. 850 |
|  |  | ATTACK_A2 | 3217 | удар 783 |
|  |  | ATTACK_A3 | 1833 | движ. 167 |
|  |  | ATTACK_A4 | 2200 | — |

## gryphon_master — GriffonKnight_HG_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| high_swing | общая | ATTACK_A1 | 2333 | движ. 850 |
|  |  | ATTACK_A2 | 3217 | удар 783 |
|  |  | ATTACK_A3 | 1833 | движ. 167 |
|  |  | ATTACK_A4 | 2200 | — |
| fatal_dive | общая | ATTACK_B1 | 2983 | движ. 1500 |
|  |  | ATTACK_B2 | 2817 | удар 83 |
|  |  | ATTACK_B3 | 1817 | движ. 150 |
|  |  | ATTACK_B4 | 2200 | — |
| aerial_smite | общая | ATTACK_A1 | 2333 | движ. 850 |
|  |  | ATTACK_A2 | 3217 | удар 783 |
|  |  | ATTACK_A3 | 1833 | движ. 167 |
|  |  | ATTACK_A4 | 2200 | — |

## hoplite — Hoplite_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| sting | общая | ATTACK_A1 | 1150 | движ. 233 |
|  |  | ATTACK_A2_TO_IDLE | 1600 | движ. 483, удар 583 |

## housecarl — Huscarl_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| smash | общая | ATTACK_A | 1583 | удар 700, движ. 700 |
| rolling_axe | общая | ATTACK_B | 2250 | движ. 667, удар 717, удар 1050, удар 1283 |

## hunter — Hunter_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| single_shot | общая | ATTACK | 1267 | — |
|  |  | ATTACK_IDLE | 567 | — |
|  |  | ATTACK_END | 867 | удар 0 |
| dual_shot | общая | ATTACK_B | 733 | — |
|  |  | ATTACK_B_IDLE | 533 | движ. 0 |
|  |  | ATTACK_B_2 | 633 | — |
|  |  | ATTACK_B_IDLE2 | 233 | — |
|  |  | ATTACK_B_END2 | 217 | — |

## knight — Knight_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| assaulting_lance | общая | ATTACK_1 | 633 | движ. 100 |
|  |  | ATTACK_2 | 3417 | движ. 1233, удар 1467 |
|  |  | ATTACK_3 | 783 | движ. 0 |
|  |  | ATTACK_4 | 517 | — |
| wild_rush | общая | ATTACK_C1 | 900 | — |
|  |  | ATTACK_C2 | 533 | движ. 0 |

## landsknecht — Mercenary_HG_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| heavy_slash | слот UO | S04_MEGA_SLASH_1 | 1267 | движ. 200 |
|  |  | S04_MEGA_SLASH_2 | 817 | удар 67 |
| killing_chain | общая | ATTACK | 1283 | удар 433, движ. 433 |
| bastards_cross | общая | ATTACK_B1 | 1267 | движ. 200 |
|  |  | ATTACK_B2 | 817 | удар 67 |

## legionnaire — Hoplite_HG_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| sting | общая | ATTACK_A1 | 917 | движ. 150 |
|  |  | ATTACK_A2_TO_IDLE | 2583 | движ. 1483, удар 1683 |
| row_protection | общая | ATTACK_B1 | 917 | движ. 150 |
|  |  | ATTACK_B2_TO_IDLE | 2583 | движ. 1483, удар 1683 |
| greatshield | общая | ATTACK_C1 | 917 | движ. 150 |
|  |  | ATTACK_C2_TO_IDLE | 1733 | движ. 833, удар 983 |

## paladin — WhiteKnight_HG_M (модель временная: в игре её нет)

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| slice | общая | ATTACK_1 | 633 | движ. 100 |
|  |  | ATTACK_2 | 1433 | движ. 1050, удар 1083 |
|  |  | ATTACK_3 | 533 | удар 0 |
|  |  | ATTACK_4 | 583 | движ. 0 |
|  |  | ATTACK_5 | 1017 | — |
| heal | слот UO | S07_BT_HEAL_A1 | 717 | удар 400 |
|  |  | S07_BT_HEAL_A2 | 4050 | — |
|  |  | S07_BT_HEAL_A3 | 600 | — |
| divine_cross | общая | ATTACK_A1 | 633 | движ. 100 |
|  |  | ATTACK_A2 | 1700 | движ. 1050, удар 1083 |
|  |  | ATTACK_A3 | 583 | движ. 0 |
|  |  | ATTACK_A4 | 1017 | — |

## radiant_knight — WhiteKnight_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| hache | общая | ATTACK_1 | 633 | движ. 100 |
|  |  | ATTACK_2 | 2000 | движ. 1250, удар 1333 |
|  |  | ATTACK_3 | 583 | движ. 0 |
|  |  | ATTACK_4 | 933 | — |
| row_heal | общая | ATTACK_A1 | 633 | движ. 100 |
|  |  | ATTACK_A2 | 2000 | движ. 1250, удар 1333 |
|  |  | ATTACK_A3 | 583 | движ. 0 |
|  |  | ATTACK_A4 | 933 | — |

## rogue — Thief_HG_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| passive_steal | общая | ATTACK | 1200 | движ. 217, удар 233, движ. 567, удар 583 |
| toxic_throw | общая | ATTACK_B1 | 817 | движ. 283 |
|  |  | ATTACK_B2 | 1717 | удар 367, удар 633 |
|  |  | ATTACK_B3 | 567 | — |
| shadowbite | общая | ATTACK_C1 | 2183 | движ. 483, удар 550, удар 683, движ. 683, движ. 917, удар 950, удар 1417, движ. 1417 |
|  |  | ATTACK_C2 | 1200 | — |
|  |  | ATTACK_C3 | 483 | — |
| active_steal | общая | ATTACK_A | 883 | движ. 233, удар 267 |

## sainted_knight — WhiteKnight_HG_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| hache | общая | ATTACK_1 | 633 | движ. 100 |
|  |  | ATTACK_2 | 1433 | движ. 1050, удар 1083 |
|  |  | ATTACK_3 | 533 | удар 0 |
|  |  | ATTACK_4 | 583 | движ. 0 |
|  |  | ATTACK_5 | 1017 | — |
| row_heal | общая | ATTACK_A1 | 633 | движ. 100 |
|  |  | ATTACK_A2 | 1700 | движ. 1050, удар 1083 |
|  |  | ATTACK_A3 | 583 | движ. 0 |
|  |  | ATTACK_A4 | 1017 | — |
| saints_blade | общая | ATTACK_1 | 633 | движ. 100 |
|  |  | ATTACK_2 | 1433 | движ. 1050, удар 1083 |
|  |  | ATTACK_3 | 533 | удар 0 |
|  |  | ATTACK_4 | 583 | движ. 0 |
|  |  | ATTACK_5 | 1017 | — |

## sellsword — Mercenary_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| heavy_slash | слот UO | S04_MEGA_SLASH_1 | 1267 | движ. 200 |
|  |  | S04_MEGA_SLASH_2 | 817 | удар 67 |
| killing_chain | общая | ATTACK | 1283 | удар 433, движ. 433 |

## sergeant — Soldier_HG_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| long_thrust | общая | ATTACK_1 | 1033 | удар 200 |
| javelin | общая | ATTACK_A1 | 933 | движ. 133 |
|  |  | ATTACK_A2 | 1100 | удар 400 |
|  |  | ATTACK_A3 | 983 | движ. 183 |
|  |  | ATTACK_A4 | 883 | — |
| honed_spear | общая | ATTACK_B_TO_IDLE | 2017 | удар 450 |

## shaman — Shaman_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| passive_curse | слот UO | S04_PASSIVE_CURSE_1 | 1167 | — |
|  |  | S04_PASSIVE_CURSE_2 | 850 | — |
|  |  | S04_PASSIVE_CURSE_3 | 1300 | удар 200 |
|  |  | S04_PASSIVE_CURSE_4 | 1100 | удар 0 |
|  |  | S04_PASSIVE_CURSE_5 | 517 | — |
| offensive_curse | общая | ATTACK | 2350 | удар 950, движ. 1050 |

## shieldshooter — Ranger_HG_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| power_bolt | общая | ATTACK_1 | 417 | — |
|  |  | ATTACK_2 | 2000 | — |
|  |  | ATTACK_END | 1000 | удар 0 |
| toxic_bolt | общая | ATTACK_B1 | 383 | — |
|  |  | ATTACK_B2 | 2000 | — |
|  |  | ATTACK_B3 | 933 | удар 0 |
| heavy_bolt | общая | ATTACK_1 | 417 | — |
|  |  | ATTACK_2 | 2000 | — |
|  |  | ATTACK_END | 1000 | удар 0 |

## sniper — Hunter_HG_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| single_shot | общая | ATTACK | 1367 | — |
|  |  | ATTACK_IDLE | 567 | — |
|  |  | ATTACK_END | 883 | удар 0 |
| dual_shot | общая | ATTACK_B | 833 | — |
|  |  | ATTACK_B_IDLE | 633 | движ. 0 |
|  |  | ATTACK_B_2 | 900 | — |
|  |  | ATTACK_B_IDLE2 | 500 | — |
|  |  | ATTACK_B_END2 | 250 | — |
| row_shot | общая | ATTACK_C | 1000 | — |
|  |  | ATTACK_C_IDLE | 350 | — |
|  |  | ATTACK_C_END | 717 | удар 0 |

## soldier — Soldier_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| long_thrust | общая | ATTACK_1 | 900 | удар 200 |
| javelin | общая | ATTACK_A1 | 867 | движ. 67 |
|  |  | ATTACK_A2 | 1100 | удар 400 |
|  |  | ATTACK_A3 | 983 | движ. 183 |
|  |  | ATTACK_A4 | 983 | — |

## sorceress — Witch_HG_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| icebolt | общая | MAGIC_A_1 | 1383 | — |
|  |  | MAGIC_A_2 | 1750 | — |
|  |  | MAGIC_A_END | 1333 | удар 150 |
| magick_missile | общая | MAGIC_B_1 | 2283 | — |
|  |  | MAGIC_B_2 | 1750 | — |
|  |  | MAGIC_B_3 | 700 | удар 167 |
|  |  | MAGIC_B_4 | 2567 | — |
|  |  | MAGIC_B_END | 3100 | — |
| ice_coffin | общая | MAGIC_A_1 | 1383 | — |
|  |  | MAGIC_A_2 | 1750 | — |
|  |  | MAGIC_A_END | 1333 | удар 150 |

## sword_master — Swordsman_HG_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| keen_edge | общая | ATTACK | 850 | удар 233 |
| impale | общая | ATTACK_B | 1133 | удар 183 |
| meteor_slash | общая | ATTACK_C | 3167 | удар 183, удар 383, удар 550, удар 783, удар 850, удар 933, удар 1017, движ. 1333, удар 1367, удар 1383 |

## swordfighter — Swordsman_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| keen_edge | общая | ATTACK | 983 | удар 433 |
| impale | общая | ATTACK_B | 1167 | удар 183 |

## thief — Thief_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| passive_steal | общая | ATTACK | 1167 | движ. 217, удар 233, движ. 567, удар 583 |
| toxic_throw | общая | ATTACK_B1 | 817 | движ. 283 |
|  |  | ATTACK_B2 | 1717 | удар 367, удар 633 |
|  |  | ATTACK_B3 | 467 | — |

## vanguard — Fighter_HG_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| warding_slash | общая | ATTACK_1 | 1200 | удар 317 |
| shield_bash | общая | ATTACK_A1 | 917 | движ. 133 |
|  |  | ATTACK_A2_TO_IDLE | 1067 | удар 633 |
| defender | общая | ATTACK_B | 1283 | удар 317 |

## viking — Huscarl_HG_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| smash | общая | ATTACK_A | 1733 | удар 700, движ. 700 |
| rolling_axe | общая | ATTACK_B | 2317 | движ. 633, удар 683, удар 1017, удар 1250 |
| wide_breaker | общая | ATTACK_C | 1667 | удар 633 |

## warlock — Wizard_HG_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| fireball | общая | MAGIC_A | 1200 | — |
|  |  | MAGIC_A_IDLE | 1067 | — |
|  |  | MAGIC_A_2 | 1400 | — |
|  |  | MAGIC_A_2_IDLE | 633 | удар 0 |
|  |  | MAGIC_A_END | 217 | — |
| thunderous_strike | общая | MAGIC_B | 1400 | — |
|  |  | MAGIC_B_IDLE | 667 | — |
|  |  | MAGIC_B_2 | 1267 | — |
|  |  | MAGIC_B_2_IDLE | 667 | удар 0 |
|  |  | MAGIC_B_END | 250 | — |
| volcano | общая | MAGIC_C | 1567 | — |
|  |  | MAGIC_C_IDLE | 833 | — |
|  |  | MAGIC_C_2 | 1167 | — |
|  |  | MAGIC_C_2_IDLE | 500 | удар 0 |
|  |  | MAGIC_C_END | 250 | — |

## warrior — Warrior_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| heavy_smash | общая | ATTACK_1 | 967 | движ. 83 |
|  |  | ATTACK_2 | 1717 | удар 1067 |
|  |  | ATTACK_3 | 1200 | движ. 400 |
|  |  | ATTACK_4 | 783 | — |
| assaulting_blow | общая | ATTACK_C | 1600 | удар 650 |

## werebear — WereBear_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| bear_crush | общая | ATTACK | 3667 | движ. 617, удар 2383 |
| round_swing | общая | ATTACK_B | 1283 | — |
|  |  | ATTACK_B_IDLE | 1117 | удар 267, удар 400, удар 550, удар 650, удар 750, удар 883 |
|  |  | ATTACK_B_END | 1217 | удар 267 |
| earthshaker | общая | ATTACK_C1 | 950 | движ. 217 |
|  |  | ATTACK_C2 | 1100 | удар 433 |
|  |  | ATTACK_C3 | 1317 | движ. 183 |
|  |  | ATTACK_C4 | 967 | — |

## werefox — WereFox_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| piercing_lance | общая | ATTACK | 1100 | удар 100 |
| passive_hold | общая | ATTACK_B1 | 617 | движ. 217 |
|  |  | ATTACK_B2 | 883 | удар 83 |
|  |  | ATTACK_B3 | 467 | движ. 267 |
|  |  | ATTACK_B4 | 717 | — |
| venom_thrust | общая | ATTACK_C1 | 3400 | — |
|  |  | ATTACK_C2 | 450 | движ. 50 |
|  |  | ATTACK_C3 | 533 | удар 150 |
|  |  | ATTACK_C4 | 500 | движ. 300 |
|  |  | ATTACK_C5 | 717 | — |

## werelion — WereWolf_M (модель временная: в игре её нет)

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| wide_smash | общая | ATTACK | 1017 | удар 333 |
| mounting_charge | общая | ATTACK_B | 683 | — |
|  |  | ATTACK_B_IDLE | 517 | — |
|  |  | ATTACK_B_2 | 400 | движ. 33 |
|  |  | ATTACK_B_IDLE2 | 567 | удар 33 |
|  |  | ATTACK_B_END | 217 | — |
| grand_smash | общая | ATTACK_C1 | 683 | удар 67 |
|  |  | ATTACK_C2 | 567 | движ. 0 |
|  |  | ATTACK_C3 | 517 | — |
|  |  | ATTACK_C4 | 433 | движ. 67 |
|  |  | ATTACK_C5 | 650 | — |

## wereowl — WereOwl_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| aurora_veil | общая | MAGIC_A_1 | 450 | — |
|  |  | MAGIC_A_2 | 2667 | — |
|  |  | MAGIC_A_END | 1300 | удар 200 |
| night_vision | общая | MAGIC_B_1 | 500 | — |
|  |  | MAGIC_B_2 | 2000 | — |
|  |  | MAGIC_B_3 | 2133 | удар 150 |
|  |  | MAGIC_B_4 | 1750 | — |
|  |  | MAGIC_B_END | 383 | — |
| extra_heal | общая | MAGIC_A_1 | 450 | — |
|  |  | MAGIC_A_2 | 2667 | — |
|  |  | MAGIC_A_END | 1300 | удар 200 |

## werewolf — WereWolf_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| finishing_stab | общая | ATTACK | 1017 | удар 333 |
| decimate | общая | ATTACK_B | 683 | — |
|  |  | ATTACK_B_IDLE | 517 | — |
|  |  | ATTACK_B_2 | 400 | движ. 33 |
|  |  | ATTACK_B_IDLE2 | 567 | удар 33 |
|  |  | ATTACK_B_END | 217 | — |
| wild_fang | общая | ATTACK_C1 | 683 | удар 67 |
|  |  | ATTACK_C2 | 567 | движ. 0 |
|  |  | ATTACK_C3 | 517 | — |
|  |  | ATTACK_C4 | 433 | движ. 67 |
|  |  | ATTACK_C5 | 650 | — |

## witch — Witch_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| icebolt | общая | MAGIC_A_1 | 917 | — |
|  |  | MAGIC_A_2 | 2800 | — |
|  |  | MAGIC_A_END | 1517 | удар 383 |
| magick_missile | общая | MAGIC_B_1 | 967 | — |
|  |  | MAGIC_B_2 | 967 | — |
|  |  | MAGIC_B_3 | 867 | удар 333 |
|  |  | MAGIC_B_4 | 2450 | — |
|  |  | MAGIC_B_END | 367 | — |

## wizard — Wizard_M

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| fireball | общая | MAGIC_A | 1183 | — |
|  |  | MAGIC_A_IDLE | 1067 | — |
|  |  | MAGIC_A_2 | 1400 | — |
|  |  | MAGIC_A_2_IDLE | 633 | удар 0 |
|  |  | MAGIC_A_END | 217 | — |

## wyvern_knight — WyvernKnight_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| diving_thrust | общая | ATTACK_A1 | 3983 | движ. 983 |
|  |  | ATTACK_A2 | 983 | удар 533 |
|  |  | ATTACK_A3 | 4167 | движ. 600 |
|  |  | ATTACK_A4 | 2150 | — |

## wyvern_master — WyvernKnight_HG_F

| Навык | Источник | Часть | мс | События |
|---|---|---|---|---|
| diving_thrust | общая | ATTACK_A1 | 3983 | движ. 983 |
|  |  | ATTACK_A2 | 983 | удар 533 |
|  |  | ATTACK_A3 | 4167 | движ. 600 |
|  |  | ATTACK_A4 | 2517 | — |
| fire_breath | общая | ATTACK_B1 | 3650 | движ. 650 |
|  |  | ATTACK_B2 | 1050 | удар 583 |
|  |  | ATTACK_B3 | 4483 | движ. 833 |
|  |  | ATTACK_B4 | 2517 | — |
| tempest_drive | общая | ATTACK_A1 | 3983 | движ. 983 |
|  |  | ATTACK_A2 | 983 | удар 533 |
|  |  | ATTACK_A3 | 4167 | движ. 600 |
|  |  | ATTACK_A4 | 2517 | — |
