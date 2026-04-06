# ============================================================================
# APIS COMPLETAS DE ATENDIMENTO - CRUD PARA TODOS OS MODELS
# ============================================================================

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.sistema.decorators import api_token_required
from django.db.models import Q, Count, Avg, Max
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json
import logging
import traceback

logger = logging.getLogger(__name__)

from apps.comercial.atendimento.models import (
    FluxoAtendimento, QuestaoFluxo, AtendimentoFluxo, RespostaQuestao,
    TentativaResposta,
)
from apps.comercial.leads.models import LeadProspecto, HistoricoContato
from apps.sistema.models import LogSistema


# ============================================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================================

def _criar_log_api(nivel, modulo, mensagem, dados_extras=None, request=None):
    """Cria um log no sistema para APIs de atendimento"""
    try:
        ip = None
        usuario = None
        
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')
            
            if request.user.is_authenticated:
                usuario = request.user.username
        
        LogSistema.objects.create(
            nivel=nivel,
            modulo=modulo,
            mensagem=mensagem,
            dados_extras=dados_extras,
            usuario=usuario,
            ip=ip
        )
    except Exception as e:
        logger.warning("Erro ao criar log: %s", str(e))


def _parse_json_request(request):
    """Parse seguro do JSON do request"""
    try:
        body = request.body.decode('utf-8') if isinstance(request.body, (bytes, bytearray)) else request.body
        return json.loads(body or '{}')
    except Exception:
        return None


def _parse_bool(value):
    """Parse seguro de valores booleanos"""
    if value is None:
        return None
    value_lower = str(value).strip().lower()
    if value_lower in ['1', 'true', 't', 'sim', 'yes', 'y']:
        return True
    if value_lower in ['0', 'false', 'f', 'nao', 'não', 'no', 'n']:
        return False
    return None


def _safe_ordering(ordering_param, allowed_fields, default='-id'):
    """Validação segura de ordenação"""
    if not ordering_param:
        return default
    raw = ordering_param.strip()
    desc = raw.startswith('-')
    field = raw[1:] if desc else raw
    if field in allowed_fields:
        return f"-{field}" if desc else field
    return default


def _model_field_names(model_cls):
    """Retorna nomes dos campos do modelo"""
    field_names = []
    for f in model_cls._meta.get_fields():
        if getattr(f, 'many_to_many', False) or getattr(f, 'one_to_many', False):
            continue
        if hasattr(f, 'attname'):
            field_names.append(f.name)
    return set(field_names)


# ============================================================================
# FUNÇÕES DE SERIALIZAÇÃO MELHORADAS
# ============================================================================

def _serialize_fluxo_atendimento(fluxo):
    """Serializa um objeto FluxoAtendimento de forma robusta"""
    try:
        return {
            'id': fluxo.id,
            'nome': fluxo.nome,
            'descricao': fluxo.descricao,
            'tipo_fluxo': fluxo.tipo_fluxo,
            'tipo_fluxo_display': fluxo.get_tipo_fluxo_display(),
            'status': fluxo.status,
            'status_display': fluxo.get_status_display(),
            'ativo': fluxo.ativo,
            'max_tentativas': fluxo.max_tentativas,
            'tempo_limite_minutos': fluxo.tempo_limite_minutos,
            'permite_pular_questoes': fluxo.permite_pular_questoes,
            'data_criacao': fluxo.data_criacao.isoformat() if fluxo.data_criacao else None,
            'data_atualizacao': fluxo.data_atualizacao.isoformat() if fluxo.data_atualizacao else None,
            'criado_por': fluxo.criado_por,
            # Estatísticas calculadas
            'total_questoes': fluxo.get_total_questoes(),
            'total_atendimentos': getattr(fluxo, 'total_atendimentos_cached', 0),
            'taxa_completacao': getattr(fluxo, 'taxa_completacao_cached', '0.0%'),
            'estatisticas': fluxo.get_estatisticas() if hasattr(fluxo, 'get_estatisticas') else {}
        }
    except Exception as e:
        return {
            'id': fluxo.id,
            'nome': getattr(fluxo, 'nome', 'N/A'),
            'error': f'Erro na serialização: {str(e)}'
        }


def _serialize_questao_fluxo(questao, incluir_detalhes_inteligentes=False):
    """Serializa um objeto QuestaoFluxo de forma robusta"""
    try:
        data = {
            'id': questao.id,
            'fluxo_id': questao.fluxo.id if questao.fluxo else None,
            'fluxo_nome': questao.fluxo.nome if questao.fluxo else 'N/A',
            'indice': questao.indice,
            'titulo': questao.titulo,
            'descricao': questao.descricao,
            'tipo_questao': questao.tipo_questao,
            'tipo_questao_display': questao.get_tipo_questao_display(),
            'tipo_validacao': questao.tipo_validacao,
            'tipo_validacao_display': questao.get_tipo_validacao_display(),
            'opcoes_resposta': questao.opcoes_resposta,
            'opcoes_formatadas': questao.get_opcoes_formatadas() if hasattr(questao, 'get_opcoes_formatadas') else [],
            'resposta_padrao': questao.resposta_padrao,
            'regex_validacao': questao.regex_validacao,
            'tamanho_minimo': questao.tamanho_minimo,
            'tamanho_maximo': questao.tamanho_maximo,
            'valor_minimo': float(questao.valor_minimo) if questao.valor_minimo else None,
            'valor_maximo': float(questao.valor_maximo) if questao.valor_maximo else None,
            'questao_dependencia_id': questao.questao_dependencia.id if questao.questao_dependencia else None,
            'valor_dependencia': questao.valor_dependencia,
            'ativo': questao.ativo,
            'permite_voltar': questao.permite_voltar,
            'permite_editar': questao.permite_editar,
            'ordem_exibicao': questao.ordem_exibicao,
            # Novos campos do fluxo inteligente
            'opcoes_dinamicas_fonte': questao.opcoes_dinamicas_fonte,
            'max_tentativas': questao.max_tentativas,
            'estrategia_erro': questao.estrategia_erro,
            'estrategia_erro_display': questao.get_estrategia_erro_display(),
            'questao_padrao_proxima_id': questao.questao_padrao_proxima.id if questao.questao_padrao_proxima else None,
            'mensagem_erro_padrao': questao.mensagem_erro_padrao,
            'instrucoes_resposta_correta': questao.instrucoes_resposta_correta
        }
        
        # Incluir detalhes inteligentes apenas quando solicitado (para evitar overhead)
        if incluir_detalhes_inteligentes:
            data.update({
                'roteamento_respostas': questao.roteamento_respostas,
                'prompt_ia_validacao': questao.prompt_ia_validacao,
                'criterios_ia': questao.criterios_ia,
                'webhook_n8n_validacao': questao.webhook_n8n_validacao,
                'webhook_n8n_pos_resposta': questao.webhook_n8n_pos_resposta,
                'query_opcoes_dinamicas': questao.query_opcoes_dinamicas,
                'variaveis_contexto': questao.variaveis_contexto,
                'template_questao': questao.template_questao,
                'mensagem_tentativa_esgotada': questao.mensagem_tentativa_esgotada,
                'questao_erro_redirecionamento_id': questao.questao_erro_redirecionamento.id if questao.questao_erro_redirecionamento else None
            })
        
        return data
    except Exception as e:
        return {
            'id': questao.id,
            'titulo': getattr(questao, 'titulo', 'N/A'),
            'error': f'Erro na serialização: {str(e)}'
        }


def _serialize_tentativa_resposta(tentativa):
    """Serializa um objeto TentativaResposta de forma robusta"""
    try:
        return {
            'id': tentativa.id,
            'atendimento_id': tentativa.atendimento.id if tentativa.atendimento else None,
            'questao_id': tentativa.questao.id if tentativa.questao else None,
            'questao_titulo': tentativa.questao.titulo if tentativa.questao else 'N/A',
            'tentativa_numero': tentativa.tentativa_numero,
            'resposta_original': tentativa.resposta_original,
            'resposta_processada': tentativa.resposta_processada,
            'valida': tentativa.valida,
            'mensagem_erro': tentativa.mensagem_erro,
            'resultado_ia': tentativa.resultado_ia,
            'confianca_ia': float(tentativa.confianca_ia) if tentativa.confianca_ia else None,
            'resultado_webhook': tentativa.resultado_webhook,
            'estrategia_aplicada': tentativa.estrategia_aplicada,
            'contexto_tentativa': tentativa.contexto_tentativa,
            'data_tentativa': tentativa.data_tentativa.isoformat() if tentativa.data_tentativa else None,
            'tempo_resposta_segundos': tentativa.tempo_resposta_segundos,
            'tempo_resposta_formatado': tentativa.get_tempo_resposta_formatado() if hasattr(tentativa, 'get_tempo_resposta_formatado') else None,
            'ip_origem': tentativa.ip_origem,
            'user_agent': tentativa.user_agent,
            'resultado_ia_resumido': tentativa.get_resultado_ia_resumido() if hasattr(tentativa, 'get_resultado_ia_resumido') else None
        }
    except Exception as e:
        return {
            'id': tentativa.id,
            'tentativa_numero': getattr(tentativa, 'tentativa_numero', 0),
            'error': f'Erro na serialização: {str(e)}'
        }


def _serialize_atendimento_fluxo(atendimento):
    """Serializa um objeto AtendimentoFluxo de forma robusta"""
    try:
        return {
            'id': atendimento.id,
            'lead_id': atendimento.lead.id if atendimento.lead else None,
            'lead_nome': atendimento.lead.nome_razaosocial if atendimento.lead else 'N/A',
            'lead_telefone': atendimento.lead.telefone if atendimento.lead else None,
            'fluxo_id': atendimento.fluxo.id if atendimento.fluxo else None,
            'fluxo_nome': atendimento.fluxo.nome if atendimento.fluxo else 'N/A',
            'historico_contato_id': atendimento.historico_contato.id if atendimento.historico_contato else None,
            'status': atendimento.status,
            'status_display': atendimento.get_status_display(),
            'questao_atual': atendimento.questao_atual,
            'total_questoes': atendimento.total_questoes,
            'questoes_respondidas': atendimento.questoes_respondidas,
            'progresso_percentual': atendimento.get_progresso_percentual(),
            'data_inicio': atendimento.data_inicio.isoformat() if atendimento.data_inicio else None,
            'data_ultima_atividade': atendimento.data_ultima_atividade.isoformat() if atendimento.data_ultima_atividade else None,
            'data_conclusao': atendimento.data_conclusao.isoformat() if atendimento.data_conclusao else None,
            'tempo_total': atendimento.tempo_total,
            'tempo_formatado': atendimento.get_tempo_formatado() if hasattr(atendimento, 'get_tempo_formatado') else None,
            'tentativas_atual': atendimento.tentativas_atual,
            'max_tentativas': atendimento.max_tentativas,
            'dados_respostas': atendimento.dados_respostas,
            'respostas_formatadas': atendimento.get_respostas_formatadas() if hasattr(atendimento, 'get_respostas_formatadas') else [],
            'observacoes': atendimento.observacoes,
            'ip_origem': atendimento.ip_origem,
            'user_agent': atendimento.user_agent,
            'dispositivo': atendimento.dispositivo,
            'id_externo': atendimento.id_externo,
            'resultado_final': atendimento.resultado_final,
            'score_qualificacao': atendimento.score_qualificacao,
            # Ações disponíveis
            'pode_avancar': atendimento.pode_avancar() if hasattr(atendimento, 'pode_avancar') else False,
            'pode_voltar': atendimento.pode_voltar() if hasattr(atendimento, 'pode_voltar') else False,
            'pode_ser_reiniciado': atendimento.pode_ser_reiniciado() if hasattr(atendimento, 'pode_ser_reiniciado') else False,
            # Estatísticas de tentativas inteligentes
            'estatisticas_tentativas': atendimento.get_estatisticas_tentativas() if hasattr(atendimento, 'get_estatisticas_tentativas') else None,
            'questoes_problematicas': atendimento.get_questoes_problematicas() if hasattr(atendimento, 'get_questoes_problematicas') else [],
            'contexto_dinamico': atendimento.get_contexto_dinamico() if hasattr(atendimento, 'get_contexto_dinamico') else {}
        }
    except Exception as e:
        return {
            'id': atendimento.id,
            'error': f'Erro na serialização: {str(e)}'
        }


def _serialize_resposta_questao(resposta):
    """Serializa um objeto RespostaQuestao de forma robusta"""
    try:
        return {
            'id': resposta.id,
            'atendimento_id': resposta.atendimento.id if resposta.atendimento else None,
            'questao_id': resposta.questao.id if resposta.questao else None,
            'questao_titulo': resposta.questao.titulo if resposta.questao else 'N/A',
            'questao_tipo': resposta.questao.tipo_questao if resposta.questao else None,
            'resposta': resposta.resposta,
            'resposta_processada': resposta.resposta_processada,
            'valida': resposta.valida,
            'mensagem_erro': resposta.mensagem_erro,
            'tentativas': resposta.tentativas,
            'data_resposta': resposta.data_resposta.isoformat() if resposta.data_resposta else None,
            'tempo_resposta': resposta.tempo_resposta,
            'tempo_resposta_formatado': resposta.get_tempo_resposta_formatado() if hasattr(resposta, 'get_tempo_resposta_formatado') else None,
            'ip_origem': resposta.ip_origem,
            'user_agent': resposta.user_agent,
            'dados_extras': resposta.dados_extras
        }
    except Exception as e:
        return {
            'id': resposta.id,
            'error': f'Erro na serialização: {str(e)}'
        }


# ============================================================================
# APIS CRUD - FLUXOS DE ATENDIMENTO
# ============================================================================

@login_required
@require_http_methods(["POST"])
def criar_fluxo_api(request):
    """API para criar novo fluxo de atendimento"""
    try:
        data = _parse_json_request(request)
        if data is None:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
        
        # Campos obrigatórios
        required = ['nome', 'tipo_fluxo']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return JsonResponse({'error': f'Campos obrigatórios ausentes: {", ".join(missing)}'}, status=400)
        
        # Validar tipo_fluxo
        tipos_validos = [choice[0] for choice in FluxoAtendimento.TIPO_FLUXO_CHOICES]
        if data['tipo_fluxo'] not in tipos_validos:
            return JsonResponse({'error': f'Tipo de fluxo inválido. Opções válidas: {", ".join(tipos_validos)}'}, status=400)
        
        # Validar status se fornecido
        if 'status' in data:
            status_validos = [choice[0] for choice in FluxoAtendimento.STATUS_CHOICES]
            if data['status'] not in status_validos:
                return JsonResponse({'error': f'Status inválido. Opções válidas: {", ".join(status_validos)}'}, status=400)
        
        # Criar fluxo
        allowed_fields = _model_field_names(FluxoAtendimento)
        payload = {k: v for k, v in data.items() if k in allowed_fields}
        
        # Definir criado_por se usuário autenticado
        if request.user.is_authenticated:
            payload['criado_por'] = request.user.username
        
        fluxo = FluxoAtendimento.objects.create(**payload)
        
        _criar_log_api('INFO', 'criar_fluxo_api', f'Fluxo criado: {fluxo.nome}', {'fluxo_id': fluxo.id}, request)
        
        return JsonResponse({
            'success': True,
            'id': fluxo.id,
            'fluxo': _serialize_fluxo_atendimento(fluxo)
        }, status=201)
        
    except Exception as e:
        _criar_log_api('ERROR', 'criar_fluxo_api', f'Erro ao criar fluxo: {str(e)}', {'traceback': traceback.format_exc()}, request)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["PUT", "PATCH"])
def atualizar_fluxo_api(request, fluxo_id):
    """API para atualizar fluxo de atendimento"""
    try:
        data = _parse_json_request(request)
        if data is None:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
        
        try:
            fluxo = FluxoAtendimento.objects.get(id=fluxo_id)
        except FluxoAtendimento.DoesNotExist:
            return JsonResponse({'error': 'Fluxo não encontrado'}, status=404)
        
        # Validações
        if 'tipo_fluxo' in data:
            tipos_validos = [choice[0] for choice in FluxoAtendimento.TIPO_FLUXO_CHOICES]
            if data['tipo_fluxo'] not in tipos_validos:
                return JsonResponse({'error': f'Tipo de fluxo inválido. Opções válidas: {", ".join(tipos_validos)}'}, status=400)
        
        if 'status' in data:
            status_validos = [choice[0] for choice in FluxoAtendimento.STATUS_CHOICES]
            if data['status'] not in status_validos:
                return JsonResponse({'error': f'Status inválido. Opções válidas: {", ".join(status_validos)}'}, status=400)
        
        # Atualizar campos
        allowed_fields = _model_field_names(FluxoAtendimento) - {'id', 'data_criacao'}
        updates = {k: v for k, v in data.items() if k in allowed_fields}
        
        if not updates:
            return JsonResponse({'error': 'Nenhum campo válido para atualizar'}, status=400)
        
        for key, value in updates.items():
            setattr(fluxo, key, value)
        
        fluxo.save()
        
        _criar_log_api('INFO', 'atualizar_fluxo_api', f'Fluxo atualizado: {fluxo.nome}', {'fluxo_id': fluxo.id, 'campos': list(updates.keys())}, request)
        
        return JsonResponse({
            'success': True,
            'id': fluxo.id,
            'fluxo': _serialize_fluxo_atendimento(fluxo)
        })
        
    except Exception as e:
        _criar_log_api('ERROR', 'atualizar_fluxo_api', f'Erro ao atualizar fluxo: {str(e)}', {'fluxo_id': fluxo_id}, request)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def consultar_fluxos_api(request):
    """API GET melhorada para consultar fluxos de atendimento"""
    try:
        page = max(1, int(request.GET.get('page', 1)))
        per_page = max(1, min(int(request.GET.get('per_page', 20)), 100))
        
        # Filtros
        fluxo_id = request.GET.get('id')
        search = request.GET.get('search', '').strip()
        tipo_fluxo = request.GET.get('tipo_fluxo')
        status = request.GET.get('status')
        ativo = _parse_bool(request.GET.get('ativo'))
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        ordering = request.GET.get('ordering')
        include_stats = _parse_bool(request.GET.get('include_stats', 'true'))
        
        # QuerySet base com anotações para performance
        qs = FluxoAtendimento.objects.all()
        
        if include_stats:
            qs = qs.annotate(
                total_atendimentos_cached=Count('atendimentos'),
                total_questoes_cached=Count('questoes')
            )
        
        # Aplicar filtros
        if fluxo_id:
            qs = qs.filter(id=fluxo_id)
        else:
            if search:
                qs = qs.filter(
                    Q(nome__icontains=search) |
                    Q(descricao__icontains=search) |
                    Q(criado_por__icontains=search)
                )
            
            if tipo_fluxo:
                qs = qs.filter(tipo_fluxo=tipo_fluxo)
            
            if status:
                qs = qs.filter(status=status)
            
            if ativo is not None:
                qs = qs.filter(ativo=ativo)
            
            if data_inicio:
                try:
                    di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    qs = qs.filter(data_criacao__date__gte=di)
                except ValueError:
                    pass
            
            if data_fim:
                try:
                    df = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    qs = qs.filter(data_criacao__date__lte=df)
                except ValueError:
                    pass
        
        # Ordenação
        allowed_order_fields = {'id', 'nome', 'data_criacao', 'data_atualizacao', 'tipo_fluxo', 'status'}
        order_by = _safe_ordering(ordering, allowed_order_fields, '-data_criacao')
        qs = qs.order_by(order_by)
        
        # Paginação
        total = qs.count()
        start = (page - 1) * per_page
        end = start + per_page
        items = qs[start:end]
        
        # Serialização
        results = []
        for item in items:
            serialized = _serialize_fluxo_atendimento(item)
            if include_stats and hasattr(item, 'total_atendimentos_cached'):
                serialized['total_atendimentos'] = item.total_atendimentos_cached
                serialized['total_questoes'] = item.total_questoes_cached
            results.append(serialized)
        
        # Metadata adicional
        metadata = {
            'tipos_fluxo_disponiveis': FluxoAtendimento.TIPO_FLUXO_CHOICES,
            'status_disponiveis': FluxoAtendimento.STATUS_CHOICES
        }
        
        return JsonResponse({
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'ordering': order_by,
            'metadata': metadata
        })
        
    except Exception as e:
        _criar_log_api('ERROR', 'consultar_fluxos_api', f'Erro na consulta: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["DELETE"])
def deletar_fluxo_api(request, fluxo_id):
    """API para deletar fluxo de atendimento"""
    try:
        try:
            fluxo = FluxoAtendimento.objects.get(id=fluxo_id)
        except FluxoAtendimento.DoesNotExist:
            return JsonResponse({'error': 'Fluxo não encontrado'}, status=404)
        
        # Verificar se existem atendimentos vinculados
        atendimentos_count = fluxo.atendimentos.count()
        if atendimentos_count > 0:
            return JsonResponse({
                'error': f'Não é possível deletar fluxo com {atendimentos_count} atendimento(s) vinculado(s)'
            }, status=400)
        
        nome_fluxo = fluxo.nome
        fluxo.delete()
        
        _criar_log_api('INFO', 'deletar_fluxo_api', f'Fluxo deletado: {nome_fluxo}', {'fluxo_id': fluxo_id}, request)
        
        return JsonResponse({
            'success': True,
            'message': f'Fluxo "{nome_fluxo}" deletado com sucesso'
        })
        
    except Exception as e:
        _criar_log_api('ERROR', 'deletar_fluxo_api', f'Erro ao deletar fluxo: {str(e)}', {'fluxo_id': fluxo_id}, request)
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# APIS CRUD - QUESTÕES DE FLUXO
# ============================================================================

@login_required
@require_http_methods(["POST"])
def criar_questao_api(request):
    """API para criar nova questão de fluxo"""
    try:
        data = _parse_json_request(request)
        if data is None:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
        
        # Campos obrigatórios
        required = ['fluxo_id', 'titulo', 'tipo_questao']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return JsonResponse({'error': f'Campos obrigatórios ausentes: {", ".join(missing)}'}, status=400)
        
        # Verificar se o fluxo existe
        try:
            fluxo = FluxoAtendimento.objects.get(id=data['fluxo_id'])
        except FluxoAtendimento.DoesNotExist:
            return JsonResponse({'error': 'Fluxo não encontrado'}, status=404)
        
        # Validações
        tipos_validos = [choice[0] for choice in QuestaoFluxo.TIPO_QUESTAO_CHOICES]
        if data['tipo_questao'] not in tipos_validos:
            return JsonResponse({'error': f'Tipo de questão inválido. Opções válidas: {", ".join(tipos_validos)}'}, status=400)
        
        if 'tipo_validacao' in data:
            validacoes_validas = [choice[0] for choice in QuestaoFluxo.TIPO_VALIDACAO_CHOICES]
            if data['tipo_validacao'] not in validacoes_validas:
                return JsonResponse({'error': f'Tipo de validação inválido. Opções válidas: {", ".join(validacoes_validas)}'}, status=400)
        
        # Preparar dados
        allowed_fields = _model_field_names(QuestaoFluxo)
        payload = {k: v for k, v in data.items() if k in allowed_fields}
        payload['fluxo'] = fluxo
        
        # Se não foi especificado o índice, usar o próximo disponível
        if 'indice' not in payload or not payload['indice']:
            max_indice = QuestaoFluxo.objects.filter(fluxo=fluxo).aggregate(
                max_indice=Max('indice')
            )['max_indice'] or 0
            payload['indice'] = max_indice + 1
        
        questao = QuestaoFluxo.objects.create(**payload)
        
        _criar_log_api('INFO', 'criar_questao_api', f'Questão criada: {questao.titulo}', {'questao_id': questao.id, 'fluxo_id': fluxo.id}, request)
        
        return JsonResponse({
            'success': True,
            'id': questao.id,
            'questao': _serialize_questao_fluxo(questao)
        }, status=201)
        
    except Exception as e:
        _criar_log_api('ERROR', 'criar_questao_api', f'Erro ao criar questão: {str(e)}', {'traceback': traceback.format_exc()}, request)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["PUT", "PATCH"])
def atualizar_questao_api(request, questao_id):
    """API para atualizar questão de fluxo"""
    try:
        data = _parse_json_request(request)
        if data is None:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
        
        try:
            questao = QuestaoFluxo.objects.select_related('fluxo').get(id=questao_id)
        except QuestaoFluxo.DoesNotExist:
            return JsonResponse({'error': 'Questão não encontrada'}, status=404)
        
        # Validações
        if 'tipo_questao' in data:
            tipos_validos = [choice[0] for choice in QuestaoFluxo.TIPO_QUESTAO_CHOICES]
            if data['tipo_questao'] not in tipos_validos:
                return JsonResponse({'error': f'Tipo de questão inválido. Opções válidas: {", ".join(tipos_validos)}'}, status=400)
        
        if 'tipo_validacao' in data:
            validacoes_validas = [choice[0] for choice in QuestaoFluxo.TIPO_VALIDACAO_CHOICES]
            if data['tipo_validacao'] not in validacoes_validas:
                return JsonResponse({'error': f'Tipo de validação inválido. Opções válidas: {", ".join(validacoes_validas)}'}, status=400)
        
        # Atualizar campos
        allowed_fields = _model_field_names(QuestaoFluxo) - {'id', 'fluxo'}
        updates = {k: v for k, v in data.items() if k in allowed_fields}
        
        if not updates:
            return JsonResponse({'error': 'Nenhum campo válido para atualizar'}, status=400)
        
        for key, value in updates.items():
            setattr(questao, key, value)
        
        questao.save()
        
        _criar_log_api('INFO', 'atualizar_questao_api', f'Questão atualizada: {questao.titulo}', {'questao_id': questao.id, 'campos': list(updates.keys())}, request)
        
        return JsonResponse({
            'success': True,
            'id': questao.id,
            'questao': _serialize_questao_fluxo(questao)
        })
        
    except Exception as e:
        _criar_log_api('ERROR', 'atualizar_questao_api', f'Erro ao atualizar questão: {str(e)}', {'questao_id': questao_id}, request)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def consultar_questoes_api(request):
    """API GET melhorada para consultar questões de fluxo"""
    try:
        page = max(1, int(request.GET.get('page', 1)))
        per_page = max(1, min(int(request.GET.get('per_page', 20)), 100))
        
        # Filtros
        questao_id = request.GET.get('id')
        fluxo_id = request.GET.get('fluxo_id')
        search = request.GET.get('search', '').strip()
        tipo_questao = request.GET.get('tipo_questao')
        tipo_validacao = request.GET.get('tipo_validacao')
        ativo = _parse_bool(request.GET.get('ativo'))
        indice = request.GET.get('indice')
        ordering = request.GET.get('ordering')
        
        # QuerySet base
        qs = QuestaoFluxo.objects.select_related('fluxo', 'questao_dependencia')
        
        # Aplicar filtros
        if questao_id:
            qs = qs.filter(id=questao_id)
        else:
            if fluxo_id:
                qs = qs.filter(fluxo_id=fluxo_id)
            
            if search:
                qs = qs.filter(
                    Q(titulo__icontains=search) |
                    Q(descricao__icontains=search) |
                    Q(fluxo__nome__icontains=search)
                )
            
            if tipo_questao:
                qs = qs.filter(tipo_questao=tipo_questao)
            
            if tipo_validacao:
                qs = qs.filter(tipo_validacao=tipo_validacao)
            
            if ativo is not None:
                qs = qs.filter(ativo=ativo)
            
            if indice:
                try:
                    indice_int = int(indice)
                    qs = qs.filter(indice=indice_int)
                except ValueError:
                    pass
        
        # Ordenação
        allowed_order_fields = {'id', 'indice', 'titulo', 'tipo_questao', 'ordem_exibicao', 'fluxo__nome'}
        order_by = _safe_ordering(ordering, allowed_order_fields, 'fluxo__id,indice')
        qs = qs.order_by(*order_by.split(','))
        
        # Paginação
        total = qs.count()
        start = (page - 1) * per_page
        end = start + per_page
        items = qs[start:end]
        
        # Serialização
        results = [_serialize_questao_fluxo(item) for item in items]
        
        # Metadata adicional
        metadata = {
            'tipos_questao_disponiveis': QuestaoFluxo.TIPO_QUESTAO_CHOICES,
            'tipos_validacao_disponiveis': QuestaoFluxo.TIPO_VALIDACAO_CHOICES
        }
        
        return JsonResponse({
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'ordering': order_by,
            'metadata': metadata
        })
        
    except Exception as e:
        _criar_log_api('ERROR', 'consultar_questoes_api', f'Erro na consulta: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["DELETE"])
def deletar_questao_api(request, questao_id):
    """API para deletar questão de fluxo"""
    try:
        try:
            questao = QuestaoFluxo.objects.get(id=questao_id)
        except QuestaoFluxo.DoesNotExist:
            return JsonResponse({'error': 'Questão não encontrada'}, status=404)
        
        # Verificar se existem respostas vinculadas
        respostas_count = questao.respostas.count()
        if respostas_count > 0:
            return JsonResponse({
                'error': f'Não é possível deletar questão com {respostas_count} resposta(s) vinculada(s)'
            }, status=400)
        
        titulo_questao = questao.titulo
        fluxo_id = questao.fluxo.id
        questao.delete()
        
        _criar_log_api('INFO', 'deletar_questao_api', f'Questão deletada: {titulo_questao}', {'questao_id': questao_id, 'fluxo_id': fluxo_id}, request)
        
        return JsonResponse({
            'success': True,
            'message': f'Questão "{titulo_questao}" deletada com sucesso'
        })
        
    except Exception as e:
        _criar_log_api('ERROR', 'deletar_questao_api', f'Erro ao deletar questão: {str(e)}', {'questao_id': questao_id}, request)
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# APIS CRUD - ATENDIMENTOS DE FLUXO
# ============================================================================

@login_required
@require_http_methods(["POST"])
def criar_atendimento_api(request):
    """API para criar novo atendimento de fluxo"""
    try:
        data = _parse_json_request(request)
        if data is None:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
        
        # Campos obrigatórios
        required = ['lead_id', 'fluxo_id']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return JsonResponse({'error': f'Campos obrigatórios ausentes: {", ".join(missing)}'}, status=400)
        
        # Verificar se o lead existe
        try:
            lead = LeadProspecto.objects.get(id=data['lead_id'])
        except LeadProspecto.DoesNotExist:
            return JsonResponse({'error': 'Lead não encontrado'}, status=404)
        
        # Verificar se o fluxo existe
        try:
            fluxo = FluxoAtendimento.objects.get(id=data['fluxo_id'])
        except FluxoAtendimento.DoesNotExist:
            return JsonResponse({'error': 'Fluxo não encontrado'}, status=404)
        
        # Verificar se já existe atendimento ativo para este lead no fluxo
        atendimento_ativo = AtendimentoFluxo.objects.filter(
            lead=lead,
            fluxo=fluxo,
            status__in=['iniciado', 'em_andamento', 'pausado']
        ).first()
        
        if atendimento_ativo:
            return JsonResponse({
                'error': 'Já existe um atendimento ativo para este lead neste fluxo',
                'atendimento_existente_id': atendimento_ativo.id
            }, status=400)
        
        # Preparar dados
        allowed_fields = _model_field_names(AtendimentoFluxo)
        payload = {k: v for k, v in data.items() if k in allowed_fields}
        payload['lead'] = lead
        payload['fluxo'] = fluxo
        payload['total_questoes'] = fluxo.get_total_questoes()
        
        # Definir histórico de contato se fornecido
        if 'historico_contato_id' in data:
            try:
                historico = HistoricoContato.objects.get(id=data['historico_contato_id'])
                payload['historico_contato'] = historico
            except HistoricoContato.DoesNotExist:
                return JsonResponse({'error': 'Histórico de contato não encontrado'}, status=404)
        
        # Extrair IP e User Agent
        if 'ip_origem' not in payload:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                payload['ip_origem'] = x_forwarded_for.split(',')[0].strip()
            else:
                payload['ip_origem'] = request.META.get('REMOTE_ADDR')
        
        if 'user_agent' not in payload:
            payload['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
        
        atendimento = AtendimentoFluxo.objects.create(**payload)
        
        _criar_log_api('INFO', 'criar_atendimento_api', f'Atendimento criado', {
            'atendimento_id': atendimento.id,
            'lead_id': lead.id,
            'fluxo_id': fluxo.id
        }, request)
        
        return JsonResponse({
            'success': True,
            'id': atendimento.id,
            'atendimento': _serialize_atendimento_fluxo(atendimento)
        }, status=201)
        
    except Exception as e:
        _criar_log_api('ERROR', 'criar_atendimento_api', f'Erro ao criar atendimento: {str(e)}', {'traceback': traceback.format_exc()}, request)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["PUT", "PATCH"])
def atualizar_atendimento_api(request, atendimento_id):
    """API para atualizar atendimento de fluxo"""
    try:
        data = _parse_json_request(request)
        if data is None:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
        
        try:
            atendimento = AtendimentoFluxo.objects.select_related('lead', 'fluxo').get(id=atendimento_id)
        except AtendimentoFluxo.DoesNotExist:
            return JsonResponse({'error': 'Atendimento não encontrado'}, status=404)
        
        # Validações
        if 'status' in data:
            status_validos = [choice[0] for choice in AtendimentoFluxo.STATUS_CHOICES]
            if data['status'] not in status_validos:
                return JsonResponse({'error': f'Status inválido. Opções válidas: {", ".join(status_validos)}'}, status=400)
        
        # Atualizar campos
        allowed_fields = _model_field_names(AtendimentoFluxo) - {'id', 'lead', 'fluxo', 'data_inicio'}
        updates = {k: v for k, v in data.items() if k in allowed_fields}
        
        if not updates:
            return JsonResponse({'error': 'Nenhum campo válido para atualizar'}, status=400)
        
        for key, value in updates.items():
            setattr(atendimento, key, value)
        
        atendimento.save()
        
        _criar_log_api('INFO', 'atualizar_atendimento_api', f'Atendimento atualizado', {
            'atendimento_id': atendimento.id,
            'campos': list(updates.keys())
        }, request)
        
        return JsonResponse({
            'success': True,
            'id': atendimento.id,
            'atendimento': _serialize_atendimento_fluxo(atendimento)
        })
        
    except Exception as e:
        _criar_log_api('ERROR', 'atualizar_atendimento_api', f'Erro ao atualizar atendimento: {str(e)}', {'atendimento_id': atendimento_id}, request)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def consultar_atendimentos_api(request):
    """API GET melhorada para consultar atendimentos de fluxo"""
    try:
        page = max(1, int(request.GET.get('page', 1)))
        per_page = max(1, min(int(request.GET.get('per_page', 20)), 100))
        
        # Filtros
        atendimento_id = request.GET.get('id')
        lead_id = request.GET.get('lead_id')
        fluxo_id = request.GET.get('fluxo_id')
        status = request.GET.get('status')
        search = request.GET.get('search', '').strip()
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        score_min = request.GET.get('score_min')
        score_max = request.GET.get('score_max')
        apenas_ativos = _parse_bool(request.GET.get('apenas_ativos'))
        ordering = request.GET.get('ordering')
        
        # QuerySet base
        qs = AtendimentoFluxo.objects.select_related('lead', 'fluxo', 'historico_contato')
        
        # Aplicar filtros
        if atendimento_id:
            qs = qs.filter(id=atendimento_id)
        else:
            if lead_id:
                qs = qs.filter(lead_id=lead_id)
            
            if fluxo_id:
                qs = qs.filter(fluxo_id=fluxo_id)
            
            if status:
                qs = qs.filter(status=status)
            
            if apenas_ativos:
                qs = qs.filter(status__in=['iniciado', 'em_andamento', 'pausado'])
            
            if search:
                qs = qs.filter(
                    Q(lead__nome_razaosocial__icontains=search) |
                    Q(lead__telefone__icontains=search) |
                    Q(fluxo__nome__icontains=search) |
                    Q(observacoes__icontains=search)
                )
            
            if data_inicio:
                try:
                    di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    qs = qs.filter(data_inicio__date__gte=di)
                except ValueError:
                    pass
            
            if data_fim:
                try:
                    df = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    qs = qs.filter(data_inicio__date__lte=df)
                except ValueError:
                    pass
            
            if score_min:
                try:
                    score_min_int = int(score_min)
                    qs = qs.filter(score_qualificacao__gte=score_min_int)
                except ValueError:
                    pass
            
            if score_max:
                try:
                    score_max_int = int(score_max)
                    qs = qs.filter(score_qualificacao__lte=score_max_int)
                except ValueError:
                    pass
        
        # Ordenação
        allowed_order_fields = {'id', 'data_inicio', 'data_ultima_atividade', 'questao_atual', 'score_qualificacao', 'status'}
        order_by = _safe_ordering(ordering, allowed_order_fields, '-data_inicio')
        qs = qs.order_by(order_by)
        
        # Paginação
        total = qs.count()
        start = (page - 1) * per_page
        end = start + per_page
        items = qs[start:end]
        
        # Serialização
        results = [_serialize_atendimento_fluxo(item) for item in items]
        
        # Metadata adicional
        metadata = {
            'status_disponiveis': AtendimentoFluxo.STATUS_CHOICES,
            'estatisticas': {
                'total_atendimentos': total,
                'ativos': qs.filter(status__in=['iniciado', 'em_andamento', 'pausado']).count(),
                'completados': qs.filter(status='completado').count(),
                'abandonados': qs.filter(status='abandonado').count()
            }
        }
        
        return JsonResponse({
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'ordering': order_by,
            'metadata': metadata
        })
        
    except Exception as e:
        _criar_log_api('ERROR', 'consultar_atendimentos_api', f'Erro na consulta: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# APIS ESPECÍFICAS DE ATENDIMENTO
# ============================================================================

@login_required
@require_http_methods(["POST"])
def responder_questao_api(request, atendimento_id):
    """API para responder uma questão no atendimento"""
    try:
        data = _parse_json_request(request)
        if data is None:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
        
        # Campos obrigatórios
        required = ['questao_id', 'resposta']
        missing = [f for f in required if f not in data]
        if missing:
            return JsonResponse({'error': f'Campos obrigatórios ausentes: {", ".join(missing)}'}, status=400)
        
        try:
            atendimento = AtendimentoFluxo.objects.select_related('lead', 'fluxo').get(id=atendimento_id)
        except AtendimentoFluxo.DoesNotExist:
            return JsonResponse({'error': 'Atendimento não encontrado'}, status=404)
        
        try:
            questao = QuestaoFluxo.objects.get(id=data['questao_id'], fluxo=atendimento.fluxo)
        except QuestaoFluxo.DoesNotExist:
            return JsonResponse({'error': 'Questão não encontrada no fluxo do atendimento'}, status=404)
        
        # Verificar se o atendimento está em estado válido
        if atendimento.status not in ['iniciado', 'em_andamento']:
            return JsonResponse({'error': 'Atendimento não está em estado válido para receber respostas'}, status=400)
        
        # Usar o método do modelo para responder
        try:
            resultado = atendimento.responder_questao(
                indice_questao=questao.indice,
                resposta=data['resposta'],
                validar=data.get('validar', True)
            )
            
            if not resultado['sucesso']:
                return JsonResponse({'error': resultado['erro']}, status=400)
            
            # Criar registro de resposta detalhada
            resposta_obj = RespostaQuestao.objects.create(
                atendimento=atendimento,
                questao=questao,
                resposta=data['resposta'],
                valida=resultado['valida'],
                mensagem_erro=resultado.get('erro'),
                ip_origem=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                dados_extras=data.get('dados_extras', {})
            )
            
            _criar_log_api('INFO', 'responder_questao_api', f'Questão respondida', {
                'atendimento_id': atendimento.id,
                'questao_id': questao.id,
                'resposta_id': resposta_obj.id
            }, request)
            
            return JsonResponse({
                'success': True,
                'atendimento': _serialize_atendimento_fluxo(atendimento),
                'resposta': _serialize_resposta_questao(resposta_obj),
                'proxima_questao': resultado.get('proxima_questao')
            })
            
        except Exception as e:
            return JsonResponse({'error': f'Erro ao processar resposta: {str(e)}'}, status=500)
        
    except Exception as e:
        _criar_log_api('ERROR', 'responder_questao_api', f'Erro ao responder questão: {str(e)}', {'atendimento_id': atendimento_id}, request)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def finalizar_atendimento_api(request, atendimento_id):
    """API para finalizar um atendimento"""
    try:
        data = _parse_json_request(request) or {}
        
        try:
            atendimento = AtendimentoFluxo.objects.select_related('lead', 'fluxo').get(id=atendimento_id)
        except AtendimentoFluxo.DoesNotExist:
            return JsonResponse({'error': 'Atendimento não encontrado'}, status=404)
        
        sucesso = data.get('sucesso', True)
        observacoes = data.get('observacoes', '')
        
        # Usar o método do modelo para finalizar
        try:
            atendimento.finalizar_atendimento(sucesso=sucesso)
            
            if observacoes:
                atendimento.observacoes = observacoes
                atendimento.save()
            
            _criar_log_api('INFO', 'finalizar_atendimento_api', f'Atendimento finalizado', {
                'atendimento_id': atendimento.id,
                'sucesso': sucesso
            }, request)
            
            return JsonResponse({
                'success': True,
                'atendimento': _serialize_atendimento_fluxo(atendimento)
            })
            
        except Exception as e:
            return JsonResponse({'error': f'Erro ao finalizar atendimento: {str(e)}'}, status=500)
        
    except Exception as e:
        _criar_log_api('ERROR', 'finalizar_atendimento_api', f'Erro: {str(e)}', {'atendimento_id': atendimento_id}, request)
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# APIS CRUD - RESPOSTAS DE QUESTÕES
# ============================================================================

@login_required
@require_http_methods(["GET"])
def consultar_respostas_api(request):
    """API GET melhorada para consultar respostas de questões"""
    try:
        page = max(1, int(request.GET.get('page', 1)))
        per_page = max(1, min(int(request.GET.get('per_page', 20)), 100))
        
        # Filtros
        resposta_id = request.GET.get('id')
        atendimento_id = request.GET.get('atendimento_id')
        questao_id = request.GET.get('questao_id')
        lead_id = request.GET.get('lead_id')
        fluxo_id = request.GET.get('fluxo_id')
        valida = _parse_bool(request.GET.get('valida'))
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        ordering = request.GET.get('ordering')
        
        # QuerySet base
        qs = RespostaQuestao.objects.select_related('atendimento', 'questao', 'atendimento__lead', 'questao__fluxo')
        
        # Aplicar filtros
        if resposta_id:
            qs = qs.filter(id=resposta_id)
        else:
            if atendimento_id:
                qs = qs.filter(atendimento_id=atendimento_id)
            
            if questao_id:
                qs = qs.filter(questao_id=questao_id)
            
            if lead_id:
                qs = qs.filter(atendimento__lead_id=lead_id)
            
            if fluxo_id:
                qs = qs.filter(questao__fluxo_id=fluxo_id)
            
            if valida is not None:
                qs = qs.filter(valida=valida)
            
            if data_inicio:
                try:
                    di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    qs = qs.filter(data_resposta__date__gte=di)
                except ValueError:
                    pass
            
            if data_fim:
                try:
                    df = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    qs = qs.filter(data_resposta__date__lte=df)
                except ValueError:
                    pass
        
        # Ordenação
        allowed_order_fields = {'id', 'data_resposta', 'tentativas', 'tempo_resposta', 'valida'}
        order_by = _safe_ordering(ordering, allowed_order_fields, '-data_resposta')
        qs = qs.order_by(order_by)
        
        # Paginação
        total = qs.count()
        start = (page - 1) * per_page
        end = start + per_page
        items = qs[start:end]
        
        # Serialização
        results = [_serialize_resposta_questao(item) for item in items]
        
        # Metadata adicional
        metadata = {
            'estatisticas': {
                'total_respostas': total,
                'respostas_validas': qs.filter(valida=True).count(),
                'respostas_invalidas': qs.filter(valida=False).count()
            }
        }
        
        return JsonResponse({
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'ordering': order_by,
            'metadata': metadata
        })
        
    except Exception as e:
        _criar_log_api('ERROR', 'consultar_respostas_api', f'Erro na consulta: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# APIS DE ESTATÍSTICAS E RELATÓRIOS
# ============================================================================

@login_required
@require_http_methods(["GET"])
def estatisticas_atendimento_api(request):
    """API para estatísticas gerais de atendimento"""
    try:
        # Filtros de período
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        fluxo_id = request.GET.get('fluxo_id')
        
        # Base queries
        atendimentos_qs = AtendimentoFluxo.objects.all()
        respostas_qs = RespostaQuestao.objects.all()
        
        # Aplicar filtros de período
        if data_inicio:
            try:
                di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                atendimentos_qs = atendimentos_qs.filter(data_inicio__date__gte=di)
                respostas_qs = respostas_qs.filter(data_resposta__date__gte=di)
            except ValueError:
                pass
        
        if data_fim:
            try:
                df = datetime.strptime(data_fim, '%Y-%m-%d').date()
                atendimentos_qs = atendimentos_qs.filter(data_inicio__date__lte=df)
                respostas_qs = respostas_qs.filter(data_resposta__date__lte=df)
            except ValueError:
                pass
        
        if fluxo_id:
            atendimentos_qs = atendimentos_qs.filter(fluxo_id=fluxo_id)
            respostas_qs = respostas_qs.filter(questao__fluxo_id=fluxo_id)
        
        # Estatísticas de atendimentos
        total_atendimentos = atendimentos_qs.count()
        atendimentos_completados = atendimentos_qs.filter(status='completado').count()
        atendimentos_abandonados = atendimentos_qs.filter(status='abandonado').count()
        atendimentos_ativos = atendimentos_qs.filter(status__in=['iniciado', 'em_andamento', 'pausado']).count()
        
        # Taxa de completude
        taxa_completude = (atendimentos_completados / total_atendimentos * 100) if total_atendimentos > 0 else 0
        taxa_abandono = (atendimentos_abandonados / total_atendimentos * 100) if total_atendimentos > 0 else 0
        
        # Estatísticas de respostas
        total_respostas = respostas_qs.count()
        respostas_validas = respostas_qs.filter(valida=True).count()
        taxa_respostas_validas = (respostas_validas / total_respostas * 100) if total_respostas > 0 else 0
        
        # Tempo médio de atendimento
        atendimentos_com_tempo = atendimentos_qs.filter(tempo_total__isnull=False)
        tempo_medio = atendimentos_com_tempo.aggregate(Avg('tempo_total'))['tempo_total__avg'] or 0
        
        # Estatísticas por fluxo
        stats_por_fluxo = []
        for fluxo in FluxoAtendimento.objects.filter(ativo=True):
            atend_fluxo = atendimentos_qs.filter(fluxo=fluxo)
            total_fluxo = atend_fluxo.count()
            completados_fluxo = atend_fluxo.filter(status='completado').count()
            
            stats_por_fluxo.append({
                'fluxo_id': fluxo.id,
                'fluxo_nome': fluxo.nome,
                'total_atendimentos': total_fluxo,
                'completados': completados_fluxo,
                'taxa_completude': (completados_fluxo / total_fluxo * 100) if total_fluxo > 0 else 0
            })
        
        # Estatísticas por status
        stats_por_status = []
        for status_code, status_name in AtendimentoFluxo.STATUS_CHOICES:
            count = atendimentos_qs.filter(status=status_code).count()
            stats_por_status.append({
                'status': status_code,
                'status_display': status_name,
                'count': count,
                'percentual': (count / total_atendimentos * 100) if total_atendimentos > 0 else 0
            })
        
        data = {
            'periodo': {
                'data_inicio': data_inicio,
                'data_fim': data_fim
            },
            'resumo': {
                'total_atendimentos': total_atendimentos,
                'atendimentos_completados': atendimentos_completados,
                'atendimentos_abandonados': atendimentos_abandonados,
                'atendimentos_ativos': atendimentos_ativos,
                'taxa_completude': round(taxa_completude, 2),
                'taxa_abandono': round(taxa_abandono, 2),
                'tempo_medio_segundos': round(tempo_medio, 0),
                'tempo_medio_formatado': f"{int(tempo_medio // 60)}m {int(tempo_medio % 60)}s" if tempo_medio else '0s'
            },
            'respostas': {
                'total_respostas': total_respostas,
                'respostas_validas': respostas_validas,
                'taxa_respostas_validas': round(taxa_respostas_validas, 2)
            },
            'por_fluxo': stats_por_fluxo,
            'por_status': stats_por_status
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        _criar_log_api('ERROR', 'estatisticas_atendimento_api', f'Erro: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# APIS ESPECÍFICAS PARA INTEGRAÇÃO COM N8N
# ============================================================================

@csrf_exempt
@api_token_required
@require_http_methods(["POST"])
def iniciar_atendimento_n8n(request):
    """
    API para N8N iniciar um novo atendimento
    """
    try:
        data = _parse_json_request(request)
        
        # Campos obrigatórios
        required_fields = ['lead_id', 'fluxo_id']
        for field in required_fields:
            if field not in data:
                return JsonResponse({'error': f'Campo {field} é obrigatório'}, status=400)
        
        # Buscar lead
        try:
            lead = LeadProspecto.objects.get(id=data['lead_id'])
        except LeadProspecto.DoesNotExist:
            return JsonResponse({'error': 'Lead não encontrado'}, status=404)
        
        # Buscar fluxo
        try:
            fluxo = FluxoAtendimento.objects.get(id=data['fluxo_id'], ativo=True)
        except FluxoAtendimento.DoesNotExist:
            return JsonResponse({'error': 'Fluxo não encontrado ou inativo'}, status=404)
        
        # Verificar se o fluxo pode ser usado
        if not fluxo.pode_ser_usado():
            return JsonResponse({'error': 'Fluxo não pode ser usado'}, status=400)
        
        # Criar novo atendimento
        total_q = fluxo.nodos.filter(tipo='questao').count() if fluxo.modo_fluxo else fluxo.get_total_questoes()
        atendimento = AtendimentoFluxo.objects.create(
            lead=lead,
            fluxo=fluxo,
            total_questoes=total_q,
            max_tentativas=fluxo.max_tentativas,
            ip_origem=data.get('ip_origem'),
            user_agent=data.get('user_agent'),
            dispositivo=data.get('dispositivo'),
            observacoes=data.get('observacoes')
        )

        # Modo visual (node-based) vs legado (questoes lineares)
        if fluxo.modo_fluxo:
            from apps.comercial.atendimento.engine import iniciar_fluxo_visual
            resultado = iniciar_fluxo_visual(atendimento)
            response_data = {
                'atendimento_id': atendimento.id,
                'lead_id': lead.id,
                'fluxo_id': fluxo.id,
                'status': atendimento.status,
                'modo_fluxo': True,
                'total_questoes': total_q,
                'progresso_percentual': atendimento.get_progresso_percentual(),
                'resultado': resultado,
                'data_inicio': atendimento.data_inicio.isoformat()
            }
        else:
            # Buscar primeira questão (legado)
            primeira_questao = fluxo.get_questao_por_indice(1)
            response_data = {
                'atendimento_id': atendimento.id,
                'lead_id': lead.id,
                'fluxo_id': fluxo.id,
                'status': atendimento.status,
                'questao_atual': atendimento.questao_atual,
                'total_questoes': atendimento.total_questoes,
                'progresso_percentual': atendimento.get_progresso_percentual(),
                'primeira_questao': _serialize_questao_fluxo(primeira_questao) if primeira_questao else None,
                'data_inicio': atendimento.data_inicio.isoformat()
            }

        _criar_log_api('INFO', 'iniciar_atendimento_n8n', f'Atendimento {atendimento.id} iniciado para lead {lead.id} (modo_fluxo={fluxo.modo_fluxo})', request=request)

        return JsonResponse(response_data, status=201)
        
    except Exception as e:
        _criar_log_api('ERROR', 'iniciar_atendimento_n8n', f'Erro: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@api_token_required
@require_http_methods(["GET"])
def consultar_atendimento_n8n(request, atendimento_id):
    """
    API para N8N consultar status atual de um atendimento
    """
    try:
        # Buscar atendimento
        try:
            atendimento = AtendimentoFluxo.objects.get(id=atendimento_id)
        except AtendimentoFluxo.DoesNotExist:
            return JsonResponse({'error': 'Atendimento não encontrado'}, status=404)
        
        # Buscar questão atual
        questao_atual = atendimento.get_questao_atual_obj()
        
        # Buscar próxima questão
        proxima_questao = atendimento.get_proxima_questao()
        
        response_data = {
            'atendimento_id': atendimento.id,
            'lead_id': atendimento.lead.id,
            'lead_nome': atendimento.lead.nome_razaosocial,
            'lead_telefone': atendimento.lead.telefone,
            'fluxo_id': atendimento.fluxo.id,
            'fluxo_nome': atendimento.fluxo.nome,
            'status': atendimento.status,
            'questao_atual': atendimento.questao_atual,
            'total_questoes': atendimento.total_questoes,
            'questoes_respondidas': atendimento.questoes_respondidas,
            'progresso_percentual': atendimento.get_progresso_percentual(),
            'questao_atual_obj': _serialize_questao_fluxo(questao_atual) if questao_atual else None,
            'proxima_questao': _serialize_questao_fluxo(proxima_questao) if proxima_questao else None,
            'pode_avancar': atendimento.pode_avancar(),
            'pode_voltar': atendimento.pode_voltar(),
            'data_inicio': atendimento.data_inicio.isoformat(),
            'data_ultima_atividade': atendimento.data_ultima_atividade.isoformat(),
            'data_conclusao': atendimento.data_conclusao.isoformat() if atendimento.data_conclusao else None,
            'tempo_formatado': atendimento.get_tempo_formatado(),
            'respostas': atendimento.dados_respostas or {}
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        _criar_log_api('ERROR', 'consultar_atendimento_n8n', f'Erro: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@api_token_required
@require_http_methods(["POST"])
def responder_questao_n8n(request, atendimento_id):
    """
    API para N8N registrar resposta de uma questão
    """
    try:
        data = _parse_json_request(request)
        
        # Campos obrigatórios
        if 'resposta' not in data:
            return JsonResponse({'error': 'Campo resposta é obrigatório'}, status=400)
        
        # Buscar atendimento
        try:
            atendimento = AtendimentoFluxo.objects.get(id=atendimento_id)
        except AtendimentoFluxo.DoesNotExist:
            return JsonResponse({'error': 'Atendimento não encontrado'}, status=404)
        
        # Verificar se atendimento está ativo
        if atendimento.status not in ['iniciado', 'em_andamento', 'pausado']:
            return JsonResponse({'error': 'Atendimento não está ativo'}, status=400)

        # Modo visual (node-based)
        if atendimento.fluxo.modo_fluxo:
            from apps.comercial.atendimento.engine import processar_resposta_visual
            resultado = processar_resposta_visual(atendimento, data['resposta'])

            if atendimento.status == 'iniciado':
                atendimento.status = 'em_andamento'
                atendimento.save(update_fields=['status'])

            return JsonResponse({
                'success': resultado.get('tipo') != 'erro',
                'modo_fluxo': True,
                'atendimento_id': atendimento.id,
                'questoes_respondidas': atendimento.questoes_respondidas,
                'progresso_percentual': atendimento.get_progresso_percentual(),
                'resultado': resultado,
            })

        # Modo legado (questoes lineares)
        # Determinar índice da questão (usar atual ou especificada)
        indice_questao = data.get('indice_questao', atendimento.questao_atual)

        # Obter IP e User Agent para rastreamento inteligente
        ip_origem = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Usar método inteligente se disponível, caso contrário usar método tradicional
        if hasattr(atendimento, 'responder_questao_inteligente'):
            sucesso, mensagem, proxima_acao, dados_extras = atendimento.responder_questao_inteligente(
                indice_questao=indice_questao,
                resposta=data['resposta'],
                contexto=data.get('contexto', {}),
                ip_origem=ip_origem,
                user_agent=user_agent
            )
            
            # Processar próxima ação
            response_extra = {
                'proxima_acao': proxima_acao,
                'dados_extras': dados_extras
            }
            
            if not sucesso:
                # Incluir informações sobre tentativas para N8N decidir o que fazer
                response_extra.update({
                    'pode_tentar_novamente': proxima_acao.get('acao') == 'repetir',
                    'tentativas_restantes': dados_extras.get('tentativas_restantes', 0),
                    'instrucoes_correcao': dados_extras.get('instrucoes_correcao', ''),
                    'estrategia_aplicada': dados_extras.get('estrategia_aplicada', '')
                })
                return JsonResponse({
                    'success': False,
                    'error': mensagem,
                    **response_extra
                }, status=400)
        else:
            # Fallback para método tradicional
            sucesso, mensagem = atendimento.responder_questao(
                indice_questao=indice_questao,
                resposta=data['resposta'],
                validar=data.get('validar', True)
            )
            
            response_extra = {}
            
            if not sucesso:
                return JsonResponse({'error': mensagem}, status=400)
        
        # Atualizar status para em_andamento se ainda estava iniciado
        if atendimento.status == 'iniciado':
            atendimento.status = 'em_andamento'
            atendimento.save()
        
        # Criar registro detalhado de resposta se solicitado
        if data.get('criar_registro_detalhado', False):
            questao = atendimento.fluxo.get_questao_por_indice(indice_questao)
            if questao:
                RespostaQuestao.objects.create(
                    atendimento=atendimento,
                    questao=questao,
                    resposta=data['resposta'],
                    valida=sucesso,
                    ip_origem=data.get('ip_origem'),
                    user_agent=data.get('user_agent'),
                    dados_extras=data.get('dados_extras')
                )
        
        # Buscar questão atual após resposta
        questao_atual = atendimento.get_questao_atual_obj()
        proxima_questao = atendimento.get_proxima_questao()
        
        response_data = {
            'success': True,
            'mensagem': mensagem,
            'atendimento_id': atendimento.id,
            'questao_respondida': indice_questao,
            'questao_atual': atendimento.questao_atual,
            'questoes_respondidas': atendimento.questoes_respondidas,
            'progresso_percentual': atendimento.get_progresso_percentual(),
            'questao_atual_obj': _serialize_questao_fluxo(questao_atual) if questao_atual else None,
            'proxima_questao': _serialize_questao_fluxo(proxima_questao) if proxima_questao else None,
            'pode_avancar': atendimento.pode_avancar(),
            'atendimento_status': atendimento.status,
            **response_extra  # Inclui informações extras do fluxo inteligente
        }
        
        _criar_log_api('INFO', 'responder_questao_n8n', f'Resposta registrada para atendimento {atendimento.id}, questão {indice_questao}', request=request)
        
        return JsonResponse(response_data)
        
    except Exception as e:
        _criar_log_api('ERROR', 'responder_questao_n8n', f'Erro: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@api_token_required
@require_http_methods(["POST"])
def avancar_questao_n8n(request, atendimento_id):
    """
    API para N8N avançar para próxima questão
    """
    try:
        # Buscar atendimento
        try:
            atendimento = AtendimentoFluxo.objects.get(id=atendimento_id)
        except AtendimentoFluxo.DoesNotExist:
            return JsonResponse({'error': 'Atendimento não encontrado'}, status=404)
        
        # Tentar avançar questão
        sucesso, proxima_questao = atendimento.avancar_questao()
        
        if not sucesso:
            return JsonResponse({'error': 'Não é possível avançar'}, status=400)
        
        response_data = {
            'sucesso': True,
            'atendimento_id': atendimento.id,
            'questao_atual': atendimento.questao_atual,
            'questoes_respondidas': atendimento.questoes_respondidas,
            'progresso_percentual': atendimento.get_progresso_percentual(),
            'atendimento_status': atendimento.status
        }
        
        if proxima_questao:
            response_data['proxima_questao'] = _serialize_questao_fluxo(proxima_questao)
            response_data['finalizado'] = False
        else:
            response_data['proxima_questao'] = None
            response_data['finalizado'] = True
            response_data['data_conclusao'] = atendimento.data_conclusao.isoformat() if atendimento.data_conclusao else None
        
        _criar_log_api('INFO', 'avancar_questao_n8n', f'Questão avançada para atendimento {atendimento.id}', request=request)
        
        return JsonResponse(response_data)
        
    except Exception as e:
        _criar_log_api('ERROR', 'avancar_questao_n8n', f'Erro: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@api_token_required
@require_http_methods(["POST"])
def finalizar_atendimento_n8n(request, atendimento_id):
    """
    API para N8N finalizar um atendimento
    """
    try:
        data = _parse_json_request(request)
        
        # Buscar atendimento
        try:
            atendimento = AtendimentoFluxo.objects.get(id=atendimento_id)
        except AtendimentoFluxo.DoesNotExist:
            return JsonResponse({'error': 'Atendimento não encontrado'}, status=404)
        
        # Determinar se foi sucesso ou não
        sucesso = data.get('sucesso', True)
        
        # Adicionar observações se fornecidas
        if data.get('observacoes'):
            if atendimento.observacoes:
                atendimento.observacoes += f"\n\n{data['observacoes']}"
            else:
                atendimento.observacoes = data['observacoes']
            atendimento.save()
        
        # Finalizar atendimento
        atendimento.finalizar_atendimento(sucesso=sucesso)
        
        response_data = {
            'sucesso': True,
            'atendimento_id': atendimento.id,
            'status': atendimento.status,
            'data_conclusao': atendimento.data_conclusao.isoformat() if atendimento.data_conclusao else None,
            'tempo_total': atendimento.tempo_total,
            'tempo_formatado': atendimento.get_tempo_formatado(),
            'score_qualificacao': atendimento.score_qualificacao,
            'questoes_respondidas': atendimento.questoes_respondidas,
            'total_questoes': atendimento.total_questoes,
            'progresso_percentual': atendimento.get_progresso_percentual()
        }
        
        _criar_log_api('INFO', 'finalizar_atendimento_n8n', f'Atendimento {atendimento.id} finalizado com sucesso={sucesso}', request=request)
        
        return JsonResponse(response_data)
        
    except Exception as e:
        _criar_log_api('ERROR', 'finalizar_atendimento_n8n', f'Erro: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@api_token_required
@require_http_methods(["GET"])
def buscar_lead_por_telefone_n8n(request):
    """
    API para N8N buscar lead por telefone
    """
    try:
        telefone = request.GET.get('telefone')
        if not telefone:
            return JsonResponse({'error': 'Parâmetro telefone é obrigatório'}, status=400)
        
        # Buscar lead por telefone
        leads = LeadProspecto.objects.filter(telefone=telefone, ativo=True).order_by('-data_cadastro')
        
        if not leads.exists():
            return JsonResponse({'encontrado': False, 'leads': []})
        
        # Serializar leads encontrados
        leads_data = []
        for lead in leads[:5]:  # Limitar a 5 resultados
            leads_data.append({
                'id': lead.id,
                'nome': lead.nome_razaosocial,
                'email': lead.email,
                'telefone': lead.telefone,
                'origem': lead.origem,
                'status_api': lead.status_api,
                'data_cadastro': lead.data_cadastro.isoformat(),
                'score_qualificacao': lead.score_qualificacao,
                'total_contatos': lead.get_total_contatos(),
                'total_atendimentos': lead.atendimentos_fluxo.count()
            })
        
        return JsonResponse({
            'encontrado': True,
            'total_encontrados': leads.count(),
            'leads': leads_data
        })
        
    except Exception as e:
        _criar_log_api('ERROR', 'buscar_lead_por_telefone_n8n', f'Erro: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@api_token_required
@require_http_methods(["GET"])
def listar_fluxos_ativos_n8n(request):
    """
    API para N8N listar fluxos ativos
    """
    try:
        tipo_fluxo = request.GET.get('tipo')
        
        fluxos_qs = FluxoAtendimento.objects.filter(ativo=True, status='ativo')
        
        if tipo_fluxo:
            fluxos_qs = fluxos_qs.filter(tipo_fluxo=tipo_fluxo)
        
        fluxos_data = []
        for fluxo in fluxos_qs:
            fluxos_data.append({
                'id': fluxo.id,
                'nome': fluxo.nome,
                'descricao': fluxo.descricao,
                'tipo_fluxo': fluxo.tipo_fluxo,
                'total_questoes': fluxo.get_total_questoes(),
                'max_tentativas': fluxo.max_tentativas,
                'tempo_limite_minutos': fluxo.tempo_limite_minutos,
                'permite_pular_questoes': fluxo.permite_pular_questoes,
                'estatisticas': fluxo.get_estatisticas()
            })
        
        return JsonResponse({
            'fluxos': fluxos_data,
            'total': len(fluxos_data)
        })
        
    except Exception as e:
        _criar_log_api('ERROR', 'listar_fluxos_ativos_n8n', f'Erro: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@api_token_required
@require_http_methods(["GET"])
def obter_questao_n8n(request, fluxo_id, indice_questao):
    """
    API para N8N obter uma questão específica de um fluxo
    """
    try:
        # Buscar fluxo
        try:
            fluxo = FluxoAtendimento.objects.get(id=fluxo_id, ativo=True)
        except FluxoAtendimento.DoesNotExist:
            return JsonResponse({'error': 'Fluxo não encontrado'}, status=404)
        
        # Buscar questão
        questao = fluxo.get_questao_por_indice(indice_questao)
        if not questao:
            return JsonResponse({'error': 'Questão não encontrada'}, status=404)
        
        response_data = _serialize_questao_fluxo(questao)
        
        return JsonResponse(response_data)
        
    except Exception as e:
        _criar_log_api('ERROR', 'obter_questao_n8n', f'Erro: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


def _serialize_questao_fluxo(questao):
    """Serializa uma questão do fluxo para JSON"""
    if not questao:
        return None
    
    return {
        'id': questao.id,
        'indice': questao.indice,
        'titulo': questao.titulo,
        'descricao': questao.descricao,
        'tipo_questao': questao.tipo_questao,
        'tipo_validacao': questao.tipo_validacao,
        'opcoes_resposta': questao.opcoes_resposta,
        'resposta_padrao': questao.resposta_padrao,
        'regex_validacao': questao.regex_validacao,
        'tamanho_minimo': questao.tamanho_minimo,
        'tamanho_maximo': questao.tamanho_maximo,
        'valor_minimo': questao.valor_minimo,
        'valor_maximo': questao.valor_maximo,
        'permite_voltar': questao.permite_voltar,
        'permite_editar': questao.permite_editar,
        'questao_dependencia_id': questao.questao_dependencia.id if questao.questao_dependencia else None,
        'valor_dependencia': questao.valor_dependencia
    }


@csrf_exempt
@api_token_required
@require_http_methods(["POST"])
def criar_lead_n8n(request):
    """
    API para N8N criar um novo lead caso não exista
    """
    try:
        data = _parse_json_request(request)
        
        # Campos obrigatórios
        required_fields = ['nome_razaosocial', 'telefone']
        for field in required_fields:
            if field not in data:
                return JsonResponse({'error': f'Campo {field} é obrigatório'}, status=400)
        
        # Verificar se lead já existe
        lead_existente = LeadProspecto.objects.filter(
            telefone=data['telefone'],
            ativo=True
        ).first()
        
        if lead_existente:
            return JsonResponse({
                'lead_existente': True,
                'lead_id': lead_existente.id,
                'lead': {
                    'id': lead_existente.id,
                    'nome': lead_existente.nome_razaosocial,
                    'email': lead_existente.email,
                    'telefone': lead_existente.telefone,
                    'origem': lead_existente.origem,
                    'status_api': lead_existente.status_api,
                    'data_cadastro': lead_existente.data_cadastro.isoformat()
                }
            })
        
        # Criar novo lead
        lead = LeadProspecto.objects.create(
            nome_razaosocial=data['nome_razaosocial'],
            telefone=data['telefone'],
            email=data.get('email'),
            valor=data.get('valor', 0),
            empresa=data.get('empresa'),
            origem=data.get('origem', 'whatsapp'),
            canal_entrada=data.get('canal_entrada', 'whatsapp'),
            tipo_entrada=data.get('tipo_entrada', 'contato_whatsapp'),
            cpf_cnpj=data.get('cpf_cnpj'),
            endereco=data.get('endereco'),
            rua=data.get('rua'),
            numero_residencia=data.get('numero_residencia'),
            bairro=data.get('bairro'),
            cidade=data.get('cidade'),
            estado=data.get('estado'),
            cep=data.get('cep'),
            observacoes=data.get('observacoes'),
            status_api='pendente'
        )
        
        # Criar histórico de contato se fornecidos dados
        if data.get('criar_historico_contato', True):
            HistoricoContato.objects.create(
                lead=lead,
                telefone=lead.telefone,
                nome_contato=lead.nome_razaosocial,
                status='fluxo_inicializado',
                observacoes=f"Lead criado via N8N - Origem: {lead.origem}",
                origem_contato=lead.origem,
                ip_origem=data.get('ip_origem'),
                user_agent=data.get('user_agent')
            )
        
        response_data = {
            'lead_existente': False,
            'lead_criado': True,
            'lead_id': lead.id,
            'lead': {
                'id': lead.id,
                'nome': lead.nome_razaosocial,
                'email': lead.email,
                'telefone': lead.telefone,
                'origem': lead.origem,
                'status_api': lead.status_api,
                'data_cadastro': lead.data_cadastro.isoformat()
            }
        }
        
        _criar_log_api('INFO', 'criar_lead_n8n', f'Lead {lead.id} criado via N8N para telefone {lead.telefone}', request=request)
        
        return JsonResponse(response_data, status=201)
        
    except Exception as e:
        _criar_log_api('ERROR', 'criar_lead_n8n', f'Erro: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@api_token_required
@require_http_methods(["POST"])
def pausar_atendimento_n8n(request, atendimento_id):
    """
    API para N8N pausar um atendimento
    """
    try:
        data = _parse_json_request(request)
        
        # Buscar atendimento
        try:
            atendimento = AtendimentoFluxo.objects.get(id=atendimento_id)
        except AtendimentoFluxo.DoesNotExist:
            return JsonResponse({'error': 'Atendimento não encontrado'}, status=404)
        
        # Verificar se pode ser pausado
        if atendimento.status not in ['iniciado', 'em_andamento']:
            return JsonResponse({'error': 'Atendimento não pode ser pausado'}, status=400)
        
        # Pausar atendimento
        atendimento.status = 'pausado'
        
        # Adicionar observações se fornecidas
        if data.get('motivo_pausa'):
            if atendimento.observacoes:
                atendimento.observacoes += f"\n\nPausado em {timezone.now().strftime('%d/%m/%Y %H:%M')}: {data['motivo_pausa']}"
            else:
                atendimento.observacoes = f"Pausado em {timezone.now().strftime('%d/%m/%Y %H:%M')}: {data['motivo_pausa']}"
        
        atendimento.save()
        
        response_data = {
            'sucesso': True,
            'atendimento_id': atendimento.id,
            'status': atendimento.status,
            'data_pausa': atendimento.data_ultima_atividade.isoformat()
        }
        
        _criar_log_api('INFO', 'pausar_atendimento_n8n', f'Atendimento {atendimento.id} pausado', request=request)
        
        return JsonResponse(response_data)
        
    except Exception as e:
        _criar_log_api('ERROR', 'pausar_atendimento_n8n', f'Erro: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@api_token_required
@require_http_methods(["POST"])
def retomar_atendimento_n8n(request, atendimento_id):
    """
    API para N8N retomar um atendimento pausado
    """
    try:
        data = _parse_json_request(request)
        
        # Buscar atendimento
        try:
            atendimento = AtendimentoFluxo.objects.get(id=atendimento_id)
        except AtendimentoFluxo.DoesNotExist:
            return JsonResponse({'error': 'Atendimento não encontrado'}, status=404)
        
        # Verificar se está pausado
        if atendimento.status != 'pausado':
            return JsonResponse({'error': 'Atendimento não está pausado'}, status=400)
        
        # Retomar atendimento
        atendimento.status = 'em_andamento'
        
        # Adicionar observações se fornecidas
        if data.get('observacoes_retomada'):
            if atendimento.observacoes:
                atendimento.observacoes += f"\n\nRetomado em {timezone.now().strftime('%d/%m/%Y %H:%M')}: {data['observacoes_retomada']}"
            else:
                atendimento.observacoes = f"Retomado em {timezone.now().strftime('%d/%m/%Y %H:%M')}: {data['observacoes_retomada']}"
        
        atendimento.save()
        
        # Buscar questão atual
        questao_atual = atendimento.get_questao_atual_obj()
        
        response_data = {
            'sucesso': True,
            'atendimento_id': atendimento.id,
            'status': atendimento.status,
            'questao_atual': atendimento.questao_atual,
            'questao_atual_obj': _serialize_questao_fluxo(questao_atual) if questao_atual else None,
            'progresso_percentual': atendimento.get_progresso_percentual(),
            'data_retomada': atendimento.data_ultima_atividade.isoformat()
        }
        
        _criar_log_api('INFO', 'retomar_atendimento_n8n', f'Atendimento {atendimento.id} retomado', request=request)
        
        return JsonResponse(response_data)
        
    except Exception as e:
        _criar_log_api('ERROR', 'retomar_atendimento_n8n', f'Erro: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# APIS ESPECÍFICAS PARA FLUXO INTELIGENTE
# ============================================================================

@csrf_exempt
@api_token_required
@require_http_methods(["GET"])
def consultar_tentativas_resposta_n8n(request, atendimento_id):
    """
    API para N8N consultar tentativas de resposta de um atendimento
    """
    try:
        # Buscar atendimento
        try:
            atendimento = AtendimentoFluxo.objects.get(id=atendimento_id)
        except AtendimentoFluxo.DoesNotExist:
            return JsonResponse({'error': 'Atendimento não encontrado'}, status=404)
        
        # Buscar tentativas
        tentativas = TentativaResposta.objects.filter(
            atendimento=atendimento
        ).order_by('-data_tentativa')
        
        # Filtros opcionais
        questao_id = request.GET.get('questao_id')
        if questao_id:
            tentativas = tentativas.filter(questao_id=questao_id)
        
        valida = request.GET.get('valida')
        if valida is not None:
            tentativas = tentativas.filter(valida=_parse_bool(valida))
        
        # Paginação simples
        limit = int(request.GET.get('limit', 50))
        tentativas = tentativas[:limit]
        
        # Serializar tentativas
        tentativas_data = [_serialize_tentativa_resposta(t) for t in tentativas]
        
        response_data = {
            'atendimento_id': atendimento.id,
            'total_tentativas': len(tentativas_data),
            'tentativas': tentativas_data,
            'estatisticas': atendimento.get_estatisticas_tentativas() if hasattr(atendimento, 'get_estatisticas_tentativas') else {}
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        _criar_log_api('ERROR', 'consultar_tentativas_resposta_n8n', f'Erro: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@api_token_required
@require_http_methods(["GET"])
def obter_questao_inteligente_n8n(request, fluxo_id, indice_questao):
    """
    API para N8N obter uma questão com todas as informações inteligentes
    """
    try:
        # Buscar fluxo
        try:
            fluxo = FluxoAtendimento.objects.get(id=fluxo_id)
        except FluxoAtendimento.DoesNotExist:
            return JsonResponse({'error': 'Fluxo não encontrado'}, status=404)
        
        # Buscar questão
        questao = fluxo.get_questao_por_indice(indice_questao)
        if not questao:
            return JsonResponse({'error': 'Questão não encontrada'}, status=404)
        
        # Contexto opcional para renderização dinâmica
        contexto = {}
        if request.GET.get('contexto'):
            try:
                contexto = json.loads(request.GET.get('contexto'))
            except:
                pass
        
        # Serializar questão com detalhes inteligentes
        questao_data = _serialize_questao_fluxo(questao, incluir_detalhes_inteligentes=True)
        
        # Adicionar opções dinâmicas renderizadas se necessário
        if questao.opcoes_dinamicas_fonte:
            questao_data['opcoes_dinamicas_renderizadas'] = questao.get_opcoes_formatadas(contexto)
        
        # Adicionar questão renderizada se há template
        if questao.template_questao:
            questao_data['questao_renderizada'] = questao.get_questao_renderizada(contexto)
        
        response_data = {
            'fluxo_id': fluxo.id,
            'fluxo_nome': fluxo.nome,
            'questao': questao_data
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        _criar_log_api('ERROR', 'obter_questao_inteligente_n8n', f'Erro: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@api_token_required
@require_http_methods(["GET"])
def estatisticas_atendimento_inteligente_n8n(request, atendimento_id):
    """
    API para N8N obter estatísticas detalhadas de um atendimento inteligente
    """
    try:
        # Buscar atendimento
        try:
            atendimento = AtendimentoFluxo.objects.get(id=atendimento_id)
        except AtendimentoFluxo.DoesNotExist:
            return JsonResponse({'error': 'Atendimento não encontrado'}, status=404)
        
        # Obter estatísticas básicas
        estatisticas_basicas = {
            'atendimento_id': atendimento.id,
            'status': atendimento.status,
            'progresso_percentual': atendimento.get_progresso_percentual(),
            'questoes_respondidas': atendimento.questoes_respondidas,
            'total_questoes': atendimento.total_questoes,
            'tempo_formatado': atendimento.get_tempo_formatado() if hasattr(atendimento, 'get_tempo_formatado') else None
        }
        
        # Obter estatísticas de tentativas se disponível
        estatisticas_tentativas = {}
        if hasattr(atendimento, 'get_estatisticas_tentativas'):
            estatisticas_tentativas = atendimento.get_estatisticas_tentativas()
        
        # Obter questões problemáticas se disponível
        questoes_problematicas = []
        if hasattr(atendimento, 'get_questoes_problematicas'):
            questoes_problematicas = atendimento.get_questoes_problematicas()
        
        response_data = {
            **estatisticas_basicas,
            'estatisticas_tentativas': estatisticas_tentativas,
            'questoes_problematicas': questoes_problematicas,
            'contexto_dinamico': atendimento.get_contexto_dinamico() if hasattr(atendimento, 'get_contexto_dinamico') else {}
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        _criar_log_api('ERROR', 'estatisticas_atendimento_inteligente_n8n', f'Erro: {str(e)}', request=request)
        return JsonResponse({'error': str(e)}, status=500)