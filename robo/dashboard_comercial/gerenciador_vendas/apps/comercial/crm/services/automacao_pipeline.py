"""
Motor de Automações do Pipeline.

Avalia regras configuradas em `RegraPipelineEstagio` contra o estado atual de
uma oportunidade e move entre estágios quando uma regra bate.

Lógica:
- Condições dentro de uma regra: AND (todas devem bater)
- Regras dentro de um estágio: OR (qualquer uma basta)
- Estágios avaliados por `ordem` DESC (mais avançado primeiro)
- Estágios finais (is_final_ganho / is_final_perdido) não são reavaliados
- Multi-tenant: engine sempre resolve pela tenant da oportunidade
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def processar_oportunidade(oportunidade):
    """
    Ponto de entrada chamado pelos signals.
    Avalia regras e move a oportunidade se alguma bater.
    """
    if oportunidade is None:
        return

    # Flag pra evitar loop de signals
    if getattr(oportunidade, '_skip_rules_evaluation', False):
        return

    estagio = oportunidade.estagio
    if estagio is None:
        return

    # Não reavaliar oportunidades em estágio final
    if estagio.is_final_ganho or estagio.is_final_perdido:
        return

    resultado = _avaliar_regras(oportunidade)
    if resultado is None:
        return

    estagio_destino, regra, _condicoes = resultado

    if oportunidade.estagio_id == estagio_destino.pk:
        return

    _mover_por_regra(oportunidade, estagio_destino, regra)


def processar_lead(lead_id):
    """Wrapper pra chamar a partir de signal que só tem lead_id."""
    from apps.comercial.crm.models import OportunidadeVenda

    try:
        oportunidade = (
            OportunidadeVenda.all_tenants
            .select_related('estagio', 'lead')
            .get(lead_id=lead_id)
        )
    except OportunidadeVenda.DoesNotExist:
        return

    processar_oportunidade(oportunidade)


# ============================================================================
# AVALIAÇÃO
# ============================================================================

def _avaliar_regras(oportunidade):
    """
    Avalia todas as regras ativas do tenant da oportunidade contra o estado atual.
    Retorna (estagio_destino, regra, condicoes) ou None.
    """
    from apps.comercial.crm.models import PipelineEstagio

    tenant = oportunidade.tenant
    if tenant is None:
        return None

    contexto = _construir_contexto(oportunidade)

    # Estágios com regras ativas, do mais avançado pro menos (ordem DESC).
    # Garante que um lead que já atende ao estágio final não seja pego por regra
    # genérica de estágio anterior.
    estagios_com_regras = (
        PipelineEstagio.all_tenants
        .filter(tenant=tenant, ativo=True, regras__ativo=True)
        .distinct()
        .order_by('-ordem')
        .prefetch_related('regras')
    )

    for estagio in estagios_com_regras:
        regras = estagio.regras.filter(ativo=True).order_by('prioridade')
        for regra in regras:
            if _regra_bate(regra, contexto):
                return (estagio, regra, regra.condicoes)

    return None


def _construir_contexto(oportunidade):
    """Pré-carrega dados usados pelas condições, minimizando queries."""
    from apps.comercial.leads.models import HistoricoContato, ImagemLeadProspecto

    lead = oportunidade.lead
    lead_id = lead.pk if lead else None
    tenant = oportunidade.tenant

    historico_statuses = set()
    tem_conversao_venda = False
    imagens_statuses = []

    if lead_id:
        historico_statuses = set(
            HistoricoContato.all_tenants
            .filter(tenant=tenant, lead_id=lead_id)
            .values_list('status', flat=True)
        )
        tem_conversao_venda = HistoricoContato.all_tenants.filter(
            tenant=tenant, lead_id=lead_id, converteu_venda=True,
        ).exists()
        imagens_statuses = list(
            ImagemLeadProspecto.all_tenants
            .filter(tenant=tenant, lead_id=lead_id)
            .values_list('status_validacao', flat=True)
        )

    servico_statuses = _coletar_status_servicos(lead_id, tenant)

    tags = set(oportunidade.tags.values_list('nome', flat=True))

    return {
        'lead': lead,
        'oportunidade': oportunidade,
        'historico_statuses': historico_statuses,
        'tem_conversao_venda': tem_conversao_venda,
        'imagens_statuses': imagens_statuses,
        'servico_statuses': servico_statuses,
        'tags': tags,
    }


def _coletar_status_servicos(lead_id, tenant):
    """Busca status dos serviços HubSoft do lead, se existirem."""
    if not lead_id:
        return set()
    try:
        from apps.integracoes.models import ServicoClienteHubsoft
    except Exception:
        return set()

    try:
        return set(
            ServicoClienteHubsoft.all_tenants
            .filter(tenant=tenant, cliente__lead_id=lead_id)
            .values_list('status_prefixo', flat=True)
        )
    except Exception:
        return set()


def _regra_bate(regra, contexto):
    """Retorna True se TODAS as condições da regra forem satisfeitas."""
    condicoes = regra.condicoes or []
    if not condicoes:
        return False
    return all(_condicao_bate(c, contexto) for c in condicoes)


def _condicao_bate(condicao, contexto):
    """Avalia uma condição individual contra o contexto pré-carregado."""
    tipo = condicao.get('tipo', '')
    operador = condicao.get('operador', 'igual')
    valor = condicao.get('valor')
    campo = condicao.get('campo', '')

    if tipo == 'historico_status':
        return _comparar_conjunto(contexto['historico_statuses'], operador, valor)

    if tipo == 'lead_status_api':
        lead = contexto['lead']
        status_atual = getattr(lead, 'status_api', '') if lead else ''
        return _comparar_valor(status_atual or '', operador, valor)

    if tipo == 'lead_campo':
        lead = contexto['lead']
        valor_campo = getattr(lead, campo, None) if lead else None
        if isinstance(valor_campo, bool) or isinstance(valor, bool):
            return _comparar_bool(valor_campo, operador, valor)
        return _comparar_valor(valor_campo, operador, valor)

    if tipo == 'servico_status':
        return _comparar_conjunto(contexto['servico_statuses'], operador, valor)

    if tipo == 'tag':
        return _comparar_conjunto(contexto['tags'], operador, valor)

    if tipo == 'converteu_venda':
        tem = contexto['tem_conversao_venda']
        if operador in ('igual', 'existe'):
            return tem == bool(valor)
        if operador in ('diferente', 'nao_existe'):
            return tem != bool(valor)

    if tipo == 'imagem_status':
        imagens = contexto['imagens_statuses']
        if operador == 'igual':
            return valor in imagens
        if operador == 'diferente':
            return valor not in imagens
        if operador == 'todas_iguais':
            return len(imagens) > 0 and all(s == valor for s in imagens)
        if operador == 'nenhuma_com':
            return valor not in imagens
        if operador == 'existe':
            return len(imagens) > 0
        if operador == 'nao_existe':
            return len(imagens) == 0

    logger.warning("[Automacao Pipeline] Tipo de condicao desconhecido: %s", tipo)
    return False


# ============================================================================
# COMPARADORES
# ============================================================================

def _comparar_conjunto(conjunto, operador, valor):
    if operador == 'igual':
        return valor in conjunto
    if operador == 'diferente':
        return valor not in conjunto
    if operador == 'existe':
        return len(conjunto) > 0
    if operador == 'nao_existe':
        return len(conjunto) == 0
    return False


def _comparar_valor(valor_atual, operador, valor_esperado):
    if operador == 'igual':
        return str(valor_atual).strip() == str(valor_esperado).strip()
    if operador == 'diferente':
        return str(valor_atual).strip() != str(valor_esperado).strip()
    if operador == 'existe':
        return bool(valor_atual)
    if operador == 'nao_existe':
        return not bool(valor_atual)
    return False


def _comparar_bool(valor_campo, operador, valor_esperado):
    campo_bool = bool(valor_campo)
    esperado_bool = bool(valor_esperado)
    if operador in ('igual', 'existe'):
        return campo_bool == esperado_bool
    if operador in ('diferente', 'nao_existe'):
        return campo_bool != esperado_bool
    return False


# ============================================================================
# MOVIMENTAÇÃO
# ============================================================================

def _mover_por_regra(oportunidade, estagio_destino, regra):
    """
    Move a oportunidade pro estágio destino, registra histórico, atualiza métricas
    da regra e loga auditoria.
    """
    from apps.comercial.crm.models import HistoricoPipelineEstagio

    agora = timezone.now()
    horas = (agora - oportunidade.data_entrada_estagio).total_seconds() / 3600

    estagio_anterior = oportunidade.estagio
    regra_nome = regra.nome

    HistoricoPipelineEstagio.objects.create(
        oportunidade=oportunidade,
        estagio_anterior=estagio_anterior,
        estagio_novo=estagio_destino,
        motivo=f'Regra automática: {regra_nome}',
        tempo_no_estagio_horas=round(horas, 2),
    )

    campos_update = ['estagio', 'data_entrada_estagio', 'probabilidade', 'data_atualizacao']

    oportunidade.estagio = estagio_destino
    oportunidade.data_entrada_estagio = agora
    oportunidade.probabilidade = estagio_destino.probabilidade_padrao

    if estagio_destino.is_final_ganho and not oportunidade.data_fechamento_real:
        oportunidade.data_fechamento_real = agora
        campos_update.append('data_fechamento_real')

    # Flag pra evitar loop infinito nos signals
    oportunidade._skip_rules_evaluation = True
    oportunidade.save(update_fields=campos_update)

    # Métricas da regra
    try:
        regra.total_disparos = (regra.total_disparos or 0) + 1
        regra.ultima_execucao = agora
        regra.save(update_fields=['total_disparos', 'ultima_execucao'])
    except Exception as exc:
        logger.warning("[Automacao Pipeline] Falha ao atualizar metricas da regra %s: %s", regra.pk, exc)

    logger.info(
        "[Automacao Pipeline] Oportunidade %s movida '%s' -> '%s' (regra: %s)",
        oportunidade.pk,
        estagio_anterior.nome if estagio_anterior else '—',
        estagio_destino.nome,
        regra_nome,
    )

    try:
        from apps.sistema.utils import registrar_acao
        registrar_acao(
            'crm', 'mover_regra', 'oportunidade', oportunidade.pk,
            f"Movida para '{estagio_destino.nome}' pela regra '{regra_nome}'",
        )
    except Exception:
        pass


def processar_seguro(lead_id=None, oportunidade=None):
    """Wrapper que isola falhas do engine pra não derrubar signals."""
    try:
        if oportunidade is not None:
            processar_oportunidade(oportunidade)
        elif lead_id is not None:
            processar_lead(lead_id)
    except Exception as exc:
        logger.error("[Automacao Pipeline] Falha ao avaliar regras: %s", exc)
