"""
Alerta supervisor/vendedor quando lead está em "Aguardando Vendedor" há mais de X horas.

Cron sugerido (a cada 30min):
    */30 * * * * python manage.py alertar_sla_vendedor --horas=4
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Alerta quando lead esta em "Aguardando Vendedor" ha > X horas'

    def add_arguments(self, parser):
        parser.add_argument('--horas', type=int, default=4)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        from apps.comercial.crm.models import OportunidadeVenda, PipelineEstagio
        from apps.notificacoes.models import Notificacao, TipoNotificacao
        from apps.sistema.models import Tenant
        from django.contrib.auth.models import User

        horas = opts['horas']
        dry = opts['dry_run']
        limite = timezone.now() - timedelta(hours=horas)

        # Estagios "Aguardando Vendedor" (qualificacao tipo, slug aguardando-vendedor)
        estagios_alvo = PipelineEstagio.all_tenants.filter(
            slug='aguardando-vendedor', ativo=True
        )
        if not estagios_alvo.exists():
            self.stdout.write('Nenhum estagio "aguardando-vendedor" cadastrado. Saindo.')
            return

        total = 0
        for estagio in estagios_alvo:
            # Oportunidades nesse estagio ha mais de X horas
            ops = OportunidadeVenda.all_tenants.filter(
                tenant=estagio.tenant,
                estagio=estagio,
                data_entrada_estagio__lt=limite,
            )

            for op in ops:
                # Evita duplicar: checa se ja notificou nas ultimas X horas
                dados = op.dados_custom or {}
                ultimo_alerta = dados.get('_sla_ultimo_alerta')
                if ultimo_alerta:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(ultimo_alerta)
                        if (timezone.now() - dt) < timedelta(hours=horas):
                            continue  # ja foi notificado recentemente
                    except (ValueError, TypeError):
                        pass

                # Decide quem notifica: responsavel ou todos admins do tenant
                destinatarios = []
                if op.responsavel_id:
                    destinatarios = [op.responsavel]
                else:
                    # Notifica admins do tenant
                    destinatarios = list(User.objects.filter(
                        is_active=True, is_superuser=False,
                        userpermissao__tenant=op.tenant
                    ).distinct()[:5])

                msg = (
                    f'⏰ Lead {op.titulo!r} esta aguardando vendedor ha mais de {horas}h.\n'
                    f'Telefone: {op.lead.telefone if op.lead else "?"}\n'
                    f'Estagio: {estagio.nome}'
                )

                for user in destinatarios:
                    if dry:
                        self.stdout.write(f'[DRY] Notificaria {user.username}: {msg[:80]}')
                    else:
                        tipo, _ = TipoNotificacao.all_tenants.get_or_create(
                            tenant=op.tenant, codigo='sla_aguardando_vendedor',
                            defaults={'nome': 'Lead aguardando vendedor (SLA)',
                                      'descricao': 'Lead em "Aguardando Vendedor" excedeu SLA',
                                      'icone': 'bi-clock-history',
                                      'cor': 'warning'}
                        )
                        Notificacao.objects.create(
                            tenant=op.tenant, tipo=tipo, user=user,
                            titulo=f'Lead aguardando ha {horas}h+',
                            mensagem=msg,
                            link=f'/crm/oportunidades/{op.id}/',
                        )
                        total += 1

                # Marca como notificado
                if not dry:
                    dados['_sla_ultimo_alerta'] = timezone.now().isoformat()
                    op.dados_custom = dados
                    op.save(update_fields=['dados_custom'])

        self.stdout.write(self.style.SUCCESS(f'Notificacoes criadas: {total}'))
