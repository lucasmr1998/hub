"""Shadow (espião) da migração do funil — Fase 2, Passo 2.

Roda os Fluxos migrados (os que têm `origem_regra`) em modo **log-only**: avalia as
condições contra a oportunidade e registra "quais ações DISPARARIAM", SEM executar
nada. Serve pra provar paridade com o motor antigo antes do cutover (Passo 3).

Gatilho (v2 — eventos finos): o `hub.disparar_evento` chama `avaliar_evento_shadow`
em paralelo ao caminho de produção. Quando um evento fino dispara (emitido em
`signals_dominio` no save real), o shadow avalia SÓ os fluxos que escutam aquele
evento — targeted, sem over-fire. (v1 escutava o pulso do motor antigo e avaliava
todos; substituído.)

Paridade por construção: as condições são avaliadas pelo MESMO registry
(`automacao_condicoes`) que o motor antigo usa (`_condicao_bate`). Guardado pelo flag
`AUTOMACAO_SHADOW_ATIVO` e 100% blindado (nunca quebra o caminho vivo).
"""
import logging

logger = logging.getLogger(__name__)

# Tipos de nó "puros" (sem efeito colateral) que o shadow AVALIA de verdade.
# Qualquer outro tipo é ação → registrado como "faria" e NÃO executado.
_EVENTO = 'evento'
_CONDICAO = 'condicao_comercial'


def _proxima(conexoes, handle, branch):
    """Aresta a seguir: casa pela branch; senão 'default'; senão fim. (espelha o runtime)"""
    branch = branch or 'default'
    for c in conexoes:
        if c.get('de') == handle and c.get('saida') == branch:
            return c.get('para')
    for c in conexoes:
        if c.get('de') == handle and c.get('saida', 'default') == 'default':
            return c.get('para')
    return None


def avaliar_fluxo_shadow(grafo, avaliar_cond, max_passos=200):
    """Anda o grafo do Fluxo migrado sem efeito colateral.

    `avaliar_cond(config_do_no) -> bool` avalia um nó de condição (injetado pra
    testar). Nós que não são gatilho/condição são tratados como AÇÃO: registrados
    em `acoes` e assume-se sucesso (segue a saída 'sucesso'/'default').

    Devolve `(disparou: bool, acoes: list[dict])`. disparou = alcançou ≥1 ação
    (todas as condições passaram)."""
    grafo = grafo or {}
    nodes = grafo.get('nodes') or {}
    conexoes = grafo.get('conexoes') or []
    handle = grafo.get('inicio')
    acoes = []
    visitados = set()

    for _ in range(max_passos):
        if not handle or handle in visitados:
            break
        visitados.add(handle)
        node = nodes.get(handle)
        if not node:
            break
        tipo = node.get('tipo')
        cfg = node.get('config') or {}

        if tipo == _EVENTO:
            branch = 'default'
        elif tipo == _CONDICAO:
            branch = 'true' if avaliar_cond(cfg) else 'false'
        else:
            # ação: registra o que FARIA, não executa; assume sucesso
            acoes.append({
                'tipo': (cfg.get('tipo_acao') or tipo or '').strip() or tipo,
                'no': tipo,
                'config': cfg.get('config') if isinstance(cfg.get('config'), dict) else cfg,
            })
            branch = 'sucesso'

        handle = _proxima(conexoes, handle, branch)

    return (len(acoes) > 0), acoes


def _dados_condicao(oportunidade):
    """Pré-carrega o contexto das condições UMA vez (reuso entre fluxos), pelo MESMO
    registry do motor antigo. Espelha `automacao_pipeline._construir_contexto` sem
    importar do motor antigo."""
    from apps.comercial.crm.services import automacao_condicoes
    dados = {'lead': oportunidade.lead, 'oportunidade': oportunidade}
    for tipo in automacao_condicoes.REGISTRY.values():
        try:
            tipo.coletar_contexto(oportunidade, dados)
        except Exception as exc:  # noqa: BLE001
            logger.debug('shadow: coletar_contexto %s falhou: %s', getattr(tipo, 'slug', '?'), exc)
    return dados


def _fazer_avaliador(dados):
    """Closure que avalia um nó condicao_comercial contra `dados` — mesma lógica do
    `_condicao_bate` do motor antigo (mesmo registry)."""
    from apps.comercial.crm.services import automacao_condicoes

    def avaliar(cfg):
        tipo = automacao_condicoes.tipo_por_slug((cfg.get('tipo_condicao') or '').strip())
        if tipo is None:
            return False
        try:
            return bool(tipo.avaliar((cfg.get('operador') or 'igual').strip(),
                                     cfg.get('valor'), (cfg.get('campo') or '').strip(), dados))
        except Exception:  # noqa: BLE001
            return False
    return avaliar


def _op_do_contexto(contexto):
    """Resolve a oportunidade do contexto do evento (direto, ou pela do lead)."""
    op = (contexto or {}).get('oportunidade')
    if op is not None:
        return op
    lead = (contexto or {}).get('lead')
    if lead is None or not getattr(lead, 'pk', None):
        return None
    try:
        from apps.comercial.crm.models import OportunidadeVenda
        return (OportunidadeVenda.all_tenants.filter(lead=lead)
                .select_related('estagio', 'pipeline', 'lead')
                .order_by('-ativo', '-data_criacao').first())
    except Exception:  # noqa: BLE001
        return None


def avaliar_evento_shadow(evento, contexto, tenant):
    """Shadow v2: quando um EVENTO fino dispara, avalia (log-only) os fluxos migrados
    que ESCUTAM esse evento e registra o que DISPARARIA. Chamado pelo hub em paralelo
    ao caminho de produção (que segue gated por AUTOMACAO_WIRING_ATIVO). Blindado.

    Diferente da v1 (avaliava TODOS os fluxos a cada pulso do motor antigo): aqui só
    os fluxos cujo `gatilho_evento` == evento — targeted, sem over-fire."""
    from django.conf import settings
    if not getattr(settings, 'AUTOMACAO_SHADOW_ATIVO', False):
        return
    if not evento or tenant is None:
        return
    from .models import Fluxo
    fluxos = list(Fluxo.all_tenants.filter(
        tenant=tenant, origem_regra__isnull=False, gatilho_evento=evento))
    if not fluxos:
        return

    op = _op_do_contexto(contexto)
    if op is None:
        return
    dados = _dados_condicao(op)
    avaliar = _fazer_avaliador(dados)

    would_fire = []
    for f in fluxos:
        try:
            disparou, acoes = avaliar_fluxo_shadow(f.grafo or {}, avaliar)
        except Exception as exc:  # noqa: BLE001
            logger.debug('shadow: fluxo %s falhou: %s', f.pk, exc)
            continue
        if disparou:
            would_fire.append({
                'fluxo_id': f.pk,
                'origem_regra': f.origem_regra,
                'acoes': [a['tipo'] for a in acoes],
            })

    if not would_fire:
        return  # nada dispararia → nada a registrar (baixo volume)

    try:
        from apps.sistema.models import LogSistema
        LogSistema.all_tenants.create(
            tenant=tenant,
            categoria='crm', acao='shadow_fluxo',
            entidade='OportunidadeVenda', entidade_id=op.pk,
            mensagem=f'Shadow[{evento}]: {len(would_fire)} fluxo(s) dispararia(m) na op {op.pk}',
            dados_extras={'shadow': True, 'evento': evento, 'would_fire': would_fire},
        )
    except Exception:  # noqa: BLE001
        logger.exception('shadow: falha ao registrar decisão')
