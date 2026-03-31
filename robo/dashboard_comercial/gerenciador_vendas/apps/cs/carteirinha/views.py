from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from apps.sistema.validators import validate_image_upload
from apps.cs.carteirinha.models import ModeloCarteirinha, RegraAtribuicao, CarteirinhaMembro
from apps.cs.carteirinha.services import CarteirinhaService
from apps.cs.clube.models import MembroClube, NivelClube


# ── Dashboard Admin ──────────────────────────────────────────────────

@login_required(login_url='/roleta/dashboard/login/')
def dashboard_carteirinha(request):
    """Dashboard principal do modulo carteirinha."""
    modelos = ModeloCarteirinha.objects.all()
    regras = RegraAtribuicao.objects.select_related('modelo', 'nivel').all()
    total_emitidas = CarteirinhaMembro.objects.filter(ativo=True).count()

    return render(request, 'carteirinha/dashboard/home.html', {
        'modelos': modelos,
        'regras': regras,
        'total_emitidas': total_emitidas,
    })


@login_required(login_url='/roleta/dashboard/login/')
@transaction.atomic
def dashboard_modelos(request):
    """CRUD de modelos de carteirinha."""
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'criar':
            try:
                if request.FILES.get('imagem_fundo'):
                    validate_image_upload(request.FILES['imagem_fundo'])
                if request.FILES.get('logo'):
                    validate_image_upload(request.FILES['logo'])
            except ValidationError as e:
                messages.error(request, e.message)
                return redirect('dashboard_modelos_carteirinha')

            modelo = ModeloCarteirinha.objects.create(
                nome=request.POST.get('nome', '').strip(),
                descricao=request.POST.get('descricao', '').strip(),
                tipo_fundo=request.POST.get('tipo_fundo', 'cor'),
                cor_fundo_primaria=request.POST.get('cor_fundo_primaria', '#000b4a'),
                cor_fundo_secundaria=request.POST.get('cor_fundo_secundaria', '#1a2d4a'),
                cor_texto=request.POST.get('cor_texto', '#ffffff'),
                cor_texto_secundario=request.POST.get('cor_texto_secundario', '#94a3b8'),
                cor_destaque=request.POST.get('cor_destaque', '#fbbf24'),
                texto_marca=request.POST.get('texto_marca', 'Clube Megalink').strip(),
                mostrar_nome=request.POST.get('mostrar_nome') == 'on',
                mostrar_cpf=request.POST.get('mostrar_cpf') == 'on',
                mostrar_nivel=request.POST.get('mostrar_nivel') == 'on',
                mostrar_data_emissao=request.POST.get('mostrar_data_emissao') == 'on',
                mostrar_data_validade=request.POST.get('mostrar_data_validade') == 'on',
                mostrar_qr_code=request.POST.get('mostrar_qr_code') == 'on',
                mostrar_foto=request.POST.get('mostrar_foto') == 'on',
                mostrar_pontos=request.POST.get('mostrar_pontos') == 'on',
                mostrar_cidade=request.POST.get('mostrar_cidade') == 'on',
                texto_rodape=request.POST.get('texto_rodape', 'um clube filiado').strip(),
                ativo=request.POST.get('ativo') == 'on',
            )
            if request.FILES.get('imagem_fundo'):
                modelo.imagem_fundo = request.FILES['imagem_fundo']
            if request.FILES.get('logo'):
                modelo.logo = request.FILES['logo']
            if request.FILES.get('imagem_fundo') or request.FILES.get('logo'):
                modelo.save()
            messages.success(request, f'Modelo "{modelo.nome}" criado.')

        elif action == 'excluir':
            modelo_id = request.POST.get('modelo_id')
            modelo = get_object_or_404(ModeloCarteirinha, id=modelo_id)
            nome = modelo.nome
            modelo.delete()
            messages.success(request, f'Modelo "{nome}" excluído.')

        return redirect('dashboard_modelos_carteirinha')

    modelos = ModeloCarteirinha.objects.all()
    return render(request, 'carteirinha/dashboard/modelos.html', {
        'modelos': modelos,
    })


@login_required(login_url='/roleta/dashboard/login/')
def dashboard_modelo_criar(request):
    """Pagina dedicada para criar modelo com preview em tempo real."""
    if request.method == 'POST':
        try:
            if request.FILES.get('imagem_fundo'):
                validate_image_upload(request.FILES['imagem_fundo'])
            if request.FILES.get('logo'):
                validate_image_upload(request.FILES['logo'])
        except ValidationError as e:
            messages.error(request, e.message)
            return render(request, 'carteirinha/dashboard/modelo_criar.html')

        modelo = ModeloCarteirinha.objects.create(
            nome=request.POST.get('nome', '').strip(),
            descricao=request.POST.get('descricao', '').strip(),
            tipo_fundo=request.POST.get('tipo_fundo', 'cor'),
            cor_fundo_primaria=request.POST.get('cor_fundo_primaria', '#000b4a'),
            cor_fundo_secundaria=request.POST.get('cor_fundo_secundaria', '#1a2d4a'),
            cor_texto=request.POST.get('cor_texto', '#ffffff'),
            cor_texto_secundario=request.POST.get('cor_texto_secundario', '#94a3b8'),
            cor_destaque=request.POST.get('cor_destaque', '#fbbf24'),
            texto_marca=request.POST.get('texto_marca', 'Clube Megalink').strip(),
            mostrar_nome=request.POST.get('mostrar_nome') == 'on',
            mostrar_cpf=request.POST.get('mostrar_cpf') == 'on',
            mostrar_nivel=request.POST.get('mostrar_nivel') == 'on',
            mostrar_data_emissao=request.POST.get('mostrar_data_emissao') == 'on',
            mostrar_data_validade=request.POST.get('mostrar_data_validade') == 'on',
            mostrar_qr_code=request.POST.get('mostrar_qr_code') == 'on',
            mostrar_foto=request.POST.get('mostrar_foto') == 'on',
            mostrar_pontos=request.POST.get('mostrar_pontos') == 'on',
            mostrar_cidade=request.POST.get('mostrar_cidade') == 'on',
            texto_rodape=request.POST.get('texto_rodape', 'um clube filiado').strip(),
            ativo=request.POST.get('ativo') == 'on',
        )
        if request.FILES.get('imagem_fundo'):
            modelo.imagem_fundo = request.FILES['imagem_fundo']
        if request.FILES.get('logo'):
            modelo.logo = request.FILES['logo']
        if request.FILES.get('imagem_fundo') or request.FILES.get('logo'):
            modelo.save()
        messages.success(request, f'Modelo "{modelo.nome}" criado com sucesso!')
        return redirect('dashboard_modelos_carteirinha')

    return render(request, 'carteirinha/dashboard/modelo_criar.html')


@login_required(login_url='/roleta/dashboard/login/')
@transaction.atomic
def dashboard_modelo_editar(request, modelo_id):
    """Pagina de edicao de modelo com preview em tempo real."""
    modelo = get_object_or_404(ModeloCarteirinha, id=modelo_id)

    if request.method == 'POST':
        try:
            if request.FILES.get('imagem_fundo'):
                validate_image_upload(request.FILES['imagem_fundo'])
            if request.FILES.get('logo'):
                validate_image_upload(request.FILES['logo'])
        except ValidationError as e:
            messages.error(request, e.message)
            return render(request, 'carteirinha/dashboard/modelo_editar.html', {
                'modelo': modelo,
            })

        modelo.nome = request.POST.get('nome', '').strip()
        modelo.descricao = request.POST.get('descricao', '').strip()
        modelo.tipo_fundo = request.POST.get('tipo_fundo', 'cor')
        modelo.cor_fundo_primaria = request.POST.get('cor_fundo_primaria', '#000b4a')
        modelo.cor_fundo_secundaria = request.POST.get('cor_fundo_secundaria', '#1a2d4a')
        modelo.cor_texto = request.POST.get('cor_texto', '#ffffff')
        modelo.cor_texto_secundario = request.POST.get('cor_texto_secundario', '#94a3b8')
        modelo.cor_destaque = request.POST.get('cor_destaque', '#fbbf24')
        modelo.texto_marca = request.POST.get('texto_marca', 'Clube Megalink').strip()
        modelo.mostrar_nome = request.POST.get('mostrar_nome') == 'on'
        modelo.mostrar_cpf = request.POST.get('mostrar_cpf') == 'on'
        modelo.mostrar_nivel = request.POST.get('mostrar_nivel') == 'on'
        modelo.mostrar_data_emissao = request.POST.get('mostrar_data_emissao') == 'on'
        modelo.mostrar_data_validade = request.POST.get('mostrar_data_validade') == 'on'
        modelo.mostrar_qr_code = request.POST.get('mostrar_qr_code') == 'on'
        modelo.mostrar_foto = request.POST.get('mostrar_foto') == 'on'
        modelo.mostrar_pontos = request.POST.get('mostrar_pontos') == 'on'
        modelo.mostrar_cidade = request.POST.get('mostrar_cidade') == 'on'
        modelo.texto_rodape = request.POST.get('texto_rodape', '').strip()
        modelo.ativo = request.POST.get('ativo') == 'on'
        if request.FILES.get('imagem_fundo'):
            modelo.imagem_fundo = request.FILES['imagem_fundo']
        if request.FILES.get('logo'):
            modelo.logo = request.FILES['logo']
        modelo.save()
        messages.success(request, f'Modelo "{modelo.nome}" atualizado!')
        return redirect('dashboard_modelos_carteirinha')

    return render(request, 'carteirinha/dashboard/modelo_editar.html', {
        'modelo': modelo,
    })


@login_required(login_url='/roleta/dashboard/login/')
def dashboard_regras(request):
    """CRUD de regras de atribuicao."""
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'criar':
            modelo_id = request.POST.get('modelo_id')
            tipo = request.POST.get('tipo')
            nivel_id = request.POST.get('nivel_id')
            RegraAtribuicao.objects.create(
                modelo_id=modelo_id,
                tipo=tipo,
                nivel_id=nivel_id if nivel_id else None,
                pontuacao_minima=int(request.POST.get('pontuacao_minima', 0) or 0),
                cidade=request.POST.get('cidade', '').strip(),
                prioridade=int(request.POST.get('prioridade', 0) or 0),
                ativo=request.POST.get('ativo') == 'on',
            )
            messages.success(request, 'Regra criada.')

        elif action == 'excluir':
            regra_id = request.POST.get('regra_id')
            get_object_or_404(RegraAtribuicao, id=regra_id).delete()
            messages.success(request, 'Regra excluída.')

        return redirect('dashboard_regras_carteirinha')

    regras = RegraAtribuicao.objects.select_related('modelo', 'nivel').all()
    modelos = ModeloCarteirinha.objects.filter(ativo=True)
    niveis = NivelClube.objects.all()

    return render(request, 'carteirinha/dashboard/regras.html', {
        'regras': regras,
        'modelos': modelos,
        'niveis': niveis,
    })


@login_required(login_url='/roleta/dashboard/login/')
def dashboard_preview(request, modelo_id):
    """Preview de um modelo de carteirinha com dados fake."""
    modelo = get_object_or_404(ModeloCarteirinha, id=modelo_id)
    return render(request, 'carteirinha/dashboard/preview.html', {
        'modelo': modelo,
    })


# ── Area do Membro ───────────────────────────────────────────────────

def membro_carteirinha(request):
    """Pagina da carteirinha do membro."""
    membro_id = request.session.get('auth_membro_id')
    if not membro_id:
        return redirect('roleta_index')

    try:
        membro = MembroClube.objects.get(id=membro_id)
    except MembroClube.DoesNotExist:
        return redirect('roleta_index')

    carteirinha = CarteirinhaService.obter_carteirinha_membro(membro)

    if not carteirinha:
        return render(request, 'roleta/membro/carteirinha.html', {
            'membro': membro,
            'carteirinha': None,
            'modelo': None,
        })

    return render(request, 'roleta/membro/carteirinha.html', {
        'membro': membro,
        'carteirinha': carteirinha,
        'modelo': carteirinha.modelo,
    })
