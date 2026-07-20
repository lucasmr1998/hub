"""
Escopo de tenant pra request sem usuario logado.

O `TenantMiddleware` resolve o tenant a partir de `request.user.perfil.tenant`.
Numa view publica nao ha user, entao ele deixa `request.tenant = None` e o
thread local em `None`. As duas consequencias sao silenciosas e graves:

1. `TenantManager.get_queryset()` com tenant `None` NAO FILTRA NADA. Um `.objects`
   inocente na view publica lista o banco inteiro, de todos os clientes.
2. `TenantMixin.save()` com tenant `None` nao preenche o tenant. Todo create sem
   `tenant=` explicito nasce orfao.

Este modulo assume o tenant no escopo do bloco, resolvido pelo token do link.

E a PRIMEIRA de duas defesas. A segunda e passar `tenant=` explicito em toda
leitura e escrita da view publica. As duas juntas porque nenhuma basta sozinha:
o tenant explicito nao protege codigo de terceiros chamado indiretamente (a
engine de automacao, disparada pela telemetria, usa `.objects` livremente), e o
escopo sozinho depende de o `finally` sempre rodar num servidor que reusa
threads entre requests.
"""
from contextlib import contextmanager


@contextmanager
def escopo_tenant(tenant):
    """Assume `tenant` no thread local durante o bloco, e restaura ao sair."""
    from apps.sistema.middleware import get_current_tenant, set_current_tenant

    anterior = get_current_tenant()
    set_current_tenant(tenant)
    try:
        yield
    finally:
        set_current_tenant(anterior)
