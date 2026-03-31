from django.core.management.base import BaseCommand
from gestao.faq_service import FAQService


class Command(BaseCommand):
    help = 'Gera/atualiza FAQs automaticamente usando IA'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Forca regeneracao de todas')
        parser.add_argument('--categoria', type=str, help='Atualiza apenas uma categoria (slug)')
        parser.add_argument('--dry-run', action='store_true', help='Mostra o que seria gerado sem salvar')

    def handle(self, *args, **options):
        self.stdout.write("Verificando categorias...")
        FAQService.garantir_categorias()

        self.stdout.write("Gerando FAQs...")
        resultado = FAQService.atualizar_faqs(
            force=options['force'],
            categoria_slug=options.get('categoria'),
            dry_run=options['dry_run'],
        )

        for cat, status in resultado.items():
            if 'atualizado' in str(status):
                self.stdout.write(self.style.SUCCESS(f"  {cat}: {status}"))
            elif status == 'sem_mudanca':
                self.stdout.write(f"  {cat}: sem mudanca")
            elif status == 'sem_dados':
                self.stdout.write(self.style.WARNING(f"  {cat}: sem dados"))
            else:
                self.stdout.write(self.style.ERROR(f"  {cat}: {status}"))

        self.stdout.write(self.style.SUCCESS("Concluido!"))
