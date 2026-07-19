"""Abre o editor de checklist e captura ERROS DE CONSOLE do navegador.

O botao editar de cada item e um onclick que chama `window.editarItem`. Se o JS
quebra antes de definir essa funcao, o botao fica inerte sem nenhum aviso na tela.
"""
from tests.e2e.base import E2ESession


def run():
    with E2ESession("checklist_editar_console", headless=True, slow_mo=100) as s:
        erros = []
        s.page.on('console', lambda m: erros.append(f'[{m.type}] {m.text}') if m.type == 'error' else None)
        s.page.on('pageerror', lambda e: erros.append(f'[pageerror] {e}'))

        s.login()
        s.goto("/workspace/checklists/")
        s.page.wait_for_timeout(1200)
        s.shot("01_lista")

        # abre o primeiro checklist pelo link de editar
        link = s.page.query_selector("a[href*='/editar/']")
        if not link:
            print('  !! nenhum link de editar na lista (pode_editar falso?)')
            return
        link.click()
        s.page.wait_for_timeout(2000)
        s.shot("02_editor")
        print('  url apos clicar em editar:', s.page.url)

        # a funcao existe no escopo global?
        existe = s.page.evaluate("typeof window.editarItem")
        print('  typeof window.editarItem =', existe)

        # tenta clicar no botao editar do primeiro item
        botao = s.page.query_selector("button[onclick^='editarItem']")
        if botao:
            botao.click()
            s.page.wait_for_timeout(900)
            s.shot("03_apos_clique_editar")
            visivel = s.page.evaluate(
                "(() => { const m = document.getElementById('modal-item');"
                " return m ? getComputedStyle(m).display : 'sem modal'; })()")
            print('  display do modal apos clique:', visivel)
        else:
            print('  !! nenhum botao editarItem encontrado')

        print('\n  ERROS DE CONSOLE:', erros if erros else '(nenhum)')
        print(f"\nScreenshots: {s.out_dir}")


if __name__ == "__main__":
    run()
