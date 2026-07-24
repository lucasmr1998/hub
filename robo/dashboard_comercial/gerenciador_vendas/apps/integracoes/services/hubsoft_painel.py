"""Cliente da API INTERNA do painel HubSoft, tenant-aware.

Porque existe: conversao de prospecto, novo servico e upgrade de plano NAO tem
API oficial no HubSoft. So existem no painel do operador. Este service replica o
que o robo_v2 fazia (posvenda_hubsoft/api_interna/cliente_http.py), mas por tenant:
as credenciais do operador vem de uma IntegracaoAPI tipo 'hubsoft_painel' e os IDs
de negocio vem de um PerfilConversaoHubsoft, nada fica hardcoded.

Como autentica: o painel e um AngularJS que guarda um JWT no localStorage. O login
e feito uma vez via Selenium headless (email, Validar, senha, Entrar), capturamos
os cookies + o JWT e passamos a usar requests puro. O token e cacheado em
`configuracoes_extras['cache']['painel_token']` com a expiracao do proprio JWT, pra
nao abrir o navegador a cada execucao.

FASE 1 (esta): so estrutura + login + LEITURA (get_cliente, obter_servico_edit,
schema_cache, buscar_cep). Nenhum POST de escrita ainda. As escritas (criar cliente,
adicionar servico, migrar) entram nas fases seguintes, sempre atras do guard de
dry run do perfil.
"""
import base64
import json
import logging
import time

import requests

logger = logging.getLogger(__name__)

# Folga de seguranca: renova o token se faltar menos que isto pra expirar.
_MARGEM_EXP_SEGUNDOS = 120
_TIMEOUT_LOGIN = 45
_TIMEOUT_HTTP = 30


class HubsoftPainelError(Exception):
    """Falha no cliente do painel HubSoft (login, HTTP, config)."""


def _derivar_api_base(painel_url: str) -> str:
    """Deriva a base da API interna a partir da URL do painel.

    painel https://artelecom.hubsoft.com.br  ->  api https://api.artelecom.hubsoft.com.br
    (o robo_v2 tinha as duas separadas: painel e api.<mesmo dominio>).
    """
    url = (painel_url or '').rstrip('/')
    for prefixo in ('https://', 'http://'):
        if url.startswith(prefixo) and not url[len(prefixo):].startswith('api.'):
            return prefixo + 'api.' + url[len(prefixo):]
    return url


def _jwt_exp(token: str):
    """Le o campo `exp` (epoch) do payload do JWT, ou None se nao der."""
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)  # padding base64url
        dados = json.loads(base64.urlsafe_b64decode(payload))
        return int(dados.get('exp')) if dados.get('exp') else None
    except Exception:
        return None


class HubsoftPainelService:
    """Sessao HTTP autenticada contra a API interna do painel HubSoft de um tenant."""

    def __init__(self, integracao, perfil=None):
        if integracao.tipo != 'hubsoft_painel':
            raise HubsoftPainelError(
                f"Integracao '{integracao.nome}' nao e do tipo hubsoft_painel.")
        self.integracao = integracao
        self.perfil = perfil
        self.painel_url = (integracao.base_url or '').rstrip('/')
        extras = integracao.configuracoes_extras or {}
        self.api_base = (extras.get('api_base') or _derivar_api_base(self.painel_url)).rstrip('/')
        self.session = requests.Session()
        self._autenticado = False

    # ------------------------------------------------------------------
    # Autenticacao (token cacheado, senao login Selenium)
    # ------------------------------------------------------------------

    def _garantir_sessao(self):
        if self._autenticado:
            return
        token = self._token_do_cache()
        if token:
            self._aplicar_token(token, com_cookies=False)
            self._autenticado = True
            return
        self._login_painel()
        self._autenticado = True

    def _token_do_cache(self):
        cache = ((self.integracao.configuracoes_extras or {}).get('cache') or {})
        dados = cache.get('painel_token') or {}
        token = dados.get('token')
        exp = dados.get('exp')
        if not token:
            return None
        if exp and exp - time.time() < _MARGEM_EXP_SEGUNDOS:
            return None
        return token

    def _salvar_token_cache(self, token: str):
        extras = dict(self.integracao.configuracoes_extras or {})
        cache = dict(extras.get('cache') or {})
        cache['painel_token'] = {'token': token, 'exp': _jwt_exp(token)}
        extras['cache'] = cache
        self.integracao.configuracoes_extras = extras
        self.integracao.save(update_fields=['configuracoes_extras', 'data_atualizacao'])

    def _aplicar_token(self, token: str, *, com_cookies: bool):
        self.session.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json;charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': self.painel_url,
            'Referer': f'{self.painel_url}/',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Authorization': f'Bearer {token}',
        })

    def _login_painel(self):
        """Abre o painel via Selenium headless, faz login e captura cookies + JWT.

        Selenium e importado aqui dentro (lazy) pra o modulo carregar mesmo em
        ambiente sem navegador; a falta do driver vira erro claro.
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.common.exceptions import TimeoutException
        except Exception as exc:
            raise HubsoftPainelError(f'Selenium indisponivel para login no painel: {exc}')

        usuario = self.integracao.client_id
        senha = self.integracao.client_secret
        if not (usuario and senha and self.painel_url):
            raise HubsoftPainelError(
                'Credencial de painel incompleta (base_url/client_id/client_secret).')

        opts = Options()
        for arg in ('--no-sandbox', '--disable-dev-shm-usage', '--window-size=1920,1080',
                    '--headless=new', '--disable-gpu', '--no-first-run', '--disable-default-apps'):
            opts.add_argument(arg)

        driver = None
        try:
            driver = webdriver.Chrome(options=opts)
            wait = WebDriverWait(driver, _TIMEOUT_LOGIN)
            driver.get(f'{self.painel_url}/login')
            email_in = wait.until(EC.presence_of_element_located((By.NAME, 'email')))
            email_in.clear()
            email_in.send_keys(usuario)
            time.sleep(1.0)
            # O HubSoft valida o email num primeiro passo antes de pedir a senha.
            try:
                WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Validar')]"))
                ).click()
            except TimeoutException:
                pass  # fluxo de 1 etapa
            pwd = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']")))
            pwd.clear()
            pwd.send_keys(senha)
            time.sleep(1.0)
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Entrar')]"))).click()

            # Espera sair de /login (dashboard renderizado).
            fim = time.time() + 30
            ok = False
            while time.time() < fim:
                cur = driver.current_url or ''
                if '/login' not in cur and cur and not cur.endswith('://'):
                    ok = True
                    break
                time.sleep(0.5)
            if not ok:
                raise HubsoftPainelError('Login no painel nao concluiu (preso em /login).')
            time.sleep(1.5)  # folga pro AngularJS bindar

            for c in driver.get_cookies():
                self.session.cookies.set(c['name'], c['value'], domain=c.get('domain'))

            storage = driver.execute_script(
                "var out={};"
                "Object.keys(localStorage).forEach(k=>out['local_'+k]=localStorage[k]);"
                "Object.keys(sessionStorage).forEach(k=>out['session_'+k]=sessionStorage[k]);"
                "return out;"
            )
            token = self._extrair_jwt(storage)
            if not token:
                raise HubsoftPainelError('Login ok mas nenhum JWT encontrado no storage.')
            self._aplicar_token(token, com_cookies=True)
            self._salvar_token_cache(token)
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

    @staticmethod
    def _extrair_jwt(storage: dict):
        """Acha o JWT no dump de localStorage/sessionStorage (mesma heuristica do robo_v2)."""
        for _k, v in (storage or {}).items():
            if isinstance(v, str) and v.count('.') == 2 and len(v) > 100:
                return v
            try:
                obj = json.loads(v) if isinstance(v, str) and v.startswith('{') else None
            except Exception:
                obj = None
            if isinstance(obj, dict):
                for tk in ('token', 'access_token', 'accessToken', 'jwt'):
                    val = obj.get(tk)
                    if isinstance(val, str) and len(val) > 50:
                        return val
        return None

    # ------------------------------------------------------------------
    # HTTP com log
    # ------------------------------------------------------------------

    def _request(self, metodo: str, path: str, *, json_body=None, params=None, lead=None) -> dict:
        self._garantir_sessao()
        url = f'{self.api_base}{path}'
        status = None
        corpo = {}
        sucesso = False
        try:
            resp = self.session.request(
                metodo, url, json=json_body, params=params, timeout=_TIMEOUT_HTTP)
            status = resp.status_code
            try:
                corpo = resp.json()
            except Exception:
                corpo = {'_texto': (resp.text or '')[:2000]}
            sucesso = 200 <= status < 300
            if not sucesso:
                raise HubsoftPainelError(f'{metodo} {path} devolveu HTTP {status}')
            return corpo
        finally:
            self._log(metodo, path, json_body or params or {}, corpo, status, sucesso, lead)

    def _get(self, path, *, params=None, lead=None):
        return self._request('GET', path, params=params, lead=lead)

    def _post(self, path, *, json_body=None, lead=None):
        return self._request('POST', path, json_body=json_body, lead=lead)

    def _log(self, metodo, endpoint, payload, resposta, status, sucesso, lead):
        try:
            from apps.integracoes.models import LogIntegracao
            LogIntegracao.all_tenants.create(
                tenant=self.integracao.tenant,
                integracao=self.integracao,
                lead=lead if getattr(lead, 'pk', None) else None,
                endpoint=endpoint[:500],
                metodo=metodo if metodo in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE') else 'POST',
                payload_enviado=self._seguro(payload),
                resposta_recebida=self._seguro(resposta),
                status_code=status,
                sucesso=bool(sucesso),
            )
        except Exception:
            logger.exception('hubsoft_painel: falha ao registrar LogIntegracao')

    @staticmethod
    def _seguro(valor):
        """Garante JSON serializavel e limita tamanho no log."""
        try:
            json.dumps(valor)
            return valor
        except Exception:
            return {'_repr': str(valor)[:2000]}

    # ------------------------------------------------------------------
    # LEITURA (Fase 1) — validam o login sem nenhuma escrita
    # ------------------------------------------------------------------

    def schema_cache(self) -> dict:
        """GET /api/v1/cliente/create: schema do form (grupos, vendedores, formas, vencimentos)."""
        return self._get('/api/v1/cliente/create')

    def get_cliente(self, id_cliente: int, *, lead=None) -> dict:
        return self._get(f'/api/v1/cliente/{int(id_cliente)}', lead=lead)

    def obter_servico_edit(self, id_cliente_servico: int, *, lead=None) -> dict:
        return self._get(f'/api/v1/cliente/servico/{int(id_cliente_servico)}/edit', lead=lead)

    def buscar_cep(self, cep: str) -> dict:
        cep_digitos = ''.join(ch for ch in str(cep or '') if ch.isdigit())
        return self._post('/api/v1/endereco/cep/buscar',
                          json_body={'cep': cep_digitos, 'tipo_busca': 'cep'})


def hubsoft_painel_do_tenant(tenant, *, integracao_id=None, perfil=None):
    """Fabrica o service do painel a partir da IntegracaoAPI tipo hubsoft_painel do
    tenant. Espelha `hubsoft_do_tenant`. Com `integracao_id` pega essa conta; sem,
    pega a primeira ativa. `perfil` (PerfilConversaoHubsoft) e opcional aqui e
    obrigatorio nas escritas."""
    from apps.integracoes.models import IntegracaoAPI
    qs = IntegracaoAPI.all_tenants.filter(tenant=tenant, tipo='hubsoft_painel', ativa=True)
    if integracao_id:
        qs = qs.filter(pk=integracao_id)
    integ = qs.order_by('nome').first()
    if integ is None:
        return None
    return HubsoftPainelService(integ, perfil=perfil)
