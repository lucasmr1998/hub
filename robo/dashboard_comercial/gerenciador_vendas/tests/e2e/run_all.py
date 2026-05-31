"""
Runner de todos os testes E2E.

Uso:
    # Roda todos (headless):
    python tests/e2e/run_all.py

    # Roda com browser visível (debug):
    E2E_HEADLESS=false python tests/e2e/run_all.py

    # Roda só um script:
    python tests/e2e/inbox_claiming.py
"""

import os
import sys
import importlib
import traceback

HEADLESS = os.environ.get("E2E_HEADLESS", "true").lower() != "false"

SUITES = [
    "inbox_claiming",
]

def main():
    passed, failed = [], []

    print(f"\n{'='*50}")
    print(f"  Hubtrix E2E — {len(SUITES)} suite(s)")
    print(f"  Headless: {HEADLESS}")
    print(f"{'='*50}\n")

    for suite in SUITES:
        try:
            mod = importlib.import_module(f"tests.e2e.{suite}")
            mod.run()
            passed.append(suite)
        except Exception as e:
            print(f"\n  ✗ FALHOU: {suite}")
            traceback.print_exc()
            failed.append(suite)

    print(f"\n{'='*50}")
    print(f"  Resultado: {len(passed)} passou / {len(failed)} falhou")
    if failed:
        print(f"  Falharam: {', '.join(failed)}")
    print(f"{'='*50}\n")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gerenciador_vendas.settings_local")
    import django
    django.setup()
    main()
