"""Перенос данных в новую модель курса и расписания.

- справочники «Возраст детей» и «Особенности здоровья детей»;
- старое описание → краткое (первые предложения) + развёрнутое (продолжение);
- тип курса — по преобладающему формату его дат («Онлайн…», «Дистанционное…», адрес — очный);
- базовая стоимость — из старых цен вида «22 800 руб, для членов Ассоциации — 18 240 руб»;
- даты (CourseSession) → записи расписания (CourseSchedule): у очных и онлайн — даты как есть,
  у дистанционных — одна запись со сроком доступа (дат у дистанционных курсов больше нет);
  адрес и площадка из старого поля «Место» переносятся в комментарий.

Логика намеренно скопирована сюда, а не импортирована из кода приложения: миграция должна
работать одинаково, даже если код потом поменяется.
"""
import re
from collections import Counter

from django.db import migrations

CHILD_AGES = [
    ('infant', 'Грудной (0–1 год)', 1),
    ('early', 'Ранний (1–3 года)', 2),
    ('preschool', 'Дошкольный (4–7 лет)', 3),
]
HEALTH_FEATURES = [
    ('normotypical', 'Нормотипичные', 1),
    ('special_care', 'Особой заботы', 2),
    ('pregnant', 'Беременные', 3),
]

SHORT_LIMIT = 320
TRANSLIT = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
                    ['a', 'b', 'v', 'g', 'd', 'e', 'e', 'zh', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r',
                     's', 't', 'u', 'f', 'h', 'ts', 'ch', 'sh', 'sch', '', 'y', '', 'e', 'yu', 'ya']))


def split_description(text):
    """Краткое описание — первые предложения в пределах ~320 символов, развёрнутое — продолжение."""
    text = (text or '').strip()
    if len(text) <= SHORT_LIMIT:
        return text, ''
    ends = [m.end() for m in re.finditer(r'[.!?…](?=\s)', text)]
    fitting = [e for e in ends if e <= SHORT_LIMIT]
    if fitting:
        cut = fitting[-1]
    elif ends and ends[0] <= 2 * SHORT_LIMIT:
        cut = ends[0]  # первое предложение длинное, но целиком
    else:
        words = text[:SHORT_LIMIT].rsplit(' ', 1)[0]
        return words.rstrip(' ,;:—-') + '…', text  # предложение не разрезаем: полный текст ниже
    return text[:cut].strip(), text[cut:].strip()


def location_kind(location):
    loc = (location or '').strip().lower()
    if not loc:
        return ''
    if loc.startswith('онлайн'):
        return 'online'
    if loc.startswith('дистанц'):
        return 'distance'
    return 'in_person'


def full_price(price):
    """«22 800 руб, для членов Ассоциации — 18 240 руб» → 22800"""
    m = re.match(r'\s*([\d\s ]+)', price or '')
    digits = re.sub(r'\D', '', m.group(1)) if m else ''
    return int(digits) if digits else None


def slug_from_title(title):
    latin = ''.join(TRANSLIT.get(ch, ch) for ch in title.lower())
    return re.sub(r'[^a-z0-9]+', '-', latin).strip('-')[:100] or 'course'


def forwards(apps, schema_editor):
    ChildAge = apps.get_model('core', 'ChildAge')
    HealthFeature = apps.get_model('core', 'HealthFeature')
    Course = apps.get_model('core', 'Course')
    CourseSession = apps.get_model('core', 'CourseSession')
    CourseSchedule = apps.get_model('core', 'CourseSchedule')

    for code, name, order in CHILD_AGES:
        ChildAge.objects.update_or_create(code=code, defaults={'name': name, 'order': order})
    for code, name, order in HEALTH_FEATURES:
        HealthFeature.objects.update_or_create(code=code, defaults={'name': name, 'order': order})

    for course in Course.objects.all():
        sessions = list(CourseSession.objects.filter(course=course).order_by('start_date', 'pk'))

        if not course.short_description:
            course.short_description, course.full_description = split_description(course.description)
        if not course.slug:
            base, n = slug_from_title(course.title), 2
            course.slug = base
            while Course.objects.filter(slug=course.slug).exclude(pk=course.pk).exists():
                course.slug, n = f'{base}-{n}', n + 1

        kinds = Counter(location_kind(s.location) for s in sessions if location_kind(s.location))
        if not course.course_type and kinds:
            course.course_type = kinds.most_common(1)[0][0]
        prices = Counter(full_price(s.price) for s in sessions if full_price(s.price))
        if course.base_price is None and prices:
            course.base_price = prices.most_common(1)[0][0]
        course.save()

        def override(session):
            price = full_price(session.price)
            return price if price and price != course.base_price else None

        if course.course_type == 'distance':
            distance = [s for s in sessions if location_kind(s.location) == 'distance']
            dated = [s for s in sessions if location_kind(s.location) != 'distance']
            if distance:
                days = Counter(((s.end_date or s.start_date) - s.start_date).days + 1 for s in distance)
                positive = [d for d, _ in days.most_common() if d > 0]
                session_prices = Counter(full_price(s.price) for s in distance if full_price(s.price))
                price = session_prices.most_common(1)[0][0] if session_prices else None
                CourseSchedule.objects.create(
                    course=course, format='group', access_days=positive[0] if positive else None,
                    price_override=price if price and price != course.base_price else None,
                )
        else:
            dated = sessions

        for s in dated:
            kind = location_kind(s.location)
            comment = [s.location] if kind in ('in_person', 'online') and s.location else []
            if s.note:
                comment.append(s.note)
            in_moscow = s.location.strip().lower().startswith('москва')
            CourseSchedule.objects.create(
                course=course,
                format='away' if kind == 'in_person' and not in_moscow else 'group',
                start_date=s.start_date,
                end_date=s.end_date or s.start_date,
                price_override=override(s),
                comment='\n'.join(comment),
            )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_course_redesign'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
