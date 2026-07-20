"""Workspace — Checklists: roteiros de pergunta que o bot (Matrix) ou um humano
conduz pra preencher dados de um lead/oportunidade passo a passo.

Reusa os models/services do apps/automacao (Checklist, ItemChecklist,
services/checklist.py). O bot (Matrix) já consome tudo pelos endpoints /ia/*
do apps/comercial/atendimento_ia — esta tela é só a UI de gestão, hoje só
disponível via shell, pra Gabi (Nuvyon) montar o roteiro dela sozinha.

Espelha o padrão de apps/workspace/views/agentes.py: mesmos decorators,
mesmo padrão de tenant (`request.tenant` + `.all_tenants.filter(tenant=...)`)
e mesmo formato de resposta JSON (`{'ok': True, ...}` / `{'erro': ...}`).
"""
import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Max
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.sistema.decorators import user_tem_funcionalidade
from apps.sistema.utils import registrar_acao

# Quantas entidades por pagina na tela "Em andamento".
ENTIDADES_POR_PAGINA = 25


# ============================================================================
# Checklist — lista + editor
# ============================================================================

@login_required
def lista(request):
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden('Sem permissao pra acessar Workspace.')
    tenant = getattr(request, 'tenant', None)
    from apps.automacao.models import Checklist
    checklists = []
    if tenant is not None:
        checklists = list(
            Checklist.all_tenants.filter(tenant=tenant)
            .annotate(total_itens=Count('itens'))
            .order_by('nome')
        )
    return render(request, 'workspace/checklists.html', {
        'checklists': checklists,
        'total': len(checklists),
        'pode_editar': user_tem_funcionalidade(request, 'workspace.editar_todos'),
        'pagetitle': 'Checklists',
    })


@login_required
def editar_page(request, pk=None):
    """Form de criar/editar um checklist (dados + itens do roteiro)."""
    if not user_tem_funcionalidade(request, 'workspace.editar_todos'):
        return HttpResponseForbidden('Sem permissao pra gerenciar checklists.')
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return HttpResponseForbidden('sem tenant')
    from apps.automacao.models import Checklist, ItemChecklist
    from apps.comercial.leads.models import CampoCustomizado

    checklist = None
    itens = []
    if pk:
        checklist = Checklist.all_tenants.filter(tenant=tenant, pk=pk).first()
        if checklist is None:
            raise Http404('checklist nao encontrado')
        itens = list(checklist.itens.order_by('ordem', 'id'))

    campos = list(CampoCustomizado.all_tenants.filter(tenant=tenant, ativo=True).order_by('entidade', 'nome'))

    itens_data = [{
        'id': item.pk,
        'ordem': item.ordem,
        'chave': item.chave,
        'pergunta': item.pergunta,
        'ajuda': item.ajuda,
        'tipo_resposta': item.tipo_resposta,
        'opcoes': item.opcoes,
        'ura_titulo': item.ura_titulo,
        'tipo_validacao': item.tipo_validacao,
        'regex_validacao': item.regex_validacao,
        'instrucoes_ia': item.instrucoes_ia,
        'obrigatorio': item.obrigatorio,
        'max_tentativas': item.max_tentativas,
        'estrategia_erro': item.estrategia_erro,
        'mensagem_erro': item.mensagem_erro,
        'mensagem_sucesso': item.mensagem_sucesso,
        'mensagem_recontato': item.mensagem_recontato,
        'campo': item.campo_id,
    } for item in itens]

    return render(request, 'workspace/checklist_editar.html', {
        'checklist': checklist,
        'itens': itens,
        'itens_data': itens_data,
        'campos': campos,
        'contexto_choices': Checklist.CONTEXTO_CHOICES,
        'modo_choices': Checklist.MODO_PREENCHIMENTO_CHOICES,
        'entidade_choices': Checklist.ENTIDADE_ALVO_CHOICES,
        'tipo_resposta_choices': ItemChecklist.TIPO_RESPOSTA_CHOICES,
        'tipo_validacao_choices': ItemChecklist.TIPO_VALIDACAO_CHOICES,
        'estrategia_erro_choices': ItemChecklist.ESTRATEGIA_ERRO_CHOICES,
        'ura_titulo_choices': ItemChecklist.URA_TITULO_CHOICES,
        'pagetitle': checklist.nome if checklist else 'Novo checklist',
    })


@login_required
def respostas_page(request, pk):
    """Tela "Em andamento": uma linha por entidade que ja comecou a responder
    este checklist, com progresso, em qual item parou e quando respondeu por
    ultimo. E a unica janela pro que o bot coletou.

    DESEMPENHO (a escolha feita aqui): chamar `progresso()`/`proximo_item()` por
    entidade custaria 2 queries por linha (N+1 classico). Em vez disso:
      1. UMA query agregada lista as entidades e a data da ultima resposta
         (`values(...).annotate(Max(...))`), ja ordenada e paginada no banco;
      2. os itens do checklist sao carregados UMA vez (`itens_ativos`);
      3. as respostas das 25 entidades da pagina vem em UMA query
         (`respostas_por_entidade`);
      4. os leads da pagina vem em UMA query (`pk__in`).
    O calculo em si continua sendo o do servico (`progresso_de` /
    `proximo_item_de`, as mesmas funcoes que `progresso()` usa por dentro), entao
    a regra nao foi duplicada. Custo total: constante, nao cresce com a lista.
    """
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden('Sem permissao pra acessar Workspace.')
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return HttpResponseForbidden('sem tenant')
    from apps.automacao.models import Checklist, RespostaChecklist
    from apps.automacao.services import checklist as servico

    checklist = Checklist.all_tenants.filter(tenant=tenant, pk=pk).first()
    if checklist is None:
        raise Http404('checklist nao encontrado')

    agregado = (
        RespostaChecklist.all_tenants
        .filter(tenant=tenant, checklist=checklist)
        .values('entidade_tipo', 'entidade_id')
        .annotate(ultima_resposta=Max('atualizado_em'))
        .order_by('-ultima_resposta')
    )
    paginator = Paginator(agregado, ENTIDADES_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))

    pares = [(linha['entidade_tipo'], linha['entidade_id']) for linha in page_obj]
    itens = servico.itens_ativos(checklist)
    respostas_por_par = servico.respostas_por_entidade(checklist, pares)

    # Rotulo do tipo de entidade sai das choices do model, nunca de string solta.
    rotulos = dict(Checklist.ENTIDADE_ALVO_CHOICES)

    ids_lead = [ident for tipo, ident in pares if tipo == servico.ENTIDADE_LEAD]
    leads = {}
    if ids_lead:
        from apps.comercial.leads.models import LeadProspecto
        leads = {
            lead.pk: lead
            for lead in LeadProspecto.all_tenants.filter(tenant=tenant, pk__in=ids_lead)
        }

    linhas = []
    for registro in page_obj:
        tipo = registro['entidade_tipo']
        entidade_id = registro['entidade_id']
        respostas = respostas_por_par.get((tipo, entidade_id), {})
        rotulo = rotulos.get(tipo, tipo)
        lead = leads.get(entidade_id) if tipo == servico.ENTIDADE_LEAD else None

        if lead is not None:
            nome = lead.nome_razaosocial
            telefone = lead.telefone
            url_detalhe = reverse('comercial_leads:lead_detail', args=[entidade_id])
        elif tipo == servico.ENTIDADE_LEAD:
            # Lead apagado depois de responder: a resposta continua no banco.
            # A tela mostra o registro orfao em vez de quebrar.
            nome = f'{rotulo} #{entidade_id} (removido)'
            telefone = ''
            url_detalhe = ''
        else:
            nome = f'{rotulo} #{entidade_id}'
            telefone = ''
            url_detalhe = ''

        progresso = servico.progresso_de(itens, respostas)
        linhas.append({
            'nome': nome,
            'telefone': telefone,
            'url_detalhe': url_detalhe,
            'progresso': progresso,
            'rotulo_progresso': f"{progresso['respondidos']}/{progresso['total']}",
            'proximo_item': servico.proximo_item_de(itens, respostas),
            'ultima_resposta': registro['ultima_resposta'],
        })

    return render(request, 'workspace/checklist_respostas.html', {
        'checklist': checklist,
        'linhas': linhas,
        'page_obj': page_obj,
        'total_entidades': paginator.count,
        'pode_editar': user_tem_funcionalidade(request, 'workspace.editar_todos'),
        'pagetitle': f'Em andamento, {checklist.nome}',
    })


@require_POST
@login_required
def salvar(request):
    """Cria/atualiza um checklist do tenant. Valida slug unico por tenant."""
    if not user_tem_funcionalidade(request, 'workspace.editar_todos'):
        return JsonResponse({'erro': 'sem permissao'}, status=403)
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return JsonResponse({'erro': 'sem tenant'}, status=400)
    from apps.automacao.models import Checklist

    nome = (request.POST.get('nome') or '').strip()
    if not nome:
        return JsonResponse({'erro': 'nome obrigatorio'}, status=400)

    slug = slugify((request.POST.get('slug') or nome).strip())[:100]
    if not slug:
        return JsonResponse({'erro': 'slug obrigatorio'}, status=400)

    pk = (request.POST.get('id') or '').strip()
    criando = not pk.isdigit()
    if not criando:
        checklist = Checklist.all_tenants.filter(tenant=tenant, pk=int(pk)).first()
        if checklist is None:
            return JsonResponse({'erro': 'checklist nao encontrado'}, status=404)
    else:
        checklist = Checklist(tenant=tenant)

    duplicado = (
        Checklist.all_tenants.filter(tenant=tenant, slug=slug)
        .exclude(pk=checklist.pk)
        .exists()
    )
    if duplicado:
        return JsonResponse({'erro': f'ja existe um checklist com o slug "{slug}" neste tenant'}, status=400)

    contextos_validos = {k for k, _ in Checklist.CONTEXTO_CHOICES}
    modos_validos = {k for k, _ in Checklist.MODO_PREENCHIMENTO_CHOICES}
    entidades_validas = {k for k, _ in Checklist.ENTIDADE_ALVO_CHOICES}

    contexto = (request.POST.get('contexto') or '').strip()
    modo = (request.POST.get('modo_preenchimento') or '').strip()
    entidade = (request.POST.get('entidade_alvo') or '').strip()

    checklist.nome = nome
    checklist.slug = slug
    checklist.descricao = (request.POST.get('descricao') or '').strip()
    checklist.contexto = contexto if contexto in contextos_validos else 'bot_vendas'
    checklist.modo_preenchimento = modo if modo in modos_validos else 'ia'
    checklist.entidade_alvo = entidade if entidade in entidades_validas else 'lead'
    checklist.bloqueia_avanco = (request.POST.get('bloqueia_avanco') or '') in ('on', 'true', '1')
    checklist.ativo = (request.POST.get('ativo') or '') in ('on', 'true', '1')
    checklist.save()

    try:
        registrar_acao('config', 'criar' if criando else 'editar', 'checklist', checklist.pk,
                        f"Checklist '{checklist.nome}' {'criado' if criando else 'atualizado'}",
                        request=request)
    except Exception:
        pass
    return JsonResponse({'ok': True, 'id': checklist.pk})


@require_POST
@login_required
def excluir(request, pk):
    """Remove um checklist do tenant (e seus itens/respostas, via CASCADE)."""
    if not user_tem_funcionalidade(request, 'workspace.editar_todos'):
        return JsonResponse({'erro': 'sem permissao'}, status=403)
    tenant = getattr(request, 'tenant', None)
    from apps.automacao.models import Checklist
    checklist = Checklist.all_tenants.filter(tenant=tenant, pk=pk).first()
    if checklist is None:
        return JsonResponse({'erro': 'checklist nao encontrado'}, status=404)
    nome = checklist.nome
    checklist.delete()
    try:
        registrar_acao('config', 'excluir', 'checklist', pk, f"Checklist '{nome}' excluido", request=request)
    except Exception:
        pass
    return JsonResponse({'ok': True})


# ============================================================================
# Itens do checklist
# ============================================================================

def _mensagens_validation_error(exc):
    """Achata um ValidationError (dict ou lista) numa unica string legivel."""
    mensagens = []
    if hasattr(exc, 'message_dict'):
        for _campo, msgs in exc.message_dict.items():
            mensagens.extend(msgs)
    else:
        mensagens.extend(exc.messages)
    return ' '.join(mensagens)


@require_POST
@login_required
def item_salvar(request, pk):
    """Cria/atualiza um item (pergunta) do checklist `pk`. SEMPRE passa por
    `full_clean()` — é o `ItemChecklist.clean()` que protege o contrato com o
    Matrix (2 a 5 opcoes, ura_titulo fechado, regex que compila)."""
    if not user_tem_funcionalidade(request, 'workspace.editar_todos'):
        return JsonResponse({'erro': 'sem permissao'}, status=403)
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return JsonResponse({'erro': 'sem tenant'}, status=400)
    from apps.automacao.models import Checklist, ItemChecklist
    from apps.comercial.leads.models import CampoCustomizado

    checklist = Checklist.all_tenants.filter(tenant=tenant, pk=pk).first()
    if checklist is None:
        return JsonResponse({'erro': 'checklist nao encontrado'}, status=404)

    try:
        data = json.loads(request.body or '{}')
    except (ValueError, TypeError):
        return JsonResponse({'erro': 'payload invalido'}, status=400)

    chave = (data.get('chave') or '').strip()
    pergunta = (data.get('pergunta') or '').strip()
    if not chave:
        return JsonResponse({'erro': 'chave obrigatoria'}, status=400)
    if not pergunta:
        return JsonResponse({'erro': 'pergunta obrigatoria'}, status=400)

    item_id = data.get('id')
    criando = not item_id
    if not criando:
        item = ItemChecklist.all_tenants.filter(tenant=tenant, checklist=checklist, pk=item_id).first()
        if item is None:
            return JsonResponse({'erro': 'item nao encontrado'}, status=404)
    else:
        item = ItemChecklist(tenant=tenant, checklist=checklist)
        ultimo = checklist.itens.order_by('-ordem').first()
        item.ordem = (ultimo.ordem + 1) if ultimo else 0

    tipos_resp_validos = {k for k, _ in ItemChecklist.TIPO_RESPOSTA_CHOICES}
    tipos_val_validos = {k for k, _ in ItemChecklist.TIPO_VALIDACAO_CHOICES}
    estrategias_validas = {k for k, _ in ItemChecklist.ESTRATEGIA_ERRO_CHOICES}
    ura_validos = {k for k, _ in ItemChecklist.URA_TITULO_CHOICES}

    tipo_resposta = data.get('tipo_resposta') or 'texto_livre'
    tipo_validacao = data.get('tipo_validacao') or 'nenhuma'
    estrategia_erro = data.get('estrategia_erro') or 'repetir'
    ura_titulo = data.get('ura_titulo') or ''

    campo = None
    campo_id = data.get('campo')
    if campo_id:
        campo = CampoCustomizado.all_tenants.filter(tenant=tenant, pk=campo_id).first()

    opcoes = data.get('opcoes')
    if not isinstance(opcoes, list):
        opcoes = []
    opcoes_norm = []
    for o in opcoes:
        if not isinstance(o, dict):
            continue
        texto = str(o.get('texto') or '').strip()
        if not texto:
            continue
        valor = str(o.get('valor') or '').strip() or texto
        opcoes_norm.append({'texto': texto, 'valor': valor})

    item.chave = chave
    item.pergunta = pergunta
    item.ajuda = (data.get('ajuda') or '').strip()
    item.tipo_resposta = tipo_resposta if tipo_resposta in tipos_resp_validos else 'texto_livre'
    item.opcoes = opcoes_norm
    item.ura_titulo = ura_titulo if ura_titulo in ura_validos else ''
    item.tipo_validacao = tipo_validacao if tipo_validacao in tipos_val_validos else 'nenhuma'
    item.regex_validacao = (data.get('regex_validacao') or '').strip()
    item.instrucoes_ia = (data.get('instrucoes_ia') or '').strip()
    item.obrigatorio = bool(data.get('obrigatorio'))
    try:
        item.max_tentativas = max(1, int(data.get('max_tentativas') or 3))
    except (TypeError, ValueError):
        item.max_tentativas = 3
    item.estrategia_erro = estrategia_erro if estrategia_erro in estrategias_validas else 'repetir'
    item.mensagem_erro = data.get('mensagem_erro') or ''
    item.mensagem_sucesso = data.get('mensagem_sucesso') or ''
    item.mensagem_recontato = data.get('mensagem_recontato') or ''
    item.campo = campo

    try:
        item.full_clean()
    except ValidationError as exc:
        return JsonResponse({'erro': _mensagens_validation_error(exc)}, status=400)

    item.save()
    try:
        registrar_acao('config', 'criar' if criando else 'editar', 'checklist_item', item.pk,
                        f"Item '{item.chave}' do checklist '{checklist.nome}' {'criado' if criando else 'atualizado'}",
                        request=request)
    except Exception:
        pass
    return JsonResponse({'ok': True, 'id': item.pk})


@require_POST
@login_required
def item_excluir(request, pk):
    """Remove um item do checklist (e as respostas ja registradas, via CASCADE)."""
    if not user_tem_funcionalidade(request, 'workspace.editar_todos'):
        return JsonResponse({'erro': 'sem permissao'}, status=403)
    tenant = getattr(request, 'tenant', None)
    from apps.automacao.models import ItemChecklist
    item = ItemChecklist.all_tenants.filter(tenant=tenant, pk=pk).select_related('checklist').first()
    if item is None:
        return JsonResponse({'erro': 'item nao encontrado'}, status=404)
    chave = item.chave
    checklist_nome = item.checklist.nome
    item.delete()
    try:
        registrar_acao('config', 'excluir', 'checklist_item', pk,
                        f"Item '{chave}' do checklist '{checklist_nome}' excluido", request=request)
    except Exception:
        pass
    return JsonResponse({'ok': True})


@require_POST
@login_required
def itens_ordenar(request, pk):
    """Recebe a lista de ids na nova ordem (drag and drop) e atualiza `ordem`."""
    if not user_tem_funcionalidade(request, 'workspace.editar_todos'):
        return JsonResponse({'erro': 'sem permissao'}, status=403)
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return JsonResponse({'erro': 'sem tenant'}, status=400)
    from apps.automacao.models import Checklist, ItemChecklist

    checklist = Checklist.all_tenants.filter(tenant=tenant, pk=pk).first()
    if checklist is None:
        return JsonResponse({'erro': 'checklist nao encontrado'}, status=404)

    try:
        data = json.loads(request.body or '{}')
    except (ValueError, TypeError):
        return JsonResponse({'erro': 'payload invalido'}, status=400)

    ids = data.get('ids')
    if not isinstance(ids, list):
        return JsonResponse({'erro': 'ids invalido'}, status=400)

    ids_int = []
    for item_id in ids:
        try:
            ids_int.append(int(item_id))
        except (TypeError, ValueError):
            continue

    itens_por_id = {
        item.pk: item
        for item in ItemChecklist.all_tenants.filter(tenant=tenant, checklist=checklist, pk__in=ids_int)
    }
    atualizados = []
    for ordem, item_id in enumerate(ids_int):
        item = itens_por_id.get(item_id)
        if item is None or item.ordem == ordem:
            continue
        item.ordem = ordem
        atualizados.append(item)
    if atualizados:
        ItemChecklist.all_tenants.bulk_update(atualizados, ['ordem'])
    return JsonResponse({'ok': True})
