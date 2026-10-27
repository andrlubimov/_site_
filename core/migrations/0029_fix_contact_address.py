"""Адрес Ассоциации — «дом 1, строение 2» (было «корпус 2»); метка на карте — по координатам здания."""
from django.db import migrations

from core.contact_defaults import MAP_POINT


def fix(apps, schema_editor):
    ContactInfo = apps.get_model('core', 'ContactInfo')
    for info in ContactInfo.objects.all():
        info.address = info.address.replace('дом 1, корпус 2', 'дом 1, строение 2')
        info.postal_address = info.postal_address.replace('дом 1, корпус 2', 'дом 1, строение 2')
        if info.map_query == 'Москва, улица Малыгина, 1к2':
            info.map_query = 'Москва, улица Малыгина, 1с2'
        if info.map_lat is None and info.map_lng is None:
            info.map_lat, info.map_lng = MAP_POINT['map_lat'], MAP_POINT['map_lng']
        info.save()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_contact_map_point'),
    ]

    operations = [
        migrations.RunPython(fix, migrations.RunPython.noop),
    ]
