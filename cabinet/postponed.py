"""Отложенные курсы — сердечко на карточке курса.

Вошедший пользователь откладывает курсы в базу (PostponedCourse), остальные — в сессию браузера;
при входе отложенное из сессии переходит в личный кабинет. Откладывается вся карточка курса
(варианты одного курса — CourseCard): хранится один её курс, показывается карточка целиком.
"""
from django.db.models import Prefetch, Q

from core.models import Course
from core.views import build_course_cards, upcoming_schedules

from .models import PostponedCourse

SESSION_KEY = 'postponed_courses'


def _user(request):
    user = getattr(request, 'user', None)
    return user if user is not None and user.is_authenticated else None


def _session_ids(request):
    session = getattr(request, 'session', None)
    if session is None:
        return []
    return [pk for pk in session.get(SESSION_KEY, []) if isinstance(pk, int)]


def _same_card(course, prefix=''):
    """Условие «курс той же карточки» (prefix='course__' — для PostponedCourse)"""
    if course.card_id:
        return Q(**{f'{prefix}card_id': course.card_id})
    return Q(**{f'{prefix}pk': course.pk})


def postponed_ids(request):
    """id отложенных курсов; раньше отложенные — первыми"""
    user = _user(request)
    if user:
        return list(user.postponed_courses.order_by('created_at', 'pk').values_list('course_id', flat=True))
    return _session_ids(request)


def postponed_keys(request):
    """Ключи отложенных карточек (Course.card_key) — у этих карточек сердечко закрашено"""
    ids = postponed_ids(request)
    if not ids:
        return set()
    return {course.card_key for course in Course.objects.filter(pk__in=ids).only('pk', 'card_id')}


def toggle(request, course):
    """Отложить карточку курса или убрать её из отложенных. True — карточка теперь отложена."""
    user = _user(request)
    if user:
        same = user.postponed_courses.filter(_same_card(course, 'course__'))
        if same.exists():
            same.delete()
            return False
        PostponedCourse.objects.get_or_create(user=user, course=course)
        return True
    ids = _session_ids(request)
    same = set(Course.objects.filter(_same_card(course), pk__in=ids).values_list('pk', flat=True))
    if same:
        request.session[SESSION_KEY] = [pk for pk in ids if pk not in same]
        return False
    request.session[SESSION_KEY] = ids + [course.pk]
    return True


def postponed_cards(request):
    """Карточки отложенных курсов (с ближайшими датами) — последние отложенные первыми"""
    ids = postponed_ids(request)
    if not ids:
        return []
    keys = {course.pk: course for course in Course.objects.filter(pk__in=ids).only('pk', 'card_id')}
    card_ids = [course.card_id for course in keys.values() if course.card_id]
    courses = (
        Course.objects.filter(is_active=True)
        .filter(Q(pk__in=ids, card=None) | Q(card_id__in=card_ids))
        .select_related('card', 'card__description_course')
        .prefetch_related('course_teachers__teacher',
                          Prefetch('schedules', queryset=upcoming_schedules(), to_attr='upcoming'))
    )
    cards = build_course_cards(courses)
    rank = {}
    for pk in reversed(ids):
        if pk in keys:
            rank.setdefault(keys[pk].card_key, len(rank))
    cards.sort(key=lambda card: rank.get(card.key, len(rank)))
    return cards


def keep_after_login(sender, request, user, **kwargs):
    """Вошёл — отложенное до входа (в сессии) переходит в личный кабинет"""
    session = getattr(request, 'session', None)
    ids = session.pop(SESSION_KEY, []) if session is not None else []
    for course in Course.objects.filter(pk__in=[pk for pk in ids if isinstance(pk, int)]):
        if not user.postponed_courses.filter(_same_card(course, 'course__')).exists():
            PostponedCourse.objects.create(user=user, course=course)
