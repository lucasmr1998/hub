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

ETAPAS_PADRAO = [
    {'nome': 'Triagem',             'ordem': 1, 'sla_dias': 3},
    {'nome': 'Histórico',           'ordem': 2, 'sla_dias': 3},
    {'nome': 'Teste Comportamental', 'ordem': 3, 'sla_dias': 5},
    {'nome': 'Seleção',             'ordem': 4, 'sla_dias': 5},
    {'nome': 'Teste prático',       'ordem': 5, 'sla_dias': 5},
    {'nome': 'Avaliação Gestor',    'ordem': 6, 'sla_dias': 3},
    {'nome': 'Admissão',            'ordem': 7, 'sla_dias': 5},
]


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
