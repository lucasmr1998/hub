"""Nós de convergência do marketing (CRM/CS) — unit (sem DB; services mockados).

Cobre: mover_estagio, criar_oportunidade, criar_venda, dar_pontos,
atribuir_responsavel. Cada um chama um service de `services/acoes.py` (mockado).
"""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug


def _ctx(**kw):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='t'), **kw)


def test_todos_registrados():
    for tipo in ('mover_estagio', 'criar_oportunidade', 'criar_venda',
                 'dar_pontos', 'atribuir_responsavel'):
        assert tipo_por_slug(tipo) is not None, tipo


# --- mover_estagio --------------------------------------------------------
def test_mover_estagio_sem_oportunidade_erro():
    no = tipo_por_slug('mover_estagio')
    res = no.executar({'estagio_slug': 'neg'}, {}, _ctx())
    assert res.branch == 'erro'


def test_mover_estagio_ok():
    no = tipo_por_slug('mover_estagio')
    ctx = _ctx(oportunidade=SimpleNamespace(pk=1))
    with mock.patch('apps.automacao.nodes.mover_estagio.mover_estagio',
                    return_value=SimpleNamespace(slug='neg', nome='Negociação')) as m:
        res = no.executar({'estagio_slug': 'neg'}, {}, ctx)
    assert res.branch == 'sucesso' and res.output['estagio'] == 'neg'
    assert m.call_args.kwargs['estagio_slug'] == 'neg'


# --- criar_oportunidade ---------------------------------------------------
def test_criar_oportunidade_sem_lead_erro():
    no = tipo_por_slug('criar_oportunidade')
    assert no.executar({}, {}, _ctx()).branch == 'erro'


def test_criar_oportunidade_ok():
    no = tipo_por_slug('criar_oportunidade')
    ctx = _ctx(lead=SimpleNamespace(pk=2, nome='ACME'))
    with mock.patch('apps.automacao.nodes.criar_oportunidade.criar_oportunidade',
                    return_value=(SimpleNamespace(pk=5), True)):
        res = no.executar({'titulo': '{{lead.nome}}'}, {}, ctx)
    assert res.branch == 'sucesso' and res.output == {'oportunidade_id': 5, 'criada': True}


# --- criar_venda ----------------------------------------------------------
def test_criar_venda_sem_lead_erro():
    no = tipo_por_slug('criar_venda')
    assert no.executar({}, {}, _ctx()).branch == 'erro'


def test_criar_venda_ok():
    no = tipo_por_slug('criar_venda')
    ctx = _ctx(lead=SimpleNamespace(pk=2))
    with mock.patch('apps.automacao.nodes.criar_venda.criar_venda',
                    return_value=(SimpleNamespace(pk=9), True)):
        res = no.executar({}, {}, ctx)
    assert res.branch == 'sucesso' and res.output == {'venda_id': 9, 'criada': True}


# --- dar_pontos -----------------------------------------------------------
def test_dar_pontos_exige_pontos():
    no = tipo_por_slug('dar_pontos')
    assert no.validar_config({})
    assert not no.validar_config({'pontos': '10'})


def test_dar_pontos_usa_cpf_do_lead_e_chama_service():
    no = tipo_por_slug('dar_pontos')
    ctx = _ctx(lead=SimpleNamespace(pk=2, cpf_cnpj='123.456.789-00'))
    with mock.patch('apps.automacao.nodes.dar_pontos.dar_pontos',
                    return_value=SimpleNamespace(nome='Maria', saldo=20)) as m:
        res = no.executar({'pontos': '10'}, {}, ctx)
    assert res.branch == 'sucesso' and res.output == {'membro': 'Maria', 'saldo': 20}
    assert m.call_args.kwargs['cpf'] == '123.456.789-00'
    assert m.call_args.kwargs['pontos'] == 10


def test_dar_pontos_zero_vira_erro():
    no = tipo_por_slug('dar_pontos')
    assert no.executar({'pontos': '0'}, {}, _ctx()).branch == 'erro'


# --- atribuir_responsavel -------------------------------------------------
def test_atribuir_responsavel_ok():
    no = tipo_por_slug('atribuir_responsavel')
    ctx = _ctx(oportunidade=SimpleNamespace(pk=1))
    fake = SimpleNamespace(username='joao', get_full_name=lambda: 'João Silva')
    with mock.patch('apps.automacao.nodes.atribuir_responsavel.atribuir_responsavel',
                    return_value=fake):
        res = no.executar({'modo': 'round-robin'}, {}, ctx)
    assert res.branch == 'sucesso' and res.output == {'responsavel': 'João Silva'}


def test_atribuir_responsavel_erro_do_service():
    no = tipo_por_slug('atribuir_responsavel')
    with mock.patch('apps.automacao.nodes.atribuir_responsavel.atribuir_responsavel',
                    side_effect=ValueError('Sem oportunidade para atribuir.')):
        res = no.executar({'modo': 'round-robin'}, {}, _ctx())
    assert res.branch == 'erro' and 'atribuir' in res.erro
