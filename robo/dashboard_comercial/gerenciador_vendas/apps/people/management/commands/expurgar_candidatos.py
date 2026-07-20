"""
Expurgo LGPD do banco de talentos.

Anonimiza candidatos cujo prazo de retencao venceu. E a materializacao da
decisao D3: o banco de talentos guarda dado pessoal por tempo declarado, e
depois disso o dado da pessoa some sozinho, sem ninguem precisar lembrar.

Anonimiza, nao deleta: a linha e a origem do candidato sobrevivem pra que a
analise de canal nao minta retroativamente sobre quantos candidatos chegaram.
O que some e a pessoa (nome, WhatsApp, email, endereco) e o arquivo do
curriculo. Ver Candidato.anonimizar().

Roda pelo dispatcher_cron, uma vez por dia. Idempotente: candidato ja
anonimizado nao entra na fila de novo (o filtro exige anonimizado_em nulo).

Uso:
    python manage.py expurgar_candidatos
    python manage.py expurgar_candidatos --dry-run   # so conta, nao anonimiza
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Anonimiza candidatos cujo prazo de retencao LGPD venceu.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='So conta quantos venceram, sem anonimizar.')

    def handle(self, *args, **opts):
        # Import tardio: comando carrega antes do app registry em alguns fluxos.
        from apps.people.models import Candidato

        hoje = timezone.localdate()

        # `all_tenants` de proposito: o expurgo e uma obrigacao legal que vale
        # pra todos os tenants de uma vez, e nao ha request pra dar escopo. O
        # filtro por retencao_ate ja garante que so vencidos entram.
        vencidos = Candidato.all_tenants.filter(
            retencao_ate__lt=hoje,
            anonimizado_em__isnull=True,
        )

        total = vencidos.count()

        if opts['dry_run']:
            self.stdout.write(
                f'{total} candidatos com retencao vencida (nada anonimizado, '
                f'--dry-run).')
            return

        anonimizados = 0
        # Itera e chama o metodo do model, em vez de um update em massa: o
        # update nao apagaria o arquivo do curriculo, que e o dado mais
        # sensivel. anonimizar() cuida do arquivo e da linha juntos.
        for candidato in vencidos.iterator():
            candidato.anonimizar()
            anonimizados += 1

        self.stdout.write(self.style.SUCCESS(
            f'{anonimizados} candidatos anonimizados (retencao vencida).'))
