"""
Catalogo de blocos da landing page — registry declarativo + JSON schema.

Cada bloco e definido por:
- slug: identificador usado em blocos_json (ex: "hero", "texto")
- label: nome amigavel pra UI
- template: caminho do partial Django que renderiza o bloco
- schema: JSON schema das props (UI usa pra gerar form de edicao automaticamente)
- defaults: props default quando bloco e adicionado

Adicionar bloco novo = adicionar entrada aqui + criar partial em templates/landing_pages/blocos/.
Zero mudanca no renderer.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BlocoSpec:
    slug: str
    label: str
    template: str
    schema: dict
    defaults: dict
    descricao: str = ''
    categoria: str = 'basico'  # basico / conteudo / form / midia / isp


# Helper pra criar props simples
def _str(label: str, default: str = '', required: bool = False, max_length: int = 200, multiline: bool = False) -> dict:
    return {'type': 'string', 'label': label, 'default': default, 'required': required,
            'maxLength': max_length, 'multiline': multiline}


def _url(label: str, default: str = '', required: bool = False) -> dict:
    return {'type': 'string', 'format': 'uri', 'label': label, 'default': default, 'required': required}


def _select(label: str, options: list, default: str) -> dict:
    return {'type': 'string', 'enum': options, 'label': label, 'default': default}


def _bool(label: str, default: bool = False) -> dict:
    return {'type': 'boolean', 'label': label, 'default': default}


def _int(label: str, default: int = 0, min_v: int = 0, max_v: int = 9999) -> dict:
    return {'type': 'integer', 'label': label, 'default': default, 'minimum': min_v, 'maximum': max_v}


def _color(label: str, default: str = '#000000') -> dict:
    return {'type': 'string', 'format': 'color', 'label': label, 'default': default}


# ============================================================================
# REGISTRY
# ============================================================================

REGISTRY: dict[str, BlocoSpec] = {}


def registrar(spec: BlocoSpec):
    REGISTRY[spec.slug] = spec
    return spec


# Hero — titulo + subtitulo + CTA + imagem fundo
registrar(BlocoSpec(
    slug='hero',
    label='Hero',
    template='landing_pages/blocos/hero.html',
    descricao='Bloco de destaque no topo: titulo + subtitulo + CTA + imagem de fundo.',
    categoria='basico',
    schema={
        'titulo': _str('Titulo principal', required=True, max_length=200),
        'subtitulo': _str('Subtitulo', max_length=300, multiline=True),
        'cta_texto': _str('Texto do botao CTA', default='Saiba mais'),
        'cta_link': _url('Link do CTA', default='#'),
        'imagem_fundo': _url('Imagem de fundo (URL)'),
        'alinhamento': _select('Alinhamento', ['esquerda', 'centro', 'direita'], 'centro'),
        'cor_texto': _color('Cor do texto', '#ffffff'),
        'cor_overlay': _color('Cor do overlay sobre imagem', 'rgba(0,0,0,0.4)'),
    },
    defaults={
        'titulo': 'Bem-vindo',
        'subtitulo': 'Descreva seu produto aqui',
        'cta_texto': 'Saiba mais',
        'cta_link': '#',
        'imagem_fundo': '',
        'alinhamento': 'centro',
        'cor_texto': '#ffffff',
        'cor_overlay': 'rgba(0,0,0,0.4)',
    },
))

# Texto — html livre (paragrafo)
registrar(BlocoSpec(
    slug='texto',
    label='Texto',
    template='landing_pages/blocos/texto.html',
    descricao='Paragrafo de texto com formatacao rica (HTML).',
    categoria='conteudo',
    schema={
        'html': _str('Conteudo HTML', multiline=True, max_length=5000),
        'max_width': _int('Largura maxima (px)', default=720, min_v=200, max_v=1600),
        'alinhamento': _select('Alinhamento', ['esquerda', 'centro', 'direita', 'justificado'], 'esquerda'),
    },
    defaults={
        'html': '<p>Seu texto aqui.</p>',
        'max_width': 720,
        'alinhamento': 'esquerda',
    },
))

# Imagem
registrar(BlocoSpec(
    slug='imagem',
    label='Imagem',
    template='landing_pages/blocos/imagem.html',
    descricao='Imagem responsiva com alt text.',
    categoria='midia',
    schema={
        'src': _url('URL da imagem', required=True),
        'alt': _str('Texto alternativo', max_length=200),
        'link': _url('Link ao clicar (opcional)'),
        'max_width': _int('Largura maxima (px)', default=600, min_v=100, max_v=1600),
        'alinhamento': _select('Alinhamento', ['esquerda', 'centro', 'direita'], 'centro'),
    },
    defaults={
        'src': '',
        'alt': '',
        'link': '',
        'max_width': 600,
        'alinhamento': 'centro',
    },
))

# Botao — CTA isolado
registrar(BlocoSpec(
    slug='botao',
    label='Botao',
    template='landing_pages/blocos/botao.html',
    descricao='Botao com link configuravel.',
    categoria='basico',
    schema={
        'texto': _str('Texto do botao', required=True, default='Clique aqui'),
        'link': _url('Link', default='#'),
        'cor_fundo': _color('Cor de fundo', '#2563eb'),
        'cor_texto': _color('Cor do texto', '#ffffff'),
        'tamanho': _select('Tamanho', ['pequeno', 'medio', 'grande'], 'medio'),
        'alinhamento': _select('Alinhamento', ['esquerda', 'centro', 'direita'], 'centro'),
        'full_width': _bool('Largura total', False),
    },
    defaults={
        'texto': 'Clique aqui',
        'link': '#',
        'cor_fundo': '#2563eb',
        'cor_texto': '#ffffff',
        'tamanho': 'medio',
        'alinhamento': 'centro',
        'full_width': False,
    },
))

# Colunas — container N colunas
registrar(BlocoSpec(
    slug='colunas',
    label='Colunas',
    template='landing_pages/blocos/colunas.html',
    descricao='Wrapper que divide conteudo em 2/3/4 colunas responsivas.',
    categoria='basico',
    schema={
        'n_colunas': _select('Numero de colunas', ['1', '2', '3', '4'], '2'),
        'gap': _int('Espacamento entre colunas (px)', default=24, min_v=0, max_v=80),
        'colunas': {
            'type': 'array',
            'label': 'Conteudo de cada coluna (array de blocos aninhados)',
            'default': [],
        },
    },
    defaults={
        'n_colunas': '2',
        'gap': 24,
        'colunas': [
            {'blocos': []},
            {'blocos': []},
        ],
    },
))


def listar_blocos(categoria: str | None = None) -> list[BlocoSpec]:
    """Retorna blocos do catalogo, filtrando por categoria se passada."""
    blocos = list(REGISTRY.values())
    if categoria:
        blocos = [b for b in blocos if b.categoria == categoria]
    return blocos


def get_bloco(slug: str) -> BlocoSpec | None:
    return REGISTRY.get(slug)


def aplicar_defaults(slug: str) -> dict:
    """Retorna dict de props default pra um bloco. Util ao adicionar bloco no editor."""
    spec = REGISTRY.get(slug)
    if not spec:
        return {}
    return dict(spec.defaults)
