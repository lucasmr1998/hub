from django.core.management.base import BaseCommand
from apps.sistema.models import Funcionalidade, PerfilPermissao, Tenant


PERFIS_PADRAO = [
    {
        'nome': 'Vendedor',
        'descricao': 'Acesso básico ao CRM e Inbox. Vê apenas suas oportunidades e conversas.',
        'funcionalidades': [
            'comercial.ver_dashboard',
            'comercial.ver_pipeline',
            'comercial.mover_oportunidade',
            'comercial.criar_tarefa',
            'inbox.ver_minhas',
            'inbox.responder',
            'inbox.transferir_agente',
            'inbox.resolver',
        ],
    },
    {
        'nome': 'Supervisor Comercial',
        'descricao': 'Vê oportunidades da equipe, relatórios de desempenho e pode gerenciar metas.',
        'funcionalidades': [
            'comercial.ver_dashboard',
            'comercial.ver_pipeline',
            'comercial.mover_oportunidade',
            'comercial.ver_todas_oportunidades',
            'comercial.criar_tarefa',
            'comercial.ver_desempenho',
            'comercial.gerenciar_metas',
            'inbox.ver_minhas',
            'inbox.ver_equipe',
            'inbox.responder',
            'inbox.transferir_agente',
            'inbox.transferir_equipe',
            'inbox.resolver',
        ],
    },
    {
        'nome': 'Gerente Comercial',
        'descricao': 'Acesso total ao Comercial. Configura pipelines, equipes e metas.',
        'funcionalidades': [
            'comercial.ver_dashboard',
            'comercial.ver_pipeline',
            'comercial.mover_oportunidade',
            'comercial.ver_todas_oportunidades',
            'comercial.criar_tarefa',
            'comercial.ver_desempenho',
            'comercial.gerenciar_metas',
            'comercial.gerenciar_equipes',
            'comercial.configurar_pipeline',
            'inbox.ver_minhas',
            'inbox.ver_equipe',
            'inbox.ver_todas',
            'inbox.responder',
            'inbox.transferir_agente',
            'inbox.transferir_equipe',
            'inbox.resolver',
        ],
    },
    {
        'nome': 'Analista Marketing',
        'descricao': 'Gerencia leads, campanhas e segmentos. Visualiza automações.',
        'funcionalidades': [
            'marketing.ver_leads',
            'marketing.gerenciar_campanhas',
            'marketing.ver_segmentos',
            'marketing.gerenciar_segmentos',
            'marketing.ver_automacoes',
        ],
    },
    {
        'nome': 'Gerente Marketing',
        'descricao': 'Acesso total ao Marketing. Cria automações e configura landing page.',
        'funcionalidades': [
            'marketing.ver_leads',
            'marketing.gerenciar_campanhas',
            'marketing.ver_segmentos',
            'marketing.gerenciar_segmentos',
            'marketing.ver_automacoes',
            'marketing.gerenciar_automacoes',
            'marketing.configurar',
        ],
    },
    {
        'nome': 'Operador CS',
        'descricao': 'Gerencia membros do clube, cupons, parceiros e indicações.',
        'funcionalidades': [
            'cs.ver_dashboard',
            'cs.gerenciar_membros',
            'cs.gerenciar_cupons',
            'cs.gerenciar_indicacoes',
        ],
    },
    {
        'nome': 'Gerente CS',
        'descricao': 'Acesso total ao CS. Aprova cupons e configura regras do clube.',
        'funcionalidades': [
            'cs.ver_dashboard',
            'cs.gerenciar_membros',
            'cs.gerenciar_cupons',
            'cs.aprovar_cupons',
            'cs.gerenciar_indicacoes',
            'cs.configurar',
        ],
    },
    {
        'nome': 'Agente Suporte',
        'descricao': 'Atende conversas no Inbox. Vê apenas suas conversas.',
        'funcionalidades': [
            'inbox.ver_minhas',
            'inbox.responder',
            'inbox.transferir_agente',
            'inbox.resolver',
        ],
    },
    {
        'nome': 'Supervisor Suporte',
        'descricao': 'Vê conversas da equipe, transfere entre equipes.',
        'funcionalidades': [
            'inbox.ver_minhas',
            'inbox.ver_equipe',
            'inbox.responder',
            'inbox.transferir_agente',
            'inbox.transferir_equipe',
            'inbox.resolver',
        ],
    },
    {
        'nome': 'Gerente Suporte',
        'descricao': 'Acesso total ao Inbox. Configura equipes, filas e canais.',
        'funcionalidades': [
            'inbox.ver_minhas',
            'inbox.ver_equipe',
            'inbox.ver_todas',
            'inbox.responder',
            'inbox.transferir_agente',
            'inbox.transferir_equipe',
            'inbox.resolver',
            'inbox.configurar',
        ],
    },
    {
        'nome': 'Admin',
        'descricao': 'Acesso total a todos os módulos e configurações.',
        'funcionalidades': '__all__',
    },
]


class Command(BaseCommand):
    help = 'Cria perfis de permissão padrão para um tenant.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Slug do tenant. Se não informado, cria para todos os tenants ativos.',
        )

    def handle(self, *args, **options):
        tenant_slug = options.get('tenant')

        if tenant_slug:
            tenants = Tenant.objects.filter(slug=tenant_slug)
            if not tenants.exists():
                self.stderr.write(self.style.ERROR(f'Tenant "{tenant_slug}" não encontrado.'))
                return
        else:
            tenants = Tenant.objects.filter(ativo=True)

        todas_funcs = list(Funcionalidade.objects.all())
        if not todas_funcs:
            self.stderr.write(self.style.ERROR(
                'Nenhuma funcionalidade encontrada. Rode seed_funcionalidades primeiro.'
            ))
            return

        func_map = {f.codigo: f for f in todas_funcs}

        for tenant in tenants:
            criados = 0
            existentes = 0

            for perfil_data in PERFIS_PADRAO:
                nome = perfil_data['nome']

                if PerfilPermissao.objects.filter(tenant=tenant, nome=nome).exists():
                    existentes += 1
                    continue

                perfil = PerfilPermissao.objects.create(
                    tenant=tenant,
                    nome=nome,
                    descricao=perfil_data['descricao'],
                )

                codigos = perfil_data['funcionalidades']
                if codigos == '__all__':
                    perfil.funcionalidades.set(todas_funcs)
                else:
                    funcs = [func_map[c] for c in codigos if c in func_map]
                    perfil.funcionalidades.set(funcs)

                criados += 1

            self.stdout.write(self.style.SUCCESS(
                f'Tenant "{tenant.nome}": {criados} perfil(is) criado(s), {existentes} já existente(s).'
            ))
