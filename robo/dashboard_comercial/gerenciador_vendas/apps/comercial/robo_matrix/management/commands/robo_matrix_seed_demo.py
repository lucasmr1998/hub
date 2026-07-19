"""Seed de DEV para o adaptador robo_matrix.

Cria 2 tenants de teste, cada um com uma IntegracaoAPI ativa cujo `api_token`
identifica a empresa na URL (/robo/<token>/ia/...). Serve para exercitar a
resolucao de tenant por token e o isolamento entre empresas, sem tocar em nada
real. Idempotente (get_or_create por slug/token).

NAO rodar em producao: e dado sintetico de homologacao local.

Uso:
    python manage.py robo_matrix_seed_demo --settings=gerenciador_vendas.settings_local
"""
from django.core.management.base import BaseCommand
from django.db import transaction

DEMOS = [
    {'slug': 'demo-alpha', 'nome': 'Provedor Demo Alpha', 'token': 'robo-demo-alpha-token'},
    {'slug': 'demo-beta', 'nome': 'Provedor Demo Beta', 'token': 'robo-demo-beta-token'},
]


class Command(BaseCommand):
    help = 'Cria tenants e tokens de demonstracao para o adaptador robo_matrix (DEV).'

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.sistema.models import Tenant
        from apps.integracoes.models import IntegracaoAPI

        for d in DEMOS:
            tenant, criado_t = Tenant.objects.get_or_create(
                slug=d['slug'],
                defaults={'nome': d['nome'], 'modulo_comercial': True, 'ativo': True},
            )
            integ, criado_i = IntegracaoAPI.all_tenants.get_or_create(
                tenant=tenant,
                api_token=d['token'],
                defaults={
                    'nome': f"Robo Matrix {d['nome']}",
                    'tipo': 'n8n',
                    'ativa': True,
                    'client_id': '',
                    'client_secret': '',
                    'username': '',
                    'password': '',
                },
            )
            self.stdout.write(self.style.SUCCESS(
                f"tenant={tenant.slug} (novo={criado_t})  token={d['token']} (novo={criado_i})"
            ))

        self.stdout.write(self.style.SUCCESS(
            '\nTeste: GET /robo/robo-demo-alpha-token/ia/ping deve devolver o tenant demo-alpha.'
        ))
