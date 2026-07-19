from django.urls import path
from . import views

app_name = 'integracoes'

urlpatterns = [
    path('api/clientes/', views.api_clientes_hubsoft, name='api_clientes_hubsoft'),
    path(
        'api/lead/hubsoft-status/',
        views.api_lead_hubsoft_status,
        name='api_lead_hubsoft_status',
    ),
    path('api/cliente/atendimentos/', views.api_cliente_atendimentos, name='api_cliente_atendimentos'),
    path('api/cliente/ordens-servico/', views.api_cliente_ordens_servico, name='api_cliente_ordens_servico'),
    path('api/cliente/novos-servicos/', views.api_cliente_novos_servicos, name='api_cliente_novos_servicos'),
    path(
        'api/agendar-instalacao-ia/<int:lead_id>/',
        views.api_agendar_instalacao_ia,
        name='api_agendar_instalacao_ia',
    ),
    path(
        'api/verificar-cliente-cpf/<int:lead_id>/',
        views.api_verificar_cliente_por_cpf,
        name='api_verificar_cliente_por_cpf',
    ),
    path(
        'api/lead/<int:lead_id>/proxima-instalacao/',
        views.api_proxima_instalacao_lead,
        name='api_proxima_instalacao_lead',
    ),
    path(
        'api/clube/indicacoes/criar/',
        views.api_clube_indicacao_criar,
        name='api_clube_indicacao_criar',
    ),
]