"""
E2E: Modulo Atendimento — Suporte (7 paginas)

Paginas cobertas:
  /suporte/                           — dashboard suporte
  /suporte/tickets/                   — lista de tickets
  /suporte/tickets/criar/             — criar ticket
  /suporte/tickets/<id>/              — detalhe ticket
  /suporte/conhecimento/              — base de conhecimento publica
  /suporte/conhecimento/gerenciar/    — gerenciar artigos
  /suporte/conhecimento/perguntas/    — perguntas sem resposta

Rodando:
    python tests/e2e/atendimento_suporte.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gerenciador_vendas.settings_local")
import django; django.setup()

from tests.e2e.base import E2ESession

def get_ticket_id():
    from apps.suporte.models import Ticket
    ticket = Ticket.all_tenants.order_by('-id').first()
    return ticket.id if ticket else 4

def run():
    print("\n=== E2E: Atendimento — Suporte ===\n")
    ticket_id = get_ticket_id()

    paginas = [
        ("/suporte/",                          "suporte_dashboard",     "main"),
        ("/suporte/tickets/",                  "tickets_lista",         "main"),
        ("/suporte/tickets/criar/",            "tickets_criar",         "main"),
        (f"/suporte/tickets/{ticket_id}/",     "ticket_detalhe",        "main"),
        ("/suporte/conhecimento/",             "conhecimento_publico",   "main"),
        ("/suporte/conhecimento/gerenciar/",   "conhecimento_gerenciar", "main"),
        ("/suporte/conhecimento/perguntas/",   "conhecimento_perguntas", "main"),
    ]

    erros = []
    with E2ESession("atendimento_suporte", headless=True, slow_mo=200) as s:
        s.login()
        s.shot("00_login")

        for path, nome, seletor in paginas:
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
    print(f"\n  Todas as {len(paginas)} paginas OK\n")

if __name__ == "__main__":
    run()
