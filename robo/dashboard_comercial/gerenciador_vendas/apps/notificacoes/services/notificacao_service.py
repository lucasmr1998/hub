import logging

from django.contrib.auth.models import User
from django.utils import timezone

from apps.notificacoes.models import (
    Notificacao,
    TipoNotificacao,
    CanalNotificacao,
)

logger = logging.getLogger(__name__)


def criar_notificacao(
    tenant,
    codigo_tipo,
    titulo,
    mensagem,
    destinatario=None,
    destinatario_email=None,
    destinatario_telefone=None,
    url_acao='',
    prioridade=None,
    dados_contexto=None,
):
    """
    Cria uma notificação in-app para o destinatário.

    Args:
        tenant: Tenant da notificação
        codigo_tipo: Código do TipoNotificacao (ex: 'lead_novo')
        titulo: Título da notificação
        mensagem: Corpo da mensagem
        destinatario: User (opcional)
        destinatario_email: Email (opcional, para canais externos)
        destinatario_telefone: Telefone (opcional, para WhatsApp)
        url_acao: Link ao clicar (ex: '/comercial/leads/123/')
        prioridade: 'baixa', 'normal', 'alta', 'urgente' (usa padrão do tipo se None)
        dados_contexto: dict com dados extras

    Returns:
        Notificacao criada ou None se falhar
    """
    try:
        tipo = TipoNotificacao.objects.filter(
            tenant=tenant, codigo=codigo_tipo, ativo=True
        ).first()

        if not tipo:
            logger.warning(
                f'TipoNotificacao "{codigo_tipo}" não encontrado ou inativo '
                f'para tenant {tenant.pk}'
            )
            return None

        canal = CanalNotificacao.objects.filter(
            tenant=tenant, codigo='sistema', ativo=True
        ).first()

        if not canal:
            canal = _garantir_canal_sistema(tenant)

        notificacao = Notificacao(
            tenant=tenant,
            tipo=tipo,
            canal=canal,
            destinatario=destinatario,
            destinatario_email=destinatario_email,
            destinatario_telefone=destinatario_telefone,
            titulo=titulo,
            mensagem=mensagem,
            url_acao=url_acao,
            prioridade=prioridade or tipo.prioridade_padrao,
            dados_contexto=dados_contexto or {},
            status='enviada',
        )
        notificacao.save()

        logger.info(
            f'Notificação criada: [{codigo_tipo}] "{titulo}" '
            f'para {destinatario or destinatario_email or "sem destinatário"}'
        )
        return notificacao

    except Exception as e:
        logger.error(f'Erro ao criar notificação [{codigo_tipo}]: {e}')
        return None


def notificar_usuarios(
    tenant,
    codigo_tipo,
    titulo,
    mensagem,
    usuarios,
    url_acao='',
    prioridade=None,
    dados_contexto=None,
):
    """
    Cria notificação para múltiplos usuários.

    Args:
        usuarios: queryset ou lista de User
    Returns:
        Lista de Notificacao criadas
    """
    notificacoes = []
    for user in usuarios:
        n = criar_notificacao(
            tenant=tenant,
            codigo_tipo=codigo_tipo,
            titulo=titulo,
            mensagem=mensagem,
            destinatario=user,
            url_acao=url_acao,
            prioridade=prioridade,
            dados_contexto=dados_contexto,
        )
        if n:
            notificacoes.append(n)
    return notificacoes


def marcar_lida(notificacao_id, user):
    """Marca uma notificação como lida."""
    try:
        notificacao = Notificacao.objects.get(pk=notificacao_id, destinatario=user)
        notificacao.marcar_lida()
        return True
    except Notificacao.DoesNotExist:
        return False


def marcar_todas_lidas(tenant, user):
    """Marca todas as notificações não lidas do usuário como lidas."""
    return Notificacao.objects.filter(
        tenant=tenant,
        destinatario=user,
        lida=False,
    ).update(lida=True, data_lida=timezone.now())


def contar_nao_lidas(tenant, user):
    """Conta notificações não lidas do usuário."""
    return Notificacao.objects.filter(
        tenant=tenant,
        destinatario=user,
        lida=False,
    ).count()


def _garantir_canal_sistema(tenant):
    """Garante que o canal 'sistema' existe para o tenant."""
    canal, _ = CanalNotificacao.objects.get_or_create(
        tenant=tenant,
        codigo='sistema',
        defaults={
            'nome': 'Sistema (in-app)',
            'ativo': True,
            'icone': 'fas fa-bell',
        }
    )
    return canal
