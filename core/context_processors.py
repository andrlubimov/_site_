from types import SimpleNamespace

from django.urls import reverse
from django.utils.functional import SimpleLazyObject

from .models import ContactInfo

CONVENTION_URL = 'https://convent.grudnichkovoe-plavanie.ru/'


def contacts(request):
    """Контакты Ассоциации во всех шаблонах (соцсети в шапке и подвале, телефон для записи).
    Запрос к БД — только если шаблон обратился к {{ contacts }}."""
    return {'contacts': SimpleLazyObject(ContactInfo.get)}


def _page(slug):
    return reverse('core:page_content', kwargs={'slug': slug})


def _menu():
    """Пункты меню: (название, адрес, подпункты). Подпункты — выпадающий список; первый ведёт туда же,
    куда сам пункт. Меню одно для шапки, мобильного меню и подвала."""
    return [
        ('Ассоциация', _page('about'), [
            ('Об Ассоциации', _page('about')),
            ('Членство', _page('membership')),
            ('Новости', reverse('core:news_list')),
            ('Сведения об образовательной организации', _page('info')),
        ]),
        ('Курсы', reverse('core:courses_list'), [
            ('Программы', reverse('core:courses_list')),
            ('Расписание', _page('timetable')),
            ('Преподаватели', reverse('core:teachers_list')),
            ('Выездные семинары', _page('seminars')),
            ('Почему стоит учиться у нас', _page('why_us')),
        ]),
        ('Конвенция', CONVENTION_URL, []),
        ('Представители', reverse('core:specialists_list'), []),
        ('Партнёры', reverse('core:partners_list'), []),
        ('Контакты', _page('contacts'), []),
    ]


def navigation(request):
    """Меню сайта. Пункт подсвечен, если открыт он сам или одна из его страниц
    (у «Курсов» — ещё страницы курсов и преподавателей: всё, что под /education/)."""
    path = request.path
    items = []
    for label, url, children in _menu():
        links = [url] + [child_url for _, child_url in children]
        active = path in links or (label == 'Курсы' and path.startswith('/education/'))
        items.append(SimpleNamespace(
            label=label, url=url, external=url.startswith('http'), active=active,
            children=[SimpleNamespace(label=child_label, url=child_url, active=path == child_url)
                      for child_label, child_url in children],
        ))
    return {'site_menu': items}
