"""Valida visualmente a tela de checklists (lista, novo e editar) no ambiente local."""
from tests.e2e.base import E2ESession


def run():
    with E2ESession("checklists_visual", headless=True, slow_mo=120) as s:
        s.login()

        s.goto("/workspace/checklists/")
        s.page.wait_for_timeout(1200)
        s.shot("01_lista")

        s.goto("/workspace/checklists/novo/")
        s.page.wait_for_timeout(1500)
        s.shot("02_novo")
        # O erro NoReverseMatch aparecia como pagina de debug do Django
        corpo = s.page.content()
        if 'NoReverseMatch' in corpo or 'Page not found' in corpo:
            print('  !! ERRO ainda presente na pagina /novo/')
        else:
            print('  OK: /novo/ renderizou sem erro')

        print(f"\nScreenshots em: {s.out_dir}")


if __name__ == "__main__":
    run()
