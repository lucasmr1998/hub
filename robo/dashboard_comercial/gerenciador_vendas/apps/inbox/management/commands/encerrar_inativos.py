"""
Encerra automaticamente conversas humanas inativas (multi-tenant).

Regra por tenant (em ConfiguracaoInbox):
  - encerramento_auto_ativo = True
  - status in ('aberta', 'pendente')
  - modo_atendimento = 'humano'
  - ultima_mensagem_em < agora - encerramento_auto_horas
  → encerrar_por_inatividade (envia aviso configurado, se ligado, e seta motivo
    de sistema 'Encerramento automatico').

Uso:
    python manage.py encerrar_inativos
    python manage.py encerrar_inativos --dry-run
    python manage.py encerrar_inativos --tenant tr-carrion
    python manage.py encerrar_inativos --horas 24
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Encerra conversas humanas inativas (regra em ConfiguracaoInbox por tenant)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Simula sem encerrar')
        parser.add_argument('--tenant', type=str, default=None,
                            help='Roda apenas para um tenant (slug)')
        parser.add_argument('--horas', type=int, default=None,
                            help='Sobrescreve o limite configurado por tenant')

    def handle(self, *args, **opts):
        from apps.sistema.models import Tenant
        from apps.sistema.middleware import set_current_tenant
        from apps.inbox.models import ConfiguracaoInbox, Conversa
        from apps.inbox.services import encerrar_por_inatividade

        dry = opts['dry_run']
        slug = opts['tenant']
        horas_override = opts['horas']

        tenants = Tenant.objects.filter(ativo=True)
        if slug:
            tenants = tenants.filter(slug=slug)

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n[Encerrar Inativos]{" [DRY RUN]" if dry else ""}'
        ))

        total_encerradas = 0
        for t in tenants:
            cfg = ConfiguracaoInbox.all_tenants.filter(tenant=t).first()
            if not cfg or not cfg.encerramento_auto_ativo:
                continue

            horas = horas_override if horas_override is not None else cfg.encerramento_auto_horas
            limite = timezone.now() - timedelta(hours=horas)

            candidatas = (
                Conversa.all_tenants
                .filter(
                    tenant=t,
                    status__in=['aberta', 'pendente'],
                    modo_atendimento='humano',
                    ultima_mensagem_em__lt=limite,
                )
                .select_related('canal')
            )

            n = candidatas.count()
            self.stdout.write(
                f'  [{t.slug}] horas={horas} candidatas={n}'
            )
            if n == 0:
                continue

            if dry:
                for c in candidatas[:10]:
                    self.stdout.write(
                        f'    [DRY] #{c.numero} {c.contato_nome or c.contato_telefone} '
                        f'· ultima_mensagem_em={c.ultima_mensagem_em:%Y-%m-%d %H:%M}'
                    )
                if n > 10:
                    self.stdout.write(f'    ... e mais {n - 10}')
                total_encerradas += n
                continue

            set_current_tenant(t)
            try:
                for c in candidatas:
                    try:
                        encerrar_por_inatividade(c)
                        total_encerradas += 1
                    except Exception as e:
                        self.stderr.write(
                            f'    erro ao encerrar conversa #{c.numero}: {e}'
                        )
            finally:
                set_current_tenant(None)

        self.stdout.write(self.style.SUCCESS(
            f'\n  Total {"simulado" if dry else "encerrado"}: {total_encerradas}\n'
        ))
