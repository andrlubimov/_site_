"""Числительные и даты для текстов сайта конвенции: «Четырнадцатая конвенция», «с 4 по 6 декабря 2026»."""
from core.utils import MONTHS_GENITIVE, format_date_range

# порядковые 1–9: (мужской род, женский род)
UNITS = {
    1: ('первый', 'первая'), 2: ('второй', 'вторая'), 3: ('третий', 'третья'),
    4: ('четвёртый', 'четвёртая'), 5: ('пятый', 'пятая'), 6: ('шестой', 'шестая'),
    7: ('седьмой', 'седьмая'), 8: ('восьмой', 'восьмая'), 9: ('девятый', 'девятая'),
}
# основы 10–19, 20, 30: + «ый» / «ая»
STEMS = {
    10: 'десят', 11: 'одиннадцат', 12: 'двенадцат', 13: 'тринадцат', 14: 'четырнадцат', 15: 'пятнадцат',
    16: 'шестнадцат', 17: 'семнадцат', 18: 'восемнадцат', 19: 'девятнадцат', 20: 'двадцат', 30: 'тридцат',
}
TENS = {20: 'двадцать', 30: 'тридцать'}


def ordinal_ru(n, feminine=False):
    """ordinal_ru(14) → 'четырнадцатый', ordinal_ru(13, feminine=True) → 'тринадцатая', 21 → 'двадцать первый'.
    Числа больше 39 — цифрами: «40-й» / «40-я»."""
    form = 1 if feminine else 0
    if n in UNITS:
        return UNITS[n][form]
    if n in STEMS:
        return STEMS[n] + ('ая' if feminine else 'ый')
    tens, unit = divmod(n, 10)
    if tens * 10 in TENS and unit:
        return f'{TENS[tens * 10]} {UNITS[unit][form]}'
    return f'{n}-{"я" if feminine else "й"}'


def date_span(start, end):
    """«с 4 по 6 декабря 2026», «с 30 ноября по 3 декабря 2017», «5 декабря 2026»"""
    if start == end:
        return f'{start.day} {MONTHS_GENITIVE[start.month - 1]} {start.year}'
    if start.month == end.month and start.year == end.year:
        return f'с {start.day} по {end.day} {MONTHS_GENITIVE[end.month - 1]} {end.year}'
    if start.year == end.year:
        return f'с {start.day} {MONTHS_GENITIVE[start.month - 1]} по {end.day} {MONTHS_GENITIVE[end.month - 1]} {end.year}'
    return (f'с {start.day} {MONTHS_GENITIVE[start.month - 1]} {start.year} '
            f'по {end.day} {MONTHS_GENITIVE[end.month - 1]} {end.year}')


def date_range(start, end):
    """«4–6 декабря 2026» — как в остальном сайте"""
    return format_date_range(start, end)


def day_month(day):
    """«5 декабря»"""
    return f'{day.day} {MONTHS_GENITIVE[day.month - 1]}'
