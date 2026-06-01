"""E2E: CRM Pipeline (tarefa #136)"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gerenciador_vendas.settings_local")
import django; django.setup()
from tests.e2e.base import E2ESession

PAGINAS = [
    ("/crm/",                          "pipeline",           "main"),
    ("/crm/tarefas/",                  "tarefas",            "main"),
    ("/crm/desempenho/",               "desempenho",         "main"),
    ("/crm/metas/",                    "metas",              "main"),
    ("/crm/produtos/",                 "produtos",           "main"),
    ("/crm/automacoes-pipeline/",      "automacoes",         "main"),
    ("/crm/configuracoes/",            "configuracoes",      "main"),
    ("/crm/equipes/",                  "equipes",            "main"),
    ("/crm/relatorios/win-loss/",      "win_loss",           "main"),
]

def run():
    print("\n=== E2E: CRM Pipeline ===\n")
    erros = []
    with E2ESession("crm", headless=True, slow_mo=150) as s:
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
