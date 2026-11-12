"""Представители-франчайзи: страница представителя (описание, адрес) и курсы, которые он проводит.

Уникальный адрес нельзя добавить к существующим строкам за один шаг, поэтому (как в 0014):
поле без уникальности → заполнение из названия (транслитом) → уникальность.
"""
import re

from django.db import migrations, models

TRANSLIT = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
                    ['a', 'b', 'v', 'g', 'd', 'e', 'e', 'zh', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r',
                     's', 't', 'u', 'f', 'h', 'ts', 'ch', 'sh', 'sch', '', 'y', '', 'e', 'yu', 'ya']))

SLUG_HELP = ('Латиница: grudnichkovoe-plavanie.ru/specialists/адрес/. '
             'Если оставить пустым, заполнится из названия.')


def slug_from(text):
    latin = ''.join(TRANSLIT.get(ch, ch) for ch in text.lower())
    return re.sub(r'[^a-z0-9]+', '-', latin).strip('-')[:100].strip('-') or 'representative'


def fill_slugs(apps, schema_editor):
    Representative = apps.get_model('core', 'Representative')
    used = set()
    for rep in Representative.objects.order_by('pk'):
        base = slug_from(rep.name)
        slug, n = base, 2
        while slug in used:
            slug, n = f'{base}-{n}', n + 1
        used.add(slug)
        rep.slug = slug
        rep.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0030_target_group'),
    ]

    operations = [
        migrations.AddField(
            model_name='representative',
            name='description',
            field=models.TextField(
                blank=True, verbose_name='Описание',
                help_text='Показывается на странице представителя. Абзацы разделяйте пустой строкой.',
            ),
        ),
        migrations.AddField(
            model_name='representative',
            name='slug',
            # без индекса: на PostgreSQL AlterField ниже создаёт индекс *_like заново и падает на дубле
            field=models.SlugField(blank=True, default='', max_length=120, db_index=False,
                                   verbose_name='Адрес страницы'),
            preserve_default=False,
        ),
        migrations.RunPython(fill_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='representative',
            name='slug',
            field=models.SlugField(blank=True, help_text=SLUG_HELP, max_length=120, unique=True,
                                   verbose_name='Адрес страницы'),
        ),
        migrations.AddField(
            model_name='course',
            name='representatives',
            field=models.ManyToManyField(
                blank=True, related_name='courses', to='core.representative',
                verbose_name='Проводится представителями',
                help_text='Представители, купившие франшизу курса. На странице курса — список «Данный курс можно '
                          'пройти у наших представителей», на странице представителя — этот курс.',
            ),
        ),
    ]
