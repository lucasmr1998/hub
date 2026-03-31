from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
import json
import logging

from apps.sistema.models import ConfiguracaoEmpresa

logger = logging.getLogger(__name__)


@login_required
def setup_inicial_view(request):
    """
    Tela de setup inicial para o primeiro login do tenant.
    Coleta: nome da empresa, logo, cores, credenciais HubSoft.
    """
    tenant = request.tenant
    if not tenant:
        return redirect('vendas_web:home')

    config = ConfiguracaoEmpresa.all_tenants.filter(tenant=tenant, ativo=True).first()

    if request.method == 'POST':
        nome = request.POST.get('nome_empresa', '').strip()
        cor_primaria = request.POST.get('cor_primaria', '#1F3D59')
        cor_secundaria = request.POST.get('cor_secundaria', '#2c5aa0')

        if not nome:
            return render(request, 'sistema/setup_inicial.html', {
                'erro': 'Nome da empresa é obrigatório.',
                'config': config,
            })

        if config:
            config.nome_empresa = nome
            config.cor_primaria = cor_primaria
            config.cor_secundaria = cor_secundaria
            if request.FILES.get('logo'):
                config.logo_empresa = request.FILES['logo']
            config.save()
        else:
            config = ConfiguracaoEmpresa(
                tenant=tenant,
                nome_empresa=nome,
                cor_primaria=cor_primaria,
                cor_secundaria=cor_secundaria,
                ativo=True,
            )
            if request.FILES.get('logo'):
                config.logo_empresa = request.FILES['logo']
            config.save()

        # Salvar credenciais HubSoft se fornecidas
        hubsoft_url = request.POST.get('hubsoft_url', '').strip()
        hubsoft_client_id = request.POST.get('hubsoft_client_id', '').strip()

        if hubsoft_url and hubsoft_client_id:
            from apps.integracoes.models import IntegracaoAPI
            IntegracaoAPI.objects.update_or_create(
                tenant=tenant,
                tipo='hubsoft',
                defaults={
                    'nome': f'HubSoft {tenant.nome}',
                    'base_url': hubsoft_url,
                    'client_id': hubsoft_client_id,
                    'client_secret': request.POST.get('hubsoft_client_secret', ''),
                    'username': request.POST.get('hubsoft_username', ''),
                    'password': request.POST.get('hubsoft_password', ''),
                    'grant_type': 'password',
                    'ativa': True,
                }
            )

        return redirect('vendas_web:dashboard1')

    return render(request, 'sistema/setup_inicial.html', {
        'config': config,
        'tenant': tenant,
    })


# ============================================================================
# VIEWS DE AUTENTICAÇÃO — migradas de vendas_web/views.py (Sub-phase 3G)
# ============================================================================

def home_view(request):
    """View para página inicial - redireciona baseado no status de autenticação"""
    if request.user.is_authenticated:
        return redirect('vendas_web:dashboard1')
    else:
        return redirect('vendas_web:login')


def login_view(request):
    """View para página de login"""
    if request.user.is_authenticated:
        return redirect('vendas_web:dashboard1')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Bem-vindo, {user.first_name or user.username}!')
                return redirect('vendas_web:dashboard1')
            else:
                messages.error(request, 'Usuário ou senha incorretos.')
        else:
            messages.error(request, 'Por favor, preencha todos os campos.')

    config = ConfiguracaoEmpresa.get_configuracao_ativa()
    return render(request, 'vendas_web/login.html', {'config_empresa': config})


def logout_view(request):
    """View personalizada para logout"""
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, 'Você foi desconectado com sucesso.')
    return redirect('vendas_web:home')


# ============================================================================
# VIEWS DE CONFIGURAÇÕES — migradas de vendas_web/views.py (Sub-phase 3G)
# ============================================================================

@login_required
def configuracoes_view(request):
    """View principal para configurações do sistema"""
    return render(request, 'vendas_web/configuracoes/index.html')


@login_required
def configuracoes_usuarios_view(request):
    """View para gerenciar usuários do sistema"""
    from django.contrib.auth.models import User, Group

    # Verificar se o usuário tem permissão para gerenciar usuários
    if not request.user.is_superuser and not request.user.groups.filter(name='adm_all').exists():
        messages.error(request, 'Você não tem permissão para acessar esta página.')
        return redirect('vendas_web:dashboard1')

    users = User.objects.all().order_by('-date_joined')
    groups = Group.objects.all().order_by('name')

    context = {
        'users': users,
        'groups': groups,
        'user': request.user
    }
    return render(request, 'vendas_web/configuracoes/usuarios.html', context)


@login_required
def configuracoes_recontato_view(request):
    """View para gerenciar configurações de recontato"""
    from vendas_web.models import ConfiguracaoRecontato
    configuracoes = ConfiguracaoRecontato.objects.all()
    return render(request, 'vendas_web/configuracoes/recontato.html', {
        'configuracoes': configuracoes
    })


# ============================================================================
# APIs DE GERENCIAMENTO DE USUÁRIOS — migradas de vendas_web/views.py
# ============================================================================

@login_required
@require_http_methods(["POST"])
def api_usuarios_criar(request):
    """API para criar novo usuário"""
    from django.contrib.auth.models import User, Group

    try:
        # Verificar permissões
        if not request.user.is_superuser and not request.user.groups.filter(name='adm_all').exists():
            return JsonResponse({'error': 'Sem permissão'}, status=403)

        data = json.loads(request.body)
        username = data.get('username')
        email = data.get('email')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        password = data.get('password')
        groups = data.get('groups', [])
        is_active = data.get('is_active', True)
        is_staff = data.get('is_staff', False)

        # Validações
        if not username or not email or not password:
            return JsonResponse({'error': 'Username, email e senha são obrigatórios'}, status=400)

        if User.objects.filter(username=username).exists():
            return JsonResponse({'error': 'Username já existe'}, status=400)

        if User.objects.filter(email=email).exists():
            return JsonResponse({'error': 'Email já existe'}, status=400)

        # Criar usuário
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=is_active,
            is_staff=is_staff
        )

        # Adicionar grupos
        for group_name in groups:
            try:
                group = Group.objects.get(name=group_name)
                user.groups.add(group)
            except Group.DoesNotExist:
                pass

        return JsonResponse({
            'success': True,
            'message': 'Usuário criado com sucesso',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'date_joined': user.date_joined.isoformat(),
                'groups': [g.name for g in user.groups.all()]
            }
        })

    except Exception as e:
        logger.error(f'Erro ao criar usuário: {str(e)}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@login_required
@require_http_methods(["PUT"])
def api_usuarios_editar(request, user_id):
    """API para editar usuário existente"""
    from django.contrib.auth.models import User, Group

    try:
        # Verificar permissões
        if not request.user.is_superuser and not request.user.groups.filter(name='adm_all').exists():
            return JsonResponse({'error': 'Sem permissão'}, status=403)

        user = User.objects.get(id=user_id)
        data = json.loads(request.body)

        # Atualizar campos
        if 'username' in data:
            if User.objects.filter(username=data['username']).exclude(id=user_id).exists():
                return JsonResponse({'error': 'Username já existe'}, status=400)
            user.username = data['username']

        if 'email' in data:
            if User.objects.filter(email=data['email']).exclude(id=user_id).exists():
                return JsonResponse({'error': 'Email já existe'}, status=400)
            user.email = data['email']

        if 'first_name' in data:
            user.first_name = data['first_name']

        if 'last_name' in data:
            user.last_name = data['last_name']

        if 'is_active' in data:
            user.is_active = data['is_active']

        if 'is_staff' in data:
            user.is_staff = data['is_staff']

        if 'password' in data and data['password']:
            user.set_password(data['password'])

        user.save()

        # Atualizar grupos
        if 'groups' in data:
            user.groups.clear()
            for group_name in data['groups']:
                try:
                    group = Group.objects.get(name=group_name)
                    user.groups.add(group)
                except Group.DoesNotExist:
                    pass

        return JsonResponse({
            'success': True,
            'message': 'Usuário atualizado com sucesso',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'date_joined': user.date_joined.isoformat(),
                'groups': [g.name for g in user.groups.all()]
            }
        })

    except User.DoesNotExist:
        return JsonResponse({'error': 'Usuário não encontrado'}, status=404)
    except Exception as e:
        logger.error(f'Erro ao editar usuário: {str(e)}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


@login_required
@require_http_methods(["DELETE"])
def api_usuarios_deletar(request, user_id):
    """API para deletar usuário"""
    from django.contrib.auth.models import User

    try:
        # Verificar permissões
        if not request.user.is_superuser and not request.user.groups.filter(name='adm_all').exists():
            return JsonResponse({'error': 'Sem permissão'}, status=403)

        user = User.objects.get(id=user_id)

        # Não permitir deletar o próprio usuário
        if user.id == request.user.id:
            return JsonResponse({'error': 'Não é possível deletar seu próprio usuário'}, status=400)

        # Não permitir deletar superusuários
        if user.is_superuser:
            return JsonResponse({'error': 'Não é possível deletar superusuários'}, status=400)

        username = user.username
        user.delete()

        return JsonResponse({
            'success': True,
            'message': f'Usuário {username} deletado com sucesso'
        })

    except User.DoesNotExist:
        return JsonResponse({'error': 'Usuário não encontrado'}, status=404)
    except Exception as e:
        logger.error(f'Erro ao deletar usuário: {str(e)}')
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


# ============================================================================
# VIEWS DE PERFIL E TELEFONE — migradas de vendas_web/views.py
# ============================================================================

@login_required
@require_http_methods(["POST"])
def atualizar_telefone_view(request):
    """API para atualizar telefone do usuário via AJAX"""
    try:
        telefone = request.POST.get('telefone', '').strip()

        # Atualizar telefone diretamente no modelo User
        request.user.telefone = telefone if telefone else None
        request.user.save()

        return JsonResponse({
            'success': True,
            'message': 'Telefone atualizado com sucesso!',
            'telefone': telefone
        })

    except Exception as e:
        logger.error(f'Erro ao atualizar telefone: {str(e)}')
        return JsonResponse({
            'success': False,
            'message': 'Erro ao atualizar telefone. Tente novamente.'
        })


@login_required
def perfil_usuario_view(request):
    """View para exibir e editar perfil do usuário"""
    try:
        if request.method == 'POST':
            telefone = request.POST.get('telefone', '').strip()
            request.user.telefone = telefone if telefone else None
            request.user.save()
            messages.success(request, 'Telefone atualizado com sucesso!')
            return redirect('vendas_web:perfil_usuario')

        context = {
            'page_title': 'Meu Perfil',
            'user': request.user
        }

        return render(request, 'vendas_web/perfil_usuario.html', context)

    except Exception as e:
        logger.error(f'Erro na view de perfil: {str(e)}')
        messages.error(request, 'Erro ao carregar perfil. Tente novamente.')
        return redirect('vendas_web:dashboard1')
