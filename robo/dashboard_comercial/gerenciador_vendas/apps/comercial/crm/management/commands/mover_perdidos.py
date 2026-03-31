"""
Move automaticamente para 'Perdido' as oportunidades que estão em 'Em Qualificação'
há mais de 48 horas sem documentacao_validada=True.

Regra de negócio:
  - Estágio atual: tipo='qualificacao'
  - Lead: documentacao_validada=False (ou None)
  - Tempo no estágio: >= 48 horas
  → Move para estágio tipo='perdido'

Uso:
    python manage.py mover_perdidos
    python manage.py mover_perdidos --dry-run        (simula sem gravar)
    python manage.py mover_perdidos --horas 72       (customiza o limite — padrão: 48h)
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction


HORAS_PADRAO = 48


class Command(BaseCommand):
    help = 'Move para Perdido as oportunidades em qualificação há mais de N horas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Simula sem gravar'
        )
        parser.add_argument(
            '--horas', type=int, default=HORAS_PADRAO,
            help=f'Horas máximas em qualificação sem avançar (padrão: {HORAS_PADRAO})'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        horas_limite = options['horas']

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n⏱  Mover Perdidos — leads em qualificação > {horas_limite}h'
            + (' [DRY RUN]' if dry_run else '')
        ))

        from apps.comercial.crm.models import (
            PipelineEstagio, OportunidadeVenda, HistoricoPipelineEstagio,
        )

        # Estágios necessários
        estagio_qualificacao = PipelineEstagio.objects.filter(
            tipo='qualificacao', ativo=True
        ).order_by('ordem').first()
        estagio_perdido = PipelineEstagio.objects.filter(
            tipo='perdido', ativo=True
        ).order_by('ordem').first()

        if not estagio_qualificacao:
            raise CommandError('Estágio tipo="qualificacao" não encontrado.')
        if not estagio_perdido:
            raise CommandError('Estágio tipo="perdido" não encontrado.')

        self.stdout.write(
            f'\n  Qualificação: "{estagio_qualificacao.nome}"\n'
            f'  Perdido:      "{estagio_perdido.nome}"\n'
        )

        # Corte de tempo
        limite_dt = timezone.now() - timezone.timedelta(hours=horas_limite)

        # Oportunidades candidatas:
        # - no estágio de qualificação
        # - entrada no estágio há mais de horas_limite
        # - lead sem documentacao_validada
        candidatas = (
            OportunidadeVenda.objects
            .filter(
                estagio=estagio_qualificacao,
                ativo=True,
                data_entrada_estagio__lte=limite_dt,
            )
            .select_related('lead', 'estagio')
        )

        # Filtro Python para documentacao_validada (campo no LeadProspecto)
        para_mover = [
            op for op in candidatas
            if not getattr(op.lead, 'documentacao_validada', False)
        ]

        total = len(para_mover)
        self.stdout.write(f'  Candidatas encontradas: {total}')

        if total == 0:
            self.stdout.write(self.style.SUCCESS('\n  ✓ Nenhuma oportunidade a mover.'))
            return

        movidas = 0
        agora = timezone.now()

        if dry_run:
            for op in para_mover:
                horas_no_estagio = (
                    (agora - op.data_entrada_estagio).total_seconds() / 3600
                )
                self.stdout.write(
                    f'  [DRY] {op.lead.nome_razaosocial or "?":<30} '
                    f'há {horas_no_estagio:.1f}h em qualificação → Perdido'
                )
            movidas = total
        else:
            with transaction.atomic():
                historicos = []
                for op in para_mover:
                    horas_no_estagio = (
                        (agora - op.data_entrada_estagio).total_seconds() / 3600
                    )
                    historicos.append(HistoricoPipelineEstagio(
                        oportunidade=op,
                        estagio_anterior=estagio_qualificacao,
                        estagio_novo=estagio_perdido,
                        motivo=(
                            f'Qualificação não concluída após {horas_no_estagio:.0f}h '
                            f'(regra automática: >{horas_limite}h sem documentação validada)'
                        ),
                        tempo_no_estagio_horas=round(horas_no_estagio, 2),
                    ))

                HistoricoPipelineEstagio.objects.bulk_create(historicos)

                # Atualizar estágio das oportunidades em lote
                ids_para_mover = [op.pk for op in para_mover]
                OportunidadeVenda.objects.filter(pk__in=ids_para_mover).update(
                    estagio=estagio_perdido,
                    data_entrada_estagio=agora,
                    data_atualizacao=agora,
                )
                movidas = len(ids_para_mover)

        self.stdout.write(self.style.SUCCESS(
            f'\n  ✅ {"Simuladas" if dry_run else "Movidas"}: {movidas} oportunidades → '
            f'"{estagio_perdido.nome}"\n'
        ))
