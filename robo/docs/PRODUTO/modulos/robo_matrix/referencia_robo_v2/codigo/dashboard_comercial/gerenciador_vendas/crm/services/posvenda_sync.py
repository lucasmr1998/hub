"""Sincroniza os fluxos PÓS-VENDA (NewService / UpgradePlano) com o CRM.

Cada NewService vira uma OportunidadeVenda(tipo='novo_servico') e cada
UpgradePlano uma OportunidadeVenda(tipo='upgrade'), que percorrem seus
pipelines conforme o progresso real (coleta → webdriver HubSoft → sync Matrix).

Usado por:
  - signals (crm/signals.py) — transições disparadas por saves via ORM
  - management command `crm_reconciliar_posvenda` — pega as transições que o
    webdriver/polling faz via SQL cru (que NÃO dispara signals do Django).
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def _servico_do_ns_habilitado(ns) -> bool:
    """True se o serviço criado por este NewService já está 'servico_habilitado'
    no HubSoft (espelhado em ServicoClienteHubsoft)."""
    cs_id = getattr(ns, 'id_cliente_servico_origem', None)
    if not cs_id:
        return False
    try:
        from integracoes.models import ServicoClienteHubsoft
        s = ServicoClienteHubsoft.objects.filter(id_cliente_servico=cs_id).first()
        return bool(s and s.status_prefixo == 'servico_habilitado')
    except Exception:
        return False


def _slug_new_service(ns) -> str | None:
    """Estágio-alvo (slug) de um NewService conforme seu progresso."""
    status = (ns.status or '').lower()
    hub = (ns.hubsoft_processado_status or '').lower()
    matrix = (ns.matrix_sync_status or '').lower()

    if status == 'cancelado':
        return 'ns_falha'
    if hub == 'falha':
        return 'ns_falha'
    if status != 'finalizado':
        return 'ns_coletando'
    # finalizado:
    if matrix == 'sincronizado':
        # serviço já habilitado no HubSoft → Serviço Ativo (final ganho)
        if _servico_do_ns_habilitado(ns):
            return 'ns_ativo'
        return 'ns_concluido'      # criado + OS aberta, aguardando instalação
    if hub == 'sucesso':
        return 'ns_sync_matrix'   # criou no HubSoft, falta abrir atendimento/OS
    return 'ns_proc_hubsoft'       # finalizado, aguardando criação no HubSoft


def _slug_upgrade(up) -> str | None:
    """Estágio-alvo (slug) de um UpgradePlano conforme seu progresso."""
    status = (up.status or '').lower()
    hub = (up.hubsoft_processado_status or '').lower()

    if status == 'cancelado':
        return 'up_falha'
    if hub == 'falha':
        return 'up_falha'
    if hub in ('sucesso', 'dry_run'):
        return 'up_concluido'
    if status == 'finalizado':
        return 'up_proc_hubsoft'   # confirmado, aguardando webdriver migrar
    return 'up_andamento'


def _mover_para_estagio(opp, estagio, motivo=''):
    """Move a oportunidade pro estágio + registra histórico. Idempotente."""
    from crm.models import HistoricoPipelineEstagio
    if opp.estagio_id == estagio.id:
        return False
    horas = (timezone.now() - opp.data_entrada_estagio).total_seconds() / 3600
    HistoricoPipelineEstagio.objects.create(
        oportunidade=opp, estagio_anterior_id=opp.estagio_id, estagio_novo=estagio,
        motivo=motivo or 'Sincronização pós-venda', tempo_no_estagio_horas=round(horas, 2),
    )
    opp.estagio = estagio
    opp.data_entrada_estagio = timezone.now()
    opp.probabilidade = estagio.probabilidade_padrao
    campos = ['estagio', 'data_entrada_estagio', 'probabilidade']
    if estagio.is_final_ganho and not opp.data_fechamento_real:
        opp.data_fechamento_real = timezone.now()
        campos.append('data_fechamento_real')
    opp.save(update_fields=campos)
    return True


# Tags por etapa do pós-venda (cumulativas — ganha conforme avança).
TAGS_POSVENDA = {
    'ns_coletando':   [('Novo Serviço', '#0ea5e9')],
    'ns_proc_hubsoft': [('Novo Serviço', '#0ea5e9'), ('Criando no HubSoft', '#6366f1')],
    'ns_sync_matrix': [('Novo Serviço', '#0ea5e9'), ('Serviço Criado', '#14b8a6')],
    'ns_concluido':   [('Novo Serviço', '#0ea5e9'), ('Serviço Criado', '#14b8a6'),
                       ('Instalação Agendada', '#ff6b00')],
    'ns_ativo':       [('Novo Serviço', '#0ea5e9'), ('Serviço Criado', '#14b8a6'),
                       ('Instalação Agendada', '#ff6b00'), ('Serviço Ativo', '#16a34a')],
    'ns_falha':       [('Novo Serviço', '#0ea5e9'), ('Falha', '#ef4444')],
    'up_andamento':   [('Upgrade', '#6366f1')],
    'up_proc_hubsoft': [('Upgrade', '#6366f1'), ('Migrando Plano', '#0022fa')],
    'up_concluido':   [('Upgrade', '#6366f1'), ('Upgrade Aplicado', '#10b981')],
    'up_falha':       [('Upgrade', '#6366f1'), ('Falha', '#ef4444')],
}


# Tags do pipeline de INDICAÇÃO (operado por pessoas). Cumulativas por etapa,
# com a tag de canal "Indicação" sempre presente.
TAGS_INDICACAO = {
    'ind_recebida':  [('Indicação', '#8b5cf6'), ('Lead Novo', '#0022fa')],
    'ind_dados':     [('Indicação', '#8b5cf6'), ('Completando Dados', '#6366f1')],
    'ind_apto':      [('Indicação', '#8b5cf6'), ('Aguardando Assinatura', '#f59e0b')],
    'ind_cliente':   [('Indicação', '#8b5cf6'), ('Aguardando Abertura de O.S.', '#0d6efd')],
    'ind_agendado':  [('Indicação', '#8b5cf6'), ('Aguardando Abertura de O.S.', '#0d6efd'),
                      ('Aguardando Instalação', '#fd7e14')],
    'ind_concluido': [('Indicação', '#8b5cf6'), ('Aguardando Abertura de O.S.', '#0d6efd'),
                      ('Aguardando Instalação', '#fd7e14'), ('Concluído', '#16a34a')],
    'ind_perdido':   [('Indicação', '#8b5cf6'), ('Perdido', '#ef4444')],
}


# Tags do pipeline WIFEED (leads do portal WiFi). Cumulativas por etapa,
# com a tag de canal "Wifeed" sempre presente.
TAGS_WIFEED = {
    'wf_recebida':  [('Wifeed', '#06b6d4'), ('Lead Novo', '#0022fa')],
    'wf_dados':     [('Wifeed', '#06b6d4'), ('Completando Dados', '#6366f1')],
    'wf_apto':      [('Wifeed', '#06b6d4'), ('Aguardando Assinatura', '#f59e0b')],
    'wf_cliente':   [('Wifeed', '#06b6d4'), ('Aguardando Abertura de O.S.', '#0d6efd')],
    'wf_agendado':  [('Wifeed', '#06b6d4'), ('Aguardando Abertura de O.S.', '#0d6efd'),
                     ('Aguardando Instalação', '#fd7e14')],
    'wf_concluido': [('Wifeed', '#06b6d4'), ('Aguardando Abertura de O.S.', '#0d6efd'),
                     ('Aguardando Instalação', '#fd7e14'), ('Concluído', '#16a34a')],
    'wf_perdido':   [('Wifeed', '#06b6d4'), ('Perdido', '#ef4444')],
}


def aplicar_tags_etapa(opp, slug):
    """Aplica as tags da etapa (pós-venda OU indicação OU wifeed) à oportunidade."""
    from crm.models import TagCRM
    for nome, cor in (TAGS_POSVENDA.get(slug) or TAGS_INDICACAO.get(slug)
                      or TAGS_WIFEED.get(slug) or []):
        tag, _ = TagCRM.objects.get_or_create(nome=nome, defaults={'cor_hex': cor})
        opp.tags.add(tag)


def _aplicar_tags(opp, slug):
    """Adiciona à oportunidade as tags da etapa atual do pós-venda."""
    aplicar_tags_etapa(opp, slug)


def _sincronizar(lead_id, tipo, link_field, link_obj, slug, titulo):
    """Get-or-create da oportunidade pós-venda + move pro estágio alvo."""
    from crm.models import OportunidadeVenda, PipelineEstagio
    if not lead_id or not slug:
        return None
    estagio = PipelineEstagio.objects.filter(slug=slug).first()
    if not estagio:
        logger.warning('[CRM pós-venda] estágio %r não encontrado', slug)
        return None

    opp = OportunidadeVenda.objects.filter(**{'tipo': tipo, link_field: link_obj}).first()
    if not opp:
        opp = OportunidadeVenda.objects.create(
            lead_id=lead_id, tipo=tipo, estagio=estagio,
            origem_crm='automatico', probabilidade=estagio.probabilidade_padrao,
            titulo=titulo, **{link_field: link_obj},
        )
        logger.info('[CRM pós-venda] oportunidade %s criada (%s) p/ lead %s', opp.pk, tipo, lead_id)
    else:
        _mover_para_estagio(opp, estagio, motivo=f'{tipo}: {titulo}')
    _aplicar_tags(opp, slug)
    return opp


def sincronizar_new_service(ns):
    return _sincronizar(
        lead_id=ns.lead_id, tipo='novo_servico',
        link_field='new_service', link_obj=ns,
        slug=_slug_new_service(ns), titulo=f'Novo Serviço #{ns.pk}',
    )


def sincronizar_upgrade(up):
    return _sincronizar(
        lead_id=up.lead_id, tipo='upgrade',
        link_field='upgrade_plano', link_obj=up,
        slug=_slug_upgrade(up), titulo=f'Upgrade #{up.pk} (cs={up.id_cliente_servico})',
    )
