"""Первичное заполнение вариантов курсов по названиям.

Курсы, названия которых отличаются только окончанием («Пакет "Студент"» / «Пакет "Специалист"»,
«Семинар» / «Повышение квалификации»), связываются в одну группу: первый по порядку становится
основным, остальные — его вариантами. Результат можно поправить в админке (раздел «Список курсов»).
"""
import re

from django.db import migrations

from core.utils import sentence_case, split_variant_title


def group_key(text):
    return re.sub(r'[\W_]+', ' ', text.lower().replace('ё', 'е')).strip()


def fill_variants(apps, schema_editor):
    Course = apps.get_model('core', 'Course')
    groups = {}
    for course in Course.objects.order_by('order', 'pk'):
        base, label = split_variant_title(course.title)
        groups.setdefault(group_key(base), []).append((course, base, label))

    for members in groups.values():
        head = members[0][0]
        for course, base, label in members:
            course.variant_label = course.variant_label or label
            if not course.card_title and (label or course.title.isupper()):
                course.card_title = sentence_case(base)
            if course is not head and course.parent_id is None:
                course.parent = head
            course.save(update_fields=['variant_label', 'card_title', 'parent'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_course_variants'),
    ]

    operations = [
        migrations.RunPython(fill_variants, migrations.RunPython.noop),
    ]
