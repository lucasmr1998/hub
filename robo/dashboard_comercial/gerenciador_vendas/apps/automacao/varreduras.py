"""Registry de varreduras — o que o gatilho `agenda` busca a cada rodada.

Espelha `opcoes.py`: cada varredura é uma função `fn(tenant, config) -> list[dict]`.
Cada dict do resultado é um "achado" e vira UMA execução do fluxo — traz pelo menos
uma entidade reconhecida por `gatilhos._contexto_do_evento` (`oportunidade`/`lead`;
mesmo contrato do contexto de evento), o resto são escalares que entram em `var.*`.

Tudo BLINDADO: uma varredura que falha devolve lista vazia/parcial + loga, nunca
levanta pra fora. É a primeira linha de defesa porque cada função fala com banco
ou API externa (o dispatcher em `gatilhos.py` também embrulha por cima).

Adicionar uma varredura = uma função + entrada em `VARREDURAS` (+ label em
`_LABELS`, usado por `opcoes_varreduras`).
"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


def _oportunidades_perdidas(tenant, config):
    """Oportunidades perdidas há pelo menos `janela_dias_min` dias (default 30).

    Filtros opcionais na `config`:
    - `motivo_categoria`: categoria legada do motivo de perda (`motivo_perda_categoria`).
    - `motivo_ref_id`: id do `MotivoPerda` (`motivo_perda_ref_id`).
    - `pipeline`: slug do pipeline (`OportunidadeVenda.pipeline`).
    - `sem_marcador`: só entram oportunidades SEM essa chave em `dados_custom`
      (freio manual: o fluxo marca a op depois de processar, pra não repetir).
    """
    from apps.comercial.crm.models import OportunidadeVenda

    try:
        janela_dias = int(config.get('janela_dias_min') or 30)
    except (TypeError, ValueError):
        janela_dias = 30
    corte = timezone.now() - timedelta(days=janela_dias)

    qs = OportunidadeVenda.all_tenants.filter(
        tenant=tenant, ativo=True,
        estagio__is_final_perdido=True,
        data_fechamento_real__isnull=False,
        data_fechamento_real__lte=corte,
    )

    motivo_categoria = (config.get('motivo_categoria') or '').strip()
    if motivo_categoria:
        qs = qs.filter(motivo_perda_categoria=motivo_categoria)

    motivo_ref_id = config.get('motivo_ref_id')
    if motivo_ref_id not in (None, ''):
        try:
            qs = qs.filter(motivo_perda_ref_id=int(motivo_ref_id))
        except (TypeError, ValueError):
            pass

    pipeline_slug = (config.get('pipeline') or '').strip()
    if pipeline_slug:
        qs = qs.filter(pipeline__slug=pipeline_slug)

    sem_marcador = (config.get('sem_marcador') or '').strip()
    if sem_marcador:
        qs = qs.exclude(dados_custom__has_key=sem_marcador)

    qs = qs.select_related('lead', 'pipeline').order_by('data_fechamento_real')[:1000]

    agora = timezone.now()
    out = []
    for op in qs:
        out.append({
            'oportunidade': op,
            'lead': op.lead,
            'dias_perdida': (agora - op.data_fechamento_real).days,
        })
    return out


def _atendimentos_matrix_finalizados(tenant, config):
    """Atendimentos Matrix finalizados nos últimos `janela_dias` (default 2) ainda
    sem análise.

    Casa cada linha da listagem analítica (`/rest/v1/relAtAnalitico`) pela
    oportunidade que guardou o id do atendimento em
    `dados_custom['id_atendimento_matrix']`, pulando quem já tem o `marcador`
    (default `analise_atendimento_matrix`) em `dados_custom` — evita repetir o
    mesmo atendimento em rodadas seguintes.

    Nomes de campo da linha seguem `extrair_historico_matrix` (mesmo endpoint):
    `id_atendimento`, `status`, `agente` (não há `id_agente` na listagem
    analítica — isso só existe no detalhe de `consultar_atendimento`).
    """
    from .services.matrix import matrix_do_tenant
    from apps.comercial.crm.models import OportunidadeVenda

    cliente = matrix_do_tenant(tenant)
    if cliente is None:
        return []

    try:
        janela_dias = int(config.get('janela_dias') or 2)
    except (TypeError, ValueError):
        janela_dias = 2
    marcador = (config.get('marcador') or '').strip() or 'analise_atendimento_matrix'
    servico_nome = (config.get('servico_nome') or '').strip() or None

    hoje = timezone.now().date()
    data_inicial = (hoje - timedelta(days=janela_dias)).strftime('%Y-%m-%d')
    data_final = hoje.strftime('%Y-%m-%d')

    linhas = []
    try:
        page = 1
        while page <= 20:  # teto de páginas por rodada — corta cedo se a Matrix cair
            resp = cliente.listar_atendimentos_analitico(
                data_inicial=data_inicial, data_final=data_final,
                servico_nome=servico_nome, page=page, limit=300,
            )
            if isinstance(resp, dict):
                rows = resp.get('rows') or []
                total = int(resp.get('records') or 0)
            elif isinstance(resp, list):
                rows = resp
                total = len(rows)
            else:
                rows = []
                total = 0
            linhas.extend(rows)
            if not rows or len(linhas) >= total:
                break
            page += 1
    except Exception:
        logger.exception(
            'varreduras: falha ao listar atendimentos Matrix (tenant=%s)', tenant.pk,
        )
        # segue com o que já foi acumulado (lista parcial, nunca levanta)

    out = []
    for linha in linhas:
        try:
            if not isinstance(linha, dict):
                continue
            status = str(linha.get('status') or '')
            if 'finalizado' not in status.lower():
                continue
            if not str(linha.get('agente') or '').strip():
                continue
            codigo = linha.get('id_atendimento')
            if not codigo:
                continue
            op = (
                OportunidadeVenda.all_tenants
                .filter(tenant=tenant, dados_custom__id_atendimento_matrix=str(codigo))
                .exclude(dados_custom__has_key=marcador)
                .select_related('lead')
                .first()
            )
            if op is None:
                continue
            out.append({'oportunidade': op, 'lead': op.lead, 'id_atendimento_matrix': str(codigo)})
        except Exception:
            logger.exception(
                'varreduras: falha ao processar linha de atendimento Matrix (tenant=%s)', tenant.pk,
            )
            continue
    return out


VARREDURAS = {
    'oportunidades_perdidas': _oportunidades_perdidas,
    'atendimentos_matrix_finalizados': _atendimentos_matrix_finalizados,
}

_LABELS = {
    'oportunidades_perdidas': 'Oportunidades perdidas (win/loss)',
    'atendimentos_matrix_finalizados': 'Atendimentos Matrix finalizados (sem análise)',
}


def opcoes_varreduras(tenant=None):
    """Opções pro dropdown do campo `varredura` do nó `agenda`.

    `tenant` não filtra (o catálogo de varreduras é global, não por tenant) —
    o parâmetro só existe pra seguir a assinatura padrão das fontes de opções
    (`opcoes.py:opcoes_de`, que sempre chama `fn(tenant)`).
    """
    return [{'value': k, 'label': _LABELS.get(k, k)} for k in VARREDURAS]
