"""Страницы сайта конвенции. Наверху каждой — текущая конвенция: номер, даты, город, кнопка «Стать участником»."""
from types import SimpleNamespace

from django.conf import settings
from django.db.models import Exists, OuterRef
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import Convention, Organizer, PhotoContestWinner, ProgramEvent
from .utils import ordinal_ru


def page(request, template, current=None, **context):
    context['current'] = current or Convention.objects.current()
    context['main_site_url'] = settings.MAIN_SITE_URL
    return render(request, template, context)


def price_cards(convention):
    """Цены участия карточками: [('Участник', [цены]), ('Спикер', [цены])]"""
    cards = {}
    for price in convention.prices.all():
        if price.kind == 'participation':
            cards.setdefault(price.group or 'Участие', []).append(price)
    return list(cards.items())


def prices_of(convention, kind):
    return [price for price in convention.prices.all() if price.kind == kind]


def day_cards(convention):
    """Карточки дней: дата, а под ней — что проходит, по площадкам: после мероприятий подряд на одной
    площадке — её адрес и схема проезда. Если для дня ничего не указано — основная площадка конвенции."""
    cards = []
    for day in convention.days.prefetch_related('activities__venue'):
        blocks = []  # [(площадка, [мероприятия])]
        for activity in day.activities.all():
            venue = activity.venue or convention.venue
            if blocks and blocks[-1][0] == venue:
                blocks[-1][1].append(activity)
            else:
                blocks.append((venue, [activity]))
        if not blocks and convention.venue:
            blocks = [(convention.venue, [])]
        cards.append(SimpleNamespace(day=day, blocks=[SimpleNamespace(venue=v, activities=a) for v, a in blocks]))
    return cards


def partnerships(convention):
    return list(convention.partnerships.select_related('partner')) if convention else []


def home(request):
    current = Convention.objects.current()
    winners = []
    if current:
        last = (PhotoContestWinner.objects.filter(convention__is_published=True, convention__number__lte=current.number)
                .select_related('convention').first())
        if last:
            winners = list(last.convention.photo_winners.all())
    links = partnerships(current)
    return page(
        request, 'convention/home.html', current,
        featured=current.featured_speakers.select_related('speaker') if current else [],
        price_cards=price_cards(current) if current else [],
        winners=winners,
        sponsors=[p for p in links if p.is_general_sponsor],
        partners=[p for p in links if not p.is_general_sponsor],
    )


def program_start(request, number=None):
    if number is None:
        return redirect('convention:program_day', day=1)
    return redirect('convention:archive_day', number=number, day=1)


def program(request, day, number=None):
    """Программа по дням: текущей конвенции — /programma/day-N, прошедшей — /history/13/day-N"""
    day = int(day)
    current = Convention.objects.current()
    if number is None:
        convention = current
        if convention is None:
            raise Http404
    else:
        convention = get_object_or_404(Convention.objects.published(), number=number)
        if convention == current:
            return redirect('convention:program_day', day=day)

    days = list(convention.days.all())
    if not 1 <= day <= max(len(days), 1):
        raise Http404

    def day_url(n):
        if number is None:
            return reverse('convention:program_day', kwargs={'day': n})
        return reverse('convention:archive_day', kwargs={'number': convention.number, 'day': n})

    selected = days[day - 1] if days else None
    sections = []
    if selected:
        events = list(selected.events.select_related('event_type').prefetch_related('speakers'))
        for key, label in ProgramEvent.SECTIONS:
            in_section = [event for event in events if event.section == key]
            if in_section:
                sections.append(SimpleNamespace(key=key, label=label, events=in_section))
    return page(
        request, 'convention/program.html', current,
        convention=convention,
        is_archive=number is not None,
        day_cards=day_cards(convention),
        day_links=[SimpleNamespace(day=d, url=day_url(n), active=n == day) for n, d in enumerate(days, 1)],
        selected=selected,
        day_title=f'{ordinal_ru(day).capitalize()} день, {selected.label}' if selected else '',
        sections=sections,
    )


def participation(request):
    current = Convention.objects.current()
    if current is None:
        raise Http404
    return page(
        request, 'convention/participation.html', current,
        price_cards=price_cards(current),
        extras=prices_of(current, 'extra'),
        hotel_prices=prices_of(current, 'hotel'),
        day_cards=day_cards(current),
    )


def partners(request):
    current = Convention.objects.current()
    return page(
        request, 'convention/partners.html', current,
        partnerships=partnerships(current),
        coordinators=Organizer.objects.filter(group='coordinator'),
    )


def history(request):
    current = Convention.objects.current()
    past = Convention.objects.published().annotate(
        has_program=Exists(ProgramEvent.objects.filter(day__convention=OuterRef('pk'))))
    if current:
        past = past.filter(number__lt=current.number)
    conventions = []
    for convention in past.order_by('number'):
        if convention.has_program:
            convention.details_url = reverse('convention:archive', kwargs={'number': convention.number})
        elif convention.schedule_file:
            convention.details_url = convention.schedule_file.url
        else:
            convention.details_url = ''
        conventions.append(convention)
    return page(request, 'convention/history.html', current, conventions=conventions)


def contacts(request):
    organizers = list(Organizer.objects.all())
    return page(
        request, 'convention/contacts.html',
        committee=[o for o in organizers if o.group == 'committee'],
        coordinators=[o for o in organizers if o.group == 'coordinator'],
    )


def registration(request):
    """Анкета участника — Яндекс Форма во встроенном окне (как на старом сайте)"""
    current = Convention.objects.current()
    url = current.registration_url if current else ''
    return page(
        request, 'convention/registration.html', current,
        form_src=url + ('&' if '?' in url else '?') + 'iframe=1' if url else '',
        form_id=url.split('?')[0].rstrip('/').rsplit('/', 1)[-1],
    )
