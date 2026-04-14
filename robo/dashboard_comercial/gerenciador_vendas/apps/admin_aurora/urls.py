from django.urls import path
from . import views

app_name = 'admin_aurora'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('tenant/<int:tenant_id>/', views.tenant_detalhe_view, name='tenant_detalhe'),
    path('tenant/criar/', views.criar_tenant_view, name='criar_tenant'),
    path('logs/', views.logs_view, name='logs'),
    path('monitoramento/', views.monitoramento_view, name='monitoramento'),
    path('api/toggle-tenant/', views.api_toggle_tenant, name='api_toggle_tenant'),

    # Planos
    path('planos/', views.planos_view, name='planos'),
    path('planos/<int:plano_id>/', views.plano_detalhe_view, name='plano_detalhe'),

    # Configuracoes
    path('configuracoes/recuperacao-senha/', views.config_recuperacao_senha_view, name='config_recuperacao_senha'),
    path('configuracoes/assistente/', views.config_assistente_view, name='config_assistente'),

    # Documentação e Produto
    path('produto/', views.produto_view, name='produto'),
    path('docs/', views.docs_view, name='docs'),
    path('backlog/', views.backlog_view, name='backlog'),
]
