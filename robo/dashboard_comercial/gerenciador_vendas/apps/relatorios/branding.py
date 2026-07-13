"""
Paleta dos graficos derivada da MARCA do tenant.

A marca ja existe em `sistema.ConfiguracaoEmpresa` (cor_primaria, cor_secundaria,
logo_empresa, nome_empresa). Aqui a gente so monta a paleta do grafico a partir
dela: a cor da marca vem primeiro (serie unica de barra/linha usa ela) e o resto
completa com uma categorica saturada, pra categorias ficarem distinguiveis.

Antes a paleta era pastel e chumbada no template (e duplicada no deck). Agora
vive num lugar so e sai na cor do cliente.
"""
import re

# Categorica saturada de apoio (mesma familia que o relatorio legado usava, que
# era visivelmente mais viva que a pastel antiga).
CATEGORICA_PADRAO = [
    '#2563eb',  # azul
    '#10b981',  # verde
    '#f59e0b',  # ambar
    '#ef4444',  # vermelho
    '#6366f1',  # indigo
    '#14b8a6',  # teal
    '#f97316',  # laranja
    '#8b5cf6',  # violeta
]

_HEX = re.compile(r'^#[0-9A-Fa-f]{6}$')


def _valida(cor):
    return bool(cor) and bool(_HEX.match(str(cor).strip()))


def paleta_tenant(tenant, total=8):
    """Paleta de grafico do tenant: [cor_primaria, cor_secundaria, ...categorica].
    Sem tenant ou sem config, cai na categorica padrao."""
    from apps.sistema.models import ConfiguracaoEmpresa

    cores = []
    try:
        cfg = ConfiguracaoEmpresa.get_configuracao_ativa(tenant=tenant) if tenant else None
    except Exception:
        cfg = None
    if cfg:
        for c in (cfg.cor_primaria, cfg.cor_secundaria):
            c = (c or '').strip()
            if _valida(c) and c.lower() not in [x.lower() for x in cores]:
                cores.append(c)
    for c in CATEGORICA_PADRAO:
        if c.lower() not in [x.lower() for x in cores]:
            cores.append(c)
    return cores[:total]
