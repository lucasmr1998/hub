from django.urls import path
from . import views

app_name = 'suporte'

urlpatterns = [
    path('', views.dashboard_suporte, name='dashboard'),
    path('tickets/', views.ticket_lista, name='ticket_lista'),
    path('tickets/criar/', views.ticket_criar, name='ticket_criar'),
    path('tickets/<int:pk>/', views.ticket_detalhe, name='ticket_detalhe'),
    path('relatorios/', views.relatorios_suporte, name='relatorios'),
    path('tickets/api/acoes-massa/', views.api_acoes_massa, name='api_acoes_massa'),
    path('tickets/<int:pk>/api/avaliar/', views.api_avaliar_ticket, name='api_avaliar_ticket'),

    # Base de conhecimento
    path('conhecimento/', views.base_conhecimento, name='base_conhecimento'),
    path('conhecimento/gerenciar/', views.gerenciar_conhecimento, name='gerenciar_conhecimento'),
    path('conhecimento/artigo/<slug:slug>/', views.artigo_conhecimento, name='artigo_conhecimento'),
    path('conhecimento/api/feedback/<int:pk>/', views.api_artigo_feedback, name='api_artigo_feedback'),
    path('conhecimento/api/buscar/', views.api_buscar_conhecimento, name='api_buscar_conhecimento'),

    # Perguntas sem resposta (IA)
    path('conhecimento/perguntas/', views.perguntas_sem_resposta, name='perguntas_sem_resposta'),
    path('conhecimento/perguntas/<int:pk>/resolver/', views.api_pergunta_resolver, name='api_pergunta_resolver'),
    path('conhecimento/perguntas/<int:pk>/ignorar/', views.api_pergunta_ignorar, name='api_pergunta_ignorar'),
]
