from django.urls import path
from . import views
from . import views_api

app_name = 'comercial_atendimento'

urlpatterns = [
    # ========================================================================
    # APIS COMPLETAS DE ATENDIMENTO - CRUD
    # ========================================================================

    # APIs de Fluxos de Atendimento
    path('api/fluxos/', views_api.consultar_fluxos_api, name='api_fluxos_consultar'),
    path('api/fluxos/criar/', views_api.criar_fluxo_api, name='api_fluxos_criar'),
    path('api/fluxos/<int:fluxo_id>/atualizar/', views_api.atualizar_fluxo_api, name='api_fluxos_atualizar'),
    path('api/fluxos/<int:fluxo_id>/deletar/', views_api.deletar_fluxo_api, name='api_fluxos_deletar'),

    # APIs de Questoes de Fluxo
    path('api/questoes/', views_api.consultar_questoes_api, name='api_questoes_consultar'),
    path('api/questoes/criar/', views_api.criar_questao_api, name='api_questoes_criar'),
    path('api/questoes/<int:questao_id>/atualizar/', views_api.atualizar_questao_api, name='api_questoes_atualizar'),
    path('api/questoes/<int:questao_id>/deletar/', views_api.deletar_questao_api, name='api_questoes_deletar'),

    # APIs de Atendimentos de Fluxo
    path('api/atendimentos/', views_api.consultar_atendimentos_api, name='api_atendimentos_consultar'),
    path('api/atendimentos/criar/', views_api.criar_atendimento_api, name='api_atendimentos_criar'),
    path('api/atendimentos/<int:atendimento_id>/atualizar/', views_api.atualizar_atendimento_api, name='api_atendimentos_atualizar'),
    path('api/atendimentos/<int:atendimento_id>/responder/', views_api.responder_questao_api, name='api_atendimentos_responder'),
    path('api/atendimentos/<int:atendimento_id>/finalizar/', views_api.finalizar_atendimento_api, name='api_atendimentos_finalizar'),

    # APIs de Respostas de Questoes
    path('api/respostas/', views_api.consultar_respostas_api, name='api_respostas_consultar'),

    # APIs de Estatisticas
    path('api/atendimento/estatisticas/', views_api.estatisticas_atendimento_api, name='api_atendimento_estatisticas'),

    # ========================================================================
    # APIS ESPECIFICAS PARA INTEGRACAO COM N8N
    # ========================================================================

    # APIs para gerenciamento de atendimento pelo N8N
    path('api/n8n/atendimento/iniciar/', views_api.iniciar_atendimento_n8n, name='api_n8n_iniciar_atendimento'),
    path('api/n8n/atendimento/<int:atendimento_id>/consultar/', views_api.consultar_atendimento_n8n, name='api_n8n_consultar_atendimento'),
    path('api/n8n/atendimento/<int:atendimento_id>/responder/', views_api.responder_questao_n8n, name='api_n8n_responder_questao'),
    path('api/n8n/atendimento/<int:atendimento_id>/avancar/', views_api.avancar_questao_n8n, name='api_n8n_avancar_questao'),
    path('api/n8n/atendimento/<int:atendimento_id>/finalizar/', views_api.finalizar_atendimento_n8n, name='api_n8n_finalizar_atendimento'),

    # APIs para busca e consulta pelo N8N
    path('api/n8n/lead/buscar/', views_api.buscar_lead_por_telefone_n8n, name='api_n8n_buscar_lead'),
    path('api/n8n/lead/criar/', views_api.criar_lead_n8n, name='api_n8n_criar_lead'),
    path('api/n8n/fluxos/', views_api.listar_fluxos_ativos_n8n, name='api_n8n_listar_fluxos'),
    path('api/n8n/fluxo/<int:fluxo_id>/questao/<int:indice_questao>/', views_api.obter_questao_n8n, name='api_n8n_obter_questao'),

    # APIs para controle de atendimento pelo N8N
    path('api/n8n/atendimento/<int:atendimento_id>/pausar/', views_api.pausar_atendimento_n8n, name='api_n8n_pausar_atendimento'),
    path('api/n8n/atendimento/<int:atendimento_id>/retomar/', views_api.retomar_atendimento_n8n, name='api_n8n_retomar_atendimento'),

    # APIs especificas para fluxo inteligente
    path('api/n8n/atendimento/<int:atendimento_id>/tentativas/', views_api.consultar_tentativas_resposta_n8n, name='api_n8n_consultar_tentativas'),
    path('api/n8n/fluxo/<int:fluxo_id>/questao/<int:indice_questao>/inteligente/', views_api.obter_questao_inteligente_n8n, name='api_n8n_questao_inteligente'),
    path('api/n8n/atendimento/<int:atendimento_id>/estatisticas/inteligente/', views_api.estatisticas_atendimento_inteligente_n8n, name='api_n8n_estatisticas_inteligente'),

    # Rotas compativeis antigas (mantidas para compatibilidade)
    path('api/consultar/fluxos/', views_api.consultar_fluxos_api, name='consultar_fluxos_api'),
    path('api/consultar/questoes/', views_api.consultar_questoes_api, name='consultar_questoes_api'),
    path('api/consultar/atendimentos/', views_api.consultar_atendimentos_api, name='consultar_atendimentos_api'),
    path('api/consultar/respostas/', views_api.consultar_respostas_api, name='consultar_respostas_api'),

    # ========================================================================
    # PAGINAS DE CONFIGURACAO DE ATENDIMENTO
    # ========================================================================

    path('configuracoes/fluxos/', views.fluxos_atendimento_view, name='fluxos_atendimento'),
    path('configuracoes/sessoes/', views.sessoes_atendimento_view, name='sessoes_atendimento'),
    path('configuracoes/sessoes/<int:atendimento_id>/', views.sessao_detalhe_view, name='sessao_detalhe'),
    path('configuracoes/sessoes/<int:atendimento_id>/fluxo/', views.sessao_fluxo_visual_view, name='sessao_fluxo_visual'),
    path('configuracoes/fluxos/<int:fluxo_id>/editor/', views.editor_fluxo_view, name='editor_fluxo'),
    path('api/fluxos/<int:fluxo_id>/salvar-fluxo/', views.salvar_fluxo_api, name='salvar_fluxo'),
    path('api/fluxos/<int:fluxo_id>/toggle/', views.api_toggle_fluxo, name='api_toggle_fluxo'),
    path('api/fluxos/<int:fluxo_id>/simular/', views.simular_fluxo_api, name='simular_fluxo'),
    path('api/fluxos/<int:fluxo_id>/atendimentos/', views.api_atendimentos_fluxo, name='api_atendimentos_fluxo'),
    path('api/atendimentos/<int:atendimento_id>/logs/', views.api_logs_atendimento, name='api_logs_atendimento'),
    path('api/fluxos/<int:fluxo_id>/recontato/', views.salvar_recontato_api, name='salvar_recontato'),
    path('configuracoes/questoes/', views.questoes_fluxo_view, name='questoes_fluxo'),
    path('configuracoes/questoes/<int:fluxo_id>/', views.questoes_fluxo_view, name='questoes_fluxo_por_id'),

    # APIs de gerenciamento de questoes
    path('api/configuracoes/questoes/', views.api_questoes_fluxo_gerencia, name='api_questoes_fluxo_gerencia'),
    path('api/configuracoes/questoes/duplicar/', views.api_duplicar_questao_fluxo, name='api_duplicar_questao_fluxo'),
]
