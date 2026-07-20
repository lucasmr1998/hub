from django.urls import path

from apps.people.views import board, cargos, colaboradores, links, unidades

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
