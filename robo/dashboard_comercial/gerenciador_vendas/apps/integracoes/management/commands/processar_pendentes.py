"""Processa leads com status_api='pendente' enviando pro HubSoft (cadastrar_prospecto).

Itera tenant a tenant, respeitando 3 pre-requisitos por tenant:
  1. Tenant tem IntegracaoAPI tipo='hubsoft' ativa propria
  2. ConfiguracaoEmpresa.enviar_leads_integracao = True
  3. ConfiguracaoEmpresa.integracao_leads_id aponta pra essa integracao

Tenant que nao cumpre os 3 e SILENCIOSAMENTE PULADO — nao deveria entrar no
loop nem acumular erro. Isso conserta o bug historico onde o comando usava
IntegracaoAPI.objects.first() sem filtro de tenant e marcava status_api=erro
em leads de tenants que nem tinham integracao cadastrada.
"""
import logging

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
from apps.comercial.leads.models import LeadProspecto
from apps.sistema.models import Tenant

logger = logging.getLogger(__name__)


def _get_config_empresa(tenant):
    """Retorna ConfiguracaoEmpresa ativa do tenant, ou None."""
    try:
        from apps.sistema.models import ConfiguracaoEmpresa
        return ConfiguracaoEmpresa.all_tenants.filter(tenant=tenant, ativo=True).first()
    except Exception:
        return None


class Command(BaseCommand):
    help = (
        'Processa leads com status_api="pendente" enviando pro HubSoft. '
        'Itera por tenant respeitando configuracao de envio.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--lead-id', type=int, help='Processar apenas este lead.')
        parser.add_argument('--tenant', type=str, help='Slug do tenant (opcional). Sem isso, processa todos.')
        parser.add_argument('--dry-run', action='store_true',
            help='Apenas lista os leads que seriam processados, sem enviar.')

    def handle(self, *args, **options):
        tenant_filter = options.get('tenant')
        lead_id_filter = options.get('lead_id')
        dry_run = options.get('dry_run', False)

        tenants_qs = Tenant.objects.filter(ativo=True)
        if tenant_filter:
            tenants_qs = tenants_qs.filter(slug=tenant_filter)

        total_ok = 0
        total_erro = 0
        total_pulado_sem_integracao = 0
        total_pulado_config_off = 0

        for tenant in tenants_qs:
            # 1) Tenant tem IntegracaoAPI hubsoft ativa propria?
            integracao = IntegracaoAPI.all_tenants.filter(
                tenant=tenant, tipo='hubsoft', ativa=True,
            ).first()
            if not integracao:
                total_pulado_sem_integracao += 1
                logger.debug('[%s] sem IntegracaoAPI hubsoft ativa — pulado', tenant.slug)
                continue

            # 2+3) Config de envio ativada E apontando pra essa integracao
            config = _get_config_empresa(tenant)
            if not config or not config.enviar_leads_integracao or config.integracao_leads_id != integracao.id:
                total_pulado_config_off += 1
                logger.debug('[%s] ConfiguracaoEmpresa.enviar_leads_integracao=False ou integracao_leads_id mismatch — pulado', tenant.slug)
                continue

            # 3b) Sub-flag granular modos_sync.enviar_lead (alem da global).
            # Permite desligar lead sem mexer na ConfiguracaoEmpresa.
            from apps.comercial.leads.utils import (
                integracao_envia_lead,
                validar_lead_pronto_para_prospect,
            )
            if not integracao_envia_lead(integracao):
                total_pulado_config_off += 1
                logger.info(
                    '[%s] extras.modos_sync.enviar_lead=desativado — pulado',
                    tenant.slug,
                )
                continue

            # 4) Leads pendentes DESSE tenant
            qs = LeadProspecto.all_tenants.filter(
                tenant=tenant, status_api='pendente',
            ).filter(Q(id_hubsoft__isnull=True) | Q(id_hubsoft=''))
            if lead_id_filter:
                qs = qs.filter(pk=lead_id_filter)
            leads = list(qs.order_by('id'))

            if not leads:
                self.stdout.write(f'[{tenant.slug}] nenhum lead pendente.')
                continue

            self.stdout.write(self.style.SUCCESS(
                f'[{tenant.slug}] integracao={integracao.nome!r}  pendentes={len(leads)}'
            ))

            if dry_run:
                for lead in leads:
                    self.stdout.write(f'  [DRY-RUN] lead#{lead.pk} {lead.nome_razaosocial!r} cpf={lead.cpf_cnpj}')
                continue

            service = HubsoftService(integracao)
            total_pulado_preflight = 0
            for lead in leads:
                self.stdout.write(f'  Processando lead#{lead.pk} {lead.nome_razaosocial!r}... ', ending='')

                # PRE-FLIGHT CHECK: bloqueia leads invalidos ANTES de gastar
                # request HubSoft (que retornaria erro generico mascarado).
                status_pre, motivo = validar_lead_pronto_para_prospect(lead, integracao)
                if status_pre != 'pendente':
                    LeadProspecto.all_tenants.filter(pk=lead.pk).update(
                        status_api=status_pre,
                        motivo_rejeicao=motivo[:500],
                    )
                    self.stdout.write(self.style.WARNING(f'PULADO ({status_pre}): {motivo[:150]}'))
                    total_pulado_preflight += 1
                    continue

                try:
                    resposta = service.cadastrar_prospecto(lead)
                    id_prospecto = resposta.get('prospecto', {}).get('id_prospecto')
                    campos_update = {'status_api': 'processado', 'motivo_rejeicao': None}
                    if id_prospecto:
                        campos_update['id_hubsoft'] = str(id_prospecto)
                    LeadProspecto.all_tenants.filter(pk=lead.pk).update(**campos_update)
                    self.stdout.write(self.style.SUCCESS(f'OK (id_prospecto={id_prospecto})'))
                    total_ok += 1
                except HubsoftServiceError as exc:
                    # Categoriza pela mensagem do HubSoft
                    msg = str(exc).lower()
                    if 'cpf' in msg and ('invalido' in msg or 'inválido' in msg):
                        novo_status = 'cpf_invalido'
                    elif 'vendedor' in msg and ('invalido' in msg or 'inválido' in msg):
                        novo_status = 'vendedor_invalido'
                    elif 'plano' in msg or 'unidade' in msg or 'cidade' in msg or 'origem' in msg:
                        novo_status = 'regra_negocio'
                    else:
                        novo_status = 'erro'
                    LeadProspecto.all_tenants.filter(pk=lead.pk).update(
                        status_api=novo_status,
                        motivo_rejeicao=str(exc)[:500],
                    )
                    self.stdout.write(self.style.ERROR(f'ERRO ({novo_status}): {str(exc)[:200]}'))
                    total_erro += 1
                except Exception as exc:
                    LeadProspecto.all_tenants.filter(pk=lead.pk).update(
                        status_api='erro',
                        motivo_rejeicao=f'inesperado: {type(exc).__name__}: {str(exc)[:400]}',
                    )
                    self.stdout.write(self.style.ERROR(f'ERRO INESPERADO: {str(exc)[:200]}'))
                    logger.exception('Erro ao processar lead pk=%s', lead.pk)
                    total_erro += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Concluido: ok={total_ok}  erros={total_erro}  '
            f'pulados_sem_integracao={total_pulado_sem_integracao}  '
            f'pulados_config_off={total_pulado_config_off}'
        ))
