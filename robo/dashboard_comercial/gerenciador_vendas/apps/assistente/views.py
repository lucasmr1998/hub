"""
Views do Assistente CRM.
Webhook para receber mensagens do WhatsApp e responder via Uazapi.
"""
import json
import logging
import threading

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.sistema.models import PerfilUsuario

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def webhook_assistente(request, api_token):
    """
    Webhook que recebe mensagens do WhatsApp (Uazapi) para o assistente.
    Identifica o usuario pelo telefone e processa via engine.
    """
    from apps.integracoes.models import IntegracaoAPI

    # Identificar integracao pelo token
    integracao_whatsapp = IntegracaoAPI.all_tenants.filter(
        api_token=api_token, ativa=True,
    ).first()

    if not integracao_whatsapp:
        return JsonResponse({'error': 'Token invalido'}, status=401)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    # Extrair dados da mensagem (formato Uazapi)
    mensagem_texto = _extrair_mensagem(body)
    telefone = _extrair_telefone(body)

    if not mensagem_texto or not telefone:
        return JsonResponse({'ok': True, 'ignored': True})

    # Identificar usuario pelo telefone
    perfil = PerfilUsuario.objects.filter(
        telefone=telefone,
        user__is_active=True,
    ).select_related('user', 'tenant').first()

    if not perfil:
        # Tentar com formato diferente de telefone
        telefone_limpo = telefone.replace('+', '').replace('-', '').replace(' ', '')
        perfil = PerfilUsuario.objects.filter(
            user__is_active=True,
        ).select_related('user', 'tenant').extra(
            where=["REPLACE(REPLACE(REPLACE(telefone, '+', ''), '-', ''), ' ', '') = %s"],
            params=[telefone_limpo],
        ).first()

    if not perfil:
        _responder_acesso_restrito(integracao_whatsapp, telefone)
        return JsonResponse({'ok': True, 'access': 'denied'})

    usuario = perfil.user
    tenant = perfil.tenant

    # Processar em background para nao travar o webhook
    thread = threading.Thread(
        target=_processar_e_responder,
        args=(usuario, tenant, mensagem_texto, telefone, integracao_whatsapp),
        daemon=True,
    )
    thread.start()

    return JsonResponse({'ok': True, 'user': usuario.username})


def _extrair_mensagem(body):
    """Extrai texto da mensagem do payload Uazapi."""
    # Formato Uazapi
    if 'message' in body:
        msg = body['message']
        if isinstance(msg, dict):
            return msg.get('conversation') or msg.get('extendedTextMessage', {}).get('text', '')
        return str(msg) if msg else ''

    # Formato alternativo
    return body.get('text', '') or body.get('body', '')


def _extrair_telefone(body):
    """Extrai telefone do remetente do payload Uazapi."""
    # Formato Uazapi
    key = body.get('key', {})
    remote = key.get('remoteJid', '') or body.get('from', '') or body.get('number', '')
    # Remover @s.whatsapp.net
    telefone = remote.split('@')[0]
    return telefone


def _processar_e_responder(usuario, tenant, mensagem_texto, telefone, integracao_whatsapp):
    """Processa a mensagem e envia resposta (roda em thread)."""
    from apps.sistema.middleware import set_current_tenant
    set_current_tenant(tenant)

    try:
        from .engine import processar_mensagem

        # Buscar integracao de IA
        integracao_ia = None
        from apps.integracoes.models import IntegracaoAPI
        integracao_ia = IntegracaoAPI.all_tenants.filter(
            tenant=tenant,
            tipo__in=['openai', 'anthropic', 'groq'],
            ativa=True,
        ).first()

        resposta = processar_mensagem(usuario, tenant, mensagem_texto, integracao_ia)

        # Enviar resposta via WhatsApp
        _enviar_resposta(integracao_whatsapp, telefone, resposta)

    except Exception as e:
        logger.error(f'[Assistente] Erro ao processar: {e}', exc_info=True)
        _enviar_resposta(integracao_whatsapp, telefone, 'Desculpe, ocorreu um erro. Tente novamente.')


def _enviar_resposta(integracao, telefone, texto):
    """Envia mensagem via Uazapi."""
    try:
        from apps.integracoes.services.uazapi import UazapiService
        service = UazapiService(integracao)
        service.enviar_texto(telefone, texto)
    except Exception as e:
        logger.error(f'[Assistente] Erro ao enviar resposta: {e}')


def _responder_acesso_restrito(integracao, telefone):
    """Responde que o acesso e restrito."""
    _enviar_resposta(
        integracao, telefone,
        'Este numero e de uso exclusivo para usuarios do sistema Hubtrix. '
        'Se voce e um usuario, peca ao administrador para cadastrar seu telefone no perfil.'
    )
