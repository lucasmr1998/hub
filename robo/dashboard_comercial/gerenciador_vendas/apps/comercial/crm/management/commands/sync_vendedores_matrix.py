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
            f'Matrix: atribuidos={atribuidos} '
            f'sem_agente_no_matrix={sem_login_no_matrix} '
            f'sem_user_no_hubtrix={sem_match_no_hubtrix} '
            f'erros={erros}'
        ))

        # ─── Fase 2: sync Talk ───
        # Analogo ao Matrix mas usando cod_talk do PerfilUsuario.
        # So roda se o tenant tem IntegracaoAPI(tipo='talk') ativa.
        self._sync_talk(tenant, cutoff, opts)

        if opts['dry_run']:
            self.stdout.write(self.style.WARNING('DRY-RUN — nenhuma alteracao salva'))

    def _sync_talk(self, tenant, cutoff, opts):
        """Sync analogo pra atribuicao de responsavel em ops originadas do Talk.

        Filtro: ops sem responsavel, importadas do Talk (dados_custom.importado_do_talk),
        criadas apos `cutoff`.
        """
        from apps.integracoes.services.talk import TalkService, TalkServiceError
        from apps.sistema.models import PerfilUsuario
        from apps.comercial.crm.models import OportunidadeVenda
        try:
            svc = TalkService.from_tenant(tenant)
        except TalkServiceError as e:
            self.stdout.write(self.style.WARNING(f'Talk nao configurado pra {tenant.slug}: {e}'))
            return

        # importado_do_talk fica no lead.dados_custom (populado pelo importador de prospects Talk).
        # Filtro em 2 passos: `LeadProspecto.all_tenants` porque JSONField lookup nao propaga
        # bem com FK cruzando managers `all_tenants` (Django faz JOIN mas nao aplica o
        # segundo filtro dentro do JSON).
        from apps.comercial.leads.models import LeadProspecto
        lead_ids = list(LeadProspecto.all_tenants
                        .filter(tenant=tenant, dados_custom__importado_do_talk=True)
                        .values_list('id', flat=True))
        qs = (OportunidadeVenda.all_tenants
              .filter(tenant=tenant, responsavel__isnull=True,
                      data_criacao__gte=cutoff,
                      lead_id__in=lead_ids)
              .select_related('lead')
              .order_by('-data_criacao')[:opts['limit']])
        total = qs.count()
        self.stdout.write(f'Talk: {total} oportunidades elegiveis pra sync')

        # Mapa nom_agente_normalizado -> cod_agente (pra descobrir cod a partir da chamada)
        import unicodedata, re
        def _norm(s):
            if not s: return ''
            s = unicodedata.normalize('NFD', str(s)).encode('ascii','ignore').decode()
            return re.sub(r'\s+', ' ', s.lower().strip())
        try:
            agentes = svc.listar_agentes()
        except TalkServiceError as e:
            self.stdout.write(self.style.ERROR(f'Talk listar_agentes falhou: {e}'))
            return
        nom_to_cod = {}
        for a in agentes:
            nom_norm = _norm(a.get('nom_agente'))
            cod = a.get('cod_agente')
            if nom_norm and cod:
                nom_to_cod[nom_norm] = int(cod)

        # Cache: cod_talk -> User
        perfis = PerfilUsuario.objects.filter(
            tenant=tenant, cod_talk__isnull=False,
        ).select_related('user')
        cod_to_user = {p.cod_talk: p.user for p in perfis if p.cod_talk}
        self.stdout.write(f'  {len(cod_to_user)} usuarios com cod_talk mapeado')

        atribuidos = 0
        sem_chamada = 0
        sem_agente_atendeu = 0
        sem_match_no_hubtrix = 0
        erros = 0

        for oport in qs:
            lead = oport.lead
            if not lead or not lead.telefone:
                sem_chamada += 1
                continue
            tel = ''.join(c for c in str(lead.telefone) if c.isdigit())
            if len(tel) > 11:
                tel = tel[-11:]  # remove DDI 55

            # Descobrir data da criacao do lead pra rastreabilidade
            data_ref = None
            dc = lead.dados_custom or {}
            iso = dc.get('talk_created_at')
            if iso:
                try:
                    from datetime import datetime
                    from django.utils import timezone as dj_tz
                    dt = datetime.fromisoformat(str(iso).replace('Z','+00:00'))
                    data_ref = dj_tz.localtime(dt).date()
                except Exception:  # noqa: BLE001
                    pass
            if not data_ref:
                data_ref = oport.data_criacao.date()

            try:
                chamadas = svc.listar_chamadas_por_telefone(tel, data_ref.strftime('%Y-%m-%d'))
            except TalkServiceError as e:
                erros += 1
                logger.warning('[sync_vendedores_matrix/talk] oport=%s erro: %s', oport.pk, e)
                continue

            # Pega a chamada Atendida com agente preenchido (mais recente)
            atendida_com_agente = None
            for ch in sorted(chamadas, key=lambda x: x.get('dat_ligacao') or '', reverse=True):
                nom = (ch.get('nom_agente') or '').strip()
                resposta = (ch.get('nom_resposta') or '').strip().lower()
                if nom and resposta in ('atendida', ''):
                    atendida_com_agente = ch
                    break

            if not atendida_com_agente:
                sem_agente_atendeu += 1
                continue

            nom_ag = atendida_com_agente.get('nom_agente') or ''
            cod = nom_to_cod.get(_norm(nom_ag))
            if not cod:
                # Nao achou cod pelo nome — talvez nome mudou. Loga e pula.
                self.stdout.write(self.style.WARNING(
                    f'  oport={oport.pk} nom_agente={nom_ag!r} sem cod_agente conhecido no Talk'
                ))
                sem_match_no_hubtrix += 1
                continue
            user = cod_to_user.get(cod)
            if not user:
                self.stdout.write(self.style.WARNING(
                    f'  oport={oport.pk} nom_agente={nom_ag!r} cod={cod} sem PerfilUsuario.cod_talk mapeado'
                ))
                sem_match_no_hubtrix += 1
                continue

            self.stdout.write(self.style.SUCCESS(
                f'  oport={oport.pk} <- {user.username} (Talk cod={cod} nom={nom_ag!r})'
            ))
            if not opts['dry_run']:
                oport.responsavel = user
                oport.save(update_fields=['responsavel', 'data_atualizacao'])
                from apps.sistema.utils import registrar_acao
                try:
                    registrar_acao('crm', 'atribuir', 'oportunidade', oport.pk,
                                   f'Atribuido automatic via Talk (cod={cod}, nom={nom_ag}) para {user.username}',
                                   dados_extras={
                                       'cod_talk': cod,
                                       'nom_agente': nom_ag,
                                       'origem': 'sync_vendedores_talk',
                                   })
                except Exception:  # noqa: BLE001
                    pass
            atribuidos += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Talk: atribuidos={atribuidos} '
            f'sem_chamada={sem_chamada} '
            f'sem_agente_atendeu={sem_agente_atendeu} '
            f'sem_user_no_hubtrix={sem_match_no_hubtrix} '
            f'erros={erros}'
        ))
