import logging

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
from apps.comercial.leads.models import LeadProspecto

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Processa leads com status_api="pendente" que ainda não foram '
        'enviados ao Hubsoft (id_hubsoft vazio/nulo).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--lead-id',
            type=int,
            help='Processar apenas o lead com este ID.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas listar os leads que seriam processados, sem enviar.',
        )

    def handle(self, *args, **options):
        integracao = IntegracaoAPI.objects.filter(tipo='hubsoft', ativa=True).first()
        if not integracao:
            self.stderr.write(self.style.ERROR(
                'Nenhuma integração Hubsoft ativa encontrada.'
            ))
            return

        qs = LeadProspecto.objects.filter(
            status_api='pendente',
        ).filter(
            Q(id_hubsoft__isnull=True) | Q(id_hubsoft='')
        )

        if options['lead_id']:
            qs = qs.filter(pk=options['lead_id'])

        leads = list(qs.order_by('id'))

        if not leads:
            self.stdout.write(self.style.WARNING('Nenhum lead pendente encontrado.'))
            return

        self.stdout.write(f'Encontrados {len(leads)} lead(s) pendente(s).\n')

        if options['dry_run']:
            for lead in leads:
                self.stdout.write(
                    f'  [DRY-RUN] ID={lead.id} | {lead.nome_razaosocial} | '
                    f'cpf_cnpj={lead.cpf_cnpj}'
                )
            return

        service = HubsoftService(integracao)
        ok = 0
        erros = 0

        for lead in leads:
            self.stdout.write(
                f'  Processando ID={lead.id} | {lead.nome_razaosocial}... ',
                ending='',
            )
            try:
                resposta = service.cadastrar_prospecto(lead)
                id_prospecto = resposta.get('prospecto', {}).get('id_prospecto')

                campos_update = {'status_api': 'processado'}
                if id_prospecto:
                    campos_update['id_hubsoft'] = str(id_prospecto)

                LeadProspecto.objects.filter(pk=lead.pk).update(**campos_update)
                self.stdout.write(self.style.SUCCESS(
                    f'OK (id_prospecto={id_prospecto})'
                ))
                ok += 1

            except HubsoftServiceError as exc:
                LeadProspecto.objects.filter(pk=lead.pk).update(status_api='erro')
                self.stdout.write(self.style.ERROR(f'ERRO: {exc}'))
                erros += 1

            except Exception as exc:
                LeadProspecto.objects.filter(pk=lead.pk).update(status_api='erro')
                self.stdout.write(self.style.ERROR(f'ERRO INESPERADO: {exc}'))
                logger.exception("Erro ao processar lead pk=%s", lead.pk)
                erros += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Concluído: {ok} enviado(s), {erros} erro(s).'))
