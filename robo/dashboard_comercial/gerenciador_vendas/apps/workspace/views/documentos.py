"""Views de Documento e PastaDocumento — CRUD completo + render markdown."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.sistema.decorators import user_tem_funcionalidade
from apps.sistema.utils import registrar_acao
from apps.workspace.forms import DocumentoForm, PastaForm
from apps.workspace.markdown_utils import render_markdown
from apps.workspace.models import AnexoDocumento, Documento, PastaDocumento


def _pode_editar(request, doc):
    """Pode editar se: tem 'editar_todos' OU é criador e tem 'editar_proprios'."""
    if request.user.is_superuser:
        return True
    if user_tem_funcionalidade(request, 'workspace.editar_todos'):
        return True
    if doc.criado_por_id == request.user.id and user_tem_funcionalidade(request, 'workspace.editar_proprios'):
        return True
    return False


# ============================================================================
# DOCUMENTOS
# ============================================================================

def _drive_render(request, pasta_atual=None):
    """Render compartilhado entre raiz e pasta especifica."""
    busca = request.GET.get('q', '').strip()
    categoria = request.GET.get('categoria', '').strip()

    # Filtros de pasta — raiz vs dentro de pasta
    if pasta_atual:
        subpastas_qs = pasta_atual.subpastas.order_by('ordem', 'nome')
        docs_qs = pasta_atual.documentos.select_related('criado_por')
    else:
        subpastas_qs = PastaDocumento.objects.filter(pai__isnull=True).order_by('ordem', 'nome')
        docs_qs = Documento.objects.filter(pasta__isnull=True).select_related('criado_por')

    # Busca cross-pasta: se tem termo, ignora a pasta atual e busca tudo
    if busca:
        docs_qs = Documento.objects.select_related('pasta', 'criado_por').filter(
            Q(titulo__icontains=busca) | Q(conteudo__icontains=busca) | Q(resumo__icontains=busca)
        )
        subpastas_qs = PastaDocumento.objects.filter(nome__icontains=busca).order_by('nome')

    if categoria:
        docs_qs = docs_qs.filter(categoria=categoria)

    docs_qs = docs_qs.order_by('-atualizado_em')[:200]

    # Breadcrumb (do raiz até a pasta atual)
    crumbs = []
    p = pasta_atual
    while p is not None:
        crumbs.insert(0, p)
        p = p.pai

    ctx = {
        'pasta_atual': pasta_atual,
        'subpastas': subpastas_qs,
        'docs': docs_qs,
        'categorias': Documento._meta.get_field('categoria').choices,
        'filtro_categoria': categoria,
        'busca': busca,
        'crumbs': crumbs,
        'pagetitle': pasta_atual.nome if pasta_atual else 'Documentos',
    }
    return render(request, 'workspace/documentos/drive.html', ctx)


@login_required
def drive(request):
    """Vista raiz do Drive — pastas raiz + documentos sem pasta."""
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden()
    return _drive_render(request, pasta_atual=None)


@login_required
def drive_pasta(request, slug):
    """Vista de pasta especifica."""
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden()
    pasta = get_object_or_404(PastaDocumento, slug=slug)
    return _drive_render(request, pasta_atual=pasta)


@login_required
def detalhe(request, pk):
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden()
    doc = get_object_or_404(Documento, pk=pk)

    # Outros docs da mesma pasta (rail lateral)
    if doc.pasta_id:
        outros = Documento.objects.filter(pasta=doc.pasta).exclude(pk=doc.pk).order_by('-atualizado_em')[:8]
    else:
        outros = Documento.objects.filter(pasta__isnull=True).exclude(pk=doc.pk).order_by('-atualizado_em')[:8]

    # Breadcrumb completo da pasta (raiz -> doc.pasta)
    crumbs = []
    p = doc.pasta
    while p is not None:
        crumbs.insert(0, p)
        p = p.pai

    # Renderiza conforme o formato declarado
    from apps.workspace.markdown_utils import render_html_sanitizado
    conteudo = doc.conteudo or ''
    if doc.formato == 'html':
        conteudo_html = render_html_sanitizado(conteudo)
    elif doc.formato in ('imagem', 'pdf', 'link'):
        # Sem renderizar conteudo como HTML — o template trata por formato
        conteudo_html = render_markdown(conteudo) if conteudo else ''
    else:
        conteudo_html = render_markdown(conteudo)

    ctx = {
        'doc': doc,
        'conteudo_html': conteudo_html,
        'pode_editar': _pode_editar(request, doc),
        'outros_docs': outros,
        'crumbs': crumbs,
        'pagetitle': doc.titulo,
    }
    return render(request, 'workspace/documentos/detalhe.html', ctx)


@login_required
def criar(request):
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden()
    if not user_tem_funcionalidade(request, 'workspace.editar_proprios'):
        return HttpResponseForbidden('Você não pode criar documentos.')

    tenant = getattr(request, 'tenant', None)
    pasta_id = request.GET.get('pasta')
    pasta_pre = None
    if pasta_id and str(pasta_id).isdigit():
        pasta_pre = PastaDocumento.objects.filter(pk=int(pasta_id)).first()

    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES, tenant=tenant)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.tenant = tenant
            doc.criado_por = request.user
            doc.save()
            registrar_acao('workspace', 'criar', 'documento', doc.id,
                f'Documento "{doc.titulo}" criado', request=request)
            messages.success(request, 'Documento criado.')
            return redirect('workspace:documento_detalhe', pk=doc.pk)
    else:
        initial = {'pasta': pasta_pre} if pasta_pre else {}
        form = DocumentoForm(tenant=tenant, initial=initial)

    return render(request, 'workspace/documentos/editar.html', {
        'form': form, 'doc': None, 'pagetitle': 'Novo documento',
    })


@login_required
def editar(request, pk):
    doc = get_object_or_404(Documento, pk=pk)
    if not _pode_editar(request, doc):
        return HttpResponseForbidden()
    tenant = getattr(request, 'tenant', None)
    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES, instance=doc, tenant=tenant)
        if form.is_valid():
            form.save()
            registrar_acao('workspace', 'editar', 'documento', doc.id,
                f'Documento "{doc.titulo}" atualizado', request=request)
            messages.success(request, 'Documento atualizado.')
            return redirect('workspace:documento_detalhe', pk=doc.pk)
    else:
        form = DocumentoForm(instance=doc, tenant=tenant)

    return render(request, 'workspace/documentos/editar.html', {
        'form': form, 'doc': doc, 'pagetitle': f'Editar: {doc.titulo}',
    })


@login_required
def excluir(request, pk):
    doc = get_object_or_404(Documento, pk=pk)
    if not _pode_editar(request, doc):
        return HttpResponseForbidden()
    if request.method == 'POST':
        titulo = doc.titulo
        doc.delete()
        registrar_acao('workspace', 'excluir', 'documento', pk,
            f'Documento "{titulo}" excluído', request=request)
        messages.success(request, f'Documento "{titulo}" excluído.')
        return redirect('workspace:documentos_lista')
    return render(request, 'workspace/documentos/excluir.html', {'doc': doc})


# ============================================================================
# PASTAS
# ============================================================================

@login_required
def pasta_criar(request):
    if not user_tem_funcionalidade(request, 'workspace.editar_proprios'):
        return HttpResponseForbidden()
    tenant = getattr(request, 'tenant', None)
    pai_id = request.GET.get('pai') or request.POST.get('pai')
    pai = None
    if pai_id and str(pai_id).isdigit():
        pai = PastaDocumento.objects.filter(pk=int(pai_id)).first()

    if request.method == 'POST':
        form = PastaForm(request.POST, tenant=tenant)
        if form.is_valid():
            pasta = form.save(commit=False)
            pasta.tenant = tenant
            pasta.save()
            registrar_acao('workspace', 'criar', 'pasta', pasta.id,
                f'Pasta "{pasta.nome}" criada', request=request)
            messages.success(request, 'Pasta criada.')
            if pasta.pai:
                return redirect('workspace:pasta_detalhe', slug=pasta.pai.slug)
            return redirect('workspace:documentos_lista')
    else:
        initial = {'pai': pai} if pai else {}
        form = PastaForm(tenant=tenant, initial=initial)
    return render(request, 'workspace/pastas/editar.html', {
        'form': form, 'pasta': None, 'pagetitle': 'Nova pasta',
    })


@login_required
def pasta_editar(request, pk):
    pasta = get_object_or_404(PastaDocumento, pk=pk)
    if not user_tem_funcionalidade(request, 'workspace.editar_proprios'):
        return HttpResponseForbidden()
    tenant = getattr(request, 'tenant', None)
    if request.method == 'POST':
        form = PastaForm(request.POST, instance=pasta, tenant=tenant)
        if form.is_valid():
            form.save()
            registrar_acao('workspace', 'editar', 'pasta', pasta.id,
                f'Pasta "{pasta.nome}" atualizada', request=request)
            messages.success(request, 'Pasta atualizada.')
            return redirect('workspace:pasta_detalhe', slug=pasta.slug)
    else:
        form = PastaForm(instance=pasta, tenant=tenant)
    return render(request, 'workspace/pastas/editar.html', {
        'form': form, 'pasta': pasta, 'pagetitle': f'Editar: {pasta.nome}',
    })


# ============================================================================
# ANEXOS — upload manual + geracao IA
# ============================================================================

@login_required
@require_POST
def anexo_upload(request, doc_pk):
    """Upload de imagem/arquivo pra um documento. Retorna JSON com URL e snippet markdown."""
    doc = get_object_or_404(Documento, pk=doc_pk)
    if not _pode_editar(request, doc):
        return JsonResponse({'ok': False, 'erro': 'Sem permissao'}, status=403)

    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'ok': False, 'erro': 'Sem arquivo no upload'}, status=400)

    mime = arquivo.content_type or ''
    eh_imagem = mime.startswith('image/')
    tipo = 'imagem' if eh_imagem else 'arquivo'

    anexo = AnexoDocumento(
        documento=doc, tenant=doc.tenant,
        nome_original=arquivo.name[:255], tipo=tipo,
        mime_type=mime[:100], tamanho_bytes=arquivo.size,
        criado_por=request.user,
    )
    anexo.arquivo.save(arquivo.name, arquivo, save=True)

    registrar_acao('workspace', 'criar', 'anexo', anexo.id,
        f'Anexo {arquivo.name} adicionado em "{doc.titulo}"', request=request)

    url = anexo.arquivo.url
    snippet = f'![{anexo.nome_original}]({url})' if eh_imagem else f'[{anexo.nome_original}]({url})'
    return JsonResponse({
        'ok': True,
        'anexo': {
            'id': anexo.id, 'url': url, 'nome': anexo.nome_original,
            'tipo': tipo, 'tamanho_bytes': anexo.tamanho_bytes,
        },
        'markdown_snippet': snippet,
    })


@login_required
@require_POST
def anexo_gerar_ia(request, doc_pk):
    """Gera imagem por IA (Gemini) e cria anexo. POST com `prompt`."""
    doc = get_object_or_404(Documento, pk=doc_pk)
    if not _pode_editar(request, doc):
        return JsonResponse({'ok': False, 'erro': 'Sem permissao'}, status=403)

    prompt = (request.POST.get('prompt') or '').strip()
    if not prompt or len(prompt) < 10:
        return JsonResponse({'ok': False, 'erro': 'Prompt muito curto (min 10 chars)'}, status=400)

    try:
        from apps.workspace.services.imagem_ia_service import gerar_e_anexar
        anexo = gerar_e_anexar(doc, prompt, criado_por=request.user)
    except Exception as e:
        return JsonResponse({'ok': False, 'erro': str(e)}, status=500)

    registrar_acao('workspace', 'gerar_ia', 'anexo', anexo.id,
        f'Imagem gerada por IA em "{doc.titulo}" (modelo: {anexo.modelo_ia})', request=request)

    url = anexo.arquivo.url
    return JsonResponse({
        'ok': True,
        'anexo': {
            'id': anexo.id, 'url': url, 'nome': anexo.nome_original,
            'tipo': 'imagem', 'tamanho_bytes': anexo.tamanho_bytes,
            'modelo': anexo.modelo_ia,
        },
        'markdown_snippet': f'![imagem gerada por IA]({url})',
    })


@login_required
@require_POST
def anexo_excluir(request, pk):
    anexo = get_object_or_404(AnexoDocumento, pk=pk)
    if not _pode_editar(request, anexo.documento):
        return JsonResponse({'ok': False, 'erro': 'Sem permissao'}, status=403)
    nome = anexo.nome_original
    anexo.arquivo.delete(save=False)
    anexo.delete()
    registrar_acao('workspace', 'excluir', 'anexo', pk,
        f'Anexo {nome} removido', request=request)
    return JsonResponse({'ok': True})


@login_required
def pasta_excluir(request, pk):
    pasta = get_object_or_404(PastaDocumento, pk=pk)
    if not user_tem_funcionalidade(request, 'workspace.editar_todos'):
        return HttpResponseForbidden('Excluir pasta exige permissão de editar todos.')
    if request.method == 'POST':
        nome = pasta.nome
        # Move docs filhos pra raiz antes de excluir
        pasta.documentos.update(pasta=None)
        pasta.delete()
        registrar_acao('workspace', 'excluir', 'pasta', pk,
            f'Pasta "{nome}" excluída (docs movidos pra raiz)', request=request)
        messages.success(request, f'Pasta "{nome}" excluída. Documentos movidos pra raiz.')
        return redirect('workspace:documentos_lista')
    return render(request, 'workspace/pastas/excluir.html', {'pasta': pasta})
