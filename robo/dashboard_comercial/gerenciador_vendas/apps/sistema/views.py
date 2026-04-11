from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db import connection
from django_ratelimit.decorators import ratelimit
import json
import logging

from apps.sistema.models import ConfiguracaoEmpresa
from apps.sistema.utils import auditar

logger = logging.getLogger(__name__)


def health_check(request):
    """Health check endpoint for monitoring."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False

    status = 200 if db_ok else 503
    return JsonResponse({
        'status': 'healthy' if db_ok else 'unhealthy',
        'database': 'ok' if db_ok else 'error',
    }, status=status)


@login_required
def setup_inicial_view(request):
    """
    Tela de setup inicial para o primeiro login do tenant.
    Coleta: nome da empresa, logo, cores, credenciais HubSoft.
    """
    tenant = request.tenant
    if not tenant:
        return redirect('sistema:home')

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

        return redirect('dashboard:dashboard1')

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
        return redirect('dashboard:dashboard1')
    else:
        return redirect('sistema:login')


@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def login_view(request):
    """View para página de login"""
    if request.user.is_authenticated:
        return redirect('dashboard:dashboard1')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password')

        if email and password:
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Bem-vindo, {user.first_name or user.username}!')
                return redirect('dashboard:dashboard1')
            else:
                messages.error(request, 'Email ou senha incorretos.')
        else:
            messages.error(request, 'Por favor, preencha todos os campos.')

    config = ConfiguracaoEmpresa.get_configuracao_ativa()
    return render(request, 'sistema/login.html', {'config_empresa': config})


def logout_view(request):
    """View personalizada para logout"""
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, 'Você foi desconectado com sucesso.')
    return redirect('sistema:home')


# ============================================================================
# RECUPERACAO DE SENHA
# ============================================================================

def esqueci_senha_view(request):
    """Tela para solicitar recuperacao de senha."""
    from apps.sistema.models import ConfiguracaoRecuperacaoSenha
    config = ConfiguracaoRecuperacaoSenha.get_config()

    if not config.email_ativo and not config.whatsapp_ativo:
        messages.error(request, 'Recuperacao de senha nao esta configurada. Contate o administrador.')
        return redirect('sistema:login')

    if request.method == 'POST':
        identificador = request.POST.get('identificador', '').strip()
        metodo = request.POST.get('metodo', '')

        if not identificador:
            messages.error(request, 'Informe seu email ou nome de usuario.')
            return render(request, 'sistema/esqueci_senha.html', {'config': config})

        # Buscar usuario
        from django.contrib.auth.models import User
        user = User.objects.filter(email=identificador).first() or User.objects.filter(username=identificador).first()

        if not user:
            messages.error(request, 'Usuario nao encontrado.')
            return render(request, 'sistema/esqueci_senha.html', {'config': config})

        # Gerar codigo
        import random, secrets
        from datetime import timedelta
        from apps.sistema.models import CodigoRecuperacaoSenha

        # Invalidar codigos anteriores
        CodigoRecuperacaoSenha.objects.filter(user=user, usado=False).update(usado=True)

        codigo = f'{random.randint(100000, 999999)}'
        token = secrets.token_urlsafe(48)
        expira_em = timezone.now() + timedelta(minutes=config.codigo_expiracao_minutos)

        registro = CodigoRecuperacaoSenha.objects.create(
            user=user, codigo=codigo, token=token,
            metodo=metodo, expira_em=expira_em,
        )

        if metodo == 'email' and config.email_ativo:
            _enviar_email_recuperacao(user, token, config, request)
            messages.success(request, f'Link de recuperacao enviado para {user.email}.')
            return redirect('sistema:login')

        elif metodo == 'whatsapp' and config.whatsapp_ativo:
            _enviar_whatsapp_codigo(user, codigo, config)
            request.session['recuperacao_user_id'] = user.pk
            request.session['recuperacao_codigo_id'] = registro.pk
            return redirect('sistema:verificar_codigo')

        messages.error(request, 'Metodo de recuperacao invalido.')

    return render(request, 'sistema/esqueci_senha.html', {'config': config})


def verificar_codigo_view(request):
    """Tela para digitar o codigo recebido por WhatsApp."""
    from apps.sistema.models import CodigoRecuperacaoSenha, ConfiguracaoRecuperacaoSenha

    codigo_id = request.session.get('recuperacao_codigo_id')
    if not codigo_id:
        return redirect('sistema:esqueci_senha')

    registro = CodigoRecuperacaoSenha.objects.filter(pk=codigo_id, usado=False).first()
    if not registro or registro.expirado:
        messages.error(request, 'Codigo expirado. Solicite um novo.')
        return redirect('sistema:esqueci_senha')

    if registro.bloqueado:
        messages.error(request, 'Numero maximo de tentativas excedido. Solicite um novo codigo.')
        return redirect('sistema:esqueci_senha')

    if request.method == 'POST':
        codigo_digitado = request.POST.get('codigo', '').strip()

        if codigo_digitado == registro.codigo:
            # Codigo correto — redirecionar para nova senha
            registro.usado = True
            registro.save(update_fields=['usado'])
            request.session['recuperacao_token'] = registro.token
            return redirect('sistema:nova_senha')
        else:
            registro.tentativas += 1
            registro.save(update_fields=['tentativas'])
            restantes = ConfiguracaoRecuperacaoSenha.get_config().max_tentativas - registro.tentativas
            if restantes <= 0:
                messages.error(request, 'Numero maximo de tentativas excedido.')
                return redirect('sistema:esqueci_senha')
            messages.error(request, f'Codigo incorreto. {restantes} tentativa(s) restante(s).')

    return render(request, 'sistema/verificar_codigo.html')


def nova_senha_view(request):
    """Tela para definir nova senha."""
    from apps.sistema.models import CodigoRecuperacaoSenha

    token = request.session.get('recuperacao_token') or request.GET.get('token', '')
    if not token:
        return redirect('sistema:esqueci_senha')

    registro = CodigoRecuperacaoSenha.objects.filter(token=token, usado=True).order_by('-criado_em').first()
    if not registro:
        messages.error(request, 'Link invalido ou expirado.')
        return redirect('sistema:esqueci_senha')

    if request.method == 'POST':
        senha1 = request.POST.get('senha1', '')
        senha2 = request.POST.get('senha2', '')

        if not senha1 or len(senha1) < 6:
            messages.error(request, 'A senha deve ter pelo menos 6 caracteres.')
        elif senha1 != senha2:
            messages.error(request, 'As senhas nao conferem.')
        else:
            user = registro.user
            user.set_password(senha1)
            user.save()
            # Limpar sessao
            request.session.pop('recuperacao_token', None)
            request.session.pop('recuperacao_user_id', None)
            request.session.pop('recuperacao_codigo_id', None)
            messages.success(request, 'Senha alterada com sucesso! Faca login.')
            return redirect('sistema:login')

    return render(request, 'sistema/nova_senha.html')


def _enviar_email_recuperacao(user, token, config, request):
    """Envia email com link de recuperacao."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    link = request.build_absolute_uri(f'/sistema/nova-senha/?token={token}')
    nome = user.get_full_name() or user.username

    html = f"""
    <h2>Recuperacao de Senha</h2>
    <p>Ola {nome},</p>
    <p>Voce solicitou a recuperacao de senha. Clique no link abaixo para definir uma nova senha:</p>
    <p><a href="{link}" style="background:#3b82f6;color:#fff;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;">Redefinir Senha</a></p>
    <p>Este link expira em {config.codigo_expiracao_minutos} minutos.</p>
    <p>Se voce nao solicitou, ignore este email.</p>
    """

    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Recuperacao de Senha'
    msg['From'] = config.email_remetente or config.smtp_usuario
    msg['To'] = user.email
    msg.attach(MIMEText(html, 'html'))

    try:
        server = smtplib.SMTP(config.smtp_host, config.smtp_porta)
        if config.smtp_tls:
            server.starttls()
        server.login(config.smtp_usuario, config.smtp_senha)
        server.sendmail(msg['From'], [user.email], msg.as_string())
        server.quit()
    except Exception as e:
        logger.error(f'Erro ao enviar email de recuperacao: {e}')


def _enviar_whatsapp_codigo(user, codigo, config):
    """Envia codigo de recuperacao via WhatsApp (Uazapi)."""
    try:
        perfil = user.perfil
        telefone = perfil.telefone
        if not telefone:
            logger.error(f'Usuario {user.username} nao tem telefone cadastrado.')
            return

        integracao = config.whatsapp_integracao
        if not integracao:
            logger.error('Integracao WhatsApp nao configurada para recuperacao de senha.')
            return

        from apps.integracoes.services.uazapi import UazapiService
        service = UazapiService(integracao)
        mensagem = f'Seu codigo de recuperacao de senha e: *{codigo}*\n\nEste codigo expira em {config.codigo_expiracao_minutos} minutos. Nao compartilhe com ninguem.'
        service.enviar_texto(telefone, mensagem)
    except Exception as e:
        logger.error(f'Erro ao enviar WhatsApp de recuperacao: {e}')


# ============================================================================
# VIEWS DE CONFIGURAÇÕES — migradas de vendas_web/views.py (Sub-phase 3G)
# ============================================================================

@login_required
def configuracoes_view(request):
    """View principal para configurações do sistema"""
    return render(request, 'sistema/configuracoes/index.html')


@login_required
def perfis_permissao_view(request):
    """Página dedicada para gerenciar perfis de permissão."""
    from apps.sistema.decorators import user_tem_funcionalidade
    if not user_tem_funcionalidade(request, 'config.gerenciar_perfis'):
        messages.error(request, 'Sem permissão.')
        return redirect('dashboard:dashboard1')
    return render(request, 'sistema/configuracoes/perfis_permissao.html')


@login_required
def configuracoes_usuarios_view(request):
    """View para gerenciar usuários do sistema"""
    from django.contrib.auth.models import User, Group

    from apps.sistema.decorators import user_tem_funcionalidade
    if not user_tem_funcionalidade(request, 'config.gerenciar_usuarios'):
        messages.error(request, 'Você não tem permissão para acessar esta página.')
        return redirect('dashboard:dashboard1')

    from apps.sistema.models import PermissaoUsuario, PerfilPermissao

    # Filtrar usuarios pelo tenant atual (via PerfilUsuario)
    from apps.sistema.models import PerfilUsuario
    if request.tenant:
        user_ids = PerfilUsuario.objects.filter(tenant=request.tenant).values_list('user_id', flat=True)
        users = User.objects.filter(id__in=user_ids).order_by('-date_joined')
    else:
        users = User.objects.none()
    groups = Group.objects.all().order_by('name')

    # Pré-carregar permissões de cada usuário
    permissoes = {p.user_id: p for p in PermissaoUsuario.objects.select_related('perfil').filter(user__in=users)}
    for u in users:
        u.perm = permissoes.get(u.id)

    perfis = PerfilPermissao.objects.filter(tenant=request.tenant).order_by('nome') if request.tenant else PerfilPermissao.objects.none()

    context = {
        'users': users,
        'groups': groups,
        'perfis': perfis,
        'user': request.user,
    }
    return render(request, 'sistema/configuracoes/usuarios.html', context)


@login_required
def configuracoes_recontato_view(request):
    """View para gerenciar configurações de recontato"""
    from apps.sistema.models import ConfiguracaoRecontato
    configuracoes = ConfiguracaoRecontato.objects.all()
    return render(request, 'sistema/configuracoes/recontato.html', {
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
        from apps.sistema.decorators import user_tem_funcionalidade
        if not user_tem_funcionalidade(request, 'config.gerenciar_usuarios'):
            return JsonResponse({'error': 'Sem permissão'}, status=403)

        data = json.loads(request.body)
        email = data.get('email', '').strip()
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        password = data.get('password')
        groups = data.get('groups', [])
        is_active = data.get('is_active', True)
        is_staff = data.get('is_staff', False)

        # Validacoes
        if not email or not password:
            return JsonResponse({'error': 'Email e senha sao obrigatorios'}, status=400)

        if User.objects.filter(email__iexact=email).exists():
            return JsonResponse({'error': 'Email ja existe'}, status=400)

        # Gerar username unico a partir do email
        base_username = email.split('@')[0].lower().replace('.', '_')[:30]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f'{base_username}_{counter}'
            counter += 1

        # Criar usuario
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

        # Criar PerfilUsuario se não existir
        from apps.sistema.models import PerfilUsuario, PermissaoUsuario, PerfilPermissao
        if not hasattr(user, 'perfil'):
            PerfilUsuario.objects.create(user=user, tenant=request.tenant)

        # Atribuir perfil de permissão
        perfil_id = data.get('perfil_id')
        if perfil_id:
            perfil_perm = PerfilPermissao.objects.filter(pk=perfil_id, tenant=request.tenant).first()
            if perfil_perm:
                PermissaoUsuario.objects.update_or_create(
                    user=user,
                    defaults={'tenant': request.tenant, 'perfil': perfil_perm},
                )

        from apps.sistema.utils import registrar_acao
        registrar_acao('config', 'criar', 'usuario', user.id,
                       f'Usuario criado: {user.username} ({user.email})', request=request)

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
@auditar('config', 'editar', 'usuario')
def api_usuarios_editar(request, user_id):
    """API para editar usuário existente"""
    from django.contrib.auth.models import User, Group

    try:
        # Verificar permissões
        from apps.sistema.decorators import user_tem_funcionalidade
        if not user_tem_funcionalidade(request, 'config.gerenciar_usuarios'):
            return JsonResponse({'error': 'Sem permissão'}, status=403)

        # Verificar que o usuario pertence ao tenant atual
        from apps.sistema.models import PerfilUsuario
        if not PerfilUsuario.objects.filter(user_id=user_id, tenant=request.tenant).exists():
            return JsonResponse({'error': 'Usuário não encontrado'}, status=404)

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

        # Atualizar perfil de permissão
        from apps.sistema.models import PermissaoUsuario, PerfilPermissao
        perfil_id = data.get('perfil_id')
        if perfil_id is not None:
            perfil_perm = PerfilPermissao.objects.filter(pk=perfil_id, tenant=request.tenant).first() if perfil_id else None
            PermissaoUsuario.objects.update_or_create(
                user=user,
                defaults={'tenant': request.tenant, 'perfil': perfil_perm},
            )

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
@auditar('config', 'excluir', 'usuario')
def api_usuarios_deletar(request, user_id):
    """API para deletar usuário"""
    from django.contrib.auth.models import User

    try:
        # Verificar permissões
        from apps.sistema.decorators import user_tem_funcionalidade
        if not user_tem_funcionalidade(request, 'config.gerenciar_usuarios'):
            return JsonResponse({'error': 'Sem permissão'}, status=403)

        # Verificar que o usuario pertence ao tenant atual
        from apps.sistema.models import PerfilUsuario
        if not PerfilUsuario.objects.filter(user_id=user_id, tenant=request.tenant).exists():
            return JsonResponse({'error': 'Usuário não encontrado'}, status=404)

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
# APIs DE PERFIS DE PERMISSÃO
# ============================================================================

@login_required
@require_http_methods(["GET", "POST"])
@auditar('config', 'gerenciar', 'perfil_permissao')
def api_perfis_permissao(request):
    """GET: lista perfis. POST: cria perfil."""
    from apps.sistema.models import PerfilPermissao

    from apps.sistema.decorators import user_tem_funcionalidade
    if not user_tem_funcionalidade(request, 'config.gerenciar_perfis'):
        return JsonResponse({'error': 'Sem permissão'}, status=403)

    from apps.sistema.models import Funcionalidade

    if request.method == 'GET':
        perfis = PerfilPermissao.objects.filter(tenant=request.tenant).prefetch_related('funcionalidades').order_by('nome')
        # Todas as funcionalidades disponíveis
        todas = list(Funcionalidade.objects.all().values('id', 'modulo', 'codigo', 'nome', 'descricao', 'ordem'))

        data = []
        for p in perfis:
            func_ids = list(p.funcionalidades.values_list('id', flat=True))
            data.append({
                'id': p.id, 'nome': p.nome, 'descricao': p.descricao,
                'funcionalidades': func_ids,
                'total_usuarios': p.total_usuarios,
            })

        return JsonResponse({'perfis': data, 'funcionalidades': todas})

    # POST: criar
    try:
        data = json.loads(request.body)
        nome = data.get('nome', '').strip()
        if not nome:
            return JsonResponse({'error': 'Nome é obrigatório'}, status=400)

        if PerfilPermissao.objects.filter(tenant=request.tenant, nome=nome).exists():
            return JsonResponse({'error': f'Perfil "{nome}" já existe'}, status=400)

        perfil = PerfilPermissao.objects.create(
            tenant=request.tenant, nome=nome,
            descricao=data.get('descricao', ''),
        )
        func_ids = data.get('funcionalidades', [])
        if func_ids:
            perfil.funcionalidades.set(Funcionalidade.objects.filter(id__in=func_ids))

        return JsonResponse({'success': True, 'message': f'Perfil "{nome}" criado', 'id': perfil.id})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["PUT", "DELETE"])
@auditar('config', 'gerenciar', 'perfil_permissao')
def api_perfil_permissao_detalhe(request, perfil_id):
    """PUT: edita perfil. DELETE: exclui perfil."""
    from apps.sistema.models import PerfilPermissao

    from apps.sistema.decorators import user_tem_funcionalidade
    if not user_tem_funcionalidade(request, 'config.gerenciar_perfis'):
        return JsonResponse({'error': 'Sem permissão'}, status=403)

    try:
        perfil = PerfilPermissao.objects.get(pk=perfil_id, tenant=request.tenant)
    except PerfilPermissao.DoesNotExist:
        return JsonResponse({'error': 'Perfil não encontrado'}, status=404)

    if request.method == 'DELETE':
        nome = perfil.nome
        perfil.delete()
        return JsonResponse({'success': True, 'message': f'Perfil "{nome}" excluído'})

    # PUT: editar
    try:
        from apps.sistema.models import Funcionalidade
        data = json.loads(request.body)
        if 'nome' in data:
            nome = data['nome'].strip()
            if PerfilPermissao.objects.filter(tenant=request.tenant, nome=nome).exclude(pk=perfil_id).exists():
                return JsonResponse({'error': f'Perfil "{nome}" já existe'}, status=400)
            perfil.nome = nome
        if 'descricao' in data:
            perfil.descricao = data['descricao']

        perfil.save()

        if 'funcionalidades' in data:
            func_ids = data['funcionalidades']
            perfil.funcionalidades.set(Funcionalidade.objects.filter(id__in=func_ids))

        return JsonResponse({'success': True, 'message': f'Perfil "{perfil.nome}" atualizado'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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
    """View para exibir e editar perfil do usuário."""
    from apps.sistema.models import PerfilUsuario, PermissaoUsuario, Funcionalidade

    user = request.user
    perfil = getattr(user, 'perfil', None)
    perm = PermissaoUsuario.get_for_user(user)

    if request.method == 'POST':
        # Atualizar dados pessoais
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.email = request.POST.get('email', '').strip()
        user.save(update_fields=['first_name', 'last_name', 'email'])

        telefone = request.POST.get('telefone', '').strip()
        if perfil:
            perfil.telefone = telefone or None
            perfil.save(update_fields=['telefone'])

        # Trocar senha (opcional)
        nova_senha = request.POST.get('nova_senha', '').strip()
        if nova_senha:
            senha_atual = request.POST.get('senha_atual', '')
            if user.check_password(senha_atual):
                user.set_password(nova_senha)
                user.save()
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user)
                messages.success(request, 'Senha alterada com sucesso.')
            else:
                messages.error(request, 'Senha atual incorreta.')
                return redirect('sistema:perfil_usuario')

        messages.success(request, 'Perfil atualizado com sucesso.')
        return redirect('sistema:perfil_usuario')

    # Montar lista de funcionalidades agrupadas por módulo
    funcionalidades_usuario = []
    if perm and perm.perfil:
        func_ids = set(perm.perfil.funcionalidades.values_list('id', flat=True))
        todas = Funcionalidade.objects.all().order_by('modulo', 'ordem')
        by_modulo = {}
        for f in todas:
            by_modulo.setdefault(f.modulo, []).append({
                'nome': f.nome,
                'tem': f.id in func_ids,
            })
        funcionalidades_usuario = by_modulo

    context = {
        'perfil': perfil,
        'perm': perm,
        'funcionalidades': funcionalidades_usuario,
    }
    return render(request, 'sistema/perfil_usuario.html', context)


@login_required(login_url='sistema:login')
def logs_auditoria_view(request):
    """Tela centralizada de logs de auditoria."""
    from apps.sistema.models import LogSistema

    categoria = request.GET.get('categoria', '')
    acao_filter = request.GET.get('acao', '')
    usuario_filter = request.GET.get('usuario', '')
    nivel = request.GET.get('nivel', '')
    entidade = request.GET.get('entidade', '')

    logs = LogSistema.objects.order_by('-data_criacao')

    if categoria:
        logs = logs.filter(categoria=categoria)
    if acao_filter:
        logs = logs.filter(acao__icontains=acao_filter)
    if usuario_filter:
        logs = logs.filter(usuario__icontains=usuario_filter)
    if nivel:
        logs = logs.filter(nivel=nivel)
    if entidade:
        logs = logs.filter(entidade__icontains=entidade)

    context = {
        'logs': logs[:200],
        'categoria': categoria,
        'acao_filter': acao_filter,
        'usuario_filter': usuario_filter,
        'nivel': nivel,
        'entidade': entidade,
        'categorias': LogSistema.CATEGORIA_CHOICES,
    }
    return render(request, 'sistema/logs_auditoria.html', context)


@login_required
def configuracoes_empresa_view(request):
    """Configuracoes da empresa: nome, logo, cores, integracoes."""
    from apps.sistema.models import ConfiguracaoEmpresa
    from apps.integracoes.models import IntegracaoAPI

    config = ConfiguracaoEmpresa.objects.filter(ativo=True).first()
    if not config:
        config = ConfiguracaoEmpresa.objects.create(ativo=True)

    if request.method == 'POST':
        config.nome_empresa = request.POST.get('nome_empresa', config.nome_empresa)
        config.cor_primaria = request.POST.get('cor_primaria', config.cor_primaria)
        config.cor_secundaria = request.POST.get('cor_secundaria', config.cor_secundaria)
        config.enviar_leads_integracao = request.POST.get('enviar_leads_integracao') == 'on'
        integ_id = request.POST.get('integracao_leads')
        config.integracao_leads_id = integ_id if integ_id else None

        if request.FILES.get('logo_empresa'):
            config.logo_empresa = request.FILES['logo_empresa']

        config.save()
        messages.success(request, 'Configuracoes salvas.')
        return redirect('sistema:configuracoes_empresa')

    integracoes = IntegracaoAPI.objects.filter(ativa=True)

    return render(request, 'sistema/configuracoes/empresa.html', {
        'config': config,
        'integracoes': integracoes,
    })


@login_required
@require_http_methods(["POST"])
def api_agente_status(request):
    """Muda o status do agente (online/ausente/offline)."""
    import json
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    novo_status = body.get('status', '')
    if novo_status not in ('online', 'ausente', 'offline'):
        return JsonResponse({'error': 'Status invalido'}, status=400)

    from apps.inbox.models import PerfilAgenteInbox
    perfil, created = PerfilAgenteInbox.objects.get_or_create(
        user=request.user,
        defaults={'status': novo_status}
    )
    if not created:
        perfil.status = novo_status
        perfil.save(update_fields=['status', 'ultimo_status_em'])

    return JsonResponse({'ok': True, 'status': novo_status})
