"""
Cria um conjunto padrão de regras em RegraPipelineEstagio pra um tenant.

Uso:
  python manage.py seed_regras_pipeline_padrao --tenant <slug|id>
  python manage.py seed_regras_pipeline_padrao --all  # todos os tenants

O kit padrão é o que rodava na Megalink via robovendas e atende a maioria
dos fluxos de venda de ISP com integração HubSoft.
"""
from django.core.management.base import BaseCommand, CommandError


REGRAS_PADRAO = [
    # (slug do estágio, nome da regra, prioridade, condições)
    (
        'ganho',
        'Histórico marcou converteu_venda',
        0,
        [{'tipo': 'converteu_venda', 'operador': 'igual', 'valor': True}],
    ),
    (
        'ganho',
        'Tag Assinado foi adicionada',
        10,
        [{'tipo': 'tag', 'operador': 'igual', 'valor': 'Assinado'}],
    ),
    (
        'cliente-ativo',
        'Serviço HubSoft habilitado',
        0,
        [{'tipo': 'servico_status', 'operador': 'igual', 'valor': 'servico_habilitado'}],
    ),
    (
        'fechamento',
        'Todos os documentos validados',
        0,
        [{'tipo': 'imagem_status', 'operador': 'todas_iguais', 'valor': 'documentos_validos'}],
    ),
    (
        'perdido',
        'Algum documento rejeitado',
        0,
        [{'tipo': 'imagem_status', 'operador': 'igual', 'valor': 'documentos_rejeitados'}],
    ),
]


class Command(BaseCommand):
    help = 'Cria regras padrao do Motor de Automacoes do Pipeline pra um ou todos os tenants.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', help='Slug ou ID do tenant')
        parser.add_argument('--all', action='store_true', help='Aplica em todos os tenants ativos')
        parser.add_argument('--dry-run', action='store_true', help='Mostra o que seria criado sem salvar')

    def handle(self, *args, **opts):
        from apps.sistema.models import Tenant

        tenant_arg = opts.get('tenant')
        aplicar_todos = opts.get('all')
        dry_run = opts.get('dry_run')

        if not tenant_arg and not aplicar_todos:
            raise CommandError('Informe --tenant <slug|id> ou --all')

        if aplicar_todos:
            tenants = Tenant.objects.filter(ativo=True)
        else:
            q = Tenant.objects.all()
            if tenant_arg.isdigit():
                tenants = q.filter(pk=int(tenant_arg))
            else:
                tenants = q.filter(slug=tenant_arg)

        if not tenants.exists():
            raise CommandError(f'Nenhum tenant encontrado pra: {tenant_arg or "--all"}')

        total_criadas = 0
        for tenant in tenants:
            criadas = self._aplicar_pra_tenant(tenant, dry_run)
            total_criadas += criadas

        self.stdout.write(self.style.SUCCESS(
            f'{"[DRY-RUN] " if dry_run else ""}{total_criadas} regras criadas.'
        ))

    def _aplicar_pra_tenant(self, tenant, dry_run):
        from apps.comercial.crm.models import PipelineEstagio, RegraPipelineEstagio

        self.stdout.write(f'\n=== Tenant: {tenant.slug or tenant.pk} ===')

        estagios_por_slug = {
            e.slug: e
            for e in PipelineEstagio.all_tenants.filter(tenant=tenant, ativo=True)
        }

        if not estagios_por_slug:
            self.stdout.write(self.style.WARNING(
                '  Sem estagios cadastrados pra esse tenant; pulando.'
            ))
            return 0

        criadas = 0
        for slug_estagio, nome, prioridade, condicoes in REGRAS_PADRAO:
            estagio = estagios_por_slug.get(slug_estagio)
            if not estagio:
                self.stdout.write(
                    f"  - pulando '{nome}' (estagio '{slug_estagio}' nao existe)"
                )
                continue

            ja_existe = RegraPipelineEstagio.all_tenants.filter(
                tenant=tenant, estagio=estagio, nome=nome,
            ).exists()
            if ja_existe:
                self.stdout.write(f"  - '{nome}' ja existe")
                continue

            if dry_run:
                self.stdout.write(f"  + [dry] {estagio.nome} <- {nome}")
            else:
                RegraPipelineEstagio.objects.create(
                    tenant=tenant,
                    estagio=estagio,
                    nome=nome,
                    prioridade=prioridade,
                    condicoes=condicoes,
                    ativo=True,
                )
                self.stdout.write(self.style.SUCCESS(
                    f"  + {estagio.nome} <- {nome}"
                ))
            criadas += 1

        return criadas
