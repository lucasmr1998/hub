"""
Rotas publicas de candidatura. Sem login.

Prefixo proprio (`people/candidatura/`) e nao um sufixo de `people/publico/`
porque sao publicos DIFERENTES: `publico` e o colaborador ja contratado
preenchendo o cadastro; aqui e o candidato, que ainda nao tem vinculo nenhum.
Misturar as duas arvores faria uma mudanca de rota do DP atingir recrutamento.

A isencao de login vive em `_EXEMPT_PATTERNS` no middleware do sistema.
"""
from django.urls import path

from apps.people.views import publico_candidatura

app_name = 'people_candidatura'

urlpatterns = [
    path('<str:token>/', publico_candidatura.formulario, name='formulario'),
    path('<str:token>/enviar/', publico_candidatura.enviar, name='enviar'),
]
