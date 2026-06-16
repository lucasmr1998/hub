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

    Persistencia: cada chamada gera 1 OrdemServicoTentativa (painel
    /integracoes/ordens-servico/). Retries pro mesmo id_atendimento sao agrupados
    sob o mesmo grupo_tentativas_id.
    """
    import time
    import uuid
    from apps.sistema.utils import _parse_json_request
    from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
    from apps.integracoes.services.hubsoft_errors import categorizar_falha_hubsoft
    from apps.integracoes.models import OrdemServicoTentativa, ServicoClienteHubsoft

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

    # Resolve grupo de tentativas: reusa se houver anterior pro mesmo atendimento
    id_atend = data.get('id_atendimento')
    try:
        id_atend_int = int(id_atend) if id_atend is not None else None
    except (TypeError, ValueError):
        id_atend_int = None
    ultima = None
    if id_atend_int is not None:
        ultima = (
            OrdemServicoTentativa.all_tenants
            .filter(tenant=integracao.tenant, id_atendimento_hubsoft=id_atend_int)
            .order_by('-tentativa_numero').first()
        )
    grupo_id = ultima.grupo_tentativas_id if ultima else uuid.uuid4()
    tentativa_num = (ultima.tentativa_numero + 1) if ultima else 1

    # Tenta resolver servico/cliente/lead a partir do id_cliente_servico (se vier)
    id_cli_serv = data.get('id_cliente_servico')
    servico = cliente_hs = lead = None
    if id_cli_serv:
        servico = (
            ServicoClienteHubsoft.all_tenants
            .filter(tenant=integracao.tenant, id_cliente_servico=id_cli_serv)
            .select_related('cliente').first()
        )
        if servico:
            cliente_hs = servico.cliente
            lead = getattr(cliente_hs, 'lead', None) if cliente_hs else None

    # Trava defensiva: score externo precisa estar aprovado pra abrir OS.
    # Bloqueia mesmo se a chamada vier direto do Matrix (fora da engine do CRM).
    if lead is not None:
        score = getattr(lead, 'score_status', 'nao_consultado')
        if score != 'aprovado':
            return JsonResponse({
                'status': 'error',
                'msg': f'Lead bloqueado por score externo (status={score}). Aguardando aprovacao manual.',
                'motivo': 'score_bloqueado',
                'score_status': score,
            }, status=409)

    # Cria a tentativa com status=pendente
    tentativa = OrdemServicoTentativa(
        tenant=integracao.tenant,
        grupo_tentativas_id=grupo_id,
        tentativa_numero=tentativa_num,
        id_atendimento_hubsoft=id_atend_int,
        integracao=integracao,
        lead=lead,
        cliente_hubsoft=cliente_hs,
        servico=servico,
        status='pendente',
        payload_enviado=data,
        data_inicio_programado=data.get('data_inicio_programado') or None,
        hora_inicio_programado=data.get('hora_inicio_programado') or None,
        data_termino_programado=data.get('data_termino_programado') or None,
        hora_termino_programado=data.get('hora_termino_programado') or None,
        id_tecnico=(tecnicos[0] if tecnicos else None),
        cidade=(lead.cidade if lead and lead.cidade else ''),
        origem='matrix',
    )

    t0 = time.monotonic()
    try:
        ordem = HubsoftService(integracao).abrir_os(
            id_atendimento=id_atend,
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
        tentativa.status = 'sucesso'
        tentativa.resposta_hubsoft = ordem if isinstance(ordem, dict) else {'raw': str(ordem)[:2000]}
        if isinstance(ordem, dict):
            tentativa.id_ordem_servico_hubsoft = ordem.get('id_ordem_servico') or ordem.get('id')
        tentativa.duracao_ms = int((time.monotonic() - t0) * 1000)
        tentativa.save()
        return JsonResponse({'status': 'success', 'ordem_servico': ordem})
    except HubsoftServiceError as e:
        msg = str(e)
        tentativa.status = 'falha'
        tentativa.motivo_falha_mensagem = msg[:2000]
        tentativa.motivo_falha_categoria = categorizar_falha_hubsoft(msg)
        tentativa.duracao_ms = int((time.monotonic() - t0) * 1000)
        tentativa.save()
        return JsonResponse({'status': 'error', 'msg': msg[:300]}, status=400)
