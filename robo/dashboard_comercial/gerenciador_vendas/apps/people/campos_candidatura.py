"""
Catalogo dos campos do formulario de candidatura.

Irmao de campos_formulario.py (que e do DP), com a mesma mecanica: uma lista fixa
de CAMPOS DO SISTEMA, e a vaga escolhe por campo se e solicitado e se e
obrigatorio. Catalogo separado porque candidato e colaborador coletam coisas
diferentes: candidato tem experiencia previa e curriculo e NAO tem CPF nem Pix.

Python puro, sem Django, e continua assim depois dos campos custom: as funcoes
recebem os campos do tenant como PARAMETRO (`extras`), ja convertidos em dict
por `CampoCandidatura.como_campo()`. Quem consulta o banco e o model; aqui so se
resolve configuracao. E o que mantem este modulo testavel em milissegundos.

O catalogo de SISTEMA e codigo porque cada campo tem coluna correspondente no
Candidato. O que nao tem coluna vira `CampoCandidatura` e mora em
`Candidato.dados_custom`.

Dois campos sao TRAVADOS, e por razoes diferentes de peso igual:
- nome_completo: sem ele o RH nao sabe a quem esta respondendo.
- whatsapp: e a chave do dedup E o unico canal de retorno. Desligar quebraria as
  duas coisas de uma vez.
"""

CAMPOS_SISTEMA = [
    {
        'nome': 'nome_completo',
        'tipo': 'text',
        'rotulo_padrao': 'Nome completo',
        'travado': True,
    },
    {
        'nome': 'whatsapp',
        'tipo': 'tel',
        'rotulo_padrao': 'WhatsApp',
        'ajuda': 'Com DDD. É por aqui que a gente responde.',
        'travado': True,
    },
    {
        'nome': 'email',
        'tipo': 'email',
        'rotulo_padrao': 'Email',
    },
    {
        'nome': 'data_nascimento',
        'tipo': 'date',
        'rotulo_padrao': 'Data de nascimento',
    },
    {
        'nome': 'cidade',
        'tipo': 'text',
        'rotulo_padrao': 'Cidade',
    },
    {
        'nome': 'bairro',
        'tipo': 'text',
        'rotulo_padrao': 'Bairro',
    },
    {
        'nome': 'estado',
        'tipo': 'text',
        'rotulo_padrao': 'Estado (UF)',
    },
    {
        'nome': 'experiencia_previa',
        'tipo': 'text',
        'rotulo_padrao': 'Experiência prévia',
        'placeholder': 'Ex: 1 ano como atendente',
    },
    {
        'nome': 'disponibilidade_horario',
        'tipo': 'text',
        'rotulo_padrao': 'Disponibilidade de horário',
        'placeholder': 'Ex: noites e fins de semana',
    },
    {
        'nome': 'curriculo',
        'tipo': 'file',
        'rotulo_padrao': 'Currículo',
        'ajuda': 'PDF ou Word, até 5 MB.',
    },
]

SECOES = [
    {
        'chave': 'dados',
        'titulo': 'Seus dados',
        'icone': 'bi-person',
        'campos': ['nome_completo', 'whatsapp', 'email', 'data_nascimento'],
    },
    {
        'chave': 'endereco',
        'titulo': 'Onde você mora',
        'icone': 'bi-geo-alt',
        'campos': ['cidade', 'bairro', 'estado'],
    },
    {
        'chave': 'experiencia',
        'titulo': 'Sua experiência',
        'icone': 'bi-briefcase',
        'campos': ['experiencia_previa', 'disponibilidade_horario', 'curriculo'],
    },
]

SECAO_DE_CAMPO = {
    nome: secao['chave']
    for secao in SECOES
    for nome in secao['campos']
}

CAMPOS_POR_NOME = {campo['nome']: campo for campo in CAMPOS_SISTEMA}
NOMES_DE_CAMPO = [campo['nome'] for campo in CAMPOS_SISTEMA]
CAMPOS_TRAVADOS = [c['nome'] for c in CAMPOS_SISTEMA if c.get('travado')]

# O que uma vaga nova traz marcado. Espelha o conjunto que a spec observou no
# formulario de candidatura da origem (secao 2.4).
PADRAO = {
    'nome_completo':           {'solicitar': True,  'obrigatorio': True},
    'whatsapp':                {'solicitar': True,  'obrigatorio': True},
    'email':                   {'solicitar': True,  'obrigatorio': False},
    'data_nascimento':         {'solicitar': True,  'obrigatorio': False},
    'cidade':                  {'solicitar': True,  'obrigatorio': False},
    'bairro':                  {'solicitar': True,  'obrigatorio': False},
    'estado':                  {'solicitar': True,  'obrigatorio': False},
    'experiencia_previa':      {'solicitar': True,  'obrigatorio': False},
    'disponibilidade_horario': {'solicitar': True,  'obrigatorio': False},
    'curriculo':               {'solicitar': True,  'obrigatorio': False},
}


def config_padrao():
    """Configuracao inicial de uma vaga, com rotulo padrao preenchido."""
    return {
        nome: {
            'solicitar': valores['solicitar'],
            'obrigatorio': valores['obrigatorio'],
            'rotulo': CAMPOS_POR_NOME[nome]['rotulo_padrao'],
        }
        for nome, valores in PADRAO.items()
    }


def catalogo(extras=None):
    """
    Campos de sistema seguidos dos campos que o tenant inventou.

    Os custom vao DEPOIS de proposito: os de sistema tem ordem pensada (dados,
    endereco, experiencia) e um campo novo entrando no meio mudaria o
    formulario de todo mundo sem ninguem ter pedido.
    """
    return CAMPOS_SISTEMA + list(extras or [])


def normalizar_config(config, extras=None):
    """
    Completa a config com o que faltar e descarta campo desconhecido.

    Vaga salva antes de um campo novo entrar no catalogo continua valendo: o
    campo novo aparece com o padrao em vez de sumir da tela.

    Campo custom nasce NAO SOLICITADO. Criar um campo no nivel do tenant nao
    pode mexer, sozinho, nas vagas que ja estao publicadas e recebendo gente: o
    RH liga o campo na vaga em que ele faz sentido.
    """
    config = config or {}
    resultado = {}
    for campo in catalogo(extras):
        nome = campo['nome']
        salvo = config.get(nome) or {}
        travado = campo.get('travado', False)
        resultado[nome] = {
            'solicitar': True if travado else bool(salvo.get(
                'solicitar', PADRAO.get(nome, {}).get('solicitar', False))),
            'obrigatorio': True if travado else bool(salvo.get(
                'obrigatorio', PADRAO.get(nome, {}).get('obrigatorio', False))),
            'rotulo': (salvo.get('rotulo') or campo['rotulo_padrao']).strip(),
        }
        # Campo nao solicitado nao pode ser obrigatorio: seria um formulario
        # impossivel de enviar.
        if not resultado[nome]['solicitar']:
            resultado[nome]['obrigatorio'] = False
    return resultado


def campos_solicitados(config, extras=None):
    """Campos que o formulario publico mostra, na ordem do catalogo."""
    config = normalizar_config(config, extras)
    return [
        {**campo, **config[campo['nome']]}
        for campo in catalogo(extras)
        if config[campo['nome']]['solicitar']
    ]


def agrupar_em_secoes(campos):
    """
    Distribui os campos solicitados nas secoes, na ordem do catalogo.

    Secao sem campo solicitado nao aparece: uma vaga que so pede nome e WhatsApp
    nao deve mostrar o titulo "Onde voce mora" com nada embaixo.
    """
    por_secao = {}
    for campo in campos:
        # Campo custom traz a propria secao; o de sistema tem a dele no mapa.
        chave = campo.get('secao') or SECAO_DE_CAMPO.get(campo['nome'], 'dados')
        if chave not in SECAO_DE_CAMPO.values():
            chave = 'experiencia'
        por_secao.setdefault(chave, []).append(campo)

    return [
        {**secao, 'itens': por_secao[secao['chave']]}
        for secao in SECOES
        if por_secao.get(secao['chave'])
    ]


def campos_obrigatorios(config, extras=None):
    """Nomes dos campos que a vaga exige. Usado na validacao do POST."""
    config = normalizar_config(config, extras)
    return [nome for nome, v in config.items() if v['obrigatorio']]


def e_custom(nome):
    """Se a chave veio de um CampoCandidatura, e nao do catalogo de sistema."""
    return nome.startswith('custom__')


def slug_de(nome):
    """A chave em `Candidato.dados_custom` a partir do nome no formulario."""
    return nome[len('custom__'):] if e_custom(nome) else nome
