"""Central de Notificações (v2) + Central de Ajuda.

Complementa as APIs legadas de notificação com a experiência completa do
painel: página central, filtros, marcar como lida (individual e em massa)
e contagem de não lidas pro sino da topbar.

LEITURA SEM SCHEMA CHANGE: o banco é compartilhado com o v1, então o estado
"lida" vive em `Notificacao.dados_contexto['lida_em']` (ISO datetime).
NULL/ausente = não lida. O v1 ignora a chave — zero impacto.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET

logger = logging.getLogger(__name__)


def _qs_usuario(request):
    from .models import Notificacao
    return Notificacao.objects.filter(destinatario=request.user)


def _eh_lida(notif) -> bool:
    ctx = notif.dados_contexto or {}
    return isinstance(ctx, dict) and bool(ctx.get('lida_em'))


def _marcar(notif):
    """Seta lida_em no JSON sem sobrescrever o resto do contexto."""
    ctx = notif.dados_contexto if isinstance(notif.dados_contexto, dict) else {}
    if ctx.get('lida_em'):
        return False
    ctx['lida_em'] = timezone.now().isoformat()
    notif.dados_contexto = ctx
    notif.save(update_fields=['dados_contexto'])
    return True


def _serialize(notif):
    return {
        'id': notif.id,
        'tipo': notif.tipo.nome if notif.tipo_id else '',
        'tipo_codigo': notif.tipo.codigo if notif.tipo_id else '',
        'canal': notif.canal.nome if notif.canal_id else '',
        'titulo': notif.titulo,
        'mensagem': notif.mensagem,
        'status': notif.status,
        'prioridade': notif.prioridade,
        'lida': _eh_lida(notif),
        'lida_em': (notif.dados_contexto or {}).get('lida_em'),
        'data_criacao': notif.data_criacao.isoformat(),
    }


# ════════════════════════════════════════════════════════════════════
#  PÁGINA — Central de Notificações
# ════════════════════════════════════════════════════════════════════
@login_required
def central_notificacoes(request):
    return render(request, 'vendas_web/notificacoes_central.html', {
        'page_title': 'Notificações',
    })


# ════════════════════════════════════════════════════════════════════
#  APIs v2
# ════════════════════════════════════════════════════════════════════
@login_required
@require_GET
def api_notif_listar_v2(request):
    """Lista com filtros: ?filtro=todas|nao_lidas|lidas &prioridade= &q= &page="""
    try:
        qs = (_qs_usuario(request)
              .select_related('tipo', 'canal')
              .order_by('-data_criacao'))

        filtro = request.GET.get('filtro', 'todas')
        if filtro == 'nao_lidas':
            qs = qs.filter(Q(dados_contexto__lida_em__isnull=True))
        elif filtro == 'lidas':
            qs = qs.filter(dados_contexto__lida_em__isnull=False)

        prioridade = request.GET.get('prioridade', '')
        if prioridade:
            qs = qs.filter(prioridade=prioridade)

        q = (request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(titulo__icontains=q) | Q(mensagem__icontains=q))

        page = max(1, int(request.GET.get('page', 1)))
        per_page = min(50, int(request.GET.get('per_page', 15)))
        total = qs.count()
        itens = [_serialize(n) for n in qs[(page - 1) * per_page: page * per_page]]

        base = _qs_usuario(request)
        nao_lidas = base.filter(dados_contexto__lida_em__isnull=True).count()

        return JsonResponse({
            'success': True,
            'notificacoes': itens,
            'total': total,
            'nao_lidas': nao_lidas,
            'page': page,
            'tem_mais': page * per_page < total,
        })
    except Exception as e:
        logger.exception('api_notif_listar_v2')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def api_notif_marcar_lida(request, notificacao_id):
    try:
        notif = _qs_usuario(request).get(id=notificacao_id)
    except Exception:
        return JsonResponse({'success': False, 'error': 'Notificação não encontrada'}, status=404)
    _marcar(notif)
    nao_lidas = _qs_usuario(request).filter(dados_contexto__lida_em__isnull=True).count()
    return JsonResponse({'success': True, 'nao_lidas': nao_lidas})


@login_required
@require_POST
def api_notif_marcar_todas(request):
    n = 0
    for notif in _qs_usuario(request).filter(dados_contexto__lida_em__isnull=True):
        if _marcar(notif):
            n += 1
    return JsonResponse({'success': True, 'marcadas': n, 'nao_lidas': 0})


# ════════════════════════════════════════════════════════════════════
#  CENTRAL DE AJUDA — guias por perfil
# ════════════════════════════════════════════════════════════════════
GUIAS = {
    'administrador': {'titulo': 'Guia do Administrador', 'icone': 'fa-user-shield',
                      'desc': 'Acesso total: perfis de acesso, mensagens de WhatsApp, configurações e governança do sistema.'},
    'gerente':       {'titulo': 'Guia do Gerente',       'icone': 'fa-chart-pie',
                      'desc': 'Visão completa da operação: pipelines, equipe, metas, desempenho e retenção.'},
    'operador':      {'titulo': 'Guia do Operador',      'icone': 'fa-headset',
                      'desc': 'Indicações e atendimento manual: cadastrar, completar dados, converter e agendar.'},
    'vendedor':      {'titulo': 'Guia do Vendedor',      'icone': 'fa-briefcase',
                      'desc': 'Pipeline de Aquisição, oportunidades, tarefas e o dia a dia comercial.'},
    'auditor':       {'titulo': 'Guia do Auditor',       'icone': 'fa-magnifying-glass',
                      'desc': 'Consulta e conferência: veja tudo, altere nada — para revisão e compliance.'},
    'robo':          {'titulo': 'Como o Robô Atende no WhatsApp', 'icone': 'fa-robot',
                      'desc': 'Referência para todos os perfis: os fluxos automáticos do robô no WhatsApp e o que acontece por trás.'},
}


def _perfil_sugerido(user):
    """Sugere o guia conforme o(s) perfil(is) de acesso (RBAC) do usuário logado."""
    if user.is_superuser:
        return 'administrador'
    slugs = set(user.perfis_acesso.filter(ativo=True).values_list('slug', flat=True))
    for slug in ('administrador', 'gerente', 'operador', 'vendedor', 'auditor'):
        if slug in slugs:
            return slug
    # Fallback p/ usuários ainda não migrados p/ o novo RBAC (perfil legado).
    cargo = getattr(getattr(user, 'perfil_crm', None), 'cargo', '')
    if cargo in ('gerente', 'diretor', 'supervisor'):
        return 'gerente'
    if cargo == 'vendedor':
        return 'vendedor'
    return 'vendedor'


@login_required
def ajuda_home(request):
    return render(request, 'vendas_web/ajuda/index.html', {
        'page_title': 'Central de Ajuda',
        'guias': GUIAS,
        'sugerido': _perfil_sugerido(request.user),
    })


@login_required
def ajuda_guia(request, perfil):
    if perfil not in GUIAS:
        perfil = _perfil_sugerido(request.user)
    return render(request, f'vendas_web/ajuda/guia_{perfil}.html', {
        'page_title': GUIAS[perfil]['titulo'],
        'guias': GUIAS,
        'perfil_atual': perfil,
    })
