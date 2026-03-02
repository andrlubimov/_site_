from unittest.mock import patch

from django.db import OperationalError
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, TestCase

from .models import PageContent, Teacher, Course
from .views import page_content


class PageContentViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch('core.views.PageContent.objects.filter')
    def test_about_page_renders_with_fallback_when_record_missing(self, mock_filter):
        mock_filter.return_value.first.return_value = None

        response = page_content(self.factory.get('/page/about/'), 'about')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Об Ассоциации')

    @patch('core.views.PageContent.objects.filter')
    def test_unknown_slug_still_returns_404(self, mock_filter):
        mock_filter.return_value.first.return_value = None

        with self.assertRaises(Http404):
            page_content(self.factory.get('/page/unknown/'), 'unknown')

    @patch('core.views.PageContent.objects.filter')
    def test_existing_page_content_is_used(self, mock_filter):
        mock_filter.return_value.first.return_value = PageContent(
            slug='about',
            title='Тестовый заголовок',
            content='Тестовый текст',
        )

        response = page_content(self.factory.get('/page/about/'), 'about')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Тестовый заголовок')
        self.assertContains(response, 'Тестовый текст')

    @patch('core.views.PageContent.objects.filter')
    def test_about_page_renders_when_database_unavailable(self, mock_filter):
        mock_filter.side_effect = OperationalError('db unavailable')

        response = page_content(self.factory.get('/page/about/'), 'about')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Об Ассоциации')


class TeacherModelTests(TestCase):
    def test_str_returns_last_first_name(self):
        teacher = Teacher(first_name='Иван', last_name='Петров', patronymic='Сергеевич')
        self.assertEqual(str(teacher), 'Петров Иван')

    def test_full_name_property(self):
        teacher = Teacher(first_name='Иван', last_name='Петров')
        self.assertEqual(teacher.full_name, 'Иван Петров')

    def test_create_teacher(self):
        teacher = Teacher.objects.create(
            first_name='Анна', last_name='Смирнова', patronymic='Олеговна',
        )
        self.assertEqual(Teacher.objects.count(), 1)
        self.assertEqual(teacher.first_name, 'Анна')

    def test_photo_fields_optional(self):
        teacher = Teacher.objects.create(first_name='Тест', last_name='Тестов')
        self.assertFalse(teacher.photo)
        self.assertFalse(teacher.photo_transparent)


class CourseModelTests(TestCase):
    def test_course_with_teacher(self):
        teacher = Teacher.objects.create(first_name='Иван', last_name='Петров')
        course = Course.objects.create(
            title='Тестовый курс', description='Описание', hours=40, teacher=teacher,
        )
        self.assertEqual(course.teacher, teacher)
        self.assertIn(course, teacher.courses.all())

    def test_course_without_teacher(self):
        course = Course.objects.create(
            title='Курс без преподавателя', description='Описание', hours=20,
        )
        self.assertIsNone(course.teacher)

    def test_course_ordering_by_order_field(self):
        Course.objects.create(title='Второй', slug='vtoroj', description='Д', hours=10, order=2)
        Course.objects.create(title='Первый', slug='pervyj', description='Д', hours=10, order=1)
        courses = list(Course.objects.values_list('title', flat=True))
        self.assertEqual(courses[0], 'Первый')
        self.assertEqual(courses[1], 'Второй')

    def test_slug_auto_generated(self):
        course = Course.objects.create(title='Test Course', description='Д', hours=10)
        self.assertEqual(course.slug, 'test-course')


class IndexViewTests(TestCase):
    def test_index_page_renders_courses(self):
        teacher = Teacher.objects.create(first_name='Иван', last_name='Петров')
        Course.objects.create(
            title='Тестовый курс', slug='testovyj-kurs',
            description='Описание курса', hours=40, teacher=teacher, order=1,
        )
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Тестовый курс')
        self.assertContains(response, '40 учебных часов')
        self.assertContains(response, 'Иван Петров')

    def test_index_page_renders_without_courses(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Обучающие программы')
