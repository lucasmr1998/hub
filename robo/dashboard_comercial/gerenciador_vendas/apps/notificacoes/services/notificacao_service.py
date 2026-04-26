import logging

from django.db.models import Q
from django.utils import timezone

from apps.notificacoes.models import (
    Notificacao,
    NotificacaoLeituraBroadcast,
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


def notificacoes_visiveis(tenant, user):
    """
    Queryset de notificacoes que o user pode ver:
      - Pessoais: destinatario=user
      - Broadcast: destinatario=NULL e do mesmo tenant
    """
    return Notificacao.objects.filter(tenant=tenant).filter(
        Q(destinatario=user) | Q(destinatario__isnull=True)
    )


def _ids_broadcasts_lidos(tenant, user):
    """Set de IDs de broadcasts que o user ja leu (via NotificacaoLeituraBroadcast)."""
    return set(
        NotificacaoLeituraBroadcast.objects.filter(
            user=user,
            notificacao__tenant=tenant,
            notificacao__destinatario__isnull=True,
        ).values_list('notificacao_id', flat=True)
    )


def marcar_lida(notificacao_id, user):
    """Marca uma notificacao como lida.

    - Pessoal (destinatario=user): seta Notificacao.lida=True
    - Broadcast (destinatario=NULL): cria NotificacaoLeituraBroadcast (idempotente)
    - Outros casos (destinada a outro user): retorna False
    """
    notif = Notificacao.objects.filter(pk=notificacao_id).first()
    if not notif:
        return False
    if notif.is_broadcast:
        NotificacaoLeituraBroadcast.objects.get_or_create(notificacao=notif, user=user)
        return True
    if notif.destinatario_id == user.pk:
        notif.marcar_lida()
        return True
    return False


def marcar_todas_lidas(tenant, user):
    """Marca pessoais (lida=True) e broadcasts (cria registros) como lidas."""
    qtd_pessoais = Notificacao.objects.filter(
        tenant=tenant, destinatario=user, lida=False,
    ).update(lida=True, data_lida=timezone.now())

    broadcasts = Notificacao.objects.filter(
        tenant=tenant, destinatario__isnull=True,
    ).exclude(leituras_broadcast__user=user)
    novos = [
        NotificacaoLeituraBroadcast(notificacao=n, user=user)
        for n in broadcasts
    ]
    if novos:
        NotificacaoLeituraBroadcast.objects.bulk_create(novos, ignore_conflicts=True)
    return qtd_pessoais + len(novos)


def contar_nao_lidas(tenant, user):
    """Conta pessoais nao-lidas + broadcasts nao-lidas pelo user."""
    pessoais = Notificacao.objects.filter(
        tenant=tenant, destinatario=user, lida=False,
    ).count()
    broadcasts = Notificacao.objects.filter(
        tenant=tenant, destinatario__isnull=True,
    ).exclude(leituras_broadcast__user=user).count()
    return pessoais + broadcasts


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
