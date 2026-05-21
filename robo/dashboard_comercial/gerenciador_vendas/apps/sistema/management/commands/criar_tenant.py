"""
Management command para onboarding de novo provedor.
Cria Tenant + User admin + PerfilUsuario + ConfiguracaoEmpresa.

Dois modos de uso:

1. Preset (atalho) — combinacoes comuns:
    python manage.py criar_tenant \
        --nome "Provedor X" --slug "provedor-x" \
        --plano comercial_pro \
        --admin-user admin_provx --admin-email admin@provedorx.com \
        --admin-senha SenhaSegura123

2. Explicito — escolhe modulos e tiers livremente (use pra contas
   com combinacao fora dos presets, ex: Comercial + Marketing sem CS):
    python manage.py criar_tenant \
        --nome "Nuvyon" --slug "nuvyon" --cnpj "53.309.518/0001-78" \
        --modulos comercial,marketing \
        --tier-comercial pro --tier-marketing start \
        --admin-user admin_nuvyon --admin-email contato@nuvyon.com.br \
        --admin-senha SenhaSegura123

Tiers validos: starter | start | pro  (o sistema nao tem "advanced" —
o "Advanced" comercial mapeia para o tier "pro").
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils.text import slugify

from apps.sistema.models import Tenant, PerfilUsuario, ConfiguracaoEmpresa


TIERS_VALIDOS = ('starter', 'start', 'pro')
MODULOS_VALIDOS = ('comercial', 'marketing', 'cs', 'workspace')

# Presets — atalhos pra combinacoes comuns.
PLANOS = {
    'comercial_starter': {'modulos': ['comercial'], 'comercial': 'starter'},
    'comercial_start':   {'modulos': ['comercial'], 'comercial': 'start'},
    'comercial_pro':     {'modulos': ['comercial'], 'comercial': 'pro'},
    'full_start':        {'modulos': ['comercial', 'marketing', 'cs'],
                          'comercial': 'start', 'marketing': 'start', 'cs': 'start'},
    'full_pro':          {'modulos': ['comercial', 'marketing', 'cs'],
                          'comercial': 'pro', 'marketing': 'pro', 'cs': 'pro'},
}


class Command(BaseCommand):
    help = 'Cria um novo tenant (provedor) com user admin e configuração inicial.'

    def add_arguments(self, parser):
        parser.add_argument('--nome', required=True, help='Nome do provedor')
        parser.add_argument('--slug', help='Slug (gerado automaticamente se não informado)')
        parser.add_argument('--cnpj', default='', help='CNPJ do provedor')

        # Modo 1: preset
        parser.add_argument('--plano', choices=PLANOS.keys(),
                            help='Preset de plano (atalho). Ignorado se --modulos for usado.')

        # Modo 2: explicito
        parser.add_argument('--modulos', default='',
                            help='CSV de modulos ativos (ex: "comercial,marketing"). '
                                 'Sobrepoe --plano. Validos: ' + ', '.join(MODULOS_VALIDOS))
        parser.add_argument('--tier-comercial', dest='tier_comercial', choices=TIERS_VALIDOS)
        parser.add_argument('--tier-marketing', dest='tier_marketing', choices=TIERS_VALIDOS)
        parser.add_argument('--tier-cs', dest='tier_cs', choices=TIERS_VALIDOS)
        parser.add_argument('--tier-workspace', dest='tier_workspace', choices=TIERS_VALIDOS)

        # Admin
        parser.add_argument('--admin-user', required=True, help='Username do admin do tenant')
        parser.add_argument('--admin-email', required=True, help='Email do admin')
        parser.add_argument('--admin-senha', required=True, help='Senha do admin')
        parser.add_argument('--admin-telefone', default='', help='Telefone do admin')
        parser.add_argument('--trial', action='store_true', help='Iniciar em trial de 14 dias')
        parser.add_argument('--dry-run', action='store_true',
                            help='Mostra o que seria criado, sem persistir.')

    def _resolver_config(self, options) -> dict:
        """
        Resolve modulos ativos + tier de cada modulo.
        Prioridade: --modulos explicito > --plano preset > erro.
        Os --tier-* sempre sobrescrevem o tier (default 'starter').
        """
        modulos_csv = (options.get('modulos') or '').strip()
        preset_nome = options.get('plano')

        if modulos_csv:
            modulos = [m.strip() for m in modulos_csv.split(',') if m.strip()]
            invalidos = [m for m in modulos if m not in MODULOS_VALIDOS]
            if invalidos:
                raise CommandError(f'Modulo(s) invalido(s): {invalidos}. Validos: {MODULOS_VALIDOS}')
            tiers = {}
        elif preset_nome:
            preset = PLANOS[preset_nome]
            modulos = list(preset['modulos'])
            tiers = {k: v for k, v in preset.items() if k != 'modulos'}
        else:
            raise CommandError('Informe --plano (preset) OU --modulos (explicito).')

        # --tier-* sempre sobrescreve
        for mod in MODULOS_VALIDOS:
            override = options.get(f'tier_{mod}')
            if override:
                tiers[mod] = override

        return {
            'modulos': modulos,
            'comercial': tiers.get('comercial', 'starter'),
            'marketing': tiers.get('marketing', 'starter'),
            'cs': tiers.get('cs', 'starter'),
            'workspace': tiers.get('workspace', 'starter'),
        }

    def handle(self, *args, **options):
        nome = options['nome']
        slug = options['slug'] or slugify(nome)
        cfg = self._resolver_config(options)
        dry_run = options['dry_run']

        # Validações
        if Tenant.objects.filter(slug=slug).exists():
            raise CommandError(f'Tenant com slug "{slug}" já existe.')
        if User.objects.filter(username=options['admin_user']).exists():
            raise CommandError(f'Usuário "{options["admin_user"]}" já existe.')

        tenant_kwargs = {
            'nome': nome,
            'slug': slug,
            'cnpj': options['cnpj'] or None,
            'modulo_comercial': 'comercial' in cfg['modulos'],
            'modulo_marketing': 'marketing' in cfg['modulos'],
            'modulo_cs': 'cs' in cfg['modulos'],
            'modulo_workspace': 'workspace' in cfg['modulos'],
            'plano_comercial': cfg['comercial'],
            'plano_marketing': cfg['marketing'],
            'plano_cs': cfg['cs'],
            'plano_workspace': cfg['workspace'],
            'ativo': True,
        }
        if options['trial']:
            from datetime import date, timedelta
            tenant_kwargs['em_trial'] = True
            tenant_kwargs['trial_inicio'] = date.today()
            tenant_kwargs['trial_fim'] = date.today() + timedelta(days=14)

        # Resumo do que vai ser feito
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'{"[DRY-RUN] " if dry_run else ""}Provisionamento de tenant'
        ))
        self.stdout.write(f'  Nome:    {nome} (slug: {slug})')
        self.stdout.write(f'  CNPJ:    {options["cnpj"] or "—"}')
        self.stdout.write(f'  Modulos: {", ".join(cfg["modulos"])}')
        for mod in cfg['modulos']:
            self.stdout.write(f'    - {mod}: tier {cfg[mod]}')
        self.stdout.write(f'  Trial:   {"Sim (14 dias)" if options["trial"] else "Nao"}')
        self.stdout.write(f'  Admin:   {options["admin_user"]} / {options["admin_email"]}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDry-run — nada foi persistido.'))
            return

        # 1. Tenant
        tenant = Tenant(**tenant_kwargs)
        tenant.save()
        self.stdout.write(self.style.SUCCESS(f'\nTenant criado: {tenant.nome} ({tenant.slug})'))

        # 2. User admin
        user = User.objects.create_user(
            username=options['admin_user'],
            email=options['admin_email'],
            password=options['admin_senha'],
            first_name=nome,
        )
        self.stdout.write(self.style.SUCCESS(f'User criado: {user.username}'))

        # 3. PerfilUsuario
        perfil = PerfilUsuario.objects.create(
            user=user,
            tenant=tenant,
            telefone=options['admin_telefone'] or None,
        )
        self.stdout.write(self.style.SUCCESS(f'Perfil criado: {perfil}'))

        # 4. ConfiguracaoEmpresa
        ConfiguracaoEmpresa.objects.create(tenant=tenant, nome_empresa=nome, ativo=True)
        self.stdout.write(self.style.SUCCESS('Configuração da empresa criada'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== Onboarding concluído ==='))
        self.stdout.write(f'  Tenant id: {tenant.pk} | slug: {tenant.slug}')
        self.stdout.write(f'  Login:     {user.username} / {options["admin_email"]}')
        self.stdout.write('  URL:       /login/')
