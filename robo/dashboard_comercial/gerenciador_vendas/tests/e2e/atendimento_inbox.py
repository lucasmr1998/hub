"""
E2E: Modulo Atendimento — Inbox (4 paginas)

Paginas cobertas:
  /inbox/               — lista de conversas
  /inbox/configuracoes/ — canais, filas, equipes
  /inbox/dashboard/     — metricas
  /inbox/csat/          — dashboard satisfacao

Rodando:
    python tests/e2e/atendimento_inbox.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gerenciador_vendas.settings_local")
import django; django.setup()

from tests.e2e.base import E2ESession

PAGINAS = [
    ("/inbox/",               "inbox_lista",         ".inbox-container"),
    ("/inbox/configuracoes/", "inbox_configuracoes", "h1, h2, .page-title, main"),
    ("/inbox/dashboard/",     "inbox_dashboard",     "main"),
    ("/inbox/csat/",          "inbox_csat",          "main"),
]

def run():
    print("\n=== E2E: Atendimento — Inbox ===\n")
    erros = []

    with E2ESession("atendimento_inbox", headless=True, slow_mo=200) as s:
        s.login()
        s.shot("00_login")

        for path, nome, seletor in PAGINAS:
            try:
                s.goto(path)
                s.page.wait_for_selector(seletor, timeout=8000)
                s.shot(nome)
                print(f"  OK {path}")
            except Exception as e:
                s.shot(f"{nome}_ERRO")
                print(f"  ERRO {path}: {e}")
                erros.append(path)

    if erros:
        print(f"\n  {len(erros)} pagina(s) com erro: {erros}")
        sys.exit(1)
    print(f"\n  Todas as {len(PAGINAS)} paginas OK\n")

if __name__ == "__main__":
    run()
