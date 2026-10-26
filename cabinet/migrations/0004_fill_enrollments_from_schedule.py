from datetime import timedelta

from django.db import migrations


def fill_from_schedule(apps, schema_editor):
    """Купленные курсы: курс и даты — из записи расписания (раньше даты можно было указать вручную)"""
    Enrollment = apps.get_model('cabinet', 'Enrollment')
    for enrollment in Enrollment.objects.select_related('schedule'):
        schedule = enrollment.schedule
        enrollment.course_id = schedule.course_id
        if schedule.start_date:
            enrollment.start_date, enrollment.end_date = schedule.start_date, schedule.end_date
        elif schedule.access_days:  # дистанционный: доступ со дня покупки на срок из записи
            enrollment.end_date = enrollment.start_date + timedelta(days=schedule.access_days - 1)
        enrollment.save(update_fields=['course', 'start_date', 'end_date'])


class Migration(migrations.Migration):

    dependencies = [
        ('cabinet', '0003_profile_place_enrollment_from_schedule'),
    ]

    operations = [
        migrations.RunPython(fill_from_schedule, migrations.RunPython.noop),
    ]
