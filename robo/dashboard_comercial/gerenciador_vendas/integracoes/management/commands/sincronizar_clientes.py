import logging

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.integracoes.models import IntegracaoAPI, ClienteHubsoft
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
from apps.comercial.leads.models import LeadProspecto

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Consulta a API Hubsoft e sincroniza os dados de clientes '
        'vinculados a leads com status_api="processado".'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--lead-id',
            type=int,
            help='Sincronizar apenas o lead com este ID.',
        )
        parser.add_argument(
            '--todos',
            action='store_true',
            help='Re-sincronizar todos os processados, mesmo os já sincronizados.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas listar os leads que seriam sincronizados.',
        )

    def handle(self, *args, **options):
        integracao = IntegracaoAPI.objects.filter(tipo='hubsoft', ativa=True).first()
        if not integracao:
            self.stderr.write(self.style.ERROR(
                'Nenhuma integração Hubsoft ativa encontrada.'
            ))
            return

        qs = LeadProspecto.objects.filter(status_api='processado')

        if options['lead_id']:
            qs = qs.filter(pk=options['lead_id'])
        elif not options['todos']:
            ids_ja_sincronizados = ClienteHubsoft.objects.filter(
                lead__isnull=False,
            ).values_list('lead_id', flat=True)
            qs = qs.exclude(pk__in=ids_ja_sincronizados)

        leads = list(qs.order_by('id'))

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

        for lead in leads:
            self.stdout.write(
                f'  Sincronizando ID={lead.id} | {lead.nome_razaosocial}... ',
                ending='',
            )
            try:
                cliente = service.sincronizar_cliente(lead)
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
