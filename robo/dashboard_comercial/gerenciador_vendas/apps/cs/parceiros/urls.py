from django.urls import path

app_name = 'parceiros'

from apps.cs.parceiros import views
from apps.cs.parceiros import views_painel

urlpatterns = [
    path('dashboard/parceiros/', views.dashboard_parceiros_home, name='dashboard_parceiros_home'),
    path('dashboard/parceiros/lista/', views.dashboard_parceiros, name='dashboard_parceiros'),
    path('dashboard/cupons/', views.dashboard_cupons, name='dashboard_cupons'),
    path('dashboard/cupons/resgates/', views.dashboard_cupons_resgates, name='dashboard_cupons_resgates'),
    path('dashboard/cupons/<int:cupom_id>/', views.dashboard_cupom_detalhe, name='dashboard_cupom_detalhe'),
    path('cupom/validar/', views.validar_cupom, name='validar_cupom'),

    # Painel do Parceiro
    path('parceiro/login/', views_painel.painel_login, name='painel_login'),
    path('parceiro/logout/', views_painel.painel_logout, name='painel_logout'),
    path('parceiro/', views_painel.painel_home, name='painel_home'),
    path('parceiro/cupons/', views_painel.painel_cupons, name='painel_cupons'),
    path('parceiro/resgates/', views_painel.painel_resgates, name='painel_resgates'),
    path('parceiro/validar/', views_painel.painel_validar, name='painel_validar'),
]
