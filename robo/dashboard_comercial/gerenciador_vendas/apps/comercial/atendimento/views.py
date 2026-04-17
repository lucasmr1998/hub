# ============================================================================
# IMPORTS
# ============================================================================
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import models

import json
import logging

logger = logging.getLogger(__name__)

# Models
from apps.comercial.atendimento.models import (
    FluxoAtendimento,
    QuestaoFluxo,
    NodoFluxoAtendimento,
    ConexaoNodoAtendimento,
    AtendimentoFluxo,
    LogFluxoAtendimento,
)
from apps.sistema.utils import auditar


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
# VIEWS DE CONFIGURAÇÃO DE ATENDIMENTO
# ============================================================================

@login_required
def fluxos_atendimento_view(request):
    """View para gerenciar fluxos de atendimento"""
    fluxos = FluxoAtendimento.objects.all().order_by('-data_criacao')
    return render(request, 'comercial/atendimento/fluxos.html', {
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

    return render(request, 'comercial/atendimento/questoes.html', {
        'fluxos': fluxos,
        'questoes': questoes,
        'fluxo_selecionado': fluxo_selecionado
    })


# ============================================================================
# APIS DE GERENCIAMENTO - QUESTÕES DE FLUXO
# ============================================================================

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


# ============================================================================
# EDITOR VISUAL DE FLUXO (Drawflow)
# ============================================================================

@login_required(login_url='sistema:login')
def editor_fluxo_view(request, fluxo_id):
    """Renderiza o editor visual de fluxo (Drawflow)."""
    from django.shortcuts import get_object_or_404
    fluxo = get_object_or_404(FluxoAtendimento, pk=fluxo_id)

    # Se nao tem fluxo_json mas tem nodos no banco, montar dados para reconstruir
    nodos_db = []
    conexoes_db = []
    if not fluxo.fluxo_json:
        for nodo in fluxo.nodos.all().order_by('ordem'):
            nodos_db.append({
                'id': nodo.id,
                'tipo': nodo.tipo,
                'subtipo': nodo.subtipo,
                'nome': nodo.subtipo.replace('_', ' ').title() if nodo.subtipo else nodo.get_tipo_display(),
                'config': nodo.configuracao,
                'pos_x': nodo.pos_x,
                'pos_y': nodo.pos_y,
            })
        for conn in fluxo.conexoes.all():
            conexoes_db.append({
                'origem': conn.nodo_origem_id,
                'destino': conn.nodo_destino_id,
                'tipo_saida': conn.tipo_saida,
            })

    # Integracoes de IA disponiveis
    from apps.integracoes.models import IntegracaoAPI
    integracoes_ia = IntegracaoAPI.objects.filter(
        tipo__in=['openai', 'anthropic', 'groq', 'google_ai'],
        ativa=True,
    ).values_list('id', 'nome', 'tipo')
    integracoes_ia_list = [{'id': i[0], 'nome': i[1], 'tipo': i[2]} for i in integracoes_ia]

    # Filas disponiveis para transferencia
    from apps.inbox.models import FilaInbox
    filas = FilaInbox.objects.filter(ativo=True).values_list('id', 'nome')
    filas_list = [{'id': f[0], 'nome': f[1]} for f in filas]

    context = {
        'fluxo': fluxo,
        'fluxo_json': json.dumps(fluxo.fluxo_json) if fluxo.fluxo_json else '{}',
        'nodos_db': json.dumps(nodos_db),
        'conexoes_db': json.dumps(conexoes_db),
        'integracoes_ia': json.dumps(integracoes_ia_list),
        'filas_inbox': json.dumps(filas_list),
        'recontato_config_json': json.dumps(fluxo.recontato_config or {}),
    }
    return render(request, 'comercial/atendimento/editor_fluxo.html', context)


@login_required(login_url='sistema:login')
@require_http_methods(["POST"])
@auditar('crm', 'salvar_fluxo', 'fluxo_atendimento')
def salvar_fluxo_api(request, fluxo_id):
    """Salva o estado do editor visual (nodos + conexoes)."""
    from django.shortcuts import get_object_or_404
    fluxo = get_object_or_404(FluxoAtendimento, pk=fluxo_id)

    try:
        data = json.loads(request.body)
        drawflow_state = data.get('drawflow_state', {})
        nodos_data = data.get('nodos', [])
        conexoes_data = data.get('conexoes', [])

        # Salvar estado bruto do Drawflow para re-import
        fluxo.fluxo_json = drawflow_state
        fluxo.modo_fluxo = True
        fluxo.save(update_fields=['fluxo_json', 'modo_fluxo'])

        # Recriar nodos e conexoes
        fluxo.nodos.all().delete()
        fluxo.conexoes.all().delete()

        # Mapear id_temp → NodoFluxoAtendimento.pk
        id_map = {}
        for nodo_data in nodos_data:
            nodo = NodoFluxoAtendimento.objects.create(
                tenant=fluxo.tenant,
                fluxo=fluxo,
                tipo=nodo_data.get('tipo', 'entrada'),
                subtipo=nodo_data.get('subtipo', ''),
                configuracao=nodo_data.get('config', {}),
                pos_x=nodo_data.get('pos_x', 0),
                pos_y=nodo_data.get('pos_y', 0),
                ordem=nodo_data.get('ordem', 0),
            )
            id_map[str(nodo_data.get('id_temp', ''))] = nodo

        # Criar conexoes
        for conn_data in conexoes_data:
            origem = id_map.get(str(conn_data.get('origem')))
            destino = id_map.get(str(conn_data.get('destino')))
            if origem and destino:
                ConexaoNodoAtendimento.objects.create(
                    tenant=fluxo.tenant,
                    fluxo=fluxo,
                    nodo_origem=origem,
                    nodo_destino=destino,
                    tipo_saida=conn_data.get('tipo_saida', 'default'),
                )

        # Validar após salvar (retorna avisos mas não bloqueia o save)
        avisos = _validar_fluxo(fluxo)

        return JsonResponse({'ok': True, 'nodos': len(id_map), 'avisos': avisos})

    except Exception as e:
        logger.error(f"Erro ao salvar fluxo visual: {e}")
        return JsonResponse({'ok': False, 'erro': str(e)}, status=400)


def _validar_fluxo(fluxo):
    """Valida integridade de um fluxo visual. Retorna lista de erros/avisos."""
    erros = []

    nodos = list(fluxo.nodos.all())
    conexoes = list(fluxo.conexoes.all())

    if not nodos:
        erros.append({'tipo': 'erro', 'msg': 'Fluxo vazio: nenhum nodo encontrado.'})
        return erros

    # Tem nodo de entrada?
    entradas = [n for n in nodos if n.tipo == 'entrada']
    if not entradas:
        erros.append({'tipo': 'erro', 'msg': 'Falta nodo de Entrada.', 'nodo_tipo': 'entrada'})

    # Tem finalizacao?
    finalizacoes = [n for n in nodos if n.tipo == 'finalizacao']
    if not finalizacoes:
        erros.append({'tipo': 'aviso', 'msg': 'Nenhum nodo de Finalizacao. O fluxo pode nao ter um fim definido.'})

    # Nodos sem conexao de saida (exceto finalizacao)
    nodos_com_saida = {c.nodo_origem_id for c in conexoes}
    for n in nodos:
        if n.tipo not in ('finalizacao',) and n.pk not in nodos_com_saida:
            erros.append({
                'tipo': 'aviso',
                'msg': f'Nodo "{n.get_tipo_display()}" (#{n.pk}) sem conexao de saida.',
                'nodo_id': n.pk,
            })

    # Nodos sem conexao de entrada (exceto entrada)
    nodos_com_entrada = {c.nodo_destino_id for c in conexoes}
    for n in nodos:
        if n.tipo != 'entrada' and n.pk not in nodos_com_entrada:
            erros.append({
                'tipo': 'aviso',
                'msg': f'Nodo "{n.get_tipo_display()}" (#{n.pk}) sem conexao de entrada (orfao).',
                'nodo_id': n.pk,
            })

    # IAs sem integracao configurada
    for n in nodos:
        if n.tipo.startswith('ia_'):
            config = n.configuracao or {}
            if not config.get('integracao_ia_id'):
                erros.append({
                    'tipo': 'erro',
                    'msg': f'Nodo IA "{n.get_tipo_display()}" sem integracao configurada.',
                    'nodo_id': n.pk,
                })

    # Validacao de schema por subtipo
    ACAO_SUBTIPOS_VALIDOS = {
        'criar_oportunidade', 'mover_estagio', 'criar_tarefa', 'webhook',
        'enviar_whatsapp', 'enviar_email', 'notificacao_sistema',
    }
    QUESTAO_IA_ACOES_VALIDAS = {'validar', 'classificar', 'extrair', 'classificar_extrair'}
    FINALIZACAO_MOTIVOS_VALIDOS = {
        'completado', 'ganho', 'perdido', 'sem_interesse', 'sem_viabilidade',
        'duplicado', 'cancelado', 'sem_resposta', 'abandonado_usuario',
        'transferido', 'cancelado_atendente', 'cancelado_sistema', 'tempo_limite',
    }

    for n in nodos:
        config = n.configuracao or {}

        if n.tipo == 'acao':
            if n.subtipo and n.subtipo not in ACAO_SUBTIPOS_VALIDOS:
                erros.append({
                    'tipo': 'erro',
                    'msg': f'Nodo Acao #{n.pk}: subtipo "{n.subtipo}" invalido. Validos: {", ".join(sorted(ACAO_SUBTIPOS_VALIDOS))}',
                    'nodo_id': n.pk,
                })
            # criar_oportunidade: titulo obrigatorio
            if n.subtipo == 'criar_oportunidade' and not config.get('titulo'):
                erros.append({
                    'tipo': 'aviso',
                    'msg': f'Nodo Criar Oportunidade #{n.pk}: sem titulo configurado (usara "{{{{lead_nome}}}}" como padrao).',
                    'nodo_id': n.pk,
                })
            # mover_estagio: estagio obrigatorio
            if n.subtipo == 'mover_estagio' and not config.get('estagio'):
                erros.append({
                    'tipo': 'erro',
                    'msg': f'Nodo Mover Estagio #{n.pk}: campo "estagio" vazio.',
                    'nodo_id': n.pk,
                })
            # webhook: url obrigatoria
            if n.subtipo == 'webhook' and not config.get('url'):
                erros.append({
                    'tipo': 'erro',
                    'msg': f'Nodo Webhook #{n.pk}: campo "url" vazio.',
                    'nodo_id': n.pk,
                })

        if n.tipo == 'questao':
            ia_acao = config.get('ia_acao', 'validar')
            if ia_acao and ia_acao not in QUESTAO_IA_ACOES_VALIDAS:
                erros.append({
                    'tipo': 'erro',
                    'msg': f'Nodo Questao #{n.pk}: ia_acao "{ia_acao}" invalida. Validas: {", ".join(sorted(QUESTAO_IA_ACOES_VALIDAS))}',
                    'nodo_id': n.pk,
                })
            # Se tem ia_acao != validar, precisa de integracao_ia_id
            if ia_acao != 'validar' and not config.get('integracao_ia_id'):
                erros.append({
                    'tipo': 'erro',
                    'msg': f'Nodo Questao #{n.pk}: ia_acao="{ia_acao}" mas sem integracao IA configurada.',
                    'nodo_id': n.pk,
                })
            # Classificar sem categorias
            if ia_acao in ('classificar', 'classificar_extrair') and not config.get('ia_categorias'):
                erros.append({
                    'tipo': 'aviso',
                    'msg': f'Nodo Questao #{n.pk}: ia_acao="{ia_acao}" mas sem categorias definidas.',
                    'nodo_id': n.pk,
                })

        if n.tipo == 'finalizacao':
            motivo = config.get('motivo_finalizacao', '')
            if motivo and motivo not in FINALIZACAO_MOTIVOS_VALIDOS:
                erros.append({
                    'tipo': 'erro',
                    'msg': f'Nodo Finalizacao #{n.pk}: motivo "{motivo}" invalido.',
                    'nodo_id': n.pk,
                })

        if n.tipo == 'condicao':
            if not config.get('campo'):
                erros.append({
                    'tipo': 'aviso',
                    'msg': f'Nodo Condicao #{n.pk}: campo vazio (vai sempre retornar true).',
                    'nodo_id': n.pk,
                })

    return erros


@login_required
@require_http_methods(["POST"])
def api_toggle_fluxo(request, fluxo_id):
    """Ativa ou desativa um fluxo com validação."""
    from django.shortcuts import get_object_or_404
    fluxo = get_object_or_404(FluxoAtendimento, pk=fluxo_id)

    data = json.loads(request.body) if request.body else {}

    # Toggle base de conhecimento
    if data.get('base_conhecimento'):
        fluxo.base_conhecimento_ativa = not fluxo.base_conhecimento_ativa
        fluxo.save(update_fields=['base_conhecimento_ativa'])
        return JsonResponse({
            'ok': True,
            'base_conhecimento_ativa': fluxo.base_conhecimento_ativa,
        })

    novo_status = data.get('status', 'ativo')

    if novo_status == 'ativo':
        avisos = _validar_fluxo(fluxo)
        erros_criticos = [a for a in avisos if a['tipo'] == 'erro']

        if erros_criticos:
            return JsonResponse({
                'ok': False,
                'erro': 'Fluxo com erros criticos. Corrija antes de ativar.',
                'avisos': avisos,
            }, status=400)

    fluxo.status = novo_status
    fluxo.ativo = (novo_status == 'ativo')
    fluxo.save(update_fields=['status', 'ativo'])

    return JsonResponse({
        'ok': True,
        'status': fluxo.status,
        'ativo': fluxo.ativo,
        'message': f'Fluxo {"ativado" if fluxo.ativo else "desativado"} com sucesso.',
    })


# ============================================================================
# SIMULADOR DE TESTE
# ============================================================================

@login_required(login_url='sistema:login')
@require_http_methods(["POST"])
def salvar_recontato_api(request, fluxo_id):
    """Salva configuracao de recontato do fluxo."""
    from django.shortcuts import get_object_or_404
    fluxo = get_object_or_404(FluxoAtendimento, pk=fluxo_id)
    try:
        body = json.loads(request.body)
        fluxo.recontato_ativo = body.get('ativo', False)
        fluxo.recontato_config = body.get('config', {})
        fluxo.save(update_fields=['recontato_ativo', 'recontato_config'])
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'erro': str(e)}, status=400)


# ============================================================================
# LOGS DE EXECUÇÃO (para o editor visual)
# ============================================================================

@login_required(login_url='sistema:login')
def api_atendimentos_fluxo(request, fluxo_id):
    """Lista atendimentos recentes de um fluxo (para sidebar de logs no editor)."""
    from django.shortcuts import get_object_or_404
    fluxo = get_object_or_404(FluxoAtendimento, pk=fluxo_id)

    atendimentos = AtendimentoFluxo.objects.filter(
        fluxo=fluxo
    ).select_related('lead').order_by('-data_inicio')[:20]

    data = [{
        'id': a.pk,
        'lead_nome': a.lead.nome_razaosocial if a.lead else 'Sem lead',
        'lead_telefone': a.lead.telefone if a.lead else '',
        'status': a.status,
        'data_inicio': a.data_inicio.strftime('%d/%m %H:%M') if a.data_inicio else '',
        'nodo_atual_id': a.nodo_atual_id,
    } for a in atendimentos]

    return JsonResponse({'success': True, 'atendimentos': data})


@login_required(login_url='sistema:login')
def api_logs_atendimento(request, atendimento_id):
    """Retorna logs de execução de um atendimento (nodos visitados)."""
    logs = LogFluxoAtendimento.objects.filter(
        atendimento_id=atendimento_id
    ).order_by('data_execucao')

    data = [{
        'nodo_id': log.nodo_id,
        'tipo_nodo': log.tipo_nodo,
        'subtipo_nodo': log.subtipo_nodo,
        'status': log.status,
        'mensagem': log.mensagem[:200],
        'data': log.data_execucao.strftime('%H:%M:%S'),
    } for log in logs]

    return JsonResponse({'success': True, 'logs': data})


@login_required(login_url='sistema:login')
@require_http_methods(["POST"])
def simular_fluxo_api(request, fluxo_id):
    """API para o simulador de teste do editor de fluxos."""
    from django.shortcuts import get_object_or_404
    fluxo = get_object_or_404(FluxoAtendimento, pk=fluxo_id)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'erro': 'JSON invalido'}, status=400)

    action = body.get('action', '')

    if action == 'iniciar':
        nome = body.get('nome', '').strip()
        telefone = body.get('telefone', '00000000000')

        # Criar ou buscar lead de teste
        from apps.comercial.leads.models import LeadProspecto
        lead, _ = LeadProspecto.objects.get_or_create(
            telefone=telefone,
            defaults={'nome_razaosocial': nome, 'origem': 'simulador'}
        )
        # Limpar dados do lead para simular do zero
        lead.nome_razaosocial = nome
        lead.save(update_fields=['nome_razaosocial'])

        # Cancelar atendimentos anteriores desse lead nesse fluxo
        AtendimentoFluxo.objects.filter(
            lead=lead, fluxo=fluxo, status__in=['iniciado', 'em_andamento']
        ).update(status='cancelado')

        # Criar novo atendimento
        atend = AtendimentoFluxo.objects.create(
            lead=lead, fluxo=fluxo,
            status='em_andamento', total_questoes=0, dados_respostas={},
        )

        from .engine import iniciar_fluxo_visual
        resultado = iniciar_fluxo_visual(atend)

        return JsonResponse({
            'ok': True,
            'atendimento_id': atend.pk,
            'resultado': _serializar_resultado(resultado),
        })

    elif action == 'responder':
        atendimento_id = body.get('atendimento_id')
        mensagem = body.get('mensagem', '')

        atend = AtendimentoFluxo.objects.filter(pk=atendimento_id).select_related('nodo_atual').first()
        if not atend or not atend.nodo_atual:
            return JsonResponse({'ok': False, 'erro': 'Atendimento nao encontrado ou finalizado'})

        nodo = atend.nodo_atual
        from .engine import processar_resposta_visual, processar_resposta_ia_respondedor, processar_resposta_ia_agente

        if nodo.tipo == 'ia_respondedor':
            resultado = processar_resposta_ia_respondedor(atend, mensagem)
        elif nodo.tipo == 'ia_agente':
            resultado = processar_resposta_ia_agente(atend, mensagem)
        elif nodo.tipo == 'questao':
            resultado = processar_resposta_visual(atend, mensagem)
        else:
            resultado = {'tipo': 'erro', 'mensagem': f'Tipo de nodo inesperado: {nodo.tipo}'}

        atend.refresh_from_db()
        return JsonResponse({
            'ok': True,
            'atendimento_id': atend.pk,
            'resultado': _serializar_resultado(resultado),
            'status': atend.status,
        })

    return JsonResponse({'ok': False, 'erro': 'Action invalida'}, status=400)


def _serializar_resultado(resultado):
    """Serializa resultado do engine para JSON."""
    if not resultado:
        return {'tipo': 'erro', 'mensagem': 'Sem resultado'}
    r = {'tipo': resultado.get('tipo', ''), 'mensagem': resultado.get('mensagem', '')}
    if resultado.get('questao'):
        q = resultado['questao']
        r['opcoes'] = q.get('opcoes_resposta', [])
    if resultado.get('erro'):
        r['erro'] = resultado['erro']
    return r


# ============================================================================
# ACOMPANHAMENTO DE SESSOES
# ============================================================================

@login_required(login_url='sistema:login')
def sessoes_atendimento_view(request):
    """Tela de acompanhamento de sessoes ativas e historico."""
    status_filter = request.GET.get('status', '')
    fluxo_filter = request.GET.get('fluxo', '')

    sessoes = AtendimentoFluxo.objects.select_related(
        'lead', 'fluxo', 'nodo_atual'
    ).order_by('-data_inicio')

    if status_filter == 'em_andamento':
        sessoes = sessoes.filter(status__in=['iniciado', 'em_andamento', 'pausado'])
    elif status_filter:
        sessoes = sessoes.filter(status=status_filter)
    if fluxo_filter:
        sessoes = sessoes.filter(fluxo_id=fluxo_filter)

    fluxos = FluxoAtendimento.objects.all().order_by('nome')

    context = {
        'sessoes': sessoes[:100],
        'fluxos': fluxos,
        'status_filter': status_filter,
        'fluxo_filter': fluxo_filter,
    }
    return render(request, 'comercial/atendimento/sessoes.html', context)


@login_required(login_url='sistema:login')
def sessao_detalhe_view(request, atendimento_id):
    """Detalhe de uma sessao com logs de execucao."""
    from django.shortcuts import get_object_or_404
    sessao = get_object_or_404(
        AtendimentoFluxo.objects.select_related('lead', 'fluxo', 'nodo_atual'),
        pk=atendimento_id
    )
    logs = LogFluxoAtendimento.objects.filter(
        atendimento=sessao
    ).select_related('nodo').order_by('data_execucao')

    context = {
        'sessao': sessao,
        'logs': logs,
    }
    return render(request, 'comercial/atendimento/sessao_detalhe.html', context)


@login_required(login_url='sistema:login')
def sessao_debug_view(request, atendimento_id):
    """Tela de debug detalhada com timeline, logs LLM (prompt+resposta), contexto e variaveis."""
    from django.shortcuts import get_object_or_404
    import json as _json

    sessao = get_object_or_404(
        AtendimentoFluxo.objects.select_related('lead', 'fluxo', 'nodo_atual'),
        pk=atendimento_id
    )
    logs = list(
        LogFluxoAtendimento.objects.filter(atendimento=sessao)
        .select_related('nodo').order_by('data_execucao')
    )

    # Separar logs LLM dos demais
    timeline = []
    for log in logs:
        dados = log.dados or {}
        is_llm = dados.get('llm_call', False) or log.status == 'llm'
        timeline.append({
            'log': log,
            'is_llm': is_llm,
            'dados_json': _json.dumps(dados, ensure_ascii=False, indent=2, default=str) if dados else '',
            'llm_info': {
                'contexto_chamada': dados.get('contexto_chamada', ''),
                'modelo': dados.get('modelo', ''),
                'system_prompt': dados.get('system_prompt', ''),
                'conversation': dados.get('conversation', []),
                'resultado_raw': dados.get('resultado_raw', ''),
            } if is_llm else None,
        })

    # Resumo do contexto
    dados_respostas = sessao.dados_respostas or {}
    variaveis = dados_respostas.get('variaveis', {})
    respostas = {
        k: v for k, v in dados_respostas.items()
        if k not in ('variaveis',) and not k.startswith('_') and not k.startswith('ia_')
    }
    historicos_ia = {
        k: v for k, v in dados_respostas.items()
        if k.startswith('ia_agente_') or k.startswith('ia_historico_')
    }
    metadados = {
        k: v for k, v in dados_respostas.items() if k.startswith('_')
    }

    context = {
        'sessao': sessao,
        'timeline': timeline,
        'total_logs': len(logs),
        'total_llm_calls': sum(1 for t in timeline if t['is_llm']),
        'variaveis': variaveis,
        'respostas': respostas,
        'historicos_ia': historicos_ia,
        'metadados': metadados,
        'dados_respostas_json': _json.dumps(dados_respostas, ensure_ascii=False, indent=2, default=str),
    }
    return render(request, 'comercial/atendimento/sessao_debug.html', context)


@login_required(login_url='sistema:login')
def sessao_fluxo_visual_view(request, atendimento_id):
    """Visualizacao do fluxo com destaque do nodo atual da sessao."""
    from django.shortcuts import get_object_or_404
    sessao = get_object_or_404(
        AtendimentoFluxo.objects.select_related('lead', 'fluxo', 'nodo_atual'),
        pk=atendimento_id
    )
    fluxo = sessao.fluxo

    # IDs dos nodos ja executados (via logs)
    nodos_executados = list(
        LogFluxoAtendimento.objects.filter(
            atendimento=sessao, status='sucesso'
        ).exclude(nodo__isnull=True).values_list('nodo_id', flat=True).distinct()
    )

    # Nodo atual
    nodo_atual_id = sessao.nodo_atual_id

    context = {
        'sessao': sessao,
        'fluxo': fluxo,
        'fluxo_json': json.dumps(fluxo.fluxo_json) if fluxo.fluxo_json else '{}',
        'nodos_executados': json.dumps(nodos_executados),
        'nodo_atual_id': nodo_atual_id or 0,
    }

    # Se nao tem fluxo_json, montar dos nodos do banco
    if not fluxo.fluxo_json:
        nodos_db = []
        conexoes_db = []
        for nodo in fluxo.nodos.all().order_by('ordem'):
            nodos_db.append({
                'id': nodo.id,
                'tipo': nodo.tipo,
                'subtipo': nodo.subtipo,
                'nome': nodo.subtipo.replace('_', ' ').title() if nodo.subtipo else nodo.get_tipo_display(),
                'config': nodo.configuracao,
                'pos_x': nodo.pos_x,
                'pos_y': nodo.pos_y,
            })
        for conn in fluxo.conexoes.all():
            conexoes_db.append({
                'origem': conn.nodo_origem_id,
                'destino': conn.nodo_destino_id,
                'tipo_saida': conn.tipo_saida,
            })
        context['nodos_db'] = json.dumps(nodos_db)
        context['conexoes_db'] = json.dumps(conexoes_db)
    else:
        context['nodos_db'] = '[]'
        context['conexoes_db'] = '[]'

    return render(request, 'comercial/atendimento/sessao_fluxo_visual.html', context)
