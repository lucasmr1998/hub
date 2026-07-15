"""Reseta a senha de um usuario existente, forcando troca no primeiro login.

Existe por um caso concreto: quem e PROMOVIDO nao tem a senha tocada (e nem
deve ter), entao continua com a senha antiga. Se a pessoa nao lembra dela — a
Damaris nao acessava desde 03/07 — ela simplesmente nao entra, e de fora parece
que "o acesso nao foi criado".

Sempre marca `senha_temporaria=True`: a senha que o admin define morre no
primeiro login.

Uso:
    python manage.py resetar_senha --tenant nuvyon \
        --email damaris.silva@nuvyon.com.br --senha "Nuvyon@2026"

    # sem --senha, sorteia uma e imprime uma unica vez
    python manage.py resetar_senha --tenant nuvyon --email ... --dry-run
"""
import secrets
import string

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.sistema.models import Tenant, PerfilUsuario

ALFABETO = string.ascii_letters + string.digits


class Command(BaseCommand):
    help = 'Reseta a senha de um usuario (com troca obrigatoria no primeiro login).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True)
        parser.add_argument('--email', required=True)
        parser.add_argument('--senha', default=None,
                            help='Senha nova. Sem isso, sorteia uma.')
        parser.add_argument('--dry-run', action='store_true')

    @transaction.atomic
    def handle(self, *args, **opts):
        email = opts['email'].strip().lower()

        try:
            tenant = Tenant.objects.get(slug=opts['tenant'], ativo=True)
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Tenant {opts['tenant']!r} nao encontrado."))
            return

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            self.stdout.write(self.style.ERROR(f'Usuario {email} nao existe.'))
            return

        perfil = PerfilUsuario.objects.filter(user=user).first()
        if not perfil or perfil.tenant_id != tenant.id:
            dono = perfil.tenant.slug if perfil else '(sem tenant)'
            self.stdout.write(self.style.ERROR(
                f'{email} pertence ao tenant {dono!r}, nao a {tenant.slug!r}. Abortado.'
            ))
            return

        senha = opts['senha'] or ''.join(secrets.choice(ALFABETO) for _ in range(12))
        if len(senha) < 8:
            self.stdout.write(self.style.ERROR('Senha muito curta (minimo 8). Abortado.'))
            return

        ultimo = user.last_login.strftime('%d/%m/%Y %H:%M') if user.last_login else 'NUNCA'
        self.stdout.write(f'  {user.username} ({email}) | ultimo login: {ultimo}')

        if opts['dry_run']:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING('  [DRY-RUN] senha NAO alterada.'))
            return

        user.set_password(senha)
        user.save(update_fields=['password'])
        perfil.senha_temporaria = True
        perfil.save(update_fields=['senha_temporaria'])

        self.stdout.write(self.style.SUCCESS('  SENHA RESETADA (troca obrigatoria no proximo login).'))
        if not opts['senha']:
            self.stdout.write(self.style.WARNING(f'  SENHA SORTEADA: {senha}'))
