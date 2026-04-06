from django.urls import path
from . import views

app_name = 'integracoes'

urlpatterns = [
    # Página de gerenciamento
    path('', views.integracoes_view, name='integracoes'),

    # APIs CRUD
    path('api/criar/', views.api_integracao_criar, name='api_integracao_criar'),
    path('api/<int:pk>/editar/', views.api_integracao_editar, name='api_integracao_editar'),
    path('api/<int:pk>/excluir/', views.api_integracao_excluir, name='api_integracao_excluir'),
    path('api/<int:pk>/toggle/', views.api_integracao_toggle, name='api_integracao_toggle'),
    path('api/<int:pk>/testar/', views.api_integracao_testar, name='api_integracao_testar'),

    # APIs legadas
    path('api/clientes/', views.api_clientes_hubsoft, name='api_clientes_hubsoft'),
    path('api/lead/hubsoft-status/', views.api_lead_hubsoft_status, name='api_lead_hubsoft_status'),
]
