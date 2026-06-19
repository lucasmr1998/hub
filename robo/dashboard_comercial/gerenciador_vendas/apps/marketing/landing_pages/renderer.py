"""
Renderer server-side da Landing Page.

Itera por LandingPage.blocos_json, resolve template de cada bloco pelo catalogo,
renderiza com props + contexto global, junta o HTML final.

Sem dependencia de fronted JS — render 100% server-side. JS opcional adicionado
dentro de blocos especificos (ex: bloco `form` na Fase 2).

Uso:
    from apps.marketing.landing_pages.renderer import renderizar_landing
    html = renderizar_landing(landing_page, request=request)
"""
from __future__ import annotations

import logging
from typing import Any

from django.template.loader import get_template

from .catalog import REGISTRY, get_bloco

logger = logging.getLogger(__name__)


# Bloco unico de erro (renderiza placeholder quando bloco esta com config ruim
# em vez de quebrar a pagina inteira)
BLOCO_ERRO_TEMPLATE = """
<div style="padding:12px;background:#fee2e2;border:1px solid #fca5a5;color:#991b1b;font-family:monospace;font-size:12px;">
  <strong>[bloco com erro]</strong> tipo={tipo!r} motivo={motivo}
</div>
"""


def renderizar_bloco(bloco_dict: dict, contexto_global: dict | None = None, request=None) -> str:
    """Renderiza UM bloco a partir do dict {tipo, props}. Nunca levanta excecao."""
    contexto_global = contexto_global or {}
    tipo = bloco_dict.get('tipo', '')
    props = bloco_dict.get('props', {}) or {}

    spec = get_bloco(tipo)
    if not spec:
        return BLOCO_ERRO_TEMPLATE.format(tipo=tipo, motivo='tipo desconhecido')

    try:
        tpl = get_template(spec.template)
    except Exception as exc:
        logger.warning('[LP] template ausente pra bloco %s: %s', tipo, exc)
        return BLOCO_ERRO_TEMPLATE.format(tipo=tipo, motivo=f'template ausente: {exc}')

    ctx = {
        'props': props,
        'bloco_tipo': tipo,
        'bloco_label': spec.label,
        **contexto_global,
    }
    try:
        return tpl.render(ctx, request=request)
    except Exception as exc:
        logger.exception('[LP] falha ao renderizar bloco %s: %s', tipo, exc)
        return BLOCO_ERRO_TEMPLATE.format(tipo=tipo, motivo=f'erro de render: {exc}')


def renderizar_blocos(blocos_json: list[dict], contexto_global: dict | None = None, request=None) -> str:
    """Renderiza array de blocos em ordem. Junta o HTML final."""
    if not isinstance(blocos_json, list):
        logger.warning('[LP] blocos_json nao e lista: %r', type(blocos_json))
        return ''

    partes: list[str] = []
    for bloco in blocos_json:
        if not isinstance(bloco, dict):
            continue
        partes.append(renderizar_bloco(bloco, contexto_global=contexto_global, request=request))
    return '\n'.join(partes)


def renderizar_landing(landing, request=None) -> str:
    """Renderiza a LP completa: wrapper HTML + blocos + SEO + pixels."""
    contexto_global = {
        'landing': landing,
        'config': landing.config_json or {},
        'tenant': landing.tenant,
    }
    blocos_html = renderizar_blocos(
        landing.blocos_json or [],
        contexto_global=contexto_global,
        request=request,
    )

    # Wrapper completo da pagina
    wrapper = get_template('landing_pages/wrapper.html')
    return wrapper.render({
        'landing': landing,
        'config': landing.config_json or {},
        'blocos_html': blocos_html,
        'tenant': landing.tenant,
    }, request=request)
