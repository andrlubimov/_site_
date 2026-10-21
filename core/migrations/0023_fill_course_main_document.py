"""По окончании курсов повышения квалификации выдаётся удостоверение, а не сертификат.
Курс повышения квалификации определяется по названию или подписи варианта в карточке."""
from django.db import migrations

from core.utils import is_qualification_course


def fill(apps, schema_editor):
    Course = apps.get_model('core', 'Course')
    for course in Course.objects.all():
        if is_qualification_course(course.title, course.variant_label):
            # удостоверение стало основным документом — отдельный вариант «с удостоверением» не нужен
            Course.objects.filter(pk=course.pk).update(
                main_document='qualification', has_qualification_certificate=False,
                qualification_certificate_price=None)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_course_main_document'),
    ]

    operations = [
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
