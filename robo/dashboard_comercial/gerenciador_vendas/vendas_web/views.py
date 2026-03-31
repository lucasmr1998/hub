# ============================================================================
# IMPORTS
# ============================================================================
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.contrib.auth.decorators import login_required

from apps.sistema.decorators import api_token_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from django.db import models
from datetime import datetime, timedelta
from decimal import Decimal
import json
import traceback
import logging

# Setup logger
logger = logging.getLogger(__name__)

# ============================================================================
# VIEWS DE AUTENTICAÇÃO
# ============================================================================

def home_view(request):
    """View para página inicial - redireciona baseado no status de autenticação"""
    if request.user.is_authenticated:
        return redirect('vendas_web:dashboard1')
    else:
        return redirect('vendas_web:login')

def login_view(request):
    """View para página de login"""
    if request.user.is_authenticated:
        return redirect('vendas_web:dashboard1')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Bem-vindo, {user.first_name or user.username}!')
                return redirect('vendas_web:dashboard1')
            else:
                messages.error(request, 'Usuário ou senha incorretos.')
        else:
            messages.error(request, 'Por favor, preencha todos os campos.')
    
    from .models import ConfiguracaoEmpresa
    config = ConfiguracaoEmpresa.get_configuracao_ativa()
    return render(request, 'vendas_web/login.html', {'config_empresa': config})

def logout_view(request):
    """View personalizada para logout"""
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, 'Você foi desconectado com sucesso.')
    return redirect('vendas_web:home')

# Models
from .models import (
    LeadProspecto, 
    ImagemLeadProspecto,
    Prospecto, 
    HistoricoContato, 
    ConfiguracaoSistema, 
    LogSistema,
    FluxoAtendimento, 
    QuestaoFluxo, 
    AtendimentoFluxo, 
    RespostaQuestao,
    ConfiguracaoCadastro,
    PlanoInternet,
    OpcaoVencimento,
    CadastroCliente, 
    DocumentoLead,
    ConfiguracaoRecontato,
    CidadeViabilidade,
)
from apps.integracoes.models import ClienteHubsoft


# ============================================================================
# FUNÇÕES DE SERIALIZAÇÃO - APIs de Atendimento
# ============================================================================

def _serialize_fluxo_atendimento(fluxo):
    """Serializa um objeto FluxoAtendimento"""
    try:
        return {
            'id': fluxo.id,
            'nome': fluxo.nome,
            'descricao': fluxo.descricao,
            'tipo_fluxo': fluxo.tipo_fluxo,
            'ativo': fluxo.ativo,
            'data_criacao': fluxo.data_criacao.isoformat() if fluxo.data_criacao else None,
            'data_atualizacao': fluxo.data_atualizacao.isoformat() if fluxo.data_atualizacao else None,
            'total_questoes': getattr(fluxo, 'get_total_questoes', lambda: 0)(),
            'total_atendimentos': getattr(fluxo, 'get_total_atendimentos', lambda: 0)(),
            'taxa_completacao': getattr(fluxo, 'get_taxa_completacao', lambda: '0.0%')(),
            'status': getattr(fluxo, 'get_status_display', lambda: 'N/A')(),
            'prioridade': getattr(fluxo, 'prioridade', None),
            'tags': getattr(fluxo, 'tags', ''),
            'configuracoes': getattr(fluxo, 'configuracoes', {}),
            'estatisticas': getattr(fluxo, 'get_estatisticas', lambda: {})()
        }
    except Exception as e:
        return {
            'id': fluxo.id,
            'nome': getattr(fluxo, 'nome', 'N/A'),
            'error': f'Erro na serialização: {str(e)}'
        }


def _serialize_questao_fluxo(questao):
    """Serializa um objeto QuestaoFluxo"""
    try:
        return {
            'id': questao.id,
            'fluxo_id': questao.fluxo.id if questao.fluxo else None,
            'fluxo_nome': questao.fluxo.nome if questao.fluxo else 'N/A',
            'indice': questao.indice,
            'titulo': questao.titulo,
            'descricao': questao.descricao,
            'tipo_questao': questao.tipo_questao,
            'tipo_validacao': questao.tipo_validacao,
            'opcoes_resposta': getattr(questao, 'get_opcoes_formatadas', lambda: [])(),
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
            'ordem_exibicao': questao.ordem_exibicao
        }
    except Exception as e:
        return {
            'id': questao.id,
            'titulo': getattr(questao, 'titulo', 'N/A'),
            'error': f'Erro na serialização: {str(e)}'
        }


def _serialize_atendimento_fluxo(atendimento):
    """Serializa um objeto AtendimentoFluxo"""
    try:
        return {
            'id': atendimento.id,
            'lead_id': atendimento.lead.id if atendimento.lead else None,
            'lead_nome': atendimento.lead.nome_razaosocial if atendimento.lead else 'N/A',
            'fluxo_id': atendimento.fluxo.id if atendimento.fluxo else None,
            'fluxo_nome': atendimento.fluxo.nome if atendimento.fluxo else 'N/A',
            'historico_contato_id': atendimento.historico_contato.id if atendimento.historico_contato else None,
            'status': atendimento.status,
            'status_display': getattr(atendimento, 'get_status_display', lambda: 'N/A')(),
            'questao_atual': atendimento.questao_atual,
            'total_questoes': atendimento.total_questoes,
            'questoes_respondidas': atendimento.questoes_respondidas,
            'progresso_percentual': getattr(atendimento, 'get_progresso_percentual', lambda: 0)(),
            'data_inicio': atendimento.data_inicio.isoformat() if atendimento.data_inicio else None,
            'data_ultima_atividade': atendimento.data_ultima_atividade.isoformat() if atendimento.data_ultima_atividade else None,
            'data_conclusao': atendimento.data_conclusao.isoformat() if atendimento.data_conclusao else None,
            'tempo_total': atendimento.tempo_total,
            'tempo_formatado': getattr(atendimento, 'get_tempo_formatado', lambda: 'N/A')(),
            'tentativas_atual': atendimento.tentativas_atual,
            'max_tentativas': atendimento.max_tentativas,
            'dados_respostas': atendimento.dados_respostas,
            'respostas_formatadas': getattr(atendimento, 'get_respostas_formatadas', lambda: [])(),
            'observacoes': atendimento.observacoes,
            'ip_origem': atendimento.ip_origem,
            'user_agent': atendimento.user_agent,
            'dispositivo': atendimento.dispositivo,
            'id_externo': atendimento.id_externo,
            'resultado_final': atendimento.resultado_final,
            'score_qualificacao': atendimento.score_qualificacao,
            'pode_avancar': getattr(atendimento, 'pode_avancar', lambda: False)(),
            'pode_voltar': getattr(atendimento, 'pode_voltar', lambda: False)(),
            'pode_ser_reiniciado': getattr(atendimento, 'pode_ser_reiniciado', lambda: False)()
        }
    except Exception as e:
        return {
            'id': atendimento.id,
            'error': f'Erro na serialização: {str(e)}'
        }


# ============================================================================
# APIs de Atendimento - Fluxos, Questões, Atendimentos e Respostas
# ============================================================================

@require_http_methods(["GET"])
def consultar_fluxos_api(request):
    """API GET para consultar fluxos de atendimento"""
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        per_page = max(1, min(per_page, 100))

        fluxo_id = request.GET.get('id')
        search = request.GET.get('search')
        tipo_fluxo = request.GET.get('tipo_fluxo')
        ativo = request.GET.get('ativo')
        status = request.GET.get('status')
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        ordering = request.GET.get('ordering')

        qs = FluxoAtendimento.objects.all()

        if fluxo_id:
            qs = qs.filter(id=fluxo_id)
        else:
            if search:
                qs = qs.filter(
                    Q(nome__icontains=search) |
                    Q(descricao__icontains=search) |
                    Q(tags__icontains=search)
                )

            if tipo_fluxo:
                qs = qs.filter(tipo_fluxo=tipo_fluxo)

            if ativo is not None:
                ativo_bool = ativo.lower() in ['true', '1', 'sim', 'yes']
                qs = qs.filter(ativo=ativo_bool)

            if status:
                qs = qs.filter(status=status)

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
        allowed_order_fields = {'id', 'nome', 'data_criacao', 'data_atualizacao', 'prioridade', 'tipo_fluxo'}
        if ordering and ordering.lstrip('-') in allowed_order_fields:
            order_by = ordering
        else:
            order_by = '-data_criacao'
        
        qs = qs.order_by(order_by)

        total = qs.count()
        start = (page - 1) * per_page
        end = start + per_page
        items = qs[start:end]

        results = []
        for item in items:
            results.append(_serialize_fluxo_atendimento(item))

        return JsonResponse({
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'ordering': order_by,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def consultar_questoes_api(request):
    """API GET para consultar questões de fluxo"""
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        per_page = max(1, min(per_page, 100))

        questao_id = request.GET.get('id')
        fluxo_id = request.GET.get('fluxo_id')
        search = request.GET.get('search')
        tipo_questao = request.GET.get('tipo_questao')
        tipo_validacao = request.GET.get('tipo_validacao')
        ativo = request.GET.get('ativo')
        indice = request.GET.get('indice')
        ordering = request.GET.get('ordering')

        qs = QuestaoFluxo.objects.select_related('fluxo', 'questao_dependencia')

        if questao_id:
            qs = qs.filter(id=questao_id)
        else:
            if fluxo_id:
                qs = qs.filter(fluxo_id=fluxo_id)

            if search:
                qs = qs.filter(
                    Q(titulo__icontains=search) |
                    Q(descricao__icontains=search)
                )

            if tipo_questao:
                qs = qs.filter(tipo_questao=tipo_questao)

            if tipo_validacao:
                qs = qs.filter(tipo_validacao=tipo_validacao)

            if ativo is not None:
                ativo_bool = ativo.lower() in ['true', '1', 'sim', 'yes']
                qs = qs.filter(ativo=ativo_bool)

            if indice:
                try:
                    indice_int = int(indice)
                    qs = qs.filter(indice=indice_int)
                except ValueError:
                    pass

        # Ordenação
        allowed_order_fields = {'id', 'indice', 'titulo', 'tipo_questao', 'ordem_exibicao'}
        if ordering and ordering.lstrip('-') in allowed_order_fields:
            order_by = ordering
        else:
            order_by = 'fluxo__id, indice'
        
        qs = qs.order_by(order_by)

        total = qs.count()
        start = (page - 1) * per_page
        end = start + per_page
        items = qs[start:end]

        results = []
        for item in items:
            results.append(_serialize_questao_fluxo(item))

        return JsonResponse({
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'ordering': order_by,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def consultar_atendimentos_api(request):
    """API GET para consultar atendimentos de fluxo"""
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        per_page = max(1, min(per_page, 100))

        atendimento_id = request.GET.get('id')
        lead_id = request.GET.get('lead_id')
        fluxo_id = request.GET.get('fluxo_id')
        status = request.GET.get('status')
        search = request.GET.get('search')
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        score_min = request.GET.get('score_min')
        score_max = request.GET.get('score_max')
        ordering = request.GET.get('ordering')

        qs = AtendimentoFluxo.objects.select_related('lead', 'fluxo', 'historico_contato')

        if atendimento_id:
            qs = qs.filter(id=atendimento_id)
        else:
            if lead_id:
                qs = qs.filter(lead_id=lead_id)

            if fluxo_id:
                qs = qs.filter(fluxo_id=fluxo_id)

            if status:
                qs = qs.filter(status=status)

            if search:
                qs = qs.filter(
                    Q(lead__nome_razaosocial__icontains=search) |
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
        allowed_order_fields = {'id', 'data_inicio', 'data_ultima_atividade', 'questao_atual', 'score_qualificacao'}
        if ordering and ordering.lstrip('-') in allowed_order_fields:
            order_by = ordering
        else:
            order_by = '-data_inicio'
        
        qs = qs.order_by(order_by)

        total = qs.count()
        start = (page - 1) * per_page
        end = start + per_page
        items = qs[start:end]

        results = []
        for item in items:
            results.append(_serialize_atendimento_fluxo(item))

        return JsonResponse({
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'ordering': order_by,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def consultar_respostas_api(request):
    """API GET para consultar respostas de questões"""
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        per_page = max(1, min(per_page, 100))

        resposta_id = request.GET.get('id')
        atendimento_id = request.GET.get('atendimento_id')
        questao_id = request.GET.get('questao_id')
        valida = request.GET.get('valida')
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        ordering = request.GET.get('ordering')

        qs = RespostaQuestao.objects.select_related('atendimento', 'questao')

        if resposta_id:
            qs = qs.filter(id=resposta_id)
        else:
            if atendimento_id:
                qs = qs.filter(atendimento_id=atendimento_id)

            if questao_id:
                qs = qs.filter(questao_id=questao_id)

            if valida is not None:
                valida_bool = valida.lower() in ['true', '1', 'sim', 'yes']
                qs = qs.filter(valida=valida_bool)

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
        allowed_order_fields = {'id', 'data_resposta', 'tentativas', 'tempo_resposta'}
        if ordering and ordering.lstrip('-') in allowed_order_fields:
            order_by = ordering
        else:
            order_by = '-data_resposta'
        
        qs = qs.order_by(order_by)

        total = qs.count()
        start = (page - 1) * per_page
        end = start + per_page
        items = qs[start:end]

        results = []
        for item in items:
            results.append({
                'id': item.id,
                'atendimento_id': item.atendimento.id,
                'questao_id': item.questao.id,
                'questao_titulo': item.questao.titulo,
                'resposta': item.resposta,
                'resposta_processada': item.resposta_processada,
                'valida': item.valida,
                'mensagem_erro': item.mensagem_erro,
                'tentativas': item.tentativas,
                'data_resposta': item.data_resposta.isoformat() if item.data_resposta else None,
                'tempo_resposta': item.tempo_resposta,
                'tempo_resposta_formatado': item.get_tempo_resposta_formatado(),
                'ip_origem': item.ip_origem,
                'user_agent': item.user_agent,
                'dados_extras': item.dados_extras
            })

        return JsonResponse({
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'ordering': order_by,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================================

def _atualizar_resultado_processamento(prospecto, novos_dados):
    """
    Atualiza o resultado_processamento de um prospecto de forma segura
    
    Args:
        prospecto: Instância do Prospecto
        novos_dados: Dict com os dados a serem adicionados/atualizados
    """
    if prospecto.resultado_processamento:
        # Se já existe, garantir que é um dict e atualizar
        if isinstance(prospecto.resultado_processamento, dict):
            prospecto.resultado_processamento.update(novos_dados)
        else:
            # Se é string, tentar fazer parse JSON ou criar novo dict
            try:
                import json
                existing_data = json.loads(prospecto.resultado_processamento) if isinstance(prospecto.resultado_processamento, str) else {}
                existing_data.update(novos_dados)
                prospecto.resultado_processamento = existing_data
            except (json.JSONDecodeError, TypeError):
                prospecto.resultado_processamento = novos_dados
    else:
        prospecto.resultado_processamento = novos_dados


def _criar_log_sistema(nivel, modulo, mensagem, dados_extras=None, request=None):
    """
    Cria um log no sistema
    
    Args:
        nivel: Nível do log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        modulo: Módulo/função que gerou o log
        mensagem: Mensagem do log
        dados_extras: Dados JSON extras (opcional)
        request: Request HTTP para extrair IP e usuário (opcional)
    """
    try:
        ip = None
        usuario = None
        
        if request:
            # Extrair IP do request
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')
            
            # Extrair usuário se autenticado
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
        # Se falhar ao criar log, não interromper o fluxo principal
        logger.warning("Erro ao criar log: %s", str(e))


def _parse_json_request(request):
    try:
        body = request.body.decode('utf-8') if isinstance(request.body, (bytes, bytearray)) else request.body
        return json.loads(body or '{}')
    except Exception:
        return None


def _model_field_names(model_cls):
    # Campos concretos (exclui M2M e reversos)
    field_names = []
    for f in model_cls._meta.get_fields():
        if getattr(f, 'many_to_many', False) or getattr(f, 'one_to_many', False):
            continue
        if hasattr(f, 'attname'):
            field_names.append(f.name)
    return set(field_names)


def _serialize_instance(instance):
    from django.forms.models import model_to_dict
    from decimal import Decimal
    from datetime import date
    data = model_to_dict(instance)
    for key, value in list(data.items()):
        if isinstance(value, Decimal):
            data[key] = float(value)
        elif isinstance(value, datetime):
            data[key] = value.isoformat()
        elif isinstance(value, date):
            data[key] = value.isoformat()
    # Campos DateTime auto que podem não estar em model_to_dict
    for auto_dt in ['data_cadastro', 'data_atualizacao', 'data_criacao', 'data_processamento', 'data_inicio_processamento', 'data_fim_processamento', 'data_hora_contato', 'data_conversao_lead', 'data_conversao_venda']:
        if hasattr(instance, auto_dt):
            val = getattr(instance, auto_dt)
            if isinstance(val, datetime):
                data[auto_dt] = val.isoformat()
    # Campos de choices: adiciona display quando existir
    for display_field, getter in [
        ('status_api_display', 'get_status_api_display'),
        ('origem_display', 'get_origem_display'),
        ('status_display', 'get_status_display'),
        ('origem_contato_display', 'get_origem_contato_display')
    ]:
        if hasattr(instance, getter):
            try:
                data[display_field] = getattr(instance, getter)()
            except Exception:
                pass
    return data


def _resolve_fk(model_cls, field_name, value):
    # Resolve ids para FKs simples quando o payload vem com inteiro
    if value is None:
        return None
    if model_cls is Prospecto and field_name in ['lead', 'lead_id']:
        return LeadProspecto.objects.get(id=value) if value else None
    if model_cls is HistoricoContato and field_name in ['lead', 'lead_id']:
        return LeadProspecto.objects.get(id=value) if value else None
    return value


def _apply_updates(instance, updates):
    fields = _model_field_names(type(instance))
    for key, value in updates.items():
        if key in ['id', 'pk']:
            continue
        if key not in fields and not key.endswith('_id'):
            continue
        try:
            resolved_value = _resolve_fk(type(instance), key, value)
            # Coerção básica para campos de data quando vier string
            if key in fields and isinstance(resolved_value, str):
                try:
                    field_obj = type(instance)._meta.get_field(key)
                    internal_type = getattr(field_obj, 'get_internal_type', lambda: '')()
                    if internal_type == 'DateField':
                        # Tentar múltiplos formatos de data
                        date_formats = [
                            '%Y-%m-%d',      # 2002-11-14 (ISO)
                            '%d/%m/%Y',      # 14/11/2002 (BR)
                            '%d-%m-%Y',      # 14-11-2002
                            '%Y/%m/%d',      # 2002/11/14 (US)
                            '%m/%d/%Y',      # 11/14/2002 (US)
                        ]
                        coerced = None
                        for fmt in date_formats:
                            try:
                                coerced = datetime.strptime(resolved_value, fmt).date()
                                break
                            except ValueError:
                                continue
                        if coerced is None:
                            # Última tentativa com fromisoformat
                            try:
                                coerced = datetime.fromisoformat(resolved_value).date()
                            except ValueError:
                                raise ValueError(f'Formato de data inválido para campo "{key}". Use DD/MM/YYYY ou YYYY-MM-DD')
                        resolved_value = coerced
                    elif internal_type == 'DateTimeField':
                        # Tentar múltiplos formatos de datetime
                        datetime_formats = [
                            '%Y-%m-%d %H:%M:%S',      # 2002-11-14 15:30:00
                            '%Y-%m-%dT%H:%M:%S',      # 2002-11-14T15:30:00 (ISO)
                            '%d/%m/%Y %H:%M:%S',      # 14/11/2002 15:30:00 (BR)
                            '%d/%m/%Y %H:%M',         # 14/11/2002 15:30 (BR)
                            '%Y-%m-%d',               # 2002-11-14 (converte para datetime)
                            '%d/%m/%Y',               # 14/11/2002 (converte para datetime)
                        ]
                        coerced_dt = None
                        for fmt in datetime_formats:
                            try:
                                if fmt in ['%Y-%m-%d', '%d/%m/%Y']:
                                    # Para formatos só de data, adiciona hora 00:00:00
                                    date_part = datetime.strptime(resolved_value, fmt).date()
                                    coerced_dt = datetime.combine(date_part, datetime.min.time())
                                else:
                                    coerced_dt = datetime.strptime(resolved_value, fmt)
                                break
                            except ValueError:
                                continue
                        if coerced_dt is None:
                            # Última tentativa com fromisoformat
                            try:
                                coerced_dt = datetime.fromisoformat(resolved_value)
                            except ValueError:
                                raise ValueError(f'Formato de data/hora inválido para campo "{key}". Use DD/MM/YYYY HH:MM:SS ou YYYY-MM-DD HH:MM:SS')
                        resolved_value = coerced_dt
                except Exception:
                    pass
            setattr(instance, key, resolved_value)
        except LeadProspecto.DoesNotExist:
            raise ValueError('Lead relacionado não encontrado')
    instance.save()
    return instance


# ============================================================================
# APIs de Registro e Atualização
# ============================================================================

@csrf_exempt
@api_token_required
def registrar_lead_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    data = _parse_json_request(request)
    if data is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='registrar_lead_api',
            mensagem='Tentativa de registro com JSON inválido',
            dados_extras={'body': request.body.decode('utf-8', errors='ignore')[:500]},
            request=request
        )
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    
    required = ['nome_razaosocial', 'telefone']
    missing = [f for f in required if not data.get(f)]
    if missing:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='registrar_lead_api',
            mensagem=f'Campos obrigatórios ausentes: {", ".join(missing)}',
            dados_extras={'dados_recebidos': data, 'campos_faltando': missing},
            request=request
        )
        return JsonResponse({'error': f'Campos obrigatórios ausentes: {", ".join(missing)}'}, status=400)
    
    try:
        allowed = _model_field_names(LeadProspecto)
        payload = {k: v for k, v in data.items() if k in allowed}
        lead = LeadProspecto.objects.create(**payload)
        
        # Log de sucesso
        _criar_log_sistema(
            nivel='INFO',
            modulo='registrar_lead_api',
            mensagem=f'Lead registrado com sucesso - ID: {lead.id}',
            dados_extras={
                'lead_id': lead.id,
                'nome': lead.nome_razaosocial,
                'telefone': lead.telefone,
                'origem': lead.origem,
                'dados_enviados': data
            },
            request=request
        )
        
        return JsonResponse({'success': True, 'id': lead.id, 'lead': _serialize_instance(lead)}, status=201)
    except Exception as e:
        # Log de erro
        _criar_log_sistema(
            nivel='ERROR',
            modulo='registrar_lead_api',
            mensagem=f'Erro ao registrar lead: {str(e)}',
            dados_extras={
                'erro': str(e),
                'traceback': traceback.format_exc(),
                'dados_enviados': data
            },
            request=request
        )
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@api_token_required
def registrar_imagem_lead_api(request):
    """Adiciona uma ou mais imagens (URLs) a um LeadProspecto.

    POST JSON aceito:
      { "lead_id": 1, "link_url": "https://..." }
      ou
      { "lead_id": 1, "imagens": [ {"link_url": "https://...", "descricao": "..."}, ... ] }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = _parse_json_request(request)
    if data is None:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    lead_id = data.get('lead_id')
    if not lead_id:
        return JsonResponse({'error': 'Campo obrigatório: lead_id'}, status=400)

    try:
        lead = LeadProspecto.objects.get(pk=lead_id)
    except LeadProspecto.DoesNotExist:
        return JsonResponse({'error': f'Lead #{lead_id} não encontrado'}, status=404)

    imagens_input = data.get('imagens')
    if imagens_input is None:
        link_url = data.get('link_url')
        if not link_url:
            return JsonResponse({'error': 'Informe link_url ou imagens[]'}, status=400)
        imagens_input = [{'link_url': link_url, 'descricao': data.get('descricao', '')}]

    criadas = []
    for item in imagens_input:
        url = item.get('link_url', '').strip() if isinstance(item, dict) else str(item).strip()
        if not url:
            continue
        descricao = item.get('descricao', '') if isinstance(item, dict) else ''
        img = ImagemLeadProspecto.objects.create(
            lead=lead,
            link_url=url,
            descricao=descricao,
        )
        criadas.append({
            'id': img.id,
            'link_url': img.link_url,
            'descricao': img.descricao,
            'data_criacao': img.data_criacao.isoformat(),
        })

    if not criadas:
        return JsonResponse({'error': 'Nenhuma imagem válida informada'}, status=400)

    return JsonResponse({
        'success': True,
        'lead_id': lead.id,
        'imagens_criadas': len(criadas),
        'imagens': criadas,
    }, status=201)


@csrf_exempt
@api_token_required
def listar_imagens_lead_api(request):
    """Lista imagens de um LeadProspecto.  GET ?lead_id=1"""
    lead_id = request.GET.get('lead_id')
    if not lead_id:
        return JsonResponse({'error': 'Parâmetro obrigatório: lead_id'}, status=400)

    imagens = ImagemLeadProspecto.objects.filter(lead_id=lead_id).order_by('-data_criacao')
    data = [{
        'id': img.id,
        'link_url': img.link_url,
        'descricao': img.descricao,
        'data_criacao': img.data_criacao.isoformat(),
    } for img in imagens]

    return JsonResponse({'lead_id': int(lead_id), 'total': len(data), 'imagens': data})


@csrf_exempt
@api_token_required
def deletar_imagem_lead_api(request):
    """Remove uma imagem pelo ID.  POST { "imagem_id": 1 }"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = _parse_json_request(request)
    if data is None:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    imagem_id = data.get('imagem_id')
    if not imagem_id:
        return JsonResponse({'error': 'Campo obrigatório: imagem_id'}, status=400)

    try:
        img = ImagemLeadProspecto.objects.get(pk=imagem_id)
        img.delete()
        return JsonResponse({'success': True, 'message': f'Imagem #{imagem_id} removida'})
    except ImagemLeadProspecto.DoesNotExist:
        return JsonResponse({'error': f'Imagem #{imagem_id} não encontrada'}, status=404)


@csrf_exempt
@api_token_required
def imagens_por_cliente_api(request):
    """
    GET /api/leads/imagens/por-cliente/?cliente_hubsoft_id=<id>
    Retorna as imagens vinculadas ao lead relacionado ao ClienteHubsoft.
    """
    from apps.integracoes.models import ClienteHubsoft

    cliente_id = request.GET.get('cliente_hubsoft_id')
    if not cliente_id:
        return JsonResponse({'error': 'Parâmetro obrigatório: cliente_hubsoft_id'}, status=400)

    try:
        cliente = ClienteHubsoft.objects.select_related('lead').get(pk=cliente_id)
    except ClienteHubsoft.DoesNotExist:
        return JsonResponse({'error': 'Cliente não encontrado'}, status=404)

    lead = cliente.lead
    if not lead:
        return JsonResponse({'success': True, 'imagens': [], 'lead': None,
                             'message': 'Cliente sem lead relacionado'})

    imagens = ImagemLeadProspecto.objects.filter(lead=lead).order_by('-data_criacao')
    imagens_data = [
        {
            'id':                   img.pk,
            'link_url':             img.link_url,
            'descricao':            img.descricao,
            'status_validacao':     img.status_validacao,
            'observacao_validacao': img.observacao_validacao,
            'validado_por':         img.validado_por,
            'data_validacao':       img.data_validacao.isoformat() if img.data_validacao else None,
            'data_criacao':         img.data_criacao.isoformat(),
        }
        for img in imagens
    ]

    return JsonResponse({
        'success': True,
        'lead': {
            'id':                     lead.id,
            'nome':                   lead.nome_razaosocial,
            'documentacao_completa':  lead.documentacao_completa,
            'documentacao_validada':  lead.documentacao_validada,
        },
        'imagens': imagens_data,
        'total':   len(imagens_data),
    })


@csrf_exempt
@api_token_required
def validar_imagem_api(request):
    """
    POST /api/leads/imagens/validar/
    Body: { "imagem_id": 1, "acao": "aprovar"|"rejeitar", "observacao": "..." }
    Atualiza status_validacao da imagem.
    Quando TODAS as imagens do lead forem aprovadas → documentacao_validada = True no lead.
    Quando QUALQUER imagem for rejeitada → documentacao_validada = False no lead.
    """
    from django.utils import timezone

    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = _parse_json_request(request)
    if data is None:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    imagem_id  = data.get('imagem_id')
    acao       = data.get('acao', '').strip().lower()
    observacao = data.get('observacao', '').strip()

    if not imagem_id:
        return JsonResponse({'error': 'Campo obrigatório: imagem_id'}, status=400)
    if acao not in ('aprovar', 'rejeitar'):
        return JsonResponse({'error': 'acao deve ser "aprovar" ou "rejeitar"'}, status=400)

    try:
        img = ImagemLeadProspecto.objects.select_related('lead').get(pk=imagem_id)
    except ImagemLeadProspecto.DoesNotExist:
        return JsonResponse({'error': f'Imagem #{imagem_id} não encontrada'}, status=404)

    novo_status = (ImagemLeadProspecto.STATUS_VALIDO
                   if acao == 'aprovar'
                   else ImagemLeadProspecto.STATUS_REJEITADO)

    usuario = request.user.get_full_name() or request.user.username

    img.status_validacao     = novo_status
    img.observacao_validacao = observacao
    img.data_validacao       = timezone.now()
    img.validado_por         = usuario
    img.save(update_fields=['status_validacao', 'observacao_validacao',
                             'data_validacao', 'validado_por'])

    # Atualizar flags de documentação no lead
    lead = img.lead
    todas_imagens = list(lead.imagens.values_list('status_validacao', flat=True))

    if todas_imagens:
        todas_validas   = all(s == ImagemLeadProspecto.STATUS_VALIDO    for s in todas_imagens)
        alguma_rejeitada = any(s == ImagemLeadProspecto.STATUS_REJEITADO for s in todas_imagens)

        lead.documentacao_validada = todas_validas
        if todas_validas:
            lead.data_documentacao_validada = timezone.now()
        elif alguma_rejeitada:
            lead.data_documentacao_validada = None
        lead.save(update_fields=['documentacao_validada', 'data_documentacao_validada'])

    return JsonResponse({
        'success':          True,
        'imagem_id':        img.pk,
        'status_validacao': img.status_validacao,
        'validado_por':     img.validado_por,
        'lead': {
            'id':                    lead.id,
            'documentacao_validada': lead.documentacao_validada,
        },
        'message': f'Imagem {"aprovada" if acao == "aprovar" else "rejeitada"} com sucesso',
    })


@csrf_exempt
@api_token_required
def atualizar_lead_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    data = _parse_json_request(request)
    if data is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_lead_api',
            mensagem='Tentativa de atualização com JSON inválido',
            dados_extras={'body': request.body.decode('utf-8', errors='ignore')[:500]},
            request=request
        )
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    
    termo = data.get('termo_busca')
    busca = data.get('busca')
    if not termo or busca is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_lead_api',
            mensagem='Parâmetros de busca faltando',
            dados_extras={'dados_recebidos': data},
            request=request
        )
        return JsonResponse({'error': 'Parâmetros obrigatórios: termo_busca e busca'}, status=400)
    
    try:
        qs = LeadProspecto.objects.filter(**{termo: busca})
    except Exception as e:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_lead_api',
            mensagem=f'Termo de busca inválido: {termo}',
            dados_extras={'termo': termo, 'busca': busca, 'erro': str(e)},
            request=request
        )
        return JsonResponse({'error': 'termo_busca inválido para LeadProspecto'}, status=400)
    
    count = qs.count()
    if count == 0:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_lead_api',
            mensagem='Lead não encontrado',
            dados_extras={'termo': termo, 'busca': busca},
            request=request
        )
        return JsonResponse({'error': 'Registro não encontrado'}, status=404)
    
    if count > 1:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_lead_api',
            mensagem=f'Múltiplos leads encontrados ({count})',
            dados_extras={'termo': termo, 'busca': busca, 'quantidade': count},
            request=request
        )
        return JsonResponse({'error': f'Múltiplos registros encontrados ({count}). Refine a busca.'}, status=400)
    
    lead = qs.first()
    updates = {k: v for k, v in data.items() if k not in ['termo_busca', 'busca']}
    if not updates:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_lead_api',
            mensagem='Nenhum campo para atualizar',
            dados_extras={'lead_id': lead.id, 'dados_recebidos': data},
            request=request
        )
        return JsonResponse({'error': 'Nenhum campo para atualizar informado'}, status=400)
    
    # Guardar valores antigos para o log
    valores_antigos = {}
    for campo in updates.keys():
        if hasattr(lead, campo):
            valores_antigos[campo] = getattr(lead, campo)
    
    try:
        _apply_updates(lead, updates)
        
        # Log de sucesso
        _criar_log_sistema(
            nivel='INFO',
            modulo='atualizar_lead_api',
            mensagem=f'Lead atualizado com sucesso - ID: {lead.id}',
            dados_extras={
                'lead_id': lead.id,
                'termo_busca': termo,
                'valor_busca': busca,
                'campos_atualizados': list(updates.keys()),
                'valores_antigos': valores_antigos,
                'valores_novos': updates
            },
            request=request
        )
        
        return JsonResponse({'success': True, 'id': lead.id, 'lead': _serialize_instance(lead)})
    except ValueError as ve:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_lead_api',
            mensagem=f'Erro de validação ao atualizar lead: {str(ve)}',
            dados_extras={
                'lead_id': lead.id,
                'erro': str(ve),
                'dados_tentados': updates
            },
            request=request
        )
        return JsonResponse({'error': str(ve)}, status=404)
    except Exception as e:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_lead_api',
            mensagem=f'Erro ao atualizar lead: {str(e)}',
            dados_extras={
                'lead_id': lead.id,
                'erro': str(e),
                'traceback': traceback.format_exc(),
                'dados_tentados': updates
            },
            request=request
        )
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@api_token_required
def registrar_prospecto_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    data = _parse_json_request(request)
    if data is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='registrar_prospecto_api',
            mensagem='Tentativa de registro com JSON inválido',
            dados_extras={'body': request.body.decode('utf-8', errors='ignore')[:500]},
            request=request
        )
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    
    required = ['nome_prospecto']
    missing = [f for f in required if not data.get(f)]
    if missing:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='registrar_prospecto_api',
            mensagem=f'Campos obrigatórios ausentes: {", ".join(missing)}',
            dados_extras={'dados_recebidos': data, 'campos_faltando': missing},
            request=request
        )
        return JsonResponse({'error': f'Campos obrigatórios ausentes: {", ".join(missing)}'}, status=400)
    
    try:
        allowed = _model_field_names(Prospecto)
        payload = {k: v for k, v in data.items() if k in allowed}
        # Resolver lead se vier como id simples
        if 'lead' in data and isinstance(data['lead'], int):
            payload['lead'] = LeadProspecto.objects.get(id=data['lead'])
        if 'lead_id' in data and isinstance(data['lead_id'], int):
            payload['lead_id'] = data['lead_id']
        prospecto = Prospecto.objects.create(**payload)
        
        # Log de sucesso
        _criar_log_sistema(
            nivel='INFO',
            modulo='registrar_prospecto_api',
            mensagem=f'Prospecto registrado com sucesso - ID: {prospecto.id}',
            dados_extras={
                'prospecto_id': prospecto.id,
                'nome': prospecto.nome_prospecto,
                'lead_id': prospecto.lead_id,
                'status': prospecto.status,
                'dados_enviados': data
            },
            request=request
        )
        
        return JsonResponse({'success': True, 'id': prospecto.id, 'prospecto': _serialize_instance(prospecto)}, status=201)
    except LeadProspecto.DoesNotExist:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='registrar_prospecto_api',
            mensagem='Lead informado não encontrado',
            dados_extras={'lead_id': data.get('lead') or data.get('lead_id')},
            request=request
        )
        return JsonResponse({'error': 'Lead informado não encontrado'}, status=404)
    except Exception as e:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='registrar_prospecto_api',
            mensagem=f'Erro ao registrar prospecto: {str(e)}',
            dados_extras={
                'erro': str(e),
                'traceback': traceback.format_exc(),
                'dados_enviados': data
            },
            request=request
        )
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@api_token_required
def atualizar_prospecto_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    data = _parse_json_request(request)
    if data is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_prospecto_api',
            mensagem='Tentativa de atualização com JSON inválido',
            dados_extras={'body': request.body.decode('utf-8', errors='ignore')[:500]},
            request=request
        )
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    
    termo = data.get('termo_busca')
    busca = data.get('busca')
    if not termo or busca is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_prospecto_api',
            mensagem='Parâmetros de busca faltando',
            dados_extras={'dados_recebidos': data},
            request=request
        )
        return JsonResponse({'error': 'Parâmetros obrigatórios: termo_busca e busca'}, status=400)
    
    try:
        qs = Prospecto.objects.filter(**{termo: busca})
    except Exception as e:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_prospecto_api',
            mensagem=f'Termo de busca inválido: {termo}',
            dados_extras={'termo': termo, 'busca': busca, 'erro': str(e)},
            request=request
        )
        return JsonResponse({'error': 'termo_busca inválido para Prospecto'}, status=400)
    
    count = qs.count()
    if count == 0:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_prospecto_api',
            mensagem='Prospecto não encontrado',
            dados_extras={'termo': termo, 'busca': busca},
            request=request
        )
        return JsonResponse({'error': 'Registro não encontrado'}, status=404)
    
    if count > 1:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_prospecto_api',
            mensagem=f'Múltiplos prospectos encontrados ({count})',
            dados_extras={'termo': termo, 'busca': busca, 'quantidade': count},
            request=request
        )
        return JsonResponse({'error': f'Múltiplos registros encontrados ({count}). Refine a busca.'}, status=400)
    
    prospecto = qs.first()
    updates = {k: v for k, v in data.items() if k not in ['termo_busca', 'busca']}
    if not updates:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_prospecto_api',
            mensagem='Nenhum campo para atualizar',
            dados_extras={'prospecto_id': prospecto.id, 'dados_recebidos': data},
            request=request
        )
        return JsonResponse({'error': 'Nenhum campo para atualizar informado'}, status=400)
    
    # Guardar valores antigos para o log
    valores_antigos = {}
    for campo in updates.keys():
        if hasattr(prospecto, campo):
            valores_antigos[campo] = getattr(prospecto, campo)
    
    try:
        _apply_updates(prospecto, updates)
        
        # Log de sucesso
        _criar_log_sistema(
            nivel='INFO',
            modulo='atualizar_prospecto_api',
            mensagem=f'Prospecto atualizado com sucesso - ID: {prospecto.id}',
            dados_extras={
                'prospecto_id': prospecto.id,
                'termo_busca': termo,
                'valor_busca': busca,
                'campos_atualizados': list(updates.keys()),
                'valores_antigos': valores_antigos,
                'valores_novos': updates
            },
            request=request
        )
        
        return JsonResponse({'success': True, 'id': prospecto.id, 'prospecto': _serialize_instance(prospecto)})
    except ValueError as ve:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_prospecto_api',
            mensagem=f'Erro de validação ao atualizar prospecto: {str(ve)}',
            dados_extras={
                'prospecto_id': prospecto.id,
                'erro': str(ve),
                'dados_tentados': updates
            },
            request=request
        )
        return JsonResponse({'error': str(ve)}, status=404)
    except Exception as e:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_prospecto_api',
            mensagem=f'Erro ao atualizar prospecto: {str(e)}',
            dados_extras={
                'prospecto_id': prospecto.id,
                'erro': str(e),
                'traceback': traceback.format_exc(),
                'dados_tentados': updates
            },
            request=request
        )
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@api_token_required
def registrar_historico_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    data = _parse_json_request(request)
    if data is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='registrar_historico_api',
            mensagem='Tentativa de registro com JSON inválido',
            dados_extras={'body': request.body.decode('utf-8', errors='ignore')[:500]},
            request=request
        )
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    
    required = ['telefone', 'status']
    missing = [f for f in required if not data.get(f)]
    if missing:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='registrar_historico_api',
            mensagem=f'Campos obrigatórios ausentes: {", ".join(missing)}',
            dados_extras={'dados_recebidos': data, 'campos_faltando': missing},
            request=request
        )
        return JsonResponse({'error': f'Campos obrigatórios ausentes: {", ".join(missing)}'}, status=400)
    
    try:
        allowed = _model_field_names(HistoricoContato)
        payload = {k: v for k, v in data.items() if k in allowed}
        if 'lead' in data and isinstance(data['lead'], int):
            payload['lead'] = LeadProspecto.objects.get(id=data['lead'])
        if 'lead_id' in data and isinstance(data['lead_id'], int):
            payload['lead_id'] = data['lead_id']
        contato = HistoricoContato.objects.create(**payload)
        
        # Log de sucesso
        _criar_log_sistema(
            nivel='INFO',
            modulo='registrar_historico_api',
            mensagem=f'Histórico de contato registrado com sucesso - ID: {contato.id}',
            dados_extras={
                'historico_id': contato.id,
                'telefone': contato.telefone,
                'status': contato.status,
                'lead_id': contato.lead_id,
                'dados_enviados': data
            },
            request=request
        )
        
        return JsonResponse({'success': True, 'id': contato.id, 'historico': _serialize_instance(contato)}, status=201)
    except LeadProspecto.DoesNotExist:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='registrar_historico_api',
            mensagem='Lead informado não encontrado',
            dados_extras={'lead_id': data.get('lead') or data.get('lead_id')},
            request=request
        )
        return JsonResponse({'error': 'Lead informado não encontrado'}, status=404)
    except Exception as e:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='registrar_historico_api',
            mensagem=f'Erro ao registrar histórico: {str(e)}',
            dados_extras={
                'erro': str(e),
                'traceback': traceback.format_exc(),
                'dados_enviados': data
            },
            request=request
        )
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@api_token_required
def verificar_relacionamentos_api(request):
    """
    API para verificar e relacionar prospectos órfãos com leads baseado no id_hubsoft
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        # Log da verificação
        _criar_log_sistema('INFO', 'verificar_relacionamentos_api', 'Iniciando verificação de relacionamentos', request=request)
        
        relacionamentos_criados = 0
        
        # Buscar prospectos sem lead que tenham id_prospecto_hubsoft
        prospectos_sem_lead = Prospecto.objects.filter(
            lead__isnull=True,
            id_prospecto_hubsoft__isnull=False
        ).exclude(id_prospecto_hubsoft='')
        
        for prospecto in prospectos_sem_lead:
            id_hub = prospecto.id_prospecto_hubsoft.strip()
            if not id_hub:
                continue
                
            # Buscar lead correspondente
            lead = LeadProspecto.objects.filter(id_hubsoft=id_hub).first()
            if lead:
                # Relacionar prospecto com lead
                prospecto.lead = lead
                prospecto.save()
                relacionamentos_criados += 1
                
                # Log do relacionamento criado
                _criar_log_sistema(
                    'INFO', 
                    'verificar_relacionamentos_api', 
                    f'Relacionamento criado: Prospecto #{prospecto.id} → Lead #{lead.id}',
                    dados_extras={
                        'prospecto_id': prospecto.id,
                        'lead_id': lead.id,
                        'id_hubsoft': id_hub
                    },
                    request=request
                )
        
        # Buscar leads sem prospectos que tenham id_hubsoft
        leads_com_hubsoft = LeadProspecto.objects.filter(
            id_hubsoft__isnull=False
        ).exclude(id_hubsoft='')
        
        for lead in leads_com_hubsoft:
            id_hub = lead.id_hubsoft.strip()
            if not id_hub:
                continue
                
            # Buscar prospectos órfãos correspondentes
            prospectos_sem_lead = Prospecto.objects.filter(
                id_prospecto_hubsoft=id_hub,
                lead__isnull=True
            )
            
            if prospectos_sem_lead.exists():
                # Relacionar todos os prospectos encontrados
                count = prospectos_sem_lead.update(lead=lead)
                relacionamentos_criados += count
                
                # Log dos relacionamentos criados
                for prospecto in prospectos_sem_lead:
                    _criar_log_sistema(
                        'INFO', 
                        'verificar_relacionamentos_api', 
                        f'Relacionamento criado: Lead #{lead.id} → Prospecto #{prospecto.id}',
                        dados_extras={
                            'lead_id': lead.id,
                            'prospecto_id': prospecto.id,
                            'id_hubsoft': id_hub
                        },
                        request=request
                    )
        
        # Log final
        _criar_log_sistema(
            'INFO', 
            'verificar_relacionamentos_api', 
            f'Verificação concluída: {relacionamentos_criados} relacionamentos criados',
            dados_extras={'relacionamentos_criados': relacionamentos_criados},
            request=request
        )
        
        return JsonResponse({
            'success': True,
            'relacionamentos_criados': relacionamentos_criados,
            'message': f'Verificação concluída. {relacionamentos_criados} relacionamentos criados.'
        })
        
    except Exception as e:
        error_msg = str(e)
        _criar_log_sistema('ERROR', 'verificar_relacionamentos_api', f'Erro na verificação: {error_msg}', request=request)
        return JsonResponse({'error': f'Erro na verificação: {error_msg}'}, status=500)


@csrf_exempt
@api_token_required
def atualizar_historico_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    data = _parse_json_request(request)
    if data is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_historico_api',
            mensagem='Tentativa de atualização com JSON inválido',
            dados_extras={'body': request.body.decode('utf-8', errors='ignore')[:500]},
            request=request
        )
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    
    termo = data.get('termo_busca')
    busca = data.get('busca')
    if not termo or busca is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_historico_api',
            mensagem='Parâmetros de busca faltando',
            dados_extras={'dados_recebidos': data},
            request=request
        )
        return JsonResponse({'error': 'Parâmetros obrigatórios: termo_busca e busca'}, status=400)
    
    try:
        qs = HistoricoContato.objects.filter(**{termo: busca})
    except Exception as e:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_historico_api',
            mensagem=f'Termo de busca inválido: {termo}',
            dados_extras={'termo': termo, 'busca': busca, 'erro': str(e)},
            request=request
        )
        return JsonResponse({'error': 'termo_busca inválido para Histórico de Contato'}, status=400)
    
    count = qs.count()
    if count == 0:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_historico_api',
            mensagem='Histórico não encontrado',
            dados_extras={'termo': termo, 'busca': busca},
            request=request
        )
        return JsonResponse({'error': 'Registro não encontrado'}, status=404)
    
    if count > 1:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_historico_api',
            mensagem=f'Múltiplos históricos encontrados ({count})',
            dados_extras={'termo': termo, 'busca': busca, 'quantidade': count},
            request=request
        )
        return JsonResponse({'error': f'Múltiplos registros encontrados ({count}). Refine a busca.'}, status=400)
    
    contato = qs.first()
    updates = {k: v for k, v in data.items() if k not in ['termo_busca', 'busca']}
    if not updates:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_historico_api',
            mensagem='Nenhum campo para atualizar',
            dados_extras={'historico_id': contato.id, 'dados_recebidos': data},
            request=request
        )
        return JsonResponse({'error': 'Nenhum campo para atualizar informado'}, status=400)
    
    # Guardar valores antigos para o log
    valores_antigos = {}
    for campo in updates.keys():
        if hasattr(contato, campo):
            valores_antigos[campo] = getattr(contato, campo)
    
    try:
        _apply_updates(contato, updates)
        
        # Log de sucesso
        _criar_log_sistema(
            nivel='INFO',
            modulo='atualizar_historico_api',
            mensagem=f'Histórico atualizado com sucesso - ID: {contato.id}',
            dados_extras={
                'historico_id': contato.id,
                'termo_busca': termo,
                'valor_busca': busca,
                'campos_atualizados': list(updates.keys()),
                'valores_antigos': valores_antigos,
                'valores_novos': updates
            },
            request=request
        )
        
        return JsonResponse({'success': True, 'id': contato.id, 'historico': _serialize_instance(contato)})
    except ValueError as ve:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_historico_api',
            mensagem=f'Erro de validação ao atualizar histórico: {str(ve)}',
            dados_extras={
                'historico_id': contato.id,
                'erro': str(ve),
                'dados_tentados': updates
            },
            request=request
        )
        return JsonResponse({'error': str(ve)}, status=404)
    except Exception as e:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_historico_api',
            mensagem=f'Erro ao atualizar histórico: {str(e)}',
            dados_extras={
                'historico_id': contato.id,
                'erro': str(e),
                'traceback': traceback.format_exc(),
                'dados_tentados': updates
            },
            request=request
        )
        return JsonResponse({'error': str(e)}, status=400)

# ============================================================================
# VIEWS DO DASHBOARD
# ============================================================================

def dashboard_view(request):
    """View principal do dashboard"""
    context = {
        'user': request.user if request.user.is_authenticated else None
    }
    return render(request, 'vendas_web/new_dash.html', context)

@login_required(login_url='vendas_web:login')
def dashboard1(request):
    """View alternativa do dashboard - alias para dashboard_view"""
    context = {
        'user': request.user
    }
    return render(request, 'vendas_web/new_dash.html', context)

@login_required(login_url='vendas_web:login')
def leads_view(request):
    """View para a página de gerenciamento de leads"""
    context = {
        'user': request.user
    }
    return render(request, 'vendas_web/leads.html', context)


@login_required
@xframe_options_sameorigin
def visualizar_conversa_lead(request, lead_id):
    """Serve o HTML da conversa do atendimento gerado para um LeadProspecto."""
    import os
    from django.http import HttpResponse, Http404

    try:
        lead = LeadProspecto.objects.get(id=lead_id)
    except LeadProspecto.DoesNotExist:
        raise Http404("Lead não encontrado")

    if not lead.html_conversa_path:
        raise Http404("Conversa não disponível para este lead")

    base_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'media'
    )
    full_path = os.path.join(base_dir, lead.html_conversa_path)

    if not os.path.exists(full_path):
        raise Http404("Arquivo da conversa não encontrado")

    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()

    return HttpResponse(content, content_type='text/html; charset=utf-8')


@login_required
def visualizar_conversa_pdf(request, lead_id):
    """Gera e serve o PDF da conversa do atendimento para um LeadProspecto."""
    import os
    import logging
    from django.http import HttpResponse, Http404
    from django.conf import settings

    try:
        lead = LeadProspecto.objects.get(id=lead_id)
    except LeadProspecto.DoesNotExist:
        raise Http404("Lead não encontrado")

    if not lead.html_conversa_path:
        raise Http404("Conversa HTML não disponível para este lead")

    base_dir = str(getattr(settings, 'BASE_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    media_root = getattr(settings, 'MEDIA_ROOT', None) or os.path.join(base_dir, 'media')

    caminho_html = os.path.join(media_root, lead.html_conversa_path)
    if not os.path.exists(caminho_html):
        raise Http404("Arquivo HTML da conversa não encontrado")

    # Verifica se já existe PDF em cache no disco
    pasta_pdf = os.path.join(media_root, 'conversas_pdf')
    os.makedirs(pasta_pdf, exist_ok=True)
    caminho_pdf = os.path.join(pasta_pdf, f'{lead.pk}_conversa.pdf')

    if not os.path.exists(caminho_pdf):
        try:
            logging.getLogger('weasyprint').setLevel(logging.ERROR)
            logging.getLogger('fontTools').setLevel(logging.ERROR)
            from weasyprint import HTML as WeasyHTML
            pdf_bytes = WeasyHTML(filename=caminho_html).write_pdf()
            # Corrige segundo comentário do weasyprint (%🖤) para padrão compatível
            pdf_bytes = pdf_bytes.replace(b'%\xf0\x9f\x96\xa4', b'%\xe2\xe3\xcf\xd3', 1)
            with open(caminho_pdf, 'wb') as f:
                f.write(pdf_bytes)
        except Exception as exc:
            logging.getLogger(__name__).error("Erro ao gerar PDF para lead %s: %s", lead_id, exc)
            raise Http404("Erro ao gerar PDF da conversa")

    with open(caminho_pdf, 'rb') as f:
        pdf_bytes = f.read()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="conversa_atendimento_{lead_id}.pdf"'
    return response


def relatorio_leads_view(request):
    """View para a página de relatórios de leads"""
    # Por enquanto redireciona para a página de leads
    # Você pode criar um template específico para relatórios depois
    context = {
        'user': request.user if request.user.is_authenticated else None
    }
    return render(request, 'vendas_web/leads.html', context)

@login_required(login_url='vendas_web:login')
def relatorios_view(request):
    """View para a página principal de relatórios"""
    from .models import LeadProspecto, Prospecto, HistoricoContato
    from apps.integracoes.models import ClienteHubsoft, ServicoClienteHubsoft
    from django.db.models import Count, Q, Avg, Sum
    from datetime import datetime, timedelta
    from decimal import Decimal
    import json

    try:
        # Estatísticas gerais
        total_leads = LeadProspecto.objects.count()
        total_prospectos = Prospecto.objects.count()
        total_atendimentos = HistoricoContato.objects.filter(status='fluxo_inicializado').count()

        taxa_conversao = (total_prospectos / total_leads * 100) if total_leads > 0 else 0

        data_30_dias_atras = datetime.now() - timedelta(days=30)
        data_7_dias_atras = datetime.now() - timedelta(days=7)
        hoje = datetime.now().date()

        # Leads por período
        leads_hoje    = LeadProspecto.objects.filter(data_cadastro__date=hoje).count()
        leads_7_dias  = LeadProspecto.objects.filter(data_cadastro__gte=data_7_dias_atras).count()
        leads_30_dias = LeadProspecto.objects.filter(data_cadastro__gte=data_30_dias_atras).count()

        # Prospectos por período
        prospectos_hoje    = Prospecto.objects.filter(data_criacao__date=hoje).count()
        prospectos_7_dias  = Prospecto.objects.filter(data_criacao__gte=data_7_dias_atras).count()
        prospectos_30_dias = Prospecto.objects.filter(data_criacao__gte=data_30_dias_atras).count()

        # Atendimentos por período
        atendimentos_hoje    = HistoricoContato.objects.filter(data_hora_contato__date=hoje, status='fluxo_inicializado').count()
        atendimentos_7_dias  = HistoricoContato.objects.filter(data_hora_contato__gte=data_7_dias_atras, status='fluxo_inicializado').count()
        atendimentos_30_dias = HistoricoContato.objects.filter(data_hora_contato__gte=data_30_dias_atras, status='fluxo_inicializado').count()

        # ── Dados reais do Hubsoft (ClienteHubsoft / ServicoClienteHubsoft) ──
        total_clientes_hubsoft  = ClienteHubsoft.objects.count()
        clientes_ativos         = ClienteHubsoft.objects.filter(ativo=True).count()
        total_servicos          = ServicoClienteHubsoft.objects.count()
        clientes_com_alteracao  = ClienteHubsoft.objects.filter(houve_alteracao=True).count()

        # Serviços por status_prefixo (dados reais de habilitados/aguardando)
        servicos_habilitados      = ServicoClienteHubsoft.objects.filter(status_prefixo='servico_habilitado').count()
        servicos_aguardando_inst  = ServicoClienteHubsoft.objects.filter(status_prefixo='aguardando_instalacao').count()
        servicos_cancelados       = ServicoClienteHubsoft.objects.filter(status_prefixo__icontains='cancel').count()
        servicos_suspensos        = ServicoClienteHubsoft.objects.filter(status_prefixo__icontains='suspen').count()

        # Receita total (soma dos valores dos serviços habilitados)
        receita_agg = ServicoClienteHubsoft.objects.filter(
            status_prefixo='servico_habilitado', valor__isnull=False
        ).aggregate(total=Sum('valor'))
        receita_total = float(receita_agg['total'] or 0)

        # Distribuição completa de status dos serviços
        servicos_por_status_raw = ServicoClienteHubsoft.objects.values('status_prefixo', 'status').annotate(
            total=Count('id')
        ).order_by('-total')
        servicos_por_status = [
            {'status': item['status'] or item['status_prefixo'] or 'Não informado', 'total': item['total']}
            for item in servicos_por_status_raw
        ]

        # Clientes habilitados por período (usando data_habilitacao dos serviços)
        habilitados_hoje    = ServicoClienteHubsoft.objects.filter(
            status_prefixo='servico_habilitado', data_habilitacao__date=hoje
        ).count()
        habilitados_7_dias  = ServicoClienteHubsoft.objects.filter(
            status_prefixo='servico_habilitado', data_habilitacao__gte=data_7_dias_atras
        ).count()
        habilitados_30_dias = ServicoClienteHubsoft.objects.filter(
            status_prefixo='servico_habilitado', data_habilitacao__gte=data_30_dias_atras
        ).count()

        # Evolução de habilitações — últimos 30 dias
        evolucao_habilitacoes_30d = []
        for i in range(30):
            data_atual = hoje - timedelta(days=i)
            evolucao_habilitacoes_30d.append({
                'data': data_atual.strftime('%d/%m'),
                'total': ServicoClienteHubsoft.objects.filter(
                    status_prefixo='servico_habilitado',
                    data_habilitacao__date=data_atual
                ).count(),
            })
        evolucao_habilitacoes_30d.reverse()

        # Funil de conversão real: Leads → Prospectos → Clientes Hubsoft → Habilitados
        funil_conversao = [
            {'etapa': 'Leads',              'total': total_leads},
            {'etapa': 'Prospectos',         'total': total_prospectos},
            {'etapa': 'Clientes Hubsoft',   'total': total_clientes_hubsoft},
            {'etapa': 'Habilitados',        'total': servicos_habilitados},
        ]

        # Leads por origem
        leads_por_origem = LeadProspecto.objects.values('origem').annotate(total=Count('id')).order_by('-total')[:6]

        # Atendimentos
        atendimentos_por_origem = HistoricoContato.objects.filter(
            status='fluxo_inicializado'
        ).values('origem_contato').annotate(total=Count('id')).order_by('-total')

        atendimentos_por_status = HistoricoContato.objects.filter(
            status__in=['fluxo_finalizado', 'transferido_humano']
        ).values('status').annotate(total=Count('id')).order_by('-total')

        # Série temporal — leads/prospectos/atendimentos (últimos 7 dias)
        leads_por_dia = []
        prospectos_por_dia = []
        atendimentos_por_dia = []
        for i in range(7):
            data_atual = hoje - timedelta(days=i)
            leads_por_dia.append({'data': data_atual.strftime('%d/%m'), 'total': LeadProspecto.objects.filter(data_cadastro__date=data_atual).count()})
            prospectos_por_dia.append({'data': data_atual.strftime('%d/%m'), 'total': Prospecto.objects.filter(data_criacao__date=data_atual).count()})
            atendimentos_por_dia.append({'data': data_atual.strftime('%d/%m'), 'total': HistoricoContato.objects.filter(data_hora_contato__date=data_atual, status='fluxo_inicializado').count()})
        leads_por_dia.reverse()
        prospectos_por_dia.reverse()
        atendimentos_por_dia.reverse()

        dados_graficos = {
            'leads_por_origem':             list(leads_por_origem),
            'servicos_por_status':          servicos_por_status,
            'atendimentos_por_origem':      list(atendimentos_por_origem),
            'atendimentos_por_status':      list(atendimentos_por_status),
            'leads_por_dia':                leads_por_dia,
            'prospectos_por_dia':           prospectos_por_dia,
            'atendimentos_por_dia':         atendimentos_por_dia,
            'evolucao_habilitacoes_30d':    evolucao_habilitacoes_30d,
            'funil_conversao':              funil_conversao,
        }

        stats = {
            'total_leads':        total_leads,
            'total_prospectos':   total_prospectos,
            'total_atendimentos': total_atendimentos,
            'taxa_conversao':     round(taxa_conversao, 1),

            'leads_hoje':    leads_hoje,
            'leads_7_dias':  leads_7_dias,
            'leads_30_dias': leads_30_dias,

            'prospectos_hoje':    prospectos_hoje,
            'prospectos_7_dias':  prospectos_7_dias,
            'prospectos_30_dias': prospectos_30_dias,

            'atendimentos_hoje':    atendimentos_hoje,
            'atendimentos_7_dias':  atendimentos_7_dias,
            'atendimentos_30_dias': atendimentos_30_dias,

            # Dados Hubsoft reais
            'total_clientes_hubsoft':  total_clientes_hubsoft,
            'clientes_ativos':         clientes_ativos,
            'total_servicos':          total_servicos,
            'clientes_com_alteracao':  clientes_com_alteracao,
            'servicos_habilitados':    servicos_habilitados,
            'servicos_aguardando_inst': servicos_aguardando_inst,
            'servicos_cancelados':     servicos_cancelados,
            'servicos_suspensos':      servicos_suspensos,
            'receita_total':           receita_total,
            'habilitados_hoje':        habilitados_hoje,
            'habilitados_7_dias':      habilitados_7_dias,
            'habilitados_30_dias':     habilitados_30_dias,

            'dados_graficos': json.dumps(dados_graficos),
        }
    except Exception as e:
        logger.error("Erro ao calcular estatísticas: %s", e, exc_info=True)
        stats = {
            'total_leads': 0, 'total_prospectos': 0, 'total_atendimentos': 0,
            'taxa_conversao': 0,
            'leads_hoje': 0, 'leads_7_dias': 0, 'leads_30_dias': 0,
            'prospectos_hoje': 0, 'prospectos_7_dias': 0, 'prospectos_30_dias': 0,
            'atendimentos_hoje': 0, 'atendimentos_7_dias': 0, 'atendimentos_30_dias': 0,
            'total_clientes_hubsoft': 0, 'clientes_ativos': 0, 'total_servicos': 0,
            'clientes_com_alteracao': 0, 'servicos_habilitados': 0,
            'servicos_aguardando_inst': 0, 'servicos_cancelados': 0, 'servicos_suspensos': 0,
            'receita_total': 0, 'habilitados_hoje': 0, 'habilitados_7_dias': 0,
            'habilitados_30_dias': 0,
            'dados_graficos': json.dumps({}),
        }
    
    context = {
        'user': request.user,
        'stats': stats
    }
    return render(request, 'vendas_web/relatorios.html', context)

@login_required(login_url='vendas_web:login')
def vendas_view(request):
    """View para a página de gerenciamento de vendas (prospectos)"""
    context = {
        'user': request.user
    }
    return render(request, 'vendas_web/vendas.html', context)


def api_swagger_view(request):
    """View para a documentação Swagger da API"""
    context = {
        'user': request.user if request.user.is_authenticated else None
    }
    return render(request, 'vendas_web/api_swagger.html', context)


def n8n_guide_view(request):
    """View para o guia de integração N8N"""
    context = {
        'user': request.user if request.user.is_authenticated else None
    }
    return render(request, 'vendas_web/n8n_guide.html', context)


def analise_atendimentos_view(request):
    """View para análise de atendimentos"""
    context = {
        'user': request.user if request.user.is_authenticated else None
    }
    return render(request, 'vendas_web/analise_atendimentos.html', context)


def relatorio_conversoes_view(request):
    """View para relatório de conversões"""
    context = {
        'user': request.user if request.user.is_authenticated else None
    }
    return render(request, 'vendas_web/relatorio_conversoes.html', context)


def ajuda_view(request):
    """View para página de ajuda"""
    context = {
        'user': request.user if request.user.is_authenticated else None,
        'page_title': 'Central de Ajuda - Megalink'
    }
    return render(request, 'vendas_web/ajuda.html', context)

def documentacao_view(request):
    """View para página de documentação do projeto"""
    context = {
        'user': request.user if request.user.is_authenticated else None,
        'page_title': 'Documentação - Megalink'
    }
    return render(request, 'vendas_web/documentacao.html', context)


def api_documentation_view(request):
    """View para servir a documentação da API em markdown"""
    import os
    from django.http import HttpResponse
    
    # Ler o arquivo de documentação
    doc_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'api_documentation.md')
    
    try:
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Retornar como texto plano com quebras de linha preservadas
        response = HttpResponse(content, content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = 'inline; filename="api_documentation.txt"'
        return response
    except FileNotFoundError:
        return HttpResponse("Documentação não encontrada", status=404)


# ============================================================================
# APIs de Dados do Dashboard
# ============================================================================

def dashboard_data(request):
    """API para dados principais do dashboard"""
    try:
        # Cálculo das métricas conforme especificação:
        # 1. ATENDIMENTOS = Histórico de contatos com fluxo inicializado
        atendimentos = HistoricoContato.objects.filter(
            status='fluxo_inicializado'
        ).count()
        
        # 2. LEADS = Quantidade de LeadProspecto ativos
        leads = LeadProspecto.objects.filter(ativo=True).count()
        
        # 3. PROSPECTOS = Leads registrados no Hubsoft (com id_hubsoft preenchido)
        prospectos = LeadProspecto.objects.filter(
            id_hubsoft__isnull=False
        ).exclude(id_hubsoft='').count()

        # 4. CLIENTES = Clientes reais sincronizados do Hubsoft
        vendas = ClienteHubsoft.objects.count()
        
        # Calcular métricas do período anterior para comparação (últimos 30 dias vs 30 dias anteriores)
        hoje = timezone.now()
        inicio_periodo_atual = hoje - timedelta(days=30)
        inicio_periodo_anterior = hoje - timedelta(days=60)
        fim_periodo_anterior = hoje - timedelta(days=30)
        
        # Métricas do período anterior
        atendimentos_anterior = HistoricoContato.objects.filter(
            status='fluxo_inicializado',
            data_hora_contato__gte=inicio_periodo_anterior,
            data_hora_contato__lt=fim_periodo_anterior
        ).count()
        
        leads_anterior = LeadProspecto.objects.filter(
            ativo=True,
            data_cadastro__gte=inicio_periodo_anterior,
            data_cadastro__lt=fim_periodo_anterior
        ).count()
        
        prospectos_anterior = LeadProspecto.objects.filter(
            id_hubsoft__isnull=False,
            data_cadastro__gte=inicio_periodo_anterior,
            data_cadastro__lt=fim_periodo_anterior
        ).exclude(id_hubsoft='').count()

        vendas_anterior = ClienteHubsoft.objects.filter(
            data_criacao__gte=inicio_periodo_anterior,
            data_criacao__lt=fim_periodo_anterior
        ).count()
        
        # Calcular diferenças e variações percentuais
        def calcular_variacao(atual, anterior):
            if anterior == 0:
                if atual > 0:
                    return "+100.0%", atual
                else:
                    return "0.0%", 0
            else:
                variacao = ((atual - anterior) / anterior) * 100
                sinal = "+" if variacao >= 0 else ""
                return f"{sinal}{variacao:.1f}%", atual - anterior
        
        atendimentos_variacao, atendimentos_diff = calcular_variacao(atendimentos, atendimentos_anterior)
        leads_variacao, leads_diff = calcular_variacao(leads, leads_anterior)
        prospectos_variacao, prospectos_diff = calcular_variacao(prospectos, prospectos_anterior)
        vendas_variacao, vendas_diff = calcular_variacao(vendas, vendas_anterior)
        
        # Calcular taxas de conversão entre as etapas do funil
        taxa_atendimento_lead = f"{(leads/atendimentos*100):.2f}%" if atendimentos > 0 else "0.00%"
        taxa_lead_prospecto = f"{(prospectos/leads*100):.2f}%" if leads > 0 else "0.00%"
        taxa_prospecto_venda = f"{(vendas/prospectos*100):.2f}%" if prospectos > 0 else "0.00%"
        
        data = {
            'stats': {
                # Métricas principais conforme especificação
                'atendimentos': atendimentos,
                'atendimentos_variacao': atendimentos_variacao,
                'atendimentos_diff': atendimentos_diff,
                
                'leads': leads,
                'leads_variacao': leads_variacao,
                'leads_diff': leads_diff,
                
                'prospectos': prospectos,
                'prospectos_variacao': prospectos_variacao,
                'prospectos_diff': prospectos_diff,
                
                'vendas': vendas,
                'vendas_variacao': vendas_variacao,
                'vendas_diff': vendas_diff,
                
                # Taxas de conversão para as setas
                'taxa_atendimento_lead': taxa_atendimento_lead,
                'taxa_lead_prospecto': taxa_lead_prospecto,
                'taxa_prospecto_venda': taxa_prospecto_venda
            }
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dashboard_charts_data(request):
    """API para dados dos gráficos - Evolução dos últimos 7 dias"""
    try:
        # Função auxiliar para gerar dados dos últimos 7 dias
        def gerar_ultimos_7_dias(query_func):
            dados = []
            for i in range(7):
                data = timezone.now().date() - timedelta(days=i)
                count = query_func(data)
                dados.append({
                    'date': data.strftime('%d/%m'),
                    'count': count
                })
            dados.reverse()
            return dados
        
        # 1. ATENDIMENTOS dos últimos 7 dias (contatos com fluxo inicializado)
        def count_atendimentos(data):
            return HistoricoContato.objects.filter(
                data_hora_contato__date=data,
                status__in=['fluxo_inicializado']
            ).count()
        
        atendimentosUltimos7Dias = gerar_ultimos_7_dias(count_atendimentos)
        
        # 2. LEADS dos últimos 7 dias
        def count_leads(data):
            return LeadProspecto.objects.filter(
                data_cadastro__date=data,
                ativo=True
            ).count()
        
        leadsUltimos7Dias = gerar_ultimos_7_dias(count_leads)
        
        # 3. PROSPECTOS dos últimos 7 dias (leads registrados no Hubsoft)
        def count_prospectos(data):
            return LeadProspecto.objects.filter(
                data_cadastro__date=data,
                id_hubsoft__isnull=False,
            ).exclude(id_hubsoft='').count()

        prospectosUltimos7Dias = gerar_ultimos_7_dias(count_prospectos)

        # 4. CLIENTES dos últimos 7 dias (ClienteHubsoft sincronizados)
        def count_vendas(data):
            return ClienteHubsoft.objects.filter(
                data_criacao__date=data
            ).count()

        vendasUltimos7Dias = gerar_ultimos_7_dias(count_vendas)
        
        data = {
            # Dados para o gráfico de tendências (padrão será LEADS)
            'leadsUltimos7Dias': leadsUltimos7Dias,
            
            # Dados para troca dinâmica no frontend
            'atendimentosUltimos7Dias': atendimentosUltimos7Dias,
            'prospectosUltimos7Dias': prospectosUltimos7Dias,
            'vendasUltimos7Dias': vendasUltimos7Dias
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dashboard_tables_data(request):
    """API para dados das tabelas"""
    try:
        # Top empresas
        top_empresas = LeadProspecto.objects.filter(
            ativo=True,
            empresa__isnull=False
        ).exclude(empresa='').values('empresa').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Top origens
        top_origens = LeadProspecto.objects.filter(
            ativo=True
        ).values('origem').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        data = {
            'topEmpresas': list(top_empresas),
            'topOrigens': list(top_origens)
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dashboard_leads_data(request):
    """API para dados dos leads"""
    try:
        page = int(request.GET.get('page', 1))
        per_page = 20
        search = request.GET.get('search', '')
        origem_filter = request.GET.get('origem', '')
        status_filter = request.GET.get('status', '')
        ativo_filter = request.GET.get('ativo', '')
        valor_filter = request.GET.get('valor', '')
        data_inicio = request.GET.get('data_inicio', '')
        data_fim = request.GET.get('data_fim', '')
        lead_id = request.GET.get('id', '')
        
        leads_query = LeadProspecto.objects.all()
        
        # Filtro por ID específico (para modal de detalhes)
        if lead_id:
            leads_query = leads_query.filter(id=lead_id)
        else:
            # Filtros normais
            if search:
                leads_query = leads_query.filter(
                    Q(nome_razaosocial__icontains=search) |
                    Q(email__icontains=search) |
                    Q(telefone__icontains=search) |
                    Q(empresa__icontains=search) |
                    Q(cpf_cnpj__icontains=search) |
                    Q(id_hubsoft__icontains=search)
                )
            
            if origem_filter:
                leads_query = leads_query.filter(origem=origem_filter)
            
            if status_filter:
                leads_query = leads_query.filter(status_api=status_filter)
            
            if ativo_filter:
                leads_query = leads_query.filter(ativo=(ativo_filter.lower() == 'true'))
            
            # Filtro de valor
            if valor_filter:
                if valor_filter == 'sim':
                    leads_query = leads_query.filter(
                        Q(valor__isnull=False) & Q(valor__gt=0)
                    )
                elif valor_filter == 'nao':
                    leads_query = leads_query.filter(
                        Q(valor__isnull=True) | Q(valor=0)
                    )
            
            # Filtros de data
            if data_inicio:
                try:
                    from datetime import datetime
                    di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    leads_query = leads_query.filter(data_cadastro__date__gte=di)
                except ValueError:
                    pass
            
            if data_fim:
                try:
                    from datetime import datetime
                    df = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    leads_query = leads_query.filter(data_cadastro__date__lte=df)
                except ValueError:
                    pass
        
        total = leads_query.count()
        start = (page - 1) * per_page
        end = start + per_page
        
        leads = leads_query.order_by('-data_cadastro')[start:end]
        
        leads_data = []
        for lead in leads:
            leads_data.append({
                # Dados básicos
                'id': lead.id,
                'nome_razaosocial': lead.nome_razaosocial,
                'email': lead.email,
                'telefone': lead.telefone,
                'empresa': lead.empresa or '',
                
                # IDs e identificadores
                'id_hubsoft': lead.id_hubsoft or '',
                'id_origem': lead.id_origem or '',
                'id_origem_servico': lead.id_origem_servico or '',
                
                # Documentos
                'cpf_cnpj': lead.cpf_cnpj or '',
                'rg': lead.rg or '',
                
                # Endereço completo
                'endereco': lead.endereco or '',
                'rua': lead.rua or '',
                'numero_residencia': lead.numero_residencia or '',
                'bairro': lead.bairro or '',
                'cidade': lead.cidade or '',
                'estado': lead.estado or '',
                'cep': lead.cep or '',
                'ponto_referencia': lead.ponto_referencia or '',
                
                # Dados comerciais
                'valor': lead.get_valor_formatado(),
                'valor_numerico': float(lead.valor) if lead.valor else 0,
                'id_plano_rp': lead.id_plano_rp,
                'id_dia_vencimento': lead.id_dia_vencimento,
                'id_vendedor_rp': lead.id_vendedor_rp,
                'data_nascimento': lead.data_nascimento.isoformat() if lead.data_nascimento else '',
                
                # Status e origem
                'origem': lead.get_origem_display(),
                'origem_codigo': lead.origem,
                'canal_entrada': lead.canal_entrada or '',
                'tipo_entrada': lead.tipo_entrada or '',
                'status_api': lead.get_status_api_display(),
                'status_api_codigo': lead.status_api,
                'ativo': lead.ativo,
                
                # Qualificação e rastreamento
                'score_qualificacao': lead.score_qualificacao,
                'tentativas_contato': lead.tentativas_contato,
                'data_ultimo_contato': lead.data_ultimo_contato.isoformat() if lead.data_ultimo_contato else '',
                'motivo_rejeicao': lead.motivo_rejeicao or '',
                'custo_aquisicao': float(lead.custo_aquisicao) if lead.custo_aquisicao else 0,
                
                # Campanhas
                'campanha_origem_id': lead.campanha_origem.id if lead.campanha_origem else None,
                'campanha_origem_nome': lead.campanha_origem.nome if lead.campanha_origem else '',
                'campanha_conversao_id': lead.campanha_conversao.id if lead.campanha_conversao else None,
                'campanha_conversao_nome': lead.campanha_conversao.nome if lead.campanha_conversao else '',
                'total_campanhas_detectadas': lead.total_campanhas_detectadas,
                
                # Documentação e contrato
                'documentacao_completa': lead.documentacao_completa,
                'documentacao_validada': lead.documentacao_validada,
                'data_documentacao_completa': lead.data_documentacao_completa.isoformat() if lead.data_documentacao_completa else '',
                'data_documentacao_validada': lead.data_documentacao_validada.isoformat() if lead.data_documentacao_validada else '',
                'contrato_aceito': lead.contrato_aceito,
                'data_aceite_contrato': lead.data_aceite_contrato.isoformat() if lead.data_aceite_contrato else '',
                
                # Observações e datas
                'observacoes': lead.observacoes or '',
                'data_cadastro': lead.data_cadastro.isoformat() if lead.data_cadastro else None,
                'data_atualizacao': lead.data_atualizacao.isoformat() if lead.data_atualizacao else None,

                # Conversa do atendimento (HTML gerado)
                'html_conversa_path': lead.html_conversa_path or '',
                'data_geracao_html': lead.data_geracao_html.isoformat() if lead.data_geracao_html else '',
            })
        
        # Choices para filtros
        origem_choices = [
            {'value': choice[0], 'label': choice[1]}
            for choice in LeadProspecto.ORIGEM_CHOICES
        ]
        
        status_choices = [
            {'value': choice[0], 'label': choice[1]}
            for choice in LeadProspecto.STATUS_API_CHOICES
        ]
        
        # Calcular estatísticas totais (não apenas da página atual)
        from django.db.models import Sum, Count
        from django.utils import timezone
        from datetime import timedelta
        
        # Valor total de todos os leads com valor
        try:
            valor_total = LeadProspecto.objects.filter(
                valor__isnull=False,
                valor__gt=0
            ).aggregate(
                total=Sum('valor')
            )['total'] or 0
        except Exception:
            valor_total = 0
        
        # Leads de hoje
        try:
            hoje = timezone.now().date()
            leads_hoje = LeadProspecto.objects.filter(
                data_cadastro__date=hoje
            ).count()
        except Exception:
            leads_hoje = 0
        
        # Leads desta semana
        try:
            inicio_semana = hoje - timedelta(days=hoje.weekday())
            leads_semana = LeadProspecto.objects.filter(
                data_cadastro__date__gte=inicio_semana
            ).count()
        except Exception:
            leads_semana = 0
        
        data = {
            'leads': leads_data,
            'total': total,
            'page': page,
            'pages': (total + per_page - 1) // per_page,
            'origemChoices': origem_choices,
            'statusChoices': status_choices,
            'valor_total': valor_total,
            'leads_hoje': leads_hoje,
            'leads_semana': leads_semana
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dashboard_prospectos_data(request):
    """API para dados dos prospectos"""
    try:
        page = int(request.GET.get('page', 1))
        per_page = 20
        search = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        prioridade_filter = request.GET.get('prioridade', '')
        prospecto_id = request.GET.get('id', '')
        
        prospectos_query = Prospecto.objects.select_related('lead')
        
        # Filtro por ID específico (para modal de detalhes)
        if prospecto_id:
            prospectos_query = prospectos_query.filter(id=prospecto_id)
        else:
            # Filtros normais
            if search:
                prospectos_query = prospectos_query.filter(
                    Q(nome_prospecto__icontains=search) |
                    Q(id_prospecto_hubsoft__icontains=search) |
                    Q(lead__nome_razaosocial__icontains=search)
                )
            
            if status_filter:
                prospectos_query = prospectos_query.filter(status=status_filter)
            
            if prioridade_filter:
                prospectos_query = prospectos_query.filter(prioridade=prioridade_filter)
        
        total = prospectos_query.count()
        start = (page - 1) * per_page
        end = start + per_page
        
        prospectos = prospectos_query.order_by('-data_criacao')[start:end]
        
        prospectos_data = []
        for prospecto in prospectos:
            lead_data = None
            
            logger.debug("Processando Prospecto ID %s, id_hubsoft=%s, lead_id=%s",
                         prospecto.id, prospecto.id_prospecto_hubsoft,
                         prospecto.lead.id if prospecto.lead else None)
            
            # Estratégia 1: Buscar LeadProspecto pelo id_hubsoft do prospecto
            if prospecto.id_prospecto_hubsoft:
                try:
                    logger.debug("Buscando LeadProspecto com id_hubsoft=%s", prospecto.id_prospecto_hubsoft)
                    lead_prospecto = LeadProspecto.objects.filter(
                        id_hubsoft=prospecto.id_prospecto_hubsoft
                    ).first()
                    
                    if lead_prospecto:
                        logger.debug("Lead encontrado pelo id_hubsoft, lead_id=%s", lead_prospecto.id)
                        lead_data = {
                            'id': lead_prospecto.id,
                            'nome_razaosocial': lead_prospecto.nome_razaosocial or '',
                            'email': lead_prospecto.email or '',
                            'telefone': lead_prospecto.telefone or '',
                            'empresa': lead_prospecto.empresa or '',
                            'cpf_cnpj': lead_prospecto.cpf_cnpj or '',
                            'rg': lead_prospecto.rg or '',
                            'endereco': lead_prospecto.endereco or '',
                            'rua': lead_prospecto.rua or '',
                            'numero_residencia': lead_prospecto.numero_residencia or '',
                            'bairro': lead_prospecto.bairro or '',
                            'cidade': lead_prospecto.cidade or '',
                            'estado': lead_prospecto.estado or '',
                            'cep': lead_prospecto.cep or '',
                            'ponto_referencia': lead_prospecto.ponto_referencia or '',
                            'valor': lead_prospecto.get_valor_formatado(),
                            'id_plano_rp': lead_prospecto.id_plano_rp,
                            'id_dia_vencimento': lead_prospecto.id_dia_vencimento,
                            'id_vendedor_rp': lead_prospecto.id_vendedor_rp,
                            'data_nascimento': lead_prospecto.data_nascimento.isoformat() if lead_prospecto.data_nascimento else '',
                            'origem': lead_prospecto.get_origem_display(),
                            'status_api': lead_prospecto.get_status_api_display(),
                            'id_hubsoft': lead_prospecto.id_hubsoft or '',
                            'observacoes': lead_prospecto.observacoes or '',
                            'data_criacao': lead_prospecto.data_cadastro.isoformat() if lead_prospecto.data_cadastro else None
                        }
                    else:
                        logger.debug("Nenhum LeadProspecto encontrado com id_hubsoft=%s", prospecto.id_prospecto_hubsoft)
                except Exception as e:
                    logger.error("Erro ao buscar LeadProspecto por id_hubsoft: %s", e, exc_info=True)
            
            # Estratégia 2: Se o lead relacionado existe, tentar buscar o LeadProspecto pelo ID do lead
            if not lead_data and prospecto.lead:
                # Primeiro, verificar se o lead relacionado TEM id_hubsoft
                lead_id_hubsoft = getattr(prospecto.lead, 'id_hubsoft', None)
                if lead_id_hubsoft:
                    logger.debug("Lead relacionado (ID %s) tem id_hubsoft=%s", prospecto.lead.id, lead_id_hubsoft)
                    try:
                        lead_prospecto_alt = LeadProspecto.objects.filter(id_hubsoft=lead_id_hubsoft).first()
                        if lead_prospecto_alt and lead_prospecto_alt.id != prospecto.lead.id:
                            logger.debug("Encontrado LeadProspecto alternativo, lead_id=%s", lead_prospecto_alt.id)
                            # Usar este lead ao invés do relacionado direto
                            lead_data = {
                                'id': lead_prospecto_alt.id,
                                'nome_razaosocial': lead_prospecto_alt.nome_razaosocial or '',
                                'email': lead_prospecto_alt.email or '',
                                'telefone': lead_prospecto_alt.telefone or '',
                                'empresa': lead_prospecto_alt.empresa or '',
                                'cpf_cnpj': lead_prospecto_alt.cpf_cnpj or '',
                                'rg': lead_prospecto_alt.rg or '',
                                'endereco': lead_prospecto_alt.endereco or '',
                                'rua': lead_prospecto_alt.rua or '',
                                'numero_residencia': lead_prospecto_alt.numero_residencia or '',
                                'bairro': lead_prospecto_alt.bairro or '',
                                'cidade': lead_prospecto_alt.cidade or '',
                                'estado': lead_prospecto_alt.estado or '',
                                'cep': lead_prospecto_alt.cep or '',
                                'ponto_referencia': lead_prospecto_alt.ponto_referencia or '',
                                'valor': lead_prospecto_alt.get_valor_formatado(),
                                'id_plano_rp': lead_prospecto_alt.id_plano_rp,
                                'id_dia_vencimento': lead_prospecto_alt.id_dia_vencimento,
                                'id_vendedor_rp': lead_prospecto_alt.id_vendedor_rp,
                                'data_nascimento': lead_prospecto_alt.data_nascimento.isoformat() if lead_prospecto_alt.data_nascimento else '',
                                'origem': lead_prospecto_alt.get_origem_display(),
                                'status_api': lead_prospecto_alt.get_status_api_display(),
                                'id_hubsoft': lead_prospecto_alt.id_hubsoft or '',
                                'observacoes': lead_prospecto_alt.observacoes or '',
                                'data_criacao': lead_prospecto_alt.data_cadastro.isoformat() if lead_prospecto_alt.data_cadastro else None
                            }
                    except Exception as e:
                        logger.error("Erro ao buscar por id_hubsoft do lead relacionado: %s", e)
                
            # Estratégia 3: Usar o lead relacionado direto como último recurso
            if not lead_data and prospecto.lead:
                try:
                    logger.debug("Usando lead relacionado direto, lead_id=%s", prospecto.lead.id)
                    
                    lead_data = {
                        'id': prospecto.lead.id,
                        'nome_razaosocial': prospecto.lead.nome_razaosocial or '',
                        'email': prospecto.lead.email or '',
                        'telefone': prospecto.lead.telefone or '',
                        'empresa': prospecto.lead.empresa or '',
                        'cpf_cnpj': getattr(prospecto.lead, 'cpf_cnpj', '') or '',
                        'rg': getattr(prospecto.lead, 'rg', '') or '',
                        'endereco': getattr(prospecto.lead, 'endereco', '') or '',
                        'rua': getattr(prospecto.lead, 'rua', '') or '',
                        'numero_residencia': getattr(prospecto.lead, 'numero_residencia', '') or '',
                        'bairro': getattr(prospecto.lead, 'bairro', '') or '',
                        'cidade': getattr(prospecto.lead, 'cidade', '') or '',
                        'estado': getattr(prospecto.lead, 'estado', '') or '',
                        'cep': getattr(prospecto.lead, 'cep', '') or '',
                        'ponto_referencia': getattr(prospecto.lead, 'ponto_referencia', '') or '',
                        'valor': prospecto.lead.get_valor_formatado() if hasattr(prospecto.lead, 'get_valor_formatado') else 'R$ 0,00',
                        'id_plano_rp': getattr(prospecto.lead, 'id_plano_rp', None),
                        'id_dia_vencimento': getattr(prospecto.lead, 'id_dia_vencimento', None),
                        'id_vendedor_rp': getattr(prospecto.lead, 'id_vendedor_rp', None),
                        'data_nascimento': prospecto.lead.data_nascimento.isoformat() if hasattr(prospecto.lead, 'data_nascimento') and prospecto.lead.data_nascimento else '',
                        'origem': prospecto.lead.get_origem_display() if hasattr(prospecto.lead, 'get_origem_display') else '',
                        'status_api': prospecto.lead.get_status_api_display() if hasattr(prospecto.lead, 'get_status_api_display') else '',
                        'id_hubsoft': getattr(prospecto.lead, 'id_hubsoft', '') or '',
                        'observacoes': getattr(prospecto.lead, 'observacoes', '') or '',
                        'data_criacao': prospecto.lead.data_cadastro.isoformat() if hasattr(prospecto.lead, 'data_cadastro') and prospecto.lead.data_cadastro else None
                    }
                except Exception as e:
                    logger.error("Erro ao buscar dados do lead relacionado: %s", e, exc_info=True)
                    # Dados mínimos em caso de erro
                    lead_data = {
                        'id': prospecto.lead.id,
                        'nome_razaosocial': getattr(prospecto.lead, 'nome_razaosocial', ''),
                        'email': getattr(prospecto.lead, 'email', ''),
                        'telefone': getattr(prospecto.lead, 'telefone', ''),
                        'empresa': getattr(prospecto.lead, 'empresa', ''),
                        'valor': 'R$ 0,00'
                    }
            
            # Se ainda não tem lead_data, o prospecto não tem lead relacionado
            if not lead_data:
                logger.debug("Prospecto %s sem lead relacionado", prospecto.id)
            else:
                logger.debug("Lead_data final para prospecto %s: lead_id=%s", prospecto.id, lead_data.get('id'))
            
            prospectos_data.append({
                'id': prospecto.id,
                'nome_prospecto': prospecto.nome_prospecto,
                'lead': lead_data,
                'id_prospecto_hubsoft': prospecto.id_prospecto_hubsoft or '-',
                'status': prospecto.status,  # Status raw para o frontend
                'status_display': prospecto.get_status_display(),
                'prioridade': getattr(prospecto, 'prioridade', 1),
                'score_conversao': float(prospecto.score_conversao) if hasattr(prospecto, 'score_conversao') and prospecto.score_conversao else None,
                'data_criacao': prospecto.data_criacao.isoformat() if prospecto.data_criacao else None,
                'data_processamento': prospecto.data_processamento.isoformat() if prospecto.data_processamento else None,
                'observacoes': getattr(prospecto, 'observacoes', '') or '',
                'historico_status': getattr(prospecto, 'historico_status', '') or '',
                # Campos técnicos (apenas para admin/debug)
                'tentativas_processamento': prospecto.tentativas_processamento,
                'tempo_processamento': prospecto.get_tempo_processamento_formatado() if hasattr(prospecto, 'get_tempo_processamento_formatado') else '-',
                'erro_processamento': prospecto.erro_processamento[:50] + '...' if prospecto.erro_processamento and len(prospecto.erro_processamento) > 50 else (prospecto.erro_processamento or '-'),
                'dados_processamento': getattr(prospecto, 'dados_processamento', None),
                'resultado_processamento': getattr(prospecto, 'resultado_processamento', None)
            })
        
        # Status choices para o filtro
        status_choices = [
            {'value': choice[0], 'label': choice[1]}
            for choice in Prospecto.STATUS_CHOICES
        ]
        
        data = {
            'prospectos': prospectos_data,
            'total': total,
            'page': page,
            'pages': (total + per_page - 1) // per_page,
            'statusChoices': status_choices
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dashboard_historico_data(request):
    """API para dados do histórico de contatos"""
    try:
        page = int(request.GET.get('page', 1))
        per_page = 20
        search = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        sucesso_filter = request.GET.get('sucesso', '')
        data_inicio = request.GET.get('data_inicio', '')
        data_fim = request.GET.get('data_fim', '')
        contato_id = request.GET.get('id', '')
        
        historico_query = HistoricoContato.objects.select_related('lead')
        
        # Filtro por ID específico (para modal de detalhes)
        if contato_id:
            historico_query = historico_query.filter(id=contato_id)
        else:
            # Filtros normais
            if search:
                historico_query = historico_query.filter(
                    Q(telefone__icontains=search) |
                    Q(nome_contato__icontains=search) |
                    Q(lead__nome_razaosocial__icontains=search)
                )
            
            if status_filter:
                historico_query = historico_query.filter(status=status_filter)
            
            if sucesso_filter:
                historico_query = historico_query.filter(sucesso=(sucesso_filter.lower() == 'true'))
            
            if data_inicio:
                try:
                    data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    historico_query = historico_query.filter(data_hora_contato__date__gte=data_inicio_obj)
                except ValueError:
                    pass
            
            if data_fim:
                try:
                    data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    historico_query = historico_query.filter(data_hora_contato__date__lte=data_fim_obj)
                except ValueError:
                    pass
        
        total = historico_query.count()
        start = (page - 1) * per_page
        end = start + per_page
        
        historico = historico_query.order_by('-data_hora_contato')[start:end]
        
        historico_data = []
        for contato in historico:
            historico_data.append({
                'id': contato.id,
                'telefone': contato.telefone,
                'nome_contato': contato.nome_contato or '-',
                'lead_relacionado': contato.lead.nome_razaosocial if contato.lead else None,
                'status': contato.get_status_display(),
                'status_color': contato.get_status_display_color(),
                'data_hora_contato': contato.data_hora_contato.isoformat() if contato.data_hora_contato else None,
                'duracao_formatada': contato.get_duracao_formatada(),
                'sucesso': contato.sucesso,
                'converteu_lead': contato.converteu_lead,
                'converteu_venda': contato.converteu_venda,
                'valor_venda': contato.get_valor_venda_formatado() if contato.valor_venda else None,
                'data_conversao_lead': contato.data_conversao_lead.isoformat() if contato.data_conversao_lead else None,
                'data_conversao_venda': contato.data_conversao_venda.isoformat() if contato.data_conversao_venda else None,
                'origem_contato': contato.get_origem_contato_display() if contato.origem_contato else None,
                'transcricao': contato.transcricao or '-',
                'observacoes': contato.observacoes or '-',
                'ip_origem': contato.ip_origem or '-',
                'tempo_relativo': contato.get_tempo_relativo(),
                'dados_extras': contato.dados_extras,
                'bem_sucedido': contato.is_contato_bem_sucedido(),
                'conversao_completa': contato.is_conversao_completa()
            })
        
        # Status choices para o filtro
        status_choices = [
            {'value': choice[0], 'label': choice[1]}
            for choice in HistoricoContato.STATUS_CHOICES
        ]
        
        data = {
            'historico': historico_data,
            'total': total,
            'page': page,
            'pages': (total + per_page - 1) // per_page,
            'statusChoices': status_choices
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dashboard_contatos_realtime(request):
    """API para contatos em tempo real"""
    try:
        # Últimos 10 contatos
        contatos_recentes = HistoricoContato.objects.order_by('-data_hora_contato')[:10]
        
        contatos_data = []
        for contato in contatos_recentes:
            contatos_data.append({
                'id': contato.id,
                'telefone': contato.telefone,
                'nome_contato': contato.nome_contato or 'Não identificado',
                'status': contato.get_status_display(),
                'data_hora_contato': contato.data_hora_contato.isoformat() if contato.data_hora_contato else None,
                'tempo_relativo': contato.get_tempo_relativo(),
                'sucesso': contato.sucesso
            })
        
        data = {
            'contatos': contatos_data
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dashboard_contato_historico(request, telefone):
    """API para histórico detalhado de um telefone"""
    try:
        # Buscar todos os contatos deste telefone
        contatos = HistoricoContato.objects.filter(
            telefone=telefone
        ).order_by('-data_hora_contato')
        
        # Estatísticas básicas do telefone
        total_contatos = contatos.count()
        contatos_sucesso = contatos.filter(sucesso=True).count()
        contatos_finalizados = contatos.filter(status='fluxo_finalizado').count()
        contatos_transferidos = contatos.filter(status='transferido_humano').count()
        contatos_inicializados = contatos.filter(status='fluxo_inicializado').count()
        contatos_convertidos_lead = contatos.filter(converteu_lead=True).count()
        contatos_vendas = contatos.filter(converteu_venda=True).count()
        duracao_total = sum([c.duracao_segundos or 0 for c in contatos])
        
        # Calcular taxas
        taxa_sucesso = (contatos_sucesso / total_contatos * 100) if total_contatos > 0 else 0
        taxa_finalizacao = ((contatos_finalizados + contatos_transferidos) / total_contatos * 100) if total_contatos > 0 else 0
        taxa_conversao_lead = (contatos_convertidos_lead / total_contatos * 100) if total_contatos > 0 else 0
        taxa_conversao_venda = (contatos_vendas / contatos_convertidos_lead * 100) if contatos_convertidos_lead > 0 else 0
        
        # Último contato
        ultimo_contato = contatos.first()
        ultimo_contato_data = ultimo_contato.data_hora_contato.isoformat() if ultimo_contato else None
        
        # Valor total das vendas
        valor_total_vendas = contatos.filter(converteu_venda=True).aggregate(
            total=Sum('valor_venda')
        )['total'] or 0
        
        # Timeline dos contatos com informações detalhadas
        timeline_data = []
        for contato in contatos:
            timeline_data.append({
                'id': contato.id,
                'data_hora_contato': contato.data_hora_contato.isoformat() if contato.data_hora_contato else None,
                'status': contato.get_status_display(),
                'nome_contato': contato.nome_contato or 'Não identificado',
                'duracao_formatada': contato.get_duracao_formatada(),
                'sucesso': contato.sucesso,
                'converteu_lead': contato.converteu_lead,
                'converteu_venda': contato.converteu_venda,
                'valor_venda': contato.get_valor_venda_formatado() if contato.valor_venda else None,
                'observacoes': contato.observacoes or '',
                'transcricao': contato.transcricao or '',
                'tempo_relativo': contato.get_tempo_relativo(),
                'origem_contato': contato.get_origem_contato_display() if contato.origem_contato else None
            })
        
        data = {
            'telefone': telefone,
            'total': total_contatos,
            'ultimo_contato': ultimo_contato_data,
            'taxa_sucesso': f"{taxa_sucesso:.1f}%",
            'estatisticas': {
                'total_contatos': total_contatos,
                'contatos_sucesso': contatos_sucesso,
                'contatos_finalizados': contatos_finalizados,
                'contatos_transferidos': contatos_transferidos,
                'contatos_inicializados': contatos_inicializados,
                'contatos_convertidos_lead': contatos_convertidos_lead,
                'contatos_vendas': contatos_vendas,
                'duracao_total_minutos': duracao_total // 60 if duracao_total else 0,
                'taxa_sucesso': taxa_sucesso,
                'taxa_finalizacao': taxa_finalizacao,
                'taxa_conversao_lead': taxa_conversao_lead,
                'taxa_conversao_venda': taxa_conversao_venda,
                'valor_total_vendas': valor_total_vendas,
                'valor_total_vendas_formatado': f"R$ {valor_total_vendas:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            },
            'historico': timeline_data,
            'timeline': timeline_data
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dashboard_ultimas_conversoes(request):
    """API para últimas conversões — leads que viraram clientes Hubsoft"""
    try:
        limite = int(request.GET.get('limite', 6))

        # Leads que possuem ao menos um ClienteHubsoft vinculado
        clientes = (
            ClienteHubsoft.objects
            .select_related('lead')
            .prefetch_related('servicos')
            .filter(lead__isnull=False)
            .order_by('-data_criacao')[:limite]
        )

        conversoes = []
        for cliente in clientes:
            lead = cliente.lead

            # Serviço principal (primeiro serviço ativo, ou o primeiro disponível)
            servicos = list(cliente.servicos.all())
            servico_principal = next(
                (s for s in servicos if s.status_prefixo and 'habilit' in s.status_prefixo.lower()),
                servicos[0] if servicos else None
            )

            conversoes.append({
                'nome': cliente.nome_razaosocial,
                'cpf_cnpj': cliente.cpf_cnpj or '',
                'telefone': cliente.telefone_primario or (lead.telefone if lead else ''),
                'origem': lead.get_origem_display() if lead else '-',
                'data_sync': cliente.data_sync.isoformat() if cliente.data_sync else None,
                'data_cadastro': lead.data_cadastro.isoformat() if lead and lead.data_cadastro else None,
                'servico_nome': servico_principal.nome if servico_principal else '-',
                'servico_status': servico_principal.status if servico_principal else '-',
                'valor': (
                    f"R$ {servico_principal.valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    if servico_principal and servico_principal.valor else '-'
                ),
                'ativo': cliente.ativo,
                'lead_id': lead.id if lead else None,
            })

        return JsonResponse({'conversoes': conversoes})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# APIs de Validação de Vendas
# ============================================================================

def aprovar_venda_api(request):
    """API para aprovar uma venda"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        import json
        data = json.loads(request.body)
        
        prospecto_id = data.get('prospecto_id')
        observacoes = data.get('observacoes', '')
        
        if not prospecto_id:
            return JsonResponse({'error': 'ID do prospecto é obrigatório'}, status=400)
        
        if not observacoes.strip():
            return JsonResponse({'error': 'Observações da validação são obrigatórias'}, status=400)
        
        # Buscar prospecto
        prospecto = Prospecto.objects.get(id=prospecto_id)
        
        # Verificar se pode ser aprovado
        if prospecto.status not in ['processado', 'aguardando_validacao']:
            return JsonResponse({'error': 'Prospecto não pode ser aprovado neste status'}, status=400)
        
        # Atualizar status
        prospecto.status = 'validacao_aprovada'
        prospecto.save()
        
        # Criar registro de validação (pode adicionar uma tabela específica depois)
        # Por enquanto, armazenar nos dados de processamento
        usuario_validacao = f"{request.user.username}" if request.user.is_authenticated else "Sistema"
        if request.user.is_authenticated and (request.user.first_name or request.user.last_name):
            usuario_validacao = f"{request.user.first_name} {request.user.last_name}".strip()
        
        validacao_data = {
            'observacoes': observacoes,
            'data_validacao': timezone.now().isoformat(),
            'status_validacao': 'aprovada',
            'usuario_validacao': usuario_validacao
        }
        
        # Atualizar resultado_processamento de forma segura
        _atualizar_resultado_processamento(prospecto, validacao_data)
        
        prospecto.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Venda aprovada com sucesso',
            'prospecto_id': prospecto.id,
            'novo_status': prospecto.status
        })
        
    except Prospecto.DoesNotExist:
        return JsonResponse({'error': 'Prospecto não encontrado'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Dados JSON inválidos'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


def rejeitar_venda_api(request):
    """API para rejeitar uma venda"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        import json
        data = json.loads(request.body)
        
        prospecto_id = data.get('prospecto_id')
        motivo_rejeicao = data.get('motivo_rejeicao', '')
        
        if not prospecto_id:
            return JsonResponse({'error': 'ID do prospecto é obrigatório'}, status=400)
        
        if not motivo_rejeicao.strip():
            return JsonResponse({'error': 'Motivo da rejeição é obrigatório'}, status=400)
        
        # Buscar prospecto
        prospecto = Prospecto.objects.get(id=prospecto_id)
        
        # Verificar se pode ser rejeitado
        if prospecto.status not in ['processado', 'aguardando_validacao']:
            return JsonResponse({'error': 'Prospecto não pode ser rejeitado neste status'}, status=400)
        
        # Atualizar status
        prospecto.status = 'validacao_rejeitada'
        prospecto.save()
        
        # Criar registro de rejeição
        usuario_validacao = f"{request.user.username}" if request.user.is_authenticated else "Sistema"
        if request.user.is_authenticated and (request.user.first_name or request.user.last_name):
            usuario_validacao = f"{request.user.first_name} {request.user.last_name}".strip()
        
        rejeicao_data = {
            'motivo_rejeicao': motivo_rejeicao,
            'data_validacao': timezone.now().isoformat(),
            'status_validacao': 'rejeitada',
            'usuario_validacao': usuario_validacao
        }
        
        # Atualizar resultado_processamento de forma segura
        _atualizar_resultado_processamento(prospecto, rejeicao_data)
        
        prospecto.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Venda rejeitada',
            'prospecto_id': prospecto.id,
            'novo_status': prospecto.status
        })
        
    except Prospecto.DoesNotExist:
        return JsonResponse({'error': 'Prospecto não encontrado'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Dados JSON inválidos'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


def historico_contatos_api(request):
    """API para buscar histórico de contatos por lead ID ou telefone"""
    try:
        lead_id = request.GET.get('lead_id')
        prospecto_id = request.GET.get('prospecto_id')
        telefone = request.GET.get('telefone')
        
        if not lead_id and not prospecto_id and not telefone:
            return JsonResponse({'error': 'É necessário fornecer lead_id, prospecto_id ou telefone'}, status=400)
        
        historicos_query = HistoricoContato.objects.select_related('lead')
        
        # Buscar por lead_id
        if lead_id:
            try:
                lead = LeadProspecto.objects.get(id=lead_id)
                historicos_query = historicos_query.filter(
                    Q(lead_id=lead_id) | Q(telefone=lead.telefone)
                )
            except LeadProspecto.DoesNotExist:
                return JsonResponse({'error': 'Lead não encontrado'}, status=404)
        
        # Buscar por prospecto_id
        elif prospecto_id:
            try:
                prospecto = Prospecto.objects.get(id=prospecto_id)
                if prospecto.lead:
                    historicos_query = historicos_query.filter(
                        Q(lead_id=prospecto.lead.id) | Q(telefone=prospecto.lead.telefone)
                    )
                else:
                    # Se o prospecto não tem lead, buscar por nome semelhante (se houver telefone)
                    return JsonResponse({'historicos': [], 'total': 0, 'info': 'Prospecto sem lead associado'})
            except Prospecto.DoesNotExist:
                return JsonResponse({'error': 'Prospecto não encontrado'}, status=404)
        
        # Buscar por telefone
        elif telefone:
            historicos_query = historicos_query.filter(telefone=telefone)
        
        # Ordenar por data mais recente
        historicos = historicos_query.order_by('-data_hora_contato')[:50]  # Limitar a 50 registros mais recentes
        
        historicos_data = []
        for historico in historicos:
            # Formatar duração
            duracao_formatada = 'N/A'
            if historico.duracao_segundos:
                minutos = historico.duracao_segundos // 60
                segundos = historico.duracao_segundos % 60
                duracao_formatada = f"{minutos}m {segundos}s" if minutos > 0 else f"{segundos}s"
            
            # Status formatado
            status_info = {
                'status': historico.status,
                'display': historico.get_status_display(),
                'categoria': get_status_categoria(historico.status)
            }
            
            # Dados completos do lead relacionado
            lead_data = None
            if historico.lead:
                lead_data = {
                    'id': historico.lead.id,
                    'nome': historico.lead.nome_razaosocial,
                    'nome_razaosocial': historico.lead.nome_razaosocial,
                    'email': historico.lead.email,
                    'telefone': historico.lead.telefone,
                    'empresa': historico.lead.empresa or '',
                    'cpf_cnpj': historico.lead.cpf_cnpj or '',
                    'rg': historico.lead.rg or '',
                    'endereco': historico.lead.endereco or '',
                    'rua': historico.lead.rua or '',
                    'numero_residencia': historico.lead.numero_residencia or '',
                    'bairro': historico.lead.bairro or '',
                    'cidade': historico.lead.cidade or '',
                    'estado': historico.lead.estado or '',
                    'cep': historico.lead.cep or '',
                    'ponto_referencia': historico.lead.ponto_referencia or '',
                    'valor': historico.lead.get_valor_formatado(),
                    'valor_numerico': float(historico.lead.valor) if historico.lead.valor else 0,
                    'id_plano_rp': historico.lead.id_plano_rp,
                    'id_dia_vencimento': historico.lead.id_dia_vencimento,
                    'id_vendedor_rp': historico.lead.id_vendedor_rp,
                    'data_nascimento': historico.lead.data_nascimento.isoformat() if historico.lead.data_nascimento else '',
                    'origem': historico.lead.get_origem_display(),
                    'status_api': historico.lead.get_status_api_display(),
                    'id_hubsoft': historico.lead.id_hubsoft or '',
                    'observacoes': historico.lead.observacoes or ''
                }
            
            historico_item = {
                'id': historico.id,
                'data_hora': historico.data_hora_contato.isoformat() if historico.data_hora_contato else None,
                'status': status_info,
                'telefone': historico.telefone or '',
                'nome_contato': historico.nome_contato or 'Não identificado',
                'duracao': duracao_formatada,
                'duracao_segundos': historico.duracao_segundos or 0,
                'transcricao': historico.transcricao[:200] + '...' if historico.transcricao and len(historico.transcricao) > 200 else (historico.transcricao or ''),
                'transcricao_completa': historico.transcricao or '',
                'observacoes': historico.observacoes or '',
                'protocolo_atendimento': historico.protocolo_atendimento or '',
                'codigo_atendimento': historico.codigo_atendimento or '',
                'id_conta': historico.id_conta or '',
                'numero_conta': historico.numero_conta or '',
                'ultima_mensagem': historico.ultima_mensagem or '',
                'ip_origem': historico.ip_origem or '',
                'user_agent': historico.user_agent or '',
                'origem_contato': historico.get_origem_contato_display() if historico.origem_contato else '',
                'converteu_lead': historico.converteu_lead,
                'converteu_venda': historico.converteu_venda,
                'sucesso': historico.sucesso,
                'lead': lead_data
            }
            
            historicos_data.append(historico_item)
        
        # Estatísticas do histórico
        total_contatos = len(historicos_data)
        contatos_convertidos = sum(1 for h in historicos_data if h['converteu_lead'])
        vendas_convertidas = sum(1 for h in historicos_data if h['converteu_venda'])
        
        data = {
            'historicos': historicos_data,
            'total': total_contatos,
            'estatisticas': {
                'total_contatos': total_contatos,
                'contatos_convertidos': contatos_convertidos,
                'vendas_convertidas': vendas_convertidas,
                'taxa_conversao_lead': (contatos_convertidos / total_contatos * 100) if total_contatos > 0 else 0,
                'taxa_conversao_venda': (vendas_convertidas / total_contatos * 100) if total_contatos > 0 else 0
            }
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


def get_status_categoria(status):
    """Categoriza o status para facilitar a exibição"""
    categorias = {
        'fluxo_inicializado': 'inicio',
        'fluxo_finalizado': 'sucesso',
        'transferido_humano': 'transferencia',
        'convertido_lead': 'conversao',
        'venda_confirmada': 'venda',
        'chamada_perdida': 'problema',
        'ocupado': 'problema',
        'desligou': 'problema',
        'nao_atendeu': 'problema',
        'erro_sistema': 'erro',
        'timeout': 'erro'
    }
    return categorias.get(status, 'outros')


def _parse_bool(value):
    if value is None:
        return None
    value_lower = str(value).strip().lower()
    if value_lower in ['1', 'true', 't', 'sim', 'yes', 'y']:
        return True
    if value_lower in ['0', 'false', 'f', 'nao', 'não', 'no', 'n']:
        return False
    return None


def _safe_ordering(ordering_param, allowed_fields):
    if not ordering_param:
        return None
    raw = ordering_param.strip()
    desc = raw.startswith('-')
    field = raw[1:] if desc else raw
    if field in allowed_fields:
        return f"-{field}" if desc else field
    return None


# ============================================================================
# APIs de Consulta
# ============================================================================

def consultar_leads_api(request):
    """API GET de consulta sobre LeadProspecto com filtros e paginação."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        per_page = max(1, min(per_page, 100))

        lead_id = request.GET.get('id')
        search = request.GET.get('search')
        origem = request.GET.get('origem')
        status_api = request.GET.get('status_api')
        ativo_param = request.GET.get('ativo')
        data_inicio = request.GET.get('data_inicio')  # formato YYYY-MM-DD
        data_fim = request.GET.get('data_fim')        # formato YYYY-MM-DD
        ordering = request.GET.get('ordering')

        qs = LeadProspecto.objects.all()

        if lead_id:
            qs = qs.filter(id=lead_id)
        else:
            if search:
                qs = qs.filter(
                    Q(nome_razaosocial__icontains=search) |
                    Q(email__icontains=search) |
                    Q(telefone__icontains=search) |
                    Q(empresa__icontains=search) |
                    Q(cpf_cnpj__icontains=search) |
                    Q(id_hubsoft__icontains=search)
                )

            if origem:
                qs = qs.filter(origem=origem)

            if status_api:
                qs = qs.filter(status_api=status_api)

            ativo = _parse_bool(ativo_param)
            if ativo is not None:
                qs = qs.filter(ativo=ativo)

            if data_inicio:
                try:
                    di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    qs = qs.filter(data_cadastro__date__gte=di)
                except ValueError:
                    pass

            if data_fim:
                try:
                    df = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    qs = qs.filter(data_cadastro__date__lte=df)
                except ValueError:
                    pass

        allowed_order_fields = {'id', 'data_cadastro', 'data_atualizacao', 'nome_razaosocial', 'valor'}
        order_by = _safe_ordering(ordering, allowed_order_fields) or '-data_cadastro'
        qs = qs.order_by(order_by)

        total = qs.count()
        start = (page - 1) * per_page
        end = start + per_page
        items = qs[start:end]

        results = []
        for item in items:
            data = _serialize_instance(item)
            # Enriquecimentos úteis
            data['valor_formatado'] = item.get_valor_formatado()
            data['origem_display'] = item.get_origem_display()
            data['status_api_display'] = item.get_status_api_display()
            results.append(data)

        return JsonResponse({
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'ordering': order_by,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def consultar_historicos_api(request):
    """API GET de consulta sobre HistoricoContato com filtros e paginação."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        per_page = max(1, min(per_page, 100))

        contato_id = request.GET.get('id')
        telefone = request.GET.get('telefone')
        lead_id = request.GET.get('lead_id')
        status = request.GET.get('status')
        sucesso_param = request.GET.get('sucesso')
        conv_lead_param = request.GET.get('converteu_lead')
        conv_venda_param = request.GET.get('converteu_venda')
        data_inicio = request.GET.get('data_inicio')  # YYYY-MM-DD
        data_fim = request.GET.get('data_fim')        # YYYY-MM-DD
        ordering = request.GET.get('ordering')

        qs = HistoricoContato.objects.select_related('lead')

        if contato_id:
            qs = qs.filter(id=contato_id)
        else:
            if telefone:
                qs = qs.filter(telefone__icontains=telefone)

            if lead_id:
                qs = qs.filter(lead_id=lead_id)

            if status:
                qs = qs.filter(status=status)

            sucesso = _parse_bool(sucesso_param)
            if sucesso is not None:
                qs = qs.filter(sucesso=sucesso)

            converteu_lead = _parse_bool(conv_lead_param)
            if converteu_lead is not None:
                qs = qs.filter(converteu_lead=converteu_lead)

            converteu_venda = _parse_bool(conv_venda_param)
            if converteu_venda is not None:
                qs = qs.filter(converteu_venda=converteu_venda)

            if data_inicio:
                try:
                    di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    qs = qs.filter(data_hora_contato__date__gte=di)
                except ValueError:
                    pass

            if data_fim:
                try:
                    df = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    qs = qs.filter(data_hora_contato__date__lte=df)
                except ValueError:
                    pass

        allowed_order_fields = {'id', 'data_hora_contato', 'telefone', 'status'}
        order_by = _safe_ordering(ordering, allowed_order_fields) or '-data_hora_contato'
        qs = qs.order_by(order_by)

        total = qs.count()
        start = (page - 1) * per_page
        end = start + per_page
        items = qs[start:end]

        results = []
        for item in items:
            data = _serialize_instance(item)
            # Enriquecimentos úteis
            data['status_display'] = item.get_status_display()
            data['duracao_formatada'] = item.get_duracao_formatada()
            data['valor_venda_formatado'] = item.get_valor_venda_formatado() if item.valor_venda else None
            if item.lead:
                data['lead_info'] = {
                    'id': item.lead.id,
                    'nome_razaosocial': item.lead.nome_razaosocial,
                    'telefone': item.lead.telefone,
                    'empresa': item.lead.empresa,
                }
            results.append(data)

        return JsonResponse({
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'ordering': order_by,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# VIEWS PARA CADASTRO DE CLIENTES
# ============================================================================

def cadastro_cliente_view(request):
    """View para a página de cadastro de clientes"""
    try:
        # Buscar configuração ativa
        config = ConfiguracaoCadastro.objects.filter(ativo=True).first()
        if not config:
            # Configuração padrão se não houver nenhuma
            config = {
                'titulo_pagina': 'Cadastro de Cliente - Megalink',
                'subtitulo_pagina': 'Preencha seus dados para começar',
                'telefone_suporte': '(89) 2221-0068',
                'whatsapp_suporte': '558922210068',
                'email_suporte': 'contato@megalinkpiaui.com.br',
                'mostrar_selecao_plano': True,
                'cpf_obrigatorio': True,
                'email_obrigatorio': True,
                'telefone_obrigatorio': True,
                'endereco_obrigatorio': True,
                'validar_cep': True,
                'validar_cpf': True,
                'mostrar_progress_bar': True,
                'numero_etapas': 6,
                'mensagem_sucesso': 'Parabéns! Seu cadastro foi realizado com sucesso.',
                'instrucoes_pos_cadastro': 'Em breve nossa equipe entrará em contato para agendar a instalação.',
                'criar_lead_automatico': True,
                'origem_lead_padrao': 'site',
                # Configurações visuais
                'logo_url': 'https://i.ibb.co/q3MyCdBZ/Ativo-33.png',
                'background_type': 'gradient',
                'background_color_1': '#667eea',
                'background_color_2': '#764ba2',
                'background_image_url': '',
                'primary_color': '#667eea',
                'secondary_color': '#764ba2',
                'success_color': '#2ecc71',
                'error_color': '#e74c3c',
                # Configurações de documentação
                'solicitar_documentacao': True,
                'texto_instrucao_selfie': 'Por favor, tire uma selfie segurando seu documento de identificação próximo ao rosto',
                'texto_instrucao_doc_frente': 'Tire uma foto nítida da frente do seu documento',
                'texto_instrucao_doc_verso': 'Tire uma foto nítida do verso do seu documento',
                'tamanho_max_arquivo_mb': 5,
                'formatos_aceitos': 'jpg,jpeg,png,webp',
                # Configurações de contrato
                'exibir_contrato': True,
                'titulo_contrato': 'Termos de Serviço e Contrato',
                'texto_contrato': '''CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE INTERNET

1. DAS PARTES
Este contrato é celebrado entre a EMPRESA (prestadora) e o CLIENTE (contratante).

2. DO OBJETO
O presente contrato tem por objeto a prestação de serviços de internet banda larga.

3. DAS OBRIGAÇÕES DA PRESTADORA
- Fornecer o serviço de internet conforme o plano contratado
- Manter a qualidade e estabilidade da conexão
- Prestar suporte técnico quando necessário

4. DAS OBRIGAÇÕES DO CONTRATANTE
- Pagar pontualmente as mensalidades
- Zelar pelos equipamentos fornecidos em comodato
- Utilizar o serviço de forma legal e ética

5. DO PRAZO
Este contrato tem prazo indeterminado, podendo ser rescindido por qualquer das partes.

6. DO FORO
Fica eleito o foro da comarca local para dirimir quaisquer questões.

Ao aceitar este contrato, você concorda com todos os termos descritos.''',
                'tempo_minimo_leitura_segundos': 30,
                'texto_aceite_contrato': 'Li e concordo com os termos do contrato'
            }
        
        # Buscar planos ativos
        planos = PlanoInternet.objects.filter(ativo=True).order_by('ordem_exibicao', 'valor_mensal')
        
        # Buscar opções de vencimento
        vencimentos = OpcaoVencimento.objects.filter(ativo=True).order_by('ordem_exibicao', 'dia_vencimento')
        
        context = {
            'config': config,
            'planos': planos,
            'vencimentos': vencimentos
        }
        
        return render(request, 'vendas_web/cadastro.html', context)
        
    except Exception as e:
        # Log do erro
        logger.error("Erro na view de cadastro: %s", e, exc_info=True)
        return render(request, 'vendas_web/cadastro.html', {
            'error': 'Erro ao carregar configurações. Tente novamente.'
        })


@csrf_exempt
@require_http_methods(["POST"])
def api_cadastro_cliente(request):
    """API para processar cadastro de clientes"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("=== INICIANDO CADASTRO DE CLIENTE ===")
        logger.info(f"Content-Length: {request.META.get('CONTENT_LENGTH', 'unknown')}")
        logger.info(f"Content-Type: {request.META.get('CONTENT_TYPE', 'unknown')}")
        
        data = json.loads(request.body)
        logger.info(f"Dados recebidos: {list(data.keys())}")
        
        # Extrair dados do request
        ip_cliente = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Criar instância do cadastro
        cadastro = CadastroCliente(
            nome_completo=data.get('nome_completo', '').strip(),
            cpf=data.get('cpf', '').replace('.', '').replace('-', ''),
            rg=data.get('rg', '').strip() if data.get('rg') else None,
            email=data.get('email', '').strip().lower(),
            telefone=data.get('telefone', '').replace('(', '').replace(')', '').replace('-', '').replace(' ', ''),
            data_nascimento=data.get('data_nascimento'),
            cep=data.get('cep', '').replace('-', ''),
            endereco=data.get('endereco', '').strip(),
            numero=data.get('numero', '').strip(),
            bairro=data.get('bairro', '').strip(),
            cidade=data.get('cidade', '').strip(),
            estado=data.get('estado', '').strip().upper(),
            ip_cliente=ip_cliente,
            user_agent=user_agent,
            origem_cadastro=data.get('origem_cadastro', 'site')
        )
        
        # Definir plano se selecionado
        if data.get('plano_id'):
            try:
                plano = PlanoInternet.objects.get(id=data['plano_id'], ativo=True)
                cadastro.plano_selecionado = plano
            except PlanoInternet.DoesNotExist:
                pass
        
        # Definir vencimento se selecionado
        if data.get('vencimento_id'):
            try:
                vencimento = OpcaoVencimento.objects.get(id=data['vencimento_id'], ativo=True)
                cadastro.vencimento_selecionado = vencimento
            except OpcaoVencimento.DoesNotExist:
                pass
        
        # Validar dados pessoais
        erros_pessoais = cadastro.validar_dados_pessoais()
        if erros_pessoais:
            return JsonResponse({
                'success': False,
                'errors': erros_pessoais,
                'step': 'dados_pessoais'
            }, status=400)
        
        # Validar endereço
        erros_endereco = cadastro.validar_endereco()
        if erros_endereco:
            return JsonResponse({
                'success': False,
                'errors': erros_endereco,
                'step': 'endereco'
            }, status=400)
        
        # Processar dados do contrato
        if data.get('contrato_aceito'):
            cadastro.contrato_aceito = True
            cadastro.data_aceite_contrato = timezone.now()
            cadastro.ip_aceite_contrato = ip_cliente
            cadastro.tempo_leitura_contrato = data.get('tempo_leitura_contrato', 0)
        
        # Processar aceite dos termos
        if data.get('termos_aceitos'):
            cadastro.termos_aceitos = True
            cadastro.data_aceite_termos = timezone.now()
        
        # Salvar cadastro
        cadastro.save()
        
        # Atualizar status para finalizado
        cadastro.status = 'finalizado'
        cadastro.data_finalizacao = timezone.now()
        cadastro.save()
        
        # Finalizar cadastro (gera lead e histórico)
        if cadastro.finalizar_cadastro():
            lead = cadastro.lead_gerado
            
            # Atualizar dados do lead com informações completas
            if lead:
                # Atualizar campos básicos do lead
                lead.nome_razaosocial = cadastro.nome_completo
                lead.email = cadastro.email
                lead.telefone = cadastro.telefone
                lead.cpf_cnpj = cadastro.cpf
                lead.rg = cadastro.rg
                lead.data_nascimento = cadastro.data_nascimento
                
                # Atualizar endereço
                lead.cep = cadastro.cep
                lead.endereco = f"{cadastro.endereco}, {cadastro.numero}"
                lead.rua = cadastro.endereco
                lead.numero_residencia = cadastro.numero
                lead.bairro = cadastro.bairro
                lead.cidade = cadastro.cidade
                lead.estado = cadastro.estado
                
                # Atualizar plano e vencimento
                if cadastro.plano_selecionado:
                    lead.id_plano_rp = cadastro.plano_selecionado.id_sistema_externo
                    lead.valor = cadastro.plano_selecionado.valor_mensal
                
                if cadastro.vencimento_selecionado:
                    # Usar a descrição do vencimento (que contém o ID do sistema externo)
                    lead.id_dia_vencimento = cadastro.vencimento_selecionado.descricao
                
                # Definir origem
                lead.origem = 'site'
                
                # Definir IDs customizáveis da configuração
                config = ConfiguracaoCadastro.objects.filter(ativo=True).first()
                if config:
                    lead.id_origem = config.id_origem
                    lead.id_origem_servico = config.id_origem_servico
                    lead.id_vendedor_rp = config.id_vendedor
                else:
                    # Valores padrão se não houver configuração
                    lead.id_origem = data.get('id_origem', 148)
                    lead.id_origem_servico = data.get('id_origem_servico', 63)
                    lead.id_vendedor_rp = data.get('id_vendedor', 901)
                
                lead.save()
            
            # Processar documentos se existirem
            if data.get('documentos') and lead:
                documentos = data.get('documentos', {})
                for tipo_doc, doc_data in documentos.items():
                    if doc_data and isinstance(doc_data, dict):
                        try:
                            DocumentoLead.objects.create(
                                lead=lead,
                                tipo_documento=tipo_doc,
                                arquivo_base64=doc_data.get('base64', ''),
                                nome_arquivo=doc_data.get('name', ''),
                                tamanho_arquivo=doc_data.get('size', 0),
                                formato_arquivo=doc_data.get('type', '')
                            )
                        except Exception as e:
                            logger.error(f"Erro ao salvar documento {tipo_doc}: {str(e)}")
                
                # Atualizar status de documentação do lead
                lead.documentacao_completa = True
                lead.data_documentacao_completa = timezone.now()
                lead.save()
            
            # Processar aceite de contrato no lead
            if data.get('contrato_aceito') and lead:
                lead.contrato_aceito = True
                lead.data_aceite_contrato = timezone.now()
                lead.ip_aceite_contrato = ip_cliente
                lead.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Cadastro realizado com sucesso!',
                'cadastro_id': cadastro.id,
                'lead_id': lead.id if lead else None
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Erro ao finalizar cadastro. Tente novamente.',
                'errors': cadastro.erros_validacao if hasattr(cadastro, 'erros_validacao') else ['Erro interno']
            }, status=500)
        
    except json.JSONDecodeError as e:
        logger.error(f"Erro JSON Decode: {str(e)}")
        logger.error(f"Body: {request.body[:500]}")
        return JsonResponse({
            'success': False,
            'message': 'Dados inválidos enviados.'
        }, status=400)
    except Exception as e:
        logger.error(f"Erro ao processar cadastro: {str(e)}")
        logger.error(f"Traceback: ", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Erro interno: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def api_planos_internet(request):
    """API para buscar planos de internet"""
    try:
        planos = PlanoInternet.objects.filter(ativo=True).order_by('ordem_exibicao', 'valor_mensal')
        
        planos_data = []
        for plano in planos:
            planos_data.append({
                'id': plano.id,
                'nome': plano.nome,
                'descricao': plano.descricao,
                'velocidade_download': plano.velocidade_download,
                'velocidade_upload': plano.velocidade_upload,
                'valor_mensal': float(plano.valor_mensal),
                'valor_formatado': plano.get_valor_formatado(),
                'velocidade_formatada': plano.get_velocidade_formatada(),
                'wifi_6': plano.wifi_6,
                'suporte_prioritario': plano.suporte_prioritario,
                'suporte_24h': plano.suporte_24h,
                'upload_simetrico': plano.upload_simetrico,
                'destaque': plano.destaque,
                'ordem_exibicao': plano.ordem_exibicao
            })
        
        return JsonResponse({
            'success': True,
            'planos': planos_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro ao buscar planos: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def api_vencimentos(request):
    """API para buscar opções de vencimento"""
    try:
        vencimentos = OpcaoVencimento.objects.filter(ativo=True).order_by('ordem_exibicao', 'dia_vencimento')
        
        vencimentos_data = []
        for vencimento in vencimentos:
            vencimentos_data.append({
                'id': vencimento.id,
                'dia_vencimento': vencimento.dia_vencimento,
                'descricao': vencimento.descricao,
                'ordem_exibicao': vencimento.ordem_exibicao
            })
        
        return JsonResponse({
            'success': True,
            'vencimentos': vencimentos_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro ao buscar vencimentos: {str(e)}'
        }, status=500)


def get_client_ip(request):
    """Função para obter o IP real do cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@csrf_exempt
@require_http_methods(["POST"])
def api_upload_documento(request):
    """
    API para upload de documentos durante cadastro
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
        
        # Validar campos obrigatórios
        required_fields = ['tipo_documento', 'arquivo_base64', 'nome_arquivo', 'tamanho_arquivo', 'formato_arquivo']
        for field in required_fields:
            if field not in data:
                return JsonResponse({
                    'success': False,
                    'message': f'Campo obrigatório ausente: {field}'
                }, status=400)
        
        # Validar tipo de documento
        tipos_validos = ['selfie', 'doc_frente', 'doc_verso', 'comprovante_residencia', 'contrato_assinado']
        if data['tipo_documento'] not in tipos_validos:
            return JsonResponse({
                'success': False,
                'message': 'Tipo de documento inválido'
            }, status=400)
        
        # Validar tamanho do arquivo
        max_size = 5 * 1024 * 1024  # 5MB
        if data.get('tamanho_arquivo', 0) > max_size:
            return JsonResponse({
                'success': False,
                'message': f'Arquivo muito grande. Máximo permitido: {max_size/1024/1024}MB'
            }, status=400)
        
        # Retornar sucesso (o documento será salvo quando o lead for criado)
        return JsonResponse({
            'success': True,
            'message': 'Documento validado com sucesso'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'JSON inválido'
        }, status=400)
    except Exception as e:
        logger.error(f"Erro ao processar upload de documento: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Erro ao processar documento: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_consulta_cep(request, cep):
    """
    API para consultar CEP usando múltiplas fontes para melhor resultado
    """
    try:
        import requests
        import json as json_lib
        import urllib3
        
        # Desabilitar warnings de SSL
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Limpar CEP (remover caracteres especiais)
        cep_limpo = cep.replace('-', '').replace('.', '').strip()
        
        logger.info(f"=== Iniciando consulta de CEP: {cep_limpo} ===")
        
        # Validar formato do CEP
        if not cep_limpo.isdigit() or len(cep_limpo) != 8:
            logger.warning(f"CEP inválido: {cep_limpo}")
            response = JsonResponse({
                'success': False,
                'message': 'CEP deve conter 8 dígitos'
            }, status=400)
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            return response
        
        # Verificar cache local (em produção, usar Redis ou similar)
        cache_key = f"cep_cache_{cep_limpo}"
        # Por simplicidade, vamos usar um cache em memória
        # Em produção, implementar com Redis ou banco de dados
        
        # Lista de APIs para tentar em sequência
        apis_cep = [
            {
                'name': 'ViaCEP',
                'url': f"https://viacep.com.br/ws/{cep_limpo}/json/",
                'timeout': 10,
                'headers': {'User-Agent': 'Mozilla/5.0 (compatible; CEP-Service/1.0)'},
                'parser': lambda data: {
                    'cep': cep_limpo,
                    'logradouro': data.get('logradouro', ''),
                    'complemento': data.get('complemento', ''),
                    'bairro': data.get('bairro', ''),
                    'localidade': data.get('localidade', ''),
                    'uf': data.get('uf', ''),
                    'ibge': data.get('ibge', ''),
                    'gia': data.get('gia', ''),
                    'ddd': data.get('ddd', ''),
                    'siafi': data.get('siafi', '')
                },
                'error_check': lambda data: data.get('erro')
            },
            {
                'name': 'CepAPI',
                'url': f"https://cep.awesomeapi.com.br/json/{cep_limpo}",
                'timeout': 10,
                'headers': {'User-Agent': 'Mozilla/5.0 (compatible; CEP-Service/1.0)'},
                'parser': lambda data: {
                    'cep': cep_limpo,
                    'logradouro': data.get('address', ''),
                    'complemento': '',
                    'bairro': data.get('district', ''),
                    'localidade': data.get('city', ''),
                    'uf': data.get('state', ''),
                    'ibge': data.get('city_ibge', ''),
                    'gia': '',
                    'ddd': data.get('ddd', ''),
                    'siafi': ''
                },
                'error_check': lambda data: data.get('status') == 400
            },
            {
                'name': 'BrasilAPI',
                'url': f"https://brasilapi.com.br/api/cep/v1/{cep_limpo}",
                'timeout': 10,
                'headers': {'User-Agent': 'Mozilla/5.0 (compatible; CEP-Service/1.0)'},
                'parser': lambda data: {
                    'cep': cep_limpo,
                    'logradouro': data.get('street', ''),
                    'complemento': '',
                    'bairro': data.get('neighborhood', ''),
                    'localidade': data.get('city', ''),
                    'uf': data.get('state', ''),
                    'ibge': '',
                    'gia': '',
                    'ddd': '',
                    'siafi': ''
                },
                'error_check': lambda data: 'errors' in data
            },
            {
                'name': 'Postmon',
                'url': f"https://api.postmon.com.br/v1/cep/{cep_limpo}",
                'timeout': 10,
                'headers': {'User-Agent': 'Mozilla/5.0 (compatible; CEP-Service/1.0)'},
                'parser': lambda data: {
                    'cep': cep_limpo,
                    'logradouro': data.get('logradouro', ''),
                    'complemento': '',
                    'bairro': data.get('bairro', ''),
                    'localidade': data.get('cidade', ''),
                    'uf': data.get('estado', ''),
                    'ibge': '',
                    'gia': '',
                    'ddd': '',
                    'siafi': ''
                },
                'error_check': lambda data: False  # Postmon não retorna erro específico
            },
            {
                'name': 'OpenCEP',
                'url': f"https://opencep.com/v1/{cep_limpo}",
                'timeout': 10,
                'headers': {'User-Agent': 'Mozilla/5.0 (compatible; CEP-Service/1.0)'},
                'parser': lambda data: {
                    'cep': cep_limpo,
                    'logradouro': data.get('address', ''),
                    'complemento': '',
                    'bairro': data.get('district', ''),
                    'localidade': data.get('city', ''),
                    'uf': data.get('state', ''),
                    'ibge': data.get('ibge', ''),
                    'gia': '',
                    'ddd': data.get('ddd', ''),
                    'siafi': ''
                },
                'error_check': lambda data: 'error' in data
            }
        ]
        
        # Tentar cada API em sequência
        for api in apis_cep:
            try:
                logger.info(f"📡 Tentando consultar CEP {cep_limpo} via {api['name']} - URL: {api['url']}")
                
                # Fazer requisição com timeout e headers
                response = requests.get(
                    api['url'],
                    headers=api.get('headers', {}),
                    timeout=api['timeout'],
                    verify=False  # Desabilitar verificação SSL para evitar erros
                )
                
                logger.info(f"Status HTTP {response.status_code} da API {api['name']}")
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ Resposta da API {api['name']}: {json_lib.dumps(data, ensure_ascii=False)[:200]}")
                    
                    # Verificar se houve erro na API
                    if api['error_check'](data):
                        logger.warning(f"⚠️ API {api['name']} retornou erro para CEP {cep_limpo}: {data}")
                        continue
                    
                    # Processar dados com sucesso
                    endereco_data = api['parser'](data)
                    logger.info(f"📋 Dados processados: {json_lib.dumps(endereco_data, ensure_ascii=False)}")
                    
                    # Validar se os dados essenciais estão presentes
                    if endereco_data.get('localidade') and endereco_data.get('uf'):
                        logger.info(f"🎉 CEP {cep_limpo} encontrado via {api['name']}")
                        
                        response_json = JsonResponse({
                            'success': True,
                            'data': endereco_data,
                            'fonte': api['name']
                        })
                        response_json['Access-Control-Allow-Origin'] = '*'
                        response_json['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
                        response_json['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
                        return response_json
                    else:
                        logger.warning(f"⚠️ API {api['name']} retornou dados incompletos para CEP {cep_limpo}: localidade={endereco_data.get('localidade')}, uf={endereco_data.get('uf')}")
                        continue
                else:
                    logger.warning(f"❌ API {api['name']} retornou status {response.status_code} para CEP {cep_limpo}")
                    if response.status_code == 404:
                        logger.warning(f"CEP {cep_limpo} não encontrado na {api['name']}")
                    continue
                        
            except requests.Timeout:
                logger.warning(f"⏱️ Timeout na API {api['name']} para CEP {cep_limpo}")
                continue
                
            except requests.ConnectionError as e:
                logger.warning(f"🔌 Erro de conexão na API {api['name']} para CEP {cep_limpo}: {str(e)}")
                continue
                
            except requests.RequestException as e:
                logger.warning(f"❌ Erro de requisição na API {api['name']} para CEP {cep_limpo}: {str(e)}")
                continue
                
            except Exception as e:
                logger.error(f"💥 Erro inesperado na API {api['name']} para CEP {cep_limpo}: {str(e)}")
                logger.error(traceback.format_exc())
                continue
        
        # Se nenhuma API funcionou
        logger.error(f"❌ Nenhuma das {len(apis_cep)} APIs conseguiu consultar o CEP {cep_limpo}")
        logger.error(f"APIs tentadas: {', '.join([api['name'] for api in apis_cep])}")
        response = JsonResponse({
            'success': False,
            'message': f'CEP {cep_limpo} não encontrado. Verifique se o CEP está correto ou tente novamente mais tarde.',
            'cep': cep_limpo,
            'apis_tentadas': [api['name'] for api in apis_cep]
        }, status=404)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response
            
    except ImportError as e:
        response = JsonResponse({
            'success': False,
            'message': f'Erro de importação: {str(e)}'
        }, status=500)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response
        
    except Exception as e:
        logger.error(f"Erro geral ao consultar CEP {cep}: {str(e)}")
        response = JsonResponse({
            'success': False,
            'message': f'Erro interno: {str(e)}'
        }, status=500)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response


@login_required
def api_analise_atendimentos_data(request):
    """API para dados da análise de atendimentos"""
    try:
        from django.db.models import Count, Avg, Q, F
        from datetime import datetime, timedelta
        
        # Parâmetros de filtro
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        fluxo_id = request.GET.get('fluxo_id')
        status_filter = request.GET.get('status')
        
        # Query base
        atendimentos = AtendimentoFluxo.objects.all()
        historicos = HistoricoContato.objects.all()
        
        # Aplicar filtros de data
        if data_inicio:
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                atendimentos = atendimentos.filter(data_inicio__date__gte=data_inicio_obj)
                historicos = historicos.filter(data_hora_contato__date__gte=data_inicio_obj)
            except ValueError:
                pass
        
        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
                atendimentos = atendimentos.filter(data_inicio__date__lte=data_fim_obj)
                historicos = historicos.filter(data_hora_contato__date__lte=data_fim_obj)
            except ValueError:
                pass
        
        # Aplicar filtro de fluxo
        if fluxo_id:
            try:
                atendimentos = atendimentos.filter(fluxo_id=int(fluxo_id))
            except ValueError:
                pass
        
        # Aplicar filtro de status
        if status_filter:
            atendimentos = atendimentos.filter(status=status_filter)
        
        # Métricas principais
        total_atendimentos = atendimentos.count()
        atendimentos_completados = atendimentos.filter(status='completado').count()
        atendimentos_abandonados = atendimentos.filter(status='abandonado').count()
        atendimentos_em_andamento = atendimentos.filter(status__in=['iniciado', 'em_andamento']).count()
        
        # Calcular taxas
        if total_atendimentos > 0:
            taxa_completude = round((atendimentos_completados / total_atendimentos) * 100, 1)
            taxa_abandono = round((atendimentos_abandonados / total_atendimentos) * 100, 1)
        else:
            taxa_completude = 0
            taxa_abandono = 0
        
        # Tempo médio
        tempo_medio = atendimentos.filter(
            tempo_total__isnull=False
        ).aggregate(
            tempo_medio=Avg('tempo_total')
        )['tempo_medio'] or 0
        
        # Formatação do tempo médio
        if tempo_medio > 0:
            if tempo_medio < 60:
                tempo_medio_formatado = f"{int(tempo_medio)}s"
            elif tempo_medio < 3600:
                minutos = int(tempo_medio // 60)
                segundos = int(tempo_medio % 60)
                tempo_medio_formatado = f"{minutos}m {segundos}s"
            else:
                horas = int(tempo_medio // 3600)
                minutos = int((tempo_medio % 3600) // 60)
                tempo_medio_formatado = f"{horas}h {minutos}m"
        else:
            tempo_medio_formatado = "0s"
        
        # Dados para gráficos - últimos 7 dias
        data_fim_chart = datetime.now().date()
        data_inicio_chart = data_fim_chart - timedelta(days=6)
        
        chart_data = []
        for i in range(7):
            data_chart = data_inicio_chart + timedelta(days=i)
            atendimentos_dia = atendimentos.filter(data_inicio__date=data_chart).count()
            completados_dia = atendimentos.filter(
                data_inicio__date=data_chart,
                status='completado'
            ).count()
            
            chart_data.append({
                'date': data_chart.strftime('%d/%m'),
                'atendimentos': atendimentos_dia,
                'completados': completados_dia
            })
        
        # Distribuição por status
        status_distribution = atendimentos.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Distribuição por fluxo
        fluxo_distribution = atendimentos.select_related('fluxo').values(
            'fluxo__nome'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Score médio de qualificação
        score_medio = atendimentos.filter(
            score_qualificacao__isnull=False
        ).aggregate(
            score_medio=Avg('score_qualificacao')
        )['score_medio'] or 0
        
        # Dados de histórico de contatos
        total_contatos = historicos.count()
        contatos_sucesso = historicos.filter(sucesso=True).count()
        contatos_convertidos = historicos.filter(converteu_lead=True).count()
        vendas_confirmadas = historicos.filter(converteu_venda=True).count()
        
        # Taxa de conversão de contatos
        if total_contatos > 0:
            taxa_conversao_contatos = round((contatos_convertidos / total_contatos) * 100, 1)
            taxa_vendas = round((vendas_confirmadas / total_contatos) * 100, 1)
        else:
            taxa_conversao_contatos = 0
            taxa_vendas = 0
        
        response_data = {
            'metricas_principais': {
                'total_atendimentos': total_atendimentos,
                'atendimentos_completados': atendimentos_completados,
                'atendimentos_abandonados': atendimentos_abandonados,
                'atendimentos_em_andamento': atendimentos_em_andamento,
                'taxa_completude': taxa_completude,
                'taxa_abandono': taxa_abandono,
                'tempo_medio_segundos': round(tempo_medio, 2),
                'tempo_medio_formatado': tempo_medio_formatado,
                'score_medio_qualificacao': round(score_medio, 1),
            },
            'metricas_contatos': {
                'total_contatos': total_contatos,
                'contatos_sucesso': contatos_sucesso,
                'contatos_convertidos': contatos_convertidos,
                'vendas_confirmadas': vendas_confirmadas,
                'taxa_conversao_contatos': taxa_conversao_contatos,
                'taxa_vendas': taxa_vendas,
            },
            'graficos': {
                'evolucao_7_dias': chart_data,
                'distribuicao_status': list(status_distribution),
                'distribuicao_fluxo': list(fluxo_distribution),
            }
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        import traceback
        logger.error(f"Erro na API de análise de atendimentos: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'error': f'Erro ao carregar dados de análise: {str(e)}'
        }, status=500)


@login_required
def api_analise_atendimentos_fluxos(request):
    """API para listar fluxos disponíveis para filtro"""
    try:
        fluxos = FluxoAtendimento.objects.filter(ativo=True).values(
            'id', 'nome', 'tipo_fluxo'
        ).order_by('nome')
        
        fluxos_data = []
        for fluxo in fluxos:
            total_atendimentos = AtendimentoFluxo.objects.filter(fluxo_id=fluxo['id']).count()
            fluxos_data.append({
                'id': fluxo['id'],
                'nome': fluxo['nome'],
                'tipo_fluxo': fluxo['tipo_fluxo'],
                'total_atendimentos': total_atendimentos
            })
        
        return JsonResponse({
            'fluxos': fluxos_data
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'Erro ao carregar fluxos: {str(e)}'
        }, status=500)


@login_required
def api_analise_detalhada_atendimentos(request):
    """API para dados detalhados de atendimentos com paginação"""
    try:
        from django.core.paginator import Paginator
        
        # Parâmetros
        page = int(request.GET.get('page', 1))
        per_page = min(int(request.GET.get('per_page', 20)), 100)
        
        # Filtros
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        fluxo_id = request.GET.get('fluxo_id')
        status_filter = request.GET.get('status')
        search = request.GET.get('search', '').strip()
        
        # Query base
        atendimentos = AtendimentoFluxo.objects.select_related('lead', 'fluxo').all()
        
        # Aplicar filtros
        if data_inicio:
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                atendimentos = atendimentos.filter(data_inicio__date__gte=data_inicio_obj)
            except ValueError:
                pass
        
        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
                atendimentos = atendimentos.filter(data_inicio__date__lte=data_fim_obj)
            except ValueError:
                pass
        
        if fluxo_id:
            try:
                atendimentos = atendimentos.filter(fluxo_id=int(fluxo_id))
            except ValueError:
                pass
        
        if status_filter:
            atendimentos = atendimentos.filter(status=status_filter)
        
        if search:
            atendimentos = atendimentos.filter(
                Q(lead__nome_razaosocial__icontains=search) |
                Q(lead__telefone__icontains=search) |
                Q(lead__email__icontains=search) |
                Q(fluxo__nome__icontains=search)
            )
        
        # Ordenação
        atendimentos = atendimentos.order_by('-data_inicio')
        
        # Paginação
        paginator = Paginator(atendimentos, per_page)
        page_obj = paginator.get_page(page)
        
        # Serializar dados
        atendimentos_data = []
        for atendimento in page_obj:
            atendimentos_data.append({
                'id': atendimento.id,
                'lead': {
                    'id': atendimento.lead.id,
                    'nome': atendimento.lead.nome_razaosocial,
                    'telefone': atendimento.lead.telefone,
                    'email': atendimento.lead.email or '',
                },
                'fluxo': {
                    'id': atendimento.fluxo.id,
                    'nome': atendimento.fluxo.nome,
                    'tipo': atendimento.fluxo.tipo_fluxo,
                },
                'status': atendimento.status,
                'status_display': atendimento.get_status_display(),
                'data_inicio': atendimento.data_inicio.strftime('%d/%m/%Y %H:%M'),
                'data_conclusao': atendimento.data_conclusao.strftime('%d/%m/%Y %H:%M') if atendimento.data_conclusao else None,
                'progresso_percentual': atendimento.get_progresso_percentual(),
                'questao_atual': atendimento.questao_atual,
                'total_questoes': atendimento.total_questoes,
                'tempo_total': atendimento.get_tempo_formatado(),
                'score_qualificacao': atendimento.score_qualificacao,
                'observacoes': atendimento.observacoes or ''
            })
        
        return JsonResponse({
            'atendimentos': atendimentos_data,
            'total': paginator.count,
            'page': page,
            'pages': paginator.num_pages,
            'per_page': per_page
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'Erro ao carregar atendimentos detalhados: {str(e)}'
        }, status=500)


@login_required
def api_jornada_cliente_completa(request):
    """API para obter jornada completa de um cliente (lead + histórico + atendimentos)"""
    try:
        lead_id = request.GET.get('lead_id')
        atendimento_id = request.GET.get('atendimento_id')
        
        if not lead_id and not atendimento_id:
            return JsonResponse({
                'error': 'É necessário informar lead_id ou atendimento_id'
            }, status=400)
        
        # Buscar lead
        if lead_id:
            try:
                lead = LeadProspecto.objects.get(id=lead_id)
            except LeadProspecto.DoesNotExist:
                return JsonResponse({'error': 'Lead não encontrado'}, status=404)
        else:
            try:
                atendimento = AtendimentoFluxo.objects.select_related('lead').get(id=atendimento_id)
                lead = atendimento.lead
            except AtendimentoFluxo.DoesNotExist:
                return JsonResponse({'error': 'Atendimento não encontrado'}, status=404)
        
        # Buscar todos os contatos relacionados
        historicos = HistoricoContato.objects.filter(
            models.Q(lead=lead) | models.Q(telefone=lead.telefone)
        ).order_by('data_hora_contato')
        
        # Buscar todos os atendimentos de fluxo
        atendimentos = AtendimentoFluxo.objects.filter(lead=lead).select_related(
            'fluxo', 'historico_contato'
        ).order_by('data_inicio')
        
        # Serializar dados do lead
        lead_data = {
            'id': lead.id,
            'nome': lead.nome_razaosocial,
            'email': lead.email,
            'telefone': lead.telefone,
            'empresa': lead.empresa,
            'valor': lead.get_valor_formatado(),
            'origem': lead.origem,
            'data_cadastro': lead.data_cadastro.strftime('%d/%m/%Y %H:%M'),
            'status_api': lead.status_api,
            'score_qualificacao': lead.score_qualificacao,
            'tentativas_contato': lead.tentativas_contato,
            'data_ultimo_contato': lead.data_ultimo_contato.strftime('%d/%m/%Y %H:%M') if lead.data_ultimo_contato else None,
            'observacoes': lead.observacoes,
            'ativo': lead.ativo,
        }
        
        # Serializar histórico de contatos
        historicos_data = []
        for historico in historicos:
            historicos_data.append({
                'id': historico.id,
                'telefone': historico.telefone,
                'data_hora': historico.data_hora_contato.strftime('%d/%m/%Y %H:%M:%S'),
                'status': historico.status,
                'status_display': historico.get_status_display(),
                'nome_contato': historico.nome_contato,
                'duracao_segundos': historico.duracao_segundos,
                'duracao_formatada': f"{historico.duracao_segundos//60}m {historico.duracao_segundos%60}s" if historico.duracao_segundos else None,
                'transcricao': historico.transcricao,
                'observacoes': historico.observacoes,
                'sucesso': historico.sucesso,
                'converteu_lead': historico.converteu_lead,
                'converteu_venda': historico.converteu_venda,
                'valor_venda': historico.valor_venda,
                'origem_contato': historico.origem_contato,
            })
        
        # Serializar atendimentos
        atendimentos_data = []
        for atendimento in atendimentos:
            # Buscar respostas detalhadas
            respostas = atendimento.get_respostas_formatadas()
            
            atendimentos_data.append({
                'id': atendimento.id,
                'fluxo': {
                    'id': atendimento.fluxo.id,
                    'nome': atendimento.fluxo.nome,
                    'tipo_fluxo': atendimento.fluxo.tipo_fluxo,
                    'descricao': atendimento.fluxo.descricao,
                },
                'status': atendimento.status,
                'status_display': atendimento.get_status_display(),
                'data_inicio': atendimento.data_inicio.strftime('%d/%m/%Y %H:%M:%S'),
                'data_conclusao': atendimento.data_conclusao.strftime('%d/%m/%Y %H:%M:%S') if atendimento.data_conclusao else None,
                'questao_atual': atendimento.questao_atual,
                'total_questoes': atendimento.total_questoes,
                'questoes_respondidas': atendimento.questoes_respondidas,
                'progresso_percentual': atendimento.get_progresso_percentual(),
                'tempo_total': atendimento.tempo_total,
                'tempo_formatado': atendimento.get_tempo_formatado(),
                'tentativas_atual': atendimento.tentativas_atual,
                'max_tentativas': atendimento.max_tentativas,
                'score_qualificacao': atendimento.score_qualificacao,
                'observacoes': atendimento.observacoes,
                'historico_contato_id': atendimento.historico_contato.id if atendimento.historico_contato else None,
                'respostas': respostas,
                'dados_respostas': atendimento.dados_respostas,
            })
        
        # Calcular estatísticas da jornada
        total_contatos = len(historicos_data)
        contatos_sucesso = sum(1 for h in historicos_data if h['sucesso'])
        total_atendimentos = len(atendimentos_data)
        atendimentos_completados = sum(1 for a in atendimentos_data if a['status'] == 'completado')
        
        # Timeline unificada (contatos + início de atendimentos)
        timeline = []
        
        # Adicionar contatos à timeline
        for historico in historicos_data:
            timeline.append({
                'tipo': 'contato',
                'data': historico['data_hora'],
                'timestamp': historico['data_hora'],
                'titulo': f"Contato - {historico['status_display']}",
                'descricao': f"Telefone: {historico['telefone']}",
                'detalhes': historico,
                'icone': 'phone',
                'cor': '#3498db' if historico['sucesso'] else '#e74c3c'
            })
        
        # Adicionar atendimentos à timeline
        for atendimento in atendimentos_data:
            timeline.append({
                'tipo': 'atendimento',
                'data': atendimento['data_inicio'],
                'timestamp': atendimento['data_inicio'],
                'titulo': f"Atendimento - {atendimento['fluxo']['nome']}",
                'descricao': f"Status: {atendimento['status_display']} ({atendimento['progresso_percentual']}%)",
                'detalhes': atendimento,
                'icone': 'comments',
                'cor': '#27ae60' if atendimento['status'] == 'completado' else '#f39c12'
            })
        
        # Ordenar timeline por data
        timeline.sort(key=lambda x: x['timestamp'])
        
        response_data = {
            'lead': lead_data,
            'historico_contatos': historicos_data,
            'atendimentos': atendimentos_data,
            'timeline': timeline,
            'estatisticas': {
                'total_contatos': total_contatos,
                'contatos_sucesso': contatos_sucesso,
                'taxa_sucesso_contatos': round((contatos_sucesso / total_contatos) * 100, 1) if total_contatos > 0 else 0,
                'total_atendimentos': total_atendimentos,
                'atendimentos_completados': atendimentos_completados,
                'taxa_completude_atendimentos': round((atendimentos_completados / total_atendimentos) * 100, 1) if total_atendimentos > 0 else 0,
                'primeiro_contato': historicos_data[0]['data_hora'] if historicos_data else None,
                'ultimo_contato': historicos_data[-1]['data_hora'] if historicos_data else None,
                'duracao_jornada_dias': None,  # Calcular depois se necessário
            }
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        import traceback
        logger.error(f"Erro na API de jornada do cliente: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'error': f'Erro ao carregar jornada do cliente: {str(e)}'
        }, status=500)


@login_required
def api_atendimento_em_tempo_real(request):
    """API para acompanhar atendimento em tempo real"""
    try:
        atendimento_id = request.GET.get('atendimento_id')
        
        if not atendimento_id:
            return JsonResponse({
                'error': 'atendimento_id é obrigatório'
            }, status=400)
        
        try:
            atendimento = AtendimentoFluxo.objects.select_related(
                'lead', 'fluxo', 'historico_contato'
            ).get(id=atendimento_id)
        except AtendimentoFluxo.DoesNotExist:
            return JsonResponse({'error': 'Atendimento não encontrado'}, status=404)
        
        # Questão atual detalhada
        questao_atual = atendimento.get_questao_atual_obj()
        questao_data = None
        if questao_atual:
            questao_data = {
                'id': questao_atual.id,
                'indice': questao_atual.indice,
                'titulo': questao_atual.titulo,
                'descricao': questao_atual.descricao,
                'tipo_questao': questao_atual.tipo_questao,
                'tipo_validacao': questao_atual.tipo_validacao,
                'opcoes_resposta': questao_atual.get_opcoes_formatadas(),
                'resposta_padrao': questao_atual.resposta_padrao,
                'permite_voltar': questao_atual.permite_voltar,
                'permite_editar': questao_atual.permite_editar,
            }
        
        # Próxima questão
        proxima_questao = atendimento.get_proxima_questao()
        proxima_questao_data = None
        if proxima_questao:
            proxima_questao_data = {
                'id': proxima_questao.id,
                'indice': proxima_questao.indice,
                'titulo': proxima_questao.titulo,
            }
        
        # Todas as questões do fluxo
        todas_questoes = []
        for questao in atendimento.fluxo.get_questoes_ordenadas():
            respondida = str(questao.indice) in atendimento.dados_respostas
            resposta_data = atendimento.dados_respostas.get(str(questao.indice), {})
            
            todas_questoes.append({
                'id': questao.id,
                'indice': questao.indice,
                'titulo': questao.titulo,
                'tipo_questao': questao.tipo_questao,
                'respondida': respondida,
                'resposta': resposta_data.get('resposta') if respondida else None,
                'valida': resposta_data.get('valida', False) if respondida else None,
                'data_resposta': resposta_data.get('data_resposta') if respondida else None,
            })
        
        response_data = {
            'atendimento': {
                'id': atendimento.id,
                'status': atendimento.status,
                'status_display': atendimento.get_status_display(),
                'questao_atual': atendimento.questao_atual,
                'total_questoes': atendimento.total_questoes,
                'questoes_respondidas': atendimento.questoes_respondidas,
                'progresso_percentual': atendimento.get_progresso_percentual(),
                'tempo_total': atendimento.tempo_total,
                'tempo_formatado': atendimento.get_tempo_formatado(),
                'data_inicio': atendimento.data_inicio.strftime('%d/%m/%Y %H:%M:%S'),
                'data_ultima_atividade': atendimento.data_ultima_atividade.strftime('%d/%m/%Y %H:%M:%S'),
                'tentativas_atual': atendimento.tentativas_atual,
                'max_tentativas': atendimento.max_tentativas,
            },
            'lead': {
                'id': atendimento.lead.id,
                'nome': atendimento.lead.nome_razaosocial,
                'telefone': atendimento.lead.telefone,
                'email': atendimento.lead.email,
            },
            'fluxo': {
                'id': atendimento.fluxo.id,
                'nome': atendimento.fluxo.nome,
                'tipo_fluxo': atendimento.fluxo.tipo_fluxo,
                'descricao': atendimento.fluxo.descricao,
            },
            'questao_atual': questao_data,
            'proxima_questao': proxima_questao_data,
            'todas_questoes': todas_questoes,
            'pode_avancar': atendimento.pode_avancar(),
            'pode_voltar': atendimento.pode_voltar(),
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        import traceback
        logger.error(f"Erro na API de tempo real: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'error': f'Erro ao carregar dados em tempo real: {str(e)}'
        }, status=500)


# ============================================================================
# VIEWS DE GERENCIAMENTO - CONFIGURAÇÕES
# ============================================================================

@login_required
def configuracoes_view(request):
    """View principal para configurações do sistema"""
    return render(request, 'vendas_web/configuracoes/index.html')


@login_required
def configuracoes_usuarios_view(request):
    """View para gerenciar usuários do sistema"""
    from django.contrib.auth.models import User, Group
    
    # Verificar se o usuário tem permissão para gerenciar usuários
    if not request.user.is_superuser and not request.user.groups.filter(name='adm_all').exists():
        messages.error(request, 'Você não tem permissão para acessar esta página.')
        return redirect('vendas_web:dashboard1')
    
    users = User.objects.all().order_by('-date_joined')
    groups = Group.objects.all().order_by('name')
    
    context = {
        'users': users,
        'groups': groups,
        'user': request.user
    }
    return render(request, 'vendas_web/configuracoes/usuarios.html', context)


@login_required
def configuracoes_notificacoes_view(request):
    """View para gerenciar sistema de notificações (temporariamente desativado)"""
    if not request.user.is_superuser and not request.user.groups.filter(name='adm_all').exists():
        messages.error(request, 'Você não tem permissão para acessar esta página.')
        return redirect('vendas_web:dashboard1')

    messages.info(request, 'Sistema de notificações em manutenção. Em breve será reimplementado.')
    return redirect('vendas_web:dashboard1')


@login_required
def tipo_notificacao_detalhes_view(request, tipo_id):
    """View para detalhes e configuração de um tipo específico de notificação"""
    from .models import TipoNotificacao, CanalNotificacao, PreferenciaNotificacao, Notificacao, TemplateNotificacao
    
    # Verificar se o usuário tem permissão
    if not request.user.is_superuser and not request.user.groups.filter(name='adm_all').exists():
        messages.error(request, 'Você não tem permissão para acessar esta página.')
        return redirect('vendas_web:dashboard1')
    
    # Buscar o tipo de notificação
    try:
        tipo = TipoNotificacao.objects.get(id=tipo_id)
    except TipoNotificacao.DoesNotExist:
        messages.error(request, 'Tipo de notificação não encontrado.')
        return redirect('vendas_web:configuracoes_notificacoes')
    
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
    
    # Buscar todos os usuários do sistema
    from django.contrib.auth.models import User
    todos_usuarios = User.objects.filter(is_active=True).order_by('username')
    
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
    # Por enquanto, usar um JSONField no modelo TipoNotificacao ou criar um modelo separado
    # Vamos buscar do tipo_notificacao.webhook_config (assumindo que existe)
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
        import json
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
    
    return render(request, 'vendas_web/configuracoes/tipo_notificacao_detalhes.html', context)


# API Endpoints para Gerenciamento de Preferências de Notificações
@login_required
@require_http_methods(["GET"])
def api_canais_notificacao(request):
    """API para listar canais de notificação disponíveis"""
    from .models import CanalNotificacao
    
    try:
        canais = CanalNotificacao.objects.filter(ativo=True).order_by('nome')
        canais_data = []
        
        for canal in canais:
            canais_data.append({
                'id': canal.id,
                'nome': canal.nome,
                'codigo': canal.codigo,
                'icone': canal.icone,
                'ativo': canal.ativo
            })
        
        return JsonResponse({
            'success': True,
            'canais': canais_data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def api_preferencias_criar(request):
    """API para criar nova preferência de notificação para usuário"""
    from .models import PreferenciaNotificacao, TipoNotificacao, CanalNotificacao
    from django.contrib.auth.models import User
    import json
    
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
@require_http_methods(["POST"])
def api_preferencias_pausar(request, preferencia_id):
    """API para pausar preferência de notificação"""
    from .models import PreferenciaNotificacao
    
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
    from .models import PreferenciaNotificacao
    
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
    from .models import PreferenciaNotificacao
    
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


@login_required
@require_http_methods(["GET"])
def api_preferencias_dados(request, preferencia_id):
    """API para buscar dados de uma preferência específica"""
    from .models import PreferenciaNotificacao
    
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
@require_http_methods(["PUT"])
def api_preferencias_editar(request):
    """API para editar preferência de notificação"""
    from .models import PreferenciaNotificacao, CanalNotificacao
    import json
    
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


# APIs para Configuração do WhatsApp
@login_required
@require_http_methods(["GET"])
def api_whatsapp_config(request):
    """API para buscar configuração do WhatsApp de um tipo específico"""
    from .models import TipoNotificacao
    import json
    
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
    from .models import TipoNotificacao
    import json
    
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
    import requests
    import json
    from datetime import datetime
    
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
                from .models import TipoNotificacao
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


@login_required
@require_http_methods(["POST"])
def api_canal_toggle(request, canal_id):
    """API para alternar status de um canal de notificação"""
    from .models import CanalNotificacao
    
    try:
        # Verificar se o usuário tem permissão
        if not request.user.is_superuser and not request.user.groups.filter(name='adm_all').exists():
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


@login_required
@require_http_methods(["POST"])
def api_usuarios_criar(request):
    """API para criar novo usuário"""
    from django.contrib.auth.models import User, Group
    from django.contrib.auth.hashers import make_password
    
    try:
        # Verificar permissões
        if not request.user.is_superuser and not request.user.groups.filter(name='adm_all').exists():
            return JsonResponse({'error': 'Sem permissão'}, status=403)
        
        data = json.loads(request.body)
        username = data.get('username')
        email = data.get('email')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        password = data.get('password')
        groups = data.get('groups', [])
        is_active = data.get('is_active', True)
        is_staff = data.get('is_staff', False)
        
        # Validações
        if not username or not email or not password:
            return JsonResponse({'error': 'Username, email e senha são obrigatórios'}, status=400)
        
        if User.objects.filter(username=username).exists():
            return JsonResponse({'error': 'Username já existe'}, status=400)
        
        if User.objects.filter(email=email).exists():
            return JsonResponse({'error': 'Email já existe'}, status=400)
        
        # Criar usuário
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=is_active,
            is_staff=is_staff
        )
        
        # Adicionar grupos
        for group_name in groups:
            try:
                group = Group.objects.get(name=group_name)
                user.groups.add(group)
            except Group.DoesNotExist:
                pass
        
        return JsonResponse({
            'success': True,
            'message': 'Usuário criado com sucesso',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'date_joined': user.date_joined.isoformat(),
                'groups': [g.name for g in user.groups.all()]
            }
        })
        
    except Exception as e:
        logger.error(f'Erro ao criar usuário: {str(e)}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@login_required
@require_http_methods(["PUT"])
def api_usuarios_editar(request, user_id):
    """API para editar usuário existente"""
    from django.contrib.auth.models import User, Group
    
    try:
        # Verificar permissões
        if not request.user.is_superuser and not request.user.groups.filter(name='adm_all').exists():
            return JsonResponse({'error': 'Sem permissão'}, status=403)
        
        user = User.objects.get(id=user_id)
        data = json.loads(request.body)
        
        # Atualizar campos
        if 'username' in data:
            if User.objects.filter(username=data['username']).exclude(id=user_id).exists():
                return JsonResponse({'error': 'Username já existe'}, status=400)
            user.username = data['username']
        
        if 'email' in data:
            if User.objects.filter(email=data['email']).exclude(id=user_id).exists():
                return JsonResponse({'error': 'Email já existe'}, status=400)
            user.email = data['email']
        
        if 'first_name' in data:
            user.first_name = data['first_name']
        
        if 'last_name' in data:
            user.last_name = data['last_name']
        
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        if 'is_staff' in data:
            user.is_staff = data['is_staff']
        
        if 'password' in data and data['password']:
            user.set_password(data['password'])
        
        user.save()
        
        # Atualizar grupos
        if 'groups' in data:
            user.groups.clear()
            for group_name in data['groups']:
                try:
                    group = Group.objects.get(name=group_name)
                    user.groups.add(group)
                except Group.DoesNotExist:
                    pass
        
        return JsonResponse({
            'success': True,
            'message': 'Usuário atualizado com sucesso',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'date_joined': user.date_joined.isoformat(),
                'groups': [g.name for g in user.groups.all()]
            }
        })
        
    except User.DoesNotExist:
        return JsonResponse({'error': 'Usuário não encontrado'}, status=404)
    except Exception as e:
        logger.error(f'Erro ao editar usuário: {str(e)}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@login_required
@require_http_methods(["DELETE"])
def api_usuarios_deletar(request, user_id):
    """API para deletar usuário"""
    from django.contrib.auth.models import User
    
    try:
        # Verificar permissões
        if not request.user.is_superuser and not request.user.groups.filter(name='adm_all').exists():
            return JsonResponse({'error': 'Sem permissão'}, status=403)
        
        user = User.objects.get(id=user_id)
        
        # Não permitir deletar o próprio usuário
        if user.id == request.user.id:
            return JsonResponse({'error': 'Não é possível deletar seu próprio usuário'}, status=400)
        
        # Não permitir deletar superusuários
        if user.is_superuser:
            return JsonResponse({'error': 'Não é possível deletar superusuários'}, status=400)
        
        username = user.username
        user.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Usuário {username} deletado com sucesso'
        })
        
    except User.DoesNotExist:
        return JsonResponse({'error': 'Usuário não encontrado'}, status=404)
    except Exception as e:
        logger.error(f'Erro ao deletar usuário: {str(e)}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


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
        
        # Buscar usuários
        if destinatarios_ids:
            usuarios = User.objects.filter(id__in=destinatarios_ids, is_active=True)
        else:
            # Enviar para todos os usuários ativos
            usuarios = User.objects.filter(is_active=True)
        
        return JsonResponse({
            'success': False,
            'message': 'Sistema de notificações temporariamente desativado.',
            'notificacoes_criadas': 0
        })
        
    except Exception as e:
        logger.error(f'Erro ao enviar notificação: {str(e)}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@login_required
def api_notificacoes_listar(request):
    """API para listar notificações do usuário"""
    from .models import Notificacao
    
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
                'canal': notif.canal.nome,
                'titulo': notif.titulo,
                'mensagem': notif.mensagem,
                'status': notif.status,
                'prioridade': notif.prioridade,
                'data_criacao': notif.data_criacao.isoformat(),
                'data_envio': notif.data_envio.isoformat() if notif.data_envio else None
            })
        
        return JsonResponse({
            'success': True,
            'notificacoes': data,
            'total': notificacoes.count(),
            'page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        logger.error(f'Erro ao listar notificações: {str(e)}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@login_required
def api_notificacao_detalhes(request, notificacao_id):
    """API para obter detalhes completos de uma notificação específica"""
    from .models import Notificacao
    
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
                'icone': 'fa-bell'  # TipoNotificacao não tem campo icone
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
            'dados_contexto': notificacao.dados_contexto if notificacao.dados_contexto else {},
            'erro_detalhes': notificacao.erro_detalhes,
            'n8n_execution_id': notificacao.n8n_execution_id,
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
        import traceback
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
        
        return JsonResponse({
            'success': False,
            'message': 'Sistema de notificações temporariamente desativado.'
        })
        
    except Exception as e:
        logger.error(f'Erro ao enviar notificação de teste: {str(e)}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@login_required
def api_notificacoes_estatisticas(request):
    """API para obter estatísticas do sistema de notificações"""
    try:
        return JsonResponse({
            'success': False,
            'message': 'Sistema de notificações temporariamente desativado.',
            'estatisticas': {}
        })
        
    except Exception as e:
        logger.error(f'Erro ao obter estatísticas: {str(e)}')
        import traceback
        logger.error(f'Traceback: {traceback.format_exc()}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@login_required
def configuracoes_cadastro_view(request):
    """View para gerenciar configurações de cadastro"""
    configuracoes = ConfiguracaoCadastro.objects.all()
    return render(request, 'vendas_web/configuracoes/cadastro.html', {
        'configuracoes': configuracoes
    })

@login_required
@require_http_methods(["POST"])
def salvar_configuracoes_cadastro_view(request):
    """API para salvar configurações de cadastro via AJAX"""
    try:
        import json
        data = json.loads(request.body)
        
        # Obter ou criar configuração
        config, created = ConfiguracaoCadastro.objects.get_or_create(
            empresa='Megalink',
            defaults={
                'titulo_pagina': 'Cadastro de Cliente',
                'subtitulo_pagina': 'Preencha seus dados para começar'
            }
        )
        
        # Atualizar configurações visuais
        if 'logoUrl' in data:
            config.logo_url = data.get('logoUrl', config.logo_url)
        if 'backgroundType' in data:
            config.background_type = data.get('backgroundType', config.background_type)
        if 'backgroundColor1' in data:
            config.background_color_1 = data.get('backgroundColor1', config.background_color_1)
        if 'backgroundColor2' in data:
            config.background_color_2 = data.get('backgroundColor2', config.background_color_2)
        if 'backgroundImageUrl' in data:
            config.background_image_url = data.get('backgroundImageUrl', config.background_image_url)
        if 'primaryColor' in data:
            config.primary_color = data.get('primaryColor', config.primary_color)
        if 'secondaryColor' in data:
            config.secondary_color = data.get('secondaryColor', config.secondary_color)
        if 'successColor' in data:
            config.success_color = data.get('successColor', config.success_color)
        if 'errorColor' in data:
            config.error_color = data.get('errorColor', config.error_color)
        
        # Atualizar configurações de conteúdo
        if 'mainTitle' in data:
            config.titulo_pagina = data.get('mainTitle', config.titulo_pagina)
        if 'subtitle' in data:
            config.subtitulo_pagina = data.get('subtitle', config.subtitulo_pagina)
        if 'successMessage' in data:
            config.mensagem_sucesso = data.get('successMessage', config.mensagem_sucesso)
        if 'postInstructions' in data:
            config.instrucoes_pos_cadastro = data.get('postInstructions', config.instrucoes_pos_cadastro)
        
        # Atualizar configurações de contato
        if 'supportPhone' in data:
            config.telefone_suporte = data.get('supportPhone', config.telefone_suporte)
        if 'supportWhatsapp' in data:
            config.whatsapp_suporte = data.get('supportWhatsapp', config.whatsapp_suporte)
        if 'supportEmail' in data:
            config.email_suporte = data.get('supportEmail', config.email_suporte)
        
        # Atualizar configurações de campos obrigatórios
        if 'cpfRequired' in data:
            config.cpf_obrigatorio = data.get('cpfRequired', False)
        if 'emailRequired' in data:
            config.email_obrigatorio = data.get('emailRequired', False)
        if 'phoneRequired' in data:
            config.telefone_obrigatorio = data.get('phoneRequired', False)
        if 'addressRequired' in data:
            config.endereco_obrigatorio = data.get('addressRequired', False)
        
        # Atualizar configurações de validação
        if 'validateCep' in data:
            config.validar_cep = data.get('validateCep', False)
        if 'validateCpf' in data:
            config.validar_cpf = data.get('validateCpf', False)
        if 'showProgressBar' in data:
            config.mostrar_progress_bar = data.get('showProgressBar', False)
        if 'numberOfSteps' in data:
            config.numero_etapas = data.get('numberOfSteps', 4)
        
        # Atualizar configurações avançadas
        if 'autoCreateLead' in data:
            config.criar_lead_automatico = data.get('autoCreateLead', False)
        if 'leadOrigin' in data:
            config.origem_lead_padrao = data.get('leadOrigin', 'site')
        if 'sendEmailConfirmation' in data:
            config.enviar_email_confirmacao = data.get('sendEmailConfirmation', False)
        if 'sendWhatsappConfirmation' in data:
            config.enviar_whatsapp_confirmacao = data.get('sendWhatsappConfirmation', False)
        
        config.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Configurações salvas com sucesso!',
            'created': created
        })
        
    except Exception as e:
        logger.error(f'Erro ao salvar configurações de cadastro: {str(e)}')
        return JsonResponse({
            'success': False,
            'message': f'Erro ao salvar configurações: {str(e)}'
        })

@login_required
def configuracoes_recontato_view(request):
    """View para gerenciar configurações de recontato"""
    configuracoes = ConfiguracaoRecontato.objects.all()
    return render(request, 'vendas_web/configuracoes/recontato.html', {
        'configuracoes': configuracoes
    })


@login_required
def fluxos_atendimento_view(request):
    """View para gerenciar fluxos de atendimento"""
    fluxos = FluxoAtendimento.objects.all().order_by('-data_criacao')
    return render(request, 'vendas_web/configuracoes/fluxos.html', {
        'fluxos': fluxos
    })


@login_required
def questoes_fluxo_view(request, fluxo_id=None):
    """View para gerenciar questões do fluxo"""
    fluxos = FluxoAtendimento.objects.filter(ativo=True).order_by('nome')
    questoes = []
    fluxo_selecionado = None
    
    if fluxo_id:
        try:
            fluxo_selecionado = FluxoAtendimento.objects.get(id=fluxo_id)
            questoes = QuestaoFluxo.objects.filter(fluxo=fluxo_selecionado).order_by('indice')
        except FluxoAtendimento.DoesNotExist:
            pass
    
    return render(request, 'vendas_web/configuracoes/questoes.html', {
        'fluxos': fluxos,
        'questoes': questoes,
        'fluxo_selecionado': fluxo_selecionado
    })


@login_required
def planos_internet_view(request):
    """View para gerenciar planos de internet"""
    planos = PlanoInternet.objects.all().order_by('ordem_exibicao', 'nome')
    return render(request, 'vendas_web/configuracoes/planos.html', {
        'planos': planos
    })


@login_required
def opcoes_vencimento_view(request):
    """View para gerenciar opções de vencimento"""
    opcoes = OpcaoVencimento.objects.all().order_by('ordem_exibicao', 'dia_vencimento')
    return render(request, 'vendas_web/configuracoes/vencimentos.html', {
        'opcoes': opcoes
    })


@login_required
def campanhas_trafego_view(request):
    """View para gerenciar campanhas de tráfego pago"""
    from .models import CampanhaTrafego
    campanhas = CampanhaTrafego.objects.all().order_by('-ativa', 'ordem_exibicao', 'nome')
    
    # Calcular estatísticas gerais
    from django.db.models import Count, Sum
    total_campanhas = campanhas.count()
    campanhas_ativas = campanhas.filter(ativa=True).count()
    total_deteccoes = sum(c.contador_deteccoes for c in campanhas)
    total_leads = sum(c.total_leads for c in campanhas)
    
    return render(request, 'vendas_web/configuracoes/campanhas.html', {
        'campanhas': campanhas,
        'total_campanhas': total_campanhas,
        'campanhas_ativas': campanhas_ativas,
        'total_deteccoes': total_deteccoes,
        'total_leads': total_leads,
    })


@login_required
def deteccoes_campanha_view(request):
    """View para visualizar detecções de campanhas"""
    from .models import DeteccaoCampanha, CampanhaTrafego
    
    # Filtros
    campanha_id = request.GET.get('campanha')
    aceita = request.GET.get('aceita')
    
    deteccoes = DeteccaoCampanha.objects.all().select_related('campanha', 'lead')
    
    if campanha_id:
        deteccoes = deteccoes.filter(campanha_id=campanha_id)
    if aceita is not None:
        deteccoes = deteccoes.filter(aceita=aceita == 'true')
    
    deteccoes = deteccoes.order_by('-detectado_em')[:100]  # Últimas 100
    
    campanhas = CampanhaTrafego.objects.filter(ativa=True).order_by('nome')
    
    return render(request, 'vendas_web/configuracoes/deteccoes.html', {
        'deteccoes': deteccoes,
        'campanhas': campanhas,
    })


# ============================================================================
# APIS DE GERENCIAMENTO - CONFIGURAÇÕES
# ============================================================================

@login_required
@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def api_configuracoes_cadastro(request):
    """API para gerenciar configurações de cadastro"""
    try:
        if request.method == 'GET':
            configuracoes = ConfiguracaoCadastro.objects.all()
            data = []
            for config in configuracoes:
                data.append({
                    'id': config.id,
                    'empresa': config.empresa,
                    'titulo_pagina': config.titulo_pagina,
                    'subtitulo_pagina': config.subtitulo_pagina,
                    'ativo': config.ativo,
                    'mostrar_selecao_plano': config.mostrar_selecao_plano,
                    'criar_lead_automatico': config.criar_lead_automatico,
                    'data_atualizacao': config.data_atualizacao.strftime('%d/%m/%Y %H:%M:%S')
                })
            return JsonResponse({'success': True, 'data': data})
        
        elif request.method == 'POST':
            data = json.loads(request.body)
            config = ConfiguracaoCadastro.objects.create(
                empresa=data.get('empresa'),
                titulo_pagina=data.get('titulo_pagina'),
                subtitulo_pagina=data.get('subtitulo_pagina', ''),
                ativo=data.get('ativo', True),
                mostrar_selecao_plano=data.get('mostrar_selecao_plano', True),
                criar_lead_automatico=data.get('criar_lead_automatico', True)
            )
            return JsonResponse({
                'success': True, 
                'message': 'Configuração criada com sucesso!',
                'id': config.id
            })
        
        elif request.method == 'PUT':
            data = json.loads(request.body)
            config_id = data.get('id')
            config = ConfiguracaoCadastro.objects.get(id=config_id)
            
            config.empresa = data.get('empresa', config.empresa)
            config.titulo_pagina = data.get('titulo_pagina', config.titulo_pagina)
            config.subtitulo_pagina = data.get('subtitulo_pagina', config.subtitulo_pagina)
            config.ativo = data.get('ativo', config.ativo)
            config.mostrar_selecao_plano = data.get('mostrar_selecao_plano', config.mostrar_selecao_plano)
            config.criar_lead_automatico = data.get('criar_lead_automatico', config.criar_lead_automatico)
            config.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Configuração atualizada com sucesso!'
            })
        
        elif request.method == 'DELETE':
            data = json.loads(request.body)
            config_id = data.get('id')
            config = ConfiguracaoCadastro.objects.get(id=config_id)
            config.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Configuração excluída com sucesso!'
            })
    
    except Exception as e:
        logger.error(f"Erro na API de configurações de cadastro: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def api_planos_internet_gerencia(request):
    """API para gerenciar planos de internet"""
    try:
        if request.method == 'GET':
            planos = PlanoInternet.objects.all().order_by('ordem_exibicao', 'nome')
            data = []
            for plano in planos:
                data.append({
                    'id': plano.id,
                    'nome': plano.nome,
                    'descricao': plano.descricao,
                    'velocidade_download': plano.velocidade_download,
                    'velocidade_upload': plano.velocidade_upload,
                    'valor_mensal': float(plano.valor_mensal),
                    'destaque': plano.destaque,
                    'ativo': plano.ativo,
                    'ordem_exibicao': plano.ordem_exibicao,
                    'wifi_6': plano.wifi_6,
                    'suporte_prioritario': plano.suporte_prioritario,
                    'suporte_24h': plano.suporte_24h,
                    'upload_simetrico': plano.upload_simetrico
                })
            return JsonResponse({'success': True, 'data': data})
        
        elif request.method == 'POST':
            data = json.loads(request.body)
            plano = PlanoInternet.objects.create(
                nome=data.get('nome'),
                descricao=data.get('descricao', ''),
                velocidade_download=data.get('velocidade_download'),
                velocidade_upload=data.get('velocidade_upload'),
                valor_mensal=data.get('valor_mensal'),
                destaque=data.get('destaque', False),
                ativo=data.get('ativo', True),
                ordem_exibicao=data.get('ordem_exibicao', 0),
                wifi_6=data.get('wifi_6', False),
                suporte_prioritario=data.get('suporte_prioritario', False),
                suporte_24h=data.get('suporte_24h', False),
                upload_simetrico=data.get('upload_simetrico', False)
            )
            return JsonResponse({
                'success': True,
                'message': 'Plano criado com sucesso!',
                'id': plano.id
            })
        
        elif request.method == 'PUT':
            data = json.loads(request.body)
            plano_id = data.get('id')
            plano = PlanoInternet.objects.get(id=plano_id)
            
            plano.nome = data.get('nome', plano.nome)
            plano.descricao = data.get('descricao', plano.descricao)
            plano.velocidade_download = data.get('velocidade_download', plano.velocidade_download)
            plano.velocidade_upload = data.get('velocidade_upload', plano.velocidade_upload)
            plano.valor_mensal = data.get('valor_mensal', plano.valor_mensal)
            plano.destaque = data.get('destaque', plano.destaque)
            plano.ativo = data.get('ativo', plano.ativo)
            plano.ordem_exibicao = data.get('ordem_exibicao', plano.ordem_exibicao)
            plano.wifi_6 = data.get('wifi_6', plano.wifi_6)
            plano.suporte_prioritario = data.get('suporte_prioritario', plano.suporte_prioritario)
            plano.suporte_24h = data.get('suporte_24h', plano.suporte_24h)
            plano.upload_simetrico = data.get('upload_simetrico', plano.upload_simetrico)
            plano.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Plano atualizado com sucesso!'
            })
        
        elif request.method == 'DELETE':
            data = json.loads(request.body)
            plano_id = data.get('id')
            plano = PlanoInternet.objects.get(id=plano_id)
            plano.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Plano excluído com sucesso!'
            })
    
    except Exception as e:
        logger.error(f"Erro na API de planos de internet: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def api_opcoes_vencimento_gerencia(request):
    """API para gerenciar opções de vencimento"""
    try:
        if request.method == 'GET':
            opcoes = OpcaoVencimento.objects.all().order_by('ordem_exibicao', 'dia_vencimento')
            data = []
            for opcao in opcoes:
                data.append({
                    'id': opcao.id,
                    'dia_vencimento': opcao.dia_vencimento,
                    'descricao': opcao.descricao,
                    'ordem_exibicao': opcao.ordem_exibicao,
                    'ativo': opcao.ativo
                })
            return JsonResponse({'success': True, 'data': data})
        
        elif request.method == 'POST':
            data = json.loads(request.body)
            opcao = OpcaoVencimento.objects.create(
                dia_vencimento=data.get('dia_vencimento'),
                descricao=data.get('descricao', ''),
                ordem_exibicao=data.get('ordem_exibicao', 0),
                ativo=data.get('ativo', True)
            )
            return JsonResponse({
                'success': True,
                'message': 'Opção de vencimento criada com sucesso!',
                'id': opcao.id
            })
        
        elif request.method == 'PUT':
            data = json.loads(request.body)
            opcao_id = data.get('id')
            opcao = OpcaoVencimento.objects.get(id=opcao_id)
            
            opcao.dia_vencimento = data.get('dia_vencimento', opcao.dia_vencimento)
            opcao.descricao = data.get('descricao', opcao.descricao)
            opcao.ordem_exibicao = data.get('ordem_exibicao', opcao.ordem_exibicao)
            opcao.ativo = data.get('ativo', opcao.ativo)
            opcao.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Opção de vencimento atualizada com sucesso!'
            })
        
        elif request.method == 'DELETE':
            data = json.loads(request.body)
            opcao_id = data.get('id')
            opcao = OpcaoVencimento.objects.get(id=opcao_id)
            opcao.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Opção de vencimento excluída com sucesso!'
            })
    
    except Exception as e:
        logger.error(f"Erro na API de opções de vencimento: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================================
# APIS - CAMPANHAS DE TRÁFEGO
# ============================================================================

@login_required
@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def api_campanhas_trafego_gerencia(request):
    """API para gerenciar campanhas de tráfego pago"""
    from .models import CampanhaTrafego
    
    try:
        if request.method == 'GET':
            campanhas = CampanhaTrafego.objects.all().order_by('-ativa', 'ordem_exibicao', 'nome')
            data = []
            for campanha in campanhas:
                data.append({
                    'id': campanha.id,
                    'nome': campanha.nome,
                    'codigo': campanha.codigo,
                    'descricao': campanha.descricao,
                    'palavra_chave': campanha.palavra_chave,
                    'tipo_match': campanha.tipo_match,
                    'case_sensitive': campanha.case_sensitive,
                    'plataforma': campanha.plataforma,
                    'tipo_trafego': campanha.tipo_trafego,
                    'prioridade': campanha.prioridade,
                    'ativa': campanha.ativa,
                    'data_inicio': campanha.data_inicio.strftime('%Y-%m-%d') if campanha.data_inicio else None,
                    'data_fim': campanha.data_fim.strftime('%Y-%m-%d') if campanha.data_fim else None,
                    'url_destino': campanha.url_destino,
                    'orcamento': float(campanha.orcamento) if campanha.orcamento else None,
                    'meta_leads': campanha.meta_leads,
                    'contador_deteccoes': campanha.contador_deteccoes,
                    'total_leads': campanha.total_leads,
                    'cor_identificacao': campanha.cor_identificacao,
                    'ordem_exibicao': campanha.ordem_exibicao,
                })
            return JsonResponse({'success': True, 'data': data})
        
        elif request.method == 'POST':
            data = json.loads(request.body)
            campanha = CampanhaTrafego.objects.create(
                nome=data.get('nome'),
                codigo=data.get('codigo'),
                descricao=data.get('descricao', ''),
                palavra_chave=data.get('palavra_chave'),
                tipo_match=data.get('tipo_match', 'parcial'),
                case_sensitive=data.get('case_sensitive', False),
                plataforma=data.get('plataforma'),
                tipo_trafego=data.get('tipo_trafego', ''),
                prioridade=data.get('prioridade', 5),
                ativa=data.get('ativa', True),
                data_inicio=data.get('data_inicio'),
                data_fim=data.get('data_fim'),
                url_destino=data.get('url_destino', ''),
                orcamento=data.get('orcamento'),
                meta_leads=data.get('meta_leads'),
                cor_identificacao=data.get('cor_identificacao', '#667eea'),
                ordem_exibicao=data.get('ordem_exibicao', 0),
                observacoes=data.get('observacoes', ''),
                criado_por=request.user
            )
            return JsonResponse({
                'success': True,
                'message': 'Campanha criada com sucesso!',
                'id': campanha.id
            })
        
        elif request.method == 'PUT':
            data = json.loads(request.body)
            campanha_id = data.get('id')
            campanha = CampanhaTrafego.objects.get(id=campanha_id)
            
            campanha.nome = data.get('nome', campanha.nome)
            campanha.descricao = data.get('descricao', campanha.descricao)
            campanha.palavra_chave = data.get('palavra_chave', campanha.palavra_chave)
            campanha.tipo_match = data.get('tipo_match', campanha.tipo_match)
            campanha.case_sensitive = data.get('case_sensitive', campanha.case_sensitive)
            campanha.plataforma = data.get('plataforma', campanha.plataforma)
            campanha.tipo_trafego = data.get('tipo_trafego', campanha.tipo_trafego)
            campanha.prioridade = data.get('prioridade', campanha.prioridade)
            campanha.ativa = data.get('ativa', campanha.ativa)
            campanha.data_inicio = data.get('data_inicio', campanha.data_inicio)
            campanha.data_fim = data.get('data_fim', campanha.data_fim)
            campanha.url_destino = data.get('url_destino', campanha.url_destino)
            campanha.orcamento = data.get('orcamento', campanha.orcamento)
            campanha.meta_leads = data.get('meta_leads', campanha.meta_leads)
            campanha.cor_identificacao = data.get('cor_identificacao', campanha.cor_identificacao)
            campanha.ordem_exibicao = data.get('ordem_exibicao', campanha.ordem_exibicao)
            campanha.observacoes = data.get('observacoes', campanha.observacoes)
            campanha.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Campanha atualizada com sucesso!'
            })
        
        elif request.method == 'DELETE':
            data = json.loads(request.body)
            campanha_id = data.get('id')
            campanha = CampanhaTrafego.objects.get(id=campanha_id)
            campanha.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Campanha excluída com sucesso!'
            })
    
    except Exception as e:
        logger.error(f"Erro na API de campanhas: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@api_token_required
@require_http_methods(["POST"])
def api_detectar_campanha(request):
    """
    API para N8N detectar campanha em mensagem de cliente
    
    POST /api/campanhas/detectar/
    {
        "telefone": "5589999999999",
        "mensagem": "Oi, vi o cupom50 no Instagram",
        "origem": "whatsapp",
        "timestamp": "2024-11-20 10:30:00"
    }
    
    Response:
    {
        "success": true,
        "campanha_detectada": {
            "id": 5,
            "codigo": "CUPOM50",
            "nome": "Promoção Cupom 50% OFF",
            "plataforma": "instagram_ads"
        },
        "lead_id": 123,
        "score": 95.5,
        "lead_criado": false
    }
    """
    from .models import CampanhaTrafego, DeteccaoCampanha, LeadProspecto
    import re
    import unicodedata
    
    try:
        data = json.loads(request.body)
        telefone = data.get('telefone')
        mensagem = data.get('mensagem')
        origem = data.get('origem', 'whatsapp')
        timestamp_mensagem = data.get('timestamp')
        
        if not telefone or not mensagem:
            return JsonResponse({
                'success': False,
                'error': 'Telefone e mensagem são obrigatórios'
            }, status=400)
        
        # Normalizar mensagem
        mensagem_normalizada = unicodedata.normalize('NFKD', mensagem.lower())
        mensagem_normalizada = mensagem_normalizada.encode('ASCII', 'ignore').decode('ASCII')
        
        # Buscar campanhas ativas
        campanhas_ativas = CampanhaTrafego.objects.filter(ativa=True)
        
        melhor_match = None
        melhor_score = 0
        melhor_campanha = None
        melhor_trecho = None
        melhor_posicao = None
        
        for campanha in campanhas_ativas:
            # Verificar se está no período
            if not campanha.esta_ativa:
                continue
            
            palavra = campanha.palavra_chave
            if not campanha.case_sensitive:
                palavra = palavra.lower()
            
            # Aplicar detecção baseada no tipo
            if campanha.tipo_match == 'exato':
                # Match exato
                if campanha.case_sensitive:
                    encontrado = palavra in mensagem
                else:
                    encontrado = palavra in mensagem_normalizada
                
                if encontrado:
                    pos = mensagem_normalizada.find(palavra)
                    score = 100.0  # Match exato = 100%
                    if score > melhor_score or (score == melhor_score and campanha.prioridade > melhor_campanha.prioridade):
                        melhor_score = score
                        melhor_campanha = campanha
                        melhor_trecho = palavra
                        melhor_posicao = (pos, pos + len(palavra))
                        melhor_match = 'exato'
            
            elif campanha.tipo_match == 'parcial':
                # Match parcial
                if campanha.case_sensitive:
                    encontrado = palavra in mensagem
                else:
                    encontrado = palavra in mensagem_normalizada
                
                if encontrado:
                    pos = mensagem_normalizada.find(palavra)
                    # Score baseado no tamanho relativo da palavra
                    score = min(95.0, (len(palavra) / len(mensagem)) * 100 + 50)
                    if score > melhor_score or (score == melhor_score and campanha.prioridade > melhor_campanha.prioridade):
                        melhor_score = score
                        melhor_campanha = campanha
                        melhor_trecho = palavra
                        melhor_posicao = (pos, pos + len(palavra))
                        melhor_match = 'parcial'
            
            elif campanha.tipo_match == 'regex':
                # Match por regex
                try:
                    padrao = re.compile(palavra, re.IGNORECASE if not campanha.case_sensitive else 0)
                    match = padrao.search(mensagem_normalizada if not campanha.case_sensitive else mensagem)
                    
                    if match:
                        score = 90.0  # Regex = 90%
                        if score > melhor_score or (score == melhor_score and campanha.prioridade > melhor_campanha.prioridade):
                            melhor_score = score
                            melhor_campanha = campanha
                            melhor_trecho = match.group()
                            melhor_posicao = (match.start(), match.end())
                            melhor_match = 'regex'
                except:
                    continue
        
        # Se não encontrou nenhuma campanha
        if not melhor_campanha:
            return JsonResponse({
                'success': True,
                'campanha_detectada': None,
                'mensagem': 'Nenhuma campanha detectada'
            })
        
        # Buscar ou criar lead
        lead = None
        lead_criado = False
        try:
            lead = LeadProspecto.objects.get(telefone=telefone)
        except LeadProspecto.DoesNotExist:
            # Criar lead básico
            lead = LeadProspecto.objects.create(
                telefone=telefone,
                nome_razaosocial=f"Lead {telefone}",
                origem='whatsapp',
                campanha_origem=melhor_campanha
            )
            lead_criado = True
        
        # Se é primeiro contato do lead com campanha
        if lead and not lead.campanha_origem:
            lead.campanha_origem = melhor_campanha
            lead.total_campanhas_detectadas = 1
            lead.save()
        elif lead and lead.campanha_origem != melhor_campanha:
            lead.total_campanhas_detectadas += 1
            lead.save()
        
        # Registrar detecção
        deteccao = DeteccaoCampanha.objects.create(
            lead=lead,
            campanha=melhor_campanha,
            telefone=telefone,
            mensagem_original=mensagem,
            mensagem_normalizada=mensagem_normalizada,
            trecho_detectado=melhor_trecho,
            posicao_inicio=melhor_posicao[0] if melhor_posicao else None,
            posicao_fim=melhor_posicao[1] if melhor_posicao else None,
            metodo_deteccao=melhor_match,
            score_confianca=Decimal(str(melhor_score)),
            eh_primeira_mensagem=lead_criado,
            origem=origem,
            timestamp_mensagem=timestamp_mensagem,
            processado_n8n=True,
            data_processamento_n8n=timezone.now()
        )
        
        return JsonResponse({
            'success': True,
            'campanha_detectada': {
                'id': melhor_campanha.id,
                'codigo': melhor_campanha.codigo,
                'nome': melhor_campanha.nome,
                'plataforma': melhor_campanha.plataforma,
                'cor': melhor_campanha.cor_identificacao,
            },
            'deteccao': {
                'id': deteccao.id,
                'trecho_detectado': melhor_trecho,
                'score_confianca': float(melhor_score),
                'metodo': melhor_match,
            },
            'lead_id': lead.id if lead else None,
            'lead_criado': lead_criado
        })
    
    except Exception as e:
        logger.error(f"Erro ao detectar campanha: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def api_questoes_fluxo_gerencia(request):
    """API para gerenciar questões dos fluxos"""
    try:
        if request.method == 'GET':
            fluxo_id = request.GET.get('fluxo_id')
            if fluxo_id:
                questoes = QuestaoFluxo.objects.filter(fluxo_id=fluxo_id).order_by('indice')
            else:
                questoes = QuestaoFluxo.objects.all().order_by('fluxo__nome', 'indice')
            
            data = []
            for questao in questoes:
                data.append({
                    'id': questao.id,
                    'fluxo_id': questao.fluxo.id,
                    'fluxo_nome': questao.fluxo.nome,
                    'indice': questao.indice,
                    'titulo': questao.titulo,
                    'descricao': questao.descricao,
                    'tipo_questao': questao.tipo_questao,
                    'tipo_questao_display': questao.get_tipo_questao_display(),
                    'tipo_validacao': questao.tipo_validacao,
                    'tipo_validacao_display': questao.get_tipo_validacao_display(),
                    'opcoes_resposta': questao.opcoes_resposta,
                    'resposta_padrao': questao.resposta_padrao,
                    'regex_validacao': questao.regex_validacao,
                    'tamanho_minimo': questao.tamanho_minimo,
                    'tamanho_maximo': questao.tamanho_maximo,
                    'valor_minimo': questao.valor_minimo,
                    'valor_maximo': questao.valor_maximo,
                    'max_tentativas': questao.max_tentativas,
                    'estrategia_erro': questao.estrategia_erro,
                    'estrategia_erro_display': questao.get_estrategia_erro_display() if questao.estrategia_erro else None,
                    'mensagem_erro_padrao': questao.mensagem_erro_padrao,
                    'mensagem_tentativa_esgotada': questao.mensagem_tentativa_esgotada,
                    'instrucoes_resposta_correta': questao.instrucoes_resposta_correta,
                    'opcoes_dinamicas_fonte': questao.opcoes_dinamicas_fonte,
                    'opcoes_dinamicas_fonte_display': questao.get_opcoes_dinamicas_fonte_display() if questao.opcoes_dinamicas_fonte else None,
                    'permite_voltar': questao.permite_voltar,
                    'permite_editar': questao.permite_editar,
                    'ordem_exibicao': questao.ordem_exibicao,
                    'ativo': questao.ativo
                })
            return JsonResponse({'success': True, 'data': data})
        
        elif request.method == 'POST':
            data = json.loads(request.body)
            
            # Validar se o fluxo existe
            try:
                fluxo = FluxoAtendimento.objects.get(id=data.get('fluxo_id'))
            except FluxoAtendimento.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Fluxo não encontrado'
                }, status=404)
            
            # Calcular próximo índice se não fornecido
            indice = data.get('indice')
            if not indice:
                ultimo_indice = QuestaoFluxo.objects.filter(fluxo=fluxo).aggregate(
                    models.Max('indice')
                )['indice__max'] or 0
                indice = ultimo_indice + 1
            
            questao = QuestaoFluxo.objects.create(
                fluxo=fluxo,
                indice=indice,
                titulo=data.get('titulo'),
                descricao=data.get('descricao', ''),
                tipo_questao=data.get('tipo_questao'),
                tipo_validacao=data.get('tipo_validacao', 'obrigatoria'),
                opcoes_resposta=data.get('opcoes_resposta', []),
                resposta_padrao=data.get('resposta_padrao', ''),
                regex_validacao=data.get('regex_validacao', ''),
                tamanho_minimo=data.get('tamanho_minimo'),
                tamanho_maximo=data.get('tamanho_maximo'),
                valor_minimo=data.get('valor_minimo'),
                valor_maximo=data.get('valor_maximo'),
                max_tentativas=data.get('max_tentativas'),
                estrategia_erro=data.get('estrategia_erro', 'repetir'),
                mensagem_erro_padrao=data.get('mensagem_erro_padrao', ''),
                mensagem_tentativa_esgotada=data.get('mensagem_tentativa_esgotada', ''),
                instrucoes_resposta_correta=data.get('instrucoes_resposta_correta', ''),
                opcoes_dinamicas_fonte=data.get('opcoes_dinamicas_fonte'),
                permite_voltar=data.get('permite_voltar', True),
                permite_editar=data.get('permite_editar', True),
                ordem_exibicao=data.get('ordem_exibicao', indice),
                ativo=data.get('ativo', True)
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Questão criada com sucesso!',
                'id': questao.id
            })
        
        elif request.method == 'PUT':
            data = json.loads(request.body)
            questao_id = data.get('id')
            
            try:
                questao = QuestaoFluxo.objects.get(id=questao_id)
            except QuestaoFluxo.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Questão não encontrada'
                }, status=404)
            
            # Atualizar campos
            questao.titulo = data.get('titulo', questao.titulo)
            questao.descricao = data.get('descricao', questao.descricao)
            questao.tipo_questao = data.get('tipo_questao', questao.tipo_questao)
            questao.tipo_validacao = data.get('tipo_validacao', questao.tipo_validacao)
            questao.opcoes_resposta = data.get('opcoes_resposta', questao.opcoes_resposta)
            questao.resposta_padrao = data.get('resposta_padrao', questao.resposta_padrao)
            questao.regex_validacao = data.get('regex_validacao', questao.regex_validacao)
            questao.tamanho_minimo = data.get('tamanho_minimo', questao.tamanho_minimo)
            questao.tamanho_maximo = data.get('tamanho_maximo', questao.tamanho_maximo)
            questao.valor_minimo = data.get('valor_minimo', questao.valor_minimo)
            questao.valor_maximo = data.get('valor_maximo', questao.valor_maximo)
            questao.max_tentativas = data.get('max_tentativas', questao.max_tentativas)
            questao.estrategia_erro = data.get('estrategia_erro', questao.estrategia_erro)
            questao.mensagem_erro_padrao = data.get('mensagem_erro_padrao', questao.mensagem_erro_padrao)
            questao.mensagem_tentativa_esgotada = data.get('mensagem_tentativa_esgotada', questao.mensagem_tentativa_esgotada)
            questao.instrucoes_resposta_correta = data.get('instrucoes_resposta_correta', questao.instrucoes_resposta_correta)
            questao.opcoes_dinamicas_fonte = data.get('opcoes_dinamicas_fonte', questao.opcoes_dinamicas_fonte)
            questao.permite_voltar = data.get('permite_voltar', questao.permite_voltar)
            questao.permite_editar = data.get('permite_editar', questao.permite_editar)
            questao.ordem_exibicao = data.get('ordem_exibicao', questao.ordem_exibicao)
            questao.ativo = data.get('ativo', questao.ativo)
            
            # Atualizar índice se fornecido
            novo_indice = data.get('indice')
            if novo_indice and novo_indice != questao.indice:
                questao.indice = novo_indice
            
            questao.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Questão atualizada com sucesso!'
            })
        
        elif request.method == 'DELETE':
            data = json.loads(request.body)
            questao_id = data.get('id')
            
            try:
                questao = QuestaoFluxo.objects.get(id=questao_id)
                questao.delete()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Questão excluída com sucesso!'
                })
            except QuestaoFluxo.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Questão não encontrada'
                }, status=404)
    
    except Exception as e:
        logger.error(f"Erro na API de questões dos fluxos: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def api_duplicar_questao_fluxo(request):
    """API para duplicar uma questão do fluxo"""
    try:
        data = json.loads(request.body)
        questao_id = data.get('id')
        
        try:
            questao_original = QuestaoFluxo.objects.get(id=questao_id)
        except QuestaoFluxo.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Questão não encontrada'
            }, status=404)
        
        # Calcular próximo índice
        ultimo_indice = QuestaoFluxo.objects.filter(fluxo=questao_original.fluxo).aggregate(
            models.Max('indice')
        )['indice__max'] or 0
        novo_indice = ultimo_indice + 1
        
        # Criar cópia da questão
        questao_duplicada = QuestaoFluxo.objects.create(
            fluxo=questao_original.fluxo,
            indice=novo_indice,
            titulo=f"{questao_original.titulo} (Cópia)",
            descricao=questao_original.descricao,
            tipo_questao=questao_original.tipo_questao,
            tipo_validacao=questao_original.tipo_validacao,
            opcoes_resposta=questao_original.opcoes_resposta,
            resposta_padrao=questao_original.resposta_padrao,
            regex_validacao=questao_original.regex_validacao,
            tamanho_minimo=questao_original.tamanho_minimo,
            tamanho_maximo=questao_original.tamanho_maximo,
            valor_minimo=questao_original.valor_minimo,
            valor_maximo=questao_original.valor_maximo,
            max_tentativas=questao_original.max_tentativas,
            estrategia_erro=questao_original.estrategia_erro,
            mensagem_erro_padrao=questao_original.mensagem_erro_padrao,
            mensagem_tentativa_esgotada=questao_original.mensagem_tentativa_esgotada,
            instrucoes_resposta_correta=questao_original.instrucoes_resposta_correta,
            opcoes_dinamicas_fonte=questao_original.opcoes_dinamicas_fonte,
            permite_voltar=questao_original.permite_voltar,
            permite_editar=questao_original.permite_editar,
            ordem_exibicao=novo_indice,
            ativo=questao_original.ativo
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Questão duplicada com sucesso!',
            'id': questao_duplicada.id
        })
    
    except Exception as e:
        logger.error(f"Erro ao duplicar questão: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)








@login_required
@require_http_methods(["GET", "POST", "PUT", "PATCH", "DELETE"])
def api_templates_notificacoes(request, template_id=None):
    """API para gerenciar templates de notificação"""
    from .models import TemplateNotificacao
    
    try:
        # Verificar permissões
        if not request.user.is_superuser and not request.user.groups.filter(name='adm_all').exists():
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
    from .models import TipoNotificacao
    
    try:
        # Verificar permissões
        if not request.user.is_superuser and not request.user.groups.filter(name='adm_all').exists():
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
    from .models import CanalNotificacao
    
    try:
        # Verificar permissões
        if not request.user.is_superuser and not request.user.groups.filter(name='adm_all').exists():
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
# VIEWS PARA GERENCIAR TELEFONE DO USUÁRIO
# ============================================================================

@login_required
@require_http_methods(["POST"])
def atualizar_telefone_view(request):
    """API para atualizar telefone do usuário via AJAX"""
    try:
        telefone = request.POST.get('telefone', '').strip()
        
        # Atualizar telefone diretamente no modelo User
        request.user.telefone = telefone if telefone else None
        request.user.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Telefone atualizado com sucesso!',
            'telefone': telefone
        })
        
    except Exception as e:
        logger.error(f'Erro ao atualizar telefone: {str(e)}')
        return JsonResponse({
            'success': False,
            'message': 'Erro ao atualizar telefone. Tente novamente.'
        })


@login_required
def perfil_usuario_view(request):
    """View para exibir e editar perfil do usuário"""
    try:
        if request.method == 'POST':
            telefone = request.POST.get('telefone', '').strip()
            request.user.telefone = telefone if telefone else None
            request.user.save()
            messages.success(request, 'Telefone atualizado com sucesso!')
            return redirect('vendas_web:perfil_usuario')
        
        context = {
            'page_title': 'Meu Perfil',
            'user': request.user
        }
        
        return render(request, 'vendas_web/perfil_usuario.html', context)
        
    except Exception as e:
        logger.error(f'Erro na view de perfil: {str(e)}')
        messages.error(request, 'Erro ao carregar perfil. Tente novamente.')
        return redirect('vendas_web:dashboard1')


# ============================================================================
# API DE VIABILIDADE TÉCNICA
# ============================================================================

@login_required
def api_viabilidade(request):
    """
    GET /api/viabilidade/
    Consulta regiões com viabilidade técnica.

    Parâmetros opcionais (query string):
        cidade  — filtra pelo nome da cidade (parcial, sem distinção de maiúsculas)
        cep     — filtra pelo CEP (exato ou por cidade correspondente)
        uf      — filtra pelo estado (sigla, ex: PI)

    Comportamento do campo `cep`:
      1. Busca registros onde o CEP informado está cadastrado diretamente.
      2. Normaliza o CEP (somente dígitos) e consulta a API pública ViaCEP
         para obter cidade/estado, então verifica se essa cidade já consta
         na lista de viabilidade (mesmo sem CEP específico cadastrado).
      3. Retorna campo `viavel_pela_cidade` indicando quando a cobertura
         é válida via cidade (e não por CEP cadastrado diretamente).

    Sem nenhum parâmetro → retorna todas as cidades/CEPs com viabilidade.
    """
    import unicodedata
    import requests as req_ext

    def normalizar(texto):
        if not texto:
            return ''
        nfkd = unicodedata.normalize('NFKD', texto.lower())
        return nfkd.encode('ASCII', 'ignore').decode('ASCII').strip()

    cidade_param = request.GET.get('cidade', '').strip()
    cep_param    = request.GET.get('cep', '').replace('-', '').strip()
    uf_param     = request.GET.get('uf', '').upper().strip()

    qs = CidadeViabilidade.objects.filter(ativo=True)

    if uf_param:
        qs = qs.filter(estado=uf_param)

    if cidade_param:
        qs = qs.filter(cidade__icontains=cidade_param)

    # ── Modo busca por CEP ────────────────────────────────────────────────
    if cep_param:
        if len(cep_param) != 8 or not cep_param.isdigit():
            return JsonResponse(
                {'sucesso': False, 'erro': 'CEP inválido. Informe 8 dígitos numéricos.'},
                status=400,
            )

        cep_formatado = f"{cep_param[:5]}-{cep_param[5:]}"

        # 1. Busca direta pelo CEP cadastrado
        qs_cep_direto = CidadeViabilidade.objects.filter(
            ativo=True,
            cep=cep_formatado,
        )
        if uf_param:
            qs_cep_direto = qs_cep_direto.filter(estado=uf_param)

        resultados_diretos = list(qs_cep_direto)

        # 2. Consulta ViaCEP para obter cidade/UF do CEP informado
        cidade_via_cep = None
        uf_via_cep     = None
        erro_viacep    = None
        try:
            resp = req_ext.get(
                f'https://viacep.com.br/ws/{cep_param}/json/',
                timeout=5,
            )
            dados_cep = resp.json()
            if not dados_cep.get('erro'):
                cidade_via_cep = dados_cep.get('localidade', '')
                uf_via_cep     = dados_cep.get('uf', '')
        except Exception as exc:
            erro_viacep = str(exc)

        # 3. Busca por cidade retornada pelo ViaCEP
        resultados_por_cidade = []
        if cidade_via_cep and uf_via_cep:
            qs_cidade = CidadeViabilidade.objects.filter(
                ativo=True,
                cidade__iexact=cidade_via_cep,
                estado=uf_via_cep,
            )
            # Exclui os que já apareceram na busca direta
            ids_diretos = {r.pk for r in resultados_diretos}
            resultados_por_cidade = [r for r in qs_cidade if r.pk not in ids_diretos]

        def serializar(obj, viavel_pela_cidade=False):
            return {
                'id':                  obj.pk,
                'cidade':              obj.cidade,
                'estado':              obj.estado,
                'cep':                 obj.cep,
                'bairro':              obj.bairro,
                'observacao':          obj.observacao,
                'viavel_pelo_cep':     bool(obj.cep),
                'viavel_pela_cidade':  viavel_pela_cidade,
            }

        registros = (
            [serializar(r, viavel_pela_cidade=False) for r in resultados_diretos]
            + [serializar(r, viavel_pela_cidade=True) for r in resultados_por_cidade]
        )

        tem_viabilidade = bool(registros)

        return JsonResponse({
            'sucesso':          True,
            'cep_consultado':   cep_formatado,
            'cidade_do_cep':    cidade_via_cep,
            'uf_do_cep':        uf_via_cep,
            'tem_viabilidade':  tem_viabilidade,
            'total':            len(registros),
            'registros':        registros,
            'aviso_viacep':     erro_viacep,
        })

    # ── Modo listagem / busca por cidade ─────────────────────────────────
    def serializar_lista(obj):
        return {
            'id':         obj.pk,
            'cidade':     obj.cidade,
            'estado':     obj.estado,
            'cep':        obj.cep,
            'bairro':     obj.bairro,
            'observacao': obj.observacao,
        }

    registros = [serializar_lista(r) for r in qs.order_by('estado', 'cidade', 'cep')]

    return JsonResponse({
        'sucesso':  True,
        'total':    len(registros),
        'registros': registros,
    })


# ============================================================================
# VIEWS DE RELATORIOS SEPARADOS (somente leitura)
# ============================================================================

def relatorio_leads_view(request):
    """Relatorio focado em Leads — reutiliza dados da view principal"""
    from .models import LeadProspecto
    from django.db.models import Count
    from datetime import datetime, timedelta
    import json

    hoje = datetime.now().date()
    data_30 = datetime.now() - timedelta(days=30)
    data_7 = datetime.now() - timedelta(days=7)

    total = LeadProspecto.objects.count()
    leads_hoje = LeadProspecto.objects.filter(data_cadastro__date=hoje).count()
    leads_7d = LeadProspecto.objects.filter(data_cadastro__gte=data_7).count()
    leads_30d = LeadProspecto.objects.filter(data_cadastro__gte=data_30).count()

    por_origem = list(LeadProspecto.objects.values('origem').annotate(total=Count('id')).order_by('-total')[:6])

    por_dia = []
    for i in range(30):
        d = hoje - timedelta(days=i)
        por_dia.append({'data': d.strftime('%d/%m'), 'total': LeadProspecto.objects.filter(data_cadastro__date=d).count()})
    por_dia.reverse()

    return render(request, 'vendas_web/relatorio_leads_page.html', {
        'stats': {
            'total': total, 'hoje': leads_hoje, 'semana': leads_7d, 'mes': leads_30d,
        },
        'graficos': json.dumps({
            'por_origem': por_origem,
            'por_dia': por_dia,
        }),
    })


def relatorio_clientes_view(request):
    """Relatorio focado em Clientes HubSoft — somente leitura"""
    from apps.integracoes.models import ClienteHubsoft, ServicoClienteHubsoft
    from django.db.models import Count, Sum
    from datetime import datetime, timedelta
    import json

    hoje = datetime.now().date()
    data_30 = datetime.now() - timedelta(days=30)
    data_7 = datetime.now() - timedelta(days=7)

    total_clientes = ClienteHubsoft.objects.count()
    ativos = ClienteHubsoft.objects.filter(ativo=True).count()
    total_servicos = ServicoClienteHubsoft.objects.count()
    habilitados = ServicoClienteHubsoft.objects.filter(status_prefixo='servico_habilitado').count()
    aguardando = ServicoClienteHubsoft.objects.filter(status_prefixo='aguardando_instalacao').count()
    cancelados = ServicoClienteHubsoft.objects.filter(status_prefixo__icontains='cancel').count()
    suspensos = ServicoClienteHubsoft.objects.filter(status_prefixo__icontains='suspen').count()

    receita_agg = ServicoClienteHubsoft.objects.filter(status_prefixo='servico_habilitado', valor__isnull=False).aggregate(total=Sum('valor'))
    receita = float(receita_agg['total'] or 0)

    servicos_por_status = list(ServicoClienteHubsoft.objects.values('status_prefixo', 'status').annotate(total=Count('id')).order_by('-total'))

    hab_hoje = ServicoClienteHubsoft.objects.filter(status_prefixo='servico_habilitado', data_habilitacao__date=hoje).count()
    hab_7d = ServicoClienteHubsoft.objects.filter(status_prefixo='servico_habilitado', data_habilitacao__gte=data_7).count()
    hab_30d = ServicoClienteHubsoft.objects.filter(status_prefixo='servico_habilitado', data_habilitacao__gte=data_30).count()

    evolucao = []
    for i in range(30):
        d = hoje - timedelta(days=i)
        evolucao.append({'data': d.strftime('%d/%m'), 'total': ServicoClienteHubsoft.objects.filter(status_prefixo='servico_habilitado', data_habilitacao__date=d).count()})
    evolucao.reverse()

    return render(request, 'vendas_web/relatorio_clientes_page.html', {
        'stats': {
            'total_clientes': total_clientes, 'ativos': ativos, 'total_servicos': total_servicos,
            'habilitados': habilitados, 'aguardando': aguardando, 'cancelados': cancelados,
            'suspensos': suspensos, 'receita': receita,
            'hab_hoje': hab_hoje, 'hab_7d': hab_7d, 'hab_30d': hab_30d,
        },
        'graficos': json.dumps({
            'servicos_por_status': [{'status': s['status'] or s['status_prefixo'], 'total': s['total']} for s in servicos_por_status],
            'evolucao_habilitacoes': evolucao,
        }),
    })


def relatorio_atendimentos_view(request):
    """Relatorio focado em Atendimentos — somente leitura"""
    from .models import HistoricoContato
    from django.db.models import Count
    from datetime import datetime, timedelta
    import json

    hoje = datetime.now().date()
    data_30 = datetime.now() - timedelta(days=30)
    data_7 = datetime.now() - timedelta(days=7)

    total = HistoricoContato.objects.filter(status='fluxo_inicializado').count()
    atend_hoje = HistoricoContato.objects.filter(data_hora_contato__date=hoje, status='fluxo_inicializado').count()
    atend_7d = HistoricoContato.objects.filter(data_hora_contato__gte=data_7, status='fluxo_inicializado').count()
    atend_30d = HistoricoContato.objects.filter(data_hora_contato__gte=data_30, status='fluxo_inicializado').count()

    por_status = list(HistoricoContato.objects.values('status').annotate(total=Count('id')).order_by('-total')[:10])

    por_dia = []
    for i in range(30):
        d = hoje - timedelta(days=i)
        por_dia.append({'data': d.strftime('%d/%m'), 'total': HistoricoContato.objects.filter(data_hora_contato__date=d, status='fluxo_inicializado').count()})
    por_dia.reverse()

    return render(request, 'vendas_web/relatorio_atendimentos_page.html', {
        'stats': {
            'total': total, 'hoje': atend_hoje, 'semana': atend_7d, 'mes': atend_30d,
        },
        'graficos': json.dumps({
            'por_status': por_status,
            'por_dia': por_dia,
        }),
    })