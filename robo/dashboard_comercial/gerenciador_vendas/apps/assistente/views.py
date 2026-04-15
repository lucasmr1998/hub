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

    # Debug: logar body recebido
    import sys
    print(f'[Assistente] WEBHOOK keys={list(body.keys())}', flush=True)
    msg_raw = body.get('message', {})
    chat_raw = body.get('chat', {})
    print(f'[Assistente] message={json.dumps(msg_raw, default=str)[:800]}', flush=True)
    print(f'[Assistente] chat_id={chat_raw.get("id","")} chat_name={chat_raw.get("name","")} chat_phone={chat_raw.get("phone","")}', flush=True)

    # Ignorar mensagens enviadas por nos
    key = body.get('key', {})
    if key.get('fromMe', False):
        return JsonResponse({'ok': True, 'ignored': 'fromMe'})

    mensagem_texto = _extrair_mensagem(body)
    telefone = _extrair_telefone(body)

    print(f'[Assistente] msg="{mensagem_texto}" tel="{telefone}"', flush=True)

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
    """Processa via Inbox + engine de fluxo de atendimento.
    1. Salva mensagem no Inbox
    2. Busca/cria AtendimentoFluxo (sem lead)
    3. Chama engine de fluxo (classificador, agente, respondedor)
    4. Envia resposta via WhatsApp
    """
    from apps.sistema.middleware import set_current_tenant
    from apps.inbox.models import Conversa, Mensagem, CanalInbox
    from apps.comercial.atendimento.models import AtendimentoFluxo, FluxoAtendimento

    tenant_aurora = integracao_whatsapp.tenant
    set_current_tenant(tenant_aurora)

    try:
        import sys
        print(f'[Assistente] INICIO user={usuario.username}, tenant={tenant.nome}, msg="{mensagem_texto[:50]}"', flush=True)
        logger.info(f'[Assistente] user={usuario.username}, tenant={tenant.nome}, msg="{mensagem_texto[:50]}"')

        # ── 1. Buscar/criar conversa no Inbox ──
        conversa = Conversa.all_tenants.filter(
            tenant=tenant_aurora, contato_telefone=telefone,
            modo_atendimento='assistente', status__in=['aberta', 'pendente'],
        ).first()

        if not conversa:
            canal = CanalInbox.all_tenants.filter(
                tenant=tenant_aurora, tipo='whatsapp',
                provedor='uazapi', identificador_canal='assistente',
            ).first()

            if not canal:
                # Tentar canal existente sem identificador
                canal = CanalInbox.all_tenants.filter(
                    tenant=tenant_aurora, tipo='whatsapp',
                    integracao=integracao_whatsapp,
                ).first()

            if not canal:
                canal = CanalInbox.all_tenants.create(
                    tenant=tenant_aurora, nome='Assistente CRM',
                    tipo='whatsapp', provedor='uazapi',
                    identificador_canal='assistente',
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

        # ── 2. Salvar mensagem do usuario ──
        msg_user = Mensagem(
            tenant=tenant_aurora, conversa=conversa,
            remetente_tipo='contato',
            remetente_nome=usuario.get_full_name() or usuario.username,
            tipo_conteudo='texto', conteudo=mensagem_texto,
        )
        msg_user._skip_automacao = True
        msg_user.save()

        # ── 3. Buscar fluxo de atendimento ──
        canal = conversa.canal
        fluxo = canal.fluxo if canal and canal.fluxo_id else None
        print(f'[Assistente] canal={canal} canal.fluxo_id={canal.fluxo_id if canal else None}', flush=True)
        if not fluxo:
            fluxo = FluxoAtendimento.all_tenants.filter(
                tenant=tenant_aurora, ativo=True, status='ativo',
                nome__icontains='assistente',
                nodos__tipo='entrada',
            ).first()
        print(f'[Assistente] fluxo={fluxo} (pk={fluxo.pk if fluxo else None})', flush=True)

        # ── 4. Processar via engine de fluxo ──
        resposta = None

        if fluxo:
            set_current_tenant(tenant)
            resposta = _processar_via_fluxo(
                usuario, tenant, tenant_aurora, mensagem_texto,
                telefone, conversa, fluxo,
            )
            print(f'[Assistente] resposta_fluxo={resposta[:80] if resposta else None}', flush=True)
            set_current_tenant(tenant_aurora)

        # Fallback: engine standalone (se nao tem fluxo configurado)
        if not resposta:
            print(f'[Assistente] FALLBACK para engine standalone', flush=True)
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

        if not resposta:
            resposta = 'Desculpe, nao consegui processar sua mensagem.'

        # ── 5. Salvar resposta no Inbox ──
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

        # ── 6. Enviar via WhatsApp ──
        _enviar_resposta(integracao_whatsapp, telefone, resposta)
        logger.info(f'[Assistente] Enviado para {telefone}')

    except Exception as e:
        import traceback
        print(f'[Assistente] ERRO: {e}', flush=True)
        traceback.print_exc()
        logger.error(f'[Assistente] Erro: {e}', exc_info=True)
        _enviar_resposta(integracao_whatsapp, telefone, 'Desculpe, ocorreu um erro. Tente novamente.')


def _processar_via_fluxo(usuario, tenant, tenant_aurora, mensagem_texto, telefone, conversa, fluxo):
    """Processa mensagem usando o engine de fluxo de atendimento.
    Retorna texto da resposta ou None se falhar."""
    from apps.comercial.atendimento.models import AtendimentoFluxo
    from apps.comercial.atendimento.engine import (
        iniciar_fluxo_visual, processar_resposta_ia_agente,
        processar_resposta_ia_respondedor, processar_resposta_visual,
    )

    try:
        # Buscar atendimento ativo para esta conversa
        ativo = AtendimentoFluxo.all_tenants.filter(
            tenant=tenant_aurora, fluxo=fluxo,
            status__in=['iniciado', 'em_andamento'],
            dados_respostas__contains={'_conversa_id': conversa.id},
        ).select_related('nodo_atual').first()

        resultado = None

        if ativo:
            # ── Continuar atendimento existente ──
            ativo._assistente_usuario = usuario
            ativo._assistente_tenant = tenant

            dados = ativo.dados_respostas or {}
            dados['_ultima_mensagem'] = mensagem_texto
            ativo.dados_respostas = dados
            ativo.save(update_fields=['dados_respostas'])

            if ativo.nodo_atual and ativo.nodo_atual.tipo == 'ia_respondedor':
                resultado = processar_resposta_ia_respondedor(ativo, mensagem_texto)
            elif ativo.nodo_atual and ativo.nodo_atual.tipo == 'ia_agente':
                resultado = processar_resposta_ia_agente(ativo, mensagem_texto)
            elif ativo.nodo_atual and ativo.nodo_atual.tipo == 'questao':
                resultado = processar_resposta_visual(ativo, mensagem_texto)
            else:
                logger.warning(f'[Assistente] Atendimento {ativo.id} em nodo inesperado: {ativo.nodo_atual}')
                return None
        else:
            # ── Iniciar novo atendimento ──
            total_q = fluxo.nodos.filter(tipo='questao').count()
            atendimento = AtendimentoFluxo(
                tenant=tenant_aurora,
                fluxo=fluxo,
                total_questoes=total_q,
                max_tentativas=fluxo.max_tentativas,
                dados_respostas={
                    '_ultima_mensagem': mensagem_texto,
                    '_telefone': telefone,
                    '_assistente_usuario_id': usuario.id,
                    '_assistente_tenant_id': tenant.id,
                    '_conversa_id': conversa.id,
                },
            )
            atendimento._assistente_usuario = usuario
            atendimento._assistente_tenant = tenant
            atendimento.save()

            resultado = iniciar_fluxo_visual(atendimento)

        # ── Extrair texto da resposta ──
        if not resultado:
            return None

        tipo = resultado.get('tipo', '')
        if tipo in ('ia_agente', 'ia_respondedor'):
            return resultado.get('mensagem', '')
        elif tipo == 'questao':
            questao = resultado.get('questao', {})
            return questao.get('titulo', '') or resultado.get('mensagem', '')
        elif tipo == 'finalizado':
            return resultado.get('mensagem', 'Atendimento finalizado.')
        elif tipo == 'transferido':
            return resultado.get('mensagem', '')
        else:
            return resultado.get('mensagem', '')

    except Exception as e:
        logger.error(f'[Assistente] Erro no fluxo: {e}', exc_info=True)
        return None


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
