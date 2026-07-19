"""Cria/atualiza a integração Matrix (agenda + atendimento + OS de instalação).

Valores espelhados da produção (apimatrix.megalinkpiaui.com.br).
"""
from django.core.management.base import BaseCommand

from integracoes.models import IntegracaoAPI


class Command(BaseCommand):
    help = 'Cria (ou atualiza) a integração Matrix da Megalink.'

    def handle(self, *args, **options):
        integ, created = IntegracaoAPI.objects.update_or_create(
            tipo='matrix',
            nome='Matrix',
            defaults={
                'base_url': 'https://apimatrix.megalinkpiaui.com.br',
                'ativa': True,
                'configuracoes_extras': {
                    'duracao': '01:30:00',
                    'id_tipo_os': 702,
                    'status_os_api': 'pendente',
                    'nome_empresa_api': 'megalink',
                    'id_tipo_atendimento': 535,
                    'id_user_responsavel': 1618,
                    'id_status_atendimento': 1,
                },
            },
        )
        verbo = 'criada' if created else 'atualizada'
        self.stdout.write(self.style.SUCCESS(f'Integração Matrix {verbo}: {integ.base_url}'))
