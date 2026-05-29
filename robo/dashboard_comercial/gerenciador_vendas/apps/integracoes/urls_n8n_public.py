"""URLs publicas (sem login) — webhooks de N8N externo e endpoints do Matrix."""
from django.urls import path
from . import views_n8n_webhook
from . import views_matrix_os

app_name = 'integracoes_n8n_public'

urlpatterns = [
    path('lead/', views_n8n_webhook.receber_lead, name='n8n_receber_lead'),
    path('lead/imagem/', views_n8n_webhook.registrar_imagem_lead, name='n8n_registrar_imagem_lead'),
    path('viabilidade/', views_n8n_webhook.viabilidade_check, name='n8n_viabilidade'),
    path('inbox/mensagem/', views_n8n_webhook.inbox_mensagem, name='n8n_inbox_mensagem'),
    path('conversa/estado/', views_n8n_webhook.conversa_estado, name='n8n_conversa_estado'),

    # Matrix / agendamento de OS (camada que substitui o apimatrix externo)
    path('matrix/datas-sem-domingo/', views_matrix_os.consultar_datas_sem_domingo, name='matrix_datas_sem_domingo'),
    path('matrix/consultar-agenda/', views_matrix_os.consultar_agenda, name='matrix_consultar_agenda'),
    path('matrix/abrir-atendimento/', views_matrix_os.abrir_atendimento, name='matrix_abrir_atendimento'),
    path('matrix/abrir-os/', views_matrix_os.abrir_os, name='matrix_abrir_os'),
]
