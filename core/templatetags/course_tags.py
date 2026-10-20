from django import template

from core.utils import format_rub

register = template.Library()


@register.filter
def rub(value):
    """22800 → «22 800 ₽»"""
    return format_rub(value)


FILTER_ICONS = {
    'type': {'in_person': 'bi-geo-alt-fill', 'blended': 'bi-shuffle', 'distance': 'bi-laptop', 'online': 'bi-camera-video'},
    'venue': {'pool': 'bi-water', 'gym': 'bi-person-arms-up', 'home': 'bi-house'},
}


@register.filter
def filter_icon(value, field_name):
    """Значок для варианта фильтра: {{ option.data.value|filter_icon:field.name }} → 'bi-laptop' или ''"""
    return FILTER_ICONS.get(field_name, {}).get(str(value), '')
