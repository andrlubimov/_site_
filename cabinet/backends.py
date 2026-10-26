from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Вход в личный кабинет по email, даже если имя пользователя другое: аккаунты преподавателей, сотрудников.
    У зарегистрировавшихся на сайте имя пользователя и есть email — их пускает обычный ModelBackend."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        users = get_user_model()._default_manager.filter(email__iexact=username).exclude(username__iexact=username)
        for user in users:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
