from django.utils.functional import SimpleLazyObject

from .postponed import postponed_keys


def postponed(request):
    """Отложенные курсы во всех шаблонах: закрашенные сердечки на карточках и число на кнопке «Отложенные».
    Запрос к базе — только если шаблон к ним обратился и что-то отложено."""
    keys = SimpleLazyObject(lambda: postponed_keys(request))
    return {'postponed_keys': keys, 'postponed_count': SimpleLazyObject(lambda: len(keys))}
