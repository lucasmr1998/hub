"""Captura requests HTTP feitas pelo HubSoft durante o cadastro de um cliente.
Usa Chrome DevTools Protocol (CDP) para logar todas as XHR/Fetch.

Uso:
  python capturar_apis.py --linha 1
"""
import argparse
import json
import os
import sys
import time
import logging
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from dotenv import load_dotenv

# Imports usados só pelo main() de migração (CLI antigo) — opcionais.
# configurar_chrome_com_cdp/extrair_requests não dependem deles.
try:
    from main_adicionar_cliente import (  # noqa: F401
        fazer_login, esperar_dashboard, executar, MEGALINK_URL_BASE,
    )
    from processar_csv import linha_csv_para_dados, CSV_PATH_DEFAULT, ler_linha  # noqa: F401
except ImportError:
    pass

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger("captura")


def configurar_chrome_com_cdp(headless: bool = True):
    """Chrome com performance logging para capturar tráfego de rede."""
    options = Options()
    if headless:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    # Habilita CDP performance logging
    options.set_capability(
        'goog:loggingPrefs',
        {'performance': 'ALL', 'browser': 'ALL'}
    )
    options.add_experimental_option('perfLoggingPrefs', {
        'enableNetwork': True,
        'enablePage': False,
    })
    driver = webdriver.Chrome(options=options)
    return driver


def extrair_requests(driver):
    """Lê os perf logs e extrai TODAS as XHR/Fetch chamadas."""
    logs = driver.get_log('performance')
    requests = {}      # requestId -> dados parciais
    finalizadas = []   # lista de requests completas

    for entry in logs:
        try:
            msg = json.loads(entry['message'])['message']
            method = msg.get('method', '')

            if method == 'Network.requestWillBeSent':
                params = msg['params']
                rid = params['requestId']
                req = params['request']
                tipo = params.get('type', '')
                # Pega só XHR/Fetch (ignora HTML, CSS, JS, imagens)
                if tipo not in ('XHR', 'Fetch'):
                    continue
                requests[rid] = {
                    'request_id': rid,
                    'method': req['method'],
                    'url': req['url'],
                    'headers_req': req.get('headers', {}),
                    'post_data': req.get('postData', ''),
                    'tipo': tipo,
                    'timestamp': params.get('timestamp', 0),
                }

            elif method == 'Network.responseReceived':
                params = msg['params']
                rid = params['requestId']
                if rid in requests:
                    resp = params['response']
                    requests[rid]['status'] = resp.get('status', 0)
                    requests[rid]['mime_type'] = resp.get('mimeType', '')
                    requests[rid]['headers_resp'] = resp.get('headers', {})

            elif method == 'Network.loadingFinished':
                rid = msg['params']['requestId']
                if rid in requests:
                    # Tenta pegar o body da resposta
                    try:
                        body = driver.execute_cdp_cmd(
                            'Network.getResponseBody', {'requestId': rid}
                        )
                        requests[rid]['body'] = body.get('body', '')[:5000]
                    except Exception:
                        requests[rid]['body'] = '(falha lendo body)'
                    finalizadas.append(requests.pop(rid))

        except Exception:
            continue

    return finalizadas


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--linha', type=int, default=1)
    p.add_argument('--csv', default=CSV_PATH_DEFAULT)
    p.add_argument('--no-headless', dest='headless', action='store_false', default=True)
    p.add_argument('--salvar', action='store_true', help='Realmente salva o cliente (cria de verdade)')
    args = p.parse_args()

    row = ler_linha(args.csv, args.linha)
    dados, ajustes = linha_csv_para_dados(row, exigir_telefone=False)
    log.info(f"Cliente: {dados.nome} CPF={dados.cpf_cnpj}")

    driver = configurar_chrome_com_cdp(args.headless)
    wait = WebDriverWait(driver, 20)

    usuario = os.environ['USUARIO']
    senha = os.environ['SENHA']

    try:
        log.info("LOGIN...")
        fazer_login(driver, wait, usuario, senha)
        esperar_dashboard(driver)
        time.sleep(2)

        # Limpa logs do login (pra focar no cadastro)
        driver.get_log('performance')

        modo = 'COM SALVAR (real)' if args.salvar else 'dry-run'
        log.info(f"CADASTRO ({modo})...")
        executar(
            dados=dados, headless=args.headless,
            dry_run=not args.salvar, salvar=args.salvar,
            driver_existente=driver, wait_existente=wait,
            ja_logado=True,
        )
        if args.salvar:
            log.info("Aguardando 10s pós-salvar pra capturar todos os requests...")
            time.sleep(10)

        log.info("Capturando requests...")
        reqs = extrair_requests(driver)
        log.info(f"Total requests XHR/Fetch capturadas: {len(reqs)}")

        # Filtra apenas requests pro domínio megalink
        domain = urlparse(MEGALINK_URL_BASE).netloc
        reqs_domain = [r for r in reqs if domain in r.get('url', '')]
        log.info(f"  ({len(reqs_domain)} para {domain})")

        # Agrupa por URL (path) e método
        from collections import Counter
        agrupado = Counter()
        for r in reqs_domain:
            url = r.get('url', '')
            path = urlparse(url).path
            agrupado[(r.get('method', '?'), path)] += 1

        print()
        print('=' * 80)
        print('ENDPOINTS CHAMADOS DURANTE CADASTRO')
        print('=' * 80)
        for (mtd, path), n in agrupado.most_common():
            print(f'  {mtd:6} {path[:75]:75} x{n}')

        # Salva tudo em JSON para análise detalhada
        out = os.path.join(os.path.dirname(__file__), 'apis_capturadas.json')
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(reqs_domain, f, ensure_ascii=False, indent=2)
        print(f'\nDetalhes salvos em: {out}')

        # Resumo dos requests mais interessantes (POST/PUT com body)
        print()
        print('=' * 80)
        print('REQUESTS POST/PUT (que MODIFICAM dados)')
        print('=' * 80)
        for r in reqs_domain:
            mtd = r.get('method', '')
            if mtd in ('POST', 'PUT', 'PATCH', 'DELETE'):
                url = r.get('url', '')
                body = r.get('post_data', '')
                print(f'\n  {mtd} {urlparse(url).path}')
                if body:
                    print(f'    body: {body[:400]}')

    finally:
        try: driver.quit()
        except Exception: pass


if __name__ == '__main__':
    main()
