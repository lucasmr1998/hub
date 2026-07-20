"""
Tela de Analises do departamento pessoal.

Todos os numeros saem do HistoricoSituacao, gravado desde o passo 4. A
telemetria foi desenhada como fonte primaria justamente pra isso: construir esta
tela foi trabalho de query, nao de instrumentacao.
"""
from django.shortcuts import render

from apps.people import analises as metricas
from apps.people.models import Unidade
from apps.people.permissoes import requer_people


PERIODOS = [('7', '7 dias'), ('30', '30 dias'), ('90', '90 dias')]


@requer_people()
def painel(request):
    try:
        dias = int(request.GET.get('dias') or 30)
    except (TypeError, ValueError):
        dias = 30
    if dias not in (7, 30, 90):
        dias = 30

    unidade = None
    unidade_id = request.GET.get('unidade') or ''
    if unidade_id:
        unidade = Unidade.objects.filter(pk=unidade_id).first()

    tenant = request.tenant

    return render(request, 'people/analises.html', {
        'pagetitle': 'Analises',
        'resumo': metricas.resumo(tenant, dias=dias, unidade=unidade),
        'unidades': metricas.por_unidade(tenant, dias=dias),
        'funil': metricas.funil(tenant, dias=dias, unidade=unidade),
        'evolucao': metricas.evolucao_mensal(tenant, unidade=unidade),
        'parados': metricas.parados(tenant, unidade=unidade)[:12],
        'periodos': PERIODOS,
        'dias_selecionado': str(dias),
        'unidades_opcoes': list(
            Unidade.objects.filter(ativo=True).values_list('pk', 'nome')),
        'unidade_selecionada': unidade_id,
    })
