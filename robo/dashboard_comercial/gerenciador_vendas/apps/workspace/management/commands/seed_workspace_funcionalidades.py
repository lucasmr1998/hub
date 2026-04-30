"""
Cadastra as 4 funcionalidades do Workspace e adiciona aos perfis padrão.

Uso:
    python manage.py seed_workspace_funcionalidades [--settings=...]

Idempotente: pode rodar várias vezes, não duplica.

Defaults aplicados (decisão A do plano — granular):
- Admin: todas as 4
- Supervisor Comercial / Marketing / CS: ver + criar_projeto + editar_proprios
- Supervisor Suporte: ver + editar_proprios
- Outros perfis: nenhuma (configura manualmente se quiser)
"""
from django.core.management.base import BaseCommand

from apps.sistema.models import Funcionalidade, PerfilPermissao


FUNCIONALIDADES = [
    {
        'codigo': 'workspace.ver',
        'nome': 'Ver Workspace',
        'descricao': 'Acessar a área de Workspace (qualquer tela)',
        'modulo': 'workspace',
        'ordem': 10,
    },
    {
        'codigo': 'workspace.criar_projeto',
        'nome': 'Criar projeto',
        'descricao': 'Criar projetos novos no Workspace',
        'modulo': 'workspace',
        'ordem': 20,
    },
    {
        'codigo': 'workspace.editar_proprios',
        'nome': 'Editar próprios',
        'descricao': 'Editar projetos/tarefas/documentos próprios (responsável ou criador)',
        'modulo': 'workspace',
        'ordem': 30,
    },
    {
        'codigo': 'workspace.editar_todos',
        'nome': 'Editar todos',
        'descricao': 'Editar projetos/tarefas/documentos de qualquer usuário do tenant',
        'modulo': 'workspace',
        'ordem': 40,
    },
]


# Mapeamento perfil -> funcionalidades concedidas
PERFIL_DEFAULTS = {
    'Admin': ['workspace.ver', 'workspace.criar_projeto', 'workspace.editar_proprios', 'workspace.editar_todos'],
    'Supervisor Comercial': ['workspace.ver', 'workspace.criar_projeto', 'workspace.editar_proprios'],
    'Supervisor Marketing': ['workspace.ver', 'workspace.criar_projeto', 'workspace.editar_proprios'],
    'Supervisor CS': ['workspace.ver', 'workspace.criar_projeto', 'workspace.editar_proprios'],
    'Supervisor Suporte': ['workspace.ver', 'workspace.editar_proprios'],
}


class Command(BaseCommand):
    help = 'Cadastra funcionalidades do Workspace e aplica defaults nos perfis padrão.'

    def handle(self, *args, **options):
        # 1) Cadastrar funcionalidades (idempotente via codigo unique)
        self.stdout.write(self.style.NOTICE('Cadastrando funcionalidades do Workspace...'))
        criadas = 0
        atualizadas = 0
        for f in FUNCIONALIDADES:
            obj, created = Funcionalidade.objects.update_or_create(
                codigo=f['codigo'],
                defaults={
                    'modulo': f['modulo'],
                    'nome': f['nome'],
                    'descricao': f['descricao'],
                    'ordem': f['ordem'],
                },
            )
            if created:
                criadas += 1
                self.stdout.write(f'  + criada: {f["codigo"]}')
            else:
                atualizadas += 1
                self.stdout.write(f'  ~ atualizada: {f["codigo"]}')

        self.stdout.write(self.style.SUCCESS(
            f'Funcionalidades: {criadas} criadas, {atualizadas} atualizadas.'
        ))

        # 2) Aplicar defaults nos perfis padrão de TODOS os tenants
        self.stdout.write(self.style.NOTICE('\nAplicando defaults nos perfis padrão...'))
        funcs_por_codigo = {f.codigo: f for f in Funcionalidade.objects.filter(modulo='workspace')}

        atualizacoes = 0
        for nome_perfil, codigos in PERFIL_DEFAULTS.items():
            perfis = PerfilPermissao.objects.filter(nome=nome_perfil)
            funcs = [funcs_por_codigo[c] for c in codigos if c in funcs_por_codigo]
            for perfil in perfis:
                perfil.funcionalidades.add(*funcs)
                atualizacoes += 1
                self.stdout.write(
                    f'  -> {perfil.tenant.nome} / {perfil.nome}: '
                    f'+{len(funcs)} funcionalidades'
                )

        self.stdout.write(self.style.SUCCESS(
            f'\nDefaults aplicados em {atualizacoes} perfis.'
        ))
        self.stdout.write(self.style.SUCCESS('\nSeed do Workspace concluído.'))
