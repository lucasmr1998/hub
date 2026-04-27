"""
Sincroniza catalogos do HubSoft para o Hubtrix.

Destinos:
    servicos     -> apps.comercial.crm.models.ProdutoServico (categoria='plano')
    vencimentos  -> apps.comercial.crm.models.OpcaoVencimentoCRM
    [demais]     -> integracao.configuracoes_extras['cache'][<chave>]
                    (vendedores, origens_cliente, origens_contato,
                     meios_pagamento, grupos_cliente, motivos_contratacao,
                     tipos_servico, servico_status, servicos_tecnologia)

Rodar manualmente ou via cron diario.
"""
from django.core.management.base import BaseCommand

from apps.integracoes.models import IntegracaoAPI


class Command(BaseCommand):
    help = (
        'Sincroniza catalogos do HubSoft (servicos, vencimentos, vendedores, origens, etc) '
        'para o Hubtrix. Roda para todas as IntegracaoAPI(tipo=hubsoft, ativa=True) ou '
        'filtra por --integracao-id / --tenant.'
    )

    CATEGORIAS_VALIDAS = (
        'todos', 'servicos', 'vencimentos',
        'vendedores', 'origens_cliente', 'origens_contato',
        'meios_pagamento', 'grupos_cliente', 'motivos_contratacao',
        'tipos_servico', 'servico_status', 'servicos_tecnologia',
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--categoria',
            choices=self.CATEGORIAS_VALIDAS,
            default='todos',
            help='O que sincronizar (default: todos).',
        )
        parser.add_argument('--integracao-id', type=int, help='ID de IntegracaoAPI.')
        parser.add_argument('--tenant', help='Slug do tenant.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Simula sem salvar; reporta contagens.')
        parser.add_argument(
            '--apenas-automatico', action='store_true',
            help='Roda so as categorias com modo de sync "automatico" '
                 '(use no cron). Categorias em modo manual/desativado sao puladas.',
        )

    # Mapeia categoria -> feature do SYNC_FEATURES.
    # Catalogos cacheados sem feature dedicada herdam 'sincronizar_vendedores' como
    # fallback (modo grupo de catalogos secundarios), ate criarmos features individuais.
    CATEGORIA_FEATURE = {
        'servicos': 'sincronizar_planos',
        'vencimentos': 'sincronizar_vencimentos',
        'vendedores': 'sincronizar_vendedores',
        'origens_cliente': 'sincronizar_vendedores',
        'origens_contato': 'sincronizar_vendedores',
        'meios_pagamento': 'sincronizar_vendedores',
        'grupos_cliente': 'sincronizar_vendedores',
        'motivos_contratacao': 'sincronizar_vendedores',
        'tipos_servico': 'sincronizar_vendedores',
        'servico_status': 'sincronizar_vendedores',
        'servicos_tecnologia': 'sincronizar_vendedores',
    }

    def handle(self, *args, **options):
        from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError

        categoria = options['categoria']
        dry_run = options['dry_run']
        apenas_auto = options['apenas_automatico']

        qs = IntegracaoAPI.objects.filter(tipo='hubsoft', ativa=True)
        if options.get('integracao_id'):
            qs = qs.filter(pk=options['integracao_id'])
        if options.get('tenant'):
            qs = qs.filter(tenant__slug=options['tenant'])

        integracoes = list(qs)
        if not integracoes:
            self.stderr.write(self.style.ERROR('Nenhuma integracao HubSoft ativa encontrada.'))
            return

        sufixo = ' [DRY-RUN]' if dry_run else ''
        for integ in integracoes:
            self.stdout.write(self.style.MIGRATE_HEADING(
                f'>> {integ.tenant.slug} / {integ.nome} (id={integ.pk}){sufixo}'
            ))
            try:
                service = HubsoftService(integ)
            except HubsoftServiceError as exc:
                self.stderr.write(self.style.ERROR(f'  ERRO ao instanciar: {exc}'))
                continue

            if categoria == 'todos':
                if apenas_auto:
                    self._sincronizar_todas_automaticas(service, dry_run)
                else:
                    resultado = service.sincronizar_configuracoes(dry_run=dry_run)
                    self._imprimir_todos(resultado)
            else:
                if apenas_auto and not self._categoria_em_modo_automatico(integ, categoria):
                    self.stdout.write(self.style.WARNING(
                        f'  {categoria}: pulado (modo de sync nao eh "automatico")'
                    ))
                    continue
                self._sincronizar_uma(service, categoria, dry_run)

    def _categoria_em_modo_automatico(self, integ, categoria: str) -> bool:
        feature = self.CATEGORIA_FEATURE.get(categoria)
        if not feature:
            return True  # categoria sem feature mapeada — nao bloqueia
        return integ.sync_habilitado(feature)

    def _sincronizar_todas_automaticas(self, service, dry_run: bool):
        """Roda categoria por categoria, pulando as que nao estao em automatico."""
        from apps.integracoes.services.hubsoft import HubsoftServiceError
        integ = service.integracao
        for categoria in ('servicos', 'vencimentos'):
            if not self._categoria_em_modo_automatico(integ, categoria):
                self.stdout.write(self.style.WARNING(f'  {categoria}: pulado (modo nao automatico)'))
                continue
            try:
                if categoria == 'servicos':
                    r = service.sincronizar_servicos_catalogo(dry_run=dry_run)
                else:
                    r = service.sincronizar_vencimentos(dry_run=dry_run)
                self._imprimir_resumo(categoria, r)
            except HubsoftServiceError as exc:
                self.stderr.write(self.style.ERROR(f'  {categoria}: {exc}'))
        from apps.integracoes.services.hubsoft import HubsoftService
        for chave in HubsoftService.CATALOGOS_CACHE:
            if not self._categoria_em_modo_automatico(integ, chave):
                self.stdout.write(self.style.WARNING(f'  {chave}: pulado (modo nao automatico)'))
                continue
            try:
                r = service.sincronizar_catalogo_cacheado(chave, dry_run=dry_run)
                self._imprimir_resumo(chave, r)
            except HubsoftServiceError as exc:
                self.stderr.write(self.style.ERROR(f'  {chave}: {exc}'))

    def _sincronizar_uma(self, service, categoria: str, dry_run: bool):
        from apps.integracoes.services.hubsoft import HubsoftServiceError
        try:
            if categoria == 'servicos':
                r = service.sincronizar_servicos_catalogo(dry_run=dry_run)
            elif categoria == 'vencimentos':
                r = service.sincronizar_vencimentos(dry_run=dry_run)
            else:
                r = service.sincronizar_catalogo_cacheado(categoria, dry_run=dry_run)
            self._imprimir_resumo(categoria, r)
        except HubsoftServiceError as exc:
            self.stderr.write(self.style.ERROR(f'  {categoria}: {exc}'))

    def _imprimir_todos(self, resultado: dict):
        for chave, r in resultado.items():
            if chave.startswith('_'):
                continue
            if 'erro' in r:
                self.stderr.write(self.style.ERROR(f'  {chave:24s}  ERRO: {r["erro"]}'))
            else:
                self._imprimir_resumo(chave, r)
        total = resultado.get('_total_geral', 0)
        self.stdout.write(self.style.SUCCESS(f'  TOTAL: {total} criados+atualizados'))

    def _imprimir_resumo(self, chave: str, r: dict):
        self.stdout.write(
            f'  {chave:24s}  total={r["total"]:>4}  criados={r["criados"]:>4}  '
            f'atualizados={r["atualizados"]:>4}  inalterados={r["inalterados"]:>4}'
        )
