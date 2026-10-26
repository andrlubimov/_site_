from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = 'cabinet'

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.CabinetLoginView.as_view(), name='login'),
    path('register/', views.register, name='register'),
    path('logout/', LogoutView.as_view(next_page='core:index'), name='logout'),
    # разделы кабинета (названия и порядок в меню — views.SECTIONS)
    path('courses/', views.courses, name='courses'),
    path('courses/postponed/', views.postponed, name='postponed'),
    path('my-courses/', views.my_courses, name='my_courses'),
    path('my-courses/upcoming/', views.my_courses, {'status': 'upcoming'}, name='upcoming'),
    path('my-courses/current/', views.my_courses, {'status': 'current'}, name='current'),
    path('my-courses/completed/', views.my_courses, {'status': 'completed'}, name='completed'),
    path('membership/', views.membership, name='membership'),
    path('certificates/', views.certificates, name='certificates'),
    path('certificates/<int:pk>/file/', views.certificate_file, name='certificate_file'),
    path('profile/', views.profile, name='profile'),
    # запись на курс — кнопка «Записаться» у даты на странице курса
    path('enroll/', views.enroll, name='enroll'),
    path('enroll/auth/', views.enroll_auth, name='enroll_auth'),
    path('enroll/finish/', views.enroll_finish, name='enroll_finish'),
]
