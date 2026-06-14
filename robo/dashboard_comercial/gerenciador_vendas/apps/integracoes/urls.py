from django.urls import path
from . import views
from . import views_ordens_servico
from . import views_contratos_tentativas

app_name = 'integracoes'

urlpatterns = [
    # Página de gerenciamento
    path('', views.integracoes_view, name='integracoes'),
    path('saude/', views.saude_integracoes_view, name='saude_integracoes'),

    # Painel de Ordens de Servico (tentativas de OS via Matrix)
    path('ordens-servico/', views_ordens_servico.lista_ordens_servico, name='ordens_servico_lista'),
    path('ordens-servico/<uuid:grupo_id>/', views_ordens_servico.detalhe_ordem_servico, name='ordens_servico_detalhe'),
    path('ordens-servico/<uuid:grupo_id>/retentar/', views_ordens_servico.retentar_ordem_servico, name='ordens_servico_retentar'),

    # Painel de Contratos (tentativas de criar/aceitar contrato HubSoft via engine de automacao)
    path('contratos/', views_contratos_tentativas.lista_contratos, name='contratos_lista'),
    path('contratos/<uuid:grupo_id>/', views_contratos_tentativas.detalhe_contrato, name='contratos_detalhe'),
    path('contratos/<uuid:grupo_id>/retentar/', views_contratos_tentativas.retentar_contrato, name='contratos_retentar'),
    path('churn-score/', views.configuracao_churn_score_view, name='configuracao_churn_score'),
    path('<int:pk>/', views.integracao_detalhe, name='integracao_detalhe'),
    path('<int:pk>/api/defaults/', views.api_integracao_defaults, name='api_integracao_defaults'),
    path('<int:pk>/api/sincronizar-catalogo/', views.api_integracao_sincronizar_catalogo, name='api_integracao_sincronizar_catalogo'),
    path('<int:pk>/api/financeiro-sandbox/', views.api_integracao_financeiro_sandbox, name='api_integracao_financeiro_sandbox'),

    # APIs CRUD
    path('api/criar/', views.api_integracao_criar, name='api_integracao_criar'),
    path('api/<int:pk>/editar/', views.api_integracao_editar, name='api_integracao_editar'),
    path('api/<int:pk>/gerar-token/', views.api_integracao_gerar_token, name='api_integracao_gerar_token'),
    path('api/<int:pk>/excluir/', views.api_integracao_excluir, name='api_integracao_excluir'),
    path('api/<int:pk>/toggle/', views.api_integracao_toggle, name='api_integracao_toggle'),
    path('api/<int:pk>/testar/', views.api_integracao_testar, name='api_integracao_testar'),
    path('api/<int:pk>/modos-sync/', views.api_integracao_modos_sync, name='api_integracao_modos_sync'),
    path('api/<int:pk>/modos-sync/get/', views.api_integracao_modos_sync_get, name='api_integracao_modos_sync_get'),

    # APIs legadas
    path('api/clientes/', views.api_clientes_hubsoft, name='api_clientes_hubsoft'),
    path('api/lead/hubsoft-status/', views.api_lead_hubsoft_status, name='api_lead_hubsoft_status'),
]
