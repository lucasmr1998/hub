"""
A maquina de estados do ciclo de vida do colaborador.

ESTE ARQUIVO E A FONTE DA VERDADE do ciclo de vida. A spec de origem (Visio)
avisa que os nomes de estado dela eram proposta de quem escreveu o documento, e
nao valores lidos do schema real, e recomenda documentar a nossa maquina como
fonte nova. E o que este modulo e: nenhum estado, transicao ou vocabulario de
People deve ser inventado em outro lugar.

Python puro de proposito, sem import de Django. Da pra testar a maquina inteira
sem subir banco.

Tres defeitos conhecidos da spec estao resolvidos aqui, e cada um esta marcado
no ponto onde a decisao vive:

D1  Existem TRES pontos de entrada no ciclo, nao um. Ver PONTOS_ENTRADA.
D2  Duas geracoes de vocabulario conviviam nas fontes. Aqui existe uma so, e e
    esta. Ver SITUACOES.
D4  A saida da experiencia nao fechava com a entrada do desligamento, e
    "prorrogar" nao tinha estado. Ver TRANSICOES e a nota sobre prorrogacao.
"""
from apps.people.excecoes import TransicaoInvalida


# ── Vocabulario unico (D2) ───────────────────────────────────────────────────

SITUACAO_CADASTRO = 'cadastro'
SITUACAO_EM_ADMISSAO = 'em_admissao'
SITUACAO_EM_EXPERIENCIA = 'em_experiencia'
SITUACAO_EFETIVADO = 'efetivado'
SITUACAO_EM_DESLIGAMENTO = 'em_desligamento'
SITUACAO_DESLIGADO = 'desligado'
SITUACAO_FREELANCER = 'freelancer'

SITUACOES = [
    (SITUACAO_CADASTRO,        'Cadastro'),
    (SITUACAO_EM_ADMISSAO,     'Em admissao'),
    (SITUACAO_EM_EXPERIENCIA,  'Em experiencia'),
    (SITUACAO_EFETIVADO,       'Efetivado'),
    (SITUACAO_EM_DESLIGAMENTO, 'Em desligamento'),
    (SITUACAO_DESLIGADO,       'Desligado'),
    (SITUACAO_FREELANCER,      'Freelancer'),
]

VALORES_SITUACAO = [valor for valor, _ in SITUACOES]
ROTULOS_SITUACAO = dict(SITUACOES)

# Quem conta como gente da casa. Freelancer nao entra: e banco de ex
# colaboradores disponiveis, nao quadro ativo.
SITUACOES_ATIVAS = (
    SITUACAO_CADASTRO,
    SITUACAO_EM_ADMISSAO,
    SITUACAO_EM_EXPERIENCIA,
    SITUACAO_EFETIVADO,
    SITUACAO_EM_DESLIGAMENTO,
)

# Colunas do board nesta entrega. Freelancer fica de fora ate a fase do banco de
# freelancers existir. Lista separada de SITUACOES de proposito: o que o board
# mostra e decisao de produto, o que a maquina aceita e decisao de dominio.
COLUNAS_BOARD = [
    SITUACAO_CADASTRO,
    SITUACAO_EM_ADMISSAO,
    SITUACAO_EM_EXPERIENCIA,
    SITUACAO_EFETIVADO,
    SITUACAO_EM_DESLIGAMENTO,
    SITUACAO_DESLIGADO,
]


# ── Os tres pontos de entrada (D1) ───────────────────────────────────────────
#
# A tela de origem tem o modal "esse colaborador ja comecou a trabalhar?", com
# tres saidas que entram no ciclo em fases diferentes. A spec descrevia o fluxo
# como linear (cadastro depois admissao depois experiencia), o que o proprio
# produto contradizia. Modelamos as tres portas explicitamente pra que o board
# nao dependa de uma linearidade que nao existe.

ENTRADA_SO_CADASTRO = 'so_cadastro'
ENTRADA_EM_ADMISSAO = 'em_admissao'
ENTRADA_JA_TRABALHANDO = 'ja_trabalhando'
ENTRADA_LINK_PUBLICO = 'link_publico'

PONTOS_ENTRADA = {
    ENTRADA_SO_CADASTRO:    SITUACAO_CADASTRO,
    ENTRADA_EM_ADMISSAO:    SITUACAO_EM_ADMISSAO,
    ENTRADA_JA_TRABALHANDO: SITUACAO_EM_EXPERIENCIA,
    # O auto cadastro sempre entra em Cadastro: quem preenche e o proprio
    # colaborador, e ele nao decide a propria fase.
    ENTRADA_LINK_PUBLICO:   SITUACAO_CADASTRO,
}

PONTOS_ENTRADA_CHOICES = [
    (ENTRADA_SO_CADASTRO,    'So cadastrar por enquanto'),
    (ENTRADA_EM_ADMISSAO,    'Ainda em admissao'),
    (ENTRADA_JA_TRABALHANDO, 'Ja esta trabalhando'),
    (ENTRADA_LINK_PUBLICO,   'Auto cadastro por link'),
]

SITUACOES_DE_ENTRADA = set(PONTOS_ENTRADA.values())


# ── Transicoes permitidas ────────────────────────────────────────────────────

TRANSICOES = {
    SITUACAO_CADASTRO: {
        SITUACAO_EM_ADMISSAO,
        SITUACAO_EM_EXPERIENCIA,
        SITUACAO_FREELANCER,
        # Cadastrado que nunca compareceu. Preserva a linha sem poluir o board.
        SITUACAO_DESLIGADO,
    },
    SITUACAO_EM_ADMISSAO: {
        SITUACAO_EM_EXPERIENCIA,
        # Empresa sem periodo de experiencia (PJ, por exemplo). Existe.
        SITUACAO_EFETIVADO,
        SITUACAO_EM_DESLIGAMENTO,
        SITUACAO_DESLIGADO,
        # Desfazer clique errado no modal de entrada. Sem esta aresta o RH
        # criaria uma segunda linha pra corrigir, que e exatamente a duplicata
        # que a regra de fonte unica proibe.
        SITUACAO_CADASTRO,
    },
    SITUACAO_EM_EXPERIENCIA: {
        # Auto transicao: prorrogacao. Ver nota abaixo.
        SITUACAO_EM_EXPERIENCIA,
        SITUACAO_EFETIVADO,
        SITUACAO_EM_DESLIGAMENTO,
        SITUACAO_DESLIGADO,
    },
    SITUACAO_EFETIVADO: {
        SITUACAO_EM_DESLIGAMENTO,
        SITUACAO_DESLIGADO,
        SITUACAO_FREELANCER,
    },
    SITUACAO_EM_DESLIGAMENTO: {
        SITUACAO_DESLIGADO,
        # Desligamento cancelado. Acontece, e sem estas duas arestas a pessoa
        # ficaria presa em "em desligamento" pra sempre.
        SITUACAO_EFETIVADO,
        SITUACAO_EM_EXPERIENCIA,
    },
    SITUACAO_DESLIGADO: {
        # Readmissao. E o que torna o soft delete util: a linha preservada e
        # reencontrada pelo dedup e reativada, em vez de virar cadastro novo.
        SITUACAO_CADASTRO,
        SITUACAO_EM_ADMISSAO,
        SITUACAO_EM_EXPERIENCIA,
        SITUACAO_FREELANCER,
    },
    SITUACAO_FREELANCER: {
        SITUACAO_EM_ADMISSAO,
        SITUACAO_EM_EXPERIENCIA,
        SITUACAO_EFETIVADO,
        SITUACAO_DESLIGADO,
    },
}

# D4, parte 1: `em_experiencia` e `efetivado` vao direto pra `desligado` sem
# passar por `em_desligamento`. O estado intermediario e um estacionamento
# opcional (aviso previo, processo em andamento), nao um pedagio. A spec tinha
# as duas propostas incompativeis: a saida da experiencia ia pra `desligado` e a
# entrada do desligamento vinha de `em_desligamento`.
#
# D4, parte 2: prorrogar NAO e estado, e a auto transicao
# `em_experiencia -> em_experiencia`. Uma coluna "Prorrogado" racharia a
# populacao "quem esta em experiencia" em duas, e toda consulta de RH, de
# alerta de vencimento e do futuro modulo de Feedback teria que lembrar de somar
# as duas. O card nao se move, que e o certo (a pessoa continua em experiencia),
# mas a transicao existe no historico e e contavel.


# ── Pre condicoes e efeitos por transicao ────────────────────────────────────
#
# Declarativo de proposito. A alternativa (if/elif dentro do servico) e onde
# regra de negocio vai morrer escondida.
#
#   exige:   campos que precisam estar preenchidos pra transicao valer
#   calcula: campos que o servico deriva ao entrar no estado
#   limpa:   campos zerados AO SAIR do estado (ver LIMPA_AO_SAIR)

EFEITOS = {
    SITUACAO_CADASTRO:        {},
    SITUACAO_EM_ADMISSAO:     {'exige': ['data_admissao']},
    SITUACAO_EM_EXPERIENCIA:  {'exige': ['data_admissao'],
                               'calcula': ['data_fim_experiencia']},
    SITUACAO_EFETIVADO:       {},
    SITUACAO_EM_DESLIGAMENTO: {'exige': ['motivo_desligamento']},
    SITUACAO_DESLIGADO:       {'exige': ['data_desligamento', 'motivo_desligamento']},
    SITUACAO_FREELANCER:      {},
}

# Excecoes ao `exige`, por par (origem, destino).
EXCECOES_EXIGE = {
    # Cadastrado que nunca compareceu: nao ha data de desligamento a pedir,
    # porque nao houve vinculo.
    (SITUACAO_CADASTRO, SITUACAO_DESLIGADO): [],
}

# Campos zerados ao SAIR de um estado. Readmissao e o caso real: sem isso a
# pessoa volta ativa carregando data e motivo do desligamento antigo, e a ficha
# fica dizendo duas coisas contraditorias. O valor antigo nao se perde, o
# servico o guarda no snapshot do HistoricoSituacao.
LIMPA_AO_SAIR = {
    SITUACAO_DESLIGADO: ['data_desligamento', 'motivo_desligamento'],
}

# Whitelist do que a transicao pode gravar, por destino.
#
# `mover_situacao(dados={...})` so aplica campo que esteja aqui. Sem essa
# barreira o parametro viraria um `save()` disfarcado, capaz de mexer em
# qualquer coluna do colaborador a pretexto de mudar de fase, e a guarda do
# model perderia o sentido.
CAMPOS_ACEITOS = {
    SITUACAO_CADASTRO:        [],
    SITUACAO_EM_ADMISSAO:     ['data_admissao', 'cargo', 'regime_contratacao'],
    SITUACAO_EM_EXPERIENCIA:  ['data_admissao', 'data_fim_experiencia',
                               'cargo', 'regime_contratacao'],
    SITUACAO_EFETIVADO:       ['cargo'],
    SITUACAO_EM_DESLIGAMENTO: ['motivo_desligamento', 'data_desligamento'],
    SITUACAO_DESLIGADO:       ['data_desligamento', 'motivo_desligamento',
                               'elegivel_recontratacao'],
    SITUACAO_FREELANCER:      ['elegivel_recontratacao'],
}


def campos_aceitos(para):
    """Campos que a transicao pra `para` pode gravar. Ver CAMPOS_ACEITOS."""
    return list(CAMPOS_ACEITOS.get(para, []))


# ── Consultas puras sobre a maquina ──────────────────────────────────────────

def rotulo(situacao):
    """Nome de exibicao da situacao."""
    return ROTULOS_SITUACAO.get(situacao, situacao)


def situacao_valida(situacao):
    return situacao in VALORES_SITUACAO


def transicao_permitida(de, para):
    """True se a maquina aceita ir de `de` pra `para`."""
    return para in TRANSICOES.get(de, set())


def validar_transicao(de, para):
    """Levanta TransicaoInvalida se a transicao nao existe."""
    if not situacao_valida(para):
        raise TransicaoInvalida(f'Situacao desconhecida: "{para}".')
    if not transicao_permitida(de, para):
        raise TransicaoInvalida(
            f'Transicao de "{rotulo(de)}" para "{rotulo(para)}" nao e permitida.'
        )


def campos_exigidos(de, para):
    """Campos que precisam estar preenchidos pra transicao valer."""
    if (de, para) in EXCECOES_EXIGE:
        return list(EXCECOES_EXIGE[(de, para)])
    return list(EFEITOS.get(para, {}).get('exige', []))


def campos_calculados(para):
    """Campos que o servico deriva ao entrar no estado."""
    return list(EFEITOS.get(para, {}).get('calcula', []))


def campos_a_limpar(de, para):
    """Campos zerados ao sair de `de`. Vazio quando a situacao nao muda."""
    if de == para:
        return []
    return list(LIMPA_AO_SAIR.get(de, []))


def situacao_de_entrada(ponto_entrada):
    """Situacao inicial correspondente ao ponto de entrada escolhido."""
    if ponto_entrada not in PONTOS_ENTRADA:
        raise TransicaoInvalida(f'Ponto de entrada desconhecido: "{ponto_entrada}".')
    return PONTOS_ENTRADA[ponto_entrada]


def eh_prorrogacao(de, para):
    """A unica auto transicao da maquina: prorrogar a experiencia."""
    return de == para == SITUACAO_EM_EXPERIENCIA


def destinos_possiveis(de):
    """Pra montar menu de acao na UI sem duplicar a regra no template."""
    return sorted(TRANSICOES.get(de, set()))
