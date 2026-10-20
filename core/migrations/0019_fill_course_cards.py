"""Раскладывает курсы по карточкам (см. core/legacy_cards.py).
Карточки получают только курсы без карточки; курсы, которых нет в списке, — по одной карточке на курс."""
from django.db import migrations

from core.legacy_cards import assign_course_cards


def fill(apps, schema_editor):
    assign_course_cards(apps.get_model('core', 'Course'), apps.get_model('core', 'CourseCard'))


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_course_card'),
    ]

    operations = [
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
