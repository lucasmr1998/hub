"""
Orquestracao da sessao do bot: acha/cria a `SessaoAtendimentoBot`, resolve o
checklist ativo do tenant e avanca pro proximo item.

Filtro de tenant sempre explicito nas queries daqui (nao confia so no
TenantManager): estas funcoes recebem `tenant` como parametro e precisam
continuar corretas mesmo chamadas fora de um request (teste, script).
"""
import logging

from apps.automacao.models import Checklist
from apps.automacao.services.checklist import proximo_item
from apps.comercial.leads.models import LeadProspecto

from ..models import SessaoAtendimentoBot

logger = logging.getLogger(__name__)

CONTEXTO_BOT_VENDAS = 'bot_vendas'

# Lead criado pelo bot antes de ter nome (primeira chamada de /ia/proximo-passo
# so manda cellphone). Nome real vem depois via item do checklist com `campo`
# mapeado, ou por atualizacao humana no CRM.
NOME_LEAD_SEM_IDENTIFICACAO = 'Lead WhatsApp'
ORIGEM_LEAD_BOT = 'whatsapp'

# Status que NAO travam a sessao pra reuso: uma nova rodada de /ia/proximo-passo
# com o mesmo lead/telefone continua na sessao aberta em vez de abrir outra.
_STATUS_REUTILIZAVEIS = ('em_andamento', 'aguardando_resposta', 'aguardando_recontato', 'transbordado')


def checklist_do_tenant(tenant, contexto=CONTEXTO_BOT_VENDAS):
    """Primeiro checklist ativo do tenant nesse contexto. None = tenant nao
    configurou checklist ainda (o endpoint responde transbordo, fail-safe)."""
    return (
        Checklist.objects
        .filter(tenant=tenant, contexto=contexto, ativo=True)
        .order_by('id')
        .first()
    )


def _criar_lead_minimo(tenant, cellphone):
    """Lead minimo pra ancorar a conversa antes de o checklist coletar nome
    de verdade. Espelha o minimo de `registrar_lead_api`
    (apps/comercial/leads/views.py), sem o guard de CPF (aqui nao ha CPF
    ainda, e a Fase 2 nao decide duplicidade, so abre a conversa)."""
    nome = f'{NOME_LEAD_SEM_IDENTIFICACAO} {cellphone}'.strip()
    return LeadProspecto.objects.create(
        tenant=tenant, nome_razaosocial=nome, telefone=cellphone or '',
        origem=ORIGEM_LEAD_BOT,
    )


def obter_ou_criar_sessao(tenant, cellphone, lead_id, checklist):
    """Acha a sessao em andamento desse lead ou telefone; cria lead minimo e
    sessao nova se nao existir nenhuma. Sessao `finalizada` nao conta como
    "em andamento": um novo ciclo do bot pro mesmo lead abre sessao nova."""
    lead = None
    if lead_id:
        lead = LeadProspecto.objects.filter(pk=lead_id, tenant=tenant).first()

    sessao = None
    if lead is not None:
        sessao = (
            SessaoAtendimentoBot.objects
            .filter(tenant=tenant, lead=lead, status__in=_STATUS_REUTILIZAVEIS)
            .order_by('-ultima_interacao_em')
            .first()
        )
    if sessao is None and cellphone:
        sessao = (
            SessaoAtendimentoBot.objects
            .filter(tenant=tenant, cellphone=cellphone, status__in=_STATUS_REUTILIZAVEIS)
            .order_by('-ultima_interacao_em')
            .first()
        )
        if sessao is not None and lead is not None and sessao.lead_id is None:
            # Sessao tinha comecado so com telefone (sem lead_id ainda); agora
            # o Matrix mandou o lead_id, casa os dois.
            sessao.lead = lead
            sessao.save(update_fields=['lead'])

    if sessao is not None:
        return sessao

    if lead is None:
        lead = _criar_lead_minimo(tenant, cellphone)

    return SessaoAtendimentoBot.objects.create(
        tenant=tenant, lead=lead, cellphone=cellphone or lead.telefone, checklist=checklist,
    )


def entidade_da_sessao(sessao):
    """(entidade_tipo, entidade_id) que os services do checklist (Fase 1)
    entendem. A sessao do bot hoje so ancora em LEAD; um checklist com
    entidade_alvo='oportunidade' nao e suportado nesta fase, cai no lead
    mesmo pra nao travar a conversa (so loga aviso)."""
    if sessao.checklist.entidade_alvo != 'lead':
        logger.warning(
            'Checklist %s tem entidade_alvo=%s; sessao do bot so suporta lead, usando o lead mesmo assim.',
            sessao.checklist_id, sessao.checklist.entidade_alvo,
        )
    return 'lead', sessao.lead_id


def avancar(sessao):
    """Recalcula `item_atual` (proximo item elegivel sem resposta) e zera
    `tentativas_item`. Chamado depois de registrar uma resposta valida (ou
    de pular um item que estourou tentativas)."""
    entidade_tipo, entidade_id = entidade_da_sessao(sessao)
    item = proximo_item(sessao.checklist, entidade_tipo, entidade_id)
    sessao.item_atual = item
    sessao.tentativas_item = 0
    sessao.save(update_fields=['item_atual', 'tentativas_item', 'ultima_interacao_em'])
    return item


def transbordar(sessao, motivo):
    """Marca a sessao como transbordada pra atendimento humano. Terminal
    (so um /ia/proximo-passo novo, se o lead reiniciar do zero, sai dai)."""
    sessao.status = 'transbordado'
    sessao.motivo_transbordo = motivo
    sessao.save(update_fields=['status', 'motivo_transbordo', 'ultima_interacao_em'])
