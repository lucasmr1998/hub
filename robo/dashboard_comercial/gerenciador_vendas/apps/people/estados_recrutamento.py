"""
A maquina de estados do pipeline de Recrutamento e Selecao.

DIFERENCA IMPORTANTE EM RELACAO A `estados.py`, e o motivo de existir um modulo
separado em vez de mais estados no mesmo arquivo:

No Departamento Pessoal a maquina e FIXA. As situacoes do colaborador estao em
codigo, sao as mesmas pra todo tenant, e essa rigidez e proposital: fase de
vinculo trabalhista nao e preferencia de cliente.

Aqui nao. As etapas do pipeline sao CONFIGURAVEIS por unidade: ordenaveis,
ligaveis e desligaveis. A spec de origem cita uma rede nos EUA rodando so
`triagem, entrevista com RH, admissao`, contra as sete etapas do default
brasileiro. Etapa de processo seletivo E preferencia de cliente.

Entao a divisao aqui e:

    ETAPA INTERMEDIARIA  ->  DADO      (model EtapaPipeline, por unidade)
    SAIDA TERMINAL       ->  CODIGO    (este arquivo)

O criterio nao e arbitrario: **saida tem comportamento**. `admitido` aciona a
ponte pro DP, `banco_talentos` entra na politica de retencao com expurgo
automatico, `inapto` e decisao registrada. Comportamento nao vai pra tabela de
configuracao, senao o cliente consegue criar um estado que o codigo nao sabe
tratar, e a descoberta disso acontece em producao.

Etapa, por outro lado, so ordena e nomeia. Nao tem comportamento. Por isso pode
ser dado.

Python puro de proposito, sem import de Django, no mesmo padrao de `estados.py`.
"""
from apps.people.excecoes import CampoObrigatorioFaltando, TransicaoInvalida


# ── Saidas terminais ─────────────────────────────────────────────────────────

SAIDA_ADMITIDO = 'admitido'
SAIDA_BANCO_TALENTOS = 'banco_talentos'
SAIDA_INAPTO = 'inapto'
SAIDA_ARQUIVADO = 'arquivado'

SAIDAS = [
    (SAIDA_ADMITIDO,        'Admitido'),
    (SAIDA_BANCO_TALENTOS,  'Banco de talentos'),
    (SAIDA_INAPTO,          'Inapto'),
    (SAIDA_ARQUIVADO,       'Arquivado'),
]

VALORES_SAIDA = [valor for valor, _ in SAIDAS]
ROTULOS_SAIDA = dict(SAIDAS)

# Todas exigem motivo. A spec marca isto como coluna real observada em demo que
# ficou de fora da especificacao escrita: "O campo motivo nao existe em nenhum
# dos contratos de conclusao dos manifests. E uma coluna real. Modele-a."
#
# Sem motivo obrigatorio o board vira cemiterio: seis meses depois ninguem sabe
# por que aquele candidato foi pro banco, e a analise de funil nao tem o que
# dizer alem de contagem.
SAIDAS_EXIGEM_MOTIVO = tuple(VALORES_SAIDA)

# Saida da qual o candidato PODE voltar pro pipeline.
#
# Reaproveitar quem foi pro banco e literalmente o produto ("guarda quem nao foi
# contratado num banco de talentos reaproveitavel"). Inapto e arquivado voltam
# porque clique errado acontece, e a alternativa e o RH cadastrar a pessoa de
# novo, que e a duplicata que a constraint de WhatsApp existe pra impedir.
SAIDAS_REABRIVEIS = (SAIDA_BANCO_TALENTOS, SAIDA_INAPTO, SAIDA_ARQUIVADO)

# `admitido` fica de fora da lista acima com uma ressalva que o servico
# implementa: enquanto NAO houver colaborador vinculado, voltar e so desfazer um
# clique e deve ser permitido. Depois que a ponte pro DP rodou e existe um
# Colaborador apontando pra este candidato, voltar deixaria uma pessoa
# contratada pendurada num pipeline, entao ai trava.
#
# A regra vive no servico e nao aqui porque depende do objeto (tem colaborador
# vinculado?), e este modulo e puro. Ver `pode_reabrir()`.
SAIDA_QUE_VINCULA_COLABORADOR = SAIDA_ADMITIDO


# ── Etapas padrao entregues prontas ──────────────────────────────────────────
#
# O cliente recebe isto configurado e personaliza. Sao DADO inicial, nao regra:
# viram linhas de EtapaPipeline no seed e a partir dai o tenant manda.
#
# A ordem e a da spec de origem. "Admissao" aqui e a etapa em que o processo de
# admissao esta acontecendo, e nao se confunde com a saida `admitido`, que e o
# desfecho. Mesma distincao que o DP faz entre `em_admissao` e estar contratado.

# ── Blocos que uma etapa pode ter na ficha do candidato ──────────────────────
#
# Cada bloco FAZ alguma coisa, e por isso e codigo e nao dado. E o mesmo criterio
# que separa etapa de saida neste modulo: comportamento fica em codigo, nomeacao
# e ordem ficam em tabela.
#
# QUAL etapa usa QUAIS blocos e escolha do cliente (EtapaPipeline.blocos), e e o
# que permite copiar a estrutura da origem sem chumbar o pipeline dela: as sete
# etapas padrao ja nascem com os blocos que a Visio mostra em cada aba, e quem
# criar uma etapa nova escolhe os dela.
BLOCO_ANALISE_IA = 'analise_ia'
BLOCO_ROTEIRO = 'roteiro'
BLOCO_CHECKLIST = 'checklist'
BLOCO_AGENDAMENTO = 'agendamento'
BLOCO_DECISAO = 'decisao'
BLOCO_ADMISSAO = 'admissao'
BLOCO_ANOTACAO = 'anotacao'
BLOCO_MENSAGEM = 'mensagem'

BLOCOS = [
    (BLOCO_ANALISE_IA,   'Análise por IA',
     'Avalia o candidato contra os requisitos de triagem da vaga.'),
    (BLOCO_ROTEIRO,      'Roteiro da conversa',
     'Perguntas para guiar a entrevista, marcadas conforme você pergunta.'),
    (BLOCO_CHECKLIST,    'Requisitos a validar',
     'Itens objetivos que precisam ser confirmados com o candidato.'),
    (BLOCO_AGENDAMENTO,  'Agendamento',
     'Data e local, que alimentam a mensagem enviada ao candidato.'),
    (BLOCO_DECISAO,      'Decisão',
     'Aprovar ou reprovar, com comentário.'),
    (BLOCO_ADMISSAO,     'Admissão',
     'Cria a ficha de colaborador e encerra o processo seletivo.'),
    (BLOCO_ANOTACAO,     'Anotações',
     'Texto livre sobre o que aconteceu nesta etapa.'),
    (BLOCO_MENSAGEM,     'Mensagem de WhatsApp',
     'Abre o WhatsApp com a mensagem configurada para esta etapa.'),
]

VALORES_BLOCOS = [chave for chave, _, _ in BLOCOS]
ROTULOS_BLOCO = {chave: rotulo for chave, rotulo, _ in BLOCOS}


ETAPAS_PADRAO = [
    # Os `blocos` de cada etapa espelham o que a origem mostra em cada aba. Sao
    # DEFAULT, e nao regra: o cliente muda em /people/fluxo/.
    {'nome': 'Triagem', 'ordem': 1, 'sla_dias': 3, 'cor': 'ambar',
     'blocos': [BLOCO_ANALISE_IA, BLOCO_ANOTACAO, BLOCO_MENSAGEM]},

    {'nome': 'Histórico', 'ordem': 2, 'sla_dias': 3, 'cor': 'azul',
     'blocos': [BLOCO_CHECKLIST, BLOCO_ANOTACAO]},

    {'nome': 'Teste Comportamental', 'ordem': 3, 'sla_dias': 5, 'cor': 'ciano',
     'blocos': [BLOCO_ANOTACAO, BLOCO_MENSAGEM]},

    # A "Entrevista RH" da origem: analise da IA, roteiro da conversa,
    # requisitos a validar e notas, tudo numa aba so.
    {'nome': 'Seleção', 'ordem': 4, 'sla_dias': 5, 'cor': 'laranja',
     'blocos': [BLOCO_ANALISE_IA, BLOCO_ROTEIRO, BLOCO_CHECKLIST,
                BLOCO_ANOTACAO, BLOCO_MENSAGEM]},

    {'nome': 'Teste prático', 'ordem': 5, 'sla_dias': 5, 'cor': 'azul',
     'blocos': [BLOCO_AGENDAMENTO, BLOCO_ANOTACAO, BLOCO_MENSAGEM]},

    {'nome': 'Avaliação Gestor', 'ordem': 6, 'sla_dias': 3, 'cor': 'roxo',
     'blocos': [BLOCO_DECISAO, BLOCO_ANOTACAO]},

    {'nome': 'Admissão', 'ordem': 7, 'sla_dias': 5, 'cor': 'verde',
     'blocos': [BLOCO_ADMISSAO, BLOCO_MENSAGEM]},
]

# Roteiro que a origem usa na entrevista. Vem preenchido pra a etapa nao nascer
# vazia, e e EDITAVEL: numa vaga de tecnico de campo as perguntas sao outras.
ROTEIRO_PADRAO = [
    'Me fale um pouco sobre você (quem é, rotina, família)',
    'Quais foram suas duas últimas experiências de trabalho? Por que saiu?',
    'Está trabalhando atualmente?',
    'Onde mora? Qual o tempo de deslocamento até o trabalho?',
    'Tem compromissos que podem impactar o horário de trabalho?',
    'Pretensão salarial',
    'Disponibilidade de horário (turnos, fins de semana, feriados)',
]

CHECKLIST_PADRAO = [
    'Disponibilidade para a escala da vaga',
    'Locomoção até o local de trabalho',
    'Idade mínima exigida para a função',
    'Documentação básica para admissão',
]

# Paleta das etapas. Chave em vez de hex no banco: se a identidade visual mudar,
# muda aqui e vale pra todo tenant, em vez de ficar hex velho gravado em linha
# de cliente. A tela de configuracao oferece estas.
CORES_ETAPA = [
    ('ambar',   'Âmbar',   '#F59E0B'),
    ('azul',    'Azul',    '#3B82F6'),
    ('ciano',   'Ciano',   '#06B6D4'),
    ('laranja', 'Laranja', '#F97316'),
    ('roxo',    'Roxo',    '#8B5CF6'),
    ('verde',   'Verde',   '#10B981'),
    ('rosa',    'Rosa',    '#EC4899'),
    ('cinza',   'Cinza',   '#6B7280'),
]

HEX_POR_COR = {chave: hexa for chave, _, hexa in CORES_ETAPA}
CORES_CHOICES = [(chave, rotulo) for chave, rotulo, _ in CORES_ETAPA]


def hex_da_cor(chave, ordem=0):
    """
    Hex da cor da etapa. Sem cor definida, deriva da ordem, pra que um pipeline
    novo ja nasca colorido em vez de cinza uniforme.
    """
    if chave in HEX_POR_COR:
        return HEX_POR_COR[chave]
    return CORES_ETAPA[(max(ordem, 1) - 1) % len(CORES_ETAPA)][2]


# Cor de cada saida. Fixas junto com as saidas, porque saida e codigo.
COR_DA_SAIDA = {
    SAIDA_ADMITIDO:       '#10B981',
    SAIDA_BANCO_TALENTOS: '#06B6D4',
    SAIDA_INAPTO:         '#EF4444',
    SAIDA_ARQUIVADO:      '#6B7280',
}


# ── Status da vaga ───────────────────────────────────────────────────────────
#
# Repare no contraste com as etapas do pipeline logo acima: ali o vocabulario e
# configuravel por unidade, aqui e FIXO em codigo. A diferenca nao e incoerencia.
# Etapa de processo seletivo e preferencia de cliente; ciclo de vida de uma vaga
# nao e. Vaga publicada aceita candidatura e vaga encerrada nao, e isso e regra
# do produto em qualquer rede.
#
# O fluxo de APROVACAO de vaga (aguardando aprovacao, aprovada, rejeitada) existe
# no produto de origem, porem foi classificado la como edge case de rede grande e
# esta formalmente deferido. Nao entra aqui. Se entrar depois, entra como estado
# ANTES de rascunho, sem mexer nos de baixo.

STATUS_VAGA_RASCUNHO = 'rascunho'
STATUS_VAGA_PUBLICADA = 'publicada'
STATUS_VAGA_PAUSADA = 'pausada'
STATUS_VAGA_ENCERRADA = 'encerrada'

STATUS_VAGA = [
    (STATUS_VAGA_RASCUNHO,  'Rascunho'),
    (STATUS_VAGA_PUBLICADA, 'Publicada'),
    (STATUS_VAGA_PAUSADA,   'Pausada'),
    (STATUS_VAGA_ENCERRADA, 'Encerrada'),
]

VALORES_STATUS_VAGA = [valor for valor, _ in STATUS_VAGA]
ROTULOS_STATUS_VAGA = dict(STATUS_VAGA)

# So vaga publicada recebe candidatura. Pausada guarda o que ja chegou e para de
# aceitar, que e o caso real de "temos candidato demais, segura um pouco".
STATUS_VAGA_ACEITA_CANDIDATURA = (STATUS_VAGA_PUBLICADA,)

TRANSICOES_VAGA = {
    STATUS_VAGA_RASCUNHO:  {STATUS_VAGA_PUBLICADA, STATUS_VAGA_ENCERRADA},
    STATUS_VAGA_PUBLICADA: {STATUS_VAGA_PAUSADA, STATUS_VAGA_ENCERRADA},
    STATUS_VAGA_PAUSADA:   {STATUS_VAGA_PUBLICADA, STATUS_VAGA_ENCERRADA},
    # Encerrada e final. Reabrir viraria uma vaga com duas janelas de captacao e
    # um funil que soma periodos diferentes como se fossem um. Pra recontratar,
    # abre vaga nova, que e o registro honesto de que e outro processo.
    STATUS_VAGA_ENCERRADA: set(),
}


def rotulo_status_vaga(status):
    return ROTULOS_STATUS_VAGA.get(status, status)


def transicao_vaga_permitida(de, para):
    return para in TRANSICOES_VAGA.get(de, set())


def validar_transicao_vaga(de, para):
    """Levanta TransicaoInvalida se a vaga nao pode ir de `de` pra `para`."""
    if para not in VALORES_STATUS_VAGA:
        raise TransicaoInvalida(f'Status de vaga desconhecido: "{para}".')
    if not transicao_vaga_permitida(de, para):
        if de == STATUS_VAGA_ENCERRADA:
            raise TransicaoInvalida(
                'Vaga encerrada nao reabre. Reabrir juntaria duas janelas de '
                'captacao no mesmo funil. Abra uma vaga nova.'
            )
        raise TransicaoInvalida(
            f'Vaga nao pode ir de "{rotulo_status_vaga(de)}" para '
            f'"{rotulo_status_vaga(para)}".'
        )


# ── Consultas puras ──────────────────────────────────────────────────────────

def rotulo_saida(saida):
    """Nome de exibicao da saida."""
    return ROTULOS_SAIDA.get(saida, saida)


def saida_valida(saida):
    return saida in VALORES_SAIDA


def exige_motivo(saida):
    """Toda saida exige motivo. Funcao existe pra a regra ter um nome so."""
    return saida in SAIDAS_EXIGEM_MOTIVO


def pode_reabrir(saida, *, tem_colaborador_vinculado=False):
    """
    O candidato nesta saida pode voltar pro pipeline?

    `tem_colaborador_vinculado` e o que separa "cliquei errado em admitido" de
    "esta pessoa ja e funcionaria". O primeiro tem que ser reversivel, senao o
    RH corrige criando um segundo candidato. O segundo nao, senao fica um
    colaborador ativo apontando pra um candidato que voltou pra Triagem.
    """
    if saida == SAIDA_QUE_VINCULA_COLABORADOR:
        return not tem_colaborador_vinculado
    return saida in SAIDAS_REABRIVEIS


def validar_saida(saida, motivo):
    """
    Levanta se a saida nao existe ou se falta motivo.

    A etapa de DESTINO nao e validada aqui: etapa e dado, entao quem confere se
    ela existe, esta ativa e pertence a unidade certa e o servico, contra o
    banco. Este modulo so responde pelo que e regra de dominio.
    """
    if not saida_valida(saida):
        raise TransicaoInvalida(f'Saida desconhecida: "{saida}".')
    if exige_motivo(saida) and not (motivo or '').strip():
        raise CampoObrigatorioFaltando(
            ['motivo_saida'], 'pipeline', rotulo_saida(saida))


def validar_reabertura(saida, *, tem_colaborador_vinculado=False):
    """Levanta se o candidato nesta saida nao pode voltar pro pipeline."""
    if not pode_reabrir(saida, tem_colaborador_vinculado=tem_colaborador_vinculado):
        if saida == SAIDA_QUE_VINCULA_COLABORADOR:
            raise TransicaoInvalida(
                'Este candidato ja virou colaborador. Reabrir deixaria uma '
                'pessoa contratada dentro do processo seletivo. Se a contratacao '
                'foi desfeita, o caminho e desligar pelo Departamento Pessoal.'
            )
        raise TransicaoInvalida(
            f'Nao e possivel reabrir a partir de "{rotulo_saida(saida)}".')
