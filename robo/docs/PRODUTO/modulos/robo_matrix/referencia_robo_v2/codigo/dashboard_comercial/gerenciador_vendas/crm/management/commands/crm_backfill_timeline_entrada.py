"""Cria registro inicial de HistoricoPipelineEstagio para oportunidades sem timeline.

Antes da correção em crm/signals.py, oportunidades de indicação (e outras)
eram criadas sem histórico de entrada — o contador da aba Timeline ficava em 0.

    python manage.py crm_backfill_timeline_entrada --dry-run
    python manage.py crm_backfill_timeline_entrada
    python manage.py crm_backfill_timeline_entrada --tipo indicacao
    python manage.py crm_backfill_timeline_entrada --dias 90
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from crm.models import HistoricoPipelineEstagio, OportunidadeVenda

MOTIVOS = {
    'indicacao': 'Entrada no pipeline de indicações (backfill)',
    'aquisicao': 'Entrada no funil de aquisição (backfill)',
    'novo_servico': 'Entrada no pipeline de novo serviço (backfill)',
    'upgrade': 'Entrada no pipeline de upgrade (backfill)',
    'atendimento': 'Entrada no pipeline de atendimento (backfill)',
}


class Command(BaseCommand):
    help = 'Backfill do histórico inicial de estágio para oportunidades sem timeline.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas lista o que seria criado, sem gravar.',
        )
        parser.add_argument(
            '--tipo',
            choices=[c[0] for c in OportunidadeVenda.TIPO_CHOICES],
            help='Filtrar por tipo de pipeline (ex: indicacao).',
        )
        parser.add_argument(
            '--dias',
            type=int,
            default=0,
            help='Só oportunidades criadas nos últimos N dias (0 = todas).',
        )

    def handle(self, *args, **opts):
        dry_run = opts['dry_run']
        qs = (
            OportunidadeVenda.objects
            .filter(ativo=True, estagio__isnull=False)
            .annotate(n_hist=Count('historico_estagios'))
            .filter(n_hist=0)
            .select_related('estagio', 'lead', 'criado_por')
            .order_by('id')
        )

        if opts['tipo']:
            qs = qs.filter(tipo=opts['tipo'])
        if opts['dias']:
            corte = timezone.now() - timedelta(days=opts['dias'])
            qs = qs.filter(data_criacao__gte=corte)

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('Nenhuma oportunidade pendente de backfill.'))
            return

        criados = 0
        for opp in qs.iterator():
            data_ref = opp.data_entrada_estagio or opp.data_criacao or timezone.now()
            motivo = MOTIVOS.get(opp.tipo, 'Entrada no pipeline (backfill)')
            lead_nome = (opp.lead.nome_razaosocial if opp.lead else None) or opp.titulo or f'#{opp.id}'

            if dry_run:
                self.stdout.write(
                    f'  [dry-run] opp #{opp.id} ({opp.tipo}) — {lead_nome} → {opp.estagio.nome}'
                )
                criados += 1
                continue

            HistoricoPipelineEstagio.objects.create(
                oportunidade=opp,
                estagio_anterior=None,
                estagio_novo=opp.estagio,
                movido_por=opp.criado_por,
                motivo=motivo,
                tempo_no_estagio_horas=0,
                data_transicao=data_ref,
            )
            criados += 1

        prefixo = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefixo}Backfill concluído — {criados} de {total} oportunidade(s) com entrada registrada.',
        ))
