"""
Sincroniza clientes de todos os ERPs ativos para a tabela ClienteConsolidado.

Itera por adapter conhecido (HubSoft hoje; SGP/Voalle quando vierem) e
upserta cada cliente nativo no modelo central.

Uso:
    python manage.py consolidar_clientes --settings=gerenciador_vendas.settings_local
    python manage.py consolidar_clientes --tenant 3 --origem hubsoft
    python manage.py consolidar_clientes --dry-run

Crontab sugerido (4×/dia):
    0 */6 * * * python manage.py consolidar_clientes
"""
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# Mapa de adapter por origem. Adicionar novos ERPs aqui.
ADAPTERS = {}


def _carregar_adapters():
    """Carrega adapters disponíveis. Lazy pra evitar import circular em startup."""
    if ADAPTERS:
        return ADAPTERS

    from apps.integracoes.services.adapters import hubsoft as hubsoft_adapter
    ADAPTERS['hubsoft'] = hubsoft_adapter

    # Quando SGP estiver pronto:
    # from apps.integracoes.services.adapters import sgp as sgp_adapter
    # ADAPTERS['sgp'] = sgp_adapter

    return ADAPTERS


class Command(BaseCommand):
    help = 'Sincroniza clientes de ERPs nativos pra ClienteConsolidado'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--tenant', type=int, default=None, help='Limitar a um tenant específico')
        parser.add_argument('--origem', type=str, default=None, help='Limitar a um ERP (hubsoft/sgp/...)')
        parser.add_argument('--limit', type=int, default=None)

    def handle(self, *args, **options):
        from apps.sistema.models import Tenant

        adapters = _carregar_adapters()

        origens_filtro = [options['origem']] if options['origem'] else list(adapters.keys())
        for origem in origens_filtro:
            if origem not in adapters:
                self.stdout.write(self.style.WARNING(f'Adapter {origem} não disponível'))
                continue

        tenants_qs = Tenant.objects.all()
        if options['tenant']:
            tenants_qs = tenants_qs.filter(pk=options['tenant'])

        total_processados = 0
        total_upserted = 0
        total_erros = 0

        for tenant in tenants_qs:
            for origem in origens_filtro:
                if origem not in adapters:
                    continue
                adapter = adapters[origem]
                try:
                    iterador = adapter.iter_clientes_ativos(tenant)
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(
                        f'[{tenant.pk}/{origem}] Erro listando clientes: {exc}'
                    ))
                    continue

                processados_aqui = 0
                upserted_aqui = 0
                erros_aqui = 0

                for cliente_nativo in iterador:
                    if options['limit'] and processados_aqui >= options['limit']:
                        break
                    processados_aqui += 1

                    if options['dry_run']:
                        self.stdout.write(f'[DRY] {tenant.nome}/{origem} → {cliente_nativo}')
                        continue

                    try:
                        adapter.sync_cliente(cliente_nativo)
                        upserted_aqui += 1
                    except Exception as exc:
                        erros_aqui += 1
                        logger.error(
                            'Erro sync %s/%s id=%s: %s',
                            origem, tenant.pk, getattr(cliente_nativo, 'pk', '?'), exc,
                        )

                self.stdout.write(self.style.SUCCESS(
                    f'[{tenant.nome}/{origem}] {processados_aqui} processados, '
                    f'{upserted_aqui} upserted, {erros_aqui} erros'
                ))
                total_processados += processados_aqui
                total_upserted += upserted_aqui
                total_erros += erros_aqui

        self.stdout.write(self.style.SUCCESS(
            f'\n=== Total ===\n'
            f'Processados: {total_processados}\n'
            f'Upserted: {total_upserted}\n'
            f'Erros: {total_erros}\n'
            f'Modo: {"dry-run" if options["dry_run"] else "aplicado"}'
        ))
