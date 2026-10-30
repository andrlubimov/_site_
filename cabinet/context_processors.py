from django.utils.functional import SimpleLazyObject

from .postponed import postponed_keys


def postponed(request):
    """Отложенные курсы во всех шаблонах: закрашенные сердечки на карточках и число на кнопке «Отложенные».
    Запрос к базе — только если шаблон к ним обратился и что-то отложено."""
    keys = SimpleLazyObject(lambda: postponed_keys(request))
    return {'postponed_keys': keys, 'postponed_count': SimpleLazyObject(lambda: len(keys))}


def tabbar(request):
    """Нижняя панель разделов кабинета — у вошедшего на всех страницах сайта (видна на телефоне и планшете).
    В кабинете подсвечен открытый раздел, на остальных страницах — ни один."""
    user = getattr(request, 'user', None)  # запрос без AuthenticationMiddleware — без пользователя
    if user is None or not user.is_authenticated:
        return {}
    from .views import PAGES, cabinet_menu  # views тянут core.views — не на загрузке модуля

    match = request.resolver_match
    current = match.url_name if match and match.namespace == 'cabinet' and match.url_name in PAGES else None
    return {'cabinet_tabbar': SimpleLazyObject(lambda: cabinet_menu(current))}
