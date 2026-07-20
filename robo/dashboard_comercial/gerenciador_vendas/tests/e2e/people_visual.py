"""Captura visual do modulo People pra auditoria de UX contra o Design System.
Desktop + mobile. Zero toque em prod (roda no aurora_dev local).

Usa um usuario proprio (`e2e_people`) em vez do admin do dev: trocar a senha da
conta que a pessoa usa pra logar, so pra rodar screenshot, seria efeito
colateral. Crie com:

    python manage.py shell --settings=gerenciador_vendas.settings_local -c "..."

ou rode com E2E_EMAIL e E2E_PASS apontando pra outra conta.

A query do token acontece ANTES de abrir o Playwright: chamar o ORM de dentro do
contexto sync dele levanta SynchronousOnlyOperation.
"""
import os
import pathlib
import sys

from tests.e2e.base import BASE_URL, E2ESession

# Este e o unico script de e2e que consulta o ORM (pra achar o token do link
# publico), entao o bootstrap do Django mora aqui e nao no base.py compartilhado.
RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gerenciador_vendas.settings_local')


def _token_do_link():
    """Resolvido antes do browser subir, por causa do SynchronousOnlyOperation."""
    import django
    django.setup()

    from apps.people.models import LinkCadastroUnidade
    link = LinkCadastroUnidade.all_tenants.filter(ativo=True).first()
    return link.token if link else None


def run():
    token = _token_do_link()

    with E2ESession("people_visual", headless=True, slow_mo=120) as s:
        s.login()

        # Confere que autenticou antes de gastar 20 capturas com a tela de login
        s.goto("/people/")
        s.page.wait_for_timeout(1000)
        if '/login' in s.page.url:
            raise RuntimeError(
                'Login falhou. Confira E2E_EMAIL e E2E_PASS: a conta precisa '
                'existir no dev e o tenant dela precisa de modulo_people=True.')
        print(f'  Autenticado, em {s.page.url}')

        s.shot("01_board")
        _fullpage(s, "02_board_fullpage")

        # Modal dos tres pontos de entrada
        try:
            s.page.click("button:has-text('Novo colaborador')", timeout=5000)
            s.page.wait_for_timeout(700)
            s.shot("03_modal_ponto_entrada")
            s.page.keyboard.press("Escape")
            s.page.wait_for_timeout(300)
        except Exception as e:
            print(f"  [aviso] modal de entrada: {str(e)[:80]}")

        s.goto("/people/colaboradores/novo/?entrada=ja_trabalhando")
        s.page.wait_for_timeout(900)
        _fullpage(s, "04_colaborador_form")

        # Ficha, as tres abas
        s.goto("/people/")
        s.page.wait_for_timeout(800)
        try:
            s.page.click(".kanban-card >> nth=0", timeout=5000)
            s.page.wait_for_load_state("networkidle")
            s.page.wait_for_timeout(900)
            s.shot("05_ficha_resumo")

            s.page.click("button[data-tab='aba-dados']")
            s.page.wait_for_timeout(500)
            _fullpage(s, "06_ficha_dados")

            s.page.click("button[data-tab='aba-historico']")
            s.page.wait_for_timeout(500)
            s.shot("07_ficha_historico")
        except Exception as e:
            print(f"  [aviso] ficha: {str(e)[:80]}")

        for path, nome in [
            ("/people/unidades/", "08_unidades"),
            ("/people/cargos/", "09_cargos"),
            ("/people/links/", "10_links"),
            ("/people/analises/", "11_analises"),
            ("/people/unidades/nova/", "12_unidade_form"),
            ("/people/cargos/novo/", "13_cargo_form"),
            ("/people/config/", "14_config_home"),
            ("/people/config/fluxo/", "15_config_fluxo"),
            ("/people/config/fluxo/em_experiencia/", "16_config_etapa"),
            ("/people/config/fluxo/em_admissao/mensagem/", "17_config_mensagem"),
            ("/people/config/formularios/", "18_config_templates"),
            ("/people/config/formularios/novo/", "19_config_template_form"),
            ("/people/config/geral/", "20_config_geral"),
        ]:
            s.goto(path)
            s.page.wait_for_timeout(800)
            _fullpage(s, nome)

        # Formulario publico, sem login, no celular e no desktop
        if token:
            ctx = s.page.context.browser.new_context(
                viewport={"width": 390, "height": 844})
            publica = ctx.new_page()
            publica.goto(f"{BASE_URL}/people/publico/{token}/")
            publica.wait_for_load_state("networkidle")
            publica.wait_for_timeout(800)
            _shot_pagina(publica, s.out_dir, "21_publico_mobile")

            publica.set_viewport_size({"width": 1400, "height": 900})
            publica.wait_for_timeout(400)
            _shot_pagina(publica, s.out_dir, "22_publico_desktop")
            ctx.close()
        else:
            print("  [aviso] nenhum link ativo, formulario publico nao capturado")

        # Board no celular
        s.page.set_viewport_size({"width": 390, "height": 844})
        s.goto("/people/")
        s.page.wait_for_timeout(1000)
        _fullpage(s, "23_board_mobile")

        print(f"\nTudo em: {s.out_dir}")
        return s.out_dir


def _fullpage(s, nome):
    caminho = s.out_dir / f"{nome}.png"
    s.page.screenshot(path=str(caminho), full_page=True)
    print(f"  [{nome}] -> {caminho.name}")


def _shot_pagina(page, out_dir, nome):
    caminho = out_dir / f"{nome}.png"
    page.screenshot(path=str(caminho), full_page=True)
    print(f"  [{nome}] -> {caminho.name}")


if __name__ == "__main__":
    run()
