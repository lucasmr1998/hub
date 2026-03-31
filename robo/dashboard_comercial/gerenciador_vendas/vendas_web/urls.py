from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import views_api_atendimento
from apps.dashboard import views as dashboard_views

app_name = 'vendas_web'

urlpatterns = [
    # Autenticação
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard principal (migrado para apps.dashboard)
    path('dashboard/', dashboard_views.dashboard_view, name='dashboard'),
    path('dashboard1/', dashboard_views.dashboard1, name='dashboard1'),

    # APIs para dados do dashboard (migrado para apps.dashboard)
    path('api/dashboard/data/', dashboard_views.dashboard_data, name='dashboard_data'),
    path('api/dashboard/charts/', dashboard_views.dashboard_charts_data, name='dashboard_charts'),
    path('api/dashboard/tables/', dashboard_views.dashboard_tables_data, name='dashboard_tables'),
    path('api/dashboard/leads/', dashboard_views.dashboard_leads_data, name='dashboard_leads'),
    path('api/dashboard/prospectos/', dashboard_views.dashboard_prospectos_data, name='dashboard_prospectos'),
    path('api/dashboard/historico/', dashboard_views.dashboard_historico_data, name='dashboard_historico'),
    path('api/dashboard/contatos/realtime/', dashboard_views.dashboard_contatos_realtime, name='dashboard_contatos_realtime'),
    path('api/dashboard/contato/<str:telefone>/historico/', dashboard_views.dashboard_contato_historico, name='dashboard_contato_historico'),
    path('api/dashboard/ultimas-conversoes/', dashboard_views.dashboard_ultimas_conversoes, name='dashboard_ultimas_conversoes'),

    # APIs para validação de vendas
    path('api/vendas/aprovar/', views.aprovar_venda_api, name='aprovar_venda'),
    path('api/vendas/rejeitar/', views.rejeitar_venda_api, name='rejeitar_venda'),

    # API para histórico de contatos
    path('api/historico-contatos/', views.historico_contatos_api, name='historico_contatos'),

    # API para insights do funil de vendas (migrado para apps.dashboard)
    path('api/dashboard/funil/insights/', dashboard_views.dashboard_funil_insights, name='dashboard_funil_insights'),

    # Rotas adicionais para navegação
    path('leads/', views.leads_view, name='leads'),
    path('leads/<int:lead_id>/conversa/', views.visualizar_conversa_lead, name='visualizar_conversa_lead'),
    path('leads/<int:lead_id>/conversa/pdf/', views.visualizar_conversa_pdf, name='visualizar_conversa_pdf'),
    path('vendas/', dashboard_views.vendas_view, name='vendas'),
    path('relatorios/', dashboard_views.relatorios_view, name='relatorios'),
    path('relatorios/leads/', dashboard_views.relatorio_leads_view, name='relatorio_leads'),
    path('relatorios/clientes/', dashboard_views.relatorio_clientes_view, name='relatorio_clientes'),
    path('relatorios/atendimentos/', dashboard_views.relatorio_atendimentos_view, name='relatorio_atendimentos'),
    path('analise/atendimentos/', dashboard_views.analise_atendimentos_view, name='analise_atendimentos'),
    path('relatorio/conversoes/', dashboard_views.relatorio_conversoes_view, name='relatorio_conversoes'),
    path('ajuda/', dashboard_views.ajuda_view, name='ajuda'),
    path('documentacao/', dashboard_views.documentacao_view, name='documentacao'),
    
    # Rotas para cadastro de clientes
    path('cadastro/', views.cadastro_cliente_view, name='cadastro_cliente'),
    path('api/cadastro/cliente/', views.api_cadastro_cliente, name='api_cadastro_cliente'),
    path('api/planos/internet/', views.api_planos_internet, name='api_planos_internet'),
    path('api/vencimentos/', views.api_vencimentos, name='api_vencimentos'),
    path('api/cep/<str:cep>/', views.api_consulta_cep, name='api_consulta_cep'),

    # APIS simples de registro/update
    path('api/leads/registrar/', views.registrar_lead_api, name='registrar_lead'),
    path('api/leads/atualizar/', views.atualizar_lead_api, name='atualizar_lead'),
    path('api/leads/imagens/registrar/', views.registrar_imagem_lead_api, name='registrar_imagem_lead'),
    path('api/leads/imagens/listar/', views.listar_imagens_lead_api, name='listar_imagens_lead'),
    path('api/leads/imagens/deletar/', views.deletar_imagem_lead_api, name='deletar_imagem_lead'),
    path('api/leads/imagens/por-cliente/', views.imagens_por_cliente_api, name='imagens_por_cliente'),
    path('api/leads/imagens/validar/', views.validar_imagem_api, name='validar_imagem'),
    path('api/prospectos/registrar/', views.registrar_prospecto_api, name='registrar_prospecto'),
    path('api/prospectos/atualizar/', views.atualizar_prospecto_api, name='atualizar_prospecto'),
    path('api/historicos/registrar/', views.registrar_historico_api, name='registrar_historico'),
    path('api/historicos/atualizar/', views.atualizar_historico_api, name='atualizar_historico'),
    path('api/verificar-relacionamentos/', views.verificar_relacionamentos_api, name='verificar_relacionamentos'),

    # APIs de consulta (GET)
    path('api/consultar/leads/', views.consultar_leads_api, name='consultar_leads_api'),
    path('api/consultar/historicos/', views.consultar_historicos_api, name='consultar_historicos_api'),
    
    # ========================================================================
    # APIS COMPLETAS DE ATENDIMENTO - CRUD
    # ========================================================================
    
    # APIs de Fluxos de Atendimento
    path('api/fluxos/', views_api_atendimento.consultar_fluxos_api, name='api_fluxos_consultar'),
    path('api/fluxos/criar/', views_api_atendimento.criar_fluxo_api, name='api_fluxos_criar'),
    path('api/fluxos/<int:fluxo_id>/atualizar/', views_api_atendimento.atualizar_fluxo_api, name='api_fluxos_atualizar'),
    path('api/fluxos/<int:fluxo_id>/deletar/', views_api_atendimento.deletar_fluxo_api, name='api_fluxos_deletar'),
    
    # APIs de Questões de Fluxo
    path('api/questoes/', views_api_atendimento.consultar_questoes_api, name='api_questoes_consultar'),
    path('api/questoes/criar/', views_api_atendimento.criar_questao_api, name='api_questoes_criar'),
    path('api/questoes/<int:questao_id>/atualizar/', views_api_atendimento.atualizar_questao_api, name='api_questoes_atualizar'),
    path('api/questoes/<int:questao_id>/deletar/', views_api_atendimento.deletar_questao_api, name='api_questoes_deletar'),
    
    # APIs de Atendimentos de Fluxo
    path('api/atendimentos/', views_api_atendimento.consultar_atendimentos_api, name='api_atendimentos_consultar'),
    path('api/atendimentos/criar/', views_api_atendimento.criar_atendimento_api, name='api_atendimentos_criar'),
    path('api/atendimentos/<int:atendimento_id>/atualizar/', views_api_atendimento.atualizar_atendimento_api, name='api_atendimentos_atualizar'),
    path('api/atendimentos/<int:atendimento_id>/responder/', views_api_atendimento.responder_questao_api, name='api_atendimentos_responder'),
    path('api/atendimentos/<int:atendimento_id>/finalizar/', views_api_atendimento.finalizar_atendimento_api, name='api_atendimentos_finalizar'),
    
    # APIs de Respostas de Questões
    path('api/respostas/', views_api_atendimento.consultar_respostas_api, name='api_respostas_consultar'),
    
    # APIs de Estatísticas
    path('api/atendimento/estatisticas/', views_api_atendimento.estatisticas_atendimento_api, name='api_atendimento_estatisticas'),
    
    # ========================================================================
    # APIS ESPECÍFICAS PARA INTEGRAÇÃO COM N8N
    # ========================================================================
    
    # APIs para gerenciamento de atendimento pelo N8N
    path('api/n8n/atendimento/iniciar/', views_api_atendimento.iniciar_atendimento_n8n, name='api_n8n_iniciar_atendimento'),
    path('api/n8n/atendimento/<int:atendimento_id>/consultar/', views_api_atendimento.consultar_atendimento_n8n, name='api_n8n_consultar_atendimento'),
    path('api/n8n/atendimento/<int:atendimento_id>/responder/', views_api_atendimento.responder_questao_n8n, name='api_n8n_responder_questao'),
    path('api/n8n/atendimento/<int:atendimento_id>/avancar/', views_api_atendimento.avancar_questao_n8n, name='api_n8n_avancar_questao'),
    path('api/n8n/atendimento/<int:atendimento_id>/finalizar/', views_api_atendimento.finalizar_atendimento_n8n, name='api_n8n_finalizar_atendimento'),
    
    # APIs para busca e consulta pelo N8N
    path('api/n8n/lead/buscar/', views_api_atendimento.buscar_lead_por_telefone_n8n, name='api_n8n_buscar_lead'),
    path('api/n8n/lead/criar/', views_api_atendimento.criar_lead_n8n, name='api_n8n_criar_lead'),
    path('api/n8n/fluxos/', views_api_atendimento.listar_fluxos_ativos_n8n, name='api_n8n_listar_fluxos'),
    path('api/n8n/fluxo/<int:fluxo_id>/questao/<int:indice_questao>/', views_api_atendimento.obter_questao_n8n, name='api_n8n_obter_questao'),
    
    # APIs para controle de atendimento pelo N8N
    path('api/n8n/atendimento/<int:atendimento_id>/pausar/', views_api_atendimento.pausar_atendimento_n8n, name='api_n8n_pausar_atendimento'),
    path('api/n8n/atendimento/<int:atendimento_id>/retomar/', views_api_atendimento.retomar_atendimento_n8n, name='api_n8n_retomar_atendimento'),
    
    # APIs específicas para fluxo inteligente
    path('api/n8n/atendimento/<int:atendimento_id>/tentativas/', views_api_atendimento.consultar_tentativas_resposta_n8n, name='api_n8n_consultar_tentativas'),
    path('api/n8n/fluxo/<int:fluxo_id>/questao/<int:indice_questao>/inteligente/', views_api_atendimento.obter_questao_inteligente_n8n, name='api_n8n_questao_inteligente'),
    path('api/n8n/atendimento/<int:atendimento_id>/estatisticas/inteligente/', views_api_atendimento.estatisticas_atendimento_inteligente_n8n, name='api_n8n_estatisticas_inteligente'),
    
    # Rotas compatíveis antigas (mantidas para compatibilidade)
    path('api/consultar/fluxos/', views_api_atendimento.consultar_fluxos_api, name='consultar_fluxos_api'),
    path('api/consultar/questoes/', views_api_atendimento.consultar_questoes_api, name='consultar_questoes_api'),
    path('api/consultar/atendimentos/', views_api_atendimento.consultar_atendimentos_api, name='consultar_atendimentos_api'),
    path('api/consultar/respostas/', views_api_atendimento.consultar_respostas_api, name='consultar_respostas_api'),

    # APIs de análise de atendimentos (migrado para apps.dashboard)
    path('api/analise/atendimentos/data/', dashboard_views.api_analise_atendimentos_data, name='api_analise_atendimentos_data'),
    path('api/analise/atendimentos/fluxos/', dashboard_views.api_analise_atendimentos_fluxos, name='api_analise_atendimentos_fluxos'),
    path('api/analise/atendimentos/detalhada/', dashboard_views.api_analise_detalhada_atendimentos, name='api_analise_detalhada_atendimentos'),
    path('api/jornada/cliente/', dashboard_views.api_jornada_cliente_completa, name='api_jornada_cliente_completa'),
    path('api/atendimento/tempo-real/', dashboard_views.api_atendimento_em_tempo_real, name='api_atendimento_em_tempo_real'),

    # Documentação da API (migrado para apps.dashboard)
    path('api/docs/', dashboard_views.api_swagger_view, name='api_swagger'),
    path('api/docs/markdown/', dashboard_views.api_documentation_view, name='api_documentation'),
    path('api/docs/n8n/', dashboard_views.n8n_guide_view, name='n8n_guide'),

    # ========================================================================
    # PÁGINAS DE CONFIGURAÇÃO E GERENCIAMENTO
    # ========================================================================
    
    # Página principal de configurações
    path('configuracoes/', views.configuracoes_view, name='configuracoes'),
    
    # Páginas de gerenciamento
    path('configuracoes/usuarios/', views.configuracoes_usuarios_view, name='configuracoes_usuarios'),
    path('configuracoes/notificacoes/', views.configuracoes_notificacoes_view, name='configuracoes_notificacoes'),
    path('configuracoes/notificacoes/tipo/<int:tipo_id>/', views.tipo_notificacao_detalhes_view, name='tipo_notificacao_detalhes'),
    path('configuracoes/cadastro/', views.configuracoes_cadastro_view, name='configuracoes_cadastro'),
    path('configuracoes/cadastro/save/', views.salvar_configuracoes_cadastro_view, name='salvar_configuracoes_cadastro'),
    path('configuracoes/recontato/', views.configuracoes_recontato_view, name='configuracoes_recontato'),
    path('configuracoes/fluxos/', views.fluxos_atendimento_view, name='fluxos_atendimento'),
    path('configuracoes/questoes/', views.questoes_fluxo_view, name='questoes_fluxo'),
    path('configuracoes/questoes/<int:fluxo_id>/', views.questoes_fluxo_view, name='questoes_fluxo_por_id'),
    path('configuracoes/planos/', views.planos_internet_view, name='planos_internet'),
    path('configuracoes/vencimentos/', views.opcoes_vencimento_view, name='opcoes_vencimento'),
    
    # Campanhas de Tráfego Pago
    path('configuracoes/campanhas/', views.campanhas_trafego_view, name='campanhas_trafego'),
    path('configuracoes/campanhas/deteccoes/', views.deteccoes_campanha_view, name='deteccoes_campanha'),
    
    # APIs de gerenciamento
    path('api/configuracoes/usuarios/', views.api_usuarios_criar, name='api_usuarios_criar'),
    path('api/configuracoes/usuarios/<int:user_id>/', views.api_usuarios_editar, name='api_usuarios_editar'),
    path('api/configuracoes/usuarios/<int:user_id>/deletar/', views.api_usuarios_deletar, name='api_usuarios_deletar'),
    
    # APIs de notificações
    path('api/notificacoes/enviar/', views.api_notificacao_enviar, name='api_notificacao_enviar'),
    path('api/notificacoes/listar/', views.api_notificacoes_listar, name='api_notificacoes_listar'),
    path('api/notificacoes/<int:notificacao_id>/', views.api_notificacao_detalhes, name='api_notificacao_detalhes'),
    path('api/notificacoes/preferencias/', views.api_notificacoes_preferencias, name='api_notificacoes_preferencias'),
    path('api/notificacoes/teste/', views.api_notificacoes_teste, name='api_notificacoes_teste'),
    path('api/notificacoes/estatisticas/', views.api_notificacoes_estatisticas, name='api_notificacoes_estatisticas'),
    path('api/templates-notificacoes/', views.api_templates_notificacoes, name='api_templates_notificacoes'),
    path('api/templates-notificacoes/<int:template_id>/', views.api_templates_notificacoes, name='api_templates_notificacoes_detail'),
    path('api/tipos-notificacao/', views.api_tipos_notificacao, name='api_tipos_notificacao'),
    path('api/tipos-notificacao/<int:tipo_id>/', views.api_tipos_notificacao, name='api_tipos_notificacao_detail'),
    path('api/canais-notificacao/', views.api_canais_notificacao, name='api_canais_notificacao'),
    path('api/canais-notificacao/<int:canal_id>/', views.api_canais_notificacao, name='api_canais_notificacao_detail'),
    
    # APIs de gerenciamento de preferências de usuários
    path('api/notificacoes/canais/', views.api_canais_notificacao, name='api_canais'),
    path('api/notificacoes/preferencias/criar/', views.api_preferencias_criar, name='api_preferencias_criar'),
    path('api/notificacoes/preferencias/editar/', views.api_preferencias_editar, name='api_preferencias_editar'),
    path('api/notificacoes/preferencias/<int:preferencia_id>/dados/', views.api_preferencias_dados, name='api_preferencias_dados'),
    path('api/notificacoes/preferencias/<int:preferencia_id>/pausar/', views.api_preferencias_pausar, name='api_preferencias_pausar'),
    path('api/notificacoes/preferencias/<int:preferencia_id>/ativar/', views.api_preferencias_ativar, name='api_preferencias_ativar'),
    path('api/notificacoes/preferencias/<int:preferencia_id>/', views.api_preferencias_remover, name='api_preferencias_remover'),
    
    # APIs de configuração do WhatsApp
    path('api/notificacoes/whatsapp/config/', views.api_whatsapp_config, name='api_whatsapp_config'),
    path('api/notificacoes/whatsapp/config/salvar/', views.api_whatsapp_config_salvar, name='api_whatsapp_config_salvar'),
    path('api/notificacoes/whatsapp/test/', views.api_whatsapp_test, name='api_whatsapp_test'),
    
    # API para alternar status de canais
    path('api/notificacoes/canais/<int:canal_id>/toggle/', views.api_canal_toggle, name='api_canal_toggle'),
    path('api/configuracoes/cadastro/', views.api_configuracoes_cadastro, name='api_configuracoes_cadastro'),
    path('api/configuracoes/planos/', views.api_planos_internet_gerencia, name='api_planos_internet_gerencia'),
    path('api/configuracoes/vencimentos/', views.api_opcoes_vencimento_gerencia, name='api_opcoes_vencimento_gerencia'),
    
    # APIs de Campanhas de Tráfego
    path('api/campanhas/', views.api_campanhas_trafego_gerencia, name='api_campanhas_trafego_gerencia'),
    path('api/campanhas/detectar/', views.api_detectar_campanha, name='api_detectar_campanha'),
    
    path('api/configuracoes/questoes/', views.api_questoes_fluxo_gerencia, name='api_questoes_fluxo_gerencia'),
    path('api/configuracoes/questoes/duplicar/', views.api_duplicar_questao_fluxo, name='api_duplicar_questao_fluxo'),

    # Viabilidade técnica
    path('api/viabilidade/', views.api_viabilidade, name='api_viabilidade'),
]