from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_fill_contact_info'),
        ('cabinet', '0002_postponed_membership_courses_certificates'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='about',
            field=models.TextField(blank=True, verbose_name='Обо мне'),
        ),
        migrations.AddField(
            model_name='profile',
            name='city',
            field=models.CharField(blank=True, max_length=100, verbose_name='Город'),
        ),
        migrations.AddField(
            model_name='profile',
            name='country',
            field=models.CharField(blank=True, max_length=100, verbose_name='Страна'),
        ),
        migrations.AlterField(
            model_name='enrollment',
            name='course',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.course', verbose_name='Курс'),
        ),
        migrations.AlterField(
            model_name='enrollment',
            name='end_date',
            field=models.DateField(editable=False, null=True, verbose_name='Окончание обучения'),
        ),
        migrations.AlterField(
            model_name='enrollment',
            name='schedule',
            field=models.ForeignKey(help_text='Курс и даты обучения возьмутся из неё. У дистанционного курса доступ — со дня покупки.', on_delete=django.db.models.deletion.PROTECT, related_name='+', to='core.courseschedule', verbose_name='Запись расписания'),
        ),
        migrations.AlterField(
            model_name='enrollment',
            name='start_date',
            field=models.DateField(editable=False, verbose_name='Начало обучения'),
        ),
    ]
