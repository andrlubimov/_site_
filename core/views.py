from types import SimpleNamespace

from django.db import OperationalError
from django.http import Http404
from django.shortcuts import render, get_object_or_404
from .models import Teacher, Course, Specialist, Partner, News, PageContent

import logging

logger = logging.getLogger(__name__)

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
    courses = Course.objects.filter(is_active=True).select_related('teacher').order_by('order', '-created_at')
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
    courses = Course.objects.filter(is_active=True).select_related('teacher')
    context = {
        'courses': courses,
        'page_title': 'Обучающие программы',
    }
    return render(request, 'core/courses_list.html', context)


def course_detail(request, slug):
    """Детальная страница курса"""
    course = get_object_or_404(Course, slug=slug, is_active=True)
    context = {
        'course': course,
        'page_title': course.title,
    }
    return render(request, 'core/course_detail.html', context)


def specialists_list(request):
    """Список специалистов"""
    specialists = Specialist.objects.filter(is_active=True).order_by('order')
    context = {
        'specialists': specialists,
        'page_title': 'Наши специалисты',
    }
    return render(request, 'core/specialists_list.html', context)


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


def page_content(request, slug):
    """Страница с контентом"""
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
    return render(request, 'core/page_content.html', context)
