"""Servicos de inatividade do atendente (v3).

2 niveis:
  - Nivel A — atribuido mas nao assumiu em X min -> REALOCA automaticamente
  - Nivel B — assumiu mas nao responde ha Y min -> NOTIFICA administrador

Acionado pelo management command `cron_inatividade_atendente`.
Doc completa em docs/PRODUTO/modulos/inbox/reatribuicao-inatividade.md.
"""
import logging

from django.contrib.auth.models import User
from django.utils import timezone

from .models import (
    Mensagem, MembroEquipeInbox,
    HistoricoTransferencia, PerfilAgenteInbox,
)

logger = logging.getLogger(__name__)


def _registrar_msg_sistema(conversa, conteudo):
    Mensagem(
        tenant=conversa.tenant,
        conversa=conversa,
        remetente_tipo='sistema',
        remetente_nome='Sistema',
        tipo_conteudo='sistema',
        conteudo=conteudo,
    ).save()


def _selecionar_proximo_agente(fila, excluir_user_id):
    """Seleciona proximo agente online da fila, excluindo quem perdeu a conversa."""
    from .distribution import selecionar_agente
    # selecionar_agente nao tem exclude, vou filtrar manualmente
    membros = MembroEquipeInbox.all_tenants.filter(
        tenant=fila.tenant, equipe=fila.equipe,
    ).values_list('user_id', flat=True)
    membros = [m for m in membros if m != excluir_user_id]
    if not membros:
        return None
    perfis = PerfilAgenteInbox.all_tenants.filter(
        tenant=fila.tenant, user_id__in=membros, status='online',
    )
    disponiveis = [p for p in perfis if p.disponivel]
    if not disponiveis:
        return None
    if fila.modo_distribuicao == 'menor_carga':
        return min(disponiveis, key=lambda p: p.conversas_abertas_count).user
    return disponiveis[0].user


def realocar_conversa_inativa(conversa):
    """Nivel A: conversa atribuida ha tempo, nao foi assumida. Reatribui.

    Pre-condicoes ja verificadas pelo caller (cron):
      - conversa.assumida == False
      - conversa.agente_id is not None
      - tempo desde data_abertura/transferencia > tempo_max_sem_assumir_min
      - conversa.realocacoes_count < fila.max_realocacoes
      - dentro do horario da fila

    Acoes:
      1. Tenta selecionar OUTRO agente online (exclui o atual)
      2. Se achar: muda conversa.agente + cria HistoricoTransferencia(tipo='realocar_inativo')
         + msg sistema + incrementa realocacoes_count
      3. Se nao achar agente: deixa conversa sem agente (agente=NULL, status=pendente)
         pra outro pegar manualmente. Registra historico com para_agente=NULL.

    Retorna o novo agente (User) ou None se foi liberada sem novo destino.
    """
    fila = conversa.fila
    if not fila:
        logger.warning("Realocar: conversa #%s sem fila — skipping", conversa.pk)
        return None

    agente_anterior = conversa.agente
    nome_anterior = (agente_anterior.get_full_name() or agente_anterior.username) if agente_anterior else 'agente'

    novo_agente = _selecionar_proximo_agente(fila, excluir_user_id=conversa.agente_id)

    HistoricoTransferencia(
        tenant=conversa.tenant,
        conversa=conversa,
        tipo='realocar_inativo',
        de_agente=agente_anterior,
        para_agente=novo_agente,
        de_equipe=conversa.equipe,
        para_equipe=conversa.equipe,
        para_fila=fila,
        motivo=f'auto: nao assumiu em {fila.tempo_max_sem_assumir_min}min',
    ).save()

    conversa.realocacoes_count = (conversa.realocacoes_count or 0) + 1

    if novo_agente:
        conversa.agente = novo_agente
        conversa.assumida = False
        conversa.save(update_fields=['agente', 'assumida', 'realocacoes_count'])
        nome_novo = novo_agente.get_full_name() or novo_agente.username
        _registrar_msg_sistema(
            conversa,
            f"Conversa reatribuida automaticamente: {nome_anterior} nao assumiu. Agora com {nome_novo}."
        )
        logger.info("Realocar: conversa #%s %s -> %s (realocacao #%d)",
                    conversa.numero, nome_anterior, nome_novo, conversa.realocacoes_count)
    else:
        conversa.agente = None
        conversa.assumida = False
        conversa.status = 'pendente'
        conversa.save(update_fields=['agente', 'assumida', 'status', 'realocacoes_count'])
        _registrar_msg_sistema(
            conversa,
            f"Conversa liberada da fila: {nome_anterior} nao assumiu e nenhum outro agente online disponivel."
        )
        logger.info("Realocar: conversa #%s liberada (sem agente disponivel)", conversa.numero)

    return novo_agente


def alertar_admin_inatividade(conversa):
    """Nivel B: atendente assumiu mas nao responde ultima msg do contato ha Y min.

    NAO toca na conversa. Apenas:
      1. Cria HistoricoTransferencia(tipo='alerta_admin') pra auditoria
      2. Notifica todos os usuarios com permissao inbox.gerenciar via apps.notificacoes
      3. Marca metadata.alerta_inatividade_em pra nao repetir

    Idempotente: se ja alertou, nao alerta de novo. Reset quando agente responder
    (logica no cron: so chama se metadata.alerta_inatividade_em for None).
    """
    from apps.notificacoes.services.notificacao_service import criar_notificacao

    agente = conversa.agente
    fila = conversa.fila
    contato = conversa.contato_nome or conversa.contato_telefone or f'#{conversa.numero}'

    # ultima msg do contato pra mostrar contexto
    ultima_msg_contato = Mensagem.all_tenants.filter(
        tenant=conversa.tenant, conversa=conversa, remetente_tipo='contato',
    ).order_by('-data_envio').first()
    preview = (ultima_msg_contato.conteudo or '')[:120] if ultima_msg_contato else ''

    # 1. Audit historico
    HistoricoTransferencia(
        tenant=conversa.tenant,
        conversa=conversa,
        tipo='alerta_admin',
        de_agente=agente,
        para_agente=agente,  # nao muda
        de_equipe=conversa.equipe,
        para_equipe=conversa.equipe,
        para_fila=fila,
        motivo=f'admin notificado: {fila.tempo_max_sem_responder_min}min sem responder',
    ).save()

    # 2. Destinatarios: users com permissao inbox.gerenciar do tenant
    admins = User.objects.filter(
        perfil__tenant=conversa.tenant,
        is_active=True,
    ).filter(
        # Procura pela permissao via grupo/perfil ou is_staff/is_superuser
        # Mais robusto: usa has_perm em loop (mas isso e cache-friendly em prod)
    )
    # Filtra in-memory por permissao real (perm 'inbox.gerenciar' nao existe necessariamente
    # como Permission do Django — eh nome usado via has_perm. Vou pegar admins/superusers + os
    # que tem o ContentType de inbox.* configurado)
    destinatarios = [u for u in admins if u.is_superuser or u.has_perm('inbox.gerenciar')]

    nome_agente = (agente.get_full_name() or agente.username) if agente else 'sem agente'
    titulo = f'Atendimento sem resposta ha {fila.tempo_max_sem_responder_min}min'
    msg = (
        f'Cliente: {contato}\n'
        f'Atendente: {nome_agente}\n'
        f'Ultima msg: "{preview}"'
    )

    enviados = 0
    for admin_user in destinatarios:
        notif = criar_notificacao(
            tenant=conversa.tenant,
            codigo_tipo='inatividade_atendente',
            titulo=titulo,
            mensagem=msg,
            destinatario=admin_user,
            url_acao=f'/inbox/?conversa={conversa.pk}',
            prioridade='alta',
            dados_contexto={
                'conversa_id': conversa.pk,
                'agente_id': agente.pk if agente else None,
                'tempo_sem_responder_min': fila.tempo_max_sem_responder_min,
            },
        )
        if notif:
            enviados += 1

    # 3. Marca metadata pra nao repetir
    meta = conversa.metadata or {}
    meta['alerta_inatividade_em'] = timezone.now().isoformat()
    conversa.metadata = meta
    conversa.save(update_fields=['metadata'])

    logger.info("Alerta admin: conversa #%s notificou %d admin(s)", conversa.numero, enviados)
    return enviados
