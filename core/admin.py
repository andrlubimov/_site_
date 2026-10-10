from django.contrib import admin, messages
from django.db.models import Max
from django.templatetags.static import static
from django.utils.html import format_html
from PIL import Image

from .models import (
    Teacher, Course, CourseTeacher, CourseSession, Specialist, Representative, Partner, News, PageContent,
    AboutSection,
)


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ['last_name', 'first_name', 'patronymic']
    search_fields = ['first_name', 'last_name', 'patronymic']


class CourseTeacherInline(admin.TabularInline):
    model = CourseTeacher
    extra = 1
    fields = ['teacher', 'order']
    autocomplete_fields = ['teacher']


class CourseSessionInline(admin.TabularInline):
    model = CourseSession
    extra = 1
    fields = ['start_date', 'end_date', 'location', 'price', 'note']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    inlines = [CourseTeacherInline, CourseSessionInline]
    list_display = ['title', 'kind', 'hours', 'teacher_names', 'order', 'is_active', 'created_at']
    list_filter = ['is_active', 'kind', 'created_at']
    search_fields = ['title', 'description', 'teachers__last_name']
    list_editable = ['order', 'is_active']
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = (
        ('Название курса', {
            'fields': ('title', 'slug', 'kind'),
        }),
        ('Информация о курсе', {
            'fields': ('description', 'audience', 'program', 'hours', 'image'),
        }),
        ('Настройки', {
            'fields': ('order', 'is_active'),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('course_teachers__teacher')

    @admin.display(description='Преподаватели')
    def teacher_names(self, obj):
        return obj.teacher_names or '—'


@admin.register(Specialist)
class SpecialistAdmin(admin.ModelAdmin):
    list_display = ['name', 'position', 'city', 'country', 'is_active', 'order']
    list_filter = ['is_active', 'country']
    search_fields = ['name', 'position', 'city']
    list_editable = ['order', 'is_active']


@admin.register(Representative)
class RepresentativeAdmin(admin.ModelAdmin):
    list_display = ['name', 'kind', 'city', 'country', 'has_coordinates', 'is_active', 'order']
    list_filter = ['kind', 'is_active', 'country']
    search_fields = ['name', 'city', 'country', 'contact_name']
    list_editable = ['is_active', 'order']
    fieldsets = (
        (None, {'fields': ('kind', 'name', 'logo', 'contact_name')}),
        ('Расположение', {'fields': ('city', 'country', 'latitude', 'longitude')}),
        ('Контакты', {'fields': ('website', 'email', 'phone')}),
        ('Настройки', {'fields': ('is_active', 'order')}),
    )

    @admin.display(boolean=True, description='На глобусе')
    def has_coordinates(self, obj):
        return obj.has_coordinates


def logo_has_transparency(field_file):
    """Есть ли у логотипа прозрачные пиксели (иначе на круге будет белый прямоугольник)"""
    try:
        field_file.open('rb')
        with Image.open(field_file) as img:
            if img.mode == 'P':
                return 'transparency' in img.info
            if img.mode not in ('RGBA', 'LA'):
                return False
            return img.getchannel('A').getextrema()[0] < 255
    except Exception:
        return True  # не мешаем сохранению, если файл не прочитался
    finally:
        field_file.close()


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ['logo_thumb', 'name', 'city', 'country', 'website', 'is_active', 'order']
    list_display_links = ['logo_thumb', 'name']
    list_filter = ['is_active', 'country']
    search_fields = ['name', 'description', 'city']
    list_editable = ['order', 'is_active']
    readonly_fields = ['logo_preview']
    fieldsets = (
        (None, {
            'fields': ('name', 'logo', 'logo_preview', 'description'),
            'description': 'Партнёр появится на странице «Партнеры» спасательным кругом в бассейне. '
                           'При наведении на круг показывается описание, при нажатии открывается сайт.',
        }),
        ('Расположение', {'fields': ('city', 'country')}),
        ('Сайт', {'fields': ('website',)}),
        ('Показ на сайте', {'fields': ('is_active', 'order')}),
    )

    class Media:
        css = {'all': ['css/admin-partner.css']}
        js = ['js/admin-partner-logo.js']

    @admin.display(description='Логотип')
    def logo_thumb(self, obj):
        if not obj.logo:
            return '—'
        return format_html('<img src="{}" alt="" class="partner-admin-thumb">', obj.logo.url)

    @admin.display(description='Как будет выглядеть')
    def logo_preview(self, obj):
        logo = obj.logo.url if obj and obj.logo else ''
        return format_html(
            '<div class="partner-admin-preview" data-empty-text="Выберите файл логотипа — здесь появится круг с ним">'
            '<img class="partner-admin-ring" src="{}" alt="">'
            '<img class="partner-admin-logo" src="{}" alt=""{}>'
            '</div>',
            static('lifebuoy.png'), logo, '' if logo else format_html(' hidden'),
        )

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        # новый партнёр по умолчанию встаёт в конец бассейна
        initial.setdefault('order', (Partner.objects.aggregate(m=Max('order'))['m'] or 0) + 1)
        return initial

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if 'logo' in form.changed_data and obj.logo and not logo_has_transparency(obj.logo):
            messages.warning(request, f'У логотипа «{obj.name}» нет прозрачного фона — на спасательном круге '
                                      f'он будет в белом прямоугольнике. Лучше загрузить PNG с прозрачностью.')


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

@admin.register(AboutSection)
class AboutSectionAdmin(admin.ModelAdmin):
    """Блоки фиксированы шаблоном страницы — их можно только редактировать."""
    list_display = ['__str__', 'title', 'updated_at']
    readonly_fields = ['key']
    fields = ['key', 'title', 'content']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
