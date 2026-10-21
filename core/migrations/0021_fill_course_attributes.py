"""Характеристики курсов для фильтров (возраст детей, особенности здоровья, место, уровень),
необходимый курс и недостающие тексты — см. core/legacy_attributes.py.
Заполняется только то, что ещё пусто."""
from django.db import migrations

from core.legacy_attributes import fill_course_attributes


def fill(apps, schema_editor):
    fill_course_attributes(apps.get_model('core', 'Course'), apps.get_model('core', 'ChildAge'),
                           apps.get_model('core', 'HealthFeature'))


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_remove_course_parent'),
    ]

    operations = [
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
