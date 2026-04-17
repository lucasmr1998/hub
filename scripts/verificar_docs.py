"""
Verifica se arquivos de modulos importantes foram modificados sem atualizacao da doc.

Uso:
    python scripts/verificar_docs.py [--staged]

- Sem --staged: compara HEAD com working tree (mudancas nao commitadas)
- Com --staged: compara HEAD com index (mudancas staged, usado pelo pre-commit)

Regras (modulo → doc esperado):
    apps/comercial/atendimento/  → robo/docs/PRODUTO/modulos/atendimento/ ou modulos/fluxos/
    apps/inbox/                  → robo/docs/PRODUTO/modulos/inbox/
    apps/comercial/crm/          → robo/docs/PRODUTO/modulos/comercial/
    apps/comercial/leads/        → robo/docs/PRODUTO/modulos/comercial/
    apps/suporte/                → robo/docs/PRODUTO/modulos/suporte/
    apps/marketing/              → robo/docs/PRODUTO/modulos/marketing/
    apps/cs/                     → robo/docs/PRODUTO/modulos/cs/
    apps/integracoes/            → robo/docs/PRODUTO/integracoes/
    apps/assistente/             → robo/docs/PRODUTO/modulos/assistente-crm/

Exit code:
    0 - tudo ok ou aviso apenas
    1 - sempre, quando ha aviso (mas nao bloqueia commit — hook usa exit 0)
"""
import subprocess
import sys


REGRAS = [
    ('apps/comercial/atendimento/', ['robo/docs/PRODUTO/modulos/atendimento/', 'robo/docs/PRODUTO/modulos/fluxos/']),
    ('apps/inbox/', ['robo/docs/PRODUTO/modulos/inbox/']),
    ('apps/comercial/crm/', ['robo/docs/PRODUTO/modulos/comercial/']),
    ('apps/comercial/leads/', ['robo/docs/PRODUTO/modulos/comercial/']),
    ('apps/comercial/cadastro/', ['robo/docs/PRODUTO/modulos/comercial/']),
    ('apps/comercial/viabilidade/', ['robo/docs/PRODUTO/modulos/comercial/']),
    ('apps/suporte/', ['robo/docs/PRODUTO/modulos/suporte/']),
    ('apps/marketing/', ['robo/docs/PRODUTO/modulos/marketing/']),
    ('apps/cs/', ['robo/docs/PRODUTO/modulos/cs/']),
    ('apps/integracoes/', ['robo/docs/PRODUTO/integracoes/']),
    ('apps/assistente/', ['robo/docs/PRODUTO/modulos/assistente-crm/']),
]


IGNORAR_SUFIXOS = (
    '/tests/', '/tests.py', '/test_', '/__pycache__/',
    '/migrations/', '.pyc',
)


def arquivos_modificados(staged=False):
    """Retorna lista de arquivos modificados (absolutos relativos ao repo)."""
    if staged:
        cmd = ['git', 'diff', '--cached', '--name-only']
    else:
        cmd = ['git', 'diff', 'HEAD', '--name-only']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except subprocess.CalledProcessError:
        return []


def deve_ignorar(arquivo):
    return any(suf in arquivo for suf in IGNORAR_SUFIXOS)


def verificar(staged=False):
    arquivos = arquivos_modificados(staged=staged)
    if not arquivos:
        return []

    arquivos_normalizados = [a.replace('\\', '/') for a in arquivos]
    arquivos_relevantes = [a for a in arquivos_normalizados if not deve_ignorar(a)]

    avisos = []
    for modulo, docs in REGRAS:
        # Houve mudanca no modulo?
        mod_mudou = any(modulo in a for a in arquivos_relevantes)
        if not mod_mudou:
            continue

        # Alguma doc correspondente foi atualizada?
        doc_atualizada = any(d in a for a in arquivos_normalizados for d in docs)
        if doc_atualizada:
            continue

        avisos.append({
            'modulo': modulo,
            'docs_esperadas': docs,
        })

    return avisos


def main():
    staged = '--staged' in sys.argv
    avisos = verificar(staged=staged)

    if not avisos:
        return 0

    print()
    print('------------------------------------------------------------------')
    print('  AVISO: Mudancas em modulos sem atualizacao da documentacao')
    print('------------------------------------------------------------------')
    print()
    for aviso in avisos:
        print(f'  * {aviso["modulo"]} foi modificado. Esperado atualizar uma destas:')
        for doc in aviso['docs_esperadas']:
            print(f'      - {doc}')
        print()
    print('Atualize a doc antes de commitar, ou prossiga se for uma mudanca que')
    print('nao requer atualizacao (ex: typo, refactor interno).')
    print()
    return 0  # nao bloqueia, so avisa


if __name__ == '__main__':
    sys.exit(main())
