from django.db import models
from django.utils.text import slugify
from django.utils import timezone


class Teacher(models.Model):
    """Модель преподавателя"""
    first_name = models.CharField('Имя', max_length=100)
    last_name = models.CharField('Фамилия', max_length=100)
    patronymic = models.CharField('Отчество', max_length=100, blank=True)
    photo = models.ImageField('Фотография с фоном', upload_to='teachers/', blank=True, null=True)
    photo_transparent = models.ImageField(
        'Фотография без фона', upload_to='teachers/transparent/', blank=True, null=True
    )

    class Meta:
        verbose_name = 'Преподаватель'
        verbose_name_plural = 'Преподаватели'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.last_name} {self.first_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Course(models.Model):
    """Модель обучающего курса"""
    title = models.CharField('Название курса', max_length=255)
    slug = models.SlugField('URL', unique=True, blank=True)
    description = models.TextField('Описание')
    hours = models.IntegerField('Учебные часы')
    teachers = models.ManyToManyField(
        Teacher, verbose_name='Преподаватели', through='CourseTeacher',
        related_name='courses', blank=True,
    )
    kind = models.CharField('Тип', max_length=100, blank=True,
                            help_text='Например: «Семинар» или «Повышение квалификации».')
    audience = models.TextField('Для кого', blank=True)
    program = models.TextField(
        'Программа курса', blank=True,
        help_text='Абзацы разделяйте пустой строкой. Одиночный перенос строки — перенос внутри абзаца.',
    )
    image = models.ImageField('Изображение', upload_to='courses/', blank=True, null=True)
    order = models.IntegerField('Место на странице', default=0)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обн  овлен', auto_now=True)

    class Meta:
        verbose_name = 'Блок курса'
        verbose_name_plural = 'Блоки курсов'
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

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
        return f"{self.course} — {self.teacher}"


class CourseSession(models.Model):
    """Даты проведения курса — показываются в календаре на странице «Расписание»"""
    course = models.ForeignKey(
        Course, verbose_name='Курс', on_delete=models.CASCADE, related_name='sessions',
    )
    start_date = models.DateField('Дата начала')
    end_date = models.DateField('Дата окончания', blank=True, null=True,
                                help_text='Оставьте пустым, если курс проходит в один день.')
    location = models.CharField('Место проведения', max_length=255, blank=True)
    price = models.CharField('Стоимость', max_length=100, blank=True,
                             help_text='Например: «от 18 240 руб».')
    note = models.CharField('Примечание', max_length=255, blank=True,
                            help_text='Например: «Онлайн» или «Набор закрыт».')

    class Meta:
        verbose_name = 'Дата проведения'
        verbose_name_plural = 'Даты проведения'
        ordering = ['start_date']

    def __str__(self):
        return f"{self.course} — {self.start_date:%d.%m.%Y}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': 'Дата окончания не может быть раньше даты начала.'})

    @property
    def last_date(self):
        return self.end_date or self.start_date


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
