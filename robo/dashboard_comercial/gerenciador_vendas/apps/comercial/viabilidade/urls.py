from django.urls import path
from . import views

app_name = 'comercial_viabilidade'

urlpatterns = [
    path('api/viabilidade/', views.api_viabilidade, name='api_viabilidade'),
]
