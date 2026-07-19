"""Cliente da API Wifeed (portal WiFi) — autenticação e leitura de records.

Doc: base https://api.wifeed.com.br
  POST /auth/api/login {clientId, clientSecret} -> {response:{token}}  (Bearer, 24h)
  GET  /core/openapi/v1/report/record?date=YYYY-MM-DD&page=N&local=<ids>
       -> lista de pessoas cadastradas no portal (id, name, email, phoneNumber,
          birthDate, gender, registerType, accessAmount, lastAccessDate)
       page começa em 0, máx 500/página. Rate limit 15 req/s (429 + Retry-After).
"""
import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

PAGE_SIZE = 500          # máximo por página no /report/record
_TOKEN_TTL = 23 * 3600   # token vale 24h; renova com folga


class WifeedError(Exception):
    """Falha ao falar com a API Wifeed."""


class WifeedClient:
    def __init__(self, base_url=None, client_id=None, client_secret=None, timeout=30):
        self.base_url = (base_url or getattr(settings, 'WIFEED_BASE_URL',
                                             'https://api.wifeed.com.br')).rstrip('/')
        self.client_id = client_id or getattr(settings, 'WIFEED_CLIENT_ID', '')
        self.client_secret = client_secret or getattr(settings, 'WIFEED_CLIENT_SECRET', '')
        self.timeout = timeout
        self._token = None
        self._token_ts = 0.0

    # ---- auth -----------------------------------------------------------
    def _login(self):
        if not self.client_id or not self.client_secret:
            raise WifeedError('WIFEED_CLIENT_ID/WIFEED_CLIENT_SECRET não configurados.')
        url = f'{self.base_url}/auth/api/login'
        resp = requests.post(
            url,
            json={'clientId': self.client_id, 'clientSecret': self.client_secret},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise WifeedError(f'Login Wifeed falhou ({resp.status_code}): {resp.text[:300]}')
        token = (resp.json() or {}).get('response', {}).get('token')
        if not token:
            raise WifeedError('Login Wifeed sem token na resposta.')
        self._token = token
        self._token_ts = time.monotonic()
        return token

    def _auth_header(self):
        if not self._token or (time.monotonic() - self._token_ts) > _TOKEN_TTL:
            self._login()
        return {'Authorization': f'Bearer {self._token}'}

    # ---- requests com retry de rate-limit -------------------------------
    def _get(self, path, params):
        url = f'{self.base_url}{path}'
        for tentativa in range(4):
            resp = requests.get(url, params=params, headers=self._auth_header(),
                                 timeout=self.timeout)
            if resp.status_code == 429:
                espera = int(resp.headers.get('Retry-After', '2') or 2)
                logger.warning('[Wifeed] 429 rate-limit, aguardando %ss', espera)
                time.sleep(min(espera, 30))
                continue
            if resp.status_code == 401 and tentativa == 0:
                # token pode ter expirado — força novo login e tenta de novo
                self._token = None
                continue
            if resp.status_code != 200:
                raise WifeedError(f'GET {path} falhou ({resp.status_code}): {resp.text[:300]}')
            return resp.json()
        raise WifeedError(f'GET {path} falhou após retries (rate-limit/token).')

    # ---- records (leads do portal) --------------------------------------
    def get_records_page(self, date, page=0, local=None):
        """Uma página de records. `date`='YYYY-MM-DD'; `local`=id ou lista de ids."""
        params = {'date': date, 'page': page}
        if local is not None:
            params['local'] = local
        data = self._get('/core/openapi/v1/report/record', params)
        return data if isinstance(data, list) else (data or {}).get('response', []) or []

    def iter_records(self, date, local=None, max_paginas=200):
        """Itera todos os records de uma data (paginando até esvaziar)."""
        for page in range(max_paginas):
            lote = self.get_records_page(date, page=page, local=local)
            if not lote:
                return
            for rec in lote:
                yield rec
            if len(lote) < PAGE_SIZE:
                return
            # respeita o rate limit (15 req/s) entre páginas
            time.sleep(0.1)

    # ---- catálogo: locais e campanhas -----------------------------------
    @staticmethod
    def _lista(data):
        return data if isinstance(data, list) else (data or {}).get('response', []) or []

    def _paginar(self, path, params=None, max_paginas=50):
        """Itera todas as páginas de um endpoint de listagem (500/página)."""
        base = dict(params or {})
        for page in range(max_paginas):
            base['page'] = page
            lote = self._lista(self._get(path, base))
            if not lote:
                return
            for item in lote:
                yield item
            if len(lote) < PAGE_SIZE:
                return
            time.sleep(0.1)

    def get_locais(self):
        """Lista os locais (pontos WiFi) da conta: {id, name, isActive}."""
        return list(self._paginar('/core/openapi/v1/local'))

    def get_campanhas(self):
        """Lista as campanhas da conta: {id, name, isActive}."""
        return list(self._paginar('/core/openapi/v1/campaign'))

    # ---- access (leads por campanha; traz CPF) --------------------------
    def get_access_page(self, date, page=0, campaign=None, local=None):
        """Uma página de acessos. `date`='YYYY-MM-DD' (obrigatório)."""
        params = {'date': date, 'page': page}
        if campaign is not None:
            params['campaign'] = campaign
        if local is not None:
            params['local'] = local
        return self._lista(self._get('/core/openapi/v1/report/access', params))

    def iter_access(self, date, campaign=None, local=None, max_paginas=200):
        """Itera todos os acessos de uma data (paginando até esvaziar)."""
        for page in range(max_paginas):
            lote = self.get_access_page(date, page=page, campaign=campaign, local=local)
            if not lote:
                return
            for row in lote:
                yield row
            if len(lote) < PAGE_SIZE:
                return
            time.sleep(0.1)
