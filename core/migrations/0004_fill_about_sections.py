from django.db import migrations

from core.about_defaults import ABOUT_SECTIONS


def fill(apps, schema_editor):
    AboutSection = apps.get_model('core', 'AboutSection')
    for order, data in enumerate(ABOUT_SECTIONS, start=1):
        AboutSection.objects.get_or_create(
            key=data['key'],
            defaults={'title': data['title'], 'content': data['content'], 'order': order},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_about_section'),
    ]

    operations = [
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
