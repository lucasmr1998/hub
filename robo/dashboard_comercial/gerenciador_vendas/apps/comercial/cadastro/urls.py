from django.urls import path
from . import views

app_name = 'comercial_cadastro'

urlpatterns = [
    # Pagina de cadastro
    path('cadastro/', views.cadastro_cliente_view, name='cadastro_cliente'),

    # APIs de cadastro
    path('api/cadastro/cliente/', views.api_cadastro_cliente, name='api_cadastro_cliente'),
    path('api/planos/internet/', views.api_planos_internet, name='api_planos_internet'),
    path('api/vencimentos/', views.api_vencimentos, name='api_vencimentos'),
    path('api/cep/<str:cep>/', views.api_consulta_cep, name='api_consulta_cep'),

    # Paginas de configuracao de cadastro
    path('configuracoes/cadastro/', views.configuracoes_cadastro_view, name='configuracoes_cadastro'),
    path('configuracoes/cadastro/save/', views.salvar_configuracoes_cadastro_view, name='salvar_configuracoes_cadastro'),
    path('configuracoes/planos/', views.planos_internet_view, name='planos_internet'),
    path('configuracoes/vencimentos/', views.opcoes_vencimento_view, name='opcoes_vencimento'),

    # APIs de gerenciamento de cadastro
    path('api/configuracoes/cadastro/', views.api_configuracoes_cadastro, name='api_configuracoes_cadastro'),
    path('api/configuracoes/planos/', views.api_planos_internet_gerencia, name='api_planos_internet_gerencia'),
    path('api/configuracoes/vencimentos/', views.api_opcoes_vencimento_gerencia, name='api_opcoes_vencimento_gerencia'),
]
