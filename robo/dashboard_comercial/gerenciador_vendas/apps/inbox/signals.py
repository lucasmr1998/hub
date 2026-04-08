"""
Signals do Inbox para integração com o engine de automações.

Dispara eventos quando:
- Nova conversa é criada
- Mensagem de contato é recebida
- Conversa é resolvida
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='inbox.Conversa')
def on_conversa_criada(sender, instance, created, **kwargs):
    """Dispara evento 'conversa_aberta' quando nova conversa é criada."""
    if not created:
        return

    if getattr(instance, '_skip_automacao', False):
        return

    try:
        from apps.marketing.automacoes.engine import disparar_evento

        contexto = {
            'conversa': instance,
            'lead': instance.lead,
            'telefone': instance.contato_telefone,
            'nome': instance.contato_nome,
            'canal': instance.canal.tipo if instance.canal_id else '',
        }

        if instance.lead:
            contexto.update({
                'lead_nome': instance.lead.nome_razaosocial,
                'lead_telefone': instance.lead.telefone,
                'lead_email': instance.lead.email or '',
            })

        disparar_evento('conversa_aberta', contexto, tenant=instance.tenant)
    except Exception as e:
        logger.error("Erro ao disparar automação conversa_aberta: %s", e)


@receiver(post_save, sender='inbox.Mensagem')
def on_mensagem_recebida(sender, instance, created, **kwargs):
    """Dispara evento 'mensagem_recebida' para mensagens de contato."""
    if not created:
        return

    if instance.remetente_tipo != 'contato':
        return

    if getattr(instance, '_skip_automacao', False):
        return

    try:
        from apps.marketing.automacoes.engine import disparar_evento

        conversa = instance.conversa
        contexto = {
            'conversa': conversa,
            'mensagem': instance,
            'lead': conversa.lead,
            'telefone': conversa.contato_telefone,
            'nome': conversa.contato_nome,
            'conteudo': instance.conteudo[:200],
            'canal': conversa.canal.tipo if conversa.canal_id else '',
        }

        if conversa.lead:
            contexto.update({
                'lead_nome': conversa.lead.nome_razaosocial,
                'lead_telefone': conversa.lead.telefone,
                'lead_email': conversa.lead.email or '',
            })

        disparar_evento('mensagem_recebida', contexto, tenant=instance.tenant)
    except Exception as e:
        logger.error("Erro ao disparar automação mensagem_recebida: %s", e)

    # Encaminhar para webhook N8N do tenant (se configurado)
    try:
        from apps.integracoes.models import IntegracaoAPI
        conversa = instance.conversa

        integracao_n8n = IntegracaoAPI.all_tenants.filter(
            tenant=instance.tenant,
            tipo='n8n',
            ativa=True,
        ).first()

        if integracao_n8n and integracao_n8n.base_url:
            import requests
            import threading

            # Se a mensagem veio do Uazapi, repassar o payload original completo
            metadata = instance.metadata or {}
            uazapi_raw = metadata.get('uazapi_raw', {})

            if uazapi_raw:
                # Repassar o body original do Uazapi + dados extras do nosso sistema
                payload = uazapi_raw.copy()
                payload['_aurora'] = {
                    'conversa_id': conversa.pk,
                    'mensagem_id': instance.pk,
                    'tenant': instance.tenant.nome if instance.tenant else '',
                }
                if conversa.lead:
                    payload['_aurora']['lead_id'] = conversa.lead.pk
                    payload['_aurora']['lead_nome'] = conversa.lead.nome_razaosocial
                    payload['_aurora']['lead_email'] = conversa.lead.email or ''
                if conversa.oportunidade_id:
                    payload['_aurora']['oportunidade_id'] = conversa.oportunidade_id
                elif conversa.lead:
                    # Buscar oportunidade ativa do lead
                    from apps.comercial.crm.models import OportunidadeVenda
                    op = OportunidadeVenda.objects.filter(
                        lead=conversa.lead, ativo=True
                    ).order_by('-data_criacao').first()
                    if op:
                        payload['_aurora']['oportunidade_id'] = op.pk
            else:
                # Payload padrao para mensagens que nao vieram do Uazapi
                payload = {
                    'data': {
                        'remoteJid': conversa.contato_telefone,
                        'fromMe': False,
                        'text': instance.conteudo,
                        'messageType': {'texto': 'Conversation', 'imagem': 'ImageMessage', 'audio': 'AudioMessage', 'video': 'videoMessage', 'arquivo': 'DocumentMessage'}.get(instance.tipo_conteudo, 'Conversation'),
                        'mediaUrl': instance.arquivo_url or None,
                        'id': str(instance.pk),
                        'source': 'aurora',
                        'caption': None,
                        'reactionMessage': None,
                    },
                    'session_id': f'sessionid_{conversa.contato_telefone}',
                    'conversa_id': conversa.pk,
                    'tenant': instance.tenant.nome if instance.tenant else '',
                }
                if conversa.lead:
                    payload['lead_id'] = conversa.lead.pk
                    payload['lead_nome'] = conversa.lead.nome_razaosocial
                    payload['lead_email'] = conversa.lead.email or ''
                if conversa.oportunidade_id:
                    payload['oportunidade_id'] = conversa.oportunidade_id
                elif conversa.lead:
                    from apps.comercial.crm.models import OportunidadeVenda
                    op = OportunidadeVenda.objects.filter(
                        lead=conversa.lead, ativo=True
                    ).order_by('-data_criacao').first()
                    if op:
                        payload['oportunidade_id'] = op.pk

            def _enviar():
                try:
                    headers = {'Content-Type': 'application/json'}
                    token = integracao_n8n.access_token or ''
                    if token:
                        headers['Authorization'] = f'Bearer {token}'
                    resp = requests.post(integracao_n8n.base_url, json=payload, headers=headers, timeout=10)
                    logger.info("Mensagem encaminhada para N8N: tenant=%s, status=%s", instance.tenant, resp.status_code)
                except Exception as ex:
                    logger.error("Erro ao encaminhar para N8N: %s", ex)

            threading.Thread(target=_enviar, daemon=True).start()

    except Exception as e:
        logger.error("Erro ao encaminhar para N8N: %s", e)

    # Disparar fluxo de atendimento por canal (se houver fluxo ativo)
    try:
        conversa = instance.conversa
        lead = conversa.lead
        canal = conversa.canal.tipo if conversa.canal_id else ''

        # Se conversa nao tem lead (widget sem dados), criar lead minimo
        if not lead and canal:
            from apps.comercial.leads.models import LeadProspecto
            nome = conversa.contato_nome or 'Visitante'
            lead = LeadProspecto(
                tenant=instance.tenant,
                nome_razaosocial=nome,
                telefone=conversa.contato_telefone or '',
                email=conversa.contato_email or '',
                origem='widget' if canal == 'widget' else 'outros',
                canal_entrada=canal,
                status_api='pendente',
            )
            lead._skip_automacao = True
            lead._skip_segmento = True
            lead.save()
            conversa.lead = lead
            conversa.save(update_fields=['lead'])
            logger.info("Lead criado automaticamente para conversa widget: %s", lead.nome_razaosocial)

        if lead and canal:
            from apps.comercial.atendimento.engine import iniciar_por_canal, processar_resposta_visual
            from apps.comercial.atendimento.models import AtendimentoFluxo

            # Verificar se ja tem atendimento ativo aguardando resposta
            ativo = AtendimentoFluxo.objects.filter(
                lead=lead, fluxo__modo_fluxo=True,
                status__in=['iniciado', 'em_andamento'],
                nodo_atual__tipo__in=['questao', 'ia_respondedor', 'ia_agente'],
            ).select_related('fluxo', 'nodo_atual').first()

            if ativo:
                # Dispatch para o handler correto baseado no tipo do nodo
                if ativo.nodo_atual and ativo.nodo_atual.tipo == 'ia_respondedor':
                    from apps.comercial.atendimento.engine import processar_resposta_ia_respondedor
                    resultado = processar_resposta_ia_respondedor(ativo, instance.conteudo)
                elif ativo.nodo_atual and ativo.nodo_atual.tipo == 'ia_agente':
                    from apps.comercial.atendimento.engine import processar_resposta_ia_agente
                    resultado = processar_resposta_ia_agente(ativo, instance.conteudo)
                else:
                    resultado = processar_resposta_visual(ativo, instance.conteudo)
                logger.info("Resposta processada no fluxo: atendimento=%s, resultado=%s", ativo.id, resultado.get('tipo') if resultado else 'None')
            else:
                # Tentar iniciar novo fluxo (prioriza fluxo vinculado ao canal)
                canal_inbox = conversa.canal if conversa.canal_id else None
                fluxo_do_canal = canal_inbox.fluxo if canal_inbox and canal_inbox.fluxo_id else None
                atendimento, resultado = iniciar_por_canal(lead, canal, tenant=instance.tenant, fluxo_forcado=fluxo_do_canal)
                if atendimento:
                    logger.info("Fluxo atendimento iniciado: atendimento=%s, canal=%s", atendimento.id, canal)

            # Enviar resposta do bot de volta no inbox
            if resultado and resultado.get('tipo') == 'questao':
                questao = resultado.get('questao', {})
                texto = questao.get('titulo', '')
                opcoes = questao.get('opcoes_resposta', [])
                if opcoes:
                    texto += '\n\n' + '\n'.join(f'{i+1}. {o}' for i, o in enumerate(opcoes))

                if texto:
                    from apps.inbox.models import Mensagem as MensagemInbox
                    msg = MensagemInbox(
                        tenant=instance.tenant,
                        conversa=conversa,
                        remetente_tipo='bot',
                        remetente_nome='Aurora',
                        tipo_conteudo='texto',
                        conteudo=texto,
                    )
                    msg._skip_automacao = True
                    msg.save()

                    conversa.ultima_mensagem_em = msg.data_envio
                    conversa.ultima_mensagem_preview = texto[:255]
                    conversa.save(update_fields=['ultima_mensagem_em', 'ultima_mensagem_preview'])

                    # Enviar via webhook externo (WhatsApp)
                    from apps.inbox.services import _enviar_webhook_async
                    _enviar_webhook_async(conversa, msg)

            elif resultado and resultado.get('tipo') in ('ia_respondedor', 'ia_agente'):
                texto = resultado.get('mensagem', '')
                if texto:
                    from apps.inbox.models import Mensagem as MensagemInbox
                    msg = MensagemInbox(
                        tenant=instance.tenant,
                        conversa=conversa,
                        remetente_tipo='bot',
                        remetente_nome='Aurora IA',
                        tipo_conteudo='texto',
                        conteudo=texto,
                    )
                    msg._skip_automacao = True
                    msg.save()

                    conversa.ultima_mensagem_em = msg.data_envio
                    conversa.ultima_mensagem_preview = texto[:255]
                    conversa.save(update_fields=['ultima_mensagem_em', 'ultima_mensagem_preview'])

                    from apps.inbox.services import _enviar_webhook_async
                    _enviar_webhook_async(conversa, msg)

            elif resultado and resultado.get('tipo') == 'finalizado':
                from apps.inbox.models import Mensagem as MensagemInbox
                msg_final = resultado.get('mensagem', 'Atendimento finalizado. Obrigado!')
                msg = MensagemInbox(
                    tenant=instance.tenant,
                    conversa=conversa,
                    remetente_tipo='bot',
                    remetente_nome='Aurora',
                    tipo_conteudo='texto',
                    conteudo=msg_final,
                )
                msg._skip_automacao = True
                msg.save()
                from apps.inbox.services import _enviar_webhook_async
                _enviar_webhook_async(conversa, msg)

    except Exception as e:
        logger.error("Erro ao processar fluxo de atendimento por canal: %s", e, exc_info=True)


@receiver(post_save, sender='inbox.Conversa')
def on_conversa_resolvida(sender, instance, created, **kwargs):
    """Dispara evento 'conversa_resolvida' quando conversa muda para resolvida."""
    if created:
        return

    if instance.status != 'resolvida':
        return

    if getattr(instance, '_skip_automacao', False):
        return

    try:
        from apps.marketing.automacoes.engine import disparar_evento

        contexto = {
            'conversa': instance,
            'lead': instance.lead,
            'telefone': instance.contato_telefone,
            'nome': instance.contato_nome,
        }

        if instance.lead:
            contexto.update({
                'lead_nome': instance.lead.nome_razaosocial,
                'lead_telefone': instance.lead.telefone,
            })

        disparar_evento('conversa_resolvida', contexto, tenant=instance.tenant)
    except Exception as e:
        logger.error("Erro ao disparar automação conversa_resolvida: %s", e)
