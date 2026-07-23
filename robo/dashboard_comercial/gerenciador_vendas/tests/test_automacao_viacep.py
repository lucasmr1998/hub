"""Testes do nó `viacep`. A chamada de rede é mockada; o que importa é o
roteamento (encontrado / nao_encontrado / erro) e o output que chega no fluxo.
"""
from unittest import mock

import pytest

from apps.automacao.nodes import Contexto
from apps.automacao.nodes.base import REGISTRY
from tests.factories import TenantFactory

CAMINHO_SERVICE = 'apps.comercial.viabilidade.services.buscar_endereco_por_cep'


def _rodar(cep_config, tenant, variaveis=None):
    ctx = Contexto(tenant=tenant, variaveis=variaveis)
    return REGISTRY['viacep'].executar({'cep': cep_config}, None, ctx)


@pytest.mark.django_db
@mock.patch(CAMINHO_SERVICE)
def test_cep_encontrado_traz_endereco_pro_fluxo(mock_busca):
    tenant = TenantFactory()
    mock_busca.return_value = {
        'cep': '01310100', 'logradouro': 'Avenida Paulista',
        'bairro': 'Bela Vista', 'cidade': 'São Paulo', 'uf': 'SP',
    }

    r = _rodar('01310-100', tenant)

    assert r.branch == 'encontrado'
    assert r.output['logradouro'] == 'Avenida Paulista'
    assert r.output['cidade'] == 'São Paulo'
    assert r.output['uf'] == 'SP'
    mock_busca.assert_called_once_with('01310-100')


@pytest.mark.django_db
@mock.patch(CAMINHO_SERVICE)
def test_cep_inexistente_cai_em_nao_encontrado_nao_erro(mock_busca):
    """CEP que o cliente digitou errado é caso de negócio: o fluxo repergunta,
    não trata como falha técnica."""
    tenant = TenantFactory()
    mock_busca.return_value = {}

    r = _rodar('99999-999', tenant)

    assert r.branch == 'nao_encontrado'
    # Ecoa o CEP consultado pra quem quiser montar a mensagem de repergunta.
    assert r.output['cep'] == '99999-999'


@pytest.mark.django_db
@mock.patch(CAMINHO_SERVICE)
def test_cep_vazio_depois_de_resolver_e_erro(mock_busca):
    tenant = TenantFactory()

    r = _rodar('{{var.payload.cep}}', tenant, variaveis={'payload': {}})

    assert r.branch == 'erro'
    mock_busca.assert_not_called()


@pytest.mark.django_db
@mock.patch(CAMINHO_SERVICE)
def test_falha_de_rede_vira_branch_erro_nao_derruba_execucao(mock_busca):
    tenant = TenantFactory()
    mock_busca.side_effect = RuntimeError('timeout')

    r = _rodar('01310-100', tenant)

    assert r.branch == 'erro'
    assert 'timeout' in (r.erro or '')


@pytest.mark.django_db
@mock.patch(CAMINHO_SERVICE)
def test_cep_resolve_template_da_resposta_do_checklist(mock_busca):
    """No fluxo o CEP vem de `{{nodes.respostas.cep}}`, não de literal."""
    tenant = TenantFactory()
    mock_busca.return_value = {'cep': '64000000', 'logradouro': 'Rua X',
                               'bairro': 'Centro', 'cidade': 'Teresina', 'uf': 'PI'}
    ctx = Contexto(tenant=tenant)
    ctx.nodes = {'respostas': {'cep': '64000000'}}

    r = REGISTRY['viacep'].executar({'cep': '{{nodes.respostas.cep}}'}, None, ctx)

    assert r.branch == 'encontrado'
    mock_busca.assert_called_once_with('64000000')
