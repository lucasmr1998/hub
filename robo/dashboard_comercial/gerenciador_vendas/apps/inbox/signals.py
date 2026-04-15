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


import re
import time


def _dividir_mensagem(texto):
    """Divide texto longo em multiplas mensagens (paragrafos + links separados).
    Similar ao code do N8N que quebrava respostas da IA."""
    if not texto:
        return []

    # Normalizar \n literais
    normalized = texto.replace('\\n', '\n')

    # Dividir por paragrafos (2+ quebras de linha)
    parts = re.split(r'\n{2,}', normalized)

    results = []
    url_regex = re.compile(r'(https?://\S+)')

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Extrair links
        links = url_regex.findall(part)

        # Texto sem links
        clean = url_regex.sub('', part).strip()

        if clean:
            results.append(clean)

        for link in links:
            results.append(link)

    return results if results else [texto]


def _enviar_mensagens_bot(tenant, conversa, texto, nome_bot='Hubtrix IA'):
    """Envia texto como uma ou mais mensagens do bot, dividindo por paragrafos."""
    from apps.inbox.models import Mensagem as MensagemInbox
    from apps.inbox.services import _enviar_webhook_async

    partes = _dividir_mensagem(texto)
    # Limitar a 3 mensagens para evitar spam (reagrupar excedentes na ultima)
    if len(partes) > 3:
        partes = partes[:2] + ['\n\n'.join(partes[2:])]
    ultima_msg = None

    for parte in partes:
        msg = MensagemInbox(
            tenant=tenant,
            conversa=conversa,
            remetente_tipo='bot',
            remetente_nome=nome_bot,
            tipo_conteudo='texto',
            conteudo=parte,
        )
        msg._skip_automacao = True
        msg.save()
        _enviar_webhook_async(conversa, msg)
        ultima_msg = msg
        if len(partes) > 1:
            time.sleep(0.3)  # pequeno delay entre mensagens

    if ultima_msg:
        conversa.ultima_mensagem_em = ultima_msg.data_envio
        conversa.ultima_mensagem_preview = partes[-1][:255]
        conversa.save(update_fields=['ultima_mensagem_em', 'ultima_mensagem_preview'])


def _canal_suporta_botoes(conversa):
    """Verifica se o canal da conversa suporta mensagens interativas (botões)."""
    canal = conversa.canal
    return canal and canal.provedor == 'uazapi' and canal.integracao_id


def _enviar_mensagem_interativa_bot(tenant, conversa, texto, opcoes, nome_bot='Hubtrix'):
    """Envia mensagem com botões nativos do WhatsApp via Uazapi."""
    from apps.inbox.models import Mensagem as MensagemInbox

    # Salvar mensagem no inbox (texto com opções para histórico)
    texto_completo = texto + '\n\n' + '\n'.join(f'{i+1}. {o}' for i, o in enumerate(opcoes))
    msg = MensagemInbox(
        tenant=tenant,
        conversa=conversa,
        remetente_tipo='bot',
        remetente_nome=nome_bot,
        tipo_conteudo='texto',
        conteudo=texto_completo,
    )
    msg._skip_automacao = True
    msg.save()

    # Enviar via provider com botões nativos
    canal = conversa.canal
    telefone = conversa.contato_telefone

    def _send_interativo():
        try:
            from apps.inbox.providers import get_provider
            provider = get_provider(canal)
            service = provider._service

            if len(opcoes) <= 3:
                # Botões de resposta rápida (máximo 3)
                choices = [f'{o}|{o}' for o in opcoes]
                result = service.enviar_botoes(telefone, texto, choices)
            else:
                # Lista para 4+ opções
                choices = [f'{o}|{o}|' for o in opcoes]
                result = service.enviar_lista(telefone, texto, choices, texto_botao='Ver opcoes')

            msg_id = provider.extrair_msg_id(result)
            if msg_id:
                MensagemInbox.all_tenants.filter(pk=msg.pk).update(
                    identificador_externo=msg_id
                )
        except Exception as e:
            logger.error("Erro ao enviar mensagem interativa: %s", e)
            # Fallback: envia como texto normal
            try:
                from apps.inbox.providers import get_provider
                provider = get_provider(canal)
                provider.enviar_texto(telefone, texto_completo)
            except Exception:
                pass

    import threading
    thread = threading.Thread(target=_send_interativo, daemon=True)
    thread.start()

    conversa.ultima_mensagem_em = msg.data_envio
    conversa.ultima_mensagem_preview = texto_completo[:255]
    conversa.save(update_fields=['ultima_mensagem_em', 'ultima_mensagem_preview'])


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
                # Resetar recontato se lead respondeu
                if ativo.recontato_tentativas > 0:
                    ativo.recontato_tentativas = 0
                    ativo.recontato_proximo_em = None
                    ativo.save(update_fields=['recontato_tentativas', 'recontato_proximo_em'])

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
                    # Marcar conversa como atendida pelo bot
                    conversa.modo_atendimento = 'bot'
                    conversa.save(update_fields=['modo_atendimento'])

            # Enviar resposta do bot de volta no inbox
            if resultado and resultado.get('tipo') == 'questao':
                questao = resultado.get('questao', {})
                texto = questao.get('titulo', '')
                opcoes = questao.get('opcoes_resposta', [])
                if opcoes and _canal_suporta_botoes(conversa):
                    _enviar_mensagem_interativa_bot(instance.tenant, conversa, texto, opcoes)
                elif opcoes:
                    texto += '\n\n' + '\n'.join(f'{i+1}. {o}' for i, o in enumerate(opcoes))
                    if texto:
                        _enviar_mensagens_bot(instance.tenant, conversa, texto, 'Hubtrix')
                elif texto:
                    _enviar_mensagens_bot(instance.tenant, conversa, texto, 'Hubtrix')

            elif resultado and resultado.get('tipo') in ('ia_respondedor', 'ia_agente'):
                texto = resultado.get('mensagem', '')
                if texto:
                    _enviar_mensagens_bot(instance.tenant, conversa, texto, 'Hubtrix IA')

            elif resultado and resultado.get('tipo') == 'finalizado':
                msg_final = resultado.get('mensagem', 'Atendimento finalizado. Obrigado!')
                _enviar_mensagens_bot(instance.tenant, conversa, msg_final, 'Hubtrix')
                # Marcar conversa como finalizada pelo bot
                conversa.modo_atendimento = 'finalizado_bot'
                conversa.save(update_fields=['modo_atendimento'])

            elif resultado and resultado.get('tipo') == 'transferido':
                texto = resultado.get('mensagem', '')
                if texto:
                    _enviar_mensagens_bot(instance.tenant, conversa, texto, 'Hubtrix')
                # modo_atendimento ja foi setado no engine como 'humano'

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
