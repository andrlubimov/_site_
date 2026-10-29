"""Фильтры курсов для страниц «Программы» (/education/courses/) и «Расписание» (/page/timetable/).

Внутри одной группы отмеченные варианты объединяются через «или», между группами — через «и».
Параметры передаются в адресе (?type=online&age=infant…), поэтому отфильтрованной страницей можно поделиться.
"""
from django import forms
from django.db.models import Q

from .models import ChildAge, Course, HealthFeature, Teacher

HOURS_RANGES = {
    'upto10': (None, 10),
    '11-30': (11, 30),
    '31-60': (31, 60),
    'over60': (61, None),
}
HOURS_CHOICES = [
    ('upto10', 'до 10 ч'),
    ('11-30', '11–30 ч'),
    ('31-60', '31–60 ч'),
    ('over60', '60+ ч'),
]
# короче, чем в карточке курса, — чтобы «таблетки» помещались в узкую колонку
SKILL_FILTER_CHOICES = [
    ('beginner', 'Новичок'),
    ('basic', 'Есть база (1–3 мес.)'),
    ('advanced', 'Продвинутый'),
]


def search_key(text):
    return (text or '').lower().replace('ё', 'е')


class CourseFilterForm(forms.Form):
    # порядок в блоке фильтров: частые группы — сверху
    field_order = ['q', 'type', 'hours', 'direction', 'teacher', 'age', 'health', 'venue', 'skill']

    q = forms.CharField(label='Поиск', required=False, max_length=100, widget=forms.TextInput(attrs={
        'type': 'search', 'class': 'form-control form-control-sm', 'placeholder': 'Название или тема',
    }))
    hours = forms.MultipleChoiceField(label='Длительность', choices=HOURS_CHOICES, required=False,
                                      widget=forms.CheckboxSelectMultiple)
    teacher = forms.ModelChoiceField(label='Преподаватель', queryset=Teacher.objects.none(), required=False,
                                     to_field_name='slug', empty_label='Все преподаватели')
    age = forms.ModelMultipleChoiceField(label='Возраст детей', queryset=ChildAge.objects.all(), required=False,
                                         to_field_name='code', widget=forms.CheckboxSelectMultiple)
    health = forms.ModelMultipleChoiceField(label='Особенности здоровья', queryset=HealthFeature.objects.all(),
                                            required=False, to_field_name='code',
                                            widget=forms.CheckboxSelectMultiple)
    direction = forms.MultipleChoiceField(label='Направление', choices=Course.DIRECTION_CHOICES,
                                          required=False, widget=forms.CheckboxSelectMultiple)
    venue = forms.MultipleChoiceField(label='Место проведения', choices=Course.VENUE_CHOICES, required=False,
                                      widget=forms.CheckboxSelectMultiple)
    type = forms.MultipleChoiceField(label='Формат', choices=Course.TYPE_CHOICES, required=False,
                                     widget=forms.CheckboxSelectMultiple)
    skill = forms.MultipleChoiceField(label='Уровень учащегося', choices=SKILL_FILTER_CHOICES, required=False,
                                      widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, dated_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        if dated_only:  # «Расписание»: у дистанционных курсов дат нет — и выбирать их там незачем
            self.fields['type'].choices = [c for c in Course.TYPE_CHOICES if c[0] != Course.TYPE_DISTANCE]
        # в списке — только преподаватели, у которых есть курсы на сайте
        self.fields['teacher'].queryset = (Teacher.objects.filter(courses__is_active=True)
                                           .distinct().order_by('last_name', 'first_name'))
        self.fields['teacher'].widget.attrs['class'] = 'form-select form-select-sm'

    @property
    def is_filtered(self):
        return self.is_valid() and any(self.cleaned_data.values())

    def filter(self, queryset):
        """Применяет выбранные фильтры к queryset курсов"""
        if not self.is_valid():
            return queryset
        data = self.cleaned_data
        if data['q']:
            # поиск по названию курса и карточки и по краткому описанию; без учёта регистра и «ё»
            needle = search_key(data['q'].strip())
            found = [
                course.pk for course in queryset.select_related('card')
                if needle in search_key(' '.join([course.title, course.short_description,
                                                  course.card.title if course.card_id else '']))
            ]
            queryset = queryset.filter(pk__in=found)
        if data['hours']:
            hours_q = Q()
            for key in data['hours']:
                low, high = HOURS_RANGES[key]
                part = Q()
                if low is not None:
                    part &= Q(hours__gte=low)
                if high is not None:
                    part &= Q(hours__lte=high)
                hours_q |= part
            queryset = queryset.filter(hours_q)
        if data['teacher']:
            queryset = queryset.filter(teachers=data['teacher'])
        if data['age']:
            queryset = queryset.filter(child_ages__in=data['age'])
        if data['health']:
            queryset = queryset.filter(health_features__in=data['health'])
        if data['direction']:
            queryset = queryset.filter(direction__in=data['direction'])
        if data['venue']:
            queryset = queryset.filter(venue__in=data['venue'])
        if data['type']:
            queryset = queryset.filter(course_type__in=data['type'])
        if data['skill']:
            queryset = queryset.filter(skill_level__in=data['skill'])
        return queryset.distinct()
