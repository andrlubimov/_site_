"""Отложенные курсы на основном сайте — и без входа в личный кабинет"""
from django.urls import path

from . import views

app_name = 'postponed'

urlpatterns = [
    path('education/postponed/', views.postponed_public, name='list'),
    path('postponed/toggle/', views.postponed_toggle, name='toggle'),
]
