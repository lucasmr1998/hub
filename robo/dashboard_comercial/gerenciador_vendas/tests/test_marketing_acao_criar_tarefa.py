"""Convergência passo 2: `_acao_criar_tarefa` do marketing delega pro service único.

Unit, sem DB: mocka `apps.automacao.services.acoes.criar_tarefa` e confere que o
adaptador antigo parseia a config no formato legado e chama o service certo.
"""
from types import SimpleNamespace
from unittest import mock


def test_delega_pro_service_com_config_parseada():
    from apps.marketing.automacoes import engine
    regra = SimpleNamespace(tenant=SimpleNamespace(pk=1), nome='Regra X')
    acao = SimpleNamespace(configuracao='Follow-up {{lead_nome}}\ntipo: ligacao\nprioridade: alta')
    lead = SimpleNamespace(pk=2, nome='ACME')
    contexto = {'lead': lead, 'lead_nome': 'ACME'}

    with mock.patch('apps.automacao.services.acoes.criar_tarefa',
                    return_value=SimpleNamespace(pk=99)) as m:
        msg = engine._acao_criar_tarefa(regra, acao, contexto)

    assert 'pk=99' in msg
    assert m.call_args.args[0] is regra.tenant
    kwargs = m.call_args.kwargs
    assert kwargs['titulo'] == 'Follow-up ACME'   # _substituir_variaveis resolveu o legado
    assert kwargs['tipo'] == 'ligacao'
    assert kwargs['prioridade'] == 'alta'
    assert kwargs['lead'] is lead


def test_sem_responsavel_retorna_mensagem():
    from apps.marketing.automacoes import engine
    regra = SimpleNamespace(tenant=SimpleNamespace(pk=1), nome='R')
    acao = SimpleNamespace(configuracao='Tarefa')
    with mock.patch('apps.automacao.services.acoes.criar_tarefa',
                    side_effect=ValueError('Nenhum responsável disponível para a tarefa.')):
        msg = engine._acao_criar_tarefa(regra, acao, {})
    assert 'responsável' in msg
