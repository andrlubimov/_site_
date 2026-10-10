from datetime import date, timedelta
from types import SimpleNamespace

from django.db import OperationalError
from django.db.models import F, Min, Q
from django.http import Http404
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils.text import Truncator
from .about_defaults import ABOUT_SECTIONS
from .models import (
    Teacher, Course, CourseSession, Specialist, Representative, Partner, News, PageContent, AboutSection,
)

import logging

logger = logging.getLogger(__name__)

HOME_COURSES_LIMIT = 6

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
    # На главной — курсы с ближайшими датами; полный список на странице «Программы»
    courses = (
        Course.objects.filter(is_active=True)
        .annotate(next_date=Min('sessions__start_date', filter=Q(sessions__start_date__gte=date.today())))
        .prefetch_related('course_teachers__teacher')
        .order_by(F('next_date').asc(nulls_last=True), 'order', '-created_at')[:HOME_COURSES_LIMIT]
    )
    specialists = Specialist.objects.filter(is_active=True).order_by('order')[:4]
    partners = Partner.objects.filter(is_active=True).order_by('order')

    # Получаем контент страниц
    try:
        about_text = PageContent.objects.get(slug='about_text').content
    except PageContent.DoesNotExist:
        about_text = "Основная цель Ассоциации — создание объединения специалистов, дающего возможность выражать свою профессиональную позицию, знакомить с достижениями и инновациями, содействовать получению новых знаний, повышать квалификацию и обмениваться опытом с коллегами."

    try:
        courses_intro = PageContent.objects.get(slug='courses_intro').content
    except PageContent.DoesNotExist:
        courses_intro = "Возможность получать знания у лучших преподавателей с огромным практическим стажем. Качественное интенсивное образование, большой выбор учебных программ разного направления, связанных с детьми. Выпускники курсов получают документы государственного образца."

    context = {
        'courses': courses,
        'specialists': specialists,
        'partners': partners,
        'about_text': about_text,
        'courses_intro': courses_intro,
    }
    return render(request, 'core/index.html', context)


def courses_list(request):
    """Список всех курсов"""
    courses = Course.objects.filter(is_active=True).prefetch_related('course_teachers__teacher')
    context = {
        'courses': courses,
        'page_title': 'Обучающие программы',
    }
    return render(request, 'core/courses_list.html', context)


def course_detail(request, slug):
    """Детальная страница курса"""
    course = get_object_or_404(
        Course.objects.prefetch_related('course_teachers__teacher'), slug=slug, is_active=True,
    )
    sessions = course.sessions.filter(
        Q(end_date__gte=date.today()) | Q(end_date=None, start_date__gte=date.today())
    )
    context = {
        'course': course,
        'sessions': [
            {'session': s, 'dates': format_date_range(s.start_date, s.last_date)} for s in sessions
        ],
        'page_title': course.title,
    }
    return render(request, 'core/course_detail.html', context)


# Штаб-квартира Ассоциации — отдельная метка на глобусе, как на старой карте
ASSOCIATION_HQ = {
    'name': 'Ассоциация раннего и грудничкового плавания',
    'city': 'Москва',
    'country': 'Россия',
    'lat': 55.753215,
    'lng': 37.622504,
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


MONTHS_GENITIVE = [
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
]

# Цвета полосок курсов в календаре (по id курса)
CALENDAR_COLORS = ['#1f8fa6', '#0d6efd', '#6f42c1', '#d63384', '#fd7e14', '#198754']


def format_date_range(start, end):
    """12–14 ноября 2026 / 30 ноября – 2 декабря 2026 / 5 мая 2026"""
    if start == end:
        return f"{start.day} {MONTHS_GENITIVE[start.month - 1]} {start.year}"
    if start.year != end.year:
        return (f"{start.day} {MONTHS_GENITIVE[start.month - 1]} {start.year} – "
                f"{end.day} {MONTHS_GENITIVE[end.month - 1]} {end.year}")
    if start.month != end.month:
        return (f"{start.day} {MONTHS_GENITIVE[start.month - 1]} – "
                f"{end.day} {MONTHS_GENITIVE[end.month - 1]} {end.year}")
    return f"{start.day}–{end.day} {MONTHS_GENITIVE[start.month - 1]} {start.year}"


def get_calendar_events():
    """События для календаря FullCalendar на странице «Расписание»"""
    try:
        sessions = list(
            CourseSession.objects.filter(course__is_active=True)
            .select_related('course')
            .prefetch_related('course__course_teachers__teacher')
        )
    except OperationalError:
        logger.warning("CourseSession unavailable due to database connectivity issue")
        return []

    events = []
    for session in sessions:
        course = session.course
        last_date = session.last_date
        events.append({
            'id': session.pk,
            'title': course.title,
            'start': session.start_date.isoformat(),
            # у событий «на весь день» FullCalendar считает конец невключительным
            'end': (last_date + timedelta(days=1)).isoformat(),
            'allDay': True,
            'url': reverse('core:course_detail', kwargs={'slug': course.slug}),
            'color': CALENDAR_COLORS[course.pk % len(CALENDAR_COLORS)],
            'extendedProps': {
                'dates': format_date_range(session.start_date, last_date),
                'hours': course.hours,
                'teacher': course.teacher_names,
                'location': session.location,
                'price': session.price,
                'note': session.note,
                'description': Truncator(course.description).words(30),
            },
        })
    return events


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


def page_content(request, slug):
    """Страница с контентом"""
    if slug == 'about':
        return about(request)
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
        context['calendar_events'] = get_calendar_events()
    return render(request, 'core/page_content.html', context)
