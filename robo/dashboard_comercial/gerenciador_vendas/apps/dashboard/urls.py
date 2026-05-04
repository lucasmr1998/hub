from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Home personalizada por perfil — entry point pós-login
    path('home/', views.home_router, name='home'),

    # Dashboard principal
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard1/', views.dashboard1, name='dashboard1'),

    # APIs para dados do dashboard
    path('api/dashboard/data/', views.dashboard_data, name='dashboard_data'),
    path('api/dashboard/charts/', views.dashboard_charts_data, name='dashboard_charts'),
    path('api/dashboard/tables/', views.dashboard_tables_data, name='dashboard_tables'),
    path('api/dashboard/leads/', views.dashboard_leads_data, name='dashboard_leads'),
    path('api/dashboard/prospectos/', views.dashboard_prospectos_data, name='dashboard_prospectos'),
    path('api/dashboard/historico/', views.dashboard_historico_data, name='dashboard_historico'),
    path('api/dashboard/contatos/realtime/', views.dashboard_contatos_realtime, name='dashboard_contatos_realtime'),
    path('api/dashboard/contato/<str:telefone>/historico/', views.dashboard_contato_historico, name='dashboard_contato_historico'),
    path('api/dashboard/ultimas-conversoes/', views.dashboard_ultimas_conversoes, name='dashboard_ultimas_conversoes'),

    # API para insights do funil de vendas
    path('api/dashboard/funil/insights/', views.dashboard_funil_insights, name='dashboard_funil_insights'),

    # Paginas de vendas e relatorios
    path('vendas/', views.vendas_view, name='vendas'),
    path('relatorios/', views.relatorios_view, name='relatorios'),
    path('relatorios/leads/', views.relatorio_leads_view, name='relatorio_leads'),
    path('relatorios/clientes/', views.relatorio_clientes_view, name='relatorio_clientes'),
    path('relatorios/atendimentos/', views.relatorio_atendimentos_view, name='relatorio_atendimentos'),
    path('analise/atendimentos/', views.analise_atendimentos_view, name='analise_atendimentos'),
    path('relatorios/conversoes/', views.relatorio_conversoes_view, name='relatorio_conversoes'),
    path('ajuda/', views.ajuda_view, name='ajuda'),
    path('documentacao/', views.documentacao_view, name='documentacao'),

    # APIs de analise de atendimentos
    path('api/analise/atendimentos/data/', views.api_analise_atendimentos_data, name='api_analise_atendimentos_data'),
    path('api/analise/atendimentos/fluxos/', views.api_analise_atendimentos_fluxos, name='api_analise_atendimentos_fluxos'),
    path('api/analise/atendimentos/detalhada/', views.api_analise_detalhada_atendimentos, name='api_analise_detalhada_atendimentos'),
    path('api/jornada/cliente/', views.api_jornada_cliente_completa, name='api_jornada_cliente_completa'),
    path('api/atendimento/tempo-real/', views.api_atendimento_em_tempo_real, name='api_atendimento_em_tempo_real'),

    # Documentacao da API
    path('api/docs/', views.api_swagger_view, name='api_swagger'),
    path('api/docs/markdown/', views.api_documentation_view, name='api_documentation'),
    path('api/docs/n8n/', views.n8n_guide_view, name='n8n_guide'),
]
