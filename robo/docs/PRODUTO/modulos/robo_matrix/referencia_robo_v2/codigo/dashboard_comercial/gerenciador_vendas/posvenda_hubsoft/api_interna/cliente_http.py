"""Cliente HTTP para HubSoft Megalink.
Faz login via Selenium (cookies), depois usa requests.Session() pra
todos os endpoints internos. Cadastra cliente + habilita serviço + ajusta
PPPoE em ~10s por cliente.
"""
import json
import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from selenium.webdriver.support.ui import WebDriverWait

# imports do webdriver irmão — relativo no pacote (Django), absoluto como script
try:
    from ..webdriver.main_novo_servico import configurar_driver, TIMEOUT_PADRAO  # noqa: E402
    from ..webdriver.main_adicionar_cliente import (  # noqa: E402
        fazer_login, esperar_dashboard, MEGALINK_URL_BASE)
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'webdriver'))
    from main_novo_servico import configurar_driver, TIMEOUT_PADRAO  # noqa: E402
    from main_adicionar_cliente import (  # noqa: E402
        fazer_login, esperar_dashboard, MEGALINK_URL_BASE)

load_dotenv()
log = logging.getLogger("http_megalink")

BASE = MEGALINK_URL_BASE  # https://megalinktelecom.hubsoft.com.br (painel)
API_BASE = os.environ.get('MEGALINK_API_BASE',
                          'https://api.megalinktelecom.hubsoft.com.br')


class ClienteHTTP:
    """Wrapper de sessão HTTP autenticada via Selenium cookies."""

    def __init__(self, headless: bool = True):
        self.session = requests.Session()
        self._driver = None
        self._tmp = None
        self.headless = headless

    def login(self):
        """Login no painel via Selenium e captura cookies + token Bearer."""
        usuario = os.environ['USUARIO']
        senha = os.environ['SENHA']
        log.info("Login Selenium para capturar token...")
        self._driver, self._tmp = configurar_driver(self.headless)
        wait = WebDriverWait(self._driver, TIMEOUT_PADRAO)
        fazer_login(self._driver, wait, usuario, senha)
        if not esperar_dashboard(self._driver):
            raise RuntimeError("Login Selenium falhou")
        # Captura cookies
        for c in self._driver.get_cookies():
            self.session.cookies.set(c['name'], c['value'], domain=c.get('domain'))
        log.info(f"✓ {len(self.session.cookies)} cookies")

        # Captura token Angular (localStorage/sessionStorage)
        token = self._driver.execute_script(
            "var ks = Object.keys(localStorage).concat(Object.keys(sessionStorage));"
            "var out = {};"
            "Object.keys(localStorage).forEach(k => out['local_'+k] = localStorage[k]);"
            "Object.keys(sessionStorage).forEach(k => out['session_'+k] = sessionStorage[k]);"
            "return out;"
        )
        log.info(f"  storage keys: {list(token.keys())}")
        bearer = None
        for k, v in token.items():
            # Procura token tipo JWT (3 partes separadas por .)
            if isinstance(v, str) and v.count('.') == 2 and len(v) > 100:
                bearer = v
                log.info(f"  ✓ Bearer encontrado em {k}: {v[:30]}...")
                break
            # Ou objeto JSON com 'token'/'access_token'
            try:
                obj = json.loads(v) if isinstance(v, str) and v.startswith('{') else None
                if obj and isinstance(obj, dict):
                    for tk in ('token','access_token','accessToken','jwt'):
                        if tk in obj and isinstance(obj[tk], str) and len(obj[tk]) > 50:
                            bearer = obj[tk]
                            log.info(f"  ✓ Bearer em {k}.{tk}: {bearer[:30]}...")
                            break
                if bearer: break
            except Exception:
                pass

        self.session.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json;charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': BASE,
            'Referer': f'{BASE}/cliente/adicionar/',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        })
        if bearer:
            self.session.headers['Authorization'] = f'Bearer {bearer}'
            log.info("  ✓ Authorization: Bearer setado")
        else:
            log.warning("  ⚠ Nenhum Bearer token detectado no storage")

    def close(self):
        try:
            if self._driver: self._driver.quit()
        except Exception: pass
        try:
            if self._tmp:
                import shutil; shutil.rmtree(self._tmp)
        except Exception: pass

    # ============ Endpoints ============

    def _post(self, path: str, json_body):
        url = f"{API_BASE}{path}"
        r = self.session.post(url, json=json_body, timeout=30)
        return r

    def _put(self, path: str, json_body):
        url = f"{API_BASE}{path}"
        r = self.session.put(url, json=json_body, timeout=30)
        return r

    def _get(self, path: str, params=None):
        url = f"{API_BASE}{path}"
        r = self.session.get(url, params=params, timeout=30)
        return r

    # 1) Carrega schema/listas iniciais do form (grupos, vendedores, etc.)
    def get_cliente_create(self) -> dict:
        r = self._get('/api/v1/cliente/create')
        log.info(f"  GET /cliente/create → {r.status_code} ct={r.headers.get('content-type')} len={len(r.content)}")
        if r.status_code != 200:
            log.error(f"  body[:300]: {r.text[:300]}")
        r.raise_for_status()
        return r.json()

    # 2) Pré-check CPF
    def cpf_ja_cadastrado(self, cpf: str) -> bool:
        cpf_d = ''.join(c for c in cpf if c.isdigit())
        r = self._post(
            '/api/v1/cliente/consulta_adicionar_cliente/cpf_cnpj',
            {'consulta': cpf_d, 'status': 'todos', 'tipo': 'cpf_cnpj'},
        )
        if not r.ok: return False
        j = r.json()
        clientes = j.get('clientes', [])
        return len(clientes) > 0

    # 3) Resolve endereço completo
    def buscar_cep(self, cep: str) -> dict:
        cep_d = ''.join(c for c in cep if c.isdigit())
        r = self._post('/api/v1/endereco/cep/buscar',
                       {'cep': cep_d, 'tipo_busca': 'cep'})
        r.raise_for_status()
        return r.json().get('cep', {})

    def resolver_endereco_numero(self, cep: str, cidade_obj: dict,
                                  bairro: str, endereco: str, numero: str,
                                  complemento: str = '') -> dict:
        """Cria/resolve endereco_numero. Retorna dict com id_endereco_numero."""
        body = {
            'cep': ''.join(c for c in cep if c.isdigit()),
            'cidade': cidade_obj,
            'endereco': endereco,
            'numero': str(numero),
            'bairro': bairro,
            'condominio': None,
            'complemento': complemento or None,
            'ignorar_id_endereco_numero': None,
        }
        r = self._post('/api/v1/endereco/endereco_numero/numero', body)
        if not r.ok:
            log.error(f"  endereco_numero falhou: {r.status_code} {r.text[:300]}")
            r.raise_for_status()
        return r.json()

    # 4) CRIAR CLIENTE — POST /api/v1/cliente
    def criar_cliente(self, payload: dict) -> dict:
        r = self._post('/api/v1/cliente', payload)
        log.info(f"  POST /api/v1/cliente → {r.status_code}")
        if not r.ok:
            log.error(f"  body: {r.text[:600]}")
            r.raise_for_status()
        j = r.json()
        if j.get('status') != 'success':
            log.error(f"  resp error: {j}")
            raise RuntimeError(j.get('msg', 'falha no criar_cliente'))
        return j

    # 5) Habilitar serviço — fluxo descoberto do painel
    def habilitar_servico(self, id_cliente: int, id_cs: int):
        # Pré: registra "acesso" + lista serviços (replica navegação do painel)
        self._post('/api/v1/cliente/acesso', {
            'acessos': [{
                'id_cliente': str(id_cliente),
                'state': 'app.cliente.editar.servico',
                'acesso': 'SERVIÇO',
                'data_cadastro': time.strftime('%Y-%m-%d %H:%M:%S'),
            }]
        })
        self._post(
            f'/api/v1/cliente/servico/{id_cliente}/buscar/paginado/5',
            {
                'status': ['aguardando_migracao','servico_habilitado',
                          'suspenso_debito','suspenso_parcialmente'],
                'cancelado': False,
                'filtros': [],
                'id_revenda': None,
            },
        )
        # ESSENCIAL: status_conexao "seleciona" o serviço no contexto
        self._post('/api/v1/cliente/servico/status_conexao', {'ids': [id_cs]})
        time.sleep(0.5)
        # Endpoint sem id_cs — usa serviço selecionado por status_conexao
        r = self._post('/api/v1/cliente/servico/habilitar', {
            'motivo_habilitacao': None,
            'migrar_atendimentos': True,
            'id_cliente_servico': id_cs,  # talvez ele aceite no body
        })
        if not r.ok:
            log.error(f"  habilitar({id_cs}) falhou: {r.status_code} {r.text[:300]}")
            r.raise_for_status()
        return r.json()

    # 6) Atualiza id_vencimento do serviço (POST /cliente sempre cria com
    # dia 10 — precisa PUT depois pra setar o dia correto).
    def atualizar_vencimento(self, id_cliente: int, id_cs: int, id_vencimento: int):
        # Pega o objeto cs completo via buscar/paginado
        r = self._post(
            f'/api/v1/cliente/servico/{id_cliente}/buscar/paginado/5',
            {'status': ['aguardando_migracao','servico_habilitado',
                       'suspenso_debito','suspenso_parcialmente'],
             'cancelado': False, 'filtros': [], 'id_revenda': None},
        )
        j = r.json() if r.ok else {}
        cli_obj = j.get('cliente', {})
        servs_pag = cli_obj.get('servicos', {})
        data = servs_pag.get('data', []) if isinstance(servs_pag, dict) else []
        cs_obj = next((s for s in data if isinstance(s, dict)
                        and s.get('id_cliente_servico') == id_cs), None)
        if not cs_obj:
            raise RuntimeError(f"serviço {id_cs} não achado em paginado")
        cs_obj['id_vencimento'] = id_vencimento
        r2 = self._put(f'/api/v1/cliente/servico/{id_cs}', cs_obj)
        if not r2.ok:
            raise RuntimeError(f"PUT serviço falhou: {r2.status_code} {r2.text[:200]}")
        return r2.json()

    # 7) Atualiza login/senha PPPoE — usa GET pra pegar objeto completo
    def atualizar_pppoe(self, id_auth: int, id_cs: int, login: str, senha: str):
        # GET pega objeto completo (com equipamento_conexao, etc.)
        r_get = self._get(f'/api/v1/cliente/servico/autenticacao/{id_auth}')
        if not r_get.ok:
            r_get.raise_for_status()
        obj = r_get.json().get('cliente_servico_autenticacao')
        if not obj:
            raise RuntimeError(f"GET /autenticacao/{id_auth} sem objeto na resposta")
        # Modifica só login e password
        obj['login'] = login
        obj['password'] = senha
        # PUT com objeto completo
        r = self._put(f'/api/v1/cliente/servico/autenticacao/{id_auth}', obj)
        if not r.ok:
            log.error(f"  atualizar_pppoe falhou: {r.status_code} {r.text[:300]}")
            r.raise_for_status()
        return r.json()

    # 8) ADICIONAR SERVIÇO a cliente existente — POST /api/v1/cliente/servico
    def adicionar_servico(self, payload: dict) -> dict:
        """POST /api/v1/cliente/servico. Cria um novo serviço para um cliente
        já existente. Retorna o JSON com cliente_servico.id_cliente_servico e
        cliente_servico_autenticacao."""
        r = self._post('/api/v1/cliente/servico', payload)
        log.info(f"  POST /api/v1/cliente/servico → {r.status_code}")
        if not r.ok:
            log.error(f"  body: {r.text[:600]}")
            r.raise_for_status()
        j = r.json()
        if j.get('status') != 'success':
            log.error(f"  resp error: {j}")
            raise RuntimeError(j.get('msg', 'falha no adicionar_servico'))
        return j

    # 8b) UPGRADE / MIGRAR PARA OUTRO SERVIÇO — mesmo POST /cliente/servico, mas
    #     com o objeto do serviço ANTIGO + troca de plano + flags de migração.
    #     Estrutura descoberta via captura CDP (hubsoft_capturar_migracao).
    def obter_servico_edit(self, id_cliente_servico: int) -> dict:
        """GET /cliente/servico/{id}/edit → objeto completo do serviço (cliente_servico)."""
        r = self._get(f'/api/v1/cliente/servico/{id_cliente_servico}/edit')
        r.raise_for_status()
        return (r.json() or {}).get('cliente_servico') or {}

    def montar_payload_migracao(self, obj_antigo: dict, id_servico_novo: int) -> dict:
        """Monta o payload de migração a partir do objeto do serviço antigo.

        O /edit retorna os IDs (id_forma_cobranca, id_vencimento) mas os objetos
        aninhados (forma_cobranca, vencimento, grupos, vendedor) vêm nulos — a API
        exige os objetos completos, então preenchemos do schema/defaults."""
        import copy
        p = copy.deepcopy(obj_antigo)
        novo = self.buscar_plano_por_id(id_servico_novo)
        p['servico'] = novo
        p['valor'] = float(novo.get('valor') or p.get('valor') or 0)
        p['id_cliente_servico_antigo'] = obj_antigo.get('id_cliente_servico')
        p['id_cliente_servico'] = None
        p['id_servico'] = None
        p['origem'] = 'novo'
        p['executar_migracao_imediata'] = True
        p['migrar_durante_troca_servico'] = {
            'atendimentosOS': True,
            'tipoMigracaoAtendimentoOs': 'atendimento_com_os_aberta',
        }
        self._preencher_objetos_nulos(p)
        return p

    # status "Serviço Habilitado" (id 11) — na migração imediata o serviço nasce ativo
    SERVICO_STATUS_HABILITADO = {
        'id_servico_status': 11, 'descricao': 'Serviço Habilitado',
        'prefixo': 'servico_habilitado', 'ativo': True, 'habilitado': True,
        'imagem': 'assets/images/icons/success.svg', 'cobrar': True,
        'permite_os': True, 'padrao_sistema': True,
        'cobrar_dias_nao_utilizados': True, 'permite_atendimento': True,
    }

    # grupo do serviço (grupo_cliente_servico) — deve ser "Varejo" (id 29), igual
    # ao que o webdriver seleciona. NÃO usar "Varejo - Regional 5" (id 132), que
    # veio do script de migração em massa (processar_csv) e marca a regional errada.
    GRUPO_SERVICO_VAREJO = {
        'id': 29, 'descricao': 'Varejo', 'ativo': True,
        'material_color': None, 'display': 'Varejo',
    }

    def _preencher_objetos_nulos(self, p: dict) -> None:
        """Preenche forma_cobranca/vencimento/grupos/vendedor/servico_status nulos."""
        if not (p.get('servico_status') or {}).get('id_servico_status'):
            p['servico_status'] = dict(self.SERVICO_STATUS_HABILITADO)
            p['id_servico_status'] = 11
        sch = self.schema_cache()
        if not p.get('forma_cobranca'):
            idfc = p.get('id_forma_cobranca') or 140
            p['forma_cobranca'] = next(
                (fc for fc in sch.get('formas_cobranca', [])
                 if fc.get('id_forma_cobranca') == idfc),
                {'id_forma_cobranca': idfc, 'descricao': 'BANCO ITAU', 'ativo': True})
            p['id_forma_cobranca'] = idfc
        if not p.get('vencimento'):
            idv = p.get('id_vencimento') or 9
            p['vencimento'] = next(
                (v for v in sch.get('vencimentos', [])
                 if v.get('id_vencimento') == idv), None)
        if not p.get('vendedor'):
            p['vendedor'] = {'id': 1385, 'name': 'DARLAN VELOZO',
                             'id_imagem_upload': None, 'enabled2fa': False, 'imagem': None}
        if not p.get('id_usuario_vendedor'):
            p['id_usuario_vendedor'] = 1385
        if not p.get('grupos'):
            grupo = None
            for g in sch.get('grupos', []):
                if g.get('id') == 29 or g.get('id_grupo') == 29:
                    grupo = g
                    break
            p['grupos'] = [grupo or dict(self.GRUPO_SERVICO_VAREJO)]

    def migrar_servico(self, id_cliente_servico_antigo: int, id_servico_novo: int) -> dict:
        """Migra (upgrade) o serviço para outro plano via API. Cria o novo serviço
        substituindo o antigo, com migração imediata."""
        obj = self.obter_servico_edit(id_cliente_servico_antigo)
        if not obj:
            raise RuntimeError(f'serviço {id_cliente_servico_antigo} não encontrado (/edit)')
        payload = self.montar_payload_migracao(obj, id_servico_novo)
        r = self._post('/api/v1/cliente/servico', payload)
        log.info(f"  POST /cliente/servico (migração) → {r.status_code}")
        if not r.ok:
            log.error(f"  body: {r.text[:600]}")
            r.raise_for_status()
        j = r.json()
        if j.get('status') != 'success':
            raise RuntimeError(j.get('msg', 'falha na migração'))
        return j

    def get_cliente(self, id_cliente: int) -> dict:
        """GET /api/v1/cliente/{id} — retorna objeto 'cliente' com enderecos."""
        r = self._get(f'/api/v1/cliente/{id_cliente}')
        r.raise_for_status()
        return r.json().get('cliente', {})

    # 9.5) UNIFICAR COBRANÇA — 2 PUTs em /api/v1/cliente/servico/{id}
    def _get_cs_completo_paginado(self, id_cliente: int, id_cs: int) -> dict:
        """Busca cs COMPLETO (117 chaves, com todos sub-objetos) via paginado/5."""
        r = self._post(
            f'/api/v1/cliente/servico/{id_cliente}/buscar/paginado/5',
            {'status': ['servico_habilitado','aguardando_instalacao',
                         'suspenso_debito','suspenso_parcialmente',
                         'aguardando_migracao'],
             'cancelado': False, 'filtros': [], 'id_revenda': None})
        j = r.json()
        data = j.get('cliente', {}).get('servicos', {}).get('data', [])
        for cs in data:
            if cs.get('id_cliente_servico') == id_cs:
                return cs
        raise RuntimeError(f"cs {id_cs} não achado no paginado do cliente {id_cliente}")

    def _put_cs(self, id_cs: int, cs_obj: dict) -> dict:
        """PUT /api/v1/cliente/servico/{id}."""
        r = self._put(f'/api/v1/cliente/servico/{id_cs}', cs_obj)
        if not r.ok:
            log.error(f"  body: {r.text[:500]}")
            r.raise_for_status()
        j = r.json()
        if j.get('status') != 'success':
            log.error(f"  errors: {j.get('errors')}")
            raise RuntimeError(j.get('msg', 'falha no PUT cs'))
        return j

    def unificar_cobranca_etapa_a(self, id_cliente: int,
                                   id_cs_secundario: int,
                                   id_cs_principal: int) -> dict:
        """Etapa A: zera valor do secundário e associa ao principal.
        Setar permite_associar=True é OBRIGATÓRIO — sem isso a API
        silenciosamente ignora id_cliente_servico_associado."""
        cs = self._get_cs_completo_paginado(id_cliente, id_cs_secundario)
        r_edit = self._get(f'/api/v1/cliente/servico/{id_cs_secundario}/edit')
        servs_disponiveis = r_edit.json().get('servicos', [])
        principal = next((s for s in servs_disponiveis
                          if s.get('id_cliente_servico') == id_cs_principal), None)
        if not principal:
            raise RuntimeError(f"id_cs_principal={id_cs_principal} não está na lista "
                                "de associáveis do /edit do secundário")
        cs['valor'] = 0
        cs['permite_associar'] = True
        cs['id_cliente_servico_associado'] = id_cs_principal
        cs['cliente_servico_associado'] = principal
        cs['agrupamento_nota'] = 'desagrupado'
        cs['agrupamento_fatura'] = 'agrupado_cliente'
        cs['carne'] = True
        return self._put_cs(id_cs_secundario, cs)

    def unificar_cobranca_etapa_b(self, id_cliente: int,
                                   id_cs_principal: int,
                                   valor_soma: float) -> dict:
        """Etapa B: define valor=soma no principal e garante config de cobrança."""
        cs = self._get_cs_completo_paginado(id_cliente, id_cs_principal)
        cs['valor'] = round(float(valor_soma), 2)
        cs['id_cliente_servico_associado'] = None
        cs['cliente_servico_associado'] = None
        cs['agrupamento_nota'] = 'desagrupado'
        cs['agrupamento_fatura'] = 'agrupado_cliente'
        cs['carne'] = True
        return self._put_cs(id_cs_principal, cs)

    # 10) CANCELAR SERVIÇO — POST /api/v1/cliente/servico/protocolo_cancelamento
    def cancelar_servico(self, id_cliente_servico: int, *,
                          id_empresa: int = 17,
                          empresa_display: str = "MEGA TELEINFORMATICA LTDA (CNPJ: 11.408.142/0001-09)",
                          id_motivo: int = 88,
                          motivo_descricao: str = "Cadastro Incorreto",
                          observacao: str = "Cadastro incorreto - migracao",
                          data_vencimento: str = None) -> dict:
        """Cancela um cliente_servico. Replica payload capturado via CDP.
        Default: motivo 88 'Cadastro Incorreto', empresa MEGA TELEINFORMATICA,
        sem multa/proporcional/OS, mantém fatura gerada."""
        from datetime import datetime, timedelta
        if data_vencimento is None:
            data_vencimento = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

        payload = {
            'cancelar_fatura_pendente': False,
            'gerar_fatura': True,
            'gerar_multa': False,
            'gerar_proporcional': False,
            'desautorizar_cpe': False,
            'tipo_calculo': 'automatico',
            'remover_porta': False,
            'exibirEquipamentos': False,
            'abrir_os_retirada': False,
            'descricao_os_retirada': None,
            'data_vencimento': data_vencimento,
            'empresa': {'id_empresa': id_empresa, 'display': empresa_display},
            'motivo_cancelamento': {
                'id_motivo_cancelamento': id_motivo,
                'descricao': motivo_descricao,
                'gera_multa': False,
            },
            'observacao': observacao,
            'id_cliente_servico': id_cliente_servico,
            'faturas': [],
            'data_referencia_calculo_proporcional': None,
        }
        r = self._post('/api/v1/cliente/servico/protocolo_cancelamento', payload)
        log.info(f"  POST /protocolo_cancelamento → {r.status_code}")
        if not r.ok:
            log.error(f"  body: {r.text[:500]}")
            r.raise_for_status()
        j = r.json()
        if j.get('status') != 'success':
            log.error(f"  resp: {j}")
            raise RuntimeError(j.get('msg', 'falha no cancelar_servico'))
        return j

    def buscar_id_auth_do_servico(self, id_cliente: int, id_cs: int) -> int:
        """Após criar serviço, busca o id_cliente_servico_autenticacao via
        /cliente/servico/{id_cli}/buscar/paginado/5 (mesma rotina do habilitar)."""
        r = self._post(
            f'/api/v1/cliente/servico/{id_cliente}/buscar/paginado/5',
            {'status': ['aguardando_migracao','servico_habilitado',
                       'suspenso_debito','suspenso_parcialmente',
                       'aguardando_instalacao'],
             'cancelado': False, 'filtros': [], 'id_revenda': None},
        )
        if not r.ok:
            return None
        j = r.json()
        servs = j.get('cliente', {}).get('servicos', {})
        data = servs.get('data', []) if isinstance(servs, dict) else []
        for s in data:
            if s.get('id_cliente_servico') == id_cs:
                auth = s.get('cliente_servico_autenticacao')
                if auth:
                    return auth.get('id_cliente_servico_autenticacao')
        return None

    def montar_payload_adicionar_servico(self, *, id_cliente: int,
                                         id_endereco_numero: int,
                                         endereco_numero_obj: dict,
                                         id_servico: int, valor: float,
                                         id_vencimento: int,
                                         servico_status_obj: dict = None,
                                         forma_cobranca_obj: dict = None,
                                         grupo_obj: dict = None,
                                         vendedor_obj: dict = None) -> dict:
        """Monta o payload do POST /cliente/servico baseado no template
        capturado via DevTools (template_servico_capturado.json)."""
        from datetime import datetime

        servico = self.buscar_plano_por_id(id_servico)
        # Status "Aguardando Instalação" (id=6) — habilita_servico() faz o resto
        if servico_status_obj is None:
            servico_status_obj = {
                'id_servico_status': 6,
                'descricao': 'Aguardando Instalação',
                'prefixo': 'aguardando_instalacao',
                'ativo': True, 'habilitado': False,
                'imagem': 'assets/images/icons/clock.png',
                'cobrar': False, 'permite_os': True,
                'padrao_sistema': True,
                'cobrar_dias_nao_utilizados': True,
                'permite_atendimento': True,
            }
        # BANCO ITAU (id=140) — pega completo do schema cacheado
        if forma_cobranca_obj is None:
            sch = self.schema_cache()
            for fc in sch.get('formas_cobranca', []):
                if fc.get('id_forma_cobranca') == 140:
                    forma_cobranca_obj = fc
                    break
            if forma_cobranca_obj is None:
                forma_cobranca_obj = {'id_forma_cobranca': 140,
                                       'descricao': 'BANCO ITAU', 'ativo': True}
        # grupo do serviço = "Varejo" (id=29). NÃO usar "Varejo - Regional 5" (132).
        if grupo_obj is None:
            grupo_obj = dict(self.GRUPO_SERVICO_VAREJO)
        if vendedor_obj is None:
            vendedor_obj = {
                'id': 1385, 'name': 'DARLAN VELOZO',
                'id_imagem_upload': None,
                'enabled2fa': False, 'imagem': None,
            }

        # Endereço usado em 4 papéis: instalacao, cadastral, cobranca, fiscal
        endereco_item = {
            'id_endereco_numero': id_endereco_numero,
            'endereco_numero': endereco_numero_obj,
        }
        cs_enderecos = []
        for tipo in ('instalacao', 'cadastral', 'cobranca', 'fiscal'):
            item = dict(endereco_item)
            item['tipo'] = tipo
            cs_enderecos.append(item)

        return {
            'id_cliente': id_cliente,
            'id_usuario_vendedor': vendedor_obj['id'],
            'id_vencimento': id_vencimento,
            'valor': valor,
            'validade': 12,
            'carne': False,
            'gerar_carne': 'nao_gerar_carne',
            'tipo_cobranca': 'postecipada',
            'agrupamento_fatura': 'agrupado_cliente',
            'agrupamento_nota': 'desagrupado',
            'data_venda': datetime.now().isoformat() + 'Z',
            'dados_calculo': None,
            'servico': servico,
            'servico_status': servico_status_obj,
            'forma_cobranca': forma_cobranca_obj,
            'vendedor': vendedor_obj,
            'grupos': [grupo_obj],
            'cliente_servico_endereco': cs_enderecos,
            'cliente_servico_taxa_instalacao': {
                'cobrar_taxa_instalacao': False,
                'tipo_taxa_instalacao': 'nao_cobrar_taxa',
                'cobranca_parcelada': 'parcelado',
                'parcelas': None,
            },
            'cliente_servico_contrato': [],
            'cliente_servico_pacote': [],
            'cliente_servico_pacote_migracao': [],
            'cliente_servico_pacote_transmissao': [],
            'promocoes': [],
            'promocoes_desativar': [],
            'migrar_durante_troca_servico': {
                'atendimentosOS': [], 'tipoMigracaoAtendimentoOs': None,
            },
        }


    # ============ Funcoes de alto nível ============

    def schema_cache(self):
        """Schema do /cliente/create (cacheado em memória após 1º call)."""
        if not hasattr(self, '_schema'):
            self._schema = self.get_cliente_create()
        return self._schema

    def buscar_plano_por_id(self, id_servico: int) -> dict:
        """Acha o objeto 'servico' completo a partir do id_servico.
        Como /cliente/create não traz lista de serviços por padrão,
        usamos /api/v1/servico/{id} se existir; senão, fallback para banco.
        """
        # Tenta endpoint direto
        r = self._get(f'/api/v1/servico/{id_servico}')
        if r.ok:
            try:
                j = r.json()
                if 'servico' in j:
                    return j['servico']
            except Exception:
                pass
        # Fallback: busca via /api/v1/configuracao/geral/promocao/verifica_disponibilidade
        # ou via banco
        log.warning(f"  /servico/{id_servico} não retornou servico — usando banco")
        import psycopg2
        conn = psycopg2.connect(
            host=os.environ['HUBSOFT_DB_HOST'], port=os.environ['HUBSOFT_DB_PORT'],
            dbname=os.environ['HUBSOFT_DB_NAME'], user=os.environ['HUBSOFT_DB_USER'],
            password=os.environ['HUBSOFT_DB_PASSWORD'])
        cur = conn.cursor()
        cur.execute("""
            SELECT id_servico, id_servico_tecnologia, id_servico_grupo,
                   id_servico_status, descricao, valor, tipo_pagamento,
                   tipo_cobranca, ativo, autentica_radius, carne, emite_contrato,
                   garantia_banda_download, garantia_banda_upload, validade
            FROM servico WHERE id_servico = %s
        """, (id_servico,))
        r = cur.fetchone()
        conn.close()
        if not r:
            raise RuntimeError(f"id_servico={id_servico} não existe no banco")
        return {
            'id_servico': r[0], 'id_servico_tecnologia': r[1],
            'id_servico_grupo': r[2], 'id_servico_status': r[3],
            'descricao': r[4], 'valor': float(r[5]) if r[5] else 0,
            'tipo_pagamento': r[6], 'tipo_cobranca': r[7],
            'ativo': r[8], 'autentica_radius': r[9],
            'carne': r[10], 'emite_contrato': r[11],
            'garantia_banda_download': str(r[12] or ''),
            'garantia_banda_upload': str(r[13] or ''),
            'validade': r[14] or 12,
            'permite_associar': True, 'permite_prospecto': False,
            'travar_pacotes': False, 'permite_mvno': False,
            'usa_rede_neutra': False,
            'nome_radius': f'HUBSOFT-SERVICE-{r[0]}',
            'display': r[4],
            'servico_composicao': [], 'servico_contrato': [],
        }

    # Mapa estático de id_vencimento na megalink (consultado em 2026-06-17)
    # dia → id_vencimento. Para dias não disponíveis, escolhe próximo maior.
    VENCIMENTOS_MEGALINK = {
        1: 28, 5: 9, 10: 4, 15: 5, 20: 6, 25: 11,
        # último_dia → id 10
    }
    DIAS_DISPONIVEIS = sorted(VENCIMENTOS_MEGALINK.keys())

    def resolver_id_vencimento(self, dia: int) -> tuple[int, int]:
        """Retorna (id_vencimento, dia_real). Para dia inexistente, próximo
        maior; se >25 ou 'último', usa id 10 (último_dia)."""
        try:
            d = int(dia)
        except (TypeError, ValueError):
            return (4, 10)  # default dia 10
        if d in self.VENCIMENTOS_MEGALINK:
            return (self.VENCIMENTOS_MEGALINK[d], d)
        maiores = [x for x in self.DIAS_DISPONIVEIS if x > d]
        if maiores:
            d_ok = maiores[0]
            return (self.VENCIMENTOS_MEGALINK[d_ok], d_ok)
        # > 25: último_dia
        return (10, 31)

    def buscar_cidade_por_nome(self, nome_cidade: str, uf: str) -> dict:
        """Fallback: busca cidade no banco megalink quando CEP não retorna.
        Retorna objeto cidade_completo no mesmo formato da API."""
        import psycopg2, unicodedata, re
        def norm(s):
            s = unicodedata.normalize('NFKD', str(s).upper())
            s = ''.join(c for c in s if not unicodedata.combining(c))
            return re.sub(r'\s+', ' ', s).strip()
        alvo = norm(nome_cidade)
        conn = psycopg2.connect(
            host=os.environ['HUBSOFT_DB_HOST'], port=os.environ['HUBSOFT_DB_PORT'],
            dbname=os.environ['HUBSOFT_DB_NAME'], user=os.environ['HUBSOFT_DB_USER'],
            password=os.environ['HUBSOFT_DB_PASSWORD'])
        cur = conn.cursor()
        cur.execute("""
            SELECT cd.id_cidade, cd.nome, cd.cep, cd.ibge, cd.ativo, cd.nome_nfse,
                   e.id_estado, e.nome as est_nome, e.sigla, e.ibge, e.id_pais
            FROM cidade cd
            JOIN estado e ON e.id_estado = cd.id_estado
            WHERE e.sigla = %s
        """, (uf.upper(),))
        rs = cur.fetchall()
        conn.close()
        # Match: nome exato (normalizado) → nome contém → nome do CSV contém nome banco
        melhor = None
        for r in rs:
            n = norm(r[1])
            if n == alvo:
                melhor = r; break
        if melhor is None:
            for r in rs:
                n = norm(r[1])
                if n in alvo or alvo in n:
                    melhor = r; break
        if melhor is None:
            return {}
        cidade_obj = {
            'id_cidade': melhor[0],
            'nome': melhor[1],
            'cep': melhor[2],
            'ibge': melhor[3],
            'ativo': melhor[4],
            'nome_nfse': melhor[5],
            'display': f'{melhor[1].upper()}/{melhor[8]}',
            'display_lower': melhor[1].lower(),
            'value': melhor[0],
            'id_estado': melhor[6],
            'estado': {
                'id_estado': melhor[6],
                'nome': melhor[7],
                'sigla': melhor[8],
                'ibge': melhor[9],
                'id_pais': melhor[10],
                'ativo': True,
                'display': melhor[7].upper(),
                'display_lower': melhor[7].lower(),
                'value': melhor[6],
            },
        }
        return cidade_obj

    def buscar_contratos_do_plano(self, id_servico: int) -> list:
        """Retorna lista de contratos vinculados ao plano com sub-objeto
        contrato completo (formato esperado pela API)."""
        import psycopg2
        from datetime import datetime
        conn = psycopg2.connect(
            host=os.environ['HUBSOFT_DB_HOST'], port=os.environ['HUBSOFT_DB_PORT'],
            dbname=os.environ['HUBSOFT_DB_NAME'], user=os.environ['HUBSOFT_DB_USER'],
            password=os.environ['HUBSOFT_DB_PASSWORD'])
        cur = conn.cursor()
        cur.execute("""
            SELECT sc.id_contrato, sc.id_empresa, sc.obrigatorio,
                   c.descricao, c.ativo, c.validade, c.gera_multa,
                   c.valor_multa, c.id_tipo_servico_multa_contratual,
                   c.descricao_multa, c.permite_renovar_vigencia_servico
            FROM servico_contrato sc
            LEFT JOIN contrato c ON c.id_contrato = sc.id_contrato
            WHERE sc.id_servico = %s
        """, (id_servico,))
        rs = cur.fetchall()
        conn.close()
        contratos = []
        for r in rs:
            id_contrato = r[0]
            id_empresa = r[1]
            contratos.append({
                'id_empresa': id_empresa,
                'id_contrato': id_contrato,
                'obrigatorio': r[2],
                'contrato': {
                    'id_contrato': id_contrato,
                    'descricao': r[3] or '',
                    'ativo': r[4],
                    'validade': r[5] or 12,
                    'gera_multa': r[6] or False,
                    'valor_multa': float(r[7]) if r[7] is not None else None,
                    'id_empresa': id_empresa,
                    'id_tipo_servico_multa_contratual': r[8],
                    'descricao_multa': r[9],
                    'permite_renovar_vigencia_servico': r[10]
                        if r[10] is not None else True,
                    'display': r[3] or '',
                },
                'data_inicio': datetime.now().isoformat() + 'Z',
                'data_termino': None,
                'anexos': [],
            })
        return contratos

    def montar_payload(self, dados, template: dict, endereco_resolvido: dict) -> dict:
        """Constrói payload do POST /api/v1/cliente substituindo campos do template."""
        import copy
        from datetime import datetime

        payload = copy.deepcopy(template)
        doc = ''.join(c for c in dados.cpf_cnpj if c.isdigit())
        tel = ''.join(c for c in dados.telefone_1 if c.isdigit())
        # Detecta tipo pessoa: CNPJ tem 14 dígitos, CPF tem 11
        is_pj = (getattr(dados, 'tipo_cliente', 'fisica') == 'juridica') or (len(doc) == 14)

        payload['cpf_cnpj'] = doc
        payload['nome_razaosocial'] = dados.nome
        payload['nome_fantasia'] = dados.nome
        payload['telefone_primario'] = tel
        payload['email_principal'] = dados.email_principal

        if is_pj:
            # PJ: sem data_nascimento, sem gênero. Adiciona campos PJ-específicos.
            payload['tipo_pessoa'] = 'pj'
            payload['data_nascimento'] = None
            payload['indicador_inscricao_estadual'] = '9'  # 9 = não contribuinte
            payload['consumidor_final'] = '1'              # 1 = consumidor final
            # Limpa campos PF que podem estar no template
            for k in ('genero', 'estado_civil', 'nome_pai', 'nome_mae',
                      'nacionalidade', 'profissao', 'rg'):
                if k in payload:
                    payload[k] = None
        else:
            payload['tipo_pessoa'] = 'pf'
            # Data nascimento: formato 'YYYY-MM-DD' (sem timezone)
            # Megalink rejeita idade < 18 anos e datas muito antigas (>110 anos).
            # Fora dos limites razoáveis (18-110 anos), usa default 1930.
            try:
                dt = datetime.strptime(dados.data_nascimento, '%d/%m/%Y')
                anos = (datetime.now() - dt).days // 365
                if anos < 18 or anos > 110:
                    payload['data_nascimento'] = '1930-01-01'
                else:
                    payload['data_nascimento'] = dt.strftime('%Y-%m-%d')
            except Exception:
                payload['data_nascimento'] = '1930-01-01'

        # Endereço resolvido (mesmo nas 2 entradas + endereco_instalacao)
        enderecos = endereco_resolvido
        # cliente_endereco_numeros: [cadastral, cobranca]
        for i, end_item in enumerate(payload['cliente_endereco_numeros']):
            tipo = end_item.get('tipo', 'cadastral')
            end_item.update(enderecos)
            end_item['tipo'] = tipo
        payload['cliente_servico_endereco_instalacao'].update(enderecos)
        payload['cliente_servico_endereco_instalacao']['tipo'] = 'cadastral'

        # Plano: substitui id_servico, valor, descricao
        id_servico = int(dados.id_plano_megalink) if dados.id_plano_megalink else None
        if id_servico:
            novo_servico = self.buscar_plano_por_id(id_servico)
            payload['cliente_servico']['servico'] = novo_servico
            payload['cliente_servico']['valor'] = novo_servico.get('valor', 75)

            # Popula contratos do plano (se houver) — API exige
            contratos = self.buscar_contratos_do_plano(id_servico)
            payload['cliente_servico_contratos'] = contratos
            # Coloca tb dentro do servico (alguns formats exigem)
            novo_servico['servico_contrato'] = contratos

        # Vencimento: mapeia dia do CSV → id_vencimento da megalink
        id_venc, dia_real = self.resolver_id_vencimento(dados.dia_vencimento)
        v_obj = {
            'id_vencimento': id_venc,
            'dia_vencimento': str(dia_real) if dia_real != 31 else 'ultimo_dia',
            'ativo': True,
            'display': str(dia_real) if dia_real != 31 else 'ultimo_dia',
            'value': id_venc,
        }
        payload['cliente_servico']['vencimento'] = v_obj
        payload['cliente_servico']['id_vencimento'] = id_venc
        # No root também (algumas APIs pegam de lá)
        payload['id_vencimento'] = id_venc

        # Grupos cliente_servico = "Varejo" (id 29). Já vem do template como
        # Boleto Digital; substitui para Varejo (NÃO "Varejo - Regional 5"/132).
        payload['cliente_servico']['grupos'] = [dict(self.GRUPO_SERVICO_VAREJO)]

        # Data da venda
        payload['cliente_servico']['data_venda'] = datetime.now().isoformat() + 'Z'

        # Vendedor das conversões do robô v2 = 1613 "Venda-Automática" (mira
        # própria, separada do gestao_leads_bot que usa 1618).
        payload['cliente_servico']['vendedor'] = dict(self.VENDEDOR_CONVERSAO)
        payload['cliente_servico']['id_usuario_vendedor'] = self.VENDEDOR_CONVERSAO['id']

        return payload

    # Vendedor atrelado às conversões prospecto→cliente do robô v2 (id 1613).
    VENDEDOR_CONVERSAO = {
        'id': 1613, 'name': 'Venda-Automática',
        'email': 'webdriver@megalinkinternet.com.br',
        'id_imagem_upload': None, 'enabled2fa': False, 'imagem': None,
    }


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    cli = ClienteHTTP(headless=True)
    try:
        cli.login()

        # Sanity check: chama um endpoint simples
        log.info("Testando endpoint /cliente/create (schema)...")
        sch = cli.get_cliente_create()
        print(f"  status={sch.get('status')}")
        # Salva schema pra análise
        with open('/tmp/megalink_schema.json', 'w') as f:
            json.dump(sch, f, ensure_ascii=False, indent=2)
        print(f"  Schema salvo em /tmp/megalink_schema.json ({len(json.dumps(sch))} bytes)")

        # Grupos cliente
        grupos = sch.get('grupos_clientes', [])
        print(f"  grupos_clientes: {len(grupos)}")
        for g in grupos[:10]:
            print(f"    id={g.get('id_grupo_cliente')} {g.get('descricao')!r}")

        # Vendedores (achar DARLAN ou semelhante)
        vendedores = sch.get('vendedores', [])
        print(f"  vendedores: {len(vendedores)}")
        for v in vendedores[:5]:
            print(f"    id={v.get('id_usuario')} nome={v.get('nome') or v.get('display')!r}")
        darlan = [v for v in vendedores if 'DARLAN' in
                  json.dumps(v, ensure_ascii=False).upper()]
        print(f"  DARLAN matches: {len(darlan)}")
        for v in darlan[:3]:
            print(f"    {v}")

        # Sanity: TEREZA CPF check
        existe = cli.cpf_ja_cadastrado('890.376.423-49')
        print(f"  TEREZA CPF já cadastrado? {existe}")

        # ======== TESTE COM LINHA 6 (LINDINA - PF não cadastrada) ========
        from processar_csv import linha_csv_para_dados, ler_linha
        row = ler_linha(os.path.join(os.path.dirname(__file__),
                        '..', 'migracao', 'migrar_clientes_megalink.csv'), 6)
        dados, ajustes = linha_csv_para_dados(row, exigir_telefone=False)
        log.info(f"=== TESTE LINHA 3: {dados.nome} CPF={dados.cpf_cnpj} ===")

        # Pre-check
        if cli.cpf_ja_cadastrado(dados.cpf_cnpj):
            log.warning(f"CPF {dados.cpf_cnpj} já cadastrado — abortando teste")
            sys.exit(0)

        # Resolve endereço
        log.info("Resolvendo endereço...")
        cep_data = cli.buscar_cep(dados.cep)
        cidade_obj = cep_data.get('cidade_completo')
        if not cidade_obj:
            log.error(f"CEP {dados.cep!r} sem cidade_completo")
            sys.exit(1)
        log.info(f"  cidade resolvida: {cidade_obj.get('display')!r} "
                 f"id_cidade={cidade_obj.get('id_cidade')}")

        # Monta endereço resolvido (objeto que vai no payload)
        endereco_resolvido = {
            'id_endereco_numero': None,
            'cep': ''.join(c for c in dados.cep if c.isdigit()),
            'endereco': dados.rua,
            'numero': str(dados.numero or 'S/N'),
            'bairro': dados.bairro,
            'complemento': dados.complemento or None,
            'referencia': dados.referencia or None,
            'cidade': cidade_obj,
            'estado': cidade_obj.get('estado', {}),
            'pais': cep_data.get('pais', {}),
            'condominio': None,
            'atualizar_coords_auto': True,
        }

        # Carrega template
        with open(os.path.join(os.path.dirname(__file__), 'templates', 'template_cliente.json')) as f:
            template = json.load(f)
        log.info("Template carregado")

        # Monta payload
        payload = cli.montar_payload(dados, template, endereco_resolvido)
        log.info(f"Payload montado ({len(json.dumps(payload))} bytes)")

        # Salva payload pra debug
        with open('/tmp/payload_ana.json', 'w') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        log.info("Payload salvo em /tmp/payload_ana.json")

        # POST de criação
        log.info("Enviando POST /api/v1/cliente...")
        resp = cli.criar_cliente(payload)
        log.info(f"  msg: {resp.get('msg')!r}")
        cli_obj = resp.get('cliente', {})
        log.info(f"  ✓ id_cliente: {cli_obj.get('id_cliente')}")
        log.info(f"  codigo_cliente: {cli_obj.get('codigo_cliente')}")
        servicos = cli_obj.get('servicos', [])
        log.info(f"  servicos criados: {len(servicos)}")
        for s in servicos:
            log.info(f"    cs_id={s.get('id_cliente_servico')} "
                     f"status={s.get('servico_status',{}).get('descricao')!r}")
    finally:
        cli.close()
