import shutil
import tempfile
from datetime import date, timedelta
from io import BytesIO

import phonenumbers
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from PIL import Image

from core.models import Course, CourseCard, CourseSchedule, Specialist
from core.tests import make_course

from .models import (
    Certificate, Enrollment, Membership, MembershipApplication, PostponedCourse, Profile, add_years,
)
from .postponed import SESSION_KEY
from .phone import COUNTRY_NAMES, POPULAR_REGIONS, country_choices, format_phone, parse_phone, split_phone, to_e164

PASSWORD = 'Plavanie-2026!'


def registration_data(**overrides):
    """Заполненная форма регистрации; любое поле можно переопределить"""
    data = {
        'last_name': 'Иванова', 'first_name': 'Мария', 'middle_name': 'Сергеевна', 'birth_date': '1990-05-17',
        'phone_country': 'RU', 'phone_number': '916 123-45-67', 'email': 'Maria@Example.com',
        'password1': PASSWORD, 'password2': PASSWORD, 'consent': 'on',
    }
    data.update(overrides)
    return data


def image_upload(name='photo.png', mode='RGBA', size=(1600, 1200), fmt='PNG'):
    buffer = BytesIO()
    Image.new(mode, size, (200, 80, 40, 120) if mode == 'RGBA' else (200, 80, 40)).save(buffer, fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f'image/{fmt.lower()}')


def make_member(email='maria@example.com', **profile):
    user = User.objects.create_user(email, email, PASSWORD, first_name='Мария', last_name='Иванова')
    Profile.objects.create(user=user, **{'birth_date': date(1990, 5, 17), 'phone': '+79161234567', **profile})
    return user


class MediaTestCase(TestCase):
    """Загруженные в тесте файлы — во временной папке"""

    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        settings_override = override_settings(MEDIA_ROOT=self.media)
        settings_override.enable()
        self.addCleanup(settings_override.disable)


class PhoneTests(SimpleTestCase):
    def test_country_list(self):
        self.assertEqual(set(COUNTRY_NAMES) - set(phonenumbers.SUPPORTED_REGIONS), set())
        popular, others = country_choices()  # группы: (название, варианты)
        self.assertEqual(popular[1][0], ('RU', 'Россия +7'))
        self.assertEqual([code for code, _ in popular[1]], POPULAR_REGIONS)
        codes = [code for code, _ in others[1]]
        self.assertEqual(len(codes) + len(POPULAR_REGIONS), len(COUNTRY_NAMES))  # без повторов
        labels = [label for _, label in others[1]]
        self.assertEqual(labels[:2], ['Австралия +61', 'Австрия +43'])  # по алфавиту

    def test_parse_and_format(self):
        self.assertEqual(to_e164(parse_phone('8 (916) 123-45-67', 'RU')), '+79161234567')  # с восьмёркой
        self.assertEqual(to_e164(parse_phone('+375 29 491-19-11', 'RU')), '+375294911911')  # «+» важнее страны
        self.assertIsNone(parse_phone('123', 'RU'))
        self.assertIsNone(parse_phone('916 123-45-67', 'BY'))  # российский номер — не белорусский
        self.assertEqual(format_phone('+79161234567'), '+7 916 123-45-67')
        self.assertEqual(split_phone('+77012345678'), ('KZ', '701 234 5678'))  # +7 — и Казахстан


class RegistrationTests(MediaTestCase):
    def register(self, **overrides):
        return self.client.post('/cabinet/register/', registration_data(**overrides))

    def test_page(self):
        response = self.client.get('/cabinet/register/')
        self.assertContains(response, 'name="phone_country"')
        self.assertContains(response, '<option value="RU" data-example="912 345-67-89" selected>Россия +7</option>',
                            html=True)
        self.assertContains(response, 'name="phone_number"')
        self.assertContains(response, 'Отчество (второе имя)')
        self.assertContains(response, 'name="consent"')

    def test_registration_creates_user_and_profile_and_logs_in(self):
        response = self.register()
        self.assertRedirects(response, '/cabinet/', fetch_redirect_response=False)
        user = User.objects.get()
        self.assertEqual((user.username, user.email), ('maria@example.com', 'maria@example.com'))
        self.assertEqual((user.last_name, user.first_name), ('Иванова', 'Мария'))
        self.assertTrue(user.check_password(PASSWORD))
        profile = user.profile
        self.assertEqual(profile.middle_name, 'Сергеевна')
        self.assertEqual(profile.birth_date, date(1990, 5, 17))
        self.assertEqual(profile.phone, '+79161234567')
        self.assertFalse(profile.avatar)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        page = self.client.get('/cabinet/courses/')
        self.assertContains(page, 'Вы зарегистрировались')
        self.assertContains(page, 'Иванова Мария Сергеевна')

    def test_middle_name_and_photo_are_optional(self):
        self.register(middle_name='')
        self.assertEqual(Profile.objects.get().middle_name, '')

    def test_country_city_and_about_at_registration(self):
        self.register(country='Беларусь', city='Минск', about='Инструктор по плаванию')
        profile = Profile.objects.get()
        self.assertEqual((profile.country, profile.city, profile.about), ('Беларусь', 'Минск', 'Инструктор по плаванию'))
        self.client.logout()
        response = self.client.get('/cabinet/register/')
        self.assertContains(response, '<option value="" selected>Не указана</option>', html=True)

    def test_photo_is_shrunk_to_jpeg_without_original_name(self):
        data = registration_data()
        data['avatar'] = image_upload('Мария паспорт.png')
        self.client.post('/cabinet/register/', data)
        avatar = Profile.objects.get().avatar
        self.assertRegex(avatar.name, r'^avatars/[0-9a-f]{32}\.jpg$')
        with Image.open(avatar.path) as image:
            self.assertEqual((image.format, image.mode), ('JPEG', 'RGB'))
            self.assertEqual(max(image.size), 600)

    def test_not_an_image_is_rejected(self):
        data = registration_data()
        data['avatar'] = SimpleUploadedFile('photo.jpg', b'not an image', content_type='image/jpeg')
        response = self.client.post('/cabinet/register/', data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors['avatar'])
        self.assertFalse(User.objects.exists())

    def test_same_email_in_other_case_is_taken(self):
        make_member('maria@example.com')
        response = self.register(email='MARIA@example.com')
        self.assertContains(response, 'С этим email уже зарегистрировались')
        self.assertEqual(User.objects.count(), 1)

    def test_wrong_phone_for_country_shows_example(self):
        response = self.register(phone_country='BY', phone_number='123')
        self.assertContains(response, 'для выбранной страны он выглядит так: +375 29 491-19-11')
        self.assertContains(response, 'aria-invalid="true"', count=1)  # подсвечен номер, а не список стран
        self.assertFalse(User.objects.exists())

    def test_phone_with_plus_and_other_country(self):
        self.register(phone_country='RU', phone_number='+375 29 491-19-11')
        self.assertEqual(Profile.objects.get().phone, '+375294911911')

    def test_unknown_country_is_rejected(self):
        response = self.register(phone_country='XX')
        self.assertTrue(response.context['form'].errors['phone'])

    def test_birth_date_must_be_in_past(self):
        response = self.register(birth_date=(timezone.localdate() + timedelta(days=1)).isoformat())
        self.assertContains(response, 'Дата рождения должна быть в прошлом.')

    def test_password_rules(self):
        response = self.register(password1='12345678', password2='12345678')
        self.assertTrue(response.context['form'].errors['password2'])
        response = self.register(password2='Другой-пароль-1')
        self.assertTrue(response.context['form'].errors['password2'])
        self.assertFalse(User.objects.exists())

    def test_consent_is_required(self):
        data = registration_data()
        del data['consent']
        response = self.client.post('/cabinet/register/', data)
        self.assertContains(response, 'Без согласия на обработку данных')
        self.assertFalse(User.objects.exists())

    def test_logged_in_user_goes_to_cabinet(self):
        self.client.force_login(make_member())
        self.assertRedirects(self.client.get('/cabinet/register/'), '/cabinet/', fetch_redirect_response=False)


class LoginTests(TestCase):
    def setUp(self):
        self.user = make_member()

    def test_login_by_email_in_any_case(self):
        response = self.client.post('/cabinet/login/', {'username': 'Maria@EXAMPLE.com', 'password': PASSWORD})
        self.assertRedirects(response, '/cabinet/', fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_wrong_password(self):
        response = self.client.post('/cabinet/login/', {'username': 'maria@example.com', 'password': 'wrong'})
        self.assertContains(response, 'Неверный email или пароль.')

    def test_back_to_requested_page(self):
        response = self.client.get('/cabinet/certificates/')
        self.assertRedirects(response, '/cabinet/login/?next=/cabinet/certificates/')
        response = self.client.post('/cabinet/login/?next=/cabinet/certificates/', {
            'username': 'maria@example.com', 'password': PASSWORD, 'next': '/cabinet/certificates/'})
        self.assertRedirects(response, '/cabinet/certificates/')

    def test_logout(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.post('/cabinet/logout/'), '/')
        self.assertNotIn('_auth_user_id', self.client.session)


class CabinetPagesTests(TestCase):
    PAGES = [
        ('/cabinet/courses/', 'Курсы ассоциации'),
        ('/cabinet/my-courses/upcoming/', 'Мои курсы'),
        ('/cabinet/my-courses/current/', 'Мои курсы'),
        ('/cabinet/my-courses/completed/', 'Мои курсы'),
        ('/cabinet/my-courses/postponed/', 'Мои курсы'),
        ('/cabinet/membership/', 'Моё членство'),
        ('/cabinet/certificates/', 'Мои сертификаты'),
        ('/cabinet/profile/', 'Мой профиль'),
    ]

    def setUp(self):
        self.client.force_login(make_member())

    def test_all_pages_open_with_their_title(self):
        for url, title in self.PAGES:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, f'<h1 class="cabinet-title">{title}</h1>', html=True)
                self.assertContains(response, f'href="{url}" aria-current="page"')

    def test_home_opens_first_section(self):
        self.assertRedirects(self.client.get('/cabinet/'), '/cabinet/courses/')

    def test_menu_is_nested_list_without_numbers(self):
        response = self.client.get('/cabinet/my-courses/postponed/')
        menu = response.context['cabinet_menu']
        self.assertEqual([item.title for item in menu],
                         ['Курсы ассоциации', 'Мои курсы', 'Моё членство', 'Мои сертификаты', 'Мой профиль'])
        self.assertEqual(menu[0].children, [])
        self.assertEqual([child.title for child in menu[1].children],
                         ['Предстоящие', 'Идущие', 'Завершённые', 'Отложенные'])
        self.assertTrue(menu[1].open)  # раздел «Мои курсы» раскрыт: открыт его подраздел
        self.assertContains(response, 'class="cabinet-subnav"', count=1)
        self.assertContains(response, 'logo-baby.svg')

    def test_bottom_tabbar_lists_sections_and_marks_open_one(self):
        response = self.client.get('/cabinet/my-courses/postponed/')
        self.assertContains(response, 'class="cabinet-tabbar-link"', count=4)
        for label in ['Курсы', 'Мои курсы', 'Членство', 'Сертификаты', 'Профиль']:
            self.assertContains(response, f'<span>{label}</span>', html=True)
        # открыт подраздел «Отложенные» — подсвечена вкладка «Мои курсы», но это не её страница
        self.assertContains(response, '<a class="cabinet-tabbar-link is-active" data-tab="my_courses" href="/cabinet/my-courses/">')

    def test_bottom_tabbar_on_all_site_pages_for_logged_in(self):
        for url in ['/', '/education/courses/', '/page/contacts/']:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'class="cabinet-tabbar"')
                self.assertContains(response, 'class="cabinet-tabbar-link"', count=5)  # вне кабинета не подсвечен ни один
        self.client.logout()
        self.assertNotContains(self.client.get('/'), 'cabinet-tabbar')

    def test_pages_need_login(self):
        self.client.logout()
        for url, _ in self.PAGES + [('/cabinet/my-courses/', '')]:
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f'/cabinet/login/?next={url}')

    def test_staff_without_profile(self):
        admin = User.objects.create_superuser('admin', '', PASSWORD)
        self.client.force_login(admin)
        response = self.client.get('/cabinet/profile/')
        self.assertContains(response, '<p class="cabinet-user-name">admin</p>', html=True)


class NavbarButtonTests(TestCase):
    def test_button_between_contacts_and_socials(self):
        html = self.client.get('/page/contacts/').content.decode()
        contacts = html.index('>Контакты</a>')
        button = html.index('class="top-nav-cabinet')
        socials = html.index('class="top-nav-social"')
        self.assertLess(contacts, button)
        self.assertLess(button, socials)

    def test_button_leads_to_login_or_cabinet(self):
        response = self.client.get('/')
        self.assertContains(response, 'href="/cabinet/login/" title="Личный кабинет"')
        self.assertContains(response, 'class="mobile-nav-cabinet" href="/cabinet/login/"')
        self.client.force_login(make_member())
        response = self.client.get('/')
        self.assertContains(response, 'href="/cabinet/" title="Личный кабинет"')


class UserAdminTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('admin', 'admin@example.com', PASSWORD))

    def test_user_page_has_cabinet_sections(self):
        member = make_member()
        page = self.client.get(f'/admin/auth/user/{member.pk}/change/')
        for title in ('Членство в Ассоциации', 'Купленные курсы', 'Сертификаты и удостоверения'):
            self.assertContains(page, title)
        for url in ('/admin/cabinet/membership/', '/admin/cabinet/enrollment/', '/admin/cabinet/certificate/'):
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_users_list_shows_phone(self):
        make_member()
        response = self.client.get('/admin/auth/user/')
        self.assertContains(response, '+7 916 123-45-67')

    def test_profile_inline_normalizes_phone(self):
        member = make_member()
        page = self.client.get(f'/admin/auth/user/{member.pk}/change/')
        self.assertContains(page, 'Данные из регистрации в личном кабинете')
        profile = member.profile
        profile.phone = '8 (903) 142-71-17'
        profile.full_clean()
        self.assertEqual(profile.phone, '+79031427117')


class PostponedTests(TestCase):
    """Сердечко на карточке курса: без входа — в сессии, после входа — в личном кабинете"""

    def setUp(self):
        self.card = CourseCard.objects.create(title='Грудничковое плавание. Базовый модуль')
        self.seminar = make_course(title='Семинар', slug='seminar', card=self.card, card_position=1)
        self.qualification = make_course(title='Повышение', slug='qualification', card=self.card, card_position=2)
        self.single = make_course(title='Аквааэробика для беременных', slug='aqua')

    def toggle(self, course, **headers):
        return self.client.post('/postponed/toggle/', {'course': course.pk}, HTTP_ACCEPT='application/json', **headers)

    def test_anonymous_heart_goes_to_session(self):
        data = self.toggle(self.single).json()
        self.assertEqual(data, {'postponed': True, 'key': f'course-{self.single.pk}', 'count': 1})
        self.assertEqual(self.client.session[SESSION_KEY], [self.single.pk])
        data = self.toggle(self.single).json()
        self.assertEqual((data['postponed'], data['count']), (False, 0))
        self.assertEqual(self.client.session[SESSION_KEY], [])

    def test_variants_of_one_card_are_postponed_together(self):
        self.assertTrue(self.toggle(self.seminar).json()['postponed'])
        data = self.toggle(self.qualification).json()  # вторая строка той же карточки — снимает сердечко
        self.assertEqual((data['postponed'], data['key'], data['count']), (False, f'card-{self.card.pk}', 0))

    def test_heart_on_cards_and_button_in_header(self):
        response = self.client.get('/education/courses/')
        self.assertContains(response, 'class="course-heart"', count=2)
        self.assertContains(response, 'class="top-nav-postponed" href="/education/postponed/" title="Отложенные курсы" '
                                      'data-postponed-link hidden')  # пока ничего не отложено — кнопки не видно
        self.toggle(self.seminar)
        response = self.client.get('/education/courses/')
        self.assertContains(response, 'class="course-heart is-postponed"', count=1)
        self.assertContains(response, f'data-postpone-key="card-{self.card.pk}"')
        self.assertContains(response, 'aria-pressed="true"', count=1)
        self.assertContains(response, 'data-postponed-link>')
        self.assertContains(response, '<span class="top-nav-postponed-count" data-postponed-count>1</span>', html=True)

    def test_public_page_lists_postponed_cards(self):
        self.assertContains(self.client.get('/education/postponed/'), 'Пока ничего не отложено')
        self.toggle(self.single)
        self.toggle(self.qualification)
        response = self.client.get('/education/postponed/')
        cards = response.context['cards']
        self.assertEqual([card.title for card in cards],  # последние отложенные — первыми; карточка — целиком
                         ['Грудничковое плавание. Базовый модуль', 'Аквааэробика для беременных'])
        self.assertEqual(len(cards[0].variants), 2)
        self.assertContains(response, 'хранятся только в этом браузере')

    def test_without_js_returns_to_page(self):
        response = self.client.post('/postponed/toggle/', {'course': self.single.pk, 'next': '/education/courses/?q=аква'})
        self.assertRedirects(response, '/education/courses/?q=%D0%B0%D0%BA%D0%B2%D0%B0', fetch_redirect_response=False)
        response = self.client.post('/postponed/toggle/', {'course': self.single.pk, 'next': 'https://evil.example/'})
        self.assertRedirects(response, '/education/postponed/', fetch_redirect_response=False)

    def test_bad_requests(self):
        self.assertEqual(self.client.get('/postponed/toggle/').status_code, 405)
        self.assertEqual(self.client.post('/postponed/toggle/', {'course': 'abc'}).status_code, 404)
        hidden = make_course(title='Скрытый', slug='hidden', is_active=False)
        self.assertEqual(self.toggle(hidden).status_code, 404)

    def test_logged_in_heart_goes_to_cabinet(self):
        user = make_member()
        self.client.force_login(user)
        self.assertTrue(self.toggle(self.seminar).json()['postponed'])
        self.assertEqual(list(user.postponed_courses.values_list('course_id', flat=True)), [self.seminar.pk])
        response = self.client.get('/education/courses/')
        self.assertNotContains(response, 'top-nav-postponed')  # кнопка «Отложенные» — только без входа
        response = self.client.get('/cabinet/my-courses/postponed/')
        self.assertEqual([card.title for card in response.context['cards']], ['Грудничковое плавание. Базовый модуль'])
        self.assertContains(response, 'class="cabinet-nav-count" data-postponed-count data-postponed-link>1</span>')
        self.assertRedirects(self.client.get('/education/postponed/'), '/cabinet/my-courses/postponed/')
        # старый адрес раздела ведёт на новый
        self.assertRedirects(self.client.get('/cabinet/courses/postponed/'), '/cabinet/my-courses/postponed/',
                             status_code=301)
        # «таблетка» «Отложенные» на «Моих курсах» — с числом отложенных
        tabs = self.client.get('/cabinet/my-courses/upcoming/').context['tabs']
        self.assertEqual((tabs[-1].title, tabs[-1].count), ('Отложенные', 1))

    def test_postponed_before_login_moves_to_cabinet(self):
        user = make_member()
        PostponedCourse.objects.create(user=user, course=self.qualification)
        self.toggle(self.seminar)  # та же карточка — второй раз не добавится
        self.toggle(self.single)
        self.client.post('/cabinet/login/', {'username': 'maria@example.com', 'password': PASSWORD})
        self.assertEqual(sorted(user.postponed_courses.values_list('course_id', flat=True)),
                         sorted([self.qualification.pk, self.single.pk]))
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_postponed_at_registration_moves_to_cabinet(self):
        self.toggle(self.single)
        self.client.post('/cabinet/register/', registration_data())
        user = User.objects.get(username='maria@example.com')
        self.assertEqual(list(user.postponed_courses.values_list('course_id', flat=True)), [self.single.pk])


class CabinetCoursesTests(TestCase):
    def setUp(self):
        self.client.force_login(make_member())

    def test_courses_like_programs_page_with_filters(self):
        make_course(title='Онлайн-курс', slug='online', course_type=Course.TYPE_ONLINE)
        make_course(title='Очный курс', slug='offline', course_type=Course.TYPE_IN_PERSON)
        response = self.client.get('/cabinet/courses/')
        self.assertContains(response, 'class="course-card"', count=2)
        self.assertContains(response, 'class="course-heart"', count=2)
        self.assertContains(response, 'course-filters-wrap course-filters-wrap--panel">')  # фильтры свёрнуты
        self.assertContains(response, 'js/course-filters.js')
        response = self.client.get('/cabinet/courses/?type=online')
        self.assertContains(response, 'class="course-card"', count=1)
        self.assertContains(response, 'course-filters-wrap--panel" open>')  # что-то выбрано — раскрыты
        self.assertEqual(response.context['found_label'], '1 программа')


class MyCoursesTests(MediaTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_member()
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        self.course = make_course(title='Базовый курс', slug='base', main_document=Course.DOC_QUALIFICATION)

    def schedule(self, start_days, end_days=None, course=None):
        """Запись расписания: даты — через столько-то дней от сегодня"""
        return CourseSchedule.objects.create(
            course=course or self.course, format='group', start_date=self.today + timedelta(days=start_days),
            end_date=self.today + timedelta(days=start_days if end_days is None else end_days))

    def enroll(self, start_days, end_days=None):
        return Enrollment.objects.create(user=self.user, schedule=self.schedule(start_days, end_days))

    def test_my_courses_opens_upcoming(self):
        self.assertRedirects(self.client.get('/cabinet/my-courses/'), '/cabinet/my-courses/upcoming/')

    def test_split_by_dates(self):
        self.enroll(5, 7)
        self.enroll(-1, 1)
        self.enroll(0)  # один день — сегодня
        self.enroll(-10, -8)
        response = self.client.get('/cabinet/my-courses/upcoming/')
        self.assertEqual([(tab.title, tab.count) for tab in response.context['tabs']],
                         [('Предстоящие', 1), ('Идущие', 2), ('Завершённые', 1), ('Отложенные', 0)])
        self.assertContains(response, 'Начнётся через 5 дней')
        self.assertContains(response, 'class="course-card enrollment-card"', count=1)
        self.assertContains(self.client.get('/cabinet/my-courses/current/'), 'Идёт, последний день')
        response = self.client.get('/cabinet/my-courses/completed/')
        self.assertContains(response, 'Завершён')
        self.assertContains(response, 'Базовый курс')

    def test_empty_tab(self):
        response = self.client.get('/cabinet/my-courses/upcoming/')
        self.assertContains(response, 'Нет курсов, которые скоро начнутся.')
        self.assertContains(response, 'href="/cabinet/courses/"')

    def test_course_and_dates_from_schedule(self):
        schedule = CourseSchedule.objects.create(course=self.course, format='group',
                                                 start_date=date(2030, 5, 12), end_date=date(2030, 5, 16))
        enrollment = Enrollment(user=self.user, schedule=schedule)
        enrollment.full_clean()
        enrollment.save()
        self.assertEqual((enrollment.course, enrollment.start_date, enrollment.end_date),
                         (self.course, date(2030, 5, 12), date(2030, 5, 16)))
        distance = make_course(title='Дистанционный', slug='distance', course_type=Course.TYPE_DISTANCE)
        access = CourseSchedule.objects.create(course=distance, format='individual', access_days=30)
        enrollment = Enrollment.objects.create(user=self.user, schedule=access)
        self.assertEqual((enrollment.course, enrollment.start_date, enrollment.end_date),
                         (distance, self.today, self.today + timedelta(days=29)))  # доступ — со дня покупки

    def test_schedule_changes_reach_enrollments(self):
        enrollment = self.enroll(5, 7)
        schedule = enrollment.schedule
        schedule.start_date, schedule.end_date = date(2031, 1, 10), date(2031, 1, 12)
        schedule.save()
        enrollment.refresh_from_db()
        self.assertEqual((enrollment.start_date, enrollment.end_date), (date(2031, 1, 10), date(2031, 1, 12)))
        distance = make_course(title='Дистанционный', slug='distance', course_type=Course.TYPE_DISTANCE)
        access = CourseSchedule.objects.create(course=distance, format='individual', access_days=30)
        enrollment = Enrollment.objects.create(user=self.user, schedule=access)
        access.access_days = 60
        access.save()
        enrollment.refresh_from_db()
        self.assertEqual((enrollment.start_date, enrollment.end_date),
                         (self.today, self.today + timedelta(days=59)))

    def test_schedule_without_dates_is_rejected(self):
        empty = CourseSchedule.objects.create(course=self.course, format='group')
        with self.assertRaises(ValidationError):
            Enrollment(user=self.user, schedule=empty).full_clean()

    def test_schedule_with_purchases_is_protected(self):
        from django.db.models import ProtectedError
        enrollment = self.enroll(5, 7)
        with self.assertRaises(ProtectedError):
            enrollment.schedule.delete()

    def test_admin_picks_only_schedule(self):
        schedule = self.schedule(5, 7)
        admin = User.objects.create_superuser('admin', 'admin@example.com', PASSWORD)
        self.client.force_login(admin)
        page = self.client.get('/admin/cabinet/enrollment/add/')
        self.assertContains(page, 'name="schedule"')
        self.assertNotContains(page, 'name="course"')  # курс и даты не вводятся — берутся из записи
        self.assertNotContains(page, 'name="start_date"')
        response = self.client.post('/admin/cabinet/enrollment/add/', {'user': self.user.pk, 'schedule': schedule.pk})
        self.assertRedirects(response, '/admin/cabinet/enrollment/')
        enrollment = Enrollment.objects.get()
        self.assertEqual((enrollment.course, enrollment.start_date, enrollment.end_date),
                         (self.course, schedule.start_date, schedule.end_date))
        user_page = self.client.get(f'/admin/auth/user/{self.user.pk}/change/')
        self.assertContains(user_page, 'name="enrollments-0-schedule"')
        self.assertNotContains(user_page, 'name="enrollments-0-course"')

    def test_completed_course_links_certificate(self):
        self.enroll(-10, -8)
        certificate = Certificate.objects.create(user=self.user, course=self.course, issued_on=self.today,
                                                 file=SimpleUploadedFile('doc.pdf', b'%PDF-1.4'))
        response = self.client.get('/cabinet/my-courses/completed/')
        self.assertContains(response, f'href="/cabinet/certificates/{certificate.pk}/file/"')
        self.assertContains(response, 'Удостоверение о повышении квалификации')


class MembershipTests(TestCase):
    def setUp(self):
        self.user = make_member()
        self.client.force_login(self.user)
        self.today = timezone.localdate()

    def test_not_a_member(self):
        response = self.client.get('/cabinet/membership/')
        self.assertContains(response, 'Вы не являетесь членом Ассоциации')
        self.assertContains(response, 'со скидкой 20%')
        self.assertNotContains(response, 'name="show_on_site"')
        self.client.post('/cabinet/membership/', {'show_on_site': 'on'})  # не член — показывать нечего
        self.assertFalse(Membership.objects.exists())

    def test_active_member_dates_and_switch(self):
        membership = Membership.objects.create(user=self.user, start_date=self.today - timedelta(days=100))
        self.assertEqual(membership.next_fee_date, add_years(membership.start_date))  # взносы — раз в год
        response = self.client.get('/cabinet/membership/')
        self.assertContains(response, 'Членство активно')
        self.assertContains(response, 'через 265 дней')
        self.assertContains(response, 'name="show_on_site"')
        self.assertNotContains(response, 'checked')
        response = self.client.post('/cabinet/membership/', {'show_on_site': 'on'}, follow=True)
        self.assertContains(response, 'Теперь вас видно на сайте')
        membership.refresh_from_db()
        self.assertTrue(membership.show_on_site)
        self.client.post('/cabinet/membership/', {})
        membership.refresh_from_db()
        self.assertFalse(membership.show_on_site)

    def test_suspended_and_overdue(self):
        Membership.objects.create(user=self.user, status=Membership.STATUS_SUSPENDED,
                                  start_date=date(2020, 3, 1), next_fee_date=self.today - timedelta(days=3))
        response = self.client.get('/cabinet/membership/')
        self.assertContains(response, 'Членство приостановлено')
        self.assertContains(response, 'просрочен на 3 дня')
        self.assertContains(response, 'Пока членство приостановлено, на сайте вас не видно.')

    def test_member_on_home_page(self):
        Specialist.objects.create(name='Надежда Кириченко', position='Тренер', city='Москва', country='Россия')
        membership = Membership.objects.create(user=self.user, start_date=date(2023, 3, 15))
        self.assertNotContains(self.client.get('/'), 'Мария Иванова')
        membership.show_on_site = True
        membership.save()
        Profile.objects.filter(user=self.user).update(city='Смоленск', country='Россия')
        response = self.client.get('/')
        self.assertContains(response, 'sea-card sea-card--person', count=2)
        self.assertContains(response, 'Мария Иванова')
        self.assertContains(response, 'Член Ассоциации с 2023 года')
        self.assertContains(response, 'Смоленск, Россия')
        membership.status = Membership.STATUS_SUSPENDED
        membership.save()
        self.assertNotContains(self.client.get('/'), 'Мария Иванова')

    def test_start_date_required_for_member(self):
        with self.assertRaises(ValidationError):
            Membership(user=self.user).full_clean()
        Membership(user=self.user, status=Membership.STATUS_NONE).full_clean()

    def test_admin_action_moves_fee_date(self):
        admin = User.objects.create_superuser('admin', 'admin@example.com', PASSWORD)
        self.client.force_login(admin)
        membership = Membership.objects.create(user=self.user, start_date=date(2024, 2, 29),
                                               next_fee_date=date(2025, 2, 28))
        self.client.post('/admin/cabinet/membership/', {'action': 'fee_paid', '_selected_action': [membership.pk]})
        membership.refresh_from_db()
        self.assertEqual(membership.next_fee_date, date(2026, 2, 28))

    def test_next_fee_is_nearest_anniversary(self):
        from .models import next_anniversary
        today = date(2026, 10, 26)
        self.assertEqual(next_anniversary(date(2023, 3, 15), today), date(2027, 3, 15))  # давний член
        self.assertEqual(next_anniversary(date(2025, 12, 1), today), date(2026, 12, 1))
        self.assertEqual(next_anniversary(today, today), date(2027, 10, 26))  # вступил сегодня — через год
        self.assertEqual(next_anniversary(date(2024, 2, 29), today), date(2027, 2, 28))


class CertificateTests(MediaTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_member()
        self.client.force_login(self.user)
        self.course = make_course(title='Базовый курс', slug='base')
        self.certificate = Certificate.objects.create(
            user=self.user, course=self.course, number='77-123', issued_on=date(2026, 5, 16),
            file=SimpleUploadedFile('Сканы Мария.PDF', b'%PDF-1.4 test'))

    def test_list(self):
        self.assertEqual(self.certificate.title, 'Сертификат о прохождении курса')  # по документу курса
        self.assertRegex(self.certificate.file.name, r'^certificates/[0-9a-f]{32}\.pdf$')
        response = self.client.get('/cabinet/certificates/')
        self.assertContains(response, 'Сертификат о прохождении курса')
        self.assertContains(response, '№ 77-123 · выдан 16 мая 2026')
        self.assertContains(response, 'href="/education/courses/base/"')

    def test_only_owner_downloads(self):
        response = self.client.get(f'/cabinet/certificates/{self.certificate.pk}/file/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertEqual(b''.join(response.streaming_content), b'%PDF-1.4 test')
        self.client.force_login(make_member('other@example.com'))
        self.assertEqual(self.client.get(f'/cabinet/certificates/{self.certificate.pk}/file/').status_code, 404)

    def test_empty(self):
        self.certificate.delete()
        self.assertContains(self.client.get('/cabinet/certificates/'), 'когда вы пройдёте курс')


class ProfileTests(MediaTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_member()
        self.client.force_login(self.user)

    def profile_data(self, **overrides):
        data = {
            'form': 'profile', 'last_name': 'Иванова', 'first_name': 'Мария', 'middle_name': '',
            'birth_date': '1990-05-17', 'country': '', 'city': '', 'about': '',
            'phone_country': 'RU', 'phone_number': '916 123-45-67', 'email': 'maria@example.com',
        }
        data.update(overrides)
        return data

    def test_page_shows_registration_data(self):
        response = self.client.get('/cabinet/profile/')
        self.assertContains(response, 'value="Иванова"')
        self.assertContains(response, 'value="1990-05-17"')
        self.assertContains(response, 'value="916 123-45-67"')
        self.assertContains(response, 'value="maria@example.com"')
        self.assertContains(response, 'name="old_password"')

    def test_fill_in_and_change(self):
        response = self.client.post('/cabinet/profile/', self.profile_data(
            middle_name='Сергеевна', phone_country='KZ', phone_number='701 234 5678', email='Maria.New@example.com'),
            follow=True)
        self.assertRedirects(response, '/cabinet/profile/')
        self.assertContains(response, 'Данные сохранены.')
        self.user.refresh_from_db()
        self.assertEqual((self.user.email, self.user.username), ('maria.new@example.com', 'maria.new@example.com'))
        profile = self.user.profile
        self.assertEqual((profile.middle_name, profile.phone), ('Сергеевна', '+77012345678'))

    def test_country_city_and_about(self):
        response = self.client.get('/cabinet/profile/')
        self.assertContains(response, '<option value="Казахстан" data-code="KZ">Казахстан</option>', html=True)
        self.assertContains(response, 'name="city"')
        self.assertContains(response, 'name="about"')
        self.client.post('/cabinet/profile/', self.profile_data(
            country='Казахстан', city='Алматы', about='Тренер по грудничковому плаванию, 10 лет в бассейне.'))
        profile = Profile.objects.get()
        self.assertEqual((profile.country, profile.city, profile.place), ('Казахстан', 'Алматы', 'Алматы, Казахстан'))
        self.assertEqual(profile.about, 'Тренер по грудничковому плаванию, 10 лет в бассейне.')
        response = self.client.get('/cabinet/profile/')
        self.assertContains(response, '<option value="Казахстан" data-code="KZ" selected>Казахстан</option>',
                            html=True)
        self.assertContains(response, 'Тренер по грудничковому плаванию, 10 лет в бассейне.</textarea>')
        response = self.client.post('/cabinet/profile/', self.profile_data(country='Атлантида'))
        self.assertTrue(response.context['form'].errors['country'])  # только из списка

    def test_country_typed_in_admin_is_kept(self):
        Profile.objects.filter(user=self.user).update(country='РФ')
        self.client.post('/cabinet/profile/', self.profile_data(country='РФ', city='Москва'))
        self.assertEqual(Profile.objects.get().country, 'РФ')

    def test_email_of_other_user_is_taken(self):
        make_member('other@example.com')
        response = self.client.post('/cabinet/profile/', self.profile_data(email='OTHER@example.com'))
        self.assertContains(response, 'Этот email уже у другого пользователя.')
        self.assertContains(response, '<p class="cabinet-user-email">maria@example.com</p>', html=True)

    def test_photo_replace_and_remove(self):
        data = self.profile_data()
        data['avatar'] = image_upload()
        self.client.post('/cabinet/profile/', data)
        first = Profile.objects.get().avatar
        self.assertTrue(first.storage.exists(first.name))
        data = self.profile_data()
        data['avatar'] = image_upload('new.jpg', mode='RGB', fmt='JPEG')
        self.client.post('/cabinet/profile/', data)
        second = Profile.objects.get().avatar
        self.assertNotEqual(second.name, first.name)
        self.assertFalse(first.storage.exists(first.name))  # прежнее фото удалено
        self.client.post('/cabinet/profile/', self.profile_data(remove_avatar='on'))
        self.assertFalse(Profile.objects.get().avatar)
        self.assertFalse(second.storage.exists(second.name))

    def test_change_password_and_stay_logged_in(self):
        response = self.client.post('/cabinet/profile/', {
            'form': 'password', 'old_password': PASSWORD,
            'new_password1': 'Novyi-parol-2026', 'new_password2': 'Novyi-parol-2026'})
        self.assertRedirects(response, '/cabinet/profile/')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Novyi-parol-2026'))
        self.assertEqual(self.client.get('/cabinet/profile/').status_code, 200)  # сессия не сброшена
        response = self.client.post('/cabinet/profile/', {
            'form': 'password', 'old_password': 'wrong', 'new_password1': 'x', 'new_password2': 'x'})
        self.assertTrue(response.context['password_form'].errors['old_password'])

    def test_staff_without_profile_fills_it(self):
        admin = User.objects.create_superuser('admin', 'admin@example.com', PASSWORD)
        self.client.force_login(admin)
        self.client.post('/cabinet/profile/', self.profile_data(email='admin@example.com', last_name='Админов'))
        admin.refresh_from_db()
        self.assertEqual((admin.username, admin.profile.phone), ('admin@example.com', '+79161234567'))


class EnrollTests(TestCase):
    """«Записаться» у даты на странице курса: с входом — запись сразу, без входа — через вход или регистрацию"""

    def setUp(self):
        self.today = timezone.localdate()
        self.course = make_course(title='Базовый курс', slug='base')
        self.schedule = CourseSchedule.objects.create(
            course=self.course, format='group', start_date=self.today + timedelta(days=10),
            end_date=self.today + timedelta(days=12))

    def enroll(self, schedule=None):
        return self.client.post('/cabinet/enroll/', {'schedule': (schedule or self.schedule).pk})

    def test_logged_in_user_is_enrolled(self):
        user = make_member()
        self.client.force_login(user)
        response = self.enroll()
        self.assertRedirects(response, '/cabinet/my-courses/upcoming/', fetch_redirect_response=False)
        enrollment = Enrollment.objects.get()
        self.assertEqual((enrollment.user, enrollment.schedule, enrollment.course), (user, self.schedule, self.course))
        page = self.client.get('/cabinet/my-courses/upcoming/')
        self.assertContains(page, 'Вы записались на курс «Базовый курс»')
        self.assertContains(page, 'class="course-card enrollment-card"', count=1)
        self.enroll()  # второй раз — та же запись
        self.assertEqual(Enrollment.objects.count(), 1)
        self.assertContains(self.client.get('/cabinet/my-courses/upcoming/'), 'Вы уже записаны на эти даты.')

    def test_course_page_buttons(self):
        page = self.client.get('/education/courses/base/')
        self.assertContains(page, f'<input type="hidden" name="schedule" value="{self.schedule.pk}">', html=True)
        self.assertContains(page, 'Записаться</button>')
        user = make_member()
        self.client.force_login(user)
        self.enroll()
        page = self.client.get('/education/courses/base/')
        self.assertContains(page, 'Вы записаны</a>')
        self.assertNotContains(page, 'Записаться</button>')

    def test_anonymous_logs_in_and_is_enrolled(self):
        user = make_member()
        response = self.enroll()
        self.assertRedirects(response, '/cabinet/enroll/auth/')
        self.assertFalse(Enrollment.objects.exists())
        page = self.client.get('/cabinet/enroll/auth/')
        self.assertContains(page, 'Базовый курс')
        self.assertContains(page, 'href="/cabinet/login/?next=/cabinet/enroll/finish/"')
        self.assertContains(page, 'href="/cabinet/register/?next=/cabinet/enroll/finish/"')
        login_page = self.client.get('/cabinet/login/?next=/cabinet/enroll/finish/')
        self.assertContains(login_page, 'После входа запишем вас на курс')
        response = self.client.post('/cabinet/login/', {'username': 'maria@example.com', 'password': PASSWORD,
                                                        'next': '/cabinet/enroll/finish/'})
        self.assertRedirects(response, '/cabinet/enroll/finish/', fetch_redirect_response=False)
        response = self.client.get('/cabinet/enroll/finish/')
        self.assertRedirects(response, '/cabinet/my-courses/upcoming/', fetch_redirect_response=False)
        self.assertEqual(Enrollment.objects.get().user, user)
        self.assertNotIn('pending_enrollment', self.client.session)

    def test_anonymous_registers_and_is_enrolled(self):
        self.enroll()
        page = self.client.get('/cabinet/register/?next=/cabinet/enroll/finish/')
        self.assertContains(page, 'После регистрации запишем вас на курс')
        self.assertContains(page, '<input type="hidden" name="next" value="/cabinet/enroll/finish/">', html=True)
        data = registration_data()
        data['next'] = '/cabinet/enroll/finish/'
        response = self.client.post('/cabinet/register/', data, follow=True)
        self.assertRedirects(response, '/cabinet/my-courses/upcoming/')
        self.assertContains(response, 'Вы зарегистрировались')
        self.assertContains(response, 'Вы записались на курс «Базовый курс»')
        self.assertEqual(Enrollment.objects.get().user.username, 'maria@example.com')

    def test_register_ignores_foreign_next(self):
        data = registration_data()
        data['next'] = 'https://evil.example/'
        self.assertRedirects(self.client.post('/cabinet/register/', data), '/cabinet/', fetch_redirect_response=False)

    def test_login_without_enroll_flow_does_not_enroll(self):
        make_member()
        self.enroll()  # нажал «Записаться», но вошёл обычным входом
        self.assertNotContains(self.client.get('/cabinet/login/'), 'запишем вас на курс')
        self.client.post('/cabinet/login/', {'username': 'maria@example.com', 'password': PASSWORD})
        self.assertFalse(Enrollment.objects.exists())

    def test_closed_or_unknown_dates(self):
        past = CourseSchedule.objects.create(course=self.course, format='group',
                                             start_date=self.today - timedelta(days=10),
                                             end_date=self.today - timedelta(days=8))
        self.assertEqual(self.enroll(past).status_code, 404)
        self.assertEqual(self.client.post('/cabinet/enroll/', {'schedule': 'abc'}).status_code, 404)
        self.assertEqual(self.client.get('/cabinet/enroll/').status_code, 405)
        Course.objects.filter(pk=self.course.pk).update(is_active=False)
        self.assertEqual(self.enroll().status_code, 404)

    def test_pages_without_pending_date(self):
        self.assertRedirects(self.client.get('/cabinet/enroll/auth/'), '/education/courses/')
        self.client.force_login(make_member())
        self.assertRedirects(self.client.get('/cabinet/enroll/finish/'), '/cabinet/my-courses/',
                             fetch_redirect_response=False)

    def test_distance_course_access_from_today(self):
        distance = make_course(title='Дистанционный', slug='distance', course_type=Course.TYPE_DISTANCE)
        access = CourseSchedule.objects.create(course=distance, format='individual', access_days=30)
        self.client.force_login(make_member())
        response = self.enroll(access)
        self.assertRedirects(response, '/cabinet/my-courses/current/', fetch_redirect_response=False)
        enrollment = Enrollment.objects.get()
        self.assertEqual((enrollment.start_date, enrollment.end_date), (self.today, self.today + timedelta(days=29)))


class TeacherMembersTests(MediaTestCase):
    """Преподаватели — члены Ассоциации: аккаунт без пароля и членство (миграция 0006)"""

    def test_migration_makes_teachers_members(self):
        from importlib import import_module

        from django.apps import apps

        from core.models import Teacher
        teacher = Teacher.objects.create(first_name='Анна', last_name='Швыдко')
        linked = Teacher.objects.create(first_name='Елена', last_name='Нури', user=make_member('nuri@example.com'))
        import_module('cabinet.migrations.0006_teachers_members').teachers_to_members(apps, None)
        teacher.refresh_from_db()
        user = teacher.user
        self.assertEqual((user.username, user.first_name, user.last_name), ('anna-shvydko', 'Анна', 'Швыдко'))
        self.assertFalse(user.has_usable_password())  # войти нельзя, пока не зададут пароль
        membership = user.membership
        self.assertEqual((membership.status, membership.start_date, membership.next_fee_date),
                         (Membership.STATUS_ACTIVE, date(2026, 10, 26), date(2027, 10, 26)))
        self.assertFalse(membership.show_on_site)
        self.assertFalse(Membership.objects.filter(user=linked.user).exists())  # уже со своим аккаунтом — не трогаем
        import_module('cabinet.migrations.0006_teachers_members').teachers_to_members(apps, None)
        self.assertEqual(User.objects.filter(username='anna-shvydko').count(), 1)  # повторный запуск — без дублей

    def test_teacher_photo_on_home_and_in_cabinet(self):
        from core.models import Teacher
        user = User.objects.create_user('anna-shvydko', first_name='Анна', last_name='Швыдко')
        teacher = Teacher.objects.create(first_name='Анна', last_name='Швыдко', user=user, photo=image_upload())
        Membership.objects.create(user=user, start_date=date(2026, 10, 26), show_on_site=True)
        response = self.client.get('/')
        self.assertContains(response, 'Анна Швыдко')
        self.assertContains(response, teacher.photo.url)
        self.client.force_login(user)
        self.assertContains(self.client.get('/cabinet/membership/'), f'src="{teacher.photo.url}"')

    def test_teacher_logs_in_by_email_once_admin_sets_it(self):
        user = User.objects.create_user('anna-shvydko', first_name='Анна', last_name='Швыдко')
        user.email = 'anna@example.com'
        user.set_password(PASSWORD)
        user.save()
        response = self.client.post('/cabinet/login/', {'username': 'Anna@Example.com', 'password': PASSWORD})
        self.assertRedirects(response, '/cabinet/', fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_admin_shows_member_teachers_and_bulk_show(self):
        from core.models import Teacher
        user = User.objects.create_user('anna-shvydko', first_name='Анна', last_name='Швыдко')
        Teacher.objects.create(first_name='Анна', last_name='Швыдко', user=user)
        membership = Membership.objects.create(user=user, start_date=date(2026, 10, 26))
        self.client.force_login(User.objects.create_superuser('admin', 'admin@example.com', PASSWORD))
        self.assertContains(self.client.get('/admin/core/teacher/'), 'Член Ассоциации')
        self.client.post('/admin/cabinet/membership/', {'action': 'show_on_site', '_selected_action': [membership.pk]})
        membership.refresh_from_db()
        self.assertTrue(membership.show_on_site)


class MembershipPageTests(TestCase):
    """«Членство в Ассоциации» со старого сайта и анкеты на вступление"""

    PERSON = {
        'last_name': 'Иванова', 'first_name': 'Мария', 'middle_name': 'Сергеевна', 'birth_year': '1990',
        'email': 'maria@example.com', 'phone_country': 'RU', 'phone_number': '',
        'education': 'РГУФК, 2012', 'extra_education': '', 'degree': '',
        'work_places': 'Бассейн «Дельфин»', 'positions': 'Инструктор', 'country': 'Россия', 'city': 'Москва',
        'recommendation': 'Елена Нури', 'consent': 'on', 'nickname': '',
    }
    ORGANIZATION = {
        'organization': 'Аквaклуб «Капелька»', 'activity': 'Грудничковое плавание', 'country': 'Казахстан',
        'city': 'Алматы', 'employees': '12', 'last_name': 'Петрова', 'first_name': 'Анна', 'middle_name': 'Ивановна',
        'head_position': 'Директор', 'address': 'ул. Абая, 1', 'email': 'club@example.com',
        'phone_country': 'KZ', 'phone_number': '701 234 5678', 'website': '', 'consent': 'on', 'nickname': '',
    }

    def test_page_content(self):
        response = self.client.get('/page/membership/')
        self.assertContains(response, '<h1 class="header-page-title">Членство в Ассоциации</h1>', html=True)
        for text in ('В члены Ассоциации принимаются физические и юридические лица',
                     'Преимущества членства в Ассоциации', 'юридическую помощь', '3 500 ₽', '35 000 ₽',
                     '10% — 10 лет', 'Размеры членских взносов на 2026 год', 'documents/polozhenye-o-chlenstve.pdf'):
            self.assertContains(response, text)
        self.assertContains(response, 'href="/membership/apply/person/"')
        self.assertContains(response, 'href="/membership/apply/organization/"')

    def test_regulations_file_exists(self):
        from django.contrib.staticfiles import finders
        self.assertTrue(finders.find('documents/polozhenye-o-chlenstve.pdf'))

    def test_old_site_addresses(self):
        self.assertRedirects(self.client.get('/association/membership'), '/page/membership/', status_code=301)
        self.assertRedirects(self.client.get('/association/privatemembership'), '/membership/apply/person/',
                             status_code=301)
        self.assertRedirects(self.client.get('/association/corporativemembership'),
                             '/membership/apply/organization/', status_code=301)

    def test_person_application(self):
        page = self.client.get('/membership/apply/person/')
        self.assertContains(page, 'Физические лица')
        self.assertContains(page, '152-ФЗ')
        response = self.client.post('/membership/apply/person/', self.PERSON)
        self.assertRedirects(response, '/membership/apply/done/')
        application = MembershipApplication.objects.get()
        self.assertEqual((application.kind, application.status, application.last_name, application.city,
                          application.phone, application.user),
                         ('person', 'new', 'Иванова', 'Москва', '', None))
        self.assertContains(self.client.get('/membership/apply/done/'), 'Заявка отправлена')

    def test_person_required_fields_and_consent(self):
        data = dict(self.PERSON, education='', recommendation='')
        del data['consent']
        response = self.client.post('/membership/apply/person/', data)
        errors = response.context['form'].errors
        self.assertEqual(set(errors), {'education', 'recommendation', 'consent'})
        self.assertFalse(MembershipApplication.objects.exists())

    def test_organization_application(self):
        response = self.client.post('/membership/apply/organization/', self.ORGANIZATION)
        self.assertRedirects(response, '/membership/apply/done/')
        application = MembershipApplication.objects.get()
        self.assertEqual((application.kind, application.organization, application.phone, application.employees),
                         ('organization', 'Аквaклуб «Капелька»', '+77012345678', 12))
        data = dict(self.ORGANIZATION, phone_number='')
        self.assertTrue(self.client.post('/membership/apply/organization/', data).context['form'].errors['phone'])

    def test_spam_trap(self):
        response = self.client.post('/membership/apply/person/', dict(self.PERSON, nickname='bot'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MembershipApplication.objects.exists())

    def test_logged_in_user_gets_prefilled_form_and_membership_on_accept(self):
        user = make_member()
        Profile.objects.filter(user=user).update(city='Смоленск', country='Россия', middle_name='Сергеевна')
        self.client.force_login(user)
        page = self.client.get('/membership/apply/person/')
        for value in ('value="Иванова"', 'value="Смоленск"', 'value="1990"', 'value="maria@example.com"'):
            self.assertContains(page, value)
        self.client.post('/membership/apply/person/', self.PERSON)
        application = MembershipApplication.objects.get()
        self.assertEqual(application.user, user)
        self.client.force_login(User.objects.create_superuser('admin', 'admin@example.com', PASSWORD))
        self.assertEqual(self.client.get(f'/admin/cabinet/membershipapplication/{application.pk}/change/').status_code,
                         200)
        self.client.post('/admin/cabinet/membershipapplication/',
                         {'action': 'accept', '_selected_action': [application.pk]})
        application.refresh_from_db()
        self.assertEqual(application.status, 'accepted')
        self.assertEqual(user.membership.start_date, timezone.localdate())

