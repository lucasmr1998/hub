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
    path('oportunidades/criar/', views.api_criar_oportunidade, name='api_criar_oportunidade'),
    path('oportunidades/', views.oportunidades_lista, name='oportunidades_lista'),
    path('oportunidades/<int:pk>/', views.oportunidade_detalhe, name='oportunidade_detalhe'),
    path('oportunidades/<int:pk>/atribuir/', views.api_atribuir_responsavel, name='api_atribuir_responsavel'),
    path('oportunidades/<int:pk>/editar/', views.api_editar_oportunidade, name='api_editar_oportunidade'),
    path('oportunidades/<int:pk>/excluir/', views.api_excluir_oportunidade, name='api_excluir_oportunidade'),
    path('oportunidades/<int:pk>/notas/', views.api_notas_oportunidade, name='api_notas_oportunidade'),
    path('oportunidades/<int:pk>/tarefas/', views.api_tarefas_oportunidade, name='api_tarefas_oportunidade'),

    # Relatórios
    path('relatorios/win-loss/', views.relatorio_win_loss, name='relatorio_win_loss'),

    # AI suggested next action
    path('oportunidades/<int:pk>/sugestao/aplicar/', views.api_sugestao_aplicar, name='api_sugestao_aplicar'),
    path('oportunidades/<int:pk>/cadastro-completo/', views.api_cadastro_completo_oportunidade, name='api_cadastro_completo_oportunidade'),
    path('oportunidades/<int:pk>/sugestao/rejeitar/', views.api_sugestao_rejeitar, name='api_sugestao_rejeitar'),

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
    # Retenção movida pra apps.cs.retencao em 05/05/2026.
    # URLs antigas redirecionam pra /cs/retencao/ via gerenciador_vendas/urls.py.

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

    # Automações do Pipeline
    path('automacoes-pipeline/', views.automacoes_pipeline_view, name='automacoes_pipeline'),
    path('automacoes-pipeline/nova/', views.regra_pipeline_criar, name='regra_pipeline_criar'),
    path('automacoes-pipeline/<int:pk>/editar/', views.regra_pipeline_editar, name='regra_pipeline_editar'),
    path('automacoes-pipeline/<int:pk>/excluir/', views.regra_pipeline_excluir, name='regra_pipeline_excluir'),
    path('automacoes-pipeline/<int:pk>/toggle/', views.regra_pipeline_toggle, name='regra_pipeline_toggle'),
    path('automacoes-pipeline/<int:pk>/duplicar/', views.regra_pipeline_duplicar, name='regra_pipeline_duplicar'),
    path('automacoes-pipeline/<int:pk>/preview/', views.regra_pipeline_preview, name='regra_pipeline_preview'),
    path('automacoes-pipeline/<int:pk>/historico/', views.regra_pipeline_historico, name='regra_pipeline_historico'),

    # Motivos de Perda — tela dedicada (T7)
    path('motivos-perda/', views.motivos_perda_lista, name='motivos_perda_lista'),

    # Configurações
    path('configuracoes/', views.configuracoes_crm, name='configuracoes'),
    path('configuracoes/salvar/', views.api_salvar_config, name='api_salvar_config'),
    path('configuracoes/estagios/reordenar/', views.api_reordenar_estagios, name='api_reordenar_estagios'),
    path('configuracoes/estagios/criar/', views.api_criar_estagio, name='api_criar_estagio'),
    path('configuracoes/estagios/<int:pk>/', views.api_estagio_detalhe, name='api_estagio_detalhe'),
    path('configuracoes/estagios/<int:pk>/campos-obrigatorios/', views.api_estagio_campos_obrigatorios, name='api_estagio_campos_obrigatorios'),
    path('configuracoes/estagios/<int:pk>/excluir/', views.api_excluir_estagio, name='api_excluir_estagio'),
    path('configuracoes/equipes/criar/', views.api_criar_equipe, name='api_criar_equipe'),
    path('equipes/', views.equipes_view, name='equipes'),

    # Produtos e Serviços
    path('produtos/', views.produtos_lista, name='produtos'),
    path('produtos/salvar/', views.api_produto_salvar, name='api_produto_salvar'),
    path('produtos/<int:pk>/excluir/', views.api_produto_excluir, name='api_produto_excluir'),
    path('api/produtos/', views.api_produtos_listar, name='api_produtos_listar'),

    # Opções de Vencimento
    path('vencimentos/salvar/', views.api_vencimento_salvar, name='api_vencimento_salvar'),
    path('vencimentos/<int:pk>/excluir/', views.api_vencimento_excluir, name='api_vencimento_excluir'),
    path('api/vencimentos/', views.api_vencimentos_listar, name='api_vencimentos_listar'),

    # Itens da Oportunidade
    path('oportunidades/<int:pk>/itens/', views.api_itens_oportunidade, name='api_itens_oportunidade'),
    path('itens/<int:pk>/remover/', views.api_item_oportunidade_remover, name='api_item_remover'),

    # Documentos da Oportunidade (upload manual + aprovacao inline)
    path('oportunidades/<int:pk>/documentos/', views.api_oportunidade_adicionar_documento, name='api_oportunidade_adicionar_documento'),
    path('documentos/<int:pk>/aprovar/', views.api_documento_aprovar, name='api_documento_aprovar'),
    path('documentos/<int:pk>/rejeitar/', views.api_documento_rejeitar, name='api_documento_rejeitar'),
    path('documentos/<int:pk>/remover/', views.api_documento_remover, name='api_documento_remover'),
    path('documentos/<int:pk>/visualizar/', views.api_documento_visualizar, name='api_documento_visualizar'),

    # Webhooks inbound
    path('webhook/hubsoft/contrato/', views.webhook_hubsoft_contrato, name='webhook_hubsoft_contrato'),
]
