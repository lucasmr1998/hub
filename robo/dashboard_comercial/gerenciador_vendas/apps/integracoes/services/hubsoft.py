import io
import logging
import re
import time
from datetime import timedelta

import requests
from django.utils import timezone

from apps.integracoes.models import IntegracaoAPI, LogIntegracao, ClienteHubsoft, ServicoClienteHubsoft

logger = logging.getLogger(__name__)


class HubsoftServiceError(Exception):
    """Erro genérico do serviço Hubsoft."""
    pass


class HubsoftService:
    """
    Encapsula a comunicação com a API REST do Hubsoft.

    Padrão (espelhando o SGPService):
      - Wrapper único `_request` com mascaramento de credencial em log
      - Helpers `_get`, `_post`, `_put` por cima do `_request`
      - Token OAuth2 cacheado em `IntegracaoAPI.access_token`
      - Cada método público retorna o JSON cru ou levanta `HubsoftServiceError`
    """

    ENDPOINT_TOKEN = '/oauth/token'
    ENDPOINT_PROSPECTO = '/api/v1/integracao/prospecto'
    ENDPOINT_CLIENTE = '/api/v1/integracao/cliente'
    ENDPOINT_CONTRATO_ANEXO_TPL = '/api/v1/integracao/cliente/contrato/adicionar_anexo_contrato/{id_contrato}'
    ENDPOINT_CONTRATO_ACEITAR = '/api/v1/integracao/cliente/contrato/aceitar_contrato'

    CAMPOS_SEGREDO_LOG = ('password', 'client_secret', 'token', 'access_token')

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
        Obtém (ou reutiliza) um access_token válido. Cacheia no
        `IntegracaoAPI.access_token` + `token_expira_em`.
        """
        if self.integracao.token_valido:
            return self.integracao.access_token

        payload = {
            'client_id': self.integracao.client_id,
            'client_secret': self.integracao.client_secret,
            'username': self.integracao.username,
            'password': self.integracao.password,
            'grant_type': self.integracao.grant_type,
        }

        resposta = self._request(
            'POST', self.ENDPOINT_TOKEN,
            json=payload, autenticar=False,
        )

        token = resposta.get('access_token', '')
        expires_in = resposta.get('expires_in', 3600)
        if not token:
            raise HubsoftServiceError(f"Token não retornado pelo HubSoft: {resposta}")

        IntegracaoAPI.objects.filter(pk=self.integracao.pk).update(
            access_token=token,
            token_expira_em=timezone.now() + timedelta(seconds=int(expires_in) - 60),
        )
        self.integracao.refresh_from_db()
        return token

    # ------------------------------------------------------------------
    # Prospecto
    # ------------------------------------------------------------------

    def cadastrar_prospecto(self, lead) -> dict:
        """Envia LeadProspecto para o HubSoft. Retorna dict da API."""
        payload = self._mapear_lead_para_hubsoft(lead)
        resposta = self._post(self.ENDPOINT_PROSPECTO, json=payload, lead=lead)

        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft rejeitou prospecto: {resposta}"
            )
        return resposta

    # ------------------------------------------------------------------
    # Cliente
    # ------------------------------------------------------------------

    def consultar_cliente(self, cpf_cnpj: str, lead=None) -> dict:
        """Consulta cliente no HubSoft por CPF/CNPJ."""
        cpf_limpo = self._somente_numeros(cpf_cnpj)
        params = {'busca': 'cpf_cnpj', 'termo_busca': cpf_limpo}
        resposta = self._get(self.ENDPOINT_CLIENTE, params=params, lead=lead)

        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft retornou erro ao consultar cliente {cpf_limpo}: {resposta}"
            )
        return resposta

    def sincronizar_cliente(self, lead) -> ClienteHubsoft | None:
        """
        Consulta o HubSoft pelo CPF/CNPJ do lead e cria/atualiza
        ClienteHubsoft + ServicoClienteHubsoft local. Detecta alterações.
        """
        if not lead.cpf_cnpj:
            logger.warning("Lead pk=%s sem CPF/CNPJ, impossível consultar cliente.", lead.pk)
            return None

        resposta = self.consultar_cliente(lead.cpf_cnpj, lead=lead)
        clientes = resposta.get('clientes', [])
        if not clientes:
            logger.info("Nenhum cliente encontrado no Hubsoft para CPF/CNPJ %s", lead.cpf_cnpj)
            return None

        return self._sincronizar_dados_cliente(clientes[0], lead)

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

        if dados.get('data_cadastro'):
            campos_cliente['data_cadastro_hubsoft'] = _make_aware(dados['data_cadastro'])
        if dados.get('data_nascimento'):
            parsed = parse_date(dados['data_nascimento'][:10])
            if parsed:
                campos_cliente['data_nascimento'] = parsed
        if dados.get('data_atualizacao'):
            campos_cliente['data_atualizacao_hubsoft'] = _make_aware(dados['data_atualizacao'])

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
        """Cria/atualiza ServicoClienteHubsoft. Retorna lista de alterações."""
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

            if svc.get('data_habilitacao'):
                campos_servico['data_habilitacao'] = _make_aware_svc(svc['data_habilitacao'])
            if svc.get('data_cancelamento'):
                campos_servico['data_cancelamento'] = _make_aware_svc(svc['data_cancelamento'])
            if svc.get('data_atualizacao'):
                campos_servico['data_atualizacao_servico'] = _make_aware_svc(svc['data_atualizacao'])

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
        ).exclude(id_cliente_servico__in=ids_encontrados)
        for svc_rem in removidos:
            todas_alteracoes.append({
                'campo': f'servico[{svc_rem.id_cliente_servico}]',
                'valor_anterior': svc_rem.nome,
                'valor_novo': '[REMOVIDO]',
            })
        removidos.delete()

        self._sincronizar_produtos_crm(cliente, servicos_data)
        return todas_alteracoes

    def _sincronizar_produtos_crm(self, cliente, servicos_data):
        """Garante que cada serviço do HubSoft tenha um ProdutoServico no catálogo."""
        try:
            from apps.comercial.crm.models import ProdutoServico

            if not self.integracao.sync_permitido('sincronizar_servicos'):
                return

            tenant = cliente.tenant
            for svc in servicos_data:
                id_servico = str(svc.get('id_servico') or '')
                nome = svc.get('nome') or ''
                if not id_servico or not nome:
                    continue

                ProdutoServico.objects.update_or_create(
                    tenant=tenant,
                    id_externo=id_servico,
                    defaults={
                        'nome': nome,
                        'preco': svc.get('valor') or 0,
                        'categoria': 'plano',
                        'recorrencia': 'mensal',
                        'dados_erp': {
                            'velocidade_download': svc.get('velocidade_download') or '',
                            'velocidade_upload': svc.get('velocidade_upload') or '',
                            'tecnologia': svc.get('tecnologia') or '',
                            'numero_plano': svc.get('numero_plano'),
                            'id_servico_hubsoft': svc.get('id_servico'),
                        },
                    }
                )
        except Exception as e:
            logger.warning(f'Erro ao sincronizar ProdutoServico: {e}')

    # ------------------------------------------------------------------
    # Contrato — anexos e aceite (movido de cadastro/contrato_service)
    # ------------------------------------------------------------------

    def anexar_arquivos_contrato(
        self,
        id_contrato: int,
        arquivos: list[tuple[str, bytes, str]],
        lead=None,
    ) -> dict:
        """
        Anexa múltiplos arquivos a um contrato no HubSoft em uma única request.

        HubSoft exige chaves indexadas: files[0], files[1], ...
        Cada item de `arquivos` é (nome_arquivo, conteudo_bytes, content_type).
        Levanta HubsoftServiceError em falha.
        """
        endpoint = self.ENDPOINT_CONTRATO_ANEXO_TPL.format(id_contrato=int(id_contrato))
        files_payload = [
            (f"files[{i}]", (nome, io.BytesIO(conteudo), content_type))
            for i, (nome, conteudo, content_type) in enumerate(arquivos)
        ]
        nomes = [n for n, _, _ in arquivos]
        total_bytes = sum(len(c) for _, c, _ in arquivos)
        log_payload = {'id_contrato': id_contrato, 'arquivos': nomes, 'total_bytes': total_bytes}

        resposta = self._request(
            'POST', endpoint,
            files=files_payload,
            log_payload=log_payload,
            timeout=120,
            lead=lead,
        )
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft rejeitou anexo de contrato {id_contrato}: {resposta}"
            )
        return resposta

    def aceitar_contrato(self, id_contrato: int, *, observacao: str = '', lead=None) -> dict:
        """Marca contrato como aceito no HubSoft."""
        agora = timezone.localtime(timezone.now())
        payload = {
            'ids_cliente_servico_contrato': [int(id_contrato)],
            'data_aceito': agora.strftime('%Y-%m-%d'),
            'hora_aceito': agora.strftime('%H:%M'),
            'observacao': observacao or 'Contrato aceito via Hubtrix.',
        }
        resposta = self._put(self.ENDPOINT_CONTRATO_ACEITAR, json=payload, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft rejeitou aceite do contrato {id_contrato}: {resposta}"
            )
        return resposta

    # ------------------------------------------------------------------
    # Detecção de alterações (vantagem do HubSoft sobre SGP — mantido)
    # ------------------------------------------------------------------

    @staticmethod
    def _valores_iguais(valor_atual, novo_valor):
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
            return Dec(str(valor_atual)) == Dec(str(novo_valor))
        except (InvalidOperation, ValueError, TypeError):
            pass

        return str(valor_atual) == str(novo_valor)

    @classmethod
    def _detectar_alteracoes(cls, existente: ClienteHubsoft, novos_campos: dict) -> list:
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
    # Mapeamento Lead → payload HubSoft
    # ------------------------------------------------------------------

    def _mapear_lead_para_hubsoft(self, lead) -> dict:
        payload = {
            'nome_razaosocial': lead.nome_razaosocial or '',
            'tipo_pessoa': self._detectar_tipo_pessoa(lead.cpf_cnpj),
        }

        if lead.cpf_cnpj:
            payload['cpf_cnpj'] = self._somente_numeros(lead.cpf_cnpj)

        payload['telefone'] = self._normalizar_telefone(lead.telefone)

        if lead.email:
            payload['email'] = lead.email
        if lead.observacoes:
            payload['observacao'] = lead.observacoes

        payload['cep'] = self._somente_numeros(lead.cep) if lead.cep else ''
        payload['bairro'] = lead.bairro or ''
        payload['endereco'] = lead.rua or lead.endereco or ''
        payload['numero'] = lead.numero_residencia or 'S/N'

        if lead.ponto_referencia:
            payload['referencia'] = lead.ponto_referencia
        if lead.rg:
            payload['rg'] = lead.rg
        if lead.data_nascimento:
            payload['data_nascimento'] = lead.data_nascimento.strftime('%Y-%m-%d')

        # Defaults da integração — fallback quando o lead não traz o id específico.
        extras = self.integracao.configuracoes_extras or {}

        plano_id = lead.id_plano_rp or extras.get('plano_id_padrao') or 0
        payload['servico'] = {
            'id_servico': int(plano_id) if plano_id else 0,
            'valor': float(lead.valor) if lead.valor else 0,
        }

        vendedor_id = lead.id_vendedor_rp or extras.get('vendedor_id_padrao')
        if vendedor_id:
            payload['id_vendedor'] = int(vendedor_id)

        venc_id = lead.id_dia_vencimento or extras.get('dia_vencimento_id_padrao')
        if venc_id:
            payload['id_vencimento'] = int(venc_id)

        origem_id = lead.id_origem or extras.get('id_origem_padrao')
        if origem_id:
            try:
                payload['id_origem_cliente'] = int(origem_id)
            except (ValueError, TypeError):
                pass

        origem_servico_id = lead.id_origem_servico or extras.get('id_origem_servico_padrao')
        if origem_servico_id:
            try:
                payload['id_origem_servico'] = int(origem_servico_id)
            except (ValueError, TypeError):
                pass

        payload['id_externo'] = str(lead.pk)
        return payload

    # ------------------------------------------------------------------
    # Helpers de normalização
    # ------------------------------------------------------------------

    @staticmethod
    def _somente_numeros(valor: str) -> str:
        if not valor:
            return ''
        return re.sub(r'\D', '', str(valor))

    @staticmethod
    def _normalizar_telefone(valor: str) -> str:
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

    # ------------------------------------------------------------------
    # Wrapper HTTP central
    # ------------------------------------------------------------------

    def _get(self, endpoint: str, *, params: dict = None, lead=None) -> dict:
        return self._request('GET', endpoint, params=params, lead=lead)

    def _post(self, endpoint: str, *, json: dict = None, params: dict = None, lead=None) -> dict:
        return self._request('POST', endpoint, json=json, params=params, lead=lead)

    def _put(self, endpoint: str, *, json: dict = None, params: dict = None, lead=None) -> dict:
        return self._request('PUT', endpoint, json=json, params=params, lead=lead)

    def _request(
        self,
        metodo: str,
        endpoint: str,
        *,
        json: dict = None,
        params: dict = None,
        files: list = None,
        log_payload: dict = None,
        timeout: int = 30,
        autenticar: bool = True,
        lead=None,
    ) -> dict:
        """
        Wrapper HTTP único: aplica auth (Bearer ou skip), executa, registra
        LogIntegracao com payload mascarado, levanta HubsoftServiceError em falha.

        - `json`: corpo JSON (POST/PUT). Ignorado se `files` informado.
        - `files`: lista no formato requests (multipart).
        - `params`: query string.
        - `log_payload`: o que registrar quando o body é multipart (não dá pra logar bytes).
        - `autenticar`: False só para o endpoint de token.
        """
        url = f"{self.base_url}{endpoint}"
        headers = {'Accept': 'application/json'}
        if autenticar:
            token = self.obter_token()
            headers['Authorization'] = f'Bearer {token}'

        payload_para_log = (
            log_payload if log_payload is not None
            else self._payload_seguro(json or params or {})
        )

        inicio = time.time()
        try:
            resp = requests.request(
                metodo, url,
                json=json if files is None else None,
                params=params,
                files=files,
                headers=headers,
                timeout=timeout,
            )
            tempo_ms = int((time.time() - inicio) * 1000)
        except requests.RequestException as exc:
            tempo_ms = int((time.time() - inicio) * 1000)
            self._registrar_log(
                endpoint=endpoint, metodo=metodo,
                payload=payload_para_log, resposta={},
                status_code=0, sucesso=False, erro=str(exc),
                tempo_ms=tempo_ms, lead=lead,
            )
            raise HubsoftServiceError(f"Falha de conexão com HubSoft: {exc}") from exc

        try:
            resposta_json = resp.json()
        except ValueError:
            resposta_json = {'raw': resp.text[:2000]}

        sucesso = resp.status_code in (200, 201)
        resposta_para_log = (
            resposta_json if isinstance(resposta_json, dict)
            else {'list': resposta_json}
        )
        msg_erro_api = ''
        if isinstance(resposta_json, dict):
            msg_erro_api = resposta_json.get('msg', '') or ''

        self._registrar_log(
            endpoint=endpoint, metodo=metodo,
            payload=payload_para_log,
            resposta=resposta_para_log,
            status_code=resp.status_code,
            sucesso=sucesso,
            erro='' if sucesso else f"HTTP {resp.status_code}: {msg_erro_api}",
            tempo_ms=tempo_ms, lead=lead,
        )

        if not sucesso:
            raise HubsoftServiceError(
                f"Erro HubSoft em {endpoint} (HTTP {resp.status_code}): {resposta_json}"
            )

        if isinstance(resposta_json, dict):
            return resposta_json
        return {'list': resposta_json}

    @classmethod
    def _payload_seguro(cls, data: dict) -> dict:
        """Mascara segredos no payload logado."""
        if not isinstance(data, dict):
            return data
        return {
            k: ('***REDACTED***' if k in cls.CAMPOS_SEGREDO_LOG else v)
            for k, v in data.items()
        }

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
