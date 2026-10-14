"""Снаряжение Unicorn Overlord -> data/items.json (по docs/uo/items.json; вызывается из tools/uo_import.py).

Слоты: меч light_sword, топор heavy_weapon, копьё lance, лук bow, посох staff, щит light_shield,
большой щит greatshield, аксессуар artifact. Атака, защита и шанс блока предмета -> модификаторы;
доп. статы («Initiative +2», «Max HP +10%», «All Stats +5») -> модификаторы; «Base AP/PP +1» ->
ap_bonus / pp_bonus; щит даёт тег shield (средний блок), большой щит — greatshield (тяжёлый);
иммунитеты -> теги immune_<метка>; «лечение N% HP при активном навыке» -> пассивка предмета без цены.
Навык предмета — навык или пассивка с тем же именем у классов или со страницы навыка вики.
Тир 0..30 — по силе предмета внутри вида; цена — цена UO / 40, без цены — по тиру.
"""
from __future__ import annotations

import re

SLOTS = {"sword": "light_sword", "axe": "heavy_weapon", "spear": "lance", "bow": "bow", "staff": "staff",
         "shield": "light_shield", "greatshield": "greatshield", "accessory": "artifact"}
STATS = [("Physickal Attack", "phys_atk"), ("Magick Attack", "mag_atk"), ("Physickal Defense", "phys_def"),
         ("Physickal Defence", "phys_def"), ("Magick Defense", "mag_def"), ("Magickal Defense", "mag_def"),
         ("Critical Damage", "crit_damage"), ("Critical Rate", "crit_rate"), ("Guard Rate", "guard_rate"),
         ("Initiative", "initiative"), ("Accuracy", "accuracy"), ("Evasion", "evasion"), ("Max HP", "hp")]
ALL_STATS = ["hp", "phys_atk", "phys_def", "mag_atk", "mag_def", "accuracy", "evasion", "crit_rate", "guard_rate",
             "initiative"]
IMMUNITIES = {"Poison": "poison", "Burn": "burn", "Brun": "burn", "Freeze": "freeze", "Stun": "stun",
              "Blindness": "blind", "Blind": "blind", "Passive Seal": "passive_seal", "Guard Seal": "guard_seal",
              "Affliction": "ailment", "Debuff": "debuff"}

# --- русские названия ----------------------------------------------------------------

NOUNS = {   # вид предмета -> (существительное, род: m, f, n, p)
    "Sword": ("меч", "m"), "Shortsword": ("короткий меч", "m"), "Blade": ("клинок", "m"), "Axe": ("топор", "m"),
    "ShortAxe": ("короткий топор", "m"), "Spear": ("копьё", "n"), "ShortSpear": ("короткое копьё", "n"),
    "Lance": ("пика", "f"), "Longspear": ("длинное копьё", "n"), "Shortspear": ("короткое копьё", "n"),
    "Bow": ("лук", "m"), "ShortBow": ("короткий лук", "m"), "LongBow": ("длинный лук", "m"),
    "Longbow": ("длинный лук", "m"), "Strongbow": ("тугой лук", "m"), "Greatbow": ("большой лук", "m"),
    "Staff": ("посох", "m"), "Rod": ("жезл", "m"), "Scepter": ("скипетр", "m"), "Mace": ("булава", "f"),
    "Shield": ("щит", "m"), "Greatshield": ("большой щит", "m"), "Towershield": ("башенный щит", "m"),
    "Buckler": ("баклер", "m"), "Bockler": ("баклер", "m"), "Pendant": ("кулон", "m"), "Bangle": ("браслет", "m"),
    "Circlet": ("диадема", "f"), "Beret": ("берет", "m"), "Hood": ("капюшон", "m"), "Talisman": ("талисман", "m"),
    "Plume": ("перо", "n"), "Shackles": ("кандалы", "p"), "Spectacles": ("очки", "p"), "Scarf": ("шарф", "m"),
    "Eyepatch": ("повязка", "f"), "Broach": ("брошь", "f"), "Ribbon": ("лента", "f"), "Medallion": ("медальон", "m"),
    "Ring": ("кольцо", "n"), "Bracelet": ("браслет", "m"), "Gauntlets": ("рукавицы", "p"), "Lantern": ("фонарь", "m"),
    "Earrings": ("серьги", "p"), "Standard": ("знамя", "n"), "Bell": ("колокольчик", "m"), "Tome": ("фолиант", "m"),
    "Reins": ("поводья", "p"), "Amulet": ("амулет", "m"), "Belt": ("пояс", "m"), "Robes": ("одеяние", "n"),
    "Cloak": ("плащ", "m"), "Cape": ("накидка", "f"), "Gloves": ("перчатки", "p"), "Coin": ("монета", "f"),
    "Mitre": ("митра", "f"), "Hammer": ("молот", "m"), "Halberd": ("алебарда", "f"), "Kit": ("набор", "m"),
    "Lens": ("линза", "f"), "Charm": ("оберег", "m"), "Crown": ("корона", "f"), "Egg": ("яйцо", "n"),
    "Goblet": ("кубок", "m"), "Necklace": ("ожерелье", "n"), "Shawl": ("шаль", "f"), "Signet": ("перстень", "m"),
    "Wand": ("палочка", "f"), "Cane": ("трость", "f"), "Rapier": ("рапира", "f"), "Claymore": ("клеймор", "m"),
    "Saber": ("сабля", "f"), "Longsword": ("длинный меч", "m"), "Handaxe": ("ручной топор", "m"),
    "Battleaxe": ("боевой топор", "m"), "Greataxe": ("секира", "f"), "Cleaver": ("тесак", "m"),
    "Warspear": ("боевое копьё", "n"), "Pike": ("пика", "f"), "Partisan": ("протазан", "m"),
    "Trident": ("трезубец", "m"), "Sarissa": ("сарисса", "f"), "Javelin": ("дротик", "m"),
    "Warbow": ("боевой лук", "m"), "Crossbow": ("арбалет", "m"), "Spiritbow": ("лук духов", "m"),
    "Bonestaff": ("костяной посох", "m"), "Roundshield": ("круглый щит", "m"), "Iceshield": ("ледяной щит", "m"),
    "Pavise": ("павеза", "f"), "Sash": ("кушак", "m"), "Choker": ("ошейник", "m"), "Anklet": ("браслет на ногу", "m"),
    "Mantle": ("мантия", "f"), "Shoes": ("туфли", "p"), "Boots": ("сапоги", "p"), "Caligae": ("калиги", "p"),
    "Sabatons": ("сабатоны", "p"), "Bandana": ("бандана", "f"), "Mittens": ("варежки", "p"), "Star": ("звезда", "f"),
    "Tasset": ("набедренник", "m"), "Epee": ("шпага", "f"), "Épée": ("шпага", "f"), "Edge": ("клинок", "m"),
    "Bough": ("ветвь", "f"), "Crosier": ("посох", "m"),
}
ADJ = {     # прилагательное: окончания для м, ж, с, мн (основа + окончание)
    "Bronze": ("Бронзов", "ый"), "Iron": ("Железн", "ый"), "Steel": ("Стальн", "ой"),
    "Black-Iron": ("Чёрножелезн", "ый"), "Silver": ("Серебрян", "ый"), "Gold": ("Золот", "ой"),
    "Golden": ("Золот", "ой"), "Baroque": ("Барочн", "ый"), "Thorn": ("Терновн", "ый"), "Icefall": ("Ледопадн", "ый"),
    "Meteorite": ("Метеоритн", "ый"), "Sacral": ("Сакральн", "ый"), "Hoarfrost": ("Инейн", "ый"),
    "Searing": ("Палящ", "ий"), "Viper": ("Гадюч", "ий"), "Luminous": ("Сияющ", "ий"), "Moonlight": ("Лунн", "ый"),
    "Unyielding": ("Непреклонн", "ый"), "Ironclad": ("Окованн", "ый"), "Holy": ("Свят", "ой"), "Royal": ("Королевск", "ий"),
    "Runic": ("Рунн", "ый"), "Crimson": ("Багров", "ый"), "Greatwood": ("Великодревн", "ый"), "Carnat": ("Карнатск", "ий"),
    "Spellsteel": ("Чарастальн", "ой"), "Vorpal": ("Ворпальн", "ый"), "Sanguine": ("Кровав", "ый"),
    "Dragonbone": ("Драконокостн", "ый"), "Wingcrest": ("Крылогербов", "ый"), "Carnelian": ("Сердоликов", "ый"),
    "Zenoiran": ("Зенойрск", "ий"), "Phantom": ("Призрачн", "ый"), "Bloody": ("Кровав", "ый"), "Corroded": ("Ржав", "ый"),
    "Flame": ("Огненн", "ый"), "Thundering": ("Громов", "ой"), "Piercing": ("Пронзающ", "ий"), "Infamous": ("Бесславн", "ый"),
    "Starless": ("Беззвёздн", "ый"), "Desert": ("Пустынн", "ый"), "Silvermoon": ("Серебролунн", "ый"),
    "Pestilent": ("Чумн", "ой"), "Telluric": ("Земн", "ой"), "Icestorm": ("Буранн", "ый"), "Quartz": ("Кварцев", "ый"),
    "Lyrical": ("Лиричн", "ый"), "Hallowed": ("Освящённ", "ый"), "Ringed": ("Кольчат", "ый"),
    "Phosphorescent": ("Фосфоресцирующ", "ий"), "Precious": ("Драгоценн", "ый"), "Gleaming": ("Блестящ", "ий"),
    "Chiropteran": ("Нетопыриный", ""), "Red-Bark": ("Краснокор", "ый"), "Obsidian": ("Обсидианов", "ый"),
    "Blessed": ("Благословенн", "ый"), "Unfettered": ("Вольн", "ый"), "Chivalric": ("Рыцарск", "ий"),
    "Mirage": ("Миражн", "ый"), "Panoplied": ("Латн", "ый"), "Bulwark": ("Бастионн", "ый"), "Blacksilver": ("Чернособрян", "ый"),
    "Brown": ("Коричнев", "ый"), "Green": ("Зелён", "ый"), "Elite": ("Элитн", "ый"), "Leather": ("Кожан", "ый"),
    "Silk": ("Шёлков", "ый"), "Silken": ("Шёлков", "ый"), "Vitality": ("Живительн", "ый"), "Lifeblood": ("Животворн", "ый"),
    "Blue": ("Син", "ий"), "Mirrored": ("Зеркальн", "ый"), "Lucky": ("Счастлив", "ый"), "Cloth": ("Тканев", "ый"),
    "Leaf": ("Листов", "ой"), "Rose": ("Розов", "ый"), "White": ("Бел", "ый"), "Verdant": ("Изумрудн", "ый"),
    "Bloodstained": ("Окровавленн", "ый"), "Undead": ("Немёртв", "ый"), "Defensive": ("Защитн", "ый"),
    "Aurora": ("Зарев", "ой"), "Truestrike": ("Верн", "ый"), "Armored": ("Бронированн", "ый"), "Dawn": ("Рассветн", "ый"),
    "Dusk": ("Закатн", "ый"), "Power": ("Силов", "ой"), "Twilight": ("Сумеречн", "ый"), "Illusory": ("Иллюзорн", "ый"),
    "Soothing": ("Успокаивающ", "ий"), "Detoxifying": ("Противоядн", "ый"), "Quenching": ("Гасящ", "ий"),
    "Defrosting": ("Оттаивающ", "ий"), "Awakening": ("Пробуждающ", "ий"), "Clearsight": ("Ясновидящ", "ий"),
    "Parrying": ("Парирующ", "ий"), "Skillful": ("Искусн", "ый"), "Glacial": ("Ледников", "ый"), "Barbed": ("Колюч", "ий"),
    "Wooly": ("Шерстян", "ой"), "Fluffy": ("Пушист", "ый"), "Celestial": ("Небесн", "ый"), "Dirty": ("Грязн", "ый"),
    "Crude": ("Грубый", ""), "Large": ("Больш", "ой"), "Medical": ("Медицинск", "ий"), "Ancient": ("Древн", "ий"),
    "Dream": ("Сонн", "ый"), "Black": ("Чёрн", "ый"), "Conveyable": ("Переносн", "ой"), "Scarlet": ("Алый", ""),
    "Wind": ("Ветрян", "ой"), "Grand": ("Велик", "ий"), "Storm": ("Штормов", "ой"), "Frozen": ("Замёрзш", "ий"),
    "Crushing": ("Сокрушающ", "ий"), "Spiked": ("Шипаст", "ый"), "Banishing": ("Изгоняющ", "ий"),
    "Surging": ("Стремительн", "ый"), "Twinned": ("Сдвоенн", "ый"), "Canyon": ("Каньонн", "ый"), "Helix": ("Спиральн", "ый"),
    "Unwavering": ("Несгибаем", "ый"), "Thawing": ("Тающ", "ий"), "Lamplight": ("Светильн", "ый"),
    "Battleline": ("Боев", "ой"), "Wingline": ("Крылат", "ый"), "Wolfpack": ("Волчий", ""), "Badger": ("Барсучий", ""),
    "Twin": ("Двойн", "ой"), "Heavenswing": ("Небесн", "ый"), "Azure": ("Лазурн", "ый"),
}
ENDINGS = {  # окончание основы -> окончания по родам
    "ый": {"m": "ый", "f": "ая", "n": "ое", "p": "ые"}, "ой": {"m": "ой", "f": "ая", "n": "ое", "p": "ые"},
    "ий": {"m": "ий", "f": "ая", "n": "ее", "p": "ие"},
}
SOFT = {"Син", "Древн", "Зарев"}               # мягкая основа: синяя, синее, древняя
OWNERS = {   # «Knight's» -> родительный падеж после существительного
    "Recruit's": "новобранца", "Templar's": "храмовника", "Knight's": "рыцаря", "Hunter's": "охотника",
    "Watchman's": "стражника", "Nameless Guard's": "безымянного стража", "Phantom Knight's": "призрачного рыцаря",
    "Zenoiran Knight's": "зенойрского рыцаря", "Zenoiran Knight": "зенойрского рыцаря", "Guard's": "стража",
    "Squire's": "оруженосца", "White Knight's": "белого рыцаря", "Holy Knight's": "святого рыцаря",
    "Citadel Guard's": "стража цитадели", "Hero's": "героя", "Champion's": "чемпиона", "Battler's": "бойца",
    "Mercenay's": "наёмника", "Mercenary's": "наёмника", "Veteran's": "ветерана", "Prisoner's": "узника",
    "Daemon's": "демона", "Sage's": "мудреца", "Warrior's": "воина", "Sorcerer's": "чародея", "Cleric's": "клирика",
    "Thief's": "вора", "Gambler's": "игрока", "Dirty Gambler's": "шулера", "Sniper's": "снайпера",
    "Defender's": "защитника", "Liberator's": "освободителя", "Pursuant's": "преследователя", "Outlaw's": "изгоя",
    "Mage's": "мага", "Monk's": "монаха", "Archbishop's": "архиепископа", "Spirit's": "духа", "Dancer's": "танцора",
    "Acrobat's": "акробата", "Necromancer's": "некроманта", "Old Witch's": "старой ведьмы", "Master's": "мастера",
    "Druid's": "друида", "Phoenix's": "феникса", "Familiar's": "фамильяра", "Barbarian's": "варвара",
    "Mason's": "каменщика", "Headsman's": "палача", "Giant's": "великана", "General's": "генерала",
    "Dragoon's": "драгуна", "Adept's": "адепта", "Valkyrie's": "валькирии", "Interrogator's": "дознавателя",
    "Trapper's": "ловчего", "Cardinal's": "кардинала", "Shaman's": "шамана", "Cutthroat's": "головореза",
    "Scorpion's": "скорпиона", "Sylph's": "сильфиды", "Wind Faerie's": "феи ветра", "Sage Owl's": "мудрой совы",
    "Wolf Fang": "волчьего клыка", "Cavalry Hunter's": "охотника на конницу", "Angel Hunter's": "охотника на ангелов",
    "Beast Hunter's": "охотника на зверей", "White Rider's": "белого всадника", "Courser's": "скакуна",
    "Heavensteed": "небесного скакуна", "Heavenwyvern": "небесной виверны", "Wyvern": "виверны",
    "Gravekeeper": "могильщика", "Rose Knight": "рыцаря розы", "Dark Knight": "тёмного рыцаря",
    "Golden Ram": "золотого овна", "Azure Crest": "лазурного герба", "Scarlet Crest": "алого герба",
    "Blue Rose": "синей розы", "Twin Dragon": "двух драконов", "Holy Unicorn": "святого единорога",
    "Mother Laelia's": "матушки Лелии", "Kaikai's": "Кайкай", "Lips's": "Липс", "Scarlett's": "Скарлетт",
    "Chloe's": "Хлои", "Ervélda's": "Эрвельды", "Notos's": "Нота", "Boreas's": "Борея", "Zephyros's": "Зефира",
    "Apeliotes's": "Апелиота", "Euros's": "Эвра", "Skiron's": "Скирона", "Grand Magus": "великого мага",
    "Bow of": "", "Staff of": "",
}
WHOLE = {   # уникальные названия целиком
    "Barbarian's Might": "Мощь варвара", "Viperfang": "Клык гадюки", "Flamberge": "Фламберг",
    "Dancer's Delight": "Отрада танцора", "Sylph's Bane": "Погибель сильфиды", "Galecutter": "Рассекатель бурь",
    "Hailstorm Edge": "Клинок града", "Cutthroat's Boon": "Дар головореза", "Wyvern Razor": "Бритва виверны",
    "Stingray": "Скат", "Bandit Longsword": "Длинный меч разбойника", "Greatsword": "Двуручный меч",
    "Rosularis Sword": "Меч Розулярис", "Kingsblade Cornix": "Королевский клинок Корникс",
    "Scorpion's Sting": "Жало скорпиона", "Knot of Ruin": "Узел погибели", "Eliminator": "Истребитель",
    "Morningstar": "Моргенштерн", "Labrys": "Лабрис", "Warhammer": "Боевой молот", "Juggernaut": "Джаггернаут",
    "Helleborus Axe": "Топор Геллеборус", "Kingsaxe Drakenash": "Королевский топор Дракенаш", "Glaive": "Глефа",
    "Storm of Hail": "Градовая буря", "Elfeater": "Пожиратель эльфов", "Testarossa": "Тестаросса",
    "Orchis Spear": "Копьё Орхис", "Kingspear Elhal": "Королевское копьё Эльхал", "The Inquisitor": "Инквизитор",
    "Bow of Swiftness": "Лук быстроты", "Crane Bow": "Журавлиный лук", "Gallian Crossbow": "Галлийский арбалет",
    "Frostbloom Bow": "Лук морозоцвета", "Woodpecker": "Дятел", "Alminster": "Альминстер", "Quince Bow": "Айвовый лук",
    "Kingsbow Bastorik": "Королевский лук Басторик", "Pheasant Bow": "Фазаний лук", "Spellseal Bow": "Лук печатей",
    "Salamander Greatbow": "Большой лук саламандры", "Greatwood Spiritbow": "Великодревний лук духов",
    "Staff of Succor": "Посох помощи", "Purifier": "Очиститель", "Speed-Hex Staff": "Посох сглаза скорости",
    "Poison-Hex Staff": "Посох сглаза яда", "Flame-Hex Staff": "Посох сглаза огня", "Dustbound Staff": "Пыльный посох",
    "Chlorotic": "Хлоротик", "Ein Seeker": "Айн-искатель", "Millenium Scepter": "Тысячелетний скипетр", "Libera": "Либера",
    "Lupinus Staff": "Посох Люпинус", "Kingstaff Albiore": "Королевский посох Альбиоре", "Papal Crosier": "Папский посох",
    "Bloodmoon Rod": "Жезл кровавой луны", "Arrowshield": "Стрелощит", "Manalith Buckler": "Баклер манолита",
    "Horsekiller Greatshield": "Большой щит конеборца", "Wingclipper Greatshield": "Большой щит крылоруба",
    "Beastslayer Greatshield": "Большой щит зверобоя", "Heaven's Mirror Greatshield": "Большой щит небесного зеркала",
    "Drakestone Iceshield": "Ледяной щит драконьего камня", "Greatshield Of The Abyss": "Большой щит бездны",
    "Gran Baris": "Гран Барис", "Ruby Pendant": "Рубиновый кулон", "Lapis Pendant": "Лазуритовый кулон",
    "Sapphire Pendant": "Сапфировый кулон", "Amethyst Pendant": "Аметистовый кулон", "Onyx Pendant": "Ониксовый кулон",
    "Dove Plume": "Голубиное перо", "Raven Plume": "Вороново перо", "Angel Plume": "Ангельское перо",
    "Gauntlets": "Рукавицы", "Charm Of Land & Sea": "Оберег суши и моря", "Charm Of Sun & Moon": "Оберег солнца и луны",
    "Lionheart": "Львиное сердце", "Mistletoe Charm": "Оберег омелы", "Retaliation Earrings": "Серьги возмездия",
    "Earrings Of Pursuit": "Серьги преследования", "Tailwind Cape": "Накидка попутного ветра", "Gust Bracelet": "Браслет порыва",
    "Squall Bracelet": "Браслет шквала", "Elite Standard": "Элитное знамя", "First Aid Kit": "Аптечка",
    "Self-Aid Kit": "Набор самопомощи", "Shawl Of Repose": "Шаль покоя", "Charm Of Warding": "Оберег защиты",
    "Lapis Bell": "Лазуритовый колокольчик", "Flamebrand Tome": "Фолиант огненного клейма",
    "Frostbrand Tome": "Фолиант ледяного клейма", "Thunderbrand Tome": "Фолиант громового клейма",
    "Bloodbrand Tome": "Фолиант кровавого клейма", "Glory Sash": "Кушак славы", "Counter Belt": "Пояс ответа",
    "Wyvern Claw": "Коготь виверны", "Power Belt": "Пояс силы", "Salamander Ring": "Кольцо саламандры",
    "Thunderclap Ring": "Кольцо громового раската", "Cooling Bandana": "Охлаждающая бандана", "Rookie Egg": "Яйцо новичка",
    "Golden Egg": "Золотое яйцо", "Miser's Bracelet": "Браслет скряги", "Silver Goblet": "Серебряный кубок",
    "Gold Goblet": "Золотой кубок", "Gauntlets Of The Abyss": "Рукавицы бездны", "Crown Of The Abyss": "Корона бездны",
    "Talisman Of The Abyss": "Талисман бездны", "Magia Soul": "Душа магии", "Magia Heart": "Сердце магии",
    "White Cat-Ear Hood": "Белый капюшон с ушками", "Black Cat-Ear Hood": "Чёрный капюшон с ушками",
    "Ring Of The Unicorn": "Кольцо единорога", "Holy Unicorn Signet": "Перстень святого единорога",
    "Vengeful Caligae": "Калиги мести", "Guardian Gloves": "Перчатки стража", "Bloodmoon Earrings": "Серьги кровавой луны",
    "Wolfpack Gauntlets": "Рукавицы волчьей стаи", "Badger Gauntlets": "Барсучьи рукавицы", "Undead Ring": "Кольцо нежити",
    "Lucky Coin": "Счастливая монета", "Sniper's Amber Lens": "Янтарная линза снайпера", "Truestrike Star": "Звезда верного удара",
    "Dragon Shield": "Драконий щит", "Unyielding Shield": "Непреклонный щит",
    "Bandit's Handaxe": "Ручной топор разбойника", "Warding Staff": "Охранный посох", "Watchman's Horn": "Рог стражника",
    "Large Aid Kit": "Большая аптечка"
}


def adjective(word: str, gender: str) -> str:
    stem, ending = ADJ[word]
    if not ending:
        return stem
    if stem in SOFT:
        return stem + {"m": "ий", "f": "яя", "n": "ее", "p": "ие"}[gender]
    return stem + ENDINGS[ending][gender]


def russian(name: str) -> str:
    """Русское название предмета: целиком из WHOLE, иначе [прилагательное] существительное [чьё]."""
    if name in WHOLE:
        return WHOLE[name]
    words = name.split()
    noun = words[-1]
    if noun not in NOUNS and len(words) > 1 and f"{words[-2]} {words[-1]}" in WHOLE:
        return WHOLE[f"{words[-2]} {words[-1]}"]
    if noun not in NOUNS:
        return name
    text, gender = NOUNS[noun]
    rest = " ".join(words[:-1])
    owner = ""
    for key in sorted(OWNERS, key=len, reverse=True):
        if rest.endswith(key):
            owner, rest = OWNERS[key], rest[:-len(key)].strip()
            break
    adjectives = []
    for word in rest.split():
        if word not in ADJ:
            return name
        adjectives.append(adjective(word, gender))
    head = " ".join(adjectives + [text])
    head = head[0].upper() + head[1:]
    return f"{head} {owner}".strip()


# --- статы и навыки ------------------------------------------------------------------

def modifiers(entry: dict) -> list[dict]:
    mods = []
    for key in ("phys_atk", "mag_atk", "phys_def", "mag_def", "guard_rate"):
        if entry.get(key):
            mods.append({"stat": key, "op": "FLAT", "value": entry[key]})
    return mods


def substats(entry: dict, notes: list[str]) -> tuple[list[dict], dict, list[str], list[str]]:
    """Доп. статы -> (модификаторы, {ap_bonus, pp_bonus}, теги, пассивки «лечение при навыке»)."""
    mods, bonus, tags, heals = [], {}, [], []
    for line in entry["stats"]:
        line = re.sub(r"\[\[[^\]]*\]\]", "", line).strip()      # картинки AP/PP из таблицы Cargo
        text = line.replace("PP", " PP").replace("AP", " AP")
        number = re.search(r"([+-]?\d+)\s*(%?)", text)
        value, percent = (int(number.group(1)), bool(number.group(2))) if number else (0, False)
        if "Guard Efficiency" in line:
            continue
        if "Base" in line and " AP" in text and "PP" not in line.replace("AP_Gem", ""):
            bonus["ap_bonus"] = bonus.get("ap_bonus", 0) + value
            continue
        if "Base" in line and " PP" in text:
            bonus["pp_bonus"] = bonus.get("pp_bonus", 0) + value
            continue
        if line.startswith("All Stats"):
            mods += [{"stat": s, "op": "FLAT", "value": value} for s in ALL_STATS]
            continue
        immunity = next((label for word, label in IMMUNITIES.items() if line.startswith(word) and "Immunity" in line), None)
        if immunity:
            tags.append(f"immune_{immunity}")
            continue
        heal = re.search(r"Heal (\d+)% HP when using Active [Ss]kill", line)
        if heal:
            heals.append(heal.group(1))
            continue
        stat = next((s for word, s in STATS if line.startswith(word)), None)
        if stat is None:
            notes.append(f"«{line}» не переносится")
            continue
        if percent and stat not in ("crit_rate", "guard_rate", "evasion", "accuracy"):
            mods.append({"stat": stat, "op": "PERCENT_ADD", "value": round(value / 100, 3)})
        else:
            mods.append({"stat": stat, "op": "FLAT", "value": value})
    return mods, bonus, tags, heals


def strength(entry: dict, mods: list[dict], bonus: dict) -> float:
    """Сила предмета для тира: атака, защита, блок, доп. статы, AP/PP."""
    value = entry["phys_atk"] + entry["mag_atk"] + entry["phys_def"] * 1.5 + entry["mag_def"] * 1.5 + entry["guard_rate"] / 3
    for mod in mods[len(modifiers(entry)):]:            # доп. статы (основные уже посчитаны выше)
        main = mod["stat"] in ("phys_atk", "mag_atk", "phys_def", "mag_def")
        value += abs(mod["value"]) * (40 if mod["op"] == "PERCENT_ADD" else (1.5 if main else 0.5))
    value += bonus.get("ap_bonus", 0) * 12 + bonus.get("pp_bonus", 0) * 8
    return value + len(entry["skills"]) * 4


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower().replace("'", "").replace("é", "e")).strip("_")


def build(reference: dict, importer, known_skills: dict, known_passives: dict) -> tuple[dict, dict, dict, dict]:
    """(предметы, пассивки предметов, навыки предметов, переводы). importer — tools.uo_import.Importer."""
    items, passives, skills, ru, rows = {}, {}, {}, {}, []
    for entry in reference["items"]:
        key = slug(entry["name"])
        if key in items or entry["kind"] not in SLOTS:
            continue
        notes: list[str] = []
        mods, bonus, tags, heals = substats(entry, notes)
        mods = modifiers(entry) + mods
        tags = (["shield"] if entry["kind"] == "shield" else ["greatshield"] if entry["kind"] == "greatshield" else []) + tags
        item_skills, item_passives = [], []
        for name in entry["skills"]:
            skill_key = slug(name)
            if skill_key in known_skills:
                item_skills.append(skill_key)
            elif skill_key in known_passives:
                item_passives.append(skill_key)
            elif name in reference.get("skills", {}):
                data = dict(reference["skills"][name], name=name)
                if data["category"] == "active":
                    skills[skill_key] = importer.active(skill_key, data)
                    item_skills.append(skill_key)
                else:
                    passives[skill_key] = {"name": name, "pp_cost": data["pp"] or 1,
                                           "reaction": importer.passive(skill_key, data)}
                    item_passives.append(skill_key)
                ru[name] = importer.ru.get(name, name)
            else:
                notes.append(f"навык «{name}» без описания в вики — не перенесён")
        for percent in heals:
            passive_id = f"uo_item_heal_{percent}"
            passives[passive_id] = {"name": f"UO heal {percent}", "pp_cost": 0, "reaction": {
                "event": "skill_used", "whose": "self", "action": "heal", "amount": int(percent), "percent": True,
                "to": "owner"}}
            ru[f"UO heal {percent}"] = f"Лечение {percent}% HP при навыке"
            item_passives.append(passive_id)
        rows.append((entry["kind"], strength(entry, mods, bonus), key))
        items[key] = {"name": entry["name"], "slot": SLOTS[entry["kind"]], "modifiers": mods, "skills": item_skills,
                      "passives": item_passives, "tags": tags, "damage_tags": [], "price": round(entry["price"] / 40),
                      **bonus}
        ru[entry["name"]] = russian(entry["name"])
        if notes:
            importer.notes.setdefault(f"предмет {key}", []).extend(notes)
    for kind in SLOTS:                                # тир — место по силе внутри вида
        ranked = sorted((power, key) for k, power, key in rows if k == kind)
        for index, (_power, key) in enumerate(ranked):
            tier = round(30 * index / max(1, len(ranked) - 1))
            items[key]["tier"] = tier
            if not items[key]["price"]:
                items[key]["price"] = 20 + tier * 12
    return items, passives, skills, ru
