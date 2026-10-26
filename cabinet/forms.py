from functools import lru_cache

from django import forms
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from .models import Profile
from .phone import (
    CODES_BY_NAME, DEFAULT_REGION, country_choices, country_name_choices, example_local, example_number, parse_phone,
    split_phone, to_e164,
)

AVATAR_MAX_MB = 5
ABOUT_MAX_LENGTH = 1500
PASSWORD_HELP = 'Не короче 8 символов; не только цифры и не слишком простой.'


def keep_country(field, country):
    """Страна не из списка (например, вписана в админке раньше) — добавить её, чтобы не потерялась при сохранении"""
    if country and country not in CODES_BY_NAME:
        field.choices = [*field.choices, (country, country)]


def plain_widgets(widget):
    """Поля ввода виджета: у телефона их два (страна и номер), у остальных — он сам"""
    return getattr(widget, 'widgets', [widget])


def input_widget(widget):
    """Поле, которое подсвечивается при ошибке: у телефона — номер (страна выбрана из списка)"""
    return plain_widgets(widget)[-1]


class StyledFormMixin:
    """Классы Bootstrap у полей; у полей с ошибкой — ещё is-invalid (красная рамка)"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            for widget in plain_widgets(field.widget):
                if isinstance(widget, forms.CheckboxInput):
                    css = 'form-check-input'
                elif isinstance(widget, forms.Select):
                    css = 'form-select'
                else:
                    css = 'form-control'
                widget.attrs['class'] = f"{css} {widget.attrs.get('class', '')}".strip()

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                widget = input_widget(self.fields[name].widget)
                widget.attrs['class'] += ' is-invalid'
                widget.attrs['aria-invalid'] = 'true'


@lru_cache(maxsize=None)
def _example_local(region):
    return example_local(region)


class CountrySelect(forms.Select):
    """Список стран; у каждой — пример номера: подсказка в поле номера меняется вместе со страной"""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            option['attrs']['data-example'] = _example_local(value)
        return option


class CountryNameSelect(forms.Select):
    """Страна; у каждой — её код: выбранная страна подставляется и в код телефона (js/cabinet.js)"""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            option['attrs']['data-code'] = CODES_BY_NAME.get(value, '')
        return option


class PhoneWidget(forms.MultiWidget):
    """Телефон: код страны из списка + номер"""
    template_name = 'cabinet/widgets/phone.html'

    def __init__(self, attrs=None):
        widgets = {  # в запросе: phone_country и phone_number
            'country': CountrySelect(choices=country_choices(), attrs={
                'class': 'phone-country', 'aria-label': 'Страна', 'data-phone-country': '',
            }),
            'number': forms.TextInput(attrs={
                'type': 'tel', 'inputmode': 'tel', 'autocomplete': 'tel', 'maxlength': 30,
                'placeholder': example_local(DEFAULT_REGION), 'data-phone-number': '',
            }),
        }
        super().__init__(widgets, attrs)

    def decompress(self, value):
        return list(split_phone(value)) if value else [DEFAULT_REGION, '']

    def id_for_label(self, id_):
        return f'{id_}_1' if id_ else ''  # подпись поля — к номеру, а не к списку стран


class PhoneField(forms.MultiValueField):
    """Телефон с кодом страны → номер в международном формате +79161234567.
    Номер можно ввести целиком, начиная с «+», — тогда выбранная страна не важна."""
    widget = PhoneWidget
    default_error_messages = {
        'invalid_phone': 'Проверьте номер — для выбранной страны он выглядит так: %(example)s',
    }

    def __init__(self, **kwargs):
        fields = (
            forms.ChoiceField(choices=country_choices()),
            forms.CharField(max_length=30),
        )
        super().__init__(fields, require_all_fields=True, **kwargs)

    def compress(self, data_list):
        if not data_list:
            return ''
        region, number = data_list
        parsed = parse_phone(number, region)
        if parsed is None:
            raise ValidationError(self.error_messages['invalid_phone'], code='invalid',
                                  params={'example': example_number(region)})
        return to_e164(parsed)


# поля профиля (Profile) в формах регистрации и «Моего профиля»; фото — отдельно
PROFILE_FIELDS = ['middle_name', 'birth_date', 'country', 'city', 'about', 'phone']


class PersonForm(forms.Form):
    """Данные о человеке — общие для регистрации и страницы «Мой профиль»"""
    error_messages = {
        'duplicate_email': 'С этим email уже зарегистрировались — войдите в личный кабинет.',
    }

    last_name = forms.CharField(label='Фамилия', max_length=150,
                                widget=forms.TextInput(attrs={'autocomplete': 'family-name'}))
    first_name = forms.CharField(label='Имя', max_length=150,
                                 widget=forms.TextInput(attrs={'autocomplete': 'given-name'}))
    middle_name = forms.CharField(label='Отчество (второе имя)', max_length=150, required=False,
                                  widget=forms.TextInput(attrs={'autocomplete': 'additional-name'}))
    birth_date = forms.DateField(label='Дата рождения', widget=forms.DateInput(
        attrs={'type': 'date', 'min': '1900-01-01', 'autocomplete': 'bday'}, format='%Y-%m-%d'))
    country = forms.ChoiceField(label='Страна', required=False, choices=country_name_choices(),
                                widget=CountryNameSelect(attrs={'data-country-select': ''}))
    city = forms.CharField(label='Город', max_length=100, required=False,
                           widget=forms.TextInput(attrs={'autocomplete': 'address-level2'}))
    about = forms.CharField(
        label='Обо мне', max_length=ABOUT_MAX_LENGTH, required=False,
        help_text=f'Чем занимаетесь, где работаете или учитесь — до {ABOUT_MAX_LENGTH} символов.',
        widget=forms.Textarea(attrs={'rows': 4}),
    )
    phone = PhoneField(label='Контактный телефон')
    email = forms.EmailField(label='Email', max_length=150,  # email — это и логин, а логин не длиннее 150
                             help_text='Им вы входите в личный кабинет.',
                             widget=forms.EmailInput(attrs={'autocomplete': 'email'}))
    avatar = forms.ImageField(label='Фотография', required=False,
                              help_text=f'JPG или PNG до {AVATAR_MAX_MB} МБ — для аватарки в личном кабинете.',
                              widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['birth_date'].widget.attrs['max'] = timezone.localdate().isoformat()

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        taken = User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email))
        instance = getattr(self, 'instance', None)
        if instance is not None and instance.pk:
            taken = taken.exclude(pk=instance.pk)  # свой же email — не занят
        if taken.exists():
            raise ValidationError(self.error_messages['duplicate_email'], code='duplicate_email')
        return email

    def clean_birth_date(self):
        birth_date = self.cleaned_data['birth_date']
        if birth_date >= timezone.localdate():
            raise ValidationError('Дата рождения должна быть в прошлом.', code='future')
        if birth_date.year < 1900:
            raise ValidationError('Проверьте год рождения.', code='too_old')
        return birth_date

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar and avatar.size > AVATAR_MAX_MB * 1024 * 1024:
            raise ValidationError(f'Фото больше {AVATAR_MAX_MB} МБ — выберите поменьше.', code='too_big')
        return avatar


class RegistrationForm(StyledFormMixin, PersonForm, BaseUserCreationForm):
    """Регистрация в личном кабинете. Логин — email; ФИО, дата рождения, телефон и фото — в профиль."""
    error_messages = {**BaseUserCreationForm.error_messages, **PersonForm.error_messages}

    consent = forms.BooleanField(
        label='Даю согласие на обработку моих персональных данных',
        error_messages={'required': 'Без согласия на обработку данных зарегистрироваться не получится.'},
    )

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ['last_name', 'first_name', 'email']

    field_order = ['last_name', 'first_name', 'middle_name', 'birth_date', 'avatar', 'country', 'city', 'about',
                   'phone', 'email', 'password1', 'password2', 'consent']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].help_text = 'Им вы будете входить в личный кабинет.'
        self.fields['password1'].help_text = PASSWORD_HELP
        self.fields['password2'].label = 'Повторите пароль'
        self.fields['password2'].help_text = ''

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email  # email и есть логин
        if commit:
            user.save()
            data = self.cleaned_data
            Profile.objects.create(user=user, avatar=data['avatar'],
                                   **{name: data[name] for name in PROFILE_FIELDS})
        return user


class ProfileForm(StyledFormMixin, PersonForm, forms.ModelForm):
    """«Мой профиль»: данные из регистрации — дополнить или поменять. Новый email — это и новый логин."""
    error_messages = {'duplicate_email': 'Этот email уже у другого пользователя.'}

    remove_avatar = forms.BooleanField(label='Удалить фото', required=False)

    class Meta:
        model = User
        fields = ['last_name', 'first_name', 'email']

    field_order = ['last_name', 'first_name', 'middle_name', 'birth_date', 'avatar', 'remove_avatar',
                   'country', 'city', 'about', 'phone', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # у сотрудников, заведённых в админке, профиля может не быть — он появится при сохранении
        self.profile = getattr(self.instance, 'profile', None)
        if self.profile:
            for name in PROFILE_FIELDS:
                self.initial.setdefault(name, getattr(self.profile, name))
            keep_country(self.fields['country'], self.profile.country)
        self.fields['avatar'].help_text = f'JPG или PNG до {AVATAR_MAX_MB} МБ. Новое фото заменит прежнее.'

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email
        user.save()
        data = self.cleaned_data
        profile = self.profile or Profile(user=user)
        old_avatar = profile.avatar.name if profile.avatar else ''
        for name in PROFILE_FIELDS:
            setattr(profile, name, data[name])
        if data['avatar']:
            profile.avatar = data['avatar']
        elif data['remove_avatar']:
            profile.avatar = ''
        profile.save()
        if old_avatar and old_avatar != profile.avatar.name:
            profile.avatar.storage.delete(old_avatar)  # прежнее фото больше не нужно
        self.profile = profile
        return user


class PasswordForm(StyledFormMixin, PasswordChangeForm):
    """Смена пароля в «Моём профиле»"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.pop('autofocus', None)  # иначе страница прыгает к паролю
        self.fields['new_password1'].help_text = PASSWORD_HELP
        self.fields['new_password2'].label = 'Повторите новый пароль'


class LoginForm(StyledFormMixin, AuthenticationForm):
    """Вход по email и паролю (email при регистрации стал логином)"""
    username = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={'autofocus': True,
                                                                            'autocomplete': 'email'}))
    error_messages = {
        'invalid_login': 'Неверный email или пароль.',
        'inactive': 'Вход в этот кабинет закрыт. Если это ошибка, напишите нам.',
    }

    def clean_username(self):
        return self.cleaned_data['username'].lower()
