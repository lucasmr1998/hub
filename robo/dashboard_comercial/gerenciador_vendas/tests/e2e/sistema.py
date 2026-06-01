"""E2E: Sistema — Auth & Configuracoes (tarefa #133)"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gerenciador_vendas.settings_local")
import django; django.setup()
from tests.e2e.base import E2ESession

PAGINAS = [
    ("/login/",                      "login",              "input[name='email']"),
    ("/configuracoes/",              "configuracoes",      "main"),
    ("/configuracoes/usuarios/",     "usuarios",           "main"),
    ("/configuracoes/empresa/",      "empresa",            "main"),
    ("/configuracoes/perfis/",       "perfis",             "main"),
    ("/configuracoes/logs/",         "logs",               "main"),
    ("/configuracoes/recontato/",    "recontato",          "main"),
    ("/perfil/",                     "perfil",             "main"),
    ("/configuracoes/integracoes/",  "integracoes",        "main"),
    ("/configuracoes/notificacoes/", "notificacoes",       "main"),
]

def run():
    print("\n=== E2E: Sistema ===\n")
    erros = []
    with E2ESession("sistema", headless=True, slow_mo=150) as s:
        # Screenshot do login sem estar logado
        s.goto("/login/")
        s.page.wait_for_selector("input[name='email']", timeout=5000)
        s.shot("login_pagina")
        print("  OK /login/")

        s.login()
        for path, nome, sel in PAGINAS[1:]:
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
        print(f"\n  ERROS: {erros}")
        sys.exit(1)
    print(f"\n  Todas as paginas OK\n")

if __name__ == "__main__":
    run()
