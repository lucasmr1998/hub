"""
Utilitários de markdown pro Workspace.

Sanitização via Bleach (whitelist de tags/atributos/protocolos).
Renderização via biblioteca markdown com extensões básicas.

Uso típico:
    from apps.workspace.markdown_utils import render_markdown, sanitizar_input

    # Antes de salvar conteúdo de Documento.conteudo (markdown):
    doc.conteudo = sanitizar_input(request.POST.get('conteudo', ''))

    # Pra renderizar em template:
    {{ doc.conteudo|render_markdown_safe }}  # via templatetag custom
"""
import bleach
import markdown as md

try:
    from bleach.css_sanitizer import CSSSanitizer
    _CSS_PROPS = [
        # Box / layout
        'display', 'box-sizing', 'overflow', 'overflow-x', 'overflow-y', 'visibility', 'position',
        'top', 'right', 'bottom', 'left', 'z-index', 'float', 'clear',
        'width', 'height', 'min-width', 'min-height', 'max-width', 'max-height',
        # Flex / grid
        'flex', 'flex-direction', 'flex-wrap', 'flex-flow', 'flex-grow', 'flex-shrink', 'flex-basis',
        'justify-content', 'align-items', 'align-content', 'align-self', 'gap', 'row-gap', 'column-gap',
        'grid', 'grid-template', 'grid-template-columns', 'grid-template-rows', 'grid-column', 'grid-row',
        'order',
        # Spacing
        'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
        'margin-block', 'margin-inline',
        'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
        'padding-block', 'padding-inline',
        # Borders
        'border', 'border-top', 'border-right', 'border-bottom', 'border-left',
        'border-color', 'border-top-color', 'border-right-color', 'border-bottom-color', 'border-left-color',
        'border-style', 'border-top-style', 'border-right-style', 'border-bottom-style', 'border-left-style',
        'border-width', 'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width',
        'border-radius', 'border-top-left-radius', 'border-top-right-radius',
        'border-bottom-left-radius', 'border-bottom-right-radius',
        # Backgrounds
        'background', 'background-color', 'background-image', 'background-position',
        'background-size', 'background-repeat',
        # Typography
        'color', 'font', 'font-family', 'font-size', 'font-weight', 'font-style', 'font-synthesis',
        'line-height', 'letter-spacing', 'word-spacing', 'text-align', 'text-decoration',
        'text-transform', 'text-indent', 'text-shadow', 'white-space', 'word-break', 'overflow-wrap',
        '-webkit-font-smoothing', '-moz-osx-font-smoothing',
        # Effects
        'opacity', 'box-shadow', 'transform', 'transition', 'cursor',
        # List
        'list-style', 'list-style-type', 'list-style-position',
        # Tables
        'border-collapse', 'border-spacing', 'table-layout', 'vertical-align',
    ]
    _CSS_SANITIZER = CSSSanitizer(allowed_css_properties=_CSS_PROPS)
except ImportError:
    _CSS_SANITIZER = None


# Tags permitidas no HTML final renderizado
ALLOWED_TAGS = [
    'p', 'br', 'hr',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'strong', 'em', 'b', 'i', 'u', 's', 'mark',
    'ul', 'ol', 'li',
    'blockquote',
    'code', 'pre',
    'a', 'img',
    'table', 'thead', 'tbody', 'tfoot', 'tr', 'td', 'th', 'caption',
    'span', 'div', 'section', 'article', 'header', 'footer', 'main', 'nav',
    'figure', 'figcaption',
    'small', 'sub', 'sup',
]

# Atributos permitidos por tag
ALLOWED_ATTRIBUTES = {
    '*': ['class', 'id', 'style'],
    'a': ['href', 'title', 'target', 'rel', 'style'],
    'img': ['src', 'alt', 'title', 'width', 'height', 'style'],
    'pre': ['class'],
    'code': ['class'],
    'th': ['scope', 'colspan', 'rowspan'],
    'td': ['colspan', 'rowspan', 'style'],
}

# Protocolos permitidos em href / src
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


# Extensões do markdown
MARKDOWN_EXTENSIONS = [
    'extra',           # tables, fenced code, footnotes
    'sane_lists',      # listas mais previsíveis
    'nl2br',           # \n vira <br>
    'codehilite',      # syntax highlight em ``` blocks
]


def _bleach_kwargs(strip_comments=True):
    kw = dict(
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=strip_comments,
    )
    if _CSS_SANITIZER is not None:
        kw['css_sanitizer'] = _CSS_SANITIZER
    return kw


def render_markdown(texto):
    """Converte texto markdown em HTML sanitizado."""
    if not texto:
        return ''
    html = md.markdown(texto, extensions=MARKDOWN_EXTENSIONS, output_format='html5')
    return bleach.clean(html, **_bleach_kwargs(strip_comments=True))


def render_html_sanitizado(texto):
    """Para conteúdo que já é HTML (ex: emails exportados do Paper).
    Bypassa o md.markdown e sanitiza diretamente com bleach."""
    if not texto:
        return ''
    return bleach.clean(texto, **_bleach_kwargs(strip_comments=False))


def sanitizar_input(texto):
    """
    Sanitiza markdown bruto antes de salvar.

    Escopo conservador: deixa o markdown passar quase intacto, mas remove
    HTML inline malicioso (script tags, on* handlers, javascript: protocol).
    A renderização final passa de novo por render_markdown que aplica
    a whitelist completa.
    """
    if not texto:
        return ''
    # Remove HTML perigoso, mantém o resto como texto puro markdown
    return bleach.clean(
        texto,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=False,           # não remove conteúdo, escapa
        strip_comments=True,
    )
