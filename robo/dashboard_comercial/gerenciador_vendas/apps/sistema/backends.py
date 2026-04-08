"""
Backend de autenticacao por email.

Permite login com email em vez de username.
Compativel com Django authenticate(request, username=email, password=senha).
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailBackend(ModelBackend):
    """Autentica usando email em vez de username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        # username pode ser email ou username (compatibilidade)
        if username is None:
            return None

        # Tentar por email primeiro
        try:
            user = User.objects.get(email__iexact=username)
        except User.DoesNotExist:
            # Fallback: tentar por username (compatibilidade)
            try:
                user = User.objects.get(username__iexact=username)
            except User.DoesNotExist:
                return None
        except User.MultipleObjectsReturned:
            # Se houver emails duplicados, pegar o primeiro ativo
            user = User.objects.filter(email__iexact=username, is_active=True).first()
            if not user:
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
