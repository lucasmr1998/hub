from django.urls import path
from . import views

app_name = 'assistente'

urlpatterns = [
    path('webhook/<str:api_token>/', views.webhook_assistente, name='webhook'),
]
