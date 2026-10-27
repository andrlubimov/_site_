from types import SimpleNamespace

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError, models
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone

from .contact_defaults import CONTACT_DEFAULTS, MAP_POINT
from .utils import format_date_range, format_day_list, plural_ru, sentence_case, slugify_ru


def unique_slug(model, text, pk=None, fallback='page'):
    """Латинский адрес страницы из русского текста; при совпадении добавляется -2, -3…"""
    base = slugify_ru(text) or fallback
    slug, n = base, 2
    while model.objects.filter(slug=slug).exclude(pk=pk).exists():
        slug, n = f'{base}-{n}', n + 1
    return slug


class Teacher(models.Model):
    """Модель преподавателя"""
    first_name = models.CharField('Имя', max_length=100)
    last_name = models.CharField('Фамилия', max_length=100)
    patronymic = models.CharField('Отчество', max_length=100, blank=True)
    photo = models.ImageField('Фотография с фоном', upload_to='teachers/', blank=True, null=True)
    photo_transparent = models.ImageField(
        'Фотография без фона', upload_to='teachers/transparent/', blank=True, null=True
    )
    slug = models.SlugField(
        'Адрес страницы', max_length=120, unique=True, blank=True,
        help_text='Латиница: grudnichkovoe-plavanie.ru/education/teachers/адрес/. '
                  'Если оставить пустым, заполнится из имени и фамилии.',
    )
    bio = models.TextField(
        'Описание', blank=True,
        help_text='Показывается на странице преподавателя. Абзацы разделяйте пустой строкой.',
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name='Аккаунт в личном кабинете', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='teacher',
        help_text='Преподаватели — члены Ассоциации: членство и вход в личный кабинет — через этот аккаунт.',
    )

    class Meta:
        verbose_name = 'Преподаватель'
        verbose_name_plural = 'Преподаватели'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.last_name} {self.first_name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Teacher, f'{self.first_name} {self.last_name}', self.pk, 'teacher')
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_absolute_url(self):
        return reverse('core:teacher_detail', kwargs={'slug': self.slug})

    @property
    def initials(self):
        return f"{self.first_name[:1]}{self.last_name[:1]}".upper()

    @property
    def display_name(self):
        """Имя, отчество и фамилия — для страницы преподавателя"""
        return ' '.join(part for part in (self.first_name, self.patronymic, self.last_name) if part)


class ChildAge(models.Model):
    """Справочник «Возраст детей» (грудной, ранний, дошкольный)"""
    code = models.SlugField('Код', max_length=30, unique=True)
    name = models.CharField('Название', max_length=100)
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Возраст детей'
        verbose_name_plural = 'Возраст детей'
        ordering = ['order']

    def __str__(self):
        return self.name


class HealthFeature(models.Model):
    """Справочник «Особенности здоровья детей» (нормотипичные, особой заботы, беременные)"""
    code = models.SlugField('Код', max_length=30, unique=True)
    name = models.CharField('Название', max_length=100)
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Особенность здоровья'
        verbose_name_plural = 'Особенности здоровья детей'
        ordering = ['order']

    def __str__(self):
        return self.name


class Course(models.Model):
    """Обучающий курс. Даты проведения — в расписании (CourseSchedule)."""
    TYPE_IN_PERSON = 'in_person'
    TYPE_BLENDED = 'blended'
    TYPE_DISTANCE = 'distance'
    TYPE_ONLINE = 'online'
    TYPE_CHOICES = [
        (TYPE_IN_PERSON, 'Очный'),
        (TYPE_BLENDED, 'Очно-заочный'),
        (TYPE_DISTANCE, 'Дистанционный'),
        (TYPE_ONLINE, 'Онлайн'),
    ]
    DATED_TYPES = (TYPE_IN_PERSON, TYPE_ONLINE, TYPE_BLENDED)

    MEMBER_DISCOUNT_PERCENT = 20  # скидка для членов Ассоциации (на старом сайте — тоже 20%)
    ALUMNI_DISCOUNT_PERCENT = 10  # скидка для тех, кто уже обучался в Ассоциации

    DIRECTION_CHOICES = [
        ('land', 'Сухопутные'),
        ('swimming', 'Плавание'),
        ('hydrorehab', 'Гидрореабилитация'),
        ('management', 'Администрирование'),
    ]
    DIRECTION_ICONS = {  # значки Bootstrap Icons для карточек на странице «Программы»
        'land': 'bi-person-arms-up',
        'swimming': 'bi-water',
        'hydrorehab': 'bi-heart-pulse',
        'management': 'bi-briefcase',
    }
    TYPE_ICONS = {
        TYPE_IN_PERSON: 'bi-geo-alt-fill',
        TYPE_BLENDED: 'bi-shuffle',
        TYPE_DISTANCE: 'bi-laptop',
        TYPE_ONLINE: 'bi-camera-video',
    }
    DOC_CERTIFICATE = 'certificate'
    DOC_QUALIFICATION = 'qualification'
    DOCUMENT_CHOICES = [
        (DOC_CERTIFICATE, 'Сертификат о прохождении курса'),
        (DOC_QUALIFICATION, 'Удостоверение о повышении квалификации'),
    ]
    DOCUMENT_NOTES = {DOC_QUALIFICATION: 'с занесением данных в ФИС ФРДО'}

    VENUE_CHOICES = [
        ('pool', 'В бассейне'),
        ('gym', 'В спортзале'),
        ('home', 'На дому'),
    ]
    SKILL_CHOICES = [
        ('beginner', 'Новичок'),
        ('basic', '1–3 месяца практики и базовый курс за плечами'),
        ('advanced', 'Продвинутый'),
    ]

    title = models.CharField('Название', max_length=255)
    short_description = models.TextField(
        'Краткое описание',
        help_text='1–3 предложения: показывается в карточках курсов, в календаре и вверху страницы курса.',
    )
    full_description = models.TextField(
        'Развёрнутое описание', blank=True,
        help_text='Показывается на странице курса под кратким описанием. '
                  'Абзацы разделяйте пустой строкой.',
    )
    slug = models.SlugField(
        'Адрес страницы', max_length=100, unique=True,
        help_text='Латинские буквы, цифры и дефисы: grudnichkovoe-plavanie.ru/education/courses/адрес-курса/',
    )
    audience = models.TextField('Для кого', help_text='На кого рассчитан курс.')
    program = models.TextField(
        'Программа курса',
        help_text='Абзацы разделяйте пустой строкой. Одиночный перенос строки — перенос внутри абзаца.',
    )
    hours = models.PositiveIntegerField('Учебные часы')
    teachers = models.ManyToManyField(
        Teacher, verbose_name='Преподаватели', through='CourseTeacher',
        related_name='courses', blank=True,
    )
    child_ages = models.ManyToManyField(ChildAge, verbose_name='Возраст детей', related_name='courses')
    direction = models.CharField('Направление работы', max_length=20, choices=DIRECTION_CHOICES)
    health_features = models.ManyToManyField(
        HealthFeature, verbose_name='Особенности здоровья детей', related_name='courses',
    )
    venue = models.CharField('Место проведения', max_length=20, choices=VENUE_CHOICES)
    skill_level = models.CharField('Навыки учащегося', max_length=20, choices=SKILL_CHOICES)
    course_type = models.CharField(
        'Тип', max_length=20, choices=TYPE_CHOICES,
        help_text='От типа зависят даты в расписании: у очных и онлайн — начало и конец, '
                  'у очно-заочных — ещё очные дни и доступ к материалам, у дистанционных — срок доступа.',
    )
    main_document = models.CharField(
        'Документ по окончании курса', max_length=20, choices=DOCUMENT_CHOICES, default=DOC_CERTIFICATE,
        help_text='По окончании курсов повышения квалификации выдаётся удостоверение, остальных — сертификат.',
    )
    base_price = models.PositiveIntegerField(
        'Базовая стоимость, ₽', null=True,
        help_text='Стоимость обучения с документом, выбранным выше.',
    )
    has_diploma = models.BooleanField('Есть вариант с дипломом', default=False,
                                      help_text='Диплом — для слушателей с высшим образованием.')
    diploma_price = models.PositiveIntegerField('Стоимость с дипломом, ₽', null=True, blank=True)
    has_qualification_certificate = models.BooleanField(
        'Есть вариант с удостоверением о повышении квалификации', default=False,
        help_text='Удостоверение — для слушателей со средним или высшим физкультурным образованием.',
    )
    qualification_certificate_price = models.PositiveIntegerField(
        'Стоимость с удостоверением, ₽', null=True, blank=True,
    )
    required_course = models.ForeignKey(
        'self', verbose_name='Необходимый курс для старта', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='next_courses',
        help_text='Курс, который нужно пройти перед этим.',
    )

    # Варианты одного курса (пакет «Студент»/«Специалист», семинар/повышение квалификации)
    # на странице «Программы» показываются одной карточкой — CourseCard
    card = models.ForeignKey(
        'CourseCard', verbose_name='Карточка курса', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='courses',
        help_text='На странице «Программы» курсы одной карточки показываются вместе — строками внутри неё.',
    )
    card_position = models.PositiveSmallIntegerField(
        'Порядок в карточке', default=0, help_text='Чем меньше число, тем выше строка курса в карточке.',
    )
    variant_label = models.CharField(
        'Название варианта', max_length=100, blank=True,
        help_text='Строка внутри карточки, например «Пакет «Студент»», «Семинар», '
                  '«Повышение квалификации». Если пусто, пишется тип курса.',
    )

    order = models.IntegerField('Место на странице', default=0)
    is_active = models.BooleanField('Показывать на сайте', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Курс'
        verbose_name_plural = 'Курсы'
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title

    def clean(self):
        errors = {}
        for flag, price_field in (('has_diploma', 'diploma_price'),
                                  ('has_qualification_certificate', 'qualification_certificate_price')):
            if getattr(self, flag):
                if getattr(self, price_field) is None:
                    errors[price_field] = 'Укажите стоимость для этого варианта документа.'
            else:
                setattr(self, price_field, None)  # вариант выключен — цена не нужна
        if self.main_document == self.DOC_QUALIFICATION and self.has_qualification_certificate:
            errors['has_qualification_certificate'] = (
                'Удостоверение уже выбрано документом по окончании курса — отдельный вариант с ним не нужен.')
        if self.required_course_id:
            if self.pk and self.required_course_id == self.pk:
                errors['required_course'] = 'Курс не может требовать сам себя.'
            else:
                # защита от цикла: A требует B, B требует … A
                seen, current = {self.pk}, self.required_course
                while current is not None:
                    if current.pk in seen:
                        errors['required_course'] = 'Получается замкнутая цепочка обязательных курсов.'
                        break
                    seen.add(current.pk)
                    current = current.required_course
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Course, self.title, self.pk, 'course')
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('core:course_detail', kwargs={'slug': self.slug})

    @property
    def is_dated(self):
        return self.course_type in self.DATED_TYPES

    @property
    def list_title(self):
        """Название курса без карточки на странице «Программы» (заглавные буквы — в обычные)"""
        return sentence_case(self.title)

    @property
    def display_title(self):
        """Заголовок страницы курса: общее название карточки (там регистр выверен вручную),
        вариант — пакет, семинар — показывается рядом переключателем"""
        return self.card.title if self.card_id else self.list_title

    @property
    def variant_name(self):
        """Строка варианта внутри карточки"""
        return self.variant_label or self.get_course_type_display()

    @property
    def card_key(self):
        """Карточка на странице «Программы»: варианты одного курса (CourseCard) — одна карточка.
        Сердечком откладывается сразу вся карточка (cabinet/postponed.py)."""
        return f'card-{self.card_id}' if self.card_id else f'course-{self.pk}'

    @property
    def direction_icon(self):
        return self.DIRECTION_ICONS.get(self.direction, 'bi-mortarboard')

    @property
    def type_icon(self):
        return self.TYPE_ICONS.get(self.course_type, 'bi-mortarboard')

    @property
    def teacher_list(self):
        """Преподаватели в заданном порядке (используйте prefetch_related('course_teachers__teacher'))"""
        return [link.teacher for link in self.course_teachers.all()]

    @property
    def main_teacher(self):
        teachers = self.teacher_list
        return teachers[0] if teachers else None

    @property
    def teacher_names(self):
        return ', '.join(t.full_name for t in self.teacher_list)

    @property
    def hours_label(self):
        return f'{self.hours} {plural_ru(self.hours, ("учебный час", "учебных часа", "учебных часов"))}'

    def discounted_price(self, percent):
        """Базовая стоимость минус percent процентов"""
        if self.base_price is None:
            return None
        return round(self.base_price * (100 - percent) / 100)

    @property
    def member_price(self):
        """Стоимость для членов Ассоциации"""
        return self.discounted_price(self.MEMBER_DISCOUNT_PERCENT)

    @property
    def alumni_price(self):
        """Стоимость для тех, кто обучался у нас ранее"""
        return self.discounted_price(self.ALUMNI_DISCOUNT_PERCENT)

    @property
    def documents(self):
        """Документ по окончании курса: (название, примечание, стоимость). Первым — основной документ
        (сертификат или, у курсов повышения квалификации, удостоверение) по базовой стоимости."""
        docs = [(self.get_main_document_display(), self.DOCUMENT_NOTES.get(self.main_document, ''), self.base_price)]
        if self.has_diploma:
            docs.append(('Диплом', 'для слушателей с высшим образованием', self.diploma_price))
        if self.has_qualification_certificate and self.main_document != self.DOC_QUALIFICATION:
            docs.append(('Удостоверение о повышении квалификации',
                         'для слушателей со средним или высшим физкультурным образованием',
                         self.qualification_certificate_price))
        return docs


class CourseCard(models.Model):
    """Карточка на странице «Программы»: несколько вариантов одного курса (пакеты «Студент» /
    «Специалист», семинар и повышение квалификации) показываются вместе, строками внутри неё."""
    title = models.CharField(
        'Название', max_length=255,
        help_text='Общее название курса — без «Пакет «Студент»», «Семинар», «Повышение квалификации».',
    )
    description_course = models.ForeignKey(
        'Course', verbose_name='Описание взять из курса', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
        help_text='Краткое описание карточки берётся из этого курса. Если не выбран — из первого курса карточки.',
    )
    order = models.IntegerField('Порядок', default=0)
    is_active = models.BooleanField('Показывать на сайте', default=True)

    class Meta:
        verbose_name = 'Карточка курса'
        verbose_name_plural = 'Карточки курсов'
        ordering = ['order', 'title']

    def __str__(self):
        return self.title

    @property
    def ordered_courses(self):
        return list(self.courses.order_by('card_position', 'pk'))

    @property
    def description_source(self):
        """Курс, из которого берётся краткое описание карточки"""
        if self.description_course_id:
            return self.description_course
        courses = self.ordered_courses
        return next((c for c in courses if c.short_description.strip()), courses[0] if courses else None)

    @property
    def short_description(self):
        source = self.description_source
        return source.short_description if source else ''


class CourseTeacher(models.Model):
    """Преподаватель курса; порядок задаёт, кто указан первым (его фото на главной)"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='course_teachers')
    teacher = models.ForeignKey(Teacher, verbose_name='Преподаватель', on_delete=models.CASCADE,
                                related_name='course_links')
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Преподаватель курса'
        verbose_name_plural = 'Преподаватели курса'
        ordering = ['order', 'pk']
        unique_together = [('course', 'teacher')]

    def __str__(self):
        return str(self.teacher)


class CourseSchedule(models.Model):
    """Запись расписания курса. Какие даты заполняются — зависит от типа курса."""
    FORMAT_CHOICES = [
        ('individual', 'Индивидуальный'),
        ('group', 'Групповой'),
        ('corporate', 'Корпоративный'),
        ('away', 'Выездной'),
    ]

    course = models.ForeignKey(Course, verbose_name='Курс', on_delete=models.CASCADE, related_name='schedules')
    format = models.CharField('Формат проведения', max_length=20, choices=FORMAT_CHOICES)
    start_date = models.DateField('Дата начала', null=True, blank=True)
    end_date = models.DateField('Дата окончания', null=True, blank=True)
    materials_from = models.DateField('Доступ к материалам: с', null=True, blank=True)
    materials_to = models.DateField('Доступ к материалам: по', null=True, blank=True)
    access_days = models.PositiveSmallIntegerField('Срок доступа, дней', null=True, blank=True)
    time_from = models.TimeField('Занятия: начало', null=True, blank=True,
                                 help_text='Примерное время, например 8:00.')
    time_to = models.TimeField('Занятия: окончание', null=True, blank=True, help_text='Например 18:00.')
    price_override = models.PositiveIntegerField(
        'Стоимость, ₽', null=True, blank=True,
        help_text='Заполните, только если стоимость отличается от базовой стоимости курса.',
    )
    comment = models.TextField('Комментарий', blank=True)

    class Meta:
        verbose_name = 'Запись расписания'
        verbose_name_plural = 'Расписание курсов'
        ordering = [models.F('start_date').asc(nulls_last=True), 'pk']

    def __str__(self):
        label = self.date_label
        return f'{self.course} — {label}' if label else str(self.course)

    def clean(self):
        if not self.course_id:
            return
        course_type = self.course.course_type
        if not course_type:
            raise ValidationError({'course': 'У курса не указан тип — укажите его в карточке курса.'})
        errors = {}

        def require(*fields):
            for name in fields:
                if getattr(self, name) in (None, ''):
                    errors[name] = 'Обязательное поле для этого типа курса.'

        if course_type == Course.TYPE_DISTANCE:
            require('access_days')
            if self.access_days == 0:
                errors['access_days'] = 'Срок доступа должен быть больше нуля.'
            # у дистанционных курсов дат нет
            self.start_date = self.end_date = self.materials_from = self.materials_to = None
            self.time_from = self.time_to = None
        else:
            require('start_date', 'end_date', 'time_from', 'time_to')
            if self.start_date and self.end_date and self.end_date < self.start_date:
                errors['end_date'] = 'Дата окончания не может быть раньше даты начала.'
            if self.time_from and self.time_to and self.time_to <= self.time_from:
                errors['time_to'] = 'Окончание занятий должно быть позже начала.'
            self.access_days = None
            if course_type == Course.TYPE_BLENDED:
                require('materials_from', 'materials_to')
                if self.materials_from and self.materials_to and self.materials_to < self.materials_from:
                    errors['materials_to'] = 'Конец доступа не может быть раньше начала.'
            else:
                self.materials_from = self.materials_to = None
        if errors:
            raise ValidationError(errors)

    @property
    def price(self):
        return self.price_override if self.price_override is not None else self.course.base_price

    @property
    def last_date(self):
        return self.end_date or self.start_date

    @property
    def date_label(self):
        if self.start_date:
            return format_date_range(self.start_date, self.last_date)
        if self.access_days:
            return f'Доступ {self.access_days} {plural_ru(self.access_days, ("день", "дня", "дней"))}'
        return ''

    @property
    def time_label(self):
        if self.time_from and self.time_to:
            return f'{self.time_from:%H:%M}–{self.time_to:%H:%M}'
        return ''

    @property
    def materials_label(self):
        if self.materials_from and self.materials_to:
            return format_date_range(self.materials_from, self.materials_to)
        return ''

    @property
    def in_person_days_label(self):
        return format_day_list(day.date for day in self.in_person_days.all())


class CourseScheduleDay(models.Model):
    """Дата очного занятия в записи расписания очно-заочного курса"""
    schedule = models.ForeignKey(CourseSchedule, on_delete=models.CASCADE, related_name='in_person_days')
    date = models.DateField('Дата очного занятия')

    class Meta:
        verbose_name = 'Очное занятие'
        verbose_name_plural = 'Даты очных занятий'
        ordering = ['date']
        unique_together = [('schedule', 'date')]

    def __str__(self):
        return f'{self.date:%d.%m.%Y}'


class Specialist(models.Model):
    """Модель специалиста"""
    name = models.CharField('ФИО', max_length=255)
    position = models.CharField('Должность', max_length=255)
    city = models.CharField('Город', max_length=100)
    country = models.CharField('Страна', max_length=100)
    photo = models.ImageField('Фото', upload_to='specialists/', blank=True, null=True)
    is_active = models.BooleanField('Активен', default=True)
    order = models.IntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Специалист'
        verbose_name_plural = 'Специалисты'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name



class Representative(models.Model):
    """Региональный представитель или зарубежный партнёр — страница «Представители» и глобус"""
    KIND_REGIONAL = 'regional'
    KIND_FOREIGN = 'foreign'
    KIND_CHOICES = [
        (KIND_REGIONAL, 'Региональный представитель'),
        (KIND_FOREIGN, 'Зарубежный партнёр'),
    ]

    kind = models.CharField('Тип', max_length=20, choices=KIND_CHOICES, default=KIND_REGIONAL)
    name = models.CharField('Название', max_length=255)
    logo = models.ImageField('Логотип', upload_to='representatives/', blank=True, null=True)
    city = models.CharField('Город', max_length=100)
    country = models.CharField('Страна', max_length=100)
    contact_name = models.CharField('Контактное лицо', max_length=255, blank=True,
                                    help_text='Например, имя представителя или название школы.')
    website = models.URLField('Сайт', blank=True)
    email = models.EmailField('Почта', blank=True)
    phone = models.CharField('Телефон', max_length=50, blank=True)
    latitude = models.FloatField('Широта', blank=True, null=True,
                                 help_text='Для отметки на глобусе, например 55.0302 (Новосибирск).')
    longitude = models.FloatField('Долгота', blank=True, null=True,
                                  help_text='Например 82.9204. Координаты можно скопировать из Яндекс/Google Карт.')
    is_active = models.BooleanField('Показывать на сайте', default=True)
    order = models.IntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Представитель'
        verbose_name_plural = 'Представители'
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} ({self.city})"

    @property
    def phone_href(self):
        """Телефон для ссылки tel: — только цифры и ведущий плюс"""
        digits = ''.join(ch for ch in self.phone if ch.isdigit())
        return ('+' if self.phone.strip().startswith('+') else '') + digits

    @property
    def has_coordinates(self):
        return self.latitude is not None and self.longitude is not None

class Partner(models.Model):
    """Модель партнера"""
    name = models.CharField('Название', max_length=255)
    description = models.TextField('Описание', blank=True)
    logo = models.ImageField('Логотип', upload_to='partners/', blank=True, null=True,
                             help_text='PNG с прозрачным фоном — логотип печатается на спасательном круге.')
    city = models.CharField('Город', max_length=100, blank=True)
    country = models.CharField('Страна', max_length=100, blank=True)
    website = models.URLField('Сайт', blank=True)
    is_active = models.BooleanField('Активен', default=True)
    order = models.IntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Партнер'
        verbose_name_plural = 'Партнеры'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class News(models.Model):
    """Модель новости"""
    title = models.CharField('Заголовок', max_length=255)
    slug = models.SlugField('URL', unique=True, blank=True)
    content = models.TextField('Содержание')
    image = models.ImageField('Изображение', upload_to='news/', blank=True, null=True)
    published_date = models.DateTimeField('Дата публикации', default=timezone.now)
    is_published = models.BooleanField('Опубликовано', default=True)

    class Meta:
        verbose_name = 'Новость'
        verbose_name_plural = 'Новости'
        ordering = ['-published_date']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class PageContent(models.Model):
    """Модель для статического контента страниц"""
    slug = models.CharField('Идентификатор', max_length=100, unique=True)
    title = models.CharField('Заголовок', max_length=255, blank=True)
    content = models.TextField('Содержание')
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Контент страницы'
        verbose_name_plural = 'Контент страниц'

    def __str__(self):
        return self.slug

class AboutSection(models.Model):
    """Текстовый блок страницы «Об Ассоциации». Набор блоков фиксирован — его задаёт шаблон."""
    KEY_CHOICES = [
        ('intro', '1. Вступление'),
        ('goals', '2. Цели и задачи'),
        ('directions', '3. Направления деятельности'),
        ('education', '4. Образовательная и просветительская деятельность'),
        ('documents', '5. Документы'),
    ]

    key = models.CharField('Блок', max_length=30, choices=KEY_CHOICES, unique=True)
    title = models.CharField('Заголовок', max_length=255, blank=True)
    content = models.TextField(
        'Текст', blank=True,
        help_text='Абзацы разделяйте пустой строкой. Одиночный перенос строки — перенос внутри абзаца.',
    )
    order = models.PositiveSmallIntegerField('Порядок', default=0, editable=False)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Блок страницы «Об Ассоциации»'
        verbose_name_plural = 'Страница «Об Ассоциации»'
        ordering = ['order']

    def __str__(self):
        return self.get_key_display()


class ContactInfo(models.Model):
    """Контакты Ассоциации: страница «Контакты», ссылки на соцсети в шапке и подвале, телефон для записи.
    Запись одна — её можно только редактировать."""
    organization = models.CharField('Название', max_length=255)
    legal_name = models.CharField('Юридическое название', max_length=255, blank=True)
    inn = models.CharField('ИНН', max_length=12, blank=True)
    address = models.CharField('Адрес', max_length=255)
    directions = models.TextField('Как добраться', blank=True)
    work_hours = models.CharField('Режим работы', max_length=255, blank=True)
    phone_education = models.CharField('Телефон по вопросам обучения', max_length=30,
                                       help_text='Показывается и на страницах курсов — для записи.')
    phone_cooperation = models.CharField('Телефон по вопросам сотрудничества', max_length=30, blank=True,
                                         help_text='И по организационным вопросам.')
    email = models.EmailField('Электронная почта')
    postal_address = models.CharField('Почтовый адрес', max_length=255, blank=True)
    vk_url = models.URLField('ВКонтакте', blank=True)
    telegram_url = models.URLField('Telegram', blank=True)
    map_query = models.CharField('Адрес для карты', max_length=255, blank=True,
                                 help_text='Что искать на Яндекс Картах, если не указаны координаты метки ниже. '
                                           'Если пусто — карта по адресу выше.')
    map_lat = models.DecimalField(
        'Метка на карте: широта', max_digits=9, decimal_places=6, null=True, blank=True,
        help_text='Координаты здания — на карте ставится метка Ассоциации. Узнать их: Яндекс Карты → '
                  'правый клик по зданию → «Что здесь?» (первое число — широта, второе — долгота).',
    )
    map_lng = models.DecimalField('Метка на карте: долгота', max_digits=9, decimal_places=6, null=True, blank=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Контакты'
        verbose_name_plural = 'Контакты'

    def __str__(self):
        return 'Контакты Ассоциации'

    @classmethod
    def get(cls):
        """Контакты из БД, а если записи нет или БД недоступна — со старого сайта (contact_defaults)"""
        try:
            info = cls.objects.first()
        except DatabaseError:
            info = None
        return info or SimpleNamespace(**CONTACT_DEFAULTS, **MAP_POINT)
