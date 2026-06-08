"""
Importa todos os docs de robo/docs/ pro Workspace, organizados como Drive de empresa.

Suporta .md (conteudo no banco), .pdf/.pptx (arquivo no media volume) e .json/.sql
(conteudo no banco como bloco de codigo).

Estrutura nova: por time, nao mirror do filesystem. Numeracao na raiz forca ordem
visual (Executivo no topo, Tarefas/Reunioes/Agentes no rodape).

Filesystem continua fonte da verdade. Re-rodar sincroniza (idempotente via slug).
Ao final gera um manifesto de sync (robo/docs/_SYNC_NUVEM.md + .sync_nuvem.json)
mapeando cada arquivo local -> doc na nuvem + link, ou marcando como "local-apenas".

Uso:
    python manage.py importar_docs_drive [--tenant 'Aurora HQ'] [--clear] [--dry-run]
        [--apenas-md | --apenas-binarios] [--base-url https://app.hubtrix.com.br]
        [--no-manifest]
"""
import json
import re
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.sistema.models import Tenant
from apps.workspace.models import Documento, PastaDocumento


# Extensoes suportadas e como cada uma vira Documento.
# formato 'markdown' = conteudo no banco; 'pdf'/'link' = bytes no Documento.arquivo.
EXT_MARKDOWN = '.md'
EXT_CONFIG = {
    '.md':   {'formato': 'markdown', 'modo': 'md'},
    '.pdf':  {'formato': 'pdf',      'modo': 'arquivo'},
    '.pptx': {'formato': 'link',     'modo': 'arquivo'},  # sem viewer: download via template
    '.json': {'formato': 'markdown', 'modo': 'codigo', 'lang': 'json'},
    '.sql':  {'formato': 'markdown', 'modo': 'codigo', 'lang': 'sql'},
}
EXTENSOES = set(EXT_CONFIG)

# Arquivos de manifesto gerados por este command (nunca importar a si mesmos).
MANIFESTO_JSON = '.sync_nuvem.json'
MANIFESTO_MD = '_SYNC_NUVEM.md'


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
        parser.add_argument('--apenas-md', action='store_true',
            help='So importa .md (conteudo no banco, dispensa media volume)')
        parser.add_argument('--apenas-binarios', action='store_true',
            help='So importa .pdf/.pptx/.json/.sql (precisa do media volume)')
        parser.add_argument('--base-url', default='https://app.hubtrix.com.br',
            help='Base URL pros links do manifesto de sync')
        parser.add_argument('--no-manifest', action='store_true',
            help='Nao gerar o manifesto de sync ao final')
        parser.add_argument('--manifesto-apenas', action='store_true',
            help='Nao importa nada: so consulta o banco (read-only) e gera o manifesto. '
                 'Use apontando pro banco de prod pra ver o que ja esta la.')

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
        apenas_md = opts.get('apenas_md')
        apenas_bin = opts.get('apenas_binarios')
        base_url = (opts.get('base_url') or '').rstrip('/')
        if apenas_md and apenas_bin:
            raise CommandError('Use --apenas-md OU --apenas-binarios, nao os dois.')

        self.stdout.write(self.style.NOTICE(f'Raiz: {root}'))
        self.stdout.write(self.style.NOTICE(f'Tenant: {tenant.nome}'))
        if apenas_md:
            self.stdout.write(self.style.NOTICE('(apenas .md)'))
        if apenas_bin:
            self.stdout.write(self.style.NOTICE('(apenas binarios: .pdf/.pptx/.json/.sql)'))
        if dry:
            self.stdout.write(self.style.WARNING('(dry-run — nao grava)'))

        # Modo so-manifesto: nao importa nada, so le o banco e escreve o manifesto.
        # Seguro apontar pro banco de prod (read-only no DB).
        if opts.get('manifesto_apenas'):
            self.stdout.write(self.style.NOTICE('(so-manifesto — nao importa, le o banco)'))
            self._gerar_manifesto(root, tenant, base_url)
            return

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

            arquivos = sorted(
                p for p in root.rglob('*')
                if p.is_file() and p.suffix.lower() in EXTENSOES
                and p.name not in (MANIFESTO_JSON, MANIFESTO_MD)
            )

            for f in arquivos:
                ext = f.suffix.lower()
                eh_md = ext == EXT_MARKDOWN
                # Respeita filtros --apenas-md / --apenas-binarios
                if eh_md and apenas_bin:
                    continue
                if not eh_md and apenas_md:
                    continue

                rel = f.relative_to(root).as_posix()
                resultado = self._rotear(rel)
                if not resultado:
                    ignorados += 1
                    self.stdout.write(self.style.WARNING(f'  IGNORADO (sem mapping): {rel}'))
                    continue

                dest_pasta_path, categoria = resultado
                pasta_obj = self._garantir_pasta(tenant, dest_pasta_path, pastas_cache, dry)

                slug_doc = slugify(rel.replace('/', '-'))[:200]
                if not slug_doc:
                    ignorados += 1
                    continue

                if eh_md:
                    created = self._processar_md(f, rel, tenant, pasta_obj, categoria, slug_doc, dry)
                else:
                    created = self._processar_binario(f, ext, tenant, pasta_obj, categoria, slug_doc, dry)

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
                self.stdout.write(self.style.WARNING('\nDry-run: nada gravado (manifesto nao gerado).'))
            else:
                self.stdout.write(self.style.SUCCESS('\nDrive importado.'))
                if not opts.get('no_manifest'):
                    self._gerar_manifesto(root, tenant, base_url)

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

    # ── Processadores por tipo ───────────────────────────────────────────────

    def _processar_md(self, f, rel, tenant, pasta_obj, categoria, slug_doc, dry):
        conteudo = f.read_text(encoding='utf-8', errors='replace')
        titulo = self._extrair_titulo(conteudo, f.name)
        resumo = self._extrair_resumo(conteudo)
        if dry:
            return True
        _, created = Documento.all_tenants.update_or_create(
            tenant=tenant, slug=slug_doc,
            defaults={
                'titulo': titulo, 'categoria': categoria, 'formato': 'markdown',
                'conteudo': conteudo, 'resumo': resumo,
                'pasta': pasta_obj, 'visivel_agentes': True, 'ordem': 0,
            },
        )
        return created

    def _processar_binario(self, f, ext, tenant, pasta_obj, categoria, slug_doc, dry):
        cfg = EXT_CONFIG[ext]
        titulo = self._titulo_de_arquivo(f.name)
        resumo = f'Arquivo {ext.lstrip(".")} importado de {f.name}'

        if cfg['modo'] == 'codigo':
            # json/sql: conteudo legivel como bloco de codigo no banco
            raw = f.read_text(encoding='utf-8', errors='replace')
            if ext == '.json':
                raw = self._json_pretty(raw)
            conteudo = f"```{cfg['lang']}\n{raw}\n```"
            if dry:
                return True
            _, created = Documento.all_tenants.update_or_create(
                tenant=tenant, slug=slug_doc,
                defaults={
                    'titulo': titulo, 'categoria': categoria, 'formato': cfg['formato'],
                    'conteudo': conteudo, 'resumo': resumo,
                    'pasta': pasta_obj, 'visivel_agentes': True, 'ordem': 0,
                },
            )
            return created

        # modo 'arquivo' (pdf/pptx): bytes vao pro Documento.arquivo (media volume)
        if dry:
            return True
        doc, created = Documento.all_tenants.update_or_create(
            tenant=tenant, slug=slug_doc,
            defaults={
                'titulo': titulo, 'categoria': categoria, 'formato': cfg['formato'],
                'resumo': resumo, 'pasta': pasta_obj,
                'visivel_agentes': True, 'ordem': 0,
            },
        )
        # Idempotencia de bytes: so (re)grava se ausente ou nome/tamanho diferem
        if self._precisa_regravar_arquivo(doc, f):
            doc.arquivo.save(f.name, ContentFile(f.read_bytes()), save=True)
        return created

    def _precisa_regravar_arquivo(self, doc, f):
        # Compara por TAMANHO, nao por nome: o storage trunca/randomiza o nome
        # quando o path passa de 100 chars, entao nome nunca bate e re-gravaria
        # a cada run (duplicando no media). Tamanho igual = mesmo arquivo.
        if not doc.arquivo:
            return True
        try:
            return doc.arquivo.size != f.stat().st_size
        except (OSError, ValueError):
            return True

    def _titulo_de_arquivo(self, filename):
        base = Path(filename).stem
        return (base.replace('-', ' ').replace('_', ' ').strip()[:200]) or filename

    def _json_pretty(self, raw):
        try:
            return json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
        except (ValueError, TypeError):
            return raw

    # ── Manifesto de sync ─────────────────────────────────────────────────────

    def _gerar_manifesto(self, root, tenant, base_url):
        """Caminha os arquivos locais, mapeia pro doc na nuvem (slug deterministico)
        e escreve manifesto (json + md). Reflete o estado real da nuvem, mesmo
        apos runs parciais (--apenas-md / --apenas-binarios)."""
        agora = timezone.now().isoformat(timespec='seconds')
        entradas = []
        arquivos = sorted(
            p for p in root.rglob('*')
            if p.is_file() and p.suffix.lower() in EXTENSOES
            and p.name not in (MANIFESTO_JSON, MANIFESTO_MD)
        )
        for f in arquivos:
            rel = f.relative_to(root).as_posix()
            resultado = self._rotear(rel)
            pasta_path = resultado[0] if resultado else ''
            slug_doc = slugify(rel.replace('/', '-'))[:200]
            doc = (
                Documento.all_tenants.filter(tenant=tenant, slug=slug_doc).first()
                if slug_doc else None
            )
            if doc:
                entradas.append({
                    'arquivo': rel, 'status': 'sincronizado',
                    'documento_id': doc.pk, 'documento_slug': doc.slug,
                    'categoria': doc.categoria, 'formato': doc.formato,
                    'pasta': pasta_path,
                    'url': f'{base_url}/workspace/documentos/{doc.pk}/',
                })
            else:
                entradas.append({
                    'arquivo': rel, 'status': 'local-apenas',
                    'documento_id': None, 'documento_slug': slug_doc,
                    'categoria': '', 'formato': '', 'pasta': pasta_path, 'url': '',
                })

        sincronizados = sum(1 for e in entradas if e['status'] == 'sincronizado')
        local_apenas = len(entradas) - sincronizados
        payload = {
            'gerado_em': agora, 'tenant': tenant.nome, 'base_url': base_url,
            'total': len(entradas), 'sincronizados': sincronizados,
            'local_apenas': local_apenas, 'arquivos': entradas,
        }
        (root / MANIFESTO_JSON).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8',
        )
        (root / MANIFESTO_MD).write_text(self._manifesto_md(payload), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(
            f'Manifesto: {sincronizados} na nuvem, {local_apenas} local-apenas '
            f'-> {MANIFESTO_MD}'
        ))

    def _manifesto_md(self, payload):
        linhas = [
            '# Sincronizacao com a nuvem (Workspace)',
            '',
            f"Gerado em {payload['gerado_em']} para o tenant **{payload['tenant']}**.",
            '',
            f"- Total de arquivos: **{payload['total']}**",
            f"- Sincronizados na nuvem: **{payload['sincronizados']}**",
            f"- Apenas local (ainda nao enviados): **{payload['local_apenas']}**",
            '',
            '> Fonte viva colaborativa: Workspace. A pasta `robo/docs/` segue como fonte versionada.',
            '> Re-rode `python manage.py importar_docs_drive` para atualizar este manifesto.',
            '',
            '| Arquivo | Status | Categoria | Link na nuvem |',
            '|---------|--------|-----------|---------------|',
        ]
        for e in payload['arquivos']:
            if e['status'] == 'sincronizado':
                link = f"[abrir]({e['url']})"
                cat = e['categoria'] or 'outro'
            else:
                link = 'sem link'
                cat = 'sem'
            linhas.append(f"| `{e['arquivo']}` | {e['status']} | {cat} | {link} |")
        linhas.append('')
        return '\n'.join(linhas)

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
