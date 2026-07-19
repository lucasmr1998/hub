"""Catálogo de fontes Wifeed (locais/campanhas) selecionáveis no painel.

Espelha da API Wifeed a lista de locais e campanhas em `WifeedFonte`, preservando
a marcação `ativo` (quais trazem leads). O poller lê as fontes ativas daqui.
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def _upsert(tipo, itens, agora):
    """Insere/atualiza WifeedFonte para uma lista de itens da API. Preserva `ativo`."""
    from crm.models import WifeedFonte
    vistos = 0
    for it in itens:
        ext = it.get('id')
        if ext is None:
            continue
        WifeedFonte.objects.update_or_create(
            tipo=tipo, externo_id=int(ext),
            defaults={
                'nome': (it.get('name') or '').strip()[:200],
                'ativo_wifeed': bool(it.get('isActive', True)),
                'ultima_sincronizacao': agora,
            },
        )
        vistos += 1
    return vistos


def sincronizar_catalogo(client=None):
    """Puxa locais + campanhas da API e atualiza o catálogo. Retorna contagens.

    Não desativa/apaga fontes ausentes (poderia zerar seleção do usuário); apenas
    marca `ativo_wifeed=False` para o que não aparecer mais e existir localmente.
    """
    from crm.models import WifeedFonte
    from crm.services.wifeed_client import WifeedClient

    client = client or WifeedClient()
    agora = timezone.now()

    locais = client.get_locais()
    campanhas = client.get_campanhas()
    n_local = _upsert('local', locais, agora)
    n_camp = _upsert('campanha', campanhas, agora)

    # Marca como inativa no Wifeed o que não veio mais (mantém a linha e o `ativo`).
    ids_local = {int(x['id']) for x in locais if x.get('id') is not None}
    ids_camp = {int(x['id']) for x in campanhas if x.get('id') is not None}
    WifeedFonte.objects.filter(tipo='local').exclude(externo_id__in=ids_local).update(ativo_wifeed=False)
    WifeedFonte.objects.filter(tipo='campanha').exclude(externo_id__in=ids_camp).update(ativo_wifeed=False)

    logger.info('[wifeed] catálogo sincronizado: %s locais, %s campanhas', n_local, n_camp)
    return {'locais': n_local, 'campanhas': n_camp}


def ids_ativos(tipo):
    """IDs externos (Wifeed) das fontes ativas de um tipo ('local'/'campanha')."""
    from crm.models import WifeedFonte
    return list(WifeedFonte.objects.filter(tipo=tipo, ativo=True)
               .values_list('externo_id', flat=True))


def _fonte_do_lead(lead):
    """(tipo, externo_id) da fonte Wifeed do lead, a partir de id_origem_servico.
    Local grava o id numérico; campanha grava 'camp:<id>'. Retorna (None, None)."""
    val = (getattr(lead, 'id_origem_servico', '') or '').strip()
    if not val:
        return None, None
    if val.startswith('camp:'):
        ext = val[5:]
        return ('campanha', int(ext)) if ext.isdigit() else (None, None)
    return ('local', int(val)) if val.isdigit() else (None, None)


def aplicar_tag_fonte(opp, lead):
    """Aplica na oportunidade a tag do LOCAL/CAMPANHA de origem do lead Wifeed.
    Nome da tag = nome da fonte (do catálogo WifeedFonte). Idempotente."""
    from crm.models import TagCRM, WifeedFonte
    tipo, ext = _fonte_do_lead(lead)
    if not tipo:
        return
    fonte = WifeedFonte.objects.filter(tipo=tipo, externo_id=ext).first()
    nome = (fonte.nome if fonte and fonte.nome
            else (f'Campanha {ext}' if tipo == 'campanha' else f'Local {ext}'))
    cor = '#8b5cf6' if tipo == 'campanha' else '#06b6d4'
    try:
        tag, _ = TagCRM.objects.get_or_create(nome=nome[:50], defaults={'cor_hex': cor})
        opp.tags.add(tag)
    except Exception as e:  # noqa: BLE001
        logger.warning('[wifeed] falha ao aplicar tag de fonte na opp %s: %s',
                       getattr(opp, 'pk', '?'), e)
