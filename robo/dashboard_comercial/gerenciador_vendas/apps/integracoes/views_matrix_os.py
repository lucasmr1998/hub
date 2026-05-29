"""Endpoints consumidos pelo Matrix para agendamento/abertura de OS, sobre o HubSoft.

Substituem a camada externa `apimatrix.<provedor>` trazendo a orquestracao pra
dentro do Hubtrix. Autenticam por Bearer token (api_token_required -> request.tenant).

Fase 1: consultar_datas_sem_domingo (logica de data pura).
Fases seguintes: consultar_agenda, abrir_atendimento, abrir_os (via HubsoftService).
"""
import datetime
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from apps.sistema.decorators import api_token_required

logger = logging.getLogger(__name__)

# Defaults da geracao de datas de instalacao (ajustaveis por querystring).
DATAS_OFFSET_DIAS = 1   # a partir de quantos dias da data_referencia
DATAS_QUANTIDADE = 5    # quantas datas retornar (Matrix le as 3 primeiras)


@csrf_exempt
@require_GET
@api_token_required
def consultar_datas_sem_domingo(request):
    """Retorna as proximas datas disponiveis para instalacao, pulando domingos.

    GET ?data_referencia=DD/MM/YYYY [&qtd=N] [&offset_dias=N]
    Resposta: {"status": "success", "datas": ["DD/MM/YYYY", ...]}
    (o Matrix le datas.0, datas.1, datas.2 -> data_instalacao_1/2/3)
    """
    data_ref = (request.GET.get('data_referencia') or '').strip()
    try:
        base = datetime.datetime.strptime(data_ref, '%d/%m/%Y').date()
    except (ValueError, TypeError):
        from django.utils import timezone
        base = timezone.localdate()

    try:
        qtd = max(1, min(int(request.GET.get('qtd', DATAS_QUANTIDADE)), 15))
    except (ValueError, TypeError):
        qtd = DATAS_QUANTIDADE
    try:
        offset = max(0, int(request.GET.get('offset_dias', DATAS_OFFSET_DIAS)))
    except (ValueError, TypeError):
        offset = DATAS_OFFSET_DIAS

    datas = []
    dia = base + datetime.timedelta(days=offset)
    while len(datas) < qtd:
        if dia.weekday() != 6:  # 6 = domingo (Mon=0 ... Sun=6)
            datas.append(dia.strftime('%d/%m/%Y'))
        dia += datetime.timedelta(days=1)

    return JsonResponse({'status': 'success', 'datas': datas})
