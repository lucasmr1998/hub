import os

from django.core.management.base import BaseCommand, CommandError

from apps.integracoes.models import IntegracaoAPI


class Command(BaseCommand):
    help = (
        'Cria (ou atualiza) a integração SGP (inSystem). '
        'Credenciais via variáveis de ambiente: SGP_BASE_URL, SGP_APP, SGP_TOKEN.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--nome',
            default='SGP',
            help='Nome da integração (default: "SGP")',
        )

    def handle(self, *args, **options):
        required_vars = ['SGP_BASE_URL', 'SGP_APP', 'SGP_TOKEN']
        missing = [v for v in required_vars if not os.environ.get(v)]
        if missing:
            raise CommandError(
                f"Variáveis de ambiente faltando: {', '.join(missing)}. "
                f"Exporte SGP_BASE_URL, SGP_APP e SGP_TOKEN antes de rodar."
            )

        defaults = {
            'base_url': os.environ['SGP_BASE_URL'],
            'client_id': os.environ['SGP_APP'],       # app SGP mora em client_id
            'client_secret': '',                       # SGP não usa client_secret
            'username': '',                            # reservado para fallback Basic
            'password': '',                            # reservado para fallback Basic
            'access_token': os.environ['SGP_TOKEN'],   # token estático do SGP
            'grant_type': 'token_app',
            'ativa': True,
            'configuracoes_extras': {},
        }

        integracao, created = IntegracaoAPI.objects.update_or_create(
            tipo='sgp',
            nome=options['nome'],
            defaults=defaults,
        )

        if created:
            self.stdout.write(self.style.SUCCESS(
                f"Integração SGP criada: {integracao.nome} ({integracao.base_url})"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Integração SGP atualizada: {integracao.nome} ({integracao.base_url})"
            ))

        self.stdout.write(
            "\nPróximo passo: rodar `python manage.py shell` e testar:\n"
            "  from apps.integracoes.models import IntegracaoAPI\n"
            "  from apps.integracoes.services.sgp import SGPService\n"
            f"  i = IntegracaoAPI.objects.get(pk={integracao.pk})\n"
            "  SGPService(i).validar_credenciais()  # deve retornar True\n"
        )
