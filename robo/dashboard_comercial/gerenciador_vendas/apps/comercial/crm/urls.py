from django.urls import path
from . import views

app_name = 'crm'

urlpatterns = [
    # Pipeline / Kanban
    path('', views.pipeline_view, name='pipeline'),
    path('pipeline/', views.pipeline_view, name='pipeline_view'),
    path('pipeline/dados/', views.api_pipeline_dados, name='api_pipeline_dados'),
    path('pipeline/mover/', views.api_mover_oportunidade, name='api_mover_oportunidade'),

    # Oportunidades
    path('oportunidades/', views.oportunidades_lista, name='oportunidades_lista'),
    path('oportunidades/<int:pk>/', views.oportunidade_detalhe, name='oportunidade_detalhe'),
    path('oportunidades/<int:pk>/atribuir/', views.api_atribuir_responsavel, name='api_atribuir_responsavel'),
    path('oportunidades/<int:pk>/editar/', views.api_editar_oportunidade, name='api_editar_oportunidade'),
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
    path('equipes/', views.equipes_view, name='equipes'),

    # Webhooks inbound
    path('webhook/hubsoft/contrato/', views.webhook_hubsoft_contrato, name='webhook_hubsoft_contrato'),
]
