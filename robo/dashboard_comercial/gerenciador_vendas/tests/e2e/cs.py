"""E2E: CS Customer Success (tarefa #137)"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gerenciador_vendas.settings_local")
import django; django.setup()
from tests.e2e.base import E2ESession

PAGINAS = [
    ("/cs/clube/dashboard/",                          "clube_dashboard",    "main"),
    ("/cs/clube/dashboard/participantes/",            "participantes",      "main"),
    ("/cs/clube/dashboard/premios/",                  "premios",            "main"),
    ("/cs/clube/dashboard/banners/",                  "banners",            "main"),
    ("/cs/clube/dashboard/gamificacao/",              "gamificacao",        "main"),
    ("/cs/clube/dashboard/config/",                   "config",             "main"),
    ("/cs/clube/dashboard/relatorios/",               "relatorios",         "main"),
    ("/cs/parceiros/dashboard/parceiros/",            "parceiros",          "main"),
    ("/cs/parceiros/dashboard/cupons/",               "cupons",             "main"),
    ("/cs/indicacoes/dashboard/indicacoes/",          "indicacoes",         "main"),
    ("/cs/carteirinha/dashboard/carteirinha/",        "carteirinha",        "main"),
    ("/cs/retencao/",                                 "retencao",           "main"),
]

def run():
    print("\n=== E2E: CS Customer Success ===\n")
    erros = []
    with E2ESession("cs", headless=True, slow_mo=150) as s:
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
