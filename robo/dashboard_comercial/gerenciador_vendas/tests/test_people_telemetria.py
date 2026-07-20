"""
Testes da telemetria do People.

A spec de origem nao tinha nenhum evento instrumentado, entao aqui a exigencia e
maior que o normal: nao basta emitir, precisa emitir a coisa certa, uma vez so,
sem vazar documento, e sem derrubar a operacao quando o canal falha.
"""
from datetime import date

import pytest

from apps.automacao.eventos import EVENTOS
from apps.people import estados, telemetria
from apps.people.models import Cargo, Unidade
from apps.people.services import mover_situacao, registrar_colaborador
from apps.sistema.models import LogSistema
from tests.factories import TenantFactory


CPF_VALIDO = '52998224725'
CPF_VALIDO_2 = '15350946056'


@pytest.fixture
def unidade(db):
    tenant = TenantFactory()
    return Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro', codigo='loja-centro')


@pytest.fixture
def eventos_capturados(monkeypatch):
    """Intercepta o hub da automacao pra ver o que foi disparado."""
    capturados = []

    def falso_disparar(evento, contexto=None, tenant=None):
        capturados.append({'evento': evento, 'contexto': contexto or {}, 'tenant': tenant})

    monkeypatch.setattr('apps.automacao.hub.disparar_evento', falso_disparar)
    return capturados


def _registrar(unidade, nome='Maria Souza', origem='rh', **dados):
    return registrar_colaborador(
        unidade.tenant, unidade, {'nome_completo': nome, **dados}, origem=origem)


def _logs(tenant, acao=None):
    qs = LogSistema.all_tenants.filter(tenant=tenant, categoria='people')
    return qs.filter(acao=acao) if acao else qs


# ──────────────────────────────────────────────
# Emissao basica
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_cadastro_emite_evento_de_criacao(unidade, eventos_capturados):
    _registrar(unidade, cpf=CPF_VALIDO)
    nomes = [e['evento'] for e in eventos_capturados]
    assert telemetria.EVENTO_CRIADO in nomes


@pytest.mark.django_db
def test_cadastro_grava_log_na_categoria_people(unidade):
    """
    Sem a categoria registrada em LogSistema.CATEGORIA_CHOICES, o log gravaria
    mas ficaria fora do filtro de /aurora-admin/logs/, o que e pior que nao
    gravar: da falsa sensacao de instrumentacao.
    """
    r = _registrar(unidade, cpf=CPF_VALIDO)
    log = _logs(unidade.tenant, acao='criado').first()
    assert log is not None
    assert log.entidade == 'colaborador'
    assert log.entidade_id == r.colaborador.pk
    assert log.dados_extras['evento'] == telemetria.EVENTO_CRIADO


@pytest.mark.django_db
def test_categoria_people_esta_nos_choices():
    valores = [v for v, _ in LogSistema.CATEGORIA_CHOICES]
    assert 'people' in valores


@pytest.mark.django_db
def test_transicao_emite_o_evento_da_fase(unidade, eventos_capturados):
    r = _registrar(unidade, cpf=CPF_VALIDO)
    eventos_capturados.clear()

    mover_situacao(r.colaborador, estados.SITUACAO_EM_ADMISSAO,
                   dados={'data_admissao': date(2026, 7, 1)})

    assert [e['evento'] for e in eventos_capturados] == [
        telemetria.EVENTO_ADMISSAO_INICIADA]


@pytest.mark.django_db
def test_prorrogacao_tem_evento_proprio(unidade, eventos_capturados):
    """
    A situacao nao muda na prorrogacao. Sem evento proprio, o unico registro de
    que a experiencia foi esticada seria o contador, e ninguem conseguiria
    montar alerta em cima disso.
    """
    r = _registrar(unidade, cpf=CPF_VALIDO)
    mover_situacao(r.colaborador, estados.SITUACAO_EM_EXPERIENCIA,
                   dados={'data_admissao': date(2026, 7, 1)})
    eventos_capturados.clear()

    mover_situacao(r.colaborador, estados.SITUACAO_EM_EXPERIENCIA, motivo='Prorrogado')

    assert [e['evento'] for e in eventos_capturados] == [
        telemetria.EVENTO_EXPERIENCIA_PRORROGADA]


@pytest.mark.django_db
def test_transicao_recusada_nao_emite(unidade, eventos_capturados):
    from apps.people.excecoes import CampoObrigatorioFaltando

    r = _registrar(unidade, cpf=CPF_VALIDO)
    eventos_capturados.clear()

    with pytest.raises(CampoObrigatorioFaltando):
        mover_situacao(r.colaborador, estados.SITUACAO_EM_ADMISSAO)

    assert eventos_capturados == []


# ──────────────────────────────────────────────
# Dedup: um acontecimento, um evento
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_reaproveitamento_emite_evento_proprio(unidade, eventos_capturados):
    _registrar(unidade, cpf=CPF_VALIDO)
    eventos_capturados.clear()

    _registrar(unidade, cpf=CPF_VALIDO, origem='link_publico')

    assert [e['evento'] for e in eventos_capturados] == [
        telemetria.EVENTO_REAPROVEITADO]


@pytest.mark.django_db
def test_readmissao_emite_um_evento_so(unidade, eventos_capturados):
    """
    Readmissao envolve uma transicao de fase por baixo, mas e UM acontecimento.
    Emitir "readmitido" e "voltou pra cadastro" pro mesmo ato poluiria o log e o
    editor de fluxos, e faria qualquer contagem dobrar.
    """
    primeiro = _registrar(unidade, cpf=CPF_VALIDO, data_admissao=date(2026, 1, 10))
    mover_situacao(primeiro.colaborador, estados.SITUACAO_DESLIGADO,
                   dados={'data_desligamento': date(2026, 6, 1),
                          'motivo_desligamento': 'pedido'})
    eventos_capturados.clear()

    r = _registrar(unidade, cpf=CPF_VALIDO)

    assert r.acao == 'reativado'
    assert [e['evento'] for e in eventos_capturados] == [
        telemetria.EVENTO_READMITIDO]


@pytest.mark.django_db
def test_readmissao_carrega_a_transicao_no_contexto(unidade, eventos_capturados):
    """O evento e um so, mas nao pode perder a informacao dos dois."""
    primeiro = _registrar(unidade, cpf=CPF_VALIDO, data_admissao=date(2026, 1, 10))
    mover_situacao(primeiro.colaborador, estados.SITUACAO_DESLIGADO,
                   dados={'data_desligamento': date(2026, 6, 1),
                          'motivo_desligamento': 'pedido'})
    eventos_capturados.clear()

    _registrar(unidade, cpf=CPF_VALIDO)

    contexto = eventos_capturados[0]['contexto']
    assert contexto['situacao_de'] == estados.SITUACAO_DESLIGADO
    assert contexto['situacao_para'] == estados.SITUACAO_CADASTRO


@pytest.mark.django_db
def test_duplicata_bloqueada_vira_log_de_warning(unidade):
    """
    Volume alto disso num link publico e sinal de formulario confuso ou de
    abuso, e esse numero nao existe em lugar nenhum se nao for registrado.
    """
    _registrar(unidade, nome='Maria Souza', telefone='86999998888')
    r = _registrar(unidade, nome='Joana Lima', telefone='86999998888')

    assert r.acao == 'conflito'
    log = _logs(unidade.tenant, acao='duplicata_bloqueada').first()
    assert log is not None
    assert log.nivel == 'WARNING'
    assert log.dados_extras['motivo'] == 'possivel_duplicata'
    assert log.dados_extras['candidatos'][0]['match'] == 'telefone'


@pytest.mark.django_db
def test_recontratacao_barrada_tambem_e_registrada(unidade):
    primeiro = _registrar(unidade, cpf=CPF_VALIDO, data_admissao=date(2026, 1, 10))
    mover_situacao(primeiro.colaborador, estados.SITUACAO_DESLIGADO,
                   dados={'data_desligamento': date(2026, 6, 1),
                          'motivo_desligamento': 'justa_causa',
                          'elegivel_recontratacao': False})

    _registrar(unidade, cpf=CPF_VALIDO)

    log = _logs(unidade.tenant, acao='duplicata_bloqueada').first()
    assert log.dados_extras['motivo'] == 'nao_elegivel_recontratacao'


# ──────────────────────────────────────────────
# O contexto nao pode vazar documento
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_contexto_nao_carrega_cpf_inteiro(unidade, eventos_capturados):
    """
    Contexto de evento circula por fluxo do cliente, por log e por integracao
    externa. Documento inteiro nao tem por que passear por ali.
    """
    _registrar(unidade, cpf=CPF_VALIDO)

    contexto = eventos_capturados[0]['contexto']
    assert CPF_VALIDO not in str(contexto)
    assert contexto['cpf_mascarado'].endswith(CPF_VALIDO[-2:])


@pytest.mark.django_db
def test_contexto_traz_o_minimo_pra_montar_uma_mensagem(unidade, eventos_capturados):
    """Um fluxo de "avisar o gestor" precisa de nome, telefone e unidade."""
    cargo = Cargo.all_tenants.create(tenant=unidade.tenant, nome='Atendente')
    _registrar(unidade, cpf=CPF_VALIDO, telefone='86999998888', cargo=cargo)

    contexto = eventos_capturados[0]['contexto']
    for chave in ('colaborador_id', 'colaborador_nome', 'telefone',
                  'unidade_nome', 'cargo', 'situacao'):
        assert chave in contexto, f'faltou {chave}'


@pytest.mark.django_db
def test_contexto_so_tem_escalar(unidade, eventos_capturados):
    """
    A fila da engine so aceita instancia de model nas entidades que ela conhece
    (lead, oportunidade, conversa). Colaborador nao esta na lista, entao tudo
    aqui precisa ser serializavel.
    """
    import json
    _registrar(unidade, cpf=CPF_VALIDO)
    json.dumps(eventos_capturados[0]['contexto'])  # nao pode levantar


# ──────────────────────────────────────────────
# Telemetria nunca derruba a operacao
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_falha_no_log_nao_impede_o_cadastro(unidade, monkeypatch):
    """
    Um cadastro que falha porque o log de auditoria falhou seria uma troca
    pessima. O HistoricoSituacao ja foi gravado antes, entao nada se perde.
    """
    def explode(*args, **kwargs):
        raise RuntimeError('log fora do ar')

    monkeypatch.setattr('apps.sistema.utils.registrar_acao', explode)

    r = _registrar(unidade, cpf=CPF_VALIDO)
    assert r.acao == 'criado'
    assert r.colaborador.pk


@pytest.mark.django_db
def test_falha_no_hub_nao_impede_a_transicao(unidade, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError('engine fora do ar')

    monkeypatch.setattr('apps.automacao.hub.disparar_evento', explode)

    r = _registrar(unidade, cpf=CPF_VALIDO)
    mover_situacao(r.colaborador, estados.SITUACAO_EM_ADMISSAO,
                   dados={'data_admissao': date(2026, 7, 1)})

    assert r.colaborador.situacao == estados.SITUACAO_EM_ADMISSAO


@pytest.mark.django_db
def test_historico_sobrevive_mesmo_com_os_dois_canais_mortos(unidade, monkeypatch):
    """A fonte primaria e o historico, e ela nao depende de telemetria nenhuma."""
    from apps.people.models import HistoricoSituacao

    def explode(*args, **kwargs):
        raise RuntimeError('canal morto')

    monkeypatch.setattr('apps.sistema.utils.registrar_acao', explode)
    monkeypatch.setattr('apps.automacao.hub.disparar_evento', explode)

    r = _registrar(unidade, cpf=CPF_VALIDO)
    mover_situacao(r.colaborador, estados.SITUACAO_EM_ADMISSAO,
                   dados={'data_admissao': date(2026, 7, 1)})

    trilha = HistoricoSituacao.all_tenants.filter(colaborador=r.colaborador)
    assert trilha.count() == 2


# ──────────────────────────────────────────────
# Coerencia do mapa de eventos
# ──────────────────────────────────────────────

def test_toda_situacao_tem_evento_mapeado():
    faltando = [s for s in estados.VALORES_SITUACAO
                if s not in telemetria.EVENTO_POR_SITUACAO]
    assert not faltando, f'Situacoes sem evento: {faltando}'


def test_evento_da_transicao_nunca_devolve_none():
    for de in estados.VALORES_SITUACAO:
        for para in estados.TRANSICOES.get(de, set()):
            assert telemetria.evento_da_transicao(de, para) is not None, \
                f'{de} para {para} sem evento'


def test_nomes_de_evento_usam_o_namespace_do_modulo():
    constantes = [v for k, v in vars(telemetria).items()
                  if k.startswith('EVENTO_') and isinstance(v, str)]
    assert constantes
    for nome in constantes:
        assert nome.startswith('people.'), f'{nome} fora do namespace'


def test_os_quatro_eventos_do_catalogo_batem_com_as_constantes():
    """
    So 4 dos 12 entram no catalogo do editor, pra nao poluir com evento que
    nenhum cliente automatizaria hoje. Mas os 4 precisam existir de verdade:
    catalogo apontando pra evento que ninguem emite e pior que catalogo vazio.
    """
    no_catalogo = {k for k in EVENTOS if k.startswith('people.')}
    assert no_catalogo == {
        telemetria.EVENTO_CRIADO,
        telemetria.EVENTO_ADMISSAO_INICIADA,
        telemetria.EVENTO_EXPERIENCIA_INICIADA,
        telemetria.EVENTO_DESLIGADO,
    }


def test_eventos_do_catalogo_estao_no_grupo_people():
    for chave, dados in EVENTOS.items():
        if chave.startswith('people.'):
            assert dados['grupo'] == 'People'
            assert dados['label']
            assert dados['descricao']
