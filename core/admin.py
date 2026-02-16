from django.contrib import admin
from .models import Course, Specialist, Partner, News, PageContent


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'hours', 'instructor', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'instructor', 'description']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Specialist)
class SpecialistAdmin(admin.ModelAdmin):
    list_display = ['name', 'position', 'city', 'country', 'is_active', 'order']
    list_filter = ['is_active', 'country']
    search_fields = ['name', 'position', 'city']
    list_editable = ['order', 'is_active']


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ['name', 'website', 'is_active', 'order']
    list_filter = ['is_active']
    search_fields = ['name']
    list_editable = ['order', 'is_active']


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ['title', 'published_date', 'is_published']
    list_filter = ['is_published', 'published_date']
    search_fields = ['title', 'content']
    prepopulated_fields = {'slug': ('title',)}
    list_editable = ['is_published']
    date_hierarchy = 'published_date'


@admin.register(PageContent)
class PageContentAdmin(admin.ModelAdmin):
    list_display = ['slug', 'title', 'updated_at']
    search_fields = ['slug', 'title', 'content']