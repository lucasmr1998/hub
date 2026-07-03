"""
Importa prospects criados pelo Talk (softphone) no HubSoft pra dentro do CRM.

Uso:
    python manage.py importar_prospects_talk --tenant=nuvyon
    python manage.py importar_prospects_talk --tenant=nuvyon --dry-run
    python manage.py importar_prospects_talk --tenant=nuvyon --desde=2026-07-01
    python manage.py importar_prospects_talk                       # todos os tenants

Cron sugerido: `* * * * *` (a cada 1 min). Cada execucao filtra pelos criados
desde a data especificada em --desde (default: hoje BRT), pega no HubSoft,
faz anti-duplicacao e cria op no CRM.
"""
from datetime import datetime

from django.core.management.base import BaseCommand

from apps.integracoes.services.importador_prospects_talk import importar_prospects_talk
from apps.sistema.models import Tenant


class Command(BaseCommand):
    help = 'Importa prospects Talk do HubSoft pro CRM (Lead + Oportunidade).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', help='slug do tenant (default: todos com hubsoft ativo)')
        parser.add_argument('--desde', help='data YYYY-MM-DD (default: hoje BRT)')
        parser.add_argument('--limit', type=int, help='max de prospects a processar')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        slug = opts.get('tenant')
        desde_str = opts.get('desde')
        limit = opts.get('limit')
        dry = opts.get('dry_run', False)

        desde = None
        if desde_str:
            desde = datetime.strptime(desde_str, '%Y-%m-%d').date()

        tenants = Tenant.objects.filter(ativo=True)
        if slug:
            tenants = tenants.filter(slug=slug)

        total_criados = 0
        total_vinculados = 0
        total_ja = 0
        total_falhas = 0

        for tenant in tenants:
            r = importar_prospects_talk(tenant, desde=desde, limit=limit, dry_run=dry)
            self.stdout.write(
                f"[{tenant.slug}] encontrados={r.encontrados} "
                f"criados={r.criados} vinculados={r.vinculados_por_telefone} "
                f"ja_importados={r.ja_importados} pulados_data={r.pulados_por_data} "
                f"falhas={len(r.falhas)}"
            )
            if r.falhas:
                for f in r.falhas[:5]:
                    self.stdout.write(self.style.WARNING(f"  falha: {f}"))
            total_criados += r.criados
            total_vinculados += r.vinculados_por_telefone
            total_ja += r.ja_importados
            total_falhas += len(r.falhas)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Total: criados={total_criados} vinculados={total_vinculados} '
            f'ja_importados={total_ja} falhas={total_falhas}'
        ))
