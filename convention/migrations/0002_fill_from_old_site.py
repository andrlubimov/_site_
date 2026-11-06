"""Сайт конвенции — данными со старого сайта (convention/seed), если конвенций в базе ещё нет."""
from django.db import migrations


def fill(apps, schema_editor):
    from convention.seed import load

    load(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('convention', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
