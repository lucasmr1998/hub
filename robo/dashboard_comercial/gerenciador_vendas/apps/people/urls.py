from django.urls import path

from apps.people.views import inicio, unidades

app_name = 'people'

urlpatterns = [
    path('', inicio.home, name='home'),

    # Unidades (lojas e filiais)
    path('unidades/', unidades.lista, name='unidades_lista'),
    path('unidades/nova/', unidades.criar, name='unidade_criar'),
    path('unidades/<int:pk>/', unidades.editar, name='unidade_editar'),
    path('unidades/<int:pk>/alternar-ativo/', unidades.alternar_ativo,
         name='unidade_alternar_ativo'),
]
