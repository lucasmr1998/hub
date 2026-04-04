"""
Management command para execução periódica de automações.

Roda a cada 5 minutos via crontab:
    */5 * * * * python manage.py executar_automacoes_cron --settings=gerenciador_vendas.settings

Responsabilidades:
1. Executar ações com delay que já passaram do horário
2. Detectar leads sem contato há X dias
3. Detectar tarefas CRM vencidas
4. Disparo em massa por segmento
"""
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.sistema.models import Tenant
from apps.sistema.middleware import set_current_tenant
from apps.marketing.automacoes.engine import disparar_evento, executar_pendentes
from apps.marketing.automacoes.models import RegraAutomacao, LogExecucao

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Executa automações agendadas, eventos temporais e disparos por segmento'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Simula sem executar')
        parser.add_argument('--tenant', type=str, help='Slug de um tenant específico')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        tenant_slug = options.get('tenant')

        if tenant_slug:
            tenants = Tenant.objects.filter(slug=tenant_slug, ativo=True)
        else:
            tenants = Tenant.objects.filter(ativo=True)

        total_pendentes = 0
        total_eventos = 0

        for tenant in tenants:
            set_current_tenant(tenant)
            self.stdout.write(f'\n[{tenant.nome}]')

            # 1. Executar pendentes (delays)
            if not dry_run:
                count = executar_pendentes(tenant)
                total_pendentes += count
                if count:
                    self.stdout.write(f'  Pendentes executados: {count}')

            # 2. Lead sem contato
            count = self._evento_lead_sem_contato(tenant, dry_run)
            total_eventos += count

            # 3. Tarefa vencida
            count = self._evento_tarefa_vencida(tenant, dry_run)
            total_eventos += count

            # 4. Disparo por segmento
            count = self._disparar_segmentos(tenant, dry_run)
            total_eventos += count

        set_current_tenant(None)
        self.stdout.write(self.style.SUCCESS(
            f'\nConcluído: {total_pendentes} pendentes executados, {total_eventos} eventos disparados'
        ))

    def _evento_lead_sem_contato(self, tenant, dry_run):
        """Detecta leads sem contato e dispara evento."""
        from apps.comercial.leads.models import LeadProspecto
        from datetime import timedelta

        regras = RegraAutomacao.all_tenants.filter(
            tenant=tenant, evento='lead_sem_contato', ativa=True,
        )
        if not regras.exists():
            return 0

        count = 0
        for regra in regras:
            # Extrair dias da config (condição ou nodo)
            dias = self._extrair_dias_config(regra)
            if dias <= 0:
                dias = 3  # Default: 3 dias

            limite = timezone.now() - timedelta(days=dias)

            # Leads com último histórico antes do limite
            from apps.comercial.leads.models import HistoricoContato
            from django.db.models import Max

            leads_com_contato = HistoricoContato.all_tenants.filter(
                tenant=tenant,
            ).values('lead_id').annotate(
                ultimo=Max('data_hora_contato')
            ).filter(ultimo__lt=limite).values_list('lead_id', flat=True)

            # Evitar disparar para o mesmo lead mais de 1x por período
            ja_disparados = LogExecucao.all_tenants.filter(
                tenant=tenant, regra=regra,
                data_execucao__gte=limite,
            ).values_list('lead_id', flat=True)

            leads = LeadProspecto.all_tenants.filter(
                tenant=tenant, pk__in=leads_com_contato,
            ).exclude(pk__in=ja_disparados)

            for lead in leads[:50]:  # Limite por execução
                if dry_run:
                    self.stdout.write(f'  [DRY-RUN] lead_sem_contato: {lead.nome_razaosocial} ({dias}d)')
                else:
                    disparar_evento('lead_sem_contato', {
                        'lead': lead,
                        'lead_nome': lead.nome_razaosocial,
                        'telefone': lead.telefone,
                        'nome': lead.nome_razaosocial,
                        'dias_sem_contato': dias,
                    }, tenant=tenant)
                count += 1

            if count:
                self.stdout.write(f'  lead_sem_contato: {count} leads')

        return count

    def _evento_tarefa_vencida(self, tenant, dry_run):
        """Detecta tarefas vencidas e dispara evento."""
        from apps.comercial.crm.models import TarefaCRM

        regras = RegraAutomacao.all_tenants.filter(
            tenant=tenant, evento='tarefa_vencida', ativa=True,
        )
        if not regras.exists():
            return 0

        tarefas = TarefaCRM.all_tenants.filter(
            tenant=tenant,
            status__in=['pendente', 'em_andamento'],
            data_vencimento__lt=timezone.now(),
        ).select_related('lead', 'responsavel')[:50]

        count = 0
        for tarefa in tarefas:
            if dry_run:
                self.stdout.write(f'  [DRY-RUN] tarefa_vencida: {tarefa.titulo}')
            else:
                disparar_evento('tarefa_vencida', {
                    'tarefa': tarefa,
                    'tarefa_titulo': tarefa.titulo,
                    'lead': tarefa.lead,
                    'responsavel': tarefa.responsavel,
                    'nome': tarefa.titulo,
                }, tenant=tenant)
            count += 1

        if count:
            self.stdout.write(f'  tarefa_vencida: {count} tarefas')

        return count

    def _disparar_segmentos(self, tenant, dry_run):
        """Disparo em massa para regras com segmento associado."""
        from apps.comercial.crm.services.segmentos import filtrar_leads_por_regras

        regras = RegraAutomacao.all_tenants.filter(
            tenant=tenant, evento='disparo_segmento', ativa=True,
            segmento__isnull=False,
        ).select_related('segmento')

        count = 0
        for regra in regras:
            seg = regra.segmento
            regras_filtro = seg.regras_filtro.get('regras', [])

            if regras_filtro:
                leads = filtrar_leads_por_regras(regras_filtro)
            else:
                leads = seg.leads.all()

            for lead in leads[:100]:  # Limite por execução
                if dry_run:
                    self.stdout.write(f'  [DRY-RUN] disparo_segmento ({seg.nome}): {lead.nome_razaosocial}')
                else:
                    disparar_evento('disparo_segmento', {
                        'lead': lead,
                        'lead_nome': lead.nome_razaosocial,
                        'telefone': lead.telefone,
                        'nome': lead.nome_razaosocial,
                        'segmento': seg,
                        'segmento_nome': seg.nome,
                    }, tenant=tenant)
                count += 1

            if count:
                self.stdout.write(f'  disparo_segmento ({seg.nome}): {count} leads')

        return count

    def _extrair_dias_config(self, regra):
        """Extrai número de dias da configuração da regra."""
        # Tentar das condições legacy
        for cond in regra.condicoes.all():
            if 'dias' in cond.campo.lower():
                try:
                    return int(cond.valor)
                except ValueError:
                    pass

        # Tentar dos nodos (modo fluxo)
        for nodo in regra.nodos.filter(tipo='trigger'):
            dias = nodo.configuracao.get('dias', 0)
            if dias:
                try:
                    return int(dias)
                except (ValueError, TypeError):
                    pass

        return 0
