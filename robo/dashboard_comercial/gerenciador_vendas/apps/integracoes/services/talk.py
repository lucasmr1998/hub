"""
Service pra plataforma Talk (Matrix do Brasil — PABX/softphone).

Endpoints usados:
- GET /ws/rest/restGerenciaAgente.php?modulo=listaagentes&token=X
  → lista agentes cadastrados (cod_agente + nom_agente)
- GET /ws/rest/restRastreabilidade.php?query={num_token, dat_inicial, dat_final, num_origem}
  → lista chamadas por telefone de origem numa data

Uso:
    from apps.integracoes.services.talk import TalkService
    svc = TalkService.from_tenant(tenant)  # busca IntegracaoAPI(tipo='talk')
    chamadas = svc.listar_chamadas_por_telefone(tel='35991897675', data='2026-07-02')
    agentes = svc.listar_agentes()  # {cod_agente: nom_agente}
"""
import json
import logging
from typing import Optional

import requests

from apps.integracoes.models import IntegracaoAPI

logger = logging.getLogger(__name__)


class TalkServiceError(Exception):
    pass


class TalkService:
    def __init__(self, integracao: IntegracaoAPI):
        if integracao.tipo != 'talk':
            raise TalkServiceError(f'Integracao {integracao.pk} nao eh do tipo talk')
        self.integracao = integracao
        self.base_url = integracao.base_url.rstrip('/')
        extras = integracao.configuracoes_extras or {}
        self.token = extras.get('token') or ''
        if not self.token:
            raise TalkServiceError(f'IntegracaoAPI {integracao.pk} sem token em configuracoes_extras.token')

    @classmethod
    def from_tenant(cls, tenant) -> 'TalkService':
        integ = IntegracaoAPI.all_tenants.filter(tenant=tenant, tipo='talk', ativa=True).first()
        if not integ:
            raise TalkServiceError(f'Nenhuma IntegracaoAPI talk ativa em {tenant.slug}')
        return cls(integ)

    def _get(self, endpoint: str, params: dict) -> dict:
        url = f'{self.base_url}/{endpoint.lstrip("/")}'
        try:
            r = requests.get(url, params=params, timeout=20)
        except requests.RequestException as e:
            raise TalkServiceError(f'erro de rede: {e}') from e
        if r.status_code != 200:
            raise TalkServiceError(f'HTTP {r.status_code}: {r.text[:200]}')
        try:
            return r.json()
        except ValueError:
            raise TalkServiceError(f'resposta nao eh JSON: {r.text[:200]}')

    def listar_agentes(self) -> list[dict]:
        """Retorna lista bruta de agentes (dict com cod_agente, nom_agente, dat_termino...).

        Filtre por `dat_termino` vazio pra ativos.
        """
        data = self._get('/ws/rest/restGerenciaAgente.php', {'modulo': 'listaagentes', 'token': self.token})
        agentes = data.get('msg') if isinstance(data.get('msg'), list) else []
        return agentes

    def listar_chamadas_por_telefone(self, telefone: str, dat_inicial: str, dat_final: Optional[str] = None) -> list[dict]:
        """
        Rastreabilidade — retorna chamadas do telefone naquele dia.

        Args:
            telefone: numero de origem so digitos (ex '35991897675')
            dat_inicial: 'YYYY-MM-DD'
            dat_final: 'YYYY-MM-DD' (default = dat_inicial)

        Returns:
            lista com dict {dat_ligacao, cod_cdr, nom_agente, nom_resposta, num_seg_bilhetado, ...}
        """
        if not dat_final:
            dat_final = dat_inicial
        query = json.dumps({
            'num_token': self.token,
            'dat_inicial': dat_inicial,
            'dat_final': dat_final,
            'num_origem': telefone,
        })
        data = self._get('/ws/rest/restRastreabilidade.php', {'query': query})
        return data.get('retorno') or []
