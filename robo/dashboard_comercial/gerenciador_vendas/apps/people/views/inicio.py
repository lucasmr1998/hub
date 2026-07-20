"""
Entrada do modulo People.

Placeholder do passo 1. Vira o board kanban no passo 7.
"""
from django.shortcuts import render

from apps.people.models import Unidade
from apps.people.permissoes import requer_people


@requer_people()
def home(request):
    contexto = {
        'pagetitle': 'People',
        'unidades': Unidade.objects.filter(ativo=True),
    }
    return render(request, 'people/home.html', contexto)
