"""Servicos do app Suporte — funcoes puras reutilizaveis (views, engine, N8N).

A logica de "registrar pergunta sem resposta" vivia acoplada na engine antiga
do atendimento (apps/comercial/atendimento/engine.py). Aqui ela e extraida
pra uma funcao pura que recebe (tenant, pergunta, lead, conversa) — assim
pode ser chamada pelo endpoint publico /api/public/n8n/conhecimento/* sem
depender do modelo Atendimento.
"""
import logging
import re

logger = logging.getLogger(__name__)

# Stop-words PT usadas pra extrair "termo significativo" da pergunta antes
# de buscar duplicatas. Mantido em sync com engine.py:_STOP_WORDS_PT.
_STOP_WORDS_PT = {
    'a', 'o', 'e', 'de', 'do', 'da', 'dos', 'das', 'em', 'no', 'na', 'nos', 'nas',
    'um', 'uma', 'uns', 'umas', 'para', 'por', 'com', 'sem', 'que', 'se', 'como',
    'mais', 'ou', 'ao', 'aos', 'as', 'os', 'eu', 'ele', 'ela', 'eles', 'elas',
    'meu', 'minha', 'seu', 'sua', 'voce', 'voces', 'isso', 'isto', 'aquele',
    'aquela', 'aqui', 'ali', 'la', 'tem', 'ter', 'ser', 'estar', 'foi', 'era',
}


def _primeiro_termo_significativo(pergunta: str) -> str:
    """Pega o primeiro termo >=3 chars que nao seja stop-word PT.
    Usado pra detectar duplicatas via icontains."""
    palavras = re.findall(r'[a-zA-ZÀ-ÿ]+', (pergunta or '').lower())
    for p in palavras:
        if len(p) >= 3 and p not in _STOP_WORDS_PT:
            return p
    # fallback: primeiros 30 chars da pergunta crua
    return (pergunta or '')[:30]


def registrar_pergunta_sem_resposta(*, tenant, pergunta: str, lead=None, conversa=None):
    """Registra uma PerguntaSemResposta — ou incrementa ocorrencias se ja existe similar.

    Args:
        tenant: instancia Tenant (obrigatorio).
        pergunta: texto livre da duvida (obrigatorio, min 3 chars uteis).
        lead: LeadProspecto opcional pra vincular.
        conversa: Conversa opcional pra vincular.

    Returns:
        (objeto PerguntaSemResposta, criada: bool) ou (None, False) se invalido.
    """
    from apps.suporte.models import PerguntaSemResposta

    if not pergunta or not pergunta.strip() or len(pergunta.strip()) < 3:
        return None, False

    pergunta = pergunta.strip()
    termo = _primeiro_termo_significativo(pergunta)

    # Dedup: se ja existe pendente com mesmo termo significativo, incrementa.
    # all_tenants pra escapar do auto-filter quando chamado fora de request.
    existente = PerguntaSemResposta.all_tenants.filter(
        tenant=tenant, status='pendente', pergunta__icontains=termo,
    ).first()

    if existente:
        existente.ocorrencias = (existente.ocorrencias or 0) + 1
        update_fields = ['ocorrencias']
        # Atualiza lead/conversa se ainda nao tinha
        if lead and not existente.lead_id:
            existente.lead = lead
            update_fields.append('lead')
        if conversa and not existente.conversa_id:
            existente.conversa = conversa
            update_fields.append('conversa')
        existente.save(update_fields=update_fields)
        return existente, False

    nova = PerguntaSemResposta.objects.create(
        tenant=tenant, pergunta=pergunta, lead=lead, conversa=conversa,
    )
    return nova, True


# ============================================================================
# BUSCA DE CONHECIMENTO (RAG via pgvector)
# ============================================================================

def buscar_artigos(tenant, pergunta: str, k: int = 5, distancia_max: float = 0.5, categorias=None):
    """Busca top-K artigos da base de conhecimento mais relevantes pra `pergunta`.

    Usa pgvector com distancia cosseno (`<=>`). Filtra por tenant + publicado=True.
    Ignora artigos sem embedding (ainda nao processados pelo backfill/signal).

    Args:
        tenant: instancia Tenant.
        pergunta: texto livre.
        k: numero max de resultados.
        distancia_max: corta resultados acima desse limiar de distancia cosseno
            (0 = identico, 2 = oposto). 0.5 ja e bem permissivo; 0.3 e mais
            preciso. Default 0.5 pra nao deixar buscas voltarem vazias logo de
            cara em bases pequenas.

    Returns:
        list[dict] com {artigo: ArtigoConhecimento, distancia: float}.
        Lista vazia se nao houver match relevante OU se nao conseguir gerar
        embedding da pergunta (sem credencial OpenAI).
    """
    from pgvector.django import CosineDistance
    from apps.suporte.models import ArtigoConhecimento
    from apps.sistema.services.embeddings import gerar_embedding

    if not pergunta or len(pergunta.strip()) < 3:
        return []

    emb_pergunta = gerar_embedding(pergunta, tenant=tenant)
    if emb_pergunta is None:
        logger.warning('buscar_artigos: nao gerou embedding da pergunta')
        return []

    qs = (
        ArtigoConhecimento.all_tenants
        .filter(tenant=tenant, publicado=True)
        .exclude(embedding__isnull=True)
    )
    if categorias:
        # Escopo opcional por categoria (ex: agente que só enxerga parte da base).
        qs = qs.filter(categoria_id__in=categorias)
    qs = (
        qs.annotate(distancia=CosineDistance('embedding', emb_pergunta))
        .filter(distancia__lte=distancia_max)
        .order_by('distancia')[:k]
    )

    return [{'artigo': a, 'distancia': float(a.distancia)} for a in qs]
