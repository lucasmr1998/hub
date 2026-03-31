from django.urls import path
from . import views

app_name = 'integracoes'

urlpatterns = [
    path('api/clientes/', views.api_clientes_hubsoft, name='api_clientes_hubsoft'),
    path(
        'api/lead/hubsoft-status/',
        views.api_lead_hubsoft_status,
        name='api_lead_hubsoft_status',
    ),
]
