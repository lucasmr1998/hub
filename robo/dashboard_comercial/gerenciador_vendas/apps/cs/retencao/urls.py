from django.urls import path
from . import views

app_name = 'retencao'

urlpatterns = [
    path('', views.retencao_view, name='retencao'),
    path('scanner/', views.api_scanner_retencao, name='api_scanner_retencao'),
    path('alertas/<int:pk>/tratar/', views.api_tratar_alerta, name='api_tratar_alerta'),
    path('alertas/<int:pk>/resolver/', views.api_resolver_alerta, name='api_resolver_alerta'),
]
