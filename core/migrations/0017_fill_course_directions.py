"""Направление работы для курсов со старого сайта (см. core/legacy_directions.py).
Заполняется только там, где направление ещё не указано."""
from django.db import migrations

from core.legacy_directions import LEGACY_DIRECTIONS


def fill(apps, schema_editor):
    Course = apps.get_model('core', 'Course')
    for slug, direction in LEGACY_DIRECTIONS.items():
        Course.objects.filter(slug=slug, direction='').update(direction=direction)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_fill_course_variants'),
    ]

    operations = [
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
