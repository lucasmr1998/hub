"""RBAC — controle de acesso por PERFIL (o que cada tipo de usuário vê e opera).

Catálogo de capacidades (código → rótulo) usado tanto na tela de matriz de perfis
quanto no enforcement (menu, abas, decorators, escopo de dados). Fonte única.

- superusuário: tem TODAS as capacidades e escopo 'todos'.
- usuário com perfil(s): capacidades = união dos perfis ativos; escopo = o mais amplo.
- usuário SEM perfil (rollout): recebe um baseline seguro (CAP_PADRAO / escopo 'proprios')
  para não travar a ferramenta até o admin atribuir um perfil.
"""
import functools

from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import redirect

# ── Catálogo (grupos ordenados → [(codigo, rotulo)]) ────────────────────────
CAPACIDADES = [
    ('Visão geral', [
        ('ver_dashboard', 'Dashboard'),
        ('ver_analises',  'Análises'),
    ]),
    ('Comercial', [
        ('ver_leads',  'Leads'),
        ('ver_vendas', 'Vendas'),
    ]),
    ('Pipelines (ver)', [
        ('ver_pipeline_aquisicao',    'Pipeline · Aquisição'),
        ('ver_pipeline_novo_servico', 'Pipeline · Novo Serviço'),
        ('ver_pipeline_upgrade',      'Pipeline · Upgrade'),
        ('ver_pipeline_atendimento',  'Pipeline · Atendimento'),
        ('ver_pipeline_indicacao',    'Pipeline · Indicação'),
        ('ver_pipeline_wifeed',       'Pipeline · Wifeed'),
    ]),
    ('CRM', [
        ('ver_tarefas',   'Tarefas'),
        ('ver_desempenho', 'Desempenho'),
        ('ver_retencao',  'Retenção'),
        ('ver_metas',     'Metas'),
        ('ver_segmentos', 'Segmentos'),
    ]),
    ('Administração', [
        ('ver_config', 'Configurações do CRM'),
        ('ver_admin',  'Admin / gestão de usuários e perfis'),
    ]),
    ('Operar (ações)', [
        ('operar_mover_oportunidade', 'Mover oportunidades no kanban'),
        ('operar_editar_lead',        'Editar dados do lead'),
        ('operar_indicacao',          'Operar indicações (criar/converter/agendar)'),
        ('operar_wifeed',             'Operar Wifeed (criar/converter/agendar)'),
        ('operar_atribuir',           'Atribuir responsável'),
        ('operar_tarefas',            'Criar/concluir tarefas e notas'),
        ('gerenciar_usuarios',        'Gerenciar usuários'),
        ('gerenciar_perfis',          'Gerenciar perfis de acesso'),
        ('gerenciar_config',          'Alterar configurações do sistema'),
        ('gerenciar_wifeed',          'Gerenciar fontes Wifeed (locais/campanhas)'),
    ]),
]

TODAS_CAPACIDADES = {cod for _, itens in CAPACIDADES for cod, _ in itens}

# pipeline_tipo → capacidade de visualização
PIPELINE_CAP = {
    'aquisicao':    'ver_pipeline_aquisicao',
    'novo_servico': 'ver_pipeline_novo_servico',
    'upgrade':      'ver_pipeline_upgrade',
    'atendimento':  'ver_pipeline_atendimento',
    'indicacao':    'ver_pipeline_indicacao',
    'wifeed':       'ver_pipeline_wifeed',
}

# Usuário SEM perfil = SEM acesso (decisão 2026-07-09): o acesso é LIBERADO pela
# atribuição de um Perfil de Acesso — os usuários vêm do portal TecHub (SSO +
# sincronização) e o admin concede o perfil na tela Perfis de Acesso.
# Superuser continua com todas as capacidades.
CAP_PADRAO: set = set()

_ESCOPO_PESO = {'proprios': 0, 'pipeline': 1, 'todos': 2}


def _perfis_ativos(user):
    return list(user.perfis_acesso.filter(ativo=True)) if user and user.is_authenticated else []


def capacidades_do_usuario(user):
    """Set de códigos de capacidade do usuário. Superuser = todas."""
    if not user or not user.is_authenticated:
        return set()
    if user.is_superuser:
        return set(TODAS_CAPACIDADES)
    perfis = _perfis_ativos(user)
    if not perfis:
        return set(CAP_PADRAO)
    caps = set()
    for p in perfis:
        caps.update(p.capacidades or [])
    return caps & TODAS_CAPACIDADES


def usuario_pode(user, codigo):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return codigo in capacidades_do_usuario(user)


def escopo_do_usuario(user):
    """Escopo de dados mais amplo entre os perfis. Superuser = 'todos'."""
    if user and user.is_authenticated and user.is_superuser:
        return 'todos'
    perfis = _perfis_ativos(user)
    if not perfis:
        return 'proprios'
    return max((p.escopo_dados for p in perfis), key=lambda e: _ESCOPO_PESO.get(e, 0))


# Pipelines OCULTOS do sistema (2026-07-13, pedido do usuário): 'atendimento'
# saiu da visão por ora (sem uso — nada cria oportunidades desse tipo). Para
# reativar, basta remover daqui. Vale para todos, inclusive superuser.
PIPELINES_OCULTOS = {'atendimento'}


def pipelines_visiveis(user):
    """Lista de pipeline_tipo que o usuário pode ver (na ordem do catálogo)."""
    caps = capacidades_do_usuario(user)
    return [t for t, cap in PIPELINE_CAP.items()
            if cap in caps and t not in PIPELINES_OCULTOS]


def usuarios_por_capacidade(codigo):
    """Usuários (ativos) que têm a capacidade — para destino de notificações.

    Inclui superusuários e quem tem um perfil ativo que concede o código.
    """
    from django.db.models import Q
    return (User.objects.filter(is_active=True)
            .filter(Q(is_superuser=True)
                    | Q(perfis_acesso__ativo=True,
                        perfis_acesso__capacidades__contains=codigo))
            .distinct())


# ── Enforcement ─────────────────────────────────────────────────────────────
def _quer_json(request):
    return (request.headers.get('x-requested-with') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('Accept', '')
            or request.content_type == 'application/json'
            or request.path.rstrip('/').split('/')[-1].startswith('api')
            or '/api' in request.path or request.method in ('POST', 'PUT', 'DELETE'))


def requer_cap(codigo):
    """Decorator: exige a capacidade `codigo`. 403 JSON p/ API, redirect p/ página."""
    def deco(view):
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            if usuario_pode(request.user, codigo):
                return view(request, *args, **kwargs)
            if _quer_json(request):
                return JsonResponse({'ok': False, 'erro': 'Sem permissão para esta ação.'},
                                    status=403)
            from django.contrib import messages
            messages.error(request, 'Você não tem permissão para acessar esta página.')
            return redirect('vendas_web:dashboard1')
        return wrapper
    return deco


def permissoes_context(request):
    """Context processor: injeta `cap` (set de códigos) e `escopo` nos templates."""
    u = getattr(request, 'user', None)
    if not u or not u.is_authenticated:
        return {'cap': set(), 'escopo': 'proprios', 'pipelines_permitidos': []}
    return {
        'cap': capacidades_do_usuario(u),
        'escopo': escopo_do_usuario(u),
        'pipelines_permitidos': pipelines_visiveis(u),
    }
