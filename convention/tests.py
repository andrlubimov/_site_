from datetime import date, time

from django.contrib.auth.models import User
from django.test import TestCase

from .models import Convention, EventType, Organizer, Partner, ProgramEvent, Speaker
from .utils import date_span, ordinal_ru

HOST = 'convent.grudnichkovoe-plavanie.ru'


class UtilsTests(TestCase):
    def test_ordinals(self):
        self.assertEqual(ordinal_ru(14), 'четырнадцатый')
        self.assertEqual(ordinal_ru(13, feminine=True), 'тринадцатая')
        self.assertEqual(ordinal_ru(3, feminine=True), 'третья')
        self.assertEqual(ordinal_ru(21), 'двадцать первый')
        self.assertEqual(ordinal_ru(40, feminine=True), '40-я')

    def test_date_span(self):
        self.assertEqual(date_span(date(2026, 12, 4), date(2026, 12, 6)), 'с 4 по 6 декабря 2026')
        self.assertEqual(date_span(date(2017, 11, 30), date(2017, 12, 3)), 'с 30 ноября по 3 декабря 2017')


class SeedTests(TestCase):
    """Начальные данные со старого сайта (миграция 0002)"""

    def test_current_is_fourteenth(self):
        current = Convention.objects.current()
        self.assertEqual(current.number, 14)
        self.assertEqual(current.dates, '4–6 декабря 2026')
        self.assertEqual(current.days.count(), 3)
        self.assertFalse(ProgramEvent.objects.filter(day__convention=current).exists())  # программу 2026 заполнят в админке
        self.assertEqual([(p.group, p.label, p.amount) for p in current.prices.filter(kind='participation')], [
            ('Участник', '1 день', 12800), ('Участник', '2 дня', 15800), ('Участник', '3 дня', 22800),
            ('Спикер', '1 день', 9800), ('Спикер', '2 дня', 12800), ('Спикер', '3 дня', 17800),
        ])
        self.assertEqual(current.partnerships.get(is_general_sponsor=True).partner.name, 'PoolStyle')
        self.assertEqual(current.partnerships.count(), 7)
        self.assertEqual(current.featured_speakers.count(), 12)

    def test_program_of_2025_by_days(self):
        thirteenth = Convention.objects.get(number=13)
        counts = [day.events.count() for day in thirteenth.days.all()]
        self.assertEqual(counts, [37, 28, 30])
        self.assertTrue(ProgramEvent.objects.filter(day__convention=thirteenth, section='managers').exists())
        self.assertTrue(ProgramEvent.objects.filter(day__convention=thirteenth, section='pool').exists())
        event = ProgramEvent.objects.get(title__startswith='Бобат-терапия')
        self.assertEqual([s.name for s in event.speakers.all()], ['Анна Трофимова', 'Ирина Бурмистенко'])

    def test_archive_and_contacts(self):
        self.assertEqual(list(Convention.objects.values_list('number', flat=True).order_by('number')),
                         list(range(6, 15)))
        self.assertEqual(Organizer.objects.filter(group='committee').count(), 5)
        self.assertEqual(Organizer.objects.filter(group='coordinator').count(), 2)


class HostRoutingTests(TestCase):
    def test_convention_domain_serves_convention(self):
        response = self.client.get('/', HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'convention/home.html')
        self.assertContains(response, 'четырнадцатая ежегодная конвенция')
        self.assertContains(response, '4–6 декабря 2026 · Москва')
        self.assertContains(response, 'Конвенция пройдет в 2026 году уже четырнадцатый раз')
        self.assertContains(response, 'Конвенция проводится с 4 по 6 декабря 2026')

    def test_main_domain_unchanged(self):
        response = self.client.get('/')
        self.assertTemplateNotUsed(response, 'convention/home.html')
        self.assertEqual(self.client.get('/uchastie').status_code, 404)

    def test_rest_of_site_not_on_convention_domain(self):
        for url in ['/admin/', '/education/courses/', '/cabinet/']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url, HTTP_HOST=HOST).status_code, 404)

    def test_unknown_host_rejected(self):
        self.assertEqual(self.client.get('/', HTTP_HOST='evil.example').status_code, 400)


class PagesTests(TestCase):
    def get(self, url):
        return self.client.get(url, HTTP_HOST=HOST)

    def test_old_addresses(self):
        self.assertRedirects(self.get('/programma'), '/programma/day-1', fetch_redirect_response=False)
        for url in ['/programma/day-1', '/programma/day-3', '/uchastie', '/uchastie/', '/partnery', '/history',
                    '/kontakty', '/anketa']:
            with self.subTest(url=url):
                self.assertEqual(self.get(url).status_code, 200)
        self.assertEqual(self.get('/programma/day-4').status_code, 404)

    def test_current_program_waits_for_admin(self):
        response = self.get('/programma/day-2')
        self.assertContains(response, 'Второй день, 5 декабря')
        self.assertContains(response, 'Программа находится в процессе наполнения')
        self.assertNotContains(response, 'class="event-card"')
        self.assertContains(response, 'Международный торгово-выставочный комплекс «Гринвуд»')  # площадка в карточке дня

    def test_archived_program(self):
        response = self.get('/history/13/day-1')
        self.assertContains(response, 'Тринадцатая конвенция, 5–7 декабря 2025')
        self.assertContains(response, 'Развитие функциональных блоков мозга')
        self.assertContains(response, 'Мероприятия для руководителей')
        self.assertContains(response, '<b>08:15</b> → 05.12.2025')
        self.assertContains(response, 'style="--event-color: #00923C"')
        self.assertNotContains(response, 'Программа находится в процессе наполнения')
        self.assertContains(self.get('/history/13/day-2'), 'Мастер-классы в бассейне')
        self.assertRedirects(self.get('/history/14/day-2'), '/programma/day-2', fetch_redirect_response=False)
        self.assertEqual(self.get('/history/99/day-1').status_code, 404)

    def test_participation(self):
        response = self.get('/uchastie')
        self.assertContains(response, '<b>3 дня</b> — 22800 руб')
        self.assertContains(response, 'Номер категории Комфорт (одноместное проживание) — 5700 руб/сутки')
        self.assertContains(response, '<b>Питание на Конвенции</b> (каждый обед или ужин, шведский стол) — 1320 руб.')
        self.assertContains(response, '4 декабря')
        # положение и оферта в архиве — 2023 года: у текущей конвенции их нет, пока не загрузят новые
        self.assertNotContains(response, 'Публичная оферта')
        self.assertTrue(Convention.objects.get(number=11).offer)

    def test_history(self):
        response = self.get('/history')
        self.assertContains(response, 'Шестая конвенция')
        self.assertContains(response, 'Проходила 30 ноября – 3 декабря 2017 года в Международном')
        self.assertContains(response, 'href="/history/13"')
        self.assertContains(response, 'class="center speaker-card archive-card"', count=8)  # 6–13, без текущей

    def test_partners_and_contacts(self):
        response = self.get('/partnery')
        self.assertContains(response, 'Генеральный спонсор')
        self.assertContains(response, 'Сайт генерального спонсора')
        self.assertContains(response, 'id="uslovya"')
        self.assertContains(response, 'href="tel:+79169990990"')
        self.assertNotContains(response, 'PROPERĀ')  # партнёр прошлых лет — не у текущей конвенции
        response = self.get('/kontakty')
        self.assertContains(response, 'Оргкомитет конвенции')
        self.assertContains(response, 'manager.babyswim@gmail.com')

    def test_registration_form(self):
        response = self.get('/anketa')
        self.assertContains(response, 'src="https://forms.yandex.ru/cloud/68c2bee9d046882ac381dfad?iframe=1"')
        self.assertContains(response, 'name="ya-form-68c2bee9d046882ac381dfad"')

    def test_new_convention_becomes_current(self):
        new = Convention.objects.create(number=15, start_date=date(2027, 12, 3), end_date=date(2027, 12, 5),
                                        place='в Москве')
        day = new.days.create(date=date(2027, 12, 3))
        event = day.events.create(time=time(9, 0), event_type=EventType.objects.get(name='Доклад-презентация'),
                                  title='Новый доклад', section='main')
        event.speakers.add(Speaker.objects.create(name='Новый Спикер'))
        response = self.get('/')
        self.assertContains(response, 'пятнадцатая ежегодная конвенция')
        self.assertContains(self.get('/programma/day-1'), 'Новый доклад')
        self.assertContains(self.get('/history'), 'Четырнадцатая конвенция')

    def test_without_any_convention(self):
        Convention.objects.all().delete()
        self.assertEqual(self.get('/').status_code, 200)
        self.assertEqual(self.get('/programma/day-1').status_code, 404)
        self.assertContains(self.get('/anketa'), 'Регистрация на конвенцию откроется скоро')


class AdminTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('admin', 'admin@example.com', 'x'))

    def test_admin_pages(self):
        thirteenth = Convention.objects.get(number=13)
        day = thirteenth.days.first()
        for url in ['/admin/convention/convention/', f'/admin/convention/convention/{thirteenth.pk}/change/',
                    '/admin/convention/conventionday/', f'/admin/convention/conventionday/{day.pk}/change/',
                    '/admin/convention/programevent/', '/admin/convention/speaker/', '/admin/convention/partner/',
                    '/admin/convention/eventtype/', '/admin/convention/organizer/', '/admin/convention/venue/',
                    '/admin/convention/photocontestwinner/', '/admin/convention/programevent/?q=Лурия']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(Partner.objects.count(), 11)
