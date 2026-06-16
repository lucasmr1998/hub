"""
Sincroniza OportunidadeVenda.responsavel com o agente atribuido no Matrix Brasil.

Rodar periodicamente (cron a cada 10-15min):
    python manage.py sync_vendedores_matrix --tenant=nuvyon

So mexe em oportunidades:
- Do tenant especificado
- COM `dados_custom['id_atendimento_matrix']` setado (origem Matrix)
- SEM responsavel atribuido (responsavel IS NULL)
- Criadas nos ultimos N dias (default 7)

Pra cada uma:
1. Chama `GET /rest/v1/atendimento?codigo_atendimento=<id>` na Matrix
2. Le `login_agente` do retorno
3. Resolve User no Hubtrix via PerfilUsuario.login_matrix (mesmo tenant)
4. Seta OportunidadeVenda.responsavel + registra acao

Leads sem id_atendimento_matrix (criados manual, importados, etc) seguem
o padrao normal do CRM — atribuicao manual ou via FilaInbox.
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sincroniza vendedor atribuido no Matrix Brasil com OportunidadeVenda.responsavel'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, required=True,
                            help='Slug do tenant (ex: nuvyon)')
        parser.add_argument('--dias', type=int, default=7,
                            help='Janela em dias pra considerar oportunidades recentes (default 7)')
        parser.add_argument('--dry-run', action='store_true',
                            help='So mostra o que faria, nao escreve')
        parser.add_argument('--limit', type=int, default=200,
                            help='Limite de oportunidades por execucao (default 200)')

    def handle(self, *args, **opts):
        from apps.sistema.models import Tenant, PerfilUsuario
        from apps.comercial.crm.models import OportunidadeVenda
        from apps.integracoes.services.matrix_brasil import MatrixBrasilService, MatrixBrasilServiceError

        slug = opts['tenant']
        try:
            tenant = Tenant.objects.get(slug=slug, ativo=True)
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Tenant {slug!r} nao encontrado ou inativo'))
            return

        try:
            svc = MatrixBrasilService.from_tenant(tenant)
        except MatrixBrasilServiceError as e:
            self.stdout.write(self.style.ERROR(f'Matrix Brasil nao configurado pra {slug}: {e}'))
            return

        cutoff = timezone.now() - timedelta(days=opts['dias'])
        qs = (OportunidadeVenda.all_tenants
              .filter(tenant=tenant, responsavel__isnull=True,
                      data_criacao__gte=cutoff,
                      dados_custom__has_key='id_atendimento_matrix')
              .order_by('-data_criacao')[:opts['limit']])

        total = qs.count()
        self.stdout.write(f'Tenant {slug}: {total} oportunidades elegiveis pra sync')

        # Cache: login_matrix -> User
        perfis = PerfilUsuario.objects.filter(
            tenant=tenant, login_matrix__isnull=False,
        ).exclude(login_matrix='').select_related('user')
        login_to_user = {
            (p.login_matrix or '').strip().lower(): p.user
            for p in perfis if p.login_matrix
        }
        self.stdout.write(f'  {len(login_to_user)} usuarios com login_matrix mapeado')

        atribuidos = 0
        sem_login_no_matrix = 0
        sem_match_no_hubtrix = 0
        erros = 0

        for oport in qs:
            codigo = (oport.dados_custom or {}).get('id_atendimento_matrix')
            if not codigo:
                continue
            try:
                dados = svc.consultar_atendimento(codigo)
            except MatrixBrasilServiceError as e:
                logger.warning('[sync_vendedores_matrix] oport=%s erro matrix: %s', oport.pk, e)
                erros += 1
                continue
            login = (dados.get('login_agente') or '').strip()
            if not login:
                sem_login_no_matrix += 1
                continue
            user = login_to_user.get(login.lower())
            if not user:
                sem_match_no_hubtrix += 1
                self.stdout.write(self.style.WARNING(
                    f'  oport={oport.pk} login_agente={login!r} sem User mapeado no Hubtrix'
                ))
                continue
            self.stdout.write(self.style.SUCCESS(
                f'  oport={oport.pk} <- {user.username} (login matrix={login})'
            ))
            if not opts['dry_run']:
                oport.responsavel = user
                oport.save(update_fields=['responsavel', 'data_atualizacao'])
                from apps.sistema.utils import registrar_acao
                try:
                    registrar_acao('crm', 'atribuir', 'oportunidade', oport.pk,
                                   f'Atribuido automatic via Matrix Brasil (login={login}) para {user.username}',
                                   dados_extras={
                                       'login_matrix': login,
                                       'id_atendimento_matrix': codigo,
                                       'origem': 'sync_vendedores_matrix',
                                   })
                except Exception:
                    pass
            atribuidos += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Resumo: atribuidos={atribuidos} '
            f'sem_agente_no_matrix={sem_login_no_matrix} '
            f'sem_user_no_hubtrix={sem_match_no_hubtrix} '
            f'erros={erros}'
        ))
        if opts['dry_run']:
            self.stdout.write(self.style.WARNING('DRY-RUN — nenhuma alteracao salva'))
