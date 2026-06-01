"""Endpoints publicos /api/public/n8n/conhecimento/* — base de conhecimento.

Permitem que bots externos (Matrix, N8N agente LLM) registrem perguntas sem
resposta E busquem na base de conhecimento (RAG via pgvector). Autenticam
por Bearer token via api_token_required -> request.tenant.
"""
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.sistema.decorators import api_token_required

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
@api_token_required
def registrar_pergunta(request):
    """POST /api/public/n8n/conhecimento/registrar-pergunta/

    Body JSON:
      {
        "pergunta": "qual o valor do plano 500MB?",   # obrigatorio
        "lead_id": 462,        # opcional
        "conversa_id": 312     # opcional
      }

    Resposta:
      {"status": "success",
       "criada": true|false,         # true=nova, false=incrementou ocorrencias
       "pergunta_id": 28,
       "ocorrencias": 3}
    """
    from apps.sistema.utils import _parse_json_request
    from apps.suporte.services import registrar_pergunta_sem_resposta

    data = _parse_json_request(request) or {}
    pergunta = (data.get('pergunta') or '').strip()
    if not pergunta or len(pergunta) < 3:
        return JsonResponse(
            {'status': 'error', 'msg': 'pergunta obrigatoria (min 3 chars)'},
            status=400,
        )

    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'status': 'error', 'msg': 'tenant nao resolvido'}, status=401)

    lead = None
    if data.get('lead_id'):
        from apps.comercial.leads.models import LeadProspecto
        lead = LeadProspecto.all_tenants.filter(tenant=tenant, id=data['lead_id']).first()

    conversa = None
    if data.get('conversa_id'):
        from apps.inbox.models import Conversa
        conversa = Conversa.all_tenants.filter(tenant=tenant, id=data['conversa_id']).first()

    try:
        obj, criada = registrar_pergunta_sem_resposta(
            tenant=tenant, pergunta=pergunta, lead=lead, conversa=conversa,
        )
    except Exception as e:
        logger.exception('Erro ao registrar pergunta sem resposta')
        return JsonResponse({'status': 'error', 'msg': str(e)[:300]}, status=400)

    if not obj:
        return JsonResponse(
            {'status': 'error', 'msg': 'pergunta invalida'}, status=400,
        )

    return JsonResponse({
        'status': 'success',
        'criada': criada,
        'pergunta_id': obj.id,
        'ocorrencias': obj.ocorrencias,
    })


@csrf_exempt
@require_POST
@api_token_required
def registrar_erro_resposta(request):
    """POST /api/public/n8n/atendimento/registrar-erro-resposta/

    Telemetria de fricao no fluxo: bot perguntou X, cliente respondeu Y errado.
    Diferente de /conhecimento/registrar-pergunta/ (la o cliente pergunta livre).

    Body JSON:
      {
        "pergunta_bot": "qual seu CPF?",         # obrigatorio
        "resposta_cliente": "12345",             # obrigatorio
        "no_fluxo": "ColetaCPF",                 # opcional
        "canal": "whatsapp",                     # opcional
        "lead_id": 462,                          # opcional
        "conversa_id": 312                       # opcional
      }

    Resposta:
      {"status":"success","criada":true|false,"erro_id":N,"ocorrencias":N}
    """
    from apps.sistema.utils import _parse_json_request
    from apps.comercial.atendimento.services.motivo_erro_service import registrar_erro_resposta as svc

    data = _parse_json_request(request) or {}
    pb = (data.get('pergunta_bot') or '').strip()
    rc = (data.get('resposta_cliente') or '').strip()
    if not pb or not rc:
        return JsonResponse(
            {'status': 'error', 'msg': 'pergunta_bot e resposta_cliente sao obrigatorios'},
            status=400,
        )

    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'status': 'error', 'msg': 'tenant nao resolvido'}, status=401)

    lead = None
    if data.get('lead_id'):
        from apps.comercial.leads.models import LeadProspecto
        lead = LeadProspecto.all_tenants.filter(tenant=tenant, id=data['lead_id']).first()
    conversa = None
    if data.get('conversa_id'):
        from apps.inbox.models import Conversa
        conversa = Conversa.all_tenants.filter(tenant=tenant, id=data['conversa_id']).first()

    try:
        obj, criada = svc(
            tenant=tenant,
            pergunta_bot=pb, resposta_cliente=rc,
            no_fluxo=(data.get('no_fluxo') or '').strip(),
            canal=(data.get('canal') or '').strip(),
            lead=lead, conversa=conversa,
        )
    except Exception as e:
        logger.exception('Erro ao registrar erro de resposta')
        return JsonResponse({'status': 'error', 'msg': str(e)[:300]}, status=400)

    if not obj:
        return JsonResponse({'status': 'error', 'msg': 'payload invalido'}, status=400)

    return JsonResponse({
        'status': 'success',
        'criada': criada,
        'erro_id': obj.id,
        'ocorrencias': obj.ocorrencias,
    })


@csrf_exempt
@require_POST
@api_token_required
def buscar_conhecimento(request):
    """POST /api/public/n8n/conhecimento/buscar/

    Body JSON:
      {
        "pergunta": "qual o valor do plano 500MB?",   # obrigatorio
        "k": 5,                  # opcional, default 5
        "distancia_max": 0.5     # opcional, default 0.5
      }

    Resposta `200`:
      {
        "status": "success",
        "encontrou": true,
        "artigos": [
          {
            "id": 12,
            "titulo": "Tabela de planos residenciais",
            "resumo": "Planos a partir de R$ 89/mes ...",
            "conteudo": "...",
            "tags": ["planos","preco"],
            "url": "/suporte/conhecimento/artigo/tabela-planos/",
            "distancia": 0.18
          }
        ]
      }
    """
    from apps.sistema.utils import _parse_json_request
    from apps.suporte.services import buscar_artigos

    data = _parse_json_request(request) or {}
    pergunta = (data.get('pergunta') or '').strip()
    if not pergunta:
        return JsonResponse({'status': 'error', 'msg': 'pergunta obrigatoria'}, status=400)

    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'status': 'error', 'msg': 'tenant nao resolvido'}, status=401)

    try:
        k = max(1, min(int(data.get('k', 5)), 20))
    except (ValueError, TypeError):
        k = 5
    try:
        dist_max = float(data.get('distancia_max', 0.5))
    except (ValueError, TypeError):
        dist_max = 0.5

    resultados = buscar_artigos(tenant, pergunta, k=k, distancia_max=dist_max)
    artigos = [
        {
            'id': r['artigo'].id,
            'titulo': r['artigo'].titulo,
            'resumo': r['artigo'].resumo or '',
            'conteudo': r['artigo'].conteudo or '',
            'tags': r['artigo'].tags_lista,
            'url': f'/suporte/conhecimento/artigo/{r["artigo"].slug}/',
            'distancia': r['distancia'],
        }
        for r in resultados
    ]

    return JsonResponse({
        'status': 'success',
        'encontrou': bool(artigos),
        'artigos': artigos,
    })


@csrf_exempt
@require_POST
@api_token_required
def encerrar_oportunidade_com_motivo(request, pk):
    """POST /api/public/n8n/crm/oportunidade/<pk>/encerrar-com-motivo/

    Permite que bot externo (Matrix, N8N agente LLM) encerre uma oportunidade
    movendo-a pro estagio is_final_perdido + classifica motivo automaticamente
    via LLM com base na ultima mensagem do cliente.

    Body JSON:
      {
        "ultima_mensagem_cliente": "muito caro, fica pra proxima",  # obrigatorio
        "estagio_perdida_id": 42,   # opcional. Se omitido, pega 1o is_final_perdido do pipeline padrao
      }

    Resposta `200`:
      {"status":"success","motivo_classificado":"Preco","motivo_id":3,
       "confidence":0.86,"oportunidade_id":58,"estagio":"Perdida"}

    Politica:
      - motivo_perda_origem='bot' (rastreio).
      - Se confidence < 0.5 ou LLM falhar -> usa motivo "Outro" + texto livre
        com a mensagem original e nao bloqueia (objetivo: nao travar fluxo).
      - Idempotente: se ja foi encerrada com motivo, retorna o motivo atual.
    """
    from apps.sistema.utils import _parse_json_request
    from apps.comercial.crm.models import OportunidadeVenda, MotivoPerda, PipelineEstagio
    from apps.sistema.services.embeddings import _resolver_api_key
    import requests as _req
    import json as _json

    data = _parse_json_request(request) or {}
    ultima_msg = (data.get('ultima_mensagem_cliente') or '').strip()
    if not ultima_msg:
        return JsonResponse({'status': 'error', 'msg': 'ultima_mensagem_cliente obrigatoria'}, status=400)

    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'status': 'error', 'msg': 'tenant nao resolvido'}, status=401)

    op = OportunidadeVenda.all_tenants.filter(tenant=tenant, pk=pk, ativo=True).first()
    if not op:
        return JsonResponse({'status': 'error', 'msg': 'oportunidade nao encontrada'}, status=404)

    # Idempotente: ja encerrada com motivo
    if op.motivo_perda_ref_id and op.estagio and op.estagio.is_final_perdido:
        return JsonResponse({
            'status': 'success', 'idempotente': True,
            'motivo_classificado': op.motivo_perda_ref.nome if op.motivo_perda_ref else None,
            'motivo_id': op.motivo_perda_ref_id,
            'oportunidade_id': op.pk,
        })

    # Resolve estagio_perdida
    estagio_id = data.get('estagio_perdida_id')
    if estagio_id:
        estagio_perdida = PipelineEstagio.all_tenants.filter(tenant=tenant, pk=estagio_id, is_final_perdido=True).first()
    else:
        estagio_perdida = PipelineEstagio.all_tenants.filter(
            tenant=tenant, is_final_perdido=True, ativo=True,
        ).order_by('-ordem').first()
    if not estagio_perdida:
        return JsonResponse({'status': 'error', 'msg': 'tenant nao tem estagio is_final_perdido cadastrado'}, status=400)

    motivos = list(MotivoPerda.all_tenants.filter(tenant=tenant, ativo=True).order_by('ordem', 'nome').values('id', 'nome'))
    outros_id = next((m['id'] for m in motivos if m['nome'].lower() == 'outro'), None)

    motivo_id_final = outros_id
    motivo_nome_final = 'Outro'
    confidence = 0.0
    justificativa = f'Mensagem do cliente: {ultima_msg[:200]}'

    # Classifica via OpenAI
    api_key = _resolver_api_key(tenant)
    if api_key and motivos:
        opcoes_txt = '\n'.join([f"  - id={m['id']}: {m['nome']}" for m in motivos])
        try:
            r = _req.post(
                'https://api.openai.com/v1/chat/completions',
                headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                json={
                    'model': 'gpt-4o-mini',
                    'messages': [
                        {'role': 'system', 'content':
                            'Voce classifica motivo de perda de oportunidade comercial a partir de UMA mensagem '
                            'do cliente. Retorne JSON {motivo_id, motivo_nome, justificativa, confidence}. Se '
                            'incerto, use motivo_id=null e confidence baixo.\n\nMotivos:\n' + opcoes_txt
                        },
                        {'role': 'user', 'content': ultima_msg},
                    ],
                    'response_format': {'type': 'json_object'},
                    'temperature': 0.1,
                },
                timeout=30,
            )
            if r.status_code == 200:
                resp = _json.loads(r.json()['choices'][0]['message']['content'])
                confidence = float(resp.get('confidence') or 0.0)
                if confidence >= 0.5 and resp.get('motivo_id'):
                    candidato_id = resp.get('motivo_id')
                    if any(m['id'] == candidato_id for m in motivos):
                        motivo_id_final = candidato_id
                        motivo_nome_final = next((m['nome'] for m in motivos if m['id'] == candidato_id), motivo_nome_final)
                        justificativa = (resp.get('justificativa') or '').strip()[:400]
        except Exception as e:
            logger.exception('classify motivo via LLM falhou: %s', e)

    obs = f'[BOT conf={confidence:.2f}] {justificativa}'
    OportunidadeVenda.all_tenants.filter(pk=op.pk).update(
        estagio=estagio_perdida,
        motivo_perda_ref_id=motivo_id_final,
        motivo_perda=obs,
        motivo_perda_origem='bot',
    )

    return JsonResponse({
        'status': 'success',
        'motivo_classificado': motivo_nome_final,
        'motivo_id': motivo_id_final,
        'confidence': confidence,
        'oportunidade_id': op.pk,
        'estagio': estagio_perdida.nome,
    })
