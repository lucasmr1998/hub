"""
Verifica se arquivos de modulos importantes foram modificados sem atualizacao da doc.

Uso:
    python scripts/verificar_docs.py [--staged]

- Sem --staged: compara HEAD com working tree (mudancas nao commitadas)
- Com --staged: compara HEAD com index (mudancas staged, usado pelo pre-commit)

Regras (modulo → doc esperado):
    apps/comercial/atendimento/  → robo/docs/PRODUTO/13-MODULO_FLUXOS.md ou 14-MODULO_ATENDIMENTO.md
    apps/inbox/                  → robo/docs/PRODUTO/06-INBOX.md
    apps/comercial/crm/          → robo/docs/PRODUTO/07-MODULO_COMERCIAL.md
    apps/comercial/leads/        → robo/docs/PRODUTO/07-MODULO_COMERCIAL.md
    apps/suporte/                → robo/docs/PRODUTO/12-MODULO_SUPORTE.md
    apps/marketing/              → robo/docs/PRODUTO/08-MODULO_MARKETING.md
    apps/cs/                     → robo/docs/PRODUTO/09-MODULO_CS.md
    apps/integracoes/            → robo/docs/PRODUTO/10-INTEGRACOES.md ou 03-INTEGRACOES_HUBSOFT.md
    apps/assistente/             → robo/docs/PRODUTO/17-ASSISTENTE_CRM.md

Exit code:
    0 - tudo ok ou aviso apenas
    1 - sempre, quando ha aviso (mas nao bloqueia commit — hook usa exit 0)
"""
import subprocess
import sys


REGRAS = [
    ('apps/comercial/atendimento/', ['robo/docs/PRODUTO/13-MODULO_FLUXOS.md', 'robo/docs/PRODUTO/14-MODULO_ATENDIMENTO.md']),
    ('apps/inbox/', ['robo/docs/PRODUTO/06-INBOX.md']),
    ('apps/comercial/crm/', ['robo/docs/PRODUTO/07-MODULO_COMERCIAL.md']),
    ('apps/comercial/leads/', ['robo/docs/PRODUTO/07-MODULO_COMERCIAL.md']),
    ('apps/suporte/', ['robo/docs/PRODUTO/12-MODULO_SUPORTE.md']),
    ('apps/marketing/', ['robo/docs/PRODUTO/08-MODULO_MARKETING.md']),
    ('apps/cs/', ['robo/docs/PRODUTO/09-MODULO_CS.md']),
    ('apps/integracoes/', ['robo/docs/PRODUTO/10-INTEGRACOES.md', 'robo/docs/PRODUTO/03-INTEGRACOES_HUBSOFT.md']),
    ('apps/assistente/', ['robo/docs/PRODUTO/17-ASSISTENTE_CRM.md']),
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
