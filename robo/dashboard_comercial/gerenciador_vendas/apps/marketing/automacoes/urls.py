from django.urls import path
from . import views

app_name = 'marketing_automacoes'

urlpatterns = [
    path('', views.lista_automacoes, name='lista'),
    path('criar/', views.criar_automacao, name='criar'),
    path('dashboard/', views.dashboard_automacoes, name='dashboard'),
    path('<int:pk>/editar/', views.editar_automacao, name='editar'),
    path('<int:pk>/fluxo/', views.editor_fluxo, name='editor_fluxo'),
    path('<int:pk>/salvar-fluxo/', views.salvar_fluxo, name='salvar_fluxo'),
    path('<int:pk>/toggle/', views.toggle_automacao, name='toggle'),
    path('<int:pk>/excluir/', views.excluir_automacao, name='excluir'),
    path('<int:pk>/historico/', views.historico_automacao, name='historico'),
    path('api/lead/<int:lead_pk>/timeline/', views.api_lead_timeline, name='api_lead_timeline'),
]
