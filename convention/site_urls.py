"""Адреса на домене конвенции (convent.grudnichkovoe-plavanie.ru) — включает convention.middleware."""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path('', include('convention.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
