from django.urls import path
from . import views

app_name = 'crm'

urlpatterns = [
    # Pipeline / Kanban
    path('', views.pipeline_view, name='pipeline'),
    path('pipeline/', views.pipeline_view, name='pipeline_view'),
    path('pipeline/dados/', views.api_pipeline_dados, name='api_pipeline_dados'),
    path('pipeline/mover/', views.api_mover_oportunidade, name='api_mover_oportunidade'),

    # Mensagens de WhatsApp por pipeline
    path('mensagens/', views.mensagens_view, name='mensagens'),
    path('mensagens/salvar/', views.api_mensagem_salvar, name='api_mensagem_salvar'),
    path('mensagens/robo/', views.mensagens_robo_view, name='mensagens_robo'),
    path('mensagens/robo/salvar/', views.api_mensagem_robo_salvar, name='api_mensagem_robo_salvar'),

    # Perfis de Acesso (RBAC)
    path('perfis/', views.perfis_view, name='perfis'),
    path('perfis/salvar/', views.api_perfil_salvar, name='api_perfil_salvar'),
    path('perfis/usuarios/', views.api_perfil_usuarios, name='api_perfil_usuarios'),
    path('perfis/sincronizar-portal/', views.api_usuarios_sincronizar, name='api_usuarios_sincronizar'),

    # Gestão de usuários (portal TecHub + perfis)
    path('usuarios/', views.usuarios_view, name='usuarios'),
    path('usuarios/perfil/', views.api_usuario_perfil, name='api_usuario_perfil'),

    # Pipeline de Indicações (operado por pessoas)
    path('indicacoes/criar/', views.api_indicacao_criar, name='api_indicacao_criar'),
    path('indicacoes/lead-editar/', views.api_lead_editar, name='api_lead_editar'),
    path('indicacoes/converter/', views.api_indicacao_converter, name='api_indicacao_converter'),
    path('indicacoes/contrato-status/', views.api_indicacao_contrato_status, name='api_indicacao_contrato_status'),
    path('indicacoes/agendar/', views.api_indicacao_agendar, name='api_indicacao_agendar'),

    # Pipeline Wifeed (leads do portal WiFi; entrada via poller). lead-editar é
    # compartilhado com a Indicação (api_lead_editar, genérico).
    path('wifeed/criar/', views.api_wifeed_criar, name='api_wifeed_criar'),
    path('wifeed/converter/', views.api_wifeed_converter, name='api_wifeed_converter'),
    path('wifeed/contrato-status/', views.api_wifeed_contrato_status, name='api_wifeed_contrato_status'),
    path('wifeed/agendar/', views.api_wifeed_agendar, name='api_wifeed_agendar'),
    # Painel de fontes (locais/campanhas que trazem leads)
    path('wifeed/fontes/', views.wifeed_fontes_view, name='wifeed_fontes'),
    path('wifeed/fontes/sincronizar/', views.api_wifeed_fontes_sincronizar, name='api_wifeed_fontes_sincronizar'),
    path('wifeed/fontes/salvar/', views.api_wifeed_fontes_salvar, name='api_wifeed_fontes_salvar'),

    # Oportunidades
    path('oportunidades/', views.oportunidades_lista, name='oportunidades_lista'),
    path('oportunidades/<int:pk>/', views.oportunidade_detalhe, name='oportunidade_detalhe'),
    path('oportunidades/<int:pk>/atribuir/', views.api_atribuir_responsavel, name='api_atribuir_responsavel'),
    path('oportunidades/<int:pk>/notas/', views.api_notas_oportunidade, name='api_notas_oportunidade'),
    path('oportunidades/<int:pk>/tarefas/', views.api_tarefas_oportunidade, name='api_tarefas_oportunidade'),

    # Tarefas
    path('tarefas/', views.tarefas_lista, name='tarefas_lista'),
    path('tarefas/criar/', views.api_tarefa_criar, name='api_tarefa_criar'),
    path('tarefas/<int:pk>/concluir/', views.api_tarefa_concluir, name='api_tarefa_concluir'),

    # Notas
    path('notas/criar/', views.api_nota_criar, name='api_nota_criar'),
    path('notas/<int:pk>/fixar/', views.api_nota_fixar, name='api_nota_fixar'),
    path('notas/<int:pk>/deletar/', views.api_nota_deletar, name='api_nota_deletar'),

    # Desempenho e Metas
    path('desempenho/', views.desempenho_view, name='desempenho'),
    path('desempenho/dados/', views.api_desempenho_dados, name='api_desempenho_dados'),
    path('metas/', views.metas_view, name='metas'),
    path('metas/criar/', views.api_meta_criar, name='api_meta_criar'),

    # Retenção
    path('retencao/', views.retencao_view, name='retencao'),
    path('retencao/scanner/', views.api_scanner_retencao, name='api_scanner_retencao'),
    path('retencao/alertas/<int:pk>/tratar/', views.api_tratar_alerta, name='api_tratar_alerta'),
    path('retencao/alertas/<int:pk>/resolver/', views.api_resolver_alerta, name='api_resolver_alerta'),

    # Segmentos
    path('segmentos/', views.segmentos_lista, name='segmentos_lista'),
    path('segmentos/salvar/', views.api_segmento_salvar, name='api_segmento_salvar'),
    path('segmentos/<int:pk>/', views.segmento_detalhe, name='segmento_detalhe'),
    path('segmentos/<int:pk>/buscar-leads/', views.api_segmento_buscar_leads, name='api_segmento_buscar_leads'),
    path('segmentos/<int:pk>/adicionar-lead/', views.api_segmento_adicionar_lead, name='api_segmento_adicionar_lead'),
    path('segmentos/<int:pk>/remover-membro/', views.api_segmento_remover_membro, name='api_segmento_remover_membro'),
    path('segmentos/<int:pk>/disparar-campanha/', views.api_segmento_disparar_campanha, name='api_segmento_disparar_campanha'),

    # Metas
    path('metas/salvar/', views.api_meta_salvar, name='api_meta_salvar'),
    path('metas/<int:pk>/excluir/', views.api_meta_excluir, name='api_meta_excluir'),

    # Configurações
    path('configuracoes/', views.configuracoes_crm, name='configuracoes'),
    path('configuracoes/salvar/', views.api_salvar_config, name='api_salvar_config'),
    path('configuracoes/estagios/reordenar/', views.api_reordenar_estagios, name='api_reordenar_estagios'),
    path('configuracoes/estagios/criar/', views.api_criar_estagio, name='api_criar_estagio'),
    path('configuracoes/estagios/<int:pk>/', views.api_estagio_detalhe, name='api_estagio_detalhe'),
    path('configuracoes/estagios/<int:pk>/excluir/', views.api_excluir_estagio, name='api_excluir_estagio'),
    path('configuracoes/equipes/criar/', views.api_criar_equipe, name='api_criar_equipe'),

    # Regras de Pipeline
    path('configuracoes/estagios/<int:estagio_pk>/regras/', views.api_regras_estagio, name='api_regras_estagio'),
    path('configuracoes/regras/salvar/', views.api_regra_salvar, name='api_regra_salvar'),
    path('configuracoes/regras/<int:pk>/excluir/', views.api_regra_excluir, name='api_regra_excluir'),
    path('configuracoes/regras/opcoes/', views.api_regras_opcoes, name='api_regras_opcoes'),

    # Documentação
    path('documentacao/', views.documentacao_crm, name='documentacao_crm'),

    # Webhooks inbound
    path('webhook/hubsoft/contrato/', views.webhook_hubsoft_contrato, name='webhook_hubsoft_contrato'),
]
