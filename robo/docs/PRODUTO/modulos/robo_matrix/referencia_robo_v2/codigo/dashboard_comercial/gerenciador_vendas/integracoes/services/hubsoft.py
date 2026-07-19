import logging
import os
import re
import time
from datetime import timedelta
from decimal import Decimal

import requests
from django.utils import timezone

from integracoes.models import (
    IntegracaoAPI, LogIntegracao, ClienteHubsoft, ServicoClienteHubsoft,
    AtendimentoHubsoft, OrdemServicoHubsoft,
)

logger = logging.getLogger(__name__)


class HubsoftServiceError(Exception):
    """Erro genérico do serviço Hubsoft."""
    pass


class HubsoftService:
    """
    Encapsula a comunicação com a API do Hubsoft.
    - Autenticação OAuth2 (password grant)
    - Cadastro de prospecto
    """

    ENDPOINT_TOKEN = '/oauth/token'
    ENDPOINT_PROSPECTO = '/api/v1/integracao/prospecto'

    def __init__(self, integracao: IntegracaoAPI):
        if integracao.tipo != 'hubsoft':
            raise HubsoftServiceError(
                f"Integração '{integracao.nome}' não é do tipo hubsoft."
            )
        self.integracao = integracao
        self.base_url = integracao.base_url.rstrip('/')

    # ------------------------------------------------------------------
    # Autenticação
    # ------------------------------------------------------------------

    def obter_token(self) -> str:
        """
        Obtém (ou reutiliza) um access_token válido.
        Cacheia o token no próprio model IntegracaoAPI.
        """
        if self.integracao.token_valido:
            return self.integracao.access_token

        url = f"{self.base_url}{self.ENDPOINT_TOKEN}"
        payload = {
            'client_id': self.integracao.client_id,
            'client_secret': self.integracao.client_secret,
            'username': self.integracao.username,
            'password': self.integracao.password,
            'grant_type': self.integracao.grant_type,
        }

        inicio = time.time()
        try:
            resp = requests.post(url, json=payload, timeout=30)
            tempo_ms = int((time.time() - inicio) * 1000)
        except requests.RequestException as exc:
            tempo_ms = int((time.time() - inicio) * 1000)
            self._registrar_log(
                endpoint=self.ENDPOINT_TOKEN,
                metodo='POST',
                payload=payload,
                resposta={},
                status_code=0,
                sucesso=False,
                erro=str(exc),
                tempo_ms=tempo_ms,
            )
            raise HubsoftServiceError(f"Falha de conexão ao obter token: {exc}") from exc

        resposta_json = {}
        try:
            resposta_json = resp.json()
        except ValueError:
            resposta_json = {'raw': resp.text[:2000]}

        self._registrar_log(
            endpoint=self.ENDPOINT_TOKEN,
            metodo='POST',
            payload={k: v for k, v in payload.items() if k != 'password'},
            resposta=resposta_json,
            status_code=resp.status_code,
            sucesso=resp.status_code == 200,
            erro='' if resp.status_code == 200 else f"HTTP {resp.status_code}",
            tempo_ms=tempo_ms,
        )

        if resp.status_code != 200:
            raise HubsoftServiceError(
                f"Erro ao obter token (HTTP {resp.status_code}): "
                f"{resposta_json}"
            )

        token = resposta_json.get('access_token', '')
        expires_in = resposta_json.get('expires_in', 3600)

        IntegracaoAPI.objects.filter(pk=self.integracao.pk).update(
            access_token=token,
            token_expira_em=timezone.now() + timedelta(seconds=int(expires_in) - 60),
        )
        self.integracao.refresh_from_db()

        return token

    # ------------------------------------------------------------------
    # Cadastro de Prospecto
    # ------------------------------------------------------------------

    def cadastrar_prospecto(self, lead) -> dict:
        """
        Envia um LeadProspecto para o Hubsoft como prospecto.
        Retorna o dict da resposta da API em caso de sucesso.
        Lança HubsoftServiceError em caso de falha.
        """
        token = self.obter_token()

        url = f"{self.base_url}{self.ENDPOINT_PROSPECTO}"
        payload = self._mapear_lead_para_hubsoft(lead)
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        inicio = time.time()
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            tempo_ms = int((time.time() - inicio) * 1000)
        except requests.RequestException as exc:
            tempo_ms = int((time.time() - inicio) * 1000)
            self._registrar_log(
                endpoint=self.ENDPOINT_PROSPECTO,
                metodo='POST',
                payload=payload,
                resposta={},
                status_code=0,
                sucesso=False,
                erro=str(exc),
                tempo_ms=tempo_ms,
                lead=lead,
            )
            raise HubsoftServiceError(f"Falha de conexão ao cadastrar prospecto: {exc}") from exc

        resposta_json = {}
        try:
            resposta_json = resp.json()
        except ValueError:
            resposta_json = {'raw': resp.text[:2000]}

        sucesso = resp.status_code in (200, 201) and resposta_json.get('status') == 'success'

        self._registrar_log(
            endpoint=self.ENDPOINT_PROSPECTO,
            metodo='POST',
            payload=payload,
            resposta=resposta_json,
            status_code=resp.status_code,
            sucesso=sucesso,
            erro='' if sucesso else f"HTTP {resp.status_code}: {resposta_json.get('msg', '')}",
            tempo_ms=tempo_ms,
            lead=lead,
        )

        if not sucesso:
            raise HubsoftServiceError(
                f"Erro ao cadastrar prospecto (HTTP {resp.status_code}): "
                f"{resposta_json}"
            )

        return resposta_json

    # ------------------------------------------------------------------
    # Consulta de Cliente
    # ------------------------------------------------------------------

    ENDPOINT_CLIENTE = '/api/v1/integracao/cliente'
    ENDPOINT_CLIENTE_ATENDIMENTO = '/api/v1/integracao/cliente/atendimento'
    ENDPOINT_CLIENTE_OS = '/api/v1/integracao/cliente/ordem_servico'

    def _get_hubsoft(self, endpoint: str, params: dict, lead=None) -> dict:
        """Helper genérico para GETs autenticados ao Hubsoft com logging."""
        token = self.obter_token()
        url = f"{self.base_url}{endpoint}"
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
        }

        inicio = time.time()
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            tempo_ms = int((time.time() - inicio) * 1000)
        except requests.RequestException as exc:
            tempo_ms = int((time.time() - inicio) * 1000)
            self._registrar_log(
                endpoint=endpoint, metodo='GET', payload=params, resposta={},
                status_code=0, sucesso=False, erro=str(exc), tempo_ms=tempo_ms, lead=lead,
            )
            raise HubsoftServiceError(f"Falha de conexão em {endpoint}: {exc}") from exc

        try:
            resposta_json = resp.json()
        except ValueError:
            resposta_json = {'raw': resp.text[:2000]}

        sucesso = resp.status_code == 200 and resposta_json.get('status') == 'success'

        self._registrar_log(
            endpoint=endpoint, metodo='GET', payload=params, resposta=resposta_json,
            status_code=resp.status_code, sucesso=sucesso,
            erro='' if sucesso else f"HTTP {resp.status_code}: {resposta_json.get('msg', '')}",
            tempo_ms=tempo_ms, lead=lead,
        )

        if not sucesso:
            raise HubsoftServiceError(
                f"Erro em {endpoint} (HTTP {resp.status_code}): {resposta_json}"
            )
        return resposta_json

    def consultar_atendimentos_cliente(self, codigo_cliente, lead=None, **filtros) -> dict:
        """
        GET /api/v1/integracao/cliente/atendimento
        Consulta atendimentos do cliente pelo codigo_cliente.
        Default: traz TODOS (pendentes + fechados). Passe apenas_pendente='sim' para só abertos.
        Filtros opcionais: apenas_pendente, limit, order_by, order_type, data_inicio, data_fim, relacoes
        """
        params = {
            'busca': 'codigo_cliente',
            'termo_busca': str(codigo_cliente),
            'apenas_pendente': filtros.pop('apenas_pendente', 'nao'),
            'limit': filtros.pop('limit', 50),
            'order_by': filtros.pop('order_by', 'data_cadastro'),
            'order_type': filtros.pop('order_type', 'desc'),
            'relacoes': filtros.pop('relacoes', 'atendimento_mensagem,ordem_servico_mensagem,checklists'),
        }
        params.update({k: v for k, v in filtros.items() if v is not None})
        return self._get_hubsoft(self.ENDPOINT_CLIENTE_ATENDIMENTO, params, lead=lead)

    def consultar_ordens_servico_cliente(self, codigo_cliente, lead=None, **filtros) -> dict:
        """
        GET /api/v1/integracao/cliente/ordem_servico
        Consulta ordens de serviço pelo codigo_cliente.
        Filtros opcionais: status, limit, order_by, order_type, data_inicio, data_fim,
        exibir_atendimento, relacoes, reservada
        """
        params = {
            'busca': 'codigo_cliente',
            'termo_busca': str(codigo_cliente),
            'limit': filtros.pop('limit', 50),
            'order_by': filtros.pop('order_by', 'data_cadastro'),
            'order_type': filtros.pop('order_type', 'desc'),
            'exibir_atendimento': filtros.pop('exibir_atendimento', 'true'),
            'relacoes': filtros.pop('relacoes', 'ordem_servico_mensagem,anexos'),
        }
        params.update({k: v for k, v in filtros.items() if v is not None})
        return self._get_hubsoft(self.ENDPOINT_CLIENTE_OS, params, lead=lead)

    # ------------------------------------------------------------------
    # Sincronização Atendimentos / OS
    # ------------------------------------------------------------------

    def sincronizar_atendimentos_os(self, cliente: ClienteHubsoft) -> dict:
        """
        Sincroniza (cria/atualiza) atendimentos e OS locais a partir da API Hubsoft.
        Retorna dict com contadores.
        """
        if not cliente.codigo_cliente:
            return {'erro': 'Cliente sem codigo_cliente'}

        resultado = {'atendimentos_criados': 0, 'atendimentos_atualizados': 0,
                     'os_criadas': 0, 'os_atualizadas': 0, 'erros': []}

        # --- ATENDIMENTOS ---
        try:
            resp = self.consultar_atendimentos_cliente(cliente.codigo_cliente, lead=cliente.lead)
            atends = resp.get('atendimentos') or resp.get('dados') or []
            if not isinstance(atends, list):
                atends = [atends]

            for a in atends:
                if not isinstance(a, dict) or not a.get('id_atendimento'):
                    continue
                defaults = {
                    'cliente': cliente,
                    'protocolo': (a.get('protocolo') or '')[:50],
                    'tipo_atendimento': (a.get('tipo_atendimento') or '')[:120],
                    'status': (a.get('status') or '')[:60],
                    'status_fechamento': (a.get('status_fechamento') or '')[:60],
                    'motivo_fechamento': (a.get('motivo_fechamento') or '')[:255],
                    'setor_responsavel': (a.get('setor_responsavel') or '')[:120],
                    'usuario_abertura': (a.get('usuario_abertura') or '')[:120],
                    'usuario_responsavel': (a.get('usuario_responsavel') or '')[:120],
                    'usuario_fechamento': (a.get('usuario_fechamento') or '')[:120],
                    'descricao_abertura': a.get('descricao_abertura') or '',
                    'descricao_fechamento': a.get('descricao_fechamento') or '',
                    'data_cadastro': (a.get('data_cadastro') or '')[:30],
                    'data_fechamento': (a.get('data_fechamento') or '')[:30],
                    'rascunho': bool(a.get('rascunho')),
                    'qtd_ordens_servico': len(a.get('ordens_servico') or []),
                    'dados_completos': a,
                }
                obj, criado = AtendimentoHubsoft.objects.update_or_create(
                    id_atendimento=a['id_atendimento'], defaults=defaults,
                )
                if criado:
                    resultado['atendimentos_criados'] += 1
                else:
                    resultado['atendimentos_atualizados'] += 1
        except Exception as exc:
            resultado['erros'].append(f'atendimentos: {exc}')
            logger.error("Erro ao sincronizar atendimentos do cliente %s: %s", cliente.pk, exc)

        # --- ORDENS DE SERVIÇO ---
        try:
            resp = self.consultar_ordens_servico_cliente(cliente.codigo_cliente, lead=cliente.lead)
            ordens = resp.get('ordens_servico') or resp.get('ordem_servico') or resp.get('dados') or []
            if not isinstance(ordens, list):
                ordens = [ordens]

            for o in ordens:
                if not isinstance(o, dict) or not o.get('id_ordem_servico'):
                    continue

                # Vincular ao atendimento local se existir
                atend_local = None
                atend_data = o.get('atendimento') or {}
                if isinstance(atend_data, dict) and atend_data.get('id_atendimento'):
                    atend_local = AtendimentoHubsoft.objects.filter(
                        id_atendimento=atend_data['id_atendimento']
                    ).first()

                defaults = {
                    'cliente': cliente,
                    'atendimento': atend_local,
                    'numero_ordem_servico': (o.get('numero_ordem_servico') or '')[:60],
                    'tipo': (o.get('tipo') or '')[:120],
                    'status': (o.get('status') or '')[:60],
                    'status_fechamento': (o.get('status_fechamento') or '')[:60],
                    'usuario_abertura': (o.get('usuario_abertura') or '')[:120],
                    'usuario_fechamento': (o.get('usuario_fechamento') or '')[:120],
                    'descricao_abertura': o.get('descricao_abertura') or '',
                    'descricao_servico': o.get('descricao_servico') or '',
                    'descricao_fechamento': o.get('descricao_fechamento') or '',
                    'data_cadastro': (o.get('data_cadastro') or '')[:30],
                    'data_inicio_programado': (o.get('data_inicio_programado') or '')[:30],
                    'data_termino_programado': (o.get('data_termino_programado') or '')[:30],
                    'data_inicio_executado': (o.get('data_inicio_executado') or '')[:30],
                    'data_termino_executado': (o.get('data_termino_executado') or '')[:30],
                    'tecnicos': o.get('tecnicos') or [],
                    'qtd_anexos': len(o.get('anexos') or []),
                    'dados_completos': o,
                }
                obj, criado = OrdemServicoHubsoft.objects.update_or_create(
                    id_ordem_servico=o['id_ordem_servico'], defaults=defaults,
                )
                if criado:
                    resultado['os_criadas'] += 1
                else:
                    resultado['os_atualizadas'] += 1
        except Exception as exc:
            resultado['erros'].append(f'os: {exc}')
            logger.error("Erro ao sincronizar OS do cliente %s: %s", cliente.pk, exc)

        return resultado

    def consultar_cliente(self, cpf_cnpj: str, lead=None) -> dict:
        """
        Consulta um cliente no Hubsoft por CPF/CNPJ.
        Retorna o dict da resposta ou lança HubsoftServiceError.
        """
        token = self.obter_token()

        cpf_cnpj_limpo = self._somente_numeros(cpf_cnpj)
        url = f"{self.base_url}{self.ENDPOINT_CLIENTE}"
        params = {'busca': 'cpf_cnpj', 'termo_busca': cpf_cnpj_limpo}
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
        }

        inicio = time.time()
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            tempo_ms = int((time.time() - inicio) * 1000)
        except requests.RequestException as exc:
            tempo_ms = int((time.time() - inicio) * 1000)
            self._registrar_log(
                endpoint=self.ENDPOINT_CLIENTE,
                metodo='GET',
                payload={'busca': 'cpf_cnpj', 'termo_busca': cpf_cnpj_limpo},
                resposta={},
                status_code=0,
                sucesso=False,
                erro=str(exc),
                tempo_ms=tempo_ms,
                lead=lead,
            )
            raise HubsoftServiceError(f"Falha de conexão ao consultar cliente: {exc}") from exc

        resposta_json = {}
        try:
            resposta_json = resp.json()
        except ValueError:
            resposta_json = {'raw': resp.text[:2000]}

        sucesso = resp.status_code == 200 and resposta_json.get('status') == 'success'

        if not sucesso:
            self._registrar_log(
                endpoint=self.ENDPOINT_CLIENTE,
                metodo='GET',
                payload={'busca': 'cpf_cnpj', 'termo_busca': cpf_cnpj_limpo},
                resposta=resposta_json,
                status_code=resp.status_code,
                sucesso=False,
                erro=f"HTTP {resp.status_code}: {resposta_json.get('msg', '')}",
                tempo_ms=tempo_ms,
                lead=lead,
            )

        if not sucesso:
            raise HubsoftServiceError(
                f"Erro ao consultar cliente (HTTP {resp.status_code}): "
                f"{resposta_json}"
            )

        # A API oficial de integração só retorna clientes ATIVOS. Se não veio
        # ninguém, tenta o banco ESPELHO (read replica) — assim clientes
        # INATIVOS/cancelados também são detectados e seguem o mesmo fluxo de
        # "cliente já cadastrado" (em vez de virarem lead novo).
        if not (resposta_json.get('clientes') or []):
            espelho = self._consultar_cliente_espelho(cpf_cnpj_limpo)
            if espelho.get('clientes'):
                return espelho

        return resposta_json

    def _consultar_cliente_espelho(self, cpf_cnpj_limpo: str) -> dict:
        """Fallback: busca o cliente no banco ESPELHO (read replica) do HubSoft.

        A API oficial só retorna clientes ativos; clientes inativos/cancelados
        ficam invisíveis e seriam tratados como lead novo. Aqui montamos a MESMA
        estrutura ({'status':'success','clientes':[...]}) a partir do espelho,
        para que clientes já cadastrados (mesmo inativos) sigam o fluxo de cliente
        existente. NUNCA levanta exceção — em qualquer falha retorna lista vazia.
        """
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=os.environ['HUBSOFT_DB_HOST'], port=os.environ['HUBSOFT_DB_PORT'],
                dbname=os.environ['HUBSOFT_DB_NAME'], user=os.environ['HUBSOFT_DB_USER'],
                password=os.environ['HUBSOFT_DB_PASSWORD'], connect_timeout=10,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning('Espelho HubSoft indisponível p/ CPF %s: %s', cpf_cnpj_limpo, exc)
            return {'status': 'success', 'clientes': []}
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id_cliente, uuid, codigo_cliente, nome_razaosocial, nome_fantasia, "
                "tipo_pessoa, cpf_cnpj, telefone_primario, telefone_secundario, "
                "email_principal, email_secundario, ativo, data_cadastro, data_nascimento, "
                "data_atualizacao, nome_pai, nome_mae "
                "FROM cliente WHERE cpf_cnpj = %s ORDER BY ativo DESC, id_cliente DESC LIMIT 1",
                [cpf_cnpj_limpo])
            row = cur.fetchone()
            if not row:
                return {'status': 'success', 'clientes': []}
            c = dict(zip([d[0] for d in cur.description], row))
            cur.execute(
                "SELECT cs.id_cliente_servico, cs.uuid, cs.id_servico, cs.numero_plano, "
                "cs.valor, COALESCE(sv.descricao, sv.nome_exibicao, '') AS nome, "
                "COALESCE(ss.descricao, '') AS status, cs.data_venda, cs.data_cadastro, "
                "cs.data_habilitacao, cs.data_cancelamento "
                "FROM cliente_servico cs "
                "LEFT JOIN servico sv ON sv.id_servico = cs.id_servico "
                "LEFT JOIN servico_status ss ON ss.id_servico_status = cs.id_servico_status "
                "WHERE cs.id_cliente = %s ORDER BY cs.id_cliente_servico DESC",
                [c['id_cliente']])
            servicos = []
            for s in cur.fetchall():
                sd = dict(zip([d[0] for d in cur.description], s))
                _s = lambda v: str(v) if v else ''
                servicos.append({
                    'id_cliente_servico': sd['id_cliente_servico'],
                    'uuid_cliente_servico': sd['uuid'] or '',
                    'id_servico': sd['id_servico'],
                    'numero_plano': sd['numero_plano'],
                    'nome': sd['nome'] or '',
                    'valor': float(sd['valor']) if sd['valor'] is not None else None,
                    'status': sd['status'] or '',
                    'data_venda': _s(sd['data_venda']),
                    'data_cadastro': _s(sd['data_cadastro']),
                    'data_habilitacao': _s(sd['data_habilitacao']),
                    'data_cancelamento': _s(sd['data_cancelamento']),
                    'vendedor': {},
                })
            _d = lambda v: str(v) if v else ''
            cliente = {
                'id_cliente': c['id_cliente'],
                'uuid_cliente': c['uuid'] or '',
                'codigo_cliente': c['codigo_cliente'],
                'nome_razaosocial': c['nome_razaosocial'] or '',
                'nome_fantasia': c['nome_fantasia'] or '',
                'tipo_pessoa': c['tipo_pessoa'] or 'pf',
                'cpf_cnpj': c['cpf_cnpj'] or '',
                'telefone_primario': c['telefone_primario'] or '',
                'telefone_secundario': c['telefone_secundario'] or '',
                'email_principal': c['email_principal'] or '',
                'email_secundario': c['email_secundario'] or '',
                'ativo': bool(c['ativo']),
                'data_cadastro': _d(c['data_cadastro']),
                'data_nascimento': _d(c['data_nascimento'])[:10],
                'data_atualizacao': _d(c['data_atualizacao']),
                'nome_pai': c['nome_pai'] or '',
                'nome_mae': c['nome_mae'] or '',
                'servicos': servicos,
            }
            logger.info('Cliente encontrado no ESPELHO (ativo=%s) p/ CPF %s: id_cliente=%s',
                        cliente['ativo'], cpf_cnpj_limpo, cliente['id_cliente'])
            return {'status': 'success', 'clientes': [cliente], '_origem': 'espelho'}
        except Exception as exc:  # noqa: BLE001
            logger.warning('Falha ao consultar espelho p/ CPF %s: %s', cpf_cnpj_limpo, exc)
            return {'status': 'success', 'clientes': []}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Sincronização de Cliente
    # ------------------------------------------------------------------

    def sincronizar_cliente(self, lead) -> ClienteHubsoft | None:
        """
        Consulta o Hubsoft pelo CPF/CNPJ do lead e cria/atualiza
        o ClienteHubsoft local. Detecta alterações entre syncs.
        Retorna o ClienteHubsoft atualizado ou None se não encontrado.
        """
        if not lead.cpf_cnpj:
            logger.warning("Lead pk=%s sem CPF/CNPJ, impossível consultar cliente.", lead.pk)
            return None

        resposta = self.consultar_cliente(lead.cpf_cnpj, lead=lead)
        clientes = resposta.get('clientes', [])

        if not clientes:
            logger.info("Nenhum cliente encontrado no Hubsoft para CPF/CNPJ %s", lead.cpf_cnpj)
            return None

        dados_cliente = clientes[0]
        return self._sincronizar_dados_cliente(dados_cliente, lead)

    def _sincronizar_dados_cliente(self, dados: dict, lead=None) -> ClienteHubsoft:
        """Cria ou atualiza o ClienteHubsoft e seus ServicoClienteHubsoft."""
        from django.utils.dateparse import parse_datetime as _parse_datetime, parse_date

        id_cliente = dados['id_cliente']

        campos_cliente = {
            'uuid_cliente': dados.get('uuid_cliente') or '',
            'codigo_cliente': dados.get('codigo_cliente'),
            'nome_razaosocial': dados.get('nome_razaosocial') or '',
            'nome_fantasia': dados.get('nome_fantasia') or '',
            'tipo_pessoa': dados.get('tipo_pessoa') or 'pf',
            'cpf_cnpj': dados.get('cpf_cnpj') or '',
            'telefone_primario': dados.get('telefone_primario') or '',
            'telefone_secundario': dados.get('telefone_secundario') or '',
            'telefone_terciario': dados.get('telefone_terciario') or '',
            'email_principal': dados.get('email_principal') or '',
            'email_secundario': dados.get('email_secundario') or '',
            'rg': dados.get('rg') or '',
            'rg_emissao': dados.get('rg_emissao') or '',
            'inscricao_municipal': dados.get('inscricao_municipal') or '',
            'inscricao_estadual': dados.get('inscricao_estadual') or '',
            'nome_pai': dados.get('nome_pai') or '',
            'nome_mae': dados.get('nome_mae') or '',
            'estado_civil': dados.get('estado_civil') or '',
            'genero': dados.get('genero') or '',
            'nacionalidade': dados.get('nacionalidade') or '',
            'profissao': dados.get('profissao') or '',
            'alerta': bool(dados.get('alerta')),
            'alerta_mensagens': dados.get('alerta_mensagens') or [],
            'ativo': bool(dados.get('ativo', True)),
            'id_origem_cliente': dados.get('id_origem_cliente'),
            'origem_cliente': dados.get('origem_cliente') or '',
            'motivo_contratacao': dados.get('motivo_contratacao') or '',
            'id_externo': dados.get('id_externo') or '',
            'grupos': dados.get('grupos') or [],
            'dados_completos': dados,
        }

        def _make_aware(dt_str):
            if not dt_str:
                return None
            dt = _parse_datetime(dt_str.replace(' ', 'T'))
            if dt and timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt

        dt_cadastro = dados.get('data_cadastro')
        if dt_cadastro:
            campos_cliente['data_cadastro_hubsoft'] = _make_aware(dt_cadastro)

        dt_nascimento = dados.get('data_nascimento')
        if dt_nascimento:
            parsed = parse_date(dt_nascimento[:10])
            if parsed:
                campos_cliente['data_nascimento'] = parsed

        dt_atualizacao = dados.get('data_atualizacao')
        if dt_atualizacao:
            campos_cliente['data_atualizacao_hubsoft'] = _make_aware(dt_atualizacao)

        try:
            cliente_existente = ClienteHubsoft.objects.get(id_cliente=id_cliente)
        except ClienteHubsoft.DoesNotExist:
            cliente_existente = None

        alteracoes = []
        if cliente_existente:
            alteracoes = self._detectar_alteracoes(cliente_existente, campos_cliente)

        if lead:
            campos_cliente['lead'] = lead

        cliente, created = ClienteHubsoft.objects.update_or_create(
            id_cliente=id_cliente,
            defaults=campos_cliente,
        )

        alteracoes_servicos = self._sincronizar_servicos(cliente, dados.get('servicos') or [])

        # Sincronizar atendimentos e OS (silenciar erros para não quebrar o fluxo principal)
        try:
            self.sincronizar_atendimentos_os(cliente)
        except Exception as exc:
            logger.warning("Falha ao sincronizar atendimentos/OS do cliente %s: %s", cliente.pk, exc)

        todas_alteracoes = alteracoes + alteracoes_servicos

        ClienteHubsoft.objects.filter(pk=cliente.pk).update(
            houve_alteracao=bool(todas_alteracoes) and not created,
        )

        if created:
            logger.info("Cliente Hubsoft criado: %s (id_cliente=%s)", cliente.nome_razaosocial, id_cliente)
        elif todas_alteracoes:
            logger.info(
                "Cliente Hubsoft atualizado com %d alteração(ões): %s (id_cliente=%s)",
                len(todas_alteracoes), cliente.nome_razaosocial, id_cliente,
            )

        if todas_alteracoes and not created:
            historico = cliente.historico_alteracoes or []
            historico.append({
                'data': timezone.now().isoformat(),
                'alteracoes': todas_alteracoes,
            })
            ClienteHubsoft.objects.filter(pk=cliente.pk).update(
                historico_alteracoes=historico,
                houve_alteracao=True,
            )

        return cliente

    def _sincronizar_servicos(self, cliente: ClienteHubsoft, servicos_data: list) -> list:
        """
        Cria ou atualiza os ServicoClienteHubsoft vinculados ao cliente.
        Retorna lista de alterações detectadas nos serviços.
        """
        from django.utils.dateparse import parse_datetime as _parse_datetime

        def _make_aware_svc(dt_str):
            if not dt_str:
                return None
            dt = _parse_datetime(dt_str.replace(' ', 'T'))
            if dt and timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt

        ids_encontrados = []
        todas_alteracoes = []

        for svc in servicos_data:
            id_cs = svc.get('id_cliente_servico')
            if not id_cs:
                continue
            ids_encontrados.append(id_cs)

            vendedor = svc.get('vendedor') or {}

            campos_servico = {
                'cliente': cliente,
                'uuid_cliente_servico': svc.get('uuid_cliente_servico') or '',
                'id_servico': svc.get('id_servico'),
                'numero_plano': svc.get('numero_plano'),
                'nome': svc.get('nome') or '',
                'valor': svc.get('valor'),
                'tecnologia': svc.get('tecnologia') or '',
                'velocidade_download': svc.get('velocidade_download') or '',
                'velocidade_upload': svc.get('velocidade_upload') or '',
                'status': svc.get('status') or '',
                'status_prefixo': svc.get('status_prefixo') or '',
                'data_venda': svc.get('data_venda') or '',
                'data_inicio_contrato': svc.get('data_inicio_contrato') or '',
                'data_fim_contrato': svc.get('data_fim_contrato') or '',
                'vigencia_meses': svc.get('vigencia_meses'),
                'data_cadastro_servico': svc.get('data_cadastro') or '',
                'id_cliente_servico_autenticacao': svc.get('id_cliente_servico_autenticacao'),
                'login': svc.get('login') or '',
                'senha': svc.get('senha') or '',
                'mac_addr': svc.get('mac_addr') or '',
                'phy_addr': svc.get('phy_addr') or '',
                'vlan': svc.get('vlan') or '',
                'ipv4': svc.get('ipv4') or None,
                'ipv6': svc.get('ipv6') or None,
                'id_motivo_cancelamento': svc.get('id_motivo_cancelamento'),
                'motivo_cancelamento': svc.get('motivo_cancelamento') or '',
                'id_vendedor': vendedor.get('id_vendedor'),
                'vendedor_nome': vendedor.get('nome') or '',
                'vendedor_email': vendedor.get('email') or '',
                'dados_completos': svc,
            }

            dt_hab = svc.get('data_habilitacao')
            if dt_hab:
                campos_servico['data_habilitacao'] = _make_aware_svc(dt_hab)

            dt_cancel = svc.get('data_cancelamento')
            if dt_cancel:
                campos_servico['data_cancelamento'] = _make_aware_svc(dt_cancel)

            dt_atualiz = svc.get('data_atualizacao')
            if dt_atualiz:
                campos_servico['data_atualizacao_servico'] = _make_aware_svc(dt_atualiz)

            try:
                servico_existente = ServicoClienteHubsoft.objects.get(id_cliente_servico=id_cs)
                alteracoes_svc = self._detectar_alteracoes_servico(servico_existente, campos_servico)
                todas_alteracoes.extend(alteracoes_svc)
            except ServicoClienteHubsoft.DoesNotExist:
                pass

            ServicoClienteHubsoft.objects.update_or_create(
                id_cliente_servico=id_cs,
                defaults=campos_servico,
            )

        removidos = ServicoClienteHubsoft.objects.filter(
            cliente=cliente,
        ).exclude(
            id_cliente_servico__in=ids_encontrados,
        )
        for svc_rem in removidos:
            todas_alteracoes.append({
                'campo': f'servico[{svc_rem.id_cliente_servico}]',
                'valor_anterior': svc_rem.nome,
                'valor_novo': '[REMOVIDO]',
            })
        removidos.delete()

        return todas_alteracoes

    @staticmethod
    def _valores_iguais(valor_atual, novo_valor):
        """Compara dois valores de forma inteligente, tratando timezone e decimais."""
        from datetime import datetime as dt_class
        from decimal import Decimal as Dec, InvalidOperation

        if valor_atual is None and novo_valor is None:
            return True
        if valor_atual is None and novo_valor == '':
            return True
        if novo_valor is None and valor_atual == '':
            return True
        if valor_atual is None or novo_valor is None:
            return False

        if isinstance(valor_atual, dt_class) and isinstance(novo_valor, dt_class):
            if timezone.is_aware(valor_atual) and timezone.is_aware(novo_valor):
                return abs((valor_atual - novo_valor).total_seconds()) < 1
            return valor_atual == novo_valor

        try:
            d_atual = Dec(str(valor_atual))
            d_novo = Dec(str(novo_valor))
            return d_atual == d_novo
        except (InvalidOperation, ValueError, TypeError):
            pass

        return str(valor_atual) == str(novo_valor)

    @classmethod
    def _detectar_alteracoes(cls, existente: ClienteHubsoft, novos_campos: dict) -> list:
        """Compara campos atuais do cliente com novos valores e retorna lista de diffs."""
        campos_ignorar = {
            'dados_completos', 'lead', 'houve_alteracao',
            'grupos', 'alerta_mensagens',
        }
        alteracoes = []

        for campo, novo_valor in novos_campos.items():
            if campo in campos_ignorar:
                continue
            valor_atual = getattr(existente, campo, None)

            if not cls._valores_iguais(valor_atual, novo_valor):
                alteracoes.append({
                    'campo': campo,
                    'valor_anterior': str(valor_atual or ''),
                    'valor_novo': str(novo_valor or ''),
                })

        return alteracoes

    @classmethod
    def _detectar_alteracoes_servico(cls, existente: ServicoClienteHubsoft, novos_campos: dict) -> list:
        """Compara campos atuais do serviço com novos valores e retorna lista de diffs."""
        campos_rastrear = {
            'status', 'status_prefixo', 'nome', 'valor',
            'velocidade_download', 'velocidade_upload',
            'login', 'senha', 'mac_addr', 'ipv4', 'ipv6',
            'data_habilitacao', 'data_cancelamento', 'motivo_cancelamento',
            'vendedor_nome',
        }
        alteracoes = []
        id_cs = existente.id_cliente_servico

        for campo in campos_rastrear:
            novo_valor = novos_campos.get(campo)
            valor_atual = getattr(existente, campo, None)

            if not cls._valores_iguais(valor_atual, novo_valor):
                alteracoes.append({
                    'campo': f'servico[{id_cs}].{campo}',
                    'valor_anterior': str(valor_atual or ''),
                    'valor_novo': str(novo_valor or ''),
                })

        return alteracoes

    # ------------------------------------------------------------------
    # Mapeamento de campos
    # ------------------------------------------------------------------

    def _mapear_lead_para_hubsoft(self, lead) -> dict:
        """
        Converte os campos de um LeadProspecto para o formato esperado
        pela API Hubsoft POST /api/v1/integracao/prospecto.
        """
        payload = {}

        payload['nome_razaosocial'] = lead.nome_razaosocial or ''
        payload['tipo_pessoa'] = self._detectar_tipo_pessoa(lead.cpf_cnpj)

        if lead.cpf_cnpj:
            payload['cpf_cnpj'] = self._somente_numeros(lead.cpf_cnpj)

        # Telefone: remover caracteres não numéricos e, se começar com 55,
        # descartar esse prefixo de DDI para enviar apenas DDD + número.
        payload['telefone'] = self._normalizar_telefone(lead.telefone)

        if lead.email:
            payload['email'] = lead.email

        if lead.observacoes:
            payload['observacao'] = lead.observacoes

        payload['cep'] = self._somente_numeros(lead.cep) if lead.cep else ''

        payload['bairro'] = lead.bairro or ''

        if lead.rua:
            payload['endereco'] = lead.rua
        elif lead.endereco:
            payload['endereco'] = lead.endereco
        else:
            payload['endereco'] = ''

        payload['numero'] = lead.numero_residencia or 'S/N'

        if lead.ponto_referencia:
            payload['referencia'] = lead.ponto_referencia

        if lead.rg:
            payload['rg'] = lead.rg

        if lead.data_nascimento:
            if hasattr(lead.data_nascimento, 'strftime'):
                payload['data_nascimento'] = lead.data_nascimento.strftime('%Y-%m-%d')
            else:
                payload['data_nascimento'] = str(lead.data_nascimento)[:10]

        # Serviço (plano) — obrigatório na API
        payload['servico'] = {
            'id_servico': lead.id_plano_rp if lead.id_plano_rp else 0,
            'valor': float(lead.valor) if lead.valor else 0,
        }

        # Vendedor das vendas do robô v2 = 1613 "Venda-Automática". Mira própria,
        # separada do gestao_leads_bot (que converte só os do 1618). Isso garante
        # que o nosso worker de conversão (vendedor 1613) pegue estes prospectos.
        from django.conf import settings as _settings
        payload['id_vendedor'] = getattr(_settings, 'HUBSOFT_VENDEDOR_CONVERSAO', 1613)

        if lead.id_dia_vencimento:
            payload['id_vencimento'] = lead.id_dia_vencimento

        if lead.id_origem:
            try:
                payload['id_origem_cliente'] = int(lead.id_origem)
            except (ValueError, TypeError):
                pass

        if lead.id_origem_servico:
            try:
                payload['id_origem_servico'] = int(lead.id_origem_servico)
            except (ValueError, TypeError):
                pass

        payload['id_externo'] = str(lead.pk)

        return payload

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _somente_numeros(valor: str) -> str:
        if not valor:
            return ''
        return re.sub(r'\D', '', str(valor))

    @staticmethod
    def _normalizar_telefone(valor: str) -> str:
        """
        Remove caracteres não numéricos e, se o telefone começar com 55
        (DDI do Brasil), remove esse prefixo para manter apenas DDD + número.
        Ex.: 5589994034399 -> 89994034399
        """
        numeros = HubsoftService._somente_numeros(valor)
        if numeros.startswith('55') and len(numeros) > 11:
            numeros = numeros[2:]
        return numeros

    @staticmethod
    def _detectar_tipo_pessoa(cpf_cnpj: str) -> str:
        if not cpf_cnpj:
            return 'pf'
        numeros = re.sub(r'\D', '', cpf_cnpj)
        return 'pj' if len(numeros) > 11 else 'pf'

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
            logger.error("Erro ao registrar log de integração: %s", exc)
