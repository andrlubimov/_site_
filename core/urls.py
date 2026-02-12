from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.index, name='index'),
    path('courses/', views.courses_list, name='courses_list'),
    path('courses/<slug:slug>/', views.course_detail, name='course_detail'),
    path('specialists/', views.specialists_list, name='specialists_list'),
    path('partners/', views.partners_list, name='partners_list'),
    path('news/', views.news_list, name='news_list'),
    path('news/<slug:slug>/', views.news_detail, name='news_detail'),
    path('page/<slug:slug>/', views.page_content, name='page_content'),
]