"""
Testes do servico de cadastro: dedup, readmissao e transicao de fase.

E o coracao do modulo. A regra de fonte unica diz que todo fluxo que cria pessoa
precisa pesquisar antes, reutilizar quem existe, impedir duplicidade por
documento e nunca criar cadastro paralelo. Cada uma dessas quatro clausulas tem
teste aqui, e os casos hostis (corrida, CPF invalido, homonimo) tem mais.
"""
from datetime import date, timedelta

import pytest

from apps.people import estados
from apps.people.excecoes import CampoObrigatorioFaltando, TransicaoInvalida
from apps.people.models import Colaborador, HistoricoSituacao, Unidade
from apps.people.services import (
    buscar_colaborador, config_efetiva, mover_situacao, registrar_colaborador,
    unidade_sentinela,
)
from tests.factories import TenantFactory


@pytest.fixture
def unidade(db):
    tenant = TenantFactory()
    return Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro', codigo='loja-centro')


def _registrar(unidade, nome='Maria Souza', origem='rh', **dados):
    return registrar_colaborador(
        unidade.tenant, unidade, {'nome_completo': nome, **dados}, origem=origem,
    )


# CPFs com digito verificador valido, pra nao cair na fila de revisao sem querer
CPF_VALIDO = '52998224725'
CPF_VALIDO_2 = '15350946056'


# ──────────────────────────────────────────────
# Criacao
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_cria_quando_nao_existe(unidade):
    r = _registrar(unidade, cpf=CPF_VALIDO)
    assert r.acao == 'criado'
    assert r.ok
    assert r.colaborador.cpf == CPF_VALIDO
    assert r.colaborador.situacao == estados.SITUACAO_CADASTRO


@pytest.mark.django_db
def test_criacao_grava_historico_de_entrada(unidade):
    r = _registrar(unidade, cpf=CPF_VALIDO)
    hist = HistoricoSituacao.all_tenants.filter(colaborador=r.colaborador)
    assert hist.count() == 1
    assert hist.first().de == ''
    assert hist.first().para == estados.SITUACAO_CADASTRO


@pytest.mark.django_db
def test_normaliza_tudo_na_entrada(unidade):
    r = _registrar(
        unidade, nome='  Maria   da  Silva ', cpf='529.982.247-25',
        telefone='(86) 99999-8888', email='  Maria@EXEMPLO.com ',
        estado='pi', cep='64000000',
    )
    col = r.colaborador
    assert col.nome_completo == 'Maria da Silva'
    assert col.cpf == CPF_VALIDO
    assert col.telefone == '5586999998888'
    assert col.email == 'maria@exemplo.com'
    assert col.estado == 'PI'
    assert col.cep == '64000-000'


@pytest.mark.django_db
def test_campo_fora_da_whitelist_e_ignorado(unidade):
    """
    Um dos chamadores e formulario publico que qualquer um posta. Campo
    desconhecido nao pode virar atribuicao.
    """
    r = registrar_colaborador(
        unidade.tenant, unidade,
        {'nome_completo': 'Maria', 'situacao': 'efetivado', 'pendente_revisao': False,
         'elegivel_recontratacao': False},
        origem='link_publico',
    )
    assert r.colaborador.situacao == estados.SITUACAO_CADASTRO
    assert r.colaborador.elegivel_recontratacao is True


@pytest.mark.django_db
def test_nome_e_obrigatorio(unidade):
    with pytest.raises(ValueError):
        registrar_colaborador(unidade.tenant, unidade, {'cpf': CPF_VALIDO}, origem='rh')


@pytest.mark.django_db
def test_unidade_de_outro_tenant_e_recusada(unidade):
    outra = Unidade.all_tenants.create(
        tenant=TenantFactory(), nome='Outra', codigo='outra')
    with pytest.raises(ValueError):
        registrar_colaborador(
            unidade.tenant, outra, {'nome_completo': 'Maria'}, origem='rh')


@pytest.mark.django_db
def test_situacao_inicial_precisa_ser_ponto_de_entrada(unidade):
    """Ninguem nasce efetivado nem desligado."""
    with pytest.raises(TransicaoInvalida):
        registrar_colaborador(
            unidade.tenant, unidade, {'nome_completo': 'Maria'},
            origem='rh', situacao_inicial=estados.SITUACAO_EFETIVADO,
        )


# ──────────────────────────────────────────────
# Os tres pontos de entrada (D1)
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_entra_direto_em_admissao(unidade):
    r = registrar_colaborador(
        unidade.tenant, unidade,
        {'nome_completo': 'Maria', 'data_admissao': date(2026, 7, 1)},
        origem='rh', situacao_inicial=estados.SITUACAO_EM_ADMISSAO,
    )
    assert r.colaborador.situacao == estados.SITUACAO_EM_ADMISSAO
    assert r.colaborador.ponto_entrada == estados.ENTRADA_EM_ADMISSAO


@pytest.mark.django_db
def test_entra_direto_em_experiencia_ja_trabalhando(unidade):
    r = registrar_colaborador(
        unidade.tenant, unidade,
        {'nome_completo': 'Maria', 'data_admissao': date(2026, 7, 1)},
        origem='rh', situacao_inicial=estados.SITUACAO_EM_EXPERIENCIA,
    )
    assert r.colaborador.situacao == estados.SITUACAO_EM_EXPERIENCIA
    assert r.colaborador.ponto_entrada == estados.ENTRADA_JA_TRABALHANDO


@pytest.mark.django_db
def test_link_publico_marca_o_proprio_ponto_de_entrada(unidade):
    r = _registrar(unidade, origem='link_publico', cpf=CPF_VALIDO)
    assert r.colaborador.ponto_entrada == estados.ENTRADA_LINK_PUBLICO
    assert r.colaborador.origem_cadastro == 'link_publico'
    assert r.colaborador.situacao == estados.SITUACAO_CADASTRO


# ──────────────────────────────────────────────
# Dedup por CPF
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_mesmo_cpf_reaproveita_em_vez_de_criar(unidade):
    primeiro = _registrar(unidade, nome='Maria Souza', cpf=CPF_VALIDO)
    segundo = _registrar(unidade, nome='Maria Souza', cpf='529.982.247-25')

    assert segundo.acao == 'reaproveitado'
    assert segundo.colaborador.pk == primeiro.colaborador.pk
    assert Colaborador.all_tenants.filter(tenant=unidade.tenant).count() == 1


@pytest.mark.django_db
def test_reaproveitamento_preenche_lacuna(unidade):
    _registrar(unidade, nome='Maria', cpf=CPF_VALIDO)
    r = _registrar(unidade, nome='Maria', cpf=CPF_VALIDO,
                   email='maria@exemplo.com', rg='1234567')

    assert r.acao == 'reaproveitado'
    assert r.colaborador.email == 'maria@exemplo.com'
    assert r.colaborador.rg == '1234567'


@pytest.mark.django_db
def test_reaproveitamento_nao_sobrescreve_dado_do_rh(unidade):
    """
    A regra de ouro: o auto cadastro preenche lacuna, nunca sobrescreve. Quem
    esta com o celular na porta da loja nao tem autoridade sobre o cadastro que
    o RH ja conferiu.
    """
    _registrar(unidade, nome='Maria', cpf=CPF_VALIDO, email='conferido@rh.com')
    r = _registrar(unidade, nome='Maria', cpf=CPF_VALIDO,
                   origem='link_publico', email='digitado@errado.com')

    assert r.colaborador.email == 'conferido@rh.com'


@pytest.mark.django_db
def test_auto_cadastro_nao_mexe_em_campo_do_rh_nem_vazio(unidade):
    """Cargo, regime e data de admissao sao decisao do RH, nao do colaborador."""
    _registrar(unidade, nome='Maria', cpf=CPF_VALIDO)
    r = _registrar(unidade, nome='Maria', cpf=CPF_VALIDO, origem='link_publico',
                   cargo='Gerente', data_admissao=date(2026, 1, 1))

    assert r.colaborador.cargo == ''
    assert r.colaborador.data_admissao is None


@pytest.mark.django_db
def test_reaproveitamento_nao_muda_fase_nem_unidade(unidade):
    """
    Transferencia de loja tem decisao de gestor por tras. Nao pode acontecer
    como efeito colateral de alguem reenviar um formulario.
    """
    outra_loja = Unidade.all_tenants.create(
        tenant=unidade.tenant, nome='Loja Norte', codigo='loja-norte')
    primeiro = _registrar(unidade, cpf=CPF_VALIDO,
                          data_admissao=date(2026, 7, 1))
    mover_situacao(primeiro.colaborador, estados.SITUACAO_EM_ADMISSAO)

    r = registrar_colaborador(
        unidade.tenant, outra_loja, {'nome_completo': 'Maria', 'cpf': CPF_VALIDO},
        origem='link_publico',
    )
    assert r.acao == 'reaproveitado'
    assert r.colaborador.unidade_id == unidade.pk
    assert r.colaborador.situacao == estados.SITUACAO_EM_ADMISSAO


@pytest.mark.django_db
def test_pessoas_sem_cpf_nao_sao_confundidas(unidade):
    """Sem CPF e sem telefone, nao ha match. Duas pessoas, dois cadastros."""
    a = _registrar(unidade, nome='Joao Um')
    b = _registrar(unidade, nome='Joao Dois')
    assert a.acao == 'criado' and b.acao == 'criado'
    assert a.colaborador.pk != b.colaborador.pk


# ──────────────────────────────────────────────
# Match fraco: nunca resolve sozinho
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_telefone_igual_gera_conflito_e_nao_reaproveita(unidade):
    """
    Telefone se repete: familia, telefone da loja, numero reciclado pela
    operadora. Reaproveitar sozinho fundiria duas pessoas num cadastro so.
    """
    _registrar(unidade, nome='Maria Souza', telefone='86999998888')
    r = _registrar(unidade, nome='Joana Lima', telefone='(86) 99999-8888')

    assert r.acao == 'conflito'
    assert r.colaborador is None
    assert r.motivo_conflito == 'possivel_duplicata'
    assert r.conflitos[0].forca == 'fraco'
    assert r.conflitos[0].motivo == 'telefone'
    assert Colaborador.all_tenants.filter(tenant=unidade.tenant).count() == 1


@pytest.mark.django_db
def test_homonimo_com_mesma_data_de_nascimento_gera_conflito(unidade):
    _registrar(unidade, nome='Jose da Silva', data_nascimento=date(1990, 5, 20))
    r = _registrar(unidade, nome='JOSE DA SILVA', data_nascimento=date(1990, 5, 20))

    assert r.acao == 'conflito'
    assert r.conflitos[0].motivo == 'nome_nascimento'


@pytest.mark.django_db
def test_cpf_vence_o_match_fraco(unidade):
    """CPF diferente e pessoa diferente, mesmo com telefone igual."""
    _registrar(unidade, nome='Maria', cpf=CPF_VALIDO, telefone='86999998888')
    r = _registrar(unidade, nome='Joana', cpf=CPF_VALIDO_2, telefone='86999998888')

    assert r.acao == 'conflito'  # telefone levanta a mao
    # e o CPF diferente aparece como fraco, nao como forte
    assert all(c.forca == 'fraco' for c in r.conflitos)


@pytest.mark.django_db
def test_rh_resolve_conflito_apontando_a_pessoa(unidade):
    """`colaborador_id` e a resposta do RH a pergunta "e essa pessoa?"."""
    primeiro = _registrar(unidade, nome='Maria Souza', telefone='86999998888')
    r = registrar_colaborador(
        unidade.tenant, unidade,
        {'nome_completo': 'Maria S. Souza', 'telefone': '86999998888',
         'cpf': CPF_VALIDO},
        origem='rh', colaborador_id=primeiro.colaborador.pk,
    )
    assert r.acao == 'reaproveitado'
    assert r.colaborador.pk == primeiro.colaborador.pk
    assert r.colaborador.cpf == CPF_VALIDO


# ──────────────────────────────────────────────
# Readmissao
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_desligado_e_reativado_e_nao_duplicado(unidade):
    """
    O que torna o soft delete util. Sem isto, o ex colaborador que volta vira
    linha nova e todo relatorio historico dele se parte em dois.
    """
    primeiro = _registrar(unidade, nome='Maria', cpf=CPF_VALIDO,
                          data_admissao=date(2026, 1, 10))
    mover_situacao(primeiro.colaborador, estados.SITUACAO_DESLIGADO,
                   dados={'data_desligamento': date(2026, 6, 1),
                          'motivo_desligamento': 'pedido'})

    r = _registrar(unidade, nome='Maria', cpf=CPF_VALIDO)

    assert r.acao == 'reativado'
    assert r.colaborador.pk == primeiro.colaborador.pk
    assert r.colaborador.situacao == estados.SITUACAO_CADASTRO
    assert Colaborador.all_tenants.filter(tenant=unidade.tenant).count() == 1


@pytest.mark.django_db
def test_readmissao_limpa_dados_do_desligamento_anterior(unidade):
    """Senao a pessoa volta ativa com data de desligamento preenchida, e a
    ficha diz duas coisas contraditorias."""
    primeiro = _registrar(unidade, cpf=CPF_VALIDO, data_admissao=date(2026, 1, 10))
    mover_situacao(primeiro.colaborador, estados.SITUACAO_DESLIGADO,
                   dados={'data_desligamento': date(2026, 6, 1),
                          'motivo_desligamento': 'pedido'})

    r = _registrar(unidade, cpf=CPF_VALIDO)

    assert r.colaborador.data_desligamento is None
    assert r.colaborador.motivo_desligamento == ''


@pytest.mark.django_db
def test_readmissao_guarda_o_que_limpou_no_historico(unidade):
    """Limpar o campo nao pode significar perder a informacao."""
    primeiro = _registrar(unidade, cpf=CPF_VALIDO, data_admissao=date(2026, 1, 10))
    mover_situacao(primeiro.colaborador, estados.SITUACAO_DESLIGADO,
                   dados={'data_desligamento': date(2026, 6, 1),
                          'motivo_desligamento': 'pedido'})
    _registrar(unidade, cpf=CPF_VALIDO)

    readmissao = HistoricoSituacao.all_tenants.filter(
        colaborador=primeiro.colaborador, de=estados.SITUACAO_DESLIGADO).first()
    assert readmissao.dados['limpos']['data_desligamento'] == '2026-06-01'
    assert readmissao.dados['limpos']['motivo_desligamento'] == 'pedido'


@pytest.mark.django_db
def test_nao_elegivel_a_recontratacao_vira_conflito(unidade):
    """Politica do RH nao pode ser furada por um reenvio de formulario."""
    primeiro = _registrar(unidade, cpf=CPF_VALIDO, data_admissao=date(2026, 1, 10))
    mover_situacao(primeiro.colaborador, estados.SITUACAO_DESLIGADO,
                   dados={'data_desligamento': date(2026, 6, 1),
                          'motivo_desligamento': 'justa_causa',
                          'elegivel_recontratacao': False})

    r = _registrar(unidade, cpf=CPF_VALIDO)

    assert r.acao == 'conflito'
    assert r.motivo_conflito == 'nao_elegivel_recontratacao'
    assert r.colaborador is None


@pytest.mark.django_db
def test_reativacao_pode_ser_desligada_pelo_chamador(unidade):
    primeiro = _registrar(unidade, cpf=CPF_VALIDO, data_admissao=date(2026, 1, 10))
    mover_situacao(primeiro.colaborador, estados.SITUACAO_DESLIGADO,
                   dados={'data_desligamento': date(2026, 6, 1),
                          'motivo_desligamento': 'pedido'})

    r = registrar_colaborador(
        unidade.tenant, unidade, {'nome_completo': 'Maria', 'cpf': CPF_VALIDO},
        origem='rh', permitir_reativacao=False,
    )
    assert r.acao == 'conflito'
    assert r.motivo_conflito == 'reativacao_nao_permitida'


@pytest.mark.django_db
def test_readmissao_pode_mudar_de_loja(unidade):
    """Diferente do reaproveitamento: quem volta pode voltar em outra unidade."""
    outra = Unidade.all_tenants.create(
        tenant=unidade.tenant, nome='Loja Norte', codigo='loja-norte')
    primeiro = _registrar(unidade, cpf=CPF_VALIDO, data_admissao=date(2026, 1, 10))
    mover_situacao(primeiro.colaborador, estados.SITUACAO_DESLIGADO,
                   dados={'data_desligamento': date(2026, 6, 1),
                          'motivo_desligamento': 'pedido'})

    r = registrar_colaborador(
        unidade.tenant, outra, {'nome_completo': 'Maria', 'cpf': CPF_VALIDO},
        origem='rh')

    assert r.acao == 'reativado'
    assert r.colaborador.unidade_id == outra.pk


# ──────────────────────────────────────────────
# CPF invalido e fila de revisao
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_cpf_invalido_e_aceito_mas_cai_na_fila_de_revisao(unidade):
    """
    Bloquear no formulario publico faz a pessoa desistir e o RH cadastrar por
    fora, o que reintroduz a duplicata. CPF errado numa fila e melhor que
    cadastro paralelo.
    """
    r = _registrar(unidade, cpf='11111111111', origem='link_publico')
    assert r.acao == 'criado'
    assert r.colaborador.cpf_valido is False
    assert r.colaborador.pendente_revisao is True


@pytest.mark.django_db
def test_cpf_valido_nao_cai_na_fila(unidade):
    r = _registrar(unidade, cpf=CPF_VALIDO)
    assert r.colaborador.cpf_valido is True
    assert r.colaborador.pendente_revisao is False


@pytest.mark.django_db
def test_sem_cpf_cai_na_fila(unidade):
    r = _registrar(unidade, nome='Sem Documento')
    assert r.colaborador.pendente_revisao is True


# ──────────────────────────────────────────────
# buscar_colaborador
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_busca_encontra_desligado(unidade):
    """Encontrar quem saiu e o que permite readmitir em vez de duplicar."""
    primeiro = _registrar(unidade, cpf=CPF_VALIDO, data_admissao=date(2026, 1, 10))
    mover_situacao(primeiro.colaborador, estados.SITUACAO_DESLIGADO,
                   dados={'data_desligamento': date(2026, 6, 1),
                          'motivo_desligamento': 'pedido'})

    achados = buscar_colaborador(unidade.tenant, cpf=CPF_VALIDO)
    assert len(achados) == 1
    assert achados[0].forca == 'forte'


@pytest.mark.django_db
def test_busca_ordena_forte_antes_de_fraco(unidade):
    _registrar(unidade, nome='Com CPF', cpf=CPF_VALIDO)
    _registrar(unidade, nome='Com Telefone', telefone='86999998888')

    achados = buscar_colaborador(
        unidade.tenant, cpf=CPF_VALIDO, telefone='86999998888')
    assert [c.forca for c in achados] == ['forte', 'fraco']


@pytest.mark.django_db
def test_busca_nao_atravessa_tenant(unidade):
    outro = Unidade.all_tenants.create(
        tenant=TenantFactory(), nome='Outra Rede', codigo='outra-rede')
    _registrar(outro, nome='De Outro Tenant', cpf=CPF_VALIDO)

    assert buscar_colaborador(unidade.tenant, cpf=CPF_VALIDO) == []


# ──────────────────────────────────────────────
# mover_situacao
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_transicao_valida_grava_historico(unidade):
    r = _registrar(unidade, cpf=CPF_VALIDO)
    mover_situacao(r.colaborador, estados.SITUACAO_EM_ADMISSAO,
                   motivo='Documentos ok', dados={'data_admissao': date(2026, 7, 1)})

    col = Colaborador.all_tenants.get(pk=r.colaborador.pk)
    assert col.situacao == estados.SITUACAO_EM_ADMISSAO
    hist = HistoricoSituacao.all_tenants.filter(colaborador=col).order_by('-criado_em').first()
    assert hist.de == estados.SITUACAO_CADASTRO
    assert hist.motivo == 'Documentos ok'


@pytest.mark.django_db
def test_transicao_invalida_levanta(unidade):
    r = _registrar(unidade, cpf=CPF_VALIDO)
    with pytest.raises(TransicaoInvalida):
        mover_situacao(r.colaborador, estados.SITUACAO_EFETIVADO)


@pytest.mark.django_db
def test_transicao_sem_campo_exigido_e_recusada(unidade):
    """Entrar em admissao sem data de admissao enche o board de card que nunca
    vence, e o RH perde a confianca na tela."""
    r = _registrar(unidade, cpf=CPF_VALIDO)
    with pytest.raises(CampoObrigatorioFaltando) as erro:
        mover_situacao(r.colaborador, estados.SITUACAO_EM_ADMISSAO)
    assert 'data_admissao' in erro.value.campos


@pytest.mark.django_db
def test_transicao_recusada_nao_deixa_rastro(unidade):
    r = _registrar(unidade, cpf=CPF_VALIDO)
    try:
        mover_situacao(r.colaborador, estados.SITUACAO_EM_ADMISSAO)
    except CampoObrigatorioFaltando:
        pass

    col = Colaborador.all_tenants.get(pk=r.colaborador.pk)
    assert col.situacao == estados.SITUACAO_CADASTRO
    assert HistoricoSituacao.all_tenants.filter(colaborador=col).count() == 1


@pytest.mark.django_db
def test_mover_situacao_deixa_o_objeto_do_caller_atualizado(unidade):
    """
    Regressao. A transicao trabalha numa instancia travada por
    select_for_update, entao a instancia que o caller tem em maos fica velha e
    nao enxerga o que foi calculado nem o que foi limpo. Ler um campo dela
    depois devolvia o valor antigo, silenciosamente.
    """
    r = _registrar(unidade, cpf=CPF_VALIDO)
    col = r.colaborador

    mover_situacao(col, estados.SITUACAO_EM_EXPERIENCIA,
                   dados={'data_admissao': date(2026, 7, 1)})

    # sem reler do banco
    assert col.situacao == estados.SITUACAO_EM_EXPERIENCIA
    assert col.data_fim_experiencia is not None

    mover_situacao(col, estados.SITUACAO_DESLIGADO,
                   dados={'data_desligamento': date(2026, 8, 1),
                          'motivo_desligamento': 'pedido'})
    mover_situacao(col, estados.SITUACAO_CADASTRO, motivo='Readmissao')

    assert col.data_desligamento is None
    assert col.motivo_desligamento == ''


@pytest.mark.django_db
def test_dados_fora_da_whitelist_da_transicao_sao_ignorados(unidade):
    """`dados` nao pode virar um save() disfarcado."""
    r = _registrar(unidade, cpf=CPF_VALIDO)
    mover_situacao(r.colaborador, estados.SITUACAO_EM_ADMISSAO,
                   dados={'data_admissao': date(2026, 7, 1),
                          'nome_completo': 'Hackeado',
                          'pendente_revisao': False})

    col = Colaborador.all_tenants.get(pk=r.colaborador.pk)
    assert col.nome_completo != 'Hackeado'


@pytest.mark.django_db
def test_cadastrado_que_nunca_compareceu_desliga_sem_exigir_data(unidade):
    r = _registrar(unidade, cpf=CPF_VALIDO)
    mover_situacao(r.colaborador, estados.SITUACAO_DESLIGADO, motivo='Nao compareceu')

    col = Colaborador.all_tenants.get(pk=r.colaborador.pk)
    assert col.situacao == estados.SITUACAO_DESLIGADO


# ──────────────────────────────────────────────
# Experiencia e prorrogacao (D4)
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_entrar_em_experiencia_calcula_o_fim_do_primeiro_periodo(unidade):
    """
    Marca o fim do PRIMEIRO periodo (o 45 de um 45 mais 45), nao o total. E
    nesse marco que o gestor decide prorrogar, efetivar ou dispensar.
    """
    r = _registrar(unidade, cpf=CPF_VALIDO)
    mover_situacao(r.colaborador, estados.SITUACAO_EM_EXPERIENCIA,
                   dados={'data_admissao': date(2026, 7, 1)})

    col = Colaborador.all_tenants.get(pk=r.colaborador.pk)
    cfg = config_efetiva(unidade)
    assert col.data_fim_experiencia == date(2026, 7, 1) + timedelta(
        days=cfg.dias_primeiro_periodo_experiencia)


@pytest.mark.django_db
def test_override_da_unidade_muda_o_calculo(unidade):
    unidade.dias_primeiro_periodo_experiencia = 30
    unidade.save()

    r = _registrar(unidade, cpf=CPF_VALIDO)
    mover_situacao(r.colaborador, estados.SITUACAO_EM_EXPERIENCIA,
                   dados={'data_admissao': date(2026, 7, 1)})

    col = Colaborador.all_tenants.get(pk=r.colaborador.pk)
    assert col.data_fim_experiencia == date(2026, 7, 31)


@pytest.mark.django_db
def test_data_explicita_vence_o_calculo(unidade):
    """A operacao real tem excecao, e o servico nao pode ser mais esperto que
    o gestor."""
    r = _registrar(unidade, cpf=CPF_VALIDO)
    mover_situacao(r.colaborador, estados.SITUACAO_EM_EXPERIENCIA,
                   dados={'data_admissao': date(2026, 7, 1),
                          'data_fim_experiencia': date(2026, 9, 30)})

    col = Colaborador.all_tenants.get(pk=r.colaborador.pk)
    assert col.data_fim_experiencia == date(2026, 9, 30)


@pytest.mark.django_db
def test_prorrogacao_nao_move_o_card_e_empurra_a_data(unidade):
    """
    A pessoa continua em experiencia, entao o card nao se move. Mas a
    transicao existe, incrementa o contador e vai pro historico.
    """
    r = _registrar(unidade, cpf=CPF_VALIDO)
    mover_situacao(r.colaborador, estados.SITUACAO_EM_EXPERIENCIA,
                   dados={'data_admissao': date(2026, 7, 1)})
    col = Colaborador.all_tenants.get(pk=r.colaborador.pk)
    primeiro_fim = col.data_fim_experiencia

    mover_situacao(col, estados.SITUACAO_EM_EXPERIENCIA, motivo='Prorrogado')

    col = Colaborador.all_tenants.get(pk=col.pk)
    cfg = config_efetiva(unidade)
    assert col.situacao == estados.SITUACAO_EM_EXPERIENCIA
    assert col.prorrogacoes_experiencia == 1
    assert col.data_fim_experiencia > primeiro_fim
    assert col.data_fim_experiencia == date(2026, 7, 1) + timedelta(
        days=cfg.dias_experiencia_padrao)


@pytest.mark.django_db
def test_prorrogacao_aparece_no_historico(unidade):
    r = _registrar(unidade, cpf=CPF_VALIDO)
    mover_situacao(r.colaborador, estados.SITUACAO_EM_EXPERIENCIA,
                   dados={'data_admissao': date(2026, 7, 1)})
    col = Colaborador.all_tenants.get(pk=r.colaborador.pk)
    mover_situacao(col, estados.SITUACAO_EM_EXPERIENCIA, motivo='Prorrogado')

    hist = HistoricoSituacao.all_tenants.filter(
        colaborador=col, de=estados.SITUACAO_EM_EXPERIENCIA,
        para=estados.SITUACAO_EM_EXPERIENCIA).first()
    assert hist is not None
    assert hist.dados['prorrogacao'] == 1


@pytest.mark.django_db
def test_nova_experiencia_zera_o_contador_de_prorrogacao(unidade):
    """Readmitido comeca experiencia do zero, nao herda prorrogacao antiga."""
    r = _registrar(unidade, cpf=CPF_VALIDO)
    col = r.colaborador
    mover_situacao(col, estados.SITUACAO_EM_EXPERIENCIA,
                   dados={'data_admissao': date(2026, 7, 1)})
    col = Colaborador.all_tenants.get(pk=col.pk)
    mover_situacao(col, estados.SITUACAO_EM_EXPERIENCIA)
    col = Colaborador.all_tenants.get(pk=col.pk)
    assert col.prorrogacoes_experiencia == 1

    mover_situacao(col, estados.SITUACAO_DESLIGADO,
                   dados={'data_desligamento': date(2026, 8, 1),
                          'motivo_desligamento': 'pedido'})
    col = Colaborador.all_tenants.get(pk=col.pk)
    mover_situacao(col, estados.SITUACAO_EM_EXPERIENCIA,
                   dados={'data_admissao': date(2026, 9, 1)})

    col = Colaborador.all_tenants.get(pk=col.pk)
    assert col.prorrogacoes_experiencia == 0


# ──────────────────────────────────────────────
# Unidade sentinela
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_sentinela_serve_de_fallback_pra_quem_nao_sabe_a_loja(unidade):
    """Recrutamento vai precisar criar pessoa antes de saber a unidade."""
    sentinela = unidade_sentinela(unidade.tenant)
    r = registrar_colaborador(
        unidade.tenant, sentinela, {'nome_completo': 'Candidato Aprovado'},
        origem='api')
    assert r.acao == 'criado'
    assert r.colaborador.unidade_id == sentinela.pk
