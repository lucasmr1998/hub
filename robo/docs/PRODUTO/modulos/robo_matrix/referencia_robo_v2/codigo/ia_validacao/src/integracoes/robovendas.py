"""Cliente HTTP para a API Django do Robo Vendas (+ apimatrix para agendamento Hubsoft).

Cobre todos os endpoints que o flow.json original consumia:
- Leads: registrar, atualizar, buscar, tags, status, imagens
- Histórico: registrar transição
- Hubsoft (via Django): status de migração lead → cliente
- ApiMatrix: consultar datas, agenda, abrir atendimento, abrir OS
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from src.config import config

logger = logging.getLogger(__name__)


def _post_com_retry(client: httpx.Client, url: str, json: dict, tentativas: int = 3) -> httpx.Response | None:
    """POST com retry em 503/429 (rate limit do nginx). Backoff 0.5s, 1s, 2s."""
    delay = 0.5
    for i in range(tentativas):
        try:
            r = client.post(url, json=json)
            if r.status_code in (429, 503):
                if i < tentativas - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 503) and i < tentativas - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    return None


# Mapeamento: chave do dados_extraidos da IA → campo do LeadProspecto
MAPEAMENTO_CAMPOS: dict[str, str] = {
    'nome': 'nome_razaosocial',
    'cpf': 'cpf_cnpj',
    'rg': 'rg',
    'email': 'email',
    'data_nascimento': 'data_nascimento',
    'cidade': 'cidade',
    'estado': 'estado',
    'bairro': 'bairro',
    'rua': 'rua',
    'logradouro': 'rua',
    'cep': 'cep',
    'numero_residencia': 'numero_residencia',
    'ponto_referencia': 'ponto_referencia',
    'id_plano_rp': 'id_plano_rp',
    'id_dia_vencimento': 'id_dia_vencimento',
    'valor': 'valor',
}


# Mapeamento de plano falado pelo cliente → id_plano_rp + valor
# (ids reais batidos do flow.json original)
PLANOS: dict[str, dict[str, Any]] = {
    '300':  {'id_plano_rp': 1647, 'valor': 79.90, 'titulo': 'Plano de 300MB'},
    '620':  {'id_plano_rp': 1649, 'valor': 99.90, 'titulo': 'Plano de 620MB'},
    '1g':   {'id_plano_rp': 1648, 'valor': 129.90, 'titulo': 'Plano de 1GB Turbo'},
    '1giga': {'id_plano_rp': 1648, 'valor': 129.90, 'titulo': 'Plano de 1GB Turbo'},
    '1000': {'id_plano_rp': 1648, 'valor': 129.90, 'titulo': 'Plano de 1GB Turbo'},
    '2g':   {'id_plano_rp': 1650, 'valor': 169.90, 'titulo': 'Plano de 2GB'},
    '2giga': {'id_plano_rp': 1650, 'valor': 169.90, 'titulo': 'Plano de 2GB'},
    '2000': {'id_plano_rp': 1650, 'valor': 169.90, 'titulo': 'Plano de 2GB'},
    'ponto': {'id_plano_rp': 2088, 'valor': 149.90, 'titulo': '1 Giga + Ponto Adicional'},
}


# Mapeamento de dia falado → id_dia_vencimento (ids do flow original)
DIAS_VENCIMENTO: dict[int, int] = {
    1: 28,
    5: 9,
    10: 5,
    15: 5,
    20: 6,
    25: 6,
}


class RoboVendasClient:
    """Cliente HTTP minimalista para o backend Django + apimatrix."""

    def __init__(self, base_url: str, apimatrix_url: str = '', timeout: float = 15.0):
        self.base_url = base_url.rstrip('/')
        self.apimatrix_url = apimatrix_url.rstrip('/')
        self.timeout = timeout
        self._cliente = httpx.Client(timeout=timeout)

    # ────────────────────────────────────────────────────────────────────
    # LEADS
    # ────────────────────────────────────────────────────────────────────

    def buscar_lead_por_telefone(self, telefone: str) -> int | None:
        try:
            r = self._cliente.get(
                f'{self.base_url}/api/consultar/leads/',
                params={'search': telefone, 'ativo': 'true', 'page': 1},  # sem filtro de origem: Matrix cria leads com origem 'conta N'
            )
            r.raise_for_status()
            results = r.json().get('results') or []
            if results:
                return results[0].get('id')
        except Exception as e:
            logger.warning(f'buscar_lead_por_telefone falhou: {e}')
        return None

    def verificar_lead_existe(self, telefone: str) -> tuple[bool, int | None]:
        """(consulta_ok, lead_id) — distingue 'lead NÃO existe' de instabilidade.

        consulta_ok=True + lead_id=None → a API respondeu 200 e NÃO há lead para
        este telefone (ex.: lead apagado, mas o flow ainda carrega o id antigo).
        consulta_ok=False → erro/timeout (instabilidade real, não conclui nada).
        """
        try:
            r = self._cliente.get(
                f'{self.base_url}/api/consultar/leads/',
                params={'search': telefone, 'page': 1},  # sem filtro de origem
            )
            if r.status_code != 200:
                return False, None
            results = r.json().get('results') or []
            return True, (results[0].get('id') if results else None)
        except Exception as e:
            logger.warning(f'verificar_lead_existe({telefone}) falhou: {e}')
            return False, None

    def consultar_lead_completo(self, lead_id: int | None = None,
                                 telefone: str | None = None) -> dict[str, Any] | None:
        """Busca o registro completo do lead — por id ou telefone.

        Tenta primeiro by-id (mais barato), com retry em 503/429; cai pro
        search por telefone se id falhar. Evita None em sobrecarga do nginx.
        """
        # Tentativa 1: por id, com retry em 503/429
        if lead_id:
            url = f'{self.base_url}/api/consultar/leads/{lead_id}/'
            delay = 0.4
            for i in range(3):
                try:
                    r = self._cliente.get(url)
                    if r.status_code in (429, 503) and i < 2:
                        time.sleep(delay)
                        delay *= 2
                        continue
                    if r.status_code == 200:
                        return r.json()
                    # 404 é resposta legítima (endpoint não existe pra by-id em
                    # algumas instalações) → cai pro fallback de telefone abaixo.
                    break
                except Exception as e:
                    logger.warning(f'consultar_lead_completo by-id({lead_id}) erro: {e}')
                    break
        # Tentativa 2: por telefone (search), também com retry
        if telefone:
            url = f'{self.base_url}/api/consultar/leads/'
            params = {'search': telefone, 'page': 1}  # sem filtro de origem
            delay = 0.4
            for i in range(3):
                try:
                    r = self._cliente.get(url, params=params)
                    if r.status_code in (429, 503) and i < 2:
                        time.sleep(delay)
                        delay *= 2
                        continue
                    r.raise_for_status()
                    results = r.json().get('results') or []
                    if results:
                        return results[0]
                    break
                except Exception as e:
                    logger.warning(f'consultar_lead_completo search({telefone}) erro: {e}')
                    break
        return None

    def registrar_lead(self, telefone: str, nome_provisorio: str = 'Lead WhatsApp') -> int | None:
        try:
            payload = {
                'nome_razaosocial': nome_provisorio,
                'telefone': telefone,
                'origem': 'whatsapp',
                'canal_entrada': 'whatsapp',
                'tipo_entrada': 'contato_whatsapp',
                'status_api': 'processamento_manual',
                'id_origem': '106',
                'id_origem_servico': '74',
                'id_vendedor_rp': 1618,
            }
            r = _post_com_retry(self._cliente, f"{self.base_url}/api/leads/registrar/", payload)
            r.raise_for_status()
            return r.json().get('id')
        except Exception as e:
            logger.warning(f'registrar_lead falhou: {e}')
            return None

    def atualizar_lead(self, lead_id: int, campos: dict[str, Any]) -> bool:
        if not campos:
            return True
        try:
            payload = {'termo_busca': 'id', 'busca': lead_id, **campos}
            r = _post_com_retry(self._cliente, f'{self.base_url}/api/leads/atualizar/', payload)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f'atualizar_lead({lead_id}) falhou: {e}')
            return False

    def atualizar_status(self, lead_id: int, status_api: str, observacoes: str = '') -> bool:
        """Atalho pra mudar o status_api do lead em momentos chave do fluxo."""
        campos = {'status_api': status_api}
        if observacoes:
            campos['observacoes'] = observacoes
        return self.atualizar_lead(lead_id, campos)

    def atualizar_tags(self, lead_id: int, tags_add: list[str] | None = None,
                       tags_remove: list[str] | None = None) -> bool:
        try:
            payload = {
                'lead_id': lead_id,
                'tags_add': tags_add or [],
                'tags_remove': tags_remove or [],
            }
            r = _post_com_retry(self._cliente, f'{self.base_url}/api/leads/tags/', payload)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f'atualizar_tags({lead_id}) falhou: {e}')
            return False

    # ────────────────────────────────────────────────────────────────────
    # IMAGENS / DOCUMENTAÇÃO
    # ────────────────────────────────────────────────────────────────────

    def registrar_imagem(self, lead_id: int, link_url: str, descricao: str,
                          status_validacao: str = '', observacao: str = '') -> bool:
        """Registra uma imagem enviada pelo cliente. Descricao tipica:
        'selfie_com_doc' | 'frente_doc' | 'verso_doc' | 'comprovante_residencia'.

        Se status_validacao for passado (ex: 'documentos_validos' quando IA
        aprovou), a imagem já é criada com esse status no Django (evita ficar
        em 'pendente' aguardando ação humana).
        """
        try:
            payload = {'lead_id': lead_id, 'link_url': link_url, 'descricao': descricao}
            if status_validacao:
                payload['status_validacao'] = status_validacao
            if observacao:
                payload['observacao_validacao'] = observacao
            r = _post_com_retry(self._cliente, f'{self.base_url}/api/leads/imagens/registrar/', payload)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f'registrar_imagem({lead_id}) falhou: {e}')
            return False

    # ────────────────────────────────────────────────────────────────────
    # NEW SERVICE — contratação de novo serviço (cliente Hubsoft existente)
    # ────────────────────────────────────────────────────────────────────

    def criar_new_service(self, lead_id: int) -> int | None:
        """Cria (ou reaproveita) um NewService em coleta. Retorna o id."""
        try:
            r = _post_com_retry(
                self._cliente,
                f'{self.base_url}/api/new-service/criar/',
                {'lead_id': lead_id},
            )
            r.raise_for_status()
            return (r.json().get('new_service') or {}).get('id')
        except Exception as e:
            logger.warning(f'criar_new_service(lead={lead_id}) falhou: {e}')
            return None

    def _get_com_retry(self, url: str, params: dict, tentativas: int = 3) -> httpx.Response | None:
        """GET com retry em 503/429 (nginx sob carga)."""
        delay = 0.5
        for i in range(tentativas):
            try:
                r = self._cliente.get(url, params=params)
                if r.status_code in (429, 503):
                    if i < tentativas - 1:
                        time.sleep(delay)
                        delay *= 2
                        continue
                r.raise_for_status()
                return r
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 503) and i < tentativas - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
        return None

    def obter_new_service(self, new_service_id: int) -> dict[str, Any] | None:
        try:
            r = self._get_com_retry(
                f'{self.base_url}/api/new-service/obter/',
                {'id': new_service_id},
            )
            if not r:
                return None
            data = r.json()
            return data.get('new_service') if data.get('found') else None
        except Exception as e:
            logger.warning(f'obter_new_service({new_service_id}) falhou: {e}')
            return None

    def obter_new_service_em_coleta(self, lead_id: int) -> dict[str, Any] | None:
        """Busca o NewService em coleta do lead. None se não houver."""
        try:
            r = self._get_com_retry(
                f'{self.base_url}/api/new-service/obter/',
                {'lead_id': lead_id, 'status': 'em_coleta'},
            )
            if not r:
                return None
            data = r.json()
            return data.get('new_service') if data.get('found') else None
        except Exception as e:
            logger.warning(f'obter_new_service_em_coleta(lead={lead_id}) falhou: {e}')
            return None

    def atualizar_new_service(self, new_service_id: int, campos: dict[str, Any]) -> bool:
        if not campos:
            return True
        try:
            payload = {'id': new_service_id, **campos}
            r = _post_com_retry(
                self._cliente,
                f'{self.base_url}/api/new-service/atualizar/',
                payload,
            )
            r.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f'atualizar_new_service({new_service_id}) falhou: {e}')
            return False

    def registrar_imagem_new_service(
        self, new_service_id: int, link_url: str, descricao: str,
        status_validacao: str = '', observacao_validacao: str = '',
    ) -> bool:
        try:
            payload = {
                'new_service_id': new_service_id,
                'link_url': link_url,
                'descricao': descricao,
            }
            if status_validacao:
                payload['status_validacao'] = status_validacao
            if observacao_validacao:
                payload['observacao_validacao'] = observacao_validacao
            r = _post_com_retry(
                self._cliente,
                f'{self.base_url}/api/new-service/imagens/registrar/',
                payload,
            )
            r.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f'registrar_imagem_new_service({new_service_id}) falhou: {e}')
            return False

    def finalizar_new_service(self, new_service_id: int, observacoes: str = '') -> bool:
        try:
            payload = {'id': new_service_id}
            if observacoes:
                payload['observacoes'] = observacoes
            r = _post_com_retry(
                self._cliente,
                f'{self.base_url}/api/new-service/finalizar/',
                payload,
            )
            r.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f'finalizar_new_service({new_service_id}) falhou: {e}')
            return False

    # ────────────────────────────────────────────────────────────────────
    # FLUXO UPGRADE (conversacional, turno a turno)
    # ────────────────────────────────────────────────────────────────────
    def turno_upgrade(self, lead_id: int, mensagem: str = '') -> dict[str, Any] | None:
        """Um turno do fluxo de upgrade no Django.

        mensagem vazia  → "mostrar" a pergunta atual (e finalizar se for o fim).
        mensagem cheia   → "responder" a pergunta atual e avançar.
        Devolve o dict do endpoint /api/upgrade-conversa/turno/ ou None.
        """
        try:
            r = _post_com_retry(
                self._cliente,
                f'{self.base_url}/api/upgrade-conversa/turno/',
                {'lead_id': lead_id, 'mensagem': mensagem or ''},
            )
            if not r:
                return None
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f'turno_upgrade(lead={lead_id}) falhou: {e}')
            return None

    # ────────────────────────────────────────────────────────────────────
    # HISTÓRICO
    # ────────────────────────────────────────────────────────────────────

    def registrar_historico(
        self, telefone: str, lead_id: int | None, status: str,
        observacoes: str = '', nome_contato: str = '',
        protocolo: str = '', codigo_atendimento: str = '',
    ) -> bool:
        try:
            payload = {
                'telefone': telefone,
                'nome_contato': nome_contato,
                'origem_contato': 'whatsapp',
                'status': status,
                'observacoes': observacoes,
            }
            if lead_id:
                payload['lead_id'] = lead_id
            if protocolo:
                payload['protocolo_atendimento'] = protocolo
            if codigo_atendimento:
                payload['codigo_atendimento'] = codigo_atendimento
            r = _post_com_retry(self._cliente, f'{self.base_url}/api/historicos/registrar/', payload)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f'registrar_historico falhou: {e}')
            return False

    # ────────────────────────────────────────────────────────────────────
    # HUBSOFT (via integração Django)
    # ────────────────────────────────────────────────────────────────────

    def hubsoft_status(self, lead_id: int) -> dict[str, Any] | None:
        """Consulta se o lead já virou cliente no Hubsoft e doc foi validada.

        Retorno: {eh_cliente_hubsoft, servicos: [...], lead.documentacao_validada, ...}
        """
        try:
            r = self._cliente.get(
                f'{self.base_url}/integracoes/api/lead/hubsoft-status/',
                params={'lead_id': lead_id},
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f'hubsoft_status({lead_id}) falhou: {e}')
            return None

    def verificar_cliente_por_cpf(self, lead_id: int) -> dict[str, Any] | None:
        """Pergunta ao Django se o CPF já é cliente Hubsoft.

        Django consulta a API Hubsoft, cria/atualiza ClienteHubsoft local
        e (se achar) seta status_api='cliente_ativo' no lead.

        Retorna {eh_cliente: bool, cliente_hubsoft_id?, nome?, ...} ou None.
        """
        try:
            r = self._cliente.post(
                f'{self.base_url}/integracoes/api/verificar-cliente-cpf/{lead_id}/',
                json={},
                timeout=45,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f'verificar_cliente_por_cpf({lead_id}) falhou: {e}')
            return None

    def consultar_viabilidade(self, cep: str = '', cidade: str = '', uf: str = '') -> dict[str, Any] | None:
        """Consulta viabilidade técnica (cidade/bairro) no Django.

        Prioriza `cep` (resolve cidade via ViaCEP no Django e cruza com o
        cadastro); cai para `cidade`+`uf` se não houver CEP. Retorno bruto do
        endpoint `/api/viabilidade/` (ver `vendas_web.views.api_viabilidade`):
        {sucesso, tem_viabilidade?, registros: [{cidade, estado, atende_cidade_inteira,
        bairros: [{nome, cep}], ...}], ...} ou None se a chamada falhar.
        """
        params: dict[str, str] = {}
        if cep:
            params['cep'] = cep
        if cidade:
            params['cidade'] = cidade
        if uf:
            params['uf'] = uf
        if not params:
            return None
        try:
            r = self._cliente.get(f'{self.base_url}/api/viabilidade/', params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f'consultar_viabilidade({params}) falhou: {e}')
            return None

    def proxima_instalacao_lead(self, lead_id: int) -> dict[str, Any] | None:
        """Retorna info da OS de instalação em aberto do lead (sem nomes)."""
        try:
            r = self._cliente.get(
                f'{self.base_url}/integracoes/api/lead/{lead_id}/proxima-instalacao/',
                timeout=15,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f'proxima_instalacao_lead({lead_id}) falhou: {e}')
            return None

    def agendar_instalacao_ia(self, lead_id: int) -> dict[str, Any] | None:
        """Dispara o agendamento de instalação no Django (endpoint próprio).

        Lê turno_instalacao e data_instalacao já salvos no lead e tenta abrir
        atendimento + OS via Matrix. Retorna dict com:
        - status: 'agendado' | 'aguardando_sync' | 'erro'
        - mensagem: str
        - dados: {data, turno, horario, nome_tecnico, ...}  # se agendado
        """
        try:
            r = self._cliente.post(
                f'{self.base_url}/integracoes/api/agendar-instalacao-ia/{lead_id}/',
                json={},
                timeout=60,   # consultar_agenda + abrir_atendimento + abrir_os
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f'agendar_instalacao_ia({lead_id}) falhou: {e}')
            return None

    # ────────────────────────────────────────────────────────────────────
    # APIMATRIX (agendamento de instalação)
    # ────────────────────────────────────────────────────────────────────

    def consultar_datas_disponiveis(self, data_referencia: str) -> list[str]:
        """Retorna até 3 próximas datas com instalação disponível (sem domingo)."""
        if not self.apimatrix_url:
            return []
        try:
            r = self._cliente.get(
                f'{self.apimatrix_url}/consultar_datas_sem_domingo',
                params={'data_referencia': data_referencia},
            )
            r.raise_for_status()
            return r.json().get('datas') or []
        except Exception as e:
            logger.warning(f'consultar_datas_disponiveis falhou: {e}')
            return []

    def consultar_agenda(self, cidade: str, data_referencia: str, turno: str) -> dict[str, Any] | None:
        if not self.apimatrix_url:
            return None
        try:
            r = self._cliente.get(
                f'{self.apimatrix_url}/consultar_agenda',
                params={'cidade': cidade, 'data_referencia': data_referencia,
                        'turno': turno, 'qtd_vagas': 1},
            )
            r.raise_for_status()
            return r.json().get('dados')
        except Exception as e:
            logger.warning(f'consultar_agenda falhou: {e}')
            return None

    def abrir_atendimento(self, id_cliente_servico: int, telefone: str,
                          descricao: str, nome: str = 'ClienteVenda') -> int | None:
        if not self.apimatrix_url:
            return None
        try:
            payload = {
                'id_cliente_servico': id_cliente_servico,
                'nome': nome,
                'telefone': telefone,
                'descricao': descricao,
                'id_tipo_atendimento': 535,
                'id_atendimento_status': 1,
                'id_usuario_responsavel': 1618,
                'empresa': 'megalink',
            }
            r = self._cliente.post(f'{self.apimatrix_url}/abrir_atendimento', json=payload)
            r.raise_for_status()
            return (r.json().get('atendimento') or {}).get('id_atendimento')
        except Exception as e:
            logger.warning(f'abrir_atendimento falhou: {e}')
            return None

    def abrir_os(self, id_atendimento: int, id_agenda: int, data: str,
                 hora: str, id_tecnico: int) -> bool:
        if not self.apimatrix_url:
            return False
        try:
            payload = {
                'id_atendimento': id_atendimento,
                'id_tipo_ordem_servico': 702,
                'id_agenda_ordem_servico': id_agenda,
                'data_inicio_programado': data,
                'data_termino_programado': data,
                'hora_inicio_programado': hora,
                'duracao': '01:30:00',
                'status': 'pendente',
                'id_tecnico': id_tecnico,
                'empresa': 'megalink',
            }
            r = self._cliente.post(f'{self.apimatrix_url}/abrir_os', json=payload)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f'abrir_os falhou: {e}')
            return False

    # ────────────────────────────────────────────────────────────────────
    # ORQUESTRAÇÃO
    # ────────────────────────────────────────────────────────────────────

    def garantir_lead(self, telefone: str) -> int | None:
        lead_id = self.buscar_lead_por_telefone(telefone)
        if lead_id:
            return lead_id
        return self.registrar_lead(telefone)

    def sincronizar_dados(self, lead_id: int, dados_extraidos: dict[str, Any]) -> bool:
        """Pega os campos extraídos pela IA e manda PATCH parcial pro Django.

        Aplica:
        - Mapeamento direto de chaves (nome → nome_razaosocial, etc.)
        - Conversão plano_velocidade → id_plano_rp + valor + titulo
        - Conversão dia_vencimento → id_dia_vencimento
        """
        campos: dict[str, Any] = {}

        # Campos diretos
        for chave_ia, valor in dados_extraidos.items():
            if not valor:
                continue
            campo_django = MAPEAMENTO_CAMPOS.get(chave_ia)
            if campo_django:
                campos[campo_django] = valor

        # Plano
        plano_velocidade = dados_extraidos.get('plano_velocidade')
        if plano_velocidade:
            chave = str(plano_velocidade).strip().lower().replace(' ', '').replace('mb', '').replace('mega', '')
            plano = PLANOS.get(chave)
            if plano:
                campos['id_plano_rp'] = plano['id_plano_rp']
                campos['valor'] = plano['valor']

        # Dia vencimento
        dia = dados_extraidos.get('dia_vencimento')
        if dia is not None:
            try:
                dia_int = int(dia)
                id_venc = DIAS_VENCIMENTO.get(dia_int)
                if id_venc:
                    campos['id_dia_vencimento'] = id_venc
            except (ValueError, TypeError):
                pass

        if not campos:
            return True
        return self.atualizar_lead(lead_id, campos)


robovendas = RoboVendasClient(
    base_url=config.ROBOVENDAS_API_URL,
    apimatrix_url=getattr(config, 'APIMATRIX_URL', '') or 'https://apimatrix.megalinkpiaui.com.br',
)
