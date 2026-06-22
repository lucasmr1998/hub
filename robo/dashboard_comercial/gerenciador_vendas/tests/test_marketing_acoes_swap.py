"""Convergência passo 2: os `_acao_*` do marketing delegam pros services únicos.

Unit, sem DB: mocka `apps.automacao.services.acoes.*` e confere que cada adaptador
parseia a config legada e chama o service certo (swap fiel).
"""
from types import SimpleNamespace
from unittest import mock


def _regra():
    return SimpleNamespace(tenant=SimpleNamespace(pk=1), nome='R')


def test_atribuir_round_robin():
    from apps.marketing.automacoes import engine
    acao = SimpleNamespace(configuracao='round-robin')
    with mock.patch('apps.automacao.services.acoes.atribuir_responsavel',
                    return_value=SimpleNamespace(username='joao', get_full_name=lambda: 'João')) as m:
        msg = engine._acao_atribuir_responsavel(_regra(), acao, {'oportunidade': SimpleNamespace(pk=1)})
    assert 'João' in msg
    assert m.call_args.kwargs['modo'] == 'round-robin'


def test_atribuir_fixo():
    from apps.marketing.automacoes import engine
    acao = SimpleNamespace(configuracao='responsavel: joao')
    with mock.patch('apps.automacao.services.acoes.atribuir_responsavel',
                    return_value=SimpleNamespace(username='joao', get_full_name=lambda: '')) as m:
        engine._acao_atribuir_responsavel(_regra(), acao, {})
    assert m.call_args.kwargs['modo'] == 'fixo'
    assert m.call_args.kwargs['username'] == 'joao'


def test_notificacao_delega():
    from apps.marketing.automacoes import engine
    acao = SimpleNamespace(configuracao='Olá equipe', _titulo='Aviso')
    with mock.patch('apps.automacao.services.acoes.notificar', return_value=SimpleNamespace(pk=1)) as m:
        msg = engine._acao_notificacao_sistema(_regra(), acao, {})
    assert 'broadcast criada' in msg
    assert m.call_args.kwargs['mensagem'] == 'Olá equipe'


def test_mover_estagio_delega():
    from apps.marketing.automacoes import engine
    acao = SimpleNamespace(configuracao='estagio: negociacao')
    op = SimpleNamespace(pk=1)
    with mock.patch('apps.automacao.services.acoes.mover_estagio',
                    return_value=SimpleNamespace(nome='Negociação')) as m:
        msg = engine._acao_mover_estagio(_regra(), acao, {'oportunidade': op})
    assert 'movida' in msg
    assert m.call_args.kwargs['estagio_slug'] == 'negociacao'
    assert m.call_args.kwargs['oportunidade'] is op


def test_dar_pontos_delega():
    from apps.marketing.automacoes import engine
    acao = SimpleNamespace(configuracao='pontos: 10')
    with mock.patch('apps.automacao.services.acoes.dar_pontos',
                    return_value=SimpleNamespace(nome='Maria')) as m:
        msg = engine._acao_dar_pontos(_regra(), acao, {'lead': SimpleNamespace(cpf_cnpj='123')})
    assert '10 pontos' in msg
    assert m.call_args.kwargs['cpf'] == '123'
    assert m.call_args.kwargs['pontos'] == 10


def test_criar_oportunidade_delega():
    from apps.marketing.automacoes import engine
    acao = SimpleNamespace(configuracao='', _config_json={'pipeline': 'p', 'estagio': 'e'})
    lead = SimpleNamespace(pk=2, nome='ACME')
    with mock.patch('apps.automacao.services.acoes.criar_oportunidade',
                    return_value=(SimpleNamespace(pk=9), True)) as m:
        msg = engine._acao_criar_oportunidade(_regra(), acao, {'lead': lead, 'lead_nome': 'ACME'})
    assert 'pk=9' in msg
    assert m.call_args.kwargs['pipeline_slug'] == 'p'
    assert m.call_args.kwargs['estagio_slug'] == 'e'


def test_criar_oportunidade_ja_existe():
    from apps.marketing.automacoes import engine
    acao = SimpleNamespace(configuracao='')
    lead = SimpleNamespace(pk=2, nome='ACME')
    with mock.patch('apps.automacao.services.acoes.criar_oportunidade',
                    return_value=(SimpleNamespace(pk=9), False)):
        msg = engine._acao_criar_oportunidade(_regra(), acao, {'lead': lead})
    assert 'ja existe' in msg


def test_criar_venda_delega():
    from apps.marketing.automacoes import engine
    acao = SimpleNamespace(configuracao='')
    with mock.patch('apps.automacao.services.acoes.criar_venda',
                    return_value=(SimpleNamespace(pk=5), True)):
        msg = engine._acao_criar_venda(_regra(), acao, {'lead': SimpleNamespace(pk=2)})
    assert 'Venda criada' in msg
