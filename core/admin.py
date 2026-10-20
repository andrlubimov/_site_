from datetime import date

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import ValidationError
from django.db.models import Count, Max, Q
from django.forms.models import BaseInlineFormSet
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.text import Truncator
from PIL import Image

from .models import (
    Teacher, Course, CourseCard, CourseTeacher, CourseSchedule, CourseScheduleDay, Specialist, Representative, Partner,
    News, PageContent, AboutSection,
)
from .utils import format_rub


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ['last_name', 'first_name', 'patronymic', 'has_bio', 'courses_count']
    search_fields = ['first_name', 'last_name', 'patronymic']
    prepopulated_fields = {'slug': ('first_name', 'last_name')}
    readonly_fields = ['courses_overview']

    class Media:
        css = {'all': ['css/admin-course.css']}
    fieldsets = (
        (None, {'fields': ('last_name', 'first_name', 'patronymic', 'slug')}),
        ('Фотографии', {'fields': ('photo', 'photo_transparent')}),
        ('Страница преподавателя', {
            'fields': ('bio', 'courses_overview'),
            'description': 'На странице преподавателя показываются фото, описание и курсы, которые он ведёт. '
                           'Ссылка на неё — у имени и фото преподавателя на странице курса.',
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(courses_total=Count('courses', distinct=True))

    @admin.display(boolean=True, description='Есть описание')
    def has_bio(self, obj):
        return bool(obj.bio.strip())

    @admin.display(description='Курсов', ordering='courses_total')
    def courses_count(self, obj):
        return obj.courses_total

    @admin.display(description='Курсы преподавателя')
    def courses_overview(self, obj):
        if not obj or not obj.pk:
            return 'Курсы появятся здесь, когда преподаватель будет указан в карточке курса.'
        courses = obj.courses.order_by('title')
        if not courses:
            return 'Преподаватель пока не указан ни в одном курсе.'
        return format_html('<ul class="course-admin-schedule">{}</ul>', format_html_join(
            '', '<li><a href="{}">{}</a>{}</li>',
            ((reverse('admin:core_course_change', args=[c.pk]), c.title,
              '' if c.is_active else ' (скрыт на сайте)') for c in courses),
        ))


class CourseTeacherInline(admin.TabularInline):
    model = CourseTeacher
    extra = 0
    min_num = 1  # у курса должен быть хотя бы один преподаватель
    fields = ['teacher', 'order']
    autocomplete_fields = ['teacher']
    verbose_name_plural = 'Преподаватели'

    def get_formset(self, request, obj=None, **kwargs):
        kwargs['validate_min'] = True
        return super().get_formset(request, obj, **kwargs)


class CourseInCardInline(admin.TabularInline):
    """Курсы внутри карточки: подпись варианта и порядок строк. Состав меняется полем «Курсы» выше."""
    model = Course
    fk_name = 'card'
    fields = ['course_link', 'variant_label', 'card_position', 'course_type', 'hours']
    readonly_fields = ['course_link', 'course_type', 'hours']
    extra = 0
    can_delete = False
    verbose_name = 'Курс в карточке'
    verbose_name_plural = 'Строки карточки (подпись варианта и порядок)'
    ordering = ['card_position', 'pk']

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description='Курс')
    def course_link(self, obj):
        return format_html('<a href="{}">{}</a>', reverse('admin:core_course_change', args=[obj.pk]), obj.title)


class CourseCardForm(forms.ModelForm):
    courses = forms.ModelMultipleChoiceField(
        label='Курсы', queryset=Course.objects.order_by('title'),
        widget=FilteredSelectMultiple('курсы', is_stacked=False),
        help_text='Варианты одного курса: пакеты «Студент» и «Специалист», семинар и повышение квалификации. '
                  'Курс может быть только в одной карточке — при выборе он переносится из прежней.',
    )

    class Meta:
        model = CourseCard
        fields = ['title', 'courses', 'description_course', 'order', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description_course'].queryset = Course.objects.order_by('title')
        if self.instance.pk:
            self.fields['courses'].initial = self.instance.courses.all()

    def clean(self):
        # «описание из курса этой карточки» проверяем по курсам, выбранным в форме, — так можно выбрать
        # и курс, который добавляется в карточку прямо сейчас
        cleaned = super().clean()
        courses, source = cleaned.get('courses'), cleaned.get('description_course')
        if source and courses is not None and source not in courses:
            self.add_error('description_course', 'Выберите курс, включённый в эту карточку.')
        return cleaned


@admin.register(CourseCard)
class CourseCardAdmin(admin.ModelAdmin):
    form = CourseCardForm
    inlines = [CourseInCardInline]
    list_display = ['title', 'direction_label', 'variants_label', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    list_filter = ['is_active', 'courses__direction']
    search_fields = ['title', 'courses__title']
    readonly_fields = ['description_preview']
    fieldsets = (
        (None, {
            'fields': ('title', 'courses', 'description_course', 'description_preview'),
            'description': 'Карточка на странице «Программы» объединяет варианты одного курса. '
                           'Краткое описание карточки берётся из выбранного курса.',
        }),
        ('Показ на сайте', {'fields': ('order', 'is_active')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('courses').distinct()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        card = form.instance
        # порядок строк — как курсы выбраны в правой колонке виджета (браузер отправляет их по порядку)
        posted = [str(pk) for pk in form.data.getlist('courses')]
        selected = sorted(form.cleaned_data['courses'],
                          key=lambda c: posted.index(str(c.pk)) if str(c.pk) in posted else len(posted))
        card.courses.exclude(pk__in=[c.pk for c in selected]).update(card=None)
        position = max([c.card_position for c in card.courses.all()], default=-1) + 1
        for course in selected:
            if course.card_id != card.pk:
                Course.objects.filter(pk=course.pk).update(card=card, card_position=position)
                position += 1

    @admin.display(description='Направление')
    def direction_label(self, obj):
        directions = sorted({c.get_direction_display() for c in obj.courses.all() if c.direction})
        return ', '.join(directions) or '—'

    @admin.display(description='Варианты')
    def variants_label(self, obj):
        courses = sorted(obj.courses.all(), key=lambda c: (c.card_position, c.pk))
        return ' · '.join(c.variant_label or c.get_course_type_display() or c.title for c in courses) or '—'

    @admin.display(description='Описание в карточке')
    def description_preview(self, obj):
        if not obj or not obj.pk:
            return 'Появится после сохранения.'
        return obj.short_description or '—'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    inlines = [CourseTeacherInline]
    list_display = ['title', 'course_type', 'hours', 'price_label', 'teacher_names', 'order', 'is_active']
    list_filter = ['is_active', 'course_type', 'direction', 'venue', 'skill_level', 'child_ages', 'health_features']
    search_fields = ['title', 'slug', 'short_description', 'full_description', 'teachers__last_name']
    list_editable = ['order', 'is_active']
    prepopulated_fields = {'slug': ('title',)}
    autocomplete_fields = ['required_course', 'card']
    readonly_fields = ['schedule_overview']
    fieldsets = (
        ('Основное', {
            'fields': ('title', 'slug', 'short_description', 'full_description'),
        }),
        ('Карточка на странице «Программы»', {
            'fields': ('card', 'variant_label', 'card_position'),
            'description': 'Варианты одного курса (пакеты «Студент»/«Специалист», семинар и повышение '
                           'квалификации) показываются одной карточкой — строками внутри неё. Сами карточки, '
                           'их названия и состав — в разделе «Карточки курсов».',
        }),
        ('Содержание', {
            'fields': ('audience', 'program', 'hours'),
        }),
        ('Характеристики', {
            'fields': ('course_type', 'direction', 'venue', 'skill_level', 'child_ages', 'health_features'),
        }),
        ('Стоимость и документ по окончании курса', {
            'fields': ('base_price', 'has_diploma', 'diploma_price',
                       'has_qualification_certificate', 'qualification_certificate_price'),
            'description': 'По окончании курса слушатель получает сертификат о прохождении курса — '
                           'по базовой стоимости. Если у курса есть вариант с дипломом или с удостоверением '
                           'о повышении квалификации, отметьте его и укажите стоимость.',
        }),
        ('Требования', {
            'fields': ('required_course',),
        }),
        ('Расписание', {
            'fields': ('schedule_overview',),
        }),
        ('Показ на сайте', {
            'fields': ('order', 'is_active'),
        }),
    )

    class Media:
        css = {'all': ['css/admin-course.css']}
        js = ['js/admin-course.js']

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('course_teachers__teacher')

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name in ('child_ages', 'health_features'):
            kwargs['widget'] = forms.CheckboxSelectMultiple
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    @admin.display(description='Преподаватели')
    def teacher_names(self, obj):
        return obj.teacher_names or '—'

    @admin.display(description='Базовая стоимость', ordering='base_price')
    def price_label(self, obj):
        return format_rub(obj.base_price) or '—'

    @admin.display(description='Актуальные записи')
    def schedule_overview(self, obj):
        if not obj or not obj.pk:
            return 'Записи расписания можно добавить после сохранения курса.'
        today = date.today()
        schedules = obj.schedules.filter(
            Q(start_date=None) | Q(end_date__gte=today)
        ).prefetch_related('in_person_days')
        rows = format_html_join(
            '', '<li><a href="{}">{}</a>{}</li>',
            ((reverse('admin:core_courseschedule_change', args=[s.pk]), s.date_label or 'без дат',
              f' — {s.get_format_display()}' if s.format else '') for s in schedules),
        )
        return format_html(
            '<ul class="course-admin-schedule">{}</ul>'
            '<a class="addlink" href="{}?course={}">Добавить запись расписания</a>'
            '<a class="course-admin-schedule-all" href="{}?course__id__exact={}">Всё расписание курса</a>',
            rows or format_html('<li>Актуальных записей нет</li>'),
            reverse('admin:core_courseschedule_add'), obj.pk,
            reverse('admin:core_courseschedule_changelist'), obj.pk,
        )


class CourseTypeSelect(forms.Select):
    """Список курсов с типом курса в data-атрибуте — по нему JS показывает нужные поля дат"""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, 'instance', None)
        if instance is not None:
            option['attrs']['data-course-type'] = instance.course_type
        return option


class CourseScheduleDayFormSet(BaseInlineFormSet):
    """Очные занятия обязательны для очно-заочных курсов и должны попадать в даты проведения"""

    def clean(self):
        super().clean()
        schedule = self.instance
        if not schedule.course_id or schedule.course.course_type != Course.TYPE_BLENDED:
            return  # у остальных типов очные даты не используются (удаляются при сохранении)
        dates = [
            form.cleaned_data['date'] for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE') and form.cleaned_data.get('date')
        ]
        if not dates:
            raise ValidationError('Укажите хотя бы одну дату очного занятия.')
        if schedule.start_date and schedule.end_date:
            outside = [d for d in dates if not schedule.start_date <= d <= schedule.end_date]
            if outside:
                raise ValidationError('Очные занятия должны проходить в пределах дат курса: ' +
                                      ', '.join(f'{d:%d.%m.%Y}' for d in sorted(outside)))


class CourseScheduleDayInline(admin.TabularInline):
    model = CourseScheduleDay
    formset = CourseScheduleDayFormSet
    extra = 1
    verbose_name_plural = 'Даты очных занятий'


class ActualityFilter(admin.SimpleListFilter):
    title = 'актуальность'
    parameter_name = 'actual'

    def lookups(self, request, model_admin):
        return [('upcoming', 'Текущие и будущие'), ('past', 'Прошедшие')]

    def queryset(self, request, queryset):
        today = date.today()
        if self.value() == 'upcoming':
            return queryset.filter(Q(start_date=None) | Q(end_date__gte=today))
        if self.value() == 'past':
            return queryset.filter(end_date__lt=today)
        return queryset


@admin.register(CourseSchedule)
class CourseScheduleAdmin(admin.ModelAdmin):
    inlines = [CourseScheduleDayInline]
    list_display = ['dates', 'course_short', 'type_label', 'format', 'time_label', 'price_label', 'comment_short']
    list_display_links = ['dates', 'course_short']
    list_editable = ['format']
    list_filter = [ActualityFilter, 'course__course_type', 'format']
    search_fields = ['course__title', 'comment']
    list_select_related = ['course']
    date_hierarchy = 'start_date'
    fieldsets = (
        (None, {
            'fields': ('course', 'format'),
        }),
        ('Даты проведения', {
            'fields': (('start_date', 'end_date'), ('materials_from', 'materials_to'),
                       'access_days', ('time_from', 'time_to')),
            'description': '<span class="schedule-type-hint">Какие даты заполнять, зависит от типа курса.</span>',
        }),
        ('Стоимость и комментарий', {
            'fields': ('price_override', 'comment'),
        }),
    )

    class Media:
        css = {'all': ['css/admin-course.css']}
        js = ['js/admin-schedule.js']

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('in_person_days')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'course':
            kwargs['widget'] = CourseTypeSelect
            kwargs['queryset'] = Course.objects.order_by('title')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if form.instance.course.course_type != Course.TYPE_BLENDED:
            form.instance.in_person_days.all().delete()

    @admin.display(description='Курс', ordering='course__title')
    def course_short(self, obj):
        return format_html('<span title="{}">{}</span>', obj.course.title, Truncator(obj.course.title).chars(70))

    @admin.display(description='Тип курса', ordering='course__course_type')
    def type_label(self, obj):
        return obj.course.get_course_type_display() or '—'

    @admin.display(description='Даты', ordering='start_date')
    def dates(self, obj):
        label = obj.date_label or '—'
        days = obj.in_person_days_label
        return f'{label} (очно: {days})' if days else label

    @admin.display(description='Время')
    def time_label(self, obj):
        return obj.time_label or '—'

    @admin.display(description='Стоимость')
    def price_label(self, obj):
        if obj.price_override is not None:
            return f'{format_rub(obj.price_override)} (базовая {format_rub(obj.course.base_price) or "—"})'
        return format_rub(obj.price) or '—'

    @admin.display(description='Комментарий')
    def comment_short(self, obj):
        return (obj.comment[:60] + '…') if len(obj.comment) > 60 else obj.comment


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
