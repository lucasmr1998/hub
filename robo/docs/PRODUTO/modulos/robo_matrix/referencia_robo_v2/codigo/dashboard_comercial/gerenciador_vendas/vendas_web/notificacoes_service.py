"""Serviço de criação de notificações (painel/sino) — personalizadas por usuário.

Reusa os modelos existentes (Notificacao/TipoNotificacao/CanalNotificacao/
PreferenciaNotificacao). O sino já renderiza por `destinatario`. Aqui só criamos as
notificações e as direcionamos por PERFIL/PERMISSÃO (via rbac.usuarios_por_capacidade).

Nunca levanta exceção para o chamador — notificar é best-effort.
"""
import logging

logger = logging.getLogger(__name__)


def notificar(tipo_codigo, titulo, mensagem, destinatarios, contexto=None,
              prioridade='normal', chave=None):
    """Cria uma notificação de painel para cada usuário em `destinatarios`.

    - respeita PreferenciaNotificacao (se o usuário desativou este tipo, pula);
    - `chave` (opcional) evita duplicar a mesma notificação para o mesmo usuário.
    Retorna a quantidade criada.
    """
    try:
        from django.utils import timezone
        from vendas_web.models import (Notificacao, TipoNotificacao,
                                        CanalNotificacao, PreferenciaNotificacao)
    except Exception as e:  # noqa: BLE001
        logger.warning('notificar: import falhou: %s', e)
        return 0

    users = [u for u in (destinatarios or []) if u and getattr(u, 'is_active', True)]
    # dedup de usuários
    users = list({u.id: u for u in users}.values())
    if not users:
        return 0

    tipo, _ = TipoNotificacao.objects.get_or_create(
        codigo=tipo_codigo,
        defaults={'nome': tipo_codigo.replace('_', ' ').title(), 'ativo': True})
    canal, _ = CanalNotificacao.objects.get_or_create(
        codigo='painel', defaults={'nome': 'Painel', 'ativo': True, 'icone': 'fas fa-bell'})

    criadas = 0
    for u in users:
        pref = PreferenciaNotificacao.objects.filter(usuario=u, tipo_notificacao=tipo).first()
        if pref and not pref.ativo:
            continue
        # NÃO incluir 'lida_em' — o sino considera "não lida" quando a CHAVE está
        # AUSENTE (dados_contexto__lida_em__isnull=True). Setar None a marcaria lida.
        ctx = dict(contexto) if contexto else {}
        ctx.pop('lida_em', None)
        if chave:
            ctx['chave'] = chave
            if Notificacao.objects.filter(tipo=tipo, destinatario=u,
                                          dados_contexto__chave=chave).exists():
                continue
        try:
            Notificacao.objects.create(
                tipo=tipo, canal=canal, destinatario=u,
                titulo=(titulo or '')[:200], mensagem=mensagem or '',
                dados_contexto=ctx, status='enviada', prioridade=prioridade,
                data_envio=timezone.now())
            criadas += 1
        except Exception as e:  # noqa: BLE001
            logger.warning('notificar: falha ao criar p/ user=%s: %s', u.pk, e)
    return criadas


def notificar_por_capacidade(cap, tipo_codigo, titulo, mensagem, contexto=None,
                             prioridade='normal', chave=None, excluir_user=None):
    """Notifica todos os usuários que têm a capacidade `cap` (perfil/permissão)."""
    try:
        from vendas_web.rbac import usuarios_por_capacidade
        users = list(usuarios_por_capacidade(cap))
    except Exception as e:  # noqa: BLE001
        logger.warning('notificar_por_capacidade(%s) falhou: %s', cap, e)
        return 0
    if excluir_user is not None:
        eid = getattr(excluir_user, 'id', None)
        users = [u for u in users if u.id != eid]
    return notificar(tipo_codigo, titulo, mensagem, users, contexto, prioridade, chave)
