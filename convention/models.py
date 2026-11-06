"""Сайт конвенции специалистов грудничкового плавания (convent.grudnichkovoe-plavanie.ru).
Всё, что меняется из года в год — даты, программа, цены, партнёры, спикеры на главной, фотоконкурс, —
привязано к конвенции. Текущая — опубликованная с самым большим номером, остальные — в архиве."""
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from .utils import date_range, date_span, day_month, ordinal_ru

color_validator = RegexValidator(r'^#[0-9A-Fa-f]{6}$', 'Цвет в формате #RRGGBB, например #00923C.')


class Venue(models.Model):
    """Площадка: выставочный комплекс, акваклуб. Из года в год обычно одни и те же."""
    name = models.CharField('Название', max_length=255,
                            help_text='Например: «Международный торгово-выставочный комплекс «Гринвуд»».')
    address = models.CharField('Адрес', max_length=255, blank=True)
    map_url = models.URLField('Схема проезда', blank=True)
    transfer_text = models.CharField('Трансфер', max_length=255, blank=True,
                                     help_text='Например: «Бесплатный трансфер от м. Сходненская».')
    transfer_url = models.URLField('Ссылка для трансфера', blank=True, help_text='Расписание трансфера.')

    class Meta:
        verbose_name = 'Площадка'
        verbose_name_plural = 'Площадки'
        ordering = ['name']

    def __str__(self):
        return self.name


class ConventionQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)

    def current(self):
        """Текущая конвенция — опубликованная с самым большим номером (или None)"""
        return self.published().order_by('-number').first()


class Convention(models.Model):
    number = models.PositiveSmallIntegerField('Номер', unique=True,
                                              help_text='14 — «Четырнадцатая ежегодная конвенция».')
    start_date = models.DateField('Первый день')
    end_date = models.DateField('Последний день')
    city = models.CharField('Город', max_length=100, default='Москва')
    place = models.CharField(
        'Где проходит', max_length=255,
        help_text='Продолжает фразу «Конвенция проводится с 4 по 6 декабря 2026…», например: '
                  '«в Международном торгово-выставочном комплексе «Гринвуд»». Так же — в архиве.')
    venue = models.ForeignKey(
        Venue, models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='Основная площадка',
        help_text='Её адрес, схема проезда и трансфер — на главной под датами. '
                  'И в карточке дня, если для дня не указано, что в нём проходит.')
    is_published = models.BooleanField(
        'Показывать на сайте', default=True,
        help_text='Текущая конвенция — опубликованная с самым большим номером, остальные — в архиве.')
    highlights = models.TextField(
        'Коротко о конвенции', blank=True,
        default='3 дня профессионального общения\nБолее 30 спикеров и ведущих\nЛекции, тренинги и мастер-классы',
        help_text='На главной над спикерами; каждая строка — отдельно.')
    registration_url = models.URLField('Анкета участника', blank=True,
                                       help_text='Ссылка на Яндекс Форму — страница «Стать участником».')
    program_notice = models.CharField(
        'Объявление над программой', max_length=255, blank=True,
        default='Программа находится в процессе наполнения и уточнения. Следите за обновлениями!',
        help_text='Когда программа готова — очистите.')
    price_note = models.TextField(
        'Пояснение к ценам', blank=True,
        default='Стоимость указана при оплате в день события без учета скидок.\n'
                'В стоимость включено посещение всех мероприятий в выбранные вами дни.\n'
                'Предусмотрены скидки: при ранней оплате участия; для группового посещения; '
                'участникам прошлых Конвенций; членам Ассоциации грудничкового плавания.',
        help_text='Под карточками цен на странице «Участие»; каждая строка — отдельно.')
    hotel_name = models.CharField('Отель', max_length=255, blank=True, help_text='Например: «Отель «Гринвуд»».')
    hotel_url = models.URLField('Сайт отеля', blank=True)
    hotel_booking_url = models.URLField('Бронирование номера', blank=True,
                                        help_text='Кнопка «Забронировать номер» на странице «Участие».')
    hotel_note = models.CharField('Примечание к ценам на номера', max_length=255, blank=True,
                                  help_text='Например: «Завтрак включен в стоимость номера.»')
    regulations = models.FileField('Положение о конвенции', upload_to='convention/docs/', blank=True)
    offer = models.FileField('Публичная оферта', upload_to='convention/docs/', blank=True)
    price_list = models.FileField('Подробно о стоимости участия', upload_to='convention/docs/', blank=True,
                                  help_text='Файл для кнопки «Подробнее о стоимости участия».')
    archive_image = models.ImageField('Картинка в архиве', upload_to='convention/archive/', blank=True,
                                      help_text='Круглая картинка над названием в архиве. Если нет — номер конвенции.')
    schedule_file = models.FileField(
        'Программа файлом', upload_to='convention/archive/', blank=True,
        help_text='Для прошедших конвенций без программы по дням: «Подробнее» в архиве откроет этот файл.')

    objects = ConventionQuerySet.as_manager()

    class Meta:
        verbose_name = 'Конвенция'
        verbose_name_plural = 'Конвенции'
        ordering = ['-number']

    def __str__(self):
        return f'{self.title}, {self.dates}'

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': 'Последний день раньше первого.'})

    @property
    def year(self):
        return self.start_date.year

    @property
    def title(self):
        """«Четырнадцатая конвенция»"""
        return f'{ordinal_ru(self.number, feminine=True).capitalize()} конвенция'

    @property
    def ordinal(self):
        """«четырнадцатая»"""
        return ordinal_ru(self.number, feminine=True)

    @property
    def times(self):
        """«четырнадцатый» — «Конвенция пройдет уже четырнадцатый раз»"""
        return ordinal_ru(self.number)

    @property
    def dates(self):
        """«4–6 декабря 2026»"""
        return date_range(self.start_date, self.end_date)

    @property
    def dates_span(self):
        """«с 4 по 6 декабря 2026»"""
        return date_span(self.start_date, self.end_date)

    @property
    def highlight_lines(self):
        return [line.strip() for line in self.highlights.splitlines() if line.strip()]

    @property
    def price_note_lines(self):
        return [line.strip() for line in self.price_note.splitlines() if line.strip()]


class ConventionDay(models.Model):
    """День конвенции: карточка дня (что где проходит) и программа этого дня."""
    convention = models.ForeignKey(Convention, models.CASCADE, related_name='days', verbose_name='Конвенция')
    date = models.DateField('Дата')

    class Meta:
        verbose_name = 'День конвенции'
        verbose_name_plural = 'Дни и программа'
        ordering = ['convention', 'date']
        constraints = [models.UniqueConstraint(fields=['convention', 'date'], name='convention_day_unique_date')]

    def __str__(self):
        return f'{day_month(self.date)} {self.date.year} — {self.convention.number}-я конвенция'

    @property
    def label(self):
        """«5 декабря»"""
        return day_month(self.date)


class DayActivity(models.Model):
    """Что проходит в этот день — в карточке дня над программой и на странице «Участие»."""
    day = models.ForeignKey(ConventionDay, models.CASCADE, related_name='activities', verbose_name='День')
    title = models.CharField('Что проходит', max_length=255,
                             help_text='Например: «Доклады и презентации по работе с детьми».')
    hall = models.CharField('Зал', max_length=100, blank=True, help_text='Например: «Зал «Гранд»».')
    venue = models.ForeignKey(Venue, models.PROTECT, null=True, blank=True, related_name='+',
                              verbose_name='Площадка', help_text='Если пусто — основная площадка конвенции.')
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Что проходит в этот день'
        verbose_name_plural = 'Что проходит в этот день (карточка дня)'
        ordering = ['day', 'order', 'id']

    def __str__(self):
        return self.title


class EventType(models.Model):
    """Тип мероприятия в программе — свой цвет и метка: доклад, мастер-класс, круглый стол…"""
    name = models.CharField('Название', max_length=100, unique=True)
    color = models.CharField('Цвет', max_length=7, default='#00923C', validators=[color_validator],
                             help_text='Полоса слева и заголовок мероприятия, в формате #RRGGBB.')
    show_label = models.BooleanField(
        'Показывать название', default=True,
        help_text='Метка перед временем. Организационным (регистрация, обед, перерыв) она не нужна.')
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Тип мероприятия'
        verbose_name_plural = 'Типы мероприятий'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Speaker(models.Model):
    name = models.CharField('Имя и фамилия', max_length=150)
    photo = models.ImageField('Фото', upload_to='convention/speakers/', blank=True)
    details = models.CharField('О спикере', max_length=500, blank=True,
                               help_text='Должность, организация (город) — под именем в программе.')

    class Meta:
        verbose_name = 'Спикер'
        verbose_name_plural = 'Спикеры'
        ordering = ['name']

    def __str__(self):
        return self.name


class ProgramEvent(models.Model):
    # разделы программы дня — в этом порядке; у основной программы подзаголовка нет
    SECTIONS = [
        ('main', 'Основная программа'),
        ('pool', 'Мастер-классы в бассейне'),
        ('managers', 'Мероприятия для руководителей'),
    ]

    day = models.ForeignKey(ConventionDay, models.CASCADE, related_name='events', verbose_name='День')
    section = models.CharField('Раздел', max_length=20, choices=SECTIONS, default='main',
                               help_text='Мастер-классы в бассейне и мероприятия для руководителей — '
                                         'отдельными списками со своим подзаголовком.')
    time = models.TimeField('Начало')
    location = models.CharField('Место', max_length=255, blank=True,
                                help_text='Например: «Зал «Гранд» (ТВК «Гринвуд»)».')
    event_type = models.ForeignKey(EventType, models.PROTECT, related_name='events', verbose_name='Тип')
    title = models.CharField('Тема', max_length=500)
    topic = models.TextField('Описание', blank=True)
    speakers = models.ManyToManyField(Speaker, blank=True, related_name='events', verbose_name='Спикеры')

    class Meta:
        verbose_name = 'Мероприятие программы'
        verbose_name_plural = 'Программа'
        ordering = ['day', 'time', 'id']

    def __str__(self):
        return f'{self.time:%H:%M} {self.title}'


class Partner(models.Model):
    """Партнёр конвенции. На сайте — только те, кто указан у текущей конвенции."""
    name = models.CharField('Название', max_length=255)
    logo = models.ImageField('Логотип', upload_to='convention/partners/', blank=True)
    website = models.URLField('Сайт', blank=True)
    headline = models.TextField('Главное о партнёре', blank=True, help_text='Первый абзац, жирным.')
    description = models.TextField('Описание', blank=True, help_text='Абзацы разделяйте пустой строкой.')

    class Meta:
        verbose_name = 'Партнёр конвенции'
        verbose_name_plural = 'Партнёры конвенции'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def paragraphs(self):
        return [p.strip() for p in self.description.replace('\r\n', '\n').split('\n\n') if p.strip()]


class Partnership(models.Model):
    convention = models.ForeignKey(Convention, models.CASCADE, related_name='partnerships', verbose_name='Конвенция')
    partner = models.ForeignKey(Partner, models.CASCADE, related_name='partnerships', verbose_name='Партнёр')
    is_general_sponsor = models.BooleanField('Генеральный спонсор', default=False)
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Партнёр'
        verbose_name_plural = 'Партнёры'
        ordering = ['-is_general_sponsor', 'order', 'id']
        constraints = [models.UniqueConstraint(fields=['convention', 'partner'], name='convention_partner_once')]

    def __str__(self):
        return str(self.partner)


class Price(models.Model):
    KINDS = [
        ('participation', 'Участие'),
        ('extra', 'Дополнительно'),
        ('hotel', 'Проживание'),
    ]

    convention = models.ForeignKey(Convention, models.CASCADE, related_name='prices', verbose_name='Конвенция')
    kind = models.CharField('Раздел', max_length=20, choices=KINDS, default='participation')
    group = models.CharField(
        'Карточка', max_length=100, blank=True,
        help_text='Для участия: «Участник», «Спикер» — цены с одинаковой карточкой собираются вместе.')
    label = models.CharField('Что', max_length=255,
                             help_text='Например: «1 день», «Питание на Конвенции», «Номер категории Комфорт».')
    note = models.CharField('Уточнение', max_length=255, blank=True,
                            help_text='В скобках после названия: «одноместное проживание».')
    amount = models.PositiveIntegerField('Цена')
    unit = models.CharField('Единица', max_length=30, default='руб', help_text='«руб» или «руб/сутки».')
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Цена'
        verbose_name_plural = 'Цены участия'
        ordering = ['kind', 'order', 'id']

    def __str__(self):
        return f'{self.group or self.get_kind_display()}: {self.label} — {self.amount} {self.unit}'


class FeaturedSpeaker(models.Model):
    """Спикер на главной странице сайта конвенции."""
    convention = models.ForeignKey(Convention, models.CASCADE, related_name='featured_speakers',
                                   verbose_name='Конвенция')
    speaker = models.ForeignKey(Speaker, models.CASCADE, related_name='+', verbose_name='Спикер')
    caption = models.CharField('Подпись', max_length=500, blank=True,
                               help_text='Если пусто — «О спикере» из карточки спикера.')
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Спикер на главной'
        verbose_name_plural = 'Спикеры на главной'
        ordering = ['order', 'id']

    def __str__(self):
        return str(self.speaker)

    @property
    def text(self):
        return self.caption or self.speaker.details


class PhotoContestWinner(models.Model):
    """Победитель фотоконкурса «Рыбка в воде». На главной — победители последнего конкурса."""
    convention = models.ForeignKey(Convention, models.CASCADE, related_name='photo_winners',
                                   verbose_name='Конвенция', help_text='Конвенция, на которой подвели итоги.')
    place = models.PositiveSmallIntegerField('Место', default=1)
    author = models.CharField('Автор', max_length=255, help_text='Например: «Aquababy (Алматы, Казахстан)».')
    photo = models.ImageField('Фотография', upload_to='convention/photo-contest/')

    class Meta:
        verbose_name = 'Победитель фотоконкурса'
        verbose_name_plural = 'Фотоконкурс'
        ordering = ['-convention__number', 'place', 'id']

    def __str__(self):
        return f'{self.author} — {self.place} место'


class Organizer(models.Model):
    """Оргкомитет и координаторы — страница «Контакты»; координаторы — ещё и на странице партнёров."""
    GROUPS = [
        ('committee', 'Оргкомитет'),
        ('coordinator', 'Координатор (с телефоном и почтой)'),
    ]

    group = models.CharField('Группа', max_length=20, choices=GROUPS, default='committee')
    name = models.CharField('Имя и фамилия', max_length=150)
    photo = models.ImageField('Фото', upload_to='convention/organizers/', blank=True)
    role = models.TextField('Роль')
    phone = models.CharField('Телефон', max_length=30, blank=True)
    email = models.EmailField('Почта', blank=True)
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Организатор'
        verbose_name_plural = 'Оргкомитет и контакты'
        ordering = ['group', 'order', 'id']

    def __str__(self):
        return self.name
