"""
Testes da maquina de estados do People (`apps.people.estados`).

Modulo puro: nenhum teste aqui toca banco. Se algum precisar de
`@pytest.mark.django_db`, e sinal de que regra de dominio vazou pro ORM.

Alem dos casos obvios, aqui moram os testes que travam os tres defeitos que a
spec de origem mandava corrigir (D1, D2, D4). Sao eles que impedem a maquina de
regredir pro desenho antigo numa refatoracao distraida.
"""
import pytest

from apps.people import estados
from apps.people.excecoes import TransicaoInvalida


# ──────────────────────────────────────────────
# Coerencia da tabela
# ──────────────────────────────────────────────

def test_toda_situacao_tem_entrada_em_transicoes():
    faltando = [s for s in estados.VALORES_SITUACAO if s not in estados.TRANSICOES]
    assert not faltando, f'Situacoes sem transicao declarada: {faltando}'


def test_todo_destino_e_situacao_valida():
    for origem, destinos in estados.TRANSICOES.items():
        for destino in destinos:
            assert estados.situacao_valida(destino), \
                f'{origem} aponta pra situacao inexistente: {destino}'


def test_toda_situacao_tem_efeitos_declarados():
    faltando = [s for s in estados.VALORES_SITUACAO if s not in estados.EFEITOS]
    assert not faltando, f'Situacoes sem EFEITOS: {faltando}'


def test_colunas_do_board_sao_situacoes_validas():
    for coluna in estados.COLUNAS_BOARD:
        assert estados.situacao_valida(coluna)


def test_nenhuma_situacao_e_beco_sem_saida():
    """Toda situacao precisa ter pelo menos uma saida, senao a pessoa trava."""
    presas = [s for s in estados.VALORES_SITUACAO if not estados.TRANSICOES.get(s)]
    assert not presas, f'Situacoes sem saida: {presas}'


def test_toda_situacao_e_alcancavel_a_partir_de_um_ponto_de_entrada():
    """Estado que ninguem alcanca e estado morto. Pega orfao adicionado depois."""
    visitados = set(estados.SITUACOES_DE_ENTRADA)
    fila = list(visitados)
    while fila:
        atual = fila.pop()
        for destino in estados.TRANSICOES.get(atual, set()):
            if destino not in visitados:
                visitados.add(destino)
                fila.append(destino)

    orfas = set(estados.VALORES_SITUACAO) - visitados
    assert not orfas, f'Situacoes inalcancaveis: {orfas}'


def test_de_qualquer_situacao_se_chega_a_desligado():
    """Todo mundo precisa poder sair da empresa, de onde quer que esteja."""
    for inicial in estados.VALORES_SITUACAO:
        visitados = {inicial}
        fila = [inicial]
        while fila:
            atual = fila.pop()
            for destino in estados.TRANSICOES.get(atual, set()):
                if destino not in visitados:
                    visitados.add(destino)
                    fila.append(destino)
        assert estados.SITUACAO_DESLIGADO in visitados, \
            f'De "{inicial}" nao se chega a desligado'


# ──────────────────────────────────────────────
# D1: os tres pontos de entrada
# ──────────────────────────────────────────────

def test_existem_tres_portas_de_entrada_do_rh():
    """
    O modal "esse colaborador ja comecou a trabalhar?" tem 3 saidas, e elas
    entram no ciclo em fases diferentes. Se este teste quebrar porque alguem
    reduziu a um ponto de entrada, o board volta a assumir um fluxo linear que
    o produto nao tem.
    """
    portas_rh = {
        estados.ENTRADA_SO_CADASTRO,
        estados.ENTRADA_EM_ADMISSAO,
        estados.ENTRADA_JA_TRABALHANDO,
    }
    assert portas_rh <= set(estados.PONTOS_ENTRADA)

    destinos = {estados.situacao_de_entrada(p) for p in portas_rh}
    assert destinos == {
        estados.SITUACAO_CADASTRO,
        estados.SITUACAO_EM_ADMISSAO,
        estados.SITUACAO_EM_EXPERIENCIA,
    }


def test_link_publico_sempre_entra_em_cadastro():
    """Quem preenche o auto cadastro e o proprio colaborador, e ele nao decide
    a propria fase."""
    assert estados.situacao_de_entrada(estados.ENTRADA_LINK_PUBLICO) == \
        estados.SITUACAO_CADASTRO


def test_ponto_de_entrada_desconhecido_levanta():
    with pytest.raises(TransicaoInvalida):
        estados.situacao_de_entrada('pela_janela')


# ──────────────────────────────────────────────
# D4: prorrogacao e as saidas do desligamento
# ──────────────────────────────────────────────

def test_prorrogacao_e_a_unica_auto_transicao():
    """
    Prorrogar a experiencia nao e estado novo, e auto transicao. Uma coluna
    "Prorrogado" racharia a populacao "quem esta em experiencia" em duas, e toda
    consulta de RH e de alerta de vencimento teria que somar as duas.
    """
    auto = {s for s in estados.VALORES_SITUACAO if estados.transicao_permitida(s, s)}
    assert auto == {estados.SITUACAO_EM_EXPERIENCIA}
    assert estados.eh_prorrogacao(
        estados.SITUACAO_EM_EXPERIENCIA, estados.SITUACAO_EM_EXPERIENCIA)


def test_dispensa_na_experiencia_nao_precisa_passar_por_em_desligamento():
    """Metade do D4: em_desligamento e estacionamento opcional, nao pedagio."""
    assert estados.transicao_permitida(
        estados.SITUACAO_EM_EXPERIENCIA, estados.SITUACAO_DESLIGADO)
    assert estados.transicao_permitida(
        estados.SITUACAO_EFETIVADO, estados.SITUACAO_DESLIGADO)


def test_desligamento_pode_ser_cancelado():
    """Outra metade do D4: sem estas arestas a pessoa ficava presa em
    em_desligamento pra sempre."""
    assert estados.transicao_permitida(
        estados.SITUACAO_EM_DESLIGAMENTO, estados.SITUACAO_EFETIVADO)
    assert estados.transicao_permitida(
        estados.SITUACAO_EM_DESLIGAMENTO, estados.SITUACAO_EM_EXPERIENCIA)


def test_readmissao_sai_de_desligado():
    """O que torna o soft delete util: a linha preservada volta a circular."""
    for destino in (estados.SITUACAO_CADASTRO, estados.SITUACAO_EM_ADMISSAO,
                    estados.SITUACAO_EM_EXPERIENCIA, estados.SITUACAO_FREELANCER):
        assert estados.transicao_permitida(estados.SITUACAO_DESLIGADO, destino)


def test_desfazer_entrada_errada_no_modal():
    """Sem esta aresta o RH cria uma segunda linha pra corrigir, que e a
    duplicata que a regra de fonte unica proibe."""
    assert estados.transicao_permitida(
        estados.SITUACAO_EM_ADMISSAO, estados.SITUACAO_CADASTRO)


# ──────────────────────────────────────────────
# Validacao de transicao
# ──────────────────────────────────────────────

def test_transicao_valida_nao_levanta():
    estados.validar_transicao(estados.SITUACAO_CADASTRO, estados.SITUACAO_EM_ADMISSAO)


def test_transicao_invalida_levanta():
    # Nao se pula de cadastro direto pra efetivado sem passar por admissao ou
    # experiencia: nao houve vinculo pra efetivar.
    with pytest.raises(TransicaoInvalida):
        estados.validar_transicao(estados.SITUACAO_CADASTRO, estados.SITUACAO_EFETIVADO)


def test_transicao_pra_situacao_inexistente_levanta():
    with pytest.raises(TransicaoInvalida):
        estados.validar_transicao(estados.SITUACAO_CADASTRO, 'aposentado')


def test_auto_transicao_fora_da_experiencia_e_invalida():
    with pytest.raises(TransicaoInvalida):
        estados.validar_transicao(estados.SITUACAO_EFETIVADO, estados.SITUACAO_EFETIVADO)


# ──────────────────────────────────────────────
# Pre condicoes e limpeza
# ──────────────────────────────────────────────

def test_entrar_em_admissao_exige_data_admissao():
    exigidos = estados.campos_exigidos(
        estados.SITUACAO_CADASTRO, estados.SITUACAO_EM_ADMISSAO)
    assert 'data_admissao' in exigidos


def test_entrar_em_experiencia_exige_data_admissao_e_calcula_o_fim():
    assert 'data_admissao' in estados.campos_exigidos(
        estados.SITUACAO_EM_ADMISSAO, estados.SITUACAO_EM_EXPERIENCIA)
    assert 'data_fim_experiencia' in estados.campos_calculados(
        estados.SITUACAO_EM_EXPERIENCIA)


def test_desligar_exige_data_e_motivo():
    exigidos = estados.campos_exigidos(
        estados.SITUACAO_EFETIVADO, estados.SITUACAO_DESLIGADO)
    assert set(exigidos) == {'data_desligamento', 'motivo_desligamento'}


def test_cadastrado_que_nunca_compareceu_nao_exige_nada():
    """Excecao registrada: nao houve vinculo, entao nao ha data de
    desligamento a pedir."""
    assert estados.campos_exigidos(
        estados.SITUACAO_CADASTRO, estados.SITUACAO_DESLIGADO) == []


def test_sair_de_desligado_limpa_dados_do_desligamento():
    """
    Readmissao. Sem isso a pessoa volta ativa carregando data e motivo do
    desligamento antigo, e a ficha passa a dizer duas coisas contraditorias.
    """
    limpar = estados.campos_a_limpar(
        estados.SITUACAO_DESLIGADO, estados.SITUACAO_EM_EXPERIENCIA)
    assert set(limpar) == {'data_desligamento', 'motivo_desligamento'}


def test_prorrogacao_nao_limpa_nada():
    assert estados.campos_a_limpar(
        estados.SITUACAO_EM_EXPERIENCIA, estados.SITUACAO_EM_EXPERIENCIA) == []


def test_transicao_comum_nao_limpa_nada():
    assert estados.campos_a_limpar(
        estados.SITUACAO_CADASTRO, estados.SITUACAO_EM_ADMISSAO) == []


# ──────────────────────────────────────────────
# D2: vocabulario unico
# ──────────────────────────────────────────────

def test_vocabulario_nao_mistura_as_duas_geracoes_da_spec():
    """
    As fontes conviviam com dois vocabularios ("Processo Admissional" e "Em
    Admissao", "Efetivados" e "efetivado"). Aqui existe um so. Este teste
    trava a volta dos nomes antigos.
    """
    proibidos = {'processo_admissional', 'efetivados', 'desligados',
                 'experiencia', 'admissao'}
    assert not (set(estados.VALORES_SITUACAO) & proibidos)


def test_todo_valor_tem_rotulo_legivel():
    for valor in estados.VALORES_SITUACAO:
        assert estados.rotulo(valor) != valor, f'Sem rotulo: {valor}'


def test_destinos_possiveis_vem_ordenado():
    destinos = estados.destinos_possiveis(estados.SITUACAO_EM_ADMISSAO)
    assert destinos == sorted(destinos)
