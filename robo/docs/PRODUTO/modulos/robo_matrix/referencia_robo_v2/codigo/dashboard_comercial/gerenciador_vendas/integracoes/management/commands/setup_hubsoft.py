from django.core.management.base import BaseCommand

from integracoes.models import IntegracaoAPI


class Command(BaseCommand):
    help = 'Cria (ou atualiza) a integração Hubsoft com as credenciais padrão da Megalink.'

    def handle(self, *args, **options):
        integracao, created = IntegracaoAPI.objects.update_or_create(
            tipo='hubsoft',
            nome='Hubsoft Megalink',
            defaults={
                'base_url': 'https://api.megalinktelecom.hubsoft.com.br',
                'client_id': '103',
                'client_secret': '***REMOVIDO***',
                'username': '***REMOVIDO***',
                'password': '***REMOVIDO***',
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
