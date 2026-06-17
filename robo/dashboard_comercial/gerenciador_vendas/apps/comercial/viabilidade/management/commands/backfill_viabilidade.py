"""
Backfill de viabilidade tecnica pros leads historicos.

Itera leads do tenant que tem CEP preenchido mas NAO tem
`dados_custom.viabilidade.status` populado, chama o service de viabilidade
(HubSoft API ou CidadeViabilidade local, conforme tenant) e grava resultado.

Habilita o relatorio #9 do briefing Nuvyon (Cobertura e Viabilidade) pra
historico, nao so leads novos a partir do deploy de 17/06.

Uso:
    python manage.py backfill_viabilidade --tenant nuvyon
    python manage.py backfill_viabilidade --tenant nuvyon --dry-run
    python manage.py backfill_viabilidade --tenant nuvyon --max 100 --rate-limit 1.0
"""
import logging
import time

from django.core.management.base import BaseCommand

from apps.comercial.leads.models import LeadProspecto
from apps.comercial.viabilidade.services import consultar_viabilidade
from apps.sistema.models import Tenant

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Roda consultar_viabilidade pros leads historicos sem viabilidade gravada.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, required=True,
            help='Slug do tenant (obrigatorio).')
        parser.add_argument('--max', type=int, default=None,
            help='Limite de leads processados (default: todos).')
        parser.add_argument('--rate-limit', type=float, default=0.5,
            help='Pausa em segundos entre chamadas (default 0.5s).')
        parser.add_argument('--dry-run', action='store_true',
            help='So lista quantos leads seriam processados, sem chamar a API.')

    def handle(self, *args, **opts):
        tenant_slug = opts['tenant']
        try:
            tenant = Tenant.objects.get(slug=tenant_slug, ativo=True)
        except Tenant.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'Tenant {tenant_slug!r} nao encontrado'))
            return

        # Leads com CEP e sem viabilidade gravada (dados_custom__viabilidade__status ausente)
        qs = LeadProspecto.all_tenants.filter(tenant=tenant).exclude(cep='').exclude(cep__isnull=True)
        # Filtra Python-side pra evitar JSONField complexo no SQL
        total_qs = qs.count()
        self.stdout.write(f'[{tenant.slug}] leads com CEP: {total_qs}')

        leads_pendentes = []
        for lead in qs.iterator():
            via = (lead.dados_custom or {}).get('viabilidade') or {}
            if not via.get('status'):
                leads_pendentes.append(lead)
            if opts.get('max') and len(leads_pendentes) >= opts['max']:
                break

        self.stdout.write(self.style.SUCCESS(
            f'[{tenant.slug}] sem viabilidade gravada: {len(leads_pendentes)}'
        ))

        if opts.get('dry_run'):
            self.stdout.write(self.style.WARNING('DRY-RUN — nenhuma chamada a HubSoft feita.'))
            return

        if not leads_pendentes:
            return

        rate = opts.get('rate_limit', 0.5)
        total_ok = total_fora = total_erro = 0
        t0 = time.monotonic()

        for i, lead in enumerate(leads_pendentes, 1):
            try:
                resultado = consultar_viabilidade(
                    tenant,
                    cep=lead.cep or '',
                    logradouro=lead.rua or '',
                    numero=lead.numero_residencia or '',
                    bairro=lead.bairro or '',
                    cidade=lead.cidade or '',
                    uf=lead.estado or '',
                )
                if resultado.status != 'nao_consultado':
                    dc = lead.dados_custom or {}
                    dc['viabilidade'] = resultado.to_dict()
                    lead.dados_custom = dc
                    lead.save(update_fields=['dados_custom'])
                    if resultado.status == 'cobertura_ok':
                        total_ok += 1
                    elif resultado.status == 'fora_cobertura':
                        total_fora += 1
                    else:
                        total_erro += 1
            except Exception as exc:
                total_erro += 1
                logger.exception('backfill viab lead=%s falhou: %s', lead.pk, exc)

            if i % 50 == 0:
                self.stdout.write(
                    f'  {i}/{len(leads_pendentes)} ok={total_ok} fora={total_fora} erro={total_erro}'
                )
            if rate > 0:
                time.sleep(rate)

        dur = time.monotonic() - t0
        self.stdout.write(self.style.SUCCESS(
            f'=== [{tenant.slug}] DONE em {dur:.1f}s: ok={total_ok} '
            f'fora={total_fora} erro={total_erro} (total={len(leads_pendentes)}) ==='
        ))
