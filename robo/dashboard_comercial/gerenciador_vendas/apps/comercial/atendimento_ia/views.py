"""
Os 3 endpoints do bot conversacional (Fase 2): /ia/proximo-passo, /ia/validar,
/ia/recontato. O bot Matrix e uma casca burra (renderiza mensagem, captura
resposta, chama a gente em loop); toda a inteligencia fica aqui.

Loop: proximo-passo (qual a proxima pergunta?) -> bot renderiza -> captura
resposta -> validar (serve? o que eu respondo?) -> volta pro proximo-passo.
No timeout do cliente: recontato.

Contrato de chaves e tipos e IMUTAVEL (extraido do JSON do flow do Matrix),
ver services/contrato.py. O Matrix tem timeout de 45s por chamada: qualquer
erro nosso vira uma resposta de transbordo, nunca um 500 nem um request
pendurado.
"""
import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.sistema.decorators import api_token_required

from .models import TentativaResposta
from .services import contrato
from .services import sessao as sessao_service
from .services import validacao as validacao_service
from apps.automacao.services import checklist as checklist_service

logger = logging.getLogger(__name__)

# ── status_lead (polimorfico, ver contrato) ─────────────────────────────────
STATUS_LEAD_INICIA_VENDA = 0
STATUS_LEAD_CLIENTE_ATIVO = 'cliente_ativo'
STATUS_LEAD_RETOMAR = 'em_andamento'

# ── proximo_passo ────────────────────────────────────────────────────────────
PASSO_SEGUIR_PERGUNTA = 'seguir_pergunta'
PASSO_ENCERRAR = 'red_encerrar'
MOTIVO_SEM_CHECKLIST = 'sem_checklist'
MOTIVO_TRANSBORDO_GENERICO = 'transbordado'

# ── validar ──────────────────────────────────────────────────────────────────
MSG_ERRO_SEM_CHECKLIST = 'Nao consegui continuar o atendimento automatico agora. Vou te transferir para um atendente.'
MSG_ERRO_SEM_ITEM_ATUAL = 'Perdi o fio da nossa conversa por aqui. Vou te transferir para um atendente.'
MSG_ERRO_PADRAO = 'Nao consegui entender sua resposta. Pode tentar novamente?'
# Usada so quando a IA detecta intencao de desistir/transferir e o proprio
# resultado nao trouxe uma mensagem humanizada pra usar no lugar (ver
# `validacao_service.INTENCOES_TRANSBORDO`).
MSG_TRANSBORDO_INTENCAO = 'Vou te transferir para um atendente que vai continuar seu atendimento.'
MOTIVO_SEM_ITEM_ATUAL = 'sem_item_atual'
MOTIVO_MAX_TENTATIVAS = 'max_tentativas_excedida'

# ── recontato ────────────────────────────────────────────────────────────────
# Documentado aqui porque nao vem de config nenhuma: apos esse numero de
# recontatos sem resposta do cliente, encerra em vez de reperguntar de novo.
LIMITE_TENTATIVAS_RECONTATO = 2
ACAO_REPERGUNTAR = 'reperguntar'
ACAO_ENCERRAR = 'encerrar'
MOTIVO_RECONTATO_ESGOTADO = 'recontato_esgotado'
MSG_RECONTATO_SEM_ITEM = 'Ainda esta ai?'


def _parse_json(request):
    try:
        corpo = request.body.decode('utf-8') if request.body else '{}'
        return json.loads(corpo or '{}')
    except (ValueError, UnicodeDecodeError):
        return None


def _to_int(valor, default=0):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return default


def _status_lead(sessao, checklist):
    """0 = sessao nova (nenhuma resposta ainda, o Matrix trata como "iniciar
    venda"); "cliente_ativo" = sessao marcada como cliente ja ativo;
    "em_andamento" = retomando um checklist ja comecado."""
    entidade_tipo, entidade_id = sessao_service.entidade_da_sessao(sessao)
    respostas = checklist_service.respostas_da_entidade(checklist, entidade_tipo, entidade_id)
    if not respostas:
        return STATUS_LEAD_INICIA_VENDA
    if sessao.is_cliente_ativo:
        return STATUS_LEAD_CLIENTE_ATIVO
    return STATUS_LEAD_RETOMAR


# ============================================================================
# POST /ia/proximo-passo
# ============================================================================

@csrf_exempt
@api_token_required
def proximo_passo(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo nao permitido'}, status=405)
    body = _parse_json(request)
    if body is None:
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    tenant = request.tenant
    cellphone = str(body.get('cellphone') or '').strip()
    lead_id = body.get('lead_id')
    # `ultima_mensagem` reservado pra deteccao de intent numa fase futura.

    checklist = sessao_service.checklist_do_tenant(tenant)
    if checklist is None:
        # Fail-safe: tenant sem checklist configurado nunca deve travar o
        # cliente no loop, manda pra humano.
        return JsonResponse(contrato.payload_proximo_passo(
            lead_id=lead_id, status_lead=STATUS_LEAD_RETOMAR,
            proximo_passo=PASSO_SEGUIR_PERGUNTA, proxima_pergunta_id=0,
            deve_perguntar=False, deve_transbordar=True,
            motivo=MOTIVO_SEM_CHECKLIST, intent_detectado='', mensagem_inicial='',
        ))

    sessao = sessao_service.obter_ou_criar_sessao(tenant, cellphone, lead_id, checklist)

    if sessao.status == 'transbordado':
        return JsonResponse(contrato.payload_proximo_passo(
            lead_id=sessao.lead_id, status_lead=_status_lead(sessao, checklist),
            proximo_passo=PASSO_SEGUIR_PERGUNTA, proxima_pergunta_id=0,
            deve_perguntar=False, deve_transbordar=True,
            motivo=sessao.motivo_transbordo or MOTIVO_TRANSBORDO_GENERICO,
            intent_detectado='', mensagem_inicial='',
        ))
    if sessao.status == 'finalizado':
        return JsonResponse(contrato.payload_proximo_passo(
            lead_id=sessao.lead_id, status_lead=_status_lead(sessao, checklist),
            proximo_passo=PASSO_ENCERRAR, proxima_pergunta_id=0,
            deve_perguntar=False, deve_transbordar=False,
            motivo='', intent_detectado='', mensagem_inicial='',
        ))

    entidade_tipo, entidade_id = sessao_service.entidade_da_sessao(sessao)
    item = checklist_service.proximo_item(checklist, entidade_tipo, entidade_id)

    if item is None:
        # Checklist completo: nada mais elegivel ficou sem resposta.
        sessao.status = 'finalizado'
        sessao.item_atual = None
        sessao.save(update_fields=['status', 'item_atual', 'ultima_interacao_em'])
        return JsonResponse(contrato.payload_proximo_passo(
            lead_id=sessao.lead_id, status_lead=_status_lead(sessao, checklist),
            proximo_passo=PASSO_ENCERRAR, proxima_pergunta_id=0,
            deve_perguntar=False, deve_transbordar=False,
            motivo='', intent_detectado='', mensagem_inicial='',
        ))

    status_lead = _status_lead(sessao, checklist)
    sessao.item_atual = item
    sessao.status = 'aguardando_resposta'
    sessao.save(update_fields=['item_atual', 'status', 'ultima_interacao_em'])

    return JsonResponse(contrato.payload_proximo_passo(
        lead_id=sessao.lead_id, status_lead=status_lead,
        proximo_passo=PASSO_SEGUIR_PERGUNTA, proxima_pergunta_id=item.id,
        deve_perguntar=True, deve_transbordar=False,
        motivo='', intent_detectado='', mensagem_inicial=item.pergunta, item=item,
    ))


# ============================================================================
# POST /ia/validar
# ============================================================================

@csrf_exempt
@api_token_required
def validar(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo nao permitido'}, status=405)
    body = _parse_json(request)
    if body is None:
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    tenant = request.tenant
    cellphone = str(body.get('cellphone') or '').strip()
    lead_id = body.get('lead_id')
    resposta_bruta = body.get('answer')
    question_id = body.get('question_id')

    checklist = sessao_service.checklist_do_tenant(tenant)
    if checklist is None:
        return JsonResponse(contrato.payload_validar(
            resposta_correta=False, resposta_sem_erro_api=False,
            retorno_erro_api=MSG_ERRO_SEM_CHECKLIST, needs_reception=True,
            is_a_client=False, cancelado=False, message='',
        ))

    sessao = sessao_service.obter_ou_criar_sessao(tenant, cellphone, lead_id, checklist)

    if sessao.status in ('transbordado', 'finalizado'):
        # Idempotente: nao ha mais o que validar, so confirma o estado atual
        # pro bot nao ficar preso esperando uma resposta que nao vai vir.
        return JsonResponse(contrato.payload_validar(
            resposta_correta=True, resposta_sem_erro_api=True, retorno_erro_api='',
            needs_reception=(sessao.status == 'transbordado'),
            is_a_client=sessao.is_cliente_ativo, cancelado=False, message='',
        ))

    item = sessao.item_atual
    if item is None:
        # Nao deveria acontecer (o bot sempre chama /ia/proximo-passo antes),
        # mas fail-safe: transborda em vez de derrubar o cliente num loop morto.
        logger.warning('Sessao %s recebeu /ia/validar sem item_atual', sessao.pk)
        sessao_service.transbordar(sessao, MOTIVO_SEM_ITEM_ATUAL)
        return JsonResponse(contrato.payload_validar(
            resposta_correta=False, resposta_sem_erro_api=False,
            retorno_erro_api=MSG_ERRO_SEM_ITEM_ATUAL, needs_reception=True,
            is_a_client=False, cancelado=False, message='',
        ))

    if question_id and _to_int(question_id) != item.id:
        # A fonte da verdade e sempre `sessao.item_atual`, nao o question_id
        # que o bot manda de volta, so loga pra investigar dessincronia.
        logger.warning(
            'question_id do Matrix (%s) diverge do item_atual da sessao %s (item %s)',
            question_id, sessao.pk, item.id,
        )

    resultado = validacao_service.validar(item, resposta_bruta, tenant)

    numero_tentativa = sessao.tentativas_item + 1
    TentativaResposta.objects.create(
        tenant=tenant, sessao=sessao, item=item, numero=numero_tentativa,
        resposta='' if resposta_bruta is None else str(resposta_bruta),
        valida=resultado['valida'], fonte_validacao=resultado['fonte'],
        motivo_erro=resultado['erro'],
    )

    # IA detectou que o cliente quer desistir ou falar com atendente: transborda
    # direto em vez de insistir na pergunta, mesmo que a resposta em si tenha
    # validado (o cliente pode responder certo e ainda assim pedir humano).
    intencao = resultado.get('intencao') or ''
    if intencao in validacao_service.INTENCOES_TRANSBORDO:
        sessao_service.transbordar(sessao, intencao)
        return JsonResponse(contrato.payload_validar(
            resposta_correta=False, resposta_sem_erro_api=True,
            retorno_erro_api=resultado.get('erro') or MSG_TRANSBORDO_INTENCAO,
            needs_reception=True, is_a_client=sessao.is_cliente_ativo,
            cancelado=False, message='',
        ))

    if resultado['valida'] is not False:
        # True (validou de verdade) ou None (IA fora do ar, aceito com
        # ressalva): os dois avancam o checklist.
        entidade_tipo, entidade_id = sessao_service.entidade_da_sessao(sessao)
        checklist_service.registrar_resposta(
            checklist, item, entidade_tipo, entidade_id, resposta_bruta,
            valor_processado=resultado['valor_processado'], origem='bot',
        )
        sessao_service.avancar(sessao)
        return JsonResponse(contrato.payload_validar(
            resposta_correta=True, resposta_sem_erro_api=True, retorno_erro_api='',
            needs_reception=False, is_a_client=sessao.is_cliente_ativo,
            cancelado=False, message=item.mensagem_sucesso or '',
        ))

    # Resposta invalida.
    sessao.tentativas_item = numero_tentativa
    sessao.save(update_fields=['tentativas_item', 'ultima_interacao_em'])

    if sessao.tentativas_item < item.max_tentativas:
        return JsonResponse(contrato.payload_validar(
            resposta_correta=False, resposta_sem_erro_api=True,
            retorno_erro_api=item.mensagem_erro or MSG_ERRO_PADRAO,
            needs_reception=False, is_a_client=sessao.is_cliente_ativo,
            cancelado=False, message='',
        ))

    # Estourou `max_tentativas`: aplica a `estrategia_erro` do item.
    estrategia = item.estrategia_erro
    if estrategia == 'transbordar':
        sessao_service.transbordar(sessao, MOTIVO_MAX_TENTATIVAS)
        return JsonResponse(contrato.payload_validar(
            resposta_correta=False, resposta_sem_erro_api=True,
            retorno_erro_api=item.mensagem_erro or MSG_ERRO_PADRAO,
            needs_reception=True, is_a_client=sessao.is_cliente_ativo,
            cancelado=False, message='',
        ))
    if estrategia == 'pular':
        entidade_tipo, entidade_id = sessao_service.entidade_da_sessao(sessao)
        checklist_service.registrar_resposta(
            checklist, item, entidade_tipo, entidade_id, '', valor_processado=None, origem='bot',
        )
        sessao_service.avancar(sessao)
        return JsonResponse(contrato.payload_validar(
            resposta_correta=True, resposta_sem_erro_api=True, retorno_erro_api='',
            needs_reception=False, is_a_client=sessao.is_cliente_ativo,
            cancelado=False, message=item.mensagem_sucesso or '',
        ))
    if estrategia == 'finalizar':
        sessao.status = 'finalizado'
        sessao.save(update_fields=['status', 'ultima_interacao_em'])
        return JsonResponse(contrato.payload_validar(
            resposta_correta=False, resposta_sem_erro_api=True,
            retorno_erro_api=item.mensagem_erro or MSG_ERRO_PADRAO,
            needs_reception=False, is_a_client=sessao.is_cliente_ativo,
            cancelado=True, message='',
        ))

    # estrategia == 'repetir' (default): sem acao de saida, so continua
    # repetindo a pergunta (nao ha branch nova pra abrir aqui).
    return JsonResponse(contrato.payload_validar(
        resposta_correta=False, resposta_sem_erro_api=True,
        retorno_erro_api=item.mensagem_erro or MSG_ERRO_PADRAO,
        needs_reception=False, is_a_client=sessao.is_cliente_ativo,
        cancelado=False, message='',
    ))


# ============================================================================
# POST /ia/recontato
# ============================================================================

@csrf_exempt
@api_token_required
def recontato(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo nao permitido'}, status=405)
    body = _parse_json(request)
    if body is None:
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    tenant = request.tenant
    cellphone = str(body.get('cellphone') or '').strip()
    lead_id = body.get('lead_id')
    pergunta_id = body.get('pergunta_id')

    checklist = sessao_service.checklist_do_tenant(tenant)
    if checklist is None:
        # Sem checklist nao ha o que reperguntar: encerra e deixa o
        # transbordo do proximo-passo cuidar de mandar pra humano.
        return JsonResponse(contrato.payload_recontato(
            pergunta_id=pergunta_id, acao=ACAO_ENCERRAR, tentativa=0,
            reperguntar=False, mensagem='', deve_transbordar=True,
        ))

    sessao = sessao_service.obter_ou_criar_sessao(tenant, cellphone, lead_id, checklist)
    item = sessao.item_atual

    sessao.tentativas_recontato += 1

    if sessao.tentativas_recontato > LIMITE_TENTATIVAS_RECONTATO:
        sessao.status = 'transbordado'
        sessao.motivo_transbordo = MOTIVO_RECONTATO_ESGOTADO
        sessao.save(update_fields=['tentativas_recontato', 'status', 'motivo_transbordo', 'ultima_interacao_em'])
        return JsonResponse(contrato.payload_recontato(
            pergunta_id=item.id if item else pergunta_id, acao=ACAO_ENCERRAR,
            tentativa=sessao.tentativas_recontato, reperguntar=False, mensagem='',
            deve_transbordar=True,
        ))

    sessao.status = 'aguardando_recontato'
    sessao.save(update_fields=['tentativas_recontato', 'status', 'ultima_interacao_em'])

    if item is not None:
        mensagem = item.mensagem_recontato or f'{MSG_RECONTATO_SEM_ITEM} {item.pergunta}'
    else:
        mensagem = MSG_RECONTATO_SEM_ITEM

    return JsonResponse(contrato.payload_recontato(
        pergunta_id=item.id if item else pergunta_id, acao=ACAO_REPERGUNTAR,
        tentativa=sessao.tentativas_recontato, reperguntar=True, mensagem=mensagem,
        deve_transbordar=False,
    ))
