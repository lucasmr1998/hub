"""
Importa todos os MD de robo/docs/ pro Workspace, organizados como Drive de empresa.

Estrutura nova: por time, nao mirror do filesystem. Numeracao na raiz forca ordem
visual (Executivo no topo, Tarefas/Reunioes/Agentes no rodape).

Filesystem continua fonte da verdade. Re-rodar sincroniza (idempotente via slug).

Uso:
    python manage.py importar_docs_drive [--tenant 'Aurora HQ'] [--clear] [--dry-run]
"""
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.sistema.models import Tenant
from apps.workspace.models import Documento, PastaDocumento


# ============================================================================
# ESTRUTURA DA EMPRESA
# ============================================================================

# Pastas raiz (ordem importa pra exibicao no Drive)
PASTAS_RAIZ = [
    {'ordem': 1,  'nome': '01. Executivo',          'icone': 'bi-briefcase',          'cor': '#252020'},
    {'ordem': 2,  'nome': '02. Produto',            'icone': 'bi-box-seam',           'cor': '#3a3434'},
    {'ordem': 3,  'nome': '03. Marketing',          'icone': 'bi-megaphone',          'cor': '#E76F51'},
    {'ordem': 4,  'nome': '04. Comercial',          'icone': 'bi-graph-up-arrow',     'cor': '#1A1717'},
    {'ordem': 5,  'nome': '05. Operacoes',          'icone': 'bi-gear-wide-connected','cor': '#475569'},
    {'ordem': 6,  'nome': '06. Sucesso do Cliente', 'icone': 'bi-heart',              'cor': '#94A3B8'},
    {'ordem': 7,  'nome': '07. Tech',               'icone': 'bi-code-slash',         'cor': '#3a3434'},
    {'ordem': 8,  'nome': '08. Clientes',           'icone': 'bi-people-fill',        'cor': '#475569'},
    {'ordem': 9,  'nome': '09. Reunioes',           'icone': 'bi-calendar-event',     'cor': '#94A3B8'},
    {'ordem': 10, 'nome': '10. Tarefas',            'icone': 'bi-check2-square',      'cor': '#475569'},
    {'ordem': 11, 'nome': '11. Agentes IA',         'icone': 'bi-robot',              'cor': '#1A1717'},
]


# ============================================================================
# MAPEAMENTO PATH FILESYSTEM -> PATH NO DRIVE
#
# Formato: ('source_path_pattern', 'dest_drive_path', 'categoria_default')
#   - Se source termina em '.md' = match exato de arquivo
#   - Se source termina em '/'  = prefix (subpaths sao preservados em dest)
# Ordem importa: primeiro match vence (especificos antes de genericos)
# ============================================================================

MAPEAMENTO = [
    # ───── Marketing ─────
    ('BRAND/',                                    '03. Marketing/Brand',                       'regras'),
    ('GTM/01-PESQUISA_MERCADO.md',                '03. Marketing/Pesquisa de mercado',         'estrategia'),
    ('GTM/02-ICP.md',                             '03. Marketing/Pesquisa de mercado',         'estrategia'),
    ('GTM/03-CONCORRENTES.md',                    '03. Marketing/Pesquisa de mercado',         'estrategia'),
    ('GTM/04-PROPOSTA_VALOR.md',                  '03. Marketing/Posicionamento',              'estrategia'),
    ('GTM/05-POSICIONAMENTO.md',                  '03. Marketing/Posicionamento',              'estrategia'),
    ('GTM/06-MENSAGENS_CHAVE.md',                 '03. Marketing/Mensagens-chave',             'estrategia'),
    ('GTM/07-CANAIS.md',                          '03. Marketing/Canais',                      'estrategia'),
    ('GTM/11-MATERIAIS_LANCAMENTO.md',            '03. Marketing/Lancamentos',                 'entrega'),
    ('GTM/posicionamento/',                       '03. Marketing/Posicionamento',              'estrategia'),

    # ───── Comercial ─────
    ('GTM/08-PRECIFICACAO.md',                    '04. Comercial/Precificacao',                'estrategia'),
    ('GTM/09-ENABLEMENT.md',                      '04. Comercial/Enablement',                  'processo'),
    ('GTM/10-ROADMAP_GTM.md',                     '04. Comercial/Enablement',                  'roadmap'),
    ('GTM/12-FLUXO_COMERCIAL.md',                 '04. Comercial/Fluxo comercial',             'processo'),
    ('GTM/13-DIAGNOSTICO.md',                     '04. Comercial/Diagnostico',                 'processo'),
    ('GTM/cases/',                                '04. Comercial/Cases',                       'relatorio'),
    ('GTM/propostas/',                            '04. Comercial/Propostas',                   'entrega'),
    ('OPERACIONAL/materiais/scripts_vendas/',     '04. Comercial/Scripts de venda',            'processo'),
    ('OPERACIONAL/materiais/apresentacao/',       '04. Comercial/Apresentacoes',               'entrega'),
    ('OPERACIONAL/materiais/propostas/',          '04. Comercial/Propostas',                   'entrega'),

    # ───── Executivo ─────
    ('GTM/00-CHECKLIST_GTM.md',                   '01. Executivo/Estrategia',                  'estrategia'),
    ('GTM/00-README.md',                          '01. Executivo/Estrategia',                  'contexto'),

    # ───── Produto ─────
    ('PRODUTO/core/',                             '02. Produto/Core',                          'regras'),
    ('PRODUTO/integracoes/',                      '02. Produto/Integracoes',                   'processo'),
    ('PRODUTO/ops/',                              '02. Produto/Operacao tecnica',              'processo'),
    ('PRODUTO/modulos/',                          '02. Produto/Modulos',                       'processo'),
    ('PRODUTO/README.md',                         '02. Produto',                               'regras'),
    ('PRODUTO/VISAO.md',                          '01. Executivo/Estrategia',                  'estrategia'),

    # ───── Operacoes ─────
    ('OPERACIONAL/contratos/',                    '05. Operacoes/Contratos',                   'regras'),
    ('OPERACIONAL/materiais/juridico/',           '05. Operacoes/Juridico',                    'regras'),
    ('OPERACIONAL/materiais/treinamento_parceiro/','05. Operacoes/Treinamento de parceiros',  'processo'),
    ('OPERACIONAL/materiais/reguas/',             '05. Operacoes/Reguas e fluxos',             'processo'),
    ('OPERACIONAL/materiais/fluxos/',             '05. Operacoes/Reguas e fluxos',             'processo'),

    # ───── Clientes ─────
    ('context/clientes/',                         '08. Clientes',                              'contexto'),

    # ───── Reunioes (flat) ─────
    ('context/reunioes/',                         '09. Reunioes',                              'sessao'),

    # ───── Tarefas ─────
    ('context/tarefas/backlog/',                  '10. Tarefas/Backlog',                       'processo'),
    ('context/tarefas/finalizadas/',              '10. Tarefas/Finalizadas',                   'processo'),
    ('context/tarefas/',                          '10. Tarefas',                               'processo'),

    # ───── Agentes IA (capitaliza subpastas) ─────
    ('AGENTES/',                                  '11. Agentes IA',                            'contexto'),

    # ───── Catch-all OPERACIONAL ─────
    ('OPERACIONAL/materiais/',                    '05. Operacoes',                             'processo'),
    ('OPERACIONAL/',                              '05. Operacoes',                             'processo'),

    # ───── Catch-all context (avulsos: planos, palestras, diagnosticos soltos) ─────
    ('context/',                                  '01. Executivo/Decisoes',                    'contexto'),

    # ───── Catch-all PRODUTO ─────
    ('PRODUTO/',                                  '02. Produto',                               'regras'),
]


# Capitalizacao de subpastas (alguns paths sao all-lowercase no FS)
SUBPASTA_RENAME = {
    'comercial':         'Comercial',
    'executivo':         'Executivo',
    'marketing':         'Marketing',
    'operacoes':         'Operacoes',
    'produto':           'Produto',
    'tech':              'Tech',
    'fatepi':            'Fatepi/Faespi',
    'gigamax':           'Gigamax',
    'nuvyon':            'Nuvyon',
    'implementacoes':    'Implementacoes',
    'reunioes':          'Reunioes',
    'core':              'Core',
    'integracoes':       'Integracoes',
    'ops':               'Operacao tecnica',
    'modulos':           'Modulos',
    'cases':             'Cases',
    'propostas':         'Propostas',
    'posicionamento':    'Posicionamento',
    'contratos':         'Contratos',
    'juridico':          'Juridico',
    'reguas':            'Reguas',
    'fluxos':            'Fluxos',
    'scripts_vendas':    'Scripts de venda',
    'apresentacao':      'Apresentacao',
    'treinamento_parceiro': 'Treinamento de parceiros',
    'materiais':         'Materiais',
    'backlog':           'Backlog',
    'finalizadas':       'Finalizadas',
    'clientes':          'Clientes',
    'tarefas':           'Tarefas',
    'context':           'Contexto',
}


class Command(BaseCommand):
    help = 'Importa MD do robo/docs como Drive de empresa por time.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Aurora HQ')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--clear', action='store_true')
        parser.add_argument('--root', help='Default: robo/docs (auto-resolve)')

    def handle(self, *args, **opts):
        # Resolver root
        if opts.get('root'):
            root = Path(opts['root']).resolve()
        else:
            here = Path(__file__).resolve()
            root = here.parents[6] / 'docs'
        if not root.exists():
            raise CommandError(f'Raiz nao encontrada: {root}')

        try:
            tenant = Tenant.objects.get(nome=opts['tenant'])
        except Tenant.DoesNotExist:
            raise CommandError(f'Tenant nao encontrado: {opts["tenant"]}')

        dry = opts.get('dry_run')
        clear = opts.get('clear')

        self.stdout.write(self.style.NOTICE(f'Raiz: {root}'))
        self.stdout.write(self.style.NOTICE(f'Tenant: {tenant.nome}'))
        if dry:
            self.stdout.write(self.style.WARNING('(dry-run — nao grava)'))

        with transaction.atomic():
            if clear and not dry:
                self.stdout.write(self.style.WARNING('\nApagando docs+pastas existentes...'))
                Documento.all_tenants.filter(tenant=tenant).delete()
                PastaDocumento.all_tenants.filter(tenant=tenant).delete()

            # 1) Criar pastas raiz da empresa (sempre, mesmo vazias)
            pastas_cache = {}  # path_drive -> PastaDocumento
            for cfg in PASTAS_RAIZ:
                slug = slugify(cfg['nome'])[:120]
                if dry:
                    pastas_cache[cfg['nome']] = type('FakePasta', (), {
                        'pk': len(pastas_cache) + 1, 'slug': slug, 'nome': cfg['nome'], 'pai_id': None,
                    })()
                    continue
                pasta, _ = PastaDocumento.all_tenants.update_or_create(
                    tenant=tenant, slug=slug,
                    defaults={
                        'nome': cfg['nome'], 'pai': None,
                        'icone': cfg['icone'], 'cor': cfg['cor'], 'ordem': cfg['ordem'],
                    },
                )
                pastas_cache[cfg['nome']] = pasta

            self.stdout.write(self.style.SUCCESS(f'Pastas raiz: {len(PASTAS_RAIZ)} criadas/atualizadas.'))

            # 2) Iterar arquivos e roteer
            criados = 0
            atualizados = 0
            ignorados = 0
            stats_por_raiz = {}

            for f in sorted(root.rglob('*.md')):
                rel = f.relative_to(root).as_posix()
                resultado = self._rotear(rel)
                if not resultado:
                    ignorados += 1
                    self.stdout.write(self.style.WARNING(f'  IGNORADO (sem mapping): {rel}'))
                    continue

                dest_pasta_path, categoria = resultado

                # Garante hierarquia de pastas no Drive ate dest_pasta_path
                pasta_obj = self._garantir_pasta(tenant, dest_pasta_path, pastas_cache, dry)

                # Cria documento
                conteudo = f.read_text(encoding='utf-8', errors='replace')
                titulo = self._extrair_titulo(conteudo, f.name)
                resumo = self._extrair_resumo(conteudo)
                slug_doc = slugify(rel.replace('/', '-'))[:200]
                if not slug_doc:
                    ignorados += 1
                    continue

                if dry:
                    criados += 1
                else:
                    _, created = Documento.all_tenants.update_or_create(
                        tenant=tenant, slug=slug_doc,
                        defaults={
                            'titulo': titulo, 'categoria': categoria,
                            'conteudo': conteudo, 'resumo': resumo,
                            'pasta': pasta_obj, 'visivel_agentes': True, 'ordem': 0,
                        },
                    )
                    if created:
                        criados += 1
                    else:
                        atualizados += 1

                # Stats: agrupar por pasta raiz
                raiz_nome = dest_pasta_path.split('/')[0]
                stats_por_raiz[raiz_nome] = stats_por_raiz.get(raiz_nome, 0) + 1

            self.stdout.write(self.style.SUCCESS(
                f'\nDocumentos: +{criados} criados, ~{atualizados} atualizados, {ignorados} ignorados.'
            ))

            if stats_por_raiz:
                self.stdout.write('\nDistribuicao por raiz:')
                for nome in [c['nome'] for c in PASTAS_RAIZ]:
                    n = stats_por_raiz.get(nome, 0)
                    self.stdout.write(f'  {nome}: {n} docs')

            if dry:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING('\nDry-run: nada gravado.'))
            else:
                self.stdout.write(self.style.SUCCESS('\nDrive importado.'))

    # ── Helpers ────────────────────────────────────────────────────────────

    def _rotear(self, rel_path):
        """Retorna (dest_pasta_path, categoria) ou None se sem match."""
        for src, dest, cat in MAPEAMENTO:
            if src.endswith('.md'):
                # Match exato de arquivo
                if rel_path == src:
                    return dest, cat
            elif src.endswith('/'):
                # Prefix — preserva subpath
                if rel_path.startswith(src):
                    sub = rel_path[len(src):]
                    sub_dir = '/'.join(sub.split('/')[:-1])  # remove o nome do arquivo
                    if sub_dir:
                        # Capitaliza/renomeia cada parte
                        partes = [SUBPASTA_RENAME.get(p, p.replace('_', ' ').replace('-', ' ').title()) for p in sub_dir.split('/')]
                        return f"{dest}/{'/'.join(partes)}", cat
                    return dest, cat
        return None

    def _garantir_pasta(self, tenant, drive_path, cache, dry):
        """Cria pastas hierarquicas em cascata. Retorna a folha."""
        partes = drive_path.split('/')
        pai = None
        path_acumulado = ''
        for i, parte in enumerate(partes):
            path_acumulado = f'{path_acumulado}/{parte}' if path_acumulado else parte
            if path_acumulado in cache:
                pai = cache[path_acumulado]
                continue

            slug = slugify(path_acumulado.replace('/', '-'))[:120]
            if dry:
                fake = type('FakePasta', (), {
                    'pk': len(cache) + 1000, 'slug': slug, 'nome': parte, 'pai_id': None,
                })()
                cache[path_acumulado] = fake
                pai = fake
                continue

            pasta, _ = PastaDocumento.all_tenants.update_or_create(
                tenant=tenant, slug=slug,
                defaults={
                    'nome': parte, 'pai': pai,
                    'icone': 'bi-folder', 'cor': '#475569', 'ordem': i,
                },
            )
            cache[path_acumulado] = pasta
            pai = pasta
        return pai

    def _extrair_titulo(self, conteudo, fallback_filename):
        body = conteudo
        if body.startswith('---'):
            partes = body.split('---', 2)
            if len(partes) >= 3:
                body = partes[2].lstrip()
        m = re.search(r'^#\s+(.+?)\s*$', body, re.MULTILINE)
        if m:
            return m.group(1).strip()[:200]
        base = Path(fallback_filename).stem
        return base.replace('-', ' ').replace('_', ' ').strip().capitalize()[:200]

    def _extrair_resumo(self, conteudo):
        """Extrai resumo. Pula metadata, headings, codigo, tabelas."""
        body = conteudo
        if body.startswith('---'):
            partes = body.split('---', 2)
            if len(partes) >= 3:
                body = partes[2].lstrip()

        # Padroes que NAO sao resumo (metadata frequente em docs)
        meta_re = re.compile(
            r'^\s*[*_]{1,2}[A-Za-zÇçÃãÁáÉéÍíÓóÚúÂâÊêÔô\s/]+:[*_]{1,2}',
            re.IGNORECASE,
        )

        for raw in body.split('\n'):
            ln = raw.strip()
            if not ln:
                continue
            if ln.startswith('#'):
                continue
            if ln.startswith('```'):
                continue
            if ln.startswith('---'):
                continue
            if ln.startswith('|'):
                continue
            if ln.startswith('>'):  # blockquote
                continue
            if ln.startswith('-') or ln.startswith('*') or ln.startswith('+'):
                # bullet list — pode ser resumo, mas geralmente nao
                continue
            if meta_re.match(ln):
                # Linha de metadata tipo **Data:** 26/04/2026
                continue
            # Italico sozinho (geralmente nota editorial)
            if (ln.startswith('_') and ln.endswith('_')) or (ln.startswith('*') and ln.endswith('*') and not ln.startswith('**')):
                continue
            return ln[:280]
        return ''
