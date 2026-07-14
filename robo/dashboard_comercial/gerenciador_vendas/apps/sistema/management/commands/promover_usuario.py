"""Troca o perfil de permissao de um usuario que JA existe (e o cargo no CRM).

Existe porque `criar_usuario` e idempotente por email: rodar ele num usuario ja
existente PULA em silencio, e quem pediu a promocao acha que promoveu. Promover
e outra operacao, entao e outro comando.

Mostra SEMPRE o antes e o depois — promover muda o que a pessoa enxerga no
sistema (um Gerente Comercial ve o pipeline inteiro, nao so o dele).

Uso:
    python manage.py promover_usuario --tenant nuvyon \
        --email caio.resende@nuvyon.com.br --perfil "Gerente Comercial" --cargo gerente

    python manage.py promover_usuario --tenant nuvyon --email ... --dry-run
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.sistema.models import (
    Tenant, PerfilUsuario, PerfilPermissao, PermissaoUsuario,
)

CARGOS = ('vendedor', 'supervisor', 'gerente', 'diretor', 'outro')


class Command(BaseCommand):
    help = 'Troca o perfil de permissao (e o cargo CRM) de um usuario existente.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True)
        parser.add_argument('--email', required=True)
        parser.add_argument('--perfil', required=True,
                            help='Novo PerfilPermissao (ex: "Gerente Comercial")')
        parser.add_argument('--cargo', choices=CARGOS, default=None,
                            help='Novo cargo no CRM (PerfilVendedor). Cria o cadastro se nao existir.')
        parser.add_argument('--equipe', default=None, help='Nome da EquipeVendas (opcional).')
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

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            self.stdout.write(self.style.ERROR(
                f'Usuario {email} NAO existe. Pra criar, use o criar_usuario.'
            ))
            return

        # O usuario e mesmo deste tenant? Promover alguem de outro tenant seria
        # vazamento de acesso entre clientes.
        perfil_usuario = PerfilUsuario.objects.filter(user=user).first()
        if not perfil_usuario or perfil_usuario.tenant_id != tenant.id:
            dono = perfil_usuario.tenant.slug if perfil_usuario else '(sem tenant)'
            self.stdout.write(self.style.ERROR(
                f'{email} pertence ao tenant {dono!r}, nao a {tenant.slug!r}. Abortado.'
            ))
            return

        novo_perfil = PerfilPermissao.objects.filter(tenant=tenant, nome=opts['perfil']).first()
        if not novo_perfil:
            nomes = list(PerfilPermissao.objects.filter(tenant=tenant).values_list('nome', flat=True))
            self.stdout.write(self.style.ERROR(
                f"Perfil {opts['perfil']!r} nao existe no tenant. Disponiveis: {nomes}"
            ))
            return

        equipe = None
        if opts['equipe']:
            equipe = EquipeVendas.all_tenants.filter(
                tenant=tenant, nome=opts['equipe'], ativo=True).first()
            if not equipe:
                self.stdout.write(self.style.ERROR(f"Equipe {opts['equipe']!r} nao existe. Abortado."))
                return

        # ---- ANTES ----
        perm = PermissaoUsuario.objects.filter(user=user).first()
        perfil_antes = perm.perfil.nome if perm and perm.perfil else '(nenhum)'
        pv = PerfilVendedor.all_tenants.filter(tenant=tenant, user=user).first()
        cargo_antes = pv.cargo if pv else '(sem cadastro CRM)'
        equipe_antes = pv.equipe.nome if pv and pv.equipe else '—'
        ops = user.oportunidades_responsavel.count() if hasattr(user, 'oportunidades_responsavel') else 0

        self.stdout.write(f'  {user.username} ({email})')
        self.stdout.write(f'    ANTES : perfil={perfil_antes!r} cargo={cargo_antes!r} '
                          f'equipe={equipe_antes!r} oportunidades={ops}')
        self.stdout.write(f"    DEPOIS: perfil={novo_perfil.nome!r} "
                          f"cargo={opts['cargo'] or cargo_antes!r} "
                          f"equipe={opts['equipe'] or equipe_antes!r}")

        if dry:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING('    [DRY-RUN] nada gravado.'))
            return

        PermissaoUsuario.objects.update_or_create(
            user=user, defaults={'perfil': novo_perfil, 'tenant': tenant},
        )
        if opts['cargo'] or equipe:
            if pv:
                if opts['cargo']:
                    pv.cargo = opts['cargo']
                if equipe:
                    pv.equipe = equipe
                pv.ativo = True
                pv.save(update_fields=['cargo', 'equipe', 'ativo'])
            else:
                PerfilVendedor.all_tenants.create(
                    tenant=tenant, user=user,
                    cargo=opts['cargo'] or 'vendedor', equipe=equipe, ativo=True,
                )

        self.stdout.write(self.style.SUCCESS('    PROMOVIDO.'))
        if ops:
            self.stdout.write(
                f'    Atencao: ele continua responsavel por {ops} oportunidade(s). '
                f'Promover nao redistribui carteira.'
            )
