from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.models import Course
from core.views import cards_found_label, course_list_context, upcoming_schedules

from .forms import (
    LoginForm, OrganizationApplicationForm, PasswordForm, PersonApplicationForm, ProfileForm, RegistrationForm,
)
from .models import Certificate, Enrollment
from .postponed import postponed_cards, postponed_keys, toggle


def section(key, title, icon, children=()):
    return SimpleNamespace(key=key, title=title, icon=icon, children=list(children))


# Разделы личного кабинета — меню слева, вложенным списком. Адреса — в urls.py (имя адреса = key).
SECTIONS = [
    section('courses', 'Курсы ассоциации', 'bi-journal-bookmark', [
        section('postponed', 'Отложенные курсы', 'bi-heart'),
    ]),
    section('my_courses', 'Мои курсы', 'bi-mortarboard', [
        section(Enrollment.UPCOMING, 'Предстоящие', 'bi-calendar-event'),
        section(Enrollment.CURRENT, 'Идущие', 'bi-play-circle'),
        section(Enrollment.COMPLETED, 'Завершённые', 'bi-check2-circle'),
    ]),
    section('membership', 'Моё членство', 'bi-people'),
    section('certificates', 'Мои сертификаты', 'bi-award'),
    section('profile', 'Мой профиль', 'bi-person-circle'),
]

ENROLL_SESSION_KEY = 'pending_enrollment'  # дата курса, выбранная до входа: запись — сразу после входа

PAGES = {page.key: page for parent in SECTIONS for page in [parent, *parent.children]}
PARENTS = {child.key: parent for parent in SECTIONS for child in parent.children}
MY_COURSES_TABS = [Enrollment.UPCOMING, Enrollment.CURRENT, Enrollment.COMPLETED]


def cabinet_menu(current):
    """Меню кабинета: раздел подсвечен, если открыт он сам; раздел с открытым подразделом — «раскрыт»"""
    def item(page):
        return SimpleNamespace(key=page.key, title=page.title, icon=page.icon,
                               url=reverse(f'cabinet:{page.key}'), active=page.key == current)
    menu = []
    for page in SECTIONS:
        entry = item(page)
        entry.children = [item(child) for child in page.children]
        entry.open = any(child.active for child in entry.children)
        menu.append(entry)
    return menu


def cabinet_user(user):
    """Кто вошёл: имя, email и фото — для шапки меню кабинета. У сотрудников, заведённых в админке,
    профиля может не быть."""
    profile = getattr(user, 'profile', None)
    teacher = getattr(user, 'teacher', None)  # у преподавателя без своего фото — фото со страницы преподавателя
    name = profile.full_name if profile else user.get_full_name()
    if profile and profile.avatar:
        avatar = profile.avatar.url
    else:
        avatar = teacher.photo.url if teacher and teacher.photo else ''
    return SimpleNamespace(
        name=name or user.get_username(),
        email=user.email,
        avatar=avatar,
        initials=(profile.initials if profile else '') or user.get_username()[:1].upper(),
    )


def cabinet_context(request, key):
    """Общее для страниц кабинета: меню слева, кто вошёл, раздел и его родитель"""
    parent = PARENTS.get(key)
    return {
        'page': PAGES[key],
        'parent': SimpleNamespace(title=parent.title, url=reverse(f'cabinet:{parent.key}')) if parent else None,
        'cabinet_menu': cabinet_menu(key),
        'cabinet_user': cabinet_user(request.user),
    }


@login_required
def home(request):
    return redirect('cabinet:courses')


@login_required
def courses(request):
    """Курсы ассоциации — как страница «Программы» на сайте: фильтры, разделы по направлениям, сердечки"""
    context = course_list_context(request)
    context.update(cabinet_context(request, 'courses'))
    return render(request, 'cabinet/courses.html', context)


@login_required
def postponed(request):
    """Отложенные курсы — карточки, отмеченные сердечком"""
    cards = postponed_cards(request)
    context = {'cards': cards, 'found_label': cards_found_label(cards) if cards else ''}
    context.update(cabinet_context(request, 'postponed'))
    return render(request, 'cabinet/postponed.html', context)


@login_required
def my_courses(request, status=None):
    """Купленные курсы: предстоящие, идущие и завершённые — по датам обучения. Без выбора — предстоящие."""
    if status is None:
        return redirect('cabinet:upcoming')
    today = timezone.localdate()
    groups = {key: [] for key in MY_COURSES_TABS}
    certificates = {c.course_id: c for c in request.user.certificates.exclude(course=None)}
    for enrollment in (request.user.enrollments
                       .select_related('course__card')
                       .prefetch_related('course__course_teachers__teacher')):
        enrollment.status = enrollment.status_on(today)
        enrollment.note = enrollment.status_note(today)
        enrollment.certificate = certificates.get(enrollment.course_id)
        groups[enrollment.status].append(enrollment)
    groups[Enrollment.COMPLETED].reverse()  # недавно завершённые — первыми
    context = {
        'tabs': [SimpleNamespace(key=key, title=PAGES[key].title, url=reverse(f'cabinet:{key}'),
                                 count=len(groups[key]), active=key == status) for key in MY_COURSES_TABS],
        'enrollments': groups[status],
        'status': status,
    }
    context.update(cabinet_context(request, status))
    return render(request, 'cabinet/my_courses.html', context)


@login_required
def membership(request):
    """Моё членство: статус, даты вступления и следующего взноса, показ на сайте"""
    member = getattr(request.user, 'membership', None)
    if request.method == 'POST' and member is not None and member.is_member:
        member.show_on_site = request.POST.get('show_on_site') == 'on'
        member.save(update_fields=['show_on_site'])
        messages.success(request, 'Теперь вас видно на сайте в разделе «Членство в ассоциации».'
                         if member.show_on_site else 'Вы скрыты с сайта.')
        return redirect('cabinet:membership')
    context = {'membership': member, 'member_discount': Course.MEMBER_DISCOUNT_PERCENT}
    context.update(cabinet_context(request, 'membership'))
    return render(request, 'cabinet/membership.html', context)


@login_required
def certificates(request):
    """Мои сертификаты — документы о пройденном обучении"""
    context = {'certificates': request.user.certificates.select_related('course')}
    context.update(cabinet_context(request, 'certificates'))
    return render(request, 'cabinet/certificates.html', context)


@login_required
def certificate_file(request, pk):
    """Файл документа — только его владельцу"""
    certificate = get_object_or_404(Certificate, pk=pk, user=request.user)
    return FileResponse(certificate.file.open('rb'), as_attachment=True, filename=certificate.download_name)


@login_required
def profile(request):
    """Мой профиль: данные из регистрации — дополнить или поменять; смена пароля"""
    account = User.objects.get(pk=request.user.pk)  # не request.user: форма с ошибкой не должна менять шапку меню
    profile_form, password_form = ProfileForm(instance=account), PasswordForm(request.user)
    if request.method == 'POST' and request.POST.get('form') == 'password':
        password_form = PasswordForm(request.user, request.POST)
        if password_form.is_valid():
            password_form.save()
            update_session_auth_hash(request, password_form.user)  # остаться в кабинете с новым паролем
            messages.success(request, 'Пароль изменён.')
            return redirect('cabinet:profile')
    elif request.method == 'POST':
        profile_form = ProfileForm(request.POST, request.FILES, instance=account)
        if profile_form.is_valid():
            try:
                with transaction.atomic():
                    profile_form.save()
            except IntegrityError:  # тот же email успели занять параллельно
                profile_form.add_error('email', profile_form.error_messages['duplicate_email'])
            else:
                messages.success(request, 'Данные сохранены.')
                return redirect('cabinet:profile')
    profile_data = profile_form.profile
    context = {
        'form': profile_form,
        'password_form': password_form,
        'avatar_url': profile_data.avatar.url if profile_data and profile_data.avatar else '',
        'joined': account.date_joined,
    }
    context.update(cabinet_context(request, 'profile'))
    return render(request, 'cabinet/profile.html', context)


def safe_next(request):
    """Куда вернуться после входа или регистрации — только на страницу этого сайта"""
    url = request.POST.get('next') or request.GET.get('next', '')
    allowed = url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure())
    return url if allowed else ''


def pending_schedule(request, next_url=None):
    """Дата курса, на которую человек нажал «Записаться» до входа (только если ещё открыта запись).
    next_url — адрес после входа: о записи напоминаем, только если вход ведёт к ней."""
    if next_url is not None and next_url != reverse('cabinet:enroll_finish'):
        return None
    pk = request.session.get(ENROLL_SESSION_KEY)
    return open_schedules().filter(pk=pk).first() if isinstance(pk, int) else None


class CabinetLoginView(LoginView):
    template_name = 'cabinet/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending'] = pending_schedule(self.request, self.get_redirect_url())
        return context


def register(request):
    """Регистрация: после неё человек сразу входит в личный кабинет (или возвращается туда, откуда пришёл —
    например, к записи на курс)"""
    next_url = safe_next(request)
    if request.user.is_authenticated:
        return redirect(next_url or 'cabinet:home')
    if request.method == 'POST':
        form = RegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
            except IntegrityError:  # тот же email успели зарегистрировать параллельно
                form.add_error('email', form.error_messages['duplicate_email'])
            else:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, 'Вы зарегистрировались — добро пожаловать в личный кабинет!')
                return redirect(next_url or 'cabinet:home')
    else:
        form = RegistrationForm()
    return render(request, 'cabinet/register.html', {
        'form': form, 'next': next_url, 'pending': pending_schedule(request, next_url),
    })


# --- Запись на курс: кнопка «Записаться» у даты на странице курса

def open_schedules():
    """Даты, на которые можно записаться: ещё не прошли, курс есть на сайте"""
    return upcoming_schedules().filter(course__is_active=True).select_related('course__card')


def complete_enrollment(request, schedule):
    """Записать вошедшего на дату курса и открыть «Мои курсы» на нужной вкладке"""
    enrollment, created = Enrollment.objects.get_or_create(user=request.user, schedule=schedule)
    if created:
        course = enrollment.course
        variant = f' ({course.variant_name.lower()})' if course.card_id else ''
        messages.success(request, f'Вы записались на курс «{course.display_title}»{variant} — {enrollment.date_label}.')
    else:
        messages.info(request, 'Вы уже записаны на эти даты.')
    return redirect(f'cabinet:{enrollment.status_on(timezone.localdate())}')


@require_POST
def enroll(request):
    """«Записаться»: вошедшего — записать сразу; остальным — запомнить дату и предложить войти
    или зарегистрироваться (оплата появится позже — тогда она встанет между выбором даты и записью)"""
    schedule_id = request.POST.get('schedule', '')
    if not schedule_id.isdigit():
        raise Http404('Дата курса не найдена')
    schedule = get_object_or_404(open_schedules(), pk=schedule_id)
    if not request.user.is_authenticated:
        request.session[ENROLL_SESSION_KEY] = schedule.pk
        return redirect('cabinet:enroll_auth')
    return complete_enrollment(request, schedule)


def enroll_auth(request):
    """Запись без входа: войти или зарегистрироваться — и сразу запись на выбранную дату"""
    schedule = pending_schedule(request)
    if schedule is None:
        return redirect('core:courses_list')
    if request.user.is_authenticated:
        return redirect('cabinet:enroll_finish')
    return render(request, 'cabinet/enroll_auth.html', {
        'schedule': schedule, 'course': schedule.course, 'next': reverse('cabinet:enroll_finish'),
    })


@login_required
def enroll_finish(request):
    """После входа или регистрации — запись на дату, выбранную до входа"""
    schedule = pending_schedule(request)
    request.session.pop(ENROLL_SESSION_KEY, None)
    if schedule is None:
        return redirect('cabinet:my_courses')
    return complete_enrollment(request, schedule)


# --- Отложенные курсы на основном сайте (адреса — public_urls.py)

def postponed_public(request):
    """Отложенные курсы без входа — в этом браузере. Кто вошёл, видит их в личном кабинете."""
    if request.user.is_authenticated:
        return redirect('cabinet:postponed')
    cards = postponed_cards(request)
    context = {
        'cards': cards,
        'found_label': cards_found_label(cards) if cards else '',
        'page_title': 'Отложенные курсы',
    }
    return render(request, 'cabinet/postponed_public.html', context)


@require_POST
def postponed_toggle(request):
    """Сердечко на карточке курса: отложить или убрать. Из js/postponed.js — ответ JSON, без JS — назад на страницу."""
    course_id = request.POST.get('course', '')
    if not course_id.isdigit():
        raise Http404('Курс не найден')
    course = get_object_or_404(Course, pk=course_id, is_active=True)
    is_postponed = toggle(request, course)
    if 'application/json' in request.headers.get('Accept', ''):
        return JsonResponse({'postponed': is_postponed, 'key': course.card_key,
                             'count': len(postponed_keys(request))})
    next_url = request.POST.get('next') or request.headers.get('Referer', '')
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        next_url = reverse('postponed:list')
    return redirect(next_url)


# --- Заявка на вступление в Ассоциацию (страница «Членство»; адреса — membership_urls.py)

APPLICATION_FORMS = {'person': PersonApplicationForm, 'organization': OrganizationApplicationForm}


def membership_apply(request, kind):
    """Анкета на вступление: физические или юридические лица. Можно и без входа в личный кабинет."""
    form_class = APPLICATION_FORMS[kind]
    form = form_class(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('membership:done')
    return render(request, 'cabinet/membership_apply.html', {
        'form': form, 'kind': kind, 'kinds': [(key, cls.title) for key, cls in APPLICATION_FORMS.items()],
        'page_title': 'Заявка на вступление в Ассоциацию',
    })


def membership_apply_done(request):
    return render(request, 'cabinet/membership_apply_done.html', {'page_title': 'Заявка отправлена'})

