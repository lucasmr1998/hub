"""Explora o processo de conversao/cadastro no painel HubSoft e extrai TODOS os
campos e catalogos (IDs), sem salvar nada.

Duas frentes:
1. API interna (sempre): le os schemas /api/v1/cliente/create e
   /api/v1/cliente/servico/create e monta um relatorio com os campos do cliente e
   do servico (obrigatorios/opcionais) + todos os catalogos com id e descricao
   (grupo_cliente, origem_cliente, grupos_cliente_servico, forma_cobranca,
   vencimento, servico_status, tipos_servico, vendedores, contratos...).
2. Webdriver (--com-webdriver): abre o painel, entra no wizard "Converter em
   Cliente" de um prospecto e percorre as etapas capturando os campos de cada uma
   (extracao GENERICA do DOM, sem XPath fixo) + screenshots. NUNCA clica SALVAR
   (dry-run total).

Uso:
    python manage.py hubsoft_explorar_conversao --tenant demo-local \\
        [--com-webdriver --id-prospecto 24596 --com-janela] \\
        --settings=gerenciador_vendas.settings_local

Saida em <scratch>/hubsoft_conversao/ (relatorio.md, schemas .json, screenshots).
"""
import json
import os
import time

from django.core.management.base import BaseCommand, CommandError

# catalogos que interessam -> (chave no schema, rotulo)
_CATALOGOS = [
    ('grupos_clientes', 'Grupo do cliente'),
    ('origens_cliente', 'Origem do cliente'),
    ('origens_cliente_editar', 'Origem do cliente (edicao)'),
    ('origens_servico', 'Origem do servico'),
    ('grupos_cliente_servico', 'Grupo do servico'),
    ('formas_cobranca', 'Forma de cobranca'),
    ('vencimentos', 'Vencimento'),
    ('servicos_status', 'Status do servico'),
    ('tipos_servico', 'Tipo de servico'),
    ('tipos_cliente', 'Tipo de cliente'),
    ('generos', 'Genero'),
    ('estados_civil', 'Estado civil'),
    ('nacionalidades', 'Nacionalidade'),
    ('cfops', 'CFOP'),
    ('contratos', 'Contrato'),
    ('vendedores', 'Vendedor'),
    ('tecnicos', 'Tecnico'),
]


def _id_label(item):
    """(id, label) de um item de catalogo, robusto a nomes de chave variados."""
    if not isinstance(item, dict):
        return (item, str(item))
    idv = None
    for k, v in item.items():
        if k == 'id' or k.startswith('id_'):
            idv = v
            break
    label = (item.get('descricao') or item.get('nome') or item.get('name')
             or item.get('display') or item.get('dia_vencimento') or '')
    return (idv, str(label))


def _campos_do_formulario(form):
    """(obrigatorios, opcionais) a partir de formulario.parametros (*.required)."""
    req, opt = [], []
    for p in (form or {}).get('parametros') or []:
        pref = p.get('prefixo', '')
        if pref.endswith('.required'):
            campo = pref[:-len('.required')]
            (req if p.get('valor') else opt).append(campo)
    return req, opt


class Command(BaseCommand):
    help = 'Extrai os campos e catalogos (IDs) da conversao/cadastro HubSoft, sem salvar.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True)
        parser.add_argument('--integracao-id', type=int, default=None)
        parser.add_argument('--com-webdriver', action='store_true',
                            help='Alem da API, percorre o wizard no navegador (dry-run, nao salva).')
        parser.add_argument('--id-prospecto', default=None,
                            help='Prospecto pra abrir no wizard (so com --com-webdriver).')
        parser.add_argument('--com-janela', action='store_true', help='Mostra o navegador.')
        parser.add_argument('--saida', default=None, help='Diretorio de saida do relatorio.')

    def handle(self, *args, **o):
        from apps.sistema.models import Tenant
        from apps.integracoes.services.hubsoft_painel import hubsoft_painel_do_tenant

        tenant = Tenant.objects.filter(slug=(o['tenant'] or '').strip()).first()
        if tenant is None:
            raise CommandError(f"Tenant '{o['tenant']}' nao encontrado.")
        svc = hubsoft_painel_do_tenant(tenant, integracao_id=o['integracao_id'])
        if svc is None:
            raise CommandError(f'Tenant {tenant.slug} sem integracao hubsoft_painel ativa.')

        saida = o['saida'] or os.path.join(os.environ.get('TMPDIR', '/tmp'), 'hubsoft_conversao')
        os.makedirs(saida, exist_ok=True)
        self.stdout.write(self.style.MIGRATE_HEADING(f'Explorando conversao HubSoft -> {saida}'))

        # === 1. API interna ===
        schema_cli = svc.schema_cache()
        schema_serv = svc._get('/api/v1/cliente/servico/create')
        json.dump(schema_cli, open(os.path.join(saida, 'schema_cliente_create.json'), 'w'),
                  ensure_ascii=False, indent=1)
        json.dump(schema_serv, open(os.path.join(saida, 'schema_servico_create.json'), 'w'),
                  ensure_ascii=False, indent=1)

        req_c, opt_c = _campos_do_formulario(schema_cli.get('formulario'))
        req_s, opt_s = _campos_do_formulario(schema_serv.get('formulario')
                                             or schema_cli.get('formulario_cliente_servico'))

        linhas = ['# Conversao/Cadastro HubSoft — campos e catalogos', '',
                  f'Tenant: {tenant.slug} · painel: {svc.painel_url}', '',
                  '## Campos do CLIENTE', '',
                  '**Obrigatorios:** ' + (', '.join(req_c) or '(nenhum)'),
                  '', '**Opcionais:** ' + (', '.join(opt_c) or '(nenhum)'), '',
                  '## Campos do SERVICO', '',
                  '**Obrigatorios:** ' + (', '.join(req_s) or '(nenhum)'),
                  '', '**Opcionais:** ' + (', '.join(opt_s) or '(nenhum)'), '',
                  '## Catalogos (id -> descricao)', '']

        fonte = dict(schema_cli)
        fonte.update({k: v for k, v in schema_serv.items() if k not in fonte or not fonte.get(k)})
        resumo = {}
        for chave, rotulo in _CATALOGOS:
            itens = fonte.get(chave)
            if not isinstance(itens, list):
                continue
            resumo[chave] = len(itens)
            linhas.append(f'### {rotulo} (`{chave}`) — {len(itens)} itens')
            for it in itens:
                idv, lab = _id_label(it)
                linhas.append(f'- {idv} — {lab}')
            linhas.append('')

        rel = os.path.join(saida, 'relatorio.md')
        open(rel, 'w').write('\n'.join(linhas))
        self.stdout.write(self.style.SUCCESS(f'  relatorio da API: {rel}'))
        self.stdout.write(f'  campos cliente obrigatorios: {req_c}')
        self.stdout.write(f'  campos servico obrigatorios: {req_s}')
        self.stdout.write('  catalogos: ' + ', '.join(f'{k}={n}' for k, n in resumo.items()))

        # === 2. Webdriver (opcional, dry-run) ===
        if o['com_webdriver']:
            self._explorar_wizard(svc, o, saida)
        else:
            self.stdout.write('  (sem --com-webdriver: so a extracao da API foi feita)')

    # ------------------------------------------------------------------
    def _explorar_wizard(self, svc, o, saida):
        """Abre o wizard de conversao e percorre as etapas capturando campos, sem salvar."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from apps.integracoes.services.hubsoft_painel import _botao_xpath

        idp = str(o['id_prospecto'] or '').strip()
        if not idp:
            self.stdout.write(self.style.WARNING('  --com-webdriver exige --id-prospecto; pulando o navegador.'))
            return
        shots = os.path.join(saida, 'screenshots')
        os.makedirs(shots, exist_ok=True)

        driver = self._chrome(headless=not o['com_janela'])
        etapas = []
        try:
            self._login(driver, svc, _botao_xpath)
            self.stdout.write('  login no painel ok; abrindo Prospectos...')
            wait = WebDriverWait(driver, 25)

            # Prospectos: navega pela URL direta (menos fragil que clicar no menu)
            driver.get(f'{svc.painel_url}/#!/cliente/prospecto')
            time.sleep(4)
            driver.save_screenshot(os.path.join(shots, '01_prospectos.png'))

            # busca pelo id do prospecto
            try:
                campo = wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input[ng-model*='busca'], input[type='search'], input[placeholder*='usca']")))
                campo.clear(); campo.send_keys(idp)
                from selenium.webdriver.common.keys import Keys
                campo.send_keys(Keys.ENTER); time.sleep(3)
            except Exception as e:
                self.stdout.write(f'  (busca nao localizada: {e})')
            driver.save_screenshot(os.path.join(shots, '02_busca.png'))

            # abre menu Acoes -> Converter em Cliente (busca generica por texto)
            abriu = self._abrir_converter(driver, wait)
            if not abriu:
                self.stdout.write(self.style.WARNING(
                    '  nao consegui abrir "Converter em Cliente" automaticamente. '
                    'Screenshots salvos; abra manualmente com --com-janela pra eu capturar as etapas.'))
            time.sleep(3)

            # percorre as etapas do wizard capturando campos
            for i in range(1, 8):
                campos = self._campos_visiveis(driver)
                if campos:
                    etapas.append({'etapa': i, 'campos': campos})
                driver.save_screenshot(os.path.join(shots, f'wizard_{i:02d}.png'))
                self.stdout.write(f'  etapa {i}: {len(campos)} campos capturados')
                if not self._avancar(driver, wait, _botao_xpath):
                    self.stdout.write(f'  etapa {i}: sem botao de avancar (fim ou etapa de SALVAR). Parando ANTES de salvar.')
                    break
                time.sleep(2)

            json.dump(etapas, open(os.path.join(saida, 'wizard_campos.json'), 'w'),
                      ensure_ascii=False, indent=1)
            self.stdout.write(self.style.SUCCESS(
                f'  wizard: {len(etapas)} etapas capturadas (sem salvar) -> {saida}/wizard_campos.json'))
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    def _chrome(self, *, headless):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        opts = Options()
        if headless:
            opts.add_argument('--headless=new')
        for a in ('--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900', '--disable-gpu'):
            opts.add_argument(a)
        return webdriver.Chrome(options=opts)

    def _login(self, driver, svc, botao_xpath):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        driver.get(f'{svc.painel_url}/login')
        wait = WebDriverWait(driver, 30)
        email = wait.until(EC.presence_of_element_located((By.NAME, 'email')))
        email.clear(); email.send_keys(svc.integracao.client_id); time.sleep(0.8)
        try:
            WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, botao_xpath('validar')))).click()
        except Exception:
            pass
        pwd = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']")))
        pwd.clear(); pwd.send_keys(svc.integracao.client_secret); time.sleep(0.8)
        wait.until(EC.element_to_be_clickable((By.XPATH, botao_xpath('entrar')))).click()
        fim = time.time() + 30
        while time.time() < fim and '/login' in (driver.current_url or ''):
            time.sleep(0.5)
        time.sleep(2)

    def _abrir_converter(self, driver, wait):
        from selenium.webdriver.common.by import By
        for xp in ("//button[contains(.,'Ações') or contains(.,'Acoes')]",
                   "//*[contains(@aria-label,'Ações') or contains(@aria-label,'menu')]"):
            try:
                els = driver.find_elements(By.XPATH, xp)
                if els:
                    driver.execute_script("arguments[0].click();", els[0]); time.sleep(1.5)
                    break
            except Exception:
                continue
        try:
            alvo = driver.find_element(By.XPATH, "//*[contains(translate(.,'CONVERTER','converter'),'converter em cliente')]")
            driver.execute_script("arguments[0].click();", alvo); time.sleep(2)
            return True
        except Exception:
            return False

    def _campos_visiveis(self, driver):
        """Enumera inputs/selects/textarea visiveis (nome, tipo, label, valor)."""
        js = r'''
        const out=[];
        document.querySelectorAll('input,select,textarea,md-select').forEach(el=>{
          const r=el.getBoundingClientRect(); if(r.width===0&&r.height===0) return;
          let label='';
          const id=el.id; if(id){const l=document.querySelector("label[for='"+id+"']"); if(l)label=l.innerText;}
          if(!label){const p=el.closest('md-input-container,.form-group,.field'); if(p){const l=p.querySelector('label'); if(l)label=l.innerText;}}
          out.push({tag:el.tagName.toLowerCase(), type:el.getAttribute('type')||'',
                    name:el.getAttribute('name')||el.getAttribute('ng-model')||el.getAttribute('aria-label')||'',
                    label:(label||'').trim().slice(0,60), value:(el.value||'').slice(0,40),
                    required:el.required||el.getAttribute('aria-required')==='true'});
        });
        return out;'''
        try:
            return driver.execute_script(js)
        except Exception:
            return []

    def _avancar(self, driver, wait, botao_xpath):
        """Clica um botao de avancar (nunca SALVAR/FINALIZAR). Retorna se avancou."""
        from selenium.webdriver.common.by import By
        for termo in ('avançar', 'avancar', 'próximo', 'proximo', 'continuar'):
            try:
                els = driver.find_elements(By.XPATH, botao_xpath(termo))
                vis = [e for e in els if e.is_displayed() and e.is_enabled()]
                if vis:
                    driver.execute_script("arguments[0].click();", vis[-1]); time.sleep(1.5)
                    return True
            except Exception:
                continue
        return False
