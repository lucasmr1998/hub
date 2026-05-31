"""Endpoints consumidos pelo Matrix para agendamento/abertura de OS, sobre o HubSoft.

Substituem a camada externa `apimatrix.<provedor>` trazendo a orquestracao pra
dentro do Hubtrix. Autenticam por Bearer token (api_token_required -> request.tenant).

Fase 1: consultar_datas_sem_domingo (logica de data pura).
Fases seguintes: consultar_agenda, abrir_atendimento, abrir_os (via HubsoftService).
"""
import datetime
import logging
import unicodedata

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.sistema.decorators import api_token_required

logger = logging.getLogger(__name__)

# Faixas de turno por hora de inicio (HH). Ajustaveis se o provedor usar outras.
_TURNOS = {
    'manha': (0, 12),
    'tarde': (12, 18),
    'noite': (18, 24),
}


def _hubsoft_e_config(request):
    """Retorna (IntegracaoAPI hubsoft do tenant, dict de config os_matrix)."""
    from apps.integracoes.models import IntegracaoAPI
    integracao = IntegracaoAPI.all_tenants.filter(
        tenant=getattr(request, 'tenant', None), tipo='hubsoft', ativa=True,
    ).first()
    cfg = (integracao.configuracoes_extras or {}).get('os_matrix', {}) if integracao else {}
    return integracao, cfg


def _normaliza(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower().strip()
    return s


def _data_iso(data_br):
    """DD/MM/YYYY -> YYYY-MM-DD (ou hoje se invalido)."""
    try:
        return datetime.datetime.strptime((data_br or '').strip(), '%d/%m/%Y').strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        from django.utils import timezone
        return timezone.localdate().strftime('%Y-%m-%d')


def _coerce_lista(v):
    # Matrix as vezes manda string ('manha') ou int (258) onde o service espera lista.
    # enumerate(string) explode em chars, entao normalizamos aqui.
    if v is None or v == '':
        return None
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v]


def _slots_do_turno(horarios, data_iso, turno):
    """Extrai os horarios da agenda HubSoft para uma data/turno -> formato do Matrix:
    [{"horario": "HH:MM:SS", "tecnicos": [{"id": N}, ...]}, ...]
    """
    faixa = _TURNOS.get(_normaliza(turno))
    bloco_data = ((horarios or {}).get('datas') or {}).get(data_iso) or {}
    out = []
    for hora_str, info in (bloco_data.get('horarios') or {}).items():
        try:
            hh = int(str(hora_str).split(':')[0])
        except (ValueError, IndexError):
            hh = 0
        if faixa and not (faixa[0] <= hh < faixa[1]):
            continue
        tecnicos = [{'id': t.get('id')} for t in (info.get('tecnicos') or []) if t.get('id') is not None]
        out.append({'horario': hora_str, 'tecnicos': tecnicos})
    return out

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


@csrf_exempt
@require_GET
@api_token_required
def consultar_agenda(request):
    """Horarios disponiveis na agenda do tenant para uma data/turno.

    GET ?data_referencia=DD/MM/YYYY&turno=manha|tarde|noite
    Resposta (formato que o Matrix le):
      {"dados": {"id_agenda_ordem_servico": N,
                 "disponibilidade_turno": [{"horario": "HH:MM:SS", "tecnicos": [{"id": N}]}]}}
    """
    from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
    integracao, cfg = _hubsoft_e_config(request)
    if not integracao:
        return JsonResponse({'status': 'error', 'msg': 'Integracao HubSoft nao configurada para o tenant'}, status=400)

    id_agenda = cfg.get('id_agenda_ordem_servico')
    descricao_agenda = cfg.get('agenda_descricao')
    if not id_agenda and not descricao_agenda:
        return JsonResponse({'status': 'error', 'msg': 'id_agenda_ordem_servico nao configurado (os_matrix)'}, status=400)

    data_iso = _data_iso(request.GET.get('data_referencia'))
    turno = request.GET.get('turno') or ''
    try:
        horarios = HubsoftService(integracao).consultar_horarios_agenda(
            id_agenda_ordem_servico=id_agenda, descricao=descricao_agenda,
            data_inicio=data_iso, dias=1,
        )
    except HubsoftServiceError as e:
        return JsonResponse({'status': 'error', 'msg': str(e)[:300]}, status=400)

    return JsonResponse({'status': 'success', 'dados': {
        'id_agenda_ordem_servico': id_agenda,
        'disponibilidade_turno': _slots_do_turno(horarios, data_iso, turno),
    }})


@csrf_exempt
@require_POST
@api_token_required
def abrir_atendimento(request):
    """Abre um atendimento no HubSoft (sem OS). Body JSON com id_cliente_servico,
    nome, telefone, descricao, email. Tipos/status/responsavel vem da config os_matrix.
    Resposta: {"atendimento": {"id_atendimento": N, ...}}.
    """
    from apps.sistema.utils import _parse_json_request
    from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
    integracao, cfg = _hubsoft_e_config(request)
    if not integracao:
        return JsonResponse({'status': 'error', 'msg': 'Integracao HubSoft nao configurada'}, status=400)
    data = _parse_json_request(request) or {}
    try:
        atendimento = HubsoftService(integracao).abrir_atendimento_os(
            id_cliente_servico=data.get('id_cliente_servico'),
            descricao=data.get('descricao') or 'Atendimento via Matrix',
            nome=data.get('nome') or '',
            telefone=data.get('telefone') or '',
            email=data.get('email'),
            id_tipo_atendimento=cfg.get('id_tipo_atendimento'),
            id_atendimento_status=cfg.get('id_status_atendimento'),
            id_usuario_responsavel=cfg.get('id_usuario_responsavel'),
            abrir_os=False,
        )
    except HubsoftServiceError as e:
        return JsonResponse({'status': 'error', 'msg': str(e)[:300]}, status=400)
    return JsonResponse({'status': 'success', 'atendimento': atendimento})


@csrf_exempt
@require_POST
@api_token_required
def abrir_os(request):
    """Abre a OS a partir do atendimento, com o slot escolhido. Body JSON:
    id_atendimento, data_inicio_programado, data_termino_programado,
    hora_inicio_programado, hora_termino_programado, id_tecnico|tecnicos, disponibilidade.
    id_tipo_os / status / id_agenda vem da config os_matrix (com override pelo body).
    Resposta: {"ordem_servico": {...}}.
    """
    from apps.sistema.utils import _parse_json_request
    from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
    integracao, cfg = _hubsoft_e_config(request)
    if not integracao:
        return JsonResponse({'status': 'error', 'msg': 'Integracao HubSoft nao configurada'}, status=400)
    data = _parse_json_request(request) or {}
    if not data.get('id_atendimento'):
        return JsonResponse({'status': 'error', 'msg': 'id_atendimento obrigatorio'}, status=400)

    tecnicos = _coerce_lista(data.get('tecnicos'))
    if not tecnicos and data.get('id_tecnico'):
        tecnicos = [data['id_tecnico']]
    disponibilidade = _coerce_lista(data.get('disponibilidade'))
    try:
        ordem = HubsoftService(integracao).abrir_os(
            id_atendimento=data['id_atendimento'],
            id_agenda_ordem_servico=data.get('id_agenda_ordem_servico') or cfg.get('id_agenda_ordem_servico'),
            id_tipo_ordem_servico=data.get('id_tipo_ordem_servico') or cfg.get('id_tipo_os'),
            data_inicio_programado=data.get('data_inicio_programado'),
            data_termino_programado=data.get('data_termino_programado'),
            hora_inicio_programado=data.get('hora_inicio_programado'),
            hora_termino_programado=data.get('hora_termino_programado'),
            status=data.get('status') or cfg.get('status_os') or 'pendente',
            tecnicos=tecnicos,
            disponibilidade=disponibilidade,
        )
    except HubsoftServiceError as e:
        return JsonResponse({'status': 'error', 'msg': str(e)[:300]}, status=400)
    return JsonResponse({'status': 'success', 'ordem_servico': ordem})
