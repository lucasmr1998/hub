"""Reconcilia as oportunidades PÓS-VENDA (Novo Serviço / Upgrade) com o
estado real de NewService / UpgradePlano.

Necessário porque o webdriver/polling (HubSoft) atualiza esses registros via
SQL cru, o que NÃO dispara os signals do Django. Rodar periodicamente
(cron a cada ~5 min) garante que as oportunidades avancem (Processando →
Concluído) mesmo sem signal.

    python manage.py crm_reconciliar_posvenda
    python manage.py crm_reconciliar_posvenda --dias 7   # só recentes
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from vendas_web.models import NewService, UpgradePlano
from crm.services.posvenda_sync import sincronizar_new_service, sincronizar_upgrade


class Command(BaseCommand):
    help = 'Sincroniza oportunidades pós-venda (Novo Serviço/Upgrade) com NewService/UpgradePlano.'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=0,
                            help='Só processa registros criados nos últimos N dias (0 = todos).')

    def handle(self, *args, **opts):
        ns_qs = NewService.objects.exclude(lead__isnull=True)
        up_qs = UpgradePlano.objects.exclude(lead__isnull=True)
        if opts['dias']:
            corte = timezone.now() - timedelta(days=opts['dias'])
            ns_qs = ns_qs.filter(criado_em__gte=corte)
            up_qs = up_qs.filter(criado_em__gte=corte)

        n_ns = n_up = 0
        for ns in ns_qs.iterator():
            try:
                if sincronizar_new_service(ns):
                    n_ns += 1
            except Exception as e:
                self.stderr.write(f'NewService {ns.pk}: {e}')
        for up in up_qs.iterator():
            try:
                if sincronizar_upgrade(up):
                    n_up += 1
            except Exception as e:
                self.stderr.write(f'UpgradePlano {up.pk}: {e}')

        self.stdout.write(self.style.SUCCESS(
            f'Reconciliação OK — Novo Serviço: {n_ns} oportunidade(s) | Upgrade: {n_up}'))
