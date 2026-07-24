"""Captura o template de payload da conversao (POST /api/v1/cliente) direto do
painel HubSoft, via Chrome DevTools Protocol, e grava em
`PerfilConversaoHubsoft.template_conversao`.

Diferente do robo_v2 (que roteava o wizard inteiro com XPaths fixos da Megalink e
fazia a conversao sozinho), aqui e TENANT-AGNOSTICO: o comando abre o painel numa
janela, faz login best-effort com a credencial do tenant, e o OPERADOR dirige o
wizard "Converter em Cliente" manualmente uma vez (com um prospecto de TESTE). O
comando so fareja a rede e captura o POST /cliente que o proprio painel dispara no
SALVAR. Zero XPath especifico: serve pra qualquer HubSoft.

Antes de gravar no perfil, o PII do prospecto de teste (cpf, nome, telefone, email,
rg, id_prospecto, endereco) e NEUTRALIZADO: o template guarda so a estrutura +
objetos da empresa (servico, contratos, forma_cobranca); a identidade e o endereco
sao preenchidos por lead em tempo de execucao (montar_payload_conversao).

Uso (janela visivel obrigatoria pra o operador dirigir):
    python manage.py hubsoft_capturar_template --tenant demo-local --perfil padrao \\
        --salvar-perfil --settings=gerenciador_vendas.settings_local

⚠️ A captura exige uma conversao REAL no painel (o operador clica SALVAR). Use um
prospecto de teste. Sem --salvar-perfil, so grava o JSON num arquivo pra revisao.
"""
import json
import time

from django.core.management.base import BaseCommand, CommandError


def _configurar_chrome_cdp():
    """Chrome NAO-headless com performance logging (captura de rede via CDP)."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    for arg in ('--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900',
                '--disable-gpu', '--no-first-run', '--disable-default-apps'):
        opts.add_argument(arg)
    opts.set_capability('goog:loggingPrefs', {'performance': 'ALL', 'browser': 'ALL'})
    opts.add_experimental_option('perfLoggingPrefs', {'enableNetwork': True, 'enablePage': False})
    return webdriver.Chrome(options=opts)


def _posts_de(driver, url_contem: str, excluir: str):
    """Le os perf logs e devolve os POST cuja URL contem `url_contem` e nao contem
    `excluir`. Cada item: {request_id, url, status}."""
    achados = []
    for entry in driver.get_log('performance'):
        try:
            msg = json.loads(entry['message'])['message']
            if msg.get('method') != 'Network.requestWillBeSent':
                continue
            req = msg['params']['request']
            url = req.get('url', '')
            if req.get('method') != 'POST':
                continue
            if url_contem in url and (not excluir or excluir not in url):
                achados.append({'request_id': msg['params']['requestId'], 'url': url})
        except Exception:
            continue
    return achados


def _corpo_da_request(driver, request_id):
    """Corpo completo do POST via CDP (Network.getRequestPostData)."""
    try:
        r = driver.execute_cdp_cmd('Network.getRequestPostData', {'requestId': request_id})
        return r.get('postData') or ''
    except Exception:
        return ''


def _login_best_effort(driver, painel_url, usuario, senha, stdout):
    """Tenta logar sozinho (email -> VALIDAR -> senha -> ENTRAR). Se falhar, o
    operador loga na propria janela. Reusa o casamento de botao em caixa alta."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from apps.integracoes.services.hubsoft_painel import _botao_xpath
    try:
        driver.get(f'{painel_url}/login')
        wait = WebDriverWait(driver, 25)
        email = wait.until(EC.presence_of_element_located((By.NAME, 'email')))
        email.clear(); email.send_keys(usuario)
        time.sleep(0.8)
        try:
            WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, _botao_xpath('validar')))).click()
        except Exception:
            pass
        pwd = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']")))
        pwd.clear(); pwd.send_keys(senha)
        time.sleep(0.8)
        wait.until(EC.element_to_be_clickable((By.XPATH, _botao_xpath('entrar')))).click()
        stdout.write('  login automatico enviado.')
    except Exception as exc:
        stdout.write(f'  login automatico falhou ({exc}); faca login na janela aberta.')


def _neutralizar_pii(payload: dict) -> dict:
    """Zera a identidade/endereco do prospecto de teste, mantendo a estrutura +
    objetos da empresa. O que for zerado aqui e reescrito por lead no runtime."""
    import copy
    p = copy.deepcopy(payload)
    for k in ('cpf_cnpj', 'nome_razaosocial', 'nome_fantasia', 'telefone_primario',
              'telefone_secundario', 'email_principal', 'rg'):
        if k in p:
            p[k] = ''
    for k in ('data_nascimento', 'id_prospecto', 'nome_pai', 'nome_mae'):
        if k in p:
            p[k] = None
    end_keys = ('cep', 'endereco', 'numero', 'bairro', 'complemento', 'referencia')
    for item in (p.get('cliente_endereco_numeros') or []):
        if isinstance(item, dict):
            for k in end_keys:
                if k in item:
                    item[k] = '' if k in ('cep', 'endereco', 'numero', 'bairro') else None
    inst = p.get('cliente_servico_endereco_instalacao')
    if isinstance(inst, dict):
        for k in end_keys:
            if k in inst:
                inst[k] = '' if k in ('cep', 'endereco', 'numero', 'bairro') else None
    return p


class Command(BaseCommand):
    help = ('Captura o template_conversao (POST /cliente) do painel HubSoft via CDP, '
            'com o operador dirigindo o wizard. Neutraliza PII antes de gravar.')

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True)
        parser.add_argument('--perfil', default='padrao')
        parser.add_argument('--integracao-id', type=int, default=None,
                            help='IntegracaoAPI hubsoft_painel especifica (default: a 1a ativa).')
        parser.add_argument('--url-contem', default='/api/v1/cliente',
                            help='Filtro da URL do POST a capturar.')
        parser.add_argument('--excluir', default='/servico',
                            help='Descarta POSTs cuja URL contenha isto (default /servico).')
        parser.add_argument('--timeout', type=int, default=600,
                            help='Segundos aguardando o operador concluir (default 600).')
        parser.add_argument('--salvar-perfil', action='store_true',
                            help='Grava o payload capturado em perfil.template_conversao.')

    def handle(self, *args, **o):
        from apps.sistema.models import Tenant
        from apps.integracoes.models import IntegracaoAPI, PerfilConversaoHubsoft

        tenant = Tenant.objects.filter(slug=(o['tenant'] or '').strip()).first()
        if tenant is None:
            raise CommandError(f"Tenant '{o['tenant']}' nao encontrado.")
        perfil = PerfilConversaoHubsoft.all_tenants.filter(tenant=tenant, nome=o['perfil']).first()
        if perfil is None:
            raise CommandError(f"Perfil '{o['perfil']}' nao encontrado no tenant {tenant.slug}.")
        qs = IntegracaoAPI.all_tenants.filter(tenant=tenant, tipo='hubsoft_painel', ativa=True)
        if o['integracao_id']:
            qs = qs.filter(pk=o['integracao_id'])
        integ = qs.order_by('nome').first()
        if integ is None:
            raise CommandError(f'Tenant {tenant.slug} sem integracao hubsoft_painel ativa.')

        painel_url = (integ.base_url or '').rstrip('/')
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Captura de template, tenant {tenant.slug}, painel {painel_url}'))

        driver = None
        try:
            driver = _configurar_chrome_cdp()
            _login_best_effort(driver, painel_url, integ.client_id, integ.client_secret, self.stdout)

            self.stdout.write(self.style.WARNING(
                '\n  ===================== FACA AGORA NA JANELA DO CHROME =====================\n'
                '  1. Se pedir login, entre (a janela ja tentou logar sozinha).\n'
                '  2. Menu Cliente -> Prospectos.\n'
                '  3. Busque o prospecto de TESTE (ex: 24596) e clique em Acoes.\n'
                '  4. Converter em Cliente -> preencha o wizard (plano, vencimento,\n'
                '     grupo, banco) -> avance ate o fim -> clique SALVAR.\n'
                f'  Estou escutando a rede e capturo o POST {o["url_contem"]} sozinho.\n'
                f'  Voce tem {o["timeout"]}s. NAO feche a janela nem este terminal.\n'
                '  =========================================================================\n'))

            driver.get_log('performance')  # zera o que veio do login
            alvo, fim = None, time.time() + o['timeout']
            prox_aviso = time.time() + 30
            while time.time() < fim:
                posts = _posts_de(driver, o['url_contem'], o['excluir'])
                if posts:
                    alvo = posts[-1]
                    break
                if time.time() >= prox_aviso:
                    restante = int(fim - time.time())
                    self.stdout.write(f'  ...ainda aguardando o SALVAR ({restante}s restantes)')
                    prox_aviso += 30
                time.sleep(2.0)

            if alvo is None:
                raise CommandError(f'Nenhum POST {o["url_contem"]} capturado em {o["timeout"]}s.')

            body = _corpo_da_request(driver, alvo['request_id'])
            try:
                payload = json.loads(body) if body else {}
            except Exception:
                raise CommandError(f'POST capturado mas corpo nao e JSON valido ({len(body)}b).')
            if not isinstance(payload, dict) or not payload:
                raise CommandError('Payload capturado vazio/invalido.')

            self.stdout.write(self.style.SUCCESS(
                f'  capturado: POST {alvo["url"]} ({len(body)}b, {len(payload)} chaves)'))
            limpo = _neutralizar_pii(payload)

            scratch = f'/tmp/template_conversao_{tenant.slug}.json'
            with open(scratch, 'w', encoding='utf-8') as f:
                json.dump(limpo, f, indent=2, ensure_ascii=False)
            self.stdout.write(f'  JSON (PII neutralizado) salvo em {scratch}')

            if o['salvar_perfil']:
                perfil.template_conversao = limpo
                perfil.save(update_fields=['template_conversao', 'atualizado_em'])
                self.stdout.write(self.style.SUCCESS(
                    f'  gravado em perfil "{perfil.nome}".template_conversao'))
            else:
                self.stdout.write(
                    '  (sem --salvar-perfil: revise o JSON e rode de novo com a flag pra gravar)')
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
