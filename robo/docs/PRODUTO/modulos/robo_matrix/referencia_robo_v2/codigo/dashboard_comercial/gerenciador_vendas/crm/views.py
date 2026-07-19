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

from .models import (
    PipelineEstagio, OportunidadeVenda, HistoricoPipelineEstagio,
    TarefaCRM, NotaInterna, MetaVendas, SegmentoCRM, AlertaRetencao,
    ConfiguracaoCRM, EquipeVendas, PerfilVendedor, RegraPipelineEstagio,
    TagCRM,
)
from vendas_web.rbac import requer_cap
from crm.services.indicacao_pipeline import (
    contrato_info as _contrato_info,
    mover_para_slug as _mover_para_slug,
    sincronizar_contrato_assinado as _sincronizar_contrato_assinado_indicacao,
    sincronizar_indicacao_pendentes as _sincronizar_contratos_indicacao_pendentes,
)

logger = logging.getLogger(__name__)


# ============================================================================
# HELPERS
# ============================================================================

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
        'tipo': op.tipo,
        'lead_id': lead.pk,
        'nome': (lead.nome_razaosocial or op.titulo or '')[:50],
        'telefone': lead.telefone,
        'email': lead.email or '',
        'valor': str(lead.valor or op.valor_estimado or 0),
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

def _pipeline_tipo_request(request):
    """Pipeline selecionado, RESPEITANDO as permissões do usuário.

    Cai no 1º pipeline que o usuário pode ver quando o pedido é inválido/negado.
    """
    from vendas_web.rbac import pipelines_visiveis
    permitidos = pipelines_visiveis(request.user)
    p = request.GET.get('pipeline')
    if p and p in permitidos:
        return p
    return permitidos[0] if permitidos else 'aquisicao'


def _escopo_oportunidades(request, qs):
    """Aplica o escopo de dados do perfil ao queryset de oportunidades.

    todos/pipeline → vê todas (do pipeline já filtrado); proprios → as suas + não
    atribuídas. Superuser vê tudo.
    """
    from vendas_web.rbac import escopo_do_usuario
    if request.user.is_superuser:
        return qs
    if escopo_do_usuario(request.user) in ('todos', 'pipeline'):
        return qs
    from django.db.models import Q
    return qs.filter(Q(responsavel=request.user) | Q(responsavel__isnull=True))


@login_required
def pipeline_view(request):
    pipeline_tipo = _pipeline_tipo_request(request)
    estagios = PipelineEstagio.objects.filter(
        ativo=True, pipeline_tipo=pipeline_tipo).order_by('ordem')
    vendedores = []
    from django.contrib.auth.models import User
    for u in User.objects.filter(is_active=True).order_by('first_name'):
        vendedores.append({'id': u.pk, 'nome': u.get_full_name() or u.username})

    # Planos ativos p/ o formulário de Nova Indicação/Wifeed (select).
    planos_ind = []
    if pipeline_tipo in ('indicacao', 'wifeed'):
        try:
            from vendas_web.models import PlanoInternet
            vistos = set()
            for p in PlanoInternet.objects.filter(ativo=True).order_by('valor_mensal'):
                ext = str(p.id_sistema_externo or '')
                if not ext.isdigit() or ext in vistos:
                    continue
                vistos.add(ext)
                planos_ind.append({'id_rp': int(ext),
                                   'label': f'{p.nome} — {p.get_valor_formatado()}'})
        except Exception:
            pass

    # Contagem nas abas = só oportunidades no PRIMEIRO estágio de cada
    # pipeline (menor `ordem`, ativo) — não o total do funil inteiro.
    _primeiro_estagio_id = {}
    for e in PipelineEstagio.objects.filter(ativo=True).order_by('pipeline_tipo', 'ordem'):
        _primeiro_estagio_id.setdefault(e.pipeline_tipo, e.pk)

    from django.db.models import Count as _Count
    _contagem_por_estagio = {r['estagio']: r['n'] for r in OportunidadeVenda.objects
                              .filter(ativo=True, estagio_id__in=_primeiro_estagio_id.values())
                              .values('estagio').annotate(n=_Count('id'))}
    pipelines_ctx = [
        {'valor': v, 'rotulo': r,
         'count': _contagem_por_estagio.get(_primeiro_estagio_id.get(v), 0)}
        for v, r in PipelineEstagio.PIPELINE_TIPO_CHOICES
    ]

    context = {
        'estagios': estagios,
        'vendedores': vendedores,
        'pipeline_tipo': pipeline_tipo,
        'pipelines': pipelines_ctx,
        'planos_ind': planos_ind,
        'vencimentos_ind': _vencimentos_ctx() if pipeline_tipo in ('indicacao', 'wifeed') else [],
        'page_title': 'Pipeline CRM',
    }
    return render(request, 'crm/pipeline.html', context)


@login_required
@require_GET
def api_pipeline_dados(request):
    pipeline_tipo = _pipeline_tipo_request(request)
    estagios = PipelineEstagio.objects.filter(
        ativo=True, pipeline_tipo=pipeline_tipo).order_by('ordem')

    # Filtros
    responsavel_id = request.GET.get('responsavel')
    prioridade = request.GET.get('prioridade')
    search = request.GET.get('search', '').strip()

    if pipeline_tipo == 'indicacao':
        _sincronizar_contratos_indicacao_pendentes(request.user)
    elif pipeline_tipo == 'wifeed':
        try:
            from crm.services.wifeed_pipeline import sincronizar_wifeed_pendentes
            sincronizar_wifeed_pendentes(request.user)
        except Exception as e:  # noqa: BLE001
            logger.warning('Falha ao sincronizar wifeed pendentes: %s', e)

    qs = OportunidadeVenda.objects.filter(ativo=True, tipo=pipeline_tipo).select_related(
        'lead', 'estagio', 'responsavel', 'plano_interesse'
    ).prefetch_related('tarefas', 'tags')

    # Regra de visibilidade: escopo de dados do perfil (todos / pipeline / proprios)
    qs = _escopo_oportunidades(request, qs)

    if responsavel_id:
        qs = qs.filter(responsavel_id=responsavel_id)
    if prioridade:
        qs = qs.filter(prioridade=prioridade)
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
@requer_cap('operar_mover_oportunidade')
def api_mover_oportunidade(request):
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

    # Indicação: ao puxar Indicação Recebida → Completando Dados, o operador
    # que arrastou assume a oportunidade (só se ainda estiver sem responsável).
    if (
        (estagio_anterior.slug, estagio_novo.slug) in (('ind_recebida', 'ind_dados'),
                                                       ('wf_recebida', 'wf_dados'))
        and oportunidade.responsavel_id is None
    ):
        oportunidade.responsavel = request.user
        campos.append('responsavel')

    if estagio_novo.is_final_ganho and not oportunidade.data_fechamento_real:
        oportunidade.data_fechamento_real = timezone.now()
        campos.append('data_fechamento_real')
        _atualizar_meta_venda(oportunidade, request.user)

    oportunidade.save(update_fields=campos)

    # Tags da nova etapa (pós-venda / indicação). Aditivo e no-op p/ aquisição.
    try:
        from crm.services.posvenda_sync import aplicar_tags_etapa
        aplicar_tags_etapa(oportunidade, estagio_novo.slug)
    except Exception as e:
        logger.warning('Falha ao aplicar tags (drag estagio=%s): %s', estagio_novo.slug, e)

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

_COR_PIPELINE = {
    'aquisicao': '#0022fa',
    'novo_servico': '#059669',
    'upgrade': '#f59e0b',
    'atendimento': '#0ea5e9',
    'indicacao': '#7c3aed',
    'wifeed': '#06b6d4',
}

_ROTULO_CURTO_PIPELINE = {
    'aquisicao': 'Aquisição',
    'novo_servico': 'Novo Serviço',
    'upgrade': 'Upgrade',
    'atendimento': 'Atendimento',
    'indicacao': 'Indicação',
    'wifeed': 'Wifeed',
}


@login_required
def oportunidades_lista(request):
    qs = OportunidadeVenda.objects.filter(ativo=True).select_related(
        'lead', 'estagio', 'responsavel'
    ).order_by('estagio__pipeline_tipo', 'estagio__ordem', '-data_criacao')

    if not request.user.is_superuser:
        from django.db.models import Q
        qs = qs.filter(Q(responsavel=request.user) | Q(responsavel__isnull=True))

    estagios = list(PipelineEstagio.objects.filter(ativo=True).order_by('pipeline_tipo', 'ordem'))
    for e in estagios:
        e.rotulo_curto_pipeline = _ROTULO_CURTO_PIPELINE.get(e.pipeline_tipo, e.pipeline_tipo)

    # Cards de resumo AGRUPADOS POR PIPELINE. Vários pipelines reaproveitam
    # nomes de estágio iguais (ex: "Coletando Dados" em novo_servico e
    # upgrade; "Falha"/"Concluído"/"Perdido" também se repetem) — sem
    # agrupar por pipeline não dá pra saber qual estágio é qual só olhando.
    # Contagem via aggregate (não via `regroup` do template): `regroup`
    # exige a lista pré-ordenada pelo MESMO campo pra não fragmentar um
    # único estágio em vários grupos — e `ordem` se repete entre pipelines
    # diferentes (pipeline A e B podem ter os dois um estágio com ordem=1),
    # o que fazia o mesmo estágio aparecer picotado em cards duplicados.
    #
    # `.order_by()` (limpa a ordenação) ANTES do aggregate é obrigatório:
    # o `qs` tem `order_by(...,'-data_criacao')` pra tabela, e o Django
    # inclui campos de `order_by()` explícito no GROUP BY do `.values()`
    # — sem isso, `data_criacao` (praticamente único por linha) vira parte
    # do agrupamento e cada oportunidade sai como grupo próprio (n=1),
    # fazendo o total ficar bem menor que o real.
    from django.db.models import Count as _Count
    contagem_estagio = {r['estagio']: r['n']
                        for r in qs.order_by().values('estagio').annotate(n=_Count('id'))}

    resumo_por_pipeline = []
    for tipo_valor, tipo_rotulo in PipelineEstagio.PIPELINE_TIPO_CHOICES:
        cards = [
            {'estagio': e, 'count': contagem_estagio[e.pk]}
            for e in estagios if e.pipeline_tipo == tipo_valor and contagem_estagio.get(e.pk)
        ]
        if cards:
            resumo_por_pipeline.append({
                'valor': tipo_valor,
                'rotulo': tipo_rotulo,
                'cor': _COR_PIPELINE.get(tipo_valor, '#6b7280'),
                'total': sum(c['count'] for c in cards),
                'cards': cards,
            })

    context = {
        'oportunidades': qs,
        'estagios': estagios,
        'resumo_por_pipeline': resumo_por_pipeline,
        'total_oportunidades': sum(g['total'] for g in resumo_por_pipeline),
        'page_title': 'Oportunidades',
    }
    return render(request, 'crm/oportunidades_lista.html', context)


def _montar_timeline_oportunidade(historico_contatos, historico_estagios, historico_status):
    """Mescla contatos, estágios e mudanças de status_api em ordem decrescente."""
    itens = []
    for hc in historico_contatos:
        itens.append({'tipo': 'contato', 'data': hc.data_hora_contato, 'obj': hc})
    for he in historico_estagios:
        itens.append({'tipo': 'estagio', 'data': he.data_transicao, 'obj': he})
    for hs in historico_status:
        itens.append({'tipo': 'status', 'data': hs.data_alteracao, 'obj': hs})
    itens.sort(key=lambda row: row['data'], reverse=True)
    return itens


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
    from vendas_web.models import HistoricoContato, HistoricoStatusLead
    historico_contatos = HistoricoContato.objects.filter(lead=lead).order_by('-data_hora_contato')[:20]
    historico_status = HistoricoStatusLead.objects.filter(
        lead=lead
    ).select_related('alterado_por').order_by('-data_alteracao')[:50]

    try:
        from integracoes.models import ClienteHubsoft
        cliente_hubsoft = ClienteHubsoft.objects.filter(lead=lead).prefetch_related('servicos').first()
    except Exception:
        cliente_hubsoft = None

    historico_estagios = HistoricoPipelineEstagio.objects.filter(
        oportunidade=oportunidade
    ).select_related('estagio_anterior', 'estagio_novo', 'movido_por').order_by('-data_transicao')

    timeline_itens = _montar_timeline_oportunidade(
        list(historico_contatos),
        list(historico_estagios),
        list(historico_status),
    )

    estagios = PipelineEstagio.objects.filter(ativo=True).order_by('ordem')

    from django.contrib.auth.models import User
    vendedores = User.objects.filter(is_active=True).order_by('first_name')

    # Planos ativos p/ o select do form de indicação (só quando relevante).
    planos_ind = []
    if oportunidade.tipo in ('indicacao', 'wifeed'):
        try:
            from vendas_web.models import PlanoInternet
            vistos = set()
            for p in PlanoInternet.objects.filter(ativo=True).order_by('valor_mensal'):
                ext = str(p.id_sistema_externo or '')
                if not ext.isdigit() or ext in vistos:
                    continue
                vistos.add(ext)
                planos_ind.append({'id_rp': int(ext),
                                   'label': f'{p.nome} — {p.get_valor_formatado()}'})
        except Exception:
            pass

    # Mensagem inicial de WhatsApp do pipeline (placeholders resolvidos).
    wa_mensagem = ''
    try:
        from crm.models import MensagemPipeline
        mp = MensagemPipeline.objects.filter(pipeline_tipo=oportunidade.tipo, ativo=True).first()
        if mp and mp.mensagem:
            nome = (lead.nome_razaosocial or '').strip()
            primeiro = nome.split(' ')[0] if nome else ''
            wa_mensagem = mp.mensagem.replace('{primeiro_nome}', primeiro).replace('{nome}', nome)
    except Exception:
        pass

    context = {
        'oportunidade': oportunidade,
        'lead': lead,
        'historico_contatos': historico_contatos,
        'historico_status': historico_status,
        'cliente_hubsoft': cliente_hubsoft,
        'historico_estagios': historico_estagios,
        'timeline_itens': timeline_itens,
        'timeline_total': len(timeline_itens),
        'estagios': estagios,
        'vendedores': vendedores,
        'planos_ind': planos_ind,
        'vencimentos_ind': _vencimentos_ctx() if oportunidade.tipo in ('indicacao', 'wifeed') else [],
        'wa_mensagem': wa_mensagem,
        'page_title': f'CRM — {lead.nome_razaosocial or oportunidade.titulo}',
    }
    return render(request, 'crm/oportunidade_detalhe.html', context)


@login_required
@require_POST
@requer_cap('operar_atribuir')
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
    # Notifica o responsável atribuído (exceto se ele mesmo se atribuiu).
    if oportunidade.responsavel and oportunidade.responsavel != request.user:
        try:
            from vendas_web.notificacoes_service import notificar
            titulo_op = oportunidade.titulo or (oportunidade.lead.nome_razaosocial if oportunidade.lead else '')
            notificar('atribuicao', 'Oportunidade atribuída a você',
                      f'Você é o responsável por "{titulo_op}".',
                      [oportunidade.responsavel],
                      contexto={'oportunidade_id': oportunidade.id,
                                'url': f'/crm/oportunidades/{oportunidade.id}/'},
                      prioridade='alta')
        except Exception:  # noqa: BLE001
            pass
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
    qs = TarefaCRM.objects.filter(
        responsavel=request.user
    ).select_related('lead', 'oportunidade', 'criado_por').order_by('data_vencimento')

    hoje = timezone.now().date()
    tarefas_hoje = qs.filter(data_vencimento__date=hoje, status__in=['pendente', 'em_andamento'])
    tarefas_semana = qs.filter(
        data_vencimento__date__gt=hoje,
        data_vencimento__date__lte=hoje + timezone.timedelta(days=7),
        status__in=['pendente', 'em_andamento']
    )
    tarefas_vencidas = qs.filter(data_vencimento__lt=timezone.now(), status__in=['pendente', 'em_andamento', 'vencida'])
    tarefas_todas = qs.exclude(status='concluida')

    context = {
        'tarefas_hoje': tarefas_hoje,
        'tarefas_semana': tarefas_semana,
        'tarefas_vencidas': tarefas_vencidas,
        'tarefas_todas': tarefas_todas,
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
        from vendas_web.models import LeadProspecto
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
        from vendas_web.models import LeadProspecto
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
    from django.contrib.auth.models import User
    hoje = timezone.now().date()
    mes_inicio = hoje.replace(day=1)

    vendedores = User.objects.filter(is_active=True).order_by('first_name')
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
    for u in User.objects.filter(is_active=True):
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
    hoje = timezone.now().date()
    metas_ativas = MetaVendas.objects.filter(
        data_inicio__lte=hoje, data_fim__gte=hoje
    ).select_related('vendedor', 'equipe').order_by('-data_inicio')

    from django.contrib.auth.models import User
    vendedores = User.objects.filter(is_active=True).order_by('first_name')
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
        from integracoes.models import ServicoClienteHubsoft, ClienteHubsoft
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
    if not request.user.is_superuser:
        from django.shortcuts import redirect
        return redirect('crm:pipeline')

    config = ConfiguracaoCRM.get_config()
    estagios = PipelineEstagio.objects.order_by('ordem')
    equipes = EquipeVendas.objects.filter(ativo=True)

    context = {
        'config': config,
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

    est.nome = nome
    est.slug = slugify(nome)
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
    regras = [
        {
            'pk': r.pk,
            'nome': r.nome,
            'condicoes': r.condicoes,
            'ativo': r.ativo,
            'prioridade': r.prioridade,
        }
        for r in est.regras.filter(ativo=True).order_by('prioridade')
    ]
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
            'regras': regras,
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
@require_POST
def api_segmento_salvar(request):
    from django.utils.text import slugify as _slugify
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
    seg.save()
    return JsonResponse({'ok': True, 'id': seg.pk})


@login_required
@require_GET
def api_segmento_buscar_leads(request, pk):
    seg = get_object_or_404(SegmentoCRM, pk=pk)
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'leads': []})

    from vendas_web.models import LeadProspecto
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

    from vendas_web.models import LeadProspecto
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
def webhook_hubsoft_contrato(request):
    """Recebe confirmação de contrato do Hubsoft e move oportunidade para Cliente Ativo."""
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

    lead = oportunidade.lead
    if lead:
        try:
            from integracoes.services.clube_indicacoes import notificar_clube_contrato_aceito_indicacao
            notificar_clube_contrato_aceito_indicacao(lead)
        except Exception as e:  # noqa: BLE001
            logger.warning('Webhook HubSoft contrato → Clube falhou lead %s: %s', lead.pk, e)

    return JsonResponse({'ok': True})


# ============================================================================
# DOCUMENTAÇÃO CRM
# ============================================================================

@login_required
def documentacao_crm(request):
    """Página de documentação do sistema de regras e APIs do CRM."""
    from vendas_web.models import LeadProspecto, HistoricoContato
    context = {
        'status_historico': HistoricoContato.STATUS_CHOICES,
        'status_lead': LeadProspecto.STATUS_API_CHOICES,
        'estagios': PipelineEstagio.objects.filter(ativo=True).order_by('ordem'),
        'regras': RegraPipelineEstagio.objects.filter(ativo=True).select_related('estagio').order_by('estagio__ordem', 'prioridade'),
        'tags': TagCRM.objects.all().order_by('nome'),
    }
    return render(request, 'crm/documentacao_crm.html', context)


# ============================================================================
# REGRAS DE PIPELINE (CRUD)
# ============================================================================

@login_required
@require_GET
def api_regras_estagio(request, estagio_pk):
    """Retorna todas as regras de um estágio."""
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'erro': 'Sem permissão'}, status=403)

    estagio = get_object_or_404(PipelineEstagio, pk=estagio_pk)
    regras = [
        {
            'pk': r.pk,
            'nome': r.nome,
            'condicoes': r.condicoes,
            'ativo': r.ativo,
            'prioridade': r.prioridade,
        }
        for r in estagio.regras.order_by('prioridade')
    ]
    return JsonResponse({'ok': True, 'regras': regras})


@login_required
@require_POST
def api_regra_salvar(request):
    """Cria ou edita uma regra de pipeline."""
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'erro': 'Sem permissão'}, status=403)

    try:
        dados = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    estagio_id = dados.get('estagio_id')
    regra_id = dados.get('regra_id')
    nome = (dados.get('nome') or '').strip()
    condicoes = dados.get('condicoes', [])
    ativo = dados.get('ativo', True)
    prioridade = dados.get('prioridade', 0)

    if not estagio_id:
        return JsonResponse({'ok': False, 'erro': 'estagio_id obrigatório'}, status=400)
    if not nome:
        return JsonResponse({'ok': False, 'erro': 'Nome da regra obrigatório'}, status=400)
    if not condicoes:
        return JsonResponse({'ok': False, 'erro': 'Pelo menos uma condição é obrigatória'}, status=400)

    estagio = get_object_or_404(PipelineEstagio, pk=estagio_id)

    if regra_id:
        regra = get_object_or_404(RegraPipelineEstagio, pk=regra_id, estagio=estagio)
    else:
        regra = RegraPipelineEstagio(estagio=estagio)

    regra.nome = nome
    regra.condicoes = condicoes
    regra.ativo = ativo
    regra.prioridade = prioridade
    regra.save()

    return JsonResponse({'ok': True, 'regra_id': regra.pk})


@login_required
@require_POST
def api_regra_excluir(request, pk):
    """Exclui uma regra de pipeline."""
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'erro': 'Sem permissão'}, status=403)

    regra = get_object_or_404(RegraPipelineEstagio, pk=pk)
    regra.delete()
    return JsonResponse({'ok': True})


@login_required
@require_GET
def api_regras_opcoes(request):
    """
    Retorna tipos de condição, operadores e valores disponíveis
    para o builder de regras na UI.
    """
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'erro': 'Sem permissão'}, status=403)

    from vendas_web.models import LeadProspecto, HistoricoContato
    from integracoes.models import ServicoClienteHubsoft

    # Status do HistoricoContato
    historico_valores = [
        {'value': code, 'label': label}
        for code, label in HistoricoContato.STATUS_CHOICES
    ]

    # Status API do Lead — usa StatusConfiguravel como fonte principal (dinâmico)
    # com fallback para STATUS_API_CHOICES hardcoded
    from vendas_web.models import StatusConfiguravel
    status_configuravel_qs = StatusConfiguravel.objects.filter(
        grupo='lead_status_api', ativo=True
    ).order_by('ordem')

    if status_configuravel_qs.exists():
        # Merge: StatusConfiguravel + hardcoded (sem duplicatas)
        codigos_vistos = set()
        lead_status_valores = []
        for s in status_configuravel_qs:
            lead_status_valores.append({'value': s.codigo, 'label': s.rotulo})
            codigos_vistos.add(s.codigo)
        # Adicionar do hardcoded que não estão no StatusConfiguravel
        for code, label in LeadProspecto.STATUS_API_CHOICES:
            if code not in codigos_vistos:
                lead_status_valores.append({'value': code, 'label': label})
    else:
        lead_status_valores = [
            {'value': code, 'label': label}
            for code, label in LeadProspecto.STATUS_API_CHOICES
        ]

    # Campos booleanos do Lead
    lead_campos = [
        {'value': 'documentacao_validada', 'label': 'Documentação Validada', 'tipo_campo': 'boolean'},
        {'value': 'documentacao_completa', 'label': 'Documentação Completa', 'tipo_campo': 'boolean'},
        {'value': 'contrato_aceito', 'label': 'Contrato Aceito', 'tipo_campo': 'boolean'},
    ]

    # Status de serviço Hubsoft (valores distintos do banco)
    servico_valores_db = list(
        ServicoClienteHubsoft.objects
        .exclude(status_prefixo='')
        .values_list('status_prefixo', flat=True)
        .distinct()
        .order_by('status_prefixo')
    )
    servico_valores = [
        {'value': s, 'label': s.replace('_', ' ').title()}
        for s in servico_valores_db
    ]

    # Tags CRM
    tag_valores = [
        {'value': t.nome, 'label': t.nome}
        for t in TagCRM.objects.all().order_by('nome')
    ]

    tipos_condicao = [
        {
            'value': 'historico_status',
            'label': 'Status do Histórico de Contato',
            'valores': historico_valores,
        },
        {
            'value': 'lead_status_api',
            'label': 'Status API do Lead',
            'valores': lead_status_valores,
        },
        {
            'value': 'lead_campo',
            'label': 'Campo do Lead',
            'campos': lead_campos,
        },
        {
            'value': 'servico_status',
            'label': 'Status do Serviço Hubsoft',
            'valores': servico_valores,
        },
        {
            'value': 'tag',
            'label': 'Tag CRM',
            'valores': tag_valores,
        },
        {
            'value': 'converteu_venda',
            'label': 'Converteu em Venda',
            'tipo_campo': 'boolean',
        },
        {
            'value': 'imagem_status',
            'label': 'Status de Documentos/Imagens',
            'valores': [
                {'value': 'pendente', 'label': 'Pendente'},
                {'value': 'documentos_validos', 'label': 'Documentos Válidos'},
                {'value': 'documentos_rejeitados', 'label': 'Documentos Rejeitados'},
            ],
        },
    ]

    operadores = [
        {'value': 'igual', 'label': 'Igual a'},
        {'value': 'diferente', 'label': 'Diferente de'},
        {'value': 'todas_iguais', 'label': 'Todas iguais a (imagens)'},
        {'value': 'nenhuma_com', 'label': 'Nenhuma com (imagens)'},
        {'value': 'existe', 'label': 'Existe / Verdadeiro'},
        {'value': 'nao_existe', 'label': 'Não existe / Falso'},
    ]

    return JsonResponse({
        'ok': True,
        'tipos_condicao': tipos_condicao,
        'operadores': operadores,
    })


# ============================================================================
# PIPELINE DE INDICAÇÕES (operado por pessoas)
# ============================================================================

# Campos do lead que o operador pode preencher/editar pela tela de indicação.
_CAMPOS_LEAD_EDITAVEIS = [
    'nome_razaosocial', 'cpf_cnpj', 'email', 'rg', 'data_nascimento',
    'cep', 'rua', 'numero_residencia', 'bairro', 'cidade', 'estado',
    'ponto_referencia', 'tipo_imovel', 'tipo_residencia', 'observacoes',
    'id_plano_rp', 'id_dia_vencimento', 'turno_instalacao', 'data_instalacao',
    'id_indicador',
]
_CAMPOS_INT = {'id_plano_rp', 'id_dia_vencimento'}
# Mínimo p/ o lead virar prospecto/cliente (senão a API do HubSoft recusa).
_CAMPOS_MIN_CONVERSAO = ['nome_razaosocial', 'cpf_cnpj', 'telefone', 'cep',
                         'rua', 'numero_residencia', 'bairro', 'cidade',
                         'data_nascimento', 'id_plano_rp', 'id_dia_vencimento']
# id_vencimento do HubSoft → dia do mês. O lead.id_dia_vencimento guarda o ID do
# HubSoft (não o dia). Fonte: regra ia_validador 'dia_vencimento'
# (28→dia 1, 9→dia 5, 5→dia 15, 6→dia 20). A API recusa qualquer outro valor.
VENCIMENTOS_HUBSOFT = [(28, 1), (9, 5), (5, 15), (6, 20)]
_VENCIMENTOS_VALIDOS = {v[0] for v in VENCIMENTOS_HUBSOFT}


def _vencimentos_ctx():
    return [{'id': i, 'dia': d} for i, d in VENCIMENTOS_HUBSOFT]


def _coerce_lead(campo, valor):
    """Normaliza valores do formulário p/ o tipo do campo do lead."""
    if valor in (None, ''):
        return None if campo in _CAMPOS_INT or campo in ('data_instalacao', 'data_nascimento') else ''
    if campo in _CAMPOS_INT:
        try:
            return int(valor)
        except (TypeError, ValueError):
            return None
    return valor


def _aplicar_campos_lead(lead, data):
    """Seta os campos editáveis presentes no payload. Retorna lista alterada."""
    alterados = []
    for c in _CAMPOS_LEAD_EDITAVEIS:
        if c in data:
            setattr(lead, c, _coerce_lead(c, data.get(c)))
            alterados.append(c)
    # Nome digitado por OPERADOR conta como confirmado (push name não conta —
    # ver LeadProspecto.nome_confirmado / robô sempre pergunta o nome completo).
    if 'nome_razaosocial' in alterados and (lead.nome_razaosocial or '').strip():
        lead.nome_confirmado = True
        alterados.append('nome_confirmado')
    return alterados


def _notificar_indicacao(tipo, titulo, mensagem, op, prioridade='normal', chave=None):
    """Notifica os operadores do pipeline de Indicação sobre um marco da oportunidade."""
    try:
        from vendas_web.notificacoes_service import notificar_por_capacidade
        notificar_por_capacidade(
            'ver_pipeline_indicacao', tipo, titulo, mensagem,
            contexto={'oportunidade_id': op.id, 'url': f'/crm/oportunidades/{op.id}/'},
            prioridade=prioridade, chave=chave)
    except Exception:  # noqa: BLE001
        pass


def _notificar_alerta(tipo, titulo, mensagem, op=None):
    """Alerta/exceção → notifica gerentes/admins (quem tem ver_desempenho)."""
    try:
        from vendas_web.notificacoes_service import notificar_por_capacidade
        ctx = {'oportunidade_id': op.id, 'url': f'/crm/oportunidades/{op.id}/'} if op else {}
        notificar_por_capacidade('ver_desempenho', tipo, titulo, mensagem,
                                 contexto=ctx, prioridade='urgente')
    except Exception:  # noqa: BLE001
        pass


@login_required
@require_GET
def api_indicacao_contrato_status(request):
    """Estado do contrato do cliente convertido (monitoramento p/ o operador)."""
    from crm.services.indicacao_pipeline import sincronizar_oportunidade_indicacao
    op = get_object_or_404(OportunidadeVenda, pk=request.GET.get('oportunidade_id'), ativo=True)
    contrato = _contrato_info(op.lead)
    movido = sincronizar_oportunidade_indicacao(op, request.user)
    if movido:
        op.refresh_from_db()
    return JsonResponse({
        'ok': True,
        'contrato': contrato,
        'movido': movido,
        'oportunidade': _oportunidade_para_dict(op),
    })


def criar_lead_indicacao(data):
    """Cria lead de indicação no funil CRM (signal gera a oportunidade).

    Raises ValueError se nome ou telefone estiverem ausentes.
    Retorna (lead, oportunidade|None).
    """
    from vendas_web.models import LeadProspecto

    nome = (data.get('nome_razaosocial') or '').strip()
    telefone = (data.get('telefone') or '').strip()
    if not nome or not telefone:
        raise ValueError('Nome e telefone são obrigatórios')

    campos = {
        'nome_razaosocial': nome, 'telefone': telefone,
        'canal_entrada': 'indicacao', 'origem': 'indicacao',
        'tipo_entrada': 'formulario', 'status_api': 'indicacao',
        'id_indicador': (data.get('id_indicador') or '').strip(),
    }
    for c in _CAMPOS_LEAD_EDITAVEIS:
        if c in data and c not in campos:
            v = _coerce_lead(c, data.get(c))
            if v not in (None, ''):
                campos[c] = v
    lead = LeadProspecto.objects.create(**campos)
    op = OportunidadeVenda.objects.filter(lead=lead, tipo='indicacao').first()
    return lead, op


@login_required
@require_POST
@requer_cap('operar_indicacao')
def api_indicacao_criar(request):
    """Cria manualmente um lead de INDICAÇÃO. O signal cria a oportunidade no
    funil de indicações. NÃO cria prospecto (status_api='indicacao' ≠ 'pendente')."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    try:
        lead, op = criar_lead_indicacao(data)
    except ValueError as e:
        return JsonResponse({'ok': False, 'erro': str(e)}, status=400)

    return JsonResponse({'ok': True, 'lead_id': lead.id,
                         'oportunidade_id': op.id if op else None})


@login_required
@require_POST
@requer_cap('operar_editar_lead')
def api_lead_editar(request):
    """Preenche/atualiza os dados do lead de uma oportunidade (form editável)."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)
    op = get_object_or_404(OportunidadeVenda, pk=data.get('oportunidade_id'), ativo=True)
    if not request.user.is_superuser and op.responsavel and op.responsavel != request.user:
        return JsonResponse({'ok': False, 'erro': 'Sem permissão'}, status=403)
    lead = op.lead
    if 'telefone' in data and (data.get('telefone') or '').strip():
        lead.telefone = data['telefone'].strip()
    alterados = _aplicar_campos_lead(lead, data)
    lead.save()
    return JsonResponse({'ok': True, 'campos_alterados': alterados})


@login_required
@require_POST
@requer_cap('operar_indicacao')
def api_indicacao_converter(request):
    """Torna o lead de indicação em prospecto → cliente (backend existente).

    Exige dados mínimos completos. Cria o prospecto (status_api='pendente' dispara
    HubsoftService.cadastrar_prospecto) e roda a conversão prospecto→cliente."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)
    op = get_object_or_404(OportunidadeVenda, pk=data.get('oportunidade_id'), ativo=True)
    lead = op.lead

    faltando = [c for c in _CAMPOS_MIN_CONVERSAO if not getattr(lead, c, None)]
    if faltando:
        return JsonResponse({'ok': False, 'erro': 'Dados incompletos para conversão',
                             'faltando': faltando}, status=400)
    if lead.id_dia_vencimento not in _VENCIMENTOS_VALIDOS:
        return JsonResponse({'ok': False, 'faltando': ['id_dia_vencimento'],
                             'erro': 'Dia de vencimento inválido — escolha 1, 5, 15 ou 20.'},
                            status=400)

    # 1) prospecto — o signal enviar_lead_pendente_para_hubsoft cria ao ver 'pendente'
    if not lead.id_hubsoft:
        lead.status_api = 'pendente'
        lead.save(update_fields=['status_api', 'data_atualizacao'])
        lead.refresh_from_db()
    if not lead.id_hubsoft:
        return JsonResponse({'ok': False,
                             'erro': 'Não foi possível criar o prospecto no HubSoft'}, status=502)

    # 2) conversão prospecto → cliente (executor por API)
    from posvenda_hubsoft.executores.seletor import processar
    res = processar('conversao', lead.id, dry_run=False)
    if getattr(res, 'status', None) == 'sucesso':
        _mover_para_slug(op, 'ind_apto', request.user, 'Convertido em cliente — aguardando assinatura do contrato')
        _notificar_indicacao('indicacao_convertida', 'Indicação convertida em cliente',
                             f'{lead.nome_razaosocial or "Cliente"} foi convertido no HubSoft. '
                             f'Aguardando assinatura do contrato para abrir atendimento/O.S.',
                             op, prioridade='alta', chave=f'ind_conv_{op.id}')
        from integracoes.services.clube_indicacoes import notificar_clube_conversao_indicacao
        notificar_clube_conversao_indicacao(lead, valor_venda=getattr(lead, 'valor', None))
        return JsonResponse({'ok': True, 'status': 'cliente_criado',
                             'id_hubsoft': lead.id_hubsoft,
                             'oportunidade': _oportunidade_para_dict(op)})
    # prospecto existe; a conversão pode ser retomada pelo worker de conversão
    _notificar_alerta('indicacao_falha_conversao', 'Falha ao converter indicação',
                      f'A conversão de {lead.nome_razaosocial or "um lead"} não concluiu: '
                      f'{(getattr(res, "erro", "") or "")[:120]}', op)
    return JsonResponse({'ok': False, 'status': getattr(res, 'status', 'falha'),
                         'id_hubsoft': lead.id_hubsoft,
                         'erro': (getattr(res, 'erro', '') or
                                  'Conversão não concluída — o worker tentará novamente')},
                        status=202)


@login_required
@require_POST
@requer_cap('operar_indicacao')
def api_indicacao_agendar(request):
    """Abre atendimento + O.S. (Matrix) p/ o lead já convertido em cliente."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)
    op = get_object_or_404(OportunidadeVenda, pk=data.get('oportunidade_id'), ativo=True)
    lead = op.lead

    # GATE: só abre atendimento/O.S. se o contrato já estiver ACEITO pelo cliente
    # (o aceite é feito pelo próprio cliente no app; aqui só monitoramos).
    contrato = _contrato_info(lead)
    if not contrato['aceito']:
        return JsonResponse({'ok': False, 'contrato': contrato,
                             'erro': 'O contrato ainda não foi aceito pelo cliente. '
                                     'Abra o atendimento e a O.S. somente após o aceite.'},
                            status=409)

    turno = (data.get('turno') or '').strip()
    data_inst = (data.get('data_instalacao') or '').strip()
    if turno not in ('manha', 'tarde') or not data_inst:
        return JsonResponse({'ok': False, 'erro': 'Informe turno (manha/tarde) e data'}, status=400)

    # Converte a data (string 'YYYY-MM-DD' do form) para um objeto date — o
    # executar_agendamento faz data_instalacao.strftime(...), que quebra com string.
    from datetime import datetime as _dt
    try:
        data_obj = _dt.strptime(data_inst, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'ok': False, 'erro': 'Data inválida (use o seletor).'}, status=400)

    lead.turno_instalacao = turno
    lead.data_instalacao = data_obj
    lead.save(update_fields=['turno_instalacao', 'data_instalacao', 'data_atualizacao'])

    from integracoes.services.agendamento_ia import (
        criar_ou_obter_agendamento, executar_agendamento, AgendamentoIAError,
    )
    try:
        agendamento = criar_ou_obter_agendamento(lead)
        resultado = executar_agendamento(agendamento)
    except AgendamentoIAError as e:
        return JsonResponse({'ok': False, 'erro': str(e)}, status=400)

    if resultado.get('status') == 'agendado':
        _mover_para_slug(op, 'ind_agendado', request.user, 'Atendimento + O.S. abertos (indicação)')
        _notificar_indicacao('indicacao_os_aberta', 'Atendimento e O.S. abertos',
                             f'Instalação de {lead.nome_razaosocial or "cliente"} agendada '
                             f'({turno}, {data_obj.strftime("%d/%m/%Y")}) — atendimento e O.S. abertos.',
                             op, prioridade='alta', chave=f'ind_os_{op.id}')
        return JsonResponse({'ok': True, 'agendamento': resultado,
                             'oportunidade': _oportunidade_para_dict(op)})
    if resultado.get('status') == 'erro':
        _notificar_alerta('indicacao_falha_agendamento', 'Falha ao abrir atendimento/O.S.',
                          f'Não foi possível abrir atendimento/O.S. de '
                          f'{lead.nome_razaosocial or "cliente"}: {(resultado.get("mensagem") or "")[:120]}', op)
    # aguardando_sync (worker retoma) ou erro
    return JsonResponse({'ok': False, 'status': resultado.get('status'),
                         'agendamento': resultado,
                         'erro': resultado.get('mensagem') or 'Falha ao abrir atendimento/O.S.'},
                        status=202)


# ============================================================================
# PIPELINE WIFEED (leads do portal WiFi) — mesmo processo da Indicação, porém
# pipeline próprio (slugs wf_*, tipo='wifeed') alimentado pelo poller da API.
# As ações sobre a oportunidade reusam os backends genéricos (conversão HubSoft,
# agendamento IA, mover_para_slug, contrato_info).
# ============================================================================

def _notificar_wifeed(tipo, titulo, mensagem, op, prioridade='normal', chave=None):
    """Notifica os operadores do pipeline Wifeed sobre um marco da oportunidade."""
    try:
        from vendas_web.notificacoes_service import notificar_por_capacidade
        notificar_por_capacidade(
            'ver_pipeline_wifeed', tipo, titulo, mensagem,
            contexto={'oportunidade_id': op.id, 'url': f'/crm/oportunidades/{op.id}/'},
            prioridade=prioridade, chave=chave)
    except Exception:  # noqa: BLE001
        pass


def criar_lead_wifeed(data):
    """Cria lead do Wifeed no funil CRM (signal gera a oportunidade wifeed).

    Raises ValueError se nome ou telefone estiverem ausentes.
    Retorna (lead, oportunidade|None). Aceita `id_origem` (id do record no Wifeed)
    e `id_origem_servico` (id do local) para rastreio/dedupe.
    """
    from vendas_web.models import LeadProspecto

    nome = (data.get('nome_razaosocial') or '').strip()
    telefone = (data.get('telefone') or '').strip()
    if not nome or not telefone:
        raise ValueError('Nome e telefone são obrigatórios')

    campos = {
        'nome_razaosocial': nome, 'telefone': telefone,
        'canal_entrada': 'wifeed', 'origem': 'wifeed',
        'tipo_entrada': 'formulario', 'status_api': 'wifeed',
        'id_origem': (str(data.get('id_origem')) if data.get('id_origem') else ''),
        'id_origem_servico': (str(data.get('id_origem_servico')) if data.get('id_origem_servico') else ''),
    }
    for c in _CAMPOS_LEAD_EDITAVEIS:
        if c in data and c not in campos:
            v = _coerce_lead(c, data.get(c))
            if v not in (None, ''):
                campos[c] = v
    lead = LeadProspecto.objects.create(**campos)
    op = OportunidadeVenda.objects.filter(lead=lead, tipo='wifeed').first()
    return lead, op


@login_required
@require_GET
def api_wifeed_contrato_status(request):
    """Estado do contrato do cliente convertido (monitoramento p/ o operador)."""
    from crm.services.wifeed_pipeline import sincronizar_oportunidade_wifeed
    op = get_object_or_404(OportunidadeVenda, pk=request.GET.get('oportunidade_id'), ativo=True)
    contrato = _contrato_info(op.lead)
    movido = sincronizar_oportunidade_wifeed(op, request.user)
    if movido:
        op.refresh_from_db()
    return JsonResponse({
        'ok': True,
        'contrato': contrato,
        'movido': movido,
        'oportunidade': _oportunidade_para_dict(op),
    })


@login_required
@require_POST
@requer_cap('operar_wifeed')
def api_wifeed_criar(request):
    """Cria manualmente um lead WIFEED. O signal cria a oportunidade no funil
    wifeed. NÃO cria prospecto (status_api='wifeed' ≠ 'pendente')."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)
    try:
        lead, op = criar_lead_wifeed(data)
    except ValueError as e:
        return JsonResponse({'ok': False, 'erro': str(e)}, status=400)
    return JsonResponse({'ok': True, 'lead_id': lead.id,
                         'oportunidade_id': op.id if op else None})


@login_required
@require_POST
@requer_cap('operar_wifeed')
def api_wifeed_converter(request):
    """Torna o lead wifeed em prospecto → cliente (mesmo backend da indicação)."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)
    op = get_object_or_404(OportunidadeVenda, pk=data.get('oportunidade_id'), ativo=True)
    lead = op.lead

    faltando = [c for c in _CAMPOS_MIN_CONVERSAO if not getattr(lead, c, None)]
    if faltando:
        return JsonResponse({'ok': False, 'erro': 'Dados incompletos para conversão',
                             'faltando': faltando}, status=400)
    if lead.id_dia_vencimento not in _VENCIMENTOS_VALIDOS:
        return JsonResponse({'ok': False, 'faltando': ['id_dia_vencimento'],
                             'erro': 'Dia de vencimento inválido — escolha 1, 5, 15 ou 20.'},
                            status=400)

    if not lead.id_hubsoft:
        lead.status_api = 'pendente'
        lead.save(update_fields=['status_api', 'data_atualizacao'])
        lead.refresh_from_db()
    if not lead.id_hubsoft:
        return JsonResponse({'ok': False,
                             'erro': 'Não foi possível criar o prospecto no HubSoft'}, status=502)

    from posvenda_hubsoft.executores.seletor import processar
    res = processar('conversao', lead.id, dry_run=False)
    if getattr(res, 'status', None) == 'sucesso':
        _mover_para_slug(op, 'wf_apto', request.user, 'Convertido em cliente — aguardando assinatura do contrato')
        _notificar_wifeed('wifeed_convertida', 'Lead Wifeed convertido em cliente',
                          f'{lead.nome_razaosocial or "Cliente"} foi convertido no HubSoft. '
                          f'Aguardando assinatura do contrato para abrir atendimento/O.S.',
                          op, prioridade='alta', chave=f'wf_conv_{op.id}')
        return JsonResponse({'ok': True, 'status': 'cliente_criado',
                             'id_hubsoft': lead.id_hubsoft,
                             'oportunidade': _oportunidade_para_dict(op)})
    _notificar_alerta('wifeed_falha_conversao', 'Falha ao converter lead Wifeed',
                      f'A conversão de {lead.nome_razaosocial or "um lead"} não concluiu: '
                      f'{(getattr(res, "erro", "") or "")[:120]}', op)
    return JsonResponse({'ok': False, 'status': getattr(res, 'status', 'falha'),
                         'id_hubsoft': lead.id_hubsoft,
                         'erro': (getattr(res, 'erro', '') or
                                  'Conversão não concluída — o worker tentará novamente')},
                        status=202)


@login_required
@require_POST
@requer_cap('operar_wifeed')
def api_wifeed_agendar(request):
    """Abre atendimento + O.S. (Matrix) p/ o lead wifeed já convertido em cliente."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)
    op = get_object_or_404(OportunidadeVenda, pk=data.get('oportunidade_id'), ativo=True)
    lead = op.lead

    contrato = _contrato_info(lead)
    if not contrato['aceito']:
        return JsonResponse({'ok': False, 'contrato': contrato,
                             'erro': 'O contrato ainda não foi aceito pelo cliente. '
                                     'Abra o atendimento e a O.S. somente após o aceite.'},
                            status=409)

    turno = (data.get('turno') or '').strip()
    data_inst = (data.get('data_instalacao') or '').strip()
    if turno not in ('manha', 'tarde') or not data_inst:
        return JsonResponse({'ok': False, 'erro': 'Informe turno (manha/tarde) e data'}, status=400)

    from datetime import datetime as _dt
    try:
        data_obj = _dt.strptime(data_inst, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'ok': False, 'erro': 'Data inválida (use o seletor).'}, status=400)

    lead.turno_instalacao = turno
    lead.data_instalacao = data_obj
    lead.save(update_fields=['turno_instalacao', 'data_instalacao', 'data_atualizacao'])

    from integracoes.services.agendamento_ia import (
        criar_ou_obter_agendamento, executar_agendamento, AgendamentoIAError,
    )
    try:
        agendamento = criar_ou_obter_agendamento(lead)
        resultado = executar_agendamento(agendamento)
    except AgendamentoIAError as e:
        return JsonResponse({'ok': False, 'erro': str(e)}, status=400)

    if resultado.get('status') == 'agendado':
        _mover_para_slug(op, 'wf_agendado', request.user, 'Atendimento + O.S. abertos (wifeed)')
        _notificar_wifeed('wifeed_os_aberta', 'Atendimento e O.S. abertos',
                          f'Instalação de {lead.nome_razaosocial or "cliente"} agendada '
                          f'({turno}, {data_obj.strftime("%d/%m/%Y")}) — atendimento e O.S. abertos.',
                          op, prioridade='alta', chave=f'wf_os_{op.id}')
        return JsonResponse({'ok': True, 'agendamento': resultado,
                             'oportunidade': _oportunidade_para_dict(op)})
    if resultado.get('status') == 'erro':
        _notificar_alerta('wifeed_falha_agendamento', 'Falha ao abrir atendimento/O.S.',
                          f'Não foi possível abrir atendimento/O.S. de '
                          f'{lead.nome_razaosocial or "cliente"}: {(resultado.get("mensagem") or "")[:120]}', op)
    return JsonResponse({'ok': False, 'status': resultado.get('status'),
                         'agendamento': resultado,
                         'erro': resultado.get('mensagem') or 'Falha ao abrir atendimento/O.S.'},
                        status=202)


# ============================================================================
# FONTES WIFEED — painel p/ escolher quais locais/campanhas trazem leads
# ============================================================================

@login_required
@requer_cap('gerenciar_wifeed')
def wifeed_fontes_view(request):
    """Painel de gestão das fontes do Wifeed (locais e campanhas)."""
    from django.conf import settings
    from crm.models import WifeedFonte, WifeedConfig
    fontes = list(WifeedFonte.objects.all())
    locais = [f for f in fontes if f.tipo == 'local']
    campanhas = [f for f in fontes if f.tipo == 'campanha']
    ultima = max((f.ultima_sincronizacao for f in fontes if f.ultima_sincronizacao), default=None)
    creds_ok = bool(getattr(settings, 'WIFEED_CLIENT_ID', '') and getattr(settings, 'WIFEED_CLIENT_SECRET', ''))
    return render(request, 'crm/wifeed_fontes.html', {
        'locais': locais,
        'campanhas': campanhas,
        'n_local_ativo': sum(1 for f in locais if f.ativo),
        'n_camp_ativo': sum(1 for f in campanhas if f.ativo),
        'ultima_sync': ultima,
        'creds_ok': creds_ok,
        'wifeed_enabled': getattr(settings, 'WIFEED_ENABLED', False),
        'intervalo_minutos': WifeedConfig.get().intervalo_minutos,
        'page_title': 'Fontes Wifeed',
    })


@login_required
@require_POST
@requer_cap('gerenciar_wifeed')
def api_wifeed_fontes_sincronizar(request):
    """Atualiza o catálogo de locais/campanhas a partir da API Wifeed."""
    from django.conf import settings
    from crm.services.wifeed_fontes import sincronizar_catalogo
    from crm.services.wifeed_client import WifeedError
    if not (getattr(settings, 'WIFEED_CLIENT_ID', '') and getattr(settings, 'WIFEED_CLIENT_SECRET', '')):
        return JsonResponse({'ok': False, 'erro': 'Credenciais do Wifeed não configuradas '
                             '(WIFEED_CLIENT_ID/WIFEED_CLIENT_SECRET).'}, status=400)
    try:
        res = sincronizar_catalogo()
    except WifeedError as e:
        return JsonResponse({'ok': False, 'erro': f'Falha na API Wifeed: {e}'}, status=502)
    except Exception as e:  # noqa: BLE001
        return JsonResponse({'ok': False, 'erro': f'Erro ao sincronizar: {e}'}, status=500)
    return JsonResponse({'ok': True, **res})


@login_required
@require_POST
@requer_cap('gerenciar_wifeed')
def api_wifeed_fontes_salvar(request):
    """Salva a seleção de fontes + intervalo e DISPARA uma sincronização de leads.

    Body: {ids: [pk,...] (estado completo), intervalo_minutos: int}.
    Ao salvar, puxa os leads das fontes ativas (hoje) em background — os cards
    aparecem no pipeline em instantes."""
    from django.conf import settings
    from crm.models import WifeedFonte, WifeedConfig
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    ids = {int(x) for x in (data.get('ids') or []) if str(x).isdigit()}
    ativados = WifeedFonte.objects.filter(pk__in=ids).update(ativo=True)
    WifeedFonte.objects.exclude(pk__in=ids).update(ativo=False)

    # Intervalo do poller (min 1, máx 1440 minutos).
    try:
        intervalo = int(data.get('intervalo_minutos') or 15)
    except (TypeError, ValueError):
        intervalo = 15
    intervalo = max(1, min(1440, intervalo))
    cfg = WifeedConfig.get()
    if cfg.intervalo_minutos != intervalo:
        cfg.intervalo_minutos = intervalo
        cfg.save(update_fields=['intervalo_minutos', 'atualizado_em'])

    # Dispara a captação dos leads das fontes ativas (hoje), sem travar a resposta.
    disparou = False
    if ativados and getattr(settings, 'WIFEED_CLIENT_ID', '') and getattr(settings, 'WIFEED_CLIENT_SECRET', ''):
        try:
            from crm.services.wifeed_sync import sincronizar_em_background
            sincronizar_em_background(dias=0)
            disparou = True
        except Exception:  # noqa: BLE001
            logger.exception('[wifeed] falha ao disparar sync no salvar')

    return JsonResponse({
        'ok': True, 'ativos': ativados, 'intervalo_minutos': intervalo,
        'sync_disparado': disparou,
        'mensagem': ('Seleção salva. Buscando leads das fontes — aparecem no pipeline em instantes.'
                     if disparou else 'Seleção salva.'),
    })


# ============================================================================
# PERFIS DE ACESSO (RBAC) — tela de matriz de permissões
# ============================================================================

@login_required
@requer_cap('gerenciar_perfis')
def perfis_view(request):
    from vendas_web.models import PerfilAcesso
    from vendas_web.rbac import CAPACIDADES
    from django.contrib.auth.models import User
    perfis = []
    for p in PerfilAcesso.objects.prefetch_related('usuarios').order_by('nome'):
        perfis.append({
            'id': p.id, 'nome': p.nome, 'descricao': p.descricao, 'cor_hex': p.cor_hex,
            'ativo': p.ativo, 'escopo_dados': p.escopo_dados,
            'capacidades': list(p.capacidades or []),
            'usuarios': list(p.usuarios.values_list('id', flat=True)),
            'qtd_usuarios': p.usuarios.count(),
        })
    usuarios = [{'id': u.id, 'nome': (u.get_full_name() or u.username), 'username': u.username}
                for u in User.objects.filter(is_active=True).order_by('first_name', 'username')]
    return render(request, 'crm/perfis.html', {
        'perfis_json': json.dumps(perfis),
        'catalogo': CAPACIDADES,
        'escopo_choices': PerfilAcesso.ESCOPO_CHOICES,
        'usuarios_json': json.dumps(usuarios),
        'page_title': 'Perfis de Acesso',
    })


@login_required
@require_POST
@requer_cap('gerenciar_perfis')
def api_perfil_salvar(request):
    from vendas_web.models import PerfilAcesso
    from vendas_web.rbac import TODAS_CAPACIDADES
    from django.utils.text import slugify
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)
    nome = (data.get('nome') or '').strip()
    if not nome:
        return JsonResponse({'ok': False, 'erro': 'Nome é obrigatório'}, status=400)
    caps = [c for c in (data.get('capacidades') or []) if c in TODAS_CAPACIDADES]
    escopo = data.get('escopo_dados')
    if escopo not in dict(PerfilAcesso.ESCOPO_CHOICES):
        escopo = 'proprios'
    defaults = {
        'nome': nome, 'descricao': (data.get('descricao') or '')[:255],
        'cor_hex': (data.get('cor_hex') or '#0022fa')[:7],
        'ativo': bool(data.get('ativo', True)),
        'capacidades': caps, 'escopo_dados': escopo,
    }
    pid = data.get('id')
    if pid:
        PerfilAcesso.objects.filter(pk=pid).update(**defaults)
        perfil = PerfilAcesso.objects.get(pk=pid)
    else:
        base = slugify(nome)[:70] or 'perfil'
        slug, i = base, 1
        while PerfilAcesso.objects.filter(slug=slug).exists():
            i += 1
            slug = f'{base}-{i}'
        perfil = PerfilAcesso.objects.create(slug=slug, **defaults)
    return JsonResponse({'ok': True, 'id': perfil.id})


@login_required
@requer_cap('gerenciar_usuarios')
def usuarios_view(request):
    """Gestão de Usuários — lista os usuários (vindos do portal TecHub) com
    busca, status de acesso e atribuição de perfil em um clique."""
    from django.contrib.auth.models import User
    from vendas_web.models import PerfilAcesso
    perfis = list(PerfilAcesso.objects.filter(ativo=True).order_by('nome')
                  .values('id', 'nome', 'cor_hex'))
    usuarios = []
    qs = (User.objects.filter(is_active=True)
          .prefetch_related('perfis_acesso')
          .order_by('first_name', 'username'))
    for u in qs:
        ps = [{'id': p.id, 'nome': p.nome, 'cor': p.cor_hex}
              for p in u.perfis_acesso.all() if p.ativo]
        usuarios.append({
            'id': u.id,
            'nome': (u.get_full_name() or u.username),
            'username': u.username,
            'email': u.email or '',
            'is_superuser': u.is_superuser,
            'perfis': ps,
        })
    stats = {
        'total': len(usuarios),
        'admins': sum(1 for u in usuarios if u['is_superuser']),
        'liberados': sum(1 for u in usuarios if u['perfis'] and not u['is_superuser']),
    }
    stats['pendentes'] = stats['total'] - stats['admins'] - stats['liberados']
    return render(request, 'crm/usuarios.html', {
        'usuarios_json': json.dumps(usuarios),
        'perfis_json': json.dumps(perfis),
        'stats': stats,
        'page_title': 'Gestão de Usuários',
    })


@login_required
@require_POST
@requer_cap('gerenciar_usuarios')
def api_usuario_perfil(request):
    """Adiciona/remove UM perfil de UM usuário. Body: {user_id, perfil_id, acao}."""
    from django.contrib.auth.models import User
    from vendas_web.models import PerfilAcesso
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)
    user = get_object_or_404(User, pk=data.get('user_id'), is_active=True)
    perfil = get_object_or_404(PerfilAcesso, pk=data.get('perfil_id'), ativo=True)
    acao = data.get('acao')
    if acao == 'adicionar':
        perfil.usuarios.add(user)
    elif acao == 'remover':
        perfil.usuarios.remove(user)
    else:
        return JsonResponse({'ok': False, 'erro': 'Ação inválida'}, status=400)
    perfis = [{'id': p.id, 'nome': p.nome, 'cor': p.cor_hex}
              for p in user.perfis_acesso.filter(ativo=True)]
    return JsonResponse({'ok': True, 'perfis': perfis})


@login_required
@require_POST
@requer_cap('gerenciar_usuarios')
def api_usuarios_sincronizar(request):
    """Importa/atualiza os usuários do PORTAL TECHUB para o banco local.

    Chama POST {PORTAL_URL}/api/listar-usuarios/ (autentica com o mesmo
    PORTAL_SECRET_KEY do SSO). Usuário novo nasce com senha inutilizável —
    login só via SSO do portal — e SEM perfil (acesso é liberado pelo admin
    atribuindo um Perfil de Acesso). Ninguém é desativado/rebaixado aqui.
    """
    from django.conf import settings as _s
    from django.contrib.auth.models import User
    portal_url = getattr(_s, 'PORTAL_URL', 'http://127.0.0.1:8100')
    secret = getattr(_s, 'PORTAL_SECRET_KEY', '')
    if not secret:
        return JsonResponse({'ok': False, 'erro': 'PORTAL_SECRET_KEY não configurada.'}, status=500)
    try:
        r = requests.post(f'{portal_url}/api/listar-usuarios/',
                          json={'secret_key': secret}, timeout=15)
        r.raise_for_status()
        usuarios = r.json().get('users', [])
    except Exception as e:
        return JsonResponse({'ok': False,
                             'erro': f'Falha ao consultar o portal: {e}'}, status=502)
    criados = atualizados = 0
    for ud in usuarios:
        if not ud.get('username'):
            continue
        user, created = User.objects.get_or_create(
            username=ud['username'],
            defaults={'email': ud.get('email', ''),
                      'first_name': ud.get('first_name', ''),
                      'last_name': ud.get('last_name', '')})
        user.email = ud.get('email', user.email)
        user.first_name = ud.get('first_name', user.first_name)
        user.last_name = ud.get('last_name', user.last_name)
        # eleva flags vindas do portal, nunca rebaixa (mesma regra do SSO)
        user.is_staff = user.is_staff or ud.get('is_staff', False)
        user.is_superuser = user.is_superuser or ud.get('is_superuser', False)
        if created:
            user.set_unusable_password()
            criados += 1
        else:
            atualizados += 1
        user.save()
    return JsonResponse({'ok': True, 'total_portal': len(usuarios),
                         'criados': criados, 'atualizados': atualizados})


@login_required
@require_POST
@requer_cap('gerenciar_perfis')
def api_perfil_usuarios(request):
    from vendas_web.models import PerfilAcesso
    from django.contrib.auth.models import User
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)
    perfil = get_object_or_404(PerfilAcesso, pk=data.get('id'))
    ids = [int(x) for x in (data.get('usuarios') or []) if str(x).isdigit()]
    perfil.usuarios.set(User.objects.filter(id__in=ids, is_active=True))
    return JsonResponse({'ok': True, 'total': perfil.usuarios.count()})


# ============================================================================
# MENSAGENS DE WHATSAPP POR PIPELINE (mensagem inicial configurável)
# ============================================================================

@login_required
@requer_cap('ver_config')
def mensagens_view(request):
    from crm.models import MensagemPipeline
    existentes = {m.pipeline_tipo: m for m in MensagemPipeline.objects.all()}
    itens = []
    for v, rot in PipelineEstagio.PIPELINE_TIPO_CHOICES:
        m = existentes.get(v)
        itens.append({'tipo': v, 'rotulo': rot,
                      'mensagem': m.mensagem if m else '',
                      'ativo': m.ativo if m else True})
    return render(request, 'crm/mensagens.html',
                  {'itens': itens, 'page_title': 'Mensagens de WhatsApp'})


def _invalidar_cache_ia():
    """Avisa o engine (FastAPI) que uma regra/mensagem mudou → recarrega na hora."""
    try:
        from django.conf import settings as _s
        ia_url = getattr(_s, 'IA_VALIDACAO_URL', 'http://127.0.0.1:8091')
        requests.post(f'{ia_url}/admin/invalidar-cache/', timeout=3)
    except Exception:
        pass


# Perguntas cujas RESPOSTAS (confirmação/erro) são editáveis na aba. Vêm da
# RegraValidacao (msg_sucesso/msg_erro) — o engine já as usa.
_RESPOSTAS_EDITAVEIS = [
    ('coleta_cpf', 'CPF'), ('coleta_nome', 'Nome'),
    ('coleta_data_nascimento', 'Data de nascimento'), ('coleta_email', 'E-mail'),
    ('coleta_cep', 'CEP'), ('coleta_cidade', 'Cidade'), ('coleta_bairro', 'Bairro'),
    ('coleta_rua', 'Rua'), ('coleta_numero', 'Número da residência'),
    ('tipo_imovel', 'Tipo de imóvel'), ('dia_vencimento', 'Dia de vencimento'),
    ('escolha_turno', 'Turno da instalação'), ('escolha_data', 'Data da instalação'),
    ('confirmacao_dados', 'Confirmação dos dados'),
]


def _item_mensagem(m):
    """Card de uma MensagemRobo (1 campo)."""
    return {
        'titulo': m.rotulo, 'descricao': m.descricao,
        'campos': [{
            'id': f'msg__{m.chave}', 'label': '', 'texto': m.texto,
            'texto_padrao': m.texto_padrao,
            'placeholder': m.placeholders, 'fonte': 'mensagem',
            'chave': m.chave, 'ativo': m.ativo, 'tem_ativo': True,
            'editada': bool(m.texto_padrao) and (m.texto or '').strip() != (m.texto_padrao or '').strip(),
        }],
    }


@login_required
@requer_cap('ver_config')
def mensagens_robo_view(request):
    """Central de mensagens do robô (o que o cliente lê no WhatsApp), agrupada."""
    from ia_validador.models import MensagemRobo, RegraValidacao
    grupos = []
    por_grupo = {}
    for m in MensagemRobo.objects.all():
        por_grupo.setdefault(m.grupo, []).append(m)
    for gkey, grot in MensagemRobo.GRUPO_CHOICES:
        msgs = sorted(por_grupo.get(gkey, []), key=lambda x: (x.ordem, x.chave))
        if msgs:
            grupos.append({'rotulo': grot, 'itens': [_item_mensagem(m) for m in msgs]})

    # Grupo sintético: Confirmações & respostas (msg_sucesso/msg_erro das regras)
    regras = {r.question_id: r for r in RegraValidacao.objects.filter(
        question_id__in=[q for q, _ in _RESPOSTAS_EDITAVEIS])}
    itens_resp = []
    for qid, label in _RESPOSTAS_EDITAVEIS:
        r = regras.get(qid)
        if not r:
            continue
        itens_resp.append({
            'titulo': label,
            'descricao': 'Resposta após o cliente informar este dado.',
            'campos': [
                {'id': f'reg__{qid}__msg_sucesso', 'label': 'Confirmação (resposta válida)',
                 'texto': r.msg_sucesso or '', 'placeholder': '', 'fonte': 'regra',
                 'question_id': qid, 'campo': 'msg_sucesso', 'tem_ativo': False},
                {'id': f'reg__{qid}__msg_erro', 'label': 'Erro (resposta inválida)',
                 'texto': r.msg_erro or '', 'placeholder': '', 'fonte': 'regra',
                 'question_id': qid, 'campo': 'msg_erro', 'tem_ativo': False},
            ],
        })
    if itens_resp:
        grupos.append({'rotulo': 'Confirmações & respostas', 'itens': itens_resp})

    return render(request, 'crm/mensagens_robo.html',
                  {'grupos': grupos, 'page_title': 'Mensagens do Robô'})


@login_required
@require_POST
@requer_cap('gerenciar_config')
def api_mensagem_robo_salvar(request):
    """Salva UMA mensagem do robô e invalida o cache do engine (reflete na hora).

    Duas fontes:
    - fonte='mensagem' → MensagemRobo por `chave` (texto vazio = usa padrão).
    - fonte='regra'    → RegraValidacao.`campo` (msg_sucesso/msg_erro) por `question_id`.
    """
    from ia_validador.models import MensagemRobo, RegraValidacao
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)
    fonte = data.get('fonte') or 'mensagem'
    texto = (data.get('texto') or '').strip()

    if fonte == 'regra':
        qid = (data.get('question_id') or '').strip()
        campo = data.get('campo')
        if campo not in ('msg_sucesso', 'msg_erro'):
            return JsonResponse({'ok': False, 'erro': 'Campo inválido'}, status=400)
        r = RegraValidacao.objects.filter(question_id=qid).first()
        if not r:
            return JsonResponse({'ok': False, 'erro': 'Regra não encontrada'}, status=404)
        setattr(r, campo, texto)
        r.save(update_fields=[campo])
        _invalidar_cache_ia()
        return JsonResponse({'ok': True})

    chave = (data.get('chave') or '').strip()
    m = MensagemRobo.objects.filter(chave=chave).first()
    if not m:
        return JsonResponse({'ok': False, 'erro': 'Mensagem não encontrada'}, status=404)
    # Guarda GENÉRICA: se o texto PADRÃO tem opções numeradas ("*1)*", "*2)*"…),
    # a edição precisa manter os mesmos números — o robô entende a resposta
    # por eles. (Vale p/ vitrine de planos, confirmações, menu de ajuste etc.)
    import re as _re
    if texto and m.texto_padrao:
        numeros_padrao = sorted(set(_re.findall(r'\*(\d)\)\*', m.texto_padrao)))
        if numeros_padrao:
            faltando = [n for n in numeros_padrao if n not in texto]
            if faltando:
                return JsonResponse(
                    {'ok': False,
                     'erro': f'Mantenha as opções numeradas {", ".join(numeros_padrao)} '
                             'no texto — o robô usa esses números para entender a resposta.'},
                    status=400)
    m.texto = texto
    m.ativo = bool(data.get('ativo', True))
    m.save(update_fields=['texto', 'ativo', 'data_atualizacao'])
    _invalidar_cache_ia()
    return JsonResponse({'ok': True})


@login_required
@require_POST
@requer_cap('gerenciar_config')
def api_mensagem_salvar(request):
    from crm.models import MensagemPipeline
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)
    tipo = data.get('pipeline_tipo')
    if tipo not in {c[0] for c in PipelineEstagio.PIPELINE_TIPO_CHOICES}:
        return JsonResponse({'ok': False, 'erro': 'Pipeline inválido'}, status=400)
    MensagemPipeline.objects.update_or_create(
        pipeline_tipo=tipo,
        defaults={'mensagem': (data.get('mensagem') or '').strip(),
                  'ativo': bool(data.get('ativo', True))})
    return JsonResponse({'ok': True})
