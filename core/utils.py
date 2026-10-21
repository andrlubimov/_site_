"""Форматирование дат, цен и склонений для курсов и расписания; транслитерация адресов страниц."""
import re

from django.utils.text import slugify

MONTHS_GENITIVE = [
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
]


def format_date_range(start, end):
    """12–14 ноября 2026 / 30 ноября – 2 декабря 2026 / 5 мая 2026"""
    if start == end:
        return f"{start.day} {MONTHS_GENITIVE[start.month - 1]} {start.year}"
    if start.year != end.year:
        return (f"{start.day} {MONTHS_GENITIVE[start.month - 1]} {start.year} – "
                f"{end.day} {MONTHS_GENITIVE[end.month - 1]} {end.year}")
    if start.month != end.month:
        return (f"{start.day} {MONTHS_GENITIVE[start.month - 1]} – "
                f"{end.day} {MONTHS_GENITIVE[end.month - 1]} {end.year}")
    return f"{start.day}–{end.day} {MONTHS_GENITIVE[start.month - 1]} {start.year}"


def format_day_list(dates):
    """Отдельные дни: «3, 4 и 10 декабря 2026», «30 ноября и 2 декабря 2026»."""
    dates = sorted(set(dates))
    if not dates:
        return ''
    groups = []  # [(год, месяц, [дни])] подряд по месяцам
    for d in dates:
        if groups and groups[-1][0] == d.year and groups[-1][1] == d.month:
            groups[-1][2].append(d.day)
        else:
            groups.append((d.year, d.month, [d.day]))
    parts = []
    for i, (year, month, days) in enumerate(groups):
        last_in_year = i == len(groups) - 1 or groups[i + 1][0] != year
        text = join_ru([str(day) for day in days]) + ' ' + MONTHS_GENITIVE[month - 1]
        parts.append(text + (f' {year}' if last_in_year else ''))
    return join_ru(parts)


def join_ru(items):
    """['a', 'b', 'c'] → 'a, b и c'"""
    items = list(items)
    if len(items) <= 1:
        return ''.join(items)
    return ', '.join(items[:-1]) + ' и ' + items[-1]


def plural_ru(n, forms):
    """plural_ru(5, ('день', 'дня', 'дней')) → 'дней'"""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return forms[1]
    return forms[2]


def format_rub(amount):
    """22800 → '22 800 ₽' (с неразрывными пробелами)"""
    if amount is None:
        return ''
    return f'{int(amount):,}'.replace(',', ' ') + ' ₽'


TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z',
    'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
    'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def slugify_ru(text, max_length=100):
    """«Грудничковое плавание. Базовый модуль» → 'grudnichkovoe-plavanie-bazovyy-modul'"""
    latin = ''.join(TRANSLIT.get(ch, ch) for ch in text.lower())
    slug = slugify(latin)
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit('-', 1)[0] or slug[:max_length]
    return slug


def sentence_case(text):
    """«ГИДРОРЕАБИЛИТАЦИЯ ДЕТЕЙ. ВВЕДЕНИЕ» → «Гидрореабилитация детей. Введение».
    Меняет только строки, набранные целиком заглавными; остальные возвращает как есть."""
    if not text or not text.isupper():
        return text
    return re.sub(r'(^|[.!?]\s+)(\w)', lambda m: m.group(1) + m.group(2).upper(), text.lower())


# Окончания названий, которыми отличаются варианты одного курса
VARIANT_SUFFIXES = [
    (re.compile(r'[\s.]*Пакет\s*["«„]*\s*Студент\s*["»“]*[\s.]*$', re.I), 'Пакет «Студент»'),
    (re.compile(r'[\s.]*Пакет\s*["«„]*\s*Специ?алист\s*["»“]*[\s.]*$', re.I), 'Пакет «Специалист»'),
    (re.compile(r'[\s.]*Повышение\s+квалификации[\s.]*$', re.I), 'Повышение квалификации'),
    (re.compile(r'[\s.]*Семинар-практикум[\s.]*$', re.I), 'Семинар-практикум'),
    (re.compile(r'[\s.]*Семинар[\s.]*$', re.I), 'Семинар'),
]


def split_variant_title(title):
    """«Патронажное искусство. Пакет "СТУДЕНТ"» → («Патронажное искусство», «Пакет «Студент»»).
    Если в конце нет пакета/семинара/повышения квалификации — (title, '')."""
    for pattern, label in VARIANT_SUFFIXES:
        base, count = pattern.subn('', title)
        if count and base.strip():
            return base.strip(), label
    return title.strip(), ''


QUALIFICATION_RE = re.compile(r'повышени\w*\s+квалификаци', re.IGNORECASE)


def is_qualification_course(*texts):
    """Курс повышения квалификации — по названию или подписи варианта.
    По окончании такого курса выдаётся удостоверение, а не сертификат."""
    return any(QUALIFICATION_RE.search(text or '') for text in texts)
