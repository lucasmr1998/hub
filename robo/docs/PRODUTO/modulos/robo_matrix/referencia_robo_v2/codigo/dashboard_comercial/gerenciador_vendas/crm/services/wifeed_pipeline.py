"""Sincronização automática do pipeline WIFEED com o estado real no HubSoft.

Mesmo comportamento do pipeline de Indicação, porém com slugs próprios (wf_*) e
tipo='wifeed'. Reaproveita os helpers genéricos (agnósticos a pipeline)
`contrato_info` e `mover_para_slug` do módulo de indicação.
"""
import logging

from crm.services.indicacao_pipeline import (
    contrato_info,
    lead_tem_servico_habilitado,
    mover_para_slug,
)

logger = logging.getLogger(__name__)

# Reexporta helpers genéricos para quem importar deste módulo.
__all__ = [
    'contrato_info', 'mover_para_slug',
    'sincronizar_contrato_assinado', 'sincronizar_atendimento_os_aberta',
    'sincronizar_servico_habilitado', 'sincronizar_oportunidade_wifeed',
    'sincronizar_wifeed_do_lead', 'sincronizar_wifeed_pendentes',
]


def sincronizar_contrato_assinado(oportunidade, user=None):
    """wf_apto → wf_cliente quando o contrato foi assinado."""
    if oportunidade.tipo != 'wifeed' or oportunidade.estagio.slug != 'wf_apto':
        return False
    lead = oportunidade.lead
    if not lead:
        return False
    info = contrato_info(lead)
    if not (info.get('aceito') or getattr(lead, 'contrato_aceito', False)):
        return False
    return mover_para_slug(
        oportunidade, 'wf_cliente', user,
        'Contrato assinado pelo cliente (wifeed)',
    )


def sincronizar_atendimento_os_aberta(oportunidade, user=None):
    """wf_cliente → wf_agendado quando atendimento + O.S. já foram abertos."""
    if oportunidade.tipo != 'wifeed' or oportunidade.estagio.slug != 'wf_cliente':
        return False
    from integracoes.models import AgendamentoInstalacaoIA
    if not AgendamentoInstalacaoIA.objects.filter(
        lead=oportunidade.lead, status='agendado',
    ).exists():
        return False
    return mover_para_slug(
        oportunidade, 'wf_agendado', user,
        'Atendimento + O.S. abertos (sincronização automática)',
    )


def sincronizar_servico_habilitado(oportunidade, user=None):
    """wf_agendado → wf_concluido quando o serviço está habilitado no HubSoft."""
    if oportunidade.tipo != 'wifeed' or oportunidade.estagio.slug != 'wf_agendado':
        return False
    lead = oportunidade.lead
    if not lead or not lead_tem_servico_habilitado(lead):
        return False
    return mover_para_slug(
        oportunidade, 'wf_concluido', user,
        'Serviço habilitado no HubSoft (wifeed)',
    )


def sincronizar_oportunidade_wifeed(oportunidade, user=None):
    """Aplica todas as transições automáticas possíveis para uma oportunidade."""
    if oportunidade.tipo != 'wifeed':
        return False
    if oportunidade.estagio.slug in ('wf_concluido', 'wf_perdido'):
        return False
    movido = False
    for fn in (sincronizar_contrato_assinado, sincronizar_atendimento_os_aberta,
               sincronizar_servico_habilitado):
        if fn(oportunidade, user):
            movido = True
            oportunidade.refresh_from_db(fields=['estagio', 'estagio_id', 'data_entrada_estagio'])
    return movido


def sincronizar_wifeed_do_lead(lead_id, user=None):
    from crm.models import OportunidadeVenda
    op = OportunidadeVenda.objects.filter(
        lead_id=lead_id, tipo='wifeed', ativo=True,
    ).select_related('lead', 'estagio').first()
    if not op:
        return False
    return sincronizar_oportunidade_wifeed(op, user)


def sincronizar_wifeed_pendentes(user=None):
    """Varre oportunidades wifeed abertas e reconcilia com HubSoft/agendamento."""
    from crm.models import OportunidadeVenda
    qs = OportunidadeVenda.objects.filter(
        ativo=True, tipo='wifeed',
    ).exclude(
        estagio__slug__in=['wf_concluido', 'wf_perdido'],
    ).select_related('lead', 'estagio')
    for op in qs:
        try:
            sincronizar_oportunidade_wifeed(op, user)
        except Exception as e:  # noqa: BLE001
            logger.warning('Sync wifeed op=%s: %s', op.pk, e)
