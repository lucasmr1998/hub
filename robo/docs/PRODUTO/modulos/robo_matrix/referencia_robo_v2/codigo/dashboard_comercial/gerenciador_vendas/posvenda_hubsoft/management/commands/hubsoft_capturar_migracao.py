"""Captura a chamada de API da MIGRAÇÃO (upgrade) do HubSoft.

Roda o fluxo de migração via webdriver COM log de rede (CDP) e clica SALVAR de
verdade — assim captura o endpoint + payload reais da migração, que não estavam
nas capturas anteriores. O resultado vai p/ CapturaAPI + um JSON de referência.

    manage.py hubsoft_capturar_migracao --id <upgrade_id> [--com-janela]

⚠️ Faz uma migração REAL (clica SALVAR). Use um serviço de teste/descartável.
"""
import json
import os
import time

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Captura a API da migração de plano (faz migração REAL com log de rede)'

    def add_arguments(self, parser):
        parser.add_argument('--id', type=int, required=True, help='id do UpgradePlano')
        parser.add_argument('--com-janela', action='store_true')

    def handle(self, *args, **o):
        from posvenda_hubsoft.services.ambiente import preparar_ambiente_webdriver
        preparar_ambiente_webdriver()
        from posvenda_hubsoft.webdriver import main_upgrade_plano as up
        from posvenda_hubsoft.webdriver import main_novo_servico as ns
        from posvenda_hubsoft.api_interna.capturar_apis import (
            configurar_chrome_com_cdp, extrair_requests)
        from selenium.webdriver.support.ui import WebDriverWait

        dados = up.buscar_dados(o['id'])
        self.stdout.write(f'Migrar cs={dados.id_cliente_servico} '
                          f'({dados.plano_atual_titulo!r}) → {dados.plano_novo_titulo!r}')

        usuario, senha = os.environ['USUARIO'], os.environ['SENHA']
        driver = configurar_chrome_com_cdp(headless=not o['com_janela'])
        wait = WebDriverWait(driver, ns.TIMEOUT_PADRAO)
        try:
            ns.fazer_login(driver, wait, usuario, senha)
            up.abrir_servico(driver, wait, dados.id_cliente_hubsoft)
            up.fechar_pesquisa_nps(driver)
            up.localizar_card_servico(driver, wait, dados.id_cliente_servico)
            up.abrir_menu_acoes_do_servico(driver, wait, dados.id_cliente_servico)
            up.clicar_migrar_para_outro_servico(driver, wait)
            up.fechar_pesquisa_nps(driver)
            ns.selecionar_plano(driver, wait, dados.plano_novo_titulo)
            ns.selecionar_vendedor(driver, wait, 'Venda-Automática-Matrix')
            up.ativar_switch_migracao_imediata(driver, wait)
            for i in range(6):
                ns.clicar_avancar(driver, wait, f'cap {i+1}/6')
            driver.get_log('performance')  # limpa logs antes do SALVAR
            self.stdout.write(self.style.WARNING('Clicando SALVAR (migração REAL)...'))
            ns.clicar_salvar(driver, wait)
            time.sleep(6)   # deixa a chamada de rede acontecer

            reqs = extrair_requests(driver)
            # candidatos: POST/PUT em /api/v1/cliente/servico*
            cands = [r for r in reqs
                     if r.get('method') in ('POST', 'PUT')
                     and '/api/v1/cliente/servico' in r.get('url', '')]
            self.stdout.write(self.style.SUCCESS(f'{len(cands)} chamada(s) de migração capturada(s):'))
            from posvenda_hubsoft.models import CapturaAPI
            saida = []
            for r in cands:
                # tenta o postData completo via CDP (o do log pode vir truncado)
                body = r.get('post_data', '')
                try:
                    full = driver.execute_cdp_cmd(
                        'Network.getRequestPostData', {'requestId': r['request_id']})
                    if full.get('postData'):
                        body = full['postData']
                except Exception:
                    pass
                self.stdout.write(f"  {r['method']} {r['url']}  (status {r.get('status')}, body {len(body)}b)")
                try:
                    body_json = json.loads(body) if body else {}
                except Exception:
                    body_json = {'_raw': body[:2000]}
                CapturaAPI.objects.create(
                    processo='upgrade', registro_id=o['id'], metodo=r['method'],
                    endpoint=r['url'][:255], payload=body_json,
                    status_code=r.get('status'))
                saida.append({'method': r['method'], 'url': r['url'],
                              'status': r.get('status'), 'payload': body_json})
            destino = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   '..', 'api_interna', 'templates', 'migracao_capturada.json')
            with open(os.path.abspath(destino), 'w') as f:
                json.dump(saida, f, indent=2, ensure_ascii=False)
            self.stdout.write(self.style.SUCCESS(f'salvo em {os.path.abspath(destino)}'))
        finally:
            try:
                driver.quit()
            except Exception:
                pass
