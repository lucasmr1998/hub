"""
Testes dos endpoints do editor de automação (E1).

Sem banco: chama as views direto via RequestFactory, setando `user`/`tenant` na
mão (auth/tenant é responsabilidade do Django, não da view). Mantém o módulo
inteiro DB-free, igual ao resto da automação.

- catálogo de nós (paleta)
- testar fluxo (roda executar_fluxo no JSON postado, devolve trace)
- exige login + tenant
"""
import json
from types import SimpleNamespace

from django.test import RequestFactory

from apps.automacao import views


def _req_get(autenticado=True):
    req = RequestFactory().get('/automacao/api/nodes/')
    # is_superuser=True: estes testes cobrem roteamento/execução, não permissão
    # (permissão granular tem suite própria em test_automacao_permissoes.py).
    req.user = SimpleNamespace(is_authenticated=autenticado, is_superuser=True)
    return req


def _post_fluxo(payload, tenant=SimpleNamespace(pk=1, slug='alpha')):
    req = RequestFactory().post(
        '/automacao/api/testar-fluxo/',
        data=json.dumps(payload),
        content_type='application/json',
    )
    req.user = SimpleNamespace(is_authenticated=True, is_superuser=True)
    req.tenant = tenant
    return views.testar_fluxo_api(req)


def test_catalogo_lista_nos():
    resp = views.nodes_catalogo_api(_req_get())
    tipos = {n['tipo'] for n in json.loads(resp.content)['nodes']}
    assert {'set_fields', 'http_request'} <= tipos


def test_testar_fluxo_roda_e_devolve_trace():
    fluxo = {
        'inicio': 'n1',
        'nodes': {
            'n1': {'tipo': 'set_fields', 'config': {'campo': 'nome', 'valor': 'Lucas'}},
            'n2': {'tipo': 'set_fields', 'config': {'campo': 'oi', 'valor': 'Oi {{var.nome}}'}},
        },
        'conexoes': [{'de': 'n1', 'para': 'n2', 'saida': 'sucesso'}],
    }
    resp = _post_fluxo({'fluxo': fluxo})
    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert data['status'] == 'completado'
    assert data['variaveis']['oi'] == 'Oi Lucas'
    assert [p['handle'] for p in data['passos']] == ['n1', 'n2']


def test_testar_fluxo_invalido_retorna_400():
    resp = _post_fluxo({'fluxo': {'inicio': 'x', 'nodes': {}}})
    assert resp.status_code == 400


def test_sem_tenant_retorna_400():
    fluxo = {'inicio': 'n1', 'nodes': {'n1': {'tipo': 'set_fields',
             'config': {'campo': 'x', 'valor': '1'}}}, 'conexoes': []}
    resp = _post_fluxo({'fluxo': fluxo}, tenant=None)
    assert resp.status_code == 400


def test_exige_login():
    resp = views.nodes_catalogo_api(_req_get(autenticado=False))
    assert resp.status_code == 302
