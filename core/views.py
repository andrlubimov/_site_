from datetime import date, timedelta
from types import SimpleNamespace

from django.db import OperationalError
from django.db.models import F, Min, Prefetch, Q
from django.http import Http404
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.utils.text import Truncator
from . import info_page, membership_page
from .about_defaults import ABOUT_SECTIONS
from .filters import CourseFilterForm
from .models import (
    Teacher, Course, CourseSchedule, Specialist, Representative, Partner, News, PageContent, AboutSection,
    ContactInfo,
)
from .utils import format_rub, plural_ru
from cabinet.models import Enrollment, Membership

import logging

logger = logging.getLogger(__name__)

HOME_CARDS_LIMIT = 8  # карточек курсов в карусели на главной — остальные по кнопке «Больше курсов»

FALLBACK_PAGE_TITLES = {
    'about': 'Об Ассоциации',
    'membership': 'Членство',
    'contacts': 'Контакты',
    'info': 'Сведения об образовательной организации',
    'timetable': 'Расписание',
    'seminars': 'Выездные семинары',
    'why_us': 'Почему мы',
}


def index(request):
    """Главная страница"""
    # На главной — несколько карточек (как на странице «Программы») с ближайшими датами
    courses = (
        Course.objects.filter(is_active=True)
        .annotate(next_date=Min('schedules__start_date', filter=Q(schedules__start_date__gte=date.today())))
        .select_related('card', 'card__description_course')
        .prefetch_related('course_teachers__teacher',
                          Prefetch('schedules', queryset=upcoming_schedules(), to_attr='upcoming'))
        .order_by(F('next_date').asc(nulls_last=True), 'order', '-created_at')
    )
    all_cards = build_course_cards(courses)  # порядок карточек — по ближайшей дате
    cards = all_cards[:HOME_CARDS_LIMIT]
    more_count = len(all_cards) - len(cards)
    # сначала региональные представители (regional), затем зарубежные (foreign)
    representatives = Representative.objects.filter(is_active=True).order_by('-kind', 'order')
    partners = Partner.objects.filter(is_active=True).order_by('order')

    # Получаем контент страниц
    try:
        courses_intro = PageContent.objects.get(slug='courses_intro').content
    except PageContent.DoesNotExist:
        courses_intro = "Возможность получать знания у лучших преподавателей с огромным практическим стажем. Качественное интенсивное образование, большой выбор учебных программ разного направления, связанных с детьми. Выпускники курсов получают документы государственного образца."

    context = {
        'cards': cards,
        'more_label': (f'Ещё {more_count} {plural_ru(more_count, ("программа", "программы", "программ"))}'
                       if more_count else ''),
        'members': site_members(),
        'representatives': representatives,
        'partners': partners,
        'courses_intro': courses_intro,
    }
    return render(request, 'core/index.html', context)


def site_members():
    """Члены Ассоциации на главной: специалисты из админки и члены Ассоциации из личного кабинета,
    которые сами включили показ на сайте (у них — фото, имя, город и страна из профиля)"""
    members = [
        SimpleNamespace(name=s.name, desc=s.position, place=f'{s.city}, {s.country}',
                        photo=s.photo.url if s.photo else '')
        for s in Specialist.objects.filter(is_active=True).order_by('order')
    ]
    for membership in Membership.objects.shown_on_site().select_related('user__profile').order_by('start_date'):
        members.append(SimpleNamespace(name=membership.public_name, desc=membership.since_label,
                                       place=membership.place, photo=membership.photo_url))
    return members


COURSE_SORTS = [
    ('', 'Рекомендуемые'),
    ('new', 'Сначала новые'),
    ('hours', 'По длительности'),
    ('title', 'По алфавиту'),
]


def courses_list(request):
    """Список курсов с фильтрами: разделы по направлениям, варианты одного курса — в одной карточке"""
    context = course_list_context(request)
    context['page_title'] = 'Обучающие программы'
    return render(request, 'core/courses_list.html', context)


def course_list_context(request):
    """Карточки курсов с фильтрами и сортировкой — для страницы «Программы» и для «Курсов ассоциации»
    в личном кабинете"""
    filter_form = CourseFilterForm(request.GET or None)
    courses = list(filter_form.filter(
        Course.objects.filter(is_active=True)
        .select_related('card', 'card__description_course')
        .prefetch_related('course_teachers__teacher')
    ))
    sort = request.GET.get('sort', '')
    if sort not in dict(COURSE_SORTS):
        sort = ''
    cards = build_course_cards(courses)
    return {
        'courses': courses,
        'cards': cards,
        'sections': group_cards_by_direction(cards, sort),
        'cards_count': len(cards),
        'found_label': cards_found_label(cards),
        'sort': sort,
        'sort_choices': COURSE_SORTS,
        'active_filters': active_filter_chips(filter_form, request),
        'filter_form': filter_form,
    }


def cards_found_label(cards):
    """«N программ · M вариантов» — над списком карточек"""
    variants_count = sum(len(card.variants) for card in cards)
    label = f'{len(cards)} {plural_ru(len(cards), ("программа", "программы", "программ"))}'
    if variants_count != len(cards):
        label += f' · {variants_count} {plural_ru(variants_count, ("вариант", "варианта", "вариантов"))}'
    return label


def build_course_cards(courses):
    """Карточки для страницы «Программы» из курсов, прошедших фильтры.

    Курсы одной карточки (CourseCard) идут строками внутри неё в заданном порядке; курс без карточки
    показывается отдельной карточкой. Скрытые карточки (is_active=False) не показываются."""
    cards = {}
    for course in courses:
        card_obj = course.card if course.card_id else None
        if card_obj is not None and not card_obj.is_active:
            continue
        key = ('card', card_obj.pk) if card_obj else ('course', course.pk)
        card = cards.get(key)
        if card is None:
            card = cards[key] = SimpleNamespace(
                obj=card_obj,
                key=course.card_key,  # по нему закрашено сердечко отложенной карточки
                title=card_obj.title if card_obj else course.list_title,
                order=card_obj.order if card_obj else course.order,
                variants=[],
            )
        card.variants.append(course)

    for card in cards.values():
        card.variants.sort(key=lambda c: (c.card_position, c.pk))
        source = card.obj.description_source if card.obj else card.variants[0]
        card.description = source.short_description if source else ''
        card.direction = (source or card.variants[0]).direction or card.variants[0].direction
        card.direction_label = dict(Course.DIRECTION_CHOICES).get(card.direction, '')
        card.direction_icon = Course.DIRECTION_ICONS.get(card.direction, 'bi-mortarboard')
        card.url = card.variants[0].get_absolute_url()
        card.min_hours = min(c.hours for c in card.variants)
        card.created_at = max(c.created_at for c in card.variants)
        card.types, card.teachers = [], []
        for course in card.variants:
            if course.course_type and course.course_type not in [code for code, _, _ in card.types]:
                card.types.append((course.course_type, course.get_course_type_display(), course.type_icon))
            for teacher in course.teacher_list:
                if teacher not in card.teachers:
                    card.teachers.append(teacher)
    return list(cards.values())


# Порядок разделов на странице «Программы»: крупные направления — сверху
DIRECTION_SECTION_ORDER = ['swimming', 'hydrorehab', 'land', 'management']


def group_cards_by_direction(cards, sort=''):
    """Разделы страницы «Программы»: по направлениям в порядке Course.DIRECTION_CHOICES, затем «Другие»"""
    sort_keys = {
        '': lambda c: (c.order, c.title.lower()),
        'new': lambda c: c.created_at,
        'hours': lambda c: (c.min_hours, c.title.lower()),
        'title': lambda c: c.title.lower(),
    }
    sections = []
    labels = dict(Course.DIRECTION_CHOICES)
    choices = [(code, labels[code]) for code in DIRECTION_SECTION_ORDER] + [('', 'Другие программы')]
    for code, label in choices:
        items = sorted((c for c in cards if (c.direction or '') == code),
                       key=sort_keys[sort], reverse=(sort == 'new'))
        if items:
            sections.append(SimpleNamespace(
                code=code or 'other', label=label, cards=items,
                icon=Course.DIRECTION_ICONS.get(code, 'bi-mortarboard'),
                count_label=f'{len(items)} {plural_ru(len(items), ("программа", "программы", "программ"))}',
            ))
    return sections


def active_filter_chips(form, request):
    """Выбранные фильтры для строки над списком: (название, ссылка без этого фильтра)"""
    if not form.is_bound or not form.is_valid():
        return []
    chips = []
    for name, field in form.fields.items():
        if name == 'q':
            labels = {request.GET.get('q', ''): f'«{request.GET.get("q", "").strip()}»'}
        else:
            labels = {str(value): label for value, label in field.choices}
        for value in request.GET.getlist(name):
            if not value or not value.strip() or value not in labels:
                continue
            query = request.GET.copy()
            query.setlist(name, [v for v in query.getlist(name) if v != value])
            for key in list(query.keys()):
                if not any(query.getlist(key)):
                    del query[key]
            url = f'{request.path}?{query.urlencode()}' if query else request.path
            chips.append((labels[value], url))
    return chips


def upcoming_schedules():
    """Записи расписания, которые ещё не прошли (дистанционные — без дат — актуальны всегда)"""
    return (CourseSchedule.objects
            .filter(Q(start_date=None) | Q(end_date__gte=date.today()))
            .prefetch_related('in_person_days'))


def course_detail(request, slug):
    """Детальная страница курса: /education/courses/<slug>/"""
    course = get_object_or_404(
        Course.objects.select_related('required_course__card', 'card').prefetch_related(
            'course_teachers__teacher', 'child_ages', 'health_features',
            Prefetch('schedules', queryset=upcoming_schedules(), to_attr='upcoming'),
        ),
        slug=slug, is_active=True,
    )
    # другие варианты этого же курса (семинар / повышение квалификации, пакеты) — переключатель вверху
    variants = []
    if course.card_id and course.card.is_active:
        variants = [c for c in course.card.ordered_courses if c.is_active]
    enrolled = set()  # даты, на которые вошедший уже записан, — у них вместо «Записаться» «Вы записаны»
    if request.user.is_authenticated:
        enrolled = set(Enrollment.objects.filter(user=request.user, schedule__course=course)
                       .values_list('schedule_id', flat=True))
    context = {
        'course': course,
        'variants': variants if len(variants) > 1 else [],
        'schedules': course.upcoming,
        'enrolled': enrolled,
        'page_title': course.title,
    }
    return render(request, 'core/course_detail.html', context)


def teachers_list(request):
    """Список преподавателей: карточки с фото, числом программ и направлениями; фильтр по направлению"""
    teachers = Teacher.objects.prefetch_related(Prefetch(
        'courses', queryset=Course.objects.filter(is_active=True), to_attr='active_courses',
    )).order_by('last_name', 'first_name')
    labels = dict(Course.DIRECTION_CHOICES)
    direction = request.GET.get('direction', '')
    if direction not in labels:
        direction = ''
    cards = []
    for teacher in teachers:
        codes = {c.direction for c in teacher.active_courses if c.direction}
        if direction and direction not in codes:
            continue
        # программа — карточка на странице «Программы»: варианты одного курса считаются один раз
        programs = len({('card', c.card_id) if c.card_id else ('course', c.pk) for c in teacher.active_courses})
        cards.append(SimpleNamespace(
            teacher=teacher,
            programs_label=(f'{programs} {plural_ru(programs, ("программа", "программы", "программ"))}'
                            if programs else 'Сейчас нет открытых курсов'),
            directions=[(code, labels[code], Course.DIRECTION_ICONS[code])
                        for code in DIRECTION_SECTION_ORDER if code in codes],
        ))
    # сначала те, у кого есть открытые курсы (порядок по фамилии сохраняется)
    cards.sort(key=lambda card: not card.teacher.active_courses)
    context = {
        'cards': cards,
        'found_label': f'{len(cards)} {plural_ru(len(cards), ("преподаватель", "преподавателя", "преподавателей"))}',
        'direction': direction,
        'direction_choices': [(code, labels[code], Course.DIRECTION_ICONS[code]) for code in DIRECTION_SECTION_ORDER],
        'page_title': 'Преподаватели',
    }
    return render(request, 'core/teachers_list.html', context)


def teacher_detail(request, slug):
    """Страница преподавателя: описание и курсы, которые он ведёт (ближайшие по дате — первыми)"""
    teacher = get_object_or_404(Teacher, slug=slug)
    courses = (
        Course.objects.filter(is_active=True, teachers=teacher)
        .annotate(next_date=Min('schedules__start_date', filter=Q(schedules__start_date__gte=date.today())))
        .select_related('card', 'card__description_course')
        .prefetch_related('course_teachers__teacher',
                          Prefetch('schedules', queryset=upcoming_schedules(), to_attr='upcoming'))
        .order_by(F('next_date').asc(nulls_last=True), 'title')
    )
    # те же карточки, что на странице «Программы»; порядок — по ближайшей дате
    cards = build_course_cards(courses)
    found_label = cards_found_label(cards)
    directions = []
    for card in cards:
        if card.direction and card.direction not in [code for code, _, _ in directions]:
            directions.append((card.direction, card.direction_label, card.direction_icon))
    context = {
        'teacher': teacher,
        'cards': cards,
        'found_label': found_label,
        'directions': directions,
        'page_title': teacher.display_name,
    }
    return render(request, 'core/teacher_detail.html', context)


def legacy_course_redirect(request, slug, legacy=None):
    """Старые адреса /courses/<slug>/ и ссылки старого сайта /education/courses/<slug>/<дата> → страница курса"""
    return redirect('core:course_detail', slug=slug, permanent=True)


# Штаб-квартира Ассоциации — отдельная метка на глобусе, как на старой карте
ASSOCIATION_HQ = {
    'name': 'Ассоциация раннего и грудничкового плавания',
    'city': 'Москва',
    'country': 'Россия',
    'lat': 55.876348,  # улица Малыгина, 1 с2 — как метка на карте в «Контактах» (contact_defaults.MAP_POINT)
    'lng': 37.701378,
    'kind': 'hq',
}


def representatives_list(request):
    """Страница «Представители»: региональные представители, зарубежные партнёры и глобус"""
    representatives = list(Representative.objects.filter(is_active=True))
    globe_points = [ASSOCIATION_HQ] + [
        {
            'id': f'rep-{rep.pk}',
            'name': rep.name,
            'city': rep.city,
            'country': rep.country,
            'lat': rep.latitude,
            'lng': rep.longitude,
            'kind': rep.kind,
            'logo': rep.logo.url if rep.logo else '',
        }
        for rep in representatives if rep.has_coordinates
    ]
    context = {
        'regional': [r for r in representatives if r.kind == Representative.KIND_REGIONAL],
        'foreign': [r for r in representatives if r.kind == Representative.KIND_FOREIGN],
        'globe_points': globe_points,
        'page_title': 'Представители',
    }
    return render(request, 'core/representatives.html', context)


def partners_list(request):
    """Список партнеров"""
    partners = Partner.objects.filter(is_active=True).order_by('order')
    context = {
        'partners': partners,
        'page_title': 'Партнеры Ассоциации',
    }
    return render(request, 'core/partners_list.html', context)


def news_list(request):
    """Список новостей"""
    news = News.objects.filter(is_published=True).order_by('-published_date')
    context = {
        'news': news,
        'page_title': 'Новости',
    }
    return render(request, 'core/news_list.html', context)


def news_detail(request, slug):
    """Детальная страница новости"""
    news_item = get_object_or_404(News, slug=slug, is_published=True)
    context = {
        'news': news_item,
        'page_title': news_item.title,
    }
    return render(request, 'core/news_detail.html', context)


# Цвета полосок курсов в календаре (по id курса)
# — цвета палитры сайта; на каждом белый текст читается (контраст ≥ 5:1)
CALENDAR_COLORS = ['#0f6f93', '#0b3e52', '#be3455', '#b45309', '#4a5560', '#0b5675']


def get_calendar_events(courses=None):
    """События календаря на странице «Расписание»: записи расписания с датами.
    Дистанционные курсы дат не имеют и выводятся отдельным списком (get_distance_schedules).
    courses — queryset курсов после фильтров (None — все активные)."""
    try:
        schedules = CourseSchedule.objects.filter(course__is_active=True).exclude(start_date=None)
        if courses is not None:
            schedules = schedules.filter(course__in=courses)
        schedules = list(
            schedules
            .select_related('course')
            .prefetch_related('course__course_teachers__teacher', 'in_person_days')
        )
    except OperationalError:
        logger.warning("CourseSchedule unavailable due to database connectivity issue")
        return []

    events = []
    for schedule in schedules:
        course = schedule.course
        events.append({
            'id': schedule.pk,
            'title': course.title,
            'start': schedule.start_date.isoformat(),
            # у событий «на весь день» FullCalendar считает конец невключительным
            'end': (schedule.last_date + timedelta(days=1)).isoformat(),
            'allDay': True,
            'url': reverse('core:course_detail', kwargs={'slug': course.slug}),
            'color': CALENDAR_COLORS[course.pk % len(CALENDAR_COLORS)],
            'extendedProps': {
                'dates': schedule.date_label,
                'inPersonDays': schedule.in_person_days_label,
                'materials': schedule.materials_label,
                'time': schedule.time_label,
                'type': course.get_course_type_display(),
                'format': schedule.get_format_display(),
                'hours': course.hours_label,
                'teacher': course.teacher_names,
                'price': format_rub(schedule.price),
                'comment': schedule.comment,
                'description': Truncator(course.short_description).words(30),
            },
        })
    return events


def get_distance_schedules(courses=None):
    """Дистанционные курсы для страницы «Расписание»: без дат, со сроком доступа"""
    try:
        schedules = CourseSchedule.objects.filter(course__is_active=True, start_date=None)
        if courses is not None:
            schedules = schedules.filter(course__in=courses)
        return list(schedules.select_related('course').order_by('course__title', 'access_days'))
    except OperationalError:
        return []


def get_about_sections():
    """Блоки страницы «Об Ассоциации» по ключу; отсутствующие берутся из about_defaults."""
    sections = {item['key']: SimpleNamespace(**item) for item in ABOUT_SECTIONS}
    try:
        for section in AboutSection.objects.all():
            sections[section.key] = section
    except OperationalError:
        logger.warning("AboutSection unavailable due to database connectivity issue")
    return sections


def about(request):
    """Страница «Об Ассоциации» из редактируемых блоков"""
    context = {
        'content': SimpleNamespace(slug='about'),
        'page_title': 'Ассоциация грудничкового плавания',
        'sections': get_about_sections(),
    }
    return render(request, 'core/about.html', context)


def contacts(request):
    """Страница «Контакты»: данные — из записи «Контакты» в админке (по умолчанию — со старого сайта)"""
    info = ContactInfo.get()
    context = {
        'content': SimpleNamespace(slug='contacts'),
        'page_title': 'Контакты',
        'info': info,
        'map_query': info.map_query or info.address,
        # метка Ассоциации на карте: «долгота,широта» — так их ждут Яндекс Карты
        'map_point': f'{info.map_lng},{info.map_lat}' if info.map_lat and info.map_lng else '',
    }
    return render(request, 'core/contacts.html', context)


def education_info(request):
    """«Сведения об образовательной организации»: тексты и документы — core/info_page.py"""
    teachers = {t.slug: t for t in Teacher.objects.filter(slug__in=[l.teacher_slug for l in info_page.LEADERS])}
    leaders = [SimpleNamespace(**vars(leader), teacher=teachers.get(leader.teacher_slug)) for leader in info_page.LEADERS]
    context = {
        'content': SimpleNamespace(slug='info'),
        'page_title': 'Сведения об образовательной организации',
        'info': info_page,
        'leaders': leaders,
    }
    return render(request, 'core/education_info.html', context)


def membership(request):
    """«Членство в Ассоциации»: преимущества, взносы, анкеты на вступление — core/membership_page.py"""
    context = {
        'content': SimpleNamespace(slug='membership'),
        'page_title': 'Членство в Ассоциации',
        'page': membership_page,
    }
    return render(request, 'core/membership.html', context)


def page_content(request, slug):
    """Страница с контентом"""
    if slug == 'about':
        return about(request)
    if slug == 'membership':
        return membership(request)
    if slug == 'contacts':
        return contacts(request)
    if slug == 'info':
        return education_info(request)
    try:
        content = PageContent.objects.filter(slug=slug).first()
    except OperationalError:
        logger.warning("PageContent unavailable for slug '%s' due to database connectivity issue", slug)
        content = None
    if content is None:
        if slug not in FALLBACK_PAGE_TITLES:
            raise Http404("No PageContent matches the given query.")
        content = SimpleNamespace(slug=slug, title=FALLBACK_PAGE_TITLES[slug], content='')
    context = {
        'content': content,
        'page_title': content.title or slug,
    }
    if slug == 'timetable':
        filter_form = CourseFilterForm(request.GET or None)
        courses = filter_form.filter(Course.objects.filter(is_active=True)) if filter_form.is_filtered else None
        context['filter_form'] = filter_form
        context['calendar_events'] = get_calendar_events(courses)
        context['distance_schedules'] = get_distance_schedules(courses)
    return render(request, 'core/page_content.html', context)
