"""
Recalcula churn_score de todos os ClienteHubsoft ativos.

Roda preferencialmente 1x/dia (madrugada). Atualiza:
- ClienteHubsoft.churn_score
- ClienteHubsoft.churn_sinais (breakdown JSON)
- ClienteHubsoft.churn_atualizado_em

Notifica gerentes CS quando cliente passa de saudável → alto_risco
(transição de classe, não a cada execução).

Uso:
    python manage.py atualizar_churn_score --settings=gerenciador_vendas.settings_local

Crontab sugerido:
    0 4 * * *  python manage.py atualizar_churn_score
"""
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Recalcula churn score de clientes ativos e notifica gerente CS em transições de classe'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=None)

    def handle(self, *args, **options):
        from apps.integracoes.models import ClienteHubsoft
        from apps.integracoes.services import churn_score

        dry = options['dry_run']
        limit = options['limit']

        qs = ClienteHubsoft.objects.filter(ativo=True).select_related('lead', 'tenant')
        if limit:
            qs = qs[:limit]

        atualizados = 0
        novos_alto_risco = []
        agora = timezone.now()

        for cliente in qs:
            score_anterior = cliente.churn_score
            classe_anterior = churn_score.classificar(score_anterior)

            score, sinais = churn_score.calcular(cliente)
            classe_atual = churn_score.classificar(score)

            if not dry:
                cliente.churn_score = score
                cliente.churn_sinais = sinais
                cliente.churn_atualizado_em = agora
                cliente.save(update_fields=['churn_score', 'churn_sinais', 'churn_atualizado_em'])
                atualizados += 1

            # Detectar transição pra alto_risco
            if classe_atual == 'alto_risco' and classe_anterior != 'alto_risco':
                novos_alto_risco.append((cliente, score, sinais))

        # Notificar gerentes CS dos novos alto-risco
        if not dry and novos_alto_risco:
            self._notificar_gerentes_cs(novos_alto_risco)

        self.stdout.write(self.style.SUCCESS(
            f'\nClientes processados: {qs.count()}\n'
            f'Atualizados: {atualizados}\n'
            f'Novos alto-risco: {len(novos_alto_risco)}\n'
            f'Modo: {"dry-run" if dry else "aplicado"}'
        ))

    def _notificar_gerentes_cs(self, lista_clientes):
        """Manda notificação pra todos os usuários com perfil 'Gerente CS' do tenant."""
        try:
            from django.contrib.auth.models import User
            from apps.notificacoes.services import criar_notificacao

            # Agrupar por tenant
            por_tenant = {}
            for cliente, score, sinais in lista_clientes:
                por_tenant.setdefault(cliente.tenant_id, []).append((cliente, score, sinais))

            for tenant_id, clientes in por_tenant.items():
                gerentes = User.objects.filter(
                    perfil__tenant_id=tenant_id,
                    permissoes__perfil__nome__in=['Gerente CS', 'Operador CS', 'Admin'],
                    is_active=True,
                ).distinct()

                if not gerentes.exists():
                    continue

                for gerente in gerentes:
                    nomes = ', '.join(c.nome_razaosocial for c, _, _ in clientes[:3])
                    extra = f' e mais {len(clientes) - 3}' if len(clientes) > 3 else ''
                    criar_notificacao(
                        tenant=clientes[0][0].tenant,
                        codigo_tipo='cliente_em_risco',  # pode não existir; cair no fallback
                        titulo=f'{len(clientes)} cliente(s) em risco de churn',
                        mensagem=f'Novo alto-risco: {nomes}{extra}',
                        destinatario=gerente,
                        url_acao='/dashboard/clientes-em-risco/',
                        dados_contexto={
                            'cliente_ids': [c.id for c, _, _ in clientes],
                        },
                    )
        except Exception as exc:
            logger.error('Erro ao notificar gerentes de CS: %s', exc)
