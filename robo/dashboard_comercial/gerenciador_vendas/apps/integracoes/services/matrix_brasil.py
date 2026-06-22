"""
Cliente HTTP pra Matrix Brasil (matrixdobrasil.ai) — instancia por tenant.

Hoje suporta v1 (token raw no header Authorization). v2 (JWT com refresh)
fica como evolucao quando necessario.

Uso tipico:
    from apps.integracoes.services.matrix_brasil import MatrixBrasilService
    svc = MatrixBrasilService.from_tenant(tenant)
    dados = svc.consultar_atendimento(codigo_atendimento=1014193)
    print(dados['login_agente'])

Doc da API: robo/docs/PRODUTO/integracoes/apis/matrix/

Ver tambem o cliente legado em apps.comercial.atendimento.services.atendimento_service
(usa env var MATRIX_API_TOKEN global e gera HTML pra histórico). Este aqui e
multi-tenant e estruturado pra sync programatica.
"""
import logging
import requests

logger = logging.getLogger(__name__)


class MatrixBrasilServiceError(Exception):
    """Erro de chamada a API Matrix Brasil."""


class MatrixBrasilService:
    """Cliente Matrix Brasil v1 por tenant."""

    def __init__(self, base_url, token, *, timeout=20):
        if not base_url or not token:
            raise MatrixBrasilServiceError('Matrix Brasil sem base_url ou token configurado')
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.timeout = timeout

    @classmethod
    def from_tenant(cls, tenant):
        """Resolve config via IntegracaoAPI(tipo='n8n', nome contendo Matrix).

        Pega `base_url` e `access_token` da IntegracaoAPI ativa do tenant.
        Convencao: na Nuvyon a IntegracaoAPI Matrix tem nome 'Matrix Nuvyon'.
        """
        from apps.integracoes.models import IntegracaoAPI
        integracao = IntegracaoAPI.all_tenants.filter(
            tenant=tenant, ativa=True, tipo='n8n',
        ).filter(nome__icontains='matrix').first()
        if not integracao:
            raise MatrixBrasilServiceError(
                f'Tenant {tenant.slug} sem IntegracaoAPI Matrix ativa configurada'
            )
        return cls(integracao.base_url, integracao.access_token)

    def _headers(self):
        return {'Authorization': self.token, 'Content-Type': 'application/json'}

    # ------------------------------------------------------------------
    # Atendimentos
    # ------------------------------------------------------------------
    def consultar_atendimento(self, codigo_atendimento):
        """GET /rest/v1/atendimento?codigo_atendimento=<id>

        Retorna dict com chaves: id_atendimento, protocolo, data_entrada,
        id_status_atendimento, status, id_agente, agente, login_agente,
        mensagens (lista), contato (dict), etc.

        Levanta MatrixBrasilServiceError em erro de auth/HTTP.
        """
        url = f'{self.base_url}/rest/v1/atendimento'
        try:
            r = requests.get(url, headers=self._headers(),
                             params={'codigo_atendimento': str(codigo_atendimento)},
                             timeout=self.timeout)
        except requests.RequestException as e:
            raise MatrixBrasilServiceError(f'Erro de rede: {e}')
        if r.status_code == 401 or r.status_code == 403:
            raise MatrixBrasilServiceError(f'Token Matrix invalido (HTTP {r.status_code})')
        if r.status_code != 200:
            raise MatrixBrasilServiceError(f'HTTP {r.status_code}: {r.text[:200]}')
        try:
            return r.json()
        except ValueError:
            raise MatrixBrasilServiceError(f'Resposta nao-JSON: {r.text[:200]}')

    # ------------------------------------------------------------------
    # Agentes (uteis pra debug + popular login_matrix)
    # ------------------------------------------------------------------
    def listar_agentes(self):
        """GET /rest/v1/agentes — lista completa. Retorna list[dict]."""
        url = f'{self.base_url}/rest/v1/agentes'
        r = requests.get(url, headers=self._headers(), timeout=self.timeout)
        if r.status_code != 200:
            raise MatrixBrasilServiceError(f'HTTP {r.status_code}: {r.text[:200]}')
        return r.json()

    def buscar_agente(self, login):
        """GET /rest/v1/agente/{login} — retorna dict com cod_agente + dados."""
        url = f'{self.base_url}/rest/v1/agente/{login}'
        r = requests.get(url, headers=self._headers(), timeout=self.timeout)
        if r.status_code != 200:
            raise MatrixBrasilServiceError(f'HTTP {r.status_code}: {r.text[:200]}')
        try:
            d = r.json()
            return d[0] if isinstance(d, list) and d else d
        except ValueError:
            raise MatrixBrasilServiceError(f'Resposta nao-JSON: {r.text[:200]}')

    # ------------------------------------------------------------------
    # Listagem analitica (paginada) — pra extracao em massa
    # ------------------------------------------------------------------
    def listar_atendimentos_analitico(self, data_inicial, data_final,
                                       servico_nome=None, page=1, limit=300):
        """GET /rest/v1/relAtAnalitico — paginado, datas YYYY-MM-DD.

        Filtro `servico` aceita o NOME da fila como string (descoberta
        empirica: passar id_servico int e ignorado silenciosamente; passar
        o nome funciona). Ex.: servico_nome='NOVO CLIENTE'.

        Retorna o dict bruto: {page, total, records, rows[], grafico}.
        rows[] tem id_atendimento, contato, telefone, cpf, agente, servico,
        datas e contadores (qtd_cliente/agente/auto), sem mensagens.
        Pra mensagens use consultar_atendimento(codigo).
        """
        params = {
            'data_inicial': data_inicial,
            'data_final': data_final,
            'page': page,
            'limit': limit,
        }
        if servico_nome:
            params['servico'] = servico_nome
        url = f'{self.base_url}/rest/v1/relAtAnalitico'
        try:
            r = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise MatrixBrasilServiceError(f'Erro de rede: {e}')
        if r.status_code != 200:
            raise MatrixBrasilServiceError(f'HTTP {r.status_code}: {r.text[:200]}')
        try:
            return r.json()
        except ValueError:
            raise MatrixBrasilServiceError(f'Resposta nao-JSON: {r.text[:200]}')
