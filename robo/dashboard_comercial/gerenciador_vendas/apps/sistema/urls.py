from django.urls import path
from . import views

app_name = 'sistema'

urlpatterns = [
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

    # Configuracoes de recontato
    path('configuracoes/recontato/', views.configuracoes_recontato_view, name='configuracoes_recontato'),
]
