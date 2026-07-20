"""
Catalogo dos campos do formulario de cadastro.

Espelha a tela "Novo Template" do produto de origem: uma lista fixa de CAMPOS DO
SISTEMA, e o template escolhe por campo se ele e solicitado, se e obrigatorio e
com que rotulo aparece.

Python puro, sem Django. O catalogo e codigo porque cada campo tem uma coluna
correspondente no `Colaborador`: nao da pra o cliente inventar campo novo aqui
sem alterar o model. Campo customizado, se for preciso um dia, vira feature
propria com armazenamento em JSON.

O que NAO entra aqui, e e proposital (a tela de origem avisa isso em texto):
documento de identificacao digitalizado e dados bancarios sensiveis ficam numa
etapa propria de seguranca, nao no formulario aberto de cadastro.
"""

# `travado` marca campo que o cliente nao pode desligar nem tornar opcional.
# Nome e o unico: sem ele nao ha cadastro, e o dedup precisa de algo pra
# comparar quando nao ha documento.
CAMPOS_SISTEMA = [
    {
        'nome': 'nome_completo',
        'label': 'Nome completo',
        'descricao': 'Nome completo do colaborador. Aparece em todo o cadastro e nos documentos.',
        'tipo': 'text',
        'rotulo_padrao': 'Nome completo',
        'travado': True,
    },
    {
        'nome': 'primeiro_nome',
        'label': 'Nome preferido',
        'descricao': 'Como o colaborador prefere ser chamado no dia a dia.',
        'tipo': 'text',
        'rotulo_padrao': 'Primeiro nome',
    },
    {
        'nome': 'cpf',
        'label': 'Documento fiscal pessoal',
        'descricao': 'Documento que identifica o colaborador (CPF no Brasil). '
                     'E o que impede a mesma pessoa de ser cadastrada duas vezes.',
        'tipo': 'text',
        'rotulo_padrao': 'CPF',
    },
    {
        'nome': 'rg',
        'label': 'Documento de identidade',
        'descricao': 'RG ou equivalente.',
        'tipo': 'text',
        'rotulo_padrao': 'RG',
    },
    {
        'nome': 'data_nascimento',
        'label': 'Data de nascimento',
        'descricao': 'Usada no dedup quando nao ha documento, e no aniversario.',
        'tipo': 'date',
        'rotulo_padrao': 'Data de Nascimento',
    },
    {
        'nome': 'telefone',
        'label': 'Celular',
        'descricao': 'Canal principal com o colaborador.',
        'tipo': 'tel',
        'rotulo_padrao': 'Celular',
    },
    {
        'nome': 'email',
        'label': 'Email',
        'descricao': 'Email pessoal do colaborador.',
        'tipo': 'email',
        'rotulo_padrao': 'Email',
    },
    {
        'nome': 'pis',
        'label': 'PIS',
        'descricao': 'Numero do PIS/PASEP.',
        'tipo': 'text',
        'rotulo_padrao': 'PIS',
    },
    {
        'nome': 'tipo_chave_pix',
        'label': 'Tipo de chave Pix',
        'descricao': 'Como o colaborador recebe pagamentos avulsos.',
        'tipo': 'select',
        'rotulo_padrao': 'Tipo de Chave Pix',
        'opcoes': 'TIPO_CHAVE_PIX_CHOICES',
    },
    {
        'nome': 'chave_pix',
        'label': 'Chave Pix',
        'descricao': 'A chave em si.',
        'tipo': 'text',
        'rotulo_padrao': 'Chave Pix',
    },
    {
        'nome': 'cep',
        'label': 'CEP',
        'descricao': 'Codigo postal do endereco residencial.',
        'tipo': 'text',
        'rotulo_padrao': 'CEP',
    },
    {
        'nome': 'rua',
        'label': 'Rua',
        'descricao': 'Logradouro do endereco residencial.',
        'tipo': 'text',
        'rotulo_padrao': 'Rua / Logradouro',
    },
    {
        'nome': 'numero',
        'label': 'Numero',
        'descricao': 'Numero do endereco.',
        'tipo': 'text',
        'rotulo_padrao': 'Numero',
    },
    {
        'nome': 'complemento',
        'label': 'Complemento',
        'descricao': 'Apartamento, bloco, referencia.',
        'tipo': 'text',
        'rotulo_padrao': 'Complemento',
    },
    {
        'nome': 'bairro',
        'label': 'Bairro',
        'descricao': 'Bairro do endereco.',
        'tipo': 'text',
        'rotulo_padrao': 'Bairro',
    },
    {
        'nome': 'cidade',
        'label': 'Cidade',
        'descricao': 'Cidade do endereco.',
        'tipo': 'text',
        'rotulo_padrao': 'Cidade',
    },
    {
        'nome': 'estado',
        'label': 'Estado',
        'descricao': 'UF do endereco.',
        'tipo': 'select',
        'rotulo_padrao': 'Estado',
        'opcoes': 'UFS',
    },
]

CAMPOS_POR_NOME = {campo['nome']: campo for campo in CAMPOS_SISTEMA}
NOMES_DE_CAMPO = [campo['nome'] for campo in CAMPOS_SISTEMA]
CAMPOS_TRAVADOS = [c['nome'] for c in CAMPOS_SISTEMA if c.get('travado')]

# O que um template novo traz marcado. Espelha o formulario de cadastro que a
# spec descreveu como o real: nome, documento, contato, endereco e Pix, com o
# minimo obrigatorio pra o dedup funcionar.
PADRAO_BRASIL = {
    'nome_completo':   {'solicitar': True,  'obrigatorio': True},
    'primeiro_nome':   {'solicitar': True,  'obrigatorio': False},
    'cpf':             {'solicitar': True,  'obrigatorio': True},
    'rg':              {'solicitar': True,  'obrigatorio': False},
    'data_nascimento': {'solicitar': True,  'obrigatorio': True},
    'telefone':        {'solicitar': True,  'obrigatorio': True},
    'email':           {'solicitar': True,  'obrigatorio': False},
    'pis':             {'solicitar': True,  'obrigatorio': False},
    'tipo_chave_pix':  {'solicitar': True,  'obrigatorio': False},
    'chave_pix':       {'solicitar': True,  'obrigatorio': False},
    'cep':             {'solicitar': True,  'obrigatorio': False},
    'rua':             {'solicitar': True,  'obrigatorio': False},
    'numero':          {'solicitar': True,  'obrigatorio': False},
    'complemento':     {'solicitar': True,  'obrigatorio': False},
    'bairro':          {'solicitar': True,  'obrigatorio': False},
    'cidade':          {'solicitar': True,  'obrigatorio': False},
    'estado':          {'solicitar': True,  'obrigatorio': False},
}


def config_padrao():
    """Copia da configuracao inicial, com rotulo padrao preenchido."""
    return {
        nome: {
            'solicitar': valores['solicitar'],
            'obrigatorio': valores['obrigatorio'],
            'rotulo': CAMPOS_POR_NOME[nome]['rotulo_padrao'],
        }
        for nome, valores in PADRAO_BRASIL.items()
    }


def normalizar_config(config):
    """
    Completa a configuracao com o que faltar e descarta campo desconhecido.

    Template gravado antes de um campo novo entrar no catalogo continua valendo:
    o campo novo aparece com o padrao em vez de sumir da tela.
    """
    config = config or {}
    resultado = {}
    for campo in CAMPOS_SISTEMA:
        nome = campo['nome']
        salvo = config.get(nome) or {}
        travado = campo.get('travado', False)
        resultado[nome] = {
            'solicitar': True if travado else bool(salvo.get(
                'solicitar', PADRAO_BRASIL.get(nome, {}).get('solicitar', False))),
            'obrigatorio': True if travado else bool(salvo.get(
                'obrigatorio', PADRAO_BRASIL.get(nome, {}).get('obrigatorio', False))),
            'rotulo': (salvo.get('rotulo') or campo['rotulo_padrao']).strip(),
        }
        # Campo que nao e solicitado nao pode ser obrigatorio: seria um
        # formulario impossivel de enviar.
        if not resultado[nome]['solicitar']:
            resultado[nome]['obrigatorio'] = False
    return resultado


def campos_solicitados(config):
    """Campos que o formulario publico deve mostrar, na ordem do catalogo."""
    config = normalizar_config(config)
    return [
        {**campo, **config[campo['nome']]}
        for campo in CAMPOS_SISTEMA
        if config[campo['nome']]['solicitar']
    ]
