"""Преподаватели — члены Ассоциации. У каждого — аккаунт в личном кабинете (пока без email и пароля:
войти можно, когда администратор их задаст) и членство с 26 октября 2026 года."""
from datetime import date

from django.contrib.auth.hashers import make_password
from django.db import migrations

MEMBERS_SINCE = date(2026, 10, 26)
NEXT_FEE = date(2027, 10, 26)  # взносы — раз в год


def teachers_to_members(apps, schema_editor):
    Teacher = apps.get_model('core', 'Teacher')
    User = apps.get_model('auth', 'User')
    Membership = apps.get_model('cabinet', 'Membership')
    for teacher in Teacher.objects.filter(user=None):
        user, _ = User.objects.get_or_create(username=teacher.slug or f'teacher-{teacher.pk}', defaults={
            'first_name': teacher.first_name, 'last_name': teacher.last_name,
            'password': make_password(None),  # пароля нет — войти нельзя, пока его не зададут
        })
        teacher.user = user
        teacher.save(update_fields=['user'])
        Membership.objects.get_or_create(user=user, defaults={
            'status': 'active', 'start_date': MEMBERS_SINCE, 'next_fee_date': NEXT_FEE,
        })


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('core', '0026_teacher_user'),
        ('cabinet', '0005_enrollment_unique'),
    ]

    operations = [
        migrations.RunPython(teachers_to_members, migrations.RunPython.noop),
    ]
