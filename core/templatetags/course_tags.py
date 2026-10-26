from django import template

from core.utils import format_rub

register = template.Library()


@register.filter
def rub(value):
    """22800 → «22 800 ₽»"""
    return format_rub(value)


@register.filter
def is_postponed(card_key, postponed_keys):
    """Отложена ли карточка курса: {{ card.key|is_postponed:postponed_keys }}"""
    return bool(postponed_keys) and card_key in postponed_keys


@register.filter
def tel_href(phone):
    """«+7 (916) 999-09-90» → «tel:+79169990990»"""
    phone = str(phone or '').strip()
    digits = ''.join(ch for ch in phone if ch.isdigit())
    return f"tel:{'+' if phone.startswith('+') else ''}{digits}"


FILTER_ICONS = {
    'type': {'in_person': 'bi-geo-alt-fill', 'blended': 'bi-shuffle', 'distance': 'bi-laptop', 'online': 'bi-camera-video'},
    'venue': {'pool': 'bi-water', 'gym': 'bi-person-arms-up', 'home': 'bi-house'},
}


@register.filter
def filter_icon(value, field_name):
    """Значок для варианта фильтра: {{ option.data.value|filter_icon:field.name }} → 'bi-laptop' или ''"""
    return FILTER_ICONS.get(field_name, {}).get(str(value), '')
