from datetime import date, timedelta
from unittest.mock import patch

from django.db import OperationalError
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, TestCase

from datetime import time

from django.core.exceptions import ValidationError

from .models import (
    AboutSection, ChildAge, Course, CourseSchedule, CourseScheduleDay, CourseTeacher, HealthFeature, PageContent,
    Representative, Teacher,
)
from .utils import (
    format_date_range, format_day_list, format_rub, plural_ru, sentence_case, slugify_ru, split_variant_title,
)
from .views import page_content


def make_course(**kwargs):
    """Курс со всеми обязательными полями; любые можно переопределить"""
    defaults = {
        'title': 'Тестовый курс', 'short_description': 'Кратко о курсе', 'audience': 'Тренерам',
        'program': 'Темы', 'hours': 40, 'course_type': Course.TYPE_ONLINE, 'direction': 'swimming',
        'venue': 'pool', 'skill_level': 'beginner', 'base_price': 10000,
    }
    defaults.update(kwargs)
    return Course.objects.create(**defaults)


class PageContentViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        # БД недоступна и для контактов в шапке и подвале — берутся значения со старого сайта
        patcher = patch('core.models.ContactInfo.objects')
        patcher.start().first.side_effect = OperationalError('db unavailable')
        self.addCleanup(patcher.stop)

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
            slug='seminars',
            title='Тестовый заголовок',
            content='Тестовый текст',
        )

        response = page_content(self.factory.get('/page/seminars/'), 'seminars')

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
        course = make_course()
        CourseTeacher.objects.create(course=course, teacher=second, order=1)
        CourseTeacher.objects.create(course=course, teacher=first, order=0)
        self.assertEqual(course.teacher_list, [first, second])
        self.assertEqual(course.main_teacher, first)
        self.assertEqual(course.teacher_names, 'Наталия Дворяшина, Екатерина Любимова')
        self.assertIn(course, first.courses.all())

    def test_course_without_teacher(self):
        course = make_course(title='Курс без преподавателя')
        self.assertIsNone(course.main_teacher)
        self.assertEqual(course.teacher_names, '')

    def test_course_ordering_by_order_field(self):
        make_course(title='Второй', slug='vtoroj', order=2)
        make_course(title='Первый', slug='pervyj', order=1)
        courses = list(Course.objects.values_list('title', flat=True))
        self.assertEqual(courses[:2], ['Первый', 'Второй'])

    def test_slug_auto_generated(self):
        self.assertEqual(make_course(title='Test Course').slug, 'test-course')

    def test_slug_transliterated_from_russian_and_unique(self):
        first = make_course(title='Грудничковое плавание. Базовый модуль')
        second = make_course(title='Грудничковое плавание. Базовый модуль')
        self.assertEqual(first.slug, 'grudnichkovoe-plavanie-bazovyy-modul')
        self.assertEqual(second.slug, 'grudnichkovoe-plavanie-bazovyy-modul-2')

    def test_lookup_options_seeded_by_migration(self):
        self.assertEqual(list(ChildAge.objects.values_list('code', flat=True)), ['infant', 'early', 'preschool'])
        self.assertEqual(list(HealthFeature.objects.values_list('code', flat=True)),
                         ['normotypical', 'special_care', 'pregnant'])

    def test_document_price_required_when_option_enabled(self):
        course = make_course(has_diploma=True)
        with self.assertRaises(ValidationError) as ctx:
            course.clean()
        self.assertIn('diploma_price', ctx.exception.message_dict)

    def test_document_price_cleared_when_option_disabled(self):
        course = make_course(diploma_price=15000, qualification_certificate_price=17000)
        course.clean()
        self.assertIsNone(course.diploma_price)
        self.assertIsNone(course.qualification_certificate_price)

    def test_documents_list(self):
        course = make_course(base_price=10000, has_qualification_certificate=True,
                             qualification_certificate_price=14000)
        self.assertEqual([(name, price) for name, _, price in course.documents], [
            ('Сертификат о прохождении курса', 10000),
            ('Удостоверение о повышении квалификации', 14000),
        ])

    def test_qualification_course_gives_certificate_of_qualification_only(self):
        course = make_course(base_price=12900, main_document=Course.DOC_QUALIFICATION)
        self.assertEqual(course.documents, [
            ('Удостоверение о повышении квалификации', 'с занесением данных в ФИС ФРДО', 12900),
        ])
        course.has_qualification_certificate, course.qualification_certificate_price = True, 14000
        with self.assertRaises(ValidationError):
            course.clean()  # удостоверение уже основной документ — второй вариант с ним не нужен

    def test_is_qualification_course(self):
        from .utils import is_qualification_course
        self.assertTrue(is_qualification_course('Плавание. ПОВЫШЕНИЕ КВАЛИФИКАЦИИ'))
        self.assertTrue(is_qualification_course('Плавание', 'Повышение квалификации'))
        self.assertFalse(is_qualification_course('Плавание. Семинар', 'Пакет «Специалист»'))

    def test_required_course_cannot_be_self_or_cycle(self):
        a = make_course(title='A')
        b = make_course(title='B', required_course=a)
        a.required_course = a
        with self.assertRaises(ValidationError):
            a.clean()
        a.required_course = b  # A → B → A
        with self.assertRaises(ValidationError):
            a.clean()
        Course.objects.get(pk=b.pk).clean()  # B → A без обратной ссылки — нормально

    def test_member_price_is_base_minus_20_percent(self):
        self.assertEqual(make_course(base_price=22800).member_price, 18240)
        self.assertEqual(make_course(base_price=5700).member_price, 4560)
        self.assertIsNone(Course(base_price=None).member_price)

    def test_alumni_price_is_base_minus_10_percent(self):
        self.assertEqual(make_course(base_price=22800).alumni_price, 20520)
        self.assertEqual(make_course(base_price=5700).alumni_price, 5130)
        self.assertIsNone(Course(base_price=None).alumni_price)

    def test_hours_label_plural(self):
        self.assertEqual(make_course(hours=21).hours_label, '21 учебный час')
        self.assertEqual(make_course(hours=3).hours_label, '3 учебных часа')
        self.assertEqual(make_course(hours=80).hours_label, '80 учебных часов')


class CourseScheduleTests(TestCase):
    def schedule(self, course_type, **kwargs):
        course = make_course(course_type=course_type)
        return CourseSchedule(course=course, format='group', **kwargs)

    def test_online_requires_dates_and_time(self):
        with self.assertRaises(ValidationError) as ctx:
            self.schedule(Course.TYPE_ONLINE, access_days=14).clean()
        self.assertEqual(set(ctx.exception.message_dict),
                         {'start_date', 'end_date', 'time_from', 'time_to'})

    def test_in_person_clears_distance_and_materials_fields(self):
        s = self.schedule(Course.TYPE_IN_PERSON, start_date=date(2026, 11, 1), end_date=date(2026, 11, 3),
                          time_from=time(10), time_to=time(18), access_days=14,
                          materials_from=date(2026, 10, 1), materials_to=date(2026, 12, 1))
        s.clean()
        self.assertIsNone(s.access_days)
        self.assertIsNone(s.materials_from)

    def test_blended_requires_materials_period(self):
        with self.assertRaises(ValidationError) as ctx:
            self.schedule(Course.TYPE_BLENDED, start_date=date(2026, 11, 1), end_date=date(2026, 11, 30),
                          time_from=time(10), time_to=time(18)).clean()
        self.assertEqual(set(ctx.exception.message_dict), {'materials_from', 'materials_to'})

    def test_distance_has_no_dates(self):
        s = self.schedule(Course.TYPE_DISTANCE, start_date=date(2026, 11, 1), end_date=date(2026, 11, 30),
                          access_days=30)
        s.clean()
        self.assertIsNone(s.start_date)
        self.assertEqual(s.date_label, 'Доступ 30 дней')
        with self.assertRaises(ValidationError):
            self.schedule(Course.TYPE_DISTANCE).clean()

    def test_end_before_start_and_time_order(self):
        with self.assertRaises(ValidationError) as ctx:
            self.schedule(Course.TYPE_ONLINE, start_date=date(2026, 11, 5), end_date=date(2026, 11, 1),
                          time_from=time(18), time_to=time(10)).clean()
        self.assertEqual(set(ctx.exception.message_dict), {'end_date', 'time_to'})

    def test_course_without_type(self):
        with self.assertRaises(ValidationError) as ctx:
            self.schedule('').clean()
        self.assertIn('course', ctx.exception.message_dict)

    def test_price_override_and_labels(self):
        s = self.schedule(Course.TYPE_ONLINE, start_date=date(2026, 11, 12), end_date=date(2026, 11, 14),
                          time_from=time(8), time_to=time(18))
        self.assertEqual(s.price, 10000)
        s.price_override = 8000
        self.assertEqual(s.price, 8000)
        self.assertEqual(s.date_label, '12–14 ноября 2026')
        self.assertEqual(s.time_label, '08:00–18:00')


class CourseAdminTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.client.force_login(User.objects.create_superuser('boss', 'boss@example.com', 'pw'))
        self.teacher = Teacher.objects.create(first_name='Иван', last_name='Петров')

    def course_data(self, **extra):
        data = {
            'title': 'Новый курс', 'slug': 'novyy-kurs', 'short_description': 'Кратко',
            'full_description': '', 'audience': 'Тренерам', 'program': 'Темы', 'hours': '16',
            'course_type': 'online', 'direction': 'swimming', 'venue': 'pool', 'skill_level': 'beginner',
            'child_ages': [ChildAge.objects.get(code='infant').pk],
            'health_features': [HealthFeature.objects.get(code='normotypical').pk],
            'main_document': 'certificate', 'base_price': '10000', 'diploma_price': '',
            'qualification_certificate_price': '',
            'required_course': '', 'order': '0', 'is_active': 'on',
            'card': '', 'variant_label': '', 'card_position': '0',
            'course_teachers-TOTAL_FORMS': '1', 'course_teachers-INITIAL_FORMS': '0',
            'course_teachers-MIN_NUM_FORMS': '1', 'course_teachers-MAX_NUM_FORMS': '1000',
            'course_teachers-0-teacher': str(self.teacher.pk), 'course_teachers-0-order': '0',
        }
        data.update(extra)
        return data

    def test_add_course(self):
        response = self.client.post('/admin/core/course/add/', self.course_data(
            has_diploma='on', diploma_price='15000'))
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        course = Course.objects.get(slug='novyy-kurs')
        self.assertEqual(course.diploma_price, 15000)
        self.assertEqual(course.teacher_list, [self.teacher])
        self.assertEqual(list(course.child_ages.values_list('code', flat=True)), ['infant'])

    def test_course_requires_teacher_and_diploma_price(self):
        data = self.course_data(has_diploma='on')
        data['course_teachers-0-teacher'] = ''
        response = self.client.post('/admin/core/course/add/', data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('diploma_price', response.context['adminform'].form.errors)
        self.assertFalse(Course.objects.filter(slug='novyy-kurs').exists())

    def schedule_data(self, course, days=(), **extra):
        data = {
            'course': str(course.pk), 'format': 'group', 'start_date': '2026-11-10', 'end_date': '2026-11-20',
            'materials_from': '2026-11-01', 'materials_to': '2026-12-01', 'access_days': '',
            'time_from': '10:00', 'time_to': '15:00', 'price_override': '', 'comment': '',
            'in_person_days-TOTAL_FORMS': str(len(days)), 'in_person_days-INITIAL_FORMS': '0',
            'in_person_days-MIN_NUM_FORMS': '0', 'in_person_days-MAX_NUM_FORMS': '1000',
        }
        for i, day in enumerate(days):
            data[f'in_person_days-{i}-date'] = day
        data.update(extra)
        return data

    def test_add_blended_schedule_with_in_person_days(self):
        course = make_course(course_type=Course.TYPE_BLENDED)
        response = self.client.post('/admin/core/courseschedule/add/',
                                    self.schedule_data(course, days=['2026-11-12', '2026-11-14']))
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        schedule = CourseSchedule.objects.get(course=course)
        self.assertEqual(schedule.in_person_days_label, '12 и 14 ноября 2026')
        self.assertEqual(schedule.materials_label, '1 ноября – 1 декабря 2026')

    def test_blended_schedule_requires_in_person_days_within_dates(self):
        course = make_course(course_type=Course.TYPE_BLENDED)
        response = self.client.post('/admin/core/courseschedule/add/', self.schedule_data(course))
        self.assertContains(response, 'Укажите хотя бы одну дату очного занятия')
        response = self.client.post('/admin/core/courseschedule/add/',
                                    self.schedule_data(course, days=['2026-12-25']))
        self.assertContains(response, 'в пределах дат курса')
        self.assertFalse(CourseSchedule.objects.exists())

    def test_distance_schedule_keeps_only_access_days(self):
        course = make_course(course_type=Course.TYPE_DISTANCE)
        response = self.client.post('/admin/core/courseschedule/add/',
                                    self.schedule_data(course, days=['2026-11-12'], access_days='30'))
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        schedule = CourseSchedule.objects.get(course=course)
        self.assertIsNone(schedule.start_date)
        self.assertEqual(schedule.access_days, 30)
        self.assertFalse(schedule.in_person_days.exists())

    def test_schedule_form_marks_course_types_for_js(self):
        course = make_course(course_type=Course.TYPE_BLENDED)
        response = self.client.get(f'/admin/core/courseschedule/add/?course={course.pk}')
        self.assertContains(response, 'data-course-type="blended"')
        self.assertContains(response, 'admin-schedule.js')


class CourseDetailTests(TestCase):
    def setUp(self):
        self.course = make_course(
            title='Курс', slug='kurs', short_description='Короткое описание.',
            full_description='Подробности.', has_diploma=True, diploma_price=15000,
        )
        self.course.child_ages.set(ChildAge.objects.filter(code__in=['infant', 'early']))

    def test_page_shows_facts_documents_and_schedule(self):
        CourseSchedule.objects.create(course=self.course, format='group', start_date=date.today(),
                                      end_date=date.today() + timedelta(days=2), time_from=time(10), time_to=time(15))
        CourseSchedule.objects.create(course=self.course, format='group',
                                      start_date=date.today() - timedelta(days=30),
                                      end_date=date.today() - timedelta(days=28))  # прошедшая — не показываем
        response = self.client.get('/education/courses/kurs/')
        self.assertEqual(response.status_code, 200)
        for text in ['Короткое описание.', 'Подробности.', 'Плавание', 'Грудной (0–1 год)', 'Ранний (1–3 года)',
                     'Диплом', '15\u00a0000\u00a0₽', '10:00–15:00', 'Онлайн', 'Сертификат о прохождении курса']:
            self.assertContains(response, text)
        self.assertEqual(len(response.context['schedules']), 1)

    def test_layout_title_prices_and_signup_buttons(self):
        for days in (3, 40):
            CourseSchedule.objects.create(course=self.course, format='group',
                                          start_date=date.today() + timedelta(days=days),
                                          end_date=date.today() + timedelta(days=days + 1),
                                          time_from=time(10), time_to=time(15))
        response = self.client.get('/education/courses/kurs/')
        # название курса — главный заголовок страницы (в шапке — название раздела)
        self.assertContains(response, '<h1 class="course-detail-title">Курс</h1>', html=True)
        self.assertContains(response, 'Образовательные программы и семинары')
        # стоимость и стоимость для членов Ассоциации (−20%)
        self.assertContains(response, '10\u00a0000\u00a0₽')
        self.assertContains(response, '8\u00a0000\u00a0₽')
        # и для тех, кто обучался у нас ранее (−10%)
        self.assertContains(response, '9 000 ₽')
        self.assertContains(response, 'для тех, кто обучался у нас ранее')
        # у документа — «!» с подсказкой про зачёт
        self.assertContains(response, 'data-hint="Документ выдаётся только в случае успешной сдачи зачёта"')
        # по кнопке «Записаться» на каждую ближайшую дату — записывает (cabinet/views.py: enroll)
        self.assertContains(response, 'course-signup-btn', count=2)
        self.assertContains(response, 'action="/cabinet/enroll/"', count=2)
        self.assertContains(response, 'course-program-toggle')

    def test_teacher_photo_and_name_link_to_teacher_page(self):
        teacher = Teacher.objects.create(first_name='Анна', last_name='Швыдко')
        CourseTeacher.objects.create(course=self.course, teacher=teacher)
        response = self.client.get('/education/courses/kurs/')
        # ссылка в боковом блоке и у фото с именем в основном
        self.assertContains(response, 'href="/education/teachers/anna-shvydko/"', count=2)

    def test_no_dates_message(self):
        self.assertContains(self.client.get('/education/courses/kurs/'), 'Даты ближайших потоков пока не объявлены')

    def test_required_course_link(self):
        base = make_course(title='Базовый курс', slug='base')
        self.course.required_course = base
        self.course.save()
        self.assertContains(self.client.get('/education/courses/kurs/'), 'href="/education/courses/base/"')

    def test_inactive_course_404(self):
        Course.objects.filter(pk=self.course.pk).update(is_active=False)
        self.assertEqual(self.client.get('/education/courses/kurs/').status_code, 404)

    def test_legacy_urls_redirect(self):
        self.assertRedirects(self.client.get('/courses/kurs/'), '/education/courses/kurs/', status_code=301)
        self.assertRedirects(self.client.get('/education/courses/kurs/09102026'), '/education/courses/kurs/',
                             status_code=301, fetch_redirect_response=False)
        self.assertRedirects(self.client.get('/courses/'), '/education/courses/', status_code=301)


class TeacherPageTests(TestCase):
    def setUp(self):
        self.teacher = Teacher.objects.create(first_name='Ольга', last_name='Белоцерковская',
                                              patronymic='Ивановна', bio='Педиатр.\n\nАвтор семинаров.')

    def test_slug_generated_from_name_and_unique(self):
        self.assertEqual(self.teacher.slug, 'olga-belotserkovskaya')
        twin = Teacher.objects.create(first_name='Ольга', last_name='Белоцерковская')
        self.assertEqual(twin.slug, 'olga-belotserkovskaya-2')
        self.assertEqual(self.teacher.get_absolute_url(), '/education/teachers/olga-belotserkovskaya/')

    def test_page_shows_bio_and_active_courses(self):
        active = make_course(title='Патронажное искусство', slug='patronage')
        hidden = make_course(title='Скрытый курс', slug='hidden', is_active=False)
        other = make_course(title='Чужой курс', slug='other')
        for course in (active, hidden):
            CourseTeacher.objects.create(course=course, teacher=self.teacher)
        schedule = CourseSchedule.objects.create(course=active, format='group',
                                                 start_date=date.today() + timedelta(days=5),
                                                 end_date=date.today() + timedelta(days=6))
        response = self.client.get('/education/teachers/olga-belotserkovskaya/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ольга Ивановна Белоцерковская')
        self.assertContains(response, '<p>Автор семинаров.</p>', html=True)
        self.assertContains(response, 'href="/education/courses/patronage/"')
        self.assertNotContains(response, hidden.title)
        self.assertNotContains(response, other.title)
        cards = response.context['cards']
        self.assertEqual([card.variants for card in cards], [[active]])
        self.assertContains(response, 'class="course-card"', count=1)  # та же карточка, что на «Программах»
        self.assertContains(response, schedule.date_label)  # ближайшая дата в строке варианта
        self.assertContains(response, '1 программа')

    def test_unknown_teacher_404(self):
        self.assertEqual(self.client.get('/education/teachers/nobody/').status_code, 404)


class IndexViewTests(TestCase):
    def test_index_page_renders_courses(self):
        teacher = Teacher.objects.create(first_name='Иван', last_name='Петров')
        course = make_course(title='Тестовый курс', slug='testovyj-kurs', short_description='Описание курса',
                             hours=40, order=1)
        CourseTeacher.objects.create(course=course, teacher=teacher)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Тестовый курс')
        self.assertContains(response, '40 учебных часов')
        self.assertContains(response, 'Иван <strong>Петров</strong>')  # карточка как на странице «Программы»
        self.assertContains(response, 'class="course-card"', count=1)

    def test_beach_figures_link_to_partner_sites(self):
        response = self.client.get('/')
        self.assertContains(response, 'class="beach-figure beach-figure--whale" href="https://моредетям.рф/"')
        self.assertContains(response, 'class="beach-figure beach-figure--matryoshka" '
                                      'href="https://convent.grudnichkovoe-plavanie.ru/"')

    def test_index_shows_nearest_courses_first(self):
        far = make_course(title='Дальний курс', slug='far', order=1)
        near = make_course(title='Ближний курс', slug='near', order=2)
        CourseSchedule.objects.create(course=far, format='group', start_date=date.today() + timedelta(days=60),
                                      end_date=date.today() + timedelta(days=61))
        CourseSchedule.objects.create(course=near, format='group', start_date=date.today() + timedelta(days=3),
                                      end_date=date.today() + timedelta(days=4))
        cards = self.client.get('/').context['cards']
        self.assertEqual([card.variants for card in cards[:2]], [[near], [far]])

    def test_index_courses_carousel_and_more_button(self):
        for i in range(10):
            make_course(title=f'Курс {i}', slug=f'kurs-{i}', order=i)
        response = self.client.get('/')
        self.assertContains(response, 'class="course-card"', count=8)  # в карусели — 8 ближайших
        self.assertEqual(response.context['more_label'], 'Ещё 2 программы')
        self.assertContains(response, 'Больше курсов')

    def test_representatives_and_partners_carousels(self):
        from .models import Partner
        Representative.objects.create(name='Клуб AquaBaby', city='Алматы', country='Казахстан', phone='+7 (727) 329-33-80')
        Partner.objects.create(name='Дарин', description='Станции дозирования', website='https://darin7.ru/')
        response = self.client.get('/')
        # представители и партнёры (курсов и специалистов в этом тесте нет — их каруселей нет)
        self.assertContains(response, 'class="sea-carousel" data-carousel>', count=2)
        self.assertContains(response, 'Клуб AquaBaby')
        self.assertContains(response, 'href="tel:+77273293380"')
        self.assertContains(response, 'Дарин')
        self.assertContains(response, 'Подробнее о представителях')
        self.assertContains(response, 'Подробнее о партнёрах')
        self.assertContains(response, 'js/sea-carousel.js')

    def test_membership_specialists_carousel(self):
        from .models import Specialist
        for i in range(6):
            Specialist.objects.create(name=f'Специалист {i}', position='Тренер', city='Москва', country='Россия')
        response = self.client.get('/')
        self.assertContains(response, 'sea-card sea-card--person', count=6)  # все активные, не только 4

    def test_index_page_renders_without_courses(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Обучающие программы')


class TimetableCalendarTests(TestCase):
    def setUp(self):
        teacher = Teacher.objects.create(first_name='Иван', last_name='Петров')
        self.course = make_course(title='Курс в календаре', slug='kurs-v-kalendare', hours=24,
                                  course_type=Course.TYPE_BLENDED)
        CourseTeacher.objects.create(course=self.course, teacher=teacher)

    def get_events(self):
        response = self.client.get('/page/timetable/')
        self.assertEqual(response.status_code, 200)
        return response.context['calendar_events']

    def test_schedule_becomes_calendar_event(self):
        schedule = CourseSchedule.objects.create(
            course=self.course, format='group', start_date=date(2026, 11, 12), end_date=date(2026, 11, 14),
            time_from=time(10), time_to=time(15), price_override=9000, comment='Москва',
        )
        CourseScheduleDay.objects.create(schedule=schedule, date=date(2026, 11, 13))
        events = self.get_events()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event['title'], 'Курс в календаре')
        self.assertEqual(event['start'], '2026-11-12')
        self.assertEqual(event['end'], '2026-11-15')  # конец невключительный
        self.assertEqual(event['url'], '/education/courses/kurs-v-kalendare/')
        props = event['extendedProps']
        self.assertEqual(props['teacher'], 'Иван Петров')
        self.assertEqual(props['dates'], '12–14 ноября 2026')
        self.assertEqual(props['inPersonDays'], '13 ноября 2026')
        self.assertEqual(props['time'], '10:00–15:00')
        self.assertEqual(props['price'], '9\u00a0000\u00a0₽')
        self.assertEqual(props['hours'], '24 учебных часа')

    def test_distance_courses_listed_separately(self):
        distance = make_course(title='Дистанционный курс', slug='dist', course_type=Course.TYPE_DISTANCE)
        CourseSchedule.objects.create(course=distance, format='group', access_days=14)
        response = self.client.get('/page/timetable/')
        self.assertEqual(response.context['calendar_events'], [])
        self.assertContains(response, 'Дистанционное обучение')
        self.assertContains(response, 'Доступ 14 дней')

    def test_inactive_course_hidden(self):
        CourseSchedule.objects.create(course=self.course, format='group', start_date=date(2026, 5, 5),
                                      end_date=date(2026, 5, 5))
        Course.objects.filter(pk=self.course.pk).update(is_active=False)
        self.assertEqual(self.get_events(), [])

    def test_calendar_assets_only_on_timetable(self):
        self.assertContains(self.client.get('/page/timetable/'), 'fullcalendar.global.js')
        self.assertNotContains(self.client.get('/page/contacts/'), 'fullcalendar.global.js')


class FormattingTests(SimpleTestCase):
    def test_format_date_range(self):
        self.assertEqual(format_date_range(date(2026, 11, 30), date(2026, 12, 2)), '30 ноября – 2 декабря 2026')
        self.assertEqual(format_date_range(date(2026, 12, 30), date(2027, 1, 2)),
                         '30 декабря 2026 – 2 января 2027')
        self.assertEqual(format_date_range(date(2026, 5, 5), date(2026, 5, 5)), '5 мая 2026')

    def test_format_day_list(self):
        self.assertEqual(format_day_list([date(2026, 12, 10), date(2026, 12, 3), date(2026, 12, 4)]),
                         '3, 4 и 10 декабря 2026')
        self.assertEqual(format_day_list([date(2026, 11, 30), date(2026, 12, 2)]), '30 ноября и 2 декабря 2026')
        self.assertEqual(format_day_list([date(2026, 12, 30), date(2027, 1, 2)]), '30 декабря 2026 и 2 января 2027')

    def test_plural_rub_and_slug(self):
        self.assertEqual([plural_ru(n, ('день', 'дня', 'дней')) for n in (1, 2, 5, 11, 21, 104)],
                         ['день', 'дня', 'дней', 'дней', 'день', 'дня'])
        self.assertEqual(format_rub(22800), '22\u00a0800\u00a0₽')
        self.assertEqual(format_rub(None), '')
        self.assertEqual(slugify_ru('Щука и ёж: «Синдром Дауна»'), 'schuka-i-ezh-sindrom-dauna')


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

    def test_split_description(self):
        from core.management.commands.import_old_courses import split_description
        self.assertEqual(split_description('Коротко.'), ('Коротко.', ''))
        text = 'Первое предложение. ' * 10 + 'Хвост.'
        short, full = split_description(text, limit=60)
        self.assertEqual(short, 'Первое предложение. Первое предложение. Первое предложение.')
        self.assertTrue(full.startswith('Первое предложение.'))
        self.assertEqual(short + ' ' + full, text.strip())

    def test_price_and_type_from_old_site(self):
        from core.management.commands.import_old_courses import location_kind, parse_full_price
        self.assertEqual(parse_full_price('22 800 руб, для членов Ассоциации — 18 240 руб'), 22800)
        self.assertIsNone(parse_full_price(''))
        self.assertEqual(location_kind('Онлайн — ZOOM'), Course.TYPE_ONLINE)
        self.assertEqual(location_kind('Дистанционное обучение — в удобное для вас время'), Course.TYPE_DISTANCE)
        self.assertEqual(location_kind('Москва, ул. Малыгина, 1 стр. 2'), Course.TYPE_IN_PERSON)

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


class CourseFilterTests(TestCase):
    def setUp(self):
        self.teacher = Teacher.objects.create(first_name='Анна', last_name='Швыдко')
        self.online = make_course(title='Онлайн-курс', slug='online', hours=6, course_type=Course.TYPE_ONLINE,
                                  direction='management')
        self.pool = make_course(title='Очный курс', slug='pool', hours=40, course_type=Course.TYPE_IN_PERSON,
                                direction='swimming', skill_level='advanced')
        self.distance = make_course(title='Дистанционный курс', slug='dist', hours=80,
                                    course_type=Course.TYPE_DISTANCE, venue='home')
        CourseTeacher.objects.create(course=self.pool, teacher=self.teacher)
        self.pool.child_ages.set(ChildAge.objects.filter(code='infant'))
        self.distance.child_ages.set(ChildAge.objects.filter(code__in=['infant', 'early']))

    def titles(self, query):
        response = self.client.get('/education/courses/' + query)
        self.assertEqual(response.status_code, 200)
        return sorted(c.title for c in response.context['courses'])

    def test_no_filters_shows_all(self):
        self.assertEqual(len(self.titles('')), 3)

    def test_each_filter(self):
        self.assertEqual(self.titles('?type=online'), ['Онлайн-курс'])
        self.assertEqual(self.titles('?hours=upto10'), ['Онлайн-курс'])
        self.assertEqual(self.titles('?hours=31-60&hours=over60'), ['Дистанционный курс', 'Очный курс'])
        self.assertEqual(self.titles('?teacher=anna-shvydko'), ['Очный курс'])
        self.assertEqual(self.titles('?age=infant'), ['Дистанционный курс', 'Очный курс'])
        self.assertEqual(self.titles('?direction=management'), ['Онлайн-курс'])
        self.assertEqual(self.titles('?venue=home'), ['Дистанционный курс'])
        self.assertEqual(self.titles('?skill=advanced'), ['Очный курс'])

    def test_groups_combine_with_and(self):
        self.assertEqual(self.titles('?age=infant&type=distance'), ['Дистанционный курс'])
        response = self.client.get('/education/courses/?type=online&skill=advanced')
        self.assertContains(response, 'Ничего не нашлось')

    def test_age_filter_no_duplicates(self):
        self.assertEqual(self.titles('?age=infant&age=early'), ['Дистанционный курс', 'Очный курс'])

    def test_courses_are_cards_with_teacher_links(self):
        response = self.client.get('/education/courses/')
        self.assertContains(response, 'class="course-card"', count=3)
        self.assertContains(response, 'Анна <strong>Швыдко</strong>')  # «таблетка»: имя, под ним фамилия
        self.assertContains(response, 'href="/education/teachers/anna-shvydko/"')
        self.assertContains(response, 'name="type"')

    def test_timetable_filters_calendar_and_distance_list(self):
        CourseSchedule.objects.create(course=self.online, format='group', start_date=date(2026, 11, 3),
                                      end_date=date(2026, 11, 3))
        CourseSchedule.objects.create(course=self.pool, format='group', start_date=date(2026, 11, 10),
                                      end_date=date(2026, 11, 12))
        CourseSchedule.objects.create(course=self.distance, format='group', access_days=30)
        response = self.client.get('/page/timetable/?type=online')
        self.assertEqual([e['title'] for e in response.context['calendar_events']], ['Онлайн-курс'])
        self.assertEqual(response.context['distance_schedules'], [])
        response = self.client.get('/page/timetable/')
        self.assertEqual(len(response.context['calendar_events']), 2)
        self.assertEqual(len(response.context['distance_schedules']), 1)
        self.assertContains(response, 'course-filters')


class CourseCardTests(TestCase):
    """Карточка курса: варианты одного курса на странице «Программы» — одна карточка"""

    def setUp(self):
        from .models import CourseCard
        self.card = CourseCard.objects.create(title='Патронаж', order=10)
        self.student = make_course(title='Патронаж. Пакет «Студент»', slug='patronage-student', order=1,
                                   card=self.card, card_position=0, variant_label='Пакет «Студент»',
                                   short_description='',  # описания нет — карточка возьмёт его у «Специалиста»
                                   course_type=Course.TYPE_DISTANCE, direction='land', hours=20)
        self.specialist = make_course(title='Патронаж. Пакет «Специалист»', slug='patronage-specialist', order=2,
                                      card=self.card, card_position=1, variant_label='Пакет «Специалист»',
                                      short_description='Описание патронажа.',
                                      course_type=Course.TYPE_DISTANCE, direction='land', hours=20)
        self.other = make_course(title='ДРУГОЙ КУРС', slug='other', direction='management')
        self.teacher = Teacher.objects.create(first_name='Ольга', last_name='Белоцерковская')
        CourseTeacher.objects.create(course=self.student, teacher=self.teacher)
        CourseTeacher.objects.create(course=self.specialist, teacher=self.teacher)

    def get(self, query=''):
        response = self.client.get('/education/courses/' + query)
        self.assertEqual(response.status_code, 200)
        return response

    def test_variants_share_one_card(self):
        response = self.get()
        self.assertContains(response, 'class="course-card"', count=2)
        self.assertContains(response, 'href="/education/courses/patronage-specialist/"')
        self.assertContains(response, '2 программы · 3 варианта')
        card = next(c for c in response.context['cards'] if c.obj == self.card)
        self.assertEqual([c.slug for c in card.variants], ['patronage-student', 'patronage-specialist'])
        self.assertEqual(card.teachers, [self.teacher])  # преподаватель не дублируется
        self.assertEqual(card.description, 'Описание патронажа.')
        self.assertEqual(self.card.short_description, 'Описание патронажа.')

    def test_description_course_chosen_explicitly(self):
        self.card.description_course = self.student
        self.card.save()
        self.student.short_description = 'Своё описание.'
        self.student.save()
        self.assertContains(self.get(), 'Своё описание.')

    def test_sections_by_direction(self):
        response = self.get()
        self.assertEqual([s.label for s in response.context['sections']], ['Сухопутные', 'Администрирование'])
        from .views import DIRECTION_SECTION_ORDER
        self.assertEqual(sorted(DIRECTION_SECTION_ORDER), sorted(code for code, _ in Course.DIRECTION_CHOICES))
        self.assertContains(response, 'course-dir--land')
        self.assertContains(response, '1 программа')

    def test_course_without_card_gets_own_card_with_softened_title(self):
        self.assertContains(self.get(), 'Другой курс')

    def test_hidden_card_not_shown(self):
        self.card.is_active = False
        self.card.save()
        response = self.get()
        self.assertNotContains(response, 'patronage-student')
        self.assertEqual(len(response.context['cards']), 1)

    def test_variant_found_by_filter_stays_under_card(self):
        self.specialist.hours = 80
        self.specialist.save()
        response = self.get('?hours=over60')
        self.assertContains(response, 'class="course-card"', count=1)
        self.assertContains(response, '>Патронаж<')
        self.assertNotContains(response, 'href="/education/courses/patronage-student/"')

    def test_search_is_case_insensitive_and_matches_card_title(self):
        self.assertEqual(len(self.get('?q=ПАТРОНАЖ').context['cards']), 1)
        self.assertEqual(len(self.get('?q=другой').context['cards']), 1)
        self.assertEqual(len(self.get('?q=описание%20патронажа').context['cards']), 1)
        response = self.get('?q=патронаж')
        self.assertEqual(dict(response.context['active_filters']), {'«патронаж»': '/education/courses/'})

    def test_sort_by_title(self):
        make_course(title='Аквагимнастика', slug='aqua', direction='management', order=99)
        titles = [c.title for c in self.get('?sort=title').context['sections'][1].cards]
        self.assertEqual(titles, ['Аквагимнастика', 'Другой курс'])
        titles = [c.title for c in self.get().context['sections'][1].cards]
        self.assertEqual(titles, ['Другой курс', 'Аквагимнастика'])  # по умолчанию — порядок из админки

    def test_active_filter_chip_removes_only_its_value(self):
        response = self.get('?type=distance&type=online')
        chips = dict(response.context['active_filters'])
        self.assertEqual(chips['Дистанционный'], '/education/courses/?type=online')


class CourseCardAdminTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.client.force_login(User.objects.create_superuser('boss', 'boss@example.com', 'pw'))
        self.seminar = make_course(title='Плавание. Семинар', slug='swim-seminar')
        self.qualification = make_course(title='Плавание. Повышение квалификации', slug='swim-pk')

    def test_add_card_with_courses(self):
        from .models import CourseCard
        response = self.client.post('/admin/core/coursecard/add/', {
            'title': 'Плавание', 'courses': [self.seminar.pk, self.qualification.pk],
            'description_course': self.qualification.pk, 'order': '0', 'is_active': 'on',
            'courses-TOTAL_FORMS': '0', 'courses-INITIAL_FORMS': '0',
            'courses-MIN_NUM_FORMS': '0', 'courses-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(response.status_code, 302, response.content.decode()[:600])
        card = CourseCard.objects.get(title='Плавание')
        self.assertEqual(card.ordered_courses, [self.seminar, self.qualification])
        self.assertEqual(card.description_source, self.qualification)

    def test_description_course_must_be_in_card(self):
        other = make_course(title='Чужой курс', slug='alien')
        response = self.client.post('/admin/core/coursecard/add/', {
            'title': 'Плавание', 'courses': [self.seminar.pk], 'description_course': other.pk,
            'order': '0', 'is_active': 'on',
            'courses-TOTAL_FORMS': '0', 'courses-INITIAL_FORMS': '0',
            'courses-MIN_NUM_FORMS': '0', 'courses-MAX_NUM_FORMS': '1000',
        })
        self.assertContains(response, 'Выберите курс, включённый в эту карточку')


class LegacyCardsTests(TestCase):
    def test_mapping_is_consistent(self):
        from core.legacy_cards import LEGACY_CARDS
        from core.legacy_directions import LEGACY_DIRECTIONS
        slugs = [slug for _, members in LEGACY_CARDS for slug, _ in members]
        self.assertEqual(len(slugs), len(set(slugs)), 'курс не может быть в двух карточках')
        for title, members in LEGACY_CARDS:
            directions = {LEGACY_DIRECTIONS.get(slug) for slug, _ in members}
            self.assertEqual(len(directions), 1, f'у курсов карточки «{title}» разные направления')

    def test_assign_course_cards(self):
        from core.legacy_cards import assign_course_cards
        from .models import CourseCard
        pk = make_course(title='Грудничковое плавание. Работа в бассейне. Повышение квалификации',
                         slug='gp-base-pool1onl')
        seminar = make_course(title='Грудничковое плавание. Базовый модуль. Работа в бассейне. Семинар.',
                              slug='gp-base-pool3')
        lone = make_course(title='Новый курс', slug='brand-new')
        self.assertEqual(assign_course_cards(Course, CourseCard), 2)
        card = CourseCard.objects.get(title='Грудничковое плавание. Базовый модуль. Работа в бассейне')
        self.assertEqual(card.ordered_courses, [seminar, pk])
        self.assertEqual([c.variant_label for c in card.ordered_courses], ['Семинар', 'Повышение квалификации'])
        lone.refresh_from_db()
        self.assertEqual(lone.card.title, 'Новый курс')
        self.assertEqual(assign_course_cards(Course, CourseCard), 0)  # повторный запуск ничего не меняет


class VariantTitleTests(SimpleTestCase):
    def test_split_variant_title(self):
        self.assertEqual(split_variant_title('Недоношенные дети. Пакет "СТУДЕНТ"'),
                         ('Недоношенные дети', 'Пакет «Студент»'))
        self.assertEqual(split_variant_title('ЧАСТЬ 2. ПАКЕТ СПЕЦАЛИСТ'), ('ЧАСТЬ 2', 'Пакет «Специалист»'))
        self.assertEqual(split_variant_title('Плавание. Повышение квалификации.'),
                         ('Плавание', 'Повышение квалификации'))
        self.assertEqual(split_variant_title('Гимнастика в воде. Семинар.'), ('Гимнастика в воде', 'Семинар'))
        self.assertEqual(split_variant_title('Психосоматика (РАС)'), ('Психосоматика (РАС)', ''))

    def test_sentence_case(self):
        self.assertEqual(sentence_case('ГИДРОРЕАБИЛИТАЦИЯ ДЕТЕЙ. ВВЕДЕНИЕ'), 'Гидрореабилитация детей. Введение')
        self.assertEqual(sentence_case('Обычный Заголовок'), 'Обычный Заголовок')


class LegacyAttributesTests(TestCase):
    """Характеристики курсов для фильтров (core/legacy_attributes.py)"""

    def test_mapping_uses_known_codes_and_courses(self):
        from core.legacy_attributes import LEGACY_ATTRIBUTES, LEGACY_REQUIRED
        from core.legacy_cards import LEGACY_CARDS
        known = {slug for _, members in LEGACY_CARDS for slug, _ in members}
        self.assertEqual(set(LEGACY_ATTRIBUTES), known, 'характеристики заданы для всех курсов старого сайта')
        self.assertTrue(set(LEGACY_REQUIRED) | set(LEGACY_REQUIRED.values()) <= known)
        venues, skills = dict(Course.VENUE_CHOICES), dict(Course.SKILL_CHOICES)
        for slug, attrs in LEGACY_ATTRIBUTES.items():
            self.assertIn(attrs['venue'], venues, slug)
            self.assertIn(attrs['skill'], skills, slug)
            self.assertTrue(set(attrs['ages']) <= {'infant', 'early', 'preschool'}, slug)
            self.assertTrue(set(attrs['health']) <= {'normotypical', 'special_care', 'pregnant'}, slug)

    def test_fills_only_empty_values(self):
        from core.legacy_attributes import fill_course_attributes
        part1 = make_course(title='Патронаж. Часть 1', slug='nursing-art-basic2', venue='', skill_level='')
        part2 = make_course(title='Патронаж. Часть 2', slug='advanced', venue='gym', skill_level='')
        speech = make_course(title='Речь', slug='speech', audience='', short_description='Своё описание')
        self.assertEqual(fill_course_attributes(Course, ChildAge, HealthFeature), 3)

        part1.refresh_from_db()
        self.assertEqual((part1.venue, part1.skill_level), ('home', 'beginner'))
        self.assertEqual(list(part1.child_ages.values_list('code', flat=True)), ['infant'])
        part2.refresh_from_db()
        self.assertEqual(part2.venue, 'gym')  # правка из админки не затирается
        self.assertEqual(part2.required_course, part1)
        speech.refresh_from_db()
        self.assertEqual(speech.short_description, 'Своё описание')
        self.assertTrue(speech.audience)

        part1.child_ages.set([ChildAge.objects.get(code='preschool')])
        fill_course_attributes(Course, ChildAge, HealthFeature)
        self.assertEqual(list(part1.child_ages.values_list('code', flat=True)), ['preschool'])


class CourseDetailVariantsTests(TestCase):
    def test_variant_switch_links_other_variants_of_card(self):
        from .models import CourseCard
        card = CourseCard.objects.create(title='Плавание')
        seminar = make_course(title='Плавание. Семинар', slug='swim-seminar', card=card, card_position=0,
                              variant_label='Семинар')
        make_course(title='Плавание. ПК', slug='swim-pk', card=card, card_position=1,
                    variant_label='Повышение квалификации')
        response = self.client.get(seminar.get_absolute_url())
        self.assertContains(response, '<span class="course-variant is-current" aria-current="page">Семинар</span>',
                            html=True)
        self.assertContains(response, 'href="/education/courses/swim-pk/"')

    def test_no_switch_for_single_course(self):
        course = make_course(title='Одиночный курс', slug='single')
        self.assertNotContains(self.client.get(course.get_absolute_url()), 'course-variant-switch')


class ContactsPageTests(TestCase):
    def test_page_shows_contacts_from_admin_record(self):
        from .models import ContactInfo
        info = ContactInfo.objects.get()  # создана миграцией из данных старого сайта
        self.assertEqual(info.inn, '7716804870')
        info.phone_education = '+7 (999) 123-45-67'
        info.save()
        response = self.client.get('/page/contacts/')
        self.assertContains(response, 'href="tel:+79991234567"')
        self.assertContains(response, 'Улица Малыгина, 1')  # как добраться
        self.assertContains(response, 'yandex.ru/map-widget')
        self.assertContains(response, 'href="https://vk.com/plavaniegrud"')
        # телефон для записи на странице курса — тот же
        course = make_course(title='Курс', slug='kurs')
        self.assertContains(self.client.get(course.get_absolute_url()), '+7 (999) 123-45-67')

    def test_address_and_map_point(self):
        from decimal import Decimal

        from .contact_defaults import MAP_POINT
        from .models import ContactInfo
        info = ContactInfo.objects.get()  # исправлена миграцией 0029
        self.assertEqual(info.address, 'Москва, улица Малыгина, дом 1, строение 2')
        self.assertEqual(info.postal_address, '129346, Москва, улица Малыгина, дом 1, строение 2')
        self.assertEqual((info.map_lat, info.map_lng), (Decimal(str(MAP_POINT['map_lat'])), Decimal(str(MAP_POINT['map_lng']))))
        response = self.client.get('/page/contacts/')
        point = f"{MAP_POINT['map_lng']},{MAP_POINT['map_lat']}"
        self.assertContains(response, f'll={point}&amp;z=17&amp;pt={point},pm2rdl')  # метка на здании
        info.map_lat = info.map_lng = None
        info.save()
        response = self.client.get('/page/contacts/')  # без координат — поиск по адресу
        self.assertContains(response, 'map-widget/v1/?text=')
        self.assertContains(self.client.get('/page/info/'), 'улица Малыгина, дом 1, строение 2')

    def test_falls_back_to_old_site_contacts_without_record(self):
        from .models import ContactInfo
        ContactInfo.objects.all().delete()
        response = self.client.get('/page/contacts/')
        self.assertContains(response, 'info.babyswim@gmail.com')
        self.assertContains(response, 'href="https://t.me/babyswimming_association"')

    def test_admin_has_single_record(self):
        from django.contrib.auth.models import User
        from .models import ContactInfo
        self.client.force_login(User.objects.create_superuser('boss', 'boss@example.com', 'pw'))
        response = self.client.get('/admin/core/contactinfo/')
        self.assertRedirects(response, f'/admin/core/contactinfo/{ContactInfo.objects.get().pk}/change/')
        self.assertEqual(self.client.get('/admin/core/contactinfo/add/').status_code, 403)


class TeachersListTests(TestCase):
    def setUp(self):
        self.anna = Teacher.objects.create(first_name='Анна', last_name='Швыдко')
        self.olga = Teacher.objects.create(first_name='Ольга', last_name='Белоцерковская')
        self.idle = Teacher.objects.create(first_name='Мария', last_name='Абрамова')  # без открытых курсов
        swim = make_course(title='Плавание', slug='swim', direction='swimming')
        swim_pk = make_course(title='Плавание. ПК', slug='swim-pk', direction='swimming')
        land = make_course(title='Патронаж', slug='land', direction='land')
        from .models import CourseCard
        card = CourseCard.objects.create(title='Плавание')
        Course.objects.filter(pk__in=[swim.pk, swim_pk.pk]).update(card=card)
        for course in (swim, swim_pk):
            CourseTeacher.objects.create(course=course, teacher=self.anna)
        CourseTeacher.objects.create(course=land, teacher=self.olga)

    def test_list_shows_teachers_with_programs_first(self):
        response = self.client.get('/education/teachers/')
        self.assertEqual(response.status_code, 200)
        cards = response.context['cards']
        self.assertEqual([c.teacher for c in cards], [self.olga, self.anna, self.idle])
        anna = cards[1]
        self.assertEqual(anna.programs_label, '1 программа')  # два варианта одной карточки — одна программа
        self.assertEqual([code for code, _, _ in anna.directions], ['swimming'])
        self.assertEqual(cards[2].programs_label, 'Сейчас нет открытых курсов')
        self.assertContains(response, 'href="/education/teachers/anna-shvydko/"')
        self.assertContains(response, '3 преподавателя')

    def test_filter_by_direction(self):
        cards = self.client.get('/education/teachers/?direction=land').context['cards']
        self.assertEqual([c.teacher for c in cards], [self.olga])
        self.assertEqual(len(self.client.get('/education/teachers/?direction=bad').context['cards']), 3)


class NavigationTests(TestCase):
    def test_menu_has_courses_dropdown_with_all_course_pages(self):
        response = self.client.get('/education/teachers/')
        menu = {item.label: item for item in response.context['site_menu']}
        self.assertNotIn('Просвещение', menu)
        courses = menu['Курсы']
        self.assertTrue(courses.active)  # раздел подсвечен на любой странице /education/
        self.assertEqual([c.label for c in courses.children],
                         ['Программы', 'Расписание', 'Преподаватели', 'Выездные семинары',
                          'Почему стоит учиться у нас'])
        self.assertEqual([c.label for c in courses.children if c.active], ['Преподаватели'])
        self.assertContains(response, 'class="top-nav-menu"', count=2)  # Ассоциация и Курсы
        self.assertContains(response, 'href="/education/teachers/" class="is-active" aria-current="page"')

    def test_association_dropdown_and_external_convention(self):
        response = self.client.get('/page/membership/')
        menu = {item.label: item for item in response.context['site_menu']}
        self.assertTrue(menu['Ассоциация'].active)
        self.assertFalse(menu['Курсы'].active)
        self.assertTrue(menu['Конвенция'].external)
        self.assertContains(response, 'href="https://convent.grudnichkovoe-plavanie.ru/" target="_blank" rel="noopener"')


class EducationInfoPageTests(TestCase):
    def test_page_shows_sections_leaders_and_documents(self):
        leader = Teacher.objects.create(first_name='Екатерина', last_name='Любимова')
        response = self.client.get('/page/info/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Основные сведения')
        self.assertContains(response, 'Дата создания')
        self.assertContains(response, 'Генеральный директор')
        # руководитель есть среди преподавателей — ссылка на его страницу (в двух разделах)
        self.assertContains(response, f'href="{leader.get_absolute_url()}"', count=2)
        self.assertContains(response, '/static/documents/signed/rejim_zaniati.pdf.sig')
        self.assertContains(response, 'Аннотация к программе', count=3)  # у «Коррекции» аннотации нет

    def test_all_documents_exist(self):
        from django.contrib.staticfiles import finders
        from core import info_page
        docs = [d for _, group in info_page.REGULATIONS for d in group] + info_page.PAID_SERVICES + [
            info_page.TEACHING_STAFF, info_page.MATERIAL_DOC]
        docs += [d for _, program, annotation in info_page.PROGRAMS for d in (program, annotation) if d]
        paths = [d.path for d in docs] + [d.sig_path for d in docs if d.sig_path]
        paths += [item.path for item in info_page.LICENSES] + [item.thumb for item in info_page.LICENSES]
        self.assertEqual([p for p in paths if not finders.find(p)], [])
        self.assertTrue(all(d.size for d in docs))

    def test_old_site_address_redirects(self):
        self.assertRedirects(self.client.get('/information/'), '/page/info/', status_code=301)
