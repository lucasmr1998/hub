"""
Signals do sistema para auditoria de autenticacao.
"""
import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def on_user_login(sender, request, user, **kwargs):
    from apps.sistema.utils import registrar_acao
    registrar_acao(
        categoria='auth', acao='login', entidade='usuario', entidade_id=user.pk,
        mensagem=f'Login: {user.username}',
        request=request,
    )


@receiver(user_logged_out)
def on_user_logout(sender, request, user, **kwargs):
    from apps.sistema.utils import registrar_acao
    if user:
        registrar_acao(
            categoria='auth', acao='logout', entidade='usuario', entidade_id=user.pk,
            mensagem=f'Logout: {user.username}',
            request=request,
        )


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    from apps.sistema.utils import registrar_acao
    username = credentials.get('username', 'desconhecido')
    registrar_acao(
        categoria='auth', acao='login_falho', entidade='usuario', entidade_id=None,
        mensagem=f'Tentativa de login falha: {username}',
        request=request,
        nivel='WARNING',
    )
