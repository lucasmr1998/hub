"""Sincronização automática do pipeline de INDICAÇÃO com o estado real no HubSoft."""
import logging
import os

import psycopg2
from django.utils import timezone

logger = logging.getLogger(__name__)


def _hubsoft_mirror_conn():
    return psycopg2.connect(
        host=os.environ['HUBSOFT_DB_HOST'], port=os.environ['HUBSOFT_DB_PORT'],
        dbname=os.environ['HUBSOFT_DB_NAME'], user=os.environ['HUBSOFT_DB_USER'],
        password=os.environ['HUBSOFT_DB_PASSWORD'], connect_timeout=10,
    )


def contrato_info(lead):
    """Lê aceite do contrato no espelho HubSoft (somente leitura)."""
    info = {
        'tem_contrato': False, 'aceito': False,
        'numero': '', 'data_aceito': '', 'id_contrato': None,
    }
    cpf = ''.join(ch for ch in (lead.cpf_cnpj or '') if ch.isdigit())
    if not cpf:
        return info
    try:
        conn = _hubsoft_mirror_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT cc.id_cliente_servico_contrato, cc.numero_contrato, cc.aceito, cc.data_aceito "
            "FROM cliente_servico_contrato cc "
            "JOIN cliente_servico cs ON cs.id_cliente_servico = cc.id_cliente_servico "
            "JOIN cliente cl ON cl.id_cliente = cs.id_cliente "
            "WHERE cl.cpf_cnpj = %s AND cc.deleted_at IS NULL "
            "ORDER BY cc.id_cliente_servico_contrato DESC LIMIT 1",
            [cpf],
        )
        row = cur.fetchone()
        conn.close()
        if row:
            info['tem_contrato'] = True
            info['id_contrato'] = row[0]
            info['numero'] = row[1] or ''
            info['aceito'] = bool(row[2])
            info['data_aceito'] = str(row[3])[:10] if row[3] else ''
    except Exception as e:  # noqa: BLE001
        logger.warning('Status do contrato (indicação) falhou lead=%s: %s', lead.pk, e)
    return info


def mover_para_slug(oportunidade, slug, user=None, motivo=''):
    """Move a oportunidade para o estágio (por slug), gravando histórico."""
    from crm.models import HistoricoPipelineEstagio, PipelineEstagio

    estagio = PipelineEstagio.objects.filter(slug=slug, ativo=True).first()
    if not estagio or oportunidade.estagio_id == estagio.id:
        return False
    horas = (timezone.now() - oportunidade.data_entrada_estagio).total_seconds() / 3600
    HistoricoPipelineEstagio.objects.create(
        oportunidade=oportunidade,
        estagio_anterior=oportunidade.estagio,
        estagio_novo=estagio,
        movido_por=user if getattr(user, 'is_authenticated', False) else None,
        motivo=motivo,
        tempo_no_estagio_horas=round(horas, 2),
    )
    oportunidade.estagio = estagio
    oportunidade.data_entrada_estagio = timezone.now()
    oportunidade.probabilidade = estagio.probabilidade_padrao
    campos = ['estagio', 'data_entrada_estagio', 'probabilidade', 'data_atualizacao']
    if estagio.is_final_ganho and not oportunidade.data_fechamento_real:
        oportunidade.data_fechamento_real = timezone.now()
        campos.append('data_fechamento_real')
    oportunidade.save(update_fields=campos)
    try:
        from crm.services.posvenda_sync import aplicar_tags_etapa
        aplicar_tags_etapa(oportunidade, slug)
    except Exception as e:  # noqa: BLE001
        logger.warning('Falha ao aplicar tags (mover slug=%s): %s', slug, e)
    return True


def lead_tem_servico_habilitado(lead):
    from integracoes.models import ServicoClienteHubsoft
    return ServicoClienteHubsoft.objects.filter(
        cliente__lead_id=lead.pk,
        status_prefixo='servico_habilitado',
    ).exists()


def sincronizar_contrato_assinado(oportunidade, user=None):
    """ind_apto → ind_cliente quando o contrato foi assinado."""
    if oportunidade.tipo != 'indicacao' or oportunidade.estagio.slug != 'ind_apto':
        return False
    lead = oportunidade.lead
    if not lead:
        return False
    info = contrato_info(lead)
    if not (info.get('aceito') or getattr(lead, 'contrato_aceito', False)):
        return False
    return mover_para_slug(
        oportunidade, 'ind_cliente', user,
        'Contrato assinado pelo cliente (indicação)',
    )


def sincronizar_atendimento_os_aberta(oportunidade, user=None):
    """ind_cliente → ind_agendado quando atendimento + O.S. já foram abertos."""
    if oportunidade.tipo != 'indicacao' or oportunidade.estagio.slug != 'ind_cliente':
        return False
    from integracoes.models import AgendamentoInstalacaoIA
    if not AgendamentoInstalacaoIA.objects.filter(
        lead=oportunidade.lead, status='agendado',
    ).exists():
        return False
    return mover_para_slug(
        oportunidade, 'ind_agendado', user,
        'Atendimento + O.S. abertos (sincronização automática)',
    )


def sincronizar_servico_habilitado(oportunidade, user=None):
    """ind_agendado → ind_concluido quando o serviço está habilitado no HubSoft."""
    if oportunidade.tipo != 'indicacao' or oportunidade.estagio.slug != 'ind_agendado':
        return False
    lead = oportunidade.lead
    if not lead or not lead_tem_servico_habilitado(lead):
        return False
    return mover_para_slug(
        oportunidade, 'ind_concluido', user,
        'Serviço habilitado no HubSoft (indicação)',
    )


def sincronizar_oportunidade_indicacao(oportunidade, user=None):
    """Aplica todas as transições automáticas possíveis para uma oportunidade."""
    if oportunidade.tipo != 'indicacao':
        return False
    if oportunidade.estagio.slug in ('ind_concluido', 'ind_perdido'):
        return False
    movido = False
    for fn in (sincronizar_contrato_assinado, sincronizar_atendimento_os_aberta,
               sincronizar_servico_habilitado):
        if fn(oportunidade, user):
            movido = True
            oportunidade.refresh_from_db(fields=['estagio', 'estagio_id', 'data_entrada_estagio'])
    return movido


def sincronizar_indicacao_do_lead(lead_id, user=None):
    from crm.models import OportunidadeVenda
    op = OportunidadeVenda.objects.filter(
        lead_id=lead_id, tipo='indicacao', ativo=True,
    ).select_related('lead', 'estagio').first()
    if not op:
        return False
    return sincronizar_oportunidade_indicacao(op, user)


def sincronizar_indicacao_pendentes(user=None):
    """Varre oportunidades de indicação abertas e reconcilia com HubSoft/agendamento."""
    from crm.models import OportunidadeVenda
    qs = OportunidadeVenda.objects.filter(
        ativo=True, tipo='indicacao',
    ).exclude(
        estagio__slug__in=['ind_concluido', 'ind_perdido'],
    ).select_related('lead', 'estagio')
    for op in qs:
        try:
            sincronizar_oportunidade_indicacao(op, user)
        except Exception as e:  # noqa: BLE001
            logger.warning('Sync indicação op=%s: %s', op.pk, e)
