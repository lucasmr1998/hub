"""Relatório de paridade da migração do funil (Fase 2, Passo 3).

Cruza os fires REAIS do motor antigo (`mover_regra`/`acoes_regra`) com o que o shadow
FARIA (`shadow_fluxo`), por pulso (`motor_disparado`), pra provar paridade antes do
cutover. Read-only (só LÊ LogSistema). Requer o shadow ligado (AUTOMACAO_SHADOW_ATIVO)
tendo rodado por um período.

Uso:
    python manage.py comparar_shadow_pipeline --dias 7
    python manage.py comparar_shadow_pipeline --tenant nuvyon --dias 3
"""
from datetime import timedelta
from itertools import groupby

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.automacao.comparador_pipeline import comparar_op_agregado, resumir

_ACOES = ('motor_disparado', 'mover_regra', 'acoes_regra', 'shadow_fluxo')


def _regras_do_log(log):
    extras = log.dados_extras or {}
    if log.acao in ('mover_regra', 'acoes_regra'):
        rid = extras.get('regra_id')
        return {int(rid)} if rid is not None else set()
    if log.acao == 'shadow_fluxo':
        out = set()
        for wf in (extras.get('would_fire') or []):
            orig = wf.get('origem_regra')
            if orig is not None:
                out.add(int(orig))
        return out
    return set()


class Command(BaseCommand):
    help = 'Relatório de paridade shadow vs motor antigo (migração do funil).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='', help='Slug do tenant (vazio = todos).')
        parser.add_argument('--dias', type=int, default=7, help='Janela em dias (default 7).')
        parser.add_argument('--exemplos', type=int, default=5, help='Nº de divergências a listar por tenant.')

    def handle(self, *args, **opts):
        from apps.sistema.models import LogSistema

        desde = timezone.now() - timedelta(days=opts['dias'])
        logs = (LogSistema.all_tenants
                .filter(acao__in=_ACOES, entidade='OportunidadeVenda',
                        entidade_id__isnull=False, data_criacao__gte=desde)
                .select_related('tenant')
                .order_by('tenant_id', 'entidade_id', 'data_criacao'))
        if opts['tenant']:
            logs = logs.filter(tenant__slug=opts['tenant'])

        logs = list(logs)
        if not logs:
            self.stdout.write(self.style.WARNING(
                'Sem logs no período. O shadow já rodou? (AUTOMACAO_SHADOW_ATIVO ligado + tráfego)'))
            return

        # agrupa por tenant, depois por op
        por_tenant = {}
        for tid, grupo_t in groupby(logs, key=lambda l: l.tenant_id):
            grupo_t = list(grupo_t)
            slug = grupo_t[0].tenant.slug if grupo_t[0].tenant else str(tid)
            pulsos_tenant = []
            for op_id, grupo_op in groupby(grupo_t, key=lambda l: l.entidade_id):
                eventos = [{'acao': l.acao, 'ts': l.data_criacao, 'rules': _regras_do_log(l)}
                           for l in grupo_op]
                pulsos_tenant.extend(comparar_op_agregado(eventos))
            por_tenant[slug] = pulsos_tenant

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Paridade shadow vs motor antigo — últimos {opts["dias"]} dia(s)'))

        for slug, pulsos in por_tenant.items():
            r = resumir(pulsos)
            self.stdout.write(f'\n== {slug} ==')
            self.stdout.write(
                f'  pulsos: {r["pulsos"]} | com atividade: {r["pulsos_com_atividade"]} | '
                f'divergentes: {r["divergentes"]} | paridade: {r["paridade"]*100:.1f}%')
            if r['regras_so_antigo']:
                self.stdout.write(self.style.ERROR(
                    f'  regras que o NOVO PERDERIA (antigo fez, novo nao faria): {r["regras_so_antigo"]}'))
            if r['regras_so_novo']:
                self.stdout.write(self.style.WARNING(
                    f'  regras que o NOVO FARIA A MAIS (antigo nao fez): {r["regras_so_novo"]}'))
            if r['divergentes'] == 0 and r['pulsos_com_atividade'] > 0:
                self.stdout.write(self.style.SUCCESS('  ✓ 0 divergência — candidato a cutover'))
            # exemplos de divergência
            n = opts['exemplos']
            exemplos = [p for p in pulsos if not p['match']][:n]
            for p in exemplos:
                self.stdout.write(
                    f'    divergência: antigo={sorted(p["antigo"])} novo={sorted(p["novo"])} '
                    f'(so_antigo={sorted(p["so_antigo"])} so_novo={sorted(p["so_novo"])})')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Feito (read-only).'))
