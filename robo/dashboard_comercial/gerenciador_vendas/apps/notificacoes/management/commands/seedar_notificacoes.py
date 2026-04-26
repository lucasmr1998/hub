"""
Aplica seeds canonicos de TipoNotificacao + CanalNotificacao em todos os
tenants (ou em um especifico via --tenant). Idempotente.

Tenants novos pegam o seed automaticamente via signal post_save em
apps.notificacoes.signals. Esse comando serve pra:
  - Cobrir tenants criados antes da existencia do signal
  - Re-aplicar quando a lista TIPOS_PADRAO em seeds.py crescer
"""
from django.core.management.base import BaseCommand

from apps.sistema.models import Tenant
from apps.notificacoes.seeds import seed_tenant


class Command(BaseCommand):
    help = 'Aplica seeds canonicos de tipos/canais de notificacao em todos os tenants.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', help='Slug de um tenant especifico (default: todos).')

    def handle(self, *args, **options):
        slug = options.get('tenant')
        qs = Tenant.objects.filter(ativo=True)
        if slug:
            qs = qs.filter(slug=slug)

        if not qs.exists():
            self.stdout.write(self.style.WARNING('Nenhum tenant encontrado.'))
            return

        total_tipos = 0
        total_canais = 0
        for tenant in qs:
            resumo = seed_tenant(tenant)
            total_tipos += resumo['tipos_criados']
            total_canais += resumo['canais_criados']
            self.stdout.write(
                f"  [{tenant.slug}] +{resumo['tipos_criados']} tipos, +{resumo['canais_criados']} canais"
            )

        self.stdout.write(self.style.SUCCESS(
            f'\nConcluido. {qs.count()} tenant(s) processados. '
            f'Total: +{total_tipos} tipos, +{total_canais} canais.'
        ))
