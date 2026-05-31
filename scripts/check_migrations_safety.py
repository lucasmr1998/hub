#!/usr/bin/env python3
"""Guard pre-push: garante que migrations estao seguras pra subir em prod.

Falha (exit 1) se:
1. Algum arquivo em `migrations/` esta untracked (`??`) ou nao staged.
2. Qualquer migration commitada referencia uma dependency cujo arquivo
   nao esta em `git ls-files` (parent ausente).

Roda automaticamente como `.git/hooks/pre-push`. Pode ser rodado manualmente
pra checar o estado a qualquer momento.

Contexto do incidente que originou: 31/05/2026 uma migration orfa (0013)
ficou untracked entre sessoes paralelas. Migration nova (0014) declarou
dependencia em 0013 — push subiu 0014 sem 0013, container caiu no `migrate
--noinput` do Dockerfile e EasyPanel mostrou 502 em TODOS endpoints
(outage geral, todos tenants).
"""
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

# Apps removidas do INSTALLED_APPS (CLAUDE.md: vendas_web esta morto).
# Migrations dessas apps nao rodam em runtime, entao orphans podem ser ignorados.
SKIP_APPS = {'vendas_web'}


def _run(cmd):
    return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)


def check_untracked_migrations():
    """Falha se houver arquivo `??` ou modificado nao-staged em qualquer pasta migrations/."""
    out = _run(['git', 'status', '--porcelain']).stdout
    problems = []
    for line in out.splitlines():
        # formato porcelain: 'XY path'
        if len(line) < 4:
            continue
        flag = line[:2]
        path = line[3:].strip().strip('"')
        if '/migrations/' not in path and not path.startswith('migrations/'):
            continue
        if not path.endswith('.py'):
            continue
        if path.endswith('__init__.py'):
            continue
        # ?? = untracked; ' M' = unstaged; 'MM' = staged + unstaged mod
        if flag.startswith('?') or flag == ' M' or flag[1] == 'M':
            problems.append(f'  {flag}  {path}')
    return problems


def check_orphan_dependencies():
    """Pra cada migration *.py tracked no git, verifica se cada dependency
    declarada em `dependencies = [...]` aponta pra arquivo que existe no
    git ls-files. Detecta o caso "migration X depende de Y, mas Y nao foi
    commitado ainda" — exatamente o incidente."""
    tracked = _run(['git', 'ls-files', '*migrations/*.py']).stdout.splitlines()
    tracked_paths = [p for p in tracked if not p.endswith('__init__.py')]

    # mapa: (app_label, migration_name_sem_ext) -> path
    known = {}
    for p in tracked_paths:
        m = re.search(r'/([a-z_][a-z0-9_]*)/migrations/([0-9]{4}_[a-zA-Z0-9_]+)\.py$', p)
        if m:
            known[(m.group(1), m.group(2))] = p

    pattern = re.compile(r"\(\s*['\"]([a-z_][a-z0-9_]*)['\"]\s*,\s*['\"]([0-9]{4}_[a-zA-Z0-9_]+)['\"]\s*\)")
    problems = []
    for (app, name), path in known.items():
        if app in SKIP_APPS:
            continue
        try:
            content = (REPO_ROOT / path).read_text(encoding='utf-8')
        except Exception:
            continue
        # extrai bloco dependencies = [...]
        dep_match = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if not dep_match:
            continue
        for dep_app, dep_name in pattern.findall(dep_match.group(1)):
            if dep_app in SKIP_APPS:
                continue
            if (dep_app, dep_name) not in known:
                problems.append(f'  {app}/{name} depende de {dep_app}/{dep_name} (parent ausente em git ls-files)')
    return problems


def main():
    problems_untracked = check_untracked_migrations()
    problems_orphan = check_orphan_dependencies()

    if not problems_untracked and not problems_orphan:
        print('[migrations-safety] OK — sem orphans, sem migrations untracked')
        return 0

    print('[migrations-safety] BLOQUEADO — sistema esta em prod e auto-aplica migrate no rebuild.\n')
    if problems_untracked:
        print('Arquivos em migrations/ nao commitados (resolve antes de pushar):')
        for p in problems_untracked:
            print(p)
        print()
    if problems_orphan:
        print('Migrations apontando pra parent que nao esta no git:')
        for p in problems_orphan:
            print(p)
        print()
    print('Como resolver:')
    print('  - Untracked (??): "git add" + commit, ou "git rm" se nao for usar.')
    print('  - Modificado ( M / MM): "git add" + commit ou stash.')
    print('  - Orphan parent: garante que o parent esta commitado e pushed.')
    print('\nBypass (use APENAS com avaliacao de risco): git push --no-verify')
    return 1


if __name__ == '__main__':
    sys.exit(main())
