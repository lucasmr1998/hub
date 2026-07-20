"""
Unidades (lojas e filiais).

Listagem somente leitura no passo 5, pra fechar a navegacao do modulo. O CRUD
entra no passo 6.
"""
from django.db.models import Count, Q
from django.shortcuts import render

from apps.people import estados
from apps.people.models import Unidade
from apps.people.permissoes import pode_acessar, requer_people


@requer_people()
def lista(request):
    unidades = Unidade.objects.annotate(
        total_colaboradores=Count(
            'colaboradores',
            filter=Q(colaboradores__situacao__in=estados.SITUACOES_ATIVAS),
        ),
    ).order_by('-ativo', 'nome')

    contexto = {
        'pagetitle': 'Unidades',
        'unidades': unidades,
        'pode_gerir': pode_acessar(request, 'people.gerir_unidades'),
    }
    return render(request, 'people/unidades_lista.html', contexto)
