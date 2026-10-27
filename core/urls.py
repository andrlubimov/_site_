from django.urls import path, re_path
from django.views.generic import RedirectView

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.index, name='index'),
    # Курсы — по тем же адресам, что и на старом сайте: grudnichkovoe-plavanie.ru/education/courses/<адрес>/
    path('education/courses/', views.courses_list, name='courses_list'),
    path('education/courses/<slug:slug>/', views.course_detail, name='course_detail'),
    # ссылки старого сайта вели на конкретную дату: /education/courses/<адрес>/<ддммгггг>
    re_path(r'^education/courses/(?P<slug>[-a-zA-Z0-9_]+)/(?P<legacy>\d+)/?$', views.legacy_course_redirect),
    path('education/teachers/', views.teachers_list, name='teachers_list'),
    path('education/teachers/<slug:slug>/', views.teacher_detail, name='teacher_detail'),
    # прежние адреса нового сайта
    path('courses/', RedirectView.as_view(pattern_name='core:courses_list', permanent=True)),
    path('courses/<slug:slug>/', views.legacy_course_redirect),
    path('specialists/', views.representatives_list, name='specialists_list'),
    path('partners/', views.partners_list, name='partners_list'),
    path('news/', views.news_list, name='news_list'),
    path('news/<slug:slug>/', views.news_detail, name='news_detail'),
    path('page/<slug:slug>/', views.page_content, name='page_content'),
    # «Сведения об образовательной организации» на старом сайте — /information/
    path('information/', RedirectView.as_view(url='/page/info/', permanent=True)),
    # «Членство» и анкеты на старом сайте
    path('association/membership', RedirectView.as_view(url='/page/membership/', permanent=True)),
    path('association/privatemembership', RedirectView.as_view(pattern_name='membership:apply_person',
                                                               permanent=True)),
    path('association/corporativemembership', RedirectView.as_view(pattern_name='membership:apply_organization',
                                                                   permanent=True)),
]
