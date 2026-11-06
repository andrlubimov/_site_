from django import forms
from django.contrib import admin
from django.db import models
from django.db.models import Count
from django.utils.html import format_html

from .models import (
    Convention, ConventionDay, DayActivity, EventType, FeaturedSpeaker, Organizer, Partner, Partnership,
    PhotoContestWinner, Price, ProgramEvent, Speaker, Venue,
)

SMALL_TEXT = {models.TextField: {'widget': forms.Textarea(attrs={'rows': 2, 'cols': 40})}}


def thumb(image, height=40):
    if not image:
        return '—'
    return format_html('<img src="{}" style="height:{}px;max-width:120px;object-fit:contain">', image.url, height)


class ConventionDayInline(admin.TabularInline):
    model = ConventionDay
    extra = 0
    fields = ['date', 'events_total']
    readonly_fields = ['events_total']
    show_change_link = True
    verbose_name_plural = 'Дни (программа дня — по ссылке «Изменить»)'

    @admin.display(description='Мероприятий в программе')
    def events_total(self, obj):
        return obj.events.count() if obj.pk else '—'


class PriceInline(admin.TabularInline):
    model = Price
    extra = 0
    fields = ['kind', 'group', 'label', 'note', 'amount', 'unit', 'order']


class PartnershipInline(admin.TabularInline):
    model = Partnership
    extra = 0
    autocomplete_fields = ['partner']
    fields = ['partner', 'is_general_sponsor', 'order']


class FeaturedSpeakerInline(admin.TabularInline):
    model = FeaturedSpeaker
    extra = 0
    autocomplete_fields = ['speaker']
    fields = ['speaker', 'caption', 'order']


class PhotoContestWinnerInline(admin.TabularInline):
    model = PhotoContestWinner
    extra = 0
    fields = ['place', 'author', 'photo']


@admin.register(Convention)
class ConventionAdmin(admin.ModelAdmin):
    list_display = ['number', 'title', 'dates', 'place', 'is_published', 'is_current']
    list_display_links = ['number', 'title']
    inlines = [ConventionDayInline, PriceInline, PartnershipInline, FeaturedSpeakerInline, PhotoContestWinnerInline]
    fieldsets = (
        (None, {
            'fields': ('number', ('start_date', 'end_date'), 'city', 'place', 'venue', 'is_published'),
            'description': 'На сайте конвенции — текущая конвенция (опубликованная с самым большим номером): '
                           'её даты в шапке, программа, цены и партнёры. Прошедшие — в «Архиве». '
                           'Чтобы начать новый год, добавьте новую конвенцию со следующим номером.',
        }),
        ('Главная страница', {'fields': ('highlights',)}),
        ('Участие', {'fields': ('registration_url', 'price_note', 'price_list', 'regulations', 'offer')}),
        ('Проживание', {'fields': ('hotel_name', 'hotel_url', 'hotel_booking_url', 'hotel_note')}),
        ('Программа', {'fields': ('program_notice',)}),
        ('Архив', {'fields': ('archive_image', 'schedule_file'), 'classes': ('collapse',)}),
    )

    @admin.display(boolean=True, description='Текущая')
    def is_current(self, obj):
        current = Convention.objects.current()
        return bool(current and current.pk == obj.pk)


class DayActivityInline(admin.TabularInline):
    model = DayActivity
    extra = 0
    fields = ['title', 'hall', 'venue', 'order']


class ProgramEventInline(admin.TabularInline):
    model = ProgramEvent
    extra = 0
    fields = ['time', 'section', 'event_type', 'location', 'title', 'topic', 'speakers']
    autocomplete_fields = ['speakers']
    formfield_overrides = SMALL_TEXT


@admin.register(ConventionDay)
class ConventionDayAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'activities_list', 'events_total']
    list_filter = ['convention']
    fields = ['convention', 'date']
    inlines = [DayActivityInline, ProgramEventInline]

    def get_queryset(self, request):
        return (super().get_queryset(request).select_related('convention')
                .annotate(events_count=Count('events', distinct=True)))

    @admin.display(description='Что проходит')
    def activities_list(self, obj):
        return '; '.join(a.title for a in obj.activities.all()) or '—'

    @admin.display(description='Мероприятий', ordering='events_count')
    def events_total(self, obj):
        return obj.events_count


@admin.register(ProgramEvent)
class ProgramEventAdmin(admin.ModelAdmin):
    list_display = ['time', 'title', 'day', 'section', 'event_type', 'location', 'speakers_list']
    list_filter = ['day__convention', 'day', 'section', 'event_type']
    search_fields = ['title', 'topic', 'speakers__name']
    autocomplete_fields = ['speakers']
    list_select_related = ['day__convention', 'event_type']
    fields = ['day', 'section', 'time', 'event_type', 'location', 'title', 'topic', 'speakers']

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('speakers')

    @admin.display(description='Спикеры')
    def speakers_list(self, obj):
        return ', '.join(s.name for s in obj.speakers.all())


@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'color_sample', 'color', 'show_label', 'order']
    list_editable = ['color', 'show_label', 'order']

    @admin.display(description='')
    def color_sample(self, obj):
        return format_html('<span style="display:inline-block;width:1.2em;height:1.2em;border-radius:3px;'
                           'background:{}"></span>', obj.color)


@admin.register(Speaker)
class SpeakerAdmin(admin.ModelAdmin):
    list_display = ['name', 'photo_thumb', 'details', 'events_total']
    search_fields = ['name', 'details']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(events_count=Count('events', distinct=True))

    @admin.display(description='Фото')
    def photo_thumb(self, obj):
        return thumb(obj.photo)

    @admin.display(description='Выступлений', ordering='events_count')
    def events_total(self, obj):
        return obj.events_count


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ['name', 'logo_thumb', 'website', 'conventions']
    search_fields = ['name']

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('partnerships__convention')

    @admin.display(description='Логотип')
    def logo_thumb(self, obj):
        return thumb(obj.logo)

    @admin.display(description='Конвенции')
    def conventions(self, obj):
        return ', '.join(str(p.convention.number) for p in obj.partnerships.all()) or '—'


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ['name', 'address']
    search_fields = ['name', 'address']


@admin.register(PhotoContestWinner)
class PhotoContestWinnerAdmin(admin.ModelAdmin):
    list_display = ['author', 'place', 'convention', 'photo_thumb']
    list_filter = ['convention']

    @admin.display(description='Фото')
    def photo_thumb(self, obj):
        return thumb(obj.photo, 60)


@admin.register(Organizer)
class OrganizerAdmin(admin.ModelAdmin):
    list_display = ['name', 'photo_thumb', 'group', 'role', 'phone', 'email', 'order']
    list_editable = ['order']
    list_filter = ['group']

    @admin.display(description='Фото')
    def photo_thumb(self, obj):
        return thumb(obj.photo)
