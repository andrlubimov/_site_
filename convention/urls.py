"""Адреса — как на старом сайте конвенции (/programma/day-1, /uchastie…), чтобы старые ссылки работали.
Слэш в конце не обязателен."""
from django.urls import path, re_path

from . import views

app_name = 'convention'

urlpatterns = [
    path('', views.home, name='home'),
    re_path(r'^programma/?$', views.program_start, name='program'),
    re_path(r'^programma/day-(?P<day>[0-9]+)/?$', views.program, name='program_day'),
    re_path(r'^uchastie/?$', views.participation, name='participation'),
    re_path(r'^partnery/?$', views.partners, name='partners'),
    re_path(r'^history/?$', views.history, name='history'),
    # программа прошедшей конвенции, если она заведена по дням
    re_path(r'^history/(?P<number>[0-9]+)/?$', views.program_start, name='archive'),
    re_path(r'^history/(?P<number>[0-9]+)/day-(?P<day>[0-9]+)/?$', views.program, name='archive_day'),
    re_path(r'^kontakty/?$', views.contacts, name='contacts'),
    re_path(r'^anketa/?$', views.registration, name='registration'),
    path('robots.txt', views.robots_txt),
]
