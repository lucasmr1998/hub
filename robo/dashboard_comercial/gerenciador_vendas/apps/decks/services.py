"""
Servicos do editor de deck. O coracao e reusar a engine de relatorios pra
computar os dados de um bloco tipo=widget (nada de grafico reinventado).
"""
from apps.relatorios.query_builder import WidgetQueryBuilder


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
