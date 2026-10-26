from django.apps import AppConfig


class CabinetConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cabinet'
    verbose_name = 'Личный кабинет'

    def ready(self):
        from django.contrib.auth.signals import user_logged_in

        from .postponed import keep_after_login

        # отложенное до входа — в личный кабинет
        user_logged_in.connect(keep_after_login, dispatch_uid='cabinet_keep_postponed')
