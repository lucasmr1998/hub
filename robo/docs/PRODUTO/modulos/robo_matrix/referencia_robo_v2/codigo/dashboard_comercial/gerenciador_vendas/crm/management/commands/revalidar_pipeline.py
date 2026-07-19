"""
Reavalia todas as oportunidades ativas contra as regras configuradas
do pipeline e move para o estágio correto quando necessário.

Uso:
    python manage.py revalidar_pipeline
    python manage.py revalidar_pipeline --dry-run
    python manage.py revalidar_pipeline --estagio negociacao
    python manage.py revalidar_pipeline --limit 100
"""
from django.core.management.base import BaseCommand
from django.db.models import Q


class Command(BaseCommand):
    help = 'Reavalia oportunidades ativas contra as regras do pipeline e move quando necessário'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Simula sem gravar alterações',
        )
        parser.add_argument(
            '--estagio', type=str, default='',
            help='Filtrar por tipo de estágio (ex: negociacao, fechamento)',
        )
        parser.add_argument(
            '--limit', type=int, default=0,
            help='Processar no máximo N oportunidades',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        filtro_estagio = options['estagio']
        limit = options['limit']

        self.stdout.write(self.style.MIGRATE_HEADING(
            '\nRevalidar Pipeline' + (' [DRY RUN]' if dry_run else '')
        ))

        from crm.models import OportunidadeVenda, RegraPipelineEstagio
        from crm.services.regras_engine import avaliar_regras_para_lead, mover_oportunidade_por_regra

        # Verificar se há regras configuradas
        total_regras = RegraPipelineEstagio.objects.filter(ativo=True).count()
        if total_regras == 0:
            self.stdout.write(self.style.WARNING(
                'Nenhuma regra ativa configurada. Configure regras na página de configurações do CRM.'
            ))
            return

        self.stdout.write(f'  Regras ativas: {total_regras}')

        # Buscar oportunidades
        qs = (
            OportunidadeVenda.objects
            .filter(ativo=True)
            .exclude(estagio__is_final_ganho=True)
            .exclude(estagio__is_final_perdido=True)
            .select_related('lead', 'estagio')
            .prefetch_related('tags')
        )

        if filtro_estagio:
            qs = qs.filter(estagio__tipo=filtro_estagio)

        if limit > 0:
            qs = qs[:limit]

        oportunidades = list(qs)
        self.stdout.write(f'  Oportunidades a avaliar: {len(oportunidades)}')

        movidas = 0
        sem_mudanca = 0
        sem_regra = 0

        for opp in oportunidades:
            resultado = avaliar_regras_para_lead(opp)

            if resultado is None:
                sem_regra += 1
                continue

            estagio_destino, regra_nome, condicoes = resultado

            if opp.estagio_id == estagio_destino.pk:
                sem_mudanca += 1
                continue

            if dry_run:
                self.stdout.write(
                    f'  [DRY] {opp.lead.nome_razaosocial if opp.lead else opp.pk}: '
                    f'{opp.estagio.nome} -> {estagio_destino.nome} (Regra: {regra_nome})'
                )
            else:
                mover_oportunidade_por_regra(opp, estagio_destino, regra_nome, condicoes)
                self.stdout.write(
                    f'  MOVIDA: {opp.lead.nome_razaosocial if opp.lead else opp.pk}: '
                    f'{opp.estagio.nome} -> {estagio_destino.nome}'
                )

            movidas += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'  Movidas: {movidas}'))
        self.stdout.write(f'  Sem mudança: {sem_mudanca}')
        self.stdout.write(f'  Sem regra correspondente: {sem_regra}')
        self.stdout.write('')
