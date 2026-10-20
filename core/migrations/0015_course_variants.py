from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_teacher_page'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='card_title',
            field=models.CharField(
                blank=True, max_length=255, verbose_name='Название в списке курсов',
                help_text='Общее название для карточки на странице «Программы» — без «Пакет Студент», '
                          '«Семинар» и т. п. Если пусто, используется название курса.',
            ),
        ),
        migrations.AddField(
            model_name='course',
            name='parent',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='variants', to='core.course', verbose_name='Основной курс',
                help_text='Если этот курс — вариант другого (другой пакет, семинар или повышение квалификации), '
                          'выберите основной курс: на странице «Программы» они покажутся одной карточкой.',
            ),
        ),
        migrations.AddField(
            model_name='course',
            name='variant_label',
            field=models.CharField(
                blank=True, max_length=100, verbose_name='Название варианта',
                help_text='Строка внутри карточки, например «Пакет «Студент»», «Семинар», '
                          '«Повышение квалификации». Если пусто, пишется тип курса.',
            ),
        ),
    ]
