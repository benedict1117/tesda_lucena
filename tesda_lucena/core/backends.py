from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from .utils import normalize_phone


class EmailOrPhoneBackend(ModelBackend):
    """Log in with an email address or a mobile number (username also works)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        User = get_user_model()
        ident = username.strip()
        query = (
            Q(username__iexact=ident)
            | Q(email__iexact=ident)
            | Q(phone=ident)
            | Q(phone=normalize_phone(ident))
        )
        for user in User.objects.filter(query).distinct():
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
