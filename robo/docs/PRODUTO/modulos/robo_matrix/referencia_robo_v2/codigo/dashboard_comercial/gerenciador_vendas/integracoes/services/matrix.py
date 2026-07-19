"""
Serviço para comunicação com a API Matrix (agendamento de instalação).
Segue o mesmo padrão do HubsoftService.
"""
import logging
import time

import requests

from integracoes.models import IntegracaoAPI, LogIntegracao

logger = logging.getLogger(__name__)


class MatrixServiceError(Exception):
    pass


class MatrixService:
    def __init__(self, integracao: IntegracaoAPI):
        if integracao.tipo != 'matrix':
            raise MatrixServiceError(f"Integração '{integracao.nome}' não é do tipo matrix.")
        self.integracao = integracao
        self.base_url = integracao.base_url.rstrip('/')
        self.config = integracao.configuracoes_extras or {}

    # ------------------------------------------------------------------
    # APIs públicas
    # ------------------------------------------------------------------

    def consultar_datas_disponiveis(self, data_referencia, lead=None):
        """GET /consultar_datas_sem_domingo?data_referencia=DD/MM/YYYY"""
        endpoint = '/consultar_datas_sem_domingo'
        params = {'data_referencia': data_referencia}
        return self._get(endpoint, params, lead=lead)

    def consultar_agenda(self, cidade, data_referencia, turno, qtd_vagas=1, lead=None):
        """GET /consultar_agenda?cidade=X&data_referencia=DD/MM/YYYY&turno=X&qtd_vagas=1"""
        endpoint = '/consultar_agenda'
        params = {
            'cidade': cidade,
            'data_referencia': data_referencia,
            'turno': turno,
            'qtd_vagas': qtd_vagas,
        }
        return self._get(endpoint, params, lead=lead)

    def abrir_atendimento(self, id_cliente_servico, nome, telefone, descricao, lead=None):
        """POST /abrir_atendimento"""
        endpoint = '/abrir_atendimento'
        payload = {
            'id_cliente_servico': id_cliente_servico,
            'nome': nome,
            'telefone': telefone,
            'descricao': descricao,
            'id_tipo_atendimento': self.config.get('id_tipo_atendimento', 535),
            'id_atendimento_status': self.config.get('id_status_atendimento', 1),
            'id_usuario_responsavel': self.config.get('id_user_responsavel', 1618),
            'empresa': self.config.get('nome_empresa_api', 'megalink'),
        }
        return self._post(endpoint, payload, lead=lead)

    def abrir_os(self, id_atendimento, id_agenda_os, data_inicio, hora_inicio, id_tecnico, lead=None):
        """POST /abrir_os"""
        endpoint = '/abrir_os'
        payload = {
            'id_atendimento': id_atendimento,
            'id_tipo_ordem_servico': self.config.get('id_tipo_os', 702),
            'id_agenda_ordem_servico': id_agenda_os,
            'data_inicio_programado': data_inicio,
            'data_termino_programado': data_inicio,
            'hora_inicio_programado': hora_inicio,
            'duracao': self.config.get('duracao', '01:30:00'),
            'status': self.config.get('status_os_api', 'pendente'),
            'id_tecnico': id_tecnico,
            'empresa': self.config.get('nome_empresa_api', 'megalink'),
        }
        return self._post(endpoint, payload, lead=lead)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, endpoint, params, lead=None):
        url = f"{self.base_url}{endpoint}"
        inicio = time.time()
        try:
            resp = requests.get(url, params=params, timeout=30)
            tempo_ms = int((time.time() - inicio) * 1000)
        except requests.RequestException as exc:
            tempo_ms = int((time.time() - inicio) * 1000)
            self._registrar_log(
                endpoint=endpoint, metodo='GET', payload=params,
                resposta={}, status_code=0, sucesso=False,
                erro=str(exc), tempo_ms=tempo_ms, lead=lead,
            )
            raise MatrixServiceError(f"Falha de conexão: {exc}") from exc

        resposta = self._parse_response(resp)
        sucesso = resp.status_code in (200, 201) and resposta.get('status') == 'success'

        self._registrar_log(
            endpoint=endpoint, metodo='GET', payload=params,
            resposta=resposta, status_code=resp.status_code,
            sucesso=sucesso,
            erro='' if sucesso else f"HTTP {resp.status_code}: {resposta.get('msg', resposta.get('message', ''))}",
            tempo_ms=tempo_ms, lead=lead,
        )

        if not sucesso:
            raise MatrixServiceError(f"Erro na API Matrix ({endpoint}): {resposta}")

        return resposta

    def _post(self, endpoint, payload, lead=None):
        url = f"{self.base_url}{endpoint}"
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        inicio = time.time()
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            tempo_ms = int((time.time() - inicio) * 1000)
        except requests.RequestException as exc:
            tempo_ms = int((time.time() - inicio) * 1000)
            self._registrar_log(
                endpoint=endpoint, metodo='POST', payload=payload,
                resposta={}, status_code=0, sucesso=False,
                erro=str(exc), tempo_ms=tempo_ms, lead=lead,
            )
            raise MatrixServiceError(f"Falha de conexão: {exc}") from exc

        resposta = self._parse_response(resp)
        sucesso = resp.status_code in (200, 201) and resposta.get('status') != 'error'

        self._registrar_log(
            endpoint=endpoint, metodo='POST', payload=payload,
            resposta=resposta, status_code=resp.status_code,
            sucesso=sucesso,
            erro='' if sucesso else f"HTTP {resp.status_code}: {resposta.get('msg', resposta.get('message', ''))}",
            tempo_ms=tempo_ms, lead=lead,
        )

        if not sucesso:
            raise MatrixServiceError(f"Erro na API Matrix ({endpoint}): {resposta}")

        return resposta

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(resp):
        try:
            return resp.json()
        except ValueError:
            return {'raw': resp.text[:2000]}

    def _registrar_log(self, *, endpoint, metodo, payload, resposta,
                       status_code, sucesso, erro, tempo_ms, lead=None):
        try:
            LogIntegracao.objects.create(
                integracao=self.integracao,
                lead=lead,
                endpoint=endpoint,
                metodo=metodo,
                payload_enviado=payload,
                resposta_recebida=resposta,
                status_code=status_code,
                sucesso=sucesso,
                mensagem_erro=erro,
                tempo_resposta_ms=tempo_ms,
            )
        except Exception as exc:
            logger.error("Erro ao registrar log Matrix: %s", exc)
