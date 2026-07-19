"""Service que processa NewService finalizados → Atendimento+OS no Matrix/Hubsoft.

Espelha o fluxo do `agendamento_ia.executar_agendamento` mas usa os dados do
NewService (endereço novo, plano novo, data/turno) em vez do LeadProspecto.

Fluxo:
1. Pré-sync ClienteHubsoft pelo CPF do lead
2. Pega id_cliente_servico do PRIMEIRO serviço ativo do cliente (atendimento
   é amarrado a algum serviço — o operador depois associa OS ao serviço novo)
3. Consulta agenda Matrix (cidade do NewService, data, turno)
4. Abre atendimento → abre OS
5. Persiste tudo nos campos matrix_sync_* do NewService

Worker `processar_newservice_finalizados` chama essa função em loop.
"""
from __future__ import annotations

import logging
from datetime import datetime

from django.utils import timezone

from datetime import datetime, timedelta

from integracoes.models import ClienteHubsoft, IntegracaoAPI, ServicoClienteHubsoft
from integracoes.services.matrix import MatrixService, MatrixServiceError
from vendas_web.models import NewService

logger = logging.getLogger(__name__)


class AgendamentoNewServiceError(Exception):
    pass


def _get_matrix_service() -> MatrixService:
    integ = IntegracaoAPI.objects.filter(tipo='matrix', ativa=True).first()
    if not integ:
        raise AgendamentoNewServiceError('Integração Matrix não configurada')
    return MatrixService(integ)


def _telefone_sem_55(telefone: str) -> str:
    t = (telefone or '').strip()
    if len(t) > 11 and t.startswith('55'):
        return t[2:]
    return t


def _montar_descricao_ns(ns: NewService) -> str:
    """Descrição do atendimento usando dados do NewService.

    Endereço, plano, vencimento vêm do NewService (nova contratação).
    Dados pessoais (nome, CPF) vêm do lead.
    """
    lead = ns.lead
    return (
        f'*Nova contratacao - Cliente existente* '
        f'Cliente: {lead.nome_razaosocial or "?"} '
        f'CPF: {lead.cpf_cnpj or "?"} '
        f'Endereco instalacao: {ns.rua or "?"}, N {ns.numero_residencia or "?"} '
        f'{ns.bairro or "?"} {ns.cidade or "?"}-{ns.estado or "?"} '
        f'CEP: {ns.cep or "?"} '
        f'Tipo imovel: {ns.tipo_imovel or "?"} ({ns.tipo_residencia or "-"}) '
        f'Plano ID: {ns.id_plano_rp or "?"} R$ {ns.valor or "?"} '
        f'Venc ID: {ns.id_dia_vencimento or "?"} '
        f'Ponto ref: {ns.ponto_referencia or "-"} '
        f'NewService #{ns.pk}. Solicitado via WhatsApp.'
    )


def _parse_data_cadastro(s: str | None) -> datetime | None:
    """Parseia data_cadastro_servico (CharField) em vários formatos do Hubsoft."""
    if not s:
        return None
    s = s.strip()
    for fmt in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%d/%m/%Y',
                '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _obter_id_cliente_servico(ns: NewService) -> int | None:
    """Acha o `id_cliente_servico` do serviço NOVO criado no Hubsoft pelo
    webdriver pra esta contratação específica.

    Critérios de match (em ordem de precedência):
      1. ServicoClienteHubsoft.cliente bate pelo CPF do lead
      2. id_servico == ns.id_plano_rp (mesmo plano contratado)
      3. status_prefixo indica "aguardando instalação" (serviço novo,
         ainda não habilitado — não pega serviço antigo já ativo)
      4. data_cadastro_servico parseável e >= ns.finalizado_em - 5min
         (margem pra clock skew; aceita serviço criado ATÉ 5 min antes
         do bot marcar como finalizado, cobre delay do webdriver)
      5. NÃO está vinculado a outro NewService.id_cliente_servico_origem
         (cada cs só pode ser usado UMA vez — um serviço/uma OS)
      6. Pega o de data_cadastro mais ANTIGA dentre os matches válidos
         (FIFO — primeira contratação que chegou pega o primeiro
         serviço criado).

    Retorna None se nenhum match encontrado — signal/worker retentam
    depois, dando tempo do webdriver criar o serviço no Hubsoft.
    """
    lead = ns.lead
    if not lead or not lead.cpf_cnpj:
        return None
    cliente = ClienteHubsoft.objects.filter(cpf_cnpj=lead.cpf_cnpj).first()
    if not cliente:
        return None

    # IDs de serviço já consumidos por OUTROS NewServices do mesmo cliente
    cs_usados = set(
        NewService.objects
        .filter(lead__cpf_cnpj=lead.cpf_cnpj)
        .exclude(pk=ns.pk)
        .exclude(id_cliente_servico_origem__isnull=True)
        .values_list('id_cliente_servico_origem', flat=True)
    )

    referencia_dt = ns.finalizado_em or ns.criado_em
    if referencia_dt is None:
        return None
    # data_cadastro_servico vem do Hubsoft em horário LOCAL (Brasília).
    # finalizado_em vem do Django em UTC. Converte pra local antes de
    # comparar naive, senão o filtro de margem rejeita serviços válidos.
    if referencia_dt.tzinfo:
        from django.utils import timezone
        ref_local = timezone.localtime(referencia_dt)
        margem_naive = (ref_local - timedelta(minutes=5)).replace(tzinfo=None)
    else:
        margem_naive = referencia_dt - timedelta(minutes=5)

    candidatos = []
    qs = ServicoClienteHubsoft.objects.filter(
        cliente=cliente,
        id_servico=ns.id_plano_rp,
        status_prefixo__icontains='aguard',
    ).exclude(id_cliente_servico__in=cs_usados)

    for s in qs:
        dt_cad = _parse_data_cadastro(s.data_cadastro_servico)
        if dt_cad is None:
            # Sem data parseável → ignora (pode ser serviço antigo migrado)
            continue
        if dt_cad < margem_naive:
            continue
        candidatos.append((dt_cad, s.id_cliente_servico))

    if not candidatos:
        logger.info(
            'Nenhum serviço novo Hubsoft compatível com NS %s (plano=%s, '
            'finalizado_em=%s). cs já usados=%s. Aguardando webdriver.',
            ns.pk, ns.id_plano_rp, referencia_dt, cs_usados,
        )
        return None

    # Mais antigo primeiro (FIFO: primeira contratação pega 1º serviço criado)
    candidatos.sort(key=lambda t: t[0])
    cs_escolhido = candidatos[0][1]
    logger.info(
        'NS %s → cs=%s (plano=%s, criado em %s). Excluídos: %s',
        ns.pk, cs_escolhido, ns.id_plano_rp, candidatos[0][0], cs_usados,
    )
    return cs_escolhido


def _pre_sync_cliente(ns: NewService) -> None:
    """Garante ClienteHubsoft + ServicoClienteHubsoft atualizados localmente."""
    try:
        from integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
        integ = IntegracaoAPI.objects.filter(tipo='hubsoft', ativa=True).first()
        if integ and ns.lead and ns.lead.cpf_cnpj:
            try:
                HubsoftService(integ).sincronizar_cliente(ns.lead)
                logger.info('NewService %s: lead %s pré-sync Hubsoft OK',
                            ns.pk, ns.lead_id)
            except HubsoftServiceError as e:
                logger.warning('NewService %s: pré-sync falhou (segue): %s', ns.pk, e)
    except Exception as e:
        logger.warning('NewService %s: pré-sync pulado: %s', ns.pk, e)


def _salvar(ns: NewService, **campos):
    for k, v in campos.items():
        setattr(ns, k, v)
    ns.save(update_fields=list(campos.keys()) + ['atualizado_em'])


def executar_agendamento_new_service(ns: NewService) -> dict:
    """Processa um NewService finalizado: abre Atendimento + OS no Matrix.

    Idempotente — pode ser chamado várias vezes pelo worker. Se já está
    sincronizado, retorna sucesso imediato.
    """
    if ns.matrix_sync_status == 'sincronizado':
        return {'status': 'ja_sincronizado',
                'id_atendimento': ns.id_atendimento_matrix,
                'id_os': ns.id_os_matrix}

    if not ns.data_instalacao or not ns.turno_instalacao:
        _salvar(ns,
                matrix_sync_status='erro',
                ultimo_erro_sync_matrix='Sem data_instalacao ou turno_instalacao',
                tentativas_sync_matrix=ns.tentativas_sync_matrix + 1)
        return {'status': 'erro', 'mensagem': 'Sem data/turno'}

    _pre_sync_cliente(ns)

    id_cliente_servico = _obter_id_cliente_servico(ns)
    if not id_cliente_servico:
        _salvar(ns,
                matrix_sync_status='pendente',
                ultimo_erro_sync_matrix='Cliente ainda não sincronizado no Hubsoft',
                tentativas_sync_matrix=ns.tentativas_sync_matrix + 1)
        return {'status': 'aguardando_sync',
                'mensagem': 'Cliente ainda não sincronizado no Hubsoft'}

    _salvar(ns,
            matrix_sync_status='processando',
            id_cliente_servico_origem=id_cliente_servico,
            tentativas_sync_matrix=ns.tentativas_sync_matrix + 1)

    try:
        service = _get_matrix_service()
    except AgendamentoNewServiceError as e:
        _salvar(ns, matrix_sync_status='erro', ultimo_erro_sync_matrix=str(e))
        return {'status': 'erro', 'mensagem': str(e)}

    # 1) Consultar agenda
    data_dmy = ns.data_instalacao.strftime('%d/%m/%Y')
    try:
        resp_agenda = service.consultar_agenda(
            cidade=ns.cidade or ns.lead.cidade or '',
            data_referencia=data_dmy,
            turno=ns.turno_instalacao,
            qtd_vagas=1,
            lead=ns.lead,
        )
    except MatrixServiceError as e:
        _salvar(ns, matrix_sync_status='erro',
                ultimo_erro_sync_matrix=f'consultar_agenda: {e}')
        return {'status': 'erro', 'mensagem': str(e)}

    dados_agenda = (resp_agenda or {}).get('dados') or resp_agenda or {}
    disp = (dados_agenda.get('disponibilidade_turno') or [{}])[0]
    horario_str = disp.get('horario') or ''
    tecnicos = disp.get('tecnicos') or [{}]
    id_tecnico = tecnicos[0].get('id') if tecnicos else None
    id_agenda_os = dados_agenda.get('id_agenda_ordem_servico')

    if not (horario_str and id_tecnico and id_agenda_os):
        msg = (f'Agenda incompleta: horario={horario_str!r} '
               f'tecnico={id_tecnico!r} id_agenda={id_agenda_os!r}')
        _salvar(ns, matrix_sync_status='erro', ultimo_erro_sync_matrix=msg)
        return {'status': 'erro', 'mensagem': msg}

    # 2) Abrir atendimento
    try:
        resp_atend = service.abrir_atendimento(
            id_cliente_servico=id_cliente_servico,
            nome='ClienteNovoServico',
            telefone=_telefone_sem_55(ns.lead.telefone or ''),
            descricao=_montar_descricao_ns(ns),
            lead=ns.lead,
        )
    except MatrixServiceError as e:
        _salvar(ns, matrix_sync_status='erro',
                ultimo_erro_sync_matrix=f'abrir_atendimento: {e}')
        return {'status': 'erro', 'mensagem': str(e)}

    id_atendimento = (
        (resp_atend.get('atendimento') or {}).get('id_atendimento')
        or (resp_atend.get('dados') or {}).get('id_atendimento')
        or resp_atend.get('id_atendimento')
    )
    if not id_atendimento:
        _salvar(ns, matrix_sync_status='erro',
                ultimo_erro_sync_matrix='abrir_atendimento sem id_atendimento')
        return {'status': 'erro', 'mensagem': 'Falha ao abrir atendimento'}

    _salvar(ns, id_atendimento_matrix=id_atendimento)

    # 3) Abrir OS
    try:
        resp_os = service.abrir_os(
            id_atendimento=id_atendimento,
            id_agenda_os=id_agenda_os,
            data_inicio=ns.data_instalacao.strftime('%Y-%m-%d'),
            hora_inicio=horario_str,
            id_tecnico=id_tecnico,
            lead=ns.lead,
        )
    except MatrixServiceError as e:
        _salvar(ns, matrix_sync_status='erro',
                ultimo_erro_sync_matrix=f'abrir_os: {e}')
        return {'status': 'erro', 'mensagem': str(e)}

    id_os = (
        (resp_os.get('ordem_servico') or {}).get('id_ordem_servico')
        or (resp_os.get('dados') or {}).get('id_os')
        or resp_os.get('id_os')
        or resp_os.get('id_ordem_servico')
    )

    _salvar(ns,
            matrix_sync_status='sincronizado',
            id_os_matrix=id_os,
            data_sync_matrix=timezone.now(),
            ultimo_erro_sync_matrix='')

    logger.info(
        'NewService %s sincronizado: atendimento=%s os=%s data=%s turno=%s',
        ns.pk, id_atendimento, id_os, ns.data_instalacao, ns.turno_instalacao,
    )
    return {
        'status': 'sincronizado',
        'mensagem': 'Atendimento+OS abertos no Matrix',
        'id_atendimento': id_atendimento,
        'id_os': id_os,
    }
