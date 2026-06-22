"""Resolvedor do Matrix Brasil por tenant pra engine de automação.

Espelha o padrão de `services/whatsapp.py:uazapi_do_tenant`: o nó nunca fala com
a API direto — pede o cliente por tenant aqui. Se o tenant não tem integração
Matrix ativa, devolve None (o nó vira erro controlado).
"""


def matrix_do_tenant(tenant):
    """Devolve um `MatrixBrasilService` do tenant, ou None se não houver
    integração Matrix ativa configurada."""
    from apps.integracoes.services.matrix_brasil import (
        MatrixBrasilService, MatrixBrasilServiceError,
    )
    try:
        return MatrixBrasilService.from_tenant(tenant)
    except MatrixBrasilServiceError:
        return None
