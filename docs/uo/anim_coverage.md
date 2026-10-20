# Покрытие анимаций навыков

Собрано `python tools/uo_battle/fill_skill_animations.py --write`. Подробности — в докстринге скрипта.

Пар «класс — навык»: привязка 104, цепочка класса 65, общая атака или каст 1454.

## Навыки, у которых хоть у одного класса анимация общая

Навыки-ответы пассивок сюда не входят: удар класса для них — задумка.

| Навык | Вид | Область | Классов | Примеры |
|---|---|---|---|---|
| active_shatter | melee | single | 20 | crusader, dreadnought, elven_fencer, feather_shield |
| armor_shatter | melee | single | 7 | arbalist, elven_archer, feather_bow, hunter |
| armor_shatter_ii | melee | single | 7 | arbalist, elven_archer, feather_bow, hunter |
| assassins_nail | melee | single | 20 | crusader, dreadnought, elven_fencer, feather_shield |
| astral_blade | melee | single | 63 | arbalist, berserker, bishop, breaker |
| banishing_smite | melee | row | 12 | berserker, breaker, dark_knight, doom_knight |
| beastslayer | melee | row | 19 | arbalist, berserker, breaker, dark_knight |
| blizzard | magic | all | 12 | bishop, cleric, druid, high_priestess |
| bulwark | support | row | 5 | dreadnought, hoplite, legionnaire, shieldshooter |
| checkmate | ranged | single | 7 | arbalist, elven_archer, feather_bow, hunter |
| crush | melee | single | 12 | berserker, breaker, dark_knight, doom_knight |
| demolition | melee | single | 12 | berserker, breaker, dark_knight, doom_knight |
| desperation | melee | single | 12 | berserker, breaker, dark_knight, doom_knight |
| dispel_all | ranged | all | 12 | bishop, cleric, druid, high_priestess |
| double_blast | melee | single | 20 | crusader, dreadnought, elven_fencer, feather_shield |
| dragoon_dive | ranged | all | 12 | elven_augur, elven_sibyl, great_knight, hoplite |
| earthquake | magic | all | 12 | bishop, cleric, druid, high_priestess |
| elfslayer | melee | column | 12 | elven_augur, elven_sibyl, great_knight, hoplite |
| execution | melee | single | 12 | berserker, breaker, dark_knight, doom_knight |
| fire_slash | melee | single | 20 | crusader, dreadnought, elven_fencer, feather_shield |
| firestorm | melee | single | 20 | crusader, dreadnought, elven_fencer, feather_shield |
| flame_arrow | ranged | single | 7 | arbalist, elven_archer, feather_bow, hunter |
| flame_javelin | ranged | single | 12 | elven_augur, elven_sibyl, great_knight, hoplite |
| freezing_thrust | magic | single | 10 | great_knight, hoplite, knight, legionnaire |
| glowing_light | support | all | 63 | arbalist, berserker, bishop, breaker |
| gravity | ranged | all | 12 | bishop, cleric, druid, high_priestess |
| grisly_fire | melee | single | 20 | crusader, dreadnought, elven_fencer, feather_shield |
| grisly_poison | melee | single | 20 | crusader, dreadnought, elven_fencer, feather_shield |
| harpoon_bolt | ranged | column | 7 | arbalist, elven_archer, feather_bow, hunter |
| healing_wind | heal | row | 63 | arbalist, berserker, bishop, breaker |
| heavy_smash | melee | single | 10 | berserker, dark_knight, doom_knight, gladiator |
| holy_cradle | support | row | 12 | bishop, cleric, druid, high_priestess |
| holy_smite | magic | single | 12 | bishop, cleric, druid, high_priestess |
| icestorm | melee | single | 20 | crusader, dreadnought, elven_fencer, feather_shield |
| icicle_dart | magic | single | 32 | crusader, dreadnought, elven_augur, elven_fencer |
| icy_blow | melee | single | 12 | berserker, breaker, dark_knight, doom_knight |
| icy_crush | melee | single | 12 | berserker, breaker, dark_knight, doom_knight |
| leaping_slash | melee | single | 20 | crusader, dreadnought, elven_fencer, feather_shield |
| lethal_venom | melee | column | 12 | elven_augur, elven_sibyl, great_knight, hoplite |
| lightning_shaker | magic | row | 12 | elven_augur, elven_sibyl, great_knight, hoplite |
| magick_attack | magic | single | 51 | arbalist, berserker, breaker, crusader |
| magick_shatter | melee | row | 7 | arbalist, elven_archer, feather_bow, hunter |
| magick_wall | support | single | 15 | crusader, dark_knight, doom_knight, feather_shield |
| painful_smash | melee | single | 12 | berserker, breaker, dark_knight, doom_knight |
| passive_shatter | melee | single | 7 | arbalist, elven_archer, feather_bow, hunter |
| passive_shatter_spear | melee | column | 12 | elven_augur, elven_sibyl, great_knight, hoplite |
| penetrate | melee | column | 12 | elven_augur, elven_sibyl, great_knight, hoplite |
| phantom_attack | magic | single | 51 | arbalist, berserker, breaker, crusader |
| phantom_veil | support | row | 12 | bishop, cleric, druid, high_priestess |
| poison_arrow | ranged | single | 7 | arbalist, elven_archer, feather_bow, hunter |
| poison_slash | melee | single | 20 | crusader, dreadnought, elven_fencer, feather_shield |
| powerful_impact | melee | single | 12 | berserker, breaker, dark_knight, doom_knight |
| provoking_slash | melee | single | 32 | berserker, breaker, crusader, dark_knight |
| rampage | melee | single | 12 | elven_augur, elven_sibyl, great_knight, hoplite |
| reincarnation | support | single | 63 | arbalist, berserker, bishop, breaker |
| resurrection | support | single | 12 | bishop, cleric, druid, high_priestess |
| sandstorm | ranged | all | 12 | bishop, cleric, druid, high_priestess |
| sanguine_attack | melee | single | 51 | arbalist, berserker, breaker, crusader |
| sanguine_darts | magic | column | 12 | bishop, cleric, druid, high_priestess |
| sanguine_rain | magic | all | 12 | bishop, cleric, druid, high_priestess |
| shadow_arrow | ranged | single | 7 | arbalist, elven_archer, feather_bow, hunter |
| shadow_thrust | melee | column | 12 | elven_augur, elven_sibyl, great_knight, hoplite |
| skyward_thrust | magic | single | 12 | bishop, cleric, druid, high_priestess |
| sonic_blast | melee | single | 20 | crusader, dreadnought, elven_fencer, feather_shield |
| sorcerous_blow | magic | single | 63 | arbalist, berserker, bishop, breaker |
| spiked_blow | melee | single | 12 | berserker, breaker, dark_knight, doom_knight |
| spiked_bolt | ranged | single | 7 | arbalist, elven_archer, feather_bow, hunter |
| strength_shatter | melee | single | 7 | arbalist, elven_archer, feather_bow, hunter |
| strength_shatter_ii | melee | single | 7 | arbalist, elven_archer, feather_bow, hunter |
| thunderous_thrust | magic | single | 12 | elven_augur, elven_sibyl, great_knight, hoplite |
| trinity_rain | magic | all | 12 | bishop, cleric, druid, high_priestess |
| triple_shatter | ranged | single | 7 | arbalist, elven_archer, feather_bow, hunter |
| true_thrust | melee | column | 10 | elven_augur, elven_sibyl, great_knight, knight |
| wall | support | single | 20 | crusader, dark_knight, doom_knight, dreadnought |
