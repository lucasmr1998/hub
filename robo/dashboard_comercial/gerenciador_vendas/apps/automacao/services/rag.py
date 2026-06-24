"""
RAG do agente — busca na base de conhecimento (módulo Suporte), tenant-safe.

Envolve `apps.suporte.services.buscar_artigos` (pgvector, filtra por tenant + publicado)
e formata os artigos pro LLM. Não acopla a engine ao motor de atendimento. Degrada
gracioso: sem credencial/embedding ou base vazia → texto neutro (nunca levanta).
"""
import logging

logger = logging.getLogger(__name__)

_MAX_TRECHO = 600  # chars por artigo no contexto do LLM


def buscar_conhecimento(tenant, pergunta, categorias=None, k=5):
    """Busca na base e devolve um texto pronto pro LLM (título + trecho dos top-K).

    `categorias`: lista de ids de `CategoriaConhecimento` (None/[] = base inteira do
    tenant). Sempre tenant-safe (o filtro de tenant é do `buscar_artigos`).
    """
    try:
        from apps.suporte.services import buscar_artigos
        resultados = buscar_artigos(tenant, pergunta, k=k, categorias=categorias)
    except Exception as e:  # noqa: BLE001 — pgvector/credencial ausente não derruba o agente
        logger.warning('rag.buscar_conhecimento falhou: %s', e)
        return 'Não foi possível consultar a base de conhecimento agora.'

    if not resultados:
        return 'Nada encontrado na base de conhecimento para essa pergunta.'

    partes = []
    for r in resultados:
        a = r['artigo']
        trecho = (getattr(a, 'resumo', '') or getattr(a, 'conteudo', '') or '').strip()
        if len(trecho) > _MAX_TRECHO:
            trecho = trecho[:_MAX_TRECHO] + '…'
        partes.append(f'## {a.titulo}\n{trecho}')
    return '\n\n'.join(partes)
