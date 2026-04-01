from django.urls import path
from . import views

app_name = 'suporte'

urlpatterns = [
    path('', views.dashboard_suporte, name='dashboard'),
    path('tickets/', views.ticket_lista, name='ticket_lista'),
    path('tickets/criar/', views.ticket_criar, name='ticket_criar'),
    path('tickets/<int:pk>/', views.ticket_detalhe, name='ticket_detalhe'),
]
