"""
Testes do nó `http_request` (D4).

Puro unit, sem rede: `requests.request` é mockado. SSRF é testado com IPs
literais (sem DNS). Cobre 2xx, 4xx/5xx, timeout, validar_config, bloqueio SSRF
(esquema + IP interno), allow_redirects=False, mascaramento de headers e
garantia de que o token bearer não vaza no output.
"""
import json
from types import SimpleNamespace
from unittest import mock

import requests

from apps.automacao.nodes import Contexto, tipo_por_slug


def _ctx(**kwargs):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='alpha'), **kwargs)


class _FakeResp:
    def __init__(self, status_code=200, headers=None, body=b'{"ok": true}'):
        self.status_code = status_code
        self.headers = headers if headers is not None else {'Content-Type': 'application/json'}
        self._body = body

    def iter_content(self, n):
        for i in range(0, len(self._body), n):
            yield self._body[i:i + n]

    def close(self):
        pass


_PATH = 'apps.automacao.nodes.http_request.requests.request'


def test_no_registrado():
    assert tipo_por_slug('http_request') is not None


def test_validar_config_sem_url():
    assert tipo_por_slug('http_request').validar_config({'metodo': 'GET'}) != []


def test_validar_config_metodo_invalido():
    assert tipo_por_slug('http_request').validar_config({'url': 'http://x', 'metodo': 'FOO'}) != []


@mock.patch(_PATH)
def test_get_2xx(mock_req):
    mock_req.return_value = _FakeResp(200, {'Content-Type': 'application/json'}, b'{"hello":"world"}')
    res = tipo_por_slug('http_request').executar(
        {'metodo': 'GET', 'url': 'http://1.1.1.1/x'}, {}, _ctx())
    assert res.status == 'ok'
    assert res.branch == 'sucesso'
    assert res.output['status_code'] == 200
    assert res.output['ok'] is True
    assert res.output['body'] == {'hello': 'world'}
    # prova allow_redirects=False (não segue 3xx cegamente)
    assert mock_req.call_args.kwargs['allow_redirects'] is False


@mock.patch(_PATH)
def test_status_erro_vai_pro_branch_erro(mock_req):
    mock_req.return_value = _FakeResp(500, {'Content-Type': 'application/json'}, b'{}')
    res = tipo_por_slug('http_request').executar(
        {'metodo': 'GET', 'url': 'http://1.1.1.1/'}, {}, _ctx())
    assert res.branch == 'erro'
    assert res.output['status_code'] == 500
    assert res.output['ok'] is False


@mock.patch(_PATH)
def test_timeout_vai_pro_branch_erro(mock_req):
    mock_req.side_effect = requests.Timeout('timeout')
    res = tipo_por_slug('http_request').executar(
        {'metodo': 'GET', 'url': 'http://1.1.1.1/'}, {}, _ctx())
    assert res.branch == 'erro'
    assert 'falha HTTP' in res.erro


@mock.patch(_PATH)
def test_ssrf_bloqueia_ip_interno_e_esquema(mock_req):
    no = tipo_por_slug('http_request')
    for url in ('http://127.0.0.1/', 'http://169.254.169.254/', 'file:///etc/passwd'):
        res = no.executar({'metodo': 'GET', 'url': url}, {}, _ctx())
        assert res.branch == 'erro', url
        assert 'SSRF' in res.erro, url
    mock_req.assert_not_called()


@mock.patch(_PATH)
def test_mascara_headers_da_resposta(mock_req):
    mock_req.return_value = _FakeResp(
        200,
        {'Content-Type': 'text/plain', 'Set-Cookie': 'sess=segredo', 'Authorization': 'Bearer X'},
        b'ok',
    )
    res = tipo_por_slug('http_request').executar(
        {'metodo': 'GET', 'url': 'http://1.1.1.1/'}, {}, _ctx())
    assert res.output['headers']['Set-Cookie'] == '***'
    assert res.output['headers']['Authorization'] == '***'


@mock.patch(_PATH)
def test_bearer_token_nao_vaza_no_output(mock_req):
    mock_req.return_value = _FakeResp(200, {'Content-Type': 'application/json'}, b'{}')
    res = tipo_por_slug('http_request').executar(
        {'metodo': 'GET', 'url': 'http://1.1.1.1/',
         'auth': {'tipo': 'bearer', 'token': 'SUPERSECRET'}},
        {}, _ctx())
    # token vai no header da requisição...
    assert mock_req.call_args.kwargs['headers']['Authorization'] == 'Bearer SUPERSECRET'
    # ...mas nunca aparece no output devolvido
    assert 'SUPERSECRET' not in json.dumps(res.output, default=str)


@mock.patch(_PATH)
def test_salvar_em_promove_output(mock_req):
    mock_req.return_value = _FakeResp(200, {'Content-Type': 'application/json'}, b'{"x":1}')
    res = tipo_por_slug('http_request').executar(
        {'metodo': 'GET', 'url': 'http://1.1.1.1/', 'salvar_em': 'resp'}, {}, _ctx())
    assert res.promote and 'resp' in res.promote
    assert res.promote['resp']['status_code'] == 200
