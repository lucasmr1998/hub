import logging

from django.core.management.base import BaseCommand
from django.db.models import Q

from integracoes.models import IntegracaoAPI, ClienteHubsoft
from integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
from vendas_web.models import LeadProspecto

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Consulta a API Hubsoft e sincroniza os dados de clientes '
        'vinculados a leads com status_api="processado".'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--lead-id', type=int,
            help='Sincronizar apenas o lead com este ID.',
        )
        parser.add_argument(
            '--todos', action='store_true',
            help='Re-sincronizar todos os processados, mesmo os já sincronizados.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Apenas listar os leads que seriam sincronizados.',
        )
        parser.add_argument(
            '--limite', type=int, default=0,
            help='Sincronizar no máximo N clientes por execução (0 = sem limite).',
        )
        parser.add_argument(
            '--minutos-desde-sync', type=int, default=0,
            help='Só sincronizar clientes cujo último sync foi há mais de N minutos.',
        )
        parser.add_argument(
            '--horas-backoff-fantasma', type=int, default=6,
            help='Backoff (em horas) para leads não encontrados, aplicado APÓS a janela de grace. Padrão: 6h.',
        )
        parser.add_argument(
            '--minutos-grace', type=int, default=15,
            help='Janela inicial (em minutos) sem backoff — sync continua tentando a cada ciclo. Padrão: 15min.',
        )

    def handle(self, *args, **options):
        from django.utils import timezone
        from datetime import timedelta

        integracao = IntegracaoAPI.objects.filter(tipo='hubsoft', ativa=True).first()
        if not integracao:
            self.stderr.write(self.style.ERROR(
                'Nenhuma integração Hubsoft ativa encontrada.'
            ))
            return

        # Filtrar ClienteHubsoft pelo tempo de último sync (incremental)
        clientes_qs = ClienteHubsoft.objects.filter(lead__isnull=False)
        minutos = options.get('minutos_desde_sync') or 0
        if minutos > 0:
            corte = timezone.now() - timedelta(minutes=minutos)
            clientes_qs = clientes_qs.filter(data_sync__lt=corte)

        ids_com_cliente_filtrado = set(clientes_qs.values_list('lead_id', flat=True))
        ids_com_cliente_total = set(
            ClienteHubsoft.objects.filter(lead__isnull=False).values_list('lead_id', flat=True)
        )

        # Política de backoff em 2 fases pra leads não encontrados:
        # - Janela de grace (15min desde a 1ª tentativa): sync continua tentando
        # - Após a janela: backoff longo (6h) entre tentativas
        horas_bk = options.get('horas_backoff_fantasma') or 6
        minutos_grace = options.get('minutos_grace') or 15
        agora = timezone.now()
        corte_grace = agora - timedelta(minutes=minutos_grace)  # 1ª tentativa < corte = janela expirada
        corte_bk = agora - timedelta(hours=horas_bk)            # última tentativa >= corte = ainda em backoff

        # Buscar pares (lead_id, data_sync_cliente)
        dados_clientes = dict(
            ClienteHubsoft.objects.filter(lead__isnull=False)
            .values_list('lead_id', 'data_sync')
        )
        # Leads com ClienteHubsoft que tiveram tentativa pós-data_sync (= não encontrados)
        leads_com_tentativa = LeadProspecto.objects.filter(
            pk__in=ids_com_cliente_total,
            data_ultima_tentativa_sync_hubsoft__isnull=False,
        ).values_list(
            'pk',
            'data_ultima_tentativa_sync_hubsoft',
            'data_primeira_tentativa_sync_hubsoft',
        )

        orfaos_em_backoff = set()
        for lead_pk, dt_ultima, dt_primeira in leads_com_tentativa:
            data_sync_cli = dados_clientes.get(lead_pk)
            # Última tentativa MAIS recente que data_sync = Hubsoft retornou vazio (órfão)
            if not (data_sync_cli and dt_ultima > data_sync_cli):
                continue
            # Janela de grace ainda ativa? (1ª tentativa < 15min atrás) → não bloqueia
            if dt_primeira and dt_primeira >= corte_grace:
                continue
            # Janela expirada — aplica backoff se a última tentativa foi < 6h atrás
            if dt_ultima >= corte_bk:
                orfaos_em_backoff.add(lead_pk)

        # Remover órfãos em backoff do queryset elegível
        ids_com_cliente_filtrado -= orfaos_em_backoff

        if options['lead_id']:
            qs = LeadProspecto.objects.filter(pk=options['lead_id'])
        elif options['todos']:
            qs = LeadProspecto.objects.filter(
                Q(status_api='processado') | Q(pk__in=ids_com_cliente_filtrado)
            )
        else:
            # Fantasmas: lead processado SEM ClienteHubsoft.
            # Em backoff = passou da janela de grace E última tentativa < 6h
            ids_em_backoff = set(
                LeadProspecto.objects
                .filter(status_api='processado')
                .exclude(pk__in=ids_com_cliente_total)
                .filter(data_primeira_tentativa_sync_hubsoft__lt=corte_grace)  # janela expirou
                .filter(data_ultima_tentativa_sync_hubsoft__gte=corte_bk)      # < 6h da última
                .values_list('pk', flat=True)
            )

            ids_novos = set(
                LeadProspecto.objects
                .filter(status_api='processado')
                .exclude(pk__in=ids_com_cliente_total)
                .exclude(pk__in=ids_em_backoff)
                .values_list('pk', flat=True)
            )
            qs = LeadProspecto.objects.filter(pk__in=ids_novos | ids_com_cliente_filtrado)

        # Priorizar:
        # 1) Leads que nunca foram sincronizados (sem ClienteHubsoft)
        # 2) Depois os com sync mais antigo
        leads_novos = list(qs.exclude(pk__in=ids_com_cliente_total).order_by('id'))
        leads_existentes = list(
            qs.filter(pk__in=ids_com_cliente_total)
            .order_by('clientes_hubsoft__data_sync', 'id')
        )
        leads = leads_novos + leads_existentes

        # Aplicar limite
        limite = options.get('limite') or 0
        if limite > 0:
            leads = leads[:limite]

        if not leads:
            self.stdout.write(self.style.WARNING('Nenhum lead para sincronizar.'))
            return

        self.stdout.write(f'Encontrados {len(leads)} lead(s) para sincronizar.\n')

        if options['dry_run']:
            for lead in leads:
                self.stdout.write(
                    f'  [DRY-RUN] ID={lead.id} | {lead.nome_razaosocial} | '
                    f'cpf_cnpj={lead.cpf_cnpj} | id_hubsoft={lead.id_hubsoft}'
                )
            return

        service = HubsoftService(integracao)
        ok = 0
        nao_encontrados = 0
        erros = 0

        from django.utils import timezone as _tz

        for lead in leads:
            self.stdout.write(
                f'  Sincronizando ID={lead.id} | {lead.nome_razaosocial}... ',
                ending='',
            )
            try:
                cliente = service.sincronizar_cliente(lead)
                # Marcar tentativa (sucesso ou não)
                _agora_tentativa = _tz.now()
                LeadProspecto.objects.filter(pk=lead.pk).update(
                    data_ultima_tentativa_sync_hubsoft=_agora_tentativa,
                )
                # 1ª tentativa: só seta se ainda nulo (idempotente)
                LeadProspecto.objects.filter(
                    pk=lead.pk, data_primeira_tentativa_sync_hubsoft__isnull=True
                ).update(data_primeira_tentativa_sync_hubsoft=_agora_tentativa)
                if cliente:
                    alteracao_info = ""
                    if cliente.houve_alteracao:
                        alteracao_info = " [ALTERAÇÕES DETECTADAS]"
                    self.stdout.write(self.style.SUCCESS(
                        f'OK (id_cliente={cliente.id_cliente}, '
                        f'servicos={cliente.servicos.count()}){alteracao_info}'
                    ))
                    ok += 1
                else:
                    self.stdout.write(self.style.WARNING('NÃO ENCONTRADO no Hubsoft'))
                    nao_encontrados += 1

            except HubsoftServiceError as exc:
                _agora_tentativa = _tz.now()
                LeadProspecto.objects.filter(pk=lead.pk).update(
                    data_ultima_tentativa_sync_hubsoft=_agora_tentativa,
                )
                # 1ª tentativa: só seta se ainda nulo (idempotente)
                LeadProspecto.objects.filter(
                    pk=lead.pk, data_primeira_tentativa_sync_hubsoft__isnull=True
                ).update(data_primeira_tentativa_sync_hubsoft=_agora_tentativa)
                self.stdout.write(self.style.ERROR(f'ERRO: {exc}'))
                erros += 1

            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'ERRO INESPERADO: {exc}'))
                logger.exception("Erro ao sincronizar lead pk=%s", lead.pk)
                erros += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Concluído: {ok} sincronizado(s), '
            f'{nao_encontrados} não encontrado(s), {erros} erro(s).'
        ))
