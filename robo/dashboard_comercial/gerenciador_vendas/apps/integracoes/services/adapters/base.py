"""
Interface base pros adapters de ERP → ClienteConsolidado.

Cada ERP suportado deve implementar um adapter com:

    sync_cliente(cliente_nativo) -> ClienteConsolidado
        Recebe instância do modelo nativo (ClienteHubsoft, ClienteSGP, ...)
        Retorna ClienteConsolidado upserted (criado ou atualizado).

    iter_clientes_ativos(tenant) -> Iterator[cliente_nativo]
        Iterador sobre clientes ativos do ERP no tenant. Usado pelo cron
        de sync em batch.

    NOME_ORIGEM: str
        Slug da origem ('hubsoft', 'sgp', etc). Tem que bater com o choice
        de ClienteConsolidado.ORIGEM_CHOICES.

Adapter NÃO precisa duplicar lógica de auth/conexão com ERP — pode importar
o service nativo (HubsoftService, SGPService) se precisar.

A função real de upsert vive aqui (DRY entre adapters):
"""
from datetime import timedelta

from django.utils import timezone


def upsert_consolidado(*, tenant, dados):
    """
    Cria ou atualiza um ClienteConsolidado a partir do dict normalizado.

    Args:
        tenant: instância de Tenant
        dados: dict com chaves obrigatórias (origem, id_origem, nome) e opcionais.

    Returns:
        ClienteConsolidado (criado ou atualizado)
    """
    from apps.integracoes.models import ClienteConsolidado

    if not dados.get('origem') or not dados.get('id_origem'):
        raise ValueError('Adapter precisa fornecer origem e id_origem')

    # Garantir id_origem como string
    dados['id_origem'] = str(dados['id_origem'])

    # Calcular meses_como_cliente se temos data_virou_cliente mas não meses
    if dados.get('data_virou_cliente') and 'meses_como_cliente' not in dados:
        delta = timezone.now() - dados['data_virou_cliente']
        dados['meses_como_cliente'] = round(delta.days / 30, 1)

    cliente, _ = ClienteConsolidado.objects.update_or_create(
        tenant=tenant,
        origem=dados['origem'],
        id_origem=dados['id_origem'],
        defaults={k: v for k, v in dados.items() if k not in ('origem', 'id_origem', 'tenant')},
    )
    return cliente
