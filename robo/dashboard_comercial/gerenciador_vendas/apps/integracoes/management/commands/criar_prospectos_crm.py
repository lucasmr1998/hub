"""
Processa leads "humanos" travados no CRM, criando prospecto no HubSoft.

Cenario coberto:
- Lead comecou no flow do bot (Matrix), foi transferido pra humano.
- Em algum momento o cron `processar_pendentes` pulou ou marcou status_api='processamento_manual'.
- Operador trabalhou a oportunidade no CRM, subiu/aprovou documentos, marcou score como aprovado.
- Sem este cron, esse lead nunca mais vai pro HubSoft (nem o cron padrao nem o bot Selenium pegam).

Filtro deste cron (estagio FIXO):
  - tenant ativo com IntegracaoAPI hubsoft ativa
  - oportunidade.estagio.slug = `analises-doc-score` (configuravel via --estagio-slug)
  - lead.documentacao_validada = True
  - lead.score_status = 'aprovado'
  - lead.id_hubsoft IS NULL (idempotente — nao recria se ja existe prospecto)
  - lead.status_api != 'pendente' (evita colisao com processar_pendentes)

Para cada lead encontrado:
  - Chama helper `criar_prospecto_para_lead` (mesma logica do processar_pendentes).
  - Bot Selenium (container hubtrix-bot-nuvyon) pega no proximo poll e converte.

Read-only para tenants sem integracao hubsoft. Idempotente.
"""
import logging

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.integracoes.models import IntegracaoAPI
from apps.comercial.leads.models import LeadProspecto
from apps.comercial.crm.models import OportunidadeVenda, PipelineEstagio
from apps.sistema.models import Tenant

from apps.integracoes.services.hubsoft_prospecto import criar_prospecto_para_lead

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Processa leads "humanos" no CRM que ja tem docs aprovados, score aprovado e '
        'estao no estagio "Analises - Doc & Score" sem prospecto HubSoft ainda.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str,
            help='Slug do tenant (opcional). Sem isso, processa todos com integracao hubsoft ativa.')
        parser.add_argument('--estagio-slug', type=str, default='analises-doc-score',
            help='Slug do estagio trigger. Default: analises-doc-score.')
        parser.add_argument('--limit', type=int, default=50,
            help='Maximo de leads processados por execucao. Default: 50.')
        parser.add_argument('--dry-run', action='store_true',
            help='Apenas lista os leads que seriam processados, sem chamar HubSoft.')

    def handle(self, *args, **options):
        tenant_filter = options.get('tenant')
        estagio_slug = options.get('estagio_slug') or 'analises-doc-score'
        limit = options.get('limit') or 50
        dry_run = options.get('dry_run', False)

        tenants_qs = Tenant.objects.filter(ativo=True)
        if tenant_filter:
            tenants_qs = tenants_qs.filter(slug=tenant_filter)

        total_ok = 0
        total_erro = 0
        total_pulado = 0
        total_tenants_sem_integracao = 0

        for tenant in tenants_qs:
            integracao = IntegracaoAPI.all_tenants.filter(
                tenant=tenant, tipo='hubsoft', ativa=True,
            ).first()
            if not integracao:
                total_tenants_sem_integracao += 1
                continue

            # Encontra os estagios "Analises - Doc & Score" desse tenant (slug pode existir
            # em mais de um pipeline; pega todos).
            estagios_ids = list(
                PipelineEstagio.all_tenants.filter(
                    pipeline__tenant=tenant, slug=estagio_slug,
                ).values_list('id', flat=True)
            )
            if not estagios_ids:
                logger.debug('[%s] sem estagio slug=%r — pulado', tenant.slug, estagio_slug)
                continue

            # Leads candidatos: oportunidade no estagio + flags do lead.
            oportunidades = OportunidadeVenda.all_tenants.filter(
                tenant=tenant,
                ativo=True,
                estagio_id__in=estagios_ids,
                lead__documentacao_validada=True,
                lead__score_status='aprovado',
            ).filter(
                Q(lead__id_hubsoft__isnull=True) | Q(lead__id_hubsoft=''),
            ).exclude(
                lead__status_api='pendente',
            ).select_related('lead')[:limit]

            self.stdout.write(self.style.SUCCESS(
                f'[{tenant.slug}] candidatos={oportunidades.count()} estagio={estagio_slug}'
            ))

            if dry_run:
                for op in oportunidades:
                    self.stdout.write(
                        f'  [DRY-RUN] op#{op.pk} lead#{op.lead_id} '
                        f'{op.lead.nome_razaosocial!r} status_api={op.lead.status_api!r}'
                    )
                continue

            for op in oportunidades:
                lead = op.lead
                self.stdout.write(
                    f'  op#{op.pk} lead#{lead.pk} {lead.nome_razaosocial!r}... ',
                    ending='',
                )

                resultado = criar_prospecto_para_lead(lead, integracao=integracao)
                if resultado.ok:
                    total_ok += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'OK (id_prospecto={resultado.id_prospecto})'
                    ))
                    try:
                        from apps.sistema.utils import registrar_acao
                        registrar_acao(
                            'integracao', 'criar_prospecto_crm', 'lead', lead.pk,
                            f'Cron CRM criou prospecto HubSoft id={resultado.id_prospecto} (op#{op.pk})',
                            tenant=tenant,
                        )
                    except Exception:
                        pass
                elif resultado.pulado_preflight:
                    total_pulado += 1
                    self.stdout.write(self.style.WARNING(
                        f'PULADO ({resultado.novo_status}): {(resultado.motivo or "")[:120]}'
                    ))
                else:
                    total_erro += 1
                    self.stdout.write(self.style.ERROR(
                        f'ERRO ({resultado.novo_status}): {(resultado.motivo or "")[:200]}'
                    ))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'=== resumo: ok={total_ok} erro={total_erro} pulado={total_pulado} '
            f'tenants_sem_integracao={total_tenants_sem_integracao} ==='
        ))
