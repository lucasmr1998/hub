"""
Views do app decks — editor de apresentacoes.

UI: lista de decks, editor (GridStack por slide), apresentar (fullscreen).
APIs JSON: CRUD de deck/slide/bloco, layout dos blocos, congelar snapshot,
dados de widget ao vivo (pro editor), picker de widgets.

Permissoes (registradas sob o modulo 'relatorios' no seed):
- decks.ver_decks         — ver decks (compartilhados + proprios)
- decks.criar_deck        — criar/editar deck, slides e blocos
- decks.compartilhar_deck — marcar como compartilhado (admin)
Superuser bypassa.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.sistema.decorators import user_tem_funcionalidade
from apps.relatorios.branding import paleta_tenant
from apps.relatorios.models import Dashboard, Widget

from . import modelos as modelos_slide
from .models import Deck, Slide, SlideBloco
from .services import dados_widget, tema_deck

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _perm(request, codigo: str) -> bool:
    if request.user.is_superuser:
        return True
    return user_tem_funcionalidade(request, codigo)


def _pode_editar_deck(request, deck: Deck) -> bool:
    if request.user.is_superuser:
        return True
    if deck.criado_por_id == request.user.id:
        return _perm(request, 'decks.criar_deck')
    return _perm(request, 'decks.compartilhar_deck')


def _decks_visiveis(request):
    return Deck.objects.filter(
        Q(compartilhado=True) | Q(criado_por=request.user)
    ).order_by('ordem', 'nome')


def _json(request):
    try:
        return json.loads(request.body or '{}')
    except (ValueError, TypeError):
        return {}


def _bloco_dict(b: SlideBloco):
    return {
        'id': b.id,
        'tipo': b.tipo,
        'widget_id': b.widget_id,
        'conteudo': b.conteudo or {},
        'layout': b.layout or {},
        'estilo': b.estilo or {},
        'dados_snapshot': b.dados_snapshot or {},
        'ordem': b.ordem,
    }


def _slide_dict(s: Slide):
    return {
        'id': s.id,
        'ordem': s.ordem,
        'titulo': s.titulo,
        'fundo': s.fundo or {},
        'blocos': [_bloco_dict(b) for b in s.blocos.all()],
    }


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------

@login_required
def lista_view(request):
    if not _perm(request, 'decks.ver_decks'):
        return HttpResponseForbidden('Sem permissao')
    decks = list(_decks_visiveis(request).select_related('criado_por'))
    return render(request, 'decks/lista.html', {
        'decks': decks,
        'pode_criar': _perm(request, 'decks.criar_deck'),
        'page_title': 'Apresentacoes',
    })


@login_required
@require_POST
def criar_view(request):
    if not _perm(request, 'decks.criar_deck'):
        return HttpResponseForbidden('Sem permissao')
    nome = (request.POST.get('nome') or 'Nova apresentacao').strip()[:120]
    deck = Deck(nome=nome, criado_por=request.user)
    deck.save()
    # ja cria o primeiro slide em branco
    Slide.objects.create(deck=deck, ordem=0)
    return redirect('decks:editar', pk=deck.pk)


@login_required
def editor_view(request, pk):
    deck = get_object_or_404(_decks_visiveis(request), pk=pk)
    if not _pode_editar_deck(request, deck):
        return HttpResponseForbidden('Sem permissao pra editar')
    slides = [_slide_dict(s) for s in deck.slides.prefetch_related('blocos')]
    tenant = getattr(request, 'tenant', None)
    return render(request, 'decks/editor.html', {
        'deck': deck,
        'slides_json': slides,
        'page_title': deck.nome,
        'chart_palette': json.dumps(paleta_tenant(tenant)),
        'tema_json': tema_deck(deck, tenant),
        'modelos_json': modelos_slide.listar(),
    })


@login_required
def apresentar_view(request, pk):
    deck = get_object_or_404(_decks_visiveis(request), pk=pk)
    slides = [_slide_dict(s) for s in deck.slides.prefetch_related('blocos')]
    tenant = getattr(request, 'tenant', None)
    return render(request, 'decks/apresentar.html', {
        'deck': deck,
        'slides_json': slides,
        'chart_palette': json.dumps(paleta_tenant(tenant)),
        'tema_json': tema_deck(deck, tenant),
    })


@login_required
@require_POST
def excluir_view(request, pk):
    deck = get_object_or_404(_decks_visiveis(request), pk=pk)
    if not _pode_editar_deck(request, deck):
        return HttpResponseForbidden('Sem permissao')
    deck.delete()
    return redirect('decks:lista')


# ----------------------------------------------------------------------------
# APIs
# ----------------------------------------------------------------------------

@login_required
@require_POST
def api_deck_salvar(request):
    """Cria/edita meta do deck (nome, descricao, tema, compartilhado)."""
    data = _json(request)
    deck_id = data.get('id')
    if deck_id:
        deck = get_object_or_404(_decks_visiveis(request), pk=deck_id)
        if not _pode_editar_deck(request, deck):
            return HttpResponseForbidden('Sem permissao')
    else:
        if not _perm(request, 'decks.criar_deck'):
            return HttpResponseForbidden('Sem permissao')
        deck = Deck(criado_por=request.user)
    if 'nome' in data:
        deck.nome = (data.get('nome') or 'Apresentacao').strip()[:120]
    if 'descricao' in data:
        deck.descricao = data.get('descricao') or ''
    if 'tema' in data and isinstance(data['tema'], dict):
        deck.tema = data['tema']
    if 'compartilhado' in data and _perm(request, 'decks.compartilhar_deck'):
        deck.compartilhado = bool(data['compartilhado'])
    deck.save()
    return JsonResponse({'ok': True, 'deck_id': deck.id})


@login_required
@require_POST
def api_slide_adicionar(request, pk):
    """Cria um slide, opcionalmente a partir de um modelo (body: {modelo}).
    Os blocos do modelo ja nascem posicionados; os slots de grafico nascem sem
    widget (o usuario clica e escolhe)."""
    deck = get_object_or_404(_decks_visiveis(request), pk=pk)
    if not _pode_editar_deck(request, deck):
        return HttpResponseForbidden('Sem permissao')
    modelo = (_json(request).get('modelo') or 'branco')
    slide = Slide.objects.create(deck=deck, ordem=deck.slides.count())
    for i, b in enumerate(modelos_slide.blocos_do_modelo(modelo)):
        SlideBloco.objects.create(
            slide=slide, ordem=i, tipo=b['tipo'],
            conteudo=b.get('conteudo') or {}, layout=b.get('layout') or {},
        )
    slide.refresh_from_db()
    return JsonResponse({'ok': True, 'slide': _slide_dict(slide)})


@login_required
@require_POST
def api_slides_reordenar(request, pk):
    deck = get_object_or_404(_decks_visiveis(request), pk=pk)
    if not _pode_editar_deck(request, deck):
        return HttpResponseForbidden('Sem permissao')
    ordem = _json(request).get('ordem') or []
    mapa = {s.id: s for s in deck.slides.all()}
    for i, sid in enumerate(ordem):
        s = mapa.get(int(sid))
        if s and s.ordem != i:
            s.ordem = i
            s.save(update_fields=['ordem', 'atualizado_em'])
    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_slide_excluir(request, pk):
    slide = get_object_or_404(Slide, pk=pk)
    deck = get_object_or_404(_decks_visiveis(request), pk=slide.deck_id)
    if not _pode_editar_deck(request, deck):
        return HttpResponseForbidden('Sem permissao')
    slide.delete()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_bloco_salvar(request, pk):
    """Cria/edita um bloco no slide <pk>. Body: {id?, tipo, widget_id?, conteudo?, estilo?, layout?}."""
    slide = get_object_or_404(Slide, pk=pk)
    deck = get_object_or_404(_decks_visiveis(request), pk=slide.deck_id)
    if not _pode_editar_deck(request, deck):
        return HttpResponseForbidden('Sem permissao')
    data = _json(request)
    bloco_id = data.get('id')
    if bloco_id:
        bloco = get_object_or_404(SlideBloco, pk=bloco_id, slide=slide)
    else:
        bloco = SlideBloco(slide=slide, ordem=slide.blocos.count())
    if 'tipo' in data:
        bloco.tipo = data['tipo']
    if 'widget_id' in data:
        wid = data['widget_id']
        # so aceita widget de dashboard visivel ao usuario (mesmo tenant)
        if wid:
            dashes = Dashboard.objects.filter(Q(compartilhado=True) | Q(criado_por=request.user))
            bloco.widget = Widget.objects.filter(pk=wid, dashboard__in=dashes).first()
        else:
            bloco.widget = None
    for campo in ('conteudo', 'estilo', 'layout'):
        if campo in data and isinstance(data[campo], dict):
            setattr(bloco, campo, data[campo])
    bloco.save()
    return JsonResponse({'ok': True, 'bloco': _bloco_dict(bloco)})


@login_required
@require_POST
def api_bloco_excluir(request, pk):
    bloco = get_object_or_404(SlideBloco, pk=pk)
    deck = get_object_or_404(_decks_visiveis(request), pk=bloco.slide.deck_id)
    if not _pode_editar_deck(request, deck):
        return HttpResponseForbidden('Sem permissao')
    bloco.delete()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_slide_layout(request, pk):
    """Posicao/tamanho dos blocos de um slide. Body: {layouts:[{id,x,y,w,h}]}.
    Copia direta do api_dashboard_layout de relatorios."""
    slide = get_object_or_404(Slide, pk=pk)
    deck = get_object_or_404(_decks_visiveis(request), pk=slide.deck_id)
    if not _pode_editar_deck(request, deck):
        return HttpResponseForbidden('Sem permissao')
    layouts = _json(request).get('layouts') or []
    mapa = {b.id: b for b in slide.blocos.all()}
    n = 0
    for item in layouts:
        b = mapa.get(int(item.get('id', 0)))
        if not b:
            continue
        b.layout = {
            'x': int(item.get('x', 0)), 'y': int(item.get('y', 0)),
            'w': int(item.get('w', 4)), 'h': int(item.get('h', 3)),
        }
        b.save(update_fields=['layout', 'atualizado_em'])
        n += 1
    return JsonResponse({'ok': True, 'total': n})


@login_required
@require_POST
def api_deck_congelar(request, pk):
    """Roda o builder pra cada bloco widget e grava o dados_snapshot."""
    deck = get_object_or_404(_decks_visiveis(request), pk=pk)
    if not _pode_editar_deck(request, deck):
        return HttpResponseForbidden('Sem permissao')
    n = 0
    for slide in deck.slides.prefetch_related('blocos__widget'):
        for bloco in slide.blocos.all():
            if bloco.tipo != 'widget' or not bloco.widget_id:
                continue
            overrides = {}
            conf = bloco.conteudo or {}
            if conf.get('dias'):
                overrides['dias'] = conf['dias']
            if conf.get('fonte'):
                overrides['fonte'] = conf['fonte']
            try:
                bloco.dados_snapshot = dados_widget(bloco.widget, request.tenant, overrides or None)
                bloco.save(update_fields=['dados_snapshot', 'atualizado_em'])
                n += 1
            except Exception as e:
                logger.warning('congelar bloco %s falhou: %s', bloco.id, e)
    deck.snapshot_em = timezone.now()
    deck.save(update_fields=['snapshot_em', 'atualizado_em'])
    return JsonResponse({'ok': True, 'blocos': n, 'snapshot_em': deck.snapshot_em.isoformat()})


@login_required
def api_bloco_widget_dados(request, pk):
    """Dados AO VIVO de um bloco widget (usado no editor)."""
    bloco = get_object_or_404(SlideBloco, pk=pk, tipo='widget')
    deck = get_object_or_404(_decks_visiveis(request), pk=bloco.slide.deck_id)
    if not bloco.widget_id:
        return JsonResponse({'ok': False, 'error': 'Bloco sem widget'}, status=400)
    overrides = {}
    conf = bloco.conteudo or {}
    if conf.get('dias'):
        overrides['dias'] = conf['dias']
    if conf.get('fonte'):
        overrides['fonte'] = conf['fonte']
    try:
        d = dados_widget(bloco.widget, request.tenant, overrides or None)
        return JsonResponse({'ok': True, **d})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
def api_widgets_disponiveis(request):
    """Lista dashboards visiveis -> widgets, pro picker do editor."""
    if not _perm(request, 'decks.criar_deck'):
        return HttpResponseForbidden('Sem permissao')
    dashes = Dashboard.objects.filter(
        Q(compartilhado=True) | Q(criado_por=request.user)
    ).order_by('nome').prefetch_related('widgets')
    out = []
    for d in dashes:
        widgets = [{'id': w.id, 'titulo': w.titulo, 'visualizacao': w.visualizacao}
                   for w in d.widgets.all()]
        if widgets:
            out.append({'dashboard_id': d.id, 'dashboard_nome': d.nome, 'widgets': widgets})
    return JsonResponse({'ok': True, 'dashboards': out})
