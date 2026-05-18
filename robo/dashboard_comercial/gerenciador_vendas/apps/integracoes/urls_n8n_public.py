"""URLs publicas (sem login) — webhooks de N8N externo."""
from django.urls import path
from . import views_n8n_webhook

app_name = 'integracoes_n8n_public'

urlpatterns = [
    path('lead/', views_n8n_webhook.receber_lead, name='n8n_receber_lead'),
    path('viabilidade/', views_n8n_webhook.viabilidade_check, name='n8n_viabilidade'),
]
