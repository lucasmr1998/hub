from django.urls import path
from . import views

app_name = 'integracoes'

urlpatterns = [
    # Página de gerenciamento
    path('', views.integracoes_view, name='integracoes'),
    path('<int:pk>/', views.integracao_detalhe, name='integracao_detalhe'),
    path('<int:pk>/api/defaults/', views.api_integracao_defaults, name='api_integracao_defaults'),
    path('<int:pk>/api/sincronizar-catalogo/', views.api_integracao_sincronizar_catalogo, name='api_integracao_sincronizar_catalogo'),

    # APIs CRUD
    path('api/criar/', views.api_integracao_criar, name='api_integracao_criar'),
    path('api/<int:pk>/editar/', views.api_integracao_editar, name='api_integracao_editar'),
    path('api/<int:pk>/excluir/', views.api_integracao_excluir, name='api_integracao_excluir'),
    path('api/<int:pk>/toggle/', views.api_integracao_toggle, name='api_integracao_toggle'),
    path('api/<int:pk>/testar/', views.api_integracao_testar, name='api_integracao_testar'),
    path('api/<int:pk>/modos-sync/', views.api_integracao_modos_sync, name='api_integracao_modos_sync'),
    path('api/<int:pk>/modos-sync/get/', views.api_integracao_modos_sync_get, name='api_integracao_modos_sync_get'),

    # APIs legadas
    path('api/clientes/', views.api_clientes_hubsoft, name='api_clientes_hubsoft'),
    path('api/lead/hubsoft-status/', views.api_lead_hubsoft_status, name='api_lead_hubsoft_status'),
]
