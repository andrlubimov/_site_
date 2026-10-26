"""Телефон с кодом страны: список стран для формы, проверка и формат номера (библиотека phonenumbers).

Номер хранится в международном формате E.164 (+79161234567), показывается — как +7 916 123-45-67.
"""
import phonenumbers
from phonenumbers import PhoneNumberFormat, PhoneNumberType

DEFAULT_REGION = 'RU'

# страны, откуда чаще всего приходят слушатели и представители Ассоциации, — в начале списка
POPULAR_REGIONS = ['RU', 'BY', 'KZ', 'UZ', 'KG', 'TJ', 'AM', 'AZ', 'GE', 'MD', 'UA', 'TR']

# Названия всех стран и территорий, которые знает phonenumbers (код ISO → название)
COUNTRY_NAMES = {
    'AC': 'Остров Вознесения', 'AD': 'Андорра', 'AE': 'ОАЭ', 'AF': 'Афганистан', 'AG': 'Антигуа и Барбуда',
    'AI': 'Ангилья', 'AL': 'Албания', 'AM': 'Армения', 'AO': 'Ангола', 'AR': 'Аргентина',
    'AS': 'Американское Самоа', 'AT': 'Австрия', 'AU': 'Австралия', 'AW': 'Аруба', 'AX': 'Аландские острова',
    'AZ': 'Азербайджан',
    'BA': 'Босния и Герцеговина', 'BB': 'Барбадос', 'BD': 'Бангладеш', 'BE': 'Бельгия', 'BF': 'Буркина-Фасо',
    'BG': 'Болгария', 'BH': 'Бахрейн', 'BI': 'Бурунди', 'BJ': 'Бенин', 'BL': 'Сен-Бартелеми', 'BM': 'Бермуды',
    'BN': 'Бруней', 'BO': 'Боливия', 'BQ': 'Бонэйр, Синт-Эстатиус и Саба', 'BR': 'Бразилия', 'BS': 'Багамы',
    'BT': 'Бутан', 'BW': 'Ботсвана', 'BY': 'Беларусь', 'BZ': 'Белиз',
    'CA': 'Канада', 'CC': 'Кокосовые острова', 'CD': 'ДР Конго', 'CF': 'ЦАР', 'CG': 'Республика Конго',
    'CH': 'Швейцария', 'CI': 'Кот-д’Ивуар', 'CK': 'Острова Кука', 'CL': 'Чили', 'CM': 'Камерун', 'CN': 'Китай',
    'CO': 'Колумбия', 'CR': 'Коста-Рика', 'CU': 'Куба', 'CV': 'Кабо-Верде', 'CW': 'Кюрасао',
    'CX': 'Остров Рождества', 'CY': 'Кипр', 'CZ': 'Чехия',
    'DE': 'Германия', 'DJ': 'Джибути', 'DK': 'Дания', 'DM': 'Доминика', 'DO': 'Доминиканская Республика',
    'DZ': 'Алжир',
    'EC': 'Эквадор', 'EE': 'Эстония', 'EG': 'Египет', 'EH': 'Западная Сахара', 'ER': 'Эритрея', 'ES': 'Испания',
    'ET': 'Эфиопия',
    'FI': 'Финляндия', 'FJ': 'Фиджи', 'FK': 'Фолклендские острова', 'FM': 'Микронезия',
    'FO': 'Фарерские острова', 'FR': 'Франция',
    'GA': 'Габон', 'GB': 'Великобритания', 'GD': 'Гренада', 'GE': 'Грузия', 'GF': 'Французская Гвиана',
    'GG': 'Гернси', 'GH': 'Гана', 'GI': 'Гибралтар', 'GL': 'Гренландия', 'GM': 'Гамбия', 'GN': 'Гвинея',
    'GP': 'Гваделупа', 'GQ': 'Экваториальная Гвинея', 'GR': 'Греция', 'GT': 'Гватемала', 'GU': 'Гуам',
    'GW': 'Гвинея-Бисау', 'GY': 'Гайана',
    'HK': 'Гонконг', 'HN': 'Гондурас', 'HR': 'Хорватия', 'HT': 'Гаити', 'HU': 'Венгрия',
    'ID': 'Индонезия', 'IE': 'Ирландия', 'IL': 'Израиль', 'IM': 'Остров Мэн', 'IN': 'Индия',
    'IO': 'Британская территория в Индийском океане', 'IQ': 'Ирак', 'IR': 'Иран', 'IS': 'Исландия',
    'IT': 'Италия',
    'JE': 'Джерси', 'JM': 'Ямайка', 'JO': 'Иордания', 'JP': 'Япония',
    'KE': 'Кения', 'KG': 'Кыргызстан', 'KH': 'Камбоджа', 'KI': 'Кирибати', 'KM': 'Коморы',
    'KN': 'Сент-Китс и Невис', 'KP': 'КНДР', 'KR': 'Южная Корея', 'KW': 'Кувейт', 'KY': 'Каймановы острова',
    'KZ': 'Казахстан',
    'LA': 'Лаос', 'LB': 'Ливан', 'LC': 'Сент-Люсия', 'LI': 'Лихтенштейн', 'LK': 'Шри-Ланка', 'LR': 'Либерия',
    'LS': 'Лесото', 'LT': 'Литва', 'LU': 'Люксембург', 'LV': 'Латвия', 'LY': 'Ливия',
    'MA': 'Марокко', 'MC': 'Монако', 'MD': 'Молдова', 'ME': 'Черногория', 'MF': 'Сен-Мартен',
    'MG': 'Мадагаскар', 'MH': 'Маршалловы Острова', 'MK': 'Северная Македония', 'ML': 'Мали', 'MM': 'Мьянма',
    'MN': 'Монголия', 'MO': 'Макао', 'MP': 'Северные Марианские острова', 'MQ': 'Мартиника',
    'MR': 'Мавритания', 'MS': 'Монтсеррат', 'MT': 'Мальта', 'MU': 'Маврикий', 'MV': 'Мальдивы',
    'MW': 'Малави', 'MX': 'Мексика', 'MY': 'Малайзия', 'MZ': 'Мозамбик',
    'NA': 'Намибия', 'NC': 'Новая Каледония', 'NE': 'Нигер', 'NF': 'Остров Норфолк', 'NG': 'Нигерия',
    'NI': 'Никарагуа', 'NL': 'Нидерланды', 'NO': 'Норвегия', 'NP': 'Непал', 'NR': 'Науру', 'NU': 'Ниуэ',
    'NZ': 'Новая Зеландия',
    'OM': 'Оман',
    'PA': 'Панама', 'PE': 'Перу', 'PF': 'Французская Полинезия', 'PG': 'Папуа — Новая Гвинея',
    'PH': 'Филиппины', 'PK': 'Пакистан', 'PL': 'Польша', 'PM': 'Сен-Пьер и Микелон', 'PR': 'Пуэрто-Рико',
    'PS': 'Палестина', 'PT': 'Португалия', 'PW': 'Палау', 'PY': 'Парагвай',
    'QA': 'Катар',
    'RE': 'Реюньон', 'RO': 'Румыния', 'RS': 'Сербия', 'RU': 'Россия', 'RW': 'Руанда',
    'SA': 'Саудовская Аравия', 'SB': 'Соломоновы Острова', 'SC': 'Сейшельские Острова', 'SD': 'Судан',
    'SE': 'Швеция', 'SG': 'Сингапур', 'SH': 'Остров Святой Елены', 'SI': 'Словения',
    'SJ': 'Шпицберген и Ян-Майен', 'SK': 'Словакия', 'SL': 'Сьерра-Леоне', 'SM': 'Сан-Марино',
    'SN': 'Сенегал', 'SO': 'Сомали', 'SR': 'Суринам', 'SS': 'Южный Судан', 'ST': 'Сан-Томе и Принсипи',
    'SV': 'Сальвадор', 'SX': 'Синт-Мартен', 'SY': 'Сирия', 'SZ': 'Эсватини',
    'TA': 'Тристан-да-Кунья', 'TC': 'Теркс и Кайкос', 'TD': 'Чад', 'TG': 'Того', 'TH': 'Таиланд',
    'TJ': 'Таджикистан', 'TK': 'Токелау', 'TL': 'Восточный Тимор', 'TM': 'Туркменистан', 'TN': 'Тунис',
    'TO': 'Тонга', 'TR': 'Турция', 'TT': 'Тринидад и Тобаго', 'TV': 'Тувалу', 'TW': 'Тайвань',
    'TZ': 'Танзания',
    'UA': 'Украина', 'UG': 'Уганда', 'US': 'США', 'UY': 'Уругвай', 'UZ': 'Узбекистан',
    'VA': 'Ватикан', 'VC': 'Сент-Винсент и Гренадины', 'VE': 'Венесуэла', 'VG': 'Британские Виргинские острова',
    'VI': 'Виргинские острова (США)', 'VN': 'Вьетнам', 'VU': 'Вануату',
    'WF': 'Уоллис и Футуна', 'WS': 'Самоа',
    'YE': 'Йемен', 'YT': 'Майотта',
    'ZA': 'ЮАР', 'ZM': 'Замбия', 'ZW': 'Зимбабве',
}


CODES_BY_NAME = {name: code for code, name in COUNTRY_NAMES.items()}


def _sorted_by_name(regions):
    return sorted(regions, key=lambda region: COUNTRY_NAMES[region].casefold().replace('ё', 'е'))


def calling_code(region):
    return phonenumbers.country_code_for_region(region)


def country_label(region):
    """«Россия +7» — так страна выглядит в списке"""
    return f'{COUNTRY_NAMES[region]} +{calling_code(region)}'


def country_choices():
    """Варианты для кода страны у телефона: сначала частые, потом остальные по алфавиту"""
    others = _sorted_by_name(region for region in COUNTRY_NAMES if region not in POPULAR_REGIONS)
    return [('Часто выбирают', [(region, country_label(region)) for region in POPULAR_REGIONS]),
            ('Все страны', [(region, country_label(region)) for region in others])]


def country_name_choices():
    """Варианты для поля «Страна» (хранится название): тот же список, без кодов"""
    others = _sorted_by_name(region for region in COUNTRY_NAMES if region not in POPULAR_REGIONS)
    return [('', 'Не указана'),
            ('Часто выбирают', [(COUNTRY_NAMES[region],) * 2 for region in POPULAR_REGIONS]),
            ('Все страны', [(COUNTRY_NAMES[region],) * 2 for region in others])]


def example_number(region):
    """Пример номера страны (мобильного) в международном формате: +7 912 345-67-89"""
    example = (phonenumbers.example_number_for_type(region, PhoneNumberType.MOBILE)
               or phonenumbers.example_number(region))
    return phonenumbers.format_number(example, PhoneNumberFormat.INTERNATIONAL) if example else ''


def example_local(region):
    """Тот же пример без кода страны — подсказка в поле номера: 912 345-67-89"""
    return example_number(region).removeprefix(f'+{calling_code(region)}').strip()


def parse_phone(number, region=DEFAULT_REGION):
    """Номер из формы → объект phonenumbers или None, если такого номера быть не может.
    Номер, начатый с «+», разбирается по своему коду страны: выбранная страна тогда не важна.
    Российский номер можно ввести и с восьмёркой: 8 916 123-45-67."""
    try:
        parsed = phonenumbers.parse(number, region)
    except phonenumbers.NumberParseException:
        return None
    return parsed if phonenumbers.is_valid_number(parsed) else None


def to_e164(parsed):
    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)


def format_phone(value):
    """+79161234567 → +7 916 123-45-67; что не разобралось — как есть"""
    parsed = parse_phone(value) if value else None
    return phonenumbers.format_number(parsed, PhoneNumberFormat.INTERNATIONAL) if parsed else value


def split_phone(value):
    """Номер из базы → (страна, номер без кода) — для поля формы"""
    parsed = parse_phone(value) if value else None
    if parsed is None:
        return DEFAULT_REGION, value or ''
    region = phonenumbers.region_code_for_number(parsed)
    if region not in COUNTRY_NAMES:
        return DEFAULT_REGION, phonenumbers.format_number(parsed, PhoneNumberFormat.INTERNATIONAL)
    international = phonenumbers.format_number(parsed, PhoneNumberFormat.INTERNATIONAL)
    return region, international.removeprefix(f'+{parsed.country_code}').strip()
