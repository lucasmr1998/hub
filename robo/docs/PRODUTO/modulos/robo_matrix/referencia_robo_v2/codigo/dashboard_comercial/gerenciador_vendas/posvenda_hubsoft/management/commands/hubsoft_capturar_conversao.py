"""Captura a API da CONVERSÃO prospecto→cliente no painel HubSoft (via CDP).

Porta a navegação do webdriver de produção (main_refatorado.py): login →
Prospectos → busca → Ações → "Converter em Cliente" → wizard (boleto/endereço/
grupo Varejo/banco Itau/avançar.../SALVAR) e grava o POST /api/v1/cliente.

    manage.py hubsoft_capturar_conversao --nome "Martin..." --id-prospecto 3679 [--com-janela]

⚠️ Faz uma conversão REAL (clica SALVAR). Use um prospecto de teste.
"""
import json
import os
import time

from django.core.management.base import BaseCommand

SHOT = '/tmp/claude-1000/-home-darlan-projetos-django-new-robo-v2/c175167c-e9f0-403e-b5e7-a2d50e1fef47/scratchpad'
WZ = "/html/body/div[5]/md-dialog/md-dialog-content/div/hubsoft-cliente-wizard"
BTN_NEXT = WZ + "/div[2]/md-dialog-actions/div[2]/button"


class Command(BaseCommand):
    help = 'Captura a API da conversão prospecto→cliente (conversão REAL via wizard)'

    def add_arguments(self, parser):
        parser.add_argument('--nome', required=True)
        parser.add_argument('--id-prospecto', required=True)
        parser.add_argument('--com-janela', action='store_true')

    def handle(self, *args, **o):
        from posvenda_hubsoft.services.ambiente import preparar_ambiente_webdriver
        preparar_ambiente_webdriver()
        os.environ['USUARIO'] = os.environ.get('HUBSOFT_PAINEL_USUARIO', '')
        os.environ['SENHA'] = os.environ.get('HUBSOFT_PAINEL_SENHA', '')
        from posvenda_hubsoft.webdriver.main_novo_servico import fazer_login
        from posvenda_hubsoft.api_interna.capturar_apis import (
            configurar_chrome_com_cdp, extrair_requests)
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys

        nome, idp = o['nome'], str(o['id_prospecto'])
        d = configurar_chrome_com_cdp(headless=not o['com_janela'])
        w = WebDriverWait(d, 20)

        def click(xp, t=1.0):
            el = w.until(EC.element_to_be_clickable((By.XPATH, xp)))
            d.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            d.execute_script("arguments[0].click();", el)
            time.sleep(t)
            return el

        def next_btn(t=2.5):
            time.sleep(1.5)
            click(BTN_NEXT, t)

        try:
            fazer_login(d, w, os.environ['USUARIO'], os.environ['SENHA'])
            time.sleep(2)
            # ETAPA 2: menu Cliente → Prospectos
            click("//i[contains(@class,'icon-chevron-right') and contains(@class,'arrow')]")
            click("//span[@class='title ng-scope ng-binding flex' and contains(text(),'Prospectos')]//parent::a", 2.5)
            # ETAPA 3: busca por nome
            busca = w.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[ng-model='vm.filtros.busca']")))
            busca.clear(); busca.send_keys(nome); busca.send_keys(Keys.ENTER)
            time.sleep(3)
            d.save_screenshot(f'{SHOT}/conv_lista.png')
            # ETAPA 4: Ações na linha do prospecto → Converter em Cliente
            click(f"//tr[.//td[normalize-space(.)='{idp}']]/descendant::button"
                  "[@aria-label='Open menu with custom trigger' and .//span[normalize-space(.)='Ações']]")
            self.stdout.write('  menu Ações aberto')
            # ETAPA 5: Converter em Cliente
            click("//span[@style='color:green' and contains(text(),'Converter em Cliente')]", 3)
            self.stdout.write('  wizard iniciado')
            d.save_screenshot(f'{SHOT}/conv_wizard1.png')

            # ETAPA 6: boleto
            click(WZ + "/div[1]/div/hubsoft-accordion/div[2]/hubsoft-accordion-content/div/form/div/div[6]/md-input-container[1]/md-select")
            click("//md-option[contains(.,'Boleto Digital')]")
            next_btn(); next_btn()
            d.save_screenshot(f'{SHOT}/conv_wizard2.png')

            # ETAPA 7: endereço + grupo Varejo
            time.sleep(2)
            click(WZ + "/div[1]/div/div/form/div/md-input-container/md-select", 2)
            click("/html/body/div[7]/md-select-menu/md-content/md-option", 2)
            click(WZ + "/div[1]/div/div/form/div/div[2]/md-input-container[2]/md-select", 2)
            click("//div[8]//md-option[.//div[contains(@class,'md-text') and normalize-space(text())='Varejo']]", 3)
            next_btn(); next_btn()
            d.save_screenshot(f'{SHOT}/conv_wizard3.png')

            # ETAPA 8: banco
            time.sleep(2)
            click(WZ + "/div[1]/div/form/div[1]/div/hubsoft-select-virtual-repeat/md-input-container/md-select", 3)
            click("//button[@aria-label='BANCO ITAU']", 3)
            d.save_screenshot(f'{SHOT}/conv_wizard4.png')

            # ETAPA 9 + 10: avançar + SALVAR
            next_btn(); next_btn()
            d.get_log('performance')  # limpa antes do SALVAR
            self.stdout.write(self.style.WARNING('clicando SALVAR (conversão REAL)...'))
            click(WZ + "/div[2]/md-dialog-actions/div[2]/div/button", 6)

            reqs = extrair_requests(d)
            cands = [r for r in reqs if r.get('method') in ('POST', 'PUT')
                     and ('/cliente' in r.get('url', '') and 'servico' not in r.get('url', ''))]
            self.stdout.write(self.style.SUCCESS(f'{len(cands)} chamada(s) de cliente capturada(s):'))
            saida = []
            for r in cands:
                body = r.get('post_data', '')
                try:
                    full = d.execute_cdp_cmd('Network.getRequestPostData', {'requestId': r['request_id']})
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
            with open(f'{SHOT}/conversao_capturada.json', 'w') as f:
                json.dump(saida, f, indent=2, ensure_ascii=False)
            self.stdout.write(f'  salvo em {SHOT}/conversao_capturada.json')
        finally:
            try:
                d.quit()
            except Exception:
                pass
