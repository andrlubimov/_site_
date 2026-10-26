from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .forms import keep_country
from .models import Certificate, Enrollment, Membership, Profile, add_years
from .phone import country_name_choices


class ProfileAdminForm(forms.ModelForm):
    """Страна — из того же списка, что при регистрации"""
    country = forms.ChoiceField(label='Страна', required=False, choices=country_name_choices())

    class Meta:
        model = Profile
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        keep_country(self.fields['country'], self.instance.country)


class ProfileInline(admin.StackedInline):
    model = Profile
    form = ProfileAdminForm
    can_delete = False
    verbose_name = verbose_name_plural = 'Данные из регистрации в личном кабинете'
    fields = ['middle_name', 'birth_date', 'phone', 'country', 'city', 'about', 'avatar']


class MembershipInline(admin.StackedInline):
    model = Membership
    can_delete = False
    verbose_name = verbose_name_plural = 'Членство в Ассоциации'
    fields = ['status', 'start_date', 'next_fee_date', 'show_on_site']


class EnrollmentInline(admin.TabularInline):
    """Выбирается запись расписания — курс и даты обучения подтягиваются из неё"""
    model = Enrollment
    extra = 0
    verbose_name_plural = 'Купленные курсы — «Мои курсы» в личном кабинете'
    fields = ['schedule', 'course', 'start_date', 'end_date']
    readonly_fields = ['course', 'start_date', 'end_date']
    autocomplete_fields = ['schedule']


class CertificateInline(admin.TabularInline):
    model = Certificate
    extra = 0
    verbose_name_plural = 'Сертификаты и удостоверения — «Мои сертификаты» в личном кабинете'
    fields = ['title', 'course', 'number', 'issued_on', 'file']
    autocomplete_fields = ['course']


admin.site.unregister(User)


@admin.register(User)
class CabinetUserAdmin(UserAdmin):
    """Пользователи сайта: сотрудники и зарегистрированные в личном кабинете (логин — email)"""
    inlines = [ProfileInline, MembershipInline, EnrollmentInline, CertificateInline]
    list_display = ['username', 'last_name', 'first_name', 'phone', 'membership_status', 'date_joined', 'is_staff']
    list_select_related = ['profile', 'membership']
    list_filter = ['membership__status', 'is_staff', 'is_active']

    def get_inline_instances(self, request, obj=None):
        # новому пользователю из админки профиль не нужен: он заполняется при регистрации на сайте
        return super().get_inline_instances(request, obj) if obj else []

    @admin.display(description='Телефон', ordering='profile__phone')
    def phone(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.phone_display if profile else '—'

    @admin.display(description='Членство', ordering='membership__status')
    def membership_status(self, obj):
        membership = getattr(obj, 'membership', None)
        return membership.get_status_display() if membership else '—'


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'full_name', 'status', 'start_date', 'next_fee_date', 'show_on_site']
    list_filter = ['status', 'show_on_site']
    search_fields = ['user__username', 'user__last_name', 'user__first_name']
    list_select_related = ['user']
    autocomplete_fields = ['user']
    actions = ['fee_paid', 'show_on_site', 'hide_from_site']

    @admin.display(description='Имя', ordering='user__last_name')
    def full_name(self, obj):
        return obj.user.get_full_name()

    @admin.action(description='Взнос получен: следующий — через год')
    def fee_paid(self, request, queryset):
        moved = 0
        for membership in queryset:
            fee_date = membership.next_fee_date or membership.start_date
            if fee_date:
                membership.next_fee_date = add_years(fee_date)
                membership.save(update_fields=['next_fee_date'])
                moved += 1
        self.message_user(request, f'Дата следующего взноса перенесена на год: {moved}.', messages.SUCCESS)

    @admin.action(description='Показывать на сайте (раздел «Членство в ассоциации» на главной)')
    def show_on_site(self, request, queryset):
        self.message_user(request, f'Показываются на сайте: {queryset.update(show_on_site=True)}.', messages.SUCCESS)

    @admin.action(description='Скрыть с сайта')
    def hide_from_site(self, request, queryset):
        self.message_user(request, f'Скрыты с сайта: {queryset.update(show_on_site=False)}.', messages.SUCCESS)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    """Выбирается запись расписания — курс и даты обучения подтягиваются из неё"""
    list_display = ['user', 'course', 'start_date', 'end_date', 'created_at']
    list_filter = ['start_date']
    search_fields = ['user__username', 'user__last_name', 'course__title']
    list_select_related = ['user', 'course']
    fields = ['user', 'schedule', 'course', 'start_date', 'end_date']
    readonly_fields = ['course', 'start_date', 'end_date']
    autocomplete_fields = ['user', 'schedule']
    date_hierarchy = 'start_date'


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'course', 'number', 'issued_on']
    search_fields = ['title', 'number', 'user__username', 'user__last_name', 'course__title']
    list_select_related = ['user', 'course']
    autocomplete_fields = ['user', 'course']
    date_hierarchy = 'issued_on'
