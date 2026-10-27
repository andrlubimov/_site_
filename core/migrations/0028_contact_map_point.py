from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_hide_demo_specialists'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contactinfo',
            name='map_query',
            field=models.CharField(blank=True, help_text='Что искать на Яндекс Картах, если не указаны координаты метки ниже. Если пусто — карта по адресу выше.', max_length=255, verbose_name='Адрес для карты'),
        ),
        migrations.AddField(
            model_name='contactinfo',
            name='map_lat',
            field=models.DecimalField(blank=True, decimal_places=6, help_text='Координаты здания — на карте ставится метка Ассоциации. Узнать их: Яндекс Карты → правый клик по зданию → «Что здесь?» (первое число — широта, второе — долгота).', max_digits=9, null=True, verbose_name='Метка на карте: широта'),
        ),
        migrations.AddField(
            model_name='contactinfo',
            name='map_lng',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Метка на карте: долгота'),
        ),
    ]
