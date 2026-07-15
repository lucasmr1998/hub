"""Registra as ligacoes do Talk como HistoricoContato (timeline da oportunidade).

Roda no cron (a cada poucos minutos, --dias curto) e serve de backfill (--dias
grande, uma vez). Idempotente por cod_cdr.

Uso:
    python manage.py registrar_ligacoes_talk --tenant nuvyon
    python manage.py registrar_ligacoes_talk --tenant nuvyon --dias 30 --dry-run
"""
from django.core.management.base import BaseCommand

from apps.integracoes.services.registrar_ligacoes_talk import registrar_ligacoes_talk
from apps.sistema.models import Tenant


class Command(BaseCommand):
    help = 'Cria um HistoricoContato por ligacao do Talk (pra aparecer na timeline).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', help='Slug do tenant. Sem isso, todos com Talk ativo.')
        parser.add_argument('--dias', type=int, default=7)
        parser.add_argument('--limit', type=int, default=None)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        tenants = Tenant.objects.filter(ativo=True)
        if opts.get('tenant'):
            tenants = tenants.filter(slug=opts['tenant'])

        for tenant in tenants:
            r = registrar_ligacoes_talk(
                tenant, dias=opts['dias'], limit=opts['limit'], dry_run=opts['dry_run'],
            )
            if r.leads_processados == 0:
                continue
            self.stdout.write(
                f'[{tenant.slug}] leads={r.leads_processados} '
                f'ligacoes_criadas={r.ligacoes_criadas} ja_existiam={r.ja_existiam} '
                f'sem_chamada={r.sem_chamada} erros={r.erros}'
            )
            for m in r.mensagens[:15]:
                self.stdout.write(f'  {m}')
        if opts['dry_run']:
            self.stdout.write(self.style.WARNING('\nDRY-RUN: nada gravado.'))
