"""
Entrada do modulo People.

Placeholder do passo 1 do plano. Vira o board kanban no passo 7.
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.people.models import Unidade
from apps.sistema.decorators import user_tem_funcionalidade


@login_required
def home(request):
    if not user_tem_funcionalidade(request, 'people.ver'):
        return HttpResponseForbidden('Sem permissao pra acessar People.')

    contexto = {
        'pagetitle': 'People',
        'unidades': Unidade.objects.filter(ativo=True),
    }
    return render(request, 'people/home.html', contexto)
