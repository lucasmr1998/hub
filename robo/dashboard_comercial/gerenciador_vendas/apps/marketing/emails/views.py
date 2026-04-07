import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST, require_http_methods

from apps.sistema.decorators import user_tem_funcionalidade

from .models import TemplateEmail, CategoriaTemplate
from .renderer import renderizar_email


def _check_perm(request, codigo):
    if not user_tem_funcionalidade(request, codigo):
        return JsonResponse({'error': 'Sem permissão para esta ação'}, status=403)
    return None


# ============================================================================
# VARIÁVEIS DISPONÍVEIS (para o editor)
# ============================================================================

VARIAVEIS_DISPONIVEIS = {
    'Lead': [
        {'var': '{{lead.nome}}', 'label': 'Nome do lead'},
        {'var': '{{lead.telefone}}', 'label': 'Telefone'},
        {'var': '{{lead.email}}', 'label': 'Email'},
        {'var': '{{lead.bairro}}', 'label': 'Bairro'},
        {'var': '{{lead.cidade}}', 'label': 'Cidade'},
        {'var': '{{lead.plano_interesse}}', 'label': 'Plano de interesse'},
    ],
    'Empresa': [
        {'var': '{{tenant.nome}}', 'label': 'Nome da empresa'},
        {'var': '{{tenant.telefone}}', 'label': 'Telefone da empresa'},
        {'var': '{{tenant.site}}', 'label': 'Site'},
        {'var': '{{tenant.logo_url}}', 'label': 'URL do logo'},
    ],
    'Comercial': [
        {'var': '{{vendedor.nome}}', 'label': 'Nome do vendedor'},
        {'var': '{{vendedor.telefone}}', 'label': 'Telefone do vendedor'},
        {'var': '{{vendedor.email}}', 'label': 'Email do vendedor'},
    ],
    'Contexto': [
        {'var': '{{data_atual}}', 'label': 'Data atual'},
        {'var': '{{link_descadastro}}', 'label': 'Link de descadastro'},
    ],
}


# ============================================================================
# LISTA DE TEMPLATES
# ============================================================================

@login_required
def lista_emails(request):
    """Lista todos os templates de email do tenant."""
    denied = _check_perm(request, 'marketing.ver_emails')
    if denied:
        return denied

    templates = TemplateEmail.objects.all().select_related('categoria', 'criado_por')
    categorias = CategoriaTemplate.objects.all()

    # Filtros
    status = request.GET.get('status', '')
    categoria_id = request.GET.get('categoria', '')
    if status:
        templates = templates.filter(status=status)
    if categoria_id:
        templates = templates.filter(categoria_id=categoria_id)

    # KPIs
    total = TemplateEmail.objects.count()
    ativos = TemplateEmail.objects.filter(status='ativo').count()
    rascunhos = TemplateEmail.objects.filter(status='rascunho').count()

    context = {
        'templates': templates,
        'categorias': categorias,
        'total': total,
        'ativos': ativos,
        'rascunhos': rascunhos,
        'filtro_status': status,
        'filtro_categoria': categoria_id,
    }
    return render(request, 'emails/lista.html', context)


# ============================================================================
# CRIAR TEMPLATE
# ============================================================================

@login_required
def criar_email(request):
    """Cria um novo template e redireciona para o editor."""
    denied = _check_perm(request, 'marketing.gerenciar_emails')
    if denied:
        return denied

    if request.method == 'POST':
        nome = request.POST.get('nome', 'Novo email').strip()
        categoria_id = request.POST.get('categoria', '')

        template = TemplateEmail(
            nome=nome or 'Novo email',
            criado_por=request.user,
            config_json={
                'largura': 600,
                'cor_fundo': '#f5f5f5',
                'cor_fundo_conteudo': '#ffffff',
                'fonte_padrao': 'Arial, Helvetica, sans-serif',
            },
            blocos_json=[],
        )
        if categoria_id:
            template.categoria_id = int(categoria_id)
        template.save()

        return redirect('marketing_emails:editor', pk=template.pk)

    categorias = CategoriaTemplate.objects.all()
    return render(request, 'emails/criar_modal.html', {'categorias': categorias})


# ============================================================================
# EDITOR VISUAL
# ============================================================================

@login_required
def editor_email(request, pk):
    """Editor visual drag-and-drop de blocos."""
    denied = _check_perm(request, 'marketing.gerenciar_emails')
    if denied:
        return denied

    template = get_object_or_404(TemplateEmail, pk=pk)

    context = {
        'template': template,
        'config_json': json.dumps(template.config_json or {}),
        'blocos_json': json.dumps(template.blocos_json or []),
        'variaveis': VARIAVEIS_DISPONIVEIS,
        'categorias': CategoriaTemplate.objects.all(),
    }
    return render(request, 'emails/editor.html', context)


# ============================================================================
# SALVAR TEMPLATE (API)
# ============================================================================

@login_required
@require_POST
def salvar_email(request, pk):
    """Salva o conteúdo do editor (blocos + config) via AJAX."""
    denied = _check_perm(request, 'marketing.gerenciar_emails')
    if denied:
        return denied

    template = get_object_or_404(TemplateEmail, pk=pk)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    # Atualizar campos
    if 'nome' in data:
        template.nome = data['nome']
    if 'assunto' in data:
        template.assunto = data['assunto']
    if 'descricao' in data:
        template.descricao = data['descricao']
    if 'config' in data:
        template.config_json = data['config']
    if 'blocos' in data:
        template.blocos_json = data['blocos']
    if 'status' in data and data['status'] in ('rascunho', 'ativo', 'arquivado'):
        template.status = data['status']
    if 'categoria_id' in data:
        template.categoria_id = data['categoria_id'] or None

    # Compilar HTML
    template.html_compilado = renderizar_email(template.config_json, template.blocos_json)
    template.save()

    return JsonResponse({
        'ok': True,
        'id': template.pk,
        'html_preview': template.html_compilado,
    })


# ============================================================================
# PREVIEW
# ============================================================================

@login_required
def preview_email(request, pk):
    """Retorna o HTML compilado do template para preview."""
    template = get_object_or_404(TemplateEmail, pk=pk)

    # Recompilar para garantir que está atualizado
    html = renderizar_email(template.config_json, template.blocos_json)

    return render(request, 'emails/preview.html', {
        'html_email': html,
        'template': template,
    })


# ============================================================================
# PREVIEW VIA POST (para preview ao vivo no editor)
# ============================================================================

@login_required
@require_POST
def preview_live(request):
    """Gera preview HTML a partir de JSON enviado pelo editor."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    config = data.get('config', {})
    blocos = data.get('blocos', [])
    html = renderizar_email(config, blocos)

    return JsonResponse({'html': html})


# ============================================================================
# DUPLICAR TEMPLATE
# ============================================================================

@login_required
@require_POST
def duplicar_email(request, pk):
    """Cria uma cópia do template."""
    denied = _check_perm(request, 'marketing.gerenciar_emails')
    if denied:
        return denied

    original = get_object_or_404(TemplateEmail, pk=pk)

    copia = TemplateEmail(
        nome=f'{original.nome} (cópia)',
        descricao=original.descricao,
        assunto=original.assunto,
        config_json=original.config_json,
        blocos_json=original.blocos_json,
        html_compilado=original.html_compilado,
        categoria=original.categoria,
        status='rascunho',
        criado_por=request.user,
    )
    copia.save()

    return JsonResponse({'ok': True, 'id': copia.pk})


# ============================================================================
# EXCLUIR TEMPLATE
# ============================================================================

@login_required
@require_POST
def excluir_email(request, pk):
    """Exclui um template."""
    denied = _check_perm(request, 'marketing.gerenciar_emails')
    if denied:
        return denied

    template = get_object_or_404(TemplateEmail, pk=pk)
    template.delete()

    return JsonResponse({'ok': True})


# ============================================================================
# API: LISTAR TEMPLATES (para selects em automações)
# ============================================================================

@login_required
@require_http_methods(['GET'])
def api_templates(request):
    """Retorna lista de templates ativos para uso em automações."""
    templates = TemplateEmail.objects.filter(status='ativo').values(
        'id', 'nome', 'assunto', 'categoria__nome'
    )
    return JsonResponse({'templates': list(templates)})
