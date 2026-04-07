from django.urls import path
from . import views

app_name = 'sistema'

urlpatterns = [
    # Health check
    path('health/', views.health_check, name='health_check'),

    # Setup inicial
    path('setup/', views.setup_inicial_view, name='setup_inicial'),

    # Autenticacao
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Pagina principal de configuracoes
    path('configuracoes/', views.configuracoes_view, name='configuracoes'),

    # Gerenciamento de usuarios
    path('configuracoes/usuarios/', views.configuracoes_usuarios_view, name='configuracoes_usuarios'),
    path('api/configuracoes/usuarios/', views.api_usuarios_criar, name='api_usuarios_criar'),
    path('api/configuracoes/usuarios/<int:user_id>/', views.api_usuarios_editar, name='api_usuarios_editar'),
    path('api/configuracoes/usuarios/<int:user_id>/deletar/', views.api_usuarios_deletar, name='api_usuarios_deletar'),

    # Perfis de permissão
    path('configuracoes/perfis/', views.perfis_permissao_view, name='perfis_permissao'),
    path('api/configuracoes/perfis/', views.api_perfis_permissao, name='api_perfis_permissao'),
    path('api/configuracoes/perfis/<int:perfil_id>/', views.api_perfil_permissao_detalhe, name='api_perfil_permissao_detalhe'),

    # Perfil do usuário
    path('perfil/', views.perfil_usuario_view, name='perfil_usuario'),

    # Configuracoes de recontato
    path('configuracoes/recontato/', views.configuracoes_recontato_view, name='configuracoes_recontato'),

    # Logs de auditoria
    path('configuracoes/logs/', views.logs_auditoria_view, name='logs_auditoria'),
]
