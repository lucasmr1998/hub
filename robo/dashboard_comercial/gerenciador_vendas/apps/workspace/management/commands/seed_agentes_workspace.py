"""
Seed do roster de agentes do Workspace.

Le os docs de personas em robo/docs/AGENTES/*.md e cria/atualiza um
`automacao.Agente` por persona, para um tenant (padrao aurora-hq). Idempotente
por (tenant, nome). Os agentes recebem as tools de dados (read-only) para
consultar o negocio. Roster e prompts vem dos docs (nada hardcoded aqui, so a
lista curada de tools de dados).

    python manage.py seed_agentes_workspace
    python manage.py seed_agentes_workspace --tenant demo --dry-run
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


# Tools de dados (read-only) que todo agente executivo recebe.
# Chaves do registry em apps/automacao/services/ia_tools.py.
TOOLS_AGENTE = [
    # consulta (read-only)
    'status_pipeline', 'resumo_leads', 'vendas_periodo', 'churn_clientes', 'tickets_abertos',
    'listar_documentos', 'consultar_documento',
    # acao no workspace (o agente faz)
    'criar_projeto', 'criar_tarefa_workspace', 'criar_etapa', 'salvar_documento',
    'atualizar_tarefa_workspace', 'atualizar_projeto',
    # recomendar com aval humano
    'solicitar_aprovacao',
]

# Tools extras por time (alem das padrao): tech explora codigo, marketing gera imagem.
TOOLS_EXTRA_POR_EQUIPE = {
    'tech': ['explorar_codigo'],
    'marketing': ['gerar_imagem'],
}

PREFIXO_PROMPT = (
    'Voce e um agente da Hubtrix operando no Workspace interno. Quando a pergunta '
    'envolver numeros do negocio (pipeline, leads, vendas, churn, suporte), USE as '
    'ferramentas de dados disponiveis para buscar os valores reais antes de responder, '
    'em vez de estimar. Quando quiser RECOMENDAR uma acao que precisa de aval humano, '
    'use solicitar_aprovacao em vez de afirmar que ja fez. Seja direto e fundamente com dados.\n\n'
)

# Visual por time (cor hex + Bootstrap Icon). O `equipe` vem da subpasta em AGENTES/.
ESTILO_EQUIPE = {
    'executivo': ('#1e3a8a', 'bi-briefcase'),
    'produto':   ('#7c3aed', 'bi-box-seam'),
    'comercial': ('#b45309', 'bi-graph-up-arrow'),
    'marketing': ('#be185d', 'bi-megaphone'),
    'tech':      ('#0f766e', 'bi-code-slash'),
    'operacoes': ('#475569', 'bi-gear'),
    'fluxo':     ('#0891b2', 'bi-robot'),
}


def _achar_agentes_dir():
    """Autodetecta robo/docs/AGENTES subindo a partir do BASE_DIR."""
    base = Path(settings.BASE_DIR)
    for cand in [base, *base.parents]:
        for sub in (cand / 'docs' / 'AGENTES', cand / 'robo' / 'docs' / 'AGENTES'):
            if sub.is_dir():
                return sub
    return None


def _nome_do_md(texto, fallback):
    """Extrai o nome do agente do H1 (ex: '# Agente — CEO' -> 'CEO')."""
    for linha in texto.splitlines():
        s = linha.strip()
        if s.startswith('# '):
            titulo = s[2:].strip()
            for sep in ('—', ' - ', ':'):
                if sep in titulo:
                    esq, dir_ = titulo.split(sep, 1)
                    if esq.strip().lower().startswith('agente'):
                        return dir_.strip()
            return titulo
    return fallback


class Command(BaseCommand):
    help = 'Cria/atualiza os agentes do Workspace a partir de robo/docs/AGENTES/*.md.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='aurora-hq', help='Slug do tenant (padrao aurora-hq)')
        parser.add_argument('--dir', default=None, help='Caminho da pasta AGENTES (padrao: autodetecta)')
        parser.add_argument('--dry-run', action='store_true', help='So mostra, nao grava')

    def handle(self, *args, **opts):
        from apps.sistema.models import Tenant
        from apps.automacao.models import Agente
        from apps.automacao.services.ia import integracao_ia_do_tenant

        tenant = Tenant.objects.filter(slug=opts['tenant']).first()
        if tenant is None:
            raise CommandError(f"tenant '{opts['tenant']}' nao encontrado")

        agentes_dir = Path(opts['dir']) if opts['dir'] else _achar_agentes_dir()
        if not agentes_dir or not agentes_dir.is_dir():
            raise CommandError('pasta AGENTES nao encontrada (use --dir)')

        arquivos = sorted(p for p in agentes_dir.rglob('*.md') if p.name.lower() != 'readme.md')
        if not arquivos:
            raise CommandError(f'nenhum .md de agente em {agentes_dir}')

        integracao = integracao_ia_do_tenant(tenant)
        dry = opts['dry_run']
        criados = atualizados = 0
        ordem_por_equipe = {}

        for arq in arquivos:
            texto = arq.read_text(encoding='utf-8').replace('AuroraISP', 'Hubtrix')
            nome = _nome_do_md(texto, arq.stem.replace('_', ' ').title())
            rel = arq.relative_to(agentes_dir)
            # Subpasta = time (ex: executivo/ceo.md -> 'executivo'); arquivo na raiz = sem time.
            equipe = rel.parts[0] if len(rel.parts) > 1 else ''
            cor, icone = ESTILO_EQUIPE.get(equipe, ('', 'bi-robot'))
            ordem = ordem_por_equipe.get(equipe, 0)
            ordem_por_equipe[equipe] = ordem + 1
            if dry:
                self.stdout.write(f'  [dry] {nome}  [{equipe or "sem time"}]  ({rel})')
                continue
            _obj, criado = Agente.all_tenants.update_or_create(
                tenant=tenant, nome=nome,
                defaults={
                    'system_prompt': PREFIXO_PROMPT + texto,
                    'tools': list(TOOLS_AGENTE) + TOOLS_EXTRA_POR_EQUIPE.get(equipe, []),
                    'memoria': 'conversa',
                    'integracao_ia': integracao,
                    'ativo': True,
                    'equipe': equipe,
                    'cor': cor,
                    'icone': icone,
                    'ordem': ordem,
                },
            )
            criados += int(criado)
            atualizados += int(not criado)
            self.stdout.write(f'  {"criado" if criado else "atualizado"}: {nome}')

        if not dry:
            intg = str(integracao) if integracao else 'NENHUMA (fallback em runtime)'
            self.stdout.write(self.style.SUCCESS(
                f'Roster {tenant.slug}: {criados} criados, {atualizados} atualizados '
                f'({len(arquivos)} personas). Integracao IA: {intg}.'))
