"""
Gera o catalogo de tools dos agentes (robo/docs/PRODUTO/modulos/automacao/TOOLS.md)
a partir do registry em services/ia_tools.py.

Fonte da verdade = codigo; o doc e DERIVADO (nunca editar a mao). Rodar apos
criar/alterar uma tool (a skill criar-tool faz isso). Roda junto do gerar_hub.

    python manage.py gerar_catalogo_tools --settings=gerenciador_vendas.settings_local
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

TIPO_LABEL = {'conhecimento': 'Conhecimento', 'executavel': 'Executavel'}


def _achar_doc():
    """Autodetecta robo/docs/PRODUTO/modulos/automacao subindo do BASE_DIR."""
    base = Path(settings.BASE_DIR)
    for cand in [base, *base.parents]:
        for sub in (cand / 'docs' / 'PRODUTO' / 'modulos' / 'automacao',
                    cand / 'robo' / 'docs' / 'PRODUTO' / 'modulos' / 'automacao'):
            if sub.is_dir():
                return sub / 'TOOLS.md'
    return None


class Command(BaseCommand):
    help = 'Gera o catalogo TOOLS.md a partir do registry de tools (ia_tools.py).'

    def add_arguments(self, parser):
        parser.add_argument('--saida', default=None, help='Caminho do TOOLS.md (padrao: autodetecta)')

    def handle(self, *args, **opts):
        # Importar ia_tools roda os @_tool e popula o registry.
        from apps.automacao.services.ia_tools import catalogo_tools

        tools = catalogo_tools()
        saida = Path(opts['saida']) if opts['saida'] else _achar_doc()
        if saida is None:
            self.stderr.write('pasta do modulo automacao nao encontrada (use --saida)')
            return

        por_cat = {}
        for t in sorted(tools, key=lambda x: (x['categoria'], x['tipo'], x['chave'])):
            por_cat.setdefault(t['categoria'], []).append(t)

        L = [
            '# Catalogo de tools dos agentes',
            '',
            '> GERADO de `apps/automacao/services/ia_tools.py` via',
            '> `python manage.py gerar_catalogo_tools`. **Nao edite a mao** — rode o comando.',
            '> **Antes de criar uma tool nova, procure aqui** se ja existe uma que faca o que voce precisa.',
            '',
            '> `tipo`: **Conhecimento** = le/consulta (read-only) · **Executavel** = faz/escreve (efeito colateral).',
            '',
            f'Total: **{len(tools)} tools** em **{len(por_cat)} categorias**.',
            '',
            '| Categoria | Tools |',
            '|---|---|',
        ]
        for cat in sorted(por_cat):
            chaves = ', '.join(f'`{t["chave"]}`' for t in por_cat[cat])
            L.append(f'| **{cat}** | {chaves} |')
        L.append('')

        for cat in sorted(por_cat):
            L.append(f'## {cat}')
            L.append('')
            for t in por_cat[cat]:
                L.append(f'### `{t["chave"]}` — {TIPO_LABEL.get(t["tipo"], t["tipo"])}')
                L.append('')
                L.append(t['descricao'])
                L.append('')
                params = t['parametros'] or {}
                if params:
                    L.append('| Parametro | Tipo | Obrigatorio | Descricao |')
                    L.append('|---|---|---|---|')
                    for nome, spec in params.items():
                        obr = 'sim' if nome in (t['obrigatorios'] or []) else 'nao'
                        L.append(f'| `{nome}` | {spec.get("type", "?")} | {obr} | {spec.get("description", "")} |')
                else:
                    L.append('_Sem parametros._')
                L.append('')

        saida.write_text('\n'.join(L) + '\n', encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Catalogo gerado: {saida} ({len(tools)} tools).'))
