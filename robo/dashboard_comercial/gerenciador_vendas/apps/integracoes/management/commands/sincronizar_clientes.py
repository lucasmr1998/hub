"""Sincroniza ClienteHubsoft pra leads com status_api='processado'.

Multi-tenant: itera POR TENANT (corrigindo bug onde antes pegava
IntegracaoAPI.objects.filter(...).first() sem filtro de tenant, o que
funcionava so porque Nuvyon era unica em prod com HubSoft).

So processa tenants com IntegracaoAPI hubsoft ativa E
extras.modos_sync.sincronizar_cliente='ativado' (alem do --lead-id manual
que bypassa a flag).
"""
import logging

from django.core.management.base import BaseCommand

from apps.integracoes.models import IntegracaoAPI, ClienteHubsoft
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
from apps.comercial.leads.models import LeadProspecto
from apps.sistema.models import Tenant

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Consulta a API Hubsoft e sincroniza os dados de clientes '
        'vinculados a leads com status_api="processado". Itera por tenant.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--lead-id', type=int,
                            help='Sincronizar apenas o lead com este ID.')
        parser.add_argument('--tenant', type=str,
                            help='Slug do tenant (opcional). Sem isso, todos.')
        parser.add_argument('--todos', action='store_true',
                            help='Re-sincronizar todos os processados, mesmo os já sincronizados.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Apenas listar os leads que seriam sincronizados.')

    def handle(self, *args, **options):
        tenant_filter = options.get('tenant')
        lead_id_filter = options.get('lead_id')
        todos = options.get('todos', False)
        dry_run = options.get('dry_run', False)

        # Modo --lead-id: localiza o tenant pelo lead (bypass tenant_filter +
        # sync flag check, e o ciclo abaixo nao itera tudo).
        if lead_id_filter:
            try:
                lead_obj = LeadProspecto.all_tenants.get(pk=lead_id_filter)
            except LeadProspecto.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'Lead {lead_id_filter} nao encontrado.'))
                return
            tenants_qs = Tenant.objects.filter(pk=lead_obj.tenant_id, ativo=True)
        else:
            tenants_qs = Tenant.objects.filter(ativo=True)
            if tenant_filter:
                tenants_qs = tenants_qs.filter(slug=tenant_filter)

        total_ok = 0
        total_nao_encontrados = 0
        total_erros = 0
        total_pulado_sem_integracao = 0
        total_pulado_sync_off = 0

        for tenant in tenants_qs:
            integracao = IntegracaoAPI.all_tenants.filter(
                tenant=tenant, tipo='hubsoft', ativa=True,
            ).first()
            if not integracao:
                total_pulado_sem_integracao += 1
                continue

            # Cron so roda se sincronizar_cliente='ativado'. --lead-id bypassa.
            if not lead_id_filter and not integracao.sync_habilitado('sincronizar_cliente'):
                total_pulado_sync_off += 1
                logger.debug(
                    '[%s] modos_sync.sincronizar_cliente=%s — pulado',
                    tenant.slug, integracao.get_modo_sync('sincronizar_cliente'),
                )
                continue

            qs = LeadProspecto.all_tenants.filter(
                tenant=tenant, status_api='processado',
            ).exclude(id_hubsoft__isnull=True).exclude(id_hubsoft='')

            if lead_id_filter:
                qs = qs.filter(pk=lead_id_filter)
            elif not todos:
                # Pula os ja sincronizados (filtrando por tenant pra isolamento)
                ids_ja_sincronizados = ClienteHubsoft.all_tenants.filter(
                    tenant=tenant, lead__isnull=False,
                ).values_list('lead_id', flat=True)
                qs = qs.exclude(pk__in=ids_ja_sincronizados)

            leads = list(qs.order_by('id'))
            if not leads:
                self.stdout.write(f'[{tenant.slug}] nenhum lead para sincronizar.')
                continue

            self.stdout.write(self.style.SUCCESS(
                f'[{tenant.slug}] {len(leads)} lead(s) para sincronizar.'
            ))

            if dry_run:
                for lead in leads:
                    self.stdout.write(
                        f'  [DRY-RUN] ID={lead.id} | {lead.nome_razaosocial} | '
                        f'cpf_cnpj={lead.cpf_cnpj} | id_hubsoft={lead.id_hubsoft}'
                    )
                continue

            service = HubsoftService(integracao)
            for lead in leads:
                self.stdout.write(f'  Sincronizando ID={lead.id} | {lead.nome_razaosocial}... ', ending='')
                try:
                    cliente = service.sincronizar_cliente(lead)
                    if cliente:
                        alteracao_info = ' [ALTERACOES DETECTADAS]' if cliente.houve_alteracao else ''
                        self.stdout.write(self.style.SUCCESS(
                            f'OK (id_cliente={cliente.id_cliente}, '
                            f'servicos={cliente.servicos.count()}){alteracao_info}'
                        ))
                        total_ok += 1
                    else:
                        self.stdout.write(self.style.WARNING('NAO ENCONTRADO no Hubsoft'))
                        total_nao_encontrados += 1
                except HubsoftServiceError as exc:
                    self.stdout.write(self.style.ERROR(f'ERRO: {str(exc)[:200]}'))
                    total_erros += 1
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f'ERRO INESPERADO: {str(exc)[:200]}'))
                    logger.exception('Erro ao sincronizar lead pk=%s', lead.pk)
                    total_erros += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Concluido: ok={total_ok}  nao_encontrados={total_nao_encontrados}  '
            f'erros={total_erros}  pulado_sem_integracao={total_pulado_sem_integracao}  '
            f'pulado_sync_off={total_pulado_sync_off}'
        ))
