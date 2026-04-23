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
    """
    Pré-carrega dados usados pelas condições chamando `coletar_contexto` de cada
    tipo registrado. Ordem minimiza queries (cada tipo popula só o que precisa).
    """
    from apps.comercial.crm.services import automacao_condicoes

    contexto = {
        'lead': oportunidade.lead,
        'oportunidade': oportunidade,
    }
    for tipo in automacao_condicoes.REGISTRY.values():
        try:
            tipo.coletar_contexto(oportunidade, contexto)
        except Exception as exc:
            logger.warning("[Automacao Pipeline] Falha ao coletar contexto de %s: %s", tipo.slug, exc)
    return contexto


def _regra_bate(regra, contexto):
    """Retorna True se TODAS as condições da regra forem satisfeitas."""
    condicoes = regra.condicoes or []
    if not condicoes:
        return False
    return all(_condicao_bate(c, contexto) for c in condicoes)


def _condicao_bate(condicao, contexto):
    """Avalia uma condição individual delegando ao tipo registrado."""
    from apps.comercial.crm.services import automacao_condicoes

    tipo_slug = condicao.get('tipo', '')
    operador = condicao.get('operador', 'igual')
    valor = condicao.get('valor')
    campo = condicao.get('campo', '')

    tipo = automacao_condicoes.tipo_por_slug(tipo_slug)
    if tipo is None:
        logger.warning("[Automacao Pipeline] Tipo de condicao desconhecido: %s", tipo_slug)
        return False

    try:
        return tipo.avaliar(operador, valor, campo, contexto)
    except Exception as exc:
        logger.warning("[Automacao Pipeline] Falha ao avaliar %s: %s", tipo_slug, exc)
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
