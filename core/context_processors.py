from django.utils.functional import SimpleLazyObject

from .models import ContactInfo


def contacts(request):
    """Контакты Ассоциации во всех шаблонах (соцсети в шапке и подвале, телефон для записи).
    Запрос к БД — только если шаблон обратился к {{ contacts }}."""
    return {'contacts': SimpleLazyObject(ContactInfo.get)}
