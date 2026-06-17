"""
Sincroniza a BASE COMPLETA de clientes HubSoft (com servicos inline) pro
espelho local. Itera /cliente/todos paginado.

Uso:
    # Delta diario (default — clientes modificados nas ultimas 24h):
    python manage.py sync_base_clientes_hubsoft --tenant nuvyon

    # Full sync (todos os clientes, NAO usar pra cron — uso unico/bootstrap):
    python manage.py sync_base_clientes_hubsoft --tenant nuvyon --full

    # Dry-run (so consulta a primeira pagina, nao escreve):
    python manage.py sync_base_clientes_hubsoft --tenant nuvyon --dry-run

    # Sem --tenant, processa TODOS os tenants com IntegracaoAPI hubsoft ativa
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.hubsoft_relatorios import sincronizar_base_clientes
from apps.sistema.models import Tenant

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sincroniza base de clientes HubSoft (com servicos) para espelho local.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, help='Slug do tenant (opcional).')
        parser.add_argument('--full', action='store_true',
            help='Sync completo (sem delta). Use 1x no bootstrap.')
        parser.add_argument('--dias', type=int, default=1,
            help='Delta sync: clientes modificados nos ultimos N dias (default: 1).')
        parser.add_argument('--max-paginas', type=int, default=None,
            help='Limita ao numero de paginas (pra teste/dry-run).')
        parser.add_argument('--dry-run', action='store_true',
            help='So consulta a 1a pagina pra estimar volume. Nao grava.')

    def handle(self, *args, **opts):
        tenants_qs = Tenant.objects.filter(ativo=True)
        if opts.get('tenant'):
            tenants_qs = tenants_qs.filter(slug=opts['tenant'])

        modificados_desde = None
        if not opts.get('full'):
            modificados_desde = timezone.now() - timedelta(days=opts['dias'])

        max_paginas = opts.get('max_paginas')
        if opts.get('dry_run'):
            max_paginas = 1

        total_clientes_geral = 0
        for tenant in tenants_qs:
            integ = IntegracaoAPI.all_tenants.filter(
                tenant=tenant, tipo='hubsoft', ativa=True,
            ).first()
            if not integ:
                continue

            modo = 'FULL' if opts.get('full') else f"delta {opts['dias']}d"
            self.stdout.write(self.style.SUCCESS(
                f'[{tenant.slug}] iniciando sync {modo}... '
                f'(integracao #{integ.id} {integ.nome!r})'
            ))

            res = sincronizar_base_clientes(
                integ,
                modificados_desde=modificados_desde,
                max_paginas=max_paginas,
            )

            cor = self.style.SUCCESS if res.ok and res.erros == 0 else self.style.WARNING
            self.stdout.write(cor(
                f'  [{tenant.slug}] paginas={res.total_paginas} '
                f'registros={res.total_registros} '
                f'criados={res.criados} atualizados={res.atualizados} '
                f'erros={res.erros} dur={res.duracao_seg:.1f}s'
            ))
            if res.mensagens_erro:
                for m in res.mensagens_erro[:5]:
                    self.stdout.write(self.style.ERROR(f'    {m}'))
                if len(res.mensagens_erro) > 5:
                    self.stdout.write(f'    ... +{len(res.mensagens_erro)-5} mensagens de erro')
            total_clientes_geral += res.criados + res.atualizados

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'=== resumo: total clientes processados (todos tenants): {total_clientes_geral} ==='
        ))
