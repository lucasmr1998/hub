import json
import logging
from decimal import Decimal

import requests
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.views.decorators.http import require_POST, require_GET

from apps.sistema.decorators import webhook_token_required, user_tem_funcionalidade
from apps.comercial.crm.escopo import escopo_responsaveis
from apps.sistema.models import PerfilUsuario
from apps.sistema.utils import auditar

from .models import (
    Pipeline, PipelineEstagio, OportunidadeVenda, HistoricoPipelineEstagio,
    TarefaCRM, NotaInterna, MetaVendas, SegmentoCRM,
    ConfiguracaoCRM, EquipeVendas, PerfilVendedor,
    ProdutoServico, ItemOportunidade, OpcaoVencimentoCRM,
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
    from django.utils.timesince import timesince
    lead = op.lead
    responsavel = op.responsavel
    # Usa o prefetch_related cache (evita N+1) — .all() usa cache, .filter() cria nova query
    tarefas_pendentes = sum(
        1 for t in op.tarefas.all()
        if t.status in ('pendente', 'em_andamento')
    )
    # Tempo no estagio formatado humano ("1 hora, 25 minutos") — usa o mesmo
    # `timesince` que a pagina detalhe. Mais granular que dias.
    if op.data_entrada_estagio:
        try:
            tempo_estagio_humano = timesince(op.data_entrada_estagio).split(',')[0]
        except Exception:
            tempo_estagio_humano = None
    else:
        tempo_estagio_humano = None
    # Plano: tenta id_plano_rp -> ProdutoServico, senao plano_interesse legado
    plano_nome = None
    if lead.id_plano_rp:
        try:
            from apps.comercial.crm.models import ProdutoServico
            prod = ProdutoServico.objects.filter(id_externo=str(lead.id_plano_rp)).first()
            if prod:
                plano_nome = prod.nome
        except Exception:
            pass
    if not plano_nome and op.plano_interesse:
        plano_nome = op.plano_interesse.nome

    # Viabilidade
    dc_lead = getattr(lead, 'dados_custom', None) or {}
    via = dc_lead.get('viabilidade') if isinstance(dc_lead, dict) else None
    viab_status = via.get('status') if isinstance(via, dict) else None

    # Proxima tarefa (primeira pendente por prazo)
    proxima_tarefa = None
    for t in sorted(op.tarefas.all(), key=lambda x: x.data_vencimento or x.data_criacao):
        if t.status in ('pendente', 'em_andamento'):
            proxima_tarefa = {
                'titulo': t.titulo[:50],
                'vencimento': t.data_vencimento.strftime('%d/%m %H:%M') if t.data_vencimento else None,
                'vencida': bool(t.data_vencimento and t.data_vencimento < timezone.now()),
            }
            break

    # Nome exibido no card: SEMPRE prioriza o nome atual do lead (sincronizado
    # em tempo real). op.titulo eh fallback de apelido manual; telefone e
    # ultimo recurso quando nem nome existe. Antes priorizava op.titulo, mas
    # isso travava o card num snapshot da criacao (bug do lead 1591/op 1750
    # onde o nome atualizou no lead mas o titulo da op ficou "Rafa").
    nome_display = lead.nome_razaosocial or op.titulo or lead.telefone or f'Lead #{lead.id}'
    return {
        'id': op.pk,
        'lead_id': lead.pk,
        'nome': nome_display,
        'telefone': lead.telefone,
        'email': lead.email or '',
        'cpf': lead.cpf_cnpj or '',
        'valor': str(op.valor_estimado or 0),
        'valor_estimado': str(op.valor_estimado or 0),
        'probabilidade': op.probabilidade,
        'prioridade': op.prioridade,
        'score': lead.score_qualificacao or 0,
        'score_externo': getattr(lead, 'score_status', '') or '',
        'viabilidade': viab_status or '',
        'origem': lead.origem or '',
        'dias_no_estagio': op.dias_no_estagio,
        'tempo_no_estagio': op.dias_no_estagio,
        'tempo_no_estagio_humano': tempo_estagio_humano,
        'sla_vencido': op.sla_vencido,
        'responsavel_id': responsavel.pk if responsavel else None,
        'responsavel': (responsavel.get_full_name() or responsavel.username) if responsavel else '',
        'responsavel_nome': responsavel.get_full_name() or responsavel.username if responsavel else None,
        'responsavel_avatar': (responsavel.get_full_name() or responsavel.username)[0].upper() if responsavel else '?',
        'responsavel_inicial': (responsavel.get_full_name() or responsavel.username)[0].upper() if responsavel else '?',
        'tarefas_pendentes': tarefas_pendentes,
        'proxima_tarefa': proxima_tarefa,
        'estagio_id': op.estagio_id,
        'data_criacao': op.data_criacao.strftime('%d/%m/%Y'),
        'data_prevista': op.data_fechamento_previsto.strftime('%d/%m/%Y') if op.data_fechamento_previsto else None,
        'ultima_atividade': op.data_atualizacao.strftime('%d/%m %H:%M') if op.data_atualizacao else None,
        'plano': plano_nome,
        'id_hubsoft': lead.id_hubsoft or '',
        'itens_count': sum(1 for _ in op.itens.all()),
        'tags': [{'nome': t.nome, 'cor': t.cor_hex} for t in op.tags.all()],
        'churn_risk_score': op.churn_risk_score,
        'dados_custom': op.dados_custom or {},
        # Origem / atribuicao — prioriza op (last-touch) com fallback no lead (first-touch)
        'canal':    op.canal_atribuicao or lead.canal or '',
        'fonte':    op.fonte_atribuicao or lead.fonte or '',
        'campanha': (op.campanha_atribuicao.nome if op.campanha_atribuicao_id
                     else (lead.campanha_origem.nome if lead.campanha_origem_id else '')),
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

    # Opcoes pra Canal e Fonte (escolhas fixas do model LeadProspecto)
    from apps.comercial.leads.models import LeadProspecto as _L
    # Campanhas: lista de CampanhaTrafego ativas do tenant
    from apps.marketing.campanhas.models import CampanhaTrafego
    campanhas_opts = list(
        CampanhaTrafego.objects.filter(ativa=True).order_by('nome').values('id', 'nome')
    )

    filter_fields = [
        {'type': 'select', 'label': 'Responsavel', 'name': 'responsavel', 'value': request.GET.get('responsavel', ''),
         'options': [('', 'Todos'), ('sem', '— Sem responsavel —')] + [(str(v['id']), v['nome']) for v in vendedores]},
        {'type': 'select', 'label': 'Estagio', 'name': 'estagio', 'value': request.GET.get('estagio', ''),
         'options': [('', 'Todos')] + [(str(e.pk), e.nome) for e in estagios]},
        {'type': 'select', 'label': 'Prioridade', 'name': 'prioridade', 'value': request.GET.get('prioridade', ''),
         'options': [('', 'Todas'), ('baixa', 'Baixa'), ('normal', 'Normal'), ('alta', 'Alta'), ('urgente', 'Urgente')]},
        {'type': 'select', 'label': 'Tag', 'name': 'tag', 'value': '',
         'options': [('', 'Todas')] + [(t.nome, t.nome) for t in tags]},
        {'type': 'select', 'label': 'Valor', 'name': 'valor', 'value': '',
         'options': [
             ('', 'Qualquer'),
             ('0-100', 'Ate R$ 100'),
             ('100-500', 'R$ 100 a R$ 500'),
             ('500-1000', 'R$ 500 a R$ 1.000'),
             ('1000+', 'Acima de R$ 1.000'),
         ]},
        {'type': 'select', 'label': 'Criada em', 'name': 'periodo', 'value': request.GET.get('periodo', ''),
         'options': [
             ('', 'Qualquer data'),
             ('7', 'Ultimos 7 dias'),
             ('30', 'Ultimos 30 dias'),
             ('90', 'Ultimos 90 dias'),
         ]},
        # Sprint 5: filtros de origem (multi-select)
        {'type': 'multiselect', 'label': 'Canal', 'name': 'canal',
         'values': request.GET.getlist('canal'),
         'options': [(v, l) for v, l in _L.CANAL_CHOICES]},
        {'type': 'multiselect', 'label': 'Fonte', 'name': 'fonte',
         'values': request.GET.getlist('fonte'),
         'options': [(v, l) for v, l in _L.FONTE_CHOICES]},
        {'type': 'multiselect', 'label': 'Campanha', 'name': 'campanha',
         'values': request.GET.getlist('campanha'),
         'options': [(str(c['id']), c['nome']) for c in campanhas_opts]},
    ]

    # T1 — Motivos de perda + flags pra o modal do Kanban
    from .models import MotivoPerda
    motivos_perda = list(MotivoPerda.objects.filter(ativo=True).order_by('ordem', 'nome').values('id', 'nome'))
    cfg_crm = ConfiguracaoCRM.get_config()
    motivo_perda_obrigatorio = bool(cfg_crm and cfg_crm.motivo_perda_obrigatorio)
    motivo_perda_pede_concorrente = bool(cfg_crm and cfg_crm.motivo_perda_pede_concorrente)

    # Personalizacao do card — campos visiveis pro usuario atual
    from .cards_config import (
        CAMPOS_CARD_DISPONIVEIS, CATEGORIAS_LABEL, MAX_CAMPOS_VISIVEIS,
        resolver_campos_do_usuario,
    )
    campos_visiveis = resolver_campos_do_usuario(request.user, cfg_crm)
    campos_disponiveis = [
        {'slug': slug, 'label': label, 'categoria': cat, 'icone': icone,
         'categoria_label': CATEGORIAS_LABEL.get(cat, cat)}
        for slug, label, cat, icone in CAMPOS_CARD_DISPONIVEIS
    ]

    # Origens HubSoft (cliente + servico) - do cache pra select do modal "Nova oportunidade"
    opcoes_origens_cliente = []
    opcoes_origens_servico = []
    try:
        from apps.integracoes.models import IntegracaoAPI
        integ_hs = IntegracaoAPI.all_tenants.filter(
            tenant=request.tenant, tipo='hubsoft', ativa=True,
        ).first()
        if integ_hs:
            cache_hs = (integ_hs.configuracoes_extras or {}).get('cache') or {}
            for it in (cache_hs.get('origens_cliente') or []):
                if it.get('id_origem_cliente') is not None:
                    opcoes_origens_cliente.append({
                        'id': int(it['id_origem_cliente']),
                        'nome': it.get('descricao') or it.get('nome') or f'#{it["id_origem_cliente"]}',
                    })
            for it in (cache_hs.get('origens_contato') or []):
                if it.get('id_origem_contato') is not None:
                    opcoes_origens_servico.append({
                        'id': int(it['id_origem_contato']),
                        'nome': it.get('descricao') or it.get('nome') or f'#{it["id_origem_contato"]}',
                    })
            opcoes_origens_cliente.sort(key=lambda x: x['nome'])
            opcoes_origens_servico.sort(key=lambda x: x['nome'])
    except Exception:
        pass

    context = {
        'estagios': estagios,
        'vendedores': vendedores,
        'tags': tags,
        'pipelines': pipelines,
        'pipeline_atual': pipeline_atual,
        'filter_fields': filter_fields,
        'motivos_perda_json': json.dumps(motivos_perda, ensure_ascii=False),
        'motivo_perda_obrigatorio': motivo_perda_obrigatorio,
        'motivo_perda_pede_concorrente': motivo_perda_pede_concorrente,
        'page_title': f'Pipeline: {pipeline_atual.nome}' if pipeline_atual else 'Pipeline CRM',
        'campos_visiveis_json': json.dumps(campos_visiveis, ensure_ascii=False),
        'campos_disponiveis_json': json.dumps(campos_disponiveis, ensure_ascii=False),
        'campos_max': MAX_CAMPOS_VISIVEIS,
        'opcoes_origens_cliente': opcoes_origens_cliente,
        'opcoes_origens_servico': opcoes_origens_servico,
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

    # com_valor_estimado() anota `valor_estimado_anotado` (SUM dos itens com
    # fallback no manual) e evita N+1 ao ler op.valor_estimado em cada card
    qs = OportunidadeVenda.objects.com_valor_estimado().filter(ativo=True).select_related(
        'lead', 'estagio', 'responsavel', 'plano_interesse', 'pipeline'
    ).prefetch_related('tarefas', 'tags', 'itens')

    if pipeline_id:
        qs = qs.filter(pipeline_id=pipeline_id)

    # Regra de visibilidade por escopo (ve tudo / equipe / so as suas)
    esc = escopo_responsaveis(request)
    if esc is not None:
        qs = qs.filter(responsavel_id__in=esc)

    tag = request.GET.get('tag', '').strip()
    valor_range = request.GET.get('valor', '').strip()
    # Filtros novos (Sprint 5 — origem/atribuicao). Multi-valor via getlist.
    canais = [c for c in request.GET.getlist('canal') if c]
    fontes = [f for f in request.GET.getlist('fonte') if f]
    campanhas = [c for c in request.GET.getlist('campanha') if c]

    if responsavel_id == 'sem':
        # Valor especial do filtro: so oportunidades sem dono (pedido da Gabi
        # pra cobrar atribuicao a partir do resumo diario)
        qs = qs.filter(responsavel__isnull=True)
    elif responsavel_id:
        qs = qs.filter(responsavel_id=responsavel_id)
    if prioridade:
        qs = qs.filter(prioridade=prioridade)
    estagio_filtro = request.GET.get('estagio')
    if estagio_filtro:
        qs = qs.filter(estagio_id=estagio_filtro)
    periodo = request.GET.get('periodo')
    if periodo and periodo.isdigit():
        from django.utils import timezone as _tz
        from datetime import timedelta as _td
        qs = qs.filter(data_criacao__gte=_tz.now() - _td(days=int(periodo)))
    if tag:
        qs = qs.filter(tags__nome=tag)
    if canais:
        # canal pode estar no lead (canal — first-touch) ou na op (canal_atribuicao — last-touch).
        # Filtra pela atribuicao (mais especifico) com fallback no lead.
        from django.db.models import Q
        qs = qs.filter(Q(canal_atribuicao__in=canais) | (Q(canal_atribuicao__isnull=True) & Q(lead__canal__in=canais)))
    if fontes:
        from django.db.models import Q
        qs = qs.filter(Q(fonte_atribuicao__in=fontes) | (Q(fonte_atribuicao__isnull=True) & Q(lead__fonte__in=fontes)))
    if campanhas:
        from django.db.models import Q
        try:
            campanhas_ids = [int(c) for c in campanhas]
            qs = qs.filter(Q(campanha_atribuicao_id__in=campanhas_ids) | (Q(campanha_atribuicao__isnull=True) & Q(lead__campanha_origem_id__in=campanhas_ids)))
        except (ValueError, TypeError):
            pass
    if valor_range:
        # valor_estimado virou property — usar annotate via com_valor_estimado()
        qs = qs.com_valor_estimado()
        if valor_range == '1000+':
            qs = qs.filter(valor_estimado_anotado__gte=1000)
        elif '-' in valor_range:
            parts = valor_range.split('-')
            qs = qs.filter(
                valor_estimado_anotado__gte=Decimal(parts[0]),
                valor_estimado_anotado__lte=Decimal(parts[1]),
            )
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

    # Verificar permissão por escopo. Oportunidade sem dono continua movivel
    # por qualquer um (nao ha responsavel a proteger).
    esc = escopo_responsaveis(request)
    if esc is not None and oportunidade.responsavel_id and oportunidade.responsavel_id not in esc:
        return JsonResponse({'ok': False, 'erro': 'Sem permissão para mover esta oportunidade'}, status=403)

    if oportunidade.estagio_id == estagio_novo_id:
        return JsonResponse({'ok': True, 'mensagem': 'Sem mudança de estágio'})

    # Pre-preenche os campos enviados no body ANTES da validacao de campos
    # obrigatorios (assim o usuario consegue mover preenchendo no mesmo POST,
    # sem precisar de chamada extra pra salvar antes).
    if estagio_novo.is_final_perdido:
        motivo_ref_body = data.get('motivo_perda_ref_id') or None
        if motivo_ref_body:
            oportunidade.motivo_perda_ref_id = motivo_ref_body
        motivo_categoria_body = (data.get('motivo_perda_categoria') or '').strip()
        if motivo_categoria_body:
            oportunidade.motivo_perda_categoria = motivo_categoria_body
        motivo_texto_body = (data.get('motivo_perda') or '').strip()
        if motivo_texto_body:
            oportunidade.motivo_perda = motivo_texto_body

    # Gate de campos obrigatorios — bloqueia avanco se faltarem campos
    from apps.comercial.crm.services.requisitos_estagio import campos_faltando
    faltantes = campos_faltando(oportunidade, estagio_novo)
    if faltantes:
        return JsonResponse({
            'ok': False,
            'erro': f'Campos obrigatorios faltando para entrar em "{estagio_novo.nome}".',
            'codigo': 'campos_obrigatorios_faltando',
            'campos_faltando': [{'codigo': c, 'label': l} for c, l in faltantes],
        }, status=400)

    # T2 — Validacao: se estagio destino e final de perda + config exige motivo,
    # rejeita 400 sem motivo. Aceita motivo via body do request ou ja persistido.
    motivo_perda_ref_id = data.get('motivo_perda_ref_id') or None
    motivo_perda_texto = (data.get('motivo_perda') or '').strip()
    concorrente_perdido = (data.get('concorrente_perdido') or '').strip()

    if estagio_novo.is_final_perdido:
        config = ConfiguracaoCRM.get_config()
        if config and config.motivo_perda_obrigatorio:
            tem_motivo_body = bool(motivo_perda_ref_id) or bool(motivo_perda_texto)
            tem_motivo_persistido = bool(oportunidade.motivo_perda_ref_id) or bool((oportunidade.motivo_perda or '').strip())
            if not tem_motivo_body and not tem_motivo_persistido:
                return JsonResponse({
                    'ok': False,
                    'erro': 'Motivo de perda e obrigatorio para mover ao estagio Perdida (configuracao do CRM).',
                    'codigo': 'motivo_perda_obrigatorio',
                }, status=400)

    # Calcular tempo no estágio atual
    horas_no_estagio = (timezone.now() - oportunidade.data_entrada_estagio).total_seconds() / 3600

    estagio_anterior = oportunidade.estagio

    # Registrar histórico
    HistoricoPipelineEstagio.objects.create(
        tenant=oportunidade.tenant,
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

    # Fechamento real vale pros DOIS finais (ganho E perdido) — metricas de
    # perda por periodo dependem disso. Meta de venda so em ganho.
    if (estagio_novo.is_final_ganho or estagio_novo.is_final_perdido) and not oportunidade.data_fechamento_real:
        oportunidade.data_fechamento_real = timezone.now()
        campos.append('data_fechamento_real')
        if estagio_novo.is_final_ganho:
            _atualizar_meta_venda(oportunidade, request.user)

    # T2 — Se foi pra estagio de perda e veio motivo no body, persiste tambem
    if estagio_novo.is_final_perdido:
        motivo_perda_categoria = (data.get('motivo_perda_categoria') or '').strip()
        if motivo_perda_categoria:
            oportunidade.motivo_perda_categoria = motivo_perda_categoria
            campos.append('motivo_perda_categoria')
        if motivo_perda_ref_id:
            oportunidade.motivo_perda_ref_id = motivo_perda_ref_id
            campos.append('motivo_perda_ref')
        if motivo_perda_texto:
            oportunidade.motivo_perda = motivo_perda_texto
            campos.append('motivo_perda')
        if concorrente_perdido:
            oportunidade.concorrente_perdido = concorrente_perdido
            campos.append('concorrente_perdido')

    oportunidade.save(update_fields=campos)

    # Op REABERTA (saiu de estagio final pra ativo): reavalia regras do motor.
    # Sem isso, edicoes feitas enquanto a op estava em Perdido/Ganho nunca
    # sincronizam com o HubSoft — o motor pula estagios finais e o signal de
    # op so dispara na criacao. Caso real: lead 1955 (CPF corrigido com op em
    # Perdido; HubSoft ficou com CPF antigo e bot nao converteu).
    reaberta = (
        (estagio_anterior.is_final_ganho or estagio_anterior.is_final_perdido)
        and not (estagio_novo.is_final_ganho or estagio_novo.is_final_perdido)
    )
    if reaberta:
        try:
            from apps.comercial.crm.services.automacao_pipeline import processar_seguro
            processar_seguro(oportunidade=oportunidade)
        except Exception:
            logger.warning('[CRM] Reavaliacao pos-reabertura falhou (op=%s)', oportunidade.pk, exc_info=True)

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

    # Log de auditoria
    from apps.sistema.utils import registrar_acao
    registrar_acao('crm', 'mover', 'oportunidade', oportunidade.pk,
                   f'{oportunidade.lead.nome_razaosocial}: {estagio_anterior.nome} -> {estagio_novo.nome}',
                   request=request, dados_extras={'estagio_de': estagio_anterior.slug, 'estagio_para': estagio_novo.slug})

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

    # com_valor_estimado() pra evitar N+1 ao ler op.valor_estimado em cada linha
    qs = OportunidadeVenda.objects.com_valor_estimado().filter(ativo=True).select_related(
        'lead', 'estagio', 'responsavel'
    ).prefetch_related('tags').order_by('estagio__ordem', '-data_criacao')

    esc = escopo_responsaveis(request)
    if esc is not None:
        qs = qs.filter(responsavel_id__in=esc)

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
    if responsavel_id == 'sem':
        qs = qs.filter(responsavel__isnull=True)
    elif responsavel_id:
        qs = qs.filter(responsavel_id=responsavel_id)
    if tag_nome:
        qs = qs.filter(tags__nome=tag_nome)

    estagios = PipelineEstagio.objects.filter(ativo=True).order_by('ordem')
    tags = TagCRM.objects.all().order_by('nome')

    from django.contrib.auth.models import User
    vendedores = []
    for u in User.objects.filter(is_active=True, perfil__tenant=request.tenant).order_by('first_name'):
        vendedores.append({'id': u.pk, 'nome': u.get_full_name() or u.username})

    filter_fields = [
        {'type': 'select', 'label': 'Estagio', 'name': 'estagio', 'value': estagio_id or '',
         'options': [('', 'Todos')] + [(str(e.pk), e.nome) for e in estagios]},
        {'type': 'select', 'label': 'Responsavel', 'name': 'responsavel', 'value': responsavel_id or '',
         'options': [('', 'Todos'), ('sem', '— Sem responsavel —')] + [(str(v['id']), v['nome']) for v in vendedores]},
        {'type': 'select', 'label': 'Tag', 'name': 'tag', 'value': tag_nome,
         'options': [('', 'Todas')] + [(t.nome, t.nome) for t in tags]},
    ]

    active_filters_count = sum(1 for v in [estagio_id, responsavel_id, tag_nome] if v) + (1 if search else 0)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    query_params = request.GET.copy()
    query_params.pop('page', None)
    query = query_params.urlencode()

    context = {
        'oportunidades': page_obj,
        'page_obj': page_obj,
        'query': query,
        'estagios': estagios,
        'tags': tags,
        'vendedores': vendedores,
        'filter_fields': filter_fields,
        'active_filters_count': active_filters_count,
        'filtro_search': search,
        'filtro_estagio': estagio_id,
        'filtro_responsavel': responsavel_id,
        'filtro_tag': tag_nome,
        'total_oportunidades': qs.count(),
        'page_title': 'Oportunidades',
    }
    return render(request, 'crm/oportunidades_lista.html', context)


@login_required
def central_acoes_view(request):
    """Central de Acoes: "o que fazer agora" priorizado, escopado por papel
    (vendedor ve o dele, gerente ve o do time) via escopo_responsaveis."""
    denied = _check_perm(request, 'comercial.ver_pipeline')
    if denied:
        return denied
    from apps.comercial.crm.central_acoes import (
        coletar_acoes, kpis_comerciais, tabela_operacional, opcoes_filtro)
    is_fragment = bool(request.GET.get('fragment'))
    dados = coletar_acoes(request)
    ctx = {
        'page_title': 'Central de Acoes',
        'kpis': kpis_comerciais(request),
        'colunas': dados['colunas'],
        'contadores': dados['contadores'],
        've_time': dados['ve_time'],
        'tabela': tabela_operacional(request),
    }
    if not is_fragment:
        ctx['filtro'] = opcoes_filtro(request)
    return render(request, 'crm/_ca_conteudo.html' if is_fragment else 'crm/central_acoes.html', ctx)


def _tenant_tem_origens(request):
    """(tem_origens_cliente, tem_origens_servico) do cache HubSoft do tenant.

    Origem so vira obrigatoria onde ha o que escolher: tenant sem HubSoft tem
    dropdown vazio (so o '— sem definir —') e travar ali impediria criar
    qualquer oportunidade manual."""
    try:
        from apps.integracoes.models import IntegracaoAPI
        integ = IntegracaoAPI.all_tenants.filter(
            tenant=request.tenant, tipo='hubsoft', ativa=True,
        ).first()
        if not integ:
            return (False, False)
        cache_hs = (integ.configuracoes_extras or {}).get('cache') or {}
        return (bool(cache_hs.get('origens_cliente')), bool(cache_hs.get('origens_contato')))
    except Exception:
        return (False, False)


@login_required
@require_http_methods(["POST"])
@auditar('crm', 'criar', 'oportunidade')
def api_criar_oportunidade(request):
    """Cria oportunidade manualmente com lead novo ou existente."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'erro': 'JSON invalido'}, status=400)

    nome = body.get('nome', '').strip()
    telefone = body.get('telefone', '').strip()
    titulo = body.get('titulo', '').strip()
    responsavel_id = body.get('responsavel_id')
    cidade = (body.get('cidade') or '').strip()
    id_origem = (body.get('id_origem') or '').strip()
    id_origem_servico = (body.get('id_origem_servico') or '').strip()

    if not nome or not telefone:
        return JsonResponse({'ok': False, 'erro': 'Nome e telefone sao obrigatorios'}, status=400)

    # Origem obrigatoria so onde o tenant tem origens configuradas (HubSoft).
    tem_org_cli, tem_org_serv = _tenant_tem_origens(request)
    if tem_org_cli and not id_origem:
        return JsonResponse({'ok': False, 'erro': 'Origem do cliente e obrigatoria'}, status=400)
    if tem_org_serv and not id_origem_servico:
        return JsonResponse({'ok': False, 'erro': 'Origem do contato e obrigatoria'}, status=400)

    from apps.comercial.leads.models import LeadProspecto
    # Buscar ou criar lead
    defaults_lead = {'nome_razaosocial': nome, 'origem': 'manual'}
    if cidade: defaults_lead['cidade'] = cidade
    if id_origem: defaults_lead['id_origem'] = id_origem
    if id_origem_servico: defaults_lead['id_origem_servico'] = id_origem_servico
    lead, created = LeadProspecto.objects.get_or_create(
        telefone=telefone,
        defaults=defaults_lead,
    )
    # Atualiza campos no lead existente quando vierem preenchidos no payload
    update_lead = []
    if not created and not lead.nome_razaosocial:
        lead.nome_razaosocial = nome
        update_lead.append('nome_razaosocial')
    if cidade and lead.cidade != cidade:
        lead.cidade = cidade
        update_lead.append('cidade')
    if id_origem and lead.id_origem != id_origem:
        lead.id_origem = id_origem
        update_lead.append('id_origem')
    if id_origem_servico and lead.id_origem_servico != id_origem_servico:
        lead.id_origem_servico = id_origem_servico
        update_lead.append('id_origem_servico')
    if update_lead:
        lead.save(update_fields=update_lead)

    # Verificar se lead ja tem oportunidade
    if OportunidadeVenda.objects.filter(lead=lead).exists():
        return JsonResponse({'ok': False, 'erro': 'Este lead ja possui uma oportunidade'}, status=400)

    # Primeiro estagio do pipeline padrao
    pipeline = Pipeline.objects.filter(padrao=True).first() or Pipeline.objects.first()
    estagio = PipelineEstagio.objects.filter(pipeline=pipeline, ativo=True).order_by('ordem').first()
    if not estagio:
        return JsonResponse({'ok': False, 'erro': 'Nenhum estagio disponivel'}, status=400)

    # Responsavel default = quem criou. Diagnostico de 08/07: 9 ops manuais
    # orfas porque o campo e opcional e a distribuicao automatica nao cobria
    # (vendedora criava o card e ele sumia da propria visao, ja que op sem
    # dono so aparece pra admin). Escolher outra pessoa no form segue valendo.
    oport = OportunidadeVenda.objects.create(
        pipeline=pipeline,
        lead=lead,
        estagio=estagio,
        titulo=titulo or nome,
        responsavel_id=responsavel_id or request.user.pk,
        criado_por=request.user,
        origem_crm='manual',
    )

    try:
        from apps.sistema.utils import registrar_acao
        registrar_acao(
            'crm', 'atribuir', 'oportunidade', oport.pk,
            f"Responsavel atribuido na criacao manual: "
            f"{oport.responsavel.get_full_name() or oport.responsavel.username}",
            request=request,
        )
    except Exception:
        pass

    return JsonResponse({'ok': True, 'id': oport.pk})


@login_required
@require_http_methods(["PUT"])
@auditar('crm', 'editar', 'oportunidade')
def api_editar_oportunidade(request, pk):
    """API para editar campos da oportunidade e do lead inline."""
    try:
        oport = OportunidadeVenda.objects.select_related('lead').get(pk=pk)
    except OportunidadeVenda.DoesNotExist:
        return JsonResponse({'error': 'Oportunidade nao encontrada'}, status=404)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    # Campos financeiros gated por permissao comercial.editar_valor_oportunidade
    pode_editar_valor = user_tem_funcionalidade(request, 'comercial.editar_valor_oportunidade') or request.user.is_superuser
    campos_oport = [
        'titulo', 'prioridade',
        'origem_crm', 'data_fechamento_previsto',
        'motivo_perda', 'motivo_perda_categoria',
        'motivo_ganho_categoria', 'concorrente_perdido',
    ]
    if pode_editar_valor:
        campos_oport += ['valor_estimado', 'probabilidade']
    campos_lead = [
        'nome_razaosocial', 'email', 'telefone', 'cpf_cnpj', 'rg',
        'data_nascimento',
        'cidade', 'estado', 'cep', 'rua', 'numero_residencia', 'complemento',
        'bairro',
        'empresa', 'observacoes', 'origem', 'canal_entrada',
        'score_qualificacao', 'score_status',
        'id_origem', 'id_origem_servico',
    ]

    oport_atualizados = []
    lead_atualizados = []

    # Snapshot dos campos de endereco antes do save (pra detectar mudanca e disparar viabilidade)
    CAMPOS_ENDERECO_TRIGGER = ('cep', 'rua', 'numero_residencia', 'bairro', 'cidade', 'estado')
    snapshot_endereco = {}
    if oport.lead:
        for c in CAMPOS_ENDERECO_TRIGGER:
            snapshot_endereco[c] = (getattr(oport.lead, c, '') or '')

    for campo, valor in data.items():
        if campo.startswith('dados_custom.'):
            # Campo custom da oportunidade
            custom_key = campo.replace('dados_custom.', '')
            custom = oport.dados_custom or {}
            custom[custom_key] = valor
            oport.dados_custom = custom
            if 'dados_custom' not in oport_atualizados:
                oport_atualizados.append('dados_custom')
        elif campo == 'motivo_perda_ref':
            from .models import MotivoPerda
            oport.motivo_perda_ref = (
                MotivoPerda.objects.filter(pk=valor).first() if valor else None
            )
            oport_atualizados.append('motivo_perda_ref')
        elif campo in campos_oport and hasattr(oport, campo):
            if campo in ('valor_estimado', 'probabilidade') and not valor:
                valor = None
            if campo == 'data_fechamento_previsto' and not valor:
                valor = None
            setattr(oport, campo, valor)
            oport_atualizados.append(campo)
        elif campo in campos_lead and oport.lead and hasattr(oport.lead, campo):
            if campo in ('data_nascimento', 'score_qualificacao') and not valor:
                valor = None
            if campo == 'score_status':
                valor_atual = getattr(oport.lead, 'score_status', 'nao_consultado')
                if valor != valor_atual:
                    oport.lead.score_atualizado_em = timezone.now()
                    oport.lead.score_atualizado_por = request.user if request.user.is_authenticated else None
                    if 'score_atualizado_em' not in lead_atualizados:
                        lead_atualizados.extend(['score_atualizado_em', 'score_atualizado_por'])
            setattr(oport.lead, campo, valor)
            lead_atualizados.append(campo)

    if oport_atualizados:
        oport.save(update_fields=oport_atualizados)
    if lead_atualizados and oport.lead:
        oport.lead.save(update_fields=lead_atualizados)

    from apps.sistema.utils import registrar_acao
    todos = oport_atualizados + lead_atualizados
    if todos:
        registrar_acao('crm', 'editar', 'oportunidade', oport.pk,
                       f'Campos atualizados: {", ".join(todos)}', request=request)

    # Trigger viabilidade quando qualquer campo do endereco mudou. Service auto-preenche
    # campos faltantes via ViaCEP — basta CEP pra disparar.
    viabilidade_payload = None
    endereco_mudou = oport.lead and any(
        c in lead_atualizados and snapshot_endereco.get(c, '') != (getattr(oport.lead, c, '') or '')
        for c in CAMPOS_ENDERECO_TRIGGER
    )
    if endereco_mudou and oport.lead and (oport.lead.cep or ''):
        try:
            from apps.comercial.viabilidade.services import consultar_viabilidade
            resultado = consultar_viabilidade(
                oport.tenant,
                cep=oport.lead.cep or '',
                logradouro=oport.lead.rua or '',
                numero=oport.lead.numero_residencia or '',
                bairro=oport.lead.bairro or '',
                cidade=oport.lead.cidade or '',
                uf=oport.lead.estado or '',
            )
            if resultado.status != 'nao_consultado':
                # Persistir tambem campos auto-preenchidos no lead (ViaCEP enriqueceu)
                lead_extras = []
                for campo_ext, valor_ext in (resultado.auto_preenchido or {}).items():
                    nome_attr = {
                        'logradouro': 'rua',
                        'bairro': 'bairro',
                        'cidade': 'cidade',
                        'uf': 'estado',
                    }.get(campo_ext)
                    if nome_attr and not getattr(oport.lead, nome_attr, ''):
                        setattr(oport.lead, nome_attr, valor_ext)
                        lead_extras.append(nome_attr)
                dc = oport.lead.dados_custom or {}
                dc['viabilidade'] = resultado.to_dict()
                oport.lead.dados_custom = dc
                save_fields = ['dados_custom'] + lead_extras
                oport.lead.save(update_fields=save_fields)
                viabilidade_payload = resultado.to_dict()
                registrar_acao(
                    'crm', 'viabilidade_consultada', 'oportunidade', oport.pk,
                    f'CEP {resultado.cep_consultado} -> {resultado.status} '
                    f'({resultado.cidade}/{resultado.uf}) via {resultado.fonte}',
                    request=request,
                )
        except Exception:
            logger.exception('Erro ao consultar viabilidade pro lead %s', oport.lead_id)

    return JsonResponse({
        'success': True,
        'campos': todos,
        'viabilidade': viabilidade_payload,
    })


@login_required
@require_http_methods(["DELETE"])
@auditar('crm', 'excluir', 'oportunidade')
def api_excluir_oportunidade(request, pk):
    """Exclui permanentemente uma oportunidade (CASCADE em tarefas, notas, itens, historico)."""
    denied = _check_perm(request, 'comercial.excluir_oportunidade')
    if denied:
        return denied

    try:
        oport = OportunidadeVenda.objects.get(pk=pk)
    except OportunidadeVenda.DoesNotExist:
        return JsonResponse({'error': 'Oportunidade nao encontrada'}, status=404)

    titulo = oport.titulo or f'Oportunidade #{oport.pk}'
    lead_nome = oport.lead.nome_razaosocial if oport.lead else '-'
    oport.delete()

    return JsonResponse({
        'success': True,
        'message': f'Oportunidade "{titulo}" (lead: {lead_nome}) excluida com sucesso.',
    })


@login_required
def oportunidade_detalhe(request, pk):
    from .models import MotivoPerda
    oportunidade = get_object_or_404(
        OportunidadeVenda.objects.select_related(
            'lead', 'estagio', 'responsavel', 'plano_interesse', 'criado_por'
        ).prefetch_related('tags', 'notas__autor', 'tarefas__responsavel'),
        pk=pk
    )

    lead = oportunidade.lead

    # Dados cross-app (sem duplicar, apenas consultando)
    from apps.comercial.leads.models import HistoricoContato
    historico_contatos = list(
        HistoricoContato.objects.filter(lead=lead).order_by('-data_hora_contato')[:20]
    )
    # Ids de midia do WhatsApp (wamid...) sao tokens gigantes que estouram o
    # layout da timeline e nao dizem nada pro usuario. Troca por rotulo
    # legivel SO na exibicao (nao altera o banco).
    import re as _re
    _wamid_re = _re.compile(r'\S*wamid\.\S+')
    for _hc in historico_contatos:
        if _hc.observacoes and 'wamid.' in _hc.observacoes:
            _hc.observacoes = _wamid_re.sub('[midia recebida]', _hc.observacoes)
        if _hc.ultima_mensagem and 'wamid.' in _hc.ultima_mensagem:
            _hc.ultima_mensagem = _wamid_re.sub('[midia recebida]', _hc.ultima_mensagem)

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

    # Timeline de automações (engine nova) para este lead. Adaptador SimpleNamespace
    # expõe os campos que o template espera (regra.nome, status, resultado…) sem mudar o HTML.
    from apps.automacao.models import ExecucaoFluxo
    from types import SimpleNamespace
    logs_automacao = [
        SimpleNamespace(
            data_execucao=ex.criado_em,
            status=ex.status,
            get_status_display=ex.get_status_display(),
            regra=SimpleNamespace(nome=ex.fluxo.nome if ex.fluxo_id else '(fluxo removido)'),
            acao=None, nodo=None,
            resultado=(ex.erro or ''),
        )
        for ex in (ExecucaoFluxo.all_tenants
                   .filter(tenant=request.tenant, lead=lead)
                   .select_related('fluxo').order_by('-criado_em')[:20])
    ]

    # Conversas e mensagens do Inbox
    from apps.inbox.models import Conversa, Mensagem
    conversas_inbox = Conversa.objects.filter(lead=lead).order_by('-ultima_mensagem_em')
    mensagens_inbox = []
    if conversas_inbox.exists():
        conversa_ids = conversas_inbox.values_list('id', flat=True)
        mensagens_inbox = Mensagem.objects.filter(
            conversa_id__in=conversa_ids
        ).order_by('data_envio')[:50]

    from apps.comercial.crm.models import Venda
    vendas_oportunidade = Venda.objects.filter(oportunidade=oportunidade).select_related('plano').order_by('data_venda')

    # OS e Contratos do lead (pos-venda)
    os_tentativas = []
    contrato_tentativas = []
    try:
        from apps.integracoes.models import OrdemServicoTentativa, ContratoTentativa
        os_tentativas = list(OrdemServicoTentativa.objects.filter(
            lead=lead,
        ).order_by('-criado_em')[:10])
        contrato_tentativas = list(ContratoTentativa.objects.filter(
            lead=lead,
        ).order_by('-criado_em')[:10])
    except Exception:
        pass

    # Proxima tarefa pendente (ordena por vencimento mais proximo)
    from django.db.models import F
    proxima_tarefa = oportunidade.tarefas.filter(
        status__in=['pendente', 'em_andamento', 'vencida'],
    ).select_related('responsavel').order_by(
        F('data_vencimento').asc(nulls_last=True),
        '-prioridade',
    ).first() if hasattr(oportunidade, 'tarefas') else None

    # Timeline mesclada: estágios + contatos + conversas + vendas + OS + contratos
    timeline_items = []
    for he in historico_estagios:
        timeline_items.append({
            'tipo': 'estagio',
            'data': he.data_transicao,
            'obj': he,
        })
    for hc in historico_contatos:
        timeline_items.append({
            'tipo': 'contato',
            'data': hc.data_hora_contato,
            'obj': hc,
        })
    for c in conversas_inbox:
        timeline_items.append({
            'tipo': 'conversa_aberta',
            'data': c.data_abertura,
            'canal': c.canal.nome if c.canal else 'Chat',
            'numero': c.numero,
            'status': c.status,
        })
        if c.data_resolucao:
            timeline_items.append({
                'tipo': 'conversa_resolvida',
                'data': c.data_resolucao,
                'canal': c.canal.nome if c.canal else 'Chat',
                'numero': c.numero,
                'agente': c.agente.get_full_name() or c.agente.username if c.agente else None,
            })
    for v in vendas_oportunidade:
        timeline_items.append({
            'tipo': 'venda_criada',
            'data': v.data_venda,
            'obj': v,
        })
    for t in os_tentativas:
        timeline_items.append({
            'tipo': 'os',
            'data': t.criado_em,
            'obj': t,
        })
    for t in contrato_tentativas:
        timeline_items.append({
            'tipo': 'contrato',
            'data': t.criado_em,
            'obj': t,
        })
    for log in logs_automacao:
        timeline_items.append({
            'tipo': 'automacao',
            'data': log.data_execucao,
            'obj': log,
        })
    # Tarefas concluidas/pendentes tambem entram
    for tarefa in oportunidade.tarefas.all() if hasattr(oportunidade, 'tarefas') else []:
        timeline_items.append({
            'tipo': 'tarefa',
            'data': tarefa.data_conclusao or tarefa.data_vencimento or tarefa.data_criacao,
            'obj': tarefa,
        })
    # Notas tambem
    for nota in oportunidade.notas.select_related('autor').all():
        timeline_items.append({
            'tipo': 'nota',
            'data': nota.data_criacao,
            'obj': nota,
        })
    # Logs de atribuicao de responsavel (via UI ou cron sync_vendedores_matrix).
    # LogSistema.usuario eh CharField (nao FK), entao select_related NAO pode
    # ser usado nesse campo (levaria FieldError e o try/except silenciava tudo).
    try:
        from apps.sistema.models import LogSistema
        logs_atribuicao = LogSistema.objects.filter(
            tenant=request.tenant, entidade='oportunidade',
            entidade_id=oportunidade.pk, categoria='crm', acao='atribuir',
        ).order_by('-data_criacao')[:20]
        for log in logs_atribuicao:
            timeline_items.append({
                'tipo': 'atribuicao',
                'data': log.data_criacao,
                'obj': log,
            })
    except Exception:
        pass
    timeline_items.sort(key=lambda x: x['data'], reverse=True)

    # Estagios do mesmo pipeline da oportunidade (pra stage progress bar)
    estagios_pipeline = []
    cta_proximo = None
    cta_ganho = None
    cta_perdido = None
    if oportunidade.estagio_id:
        estagios_pipeline = list(PipelineEstagio.objects.filter(
            pipeline=oportunidade.estagio.pipeline, ativo=True,
        ).order_by('ordem'))
        # CTA "Avancar": proximo estagio na ordem, nao-final
        estagio_atual_idx = next(
            (i for i, e in enumerate(estagios_pipeline) if e.pk == oportunidade.estagio_id),
            -1,
        )
        if estagio_atual_idx >= 0:
            for e in estagios_pipeline[estagio_atual_idx + 1:]:
                if not e.is_final_ganho and not e.is_final_perdido:
                    cta_proximo = e
                    break
        # CTA "Marcar venda/perda": estagios finais do pipeline
        for e in estagios_pipeline:
            if e.is_final_ganho and not cta_ganho:
                cta_ganho = e
            if e.is_final_perdido and not cta_perdido:
                cta_perdido = e
        # Se ja esta num estagio final, nao oferecer o mesmo
        if oportunidade.estagio.is_final_ganho:
            cta_ganho = None
        if oportunidade.estagio.is_final_perdido:
            cta_perdido = None

    # Anexos do lead — consolidando DocumentoLead (upload manual base64) +
    # ImagemLeadProspecto (URLs vindas do bot Matrix) + anexos de contratos
    anexos = []
    try:
        from apps.comercial.cadastro.models import DocumentoLead
        for d in DocumentoLead.objects.filter(lead=lead).order_by('-data_upload')[:20]:
            anexos.append({
                'tipo': 'documento_lead',
                'nome': d.nome_arquivo or d.get_tipo_documento_display(),
                'rotulo_tipo': d.get_tipo_documento_display(),
                'status': d.status,
                'status_display': d.get_status_display(),
                'tamanho_bytes': d.tamanho_arquivo,
                'data': d.data_upload,
                'pk': d.pk,
                'url': d.get_imagem_url_data() if d.formato_arquivo in ('jpg', 'jpeg', 'png', 'webp') else None,
            })
    except Exception:
        pass
    # ImagemLeadProspecto (URLs externas do Matrix CDN) — populadas pelo bot
    try:
        from apps.comercial.leads.utils import resolver_link_interno_imagem
    except Exception:
        resolver_link_interno_imagem = None
    LABEL_TIPO_IMAGEM = {
        'selfie_com_doc': 'Selfie com documento',
        'frente_doc': 'Documento (frente)',
        'verso_doc': 'Documento (verso)',
        'comprovante_residencia': 'Comprovante de residencia',
        'contrato_assinado': 'Contrato assinado',
        'outro': 'Outro',
    }
    STATUS_IMAGEM_PRA_DOC = {
        'pendente': 'pendente',
        'documentos_validos': 'aprovado',
        'documentos_rejeitados': 'rejeitado',
    }
    STATUS_IMAGEM_DISPLAY = {
        'pendente': 'Pendente',
        'documentos_validos': 'Aprovado',
        'documentos_rejeitados': 'Rejeitado',
    }
    for img in lead.imagens.all().order_by('-data_criacao')[:20]:
        desc = (img.descricao or '').strip().lower()
        rotulo = LABEL_TIPO_IMAGEM.get(desc, img.descricao or 'Imagem do lead')
        link = img.link_url or ''
        if resolver_link_interno_imagem:
            try:
                link = resolver_link_interno_imagem(img) or link
            except Exception:
                pass
        anexos.append({
            'tipo': 'imagem_lead',
            'nome': rotulo,
            'rotulo_tipo': rotulo,
            'status': STATUS_IMAGEM_PRA_DOC.get(img.status_validacao, img.status_validacao),
            'status_display': STATUS_IMAGEM_DISPLAY.get(img.status_validacao, img.status_validacao),
            'tamanho_bytes': 0,
            'data': img.data_criacao,
            'pk': img.pk,
            'url': link,
        })
    # Anexos enviados nas tentativas de contrato
    for ct in contrato_tentativas:
        if ct.anexos_enviados:
            for a in ct.anexos_enviados:
                anexos.append({
                    'tipo': 'contrato_anexo',
                    'nome': a.get('nome', '(sem nome)'),
                    'rotulo_tipo': 'Anexo de contrato',
                    'status': 'enviado' if ct.status == 'sucesso' else 'tentativa',
                    'status_display': ct.get_status_display(),
                    'tamanho_bytes': a.get('tamanho_bytes', 0),
                    'data': ct.criado_em,
                    'pk': None,
                    'url': None,
                    'contrato_grupo_id': ct.grupo_tentativas_id,
                })
    anexos.sort(key=lambda x: x['data'], reverse=True)

    # Origens HubSoft (cliente + servico) - do cache da IntegracaoAPI HubSoft do tenant.
    # Usado pelo modal "Editar oportunidade" pra select dos campos id_origem e id_origem_servico do lead.
    opcoes_origens_cliente = []
    opcoes_origens_servico = []
    try:
        from apps.integracoes.models import IntegracaoAPI
        integ_hs = IntegracaoAPI.all_tenants.filter(
            tenant=request.tenant, tipo='hubsoft', ativa=True,
        ).first()
        if integ_hs:
            cache_hs = (integ_hs.configuracoes_extras or {}).get('cache') or {}
            for it in (cache_hs.get('origens_cliente') or []):
                if it.get('id_origem_cliente') is not None:
                    opcoes_origens_cliente.append({
                        'id': int(it['id_origem_cliente']),
                        'nome': it.get('descricao') or it.get('nome') or f'#{it["id_origem_cliente"]}',
                    })
            for it in (cache_hs.get('origens_contato') or []):
                if it.get('id_origem_contato') is not None:
                    opcoes_origens_servico.append({
                        'id': int(it['id_origem_contato']),
                        'nome': it.get('descricao') or it.get('nome') or f'#{it["id_origem_contato"]}',
                    })
            opcoes_origens_cliente.sort(key=lambda x: x['nome'])
            opcoes_origens_servico.sort(key=lambda x: x['nome'])
    except Exception:
        pass

    context = {
        'oportunidade': oportunidade,
        'lead': lead,
        'opcoes_origens_cliente': opcoes_origens_cliente,
        'opcoes_origens_servico': opcoes_origens_servico,
        'historico_contatos': historico_contatos,
        'cliente_hubsoft': cliente_hubsoft,
        'historico_estagios': historico_estagios,
        'logs_automacao': logs_automacao,
        'timeline_items': timeline_items,
        'estagios': estagios,
        'estagios_pipeline': estagios_pipeline,
        'vendedores': vendedores,
        'conversas_inbox': conversas_inbox,
        'mensagens_inbox': mensagens_inbox,
        'os_tentativas': os_tentativas,
        'contrato_tentativas': contrato_tentativas,
        'proxima_tarefa': proxima_tarefa,
        'anexos': anexos,
        'cta_proximo': cta_proximo,
        'cta_ganho': cta_ganho,
        'cta_perdido': cta_perdido,
        'pode_editar_valor': (user_tem_funcionalidade(request, 'comercial.editar_valor_oportunidade')
                              or request.user.is_superuser),
        'pode_adicionar_documento': (user_tem_funcionalidade(request, 'comercial.adicionar_documento_inline')
                                     or request.user.is_superuser),
        'pode_aprovar_documento': (user_tem_funcionalidade(request, 'comercial.aprovar_documento_inline')
                                   or request.user.is_superuser),
        'tipos_documento_choices': [
            ('selfie', 'Selfie com Documento'),
            ('doc_frente', 'Documento Frente'),
            ('doc_verso', 'Documento Verso'),
            ('comprovante_residencia', 'Comprovante de Residencia'),
            ('contrato_assinado', 'Contrato Assinado'),
            ('outro', 'Outro'),
        ],
        'motivos_perda': MotivoPerda.objects.filter(ativo=True).order_by('ordem', 'nome'),
        'motivo_perda_obrigatorio': bool(ConfiguracaoCRM.get_config() and ConfiguracaoCRM.get_config().motivo_perda_obrigatorio),
        'motivo_perda_pede_concorrente': bool(ConfiguracaoCRM.get_config() and ConfiguracaoCRM.get_config().motivo_perda_pede_concorrente),
        'estagios_perdidos_ids_json': json.dumps(list(estagios.filter(is_final_perdido=True).values_list('id', flat=True))),
        'page_title': f'CRM — {oportunidade.titulo or lead.nome_razaosocial}',
    }
    return render(request, 'crm/oportunidade_detalhe.html', context)


@login_required
@require_POST
@login_required
@require_http_methods(['GET', 'POST'])
def api_preferencia_kanban(request):
    """GET retorna campos atuais (com fallback em cascata).
    POST salva preferencia pessoal: {campos: ['nome','telefone',...]}.
    """
    from .cards_config import (
        CAMPOS_CARD_DISPONIVEIS, MAX_CAMPOS_VISIVEIS, CATEGORIAS_LABEL,
        campos_validos, resolver_campos_do_usuario,
    )
    from .models import PreferenciaUsuarioKanban, ConfiguracaoCRM
    cfg = ConfiguracaoCRM.get_config()

    if request.method == 'GET':
        atual = resolver_campos_do_usuario(request.user, cfg)
        pref = PreferenciaUsuarioKanban.objects.filter(user=request.user).first()
        tem_pref_pessoal = bool(pref and pref.campos)
        catalogo = [
            {'slug': slug, 'label': label, 'categoria': cat, 'icone': icone,
             'categoria_label': CATEGORIAS_LABEL.get(cat, cat)}
            for slug, label, cat, icone in CAMPOS_CARD_DISPONIVEIS
        ]
        return JsonResponse({
            'success': True,
            'campos_atuais': atual,
            'campos_disponiveis': catalogo,
            'max_campos': MAX_CAMPOS_VISIVEIS,
            'tem_preferencia_pessoal': tem_pref_pessoal,
            'campos_padrao_tenant': (cfg.campos_card_padrao if cfg else []) or [],
        })

    # POST — salva
    try:
        data = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'JSON invalido'}, status=400)
    campos = campos_validos(data.get('campos') or [])
    voltar_padrao = bool(data.get('voltar_padrao'))
    if voltar_padrao:
        PreferenciaUsuarioKanban.objects.filter(user=request.user).delete()
        return JsonResponse({'success': True, 'voltou_padrao': True,
                             'campos_atuais': resolver_campos_do_usuario(request.user, cfg)})
    pref, _ = PreferenciaUsuarioKanban.objects.update_or_create(
        user=request.user, defaults={'campos': campos},
    )
    return JsonResponse({'success': True, 'campos_atuais': campos})


@login_required
@require_POST
def api_configuracao_card_padrao(request):
    """Admin define o default de campos do card pro tenant."""
    if not (request.user.is_superuser or user_tem_funcionalidade(request, 'comercial.editar_configuracoes')):
        return JsonResponse({'success': False, 'error': 'Sem permissao'}, status=403)
    from .cards_config import campos_validos
    from .models import ConfiguracaoCRM
    try:
        data = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'JSON invalido'}, status=400)
    cfg, _ = ConfiguracaoCRM.objects.get_or_create(tenant=request.tenant)
    cfg.campos_card_padrao = campos_validos(data.get('campos') or [])
    cfg.save(update_fields=['campos_card_padrao', 'data_atualizacao'])
    return JsonResponse({'success': True, 'campos_padrao_tenant': cfg.campos_card_padrao})


@login_required
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

    from apps.sistema.utils import registrar_acao
    registrar_acao('crm', 'atribuir', 'oportunidade', oportunidade.pk,
                   f'Responsavel atribuido: {nome or "removido"} para {oportunidade.lead.nome_razaosocial}',
                   request=request)

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

    # Base: escopo de visibilidade (ve tudo / equipe / so as suas)
    esc = escopo_responsaveis(request)
    if esc is None:
        qs = TarefaCRM.objects.all()
    else:
        qs = TarefaCRM.objects.filter(responsavel_id__in=esc)

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

    from django.core.paginator import Paginator

    hoje = timezone.now().date()
    tarefas_hoje = qs.filter(data_vencimento__date=hoje, status__in=['pendente', 'em_andamento'])
    tarefas_semana = qs.filter(
        data_vencimento__date__gt=hoje,
        data_vencimento__date__lte=hoje + timezone.timedelta(days=7),
        status__in=['pendente', 'em_andamento']
    )
    tarefas_vencidas = qs.filter(data_vencimento__lt=timezone.now(), status__in=['pendente', 'em_andamento', 'vencida'])

    # Aba "Todas" pode ter centenas de itens — pagina apenas ela
    tarefas_todas_qs = qs.exclude(status='concluida')
    tarefas_todas_paginator = Paginator(tarefas_todas_qs, 30)
    tarefas_todas_page = tarefas_todas_paginator.get_page(request.GET.get('page'))
    tarefas_todas = tarefas_todas_page.object_list

    tarefas_concluidas = qs.filter(status='concluida').order_by('-data_conclusao')[:20]

    # Dados para filtros
    from django.contrib.auth.models import User
    vendedores = []
    for u in User.objects.filter(is_active=True, perfil__tenant=request.tenant).order_by('first_name'):
        vendedores.append({'id': u.pk, 'nome': u.get_full_name() or u.username})

    filter_fields = [
        {'type': 'select', 'label': 'Tipo', 'name': 'tipo', 'value': filtro_tipo,
         'options': [('', 'Todos')] + list(TarefaCRM.TIPO_CHOICES)},
        {'type': 'select', 'label': 'Responsavel', 'name': 'responsavel', 'value': filtro_responsavel,
         'options': [('', 'Todos')] + [(str(v['id']), v['nome']) for v in vendedores]},
        {'type': 'select', 'label': 'Prioridade', 'name': 'prioridade', 'value': filtro_prioridade,
         'options': [('', 'Todas')] + list(TarefaCRM.PRIORIDADE_CHOICES)},
    ]
    active_filters_count = sum(1 for v in [filtro_tipo, filtro_responsavel, filtro_prioridade] if v) + (1 if filtro_search else 0)

    context = {
        'tarefas_hoje': tarefas_hoje,
        'tarefas_semana': tarefas_semana,
        'tarefas_vencidas': tarefas_vencidas,
        'tarefas_todas': tarefas_todas,
        'tarefas_todas_page_obj': tarefas_todas_page,
        'tarefas_todas_paginated': tarefas_todas_page.has_other_pages(),
        'tarefas_concluidas': tarefas_concluidas,
        'vendedores': vendedores,
        'filter_fields': filter_fields,
        'active_filters_count': active_filters_count,
        'filtro_tipo': filtro_tipo,
        'filtro_responsavel': filtro_responsavel,
        'filtro_prioridade': filtro_prioridade,
        'filtro_search': filtro_search,
        'tipos_tarefa': TarefaCRM.TIPO_CHOICES,
        'prioridades': TarefaCRM.PRIORIDADE_CHOICES,
        'hoje': hoje,
        'page_title': 'Tarefas CRM',
    }
    return render(request, 'crm/tarefas_lista.html', context)


@login_required
@require_POST
def api_tarefa_concluir(request, pk):
    # Quem enxerga a tarefa na lista (pelo escopo) pode concluir. Antes o backend
    # so aceitava o proprio responsavel, entao o clique do gestor voltava 404
    # calado. Agora ele conclui dentro do escopo dele.
    esc = escopo_responsaveis(request)
    if esc is None:
        tarefa = get_object_or_404(TarefaCRM, pk=pk)
    else:
        tarefa = get_object_or_404(TarefaCRM, pk=pk, responsavel_id__in=esc)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}

    tarefa.status = 'concluida'
    tarefa.data_conclusao = timezone.now()
    tarefa.resultado = data.get('resultado', '')
    tarefa.save(update_fields=['status', 'data_conclusao', 'resultado', 'data_atualizacao'])

    from apps.sistema.utils import registrar_acao
    dono = tarefa.responsavel_id != request.user.id
    detalhe = f'Tarefa concluida: {tarefa.titulo}'
    if dono:
        detalhe += f' (concluida pelo gestor, responsavel era {tarefa.responsavel})'
    registrar_acao('crm', 'concluir', 'tarefa', tarefa.pk, detalhe, request=request)

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

    from apps.sistema.utils import registrar_acao
    registrar_acao('crm', 'criar', 'tarefa', tarefa.pk,
                   f'Tarefa criada: {tarefa.titulo}', request=request)

    return JsonResponse({'ok': True, 'id': tarefa.pk})


# ============================================================================
# NOTAS
# ============================================================================

@login_required
@require_POST
@auditar('crm', 'criar', 'nota')
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
@auditar('crm', 'excluir', 'nota')
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

    # Filtrar apenas vendedores/supervisores (exclui admins)
    from apps.sistema.models import PermissaoUsuario
    perfis_vendedor = ['Vendedor', 'Supervisor Comercial', 'Gerente Comercial']
    users_comercial = PermissaoUsuario.objects.filter(
        tenant=request.tenant,
        perfil__nome__in=perfis_vendedor,
    ).values_list('user_id', flat=True).distinct()
    vendedores = User.objects.filter(pk__in=users_comercial, is_active=True).order_by('first_name')
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

    # Oportunidades fechadas no período. Soma valor_estimado_manual
    # (fallback simples — soma de itens nao funciona em aggregate de
    # aggregate; pra precisao total usar com_valor_estimado por op).
    from django.db.models import Value, DecimalField
    from django.db.models.functions import Coalesce
    ops_ganhas = OportunidadeVenda.objects.filter(
        estagio__is_final_ganho=True,
        data_fechamento_real__date__gte=data_inicio,
        ativo=True,
    ).values('responsavel').annotate(
        total=Count('id'),
        valor=Coalesce(Sum('valor_estimado_manual'),
                       Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))),
    )

    por_vendedor = {item['responsavel']: item for item in ops_ganhas}

    resultado = []
    from apps.sistema.models import PermissaoUsuario
    perfis_vendedor = ['Vendedor', 'Supervisor Comercial', 'Gerente Comercial']
    users_comercial = PermissaoUsuario.objects.filter(
        tenant=request.tenant,
        perfil__nome__in=perfis_vendedor,
    ).values_list('user_id', flat=True).distinct()
    for u in User.objects.filter(pk__in=users_comercial, is_active=True):
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

    # Funil por estágio (filtrado por pipeline)
    from .models import Pipeline
    pipeline_id = request.GET.get('pipeline_id', '').strip()
    if pipeline_id and pipeline_id.isdigit():
        pipeline_filtro = Pipeline.objects.filter(pk=pipeline_id).first()
    else:
        pipeline_filtro = Pipeline.objects.filter(padrao=True).first()
        if not pipeline_filtro:
            pipeline_filtro = Pipeline.objects.filter(ativo=True).first()

    funil = []
    estagios_qs = PipelineEstagio.objects.filter(ativo=True).order_by('ordem')
    if pipeline_filtro:
        estagios_qs = estagios_qs.filter(pipeline=pipeline_filtro)

    for e in estagios_qs:
        total = OportunidadeVenda.objects.filter(estagio=e, ativo=True).count()
        funil.append({'estagio': e.nome, 'cor': e.cor_hex, 'total': total})

    pipelines = list(Pipeline.objects.filter(ativo=True).values('id', 'nome'))

    return JsonResponse({
        'vendedores': resultado,
        'funil': funil,
        'pipeline_atual': pipeline_filtro.pk if pipeline_filtro else None,
        'pipelines': pipelines,
        'ok': True,
    })


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

    metas_individuais = [m for m in metas_ativas if m.tipo == 'individual']
    metas_equipe = [m for m in metas_ativas if m.tipo == 'equipe']

    context = {
        'metas_ativas': metas_ativas,
        'metas_individuais': metas_individuais,
        'metas_equipe': metas_equipe,
        'vendedores': vendedores,
        'equipes': equipes,
        'page_title': 'Metas de Vendas',
    }
    return render(request, 'crm/metas.html', context)


@login_required
@require_POST
@auditar('crm', 'criar', 'meta')
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

    if meta.tipo == 'individual':
        if not data.get('vendedor_id'):
            return JsonResponse({'ok': False, 'erro': 'Selecione um vendedor para a meta individual.'}, status=400)
        meta.vendedor = get_object_or_404(User, pk=data['vendedor_id'])
    else:
        if not data.get('equipe_id'):
            return JsonResponse({'ok': False, 'erro': 'Selecione uma equipe para a meta de equipe.'}, status=400)
        meta.equipe = get_object_or_404(EquipeVendas, pk=data['equipe_id'])

    meta.save()
    return JsonResponse({'ok': True, 'id': meta.pk})


# ============================================================================
# RETENCAO — movida pra apps.cs.retencao em 05/05/2026.
# Mantido só o scanner que ainda é usado por automação interna; demais views
# vivem em apps/cs/retencao/views.py
# ============================================================================


# Funções de retenção movidas pra apps.cs.retencao.views em 05/05/2026.


# ============================================================================
# SEGMENTOS
# ============================================================================

@login_required
def segmentos_lista(request):
    segmentos_qs = SegmentoCRM.objects.filter(ativo=True).select_related('criado_por').order_by('nome')
    total = segmentos_qs.count()
    por_tipo = {'dinamico': 0, 'manual': 0, 'hibrido': 0}
    for s in segmentos_qs:
        if s.tipo in por_tipo:
            por_tipo[s.tipo] += 1

    status_tabs = [
        {'label': 'Todos', 'url': '#', 'onclick': "filtrarPorTipo(''); return false;", 'active': True, 'count': total},
        {'label': 'Dinamicos', 'url': '#', 'onclick': "filtrarPorTipo('dinamico'); return false;", 'count': por_tipo['dinamico']},
        {'label': 'Manuais', 'url': '#', 'onclick': "filtrarPorTipo('manual'); return false;", 'count': por_tipo['manual']},
        {'label': 'Hibridos', 'url': '#', 'onclick': "filtrarPorTipo('hibrido'); return false;", 'count': por_tipo['hibrido']},
    ]

    paginator = Paginator(segmentos_qs, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'segmentos': page_obj,
        'page_obj': page_obj,
        'status_tabs': status_tabs,
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

        elif action == 'criar_motivo_perda':
            from .models import MotivoPerda
            nome = request.POST.get('nome', '').strip()
            if nome and not MotivoPerda.objects.filter(nome=nome).exists():
                ult = MotivoPerda.objects.order_by('-ordem').first()
                MotivoPerda.objects.create(
                    tenant=request.tenant, nome=nome,
                    ordem=(ult.ordem + 1) if ult else 0,
                )
            return redirect('crm:configuracoes')

        elif action == 'editar_motivo_perda':
            from .models import MotivoPerda
            mid = request.POST.get('motivo_id')
            nome = request.POST.get('nome', '').strip()
            motivo = MotivoPerda.objects.filter(pk=mid).first()
            if motivo and nome:
                motivo.nome = nome
                motivo.ativo = request.POST.get('ativo') == 'on'
                motivo.save(update_fields=['nome', 'ativo'])
            return redirect('crm:configuracoes')

        elif action == 'excluir_motivo_perda':
            from .models import MotivoPerda
            MotivoPerda.objects.filter(pk=request.POST.get('motivo_id')).delete()
            return redirect('crm:configuracoes')

    from .models import MotivoPerda
    motivos_perda = MotivoPerda.objects.all().order_by('ordem', 'nome')

    # Campos disponiveis pra marcar como obrigatorios por estagio
    from apps.comercial.crm.services.requisitos_estagio import CAMPOS_DISPONIVEIS
    campos_por_modulo = {}
    for codigo, label, modulo in CAMPOS_DISPONIVEIS:
        campos_por_modulo.setdefault(modulo, []).append({'codigo': codigo, 'label': label})

    context = {
        'config': config,
        'pipelines': pipelines,
        'pipeline_atual': pipeline_atual,
        'estagios': estagios,
        'equipes': equipes,
        'motivos_perda': motivos_perda,
        'campos_disponiveis_por_modulo': campos_por_modulo,
        'page_title': 'Configurações do CRM',
    }
    return render(request, 'crm/configuracoes_crm.html', context)


@login_required
@require_POST
def api_reordenar_estagios(request):
    if not user_tem_funcionalidade(request, 'comercial.configurar_pipeline'):
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
@auditar('crm', 'editar', 'configuracao')
def api_salvar_config(request):
    if not user_tem_funcionalidade(request, 'comercial.configurar_pipeline'):
        return JsonResponse({'ok': False, 'erro': 'Sem permissão'}, status=403)

    config = ConfiguracaoCRM.get_config()
    config.sla_alerta_horas_padrao = int(request.POST.get('sla_alerta_horas_padrao', 48))
    config.score_minimo_auto_criacao = int(request.POST.get('score_minimo_auto_criacao', 7))
    config.criar_oportunidade_automatico = bool(request.POST.get('criar_oportunidade_automatico'))
    config.notificar_responsavel_nova_oportunidade = bool(request.POST.get('notificar_responsavel_nova_oportunidade'))
    config.notificar_sla_breach = bool(request.POST.get('notificar_sla_breach'))
    # T8 — Motivos de Perda: flags de obrigatoriedade
    config.motivo_perda_obrigatorio = bool(request.POST.get('motivo_perda_obrigatorio'))
    config.motivo_perda_pede_concorrente = bool(request.POST.get('motivo_perda_pede_concorrente'))
    estagio_id = request.POST.get('estagio_inicial_padrao_id')
    config.estagio_inicial_padrao = PipelineEstagio.objects.filter(pk=estagio_id).first() if estagio_id else None
    w1 = request.POST.get('webhook_n8n_nova_oportunidade', '').strip()
    w2 = request.POST.get('webhook_n8n_mudanca_estagio', '').strip()
    w3 = request.POST.get('webhook_n8n_tarefa_vencida', '').strip()
    config.webhook_n8n_nova_oportunidade = w1 or None
    config.webhook_n8n_mudanca_estagio = w2 or None
    config.webhook_n8n_tarefa_vencida = w3 or None

    # Distribuição de oportunidades
    config.distribuicao_modo = request.POST.get('distribuicao_modo', 'desativado')
    equipe_id = request.POST.get('distribuicao_equipe_id', '').strip()
    config.distribuicao_equipe = EquipeVendas.objects.filter(pk=equipe_id).first() if equipe_id else None

    # Automações do Pipeline
    preview_max_raw = request.POST.get('preview_regras_max', '').strip()
    if preview_max_raw:
        try:
            config.preview_regras_max = max(10, min(int(preview_max_raw), 10000))
        except ValueError:
            pass

    config.save()
    return JsonResponse({'ok': True})


@login_required
@require_POST
@auditar('crm', 'criar', 'estagio')
def api_criar_estagio(request):
    if not user_tem_funcionalidade(request, 'comercial.configurar_pipeline'):
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
    if not user_tem_funcionalidade(request, 'comercial.configurar_pipeline'):
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
            'campos_obrigatorios': list(est.campos_obrigatorios or []),
        }
    })


@login_required
@require_POST
def api_estagio_campos_obrigatorios(request, pk):
    """Atualiza a lista de campos obrigatorios pra entrar no estagio."""
    if not user_tem_funcionalidade(request, 'comercial.configurar_pipeline'):
        return JsonResponse({'ok': False, 'erro': 'Sem permissão'}, status=403)
    est = get_object_or_404(PipelineEstagio, pk=pk)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'erro': 'JSON invalido'}, status=400)
    codigos = data.get('campos_obrigatorios') or []
    if not isinstance(codigos, list):
        return JsonResponse({'ok': False, 'erro': 'campos_obrigatorios precisa ser lista'}, status=400)
    # Valida que cada codigo esta na lista de disponiveis
    from apps.comercial.crm.services.requisitos_estagio import CAMPOS_DISPONIVEIS_DICT
    invalidos = [c for c in codigos if c not in CAMPOS_DISPONIVEIS_DICT]
    if invalidos:
        return JsonResponse({'ok': False, 'erro': f'Campos invalidos: {invalidos}'}, status=400)
    est.campos_obrigatorios = codigos
    est.save(update_fields=['campos_obrigatorios'])
    from apps.sistema.utils import registrar_acao
    registrar_acao('crm', 'editar', 'estagio', est.pk,
                   f'Campos obrigatorios de "{est.nome}" atualizados: {codigos}',
                   request=request)
    return JsonResponse({'ok': True, 'campos_obrigatorios': codigos})


# ============================================================================
# DOCUMENTOS DA OPORTUNIDADE (upload manual + aprovacao inline)
# ============================================================================

@login_required
@require_POST
def api_oportunidade_adicionar_documento(request, pk):
    """
    POST /crm/oportunidades/<pk>/documentos/
    Multipart form com:
      - tipo_documento (selfie|doc_frente|doc_verso|comprovante_residencia|contrato_assinado|outro)
      - arquivo (UploadedFile, imagem ou PDF, max 5MB)
      - observacao (opcional)

    Cria DocumentoLead vinculado ao lead da oportunidade.
    Se user tem comercial.aprovar_documento_inline, ja salva como 'aprovado'.
    Senao salva como 'pendente'.
    """
    import base64
    from apps.comercial.cadastro.models import DocumentoLead
    from apps.comercial.cadastro.services.documentos import recalcular_documentacao_validada
    from apps.sistema.utils import registrar_acao

    if not user_tem_funcionalidade(request, 'comercial.adicionar_documento_inline') and not request.user.is_superuser:
        return JsonResponse({'error': 'Sem permissao para adicionar documento'}, status=403)

    oportunidade = get_object_or_404(OportunidadeVenda, pk=pk)
    lead = oportunidade.lead

    tipo = (request.POST.get('tipo_documento') or '').strip()
    tipos_validos = {c[0] for c in DocumentoLead.TIPO_DOCUMENTO_CHOICES}
    if tipo not in tipos_validos:
        return JsonResponse({'error': f'tipo_documento invalido. Aceitos: {sorted(tipos_validos)}'}, status=400)

    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'error': 'Arquivo nao informado (campo "arquivo")'}, status=400)

    MAX_BYTES = 5 * 1024 * 1024
    if arquivo.size > MAX_BYTES:
        return JsonResponse({'error': f'Arquivo excede 5MB (recebido {arquivo.size} bytes)'}, status=400)

    formatos_validos = {'jpg', 'jpeg', 'png', 'webp', 'pdf'}
    nome = arquivo.name or 'documento'
    formato = (nome.rsplit('.', 1)[-1] or '').lower() if '.' in nome else ''
    if formato not in formatos_validos:
        return JsonResponse({'error': f'Formato invalido. Aceitos: {sorted(formatos_validos)}'}, status=400)

    conteudo = arquivo.read()
    arquivo_b64 = base64.b64encode(conteudo).decode('ascii')

    pode_aprovar = user_tem_funcionalidade(request, 'comercial.aprovar_documento_inline') or request.user.is_superuser
    status_inicial = 'aprovado' if pode_aprovar else 'pendente'

    usuario_nome = request.user.get_full_name() or request.user.username

    doc = DocumentoLead.objects.create(
        lead=lead,
        tipo_documento=tipo,
        arquivo_base64=arquivo_b64,
        nome_arquivo=nome[:255],
        tamanho_arquivo=arquivo.size,
        formato_arquivo=formato,
        status=status_inicial,
        observacoes_validacao=(request.POST.get('observacao') or '').strip() or None,
        data_validacao=timezone.now() if pode_aprovar else None,
        validado_por=usuario_nome if pode_aprovar else None,
    )

    if pode_aprovar:
        recalcular_documentacao_validada(lead)

    registrar_acao('crm', 'adicionar_documento', 'oportunidade', oportunidade.pk,
                   f'{usuario_nome} adicionou documento "{doc.get_tipo_documento_display()}" ({nome}) — status: {status_inicial}',
                   request=request)

    return JsonResponse({
        'ok': True,
        'documento': {
            'id': doc.pk,
            'tipo': doc.tipo_documento,
            'tipo_display': doc.get_tipo_documento_display(),
            'nome': doc.nome_arquivo,
            'tamanho': doc.tamanho_arquivo,
            'formato': doc.formato_arquivo,
            'status': doc.status,
            'status_display': doc.get_status_display(),
        },
        'documentacao_validada': lead.documentacao_validada,
    }, status=201)


@login_required
@require_POST
def api_documento_aprovar(request, pk):
    """POST /crm/documentos/<pk>/aprovar/  — body opcional: {observacao: "..."}"""
    from apps.comercial.cadastro.models import DocumentoLead
    from apps.comercial.cadastro.services.documentos import recalcular_documentacao_validada
    from apps.sistema.utils import registrar_acao

    if not user_tem_funcionalidade(request, 'comercial.aprovar_documento_inline') and not request.user.is_superuser:
        return JsonResponse({'error': 'Sem permissao para aprovar documento'}, status=403)

    doc = get_object_or_404(DocumentoLead, pk=pk)
    try:
        body = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        body = {}
    observacao = (body.get('observacao') or '').strip()
    usuario_nome = request.user.get_full_name() or request.user.username

    doc.validar_documento(status='aprovado', observacoes=observacao or None, usuario=usuario_nome)
    recalcular_documentacao_validada(doc.lead)

    registrar_acao('crm', 'aprovar_documento', 'documento_lead', doc.pk,
                   f'{usuario_nome} aprovou documento "{doc.get_tipo_documento_display()}" do lead #{doc.lead_id}',
                   request=request)

    return JsonResponse({
        'ok': True,
        'documento': {'id': doc.pk, 'status': doc.status, 'status_display': doc.get_status_display()},
        'documentacao_validada': doc.lead.documentacao_validada,
    })


@login_required
@require_POST
def api_documento_rejeitar(request, pk):
    """POST /crm/documentos/<pk>/rejeitar/  — body: {observacao: "motivo"}"""
    from apps.comercial.cadastro.models import DocumentoLead
    from apps.comercial.cadastro.services.documentos import recalcular_documentacao_validada
    from apps.sistema.utils import registrar_acao

    if not user_tem_funcionalidade(request, 'comercial.aprovar_documento_inline') and not request.user.is_superuser:
        return JsonResponse({'error': 'Sem permissao para rejeitar documento'}, status=403)

    doc = get_object_or_404(DocumentoLead, pk=pk)
    try:
        body = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        body = {}
    observacao = (body.get('observacao') or '').strip()
    usuario_nome = request.user.get_full_name() or request.user.username

    doc.validar_documento(status='rejeitado', observacoes=observacao or None, usuario=usuario_nome)
    recalcular_documentacao_validada(doc.lead)

    registrar_acao('crm', 'rejeitar_documento', 'documento_lead', doc.pk,
                   f'{usuario_nome} rejeitou documento "{doc.get_tipo_documento_display()}" do lead #{doc.lead_id}'
                   + (f' — motivo: {observacao}' if observacao else ''),
                   request=request)

    return JsonResponse({
        'ok': True,
        'documento': {'id': doc.pk, 'status': doc.status, 'status_display': doc.get_status_display()},
        'documentacao_validada': doc.lead.documentacao_validada,
    })


@login_required
@require_http_methods(['DELETE', 'POST'])
def api_documento_remover(request, pk):
    """DELETE /crm/documentos/<pk>/  — remove o documento."""
    from apps.comercial.cadastro.models import DocumentoLead
    from apps.comercial.cadastro.services.documentos import recalcular_documentacao_validada
    from apps.sistema.utils import registrar_acao

    if not user_tem_funcionalidade(request, 'comercial.adicionar_documento_inline') and not request.user.is_superuser:
        return JsonResponse({'error': 'Sem permissao'}, status=403)

    doc = get_object_or_404(DocumentoLead, pk=pk)
    lead = doc.lead
    nome_arquivo = doc.nome_arquivo
    tipo_display = doc.get_tipo_documento_display()
    usuario_nome = request.user.get_full_name() or request.user.username
    doc.delete()
    recalcular_documentacao_validada(lead)

    registrar_acao('crm', 'remover_documento', 'documento_lead', pk,
                   f'{usuario_nome} removeu documento "{tipo_display}" ({nome_arquivo}) do lead #{lead.pk}',
                   request=request)

    return JsonResponse({'ok': True, 'documentacao_validada': lead.documentacao_validada})


@login_required
@require_POST
def api_imagem_aprovar(request, pk):
    """POST /crm/imagens/<pk>/aprovar/  — body opcional: {observacao: "..."}"""
    from apps.comercial.leads.models import ImagemLeadProspecto
    from apps.sistema.utils import registrar_acao
    from django.utils import timezone

    if not user_tem_funcionalidade(request, 'comercial.aprovar_documento_inline') and not request.user.is_superuser:
        return JsonResponse({'error': 'Sem permissao para aprovar imagem'}, status=403)

    img = get_object_or_404(ImagemLeadProspecto, pk=pk)
    try:
        body = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        body = {}
    observacao = (body.get('observacao') or '').strip()
    usuario_nome = request.user.get_full_name() or request.user.username

    img.status_validacao = ImagemLeadProspecto.STATUS_VALIDO
    img.observacao_validacao = observacao
    img.data_validacao = timezone.now()
    img.validado_por = usuario_nome
    img.save(update_fields=['status_validacao', 'observacao_validacao', 'data_validacao', 'validado_por'])

    registrar_acao('crm', 'aprovar_imagem', 'imagem_lead', img.pk,
                   f'{usuario_nome} aprovou imagem "{img.descricao or "sem rotulo"}" do lead #{img.lead_id}',
                   request=request)

    return JsonResponse({
        'ok': True,
        'imagem': {'id': img.pk, 'status': img.status_validacao, 'status_display': img.get_status_validacao_display()},
    })


@login_required
@require_POST
def api_imagem_rejeitar(request, pk):
    """POST /crm/imagens/<pk>/rejeitar/  — body: {observacao: "motivo"}"""
    from apps.comercial.leads.models import ImagemLeadProspecto
    from apps.sistema.utils import registrar_acao
    from django.utils import timezone

    if not user_tem_funcionalidade(request, 'comercial.aprovar_documento_inline') and not request.user.is_superuser:
        return JsonResponse({'error': 'Sem permissao para rejeitar imagem'}, status=403)

    img = get_object_or_404(ImagemLeadProspecto, pk=pk)
    try:
        body = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        body = {}
    observacao = (body.get('observacao') or '').strip()
    usuario_nome = request.user.get_full_name() or request.user.username

    img.status_validacao = ImagemLeadProspecto.STATUS_REJEITADO
    img.observacao_validacao = observacao
    img.data_validacao = timezone.now()
    img.validado_por = usuario_nome
    img.save(update_fields=['status_validacao', 'observacao_validacao', 'data_validacao', 'validado_por'])

    registrar_acao('crm', 'rejeitar_imagem', 'imagem_lead', img.pk,
                   f'{usuario_nome} rejeitou imagem "{img.descricao or "sem rotulo"}" do lead #{img.lead_id}'
                   + (f' — motivo: {observacao}' if observacao else ''),
                   request=request)

    return JsonResponse({
        'ok': True,
        'imagem': {'id': img.pk, 'status': img.status_validacao, 'status_display': img.get_status_validacao_display()},
    })


@login_required
@require_GET
def api_documento_visualizar(request, pk):
    """GET /crm/documentos/<pk>/visualizar/  — retorna o arquivo inline (image ou PDF)."""
    from django.http import HttpResponse
    from apps.comercial.cadastro.models import DocumentoLead
    import base64

    doc = get_object_or_404(DocumentoLead, pk=pk)
    if not doc.arquivo_base64:
        return JsonResponse({'error': 'Arquivo nao disponivel'}, status=404)
    raw = base64.b64decode(doc.arquivo_base64)
    fmt = (doc.formato_arquivo or '').lower()
    content_type = {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
        'png': 'image/png', 'webp': 'image/webp',
        'pdf': 'application/pdf',
    }.get(fmt, 'application/octet-stream')
    resp = HttpResponse(raw, content_type=content_type)
    resp['Content-Disposition'] = f'inline; filename="{doc.nome_arquivo}"'
    return resp


@login_required
@require_POST
@auditar('crm', 'excluir', 'estagio')
def api_excluir_estagio(request, pk):
    if not user_tem_funcionalidade(request, 'comercial.configurar_pipeline'):
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
@auditar('crm', 'criar', 'equipe')
def api_criar_equipe(request):
    if not user_tem_funcionalidade(request, 'comercial.configurar_pipeline'):
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
                    if cargo == 'gerente':
                        # Gerente SUPERVISIONA o time, nao e membro que vende nele.
                        # Vira lider (FK no lado do time), entao a mesma pessoa
                        # lidera varios times sem sair de nenhum. Nao mexe no
                        # PerfilVendedor.equipe dele.
                        eq.lider = user
                        eq.save(update_fields=['lider'])
                    else:
                        # Vendedor/Supervisor/Diretor: membro do time. Como equipe
                        # e FK unica, update_or_create MOVE a pessoa pra ca (sai do
                        # time anterior). get_or_create nao servia: ignora defaults
                        # quando o PerfilVendedor ja existe (bug silencioso, a tela
                        # nao mudava depois do Adicionar).
                        PerfilVendedor.objects.update_or_create(
                            user=user,
                            defaults={'equipe': eq, 'cargo': cargo},
                        )
            return redirect('crm:equipes')

        elif action == 'remover_membro':
            membro_id = request.POST.get('membro_id')
            PerfilVendedor.objects.filter(pk=membro_id).delete()
            return redirect('crm:equipes')

        elif action == 'remover_lider':
            eid = request.POST.get('equipe_id')
            eq = EquipeVendas.objects.filter(pk=eid).first()
            if eq:
                eq.lider = None
                eq.save(update_fields=['lider'])
            return redirect('crm:equipes')

    return render(request, 'crm/equipes.html', {
        'equipes': equipes,
        'usuarios': usuarios,
        'page_title': 'Equipes de Vendas',
    })


@login_required
@require_POST
@auditar('marketing', 'salvar', 'segmento')
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
@auditar('marketing', 'adicionar_lead', 'segmento')
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
@auditar('marketing', 'remover_lead', 'segmento')
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
@auditar('marketing', 'disparar', 'segmento')
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
@auditar('crm', 'salvar', 'meta')
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
        if not vid:
            return JsonResponse({'ok': False, 'erro': 'Selecione um vendedor para a meta individual.'}, status=400)
        meta.vendedor = get_object_or_404(AuthUser, pk=vid)
        meta.equipe = None
    else:
        eid = request.POST.get('equipe_id')
        if not eid:
            return JsonResponse({'ok': False, 'erro': 'Selecione uma equipe para a meta de equipe.'}, status=400)
        meta.equipe = get_object_or_404(EquipeVendas, pk=eid)
        meta.vendedor = None

    meta.save()
    return JsonResponse({'ok': True, 'id': meta.pk})


@login_required
@require_POST
@auditar('crm', 'excluir', 'meta')
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
            tenant=oportunidade.tenant,
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


# ============================================================================
# PRODUTOS E SERVIÇOS
# ============================================================================

@login_required
def produtos_lista(request):
    """Página de gestão de produtos/serviços e opções de vencimento."""
    produtos_qs = ProdutoServico.objects.all().order_by('ordem', 'nome')
    vencimentos = OpcaoVencimentoCRM.objects.all().order_by('ordem', 'dia')

    paginator = Paginator(produtos_qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'produtos': page_obj.object_list,
        'page_obj': page_obj,
        'vencimentos': vencimentos,
        'categorias': ProdutoServico.CATEGORIA_CHOICES,
        'recorrencias': ProdutoServico.RECORRENCIA_CHOICES,
    }
    return render(request, 'crm/produtos.html', context)


@login_required
@require_http_methods(["POST"])
def api_produto_salvar(request):
    """Criar ou editar produto/serviço."""
    try:
        data = json.loads(request.body)
        produto_id = data.get('id')

        campos = {
            'nome': data.get('nome', '').strip(),
            'descricao': data.get('descricao', '').strip(),
            'codigo': data.get('codigo', '').strip(),
            'categoria': data.get('categoria', 'servico'),
            'preco': Decimal(str(data.get('preco', 0))),
            'recorrencia': data.get('recorrencia', 'mensal'),
            'ativo': data.get('ativo', True),
            'ordem': int(data.get('ordem', 0)),
        }

        if not campos['nome']:
            return JsonResponse({'error': 'Nome é obrigatório'}, status=400)

        plano_id = data.get('plano_internet_id')
        if plano_id:
            campos['plano_internet_id'] = plano_id

        id_externo = data.get('id_externo', '').strip()
        if id_externo:
            campos['id_externo'] = id_externo

        if produto_id:
            produto = get_object_or_404(ProdutoServico, pk=produto_id)
            for k, v in campos.items():
                setattr(produto, k, v)
            produto.save()
            msg = 'Produto atualizado com sucesso.'
        else:
            campos['tenant'] = request.tenant
            produto = ProdutoServico.objects.create(**campos)
            msg = 'Produto criado com sucesso.'

        return JsonResponse({
            'success': True,
            'message': msg,
            'produto': {
                'id': produto.pk,
                'nome': produto.nome,
                'preco': str(produto.preco),
                'categoria': produto.categoria,
                'recorrencia': produto.recorrencia,
            }
        })
    except Exception as e:
        logger.error(f'Erro ao salvar produto: {e}')
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["DELETE"])
def api_produto_excluir(request, pk):
    """Excluir produto (se não estiver vinculado a oportunidades)."""
    try:
        produto = get_object_or_404(ProdutoServico, pk=pk)
        if produto.itens_oportunidade.exists():
            return JsonResponse({
                'error': 'Produto vinculado a oportunidades. Desative-o em vez de excluir.'
            }, status=400)
        produto.delete()
        return JsonResponse({'success': True, 'message': 'Produto excluído.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_produtos_listar(request):
    """API para listar produtos (usado em selectors)."""
    apenas_ativos = request.GET.get('ativos', '1') == '1'
    qs = ProdutoServico.objects.all().order_by('ordem', 'nome')
    if apenas_ativos:
        qs = qs.filter(ativo=True)

    produtos = [{
        'id': p.pk,
        'nome': p.nome,
        'codigo': p.codigo,
        'categoria': p.categoria,
        'categoria_display': p.get_categoria_display(),
        'preco': str(p.preco),
        'recorrencia': p.recorrencia,
        'recorrencia_display': p.get_recorrencia_display(),
        'ativo': p.ativo,
        'empresa': (p.dados_erp or {}).get('empresa', '') if isinstance(p.dados_erp, dict) else '',
        'velocidade_down': (p.dados_erp or {}).get('velocidade_download_mbps') if isinstance(p.dados_erp, dict) else None,
    } for p in qs]

    return JsonResponse({'success': True, 'produtos': produtos})


# ============================================================================
# ITENS DA OPORTUNIDADE
# ============================================================================

@login_required
def api_itens_oportunidade(request, pk):
    """GET: listar itens / POST: adicionar item."""
    oportunidade = get_object_or_404(OportunidadeVenda, pk=pk)

    if request.method == 'GET':
        itens = oportunidade.itens.select_related('produto').all()
        data = [{
            'id': item.pk,
            'produto_id': item.produto_id,
            'produto_nome': item.produto.nome,
            'produto_categoria': item.produto.get_categoria_display(),
            'quantidade': item.quantidade,
            'valor_unitario': str(item.valor_unitario),
            'desconto': str(item.desconto),
            'subtotal': str(item.subtotal),
            'observacao': item.observacao,
        } for item in itens]

        return JsonResponse({
            'success': True,
            'itens': data,
            'valor_total': str(oportunidade.valor_total_itens),
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            produto = get_object_or_404(ProdutoServico, pk=data.get('produto_id'))
            forcar = bool(data.get('forcar_duplicidade'))

            # Anti-duplicidade: bloquear adicionar 2 produtos da mesma categoria
            # na mesma op (ex: 2 planos). Frontend pode reenviar com
            # forcar_duplicidade=true se o vendedor confirmar.
            if not forcar:
                ja_tem = oportunidade.itens.filter(produto__categoria=produto.categoria).first()
                if ja_tem:
                    return JsonResponse({
                        'success': False,
                        'error': 'duplicidade_categoria',
                        'message': (
                            f'A oportunidade ja tem um item da categoria '
                            f'"{produto.get_categoria_display()}" ({ja_tem.produto.nome}). '
                            f'Remova o atual ou confirme pra substituir.'
                        ),
                        'item_existente': {
                            'id': ja_tem.pk,
                            'produto_nome': ja_tem.produto.nome,
                        },
                    }, status=409)

            item = ItemOportunidade.objects.create(
                tenant=request.tenant,
                oportunidade=oportunidade,
                produto=produto,
                quantidade=int(data.get('quantidade', 1)),
                valor_unitario=Decimal(str(data.get('valor_unitario', produto.preco))),
                desconto=Decimal(str(data.get('desconto', 0))),
                observacao=data.get('observacao', ''),
            )

            oportunidade.recalcular_valor()

            from apps.sistema.utils import registrar_acao
            registrar_acao(
                'crm', 'adicionar_item', 'oportunidade', oportunidade.pk,
                f'Adicionou produto "{produto.nome}" (R$ {item.valor_unitario}, qtd {item.quantidade})',
                request=request,
            )

            return JsonResponse({
                'success': True,
                'message': f'{produto.nome} adicionado.',
                'item': {
                    'id': item.pk,
                    'produto_nome': produto.nome,
                    'subtotal': str(item.subtotal),
                },
                'valor_total': str(oportunidade.valor_total_itens),
            })
        except Exception as e:
            logger.error(f'Erro ao adicionar item: {e}')
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Método não permitido'}, status=405)


@login_required
@require_http_methods(["DELETE"])
def api_item_oportunidade_remover(request, pk):
    """Remove um item da oportunidade."""
    try:
        item = get_object_or_404(ItemOportunidade, pk=pk)
        oportunidade = item.oportunidade
        nome_produto = item.produto.nome
        valor = item.valor_unitario
        item.delete()
        oportunidade.recalcular_valor()

        from apps.sistema.utils import registrar_acao
        registrar_acao(
            'crm', 'remover_item', 'oportunidade', oportunidade.pk,
            f'Removeu produto "{nome_produto}" (R$ {valor})',
            request=request,
        )

        return JsonResponse({
            'success': True,
            'message': 'Item removido.',
            'valor_total': str(oportunidade.valor_total_itens),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# OPÇÕES DE VENCIMENTO
# ============================================================================

@login_required
@require_http_methods(["POST"])
def api_vencimento_salvar(request):
    """Criar ou editar opção de vencimento."""
    try:
        data = json.loads(request.body)
        venc_id = data.get('id')
        dia = int(data.get('dia', 0))

        if not dia or dia < 1 or dia > 31:
            return JsonResponse({'error': 'Dia inválido (1-31)'}, status=400)

        campos = {
            'dia': dia,
            'descricao': data.get('descricao', '').strip(),
            'id_externo': data.get('id_externo', '').strip(),
            'dados_erp': data.get('dados_erp', {}),
            'ativo': data.get('ativo', True),
            'ordem': int(data.get('ordem', 0)),
        }

        if venc_id:
            venc = get_object_or_404(OpcaoVencimentoCRM, pk=venc_id)
            for k, v in campos.items():
                setattr(venc, k, v)
            venc.save()
            msg = 'Opcao de vencimento atualizada.'
        else:
            campos['tenant'] = request.tenant
            venc = OpcaoVencimentoCRM.objects.create(**campos)
            msg = 'Opcao de vencimento criada.'

        return JsonResponse({'success': True, 'message': msg, 'id': venc.pk})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["DELETE"])
def api_vencimento_excluir(request, pk):
    """Excluir opção de vencimento."""
    try:
        venc = get_object_or_404(OpcaoVencimentoCRM, pk=pk)
        venc.delete()
        return JsonResponse({'success': True, 'message': 'Opcao excluida.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_vencimentos_listar(request):
    """API para listar opções de vencimento."""
    qs = OpcaoVencimentoCRM.objects.filter(ativo=True).order_by('ordem', 'dia')
    data = [{
        'id': v.pk,
        'dia': v.dia,
        'descricao': v.descricao,
        'id_externo': v.id_externo,
        'ativo': v.ativo,
    } for v in qs]
    return JsonResponse({'success': True, 'vencimentos': data})


# ============================================================================
# AUTOMAÇÕES DO PIPELINE (tela read-only)
# ============================================================================

from .services.automacao_constantes import (
    TIPOS_CONDICAO, OPERADORES, TIPOS_CONDICAO_DICT, OPERADORES_DICT,
)

ACOES_DISPONIVEIS = [
    {
        'tipo': 'criar_venda',
        'label': 'Criar Venda',
        'descricao': 'Cria um registro de Venda para o lead (idempotente — não duplica)',
        'icon': 'bi-bag-check',
    },
    {
        'tipo': 'gerar_contrato_hubsoft',
        'label': 'Gerar Contrato HubSoft',
        'descricao': 'Cria + anexa documentos + aceita contrato no HubSoft. Atomico.',
        'icon': 'bi-file-earmark-text',
        'campos_extras': [
            {'name': 'id_contrato_modelo', 'label': 'ID Modelo Contrato', 'type': 'number', 'help': 'ID do template no HubSoft (consulte /configuracao/modelo_contrato)'},
            {'name': 'id_empresa', 'label': 'ID Empresa', 'type': 'number', 'help': 'ID da empresa HubSoft (matriz/filial)'},
            {'name': 'autorizacao_nome', 'label': 'Nome do Autorizador', 'type': 'text', 'help': 'Vazio = usa lead.nome_razaosocial'},
            {'name': 'autorizacao_cpf', 'label': 'CPF do Autorizador', 'type': 'text', 'help': 'Vazio = usa lead.cpf_cnpj'},
            {'name': 'informacao_adicional', 'label': 'Observação no contrato', 'type': 'text', 'help': 'Texto livre que vai no contrato'},
        ],
    },
    {
        'tipo': 'assinar_contrato_hubsoft',
        'label': 'Assinar Contrato HubSoft',
        'descricao': 'Aceita o contrato ja existente do cliente no HubSoft (consulta com incluir_contrato + aceite). Nao cria contrato. Use com trigger "documentos validados".',
        'icon': 'bi-file-earmark-check',
        'campos_extras': [
            {'name': 'ativar_servico_apos_aceite', 'label': 'Ativar servico apos aceite', 'type': 'text', 'help': 'Digite "sim" pra ativar o servico apos o aceite (testar destravar OS). Vazio = nao.'},
        ],
    },
    {
        'tipo': 'enviar_venda_whatsapp',
        'label': 'Enviar Venda por WhatsApp',
        'descricao': 'Envia resumo da venda + fotos dos documentos pelo WhatsApp (via uazapi). Idempotente — não reenvia.',
        'icon': 'bi-whatsapp',
        'campos_extras': [
            {'name': 'telefone_destino', 'label': 'Telefone destino', 'type': 'text', 'help': 'Formato DDI+DDD+numero, só dígitos. Ex: 5553981521653'},
        ],
    },
    {
        'tipo': 'sincronizar_prospecto_hubsoft',
        'label': 'Sincronizar Prospecto HubSoft',
        'descricao': 'Cria rascunho (POST /prospecto) OU atualiza prospecto existente (PUT /prospecto/{id}) no HubSoft. Decide automaticamente pelo lead.id_hubsoft. Idempotente.',
        'icon': 'bi-cloud-arrow-up',
    },
    {
        'tipo': 'adicionar_item_oportunidade',
        'label': 'Vincular plano escolhido como item',
        'descricao': 'Cria ItemOportunidade a partir do plano escolhido pelo cliente (lead.id_plano_rp). Busca ProdutoServico com id_externo igual no catalogo do tenant. Idempotente: nao duplica se ja vinculado.',
        'icon': 'bi-cart-plus',
    },
]
ACOES_DISPONIVEIS_DICT = {a['tipo']: a for a in ACOES_DISPONIVEIS}


def _formatar_condicao(cond):
    """Formata uma condição em prosa pra exibir na UI."""
    tipo_slug = cond.get('tipo', '')
    operador_slug = cond.get('operador', '')
    tipo = TIPOS_CONDICAO_DICT.get(tipo_slug, tipo_slug)
    operador = OPERADORES_DICT.get(operador_slug, operador_slug)
    campo = cond.get('campo', '')
    valor = cond.get('valor', '')

    partes = [tipo]
    if campo:
        partes.append(f"({campo})")
    partes.append(operador)
    if valor not in ('', None):
        partes.append(f"'{valor}'")
    return ' '.join(str(p) for p in partes)


@login_required
def automacoes_pipeline_view(request):
    """Tela que lista regras agrupadas por Pipeline > Estágio > Regras."""
    denied = _check_perm(request, 'comercial.configurar_pipeline')
    if denied:
        return denied

    from .models import Pipeline

    # Filtros via query params
    pipeline_filtro = request.GET.get('pipeline') or ''
    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status') or ''
    view_mode = request.GET.get('view') or 'pipeline'  # 'pipeline' (default, accordion) | 'lista' (plana)

    pipelines_qs = Pipeline.objects.filter(ativo=True).order_by('ordem', 'nome')
    if pipeline_filtro:
        pipelines_qs = pipelines_qs.filter(pk=pipeline_filtro)

    pipelines_todos = list(Pipeline.objects.filter(ativo=True).order_by('ordem', 'nome'))

    def _passa_filtros(regra):
        if status == 'ativa' and not regra.ativo:
            return False
        if status == 'inativa' and regra.ativo:
            return False
        if q and q.lower() not in (regra.nome or '').lower():
            return False
        return True

    def _health_regra(regra):
        """Health binario simples: verde / amarelo / vermelho / sem-dados.
        verde     = regra ativa, com disparo nos ultimos 30 dias
        amarelo   = regra ativa, sem disparo ha 30+ dias (suspeita de quebra/abandono)
        vermelho  = regra ativa, com 0 acoes efetivas e mais de 0 avaliacoes
                   (avalia mas nunca executa — provavel condicao quebrada)
        nodata    = regra ativa que nunca disparou
        off       = regra desativada (status indiferente)
        """
        if not regra.ativo:
            return 'off'
        disparos = regra.total_disparos or 0
        efetivos = regra.total_acoes_efetivas or 0
        if disparos == 0:
            return 'nodata'
        if disparos > 0 and efetivos == 0:
            return 'vermelho'
        ultima = regra.ultima_execucao
        if ultima:
            agora = timezone.now()
            if (agora - ultima).days <= 30:
                return 'verde'
            return 'amarelo'
        return 'nodata'

    pipelines_ctx = []
    total_regras = 0
    total_ativas = 0
    total_disparos_global = 0
    total_estagios_com_regra = 0

    for pipe in pipelines_qs.prefetch_related('estagios__regras'):
        estagios_ctx = []
        total_regras_pipe = 0

        estagios = pipe.estagios.filter(ativo=True).order_by('ordem')
        for est in estagios:
            regras = []
            for regra in est.regras.all().order_by('prioridade'):
                if not _passa_filtros(regra):
                    continue
                regras.append({
                    'id': regra.pk,
                    'nome': regra.nome,
                    'prioridade': regra.prioridade,
                    'ativo': regra.ativo,
                    'condicoes_prosa': [_formatar_condicao(c) for c in (regra.condicoes or [])],
                    'acoes_labels': [ACOES_DISPONIVEIS_DICT.get(a.get('tipo'), {}).get('label', a.get('tipo')) for a in (regra.acoes or [])],
                    'atualizado_em': regra.atualizado_em,
                    'total_disparos': getattr(regra, 'total_disparos', 0),
                    'total_acoes_efetivas': getattr(regra, 'total_acoes_efetivas', 0),
                    'ultima_execucao': getattr(regra, 'ultima_execucao', None),
                    'health': _health_regra(regra),
                })
            estagios_ctx.append({
                'estagio': est,
                'regras': regras,
                'total_regras': len(regras),
            })
            total_regras += len(regras)
            total_regras_pipe += len(regras)
            total_ativas += sum(1 for r in regras if r['ativo'])
            total_disparos_global += sum(r['total_disparos'] for r in regras)
            if regras:
                total_estagios_com_regra += 1

        pipelines_ctx.append({
            'pipeline': pipe,
            'estagios': estagios_ctx,
            'total_regras': total_regras_pipe,
        })

    # Regras de ação pura (sem estágio destino)
    from .models import RegraPipelineEstagio
    regras_acao_pura = []
    for regra in RegraPipelineEstagio.objects.filter(estagio__isnull=True).order_by('prioridade'):
        if not _passa_filtros(regra):
            continue
        regras_acao_pura.append({
            'id': regra.pk,
            'nome': regra.nome,
            'prioridade': regra.prioridade,
            'ativo': regra.ativo,
            'condicoes_prosa': [_formatar_condicao(c) for c in (regra.condicoes or [])],
            'acoes_labels': [ACOES_DISPONIVEIS_DICT.get(a.get('tipo'), {}).get('label', a.get('tipo')) for a in (regra.acoes or [])],
            'atualizado_em': regra.atualizado_em,
            'total_disparos': getattr(regra, 'total_disparos', 0),
            'total_acoes_efetivas': getattr(regra, 'total_acoes_efetivas', 0),
            'ultima_execucao': getattr(regra, 'ultima_execucao', None),
            'health': _health_regra(regra),
        })
        total_regras += 1
        if regra.ativo:
            total_ativas += 1
        total_disparos_global += regra.total_disparos or 0

    # Lista plana (view alternada): todas as regras com pipeline+estagio
    regras_plano = []
    for p_ctx in pipelines_ctx:
        for g in p_ctx['estagios']:
            for r in g['regras']:
                regras_plano.append({
                    **r,
                    'pipeline_nome': p_ctx['pipeline'].nome,
                    'pipeline_cor': p_ctx['pipeline'].cor_hex,
                    'estagio_nome': g['estagio'].nome,
                    'estagio_cor': g['estagio'].cor_hex,
                    'estagio_tipo': g['estagio'].get_tipo_display(),
                })
    for r in regras_acao_pura:
        regras_plano.append({
            **r,
            'pipeline_nome': '—',
            'pipeline_cor': '#94A3B8',
            'estagio_nome': '(sem estagio destino)',
            'estagio_cor': '#94A3B8',
            'estagio_tipo': '—',
        })
    # Ordena por health + ultima_execucao
    health_ordem = {'vermelho': 0, 'amarelo': 1, 'nodata': 2, 'verde': 3, 'off': 4}
    regras_plano.sort(key=lambda r: (health_ordem.get(r.get('health'), 5), -(r.get('total_disparos') or 0)))

    # Filter fields no padrao list_filters (MODO B)
    pipeline_options = [('', 'Todos os pipelines')] + [
        (str(p.pk), p.nome) for p in pipelines_todos
    ]
    status_options = [
        ('', 'Todas'),
        ('ativa', 'Ativas'),
        ('inativa', 'Inativas'),
    ]
    filter_fields = [
        {'type': 'select', 'name': 'pipeline', 'label': 'Pipeline',
         'options': pipeline_options, 'value': pipeline_filtro},
        {'type': 'select', 'name': 'status', 'label': 'Status',
         'options': status_options, 'value': status},
    ]
    active_filters_count = sum(1 for v in (pipeline_filtro, status, q) if v)

    return render(request, 'crm/automacoes_pipeline.html', {
        'pipelines_ctx': pipelines_ctx,
        'pipelines_todos': pipelines_todos,
        'pipeline_filtro': pipeline_filtro,
        'q': q,
        'status_filtro': status,
        'view_mode': view_mode,
        'filter_fields': filter_fields,
        'active_filters_count': active_filters_count,
        'regras_acao_pura': regras_acao_pura,
        'regras_plano': regras_plano,
        'total_regras': total_regras,
        'total_ativas': total_ativas,
        'total_disparos_global': total_disparos_global,
        'total_estagios_com_regra': total_estagios_com_regra,
    })


# ----------------------------------------------------------------------------
# CRUD (Fase 2)
# ----------------------------------------------------------------------------

def _parse_condicoes_do_post(request):
    """
    Lê condições enviadas como formset simples via POST.
    Espera listas: cond_tipo[], cond_campo[], cond_operador[], cond_valor[].
    """
    tipos = request.POST.getlist('cond_tipo')
    campos = request.POST.getlist('cond_campo')
    operadores = request.POST.getlist('cond_operador')
    valores = request.POST.getlist('cond_valor')

    condicoes = []
    for tipo, campo, op, valor in zip(tipos, campos, operadores, valores):
        tipo = (tipo or '').strip()
        if not tipo:
            continue
        cond = {'tipo': tipo, 'operador': (op or 'igual').strip()}
        if campo.strip():
            cond['campo'] = campo.strip()
        valor = valor.strip() if isinstance(valor, str) else valor
        if valor in ('true', 'True'):
            cond['valor'] = True
        elif valor in ('false', 'False'):
            cond['valor'] = False
        elif valor != '':
            cond['valor'] = valor
        condicoes.append(cond)
    return condicoes


def _contexto_form_regra(regra=None, estagio_preselecionado=None):
    from .models import PipelineEstagio
    estagios = PipelineEstagio.objects.filter(ativo=True).order_by('ordem')
    acoes_selecionadas = {a.get('tipo') for a in (regra.acoes or [])} if regra else set()
    # Mapa linear {"<tipo>__<campo>": valor} pra usar direto no template.
    # Le tanto da estrutura aninhada (`acao.config[campo]`, padrao do engine)
    # quanto do nivel superior (fallback retrocompat).
    acoes_extras_flat = {}
    if regra:
        for a in (regra.acoes or []):
            tipo = a.get('tipo', '')
            config = a.get('config') or {}
            for k, v in config.items():
                acoes_extras_flat[f'{tipo}__{k}'] = v
            for k, v in a.items():
                if k in ('tipo', 'config'):
                    continue
                acoes_extras_flat.setdefault(f'{tipo}__{k}', v)
    return {
        'regra': regra,
        'estagios': estagios,
        'estagio_preselecionado_id': estagio_preselecionado,
        'tipos_condicao': TIPOS_CONDICAO,
        'operadores': OPERADORES,
        'acoes_disponiveis': ACOES_DISPONIVEIS,
        'acoes_selecionadas': acoes_selecionadas,
        'acoes_extras_flat': acoes_extras_flat,
    }


def _parse_acoes_do_post(request):
    """Monta lista de acoes a partir do POST. Pra acoes com campos extras
    (definidos em ACOES_DISPONIVEIS_DICT[tipo]['campos_extras']), captura os
    valores dos inputs nomeados `acao_<tipo>__<campo>` e os coloca dentro
    de `acao['config']` (estrutura esperada pelo engine em
    apps.comercial.crm.services.automacao_pipeline._executar_acoes_regra).
    """
    tipos = request.POST.getlist('acao_tipo')
    acoes = []
    for t in tipos:
        t = t.strip()
        if not t:
            continue
        acao = {'tipo': t}
        meta = ACOES_DISPONIVEIS_DICT.get(t, {})
        config = {}
        for campo in meta.get('campos_extras', []):
            nome = campo['name']
            valor = request.POST.get(f'acao_{t}__{nome}', '').strip()
            if not valor:
                continue
            if campo.get('type') == 'number':
                try:
                    valor = int(valor)
                except (ValueError, TypeError):
                    continue
            config[nome] = valor
        if config:
            acao['config'] = config
        acoes.append(acao)
    return acoes


# Templates de regra pre-prontos pra acelerar criacao
REGRA_TEMPLATES = [
    {
        'slug': 'docs_validados_contrato',
        'nome': 'Documentos validados → Assinar contrato HubSoft',
        'descricao': 'Quando todos os documentos do lead estiverem aprovados, assina o contrato no HubSoft automaticamente.',
        'icon': 'bi-file-earmark-check',
        'nome_regra_sugerido': 'Docs validados — Assinar contrato',
        'condicoes': [
            {'tipo': 'imagem_status', 'campo': 'todas_iguais', 'operador': 'igual', 'valor': 'documentos_validos'},
            {'tipo': 'score_externo', 'campo': '', 'operador': 'igual', 'valor': 'aprovado'},
        ],
        'acoes': [{'tipo': 'assinar_contrato_hubsoft'}],
    },
    {
        'slug': 'docs_validados_gerar_contrato',
        'nome': 'Documentos validados → Gerar contrato HubSoft (cria + anexa + aceita)',
        'descricao': 'Mesmo que o anterior, mas cria o contrato do zero (usar so se o tenant nao criar contrato automaticamente).',
        'icon': 'bi-file-earmark-plus',
        'nome_regra_sugerido': 'Docs validados — Gerar contrato',
        'condicoes': [
            {'tipo': 'imagem_status', 'campo': 'todas_iguais', 'operador': 'igual', 'valor': 'documentos_validos'},
            {'tipo': 'score_externo', 'campo': '', 'operador': 'igual', 'valor': 'aprovado'},
        ],
        'acoes': [{'tipo': 'gerar_contrato_hubsoft'}],
    },
    {
        'slug': 'lead_respondeu_mover',
        'nome': 'Lead respondeu o bot → Em Atendimento',
        'descricao': 'Quando o lead enviar a primeira mensagem real ao bot, move pra estagio "Em Atendimento" (selecione abaixo).',
        'icon': 'bi-chat-dots',
        'nome_regra_sugerido': 'Lead respondeu o bot',
        'condicoes': [
            {'tipo': 'historico_status', 'campo': '', 'operador': 'existe', 'valor': 'fluxo_inicializado'},
        ],
        'acoes': [],  # so move estagio (configurar no select estagio)
    },
    {
        'slug': 'venda_criada_pos_venda',
        'nome': 'Venda criada → Mensagem WhatsApp pos-venda',
        'descricao': 'Envia mensagem agradecendo pela compra quando a venda for criada.',
        'icon': 'bi-whatsapp',
        'nome_regra_sugerido': 'Pos-venda WhatsApp',
        'condicoes': [
            {'tipo': 'historico_status', 'campo': '', 'operador': 'existe', 'valor': 'venda_criada'},
        ],
        'acoes': [{'tipo': 'enviar_whatsapp', 'configuracao': 'Obrigado pela compra! Em breve nosso time vai entrar em contato pra agendar a instalacao.'}],
    },
    {
        'slug': 'sem_contato_72h',
        'nome': 'Sem contato em 72h → Criar tarefa de follow-up',
        'descricao': 'Cria tarefa pra vendedor quando lead ficar parado sem novo contato.',
        'icon': 'bi-clock-history',
        'nome_regra_sugerido': 'Follow-up 72h',
        'condicoes': [
            {'tipo': 'historico_status', 'campo': '', 'operador': 'existe', 'valor': 'sem_resposta'},
        ],
        'acoes': [{'tipo': 'criar_tarefa', 'configuracao': 'Follow-up: lead sem contato ha 72h'}],
    },
    {
        'slug': 'em_branco',
        'nome': 'Em branco (do zero)',
        'descricao': 'Crie a regra do zero, sem nenhum campo pre-preenchido.',
        'icon': 'bi-plus-square-dotted',
        'nome_regra_sugerido': '',
        'condicoes': [],
        'acoes': [],
    },
]
REGRA_TEMPLATES_DICT = {t['slug']: t for t in REGRA_TEMPLATES}


@login_required
def regra_pipeline_criar(request):
    denied = _check_perm(request, 'comercial.configurar_pipeline')
    if denied:
        return denied

    from django.shortcuts import redirect
    from .models import RegraPipelineEstagio, PipelineEstagio

    if request.method == 'POST':
        estagio_id = request.POST.get('estagio')
        estagio = PipelineEstagio.objects.filter(pk=estagio_id).first() if estagio_id else None
        acoes = _parse_acoes_do_post(request)
        if not estagio and not acoes:
            return JsonResponse({'error': 'Selecione um estágio destino ou pelo menos uma ação'}, status=400)

        RegraPipelineEstagio.objects.create(
            tenant=request.tenant,
            estagio=estagio,
            nome=request.POST.get('nome', '').strip() or 'Regra sem nome',
            prioridade=int(request.POST.get('prioridade') or 0),
            condicoes=_parse_condicoes_do_post(request),
            acoes=acoes,
            ativo=bool(request.POST.get('ativo')),
        )
        return redirect('crm:automacoes_pipeline')

    estagio_pre = request.GET.get('estagio')
    try:
        estagio_pre = int(estagio_pre) if estagio_pre else None
    except (TypeError, ValueError):
        estagio_pre = None

    template_slug = request.GET.get('template') or ''
    template_dados = REGRA_TEMPLATES_DICT.get(template_slug)

    ctx = _contexto_form_regra(estagio_preselecionado=estagio_pre)
    ctx['regra_templates'] = REGRA_TEMPLATES
    ctx['template_selecionado'] = template_slug
    # Defaults pra evitar VariableDoesNotExist no template
    ctx['nome_pre'] = (template_dados.get('nome_regra_sugerido') or '') if template_dados else ''
    ctx['condicoes_pre'] = json.dumps((template_dados.get('condicoes') or []) if template_dados else [], ensure_ascii=False)
    ctx['acoes_pre'] = json.dumps((template_dados.get('acoes') or []) if template_dados else [], ensure_ascii=False)
    ctx['template_titulo'] = template_dados.get('nome') if template_dados else ''

    return render(request, 'crm/regra_form.html', ctx)


@login_required
def regra_pipeline_editar(request, pk):
    denied = _check_perm(request, 'comercial.configurar_pipeline')
    if denied:
        return denied

    from django.shortcuts import redirect, get_object_or_404
    from .models import RegraPipelineEstagio, PipelineEstagio

    regra = get_object_or_404(RegraPipelineEstagio, pk=pk)

    if request.method == 'POST':
        estagio_id = request.POST.get('estagio')
        estagio = PipelineEstagio.objects.filter(pk=estagio_id).first() if estagio_id else None
        acoes = _parse_acoes_do_post(request)
        if not estagio and not acoes:
            return JsonResponse({'error': 'Selecione um estágio destino ou pelo menos uma ação'}, status=400)
        regra.estagio = estagio
        regra.nome = request.POST.get('nome', regra.nome).strip() or regra.nome
        regra.prioridade = int(request.POST.get('prioridade') or regra.prioridade)
        regra.ativo = bool(request.POST.get('ativo'))
        regra.condicoes = _parse_condicoes_do_post(request)
        regra.acoes = acoes
        regra.save()
        return redirect('crm:automacoes_pipeline')

    ctx = _contexto_form_regra(regra)
    # Defaults pra nao quebrar o template (vars usadas pela tela de "criar" via template)
    ctx.setdefault('regra_templates', [])
    ctx.setdefault('template_selecionado', '')
    ctx.setdefault('nome_pre', '')
    ctx.setdefault('condicoes_pre', '[]')
    ctx.setdefault('acoes_pre', '[]')
    ctx.setdefault('template_titulo', '')
    return render(request, 'crm/regra_form.html', ctx)


@login_required
@require_http_methods(["POST"])
def regra_pipeline_excluir(request, pk):
    denied = _check_perm(request, 'comercial.configurar_pipeline')
    if denied:
        return denied

    from .models import RegraPipelineEstagio

    regra = RegraPipelineEstagio.objects.filter(pk=pk).first()
    if regra:
        regra.delete()
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def regra_pipeline_toggle(request, pk):
    denied = _check_perm(request, 'comercial.configurar_pipeline')
    if denied:
        return denied

    from .models import RegraPipelineEstagio

    regra = RegraPipelineEstagio.objects.filter(pk=pk).first()
    if not regra:
        return JsonResponse({'error': 'Regra não encontrada'}, status=404)

    regra.ativo = not regra.ativo
    regra.save(update_fields=['ativo', 'atualizado_em'])
    return JsonResponse({'success': True, 'ativo': regra.ativo})


@login_required
@require_http_methods(["POST"])
def regra_pipeline_duplicar(request, pk):
    denied = _check_perm(request, 'comercial.configurar_pipeline')
    if denied:
        return denied

    from .models import RegraPipelineEstagio

    regra = RegraPipelineEstagio.objects.filter(pk=pk).first()
    if not regra:
        return JsonResponse({'error': 'Regra não encontrada'}, status=404)

    RegraPipelineEstagio.objects.create(
        estagio=regra.estagio,
        nome=f"{regra.nome} (cópia)",
        prioridade=regra.prioridade + 1,
        condicoes=list(regra.condicoes or []),
        ativo=False,
    )
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def regra_pipeline_preview(request, pk):
    """
    Retorna quantas oportunidades atualmente bateriam com essa regra.
    Útil pra o usuário testar antes de ativar.
    """
    denied = _check_perm(request, 'comercial.configurar_pipeline')
    if denied:
        return denied

    from .models import RegraPipelineEstagio, OportunidadeVenda, ConfiguracaoCRM
    from .services.automacao_pipeline import _construir_contexto, _regra_bate

    regra = RegraPipelineEstagio.objects.filter(pk=pk).first()
    if not regra:
        return JsonResponse({'error': 'Regra não encontrada'}, status=404)

    # Limite configurável por tenant
    try:
        limite = ConfiguracaoCRM.get_config().preview_regras_max or 500
    except Exception:
        limite = 500
    limite = max(10, min(limite, 10000))  # sanity bounds

    # Só oportunidades fora de estágio final
    oportunidades = (
        OportunidadeVenda.objects
        .select_related('estagio', 'lead')
        .filter(estagio__is_final_ganho=False, estagio__is_final_perdido=False)
    )

    matches = 0
    for opp in oportunidades[:limite]:
        contexto = _construir_contexto(opp)
        if _regra_bate(regra, contexto):
            matches += 1

    return JsonResponse({
        'success': True,
        'regra_id': regra.pk,
        'regra_nome': regra.nome,
        'oportunidades_que_bateriam': matches,
        'total_avaliado': min(oportunidades.count(), limite),
        'limite_configurado': limite,
    })


@login_required
@require_http_methods(["GET"])
def regra_pipeline_historico(request, pk):
    """Retorna os ultimos 50 disparos de uma regra (do log_sistema central).

    Lê de LogSistema filtrando por dados_extras.regra_id=pk e categoria='crm'.
    Inclui mover_regra (movimentações) e acoes_regra (execução de ações).
    """
    denied = _check_perm(request, 'comercial.configurar_pipeline')
    if denied:
        return denied

    from .models import RegraPipelineEstagio, OportunidadeVenda
    from apps.sistema.models import LogSistema

    regra = RegraPipelineEstagio.objects.filter(pk=pk).first()
    if not regra:
        return JsonResponse({'error': 'Regra não encontrada'}, status=404)

    logs = list(
        LogSistema.objects
        .filter(categoria='crm', dados_extras__regra_id=pk)
        .order_by('-data_criacao')[:50]
    )

    op_ids = {l.entidade_id for l in logs if l.entidade == 'oportunidade' and l.entidade_id}
    ops = {
        o.pk: o
        for o in OportunidadeVenda.objects.filter(pk__in=op_ids).select_related('lead')
    }

    items = []
    for log in logs:
        extras = log.dados_extras if isinstance(log.dados_extras, dict) else {}
        op = ops.get(log.entidade_id) if log.entidade == 'oportunidade' else None
        lead = op.lead if op else None
        items.append({
            'data': log.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'acao_tipo': log.acao,
            'oportunidade_id': op.pk if op else log.entidade_id,
            'oportunidade_url': f'/crm/oportunidade/{op.pk}/' if op else None,
            'lead_nome': lead.nome_razaosocial if lead else None,
            'estagio_anterior': extras.get('estagio_anterior_nome') or '',
            'estagio_destino': extras.get('estagio_destino_nome') or '',
            'acoes_executadas': extras.get('acoes_executadas') or [],
            'houve_efetiva': extras.get('houve_efetiva'),
            'horas_no_estagio_anterior': extras.get('horas_no_estagio_anterior'),
            'mensagem': log.mensagem,
        })

    return JsonResponse({
        'success': True,
        'regra_id': regra.pk,
        'regra_nome': regra.nome,
        'total': len(items),
        'items': items,
    })


def _planos_por_cep(tenant, cep_digits):
    """Planos vendaveis no CEP segundo o HubSoft (catalogo da unidade de
    negocio da cidade), com cache curto por tenant+cep.

    Retorna lista [{id_hubsoft, nome, valor}] ou None quando nao da pra
    saber (sem integracao ativa ou consulta falhou) — caller decide o
    fail-open."""
    from django.core.cache import cache as _cache
    chave = f'planos_cep:{tenant.pk}:{cep_digits}'
    planos = _cache.get(chave)
    if planos is not None:
        return planos
    try:
        from apps.integracoes.models import IntegracaoAPI
        from apps.integracoes.services.hubsoft import HubsoftService
        integ = IntegracaoAPI.all_tenants.filter(
            tenant=tenant, tipo='hubsoft', ativa=True,
        ).first()
        if not integ:
            return None
        servicos = HubsoftService(integ).listar_planos_por_cep(cep_digits)
        planos = [
            {
                'id_hubsoft': s.get('id_servico'),
                'nome': s.get('descricao') or s.get('display') or '',
                'valor': s.get('valor'),
            }
            for s in servicos if s.get('id_servico') is not None
        ]
        _cache.set(chave, planos, 600)
        return planos
    except Exception:
        return None


@login_required
@require_http_methods(["GET"])
def api_planos_por_cep(request):
    """Alimenta o dropdown do cadastro completo: a vendedora preenche o
    endereco e os planos mudam conforme a regiao (caso Jefferson/Itu 10/07:
    plano de unidade errada gravado no HubSoft trava o prospecto inteiro).
    `planos: null` = nao foi possivel consultar, front mantem catalogo cheio."""
    cep = ''.join(ch for ch in request.GET.get('cep', '') if ch.isdigit())
    if len(cep) != 8:
        return JsonResponse({'ok': False, 'erro': 'CEP invalido'}, status=400)
    return JsonResponse({'ok': True, 'planos': _planos_por_cep(request.tenant, cep)})


@login_required
@require_http_methods(["GET", "POST"])
def api_cadastro_completo_oportunidade(request, pk):
    """Modal "Completar dados da venda" — agrupa todos os campos obrigatorios
    pro vendedor preencher de uma vez (sem mudar logica de back-end).

    GET: retorna dict com dados atuais do Lead + opcoes (vencimentos, planos).
    POST: recebe JSON com campos, atualiza LeadProspecto. Signal post_save
          dispara o motor de regras normalmente — sem caminho paralelo.
    """
    try:
        op = OportunidadeVenda.objects.select_related('lead', 'responsavel').get(pk=pk)
    except OportunidadeVenda.DoesNotExist:
        return JsonResponse({'error': 'Oportunidade nao encontrada'}, status=404)

    lead = op.lead
    if not lead:
        return JsonResponse({'error': 'Oportunidade sem lead vinculado'}, status=400)

    if request.method == 'GET':
        viab = (lead.dados_custom or {}).get('viabilidade') or {}

        # Planos vem do catalogo ProdutoServico (categoria='plano', ativo=True).
        # Antes era lista hardcoded de 5 (300/400/500/600/800MB) que escondia
        # planos promocionais e outros do catalogo.
        from apps.comercial.crm.models import ProdutoServico
        planos_catalogo = ProdutoServico.all_tenants.filter(
            tenant=request.tenant, categoria='plano', ativo=True,
        ).exclude(id_externo='').order_by('preco', 'nome')
        opcoes_planos = []
        for p in planos_catalogo:
            try:
                id_hub = int(str(p.id_externo).strip())
            except (ValueError, TypeError):
                continue
            empresa = (p.dados_erp or {}).get('empresa') or ''
            opcoes_planos.append({
                'id_hubsoft': id_hub,
                'nome': p.nome,
                'valor': float(p.preco or 0),
                'empresa': empresa,
            })

        opcoes_vencimentos = [
            {'id_hubsoft': 9, 'dia': 5},
            {'id_hubsoft': 4, 'dia': 10},
            {'id_hubsoft': 5, 'dia': 15},
            {'id_hubsoft': 6, 'dia': 20},
        ]
        # Origens (cliente + servico) — do cache da IntegracaoAPI HubSoft.
        # Lista vazia se nao houver integracao ou cache.
        opcoes_origens_cliente = []
        opcoes_origens_servico = []
        try:
            from apps.integracoes.models import IntegracaoAPI
            integ = IntegracaoAPI.all_tenants.filter(
                tenant=request.tenant, tipo='hubsoft', ativa=True,
            ).first()
            if integ:
                extras = integ.configuracoes_extras or {}
                if extras.get('planos_disponiveis'):
                    opcoes_planos = extras['planos_disponiveis']
                if extras.get('dias_vencimento_disponiveis'):
                    opcoes_vencimentos = extras['dias_vencimento_disponiveis']
                # Origens vem do cache (sincronizado pela API HubSoft)
                cache = extras.get('cache') or {}
                for it in (cache.get('origens_cliente') or []):
                    if it.get('id_origem_cliente') is not None:
                        opcoes_origens_cliente.append({
                            'id': int(it['id_origem_cliente']),
                            'nome': it.get('descricao') or it.get('nome') or f'#{it["id_origem_cliente"]}',
                        })
                for it in (cache.get('origens_contato') or []):
                    if it.get('id_origem_contato') is not None:
                        opcoes_origens_servico.append({
                            'id': int(it['id_origem_contato']),
                            'nome': it.get('descricao') or it.get('nome') or f'#{it["id_origem_contato"]}',
                        })
                opcoes_origens_cliente.sort(key=lambda x: x['nome'])
                opcoes_origens_servico.sort(key=lambda x: x['nome'])
        except Exception:
            pass

        return JsonResponse({
            'success': True,
            'oportunidade_id': op.pk,
            'lead': {
                'id': lead.pk,
                'nome': lead.nome_razaosocial or '',
                'cpf_cnpj': lead.cpf_cnpj or '',
                'data_nascimento': lead.data_nascimento.strftime('%Y-%m-%d') if lead.data_nascimento else '',
                'rg': lead.rg or '',
                'email': lead.email or '',
                'telefone': lead.telefone or '',
                'cep': lead.cep or '',
                'rua': lead.rua or '',
                'numero_residencia': lead.numero_residencia or '',
                'complemento': lead.complemento or '',
                'bairro': lead.bairro or '',
                'cidade': lead.cidade or '',
                'estado': lead.estado or '',
                'id_plano_rp': lead.id_plano_rp or '',
                'id_dia_vencimento': lead.id_dia_vencimento or '',
                'id_hubsoft': lead.id_hubsoft or '',
                'status_api': lead.status_api or '',
                'observacoes': lead.observacoes or '',
                'ponto_referencia': lead.ponto_referencia or '',
                'id_origem': lead.id_origem or '',
                'id_origem_servico': lead.id_origem_servico or '',
            },
            'responsavel': {
                'id': op.responsavel_id,
                'nome': op.responsavel.get_full_name() if op.responsavel else '',
            } if op.responsavel else None,
            'viabilidade': {
                'status': viab.get('status') or '',
                'consultado_em': viab.get('consultado_em') or '',
            },
            'opcoes_planos': opcoes_planos,
            'opcoes_vencimentos': opcoes_vencimentos,
            'opcoes_origens_cliente': opcoes_origens_cliente,
            'opcoes_origens_servico': opcoes_origens_servico,
        })

    # POST — atualiza Lead
    import json
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    campos_permitidos = {
        'nome_razaosocial', 'cpf_cnpj', 'data_nascimento', 'rg', 'email',
        'telefone', 'cep', 'rua', 'numero_residencia', 'complemento',
        'bairro', 'cidade', 'estado', 'id_plano_rp', 'id_dia_vencimento',
        'observacoes', 'ponto_referencia', 'id_origem', 'id_origem_servico',
    }
    # Mapeamento de chaves do JS pro Lead (alguns nomes diferentes)
    aliases = {
        'nome': 'nome_razaosocial',
    }

    # Campos numericos do model (IntegerField) — string vazia precisa virar
    # None pra nao explodir "expected a number but got ''"
    CAMPOS_INT_NULLABLE = {'id_plano_rp', 'id_dia_vencimento'}

    update_fields = {}
    for k, v in (data.items() if isinstance(data, dict) else []):
        campo = aliases.get(k, k)
        if campo not in campos_permitidos:
            continue
        valor = v if v is not None else ''
        if campo == 'data_nascimento' and valor:
            try:
                from datetime import datetime as _dt
                valor = _dt.strptime(valor, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                continue
        if campo == 'data_nascimento' and not valor:
            valor = None
        if campo in CAMPOS_INT_NULLABLE:
            if valor in ('', None):
                valor = None
            else:
                try:
                    valor = int(str(valor).strip())
                except (ValueError, TypeError):
                    continue
        update_fields[campo] = valor

    if not update_fields:
        return JsonResponse({'error': 'Nenhum campo valido pra atualizar'}, status=400)

    # Obrigatorios de negocio no cadastro completo: email + origens. Valida o
    # ESTADO FINAL (payload aplicado sobre o que o lead ja tem), pra barrar
    # salvar vazio sem exigir reenvio de campo ja preenchido antes.
    OBRIGATORIOS_CADASTRO = {
        'email': 'Email',
        'id_origem': 'Origem do cliente',
        'id_origem_servico': 'Origem do contato',
    }
    faltando = []
    for campo, label in OBRIGATORIOS_CADASTRO.items():
        valor_final = update_fields.get(campo, getattr(lead, campo, None))
        if valor_final in ('', None):
            faltando.append(label)
    if faltando:
        return JsonResponse({
            'error': 'Campos obrigatorios: ' + ', '.join(faltando),
            'campos_obrigatorios': faltando,
        }, status=400)

    # Plano x cidade: bloqueia salvar plano que o HubSoft nao vende no CEP
    # informado (caso Jefferson/Itu 10/07: plano de unidade errada gravado
    # trava o prospecto no HubSoft, nem edicao sem servico passa depois).
    # Fail-open: consulta indisponivel nao bloqueia o save.
    plano_final = update_fields.get('id_plano_rp', lead.id_plano_rp)
    cep_final = ''.join(ch for ch in str(update_fields.get('cep', lead.cep) or '') if ch.isdigit())
    if plano_final and len(cep_final) == 8:
        planos_cep = _planos_por_cep(request.tenant, cep_final)
        if planos_cep is not None:
            ids_validos = {int(p['id_hubsoft']) for p in planos_cep}
            try:
                plano_int = int(plano_final)
            except (ValueError, TypeError):
                plano_int = None
            if plano_int is not None and plano_int not in ids_validos:
                return JsonResponse({
                    'error': 'O plano escolhido nao e vendido no endereco informado '
                             '(unidade de negocio da cidade). Escolha um plano '
                             'disponivel pra esse CEP.',
                    'campos_obrigatorios': ['Plano compativel com a cidade'],
                }, status=400)

    try:
        from apps.comercial.leads.models import LeadProspecto
        for k, v in update_fields.items():
            setattr(lead, k, v)
        lead.save(update_fields=list(update_fields.keys()) + ['data_atualizacao'])
    except Exception as exc:
        return JsonResponse({'error': f'Falha ao salvar: {exc!s}'[:300]}, status=500)

    try:
        from apps.sistema.utils import registrar_acao
        campos_str = ', '.join(sorted(update_fields.keys()))
        registrar_acao(
            'crm', 'editar', 'oportunidade', op.pk,
            f"Campos atualizados via modal cadastro-completo: {campos_str}",
            request=request,
            dados_extras={'oportunidade_id': op.pk, 'lead_id': lead.pk, 'campos': list(update_fields.keys())},
        )
    except Exception:
        pass

    return JsonResponse({
        'success': True,
        'campos_atualizados': sorted(update_fields.keys()),
        'lead_id': lead.pk,
    })


@login_required
@require_http_methods(["POST"])
def api_sugestao_aplicar(request, pk):
    """
    Aplica a sugestão de próxima ação: cria TarefaCRM com os dados da sugestão
    e marca o estado como 'aplicada' (regenera em 3 dias).
    """
    try:
        op = OportunidadeVenda.objects.get(pk=pk)
    except OportunidadeVenda.DoesNotExist:
        return JsonResponse({'error': 'Oportunidade não encontrada'}, status=404)

    sugestao = op.proxima_acao_sugerida or {}
    if not sugestao or sugestao.get('estado') != 'pendente':
        return JsonResponse({'error': 'Sem sugestão pendente'}, status=400)

    try:
        tarefa = TarefaCRM.objects.create(
            tenant=op.tenant,
            oportunidade=op,
            lead=op.lead,
            titulo=sugestao.get('titulo', 'Próxima ação sugerida pela IA')[:200],
            descricao=(
                f"{sugestao.get('mensagem_sugerida', '')}\n\n"
                f"--- Sugerido por IA ---\n"
                f"Justificativa: {sugestao.get('justificativa', '')}"
            ),
            tipo=sugestao.get('tipo', 'outro')[:30],
            prioridade='alta' if sugestao.get('urgencia') == 'alta' else 'normal',
            data_vencimento=timezone.now() + timezone.timedelta(hours=24),
            responsavel=op.responsavel or request.user,
            criado_por=request.user,
        )
    except Exception as exc:
        return JsonResponse({'error': f'Falha ao criar tarefa: {exc}'}, status=500)

    sugestao['estado'] = 'aplicada'
    sugestao['aplicada_em'] = timezone.now().isoformat()
    sugestao['tarefa_id'] = tarefa.id
    op.proxima_acao_sugerida = sugestao
    op.save(update_fields=['proxima_acao_sugerida'])

    from apps.sistema.utils import registrar_acao
    registrar_acao(
        'crm', 'aplicar_sugestao_ia', 'oportunidade', op.id,
        f'Sugestão IA aplicada → tarefa #{tarefa.id}: {tarefa.titulo[:80]}',
        request=request,
    )

    return JsonResponse({'success': True, 'tarefa_id': tarefa.id})


@login_required
@require_http_methods(["POST"])
def api_sugestao_rejeitar(request, pk):
    """Marca sugestão como rejeitada (regenera em 3 dias)."""
    try:
        op = OportunidadeVenda.objects.get(pk=pk)
    except OportunidadeVenda.DoesNotExist:
        return JsonResponse({'error': 'Oportunidade não encontrada'}, status=404)

    sugestao = op.proxima_acao_sugerida or {}
    if not sugestao:
        return JsonResponse({'error': 'Sem sugestão'}, status=400)

    sugestao['estado'] = 'rejeitada'
    sugestao['rejeitada_em'] = timezone.now().isoformat()
    op.proxima_acao_sugerida = sugestao
    op.save(update_fields=['proxima_acao_sugerida'])

    return JsonResponse({'success': True})


@login_required
def relatorio_win_loss(request):
    """
    Dashboard de Win/Loss analysis.
    Mostra oportunidades ganhas e perdidas no período, agrupadas por motivo
    categorizado, com timeline e filtro por período.
    """
    from datetime import timedelta
    from django.db.models import Count, Sum

    # Ve tudo (ver_todas) ou o proprio escopo de equipe. Vendedor comum: 403.
    esc = escopo_responsaveis(request)
    if esc is not None and not user_tem_funcionalidade(request, 'comercial.ver_oportunidades_da_equipe'):
        return JsonResponse({'error': 'Acesso negado'}, status=403)

    # Período: últimos 90 dias por padrão
    dias = int(request.GET.get('dias', 90))
    desde = timezone.now() - timedelta(days=dias)

    from django.db.models import Q
    # valor_estimado virou property — usa com_valor_estimado() pros Sums
    qs = OportunidadeVenda.objects.com_valor_estimado().filter(
        Q(estagio__is_final_ganho=True) | Q(estagio__is_final_perdido=True),
        data_atualizacao__gte=desde,
    )
    if esc is not None:
        qs = qs.filter(responsavel_id__in=esc)

    ganhas = qs.filter(estagio__is_final_ganho=True)
    perdidas = qs.filter(estagio__is_final_perdido=True)

    breakdown_perda = (
        perdidas.values('motivo_perda_ref', 'motivo_perda_ref__nome')
        .annotate(qtd=Count('id'), valor=Sum('valor_estimado_anotado'))
        .order_by('-qtd')
    )
    breakdown_ganho = (
        ganhas.values('motivo_ganho_categoria')
        .annotate(qtd=Count('id'), valor=Sum('valor_estimado_anotado'))
        .order_by('-qtd')
    )

    total_ganhas = ganhas.count()
    total_perdidas = perdidas.count()
    total = total_ganhas + total_perdidas
    win_rate = round(total_ganhas / total * 100, 1) if total else 0

    valor_ganho = ganhas.aggregate(total=Sum('valor_estimado_anotado'))['total'] or 0
    valor_perdido = perdidas.aggregate(total=Sum('valor_estimado_anotado'))['total'] or 0

    # Mapa de label legível (ganho ainda usa choices fixas)
    ganho_labels = dict(OportunidadeVenda.MOTIVO_GANHO_CHOICES)

    breakdown_perda_lst = []
    for item in breakdown_perda:
        nome = item['motivo_perda_ref__nome']
        breakdown_perda_lst.append({
            'categoria': item['motivo_perda_ref'],
            'label': nome or 'Sem categoria',
            'qtd': item['qtd'],
            'valor': item['valor'] or 0,
            'percent': round(item['qtd'] / total_perdidas * 100, 1) if total_perdidas else 0,
        })

    breakdown_ganho_lst = []
    for item in breakdown_ganho:
        cat = item['motivo_ganho_categoria']
        breakdown_ganho_lst.append({
            'categoria': cat,
            'label': ganho_labels.get(cat, 'Sem categoria') if cat else 'Sem categoria',
            'qtd': item['qtd'],
            'valor': item['valor'] or 0,
            'percent': round(item['qtd'] / total_ganhas * 100, 1) if total_ganhas else 0,
        })

    return render(request, 'crm/relatorio_win_loss.html', {
        'dias': dias,
        'desde': desde,
        'total_ganhas': total_ganhas,
        'total_perdidas': total_perdidas,
        'total_fechadas': total,
        'win_rate': win_rate,
        'valor_ganho': valor_ganho,
        'valor_perdido': valor_perdido,
        'breakdown_perda': breakdown_perda_lst,
        'breakdown_ganho': breakdown_ganho_lst,
        'page_title': 'Win/Loss Analysis',
    })


# ============================================================================
# T7 — Tela dedicada de Motivos de Perda
# ============================================================================

@login_required
def motivos_perda_lista(request):
    """CRUD dedicado de MotivoPerda em /crm/motivos-perda/."""
    from .models import MotivoPerda, OportunidadeVenda
    from django.db.models import Count
    from django.contrib import messages
    from django.shortcuts import redirect

    denied = _check_perm(request, 'comercial.configurar_pipeline')
    if denied:
        return denied

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'criar':
            nome = (request.POST.get('nome') or '').strip()
            if nome and not MotivoPerda.objects.filter(nome=nome).exists():
                ult = MotivoPerda.objects.order_by('-ordem').first()
                MotivoPerda.objects.create(
                    tenant=request.tenant, nome=nome,
                    ordem=(ult.ordem + 1) if ult else 1,
                )
                messages.success(request, f'Motivo "{nome}" criado.')
            elif nome:
                messages.warning(request, f'Motivo "{nome}" ja existe.')
            return redirect('crm:motivos_perda_lista')

        elif action == 'editar':
            mid = request.POST.get('motivo_id')
            nome = (request.POST.get('nome') or '').strip()
            ativo = bool(request.POST.get('ativo'))
            motivo = MotivoPerda.objects.filter(pk=mid).first()
            if motivo and nome:
                motivo.nome = nome
                motivo.ativo = ativo
                motivo.save(update_fields=['nome', 'ativo'])
                messages.success(request, f'Motivo "{nome}" atualizado.')
            return redirect('crm:motivos_perda_lista')

        elif action == 'excluir':
            mid = request.POST.get('motivo_id')
            motivo = MotivoPerda.objects.filter(pk=mid).first()
            if motivo:
                em_uso = OportunidadeVenda.objects.filter(motivo_perda_ref=motivo).count()
                nome = motivo.nome
                motivo.delete()
                if em_uso:
                    messages.warning(
                        request,
                        f'Motivo "{nome}" excluido. {em_uso} oportunidade(s) tinha(m) esse '
                        f'motivo - agora aparecem sem motivo cadastrado.'
                    )
                else:
                    messages.success(request, f'Motivo "{nome}" excluido.')
            return redirect('crm:motivos_perda_lista')

    # GET — lista com contagem de uso
    motivos = (
        MotivoPerda.objects.all()
        .annotate(qtd_oportunidades=Count('oportunidades'))
        .order_by('ordem', 'nome')
    )
    total_ativos = MotivoPerda.objects.filter(ativo=True).count()
    # uso ultimos 12m (oportunidades atualizadas)
    from datetime import timedelta
    desde = timezone.now() - timedelta(days=365)
    uso_12m = (
        OportunidadeVenda.objects
        .filter(motivo_perda_ref__isnull=False, data_atualizacao__gte=desde)
        .count()
    )

    return render(request, 'crm/motivos_perda.html', {
        'motivos': motivos,
        'total_ativos': total_ativos,
        'uso_12m': uso_12m,
        'page_title': 'Motivos de Perda',
    })
