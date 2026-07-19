"""Captura/explora o fluxo de FINALIZAR ORDEM DE SERVIÇO no painel HubSoft.

Navega a lista de atendimentos (busca por protocolo), abre o menu de ações e
(modo --explorar) lista as opções; (modo capturar) clica em finalizar O.S.,
preenche o dialog, SALVA de verdade e grava as chamadas de rede via CDP.

    manage.py hubsoft_capturar_fechar_os --protocolo 2026... [--explorar] [--com-janela]

Usa a conta admin (HUBSOFT_PAINEL_ADMIN_*). Em modo captura faz finalização REAL.
"""
import json
import os
import time

from django.core.management.base import BaseCommand

SHOT = '/tmp/claude-1000/-home-darlan-projetos-django-new-robo-v2/c175167c-e9f0-403e-b5e7-a2d50e1fef47/scratchpad'


class Command(BaseCommand):
    help = 'Captura o fluxo de finalizar O.S. no painel HubSoft'

    def add_arguments(self, parser):
        parser.add_argument('--protocolo', required=True)
        parser.add_argument('--explorar', action='store_true',
                            help='só lista as opções do menu de ações (não finaliza)')
        parser.add_argument('--com-janela', action='store_true')

    def handle(self, *args, **o):
        from posvenda_hubsoft.services.ambiente import preparar_ambiente_webdriver
        preparar_ambiente_webdriver()
        os.environ['USUARIO'] = os.environ.get('HUBSOFT_PAINEL_ADMIN_USUARIO', '')
        os.environ['SENHA'] = os.environ.get('HUBSOFT_PAINEL_ADMIN_SENHA', '')
        from posvenda_hubsoft.webdriver.main_novo_servico import fazer_login, HUBSOFT_URL_BASE
        from posvenda_hubsoft.api_interna.capturar_apis import (
            configurar_chrome_com_cdp, extrair_requests)
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By

        proto = o['protocolo']
        driver = configurar_chrome_com_cdp(headless=not o['com_janela'])
        wait = WebDriverWait(driver, 30)
        try:
            fazer_login(driver, wait, os.environ['USUARIO'], os.environ['SENHA'])
            driver.get(f'{HUBSOFT_URL_BASE}/atendimento_os/ordem_servico')
            WebDriverWait(driver, 30).until(lambda d: 'ordem_servico' in d.current_url.lower())
            time.sleep(3)

            # busca: primeiro input de texto visível da tela
            from selenium.webdriver.common.keys import Keys
            inp = None
            for cand in driver.find_elements(By.XPATH, "//md-input-container//input | //input[@type='text']"):
                if cand.is_displayed():
                    inp = cand; break
            if inp:
                inp.click(); inp.send_keys(Keys.CONTROL, 'a'); inp.send_keys(Keys.DELETE)
                inp.send_keys(proto); time.sleep(3)
                self.stdout.write(f'  protocolo {proto} digitado na lista de O.S.')
            else:
                self.stdout.write('  (input de busca não encontrado — listando tudo)')
            driver.save_screenshot(f'{SHOT}/os_lista.png')

            # kebab/menu de ações da 1ª linha (genérico)
            btn = None
            for cand in driver.find_elements(By.XPATH, "//table//tbody//tr//md-menu/button | //table//tbody//tr//button[md-icon]"):
                if cand.is_displayed():
                    btn = cand; break
            if not btn:
                self.stdout.write(self.style.ERROR('menu de ações da O.S. não encontrado'))
                driver.save_screenshot(f'{SHOT}/os_sem_menu.png'); return
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            btn.click()
            time.sleep(1.5)

            items = driver.find_elements(By.XPATH, "//md-menu-content//md-menu-item")
            opcoes = []
            for it in items:
                try:
                    if it.is_displayed() and (it.text or '').strip():
                        opcoes.append(it.text.strip())
                except Exception:
                    pass
            self.stdout.write(self.style.SUCCESS(f'OPÇÕES DO MENU DE AÇÕES ({len(opcoes)}):'))
            for op in opcoes:
                self.stdout.write(f'   • {op!r}')
            driver.save_screenshot(f'{SHOT}/os_menu_acoes.png')
            self.stdout.write(f'  screenshot: {SHOT}/os_menu_acoes.png')

            if o['explorar']:
                return

            # modo captura: clica em "Fechar OS"
            alvo = None
            for it in items:
                tl = (it.text or '').strip().lower()
                if 'fechar' in tl and 'os' in tl:
                    alvo = it; break
            if not alvo:
                self.stdout.write(self.style.ERROR('opção "Fechar OS" não encontrada no menu'))
                return
            self.stdout.write(f'  clicando: {alvo.text.strip()!r}')
            alvo.find_element(By.TAG_NAME, 'button').click()
            time.sleep(2.5)
            dialog = driver.find_element(By.XPATH, "//md-dialog")
            hoje = time.strftime('%d/%m/%Y')

            # datas de execução (md-datepicker) → hoje
            for dp in dialog.find_elements(By.XPATH, ".//md-datepicker//input"):
                if dp.is_displayed():
                    dp.click(); dp.send_keys(Keys.CONTROL, 'a'); dp.send_keys(Keys.DELETE)
                    dp.send_keys(hoje); dp.send_keys(Keys.TAB); time.sleep(0.4)
            self.stdout.write(f'  datas preenchidas ({hoje})')

            # Motivo de Fechamento (hubsoft-select-virtual-repeat com busca) → "OS CONCLUÍDA"
            MOTIVO = 'OS CONCLUÍDA'
            from selenium.webdriver.common.action_chains import ActionChains
            for sel in dialog.find_elements(By.XPATH, ".//md-select"):
                if not sel.is_displayed() or (sel.text or '').strip():
                    continue  # pula os já preenchidos (status/utilização)
                sel.click(); time.sleep(1)
                si = [i for i in driver.find_elements(By.XPATH,
                    "//input[@type='search'] | //hubsoft-select-virtual-repeat//input | //md-select-menu//input")
                    if i.is_displayed()]
                if si:
                    si[-1].click(); si[-1].send_keys(MOTIVO[:12]); time.sleep(1.2)
                for el in driver.find_elements(By.XPATH, f"//*[normalize-space(text())='{MOTIVO}']"):
                    if not el.is_displayed():
                        continue
                    clk = driver.execute_script(
                        "var e=arguments[0];while(e&&e!==document.body){if(e.tagName==='MD-LIST-ITEM'||e.tagName==='MD-OPTION'||(e.hasAttribute&&(e.hasAttribute('ng-click')||e.getAttribute('role')==='option')))return e;e=e.parentElement;}return arguments[0];", el)
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", clk)
                    try:
                        ActionChains(driver).move_to_element(clk).pause(0.2).click().perform()
                    except Exception:
                        clk.click()
                    break
                time.sleep(1); break
            self.stdout.write(f'  motivo selecionado ({MOTIVO})')

            # Descrição do Fechamento
            for ta in dialog.find_elements(By.XPATH, ".//textarea"):
                if ta.is_displayed():
                    ta.click(); ta.send_keys('O.S. de instalação aberta indevidamente (teste).')
                    break
            driver.save_screenshot(f'{SHOT}/os_dialog_preenchido.png')

            driver.get_log('performance')  # limpa antes do submit
            # botão FECHAR OS
            btn_fechar = None
            for b in dialog.find_elements(By.XPATH, ".//button"):
                if b.is_displayed() and 'fechar os' in (b.text or '').strip().lower():
                    btn_fechar = b; break
            if not btn_fechar:
                self.stdout.write(self.style.ERROR('botão FECHAR OS não encontrado'))
                return
            self.stdout.write(self.style.WARNING('clicando FECHAR OS (REAL)...'))
            driver.execute_script("arguments[0].click();", btn_fechar)
            time.sleep(6)

            reqs = extrair_requests(driver)
            cands = [r for r in reqs if r.get('method') in ('POST', 'PUT')
                     and 'ordem_servico' in r.get('url', '')]
            self.stdout.write(self.style.SUCCESS(f'{len(cands)} chamada(s) de fechar OS:'))
            saida = []
            for r in cands:
                body = r.get('post_data', '')
                try:
                    full = driver.execute_cdp_cmd('Network.getRequestPostData',
                                                  {'requestId': r['request_id']})
                    if full.get('postData'):
                        body = full['postData']
                except Exception:
                    pass
                self.stdout.write(f"  {r['method']} {r['url']} (status {r.get('status')}, body {len(body)}b)")
                try:
                    bj = json.loads(body) if body else {}
                except Exception:
                    bj = {'_raw': body[:2000]}
                saida.append({'method': r['method'], 'url': r['url'],
                              'status': r.get('status'), 'payload': bj})
            with open(f'{SHOT}/fechar_os_capturada.json', 'w') as f:
                json.dump(saida, f, indent=2, ensure_ascii=False)
            self.stdout.write(f'  salvo em {SHOT}/fechar_os_capturada.json')
        finally:
            try:
                driver.quit()
            except Exception:
                pass
