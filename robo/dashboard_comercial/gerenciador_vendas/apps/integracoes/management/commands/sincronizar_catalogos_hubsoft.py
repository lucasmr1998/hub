"""Sincroniza catalogos do HubSoft (vendedores, origens, planos, vencimentos)
e detecta mudancas vs cache anterior. Roda diariamente via CronJob.

Casos que motivaram: id_vendedor 'hubtrix' mudou de 1618 -> 743 entre
01-02/06/2026 silenciosamente. Sem sync periodico, o catalogo cacheado
em IntegracaoAPI.extras.cache fica stale e o pre-flight do
processar_pendentes deixa passar IDs invalidos.

Uso:
    python manage.py sincronizar_catalogos_hubsoft [--tenant=slug] [--dry-run]

Sem --tenant: itera todos os tenants com IntegracaoAPI hubsoft ativa.
"""
import logging

from django.core.management.base import BaseCommand

from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
from apps.sistema.models import Tenant

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Sincroniza catalogos HubSoft (vendedores, origens, planos, vencimentos) '
        'em IntegracaoAPI.configuracoes_extras.cache. Detecta diff vs rodada '
        'anterior e loga warnings se vendedores foram removidos.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, default=None,
                            help='Slug do tenant. Sem isso, processa todos.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Lista o que sincronizaria, sem persistir.')

    def handle(self, *args, **options):
        tenant_slug = options.get('tenant')
        dry_run = options.get('dry_run', False)

        qs = Tenant.objects.filter(ativo=True)
        if tenant_slug:
            qs = qs.filter(slug=tenant_slug)

        total_tenants_ok = 0
        total_tenants_erro = 0
        total_tenants_skip = 0
        total_diffs = 0

        for tenant in qs:
            integracao = IntegracaoAPI.all_tenants.filter(
                tenant=tenant, tipo='hubsoft', ativa=True,
            ).first()
            if not integracao:
                total_tenants_skip += 1
                continue

            self.stdout.write(self.style.SUCCESS(
                f'\n[{tenant.slug}] sincronizando catalogos...'
            ))

            service = HubsoftService(integracao)

            # Snapshot ANTES (pra detectar diff de IDs removidos)
            extras_antes = dict(integracao.configuracoes_extras or {})
            cache_antes = dict(extras_antes.get('cache') or {})
            ids_vendedores_antes = {
                v.get('id') for v in (cache_antes.get('vendedores') or [])
                if v.get('id') is not None
            }

            try:
                resumo = service.sincronizar_configuracoes(dry_run=dry_run)
                total_tenants_ok += 1
                self.stdout.write(f'  total_geral={resumo.get("_total_geral")} dry_run={dry_run}')
                for chave, r in resumo.items():
                    if chave.startswith('_'):
                        continue
                    if isinstance(r, dict) and 'erro' in r:
                        self.stdout.write(self.style.WARNING(
                            f'    {chave:25s} ERRO: {r["erro"][:120]}'
                        ))
                    elif isinstance(r, dict):
                        self.stdout.write(
                            f'    {chave:25s} total={r.get("total",0):4d} '
                            f'criados={r.get("criados",0):3d} '
                            f'atualizados={r.get("atualizados",0):3d}'
                        )
            except HubsoftServiceError as exc:
                total_tenants_erro += 1
                self.stdout.write(self.style.ERROR(
                    f'  HubsoftServiceError: {str(exc)[:200]}'
                ))
                continue
            except Exception as exc:
                total_tenants_erro += 1
                self.stdout.write(self.style.ERROR(
                    f'  ERRO INESPERADO: {type(exc).__name__}: {str(exc)[:200]}'
                ))
                logger.exception('Erro sincronizando tenant %s', tenant.slug)
                continue

            # Snapshot DEPOIS pra detectar IDs removidos
            if not dry_run:
                integracao.refresh_from_db()
                cache_depois = (integracao.configuracoes_extras or {}).get('cache') or {}
                ids_vendedores_depois = {
                    v.get('id') for v in (cache_depois.get('vendedores') or [])
                    if v.get('id') is not None
                }
                removidos = ids_vendedores_antes - ids_vendedores_depois
                if removidos:
                    total_diffs += len(removidos)
                    self.stdout.write(self.style.WARNING(
                        f'  ⚠️  {len(removidos)} vendedor(es) SUMIRAM do catalogo: {sorted(removidos)}'
                    ))
                    # Conta leads pendentes do tenant que usam vendedor removido —
                    # nao bloqueia, so loga pra acompanhamento.
                    from apps.comercial.leads.models import LeadProspecto
                    afetados = LeadProspecto.all_tenants.filter(
                        tenant=tenant,
                        status_api='pendente',
                        id_vendedor_rp__in=list(removidos),
                    ).count()
                    if afetados:
                        self.stdout.write(self.style.WARNING(
                            f'      {afetados} lead(s) pendente(s) deste tenant usam IDs removidos '
                            f'(pre-flight vai bloquear como vendedor_invalido)'
                        ))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Concluido: ok={total_tenants_ok} erros={total_tenants_erro} '
            f'sem_integracao={total_tenants_skip} ids_removidos={total_diffs}'
        ))
