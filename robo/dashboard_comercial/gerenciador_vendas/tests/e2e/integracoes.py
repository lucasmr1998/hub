"""E2E: Integracoes (tarefa #139)"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gerenciador_vendas.settings_local")
import django; django.setup()
from tests.e2e.base import E2ESession

INTEG_ID = 14

PAGINAS = [
    ("/configuracoes/integracoes/",              "integracoes",        "main"),
    ("/configuracoes/integracoes/saude/",        "integ_saude",        "main"),
    ("/configuracoes/integracoes/churn-score/",  "churn_score",        "main"),
    (f"/configuracoes/integracoes/{INTEG_ID}/",  "integ_detalhe",      "main"),
]

def run():
    print("\n=== E2E: Integracoes ===\n")
    erros = []
    with E2ESession("integracoes", headless=True, slow_mo=150) as s:
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
