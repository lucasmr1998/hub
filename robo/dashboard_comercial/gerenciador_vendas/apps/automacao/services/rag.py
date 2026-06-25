"""
RAG do agente — busca na base de conhecimento (módulo Suporte), tenant-safe.

Envolve `apps.suporte.services.buscar_artigos` (pgvector, filtra por tenant + publicado)
e formata os artigos pro LLM. Não acopla a engine ao motor de atendimento. Degrada
gracioso: sem credencial/embedding ou base vazia → texto neutro (nunca levanta).
"""
import logging

logger = logging.getLogger(__name__)

_MAX_TRECHO = 600  # chars por artigo no contexto do LLM


def buscar_conhecimento(tenant, pergunta, categorias=None, k=5, lead=None, registrar_gap=True):
    """Busca na base e devolve um texto pronto pro LLM (título + trecho dos top-K).

    `categorias`: lista de ids de `CategoriaConhecimento` (None/[] = base inteira do
    tenant). Sempre tenant-safe (o filtro de tenant é do `buscar_artigos`).

    `registrar_gap`: quando a busca roda mas não acha nada, registra a pergunta em
    `PerguntaSemResposta` (fecha o ciclo de melhoria da base). Só registra em "achou 0",
    não em erro de infra (pgvector/credencial ausente cai no except e NÃO registra).
    """
    try:
        from apps.suporte.services import buscar_artigos
        resultados = buscar_artigos(tenant, pergunta, k=k, categorias=categorias)
    except Exception as e:  # noqa: BLE001 — pgvector/credencial ausente não derruba o agente
        logger.warning('rag.buscar_conhecimento falhou: %s', e)
        return 'Não foi possível consultar a base de conhecimento agora.'

    if not resultados:
        if registrar_gap and pergunta and len(pergunta.strip()) >= 3:
            try:
                from apps.suporte.services import registrar_pergunta_sem_resposta
                registrar_pergunta_sem_resposta(tenant=tenant, pergunta=pergunta, lead=lead)
            except Exception:  # noqa: BLE001 — registrar gap nunca pode quebrar o agente
                logger.warning('rag: falha ao registrar pergunta sem resposta')
        return 'Nada encontrado na base de conhecimento para essa pergunta.'

    partes = []
    for r in resultados:
        a = r['artigo']
        trecho = (getattr(a, 'resumo', '') or getattr(a, 'conteudo', '') or '').strip()
        if len(trecho) > _MAX_TRECHO:
            trecho = trecho[:_MAX_TRECHO] + '…'
        partes.append(f'## {a.titulo}\n{trecho}')
    return '\n\n'.join(partes)
