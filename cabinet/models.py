import os
from datetime import timedelta
from io import BytesIO
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from PIL import Image, ImageOps

from core.utils import format_date_range, plural_ru

from .phone import format_phone, parse_phone, to_e164

AVATAR_SIZE = 600  # px по большей стороне — аватарка показывается не крупнее 120 px
CERTIFICATE_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png']


def avatar_path(instance, filename):
    """Фото — под случайным именем: исходное имя файла может выдать лишнее о человеке"""
    return f'avatars/{uuid4().hex}.jpg'


def shrink_avatar(upload):
    """Фото для аватарки: повёрнуто по EXIF, уменьшено, пересохранено в JPEG — без метаданных
    (в них бывают координаты съёмки и модель телефона)"""
    image = ImageOps.exif_transpose(Image.open(upload))
    image.thumbnail((AVATAR_SIZE, AVATAR_SIZE))
    if image.mode != 'RGB':
        # прозрачный фон → белый
        image = image.convert('RGBA')
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.getchannel('A'))
        image = background
    buffer = BytesIO()
    image.save(buffer, 'JPEG', quality=88, optimize=True)
    return ContentFile(buffer.getvalue(), name='avatar.jpg')


class Profile(models.Model):
    """Данные из регистрации в личном кабинете. Имя, фамилия, email и пароль — в самом пользователе (User),
    email служит логином."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name='Пользователь', on_delete=models.CASCADE,
                                related_name='profile')
    middle_name = models.CharField('Отчество (второе имя)', max_length=150, blank=True)
    birth_date = models.DateField('Дата рождения')
    phone = models.CharField('Телефон', max_length=20,
                             help_text='С кодом страны: +7 916 123-45-67. Сохраняется как +79161234567.')
    country = models.CharField('Страна', max_length=100, blank=True)
    city = models.CharField('Город', max_length=100, blank=True)
    about = models.TextField('Обо мне', blank=True)
    avatar = models.ImageField('Фотография', upload_to=avatar_path, blank=True)

    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'

    def __str__(self):
        return self.full_name or self.user.get_username()

    def clean(self):
        # номер, введённый в админке как угодно (+7 916 123-45-67, 8 916…), приводится к +79161234567
        parsed = parse_phone(self.phone)
        if parsed is None:
            raise ValidationError({'phone': 'Проверьте номер: нужен код страны, например +7 916 123-45-67.'})
        self.phone = to_e164(parsed)

    def save(self, *args, **kwargs):
        if self.avatar and not self.avatar._committed:  # загружено новое фото
            self.avatar = shrink_avatar(self.avatar)
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        """Фамилия Имя Отчество"""
        user = self.user
        return ' '.join(part for part in (user.last_name, user.first_name, self.middle_name) if part)

    @property
    def initials(self):
        return f'{self.user.first_name[:1]}{self.user.last_name[:1]}'.upper()

    @property
    def phone_display(self):
        return format_phone(self.phone)

    @property
    def place(self):
        """«Москва, Россия» — как у специалистов на главной"""
        return ', '.join(part for part in (self.city, self.country) if part)


def add_years(day, years=1):
    """Та же дата через years лет; 29 февраля — 28 февраля"""
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)


def next_anniversary(start, today):
    """Ближайшая годовщина start, не раньше today — дата следующего ежегодного взноса"""
    years = max(1, today.year - start.year)
    day = add_years(start, years)
    return day if day >= today else add_years(start, years + 1)


def days_label(days):
    return f'{days} {plural_ru(days, ("день", "дня", "дней"))}'


class PostponedCourse(models.Model):
    """Курс, отложенный сердечком на карточке. Откладывается вся карточка (варианты одного курса) —
    хранится один из её курсов. Без входа отложенное лежит в сессии браузера (cabinet/postponed.py)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='Пользователь', on_delete=models.CASCADE,
                             related_name='postponed_courses')
    course = models.ForeignKey('core.Course', verbose_name='Курс', on_delete=models.CASCADE, related_name='+')
    created_at = models.DateTimeField('Отложен', auto_now_add=True)

    class Meta:
        verbose_name = 'Отложенный курс'
        verbose_name_plural = 'Отложенные курсы'
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['user', 'course'], name='cabinet_postponed_unique')]

    def __str__(self):
        return str(self.course)


class MembershipQuerySet(models.QuerySet):
    def shown_on_site(self):
        """Кого показывать на главной: членство активно, и человек сам включил показ"""
        return self.filter(status=Membership.STATUS_ACTIVE, show_on_site=True)


class Membership(models.Model):
    """Членство в Ассоциации. Статус и даты ведёт администратор, показ на сайте включает и выключает
    сам член Ассоциации в личном кабинете. Взносы — раз в год."""
    STATUS_ACTIVE = 'active'
    STATUS_SUSPENDED = 'suspended'
    STATUS_NONE = 'none'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Активно'),
        (STATUS_SUSPENDED, 'Приостановлено'),
        (STATUS_NONE, 'Не является членом'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name='Пользователь', on_delete=models.CASCADE,
                                related_name='membership')
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    start_date = models.DateField('Член Ассоциации с', null=True, blank=True)
    next_fee_date = models.DateField(
        'Дата следующего взноса', null=True, blank=True,
        help_text='Взносы — раз в год. Если оставить пустым — ближайшая годовщина вступления.',
    )
    show_on_site = models.BooleanField(
        'Показывать на сайте', default=False,
        help_text='Фото и имя — в разделе «Членство в ассоциации» на главной, пока членство активно. '
                  'Включает и выключает сам член Ассоциации в личном кабинете.',
    )

    objects = MembershipQuerySet.as_manager()

    class Meta:
        verbose_name = 'Членство'
        verbose_name_plural = 'Членство в Ассоциации'

    def __str__(self):
        return f'{self.user} — {self.get_status_display().lower()}'

    def clean(self):
        if self.status != self.STATUS_NONE and not self.start_date:
            raise ValidationError({'start_date': 'Укажите, с какого дня человек — член Ассоциации.'})

    def save(self, *args, **kwargs):
        if self.start_date and not self.next_fee_date:
            self.next_fee_date = next_anniversary(self.start_date, timezone.localdate())
        super().save(*args, **kwargs)

    @property
    def is_member(self):
        return self.status in (self.STATUS_ACTIVE, self.STATUS_SUSPENDED)

    @property
    def public_name(self):
        """Имя на главной — как у специалистов: «Мария Иванова»"""
        return f'{self.user.first_name} {self.user.last_name}'.strip() or self.user.get_username()

    @property
    def photo_url(self):
        profile = getattr(self.user, 'profile', None)
        if profile and profile.avatar:
            return profile.avatar.url
        teacher = getattr(self.user, 'teacher', None)  # у преподавателя — фото со страницы преподавателя
        return teacher.photo.url if teacher and teacher.photo else ''

    @property
    def place(self):
        profile = getattr(self.user, 'profile', None)
        return profile.place if profile else ''

    @property
    def since_label(self):
        return f'Член Ассоциации с {self.start_date.year} года' if self.start_date else 'Член Ассоциации'

    @property
    def fee_overdue(self):
        return bool(self.next_fee_date) and self.next_fee_date < timezone.localdate()

    @property
    def fee_note(self):
        """Подпись к дате взноса: «через 40 дней», «сегодня», «просрочен на 3 дня»"""
        if not self.next_fee_date:
            return ''
        days = (self.next_fee_date - timezone.localdate()).days
        if days > 0:
            return f'через {days_label(days)}'
        return 'сегодня' if days == 0 else f'просрочен на {days_label(-days)}'


class Enrollment(models.Model):
    """Купленный курс — запись расписания, на которую куплено обучение. Курс и даты обучения берутся
    из неё (и меняются вместе с ней); по датам курс попадает в «Предстоящие», «Идущие» или «Завершённые»."""
    UPCOMING = 'upcoming'
    CURRENT = 'current'
    COMPLETED = 'completed'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='Слушатель', on_delete=models.CASCADE,
                             related_name='enrollments')
    schedule = models.ForeignKey(
        'core.CourseSchedule', verbose_name='Запись расписания', on_delete=models.PROTECT, related_name='+',
        help_text='Курс и даты обучения возьмутся из неё. У дистанционного курса доступ — со дня покупки.',
    )
    course = models.ForeignKey('core.Course', verbose_name='Курс', on_delete=models.PROTECT, related_name='+',
                               editable=False)
    start_date = models.DateField('Начало обучения', editable=False)
    end_date = models.DateField('Окончание обучения', null=True, editable=False)
    created_at = models.DateTimeField('Добавлен', auto_now_add=True)

    class Meta:
        verbose_name = 'Купленный курс'
        verbose_name_plural = 'Купленные курсы'
        ordering = ['start_date', 'pk']
        constraints = [models.UniqueConstraint(fields=['user', 'schedule'], name='cabinet_enrollment_unique')]

    def __str__(self):
        title = str(self.course) if self.course_id else 'Курс'
        return f'{title} ({self.date_label})' if self.start_date else title

    def fill_from_schedule(self):
        """Курс и даты — из записи расписания. У дистанционного курса дат в расписании нет:
        доступ открывается в день покупки на срок из записи."""
        schedule = self.schedule
        self.course_id = schedule.course_id
        if schedule.start_date:
            self.start_date, self.end_date = schedule.start_date, schedule.end_date
        elif schedule.access_days:
            self.start_date = self.start_date or timezone.localdate()
            self.end_date = self.start_date + timedelta(days=schedule.access_days - 1)

    def clean(self):
        if self.schedule_id and not (self.schedule.start_date or self.schedule.access_days):
            raise ValidationError({'schedule': 'В этой записи расписания нет дат обучения — '
                                               'сначала укажите их в расписании.'})

    def save(self, *args, **kwargs):
        self.fill_from_schedule()
        super().save(*args, **kwargs)

    @property
    def last_day(self):
        return self.end_date or self.start_date

    @property
    def date_label(self):
        return format_date_range(self.start_date, self.last_day)

    def status_on(self, day):
        """Предстоящий, идущий или завершённый — на день day"""
        if self.start_date > day:
            return self.UPCOMING
        return self.CURRENT if self.last_day >= day else self.COMPLETED

    def status_note(self, day):
        """«Начнётся через 5 дней», «Идёт до 16 мая 2026», «Завершён»"""
        status = self.status_on(day)
        if status == self.UPCOMING:
            days = (self.start_date - day).days
            return 'Начнётся завтра' if days == 1 else f'Начнётся через {days_label(days)}'
        if status == self.CURRENT:
            if self.last_day == day:
                return 'Идёт, последний день'
            return f'Идёт до {format_date_range(self.last_day, self.last_day)}'
        return 'Завершён'


def certificate_path(instance, filename):
    """Документ — под случайным именем: по адресу файл не подобрать"""
    return f'certificates/{uuid4().hex}{os.path.splitext(filename)[1].lower()}'


class Certificate(models.Model):
    """Документ о пройденном обучении: сертификат, удостоверение или диплом. Файл загружает администратор,
    скачать его может только сам слушатель — из личного кабинета."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='Слушатель', on_delete=models.CASCADE,
                             related_name='certificates')
    course = models.ForeignKey('core.Course', verbose_name='Курс', null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='+')
    title = models.CharField(
        'Документ', max_length=255, blank=True,
        help_text='Например, «Удостоверение о повышении квалификации». Если пусто — документ, '
                  'который выдаётся по выбранному курсу.',
    )
    number = models.CharField('Номер', max_length=100, blank=True)
    issued_on = models.DateField('Дата выдачи')
    file = models.FileField('Файл', upload_to=certificate_path, help_text='PDF, JPG или PNG.',
                            validators=[FileExtensionValidator(CERTIFICATE_EXTENSIONS)])

    class Meta:
        verbose_name = 'Сертификат'
        verbose_name_plural = 'Сертификаты и удостоверения'
        ordering = ['-issued_on', '-pk']

    def __str__(self):
        return f'{self.title} — {self.user}'

    def clean(self):
        if not self.title and not self.course_id:
            raise ValidationError({'title': 'Укажите документ или курс, по которому он выдан.'})

    def save(self, *args, **kwargs):
        if not self.title and self.course_id:
            self.title = self.course.get_main_document_display()
        super().save(*args, **kwargs)

    @property
    def extension(self):
        return os.path.splitext(self.file.name)[1].lstrip('.').lower()

    @property
    def download_name(self):
        """«Удостоверение о повышении квалификации — Иванова.pdf»"""
        return f'{self.title or "Документ"} — {self.user.last_name or self.user.get_username()}.{self.extension}'


@receiver(post_save, sender='core.CourseSchedule')
def update_enrollments(sender, instance, **kwargs):
    """Даты или курс в записи расписания поменялись — у купленных по ней курсов тоже"""
    if kwargs.get('raw'):  # загрузка выгрузки (loaddata) — данные и так согласованы
        return
    for enrollment in Enrollment.objects.filter(schedule=instance):
        enrollment.save()
