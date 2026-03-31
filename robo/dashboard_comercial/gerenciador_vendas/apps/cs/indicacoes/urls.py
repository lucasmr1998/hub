from django.urls import path

app_name = 'indicacoes'

from . import views

urlpatterns = [
    path('dashboard/indicacoes/', views.dashboard_indicacoes_home, name='dashboard_indicacoes_home'),
    path('dashboard/indicacoes/lista/', views.dashboard_indicacoes, name='dashboard_indicacoes'),
    path('dashboard/indicacoes/membros/', views.dashboard_indicacoes_membros, name='dashboard_indicacoes_membros'),
    path('dashboard/indicacoes/visual/', views.dashboard_indicacoes_visual, name='dashboard_indicacoes_visual'),
    path('indicar/<str:codigo>/', views.pagina_indicacao, name='pagina_indicacao'),
]
