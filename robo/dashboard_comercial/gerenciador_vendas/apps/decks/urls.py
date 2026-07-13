from django.urls import path

from . import views

app_name = 'decks'

urlpatterns = [
    # UI
    path('', views.lista_view, name='lista'),
    path('criar/', views.criar_view, name='criar'),
    path('<int:pk>/editar/', views.editor_view, name='editar'),
    path('<int:pk>/apresentar/', views.apresentar_view, name='apresentar'),
    path('<int:pk>/excluir/', views.excluir_view, name='excluir'),

    # APIs
    path('api/deck/salvar/', views.api_deck_salvar, name='api_deck_salvar'),
    path('api/deck/<int:pk>/slide/adicionar/', views.api_slide_adicionar, name='api_slide_adicionar'),
    path('api/deck/<int:pk>/slides/reordenar/', views.api_slides_reordenar, name='api_slides_reordenar'),
    path('api/deck/<int:pk>/congelar/', views.api_deck_congelar, name='api_deck_congelar'),
    path('api/slide/<int:pk>/excluir/', views.api_slide_excluir, name='api_slide_excluir'),
    path('api/slide/<int:pk>/bloco/salvar/', views.api_bloco_salvar, name='api_bloco_salvar'),
    path('api/slide/<int:pk>/layout/', views.api_slide_layout, name='api_slide_layout'),
    path('api/bloco/<int:pk>/excluir/', views.api_bloco_excluir, name='api_bloco_excluir'),
    path('api/bloco/<int:pk>/dados/', views.api_bloco_widget_dados, name='api_bloco_widget_dados'),
    path('api/widgets/disponiveis/', views.api_widgets_disponiveis, name='api_widgets_disponiveis'),
]
