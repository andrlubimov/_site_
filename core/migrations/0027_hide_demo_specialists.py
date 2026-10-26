"""Специалисты из стартовых демо-данных (core/load_initial_data.py) — не показывать в карусели «Членство
в ассоциации» на главной. Записи остаются: вернуть можно галочкой «Активен» в админке."""
from django.db import migrations

DEMO_SPECIALISTS = ['Надежда Кириченко', 'Наталья Полякова', 'Анастасия Григорьева', 'Екатерина Фомичева']


def hide(apps, schema_editor):
    apps.get_model('core', 'Specialist').objects.filter(name__in=DEMO_SPECIALISTS).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_teacher_user'),
    ]

    operations = [
        migrations.RunPython(hide, migrations.RunPython.noop),
    ]
