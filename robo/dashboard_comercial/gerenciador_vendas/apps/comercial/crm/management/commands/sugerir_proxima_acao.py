"""
Gera sugestões de próxima ação (IA) pra oportunidades ativas.

Para cada OportunidadeVenda em pipeline ativo (status != ganha/perdida)
sem atividade nas últimas 24h, monta contexto e chama LLM.

Uso:
    python manage.py sugerir_proxima_acao --settings=gerenciador_vendas.settings_local

Crontab sugerido (a cada 1h):
    0 * * * * python manage.py sugerir_proxima_acao --limit=50
"""
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Gera sugestões de próxima ação via IA pra oportunidades ativas'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument(
            '--limit', type=int, default=50,
            help='Máximo de oportunidades por execução (default: 50)',
        )

    def handle(self, *args, **options):
        from apps.comercial.crm.models import OportunidadeVenda
        from apps.comercial.crm.services import sugestao_acao

        dry = options['dry_run']
        limit = options['limit']

        qs = OportunidadeVenda.objects.exclude(
            status__in=['ganha', 'perdida']
        ).select_related('lead', 'estagio', 'tenant', 'responsavel').order_by('-data_criacao')

        processadas = 0
        geradas = 0
        puladas = 0

        for op in qs:
            if processadas >= limit:
                break

            if not sugestao_acao.deve_regenerar(op):
                puladas += 1
                continue

            processadas += 1
            self.stdout.write(f'Gerando sugestão pra Oportunidade #{op.id} ({op.titulo[:50]})...')

            if dry:
                continue

            sugestao = sugestao_acao.gerar_sugestao(op)
            if sugestao:
                op.proxima_acao_sugerida = sugestao
                op.save(update_fields=['proxima_acao_sugerida'])
                geradas += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  → {sugestao.get("tipo")}: {sugestao.get("titulo", "")[:80]}'
                ))
            else:
                self.stdout.write(self.style.WARNING(f'  → falhou'))

        self.stdout.write(self.style.SUCCESS(
            f'\n=== Resumo ===\n'
            f'Total avaliadas: {qs.count()}\n'
            f'Processadas (LLM call): {processadas}\n'
            f'Sugestões geradas: {geradas}\n'
            f'Puladas (cache válido): {puladas}\n'
            f'Modo: {"dry-run" if dry else "aplicado"}'
        ))
