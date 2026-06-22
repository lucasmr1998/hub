"""
Nó `http_request` — faz uma requisição HTTP e devolve a resposta como output.

Config:
- `metodo`: GET|POST|PUT|PATCH|DELETE (default GET)
- `url`: template `{{...}}`
- `headers`: dict (valores aceitam template)
- `query`: dict (valores aceitam template)
- `body`: template/dict; `body_tipo`: json|form|raw|none (default none)
- `auth`: {tipo: none|basic|bearer, token | usuario/senha}
- `timeout_seg`: int (default 15)
- `tamanho_max_kb`: cap da resposta (default 1024)
- `salvar_em`: opcional, promove o output pro `var.<nome>`

Output: `{status_code, ok, body, headers (mascarado), tempo_ms}`
Branches: `sucesso` (2xx) | `erro` (SSRF, timeout, 4xx/5xx, exceção, resposta grande)

Segurança: guard SSRF (esquema + IP interno + sem seguir redirect) e mascaramento
de headers ficam em `seguranca.py`.
"""
import base64
import json
import time

import requests

from .base import BaseNode, NodeResult, registrar
from .seguranca import DestinoBloqueado, mascarar_headers, validar_url_ssrf


METODOS = {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'}
_CHUNK = 8192


@registrar
class HttpRequestNode(BaseNode):
    tipo = "http_request"
    label = "HTTP Request"
    icone = "bi-globe"
    categoria = "core"
    grupo = "Core"
    subgrupo = "HTTP"
    saidas = ["sucesso", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'metodo', 'label': 'Método', 'tipo': 'select',
             'opcoes': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']},
            {'nome': 'url', 'label': 'URL', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': 'https://api.exemplo.com/{{var.id}}'},
            {'nome': 'query', 'label': 'Query params', 'tipo': 'keyvalue'},
            {'nome': 'headers', 'label': 'Headers', 'tipo': 'keyvalue'},
            {'nome': 'body_tipo', 'label': 'Tipo do corpo', 'tipo': 'select',
             'opcoes': ['none', 'json', 'form', 'raw']},
            {'nome': 'body', 'label': 'Corpo', 'tipo': 'textarea',
             'placeholder': '{"nome": "{{var.nome}}"}'},
            {'nome': 'timeout_seg', 'label': 'Timeout (s)', 'tipo': 'numero'},
            {'nome': 'salvar_em', 'label': 'Salvar saída em (var)', 'tipo': 'texto'},
        ]

    def validar_config(self, config) -> list:
        erros = []
        if not config.get('url'):
            erros.append('`url` é obrigatória.')
        metodo = str(config.get('metodo', 'GET')).upper()
        if metodo not in METODOS:
            erros.append(f"`metodo` inválido: {metodo} (use {', '.join(sorted(METODOS))}).")
        return erros

    def executar(self, config, entrada, contexto) -> NodeResult:
        metodo = str(config.get('metodo', 'GET')).upper()
        url = contexto.resolver(config.get('url', ''))
        timeout = config.get('timeout_seg', 15)
        tamanho_max = int(config.get('tamanho_max_kb', 1024)) * 1024

        # 1. Guard SSRF ANTES de qualquer conexão.
        try:
            validar_url_ssrf(url)
        except DestinoBloqueado as exc:
            return self._erro(f'destino bloqueado (SSRF): {exc}')

        headers = self._aplicar_auth(contexto.resolver(config.get('headers') or {}),
                                     config.get('auth'), contexto)
        kwargs = {
            'headers': headers,
            'params': contexto.resolver(config.get('query') or {}),
            'timeout': timeout,
            'allow_redirects': False,  # não seguir 3xx cegamente (bypass de SSRF)
            'stream': True,            # ler capado, sem estourar memória
        }
        self._aplicar_body(kwargs, config, contexto)

        inicio = time.monotonic()
        try:
            resp = requests.request(metodo, url, **kwargs)
            corpo, excedeu = self._ler_capado(resp, tamanho_max)
            content_type = resp.headers.get('Content-Type', '')
            status_code = resp.status_code
            resp_headers = resp.headers
            resp.close()
        except requests.RequestException as exc:
            return self._erro(f'falha HTTP: {exc}')
        tempo_ms = int((time.monotonic() - inicio) * 1000)

        if excedeu:
            return self._erro(f'resposta excede {tamanho_max // 1024} KB')

        ok = 200 <= status_code < 300
        output = {
            'status_code': status_code,
            'ok': ok,
            'body': self._parse_body(corpo, content_type),
            'headers': mascarar_headers(resp_headers),
            'tempo_ms': tempo_ms,
        }
        resultado = NodeResult(
            output=output,
            status='ok' if ok else 'erro',
            branch='sucesso' if ok else 'erro',
            erro=None if ok else f'HTTP {status_code}',
        )
        salvar_em = config.get('salvar_em')
        if salvar_em:
            resultado.promote = {salvar_em: output}
        return resultado

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _erro(msg):
        return NodeResult(status='erro', branch='erro', erro=msg, output={'ok': False})

    def _aplicar_auth(self, headers, auth, contexto):
        headers = dict(headers or {})
        tipo = str((auth or {}).get('tipo', 'none')).lower()
        if tipo == 'bearer':
            token = contexto.resolver(auth.get('token', ''))
            headers['Authorization'] = f'Bearer {token}'
        elif tipo == 'basic':
            usuario = contexto.resolver(auth.get('usuario', ''))
            senha = contexto.resolver(auth.get('senha', ''))
            cred = base64.b64encode(f'{usuario}:{senha}'.encode()).decode()
            headers['Authorization'] = f'Basic {cred}'
        return headers

    def _aplicar_body(self, kwargs, config, contexto):
        body_tipo = str(config.get('body_tipo', 'none')).lower()
        if body_tipo == 'none':
            return
        body = contexto.resolver(config.get('body'))
        if body_tipo == 'json':
            kwargs['json'] = body
        elif body_tipo == 'form':
            kwargs['data'] = body
        elif body_tipo == 'raw':
            kwargs['data'] = body if isinstance(body, (str, bytes)) else str(body)

    def _ler_capado(self, resp, tamanho_max):
        total = 0
        chunks = []
        for chunk in resp.iter_content(_CHUNK):
            if not chunk:
                continue
            total += len(chunk)
            if total > tamanho_max:
                return b'', True
            chunks.append(chunk)
        return b''.join(chunks), False

    def _parse_body(self, corpo, content_type):
        texto = corpo.decode('utf-8', errors='replace')
        if 'application/json' in (content_type or '').lower():
            try:
                return json.loads(texto)
            except ValueError:
                return texto
        return texto
