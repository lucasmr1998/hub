"""
Rotas de visao comercial das tentativas HubSoft (OS + Contratos).

Montadas em `/comercial/...` pra deixar visivel no menu Comercial — sao
parte do processo de venda (abertura de OS + aceite de contrato), nao
soh detalhe tecnico de integracao.

As views vivem em apps.integracoes pq dependem do HubsoftService, mas
o roteamento HTTP fica aqui em separado pra alinhar com a UI/UX.
"""
from django.urls import path

from . import views_ordens_servico
from . import views_contratos_tentativas

app_name = 'integracoes_comercial'

urlpatterns = [
    # Ordens de Servico (tentativas via Matrix)
    path('ordens-servico/', views_ordens_servico.lista_ordens_servico, name='ordens_servico_lista'),
    path('ordens-servico/<uuid:grupo_id>/', views_ordens_servico.detalhe_ordem_servico, name='ordens_servico_detalhe'),
    path('ordens-servico/<uuid:grupo_id>/retentar/', views_ordens_servico.retentar_ordem_servico, name='ordens_servico_retentar'),

    # Contratos (tentativas de criar/aceitar contrato HubSoft via engine de automacao)
    path('contratos/', views_contratos_tentativas.lista_contratos, name='contratos_lista'),
    path('contratos/<uuid:grupo_id>/', views_contratos_tentativas.detalhe_contrato, name='contratos_detalhe'),
    path('contratos/<uuid:grupo_id>/retentar/', views_contratos_tentativas.retentar_contrato, name='contratos_retentar'),
]
