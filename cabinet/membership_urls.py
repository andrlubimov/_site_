"""Заявка на вступление в Ассоциацию — анкеты со страницы «Членство»"""
from django.urls import path

from . import views

app_name = 'membership'

urlpatterns = [
    path('membership/apply/person/', views.membership_apply, {'kind': 'person'}, name='apply_person'),
    path('membership/apply/organization/', views.membership_apply, {'kind': 'organization'},
         name='apply_organization'),
    path('membership/apply/done/', views.membership_apply_done, name='done'),
]
