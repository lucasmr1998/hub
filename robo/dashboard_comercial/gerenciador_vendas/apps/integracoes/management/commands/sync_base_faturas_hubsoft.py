"""
Sincroniza faturas HubSoft (espelho) — itera clientes ativos do tenant e
chama /cliente/financeiro por cliente (HubSoft nao tem /faturas/todos).

Uso:
    python manage.py sync_base_faturas_hubsoft --tenant nuvyon
    python manage.py sync_base_faturas_hubsoft --tenant nuvyon --max-clientes 10  # teste
"""
from django.core.management.base import BaseCommand

from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.hubsoft_relatorios import sincronizar_base_faturas
from apps.sistema.models import Tenant


class Command(BaseCommand):
    help = 'Sincroniza faturas HubSoft (espelho) por cliente do tenant.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, help='Slug do tenant.')
        parser.add_argument('--max-clientes', type=int, default=None,
            help='Limita ao numero de clientes (pra teste).')
        parser.add_argument('--rate-limit', type=float, default=1.0,
            help='Pausa entre clientes em segundos (default 1.0).')
        parser.add_argument('--limit-por-cliente', type=int, default=50,
            help='Max faturas retornadas por cliente (default 50).')
        parser.add_argument('--apenas-ativos', action='store_true', default=True,
            help='Filtrar clientes com servico ativo (default True).')

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
                f'[{tenant.slug}] sync faturas (rate {opts["rate_limit"]}s/cliente)...'
            ))
            res = sincronizar_base_faturas(
                integ,
                apenas_status_servico='servico_habilitado' if opts['apenas_ativos'] else '',
                max_clientes=opts.get('max_clientes'),
                rate_limit_seg=opts['rate_limit'],
                limit_por_cliente=opts['limit_por_cliente'],
            )
            cor = self.style.SUCCESS if res.ok and res.erros == 0 else self.style.WARNING
            self.stdout.write(cor(
                f'  clientes processados={res.total_registros} '
                f'criados={res.criados} atualizados={res.atualizados} '
                f'erros={res.erros} dur={res.duracao_seg:.1f}s'
            ))
            for m in res.mensagens_erro[:5]:
                self.stdout.write(self.style.ERROR(f'  {m}'))
