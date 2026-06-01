from django.urls import path
from . import views
from .views_uazapi import uazapi_webhook
from .views_webhook import provider_webhook

app_name = 'inbox'

urlpatterns = [
    path('', views.inbox_view, name='inbox'),

    # Webhook genérico por provider (escalável) — com e sem barra
    path('api/webhook/<str:provedor>/<int:canal_id>/', provider_webhook, name='provider_webhook'),
    path('api/webhook/<str:provedor>/<int:canal_id>', provider_webhook),

    # Webhook Uazapi por tenant (token na URL identifica o tenant)
    path('api/webhook/<str:api_token>/', uazapi_webhook, name='uazapi_webhook_token'),
    path('api/webhook/<str:api_token>', uazapi_webhook),  # sem barra final

    # Webhook Uazapi legacy (backward compat)
    path('api/uazapi/webhook/', uazapi_webhook, name='uazapi_webhook'),
    path('api/uazapi/webhook', uazapi_webhook),

    # APIs internas (AJAX)
    path('api/conversas/', views.api_conversas, name='api_conversas'),
    path('api/conversas/<int:pk>/', views.api_conversa_detalhe, name='api_conversa_detalhe'),
    path('api/conversas/<int:pk>/mensagens/', views.api_mensagens, name='api_mensagens'),
    path('api/conversas/<int:pk>/midia/<int:msg_id>/', views.api_midia, name='api_midia'),
    path('api/conversas/<int:conversa_id>/resumir/', views.api_resumir_conversa, name='api_resumir_conversa'),
    path('csat/', views.csat_dashboard, name='csat_dashboard'),
    path('api/avaliacoes/<int:avaliacao_id>/responder/', views.api_avaliacao_responder, name='api_avaliacao_responder'),
    path('api/conversas/<int:pk>/enviar/', views.api_enviar_mensagem, name='api_enviar_mensagem'),
    path('api/conversas/<int:pk>/atribuir/', views.api_atribuir, name='api_atribuir'),
    path('api/conversas/<int:pk>/assumir/', views.api_assumir, name='api_assumir'),
    path('api/conversas/<int:pk>/resolver/', views.api_resolver, name='api_resolver'),
    path('api/conversas/<int:pk>/reabrir/', views.api_reabrir, name='api_reabrir'),
    path('api/conversas/<int:pk>/ticket/', views.api_criar_ticket, name='api_criar_ticket'),
    path('api/conversas/<int:pk>/transferir/', views.api_transferir, name='api_transferir'),
    path('api/conversas/<int:pk>/atualizar/', views.api_atualizar_conversa, name='api_atualizar_conversa'),
    path('api/conversas/<int:pk>/etiquetas/', views.api_etiquetas_conversa, name='api_etiquetas_conversa'),
    path('api/conversas/<int:pk>/notas/', views.api_notas, name='api_notas'),
    path('api/respostas-rapidas/', views.api_respostas_rapidas, name='api_respostas_rapidas'),
    path('api/etiquetas/', views.api_etiquetas, name='api_etiquetas'),
    path('api/agente/status/', views.api_atualizar_status_agente, name='api_status_agente'),
    path('api/agente/heartbeat/', views.api_agente_heartbeat, name='api_agente_heartbeat'),

    # Sugestoes IA de preenchimento de campos do Lead (v1, manual via botao no balao)
    path('api/mensagens/<int:msg_id>/sugerir-campos/', views.api_sugerir_campos, name='api_sugerir_campos'),
    path('api/leads/<int:lead_id>/aplicar-sugestoes/', views.api_aplicar_sugestoes, name='api_aplicar_sugestoes'),

    # Configurações e Dashboard
    path('configuracoes/', views.configuracoes_inbox, name='configuracoes'),
    path('dashboard/', views.dashboard_inbox, name='dashboard'),
]
