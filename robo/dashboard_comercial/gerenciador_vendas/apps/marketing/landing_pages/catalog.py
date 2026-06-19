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
from dataclasses import dataclass


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


# Form — bloco container que renderiza um FormularioLanding
registrar(BlocoSpec(
    slug='form',
    label='Formulario',
    template='landing_pages/blocos/form.html',
    descricao='Renderiza um Formulario configurado. Campos componentizados (text, email, telefone, CPF/CNPJ, CEP, viabilidade, etc.). Submit cria LeadProspecto.',
    categoria='form',
    schema={
        'formulario_id': {'type': 'integer', 'label': 'ID do Formulario', 'required': True},
        'titulo': _str('Titulo acima do form', max_length=200),
        'descricao': _str('Descricao acima do form', multiline=True, max_length=500),
        'cor_botao': _color('Cor do botao submit', '#2563eb'),
        'max_width': _int('Largura maxima (px)', default=560, min_v=300, max_v=900),
    },
    defaults={
        'formulario_id': None,
        'titulo': 'Cadastre-se',
        'descricao': '',
        'cor_botao': '#2563eb',
        'max_width': 560,
    },
))


# ============================================================================
# REGISTRY DE CAMPOS DO FORM (9 tipos componentizados)
# ============================================================================

@dataclass
class CampoSpec:
    slug: str
    label: str
    template: str
    schema: dict
    defaults: dict
    descricao: str = ''
    # Validacao server-side: nome do validador no validators.py (opcional)
    validador: str | None = None


CAMPO_REGISTRY: dict[str, CampoSpec] = {}


def registrar_campo(spec: CampoSpec):
    CAMPO_REGISTRY[spec.slug] = spec
    return spec


# Props comuns a todos os campos
def _props_base(required_default: bool = False) -> dict:
    return {
        'name': _str('Nome do campo (chave do payload)', required=True, max_length=80),
        'label': _str('Label exibida pro usuario', required=True, max_length=200),
        'placeholder': _str('Placeholder', max_length=200),
        'help_text': _str('Texto de ajuda abaixo do campo', max_length=300),
        'required': _bool('Obrigatorio', required_default),
    }


# 1) text
registrar_campo(CampoSpec(
    slug='text',
    label='Texto',
    template='landing_pages/campos/text.html',
    schema={**_props_base(), 'min_length': _int('Min caracteres', 0, 0, 1000),
            'max_length': _int('Max caracteres', 200, 1, 5000)},
    defaults={'name': 'nome', 'label': 'Nome', 'placeholder': '', 'help_text': '',
              'required': True, 'min_length': 0, 'max_length': 200},
    validador='validar_text',
))

# 2) email
registrar_campo(CampoSpec(
    slug='email',
    label='E-mail',
    template='landing_pages/campos/email.html',
    schema=_props_base(),
    defaults={'name': 'email', 'label': 'E-mail', 'placeholder': 'seu@email.com',
              'help_text': '', 'required': True},
    validador='validar_email',
))

# 3) telefone
registrar_campo(CampoSpec(
    slug='telefone',
    label='Telefone (BR)',
    template='landing_pages/campos/telefone.html',
    schema=_props_base(),
    defaults={'name': 'telefone', 'label': 'Telefone', 'placeholder': '(11) 99999-9999',
              'help_text': '', 'required': True},
    validador='validar_telefone',
))

# 4) cpf_cnpj
registrar_campo(CampoSpec(
    slug='cpf_cnpj',
    label='CPF / CNPJ',
    template='landing_pages/campos/cpf_cnpj.html',
    schema={**_props_base(),
            'tipo': _select('Tipo aceito', ['auto', 'pf', 'pj'], 'auto')},
    defaults={'name': 'cpf_cnpj', 'label': 'CPF/CNPJ', 'placeholder': '000.000.000-00',
              'help_text': '', 'required': True, 'tipo': 'auto'},
    validador='validar_cpf_cnpj',
))

# 5) cep
registrar_campo(CampoSpec(
    slug='cep',
    label='CEP (com ViaCEP)',
    template='landing_pages/campos/cep.html',
    schema={**_props_base(),
            'integra_viacep': _bool('Auto-preenche endereco via ViaCEP', True),
            'campos_preenchidos': _str('Campos preenchidos (csv: rua,bairro,cidade,uf)',
                                       default='rua,bairro,cidade,uf')},
    defaults={'name': 'cep', 'label': 'CEP', 'placeholder': '00000-000',
              'help_text': 'Preenchimento automatico do endereco', 'required': True,
              'integra_viacep': True, 'campos_preenchidos': 'rua,bairro,cidade,uf'},
    validador='validar_cep',
))

# 6) endereco (multi-campo: rua, numero, complemento, bairro, cidade, uf)
registrar_campo(CampoSpec(
    slug='endereco',
    label='Endereco completo',
    template='landing_pages/campos/endereco.html',
    schema={**_props_base(),
            'mostrar_complemento': _bool('Mostrar campo complemento', True),
            'mostrar_referencia': _bool('Mostrar campo ponto de referencia', False)},
    defaults={'name': 'endereco', 'label': 'Endereco', 'placeholder': '', 'help_text': '',
              'required': True, 'mostrar_complemento': True, 'mostrar_referencia': False},
    validador='validar_endereco',
))

# 7) select
registrar_campo(CampoSpec(
    slug='select',
    label='Selecao (dropdown)',
    template='landing_pages/campos/select.html',
    schema={**_props_base(),
            'opcoes': {'type': 'array', 'label': 'Opcoes', 'items': {'type': 'string'},
                       'default': []},
            'multi': _bool('Multi-selecao', False)},
    defaults={'name': 'plano', 'label': 'Escolha um plano', 'placeholder': '', 'help_text': '',
              'required': True, 'opcoes': [], 'multi': False},
    validador='validar_select',
))

# 8) textarea
registrar_campo(CampoSpec(
    slug='textarea',
    label='Texto longo (textarea)',
    template='landing_pages/campos/textarea.html',
    schema={**_props_base(), 'rows': _int('Linhas visiveis', 4, 2, 20),
            'max_length': _int('Max caracteres', 2000, 10, 10000)},
    defaults={'name': 'mensagem', 'label': 'Mensagem', 'placeholder': '', 'help_text': '',
              'required': False, 'rows': 4, 'max_length': 2000},
    validador='validar_text',
))

# 9) viabilidade (especial — chama API HubSoft/SGP)
registrar_campo(CampoSpec(
    slug='viabilidade',
    label='Viabilidade tecnica (HubSoft/SGP)',
    template='landing_pages/campos/viabilidade.html',
    descricao=(
        'Campo especial pra ISP: ao preencher CEP+endereco, consulta viabilidade '
        'na integracao do tenant. Pode bloquear submit se fora cobertura '
        '(via FormularioLanding.bloquear_fora_cobertura).'
    ),
    schema={**_props_base(),
            'mostrar_planos_disponiveis': _bool('Mostrar planos disponiveis quando viabilidade=ok', True),
            'mensagem_fora_cobertura': _str('Mensagem quando fora cobertura',
                default='Infelizmente ainda nao atendemos seu endereco.', max_length=300)},
    defaults={'name': 'viabilidade', 'label': 'Verificacao de cobertura',
              'placeholder': '', 'help_text': 'Confira se atendemos seu endereco',
              'required': False, 'mostrar_planos_disponiveis': True,
              'mensagem_fora_cobertura': 'Infelizmente ainda nao atendemos seu endereco.'},
    validador='validar_viabilidade',
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


def listar_campos() -> list[CampoSpec]:
    return list(CAMPO_REGISTRY.values())


def get_campo(slug: str) -> CampoSpec | None:
    return CAMPO_REGISTRY.get(slug)


def aplicar_defaults_campo(slug: str) -> dict:
    spec = CAMPO_REGISTRY.get(slug)
    return dict(spec.defaults) if spec else {}
