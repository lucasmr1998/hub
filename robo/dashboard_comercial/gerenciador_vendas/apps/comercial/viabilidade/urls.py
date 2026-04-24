from django.urls import path
from . import views

app_name = 'comercial_viabilidade'

urlpatterns = [
    path('api/viabilidade/', views.api_viabilidade, name='api_viabilidade'),

    # Gestao server-side
    path('viabilidade/cidades/', views.cidades_lista, name='cidades_lista'),
    path('viabilidade/cidades/salvar/', views.cidade_salvar, name='cidade_salvar'),
    path('viabilidade/cidades/<int:pk>/toggle/', views.cidade_toggle, name='cidade_toggle'),
    path('viabilidade/cidades/<int:pk>/excluir/', views.cidade_excluir, name='cidade_excluir'),
]
