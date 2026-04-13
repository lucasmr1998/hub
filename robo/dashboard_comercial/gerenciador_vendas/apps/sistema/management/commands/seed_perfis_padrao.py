"""
Seed de perfis de permissao padrao para cada tenant.
Idempotente: so cria o que nao existe no tenant.
"""
from django.core.management.base import BaseCommand
from apps.sistema.models import Tenant, Funcionalidade, PerfilPermissao


PERFIS = {
    'Vendedor': {
        'descricao': 'Acesso basico ao CRM e Inbox. Ve apenas suas oportunidades e conversas.',
        'funcionalidades': [
            'comercial.ver_dashboard', 'comercial.ver_pipeline', 'comercial.mover_oportunidade',
            'comercial.criar_tarefa', 'comercial.ver_desempenho',
            'inbox.ver_minhas', 'inbox.responder', 'inbox.transferir_agente', 'inbox.resolver',
        ],
    },
    'Supervisor Comercial': {
        'descricao': 'Ve oportunidades da equipe, relatorios e metas.',
        'funcionalidades': [
            'comercial.ver_dashboard', 'comercial.ver_pipeline', 'comercial.mover_oportunidade',
            'comercial.ver_todas_oportunidades', 'comercial.criar_tarefa', 'comercial.ver_desempenho',
            'comercial.gerenciar_metas',
            'inbox.ver_minhas', 'inbox.ver_equipe', 'inbox.responder',
            'inbox.transferir_agente', 'inbox.transferir_equipe', 'inbox.resolver',
        ],
    },
    'Gerente Comercial': {
        'descricao': 'Acesso total ao Comercial. Configura pipelines, equipes e metas.',
        'funcionalidades': [
            'comercial.ver_dashboard', 'comercial.ver_pipeline', 'comercial.mover_oportunidade',
            'comercial.ver_todas_oportunidades', 'comercial.criar_tarefa', 'comercial.ver_desempenho',
            'comercial.gerenciar_metas', 'comercial.gerenciar_equipes', 'comercial.configurar_pipeline',
            'inbox.ver_minhas', 'inbox.ver_equipe', 'inbox.ver_todas', 'inbox.responder',
            'inbox.transferir_agente', 'inbox.transferir_equipe', 'inbox.resolver',
        ],
    },
    'Analista Marketing': {
        'descricao': 'Gerencia leads, campanhas e segmentos.',
        'funcionalidades': [
            'marketing.ver_leads', 'marketing.gerenciar_campanhas',
            'marketing.ver_segmentos', 'marketing.gerenciar_segmentos', 'marketing.ver_automacoes',
        ],
    },
    'Gerente Marketing': {
        'descricao': 'Acesso total ao Marketing.',
        'funcionalidades': [
            'marketing.ver_leads', 'marketing.gerenciar_campanhas',
            'marketing.ver_segmentos', 'marketing.gerenciar_segmentos',
            'marketing.ver_automacoes', 'marketing.gerenciar_automacoes', 'marketing.configurar',
        ],
    },
    'Operador CS': {
        'descricao': 'Gerencia membros do clube, cupons e indicacoes.',
        'funcionalidades': [
            'cs.ver_dashboard', 'cs.gerenciar_membros', 'cs.gerenciar_cupons', 'cs.gerenciar_indicacoes',
        ],
    },
    'Gerente CS': {
        'descricao': 'Acesso total ao CS.',
        'funcionalidades': [
            'cs.ver_dashboard', 'cs.gerenciar_membros', 'cs.gerenciar_cupons',
            'cs.aprovar_cupons', 'cs.gerenciar_indicacoes', 'cs.configurar',
        ],
    },
    'Agente Suporte': {
        'descricao': 'Atende conversas no Inbox.',
        'funcionalidades': [
            'inbox.ver_minhas', 'inbox.responder', 'inbox.transferir_agente', 'inbox.resolver',
        ],
    },
    'Supervisor Suporte': {
        'descricao': 'Ve conversas da equipe, transfere entre equipes.',
        'funcionalidades': [
            'inbox.ver_minhas', 'inbox.ver_equipe', 'inbox.responder',
            'inbox.transferir_agente', 'inbox.transferir_equipe', 'inbox.resolver',
        ],
    },
    'Gerente Suporte': {
        'descricao': 'Acesso total ao Inbox.',
        'funcionalidades': [
            'inbox.ver_minhas', 'inbox.ver_equipe', 'inbox.ver_todas', 'inbox.responder',
            'inbox.transferir_agente', 'inbox.transferir_equipe', 'inbox.resolver', 'inbox.configurar',
        ],
    },
    'Admin': {
        'descricao': 'Acesso total a todos os modulos e configuracoes.',
        'funcionalidades': '__all__',
    },
}


class Command(BaseCommand):
    help = 'Cria perfis de permissao padrao para cada tenant que nao os tem (idempotente).'

    def handle(self, *args, **options):
        todas_funcs = {f.codigo: f for f in Funcionalidade.objects.all()}
        tenants = Tenant.objects.filter(ativo=True)

        total_criados = 0

        for tenant in tenants:
            for nome, config in PERFIS.items():
                perfil, created = PerfilPermissao.objects.get_or_create(
                    tenant=tenant,
                    nome=nome,
                    defaults={'descricao': config['descricao']},
                )

                if created:
                    if config['funcionalidades'] == '__all__':
                        perfil.funcionalidades.set(Funcionalidade.objects.all())
                    else:
                        funcs = [todas_funcs[c] for c in config['funcionalidades'] if c in todas_funcs]
                        perfil.funcionalidades.set(funcs)
                    total_criados += 1

        self.stdout.write(self.style.SUCCESS(
            f'Perfis: {total_criados} criados para {tenants.count()} tenant(s) ({len(PERFIS)} perfis padrao)'
        ))
