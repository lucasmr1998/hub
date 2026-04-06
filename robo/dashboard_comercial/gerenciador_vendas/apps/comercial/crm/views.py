import json
import logging
from decimal import Decimal

import requests
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from apps.sistema.decorators import webhook_token_required, user_tem_funcionalidade
from apps.sistema.models import PerfilUsuario

from .models import (
    PipelineEstagio, OportunidadeVenda, HistoricoPipelineEstagio,
    TarefaCRM, NotaInterna, MetaVendas, SegmentoCRM, AlertaRetencao,
    ConfiguracaoCRM, EquipeVendas, PerfilVendedor,
)

logger = logging.getLogger(__name__)


# ============================================================================
# HELPERS
# ============================================================================

def _check_perm(request, codigo):
    """Retorna JsonResponse 403 se o usuário não tem a funcionalidade, ou None se tem."""
    if not user_tem_funcionalidade(request, codigo):
        return JsonResponse({'error': 'Sem permissão para esta ação'}, status=403)
    return None


def _disparar_webhook(url, payload):
    if not url:
        return
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.warning(f"[CRM] Webhook falhou ({url}): {e}")


def _oportunidade_para_dict(op):
    lead = op.lead
    responsavel = op.responsavel
    # Usa o prefetch_related cache (evita N+1) — .all() usa cache, .filter() cria nova query
    tarefas_pendentes = sum(
        1 for t in op.tarefas.all()
        if t.status in ('pendente', 'em_andamento')
    )

    return {
        'id': op.pk,
        'lead_id': lead.pk,
        'nome': op.titulo or lead.nome_razaosocial,
        'telefone': lead.telefone,
        'email': lead.email or '',
        'valor': str(op.valor_estimado or 0),
        'probabilidade': op.probabilidade,
        'prioridade': op.prioridade,
        'score': lead.score_qualificacao or 0,
        'origem': lead.origem or '',
        'dias_no_estagio': op.dias_no_estagio,
        'sla_vencido': op.sla_vencido,
        'responsavel_id': responsavel.pk if responsavel else None,
        'responsavel_nome': responsavel.get_full_name() or responsavel.username if responsavel else None,
        'responsavel_inicial': (responsavel.get_full_name() or responsavel.username)[0].upper() if responsavel else '?',
        'tarefas_pendentes': tarefas_pendentes,
        'estagio_id': op.estagio_id,
        'data_criacao': op.data_criacao.strftime('%d/%m/%Y'),
        'data_prevista': op.data_fechamento_previsto.strftime('%d/%m/%Y') if op.data_fechamento_previsto else None,
        'plano': op.plano_interesse.nome if op.plano_interesse else None,
        'tags': [{'nome': t.nome, 'cor': t.cor_hex} for t in op.tags.all()],
        'churn_risk_score': op.churn_risk_score,
    }


# ============================================================================
# PIPELINE / KANBAN
# ============================================================================

@login_required
def pipeline_view(request):
    denied = _check_perm(request, 'comercial.ver_pipeline')
    if denied: return denied
    from .models import Pipeline

    pipelines = Pipeline.objects.filter(ativo=True)
    pipeline_id = request.GET.get('pipeline')
    if pipeline_id:
        pipeline_atual = pipelines.filter(pk=pipeline_id).first()
    else:
        pipeline_atual = pipelines.filter(padrao=True).first() or pipelines.first()

    if pipeline_atual:
        estagios = PipelineEstagio.objects.filter(pipeline=pipeline_atual, ativo=True).order_by('ordem')
    else:
        estagios = PipelineEstagio.objects.filter(ativo=True).order_by('ordem')

    vendedores = []
    from django.contrib.auth.models import User
    for u in User.objects.filter(is_active=True, perfil__tenant=request.tenant).order_by('first_name'):
        vendedores.append({'id': u.pk, 'nome': u.get_full_name() or u.username})

    from .models import TagCRM
    tags = TagCRM.objects.all().order_by('nome')

    context = {
        'estagios': estagios,
        'vendedores': vendedores,
        'tags': tags,
        'pipelines': pipelines,
        'pipeline_atual': pipeline_atual,
        'page_title': f'Pipeline: {pipeline_atual.nome}' if pipeline_atual else 'Pipeline CRM',
    }
    return render(request, 'crm/pipeline.html', context)


@login_required
@require_GET
def api_pipeline_dados(request):
    pipeline_id = request.GET.get('pipeline_id') or request.GET.get('pipeline')
    if pipeline_id:
        estagios = PipelineEstagio.objects.filter(pipeline_id=pipeline_id, ativo=True).order_by('ordem')
    else:
        estagios = PipelineEstagio.objects.filter(ativo=True).order_by('ordem')

    # Filtros
    responsavel_id = request.GET.get('responsavel')
    prioridade = request.GET.get('prioridade')
    search = request.GET.get('search', '').strip()

    qs = OportunidadeVenda.objects.filter(ativo=True).select_related(
        'lead', 'estagio', 'responsavel', 'plano_interesse', 'pipeline'
    ).prefetch_related('tarefas', 'tags')

    if pipeline_id:
        qs = qs.filter(pipeline_id=pipeline_id)

    # Regra de visibilidade baseada em funcionalidade
    if not user_tem_funcionalidade(request, 'comercial.ver_todas_oportunidades'):
        from django.db.models import Q
        qs = qs.filter(Q(responsavel=request.user) | Q(responsavel__isnull=True))

    tag = request.GET.get('tag', '').strip()
    valor_range = request.GET.get('valor', '').strip()

    if responsavel_id:
        qs = qs.filter(responsavel_id=responsavel_id)
    if prioridade:
        qs = qs.filter(prioridade=prioridade)
    if tag:
        qs = qs.filter(tags__nome=tag)
    if valor_range:
        if valor_range == '1000+':
            qs = qs.filter(valor_estimado__gte=1000)
        elif '-' in valor_range:
            parts = valor_range.split('-')
            qs = qs.filter(valor_estimado__gte=Decimal(parts[0]), valor_estimado__lte=Decimal(parts[1]))
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(lead__nome_razaosocial__icontains=search) |
            Q(lead__telefone__icontains=search) |
            Q(titulo__icontains=search)
        )

    # Agrupar por estágio
    oportunidades_por_estagio = {}
    for op in qs:
        eid = op.estagio_id
        if eid not in oportunidades_por_estagio:
            oportunidades_por_estagio[eid] = []
        oportunidades_por_estagio[eid].append(_oportunidade_para_dict(op))

    resultado = []
    for estagio in estagios:
        ops = oportunidades_por_estagio.get(estagio.pk, [])
        total_valor = sum(float(o['valor']) for o in ops)
        resultado.append({
            'id': estagio.pk,
            'nome': estagio.nome,
            'slug': estagio.slug,
            'cor': estagio.cor_hex,
            'icone': estagio.icone_fa,
            'is_final_ganho': estagio.is_final_ganho,
            'is_final_perdido': estagio.is_final_perdido,
            'sla_horas': estagio.sla_horas,
            'total': len(ops),
            'total_valor': total_valor,
            'oportunidades': ops,
        })

    return JsonResponse({'estagios': resultado, 'ok': True})


@login_required
@require_POST
def api_mover_oportunidade(request):
    denied = _check_perm(request, 'comercial.mover_oportunidade')
    if denied: return denied
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    oportunidade_id = data.get('oportunidade_id')
    estagio_novo_id = data.get('estagio_id')
    motivo = data.get('motivo', '')

    if not oportunidade_id or not estagio_novo_id:
        return JsonResponse({'ok': False, 'erro': 'Campos obrigatórios: oportunidade_id, estagio_id'}, status=400)

    oportunidade = get_object_or_404(OportunidadeVenda, pk=oportunidade_id, ativo=True)
    estagio_novo = get_object_or_404(PipelineEstagio, pk=estagio_novo_id, ativo=True)

    # Verificar permissão
    if not request.user.is_superuser:
        if oportunidade.responsavel and oportunidade.responsavel != request.user:
            return JsonResponse({'ok': False, 'erro': 'Sem permissão para mover esta oportunidade'}, status=403)

    if oportunidade.estagio_id == estagio_novo_id:
        return JsonResponse({'ok': True, 'mensagem': 'Sem mudança de estágio'})

    # Calcular tempo no estágio atual
    horas_no_estagio = (timezone.now() - oportunidade.data_entrada_estagio).total_seconds() / 3600

    estagio_anterior = oportunidade.estagio

    # Registrar histórico
    HistoricoPipelineEstagio.objects.create(
        oportunidade=oportunidade,
        estagio_anterior=estagio_anterior,
        estagio_novo=estagio_novo,
        movido_por=request.user,
        motivo=motivo,
        tempo_no_estagio_horas=round(horas_no_estagio, 2),
    )

    # Atualizar oportunidade
    oportunidade.estagio = estagio_novo
    oportunidade.data_entrada_estagio = timezone.now()
    oportunidade.probabilidade = estagio_novo.probabilidade_padrao

    campos = ['estagio', 'data_entrada_estagio', 'probabilidade', 'data_atualizacao']

    if estagio_novo.is_final_ganho and not oportunidade.data_fechamento_real:
        oportunidade.data_fechamento_real = timezone.now()
        campos.append('data_fechamento_real')
        _atualizar_meta_venda(oportunidade, request.user)

    oportunidade.save(update_fields=campos)

    # Disparar webhook N8N
    try:
        config = ConfiguracaoCRM.get_config()
        _disparar_webhook(config.webhook_n8n_mudanca_estagio, {
            'oportunidade_id': oportunidade.pk,
            'lead_nome': oportunidade.lead.nome_razaosocial,
            'lead_telefone': oportunidade.lead.telefone,
            'estagio_anterior': estagio_anterior.nome,
            'estagio_novo': estagio_novo.nome,
            'responsavel_nome': request.user.get_full_name() or request.user.username,
        })
    except Exception:
        pass

    return JsonResponse({
        'ok': True,
        'oportunidade': _oportunidade_para_dict(oportunidade),
    })


def _atualizar_meta_venda(oportunidade, usuario):
    """Atualiza MetaVendas do vendedor responsável ao fechar uma venda."""
    responsavel = oportunidade.responsavel or usuario
    hoje = timezone.now().date()

    meta = MetaVendas.objects.filter(
        tipo='individual',
        vendedor=responsavel,
        data_inicio__lte=hoje,
        data_fim__gte=hoje,
    ).first()

    if meta:
        from django.db.models import F
        MetaVendas.objects.filter(pk=meta.pk).update(
            realizado_vendas_quantidade=F('realizado_vendas_quantidade') + 1,
            realizado_vendas_valor=F('realizado_vendas_valor') + (oportunidade.valor_estimado or 0),
        )


# ============================================================================
# OPORTUNIDADES
# ============================================================================

@login_required
def oportunidades_lista(request):
    from django.db.models import Q
    from .models import TagCRM

    qs = OportunidadeVenda.objects.filter(ativo=True).select_related(
        'lead', 'estagio', 'responsavel'
    ).prefetch_related('tags').order_by('estagio__ordem', '-data_criacao')

    if not request.user.is_superuser:
        qs = qs.filter(Q(responsavel=request.user) | Q(responsavel__isnull=True))

    # Filtros
    search = request.GET.get('search', '').strip()
    estagio_id = request.GET.get('estagio')
    responsavel_id = request.GET.get('responsavel')
    tag_nome = request.GET.get('tag', '').strip()

    if search:
        qs = qs.filter(
            Q(lead__nome_razaosocial__icontains=search) |
            Q(lead__telefone__icontains=search) |
            Q(titulo__icontains=search)
        )
    if estagio_id:
        qs = qs.filter(estagio_id=estagio_id)
    if responsavel_id:
        qs = qs.filter(responsavel_id=responsavel_id)
    if tag_nome:
        qs = qs.filter(tags__nome=tag_nome)

    estagios = PipelineEstagio.objects.filter(ativo=True).order_by('ordem')
    tags = TagCRM.objects.all().order_by('nome')

    from django.contrib.auth.models import User
    vendedores = []
    for u in User.objects.filter(is_active=True, perfil__tenant=request.tenant).order_by('first_name'):
        vendedores.append({'id': u.pk, 'nome': u.get_full_name() or u.username})

    context = {
        'oportunidades': qs,
        'estagios': estagios,
        'tags': tags,
        'vendedores': vendedores,
        'filtro_search': search,
        'filtro_estagio': estagio_id,
        'filtro_responsavel': responsavel_id,
        'filtro_tag': tag_nome,
        'page_title': 'Oportunidades',
    }
    return render(request, 'crm/oportunidades_lista.html', context)


@login_required
def oportunidade_detalhe(request, pk):
    oportunidade = get_object_or_404(
        OportunidadeVenda.objects.select_related(
            'lead', 'estagio', 'responsavel', 'plano_interesse', 'criado_por'
        ).prefetch_related('tags', 'notas__autor', 'tarefas__responsavel'),
        pk=pk
    )

    lead = oportunidade.lead

    # Dados cross-app (sem duplicar, apenas consultando)
    from apps.comercial.leads.models import HistoricoContato
    historico_contatos = HistoricoContato.objects.filter(lead=lead).order_by('-data_hora_contato')[:20]

    try:
        from apps.integracoes.models import ClienteHubsoft
        cliente_hubsoft = ClienteHubsoft.objects.filter(lead=lead).prefetch_related('servicos').first()
    except Exception:
        cliente_hubsoft = None

    historico_estagios = HistoricoPipelineEstagio.objects.filter(
        oportunidade=oportunidade
    ).select_related('estagio_anterior', 'estagio_novo', 'movido_por').order_by('-data_transicao')

    estagios = PipelineEstagio.objects.filter(ativo=True).order_by('ordem')

    from django.contrib.auth.models import User
    vendedores = User.objects.filter(is_active=True, perfil__tenant=request.tenant).order_by('first_name')

    # Timeline de automações para este lead
    from apps.marketing.automacoes.models import LogExecucao as LogAutomacao
    logs_automacao = LogAutomacao.all_tenants.filter(
        tenant=request.tenant, lead=lead,
    ).select_related('regra', 'acao', 'nodo').order_by('-data_execucao')[:20]

    context = {
        'oportunidade': oportunidade,
        'lead': lead,
        'historico_contatos': historico_contatos,
        'cliente_hubsoft': cliente_hubsoft,
        'historico_estagios': historico_estagios,
        'logs_automacao': logs_automacao,
        'estagios': estagios,
        'vendedores': vendedores,
        'page_title': f'CRM — {oportunidade.titulo or lead.nome_razaosocial}',
    }
    return render(request, 'crm/oportunidade_detalhe.html', context)


@login_required
@require_POST
def api_atribuir_responsavel(request, pk):
    oportunidade = get_object_or_404(OportunidadeVenda, pk=pk)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    from django.contrib.auth.models import User
    responsavel_id = data.get('responsavel_id')
    if responsavel_id:
        responsavel = get_object_or_404(User, pk=responsavel_id)
        oportunidade.responsavel = responsavel
    else:
        oportunidade.responsavel = None
    oportunidade.save(update_fields=['responsavel', 'data_atualizacao'])
    nome = oportunidade.responsavel.get_full_name() if oportunidade.responsavel else None
    return JsonResponse({'ok': True, 'responsavel_nome': nome})


@login_required
def api_notas_oportunidade(request, pk):
    oportunidade = get_object_or_404(OportunidadeVenda, pk=pk)

    if request.method == 'GET':
        notas = oportunidade.notas.select_related('autor').order_by('-is_fixada', '-data_criacao')
        return JsonResponse({'notas': [
            {
                'id': n.pk,
                'conteudo': n.conteudo,
                'tipo': n.tipo,
                'tipo_label': n.get_tipo_display(),
                'autor': n.autor.get_full_name() or n.autor.username,
                'is_fixada': n.is_fixada,
                'data': n.data_criacao.strftime('%d/%m/%Y %H:%M'),
                'editado': n.editado,
            }
            for n in notas
        ]})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

        conteudo = data.get('conteudo', '').strip()
        if not conteudo:
            return JsonResponse({'ok': False, 'erro': 'Conteúdo obrigatório'}, status=400)

        nota = NotaInterna.objects.create(
            oportunidade=oportunidade,
            lead=oportunidade.lead,
            autor=request.user,
            conteudo=conteudo,
            tipo=data.get('tipo', 'geral'),
        )
        return JsonResponse({'ok': True, 'id': nota.pk, 'data': nota.data_criacao.strftime('%d/%m/%Y %H:%M')})

    return JsonResponse({'ok': False, 'erro': 'Método não permitido'}, status=405)


@login_required
def api_tarefas_oportunidade(request, pk):
    oportunidade = get_object_or_404(OportunidadeVenda, pk=pk)

    if request.method == 'GET':
        tarefas = oportunidade.tarefas.select_related('responsavel').order_by('data_vencimento')
        return JsonResponse({'tarefas': [
            {
                'id': t.pk,
                'titulo': t.titulo,
                'tipo': t.tipo,
                'tipo_label': t.get_tipo_display(),
                'status': t.status,
                'prioridade': t.prioridade,
                'responsavel': t.responsavel.get_full_name() or t.responsavel.username,
                'vencimento': t.data_vencimento.strftime('%d/%m/%Y %H:%M') if t.data_vencimento else None,
                'concluida_em': t.data_conclusao.strftime('%d/%m/%Y %H:%M') if t.data_conclusao else None,
            }
            for t in tarefas
        ]})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

        from django.contrib.auth.models import User
        responsavel_id = data.get('responsavel_id', request.user.pk)
        responsavel = get_object_or_404(User, pk=responsavel_id)

        from datetime import datetime
        vencimento = None
        if data.get('data_vencimento'):
            try:
                vencimento = datetime.fromisoformat(data['data_vencimento'])
                if timezone.is_naive(vencimento):
                    vencimento = timezone.make_aware(vencimento)
            except ValueError:
                pass

        tarefa = TarefaCRM.objects.create(
            oportunidade=oportunidade,
            lead=oportunidade.lead,
            responsavel=responsavel,
            criado_por=request.user,
            tipo=data.get('tipo', 'followup'),
            titulo=data.get('titulo', ''),
            descricao=data.get('descricao', ''),
            prioridade=data.get('prioridade', 'normal'),
            data_vencimento=vencimento,
        )
        return JsonResponse({'ok': True, 'id': tarefa.pk})

    return JsonResponse({'ok': False, 'erro': 'Método não permitido'}, status=405)


# ============================================================================
# TAREFAS
# ============================================================================

@login_required
def tarefas_lista(request):
    denied = _check_perm(request, 'comercial.criar_tarefa')
    if denied: return denied
    from django.db.models import Q

    # Base: tarefas do usuário logado (ver_todas_oportunidades vê todas)
    if user_tem_funcionalidade(request, 'comercial.ver_todas_oportunidades'):
        qs = TarefaCRM.objects.all()
    else:
        qs = TarefaCRM.objects.filter(responsavel=request.user)

    qs = qs.select_related('lead', 'oportunidade', 'criado_por', 'responsavel').order_by('data_vencimento')

    # Filtros
    filtro_tipo = request.GET.get('tipo', '')
    filtro_responsavel = request.GET.get('responsavel', '')
    filtro_prioridade = request.GET.get('prioridade', '')
    filtro_search = request.GET.get('search', '').strip()

    if filtro_tipo:
        qs = qs.filter(tipo=filtro_tipo)
    if filtro_responsavel:
        qs = qs.filter(responsavel_id=filtro_responsavel)
    if filtro_prioridade:
        qs = qs.filter(prioridade=filtro_prioridade)
    if filtro_search:
        qs = qs.filter(
            Q(titulo__icontains=filtro_search) |
            Q(lead__nome_razaosocial__icontains=filtro_search)
        )

    hoje = timezone.now().date()
    tarefas_hoje = qs.filter(data_vencimento__date=hoje, status__in=['pendente', 'em_andamento'])
    tarefas_semana = qs.filter(
        data_vencimento__date__gt=hoje,
        data_vencimento__date__lte=hoje + timezone.timedelta(days=7),
        status__in=['pendente', 'em_andamento']
    )
    tarefas_vencidas = qs.filter(data_vencimento__lt=timezone.now(), status__in=['pendente', 'em_andamento', 'vencida'])
    tarefas_todas = qs.exclude(status='concluida')
    tarefas_concluidas = qs.filter(status='concluida').order_by('-data_conclusao')[:20]

    # Dados para filtros
    from django.contrib.auth.models import User
    vendedores = []
    for u in User.objects.filter(is_active=True, perfil__tenant=request.tenant).order_by('first_name'):
        vendedores.append({'id': u.pk, 'nome': u.get_full_name() or u.username})

    context = {
        'tarefas_hoje': tarefas_hoje,
        'tarefas_semana': tarefas_semana,
        'tarefas_vencidas': tarefas_vencidas,
        'tarefas_todas': tarefas_todas,
        'tarefas_concluidas': tarefas_concluidas,
        'vendedores': vendedores,
        'filtro_tipo': filtro_tipo,
        'filtro_responsavel': filtro_responsavel,
        'filtro_prioridade': filtro_prioridade,
        'filtro_search': filtro_search,
        'tipos_tarefa': TarefaCRM.TIPO_CHOICES,
        'prioridades': TarefaCRM.PRIORIDADE_CHOICES,
        'page_title': 'Tarefas CRM',
    }
    return render(request, 'crm/tarefas_lista.html', context)


@login_required
@require_POST
def api_tarefa_concluir(request, pk):
    tarefa = get_object_or_404(TarefaCRM, pk=pk, responsavel=request.user)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}

    tarefa.status = 'concluida'
    tarefa.data_conclusao = timezone.now()
    tarefa.resultado = data.get('resultado', '')
    tarefa.save(update_fields=['status', 'data_conclusao', 'resultado', 'data_atualizacao'])
    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_tarefa_criar(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    from django.contrib.auth.models import User
    responsavel_id = data.get('responsavel_id', request.user.pk)
    responsavel = get_object_or_404(User, pk=responsavel_id)

    from datetime import datetime
    vencimento = None
    if data.get('data_vencimento'):
        try:
            vencimento = datetime.fromisoformat(data['data_vencimento'])
            if timezone.is_naive(vencimento):
                vencimento = timezone.make_aware(vencimento)
        except ValueError:
            pass

    oportunidade = None
    if data.get('oportunidade_id'):
        try:
            oportunidade = OportunidadeVenda.objects.get(pk=data['oportunidade_id'])
        except OportunidadeVenda.DoesNotExist:
            pass

    lead = None
    if oportunidade:
        lead = oportunidade.lead
    elif data.get('lead_id'):
        from apps.comercial.leads.models import LeadProspecto
        try:
            lead = LeadProspecto.objects.get(pk=data['lead_id'])
        except Exception:
            pass

    tarefa = TarefaCRM.objects.create(
        oportunidade=oportunidade,
        lead=lead,
        responsavel=responsavel,
        criado_por=request.user,
        tipo=data.get('tipo', 'followup'),
        titulo=data.get('titulo', ''),
        descricao=data.get('descricao', ''),
        prioridade=data.get('prioridade', 'normal'),
        data_vencimento=vencimento,
    )
    return JsonResponse({'ok': True, 'id': tarefa.pk})


# ============================================================================
# NOTAS
# ============================================================================

@login_required
@require_POST
def api_nota_criar(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    conteudo = data.get('conteudo', '').strip()
    if not conteudo:
        return JsonResponse({'ok': False, 'erro': 'Conteúdo obrigatório'}, status=400)

    oportunidade = None
    if data.get('oportunidade_id'):
        try:
            oportunidade = OportunidadeVenda.objects.get(pk=data['oportunidade_id'])
        except OportunidadeVenda.DoesNotExist:
            pass

    lead = None
    if oportunidade:
        lead = oportunidade.lead
    elif data.get('lead_id'):
        from apps.comercial.leads.models import LeadProspecto
        try:
            lead = LeadProspecto.objects.get(pk=data['lead_id'])
        except Exception:
            pass

    nota = NotaInterna.objects.create(
        oportunidade=oportunidade,
        lead=lead,
        autor=request.user,
        conteudo=conteudo,
        tipo=data.get('tipo', 'geral'),
    )
    return JsonResponse({'ok': True, 'id': nota.pk})


@login_required
@require_POST
def api_nota_fixar(request, pk):
    nota = get_object_or_404(NotaInterna, pk=pk)
    nota.is_fixada = not nota.is_fixada
    nota.save(update_fields=['is_fixada'])
    return JsonResponse({'ok': True, 'fixada': nota.is_fixada})


@login_required
@require_POST
def api_nota_deletar(request, pk):
    nota = get_object_or_404(NotaInterna, pk=pk, autor=request.user)
    nota.delete()
    return JsonResponse({'ok': True})


# ============================================================================
# DESEMPENHO / METAS
# ============================================================================

@login_required
def desempenho_view(request):
    denied = _check_perm(request, 'comercial.ver_desempenho')
    if denied: return denied
    from django.contrib.auth.models import User
    hoje = timezone.now().date()
    mes_inicio = hoje.replace(day=1)

    vendedores = User.objects.filter(is_active=True, perfil__tenant=request.tenant).order_by('first_name')
    estagios = PipelineEstagio.objects.filter(ativo=True).order_by('ordem')

    context = {
        'vendedores': vendedores,
        'estagios': estagios,
        'mes_inicio': mes_inicio,
        'page_title': 'Desempenho da Equipe',
    }
    return render(request, 'crm/desempenho.html', context)


@login_required
@require_GET
def api_desempenho_dados(request):
    from django.contrib.auth.models import User
    from django.db.models import Count, Sum

    periodo = request.GET.get('periodo', 'mes')
    hoje = timezone.now().date()

    if periodo == 'semana':
        data_inicio = hoje - timezone.timedelta(days=7)
    elif periodo == 'trimestre':
        data_inicio = hoje - timezone.timedelta(days=90)
    else:
        data_inicio = hoje.replace(day=1)

    # Oportunidades fechadas no período
    ops_ganhas = OportunidadeVenda.objects.filter(
        estagio__is_final_ganho=True,
        data_fechamento_real__date__gte=data_inicio,
        ativo=True,
    ).values('responsavel').annotate(
        total=Count('id'),
        valor=Sum('valor_estimado'),
    )

    por_vendedor = {item['responsavel']: item for item in ops_ganhas}

    resultado = []
    for u in User.objects.filter(is_active=True, perfil__tenant=request.tenant):
        dados = por_vendedor.get(u.pk, {'total': 0, 'valor': 0})
        ativas = OportunidadeVenda.objects.filter(responsavel=u, ativo=True).exclude(
            estagio__is_final_ganho=True
        ).exclude(estagio__is_final_perdido=True).count()

        meta = MetaVendas.objects.filter(
            tipo='individual', vendedor=u,
            data_inicio__lte=hoje, data_fim__gte=hoje
        ).first()

        resultado.append({
            'id': u.pk,
            'nome': u.get_full_name() or u.username,
            'vendas_quantidade': dados['total'],
            'vendas_valor': float(dados['valor'] or 0),
            'oportunidades_ativas': ativas,
            'meta_quantidade': meta.meta_vendas_quantidade if meta else 0,
            'meta_valor': float(meta.meta_vendas_valor) if meta else 0,
        })

    resultado.sort(key=lambda x: x['vendas_quantidade'], reverse=True)

    # Funil por estágio
    funil = []
    for e in PipelineEstagio.objects.filter(ativo=True).order_by('ordem'):
        total = OportunidadeVenda.objects.filter(estagio=e, ativo=True).count()
        funil.append({'estagio': e.nome, 'cor': e.cor_hex, 'total': total})

    return JsonResponse({'vendedores': resultado, 'funil': funil, 'ok': True})


@login_required
def metas_view(request):
    denied = _check_perm(request, 'comercial.gerenciar_metas')
    if denied: return denied
    hoje = timezone.now().date()
    metas_ativas = MetaVendas.objects.filter(
        data_inicio__lte=hoje, data_fim__gte=hoje
    ).select_related('vendedor', 'equipe').order_by('-data_inicio')

    from django.contrib.auth.models import User
    vendedores = User.objects.filter(is_active=True, perfil__tenant=request.tenant).order_by('first_name')
    equipes = EquipeVendas.objects.filter(ativo=True)

    context = {
        'metas_ativas': metas_ativas,
        'vendedores': vendedores,
        'equipes': equipes,
        'page_title': 'Metas de Vendas',
    }
    return render(request, 'crm/metas.html', context)


@login_required
@require_POST
def api_meta_criar(request):
    denied = _check_perm(request, 'comercial.gerenciar_metas')
    if denied: return denied
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    from django.contrib.auth.models import User
    from datetime import date

    meta = MetaVendas(
        tipo=data.get('tipo', 'individual'),
        periodo=data.get('periodo', 'mensal'),
        criado_por=request.user,
        meta_vendas_quantidade=int(data.get('meta_vendas_quantidade', 0)),
        meta_vendas_valor=Decimal(str(data.get('meta_vendas_valor', 0))),
        meta_leads_qualificados=int(data.get('meta_leads_qualificados', 0)),
    )

    try:
        meta.data_inicio = date.fromisoformat(data['data_inicio'])
        meta.data_fim = date.fromisoformat(data['data_fim'])
    except (KeyError, ValueError):
        return JsonResponse({'ok': False, 'erro': 'Datas inválidas'}, status=400)

    if meta.tipo == 'individual' and data.get('vendedor_id'):
        meta.vendedor = get_object_or_404(User, pk=data['vendedor_id'])
    elif meta.tipo == 'equipe' and data.get('equipe_id'):
        meta.equipe = get_object_or_404(EquipeVendas, pk=data['equipe_id'])

    meta.save()
    return JsonResponse({'ok': True, 'id': meta.pk})


# ============================================================================
# RETENCAO
# ============================================================================

@login_required
def retencao_view(request):
    alertas = AlertaRetencao.objects.filter(
        status__in=['novo', 'em_tratamento']
    ).select_related('cliente_hubsoft', 'responsavel', 'lead').order_by('-score_churn')

    context = {
        'alertas': alertas,
        'alertas_criticos': alertas.filter(nivel_risco='critico'),
        'alertas_altos': alertas.filter(nivel_risco='alto'),
        'alertas_medios': alertas.filter(nivel_risco='medio'),
        'alertas_baixos': alertas.filter(nivel_risco='baixo'),
        'page_title': 'Retenção de Clientes',
    }
    return render(request, 'crm/retencao.html', context)


@login_required
@require_POST
def api_tratar_alerta(request, pk):
    alerta = get_object_or_404(AlertaRetencao, pk=pk)
    alerta.status = 'em_tratamento'
    alerta.responsavel = request.user
    alerta.save(update_fields=['status', 'responsavel'])
    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_resolver_alerta(request, pk):
    alerta = get_object_or_404(AlertaRetencao, pk=pk)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}

    alerta.status = 'resolvido'
    alerta.data_resolucao = timezone.now()
    alerta.acoes_tomadas = data.get('acoes_tomadas', '')
    alerta.save(update_fields=['status', 'data_resolucao', 'acoes_tomadas'])
    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_scanner_retencao(request):
    """Executa scan de churn risk nos clientes Hubsoft."""
    from django.utils import timezone as tz

    try:
        from apps.integracoes.models import ServicoClienteHubsoft, ClienteHubsoft
    except ImportError:
        return JsonResponse({'ok': False, 'erro': 'App integracoes não disponível'}, status=500)

    from datetime import date as date_type
    import re

    hoje = tz.now().date()
    criados = 0
    atualizados = 0

    # data_fim_contrato é CharField (ex: "2024-12-31" ou "31/12/2024")
    # Busca todos os serviços com data_fim_contrato preenchida e filtra em Python
    servicos = ServicoClienteHubsoft.objects.exclude(
        data_fim_contrato=''
    ).select_related('cliente')

    for servico in servicos:
        # Tenta parsear a data (aceita "YYYY-MM-DD" ou "DD/MM/YYYY")
        raw = servico.data_fim_contrato.strip()
        data_fim = None
        try:
            if re.match(r'\d{4}-\d{2}-\d{2}', raw):
                data_fim = date_type.fromisoformat(raw[:10])
            elif re.match(r'\d{2}/\d{2}/\d{4}', raw):
                from datetime import datetime
                data_fim = datetime.strptime(raw[:10], '%d/%m/%Y').date()
        except (ValueError, TypeError):
            continue

        if not data_fim or data_fim < hoje:
            continue

        dias_restantes = (data_fim - hoje).days

        if dias_restantes <= 30:
            nivel, score_base = 'critico', 90
        elif dias_restantes <= 60:
            nivel, score_base = 'alto', 70
        elif dias_restantes <= 90:
            nivel, score_base = 'medio', 50
        else:
            continue

        cliente = servico.cliente

        # Usa filter+first para evitar MultipleObjectsReturned
        alerta = AlertaRetencao.objects.filter(
            cliente_hubsoft=cliente,
            tipo_alerta='contrato_expirando',
            status__in=['novo', 'em_tratamento'],
        ).first()

        if alerta:
            atualizados += 1
        else:
            AlertaRetencao.objects.create(
                cliente_hubsoft=cliente,
                lead=cliente.lead,
                tipo_alerta='contrato_expirando',
                nivel_risco=nivel,
                score_churn=max(0, score_base - dias_restantes),
                descricao=f'Contrato expira em {dias_restantes} dias ({data_fim.strftime("%d/%m/%Y")})',
                data_expiracao_contrato=data_fim,
            )
            criados += 1

    return JsonResponse({'ok': True, 'criados': criados, 'atualizados': atualizados})


# ============================================================================
# SEGMENTOS
# ============================================================================

@login_required
def segmentos_lista(request):
    segmentos = SegmentoCRM.objects.filter(ativo=True).select_related('criado_por').order_by('nome')
    context = {
        'segmentos': segmentos,
        'page_title': 'Segmentos CRM',
    }
    return render(request, 'crm/segmentos_lista.html', context)


@login_required
def segmento_detalhe(request, pk):
    segmento = get_object_or_404(SegmentoCRM, pk=pk)
    membros = segmento.membros.select_related('lead', 'adicionado_por').order_by('-data_adicao')
    context = {
        'segmento': segmento,
        'membros': membros,
        'page_title': f'Segmento: {segmento.nome}',
    }
    return render(request, 'crm/segmento_detalhe.html', context)


# ============================================================================
# CONFIGURACOES CRM
# ============================================================================

@login_required
def configuracoes_crm(request):
    denied = _check_perm(request, 'comercial.configurar_pipeline')
    if denied: return denied
    from django.shortcuts import redirect

    if not request.user.is_superuser:
        return redirect('crm:pipeline')

    from .models import Pipeline

    config = ConfiguracaoCRM.get_config()
    pipelines = Pipeline.objects.all().order_by('ordem')

    # Pipeline selecionado para editar estágios
    pipeline_id = request.GET.get('pipeline')
    if pipeline_id:
        pipeline_atual = Pipeline.objects.filter(pk=pipeline_id).first()
    else:
        pipeline_atual = pipelines.first()

    if pipeline_atual:
        estagios = PipelineEstagio.objects.filter(pipeline=pipeline_atual).order_by('ordem')
    else:
        estagios = PipelineEstagio.objects.order_by('ordem')

    equipes = EquipeVendas.objects.filter(ativo=True)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'criar_pipeline':
            from django.utils.text import slugify
            nome = request.POST.get('nome', '').strip()
            tipo = request.POST.get('tipo', 'vendas')
            if nome:
                base_slug = slugify(nome)
                slug = base_slug
                counter = 1
                while Pipeline.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                Pipeline.objects.create(
                    nome=nome, slug=slug, tipo=tipo,
                    cor_hex=request.POST.get('cor_hex', '#667eea'),
                )
            return redirect('crm:configuracoes')

        elif action == 'editar_pipeline':
            pid = request.POST.get('pipeline_id')
            p = Pipeline.objects.filter(pk=pid).first()
            if p:
                p.nome = request.POST.get('nome', p.nome)
                p.tipo = request.POST.get('tipo', p.tipo)
                p.cor_hex = request.POST.get('cor_hex', p.cor_hex)
                p.padrao = request.POST.get('padrao') == 'on'
                p.save()
                # Se marcou como padrão, desmarcar os outros
                if p.padrao:
                    Pipeline.objects.exclude(pk=p.pk).update(padrao=False)
            return redirect(f'/crm/configuracoes/?pipeline={pid}')

        elif action == 'excluir_pipeline':
            pid = request.POST.get('pipeline_id')
            Pipeline.objects.filter(pk=pid).delete()
            return redirect('crm:configuracoes')

    context = {
        'config': config,
        'pipelines': pipelines,
        'pipeline_atual': pipeline_atual,
        'estagios': estagios,
        'equipes': equipes,
        'page_title': 'Configurações do CRM',
    }
    return render(request, 'crm/configuracoes_crm.html', context)


@login_required
@require_POST
def api_reordenar_estagios(request):
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'erro': 'Sem permissão'}, status=403)

    try:
        data = json.loads(request.body)
        ordem = data.get('ordem', [])
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    for i, estagio_id in enumerate(ordem):
        PipelineEstagio.objects.filter(pk=estagio_id).update(ordem=i + 1)

    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_salvar_config(request):
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'erro': 'Sem permissão'}, status=403)

    config = ConfiguracaoCRM.get_config()
    config.sla_alerta_horas_padrao = int(request.POST.get('sla_alerta_horas_padrao', 48))
    config.score_minimo_auto_criacao = int(request.POST.get('score_minimo_auto_criacao', 7))
    config.criar_oportunidade_automatico = bool(request.POST.get('criar_oportunidade_automatico'))
    config.notificar_responsavel_nova_oportunidade = bool(request.POST.get('notificar_responsavel_nova_oportunidade'))
    config.notificar_sla_breach = bool(request.POST.get('notificar_sla_breach'))
    estagio_id = request.POST.get('estagio_inicial_padrao_id')
    config.estagio_inicial_padrao = PipelineEstagio.objects.filter(pk=estagio_id).first() if estagio_id else None
    w1 = request.POST.get('webhook_n8n_nova_oportunidade', '').strip()
    w2 = request.POST.get('webhook_n8n_mudanca_estagio', '').strip()
    w3 = request.POST.get('webhook_n8n_tarefa_vencida', '').strip()
    config.webhook_n8n_nova_oportunidade = w1 or None
    config.webhook_n8n_mudanca_estagio = w2 or None
    config.webhook_n8n_tarefa_vencida = w3 or None
    config.save()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_criar_estagio(request):
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'erro': 'Sem permissão'}, status=403)

    estagio_id = request.POST.get('estagio_id')
    nome = request.POST.get('nome', '').strip()
    if not nome:
        return JsonResponse({'ok': False, 'erro': 'Nome obrigatório'}, status=400)

    from django.utils.text import slugify
    if estagio_id:
        est = get_object_or_404(PipelineEstagio, pk=estagio_id)
    else:
        est = PipelineEstagio()
        est.ordem = PipelineEstagio.objects.count() + 1

    # Associar ao pipeline
    pipeline_id = request.POST.get('pipeline_id')
    if pipeline_id:
        from .models import Pipeline
        est.pipeline_id = pipeline_id

    est.nome = nome
    base_slug = slugify(nome)
    slug = base_slug
    counter = 1
    qs = PipelineEstagio.objects.filter(pipeline_id=est.pipeline_id) if est.pipeline_id else PipelineEstagio.objects.all()
    while qs.filter(slug=slug).exclude(pk=est.pk if est.pk else None).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    est.slug = slug
    est.tipo = request.POST.get('tipo', 'qualificacao')
    est.cor_hex = request.POST.get('cor_hex', '#667eea')
    est.icone_fa = request.POST.get('icone_fa', 'fa-circle')
    sla = request.POST.get('sla_horas', '').strip()
    est.sla_horas = int(sla) if sla else None
    est.is_final_ganho = bool(request.POST.get('is_final_ganho'))
    est.is_final_perdido = bool(request.POST.get('is_final_perdido'))
    est.save()
    return JsonResponse({'ok': True, 'id': est.pk})


@login_required
@require_GET
def api_estagio_detalhe(request, pk):
    """Retorna dados de um estágio para preencher o modal de edição."""
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'erro': 'Sem permissão'}, status=403)
    est = get_object_or_404(PipelineEstagio, pk=pk)
    return JsonResponse({
        'ok': True,
        'estagio': {
            'pk': est.pk,
            'nome': est.nome,
            'tipo': est.tipo,
            'cor_hex': est.cor_hex,
            'icone_fa': est.icone_fa,
            'sla_horas': est.sla_horas or '',
            'is_final_ganho': est.is_final_ganho,
            'is_final_perdido': est.is_final_perdido,
            'ativo': est.ativo,
        }
    })


@login_required
@require_POST
def api_excluir_estagio(request, pk):
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'erro': 'Sem permissão'}, status=403)
    est = get_object_or_404(PipelineEstagio, pk=pk)
    # Não excluir se tiver oportunidades
    n = OportunidadeVenda.objects.filter(estagio=est).count()
    if n > 0:
        return JsonResponse({'ok': False, 'erro': f'Estágio possui {n} oportunidade(s). Mova-as antes de excluir.'})
    est.delete()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_criar_equipe(request):
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'erro': 'Sem permissão'}, status=403)

    equipe_id = request.POST.get('equipe_id')
    nome = request.POST.get('nome', '').strip()
    if not nome:
        return JsonResponse({'ok': False, 'erro': 'Nome obrigatório'}, status=400)

    if equipe_id:
        equipe = get_object_or_404(EquipeVendas, pk=equipe_id)
    else:
        equipe = EquipeVendas()

    equipe.nome = nome
    equipe.descricao = request.POST.get('descricao', '').strip()
    equipe.save()
    return JsonResponse({'ok': True, 'id': equipe.pk})


@login_required
def equipes_view(request):
    """Gerenciar equipes de vendas e seus membros."""
    denied = _check_perm(request, 'comercial.gerenciar_equipes')
    if denied: return denied
    from django.shortcuts import redirect
    from django.contrib.auth.models import User

    equipes = EquipeVendas.objects.prefetch_related('membros').all()
    usuarios = User.objects.filter(is_active=True, perfil__tenant=request.tenant).order_by('first_name')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'criar_equipe':
            nome = request.POST.get('nome', '').strip()
            if nome:
                EquipeVendas.objects.create(
                    nome=nome,
                    descricao=request.POST.get('descricao', '').strip(),
                    cor_hex=request.POST.get('cor_hex', '#667eea'),
                )
            return redirect('crm:equipes')

        elif action == 'editar_equipe':
            eid = request.POST.get('equipe_id')
            eq = EquipeVendas.objects.filter(pk=eid).first()
            if eq:
                eq.nome = request.POST.get('nome', eq.nome).strip()
                eq.descricao = request.POST.get('descricao', '').strip()
                eq.cor_hex = request.POST.get('cor_hex', eq.cor_hex)
                lider_id = request.POST.get('lider')
                eq.lider_id = lider_id if lider_id else None
                eq.save()
            return redirect('crm:equipes')

        elif action == 'excluir_equipe':
            eid = request.POST.get('equipe_id')
            EquipeVendas.objects.filter(pk=eid).delete()
            return redirect('crm:equipes')

        elif action == 'adicionar_membro':
            eid = request.POST.get('equipe_id')
            uid = request.POST.get('user_id')
            cargo = request.POST.get('cargo', 'vendedor')
            if eid and uid:
                eq = EquipeVendas.objects.filter(pk=eid).first()
                user = User.objects.filter(pk=uid).first()
                if eq and user:
                    PerfilVendedor.objects.get_or_create(
                        user=user,
                        defaults={'equipe': eq, 'cargo': cargo},
                    )
            return redirect('crm:equipes')

        elif action == 'remover_membro':
            membro_id = request.POST.get('membro_id')
            PerfilVendedor.objects.filter(pk=membro_id).delete()
            return redirect('crm:equipes')

    return render(request, 'crm/equipes.html', {
        'equipes': equipes,
        'usuarios': usuarios,
        'page_title': 'Equipes de Vendas',
    })


@login_required
@require_POST
def api_segmento_salvar(request):
    seg_id = request.POST.get('seg_id')
    nome = request.POST.get('nome', '').strip()
    if not nome:
        return JsonResponse({'ok': False, 'erro': 'Nome obrigatório'}, status=400)

    if seg_id:
        seg = get_object_or_404(SegmentoCRM, pk=seg_id)
    else:
        seg = SegmentoCRM(criado_por=request.user)

    seg.nome = nome
    seg.descricao = request.POST.get('descricao', '').strip()
    seg.tipo = request.POST.get('tipo', 'manual')
    seg.cor_hex = request.POST.get('cor_hex', '#764ba2')
    seg.icone_fa = request.POST.get('icone_fa', 'fa-users')

    # Regras dinâmicas
    regras_json = request.POST.get('regras_json', '')
    if regras_json:
        try:
            regras = json.loads(regras_json)
            seg.regras_filtro = {'regras': regras}
        except (json.JSONDecodeError, TypeError):
            pass

    seg.save()

    # Atualizar membros se dinâmico/híbrido
    if seg.tipo in ('dinamico', 'hibrido') and seg.regras_filtro.get('regras'):
        from .services.segmentos import atualizar_membros_segmento
        atualizar_membros_segmento(seg)

    return JsonResponse({'ok': True, 'id': seg.pk})


@login_required
def segmento_criar(request):
    """Página dedicada de criação de segmento."""
    return render(request, 'crm/segmento_criar.html', {'segmento': None})


@login_required
def segmento_editar(request, pk):
    """Página dedicada de edição de segmento."""
    segmento = get_object_or_404(SegmentoCRM, pk=pk)
    return render(request, 'crm/segmento_criar.html', {'segmento': segmento})


@login_required
@require_POST
def api_preview_regras(request):
    """Preview de leads que atendem as regras (sem salvar)."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'total': 0, 'leads': []})

    regras = data.get('regras', [])
    if not regras:
        return JsonResponse({'total': 0, 'leads': []})

    from .services.segmentos import filtrar_leads_por_regras
    qs = filtrar_leads_por_regras(regras)
    total = qs.count()

    # Novos (últimos 7 dias)
    from datetime import timedelta
    novos = qs.filter(data_cadastro__gte=timezone.now() - timedelta(days=7)).count()

    # Amostra
    leads = []
    for l in qs[:20]:
        leads.append({
            'id': l.pk,
            'nome': l.nome_razaosocial,
            'telefone': l.telefone or '',
            'origem': l.origem or '',
            'score': l.score_qualificacao or 0,
        })

    return JsonResponse({'total': total, 'novos': novos, 'leads': leads})


def _filtrar_leads_por_regras(regras):
    """Aplica regras de filtro a LeadProspecto e retorna queryset."""
    from apps.comercial.leads.models import LeadProspecto
    from django.db.models import Q
    from datetime import timedelta

    qs = LeadProspecto.objects.all()

    for r in regras:
        campo = r.get('campo', '')
        operador = r.get('operador', 'igual')
        valor = r.get('valor', '')

        if not campo or not valor:
            continue

        # Campos especiais
        if campo == 'dias_cadastro':
            try:
                dias = int(valor)
            except ValueError:
                continue
            data_limite = timezone.now() - timedelta(days=dias)
            if operador in ('maior', 'maior_igual'):
                qs = qs.filter(data_cadastro__lte=data_limite)
            elif operador in ('menor', 'menor_igual'):
                qs = qs.filter(data_cadastro__gte=data_limite)
            continue

        # Mapear campo para field do model
        field_map = {
            'origem': 'origem',
            'score_qualificacao': 'score_qualificacao',
            'cidade': 'cidade',
            'estado': 'estado',
            'bairro': 'bairro',
            'valor': 'valor',
            'status_api': 'status_api',
        }
        field = field_map.get(campo)
        if not field:
            continue

        # Aplicar operador
        if operador == 'igual':
            qs = qs.filter(**{f'{field}__iexact': valor})
        elif operador == 'diferente':
            qs = qs.exclude(**{f'{field}__iexact': valor})
        elif operador == 'contem':
            qs = qs.filter(**{f'{field}__icontains': valor})
        elif operador == 'maior':
            qs = qs.filter(**{f'{field}__gt': valor})
        elif operador == 'menor':
            qs = qs.filter(**{f'{field}__lt': valor})
        elif operador == 'maior_igual':
            qs = qs.filter(**{f'{field}__gte': valor})
        elif operador == 'menor_igual':
            qs = qs.filter(**{f'{field}__lte': valor})

    return qs


def _atualizar_membros_segmento(segmento):
    """Atualiza membros de um segmento dinâmico com base nas regras."""
    from .models import MembroSegmento

    regras = segmento.regras_filtro.get('regras', [])
    if not regras:
        return

    leads = _filtrar_leads_por_regras(regras)
    lead_ids = set(leads.values_list('pk', flat=True))

    # Remover quem não atende mais (exceto manuais)
    MembroSegmento.all_tenants.filter(
        segmento=segmento, adicionado_manualmente=False
    ).exclude(lead_id__in=lead_ids).delete()

    # Adicionar quem atende e não está
    existentes = set(segmento.membros.values_list('lead_id', flat=True))
    novos = lead_ids - existentes
    for lead_id in novos:
        MembroSegmento.objects.create(
            tenant=segmento.tenant, segmento=segmento,
            lead_id=lead_id, adicionado_manualmente=False,
        )

    segmento.total_leads = segmento.membros.count()
    segmento.ultima_atualizacao_dinamica = timezone.now()
    segmento.save(update_fields=['total_leads', 'ultima_atualizacao_dinamica'])


@login_required
@require_GET
def api_segmento_buscar_leads(request, pk):
    seg = get_object_or_404(SegmentoCRM, pk=pk)
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'leads': []})

    from apps.comercial.leads.models import LeadProspecto
    from django.db.models import Q
    existentes = seg.membros.values_list('lead_id', flat=True)
    leads = LeadProspecto.objects.filter(
        Q(nome_completo__icontains=q) | Q(telefone__icontains=q)
    ).exclude(pk__in=existentes)[:20]
    return JsonResponse({'leads': [{'pk': l.pk, 'nome': l.nome_completo, 'telefone': l.telefone or ''} for l in leads]})


@login_required
@require_POST
def api_segmento_adicionar_lead(request, pk):
    seg = get_object_or_404(SegmentoCRM, pk=pk)
    try:
        data = json.loads(request.body)
        lead_id = data.get('lead_id')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    from apps.comercial.leads.models import LeadProspecto
    from .models import MembroSegmento
    lead = get_object_or_404(LeadProspecto, pk=lead_id)
    _, created = MembroSegmento.objects.get_or_create(
        segmento=seg, lead=lead,
        defaults={'adicionado_manualmente': True, 'adicionado_por': request.user}
    )
    if created:
        seg.total_leads = seg.membros.count()
        seg.save(update_fields=['total_leads'])
    return JsonResponse({'ok': True, 'created': created})


@login_required
@require_POST
def api_segmento_remover_membro(request, pk):
    from .models import MembroSegmento
    try:
        data = json.loads(request.body)
        membro_id = data.get('membro_id')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    membro = get_object_or_404(MembroSegmento, pk=membro_id, segmento_id=pk)
    membro.delete()
    seg = get_object_or_404(SegmentoCRM, pk=pk)
    seg.total_leads = seg.membros.count()
    seg.save(update_fields=['total_leads'])
    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_segmento_disparar_campanha(request, pk):
    seg = get_object_or_404(SegmentoCRM, pk=pk)
    config = ConfiguracaoCRM.get_config()
    if not config.webhook_n8n_mudanca_estagio:
        return JsonResponse({'ok': False, 'erro': 'Webhook N8N não configurado'})

    import requests as req_lib
    leads = list(seg.membros.select_related('lead').values_list('lead__telefone', flat=True))
    try:
        req_lib.post(config.webhook_n8n_mudanca_estagio, json={
            'segmento': seg.nome, 'total': len(leads), 'leads': leads,
        }, timeout=5)
    except Exception:
        pass
    return JsonResponse({'ok': True, 'total': len(leads)})


@login_required
@require_POST
def api_meta_salvar(request):
    """Cria ou atualiza MetaVendas via FormData."""
    from django.contrib.auth.models import User as AuthUser
    from datetime import date as date_type

    meta_id = request.POST.get('meta_id')
    if meta_id:
        meta = get_object_or_404(MetaVendas, pk=meta_id)
    else:
        meta = MetaVendas(criado_por=request.user)

    meta.tipo = request.POST.get('tipo', 'individual')
    meta.periodo = request.POST.get('periodo', 'mensal')
    meta.meta_vendas_quantidade = int(request.POST.get('meta_vendas_quantidade') or 0)
    meta.meta_vendas_valor = Decimal(str(request.POST.get('meta_vendas_valor') or 0))
    meta.meta_leads_qualificados = int(request.POST.get('meta_leads_qualificados') or 0)

    try:
        meta.data_inicio = date_type.fromisoformat(request.POST['data_inicio'])
        meta.data_fim = date_type.fromisoformat(request.POST['data_fim'])
    except (KeyError, ValueError):
        return JsonResponse({'ok': False, 'erro': 'Datas inválidas'}, status=400)

    if meta.tipo == 'individual':
        vid = request.POST.get('vendedor_id')
        meta.vendedor = get_object_or_404(AuthUser, pk=vid) if vid else None
        meta.equipe = None
    else:
        eid = request.POST.get('equipe_id')
        meta.equipe = get_object_or_404(EquipeVendas, pk=eid) if eid else None
        meta.vendedor = None

    meta.save()
    return JsonResponse({'ok': True, 'id': meta.pk})


@login_required
@require_POST
def api_meta_excluir(request, pk):
    meta = get_object_or_404(MetaVendas, pk=pk)
    meta.delete()
    return JsonResponse({'ok': True})


# ============================================================================
# WEBHOOKS INBOUND
# ============================================================================

@csrf_exempt
@webhook_token_required
def webhook_hubsoft_contrato(request):
    """Recebe confirmação de contrato do Hubsoft e move oportunidade para Cliente Ativo.

    Requer header: Authorization: Bearer <WEBHOOK_SECRET_TOKEN>
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    contrato_id = data.get('contrato_id') or data.get('id_contrato')
    if not contrato_id:
        return JsonResponse({'ok': False, 'erro': 'contrato_id obrigatório'}, status=400)

    try:
        oportunidade = OportunidadeVenda.objects.get(contrato_hubsoft_id=str(contrato_id), ativo=True)
    except OportunidadeVenda.DoesNotExist:
        return JsonResponse({'ok': True, 'mensagem': 'Oportunidade não encontrada'})

    estagio_ativo = PipelineEstagio.objects.filter(is_final_ganho=True, ativo=True).first()
    if estagio_ativo and oportunidade.estagio != estagio_ativo:
        estagio_anterior = oportunidade.estagio
        horas = (timezone.now() - oportunidade.data_entrada_estagio).total_seconds() / 3600
        HistoricoPipelineEstagio.objects.create(
            oportunidade=oportunidade,
            estagio_anterior=estagio_anterior,
            estagio_novo=estagio_ativo,
            motivo='Confirmação automática via webhook Hubsoft',
            tempo_no_estagio_horas=round(horas, 2),
        )
        oportunidade.estagio = estagio_ativo
        oportunidade.data_entrada_estagio = timezone.now()
        oportunidade.data_fechamento_real = timezone.now()
        oportunidade.save(update_fields=['estagio', 'data_entrada_estagio', 'data_fechamento_real', 'data_atualizacao'])

    return JsonResponse({'ok': True})
