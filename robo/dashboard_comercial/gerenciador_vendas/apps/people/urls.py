from django.urls import path

from apps.people.views import (
    analises, board, campos, candidatos, cargos, colaboradores, configuracao,
    fluxo, links, pipeline, quadro, unidades, vagas,
)

app_name = 'people'

urlpatterns = [
    path('', board.board, name='board'),
    path('api/colaborador/<int:pk>/mover/', board.api_mover, name='api_mover'),

    # Colaboradores
    path('colaboradores/novo/', colaboradores.criar, name='colaborador_criar'),
    path('colaboradores/<int:pk>/', colaboradores.detalhe, name='colaborador_detalhe'),
    path('colaboradores/<int:pk>/revisar/', colaboradores.revisar, name='colaborador_revisar'),

    # Links publicos de auto cadastro. Uma unidade pode ter varios.
    path('links/', links.lista, name='links_lista'),
    path('links/novo/', links.criar, name='link_criar'),
    path('links/<int:pk>/rotacionar/', links.rotacionar, name='link_rotacionar'),
    path('links/<int:pk>/alternar-ativo/', links.alternar_ativo, name='link_alternar_ativo'),
    path('links/<int:pk>/qr.svg', links.qr, name='link_qr'),

    # Analises
    path('analises/', analises.painel, name='analises'),

    # Configuracoes: fluxo, formularios e defaults do tenant
    path('config/', configuracao.home, name='config_home'),
    path('config/fluxo/', configuracao.fluxo, name='config_fluxo'),
    path('config/fluxo/<str:situacao>/', configuracao.fluxo_etapa, name='config_fluxo_etapa'),
    path('config/fluxo/<str:situacao>/mensagem/', configuracao.mensagem_etapa,
         name='config_mensagem_etapa'),
    path('config/formularios/', configuracao.templates, name='config_templates'),
    path('config/formularios/novo/', configuracao.template_editar, name='config_template_criar'),
    path('config/formularios/<int:pk>/', configuracao.template_editar,
         name='config_template_editar'),
    path('config/geral/', configuracao.geral, name='config_geral'),

    # Recrutamento: board do pipeline
    path('candidatos/', pipeline.board, name='pipeline_board'),
    path('candidatos/<int:pk>/mover/', pipeline.api_mover, name='pipeline_mover'),
    path('candidatos/<int:pk>/saida/', pipeline.api_dar_saida,
         name='pipeline_saida'),
    path('candidatos/lote/', pipeline.api_lote, name='pipeline_lote'),
    path('candidatos/<int:pk>/admitir/', candidatos.admitir,
         name='candidato_admitir'),
    path('candidatos/<int:pk>/analisar/', candidatos.analisar,
         name='candidato_analisar'),
    path('candidatos/<int:pk>/etapa/<int:etapa_pk>/anotar/',
         candidatos.anotar_etapa, name='candidato_anotar_etapa'),
    path('candidatos/<int:pk>/', candidatos.detalhe, name='candidato_detalhe'),
    path('candidatos/<int:pk>/curriculo/', candidatos.curriculo,
         name='candidato_curriculo'),

    # Recrutamento: configuracao do fluxo
    path('fluxo/', fluxo.configurar, name='fluxo_config'),
    path('fluxo/etapa/salvar/', fluxo.etapa_salvar, name='fluxo_etapa_salvar'),
    path('fluxo/etapa/<int:pk>/alternar/', fluxo.etapa_alternar,
         name='fluxo_etapa_alternar'),
    path('fluxo/etapa/<int:pk>/mover/', fluxo.etapa_mover, name='fluxo_etapa_mover'),
    path('fluxo/etapa/<int:pk>/remover/', fluxo.etapa_remover,
         name='fluxo_etapa_remover'),
    path('fluxo/resetar/', fluxo.resetar_padrao, name='fluxo_resetar'),
    path('fluxo/mensagem/', fluxo.mensagem_salvar, name='fluxo_mensagem_salvar'),

    # Recrutamento: campos que o tenant inventa pra candidatura
    path('campos/', campos.configurar, name='campos_config'),
    path('campos/salvar/', campos.salvar, name='campo_salvar'),
    path('campos/<int:pk>/alternar/', campos.alternar, name='campo_alternar'),
    path('campos/<int:pk>/mover/', campos.mover, name='campo_mover'),
    path('campos/<int:pk>/remover/', campos.remover, name='campo_remover'),

    # Recrutamento: captacao continua (link sem vaga, alimenta o banco)
    path('captacao/', vagas.banco_talentos_links, name='banco_talentos_links'),
    path('captacao/novo/', vagas.banco_talentos_link_criar,
         name='banco_talentos_link_criar'),
    path('captacao/<int:link_pk>/qr.svg', vagas.banco_talentos_link_qr,
         name='banco_talentos_link_qr'),
    path('captacao/<int:link_pk>/alternar/', vagas.banco_talentos_link_alternar,
         name='banco_talentos_link_alternar'),

    # Recrutamento: quadro por unidade
    path('quadro/', quadro.lista, name='quadro_lista'),
    path('quadro/salvar/', quadro.salvar, name='quadro_salvar'),
    path('quadro/<int:pk>/remover/', quadro.remover, name='quadro_remover'),

    # Recrutamento: requisicao de vaga com aprovacao (gap 16). Quem solicita
    # usa `people.solicitar_vaga`; quem decide usa `people.gerir_vagas`.
    path('vagas/solicitar/', vagas.solicitar, name='vaga_solicitar'),
    path('vagas/<int:pk>/reenviar/', vagas.reenviar, name='vaga_reenviar'),
    path('vagas/<int:pk>/aprovar/', vagas.aprovar, name='vaga_aprovar'),
    path('vagas/<int:pk>/rejeitar/', vagas.rejeitar, name='vaga_rejeitar'),

    # Recrutamento: vagas
    path('vagas/', vagas.lista, name='vagas_lista'),
    path('vagas/nova/', vagas.criar, name='vaga_criar'),
    path('vagas/<int:pk>/', vagas.editar, name='vaga_editar'),
    path('vagas/<int:pk>/status/', vagas.mudar_status, name='vaga_mudar_status'),
    path('vagas/<int:pk>/campos/', vagas.campos_salvar, name='vaga_campos_salvar'),
    path('vagas/<int:pk>/requisitos/', vagas.requisito_criar,
         name='vaga_requisito_criar'),
    path('vagas/<int:pk>/requisitos/<int:requisito_pk>/remover/',
         vagas.requisito_remover, name='vaga_requisito_remover'),
    path('vagas/<int:pk>/links/', vagas.link_criar, name='vaga_link_criar'),
    path('vagas/<int:pk>/links/<int:link_pk>/desativar/', vagas.link_desativar,
         name='vaga_link_desativar'),
    path('vagas/<int:pk>/links/<int:link_pk>/qr.svg', vagas.link_qr,
         name='vaga_link_qr'),
    path('vagas/<int:pk>/links/<int:link_pk>/remover/', vagas.link_remover,
         name='vaga_link_remover'),

    # Cargos
    path('cargos/', cargos.lista, name='cargos_lista'),
    path('cargos/novo/', cargos.criar, name='cargo_criar'),
    path('cargos/<int:pk>/', cargos.editar, name='cargo_editar'),
    path('cargos/<int:pk>/alternar-ativo/', cargos.alternar_ativo,
         name='cargo_alternar_ativo'),

    # Unidades (lojas e filiais)
    path('unidades/', unidades.lista, name='unidades_lista'),
    path('unidades/nova/', unidades.criar, name='unidade_criar'),
    path('unidades/<int:pk>/', unidades.editar, name='unidade_editar'),
    path('unidades/<int:pk>/alternar-ativo/', unidades.alternar_ativo,
         name='unidade_alternar_ativo'),
]
