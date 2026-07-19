"""Service de agendamento de instalação pro fluxo IA (WhatsApp).

Orquestra:
1. Verifica se o lead tem ClienteHubsoft + Servico (sincronizado)
2. Se SIM: consulta_agenda(cidade, data, turno) → abrir_atendimento → abrir_os
3. Persiste tudo em AgendamentoInstalacaoIA

Usado por:
- Endpoint /integracoes/api/agendar-instalacao-ia/<lead_id>/ (dispara após
  confirmação do cliente no WhatsApp)
- Management command processar_agendamentos_ia_pendentes (worker que
  reprocessa quando lead ainda não tinha sincronizado)
"""
from __future__ import annotations

import logging
from datetime import datetime

from django.utils import timezone

from integracoes.models import (
    AgendamentoInstalacaoIA,
    ClienteHubsoft,
    IntegracaoAPI,
)
from integracoes.services.matrix import MatrixService, MatrixServiceError
from vendas_web.models import LeadProspecto

logger = logging.getLogger(__name__)


class AgendamentoIAError(Exception):
    pass


def _get_matrix_service() -> MatrixService:
    integ = IntegracaoAPI.objects.filter(tipo='matrix', ativa=True).first()
    if not integ:
        raise AgendamentoIAError('Integração Matrix não configurada')
    return MatrixService(integ)


def _telefone_sem_55(telefone: str) -> str:
    """Remove o prefixo 55 do telefone, se houver."""
    t = (telefone or '').strip()
    if len(t) > 11 and t.startswith('55'):
        return t[2:]
    return t


def _montar_descricao(lead: LeadProspecto) -> str:
    """Monta a descrição do atendimento — mesmo padrão do site."""
    return (
        f'*Instalacao* '
        f'Cliente: {lead.nome_razaosocial or "?"} '
        f'CPF: {lead.cpf_cnpj or "?"} '
        f'Nascimento: {lead.data_nascimento or "?"} '
        f'Endereco: {lead.rua or "?"}, N {lead.numero_residencia or "?"} '
        f'{lead.bairro or "?"} {lead.cidade or "?"}-{lead.estado or "?"} '
        f'CEP: {lead.cep or "?"} '
        f'Plano ID: {lead.id_plano_rp or "?"} R$ {lead.valor or "?"} '
        f'Venc ID: {lead.id_dia_vencimento or "?"} '
        f'Cliente solicitou instalacao via WhatsApp. Dados validados via IA.'
    )


def _obter_id_cliente_servico(lead: LeadProspecto) -> int | None:
    """Retorna o id_cliente_servico do primeiro serviço ativo do lead.

    Retorna None se o lead ainda não foi sincronizado (sem ClienteHubsoft)
    ou se não houver serviços vinculados.
    """
    cliente = (
        ClienteHubsoft.objects
        .prefetch_related('servicos')
        .filter(lead_id=lead.pk)
        .first()
    )
    if not cliente:
        return None
    servico = cliente.servicos.first()
    return servico.id_cliente_servico if servico else None


def criar_ou_obter_agendamento(lead: LeadProspecto) -> AgendamentoInstalacaoIA:
    """Cria registro AgendamentoInstalacaoIA a partir dos dados do lead.

    Se já existe um agendamento ativo (não 'erro') pro lead, retorna ele.
    Senão cria novo com status='aguardando_sync'.
    """
    if not lead.turno_instalacao or not lead.data_instalacao:
        raise AgendamentoIAError(
            f'Lead {lead.pk} sem turno_instalacao ou data_instalacao definidos'
        )

    existente = (
        AgendamentoInstalacaoIA.objects
        .filter(lead=lead)
        .exclude(status='erro')
        .first()
    )
    if existente:
        return existente

    return AgendamentoInstalacaoIA.objects.create(
        lead=lead,
        turno=lead.turno_instalacao,
        data_instalacao=lead.data_instalacao,
        status='aguardando_sync',
    )


def executar_agendamento(agendamento: AgendamentoInstalacaoIA) -> dict:
    """Tenta executar o agendamento. Idempotente.

    Retorna dict com:
    - status: 'agendado' | 'aguardando_sync' | 'erro'
    - mensagem: texto pra log/cliente
    - dados: dict com horario, nome_tecnico, etc (se sucesso)
    """
    lead = agendamento.lead

    # ── 0) Sincroniza lead com Hubsoft ANTES de tudo ──────────────────
    # Garante que os dados do cliente + serviço estejam atualizados
    # localmente (ClienteHubsoft + ServicoClienteHubsoft) antes de
    # consultar agenda e abrir OS. Útil principalmente quando o cliente
    # acabou de virar cliente no Hubsoft e ainda não rodou o
    # sincronizador periódico.
    try:
        from integracoes.models import IntegracaoAPI
        from integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
        integ = IntegracaoAPI.objects.filter(tipo='hubsoft', ativa=True).first()
        if integ and lead.cpf_cnpj:
            try:
                HubsoftService(integ).sincronizar_cliente(lead)
                logger.info('Lead %s pré-sincronizado com Hubsoft antes do agendamento',
                            lead.pk)
            except HubsoftServiceError as e:
                logger.warning('sincronizar_cliente lead=%s falhou (segue): %s', lead.pk, e)
    except Exception as e:
        logger.warning('Pré-sync Hubsoft lead=%s pulado: %s', lead.pk, e)

    # ── 1) Cliente já sincronizou no Hubsoft? ──────────────────────────
    id_cliente_servico = _obter_id_cliente_servico(lead)
    if not id_cliente_servico:
        agendamento.status = 'aguardando_sync'
        agendamento.tentativas += 1
        agendamento.ultimo_erro = 'Cliente ainda não sincronizado no Hubsoft'
        agendamento.save(update_fields=['status', 'tentativas', 'ultimo_erro',
                                        'data_atualizacao'])
        return {
            'status': 'aguardando_sync',
            'mensagem': 'Cliente ainda não sincronizado no Hubsoft — worker reprocessa.',
            'dados': {},
        }

    # ── 2) Marca como processando + cacheia id_cliente_servico ─────────
    agendamento.status = 'processando'
    agendamento.tentativas += 1
    agendamento.id_cliente_servico = id_cliente_servico
    agendamento.save(update_fields=['status', 'tentativas', 'id_cliente_servico',
                                    'data_atualizacao'])

    try:
        service = _get_matrix_service()
    except AgendamentoIAError as e:
        agendamento.status = 'erro'
        agendamento.ultimo_erro = str(e)
        agendamento.save(update_fields=['status', 'ultimo_erro', 'data_atualizacao'])
        return {'status': 'erro', 'mensagem': str(e), 'dados': {}}

    # ── 3) Consultar agenda (pega horário + técnico + id_agenda_os) ────
    data_dmy = agendamento.data_instalacao.strftime('%d/%m/%Y')
    try:
        resp_agenda = service.consultar_agenda(
            cidade=lead.cidade or '',
            data_referencia=data_dmy,
            turno=agendamento.turno,
            qtd_vagas=1,
            lead=lead,
        )
    except MatrixServiceError as e:
        agendamento.status = 'erro'
        agendamento.ultimo_erro = f'consultar_agenda: {e}'
        agendamento.save(update_fields=['status', 'ultimo_erro', 'data_atualizacao'])
        return {'status': 'erro', 'mensagem': str(e), 'dados': {}}

    dados_agenda = (resp_agenda or {}).get('dados') or resp_agenda or {}
    disp = (dados_agenda.get('disponibilidade_turno') or [{}])[0]
    horario_str = disp.get('horario') or ''
    tecnicos = disp.get('tecnicos') or [{}]
    id_tecnico = tecnicos[0].get('id') if tecnicos else None
    nome_tecnico = tecnicos[0].get('nome') or '' if tecnicos else ''
    id_agenda_os = dados_agenda.get('id_agenda_ordem_servico')

    if not (horario_str and id_tecnico and id_agenda_os):
        msg = (f'Agenda incompleta: horario={horario_str!r} '
               f'tecnico={id_tecnico!r} id_agenda={id_agenda_os!r}')
        agendamento.status = 'erro'
        agendamento.ultimo_erro = msg
        agendamento.save(update_fields=['status', 'ultimo_erro', 'data_atualizacao'])
        return {'status': 'erro', 'mensagem': msg, 'dados': {}}

    try:
        horario_time = datetime.strptime(horario_str, '%H:%M:%S').time()
    except ValueError:
        try:
            horario_time = datetime.strptime(horario_str, '%H:%M').time()
        except ValueError:
            horario_time = None

    agendamento.horario = horario_time
    agendamento.id_tecnico = id_tecnico
    agendamento.nome_tecnico = nome_tecnico
    agendamento.id_agenda_os = id_agenda_os
    agendamento.save(update_fields=['horario', 'id_tecnico', 'nome_tecnico',
                                    'id_agenda_os', 'data_atualizacao'])

    # ── 4) Abrir atendimento ───────────────────────────────────────────
    try:
        resp_atend = service.abrir_atendimento(
            id_cliente_servico=id_cliente_servico,
            nome='ClienteVenda',
            telefone=_telefone_sem_55(lead.telefone or ''),
            descricao=_montar_descricao(lead),
            lead=lead,
        )
    except MatrixServiceError as e:
        agendamento.status = 'erro'
        agendamento.ultimo_erro = f'abrir_atendimento: {e}'
        agendamento.save(update_fields=['status', 'ultimo_erro', 'data_atualizacao'])
        return {'status': 'erro', 'mensagem': str(e), 'dados': {}}

    agendamento.dados_resposta_atendimento = resp_atend or {}
    id_atendimento = (
        (resp_atend.get('atendimento') or {}).get('id_atendimento')
        or (resp_atend.get('dados') or {}).get('id_atendimento')
        or resp_atend.get('id_atendimento')
    )
    if not id_atendimento:
        agendamento.status = 'erro'
        agendamento.ultimo_erro = 'abrir_atendimento sem id_atendimento'
        agendamento.save(update_fields=['status', 'ultimo_erro',
                                        'dados_resposta_atendimento',
                                        'data_atualizacao'])
        return {'status': 'erro', 'mensagem': 'Falha ao abrir atendimento', 'dados': {}}

    agendamento.id_atendimento_matrix = id_atendimento
    agendamento.save(update_fields=['id_atendimento_matrix',
                                    'dados_resposta_atendimento',
                                    'data_atualizacao'])

    # ── 5) Abrir OS ────────────────────────────────────────────────────
    try:
        resp_os = service.abrir_os(
            id_atendimento=id_atendimento,
            id_agenda_os=id_agenda_os,
            data_inicio=agendamento.data_instalacao.strftime('%Y-%m-%d'),
            hora_inicio=horario_str,
            id_tecnico=id_tecnico,
            lead=lead,
        )
    except MatrixServiceError as e:
        agendamento.status = 'erro'
        agendamento.ultimo_erro = f'abrir_os: {e}'
        agendamento.save(update_fields=['status', 'ultimo_erro', 'data_atualizacao'])
        return {'status': 'erro', 'mensagem': str(e), 'dados': {}}

    agendamento.dados_resposta_os = resp_os or {}
    id_os = (
        (resp_os.get('ordem_servico') or {}).get('id_ordem_servico')
        or (resp_os.get('dados') or {}).get('id_os')
        or resp_os.get('id_os')
        or resp_os.get('id_ordem_servico')
    )
    agendamento.id_os_matrix = id_os
    agendamento.status = 'agendado'
    agendamento.data_processado = timezone.now()
    agendamento.ultimo_erro = ''
    agendamento.save()

    logger.info(
        'Agendamento IA concluído: lead=%s data=%s turno=%s tecnico=%s OS=%s',
        lead.pk, agendamento.data_instalacao, agendamento.turno,
        nome_tecnico, id_os,
    )
    return {
        'status': 'agendado',
        'mensagem': 'Instalação agendada com sucesso',
        'dados': {
            'data': agendamento.data_instalacao.strftime('%d/%m/%Y'),
            'turno': agendamento.turno,
            'horario': horario_str,
            'nome_tecnico': nome_tecnico,
            'id_atendimento': id_atendimento,
            'id_os': id_os,
        },
    }
