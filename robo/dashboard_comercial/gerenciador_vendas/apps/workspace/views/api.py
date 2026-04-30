"""
APIs AJAX do Workspace.

Endpoints leves usados pelo Kanban (drag-drop) e quick actions.
Resposta sempre JSON. Erros sempre status 4xx + mensagem.
"""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.sistema.decorators import user_tem_funcionalidade
from apps.sistema.utils import registrar_acao
from apps.workspace.models import Tarefa


STATUS_VALIDOS = {'rascunho', 'pendente', 'em_andamento', 'concluida', 'bloqueada'}


def _pode_editar(request, tarefa):
    if request.user.is_superuser:
        return True
    if user_tem_funcionalidade(request, 'workspace.editar_todos'):
        return True
    is_owner = (
        tarefa.responsavel_id == request.user.id
        or tarefa.projeto.responsavel_id == request.user.id
    )
    if is_owner and user_tem_funcionalidade(request, 'workspace.editar_proprios'):
        return True
    return False


@login_required
@require_POST
def kanban_mover(request):
    """
    Move uma tarefa entre colunas do kanban.

    POST body (JSON):
        { "tarefa_id": 123, "novo_status": "em_andamento", "ordem": 0 }

    Resposta: { "ok": true, "tarefa": {...} } ou { "ok": false, "erro": "..." }
    """
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'erro': 'Payload JSON invalido.'}, status=400)

    tarefa_id = payload.get('tarefa_id')
    novo_status = payload.get('novo_status')
    nova_ordem = payload.get('ordem', 0)

    if not tarefa_id or not novo_status:
        return JsonResponse({'ok': False, 'erro': 'tarefa_id e novo_status sao obrigatorios.'}, status=400)
    if novo_status not in STATUS_VALIDOS:
        return JsonResponse({'ok': False, 'erro': f'Status invalido: {novo_status}'}, status=400)

    tarefa = get_object_or_404(Tarefa, pk=tarefa_id)

    if not _pode_editar(request, tarefa):
        return JsonResponse({'ok': False, 'erro': 'Sem permissao pra mover esta tarefa.'}, status=403)

    status_anterior = tarefa.status
    tarefa.status = novo_status
    try:
        tarefa.ordem = int(nova_ordem)
    except (TypeError, ValueError):
        tarefa.ordem = 0

    # Auto: marca data_conclusao quando vai pra concluida; limpa quando sai
    if novo_status == 'concluida' and status_anterior != 'concluida':
        tarefa.data_conclusao = timezone.now()
    elif novo_status != 'concluida' and status_anterior == 'concluida':
        tarefa.data_conclusao = None

    tarefa.save(update_fields=['status', 'ordem', 'data_conclusao', 'atualizado_em'])

    registrar_acao(
        'workspace', 'mover_kanban', 'tarefa', tarefa.id,
        f'Tarefa "{tarefa.titulo}" movida {status_anterior} -> {novo_status}',
        request=request,
    )

    return JsonResponse({
        'ok': True,
        'tarefa': {
            'id': tarefa.id,
            'titulo': tarefa.titulo,
            'status': tarefa.status,
            'ordem': tarefa.ordem,
            'data_conclusao': tarefa.data_conclusao.isoformat() if tarefa.data_conclusao else None,
        },
    })


@login_required
@require_POST
def tarefa_status(request, pk):
    """
    Quick action pra mudar status de uma tarefa (botoes de aprovar/iniciar/concluir).

    POST body (JSON ou form-encoded):
        { "novo_status": "em_andamento" }

    Resposta: { "ok": true, "tarefa": {...} }
    """
    tarefa = get_object_or_404(Tarefa, pk=pk)
    if not _pode_editar(request, tarefa):
        return JsonResponse({'ok': False, 'erro': 'Sem permissao.'}, status=403)

    novo_status = request.POST.get('novo_status') or ''
    if not novo_status and request.body:
        try:
            payload = json.loads(request.body.decode('utf-8'))
            novo_status = payload.get('novo_status', '')
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    if novo_status not in STATUS_VALIDOS:
        return JsonResponse({'ok': False, 'erro': f'Status invalido: {novo_status}'}, status=400)

    status_anterior = tarefa.status
    tarefa.status = novo_status
    if novo_status == 'concluida' and status_anterior != 'concluida':
        tarefa.data_conclusao = timezone.now()
    elif novo_status != 'concluida' and status_anterior == 'concluida':
        tarefa.data_conclusao = None
    tarefa.save(update_fields=['status', 'data_conclusao', 'atualizado_em'])

    registrar_acao(
        'workspace', 'mudar_status', 'tarefa', tarefa.id,
        f'Tarefa "{tarefa.titulo}" status: {status_anterior} -> {novo_status}',
        request=request,
    )

    return JsonResponse({
        'ok': True,
        'tarefa': {
            'id': tarefa.id,
            'status': tarefa.status,
            'data_conclusao': tarefa.data_conclusao.isoformat() if tarefa.data_conclusao else None,
        },
    })
