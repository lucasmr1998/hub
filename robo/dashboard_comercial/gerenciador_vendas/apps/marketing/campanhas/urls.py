from django.urls import path
from . import views

app_name = 'marketing_campanhas'

urlpatterns = [
    # Paginas de campanhas de trafego pago
    path('configuracoes/campanhas/', views.campanhas_trafego_view, name='campanhas_trafego'),
    path('configuracoes/campanhas/deteccoes/', views.deteccoes_campanha_view, name='deteccoes_campanha'),

    # APIs de campanhas de trafego
    path('api/campanhas/', views.api_campanhas_trafego_gerencia, name='api_campanhas_trafego_gerencia'),
    path('api/campanhas/detectar/', views.api_detectar_campanha, name='api_detectar_campanha'),
]
