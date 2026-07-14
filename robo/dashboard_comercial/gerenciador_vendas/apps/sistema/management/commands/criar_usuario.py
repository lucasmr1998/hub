"""Cria usuario de um tenant pela linha de comando (mesmo caminho da UI).

Existe pra dar um jeito revisavel e repetivel de provisionar gente: a criacao
passa pelo Django (senha hasheada, nunca SQL cru), amarra o usuario ao tenant,
aplica o perfil de permissao e, opcionalmente, cria o cadastro de vendedor do
CRM (que e o que faz a pessoa aparecer no filtro por time e no scorecard).

A senha e SORTEADA e sai no stdout uma unica vez, com `senha_temporaria=True`:
a pessoa e obrigada a trocar no primeiro login.

Uso:
    python manage.py criar_usuario --tenant nuvyon \
        --email taina.susi@nuvyon.com.br --nome "Taina" --sobrenome "Susi" \
        --perfil "Vendedor" --cargo vendedor

    # varios de uma vez, do mesmo jeito, e idempotente (email existente e pulado):
    python manage.py criar_usuario --tenant nuvyon --email ... --dry-run
"""
import secrets
import string

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.sistema.models import (
    Tenant, PerfilUsuario, PerfilPermissao, PermissaoUsuario,
)

ALFABETO = string.ascii_letters + string.digits
CARGOS = ('vendedor', 'supervisor', 'gerente', 'diretor', 'outro')


class Command(BaseCommand):
    help = 'Cria um usuario no tenant (User + PerfilUsuario + perfil de permissao + cargo CRM).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True, help='Slug do tenant (ex: nuvyon)')
        parser.add_argument('--email', required=True)
        parser.add_argument('--nome', default='', help='Primeiro nome')
        parser.add_argument('--sobrenome', default='')
        parser.add_argument('--perfil', required=True,
                            help='Nome do PerfilPermissao (ex: "Vendedor", "Gerente Comercial")')
        parser.add_argument('--cargo', choices=CARGOS, default=None,
                            help='Cria tambem o PerfilVendedor do CRM com este cargo. '
                                 'Sem isso, a pessoa nao entra no filtro por time.')
        parser.add_argument('--equipe', default=None,
                            help='Nome da EquipeVendas pra vincular (opcional).')
        parser.add_argument('--senha', default=None,
                            help='Senha inicial. Sem isso, sorteia uma. Em qualquer caso a '
                                 'troca no primeiro login continua obrigatoria.')
        parser.add_argument('--dry-run', action='store_true')

    @transaction.atomic
    def handle(self, *args, **opts):
        from apps.comercial.crm.models import PerfilVendedor, EquipeVendas

        dry = opts['dry_run']
        email = opts['email'].strip().lower()

        try:
            tenant = Tenant.objects.get(slug=opts['tenant'], ativo=True)
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Tenant {opts['tenant']!r} nao encontrado."))
            return

        if User.objects.filter(email__iexact=email).exists():
            self.stdout.write(self.style.WARNING(f'  ja existe (pulado): {email}'))
            return

        username = email.split('@')[0]
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.ERROR(f'  username {username!r} em uso. Abortado.'))
            return

        perfil = PerfilPermissao.objects.filter(tenant=tenant, nome=opts['perfil']).first()
        if not perfil:
            nomes = list(PerfilPermissao.objects.filter(tenant=tenant)
                         .values_list('nome', flat=True))
            self.stdout.write(self.style.ERROR(
                f"Perfil {opts['perfil']!r} nao existe no tenant. Disponiveis: {nomes}"
            ))
            return

        equipe = None
        if opts['equipe']:
            equipe = EquipeVendas.all_tenants.filter(
                tenant=tenant, nome=opts['equipe'], ativo=True).first()
            if not equipe:
                self.stdout.write(self.style.ERROR(
                    f"Equipe {opts['equipe']!r} nao existe no tenant. Abortado."
                ))
                return

        if dry:
            self.stdout.write(
                f'  [DRY] criaria {username} ({email}) perfil={perfil.nome} '
                f"cargo={opts['cargo'] or '(sem cadastro CRM)'} equipe={opts['equipe'] or '—'}"
            )
            transaction.set_rollback(True)
            return

        senha = opts['senha'] or ''.join(secrets.choice(ALFABETO) for _ in range(12))
        if len(senha) < 8:
            self.stdout.write(self.style.ERROR('Senha muito curta (minimo 8). Abortado.'))
            return

        user = User.objects.create_user(
            username=username, email=email, password=senha,
            first_name=opts['nome'], last_name=opts['sobrenome'],
            is_active=True, is_staff=False,
        )
        PerfilUsuario.objects.create(user=user, tenant=tenant, senha_temporaria=True)
        PermissaoUsuario.objects.update_or_create(
            user=user, defaults={'perfil': perfil, 'tenant': tenant},
        )
        if opts['cargo']:
            PerfilVendedor.all_tenants.create(
                tenant=tenant, user=user, cargo=opts['cargo'], ativo=True, equipe=equipe,
            )

        self.stdout.write(self.style.SUCCESS(f'  criado: {username}'))
        self.stdout.write(f'    email  : {email}')
        self.stdout.write(f'    perfil : {perfil.nome}')
        self.stdout.write(f"    cargo  : {opts['cargo'] or '(sem cadastro CRM)'}"
                          f"{f' / {equipe.nome}' if equipe else ''}")
        if opts['senha']:
            self.stdout.write('    senha  : (a que foi informada) — troca obrigatoria no 1o login')
        else:
            self.stdout.write(self.style.WARNING(f'    SENHA SORTEADA: {senha}'))
            self.stdout.write('    (troca obrigatoria no primeiro login)')
