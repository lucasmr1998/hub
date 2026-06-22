from django.urls import path

from . import views

app_name = 'automacao'

urlpatterns = [
    path('editor/', views.editor_page, name='editor'),
    path('execucoes/', views.execucoes_page, name='execucoes'),
    path('api/nodes/', views.nodes_catalogo_api, name='nodes_catalogo'),
    path('api/execucoes/', views.execucoes_api, name='execucoes_api'),
    path('api/opcoes/<str:fonte>/', views.opcoes_api, name='opcoes'),
    path('api/eventos/', views.eventos_api, name='eventos'),
    path('api/testar-fluxo/', views.testar_fluxo_api, name='testar_fluxo'),
    path('api/fluxos/', views.fluxos_api, name='fluxos'),
    path('api/fluxos/<int:pk>/', views.fluxo_api, name='fluxo'),
    path('api/fluxos/<int:pk>/webhook/', views.fluxo_webhook_api, name='fluxo_webhook'),
    path('webhook/<str:token>/', views.webhook_receber, name='webhook_receber'),
]
