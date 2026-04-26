import logging
import time
from decimal import Decimal

import requests

from apps.integracoes.models import IntegracaoAPI, LogIntegracao

logger = logging.getLogger(__name__)


class SGPServiceError(Exception):
    """Erro genérico do serviço SGP."""
    pass


class SGPService:
    """
    Encapsula a comunicação com a API do SGP (inSystem).

    Autenticação: `app + token` como campos de formdata em cada request.
    Diferente do HubSoft (OAuth2 Bearer), o SGP não rotaciona token
    automaticamente; o token é estático até ser revogado no painel.

    Fase 2.1b: autenticação + catálogos (planos, vencimentos).
    Fase 2.2: fluxo lead → cliente (cadastrar_prospecto, sincronizar_cliente).
    """

    # Mapeamento dos campos da IntegracaoAPI para os conceitos SGP:
    #   integracao.client_id     → app (nome da aplicação no SGP)
    #   integracao.access_token  → token (gerado em Sistema → Ferramentas → Painel Admin → Tokens)
    #   integracao.base_url      → URL base da instância do provedor (ex: https://gigamax.sgp.net.br)

    ENDPOINT_VALIDAR = '/api/precadastro/plano/list'
    ENDPOINT_PLANOS = '/api/precadastro/plano/list'
    ENDPOINT_VENCIMENTOS = '/api/precadastro/vencimento/list'
    ENDPOINT_VENDEDORES = '/api/precadastro/vendedor/list'
    ENDPOINT_POPS = '/api/ura/pops/'
    ENDPOINT_PORTADORES = '/api/ura/portador/'
    ENDPOINT_CONSULTA_CLIENTE = '/api/ura/consultacliente/'
    ENDPOINT_PRECADASTRO_PF = '/api/precadastro/F'
    ENDPOINT_TITULOS = '/api/ura/titulos/'
    ENDPOINT_VERIFICAR_ACESSO = '/api/ura/verificaacesso/'
    ENDPOINT_FATURA_2VIA = '/api/ura/fatura2via/'
    ENDPOINT_DOCUMENTO_TPL = '/api/suporte/cliente/{cliente_id}/documento/add/'
    ENDPOINT_TERMO_ACEITE_TPL = '/api/contrato/termoaceite/{contrato_id}'

    def __init__(self, integracao: IntegracaoAPI):
        if integracao.tipo != 'sgp':
            raise SGPServiceError(
                f"Integração '{integracao.nome}' não é do tipo sgp (tipo={integracao.tipo})."
            )
        self.integracao = integracao
        self.base_url = (integracao.base_url or '').rstrip('/')

    # ------------------------------------------------------------------
    # Autenticação / validação
    # ------------------------------------------------------------------

    def validar_credenciais(self) -> bool:
        """
        Testa se as credenciais (app + token) da integração funcionam.

        Usa POST /api/precadastro/plano/list como ping barato: se retornar
        HTTP 200 com uma lista, as credenciais são válidas.

        Retorna True em sucesso. Lança SGPServiceError em falha.
        """
        resposta = self._post(self.ENDPOINT_VALIDAR, {})
        if not isinstance(resposta, list):
            raise SGPServiceError(
                f"Credenciais SGP inválidas ou endpoint inesperado. Resposta: {resposta}"
            )
        return True

    # ------------------------------------------------------------------
    # Catálogos — Planos
    # ------------------------------------------------------------------

    def listar_planos(self) -> list[dict]:
        """
        Lista todos os planos cadastrados no SGP do tenant.

        Retorna lista de dicts com shape:
            {'tipo': 'internet', 'id': 4, 'descricao': '...',
             'valor': 119.9, 'observacao': '', 'gateway': {...}}

        Levanta SGPServiceError em falha HTTP ou auth.
        """
        resposta = self._post(self.ENDPOINT_PLANOS, {})
        if not isinstance(resposta, list):
            raise SGPServiceError(
                f"Shape inesperado em {self.ENDPOINT_PLANOS}: {resposta}"
            )
        return resposta

    def sincronizar_planos(self, *, dry_run: bool = False) -> dict:
        """
        Puxa todos os planos do SGP e faz upsert em crm.ProdutoServico,
        respeitando multi-tenancy (integracao.tenant).

        Mapeamento:
            plano['id']         -> ProdutoServico.codigo e ProdutoServico.id_externo
            plano['descricao']  -> ProdutoServico.nome
            plano['valor']      -> ProdutoServico.preco (Decimal)
            plano['tipo']       -> dados_erp['tipo_sgp']
            plano['gateway']    -> dados_erp['gateway']
            plano['observacao'] -> dados_erp['observacao_sgp']
            (fixo)              -> categoria='plano', recorrencia='mensal'

        Se dry_run=True, não persiste; só calcula o que seria feito.

        Retorna dict com contagens: {'total', 'criados', 'atualizados', 'inalterados', 'dry_run'}.
        """
        # Import local pra evitar import circular no carregamento do app
        from apps.comercial.crm.models import ProdutoServico

        planos_sgp = self.listar_planos()
        tenant = self.integracao.tenant

        resumo = {
            'total': len(planos_sgp),
            'criados': 0,
            'atualizados': 0,
            'inalterados': 0,
            'dry_run': dry_run,
        }

        for plano in planos_sgp:
            id_sgp = plano.get('id')
            if id_sgp is None:
                logger.warning("Plano SGP sem 'id', ignorando: %s", plano)
                continue

            codigo = str(id_sgp)
            nome = plano.get('descricao') or f"Plano SGP {id_sgp}"

            # valor pode vir como float ou string numérica
            valor_raw = plano.get('valor')
            try:
                preco = Decimal(str(valor_raw)) if valor_raw is not None else Decimal('0')
            except (ValueError, ArithmeticError):
                logger.warning(
                    "Plano SGP id=%s com valor inválido (%r), usando 0.",
                    id_sgp, valor_raw,
                )
                preco = Decimal('0')

            dados_erp = {
                'origem_erp': 'sgp',
                'tipo_sgp': plano.get('tipo') or '',
                'gateway': plano.get('gateway') or {},
                'observacao_sgp': plano.get('observacao') or '',
            }

            defaults = {
                'nome': nome,
                'preco': preco,
                'categoria': 'plano',
                'recorrencia': 'mensal',
                'id_externo': codigo,
                'dados_erp': dados_erp,
            }

            if dry_run:
                # Apenas classifica o que seria feito, sem salvar
                existente = ProdutoServico.objects.filter(
                    tenant=tenant, codigo=codigo,
                ).first()
                if existente is None:
                    resumo['criados'] += 1
                elif self._produto_precisa_atualizar(existente, defaults):
                    resumo['atualizados'] += 1
                else:
                    resumo['inalterados'] += 1
                continue

            produto, criado = ProdutoServico.objects.update_or_create(
                tenant=tenant,
                codigo=codigo,
                defaults=defaults,
            )
            if criado:
                resumo['criados'] += 1
            else:
                # Heurística simples: se update_or_create tocou qualquer campo, contamos como atualizado.
                # Para distinguir "atualizado vs inalterado" com precisão teríamos que snapshot antes.
                # Aqui marcamos como atualizado qualquer registro pré-existente.
                resumo['atualizados'] += 1

        return resumo

    @staticmethod
    def _produto_precisa_atualizar(produto, defaults: dict) -> bool:
        """Compara os campos dos defaults com o produto existente. Usado em dry-run."""
        for campo, novo in defaults.items():
            atual = getattr(produto, campo, None)
            # dados_erp é JSONField (dict) — comparar por igualdade
            if atual != novo:
                return True
        return False

    # ------------------------------------------------------------------
    # Catálogos — Vencimentos
    # ------------------------------------------------------------------

    def listar_vencimentos(self) -> list[dict]:
        """
        Lista todas as opções de dia de vencimento cadastradas no SGP.

        Retorna lista de dicts com shape: {'id': 1, 'dia': 5}

        Levanta SGPServiceError em falha HTTP ou auth.
        """
        resposta = self._post(self.ENDPOINT_VENCIMENTOS, {})
        if not isinstance(resposta, list):
            raise SGPServiceError(
                f"Shape inesperado em {self.ENDPOINT_VENCIMENTOS}: {resposta}"
            )
        return resposta

    def sincronizar_vencimentos(self, *, dry_run: bool = False) -> dict:
        """
        Puxa todas as opções de vencimento do SGP e faz upsert em
        crm.OpcaoVencimentoCRM, respeitando multi-tenancy (integracao.tenant).

        Mapeamento:
            venc['id']  -> OpcaoVencimentoCRM.id_externo
            venc['dia'] -> OpcaoVencimentoCRM.dia (chave natural junto com tenant)
            (derivado)  -> ordem = dia (ordena naturalmente pelo dia)
            (fixo)      -> ativo=True, dados_erp={'origem_erp': 'sgp', 'id_sgp': N}

        Chave natural pra upsert: (tenant, dia).

        Se dry_run=True, não persiste.

        Retorna: {'total', 'criados', 'atualizados', 'inalterados', 'dry_run'}.
        """
        from apps.comercial.crm.models import OpcaoVencimentoCRM

        vencimentos_sgp = self.listar_vencimentos()
        tenant = self.integracao.tenant

        resumo = {
            'total': len(vencimentos_sgp),
            'criados': 0,
            'atualizados': 0,
            'inalterados': 0,
            'dry_run': dry_run,
        }

        for venc in vencimentos_sgp:
            id_sgp = venc.get('id')
            dia = venc.get('dia')
            if id_sgp is None or dia is None:
                logger.warning("Vencimento SGP incompleto, ignorando: %s", venc)
                continue

            try:
                dia_int = int(dia)
            except (ValueError, TypeError):
                logger.warning("Vencimento SGP com 'dia' invalido (%r), ignorando.", dia)
                continue

            defaults = {
                'id_externo': str(id_sgp),
                'ordem': dia_int,
                'ativo': True,
                'dados_erp': {
                    'origem_erp': 'sgp',
                    'id_sgp': id_sgp,
                },
            }

            if dry_run:
                existente = OpcaoVencimentoCRM.objects.filter(
                    tenant=tenant, dia=dia_int,
                ).first()
                if existente is None:
                    resumo['criados'] += 1
                elif self._vencimento_precisa_atualizar(existente, defaults):
                    resumo['atualizados'] += 1
                else:
                    resumo['inalterados'] += 1
                continue

            _, criado = OpcaoVencimentoCRM.objects.update_or_create(
                tenant=tenant,
                dia=dia_int,
                defaults=defaults,
            )
            if criado:
                resumo['criados'] += 1
            else:
                resumo['atualizados'] += 1

        return resumo

    @staticmethod
    def _vencimento_precisa_atualizar(venc, defaults: dict) -> bool:
        """Compara campos de OpcaoVencimentoCRM existente com defaults (uso em dry-run)."""
        for campo, novo in defaults.items():
            atual = getattr(venc, campo, None)
            if atual != novo:
                return True
        return False

    # ------------------------------------------------------------------
    # Catálogos de referência — vendedores, POPs, portadores
    # Persistem em IntegracaoAPI.configuracoes_extras['cache'][<nome>]
    # ------------------------------------------------------------------

    def sincronizar_vendedores(self, *, dry_run: bool = False) -> dict:
        """Puxa vendedores do SGP e cacheia em configuracoes_extras['cache']['vendedores']."""
        itens = self._listar_generico(self.ENDPOINT_VENDEDORES)
        return self._persistir_cache('vendedores', itens, dry_run=dry_run)

    def sincronizar_pops(self, *, dry_run: bool = False) -> dict:
        """Puxa POPs do SGP e cacheia em configuracoes_extras['cache']['pops']."""
        itens = self._listar_generico(self.ENDPOINT_POPS)
        return self._persistir_cache('pops', itens, dry_run=dry_run)

    def sincronizar_portadores(self, *, dry_run: bool = False) -> dict:
        """
        Puxa portadores financeiros do SGP e cacheia em configuracoes_extras['cache']['portadores'].

        Atenção: este endpoint só aceita GET (diferente dos outros catálogos).
        """
        itens = self._listar_generico(self.ENDPOINT_PORTADORES, method='GET')
        return self._persistir_cache('portadores', itens, dry_run=dry_run)

    # ------------------------------------------------------------------
    # Consulta de cliente (por CPF/CNPJ)
    # ------------------------------------------------------------------

    def sincronizar_cliente(self, lead, *, cpf_cnpj: str = None):
        """
        Consulta o SGP pelo CPF/CNPJ do lead (ou explicito) e cria/atualiza
        ClienteSGP local.

        Shape do SGP: `{contratos: [...]}`. Cada contrato carrega os dados
        do cliente embutidos em camelCase (clienteId, cpfCnpj, razaoSocial,
        telefones, emails, endereco_*). Mesmo cliente aparece N vezes (1 por
        contrato) — extraimos do primeiro e salvamos a lista de contratos.

        Returns: ClienteSGP ou None se cliente nao encontrado / sem contratos.
        """
        from apps.integracoes.models import ClienteSGP

        cpf = cpf_cnpj or getattr(lead, 'cpf_cnpj', None)
        if not cpf:
            logger.warning('sincronizar_cliente: lead pk=%s sem CPF/CNPJ.', getattr(lead, 'pk', '?'))
            return None

        try:
            resposta = self.consultar_cliente(cpf, lead=lead)
        except SGPServiceError as exc:
            logger.error('sincronizar_cliente: erro consultando %s: %s', cpf, exc)
            return None

        contratos = resposta.get('contratos') or []
        if not contratos:
            logger.warning(
                'sincronizar_cliente: SGP retornou sem contratos pra cpf=%s. '
                'Provavelmente eh prospecto/pre-cadastro (sem contrato ativo).',
                cpf,
            )
            return None

        # Pega cliente do primeiro contrato (todos tem o mesmo cliente)
        primeiro = contratos[0]
        id_cliente_sgp = primeiro.get('clienteId')
        if not id_cliente_sgp:
            logger.warning(
                'sincronizar_cliente: contrato sem clienteId. cpf=%s primeiro=%s',
                cpf, str(primeiro)[:300],
            )
            return None

        # Telefones e emails vem como lista — pega o primeiro
        telefones = primeiro.get('telefones') or []
        emails = primeiro.get('emails') or []
        # Status do cliente: ativo se TEM algum contrato ativo (Status=1)
        ativo = any(c.get('contratoStatus') == 1 for c in contratos)

        defaults = {
            'tenant': self.integracao.tenant,
            'lead': lead,
            'nome': (primeiro.get('razaoSocial') or primeiro.get('nome') or '')[:300],
            'cpf_cnpj': self._somente_numeros(primeiro.get('cpfCnpj') or cpf),
            'email': (emails[0] if emails else '')[:254],
            'telefone': (telefones[0] if telefones else '')[:30],
            'cep': self._somente_numeros(primeiro.get('endereco_cep') or '')[:10],
            'logradouro': (primeiro.get('endereco_logradouro') or '')[:255],
            'numero': str(primeiro.get('endereco_numero') or '')[:20],
            'bairro': (primeiro.get('endereco_bairro') or '')[:120],
            'cidade': (primeiro.get('endereco_cidade') or '')[:100],
            'uf': (primeiro.get('endereco_uf') or '')[:2],
            'ativo': ativo,
            'contratos': contratos,
            'dados_completos': resposta,
        }

        cliente, criado = ClienteSGP.objects.update_or_create(
            integracao=self.integracao,
            id_cliente_sgp=int(id_cliente_sgp),
            defaults=defaults,
        )
        if criado:
            logger.info('ClienteSGP criado: pk=%s id_sgp=%s nome=%s', cliente.pk, id_cliente_sgp, cliente.nome)
        else:
            logger.info('ClienteSGP atualizado: pk=%s id_sgp=%s nome=%s', cliente.pk, id_cliente_sgp, cliente.nome)
        return cliente

    def consultar_cliente(self, cpf_cnpj: str, lead=None) -> dict:
        """
        Consulta um cliente no SGP por CPF/CNPJ.

        Usa POST /api/ura/consultacliente/ com cpfcnpj no formdata.
        Retorna o dict cru da resposta (que inclui dados pessoais, contratos
        e servicos). Lanca SGPServiceError em falha HTTP.
        """
        cpf_limpo = self._somente_numeros(cpf_cnpj)
        if not cpf_limpo:
            raise SGPServiceError('consultar_cliente: cpf_cnpj vazio ou invalido.')

        resposta = self._post(
            self.ENDPOINT_CONSULTA_CLIENTE,
            {'cpfcnpj': cpf_limpo},
            lead=lead,
        )
        if not isinstance(resposta, dict):
            raise SGPServiceError(
                f"Shape inesperado em {self.ENDPOINT_CONSULTA_CLIENTE}: {resposta}"
            )
        return resposta

    @staticmethod
    def _somente_numeros(valor: str) -> str:
        return ''.join(c for c in (valor or '') if c.isdigit())

    # ------------------------------------------------------------------
    # Titulos / faturas (situacao financeira do cliente)
    # ------------------------------------------------------------------

    def listar_titulos(
        self,
        cpf_cnpj: str = None,
        *,
        cliente_id: int = None,
        contrato_id: int = None,
        status: str = None,
        data_vencimento_inicio: str = None,
        data_vencimento_fim: str = None,
        data_pagamento_inicio: str = None,
        data_pagamento_fim: str = None,
        lead=None,
    ) -> list:
        """
        Lista titulos (faturas) do cliente no SGP.

        Identificacao do cliente: passar `cpf_cnpj` OU `cliente_id` (id_sgp).
        Pelo menos um eh obrigatorio.

        Filtros opcionais:
          - status: 'abertos' | 'pagos' | 'cancelados'
          - data_vencimento_inicio/fim: 'YYYY-MM-DD'
          - data_pagamento_inicio/fim: 'YYYY-MM-DD'
          - contrato_id: filtra por contrato especifico

        Retorna lista de titulos com valor, vencimento, data_pagamento,
        codigo_barras, pix, etc. Lanca SGPServiceError em falha HTTP.
        """
        if not cpf_cnpj and not cliente_id:
            raise SGPServiceError(
                'listar_titulos: informe cpf_cnpj OU cliente_id.'
            )

        payload = {}
        if cpf_cnpj:
            payload['cpfcnpj'] = self._somente_numeros(cpf_cnpj)
        if cliente_id:
            payload['cliente'] = int(cliente_id)
        if contrato_id:
            payload['contrato'] = int(contrato_id)
        if status:
            payload['status'] = status
        if data_vencimento_inicio:
            payload['data_vencimento_inicio'] = data_vencimento_inicio
        if data_vencimento_fim:
            payload['data_vencimento_fim'] = data_vencimento_fim
        if data_pagamento_inicio:
            payload['data_pagamento_inicio'] = data_pagamento_inicio
        if data_pagamento_fim:
            payload['data_pagamento_fim'] = data_pagamento_fim

        resposta = self._post(self.ENDPOINT_TITULOS, payload, lead=lead)

        # SGP costuma retornar lista direto OU dict {titulos: [...]}
        if isinstance(resposta, list):
            return resposta
        if isinstance(resposta, dict):
            return resposta.get('titulos') or resposta.get('list') or []
        raise SGPServiceError(
            f"Shape inesperado em {self.ENDPOINT_TITULOS}: {resposta}"
        )

    # ------------------------------------------------------------------
    # Operacional (acesso/conexao, 2via, documentos, contrato)
    # ------------------------------------------------------------------

    def verificar_acesso(self, *, cliente_id: int = None, contrato_id: int = None,
                         cpf_cnpj: str = None, lead=None) -> dict:
        """
        Consulta status de conexao do cliente (online/offline, sinal, etc).

        Aceita cliente_id, contrato_id ou cpf_cnpj — pelo menos um.
        Retorna dict cru da resposta (status, ultima_atividade, etc).
        """
        if not any([cliente_id, contrato_id, cpf_cnpj]):
            raise SGPServiceError(
                'verificar_acesso: informe cliente_id, contrato_id ou cpf_cnpj.'
            )
        payload = {}
        if cliente_id:
            payload['cliente'] = int(cliente_id)
        if contrato_id:
            payload['contrato'] = int(contrato_id)
        if cpf_cnpj:
            payload['cpfcnpj'] = self._somente_numeros(cpf_cnpj)
        resposta = self._post(self.ENDPOINT_VERIFICAR_ACESSO, payload, lead=lead)
        if not isinstance(resposta, (dict, list)):
            raise SGPServiceError(
                f"Shape inesperado em {self.ENDPOINT_VERIFICAR_ACESSO}: {resposta}"
            )
        return resposta

    def gerar_2via_fatura(self, titulo_id: int, *, lead=None) -> dict:
        """
        Gera 2a via de uma fatura especifica. Retorna dict com link/PDF/PIX
        atualizados.
        """
        if not titulo_id:
            raise SGPServiceError('gerar_2via_fatura: titulo_id obrigatorio.')
        payload = {'titulo': int(titulo_id)}
        resposta = self._post(self.ENDPOINT_FATURA_2VIA, payload, lead=lead)
        if not isinstance(resposta, dict):
            raise SGPServiceError(
                f"Shape inesperado em {self.ENDPOINT_FATURA_2VIA}: {resposta}"
            )
        return resposta

    def anexar_documento(self, cliente_id: int, file_obj, *,
                         nome_arquivo: str = None, descricao: str = '',
                         lead=None) -> dict:
        """
        Anexa documento ao cliente no SGP via PUT multipart.

        Args:
            cliente_id: id do cliente no SGP
            file_obj: file-like object (open('foo.pdf', 'rb')) ou bytes
            nome_arquivo: nome opcional (default: file_obj.name)
            descricao: descricao opcional do documento

        Retorna dict com id do documento criado / status.
        """
        if not cliente_id:
            raise SGPServiceError('anexar_documento: cliente_id obrigatorio.')
        endpoint = self.ENDPOINT_DOCUMENTO_TPL.format(cliente_id=int(cliente_id))
        nome = nome_arquivo or getattr(file_obj, 'name', 'arquivo.bin')
        files = {'file': (nome, file_obj)}
        payload = {}
        if descricao:
            payload['descricao'] = descricao
        resposta = self._put(endpoint, payload, files=files, lead=lead)
        if not isinstance(resposta, dict):
            raise SGPServiceError(
                f"Shape inesperado em {endpoint}: {resposta}"
            )
        return resposta

    def aceitar_contrato(self, contrato_id: int, *, lead=None) -> dict:
        """
        Aceita o termo de um contrato. Body: aceite=sim. Usado apos
        cliente revisar o termo e confirmar aceite digital.
        """
        if not contrato_id:
            raise SGPServiceError('aceitar_contrato: contrato_id obrigatorio.')
        endpoint = self.ENDPOINT_TERMO_ACEITE_TPL.format(contrato_id=int(contrato_id))
        resposta = self._post(endpoint, {'aceite': 'sim'}, lead=lead)
        if not isinstance(resposta, dict):
            raise SGPServiceError(
                f"Shape inesperado em {endpoint}: {resposta}"
            )
        return resposta

    # ------------------------------------------------------------------
    # Cadastro de prospecto (pessoa fisica)
    # ------------------------------------------------------------------

    def cadastrar_prospecto_pf(
        self,
        *,
        nome: str,
        cpf: str,
        email: str,
        telefone_celular: str,
        cep: str,
        logradouro: str,
        numero: str,
        bairro: str,
        cidade: str,
        uf: str,
        plano_id: int,
        vendedor_id: int,
        pop_id: int,
        portador_id: int,
        dia_vencimento: int,
        forma_cobranca: int,
        precadastro_ativar: int = 0,
        complemento: str = '',
        rg: str = '',
        data_nascimento: str = '',
        lead=None,
    ) -> dict:
        """
        Cria prospecto PF no SGP via POST /api/precadastro/F.

        precadastro_ativar=0 -> apenas pre-cadastro (nao cria contrato/boleto)
        precadastro_ativar=1 -> cria cliente efetivo + contrato + servicos

        Forma cobranca: codigos SGP (1=Dinheiro, 4=Cartao Credito, 6=PIX, etc).

        Retorna o dict cru da resposta. Lanca SGPServiceError em falha HTTP.
        """
        payload = {
            'nome': nome.strip(),
            'cpfcnpj': self._somente_numeros(cpf),
            'email': email.strip(),
            'telefone_celular': self._somente_numeros(telefone_celular),
            'cep': self._somente_numeros(cep),
            'logradouro': logradouro.strip(),
            'numero': str(numero).strip(),
            'bairro': bairro.strip(),
            'cidade': cidade.strip(),
            'uf': uf.strip().upper(),
            'plano': int(plano_id),
            'vendedor': int(vendedor_id),
            'pop': int(pop_id),
            'portador': int(portador_id),
            'dia_vencimento': int(dia_vencimento),
            'forma_cobranca': int(forma_cobranca),
            'precadastro_ativar': int(precadastro_ativar),
        }
        if complemento:
            payload['complemento'] = complemento.strip()
        if rg:
            payload['rg'] = rg.strip()
        if data_nascimento:
            payload['data_nascimento'] = data_nascimento.strip()

        return self._post(self.ENDPOINT_PRECADASTRO_PF, payload, lead=lead)

    def cadastrar_prospecto_para_lead(self, lead) -> dict:
        """
        Cadastra prospecto a partir de um LeadProspecto. Usa defaults do
        IntegracaoAPI.configuracoes_extras pra plano/vendedor/pop/portador
        /forma_cobranca/dia_vencimento. Levanta SGPServiceError se algum
        default obrigatorio nao estiver configurado.
        """
        extras = self.integracao.configuracoes_extras or {}
        required = ('plano_id_padrao', 'vendedor_id_padrao', 'pop_id_padrao',
                    'portador_id_padrao', 'forma_cobranca_id_padrao', 'dia_vencimento_padrao')
        faltando = [k for k in required if not extras.get(k)]
        if faltando:
            raise SGPServiceError(
                f'cadastrar_prospecto_para_lead: defaults faltando em '
                f'IntegracaoAPI.configuracoes_extras: {faltando}'
            )
        if not lead.cpf_cnpj:
            raise SGPServiceError('cadastrar_prospecto_para_lead: lead sem CPF/CNPJ.')

        return self.cadastrar_prospecto_pf(
            nome=lead.nome_razaosocial,
            cpf=lead.cpf_cnpj,
            email=lead.email or '',
            telefone_celular=lead.telefone or '',
            cep=lead.cep or '',
            logradouro=lead.rua or '',
            numero=lead.numero_residencia or 'S/N',
            bairro=lead.bairro or '',
            cidade=lead.cidade or '',
            uf=lead.estado or '',
            plano_id=extras['plano_id_padrao'],
            vendedor_id=extras['vendedor_id_padrao'],
            pop_id=extras['pop_id_padrao'],
            portador_id=extras['portador_id_padrao'],
            dia_vencimento=extras['dia_vencimento_padrao'],
            forma_cobranca=extras['forma_cobranca_id_padrao'],
            precadastro_ativar=int(extras.get('precadastro_ativar_padrao', 0)),
            lead=lead,
        )

    # --- Helpers privados pros catálogos de cache ---

    def _listar_generico(self, endpoint: str, method: str = 'POST') -> list[dict]:
        """
        Chamada autenticada + validação de shape de lista. Retorna lista de dicts.

        Suporta GET e POST porque o SGP é inconsistente entre endpoints de listagem:
        a maioria é POST formdata, mas alguns (ex: /api/ura/portador/) só aceitam GET.
        """
        if method.upper() == 'GET':
            resposta = self._get(endpoint)
        else:
            resposta = self._post(endpoint, {})
        if not isinstance(resposta, list):
            raise SGPServiceError(f"Shape inesperado em {endpoint}: {resposta}")
        return resposta

    def _persistir_cache(self, chave: str, itens: list, *, dry_run: bool) -> dict:
        """
        Guarda `itens` em integracao.configuracoes_extras['cache'][<chave>].

        Retorna resumo com total/criados/atualizados/inalterados relativo ao cache anterior.
        Semântica:
          - criados    = ids novos que não estavam no cache
          - atualizados= ids existentes cujo dict mudou
          - inalterados= ids existentes cujo dict é igual
        """
        extras = dict(self.integracao.configuracoes_extras or {})
        cache = dict(extras.get('cache') or {})
        anterior = {self._chave_item(i): i for i in (cache.get(chave) or [])}
        novo_list = list(itens)
        atual = {self._chave_item(i): i for i in novo_list}

        criados = sum(1 for k in atual if k not in anterior)
        atualizados = sum(
            1 for k, v in atual.items()
            if k in anterior and anterior[k] != v
        )
        inalterados = sum(
            1 for k, v in atual.items()
            if k in anterior and anterior[k] == v
        )

        resumo = {
            'total': len(novo_list),
            'criados': criados,
            'atualizados': atualizados,
            'inalterados': inalterados,
            'dry_run': dry_run,
        }

        if dry_run:
            return resumo

        cache[chave] = novo_list
        extras['cache'] = cache

        # Atualiza só o JSONField, sem disparar save() completo
        type(self.integracao).objects.filter(pk=self.integracao.pk).update(
            configuracoes_extras=extras,
        )
        # Reflete no objeto em memória pra consultas subsequentes no mesmo processo
        self.integracao.configuracoes_extras = extras

        return resumo

    @staticmethod
    def _chave_item(item: dict) -> str:
        """Identifica um item do SGP pelo 'id' (padrão). Fallback pra repr."""
        if isinstance(item, dict) and 'id' in item:
            return f"id:{item['id']}"
        return repr(item)

    # ------------------------------------------------------------------
    # Wrapper de POST com auth + log
    # ------------------------------------------------------------------

    def _get(self, endpoint: str, params: dict = None, lead=None) -> dict | list:
        """
        GET autenticado com app+token via query string. Registra LogIntegracao
        e levanta SGPServiceError em falha HTTP ou rede.

        Alguns endpoints do SGP só aceitam GET (ex: /api/ura/portador/).
        """
        url = f"{self.base_url}{endpoint}"
        query = {
            'app': self.integracao.client_id,
            'token': self.integracao.access_token,
        }
        if params:
            query.update(params)

        inicio = time.time()
        try:
            resp = requests.get(url, params=query, timeout=30)
            tempo_ms = int((time.time() - inicio) * 1000)
        except requests.RequestException as exc:
            tempo_ms = int((time.time() - inicio) * 1000)
            self._registrar_log(
                endpoint=endpoint, metodo='GET',
                payload=self._payload_seguro(query), resposta={},
                status_code=0, sucesso=False, erro=str(exc),
                tempo_ms=tempo_ms, lead=lead,
            )
            raise SGPServiceError(f"Falha de conexão com SGP: {exc}") from exc

        try:
            resposta_json = resp.json()
        except ValueError:
            resposta_json = {'raw': resp.text[:2000]}

        sucesso = resp.status_code == 200
        resposta_para_log = (
            resposta_json if isinstance(resposta_json, dict)
            else {'list': resposta_json}
        )

        self._registrar_log(
            endpoint=endpoint, metodo='GET',
            payload=self._payload_seguro(query),
            resposta=resposta_para_log,
            status_code=resp.status_code,
            sucesso=sucesso,
            erro='' if sucesso else f"HTTP {resp.status_code}",
            tempo_ms=tempo_ms, lead=lead,
        )

        if not sucesso:
            raise SGPServiceError(
                f"Erro SGP em {endpoint} (HTTP {resp.status_code}): {resposta_json}"
            )

        return resposta_json

    def _post(self, endpoint: str, payload: dict = None, files: dict = None,
              lead=None) -> dict | list:
        """POST autenticado com app+token via formdata."""
        return self._request('POST', endpoint, payload=payload, files=files, lead=lead)

    def _put(self, endpoint: str, payload: dict = None, files: dict = None,
             lead=None) -> dict | list:
        """PUT autenticado com app+token via formdata. Usado por anexar_documento."""
        return self._request('PUT', endpoint, payload=payload, files=files, lead=lead)

    def _request(self, metodo: str, endpoint: str, payload: dict = None,
                 files: dict = None, lead=None) -> dict | list:
        """
        Helper generico HTTP autenticado com app+token via formdata.
        Registra LogIntegracao e levanta SGPServiceError em falha.
        """
        url = f"{self.base_url}{endpoint}"
        data = {
            'app': self.integracao.client_id,
            'token': self.integracao.access_token,
        }
        if payload:
            data.update(payload)

        inicio = time.time()
        try:
            resp = requests.request(metodo, url, data=data, files=files, timeout=30)
            tempo_ms = int((time.time() - inicio) * 1000)
        except requests.RequestException as exc:
            tempo_ms = int((time.time() - inicio) * 1000)
            self._registrar_log(
                endpoint=endpoint, metodo=metodo,
                payload=self._payload_seguro(data), resposta={},
                status_code=0, sucesso=False, erro=str(exc),
                tempo_ms=tempo_ms, lead=lead,
            )
            raise SGPServiceError(f"Falha de conexão com SGP: {exc}") from exc

        try:
            resposta_json = resp.json()
        except ValueError:
            resposta_json = {'raw': resp.text[:2000]}

        sucesso = resp.status_code in (200, 201)
        resposta_para_log = (
            resposta_json if isinstance(resposta_json, dict)
            else {'list': resposta_json}
        )

        self._registrar_log(
            endpoint=endpoint, metodo=metodo,
            payload=self._payload_seguro(data),
            resposta=resposta_para_log,
            status_code=resp.status_code,
            sucesso=sucesso,
            erro='' if sucesso else f"HTTP {resp.status_code}",
            tempo_ms=tempo_ms, lead=lead,
        )

        if not sucesso:
            raise SGPServiceError(
                f"Erro SGP em {endpoint} (HTTP {resp.status_code}): {resposta_json}"
            )

        return resposta_json

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _payload_seguro(data: dict) -> dict:
        """Mascara o token no payload logado para não vazar segredo em auditoria."""
        return {
            k: (v if k != 'token' else '***REDACTED***')
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
            logger.error("Erro ao registrar log de integração SGP: %s", exc)
