from django.db import models
from django.utils.text import slugify
from django.utils import timezone


class Course(models.Model):
    """Модель обучающего курса"""
    title = models.CharField('Название курса', max_length=255)
    slug = models.SlugField('URL', unique=True, blank=True)
    description = models.TextField('Описание')
    hours = models.IntegerField('Учебные часы')
    instructor = models.CharField('Преподаватель', max_length=255)
    image = models.ImageField('Изображение', upload_to='courses/', blank=True, null=True)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)

    class Meta:
        verbose_name = 'Курс'
        verbose_name_plural = 'Курсы'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


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


class Partner(models.Model):
    """Модель партнера"""
    name = models.CharField('Название', max_length=255)
    description = models.TextField('Описание', blank=True)
    logo = models.ImageField('Логотип', upload_to='partners/', blank=True, null=True)
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