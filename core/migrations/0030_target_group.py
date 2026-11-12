"""«Возраст детей» → «Целевая группа»: новые названия, добавлены «Взрослые».

Коды прежние — ссылки на отфильтрованные страницы (?age=infant…) продолжают работать.
Целевая группа, особенности здоровья и место проведения у курса теперь необязательны.
"""
from django.db import migrations, models

TARGET_GROUPS = [
    ('infant', 'Груднички', 1),
    ('early', 'Ранний возраст', 2),
    ('preschool', 'Дошкольный возраст', 3),
    ('adults', 'Взрослые', 4),
]
OLD_NAMES = {
    'infant': 'Грудной (0–1 год)',
    'early': 'Ранний (1–3 года)',
    'preschool': 'Дошкольный (4–7 лет)',
}


def rename(apps, schema_editor):
    ChildAge = apps.get_model('core', 'ChildAge')
    for code, name, order in TARGET_GROUPS:
        ChildAge.objects.update_or_create(code=code, defaults={'name': name, 'order': order})


def restore(apps, schema_editor):
    ChildAge = apps.get_model('core', 'ChildAge')
    ChildAge.objects.filter(code='adults').delete()
    for code, name in OLD_NAMES.items():
        ChildAge.objects.filter(code=code).update(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0029_fix_contact_address'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='childage',
            options={'ordering': ['order'], 'verbose_name': 'Целевая группа', 'verbose_name_plural': 'Целевые группы'},
        ),
        migrations.AlterField(
            model_name='course',
            name='child_ages',
            field=models.ManyToManyField(blank=True, related_name='courses', to='core.childage', verbose_name='Целевая группа'),
        ),
        migrations.AlterField(
            model_name='course',
            name='health_features',
            field=models.ManyToManyField(blank=True, related_name='courses', to='core.healthfeature', verbose_name='Особенности здоровья детей'),
        ),
        migrations.AlterField(
            model_name='course',
            name='venue',
            field=models.CharField(blank=True, choices=[('pool', 'В бассейне'), ('gym', 'В спортзале'), ('home', 'На дому')], max_length=20, verbose_name='Место проведения'),
        ),
        migrations.RunPython(rename, restore),
    ]
