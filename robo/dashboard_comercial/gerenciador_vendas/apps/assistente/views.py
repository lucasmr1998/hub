"""
Views do Assistente CRM.
Webhook recebe mensagens WhatsApp, cria Conversa no Inbox,
processa via engine (ia_agente com tools CRM) ou engine proprio como fallback.
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
    Identifica usuario, cria Conversa no Inbox, processa via fluxo.
    """
    from apps.integracoes.models import IntegracaoAPI
    from .models import ConfiguracaoAssistenteGlobal, ConfiguracaoAssistenteTenant

    config_global = ConfiguracaoAssistenteGlobal.get_config()
    if not config_global.ativo:
        return JsonResponse({'error': 'Assistente desativado'}, status=403)

    integracao_whatsapp = IntegracaoAPI.all_tenants.filter(
        api_token=api_token, ativa=True,
    ).first()

    if not integracao_whatsapp:
        return JsonResponse({'error': 'Token invalido'}, status=401)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    # Ignorar mensagens enviadas por nos
    key = body.get('key', {})
    if key.get('fromMe', False):
        return JsonResponse({'ok': True, 'ignored': 'fromMe'})

    mensagem_texto = _extrair_mensagem(body)
    telefone = _extrair_telefone(body)

    if not mensagem_texto or not telefone:
        return JsonResponse({'ok': True, 'ignored': True})

    perfil = _identificar_usuario(telefone)

    if not perfil:
        _enviar_resposta(integracao_whatsapp, telefone, config_global.mensagem_acesso_restrito)
        return JsonResponse({'ok': True, 'access': 'denied'})

    usuario = perfil.user
    tenant = perfil.tenant

    config_tenant = ConfiguracaoAssistenteTenant.get_config(tenant)
    if not config_tenant.ativo:
        _enviar_resposta(integracao_whatsapp, telefone, 'Assistente nao ativado para sua empresa.')
        return JsonResponse({'ok': True, 'access': 'tenant_disabled'})

    thread = threading.Thread(
        target=_processar_via_inbox,
        args=(usuario, tenant, mensagem_texto, telefone, integracao_whatsapp, config_tenant),
        daemon=True,
    )
    thread.start()

    return JsonResponse({'ok': True, 'user': usuario.username})


def _identificar_usuario(telefone):
    """Identifica usuario pelo telefone."""
    perfil = PerfilUsuario.objects.filter(
        telefone=telefone, user__is_active=True,
    ).select_related('user', 'tenant').first()

    if not perfil:
        telefone_limpo = telefone.replace('+', '').replace('-', '').replace(' ', '')
        perfil = PerfilUsuario.objects.filter(
            user__is_active=True,
        ).select_related('user', 'tenant').extra(
            where=["REPLACE(REPLACE(REPLACE(telefone, '+', ''), '-', ''), ' ', '') = %s"],
            params=[telefone_limpo],
        ).first()

    return perfil


def _processar_via_inbox(usuario, tenant, mensagem_texto, telefone, integracao_whatsapp, config_tenant):
    """Processa via Inbox: cria conversa, salva mensagens, chama engine, responde."""
    from apps.sistema.middleware import set_current_tenant
    from apps.sistema.models import Tenant
    from apps.inbox.models import Conversa, Mensagem, CanalInbox

    tenant_aurora = Tenant.objects.get(pk=3)
    set_current_tenant(tenant_aurora)

    try:
        logger.info(f'[Assistente] user={usuario.username}, tenant={tenant.nome}, msg="{mensagem_texto[:50]}"')

        # Buscar/criar conversa
        conversa = Conversa.all_tenants.filter(
            tenant=tenant_aurora, contato_telefone=telefone,
            modo_atendimento='assistente', status__in=['aberta', 'pendente'],
        ).first()

        if not conversa:
            canal = CanalInbox.all_tenants.filter(
                tenant=tenant_aurora, tipo='whatsapp',
            ).first()

            if not canal:
                canal = CanalInbox.all_tenants.create(
                    tenant=tenant_aurora, nome='Assistente CRM',
                    tipo='whatsapp', provedor='uazapi',
                    integracao=integracao_whatsapp, ativo=True,
                )

            ultimo_numero = Conversa.all_tenants.filter(tenant=tenant_aurora).count() + 1
            conversa = Conversa(
                tenant=tenant_aurora, numero=ultimo_numero, canal=canal,
                contato_nome=usuario.get_full_name() or usuario.username,
                contato_telefone=telefone, status='aberta',
                modo_atendimento='assistente',
            )
            conversa._skip_automacao = True
            conversa.save()

        # Salvar mensagem do usuario
        msg_user = Mensagem(
            tenant=tenant_aurora, conversa=conversa,
            remetente_tipo='contato',
            remetente_nome=usuario.get_full_name() or usuario.username,
            tipo_conteudo='texto', conteudo=mensagem_texto,
        )
        msg_user._skip_automacao = True
        msg_user.save()

        # Chamar engine do assistente (com tenant do vendedor para as tools)
        set_current_tenant(tenant)
        from .engine import processar_mensagem
        integracao_ia = config_tenant.integracao_ia
        if not integracao_ia:
            from apps.integracoes.models import IntegracaoAPI
            integracao_ia = IntegracaoAPI.all_tenants.filter(
                tenant=tenant, tipo__in=['openai', 'anthropic', 'groq'], ativa=True,
            ).first()

        resposta = processar_mensagem(usuario, tenant, mensagem_texto, integracao_ia)
        set_current_tenant(tenant_aurora)

        # Salvar resposta no Inbox
        msg_resp = Mensagem(
            tenant=tenant_aurora, conversa=conversa,
            remetente_tipo='bot', remetente_nome='Hubtrix IA',
            tipo_conteudo='texto', conteudo=resposta,
        )
        msg_resp._skip_automacao = True
        msg_resp.save()

        conversa.ultima_mensagem_em = msg_resp.data_envio
        conversa.ultima_mensagem_preview = resposta[:255]
        conversa.save(update_fields=['ultima_mensagem_em', 'ultima_mensagem_preview'])

        # Enviar via WhatsApp
        _enviar_resposta(integracao_whatsapp, telefone, resposta)
        logger.info(f'[Assistente] Enviado para {telefone}')

    except Exception as e:
        logger.error(f'[Assistente] Erro: {e}', exc_info=True)
        _enviar_resposta(integracao_whatsapp, telefone, 'Desculpe, ocorreu um erro. Tente novamente.')


def _extrair_mensagem(body):
    if 'message' in body:
        msg = body['message']
        if isinstance(msg, dict):
            return msg.get('conversation') or msg.get('extendedTextMessage', {}).get('text', '')
        return str(msg) if msg else ''
    return body.get('text', '') or body.get('body', '')


def _extrair_telefone(body):
    key = body.get('key', {})
    remote = key.get('remoteJid', '') or body.get('from', '') or body.get('number', '')
    return remote.split('@')[0]


def _enviar_resposta(integracao, telefone, texto):
    try:
        from apps.integracoes.services.uazapi import UazapiService
        service = UazapiService(integracao)
        service.enviar_texto(telefone, texto)
    except Exception as e:
        logger.error(f'[Assistente] Erro ao enviar: {e}')
