from django.urls import path

from . import views_n8n
from apps.inbox import views_n8n as inbox_views_n8n

app_name = 'api_n8n'

urlpatterns = [
    # ── Leads ────────────────────────────────────────────────────────
    path('leads/', views_n8n.LeadAPIView.as_view(), name='leads'),
    path('leads/<int:pk>/', views_n8n.LeadAPIView.as_view(), name='lead_detail'),
    path('leads/buscar/', views_n8n.LeadBuscaAPIView.as_view(), name='lead_busca'),

    # ── Imagens de Lead ──────────────────────────────────────────────
    path('leads/imagens/', views_n8n.LeadImagemAPIView.as_view(), name='lead_imagens'),
    path('leads/imagens/<int:pk>/', views_n8n.LeadImagemAPIView.as_view(), name='lead_imagem_detail'),

    # ── Prospectos ───────────────────────────────────────────────────
    path('prospectos/', views_n8n.ProspectoAPIView.as_view(), name='prospectos'),
    path('prospectos/<int:pk>/', views_n8n.ProspectoAPIView.as_view(), name='prospecto_detail'),

    # ── Historico de Contato ─────────────────────────────────────────
    path('contatos/', views_n8n.HistoricoContatoAPIView.as_view(), name='contatos'),
    path('contatos/<int:pk>/', views_n8n.HistoricoContatoAPIView.as_view(), name='contato_detail'),

    # ── Fluxos (read-only) ──────────────────────────────────────────
    path('fluxos/', views_n8n.FluxoListAPIView.as_view(), name='fluxos'),

    # ── Atendimento ─────────────────────────────────────────────────
    path('atendimentos/', views_n8n.AtendimentoN8NAPIView.as_view(), name='atendimentos'),
    path('atendimentos/<int:pk>/', views_n8n.AtendimentoN8NAPIView.as_view(), name='atendimento_detail'),
    path('atendimentos/<int:pk>/responder/', views_n8n.AtendimentoRespostaAPIView.as_view(), name='atendimento_responder'),
    path('atendimentos/<int:pk>/finalizar/', views_n8n.AtendimentoFinalizarAPIView.as_view(), name='atendimento_finalizar'),

    # ── Campanhas ───────────────────────────────────────────────────
    path('campanhas/detectar/', views_n8n.CampanhaDeteccaoAPIView.as_view(), name='campanha_detectar'),

    # ── Inbox ───────────────────────────────────────────────────────
    path('inbox/mensagem-recebida/', inbox_views_n8n.InboxMensagemRecebidaAPIView.as_view(), name='inbox_mensagem_recebida'),
    path('inbox/status-mensagem/', inbox_views_n8n.InboxStatusMensagemAPIView.as_view(), name='inbox_status_mensagem'),
]
