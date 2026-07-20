from django.urls import path

from apps.people.views import (
    analises, board, cargos, colaboradores, configuracao, links, unidades,
    vagas,
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

    # Recrutamento: vagas
    path('vagas/', vagas.lista, name='vagas_lista'),
    path('vagas/nova/', vagas.criar, name='vaga_criar'),
    path('vagas/<int:pk>/', vagas.editar, name='vaga_editar'),
    path('vagas/<int:pk>/status/', vagas.mudar_status, name='vaga_mudar_status'),
    path('vagas/<int:pk>/requisitos/', vagas.requisito_criar,
         name='vaga_requisito_criar'),
    path('vagas/<int:pk>/requisitos/<int:requisito_pk>/remover/',
         vagas.requisito_remover, name='vaga_requisito_remover'),

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
