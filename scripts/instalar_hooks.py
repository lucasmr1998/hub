"""
Instala os git hooks do projeto em .git/hooks/.

Uso:
    python scripts/instalar_hooks.py

Os hooks ficam fora do controle de versao (diretorio .git/), entao cada dev
precisa rodar este script uma vez ao clonar o repo.
"""
import os
import stat
import sys


HOOKS = {
    'pre-commit': '''#!/bin/sh
# Pre-commit hook: verifica se modulos foram alterados sem atualizacao da doc.
# Nao bloqueia o commit — apenas avisa.

python scripts/verificar_docs.py --staged
exit 0
''',
    'pre-push': '''#!/bin/sh
# Pre-push: bloqueia push se houver migrations untracked ou com parent
# ausente. Sistema em prod auto-aplica migrate no rebuild — parent faltando
# derruba container (incidente 31/05/2026).
# Bypass: git push --no-verify
python scripts/check_migrations_safety.py
''',
}


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hooks_dir = os.path.join(repo_root, '.git', 'hooks')

    if not os.path.isdir(hooks_dir):
        print(f'ERRO: {hooks_dir} nao existe. Rode este script dentro do repo git.')
        return 1

    for nome, conteudo in HOOKS.items():
        caminho = os.path.join(hooks_dir, nome)
        with open(caminho, 'w', encoding='utf-8', newline='\n') as f:
            f.write(conteudo)
        # Tornar executavel (Unix)
        try:
            os.chmod(caminho, os.stat(caminho).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        except Exception:
            pass
        print(f'Hook instalado: {nome}')

    print()
    print('Hooks instalados com sucesso.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
