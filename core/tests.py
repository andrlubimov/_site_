from datetime import date, timedelta
from unittest.mock import patch

from django.db import OperationalError
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, TestCase

from .models import AboutSection, CourseSession, CourseTeacher, PageContent, Representative, Teacher, Course
from .views import format_date_range, page_content


class PageContentViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch('core.views.PageContent.objects.filter')
    def test_known_page_renders_with_fallback_when_record_missing(self, mock_filter):
        mock_filter.return_value.first.return_value = None

        response = page_content(self.factory.get('/page/membership/'), 'membership')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Членство')

    @patch('core.views.PageContent.objects.filter')
    def test_unknown_slug_still_returns_404(self, mock_filter):
        mock_filter.return_value.first.return_value = None

        with self.assertRaises(Http404):
            page_content(self.factory.get('/page/unknown/'), 'unknown')

    @patch('core.views.PageContent.objects.filter')
    def test_existing_page_content_is_used(self, mock_filter):
        mock_filter.return_value.first.return_value = PageContent(
            slug='contacts',
            title='Тестовый заголовок',
            content='Тестовый текст',
        )

        response = page_content(self.factory.get('/page/contacts/'), 'contacts')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Тестовый заголовок')
        self.assertContains(response, 'Тестовый текст')

    @patch('core.views.AboutSection.objects.all')
    def test_about_page_renders_when_database_unavailable(self, mock_all):
        mock_all.side_effect = OperationalError('db unavailable')

        response = page_content(self.factory.get('/page/about/'), 'about')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Об Ассоциации')
        self.assertContains(response, 'Цели и задачи Ассоциации')


class AboutPageTests(TestCase):
    def test_all_sections_created_by_migration(self):
        keys = list(AboutSection.objects.values_list('key', flat=True))
        self.assertEqual(keys, ['intro', 'goals', 'directions', 'education', 'documents'])

    def test_page_renders_all_blocks(self):
        response = self.client.get('/page/about/')
        self.assertEqual(response.status_code, 200)
        for text in ['счастливые обладатели самой лучшей профессии', 'Цели и задачи Ассоциации',
                     'Направления деятельности', 'Образовательная и просветительская деятельность',
                     'Документы, регламентирующие деятельность Ассоциации']:
            self.assertContains(response, text)

    def test_edited_text_is_shown(self):
        AboutSection.objects.filter(key='goals').update(title='Новые цели', content='Первый абзац\n\nВторой абзац')
        response = self.client.get('/page/about/')
        self.assertContains(response, 'Новые цели')
        self.assertContains(response, '<p>Первый абзац</p>', html=True)
        self.assertNotContains(response, 'Цели и задачи Ассоциации')

    def test_missing_section_falls_back_to_default(self):
        AboutSection.objects.filter(key='directions').delete()
        response = self.client.get('/page/about/')
        self.assertContains(response, 'Направления деятельности')


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
    def test_course_with_teachers_in_order(self):
        first = Teacher.objects.create(first_name='Наталия', last_name='Дворяшина')
        second = Teacher.objects.create(first_name='Екатерина', last_name='Любимова')
        course = Course.objects.create(title='Тестовый курс', description='Описание', hours=40)
        CourseTeacher.objects.create(course=course, teacher=second, order=1)
        CourseTeacher.objects.create(course=course, teacher=first, order=0)
        self.assertEqual(course.teacher_list, [first, second])
        self.assertEqual(course.main_teacher, first)
        self.assertEqual(course.teacher_names, 'Наталия Дворяшина, Екатерина Любимова')
        self.assertIn(course, first.courses.all())

    def test_course_without_teacher(self):
        course = Course.objects.create(
            title='Курс без преподавателя', description='Описание', hours=20,
        )
        self.assertIsNone(course.main_teacher)
        self.assertEqual(course.teacher_names, '')

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
        course = Course.objects.create(
            title='Тестовый курс', slug='testovyj-kurs',
            description='Описание курса', hours=40, order=1,
        )
        CourseTeacher.objects.create(course=course, teacher=teacher)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Тестовый курс')
        self.assertContains(response, '40 учебных часов')
        self.assertContains(response, 'Иван Петров')

    def test_index_shows_nearest_courses_first(self):
        far = Course.objects.create(title='Дальний курс', slug='far', description='Д', hours=10, order=1)
        near = Course.objects.create(title='Ближний курс', slug='near', description='Д', hours=10, order=2)
        CourseSession.objects.create(course=far, start_date=date.today() + timedelta(days=60))
        CourseSession.objects.create(course=near, start_date=date.today() + timedelta(days=3))
        courses = list(self.client.get('/').context['courses'])
        self.assertEqual(courses[:2], [near, far])

    def test_index_page_renders_without_courses(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Обучающие программы')


class TimetableCalendarTests(TestCase):
    def setUp(self):
        teacher = Teacher.objects.create(first_name='Иван', last_name='Петров')
        self.course = Course.objects.create(
            title='Курс в календаре', slug='kurs-v-kalendare',
            description='Описание', hours=24,
        )
        CourseTeacher.objects.create(course=self.course, teacher=teacher)

    def get_events(self):
        response = self.client.get('/page/timetable/')
        self.assertEqual(response.status_code, 200)
        return response.context["calendar_events"]

    def test_session_becomes_calendar_event(self):
        CourseSession.objects.create(
            course=self.course, start_date=date(2026, 11, 12), end_date=date(2026, 11, 14), location='Москва',
        )
        events = self.get_events()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event['title'], 'Курс в календаре')
        self.assertEqual(event['start'], '2026-11-12')
        self.assertEqual(event['end'], '2026-11-15')  # конец невключительный
        self.assertEqual(event['url'], '/courses/kurs-v-kalendare/')
        self.assertEqual(event['extendedProps']['teacher'], 'Иван Петров')
        self.assertEqual(event['extendedProps']['dates'], '12–14 ноября 2026')

    def test_one_day_session(self):
        CourseSession.objects.create(course=self.course, start_date=date(2026, 5, 5))
        event = self.get_events()[0]
        self.assertEqual(event['end'], '2026-05-06')
        self.assertEqual(event['extendedProps']['dates'], '5 мая 2026')

    def test_inactive_course_hidden(self):
        CourseSession.objects.create(course=self.course, start_date=date(2026, 5, 5))
        Course.objects.filter(pk=self.course.pk).update(is_active=False)
        self.assertEqual(self.get_events(), [])

    def test_calendar_assets_only_on_timetable(self):
        self.assertContains(self.client.get('/page/timetable/'), 'fullcalendar.global.js')
        self.assertNotContains(self.client.get('/page/contacts/'), 'fullcalendar.global.js')

    def test_format_date_range(self):
        self.assertEqual(format_date_range(date(2026, 11, 30), date(2026, 12, 2)), '30 ноября – 2 декабря 2026')
        self.assertEqual(format_date_range(date(2026, 12, 30), date(2027, 1, 2)),
                         '30 декабря 2026 – 2 января 2027')


class RepresentativesPageTests(TestCase):
    def setUp(self):
        self.regional = Representative.objects.create(
            kind='regional', name='Счастливый крепыш', city='Новосибирск', country='Россия',
            phone='+7 (913) 713-94-64', latitude=55.03, longitude=82.92,
        )
        self.foreign = Representative.objects.create(
            kind='foreign', name='Представитель в Турции', city='Стамбул', country='Турция',
            email='rep@example.com',
        )

    def test_page_splits_regional_and_foreign(self):
        response = self.client.get('/specialists/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['regional'], [self.regional])
        self.assertEqual(response.context['foreign'], [self.foreign])
        self.assertContains(response, 'Новосибирск • Россия')
        self.assertContains(response, 'href="tel:+79137139464"')
        self.assertContains(response, 'mailto:rep@example.com')

    def test_inactive_representative_hidden(self):
        Representative.objects.filter(pk=self.foreign.pk).update(is_active=False)
        response = self.client.get('/specialists/')
        self.assertNotContains(response, 'Представитель в Турции')

    def test_globe_points_include_hq_and_only_located_representatives(self):
        points = self.client.get('/specialists/').context['globe_points']
        self.assertEqual(points[0]['kind'], 'hq')
        names = [p['name'] for p in points[1:]]
        self.assertEqual(names, ['Счастливый крепыш'])  # у зарубежного нет координат
        self.assertEqual(points[1]['id'], f'rep-{self.regional.pk}')

    def test_phone_href(self):
        self.assertEqual(Representative(phone='+998 909242004').phone_href, '+998909242004')
        self.assertEqual(Representative(phone='8 (800) 100-00-00').phone_href, '88001000000')


class OldSiteImportParserTests(SimpleTestCase):
    """Разбор HTML старого сайта командой import_old_courses (без сети)"""

    TIMETABLE = """
    <div class="edu-schedule-box">
        <p class="tiny-outline edu-schedule-box-infoline">
        <span class="date">09.10.2026 — 23.10.2026</span>
        <span class="time">80 учебных часов</span>•
        <span class="cost">от 18 240 руб</span></p>
        <p class="tiny-outline">Наталия Дворяшина</p>
        <h2 class="small"><a href="education/courses/gp-base-pool3/09102026">Грудничковое плавание</a></h2>
    </div>"""

    COURSE = """<!-- CONTENT -->
    <p class="middle-outline">семинар</p>
    <h2 class="large">Грудничковое плавание. Работа в&nbsp;бассейне.</h2>
    <span class="hours-marker">80 учебных часов</span>
    <p class="fio-title"><img src="data/tutors/1001.jpg" class="x">Наталия<br><b>Дворяшина</b></p>
    <p class="large-text" style="text-align: justify">Первая строка
    продолжение.<br />Вторая строка.</p>
    <p class=accent style="x">&mdash;&nbsp;Для тренеров.</p>
    <h3>Рассматриваемые темы</h3><p>Тема 1</p><p>Тема 2</p>
    <div class="block-container block-container-left">
    <div class="framed-block"><h2 class="small">Где проходят занятия?</h2>
    <p><img src="loc.png">ОНЛАЙН, </p><p class="small-text">ZOOM</p></div>
    <div class="framed-block"><h2 class="small" style="margin-top: 0;">Стоимость</h2>
    <p class="outline"><b>22 800</b> <span>руб</span></p><hr>
    <p class="outline">18 240 <span>руб</span></p></div></div>
    <!-- FOOTER -->"""

    def test_parse_timetable(self):
        from core.management.commands.import_old_courses import parse_timetable
        rows = parse_timetable(self.TIMETABLE)
        self.assertEqual(rows, [{
            'slug': 'gp-base-pool3', 'href': 'education/courses/gp-base-pool3/09102026',
            'start': date(2026, 10, 9), 'end': date(2026, 10, 23), 'hours': 80,
        }])

    def test_parse_course_page(self):
        from core.management.commands.import_old_courses import parse_course_page
        data = parse_course_page(self.COURSE)
        self.assertEqual(data['kind'], 'Семинар')
        self.assertEqual(data['title'], 'Грудничковое плавание. Работа в бассейне.')
        self.assertEqual(data['hours'], 80)
        self.assertEqual(data['teachers'], [
            {'photo': 'data/tutors/1001.jpg', 'first_name': 'Наталия', 'last_name': 'Дворяшина'}])
        self.assertEqual(data['description'], 'Первая строка продолжение.\nВторая строка.')
        self.assertEqual(data['audience'], '— Для тренеров.')
        self.assertEqual(data['program'], 'Тема 1\n\nТема 2')
        self.assertEqual(data['location'], 'Онлайн — ZOOM')
        self.assertEqual(data['price'], '22 800 руб, для членов Ассоциации — 18 240 руб')


class PartnersPageTests(TestCase):
    def test_pool_renders_buoys_with_links(self):
        from .models import Partner
        Partner.objects.create(name='Дарин', description='Станции дозирования', city='Москва',
                               country='Россия', website='https://darin7.ru/', order=1)
        Partner.objects.create(name='Без сайта', order=2)
        Partner.objects.create(name='Скрытый', is_active=False)
        response = self.client.get('/partners/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="buoy"', count=2)
        self.assertContains(response, 'href="https://darin7.ru/" target="_blank" rel="noopener"')
        self.assertContains(response, 'Москва • Россия')
        self.assertNotContains(response, 'Скрытый')

    def test_parse_old_partners_page(self):
        from core.management.commands.import_old_partners import parse_partners
        page = """<!-- CONTENT --><div class="partner-box">
            <a href="https://darin7.ru/" target="_blank"><img src="data/partners/darin.png"></a>
            <h3>Дарин</h3><p>Станции&nbsp;дозирования.</p>
            <p class="location">Москва • Россия</p>
            <p class="website"><a href="https://darin7.ru/" target="_blank">Сайт партнера</a></p>
            </div><!-- FOOTER -->"""
        self.assertEqual(parse_partners(page), [{
            'name': 'Дарин', 'description': 'Станции дозирования.', 'logo': 'data/partners/darin.png',
            'website': 'https://darin7.ru/', 'city': 'Москва', 'country': 'Россия',
        }])


class PartnerAdminTests(TestCase):
    def setUp(self):
        import tempfile
        from django.contrib.auth.models import User
        self.media = tempfile.mkdtemp()
        self.addCleanup(__import__('shutil').rmtree, self.media, ignore_errors=True)
        self.user = User.objects.create_superuser('boss', 'boss@example.com', 'pw')
        self.client.force_login(self.user)

    def image(self, mode, fmt, name):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        buf = BytesIO()
        color = (200, 30, 30, 0) if mode == 'RGBA' else (200, 30, 30)
        Image.new(mode, (40, 20), color).save(buf, fmt)
        return SimpleUploadedFile(name, buf.getvalue(), content_type=f'image/{fmt.lower()}')

    def add(self, logo):
        from django.test import override_settings
        with override_settings(MEDIA_ROOT=self.media):
            return self.client.post('/admin/core/partner/add/', {
                'name': 'Новый партнёр', 'description': 'Описание', 'city': 'Казань', 'country': 'Россия',
                'website': 'https://example.com/', 'is_active': 'on', 'order': '5', 'logo': logo,
            }, follow=True)

    def test_add_partner_shows_on_pool_page(self):
        from .models import Partner
        response = self.add(self.image('RGBA', 'PNG', 'logo.png'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Partner.objects.filter(name='Новый партнёр').exists())
        self.assertNotContains(response, 'нет прозрачного фона')
        self.assertContains(self.client.get('/partners/'), 'Новый партнёр')

    def test_warning_for_logo_without_transparency(self):
        response = self.add(self.image('RGB', 'JPEG', 'logo.jpg'))
        self.assertContains(response, 'нет прозрачного фона')

    def test_new_partner_goes_last_by_default(self):
        from .models import Partner
        Partner.objects.create(name='Старый', order=7)
        response = self.client.get('/admin/core/partner/add/')
        self.assertEqual(response.context['adminform'].form.initial['order'], 8)
        self.assertContains(response, 'partner-admin-preview')
