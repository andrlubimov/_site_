"""Страница преподавателя: описание и адрес страницы (slug).

Уникальный адрес нельзя добавить к существующим строкам за один шаг, поэтому:
поле без уникальности → заполнение из имени и фамилии (транслитом) → уникальность.
"""
import re

from django.db import migrations, models

TRANSLIT = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
                    ['a', 'b', 'v', 'g', 'd', 'e', 'e', 'zh', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r',
                     's', 't', 'u', 'f', 'h', 'ts', 'ch', 'sh', 'sch', '', 'y', '', 'e', 'yu', 'ya']))

SLUG_HELP = ('Латиница: grudnichkovoe-plavanie.ru/education/teachers/адрес/. '
             'Если оставить пустым, заполнится из имени и фамилии.')


def slug_from(text):
    latin = ''.join(TRANSLIT.get(ch, ch) for ch in text.lower())
    return re.sub(r'[^a-z0-9]+', '-', latin).strip('-')[:120] or 'teacher'


def fill_slugs(apps, schema_editor):
    Teacher = apps.get_model('core', 'Teacher')
    used = set()
    for teacher in Teacher.objects.order_by('pk'):
        base = slug_from(f'{teacher.first_name} {teacher.last_name}')
        slug, n = base, 2
        while slug in used:
            slug, n = f'{base}-{n}', n + 1
        used.add(slug)
        teacher.slug = slug
        teacher.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_remove_old_course_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='teacher',
            name='bio',
            field=models.TextField(
                blank=True, verbose_name='Описание',
                help_text='Показывается на странице преподавателя. Абзацы разделяйте пустой строкой.',
            ),
        ),
        migrations.AddField(
            model_name='teacher',
            name='slug',
            # без индекса: на PostgreSQL AlterField ниже создаёт индекс *_like заново и падает на дубле
            field=models.SlugField(blank=True, default='', max_length=120, db_index=False,
                                   verbose_name='Адрес страницы'),
            preserve_default=False,
        ),
        migrations.RunPython(fill_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='teacher',
            name='slug',
            field=models.SlugField(blank=True, help_text=SLUG_HELP, max_length=120, unique=True,
                                   verbose_name='Адрес страницы'),
        ),
    ]
