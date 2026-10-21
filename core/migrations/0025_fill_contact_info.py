"""Контакты со старого сайта (core/contact_defaults.py) — если записи ещё нет."""
from django.db import migrations

from core.contact_defaults import CONTACT_DEFAULTS


def fill(apps, schema_editor):
    ContactInfo = apps.get_model('core', 'ContactInfo')
    if not ContactInfo.objects.exists():
        ContactInfo.objects.create(**CONTACT_DEFAULTS)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_contact_info'),
    ]

    operations = [
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
