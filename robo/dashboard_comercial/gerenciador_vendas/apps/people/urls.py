from django.urls import path

from apps.people.views import board, colaboradores, links, unidades

app_name = 'people'

urlpatterns = [
    path('', board.board, name='board'),
    path('api/colaborador/<int:pk>/mover/', board.api_mover, name='api_mover'),

    # Colaboradores
    path('colaboradores/novo/', colaboradores.criar, name='colaborador_criar'),
    path('colaboradores/<int:pk>/', colaboradores.detalhe, name='colaborador_detalhe'),
    path('colaboradores/<int:pk>/revisar/', colaboradores.revisar, name='colaborador_revisar'),

    # Links publicos de auto cadastro, um por unidade
    path('links/', links.lista, name='links_lista'),
    path('links/<int:unidade_pk>/gerar/', links.gerar, name='link_gerar'),
    path('links/<int:unidade_pk>/rotacionar/', links.rotacionar, name='link_rotacionar'),
    path('links/<int:unidade_pk>/desativar/', links.desativar, name='link_desativar'),

    # Unidades (lojas e filiais)
    path('unidades/', unidades.lista, name='unidades_lista'),
    path('unidades/nova/', unidades.criar, name='unidade_criar'),
    path('unidades/<int:pk>/', unidades.editar, name='unidade_editar'),
    path('unidades/<int:pk>/alternar-ativo/', unidades.alternar_ativo,
         name='unidade_alternar_ativo'),
]
