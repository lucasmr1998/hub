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
        from apps.notificacoes.models import TipoNotificacao
        from apps.notificacoes.services.notificacao_service import criar_notificacao
        from django.contrib.auth.models import User

        horas = opts['horas']
        dry = opts['dry_run']
        limite = timezone.now() - timedelta(hours=horas)

        estagios_alvo = PipelineEstagio.all_tenants.filter(
            slug='aguardando-vendedor', ativo=True
        )
        if not estagios_alvo.exists():
            self.stdout.write('Nenhum estagio "aguardando-vendedor" cadastrado. Saindo.')
            return

        total = 0
        for estagio in estagios_alvo:
            # Garante TipoNotificacao existe pro tenant (idempotente)
            TipoNotificacao.all_tenants.get_or_create(
                tenant=estagio.tenant, codigo='sla_aguardando_vendedor',
                defaults={
                    'nome': 'Lead aguardando vendedor (SLA)',
                    'descricao': 'Lead em "Aguardando Vendedor" excedeu o SLA configurado',
                    'icone': 'bi-clock-history',
                    'cor': 'warning',
                    'prioridade_padrao': 'alta',
                    'ativo': True,
                }
            )

            ops = OportunidadeVenda.all_tenants.filter(
                tenant=estagio.tenant,
                estagio=estagio,
                data_entrada_estagio__lt=limite,
            )

            for op in ops:
                dados = op.dados_custom or {}
                ultimo_alerta = dados.get('_sla_ultimo_alerta')
                if ultimo_alerta:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(ultimo_alerta)
                        if (timezone.now() - dt) < timedelta(hours=horas):
                            continue
                    except (ValueError, TypeError):
                        pass

                destinatarios = []
                if op.responsavel_id:
                    destinatarios = [op.responsavel]
                else:
                    destinatarios = list(User.objects.filter(
                        is_active=True,
                        userpermissao__tenant=op.tenant
                    ).distinct()[:5])

                titulo = f'Lead aguardando ha {horas}h+'
                msg = (
                    f'Lead {op.titulo!r} esta aguardando vendedor.\n'
                    f'Telefone: {op.lead.telefone if op.lead else "?"}\n'
                    f'Estagio: {estagio.nome}'
                )

                for user in destinatarios:
                    if dry:
                        self.stdout.write(f'[DRY] Notificaria {user.username}: {titulo}')
                        continue
                    criar_notificacao(
                        tenant=op.tenant,
                        codigo_tipo='sla_aguardando_vendedor',
                        titulo=titulo,
                        mensagem=msg,
                        destinatario=user,
                        url_acao=f'/crm/oportunidades/{op.id}/',
                        dados_contexto={
                            'oportunidade_id': op.id,
                            'lead_id': op.lead_id,
                            'horas_aguardando': horas,
                        },
                    )
                    total += 1

                if not dry:
                    dados['_sla_ultimo_alerta'] = timezone.now().isoformat()
                    op.dados_custom = dados
                    op.save(update_fields=['dados_custom'])

        self.stdout.write(self.style.SUCCESS(f'Notificacoes criadas: {total}'))
