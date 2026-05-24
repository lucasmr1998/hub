"""URLs publicas (sem login) — webhooks de N8N externo."""
from django.urls import path
from . import views_n8n_webhook

app_name = 'integracoes_n8n_public'

urlpatterns = [
    path('lead/', views_n8n_webhook.receber_lead, name='n8n_receber_lead'),
    path('lead/imagem/', views_n8n_webhook.registrar_imagem_lead, name='n8n_registrar_imagem_lead'),
    path('viabilidade/', views_n8n_webhook.viabilidade_check, name='n8n_viabilidade'),
    path('inbox/mensagem/', views_n8n_webhook.inbox_mensagem, name='n8n_inbox_mensagem'),
    path('conversa/estado/', views_n8n_webhook.conversa_estado, name='n8n_conversa_estado'),
]
