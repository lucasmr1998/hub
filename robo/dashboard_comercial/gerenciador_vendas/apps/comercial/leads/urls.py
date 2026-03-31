from django.urls import path
from . import views

app_name = 'comercial_leads'

urlpatterns = [
    # Paginas de leads
    path('leads/', views.leads_view, name='leads'),
    path('leads/<int:lead_id>/conversa/', views.visualizar_conversa_lead, name='visualizar_conversa_lead'),
    path('leads/<int:lead_id>/conversa/pdf/', views.visualizar_conversa_pdf, name='visualizar_conversa_pdf'),

    # APIs de registro/update de leads
    path('api/leads/registrar/', views.registrar_lead_api, name='registrar_lead'),
    path('api/leads/atualizar/', views.atualizar_lead_api, name='atualizar_lead'),

    # APIs de imagens de leads
    path('api/leads/imagens/registrar/', views.registrar_imagem_lead_api, name='registrar_imagem_lead'),
    path('api/leads/imagens/listar/', views.listar_imagens_lead_api, name='listar_imagens_lead'),
    path('api/leads/imagens/deletar/', views.deletar_imagem_lead_api, name='deletar_imagem_lead'),
    path('api/leads/imagens/por-cliente/', views.imagens_por_cliente_api, name='imagens_por_cliente'),
    path('api/leads/imagens/validar/', views.validar_imagem_api, name='validar_imagem'),

    # APIs de prospectos
    path('api/prospectos/registrar/', views.registrar_prospecto_api, name='registrar_prospecto'),
    path('api/prospectos/atualizar/', views.atualizar_prospecto_api, name='atualizar_prospecto'),

    # APIs de historicos
    path('api/historicos/registrar/', views.registrar_historico_api, name='registrar_historico'),
    path('api/historicos/atualizar/', views.atualizar_historico_api, name='atualizar_historico'),

    # APIs de verificacao
    path('api/verificar-relacionamentos/', views.verificar_relacionamentos_api, name='verificar_relacionamentos'),

    # APIs de consulta (GET)
    path('api/consultar/leads/', views.consultar_leads_api, name='consultar_leads_api'),
    path('api/consultar/historicos/', views.consultar_historicos_api, name='consultar_historicos_api'),

    # APIs de validacao de vendas
    path('api/vendas/aprovar/', views.aprovar_venda_api, name='aprovar_venda'),
    path('api/vendas/rejeitar/', views.rejeitar_venda_api, name='rejeitar_venda'),

    # API para historico de contatos
    path('api/historico-contatos/', views.historico_contatos_api, name='historico_contatos'),
]
