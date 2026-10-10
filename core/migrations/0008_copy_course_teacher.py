from django.db import migrations


def copy_teacher(apps, schema_editor):
    """Переносит единственного преподавателя курса (FK teacher) в связь CourseTeacher."""
    Course = apps.get_model('core', 'Course')
    CourseTeacher = apps.get_model('core', 'CourseTeacher')
    for course in Course.objects.exclude(teacher=None):
        CourseTeacher.objects.get_or_create(course=course, teacher_id=course.teacher_id, defaults={'order': 0})


def restore_teacher(apps, schema_editor):
    Course = apps.get_model('core', 'Course')
    CourseTeacher = apps.get_model('core', 'CourseTeacher')
    for link in CourseTeacher.objects.order_by('course_id', 'order', 'pk'):
        Course.objects.filter(pk=link.course_id, teacher=None).update(teacher_id=link.teacher_id)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_course_teachers_and_details'),
    ]

    operations = [
        migrations.RunPython(copy_teacher, restore_teacher),
    ]
