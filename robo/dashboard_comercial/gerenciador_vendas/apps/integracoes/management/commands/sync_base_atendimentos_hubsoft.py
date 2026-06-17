"""
Sincroniza atendimentos HubSoft (chamados) para espelho local.
Itera /atendimento/todos paginado.

Uso:
    python manage.py sync_base_atendimentos_hubsoft --tenant nuvyon
    python manage.py sync_base_atendimentos_hubsoft --tenant nuvyon --dias 90
"""
from django.core.management.base import BaseCommand

from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.hubsoft_relatorios import sincronizar_base_atendimentos
from apps.sistema.models import Tenant


class Command(BaseCommand):
    help = 'Sincroniza atendimentos HubSoft (espelho) para o tenant.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, help='Slug do tenant.')
        parser.add_argument('--dias', type=int, default=30,
            help='Atendimentos dos ultimos N dias (default: 30).')
        parser.add_argument('--max-paginas', type=int, default=None)

    def handle(self, *args, **opts):
        tenants_qs = Tenant.objects.filter(ativo=True)
        if opts.get('tenant'):
            tenants_qs = tenants_qs.filter(slug=opts['tenant'])

        for tenant in tenants_qs:
            integ = IntegracaoAPI.all_tenants.filter(
                tenant=tenant, tipo='hubsoft', ativa=True,
            ).first()
            if not integ:
                continue

            self.stdout.write(self.style.SUCCESS(
                f'[{tenant.slug}] sync atendimentos (ultimos {opts["dias"]} dias)...'
            ))
            res = sincronizar_base_atendimentos(
                integ, dias=opts['dias'], max_paginas=opts.get('max_paginas'),
            )
            cor = self.style.SUCCESS if res.ok and res.erros == 0 else self.style.WARNING
            self.stdout.write(cor(
                f'  paginas={res.total_paginas} registros={res.total_registros} '
                f'criados={res.criados} atualizados={res.atualizados} '
                f'erros={res.erros} dur={res.duracao_seg:.1f}s'
            ))
            for m in res.mensagens_erro[:5]:
                self.stdout.write(self.style.ERROR(f'  {m}'))
