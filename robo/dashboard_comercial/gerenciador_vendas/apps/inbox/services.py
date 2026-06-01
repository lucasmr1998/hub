"""
Serviços de negócio do Inbox.

Toda lógica de receber/enviar mensagens, atribuir conversas, criar tickets, etc.
Chamado pelas views (painel) e APIs (N8N/webhook).
"""

import logging
import re
import threading
import time

import requests
from django.utils import timezone

from apps.sistema.models import Tenant

from .models import CanalInbox, Conversa, Mensagem

logger = logging.getLogger(__name__)


_PREVIEW_LABELS_MIDIA = {
    'audio': '[audio]',
    'imagem': '[imagem]',
    'video': '[video]',
    'arquivo': '[arquivo]',
}


def preview_mensagem(conteudo, tipo_conteudo='texto'):
    """Calcula o preview da Conversa pra exibir na lista do Inbox.

    Quando a mensagem e midia sem caption (conteudo vazio), usa um label
    generico em vez de string vazia — caso contrario a lista mostra preview
    em branco e a vendedora nao sabe que tem mensagem nova.
    """
    texto = (conteudo or '').strip()
    if not texto:
        texto = _PREVIEW_LABELS_MIDIA.get(tipo_conteudo, '')
    return texto[:255]


# ── WebSocket notifications ────────────────────────────────────────────

def _notificar_ws_nova_mensagem(conversa, mensagem):
    """Envia notificação de nova mensagem via WebSocket (se Channels configurado)."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        msg_data = {
            'id': mensagem.id,
            'conversa_id': conversa.id,
            'remetente_tipo': mensagem.remetente_tipo,
            'remetente_nome': mensagem.remetente_nome,
            'tipo_conteudo': mensagem.tipo_conteudo,
            'conteudo': mensagem.conteudo[:500],
            'data_envio': mensagem.data_envio.isoformat(),
        }

        # Notificar grupo do tenant (lista de conversas)
        if conversa.tenant_id:
            async_to_sync(channel_layer.group_send)(
                f'inbox_tenant_{conversa.tenant_id}',
                {'type': 'nova_mensagem', 'conversa_id': conversa.id, 'mensagem': msg_data}
            )

        # Notificar grupo da conversa (chat aberto)
        async_to_sync(channel_layer.group_send)(
            f'inbox_conversa_{conversa.id}',
            {'type': 'nova_mensagem', 'conversa_id': conversa.id, 'mensagem': msg_data}
        )

    except Exception as e:
        logger.debug("WebSocket notification skipped: %s", e)


def _notificar_ws_conversa_alterada(conversa, changes=None):
    """Notifica alteração de status/atribuição de conversa via WebSocket."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        payload = {
            'type': 'conversa_atualizada',
            'conversa_id': conversa.id,
            'changes': changes or {},
        }

        if conversa.tenant_id:
            async_to_sync(channel_layer.group_send)(
                f'inbox_tenant_{conversa.tenant_id}', payload
            )

        async_to_sync(channel_layer.group_send)(
            f'inbox_conversa_{conversa.id}', payload
        )

    except Exception as e:
        logger.debug("WebSocket notification skipped: %s", e)


# ── Utilidades ─────────────────────────────────────────────────────────

def normalizar_telefone(telefone):
    """Remove tudo que não é dígito, mantém apenas números."""
    if not telefone:
        return ''
    return re.sub(r'\D', '', telefone)


def buscar_lead_por_telefone(telefone, tenant):
    """Busca LeadProspecto pelo telefone (match parcial pelos últimos dígitos)."""
    from apps.comercial.leads.models import LeadProspecto

    fone = normalizar_telefone(telefone)
    if not fone:
        return None

    # Tenta match exato primeiro
    lead = LeadProspecto.all_tenants.filter(
        tenant=tenant, telefone=fone
    ).first()
    if lead:
        return lead

    # Match pelos últimos 11 dígitos (DDD + número)
    if len(fone) >= 11:
        sufixo = fone[-11:]
        lead = LeadProspecto.all_tenants.filter(
            tenant=tenant, telefone__endswith=sufixo
        ).first()
        if lead:
            return lead

    # Match pelos últimos 10 dígitos (telefone fixo)
    if len(fone) >= 10:
        sufixo = fone[-10:]
        lead = LeadProspecto.all_tenants.filter(
            tenant=tenant, telefone__endswith=sufixo
        ).first()

    return lead


def resolver_tenant(tenant_slug):
    """Resolve tenant pelo slug. Retorna None se não encontrado."""
    if not tenant_slug:
        return None
    return Tenant.objects.filter(slug=tenant_slug).first()


# ── Receber mensagem ───────────────────────────────────────────────────

def receber_mensagem(telefone, nome, conteudo, tenant, tipo_conteudo='texto',
                     identificador_externo='', metadata=None, canal_tipo='whatsapp',
                     arquivo_url='', arquivo_nome='', canal=None):
    """
    Processa mensagem recebida de qualquer fonte (N8N, widget, provider webhook, etc).

    1. Normaliza telefone
    2. Busca/cria Conversa
    3. Vincula LeadProspecto se encontrado
    4. Cria Mensagem
    5. Atualiza contadores da Conversa

    Param canal: CanalInbox já resolvido (vem do webhook dispatcher). Se None, faz get_or_create.
    Retorna (conversa, mensagem, nova_conversa).
    """
    fone = normalizar_telefone(telefone)

    # Buscar ou criar canal
    if canal is None:
        canal, _ = CanalInbox.all_tenants.get_or_create(
            tenant=tenant, tipo=canal_tipo, identificador_canal='',
            defaults={'nome': dict(CanalInbox.TIPO_CHOICES).get(canal_tipo, canal_tipo)}
        )

    # Buscar conversa aberta existente para este telefone+canal
    conversa = Conversa.all_tenants.filter(
        tenant=tenant,
        canal=canal,
        contato_telefone=fone,
        status__in=['aberta', 'pendente'],
    ).order_by('-ultima_mensagem_em').first()

    nova_conversa = False
    if conversa and not conversa.lead:
        # Conversa existe mas sem lead (foi deletado), vincular ou criar
        lead = buscar_lead_por_telefone(fone, tenant)
        if not lead:
            from apps.comercial.leads.models import LeadProspecto
            lead = LeadProspecto(
                tenant=tenant,
                nome_razaosocial=nome or fone,
                telefone=fone,
                origem='whatsapp' if canal_tipo == 'whatsapp' else 'outros',
                canal_entrada=canal_tipo,
                status_api=LeadProspecto.status_api_inicial(tenant),
            )
            lead.save()
            logger.info("[Inbox] Lead recriado para conversa sem lead: %s", lead.nome_razaosocial)
        conversa.lead = lead
        conversa.save(update_fields=['lead'])

    if not conversa:
        # Dedup cross-canal: mesmo lead com conversa ativa em canal diferente
        lead_tmp = buscar_lead_por_telefone(fone, tenant)
        if lead_tmp:
            conversa = Conversa.all_tenants.filter(
                tenant=tenant,
                lead=lead_tmp,
                status__in=['aberta', 'pendente'],
            ).exclude(canal=canal).order_by('-ultima_mensagem_em').first()

    if not conversa:
        nova_conversa = True
        lead = buscar_lead_por_telefone(fone, tenant)

        # Se não existe lead com esse telefone, criar automaticamente
        if not lead:
            from apps.comercial.leads.models import LeadProspecto
            lead = LeadProspecto(
                tenant=tenant,
                nome_razaosocial=nome or fone,
                telefone=fone,
                origem='whatsapp' if canal_tipo == 'whatsapp' else 'outros',
                canal_entrada=canal_tipo,
                tipo_entrada='receptivo',
                status_api=LeadProspecto.status_api_inicial(tenant),
            )
            lead._skip_crm_signal = True
            lead._skip_automacao = True
            lead._skip_segmento = True
            lead.save()
            logger.info("[Inbox] Lead criado automaticamente: %s (telefone=%s)", lead.nome_razaosocial, fone)

        conversa = Conversa(
            tenant=tenant,
            canal=canal,
            lead=lead,
            contato_nome=nome or lead.nome_razaosocial,
            contato_telefone=fone,
            contato_email=lead.email if lead.email else '',
            status='aberta',
        )
        conversa.save()

        # Criar HistoricoContato
        _criar_historico_contato(lead, fone, tenant)

        # Distribuição automática (equipe + fila + agente)
        from .distribution import distribuir_conversa, verificar_horario_atendimento

        if not verificar_horario_atendimento(tenant):
            from .models import ConfiguracaoInbox
            config = ConfiguracaoInbox.get_config()
            if config.mensagem_fora_horario:
                Mensagem(
                    tenant=tenant, conversa=conversa,
                    remetente_tipo='bot', remetente_nome='Assistente',
                    tipo_conteudo='texto',
                    conteudo=config.mensagem_fora_horario,
                ).save()

        distribuir_conversa(conversa, tenant)

    # Criar mensagem
    mensagem = Mensagem(
        tenant=tenant,
        conversa=conversa,
        remetente_tipo='contato',
        remetente_nome=nome or conversa.contato_nome,
        tipo_conteudo=tipo_conteudo,
        conteudo=conteudo or '',
        arquivo_url=arquivo_url,
        arquivo_nome=arquivo_nome,
        identificador_externo=identificador_externo,
        metadata=metadata or {},
    )
    mensagem.save()

    # Atualizar conversa
    conversa.ultima_mensagem_em = mensagem.data_envio
    conversa.ultima_mensagem_preview = preview_mensagem(conteudo, tipo_conteudo)
    conversa.mensagens_nao_lidas = (conversa.mensagens_nao_lidas or 0) + 1

    # Se estava resolvida/arquivada, reabrir
    if conversa.status in ['resolvida', 'arquivada']:
        conversa.status = 'aberta'
        conversa.data_resolucao = None
        conversa.data_arquivamento = None

    conversa.save(update_fields=[
        'ultima_mensagem_em', 'ultima_mensagem_preview',
        'mensagens_nao_lidas', 'status', 'data_resolucao', 'data_arquivamento',
    ])

    # Notificar via WebSocket
    _notificar_ws_nova_mensagem(conversa, mensagem)

    return conversa, mensagem, nova_conversa


def _criar_historico_contato(lead, telefone, tenant):
    """Cria HistoricoContato para manter compatibilidade com pipeline existente."""
    from apps.comercial.leads.models import HistoricoContato

    HistoricoContato(
        tenant=tenant,
        lead=lead,
        telefone=telefone,
        status='fluxo_inicializado',
        data_hora_contato=timezone.now(),
        observacoes='Conversa iniciada via Inbox',
    ).save()


# ── Enviar mensagem ────────────────────────────────────────────────────

def enviar_mensagem(conversa, conteudo, user, tipo_conteudo='texto',
                    arquivo_url='', arquivo_nome=''):
    """
    Envia mensagem do agente para o contato.

    1. Cria Mensagem
    2. Calcula tempo_primeira_resposta se aplicável
    3. Envia via webhook (se configurado no canal)

    Retorna mensagem.
    """
    mensagem = Mensagem(
        tenant=conversa.tenant,
        conversa=conversa,
        remetente_tipo='agente',
        remetente_user=user,
        remetente_nome=user.get_full_name() or user.username,
        tipo_conteudo=tipo_conteudo,
        conteudo=conteudo,
        arquivo_url=arquivo_url,
        arquivo_nome=arquivo_nome,
    )
    mensagem.save()

    # Calcular tempo de primeira resposta
    if conversa.tempo_primeira_resposta_seg is None:
        delta = timezone.now() - conversa.data_abertura
        conversa.tempo_primeira_resposta_seg = int(delta.total_seconds())

    # Atualizar conversa
    conversa.ultima_mensagem_em = mensagem.data_envio
    conversa.ultima_mensagem_preview = preview_mensagem(conteudo, tipo_conteudo)
    conversa.mensagens_nao_lidas = 0

    update_fields = [
        'ultima_mensagem_em', 'ultima_mensagem_preview',
        'mensagens_nao_lidas', 'tempo_primeira_resposta_seg',
    ]

    # Bloqueia envio se conversa ainda não foi assumida pelo agente
    if conversa.agente_id and not conversa.assumida:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Assuma a conversa antes de responder.")

    # Se estava aberta sem agente, atribuir e assumir automaticamente
    if not conversa.agente_id:
        conversa.agente = user
        conversa.assumida = True
        if not conversa.data_assumida:
            conversa.data_assumida = timezone.now()
            update_fields.append('data_assumida')
        _vincular_agente_oportunidade(conversa, user)
        update_fields.extend(['agente', 'assumida'])

    # Quando agente responde, conversa vira humana — silencia o bot externo
    if conversa.modo_atendimento != 'humano':
        conversa.modo_atendimento = 'humano'
        update_fields.append('modo_atendimento')

    # Atribui fila padrao se ainda nao tem — sem isso, conversa fica
    # invisivel pras outras vendedoras da equipe (filtro do Inbox exige
    # fila da equipe pra mostrar conversa nao-atribuida).
    if not conversa.fila_id:
        from apps.inbox.models import FilaInbox
        fila = FilaInbox.all_tenants.filter(
            tenant=conversa.tenant, ativo=True,
        ).order_by('-prioridade').first()
        if fila:
            conversa.fila = fila
            update_fields.append('fila')
            if not conversa.equipe_id and fila.equipe_id:
                conversa.equipe = fila.equipe
                update_fields.append('equipe')

    # Infere equipe do agente que esta respondendo, se ainda vazia
    if not conversa.equipe_id:
        from apps.inbox.models import MembroEquipeInbox
        membro = MembroEquipeInbox.all_tenants.filter(
            tenant=conversa.tenant, user=user
        ).select_related('equipe').first()
        if membro:
            conversa.equipe = membro.equipe
            update_fields.append('equipe')

    conversa.save(update_fields=update_fields)

    # Log de auditoria
    from apps.sistema.utils import registrar_acao
    registrar_acao('inbox', 'enviar_mensagem', 'conversa', conversa.pk,
                   f'Mensagem enviada por {user.username} para {conversa.contato_nome}',
                   dados_extras={'canal': conversa.canal.tipo if conversa.canal_id else ''})

    # Enviar via webhook externo (fire-and-forget)
    _enviar_webhook_async(conversa, mensagem)

    # Notificar via WebSocket
    _notificar_ws_nova_mensagem(conversa, mensagem)

    return mensagem


def _enviar_webhook_async(conversa, mensagem):
    """Envia mensagem via provider correto em background thread."""
    canal = conversa.canal

    def _send():
        _RETRY_DELAYS = [2, 5, 10]
        last_exc = None
        for attempt in range(len(_RETRY_DELAYS) + 1):
            try:
                if canal.provedor and canal.integracao:
                    from apps.inbox.providers import get_provider
                    provider = get_provider(canal)
                    result = provider.enviar_mensagem(conversa, mensagem)
                    msg_id = provider.extrair_msg_id(result)
                    if msg_id:
                        Mensagem.all_tenants.filter(pk=mensagem.pk).update(identificador_externo=msg_id)
                    logger.info("[Provider:%s] Mensagem enviada para %s (tentativa %d)", canal.provedor, conversa.contato_telefone, attempt + 1)
                else:
                    _enviar_via_webhook_legado(conversa, mensagem)
                return  # sucesso
            except Exception as e:
                last_exc = e
                if attempt < len(_RETRY_DELAYS):
                    logger.warning("[Inbox] Falha ao enviar (tentativa %d/%d): %s — retry em %ds", attempt + 1, len(_RETRY_DELAYS) + 1, e, _RETRY_DELAYS[attempt])
                    time.sleep(_RETRY_DELAYS[attempt])
        logger.error("Erro ao enviar mensagem após %d tentativas: %s", len(_RETRY_DELAYS) + 1, last_exc)
        Mensagem.all_tenants.filter(pk=mensagem.pk).update(erro_envio=str(last_exc)[:500])

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()


def _enviar_via_webhook_legado(conversa, mensagem):
    """Fallback: envia via webhook_envio_url do canal (N8N, custom)."""
    webhook_url = (conversa.canal.configuracao or {}).get('webhook_envio_url')
    if not webhook_url:
        return

    payload = {
        'conversa_id': conversa.id,
        'conversa_numero': conversa.numero,
        'telefone': conversa.contato_telefone,
        'nome': conversa.contato_nome,
        'mensagem': mensagem.conteudo,
        'tipo': mensagem.tipo_conteudo,
        'arquivo_url': mensagem.arquivo_url,
        'agente': mensagem.remetente_nome,
        'tenant': conversa.tenant.slug if conversa.tenant else '',
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code >= 400:
            logger.warning("Webhook inbox falhou: status=%s url=%s", resp.status_code, webhook_url)
            Mensagem.all_tenants.filter(pk=mensagem.pk).update(
                erro_envio=f"Webhook retornou {resp.status_code}"
            )
    except Exception as e:
        logger.error("Erro ao enviar webhook inbox: %s", e)
        Mensagem.all_tenants.filter(pk=mensagem.pk).update(erro_envio=str(e)[:500])


# ── Vincular agente a oportunidade ────────────────────────────────────

def _vincular_agente_oportunidade(conversa, agente):
    """Quando um agente e atribuido a uma conversa, atribui como responsavel
    da oportunidade mais recente sem responsavel do lead."""
    if not conversa.lead or not agente:
        return
    try:
        from apps.comercial.crm.models import OportunidadeVenda
        oport = OportunidadeVenda.objects.filter(
            lead=conversa.lead,
            responsavel__isnull=True,
            ativo=True,
        ).order_by('-data_criacao').first()
        if oport:
            oport.responsavel = agente
            oport.save(update_fields=['responsavel'])
            logger.info("Oportunidade #%s atribuida a %s (via conversa #%s)",
                        oport.pk, agente.username, conversa.numero)
    except Exception as e:
        logger.error("Erro ao vincular agente a oportunidade: %s", e)


# ── Ações de conversa ──────────────────────────────────────────────────

def atribuir_conversa(conversa, agente, atribuido_por=None):
    """Atribui conversa a um agente e cria mensagem de sistema.

    Side effects:
      - modo_atendimento vira 'humano' (silencia bot externo)
      - equipe inferida da primeira equipe do agente no tenant, se vazia
    """
    from apps.inbox.models import MembroEquipeInbox

    conversa.agente = agente
    conversa.assumida = False  # novo agente precisa assumir explicitamente
    updates = ['agente', 'assumida']

    # Silencia o bot — quando agente entra, conversa fica em modo humano
    if conversa.modo_atendimento != 'humano':
        conversa.modo_atendimento = 'humano'
        updates.append('modo_atendimento')

    # Infere equipe do agente se ainda nao tem
    if not conversa.equipe_id:
        membro = MembroEquipeInbox.all_tenants.filter(
            tenant=conversa.tenant, user=agente
        ).select_related('equipe').first()
        if membro:
            conversa.equipe = membro.equipe
            updates.append('equipe')

    conversa.save(update_fields=updates)
    _vincular_agente_oportunidade(conversa, agente)

    nome_atribuidor = ''
    if atribuido_por:
        nome_atribuidor = atribuido_por.get_full_name() or atribuido_por.username

    nome_agente = agente.get_full_name() or agente.username

    Mensagem(
        tenant=conversa.tenant,
        conversa=conversa,
        remetente_tipo='sistema',
        remetente_nome='Sistema',
        tipo_conteudo='sistema',
        conteudo=f"Conversa atribuída a {nome_agente}" + (
            f" por {nome_atribuidor}" if nome_atribuidor else ""
        ),
    ).save()

    return conversa


def assumir_conversa(conversa, agente):
    """Agente assume explicitamente a conversa — libera histórico e input.

    Regras:
    - Se já assumida por outro agente: levanta ValueError
    - Se não atribuída: atribui ao agente que está assumindo
    - Seta assumida=True
    """
    if conversa.assumida and conversa.agente_id and conversa.agente_id != agente.pk:
        raise ValueError("Conversa já assumida por outro agente.")

    updates = ['assumida']

    if not conversa.agente_id:
        conversa.agente = agente
        _vincular_agente_oportunidade(conversa, agente)
        updates.append('agente')

    if conversa.modo_atendimento != 'humano':
        conversa.modo_atendimento = 'humano'
        updates.append('modo_atendimento')

    conversa.assumida = True
    if not conversa.data_assumida:
        conversa.data_assumida = timezone.now()
        updates.append('data_assumida')
    conversa.save(update_fields=updates)
    return conversa


def _invalidar_vero_session(telefone, tenant_slug=None):
    """Chama o webhook N8N 'Reset Vero Session' (apaga a row de `vero_session`
    desse telefone no banco do Vero). Sincrono com timeout 5s — falha silenciosa.

    Por que sincrono: quando o `resolver_conversa` roda via subprocess do
    dispatcher_cron (ex: encerrar_inativos), threads daemon sao mortas com
    o processo. Chamar sincrono garante que o reset chega antes de retornar.

    Configuravel via env var `VERO_RESET_WEBHOOK_URL`. Se vazia, no-op."""
    from django.conf import settings
    import os
    url = getattr(settings, 'VERO_RESET_WEBHOOK_URL', None) or os.environ.get('VERO_RESET_WEBHOOK_URL', '')
    if not url or not telefone:
        return
    try:
        requests.post(url, json={
            'telefone': telefone,
            'tenant_slug': tenant_slug or '',
        }, timeout=5)
    except Exception as e:
        logger.warning('falha invalidando vero session (telefone=%s): %s', telefone, e)


def resolver_conversa(conversa, user, motivo=None, *,
                       oportunidade_estagio_id=None,
                       oportunidade_motivo_perda_ref_id=None,
                       oportunidade_motivo_perda_texto=None,
                       oportunidade_concorrente=None):
    """Marca conversa como resolvida (idempotente — no-op se ja resolvida).
    user pode ser None em encerramentos de sistema (ex: por inatividade).
    motivo: MotivoEncerramento opcional (preenche Conversa.motivo_encerramento).

    T148/T149 — Params opcionais pra mover a oportunidade vinculada (Conversa.oportunidade)
    na mesma operacao:
      oportunidade_estagio_id: id do PipelineEstagio destino (Ganha/Perdida/Negociacao)
      oportunidade_motivo_perda_ref_id: id do MotivoPerda (se estagio destino e perdido)
      oportunidade_motivo_perda_texto: observacao livre
      oportunidade_concorrente: nome do concorrente (se motivo for "Concorrente")
    Se conversa nao tem oportunidade vinculada, params sao ignorados.

    Side effect: ao encerrar, dispara `_invalidar_vero_session` pro telefone
    da conversa (Hubtrix vira fonte da verdade: encerrou aqui -> Vero esquece
    o estado antigo daquele cliente)."""
    if conversa.status == 'resolvida':
        return conversa

    conversa.status = 'resolvida'
    conversa.data_resolucao = timezone.now()
    conversa.mensagens_nao_lidas = 0
    update_fields = ['status', 'data_resolucao', 'mensagens_nao_lidas']
    if motivo is not None:
        conversa.motivo_encerramento = motivo
        update_fields.append('motivo_encerramento')
    conversa.save(update_fields=update_fields)

    nome = (user.get_full_name() or user.username) if user else 'Sistema'
    motivo_sufixo = f" · {motivo.nome}" if motivo else ''
    Mensagem(
        tenant=conversa.tenant,
        conversa=conversa,
        remetente_tipo='sistema',
        remetente_nome='Sistema',
        tipo_conteudo='sistema',
        conteudo=f"Conversa resolvida por {nome}{motivo_sufixo}",
    ).save()

    _notificar_ws_conversa_alterada(conversa, {'status': 'resolvida'})

    # CSAT automático — criar registro e enviar mensagem de avaliação ao contato
    try:
        from .models import AvaliacaoAtendimento
        if conversa.agente_id and not AvaliacaoAtendimento.objects.filter(conversa=conversa).exists():
            AvaliacaoAtendimento.objects.create(
                tenant=conversa.tenant,
                conversa=conversa,
                data_envio=timezone.now(),
            )
            msg_csat = Mensagem(
                tenant=conversa.tenant,
                conversa=conversa,
                remetente_tipo='bot',
                remetente_nome='Sistema',
                tipo_conteudo='texto',
                conteudo='Obrigado pelo contato! Como você avalia nosso atendimento? Responda com uma nota de 1 a 5 (1 = ruim, 5 = excelente).',
            )
            msg_csat.save()
            _enviar_webhook_async(conversa, msg_csat)
    except Exception:
        pass  # CSAT não bloqueia o encerramento

    # Sinaliza Vero pra apagar a session do telefone — bot atende do zero
    # na proxima mensagem do mesmo cliente. Sincrono, timeout 5s, falha silenciosa.
    _invalidar_vero_session(
        conversa.contato_telefone,
        conversa.tenant.slug if conversa.tenant_id else None,
    )

    # T148/T149 — Se solicitado, move oportunidade vinculada
    if oportunidade_estagio_id and conversa.oportunidade_id:
        try:
            from apps.comercial.crm.models import OportunidadeVenda, PipelineEstagio
            from django.utils import timezone as _tz
            op = OportunidadeVenda.all_tenants.filter(
                tenant=conversa.tenant, pk=conversa.oportunidade_id, ativo=True,
            ).first()
            estagio_destino = PipelineEstagio.all_tenants.filter(
                tenant=conversa.tenant, pk=oportunidade_estagio_id,
            ).first()
            if op and estagio_destino and op.estagio_id != estagio_destino.id:
                # Idempotente: se ja esta em estagio final (ganho ou perdido), no-op
                if not (op.estagio and (op.estagio.is_final_ganho or op.estagio.is_final_perdido)):
                    campos = ['estagio', 'data_entrada_estagio', 'probabilidade', 'data_atualizacao']
                    op.estagio = estagio_destino
                    op.data_entrada_estagio = _tz.now()
                    op.probabilidade = estagio_destino.probabilidade_padrao
                    if estagio_destino.is_final_ganho and not op.data_fechamento_real:
                        op.data_fechamento_real = _tz.now()
                        campos.append('data_fechamento_real')
                    if estagio_destino.is_final_perdido:
                        if oportunidade_motivo_perda_ref_id:
                            op.motivo_perda_ref_id = oportunidade_motivo_perda_ref_id
                            campos.append('motivo_perda_ref')
                        if oportunidade_motivo_perda_texto:
                            op.motivo_perda = oportunidade_motivo_perda_texto
                            campos.append('motivo_perda')
                        if oportunidade_concorrente:
                            op.concorrente_perdido = oportunidade_concorrente
                            campos.append('concorrente_perdido')
                        # Origem rastreavel: humano se user definido, bot se chamado por sistema (cron)
                        op.motivo_perda_origem = 'humano' if user else 'bot'
                        campos.append('motivo_perda_origem')
                    op.save(update_fields=campos)
                    logger.info(
                        'resolver_conversa: oportunidade #%s movida pra estagio "%s" via resolucao da conversa #%s',
                        op.pk, estagio_destino.nome, conversa.pk,
                    )
        except Exception as e:
            logger.exception('resolver_conversa: falha ao mover oportunidade vinculada: %s', e)

    return conversa


def encerrar_por_inatividade(conversa):
    """Encerra (resolve) por inatividade: se aviso configurado, envia a mensagem
    pelo canal (via webhook) e marca o motivo de sistema 'auto_inatividade'.
    Idempotente — se ja resolvida, no-op."""
    from apps.inbox.models import ConfiguracaoInbox, MotivoEncerramento

    if conversa.status == 'resolvida':
        return conversa

    cfg = ConfiguracaoInbox.all_tenants.filter(tenant=conversa.tenant).first()
    aviso_texto = (cfg.encerramento_auto_aviso_texto or '').strip() if cfg else ''
    aviso_on = bool(cfg and cfg.encerramento_auto_aviso_ativo and aviso_texto)

    if aviso_on:
        msg = Mensagem(
            tenant=conversa.tenant, conversa=conversa,
            remetente_tipo='sistema', remetente_nome='Sistema',
            tipo_conteudo='texto', conteudo=aviso_texto,
        )
        msg.save()
        conversa.ultima_mensagem_em = msg.data_envio
        conversa.ultima_mensagem_preview = preview_mensagem(aviso_texto, 'texto')
        conversa.save(update_fields=['ultima_mensagem_em', 'ultima_mensagem_preview'])
        _enviar_webhook_async(conversa, msg)
        _notificar_ws_nova_mensagem(conversa, msg)

    motivo = MotivoEncerramento.all_tenants.filter(
        tenant=conversa.tenant, codigo=MotivoEncerramento.CODIGO_AUTO
    ).first()

    # T149 — se config ativa, repassa params pra resolver_conversa mover oportunidade junto
    op_estagio_id = None
    op_motivo_perda_ref_id = None
    if (cfg and cfg.encerramento_auto_fecha_oportunidade
            and cfg.encerramento_auto_oportunidade_estagio_id
            and conversa.oportunidade_id):
        op_estagio_id = cfg.encerramento_auto_oportunidade_estagio_id
        op_motivo_perda_ref_id = cfg.encerramento_auto_motivo_perda_ref_id

    return resolver_conversa(
        conversa, user=None, motivo=motivo,
        oportunidade_estagio_id=op_estagio_id,
        oportunidade_motivo_perda_ref_id=op_motivo_perda_ref_id,
        oportunidade_motivo_perda_texto='Encerrado automaticamente por inatividade da conversa.' if op_estagio_id else None,
    )


def reabrir_conversa(conversa, user):
    """Reabre uma conversa resolvida/arquivada."""
    conversa.status = 'aberta'
    conversa.data_resolucao = None
    conversa.data_arquivamento = None
    conversa.save(update_fields=['status', 'data_resolucao', 'data_arquivamento'])

    nome = user.get_full_name() or user.username
    Mensagem(
        tenant=conversa.tenant,
        conversa=conversa,
        remetente_tipo='sistema',
        remetente_nome='Sistema',
        tipo_conteudo='sistema',
        conteudo=f"Conversa reaberta por {nome}",
    ).save()

    _notificar_ws_conversa_alterada(conversa, {'status': 'aberta'})

    return conversa


def criar_ticket_de_conversa(conversa, titulo, user, categoria=None):
    """Cria um Ticket de suporte vinculado à conversa."""
    from apps.suporte.models import Ticket, CategoriaTicket

    cat = None
    if categoria:
        cat = CategoriaTicket.all_tenants.filter(
            tenant=conversa.tenant, slug=categoria
        ).first()

    # Montar descrição com preview das últimas mensagens
    ultimas = conversa.mensagens.order_by('-data_envio')[:10]
    historico = "\n".join(
        f"[{m.get_remetente_tipo_display()}] {m.conteudo[:200]}"
        for m in reversed(list(ultimas))
    )
    descricao = f"Ticket criado a partir da conversa #{conversa.numero}\n\n--- Histórico ---\n{historico}"

    ticket = Ticket(
        tenant=conversa.tenant,
        titulo=titulo,
        descricao=descricao,
        categoria=cat,
        solicitante=user,
        prioridade=conversa.prioridade,
    )
    ticket.save()

    conversa.ticket = ticket
    conversa.save(update_fields=['ticket'])

    Mensagem(
        tenant=conversa.tenant,
        conversa=conversa,
        remetente_tipo='sistema',
        remetente_nome='Sistema',
        tipo_conteudo='sistema',
        conteudo=f"Ticket #{ticket.numero} criado: {titulo}",
    ).save()

    return ticket


def marcar_mensagens_lidas(conversa):
    """Marca todas as mensagens não lidas de uma conversa como lidas."""
    agora = timezone.now()
    Mensagem.all_tenants.filter(
        conversa=conversa, lida=False, remetente_tipo='contato'
    ).update(lida=True, data_leitura=agora)
    conversa.mensagens_nao_lidas = 0
    conversa.save(update_fields=['mensagens_nao_lidas'])


def transferir_conversa(conversa, transferido_por, para_agente=None,
                        para_equipe=None, para_fila=None, motivo=''):
    """
    Transfere conversa para outro agente, equipe ou fila.

    1. Registra HistoricoTransferencia
    2. Atribui novo destino
    3. Se para equipe/fila sem agente, roda distribuição
    4. Cria mensagem de sistema
    """
    from .models import HistoricoTransferencia, EquipeInbox, FilaInbox

    historico = HistoricoTransferencia(
        tenant=conversa.tenant,
        conversa=conversa,
        tipo='transferir_manual',
        de_agente=conversa.agente,
        de_equipe=conversa.equipe,
        transferido_por=transferido_por,
        motivo=motivo,
    )

    nome_transferidor = transferido_por.get_full_name() or transferido_por.username
    msg_parts = [f"Conversa transferida por {nome_transferidor}"]

    if para_agente:
        historico.para_agente = para_agente
        conversa.agente = para_agente
        conversa.assumida = False  # destino precisa assumir
        nome_destino = para_agente.get_full_name() or para_agente.username
        msg_parts.append(f"para {nome_destino}")
        conversa.save(update_fields=['agente', 'assumida'])
        _vincular_agente_oportunidade(conversa, para_agente)

    elif para_fila:
        fila = FilaInbox.objects.filter(pk=para_fila.pk if hasattr(para_fila, 'pk') else para_fila).first()
        if fila:
            historico.para_fila = fila
            historico.para_equipe = fila.equipe
            conversa.fila = fila
            conversa.equipe = fila.equipe
            conversa.agente = None
            conversa.save(update_fields=['fila', 'equipe', 'agente'])
            msg_parts.append(f"para fila {fila.nome}")
            # Tentar distribuir
            from .distribution import distribuir_conversa
            distribuir_conversa(conversa, conversa.tenant)

    elif para_equipe:
        equipe = EquipeInbox.objects.filter(pk=para_equipe.pk if hasattr(para_equipe, 'pk') else para_equipe).first()
        if equipe:
            historico.para_equipe = equipe
            conversa.equipe = equipe
            conversa.agente = None
            conversa.save(update_fields=['equipe', 'agente'])
            msg_parts.append(f"para equipe {equipe.nome}")

    historico.save()

    Mensagem(
        tenant=conversa.tenant,
        conversa=conversa,
        remetente_tipo='sistema',
        remetente_nome='Sistema',
        tipo_conteudo='sistema',
        conteudo=' '.join(msg_parts),
    ).save()

    _notificar_ws_nova_mensagem(conversa, conversa.mensagens.order_by('-data_envio').first())

    return conversa


def receber_mensagem_widget(visitor_id, nome, conteudo, tenant, email='', telefone=''):
    """
    Processa mensagem do chat widget. Usa visitor_id (UUID do localStorage)
    para identificar o visitante em vez de telefone.
    """
    # Buscar canal widget
    canal, _ = CanalInbox.all_tenants.get_or_create(
        tenant=tenant, tipo='widget',
        defaults={'nome': 'Chat Widget'}
    )

    # Buscar conversa aberta para este visitor_id
    conversa = Conversa.all_tenants.filter(
        tenant=tenant,
        canal=canal,
        identificador_externo=visitor_id,
        status__in=['aberta', 'pendente'],
    ).order_by('-ultima_mensagem_em').first()

    nova_conversa = False
    if not conversa:
        nova_conversa = True

        # Tentar vincular a lead por email ou telefone
        lead = None
        if telefone:
            lead = buscar_lead_por_telefone(telefone, tenant)
        if not lead and email:
            from apps.comercial.leads.models import LeadProspecto
            lead = LeadProspecto.all_tenants.filter(
                tenant=tenant, email=email
            ).first()

        conversa = Conversa(
            tenant=tenant,
            canal=canal,
            lead=lead,
            contato_nome=nome,
            contato_telefone=normalizar_telefone(telefone) if telefone else '',
            contato_email=email,
            identificador_externo=visitor_id,
            status='aberta',
            metadata={'visitor_id': visitor_id, 'email': email},
        )
        conversa.save()

        # Distribuição automática
        from .distribution import distribuir_conversa, verificar_horario_atendimento

        if not verificar_horario_atendimento(tenant):
            from .models import ConfiguracaoInbox
            config = ConfiguracaoInbox.get_config()
            if config.mensagem_fora_horario:
                Mensagem(
                    tenant=tenant, conversa=conversa,
                    remetente_tipo='bot', remetente_nome='Assistente',
                    tipo_conteudo='texto',
                    conteudo=config.mensagem_fora_horario,
                ).save()

        distribuir_conversa(conversa, tenant)

    # Criar mensagem
    mensagem = Mensagem(
        tenant=tenant,
        conversa=conversa,
        remetente_tipo='contato',
        remetente_nome=nome or conversa.contato_nome,
        tipo_conteudo='texto',
        conteudo=conteudo,
    )
    mensagem.save()

    # Atualizar conversa
    conversa.ultima_mensagem_em = mensagem.data_envio
    conversa.ultima_mensagem_preview = preview_mensagem(conteudo, 'texto')
    conversa.mensagens_nao_lidas = (conversa.mensagens_nao_lidas or 0) + 1
    conversa.save(update_fields=[
        'ultima_mensagem_em', 'ultima_mensagem_preview', 'mensagens_nao_lidas',
    ])

    _notificar_ws_nova_mensagem(conversa, mensagem)

    return conversa, mensagem, nova_conversa


def atualizar_status_entrega(identificador_externo, status_entrega, tenant=None):
    """Atualiza status de entrega de uma mensagem via callback."""
    qs = Mensagem.all_tenants.filter(identificador_externo=identificador_externo)
    if tenant:
        qs = qs.filter(tenant=tenant)

    mensagem = qs.first()
    if not mensagem:
        return None

    if status_entrega == 'entregue':
        mensagem.data_entrega = timezone.now()
        mensagem.save(update_fields=['data_entrega'])
    elif status_entrega == 'lida':
        mensagem.data_entrega = mensagem.data_entrega or timezone.now()
        mensagem.lida = True
        mensagem.data_leitura = timezone.now()
        mensagem.save(update_fields=['data_entrega', 'lida', 'data_leitura'])

    return mensagem
