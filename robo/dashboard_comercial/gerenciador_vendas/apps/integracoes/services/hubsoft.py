import io
import logging
import re
import time
from datetime import timedelta

import requests
from django.db import transaction
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
    ENDPOINT_CONTRATO_CRIAR = '/api/v1/integracao/cliente/contrato/adicionar_contrato'
    ENDPOINT_CFG_MODELO_CONTRATO = '/api/v1/integracao/configuracao/modelo_contrato'

    # Catálogos de configuração
    ENDPOINT_CFG_SERVICO = '/api/v1/integracao/configuracao/servico'
    ENDPOINT_CFG_VENCIMENTO = '/api/v1/integracao/configuracao/vencimento'
    ENDPOINT_CFG_VENDEDOR = '/api/v1/integracao/configuracao/vendedor'
    ENDPOINT_CFG_ORIGEM_CLIENTE = '/api/v1/integracao/configuracao/origem_cliente'
    ENDPOINT_CFG_ORIGEM_CONTATO = '/api/v1/integracao/configuracao/origem_contato'
    ENDPOINT_CFG_MEIO_PAGAMENTO = '/api/v1/integracao/configuracao/meio_pagamento'
    ENDPOINT_CFG_GRUPO_CLIENTE = '/api/v1/integracao/configuracao/grupo_cliente'
    ENDPOINT_CFG_MOTIVO_CONTRATACAO = '/api/v1/integracao/configuracao/motivo_contratacao'
    ENDPOINT_CFG_TIPO_SERVICO = '/api/v1/integracao/configuracao/tipo_servico'
    ENDPOINT_CFG_SERVICO_STATUS = '/api/v1/integracao/configuracao/servico_status'
    ENDPOINT_CFG_SERVICO_TECNOLOGIA = '/api/v1/integracao/configuracao/servico_tecnologia'

    # Financeiro
    ENDPOINT_CLIENTE_FINANCEIRO = '/api/v1/integracao/cliente/financeiro'
    ENDPOINT_RENEGOCIACAO_LISTAR = '/api/v1/integracao/financeiro/renegociacao'
    ENDPOINT_RENEGOCIACAO_SIMULAR = '/api/v1/integracao/financeiro/renegociacao/simular'
    ENDPOINT_RENEGOCIACAO_EFETIVAR = '/api/v1/integracao/financeiro/renegociacao/efetivar'

    # Viabilidade / cobertura
    ENDPOINT_VIABILIDADE = '/api/v1/integracao/mapeamento/viabilidade/consultar'
    ENDPOINT_PROSPECTO_CREATE = '/api/v1/integracao/prospecto/create'
    ENDPOINT_PROSPECTO_EDITAR_TPL = '/api/v1/integracao/prospecto/{id_prospecto}'

    # Atendimento / OS (LEITURA — Bloco H6 reduzido)
    ENDPOINT_CLIENTE_ATENDIMENTO = '/api/v1/integracao/cliente/atendimento'
    ENDPOINT_CLIENTE_OS = '/api/v1/integracao/cliente/ordem_servico'

    # Atendimento / OS — abertura e agendamento (camada Matrix/agendamento)
    ENDPOINT_ATENDIMENTO_CREATE = '/api/v1/integracao/atendimento'
    ENDPOINT_OS_HORARIOS_AGENDA = '/api/v1/integracao/ordem_servico/horarios_disponiveis_agenda'
    ENDPOINT_OS_AGENDAR = '/api/v1/integracao/ordem_servico/agendar'
    ENDPOINT_OS_ABRIR = '/api/v1/integracao/ordem_servico/abrir_os'

    # Operacional / suporte
    ENDPOINT_EXTRATO_CONEXAO = '/api/v1/integracao/cliente/extrato_conexao'
    ENDPOINT_SOLICITAR_DESCONEXAO_TPL = '/api/v1/integracao/cliente/solicitar_desconexao/{id_cliente_servico}'
    ENDPOINT_DESBLOQUEIO_CONFIANCA = '/api/v1/integracao/cliente/desbloqueio_confianca'
    ENDPOINT_RESET_MAC = '/api/v1/integracao/cliente/reset_mac_addr'
    ENDPOINT_RESET_PHY = '/api/v1/integracao/cliente/reset_phy_addr'
    ENDPOINT_SVC_SUSPENDER_TPL = '/api/v1/integracao/cliente/cliente_servico/suspender/{id}'
    ENDPOINT_SVC_HABILITAR_TPL = '/api/v1/integracao/cliente/cliente_servico/habilitar/{id}'
    ENDPOINT_SVC_ATIVAR_TPL = '/api/v1/integracao/cliente/cliente_servico/ativar/{id}'

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

    def editar_prospecto(self, lead, id_prospecto: str | int, *, payload: dict | None = None) -> dict:
        """Atualiza prospecto existente no HubSoft (PUT /prospecto/{id}).

        Aceita update parcial — todos os campos sao opcionais na API HubSoft. Se
        `payload` nao for passado, monta automaticamente via
        `_mapear_lead_para_hubsoft_editar`, que produz o formato aninhado
        (prospecto_endereco.*, prospecto_servico.*) exigido pelo endpoint editar
        (diferente do create, que usa flat cep/endereco/bairro + servico.*).

        Retorna dict da API (espera `msg: "Prospecto atualizado com sucesso"`).
        """
        if not id_prospecto:
            raise HubsoftServiceError('editar_prospecto: id_prospecto vazio')
        if payload is None:
            payload = self._mapear_lead_para_hubsoft_editar(lead)
        endpoint = self.ENDPOINT_PROSPECTO_EDITAR_TPL.format(id_prospecto=id_prospecto)
        resposta = self._put(endpoint, json=payload, lead=lead)

        if resposta.get('status') and resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft rejeitou edicao do prospecto {id_prospecto}: {resposta}"
            )
        return resposta

    # ------------------------------------------------------------------
    # Cliente
    # ------------------------------------------------------------------

    def consultar_cliente(self, cpf_cnpj: str, lead=None, incluir_contrato: bool = False) -> dict:
        """Consulta cliente no HubSoft por CPF/CNPJ.

        incluir_contrato=True adiciona `incluir_contrato=sim` na query, trazendo os
        contratos do servico na resposta (necessario pra obter o
        id_cliente_servico_contrato usado no aceite de contrato).
        """
        cpf_limpo = self._somente_numeros(cpf_cnpj)
        params = {'busca': 'cpf_cnpj', 'termo_busca': cpf_limpo}
        if incluir_contrato:
            params['incluir_contrato'] = 'sim'
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

        # Multi-tenant: filtra por tenant da integracao (= tenant do lead).
        # Garante que dois tenants com o mesmo id_cliente HubSoft (improvavel
        # mas possivel) nao se misturem. Tambem garante que o INSERT cria
        # ClienteHubsoft com tenant_id preenchido (era None antes — bug).
        tenant_obj = self.integracao.tenant if getattr(self, 'integracao', None) else None
        if lead and not tenant_obj:
            tenant_obj = lead.tenant

        try:
            cliente_existente = ClienteHubsoft.all_tenants.get(
                tenant=tenant_obj, id_cliente=id_cliente,
            )
        except ClienteHubsoft.DoesNotExist:
            cliente_existente = None

        alteracoes = []
        if cliente_existente:
            alteracoes = self._detectar_alteracoes(cliente_existente, campos_cliente)

        if lead:
            campos_cliente['lead'] = lead
        if tenant_obj:
            campos_cliente['tenant'] = tenant_obj

        # Atomico: cliente + servicos ficam visiveis no banco JUNTOS.
        # Sem isso, ha uma janela de race em que clientes_hubsoft ja foi
        # commitado mas servicos_cliente_hubsoft ainda nao — consumidores
        # do endpoint /lead/hubsoft-status/ (ex: flow Matrix) podem ver
        # eh_cliente_hubsoft=true com servicos=[] e cachear id_cliente_servico
        # vazio numa variavel, quebrando o agendamento de OS depois.
        with transaction.atomic():
            cliente, created = ClienteHubsoft.all_tenants.update_or_create(
                tenant=tenant_obj,
                id_cliente=id_cliente,
                defaults=campos_cliente,
            )

            alteracoes_servicos = self._sincronizar_servicos(cliente, dados.get('servicos') or [])
            todas_alteracoes = alteracoes + alteracoes_servicos

            ClienteHubsoft.all_tenants.filter(pk=cliente.pk).update(
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
                ClienteHubsoft.all_tenants.filter(pk=cliente.pk).update(
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

            # Multi-tenant: setar tenant herdado do cliente (mesmo bug que
            # afetou ClienteHubsoft em 1b8132d). Sem isso, svc fica tenant=None
            # e a pagina /vendas/ filtra fora ("Sem servico" mesmo com dados).
            campos_servico['tenant'] = cliente.tenant
            try:
                servico_existente = ServicoClienteHubsoft.all_tenants.get(
                    tenant=cliente.tenant, id_cliente_servico=id_cs,
                )
                alteracoes_svc = self._detectar_alteracoes_servico(servico_existente, campos_servico)
                todas_alteracoes.extend(alteracoes_svc)
            except ServicoClienteHubsoft.DoesNotExist:
                pass

            ServicoClienteHubsoft.all_tenants.update_or_create(
                tenant=cliente.tenant,
                id_cliente_servico=id_cs,
                defaults=campos_servico,
            )

        removidos = ServicoClienteHubsoft.all_tenants.filter(
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

    def criar_contrato(
        self,
        *,
        id_cliente_servico: int,
        id_contrato_modelo: int,
        id_empresa: int,
        autorizacao_nome: str,
        autorizacao_cpf: str,
        informacao_adicional: str = '',
        lead=None,
    ) -> dict:
        """Gera contrato no HubSoft via POST /adicionar_contrato.

        Retorna o payload completo da HubSoft. O id retornado fica em
        `id_cliente_servico_contrato` no resultado (campo principal usado
        depois em anexar_arquivos_contrato e aceitar_contrato).

        Args:
            id_cliente_servico: id do servico ja existente (ServicoClienteHubsoft.id_cliente_servico)
            id_contrato_modelo: id do template/modelo de contrato (consultar via listar_modelos_contrato)
            id_empresa: id da empresa HubSoft (matriz/filial)
            autorizacao_nome: nome do titular (geralmente lead.nome_razaosocial)
            autorizacao_cpf: CPF do titular (geralmente lead.cpf_cnpj normalizado)
            informacao_adicional: texto livre pro registro (opcional)
        """
        payload = {
            'id_cliente_servico': int(id_cliente_servico),
            'id_contrato': int(id_contrato_modelo),
            'id_empresa': int(id_empresa),
            'autorizacao_nome': (autorizacao_nome or '').strip(),
            'autorizacao_cpf': ''.join(ch for ch in (autorizacao_cpf or '') if ch.isdigit()),
            'informacao_adicional': informacao_adicional or 'Contrato gerado via Hubtrix.',
        }
        resposta = self._post(self.ENDPOINT_CONTRATO_CRIAR, json=payload, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft rejeitou criacao de contrato pro servico {id_cliente_servico}: {resposta}"
            )
        return resposta

    def listar_modelos_contrato(self, *, lead=None) -> list[dict]:
        """Catalogo de modelos de contrato disponiveis pro tenant HubSoft.
        Retorna lista de dicts com id_contrato, descricao, id_empresa, etc.
        """
        resposta = self._request('GET', self.ENDPOINT_CFG_MODELO_CONTRATO, lead=lead)
        return resposta.get('modelos_contrato') or []

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
    # Catálogos de configuração — paridade com SGP Bloco 1
    # Estratégia:
    #   - Planos (servicos)  → upsert em ProdutoServico (preço fica em 0 até
    #     ser preenchido por sync de cliente, já que a HubSoft não traz preço
    #     no /configuracao/servico, só em /cliente.servicos[].valor)
    #   - Vencimentos        → upsert em OpcaoVencimentoCRM
    #   - Demais             → cache em integracao.configuracoes_extras['cache'][<chave>]
    # ------------------------------------------------------------------

    def listar_servicos(self) -> list[dict]:
        """Lista serviços (planos) cadastrados no HubSoft."""
        resposta = self._get(self.ENDPOINT_CFG_SERVICO)
        return resposta.get('servicos') or []

    def listar_vencimentos(self) -> list[dict]:
        """Lista opções de dia de vencimento."""
        resposta = self._get(self.ENDPOINT_CFG_VENCIMENTO)
        return resposta.get('vencimentos') or []

    def sincronizar_servicos_catalogo(self, *, dry_run: bool = False) -> dict:
        """
        Puxa serviços (planos) do HubSoft e faz upsert em crm.ProdutoServico.

        HubSoft só expõe id_servico + descrição + tecnologia em
        /configuracao/servico (sem preço). O preço é preservado se já
        existir; novos registros entram com preço 0 e são atualizados
        depois quando um cliente real é sincronizado.
        """
        from apps.comercial.crm.models import ProdutoServico
        from decimal import Decimal

        servicos = self.listar_servicos()
        tenant = self.integracao.tenant
        resumo = {'total': len(servicos), 'criados': 0, 'atualizados': 0,
                  'inalterados': 0, 'dry_run': dry_run}

        for svc in servicos:
            id_svc = svc.get('id_servico')
            if id_svc is None:
                continue
            codigo = str(id_svc)
            nome = svc.get('descricao') or f'Serviço HubSoft {id_svc}'
            tecnologia = (svc.get('servico_tecnologia') or {}).get('descricao') or ''

            dados_erp = {
                'origem_erp': 'hubsoft',
                'id_servico_hubsoft': id_svc,
                'tecnologia': tecnologia,
                'id_servico_tecnologia': svc.get('id_servico_tecnologia'),
            }

            existente = ProdutoServico.objects.filter(
                tenant=tenant, codigo=codigo,
            ).first()

            if dry_run:
                if existente is None:
                    resumo['criados'] += 1
                else:
                    # compara campos que vamos atualizar (não o preço, preservado)
                    mudou = (
                        existente.nome != nome
                        or existente.id_externo != codigo
                        or existente.dados_erp != dados_erp
                    )
                    resumo['atualizados' if mudou else 'inalterados'] += 1
                continue

            defaults = {
                'nome': nome,
                'categoria': 'plano',
                'recorrencia': 'mensal',
                'id_externo': codigo,
                'dados_erp': dados_erp,
            }
            if existente is None:
                defaults['preco'] = Decimal('0')
                ProdutoServico.objects.create(tenant=tenant, codigo=codigo, **defaults)
                resumo['criados'] += 1
            else:
                ProdutoServico.objects.filter(pk=existente.pk).update(**defaults)
                resumo['atualizados'] += 1

        return resumo

    def sincronizar_vencimentos(self, *, dry_run: bool = False) -> dict:
        """Puxa vencimentos do HubSoft e faz upsert em crm.OpcaoVencimentoCRM."""
        from apps.comercial.crm.models import OpcaoVencimentoCRM

        vencimentos = self.listar_vencimentos()
        tenant = self.integracao.tenant
        resumo = {'total': len(vencimentos), 'criados': 0, 'atualizados': 0,
                  'inalterados': 0, 'dry_run': dry_run}

        for venc in vencimentos:
            id_venc = venc.get('id_vencimento')
            dia = venc.get('dia_vencimento')
            if id_venc is None or dia is None:
                continue

            try:
                dia_int = int(dia)
            except (ValueError, TypeError):
                continue

            defaults = {
                'id_externo': str(id_venc),
                'ordem': dia_int,
                'ativo': True,
                'dados_erp': {'origem_erp': 'hubsoft', 'id_vencimento_hubsoft': id_venc},
            }

            if dry_run:
                existente = OpcaoVencimentoCRM.objects.filter(tenant=tenant, dia=dia_int).first()
                if existente is None:
                    resumo['criados'] += 1
                else:
                    mudou = any(
                        getattr(existente, k, None) != v for k, v in defaults.items()
                    )
                    resumo['atualizados' if mudou else 'inalterados'] += 1
                continue

            _, criado = OpcaoVencimentoCRM.objects.update_or_create(
                tenant=tenant, dia=dia_int, defaults=defaults,
            )
            resumo['criados' if criado else 'atualizados'] += 1

        return resumo

    # --- Catálogos cacheados em configuracoes_extras['cache'][<chave>] ---

    # Mapa chave_cache → (endpoint, raiz_response, fn_chave_item)
    # `raiz_response` é o nome do array dentro do JSON do HubSoft.
    # `fn_chave_item` extrai um identificador estável pra contar diff.
    CATALOGOS_CACHE = {
        'vendedores':         ('ENDPOINT_CFG_VENDEDOR',           'vendedores',         lambda i: f"id:{i.get('id')}"),
        'origens_cliente':    ('ENDPOINT_CFG_ORIGEM_CLIENTE',     'origens_cliente',    lambda i: f"id:{i.get('id_origem_cliente')}"),
        'origens_contato':    ('ENDPOINT_CFG_ORIGEM_CONTATO',     'origem_contatos',    lambda i: f"id:{i.get('id_origem_contato')}"),
        'meios_pagamento':    ('ENDPOINT_CFG_MEIO_PAGAMENTO',     'meios_pagamento',    lambda i: f"prefixo:{i.get('prefixo')}"),
        'grupos_cliente':     ('ENDPOINT_CFG_GRUPO_CLIENTE',      'grupo_cliente',      lambda i: f"id:{i.get('id_grupo_cliente')}"),
        'motivos_contratacao':('ENDPOINT_CFG_MOTIVO_CONTRATACAO', 'motivos_contratacao',lambda i: f"id:{i.get('id_motivo_contratacao')}"),
        'tipos_servico':      ('ENDPOINT_CFG_TIPO_SERVICO',       'tipos_servico',      lambda i: f"id:{i.get('id_tipo_servico')}"),
        'servico_status':     ('ENDPOINT_CFG_SERVICO_STATUS',     'servico_status',     lambda i: f"id:{i.get('id_servico_status')}"),
        'servicos_tecnologia':('ENDPOINT_CFG_SERVICO_TECNOLOGIA', 'servicos_tecnologia',lambda i: f"id:{i.get('id_servico_tecnologia')}"),
    }

    def sincronizar_catalogo_cacheado(self, chave: str, *, dry_run: bool = False) -> dict:
        """Puxa um catálogo nominal e cacheia em configuracoes_extras['cache'][chave]."""
        if chave not in self.CATALOGOS_CACHE:
            raise HubsoftServiceError(f"Catálogo desconhecido: {chave}")
        attr_endpoint, raiz, fn_chave = self.CATALOGOS_CACHE[chave]
        endpoint = getattr(self, attr_endpoint)

        resposta = self._get(endpoint)
        itens = resposta.get(raiz) or []
        return self._persistir_cache(chave, itens, fn_chave=fn_chave, dry_run=dry_run)

    def sincronizar_configuracoes(self, *, dry_run: bool = False) -> dict:
        """
        Sincroniza todos os catálogos do HubSoft de uma vez.
        Retorna dict com resumo por catálogo + total_geral.
        """
        resultado = {}

        # Catálogos persistidos em modelo CRM
        try:
            resultado['servicos'] = self.sincronizar_servicos_catalogo(dry_run=dry_run)
        except HubsoftServiceError as exc:
            resultado['servicos'] = {'erro': str(exc)}

        try:
            resultado['vencimentos'] = self.sincronizar_vencimentos(dry_run=dry_run)
        except HubsoftServiceError as exc:
            resultado['vencimentos'] = {'erro': str(exc)}

        # Catálogos cacheados
        for chave in self.CATALOGOS_CACHE:
            try:
                resultado[chave] = self.sincronizar_catalogo_cacheado(chave, dry_run=dry_run)
            except HubsoftServiceError as exc:
                resultado[chave] = {'erro': str(exc)}

        # Sumário rápido
        total = sum(
            (r.get('criados', 0) + r.get('atualizados', 0))
            for r in resultado.values() if isinstance(r, dict) and 'erro' not in r
        )
        resultado['_total_geral'] = total
        resultado['_dry_run'] = dry_run
        return resultado

    def _persistir_cache(self, chave: str, itens: list, *, fn_chave, dry_run: bool) -> dict:
        """
        Guarda `itens` em integracao.configuracoes_extras['cache'][<chave>].
        Compara com o cache anterior pra reportar criados/atualizados/inalterados.
        """
        extras = dict(self.integracao.configuracoes_extras or {})
        cache = dict(extras.get('cache') or {})
        anterior = {fn_chave(i): i for i in (cache.get(chave) or [])}
        atual = {fn_chave(i): i for i in itens}

        criados = sum(1 for k in atual if k not in anterior)
        atualizados = sum(
            1 for k, v in atual.items() if k in anterior and anterior[k] != v
        )
        inalterados = sum(
            1 for k, v in atual.items() if k in anterior and anterior[k] == v
        )

        resumo = {
            'total': len(itens), 'criados': criados, 'atualizados': atualizados,
            'inalterados': inalterados, 'dry_run': dry_run,
        }
        if dry_run:
            return resumo

        cache[chave] = itens
        extras['cache'] = cache
        type(self.integracao).objects.filter(pk=self.integracao.pk).update(
            configuracoes_extras=extras,
        )
        self.integracao.configuracoes_extras = extras
        return resumo

    # ------------------------------------------------------------------
    # Financeiro — Bloco H3 (escopo enxuto: faturas + renegociacao)
    # ------------------------------------------------------------------

    def listar_faturas_cliente(
        self,
        *,
        cpf_cnpj: str = None,
        id_cliente: int = None,
        codigo_cliente: int = None,
        apenas_pendente: bool = False,
        limit: int = None,
        order_by: str = None,
        order_type: str = None,
        lead=None,
    ) -> list:
        """
        Lista faturas (boletos) de um cliente no HubSoft.

        Identificacao: passar `cpf_cnpj`, `id_cliente` ou `codigo_cliente`
        (pelo menos um). HubSoft chama isso de `busca` + `termo_busca`.

        Cada fatura traz status, valor, datas, codigo de barras, linha
        digitavel, link do PDF e PIX copia/cola quando disponivel.
        """
        if cpf_cnpj:
            params = {'busca': 'cpf_cnpj', 'termo_busca': self._somente_numeros(cpf_cnpj)}
        elif id_cliente:
            params = {'busca': 'id_cliente', 'termo_busca': str(int(id_cliente))}
        elif codigo_cliente:
            params = {'busca': 'codigo_cliente', 'termo_busca': str(int(codigo_cliente))}
        else:
            raise HubsoftServiceError(
                'listar_faturas_cliente: informe cpf_cnpj, id_cliente ou codigo_cliente.'
            )

        if apenas_pendente:
            params['apenas_pendente'] = 'sim'
        if limit:
            params['limit'] = int(limit)
        if order_by:
            params['order_by'] = order_by
        if order_type:
            params['order_type'] = order_type

        resposta = self._get(self.ENDPOINT_CLIENTE_FINANCEIRO, params=params, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft retornou erro em /cliente/financeiro: {resposta}"
            )
        return resposta.get('faturas') or []

    def listar_renegociacoes(
        self,
        *,
        cpf_cnpj: str = None,
        documento_empresa: str = None,
        status: str = None,
        data_inicio: str = None,
        data_fim: str = None,
        pagina: int = 0,
        itens_por_pagina: int = 100,
        lead=None,
    ) -> dict:
        """
        Lista renegociacoes (acordos). Datas no formato 'YYYY-MM-DD'.

        Retorna {'paginacao': {...}, 'renegociacoes': [...]}.
        """
        params = {'pagina': int(pagina), 'itens_por_pagina': int(itens_por_pagina)}
        if cpf_cnpj:
            params['documento_cliente'] = self._somente_numeros(cpf_cnpj)
        if documento_empresa:
            params['documento_empresa'] = self._somente_numeros(documento_empresa)
        if status:
            params['status'] = status
        if data_inicio:
            params['data_inicio'] = data_inicio
        if data_fim:
            params['data_fim'] = data_fim

        resposta = self._get(self.ENDPOINT_RENEGOCIACAO_LISTAR, params=params, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft retornou erro em /financeiro/renegociacao: {resposta}"
            )
        return {
            'paginacao': resposta.get('paginacao') or {},
            'renegociacoes': resposta.get('renegociacoes') or [],
        }

    def simular_renegociacao(
        self,
        *,
        ids_faturas: list,
        quantidade_parcelas: int,
        vencimento: str,
        id_cliente: int = None,
        cpf_cnpj: str = None,
        cliente_servico: int = None,
        forma_cobranca: int = None,
        empresa: int = None,
        lead=None,
    ) -> dict:
        """
        Simula renegociacao sem efetivar. Retorna parcelas geradas.

        - `ids_faturas`: lista de ids de faturas em aberto a renegociar
        - `quantidade_parcelas`: numero de parcelas do acordo
        - `vencimento`: 'YYYY-MM-DD' da primeira parcela
        - `id_cliente` ou `cpf_cnpj`: identificacao do cliente
        - `cliente_servico`, `forma_cobranca`, `empresa`: opcionais — usados
          quando o tenant nao tem regra de renegociacao configurada no HubSoft

        Retorna dict com `regra_utilizada` + `faturas_que_foram_geradas`.
        """
        return self._renegociacao_post(
            self.ENDPOINT_RENEGOCIACAO_SIMULAR,
            ids_faturas=ids_faturas,
            quantidade_parcelas=quantidade_parcelas,
            vencimento=vencimento,
            id_cliente=id_cliente, cpf_cnpj=cpf_cnpj,
            cliente_servico=cliente_servico, forma_cobranca=forma_cobranca,
            empresa=empresa, lead=lead,
        )

    def efetivar_renegociacao(
        self,
        *,
        ids_faturas: list,
        quantidade_parcelas: int,
        vencimento: str,
        id_cliente: int = None,
        cpf_cnpj: str = None,
        cliente_servico: int = None,
        forma_cobranca: int = None,
        empresa: int = None,
        lead=None,
    ) -> dict:
        """
        Efetiva a renegociacao no HubSoft. Mesmo payload de simular_renegociacao.
        Cria as parcelas e cancela as faturas originais.
        """
        return self._renegociacao_post(
            self.ENDPOINT_RENEGOCIACAO_EFETIVAR,
            ids_faturas=ids_faturas,
            quantidade_parcelas=quantidade_parcelas,
            vencimento=vencimento,
            id_cliente=id_cliente, cpf_cnpj=cpf_cnpj,
            cliente_servico=cliente_servico, forma_cobranca=forma_cobranca,
            empresa=empresa, lead=lead,
        )

    def _renegociacao_post(
        self,
        endpoint: str,
        *,
        ids_faturas: list,
        quantidade_parcelas: int,
        vencimento: str,
        id_cliente: int = None,
        cpf_cnpj: str = None,
        cliente_servico: int = None,
        forma_cobranca: int = None,
        empresa: int = None,
        lead=None,
    ) -> dict:
        """Helper compartilhado por simular/efetivar (mesma forma de payload)."""
        if not ids_faturas:
            raise HubsoftServiceError('renegociacao: ids_faturas eh obrigatorio.')
        if not vencimento:
            raise HubsoftServiceError('renegociacao: vencimento eh obrigatorio (YYYY-MM-DD).')
        if not quantidade_parcelas or int(quantidade_parcelas) < 1:
            raise HubsoftServiceError('renegociacao: quantidade_parcelas deve ser >= 1.')

        if id_cliente:
            tipo_dados = 'id_cliente'
            dados = int(id_cliente)
        elif cpf_cnpj:
            tipo_dados = 'cpf_cnpj'
            dados = self._somente_numeros(cpf_cnpj)
        else:
            raise HubsoftServiceError('renegociacao: informe id_cliente OU cpf_cnpj.')

        payload = {
            'vencimento': vencimento,
            'faturas': 'definir_faturas',
            'quantidade_parcelas': int(quantidade_parcelas),
            'ids_faturas': [int(i) for i in ids_faturas],
            'tipo_dados_cliente': tipo_dados,
            'dados_cliente': dados,
        }
        # Campos opcionais — exigidos quando tenant nao tem regra de renegociacao
        if cliente_servico is not None:
            payload['cliente_servico'] = int(cliente_servico)
        if forma_cobranca is not None:
            payload['forma_cobranca'] = int(forma_cobranca)
        if empresa is not None:
            payload['empresa'] = int(empresa)

        resposta = self._post(endpoint, json=payload, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft rejeitou renegociacao em {endpoint}: {resposta}"
            )
        return resposta

    # ------------------------------------------------------------------
    # Operacional — Bloco H4 (suporte de 1a linha)
    # ------------------------------------------------------------------

    def verificar_extrato_conexao(
        self,
        *,
        busca: str = 'login',
        termo_busca: str,
        limit: int = 20,
        data_inicio: str = None,
        data_fim: str = None,
        lead=None,
    ) -> list:
        """
        Lista historico de conexoes (RADIUS) do cliente.

        - `busca`: campo usado como filtro: 'login' | 'ipv4' | 'ipv6_wan' | 'ipv6_lan' | 'mac'
        - `termo_busca`: valor do filtro (ex: o login PPPoE do cliente)
        - `limit`: 1 a 50 (default 20)
        - `data_inicio` / `data_fim`: 'YYYY-MM-DD' (default: ultimos 30 dias)

        Retorna lista de registros com acctstarttime/stoptime, IPs, MAC,
        upload/download em MB, etc. Util pra atendente checar se cliente
        ta online ou quando caiu pela ultima vez.
        """
        if not termo_busca:
            raise HubsoftServiceError('verificar_extrato_conexao: termo_busca obrigatorio.')
        params = {'busca': busca, 'termo_busca': termo_busca, 'limit': int(limit)}
        if data_inicio:
            params['data_inicio'] = data_inicio
        if data_fim:
            params['data_fim'] = data_fim
        resposta = self._get(self.ENDPOINT_EXTRATO_CONEXAO, params=params, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft retornou erro em /cliente/extrato_conexao: {resposta}"
            )
        return resposta.get('registros') or []

    def solicitar_desconexao(self, id_cliente_servico: int, *, lead=None) -> dict:
        """
        Forca desconexao do cliente no concentrador (PPPoE). Util pra refazer
        conexao apos mudanca de plano ou diagnostico.
        """
        if not id_cliente_servico:
            raise HubsoftServiceError('solicitar_desconexao: id_cliente_servico obrigatorio.')
        endpoint = self.ENDPOINT_SOLICITAR_DESCONEXAO_TPL.format(
            id_cliente_servico=int(id_cliente_servico),
        )
        resposta = self._get(endpoint, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft rejeitou solicitar_desconexao: {resposta}"
            )
        return resposta

    def desbloqueio_confianca(
        self,
        id_cliente_servico: int,
        *,
        dias_desbloqueio: int = 1,
        lead=None,
    ) -> dict:
        """
        Libera o servico do cliente por N dias (mesmo com fatura em aberto).
        Acao tipica de retencao.
        """
        if not id_cliente_servico:
            raise HubsoftServiceError('desbloqueio_confianca: id_cliente_servico obrigatorio.')
        payload = {
            'id_cliente_servico': str(int(id_cliente_servico)),
            'dias_desbloqueio': str(int(dias_desbloqueio)),
        }
        resposta = self._post(self.ENDPOINT_DESBLOQUEIO_CONFIANCA, json=payload, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft rejeitou desbloqueio_confianca: {resposta}"
            )
        return resposta

    def reset_mac_addr(self, id_cliente_servico: int, *, lead=None) -> dict:
        """Reseta o MAC autorizado no concentrador. Cliente pode reconectar com qualquer dispositivo."""
        return self._reset_addr(self.ENDPOINT_RESET_MAC, id_cliente_servico, lead=lead)

    def reset_phy_addr(self, id_cliente_servico: int, *, lead=None) -> dict:
        """Reseta o MAC Layer2 (phy) — usado em alguns concentradores."""
        return self._reset_addr(self.ENDPOINT_RESET_PHY, id_cliente_servico, lead=lead)

    def _reset_addr(self, endpoint: str, id_cliente_servico: int, *, lead=None) -> dict:
        if not id_cliente_servico:
            raise HubsoftServiceError(f'reset em {endpoint}: id_cliente_servico obrigatorio.')
        payload = {'id_cliente_servico': str(int(id_cliente_servico))}
        resposta = self._post(endpoint, json=payload, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(f"HubSoft rejeitou {endpoint}: {resposta}")
        return resposta

    def suspender_servico(
        self,
        id_cliente_servico: int,
        *,
        tipo_suspensao: str = 'suspenso_debito',
        lead=None,
    ) -> dict:
        """
        Suspende um servico do cliente. tipo_suspensao tipico:
        'suspenso_debito', 'suspenso_solicitacao_cliente'.
        """
        if not id_cliente_servico:
            raise HubsoftServiceError('suspender_servico: id_cliente_servico obrigatorio.')
        endpoint = self.ENDPOINT_SVC_SUSPENDER_TPL.format(id=int(id_cliente_servico))
        payload = {'tipo_suspensao': tipo_suspensao}
        resposta = self._post(endpoint, json=payload, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(f"HubSoft rejeitou suspender_servico: {resposta}")
        return resposta

    def habilitar_servico(
        self,
        id_cliente_servico: int,
        *,
        motivo_habilitacao: str = 'Habilitado via Hubtrix.',
        lead=None,
    ) -> dict:
        """Reabilita servico previamente suspenso."""
        if not id_cliente_servico:
            raise HubsoftServiceError('habilitar_servico: id_cliente_servico obrigatorio.')
        endpoint = self.ENDPOINT_SVC_HABILITAR_TPL.format(id=int(id_cliente_servico))
        payload = {'motivo_habilitacao': motivo_habilitacao}
        resposta = self._post(endpoint, json=payload, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(f"HubSoft rejeitou habilitar_servico: {resposta}")
        return resposta

    def ativar_servico(self, id_cliente_servico: int, *, lead=None) -> dict:
        """Ativa servico que estava aguardando ativacao (pos-instalacao)."""
        if not id_cliente_servico:
            raise HubsoftServiceError('ativar_servico: id_cliente_servico obrigatorio.')
        endpoint = self.ENDPOINT_SVC_ATIVAR_TPL.format(id=int(id_cliente_servico))
        resposta = self._post(endpoint, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(f"HubSoft rejeitou ativar_servico: {resposta}")
        return resposta

    # ------------------------------------------------------------------
    # Viabilidade / cobertura — Bloco H5
    # ------------------------------------------------------------------

    def consultar_viabilidade_endereco(
        self,
        *,
        endereco: str,
        numero: str,
        bairro: str,
        cidade: str,
        estado: str,
        raio: int = 250,
        detalhar_portas: bool = True,
        lead=None,
    ) -> dict:
        """
        Consulta viabilidade tecnica por endereco. Retorna projetos de
        mapeamento e caixas opticas proximas (com portas disponiveis se
        detalhar_portas=True).

        `raio` em metros (default 250m).
        """
        payload = {
            'tipo_busca': 'endereco',
            'raio': int(raio),
            'endereco': {
                'numero': str(numero),
                'endereco': endereco,
                'bairro': bairro,
                'cidade': cidade,
                'estado': (estado or '').upper(),
            },
            'detalhar_portas': bool(detalhar_portas),
        }
        return self._consultar_viabilidade(payload, lead=lead)

    def consultar_viabilidade_coords(
        self,
        *,
        latitude: float,
        longitude: float,
        raio: int = 250,
        detalhar_portas: bool = True,
        lead=None,
    ) -> dict:
        """Mesmo que consultar_viabilidade_endereco mas por lat/lng."""
        payload = {
            'tipo_busca': 'coordenadas',
            'raio': int(raio),
            'latitude': float(latitude),
            'longitude': float(longitude),
            'detalhar_portas': bool(detalhar_portas),
        }
        return self._consultar_viabilidade(payload, lead=lead)

    def _consultar_viabilidade(self, payload: dict, *, lead=None) -> dict:
        resposta = self._post(self.ENDPOINT_VIABILIDADE, json=payload, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft retornou erro em /viabilidade/consultar: {resposta}"
            )
        return resposta.get('resultado') or {}

    def listar_planos_por_cep(self, cep: str, *, lead=None) -> list:
        """
        Lista planos/servicos disponiveis para um CEP especifico.

        Retorna lista de servicos com id_servico, descricao, valor (real,
        diferente do /configuracao/servico que nao traz preco), velocidades
        e display ja formatado.
        """
        cep_limpo = self._somente_numeros(cep)
        if not cep_limpo:
            raise HubsoftServiceError('listar_planos_por_cep: cep obrigatorio.')
        resposta = self._get(self.ENDPOINT_PROSPECTO_CREATE, params={'cep': cep_limpo}, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft retornou erro em /prospecto/create?cep={cep_limpo}: {resposta}"
            )
        return resposta.get('servicos') or []

    # ------------------------------------------------------------------
    # Atendimento / OS — Bloco H6 (LEITURA, reduzido em 26/04)
    # ------------------------------------------------------------------

    def listar_atendimentos_cliente(
        self,
        *,
        cpf_cnpj: str = None,
        id_cliente: int = None,
        codigo_cliente: int = None,
        limit: int = 20,
        lead=None,
    ) -> list:
        """
        Lista atendimentos abertos no HubSoft pra um cliente.
        Util pra mostrar "ja existem N atendimentos abertos" antes do
        atendente abrir um novo.
        """
        params = self._params_busca_cliente(cpf_cnpj, id_cliente, codigo_cliente)
        if limit:
            params['limit'] = int(limit)
        resposta = self._get(self.ENDPOINT_CLIENTE_ATENDIMENTO, params=params, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft retornou erro em /cliente/atendimento: {resposta}"
            )
        return resposta.get('atendimentos') or []

    def listar_os_cliente(
        self,
        *,
        cpf_cnpj: str = None,
        id_cliente: int = None,
        codigo_cliente: int = None,
        limit: int = 20,
        lead=None,
    ) -> list:
        """Lista ordens de servico do cliente."""
        params = self._params_busca_cliente(cpf_cnpj, id_cliente, codigo_cliente)
        if limit:
            params['limit'] = int(limit)
        resposta = self._get(self.ENDPOINT_CLIENTE_OS, params=params, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft retornou erro em /cliente/ordem_servico: {resposta}"
            )
        return resposta.get('ordens_servico') or resposta.get('ordem_servico') or []

    # ------------------------------------------------------------------
    # Endpoints /todos paginados — pra sync em lote (relatorios + CS)
    # Resposta tem `paginacao` com {primeira_pagina, ultima_pagina, pagina_atual, total_registros}
    # ------------------------------------------------------------------

    def listar_clientes_todos(
        self, *,
        pagina: int = 0,
        itens_por_pagina: int = 100,
        data_inicio: str = None,
        data_fim: str = None,
        cancelado: str = None,
        servico_status: str = None,
        relacoes: str = None,
    ) -> dict:
        """
        GET /api/v1/integracao/cliente/todos paginado.
        `data_inicio`/`data_fim` em formato YYYY-MM-DD pra delta sync.
        Retorna dict completo: {status, msg, paginacao, clientes[]}.
        `clientes[].servicos` vem inline (sem N+1).
        """
        params = {'pagina': int(pagina), 'itens_por_pagina': int(itens_por_pagina)}
        if data_inicio:
            params['data_inicio'] = data_inicio
        if data_fim:
            params['data_fim'] = data_fim
        if cancelado is not None:
            params['cancelado'] = cancelado
        if servico_status:
            params['servico_status'] = servico_status
        if relacoes:
            params['relacoes'] = relacoes
        resposta = self._get('/api/v1/integracao/cliente/todos', params=params)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft retornou erro em /cliente/todos: {resposta}"
            )
        return resposta

    def listar_os_todos(
        self, *,
        pagina: int = 0,
        itens_por_pagina: int = 100,
        data_inicio: str = None,
        data_fim: str = None,
    ) -> dict:
        """
        GET /api/v1/integracao/ordem_servico/todos paginado.
        Retorna {status, paginacao, ordens_servico[]}.
        """
        params = {'pagina': int(pagina), 'itens_por_pagina': int(itens_por_pagina)}
        if data_inicio:
            params['data_inicio'] = data_inicio
        if data_fim:
            params['data_fim'] = data_fim
        resposta = self._get('/api/v1/integracao/ordem_servico/todos', params=params)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft retornou erro em /ordem_servico/todos: {resposta}"
            )
        return resposta

    def listar_atendimentos_todos(
        self, *,
        pagina: int = 0,
        itens_por_pagina: int = 100,
        data_inicio: str = None,
        data_fim: str = None,
        relacoes: str = None,
    ) -> dict:
        """
        GET /api/v1/integracao/atendimento/todos paginado.
        Retorna {status, paginacao, atendimentos[]}.
        """
        params = {'pagina': int(pagina), 'itens_por_pagina': int(itens_por_pagina)}
        if data_inicio:
            params['data_inicio'] = data_inicio
        if data_fim:
            params['data_fim'] = data_fim
        if relacoes:
            params['relacoes'] = relacoes
        resposta = self._get('/api/v1/integracao/atendimento/todos', params=params)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft retornou erro em /atendimento/todos: {resposta}"
            )
        return resposta

    # ------------------------------------------------------------------
    # Abertura / agendamento de OS (camada que substitui o apimatrix)
    # ------------------------------------------------------------------

    def abrir_atendimento_os(
        self, *,
        id_cliente_servico,
        descricao: str,
        nome: str,
        telefone: str,
        email: str = None,
        id_tipo_atendimento=None,
        id_atendimento_status=None,
        id_usuario_responsavel=None,
        abrir_os: bool = True,
        id_tipo_ordem_servico=None,
        status_os: str = None,
        ids_tecnicos: list = None,
        id_disponibilidade=None,
        parametros: dict = None,
        lead=None,
    ) -> dict:
        """Abre atendimento no HubSoft (POST /atendimento) e, com abrir_os=True,
        abre a OS na mesma chamada. Retorna o objeto `atendimento` (com
        `id_atendimento` e `ordens_servico[]`).
        """
        payload = {
            'id_cliente_servico': id_cliente_servico,
            'descricao': descricao,
            'nome': nome,
            'telefone': self._somente_numeros(telefone),
        }
        if email:
            payload['email'] = email
        if id_tipo_atendimento is not None:
            payload['id_tipo_atendimento'] = id_tipo_atendimento
        if id_atendimento_status is not None:
            payload['id_atendimento_status'] = id_atendimento_status
        if id_usuario_responsavel is not None:
            payload['id_usuario_responsavel'] = id_usuario_responsavel
        if parametros:
            payload['parametros'] = parametros
        if abrir_os:
            payload['abrir_os'] = True
            pos = {}
            if id_tipo_ordem_servico is not None:
                pos['id_tipo_ordem_servico'] = id_tipo_ordem_servico
            if status_os:
                pos['status'] = status_os
            if ids_tecnicos:
                pos['ids_tecnicos'] = [str(t) for t in ids_tecnicos]
            if id_disponibilidade is not None:
                pos['id_disponibilidade'] = id_disponibilidade
            if pos:
                payload['parametros_ordem_servico'] = pos

        resposta = self._post(self.ENDPOINT_ATENDIMENTO_CREATE, json=payload, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft rejeitou abertura de atendimento/OS: {resposta}"
            )
        return resposta.get('atendimento') or {}

    def consultar_horarios_agenda(
        self, *,
        id_agenda_ordem_servico=None,
        descricao: str = None,
        data_inicio: str = None,
        dias: int = 1,
        lead=None,
    ) -> dict:
        """Consulta horarios disponiveis numa agenda de OS.

        Informe `id_agenda_ordem_servico` OU `descricao` da agenda. `data_inicio`
        no formato YYYY-MM-DD. Retorna o bloco `horarios` (datas -> horarios ->
        tecnicos) cru do HubSoft.
        """
        if not id_agenda_ordem_servico and not descricao:
            raise HubsoftServiceError('consultar_horarios_agenda: informe id_agenda_ordem_servico ou descricao.')
        params = {}
        if id_agenda_ordem_servico is not None:
            params['id_agenda_ordem_servico'] = id_agenda_ordem_servico
        if descricao:
            params['descricao'] = descricao
        if data_inicio:
            params['data_inicio'] = data_inicio
        if dias:
            params['dias'] = int(dias)
        resposta = self._get(self.ENDPOINT_OS_HORARIOS_AGENDA, params=params, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft erro em horarios_disponiveis_agenda: {resposta}"
            )
        return resposta.get('horarios') or {}

    def agendar_os(self, id_ordem_servico, *, lead=None) -> dict:
        """Agenda uma OS que esta aguardando agendamento (POST /ordem_servico/agendar)."""
        resposta = self._post(
            self.ENDPOINT_OS_AGENDAR, json={'id_ordem_servico': int(id_ordem_servico)}, lead=lead,
        )
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft erro ao agendar OS {id_ordem_servico}: {resposta}"
            )
        return resposta

    def abrir_os(
        self, *,
        id_atendimento,
        id_agenda_ordem_servico=None,
        id_tipo_ordem_servico=None,
        data_inicio_programado: str = None,
        data_termino_programado: str = None,
        hora_inicio_programado: str = None,
        hora_termino_programado: str = None,
        status: str = None,
        descricao_servico: str = None,
        tecnicos: list = None,
        disponibilidade: list = None,
        lead=None,
    ) -> dict:
        """Abre uma OS a partir de um atendimento existente
        (POST /ordem_servico/abrir_os?id_atendimento=), ja com o slot escolhido.

        `tecnicos`: lista de ids -> vira {"0": {"id": x}, ...}
        `disponibilidade`: lista de prefixos (ex: ["manha"]) -> vira {"0": "manha", ...}
        Retorna o objeto `ordem_servico`.
        """
        body = {}
        if id_agenda_ordem_servico is not None:
            body['id_agenda_ordem_servico'] = id_agenda_ordem_servico
        if id_tipo_ordem_servico is not None:
            body['id_tipo_ordem_servico'] = id_tipo_ordem_servico
        if data_inicio_programado:
            body['data_inicio_programado'] = data_inicio_programado
        if data_termino_programado:
            body['data_termino_programado'] = data_termino_programado
        if hora_inicio_programado:
            body['hora_inicio_programado'] = hora_inicio_programado
        if hora_termino_programado:
            body['hora_termino_programado'] = hora_termino_programado
        if status:
            body['status'] = status
        if descricao_servico:
            body['descricao_servico'] = descricao_servico
        if tecnicos:
            body['tecnicos'] = {str(i): {'id': int(t)} for i, t in enumerate(tecnicos)}
        if disponibilidade:
            body['disponibilidade'] = {str(i): str(d) for i, d in enumerate(disponibilidade)}

        endpoint = f'{self.ENDPOINT_OS_ABRIR}?id_atendimento={int(id_atendimento)}'
        resposta = self._post(endpoint, json=body, lead=lead)
        if resposta.get('status') != 'success':
            raise HubsoftServiceError(
                f"HubSoft rejeitou abrir_os (atendimento {id_atendimento}): {resposta}"
            )
        return resposta.get('ordem_servico') or {}

    def _params_busca_cliente(self, cpf_cnpj=None, id_cliente=None, codigo_cliente=None) -> dict:
        """Helper compartilhado: monta busca/termo_busca pra endpoints de cliente."""
        if cpf_cnpj:
            return {'busca': 'cpf_cnpj', 'termo_busca': self._somente_numeros(cpf_cnpj)}
        if id_cliente:
            return {'busca': 'id_cliente', 'termo_busca': str(int(id_cliente))}
        if codigo_cliente:
            return {'busca': 'codigo_cliente', 'termo_busca': str(int(codigo_cliente))}
        raise HubsoftServiceError('Informe cpf_cnpj, id_cliente ou codigo_cliente.')

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
        cache = (extras.get('cache') or {})

        def _id_valido_ou_default(lead_id, default_id, cache_chave, item_id_key):
            """Retorna o ID do lead se for valido no catalogo cacheado, senao
            cai pro default da integracao. Resolve o caso onde o Matrix manda
            IDs desatualizados (ex: HubSoft renumera vendedor entre dias).

            cache_chave: nome do array em configuracoes_extras.cache
            item_id_key: nome da chave do id dentro de cada item do array

            Se o cache esta vazio, mantem o comportamento antigo (sem guard).
            """
            try:
                lead_id_int = int(lead_id) if lead_id else None
            except (ValueError, TypeError):
                lead_id_int = None
            itens = cache.get(cache_chave) or []
            if lead_id_int and itens:
                ids_validos = {int(it.get(item_id_key)) for it in itens if it.get(item_id_key) is not None}
                if lead_id_int not in ids_validos:
                    logger.warning(
                        '[HubSoft] %s=%s do lead %s nao existe no catalogo (%s itens). '
                        'Usando default=%s da IntegracaoAPI.',
                        item_id_key, lead_id_int, getattr(lead, 'pk', '?'), len(itens), default_id,
                    )
                    lead_id_int = None
            return lead_id_int or (int(default_id) if default_id else None)

        plano_id = lead.id_plano_rp or extras.get('plano_id_padrao') or 0
        payload['servico'] = {
            'id_servico': int(plano_id) if plano_id else 0,
            'valor': float(lead.valor) if lead.valor else 0,
        }

        vendedor_id = _id_valido_ou_default(
            lead.id_vendedor_rp, extras.get('vendedor_id_padrao'),
            cache_chave='vendedores', item_id_key='id',
        )
        if vendedor_id:
            payload['id_vendedor'] = vendedor_id

        venc_id = lead.id_dia_vencimento or extras.get('dia_vencimento_id_padrao')
        if venc_id:
            payload['id_vencimento'] = int(venc_id)

        origem_id = _id_valido_ou_default(
            lead.id_origem, extras.get('id_origem_padrao'),
            cache_chave='origens_cliente', item_id_key='id_origem_cliente',
        )
        if origem_id:
            payload['id_origem_cliente'] = origem_id

        origem_servico_id = _id_valido_ou_default(
            lead.id_origem_servico, extras.get('id_origem_servico_padrao'),
            cache_chave='origens_contato', item_id_key='id_origem_contato',
        )
        if origem_servico_id:
            payload['id_origem_servico'] = origem_servico_id

        payload['id_externo'] = str(lead.pk)
        return payload

    def _mapear_lead_para_hubsoft_editar(self, lead) -> dict:
        """Payload pro endpoint PUT /prospecto/{id} (editar).

        Diferencas vs create:
        - endereco usa prefixo `prospecto_endereco.*` (nao flat)
        - servico usa prefixo `prospecto_servico.*` (nao `servico.*`)
        - TODOS os campos sao opcionais — so passa o que tem valor preenchido
        - update parcial (subset aceito pela API)
        """
        payload: dict = {}

        if lead.nome_razaosocial:
            payload['nome_razaosocial'] = lead.nome_razaosocial
        payload['tipo_pessoa'] = self._detectar_tipo_pessoa(lead.cpf_cnpj)

        if lead.cpf_cnpj:
            payload['cpf_cnpj'] = self._somente_numeros(lead.cpf_cnpj)
        if lead.telefone:
            payload['telefone'] = self._normalizar_telefone(lead.telefone)
        if lead.email:
            payload['email'] = lead.email
        if lead.observacoes:
            payload['observacao'] = lead.observacoes
        if lead.rg:
            payload['rg'] = lead.rg
        if lead.data_nascimento:
            payload['data_nascimento'] = lead.data_nascimento.strftime('%d/%m/%Y')

        # Endereco aninhado como objeto JSON (prospecto_endereco: {...})
        # — formato corrigido 18/06: antes usavamos dotnotation flat
        # ("prospecto_endereco.cep") mas HubSoft retornava success silencioso
        # sem aplicar os campos. Aninhado como objeto funciona.
        endereco: dict = {}
        if lead.cep:
            endereco['cep'] = self._somente_numeros(lead.cep)
        if lead.rua or lead.endereco:
            endereco['endereco'] = lead.rua or lead.endereco
        if lead.bairro:
            endereco['bairro'] = lead.bairro
        if lead.numero_residencia:
            endereco['numero'] = lead.numero_residencia
        if lead.ponto_referencia:
            endereco['referencia'] = lead.ponto_referencia
        if endereco:
            payload['prospecto_endereco'] = endereco

        # Servico aninhado (prospecto_servico: {...})
        servico: dict = {}
        extras = self.integracao.configuracoes_extras or {}
        plano_id = lead.id_plano_rp or extras.get('plano_id_padrao')
        if plano_id:
            servico['id_servico'] = int(plano_id)
        if lead.valor:
            servico['valor'] = float(lead.valor)
        if servico:
            payload['prospecto_servico'] = servico

        # Relacionamento (flat, igual ao create)
        if lead.id_origem:
            payload['id_origem_cliente'] = int(lead.id_origem)
        if lead.id_dia_vencimento:
            payload['id_vencimento'] = int(lead.id_dia_vencimento)
        if lead.id_vendedor_rp:
            try:
                payload['id_vendedor'] = int(lead.id_vendedor_rp)
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

    # Resiliência: retry com exponential backoff em erros transitórios
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 1.5  # segundos. Tentativa 1: 1.5s, 2: 3s, 3: 6s
    RETRY_STATUS_CODES = {408, 429, 500, 502, 503, 504}

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
        Wrapper HTTP único: aplica auth (Bearer ou skip), executa com retry
        em erros transitórios (timeouts, 5xx, 429), registra LogIntegracao,
        levanta HubsoftServiceError em falha definitiva.

        - 4xx (exceto 408/429) não são reexecutadas — erros do cliente.
        - 5xx, timeouts, conn refused são reexecutados até MAX_RETRIES com backoff exponencial.
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

        ultimo_erro = None

        for tentativa in range(1, self.MAX_RETRIES + 1):
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
                # Erro de conexão / timeout — sempre tentar de novo se ainda houver tentativas
                tempo_ms = int((time.time() - inicio) * 1000)
                ultimo_erro = str(exc)

                if tentativa < self.MAX_RETRIES:
                    self._registrar_log(
                        endpoint=endpoint, metodo=metodo,
                        payload=payload_para_log, resposta={},
                        status_code=0, sucesso=False,
                        erro=f"[Tentativa {tentativa}/{self.MAX_RETRIES}] {exc}",
                        tempo_ms=tempo_ms, lead=lead,
                    )
                    time.sleep(self.RETRY_BACKOFF_BASE * (2 ** (tentativa - 1)))
                    continue

                # Esgotou tentativas — registra final e levanta
                self._registrar_log(
                    endpoint=endpoint, metodo=metodo,
                    payload=payload_para_log, resposta={},
                    status_code=0, sucesso=False,
                    erro=f"[FINAL após {tentativa} tentativas] {exc}",
                    tempo_ms=tempo_ms, lead=lead,
                )
                raise HubsoftServiceError(f"Falha de conexão com HubSoft após {tentativa} tentativas: {exc}") from exc

            # Resposta HTTP recebida — checar status
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

            if sucesso:
                self._registrar_log(
                    endpoint=endpoint, metodo=metodo,
                    payload=payload_para_log,
                    resposta=resposta_para_log,
                    status_code=resp.status_code,
                    sucesso=True,
                    erro='' if tentativa == 1 else f"Sucesso após {tentativa} tentativas",
                    tempo_ms=tempo_ms, lead=lead,
                )
                if isinstance(resposta_json, dict):
                    return resposta_json
                return {'list': resposta_json}

            # Falha — decidir se reexecuta
            ultimo_erro = f"HTTP {resp.status_code}: {msg_erro_api}"

            if resp.status_code in self.RETRY_STATUS_CODES and tentativa < self.MAX_RETRIES:
                self._registrar_log(
                    endpoint=endpoint, metodo=metodo,
                    payload=payload_para_log,
                    resposta=resposta_para_log,
                    status_code=resp.status_code,
                    sucesso=False,
                    erro=f"[Tentativa {tentativa}/{self.MAX_RETRIES}] {ultimo_erro}",
                    tempo_ms=tempo_ms, lead=lead,
                )
                time.sleep(self.RETRY_BACKOFF_BASE * (2 ** (tentativa - 1)))
                continue

            # Erro não-retryable (4xx) ou esgotou tentativas — falha final
            erro_final = (
                f"[FINAL após {tentativa} tentativas] {ultimo_erro}"
                if tentativa > 1 else ultimo_erro
            )
            self._registrar_log(
                endpoint=endpoint, metodo=metodo,
                payload=payload_para_log,
                resposta=resposta_para_log,
                status_code=resp.status_code,
                sucesso=False,
                erro=erro_final,
                tempo_ms=tempo_ms, lead=lead,
            )
            raise HubsoftServiceError(
                f"Erro HubSoft em {endpoint} (HTTP {resp.status_code}): {resposta_json}"
            )

        # Esgotou retries sem sucesso (caminho defensivo)
        raise HubsoftServiceError(
            f"Falha definitiva em {endpoint} após {self.MAX_RETRIES} tentativas: {ultimo_erro}"
        )

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
