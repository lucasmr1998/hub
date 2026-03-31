import os

from django.core.management.base import BaseCommand, CommandError

from apps.integracoes.models import IntegracaoAPI


class Command(BaseCommand):
    help = 'Cria (ou atualiza) a integração Hubsoft. Credenciais via variáveis de ambiente.'

    def handle(self, *args, **options):
        required_vars = ['HUBSOFT_BASE_URL', 'HUBSOFT_CLIENT_ID', 'HUBSOFT_CLIENT_SECRET', 'HUBSOFT_USERNAME', 'HUBSOFT_PASSWORD']
        missing = [v for v in required_vars if not os.environ.get(v)]
        if missing:
            raise CommandError(f"Variáveis de ambiente faltando: {', '.join(missing)}")

        integracao, created = IntegracaoAPI.objects.update_or_create(
            tipo='hubsoft',
            nome='Hubsoft',
            defaults={
                'base_url': os.environ['HUBSOFT_BASE_URL'],
                'client_id': os.environ['HUBSOFT_CLIENT_ID'],
                'client_secret': os.environ['HUBSOFT_CLIENT_SECRET'],
                'username': os.environ['HUBSOFT_USERNAME'],
                'password': os.environ['HUBSOFT_PASSWORD'],
                'grant_type': 'password',
                'ativa': True,
                'configuracoes_extras': {},
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS(
                f'Integração criada: {integracao.nome} ({integracao.base_url})'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Integração atualizada: {integracao.nome} ({integracao.base_url})'
            ))
