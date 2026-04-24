"""
Sincroniza catálogos do SGP (planos, vencimentos) para o Hubtrix.

Destinos:
    planos       -> apps.comercial.crm.models.ProdutoServico (categoria='plano')
    vencimentos  -> apps.comercial.crm.models.OpcaoVencimentoCRM

Rodar manualmente ou via cron diário (ver ops/02-CRON.md).
"""
from django.core.management.base import BaseCommand, CommandError

from apps.integracoes.models import IntegracaoAPI


class Command(BaseCommand):
    help = (
        'Sincroniza catálogos do SGP (planos, vencimentos) para o Hubtrix. '
        'Roda para todas as IntegracaoAPI(tipo=sgp, ativa=True) ou filtra por --integracao-id / --tenant.'
    )

    CATEGORIAS_VALIDAS = ('planos', 'vencimentos', 'vendedores', 'pops', 'portadores', 'todos')

    def add_arguments(self, parser):
        parser.add_argument(
            '--categoria',
            choices=self.CATEGORIAS_VALIDAS,
            default='todos',
            help='O que sincronizar (default: todos). Nesta fase vencimentos ainda não está implementado.',
        )
        parser.add_argument(
            '--integracao-id',
            type=int,
            help='ID específico de IntegracaoAPI a sincronizar.',
        )
        parser.add_argument(
            '--tenant',
            help='Slug do tenant. Sincroniza apenas integrações SGP desse tenant.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula sem salvar. Mostra contagens estimadas.',
        )

    def handle(self, *args, **options):
        categoria = options['categoria']
        integracao_id = options.get('integracao_id')
        tenant_slug = options.get('tenant')
        dry_run = options['dry_run']

        # Import local pra não carregar o service se só --help for chamado
        from apps.integracoes.services.sgp import SGPService, SGPServiceError

        qs = IntegracaoAPI.objects.filter(tipo='sgp', ativa=True)
        if integracao_id:
            qs = qs.filter(pk=integracao_id)
        if tenant_slug:
            qs = qs.filter(tenant__slug=tenant_slug)

        integracoes = list(qs)
        if not integracoes:
            self.stdout.write(self.style.WARNING(
                'Nenhuma IntegracaoAPI(tipo=sgp, ativa=True) encontrada com os filtros.'
            ))
            return

        self.stdout.write(
            f"Sincronizando catálogo SGP | categoria={categoria} | dry_run={dry_run} | "
            f"{len(integracoes)} integração(ões)"
        )

        for integracao in integracoes:
            tenant_slug_real = getattr(integracao.tenant, 'slug', '?')
            self.stdout.write('')
            self.stdout.write(self.style.MIGRATE_HEADING(
                f">> {integracao.nome} (tenant={tenant_slug_real}, base_url={integracao.base_url})"
            ))

            service = SGPService(integracao)

            # Planos
            if categoria in ('planos', 'todos'):
                if not integracao.sync_permitido('sincronizar_planos'):
                    self.stdout.write(
                        "  [planos] desativado em modos_sync, pulando."
                    )
                else:
                    self._sincronizar_planos(service, dry_run)

            # Vencimentos
            if categoria in ('vencimentos', 'todos'):
                if not integracao.sync_permitido('sincronizar_vencimentos'):
                    self.stdout.write(
                        "  [vencimentos] desativado em modos_sync, pulando."
                    )
                else:
                    self._sincronizar_vencimentos(service, dry_run)

            # Catálogos de referência (cache em configuracoes_extras)
            for chave, feature, metodo_nome in (
                ('vendedores', 'sincronizar_vendedores', 'sincronizar_vendedores'),
                ('pops', 'sincronizar_pops', 'sincronizar_pops'),
                ('portadores', 'sincronizar_portadores', 'sincronizar_portadores'),
            ):
                if categoria not in (chave, 'todos'):
                    continue
                if not integracao.sync_permitido(feature):
                    self.stdout.write(
                        f"  [{chave}] desativado em modos_sync, pulando."
                    )
                    continue
                self._sincronizar_cache(service, chave, metodo_nome, dry_run)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Concluído.'))

    def _sincronizar_planos(self, service, dry_run):
        from apps.integracoes.services.sgp import SGPServiceError

        try:
            resumo = service.sincronizar_planos(dry_run=dry_run)
        except SGPServiceError as exc:
            self.stdout.write(self.style.ERROR(
                f"  [planos] ERRO: {exc}"
            ))
            return
        except Exception as exc:
            raise CommandError(f"Erro inesperado em sincronizar_planos: {exc}") from exc

        prefix = '[DRY-RUN]' if dry_run else '[OK]'
        self.stdout.write(
            f"  [planos] {prefix} total={resumo['total']} "
            f"criados={resumo['criados']} "
            f"atualizados={resumo['atualizados']} "
            f"inalterados={resumo['inalterados']}"
        )

    def _sincronizar_vencimentos(self, service, dry_run):
        from apps.integracoes.services.sgp import SGPServiceError

        try:
            resumo = service.sincronizar_vencimentos(dry_run=dry_run)
        except SGPServiceError as exc:
            self.stdout.write(self.style.ERROR(
                f"  [vencimentos] ERRO: {exc}"
            ))
            return
        except Exception as exc:
            raise CommandError(f"Erro inesperado em sincronizar_vencimentos: {exc}") from exc

        prefix = '[DRY-RUN]' if dry_run else '[OK]'
        self.stdout.write(
            f"  [vencimentos] {prefix} total={resumo['total']} "
            f"criados={resumo['criados']} "
            f"atualizados={resumo['atualizados']} "
            f"inalterados={resumo['inalterados']}"
        )

    def _sincronizar_cache(self, service, chave, metodo_nome, dry_run):
        """Chama um metodo sincronizar_<chave> do service que cacheia em configuracoes_extras."""
        from apps.integracoes.services.sgp import SGPServiceError

        metodo = getattr(service, metodo_nome, None)
        if metodo is None:
            raise CommandError(f"SGPService nao possui metodo {metodo_nome!r}")

        try:
            resumo = metodo(dry_run=dry_run)
        except SGPServiceError as exc:
            self.stdout.write(self.style.ERROR(
                f"  [{chave}] ERRO: {exc}"
            ))
            return
        except Exception as exc:
            raise CommandError(f"Erro inesperado em {metodo_nome}: {exc}") from exc

        prefix = '[DRY-RUN]' if dry_run else '[OK]'
        self.stdout.write(
            f"  [{chave}] {prefix} total={resumo['total']} "
            f"criados={resumo['criados']} "
            f"atualizados={resumo['atualizados']} "
            f"inalterados={resumo['inalterados']}"
        )
