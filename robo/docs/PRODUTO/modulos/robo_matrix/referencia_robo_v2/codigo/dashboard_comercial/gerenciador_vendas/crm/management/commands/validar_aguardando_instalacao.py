"""
DEPRECADO: Use 'python manage.py revalidar_pipeline' no lugar deste comando.

Este comando agora é um wrapper que chama revalidar_pipeline para manter
compatibilidade com scripts existentes.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = '[DEPRECADO] Use revalidar_pipeline. Reavalia oportunidades no pipeline usando regras configuradas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Simula sem gravar',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            '\n  AVISO: Este comando foi deprecado.\n'
            '  Use: python manage.py revalidar_pipeline\n'
            '  Redirecionando...\n'
        ))

        from django.core.management import call_command
        call_args = []
        if options['dry_run']:
            call_args.append('--dry-run')
        call_command('revalidar_pipeline', *call_args)
