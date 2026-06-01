"""Geracao de embeddings via OpenAI text-embedding-3-small (1536 dim).

Resolve a credencial OpenAI do tenant (IntegracaoAPI tipo=openai ativa).
Se o tenant nao tem credencial propria, faz fallback pra Aurora HQ (tenant
'aurora-hq') que e a "casa". Aurora absorve custo de embedding pros tenants
novos ate eles configurarem credencial propria.

Custo: ~$0.0001 por texto (text-embedding-3-small). Trivial em qualquer volume
realista pro Hubtrix.

Uso:
    from apps.sistema.services.embeddings import gerar_embedding
    vetor = gerar_embedding('quanto custa o plano?', tenant=tenant_obj)
    # vetor: list[float] com 1536 elementos
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = 'text-embedding-3-small'
EMBEDDING_DIM = 1536


def _resolver_api_key(tenant) -> Optional[str]:
    """Pega api_key da IntegracaoAPI tipo=openai ativa do tenant.
    Fallback: Aurora HQ se o tenant nao tem credencial propria."""
    from apps.integracoes.models import IntegracaoAPI

    if tenant:
        ig = IntegracaoAPI.all_tenants.filter(
            tenant=tenant, tipo='openai', ativa=True,
        ).exclude(api_key='').exclude(api_key__isnull=True).first()
        if ig and ig.api_key:
            return ig.api_key

    # Fallback: Aurora HQ
    from apps.sistema.models import Tenant
    aurora = Tenant.objects.filter(slug='aurora-hq').first()
    if not aurora:
        return None
    ig = IntegracaoAPI.all_tenants.filter(
        tenant=aurora, tipo='openai', ativa=True,
    ).exclude(api_key='').exclude(api_key__isnull=True).first()
    if ig and ig.api_key:
        return ig.api_key
    return None


def gerar_embedding(texto: str, *, tenant=None) -> Optional[list]:
    """Gera embedding 1536-dim via OpenAI text-embedding-3-small.

    Returns:
        list[float] de 1536 elementos, ou None se nao conseguir gerar
        (sem credencial ou erro de API).
    """
    if not texto or not texto.strip():
        return None
    texto = texto.strip()[:8000]  # OpenAI limita ~8192 tokens; clamp pra prosa

    api_key = _resolver_api_key(tenant)
    if not api_key:
        logger.warning(
            'gerar_embedding: nenhuma credencial OpenAI encontrada '
            '(tenant=%s, fallback Aurora HQ tbm sem)',
            getattr(tenant, 'slug', None),
        )
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, timeout=30)
        resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texto)
        emb = resp.data[0].embedding
        if len(emb) != EMBEDDING_DIM:
            logger.error(
                'gerar_embedding: dimensao inesperada %d (esperado %d)',
                len(emb), EMBEDDING_DIM,
            )
            return None
        return emb
    except Exception as e:
        logger.exception('gerar_embedding falhou: %s', e)
        return None
