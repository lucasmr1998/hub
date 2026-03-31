"""
Management command para onboarding de novo provedor.
Cria Tenant + User admin + PerfilUsuario + ConfiguracaoEmpresa.

Uso:
    python manage.py criar_tenant \
        --nome "Provedor X" \
        --slug "provedor-x" \
        --cnpj "12.345.678/0001-90" \
        --plano comercial_start \
        --admin-user admin_provx \
        --admin-email admin@provedorx.com \
        --admin-senha SenhaSegura123
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils.text import slugify

from apps.sistema.models import Tenant, PerfilUsuario, ConfiguracaoEmpresa


PLANOS = {
    'comercial_starter': {'comercial': True, 'marketing': False, 'cs': False, 'plano_comercial': 'starter'},
    'comercial_start':   {'comercial': True, 'marketing': False, 'cs': False, 'plano_comercial': 'start'},
    'comercial_pro':     {'comercial': True, 'marketing': False, 'cs': False, 'plano_comercial': 'pro'},
    'full_start':        {'comercial': True, 'marketing': True, 'cs': True, 'plano_comercial': 'start', 'plano_marketing': 'start', 'plano_cs': 'start'},
    'full_pro':          {'comercial': True, 'marketing': True, 'cs': True, 'plano_comercial': 'pro', 'plano_marketing': 'pro', 'plano_cs': 'pro'},
}


class Command(BaseCommand):
    help = 'Cria um novo tenant (provedor) com user admin e configuração inicial.'

    def add_arguments(self, parser):
        parser.add_argument('--nome', required=True, help='Nome do provedor')
        parser.add_argument('--slug', help='Slug (gerado automaticamente se não informado)')
        parser.add_argument('--cnpj', default='', help='CNPJ do provedor')
        parser.add_argument('--plano', default='comercial_start', choices=PLANOS.keys(), help='Plano inicial')
        parser.add_argument('--admin-user', required=True, help='Username do admin do tenant')
        parser.add_argument('--admin-email', required=True, help='Email do admin')
        parser.add_argument('--admin-senha', required=True, help='Senha do admin')
        parser.add_argument('--admin-telefone', default='', help='Telefone do admin')
        parser.add_argument('--trial', action='store_true', help='Iniciar em trial de 14 dias')

    def handle(self, *args, **options):
        nome = options['nome']
        slug = options['slug'] or slugify(nome)
        plano_config = PLANOS[options['plano']]

        # Validações
        if Tenant.objects.filter(slug=slug).exists():
            raise CommandError(f'Tenant com slug "{slug}" já existe.')
        if User.objects.filter(username=options['admin_user']).exists():
            raise CommandError(f'Usuário "{options["admin_user"]}" já existe.')

        # 1. Criar Tenant
        tenant_kwargs = {
            'nome': nome,
            'slug': slug,
            'cnpj': options['cnpj'] or None,
            'modulo_comercial': plano_config.get('comercial', False),
            'modulo_marketing': plano_config.get('marketing', False),
            'modulo_cs': plano_config.get('cs', False),
            'plano_comercial': plano_config.get('plano_comercial', 'starter'),
            'plano_marketing': plano_config.get('plano_marketing', 'starter'),
            'plano_cs': plano_config.get('plano_cs', 'starter'),
            'ativo': True,
        }

        if options['trial']:
            from datetime import date, timedelta
            tenant_kwargs['em_trial'] = True
            tenant_kwargs['trial_inicio'] = date.today()
            tenant_kwargs['trial_fim'] = date.today() + timedelta(days=14)

        tenant = Tenant(**tenant_kwargs)
        tenant.save()
        self.stdout.write(self.style.SUCCESS(f'Tenant criado: {tenant.nome} ({tenant.slug})'))

        # 2. Criar User
        user = User.objects.create_user(
            username=options['admin_user'],
            email=options['admin_email'],
            password=options['admin_senha'],
            first_name=nome,
        )
        self.stdout.write(self.style.SUCCESS(f'User criado: {user.username}'))

        # 3. Criar PerfilUsuario
        perfil = PerfilUsuario.objects.create(
            user=user,
            tenant=tenant,
            telefone=options['admin_telefone'] or None,
        )
        self.stdout.write(self.style.SUCCESS(f'Perfil criado: {perfil}'))

        # 4. Criar ConfiguracaoEmpresa
        config = ConfiguracaoEmpresa(
            tenant=tenant,
            nome_empresa=nome,
            ativo=True,
        )
        config.save()
        self.stdout.write(self.style.SUCCESS(f'Configuração da empresa criada'))

        # Resumo
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== Onboarding concluído ==='))
        self.stdout.write(f'  Tenant:  {tenant.nome} (slug: {tenant.slug})')
        self.stdout.write(f'  Plano:   {options["plano"]}')
        self.stdout.write(f'  Trial:   {"Sim (14 dias)" if options["trial"] else "Não"}')
        self.stdout.write(f'  Login:   {user.username} / {options["admin_email"]}')
        self.stdout.write(f'  URL:     /login/')
