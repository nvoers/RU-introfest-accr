from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    """Log in with either the username or the e-mail address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username and "@" in username:
            User = get_user_model()
            matches = User.objects.filter(email__iexact=username.strip())
            if matches.count() == 1:
                username = matches.get().get_username()
        return super().authenticate(request, username=username, password=password, **kwargs)
