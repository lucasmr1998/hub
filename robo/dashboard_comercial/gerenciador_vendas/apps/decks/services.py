"""
Servicos do editor de deck. O coracao e reusar a engine de relatorios pra
computar os dados de um bloco tipo=widget (nada de grafico reinventado).

O tema (identidade visual) HERDA a marca do tenant (sistema.ConfiguracaoEmpresa:
logo, cor_primaria/secundaria, nome) e o deck pode sobrescrever pontualmente.
Assim o cliente configura a marca UMA vez e todo deck ja nasce na identidade dele.
"""
from apps.relatorios.query_builder import WidgetQueryBuilder

# Defaults do tema quando o tenant nao tem marca configurada.
TEMA_PADRAO = {
    'cor_primaria': '#2563eb',
    'cor_secundaria': '#0f172a',
    'cor_fundo': '#ffffff',
    'cor_texto': '#0f172a',
    'fonte': "'Inter', system-ui, sans-serif",
    'logo_url': '',
    'nome_empresa': '',
    'mostrar_logo': True,
}


def tema_deck(deck, tenant):
    """Tema efetivo do deck: marca do tenant + override do proprio deck."""
    from apps.sistema.models import ConfiguracaoEmpresa

    tema = dict(TEMA_PADRAO)
    try:
        cfg = ConfiguracaoEmpresa.get_configuracao_ativa(tenant=tenant) if tenant else None
    except Exception:
        cfg = None
    if cfg:
        if cfg.cor_primaria:
            tema['cor_primaria'] = cfg.cor_primaria
        if cfg.cor_secundaria:
            tema['cor_secundaria'] = cfg.cor_secundaria
        if cfg.nome_empresa:
            tema['nome_empresa'] = cfg.nome_empresa
        try:
            if cfg.logo_empresa:
                tema['logo_url'] = cfg.logo_empresa.url
        except Exception:
            pass
    # override do deck (so as chaves que ele definiu)
    for k, v in (getattr(deck, 'tema', None) or {}).items():
        if k in tema and v not in (None, ''):
            tema[k] = v
    return tema


def dados_widget(widget, tenant, overrides=None):
    """Computa os dados de um Widget (do modulo relatorios) via a engine
    existente e devolve {labels, series, total, meta} com meta.visualizacao
    setado (o front usa isso pra escolher o renderer). Espelha o
    api_widget_dados de relatorios, mas sob a permissao de decks."""
    resultado = WidgetQueryBuilder(widget, tenant=tenant, overrides=overrides).build().to_dict()
    meta = resultado.get('meta')
    if isinstance(meta, dict):
        meta['visualizacao'] = widget.visualizacao
        # o KPI numero precisa do formato (moeda/percentual) que vive no widget
        meta['formato'] = (widget.config_extra or {}).get('formato', '')
    return resultado
