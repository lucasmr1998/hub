# ============================================================================
# Views migradas de vendas_web.views (Phase 3C)
# ============================================================================
import json
import logging
import traceback
from datetime import datetime

import requests
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages

from apps.notificacoes.models import (
    TipoNotificacao,
    CanalNotificacao,
    PreferenciaNotificacao,
    Notificacao,
    TemplateNotificacao,
)

logger = logging.getLogger(__name__)


# ============================================================================
# VIEWS DE PÁGINA
# ============================================================================

@login_required
def minhas_notificacoes_view(request):
    """Pagina que lista as notificacoes do usuario logado."""
    from django.core.paginator import Paginator

    qs = Notificacao.objects.filter(
        tenant=request.tenant,
        destinatario=request.user,
    ).select_related('tipo', 'canal').order_by('-data_criacao')

    filtro = request.GET.get('filtro', 'todas')
    if filtro == 'nao_lidas':
        qs = qs.filter(lida=False)
    elif filtro == 'lidas':
        qs = qs.filter(lida=True)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    total_nao_lidas = Notificacao.objects.filter(
        tenant=request.tenant, destinatario=request.user, lida=False
    ).count()

    # Preserva filtro no link de paginacao
    query = f'filtro={filtro}' if filtro != 'todas' else ''

    context = {
        'notificacoes': page_obj.object_list,
        'page_obj': page_obj,
        'query': query,
        'filtro_atual': filtro,
        'total_nao_lidas': total_nao_lidas,
        'total_exibidas': paginator.count,
    }
    return render(request, 'notificacoes/minhas_notificacoes.html', context)


@login_required
def configuracoes_notificacoes_view(request):
    """View para gerenciar sistema de notificações"""
    from apps.sistema.decorators import user_tem_funcionalidade
    if not user_tem_funcionalidade(request, 'config.gerenciar_notificacoes'):
        messages.error(request, 'Você não tem permissão para acessar esta página.')
        return redirect('dashboard:dashboard1')

    tenant = request.tenant
    tipos = TipoNotificacao.objects.filter(tenant=tenant).order_by('nome')
    canais = CanalNotificacao.objects.filter(tenant=tenant).order_by('nome')

    total_enviadas = Notificacao.objects.filter(tenant=tenant, status='enviada').count()
    total_pendentes = Notificacao.objects.filter(tenant=tenant, status='pendente').count()
    total_falhas = Notificacao.objects.filter(tenant=tenant, status='falhou').count()

    context = {
        'tipos': tipos,
        'canais': canais,
        'total_enviadas': total_enviadas,
        'total_pendentes': total_pendentes,
        'total_falhas': total_falhas,
    }
    return render(request, 'notificacoes/notificacoes.html', context)


@login_required
def tipo_notificacao_detalhes_view(request, tipo_id):
    """View para detalhes e configuração de um tipo específico de notificação"""
    # Verificar se o usuário tem permissão
    from apps.sistema.decorators import user_tem_funcionalidade
    if not user_tem_funcionalidade(request, 'config.gerenciar_notificacoes'):
        messages.error(request, 'Você não tem permissão para acessar esta página.')
        return redirect('dashboard:dashboard1')

    # Buscar o tipo de notificação
    try:
        tipo = TipoNotificacao.objects.get(id=tipo_id)
    except TipoNotificacao.DoesNotExist:
        messages.error(request, 'Tipo de notificação não encontrado.')
        return redirect('notificacoes:configuracoes_notificacoes')

    # Buscar todos os canais e verificar quais têm template para este tipo
    canais = CanalNotificacao.objects.all().order_by('nome')
    canais_com_template = TemplateNotificacao.objects.filter(
        tipo_notificacao=tipo
    ).values_list('canal_id', 'id')

    # Criar dicionário de canais com template
    canais_template_map = {canal_id: template_id for canal_id, template_id in canais_com_template}

    # Adicionar informação de template aos canais
    canais_list = []
    for canal in canais:
        canal_dict = {
            'id': canal.id,
            'nome': canal.nome,
            'codigo': canal.codigo,
            'icone': canal.icone,
            'ativo': canal.ativo,
            'tem_template': canal.id in canais_template_map,
            'template_id': canais_template_map.get(canal.id)
        }
        canais_list.append(canal_dict)

    # Buscar templates para este tipo
    templates = TemplateNotificacao.objects.filter(
        tipo_notificacao=tipo
    ).select_related('canal').order_by('canal__nome')

    # Buscar preferências de usuários para este tipo
    preferencias = PreferenciaNotificacao.objects.filter(
        tipo_notificacao=tipo
    ).select_related('usuario', 'canal_preferido').order_by('usuario__username')

    # Buscar todos os usuários do tenant atual
    todos_usuarios = User.objects.filter(is_active=True, perfil__tenant=request.tenant).order_by('username')

    # Criar lista de usuários com status de preferência
    usuarios_com_status = []
    preferencias_por_usuario = {p.usuario.id: p for p in preferencias}

    for usuario in todos_usuarios:
        preferencia = preferencias_por_usuario.get(usuario.id)
        usuarios_com_status.append({
            'usuario': usuario,
            'tem_preferencia': preferencia is not None,
            'preferencia': preferencia,
            'ativo': preferencia.ativo if preferencia else False
        })

    # Buscar histórico de notificações deste tipo
    notificacoes = Notificacao.objects.filter(
        tipo=tipo
    ).select_related('canal', 'destinatario').order_by('-data_criacao')[:50]

    # Estatísticas
    templates_count = templates.count()
    preferencias_count = preferencias.filter(ativo=True).count()
    preferencias_pausados_count = preferencias.filter(ativo=False).count()
    usuarios_sem_notificacao_count = todos_usuarios.count() - preferencias.count()
    notificacoes_count = Notificacao.objects.filter(tipo=tipo, status='enviada').count()

    # Carregar configuração de webhook específica para este tipo
    webhook_config = {}
    if hasattr(tipo, 'webhook_config') and tipo.webhook_config:
        webhook_config = tipo.webhook_config
    else:
        # Fallback: usar configuração padrão
        webhook_config = {
            'url': '',
            'method': 'POST',
            'timeout': 30,
            'headers': {},
            'headers_json': '',
            'frequency': 'imediato',
            'max_retries': 3,
            'auth_type': 'none',
            'verify_ssl': True,
            'custom_payload': ''
        }

    # Carregar configuração do WhatsApp específica para este tipo
    whatsapp_config = {}
    if hasattr(tipo, 'whatsapp_config') and tipo.whatsapp_config:
        whatsapp_config = tipo.whatsapp_config
    else:
        # Fallback: usar configuração padrão
        whatsapp_config = {
            'url': 'https://automation-n8n.v4riem.easypanel.host/webhook/5a88a51b-f099-4ea9-afb5-68a10254bcdd',
            'method': 'POST',
            'timeout': 30,
            'headers': {},
            'headers_json': '',
            'frequency': 'imediato',
            'max_retries': 3,
            'message_template': '',
            'phone_format': 'e164'
        }

    # Serializar headers para JSON string
    if 'headers' in webhook_config and webhook_config['headers']:
        webhook_config['headers_json'] = json.dumps(webhook_config['headers'], indent=2)

    if 'headers' in whatsapp_config and whatsapp_config['headers']:
        whatsapp_config['headers_json'] = json.dumps(whatsapp_config['headers'], indent=2)

    context = {
        'tipo': tipo,
        'canais': canais_list,
        'templates': templates,
        'preferencias': preferencias,
        'usuarios_com_status': usuarios_com_status,
        'notificacoes': notificacoes,
        'templates_count': templates_count,
        'preferencias_count': preferencias_count,
        'preferencias_pausados_count': preferencias_pausados_count,
        'usuarios_sem_notificacao_count': usuarios_sem_notificacao_count,
        'notificacoes_count': notificacoes_count,
        'webhook_config': webhook_config,
        'whatsapp_config': whatsapp_config,
    }

    return render(request, 'notificacoes/tipo_notificacao_detalhes.html', context)


# ============================================================================
# APIs DO SISTEMA DE NOTIFICAÇÕES
# ============================================================================

@login_required
@require_http_methods(["POST"])
def api_notificacao_enviar(request):
    """API para enviar notificação via N8N"""
    try:
        data = json.loads(request.body)

        # Validar dados
        tipo_codigo = data.get('tipo')
        destinatarios_ids = data.get('destinatarios', [])
        dados_contexto = data.get('dados_contexto', {})
        prioridade = data.get('prioridade', 'normal')

        if not tipo_codigo:
            return JsonResponse({'error': 'Tipo de notificação é obrigatório'}, status=400)

        # Buscar usuários (somente do tenant atual)
        if destinatarios_ids:
            usuarios = User.objects.filter(id__in=destinatarios_ids, is_active=True, perfil__tenant=request.tenant)
        else:
            # Enviar para todos os usuários ativos do tenant atual
            usuarios = User.objects.filter(is_active=True, perfil__tenant=request.tenant)

        from apps.notificacoes.services import notificar_usuarios

        tenant = request.tenant
        notificacoes = notificar_usuarios(
            tenant=tenant,
            codigo_tipo=tipo_codigo,
            titulo=dados_contexto.get('titulo', f'Notificação: {tipo_codigo}'),
            mensagem=dados_contexto.get('mensagem', ''),
            usuarios=usuarios,
            prioridade=prioridade,
            dados_contexto=dados_contexto,
        )

        return JsonResponse({
            'success': True,
            'message': f'{len(notificacoes)} notificação(ões) criada(s).',
            'notificacoes_criadas': len(notificacoes)
        })

    except Exception as e:
        logger.error(f'Erro ao enviar notificação: {str(e)}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@login_required
def api_notificacoes_listar(request):
    """API para listar notificações do usuário"""
    try:
        usuario = request.user
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))

        notificacoes = Notificacao.objects.filter(
            destinatario=usuario
        ).order_by('-data_criacao')

        # Paginação
        start = (page - 1) * per_page
        end = start + per_page
        notificacoes_page = notificacoes[start:end]

        data = []
        for notif in notificacoes_page:
            data.append({
                'id': notif.id,
                'tipo': notif.tipo.nome,
                'tipo_codigo': notif.tipo.codigo,
                'icone': notif.tipo.icone,
                'canal': notif.canal.nome,
                'titulo': notif.titulo,
                'mensagem': notif.mensagem,
                'status': notif.status,
                'prioridade': notif.prioridade,
                'lida': notif.lida,
                'url_acao': notif.url_acao,
                'data_criacao': notif.data_criacao.isoformat(),
                'data_envio': notif.data_envio.isoformat() if notif.data_envio else None,
            })

        from apps.notificacoes.services import contar_nao_lidas
        nao_lidas = contar_nao_lidas(request.tenant, usuario)

        return JsonResponse({
            'success': True,
            'notificacoes': data,
            'total': notificacoes.count(),
            'nao_lidas': nao_lidas,
            'page': page,
            'per_page': per_page
        })

    except Exception as e:
        logger.error(f'Erro ao listar notificações: {str(e)}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@login_required
def api_notificacao_detalhes(request, notificacao_id):
    """API para obter detalhes completos de uma notificação específica"""
    try:
        # Buscar notificação (sem filtro de usuário para admins verem todas)
        notificacao = Notificacao.objects.select_related(
            'tipo', 'canal', 'destinatario'
        ).get(id=notificacao_id)

        # Montar dados completos
        data = {
            'id': notificacao.id,
            'tipo': {
                'id': notificacao.tipo.id,
                'nome': notificacao.tipo.nome,
                'codigo': notificacao.tipo.codigo,
                'icone': notificacao.tipo.icone,
            },
            'canal': {
                'id': notificacao.canal.id,
                'nome': notificacao.canal.nome,
                'codigo': notificacao.canal.codigo,
                'icone': notificacao.canal.icone  # CanalNotificacao tem o campo icone
            },
            'titulo': notificacao.titulo,
            'mensagem': notificacao.mensagem,
            'status': notificacao.status,
            'prioridade': notificacao.prioridade,
            'tentativas': notificacao.tentativas,
            'max_tentativas': notificacao.max_tentativas,
            'data_criacao': notificacao.data_criacao.isoformat(),
            'data_agendamento': notificacao.data_agendamento.isoformat() if notificacao.data_agendamento else None,
            'data_envio': notificacao.data_envio.isoformat() if notificacao.data_envio else None,
            'destinatario_email': notificacao.destinatario_email,
            'destinatario_telefone': notificacao.destinatario_telefone,
            'lida': notificacao.lida,
            'data_lida': notificacao.data_lida.isoformat() if notificacao.data_lida else None,
            'url_acao': notificacao.url_acao,
            'dados_contexto': notificacao.dados_contexto if notificacao.dados_contexto else {},
            'erro_detalhes': notificacao.erro_detalhes,
            'resposta_externa': notificacao.resposta_externa,
        }

        # Adicionar info do destinatário se existir
        if notificacao.destinatario:
            data['destinatario'] = {
                'id': notificacao.destinatario.id,
                'username': notificacao.destinatario.username,
                'email': notificacao.destinatario.email,
                'first_name': notificacao.destinatario.first_name,
                'last_name': notificacao.destinatario.last_name
            }
        else:
            data['destinatario'] = None

        return JsonResponse({
            'success': True,
            'notificacao': data
        })

    except Notificacao.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Notificação não encontrada'
        }, status=404)
    except Exception as e:
        logger.error(f'Erro ao buscar detalhes da notificação {notificacao_id}: {str(e)}')
        traceback.print_exc()  # Imprimir o traceback completo no console
        return JsonResponse({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }, status=500)


@login_required
def api_notificacoes_preferencias(request):
    """API para gerenciar preferências de notificação"""
    if request.method == 'GET':
        try:
            usuario = request.user
            preferencias = PreferenciaNotificacao.objects.filter(
                usuario=usuario
            ).select_related('tipo_notificacao', 'canal_preferido')

            data = []
            for pref in preferencias:
                data.append({
                    'id': pref.id,
                    'tipo_notificacao': {
                        'codigo': pref.tipo_notificacao.codigo,
                        'nome': pref.tipo_notificacao.nome
                    },
                    'canal_preferido': {
                        'codigo': pref.canal_preferido.codigo,
                        'nome': pref.canal_preferido.nome
                    },
                    'ativo': pref.ativo,
                    'horario_inicio': pref.horario_inicio.strftime('%H:%M'),
                    'horario_fim': pref.horario_fim.strftime('%H:%M'),
                    'dias_semana': pref.dias_semana
                })

            return JsonResponse({
                'success': True,
                'preferencias': data
            })

        except Exception as e:
            logger.error(f'Erro ao buscar preferências: {str(e)}')
            return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            usuario = request.user

            # Atualizar ou criar preferência
            preferencia, created = PreferenciaNotificacao.objects.update_or_create(
                usuario=usuario,
                tipo_notificacao_id=data['tipo_notificacao_id'],
                canal_preferido_id=data['canal_preferido_id'],
                defaults={
                    'ativo': data.get('ativo', True),
                    'horario_inicio': data.get('horario_inicio', '08:00'),
                    'horario_fim': data.get('horario_fim', '18:00'),
                    'dias_semana': data.get('dias_semana', [0, 1, 2, 3, 4, 5, 6])
                }
            )

            return JsonResponse({
                'success': True,
                'message': 'Preferência atualizada com sucesso',
                'created': created
            })

        except Exception as e:
            logger.error(f'Erro ao salvar preferência: {str(e)}')
            return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
def api_notificacoes_teste(request):
    """API para testar envio de notificação"""
    try:
        data = json.loads(request.body)

        tipo_codigo = data.get('tipo')
        canal_codigo = data.get('canal', 'email')
        dados_contexto = data.get('dados_contexto', {})

        if not tipo_codigo:
            return JsonResponse({'error': 'Tipo de notificação é obrigatório'}, status=400)

        from apps.notificacoes.services import criar_notificacao

        notificacao = criar_notificacao(
            tenant=request.tenant,
            codigo_tipo=tipo_codigo,
            titulo=f'[TESTE] Notificação de teste',
            mensagem=f'Esta é uma notificação de teste do tipo "{tipo_codigo}".',
            destinatario=request.user,
            dados_contexto=dados_contexto,
        )

        if notificacao:
            return JsonResponse({
                'success': True,
                'message': 'Notificação de teste criada com sucesso.',
                'notificacao_id': notificacao.pk,
            })

        return JsonResponse({
            'success': False,
            'message': 'Não foi possível criar a notificação. Verifique se o tipo está configurado.'
        })

    except Exception as e:
        logger.error(f'Erro ao enviar notificação de teste: {str(e)}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@login_required
def api_notificacoes_estatisticas(request):
    """API para obter estatísticas do sistema de notificações"""
    try:
        tenant = request.tenant
        qs = Notificacao.objects.filter(tenant=tenant)

        estatisticas = {
            'total': qs.count(),
            'enviadas': qs.filter(status='enviada').count(),
            'pendentes': qs.filter(status='pendente').count(),
            'falhas': qs.filter(status='falhou').count(),
            'canceladas': qs.filter(status='cancelada').count(),
            'lidas': qs.filter(lida=True).count(),
            'nao_lidas': qs.filter(lida=False).count(),
            'tipos_ativos': TipoNotificacao.objects.filter(tenant=tenant, ativo=True).count(),
            'canais_ativos': CanalNotificacao.objects.filter(tenant=tenant, ativo=True).count(),
        }

        return JsonResponse({
            'success': True,
            'estatisticas': estatisticas
        })

    except Exception as e:
        logger.error(f'Erro ao obter estatísticas: {str(e)}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


# ============================================================================
# APIs de Templates, Tipos e Canais de Notificação (CRUD completo)
# ============================================================================

@login_required
@require_http_methods(["GET", "POST", "PUT", "PATCH", "DELETE"])
def api_templates_notificacoes(request, template_id=None):
    """API para gerenciar templates de notificação"""
    try:
        # Verificar permissões
        from apps.sistema.decorators import user_tem_funcionalidade
        if not user_tem_funcionalidade(request, 'config.gerenciar_notificacoes'):
            return JsonResponse({'error': 'Sem permissão'}, status=403)

        if request.method == 'GET':
            if template_id:
                try:
                    template = TemplateNotificacao.objects.get(id=template_id)
                    return JsonResponse({
                        'success': True,
                        'template': {
                            'id': template.id,
                            'nome': template.nome,
                            'tipo_notificacao_id': template.tipo_notificacao.id,
                            'canal_id': template.canal.id,
                            'assunto': template.assunto,
                            'corpo_html': template.corpo_html,
                            'corpo_texto': template.corpo_texto,
                            'variaveis': template.variaveis,
                            'ativo': template.ativo
                        }
                    })
                except TemplateNotificacao.DoesNotExist:
                    return JsonResponse({'error': 'Template não encontrado'}, status=404)
            else:
                templates = TemplateNotificacao.objects.select_related('tipo_notificacao', 'canal').all()
                data = []
                for template in templates:
                    data.append({
                        'id': template.id,
                        'nome': template.nome,
                        'tipo_notificacao': template.tipo_notificacao.nome,
                        'canal': template.canal.nome,
                        'assunto': template.assunto,
                        'ativo': template.ativo,
                        'variaveis': template.variaveis
                    })
                return JsonResponse({'success': True, 'templates': data})

        elif request.method == 'POST':
            data = json.loads(request.body)

            template = TemplateNotificacao.objects.create(
                nome=data.get('nome'),
                tipo_notificacao_id=data.get('tipo_notificacao'),
                canal_id=data.get('canal'),
                assunto=data.get('assunto'),
                corpo_html=data.get('corpo_html', ''),
                corpo_texto=data.get('corpo_texto'),
                variaveis=data.get('variaveis', []),
                ativo=data.get('ativo', True)
            )

            return JsonResponse({
                'success': True,
                'message': 'Template criado com sucesso',
                'template_id': template.id
            })

        elif request.method == 'PUT':
            if not template_id:
                return JsonResponse({'error': 'ID do template é obrigatório'}, status=400)

            try:
                template = TemplateNotificacao.objects.get(id=template_id)
                data = json.loads(request.body)

                template.nome = data.get('nome', template.nome)
                template.tipo_notificacao_id = data.get('tipo_notificacao', template.tipo_notificacao.id)
                template.canal_id = data.get('canal', template.canal.id)
                template.assunto = data.get('assunto', template.assunto)
                template.corpo_html = data.get('corpo_html', template.corpo_html)
                template.corpo_texto = data.get('corpo_texto', template.corpo_texto)
                template.variaveis = data.get('variaveis', template.variaveis)
                template.ativo = data.get('ativo', template.ativo)
                template.save()

                return JsonResponse({
                    'success': True,
                    'message': 'Template atualizado com sucesso'
                })
            except TemplateNotificacao.DoesNotExist:
                return JsonResponse({'error': 'Template não encontrado'}, status=404)

        elif request.method == 'PATCH':
            if not template_id:
                return JsonResponse({'error': 'ID do template é obrigatório'}, status=400)

            try:
                template = TemplateNotificacao.objects.get(id=template_id)
                data = json.loads(request.body)

                if 'ativo' in data:
                    template.ativo = data['ativo']
                    template.save()

                return JsonResponse({
                    'success': True,
                    'message': 'Template atualizado com sucesso'
                })
            except TemplateNotificacao.DoesNotExist:
                return JsonResponse({'error': 'Template não encontrado'}, status=404)

        elif request.method == 'DELETE':
            if not template_id:
                return JsonResponse({'error': 'ID do template é obrigatório'}, status=400)

            try:
                template = TemplateNotificacao.objects.get(id=template_id)
                template.delete()

                return JsonResponse({
                    'success': True,
                    'message': 'Template excluído com sucesso'
                })
            except TemplateNotificacao.DoesNotExist:
                return JsonResponse({'error': 'Template não encontrado'}, status=404)

    except Exception as e:
        logger.error(f'Erro na API de templates: {str(e)}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@login_required
@require_http_methods(["GET", "POST", "PUT", "PATCH", "DELETE"])
def api_tipos_notificacao(request, tipo_id=None):
    """API para gerenciar tipos de notificação"""
    try:
        # Verificar permissões
        from apps.sistema.decorators import user_tem_funcionalidade
        if not user_tem_funcionalidade(request, 'config.gerenciar_notificacoes'):
            return JsonResponse({'error': 'Sem permissão'}, status=403)

        if request.method == 'GET':
            if tipo_id:
                try:
                    tipo = TipoNotificacao.objects.get(id=tipo_id)
                    return JsonResponse({
                        'success': True,
                        'tipo': {
                            'id': tipo.id,
                            'nome': tipo.nome,
                            'codigo': tipo.codigo,
                            'prioridade_padrao': tipo.prioridade_padrao,
                            'descricao': tipo.descricao,
                            'ativo': tipo.ativo
                        }
                    })
                except TipoNotificacao.DoesNotExist:
                    return JsonResponse({'error': 'Tipo não encontrado'}, status=404)
            else:
                tipos = TipoNotificacao.objects.all()
                data = []
                for tipo in tipos:
                    data.append({
                        'id': tipo.id,
                        'nome': tipo.nome,
                        'codigo': tipo.codigo,
                        'prioridade_padrao': tipo.prioridade_padrao,
                        'descricao': tipo.descricao,
                        'ativo': tipo.ativo
                    })
                return JsonResponse({'success': True, 'tipos': data})

        elif request.method == 'POST':
            data = json.loads(request.body)

            tipo = TipoNotificacao.objects.create(
                nome=data.get('nome'),
                codigo=data.get('codigo'),
                prioridade_padrao=data.get('prioridade_padrao', 'normal'),
                descricao=data.get('descricao', ''),
                ativo=data.get('ativo', True)
            )

            return JsonResponse({
                'success': True,
                'message': 'Tipo criado com sucesso',
                'tipo_id': tipo.id
            })

        elif request.method == 'PUT':
            if not tipo_id:
                return JsonResponse({'error': 'ID do tipo é obrigatório'}, status=400)

            try:
                tipo = TipoNotificacao.objects.get(id=tipo_id)
                data = json.loads(request.body)

                tipo.nome = data.get('nome', tipo.nome)
                tipo.codigo = data.get('codigo', tipo.codigo)
                tipo.prioridade_padrao = data.get('prioridade_padrao', tipo.prioridade_padrao)
                tipo.descricao = data.get('descricao', tipo.descricao)
                tipo.ativo = data.get('ativo', tipo.ativo)
                tipo.save()

                return JsonResponse({
                    'success': True,
                    'message': 'Tipo atualizado com sucesso'
                })
            except TipoNotificacao.DoesNotExist:
                return JsonResponse({'error': 'Tipo não encontrado'}, status=404)

        elif request.method == 'DELETE':
            if not tipo_id:
                return JsonResponse({'error': 'ID do tipo é obrigatório'}, status=400)

            try:
                tipo = TipoNotificacao.objects.get(id=tipo_id)
                tipo.delete()

                return JsonResponse({
                    'success': True,
                    'message': 'Tipo excluído com sucesso'
                })
            except TipoNotificacao.DoesNotExist:
                return JsonResponse({'error': 'Tipo não encontrado'}, status=404)

    except Exception as e:
        logger.error(f'Erro na API de tipos: {str(e)}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@login_required
@require_http_methods(["GET", "POST", "PUT", "PATCH", "DELETE"])
def api_canais_notificacao(request, canal_id=None):
    """API para gerenciar canais de notificação"""
    try:
        # Verificar permissões
        from apps.sistema.decorators import user_tem_funcionalidade
        if not user_tem_funcionalidade(request, 'config.gerenciar_notificacoes'):
            return JsonResponse({'error': 'Sem permissão'}, status=403)

        if request.method == 'GET':
            if canal_id:
                try:
                    canal = CanalNotificacao.objects.get(id=canal_id)
                    return JsonResponse({
                        'success': True,
                        'canal': {
                            'id': canal.id,
                            'nome': canal.nome,
                            'codigo': canal.codigo,
                            'icone': canal.icone,
                            'ativo': canal.ativo,
                            'configuracao': canal.configuracao
                        }
                    })
                except CanalNotificacao.DoesNotExist:
                    return JsonResponse({'error': 'Canal não encontrado'}, status=404)
            else:
                canais = CanalNotificacao.objects.all()
                data = []
                for canal in canais:
                    data.append({
                        'id': canal.id,
                        'nome': canal.nome,
                        'codigo': canal.codigo,
                        'icone': canal.icone,
                        'ativo': canal.ativo,
                        'configuracao': canal.configuracao
                    })
                return JsonResponse({'success': True, 'canais': data})

        elif request.method == 'POST':
            data = json.loads(request.body)

            canal = CanalNotificacao.objects.create(
                nome=data.get('nome'),
                codigo=data.get('codigo'),
                icone=data.get('icone', ''),
                ativo=data.get('ativo', True)
            )

            return JsonResponse({
                'success': True,
                'message': 'Canal criado com sucesso',
                'canal_id': canal.id
            })

        elif request.method == 'PUT':
            if not canal_id:
                return JsonResponse({'error': 'ID do canal é obrigatório'}, status=400)

            try:
                canal = CanalNotificacao.objects.get(id=canal_id)
                data = json.loads(request.body)

                canal.nome = data.get('nome', canal.nome)
                canal.codigo = data.get('codigo', canal.codigo)
                canal.icone = data.get('icone', canal.icone)
                canal.ativo = data.get('ativo', canal.ativo)
                canal.configuracao = data.get('configuracao', canal.configuracao)
                canal.save()

                return JsonResponse({
                    'success': True,
                    'message': 'Canal atualizado com sucesso'
                })
            except CanalNotificacao.DoesNotExist:
                return JsonResponse({'error': 'Canal não encontrado'}, status=404)

        elif request.method == 'DELETE':
            if not canal_id:
                return JsonResponse({'error': 'ID do canal é obrigatório'}, status=400)

            try:
                canal = CanalNotificacao.objects.get(id=canal_id)
                canal.delete()

                return JsonResponse({
                    'success': True,
                    'message': 'Canal excluído com sucesso'
                })
            except CanalNotificacao.DoesNotExist:
                return JsonResponse({'error': 'Canal não encontrado'}, status=404)

    except Exception as e:
        logger.error(f'Erro na API de canais: {str(e)}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


# ============================================================================
# APIs de Gerenciamento de Preferências de Notificações
# ============================================================================

@login_required
@require_http_methods(["POST"])
def api_preferencias_criar(request):
    """API para criar nova preferência de notificação para usuário"""
    try:
        data = json.loads(request.body)

        # Validar dados obrigatórios
        required_fields = ['usuario_id', 'tipo_id', 'canal_id', 'horario_inicio', 'horario_fim', 'dias_semana']
        for field in required_fields:
            if field not in data:
                return JsonResponse({
                    'success': False,
                    'error': f'Campo obrigatório ausente: {field}'
                }, status=400)

        # Buscar objetos
        usuario = User.objects.get(id=data['usuario_id'])
        tipo = TipoNotificacao.objects.get(id=data['tipo_id'])
        canal = CanalNotificacao.objects.get(id=data['canal_id'])

        # Verificar se já existe preferência para este usuário e tipo
        if PreferenciaNotificacao.objects.filter(usuario=usuario, tipo_notificacao=tipo).exists():
            return JsonResponse({
                'success': False,
                'error': 'Este usuário já possui preferência configurada para este tipo de notificação'
            }, status=400)

        # Criar preferência
        preferencia = PreferenciaNotificacao.objects.create(
            usuario=usuario,
            tipo_notificacao=tipo,
            canal_preferido=canal,
            horario_inicio=data['horario_inicio'],
            horario_fim=data['horario_fim'],
            dias_semana=data['dias_semana'],
            ativo=data.get('ativo', True)
        )

        return JsonResponse({
            'success': True,
            'preferencia_id': preferencia.id,
            'message': 'Preferência criada com sucesso'
        })

    except User.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Usuário não encontrado'
        }, status=404)
    except TipoNotificacao.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Tipo de notificação não encontrado'
        }, status=404)
    except CanalNotificacao.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Canal de notificação não encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["PUT"])
def api_preferencias_editar(request):
    """API para editar preferência de notificação"""
    try:
        data = json.loads(request.body)

        # Validar dados obrigatórios
        required_fields = ['preferencia_id', 'canal_id', 'horario_inicio', 'horario_fim', 'dias_semana']
        for field in required_fields:
            if field not in data:
                return JsonResponse({
                    'success': False,
                    'error': f'Campo obrigatório ausente: {field}'
                }, status=400)

        # Buscar preferência
        preferencia = PreferenciaNotificacao.objects.get(id=data['preferencia_id'])

        # Buscar canal
        canal = CanalNotificacao.objects.get(id=data['canal_id'])

        # Atualizar preferência
        preferencia.canal_preferido = canal
        preferencia.horario_inicio = data['horario_inicio']
        preferencia.horario_fim = data['horario_fim']
        preferencia.dias_semana = data['dias_semana']
        preferencia.ativo = data.get('ativo', True)
        preferencia.save()

        return JsonResponse({
            'success': True,
            'message': 'Preferência atualizada com sucesso'
        })

    except PreferenciaNotificacao.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Preferência não encontrada'
        }, status=404)
    except CanalNotificacao.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Canal de notificação não encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def api_preferencias_dados(request, preferencia_id):
    """API para buscar dados de uma preferência específica"""
    try:
        preferencia = PreferenciaNotificacao.objects.select_related('usuario', 'canal_preferido').get(id=preferencia_id)

        return JsonResponse({
            'success': True,
            'preferencia': {
                'id': preferencia.id,
                'usuario_id': preferencia.usuario.id,
                'usuario_nome': preferencia.usuario.get_full_name() or preferencia.usuario.username,
                'canal_id': preferencia.canal_preferido.id,
                'canal_nome': preferencia.canal_preferido.nome,
                'horario_inicio': preferencia.horario_inicio.strftime('%H:%M'),
                'horario_fim': preferencia.horario_fim.strftime('%H:%M'),
                'dias_semana': preferencia.dias_semana,
                'ativo': preferencia.ativo
            }
        })

    except PreferenciaNotificacao.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Preferência não encontrada'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def api_preferencias_pausar(request, preferencia_id):
    """API para pausar preferência de notificação"""
    try:
        preferencia = PreferenciaNotificacao.objects.get(id=preferencia_id)
        preferencia.ativo = False
        preferencia.save()

        return JsonResponse({
            'success': True,
            'message': 'Preferência pausada com sucesso'
        })

    except PreferenciaNotificacao.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Preferência não encontrada'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def api_preferencias_ativar(request, preferencia_id):
    """API para ativar preferência de notificação"""
    try:
        preferencia = PreferenciaNotificacao.objects.get(id=preferencia_id)
        preferencia.ativo = True
        preferencia.save()

        return JsonResponse({
            'success': True,
            'message': 'Preferência ativada com sucesso'
        })

    except PreferenciaNotificacao.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Preferência não encontrada'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["DELETE"])
def api_preferencias_remover(request, preferencia_id):
    """API para remover preferência de notificação"""
    try:
        preferencia = PreferenciaNotificacao.objects.get(id=preferencia_id)
        preferencia.delete()

        return JsonResponse({
            'success': True,
            'message': 'Preferência removida com sucesso'
        })

    except PreferenciaNotificacao.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Preferência não encontrada'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================================
# APIs de Configuração do WhatsApp
# ============================================================================

@login_required
@require_http_methods(["GET"])
def api_whatsapp_config(request):
    """API para buscar configuração do WhatsApp de um tipo específico"""
    try:
        tipo_id = request.GET.get('tipo_id')
        if not tipo_id:
            return JsonResponse({
                'success': False,
                'error': 'tipo_id é obrigatório'
            }, status=400)

        tipo = TipoNotificacao.objects.get(id=tipo_id)

        # Buscar configuração do WhatsApp
        whatsapp_config = {}
        if hasattr(tipo, 'whatsapp_config') and tipo.whatsapp_config:
            whatsapp_config = tipo.whatsapp_config
        else:
            # Configuração padrão
            whatsapp_config = {
                'url': 'https://automation-n8n.v4riem.easypanel.host/webhook/5a88a51b-f099-4ea9-afb5-68a10254bcdd',
                'method': 'POST',
                'timeout': 30,
                'headers': {},
                'frequency': 'imediato',
                'max_retries': 3,
                'message_template': '',
                'phone_format': 'e164'
            }

        # Serializar headers para JSON
        if 'headers' in whatsapp_config and whatsapp_config['headers']:
            whatsapp_config['headers_json'] = json.dumps(whatsapp_config['headers'], indent=2)

        return JsonResponse({
            'success': True,
            'config': whatsapp_config
        })

    except TipoNotificacao.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Tipo de notificação não encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def api_whatsapp_config_salvar(request):
    """API para salvar configuração do WhatsApp"""
    try:
        data = json.loads(request.body)

        # Validar dados obrigatórios
        if 'tipo_id' not in data or 'whatsapp_config' not in data:
            return JsonResponse({
                'success': False,
                'error': 'tipo_id e whatsapp_config são obrigatórios'
            }, status=400)

        tipo = TipoNotificacao.objects.get(id=data['tipo_id'])
        config = data['whatsapp_config']

        # Validar URL obrigatória
        if not config.get('url'):
            return JsonResponse({
                'success': False,
                'error': 'URL do webhook é obrigatória'
            }, status=400)

        # Salvar configuração no modelo
        tipo.whatsapp_config = {
            'url': config['url'],
            'method': config.get('method', 'POST'),
            'timeout': config.get('timeout', 30),
            'headers': config.get('headers', {}),
            'frequency': config.get('frequency', 'imediato'),
            'max_retries': config.get('max_retries', 3),
            'message_template': config.get('message_template', ''),
            'phone_format': config.get('phone_format', 'e164')
        }
        tipo.save()

        return JsonResponse({
            'success': True,
            'message': 'Configuração do WhatsApp salva com sucesso'
        })

    except TipoNotificacao.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Tipo de notificação não encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def api_whatsapp_test(request):
    """API para testar webhook do WhatsApp"""
    try:
        data = json.loads(request.body)

        # Validar dados obrigatórios
        if 'whatsapp_webhook_url' not in data:
            return JsonResponse({
                'success': False,
                'error': 'whatsapp_webhook_url é obrigatório'
            }, status=400)

        webhook_url = data['whatsapp_webhook_url']
        tipo_id = data.get('tipo_id')

        # Obter template personalizado se fornecido
        template_personalizado = data.get('message_template', '')

        # Buscar o tipo de notificação para usar dados reais
        tipo_nome = 'Teste de Integração'  # Fallback
        if tipo_id:
            try:
                tipo = TipoNotificacao.objects.get(id=tipo_id)
                tipo_nome = tipo.nome
            except TipoNotificacao.DoesNotExist:
                pass

        # Dados de teste para o N8N
        test_payload = {
            'tipo_notificacao': tipo_nome,
            'usuario_nome': 'Sistema Megalink',
            'telefone': '+5511999999999',
            'mensagem': 'Esta é uma mensagem de teste da integração WhatsApp com N8N.',
            'data_hora': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            'dados_contexto': {
                'sistema': 'Megalink',
                'teste': True,
                'timestamp': datetime.now().isoformat()
            }
        }

        # Se template personalizado foi fornecido, usar ele
        if template_personalizado and template_personalizado.strip():
            # Substituir variáveis no template
            template_processado = template_personalizado.replace('{{ usuario_nome }}', 'Sistema Megalink')
            template_processado = template_processado.replace('{{ mensagem }}', 'Esta é uma mensagem de teste da integração WhatsApp com N8N.')
            template_processado = template_processado.replace('{{ data_hora }}', datetime.now().strftime('%d/%m/%Y %H:%M:%S'))
            template_processado = template_processado.replace('{{ tipo_notificacao }}', tipo_nome)
            template_processado = template_processado.replace('{{ dados_contexto }}', 'Sistema: Megalink, Teste: True')

            # Adicionar o template processado ao payload
            test_payload['template_processado'] = template_processado
            test_payload['template_original'] = template_personalizado

        # Enviar requisição para o webhook
        start_time = datetime.now()
        response = requests.post(
            webhook_url,
            json=test_payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        end_time = datetime.now()

        response_time = int((end_time - start_time).total_seconds() * 1000)

        # Preparar mensagem de retorno
        mensagem_retorno = 'Teste enviado com sucesso para o N8N'
        if template_personalizado and template_personalizado.strip():
            mensagem_retorno += '\n\nTemplate personalizado foi usado no teste!'

        return JsonResponse({
            'success': True,
            'status_code': response.status_code,
            'response_time': response_time,
            'message': mensagem_retorno,
            'template_usado': bool(template_personalizado and template_personalizado.strip())
        })

    except requests.exceptions.Timeout:
        return JsonResponse({
            'success': False,
            'error': 'Timeout na requisição para o webhook'
        }, status=408)
    except requests.exceptions.ConnectionError:
        return JsonResponse({
            'success': False,
            'error': 'Erro de conexão com o webhook'
        }, status=503)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================================
# API para alternar status de canais
# ============================================================================

@login_required
@require_http_methods(["POST"])
def api_canal_toggle(request, canal_id):
    """API para alternar status de um canal de notificação"""
    try:
        # Verificar se o usuário tem permissão
        from apps.sistema.decorators import user_tem_funcionalidade
        if not user_tem_funcionalidade(request, 'config.gerenciar_notificacoes'):
            return JsonResponse({
                'success': False,
                'error': 'Você não tem permissão para alterar canais'
            }, status=403)

        # Buscar o canal
        try:
            canal = CanalNotificacao.objects.get(id=canal_id)
        except CanalNotificacao.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Canal não encontrado'
            }, status=404)

        # Obter novo status
        data = json.loads(request.body)
        novo_status = data.get('ativo', not canal.ativo)

        # Atualizar status
        canal.ativo = novo_status
        canal.save()

        return JsonResponse({
            'success': True,
            'message': f'Canal {canal.nome} {"ativado" if novo_status else "desativado"} com sucesso',
            'canal': {
                'id': canal.id,
                'nome': canal.nome,
                'codigo': canal.codigo,
                'ativo': canal.ativo
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================================
# APIs DE LEITURA (marcar lida / não lidas)
# ============================================================================

@login_required
@require_http_methods(["POST"])
def api_notificacao_marcar_lida(request, notificacao_id):
    """Marca uma notificação como lida."""
    try:
        from apps.notificacoes.services import marcar_lida
        ok = marcar_lida(notificacao_id, request.user)
        if ok:
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'Notificação não encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_notificacoes_marcar_todas_lidas(request):
    """Marca todas as notificações do usuário como lidas."""
    try:
        from apps.notificacoes.services import marcar_todas_lidas
        total = marcar_todas_lidas(request.tenant, request.user)
        return JsonResponse({'success': True, 'total_marcadas': total})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_notificacoes_nao_lidas(request):
    """Retorna contagem de notificações não lidas."""
    try:
        from apps.notificacoes.services import contar_nao_lidas
        total = contar_nao_lidas(request.tenant, request.user)
        return JsonResponse({'success': True, 'nao_lidas': total})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
