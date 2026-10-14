# Классы Unicorn Overlord (справочник)

Собрано `python tools/uo_wiki.py` из unilord.miraheze.org. Образец для своих данных; оценки статов —
буквы S (лучше всех) .. F. Сила навыков — как в UO (100 = обычный удар), «удары» — число ударов.

## Arbalist → Shieldshooter (None почёта)

Тип: Bow Infantry Archer. Особенность: 2x damage for bow attacks v. Flying. Раздел: Base Class.

Статы: hp C, phys_atk A, phys_def D, mag_atk E, mag_def B, accuracy A, evasion E, crit_rate E, guard_rate B, initiative E

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Power Bolt | active | 1 AP | 1 | 120 |  | 1 | 100 | Attack a single enemy. [Ranged] |
| Toxic Bolt | active | 1 AP | 10 | 80 |  | 1 | 100 | Attack a single enemy.; Inflicts Poison. [Ranged] |
| Medical Aid | passive | 1 PP | 1 |  |  | 1 |  | Activates at the end of a battle.; Restore 15% HP to a row of allies.; Healing doubles if target's HP is 50% or less. |
| Quick Reload | passive | 1 PP | 15 | 50 |  | 1 | 100 | Activates after attacking.; Follow-up attacks a single enemy. [Ranged] |

## Berserker (повышение из Gladiator)

Тип: Axe Infantry. Особенность: N/A. Раздел: Promoted Class.

Статы: hp S, phys_atk A, phys_def F, mag_atk F, mag_def E, accuracy E, evasion F, crit_rate E, guard_rate D, initiative F

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Wide Smash | active | 1 AP | 1 | 150 |  | 1 | 80 | Attack a row of enemies.; +50 potency if the user is at 100% HP. |
| Mounting Charge | active | 1 AP | 20 |  |  |  |  | Restore 30% HP to the user.; Grants the user +30% Phys. Attack. |
| Grand Smash | active | 2 AP | 30 | 100 |  | 1 | 80 | Attack all enemies.; +50 potency if the user is at 100% HP. [Ranged, Ground, Based] |
| Bulk Up | passive | 1 PP | 1 |  |  |  |  | Activates after being hit by an attack.; Recover 40% HP. |
| Wide Counter | passive | 1 PP | 15 | 100 |  | 1 | 75 | Activates after an enemy attacks with an active skill.; Counterattack a row of enemies. |
| Berserk | passive | 1 PP | 25 |  |  |  |  | Activates before attacking with an active skill.; Consume all PP PP to grant the user +1 AP AP.; The user will survive one lethal blow. |

## Bishop (повышение из Cleric)

Тип: Staff Infantry Caster. Особенность: N/A. Раздел: Promoted Class.

Статы: hp C, phys_atk F, phys_def D, mag_atk C, mag_def S, accuracy C, evasion B, crit_rate F, guard_rate F, initiative E

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Heal | active | 1 AP | 1 |  | 100 | 1 |  | Restore moderate HP to an ally. |
| Sacred Heal | active | 2 AP | 25 |  | 100 | 1 |  | Restore moderate HP to a row of allies.; Removes all of target's debuffs. |
| Quick Heal | passive | 1 PP | 1 |  | 50 | 1 |  | Activates after an ally is hit by an attack.; Restore minor HP to an ally. |
| Refresh | passive | 1 PP | 10 |  |  |  |  | Activates after an ally is debuffed.; Remove all debuffs from a row of allies. |
| Lifesaver | passive | 1 PP | 15 |  | 50 |  |  | Activates before being attacked.; Heal self for minor HP recovery.; Grants user a buff to endure one lethal blow. |
| Parting Resurrection | passive | 1 PP | 20 |  |  | 1 |  | Activates at the end of battle.; Revive one ally, restorting them to 1 HP. |

## Breaker (повышение из Warrior)

Тип: Axe Infantry. Особенность: N/A. Раздел: Promoted Class.

Статы: hp B, phys_atk S, phys_def A, mag_atk F, mag_def C, accuracy D, evasion D, crit_rate F, guard_rate B, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Heavy Smash | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Ignores 100% Defense v. armored targets. [Unguardable] |
| Assaulting Blow | active | 1 AP | 10 | 100 |  | 1 | 100 | Attack a single enemy.; Grants the user +1 AP AP if the target is defeated [Unguardable] |
| Row Smash | active | 2 AP | 30 | 100 |  | 1 | 100 | Attack a row of enemies.; Ignores 100% Defense v. armored targets. [Unguardable, Uncoverable] |
| Binding Guard | passive | 1 PP | 1 |  |  |  |  | Activates before attacking with an active skill.; User's next attack will inflict Guard Seal. |
| Enrage | passive | 1 PP | 20 |  |  |  |  | Activates after an ally is hit by an attack.; Grants the user +20% Attack and +20% Accuracy.; (Effect stacks.) |
| Heavy Counter | passive | 1 PP | 25 | 150 |  | 1 | 100 | Activates after an enemy attacks with an active skill.; Counterattack a single enemy.; Ignores 100% Defense v. armored targets. |

## Cleric → Bishop (None почёта)

Тип: Staff Infantry Caster. Особенность: N/A. Раздел: Base Class.

Статы: hp D, phys_atk F, phys_def E, mag_atk C, mag_def S, accuracy C, evasion B, crit_rate F, guard_rate F, initiative E

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Heal | active | 1 AP | 1 |  | 100 | 1 |  | Restore moderate HP to an ally. |
| Quick Heal | passive | 1 PP | 1 |  | 50 | 1 |  | Activates after an ally is hit by an attack.; Restore minor HP to an ally. |
| Refresh | passive | 1 PP | 10 |  |  |  |  | Activates after an ally is debuffed.; Remove all debuffs from a row of allies. |
| Lifesaver | passive | 1 PP | 15 |  | 50 |  |  | Activates before being attacked.; Heal self for minor HP recovery.; Grants user a buff to endure one lethal blow. |

## Crusader → Valkyria (50 почёта)

Тип: Sword Shield Shield Infantry. Особенность: N/A. Раздел: Base Class.

Статы: hp B, phys_atk A, phys_def B, mag_atk E, mag_def C, accuracy C, evasion E, crit_rate E, guard_rate S, initiative E

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Vertical Edge | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Becomes a truestrike, ignores 50% defense, and +50 potency v. flying targets. |
| Iron Crusher | active | 1 AP | 10 | 100 |  | 1 | 100 | Attack a single enemy.; Ignores 50% Defense v. armored targets.; +50 potency v. armored targets. [Unguardable] |
| Maiden's Hammer | passive | 1 PP | 15 | 150 |  | 1 |  | Activates after an enemy attacks with an active skill.; Counterattack a single enemy.; Potency increases the less HP the user has.; (Maximum increase:+100) |

## Dark Knight → Doom Knight (None почёта)

Тип: Axe Shield Cavalry. Особенность: 2x physical damage v. Infantry. Раздел: Base Class.

Статы: hp B, phys_atk S, phys_def C, mag_atk C, mag_def E, accuracy D, evasion F, crit_rate E, guard_rate C, initiative E

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Vengeful Axe | active | 1 AP | 1 | 50 |  | 1 | 100 | Attacks a single enemy.; Damage increases the less HP the user has.; (Maximum increase: +100.) |
| Venom Axe | active | 1 AP | 10 | 75 |  | 1 | 100 | Attack a single enemy.; Inflicts Poison. |
| Vengeance | passive | 1 PP | 1 |  |  |  |  | Activates after being attacked.; Grants the user +20% Attack and +20% Defense. (Effect stacks.); Grants the user +1 PP PP if the user is at 50% HP or less. |
| Sanguine Arts | passive | 1 PP | 15 |  |  |  |  | Activates before attacking with an active skill.; User will reover HP equal to +50% of damage dealt on next attack. |

## Doom Knight (повышение из Dark Knight)

Тип: Axe Shield Cavalry. Особенность: 2x physical damage v. Infantry. Раздел: Promoted Class.

Статы: hp A, phys_atk S, phys_def B, mag_atk A, mag_def D, accuracy D, evasion F, crit_rate E, guard_rate B, initiative D

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Vengeful Axe | active | 1 AP | 1 | 50 |  | 1 | 100 | Attacks a single enemy.; Damage increases the less HP the user has.; (Maximum increase: +100.) |
| Venom Axe | active | 1 AP | 10 | 75 |  | 1 | 100 | Attack a single enemy.; Inflicts Poison. |
| Dark Flame | active | 2 AP | 20 | 50 | 50 | 1 | 100 | Consumes 30% of own HP to attack a row of enemies.; +50 potency v. debuffed targets.; Inflitcts Burn. |
| Vengeance | passive | 1 PP | 1 |  |  |  |  | Activates after being attacked.; Grants the user +20% Attack and +20% Defense. (Effect stacks.); Grants the user +1 PP PP if the user is at 50% HP or less. |
| Sanguine Arts | passive | 1 PP | 15 |  |  |  |  | Activates before attacking with an active skill.; User will reover HP equal to +50% of damage dealt on next attack. |
| Demonic Pact | passive | 1 PP | 25 |  |  |  |  | Activates after using an active skill.; Sacrifice 25% HP to grant user +1 AP AP. |

## Dreadnought

Тип: Sword Greatshield Infantry Armor. Особенность: N/A. Раздел: Promoted Class.

Статы: hp B, phys_atk S, phys_def B, mag_atk F, mag_def E, accuracy B, evasion F, crit_rate F, guard_rate A, initiative F

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Heavy Slash | active | 1 AP | 1 | 150 |  | 1 | 100 | Attack a single enemy. |
| Penetrate | active | 2 AP | 10 | 100 |  | 1 | 100 | Attacks a column of enemies with a piercing strike.; Inflicts Phys. Defense -30%. [Unguardable] |
| Omega Shatter | active | 2 AP | 35 | 100 |  | 2 | 100 | Attack a single enemy. [Unguardable] |
| Heavy Guard | passive | 1 PP | 1 |  |  |  |  | Activates before being hit by a physickal attack.; Block an emeny attack with a heavy guard. |
| Wild Kick | passive | 1 PP | 15 | 50 |  | 1 | 100 | Activates after an enemy guards against an ally's attack.; Attack a single enemy.; Inflicts Stun and Guard Seal. |
| Hawk Eye | passive | 2 PP | 25 |  |  |  |  | Activates before attacking with an active skill.; Makes the user's next attack a truestrike and guaranteed critical. |

## Druid (повышение из Shaman)

Тип: Staff Infantry Caster. Особенность: N/A. Раздел: Promoted Class.

Статы: hp B, phys_atk D, phys_def C, mag_atk D, mag_def S, accuracy C, evasion B, crit_rate C, guard_rate F, initiative A

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Passive Curse | active | 1 AP | 1 |  |  |  |  | Inflicts PP PP -1 and Initiative -10 on a row of enemies. [Ranged] |
| Offensive Curse | active | 1 AP | 10 |  |  |  |  | Inflicts Phys. Attack -50% and Mag. Attack -50% on a row of enemies. [Ranged] |
| Defensive Curse | active | 1 AP | 20 |  |  |  |  | Inflicts Phys. Attack -50%, Mag. Attack -50%, and Guard Seal on a row of enemies. [Ranged] |
| Compounding Curse | active | 1 AP | 30 |  |  |  |  | Make debuffs 1.5x more effective for a row of enemies. [Ranged] |
| Quick Curse | passive | 1 PP | 1 |  |  |  |  | Activates before an enemy uses an attack skill.; Inflicts Attack -20% for a single enemy's next attack.; Inflicts Critcal Seal. [Ranged, Limited] |
| Cursed Swamp | passive | 2 PP | 25 |  |  |  |  | Activates at the start of a battle.; Inflicts Initiative -10 and Evasion -30 on all enemies.; Inflicts PP PP -1 to cavalry targets. [Ranged, Limited] |

## Elven Archer →   (None почёта)

Тип: Bow Infantry Archer Caster Elf. Особенность: 2x damage for bow attacks v. Flying. Раздел: Promoted Class.

Статы: hp C, phys_atk C, phys_def E, mag_atk A, mag_def A, accuracy S, evasion D, crit_rate D, guard_rate F, initiative A

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Wind Arrow | active | 1 AP | 1 | 75 | 75 | 1 | 100 | Attack a single enemy.; Inflicts Evasion -50. [Ranged] |
| | pdmg number = (n/a) | active | 0 PP | 1 |  |  |  |  | Add magick damage (50 potency) to an ally's attacks. |
| Icicle Arrow | active | 2 AP | 30 | 75 | 75 | 1 | 100 | Attack two enemies.; Inflicts Freeze. [Ranged] |
| Quick Cure | passive | 1 PP | 1 |  |  |  |  | Activates after an ally is debuffed.; Remove all debuffs from an ally.; Grants the target immunity to one debuff. |
| Selfless Heal | passive | 1 PP | 15 |  | 50 | 1 |  | Activates after being healed.; Restore minor HP to all allies.; Remove all debuffs. |
| Pure Field | passive | 1 PP | 25 |  |  |  |  | Activates at the start of a battle.; Grants all allies a buff that negates a single debuff. [Limited] |

## Elven Augur

Тип: Spear Infantry Caster Elf. Особенность: N/A. Раздел: Promoted Class.

Статы: hp D, phys_atk B, phys_def D, mag_atk B, mag_def S, accuracy C, evasion A, crit_rate F, guard_rate F, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Primus Edge | active | 1 AP | 1 | 50 | 100 | 1 | 100 | Attack a single enemy.; If the user is at 100% HP, grants the user +1 PP PP and +1 summoned faeries. |
| Sylphic Wind | active | 2 AP | 20 |  | 40 | 3 | 100 | Attack a row of enemies with magick.; +20 potency v. flying targets.; Grants the user +1 summoned faeries. [Ranged] |
| Elemental Roar | active | 3 AP | 30 | 70 | 70 | 1 | 100 | Attak all enemies.; Potency increases with faerie count (+30 per faerie).; This dismisses all summoned faeries. [Ranged] |
| Curing Heal | passive | 1 PP | 1 |  | 50 | 1 |  | Activates after an ally is hit by an attack.; Restore minor HP to an ally.; Remove all of their debuffs. |
| Rage of the Faeries | passive | 1 PP | 25 |  | 100 | 1 | 100 | Activates at the start of a battle.; Attack a row of enemies with a magick first strike.; Inflicts Stun, grants the user +1 summoned faeries. [Ranged, Limited] |
| Elemental Impetus | passive | 2 PP | 35 |  |  |  |  | Activates after using an active skill.; Grants the user +1 AP AP +1 summoned faeries. |

## Elven Fencer

Тип: Sword Infantry Caster Elf. Особенность: N/A. Раздел: Promoted Class.

Статы: hp C, phys_atk B, phys_def D, mag_atk A, mag_def B, accuracy C, evasion B, crit_rate D, guard_rate D, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Lightning Blade | active | 1 AP | 1 | 75 | 75 | 1 | 100 | Attack a single enemy.; Inflicts Stun. |
| Nature’s Wrath | active | 1 AP | 20 |  | 100 | 1 | 100 | Attack a column of enemies with piercing magic.; Inflicts -1PP PP to cavalry targets. [Ranged, Ground, Based] |
| Mirage Stab | active | 2 AP | 30 | 75 | 75 | 1 | 100 | Attack a row of enemies.; Grants the user the ability to evade one attack. |
| Slyphic Barrier | passive | 0 PP | 1 |  |  |  |  | Activates before an ally is hit by a ranged phys. attack.; Allow an ally to evade one attack. [Limited] |
| Remove Weakness | passive | 1 PP | 15 |  |  |  |  | Activates after the user is debuffed.; Removes the user’s debuffs.; Grants user a buff to evade one attack. |
| Evasive Impetus | passive | 1 PP | 25 |  |  |  |  | Activates after evading an attack.; Grants the user +1 AP AP. |

## Elven Sibyl

Тип: Spear Infantry Caster Elf. Особенность: N/A. Раздел: Promoted Class.

Статы: hp D, phys_atk C, phys_def D, mag_atk A, mag_def S, accuracy C, evasion A, crit_rate F, guard_rate F, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Primus Edge | active | 1 AP | 1 | 50 | 100 | 1 | 100 | Attack a single enemy.; If the user is at 100% HP, grants the user +1 PP PP and +1 summoned faeries. |
| Faerie Heal | active | 2 AP | 20 |  | 100 | 1 |  | Restore moderate HP to a row of allies.; Grants the target immunity to damage for one attack.; Grants the user +1 summoned faeries. [Ranged] |
| Elemental Roar | active | 3 AP | 30 | 70 | 70 | 1 | 100 | Attak all enemies.; Potency increases with faerie count (+30 per faerie).; This dismisses all summoned faeries. [Ranged] |
| Curing Heal | passive | 1 PP | 1 |  | 50 | 1 |  | Activates after an ally is hit by an attack.; Restore minor HP to an ally.; Remove all of their debuffs. |
| Boon of the Faeries | passive | 1 PP | 25 |  | 100 | 1 |  | Activates at the start of a battle.; Restore moderate HP to a row of allies.; Grants a buff that negates a single debuff.; Grants the user +1 summoned faeries. [Limited] |
| Elemental Impetus | passive | 2 PP | 35 |  |  |  |  | Activates after using an active skill.; Grants the user +1 AP AP +1 summoned faeries. |

## Featherbow

Тип: . Особенность: . Раздел: Promoted Class.

Статы: hp None, phys_atk None, phys_def None, mag_atk None, mag_def None, accuracy None, evasion None, crit_rate None, guard_rate None, initiative None

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Feathershield

Тип: . Особенность: . Раздел: Promoted Class.

Статы: hp None, phys_atk None, phys_def None, mag_atk None, mag_def None, accuracy None, evasion None, crit_rate None, guard_rate None, initiative None

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Featherstaff

Тип: . Особенность: . Раздел: Promoted Class.

Статы: hp None, phys_atk None, phys_def None, mag_atk None, mag_def None, accuracy None, evasion None, crit_rate None, guard_rate None, initiative None

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Feathersword

Тип: Sword Shield Flying Angel. Особенность: 2x dodge rate v. grounded melee. Раздел: Promoted Class.

Статы: hp C, phys_atk C, phys_def C, mag_atk D, mag_def B, accuracy B, evasion S, crit_rate E, guard_rate B, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Spiral Sword | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Inflicts Evasion -20.; Grants the user +20 Evasion. [Ranged] |
| Shield Smite | active | 1 AP | 10 | 100 |  | 1 | 100 | Attack a single enemy.; Inflicts Defense -20%.; Grants the user +20% Defense. [Ranged] |
| Honed Slash | active | 2 AP | 30 | 70 |  | 3 | 100 | Attack a single enemy.; Becomes a truestrike if the user if buffed. [Ranged] |
| Accelerate | passive | 1 PP | 1 |  |  |  |  | Activates after an enemy attacks with an active skill.; Grants the user +20 Initiative and +20 Accuracy.; (Effect stacks.) |
| Diurnal Guard | passive | 1 PP | 15 |  |  |  |  | Activates before being hit by a physickal attack.; Block an enemy attack with a medium guard.; Grants the user +1 PP PP during the day. |
| Discharge | passive | 1 PP | 25 |  |  |  |  | Activates before attacking with an active skill.; Consume all of the user's buffs and increases attack power for one attack.; (Number of consumed buffs x 25%). |

## Fighter → Vanguard (25 почёта)

Тип: Sword Shield Infantry Armor. Особенность: N/A. Раздел: Base Class.

Статы: hp C, phys_atk C, phys_def B, mag_atk D, mag_def E, accuracy C, evasion E, crit_rate D, guard_rate S, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Warding Slash | active | 1 AP | 1 | 100 |  | 1 | 100 | Attacks a single enemy.; Grants the user +20% Phys. Defense. |
| Shield Bash | active | 1 AP | 15 | 50 |  | 1 | 100 | Attacks a single enemy.; Inflicts Stun. |
| Arrow Cover | passive | 1 PP | 1 |  |  |  |  | Activates before an ally is hit by a ranged phys. attack.; Cover an ally and nullify all damage. [Limited] |
| Quick Guard | passive | 1 PP | 10 |  |  |  |  | Activates before being hit by a physickal attack.; Block an enemy attack with a medium guard. |

## Gladiator → Berserker (None почёта)

Тип: Axe Infantry. Особенность: N/A. Раздел: Base Class.

Статы: hp S, phys_atk B, phys_def F, mag_atk F, mag_def E, accuracy F, evasion F, crit_rate E, guard_rate E, initiative F

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Wide Smash | active | 1 AP | 1 | 150 |  | 1 | 80 | Attack a row of enemies.; +50 potency if the user is at 100% HP. |
| Bulk Up | passive | 1 PP | 1 |  |  |  |  | Activates after being hit by an attack.; Recover 40% HP. |
| Wide Counter | passive | 1 PP | 15 | 100 |  | 1 | 75 | Activates after an enemy attacks with an active skill.; Counterattack a row of enemies. |

## Great Knight (повышение из Knight)

Тип: Spear Shield Cavalry. Особенность: 2x physical damage v. Infantry. Раздел: Promoted Class.

Статы: hp B, phys_atk A, phys_def A, mag_atk D, mag_def C, accuracy E, evasion F, crit_rate B, guard_rate B, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Assaulting Lance | active | 1 AP | 1 | 100 |  | 1 | 100 | Attacks a single enemy.; Grants the user +1AP if the target is defeated. |
| Wild Rush | active | 1 AP | 10 | 80 |  | 1 | 100 | Attack a column of enemies with a piercing strike.; Inflitcts Stun. |
| Pile Thrust | active | 2 AP | 20 | 50 |  | 3 | 100 | Attacks a single target with multiple hits.; Grants the user +1AP if the target is defeated. |
| Quick Guard | passive | 1 PP | 1 |  |  |  |  | Activates before being hit by a physickal attack.; Block an enemy attack with a medium guard. |
| Cavalier Call | passive | 1 PP | 15 |  |  |  |  | Activates before attacking with an active skill.; Grants cavalry allies in the user's row +20% Attack. (Effect stacks). |
| Knight's Pursuit | passive | 1 PP | 25 | 50 |  | 1 | 100 | Activates after a calavry-based ally attacks (Active).; Follow-up attack a column of enemies with a piercing strike. |

## Gryphon Knight → Gryphon Master (None почёта)

Тип: Axe Flying. Особенность: 2x dodge rate v. grounded melee / 2x phys. damage v. Cavalry. Раздел: Base Class.

Статы: hp D, phys_atk B, phys_def D, mag_atk E, mag_def B, accuracy D, evasion S, crit_rate D, guard_rate F, initiative D

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| High Swing | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a row of enemies.; Cavalry targets cannot guard against this attack.; +50 potency v. cavalry targets. [Ranged] |
| Wing Rest | passive | 1 PP | 1 |  |  | 1 |  | Activates at the end of a battle.; Recover 25% HP.; Recovered HP doubles if afflicted. |
| Feathering | passive | 1 PP | 15 |  |  |  |  | Activates before attacking with an active skill.; Grants allies in the user's row +15 Initiative. |

## Gryphon Master (повышение из Gryphon Knight)

Тип: Axe Flying. Особенность: 2x dodge rate v. grounded melee / 2x phys. damage v. Cavalry. Раздел: Promoted Class.

Статы: hp C, phys_atk B, phys_def C, mag_atk E, mag_def A, accuracy D, evasion S, crit_rate D, guard_rate F, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| High Swing | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a row of enemies.; Cavalry targets cannot guard against this attack.; +50 potency v. cavalry targets. [Ranged] |
| Fatal Dive | active | 2 AP | 20 |  |  | 1 | 100 | Attack a column of enemies with a piercing strike.; Deals damage equal to 50% of the user's HP.; (This attack cannot be a critcal.) [Ranged, Unguardable] |
| Aerial Smite | active | 2 AP | 30 | 100 |  | 1 | 100 | Attack a row of enemies.; Cavalry targets cannot guard against this attack.; Grants the user -1 AP AP if a target is at 100% HP. [Ranged] |
| Wing Rest | passive | 1 PP | 1 |  |  | 1 |  | Activates at the end of a battle.; Recover 25% HP.; Recovered HP doubles if afflicted. |
| Feathering | passive | 1 PP | 15 |  |  |  |  | Activates before attacking with an active skill.; Grants allies in the user's row +15 Initiative. |
| Gryphon Glide | passive | 2 PP | 25 |  |  |  |  | Activates before being hit by a ranged attack.; Evades a single hit of a ranged attack.; Grants the user +1 AP AP. |

## High Lord (повышение из Lord)

Тип: Sword Shield Cavalry. Особенность: 2x physical damage v. Infantry. Раздел: Promoted Class.

Статы: hp A, phys_atk C, phys_def A, mag_atk C, mag_def A, accuracy B, evasion A, crit_rate C, guard_rate S, initiative A

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Lean Edge | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Recover 25% HP if the attack hits.; Recover 25% HP if the target is defeated. |
| Cavalry Slayer | active | 1 AP | 10 | 100 |  | 1 | 100 | Attack a single enemy.; Inflicts AP AP -1, PP PP -1, and Guard Seal if the target is cavalry. |
| Spinning Edge | active | 2 AP | 30 | 60 |  | 2 | 100 | Attack a row of enemies.; Ignores 50% of the target's Defense.; Grants the user +1 PP PP if a target is defeated |
| Noble Guard | passive | 1 PP | 1 |  |  |  |  | Activates before being hit by a physickal attack.; Block an ememy attack with a medium guard.; Grants the user +20% Defense.; Grants the user +1 PP PP if the user has 50% HP or less. |
| Luminous Cover | passive | 1 PP | 5 |  |  |  |  | Activates before an ally is attacked.; Cover an ally with a medium guard.; Grants that ally +20% Defense. [Limited] |
| Rapid Order | passive | 1 PP | 25 |  |  |  |  | Activates at the start of a battle.; Grants all allies +20 Initiative. [Limited] |

## High Priestess (повышение из Priestess)

Тип: Staff Infantry Caster. Особенность: N/A. Раздел: Promoted Class.

Статы: hp C, phys_atk E, phys_def C, mag_atk B, mag_def S, accuracy C, evasion A, crit_rate F, guard_rate F, initiative D

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Holy Light | active | 1 AP | 1 |  | 100 | 1 | 100 | Attack a single enemy with magick.; Removes all of target's buffs. [Ranged] |
| Curing Call | active | 1 AP | 10 |  | 50 | 1 |  | Restore minor HP to a row of allies.; Removes all of target's debuff. |
| Innocent Ray | active | 1 AP | 30 |  | 150 | 1 | 100 | Attack a row of enemies with magick.; Removes all of target's buffs. [Ranged] |
| Passive Miracle | passive | 1 PP | 15 |  | 50 | 1 |  | Activates after receiving an ally's passive skill.; Restore minor HP and grant +1 PP PP to an ally. |
| Saint's Barrier | passive | 1 PP | 25 |  |  |  |  | Activates before an ally is attacked.; Reduce damage taken by an ally by 50% for one attack.; Also prevents them from being ddebuffed. [Limited] |
| Divine Blessing | passive | 1 PP | 35 |  |  |  |  | Activates at the start of a battle.; Grants all allies HP regeneration and +10% Defense. [Limited] |

## Hoplite → Legionnaire (None почёта)

Тип: Spear Greatshield Infantry Armor. Особенность: N/A. Раздел: Base Class.

Статы: hp B, phys_atk D, phys_def S, mag_atk E, mag_def F, accuracy D, evasion F, crit_rate F, guard_rate S, initiative F

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sting | active | 1 AP | 1 | 100 |  | 1 | 100 | Attacks a single enemy.; +50 potency if the user is below 50% HP. |
| Heavy Cover | passive | 1 PP | 1 |  |  |  |  | Activates before an ally is attacked.; Cover an ally with a heavy guard. [Limited] |
| Guardian | passive | 1 PP | 15 |  |  |  |  | Activates after being hit by a physickal attack.; Grants the user +20% Phys. Defense and; +20% Guard Rate. (Effect stacks.) |

## Housecarl → Viking (None почёта)

Тип: Axe Infantry. Особенность: N/A. Раздел: Base Class.

Статы: hp D, phys_atk A, phys_def C, mag_atk F, mag_def E, accuracy D, evasion D, crit_rate E, guard_rate D, initiative B

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Smash | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Inflicts Phys. Defense -20% . |
| Rolling Axe | active | 1 AP | 10 | 40 |  | 3 | 75 | Attack a row of enemies with multiple hits.; Inflicts Phys. Defense -15% . |
| Parting Blow | passive | 1 PP | 1 | 75 |  | 1 | 100 | Activates at the end pf a battle.; Attacks a single enemy. |
| Frenzied Strike | passive | 1 PP | 15 | 50 |  | 1 | 100 | Activates after an ally is hit by an attack.; Counterattack a single enemy.; Inflicts Phys. Defense -15% . |

## Hunter → Sniper (None почёта)

Тип: Bow Infantry Archer. Особенность: 2x damage for bow attacks v. Flying. Раздел: Base Class.

Статы: hp D, phys_atk C, phys_def E, mag_atk D, mag_def B, accuracy S, evasion C, crit_rate B, guard_rate E, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Single Shot | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy. [Ranged] |
| Dual Shot | active | 1 AP | 10 | 70 |  | 1 | 100 | Attack two enemies. [Ranged] |
| Eagle Eye | passive | 1 PP | 1 |  |  |  |  | Activates before attacking with an active skill.; Makes the user's next attack a truestrike. |
| Pursuit | passive | 1 PP | 15 |  |  |  | 7034 | Activates after an ally attacks (Active).; Follow-up attack a single enemy. |

## Knight → Great Knight (None почёта)

Тип: Spear Shield Cavalry. Особенность: 2x physical damage v. Infantry. Раздел: Base Class.

Статы: hp C, phys_atk B, phys_def B, mag_atk D, mag_def C, accuracy E, evasion F, crit_rate C, guard_rate C, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Assaulting Lance | active | 1 AP | 1 | 100 |  | 1 | 100 | Attacks a single enemy.; Grants the user +1AP if the target is defeated |
| Wild Rush | active | 1 AP | 10 | 80 |  | 1 | 100 | Attack a column of enemies with a piercing strike.; Inflitcts Stun. |
| Quick Guard | passive | 1 PP | 1 |  |  |  |  | Activates before being hit by a physickal attack.; Block an enemy attack with a medium guard. |
| Cavalier Call | passive | 1 PP | 15 |  |  |  |  | Activates before attacking with an active skill.; Grants cavalry allies in the user's row +20% Attack. (Effect stacks). |

## Landsknecht (повышение из Sellsword)

Тип: Sword / Infantry. Особенность: N/A. Раздел: Promoted Class.

Статы: hp A, phys_atk S, phys_def B, mag_atk F, mag_def D, accuracy E, evasion E, crit_rate C, guard_rate B, initiative E

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Heavy Slash | active | 1 AP | 1 | 150 |  | 1 | 100 | Attack a single enemy. |
| Killing Chain | active | 1 AP | 10 | 100 |  | 1 | 100 | Attack a single enemy.; Grants the user +1AP if the target is defeated. |
| Bastard's Cross | active | 2 AP | 20 | 70 |  | 2 | 100 | Attack a single enemy.; Potency increases based on the target's HP.; (Maximum increases: +60.) |
| Following Slash | passive | 1 PP | 1 | 75 |  | 1 | 90 | Activates after an ally is hit by an attack.; Counterattack a single enemy.; Grants the user +1PP PP if the attack hits. |
| Vengeful Guard | passive | 1 PP | 25 |  |  |  |  | Activates before being hit by a physickal attack.; Blocks an enemy attack with a medium guard.; Grants the user +20% Phys. Attack. (Effect stacks.) |
| Bull Force | passive | 2 PP | 30 |  |  |  |  | Activates after using an active skill.; Grants the user +1AP AP, +20% Phys. Attack, and +20 Initiative. |

## Legionnaire (повышение из Hoplite)

Тип: Spear Greatshield Infantry Armor. Особенность: N/A. Раздел: Promoted Class.

Статы: hp B, phys_atk C, phys_def S, mag_atk E, mag_def F, accuracy D, evasion F, crit_rate F, guard_rate S, initiative F

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sting | active | 1 AP | 1 | 100 |  | 1 | 100 | Attacks a single enemy.; +50 potency if the user is below 50% HP. |
| Row Protection | active | 1 AP | 25 |  |  |  |  | Grants allies in the user's row +50% Phys. Defense. |
| Greatshield | active | 1 AP | 30 |  |  |  |  | Grants the user +50% Phys. Defense and +2 PP PP. |
| Heavy Cover | passive | 1 PP | 1 |  |  |  |  | Activates before an ally is attacked.; Cover an ally with a heavy guard. [Limited] |
| Guardian | passive | 1 PP | 15 |  |  |  |  | Activates after being hit by a physickal attack.; Grants the user +20% Phys. Defense and; +20% Guard Rate. (Effect stacks.) |
| Row Cover | passive | 2 PP | 20 |  |  |  |  | Activates before an ally is attacked.; Cover a row of allies with a medium guard. [Limited] |

## Lord → High Lord (None почёта)

Тип: Sword Shield Infantry. Особенность: N/A. Раздел: Base Class.

Статы: hp B, phys_atk C, phys_def B, mag_atk C, mag_def B, accuracy B, evasion B, crit_rate C, guard_rate A, initiative B

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Lean Edge | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Recover 25% HP if the attack hits.; Recover 25% HP if the target is defeated. |
| Cavalry Slayer | active | 1 AP | 10 | 100 |  | 1 | 100 | Attack a single enemy.; Inflicts AP AP -1, PP PP -1, and Guard Seal if the target is cavalry. |
| Noble Guard | passive | 1 PP | 1 |  |  |  |  | Activates before being hit by a physickal attack.; Block an enemy attack with a medium guard.; Grants the user +20% Defense.; Grants the user +1 PP PP if the user has 50% HP or less. |
| Luminous Cover | passive | 1 PP | 5 |  |  |  |  | Activates before an ally is attacked.; Cover an ally with a medium guard.; Grants that ally +20% Defense. [Limited] |

## Paladin

Тип: Sword Shield Cavalry. Особенность: 2x physical damage v. Infantry. Раздел: Promoted Class.

Статы: hp B, phys_atk B, phys_def C, mag_atk B, mag_def S, accuracy C, evasion E, crit_rate D, guard_rate B, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Slice | active | 1 AP | 1 | 100 |  | 1 | 100 | Attacks a single enemy.; Grants the user +1 PP PP if the target is defeated. |
| Heal | active | 1 AP | 5 |  | 100 | 1 |  | Restore moderate HP to an ally. |
| Divine Cross | active | 2 AP | 30 | 50 | 50 | 2 |  | Attacks a single enemy and remove all buffs.; Grants the user +1 PP PP if the target is defeated. |
| Holy Barrier | passive | 1 PP | 1 |  |  |  |  | Activates before an ally is attacked.; Reduce damage taken by an ally by 50% for one attack.; Also prevents them from being afflicted. [Limited] |
| Holy Guard | passive | 1 PP | 10 |  |  |  |  | Activates before being hit by a physickal attack.; Block an enemy attack with a medium guard.; Prevents debuffs. |
| Pursuit | passive | 1 PP | 20 | 75 |  | 1 | 100 | Activates after an ally attacks (Active).; Follow-up attack a single enemy. |

## Priestess → High Priestess (None почёта)

Тип: Staff Infantry Caster. Особенность: N/A. Раздел: Base Class.

Статы: hp D, phys_atk E, phys_def D, mag_atk C, mag_def A, accuracy C, evasion B, crit_rate F, guard_rate F, initiative D

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Holy Light | active | 1 AP | 1 |  | 100 | 1 | 100 | Attack a single enemy with magick.; Removes all of target's buffs. [Ranged] |
| Curing Call | active | 1 AP | 10 |  | 50 | 1 |  | Restore minor HP to a row of allies.; Removes all of target's debuff. |
| Passive Miracle | passive | 1 PP | 15 |  | 50 | 1 |  | Activates after receiving an ally's passive skill.; Restore minor HP and grant +1 PP PP to an ally. |

## Prince

Тип: Sword Infantry. Особенность: N/A. Раздел: Promoted Class.

Статы: hp C, phys_atk C, phys_def C, mag_atk C, mag_def C, accuracy C, evasion C, crit_rate C, guard_rate C, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Banishing Stab | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Remove all of the target's buff. |
| Defensive Order | active | 1 AP | 10 |  |  |  |  | Grants all allies +20% Defense. |
| Offensive Order | active | 1 AP | 10 |  |  |  |  | Grants all allies +20% Attack. |
| Rapid Order | passive | 1 PP | 1 |  |  |  |  | Activates at the start of a battle.; Grants all allies +20 Initiative. [Limited] |
| Guard Order | passive | 1 PP | 15 |  |  |  |  | Activates before an ally is attacked.; Grants a row of allies +100% Guard Rate for one attack. [Limited] |
| Sniping Order | passive | 2 PP | 25 |  |  |  |  | Activates before an ally attacks (Active).; Make a row of allies' next attack a truestrike. [Limited] |

## Radiant Knight → Sainted Knight (None почёта)

Тип: Sword Shield Cavalry. Особенность: 2x physical damage v. Infantry. Раздел: Base Class.

Статы: hp B, phys_atk D, phys_def C, mag_atk C, mag_def S, accuracy C, evasion F, crit_rate F, guard_rate B, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Hache | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Grants the user +1PP PP if this attacks hits. |
| Row Heal | active | 1 AP | 10 |  | 100 | 1 |  | Restore moderate HP to a row of allies. |
| Magick Barrier | passive | 1 PP | 1 |  |  |  |  | Activates before an ally is hit by a magick attack.; Negate the next magick damage dealt to an ally.; Also negates afflictions. [Limited] |
| Holy Guard | passive | 1 PP | 15 |  |  |  |  | Activates before being hit by a physickal attack.; Block an enemy attack with a medium guard.; Prevents debuffs. |

## Rogue (повышение из Thief)

Тип: Sword Infantry Scout. Особенность: N/A. Раздел: Promoted Class.

Статы: hp E, phys_atk D, phys_def F, mag_atk D, mag_def C, accuracy A, evasion S, crit_rate S, guard_rate F, initiative S

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Passive Steal | active | 1 AP | 1 | 50 |  | 2 | 100 | Attacks a single enemy.; Steal all of the enemy's PPPP.; (Does not apply if they guard the first hit.) |
| Toxic Throw | active | 1 AP | 10 | 25 |  | 2 | 100 | Attack a single enemy.; Inflicts Poison. [Ranged] |
| Shadowbite | active | 2 AP | 20 | 15 |  | 2 | 100 | Attack a row of enemies.; Inflicts Blindness.; Inflicts Initiative -20 and Evasion -20. [Ranged] |
| Active Steal | active | 2 AP | 30 | 25 |  | 4 | 100 | Attack a single enemy.; Steal 1 of the enemy's AP AP.; (Does not apply if they guard the first hit.) |
| Evade | passive | 1 PP | 1 |  |  |  |  | Activates before being attacked.; Evade a single hit. |
| Sneaking Edge | passive | 1 PP | 25 | 50 |  | 2 | 100 | Activates at the start of a battle.; Attack a single enemy with a first strike.; Inflicts Guard Seal and Passive Seal. [Ranged, Uncoverable, Limited] |

## Sainted Knight (повышение из Radiant Knight)

Тип: Spear Shield Cavalry. Особенность: 2x physical damage v. Infantry. Раздел: Promoted Class.

Статы: hp B, phys_atk C, phys_def C, mag_atk B, mag_def S, accuracy C, evasion F, crit_rate F, guard_rate B, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Hache | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Grants the user +1PP PP if this attacks hits. |
| Row Heal | active | 1 AP | 10 |  | 100 | 1 |  | Restore moderate HP to a row of allies. |
| Saint's Blade | active | 1 AP | 25 | 50 |  | 2 | 100 | Attack a single enemy.; +25 potency if the user is at 100% HP.; Grants the user +1PP PP if this attacks hits. |
| Magick Barrier | passive | 1 PP | 1 |  |  |  |  | Activates before an ally is hit by a magick attack.; Negate the next magick damage dealt to an ally.; Also negates afflictions. [Limited] |
| Holy Guard | passive | 1 PP | 15 |  |  |  |  | Activates before being hit by a physickal attack.; Block an enemy attack with a medium guard.; Prevents debuffs. |
| Row Barrier | passive | 2 PP | 20 |  |  |  |  | Activates before an ally is hit by a magick attack.; Negate the next magick damage dealt to a row of allies.; Also negates afflictions. [Limited] |

## Sellsword → Landsknecht (None почёта)

Тип: Sword / Infantry. Особенность: N/A. Раздел: Base Class.

Статы: hp B, phys_atk S, phys_def B, mag_atk F, mag_def D, accuracy E, evasion E, crit_rate D, guard_rate C, initiative E

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Heavy Slash | active | 1 AP | 1 | 150 |  | 1 | 100 | Attack a single enemy. |
| Killing Chain | active | 1 AP | 10 | 100 |  | 1 | 100 | Attack a single enemy.; Grants the user +1AP if the target is defeated. |
| Following Slash | passive | 1 PP | 1 | 75 |  | 1 | 90 | Activates after an ally is hit by an attack.; Counterattack a single enemy.; Grants the user +1PP PP if the attack hits. |

## Sergeant (повышение из Soldier)

Тип: Spear Infantry. Особенность: N/A. Раздел: Promoted Class.

Статы: hp C, phys_atk B, phys_def B, mag_atk D, mag_def C, accuracy C, evasion C, crit_rate D, guard_rate E, initiative B

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Long Thrust | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a column of enemies with a piercing strike.; Cavalry targets cannot guard against this attack.; Grants +50 potency v. cavalry targets. |
| Javelin | active | 1 AP | 10 | 100 |  | 1 | 100 | Attack a single enemy.; Grants +50 potency v. flying targets. [Ranged] |
| Honed Spear | active | 2 AP | 20 | 130 |  | 1 | 100 | Attack a column of enemies with a piercing strike.; +50 potency if the user if buffed.; Cavalry targets cannot guard against this attack. |
| First Aid | passive | 1 PP | 1 |  |  | 1 |  | Activates at the end of a battle.; Restore 25% HP to an ally. |
| Keen Call | passive | 1 PP | 15 |  |  |  |  | Activates before an ally attacks (Active).; Grants 100% Critical Rate for an ally's next attack. [Limited] |
| Active Gift | passive | 2 PP | 25 |  |  |  |  | Activates after an ally uses an active skill.; Grants an ally +1 AP AP. |

## Shaman → Druid (None почёта)

Тип: Staff Infantry Caster. Особенность: N/A. Раздел: Base Class.

Статы: hp C, phys_atk D, phys_def C, mag_atk D, mag_def S, accuracy C, evasion B, crit_rate C, guard_rate F, initiative B

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Passive Curse | active | 1 AP | 1 |  |  |  |  | Inflicts PP PP -1 and Initiative -10 on a row of enemies. [Ranged] |
| Offensive Curse | active | 1 AP | 10 |  |  |  |  | Inflicts Phys. Attack -50% and Mag. Attack -50% on a row of enemies. [Ranged] |
| Quick Curse | passive | 1 PP | 1 |  |  |  |  | Activates before an enemy uses an attack skill.; Inflicts Attack -20% for a single enemy's next attack.; Inflicts Critcal Seal. [Ranged, Limited] |

## Shieldshooter (повышение из Arbalist)

Тип: Bow Greatshield Infantry Archer. Особенность: 2x damage for bow attacks v. Flying. Раздел: Promoted Class.

Статы: hp C, phys_atk A, phys_def C, mag_atk E, mag_def B, accuracy S, evasion E, crit_rate E, guard_rate S, initiative D

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Power Bolt | active | 1 AP | 1 | 120 |  | 1 | 100 | Attack a single enemy. [Ranged] |
| Toxic Bolt | active | 1 AP | 10 | 80 |  | 1 | 100 | Attack a single enemy.; Inflicts Poison. [Ranged] |
| Heavy Bolt | active | 2 AP | 20 | 100 |  | 1 | 100 | Attack a single enemy.; +100 potency if the user is in the front row. [Ranged] |
| Medical Aid | passive | 1 PP | 1 |  |  | 1 |  | Activates at the end of a battle.; Restore 15% HP to a row of allies.; Healing doubles if target's HP is 50% or less. |
| Quick Reload | passive | 1 PP | 15 | 50 |  | 1 | 100 | Activates after attacking.; Follow-up attacks a single enemy. [Ranged] |
| Aid Cover | passive | 1 PP | 25 |  |  |  |  | Activates before an ally is attacked.; Cover an ally with a medium guard.; Restores 25% HP to that ally. [Limited] |

## Sniper (повышение из Hunter)

Тип: Bow Infantry Archer. Особенность: 2x damage for bow attacks v. Flying. Раздел: Promoted Class.

Статы: hp C, phys_atk B, phys_def E, mag_atk D, mag_def A, accuracy S, evasion B, crit_rate A, guard_rate E, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Single Shot | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy. [Ranged] |
| Dual Shot | active | 1 AP | 10 | 70 |  | 1 | 100 | Attack two enemies. [Ranged] |
| Row Shot | active | 2 AP | 20 | 100 |  | 1 | 100 | Attack a row of enemies. [Ranged] |
| Eagle Eye | passive | 1 PP | 1 |  |  |  |  | Activates before attacking with an active skill.; Makes the user's next attack a truestrike. |
| Pursuit | passive | 1 PP | 15 | 75 |  | 1 | 100 | Activates after an ally attacks (Active).; Follow-up attack a single enemy. |
| Aerial Snipe | passive | 1 PP | 25 | 50 |  | 1 | 100 | Activates after an ally is hit by an attack.; Counterattack a single enemy.; +100 potency v. flying targets. |

## Snow Ranger

Тип: Bow Infantry Archer. Особенность: 2x damage for bow attacks v. Flying. Раздел: Promoted Class.

Статы: hp C, phys_atk C, phys_def D, mag_atk D, mag_def C, accuracy S, evasion S, crit_rate S, guard_rate F, initiative B

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mystic Arrow | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Deals additional magick attack of 100 potenecy to armored targets. [Ranged] |
| Sonic Shaft | active | 1 AP | 20 | 100 |  | 1 | 100 | Attack a single enemy.; Deals 100% of target's Initiative in additional damage. [Ranged] |
| Glacial Rain | active | 2 AP | 30 | 60 |  | 3 | 80 | Attack all enemies.; Inflicts Freeze.; (User cannot evade or use passive skills while charging.) [Ranged, Charge] |
| Eagle's Eye | passive | 0 PP | 1 |  |  |  |  | Activates before attacking with an active skill.; Makes the user's next attack a truestrike. [Ranged] |
| Triple Counter | passive | 1 PP | 15 | 100 |  | 1 | 100 | Activates after an enemy attacks with an active skill.; Counterattack three enemies. [Ranged] |
| Snow-white Strike | passive | 1 PP | 35 | 75 |  | 1 | 100 | Activates after an ally attacks (Active).; Follow-up attack a single enemy.; Inflicts Freeze.; +100 potency v. forzen targets. [Ranged] |

## Soldier → Sergeant (None почёта)

Тип: Spear Infantry. Особенность: N/A. Раздел: Base Class.

Статы: hp C, phys_atk B, phys_def C, mag_atk D, mag_def C, accuracy D, evasion C, crit_rate D, guard_rate E, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Long Thrust | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a column of enemies with a piercing strike.; Cavalry targets cannot guard against this attack.; Grants +50 potency v. cavalry targets. |
| Javelin | active | 1 AP | 10 | 100 |  | 1 | 100 | Attack a single enemy.; Grants +50 potency v. flying targets. [Ranged] |
| First Aid | passive | 1 PP | 1 |  |  | 1 |  | Activates at the end of a battle.; Restore 25% HP to an ally. |
| Keen Call | passive | 1 PP | 15 |  |  |  |  | Activates before an ally attacks (Active).; Grants 100% Critical Rate for an ally's next attack. [Limited] |

## Sorceress (повышение из Witch)

Тип: Staff Infantry Caster. Особенность: N/A. Раздел: Promoted Class.

Статы: hp D, phys_atk F, phys_def E, mag_atk A, mag_def S, accuracy D, evasion C, crit_rate F, guard_rate F, initiative E

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Icebolt | active | 1 AP | 1 |  | 100 | 1 | 100 | Attack a single enemy with magick.; Inflicts Freeze. [Ranged] |
| Magick Missile | active | 1 AP | 10 |  | 70 | 1 | 100 | Attack two enemies with magick. [Ranged] |
| Ice Coffin | active | 2 AP | 30 |  | 100 | 1 | 100 | Attack a row enemies with magick.; Inflicts Freeze.; +50 potency v. frozen targets. [Ranged] |
| Magick Conferral | passive | 1 PP | 1 |  |  |  |  | Activates before an ally's physickal attack (Active).; Add magick damage to an ally's next attack. (50 potency.) [Limited] |
| Focus Sight | passive | 1 PP | 15 |  |  |  |  | Activates before an ally attacks (Active).; Make an ally's next attack a truestrike. [Limited] |
| Quick Cast | passive | 2 PP | 25 |  |  |  |  | Activates at the start of a battle.; Grants the user max Initiative for their next action and -50 Critical Rate. [Limited] |

## Sword Master (повышение из Swordfighter)

Тип: Sword Infantry. Особенность: N/A. Раздел: Promoted Class.

Статы: hp D, phys_atk C, phys_def E, mag_atk D, mag_def B, accuracy S, evasion S, crit_rate S, guard_rate E, initiative S

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Keen Edge | active | 1 AP | 1 | 100 |  | 1 |  | Attack a single enemy with a critical strike. (Critical rate+50%.) |
| Impale | active | 1 AP | 15 | 100 |  | 1 | 100 | Attacks a single enemy.; Grants the user +1PPPP if the target is defeated. |
| Meteor Slash | active | 2 AP | 20 | 20 |  | 9 | 100 | Attacks a single enemy with a critical flurry.; (Critical rate +30%.) |
| Hastened Strike | passive | 0 PP | 1 | 150 |  | 1 |  | Activates at the start of a battle.; Attack a single enemy with a first strike. [Limited] |
| Parry | passive | 1 PP | 10 |  |  |  |  | Activates before being hit by a melee attack.; Negate melee damage for a single hit.; Grants the user +1APAP. |
| Charged Impetus | passive | 2 PP | 25 |  |  |  |  | Activates after using an active skill.; Grants the user +1APAP and +50% Critical damage. |

## Swordfighter → Sword Master (None почёта)

Тип: Sword Infantry. Особенность: N/A. Раздел: Base Class.

Статы: hp D, phys_atk C, phys_def E, mag_atk D, mag_def B, accuracy S, evasion S, crit_rate S, guard_rate E, initiative S

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Keen Edge | active | 1 AP | 1 | 100 |  | 1 |  | Attack a single enemy with a critical strike. (Critical rate+50%.) |
| Impale | active | 1 AP | 15 | 100 |  | 1 | 100 | Attacks a single enemy.; Grants the user +1PPPP if the target is defeated. |
| Hastened Strike | passive | 0 PP | 1 | 150 |  | 1 |  | Activates at the start of a battle.; Attack a single enemy with a first strike. [Limited] |
| Parry | passive | 1 PP | 10 |  |  |  |  | Activates before being hit by a melee attack.; Negate melee damage for a single hit.; Grants the user +1APAP. |

## Thief → Rogue (None почёта)

Тип: Sword Infantry Scout. Особенность: N/A. Раздел: Base Class.

Статы: hp E, phys_atk D, phys_def F, mag_atk D, mag_def C, accuracy A, evasion S, crit_rate A, guard_rate F, initiative S

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Passive Steal | active | 1 AP | 1 | 50 |  | 2 | 100 | Attacks a single enemy.; Steal all of the enemy's PPPP.; (Does not apply if they guard the first hit.) |
| Toxic Throw | active | 1 AP | 10 | 25 |  | 2 | 100 | Attack a single enemy.; Inflicts Poison. [Ranged] |
| Evade | passive | 1 PP | 1 |  |  |  |  | Activates before being attacked.; Evade a single hit. |

## Valkyria (повышение из Crusader)

Тип: Sword Shield Shield Infantry. Особенность: N/A. Раздел: Promoted Class.

Статы: hp A, phys_atk A, phys_def A, mag_atk E, mag_def C, accuracy C, evasion E, crit_rate D, guard_rate S, initiative D

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Vertical Edge | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Becomes a truestrike, ignores 50% defense, and +50 potency v. flying targets. |
| Iron Crusher | active | 1 AP | 10 | 100 |  | 1 | 100 | Attack a single enemy.; Ignores 50% Defense v. armored targets.; +50 potency v. armored targets. [Unguardable] |
| Brandish | active | 2 AP | 30 | 50 |  | 3 | 100 | Attack a single enemy.; Ignores 50% of the target's Defense.; Grants the user +1 PP PP if the attack hits. [Unguardable] |
| Maiden's Hammer | passive | 1 PP | 15 | 150 |  | 1 |  | Activates after an enemy attacks with an active skill.; Counterattack a single enemy.; Potency increases the less HP the user has.; (Maximum increase:+100) |
| Iron Veil | passive | 1 PP | 25 |  |  |  |  | Activates at the start of a battle.; Grants +50% Guard Rate and +30% Phys. Defense to all allies. [Limited] |
| Undying Will | passive | 1 PP | 35 |  |  |  |  | Activates before attacking with an active skill.; Attack potency increases as HP decreases.(Maximum increase:+100); Grants the ablility to survive one lethal blow. |

## Vanguard (повышение из Fighter)

Тип: Sword Shield Infantry Armor. Особенность: N/A. Раздел: Promoted Class.

Статы: hp B, phys_atk C, phys_def A, mag_atk D, mag_def E, accuracy C, evasion E, crit_rate D, guard_rate S, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Warding Slash | active | 1 AP | 1 | 100 |  | 1 | 100 | Attacks a single enemy.; Grants the user +20% Phys. Defense. |
| Shield Bash | active | 1 AP | 15 | 50 |  | 1 | 100 | Attacks a single enemy.; Inflicts Stun. |
| Defender | active | 2 AP | 20 | 75 |  | 2 | 100 | Attacks a single enemy.; Grants the user 50% Phys. Defense.; Grants the user +1 PP PP if this attacks hits. |
| Arrow Cover | passive | 1 PP | 1 |  |  |  |  | Activates before an ally is hit by a ranged phys. attack.; Cover an ally and nullify all damage. [Limited] |
| Quick Guard | passive | 1 PP | 10 |  |  |  |  | Activates before being hit by a physickal attack.; Block an enemy attack with a medium guard. |
| Provoke | passive | 1 PP | 25 |  |  |  |  | Activates at the start of a battle.; Force a row of enemies to focus attacks on the user. Grants the user +50% Guard Rate. [Ranged, Limited] |

## Viking (повышение из Housecarl)

Тип: Axe Infantry. Особенность: N/A. Раздел: Promoted Class.

Статы: hp C, phys_atk A, phys_def C, mag_atk F, mag_def E, accuracy C, evasion D, crit_rate D, guard_rate C, initiative B

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Smash | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Inflicts Phys. Defense -20% . |
| Rolling Axe | active | 1 AP | 10 | 40 |  | 3 | 75 | Attack a row of enemies with multiple hits.; Inflicts Phys. Defense -15% . |
| Wide Breaker | active | 2 AP | 20 | 100 |  | 1 | 100 | Attack a row of enemies.; Inflicts Phys. Defense -30% .; +50 potency v. debuffed targets. |
| Parting Blow | passive | 1 PP | 1 | 75 |  | 1 | 100 | Activates at the end of a battle.; Attacks a single enemy. |
| Frenzied Strike | passive | 1 PP | 15 | 50 |  | 1 | 100 | Activates after an ally is hit by an attack.; Counterattack a single enemy.; Inflicts Phys. Defense -15% . |
| War Horn | passive | 2 PP | 25 |  |  |  |  | Activates at the start of a battle.; Make all allies attack skills unguardable. [Limited] |

## Warlock (повышение из Wizard)

Тип: Staff Infantry Caster. Особенность: N/A. Раздел: Promoted Class.

Статы: hp D, phys_atk F, phys_def E, mag_atk S, mag_def S, accuracy E, evasion D, crit_rate F, guard_rate F, initiative E

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fireball | active | 1 AP | 1 |  | 40 | 3 | 100 | Attack a single enemy with magick.; Inflicts Burn. [Ranged] |
| Thunderous Strike | active | 2 AP | 20 |  | 100 | 1 | 90 | Attack a row of enemies with magick.; Inflicts Stun. [Ranged] |
| Volcano | active | 2 AP | 30 |  | 150 | 1 | 90 | Attack a column of enemies with piercing magick.; Inflicts Burn. [Ranged] |
| Magick Counter | passive | 1 PP | 1 |  | 150 | 1 | 100 | Activates after an enemy attacks with an active skill.; Counterattack a single enemy with magick. [Ranged] |
| Magick Pursuit | passive | 1 PP | 15 |  | 100 | 1 | 100 | Activates after ally uses a magick attack (Active).; Follow-up attack a single enemy with magick. [Ranged] |
| Concentrate | passive | 2 PP | 25 |  |  |  |  | Activates after using an active skill.; Grants the user +1 AP AP and +40 Accuracy. [Ranged] |

## Warrior → Breaker (None почёта)

Тип: Axe Infantry. Особенность: N/A. Раздел: Base Class.

Статы: hp C, phys_atk S, phys_def B, mag_atk F, mag_def C, accuracy D, evasion D, crit_rate F, guard_rate C, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Heavy Smash | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Ignores 100% Defense v. armored targets. [Unguardable] |
| Assaulting Blow | active | 1 AP | 10 | 100 |  | 1 | 100 | Attack a single enemy.; Grants the user +1 AP AP if the target is defeated [Unguardable] |
| Binding Guard | passive | 1 PP | 1 |  |  |  |  | Activates before attacking with an active skill.; User's next attack will inflict Guard Seal. |

## Werebear

Тип: Axe Greatshield Infantry Armor Bestral. Особенность: All stats increase at night.. Раздел: Promoted Class.

Статы: hp S, phys_atk B, phys_def C, mag_atk F, mag_def F, accuracy F, evasion F, crit_rate E, guard_rate S, initiative F

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Bear Crush | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Inflicts Stun. [Unguardable] |
| Round Swing | active | 2 AP | 10 | 25 |  | 3 | 75 | Attack a row of enemies.; Damage increases the more HP the user has.; {Maximum increase: +50.) [Unguardable] |
| Earthshaker | active | 2 AP | 30 | 75 |  | 1 | 100 | Attack all enemies.; Damage increases the less HP the user has.; {Maximum increase: +75.) [Ranged, Unguardable, Ground, Based] |
| Heavy Guard | passive | 1 PP | 1 |  |  |  |  | Activates before being hit by a physickal attack.; Block an enemy attack with a heavy guard. |
| Nocturnal Rest | passive | 1 PP | 15 |  |  |  |  | Activates after attacking.; Recover 30% HP.; Recovered HP doubles at night. |
| Life Blow | passive | 1 PP | 25 |  |  | 1 | 100 | Activates at the end of a battle.; Attack a single enemy.; Deals damage equal to 80% of the user's HP.; (This attack cannot be a critical) [Unguardable] |

## Werefox

Тип: Spear Infantry ScoutBestral. Особенность: All stats increase at night.. Раздел: Promoted Class.

Статы: hp D, phys_atk C, phys_def E, mag_atk D, mag_def C, accuracy A, evasion S, crit_rate S, guard_rate F, initiative S

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Piercing Lance | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Inflicts Guard Seal. |
| Passive Hold | active | 1 AP | 10 | 100 |  | 1 | 100 | Attack a single enemy.; Inflicts Passive Seal |
| Venom Thrust | active | 2 AP | 30 | 75 |  | 1 | 100 | Attack a column of enemies with a piercing strike.; Inflicts Poison and debuffs target HP recovery by -50%.; +50 potency v. poisoned targets. |
| Nocturnal Evade | passive | 1 PP | 1 |  |  |  |  | Activates before being attacked.; Evade a single hit.; Grants the user +1 PP PP at night. |
| Shadow Pursuit | passive | 1 PP | 15 | 75 |  | 1 | 100 | Activates after an ally attacks (Active).; Follow-up attack a single enemy.; Inflicts Blindness. |
| Weakness Hunter | passive | 2 PP | 25 | 100 |  | 1 | 100 | Activates after an enemy is debuffed.; Attack a single enemy.; Ignores 50% of the target's Defense. [Unguardable] |

## Werelion

Тип: Axe Infantry Bestral. Особенность: All stats increase at night.. Раздел: Promoted Class.

Статы: hp S, phys_atk A, phys_def F, mag_atk F, mag_def E, accuracy E, evasion F, crit_rate E, guard_rate D, initiative F

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Wide Smash | active | 1 AP | 1 | 150 |  | 1 | 80 | Attack a row of enemies.; +50 potency if the user is at 100% HP. |
| Mounting Charge | active | 1 AP | 20 |  |  |  |  | Restore 30% HP to the user.; Grants the user +30% Phys. Attack. |
| Grand Smash | active | 2 AP | 30 | 100 |  | 1 | 80 | Attack all enemies.; +50 potency if the user is at 100% HP. [Ranged, Ground, Based] |
| Bulk Up | passive | 1 PP | 1 |  |  |  |  | Activates after being hit by an attack.; Recover 40% HP. |
| Wide Counter | passive | 1 PP | 15 | 100 |  | 1 | 75 | Activates after an enemy attacks with an active skill.; Counterattack a row of enemies. |
| Berserk | passive | 1 PP | 25 |  |  |  |  | Activates before attacking with an active skill.; Consume all PP PP to grant the user +1 AP AP.; The user will survive one lethal blow. |

## Wereowl

Тип: Staff Flying Caster Bestral. Особенность: 2x dodge rate v. grounded melee / All stats increase at night.. Раздел: Promoted Class.

Статы: hp D, phys_atk F, phys_def F, mag_atk C, mag_def S, accuracy C, evasion B, crit_rate F, guard_rate F, initiative B

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Aurora Veil | active | 1 AP | 1 |  |  |  |  | Grants HP regeneration to a row of allies.; Grants targets +50 Mag. Defense. |
| Night Vision | active | 1 AP | 10 |  |  |  |  | Grants a row of allies +50 Accuracy.; At night, makes the targets' next attack a truestrike. |
| Extra Heal | active | 2 AP | 30 |  | 100 | 1 |  | Restore moderate HP to an ally.; Grants HP regeneration and +30 Initiative. |
| Restore | passive | 1 PP | 1 |  |  |  |  | Activates after an ally uses a passive skill.; Grants an ally +1 PP PP. |
| Quick Dispel | passive | 1 PP | 15 |  |  |  |  | Activates after an enemy is buffed.; Remove all buffs from a single enemy. [Ranged] |
| Circle Barrier | passive | 2 PP | 25 |  |  |  |  | Activates before an ally is attacked.; Reduce damage taken by all allies by 25% for one attack. [Limited] |

## Werewolf

Тип: Sword Infantry Bestral. Особенность: All stats increase at night.. Раздел: Promoted Class.

Статы: hp B, phys_atk B, phys_def D, mag_atk F, mag_def E, accuracy S, evasion C, crit_rate B, guard_rate F, initiative B

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Finishing Stab | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Grants the user +50% Phys. Attack if the target is defeated. |
| Decimate | active | 1 AP | 10 | 75 |  | 1 | 100 | Attack a single enemy.; Potency increases the fewer enemies there are.; (Maximum increase: +100.) |
| Wild Fang | active | 2 AP | 30 | 20 |  | 3 | 100 | Attack a row of enemies.; Potency increases the less HP a target has.; (Maximum increase: +50.) |
| Nocturnal Strike | passive | 1 PP | 1 | 150 |  | 1 | 100 | Activates at the start of a battle.; Attack an enemy with a first strike.; Grants the user +1 PP PP at night. [Limited] |
| Bestral Howl | passive | 1 PP | 15 |  |  |  |  | Activates before attacking with an active skill.; Grants allies in the user's row +15% Phys. Attack. |
| Killing Pursuit | passive | 1 PP | 25 | 75 |  | 1 | 100 | Activates after an ally attacks (Active).; Follow-up attack a single enemy.; Grants the user +1 AP AP if the target is defeated. |

## Witch → Sorceress (None почёта)

Тип: Staff Infantry Caster. Особенность: N/A. Раздел: Base Class.

Статы: hp E, phys_atk F, phys_def E, mag_atk B, mag_def S, accuracy D, evasion C, crit_rate F, guard_rate F, initiative E

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Icebolt | active | 1 AP | 1 |  | 100 | 1 | 100 | Attack a single enemy with magick.; Inflicts Freeze. [Ranged] |
| Magick Missile | active | 1 AP | 10 |  | 70 | 1 | 100 | Attack two enemies with magick. [Ranged] |
| Magick Conferral | passive | 1 PP | 1 |  |  |  |  | Activates before an ally's physickal attack (Active).; Add magick damage to an ally's next attack. (50 potency.) [Limited] |
| Focus Sight | passive | 1 PP | 15 |  |  |  |  | Activates before an ally attacks (Active).; Make an ally's next attack a truestrike. [Limited] |

## Wizard → Warlock (None почёта)

Тип: Staff Infantry Caster. Особенность: N/A. Раздел: Base Class.

Статы: hp D, phys_atk F, phys_def E, mag_atk A, mag_def A, accuracy E, evasion D, crit_rate F, guard_rate F, initiative E

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fireball | active | 1 AP | 1 |  | 40 | 3 | 100 | Attack a single enemy with magick.; Inflicts Burn. [Ranged] |
| Magick Counter | passive | 1 PP | 1 |  | 150 | 1 | 100 | Activates after an enemy attacks with an active skill.; Counterattack a single enemy with magick. [Ranged] |
| Magick Pursuit | passive | 1 PP | 15 |  | 100 | 1 | 100 | Activates after ally uses a magick attack (Active).; Follow-up attack a single enemy with magick. [Ranged] |

## Wyvern Knight → Wyvern Master (None почёта)

Тип: Spear Flying. Особенность: 2x dodge rate v. grounded melee / 2x phys. damage v. Cavalry. Раздел: Base Class.

Статы: hp C, phys_atk B, phys_def B, mag_atk F, mag_def E, accuracy C, evasion A, crit_rate C, guard_rate E, initiative C

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Diving Thrust | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Cavalry targets cannot guard against this attack.; +50 potency v. cavalry targets. [Ranged] |
| Ground Counter | passive | 1 PP | 1 | 50 |  | 1 | 100 | Activates after an enemy attacks with an active skill.; Counterattack a single enemy.; +100 potency v. cavalry targets. |
| Deflect | passive | 1 PP | 15 |  |  |  |  | Activates before being hit by a melee attack.; Negate melee damage for a single hit.; Grants the user; +20 Evasion. (Effect stacks.) |

## Wyvern Master (повышение из Wyvern Knight)

Тип: Spear Flying. Особенность: 2x dodge rate v. grounded melee / 2x phys. damage v. Cavalry. Раздел: Promoted Class.

Статы: hp B, phys_atk A, phys_def B, mag_atk F, mag_def E, accuracy B, evasion S, crit_rate C, guard_rate E, initiative B

| Навык | Вид | Цена | Ур. | Физ. | Маг. | Удары | Точн. | Описание |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Diving Thrust | active | 1 AP | 1 | 100 |  | 1 | 100 | Attack a single enemy.; Cavalry targets cannot guard against this attack.; +50 potency v. cavalry targets. [Ranged] |
| Fire Breath | active | 2 AP | 20 | 75 |  | 1 | 100 | Attack a row of enemies.; Inflicts Burn. [Ranged] |
| Tempest Drive | active | 2 AP | 30 | 150 |  | 1 | 100 | Attack a column of enemies with a piercing strike.; Cavalry targets cannot guard against this attack.; Becomes a truestrike and critical if user is below 50% HP. [Ranged] |
| Ground Counter | passive | 1 PP | 1 | 50 |  | 1 | 100 | Activates after an enemy attacks with an active skill.; Counterattack a single enemy.; +100 potency v. cavalry targets. |
| Deflect | passive | 1 PP | 15 |  |  |  |  | Activates before being hit by a melee attack.; Negate melee damage for a single hit.; Grants the user; +20 Evasion. (Effect stacks.) |
| Dragon's Roar | passive | 2 PP | 25 |  |  |  |  | Activates at the start of a battle.; Inflicts Initiative -20 on all enemies. |

