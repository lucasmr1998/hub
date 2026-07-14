"""Confere o catalogo de agentes do Talk contra os usuarios do Hubtrix.

A atribuicao de oportunidade por telefone depende de uma ponte: o nome do agente
na chamada -> o cod_agente no catalogo do Talk -> o `cod_talk` no perfil do
usuario aqui. Se a pessoa atende no Talk mas nao tem `cod_talk` cadastrado, a
oportunidade dela fica SEM DONO — e ninguem descobre, porque o cron so conta e
segue.

Este comando mostra os dois lados e aponta os buracos:
  - agente no Talk SEM usuario no Hubtrix   -> a oportunidade dele vai ficar orfa
  - usuario com cod_talk que NAO existe la  -> cadastro velho, nunca vai casar

Read-only. Roda quando alguem for contratado/desligado, ou quando aparecer
oportunidade orfa vinda de telefone.

Uso:
    python manage.py auditar_agentes_talk --tenant nuvyon
"""
import re
import unicodedata

from django.core.management.base import BaseCommand

from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.talk import TalkService, TalkServiceError
from apps.sistema.models import Tenant, PerfilUsuario


def _norm(s):
    if not s:
        return ''
    s = unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', s.lower().strip())


class Command(BaseCommand):
    help = 'Compara os agentes do Talk com os usuarios do Hubtrix (quem falta mapear).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True)

    def handle(self, *args, **opts):
        try:
            tenant = Tenant.objects.get(slug=opts['tenant'], ativo=True)
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Tenant {opts['tenant']!r} nao encontrado."))
            return

        integ = IntegracaoAPI.all_tenants.filter(tenant=tenant, tipo='talk', ativa=True).first()
        if not integ:
            self.stdout.write(self.style.ERROR('Tenant sem IntegracaoAPI talk ativa.'))
            return

        try:
            agentes = TalkService(integ).listar_agentes()
        except TalkServiceError as exc:
            self.stdout.write(self.style.ERROR(f'Talk listar_agentes falhou: {exc}'))
            return

        # cod_talk -> user (do nosso lado)
        perfis = (PerfilUsuario.objects
                  .filter(tenant=tenant, cod_talk__isnull=False)
                  .select_related('user'))
        cod_to_user = {p.cod_talk: p.user for p in perfis if p.cod_talk}

        no_talk = {}
        for a in agentes:
            cod = a.get('cod_agente')
            if cod:
                no_talk[int(cod)] = (a.get('nom_agente') or '').strip()

        self.stdout.write(f'\n  Talk: {len(no_talk)} agentes | Hubtrix: {len(cod_to_user)} usuarios com cod_talk\n')

        # 1) Agente no Talk sem usuario aqui — este e o buraco que gera orfa
        orfaos = [(cod, nome) for cod, nome in sorted(no_talk.items())
                  if cod not in cod_to_user]
        if orfaos:
            self.stdout.write(self.style.ERROR(
                f'  === {len(orfaos)} agente(s) no Talk SEM usuario no Hubtrix ==='
            ))
            self.stdout.write('  (se um deles atender, a oportunidade fica SEM DONO)')
            for cod, nome in orfaos:
                self.stdout.write(f'    cod_talk={cod:<6} {nome}')
        else:
            self.stdout.write(self.style.SUCCESS('  Todos os agentes do Talk tem usuario aqui.'))

        # 2) cod_talk cadastrado aqui que nao existe mais la
        self.stdout.write('')
        mortos = [(cod, u.username) for cod, u in sorted(cod_to_user.items())
                  if cod not in no_talk]
        if mortos:
            self.stdout.write(self.style.WARNING(
                f'  === {len(mortos)} usuario(s) com cod_talk que NAO existe no Talk ==='
            ))
            self.stdout.write('  (cadastro velho: nunca vai casar com chamada nenhuma)')
            for cod, username in mortos:
                self.stdout.write(f'    cod_talk={cod:<6} {username}')
        else:
            self.stdout.write(self.style.SUCCESS('  Nenhum cod_talk orfao do nosso lado.'))

        # 3) Os que casam
        ok = [(cod, u.username, no_talk[cod]) for cod, u in sorted(cod_to_user.items())
              if cod in no_talk]
        self.stdout.write('')
        self.stdout.write(f'  === {len(ok)} mapeados corretamente ===')
        for cod, username, nome_talk in ok:
            self.stdout.write(f'    cod_talk={cod:<6} {username:<22} <- {nome_talk!r} (no Talk)')
        self.stdout.write('')
