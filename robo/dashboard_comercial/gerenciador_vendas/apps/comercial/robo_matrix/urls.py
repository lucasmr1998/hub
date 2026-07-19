"""Rotas do adaptador de contrato Matrix.

Montado em `/robo/` no urls raiz. O `<token>` identifica a empresa (api_token de
uma IntegracaoAPI ativa). O prefixo `/ia/` espelha o contrato do robo_v2, onde o
nginx removia `/robo-v2/ia` antes de chegar na FastAPI.
"""
from django.urls import path

from . import views

app_name = 'robo_matrix'

urlpatterns = [
    path('<str:token>/ia/ping', views.ping, name='ping'),
]
