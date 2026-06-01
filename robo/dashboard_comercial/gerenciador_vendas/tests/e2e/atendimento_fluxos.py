"""
E2E: Modulo Atendimento — Fluxos e Sessoes (5 paginas)

Paginas cobertas:
  /configuracoes/fluxos/              — lista de fluxos
  /configuracoes/fluxos/13/editor/    — editor visual
  /configuracoes/sessoes/             — sessoes ativas
  /configuracoes/sessoes/137/         — detalhe sessao
  /configuracoes/sessoes/137/debug/   — debug sessao

Rodando:
    python tests/e2e/atendimento_fluxos.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gerenciador_vendas.settings_local")
import django; django.setup()

from tests.e2e.base import E2ESession

# Busca IDs reais do banco
def get_ids():
    from apps.comercial.atendimento.models import FluxoAtendimento, AtendimentoFluxo
    from apps.sistema.models import Tenant
    t = Tenant.objects.get(id=3)
    fluxo = FluxoAtendimento.objects.filter(tenant=t).first()
    sessao = AtendimentoFluxo.all_tenants.filter(tenant=t).first()
    return (fluxo.id if fluxo else 13), (sessao.id if sessao else 137)

def run():
    print("\n=== E2E: Atendimento — Fluxos e Sessoes ===\n")
    fluxo_id, sessao_id = get_ids()

    paginas = [
        ("/configuracoes/fluxos/",                    "fluxos_lista",      "main"),
        (f"/configuracoes/fluxos/{fluxo_id}/editor/", "fluxos_editor",     "body"),
        ("/configuracoes/sessoes/",                   "sessoes_lista",     "main"),
        (f"/configuracoes/sessoes/{sessao_id}/",      "sessao_detalhe",    "main"),
        (f"/configuracoes/sessoes/{sessao_id}/debug/","sessao_debug",      "main"),
    ]

    erros = []
    with E2ESession("atendimento_fluxos", headless=True, slow_mo=200) as s:
        s.login()
        s.shot("00_login")

        for path, nome, seletor in paginas:
            try:
                s.goto(path)
                s.page.wait_for_selector(seletor, timeout=10000)
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
