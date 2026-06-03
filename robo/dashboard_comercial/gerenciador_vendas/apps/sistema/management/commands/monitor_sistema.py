"""Cron monitor: detecta condicoes de alerta e dispara via uazapi.

Tarefa Workspace #152. Cron sugerido: `* * * * *` (1 min) ou `*/5 * * * *`.

Detecta:
- Webhook N8N retornando 5xx repetido nas ultimas 5min
- HubSoft API com 3+ erros consecutivos nas ultimas 10min
- Leads em status erro/cpf_invalido/vendedor_invalido ha > 1h sem atualizacao
- IntegracaoAPI uazapi sem token

Cada um chama disparar_alerta() com dedup_key proprio. Repeticao na janela
de 5min (config default) suprime envio WhatsApp.

Nao roda detecao de cron_falhou aqui — isso eh feito por signal pra ser
imediato (apps/cron/signals.py).
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Monitor de sistema — detecta condicoes de alerta e dispara.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Apenas lista, nao dispara alertas.')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        self.stdout.write(self.style.SUCCESS('Monitor sistema rodando...'))

        checks = [
            self._check_webhook_5xx,
            self._check_hubsoft_errors,
            self._check_leads_travados,
            self._check_uazapi_sem_token,
        ]
        for check in checks:
            try:
                check(dry_run=dry_run)
            except Exception as e:
                logger.error('[monitor] check %s falhou: %s', check.__name__, e)
                self.stdout.write(self.style.ERROR(f'  {check.__name__}: {e}'))

        self.stdout.write(self.style.SUCCESS('Monitor concluido.'))

    # ─────────────── Checks individuais ───────────────

    def _check_webhook_5xx(self, dry_run=False):
        """Webhook N8N retornando 5xx nas ultimas 5min."""
        try:
            from apps.integracoes.models_audit import LogWebhookN8N
        except ImportError:
            return  # modulo opcional
        janela = timezone.now() - timedelta(minutes=5)
        qs = LogWebhookN8N.objects.filter(
            criado_em__gte=janela, status_code__gte=500,
        )
        n = qs.count()
        if n < 3:
            return
        ultimo = qs.order_by('-criado_em').first()
        msg = (
            f'{n} webhooks N8N retornaram 5xx nas ultimas 5min.\n'
            f'Ultimo: {ultimo.endpoint} status {ultimo.status_code} em {ultimo.criado_em}\n'
            f'Body preview: {(ultimo.body_preview or "")[:200]}'
        )
        self._disparar(dry_run, 'webhook_5xx',
                       f'{n} webhooks N8N com 5xx em 5min', msg,
                       dedup_key=f'webhook_5xx:5min')

    def _check_hubsoft_errors(self, dry_run=False):
        """3+ chamadas HubSoft falhando nas ultimas 10min."""
        from apps.integracoes.models import LogIntegracao
        janela = timezone.now() - timedelta(minutes=10)
        qs = LogIntegracao.objects.filter(
            data_criacao__gte=janela, sucesso=False,
            integracao__tipo='hubsoft',
        )
        n = qs.count()
        if n < 3:
            return
        ultimo = qs.order_by('-data_criacao').first()
        tenant_slug = ultimo.tenant.slug if ultimo and ultimo.tenant else 'desconhecido'
        msg = (
            f'{n} chamadas HubSoft falharam nas ultimas 10min ({tenant_slug}).\n'
            f'Ultimo erro: status {ultimo.status_code} em {ultimo.endpoint}\n'
            f'Mensagem: {(ultimo.mensagem_erro or "")[:300]}'
        )
        self._disparar(dry_run, 'hubsoft_erro',
                       f'HubSoft API com {n} erros em 10min ({tenant_slug})', msg,
                       dedup_key=f'hubsoft_erro:{tenant_slug}',
                       tenant=ultimo.tenant if ultimo else None)

    def _check_leads_travados(self, dry_run=False):
        """Leads com status_api de erro ha > 1h sem atualizacao."""
        from apps.comercial.leads.models import LeadProspecto
        janela = timezone.now() - timedelta(hours=1)
        status_erro = ['erro', 'cpf_invalido', 'vendedor_invalido', 'regra_negocio']
        qs = LeadProspecto.all_tenants.filter(
            status_api__in=status_erro,
            data_atualizacao__lt=janela,
        )
        n = qs.count()
        if n == 0:
            return
        # Agrupa por tenant
        from collections import Counter
        por_tenant = Counter()
        for lead in qs[:50]:  # limita pra nao explodir
            slug = lead.tenant.slug if lead.tenant else '?'
            por_tenant[slug] += 1
        resumo = '\n'.join(f'  {slug}: {c}' for slug, c in por_tenant.most_common())
        msg = (
            f'{n} leads parados em status erro ha > 1h.\n\n'
            f'Por tenant (top):\n{resumo}\n\n'
            'Veja em /admin/leads/leadprospecto/?status_api__in=erro,cpf_invalido,'
            'vendedor_invalido,regra_negocio'
        )
        self._disparar(dry_run, 'lead_travado',
                       f'{n} leads parados em erro ha > 1h', msg,
                       dedup_key='lead_travado:agregado',
                       dados_extras=dict(por_tenant))

    def _check_uazapi_sem_token(self, dry_run=False):
        """IntegracaoAPI uazapi ativa sem token configurado."""
        from apps.integracoes.models import IntegracaoAPI
        sem_token = []
        for i in IntegracaoAPI.all_tenants.filter(tipo='uazapi', ativa=True):
            token = (i.configuracoes_extras or {}).get('token', '')
            if not token:
                sem_token.append(i.tenant.slug if i.tenant else f'sem_tenant#{i.id}')
        if not sem_token:
            return
        msg = (
            f'{len(sem_token)} IntegracaoAPI uazapi ativa(s) sem token:\n'
            + '\n'.join(f'  - {s}' for s in sem_token)
        )
        self._disparar(dry_run, 'uazapi_caiu',
                       f'{len(sem_token)} uazapi sem token', msg,
                       dedup_key='uazapi_sem_token')

    # ─────────────── Helper ───────────────

    def _disparar(self, dry_run, tipo, titulo, mensagem, dedup_key=None,
                  dados_extras=None, tenant=None):
        if dry_run:
            self.stdout.write(self.style.WARNING(f'  [DRY-RUN] {tipo}: {titulo}'))
            return
        from apps.sistema.services_alertas import disparar_alerta
        alerta = disparar_alerta(
            tipo=tipo, titulo=titulo, mensagem=mensagem,
            dedup_key=dedup_key, dados_extras=dados_extras, tenant=tenant,
        )
        if alerta.suprimido:
            self.stdout.write(f'  {tipo}: criado mas suprimido (dedup)')
        elif alerta.enviado_em:
            self.stdout.write(self.style.SUCCESS(f'  {tipo}: enviado ({titulo})'))
        else:
            self.stdout.write(self.style.ERROR(f'  {tipo}: erro envio: {alerta.erro_envio}'))
