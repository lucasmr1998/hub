"""E2E: Marketing (tarefa #138)"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gerenciador_vendas.settings_local")
import django; django.setup()
from tests.e2e.base import E2ESession

PAGINAS = [
    ("/marketing/automacoes/",             "automacoes",       "main"),
    ("/marketing/automacoes/criar/",       "automacao_criar",  "main"),
    ("/marketing/emails/",                 "emails",           "main"),
    ("/marketing/emails/criar/",           "email_criar",      "main"),
    ("/marketing/emails/dominios/",        "dominios",         "main"),
    ("/marketing/segmentos/",              "segmentos",        "main"),
    ("/configuracoes/campanhas/",          "campanhas",        "main"),
]

def run():
    print("\n=== E2E: Marketing ===\n")
    erros = []
    with E2ESession("marketing", headless=True, slow_mo=150) as s:
        s.login()
        for path, nome, sel in PAGINAS:
            try:
                s.goto(path)
                s.page.wait_for_selector(sel, timeout=8000)
                s.shot(nome)
                print(f"  OK {path}")
            except Exception as e:
                s.shot(f"{nome}_ERRO")
                print(f"  ERRO {path}: {e}")
                erros.append(path)
    if erros:
        print(f"\n  ERROS: {erros}"); sys.exit(1)
    print(f"\n  Todas as paginas OK\n")

if __name__ == "__main__":
    run()
