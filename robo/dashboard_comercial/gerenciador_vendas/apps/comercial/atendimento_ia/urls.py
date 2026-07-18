from django.urls import path

from . import views

app_name = 'atendimento_ia'

# ATENCAO: os 3 paths abaixo NAO tem barra final, de proposito. O contrato do
# Matrix chama exatamente esses paths sem trailing slash. Com APPEND_SLASH=True
# (default do Django), um POST pra uma rota registrada com barra e chamada
# sem barra vira redirect 301, e o cliente HTTP do bot NAO segue redirect de
# POST preservando o body (perde os dados, e ainda gasta parte do timeout de
# 45s no round-trip do redirect). Registrar aqui SEM barra bate exatamente
# com o que o bot chama, sem depender de comportamento de redirect.
urlpatterns = [
    path('ia/proximo-passo', views.proximo_passo, name='proximo_passo'),
    path('ia/validar', views.validar, name='validar'),
    path('ia/recontato', views.recontato, name='recontato'),
]
